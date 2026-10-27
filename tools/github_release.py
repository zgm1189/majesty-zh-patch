#!/usr/bin/env python3
"""建 GitHub Release 并上传 APK。

用法：
  GITHUB_TOKEN=xxx python tools/github_release.py <owner/repo> --tag v1.6.00 \
      --name "v1.6.00" --body-file docs/release-notes.md \
      --asset 北方的扩张_纯翻译版.apk=build/out/北方的扩张_纯翻译版.apk \
      --asset 北方的扩张_完整版.apk=build/out/北方的扩张_完整版.apk

上传走 uploads.github.com（和 api.github.com 一样能穿代理，github.com:443 反而不行）。
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.github.com"
UPLOAD = "https://uploads.github.com"


def api(method: str, url: str, token: str, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    r = urllib.request.Request(url, data=data, method=method)
    r.add_header("Authorization", f"token {token}")
    r.add_header("Accept", "application/vnd.github+json")
    r.add_header("User-Agent", "majesty-zh-patch-release")
    if data:
        r.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(r, timeout=120) as resp:
            body = resp.read()
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{method} {url} -> {e.code}: {e.read().decode('utf-8','replace')[:400]}") from None


def upload_asset(repo: str, release_id: int, token: str, name: str, path: Path) -> None:
    size = path.stat().st_size
    ctype = mimetypes.guess_type(name)[0] or "application/vnd.android.package-archive"
    url = f"{UPLOAD}/repos/{repo}/releases/{release_id}/assets?name={urllib.request.quote(name)}"
    print(f"  上传 {name}  ({size/1048576:.1f} MB) ...")
    t0 = time.time()
    with open(path, "rb") as f:
        r = urllib.request.Request(url, data=f, method="POST")
        r.add_header("Authorization", f"token {token}")
        r.add_header("Content-Type", ctype)
        r.add_header("Content-Length", str(size))
        r.add_header("User-Agent", "majesty-zh-patch-release")
        try:
            with urllib.request.urlopen(r, timeout=1800) as resp:
                info = json.loads(resp.read() or b"{}")
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"上传 {name} 失败 {e.code}: {e.read().decode('utf-8','replace')[:300]}") from None
    dt = time.time() - t0
    print(f"    ok  {dt:.0f}s  {info.get('browser_download_url','')}")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("--tag", required=True)
    ap.add_argument("--name", default=None)
    ap.add_argument("--body-file", default=None)
    ap.add_argument("--draft", action="store_true")
    ap.add_argument("--asset", action="append", default=[], help="远端名=本地路径")
    args = ap.parse_args()

    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        print("[x] 没设 GITHUB_TOKEN")
        return 1

    body = Path(args.body_file).read_text(encoding="utf-8") if args.body_file else ""

    # 已存在就复用（重跑不会撞 422）
    try:
        rel = api("GET", f"{API}/repos/{args.repo}/releases/tags/{args.tag}", token)
        print(f"复用已有 Release {args.tag} (id={rel['id']})")
    except RuntimeError:
        rel = api("POST", f"{API}/repos/{args.repo}/releases", token, {
            "tag_name": args.tag,
            "name": args.name or args.tag,
            "body": body,
            "draft": args.draft,
            "prerelease": False,
        })
        print(f"创建 Release {args.tag} (id={rel['id']})")

    existing = {a["name"] for a in rel.get("assets", [])}
    for spec in args.asset:
        name, _, local = spec.partition("=")
        path = Path(local or name)
        if not path.is_file():
            print(f"[!] 跳过（文件不存在）: {path}")
            continue
        if name in existing:
            print(f"  已存在，跳过: {name}")
            continue
        upload_asset(args.repo, rel["id"], token, name, path)

    print(f"[ok] https://github.com/{args.repo}/releases/tag/{args.tag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
