#!/usr/bin/env python3
"""Decide bytes-per-pixel for ambiguous blocks via alpha-channel structure.

A 16-bit 5551/4444 texture decoded as 4-byte RGBA scatters the alpha plane into
unrelated bytes, so the number of distinct alpha values explodes. The correct
interpretation stays low-cardinality (2 values for 5551, <=16 for 4444).
"""

from __future__ import annotations

import sys
from pathlib import Path

ASSETS = Path(r"D:\project\逆向\北方的扩张\extracted\_res\assets\huge\respack")


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


def alpha_cardinality_2b(raw: bytes) -> tuple[int, int]:
    """(distinct alpha values assuming 5551, assuming 4444)."""
    a5551 = set()
    a4444 = set()
    for i in range(len(raw) // 2):
        v = (raw[i * 2] << 8) | raw[i * 2 + 1]
        a5551.add((v >> 15) & 1)
        a4444.add((v >> 12) & 0xF)
    return len(a5551), len(a4444)


def alpha_cardinality_4b(raw: bytes) -> int:
    return len(set(raw[i * 4 + 3] for i in range(len(raw) // 4)))


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(f"{'group':28s} {'blk':>3s} {'fmt':14s} {'payload':>8s} {'hdr[5]':>7s}  {'a(5551)':>7s} {'a(4444)':>7s} {'a(8888)':>7s}")
    for bin_path in sorted(ASSETS.glob("*.group.bin")):
        d, blocks = blocks_of(bin_path)
        txt = bin_path.with_name(bin_path.name.replace(".group.bin", ".group")).read_text(
            encoding="utf-8", errors="replace"
        )
        import re

        cur = "2dimage"
        res = []
        for line in txt.splitlines():
            m = re.match(r'\s*useTemplate\s+"image"\s+"([^"]+)"', line)
            if m:
                cur = m.group(1)
                continue
            m = re.match(r'\s*"([^"]+)"\s*\{', line)
            if m:
                res.append(cur)
        for i, (boff, bsize) in enumerate(blocks):
            fmt = res[i] if i < len(res) else "?"
            payload = bsize - 28
            if payload <= 0 or payload % 4 or payload % 2:
                print(f"{bin_path.name:28s} {i:3d} {fmt:14s} {payload:8d}  (odd size)")
                continue
            raw = d[boff + 28 : boff + bsize]
            c5551, c4444 = alpha_cardinality_2b(raw)
            c8888 = alpha_cardinality_4b(raw)
            d5 = d[boff + 5]
            px2 = payload // 2
            px4 = payload // 4
            sq2 = int(round(px2**0.5)) ** 2 == px2
            sq4 = int(round(px4**0.5)) ** 2 == px4
            flag = ""
            if not sq4 and not sq2:
                flag = "  <-- NON-SQUARE BOTH"
            print(
                f"{bin_path.name:28s} {i:3d} {fmt:14s} {payload:8d} 0x{d5:02x}  {c5551:7d} {c4444:7d} {c8888:7d}{flag}"
            )


if __name__ == "__main__":
    main()
