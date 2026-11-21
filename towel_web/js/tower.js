// LEO THÁP: luật + hoạt cảnh, chuyển 1:1 từ tower.py (class Tower, render_tower). Vẽ ra lưới ô chữ
// [{ch, fg, bg, b}], app.js vẽ lưới đó lên canvas. Màu là mã xterm-256 như bản terminal.
(function (G) {
  "use strict";
  const FH = 4, PW = 11, START = 50, GOAL = 100;
  const TIER_FG = { 1: 15, 2: 46, 3: 51, 4: 201, 5: 220 };
  const MAX_TIER = 5, GIVE_UP = 2, MILESTONE = 5;
  const BET = { false: [4, 4], true: [8, 10] };
  const POSES = {
    stand: [" o ", "/|\\", "/ \\"], jump: ["\\o/", " | ", "/ \\"], land: [" o ", "<|>", "/ \\"],
    fall1: ["\\o/", " | ", "\\ /"], fall2: ["_o_", " | ", "/ \\"], wob1: [" o/", "/| ", "/ \\"],
    wob2: ["\\o ", " |\\", "/ \\"], cheer1: ["\\o/", " | ", "/ \\"], cheer2: [" o ", "\\|/", "/ \\"],
    hurt: [" x ", "/|\\", "/ \\"],
  };
  const rand = (a, b) => a + Math.random() * (b - a);
  const choice = (xs) => xs[Math.floor(Math.random() * xs.length)];
  const chars = (s) => Array.from(String(s));

  class Tower {
    constructor({ start = START, goal = GOAL, sfx = null, onOver = null } = {}) {
      this.start = start; this.goal = goal; this.sfx = sfx; this.onOver = onOver;
      this.W = 30; this.TH = 24;
      this.reset(performance.now() / 1000);
    }
    reset(now) {
      this.f = this.best = this.start;
      this.score = this.combo = this.words = 0;
      this.firsts = this.bets = 0;
      this.cur = null;
      this.over = ""; this.overAt = 0;
      this.x = this.platX(this.f); this.h = Tower.feet(this.f);
      this.anim = null; this.queue = [];
      this.cheerUntil = this.shakeUntil = this.flashUntil = this.nextFirework = 0;
      this.breakUntil = 0;
      this.parts = []; this.texts = [];
      this.cam = this.camTarget();
    }
    resize(W, TH) {
      if (W === this.W && TH === this.TH) return;
      this.W = W; this.TH = TH;
      if (!this.anim) this.x = this.platX(this.f);
      this.cam = this.camTarget();
    }
    static feet(f) { return f * FH + 1; }
    platX(f) {
      const W = this.W;
      if (f <= 0 || f >= this.goal) return Math.floor(W / 2);
      const half = Math.floor(W / 2);
      const [lo, hi] = f % 2 ? [4 + Math.floor(PW / 2), half - 2] : [half + 2, W - 3 - Math.floor(PW / 2)];
      let s = (f * 7919) >>> 0;                       // số giả ngẫu nhiên cố định theo tầng
      s = Math.imul(s ^ (s >>> 16), 0x45d9f3b) >>> 0; s = Math.imul(s ^ (s >>> 16), 0x45d9f3b) >>> 0; s = (s ^ (s >>> 16)) >>> 0;
      const top = Math.max(lo, hi);
      return lo + (s % (top - lo + 1));
    }
    push(ev) { if (ev && !this.over) this.queue.push(ev); }

    // --- luật ---
    beginWord(hard) {
      this.words += 1;
      this.cur = { hard, tries: 0, bet: false, peeked: false, gaveUp: false, done: false };
    }
    betOdds() { return BET[!!(this.cur && this.cur.hard)]; }
    placeBet() {
      const c = this.cur;
      if (this.over || !c || c.done) return "chưa có từ để cược";
      if (c.bet) return "đã cược từ này rồi";
      if (c.tries || c.peeked || c.gaveUp) return "chỉ cược được trước lần nói đầu tiên";
      if (this.bets <= 0) return `chưa có lượt cược (nói đúng ngay đủ ${MILESTONE} từ để nhặt 1 lượt)`;
      this.bets -= 1; c.bet = true;
      return "";
    }
    attempt(result) {
      const c = this.cur;
      if (this.over || !c || c.done) return null;
      c.tries += 1;
      const first = c.tries === 1, betting = c.bet && first;
      const [win, lose] = BET[c.hard];
      if (c.peeked || c.gaveUp) { c.done = result === "correct"; return [c.done ? "free" : "practice", 0, false]; }
      if (result === "correct") {
        c.done = true;
        let milestone = false;
        if (first) { this.firsts += 1; if (this.firsts % MILESTONE === 0) { this.bets += 1; milestone = true; } }
        return betting ? ["bet_win", win, milestone] : [first ? "perfect" : "ok", first ? 2 : 1, milestone];
      }
      if (result === "near") return [betting ? "bet_near" : "near", 0, false];
      return betting ? ["bet_lose", lose, false] : ["bad", 1, false];
    }
    giveUp(peek) {
      const c = this.cur;
      if (this.over || !c || c.done) return null;
      c.peeked = c.peeked || peek;
      if (c.gaveUp) return null;
      c.gaveUp = true;
      return ["giveup", c.bet && !c.tries ? BET[c.hard][1] : GIVE_UP, false];
    }
    busy() { return this.anim !== null || this.queue.length > 0; }

    // --- sự kiện ---
    sound(name) { if (this.sfx) try { this.sfx(name); } catch (e) { /* bỏ qua */ } }
    startAnim(kind, dur, now, kw = {}) { this.anim = Object.assign({ kind, t0: now, dur, x0: this.x, h0: this.h }, kw); }
    text(s, fg, dh = 0, life = 1.2) { this.texts.push({ s, x: this.x, h: this.h + 4 + dh, fg, life }); }
    tier() { return Math.max(1, Math.min(this.combo, MAX_TIER)); }
    charFg(now) { return now < this.breakUntil ? 244 : TIER_FG[this.tier()]; }
    breakCombo(now) {
      if (this.combo >= 2) { this.breakUntil = now + 0.8; this.text("mất combo", 244, 3.0); }
      this.combo = 0;
    }
    burst(n, colors, cs, { up = 9, at = 1, x = null, h = null, spread = 9, g = 18, life = 0.9 } = {}) {
      x = x === null ? this.x : x; h = h === null ? this.h + at : h;
      for (let i = 0; i < n; i++) this.parts.push({ x: x + rand(-1, 1), h, vx: rand(-spread, spread), vh: rand(up * 0.3, up), g,
        life: rand(life * 0.45, life), ch: choice(chars(cs)), fg: choice(colors) });
    }
    next(now) {
      let [ev, n, milestone] = this.queue.shift();
      if (["perfect", "ok", "bet_win"].includes(ev)) {
        n = Math.min(n || (ev === "perfect" ? 2 : 1), this.goal - this.f);
        const prev = this.tier();
        this.combo += 1;
        const tier = this.tier();
        this.score += 100 * n * tier;
        this.f += n;
        this.best = Math.max(this.best, this.f);
        this.text(`+${n} TẦNG`, 46);
        if (ev === "bet_win") this.text("THẮNG CƯỢC!", 214, 1.5);
        else if (ev === "perfect") this.text("PERFECT!", 220, 1.5);
        if (this.combo >= 2) this.text(`COMBO ×${this.combo}`, TIER_FG[tier], 3.0);
        if (milestone) this.text("+1 LƯỢT CƯỢC", 214, 4.5, 2.0);
        this.burst(10, [46, 220, 15], "*+.");
        this.sound(ev === "bet_win" ? "win" : (tier > prev && tier >= 2) || milestone ? "combo" : ev);
        this.startAnim("jump", 0.42 + 0.12 * n, now, { x1: this.platX(this.f), h1: Tower.feet(this.f), arc: 2.5 + n });
      } else if (ev === "free") {
        this.text("đúng (đã xem đáp án)", 250); this.cheerUntil = now + 0.9; this.sound("ok");
      } else if (ev === "practice") {
        this.text("luyện tập: không tính", 244);
      } else if (ev === "bet") {
        this.text("CƯỢC!", 214, 1.5); this.sound("near");
      } else if (ev === "near" || ev === "bet_near") {
        this.text(ev === "bet_near" ? "gần đúng… mất lượt cược" : "gần đúng…", 220);
        this.sound("near");
        this.startAnim("wobble", 0.7, now);
      } else if (["bad", "bet_lose", "giveup"].includes(ev)) {
        n = n || 1;
        this.breakCombo(now);
        this.f = Math.max(0, this.f - n);
        if (ev === "bet_lose") this.text("THUA CƯỢC", 196, 1.5);
        else if (ev === "giveup") this.text("bỏ từ", 244, 1.5);
        this.text(`-${n}`, 196);
        this.sound("bad");
        this.startAnim("fall", 0.45 + 0.08 * (n - 1), now, { x1: this.platX(this.f), h1: Tower.feet(this.f) });
      }
    }
    end(result, now) {
      this.over = result; this.overAt = now;
      this.queue = [];
      if (result === "win") { this.sound("win"); this.nextFirework = now; }
      if (this.onOver) try { this.onOver(result); } catch (e) { console.error(e); }
    }
    finish(a, now) {
      const k = a.kind;
      if (k === "jump" || k === "fall") { this.x = a.x1; this.h = a.h1; }
      if (k === "wobble") this.x = a.x0;
      if (k === "jump") {
        this.burst(6, [250, 230], ".'", { up: 5, at: 0 });
        if (this.f >= this.goal) this.end("win", now); else this.cheerUntil = now + 0.9;
      }
      if (k === "fall") {
        this.shakeUntil = now + 0.3;
        this.burst(8, [244, 250], ".,'", { up: 4, at: 0 });
        if (this.f <= 0) {
          this.flashUntil = now + 0.6; this.shakeUntil = now + 0.5;
          this.burst(18, [196, 202, 208, 214], "°*o", { up: 11, at: 0 });
          this.sound("lose");
          this.startAnim("sink", 0.7, now);
        }
      }
      if (k === "sink") this.end("lose", now);
    }
    update(dt, now) {
      const a = this.anim;
      if (a) {
        const t = Math.min(1, (now - a.t0) / a.dur);
        if (a.kind === "jump") {
          this.x = a.x0 + (a.x1 - a.x0) * t;
          this.h = a.h0 + (a.h1 - a.h0) * t + a.arc * 4 * t * (1 - t);
        } else if (a.kind === "fall") {
          this.x = a.x0 + (a.x1 - a.x0) * Math.min(1, t * 1.6);
          this.h = a.h0 + (a.h1 - a.h0) * t * t;
        } else if (a.kind === "wobble") {
          this.x = a.x0 + (Math.sin(t * Math.PI * 6) > 0 ? 1 : -1) * (t < 0.9 ? 1 : 0);
        } else if (a.kind === "sink") {
          this.h = a.h0 - 2.5 * t;
        }
        if (t >= 1) { this.anim = null; this.finish(a, now); }
      } else if (this.queue.length && !this.over) {
        this.next(now);
      }
      if (this.cam < 2 && Math.random() < dt * 4) {
        this.parts.push({ x: rand(1, this.W - 2), h: 1.5, vx: 0, vh: rand(2, 4), g: 4, life: rand(0.3, 0.7), ch: choice(["°", "o"]), fg: 214 });
      }
      if (this.over === "win" && now >= this.nextFirework) {
        this.nextFirework = now + rand(0.25, 0.6);
        this.burst(14, [choice([196, 46, 51, 201, 226, 208])], "*+o.", { up: 6, spread: 10, g: 6,
          x: rand(4, this.W - 5), h: this.cam + this.TH * rand(0.55, 0.9) });
      }
      for (const p of this.parts) { p.x += p.vx * dt; p.h += p.vh * dt; p.vh -= p.g * dt; p.life -= dt; }
      this.parts = this.parts.filter((p) => p.life > 0);
      for (const t of this.texts) { t.h += 2.5 * dt; t.life -= dt; }
      this.texts = this.texts.filter((t) => t.life > 0);
      this.cam += (this.camTarget() - this.cam) * Math.min(1, dt * 5);
    }
    camTarget() {
      const t = Math.min(this.h - this.TH * 0.35, this.goal * FH + 8 - this.TH);
      return Math.max(t, -4);
    }
    pose(now) {
      const a = this.anim, blink = Math.floor(now * 8) % 2;
      if (a) {
        if (a.kind === "jump") return (now - a.t0) / a.dur < 0.65 ? "jump" : "land";
        if (a.kind === "fall") return blink ? "fall1" : "fall2";
        if (a.kind === "wobble") return blink ? "wob1" : "wob2";
        return "hurt";
      }
      if (this.over === "lose") return "hurt";
      if (this.over === "win" || now < this.cheerUntil) return blink ? "cheer1" : "cheer2";
      return "stand";
    }
  }

  // ---------- vẽ tháp ra lưới ô chữ (render_tower) ----------
  function renderTower(g, now) {
    const W = g.W, TH = g.TH;
    const grid = Array.from({ length: TH }, () => Array.from({ length: W }, () => null));
    const cam = Math.round(g.cam), goalH = g.goal * FH;
    const srow = (h) => TH - 1 - (Math.round(h) - cam);
    const put = (x, r, ch, fg = null, bg = null, b = false) => {
      if (r >= 0 && r < TH && x >= 0 && x < W) grid[r][x] = { ch, fg, bg, b };
    };
    for (let r = 0; r < TH; r++) {
      const wr = cam + TH - 1 - r;
      for (let x = 1; x < W - 1; x++) {
        const hsh = (((Math.imul(wr, 73856093) ^ Math.imul(x, 19349663)) % 97) + 97) % 97;
        if (wr > goalH + 3) { if (hsh < 2) put(x, r, hsh ? "+" : ".", 229); }
        else if (hsh < 3) put(x, r, ".", 237);
      }
    }
    const wall = now < g.flashUntil ? 160 : g.over === "win" ? 46 : 239;
    for (let r = 0; r < TH; r++) if (cam + TH - 1 - r <= goalH) { put(0, r, "│", wall); put(W - 1, r, "│", wall); }
    const f0 = Math.max(1, Math.floor((cam - 1) / FH) - 1), f1 = Math.min(g.goal, Math.floor((cam + TH) / FH) + 1);
    for (let f = f0; f <= f1; f++) {
      const r = srow(f * FH);
      if (r < 0 || r >= TH) continue;
      if (f === g.goal) { for (let x = 1; x < W - 1; x++) put(x, r, "▀", 220, null, true); continue; }
      const cx = g.platX(f), col = f === g.start ? 51 : 180;
      for (let x = cx - Math.floor(PW / 2); x <= cx + Math.floor(PW / 2); x++) put(x, r, "▀", col);
      chars(f).forEach((ch, i) => put(1 + i, r, ch, f % 10 === 0 ? 250 : 242, null, f % 10 === 0));
    }
    const fx = W - 7;
    ["|>>", "|", "|"].forEach((s, i) => chars(s).forEach((ch, j) => put(fx + j, srow(goalH + 3 - i), ch, ch === ">" ? 196 : 250, null, true)));
    chars(`ĐÍCH ${g.goal}`).forEach((ch, j) => put(3 + j, srow(goalH + 2), ch, 220, null, true));
    const tick = Math.floor(now * 6);
    for (let r = 0; r < TH; r++) {
      const wr = cam + TH - 1 - r;
      if (wr > 1) continue;
      for (let x = 1; x < W - 1; x++) {
        if (wr === 1) put(x, r, (x + tick) % 5 === 0 ? "^" : "~", 214);
        else {
          const k = (((x * 3 + wr * 5 + tick) % 7) + 7) % 7;
          put(x, r, k < 3 ? "▓" : k < 5 ? "▒" : "░", [202, 208, 196][k % 3], 52);
        }
      }
    }
    for (const p of g.parts) put(Math.round(p.x), srow(p.h), p.ch, p.fg);
    const fg = g.charFg(now), px = Math.round(g.x);
    POSES[g.pose(now)].forEach((line, i) => {
      const r = srow(g.h + 2 - i);
      chars(line).forEach((ch, j) => { if (ch !== " ") put(px - 1 + j, r, ch, fg, null, true); });
    });
    for (const t of g.texts) {
      const s = chars(t.s);
      const x0 = Math.max(1, Math.min(W - 1 - s.length, Math.round(t.x) - Math.floor(s.length / 2)));
      s.forEach((ch, j) => put(x0 + j, srow(t.h), ch, t.fg, null, true));
    }
    if (g.over && now - g.overAt > 0.6) {
      const box = g.over === "win"
        ? ["", "CHIẾN THẮNG!", `Lên tầng ${g.goal} sau ${g.words} từ`, `Điểm: ${g.score}`, "bấm CHƠI LẠI", ""]
        : ["", "RƠI VÀO DUNG NHAM!", `Cao nhất: tầng ${g.best}`, `${g.words} từ · điểm ${g.score}`, "bấm CHƠI LẠI", ""];
      const bg = g.over === "win" ? 22 : 52;
      const bw = Math.min(W - 2, Math.max(...box.map((s) => chars(s).length)) + 4);
      const bx = Math.floor((W - bw) / 2), by = Math.floor(TH / 2) - Math.floor(box.length / 2);
      box.forEach((s, i) => {
        const c = chars(s), padL = Math.floor((bw - c.length) / 2);
        const line = Array(Math.max(0, padL)).fill(" ").concat(c).concat(Array(bw).fill(" ")).slice(0, bw);
        line.forEach((ch, j) => put(bx + j, by + i, ch, i === 1 ? 226 : 15, bg, true));
      });
    }
    let shift = 0;
    if (now < g.shakeUntil) shift = Math.random() < 0.5 ? 1 : -1;
    return { grid, shift };
  }

  // ---------- bảng màu xterm-256 ----------
  const BASE16 = ["#000000", "#cd0000", "#00cd00", "#cdcd00", "#0000ee", "#cd00cd", "#00cdcd", "#e5e5e5",
    "#7f7f7f", "#ff0000", "#00ff00", "#ffff00", "#5c5cff", "#ff00ff", "#00ffff", "#ffffff"];
  const XTERM = [];
  for (let i = 0; i < 256; i++) {
    if (i < 16) XTERM.push(BASE16[i]);
    else if (i < 232) {
      const n = i - 16, v = (c) => (c ? 55 + c * 40 : 0);
      const r = v(Math.floor(n / 36)), g = v(Math.floor(n / 6) % 6), b = v(n % 6);
      XTERM.push(`rgb(${r},${g},${b})`);
    } else { const l = 8 + (i - 232) * 10; XTERM.push(`rgb(${l},${l},${l})`); }
  }

  G.TowerGame = { Tower, renderTower, XTERM, TIER_FG, BET, GIVE_UP, MILESTONE, START, GOAL };
})(typeof self !== "undefined" ? self : globalThis);
