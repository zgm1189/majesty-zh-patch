#!/usr/bin/env python3
"""Test whether the stubborn fnt* blocks are actually 16-bit formats."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from export_groupbin import decode_pixels, parse_container, write_png  # noqa: E402

ASSETS = Path(r"D:\project\逆向\北方的扩张\extracted\_res\assets\huge\respack")
OUT = Path(r"D:\project\逆向\北方的扩张\analysis\png")
CASES = [
    ("fntCrystalBig0.group.bin", 0),
    ("fntCrystalSmall0.group.bin", 0),
    ("fntFBSmall0.group.bin", 0),
    ("fntC0.group.bin", 0),
    ("fntW0.group.bin", 0),
]


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    for name, idx in CASES:
        data = (ASSETS / name).read_bytes()
        _, blocks = parse_container(data)
        boff, bsize = blocks[idx]
        raw = data[boff + 28 : boff + bsize]
        print(f"=== {name}[{idx}] body={bsize} payload={len(raw)}")
        cells = []
        for fmt, bpp, label in (
            ("2dimage", 4, "4B RGBA"),
            ("2dimage_5551", 2, "2B 5551"),
            ("2dimage_4444", 2, "2B 4444"),
        ):
            count = len(raw) // bpp
            side = int(round(count**0.5))
            if side * side != count:
                print(f"  {label}: {count} px not square -> skip")
                continue
            rgba = decode_pixels(raw, fmt, side, side)
            cells.append((label, side, rgba))
            print(f"  {label}: {side}x{side}")
        if not cells:
            continue
        gap = 6
        W = sum(c[1] for c in cells) + gap * (len(cells) + 1)
        H = max(c[1] for c in cells) + 2 * gap
        canvas = bytearray(W * H * 4)
        for i in range(W * H):
            canvas[i * 4 : i * 4 + 4] = bytes((25, 25, 25, 255))
        x = gap
        for label, side, rgba in cells:
            for y in range(side):
                dst = ((gap + y) * W + x) * 4
                canvas[dst : dst + side * 4] = rgba[y * side * 4 : (y + 1) * side * 4]
            x += side + gap
        out = OUT / f"_fmt_{name.replace('.group.bin','')}.png"
        write_png(out, W, H, canvas)
        print(f"  -> {out.name} ({W}x{H})  order: {[c[0] for c in cells]}")


if __name__ == "__main__":
    main()
