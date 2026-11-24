# Xbox Dashboard Recomp

Standalone consumer for the original Xbox Dashboard 5960. This repo owns the Dashboard definition, title recovery inputs and release channel. The shared native runtime and tooling are supplied by the pinned [xboxllr](https://github.com/mstan/xboxllr) submodule.

## Windows beta

The archived November 1 Windows x64 beta is the already qualified native player from the [XboxLLR Dashboard release](https://github.com/mstan/xboxllr/releases/tag/beta-2026.11.01.1). This historical package expects a Dashboard 5960 content installation. A whole HDD image import is still needed for a new player release. See the [feature coverage](xboxllr/docs/DASHBOARD.md) for the archived runtime.

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
