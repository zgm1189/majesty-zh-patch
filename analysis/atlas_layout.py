#!/usr/bin/env python3
"""画出字体纹理的槽位布局，标出哪些格子能借给汉字。"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from export_groupbin import (  # noqa: E402
    parse_container, resolve_geometry, decode_pixels, write_png,
)

RESPACK = Path(r"D:\project\逆向\北方的扩张\extracted\_res\assets\huge\respack")
OUTDIR = Path(r"D:\project\逆向\北方的扩张\build")

# (文件名, 标签, 框颜色, 字符码判定)
DECKS = [
    ("fntM0.dat", "ASCII-保留", (150, 150, 150, 255), lambda c: 0x20 <= c <= 0x7E),
    ("fntM1.dat", "Latin1-可借", (0, 110, 255, 255), lambda c: 0xA0 <= c <= 0x2FF),
    ("fntM2.dat", "Cyrillic-可借", (0, 200, 60, 255), lambda c: 0x400 <= c <= 0x4FF),
]


def load_deck(fn: str):
    d = (RESPACK / fn).read_bytes()
    best = None
    for off in (0, 2):
        n = (len(d) - off) // 14
        if n <= 0:
            continue
        codes = [int.from_bytes(d[off + i * 14 : off + i * 14 + 2], "little") for i in range(n)]
        uq = len(set(codes))
        if best is None or uq > best[0]:
            best = (uq, off, n)
    uq, off, n = best
    recs = []
    for i in range(n):
        o = off + i * 14
        recs.append((
            int.from_bytes(d[o : o + 2], "little"),
            int.from_bytes(d[o + 4 : o + 6], "little") + int.from_bytes(d[o + 6 : o + 8], "little"),
            int.from_bytes(d[o + 8 : o + 10], "little"),
            int.from_bytes(d[o + 10 : o + 12], "little"),
            int.from_bytes(d[o + 12 : o + 14], "little"),
        ))
    return off, n, uq, recs


def draw_rect(buf, aw, ah, x, y, w, h, color):
    def px(a, b):
        if 0 <= a < aw and 0 <= b < ah:
            o = (b * aw + a) * 4
            buf[o : o + 4] = bytes(color)

    for i in range(w):
        px(x + i, y)
        px(x + i, y + h - 1)
    for j in range(h):
        px(x, y + j)
        px(x + w - 1, y + j)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    OUTDIR.mkdir(parents=True, exist_ok=True)

    for fam, atlas_name in (("M", "fntm0.group.bin"), ("W", "fntw0.group.bin"), ("A", "fnta0.group.bin")):
        raw = (RESPACK / atlas_name).read_bytes()
        grp, blocks = parse_container(raw)
        boff, bsize = blocks[0]
        hdr, bpp, aw, ah = resolve_geometry(raw, boff, bsize)
        print(f"=== {atlas_name}  {grp}  {aw}x{ah} bpp={bpp} ===")

        base = bytearray(decode_pixels(raw[boff + hdr : boff + bsize], bpp == 2, "2dimage", aw, ah))
        marked = bytearray(aw * ah)
        lines = []

        for fn, label, color, ok in DECKS:
            off, n, uq, recs = load_deck(fn)
            inside = [r for r in recs if ok(r[0]) and r[2] + 12 <= ah and r[1] + r[3] <= aw]
            print(f"  {fn}: 头偏移={off} 记录={n} 唯一码={uq} → 落在本纹理且匹配: {len(inside)}")
            for c, x, y, w, h in inside:
                hh = h if 1 <= h <= 20 else 11
                draw_rect(base, aw, ah, x, y, w, hh, color)
                lines.append(f"{fam}\t{fn}\t{label}\tU+{c:04X}\t{chr(c)}\t({x},{y})\t{w}x{hh}")
                for j in range(max(1, hh)):
                    for i in range(max(1, w)):
                        if 0 <= y + j < ah and 0 <= x + i < aw:
                            marked[(y + j) * aw + (x + i)] = 1

        out_png = OUTDIR / f"atlas_{fam}_layout.png"
        write_png(out_png, aw, ah, base)
        used = sum(marked)
        pct = used * 100 // (aw * ah)
        print(f"  → {out_png.name}   已占格子像素 {used}/{aw*ah} = {pct}%   空白 {100-pct}%")
        (OUTDIR / f"atlas_{fam}_slots.txt").write_text("\n".join(lines), encoding="utf-8")
        print()


if __name__ == "__main__":
    main()
