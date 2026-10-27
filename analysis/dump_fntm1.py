#!/usr/bin/env python3
"""Inspect fntm1/fntm2 framing: are their slots usable for Chinese glyphs?"""

from __future__ import annotations

import sys
from pathlib import Path

DIR = Path(r"D:\project\逆向\北方的扩张\extracted\_res\assets\huge\respack")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    for name in ("fntm0.dat", "fntm1.dat", "fntm2.dat"):
        b = (DIR / name).read_bytes()
        print(f"=== {name}  size={len(b)}  head={int.from_bytes(b[0:2], 'little')}")
        print(f"    bytes[0:18]: {b[0:18].hex(' ')}")
        for i in range(5):
            o = 2 + i * 14
            rec = b[o : o + 14]
            if len(rec) < 14:
                break
            vals = [int.from_bytes(rec[j : j + 2], "little") for j in range(0, 14, 2)]
            ch = int.from_bytes(rec[0:2], "little")
            label = chr(ch) if 32 <= ch < 0x300 else "."
            print(f"    rec{i} @{o:5d} u16LE={vals}  char={ch:#06x} '{label}'")
        print()


if __name__ == "__main__":
    main()
