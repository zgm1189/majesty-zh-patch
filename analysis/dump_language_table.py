#!/usr/bin/env python3
"""导出 translate.dat 的 8 语言对照表（只读，不修改任何汉化产物）。"""

from __future__ import annotations

import re
import sys
from collections import Counter, OrderedDict
from pathlib import Path

SRC = Path(r"D:\project\逆向\北方的扩张\extracted\assets\translate.dat")
OUT_TSV = Path(r"D:\project\逆向\北方的扩张\analysis\language_table.tsv")

LANGS = ["en", "de", "fr", "it", "es", "ru", "pl", "pt"]
LANG_NAME = {
    "en": "英语 English", "de": "德语 Deutsch", "fr": "法语 Français",
    "it": "意大利语 Italiano", "es": "西班牙语 Español",
    "ru": "俄语 Русский", "pl": "波兰语 Polski", "pt": "葡萄牙语 Português",
}
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


def split_kv(r: str):
    if ": " in r:
        k, _, v = r.partition(": ")
        return k, v
    if ":" in r:
        k, _, v = r.partition(":")
        return k, v
    return r, None


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    recs = parse(SRC.read_bytes())

    table: OrderedDict[str, dict[str, str]] = OrderedDict()
    for r in recs:
        k, v = split_kv(r)
        if v is None:
            continue
        m = SUFFIX_RE.match(k)
        if not m:
            continue
        table.setdefault(m.group(1), {})[m.group(2)] = v

    # ---- 写 TSV ----
    def clean(s: str) -> str:
        return s.replace("\t", " ").replace("\r", "").replace("\n", " ")

    lines = ["key\t" + "\t".join(LANG_NAME[l].split()[0] for l in LANGS)]
    for stem, vals in table.items():
        row = [stem] + [clean(vals.get(l, "")) for l in LANGS]
        lines.append("\t".join(row))
    OUT_TSV.write_text("\n".join(lines), encoding="utf-8-sig")
    print(f"已导出对照表: {OUT_TSV}")
    print(f"  行数(key 数): {len(table)}    列: key + {len(LANGS)} 语言")
    print()

    # ---- 完整性检查：每个 key 是否 8 语言齐全 ----
    print("=" * 78)
    print("完整性检查：每个 key 在 8 种语言下的覆盖情况")
    print("=" * 78)
    full = sum(1 for v in table.values() if len(v) == len(LANGS))
    print(f"  8 语言齐全的 key: {full} / {len(table)}")
    missing = {l: 0 for l in LANGS}
    for v in table.values():
        for l in LANGS:
            if l not in v:
                missing[l] += 1
    print(f"  各语言缺失数: {missing}")
    print()

    # ---- 控制台预览：前 14 条，8 语言并排 ----
    print("=" * 78)
    print("对照预览（前 14 条，值截断到 30 字符）")
    print("=" * 78)
    for stem in list(table.keys())[:14]:
        vals = table[stem]
        print(f"\n▶ {stem}")
        for l in LANGS:
            v = vals.get(l, "—")
            v = v[:30] + ("…" if len(v) > 30 else "")
            print(f"   {l}: {v}")

    # ---- key 前缀分组统计（让用户了解全貌）----
    print()
    print("=" * 78)
    print("key 前缀分组（词条分布）")
    print("=" * 78)
    pre = Counter(re.sub(r"[0-9_\-]+$", "", s) for s in table)
    for name, cnt in pre.most_common(28):
        print(f"  {name:<32} {cnt:>4}")


if __name__ == "__main__":
    main()
