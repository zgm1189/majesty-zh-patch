#!/usr/bin/env python3
"""从 translate.dat 提取所有需要预填的码位，生成 src/cp_table.h。

只取 >= 0x2000 的码位：0xA0–0xFF 那段是引擎自带的西欧字母字形，
我们自己画会覆盖原有记录，导致其它语言显示退化。

用法: python gen_cp_table.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(r"D:\project\逆向\北方的扩张")
SRC = ROOT / "build" / "zh_font" / "assets" / "translate.dat"
OUT = ROOT / "src" / "cp_table.h"
MIN_CP = 0x2000


def main() -> None:
    data = SRC.read_bytes()
    i = 0
    n = len(data)
    cps: set[int] = set()
    while i + 2 <= n:
        ln = int.from_bytes(data[i : i + 2], "big")
        i += 2
        if ln == 0:
            continue
        chunk = data[i : i + ln]
        i += ln
        try:
            text = chunk.decode("utf-8")
        except UnicodeDecodeError:
            continue
        for ch in text:
            o = ord(ch)
            if o >= MIN_CP:
                cps.add(o)

    ordered = sorted(cps)
    lines = [
        "// 自动生成，勿手改（analysis/gen_cp_table.py）",
        f"// 来源: {SRC.name}，共 {len(ordered)} 个码位（>= {MIN_CP:#x}）",
        "static const unsigned short k_cps[] = {",
    ]
    row: list[str] = []
    for c in ordered:
        row.append(f"0x{c:04x},")
        if len(row) == 12:
            lines.append("    " + " ".join(row))
            row = []
    if row:
        lines.append("    " + " ".join(row))
    lines.append("};")
    lines.append(f"static const int k_ncps = {len(ordered)};")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    hanzi = sum(1 for c in ordered if 0x4E00 <= c <= 0x9FFF)
    print(f"写出 {OUT}：{len(ordered)} 个码位（汉字 {hanzi}）")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
