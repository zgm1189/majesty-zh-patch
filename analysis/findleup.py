# -*- coding: utf-8 -*-
"""在游戏镜像里找「升级判定」代码：
   同时访问 +0x28c（升级门槛）和 +0x4c（等级）的函数。
用法: findleup.py [窗口条数]
"""
import os, struct, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(ROOT, 'build', 'decomp', 'Majesty_NorthernExpansion_aarch64.bin')
IMG2FILE = 0x4E01

data = open(BIN, 'rb').read()
print('镜像 %d 字节' % len(data))


def hits_ldr_str(off):
    """off = 目标结构体偏移（4 字节对齐），返回所有 ldr/str (w|x) [Rn, #off] 的位置。"""
    imm12 = off // 4
    res = []
    KNOWN = {0xB9400000: 'ldr w', 0xF9400000: 'ldr x',
             0xB9000000: 'str w', 0xF9000000: 'str x'}
    n = len(data) - 4
    # ★ 必须从 IMG2FILE 起按 4 字节步进：镜像偏移 4 对齐，但文件偏移 = 镜像+0x4E01，
    #   0x4E01 % 4 == 1，直接按文件 4 对齐扫会整体错位 1 字节，一条都扫不到。
    for i in range(IMG2FILE, n, 4):
        w = struct.unpack_from('<I', data, i)[0]
        top = w & 0xFFC00000
        kind = KNOWN.get(top)
        if kind is None:
            continue
        if ((w >> 10) & 0xFFF) != imm12:
            continue
        res.append((i - IMG2FILE, kind, (w >> 5) & 31, w & 31))
    return res


th = hits_ldr_str(0x28c)
lv = hits_ldr_str(0x4c)
print('引用 +0x28c 的指令 %d 条，引用 +0x4c 的 %d 条' % (len(th), len(lv)))

WIN = int(sys.argv[1]) if len(sys.argv) > 1 else 400     # 窗口（字节）
found = []
for a in th:
    for b in lv:
        if abs(a[0] - b[0]) <= WIN:
            found.append((min(a[0], b[0]), a, b))
found.sort()
seen = set()
for pos, a, b in found:
    key = pos // 0x40
    if key in seen:
        continue
    seen.add(key)
    print('--- 附近 @0x%X  门槛@0x%X(%s x%d->w%d)  等级@0x%X(%s x%d->w%d)'
          % (pos, a[0], a[1], a[2], a[3], b[0], b[1], b[2], b[3]))
print('共 %d 组' % len(found))
