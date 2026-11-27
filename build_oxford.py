#!/usr/bin/env python3
"""Cấp độ, audio và nghĩa từ bộ Oxford 5000 của english_dictionary: data/oxford_us.json =
{từ: {"level": "A1".."C1", "a": link mp3 giọng Mỹ, "vi": nghĩa ngắn}}. Chỉ ghi các từ có trong words_v4.json
(cần phiên âm CMUdict ở đó để chấm).

    python3 build_oxford.py [đường dẫn oxford5000.json]      # mặc định ../english_dictionary/data/oxford5000.json

Một từ nhiều từ loại: lấy cấp độ thấp nhất, audio của mục ở cấp đó. "vi" để trống (app giữ nghĩa cũ trong
words_v4.json) khi có từ loại ở cấp thấp nhất chưa có nghĩa tiếng Việt, vd giới từ, đại từ.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "english_dictionary", "data", "oxford5000.json")
OUT = os.path.join(HERE, "data", "oxford_us.json")
CEFR = ("A1", "A2", "B1", "B2", "C1")
POS = {"noun": "dt", "verb": "đgt", "adjective": "tt", "adverb": "pht"}


def clip(text: str, limit: int = 40) -> str:
    """Nghĩa ngắn: tới dấu ';' đầu tiên, còn dài thì bỏ bớt các ý sau dấu ','."""
    text = text.split(";")[0].strip()
    while len(text) > limit and "," in text:
        text = text.rsplit(",", 1)[0].strip()
    return text


def overlay(entries: list[dict]) -> dict | None:
    """Các mục (mỗi từ loại 1 mục) của một từ -> {level, a, vi}; None nếu không mục nào có cấp độ."""
    graded = sorted((e for e in entries if e["level"] in CEFR), key=lambda e: CEFR.index(e["level"]))
    if not graded:
        return None
    level = graded[0]["level"]
    audio = next((e["audio"] for e in graded + entries if e["audio"]), "")
    vi = ""
    if all(e["vi"] for e in graded if e["level"] == level):
        vi = " | ".join([f"({POS[e['type']]}) {clip(e['vi'][0])}" for e in graded if e["vi"] and e["type"] in POS][:2])
    return {"level": level, "a": audio, "vi": vi}


def main():
    with open(SRC, encoding="utf-8") as f:
        entries = json.load(f)
    with open(os.path.join(HERE, "words_v4.json"), encoding="utf-8") as f:
        words = json.load(f)
    by_word: dict[str, list] = {}
    for e in entries:
        by_word.setdefault(e["word"].lower(), []).append(e)
    out, missing, ungraded = {}, [], []
    for w, es in sorted(by_word.items()):
        es = [e for e in es if e["word"] == w] or es         # 'may' không lẫn với tháng 'May'
        if w not in words:
            missing.append(w)
            continue
        o = overlay(es)
        if o is None:
            ungraded.append(w)
            continue
        out[w] = o
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("{\n" + ",\n".join(f"{json.dumps(w)}:{json.dumps(o, ensure_ascii=False, separators=(',', ':'))}"
                                   for w, o in out.items()) + "\n}\n")
    print(f"{len(out)}/{len(by_word)} từ -> {OUT} ({os.path.getsize(OUT) / 1e6:.2f} MB)")
    print(f"  bỏ {len(missing)} từ không có trong words_v4: {', '.join(missing)}")
    print(f"  bỏ {len(ungraded)} từ không có cấp độ: {', '.join(ungraded)}")
    play = {w: o for w, o in out.items() if len(w) >= 3}
    for lv in CEFR:
        pool = [o for o in play.values() if o["level"] == lv]
        print(f"  {lv}: {len(pool)} từ chơi được, {sum(bool(o['a']) for o in pool)} có audio,"
              f" {sum(not o['vi'] for o in pool)} dùng nghĩa cũ")


if __name__ == "__main__":
    main()
