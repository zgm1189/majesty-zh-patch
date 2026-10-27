#!/usr/bin/env python3
"""Decode fntM2 — hypothesis: it is the Cyrillic chardeck (U+0400 block)."""

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(r"D:\project\逆向\北方的扩张\extracted\_res\assets\huge\respack")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    for name in ("fntM2.dat", "fntW2.dat", "fntA2.dat"):
        b = (SRC / name).read_bytes()
        print(f"=== {name}: {len(b)} bytes ===")
        for hdr in (0, 2):
            n = (len(b) - hdr) // 14
            codes, rects = [], []
            for i in range(n):
                o = hdr + i * 14
                r = b[o : o + 14]
                ch = int.from_bytes(r[0:2], "little")
                x = int.from_bytes(r[4:6], "little") + int.from_bytes(r[6:8], "little")
                y = int.from_bytes(r[8:10], "little")
                w = int.from_bytes(r[10:12], "little")
                h = int.from_bytes(r[12:14], "little")
                codes.append(ch)
                rects.append((x, y, w, h))
            cyr = sum(1 for c in codes if 0x400 <= c <= 0x4FF)
            print(f"  hdr={hdr}: {n} recs, cyrillic={cyr}, "
                  f"min=U+{min(codes):04X} max=U+{max(codes):04X}")
        n = len(b) // 14
        print(f"  first 20 chars (hdr=0): "
              f"{' '.join(chr(int.from_bytes(b[i*14:i*14+2],'little')) for i in range(min(20, n)))}")
        print(f"  first 12 rects: {[(x, y, w, h) for (x, y, w, h) in rects[:12]]}")
        print()


if __name__ == "__main__":
    main()
