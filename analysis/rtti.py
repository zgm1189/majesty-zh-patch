#!/usr/bin/env python3
"""离线解析 s3e 镜像里的 Itanium RTTI：类名 -> type_info -> vtable -> 虚函数地址。

镜像 dump 在 build/_dump/mem.bin，其偏移就是 vaddr（装载基址由 IMG_BASE 给出）。
"""

from __future__ import annotations

import re
import struct
import sys
from pathlib import Path

MEM = Path(r"D:\project\逆向\北方的扩张\build\_dump\mem.bin")
NAME_RE = re.compile(rb"(\d{1,3})([A-Za-z_][A-Za-z0-9_]*)\x00")


def load():
    mem = MEM.read_bytes()
    base = int(sys.argv[2], 16) if len(sys.argv) > 2 else 0x758CF8B000
    return mem, base


def u64(b, o):
    return struct.unpack_from("<Q", b, o)[0]


def build_index(mem: bytes, base: int) -> dict[str, dict]:
    # 1) 找所有 type_info：8 字节指针指向 "NName" 字符串，且前 8 字节是 type_info vtable
    classes = {}
    for off in range(0, len(mem) - 16, 8):
        v = u64(mem, off)
        if v < base or v >= base + len(mem):
            continue
        tgt = v - base
        m = NAME_RE.match(mem, tgt)
        if not m or int(m.group(1)) != len(m.group(2)):
            continue
        name = m.group(2).decode()
        classes.setdefault(name, {"name_off": tgt, "typeinfo": off - 8})
    # 2) 找 vtable：type_info 地址出现在某处，其后 8 字节即 address point
    ti2cls = {c["typeinfo"]: n for n, c in classes.items()}
    for off in range(0, len(mem) - 16, 8):
        v = u64(mem, off)
        if v < base or v >= base + len(mem):
            continue
        ti = v - base
        if ti in ti2cls:
            c = classes[ti2cls[ti]]
            c["vtable"] = off + 8
    return classes


def dump_class(classes: dict, name: str, mem: bytes, base: int, maxslots: int = 40) -> None:
    c = classes.get(name)
    if not c:
        print(f"{name}: 未找到")
        return
    vt = c.get("vtable")
    print(f"{name}: type_info@0x{c['typeinfo']:x} vtable@0x{vt:x}" if vt else f"{name}: 无 vtable")
    if vt is None:
        return
    for i in range(maxslots):
        v = u64(mem, vt + i * 8)
        if v < base or v >= base + len(mem):
            print(f"  [{i}] <结束> 0x{v:x}")
            break
        print(f"  [{i}] vaddr=0x{v - base:x}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    mem, base = load()
    idx = build_index(mem, base)
    print(f"共识别 {len(idx)} 个类")
    if len(sys.argv) > 1 and sys.argv[1] != "-":
        for n in sys.argv[1].split(","):
            dump_class(idx, n, mem, base)
    else:
        for n in sorted(idx):
            if idx[n].get("vtable"):
                print(f"  {n}")
