#!/usr/bin/env python3
"""Probe what fntM2 drives: paint a marker glyph into its first slot and see
where it shows up in the game."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from export_groupbin import parse_container, resolve_geometry  # noqa: E402

SRC = Path(r"D:\project\逆向\北方的扩张\extracted\_res\assets\huge\respack")
OUT = Path(r"D:\project\逆向\北方的扩张\build\probe2")


def load_rects(name: str):
    b = (SRC / name).read_bytes()
    n = len(b) // 14
    out = []
    for i in range(n):
        r = b[i * 14 : (i + 1) * 14]
        f = [int.from_bytes(r[j : j + 2], "little") for j in range(0, 14, 2)]
        out.append(f)
    return out


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    OUT.mkdir(parents=True, exist_ok=True)

    rects = load_rects("fntM2.dat")
    print(f"fntM2.dat: {len(rects)} records (7 x u16 each)")
    print("  idx  f0(char?)  f1(idx?)  f2(metric)  f3   f4(xlo)  f5(y)  f6(w)")
    for i, f in enumerate(rects[:12]):
        a, b2, metric, xhi, xlo, y, w = f
        ch = chr(a) if 0x20 < a < 0x500 else "?"
        print(f"  [{i:2d}] 0x{a:04X} {ch:>4s} {b2:6d}   0x{metric:04X}   "
              f"{xhi:3d}  {xlo:5d}  {y:4d}  {w:4d}")

    # Build the patched atlas: mark rec0's slot with a solid block so we can
    # spot it instantly wherever the game draws it.
    atlas_path = SRC / "fntm0.group.bin"
    raw = atlas_path.read_bytes()
    grp, blocks = parse_container(raw)
    boff, bsize = blocks[0]
    hdr, bpp, aw, ah = resolve_geometry(raw, boff, bsize)
    print(f"\natlas {grp}: {aw}x{ah} bpp={bpp} hdr={hdr} off={boff}")

    atlas = bytearray(raw)
    pix = boff + hdr
    for idx in range(0, 3):
        f = rects[idx]
        x = f[3] + f[4]
        y, w = f[5], f[6]
        h = 10
        for gy in range(h):
            for gx in range(w):
                o = pix + ((y + gy) * aw + (x + gx)) * 4
                if o + 4 <= len(atlas):
                    atlas[o : o + 4] = bytes((255, 0, 255, 255))
        print(f"  marked rec[{idx}] at ({x},{y}) {w}x{h}")
    assert len(atlas) == len(raw)
    (OUT / "fntm0.group.bin").write_bytes(bytes(atlas))
    for nm in ("fntm0.group", "fntm0.dat", "fntm1.dat", "fntm2.dat"):
        p = SRC / nm
        if p.exists():
            (OUT / nm).write_bytes(p.read_bytes())
    print(f"\nwrote probe to {OUT}")


if __name__ == "__main__":
    main()
