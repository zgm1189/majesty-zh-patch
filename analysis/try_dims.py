#!/usr/bin/env python3
"""Render every plausible dimension candidate for the stubborn non-square blocks."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from export_groupbin import decode_pixels, parse_container, parse_group_text, write_png  # noqa: E402

ASSETS = Path(r"D:\project\逆向\北方的扩张\extracted\_res\assets\huge\respack")
OUT = Path(r"D:\project\逆向\北方的扩张\analysis\png")
BPP = {"2dimage": 4, "2dimage_4444": 2, "2dimage_5551": 2}

CASES = [
    ("anims29.group.bin", 3, "2dimage_4444"),
    ("anims52.group.bin", 3, "2dimage_5551"),
    ("fntCrystalBig0.group.bin", 0, "2dimage"),
    ("fntCrystalSmall0.group.bin", 0, "2dimage"),
    ("fntFBSmall0.group.bin", 0, "2dimage"),
]


def candidates(count: int):
    out = []
    p = 1
    while p <= count:
        if count % p == 0:
            q = count // p
            if q <= 4096 and p <= 4096 and 0.25 <= p / q <= 4:
                out.append((p, q))
        p *= 2
    return out


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    for name, idx, fmt in CASES:
        data = (ASSETS / name).read_bytes()
        _, blocks = parse_container(data)
        boff, bsize = blocks[idx]
        bpp = BPP[fmt]
        raw = data[boff + 28 : boff + bsize]
        count = len(raw) // bpp
        sheet = OUT / f"_dims_{name.replace('.group.bin','')}_b{idx}.png"
        cands = candidates(count)
        gap = 6
        total_w = sum(w for w, _ in cands) + gap * (len(cands) + 1)
        max_h = max(h for _, h in cands)
        W = total_w
        H = max_h + 2 * gap
        canvas = bytearray(W * H * 4)
        for i in range(W * H):
            canvas[i * 4 : i * 4 + 4] = bytes((25, 25, 25, 255))
        x = gap
        for w, h in cands:
            rgba = decode_pixels(raw, fmt, w, h)
            for y in range(h):
                dst = ((gap + y) * W + x) * 4
                canvas[dst : dst + w * 4] = rgba[y * w * 4 : (y + 1) * w * 4]
            print(f"  {name}[{idx}] {fmt} candidate {w}x{h} at x={x}")
            x += w + gap
        write_png(sheet, W, H, canvas)
        print(f"{name}[{idx}] -> {sheet.name}  ({W}x{H})")


if __name__ == "__main__":
    main()
