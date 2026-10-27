#!/usr/bin/env python3
"""把 frida-gadget 注入 APK —— 通过给 libs3e_android.so 追加一条 DT_NEEDED。

不碰 dex、不碰清单，只改 ELF 动态段：链接器加载 libs3e_android.so 时会顺带把
libfrida-gadget.so 一起拉进进程，gadget 的构造函数随即启动监听。

用法: python inject_gadget.py [--no-zh]
"""

from __future__ import annotations

import io
import json
import os
import shutil
import struct
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(r"D:\project\逆向\北方的扩张")
BUILD = ROOT / "build"
SRC_APK = ROOT / "com.herocraft.game.majesty_ne.apk"
WORK = BUILD / "_inject"
TARGET_LIB = "lib/arm64-v8a/libs3e_android.so"
GADGET = BUILD / "_frida" / "libfrida-gadget.so"
PKG = "com.herocraft.game.majesty_ne"
EXT_DIR = f"/sdcard/Android/data/{PKG}/files"
VERSION_CODE = 10600
VERSION_NAME = "1.6.00"

# .rodata 里的一段对齐填充（0x124619 起 3991 个 0 字节），只用于放库名字符串
STR_PAD_OFF = 0x124619
# .text 里 switch 跳转表之后的零填充（0x3702C 起 4084 个 0 字节），放 DT_INIT 桩
STUB_OFF = 0x3702C
DYN_OFF, DYN_SIZE = 0x1526D0, 0x1D0
DT_INIT = 12
DT_NULL = 0

BUILD_TOOLS = Path(r"D://flutter//androidsdk//build-tools//35.0.0")
APKSIGNER = BUILD_TOOLS / "apksigner.bat"
ZIPALIGN = BUILD_TOOLS / "zipalign.exe"
KEYSTORE = BUILD / "poc.keystore"


def patch_lib(data: bytes, soname: str, stub: bytes) -> bytes:
    """给 libs3e_android.so 加一个 DT_INIT 桩：加载时 dlopen 指定 .so。

    走 DT_INIT 而不是 DT_NEEDED，是因为 bionic 的 get_string() 会校验
    `index < strtab_size_`，而 .dynstr 没有空位可放新库名；DT_INIT 只用一个
    地址，桩代码自己去 dlopen，绕开整张字符串表。
    """
    name = soname.encode() + b"\0"
    if len(name) > 200:
        raise SystemExit(f"库名太长: {soname}")
    buf = bytearray(data)
    # 1) 字符串 + 桩代码
    buf[STR_PAD_OFF:STR_PAD_OFF + len(name)] = name
    buf[STUB_OFF:STUB_OFF + len(stub)] = stub
    # 2) 动态段：第一个 DT_NULL 改成 DT_INIT，后面保留 DT_NULL 收尾
    slot = None
    for i in range(0, DYN_SIZE, 16):
        tag, _ = struct.unpack_from("<QQ", buf, DYN_OFF + i)
        if tag == DT_NULL:
            slot = DYN_OFF + i
            break
    if slot is None:
        raise SystemExit("动态段没有空槽")
    struct.pack_into("<QQ", buf, slot, DT_INIT, STUB_OFF)
    return bytes(buf)


def verify_lib(data: bytes, stub: bytes) -> None:
    init = None
    for i in range(0, DYN_SIZE, 16):
        tag, val = struct.unpack_from("<QQ", data, DYN_OFF + i)
        if tag == DT_INIT:
            init = val
    assert init == STUB_OFF, f"DT_INIT 未生效: {init}"
    assert data[STUB_OFF:STUB_OFF + len(stub)] == stub, "桩代码未写入"
    print(f"  回验 DT_INIT -> {init:#x}，桩 {len(stub)} 字节")


def patch_manifest(data: bytes, code: int, name: str) -> bytes:
    """等长改写 versionCode / versionName（覆盖安装不能降级）。"""
    import patch_manifest as pm

    buf = bytearray(data)
    orig = len(buf)
    strings = pm.StringPool(buf, 8)
    target = None
    for off, name_idx, attr_start, attr_size, attr_count in pm.iter_elements(buf, 8, strings):
        if strings.get(name_idx) == "manifest":
            target = (off, attr_start, attr_size, attr_count)
            break
    if target is None:
        raise SystemExit("<manifest> 未找到")
    off, attr_start, attr_size, attr_count = target
    code_attr = name_idx = None
    for k in range(attr_count):
        a = off + 16 + attr_start + k * attr_size
        aname = strings.get(pm.u32(buf, a + 4))
        if aname == "versionCode":
            code_attr = a
        elif aname == "versionName":
            name_idx = pm.u32(buf, a + 16)
    old_name = strings.get(name_idx)
    if len(name) != len(old_name):
        raise SystemExit(f"versionName 长度必须为 {len(old_name)}")
    strings.replace(name_idx, name)
    old_code = pm.u32(buf, code_attr + 16)
    buf[code_attr + 16:code_attr + 20] = code.to_bytes(4, "little")
    assert len(buf) == orig
    print(f"  清单: versionCode {old_code} -> {code}, versionName {old_name} -> {name}")
    return bytes(buf)


def gadget_config() -> bytes:
    cfg = {
        "interaction": {
            "type": "listen",
            "address": "127.0.0.1",
            "port": 27042,
            "on_load": "resume",
        },
        "log": {"level": "info", "file": f"{EXT_DIR}/gadget.log"},
    }
    return json.dumps(cfg, indent=2).encode()


DEV_SO = None


def build_apk(with_zh: bool, zh_only: bool = False, debug: bool = False) -> Path:
    WORK.mkdir(parents=True, exist_ok=True)
    src = zipfile.ZipFile(SRC_APK)
    stub = (WORK / "stub.bin").read_bytes()
    # 产品模式：桩直接 dlopen libzhfont.so，不带 gadget
    # 调试模式：桩加载 gadget，APK 里也带 zhfont + translate，Frida 手动 dlopen
    if zh_only and not debug and DEV_SO:
        stub_lib = DEV_SO
    elif zh_only and not debug:
        stub_lib = "libzhfont.so"
    else:
        stub_lib = "libfrida-gadget.so"
    lib = patch_lib(src.read(TARGET_LIB), stub_lib, stub)
    verify_lib(lib, stub)
    (WORK / "libs3e_android.so").write_bytes(lib)

    translate = BUILD / "zh_font" / "assets" / "translate.dat"
    manifest = patch_manifest(src.read("AndroidManifest.xml"), VERSION_CODE, VERSION_NAME)
    out = WORK / "unsigned.apk"
    with zipfile.ZipFile(out, "w") as zout:
        for item in src.infolist():
            n = item.filename
            if n.startswith("META-INF/") or n == TARGET_LIB:
                continue
            if n == "AndroidManifest.xml":
                zout.writestr(item, manifest)
                continue
            if n == "assets/translate.dat" and with_zh:
                continue
            zout.writestr(item, src.read(n))
        zout.writestr(TARGET_LIB, lib, zipfile.ZIP_DEFLATED)
        if not zh_only or debug:
            for extra in ("libfrida-gadget.so", "libfrida-gadget.config.so"):
                path = GADGET if extra.endswith("-gadget.so") else None
                body = path.read_bytes() if path else gadget_config()
                zout.writestr(f"lib/arm64-v8a/{extra}", body, zipfile.ZIP_DEFLATED)
        zhso = BUILD / "so" / "libzhfont.so"
        if zhso.exists():
            zout.writestr("lib/arm64-v8a/libzhfont.so", zhso.read_bytes(), zipfile.ZIP_DEFLATED)
            print(f"  已加入 libzhfont.so ({zhso.stat().st_size/1e6:.2f} MB)")
        if with_zh:
            zout.writestr("assets/translate.dat", translate.read_bytes(), zipfile.ZIP_DEFLATED)
    print(f"  打包完成: {out.stat().st_size/1e6:.1f} MB (含中文={with_zh})")
    return out


def sign(unsigned: Path, with_zh: bool, zh_only: bool = False) -> Path:
    aligned = WORK / "aligned.apk"
    if zh_only:
        signed = BUILD / "majesty_zh.apk"
    else:
        signed = BUILD / ("majesty_zh_gadget.apk" if with_zh else "majesty_gadget.apk")
    subprocess.run([str(ZIPALIGN), "-f", "-p", "4", str(unsigned), str(aligned)], check=True)
    for p in (signed, signed.with_suffix(".apk.idsig")):
        p.unlink(missing_ok=True)
    subprocess.run([
        str(APKSIGNER), "sign",
        "--ks", str(KEYSTORE), "--ks-pass", "pass:android",
        "--ks-key-alias", "poc", "--key-pass", "pass:android",
        "--v1-signing-enabled", "true", "--v2-signing-enabled", "true",
        "--v3-signing-enabled", "true",
        "--out", str(signed), str(aligned),
    ], check=True)
    print(f"  已签名: {signed} ({signed.stat().st_size/1e6:.1f} MB)")
    return signed


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    with_zh = "--no-zh" not in sys.argv
    global DEV_SO
    DEV_SO = ("/storage/emulated/0/Android/data/com.herocraft.game.majesty_ne/files/libzhfont_dev.so"
              if "--dev" in sys.argv else None)
    zh_only = "--zh-only" in sys.argv
    apk = build_apk(with_zh, zh_only)
    sign(apk, with_zh, zh_only)


if __name__ == "__main__":
    main()
