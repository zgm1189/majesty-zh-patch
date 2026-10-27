#!/usr/bin/env python3
"""实验：hCastle_de 改成汉字，看德语界面能否显示。

做法：
  1. 把「城」「堡」画进 fntM2 的前两个西里尔格子（А / Б 的槽位）
  2. hCastle_de 写成 "АБ"（А U+0410, Б U+0411）—— 这两个西里尔字符是
     "指向那两个格子"的钥匙
  3. 输出到 build/probe_de/，由后续步骤打包+推送
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from export_groupbin import parse_container, resolve_geometry  # noqa: E402
from build_zh_ui import render  # noqa: E402

ROOT = Path(r"D:\project\逆向\北方的扩张")
SRC = ROOT / "extracted" / "_res" / "assets" / "huge" / "respack"
OUT = ROOT / "build" / "probe_de"

# 目标：hCastle_de ->「城堡」
CHARS = ["城", "堡"]
KEY = "hCastle_de"
SLOT_CHARS = "\u0410\u0411"  # А Б —— 指向 fntM2 的前两个槽位


def parse_fntM2():
    d = (SRC / "fntM2.dat").read_bytes()
    off = 2
    n = (len(d) - off) // 14
    recs = []
    for i in range(n):
        o = off + i * 14
        recs.append({
            "code": int.from_bytes(d[o : o + 2], "little"),
            "x": int.from_bytes(d[o + 4 : o + 6], "little")
            + int.from_bytes(d[o + 6 : o + 8], "little"),
            "y": int.from_bytes(d[o + 8 : o + 10], "little"),
            "w": int.from_bytes(d[o + 10 : o + 12], "little"),
        })
    return recs


def paint(fam: str, recs) -> None:
    src = SRC / f"fnt{fam}0.group.bin"
    raw = bytearray(src.read_bytes())
    grp, blocks = parse_container(raw)
    boff, bsize = blocks[0]
    hdr, bpp, aw, ah = resolve_geometry(raw, boff, bsize)
    pix = boff + hdr
    H = 11
    for k, ch in enumerate(CHARS):
        r = recs[k]
        x, y, w = r["x"], r["y"], r["w"]
        lines = render(ord(ch), w, H)
        on = 0
        for j in range(H):
            for i in range(w):
                o = pix + ((y + j) * aw + (x + i)) * 4
                if o + 4 > len(raw):
                    continue
                hit = j < len(lines) and i < len(lines[j]) and lines[j][i] == "#"
                raw[o : o + 4] = bytes((255, 255, 255, 255)) if hit else bytes((0, 0, 0, 0))
                on += hit
        print(f"  [{fam}] '{ch}' -> fntM2[{k}] ({x},{y}) {w}x{H}  笔画像素={on}")
    assert len(raw) == len(src.read_bytes()), "atlas size changed!"
    (OUT / f"fnt{fam}0.group.bin").write_bytes(bytes(raw))


def patch_translate() -> None:
    d = (ROOT / "build" / "assets" / "translate.dat").read_bytes()
    recs, i = [], 0
    while i < len(d):
        n = int.from_bytes(d[i : i + 2], "big")
        i += 2
        recs.append(d[i : i + n].decode("utf-8"))
        i += n
    hits = 0
    out = []
    for r in recs:
        if r.startswith(KEY + ": "):
            print(f"  {r!r}  ->  {KEY}: {SLOT_CHARS!r}")
            r = f"{KEY}: {SLOT_CHARS}"
            hits += 1
        out.append(r)
    buf = bytearray()
    for r in out:
        b = r.encode("utf-8")
        buf += len(b).to_bytes(2, "big") + b
    (ROOT / "build" / "probe_de" / "translate.dat").write_bytes(bytes(buf))
    print(f"  patched {hits} record -> build/probe_de/translate.dat ({len(buf)} bytes)")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    OUT.mkdir(parents=True, exist_ok=True)
    recs = parse_fntM2()
    print(f"fntM2: {len(recs)} 个槽位; 前两个 = ({recs[0]['x']},{recs[0]['y']}) w={recs[0]['w']},"
          f" ({recs[1]['x']},{recs[1]['y']}) w={recs[1]['w']}")
    print(f"目标: {KEY} ->「{''.join(CHARS)}」 (文本写成 {SLOT_CHARS!r} = U+0410 U+0411)")
    print()
    for fam in ("m", "w", "a"):
        paint(fam, recs)
    print()
    patch_translate()
    print(f"\n输出目录: {OUT}")


if __name__ == "__main__":
    main()
