#!/usr/bin/env python3
"""Xuất dữ liệu cho bản web (towel_web/): model ZIPA, bảng fbank, từ điển CTC, kho từ.
Chạy từ thư mục gốc dự án (cần .venv của app.py):
    V2I_MODEL=zipa .venv/bin/python towel_web/tools/export_web.py

Tạo ra (trong towel_web/):
  model/model.int8.onnx, model/tokens.txt     ZIPA small (anyspeech/zipa-small-crctc-300k, CC BY 4.0)
  data/fbank.bin     float32: cửa sổ povey (400) + ma trận mel (257 × 80), lấy thẳng từ lhotse
  data/lex.bin       từ điển CTC của ZIPA (LEX_ZIPA ở app.py) dạng nhị phân, xem lex_bin()
  data/lex.json      token -> lớp âm, để tính _class_logp bằng tra bảng
  data/words.json    {w: [từ...], z: [zipf...]} theo thứ tự WORD_LIST (để xếp hạng từ đích)
  data/pool_<dải>.json  từ để chơi theo dải zipf: easy (>= 5), mid (4–5), hard (3–4). Mức dễ = easy,
                     trung bình = easy + mid (zipf >= 4, như --level mid), khó = hard. Chỉ từ có bản ghi giọng Mỹ
                     trong data/audio_us.json (build_audio.py); mỗi từ: IPA, âm, nghĩa, khó/dễ, đường dẫn mp3.
"""
import json
import os
import shutil
import struct
import sys
import unicodedata

os.environ.setdefault("V2I_MODEL", "zipa")
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WEB = os.path.join(ROOT, "towel_web")
sys.path.insert(0, ROOT)

import numpy as np  # noqa: E402

import app  # noqa: E402
import ipa_us  # noqa: E402

BANDS = {"easy": (5.0, 99.0), "mid": (4.0, 5.0), "hard": (3.0, 4.0)}


def out(*p):
    path = os.path.join(WEB, *p)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return path


def copy_model():
    for f in (app.ZIPA_FILE, "tokens.txt"):
        src = os.path.join(app.ZIPA_DIR, f)
        if not os.path.exists(src):
            app.ZipaRecognizer()                     # tự tải model về models/
        shutil.copyfile(src, out("model", f))


def fbank_bin():
    from lhotse.features.kaldi.extractors import Fbank, FbankConfig
    fb = Fbank(FbankConfig(num_filters=80, dither=0.0, snip_edges=False))
    m = fb.extractor
    win = m.wav2win._window.detach().numpy().astype(np.float32)          # (400,)
    mel = m._fb.detach().numpy().astype(np.float32)                      # (257, 80)
    assert win.shape == (400,) and mel.shape == (257, 80), (win.shape, mel.shape)
    with open(out("data", "fbank.bin"), "wb") as f:
        f.write(win.tobytes() + mel.tobytes())


def lex_bin():
    """Header: 'LEX1', N (uint32), nc (uint32). Rồi ln[N] uint8, owner[N] uint16, variant[N] uint8,
    U nối liền (tổng ln) uint8 — id lớp âm 0..nc-1 (JS cộng 1, cột 0 là blank)."""
    lx = app.LEX_ZIPA
    lx._build()
    N = len(lx.ln)
    assert lx.ln.max() < 256 and len(lx.ids) < 255 and lx.owner.max() < 65536 and lx.variant.max() < 256
    flat = np.concatenate([lx.U[i, :lx.ln[i]] for i in range(N)]).astype(np.uint8)
    with open(out("data", "lex.bin"), "wb") as f:
        f.write(b"LEX1" + struct.pack("<II", N, len(lx.ids)))
        f.write(lx.ln.astype(np.uint8).tobytes())
        f.write(lx.owner.astype(np.uint16).tobytes())
        f.write(lx.variant.astype(np.uint8).tobytes())
        f.write(flat.tobytes())
    # token -> lớp âm, đúng như Lexicon._class_logp
    rec = app.ZipaRecognizer()
    pairs, blank = [], []
    for i, tok in sorted(rec.vocab.items()):
        if i == 0:
            continue
        if tok in lx.blank:
            blank.append(i)
        base = "".join(ch for ch in unicodedata.normalize("NFD", tok) if ch not in app._STRIP)
        for c, k in lx.ids.items():
            if base in lx.classes[c]:
                pairs.append([i, k + 1])
    vocab = [rec.vocab.get(i, "") for i in range(max(rec.vocab) + 1)]
    skip = sorted(rec.skip)
    with open(out("data", "lex.json"), "w", encoding="utf-8") as f:
        json.dump({"nc": len(lx.ids), "blank": blank, "pairs": pairs, "vocab": vocab, "skip": skip,
                   "keep": app.LEX_KEEP, "floor": app.LEX_FLOOR, "prior": app.WORD_PRIOR}, f, ensure_ascii=False)
    return N


def words_json():
    with open(out("data", "words.json"), "w", encoding="utf-8") as f:
        json.dump({"w": app.WORD_LIST, "z": [round(app.WORDS[w]["zipf"], 4) for w in app.WORD_LIST]}, f,
                  ensure_ascii=False, separators=(",", ":"))


def pool_json():
    if not app.AUDIO_US:
        sys.exit("Chưa có data/audio_us.json: chạy `python3 build_audio.py` trước.")
    sizes = {}
    old = out("data", "pool.json")
    if os.path.exists(old):
        os.remove(old)                               # bản cũ (chỉ mức mid)
    for band, (lo, hi) in BANDS.items():
        pool = [{"w": w, "ipa": e["ipa"], "ph": e["ph"], "vi": e["vi"], "hard": app.is_hard(w), "a": app.AUDIO_US[w]}
                for w, e in app.WORDS.items() if lo <= e["zipf"] < hi and len(w) >= 3 and w in app.AUDIO_US]
        with open(out("data", f"pool_{band}.json"), "w", encoding="utf-8") as f:
            json.dump(pool, f, ensure_ascii=False, separators=(",", ":"))
        sizes[band] = len(pool)
    return sizes


if __name__ == "__main__":
    copy_model()
    fbank_bin()
    n = lex_bin()
    words_json()
    sizes = pool_json()
    print(f"model, fbank, lex ({n} cách đọc), words ({len(app.WORD_LIST)}), pool {sizes}")
    for f in sorted(os.listdir(os.path.join(WEB, "data"))) + ["../model/" + x for x in sorted(os.listdir(os.path.join(WEB, "model")))]:
        p = os.path.join(WEB, "data", f)
        print(f"  {f:28s} {os.path.getsize(p) / 1e6:7.2f} MB")
