#!/usr/bin/env python3
"""Dump the Marmalade font descriptor (.dat) record layout.

Goal: recover the "character code -> atlas rectangle" mapping so a Chinese
glyph can be placed at a known slot later.
"""

from __future__ import annotations

import sys
from pathlib import Path

DIR = Path(r"D:\project\逆向\北方的扩张\extracted\_res\assets\huge\respack")


def dump(name: str, stride: int = 14, start: int = 2, count: int = 10) -> None:
    p = DIR / name
    b = p.read_bytes()
    print(f"=== {name}  size={len(b)}")
    print(f"    head: {b[:64].hex(' ')}")
    for i in range(count):
        o = start + i * stride
        rec = b[o : o + 14]
        if len(rec) < 14:
            break
        vals = [int.from_bytes(rec[j : j + 2], "little") for j in range(0, 14, 2)]
        ch = rec[0]
        show = chr(ch) if 32 <= ch < 127 else "."
        print(f"  rec{i:2d} off={o:5d} {rec.hex(' ')}")
        print(f"         u16LE={vals}  b0={ch:#04x} '{show}'")
    print()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    dump("fntm0.dat")
    dump("fntw0.dat")
