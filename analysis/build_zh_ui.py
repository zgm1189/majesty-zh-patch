#!/usr/bin/env python3
"""Chinese UI localisation pipeline (route A: 167 repurposed glyph slots).

Steps
  1. translate the visible UI strings,
  2. rank the Chinese characters used and map them onto the available glyph
     slots (fntM0 ASCII + fntM1 Latin-1),
  3. render each character with Windows GDI and paint it into its slot,
  4. rewrite translate.dat so the Chinese text is stored as slot characters.

Outputs land in build/zh_ui/ and are pushed to the device by a separate step.
"""

from __future__ import annotations

import subprocess
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from export_groupbin import parse_container, resolve_geometry  # noqa: E402

ROOT = Path(r"D:\project\逆向\北方的扩张")
SRC = ROOT / "extracted" / "_res" / "assets" / "huge" / "respack"
TRANS = ROOT / "extracted" / "assets" / "translate.dat"
OUT = ROOT / "build" / "zh_ui"

# ---------------------------------------------------------------- translations
ZH: dict[str, str] = {
    "kCancel": "取消",
    "kdAbout": "关于",
    "kdAchivements": "成就",
    "kdBack": "返回",
    "kdCampaign": "战役",
    "kdChangeLog": "本版新增一个付费关卡。",
    "kdChangeLogHead": "注意！",
    "kdContinue": "继续",
    "kdCreateProfile": "创建",
    "kdEndMission": "结束",
    "kdError": "错误！",
    "kdErrorProfileEql": "档案 {0} 已存在！",
    "kdExit": "退出",
    "kdExitMissionQ": "结束任务？",
    "kdExitQ": "确定退出游戏？",
    "kdExitToMainMenuQ": "退出到主菜单？",
    "kdHelp": "指南",
    "kdHelpBuildingCh": "建筑",
    "kdHelpHeroCh": "英雄",
    "kdHelpMagicCh": "法术",
    "kdHelpMonsterCh": "怪物",
    "kdHelpOtherCh": "基础",
    "kdInfo": "帮助",
    "kdLanguage": "语言",
    "kdLoad": "载入",
    "kdLoadQ": "确定载入游戏？",
    "kdMainMenu": "主菜单",
    "kdMusic": "音乐",
    "kdNewGame": "删除进度",
    "kdNewGameQ": "确定删除进度？",
    "kdOff": "关",
    "kdOn": "开",
    "kdOptions": "选项",
    "kdPlay": "开始游戏",
    "kdProfile": "档案",
    "kdProfileDeleteQ": "确定删除档案 {0}？",
    "kdRestartLevelQ": "重新开始任务？",
    "kdSave": "保存",
    "kdSaveQ": "确定保存？旧存档将丢失。",
    "kdScores": "分数",
    "kdSkirmish": "遭遇战",
    "kdSound": "音效",
    "kdSoundQ": "启用音效？",
    "kdTask": "目标",
    "kOk": "确定",
    "msgGameAutoSaved": "游戏已自动保存",
    "uiAutoSave": "自动保存",
    "uiChooseSlot": "选择存档位",
    "uiEmptySlot": "空存档位",
    "uiPlayMode": "选择游戏模式",
    "uiRestartLevel": "重新开始关卡",
    "uiWeather": "天气",
}

PS_TEMPLATE = """
Add-Type -AssemblyName System.Drawing
$bmp = New-Object System.Drawing.Bitmap({W}, {H})
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.Clear([System.Drawing.Color]::Black)
$g.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::SingleBitPerPixelGridFit
$font = New-Object System.Drawing.Font('SimSun', {SIZE}, [System.Drawing.FontStyle]::Regular, [System.Drawing.GraphicsUnit]::Pixel)
$g.DrawString([char]{CODE}, $font, [System.Drawing.Brushes]::White, -1, -2)
$g.Dispose()
for ($y = 0; $y -lt {H}; $y++) {{
  $line = ''
  for ($x = 0; $x -lt {W}; $x++) {{ $line += $(if ($bmp.GetPixel($x, $y).R -gt 100) {{ '#' }} else {{ '.' }}) }}
  Write-Output $line
}}
$bmp.Dispose()
"""


def render(code: int, w: int, h: int) -> list[str]:
    size = max(6, min(w, h) + 1)
    script = PS_TEMPLATE.format(W=w, H=h, SIZE=size, CODE=code)
    r = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    lines = [ln.strip() for ln in r.stdout.splitlines() if ln.strip() and set(ln.strip()) <= {"#", "."}]
    return lines[-h:] if len(lines) >= h else lines


def read_dat(path: Path) -> list[tuple[int, int, int, int, int, int, int]]:
    b = path.read_bytes()
    n = (len(b) - 2) // 14
    out = []
    for i in range(n):
        o = 2 + i * 14
        rec = b[o : o + 14]
        ch = int.from_bytes(rec[0:2], "little")
        metric = int.from_bytes(rec[2:4], "little")
        x = int.from_bytes(rec[4:6], "little") + int.from_bytes(rec[6:8], "little")
        y = int.from_bytes(rec[8:10], "little")
        w = int.from_bytes(rec[10:12], "little")
        h = int.from_bytes(rec[12:14], "little")
        # The last few records of these .dat files mis-frame; skip anything that
        # is not a plausible small glyph rectangle.
        if not (1 <= w <= 64 and 1 <= h <= 64 and x + w <= 4096 and y + h <= 4096):
            continue
        out.append((ch, metric, x, y, w, h, o))
    return out


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    (OUT / "huge").mkdir(parents=True, exist_ok=True)
    (OUT / "assets").mkdir(parents=True, exist_ok=True)

    # ---- 1) character inventory from the translations ----
    freq: Counter[str] = Counter()
    for text in ZH.values():
        for ch in text:
            if "\u4e00" <= ch <= "\u9fff":
                freq[ch] += 1
    print(f"distinct Chinese chars needed: {len(freq)}")

    # ---- 2) build the slot pool (slot *characters*, shared across families) ----
    # Digits and common punctuation must keep their real glyphs: the game shows
    # numbers everywhere (gold, "1/30", version strings). Only borrow the rest.
    KEEP_ASCII = {ord(c) for c in "0123456789.,:/-%+()'!?#*"}
    slot_chars: list[int] = []
    for rec in read_dat(SRC / "fntm0.dat"):
        ch = rec[0]
        if 0x21 <= ch <= 0x7E and ch not in KEEP_ASCII:
            slot_chars.append(ch)
    for rec in read_dat(SRC / "fntm1.dat"):
        ch = rec[0]
        if 0xA0 <= ch <= 0xFF:
            slot_chars.append(ch)
    print(f"available slot characters: {len(slot_chars)} "
          f"(kept ASCII: {''.join(chr(c) for c in sorted(KEEP_ASCII))})")

    if len(freq) > len(slot_chars):
        print(f"WARNING: need {len(freq)} slots but only {len(slot_chars)} available")

    hanzi_order = [c for c, _ in freq.most_common()]
    hanzi_to_char = {hz: slot_chars[i] for i, hz in enumerate(hanzi_order) if i < len(slot_chars)}
    print(f"mapped {len(hanzi_to_char)} characters onto slot characters")

    # ---- 3) paint the glyphs into every font family the UI may use ----
    for fam in ("m", "w", "a"):
        atlas_path = SRC / f"fnt{fam}0.group.bin"
        if not atlas_path.exists():
            continue
        rawa = atlas_path.read_bytes()
        grp, blocks = parse_container(rawa)
        boff, bsize = blocks[0]
        hdr, bpp, aw, ah = resolve_geometry(rawa, boff, bsize)
        atlas = bytearray(rawa)

        rects: dict[int, tuple[int, int, int, int]] = {}
        for suffix in ("0", "1", "2"):
            p = SRC / f"fnt{fam}{suffix}.dat"
            if p.exists():
                for rec in read_dat(p):
                    ch, _metric, x, y, w, h, _o = rec
                    rects.setdefault(ch, (x, y, w, h))

        painted = skipped = 0
        for hz, slot in hanzi_to_char.items():
            rect = rects.get(slot)
            if rect is None:
                skipped += 1
                continue
            x, y, w, h = rect
            dots = render(ord(hz), w, h)
            pix = boff + hdr
            for gy in range(h):
                row = dots[gy] if gy < len(dots) else "." * w
                for gx in range(w):
                    on = gx < len(row) and row[gx] == "#"
                    o = pix + ((y + gy) * aw + (x + gx)) * 4
                    if o + 4 > len(atlas):
                        continue
                    atlas[o : o + 4] = bytes((255, 255, 255, 255)) if on else bytes((0, 0, 0, 0))
            painted += 1
        print(f"  family {fam}: atlas {aw}x{ah} bpp={bpp} painted={painted} skipped={skipped}")
        assert len(atlas) == len(rawa), f"{fam} atlas size changed!"
        (OUT / "huge" / f"fnt{fam}0.group.bin").write_bytes(bytes(atlas))
        if (SRC / f"fnt{fam}0.group").exists():
            (OUT / "huge" / f"fnt{fam}0.group").write_bytes((SRC / f"fnt{fam}0.group").read_bytes())
        for suffix in ("0", "1", "2"):
            p = SRC / f"fnt{fam}{suffix}.dat"
            if p.exists():
                (OUT / "huge" / f"fnt{fam}{suffix}.dat").write_bytes(p.read_bytes())

    # ---- 4) rewrite translate.dat ----
    data = TRANS.read_bytes()
    records: list[str] = []
    i = 0
    while i < len(data):
        ln = int.from_bytes(data[i : i + 2], "big")
        i += 2
        records.append(data[i : i + ln].decode("utf-8"))
        i += ln

    def to_slots(text: str) -> str:
        out = []
        for ch in text:
            if "\u4e00" <= ch <= "\u9fff":
                slot = hanzi_to_char.get(ch)
                out.append(chr(slot) if slot else "?")
            else:
                out.append(ch)
        return "".join(out)

    replaced = 0
    new_records = []
    for rec in records:
        if ": " in rec:
            key, value = rec.split(": ", 1)
            base = key.rsplit("_", 1)[0] if key.rsplit("_", 1)[-1].isalpha() else key
            if base in ZH:
                new_records.append(f"{key}: {to_slots(ZH[base])}")
                replaced += 1
                continue
        new_records.append(rec)
    print(f"translated {replaced} records")

    buf = bytearray()
    for rec in new_records:
        raw = rec.encode("utf-8")
        buf += len(raw).to_bytes(2, "big") + raw
    (OUT / "assets" / "translate.dat").write_bytes(bytes(buf))
    print(f"wrote {OUT/'assets'/'translate.dat'} ({len(buf)} bytes)")

    # save the mapping for reference
    lines = [f"{hz}\t{chr(slot)!r}\t{slot:#06x}" for hz, slot in hanzi_to_char.items()]
    (OUT / "mapping.tsv").write_text("\n".join(lines), encoding="utf-8")
    print(f"mapping saved to {OUT/'mapping.tsv'}")


if __name__ == "__main__":
    main()
