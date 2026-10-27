"""在镜像里找「代码通过 adrp+add 计算出某个镜像地址」的位置。

背景 / 坑：
  1. 镜像偏移 0 对应 .bin 文件偏移 0x4E01，所以指令在文件里是 4k+1 对齐。
     扫指令必须 range(1, n, 4)，否则全部错位（这个坑踩过一次，所有扫描失效）。
  2. adrp 是 PC 相对 + 页对齐：
         target_page = (镜像偏移(该指令) & ~0xFFF) + (imm21 << 12)
     后面紧跟的 add xD, xN, #imm12 才是页内偏移。
  3. objdump 反汇编这个 bin 时把它当 offset 0 的 .text，显示的地址要减 0x4E01
     才是镜像偏移。别直接拿 objdump 的地址当运行时偏移用。

用法：
    python analysis/adrp_scan.py 0x44f858 0x44f870 ...
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BIN = ROOT / "build" / "decomp" / "Majesty_NorthernExpansion_aarch64.bin"
HDR = 0x4E01


def sx(v: int, bits: int) -> int:
    if v & (1 << (bits - 1)):
        return v - (1 << bits)
    return v


def main() -> None:
    targets = [int(a, 16) for a in sys.argv[1:]]
    d = BIN.read_bytes()
    n = len(d)

    # 先把所有 adrp 解析出来：文件偏移 -> (目标页, Rd)
    adrps: list[tuple[int, int, int]] = []
    for i in range(1, n - 4, 4):
        w = struct.unpack_from("<I", d, i)[0]
        if (w & 0x9F000000) != 0x90000000:
            continue
        immlo = (w >> 29) & 3
        immhi = (w >> 5) & 0x7FFFF
        imm = sx((immhi << 2) | immlo, 21)
        rd = w & 0x1F
        img_off = i - HDR
        page = (img_off & ~0xFFF) + (imm << 12)
        adrps.append((i, page, rd))

    print(f"adrp 指令 {len(adrps)} 条，镜像 {n} 字节")

    want = {t: t & ~0xFFF for t in targets}
    for i, page, rd in adrps:
        if page not in want.values():
            continue
        # 往后看 1~2 条指令找 add xD, xRd, #imm
        for k in range(1, 3):
            j = i + k * 4
            if j + 4 > n:
                break
            w = struct.unpack_from("<I", d, j)[0]
            # add (immediate) 64/32 bit, sh=0/1
            if (w & 0x7F800000) not in (0x11000000, 0x11000000 | 0x40000000):
                continue
            if (w & 0x7F000000) != 0x11000000:
                continue
            sf = (w >> 31) & 1
            sh = (w >> 22) & 1
            imm12 = (w >> 10) & 0xFFF
            rn = (w >> 5) & 0x1F
            rdd = w & 0x1F
            if rn != rd:
                continue
            val = imm12 << (12 if sh else 0)
            addr = page + val
            if addr in targets:
                print(
                    f"  HIT img=0x{i - HDR:x} (file 0x{i:x}) -> 0x{addr:x}"
                    f"  (add at img=0x{j - HDR:x}, sf={sf})"
                )
                break


if __name__ == "__main__":
    main()
