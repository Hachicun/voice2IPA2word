// Lõi chấm phát âm, chuyển từ app.py + ipa_us.py (chỉ model ZIPA). Chạy được cả trong trình duyệt (worker)
// lẫn Node (tools/check_core.js). Không gọi onnxruntime ở đây: nơi gọi tự chạy model rồi đưa log_probs vào.
(function (G) {
  "use strict";
  const SR = 16000;
  const MIN_PEAK = 0.02, MIN_SECONDS = 0.3;
  const PAD_SECONDS = 0.5, PAD_NOISE = 0.002;
  const AUTO_REVEAL = 0.9, GAME_NEAR = 0.6;
  const cps = (s) => Array.from(s);                  // duyệt theo code point như Python

  // ---------- âm thanh ----------
  function padAudio(x) {
    const n = Math.round(PAD_SECONDS * SR), out = new Float32Array(x.length + 2 * n);
    let seed = 12345;
    const rnd = () => {                              // Box-Muller trên LCG: chỉ cần tiếng ồn rất nhỏ
      seed = (seed * 1103515245 + 12345) >>> 0;
      return (seed + 1) / 4294967297;
    };
    const gauss = () => Math.sqrt(-2 * Math.log(rnd())) * Math.cos(2 * Math.PI * rnd());
    for (let i = 0; i < n; i++) { out[i] = gauss() * PAD_NOISE; out[n + x.length + i] = gauss() * PAD_NOISE; }
    out.set(x, n);
    return out;
  }

  // ---------- fbank (lhotse Fbank: 80 mel, povey, preemph 0.97, snip_edges=False) ----------
  let WIN = null, MEL = null;                         // cửa sổ 400, ma trận 257×80 (xuất từ lhotse)
  const NFFT = 512, NBIN = 257, NMEL = 80, FLEN = 400, FSHIFT = 160, EPS = 1.1920928955078125e-07;
  const TW = (() => {
    const c = new Float64Array(NFFT / 2), s = new Float64Array(NFFT / 2);
    for (let i = 0; i < NFFT / 2; i++) { c[i] = Math.cos(-2 * Math.PI * i / NFFT); s[i] = Math.sin(-2 * Math.PI * i / NFFT); }
    return { c, s };
  })();
  const REV = (() => {
    const r = new Uint16Array(NFFT), bits = Math.log2(NFFT);
    for (let i = 0; i < NFFT; i++) { let x = i, y = 0; for (let b = 0; b < bits; b++) { y = (y << 1) | (x & 1); x >>= 1; } r[i] = y; }
    return r;
  })();
  function fft(re, im) {                              // radix-2 tại chỗ
    for (let i = 0; i < NFFT; i++) {
      const j = REV[i];
      if (j > i) { let t = re[i]; re[i] = re[j]; re[j] = t; t = im[i]; im[i] = im[j]; im[j] = t; }
    }
    for (let size = 2; size <= NFFT; size <<= 1) {
      const half = size >> 1, step = NFFT / size;
      for (let i = 0; i < NFFT; i += size) {
        for (let k = 0; k < half; k++) {
          const wr = TW.c[k * step], wi = TW.s[k * step];
          const a = i + k, b = a + half;
          const xr = re[b] * wr - im[b] * wi, xi = re[b] * wi + im[b] * wr;
          re[b] = re[a] - xr; im[b] = im[a] - xi; re[a] += xr; im[a] += xi;
        }
      }
    }
  }
  function fbank(x) {
    const n = x.length;
    const F = Math.floor((n + FSHIFT / 2) / FSHIFT);
    const left = (FLEN - FSHIFT) / 2;
    const sample = (p) => {                           // đệm phản chiếu như lhotse _get_strided_batch
      if (p < left) return x[left - 1 - p];
      const q = p - left;
      return q < n ? x[q] : x[n - 1 - (q - n)];
    };
    const out = new Float32Array(F * NMEL);
    const fr = new Float64Array(FLEN), re = new Float64Array(NFFT), im = new Float64Array(NFFT), pw = new Float64Array(NBIN);
    for (let f = 0; f < F; f++) {
      let mu = 0;
      for (let i = 0; i < FLEN; i++) { fr[i] = sample(f * FSHIFT + i); mu += fr[i]; }
      mu /= FLEN;
      for (let i = 0; i < FLEN; i++) fr[i] -= mu;
      re.fill(0); im.fill(0);
      for (let i = FLEN - 1; i >= 0; i--) re[i] = (fr[i] - 0.97 * fr[i > 0 ? i - 1 : 0]) * WIN[i];
      fft(re, im);
      for (let k = 0; k < NBIN; k++) pw[k] = re[k] * re[k] + im[k] * im[k];
      for (let m = 0; m < NMEL; m++) {
        let s = 0;
        for (let k = 0; k < NBIN; k++) s += pw[k] * MEL[k * NMEL + m];
        out[f * NMEL + m] = Math.log(Math.max(s, EPS));
      }
    }
    return { data: out, frames: F };
  }

  // ---------- ctc_greedy (app.py) ----------
  const MODIFIERS = new Set(cps("˞ːʰʲʷˠˤʼ").concat(cps("̴̩̥̪̺̃̆̚")));
  function softmaxRows(logp, T, V) {                  // probs (chuẩn hoá lại) và log(probs + 1e-30) như app.py
    const P = new Float64Array(T * V), L = new Float64Array(T * V);
    for (let t = 0; t < T; t++) {
      let mx = -Infinity;
      for (let v = 0; v < V; v++) mx = Math.max(mx, logp[t * V + v]);
      let s = 0;
      for (let v = 0; v < V; v++) { const e = Math.exp(logp[t * V + v] - mx); P[t * V + v] = e; s += e; }
      for (let v = 0; v < V; v++) { P[t * V + v] /= s; L[t * V + v] = Math.log(P[t * V + v] + 1e-30); }
    }
    return { P, L };
  }
  function ctcGreedy(logp, P, T, V) {
    const out = [];
    let prev = null;
    for (let t = 0; t < T; t++) {
      let i = 0;
      for (let v = 1; v < V; v++) if (logp[t * V + v] > logp[t * V + i]) i = v;
      if (i === prev) {
        if (out.length && !LEX.skip.has(i)) out[out.length - 1][2] = Math.max(out[out.length - 1][2], P[t * V + i]);
        continue;
      }
      prev = i;
      if (!LEX.skip.has(i)) out.push([i, LEX.vocab[i] || "?", P[t * V + i]]);
    }
    const merged = [];
    for (const [, tok, c] of out) {
      if (merged.length && tok && cps(tok).every((ch) => MODIFIERS.has(ch))) {
        const m = merged[merged.length - 1];
        merged[merged.length - 1] = [m[0] + tok, Math.min(m[1], c)];
      } else merged.push([tok, c]);
    }
    return merged;
  }

  // ---------- ipa_us.from_model ----------
  const VOWELS = new Set(["iː", "ɪ", "e", "æ", "ɑː", "ɔː", "ʌ", "ʊ", "uː", "ə", "ɚ", "ɝː", "i", "u",
    "eɪ", "aɪ", "ɔɪ", "oʊ", "aʊ", "a", "ɔ"]);
  const DROP = new Set(cps("ʰʲʷˠˤʼː̴̥̪̺̃̚ˈˌ").concat(["̆"]));
  const ZMAP = {
    "ɹ": "r", "ɻ": "r", "ɽ": "r", "ʁ": "r", "ʀ": "r", "g": "ɡ", "ɢ": "ɡ", "ɣ": "ɡ", "ɠ": "ɡ",
    "ʛ": "ɡ", "ɟ": "ɡ", "c": "k", "q": "k", "x": "k", "χ": "h", "ħ": "h", "ɦ": "h", "ʜ": "h",
    "ç": "h", "ʋ": "v", "β": "v", "ⱱ": "v", "ɸ": "f", "ʍ": "w", "ɰ": "w", "ɥ": "w", "ɱ": "m",
    "ɳ": "n", "ɲ": "n", "ɴ": "ŋ", "ʈ": "t", "ɖ": "d", "ɗ": "d", "ᶑ": "d", "ɓ": "b", "ʙ": "b",
    "ɭ": "l", "ɺ": "l", "ɫ": "l", "ʎ": "l", "ʟ": "l", "ɬ": "l", "ɮ": "l", "ɕ": "ʃ", "ʂ": "ʃ",
    "ɧ": "ʃ", "ʑ": "ʒ", "ʐ": "ʒ", "ʝ": "j", "ʄ": "dʒ",
    "ɛ": "e", "ɐ": "ə", "ɘ": "ə", "ɵ": "ə", "ɤ": "ə", "ɞ": "ə", "ɨ": "ɪ", "ᵻ": "ɪ", "ʉ": "u",
    "ɯ": "u", "y": "u", "ʏ": "ʊ", "ø": "ʊ", "œ": "ʌ", "ɶ": "a", "ɒ": "ɑ", "ɜ": "ɝ", "ɝ": "ɝ",
  };
  const SKIPCH = new Set(cps("ǀǁǂǃʘʕʢʡ"));
  const DIPH = { "e ɪ": "eɪ", "a ɪ": "aɪ", "a ʊ": "aʊ", "o ʊ": "oʊ", "ɔ ɪ": "ɔɪ", "t ʃ": "tʃ", "d ʒ": "dʒ" };
  const V1 = new Set(cps("iɪeæaɑɔʌʊuəɚɝo"));
  function splitToken(tok) {
    const rhot = tok.includes("˞") || tok === "ɚ" || tok === "ɝ";
    const syl = tok.includes("̩") || tok.includes("̍");
    const base = cps(tok).filter((ch) => !DROP.has(ch) && !"˞̩̍".includes(ch)).join("");
    return [base, rhot, syl];
  }
  function fromModel(raw) {
    const units = [];
    for (const [tok, c] of raw) {
      let [base, rhot, syl] = splitToken(tok);
      if (base === "ɚ" || base === "ɝ") base = base === "ɚ" ? "ə" : "ɝ";
      if (base === "ʔ") { if (units.length) units.push(["t", c, false]); continue; }
      let chars = cps(base).filter((ch) => !SKIPCH.has(ch)).map((ch) => ZMAP[ch] || ch);
      chars = chars.flatMap((ch) => (cps(ch).length === 1 ? [ch] : cps(ch)));
      if (!chars.length) continue;
      if (syl && ["n", "l", "m"].includes(chars[chars.length - 1])) units.push(["ə", c, false]);
      chars.forEach((ch, k) => units.push([ch, c, rhot && k === chars.length - 1]));
    }
    const merged = [];
    for (const u of units) {
      const m = merged[merged.length - 1];
      const d = m && DIPH[m[0] + " " + u[0]];
      if (m && d && !m[2]) merged[merged.length - 1] = [d, Math.min(m[1], u[1]), u[2]];
      else merged.push(u.slice());
    }
    const out = [];
    for (const [sym, c, rhot] of merged) {
      if (!rhot) out.push([sym, c]);
      else if (sym === "ə") out.push(["ɚ", c]);
      else if (V1.has(sym)) out.push(["ɝ", c]);
      else if (["eɪ", "aɪ", "ɔɪ", "oʊ", "aʊ"].includes(sym)) out.push([sym, c], ["r", c]);
      else if (sym === "r") out.push(["r", c]);
      else out.push([sym, c], ["ɚ", c]);
    }
    const nvow = out.filter(([s]) => V1.has(s) || VOWELS.has(s)).length;
    return out.map(([sym, c], k) => {
      const nxt = k + 1 < out.length ? out[k + 1][0] : "", last = k === out.length - 1;
      if (sym === "ɔ") sym = nxt === "r" ? "ɔː" : "ɔ";
      else if (sym === "ɑ") sym = "ɑː";
      else if (sym === "o") sym = "oʊ";
      else if (sym === "ɝ") sym = "ɝː";
      else if (sym === "i") sym = last && nvow > 1 ? "i" : "iː";
      else if (sym === "u") sym = "uː";
      else if (sym === "ɾ") sym = "t̬";
      return [sym, c];
    });
  }

  // ---------- so khớp âm (app.py: _SUB_COST, phone_distance, align; ipa_us: resolve, key) ----------
  const NEAR_GROUPS = [
    [0.0, "a ɑ"], [0.3, "a æ"], [0.2, "t ɾ|d ɾ"], [0.3, "a ʌ"], [0.1, "ɑ ɔ?"],
    [0.4, "ɔ? oʊ|ɔ? ʊ|ɔ? ɔ|ɑ ɔ"],
    [0.4, "u ʌ|ʊ ʌ|ɑ ʌ|ɑ æ|æ e|e eɪ|i ɪ|ɪ e|ɪ eɪ|ɪ ə|u ʊ|ʊ oʊ|oʊ ɔ|ə ʌ|ə ɚ|ɚ ɝ|ɝ ə"],
    [0.4, "p b|t d|k ɡ|f v|s z|θ ð|ʃ ʒ|tʃ dʒ"],
    [0.5, "θ t|ð d|θ s|ð z|θ f|n ŋ|m n|ʃ tʃ|ʒ dʒ|z ʒ|s ʃ|l r|w v"],
  ];
  const SUB = new Map();
  for (const [cost, pairs] of NEAR_GROUPS) for (const p of pairs.split("|")) {
    const [x, y] = p.split(" ");
    SUB.set(x + " " + y, cost); SUB.set(y + " " + x, cost);
  }
  const sub = (x, y) => (x === y ? 0 : SUB.has(x + " " + y) ? SUB.get(x + " " + y) : 1);
  function phoneDistance(a, b) {
    let prev = Array.from({ length: b.length + 1 }, (_, j) => j);
    for (let i = 1; i <= a.length; i++) {
      const cur = [i];
      for (let j = 1; j <= b.length; j++) cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + sub(a[i - 1], b[j - 1]));
      prev = cur;
    }
    return prev[b.length];
  }
  function align(a, b) {
    const D = [];
    for (let i = 0; i <= a.length; i++) { D.push([]); for (let j = 0; j <= b.length; j++) D[i][j] = i === 0 || j === 0 ? i + j : 0; }
    for (let i = 1; i <= a.length; i++) for (let j = 1; j <= b.length; j++)
      D[i][j] = Math.min(D[i - 1][j] + 1, D[i][j - 1] + 1, D[i - 1][j - 1] + sub(a[i - 1], b[j - 1]));
    const out = [];
    let i = a.length, j = b.length;
    while (i || j) {
      if (i && j && D[i][j] === D[i - 1][j - 1] + sub(a[i - 1], b[j - 1])) { i--; j--; out.push([i, j]); }
      else if (i && D[i][j] === D[i - 1][j] + 1) { i--; out.push([i, null]); }
      else { j--; out.push([null, j]); }
    }
    return out.reverse();
  }
  const key = (ph) => ph.filter((p) => p).map((p) => (p === "t̬" ? "ɾ" : p === "ɔ" ? "ɔ?" : p.replace(/ː/g, "")));
  const AMBIG = { "a": ["ʌ", "ɑː"], "ɔ": ["ɑː", "ɔː"] };
  function resolve(model, ref) {
    const out = model.slice();
    for (const [i, j] of align(key(model), key(ref))) {
      if (i !== null && AMBIG[model[i]]) out[i] = j !== null && AMBIG[model[i]].includes(ref[j]) ? ref[j] : "ɑː";
    }
    return out.map((p) => (AMBIG[p] ? "ɑː" : p));
  }
  function scoreAgainst(heard, entry) {               // entry: một từ trong data/pool_*.json (ph: các cách đọc)
    let best = null;
    entry.ph.forEach((ref, k) => {
      const mine = resolve(heard, ref);
      const h = key(mine), r = key(ref);
      const sim = Math.max(0, 1 - phoneDistance(h, r) / Math.max(h.length, r.length));
      if (!best || sim > best.sim) best = { sim, k, mine, hkey: h, rkey: r, pairs: align(h, r) };
    });
    return best;
  }
  const pairStyle = (h, r) => (h === r ? "ok" : sub(h, r) < 1 ? "near" : "bad");

  // ---------- chấm CTC cả từ điển (Lexicon.word_scores, lex_totals) ----------
  let LEX = null, WORDS = null;
  function classLogp(L, T, V) {                       // [T, 1 + nc], cột 0 = blank; bỏ khung im lặng 2 đầu
    const C = LEX.nc + 1, E = new Float64Array(T * C);
    for (let t = 0; t < T; t++) {
      const row = t * V, er = t * C;
      E[er] = Math.exp(L[row]);
      for (const i of LEX.blank) if (i < V) E[er] += Math.exp(L[row + i]);
      for (let p = 0; p < LEX.pairs.length; p += 2) if (LEX.pairs[p] < V) E[er + LEX.pairs[p + 1]] += Math.exp(L[row + LEX.pairs[p]]);
      for (let c = 0; c < C; c++) E[er + c] = Math.log(E[er + c] + 1e-12);
    }
    const thr = Math.log(0.9);
    let v0 = -1, v1 = -1;
    for (let t = 0; t < T; t++) if (E[t * C] < thr) { if (v0 < 0) v0 = t; v1 = t; }
    const a = v0 < 0 ? 0 : Math.max(0, v0 - 2), b = v0 < 0 ? 1 : Math.min(T, v1 + 3);
    return { E: E.subarray(a * C, b * C), T: b - a, C };
  }
  function ctcBestPath(E, T, C, U, off, len) {
    const NEG = -1e9;
    const ab = new Float64Array(len + 1).fill(NEG), au = new Float64Array(len).fill(NEG);
    const nb = new Float64Array(len + 1), nu = new Float64Array(len);
    ab[0] = E[0];
    au[0] = E[U[off] + 1];
    for (let t = 1; t < T; t++) {
      const em = t * C, eb = E[em];
      nb[0] = ab[0] + eb;
      for (let j = 1; j <= len; j++) nb[j] = Math.max(ab[j], au[j - 1]) + eb;
      for (let j = 0; j < len; j++) {
        let v = Math.max(au[j], ab[j]);
        if (j > 0 && U[off + j] !== U[off + j - 1]) v = Math.max(v, au[j - 1]);
        nu[j] = v + E[em + U[off + j] + 1];
      }
      ab.set(nb); au.set(nu);
    }
    return Math.max(ab[len], au[len - 1]);
  }
  function lexTotals(L, T, V) {
    const { E, T: TT, C } = classLogp(L, T, V);
    const nc = LEX.nc, mx = new Float64Array(nc);
    mx.fill(-Infinity);
    for (let t = 0; t < TT; t++) for (let c = 0; c < nc; c++) mx[c] = Math.max(mx[c], E[t * C + c + 1]);
    const N = LEX.N, up = new Float64Array(N);
    for (let s = 0; s < N; s++) { let v = 0; for (let j = 0; j < LEX.ln[s]; j++) v += mx[LEX.U[LEX.off[s] + j]]; up[s] = v; }
    const order = Array.from({ length: N }, (_, i) => i).sort((x, y) => up[y] - up[x] || x - y);
    const best = new Float64Array(WORDS.w.length).fill(LEX.floor);
    for (const s of order.slice(0, LEX.keep)) {
      if (LEX.ln[s] > TT) continue;
      const sc = ctcBestPath(E, TT, C, LEX.U, LEX.off[s], LEX.ln[s]);
      if (sc > best[LEX.owner[s]]) best[LEX.owner[s]] = sc;
    }
    const total = new Float64Array(WORDS.w.length);
    for (let i = 0; i < total.length; i++) total[i] = LEX.prior * WORDS.z[i] + best[i];
    return total;
  }

  // ---------- khởi tạo ----------
  function init({ fbankBuf, lexBuf, lexJson, words }) {
    const fb = new Float32Array(fbankBuf);
    WIN = fb.subarray(0, FLEN); MEL = fb.subarray(FLEN);
    const dv = new DataView(lexBuf);
    if (String.fromCharCode(dv.getUint8(0), dv.getUint8(1), dv.getUint8(2), dv.getUint8(3)) !== "LEX1") throw new Error("lex.bin hỏng");
    const N = dv.getUint32(4, true), nc = dv.getUint32(8, true);
    let p = 12;
    const ln = new Uint8Array(lexBuf, p, N); p += N;
    const owner = new Uint16Array(lexBuf.slice(p, p + 2 * N)); p += 2 * N;
    const variant = new Uint8Array(lexBuf, p, N); p += N;
    const U = new Uint8Array(lexBuf, p);
    const off = new Uint32Array(N);
    for (let s = 1; s < N; s++) off[s] = off[s - 1] + ln[s - 1];
    LEX = { N, nc, ln, owner, variant, U, off, blank: lexJson.blank, pairs: Int32Array.from(lexJson.pairs.flat()),
      vocab: lexJson.vocab, skip: new Set(lexJson.skip), keep: lexJson.keep, floor: lexJson.floor, prior: lexJson.prior };
    WORDS = { w: words.w, z: words.z, index: new Map(words.w.map((w, i) => [w, i])) };
  }

  const pyRound = (x) => {                            // round() của Python: .5 về số chẵn
    const f = Math.floor(x), d = x - f;
    return d > 0.5 ? f + 1 : d < 0.5 ? f : f % 2 === 0 ? f : f + 1;
  };

  // logp: Float32Array [T, V] (đầu ra log_probs của ZIPA); entry: từ đích trong data/pool_*.json
  function judge(logp, T, V, entry) {
    const { P, L } = softmaxRows(logp, T, V);
    const raw = ctcGreedy(logp, P, T, V);
    const heard = fromModel(raw).map(([p]) => p);
    if (!heard.length) return { error: "no_phones", raw };
    const s = scoreAgainst(heard, entry);
    const total = lexTotals(L, T, V);
    const ti = WORDS.index.get(entry.w);
    let rank = null, top = 0;
    for (let i = 0; i < total.length; i++) if (total[i] > total[top]) top = i;
    if (ti !== undefined) { rank = 1; for (let i = 0; i < total.length; i++) if (total[i] > total[ti]) rank++; }
    const pct = pyRound(s.sim * 100);
    const correct = s.sim >= AUTO_REVEAL || rank === 1;
    return { raw, heard, sim: s.sim, pct, k: s.k, mine: s.mine, hkey: s.hkey, rkey: s.rkey, pairs: s.pairs,
      rank, heardAs: WORDS.w[top], correct,
      result: correct ? "correct" : pct >= GAME_NEAR * 100 ? "near" : "bad" };
  }

  function check(audio) {                             // trước khi chấm: đủ to, đủ dài
    let peak = 0;
    for (let i = 0; i < audio.length; i++) peak = Math.max(peak, Math.abs(audio[i]));
    if (audio.length < MIN_SECONDS * SR) return "too_short";
    if (peak < MIN_PEAK) return "too_quiet";
    return "";
  }

  const api = { SR, init, padAudio, fbank, judge, check, fromModel, scoreAgainst, pairStyle, VOWELS,
    _ctcGreedy: ctcGreedy, _softmaxRows: softmaxRows, _lexTotals: lexTotals };
  G.V2I = api;
  if (typeof module !== "undefined") module.exports = api;
})(typeof self !== "undefined" ? self : globalThis);
