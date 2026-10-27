#!/usr/bin/env python3
"""Resolve dimensions of non-square texture blocks by row continuity.

A wrong width pairs unrelated pixels into rows, so the mean absolute difference
between consecutive rows jumps. The correct orientation minimises it.
"""

from __future__ import annotations

import sys
from pathlib import Path

ASSETS = Path(r"D:\project\逆向\北方的扩张\extracted\_res\assets\huge\respack")
BPP = {"2dimage": 4, "2dimage_4444": 2, "2dimage_5551": 2, "2dimage_565": 2}


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


def parse_group_text(path: Path):
    text = path.read_text(encoding="utf-8", errors="replace")
    import re

    current = "2dimage"
    out = []
    for line in text.splitlines():
        m = re.match(r'\s*useTemplate\s+"image"\s+"([^"]+)"', line)
        if m:
            current = m.group(1)
            continue
        m = re.match(r'\s*"([^"]+)"\s*\{', line)
        if m:
            out.append((m.group(1), current))
    return out


def row_score(raw: bytes, w: int, h: int, bpp: int) -> float:
    """Mean per-pixel absolute difference between consecutive rows."""
    rb = w * bpp
    total = 0
    for y in range(h - 1):
        a = raw[y * rb : (y + 1) * rb]
        b = raw[(y + 1) * rb : (y + 2) * rb]
        total += sum(abs(a[i] - b[i]) for i in range(0, rb, bpp))
    return total / max(1, (h - 1) * w)


def col_score(raw: bytes, w: int, h: int, bpp: int) -> float:
    """Same idea along columns, for comparison."""
    total = 0
    for x in range(w - 1):
        col_a = [raw[(y * w + x) * bpp] for y in range(h)]
        col_b = [raw[(y * w + x + 1) * bpp] for y in range(h)]
        total += sum(abs(p - q) for p, q in zip(col_a, col_b))
    return total / max(1, w - 1)


def factor_pairs(count: int):
    out = []
    w = 1
    while w * w <= count:
        if count % w == 0:
            h = count // w
            if w <= 4096 and h <= 4096:
                out.append((w, h))
        w += 1
    return out


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    for bin_path in sorted(ASSETS.glob("*.group.bin")):
        d, blocks = blocks_of(bin_path)
        resources = parse_group_text(bin_path.with_name(bin_path.name.replace(".group.bin", ".group")))
        for i, (boff, bsize) in enumerate(blocks):
            fmt = resources[i][1] if i < len(resources) else "2dimage"
            resname = resources[i][0] if i < len(resources) else f"block{i}"
            bpp = BPP.get(fmt, 4)
            px = bsize - 28
            if px <= 0 or px % bpp:
                print(f"!! {bin_path.name}[{i}] {resname}: body={bsize} bpp={bpp} not divisible")
                continue
            count = px // bpp
            side = int(round(count**0.5))
            if side * side == count:
                continue
            raw = d[boff + 28 : boff + bsize]
            scored = []
            for w, h in factor_pairs(count):
                scored.append((row_score(raw, w, h, bpp), w, h))
            scored.sort()
            top = scored[:3]
            print(f"{bin_path.name}[{i}] {resname} {fmt} px={count}")
            for s, w, h in top:
                print(f"    rowscore={s:10.2f}  {w}x{h}")


if __name__ == "__main__":
    main()
