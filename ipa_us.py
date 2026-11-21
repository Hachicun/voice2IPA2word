"""
Chuẩn hoá IPA về một kiểu duy nhất: tiếng Anh Mỹ theo cách ghi của Cambridge Dictionary (US).

Bộ ký hiệu Cambridge US:
  Nguyên âm   iː ɪ e æ ɑː ɔː ʌ ʊ uː ə ɚ ɝː i u   (i, u: không nhấn, vd happy /ˈhæp.i/)
  Nguyên âm đôi eɪ aɪ ɔɪ oʊ aʊ
  Phụ âm      p b t d k ɡ f v θ ð s z ʃ ʒ h tʃ dʒ m n ŋ l r j w, t̬ (t bật nhẹ kiểu Mỹ: water /ˈwɑː.t̬ɚ/)
  Trọng âm ˈ ˌ đặt ở đầu âm tiết, dấu chấm . ngăn âm tiết.
  Mỹ: 'caught', 'law' dùng ɑː; ɔː chỉ đứng trước r ('four' /fɔːr/).

Ba nguồn IPA, mỗi nguồn một kiểu ghi, đều được đổi về bộ ký hiệu trên:
  - CMUdict (ARPAbet, có trọng âm 0/1/2): nguồn chính cho từ điển.
  - espeak en-us: dự phòng cho từ CMUdict không có (vd colour, organised); cũng là kiểu ghi của model XLSR.
  - ZIPA: phiên âm hẹp, đa ngôn ngữ: không dấu dài, 'g' ASCII, 'ɹ', 'ɛ', r-hoá bằng '˞' (ə˞, ɔ˞),
    nguyên âm đôi tách 2 token (e ɪ, o ʊ), 'o' đứng một mình = /oʊ/, 'a' dùng cho cả /ʌ/ lẫn /ɑː/.
    Model không cho biết trọng âm nên IPA của model chỉ có âm, không có ˈ và dấu chấm.
"""
import re

VOWELS = {"iː", "ɪ", "e", "æ", "ɑː", "ɔː", "ʌ", "ʊ", "uː", "ə", "ɚ", "ɝː", "i", "u",
          "eɪ", "aɪ", "ɔɪ", "oʊ", "aʊ", "a", "ɔ"}
# Hai ký hiệu chỉ có ở IPA của model ZIPA, mỗi cái ứng với vài âm Cambridge:
#   'a' = /ʌ/ (cup, judge) hoặc /ɑː/ (hot, mom);  'ɔ' (không đứng trước r) = /ɑː/ (caught), /oʊ/ (golden)...
SHORT = {"ɪ", "e", "æ", "ʌ", "ʊ"}

# ---------- 1. CMUdict (ARPAbet) ----------
_ARPA_CONS = {"B": "b", "CH": "tʃ", "D": "d", "DH": "ð", "F": "f", "G": "ɡ", "HH": "h", "JH": "dʒ",
              "K": "k", "L": "l", "M": "m", "N": "n", "NG": "ŋ", "P": "p", "R": "r", "S": "s",
              "SH": "ʃ", "T": "t", "TH": "θ", "V": "v", "W": "w", "Y": "j", "Z": "z", "ZH": "ʒ"}
_ARPA_VOW = {"AA": "ɑː", "AE": "æ", "AW": "aʊ", "AY": "aɪ", "EH": "e", "EY": "eɪ", "IH": "ɪ",
             "OW": "oʊ", "OY": "ɔɪ", "UH": "ʊ"}


def from_arpabet(arpa: list[str]) -> list[tuple[str, int | None]]:
    """['W','AO1','T','ER0'] -> [('w',None),('ɑː',1),('t̬',None),('ɚ',0)]  (âm, trọng âm; None = phụ âm)."""
    segs = []
    for k, p in enumerate(arpa):
        nxt = arpa[k + 1] if k + 1 < len(arpa) else ""
        base, st = (p[:-1], int(p[-1])) if p[-1].isdigit() else (p, None)
        if st is None:
            segs.append((_ARPA_CONS.get(base, base.lower()), None))
            continue
        if base == "AH":
            v = "ə" if st == 0 else "ʌ"
        elif base == "AO":
            v = "ɔː" if nxt == "R" else "ɑː"                 # Mỹ: caught /kɑːt/, four /fɔːr/
        elif base == "ER":
            if st == 0 and segs and segs[-1][0] in ("aɪ", "aʊ") and not (nxt and nxt[-1].isdigit()):
                segs.append(("r", None))                   # fire /faɪr/, hour /aʊr/
                continue
            v = "ɚ" if st == 0 else "ɝː"
        elif base == "IY":
            v = "i" if st == 0 else "iː"
        elif base == "UW":
            v = "u" if st == 0 and nxt[-1:].isdigit() else "uː"   # situation /ˌsɪtʃ.uˈeɪ.ʃən/
        else:
            v = _ARPA_VOW[base]
        segs.append((v, st))
    return _flap(segs)


def _flap(segs):
    """t giữa nguyên âm (hoặc sau r, n, l) và trước nguyên âm không nhấn -> t̬ (water, city, winter)."""
    out = list(segs)
    for k in range(1, len(segs) - 1):
        if segs[k][0] != "t":
            continue
        prev, nxt = segs[k - 1], segs[k + 1]
        after_vowel = prev[1] is not None or (prev[0] in ("r", "n", "l") and k >= 2 and segs[k - 2][1] is not None)
        # trước nguyên âm không nhấn (photo /ˈfoʊ.t̬oʊ/: CMUdict ghi OW2 nhưng vẫn bật nhẹ sau âm nhấn chính)
        weak = nxt[1] == 0 or (nxt[1] == 2 and k >= 2 and 1 in (segs[k - 1][1], segs[k - 2][1]))
        if after_vowel and weak and nxt[0] not in ("u", "uː"):            # into /ˈɪn.tuː/
            out[k] = ("t̬", None)
    return out


# ---------- 2. espeak en-us (dự phòng, và model XLSR) ----------
# token espeak -> ARPAbet (không kèm trọng âm). Token ghép (ɔːɹ, aɪɚ, iə, n̩) -> nhiều âm.
_ESPEAK = {
    "iː": "IY", "i": "IY0", "ɪ": "IH", "ᵻ": "IH0", "ɛ": "EH", "e": "EH", "æ": "AE", "a": "AE",
    "ɑː": "AA", "ɑ": "AA", "ɒ": "AA", "ɔː": "AO", "ɔ": "AO", "ʌ": "AH", "ə": "AH0", "ɐ": "AH0",
    "ʊ": "UH", "uː": "UW", "u": "UW", "ɜː": "ER", "ɜ": "ER", "ɝ": "ER", "ɚ": "ER0",
    "eɪ": "EY", "aɪ": "AY", "aʊ": "AW", "ɔɪ": "OY", "oʊ": "OW", "o": "OW", "oː": "AO",
    "əl": "AH0 L", "aɪɚ": "AY ER0", "aʊɚ": "AW ER0", "aɪə": "AY ER0", "iə": "IY AH0",
    "ɑːɹ": "AA R", "ɔːɹ": "AO R", "oːɹ": "AO R", "ɔɹ": "AO R", "ɛɹ": "EH R", "ɪɹ": "IH R",
    "ʊɹ": "UH R", "ɜːɹ": "ER", "əɹ": "ER0", "n̩": "AH0 N", "l̩": "AH0 L", "m̩": "AH0 M",
    "ɾ": "T", "ʔ": "T", "ɹ": "R", "r": "R", "ɡ": "G", "g": "G", "tʃ": "CH", "dʒ": "JH", "ð": "DH",
    "θ": "TH", "ʃ": "SH", "ʒ": "ZH", "ŋ": "NG", "j": "Y", "h": "HH", "x": "K", "ɬ": "L",
}


def espeak_to_arpabet(tokens: list[str]) -> list[str]:
    """['w','ˈɔː','ɾ','ɚ'] -> ['W','AO1','T','ER0']."""
    out = []
    for tok in tokens:
        st = "1" if "ˈ" in tok else "2" if "ˌ" in tok else "0"
        tok = tok.replace("ˈ", "").replace("ˌ", "")
        arpa = _ESPEAK.get(tok, tok.upper()).split()
        first = True
        for a in arpa:
            if a[-1].isdigit():                     # đã ghi sẵn trọng âm (vd 'IY0', 'AH0')
                out.append(a)
            elif a in _ARPA_VOW or a in ("AH", "AO", "ER", "IY", "UW", "AA"):
                out.append(a + (st if first else "0"))
                first = False
            else:
                out.append(a)
    return out


# ---------- 3. Chia âm tiết + ghép chuỗi hiển thị kiểu Cambridge ----------
_ONSETS = {tuple(o.split()) for o in (
    "p l|b l|k l|ɡ l|f l|s l|p r|b r|t r|d r|k r|ɡ r|f r|θ r|ʃ r|"
    "s p|s t|s k|s m|s n|s w|s f|t w|d w|k w|ɡ w|θ w|"
    "p j|b j|k j|ɡ j|f j|v j|m j|h j|n j|l j|"
    "s p r|s p l|s t r|s k r|s k w|s k j|s p j").split("|")}


def _legal_onset(cs: tuple) -> bool:
    return len(cs) == 0 or (len(cs) == 1 and cs[0] != "ŋ") or cs in _ONSETS


def to_ipa(segs: list[tuple[str, int | None]]) -> str:
    """[(âm, trọng âm)] -> '/ˈwɑː.t̬ɚ/' kiểu Cambridge (không kèm dấu /)."""
    vidx = [k for k, (_, st) in enumerate(segs) if st is not None]
    if not vidx:
        return "".join(p for p, _ in segs)
    starts = [0]                                   # vị trí bắt đầu mỗi âm tiết
    for a, b in zip(vidx, vidx[1:]):
        cl = [p for p, _ in segs[a + 1:b]]
        n = len(cl)
        while not _legal_onset(tuple(cl[len(cl) - n:])):
            n -= 1                                 # phần đầu âm tiết dài nhất hợp lệ
        prev_v, prev_st = segs[a]
        # Cambridge giữ phụ âm ở cuối âm tiết nhấn có nguyên âm ngắn (happy /ˈhæp.i/, very /ˈver.i/)
        if n and n == len(cl) and prev_st and segs[b][1] == 0 and (prev_v in SHORT or cl[0] == "r"):
            n -= 1
        starts.append(b - n)
    primary = next((k for k, s in enumerate(starts) if segs[vidx[k]][1] == 1), None)
    out = []
    for k, s in enumerate(starts):
        e = starts[k + 1] if k + 1 < len(starts) else len(segs)
        syl = "".join(p for p, _ in segs[s:e])
        st = segs[vidx[k]][1]
        mark = ""
        if len(starts) > 1:
            if st == 1:
                mark = "ˈ"
            elif st == 2 and primary is not None and k < primary:
                mark = "ˌ"                         # Cambridge chỉ ghi trọng âm phụ đứng trước âm chính
        out.append(mark + syl if mark or k == 0 else "." + syl)
    return "".join(out)


def phonemes(segs) -> list[str]:
    return [p for p, _ in segs]


# ---------- 4. IPA của model ZIPA (phiên âm hẹp) -> ký hiệu Cambridge ----------
_DROP = set("ʰʲʷˠˤʼː̴̥̪̺̃̚ˈˌ") | {"̆"}
_ZMAP = {
    "ɹ": "r", "ɻ": "r", "ɽ": "r", "ʁ": "r", "ʀ": "r", "g": "ɡ", "ɢ": "ɡ", "ɣ": "ɡ", "ɠ": "ɡ",
    "ʛ": "ɡ", "ɟ": "ɡ", "c": "k", "q": "k", "x": "k", "χ": "h", "ħ": "h", "ɦ": "h", "ʜ": "h",
    "ç": "h", "ʋ": "v", "β": "v", "ⱱ": "v", "ɸ": "f", "ʍ": "w", "ɰ": "w", "ɥ": "w", "ɱ": "m",
    "ɳ": "n", "ɲ": "n", "ɴ": "ŋ", "ʈ": "t", "ɖ": "d", "ɗ": "d", "ᶑ": "d", "ɓ": "b", "ʙ": "b",
    "ɭ": "l", "ɺ": "l", "ɫ": "l", "ʎ": "l", "ʟ": "l", "ɬ": "l", "ɮ": "l", "ɕ": "ʃ", "ʂ": "ʃ",
    "ɧ": "ʃ", "ʑ": "ʒ", "ʐ": "ʒ", "ʝ": "j", "ʄ": "dʒ",
    "ɛ": "e", "ɐ": "ə", "ɘ": "ə", "ɵ": "ə", "ɤ": "ə", "ɞ": "ə", "ɨ": "ɪ", "ᵻ": "ɪ", "ʉ": "u",
    "ɯ": "u", "y": "u", "ʏ": "ʊ", "ø": "ʊ", "œ": "ʌ", "ɶ": "a", "ɒ": "ɑ", "ɜ": "ɝ", "ɝ": "ɝ",
}
_SKIP = set("ǀǁǂǃʘʕʢʡ")                           # click, âm hầu: không có trong tiếng Anh
_DIPH = {("e", "ɪ"): "eɪ", ("a", "ɪ"): "aɪ", ("a", "ʊ"): "aʊ", ("o", "ʊ"): "oʊ",
         ("ɔ", "ɪ"): "ɔɪ", ("t", "ʃ"): "tʃ", ("d", "ʒ"): "dʒ"}
_V1 = set("iɪeæaɑɔʌʊuəɚɝo")


def _split_token(tok: str):
    """Token model -> (âm gốc, r-hoá?, âm tiết tính?). Nhận cả token nhiều ký tự kiểu espeak (XLSR)."""
    rhot = "˞" in tok or tok in ("ɚ", "ɝ")
    syl = "̩" in tok or "\u030d" in tok
    base = "".join(ch for ch in tok if ch not in _DROP and ch not in "˞̩\u030d")
    return base, rhot, syl


def from_model(raw: list[tuple[str, float]]) -> list[tuple[str, float]]:
    """[(token model, tin cậy)] -> [(âm Cambridge, tin cậy)], mỗi phần tử đúng một âm."""
    # a) tách token, đổi ký hiệu, tách token ghép kiểu espeak (oʊ, ɑːɹ...) thành từng ký tự gốc
    units = []                                   # [ [ký hiệu, tin cậy, r-hoá] ]
    for tok, c in raw:
        base, rhot, syl = _split_token(tok)
        if base in ("ɚ", "ɝ"):
            base = "ə" if base == "ɚ" else "ɝ"
        if base == "ʔ":                          # tắc thanh hầu: giữa từ thường là t (button), đầu từ bỏ
            if units:
                units.append(["t", c, False])
            continue
        chars = [_ZMAP.get(ch, ch) for ch in base if ch not in _SKIP]
        chars = [x for ch in chars for x in ([ch] if len(ch) == 1 else list(ch))]
        if not chars:
            continue
        if syl and chars[-1] in ("n", "l", "m"):
            units.append(["ə", c, False])        # n̩ -> ən
        for k, ch in enumerate(chars):
            units.append([ch, c, rhot and k == len(chars) - 1])
    # b) ghép nguyên âm đôi và tʃ dʒ
    merged = []
    for u in units:
        if merged and (merged[-1][0], u[0]) in _DIPH and not merged[-1][2]:
            m = merged[-1]
            merged[-1] = [_DIPH[m[0], u[0]], min(m[1], u[1]), u[2]]
        else:
            merged.append(list(u))
    # c) r-hoá: ə˞ -> ɚ, nguyên âm khác + ˞ -> ɝː, nguyên âm đôi + ˞ -> + r, phụ âm + ˞ -> + ɚ
    out = []
    for sym, c, rhot in merged:
        if not rhot:
            out.append([sym, c])
        elif sym == "ə":
            out.append(["ɚ", c])
        elif sym in _V1:
            out.append(["ɝ", c])
        elif sym in ("eɪ", "aɪ", "ɔɪ", "oʊ", "aʊ"):
            out += [[sym, c], ["r", c]]
        elif sym == "r":
            out.append(["r", c])
        else:
            out += [[sym, c], ["ɚ", c]]
    # d) dấu dài và quy ước Mỹ của Cambridge
    nvow = sum(1 for s, _ in out if s in _V1 or s in VOWELS)
    res = []
    for k, (sym, c) in enumerate(out):
        nxt = out[k + 1][0] if k + 1 < len(out) else ""
        last = k == len(out) - 1
        if sym == "ɔ":
            sym = "ɔː" if nxt == "r" else "ɔ"       # 'ɔ' đứng riêng: chưa rõ, xem resolve()
        elif sym == "ɑ":
            sym = "ɑː"
        elif sym == "o":
            sym = "oʊ"
        elif sym == "ɝ":
            sym = "ɝː"
        elif sym == "i":
            sym = "i" if last and nvow > 1 else "iː"  # happy /ˈhæp.i/
        elif sym == "u":
            sym = "uː"
        elif sym == "ɾ":
            sym = "t̬"
        res.append((sym, c))
    return res


AMBIGUOUS = {"a": ("ʌ", "ɑː"), "ɔ": ("ɑː", "ɔː")}


def resolve(model: list[str], ref: list[str], align) -> list[str]:
    """Đổi 'a', 'ɔ' của model sang âm Cambridge: lấy âm tương ứng ở từ khớp nhất nếu là một trong các âm
    nó có thể là; nếu không (người nói phát âm lệch) thì mặc định /ɑː/ (Mỹ: caught, hot đều là /ɑː/)."""
    out = list(model)
    for i, j in align(model, ref):
        if i is not None and model[i] in AMBIGUOUS:
            ok = AMBIGUOUS[model[i]]
            out[i] = ref[j] if j is not None and ref[j] in ok else "ɑː"
    return [("ɑː" if p in AMBIGUOUS else p) for p in out]


# ---------- 5. Khoá so khớp (dùng chung cho từ điển và model) ----------
def key(phones: list[str]) -> list[str]:
    """Âm Cambridge -> đơn vị so khớp: bỏ dấu dài, t̬ -> ɾ, 'ɔ' chưa rõ của model -> 'ɔ?' (khác ɔː trước r)."""
    return [("ɾ" if p == "t̬" else "ɔ?" if p == "ɔ" else p.replace("ː", "")) for p in phones if p]
