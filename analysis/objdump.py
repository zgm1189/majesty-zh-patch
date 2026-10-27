import sys, struct, re
path = "build/zhout.txt"
base = None
mem = {}
for line in open(path, encoding="utf-8", errors="replace"):
    line = line.rstrip("\n")
    m = re.match(r"^(0x[0-9a-fA-F]+)\s+([0-9a-fA-F]+)", line)
    if m:
        addr = int(m.group(1), 16)
        hx = m.group(2)
        if len(hx) < 32: continue
        try:
            b = bytes.fromhex(hx)
        except ValueError:
            continue
        for i, ch in enumerate(b):
            mem[addr+i] = ch
if not mem:
    print("no mem"); sys.exit()
lo = min(mem); hi = max(mem)+1
print("range %#x .. %#x  (%d bytes)" % (lo, hi, hi-lo))
def ld32(a):
    if a+4 > hi: return None
    return struct.unpack("<i", bytes(mem.get(a+i,0) for i in range(4)))[0]
def ld64(a):
    if a+8 > hi: return None
    return struct.unpack("<Q", bytes(mem.get(a+i,0) for i in range(8)))[0]
targets = [int(x,0) for x in sys.argv[1:]]
for t in targets:
    print("=== == %d (%#x) ===" % (t, t))
    for off in range(0, hi-lo-4, 4):
        if ld32(lo+off) == t:
            print("  +0x%03x" % off)
# also list all int32 in plausible ranges
print("=== 所有 int32 值 (off=value) 中 value 在 1..200000 ===")
rows=[]
for off in range(0, hi-lo-4, 4):
    v = ld32(lo+off)
    if v is not None and 1 <= v <= 200000:
        rows.append((off, v))
for off,v in rows:
    print("  +0x%03x = %d" % (off, v))
