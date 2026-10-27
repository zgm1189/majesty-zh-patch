#!/usr/bin/env python3
"""反汇编 build/_dump/mem.bin 里的一段（地址即镜像 vaddr）。

用法: python disasm.py 0x8c08c 0x8c110
"""

from __future__ import annotations

import struct
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(r"D:\project\逆向\北方的扩张")
MEM = ROOT / "build" / "_dump" / "mem.bin"
NDK = Path(r"D:\flutter\androidsdk\ndk\27.0.12077973\toolchains\llvm\prebuilt\windows-x86_64\bin")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    start = int(sys.argv[1], 16)
    end = int(sys.argv[2], 16)
    mem = MEM.read_bytes()
    start &= ~3
    chunk = mem[start:end]
    words = [struct.unpack_from("<I", chunk, i)[0] for i in range(0, len(chunk) - 3, 4)]
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        src = td / "a.s"
        src.write_text(".section .text\n" + "".join(f".inst 0x{w:08x}\n" for w in words), encoding="utf-8")
        subprocess.run([str(NDK / "clang.exe"), "--target=aarch64-linux-android26", "-c", str(src), "-o", str(td / "a.o")], check=True)
        subprocess.run([str(NDK / "ld.lld.exe"), f"-Ttext={start:#x}", "-o", str(td / "a.elf"), str(td / "a.o")],
                       check=True, capture_output=True)
        out = subprocess.run([str(NDK / "llvm-objdump.exe"), "-d", "--no-show-raw-insn", str(td / "a.elf")],
                             check=True, capture_output=True, text=True).stdout
    for line in out.splitlines():
        if line.strip().startswith("a.elf:") or "file format" in line or "Disassembly" in line:
            continue
        print(line.rstrip())


if __name__ == "__main__":
    main()
