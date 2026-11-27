#!/usr/bin/env python3
"""LEO THÁP: phần vẽ của `python app.py --game` (chế độ đoán từ dạng game). Chỉ dùng thư viện chuẩn.

Luật: bắt đầu ở tầng 50. Nói đúng nhảy lên (đúng ngay lần đầu +2 tầng, đúng sau vài lần +1), gần đúng chao đảo
đứng yên, sai rơi 1 tầng. Lên tầng 100 là thắng, rơi về tầng 0 (dung nham) là thua. Đúng liên tiếp tăng combo
(nhân điểm tới ×5; mỗi mức ×2…×5 nhân vật một màu, xem TIER_FG).

Xem thử không cần micro:
    python3 tower.py              # tự chơi; phím 1 đúng ngay · 2 đúng · 3 gần đúng · 4 sai · A tự chơi · N chơi lại
    python3 tower.py --start 97   # bắt đầu gần đích (--start 3: gần dung nham)
    python3 tower.py --combo      # xem thang combo: ×2 xanh lá, ×3 xanh ngọc, ×4 tím hồng, ×5 vàng, rồi mất combo
Tiếng hiệu ứng: âm thanh hệ thống macOS (afplay). Tắt bằng V2I_SFX=0.

Không nhấp nháy nhờ:
  - màn hình phụ (alternate screen) + ẩn con trỏ + tắt tự xuống dòng: không cuộn, không vỡ khung;
  - không bao giờ xoá màn hình giữa các khung: dựng cả khung trong bộ nhớ, chỉ ghi lại các dòng đã đổi,
    mỗi dòng ghi đè tại chỗ rồi \\e[K xoá phần thừa;
  - mỗi khung là 1 lần write() duy nhất, bọc trong "synchronized output" (\\e[?2026h … \\e[?2026l):
    Ghostty, iTerm2, WezTerm, kitty vẽ cả khung một lượt; Terminal.app bỏ qua mã này.
Khi game chạy, mọi print() của chương trình được đưa vào khung log bên phải (Screen thay sys.stdout).
"""
import atexit
import io
import math
import os
import random
import re
import subprocess
import sys
import threading
import time
import unicodedata
from collections import deque

FPS = 30
FH = 4                 # số dòng mỗi tầng (1 dòng sàn + 3 dòng cho nhân vật)
PW = 11                # bề rộng sàn
START, GOAL = 50, 100
MIN_COLS, MIN_ROWS = 64, 16
SOUNDS = {"perfect": "Glass", "ok": "Pop", "near": "Tink", "bad": "Funk", "win": "Hero", "lose": "Basso",
          "combo": "Ping"}

# Thang combo: chỉ đổi màu nhân vật (và chữ COMBO cùng màu). Mất combo: nhân vật xám một lát.
TIER_FG = {1: 15, 2: 46, 3: 51, 4: 201, 5: 220}   # trắng · xanh lá · xanh ngọc · tím hồng · vàng
MAX_TIER = 5

# Luật thưởng phạt (ngoài +2 đúng ngay · +1 đúng sau vài lần · 0 gần đúng · −1 sai):
GIVE_UP = 2                # A (xem đáp án) / N (bỏ qua) khi chưa nói đúng: −2 tầng, 1 lần mỗi từ; sau A luyện tự do
MILESTONE = 5              # mỗi 5 từ nói đúng ngay lần đầu (mốc 5, 10, 15…): nhặt 1 lượt cược
BET = {False: (4, 4), True: (8, 10)}   # cược (thắng, thua) theo lần nói đầu: từ ngắn (1 âm tiết) / dài (≥ 2 âm tiết)

POSES = {  # 3 dòng, từ đầu xuống chân
    "stand": (" o ", "/|\\", "/ \\"),
    "jump": ("\\o/", " | ", "/ \\"),
    "land": (" o ", "<|>", "/ \\"),
    "fall1": ("\\o/", " | ", "\\ /"),
    "fall2": ("_o_", " | ", "/ \\"),
    "wob1": (" o/", "/| ", "/ \\"),
    "wob2": ("\\o ", " |\\", "/ \\"),
    "cheer1": ("\\o/", " | ", "/ \\"),
    "cheer2": (" o ", "\\|/", "/ \\"),
    "hurt": (" x ", "/|\\", "/ \\"),
}


# ---------- tiện ích vẽ ----------
def C(s, fg: int | None = None, bold: bool = False) -> str:
    codes = (["1"] if bold else []) + ([f"38;5;{fg}"] if fg is not None else [])
    return f"\x1b[{';'.join(codes)}m{s}\x1b[0m" if codes else str(s)


def row_str(row) -> str:
    out, cur = [], None
    for ch, fg, bg, b in row:
        st = (fg, bg, b)
        if st != cur:
            codes = ["0"] + (["1"] if b else []) + ([f"38;5;{fg}"] if fg is not None else []) \
                + ([f"48;5;{bg}"] if bg is not None else [])
            out.append(f"\x1b[{';'.join(codes)}m")
            cur = st
        out.append(ch)
    out.append("\x1b[0m")
    return "".join(out)


_TOK = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|.", re.S)


def char_width(ch: str) -> int:
    if unicodedata.combining(ch):
        return 0                                           # t̬: dấu phụ không chiếm ô
    return 2 if unicodedata.east_asian_width(ch) in "WF" else 1


def wrap_ansi(line: str, width: int, indent: int = 4) -> list[str]:
    """Cắt dòng có mã màu theo bề rộng hiển thị; dòng nối thụt vào `indent` ô, giữ màu đang dùng."""
    if width <= indent + 4:
        return [line]
    out, cur, w, style = [], [], 0, ""
    for m in _TOK.finditer(line):
        t = m.group()
        if t.startswith("\x1b"):
            cur.append(t)
            if t.endswith("m"):
                style = "" if t in ("\x1b[0m", "\x1b[m") else style + t
            continue
        cw = char_width(t)
        if w + cw > width and w > indent:
            out.append("".join(cur) + "\x1b[0m")
            cur, w = [" " * indent, style], indent
        cur.append(t)
        w += cw
    out.append("".join(cur))
    return out


def play_sfx(name: str):
    if os.environ.get("V2I_SFX", "1") == "0" or sys.platform != "darwin":
        return
    path = f"/System/Library/Sounds/{SOUNDS.get(name, 'Pop')}.aiff"
    if os.path.exists(path):
        subprocess.Popen(["afplay", "-v", "0.3", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


class Thing:
    def __init__(self, **kw):
        self.__dict__.update(kw)


# ---------- trạng thái game ----------
class Tower:
    """Luật nằm ở begin_word / place_bet / attempt / give_up: chúng đổi số liệu ngay (lượt cược, mốc) và trả về
    sự kiện (tên, số tầng, có chạm mốc không) để push() vào hàng đợi; update() diễn hoạt cảnh từng sự kiện.
    Sự kiện: perfect / ok / bet_win (lên n tầng), near / bet_near (chao đảo), bad / bet_lose / giveup (rơi n tầng),
    free (đúng sau khi xem đáp án), practice (luyện sau khi xem đáp án), bet (vừa đặt cược).
    Mọi thứ đi qua self.lock."""

    def __init__(self, start: int = START, goal: int = GOAL, sfx=None, on_over=None):
        self.lock = threading.RLock()
        self.start, self.goal = start, goal
        self.sfx, self.on_over = sfx, on_over
        self.W, self.TH = 36, 24
        self.reset(time.monotonic())

    def reset(self, now: float):
        with self.lock:
            self.f = self.best = self.start
            self.score = self.combo = self.words = 0
            self.firsts = self.bets = 0                         # số từ đúng ngay lần đầu · lượt cược đang có
            self.cur: Thing | None = None                       # từ đang chơi (xem begin_word)
            self.over, self.over_at = "", 0.0                 # over: "" | "win" | "lose"
            self.x, self.h = self.plat_x(self.f), self.feet(self.f)
            self.anim = None
            self.queue: list[tuple] = []
            self.cheer_until = self.shake_until = self.flash_until = self.next_firework = 0.0
            self.break_until = 0.0                              # mất combo: nhân vật xám tới lúc này
            self.parts: list[Thing] = []
            self.texts: list[Thing] = []
            self.cam = self._cam_target()

    def resize(self, W: int, TH: int):
        if (W, TH) != (self.W, self.TH):
            self.W, self.TH = W, TH
            if self.anim is None:
                self.x = self.plat_x(self.f)
            self.cam = self._cam_target()

    # --- toạ độ thế giới: h = số dòng tính từ mặt dung nham (tầng 0), hướng lên ---
    @staticmethod
    def feet(f: int) -> float:
        return f * FH + 1

    def plat_x(self, f: int) -> int:
        W = self.W
        if f <= 0 or f >= self.goal:
            return W // 2
        half = W // 2
        lo, hi = (4 + PW // 2, half - 2) if f % 2 else (half + 2, W - 3 - PW // 2)
        return random.Random(f * 7919).randint(lo, max(lo, hi))

    def push(self, ev):
        if not ev:
            return
        with self.lock:
            if not self.over:
                self.queue.append(ev)

    # --- luật ---
    def begin_word(self, hard: bool):
        with self.lock:
            self.words += 1
            self.cur = Thing(hard=hard, tries=0, bet=False, peeked=False, gave_up=False, done=False)

    def bet_odds(self) -> tuple[int, int]:
        return BET[bool(self.cur and self.cur.hard)]

    def place_bet(self) -> str:
        """Đặt cược cho từ đang chơi. Trả về "" nếu được, không thì lý do."""
        with self.lock:
            c = self.cur
            if self.over or not c or c.done:
                return "chưa có từ để cược"
            if c.bet:
                return "đã cược từ này rồi"
            if c.tries or c.peeked or c.gave_up:
                return "chỉ cược được trước lần nói đầu tiên"
            if self.bets <= 0:
                return f"chưa có lượt cược (nói đúng ngay đủ {MILESTONE} từ để nhặt 1 lượt)"
            self.bets -= 1
            c.bet = True
            return ""

    def attempt(self, result: str):
        """result: correct / near / bad. Trả về sự kiện để push(), None nếu không tính (đã đúng, hết ván)."""
        with self.lock:
            c = self.cur
            if self.over or not c or c.done:
                return None
            c.tries += 1
            first = c.tries == 1
            betting = c.bet and first
            win, lose = BET[c.hard]
            if c.peeked or c.gave_up:                     # đã bỏ từ (xem đáp án): luyện tự do, không thưởng phạt
                c.done = result == "correct"
                return ("free" if c.done else "practice", 0, False)
            if result == "correct":
                c.done = True
                milestone = False
                if first:
                    self.firsts += 1
                    if self.firsts % MILESTONE == 0:
                        self.bets += 1
                        milestone = True
                return ("bet_win", win, milestone) if betting else ("perfect" if first else "ok", 2 if first else 1,
                                                                    milestone)
            if result == "near":
                return ("bet_near" if betting else "near", 0, False)
            return ("bet_lose", lose, False) if betting else ("bad", 1, False)

    def give_up(self, peek: bool):
        """A (peek=True) / N khi chưa nói đúng: −2 tầng (đã cược mà chưa nói: mất như thua cược), 1 lần mỗi từ."""
        with self.lock:
            c = self.cur
            if self.over or not c or c.done:
                return None
            c.peeked = c.peeked or peek
            if c.gave_up:
                return None
            c.gave_up = True
            n = BET[c.hard][1] if c.bet and not c.tries else GIVE_UP
            return ("giveup", n, False)

    def busy(self) -> bool:
        return self.anim is not None or bool(self.queue)

    # --- sự kiện ---
    def _sound(self, name: str):
        if self.sfx:
            try:
                self.sfx(name)
            except Exception:
                pass

    def _start(self, kind: str, dur: float, now: float, **kw):
        self.anim = dict(kind=kind, t0=now, dur=dur, x0=self.x, h0=self.h, **kw)

    def _text(self, s: str, fg: int, dh: float = 0.0, life: float = 1.2):
        self.texts.append(Thing(s=s, x=self.x, h=self.h + 4 + dh, fg=fg, life=life))

    # --- combo ---
    def tier(self) -> int:
        return max(1, min(self.combo, MAX_TIER))

    def char_fg(self, now: float) -> int:
        """Màu nhân vật theo mức combo; vừa mất combo thì xám một lát."""
        return 244 if now < self.break_until else TIER_FG[self.tier()]

    def _break(self, now: float):
        """Mất combo (sai / bỏ qua / xem đáp án)."""
        if self.combo >= 2:
            self.break_until = now + 0.8
            self._text("mất combo", 244, 3.0)
        self.combo = 0

    def _burst(self, n: int, colors, chars: str, up: float = 9.0, at: float = 1.0, x=None, h=None,
               spread: float = 9.0, g: float = 18.0, life: float = 0.9):
        x = self.x if x is None else x
        h = self.h + at if h is None else h
        for _ in range(n):
            self.parts.append(Thing(x=x + random.uniform(-1, 1), h=h, vx=random.uniform(-spread, spread),
                                    vh=random.uniform(up * 0.3, up), g=g, life=random.uniform(life * 0.45, life),
                                    ch=random.choice(chars), fg=random.choice(colors)))

    def _next(self, now: float):
        item = self.queue.pop(0)
        ev, n, milestone = (item, 0, False) if isinstance(item, str) else item
        if ev in ("perfect", "ok", "bet_win"):
            n = min(n or (2 if ev == "perfect" else 1), self.goal - self.f)
            prev = self.tier()
            self.combo += 1
            tier = self.tier()
            self.score += 100 * n * tier
            self.f += n
            self.best = max(self.best, self.f)
            self._text(f"+{n} TẦNG", 46)
            if ev == "bet_win":
                self._text("THẮNG CƯỢC!", 214, 1.5)
            elif ev == "perfect":
                self._text("PERFECT!", 220, 1.5)
            if self.combo >= 2:
                self._text(f"COMBO ×{self.combo}", TIER_FG[tier], 3.0)
            if milestone:
                self._text("+1 LƯỢT CƯỢC", 214, 4.5, life=2.0)
            self._burst(10, (46, 220, 15), "*+.")
            self._sound("win" if ev == "bet_win" else "combo" if tier > prev and tier >= 2 or milestone else ev)
            self._start("jump", 0.42 + 0.12 * n, now, x1=self.plat_x(self.f), h1=self.feet(self.f), arc=2.5 + n)
        elif ev == "free":
            self._text("đúng (đã xem đáp án)", 250)
            self.cheer_until = now + 0.9
            self._sound("ok")
        elif ev == "practice":
            self._text("luyện tập: không tính", 244)
        elif ev == "bet":
            self._text("CƯỢC!", 214, 1.5)
            self._sound("near")
        elif ev in ("near", "bet_near"):
            self._text("gần đúng… mất lượt cược" if ev == "bet_near" else "gần đúng…", 220)
            self._sound("near")
            self._start("wobble", 0.7, now)
        elif ev in ("bad", "bet_lose", "giveup"):
            n = n or 1
            self._break(now)
            self.f = max(0, self.f - n)
            if ev == "bet_lose":
                self._text("THUA CƯỢC", 196, 1.5)
            elif ev == "giveup":
                self._text("bỏ từ", 244, 1.5)
            self._text(f"-{n}", 196)
            self._sound("bad")
            self._start("fall", 0.45 + 0.08 * (n - 1), now, x1=self.plat_x(self.f), h1=self.feet(self.f))

    def _end(self, result: str, now: float):
        self.over, self.over_at = result, now
        self.queue.clear()
        if result == "win":
            self._sound("win")
            self.next_firework = now
        if self.on_over:
            try:
                self.on_over(result)
            except Exception:
                pass

    def _finish(self, a: dict, now: float):
        k = a["kind"]
        if k in ("jump", "fall"):
            self.x, self.h = a["x1"], a["h1"]
        if k == "wobble":
            self.x = a["x0"]
        if k == "jump":
            self._burst(6, (250, 230), ".'", up=5, at=0)
            if self.f >= self.goal:
                self._end("win", now)
            else:
                self.cheer_until = now + 0.9
        if k == "fall":
            self.shake_until = now + 0.3
            self._burst(8, (244, 250), ".,'", up=4, at=0)
            if self.f <= 0:
                self.flash_until, self.shake_until = now + 0.6, now + 0.5
                self._burst(18, (196, 202, 208, 214), "°*o", up=11, at=0)
                self._sound("lose")
                self._start("sink", 0.7, now)
        if k == "sink":
            self._end("lose", now)

    def update(self, dt: float, now: float):
        with self.lock:
            a = self.anim
            if a:
                t = min(1.0, (now - a["t0"]) / a["dur"])
                k = a["kind"]
                if k == "jump":
                    self.x = a["x0"] + (a["x1"] - a["x0"]) * t
                    self.h = a["h0"] + (a["h1"] - a["h0"]) * t + a["arc"] * 4 * t * (1 - t)
                elif k == "fall":
                    self.x = a["x0"] + (a["x1"] - a["x0"]) * min(1.0, t * 1.6)
                    self.h = a["h0"] + (a["h1"] - a["h0"]) * t * t
                elif k == "wobble":
                    self.x = a["x0"] + (1 if math.sin(t * math.pi * 6) > 0 else -1) * (t < 0.9)
                elif k == "sink":
                    self.h = a["h0"] - 2.5 * t
                if t >= 1:
                    self.anim = None
                    self._finish(a, now)
            elif self.queue and not self.over:
                self._next(now)
            if self.cam < 2 and random.random() < dt * 4:      # bong bóng dung nham (khi thấy dung nham)
                self.parts.append(Thing(x=random.uniform(1, self.W - 2), h=1.5, vx=0.0, vh=random.uniform(2, 4),
                                        g=4.0, life=random.uniform(0.3, 0.7), ch=random.choice("°o"), fg=214))
            if self.over == "win" and now >= self.next_firework:  # pháo hoa
                self.next_firework = now + random.uniform(0.25, 0.6)
                self._burst(14, (random.choice((196, 46, 51, 201, 226, 208)),), "*+o.", up=6, spread=10, g=6,
                            x=random.uniform(4, self.W - 5), h=self.cam + self.TH * random.uniform(0.55, 0.9))
            for p in self.parts:
                p.x += p.vx * dt
                p.h += p.vh * dt
                p.vh -= p.g * dt
                p.life -= dt
            self.parts = [p for p in self.parts if p.life > 0]
            for t in self.texts:
                t.h += 2.5 * dt
                t.life -= dt
            self.texts = [t for t in self.texts if t.life > 0]
            self.cam += (self._cam_target() - self.cam) * min(1.0, dt * 5)

    def _cam_target(self) -> float:
        """Người chơi ở khoảng 1/3 dưới màn hình; không nhìn quá sâu dưới dung nham hay quá cao trên đích."""
        t = min(self.h - self.TH * 0.35, self.goal * FH + 8 - self.TH)
        return max(t, -4.0)

    def pose(self, now: float) -> str:
        a, blink = self.anim, int(now * 8) % 2
        if a:
            k = a["kind"]
            if k == "jump":
                return "jump" if (now - a["t0"]) / a["dur"] < 0.65 else "land"
            if k == "fall":
                return "fall1" if blink else "fall2"
            if k == "wobble":
                return "wob1" if blink else "wob2"
            return "hurt"
        if self.over == "lose":
            return "hurt"
        if self.over == "win" or now < self.cheer_until:
            return "cheer1" if blink else "cheer2"
        return "stand"

    def hud_lines(self) -> list[str]:
        f, goal = self.f, self.goal
        k = max(0, min(20, round(f / goal * 20)))
        col = 196 if f < 15 else 220 if f < 35 else 46
        combo = ("    " + C(f"COMBO ×{self.combo}", TIER_FG[self.tier()], True)) if self.combo >= 2 else ""
        return [
            C("▲ LEO THÁP", 220, True) + C(f"   từ #{self.words}", 244),
            "",
            "Tầng   " + C(f, 15, True) + C(f" / {goal}", 244) + C(f"    cao nhất {self.best}", 244),
            "       " + C("█" * k, col) + C("░" * (20 - k), 238),
            "Điểm   " + C(self.score, 15, True) + combo,
            self._bet_line(),
        ]

    def _bet_line(self) -> str:
        c = self.cur
        line = "Cược   " + C(f"{self.bets} lượt", 214 if self.bets else 244, True) \
            + C(f"    đúng ngay {self.firsts % MILESTONE}/{MILESTONE}", 244)
        if c and not c.done and not c.gave_up:
            win, lose = BET[c.hard]
            kind = "DÀI" if c.hard else "NGẮN"
            if c.bet and not c.tries:
                line += "    " + C(f"ĐANG CƯỢC từ {kind}: +{win} / −{lose}", 214, True)
            elif not c.tries and not c.bet:
                line += C(f"    từ {kind}: cược +{win} / −{lose}", 244)
        return line


# ---------- vẽ tháp ----------
def render_tower(g: Tower, now: float) -> list[str]:
    W, TH = g.W, g.TH
    grid = [[(" ", None, None, False)] * W for _ in range(TH)]
    cam = round(g.cam)
    goal_h = g.goal * FH

    def srow(h: float) -> int:
        return TH - 1 - (round(h) - cam)

    def put(x: int, r: int, ch: str, fg=None, bg=None, b=False):
        if 0 <= r < TH and 0 <= x < W:
            grid[r][x] = (ch, fg, bg, b)

    for r in range(TH):                                   # nền: chấm mờ cố định theo thế giới -> thấy cuộn
        wr = cam + TH - 1 - r
        for x in range(1, W - 1):
            hsh = ((wr * 73856093) ^ (x * 19349663)) % 97
            if wr > goal_h + 3:
                if hsh < 2:
                    put(x, r, "+" if hsh else ".", 229)    # trời sao trên đích
            elif hsh < 3:
                put(x, r, ".", 237)
    wall = 160 if now < g.flash_until else 46 if g.over == "win" else 239
    for r in range(TH):
        if cam + TH - 1 - r <= goal_h:
            put(0, r, "│", wall)
            put(W - 1, r, "│", wall)
    for f in range(max(1, (cam - 1) // FH - 1), min(g.goal, (cam + TH) // FH + 1) + 1):   # sàn các tầng
        r = srow(f * FH)
        if not 0 <= r < TH:
            continue
        if f == g.goal:
            for x in range(1, W - 1):
                put(x, r, "▀", 220, None, True)
            continue
        cx = g.plat_x(f)
        col = 51 if f == g.start else 180
        for x in range(cx - PW // 2, cx + PW // 2 + 1):
            put(x, r, "▀", col)
        for i, ch in enumerate(str(f)):
            put(1 + i, r, ch, 250 if f % 10 == 0 else 242, None, f % 10 == 0)
    fx = W - 7                                             # cờ đích
    for i, s in enumerate(("|>>", "|", "|")):
        for j, ch in enumerate(s):
            put(fx + j, srow(goal_h + 3 - i), ch, 196 if ch == ">" else 250, None, True)
    for j, ch in enumerate(f"ĐÍCH {g.goal}"):
        put(3 + j, srow(goal_h + 2), ch, 220, None, True)
    tick = int(now * 6)                                    # dung nham: mặt ở h = 1 (tầng 0)
    for r in range(TH):
        wr = cam + TH - 1 - r
        if wr > 1:
            continue
        for x in range(1, W - 1):
            if wr == 1:
                put(x, r, "^" if (x + tick) % 5 == 0 else "~", 214)
            else:
                k = (x * 3 + wr * 5 + tick) % 7
                put(x, r, "▓" if k < 3 else "▒" if k < 5 else "░", (202, 208, 196)[k % 3], 52)
    for p in g.parts:
        put(round(p.x), srow(p.h), p.ch, p.fg)
    fg = g.char_fg(now)                                    # nhân vật: màu theo mức combo
    px = round(g.x)
    for i, line in enumerate(POSES[g.pose(now)]):
        r = srow(g.h + 2 - i)
        for j, ch in enumerate(line):
            if ch != " ":
                put(px - 1 + j, r, ch, fg, None, True)
    for t in g.texts:
        x0 = max(1, min(W - 1 - len(t.s), round(t.x) - len(t.s) // 2))
        for j, ch in enumerate(t.s):
            put(x0 + j, srow(t.h), ch, t.fg, None, True)
    if g.over and now - g.over_at > 0.6:
        if g.over == "win":
            box, title, bg = ["", "CHIẾN THẮNG!", f"Lên tầng {g.goal} sau {g.words} từ", f"Điểm: {g.score}",
                              "[N] chơi lại", ""], 226, 22
        else:
            box, title, bg = ["", "RƠI VÀO DUNG NHAM!", f"Cao nhất: tầng {g.best}", f"{g.words} từ · điểm {g.score}",
                              "[N] chơi lại", ""], 226, 52
        bw = min(W - 2, max(len(s) for s in box) + 4)
        bx, by = (W - bw) // 2, TH // 2 - len(box) // 2
        for i, s in enumerate(box):
            for j, ch in enumerate(s.center(bw)[:bw]):
                put(bx + j, by + i, ch, title if i == 1 else 15, bg, True)
    rows = grid
    if now < g.shake_until:                                # rung màn hình: dịch cả khung 1 cột
        blank = (" ", None, None, False)
        rows = [[blank] + row[:-1] for row in grid] if random.random() < 0.5 else [row[1:] + [blank] for row in grid]
    return [row_str(row) for row in rows]


def tower_width(cols: int) -> int:
    return max(34, min(42, int(cols * 0.4)))


# ---------- màn hình: vẽ nền 30 khung/giây, nhận print() vào khung log ----------
class LogWriter(io.TextIOBase):
    encoding = "utf-8"

    def __init__(self, screen: "Screen"):
        super().__init__()
        self.screen = screen

    def write(self, text: str) -> int:
        self.screen.add_text(text)
        return len(text)

    def writable(self) -> bool:
        return True

    def isatty(self) -> bool:
        return True                                        # để paint() trong app.py vẫn tô màu

    def flush(self):
        pass


class Screen:
    def __init__(self, tower: Tower, hud=None, keys: str = "", stderr_path: str | None = None,
                 paused=None):
        self.tower, self.hud, self.keys, self.stderr_path = tower, hud, keys, stderr_path
        # paused(): True khi đang ghi âm. Mỗi lần vẽ làm micro thu dính tiếng tách (đo: ~12/s
        # ở 30 FPS, cả Ghostty lẫn Terminal.app) nên lúc đó vẽ 1 khung rồi đứng yên.
        self.paused = paused
        self.log: deque = deque(maxlen=400)
        self.partial = ""
        self.log_lock = threading.Lock()
        self.running = False
        self.thread = None

    def add_text(self, text: str):
        with self.log_lock:
            parts = (self.partial + text).split("\n")
            self.partial = parts.pop()
            self.log.extend(p.replace("\r", "") for p in parts)

    def _log_tail(self, n: int, width: int) -> list[str]:
        if n <= 0:
            return []
        with self.log_lock:
            raw = list(self.log) + ([self.partial] if self.partial else [])
        out: list[str] = []
        for line in reversed(raw):
            out = wrap_ansi(line, width) + out
            if len(out) >= n:
                break
        return out[-n:]

    def frame(self, cols: int, rows: int, now: float) -> list[str]:
        if cols < MIN_COLS or rows < MIN_ROWS:
            msg = f"Phóng to cửa sổ terminal (tối thiểu {MIN_COLS}×{MIN_ROWS}, đang {cols}×{rows})"
            return [msg if r == rows // 2 else "" for r in range(rows)]
        g = self.tower
        with g.lock:
            g.resize(tower_width(cols), rows)
            tower = render_tower(g, now)
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
        return [tower[r] + "  " + panel[r] for r in range(rows)]

    def _out(self, s: str):
        b = s.encode()
        while b:
            b = b[os.write(self.tty, b):]

    def start(self):
        if self.running:
            return
        sys.stdout.flush()
        self.tty = os.dup(1)
        self._saved = (sys.stdout, sys.stderr)
        self._fd2 = None
        if self.stderr_path:                               # lỗi/cảnh báo (cả của thư viện C) -> file, không vỡ khung
            sys.stderr.flush()
            self._errf = open(self.stderr_path, "a", encoding="utf-8", buffering=1)
            self._fd2 = os.dup(2)
            os.dup2(self._errf.fileno(), 2)
            sys.stderr = self._errf
        sys.stdout = LogWriter(self)
        self._out("\x1b[?1049h\x1b[?25l\x1b[?7l\x1b[2J")   # màn hình phụ, ẩn con trỏ, tắt tự xuống dòng
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        atexit.register(self.stop)

    def stop(self):
        if not self.running:
            return
        self.running = False
        if self.thread and self.thread is not threading.current_thread():
            self.thread.join(1.0)
        sys.stdout, sys.stderr = self._saved
        if self._fd2 is not None:
            os.dup2(self._fd2, 2)
            os.close(self._fd2)
            self._errf.close()
        self._out("\x1b[0m\x1b[?7h\x1b[?25h\x1b[?1049l")
        os.close(self.tty)

    def _loop(self):
        prev, size = None, None
        last = time.monotonic()
        frozen = False
        while self.running:
            now = time.monotonic()
            dt, last = min(0.1, now - last), now
            hold = bool(self.paused and self.paused())
            if hold and frozen:
                time.sleep(0.01)
                continue
            frozen = hold
            try:
                ts = os.get_terminal_size(self.tty)
                if (ts.columns, ts.lines) != size:
                    size, prev = (ts.columns, ts.lines), None
                    self._out("\x1b[2J")
                self.tower.update(dt, now)
                lines = self.frame(size[0], size[1], now)
                buf = [f"\x1b[{i + 1};1H{line}\x1b[0m\x1b[K" for i, line in enumerate(lines)
                       if prev is None or i >= len(prev) or prev[i] != line]
                if buf:
                    self._out("\x1b[?2026h" + "".join(buf) + "\x1b[?2026l")
                prev = lines
            except Exception:
                import traceback
                self.add_text(traceback.format_exc())
                time.sleep(0.5)
            wait = 1 / FPS - (time.monotonic() - now)
            if wait > 0:
                time.sleep(wait)


# ---------- xem thử (log giả, giống chế độ --game) ----------
SAMPLE = [  # (từ, IPA chuẩn, nghĩa, IPA khi nói sai)
    ("cat", "kæt", "con mèo", "ket"), ("think", "θɪŋk", "nghĩ", "tɪn"), ("ship", "ʃɪp", "tàu thủy", "ʃiːp"),
    ("bird", "bɝːd", "con chim", "bɜt"), ("world", "wɝːld", "thế giới", "wɔː"),
    ("thought", "θɑːt", "ý nghĩ", "tɔt"), ("three", "θriː", "số ba", "triː"), ("bad", "bæd", "tệ", "bet"),
    ("sheep", "ʃiːp", "con cừu", "ʃɪp"), ("vegetable", "ˈvedʒtəbəl", "rau", "ˈvɛɡɛtəbəl"),
    ("problem", "ˈprɑːbləm", "vấn đề", "ˈprɔblem"), ("important", "ɪmˈpɔːrtənt", "quan trọng", "ɪmpɔtan"),
]
# 1, 2 đúng · 3 gần đúng · 4 sai · 5 bỏ từ. Tự chơi: có lượt cược thì 60% cược ở đầu từ.
AUTO_SCRIPT = [1, 2, 3, 2, 1, 4, 2, 3, 1, 1, 4, 4, 5, 1, 2, 1, 1, 3, 1, 4, 4, 4, 2]
COMBO_SCRIPT = [1, 1, 3, 2, 1, 1, 1, 1, 4, 1, 2, 1, 1, 1, 1, 1, 1, 4]   # --combo: leo đủ các mức ×2…×5, rồi mất
_VOWEL = re.compile(r"[iɪeɛæɑɔʌʊuəɚɝao]+")


class FakeWords:
    """Từ giả cho bản xem thử; luật thật nằm trong Tower (begin_word / place_bet / attempt / give_up)."""

    def __init__(self, g: Tower):
        self.g, self.cur = g, None

    def next_word(self):
        self.cur = random.choice(SAMPLE)
        hard = len(_VOWEL.findall(self.cur[1])) >= 2
        self.g.begin_word(hard)
        win, lose = self.g.bet_odds()
        print(f"\n{C(f'── Từ #{self.g.words} ──', 15, True)}  🔊  " + C(f"từ {'DÀI' if hard else 'NGẮN'}"
                                                                      f" · cược +{win}/−{lose}", 244))

    def bet(self) -> bool:
        why = self.g.place_bet()
        print(C(f"  🎲 Đã cược!", 214, True) if not why else C(f"  Không cược được: {why}.", 244))
        if not why:
            self.g.push(("bet", 0, False))
        return not why

    def attempt(self, key: int):
        if self.cur is None:
            self.next_word()
        if key == 5:
            ev = self.g.give_up(peek=True)
            print(C(f"  Bỏ từ: −{ev[1]} tầng", 196) if ev else "")
            self.cur = None
            return ev
        word, ipa, vi, wrong = self.cur
        result = {1: "correct", 2: "correct", 3: "near", 4: "bad"}[key]
        ev = self.g.attempt(result)
        if not ev:
            return None
        pct = {"correct": random.randint(92, 100), "near": random.randint(62, 88), "bad": random.randint(20, 55)}[result]
        col = 46 if pct >= 90 else 220 if pct >= 60 else 196
        delta = -ev[1] if ev[0] in ("bad", "bet_lose", "giveup") else ev[1]
        print(f"  Lần {self.g.cur.tries}: /{ipa if pct >= 90 else wrong}/  " + C(f"{pct}%", col, True)
              + C(f"   → {ev[0]} {delta:+d}" if delta else f"   → {ev[0]}", 244))
        if ev[2]:
            print(C("  ★ +1 lượt cược", 214, True))
        if result == "correct":
            print(C("  ✓ Chính xác!", 46) + "  ➜ " + C(word, 15, True) + f"  /{ipa}/ → {vi}")
            self.cur = None
        return ev


def demo(start: int, script: list[int] = AUTO_SCRIPT):
    import select
    import termios
    import tty
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    tty.setcbreak(fd)
    auto = [True]
    g = Tower(start=start, sfx=play_sfx)
    words = FakeWords(g)
    scr = Screen(g, hud=lambda: [C(f"Tự chơi: {'BẬT' if auto[0] else 'TẮT'}", 244)],
                 keys="[1] đúng  [3] gần đúng  [4] sai  [5] bỏ từ  [C] cược  [A] tự chơi  [N] chơi lại  [Q] thoát")
    scr.start()
    print(C("Bản xem thử", 15, True) + f": bắt đầu tầng {start}, lên {GOAL} thắng, rơi về 0 thua.")
    step, next_auto = 0, time.monotonic() + 1.0
    try:
        while True:
            now = time.monotonic()
            if select.select([fd], [], [], 0.05)[0]:
                ch = os.read(fd, 1)
                if ch == b"\x1b":
                    if select.select([fd], [], [], 0.03)[0]:
                        os.read(fd, 16)                     # phím mũi tên… bỏ qua
                        continue
                    break
                c = ch.decode(errors="ignore").lower()
                if c == "q":
                    break
                if c == "a":
                    auto[0], next_auto = not auto[0], now + 0.5
                elif c == "n":
                    g.reset(now)
                    words.cur = None
                    print(C(f"── Chơi lại từ tầng {start} ──", 244))
                elif c == "c" and not g.over:
                    if words.cur is None:
                        words.next_word()
                    words.bet()
                elif c and c in "12345" and not g.over:
                    g.push(words.attempt(int(c)))
            if auto[0]:
                if g.over:
                    if now - g.over_at > 5.0:
                        g.reset(now)
                        words.cur = None
                elif not g.busy() and now >= next_auto:
                    if words.cur is None:
                        words.next_word()
                        if g.bets and random.random() < 0.6 and words.bet():
                            next_auto = now + 1.0
                            continue
                    g.push(words.attempt(script[step % len(script)]))
                    step += 1
                    next_auto = now + random.uniform(1.2, 1.8)
                elif g.busy():
                    next_auto = max(next_auto, now + 0.9)
    except KeyboardInterrupt:
        pass
    finally:
        scr.stop()
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        print(f"Tầng {g.f}, cao nhất {g.best} · điểm {g.score}")


if __name__ == "__main__":
    if not sys.stdin.isatty():
        sys.exit("Chạy trong terminal: python3 tower.py")
    combo = "--combo" in sys.argv
    s = 30 if combo else START
    if "--start" in sys.argv:
        s = max(1, min(GOAL - 1, int(sys.argv[sys.argv.index("--start") + 1])))
    demo(s, COMBO_SCRIPT if combo else AUTO_SCRIPT)
