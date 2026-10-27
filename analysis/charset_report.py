#!/usr/bin/env python3
"""只读分析：语言字符集 vs 字体槽位，找出可借给汉字的格子。"""

from __future__ import annotations

import re
import sys
from pathlib import Path

RESPACK = Path(r"D:\project\逆向\北方的扩张\extracted\_res\assets\huge\respack")
SRC = Path(r"D:\project\逆向\北方的扩张\extracted\assets\translate.dat")
LANGS = ["en", "de", "fr", "it", "es", "ru", "pl", "pt"]
SUFFIX_RE = re.compile(r"^(.*)_([a-z]{2})$")


def parse(d: bytes) -> list[str]:
    recs, i = [], 0
    while i + 2 <= len(d):
        n = int.from_bytes(d[i : i + 2], "big")
        i += 2
        if i + n > len(d):
            break
        recs.append(d[i : i + n].decode("utf-8", "replace"))
        i += n
    return recs


def load_deck(name: str):
    p = RESPACK / name
    if not p.exists():
        return None
    d = p.read_bytes()
    best = None
    for off in (0, 2, 4):
        n = (len(d) - off) // 14
        if n <= 0:
            continue
        codes = [int.from_bytes(d[off + i * 14 : off + i * 14 + 2], "little") for i in range(n)]
        ok = sum(1 for c in codes if 0x20 <= c <= 0x7E or 0xA0 <= c <= 0x5FF)
        if best is None or ok > best[0]:
            best = (ok, off, codes)
    ok, off, codes = best
    return {"off": off, "n": len(codes), "codes": codes, "uniq": sorted(set(codes))}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    # ---- 语言字符集 ----
    recs = parse(SRC.read_bytes())
    chars: dict[str, set[str]] = {l: set() for l in LANGS}
    for r in recs:
        if ": " not in r:
            continue
        k, _, v = r.partition(": ")
        m = SUFFIX_RE.match(k)
        if m and m.group(2) in chars:
            chars[m.group(2)] |= set(v)

    print("=" * 78)
    print("A) 每种语言的字符集")
    print("=" * 78)
    for l in LANGS:
        na = sorted(c for c in chars[l] if ord(c) >= 128)
        kind = "纯 ASCII" if not na else ("西里尔" if any(0x400 <= ord(c) <= 0x4FF for c in na) else "西欧")
        print(f"  _{l}  ASCII {sum(1 for c in chars[l] if ord(c)<128):>3} 个 | "
              f"非 ASCII {len(na):>2} 个 [{kind}]  {''.join(na)}")

    en_nonascii = {c for c in chars["en"] if ord(c) >= 128}

    # ---- 字体槽位 ----
    print()
    print("=" * 78)
    print("B) 字体里有哪些字符槽位")
    print("=" * 78)
    decks = {}
    for key, fn in (("fntM0", "fntM0.dat"), ("fntM1", "fntM1.dat"), ("fntM2", "fntM2.dat"),
                    ("fntW1", "fntW1.dat"), ("fntA1", "fntA1.dat")):
        dk = load_deck(fn)
        if dk:
            decks[key] = dk
            print(f"  {key}: 头偏移={dk['off']}  记录={dk['n']}  唯一字符码={len(dk['uniq'])}")

    def codes_of(keys):
        out = set()
        for k in keys:
            if k in decks:
                out |= set(decks[k]["uniq"])
        return out

    ascii_slots = {c for c in codes_of(["fntM0"]) if 0x20 <= c <= 0x7E}
    latin_slots = {c for c in codes_of(["fntM1", "fntW1", "fntA1"]) if 0xA0 <= c <= 0x24F}
    cyr_slots = {c for c in codes_of(["fntM2"]) if 0x400 <= c <= 0x4FF}

    print()
    print(f"  ASCII 槽 (fntM0)      : {len(ascii_slots)} 个  "
          f"{''.join(chr(c) for c in sorted(ascii_slots))}")
    print(f"  西欧 槽 (fntM1)       : {len(latin_slots)} 个  "
          f"{''.join(chr(c) for c in sorted(latin_slots))}")
    print(f"  西里尔槽 (fntM2)      : {len(cyr_slots)} 个  "
          f"{''.join(chr(c) for c in sorted(cyr_slots))}")

    # ---- 结论 ----
    print()
    print("=" * 78)
    print("C) 结论：哪些格子能借给汉字（游戏语言=英语界面）")
    print("=" * 78)
    latin_used = set()
    for l in ("de", "fr", "it", "es", "pl", "pt"):
        latin_used |= {c for c in chars[l] if 0x80 <= ord(c) < 0x400}
    cyr_used = {c for c in chars["ru"] if 0x400 <= ord(c) <= 0x4FF}

    print(f"  英语界面实际用到的非 ASCII  : {''.join(sorted(en_nonascii)) or '（无）'} ({len(en_nonascii)} 个)")
    print()
    print(f"  ◆ ASCII 格子 {len(ascii_slots)} 个  → 英语在用 → 【不能借】")
    print(f"  ◆ 西欧格子  {len(latin_slots)} 个  → 英语界面用不到 → 【可借】")
    print(f"  ◆ 西里尔格子 {len(cyr_slots)} 个  → 英语界面用不到 → 【可借】")
    print()
    borrow = len(latin_slots) + len(cyr_slots)
    print(f"  ★ 可借格子合计: {latin_slots and len(latin_slots)} + {len(cyr_slots)} = {borrow} 个汉字位")
    print(f"  ★ 英文字母一个都不动 → 英文档名/剧情/任务 全部正常显示，不再乱码")
    print()
    print(f"  代价：游戏语言菜单里这些词会受影响（因为格子被借走）：")
    print(f"    Deutsch/Polski/Français/Русский 等语言名，以及切换到该语言后的文本")

    miss = sorted(latin_used - {chr(c) for c in latin_slots})
    print()
    print(f"  备注：6 种西欧语言用到 {len(latin_used)} 个西欧字符，")
    print(f"        其中字体槽位里没有的: {''.join(miss) if miss else '（无，全部有槽位）'}")


if __name__ == "__main__":
    main()
