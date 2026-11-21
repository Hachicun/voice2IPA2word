#!/usr/bin/env python3
"""THẮP CHÒM SAO: phần vẽ cho chế độ săn từ theo âm, chơi 1 mình (bản xem thử, chưa nối vào app.py).
Thuần terminal: nền đen của terminal, chỉ tô màu chữ (256 màu). Dùng lại khung màn hình không nhấp nháy
của tower.py. Chỉ dùng thư viện chuẩn.

Luật: chọn 1 hay vài âm. Trên trời có sẵn hình mờ của một chòm sao. Mỗi từ chứa đủ các âm đó thắp 1 ngôi sao
và các nét nối tới nó. Thắp đủ thì chòm sao sống dậy (cá vẫy đuôi, thuyền nhấp nhô, diều bay…), rồi bầu trời
trôi sang chòm kế tiếp. Không tính giờ, nói sai không mất gì.
  - Tự nghĩ ra từ và nói đúng: sao sáng ✦ (từ khó/hiếm: sao vàng lấp lánh to). Điểm đầy đủ.
  - Bấm G nhận gợi ý rồi đọc theo: sao mờ ✧, ít điểm hơn.
  - Sai, hoặc từ đã thắp rồi: sao băng tắt giữa đường.

Xem thử không cần micro:
    python3 stars.py              # phím 1 tự nói · 2 tự nói từ khó · 3 gợi ý · 4 sai · 5 trùng · A tự chơi · Q thoát
    python3 stars.py --dump       # in vài khung hình (không màu) ra stdout
    python3 stars.py --html stars_preview.html   # xuất 60 giây hoạt hình ra trang HTML
Nét nối vẽ bằng ký tự braille (⠁⠂⠄…, mỗi ô 2×4 chấm) nên đường chéo mịn. Tiếng hiệu ứng: âm thanh hệ thống
macOS (afplay). Tắt bằng V2I_SFX=0.
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

from tower import MIN_COLS, MIN_ROWS, C, Screen, Thing, char_width, row_str, wrap_ansi

SOUNDS = {"star": "Glass", "big": "Ping", "hint": "Tink", "miss": "Bottle", "done": "Hero"}

CONSTELLATIONS = [          # (tên, các điểm (x, y) trong 0..1 theo thứ tự thắp, các cạnh nối)
    ("NGÔI NHÀ", [(.22, .95), (.22, .48), (.5, .02), (.78, .48), (.78, .95)],
     [(0, 1), (1, 2), (2, 3), (3, 4), (4, 0), (1, 3)]),
    ("CON CÁ", [(.94, .5), (.64, .08), (.32, .5), (.64, .92), (.04, .1), (.04, .9), (.8, .4)],
     [(0, 1), (1, 2), (2, 3), (3, 0), (2, 4), (2, 5), (4, 5)]),
    ("CON THUYỀN", [(.04, .6), (.22, .95), (.78, .95), (.96, .6), (.5, .6), (.5, .02), (.86, .5)],
     [(0, 1), (1, 2), (2, 3), (3, 4), (4, 0), (4, 5), (5, 6), (6, 4)]),
    ("CON MÈO", [(.5, .95), (.16, .66), (.24, .34), (.12, .0), (.5, .3), (.88, .0), (.76, .34), (.84, .66)],
     [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 6), (6, 7), (7, 0)]),
    ("CÁNH DIỀU", [(.5, .0), (.78, .36), (.5, .8), (.22, .36), (.5, .36), (.62, .98)],
     [(0, 1), (1, 2), (2, 3), (3, 0), (0, 4), (4, 2), (2, 5)]),
]
WAVE = (61, 62, 104, 141, 183, 225, 231, 225, 183, 141, 104, 62)
BITS = {(0, 0): 0x01, (0, 1): 0x02, (0, 2): 0x04, (1, 0): 0x08, (1, 1): 0x10, (1, 2): 0x20, (0, 3): 0x40,
        (1, 3): 0x80}


def sfx(name: str):
    if os.environ.get("V2I_SFX", "1") == "0" or sys.platform != "darwin":
        return
    path = f"/System/Library/Sounds/{SOUNDS.get(name, 'Pop')}.aiff"
    if os.path.exists(path):
        subprocess.Popen(["afplay", "-v", "0.25", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def smooth(t: float) -> float:
    return t * t * (3 - 2 * t)


def ramp(colors, t: float) -> int:
    """Chọn màu trong dải theo t ∈ 0..1 (dùng để mờ dần trên nền đen)."""
    return colors[max(0, min(len(colors) - 1, int(t * len(colors))))]


# ---------- trạng thái ----------
class Sky:
    """Sự kiện (push): own (tự nói, tier 2 thường / 3 từ khó), hint (đọc theo gợi ý, tier 1), miss, used.
    Gọi update() mỗi khung; mọi thứ đi qua self.lock. cam tính theo đơn vị chòm sao (chòm k nằm ở x = k·W)."""

    def __init__(self, sounds: str = "/æ/", sfx=None):
        self.lock = threading.RLock()
        self.sounds, self.sfx = sounds, sfx
        self.on_done = None                              # on_done(tên chòm, số sao): gọi khi thắp xong 1 chòm
        self.W, self.TH = 50, 24
        self.reset(time.monotonic())

    def reset(self, now: float):
        with self.lock:
            self.k, self.cam = 0, 0.0
            self.stars: dict[int, list] = {}
            self.alive: dict[int, float] = {}            # chòm đã thắp xong -> lúc bắt đầu sống dậy
            self.edges: list[Thing] = []
            self.score = self.words = self.bright = self.dim = self.done = self.streak = 0
            self.anim, self.queue = None, []
            self.parts, self.texts = [], []
            self.label, self.title_t = None, None
            self.next_puff = 0.0
            self.ghost_t = now

    def resize(self, W: int, TH: int):
        self.W, self.TH = W, TH

    def push(self, kind: str, word: str = "", pts: int = 0, tier: int = 2):
        with self.lock:
            self.queue.append(Thing(kind=kind, word=word, pts=pts, tier=tier))

    def busy(self) -> bool:
        return self.anim is not None or bool(self.queue)

    # --- toạ độ thế giới: x theo cột (chòm k từ k·W), y theo dòng màn hình ---
    def shape(self, k: int):
        return CONSTELLATIONS[k % len(CONSTELLATIONS)]

    def at(self, k: int, px: float, py: float) -> tuple[float, float]:
        """Điểm (px, py) ∈ 0..1 trong khung của chòm k -> toạ độ thế giới."""
        w = self.W - 10
        hmax = max(3, self.TH - 6)
        h = min(hmax, w * 0.42)
        top = 3 + (hmax - h) * 0.4
        return k * self.W + 5 + px * w, top + py * h

    def pos(self, k: int, i: int, now: float) -> tuple[float, float]:
        x, y = self.at(k, *self.shape(k)[1][i])
        if k in self.alive:                              # chòm sống dậy: các sao chuyển động theo hình
            t = now - self.alive[k]
            ramp_in = min(1.0, t / 1.0)
            dx, dy = alive_offset(self.shape(k)[0], i, t)
            x, y = x + dx * ramp_in, y + dy * ramp_in
        return x, y

    def hand(self) -> tuple[float, float]:
        """Sao bay lên từ mép dưới, giữa màn hình."""
        return self.cam * self.W + self.W / 2, self.TH + 0.5

    # --- hiệu ứng ---
    def _sound(self, name: str):
        if self.sfx:
            try:
                self.sfx(name)
            except Exception:
                pass

    def _start(self, kind: str, dur: float, now: float, **kw):
        self.anim = Thing(kind=kind, t0=now, dur=dur, t=0.0, **kw)

    def _burst(self, x, y, n, cols, chars, speed=7.0, g=0.0, drag=2.5, life=0.9):
        for _ in range(n):
            a, sp = random.uniform(0, 2 * math.pi), random.uniform(speed * 0.35, speed)
            lf = random.uniform(life * 0.5, life)
            self.parts.append(Thing(x=x, y=y, vx=math.cos(a) * sp * 2, vy=math.sin(a) * sp, g=g, drag=drag,
                                    life=lf, max=lf, ch=random.choice(chars), cols=cols))

    def _text(self, s: str, x: float, y: float, cols, life: float = 1.6):
        self.texts.append(Thing(s=s, x=x, y=y, cols=cols, life=life, max=life))

    # --- sự kiện ---
    def _next(self, now: float):
        ev = self.queue.pop(0)
        k, i = self.k, len(self.stars.get(self.k, []))
        hx, hy = self.hand()
        sx, sy = self.pos(k, i, now)
        if ev.kind in ("own", "hint"):
            self.words += 1
            x1, y1, kind, dur = sx, sy, "fly", 1.0 if ev.kind == "own" else 1.25
        else:
            x1, y1, kind, dur = hx + (sx - hx) * .5, hy + (sy - hy) * .5, "fizz", 0.8
        self._start(kind, dur, now, ev=ev, x0=hx, y0=hy, x1=x1, y1=y1,
                    cx=(hx + x1) / 2 - (x1 - hx) * .2, cy=min(hy, y1) - 3, trail=[])

    def _ignite(self, ev, now: float):
        k = self.k
        lst = self.stars.setdefault(k, [])
        i = len(lst)
        tier = 1 if ev.kind == "hint" else ev.tier
        lst.append(Thing(i=i, tier=tier, word=ev.word, t=now))
        x, y = self.pos(k, i, now)
        self.streak = 0 if tier == 1 else self.streak + 1
        if tier == 3:
            self._burst(x, y, 26, (136, 178, 220, 222, 229, 231), "*+✦∙·", speed=10)
        elif tier == 2:
            self._burst(x, y, 16, (60, 104, 153, 189, 231), "*+∙·", speed=7.5)
        else:
            self._burst(x, y, 6, (238, 242, 246), "∙·", speed=4, life=.6)
        cols = (136, 178, 220, 222) if tier == 3 else (60, 104, 153, 189) if tier == 2 else (238, 242, 245)
        self._text(f"+{ev.pts}", x + 3, y - 1, cols)
        if self.streak >= 3:
            self._text(f"chuỗi ×{self.streak}", x + 3, y - 2, (89, 133, 177, 213), life=1.8)
        self.label = Thing(k=k, i=i, word=ev.word, tier=tier, t=now)
        self.score += ev.pts
        if tier == 1:
            self.dim += 1
        else:
            self.bright += 1
        for a, b in self.shape(k)[2]:
            if max(a, b) == i:
                ax, ay = self.pos(k, min(a, b), now)
                L = math.hypot(x - ax, (y - ay) * 2)
                self.edges.append(Thing(k=k, a=min(a, b), b=i, t0=now + .1, dur=.25 + L / 60))
        self._sound("big" if tier == 3 else "star" if tier == 2 else "hint")
        if len(lst) == len(self.shape(k)[1]):
            self._start("rest", 1.0, now, then="glow")
        else:
            self._start("rest", .45, now)

    def _finish(self, a, now: float):
        if a.kind == "fly":
            self._ignite(a.ev, now)
        elif a.kind == "fizz":
            self._burst(a.x1, a.y1, 12, (52, 88, 130, 166, 208), ".,'∙", speed=4, g=14, drag=1.0, life=1.0)
            self._text("đã thắp rồi" if a.ev.kind == "used" else "chưa đúng…", a.x1 - 4, a.y1 - 1,
                       (238, 241, 244, 174))
            self._sound("miss")
            self.streak = 0
            self._start("rest", .4, now)
        elif a.kind == "rest" and getattr(a, "then", "") == "glow":
            self.title_t = now
            self.alive[self.k] = now
            self._sound("done")
            if self.on_done:
                try:
                    self.on_done(self.shape(self.k)[0], len(self.stars.get(self.k, [])))
                except Exception:
                    pass
            self._start("glow", 5.0, now, fired=set())
        elif a.kind == "glow":
            self.done += 1
            self._start("pan", 3.0, now)
        elif a.kind == "pan":
            self.k += 1
            self.cam = float(self.k)
            self.title_t, self.label = None, None
            self.ghost_t = now

    def update(self, dt: float, now: float):
        with self.lock:
            a = self.anim
            if a:
                a.t = min(1.0, (now - a.t0) / a.dur)
                if a.kind in ("fly", "fizz"):
                    u = smooth(a.t) if a.kind == "fly" else 1 - (1 - a.t) ** 2
                    x = (1 - u) ** 2 * a.x0 + 2 * (1 - u) * u * a.cx + u * u * a.x1
                    y = (1 - u) ** 2 * a.y0 + 2 * (1 - u) * u * a.cy + u * u * a.y1
                    a.trail = (a.trail + [(x, y)])[-12:]
                    if a.ev.kind == "own" and random.random() < dt * 25:
                        gold = a.ev.tier == 3
                        self.parts.append(Thing(x=x, y=y, vx=random.uniform(-2, 2), vy=random.uniform(1, 3), g=2,
                                                drag=1, life=.6, max=.6, ch=random.choice(".∙·"),
                                                cols=(136, 178, 222) if gold else (60, 104, 153)))
                elif a.kind == "glow":
                    for j, _ in enumerate(self.stars.get(self.k, [])):
                        if j not in a.fired and now - a.t0 > .2 + j * .15:
                            a.fired.add(j)
                            sx, sy = self.pos(self.k, j, now)
                            self._burst(sx, sy, 8, (61, 104, 147, 189, 222, 231), "∙+*", speed=5, life=.8)
                elif a.kind == "pan":
                    self.cam = self.k + smooth(a.t)
                if a.t >= 1:
                    self.anim = None
                    self._finish(a, now)
            elif self.queue:
                self._next(now)
            self._alive_particles(now)
            for p in self.parts:
                p.vx *= max(0.0, 1 - p.drag * dt)
                p.vy = p.vy * max(0.0, 1 - p.drag * dt) + p.g * dt
                p.x += p.vx * dt
                p.y += p.vy * dt
                p.life -= dt
            self.parts = [p for p in self.parts if p.life > 0]
            for t in self.texts:
                t.y -= 1.3 * dt
                t.life -= dt
            self.texts = [t for t in self.texts if t.life > 0]

    def _alive_particles(self, now: float):
        """Khói ống khói, bong bóng cá… của các chòm đang sống dậy và đang thấy trên màn hình."""
        if now < self.next_puff:
            return
        self.next_puff = now + .22
        for k, t0 in self.alive.items():
            if abs(k - self.cam) > 1:
                continue
            name = self.shape(k)[0]
            if name == "NGÔI NHÀ" and now - t0 > 1:
                x, y = self.at(k, .66, .2)
                self.parts.append(Thing(x=x, y=y, vx=random.uniform(1, 3), vy=-random.uniform(1.5, 2.5), g=0,
                                        drag=0, life=2.2, max=2.2, ch=random.choice("°o∘."), cols=(237, 240, 244, 248)))
            elif name == "CON CÁ" and random.random() < .5:
                x, y = self.pos(k, 0, now)
                self.parts.append(Thing(x=x + 2, y=y - 1, vx=random.uniform(-.5, .5), vy=-2, g=0, drag=0,
                                        life=1.6, max=1.6, ch=random.choice("o°∘"), cols=(24, 31, 38, 74, 117)))

    def hud_lines(self) -> list[str]:
        name, pts, _ = self.shape(self.k)
        lit = self.stars.get(self.k, [])
        glyph = {3: C("✦", 220, True), 2: C("✦", 231, True), 1: C("✧", 245)}
        prog = " ".join([glyph[s.tier] for s in lit] + [C("∘", 239)] * (len(pts) - len(lit)))
        streak = ("   " + C(f"chuỗi ×{self.streak}", 177, True)) if self.streak >= 3 else ""
        return [
            C("✦ THẮP CHÒM SAO", 222, True) + C(f"   âm {self.sounds}", 244),
            "",
            "Chòm " + C(self.k + 1, 15, True) + "  " + C(name, 189, True),
            "      " + prog + C(f"   {len(lit)}/{len(pts)}", 244),
            "Điểm  " + C(self.score, 15, True) + streak,
            C(f"Sao sáng {self.bright} · sao mờ {self.dim} · chòm đã thắp {self.done}", 244),
        ]


def alive_offset(name: str, i: int, t: float) -> tuple[float, float]:
    """Độ lệch (cột, dòng) của sao i khi chòm sống dậy, t giây sau khi thắp xong."""
    if name == "CON CÁ":
        if i in (4, 5):
            return 1.6 * math.sin(t * 7), 0.0                          # vẫy đuôi
        if i == 2:
            return .6 * math.sin(t * 7 - .8), 0.0
        return .5 * math.sin(t * 2), 0.0                              # bơi tới lui
    if name == "CON THUYỀN":
        tilt = .5 * math.sin(t * 2.2)
        return 0.0, .7 * math.sin(t * 2.2 + .4) + (tilt if i in (5, 6) else 0)   # nhấp nhô trên sóng
    if name == "CON MÈO" and i in (3, 5):
        return 0.0, -.8 * max(0.0, math.sin(t * 5 + (0 if i == 3 else 1.2))) ** 4  # giật tai
    if name == "CÁNH DIỀU":
        return 2.0 * math.sin(t * 1.4) + (.6 * math.sin(t * 3) if i == 5 else 0), .7 * math.sin(t * 2.1)
    return 0.0, 0.0


# ---------- vẽ ----------
class Braille:
    """Lưới chấm braille 2×4 mỗi ô: vẽ đường mảnh, chéo mịn trên terminal."""

    def __init__(self):
        self.cells: dict[tuple[int, int], list] = {}

    def line(self, x0, y0, x1, y1, col: int, prio: int, upto: float = 1.0, every: int = 1, skip: float = .9):
        sx0, sy0, sx1, sy1 = x0 * 2 + 1, y0 * 4 + 2, x1 * 2 + 1, y1 * 4 + 2
        n = max(1, int(max(abs(sx1 - sx0), abs(sy1 - sy0))))
        L = math.hypot(x1 - x0, (y1 - y0) * 2) or 1
        for j in range(0, int(n * upto) + 1):
            if j % every:
                continue
            t = j / n
            if min(t, 1 - t) * L < skip:                               # chừa chỗ cho ngôi sao ở 2 đầu
                continue
            sx, sy = math.floor(sx0 + (sx1 - sx0) * t), math.floor(sy0 + (sy1 - sy0) * t)
            key = (sx // 2, sy // 4)
            e = self.cells.get(key)
            bit = BITS[(sx % 2, sy % 4)]
            if e is None:
                self.cells[key] = [bit, col, prio]
            else:
                e[0] |= bit
                if prio >= e[2]:
                    e[1], e[2] = col, prio


def render_sky(g: Sky, now: float) -> list[str]:
    W, TH = g.W, g.TH
    camx = g.cam * W
    cell = [[None] * W for _ in range(TH)]            # (ch, fg, bold)
    a = g.anim

    def put(x, r, ch, fg, b=False):
        x, r = round(x), round(r)
        if 0 <= r < TH and 0 <= x < W:
            cell[r][x] = (ch, fg, b)

    def text(x0, r, s, fg, b=False):
        for j, ch in enumerate(s):
            put(x0 + j, r, ch, fg, b)

    ground = TH
    # nét nối: hình mờ có sẵn (chấm thưa) + nét đã thắp (liền, sáng)
    br = Braille()
    vis = [k for k in (g.k - 1, g.k, g.k + 1) if k >= 0]
    pan = a and a.kind == "pan"
    for k in vis:
        if k > g.k and not pan:
            continue
        alpha = a.t if (pan and k > g.k) else min(1.0, (now - g.ghost_t) / 1.5) if k == g.k else 1.0
        ghost = ramp((233, 234, 235, 236, 237, 238), alpha)
        for ea, eb in g.shape(k)[2]:
            ax, ay = g.pos(k, ea, now)
            bx, by = g.pos(k, eb, now)
            br.line(ax - camx, ay, bx - camx, by, ghost, 0, every=3)
    glowing = a and a.kind == "glow"
    for n, e in enumerate(g.edges):
        p = (now - e.t0) / e.dur
        if p <= 0 or abs(e.k - g.cam) > 1.2:
            continue
        ax, ay = g.pos(e.k, e.a, now)
        bx, by = g.pos(e.k, e.b, now)
        col = 104 if e.k in g.alive else 61
        if glowing and e.k == g.k:
            col = WAVE[int(now * 10 - n * 2) % len(WAVE)]
        br.line(ax - camx, ay, bx - camx, by, col, 1, upto=min(1.0, p))
        if p < 1:                                                       # đầu nét đang vẽ: chấm sáng
            put(ax - camx + (bx - ax) * p, ay + (by - ay) * p, "∙", 231, True)
    for (cx, cy), (bits, col, _) in br.cells.items():
        if 0 <= cy < ground and 0 <= cx < W:
            cell[cy][cx] = (chr(0x2800 + bits), col, False)

    # trang trí khi chòm sống dậy
    for k, t0 in g.alive.items():
        if abs(k - g.cam) > 1.2:
            continue
        name, t = g.shape(k)[0], now - t0
        if t < .6:
            continue
        if name == "NGÔI NHÀ":
            x, y = g.at(k, .5, .7)
            text(x - camx - 1, y, "▪ ▪", 220 if int(t * 1.5) % 5 else 178, True)
            x, y = g.at(k, .5, .93)
            put(x - camx, y, "▯", 136)
        elif name == "CON CÁ":
            x, y = g.pos(k, 6, now)
            put(x - camx - 1, y, "•" if int(t * 2) % 6 else "-", 231, True)
        elif name == "CON THUYỀN":
            _, y = g.at(k, .5, .95)
            x0, _ = g.at(k, 0, 0)
            for j in range(int(W - 6)):
                put(x0 - camx - 3 + j, y + 1, "~" if (j + int(t * 6)) % 4 else "-", 31 if (j + int(t * 4)) % 3 else 38)
        elif name == "CON MÈO":
            blink = int(t * 2.5) % 7 == 0
            for px in (.36, .64):
                x, y = g.at(k, px, .5)
                put(x - camx, y, "-" if blink else "•", 120, True)
            x, y = g.at(k, .5, .7)
            put(x - camx, y, "ᴥ", 175)
        elif name == "CÁNH DIỀU":
            x, y = g.pos(k, 5, now)
            for j in range(1, 7):
                put(x - camx - j * 1.4, y + j * .7 + .6 * math.sin(t * 5 - j), "∿", (203, 220, 45)[j % 3])

    # bóng các vị trí sao chưa thắp; sao kế tiếp nhấp nháy
    shown = [(g.k + 1, a.t)] if pan else [(g.k, min(1, (now - g.ghost_t) / 1.5))]
    for k, alpha in shown:
        n_lit = len(g.stars.get(k, []))
        for i in range(n_lit, len(g.shape(k)[1])):
            x, y = g.pos(k, i, now)
            x -= camx
            if i == n_lit and not (a and a.kind in ("glow", "pan")):
                on = math.sin(now * 4) > 0
                put(x, y, "◌" if on else "∘", 110 if on else 67, on)
                put(x - 1, y, "·" if on else " ", 60)
                put(x + 1, y, "·" if on else " ", 60)
            else:
                put(x, y, "∘", ramp((234, 236, 238, 240), alpha))

    # các sao đã thắp: sao vàng có tia lấp lánh, sao trắng có tia ngắn, sao mờ không tia
    for k, lst in g.stars.items():
        if abs(k - g.cam) > 1.2:
            continue
        for s in lst:
            x, y = g.pos(k, s.i, now)
            x -= camx
            age = now - s.t
            tw = math.sin(now * 2.6 + s.i * 1.9)
            if age < .2:
                put(x, y, "✺", 231, True)
                text(x - 2, y, "══", 231)
                text(x + 1, y, "══", 231)
                put(x, y - 1, "║", 231)
                put(x, y + 1, "║", 231)
            elif s.tier == 3:
                arm = 2 if tw > .3 else 1
                for j in range(1, arm + 1):
                    put(x - j, y, "─" if j == 1 else "╴", 178 if j == 1 else 136)
                    put(x + j, y, "─" if j == 1 else "╶", 178 if j == 1 else 136)
                if tw > -.2:
                    put(x, y - 1, "│", 136)
                    put(x, y + 1, "│", 136)
                put(x, y, "✶" if tw > .85 else "✦", 220, True)
            elif s.tier == 2:
                if tw > -.3:
                    put(x - 1, y, "·", 110)
                    put(x + 1, y, "·", 110)
                put(x, y, "✦", 231, True)
            else:
                put(x, y, "✧", 245)

    # hạt
    for p in g.parts:
        put(p.x - camx, p.y, p.ch, ramp(p.cols, p.life / p.max))

    # sao đang bay: đầu sáng, đuôi dài mờ dần
    if a and a.kind in ("fly", "fizz") and a.trail:
        own = a.ev.kind == "own"
        cols = (136, 178, 220, 222, 229) if own and a.ev.tier == 3 else (60, 67, 110, 153, 189) if own \
            else (237, 240, 243, 246)
        if a.kind == "fizz":
            cols = cols if a.t < .5 else (52, 88, 130, 166, 208)
        tr = a.trail
        for j, (x, y) in enumerate(tr[:-1]):
            put(x - camx, y, "·" if j < len(tr) - 5 else "•", ramp(cols, (j + 1) / len(tr)))
        x, y = tr[-1]
        put(x - camx, y, "✦" if own else "∙", 231 if own else 250, True)

    # chữ: nhãn từ vừa thắp, điểm bay lên, tên chòm
    lb = g.label
    if lb and now - lb.t < 4.0 and abs(lb.k - g.cam) < 1.2:
        x, y = g.pos(lb.k, lb.i, now)
        fade = min(1.0, (4.0 - (now - lb.t)) / 1.2)
        cols = (60, 67, 74, 117, 153) if lb.tier >= 2 else (237, 240, 243)
        ry = y + 1.4 if y + 2 < ground - 1 else y - 1.4
        x0 = max(0, min(W - len(lb.word), round(x - camx - len(lb.word) / 2)))
        text(x0, ry, lb.word, ramp(cols, fade))
    for t in g.texts:
        text(round(t.x - camx), t.y, t.s, ramp(t.cols, t.life / t.max), True)
    if g.title_t is not None:
        name, pts, _ = g.shape(g.k)
        s = f"✧ CHÒM SAO {name} ✧"
        typed = int((now - g.title_t) * 16)
        fade = 1 - a.t if pan else 1.0
        x0 = (W - len(s)) // 2
        text(x0, 0, s[:typed], ramp((94, 136, 178, 220, 222), fade), True)
        lst = g.stars.get(g.k, [])
        sub = f"{len(pts)} sao · {sum(s.tier >= 2 for s in lst)} sáng · {sum(s.tier == 1 for s in lst)} mờ"
        if typed > len(s) + 6:
            text((W - len(sub)) // 2, 1, sub, ramp((237, 240, 244, 248), fade))

    return [row_str([(c[0], c[1], None, c[2]) if c else (" ", None, None, False) for c in row]) for row in cell]


def sky_width(cols: int) -> int:
    return max(40, min(64, int(cols * .52)))


class SkyScreen(Screen):
    """Screen của tower.py, chỉ đổi phần vẽ bên trái."""

    def frame(self, cols: int, rows: int, now: float) -> list[str]:
        if cols < MIN_COLS or rows < MIN_ROWS:
            msg = f"Phóng to cửa sổ terminal (tối thiểu {MIN_COLS}×{MIN_ROWS}, đang {cols}×{rows})"
            return [msg if r == rows // 2 else "" for r in range(rows)]
        g = self.tower
        with g.lock:
            g.resize(sky_width(cols), rows)
            sky = render_sky(g, now)
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
        return [sky[r] + C("│", 236) + " " + panel[r] for r in range(rows)]


# ---------- xem thử (log giả, giống chế độ săn từ /æ/) ----------
EASY = [("cat", "kæt", "con mèo"), ("back", "bæk", "phía sau"), ("hand", "hænd", "bàn tay"),
        ("black", "blæk", "màu đen"), ("thank", "θæŋk", "cảm ơn"), ("happy", "ˈhæpi", "vui"),
        ("man", "mæn", "đàn ông"), ("bag", "bæɡ", "cái túi"), ("map", "mæp", "bản đồ"), ("glass", "ɡlæs", "cái ly")]
HARD = [("avalanche", "ˈævəlæntʃ", "tuyết lở"), ("magnetic", "mæɡˈnetɪk", "có từ tính"),
        ("calendar", "ˈkæləndɚ", "lịch"), ("sandwich", "ˈsænwɪtʃ", "bánh mì kẹp"),
        ("strategy", "ˈstrætədʒi", "chiến lược"), ("vacuum", "ˈvækjuːm", "máy hút bụi"),
        ("anniversary", "ˌænɪˈvɝːsɚi", "ngày kỷ niệm")]
HINTS = [("family", "ˈfæməli", "gia đình"), ("apple", "ˈæpəl", "quả táo"), ("answer", "ˈænsɚ", "câu trả lời"),
         ("travel", "ˈtrævəl", "du lịch"), ("rabbit", "ˈræbɪt", "con thỏ")]
WRONG = [("bed", "bed"), ("cut", "kʌt"), ("cart", "kɑːrt"), ("bird", "bɝːd")]
AUTO = [1, 2, 3, 1, 4, 2, 1, 3, 2, 5, 1, 1, 2, 1, 2, 3, 1, 4, 2, 1, 1, 2, 3, 1, 2, 1, 1]


class FakeWords:
    def __init__(self, g: Sky, out=print):
        self.g, self.out = g, out
        self.lit: list[str] = []
        self.pools = {k: random.sample(v, len(v)) for k, v in (("e", EASY), ("h", HARD), ("g", HINTS))}

    def _take(self, kind: str):
        pool = self.pools[kind]
        for w in pool:
            if w[0] not in self.lit:
                return w
        return random.choice(pool)

    def attempt(self, key: int):
        g, out = self.g, self.out
        out("")
        out(C(f"── Sao #{len(self.lit) + 1} ──", 15, True) + C("  nói 1 từ chứa /æ/", 244))
        if key in (1, 2):
            w, ipa, vi = self._take("e" if key == 1 else "h")
            pts = random.randint(20, 30) if key == 1 else random.randint(50, 70)
            out(f"  Lần 1: /{ipa}/  → model nghe: " + C(w, 15, True) + C(f" ({random.randint(90, 99)}% âm)", 46))
            out(C("  ✓ Sao vàng (từ khó)!" if key == 2 else "  ✓ Sao sáng!", 222 if key == 2 else 189, True)
                + f"  {w} /{ipa}/ → {vi}  " + C(f"+{pts}", 15, True))
            self.lit.append(w)
            g.push("own", w, pts, 3 if key == 2 else 2)
        elif key == 3:
            w, ipa, vi = self._take("g")
            pts = random.randint(7, 10)
            out(C("  [G] Gợi ý: ", 244) + C(w, 15, True) + f" /{ipa}/ → {vi}  🔊")
            out(f"  Đọc theo: /{ipa}/  " + C(f"{random.randint(82, 95)}%", 46) + C("  ✓ sao mờ", 245)
                + "  " + C(f"+{pts}", 15, True))
            self.lit.append(w)
            g.push("hint", w, pts, 1)
        elif key == 5 and self.lit:
            w = random.choice(self.lit)
            out(f"  Lần 1: → model nghe: {w}  " + C(f"✗ '{w}' đã thắp rồi, thử từ khác.", 203))
            g.push("used", w)
        else:
            w, ipa = random.choice(WRONG)
            out(f"  Lần 1: /{ipa}/ → model nghe: {w}  " + C("✗ thiếu /æ/, thử từ khác (không mất gì).", 203))
            g.push("miss", w)


def demo():
    import select
    import termios
    import tty
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    tty.setcbreak(fd)
    auto = [True]
    g = Sky(sfx=sfx)
    words = FakeWords(g)
    scr = SkyScreen(g, hud=lambda: [C(f"Tự chơi: {'BẬT' if auto[0] else 'TẮT'}", 244)],
                    keys="[1] tự nói  [2] tự nói từ khó  [3] gợi ý  [4] sai  [5] trùng  [A] tự chơi  [N] làm lại"
                         "  [Q] thoát")
    scr.start()
    print(C("Bản xem thử THẮP CHÒM SAO", 15, True) + ": mỗi từ chứa /æ/ thắp 1 sao. Không tính giờ.")
    step, next_auto = 0, time.monotonic() + 1.5
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
                    words.lit.clear()
                    print(C("── Bầu trời mới ──", 244))
                elif c and c in "12345":
                    words.attempt(int(c))
            if auto[0]:
                if not g.busy() and now >= next_auto:
                    words.attempt(AUTO[step % len(AUTO)])
                    step += 1
                    next_auto = now + random.uniform(1.3, 2.0)
                elif g.busy():
                    next_auto = max(next_auto, now + 1.0)
    except KeyboardInterrupt:
        pass
    finally:
        scr.stop()
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        print(f"Đã thắp {g.done} chòm · {g.bright} sao sáng, {g.dim} sao mờ · điểm {g.score}")


# ---------- chạy không cần terminal: --dump (khung chữ), --html (hoạt hình) ----------
def simulate(seconds: float, fps: int, cols: int, rows: int, on_frame):
    random.seed(7)
    t0 = 1000.0
    g = Sky()
    g.reset(t0)
    scr = SkyScreen(g, keys="[1] tự nói  [2] tự nói từ khó  [3] gợi ý  [4] sai  [5] trùng  [Q] thoát")
    words = FakeWords(g, out=lambda s: scr.add_text(s + "\n"))
    scr.add_text(C("Bản xem thử THẮP CHÒM SAO", 15, True) + ": mỗi từ chứa /æ/ thắp 1 sao. Không tính giờ.\n")
    step, next_auto = 0, t0 + 1.2
    for f in range(int(seconds * fps)):
        now = t0 + f / fps
        if not g.busy() and now >= next_auto:
            words.attempt(AUTO[step % len(AUTO)])
            step += 1
            next_auto = now + 1.5
        elif g.busy():
            next_auto = max(next_auto, now + .9)
        g.update(1 / fps, now)
        on_frame(f, now - t0, g, scr.frame(cols, rows, now))


_SGR = re.compile(r"\x1b\[([0-9;]*)m|(.)", re.S)


def xterm(n: int):
    if n < 16:
        return [(0, 0, 0), (205, 0, 0), (0, 205, 0), (205, 205, 0), (0, 0, 238), (205, 0, 205), (0, 205, 205),
                (229, 229, 229), (127, 127, 127), (255, 0, 0), (0, 255, 0), (255, 255, 0), (92, 92, 255),
                (255, 0, 255), (0, 255, 255), (255, 255, 255)][n]
    if n < 232:
        n -= 16
        lv = (0, 95, 135, 175, 215, 255)
        return lv[n // 36], lv[n // 6 % 6], lv[n % 6]
    v = 8 + 10 * (n - 232)
    return v, v, v


def ansi_cells(line: str, cols: int):
    """Dòng ANSI -> các ô (ký tự, fg, bg, đậm); ký tự rộng 2 ô thêm ô trống '\\0'."""
    fg = bg = None
    bold = False
    out = []
    for m in _SGR.finditer(line):
        if m.group(2) is None:
            p = [int(x) for x in m.group(1).split(";") if x] or [0]
            i = 0
            while i < len(p):
                c = p[i]
                if c == 0:
                    fg, bg, bold = None, None, False
                elif c == 1:
                    bold = True
                elif c in (38, 48):
                    if p[i + 1] == 5:
                        col, i = xterm(p[i + 2]), i + 2
                    else:
                        col, i = tuple(p[i + 2:i + 5]), i + 4
                    fg, bg = (col, bg) if c == 38 else (fg, col)
                i += 1
            continue
        ch = m.group(2)
        w = char_width(ch)
        if w == 0 and out:
            out[-1] = (out[-1][0] + ch,) + out[-1][1:]
            continue
        out.append((ch, fg, bg, bold))
        if w == 2:
            out.append(("\0", fg, bg, bold))
    out = out[:cols]
    return out + [(" ", None, None, False)] * (cols - len(out))


def export_html(path: str, seconds: float = 60, fps: int = 20, cols: int = 112, rows: int = 28):
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

    simulate(seconds, fps, cols, rows, on_frame)
    data = json.dumps({"fps": fps, "cols": cols, "rows": rows, "pal": list(pal), "R": row_list, "F": frames},
                      ensure_ascii=False, separators=(",", ":"))
    blob = base64.b64encode(gzip.compress(data.encode(), 9)).decode()
    html = HTML.replace("__DATA__", blob)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"{path}: {len(frames)} khung, {len(row_list)} dòng khác nhau, {len(html) // 1024} KB")


HTML = """<!DOCTYPE html>
<html lang="vi"><head><meta charset="utf-8"><title>Thắp chòm sao: bản xem thử</title>
<style>
body{margin:0;background:#1a1a1f;color:#ccc;font:14px -apple-system,system-ui,sans-serif;display:flex;
 flex-direction:column;align-items:center;gap:12px;padding:20px}
canvas{border-radius:8px;box-shadow:0 8px 40px #0008;max-width:100%}
.bar{display:flex;gap:10px;align-items:center}
button{background:#2a2a36;color:#ddd;border:1px solid #444;border-radius:6px;padding:4px 12px;font:inherit;cursor:pointer}
input[type=range]{width:420px}
</style></head><body>
<canvas id="c"></canvas>
<div class="bar"><button id="p">⏸</button><input id="s" type="range" min="0" value="0"><span id="t"></span>
<button id="sp">1×</button></div>
<script>
(async()=>{
const b=Uint8Array.from(atob("__DATA__"),c=>c.charCodeAt(0));
const D=JSON.parse(await new Response(new Blob([b]).stream().pipeThrough(new DecompressionStream("gzip"))).text());
const cv=document.getElementById("c"),x=cv.getContext("2d"),dpr=devicePixelRatio||1;
const FONT='15px Menlo,"SF Mono",Monaco,monospace',FB='bold '+FONT;
x.font=FONT;const cw=Math.ceil(x.measureText("M").width),ch=19;
cv.width=D.cols*cw*dpr;cv.height=D.rows*ch*dpr;cv.style.width=D.cols*cw+"px";cv.style.height=D.rows*ch+"px";
x.scale(dpr,dpr);x.textBaseline="middle";
const S=document.getElementById("s"),T=document.getElementById("t"),P=document.getElementById("p"),SP=document.getElementById("sp");
S.max=D.F.length-1;let play=true,f=0,acc=0,last=performance.now(),speed=1;
function draw(i){x.fillStyle="#000";x.fillRect(0,0,D.cols*cw,D.rows*ch);
 D.F[i].forEach((ri,r)=>{let c=0;for(const [s,fg,bg,bd] of D.R[ri]){for(const g of s){
  if(bg>=0){x.fillStyle=D.pal[bg];x.fillRect(c*cw,r*ch,cw+.5,ch+.5)}
  if(g!==" "&&g!=="\\0"){x.font=bd?FB:FONT;x.fillStyle=fg>=0?D.pal[fg]:"#d0d0d8";x.fillText(g,c*cw,r*ch+ch/2+1)}
  c++}}});
 S.value=i;T.textContent=(i/D.fps).toFixed(1)+"s / "+(D.F.length/D.fps).toFixed(0)+"s"}
function tick(now){const dt=(now-last)/1000;last=now;if(play){acc+=dt*speed;const n=Math.floor(acc*D.fps);
 if(n>0){acc-=n/D.fps;f=(f+n)%D.F.length;draw(f)}}requestAnimationFrame(tick)}
P.onclick=()=>{play=!play;P.textContent=play?"⏸":"▶"};
SP.onclick=()=>{speed=speed===1?.5:speed===.5?2:1;SP.textContent=speed+"×"};
S.oninput=()=>{f=+S.value;draw(f)};
draw(0);requestAnimationFrame(tick);
})();
</script></body></html>
"""


def dump():
    strip = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
    want = {}

    def on_frame(f, t, g, lines):
        a = g.anim
        tag = None
        if a and a.kind == "fly" and .45 < a.t < .5 and "fly" not in want:
            tag = "fly"
        elif a and a.kind == "glow" and a.t > .55 and "glow" not in want:
            tag = "glow"
        elif a and a.kind == "pan" and a.t > .5 and "pan" not in want:
            tag = "pan"
        elif g.k == 1 and len(g.stars.get(1, [])) == 4 and not g.busy() and "mid" not in want:
            tag = "mid"
        if tag:
            want[tag] = t
            print(f"=== {tag} @ {t:.1f}s ===")
            for line in lines:
                print(strip.sub("", line).rstrip())

    simulate(70, 30, 104, 26, on_frame)


if __name__ == "__main__":
    if "--dump" in sys.argv:
        dump()
    elif "--html" in sys.argv:
        i = sys.argv.index("--html")
        export_html(sys.argv[i + 1] if i + 1 < len(sys.argv) else "stars_preview.html")
    else:
        if not sys.stdin.isatty():
            sys.exit("Chạy trong terminal: python3 stars.py   (hoặc --dump / --html)")
        demo()
