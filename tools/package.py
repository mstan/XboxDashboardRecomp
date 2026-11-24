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
    parser.add_argument("--build", required=True, type=Path)
    parser.add_argument("--sdl-license", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    baseline = json.loads((ROOT / "release-baseline.json").read_text(encoding="utf-8"))
    runtime_hash = digest(args.runtime_archive)
    if runtime_hash != baseline["assets"].get(args.runtime_archive.name):
        raise ValueError("The Dashboard runtime archive does not match its published baseline")
    files = {
        "XboxDashboard.exe": args.build / "XboxDashboard.exe",
        "launch_dashboard.py": ROOT / "tools/launch_dashboard.py",
        "README.md": ROOT / "SETUP.md",
        "LICENSE": ROOT / "LICENSE",
        "licenses/recomp-ui-LICENSE": ROOT / "recomp-ui/LICENSE",
        "licenses/imgui-LICENSE.txt": ROOT / "recomp-ui/src/third_party/imgui/LICENSE.txt",
        "licenses/SDL2-LICENSE.txt": args.sdl_license,
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
        "xboxllr_runtime": baseline["runtime_revision"],
        "runtime_archive_sha256": runtime_hash,
        "files": {name: digest(path) for name, path in files.items()},
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.runtime_archive) as runtime, zipfile.ZipFile(
        args.out, "x", zipfile.ZIP_DEFLATED, compresslevel=3
    ) as archive:
        for name, path in files.items():
            archive.write(path, name)
        for member in runtime.infolist():
            if not member.is_dir():
                with runtime.open(member) as source, archive.open("runtime/" + member.filename, "w") as target:
                    shutil.copyfileobj(source, target)
        archive.writestr("build.json", json.dumps(metadata, indent=2) + "\n")
    with zipfile.ZipFile(args.out) as archive:
        if archive.testzip() is not None:
            raise ValueError("Package integrity check failed")
    print(f"{digest(args.out)}  {args.out}")


if __name__ == "__main__":
    main()
