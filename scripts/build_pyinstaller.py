from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ICON = ROOT / "assets" / "app.ico"


def main() -> int:
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--name",
        "652-Checkin-Desktop",
        "--add-data",
        f"{ROOT / 'assets'};assets",
    ]
    if ICON.exists():
        cmd.extend(["--icon", str(ICON)])
    cmd.append(str(ROOT / "main.py"))
    return subprocess.call(cmd, cwd=str(ROOT))


if __name__ == "__main__":
    raise SystemExit(main())
