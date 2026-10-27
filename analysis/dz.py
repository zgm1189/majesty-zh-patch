#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""镜像反汇编小工具：dz.py <镜像起始偏移> [条数]
镜像偏移 -> 文件偏移 = +0x4E01
"""
import sys, os
from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(ROOT, 'build', 'decomp', 'Majesty_NorthernExpansion_aarch64.bin')
IMG2FILE = 0x4E01


def main():
    start = int(sys.argv[1], 0)
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 40
    data = open(BIN, 'rb').read()
    off = start + IMG2FILE
    code = data[off:off + n * 4]
    md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
    md.detail = False
    for ins in md.disasm(code, start):
        print('%08x: %-8s %s %s' % (ins.address, ins.bytes.hex(), ins.mnemonic, ins.op_str))


if __name__ == '__main__':
    main()
