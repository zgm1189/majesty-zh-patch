#!/usr/bin/env python3
"""在截图里找英雄头顶的绿色血条，输出簇中心（设备坐标）。

用法: python findhero.py build/_cur.png
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    im = Image.open(sys.argv[1] if len(sys.argv) > 1 else "build/_cur.png").convert("RGB")
    W, H = im.size
    px = im.load()
    pts = []
    for y in range(0, H, 2):
        for x in range(0, W, 2):
            r, g, b = px[x, y]
            if g > 150 and r < 120 and b < 120 and g - r > 80 and g - b > 80:
                pts.append((x, y))
    # 简单聚类
    clusters = []
    for x, y in pts:
        for c in clusters:
            if abs(c["x"] / c["n"] - x) < 60 and abs(c["y"] / c["n"] - y) < 40:
                c["x"] += x
                c["y"] += y
                c["n"] += 1
                break
        else:
            clusters.append({"x": x, "y": y, "n": 1})
    clusters = [c for c in clusters if c["n"] >= 8]
    clusters.sort(key=lambda c: -c["n"])
    print(f"图像 {W}x{H}，候选 {len(clusters)} 个")
    for c in clusters[:12]:
        cx, cy = c["x"] // c["n"], c["y"] // c["n"]
        # 血条在头顶，英雄身体在其下方约 60px
        print(f"  血条 ({cx},{cy}) 像素数 {c['n']}  -> 点 ( {cx} , {cy + 70} )")


if __name__ == "__main__":
    main()
