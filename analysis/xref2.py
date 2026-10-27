#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在 mem.dis 里找「访问了某个地址范围」的指令（adrp + ldr/str/add 组合）。

比 xref.py 更宽松：
  - 支持 adrp x8, page; ldr w9, [x8, #0x40]
  - 支持 adrp x8, page; add x8, x8, #0x40; ldr w9, [x8, #0x10]（二级偏移也算）
  - 只在「同一寄存器被重新 adrp」或「被 mov/ldr 覆盖」时清栈

用法: python xref2.py 0x53c000 0x53c100
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

DIS = Path(r"D:\project\逆向\北方的扩张\build\_dump\mem.dis")
LINE = re.compile(r"^\s*([0-9a-f]+):\s*\t(.*)$")
ADRP = re.compile(r"^adrp\s+(x\d+), 0x([0-9a-f]+)")
MEM = re.compile(r"^(ldr|str|ldrb|strb|ldrh|strh|ldrsb|ldrsh|ldrsw)\s+(\w+), \[(x\d+)(?:, #(0x[0-9a-f]+))?\]")
ADD = re.compile(r"^add\s+(x\d+), (x\d+), #(0x[0-9a-f]+)$")
WRITE = re.compile(r"^(mov|movz|movk|movn|ldr|ldrb|ldrh|adr)\s+(x\d+)")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    lo = int(sys.argv[1], 16)
    hi = int(sys.argv[2], 16) if len(sys.argv) > 2 else lo + 4
    page = {}          # reg -> 绝对页基址
    addv = {}          # reg -> 绝对地址（adrp+add 结果）
    hits = 0
    with DIS.open("r", encoding="utf-8", errors="replace") as f:
        for raw in f:
            m = LINE.match(raw)
            if not m:
                continue
            addr = int(m.group(1), 16)
            ins = m.group(2).strip()

            a = ADRP.match(ins)
            if a:
                r, pg = a.group(1), int(a.group(2), 16)
                page[r] = pg
                addv.pop(r, None)
                continue

            b = ADD.match(ins)
            if b:
                dst, src, off = b.group(1), b.group(2), int(b.group(3), 16)
                base = addv.get(src, page.get(src))
                if base is not None:
                    addv[dst] = base + off
                else:
                    addv.pop(dst, None)
                continue

            c = MEM.match(ins)
            if c:
                reg = c.group(3)
                off = int(c.group(4), 16) if c.group(4) else 0
                base = addv.get(reg, page.get(reg))
                if base is not None:
                    tgt = base + off
                    if lo <= tgt < hi:
                        hits += 1
                        print("0x%06x  %-34s -> 0x%x" % (addr, ins, tgt))
                # 目标寄存器被写，清掉它的记录
                d = WRITE.match(ins)
                if d:
                    addv.pop(d.group(2), None)
                    page.pop(d.group(2), None)
                continue

            # 其它指令覆盖了寄存器就清
            d = WRITE.match(ins)
            if d:
                addv.pop(d.group(2), None)
                page.pop(d.group(2), None)

    print("--- %d 处 ---" % hits)


if __name__ == "__main__":
    main()
