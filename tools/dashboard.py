# SPDX-License-Identifier: GPL-3.0-or-later
"""Run the engine's native title driver with this Dashboard definition."""

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


if __name__ == "__main__":
    raise SystemExit(subprocess.call([
        sys.executable, ROOT / "xboxllr/tools/native_title.py",
        "--title", ROOT / "dashboard/title.toml", "--jobs", "2", *sys.argv[1:]
    ], cwd=ROOT))
