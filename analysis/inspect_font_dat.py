#!/usr/bin/env python3
"""Check the .dat header count and tail, to see whether records can be appended."""

from __future__ import annotations

import sys
from pathlib import Path

DIR = Path(r"D:\project\逆向\北方的扩张\extracted\_res\assets\huge\respack")
STRIDE = 14
START = 2


def parse(name: str):
    b = (DIR / name).read_bytes()
    head = int.from_bytes(b[0:2], "little")
    n = (len(b) - START) // STRIDE
    print(f"=== {name}  size={len(b)}  head_u16={head}  full_records={n}")
    print(f"    head bytes: {b[0:2].hex(' ')}   tail bytes: {b[-16:].hex(' ')}")
    # decode all records
    recs = []
    for i in range(n):
        o = START + i * STRIDE
        rec = b[o : o + STRIDE]
        ch = int.from_bytes(rec[0:2], "little")
        x = int.from_bytes(rec[4:6], "little") + int.from_bytes(rec[6:8], "little")
        y = int.from_bytes(rec[8:10], "little")
        w = int.from_bytes(rec[10:12], "little")
        h = int.from_bytes(rec[12:14], "little")
        recs.append((ch, x, y, w, h))
    print(f"    first 5: {recs[:5]}")
    print(f"    last 5 : {recs[-5:]}")
    # max extents used
    maxx = max(r[1] + r[3] for r in recs)
    maxy = max(r[2] + r[4] for r in recs)
    print(f"    atlas used extent: {maxx} x {maxy}")
    codes = "".join(chr(c) if 32 <= c < 127 else "." for c, *_ in recs)
    print(f"    codes: {codes[:100]}")
    leftover = (len(b) - START) % STRIDE
    print(f"    leftover bytes after records: {leftover}")
    return recs


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parse("fntm0.dat")
    parse("fntw0.dat")
