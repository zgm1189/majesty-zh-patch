#!/usr/bin/env python3
"""列出 translate.dat 的语言表：LANGUAGE 声明、各语言词条数、抽样示例。"""

from __future__ import annotations

import re
import sys
from collections import Counter, OrderedDict
from pathlib import Path

SRC = Path(r"D:\project\逆向\北方的扩张\extracted\assets\translate.dat")

# 语言后缀：key_xx
SUFFIX_RE = re.compile(r"^(.*)_([a-z]{2})$")


def parse(d: bytes) -> list[str]:
    recs, i = [], 0
    while i + 2 <= len(d):
        n = int.from_bytes(d[i : i + 2], "big")
        i += 2
        if i + n > len(d):
            recs.append(f"<截断记录 len={n}>")
            break
        recs.append(d[i : i + n].decode("utf-8", "replace"))
        i += n
    return recs


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    d = SRC.read_bytes()
    recs = parse(d)
    print(f"文件: {SRC}")
    print(f"大小: {len(d)} 字节    记录数: {len(recs)}")
    print()

    # ---- 1) LANGUAGE 声明 ----
    print("=" * 70)
    print("1) LANGUAGE 声明行")
    print("=" * 70)
    langs_declared: list[str] = []
    for r in recs:
        if r.upper().startswith("LANGUAGE"):
            print(f"  {r!r}")
            m = re.search(r":\s*(.+)$", r)
            if m:
                langs_declared = [p.strip() for p in m.group(1).split(",") if p.strip()]
    print(f"\n  解析出 {len(langs_declared)} 种语言: {langs_declared}")
    print()

    # ---- 2) 每条记录的语言后缀分布 ----
    print("=" * 70)
    print("2) 词条 key 的语言后缀分布")
    print("=" * 70)
    suffix_count: Counter[str] = Counter()
    nonsuffix = 0
    for r in recs:
        key = r.split(":", 1)[0] if ":" in r else r
        m = SUFFIX_RE.match(key)
        if m:
            suffix_count[m.group(2)] += 1
        else:
            nonsuffix += 1
    total = sum(suffix_count.values())
    print(f"  {'后缀':<8}{'词条数':>8}   语言")
    name_map = {
        "en": "英语 English", "de": "德语 Deutsch", "fr": "法语 Français",
        "it": "意大利语 Italiano", "es": "西班牙语 Español",
        "ru": "俄语 Русский", "pl": "波兰语 Polski", "pt": "葡萄牙语 Português",
        "zh": "中文 (若有)",
    }
    for sfx, cnt in sorted(suffix_count.items(), key=lambda kv: -kv[1]):
        nm = name_map.get(sfx, "(未知语言)")
        print(f"  _{sfx:<7}{cnt:>8}   {nm}")
    print(f"  {'(无后缀)':<8}{nonsuffix:>8}")
    print(f"  {'合计':<8}{total:>8}")
    print()

    # ---- 3) 是否有中文字段 ----
    print("=" * 70)
    print("3) 是否包含中文/东亚语言字段")
    print("=" * 70)
    for probe in ("zh", "cn", "tw", "hk", "jp", "ja", "ko", "kr"):
        found = [r for r in recs if SUFFIX_RE.match(r.split(":", 1)[0] if ":" in r else r)
                 and (SUFFIX_RE.match(r.split(":", 1)[0]) or [None, ""])[1] == probe]
        if found:
            print(f"  _{probe}: {len(found)} 条  ← 存在!")
    print("  (以上未列出的语言都不存在)")
    print()

    # ---- 4) 抽样：同一 key 的三种语言对比 ----
    print("=" * 70)
    print("4) 抽样对比：同一个 key 在各语言下的文本")
    print("=" * 70)
    base: OrderedDict[str, dict[str, str]] = OrderedDict()
    for r in recs:
        if ":" not in r:
            continue
        key, _, val = r.partition(": ")
        m = SUFFIX_RE.match(key)
        if not m:
            continue
        stem, sfx = m.group(1), m.group(2)
        base.setdefault(stem, {})[sfx] = val

    show = [s for s in langs_declared[:4]]
    for stem in list(base.keys())[:6]:
        vals = base[stem]
        print(f"\n  key 主干: {stem}")
        for sfx in show:
            if sfx in vals:
                v = vals[sfx]
                v = v[:90] + ("…" if len(v) > 90 else "")
                print(f"    _{sfx}: {v}")


if __name__ == "__main__":
    main()
