#!/usr/bin/env python3
"""在 mem.dis 里找「引用了某个地址」的代码（adrp+add 组合）。

用法: python xref.py 0x44ecf8 [0x448120 ...]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

DIS = Path(r"D:\project\逆向\北方的扩张\build\_dump\mem.dis")
LINE = re.compile(r"^\s*([0-9a-f]+):\s*\t(.*)$")
ADRP = re.compile(r"^adrp\s+(x\d+), 0x([0-9a-f]+)")
ADD = re.compile(r"^add\s+(x\d+), (x\d+), #0x([0-9a-f]+)")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    targets = {int(a, 16): a for a in sys.argv[1:]}
    pend = {}          # reg -> (addr, page)
    for raw in DIS.open("r", encoding="utf-8", errors="replace"):
        m = LINE.match(raw)
        if not m:
            continue
        addr = int(m.group(1), 16)
        ins = m.group(2).strip()
        a = ADRP.match(ins)
        if a:
            pend[a.group(1)] = (addr, int(a.group(2), 16))
            continue
        b = ADD.match(ins)
        if b:
            reg, src, off = b.group(1), b.group(2), int(b.group(3), 16)
            if src in pend:
                page = pend[src][1]
                val = page + off
                if val in targets:
                    print(f"{targets[val]}  <-  0x{addr:06x}   ({ins})")
            continue
        # 其它指令里出现的寄存器若被覆盖就清掉，避免误报
        for r in re.findall(r"\b(x\d+)\b", ins):
            if r in pend and not ins.startswith("add") and not ins.startswith("adrp"):
                pend.pop(r, None)


if __name__ == "__main__":
    main()
