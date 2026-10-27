#!/usr/bin/env python3
"""把一段 Frida JS 塞进已经跑起来的 gadget，打印输出。

用法:  python fr.py <script.js> [--wait 秒]
脚本里调用 send({done: true}) 可提前结束。
"""

import sys
import time
from pathlib import Path

import frida

ADB_PORT = "127.0.0.1:27042"
OUT_DIR = Path("build/_dump")

state = {"done": False}


def on_message(msg, data):
    if msg["type"] != "send":
        print("!!", msg.get("description") or msg)
        return
    payload = msg["payload"]
    if data is not None and isinstance(payload, dict) and "file" in payload:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        (OUT_DIR / payload["file"]).write_bytes(data)
        print("[saved]", payload["file"], len(data), "bytes")
        return
    if isinstance(payload, dict) and payload.get("done"):
        print("[done]")
        state["done"] = True
        return
    print(payload if isinstance(payload, str) else repr(payload))


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    js_path = Path(sys.argv[1])
    wait = 30.0
    if "--wait" in sys.argv:
        wait = float(sys.argv[sys.argv.index("--wait") + 1])

    dev = frida.get_device_manager().add_remote_device(ADB_PORT)
    procs = dev.enumerate_processes()
    if not procs:
        raise SystemExit("gadget 里没有进程，游戏是不是没跑？")
    session = dev.attach(procs[0].pid)
    script = session.create_script(js_path.read_text(encoding="utf-8"))
    script.on("message", on_message)
    script.load()
    end = time.time() + wait
    while not state["done"] and time.time() < end:
        time.sleep(0.1)
    sys.stdout.flush()


if __name__ == "__main__":
    main()
