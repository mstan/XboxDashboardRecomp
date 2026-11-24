# SPDX-License-Identifier: GPL-3.0-or-later
"""Package a recomp-ui Dashboard player with the verified native runtime."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile


ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def revision(path):
    return subprocess.check_output(["git", "-C", path, "rev-parse", "HEAD"], text=True).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-archive", required=True, type=Path)
    parser.add_argument("--runtime-build", required=True, type=Path,
                        help="CMake build directory for the stock HLE Dashboard runtime")
    parser.add_argument("--build", required=True, type=Path)
    parser.add_argument("--sdl-license", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    baseline = json.loads((ROOT / "release-baseline.json").read_text(encoding="utf-8"))
    runtime_hash = digest(args.runtime_archive)
    if runtime_hash != baseline["assets"].get(args.runtime_archive.name):
        raise ValueError("The Dashboard runtime archive does not match its published baseline")
    cache = {}
    for line in (args.runtime_build / "CMakeCache.txt").read_text().splitlines():
        if line.startswith(("PILOT_", "XBOXLLR_BUILD_MODE:", "CMAKE_HOME_DIRECTORY:")) and "=" in line:
            key, value = line.split("=", 1)
            cache[key.split(":", 1)[0]] = value
    if (cache.get("XBOXLLR_BUILD_MODE") != "NATIVE_TITLE" or cache.get("PILOT_MEDIA") != "HOST" or
            cache.get("PILOT_SECTION_MOD_SOURCE") != "" or cache.get("PILOT_TITLE_MOD_SOURCE")):
        raise ValueError("Use the stock native Dashboard target with both mod sources empty")
    native = args.runtime_build / "native-title/Release/XboxDashboard.exe"
    native_hash = digest(native)
    framework = revision(Path(cache["CMAKE_HOME_DIRECTORY"]))
    if framework != baseline["runtime_revision"]:
        raise ValueError("Build the stock runtime from the release baseline's runtime revision")
    files = {
        "XboxDashboard.exe": args.build / "XboxDashboard.exe",
        "launch_dashboard.py": ROOT / "tools/launch_dashboard.py",
        "README.md": ROOT / "SETUP.md",
        "LICENSE": ROOT / "LICENSE",
        "licenses/recomp-ui-LICENSE": ROOT / "recomp-ui/LICENSE",
        "licenses/imgui-LICENSE.txt": ROOT / "recomp-ui/src/third_party/imgui/LICENSE.txt",
        "licenses/SDL2-LICENSE.txt": args.sdl_license,
        "licenses/XBOX-CONTROLLER-ARTWORK.md": ROOT / "assets/XBOX-CONTROLLER-ARTWORK.md",
    }
    assets = args.build / "assets"
    for path in sorted(assets.rglob("*")):
        if path.is_file():
            files["assets/" + path.relative_to(assets).as_posix()] = path
    metadata = {
        "version": "0.2.0",
        "source": revision(ROOT),
        "recomp_ui": revision(ROOT / "recomp-ui"),
        "xboxllr_packaging": baseline["packaging_revision"],
        "xboxllr_runtime": framework,
        "native_sha256": native_hash,
        "runtime_archive_sha256": runtime_hash,
        "files": {name: digest(path) for name, path in files.items()},
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.runtime_archive) as runtime, zipfile.ZipFile(
        args.out, "x", zipfile.ZIP_DEFLATED, compresslevel=3
    ) as archive:
        for name, path in files.items():
            archive.write(path, name)
        descriptor = json.loads(runtime.read("release.json"))
        provenance = json.loads(runtime.read("BUILD-PROVENANCE.json"))
        provenance.update(runtime_framework_revision=framework, runtime_source_revision=framework,
                          runtime_sha256=native_hash)
        encoded_provenance = (json.dumps(provenance, indent=2) + "\n").encode()
        executable = descriptor["executable"]
        descriptor["files"][executable] = native_hash
        descriptor["files"]["BUILD-PROVENANCE.json"] = hashlib.sha256(encoded_provenance).hexdigest()
        for member in runtime.infolist():
            if member.filename == executable:
                archive.write(native, "runtime/" + executable)
            elif member.filename == "BUILD-PROVENANCE.json":
                archive.writestr("runtime/" + member.filename, encoded_provenance)
            elif member.filename == "release.json":
                archive.writestr("runtime/" + member.filename, json.dumps(descriptor, indent=2) + "\n")
            elif not member.is_dir():
                with runtime.open(member) as source, archive.open("runtime/" + member.filename, "w") as target:
                    shutil.copyfileobj(source, target)
        archive.writestr("build.json", json.dumps(metadata, indent=2) + "\n")
    with zipfile.ZipFile(args.out) as archive:
        if archive.testzip() is not None:
            raise ValueError("Package integrity check failed")
    print(f"{digest(args.out)}  {args.out}")


if __name__ == "__main__":
    main()
