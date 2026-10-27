#!/usr/bin/env python3
"""去掉百分网（byfen）实名认证：让 com.authentication.MyApp.onCreate 只调 super。

背景
----
这个包里 application 的 name 是 `com.authentication.MyApp`，它的 onCreate 干了两件事：

    b.a.a.c()  拿到单例（构造器里 postDelayed(3000, runnable)）
    registerActivityLifecycleCallbacks(b.a.a)

3 秒后 runnable 执行 `b.a.h.b.e()` → HTTP GET `https://app2.byfen.com/get_country`
→ 回调里看 JSON 的 "cn" 字段：

    cn == true    → b.a.h.b.a(activity)  弹「需完成实名认证后才能开始网络游戏」
    cn == false   → 什么都不做
    请求失败      → b.a.h.b.a(activity)  同样弹实名

也就是说**只要请求不通就必弹**，国外网络访问国内接口经常超时，所以外国玩家大概率卡在这里。
`b.a.a` 这个单例只服务认证流程（grep 全 dex，其他引用都在 get_country 的回调里），
所以把 onCreate 里的注册去掉，整条链路就断了，不影响游戏本体。

做法
----
onCreate 原本 21 个 code unit：

    invoke-super {v2}, MultiDexApplication.onCreate   (3)
    invoke-static {}, b.a.a.c()                       (3)
    move-result-object v0                             (1)
    invoke-virtual {v2,v0}, registerActivityLifecycleCallbacks (3)
    invoke-static {}, b.a.a.c()                       (3)
    move-result-object v0                             (1)
    const v1, 0x1f01                                  (3)
    invoke-virtual {v0,v1}, b.a.a.f(I)                (3)
    return-void                                       (1)

改成 `invoke-super` + `return-void` + 17 个 nop，unit 数不变，
所以 code_item 的 insns_size、try/catch 表、debug info 都不用动。
最后按 dex 规范重算 header 里的 signature(SHA-1) 和 checksum(adler32)。

用法：
  python tools/patch_dex_noauth.py <输入 classes3.dex> <输出 classes3.dex>
"""

from __future__ import annotations

import hashlib
import struct
import sys
import zlib
from pathlib import Path

# MyApp.onCreate 前 20 字节，足够唯一
SIG = bytes.fromhex("6f1018060200" "7100 573e 0000" "0c00" "6e20 cc00 0200")
ORIG_LEN = 21 * 2  # 21 个 code unit

NEW = (
    bytes.fromhex("6f1018060200")   # invoke-super {v2}, MultiDexApplication.onCreate
    + bytes.fromhex("0e00")          # return-void
    + b"\x00\x00" * 17               # nop × 17，凑满 21 unit
)
assert len(NEW) == ORIG_LEN, (len(NEW), ORIG_LEN)


def fix_header(buf: bytearray) -> None:
    """按 dex 规范重算 signature(SHA-1, 从 0x20 起) 与 checksum(adler32, 从 0x0C 起)。"""
    if buf[:4] != b"dex\n":
        raise SystemExit("不是 dex 文件")
    sig = hashlib.sha1(bytes(buf[0x20:])).digest()
    buf[0x0C:0x20] = sig
    chk = zlib.adler32(bytes(buf[0x0C:])) & 0xFFFFFFFF
    struct.pack_into("<I", buf, 0x08, chk)


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 1
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    buf = bytearray(src.read_bytes())

    hits = []
    start = 0
    while True:
        i = buf.find(SIG, start)
        if i < 0:
            break
        hits.append(i)
        start = i + 1

    print(f"特征命中 {len(hits)} 处：{[hex(h) for h in hits]}")
    if len(hits) != 1:
        print("[x] 预期唯一命中，实际不是 —— dex 结构变了，先重新确认再改")
        return 2

    off = hits[0]
    old = bytes(buf[off:off + ORIG_LEN])
    print(f"改动前：{old.hex()}")
    buf[off:off + ORIG_LEN] = NEW
    print(f"改动后：{bytes(buf[off:off + ORIG_LEN]).hex()}")

    fix_header(buf)
    dst.write_bytes(buf)
    print(f"写出 {dst}  ({len(buf):,} bytes)")
    print(f"  checksum = {struct.unpack_from('<I', buf, 0x08)[0]:#010x}")
    print(f"  signature= {buf[0x0C:0x20].hex()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
