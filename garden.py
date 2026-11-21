#!/usr/bin/env python3
"""CÁNH ĐỒNG HOA: phần vẽ cho game học từ theo chủ đề (bản xem thử, chưa nối vào app.py).
Thuần terminal, 256 màu, dùng lại khung màn hình của tower.py. Chỉ dùng thư viện chuẩn.

Luật (bản kế hoạch): gõ hạt giống rồi đọc đúng thì gieo, mọc sẵn 8 cây. Mỗi lượt gõ 1 từ liên quan tới hạt giống,
máy hiện IPA và đọc mẫu, người chơi đọc theo. Càng gần nghĩa càng nhiều hoa (hạng ≤ 100 / 300 / 500 so với
hạt giống: 3 / 2 / 1 hoa), đúng ngay lần đầu ×2, dùng gợi ý thì chia đôi. Sai: 1 cây héo (mỗi từ tối đa 1).
Đầy 64 ô là thắng, hết cây là thua. Cả vườn lớn lên theo mốc 25 / 50 / 75 / 100%.

Hình: lưới 8×8 ô đất, trồng lần lượt theo thứ tự đọc (trái sang phải, trên xuống dưới); cây héo là cây trồng
sau cùng. Mỗi ô 1 ký hiệu theo giai đoạn: ʏ mầm · ψ ra lá · ɵ ra nụ · ✿ nở hoa · ❀ nở rộ.

Xem thử không cần micro:
    python3 garden.py              # phím 1–6 (xem dưới khung), F gần đầy vườn, A tự chơi, N ván mới, Q thoát
    python3 garden.py --dump       # in vài khung hình (không màu) ra stdout
    python3 garden.py --html garden_preview.html   # xuất cả ván (tới khi nở rộ) ra trang HTML
"""
import base64
import gzip
import json
import math
import os
import random
import re
import subprocess
import sys
import threading
import time

from stars import HTML as _STARS_HTML, ansi_cells
from tower import MIN_COLS, C, Screen, Thing, row_str, wrap_ansi

# ---------- luật (chỉnh ở đây) ----------
GRID = 8                       # vườn GRID × GRID ô
START_PLANTS = 8               # số cây có sẵn khi gieo hạt
RANKS = (100, 300, 500)        # hạng so với hạt giống -> mức 1 / 2 / 3; ngoài 500: không liên quan
BASE = {1: 3, 2: 2, 3: 1}      # số hoa theo mức khi đúng sau vài lần
FIRST_MULT = 2                 # đúng ngay lần đầu
STAGES = ("Mầm", "Ra lá", "Ra nụ", "Nở hoa", "Nở rộ")   # mốc: 0 · 25% · 50% · 75% · đầy vườn
DANGER = 2                     # còn từ ngần này cây trở xuống: báo nguy

# ---------- hình ----------
GLYPH = ("ʏ", "ψ", "ɵ", "✿", "❀")
GLYPH_FG = (71, 71, 175, 211, 212)
TILE_BG, BROKEN_BG = 236, 234
TW, PX, PY = 3, 4, 2           # ô rộng 3 ký tự; bước ngang 4, bước dọc 2 (chừa 1 khe giữa các ô)
STEP = .16                     # giây giữa 2 cây mọc liên tiếp
SOUNDS = {"plant": "Pop", "near": "Tink", "die": "Funk", "grow": "Ping", "win": "Hero", "lose": "Basso"}


def level(rank: int) -> int:
    """Hạng so với hạt giống -> mức 1 (rất gần) · 2 (gần) · 3 (xa) · 0 (không liên quan)."""
    for i, lim in enumerate(RANKS):
        if rank <= lim:
            return i + 1
    return 0


def reward(lv: int, first: bool, hint: bool = False) -> int:
    n = BASE.get(lv, 0) * (FIRST_MULT if first else 1)
    return -(-n // 2) if hint else n                      # gợi ý: chia đôi, làm tròn lên


def sfx(name: str):
    if os.environ.get("V2I_SFX", "1") == "0" or sys.platform != "darwin":
        return
    path = f"/System/Library/Sounds/{SOUNDS.get(name, 'Pop')}.aiff"
    if os.path.exists(path):
        subprocess.Popen(["afplay", "-v", "0.25", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# ---------- trạng thái ----------
class Garden:
    """Sự kiện (push): sow (gieo hạt giống), plant n (first / retry / hint), near n, die, break.
    Mỗi sự kiện là một hoạt cảnh ngắn, chạy lần lượt. Gọi update() mỗi khung; mọi thứ đi qua self.lock."""

    def __init__(self, sfx=None):
        self.lock = threading.RLock()
        self.sfx = sfx
        self.on_over = None                              # on_over("win" | "lose")
        self.W, self.TH = GRID * PX + 3, 24
        self.reset(time.monotonic())

    def reset(self, now: float):
        with self.lock:
            self.plots = [Thing(i=i, r=i // GRID, c=i % GRID, state="empty", stage=0, t=-9.0)
                          for i in range(GRID * GRID)]
            self.seed_word = ""
            self.stage = 0
            self.words = self.firsts = self.hints = 0
            self.anim, self.queue = None, []
            self.status = Thing(s="gõ hạt giống rồi đọc đúng để gieo", fg=244, t=now)
            self.over = None
            self.over_t = 0.0

    def resize(self, W: int, TH: int):
        self.TH = TH

    def push(self, kind: str, word: str = "", n: int = 0, how: str = ""):
        with self.lock:
            self.queue.append(Thing(kind=kind, word=word, n=n, how=how))

    def busy(self) -> bool:
        return self.anim is not None or bool(self.queue)

    # --- đếm ---
    def alive(self) -> int:
        return sum(p.state == "plant" for p in self.plots)

    def broken(self) -> int:
        return sum(p.state == "broken" for p in self.plots)

    def empties(self) -> list:
        return [p for p in self.plots if p.state == "empty"]

    def stage_for(self, n: int) -> int:
        total = GRID * GRID
        return sum(n >= math.ceil(total * f) for f in (.25, .5, .75))

    def milestone_next(self) -> tuple[int, str] | None:
        total = GRID * GRID
        for i, f in enumerate((.25, .5, .75, 1.0)):
            need = math.ceil(total * f)
            if self.alive() < need:
                return need, STAGES[i + 1]
        return None

    def danger(self) -> bool:
        return bool(self.seed_word) and not self.over and self.alive() <= DANGER

    # --- toạ độ ---
    def origin(self) -> tuple[int, int]:
        top = max(2, (self.TH - GRID * PY - 2) // 2 + 1)
        return 2, top

    def xy(self, p) -> tuple[int, int]:
        ox, oy = self.origin()
        return ox + p.c * PX, oy + p.r * PY

    # --- sự kiện ---
    def _sound(self, name: str):
        if self.sfx:
            try:
                self.sfx(name)
            except Exception:
                pass

    def _say(self, s: str, fg: int, now: float):
        self.status = Thing(s=s, fg=fg, t=now)

    def _start(self, kind: str, dur: float, now: float, **kw):
        self.anim = Thing(kind=kind, t0=now, dur=dur, t=0.0, **kw)

    def _next(self, now: float):
        ev = self.queue.pop(0)
        k = ev.kind
        if k in ("sow", "plant"):
            if k == "sow":
                self.seed_word = ev.word
                ev.n = START_PLANTS
                self._say(f"gieo hạt giống «{ev.word}»: mọc {ev.n} cây", 222, now)
            else:
                self._say(f"+{ev.n}  {ev.word}", 222 if ev.how == "first" else 114, now)
            ts = self.empties()[:ev.n]
            if ts:
                self._start("plant", STEP * len(ts) + .25, now, ev=ev, targets=ts, done=0)
        elif k == "near":
            self._sound("near")
            self._say(f"gần đúng · {ev.n} ô đang chờ", 179, now)
            self._start("near", 1.0, now, targets=self.empties()[:ev.n])
        elif k in ("die", "break"):
            live = [p for p in self.plots if p.state == "plant"]
            if not live:
                return
            self._sound("die")
            self._say("−1  cây héo" if k == "die" else "−1  cây chết, ô hỏng", 167, now)
            self._start("die", .7, now, p=live[-1], ev=ev)
        elif k == "grow":
            self.stage = ev.n
            self._sound("grow")
            pct = (0, 25, 50, 75, 100)[ev.n]
            self._say(f"{pct}% · {STAGES[ev.n].lower()}", 157, now)
            self._start("grow", .8, now, to=ev.n)
        elif k == "bloom":
            self.stage = 4
            self._sound("win")
            self._say(f"vườn hoa nở rộ · {self.words} từ", 212, now)
            self._start("grow", 1.2, now, to=4, win=True)
        elif k == "wither":
            self._sound("lose")
            self._say("vườn đã héo · [N] gieo lại", 244, now)
            self._start("wither", .5, now)

    def _after_change(self):
        st = self.stage_for(self.alive())
        if st > self.stage:
            self.queue.insert(0, Thing(kind="grow", n=st, word="", how=""))
        if not self.empties() and not any(q.kind == "bloom" for q in self.queue):
            self.queue.append(Thing(kind="bloom", n=0, word="", how=""))

    def _finish(self, a, now: float):
        if a.kind == "plant":
            ev = a.ev
            if ev.kind == "plant":
                self.words += 1
                self.firsts += ev.how == "first"
                self.hints += ev.how == "hint"
            self._after_change()
        elif a.kind == "die":
            a.p.state, a.p.t = ("broken" if a.ev.kind == "break" else "empty"), now
            if self.alive() == 0:
                self.queue.insert(0, Thing(kind="wither", n=0, word="", how=""))
            elif not self.empties():
                self._after_change()
        elif a.kind == "grow" and getattr(a, "win", False):
            self.over, self.over_t = "win", now
            if self.on_over:
                self.on_over("win")
        elif a.kind == "wither":
            self.over, self.over_t = "lose", now
            if self.on_over:
                self.on_over("lose")

    def update(self, dt: float, now: float):
        with self.lock:
            a = self.anim
            if a:
                a.t = min(1.0, (now - a.t0) / a.dur)
                el = now - a.t0
                if a.kind == "plant":
                    while a.done < len(a.targets) and el >= a.done * STEP:
                        p = a.targets[a.done]
                        p.state, p.stage, p.t = "plant", self.stage, now
                        a.done += 1
                        if a.done == 1:
                            self._sound("plant")
                elif a.kind == "grow":
                    upto = int(a.t * len(self.plots) * 1.05)
                    for p in self.plots[:upto]:
                        if p.state == "plant" and p.stage < a.to:
                            p.stage, p.t = a.to, now
                if a.t >= 1:
                    self.anim = None
                    self._finish(a, now)
            elif self.queue:
                self._next(now)

    def fill_to(self, n: int, now: float):
        """Xem thử: trồng ngay (không hoạt cảnh) cho tới khi có n cây."""
        with self.lock:
            if not self.seed_word:
                self.seed_word = "boring"
            for p in self.empties()[:max(0, n - self.alive())]:
                p.state, p.t = "plant", now - 1
            self.stage = self.stage_for(self.alive())
            for p in self.plots:
                p.stage = self.stage

    def hud_lines(self) -> list[str]:
        n, tot = self.alive(), GRID * GRID
        k = round(n / tot * 16)
        bar = C("■" * k, 211) + C("■" * (16 - k), 237)
        head = C("✿ CÁNH ĐỒNG HOA", 211, True)
        if self.seed_word:
            head += C("   hạt giống ", 244) + C(self.seed_word, 222, True)
        nxt = self.milestone_next()
        stage = "Giai đoạn  " + C(STAGES[self.stage], 157)
        if nxt and self.seed_word:
            stage += C(f" · còn {nxt[0] - n} hoa tới «{nxt[1]}»", 244)
        info = f"Từ đã trồng {self.words} · đúng ngay {self.firsts} · gợi ý {self.hints}"
        if self.broken():
            info += f" · ô hỏng {self.broken()}"
        lines = [head, "", "Hoa  " + C(n, 15, True) + C(f"/{tot}", 244) + "  " + bar, stage, C(info, 244)]
        if self.danger():
            lines.append(C(f"⚠ Còn {n} cây", 203, True))
        return lines


# ---------- vẽ ----------
def render_garden(g: Garden, now: float) -> list[str]:
    W, TH = g.W, g.TH
    cell = [[(" ", None, None, False)] * W for _ in range(TH)]
    a = g.anim

    def put(x, r, ch, fg, bg=None, b=False):
        if 0 <= r < TH and 0 <= x < W:
            cell[r][x] = (ch, fg, bg, b)

    def text(x0, r, s, fg, b=False):
        for j, ch in enumerate(s):
            put(x0 + j, r, ch, fg, None, b)

    near = a.targets if a and a.kind == "near" else []
    dying = a.p if a and a.kind == "die" else None
    for p in g.plots:
        x, y = g.xy(p)
        bg = BROKEN_BG if p.state == "broken" else TILE_BG
        for j in range(TW):
            put(x + j, y, " ", None, bg)
        mid = x + TW // 2
        if p.state == "broken":
            put(mid, y, "×", 239, bg)
        elif p in near:
            put(mid, y, "◌" if int((now - a.t0) * 6) % 2 == 0 else " ", 179, bg)
        elif p is dying:
            if int((now - a.t0) * 7) % 2 == 0:
                put(mid, y, GLYPH[p.stage], 167, bg)
        elif p.state == "plant":
            new = now - p.t < .3
            put(mid, y, GLYPH[p.stage], 231 if new else GLYPH_FG[p.stage], bg, new or p.stage == 4)
        else:
            put(mid, y, "·", 239, bg)

    ox, oy = g.origin()
    gw = GRID * PX - 1
    if g.seed_word:
        s = f"❁ {g.seed_word}"
        text(ox + (gw - len(s)) // 2, oy - 2, s, 222, True)
    st = g.status
    if st:
        s = st.s[:gw + 2]
        text(max(0, ox + (gw - len(s)) // 2), oy + GRID * PY, s, st.fg, True)
    return [row_str(row) for row in cell]


def garden_width(cols: int) -> int:
    return GRID * PX + 3


class GardenScreen(Screen):
    """Screen của tower.py, chỉ đổi phần vẽ bên trái."""

    def frame(self, cols: int, rows: int, now: float) -> list[str]:
        need_c, need_r = garden_width(cols) + 30, GRID * PY + 4
        if cols < max(MIN_COLS, need_c) or rows < need_r:
            msg = f"Phóng to cửa sổ terminal (tối thiểu {max(MIN_COLS, need_c)}×{need_r}, đang {cols}×{rows})"
            return [msg if r == rows // 2 else "" for r in range(rows)]
        g = self.tower
        with g.lock:
            g.resize(garden_width(cols), rows)
            field = render_garden(g, now)
            head = g.hud_lines()
        pw = cols - g.W - 2
        if self.hud:
            head += self.hud()
        rule = C("─" * max(0, min(pw - 1, 60)), 238)
        head.append(rule)
        foot = [rule] + [C(s, 244) for s in wrap_ansi(self.keys, pw - 1, 0)] if self.keys else []
        n = max(0, rows - len(head) - len(foot))
        body = self._log_tail(n, pw - 1)
        panel = (head + body + [""] * (n - len(body)) + foot)[:rows]
        panel += [""] * (rows - len(panel))
        return [field[r] + C("│", 236) + " " + panel[r] for r in range(rows)]


# ---------- xem thử (log giả, hạt giống "boring") ----------
SEED = ("boring", "ˈbɔːr.ɪŋ", "chán, tẻ nhạt")
WORDS = [  # (từ, hạng so với "boring" trong ~12.900 từ phổ biến của Numberbatch, IPA, nghĩa)
    ("tedious", 1, "ˈtiː.di.əs", "chán ngắt"), ("dull", 2, "dʌl", "buồn tẻ"),
    ("annoying", 5, "əˈnɔɪ.ɪŋ", "gây khó chịu"), ("repetitive", 6, "rɪˈpet̬.ɪ.t̬ɪv", "lặp đi lặp lại"),
    ("depressing", 9, "dɪˈpres.ɪŋ", "làm chán nản"), ("exhausting", 10, "ɪɡˈzɑː.stɪŋ", "làm kiệt sức"),
    ("meaningless", 11, "ˈmiː.nɪŋ.ləs", "vô nghĩa"), ("useless", 12, "ˈjuː.sləs", "vô ích"),
    ("tired", 16, "taɪrd", "mệt mỏi"), ("predictable", 17, "prɪˈdɪk.tə.bəl", "dễ đoán"),
    ("silly", 25, "ˈsɪl.i", "ngớ ngẩn"), ("interesting", 29, "ˈɪn.trə.stɪŋ", "thú vị"),
    ("exciting", 33, "ɪkˈsaɪ.t̬ɪŋ", "hào hứng"), ("lazy", 36, "ˈleɪ.zi", "lười biếng"),
    ("routine", 43, "ruːˈtiːn", "nếp sinh hoạt"), ("weary", 45, "ˈwɪr.i", "mệt mỏi, chán"),
    ("ordinary", 52, "ˈɔːr.də.ner.i", "bình thường"), ("sad", 57, "sæd", "buồn"),
    ("simple", 63, "ˈsɪm.pəl", "đơn giản"), ("fun", 69, "fʌn", "vui"),
    ("fascinating", 79, "ˈfæs.ə.neɪ.t̬ɪŋ", "cuốn hút"), ("chores", 87, "tʃɔːrz", "việc vặt"),
    ("sleepy", 92, "ˈsliː.pi", "buồn ngủ"), ("everyday", 94, "ˈev.riˈdeɪ", "hằng ngày"),
    ("horrible", 101, "ˈhɔːr.ə.bəl", "kinh khủng"), ("pleasant", 123, "ˈplez.ənt", "dễ chịu"),
    ("empty", 143, "ˈemp.ti", "trống rỗng"), ("weird", 181, "wɪrd", "kỳ quặc"),
    ("topic", 204, "ˈtɑː.pɪk", "chủ đề"), ("hilarious", 219, "hɪˈler.i.əs", "rất buồn cười"),
    ("homework", 221, "ˈhoʊm.wɝːk", "bài tập về nhà"), ("familiar", 241, "fəˈmɪl.jɚ", "quen thuộc"),
    ("cheap", 297, "tʃiːp", "rẻ tiền"), ("narrative", 305, "ˈnær.ə.t̬ɪv", "câu chuyện kể"),
    ("really", 317, "ˈrɪl.i", "thật sự"),
]
_VOW = re.compile(r"[iɪeæʌɑɔʊuəɚ]")
_SWAP = {"i": "ɪ", "ɪ": "i", "e": "æ", "æ": "e", "ʌ": "ɑ", "ɑ": "ʌ", "ɔ": "o", "ʊ": "u", "u": "ʊ", "ə": "a", "ɚ": "ə"}
# phím: 1 đúng ngay · 2 sai rồi đúng · 3 gần đúng · 4 sai · 5 gợi ý · 6 đáp án (A)
AUTO = [1, 1, 2, 1, 3, 1, 1, 5, 2, 1, 4, 1, 6, 1, 2, 1, 1, 3, 1, 2, 1, 5, 1, 1, 2, 1, 1, 4, 1, 2, 1, 1, 1]
KEYS = "[1] đúng ngay  [2] sai rồi đúng  [3] gần đúng  [4] sai  [5] gợi ý  [6] đáp án (A)  [F] gần đầy" \
       "  [A] tự chơi  [N] ván mới  [Q] thoát"


def bad_ipa(ipa: str) -> str:
    m = _VOW.search(ipa)
    return ipa[:m.start()] + _SWAP.get(m.group(), "ə") + ipa[m.end():] if m else ipa + "s"


class FakeWords:
    def __init__(self, g: Garden, out=print):
        self.g, self.out = g, out
        self.reset()

    def reset(self):
        self.used: list[str] = []
        self.pending = None                    # từ đang dở (sau gần đúng)

    def _take(self, want: int | None = None):
        free = [w for w in WORDS if w[0] not in self.used]
        if not free:
            self.used.clear()
            free = WORDS[:]
        if want is None:
            want = random.choices((1, 2, 3), (65, 25, 10))[0]
        pick = [w for w in free if level(w[1]) == want] or free
        w = random.choice(pick)
        self.used.append(w[0])
        return w

    def sow(self):
        w, ipa, vi = SEED
        out = self.out
        out(C("── Hạt giống ──", 15, True))
        out("  ⌨ " + C(w, 15, True) + f"  /{ipa}/  {vi}  🔊")
        out(f"  Lần 1: /{bad_ipa(ipa)}/ " + C("61%", 179) + C("  ~ gần đúng, đọc lại", 179))
        out(f"  Lần 2: /{ipa}/ " + C("95%", 46) + C("  ✓ Gieo hạt! Mọc sẵn 8 cây", 220, True))
        self.g.push("sow", w)

    def card(self, w, rank, ipa, vi, hint=False):
        lv = level(rank)
        name = ("", "rất gần", "gần", "xa")[lv]
        n = reward(lv, True, hint)
        self.out("")
        self.out(C(f"── Từ #{self.g.words + 1} ──", 15, True) + (C("  [?] gợi ý", 179) if hint else ""))
        self.out("  ⌨ " + C(w, 15, True) + f"  /{ipa}/  {vi}  🔊")
        self.out(C(f"  hạng {rank} · {name} → ", 244) + C(f"{n} hoa", 211, True) + C(" nếu đúng ngay", 244))

    def attempt(self, key: int):
        g, out = self.g, self.out
        if not g.seed_word:
            self.sow()
            return
        if g.over:
            return
        if self.pending is None or key == 5:
            hint = key == 5
            w = self._take(1 if hint else None)
            self.pending = Thing(w=w[0], rank=w[1], ipa=w[2], vi=w[3], hint=hint, tries=0, died=False)
            self.card(*w, hint)
        p = self.pending
        lv = level(p.rank)

        def say(ok: bool, pct: int, msg: str, col: int, bold: bool = False):
            p.tries += 1
            out(f"  Lần {p.tries}: /{p.ipa if ok else bad_ipa(p.ipa)}/ " + C(f"{pct}%", 46 if ok else col)
                + C(f"  {msg}", col, bold))

        def wrong(extra: str = ""):              # mỗi từ chết tối đa 1 cây
            if p.died:
                say(False, random.randint(25, 55), "✗ sai (từ này đã mất 1 cây, không mất thêm)" + extra, 203)
                return
            p.died = True
            say(False, random.randint(25, 55), "✗ sai: 1 cây héo" + extra, 203)
            g.push("die", p.w)

        if key == 3:
            say(False, random.randint(62, 86), "~ gần đúng: không mất gì", 179)
            g.push("near", p.w, reward(lv, p.tries == 1, p.hint))
            return
        if key == 4:
            wrong(". [N] từ khác")
            self.pending = None
            return
        if key == 6:
            out(C("  [A] Đáp án: 1 cây chết, ô thành đất hỏng. Giờ luyện thoải mái.", 203))
            g.push("break", p.w)
            self.pending = None
            return
        if key == 2:
            wrong()
        first = p.tries == 0
        n = reward(lv, first, p.hint)
        say(True, random.randint(90, 99), f"✓ {'Đúng ngay!' if first else 'Đúng:'} +{n} hoa",
            220 if first and not p.hint else 157, True)
        g.push("plant", p.w, n, "hint" if p.hint else "first" if first else "retry")
        self.pending = None


def demo():
    import select
    import termios
    import tty
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    tty.setcbreak(fd)
    auto = [True]
    g = Garden(sfx=sfx)
    words = FakeWords(g)
    scr = GardenScreen(g, hud=lambda: [C(f"Tự chơi: {'BẬT' if auto[0] else 'TẮT'}", 244)], keys=KEYS)
    scr.start()
    print(C("Bản xem thử CÁNH ĐỒNG HOA", 15, True) + ": hạt giống «boring», mỗi từ liên quan trồng thêm hoa.")
    step, next_auto = 0, time.monotonic() + 1.2
    try:
        while True:
            now = time.monotonic()
            if select.select([fd], [], [], 0.05)[0]:
                ch = os.read(fd, 1)
                if ch == b"\x1b":
                    if select.select([fd], [], [], 0.03)[0]:
                        os.read(fd, 16)
                        continue
                    break
                c = ch.decode(errors="ignore").lower()
                if c == "q":
                    break
                if c == "a":
                    auto[0], next_auto = not auto[0], now + .5
                elif c == "n":
                    g.reset(now)
                    words.reset()
                    step = 0
                    print(C("\n── Ván mới ──", 244))
                elif c == "f":
                    g.fill_to(GRID * GRID - 6, now)
                    print(C("  (xem thử: trồng nhanh tới gần đầy vườn)", 244))
                elif c and c in "123456":
                    words.attempt(int(c))
            if auto[0] and not g.over:
                if not g.busy() and now >= next_auto:
                    words.attempt(AUTO[step % len(AUTO)])
                    step += 1
                    next_auto = now + random.uniform(.9, 1.4)
                elif g.busy():
                    next_auto = max(next_auto, now + .6)
    except KeyboardInterrupt:
        pass
    finally:
        scr.stop()
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        print(f"Vườn: {g.alive()}/{GRID * GRID} hoa · {g.words} từ · {g.firsts} đúng ngay")


# ---------- chạy không cần terminal: --dump (khung chữ), --html (hoạt hình) ----------
def simulate(fps: int, cols: int, rows: int, on_frame, script=None, max_s: float = 180, tail: float = 9):
    random.seed(11)
    t0 = 1000.0
    g = Garden()
    g.reset(t0)
    scr = GardenScreen(g, keys=KEYS)
    words = FakeWords(g, out=lambda s: scr.add_text(s + "\n"))
    scr.add_text(C("Bản xem thử CÁNH ĐỒNG HOA", 15, True) + ": hạt giống «boring».\n")
    script = script or AUTO
    step, next_auto, end = 0, t0 + 1.5, None
    for f in range(int(max_s * fps)):
        now = t0 + f / fps
        if g.over and end is None:
            end = now + tail
        if end is not None and now >= end:
            break
        if not g.over:
            if not g.busy() and now >= next_auto:
                words.attempt(script[step % len(script)])
                step += 1
                next_auto = now + 1.0
            elif g.busy():
                next_auto = max(next_auto, now + .55)
        g.update(1 / fps, now)
        on_frame(f, now - t0, g, scr.frame(cols, rows, now))


def export_html(path: str, fps: int = 20, cols: int = 118, rows: int = 30):
    pal, rows_idx, row_list, frames = {}, {}, [], []

    def ci(c):
        if c is None:
            return -1
        h = "#%02x%02x%02x" % tuple(c)
        if h not in pal:
            pal[h] = len(pal)
        return pal[h]

    def on_frame(f, t, g, lines):
        fr = []
        for line in lines:
            runs, cur = [], None
            for ch, fg, bg, b in ansi_cells(line, cols):
                st = (ci(fg), ci(bg), int(b))
                if st != cur:
                    runs.append([ch, *st])
                    cur = st
                else:
                    runs[-1][0] += ch
            key = json.dumps(runs, ensure_ascii=False, separators=(",", ":"))
            if key not in rows_idx:
                rows_idx[key] = len(row_list)
                row_list.append(runs)
            fr.append(rows_idx[key])
        frames.append(fr)

    simulate(fps, cols, rows, on_frame)
    data = json.dumps({"fps": fps, "cols": cols, "rows": rows, "pal": list(pal), "R": row_list, "F": frames},
                      ensure_ascii=False, separators=(",", ":"))
    blob = base64.b64encode(gzip.compress(data.encode(), 9)).decode()
    html = _STARS_HTML.replace("Thắp chòm sao: bản xem thử", "Cánh đồng hoa: bản xem thử").replace("__DATA__", blob)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"{path}: {len(frames)} khung ({len(frames) / fps:.0f} giây), {len(row_list)} dòng khác nhau,"
          f" {len(html) // 1024} KB")


def dump():
    strip = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
    want = set()

    def on_frame(f, t, g, lines):
        a = g.anim
        tag = None
        if a and a.kind == "plant" and a.ev.kind == "sow" and a.t > .95:
            tag = "gieo xong"
        elif a and a.kind == "plant" and a.ev.kind == "plant" and .4 < a.t < .5:
            tag = "đang trồng"
        elif a and a.kind == "die" and .1 < a.t < .2:
            tag = "cây héo"
        elif a and a.kind == "grow" and a.t > .95:
            tag = f"mốc {a.to}"
        elif g.over == "win" and (1000 + t) - g.over_t > 2:
            tag = "nở rộ"
        if tag and tag not in want:
            want.add(tag)
            print(f"=== {tag} @ {t:.1f}s · {g.alive()} hoa ===")
            for line in lines:
                print(strip.sub("", line).rstrip())

    simulate(30, 110, 30, on_frame)


if __name__ == "__main__":
    if "--dump" in sys.argv:
        dump()
    elif "--html" in sys.argv:
        i = sys.argv.index("--html")
        export_html(sys.argv[i + 1] if i + 1 < len(sys.argv) else "garden_preview.html")
    else:
        if not sys.stdin.isatty():
            sys.exit("Chạy trong terminal: python3 garden.py   (hoặc --dump / --html)")
        demo()
