import sys, struct
BIN = "build/decomp/Majesty_NorthernExpansion_aarch64.bin"
data = open(BIN, "rb").read()
# 镜像偏移 = 文件偏移 - 0x4E01
IMG = 0x4E01
off = int(sys.argv[1], 0)
size = int(sys.argv[2], 0) if len(sys.argv) > 2 else 0x100
imm = off // 4
print("找 ldr w?, [x?, #%#x]  imm12=%#x" % (off, imm))
hits = []
for i in range(0, len(data) - 4, 4):
    w = struct.unpack_from("<I", data, i)[0]
    if (w & 0xFFC00000) == 0xB9400000:
        if ((w >> 10) & 0xFFF) == imm:
            hits.append(i - IMG)
print("命中 %d 处" % len(hits))
for h in hits[:40]:
    print("  镜像 %#x" % h)
