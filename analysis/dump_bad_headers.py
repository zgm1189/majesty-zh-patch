#!/usr/bin/env python3
"""Locate width/height fields in the 28-byte image header of non-square blocks."""

from __future__ import annotations

import sys
from pathlib import Path

ASSETS = Path(r"D:\project\逆向\北方的扩张\extracted\_res\assets\huge\respack")

BPP = {"2dimage": 4, "2dimage_4444": 2, "2dimage_5551": 2}
TARGETS = [
    ("anims14.group.bin", 4, "2dimage_5551"),
    ("anims19.group.bin", 3, "2dimage_5551"),
    ("anims29.group.bin", 3, "2dimage_4444"),
    ("anims4.group.bin", 1, "2dimage_5551"),
    ("anims41.group.bin", 1, "2dimage"),
    ("anims43.group.bin", 2, "2dimage"),
    ("anims52.group.bin", 3, "2dimage_5551"),
    ("anims54.group.bin", 0, "2dimage"),
    ("fntCrystalBig0.group.bin", 0, "2dimage"),
    ("fntCrystalSmall0.group.bin", 0, "2dimage"),
    ("fntFBSmall0.group.bin", 0, "2dimage"),
    ("fntW0.group.bin", 0, "2dimage"),
]
# Sanity anchors: header bytes for blocks whose size we already know.
ANCHORS = [
    ("anims0.group.bin", 0, "2dimage", 512, 512),
    ("anims0.group.bin", 2, "2dimage_5551", 128, 128),
    ("anims0.group.bin", 4, "2dimage_5551", 64, 64),
    ("anims3.group.bin", 0, "2dimage", 1024, 1024),
]


def u32(d: bytes, o: int) -> int:
    return int.from_bytes(d[o : o + 4], "little")


def blocks_of(path: Path):
    d = path.read_bytes()
    nb = u32(d, 10)
    pos = 14 + nb + 4
    secs = u32(d, pos)
    pos += 4
    counts = []
    for _ in range(secs):
        pos += 4
        counts.append(u32(d, pos))
        pos += 6
    out = []
    for c in counts:
        for _ in range(c):
            size = u32(d, pos)
            out.append((pos + 8, size - 8))
            pos += size
    return d, out


def find_pairs(hdr: bytes, count: int):
    """All (offset, w, h) where a BE u16 at offset divides count and h appears too."""
    out = []
    for o in range(0, 25, 1):
        w = (hdr[o] << 8) | hdr[o + 1]
        if w == 0 or count % w:
            continue
        h = count // w
        if h > 4096 or w > 4096:
            continue
        # look for h as a big-endian u16 elsewhere in the header
        for o2 in range(0, 27):
            if o2 == o:
                continue
            if ((hdr[o2] << 8) | hdr[o2 + 1]) == h:
                out.append((o, o2, w, h))
    return out


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("--- anchors (known dimensions) ---")
    for name, idx, fmt, kw, kh in ANCHORS:
        d, blocks = blocks_of(ASSETS / name)
        boff, bsize = blocks[idx]
        hdr = d[boff : boff + 28]
        print(f"{name} block{idx} {fmt} known={kw}x{kh} body={bsize}")
        print(f"   hdr: {hdr.hex(' ')}")
        hs = hdr.hex(" ")
        # locate kw and kh as BE u16
        for label, val in (("w", kw), ("h", kh)):
            hits = [o for o in range(0, 27) if (hdr[o] << 8 | hdr[o + 1]) == val]
            print(f"   {label}={val} BE-u16 at offsets {hits}")
    print()
    print("--- problem blocks ---")
    for name, idx, fmt in TARGETS:
        d, blocks = blocks_of(ASSETS / name)
        boff, bsize = blocks[idx]
        bpp = BPP[fmt]
        hdr = d[boff : boff + 28]
        px = bsize - 28
        if px % bpp:
            print(f"{name} block{idx} {fmt}: px not divisible, skip")
            continue
        count = px // bpp
        print(f"{name} block{idx} {fmt} body={bsize} px={count}")
        print(f"   hdr: {hdr.hex(' ')}")
        print(f"   candidate (wOff,hOff,w,h): {find_pairs(hdr, count)}")


if __name__ == "__main__":
    main()
