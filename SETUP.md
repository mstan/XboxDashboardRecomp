# Xbox Dashboard Recomp

Standalone consumer for the original Xbox Dashboard 5960. This repo owns the Dashboard definition, title recovery inputs and release channel. The shared native runtime and tooling are supplied by the pinned [xboxllr](https://github.com/mstan/xboxllr) submodule.

## Windows

Extract the Windows x64 release and run `XboxDashboard.exe`. Choose a raw
Xbox HDD image (`.img` or `.bin`) or a `.qcow2` image with the original
Dashboard 5960 on its C partition. Play imports the Dashboard into a local
cache and opens the original Dashboard in the native runtime. The HDD image
is opened read-only. Local console settings and saves live under `runtime/data`.

The Windows player uses the xboxllr HLE runtime with the original Dashboard integrity table. The support files and exact runtime revision come from the [XboxLLR Dashboard release](https://github.com/mstan/xboxllr/releases/tag/beta-2026.11.01.1).

## Build

Initialize the submodule and use the pinned engine's [development prerequisites](xboxllr/docs/DEVELOPMENT.md). Store user input paths and console data outside Git. The [path template](dashboard/paths.example.json) describes inputs to the developer build driver. The [native title guide](xboxllr/docs/NATIVE-TITLE-DRIVER.md) describes provenance and the prepare, configure, build and run commands.

```powershell
git submodule update --init --recursive
$opts = @('--paths', 'local/paths.json', '--generated', 'G:/Private/Dashboard/generated', '--build-dir', 'G:/Private/Dashboard/build')
python tools/dashboard.py check @opts
python tools/dashboard.py prepare @opts
python tools/dashboard.py configure @opts
python tools/dashboard.py build @opts
```

The existing package records both its runtime source revision and its packaging revision in `BUILD-PROVENANCE.json`. The player and its corresponding source remain linked to those revisions.

To build the release's front end, configure this repository with CMake
using MinGW and SDL2. Build the `XboxDashboard` target in Release mode.
`tools/package.py` combines the launcher and a stock HLE Dashboard runtime
with the support archive identified in `release-baseline.json`. Leave the
native title and section mod source options empty when building the runtime.
