"""Parse Marmalade ICF text table (assets/translate.dat).

Format: sequence of records, each = 2-byte big-endian length + length bytes of text.
No separators. Text entries look like "KEY: value" or bare markers like "_eop_: 1".
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "extracted" / "assets" / "translate.dat"
OUT = ROOT / "analysis"

data = SRC.read_bytes()
records: list[str] = []
raw_records: list[bytes] = []
i = 0
n = len(data)
truncated = False
while i < n:
    if i + 2 > n:
        truncated = True
        break
    ln = int.from_bytes(data[i : i + 2], "big")
    i += 2
    if ln == 0:
        records.append("")
        raw_records.append(b"")
        continue
    chunk = data[i : i + ln]
    if len(chunk) < ln:
        truncated = True
        records.append(f"<<TRUNCATED at {i - 2}, declared={ln}, got={len(chunk)}>>")
        raw_records.append(chunk)
        break
    i += ln
    raw_records.append(chunk)
    try:
        records.append(chunk.decode("utf-8"))
    except UnicodeDecodeError:
        records.append(chunk.decode("latin-1"))

print(f"file size      : {n}")
print(f"records        : {len(records)}")
print(f"consumed bytes : {i}/{n}  truncated={truncated}")

pairs: list[tuple[str, str]] = []
bare: list[str] = []
for text in records:
    if ": " in text:
        key, value = text.split(": ", 1)
        pairs.append((key, value))
    elif text.endswith(":"):
        pairs.append((text[:-1], ""))
    else:
        bare.append(text)

lang_counts: dict[str, int] = {}
for key, _ in pairs:
    m = re.search(r"_([a-z]{2})$", key)
    if m:
        lang_counts[m.group(1)] = lang_counts.get(m.group(1), 0) + 1

base_keys = {re.sub(r"_[a-z]{2}$", "", k) for k, _ in pairs}
prefixes: dict[str, int] = {}
for key, _ in pairs:
    m = re.match(r"^([A-Za-z_]+?)(?=[A-Z0-9]|_[a-z]{2}$)", key)
    p = (m.group(1) if m else key)[:14]
    prefixes[p] = prefixes.get(p, 0) + 1

print(f"key:value pairs: {len(pairs)}")
print(f"bare entries   : {len(bare)}  {bare[:12]}")
print(f"language tags  : {sorted(lang_counts.items(), key=lambda x: -x[1])}")
print(f"distinct basenames: {len(base_keys)}")

OUT.mkdir(parents=True, exist_ok=True)
(OUT / "translate_all.txt").write_text(
    "\n".join(f"{k}: {v}" for k, v in pairs), encoding="utf-8"
)
(OUT / "translate_raw.txt").write_text("\n".join(records), encoding="utf-8")
print("wrote analysis/translate_all.txt and analysis/translate_raw.txt")
