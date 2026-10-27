#!/usr/bin/env python3
"""Inspect the raw bytes of one glyph rectangle, to learn the visible/invisible
encoding without relying on my format guess."""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from export_groupbin import parse_container, resolve_geometry  # noqa: E402

DIR = Path(r"D:\project\逆向\北方的扩张\extracted\_res\assets\huge\respack")


def inspect(bin_name: str, dat_name: str, want: str) -> None:
    raw = (DIR / bin_name).read_bytes()
    name, blocks = parse_container(raw)
    dat = (DIR / dat_name).read_bytes()
    n = (len(dat) - 2) // 14
    rect = None
    for i in range(n):
        o = 2 + i * 14
        rec = dat[o : o + 14]
        ch = int.from_bytes(rec[0:2], "little")
        if ch == ord(want):
            x = int.from_bytes(rec[4:6], "little") + int.from_bytes(rec[6:8], "little")
            y = int.from_bytes(rec[8:10], "little")
            w = int.from_bytes(rec[10:12], "little")
            h = int.from_bytes(rec[12:14], "little")
            rect = (x, y, w, h)
            break
    print(f"=== {bin_name}  group={name}  blocks={len(blocks)}  glyph '{want}' -> {rect}")
    if rect is None:
        return

    boff, bsize = blocks[0]
    geom = resolve_geometry(raw, boff, bsize)
    print(f"    geometry: {geom}")
    hdr, bpp, aw, ah = geom
    code = raw[boff + 5]
    print(f"    format code = {code:#x}   bpp = {bpp}   atlas = {aw}x{ah}")
    pix = boff + hdr
    x, y, w, h = rect
    print(f"    glyph pixel rect: x={x} y={y} w={w} h={h}")

    counter: Counter[bytes] = Counter()
    for gy in range(y, y + h):
        for gx in range(x, x + w):
            o = pix + (gy * aw + gx) * bpp
            counter[raw[o : o + bpp]] += 1
    print(f"    distinct pixel values in glyph: {len(counter)}")
    for val, cnt in counter.most_common(10):
        u16 = int.from_bytes(val, "little")
        be = int.from_bytes(val, "big")
        print(f"      {val.hex(' ')}  count={cnt:3d}  u16LE={u16:#06x}  u16BE={be:#06x}")

    # and a sample of the surrounding background row
    print("    background sample (row just below the glyph):")
    bgy = min(y + h + 2, ah - 1)
    for gx in range(x, x + min(w, 8)):
        o = pix + (bgy * aw + gx) * bpp
        print(f"      ({gx},{bgy}) {raw[o:o+bpp].hex(' ')}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    inspect("fntm0.group.bin", "fntm0.dat", "A")
