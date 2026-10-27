#!/usr/bin/env python3
"""Repack the APK with the patched translate.dat.

Drops META-INF/* so the stale v1 signature cannot survive, and preserves each
original entry's compression method (resources.arsc must stay stored).
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

ROOT = Path(r"D:\project\逆向\北方的扩张")
SRC = ROOT / "com.herocraft.game.majesty_ne.apk"
DEFAULT_PATCH = ROOT / "build" / "assets" / "translate.dat"
DEFAULT_OUT = ROOT / "build" / "majesty_zh_poc.apk"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    # optional argv: <translate.dat> <output.apk> ; defaults keep the v1 flow.
    PATCH = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PATCH
    OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_OUT
    patched = PATCH.read_bytes()
    print(f"patched payload: {len(patched)} bytes")

    with zipfile.ZipFile(SRC) as zin, zipfile.ZipFile(OUT, "w") as zout:
        dropped: list[str] = []
        kept = 0
        for item in zin.infolist():
            if item.filename.startswith("META-INF/"):
                dropped.append(item.filename)
                continue
            if item.filename == "assets/translate.dat":
                continue
            zout.writestr(item, zin.read(item.filename))
            kept += 1
        zout.writestr("assets/translate.dat", patched, zipfile.ZIP_DEFLATED)

    print(f"entries kept={kept}  dropped={dropped}")
    print(f"wrote {OUT}  ({OUT.stat().st_size} bytes)")

    # sanity: the new archive must still contain a stored resources.arsc
    with zipfile.ZipFile(OUT) as z:
        info = z.getinfo("resources.arsc")
        mode = "STORED" if info.compress_type == zipfile.ZIP_STORED else "DEFLATED"
        print(f"resources.arsc: {mode}, {info.file_size} bytes")
        print(f"translate.dat : {z.getinfo('assets/translate.dat').file_size} bytes")
        print(f"total entries : {len(z.infolist())}")


if __name__ == "__main__":
    main()
