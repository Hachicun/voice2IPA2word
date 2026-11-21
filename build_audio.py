#!/usr/bin/env python3
"""Bảng audio giọng Mỹ: data/audio_us.json = {từ: đường_dẫn_mp3 trên Wikimedia Commons}.
Cách làm giống ~/english_dictionary/tools/build_audio.py: đọc bản dump Wiktionary tiếng Anh của kaikki.org (có link
mp3 của Wikimedia Commons), không gọi API nào. Link đầy đủ = https://upload.wikimedia.org/wikipedia/commons/ + đường dẫn.
Ưu tiên file En-us-<từ>.ogg (kiểu từ điển), rồi tới các bản ghi khác gắn nhãn giọng Mỹ (Lingua Libre…).

    python3 build_audio.py [đường dẫn kaikki.org-dictionary-English.jsonl.gz]

Mặc định dùng bản dump đã tải ở ~/english_dictionary/raw/kaikki/ (tải mới: https://kaikki.org/dictionary/English/,
file kaikki.org-dictionary-English.jsonl.gz, ~530 MB). Chỉ ghi các từ có trong words_v4.json.
"""
import gzip
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser(
    "~/english_dictionary/raw/kaikki/kaikki.org-dictionary-English.jsonl.gz")
OUT = os.path.join(HERE, "data", "audio_us.json")
BASE = "https://upload.wikimedia.org/wikipedia/commons/"
US = {"US", "General-American", "General American"}


def main():
    with open(os.path.join(HERE, "words_v4.json"), encoding="utf-8") as f:
        words = json.load(f)
    best = {}          # từ -> (ưu tiên, đường dẫn); 0 = En-us-*, 1 = bản ghi giọng Mỹ khác
    with gzip.open(SRC, "rt", encoding="utf-8") as f:
        for line in f:
            if '"mp3_url"' not in line:
                continue
            e = json.loads(line)
            w = e.get("word", "").lower()
            if w not in words:
                continue
            for s in e.get("sounds", []):
                url, name = s.get("mp3_url", ""), s.get("audio", "")
                tags = set(s.get("tags", [])) | set(s.get("raw_tags", []))
                if not url.startswith(BASE) or not (tags & US or name.lower().startswith("en-us-")):
                    continue
                cand = (0 if name.lower().startswith("en-us-") else 1, url[len(BASE):])
                if w not in best or cand[0] < best[w][0]:
                    best[w] = cand
    out = {w: p for w, (_, p) in sorted(best.items())}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    print(f"{len(out)}/{len(words)} từ có audio giọng Mỹ -> {OUT} ({os.path.getsize(OUT) / 1e6:.1f} MB)")
    for name, lo, hi in (("easy", 5, 99), ("mid", 4, 99), ("hard", 3, 4)):
        pool = [w for w, e in words.items() if lo <= e["zipf"] < hi and len(w) >= 3]
        print(f"  mức {name}: {sum(w in out for w in pool)}/{len(pool)} từ có audio")


if __name__ == "__main__":
    main()
