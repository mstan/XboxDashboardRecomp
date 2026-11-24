# SPDX-License-Identifier: GPL-3.0-or-later
"""Launch the packaged native Dashboard from files imported by recomp-ui."""

import argparse
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("xbe", type=Path)
    parser.add_argument("--volume", type=int, choices=range(101), default=100)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent / "runtime"
    sys.path.insert(0, str(root / "tools"))

    import native_release_runtime as runtime
    from native_boot_launcher import ui_state

    writable = runtime.writable_environment(root)
    data = runtime.descriptor(root)
    image = runtime.checked_image(data, args.xbe)
    data = runtime.select_revision(data, runtime.sha(image))
    choices = writable / "console-choice.txt"
    with runtime.session_lock(writable):
        choice = runtime.read_console_choice(choices)
        prepared = runtime.inside(root, runtime.profile_relative(data) + "/console").exists()
        catalog = runtime.Catalog(
            runtime.launcher_manifests(root, data),
            writable / "mod-selection.json",
            visibility=[root / "mods/ui-visibility.json"],
            frame_modes=data.get("launcher", {}).get("frame_modes", []),
            defaults=data.get("launcher", {}).get("defaults", {}),
            setup=dict(required=False, kernel=choice["kernel"], acknowledged=choice["acknowledged"],
                       eeprom=choice["eeprom"], storage=choice["storage"], hdd=choice.get("hdd", ""),
                       locked=prepared, choice_path=str(choices)),
            boot=ui_state(root, data, fallback_kernel=choice["kernel"]),
            sharp_presentation=data.get("launcher", {}).get("sharp_presentation", False),
        )
        catalog.volume = args.volume
        with runtime.game_storage(root, data, image, choices) as (profile, storage, hdd):
            if args.prepare_only:
                return 0
            return runtime.launch_game(root, data, image, profile, catalog, storage=storage, hdd=hdd)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError) as error:
        if sys.stderr is not None:
            print(error, file=sys.stderr)
        if "--prepare-only" not in sys.argv:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, str(error), "Xbox Dashboard setup", 0x10)
        raise SystemExit(2)
