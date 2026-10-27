#!/usr/bin/env python3
"""验证 fntM2 槽位与字符的对应关系：把全部 66 个槽位涂成不同灰阶，
然后显示 АБ，看游戏把它们渲染成哪个灰阶。"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from export_groupbin import parse_container, resolve_geometry  # noqa: E402

ROOT = Path(r"D:\project\逆向\北方的扩张")
SRC = ROOT / "extracted" / "_res" / "assets" / "huge" / "respack"
OUT = ROOT / "build" / "probe_de"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    d = (SRC / "fntM2.dat").read_bytes()
    off, n = 2, (len((SRC / "fntM2.dat").read_bytes()) - 2) // 14
    recs = []
    for i in range(n):
        o = off + i * 14
        recs.append((
            int.from_bytes(d[o : o + 2], "little"),
            int.from_bytes(d[o + 4 : o + 6], "little") + int.from_bytes(d[o + 6 : o + 8], "little"),
            int.from_bytes(d[o + 8 : o + 10], "little"),
            int.from_bytes(d[o + 10 : o + 12], "little"),
        ))
    print(f"fntM2: {len(recs)} 槽位")

    for fam in ("m", "w", "a"):
        src = SRC / f"fnt{fam}0.group.bin"
        raw = bytearray(src.read_bytes())
        grp, blocks = parse_container(raw)
        boff, bsize = blocks[0]
        hdr, bpp, aw, ah = resolve_geometry(raw, boff, bsize)
        pix = boff + hdr
        for k, (c, x, y, w) in enumerate(recs):
            v = 60 + (k * 8) % 195          # 每个槽位不同灰阶
            for j in range(12):
                for i in range(w):
                    o = pix + ((y + j) * aw + (x + i)) * 4
                    if o + 4 <= len(raw):
                        raw[o : o + 4] = bytes((v, v, v, 255))
        assert len(raw) == len(src.read_bytes())
        (OUT / f"fnt{fam}0.group.bin").write_bytes(bytes(raw))
        print(f"  [{fam}] 已涂 {len(recs)} 个槽位 (灰阶 60 + idx*8 mod 195)")

    print("\n每个槽位的灰阶值:")
    for k in range(len(recs)):
        v = 60 + (k * 8) % 195
        print(f"  idx {k:2d}  灰阶 {v:3d}" + ("  <- А?" if k < 3 else ""))


if __name__ == "__main__":
    main()
