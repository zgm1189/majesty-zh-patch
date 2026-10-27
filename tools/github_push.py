#!/usr/bin/env python3
"""用 GitHub Git Data API 推送仓库（当 git push 的 443 被墙、只有 api.github.com 通时用）。

流程：每个文件 → blob → tree → commit → 更新 ref。
全部走 https://api.github.com，不碰 github.com:443。

用法：
  GITHUB_TOKEN=ghp_xxx python tools/github_push.py <owner/repo> [--branch main] [--message "..."]

令牌从环境变量读，不写进命令行历史。
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.github.com"


def req(method: str, url: str, token: str, payload=None, tries: int = 3):
    data = json.dumps(payload).encode() if payload is not None else None
    for attempt in range(tries):
        r = urllib.request.Request(url, data=data, method=method)
        r.add_header("Authorization", f"token {token}")
        r.add_header("Accept", "application/vnd.github+json")
        r.add_header("User-Agent", "majesty-zh-patch-push")
        if data:
            r.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(r, timeout=180) as resp:
                body = resp.read()
                return json.loads(body) if body else {}
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:400]
            # 409/422 之类不重试，直接抛
            if e.code in (401, 403, 404, 422):
                raise RuntimeError(f"{method} {url} -> {e.code}: {detail}") from None
            if attempt == tries - 1:
                raise RuntimeError(f"{method} {url} -> {e.code}: {detail}") from None
            time.sleep(2 * (attempt + 1))
        except Exception as e:  # 网络抖动
            if attempt == tries - 1:
                raise RuntimeError(f"{method} {url} 失败: {e}") from None
            time.sleep(2 * (attempt + 1))
    raise RuntimeError("unreachable")


def git_files(root: Path) -> list[Path]:
    # -z + 关掉 quotepath：否则 git 会把中文路径转义成 "docs/\346\236\204..."，
    # 拿到的字符串根本打不开（Windows 上直接 OSError 22）。
    out = subprocess.run(
        ["git", "-c", "core.quotepath=false", "ls-files", "-z"],
        cwd=root, capture_output=True, check=True,
    )
    names = out.stdout.decode("utf-8", "replace").split("\0")
    return [root / n for n in names if n.strip()]


def ensure_nonempty(repo: str, token: str, branch: str, root: Path) -> None:
    """空仓库不接受 blob API（409 Git Repository is empty），先落一个 README 起个头。"""
    try:
        req("GET", f"{API}/repos/{repo}/git/ref/heads/{branch}", token)
        return
    except RuntimeError:
        pass
    readme = root / "README.md"
    raw = readme.read_bytes() if readme.is_file() else b"# init\n"
    print("仓库是空的，先用 contents API 建初始提交")
    req("PUT", f"{API}/repos/{repo}/contents/README.md", token, {
        "message": "chore: init",
        "content": base64.b64encode(raw).decode(),
        "branch": branch,
    })


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("repo", help="owner/repo")
    ap.add_argument("--branch", default="main")
    ap.add_argument("--message", default="")
    ap.add_argument("--root", default=".")
    ap.add_argument("--changed-only", action="store_true",
                    help="只推 HEAD~1..HEAD 改动的文件（配合 base_tree，几秒钟就完）")
    args = ap.parse_args()

    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        print("[x] 没设 GITHUB_TOKEN")
        return 1

    root = Path(args.root).resolve()
    ensure_nonempty(args.repo, token, args.branch, root)

    base_tree = None
    if args.changed_only:
        out = subprocess.run(
            ["git", "-c", "core.quotepath=false", "diff", "--name-only", "-z", "HEAD~1", "HEAD"],
            cwd=root, capture_output=True, check=True,
        )
        names = [n for n in out.stdout.decode("utf-8", "replace").split("\0") if n.strip()]
        files = [root / n for n in names if (root / n).is_file()]
        # 远端当前 tree 作基线，只提交改动条目
        head = req("GET", f"{API}/repos/{args.repo}/git/ref/heads/{args.branch}", token)
        cobj = req("GET", f"{API}/repos/{args.repo}/git/commits/{head['object']['sha']}", token)
        base_tree = cobj["tree"]["sha"]
        print(f"增量模式：{len(files)} 个改动文件，base_tree={base_tree[:8]}")
    else:
        files = git_files(root)
    print(f"待推送 {len(files)} 个文件，仓库 {args.repo}")

    # 1) 每个文件建一个 blob
    tree_items = []
    total = 0
    for i, path in enumerate(files, 1):
        rel = path.relative_to(root).as_posix()
        raw = path.read_bytes()
        total += len(raw)
        blob = req("POST", f"{API}/repos/{args.repo}/git/blobs", token, {
            "content": base64.b64encode(raw).decode(),
            "encoding": "base64",
        })
        tree_items.append({
            "path": rel,
            "mode": "100755" if os.access(path, os.X_OK) and path.suffix in (".sh", ".py") else "100644",
            "type": "blob",
            "sha": blob["sha"],
        })
        if i % 20 == 0 or i == len(files):
            print(f"  blob {i}/{len(files)}  ({total/1048576:.1f} MB)")

    # 2) tree
    tree_payload = {"tree": tree_items}
    if base_tree:
        tree_payload["base_tree"] = base_tree
    tree = req("POST", f"{API}/repos/{args.repo}/git/trees", token, tree_payload)
    print(f"tree: {tree['sha']}")

    # 3) commit（有父提交就接上，便于以后增量）
    parents = []
    try:
        ref = req("GET", f"{API}/repos/{args.repo}/git/ref/heads/{args.branch}", token)
        parents = [ref["object"]["sha"]]
        print(f"接到已有提交 {ref['object']['sha'][:8]}")
    except RuntimeError:
        print("分支还不存在，创建首个提交")

    msg = args.message or f"chore: 同步 {len(files)} 个文件"
    commit = req("POST", f"{API}/repos/{args.repo}/git/commits", token, {
        "message": msg,
        "tree": tree["sha"],
        "parents": parents,
    })
    print(f"commit: {commit['sha']}")

    # 4) 更新 / 创建 ref
    if parents:
        req("PATCH", f"{API}/repos/{args.repo}/git/refs/heads/{args.branch}", token, {
            "sha": commit["sha"], "force": False,
        })
    else:
        req("POST", f"{API}/repos/{args.repo}/git/refs", token, {
            "ref": f"refs/heads/{args.branch}", "sha": commit["sha"],
        })
    print(f"[ok] https://github.com/{args.repo}/tree/{args.branch}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
