#!/usr/bin/env python3
"""把 fntM1 / fntM2 每个槽位的字形切出来拼成对照图，看清每格到底是什么。"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from export_groupbin import (  # noqa: E402
    parse_container, resolve_geometry, decode_pixels, write_png,
)

RESPACK = Path(r"D:\project\逆向\北方的扩张\extracted\_res\assets\huge\respack")
OUTDIR = Path(r"D:\project\逆向\北方的扩张\build")


def load(fn: str):
    d = (RESPACK / fn).read_bytes()
    off = 2  # 2-byte header
    n = (len(d) - off) // 14
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
    return recs


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raw = (RESPACK / "fntm0.group.bin").read_bytes()
    grp, blocks = parse_container(raw)
    boff, bsize = blocks[0]
    hdr, bpp, aw, ah = resolve_geometry(raw, boff, bsize)
    pix = bytes(decode_pixels(raw[boff + hdr : boff + bsize], bpp == 2, "2dimage", aw, ah))
    print(f"atlas {grp} {aw}x{ah} bpp={bpp}")

    for fn, tag in (("fntM1.dat", "M1_latin"), ("fntM2.dat", "M2_index")):
        recs = load(fn)
        COLS, CELL, Z = 16, 22, 3
        rows = (len(recs) + COLS - 1) // COLS
        ow, oh = COLS * CELL * Z, rows * CELL * Z
        buf = bytearray(b"\x28" * (ow * oh * 4))
        for idx, (c, x, y, w, h) in enumerate(recs):
            cx, cy = (idx % COLS) * CELL * Z, (idx // COLS) * CELL * Z
            hh = h if 1 <= h <= 20 else 11
            for j in range(hh):
                for i in range(w):
                    sx, sy = x + i, y + j
                    if not (0 <= sx < aw and 0 <= sy < ah):
                        continue
                    o = (sy * aw + sx) * 4
                    if pix[o + 3] == 0:
                        continue
                    for dy in range(Z):
                        for dx in range(Z):
                            px, py = cx + i * Z + dx, cy + j * Z + dy
                            if 0 <= px < ow and 0 <= py < oh:
                                po = (py * ow + px) * 4
                                buf[po : po + 4] = bytes((pix[o], pix[o + 1], pix[o + 2], 255))
        out = OUTDIR / f"deck_{tag}.png"
        write_png(out, ow, oh, buf)
        print(f"{fn}: {len(recs)} recs -> {out.name}  ({COLS} 个/行)")

        lines = ["idx\tchar\tcode\tx\ty\tw\th"]
        for idx, (c, x, y, w, h) in enumerate(recs):
            ch = chr(c) if 0x20 <= c <= 0x2FF else "."
            lines.append(f"{idx}\t{ch}\tU+{c:04X}\t{x}\t{y}\t{w}\t{h}")
        (OUTDIR / f"deck_{tag}.txt").write_text("\n".join(lines), encoding="utf-8")

        # 打印前两行的字符，方便快速判断
        print("   ", " ".join(
            (chr(c) if 0x20 <= c <= 0x2FF else f"[{c}]") for c, *_ in recs[:32]))


if __name__ == "__main__":
    main()
