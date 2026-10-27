#!/usr/bin/env python3
"""验证：把「城」「堡」画进 fntM1 的 à / â 格子，hCastle_de 写成 "àâ"。

fntM1 的字符码 = Unicode（已由 .dat 证实），所以写 à(U+00E0) 就一定会
取到 (202,21) 那个格子 —— 映射是确定的。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from export_groupbin import parse_container, resolve_geometry  # noqa: E402
from build_zh_ui import render  # noqa: E402

ROOT = Path(r"D:\project\逆向\北方的扩张")
SRC = ROOT / "extracted" / "_res" / "assets" / "huge" / "respack"
OUT = ROOT / "build" / "castle_test"

CHARS = "城堡"
KEY = "hCastle_de"
# (字符, 纹理坐标, 宽) —— 来自 fntM1.dat: à=(202,21) 8x11, â=(210,21) 8x11
SLOTS = [("à", 202, 21, 8), ("â", 210, 21, 8)]


def paint(fam: str) -> None:
    src = SRC / f"fnt{fam}0.group.bin"
    raw = bytearray(src.read_bytes())
    grp, blocks = parse_container(raw)
    boff, bsize = blocks[0]
    hdr, bpp, aw, ah = resolve_geometry(raw, boff, bsize)
    pix = boff + hdr
    H = 11
    for (ch_slot, x, y, w), han in zip(SLOTS, CHARS):
        lines = render(ord(han), w, H)
        on = 0
        for j in range(H):
            for i in range(w):
                o = pix + ((y + j) * aw + (x + i)) * 4
                if o + 4 > len(raw):
                    continue
                hit = j < len(lines) and i < len(lines[j]) and lines[j][i] == "#"
                raw[o : o + 4] = bytes((255, 255, 255, 255)) if hit else bytes((0, 0, 0, 0))
                on += hit
        print(f"  [{fam}] '{han}' -> slot '{ch_slot}' ({x},{y}) {w}x{H}  笔画={on}")
    assert len(raw) == len(src.read_bytes()), "atlas size changed!"
    (OUT / f"fnt{fam}0.group.bin").write_bytes(bytes(raw))


def patch() -> None:
    d = (ROOT / "build" / "assets" / "translate.dat").read_bytes()
    recs, i = [], 0
    while i < len(d):
        n = int.from_bytes(d[i : i + 2], "big")
        i += 2
        recs.append(d[i : i + n].decode("utf-8"))
        i += n
    out, hit = [], 0
    new_val = "".join(s[0] for s in SLOTS)  # "àâ"
    for r in recs:
        if r.startswith(KEY + ": "):
            print(f"  {r!r}  ->  {KEY}: {new_val!r}")
            r = f"{KEY}: {new_val}"
            hit += 1
        out.append(r)
    buf = bytearray()
    for r in out:
        b = r.encode("utf-8")
        buf += len(b).to_bytes(2, "big") + b
    (OUT / "translate.dat").write_bytes(bytes(buf))
    print(f"  改写 {hit} 条 -> {OUT}/translate.dat ({len(buf)} bytes)")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"目标: {KEY} 显示「{CHARS}」  (文本写成 {'/'.join(s[0] for s in SLOTS)!r})")
    for fam in ("m", "w", "a"):
        paint(fam)
    patch()
    print(f"\n输出: {OUT}")


if __name__ == "__main__":
    main()
