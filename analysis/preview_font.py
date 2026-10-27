#!/usr/bin/env python3
"""离线预览：用改好的字体数据按游戏的方式排版，检查字形/对齐/覆盖。

用法: python preview_font.py [pack]
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
from gxfont import Atlas, read_deck  # noqa: E402

ROOT = Path(r"D:\project\逆向\北方的扩张")


class Font:
    def __init__(self, pack_dir: Path, fam: str):
        self.atlas = None
        self.glyphs: dict[int, object] = {}
        self.name = fam
        for p in sorted(pack_dir.iterdir()):
            low = p.name.lower()
            if not low.startswith(f"fnt{fam.lower()}"):
                continue
            if low.endswith(".group.bin"):
                self.atlas = Atlas(p)
            elif low.endswith((".dat", ".dti")):
                page, gls, _tail = read_deck(p)
                for g in gls:
                    if not g.w or not g.h:
                        continue
                    cp = ((page << 8) | g.ch) if page else g.ch
                    self.glyphs.setdefault(cp, g)
        self.line_h = max((g.h for g in self.glyphs.values()), default=16) + 2

    def width(self, text: str) -> int:
        return sum(self.glyphs[ord(c)].advance if ord(c) in self.glyphs else 4 for c in text)

    def draw_gray(self, img: Image.Image, x: int, y: int, text: str, level: int = 255) -> int:
        """Draw into an 'L' image using the raw glyph alpha (for A/B checks)."""
        pen = x
        baseline = y + self.line_h - 3
        for ch in text:
            g = self.glyphs.get(ord(ch))
            if g is None:
                pen += 4
                continue
            top = baseline + 1 - g.h
            for gy in range(g.h):
                for gx in range(g.w):
                    a = self.atlas.get(g.x + gx, g.y + gy)[3]
                    if a:
                        px, py = pen + gx, top + gy
                        if 0 <= px < img.width and 0 <= py < img.height:
                            img.putpixel((px, py), a * level // 255)
            pen += g.advance
        return pen

    def draw(self, img: Image.Image, x: int, y: int, text: str, color=(238, 232, 214)) -> int:
        pen = x
        baseline = y + self.line_h - 3
        for ch in text:
            g = self.glyphs.get(ord(ch))
            if g is None:
                pen += 4
                continue
            top = baseline - (g.h - 1)
            for gy in range(g.h):
                for gx in range(g.w):
                    a = self.atlas.get(g.x + gx, g.y + gy)[3]
                    if not a:
                        continue
                    px, py = pen + gx, top + gy
                    if 0 <= px < img.width and 0 <= py < img.height:
                        r, gg, b = color
                        bg = img.getpixel((px, py))
                        img.putpixel((px, py), (bg[0] + (r - bg[0]) * a // 255,
                                                bg[1] + (gg - bg[1]) * a // 255,
                                                bg[2] + (b - bg[2]) * a // 255))
            pen += g.advance
        return pen


def wrap(font: Font, text: str, max_w: int) -> list[str]:
    lines, cur = [], ""
    for part in text.replace("^", "\n").split("\n"):
        cur = ""
        for ch in part:
            if font.width(cur + ch) > max_w:
                lines.append(cur)
                cur = ch
            else:
                cur += ch
        lines.append(cur)
    return lines


def render(pack: str = "huge") -> Path:
    from zh_strings import ZH

    base = ROOT / "build" / "zh_font" / pack
    fonts = {fam: Font(base, fam) for fam in ("M", "A", "W")}
    print({fam: (f.atlas.w, f.atlas.h, len(f.glyphs)) for fam, f in fonts.items()})

    charset = {c for v in ZH.values() for c in v if not c.isascii() and c not in "\n^"}
    miss = sorted(c for c in charset if ord(c) not in fonts["M"].glyphs)
    print(f"charset {len(charset)}  missing {len(miss)}  {''.join(miss[:60])}")

    W, H = 960, 900
    img = Image.new("RGB", (W, H), (24, 20, 16))
    y = 14
    title = fonts["W"]
    y = title.draw(img, 20, y, "王权：北方的扩张") + 16
    y += 8

    m = fonts["M"]
    for text in ["开始游戏", "载入", "选项", "成就", "指南", "退出"]:
        m.draw(img, 20, y, text)
        y += m.line_h + 6
    y += 8

    a = fonts["A"]
    a.draw(img, 20, y, "第 3 关 · 价值连城的饼干")
    y += a.line_h + 10

    # 垂直对齐自检：矮字（一二三）必须居中，不能贴基线
    m.draw(img, 20, y, "一二三十人口国田目日｜永字八法")
    y += m.line_h + 4
    m.draw(img, 20, y, "，。！？：；、（）「」《》……——·")
    y += m.line_h + 10

    blocks = [
        ("M", ZH.get("kdSaveQ", "")),
        ("M", ZH.get("sTaskL14", "")),
        ("M", ZH.get("stHintText8", "")[:90] + "……"),
        ("M", ZH.get("hlpCastle", "")[:120] + "……"),
        ("M", "金币 1250 / 30 天 · 英雄 4/6 · 建筑 8/12"),
        ("M", ZH.get("acText55", "")),
    ]
    for fam, text in blocks:
        f = fonts[fam]
        for line in wrap(f, text, W - 40):
            f.draw(img, 20, y, line, (222, 216, 200))
            y += f.line_h
        y += 14

    img = img.resize((W * 2, H * 2), Image.LANCZOS)
    out = ROOT / "build" / f"preview_zh_{pack}.png"
    img.save(out)
    print(f"-> {out}")
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    render(sys.argv[1] if len(sys.argv) > 1 else "huge")
