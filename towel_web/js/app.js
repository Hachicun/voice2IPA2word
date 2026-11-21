// LEO THÁP bản web: canvas chỉ vẽ tháp; chữ, nút, nhật ký là thẻ HTML (style.css). Micro, âm thanh, luồng chơi
// chuyển từ GameMode/GuessMode của app.py. Chấm điểm chạy trong worker.js (ZIPA + core.js).
(function () {
  "use strict";
  const { Tower, renderTower, XTERM, TIER_FG, BET, GIVE_UP, MILESTONE } = window.TowerGame;
  const SR = 16000;
  const MODEL_URL = "model/model.int8.onnx";
  const MODEL_MB = 70.7;
  const CACHE = "towel-model-v1";
  const COLS = 30;                                      // bề rộng tháp (ô chữ)
  const SLOW_FACTOR = 0.7;
  // Bản ghi giọng Mỹ: bảng {từ: đường dẫn mp3} dựng sẵn từ dump Wiktionary (build_audio.py, cách của english_dictionary)
  const COMMONS = "https://upload.wikimedia.org/wikipedia/commons/";
  const LEVELS = {                                    // như --level của bản terminal (khoảng zipf)
    easy: { name: "Dễ", bands: ["easy"] },
    mid: { name: "Trung bình", bands: ["easy", "mid"] },
    hard: { name: "Khó", bands: ["hard"] },
  };
  const params = new URLSearchParams(location.search);
  const $ = (id) => document.getElementById(id);
  // lớp CSS cho từng kiểu chữ trong nhật ký (log(["chữ", COL.ok, đậm?, mono?]))
  const COL = { ok: "ok", near: "near", bad: "bad", dim: "dim", text: "", bold: "", gold: "gold", orange: "orange" };

  // ---------- màn hình ----------
  let screen = "loading";                             // loading | tap | starting | play | error
  function show(name) {
    screen = name;
    $("loading").hidden = name !== "loading";
    $("start").hidden = name !== "tap" && name !== "starting";
    $("error").hidden = name !== "error";
    $("game").hidden = name !== "play";
    if (name === "play") fitTower();
  }

  // ---------- nhật ký ----------
  const logEl = $("log"), logs = [];
  function log(...runs) {                             // log(["chữ", lớp, đậm?, mono?], ...) ; log() = dòng trống
    const p = document.createElement("p");
    for (const r of runs) {
      const [text, cls, bold, mono] = typeof r === "string" ? [r] : r;
      const span = document.createElement("span");
      span.textContent = text;
      const c = [cls, bold && "b", mono && "mono"].filter(Boolean).join(" ");
      if (c) span.className = c;
      p.appendChild(span);
    }
    logs.push(runs.map((r) => (typeof r === "string" ? [r] : r)));
    const stick = logEl.scrollHeight - logEl.scrollTop - logEl.clientHeight < 40;   // đang ở cuối thì cuộn theo
    logEl.appendChild(p);
    while (logEl.childNodes.length > 120) logEl.removeChild(logEl.firstChild);
    if (stick) logEl.scrollTop = logEl.scrollHeight;
  }

  // ---------- âm thanh ----------
  let ac = null;                                      // AudioContext (mở khi chạm lần đầu)
  let playing = null;                                 // nguồn đang phát
  let playEnd = 0;                                    // thời điểm (performance.now) phát xong
  function stopPlayback() {
    if (playing) { try { playing.stop(); } catch (e) { /* đã dừng */ } playing = null; }
    playEnd = 0;
    if (window.speechSynthesis) speechSynthesis.cancel();
  }
  function playSamples(x, sr) {                       // Float32Array mono
    stopPlayback();
    const buf = ac.createBuffer(1, x.length, sr);
    buf.getChannelData(0).set(x);
    const src = ac.createBufferSource();
    src.buffer = buf; src.connect(ac.destination); src.start();
    playing = src;
    playEnd = performance.now() + (x.length / sr) * 1000;
    src.onended = () => { if (playing === src) { playing = null; playEnd = 0; } };
  }
  function pad(x, sr, a, b) {                         // TTS_PAD: loa/tai nghe Bluetooth hay cắt âm đầu/cuối
    const out = new Float32Array(x.length + Math.round((a + b) * sr));
    out.set(x, Math.round(a * sr));
    return out;
  }
  function timeStretch(x, sr, factor) {               // WSOLA, như time_stretch() ở app.py
    const win = Math.floor(0.04 * sr), hopOut = Math.floor(win / 2), hopIn = Math.max(1, Math.floor(hopOut * factor));
    const tol = Math.floor(0.01 * sr);
    const w = new Float32Array(win);
    for (let i = 0; i < win; i++) w[i] = 0.5 - 0.5 * Math.cos((2 * Math.PI * i) / (win - 1));
    const xx = new Float32Array(tol + x.length + 2 * win + tol);
    xx.set(x, tol);
    const out = new Float32Array(Math.floor(xx.length / factor) + 2 * win), norm = new Float32Array(out.length);
    let posIn = tol, posOut = 0, prev = -1;
    while (posIn + win + tol < xx.length && posOut + win < out.length) {
      let best = posIn;
      if (prev >= 0) {
        let bv = -Infinity;
        for (let o = 0; o <= 2 * tol; o++) {
          let s = 0;
          const a = posIn - tol + o, b = prev + hopOut;
          for (let i = 0; i < win; i += 2) s += xx[a + i] * xx[b + i];
          if (s > bv) { bv = s; best = a; }
        }
      }
      for (let i = 0; i < win; i++) { out[posOut + i] += xx[best + i] * w[i]; norm[posOut + i] += w[i]; }
      prev = best; posIn += hopIn; posOut += hopOut;
    }
    const res = new Float32Array(posOut);
    for (let i = 0; i < posOut; i++) res[i] = out[i] / Math.max(norm[i], 1e-3);
    return res;
  }

  // tiếng hiệu ứng (thay âm thanh hệ thống macOS của bản terminal)
  function tone(freq, t0, dur, type = "sine", vol = 0.25, slideTo = null) {
    const o = ac.createOscillator(), g = ac.createGain();
    o.type = type; o.frequency.setValueAtTime(freq, t0);
    if (slideTo) o.frequency.exponentialRampToValueAtTime(slideTo, t0 + dur);
    g.gain.setValueAtTime(0.0001, t0);
    g.gain.exponentialRampToValueAtTime(vol, t0 + 0.01);
    g.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
    o.connect(g); g.connect(ac.destination);
    o.start(t0); o.stop(t0 + dur + 0.02);
  }
  function sfx(name) {
    if (!ac || params.get("sfx") === "0") return;
    const t = ac.currentTime + 0.01;
    switch (name) {
      case "perfect": tone(1318, t, 0.25, "sine", 0.2); tone(1760, t + 0.08, 0.35, "sine", 0.2); break;
      case "ok": tone(660, t, 0.12, "sine", 0.25, 880); break;
      case "near": tone(2093, t, 0.12, "triangle", 0.12); break;
      case "bad": tone(220, t, 0.35, "sawtooth", 0.08, 110); break;
      case "combo": tone(1568, t, 0.2, "sine", 0.18); tone(2349, t + 0.06, 0.3, "sine", 0.14); break;
      case "win": [523, 659, 784, 1046].forEach((f, i) => tone(f, t + i * 0.11, 0.35, "triangle", 0.2)); break;
      case "lose": [392, 311, 262, 196].forEach((f, i) => tone(f, t + i * 0.16, 0.4, "sawtooth", 0.07)); break;
      default: tone(880, t, 0.1);
    }
  }

  // ---------- micro: bấm 1 lần để nói, tự dừng khi bạn im lặng ----------
  // ghi âm: bấm 🎤 để bắt đầu, bấm lần nữa để dừng (không tự dừng)
  let micStream = null, micNode = null, rec = null;   // rec: {chunks, sr, t} khi đang ghi
  let micLevel = 0, micError = "", opening = null, micSrc = null;
  function openMic() {                                // trả về Promise; gọi lại được khi lần trước bị từ chối
    if (opening) return opening;
    opening = navigator.mediaDevices.getUserMedia({ audio: {
      channelCount: 1, echoCancellation: false, noiseSuppression: false, autoGainControl: false } })
      .then((st) => { micStream = st; micError = ""; micSrc = ac.createMediaStreamSource(st); attachMic(micSrc); })
      .catch((err) => {
        micError = "Chưa mở được micro" + (err && err.name ? ` (${err.name})` : "") + ".";
        throw err;
      })
      .finally(() => { opening = null; });
    return opening;
  }
  function attachMic(srcNode) {                       // nguồn âm (micro, hoặc bản ghi khi kiểm thử) -> rec.chunks
    if (!micNode) {
      micNode = ac.createScriptProcessor(2048, 1, 1);
      micNode.onaudioprocess = (e) => {
        const x = e.inputBuffer.getChannelData(0), dt = x.length / ac.sampleRate;
        let s2 = 0; for (let i = 0; i < x.length; i++) s2 += x[i] * x[i];
        const rms = Math.sqrt(s2 / x.length);
        micLevel = Math.max(rms, micLevel * 0.85);
        if (rec) { rec.chunks.push(new Float32Array(x)); rec.t += dt; }
        e.outputBuffer.getChannelData(0).fill(0);
      };
      micNode.connect(ac.destination);
    }
    srcNode.connect(micNode);
  }
  async function wake() {                             // khoá màn hình xong quay lại: AudioContext bị treo, micro bị tắt
    if (!ac) return;
    if (ac.state !== "running") try { await ac.resume(); } catch (e) { /* thử lại lần chạm sau */ }
    if (micStream && micStream.getAudioTracks().every((t) => t.readyState === "ended")) {
      micStream = null;
      try { await openMic(); } catch (e) { log(["  " + micError, COL.bad]); }
    }
  }
  async function to16k(x, sr) {
    if (sr === SR) return x;
    try {
      const n = Math.ceil((x.length * SR) / sr);
      const oc = new OfflineAudioContext(1, n, SR);
      const b = oc.createBuffer(1, x.length, sr);
      b.getChannelData(0).set(x);
      const s = oc.createBufferSource();
      s.buffer = b; s.connect(oc.destination); s.start();
      return (await oc.startRendering()).getChannelData(0).slice();
    } catch (e) {                                     // dự phòng: lấy trung bình từng đoạn
      const r = sr / SR, out = new Float32Array(Math.floor(x.length / r));
      for (let i = 0; i < out.length; i++) {
        const a = Math.floor(i * r), b = Math.max(a + 1, Math.floor((i + 1) * r));
        let s = 0; for (let j = a; j < b; j++) s += x[j]; out[i] = s / (b - a);
      }
      return out;
    }
  }

  // ---------- kho từ + bản ghi giọng Mỹ (Wikimedia Commons), dự phòng giọng máy ----------
  const BANDS = {};                                   // easy | mid | hard -> [mục từ]
  let level = "mid", pool = [], poolPos = 0;
  function setLevel(lv) {
    level = lv;
    pool = LEVELS[lv].bands.flatMap((b) => BANDS[b]);
    for (let i = pool.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [pool[i], pool[j]] = [pool[j], pool[i]]; }
    poolPos = 0;
    try { localStorage.setItem("towel-level", lv); } catch (e) { /* không lưu được: thôi */ }
  }
  async function loadClip(e) {                        // -> {x, sr} đã chuẩn hoá âm lượng 0.8; lỗi: ném lỗi
    if (e.clip) return e.clip;
    const r = await fetch(COMMONS + e.a);
    if (!r.ok) throw new Error("HTTP " + r.status);
    const ab = await ac.decodeAudioData(await r.arrayBuffer());
    const x = ab.getChannelData(0).slice();
    let pk = 1e-3; for (let i = 0; i < x.length; i++) pk = Math.max(pk, Math.abs(x[i]));
    for (let i = 0; i < x.length; i++) x[i] *= 0.8 / pk;
    e.clip = { x, sr: ab.sampleRate };
    return e.clip;
  }
  async function findWord() {                         // tải trước bản ghi; lỗi (mất mạng…) thì giọng máy đọc
    if (poolPos >= pool.length) setLevel(level);      // hết vòng: xáo lại
    const e = pool[poolPos++];
    try { await loadClip(e); } catch (err) { e.tts = true; }
    return e;
  }
  // giọng máy (Web Speech): giọng Mỹ cài sẵn tốt nhất, bỏ giọng "novelty" của Apple (như english_dictionary)
  const NOVELTY = /Albert|Bad News|Bahh|Bells|Boing|Bubbles|Cellos|Good News|Jester|Organ|Superstar|Trinoids|Whisper|Wobble|Zarvox/;
  let voice = null;
  function pickVoice() {
    const vs = speechSynthesis.getVoices().filter((v) => /^en[-_]US/i.test(v.lang) && !NOVELTY.test(v.name));
    voice = vs.find((v) => /premium/i.test(v.name + v.voiceURI)) || vs.find((v) => /enhanced/i.test(v.name + v.voiceURI))
      || ["Samantha", "Ava", "Zoe", "Allison", "Nicky", "Google US English"].map((n) => vs.find((v) => v.name.startsWith(n))).find(Boolean)
      || vs.find((v) => v.localService) || vs[0] || null;
  }
  if ("speechSynthesis" in window) { pickVoice(); speechSynthesis.onvoiceschanged = pickVoice; }
  function speak(text, slow) {
    if (!("speechSynthesis" in window)) return;
    const u = new SpeechSynthesisUtterance(text);
    u.lang = "en-US"; u.rate = slow ? 0.7 : 1;
    if (voice) u.voice = voice;
    speechSynthesis.cancel();
    speechSynthesis.speak(u);
  }
  function say(e, slow) {
    if (!e) return;
    if (e.clip) {
      let x = e.clip.x;
      if (slow) { e.slowClip = e.slowClip || timeStretch(x, e.clip.sr, SLOW_FACTOR); x = e.slowClip; }
      playSamples(pad(x, e.clip.sr, 0.15, 0.4), e.clip.sr);
    } else {
      stopPlayback();
      speak(e.w, slow);
    }
  }

  // ---------- chấm điểm (worker) ----------
  let worker = null, workerReady = false, judgeId = 0;
  const pending = new Map();
  function startWorker(model) {
    return new Promise((resolve, reject) => {
      worker = new Worker("js/worker.js");
      worker.onmessage = (ev) => {
        const m = ev.data;
        if (m.type === "ready") { workerReady = true; resolve(m.ms); }
        else if (m.type === "result" && pending.has(m.id)) { pending.get(m.id).resolve(m); pending.delete(m.id); }
        else if (m.type === "error") {
          if (m.id !== undefined && pending.has(m.id)) { pending.get(m.id).reject(new Error(m.message)); pending.delete(m.id); }
          else reject(new Error(m.message));
        }
      };
      worker.onerror = (e) => reject(new Error(e.message || "worker lỗi"));
      worker.postMessage({ type: "init", model }, [model]);
    });
  }
  function judge(audio, entry) {
    const id = ++judgeId;
    return new Promise((resolve, reject) => {
      pending.set(id, { resolve, reject });
      worker.postMessage({ type: "judge", id, audio, entry: { w: entry.w, ph: entry.ph } }, [audio.buffer]);
    });
  }

  // ---------- tải model (có thanh tiến trình, lưu Cache API để lần sau khỏi tải) ----------
  let loadMsg = "Đang tải…", loadFrac = 0;
  async function fetchModel() {
    let cache = null;
    try { cache = await caches.open(CACHE); } catch (e) { /* không có Cache API (http thường) */ }
    if (cache) {
      const hit = await cache.match(MODEL_URL);
      if (hit) { loadMsg = "Đọc model ZIPA đã lưu…"; loadFrac = 1; return hit.arrayBuffer(); }
    }
    const r = await fetch(MODEL_URL);
    if (!r.ok) throw new Error(`tải model: HTTP ${r.status}`);
    const total = +r.headers.get("content-length") || MODEL_MB * 1e6;
    const reader = r.body.getReader(), parts = [];
    let got = 0;
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      parts.push(value); got += value.length;
      loadFrac = Math.min(1, got / total);
      loadMsg = `Tải model ZIPA (lần đầu) ${(got / 1e6).toFixed(1)} / ${(total / 1e6).toFixed(1)} MB`;
    }
    const buf = new Uint8Array(got);
    let p = 0; for (const c of parts) { buf.set(c, p); p += c.length; }
    if (cache) try { await cache.put(MODEL_URL, new Response(buf.slice().buffer)); } catch (e) { /* đầy bộ nhớ: lần sau tải lại */ }
    return buf.buffer;
  }

  // ---------- trạng thái chơi (GameMode) ----------
  const tower = new Tower({ sfx, onOver });
  let word = null;                                    // {entry, best, tries, revealed, correct, last}
  let busy = false;                                   // đang chấm
  let finding = false;
  let history = [];
  const rounds = [];

  function onOver(result) {
    rounds.push([result, tower.best, tower.words, tower.score]);
    log();
    if (result === "win") log([`🏆 CHIẾN THẮNG! Lên tầng ${tower.goal} sau ${tower.words} từ, ${tower.score} điểm.`, COL.ok, true]);
    else log([`🔥 Rơi vào dung nham sau ${tower.words} từ (cao nhất tầng ${tower.best}).`, COL.bad, true]);
  }

  async function newWord() {
    if (finding) return;
    finding = true;
    if (word) history.push(word);
    word = null;
    stopPlayback();
    const e = await findWord();
    finding = false;
    if (!e) { log(["Không có từ nào ở mức này.", COL.bad]); return; }
    word = { entry: e, best: 0, tries: 0, revealed: false, correct: false, last: null };
    tower.beginWord(e.hard);
    const [win, lose] = tower.betOdds();
    log();
    log([`── Từ #${tower.words} ──`, COL.bold, true], ["  🔊  ", COL.text],
      [`từ ${e.hard ? "KHÓ" : "DỄ"} · cược +${win}/−${lose}`, COL.dim]);
    say(e);
    if (!e.clip) log(["  (giọng máy đọc)", COL.dim]);
    const nxt = pool[poolPos];                        // tải sẵn bản ghi từ kế tiếp
    if (nxt) loadClip(nxt).catch(() => {});
  }

  function reveal() {
    if (!word) return;
    const e = word.entry;
    const ipa = [...new Set(e.ipa)].map((p) => `/${p}/`).join("  ");
    log(["  ➜ ", COL.text], [e.w, COL.bold, true], [`  ${ipa}  →  `, COL.text], [e.vi, COL.text]);
    if (word.last) {
      const { mine, k, hkey, rkey, pairs } = word.last;
      const ref = e.ph[k], top = [], bot = [];
      for (const [i, j] of pairs) {
        const a = j !== null ? ref[j] : "-", b = i !== null ? mine[i] : "-";
        const st = i === null || j === null ? "bad" : V2Istyle(hkey[i], rkey[j]);
        const w = Math.max(Array.from(a).length, Array.from(b).length);
        top.push([a.padEnd(w + (a.length - Array.from(a).length)) + "  ", COL.text, false, true]);
        bot.push([b.padEnd(w + (b.length - Array.from(b).length)) + "  ", COL[st], false, true]);
      }
      log(["     chuẩn: ", COL.dim], ...top);
      log(["     bạn  : ", COL.dim], ...bot);
    }
    word.revealed = true;
  }
  function V2Istyle(h, r) { return h === r ? "ok" : NEAR_PAIRS.has(h + " " + r) ? "near" : "bad"; }
  const NEAR_PAIRS = new Set();                       // giống _pair_style: cặp âm gần (lấy từ core qua worker không tiện, nên ghi lại)
  ("a ɑ|a æ|t ɾ|d ɾ|a ʌ|ɑ ɔ?|ɔ? oʊ|ɔ? ʊ|ɔ? ɔ|ɑ ɔ|u ʌ|ʊ ʌ|ɑ ʌ|ɑ æ|æ e|e eɪ|i ɪ|ɪ e|ɪ eɪ|ɪ ə|u ʊ|ʊ oʊ|oʊ ɔ|ə ʌ|ə ɚ|ɚ ɝ|ɝ ə|"
    + "p b|t d|k ɡ|f v|s z|θ ð|ʃ ʒ|tʃ dʒ|θ t|ð d|θ s|ð z|θ f|n ŋ|m n|ʃ tʃ|ʒ dʒ|z ʒ|s ʃ|l r|w v").split("|").forEach((p) => {
    const [x, y] = p.split(" "); NEAR_PAIRS.add(x + " " + y); NEAR_PAIRS.add(y + " " + x);
  });
  const scoreColor = (sim) => (sim >= 0.9 ? COL.ok : sim >= 0.6 ? COL.near : COL.bad);

  async function onAudio(audio) {                     // GuessMode.on_audio + GameMode.on_audio
    if (!word) return;
    const w = word, wasCorrect = w.correct;
    busy = true;
    let r;
    try { r = await judge(audio, w.entry); }
    catch (err) { busy = false; log([`  Lỗi chấm: ${err.message}`, COL.bad]); return; }
    busy = false;
    if (w !== word) return;                           // đã sang từ khác
    if (r.error === "too_quiet" || r.error === "no_phones") {
      log(["  Không nghe rõ" + (r.error === "too_quiet" ? " (quá nhỏ)" : "") + ", thử nói to và gần micro hơn.", COL.near]);
      return;
    }
    if (r.error === "too_short") { log(["  Ngắn quá: bấm 🎤 rồi nói cả từ.", COL.near]); return; }
    w.tries += 1;
    w.best = Math.max(w.best, r.sim);
    w.last = r;
    log([`  Lần ${w.tries}: `, COL.text], [`/${r.mine.join("")}/  `, COL.text], [`${r.pct}%`, scoreColor(r.sim), true],
      [`   (cao nhất ${Math.round(w.best * 100)}%)`, COL.dim]);
    const phones = r.pairs.map(([i, j]) => (i === null ? ["_ ", COL.bad] : j === null ? [r.mine[i] + " ", COL.bad]
      : [r.mine[i] + " ", COL[V2Istyle(r.hkey[i], r.rkey[j])]]));
    log(["      ", COL.text], ...phones, r.rank === 1 ? ["  model nhận ra đúng từ ✓", COL.ok]
      : [`  model nghe giống: ${r.heardAs}` + (r.rank ? ` · từ đích xếp hạng ${r.rank}` : ""), COL.dim]);
    if (r.correct && !w.correct) {
      w.correct = true;
      log(["  ✓ Chính xác!", COL.ok, true]);
      if (!w.revealed) reveal();
    }
    if (wasCorrect || tower.over) return;             // đã đúng rồi (luyện thêm) hoặc đã hết ván
    const ev = tower.attempt(r.result);
    if (!ev) return;
    if (ev[0].startsWith("bet_")) {
      log([{ bet_win: `  🎲 THẮNG CƯỢC: +${ev[1]} tầng!`, bet_lose: `  🎲 Thua cược: −${ev[1]} tầng.`,
        bet_near: "  🎲 Gần đúng: mất lượt cược." }[ev[0]], ev[0] === "bet_win" ? COL.ok : COL.bad]);
    }
    if (ev[2]) log([`  ★ Đủ ${tower.firsts} từ đúng ngay: +1 lượt cược (bấm Cược ở từ sau).`, COL.ok]);
    // đợi phát xong bản ghi của bạn rồi mới nhảy/rơi (tiếng hiệu ứng không đè lên giọng bạn)
    const wait = Math.min(5000, Math.max(0, playEnd - performance.now()));
    setTimeout(() => tower.push(ev), wait);
  }

  // ---------- phím / nút ----------
  function act(id) {
    if (screen !== "play") return;
    const t = tower;
    if ((id === "next" || id.startsWith("lv:")) && t.over) {
      if (id.startsWith("lv:")) setLevel(id.slice(3));
      t.reset(performance.now() / 1000);
      log(); log([`══ Chơi lại từ tầng ${t.start} · mức ${LEVELS[level].name} ══`, COL.bold, true]);
      newWord();
      return;
    }
    if (t.over && (id === "bet" || id === "answer")) return;
    if (!word && id !== "next") return;
    if (id === "listen") say(word.entry);
    else if (id === "slow") say(word.entry, true);
    else if (id === "bet") {
      const why = t.placeBet();
      if (why) { log([`  Không cược được: ${why}.`, COL.dim]); return; }
      const [win, lose] = t.betOdds();
      log([`  🎲 Đã cược từ ${t.cur.hard ? "khó" : "dễ"}: nói đúng ngay +${win} tầng, sai −${lose}, gần đúng mất lượt.`, COL.near]);
      t.push(["bet", 0, false]);
    } else if (id === "answer" || id === "next") {
      if (word && !word.correct) {
        const ev = t.giveUp(id === "answer");
        if (ev) {
          log([`  Bỏ từ: −${ev[1]} tầng.` + (id === "answer" ? " Giờ luyện thoải mái, không bị trừ nữa." : ""), COL.bad]);
          t.push(ev);
        }
      }
      if (id === "answer") reveal(); else newWord();
    }
  }
  async function talk() {                            // nút nói: bấm để bắt đầu, bấm lần nữa để dừng sớm
    if (screen !== "play") return;
    if (tower.over) { act("next"); return; }
    if (rec) { stopRec(); return; }
    if (busy || !word) return;
    if (!micStream && !params.has("nomic")) {
      try { await openMic(); }
      catch (err) { log(["  " + micError, COL.bad]); return; }
    }
    if (!micNode) { log(["  Chưa có micro" + (params.has("nomic") ? " (đang mở với ?nomic)." : "."), COL.bad]); return; }
    startRec();
  }
  function startRec() {
    if (screen !== "play" || rec || busy || !word || !micNode || tower.over) return;
    stopPlayback();
    if (ac.state !== "running") ac.resume();
    rec = { chunks: [], sr: ac.sampleRate, t: 0 };
  }
  async function stopRec() {
    if (!rec || rec.closing) return;
    const r = rec;
    r.closing = true;
    await new Promise((res) => setTimeout(res, 150));  // nhận nốt khối mẫu cuối
    if (rec === r) rec = null;
    if (!r.t) { log(["  Micro không gửi âm thanh. Tải lại trang hoặc thử Chrome.", COL.bad]); return; }
    const n = r.chunks.reduce((s, c) => s + c.length, 0);
    const x = new Float32Array(n);
    let p = 0; for (const c of r.chunks) { x.set(c, p); p += c.length; }
    if (x.length) playSamples(x, r.sr);               // phát lại bản ghi của bạn
    const a16 = await to16k(x, r.sr);
    onAudio(a16);
  }

  // ---------- nút / phím ----------
  for (const b of document.querySelectorAll("[data-act]")) b.addEventListener("click", () => { b.blur(); wake(); act(b.dataset.act); });
  for (const b of document.querySelectorAll("[data-level]")) b.addEventListener("click", () => { if (screen === "tap") begin(b.dataset.level); });
  $("talk").addEventListener("click", () => { $("talk").blur(); wake(); talk(); });
  // máy tính: Space như nút nói (bấm để nói, bấm lần nữa để dừng), phím tắt như bản terminal
  document.addEventListener("keydown", (e) => {
    if (e.repeat || e.metaKey || e.ctrlKey || e.altKey) return;
    if (screen === "tap") {                           // 1 2 3 chọn mức, Enter/Space: mức lần trước
      const lv = { "1": "easy", "2": "mid", "3": "hard" }[e.key] || ((e.key === " " || e.key === "Enter") && level);
      if (lv) { e.preventDefault(); begin(lv); }
      return;
    }
    if (screen !== "play") return;
    const k = e.key.toLowerCase();
    if (e.key === " ") { e.preventDefault(); talk(); }
    else if (k === "r") act("listen"); else if (k === "s") act("slow"); else if (k === "c") act("bet");
    else if (k === "a" || e.key === "Enter") act("answer"); else if (k === "n") act("next");
  });
  document.addEventListener("visibilitychange", () => { if (!document.hidden) wake(); });

  async function begin(lv) {                          // chạm lần đầu: mở âm thanh + micro (cần cử chỉ người dùng)
    if (screen !== "tap") return;
    show("starting");
    $("start-title").textContent = "Đang mở micro…";
    setLevel(lv);
    try {
      ac = ac || new (window.AudioContext || window.webkitAudioContext)();
      const resumed = ac.resume();
      if ("speechSynthesis" in window) speechSynthesis.speak(new SpeechSynthesisUtterance(""));   // iOS: mở khoá giọng máy
      await resumed;
    } catch (err) { /* âm thanh mở lại ở lần chạm sau (wake) */ }
    let micOk = params.has("nomic");
    if (!micOk) try { await openMic(); micOk = true; } catch (err) { /* báo trong nhật ký, bấm nút nói để thử lại */ }
    show("play");
    if (!micOk) log(["  " + micError, COL.bad]);
    newWord();
  }

  // ---------- vẽ tháp (canvas nét theo devicePixelRatio) ----------
  const cv = $("tower"), ctx = cv.getContext("2d");
  let T = null;                                       // {cw, ch, rows, x, y, dpr}
  function fitTower() {
    const r = cv.getBoundingClientRect(), dpr = window.devicePixelRatio || 1;
    if (!r.width || !r.height) return;
    cv.width = Math.round(r.width * dpr); cv.height = Math.round(r.height * dpr);
    const cw = r.width / COLS, ch = cw * 1.8;
    const rows = Math.max(6, Math.floor(r.height / ch));
    T = { cw, ch, rows, dpr, x: 0, y: (r.height - rows * ch) / 2, w: r.width, h: r.height };
    tower.resize(COLS, rows);
  }
  if (window.ResizeObserver) new ResizeObserver(fitTower).observe($("tower").parentElement);
  window.addEventListener("resize", fitTower);
  const MONO = getComputedStyle(document.documentElement).getPropertyValue("--mono") || "monospace";
  function drawTower(now) {
    if (!T) return;
    const { grid, shift } = renderTower(tower, now);
    ctx.setTransform(T.dpr, 0, 0, T.dpr, 0, 0);
    ctx.fillStyle = "#050505"; ctx.fillRect(0, 0, T.w, T.h);
    ctx.textBaseline = "middle"; ctx.textAlign = "center";
    const fNormal = `${(T.cw * 1.62).toFixed(1)}px ${MONO}`, fBold = "bold " + fNormal;
    for (let r = 0; r < grid.length; r++) {
      const row = grid[r];
      for (let c = 0; c < row.length; c++) {
        const cell = row[c];
        if (!cell) continue;
        const x = T.x + (c + shift) * T.cw, y = T.y + r * T.ch;
        if (cell.bg !== null) { ctx.fillStyle = XTERM[cell.bg]; ctx.fillRect(x, y, T.cw + 0.5, T.ch + 0.5); }
        const col = XTERM[cell.fg === null ? 15 : cell.fg], ch = cell.ch;
        if (ch === "▀") { ctx.fillStyle = col; ctx.fillRect(x, y, T.cw + 0.5, T.ch * 0.42); }
        else if (ch === "▓" || ch === "▒" || ch === "░") {
          ctx.globalAlpha = ch === "▓" ? 0.75 : ch === "▒" ? 0.5 : 0.25;
          ctx.fillStyle = col; ctx.fillRect(x, y, T.cw + 0.5, T.ch + 0.5); ctx.globalAlpha = 1;
        } else if (ch === "│") { ctx.fillStyle = col; ctx.fillRect(x + T.cw * 0.45, y, Math.max(1, T.cw * 0.12), T.ch + 0.5); }
        else if (ch !== " ") { ctx.font = cell.b ? fBold : fNormal; ctx.fillStyle = col; ctx.fillText(ch, x + T.cw / 2, y + T.ch / 2); }
      }
    }
  }

  // ---------- HUD + nút (chỉ ghi DOM khi đổi) ----------
  const shown = {};
  function set(id, prop, val) {
    const k = id + "." + prop;
    if (shown[k] === val) return;
    shown[k] = val;
    const el = $(id);
    if (prop === "text") el.textContent = val;
    else if (prop === "html") el.innerHTML = val;
    else if (prop === "hidden") el.hidden = val;
    else if (prop.startsWith("--")) el.style.setProperty(prop, val);
    else if (prop.startsWith("data-")) el.setAttribute(prop, val);
    else el.style[prop] = val;
  }
  const esc = (s) => String(s).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" })[c]);
  function updateUi() {
    const g = tower;
    set("hud-level", "text", LEVELS[level].name);
    set("hud-word", "text", `từ #${g.words}`);
    set("hud-floor", "text", String(g.f));
    set("hud-best", "text", `cao nhất ${g.best}`);
    set("hud-bar", "width", `${Math.max(3, Math.min(100, (g.f / g.goal) * 100))}%`);
    set("hud-bar", "background", g.f < 15 ? "var(--bad)" : g.f < 35 ? "var(--near)" : "var(--ok)");
    set("hud-score", "text", String(g.score));
    set("hud-combo", "text", g.combo >= 2 ? `COMBO ×${g.combo}` : "");
    set("hud-combo", "color", XTERM[TIER_FG[g.tier()]]);
    const c = g.cur;
    let bet = `Cược <b class="${g.bets ? "orange" : "dim"}">${g.bets} lượt</b> <span class="dim">đúng ngay ${g.firsts % MILESTONE}/${MILESTONE}</span>`;
    if (c && !c.done && !c.gaveUp) {
      const [win, lose] = BET[c.hard], kind = c.hard ? "KHÓ" : "DỄ";
      if (c.bet && !c.tries) bet += ` <b class="orange">ĐANG CƯỢC ${kind} +${win}/−${lose}</b>`;
      else if (!c.tries && !c.bet) bet += ` <span class="dim">từ ${kind}: +${win}/−${lose}</span>`;
    }
    set("hud-bet", "html", bet);
    // nút nói
    let state, label;
    if (g.over) { state = "over"; label = "↻  CHƠI LẠI"; }
    else if (rec) { state = "rec"; label = "●  ĐANG GHI… bấm để dừng"; }
    else if (busy) { state = "busy"; label = "…  đang chấm"; }
    else if (finding || !word) { state = "wait"; label = "…  đang tìm từ"; }
    else if (!micStream && !params.has("nomic")) { state = "mic"; label = "🎤  BẬT MICRO"; }
    else { state = "idle"; label = "🎤  BẤM ĐỂ NÓI"; }
    set("talk", "data-state", state);
    set("talk-label", "text", label);
    if (rec) $("talk").style.setProperty("--level", Math.min(1, Math.sqrt(micLevel / 0.2)).toFixed(2));
    set("tools", "hidden", !!g.over);
    set("levels", "hidden", !g.over);
    for (const b of $("tools").children) {
      const id = b.dataset.act;
      const off = !word || (id === "bet" && !(g.bets > 0 && c && !c.tries && !c.bet && !c.gaveUp));
      if (b.disabled !== off) b.disabled = off;
    }
    for (const b of $("levels").children) b.setAttribute("aria-current", String(b.dataset.act === "lv:" + level));
  }

  let last = performance.now();
  function frame(ms) {
    const now = ms / 1000, dt = Math.min(0.1, (ms - last) / 1000);
    last = ms;
    if (screen === "play") { tower.update(dt, now); drawTower(now); updateUi(); }
    requestAnimationFrame(frame);
  }

  // ---------- khởi động ----------
  async function main() {
    requestAnimationFrame(frame);
    const progress = setInterval(() => { $("load-msg").textContent = loadMsg; $("load-bar").value = loadFrac; }, 100);
    try {
      const bands = ["easy", "mid", "hard"];
      const [model, ...lists] = await Promise.all([fetchModel(), ...bands.map((b) => fetch(`data/pool_${b}.json`).then((r) => r.json()))]);
      bands.forEach((b, i) => { BANDS[b] = lists[i]; });
      try { const lv = localStorage.getItem("towel-level"); if (LEVELS[lv]) level = lv; } catch (e) { /* mặc định: mid */ }
      for (const el of document.querySelectorAll("[data-count]"))
        el.textContent = LEVELS[el.dataset.count].bands.reduce((s, k) => s + BANDS[k].length, 0).toLocaleString("vi");
      for (const b of document.querySelectorAll("[data-level]")) b.setAttribute("aria-current", String(b.dataset.level === level));
      loadMsg = "Khởi động model…";
      await startWorker(model);
      clearInterval(progress);
      show("tap");
    } catch (err) {
      clearInterval(progress);
      $("error-msg").textContent = "Lỗi khi tải: " + (err.message || err);
      show("error");
      console.error(err);
    }
  }

  // để kiểm thử không cần micro: __towel.feed(Float32Array 16 kHz) chấm như vừa nói xong
  // __towel.simMic(url): phát bản ghi vào đúng đường micro (ScriptProcessor ở tần số của máy -> to16k), "bấm dừng"
  // 0,3 s sau khi hết: kiểm thử cả phần ghi âm mà không cần micro.
  async function simMic(url) {
    const buf = await ac.decodeAudioData(await (await fetch(url)).arrayBuffer());
    const src = ac.createBufferSource();
    src.buffer = buf;
    attachMic(src);
    startRec();
    await new Promise((res) => { src.onended = res; src.start(); });
    await new Promise((res) => setTimeout(res, 300));  // người dùng bấm dừng sau khi nói xong
    await stopRec();
  }
  window.__towel = { feed: (a) => onAudio(a), simMic, tower, get word() { return word; }, act, logs, talk,
    get rec() { return rec; }, get sampleRate() { return ac && ac.sampleRate; } };
  main();
})();
