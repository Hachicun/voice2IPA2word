#!/usr/bin/env python3
"""Kết quả chuẩn (Python, chỉ ZIPA) trên các bản ghi đã lưu, để so với bản JS (tools/check_core.js).
    V2I_MODEL=zipa .venv/bin/python towel_web/tools/ref_dump.py [số bản ghi, mặc định 24] [thư mục ra]
Mỗi bản ghi: <n>.pcm (float32, đã đệm 0.5 s 2 đầu), <n>.fbank, <n>.logp (float32) và ref.json."""
import glob
import json
import os
import sys

os.environ["V2I_MODEL"] = "zipa"
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

import numpy as np  # noqa: E402
import torch  # noqa: E402

import app  # noqa: E402
import ipa_us  # noqa: E402


def takes(limit: int):
    seen, out = set(), []
    for log in sorted(glob.glob(os.path.join(ROOT, "logs", "*.log")), reverse=True):
        for line in open(log, encoding="utf-8"):
            try:
                e = json.loads(line)
            except ValueError:
                continue
            f, t = e.get("file"), e.get("target")
            if e.get("event") != "take" or not f or t not in app.WORDS or "score" not in e:
                continue
            path = os.path.join(ROOT, f)
            if os.path.exists(path) and path not in seen:
                seen.add(path)
                out.append((path, t))
            if len(out) >= limit:
                return out
    return out


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 24
    dst = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "towel_web", "tools", "ref")
    os.makedirs(dst, exist_ok=True)
    rec = app.load_model()
    assert isinstance(rec, app.ZipaRecognizer)
    refs = []
    for n, (path, target) in enumerate(takes(limit)):
        audio = app.pad_audio(app.read_wav(path))
        wav = torch.from_numpy(audio.astype(np.float32)).unsqueeze(0)
        feats = rec.fbank.extract_batch([wav], sampling_rate=app.SR)[0].numpy().astype(np.float32)
        raw = rec(audio)
        logp = rec.evidence[0][1]                                # log softmax (đã chuẩn hoá) [T, V]
        heard = [p for p, _ in ipa_us.from_model(raw)]
        r = {"n": n, "file": os.path.relpath(path, ROOT), "target": target, "frames": int(feats.shape[0]),
             "raw": [[p, round(c, 4)] for p, c in raw], "heard": heard}
        if heard:
            sim, k, mine, *_ = app.score_against(heard, target)
            total, _ = app.lex_totals(rec.evidence)
            r.update({"sim": round(sim, 4), "k": k, "mine": mine,
                      "rank": int((total > total[app.WORD_INDEX[target]]).sum()) + 1,
                      "heard_as": app.WORD_LIST[int(total.argmax())],
                      "top5": [app.WORD_LIST[i] for i in np.argsort(-total)[:5]]})
        audio.astype(np.float32).tofile(os.path.join(dst, f"{n}.pcm"))
        feats.tofile(os.path.join(dst, f"{n}.fbank"))
        logp.astype(np.float32).tofile(os.path.join(dst, f"{n}.logp"))
        refs.append(r)
        print(n, target, r.get("sim"), r.get("rank"), r.get("heard_as"))
    with open(os.path.join(dst, "ref.json"), "w", encoding="utf-8") as f:
        json.dump(refs, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
