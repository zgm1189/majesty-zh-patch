#!/usr/bin/env python3
"""Work out the .dat framing: header, per-record stride, and tail layout."""

from __future__ import annotations

import sys
from pathlib import Path

DIR = Path(r"D:\project\逆向\北方的扩张\extracted\_res\assets\huge\respack")


def tail_dump(name: str) -> None:
    b = (DIR / name).read_bytes()
    print(f"=== {name}  size={len(b)}")
    print(f"  head 8 : {b[:8].hex(' ')}")
    print(f"  tail 48: {b[-48:].hex(' ')}")
    # walk backwards in strides of 14 to see where framing stays sane
    print("  backward stride-14 decode of the last records:")
    for k in range(4, 0, -1):
        o = len(b) - 5 - k * 14
        rec = b[o : o + 14]
        if len(rec) < 14:
            continue
        ch = int.from_bytes(rec[0:2], "little")
        x = int.from_bytes(rec[4:6], "little") + int.from_bytes(rec[6:8], "little")
        y = int.from_bytes(rec[8:10], "little")
        w = int.from_bytes(rec[10:12], "little")
        h = int.from_bytes(rec[12:14], "little")
        print(f"    off={o:5d} bytes={rec.hex(' ')} char={ch} x={x} y={y} w={w} h={h}")
    print()


def extents(prefix: str) -> None:
    print(f"--- {prefix} family ---")
    for suffix in ("0", "1", "2"):
        p = DIR / f"{prefix}{suffix}.dat"
        if not p.exists():
            continue
        b = p.read_bytes()
        head = int.from_bytes(b[0:2], "little")
        n = (len(b) - 2) // 14
        maxx = maxy = 0
        codes = []
        for i in range(n):
            o = 2 + i * 14
            rec = b[o : o + 14]
            ch = int.from_bytes(rec[0:2], "little")
            x = int.from_bytes(rec[4:6], "little") + int.from_bytes(rec[6:8], "little")
            y = int.from_bytes(rec[8:10], "little")
            w = int.from_bytes(rec[10:12], "little")
            h = int.from_bytes(rec[12:14], "little")
            if w < 64 and h < 64:  # ignore obviously mis-framed tail entries
                maxx = max(maxx, x + w)
                maxy = max(maxy, y + h)
                codes.append(ch)
        print(f"  {p.name:12s} size={len(b):5d} head={head:3d} recs={n:3d} extent={maxx}x{maxy}")
        print(f"     codes: {''.join(chr(c) if 32 <= c < 127 else '.' for c in codes[:60])}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    tail_dump("fntm0.dat")
    extents("fntm")
