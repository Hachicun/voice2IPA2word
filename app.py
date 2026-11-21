"""
Giữ SPACE để ghi âm 1 từ tiếng Anh, nhả ra -> phát lại bản ghi + IPA -> từ -> nghĩa tiếng Việt.
Nghĩa lấy offline từ từ điển Anh-Việt OVDP (thư mục data/).
Chạy hoàn toàn trên terminal. IPA (cả của model lẫn từ điển) ghi theo Anh Mỹ - Cambridge Dictionary, xem ipa_us.py.

Cài đặt (1 lần, macOS):
    brew install espeak-ng
    uv venv --python 3.12 && source .venv/bin/activate
    uv pip install -r requirements.txt

Chạy:
    python app.py
    -> Giữ SPACE để nói, nhả ra để dừng. Esc hoặc Ctrl+C để thoát.
    Mỗi lần ghi được lưu ở recordings/<phiên>/NN_<từ>.wav, log ở logs/<phiên>.log.

Chế độ đoán từ: máy đọc 1 từ ngẫu nhiên (không hiện chữ), bạn nói lại, chấm % giống IPA của từ đó.
    python app.py --guess                       # mức mid: từ thông dụng (zipf >= 4)
    python app.py --guess --level easy          # easy (zipf >= 5) | mid | hard (zipf 3-4) | all
    python app.py --fetch-audio --level mid     # tải sẵn bản ghi của 1 mức để chơi offline (Ctrl+C dừng, chạy lại làm tiếp)
    -> giữ SPACE nói lại · R nghe lại · S nghe chậm · A/Enter xem đáp án · N từ mới · Esc thoát
       M: giọng máy đọc đúng các âm model nghe được từ bạn, rồi phát bản ghi chuẩn (so sánh).
          Dùng AVSpeechSynthesizer của macOS qua ipa_say.swift, tự biên dịch lần đầu (cần swiftc).
    Từ mẫu: bản ghi giọng người (Mỹ) của Wiktionary trên Wikimedia Commons. Bảng {từ: file mp3} data/audio_us.json
    dựng sẵn từ bản dump Wiktionary của kaikki.org (python3 build_audio.py, như ~/english_dictionary), không hỏi
    API nào; mỗi file tải 1 lần vào data/audio/ (lần sau offline). Chỉ chơi từ có bản ghi; tải lỗi (mất mạng,
    bị chặn) thì giọng máy macOS đọc thay: giọng tốt nhất đã cài (Ava Premium...), đổi bằng V2I_VOICE="Tên giọng".
    Âm giống >= 90% hoặc model nhận ra đúng từ (chấm CTC, từ đích đứng đầu) = nói đúng, tự hiện đáp án.
    Tắt bộ gõ tiếng Việt (Telex/VNI) khi chơi, kẻo phím S/R/A bị nuốt. Xanh = âm đúng, vàng = gần đúng, đỏ = sai/thừa, _ = thiếu âm.

Game leo tháp: như chế độ đoán từ, kèm nhân vật leo tháp vẽ ngay trong terminal (tower.py).
    python app.py --game                        # --level easy | mid | hard | all như --guess
    -> bắt đầu ở tầng 50, lên tầng 100 thắng, rơi về 0 (dung nham) thua. Đúng ngay lần đầu +2 tầng, đúng sau
       vài lần +1, gần đúng (60-89%) đứng yên, sai rơi 1 tầng. Xem đáp án (A) trước khi nói đúng thì từ đó không
       được lên tầng. Phím như --guess; hết ván bấm N chơi lại. Tắt tiếng hiệu ứng: V2I_SFX=0.
       Bản ghi lách tách: V2I_FREEZE=1 (đứng hình lúc ghi).
       Nên dùng Ghostty hoặc iTerm2 (vẽ cả khung một lượt), cửa sổ tối thiểu 64×16. Xem thử không cần micro:
       python3 tower.py

Chế độ săn từ theo âm, dạng THẮP CHÒM SAO (chơi 1 mình, vẽ bằng stars.py): chọn 1 hay vài âm (nguyên âm, phụ âm),
mỗi từ chứa đủ các âm đó thắp 1 ngôi sao; đủ sao thì nối thành chòm sao (nhà, cá, thuyền, mèo, diều) và chòm
sống dậy, rồi bầu trời trôi sang chòm kế. Không tính giờ, nói sai không mất gì.
    python app.py --hunt                        # hỏi chọn âm (số hoặc ký hiệu IPA), từ gợi ý mức mid
    python app.py --hunt --sounds "æ t"         # chọn sẵn âm; --level easy | mid | hard | all như --guess
    -> giữ SPACE nói 1 từ. Model nhận ra từ trong từ điển; hợp lệ khi chứa đủ các âm và chưa thắp.
       Tự nghĩ ra từ: sao sáng ✦, điểm = 10 × số âm mục tiêu trong từ, nhân thêm khi từ ít gặp / dài; từ khó
       (zipf < 4 hoặc >= 7 âm) thành sao vàng. Phát âm >= 90% thêm 5 điểm.
       Bí: G = gợi ý 1 từ (bản ghi người thật nếu có, không thì giọng máy macOS), đọc theo giống >= 80%:
       sao mờ ✧, 1/3 điểm. G lần nữa: từ gợi ý khác · N bỏ gợi ý · R nghe lại · S nghe chậm · L từ đã thắp.
       Xem thử không cần micro: python3 stars.py

Chạy lại trên bản ghi đã lưu (so sánh các lần):
    python app.py recordings/<phiên>/*.wav

Model nhận âm (mặc định: Koel + ZIPA cộng điểm; không tải được Koel thì tự dùng ZIPA):
    python app.py --model koel          # KoelLabs/xlsr-english-01 (~1.2 GB) + ZIPA. Model Koel bị khoá:
                                        # xin quyền ở trang model trên Hugging Face rồi `hf auth login` (1 lần)
    python app.py --model zipa          # chỉ ZIPA small (71 MB, tự tải vào models/), nhanh hơn ~6 lần
    python app.py --model xlsr          # model cũ wav2vec2-xlsr-53 (~1.2 GB)

Cách chọn từ (Koel, ZIPA): chấm từng từ trong từ điển bằng xác suất CTC của model + độ phổ biến của từ
(xem mục 3b, hằng số WORD_PRIOR). Quay về cách cũ (giải mã rồi so chuỗi âm) để so sánh:
    V2I_MATCH=edit python app.py recordings/<phiên>/*.wav

Quyền macOS (lần đầu):
    System Settings > Privacy & Security > Microphone      -> bật cho app Terminal/iTerm
    System Settings > Privacy & Security > Input Monitoring -> bật cho app Terminal/iTerm
    (cần để bắt sự kiện nhả phím; bật xong phải mở lại terminal)
"""
import json
import os
import queue
import re
import sys
import threading

if os.name == "nt":
    _lib = r"C:\Program Files\eSpeak NG\libespeak-ng.dll"
elif sys.platform == "darwin":
    _lib = "/opt/homebrew/lib/libespeak-ng.dylib"
else:
    _lib = ""
if _lib and os.path.exists(_lib):
    os.environ.setdefault("PHONEMIZER_ESPEAK_LIBRARY", _lib)

import numpy as np
from phonemizer import phonemize
from phonemizer.separator import Separator
from rapidfuzz.distance import Levenshtein
from wordfreq import top_n_list, zipf_frequency

import ipa_us

HERE = os.path.dirname(os.path.abspath(__file__))
# Model nhận âm: "koel" (mặc định: Koel + ZIPA), "zipa" hoặc "xlsr". Đổi bằng --model hoặc biến môi trường V2I_MODEL.
# Đo trên 360 bản ghi giọng máy (60 từ x 6 giọng): ZIPA đoán đúng ngay 66% vs XLSR 53%, nhanh ~8 lần.
MODEL_KIND = os.environ.get("V2I_MODEL", "koel")
ZIPA_REPO = "anyspeech/zipa-small-crctc-300k"            # 64M tham số, CC BY 4.0
ZIPA_DIR = os.path.join(HERE, "models", "zipa-small-crctc-300k")
ZIPA_FILE = "model.int8.onnx"                             # 71 MB, chính xác ngang bản fp32
XLSR_MODEL = "facebook/wav2vec2-xlsr-53-espeak-cv-ft"     # model cũ, ~1.2 GB
KOEL_MODEL = "KoelLabs/xlsr-english-01"                   # wav2vec2 chuyên tiếng Anh, ~1.2 GB, bị khoá (cần xin quyền)
# Nguồn nghĩa chính: Wiktionary tiếng Việt (kaikki.org, CC BY-SA, cập nhật hằng tuần, có từ mới như
# selfie, smartphone). Từ nào Wiktionary chưa có thì lấy từ OVDP (StarDict, cũ hơn).
WIKTIONARY = os.path.join(HERE, "data", "vi-extract.jsonl.gz")
WIKTIONARY_URL = "https://kaikki.org/dictionary/downloads/vi/vi-extract.jsonl.gz"
STARDICT = os.path.join(HERE, "data", "star_anhviet")   # từ điển Anh-Việt (OVDP), dự phòng
WORDS_FILE = os.path.join(HERE, "words_v4.json")       # cache: từ -> IPA (Cambridge US), nghĩa, độ phổ biến
N_WORDS = 40000          # số từ đưa vào từ điển
SCAN_WORDS = 150000      # số từ thông dụng (wordfreq) được xét
SR = 16000
MIN_SECONDS = 0.3
# Từ 1-2 chữ cái thật sự (các từ ngắn khác thường là viết tắt / rác)
SHORT_OK = set("a i ad ah am an as at be by do go he hi if in is it me my no of oh "
               "ok on or ox so to up us we".split())
POS_ABBR = {"danh từ": "dt", "tính từ": "tt", "động từ": "đgt", "ngoại động từ": "đgt",
            "nội động từ": "đgt", "phó từ": "pht", "thán từ": "tht", "giới từ": "gt",
            "đại từ": "đt", "liên từ": "lt", "mạo từ": "mt", "trợ động từ": "đgt"}
WIKT_POS = {"noun": "dt", "verb": "đgt", "adj": "tt", "adv": "pht", "pron": "đt", "prep": "gt",
            "conj": "lt", "intj": "tht", "article": "mt", "det": "đt", "num": "st", "name": "dt riêng"}


# ---------- 1. Từ điển Anh-Việt (StarDict) ----------
def load_stardict(base: str) -> dict[str, str]:
    """Đọc file StarDict (.idx + .dict.dz) -> {từ thường: nội dung mục từ}."""
    import gzip
    import struct
    with open(base + ".idx", "rb") as f:
        raw = f.read()
    with gzip.open(base + ".dict.dz") as f:
        data = f.read()
    out, i = {}, 0
    while i < len(raw):
        j = raw.index(b"\0", i)
        word = raw[i:j].decode("utf-8", "replace").strip()
        off, size = struct.unpack(">II", raw[j + 1:j + 9])
        i = j + 9
        key = word.lower()
        if key.isalpha() and (key not in out or word == key):   # ưu tiên mục viết thường
            out[key] = data[off:off + size].decode("utf-8", "replace")
    return out


def _clip(text: str, limit: int = 35) -> str:
    """Cắt nghĩa dài ở dấu ';' hoặc ',' gần nhất trước giới hạn."""
    text = " ".join(text.split()).split(";")[0].strip()
    if len(text) > limit and ":" in text:                  # 'liên mạng: một hệ thống...' -> 'liên mạng'
        text = text.split(":")[0].strip()
    while len(text) > limit and "," in text:
        text = text.rsplit(",", 1)[0].strip()
    return text if len(text) <= limit + 15 else text[:limit].rsplit(" ", 1)[0] + "…"


# Chữ rác do lỗi mã hoá trong file OVDP gốc, vd 'uây khyếm mẹ' (mom), 'nhuây khót vốn chung' (kitty)
_GARBLED = re.compile(r"^n?h?uây(\s+(khyếm|oác|khót))?\s*", re.I)
_LABELS = re.compile(r"^(\s*\([^()]*\)\s*[,;]?)+")  # nhãn đầu dòng: (từ Mỹ,nghĩa Mỹ); (thông tục)...


def _sense(line: str) -> str:
    """Một dòng nghĩa -> nghĩa đã rút gọn; '' nếu dòng chỉ có nhãn hoặc bị cụt trong nguồn
    (vd '(giải phẫu) v', '(xem) a')."""
    core = _LABELS.sub("", _GARBLED.sub("", line.strip(" ,;")))
    core = _LABELS.sub("", core).strip(" ,;")
    if len(core) < 2 or core.startswith("(xem)") or "['" in core:
        return ""
    return _clip(core)


def short_meaning(entry: str, max_pos: int = 2, max_each: int = 1):
    """Rút gọn mục từ -> (nghĩa chung, nghĩa chuyên ngành, là_viết_tắt)."""
    groups, tech, pos, in_general = [], [], "", True
    for n, line in enumerate(entry.split("\n")):
        line = line.strip()
        if line.startswith("@"):
            if n > 0:
                in_general = False          # hết phần nghĩa chung
            continue
        if in_general and line.startswith("*"):
            pos = line.strip("* ").strip()
            groups.append((POS_ABBR.get(pos, pos if len(pos) <= 20 else ""), []))
        elif in_general and line.startswith("- "):
            if not groups:
                groups.append(("", []))
            sense = _sense(line[2:])
            if sense and len(groups[-1][1]) < max_each:
                groups[-1][1].append(sense)
        elif not in_general and line.startswith("-") and len(tech) < max_each:
            sense = _sense(line[1:])
            if sense:
                tech.append(sense)
    groups = [(p, m) for p, m in groups if m][:max_pos]
    general = " | ".join((f"({p}) " if p else "") + "; ".join(m) for p, m in groups)
    low = entry.lower()
    abbr = "viết tắt" in low or "vt của" in low
    return general, "; ".join(tech), abbr


def lemma_candidates(w: str) -> list[str]:
    """Đoán từ gốc của dạng chia: years->year, played->play, running->run..."""
    c = []
    for suf, reps in (("ies", ["y"]), ("ied", ["y"]), ("es", [""]), ("s", [""]),
                      ("ed", ["", "e"]), ("ing", ["", "e"]), ("er", ["", "e"]),
                      ("est", ["", "e"]), ("ly", [""])):
        if w.endswith(suf) and len(w) - len(suf) >= 2:
            stem = w[: -len(suf)]
            c += [stem + r for r in reps]
            if len(stem) > 2 and stem[-1] == stem[-2]:      # running -> run
                c.append(stem[:-1])
    return c


# ---------- 1b. Wiktionary tiếng Việt (kaikki.org) ----------
_SKIP_TAGS = {"form-of", "alt-of", "no-gloss", "obsolete", "archaic", "error-lua-exec"}
# Nghĩa thật ra chỉ trỏ sang từ gốc: 'Xem be', '(viết tắt) của bicycle...', 'Quá khứ của do',
# 'Ngôi 3 số nhiều thời hiện tại của be' -> lấy nghĩa của từ gốc
_FORM_GLOSS = re.compile(r"^xem\s+([a-z]+)\.?$"
                         r"|^(?:\(viết tắt\)\s*)?của\s+([a-z]+)\b"
                         r"|\b(?:quá khứ|phân từ|số nhiều|so sánh|ngôi|dạng)\b[^.;]*?\bcủa\s+([a-z]+)\b", re.I)


def load_wiktionary(path: str) -> dict[str, dict]:
    """Đọc vi-extract.jsonl.gz -> {từ: {"senses": [(loại từ, nghĩa đầu)], "lemma": từ gốc|None,
    "abbr": chỉ là viết tắt}}. Chỉ lấy mục tiếng Anh."""
    import gzip
    if not os.path.exists(path):
        print(f"(Chưa có {os.path.basename(path)}: tải từ {WIKTIONARY_URL} vào thư mục data/"
              " để có nghĩa mới hơn; tạm dùng OVDP.)")
        return {}
    out: dict[str, dict] = {}
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            if '"lang_code": "en"' not in line:
                continue
            o = json.loads(line)
            w = o.get("word", "")
            if o.get("lang_code") != "en" or w != w.lower() or not w.isalpha():
                continue
            e = out.setdefault(w, {"senses": [], "lemma": None, "abbr": True})
            pos = o.get("pos", "")
            if pos not in ("abbrev", "character", "prefix", "suffix"):
                e["abbr"] = False
            for sense in o.get("senses", []):
                gloss = " ".join(sense.get("glosses", [])[-1:]).strip()
                tags = set(sense.get("tags", []))
                m = _FORM_GLOSS.search(gloss)
                if "form-of" in tags or "alt-of" in tags or m:
                    base = (sense.get("form_of") or sense.get("alt_of") or [{}])[0].get("word") \
                        or (next(g for g in m.groups() if g) if m else None)
                    if base and base != w and not e["lemma"]:
                        e["lemma"] = base.lower()
                    continue
                if not gloss or tags & _SKIP_TAGS:
                    continue
                if pos in ("abbrev", "character", "prefix", "suffix", "phrase", "proverb"):
                    continue
                e["senses"].append((WIKT_POS.get(pos, ""), gloss))
    return out


def _wikt_text(e: dict, max_pos: int = 2) -> str:
    """Nghĩa đầu tiên của tối đa 2 loại từ, vd '(dt) tiền, tiền tệ | (đgt) ...'."""
    seen, parts = set(), []
    for pos, gloss in e["senses"]:
        if pos in seen:
            continue
        seen.add(pos)
        sense = _sense(gloss.rstrip(". "))
        if re.fullmatch(r"[a-z]+", sense):          # '(pht) easily': chỉ trỏ sang từ tiếng Anh khác
            continue
        if len(sense) > 1 and not sense[1].isupper():
            sense = sense[0].lower() + sense[1:]          # 'Tiền, tiền tệ.' -> 'tiền, tiền tệ'
        if sense:
            parts.append((f"({pos}) " if pos else "") + sense)
        if len(parts) >= max_pos:
            break
    return " | ".join(parts)


# Sửa tay: mục bị hỏng trong OVDP gốc (chữ lỗi, nghĩa cụt) và vài từ rất thông dụng mà nghĩa đầu
# tiên trong Wiktionary ít gặp (lake = chất màu, be = đang). Ưu tiên cao nhất.
MEANING_FIX = {
    "be": "(đgt) thì, là, ở",
    "should": "(trợ đgt) nên, phải",
    "are": "[be] (đgt) thì, là, ở",
    "ceo": "(dt) tổng giám đốc",
    "would": "(trợ đgt) sẽ, muốn (quá khứ của will)",
    "cannot": "không thể",
    "easy": "(tt) dễ dàng, đơn giản | (pht) thoải mái, từ từ",
    "english": "(tt) (thuộc) Anh | (dt) tiếng Anh",
    "tv": "(dt) ti vi, truyền hình",
    "lake": "(dt) hồ",
    "mom": "(dt) mẹ (từ Mỹ)",
    "italian": "(tt) (thuộc) Ý | (dt) người Ý, tiếng Ý",
    "papa": "(dt) bố, ba",
    "grandma": "(dt) bà",
    "arse": "(dt) mông, đít (thô tục)",
    "minnie": "(dt) má, mẹ",
}


def _ovdp_meaning(w: str, vi: dict[str, str]) -> tuple[str, bool]:
    """(nghĩa từ OVDP, là_viết_tắt)."""
    if w in MEANING_FIX:
        return MEANING_FIX[w], False
    general, tech, abbr = short_meaning(vi[w]) if w in vi else ("", "", False)
    return general or tech, abbr


def make_meaning(w: str, vi: dict[str, str], wk: dict[str, dict]) -> tuple[str, str]:
    """(nghĩa ngắn, nguồn 'wikt'|'ovdp'); ('', '') nếu là viết tắt / không có trong cả hai từ điển."""
    if w in MEANING_FIX:
        return MEANING_FIX[w], "fix"
    e = wk.get(w)
    if e:
        text = _wikt_text(e)
        if text:
            return text, "wikt"
        lemma = e["lemma"]                      # Wiktionary ghi rõ là dạng chia: children -> child
        if lemma in MEANING_FIX:
            return f"[{lemma}] {MEANING_FIX[lemma]}", "fix"
        if lemma and lemma in wk and (text := _wikt_text(wk[lemma])):
            return f"[{lemma}] {text}", "wikt"
    ovdp, abbr = _ovdp_meaning(w, vi)
    if ovdp and not abbr:
        return ovdp, "ovdp"
    if (e and e["abbr"]) or abbr:
        return "", ""
    # dạng chia (children, went, years, played...) -> lấy nghĩa từ gốc
    bases = ([e["lemma"]] if e and e["lemma"] else []) + lemma_candidates(w)
    for base in bases:
        if base == w:
            continue
        if base in wk and (text := _wikt_text(wk[base])):
            return f"[{base}] {text}", "wikt"
        g, a = _ovdp_meaning(base, vi)
        if g and not a and not g.startswith("["):
            return f"[{base}] {g}", "ovdp"
    return "", ""


# ---------- 2. Danh sách từ: IPA + nghĩa (tạo 1 lần, lưu cache) ----------
def word_ipa(words: list[str]) -> dict[str, list]:
    """{từ: [cách đọc, ...]}, mỗi cách đọc là [(âm Cambridge, trọng âm)].
    Nguồn chính CMUdict (từ điển phát âm Mỹ); từ CMUdict không có (vd colour, organised) lấy từ espeak en-us."""
    import cmudict
    cmu = cmudict.dict()
    out, rest = {}, []
    for w in words:
        if w in cmu:
            out[w] = [ipa_us.from_arpabet(p) for p in cmu[w]]
        else:
            rest.append(w)
    esp = phonemize(rest, language="en-us", backend="espeak", with_stress=True,
                    separator=Separator(phone=" ", word="|"), strip=True, njobs=4)
    for w, i in zip(rest, esp):
        if i.strip() and "|" not in i:
            out[w] = [ipa_us.from_arpabet(ipa_us.espeak_to_arpabet(i.split()))]
    return {w: out[w] for w in words if w in out}


def build_words() -> dict[str, dict]:
    if os.path.exists(WORDS_FILE):
        with open(WORDS_FILE, encoding="utf-8") as f:
            return json.load(f)
    print("Đang tạo từ điển (chỉ lần đầu, ~1 phút)...")
    vi = load_stardict(STARDICT)
    wk = load_wiktionary(WIKTIONARY)
    words, meanings = [], {}
    for w in top_n_list("en", SCAN_WORDS):
        if not (w.isalpha() and w.isascii()) or (len(w) <= 2 and w not in SHORT_OK):
            continue
        meaning, src = make_meaning(w, vi, wk)
        if not meaning:
            continue                         # viết tắt / không có trong từ điển -> bỏ (fu, foo...)
        words.append(w)
        meanings[w] = (meaning, src)
        if len(words) >= N_WORDS:
            break
    d = {}
    for w, variants in word_ipa(words).items():
        d[w] = {"ipa": [ipa_us.to_ipa(s) for s in variants],     # vd ['ˈwɑː.t̬ɚ'] (Cambridge US)
                "ph": [ipa_us.phonemes(s) for s in variants],     # cùng thứ tự: để so khớp
                "vi": meanings[w][0], "src": meanings[w][1], "zipf": zipf_frequency(w, "en")}
    with open(WORDS_FILE, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)
    return d


WORDS = build_words()


# ---------- 3. Tra từ gần nhất theo IPA ----------
# Từ điển (CMUdict/espeak) và model (ZIPA/XLSR) đều được đổi về cùng bộ ký hiệu Cambridge US (ipa_us.py),
# rồi so khớp trên khoá chung ipa_us.key (bỏ dấu dài). Mỗi từ có thể có nhiều cách đọc (read, live, caught).
CANON = {w: [ipa_us.key(p) for p in e["ph"]] for w, e in WORDS.items()}


# Cặp âm gần nhau: thay âm này bằng âm kia chỉ bị trừ một phần điểm (khác hẳn = 1).
# Model và từ điển hay ghi cùng một âm bằng ký hiệu khác nhau (ZIPA 'a' = espeak 'ɑ' trong mom, father),
# và người học hay lẫn các cặp như i/ɪ, s/z.
_NEAR_GROUPS = (
    (0.0, "a ɑ"),                              # 'a' của ZIPA: /ɑː/ (mom, hot) hoặc /ʌ/ (cup, judge)
    (0.3, "a æ"),
    (0.2, "t ɾ|d ɾ"),                                               # t/d bật nhẹ kiểu Mỹ (water)
    (0.3, "a ʌ"),
    (0.1, "ɑ ɔ?"),                             # 'ɔ' của ZIPA: Mỹ caught /ɑː/ thường nghe thành 'ɔ'
    (0.4, "ɔ? oʊ|ɔ? ʊ|ɔ? ɔ|ɑ ɔ"),
    (0.4, "u ʌ|ʊ ʌ|ɑ ʌ|ɑ æ|æ e|e eɪ|i ɪ|ɪ e|ɪ eɪ|ɪ ə|u ʊ|ʊ oʊ|oʊ ɔ|ə ʌ|ə ɚ|ɚ ɝ|ɝ ə"),
    (0.4, "p b|t d|k ɡ|f v|s z|θ ð|ʃ ʒ|tʃ dʒ"),                     # chỉ khác hữu thanh / vô thanh
    (0.5, "θ t|ð d|θ s|ð z|θ f|n ŋ|m n|ʃ tʃ|ʒ dʒ|z ʒ|s ʃ|l r|w v"),
)
_SUB_COST = {}
for _cost, _pairs in _NEAR_GROUPS:
    for _pair in _pairs.split("|"):
        _x, _y = _pair.split()
        _SUB_COST[_x, _y] = _SUB_COST[_y, _x] = _cost


def phone_distance(a: list[str], b: list[str]) -> float:
    """Khoảng cách Levenshtein có trọng số: thêm/bớt 1 âm = 1, thay âm gần = 0-0.5."""
    prev = [float(j) for j in range(len(b) + 1)]
    for i, x in enumerate(a, 1):
        cur = [float(i)] + [0.0] * len(b)
        for j, y in enumerate(b, 1):
            sub = 0.0 if x == y else _SUB_COST.get((x, y), 1.0)
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + sub)
        prev = cur
    return prev[-1]


def align(a: list[str], b: list[str]) -> list[tuple[int | None, int | None]]:
    """Gióng hai dãy âm theo phone_distance: [(vị trí trong a, vị trí trong b)], None = thêm/bớt."""
    D = [[float(i + j) if i == 0 or j == 0 else 0.0 for j in range(len(b) + 1)] for i in range(len(a) + 1)]
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            sub = 0.0 if a[i - 1] == b[j - 1] else _SUB_COST.get((a[i - 1], b[j - 1]), 1.0)
            D[i][j] = min(D[i - 1][j] + 1, D[i][j - 1] + 1, D[i - 1][j - 1] + sub)
    out, i, j = [], len(a), len(b)
    while i or j:
        if i and j and D[i][j] == D[i - 1][j - 1] + (0.0 if a[i - 1] == b[j - 1]
                                                       else _SUB_COST.get((a[i - 1], b[j - 1]), 1.0)):
            i, j = i - 1, j - 1
            out.append((i, j))
        elif i and D[i][j] == D[i - 1][j] + 1:
            i -= 1
            out.append((i, None))
        else:
            j -= 1
            out.append((None, j))
    return out[::-1]


def find_words(phones: list[str], top: int = 3, shortlist: int = 500) -> list[tuple[str, float, int]]:
    """[(từ, % giống, cách đọc khớp nhất)] xếp theo độ giống IPA; độ phổ biến chỉ dùng khi giống bằng nhau.
    Lọc nhanh bằng Levenshtein thường, rồi chấm lại kỹ (có trọng số) nhóm đứng đầu."""
    nd = Levenshtein.normalized_distance
    rough = sorted(CANON, key=lambda w: min(nd(phones, r) for r in CANON[w]))[:shortlist]
    scored = []
    for w in rough:
        sim, k = max((1 - phone_distance(phones, r) / max(len(phones), len(r)), -k)
                     for k, r in enumerate(CANON[w]))
        scored.append((round(sim, 4), k == 0, WORDS[w]["zipf"], w, -k))   # bằng điểm: ưu tiên cách đọc chính
    scored.sort(reverse=True)
    return [(w, sim, k) for sim, _, _, w, k in scored[:top]]


# ---------- 3b. Chấm từng từ trong từ điển bằng CTC ----------
# Thay vì chốt một dãy âm (mỗi khung lấy âm xác suất cao nhất) rồi so chuỗi, ta tính cho từng từ
# xác suất model "nghe ra" đúng dãy âm của từ đó, dùng toàn bộ xác suất ở mọi khung. Nhờ vậy âm model
# không chắc (vd nguyên âm trong 'bad' chỉ 30%, thua blank nên bị mất khi giải mã) vẫn được tính điểm.
# Điểm của nhiều model được cộng lại (Koel + ZIPA sai ở những chỗ khác nhau).
# Đo "đoán đúng ngay / trong top 3" (WORD_PRIOR 0.75):
#   400 bản ghi người thật (Google Speech Commands, 10 từ)   98 từ đa dạng, giọng máy Samantha
#   ZIPA so chuỗi (cách cũ)   67% / 74%                       53% / 66%
#   ZIPA chấm CTC             83% / 90%                       56% / 72%
#   Koel chấm CTC             81% / 89%                       71% / 87%
#   Koel + ZIPA chấm CTC      86% / 93%                       73% / 87%
WORD_PRIOR = 0.75    # trọng số độ phổ biến của từ (zipf) cộng vào điểm; 0 = chỉ xét âm
LEX_KEEP = 4000      # số cách đọc được chấm kỹ sau bước lọc nhanh
LEX_FLOOR = -80.0    # điểm của từ bị loại ở bước lọc nhanh
_STRIP = "\u0303\u0325\u0329\u030dʰ"     # mũi hoá, vô thanh, âm tiết tính, bật hơi: không đổi lớp âm


def _ctc_best_path(E: np.ndarray, U: np.ndarray, ln: np.ndarray) -> np.ndarray:
    """Điểm (log xác suất) đường đi CTC tốt nhất của mọi dãy trong U cùng lúc."""
    N, L = U.shape
    NEG = np.float32(-1e9)
    same = np.zeros((N, L), bool)
    same[:, 1:] = U[:, 1:] == U[:, :-1]                   # 2 âm giống nhau liền kề phải cách bằng blank
    a_b = np.full((N, L + 1), NEG, np.float32)            # đang ở blank trước âm j
    a_u = np.full((N, L), NEG, np.float32)                # đang ở âm j
    a_b[:, 0] = E[0, 0]
    a_u[:, 0] = E[0, U[:, 0] + 1]
    for t in range(1, E.shape[0]):
        em = E[t]
        nb = np.empty_like(a_b)
        nb[:, 0] = a_b[:, 0]
        np.maximum(a_b[:, 1:], a_u, out=nb[:, 1:])
        nb += em[0]
        nu = np.maximum(a_u, a_b[:, :L])
        nu[:, 1:] = np.maximum(nu[:, 1:], np.where(same[:, 1:], NEG, a_u[:, :-1]))
        nu += em[U + 1]
        a_b, a_u = nb, nu
    idx = np.arange(N)
    return np.maximum(a_b[idx, ln], a_u[idx, ln - 1])


class Lexicon:
    """Từ điển phát âm viết theo bộ token của một model, để chấm CTC.
    classes: âm từ điển (khoá ipa_us.key) -> các token model được coi là âm đó
    seqs:    âm mà model ghi bằng nhiều token, kèm các cách ghi thường gặp
    blank:   token không tính là âm riêng (gộp vào blank)"""

    def __init__(self, classes: dict[str, str], seqs: dict[str, list], blank: str):
        self.classes = {c: set(t.split()) for c, t in classes.items()}
        self.seqs, self.blank = seqs, set(blank.split())
        self.ids = {c: k for k, c in enumerate(classes)}
        self.U = None

    def _expand(self, key: list[str]) -> list[list[str]]:
        """Dãy âm từ điển -> các dãy lớp âm model có thể phát ra (tối đa 8 biến thể)."""
        import itertools
        opts = [self.seqs.get(p, [[p]]) for p in key]
        n = 1
        for o in opts:
            n *= len(o)
        if n > 8:
            opts = [o[:1] for o in opts]
        return [[u for part in combo for u in part] for combo in itertools.product(*opts)]

    def _build(self):
        seqs, owner, variant = [], [], []
        for wi, w in enumerate(CANON):
            seen = set()
            for k, key in enumerate(CANON[w]):
                for x in self._expand(key):
                    if x and all(u in self.ids for u in x) and tuple(x) not in seen:
                        seen.add(tuple(x))
                        seqs.append([self.ids[u] for u in x])
                        owner.append(wi)
                        variant.append(k)
        self.ln = np.array([len(x) for x in seqs])
        self.U = np.zeros((len(seqs), self.ln.max()), np.int32)
        for i, x in enumerate(seqs):
            self.U[i, :len(x)] = x
        self.owner, self.variant = np.array(owner), np.array(variant)

    def _class_logp(self, logp: np.ndarray, vocab: dict[int, str]) -> np.ndarray:
        """log xác suất token [T, V] -> log xác suất lớp âm [T, 1 + số lớp]; cột 0 = blank."""
        import unicodedata
        p = np.exp(logp.astype(np.float64))
        E = np.zeros((p.shape[0], len(self.ids) + 1))
        E[:, 0] = p[:, 0]
        for i, tok in vocab.items():
            if not 0 < i < p.shape[1]:
                continue
            if tok in self.blank:                      # '˞' của ZIPA vừa là blank vừa là lớp âm riêng
                E[:, 0] += p[:, i]
            base = "".join(ch for ch in unicodedata.normalize("NFD", tok) if ch not in _STRIP)
            for c, k in self.ids.items():
                if base in self.classes[c]:
                    E[:, k + 1] += p[:, i]
        E = np.log(E + 1e-12).astype(np.float32)
        voiced = np.where(E[:, 0] < np.log(0.9))[0]            # bỏ các khung im lặng ở 2 đầu
        return E[max(0, voiced[0] - 2): voiced[-1] + 3] if len(voiced) else E[:1]

    def word_scores(self, logp: np.ndarray, vocab: dict[int, str]) -> tuple[np.ndarray, np.ndarray]:
        """(điểm CTC tốt nhất của mỗi từ, cách đọc đạt điểm đó); từ bị loại sớm = LEX_FLOOR."""
        if self.U is None:
            self._build()
        E = self._class_logp(logp, vocab)
        best = np.full(len(CANON), LEX_FLOOR, np.float32)
        best_k = np.zeros(len(CANON), np.int32)
        # lọc nhanh: mỗi âm lấy khung tốt nhất của nó (chặn trên của điểm thật), giữ LEX_KEEP dãy đầu
        mx = np.append(E.max(0)[1:], 0.0)
        pad = np.where(np.arange(self.U.shape[1])[None] < self.ln[:, None], self.U, len(self.ids))
        cand = np.argsort(-mx[pad].sum(1))[:LEX_KEEP]
        cand = cand[self.ln[cand] <= E.shape[0]]
        if len(cand):
            score = _ctc_best_path(E, self.U[cand, :self.ln[cand].max()], self.ln[cand])
            for c in np.argsort(score):                         # điểm cao ghi sau cùng
                if score[c] > best[self.owner[cand[c]]]:
                    best[self.owner[cand[c]]] = score[c]
                    best_k[self.owner[cand[c]]] = self.variant[cand[c]]
        return best, best_k


_CONS = {"p": "p", "b": "b ɓ β", "t": "t ʈ", "d": "d ɖ ɗ", "k": "k c q", "ɡ": "g ɡ ɠ ɢ", "f": "f ɸ",
         "v": "v ʋ", "θ": "θ", "ð": "ð", "s": "s", "z": "z", "ʃ": "ʃ ɕ ʂ", "ʒ": "ʒ ʑ ʐ", "m": "m ɱ",
         "n": "n ɳ ɲ", "ŋ": "ŋ ɴ", "l": "l ɭ ʎ ʟ", "r": "ɹ ɻ r ɽ", "j": "j ʝ", "w": "w ʍ ɰ", "ɾ": "ɾ t d"}
# ZIPA: phiên âm hẹp, nguyên âm đôi và tʃ dʒ tách 2 token, r-hoá là token '˞' riêng
LEX_ZIPA = Lexicon(
    {**_CONS, "v": "v ʋ β", "b": "b ɓ", "h": "h ɦ x χ ħ ç",
     "i": "i", "ɪ": "ɪ ɨ", "e": "ɛ e", "æ": "æ", "ɑ": "ɑ a ɒ ɔ", "ɔ": "ɔ o", "ʌ": "ʌ a ɐ", "ʊ": "ʊ",
     "u": "u ʉ", "ə": "ə ɐ ɘ ɵ",
     "o": "o", "a": "a ɑ", "ɜ": "ɜ ə ɚ", "˞": "˞"},                 # 4 lớp cuối chỉ dùng trong seqs
    {"tʃ": [["t", "ʃ"]], "dʒ": [["d", "ʒ"]],
     "eɪ": [["e", "ɪ"], ["e"]], "aɪ": [["a", "ɪ"]], "aʊ": [["a", "ʊ"]], "oʊ": [["o", "ʊ"], ["o"]],
     "ɔɪ": [["ɔ", "ɪ"]],
     "ɚ": [["ə", "˞"], ["r"], ["ə", "r"]], "ɝ": [["ɜ", "˞"], ["ɜ", "r"], ["r"]]},
    "ː ʰ ʲ ʷ ˠ ˤ ʼ ̃ ̚ ̥ ̩ ̪ ̴ ̺ ˞ ▁ <sos/eos> <unk>")
# Koel: IPA tiếng Anh, nguyên âm đôi / tʃ dʒ / ɚ ɝ là một token
LEX_KOEL = Lexicon(
    {**_CONS, "k": "k x", "ɡ": "ɡ g ɣ", "h": "h ɦ",
     "i": "i", "ɪ": "ɪ ɨ", "e": "ɛ e", "æ": "æ a", "ɑ": "ɑ ɒ ɔ a", "ɔ": "ɔ o", "ʌ": "ʌ", "ʊ": "ʊ",
     "u": "u ʉ", "ə": "ə ɨ",
     "tʃ": "tʃ", "dʒ": "dʒ", "eɪ": "eɪ e", "aɪ": "aɪ", "aʊ": "aʊ", "oʊ": "oʊ əʊ o", "ɔɪ": "ɔɪ",
     "ɚ": "ɚ", "ɝ": "ɝ ɜ ɚ"},
    {"tʃ": [["tʃ"], ["t", "ʃ"]], "dʒ": [["dʒ"], ["d", "ʒ"]],
     "ɚ": [["ɚ"], ["ə", "r"], ["r"]], "ɝ": [["ɝ"], ["ɝ", "r"], ["ə", "r"]]},
    "<pad> <s> </s> <unk> | ʔ")
_ZIPF = None


WORD_LIST = list(CANON)
WORD_INDEX = {w: i for i, w in enumerate(WORD_LIST)}


def lex_totals(evidence: list) -> tuple[np.ndarray, np.ndarray]:
    """Tổng điểm (CTC các model + độ phổ biến) của mọi từ theo thứ tự WORD_LIST, và cách đọc khớp nhất."""
    global _ZIPF
    if _ZIPF is None:
        _ZIPF = np.array([WORDS[w]["zipf"] for w in CANON])
    total, best_k = WORD_PRIOR * _ZIPF, None
    for lexicon, logp, vocab in evidence:
        score, k = lexicon.word_scores(logp, vocab)
        total = total + score
        best_k = k if best_k is None else best_k       # cách đọc: theo model đầu tiên
    return total, best_k


def lex_words(evidence: list, top: int = 3) -> list[tuple[str, float, int]]:
    """evidence: [(Lexicon, logp, vocab)] của từng model. Trả về [(từ, độ chắc 0..1, cách đọc khớp nhất)]
    xếp theo tổng điểm CTC các model + độ phổ biến của từ."""
    total, best_k = lex_totals(evidence)
    order = np.argsort(-total)[:top]
    conf = np.exp(total - total[order[0]])             # độ chắc = softmax trên cả từ điển
    conf /= conf.sum()
    words = list(CANON)
    return [(words[i], float(conf[i]), int(best_k[i])) for i in order]


def match(raw: list[tuple[str, float]], top: int = 3, evidence: list | None = None):
    """IPA thô của model -> ([(âm Cambridge, tin cậy)], [(từ, điểm, IPA Cambridge của cách đọc khớp)]).
    Có evidence: chọn từ bằng chấm CTC theo từ điển, điểm = độ chắc. Không có: so chuỗi âm, điểm = % giống."""
    heard = ipa_us.from_model(raw)
    if not heard:
        return [], []
    matches = lex_words(evidence, top) if evidence else []
    if not matches:
        matches = find_words(ipa_us.key([p for p, _ in heard]), top)
    w0, _, k0 = matches[0]
    best = WORDS[w0]["ph"][k0]
    phones = ipa_us.resolve([p for p, _ in heard], best,
                              lambda a, b: align(ipa_us.key(a), ipa_us.key(b)))
    matches = [(w, sim, WORDS[w]["ipa"][k]) for w, sim, k in matches]
    return [(p, c) for p, (_, c) in zip(phones, heard)], matches


# ---------- 4. Âm thanh -> IPA ----------
_recognizer = None
MIN_PEAK = 0.02                        # bản ghi nhỏ hơn mức này coi như im lặng
PAD_SECONDS = 0.5                      # đệm tiếng ồn rất nhỏ 2 đầu: model nhận từ đơn tốt hơn hẳn
PAD_NOISE = 0.002
# Ký hiệu bổ trợ (r-hoá, bật hơi, dài...) được gộp vào âm đứng trước khi hiển thị
_MODIFIERS = set("˞ːʰʲʷˠˤʼ") | set("̴̩̥̪̺̃̆̚")


def pad_audio(audio: np.ndarray) -> np.ndarray:
    """Thêm 0.5s tiếng ồn rất nhỏ ở 2 đầu (ZIPA: đoán đúng ngay từ 53% lên 66%)."""
    rng = np.random.default_rng(0)
    n = int(PAD_SECONDS * SR)
    noise = lambda: (rng.standard_normal(n) * PAD_NOISE).astype(np.float32)
    return np.concatenate([noise(), audio.astype(np.float32), noise()])


def ctc_greedy(ids, probs, id2tok, skip: set) -> list[tuple[str, float]]:
    """Gộp khung CTC -> [(âm, độ tin cậy 0..1)]; tin cậy = xác suất cao nhất của âm đó."""
    out, prev = [], None
    for t, i in enumerate(ids):
        if i == prev:
            if out and i not in skip:
                out[-1][2] = max(out[-1][2], probs[t, i])
            continue
        prev = i
        if i not in skip:
            out.append([i, id2tok(i), probs[t, i]])
    merged = []                                  # gộp ký hiệu bổ trợ vào âm trước
    for _, tok, c in out:
        if merged and tok and all(ch in _MODIFIERS for ch in tok):
            merged[-1] = (merged[-1][0] + tok, min(merged[-1][1], float(c)))
        else:
            merged.append((tok, float(c)))
    return merged


class ZipaRecognizer:
    """ZIPA small (Zipformer CR-CTC) chạy bằng ONNX Runtime."""
    name = f"{ZIPA_REPO}/{ZIPA_FILE}"
    evidence = None                     # [(Lexicon, logp, vocab)] của lần nhận gần nhất

    def __init__(self):
        import onnxruntime as ort
        from lhotse.features.kaldi.extractors import Fbank, FbankConfig
        model_path = os.path.join(ZIPA_DIR, ZIPA_FILE)
        tokens_path = os.path.join(ZIPA_DIR, "tokens.txt")
        if not (os.path.exists(model_path) and os.path.exists(tokens_path)):
            from huggingface_hub import hf_hub_download
            print("Đang tải model ZIPA (lần đầu, 71 MB)...")
            for f in (ZIPA_FILE, "tokens.txt"):
                hf_hub_download(ZIPA_REPO, f, local_dir=ZIPA_DIR)
        opts = ort.SessionOptions()
        opts.log_severity_level = 3
        self.sess = ort.InferenceSession(model_path, opts, providers=["CPUExecutionProvider"])
        self.vocab = {}
        with open(tokens_path, encoding="utf-8") as f:
            for line in f:
                parts = line.rstrip("\n").split(" ")
                if len(parts) >= 2:
                    self.vocab[int(parts[-1])] = " ".join(parts[:-1])
        self.skip = {0} | {i for i, t in self.vocab.items() if t in ("▁", "<sos/eos>", "<unk>")}
        self.fbank = Fbank(FbankConfig(num_filters=80, dither=0.0, snip_edges=False))

    def __call__(self, audio: np.ndarray) -> list[tuple[str, float]]:
        import torch
        wav = torch.from_numpy(audio.astype(np.float32)).unsqueeze(0)
        feats = self.fbank.extract_batch([wav], sampling_rate=SR)[0].unsqueeze(0).numpy()
        logp = self.sess.run(None, {"x": feats, "x_lens": np.array([feats.shape[1]], np.int64)})[0][0]
        probs = np.exp(logp - logp.max(-1, keepdims=True))
        probs /= probs.sum(-1, keepdims=True)
        self.evidence = [(LEX_ZIPA, np.log(probs + 1e-30), self.vocab)]   # để chấm từ điển bằng CTC
        return ctc_greedy(logp.argmax(-1).tolist(), probs, lambda i: self.vocab.get(i, "?"), self.skip)


class XlsrRecognizer:
    """wav2vec2-xlsr-53-espeak-cv-ft (model cũ, đa ngôn ngữ) chạy bằng transformers."""
    name = XLSR_MODEL
    evidence = None                     # XLSR: bộ token khác, vẫn so chuỗi âm như cũ

    def __init__(self):
        from transformers import AutoModelForCTC, AutoProcessor
        print("Đang tải model XLSR-53 (lần đầu ~1.2GB)...")
        self.proc = AutoProcessor.from_pretrained(XLSR_MODEL)
        self.model = AutoModelForCTC.from_pretrained(XLSR_MODEL).eval()
        tok = self.proc.tokenizer
        self.skip = {tok.pad_token_id, tok.word_delimiter_token_id}

    def __call__(self, audio: np.ndarray) -> list[tuple[str, float]]:
        import torch
        inputs = self.proc(audio.astype(np.float32), sampling_rate=SR, return_tensors="pt")
        with torch.no_grad():
            logits = self.model(**inputs).logits[0]
        return ctc_greedy(logits.argmax(-1).tolist(), logits.softmax(-1).numpy(),
                          self.proc.tokenizer.convert_ids_to_tokens, self.skip)


class KoelRecognizer:
    """KoelLabs/xlsr-english-01: wav2vec2 nhận âm vị chuyên tiếng Anh (cả giọng người học), ghi IPA tiếng Anh.
    Chạy kèm ZIPA và cộng điểm hai model khi chọn từ; IPA hiển thị là của Koel.
    Model bị khoá trên Hugging Face: lần đầu cần được cấp quyền ở trang model và đăng nhập
    (`hf auth login` hoặc biến môi trường HF_TOKEN). Tải xong thì chạy offline."""
    name = f"{KOEL_MODEL} + {ZIPA_REPO}"

    def __init__(self):
        from transformers import AutoFeatureExtractor, AutoModelForCTC, AutoTokenizer
        try:
            parts = [c.from_pretrained(KOEL_MODEL, local_files_only=True)
                     for c in (AutoFeatureExtractor, AutoTokenizer, AutoModelForCTC)]
        except OSError:
            print("Đang tải model Koel (lần đầu ~1.2GB)...")
            parts = [c.from_pretrained(KOEL_MODEL)
                     for c in (AutoFeatureExtractor, AutoTokenizer, AutoModelForCTC)]
        self.fe, tok, self.model = parts
        self.model.eval()
        self.vocab = {i: t for t, i in tok.get_vocab().items()}
        self.skip = {i for i, t in self.vocab.items() if t in LEX_KOEL.blank and t != "ʔ"}
        self.zipa = ZipaRecognizer()

    def __call__(self, audio: np.ndarray) -> list[tuple[str, float]]:
        import unicodedata
        import torch
        self.zipa(audio)
        x = self.fe(audio.astype(np.float32), sampling_rate=SR, return_tensors="pt")
        with torch.no_grad():
            logp = self.model(**x).logits[0].log_softmax(-1).numpy()
        self.evidence = [(LEX_KOEL, logp, self.vocab)] + self.zipa.evidence
        return ctc_greedy(logp.argmax(-1).tolist(), np.exp(logp),
                          lambda i: unicodedata.normalize("NFD", self.vocab.get(i, "?")), self.skip)


def load_model():
    global _recognizer
    if _recognizer is None:
        kinds = {"koel": KoelRecognizer, "zipa": ZipaRecognizer, "xlsr": XlsrRecognizer}
        if MODEL_KIND not in kinds:
            sys.exit(f"Model không hợp lệ: {MODEL_KIND} (chọn koel, zipa hoặc xlsr)")
        try:
            _recognizer = kinds[MODEL_KIND]()
        except OSError as e:
            if MODEL_KIND != "koel":
                raise
            print(f"(Không tải được model Koel: {str(e).splitlines()[0][:120]}\n"
                  " Model này cần được cấp quyền trên Hugging Face + `hf auth login`. Tạm dùng ZIPA.)")
            _recognizer = ZipaRecognizer()
    return _recognizer


def recognize(audio: np.ndarray) -> list[tuple[str, float]]:
    """Âm thanh -> [(âm, độ tin cậy)] đúng như model nghe, không lọc."""
    return load_model()(audio)


def analyze(audio: np.ndarray) -> dict:
    """In kết quả ra màn hình, trả về dict để ghi log."""
    import time
    info = {"seconds": round(len(audio) / SR, 2),
            "peak": round(float(np.abs(audio).max()) if len(audio) else 0.0, 4),
            "rms": round(float(np.sqrt(np.mean(audio ** 2))) if len(audio) else 0.0, 4)}
    if info["peak"] < MIN_PEAK:
        print("  Không nghe rõ (quá nhỏ), thử nói to và gần micro hơn.\n")
        info["error"] = "too_quiet"
        return info
    t0 = time.time()
    raw = recognize(pad_audio(audio))
    info["infer_ms"] = round((time.time() - t0) * 1000)
    info["raw"] = [(p, round(c * 100)) for p, c in raw]
    rec = load_model()
    use_lex = bool(rec.evidence) and os.environ.get("V2I_MATCH", "ctc") != "edit"
    heard, matches = match(raw, evidence=rec.evidence if use_lex else None)
    if not heard:
        print("  Không nghe rõ, thử nói to và gần micro hơn.\n")
        info["error"] = "no_phones"
        return info
    info["ipa"] = "".join(p for p, _ in heard)                    # IPA model đã chuẩn hoá (Cambridge US)
    avg = round(100 * sum(c for _, c in heard) / len(heard))
    print(f"  IPA : /{info['ipa']}/   (tin cậy TB {avg}%)")
    print("        " + " · ".join(f"{p} {round(c * 100)}%" for p, c in heard))
    info["method"] = "ctc" if use_lex else "edit"
    info["matches"] = [{"word": w, "sim": round(sim * 100), "ipa": ipa} for w, sim, ipa in matches]
    rows = [(w, "/" + ipa + "/", sim) for w, sim, ipa in matches]
    wlen = max(len(r[0]) for r in rows)
    ilen = max(len(r[1]) for r in rows)
    for n, (w, ipa, sim) in enumerate(rows):
        mark = "★" if n == 0 else " "
        label = "chắc" if use_lex else "giống"
        print(f"  {mark} {w:<{wlen}}  {ipa:<{ilen}}  {label} {sim * 100:>3.0f}%  →  {WORDS[w]['vi']}")
    print()
    return info


# ---------- 5. Lưu bản ghi + log phiên ----------
class Session:
    """Mỗi lần chạy: recordings/<phiên>/NN_<từ>.wav và logs/<phiên>.log (mỗi dòng 1 JSON)."""

    def __init__(self):
        import time
        self.name = time.strftime("%Y%m%d_%H%M%S")
        self.rec_dir = os.path.join(HERE, "recordings", self.name)
        self.log_path = os.path.join(HERE, "logs", self.name + ".log")
        os.makedirs(self.rec_dir, exist_ok=True)
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
        self.n = 0
        self.log({"event": "start", "model": load_model().name, "words": len(WORDS)})

    def log(self, record: dict):
        import time
        record = {"time": time.strftime("%H:%M:%S"), **record}
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def save(self, audio: np.ndarray, info: dict, label: str | None = None) -> str:
        self.n += 1
        best = label or info.get("matches", [{}])[0].get("word", info.get("error", "x"))
        path = os.path.join(self.rec_dir, f"{self.n:02d}_{best}.wav")
        write_wav(path, audio)
        self.log({"event": "take", "n": self.n, "file": os.path.relpath(path, HERE), **info})
        return path


def write_wav(path: str, audio: np.ndarray):
    import wave
    pcm = (np.clip(audio, -1, 1) * 32767).astype(np.int16)
    with wave.open(path, "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(SR)
        f.writeframes(pcm.tobytes())


def read_wav(path: str) -> np.ndarray:
    import wave
    with wave.open(path) as f:
        sr, ch, width = f.getframerate(), f.getnchannels(), f.getsampwidth()
        pcm = f.readframes(f.getnframes())
    if width != 2:
        raise ValueError(f"{path}: chỉ hỗ trợ WAV 16-bit")
    audio = np.frombuffer(pcm, np.int16).astype(np.float32) / 32768
    audio = audio.reshape(-1, ch).mean(axis=1)
    if sr != SR:                                   # đổi tần số mẫu đơn giản
        n = int(len(audio) * SR / sr)
        audio = np.interp(np.linspace(0, len(audio) - 1, n), np.arange(len(audio)), audio)
    return audio.astype(np.float32)


# ---------- 6. Giữ SPACE để ghi âm ----------
# Bắt đầu ghi: chỉ khi ký tự SPACE đến từ chính cửa sổ terminal này (stdin),
#   nên bấm SPACE ở app/tab khác sẽ không kích hoạt.
# Dừng ghi: terminal không báo sự kiện nhả phím, nên dùng pynput để bắt.
class PushToTalk:
    def __init__(self, local_only: bool):
        self.local_only = local_only   # True: chỉ bắt đầu khi phím đến từ stdin
        self.space_down = False        # trạng thái phím SPACE theo pynput
        self.recording = False
        self.busy = False
        self.c_capture = False         # True: micro thu bằng rtmixer (main() gán)
        self.chunks: list[np.ndarray] = []
        self.lock = threading.Lock()
        self.jobs: queue.Queue = queue.Queue()
        self.on_start = None           # gọi khi bắt đầu ghi (vd dừng giọng đọc mẫu)

    def feed(self, data: np.ndarray):
        """Nhận một đoạn mẫu micro (mono float32, SR)."""
        if self.recording:
            with self.lock:
                self.chunks.append(data.copy())

    def start(self):
        if self.recording or self.busy:
            return
        import sounddevice as sd
        sd.stop()                      # dừng phát lại bản ghi trước (nếu còn)
        if self.on_start:
            self.on_start()
        with self.lock:
            self.chunks = []
        self.recording = True
        print("● Đang ghi... (nhả SPACE để dừng)", flush=True)

    def stop(self):
        if not self.recording:
            return
        self.recording = False
        with self.lock:
            audio = np.concatenate(self.chunks) if self.chunks else np.zeros(0, np.float32)
        self.busy = True
        self.jobs.put(audio)

    # --- pynput (toàn hệ thống) ---
    def on_press(self, key):
        from pynput import keyboard
        if key == keyboard.Key.space:
            self.space_down = True
            if not self.local_only:
                self.start()

    def on_release(self, key):
        from pynput import keyboard
        if key == keyboard.Key.space:
            self.space_down = False
            self.stop()

    # --- stdin (chỉ cửa sổ terminal này) ---
    def read_stdin(self, fd: int, check_held: bool):
        import select
        while True:
            try:
                ch = os.read(fd, 1)
            except OSError:
                return
            if not ch:
                return
            if ch == b" ":
                # pynput thấy phím trước terminal; nếu đã nhả rồi (gõ quá nhanh) thì bỏ qua
                if not check_held or self.space_down:
                    self.start()
            elif ch == b"\x1b":
                if select.select([fd], [], [], 0.05)[0]:
                    os.read(fd, 16)          # phím mũi tên v.v. -> bỏ qua
                else:
                    self.jobs.put(None)      # Esc -> thoát
                    return
            elif ch in (b"\n", b"\r"):
                self.jobs.put(("key", "\n"))
            elif ch[0] < 0x80 and (ch.isalpha() or ch == b"?"):
                self.jobs.put(("key", ch.decode().lower()))   # phím lệnh (chế độ đoán từ)


def open_mic(ptt: "PushToTalk"):
    """Mở micro (SR, mono), mẫu thu được đưa vào ptt.feed.
    Ưu tiên rtmixer: callback viết bằng C ghi vào vùng đệm vòng, không cần khóa GIL của Python.
    Callback Python của sounddevice phải chờ GIL; khi luồng khác bận (vd vẽ --game 30 FPS)
    PortAudio trên macOS bỏ bớt mẫu mà không báo -> bản ghi lách tách."""
    try:
        import rtmixer
    except ImportError:
        import sounddevice as sd
        return sd.InputStream(samplerate=SR, channels=1, dtype="float32",
                              callback=lambda d, n, t, st: ptt.feed(d[:, 0]))
    import time
    rec = rtmixer.Recorder(samplerate=SR, channels=1, latency="high")
    rb = rtmixer.RingBuffer(4, 2 ** 16)          # float32 mono, ~4 s ở 16 kHz

    def pump():
        while True:
            n = rb.read_available
            if n:
                ptt.feed(np.frombuffer(rb.read(n), np.float32))
            time.sleep(0.02)

    class _Mic:
        def __enter__(self):
            rec.start()
            rec.record_ringbuffer(rb)
            threading.Thread(target=pump, daemon=True).start()
            ptt.c_capture = True
            return self

        def __exit__(self, *exc):
            rec.stop()
            rec.close()

    return _Mic()


def can_listen_keys() -> bool:
    """macOS: kiểm tra quyền Input Monitoring (pynput chỉ kiểm tra Accessibility,
    là quyền không cần cho việc nghe phím nên báo sai)."""
    if sys.platform != "darwin":
        return True
    try:
        import Quartz
        return bool(Quartz.CGPreflightListenEventAccess())
    except Exception:
        return True


# ---------- 7. Chế độ đoán từ (--guess) ----------
# Máy đọc 1 từ ngẫu nhiên (không hiện chữ), người chơi nói lại, chấm % giống IPA của từ đó.
LEVELS = {"easy": (5.0, 99.0), "mid": (4.0, 99.0), "hard": (3.0, 4.0), "all": (0.0, 99.0)}  # khoảng zipf
AUTO_REVEAL = 0.9          # đạt từ mức này: tự hiện đáp án
_ANSI = {"ok": "32", "near": "33", "bad": "31", "dim": "2", "bold": "1"}
GUESS_KEYS = ("[giữ Space] nói  [R] nghe lại  [S] nghe chậm  [M] so âm bạn ↔ chuẩn  [A/Enter] đáp án"
              "  [N] từ mới  [Esc] thoát")
IPA_SAY_SRC = os.path.join(HERE, "ipa_say.swift")
IPA_SAY_BIN = os.path.join(HERE, "models", "ipa_say")
IPA_GAP = 0.6              # giây nghỉ giữa "âm của bạn" và "âm chuẩn" khi bấm M

# Âm Cambridge -> ký hiệu IPA mà giọng Apple đọc đúng (thử với Ava Premium: nguyên âm đôi cần dấu nối,
# /e/ phải viết ɛ, /ɝː/ viết ɜr; /ɚ/ cuối từ Apple đọc chưa tốt, ɜr là cách đỡ nhất)
_APPLE_IPA = {"e": "ɛ", "eɪ": "e͡ɪ", "aɪ": "a͡ɪ", "aʊ": "a͡ʊ", "ɔɪ": "ɔ͡ɪ", "oʊ": "o͡ʊ",
              "ɝː": "ɜr", "ɝ": "ɜr", "ɚ": "ɜr", "t̬": "t", "ɡ": "ɡ"}


def stressed_vowel(ipa: str, phones: list[str]) -> int | None:
    """Vị trí (trong phones) của nguyên âm mang trọng âm chính, đọc từ chuỗi Cambridge vd 'ˌɪmˈpɔːr.t̬ənt'."""
    vowels = [i for i, p in enumerate(phones) if p in ipa_us.VOWELS]
    if not vowels:
        return None
    marks = [m for m, _ in re.findall(r"([ˈˌ.]?)([^ˈˌ.]+)", ipa)]
    syl = marks.index("ˈ") if "ˈ" in marks else 0
    return vowels[min(syl, len(vowels) - 1)]


def apple_ipa(phones: list[str], stress: int | None) -> str:
    """Dãy âm Cambridge -> chuỗi IPA cho AVSpeechSynthesizer; dấu ˈ đặt trước phụ âm đầu âm tiết nhấn."""
    out = [_APPLE_IPA.get(p, p) for p in phones]
    nvow = sum(1 for p in phones if p in ipa_us.VOWELS)
    if stress is not None and nvow > 1:
        s = stress
        while s > 0 and phones[s - 1] not in ipa_us.VOWELS and \
                ipa_us._legal_onset(tuple(phones[s - 1:stress])):
            s -= 1
        out.insert(s, "ˈ")
    return "".join(out)


def paint(text: str, style: str) -> str:
    return f"\033[{_ANSI[style]}m{text}\033[0m" if sys.stdout.isatty() else text


def _width(s: str) -> int:
    import unicodedata
    return sum(1 for ch in s if not unicodedata.combining(ch))   # t̬ chiếm 1 ô


# Từ mẫu: bản ghi giọng người (Mỹ) trên Wikimedia Commons, tra bằng bảng data/audio_us.json {từ: đường dẫn mp3}
# dựng sẵn từ bản dump Wiktionary của kaikki.org (build_audio.py, cách của ~/english_dictionary): không gọi API.
# Tải 1 lần rồi giữ ở data/audio/<từ>.wav (lần sau offline). Từ không có bản ghi / tải lỗi: giọng máy macOS (`say`),
# giọng tiếng Anh tốt nhất đã cài (Ava Premium…), đổi bằng V2I_VOICE. Cùng giọng đó đọc âm của bạn khi bấm M.
# Giọng Premium/Enhanced tải trong System Settings > Accessibility > Spoken Content.
COMMONS = "https://upload.wikimedia.org/wikipedia/commons/"
AUDIO_DIR = os.path.join(HERE, "data", "audio")
AUDIO_TABLE = os.path.join(HERE, "data", "audio_us.json")
# Wikimedia giới hạn chặt client không ghi cách liên hệ (https://w.wiki/4wJS): đặt V2I_CONTACT="email hoặc URL"
HTTP_UA = "voice2ipa-practice/0.2 (" + (os.environ.get("V2I_CONTACT") or "personal pronunciation practice") + ")"
VOICES = ("Ava (Premium)", "Zoe (Premium)", "Evan (Premium)", "Ava (Enhanced)", "Zoe (Enhanced)", "Evan (Enhanced)",
          "Samantha (Enhanced)", "Allison (Enhanced)", "Tom (Enhanced)", "Samantha")
TTS_PAD = (0.15, 0.4)      # giây im lặng thêm trước/sau: loa, tai nghe Bluetooth hay cắt mất âm đầu/cuối
SLOW_FACTOR = 0.7          # phím S: phát chậm còn 70% tốc độ, giữ nguyên cao độ


def load_audio_table() -> dict[str, str]:
    try:
        with open(AUDIO_TABLE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        print(f"(Chưa có {os.path.relpath(AUDIO_TABLE, HERE)}: chạy `python3 build_audio.py` để dùng bản ghi giọng người;"
              " tạm dùng giọng máy.)")
        return {}


AUDIO_US = load_audio_table()


def audio_file_name(path: str) -> str:
    """Tên file trên Commons từ đường dẫn: transcoded/b/bd/TÊN/TÊN.mp3 hoặc b/bd/TÊN."""
    import urllib.parse
    parts = path.split("/")
    return urllib.parse.unquote(parts[3] if path.startswith("transcoded/") else parts[2])


def has_recording(word: str) -> bool:
    return word in AUDIO_US or os.path.exists(os.path.join(AUDIO_DIR, word + ".wav"))


def installed_voices() -> set[str]:
    """Tên các giọng `say` đã cài. Mỗi dòng `say -v ?`: "<tên, có thể có dấu cách>  <xx_YY>  # câu mẫu"."""
    import shutil
    import subprocess
    if not shutil.which("say"):
        return set()
    listed = subprocess.run(["say", "-v", "?"], capture_output=True, text=True).stdout
    return {m.group(1).strip() for line in listed.splitlines()
            if (m := re.match(r"(.+?)\s{2,}[a-z]{2}_[A-Z]{2}", line))}


def best_voice() -> str:
    """V2I_VOICE nếu đã cài, không thì giọng đầu tiên trong VOICES đã cài; "" = giọng mặc định của máy."""
    have = installed_voices()
    want = [os.environ["V2I_VOICE"]] if os.environ.get("V2I_VOICE") else []
    return next((v for v in want + list(VOICES) if v in have), "")


def load_wav_native(path: str) -> tuple[np.ndarray, int]:
    """WAV 16-bit -> (float32 mono, tần số mẫu gốc)."""
    import wave
    with wave.open(path) as f:
        sr, ch = f.getframerate(), f.getnchannels()
        x = np.frombuffer(f.readframes(f.getnframes()), np.int16).astype(np.float32) / 32768
    return x.reshape(-1, ch).mean(axis=1), sr


def time_stretch(x: np.ndarray, sr: int, factor: float) -> np.ndarray:
    """Đổi tốc độ, giữ cao độ (WSOLA): factor 0.7 = dài thêm ~43%."""
    win = int(0.04 * sr)
    hop_out = win // 2
    hop_in = max(1, int(hop_out * factor))
    tol = int(0.01 * sr)
    w = np.hanning(win).astype(np.float32)
    x = np.concatenate([np.zeros(tol, np.float32), x, np.zeros(2 * win + tol, np.float32)])
    out = np.zeros(int(len(x) / factor) + 2 * win, np.float32)
    norm = np.zeros_like(out)
    pos_in, pos_out, prev = tol, 0, None
    while pos_in + win + tol < len(x) and pos_out + win < len(out):
        best = pos_in
        if prev is not None:                       # chọn đoạn nối khớp nhất với phần tiếp tự nhiên
            target = x[prev + hop_out:prev + hop_out + win]
            region = x[pos_in - tol:pos_in + tol + win]
            best = pos_in - tol + int(np.argmax(np.correlate(region, target, "valid")))
        out[pos_out:pos_out + win] += x[best:best + win] * w
        norm[pos_out:pos_out + win] += w
        prev, pos_in, pos_out = best, pos_in + hop_in, pos_out + hop_out
    return (out / np.maximum(norm, 1e-3))[:pos_out]


class Speaker:
    """Từ mẫu: bản ghi giọng người trên Commons (bảng AUDIO_US, tải 1 lần vào data/audio/), không có hoặc tải lỗi thì
    giọng máy macOS (`say`). Phát bằng sounddevice, thêm khoảng lặng 2 đầu. Phím M: giọng máy đọc theo IPA."""

    def __init__(self):
        import tempfile
        self.dir = tempfile.mkdtemp(prefix="v2i_tts_")
        self.cache: dict[tuple, tuple[np.ndarray, int]] = {}
        self.lock = threading.Lock()
        self.ipa_bin: str | None = None          # None: chưa kiểm tra, "": không dùng được
        self.voice = best_voice()
        self.who: dict[str, str] = {}            # từ -> "người" | "máy": nguồn của lần đọc gần nhất
        self.blocked_until = 0.0                 # Commons trả 429: không tải gì tới lúc này
        self.word_locks: dict[str, threading.Lock] = {}   # 1 từ chỉ tải / đọc ở 1 luồng (luồng tải sẵn vs luồng chính)
        self.last_error = ""

    def _remember(self, key: tuple, clip: tuple[np.ndarray, int]):
        with self.lock:
            while len(self.cache) >= 16:
                self.cache.pop(next(iter(self.cache)))
            self.cache[key] = clip

    # --- bản ghi người thật ---
    @staticmethod
    def path(word: str) -> str:
        return os.path.join(AUDIO_DIR, word + ".wav")

    def fetch(self, word: str) -> str | None:
        """Đường dẫn WAV bản ghi của từ (tải mp3 từ Commons rồi đổi sang WAV nếu chưa có); None nếu không có
        trong bảng hoặc tải lỗi (mất mạng, bị chặn: ghi lý do vào last_error)."""
        import subprocess
        import tempfile
        import time
        if os.path.exists(self.path(word)):
            return self.path(word)
        src = AUDIO_US.get(word)
        if not src or time.time() < self.blocked_until:
            return None
        os.makedirs(AUDIO_DIR, exist_ok=True)
        with tempfile.TemporaryDirectory() as d:
            mp3, head = os.path.join(d, "a.mp3"), os.path.join(d, "head")
            # curl: upload.wikimedia.org hay trả 429 cho urllib của Python dù cùng User-Agent
            r = subprocess.run(["curl", "-sS", "-L", "--max-time", "8", "-A", HTTP_UA, "-o", mp3, "-D", head,
                                "-w", "%{http_code}", COMMONS + src], capture_output=True, text=True)
            code = int(r.stdout.strip()) if r.stdout.strip().isdigit() else 0
            if r.returncode or code != 200:
                if code == 429:
                    m = re.findall(r"(?im)^retry-after:\s*(\d+)", open(head, errors="replace").read())
                    self.blocked_until = time.time() + (int(m[-1]) if m else 600)
                    self.last_error = "Wikimedia tạm chặn tải (429)"
                else:
                    self.last_error = f"tải bản ghi lỗi ({'HTTP ' + str(code) if code else 'mất mạng?'})"
                return None
            fd, tmp = tempfile.mkstemp(suffix=".wav", dir=AUDIO_DIR)
            os.close(fd)
            r = subprocess.run(["afconvert", "-f", "WAVE", "-d", "LEI16", "-c", "1", mp3, tmp], capture_output=True)
            if r.returncode:
                os.remove(tmp)
                self.last_error = "không đổi được mp3 sang WAV (cần afconvert của macOS)"
                return None
            os.replace(tmp, self.path(word))
        return self.path(word)

    def source(self, word: str) -> str:
        """Tên file bản ghi trên Commons ("" nếu không có)."""
        return audio_file_name(AUDIO_US[word]) if word in AUDIO_US else ""

    # --- giọng máy (`say`) ---
    def _tts(self, word: str) -> tuple[np.ndarray, int] | None:
        import shutil
        import subprocess
        import tempfile
        if not shutil.which("say"):
            return None
        fd, path = tempfile.mkstemp(suffix=".wav", dir=self.dir)
        os.close(fd)
        args = ["-o", path, "--file-format=WAVE", "--data-format=LEI16@22050", "--", word]
        ok = bool(self.voice) and subprocess.run(["say", "-v", self.voice] + args, capture_output=True).returncode == 0
        ok = ok or subprocess.run(["say"] + args, capture_output=True).returncode == 0
        x, sr = load_wav_native(path) if ok else (None, 0)
        os.remove(path)
        return (x, sr) if x is not None and len(x) else None

    def _word(self, word: str, slow: bool = False) -> tuple[np.ndarray, int] | None:
        """Âm của từ (đã chuẩn hoá âm lượng, chưa đệm): bản ghi người thật, không được thì giọng máy."""
        key = ("word", word, slow)
        if key in self.cache:
            return self.cache[key]
        if slow:
            base = self._word(word)
            if base is None:
                return None
            clip = (time_stretch(base[0], base[1], SLOW_FACTOR), base[1])
        else:
            with self.lock:
                lock = self.word_locks.setdefault(word, threading.Lock())
            with lock:                           # luồng kia đang tải đúng từ này: đợi rồi lấy từ cache
                if key in self.cache:
                    return self.cache[key]
                path = self.fetch(word)
                raw, who = (load_wav_native(path), "người") if path else (self._tts(word), "máy")
                if raw is None:
                    return None
                self.who[word] = who
                clip = (raw[0] * (0.8 / max(float(np.abs(raw[0]).max()), 1e-3)), raw[1])
                self._remember(key, clip)
            return clip
        self._remember(key, clip)
        return clip

    def prefetch(self, word: str):
        """Tải / đọc sẵn từ kế tiếp ở nền."""
        threading.Thread(target=self._word, args=(word,), daemon=True).start()

    @staticmethod
    def _pad(x: np.ndarray, sr: int) -> np.ndarray:
        pad = [np.zeros(int(s * sr), np.float32) for s in TTS_PAD]
        return np.concatenate([pad[0], x, pad[1]])

    def say(self, word: str, slow: bool = False) -> str:
        """Phát từ. -> 'người' | 'máy' | '' (không đọc được)."""
        import sounddevice as sd
        sd.stop()
        clip = self._word(word, slow)
        if clip is None:
            print("  (Không đọc được từ này: không có bản ghi và không có lệnh `say`.)")
            return ""
        sd.play(self._pad(*clip), clip[1])
        return self.who.get(word, "")

    # --- đọc chuỗi IPA (chỉ macOS: AVSpeechSynthesizer qua ipa_say.swift) ---
    def _ipa_tool(self) -> str | None:
        """Biên dịch ipa_say.swift (1 lần, ~10 s) nếu chưa có hoặc đã sửa; None nếu máy không hỗ trợ."""
        import shutil
        import subprocess
        with self.lock:
            if self.ipa_bin is not None:
                return self.ipa_bin or None
            self.ipa_bin = ""
            if sys.platform != "darwin" or not os.path.exists(IPA_SAY_SRC):
                return None
            fresh = (os.path.exists(IPA_SAY_BIN)
                     and os.path.getmtime(IPA_SAY_BIN) >= os.path.getmtime(IPA_SAY_SRC))
            if not fresh:
                if not shutil.which("swiftc"):
                    return None
                os.makedirs(os.path.dirname(IPA_SAY_BIN), exist_ok=True)
                r = subprocess.run(["swiftc", "-O", IPA_SAY_SRC, "-o", IPA_SAY_BIN],
                                   capture_output=True, text=True)
                if r.returncode:
                    print(f"  (Không biên dịch được ipa_say.swift: {r.stderr.strip()[:200]})")
                    return None
            self.ipa_bin = IPA_SAY_BIN
            return self.ipa_bin

    def _render_ipa(self, ipa: str) -> tuple[np.ndarray, int] | None:
        """Giọng máy đọc 1 chuỗi IPA (chưa đệm)."""
        import subprocess
        import tempfile
        key = ("ipa", ipa)
        if key in self.cache:
            return self.cache[key]
        tool = self._ipa_tool()
        if not tool:
            return None
        out = tempfile.mkdtemp(dir=self.dir)
        cmd = [tool, "--voice", self.voice, "--out", out, ipa]
        if subprocess.run(cmd, capture_output=True).returncode:
            return None
        x, sr = load_wav_native(os.path.join(out, "0.wav"))
        os.remove(os.path.join(out, "0.wav"))
        os.rmdir(out)
        self._remember(key, (x * (0.8 / max(float(np.abs(x).max()), 1e-3)), sr))
        return self.cache[key]

    def say_compare(self, ipa: str, word: str) -> bool:
        """Phím M: giọng máy đọc các âm bạn nói (IPA) -> nghỉ -> từ chuẩn (bản ghi người thật nếu có)."""
        import sounddevice as sd
        sd.stop()
        mine, ref = self._render_ipa(ipa), self._word(word)
        if mine is None or ref is None:
            return False
        (x, sr_x), (y, sr) = mine, ref
        if sr_x != sr:                                           # đưa về cùng tần số mẫu
            x = np.interp(np.arange(int(len(x) * sr / sr_x)) * sr_x / sr, np.arange(len(x)), x)
        audio = np.concatenate([x, np.zeros(int(IPA_GAP * sr), np.float32), y]).astype(np.float32)
        sd.play(self._pad(audio, sr), sr)
        return True

    def prefetch_ipa(self, ipa: str):
        threading.Thread(target=self._render_ipa, args=(ipa,), daemon=True).start()

    def stop(self):
        import sounddevice as sd
        sd.stop()


def score_against(heard: list[str], target: str):
    """So âm người chơi nói với từng cách đọc của từ đích, lấy cách đọc khớp nhất.
    -> (điểm 0..1, cách đọc k, âm của bạn (Cambridge), khoá âm bạn, khoá âm chuẩn, cặp gióng)"""
    best = None
    for k, ref in enumerate(WORDS[target]["ph"]):
        mine = ipa_us.resolve(heard, ref, lambda a, b: align(ipa_us.key(a), ipa_us.key(b)))
        h, r = ipa_us.key(mine), CANON[target][k]
        sim = max(0.0, 1 - phone_distance(h, r) / max(len(h), len(r)))
        if best is None or sim > best[0]:
            best = (sim, k, mine, h, r, align(h, r))
    return best


def _pair_style(h: str, r: str) -> str:
    if h == r:
        return "ok"
    return "near" if _SUB_COST.get((h, r), 1.0) < 1 else "bad"


def _score_style(sim: float) -> str:
    return "ok" if sim >= AUTO_REVEAL else "near" if sim >= 0.6 else "bad"


def show_mine(mine, hkey, rkey, pairs) -> str:
    """Âm bạn nói, tô màu theo âm chuẩn (chưa lộ đáp án): xanh đúng, vàng gần đúng, đỏ sai/thừa, _ = thiếu."""
    out = []
    for i, j in pairs:
        if i is None:
            out.append(paint("_", "bad"))
        elif j is None:
            out.append(paint(mine[i], "bad"))
        else:
            out.append(paint(mine[i], _pair_style(hkey[i], rkey[j])))
    return " ".join(out)


def show_aligned(mine, ref, hkey, rkey, pairs) -> tuple[str, str]:
    """Hai dòng gióng từng âm: chuẩn / bạn ('-' = thiếu hoặc thừa)."""
    top, bot = [], []
    for i, j in pairs:
        a = ref[j] if j is not None else "-"
        b = mine[i] if i is not None else "-"
        style = "bad" if i is None or j is None else _pair_style(hkey[i], rkey[j])
        w = max(_width(a), _width(b))
        top.append(a + " " * (w - _width(a)))
        bot.append(paint(b + " " * (w - _width(b)), style))
    return "  ".join(top), "  ".join(bot)


class GuessMode:
    def __init__(self, session: "Session", level: str):
        import random
        if level not in LEVELS:
            sys.exit(f"Mức không hợp lệ: {level} (chọn {', '.join(LEVELS)})")
        lo, hi = LEVELS[level]
        self.pool = [w for w, e in WORDS.items() if lo <= e["zipf"] < hi and len(w) >= 3]
        if AUDIO_US:               # chỉ chơi từ có bản ghi giọng Mỹ (như trước); chưa dựng bảng thì giọng máy cả
            self.pool = [w for w in self.pool if has_recording(w)]
        random.shuffle(self.pool)
        self.session, self.level = session, level
        self.speaker = Speaker()
        threading.Thread(target=self.speaker._ipa_tool, daemon=True).start()   # biên dịch sẵn cho phím M
        self.word = None
        self.history = []          # [(từ, % âm cao nhất, số lần nói, đã nói đúng)]
        session.log({"event": "guess_start", "level": level, "pool": len(self.pool)})

    def intro(self):
        print(f"Chế độ ĐOÁN TỪ (mức {self.level}, {len(self.pool)} từ). Nghe rồi nói lại từ đó.")
        print(paint("  Từ mẫu: bản ghi giọng Mỹ (Wiktionary / Wikimedia Commons); tải lỗi thì giọng máy"
                    f" ({self.speaker.voice or 'mặc định'}). Phím M đọc âm của bạn bằng giọng máy.", "dim"))
        print(paint(GUESS_KEYS, "dim"))

    # --- một từ ---
    def new_word(self):
        self._close_word()
        if not self.pool:
            print("  Hết từ ở mức này.")
            return
        self.word = self.pool.pop()
        self.best, self.tries, self.revealed, self.correct, self.last = 0.0, 0, False, False, None
        self.cmp = None            # IPA âm bạn nói (dạng Apple), để bấm M
        print(f"\n── Từ #{len(self.history) + 1} ──  🔊")
        who = self.speaker.say(self.word)
        if who == "máy" and has_recording(self.word):
            print(paint(f"  (giọng máy: {self.speaker.last_error or 'chưa tải được bản ghi'})", "dim"))
        self.session.log({"event": "guess_target", "word": self.word, "audio": self.speaker.source(self.word)
                          if who == "người" else f"say:{self.speaker.voice}"})
        if self.pool:
            self.speaker.prefetch(self.pool[-1])     # tải sẵn bản ghi từ kế tiếp ở nền

    def _close_word(self):
        if self.word:
            self.history.append((self.word, self.best, self.tries, self.correct))
            self.word = None

    def reveal(self):
        if not self.word:
            return
        e = WORDS[self.word]
        ipa = "  ".join("/" + p + "/" for p in dict.fromkeys(e["ipa"]))
        print(f"  ➜ {paint(self.word, 'bold')}  {ipa}  →  {e['vi']}")
        if self.last:
            mine, k, hkey, rkey, pairs = self.last
            top, bot = show_aligned(mine, e["ph"][k], hkey, rkey, pairs)
            print(f"     chuẩn : {top}\n     bạn   : {bot}")
        src = self.speaker.source(self.word)
        if src and not self.revealed and self.speaker.who.get(self.word) == "người":
            print(paint(f"     bản ghi: {src} (Wikimedia Commons)", "dim"))
        if not self.revealed:
            self.session.log({"event": "guess_reveal", "word": self.word, "best": round(self.best * 100),
                              "tries": self.tries})
        self.revealed = True

    def on_key(self, ch: str):
        if not self.word and ch != "n":
            return
        if ch == "r":
            self.speaker.say(self.word)
        elif ch == "s":
            self.speaker.say(self.word, slow=True)
        elif ch in ("a", "\n"):
            self.reveal()
        elif ch == "n":
            self.new_word()
        elif ch == "m":
            if not self.cmp:
                print("  Nói thử trước đã (giữ Space), rồi bấm M để nghe âm của bạn và âm chuẩn.")
            elif self.speaker.say_compare(self.cmp, self.word):
                print("  🔊 âm của bạn (giọng máy) … rồi bản ghi chuẩn")
            else:
                print("  (Không đọc được IPA: cần macOS + Xcode Command Line Tools để biên dịch ipa_say.swift.)")
        elif ch in ("h", "?"):
            print(paint(GUESS_KEYS, "dim"))

    def on_audio(self, audio: np.ndarray) -> dict:
        info = {"target": self.word,
                "seconds": round(len(audio) / SR, 2),
                "peak": round(float(np.abs(audio).max()) if len(audio) else 0.0, 4)}
        if not self.word:
            return info
        if info["peak"] < MIN_PEAK:
            print("  Không nghe rõ (quá nhỏ), thử nói to và gần micro hơn.")
            info["error"] = "too_quiet"
            return info
        raw = recognize(pad_audio(audio))
        info["raw"] = [(p, round(c * 100)) for p, c in raw]
        heard = [p for p, _ in ipa_us.from_model(raw)]
        if not heard:
            print("  Không nghe rõ, thử nói to và gần micro hơn.")
            info["error"] = "no_phones"
            return info
        sim, k, mine, hkey, rkey, pairs = score_against(heard, self.word)
        self.tries += 1
        self.best = max(self.best, sim)
        self.last = (mine, k, hkey, rkey, pairs)
        # Để bấm M: đọc lại đúng các âm model nghe được, rồi âm chuẩn, cùng một giọng máy.
        # Trọng âm của bạn: lấy theo nguyên âm gióng với nguyên âm nhấn của từ chuẩn.
        ref = WORDS[self.word]["ph"][k]
        rs = stressed_vowel(WORDS[self.word]["ipa"][k], ref)
        ms = next((i for i, j in pairs if j == rs and i is not None and mine[i] in ipa_us.VOWELS), None)
        self.cmp = apple_ipa(mine, ms)
        self.speaker.prefetch_ipa(self.cmp)
        # Chấm CTC cả từ điển (chính xác hơn so chuỗi âm: âm model không chắc vẫn được tính, xem mục 3b):
        # từ đích đứng đầu = model nhận ra đúng từ bạn nói, kể cả khi % âm chưa cao.
        rec = load_model()
        rank = None
        if rec.evidence and os.environ.get("V2I_MATCH", "ctc") != "edit":
            total, _ = lex_totals(rec.evidence)
            rank = int((total > total[WORD_INDEX[self.word]]).sum()) + 1
            heard_as = WORD_LIST[int(total.argmax())]
        else:
            _, matches = match(raw, top=1)
            heard_as = matches[0][0] if matches else ""
        correct = sim >= AUTO_REVEAL or rank == 1
        pct = round(sim * 100)
        print(f"  Lần {self.tries}: /{''.join(mine)}/  {paint(f'{pct}%', _score_style(sim))}"
              f"   (cao nhất {round(self.best * 100)}%)")
        hint = (paint("model nhận ra đúng từ ✓", "ok") if rank == 1
                else f"model nghe giống: {heard_as}" + (f" · từ đích xếp hạng {rank}" if rank else ""))
        print(f"          {show_mine(mine, hkey, rkey, pairs)}   {hint}")
        info.update({"ipa": "".join(mine), "score": pct, "variant": k, "heard_as": heard_as,
                     "rank": rank, "correct": correct})
        if correct and not self.correct:
            self.correct = True
            print(paint("  ✓ Chính xác!", "ok"))
            if not self.revealed:
                self.reveal()
            print(paint("  [N] từ mới  [Space] nói lại  [R] nghe lại", "dim"))
        return info

    def summary(self):
        self._close_word()
        done = [h for h in self.history if h[2]]
        if not done:
            return
        avg = sum(b for _, b, _, _ in done) / len(done)
        good = sum(1 for *_, ok in done if ok)
        print(f"\nĐã luyện {len(done)} từ: nói đúng {good} từ, % âm cao nhất trung bình {round(avg * 100)}%.")
        weak = sorted((h for h in done if not h[3]), key=lambda h: h[1])[:5]
        if weak:
            print("Cần luyện thêm: " + ", ".join(f"{w} ({round(b * 100)}%)" for w, b, _, _ in weak))
        self.session.log({"event": "guess_summary", "words": len(done), "good": good,
                          "avg": round(avg * 100)})


# ---------- 7b. Game leo tháp (--game) ----------
# Như --guess, nhưng có nhân vật leo tháp (vẽ bằng tower.py): bắt đầu ở tầng 50, lên 100 thắng, rơi về 0 thua.
GAME_NEAR = 0.6            # % âm từ mức này tới dưới AUTO_REVEAL: gần đúng, đứng yên; thấp hơn: rơi 1 tầng
GAME_KEYS = ("[giữ Space] nói  [C] cược  [R] nghe lại  [S] nghe chậm  [M] so âm bạn ↔ chuẩn  [A] đáp án"
             "  [N] từ mới  [Esc] thoát")


def is_hard(w: str) -> bool:
    """Từ khó (để cược) = từ có 2 âm tiết trở lên (đếm nguyên âm trong cách đọc đầu tiên)."""
    return sum(1 for p in WORDS[w]["ph"][0] if p in ipa_us.VOWELS) >= 2


class GameMode(GuessMode):
    """Mỗi lần nói một từ: đúng ngay lần đầu +2 tầng, đúng sau vài lần +1, gần đúng đứng yên, sai rơi 1 tầng.
    Xem đáp án (A) hay bỏ qua (N) khi chưa nói đúng: −2 tầng, mất combo; sau A luyện tự do, không thưởng phạt.
    Mỗi 5 từ đúng ngay lần đầu nhặt 1 lượt cược; [C] cược trước lần nói đầu (luật ở tower.py: BET, GIVE_UP).
    Khi chạy, mọi print() hiện ở khung log bên phải; lỗi của thư viện ghi vào logs/<phiên>.stderr.log."""

    def __init__(self, session: "Session", level: str):
        import tower
        super().__init__(session, level)
        self.tower = tower.Tower(sfx=tower.play_sfx, on_over=self._over)
        self.screen = tower.Screen(self.tower, self.hud, GAME_KEYS,
                                   stderr_path=os.path.join(HERE, "logs", session.name + ".stderr.log"),
                                   paused=self._freeze)
        self.ptt: "PushToTalk | None" = None   # main() gán, để hiện trạng thái đang ghi / đang chấm
        self.rounds = []           # [(kết quả, tầng cao nhất, số từ, điểm)]

    def _freeze(self) -> bool:
        """Đứng hình lúc ghi: mặc định chỉ khi không có rtmixer (micro qua callback Python thì
        mỗi khung vẽ làm mất mẫu -> lách tách). V2I_FREEZE=1: luôn, V2I_FREEZE=0: không bao giờ."""
        p = self.ptt
        if not (p and p.recording):
            return False
        f = os.environ.get("V2I_FREEZE")
        return f == "1" if f in ("0", "1") else not p.c_capture

    def intro(self):
        import tower
        self.screen.start()
        t = self.tower
        print(paint("LEO THÁP", "bold") + f" · mức {self.level} · {len(self.pool)} từ"
              f" · giọng {self.speaker.voice or 'mặc định'}")
        print(paint(f"  Bắt đầu ở tầng {t.start}: lên tầng {t.goal} là thắng, rơi về 0 (dung nham) là thua.", "dim"))
        print(paint(f"  Đúng ngay lần đầu +2 tầng · đúng +1 · gần đúng ({round(GAME_NEAR * 100)}–"
                    f"{round(AUTO_REVEAL * 100) - 1}%) đứng yên · sai rơi 1 tầng.", "dim"))
        (ew, el), (hw, hl) = tower.BET[False], tower.BET[True]
        print(paint(f"  [A] đáp án / [N] bỏ từ khi chưa đúng: −{tower.GIVE_UP} tầng (sau đó luyện thoải mái,"
                    " không bị trừ).", "dim"))
        print(paint(f"  Mỗi {tower.MILESTONE} từ đúng ngay lần đầu: +1 lượt cược. [C] cược trước khi nói:"
                    f" từ dễ (1 âm tiết) +{ew}/−{el}, từ khó +{hw}/−{hl}, gần đúng thì mất lượt.", "dim"))
        if not can_listen_keys():
            print(paint("  ⚠ Terminal chưa có quyền Input Monitoring: không bắt được lúc nhả Space.", "bad"))
        self.session.log({"event": "game_start", "level": self.level, "start": t.start, "goal": t.goal})

    def hud(self) -> list[str]:
        p = self.ptt
        if p and p.recording:
            status = paint("● ĐANG GHI", "bad")
        elif p and p.busy:
            status = paint("… đang chấm", "near")
        elif self.tower.over:
            status = paint("[N] chơi lại", "bold")
        else:
            status = paint("🔊 nghe rồi giữ Space nói lại", "dim")
        return ["", status]

    def new_word(self):
        super().new_word()
        if self.word:
            self.tower.begin_word(is_hard(self.word))

    def on_key(self, ch: str):
        t = self.tower
        if t.over:
            if ch == "n":
                import time
                t.reset(time.monotonic())
                print(paint(f"\n══ Chơi lại từ tầng {t.start} ══", "bold"))
                super().on_key("n")
            elif ch != "a":
                super().on_key(ch)             # vẫn nghe lại / so âm từ cuối được
            return
        if ch == "c":
            self._bet()
            return
        if self.word and not self.correct and ch in ("n", "a", "\n"):
            ev = t.give_up(peek=ch != "n")
            if ev:
                print(paint(f"  Bỏ từ: −{ev[1]} tầng." + (" Giờ luyện thoải mái, không bị trừ nữa." if ch != "n" else ""),
                            "bad"))
                self.session.log({"event": "game_giveup", "word": self.word, "floors": ev[1],
                                  "key": "N" if ch == "n" else "A"})
                t.push(ev)
        super().on_key(ch)

    def _bet(self):
        t = self.tower
        why = t.place_bet()
        if why:
            print(paint(f"  Không cược được: {why}.", "dim"))
            return
        win, lose = t.bet_odds()
        kind = "khó" if t.cur.hard else "dễ"
        print(paint(f"  🎲 Đã cược từ {kind}: nói đúng ngay +{win} tầng, sai −{lose}, gần đúng mất lượt.", "near"))
        self.session.log({"event": "game_bet", "word": self.word, "hard": t.cur.hard, "win": win, "lose": lose})
        t.push(("bet", 0, False))

    def on_audio(self, audio: np.ndarray) -> dict:
        was_correct = self.correct
        info = super().on_audio(audio)
        if "score" not in info or was_correct or self.tower.over:
            return info                        # không chấm được, đã đúng rồi (luyện thêm) hoặc đã hết ván
        result = ("correct" if info["correct"] else "near" if info["score"] >= GAME_NEAR * 100 else "bad")
        ev = self.tower.attempt(result)
        if not ev:
            return info
        if ev[0].startswith("bet_"):
            print(paint({"bet_win": f"  🎲 THẮNG CƯỢC: +{ev[1]} tầng!", "bet_lose": f"  🎲 Thua cược: −{ev[1]} tầng.",
                         "bet_near": "  🎲 Gần đúng: mất lượt cược."}[ev[0]],
                        "ok" if ev[0] == "bet_win" else "bad"))
        if ev[2]:
            print(paint(f"  ★ Đủ {self.tower.firsts} từ đúng ngay: +1 lượt cược (bấm C ở từ sau).", "ok"))
        self._push_after_playback(ev)
        info["game"] = ev[0]
        return info

    def _push_after_playback(self, ev: tuple):
        """main() đang phát lại bản ghi của bạn: đợi phát xong (hoặc bị dừng khi bạn nói tiếp) rồi mới nhảy/rơi và
        phát tiếng hiệu ứng, để tiếng hiệu ứng không đè lên giọng bạn."""
        import time
        import sounddevice as sd

        def job():
            end = time.monotonic() + 5
            try:
                while time.monotonic() < end and sd.get_stream().active:
                    time.sleep(0.03)
            except RuntimeError:               # chưa phát gì
                pass
            self.tower.push(ev)
        threading.Thread(target=job, daemon=True).start()

    def _over(self, result: str):
        """Tower gọi (luồng vẽ) khi lên tới đích hoặc rơi vào dung nham."""
        t = self.tower
        self.rounds.append((result, t.best, t.words, t.score))
        if result == "win":
            print(paint(f"\n🏆 CHIẾN THẮNG! Lên tầng {t.goal} sau {t.words} từ, {t.score} điểm.", "ok"))
        else:
            print(paint(f"\n🔥 Rơi vào dung nham sau {t.words} từ (cao nhất tầng {t.best}).", "bad"))
        print(paint("  [N] chơi lại  ·  [Esc] thoát", "dim"))
        self.session.log({"event": "game_over", "result": result, "best": t.best, "words": t.words,
                          "score": t.score})

    def summary(self):
        self.screen.stop()
        super().summary()
        t = self.tower
        for result, best, words, score in self.rounds:
            print(("Thắng" if result == "win" else "Thua") + f": {words} từ, cao nhất tầng {best}, {score} điểm")
        if not t.over and t.words:
            print(f"Ván đang chơi: tầng {t.f}/{t.goal}, cao nhất {t.best}, {t.score} điểm")


# ---------- 8. Chế độ săn từ theo âm (--hunt) ----------
# Chơi 1 mình, dạng THẮP CHÒM SAO (vẽ bằng stars.py). Người chơi chọn 1 hay vài âm (nguyên âm, phụ âm); mỗi từ
# chứa TẤT CẢ các âm đó thắp 1 ngôi sao, đủ sao thành chòm sao. Từ đã thắp không dùng lại. Tự nghĩ ra từ: sao
# sáng, đủ điểm. Bí thì bấm G: gợi ý 1 từ, đọc theo giống >= 80%: sao mờ, 1/3 điểm. Không tính giờ.
HUNT_PASS = 0.8            # gợi ý: % âm giống tối thiểu để qua
HUNT_FEW = 10              # cảnh báo khi kho từ gợi ý ít hơn số này
HUNT_KEYS = ("[giữ Space] nói 1 từ  [G] gợi ý  [R] nghe lại  [S] nghe chậm  [N] bỏ gợi ý  [L] từ đã thắp"
             "  [Esc] thoát")
HUNT_MENU = (  # (âm Cambridge US, từ ví dụ)
    ("iː", "see"), ("ɪ", "sit"), ("e", "bed"), ("æ", "cat"), ("ɑː", "hot"), ("ɔː", "four"), ("ʌ", "cup"),
    ("ʊ", "book"), ("uː", "blue"), ("ə", "about"), ("ɚ", "teacher"), ("ɝː", "bird"), ("eɪ", "day"),
    ("aɪ", "my"), ("ɔɪ", "boy"), ("oʊ", "go"), ("aʊ", "now"),
    ("p", "pen"), ("b", "bad"), ("t", "tea"), ("d", "day"), ("k", "cat"), ("ɡ", "go"), ("f", "fish"),
    ("v", "very"), ("θ", "think"), ("ð", "this"), ("s", "see"), ("z", "zoo"), ("ʃ", "she"), ("ʒ", "vision"),
    ("h", "hat"), ("tʃ", "chair"), ("dʒ", "job"), ("m", "man"), ("n", "no"), ("ŋ", "sing"), ("l", "leg"),
    ("r", "red"), ("j", "yes"), ("w", "we"),
)
_HUNT_SETS: dict[str, list[set]] = {}


def hunt_key(p: str) -> str:
    """Âm -> đơn vị so: giữ nguyên âm Cambridge (iː khác i không nhấn của happy, ɝː khác ɚ), chỉ t̬ (water) tính là t."""
    return "t" if p == "t̬" else p


def hunt_sets(w: str) -> list[set]:
    if w not in _HUNT_SETS:
        _HUNT_SETS[w] = [{hunt_key(p) for p in ph} for ph in WORDS[w]["ph"]]
    return _HUNT_SETS[w]


def hunt_variant(w: str, keys: set) -> int | None:
    """Cách đọc đầu tiên của từ chứa đủ các âm; None nếu không có."""
    return next((k for k, s in enumerate(hunt_sets(w)) if keys <= s), None)


def hunt_pool(keys: set, level: str) -> list[str]:
    lo, hi = LEVELS[level]
    return [w for w, e in WORDS.items()
            if lo <= e["zipf"] < hi and len(w) >= 3 and hunt_variant(w, keys) is not None]


def parse_sounds(text: str) -> list[str]:
    """'4 20' | 'æ,t' | 'i: tʃ' -> các âm trong HUNT_MENU (giữ thứ tự, bỏ trùng). Sai ký hiệu: ValueError."""
    alias = {"g": "ɡ", "ae": "æ", "sh": "ʃ", "ch": "tʃ", "th": "θ", "dh": "ð", "ng": "ŋ", "zh": "ʒ", "y": "j"}
    by_key = {hunt_key(p): p for p, _ in HUNT_MENU}
    out = []
    for tok in re.split(r"[\s,;/]+", text.strip()):
        if not tok:
            continue
        if tok.isdigit():
            if not 1 <= int(tok) <= len(HUNT_MENU):
                raise ValueError(f"không có số {tok}")
            p = HUNT_MENU[int(tok) - 1][0]
        else:
            t = alias.get(tok.lower(), tok).replace(":", "ː")
            p = by_key.get(hunt_key(t)) or by_key.get(t + "ː")      # i -> iː, u -> uː, ɑ -> ɑː
            if p is None:
                raise ValueError(f"không biết âm '{tok}'")
        if p not in out:
            out.append(p)
    if not out:
        raise ValueError("chưa chọn âm nào")
    return out


def choose_sounds(level: str, preset: str | None) -> list[str]:
    """Chọn âm: từ --sounds, hoặc hỏi trên terminal (chạy trước khi terminal chuyển sang chế độ bắt phím)."""
    if level not in LEVELS:
        sys.exit(f"Mức không hợp lệ: {level} (chọn {', '.join(LEVELS)})")
    if preset is None:
        if not sys.stdin.isatty():
            sys.exit("Chế độ --hunt cần terminal tương tác (hoặc chọn âm sẵn: --sounds \"æ t\").")
        cells = [f"{i:>2} {p:<3} {ex:<8}" for i, (p, ex) in enumerate(HUNT_MENU, 1)]
        nv = sum(1 for p, _ in HUNT_MENU if p in ipa_us.VOWELS)
        print("Nguyên âm:")
        for i in range(0, nv, 6):
            print("  " + "".join(cells[i:min(i + 6, nv)]))
        print("Phụ âm:")
        for i in range(nv, len(cells), 6):
            print("  " + "".join(cells[i:i + 6]))
    while True:
        text = preset if preset is not None else input(
            "Chọn 1 hay vài âm (số hoặc ký hiệu IPA, cách nhau dấu cách; vd: 4 20  hoặc  æ t): ")
        try:
            sounds = parse_sounds(text)
        except ValueError as e:
            if preset is not None:
                sys.exit(f"--sounds: {e}")
            print(f"  {e}, chọn lại.")
            continue
        n = len(hunt_pool({hunt_key(p) for p in sounds}, level))
        names = " ".join("/" + p + "/" for p in sounds)
        if n == 0:
            msg = f"Không có từ nào (mức {level}) chứa đủ {names}"
            if preset is not None:
                sys.exit(msg + ".")
            print(f"  {msg}, bớt âm hoặc chọn mức khác.")
            continue
        print(f"Âm đã chọn: {names} · {n} từ mức {level} chứa đủ các âm này."
              + (" (ít từ gợi ý)" if n < HUNT_FEW else ""))
        return sounds


def after_playback(fn):
    """main() đang phát lại bản ghi của bạn: đợi phát xong (hoặc bị dừng khi bạn nói tiếp) rồi mới chạy fn
    (hoạt hình + tiếng hiệu ứng), để tiếng hiệu ứng không đè lên giọng bạn."""
    import time
    import sounddevice as sd

    def job():
        end = time.monotonic() + 5
        try:
            while time.monotonic() < end and sd.get_stream().active:
                time.sleep(0.03)
        except RuntimeError:                   # chưa phát gì
            pass
        fn()
    threading.Thread(target=job, daemon=True).start()


def hunt_points(w: str, keys: set) -> tuple[int, int]:
    """(điểm khi tự nói ra từ, tier). Nhiều âm mục tiêu, ít gặp (zipf thấp), dài: nhiều điểm hơn.
    tier 3 = từ khó (ít gặp hoặc dài) -> sao vàng; tier 2 = sao trắng."""
    k = hunt_variant(w, keys) or 0
    ph = WORDS[w]["ph"][k]
    hits = sum(1 for p in ph if hunt_key(p) in keys)
    zipf = WORDS[w]["zipf"]
    pts = 10 * max(1, hits) * (1 + max(0.0, 5.5 - zipf) * 0.5) * (1 + max(0, len(ph) - 4) * 0.1)
    return round(pts), 3 if zipf < 4.0 or len(ph) >= 7 else 2


class HuntMode:
    """Chơi 1 mình: mỗi từ chứa đủ các âm đã chọn thắp 1 ngôi sao trên bầu trời (vẽ bằng stars.py); đủ sao thì
    thành chòm sao. Tự nghĩ ra từ: sao sáng, đủ điểm. Bí: G gợi ý 1 từ, đọc theo >= HUNT_PASS: sao mờ, 1/3 điểm.
    Không tính giờ, nói sai không mất gì. Giao diện giống GuessMode để main() dùng chung:
    intro, new_word, on_key, on_audio, summary, speaker, word (tên file bản ghi), ptt."""

    def __init__(self, session: "Session", level: str, sounds: list[str]):
        import random
        import stars
        self.session, self.level, self.sounds = session, level, sounds
        self.keys = {hunt_key(p) for p in sounds}
        self.pool = hunt_pool(self.keys, level)          # kho từ để gợi ý (theo mức)
        random.shuffle(self.pool)
        self.speaker = Speaker()
        self.used: dict[str, str] = {}                   # từ -> cách thắp: bạn | gợi ý | bỏ (gợi ý bỏ qua)
        self.state = "free"                              # free: tự nói | hint: đọc theo gợi ý
        self.word = self.last = self.hint = None         # word: từ đang xét (đặt tên file bản ghi)
        self.tries, self.best, self.misses = 0, 0.0, 0
        self.names = " ".join("/" + p + "/" for p in sounds)
        self.sky = stars.Sky(sounds=self.names, sfx=stars.sfx)
        self.sky.on_done = self._constellation_done
        self.screen = stars.SkyScreen(self.sky, self.hud, HUNT_KEYS,
                                      stderr_path=os.path.join(HERE, "logs", session.name + ".stderr.log"),
                                      paused=lambda: GameMode._freeze(self))
        self.ptt: "PushToTalk | None" = None
        session.log({"event": "hunt_start", "level": level, "sounds": sounds, "pool": len(self.pool)})

    def intro(self):
        self.screen.start()
        print(paint("THẮP CHÒM SAO", "bold") + f" · âm {self.names} · mức {self.level}"
              f" ({len(self.pool)} từ để gợi ý)")
        print(paint(f"  Mỗi từ chứa đủ {self.names} thắp 1 ngôi sao; đủ sao thành chòm sao. Không tính giờ,"
                    " nói sai không mất gì.", "dim"))
        print(paint("  Tự nghĩ ra từ: sao sáng, đủ điểm (từ khó: sao vàng). Bí: [G] gợi ý 1 từ, đọc theo giống"
                    f" >= {round(HUNT_PASS * 100)}%: sao mờ, 1/3 điểm.", "dim"))
        if not can_listen_keys():
            print(paint("  ⚠ Terminal chưa có quyền Input Monitoring: không bắt được lúc nhả Space.", "bad"))
        self._prepare_next()

    def hud(self) -> list[str]:
        p = self.ptt
        if p and p.recording:
            status = paint("● ĐANG GHI", "bad")
        elif p and p.busy:
            status = paint("… đang chấm", "near")
        elif self.state == "hint":
            status = paint("Đọc theo: ", "dim") + paint(self.hint, "bold") + paint("  [N] bỏ gợi ý", "dim")
        else:
            status = paint(f"Giữ Space, nói 1 từ chứa {self.names}", "dim")
        return ["", status]

    # --- chọn từ gợi ý ---
    def _free(self) -> list[str]:
        return [w for w in self.pool if w not in self.used]

    def _pick(self, avoid: str | None = None) -> str | None:
        """Ưu tiên từ đã tải bản ghi, rồi từ có bản ghi trên Commons, cuối cùng từ chỉ đọc được bằng giọng máy."""
        free = [w for w in self._free() if w != avoid] or self._free()
        if not free:
            return None
        return (next((w for w in free if os.path.exists(Speaker.path(w))), None)
                or next((w for w in free if w in AUDIO_US), None) or free[0])

    def _prepare_next(self):
        """Tải sẵn bản ghi từ gợi ý kế tiếp ở nền."""
        w = self._pick(avoid=self.hint)
        if w:
            self.speaker.prefetch(w)

    def _hint_word(self) -> str | None:
        return self._pick(avoid=self.hint)

    # --- hiển thị ---
    def _ipa_marked(self, w: str) -> str:
        """IPA Cambridge của từ, tô đậm các âm đã chọn."""
        k = hunt_variant(w, self.keys)
        k = 0 if k is None else k
        ipa, ph = WORDS[w]["ipa"][k], WORDS[w]["ph"][k]
        out, pos = [], 0
        for p in ph:
            while pos < len(ipa) and ipa[pos] in "ˈˌ.":
                out.append(ipa[pos])
                pos += 1
            if not ipa.startswith(p, pos):
                return ipa                                   # không gióng được: in nguyên
            out.append(paint(p, "ok") if hunt_key(p) in self.keys else p)
            pos += len(p)
        return "".join(out) + ipa[pos:]

    def _card(self, w: str) -> str:
        return f"{paint(w, 'bold')}  /{self._ipa_marked(w)}/  →  {WORDS[w]['vi']}"

    def _speak(self, w: str, slow: bool = False):
        self.speaker.say(w, slow)

    def _lit(self) -> int:
        return sum(1 for who in self.used.values() if who != "bỏ")

    # --- lượt ---
    def new_word(self):
        """Mời nói từ cho ngôi sao kế tiếp (không có lượt máy)."""
        self.state, self.hint, self.tries, self.best = "free", None, 0, 0.0
        print("\n" + paint(f"── Sao #{self._lit() + 1} ──", "bold")
              + paint(f"  giữ Space nói 1 từ chứa {self.names}  ·  bí thì [G] gợi ý", "dim"))

    def give_hint(self):
        w = self._hint_word()
        if not w:
            print("  Hết từ để gợi ý ở mức này: tự nghĩ thêm nhé.")
            return
        if self.state == "hint" and self.hint:
            self.used[self.hint] = "bỏ"
        self.state, self.hint, self.word, self.best, self.tries = "hint", w, w, 0.0, 0
        print("  " + paint("[G] Gợi ý: ", "dim") + self._card(w) + "  🔊")
        print(paint(f"  Đọc theo (giữ Space), cần >= {round(HUNT_PASS * 100)}%.  [R] nghe lại  [S] nghe chậm"
                    "  [G] từ khác  [N] bỏ gợi ý", "dim"))
        self._speak(w)
        self.session.log({"event": "hunt_hint", "word": w})
        self._prepare_next()

    def on_key(self, ch: str):
        if ch in ("h", "?"):
            print(paint(HUNT_KEYS, "dim"))
        elif ch == "l":
            lit = [f"{w}" + ("" if who == "bạn" else " (gợi ý)") for w, who in self.used.items() if who != "bỏ"]
            print("  Đã thắp: " + (", ".join(lit) if lit else "chưa có từ nào"))
        elif ch in ("r", "s"):
            target = self.hint if self.state == "hint" else self.last
            if target:
                self._speak(target, slow=ch == "s")
        elif ch == "g":
            self.give_hint()
        elif ch == "n" and self.state == "hint":
            self.used[self.hint] = "bỏ"
            print(paint("  Bỏ gợi ý, tự nghĩ từ khác.", "dim"))
            self.session.log({"event": "hunt_skip_hint", "word": self.hint})
            self.new_word()

    # --- người nói ---
    def _recognize(self, raw) -> list[str]:
        """Các từ model nghe giống nhất (chấm CTC cả từ điển), xếp từ cao xuống."""
        rec = load_model()
        if rec.evidence and os.environ.get("V2I_MATCH", "ctc") != "edit":
            total, _ = lex_totals(rec.evidence)
            return [WORD_LIST[i] for i in np.argsort(-total)[:5]]
        _, matches = match(raw, top=5)
        return [w for w, _, _ in matches]

    def on_audio(self, audio: np.ndarray) -> dict:
        info = {"state": self.state, "seconds": round(len(audio) / SR, 2),
                "peak": round(float(np.abs(audio).max()) if len(audio) else 0.0, 4)}
        if info["peak"] < MIN_PEAK:
            print("  Không nghe rõ (quá nhỏ), thử nói to và gần micro hơn.")
            info["error"] = "too_quiet"
            return info
        raw = recognize(pad_audio(audio))
        info["raw"] = [(p, round(c * 100)) for p, c in raw]
        heard = [p for p, _ in ipa_us.from_model(raw)]
        if not heard:
            print("  Không nghe rõ, thử nói to và gần micro hơn.")
            info["error"] = "no_phones"
            return info
        self.tries += 1
        if self.state == "hint":
            return self._judge_hint(heard, info)
        return self._judge_own(raw, heard, info)

    def _push(self, kind: str, w: str = "", pts: int = 0, tier: int = 2):
        """Đợi phát lại bản ghi của bạn xong rồi mới cho sao bay (tiếng hiệu ứng không đè giọng bạn)."""
        after_playback(lambda: self.sky.push(kind, w, pts, tier))

    def _judge_hint(self, heard: list[str], info: dict) -> dict:
        sim, k, mine, hkey, rkey, pairs = score_against(heard, self.hint)
        self.best = max(self.best, sim)
        pct = round(sim * 100)
        ok = sim >= HUNT_PASS
        print(f"  Lần {self.tries}: /{''.join(mine)}/  {paint(f'{pct}%', 'ok' if ok else _score_style(sim))}"
              f"   (cao nhất {round(self.best * 100)}%)")
        print(f"          {show_mine(mine, hkey, rkey, pairs)}")
        info.update({"target": self.hint, "ipa": "".join(mine), "score": pct, "passed": ok})
        if ok:
            w = self.hint
            pts = max(3, round(hunt_points(w, self.keys)[0] / 3))
            self.used[w] = "gợi ý"
            self.last = w
            print(paint("  ✓ Đọc đúng: sao mờ ✧", "ok") + f"  {paint(f'+{pts}', 'bold')}")
            self._push("hint", w, pts, 1)
            info.update({"verdict": "hint_ok", "points": pts})
            self.new_word()
        else:
            print(paint(f"  Chưa đủ {round(HUNT_PASS * 100)}%: đọc lại (giữ Space), [R] nghe lại,"
                        " [G] từ khác, [N] bỏ gợi ý.", "dim"))
        return info

    def _judge_own(self, raw, heard: list[str], info: dict) -> dict:
        top = self._recognize(raw)
        if not top:
            print("  Không nhận ra từ nào, thử lại.")
            info["error"] = "no_match"
            return info
        scored = {}
        for x in top[:3]:
            scored[x] = score_against(heard, x)
        # model hay xếp từ hiếm thấp: nhận từ hợp lệ trong 3 từ đầu nếu âm giống đủ
        w = next((x for x in top[:3] if x not in self.used and hunt_variant(x, self.keys) is not None
                  and (x == top[0] or scored[x][0] >= HUNT_PASS)), top[0])
        sim, k, mine, hkey, rkey, pairs = scored[w]
        pct = round(sim * 100)
        others = [x for x in top[:4] if x != w]
        print(f"  Lần {self.tries}: /{''.join(mine)}/  → model nghe: {paint(w, 'bold')} "
              f"{paint(f'({pct}% âm)', _score_style(sim))}"
              + paint(f"   khác: {', '.join(others)}" if others else "", "dim"))
        info.update({"heard_as": w, "top": top, "ipa": "".join(mine), "score": pct})
        self.word = w
        if w in self.used and self.used[w] != "bỏ":
            print(paint(f"  ✗ '{w}' đã thắp rồi. Nói từ khác.", "bad"))
            info["verdict"] = "used"
            self.misses += 1
            self._push("used", w)
        elif hunt_variant(w, self.keys) is None:
            missing = [p for p in self.sounds if hunt_key(p) not in set().union(*hunt_sets(w))]
            print(paint(f"  ✗ '{w}' /{WORDS[w]['ipa'][0]}/ thiếu âm " + " ".join(f"/{p}/" for p in missing)
                        + ". Thử từ khác (không mất gì), hoặc [G] gợi ý.", "bad"))
            info["verdict"] = "missing"
            self.misses += 1
            self._push("miss", w)
        else:
            pts, tier = hunt_points(w, self.keys)
            bonus = 5 if sim >= AUTO_REVEAL else 0
            self.used[w] = "bạn"
            self.last = w
            print(paint("  ✓ Sao vàng (từ khó)!" if tier == 3 else "  ✓ Sao sáng!", "ok") + "  " + self._card(w)
                  + "  " + paint(f"+{pts + bonus}", "bold") + (paint("  (phát âm chuẩn +5)", "dim") if bonus else ""))
            self._push("own", w, pts + bonus, tier)
            info.update({"verdict": "ok", "points": pts + bonus, "tier": tier})
            self.new_word()
        return info

    def _constellation_done(self, name: str, n: int):
        """Sky gọi (luồng vẽ) khi thắp xong 1 chòm."""
        print(paint(f"\n✧ Thắp xong chòm {name}: {n} sao ✧", "ok"))
        self.session.log({"event": "hunt_constellation", "name": name, "stars": n})

    def summary(self):
        self.screen.stop()
        s = self.sky
        own = [w for w, who in self.used.items() if who == "bạn"]
        hinted = [w for w, who in self.used.items() if who == "gợi ý"]
        if not own and not hinted:
            return
        print(f"\nThắp chòm sao {self.names}: {s.done} chòm, {len(own)} sao sáng (tự nghĩ),"
              f" {len(hinted)} sao mờ (gợi ý) · {s.score} điểm.")
        if own:
            print("  Từ bạn tìm: " + ", ".join(own))
        if hinted:
            print("  Từ gợi ý:   " + ", ".join(hinted))
        self.session.log({"event": "hunt_summary", "own": own, "hinted": hinted, "misses": self.misses,
                          "constellations": s.done, "score": s.score})


def main(mode: str = "lookup", level: str = "mid", sounds: list[str] | None = None):
    import logging
    import sounddevice as sd
    from pynput import keyboard

    logging.getLogger("pynput").setLevel(logging.ERROR)   # ẩn cảnh báo "not trusted" sai

    load_model()
    recognize(pad_audio(np.zeros(SR, np.float32)))     # chạy thử 1 lần để lần ghi đầu không bị chậm
    session = Session()
    game = (GuessMode(session, level) if mode == "guess"
            else GameMode(session, level) if mode == "game"
            else HuntMode(session, level, sounds) if mode == "hunt" else None)

    fd = sys.stdin.fileno() if sys.stdin.isatty() else None
    ptt = PushToTalk(local_only=fd is not None)
    if game:
        ptt.on_start = game.speaker.stop
        game.ptt = ptt
    old_tty = None
    if fd is not None:
        import termios
        old_tty = termios.tcgetattr(fd)
        new = termios.tcgetattr(fd)
        new[3] &= ~(termios.ECHO | termios.ICANON)   # không in dấu cách ra màn hình
        new[6][termios.VMIN] = 1
        new[6][termios.VTIME] = 0
        termios.tcsetattr(fd, termios.TCSANOW, new)

    listener = keyboard.Listener(on_press=ptt.on_press, on_release=ptt.on_release)
    try:
        stream = open_mic(ptt)
        with stream:
            listener.start()
            listener.wait()
            trusted = can_listen_keys()
            if not trusted:
                print("⚠ Terminal chưa có quyền Input Monitoring nên không bắt được lúc nhả phím.\n"
                      "  Bật trong System Settings > Privacy & Security > Input Monitoring,\n"
                      "  rồi mở lại terminal.")
            if fd is not None:
                threading.Thread(target=ptt.read_stdin, args=(fd, trusted),
                                 daemon=True).start()
            print(f"\nBản ghi: recordings/{session.name}/   Log: logs/{session.name}.log")
            if game:
                if fd is None:
                    print("⚠ Không có terminal tương tác: không bấm được phím lệnh.")
                game.intro()
                game.new_word()
            else:
                print("Giữ SPACE (trong cửa sổ này) để nói 1 từ tiếng Anh, nhả ra để dừng."
                      " Esc / Ctrl+C để thoát.\n")
            while True:
                audio = ptt.jobs.get()
                if audio is None:
                    break
                if isinstance(audio, tuple):           # ("key", ký tự): phím lệnh
                    if game and not ptt.recording:
                        game.on_key(audio[1])
                    continue
                try:
                    if len(audio) < SR * MIN_SECONDS:
                        print("  Quá ngắn, giữ SPACE lâu hơn.\n")
                        session.log({"event": "too_short", "seconds": round(len(audio) / SR, 2)})
                    else:
                        sd.play(audio, SR)     # phát lại bản ghi (chạy nền, song song với phân tích)
                        try:
                            info = game.on_audio(audio) if game else analyze(audio)
                        except Exception as e:
                            import traceback
                            print(f"  Lỗi: {e}\n")
                            info = {"error": repr(e), "traceback": traceback.format_exc()}
                        session.save(audio, info, label=game.word if game else None)
                finally:
                    if fd is not None:
                        termios.tcflush(fd, termios.TCIFLUSH)
                    ptt.busy = False
    except KeyboardInterrupt:
        pass
    finally:
        listener.stop()
        if old_tty is not None:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_tty)
        if game:
            game.speaker.stop()
            game.summary()
        session.log({"event": "end", "takes": session.n})
        print("Tạm biệt!")


def analyze_files(paths: list[str]):
    """Chạy lại nhận dạng trên các file WAV đã lưu, để so sánh các lần ghi."""
    load_model()
    for path in paths:
        print(f"== {path}")
        analyze(read_wav(path))


FETCH_PACE = 1.0           # giây nghỉ giữa 2 lần tải (upload.wikimedia.org chặn nếu tải dồn)


def fetch_audio(level: str):
    """Tải dần bản ghi giọng Mỹ của các từ ở 1 mức vào data/audio/ (từ phổ biến trước), để lúc chơi chạy offline.
    Bị chặn (429) thì chờ hết thời gian máy chủ yêu cầu. Ctrl+C để dừng, lần sau chạy lại sẽ làm tiếp."""
    import time
    if level not in LEVELS:
        sys.exit(f"Mức không hợp lệ: {level} (chọn {', '.join(LEVELS)})")
    lo, hi = LEVELS[level]
    words = sorted((w for w, e in WORDS.items() if lo <= e["zipf"] < hi and len(w) >= 3 and w in AUDIO_US),
                   key=lambda w: -WORDS[w]["zipf"])
    sp = Speaker()
    todo = [w for w in words if not os.path.exists(sp.path(w))]
    print(f"Mức {level}: {len(words)} từ có bản ghi, cần tải {len(todo)}.")
    try:
        i = 0
        while i < len(todo):
            if not sp.fetch(todo[i]) and time.time() < sp.blocked_until:
                wait = sp.blocked_until - time.time()
                print(f"\r  {sp.last_error}: chờ {int(wait)} s…".ljust(70), end="", flush=True)
                time.sleep(wait)
                continue
            i += 1
            print(f"\r  tải {i}/{len(todo)}".ljust(70), end="", flush=True)
            time.sleep(FETCH_PACE)
        print()
    except KeyboardInterrupt:
        print("\n  Dừng. Chạy lại lệnh này để tải tiếp.")
    have = sum(1 for w in words if os.path.exists(sp.path(w)))
    print(f"Mức {level}: đã có {have}/{len(words)} bản ghi trong {AUDIO_DIR}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--model" in args:                       # --model koel | zipa | xlsr
        k = args.index("--model")
        MODEL_KIND = args[k + 1] if k + 1 < len(args) else ""
        del args[k:k + 2]
    level = "mid"
    if "--level" in args:                       # --level easy | mid | hard | all (chế độ đoán từ)
        k = args.index("--level")
        level = args[k + 1] if k + 1 < len(args) else ""
        del args[k:k + 2]
    sounds = None
    if "--sounds" in args:                      # --sounds "æ t" (chế độ săn từ, bỏ qua bước hỏi)
        k = args.index("--sounds")
        sounds = args[k + 1] if k + 1 < len(args) else ""
        del args[k:k + 2]
    mode = "lookup"
    if "--guess" in args:
        args.remove("--guess")
        mode = "guess"
    if "--game" in args:                        # --guess dạng game leo tháp (--guess đi kèm hay không đều được)
        args.remove("--game")
        mode = "game"
    if "--hunt" in args:
        args.remove("--hunt")
        mode = "hunt"
    if "--fetch-audio" in args:                 # tải sẵn bản ghi của 1 mức để chơi offline
        fetch_audio(level)
    elif args:
        analyze_files(args)
    else:
        main(mode, level, choose_sounds(level, sounds) if mode == "hunt" else None)
