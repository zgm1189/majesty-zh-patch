#!/usr/bin/env python3
"""中文翻译总表：合并各分册。键名对应 translate.dat 里的 `key_en` 条目。"""

from __future__ import annotations

from zh_entities import ZH as _ENT
from zh_help import ZH as _HELP
from zh_story import ZH as _STORY
from zh_ui import ZH as _UI

ZH: dict[str, str] = {**_UI, **_ENT, **_HELP, **_STORY}

if __name__ == "__main__":
    import sys

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(f"entries: {len(ZH)}")
    chars = {c for v in ZH.values() for c in v if not c.isascii() and c not in "\n^"}
    print(f"distinct non-ascii chars: {len(chars)}")
    print(f"total chars: {sum(len(v) for v in ZH.values())}")
