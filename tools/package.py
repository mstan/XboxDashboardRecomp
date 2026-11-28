# SPDX-License-Identifier: GPL-3.0-or-later
"""Package a recomp-ui Dashboard player with the verified native runtime."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'xboxllr-tools/tools'))
from native_release_archive import compose


def digest(path):
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def revision(path):
    subprocess.run(["git", "-C", path, "diff", "--quiet", "HEAD", "--"], check=True)
    return subprocess.check_output(["git", "-C", path, "rev-parse", "HEAD"], text=True).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-archive", required=True, type=Path)
    parser.add_argument("--runtime-build", type=Path,
                        help="Optional replacement stock HLE runtime build; default preserves the admitted archive runtime")
    parser.add_argument("--build", required=True, type=Path)
    parser.add_argument("--sdl-license", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    baseline = json.loads((ROOT / "release-baseline.json").read_text(encoding="utf-8"))
    runtime_hash = digest(args.runtime_archive)
    if runtime_hash != baseline["assets"].get(args.runtime_archive.name):
        raise ValueError("The Dashboard runtime archive does not match its published baseline")
    native = None
    if args.runtime_build:
        cache = {}
        for line in (args.runtime_build / 'CMakeCache.txt').read_text().splitlines():
            if line.startswith(('PILOT_', 'XBOXLLR_BUILD_MODE:', 'CMAKE_HOME_DIRECTORY:')) and '=' in line:
                key, value = line.split('=', 1)
                cache[key.split(':', 1)[0]] = value
        if (cache.get('XBOXLLR_BUILD_MODE') != 'NATIVE_TITLE' or cache.get('PILOT_MEDIA') != 'HOST' or
                cache.get('PILOT_SECTION_MOD_SOURCE') != '' or cache.get('PILOT_TITLE_MOD_SOURCE')):
            raise ValueError('Use the stock native Dashboard target with both mod sources empty')
        native = args.runtime_build / 'native-title/Release/XboxDashboard.exe'
        framework = revision(Path(cache['CMAKE_HOME_DIRECTORY']))
        if framework != baseline['runtime_revision']:
            raise ValueError('Build the stock runtime from the release baseline runtime revision')
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
    # Runtime admission is title-owned. Full composition, dependency closure,
    # private-input exclusion and archive publication belong to the engine.
    with zipfile.ZipFile(args.runtime_archive) as runtime:
        names = [member.filename for member in runtime.infolist() if not member.is_dir()]
        if len(names) != len(set(names)):
            raise ValueError('Duplicate frozen runtime archive entry')
        descriptor = json.loads(runtime.read('release.json'))
        if set(names) != set(descriptor['files']) | {'release.json'}:
            raise ValueError('Frozen runtime inventory differs from its manifest')
        for name, expected in descriptor['files'].items():
            with runtime.open(name) as stream:
                if hashlib.file_digest(stream, 'sha256').hexdigest() != expected:
                    raise ValueError('Frozen runtime member changed: ' + name)
        provenance_bytes = runtime.read('BUILD-PROVENANCE.json')
        provenance = json.loads(provenance_bytes)
        framework = baseline['runtime_revision']
        executable = descriptor['executable']
        native_hash = descriptor['files'][executable]
        if (provenance.get('runtime_framework_revision') != framework or
                provenance.get('runtime_source_revision') != framework or
                provenance.get('runtime_sha256') != native_hash):
            raise ValueError('Frozen runtime source/binary identity differs from the baseline')
        descriptor_bytes = runtime.read('release.json')
        if native is not None:
            native_hash = digest(native)
            provenance.update(runtime_framework_revision=framework, runtime_source_revision=framework,
                              runtime_sha256=native_hash)
            provenance_bytes = (json.dumps(provenance, indent=2)+'\n').encode()
            descriptor['files'][executable] = native_hash
            descriptor['files']['BUILD-PROVENANCE.json'] = hashlib.sha256(provenance_bytes).hexdigest()
            descriptor_bytes = (json.dumps(descriptor, indent=2)+'\n').encode()
        metadata = dict(version='0.2.0', source=revision(ROOT), recomp_ui=revision(ROOT/'recomp-ui'),
            xboxllr_packaging=baseline['packaging_revision'], xboxllr_tools=revision(ROOT/'xboxllr-tools'),
            xboxllr_runtime=framework, native_sha256=native_hash, runtime_archive_sha256=runtime_hash,
            files={name: digest(path) for name,path in files.items()})
        payloads = dict(files)
        for name in names:
            payloads['runtime/' + name] = lambda name=name: runtime.open(name)
        if native is not None:
            payloads['runtime/' + executable] = native
        payloads['runtime/BUILD-PROVENANCE.json'] = provenance_bytes
        payloads['runtime/release.json'] = descriptor_bytes
        metadata['files'].update({'runtime/' + name: expected for name, expected in descriptor['files'].items()})
        metadata['files']['runtime/release.json'] = hashlib.sha256(payloads['runtime/release.json']).hexdigest()
        payloads['build.json'] = (json.dumps(metadata, indent=2)+'\n').encode()
        compose(payloads, args.out, title=descriptor['title'],
                distribution=descriptor['distribution'], provenance=metadata)
    print(f"{digest(args.out)}  {args.out}")


if __name__ == "__main__":
    main()
