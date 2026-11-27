// So js/core.js (+ onnxruntime-web) với kết quả Python của tools/ref_dump.py.
//   node towel_web/tools/check_core.js <thư mục ref> <thư mục node_modules có onnxruntime-web>
const fs = require("fs");
const path = require("path");
const WEB = path.join(__dirname, "..");
const [refDir, nm] = process.argv.slice(2);
const ort = require(path.join(nm, "onnxruntime-web"));
const V2I = require(path.join(WEB, "js", "core.js"));

const buf = (p) => { const b = fs.readFileSync(p); return b.buffer.slice(b.byteOffset, b.byteOffset + b.length); };
const f32 = (p) => new Float32Array(buf(p));

(async () => {
  ort.env.wasm.numThreads = 1;
  const pool = ["a1", "a2", "b1", "b2", "c1"].flatMap((b) => JSON.parse(fs.readFileSync(path.join(WEB, "data", `pool_${b}.json`), "utf8")));
  V2I.init({ fbankBuf: buf(path.join(WEB, "data", "fbank.bin")), lexBuf: buf(path.join(WEB, "data", "lex.bin")),
    lexJson: JSON.parse(fs.readFileSync(path.join(WEB, "data", "lex.json"), "utf8")),
    words: JSON.parse(fs.readFileSync(path.join(WEB, "data", "words.json"), "utf8")) });
  const sess = await ort.InferenceSession.create(path.join(WEB, "model", "model.int8.onnx"));
  const refs = JSON.parse(fs.readFileSync(path.join(refDir, "ref.json"), "utf8"));
  const allWords = JSON.parse(fs.readFileSync(path.join(WEB, "data", "words.json"), "utf8"));
  let same = { raw: 0, sim: 0, rank: 0, result: 0, simPy: 0, rankPy: 0 }, maxFb = 0, maxLp = 0;
  for (const r of refs) {
    // từ đích có thể ngoài pool (mức khác): dựng entry từ ref (ph lấy từ words_v4 qua Python không có sẵn ở đây)
    const entry = pool.find((e) => e.w === r.target);
    if (!entry) { console.log(r.n, r.target, "(không có trong kho từ, bỏ)"); continue; }
    const pcm = f32(path.join(refDir, r.n + ".pcm"));
    const fbPy = f32(path.join(refDir, r.n + ".fbank"));
    const fb = V2I.fbank(pcm);
    let d = 0;
    for (let i = 0; i < fb.data.length; i++) d = Math.max(d, Math.abs(fb.data[i] - fbPy[i]));
    maxFb = Math.max(maxFb, d);
    const t0 = Date.now();
    const out = await sess.run({ x: new ort.Tensor("float32", fb.data, [1, fb.frames, 80]),
      x_lens: new ort.Tensor("int64", BigInt64Array.from([BigInt(fb.frames)]), [1]) });
    const lp = out.log_probs, [, T, V] = lp.dims;
    const ms = Date.now() - t0;
    // logp Python là log softmax đã chuẩn hoá; so sau khi chuẩn hoá phía JS
    const { L } = V2I._softmaxRows(lp.data, T, V), lpPy = f32(path.join(refDir, r.n + ".logp"));
    for (let i = 0; i < L.length; i++) maxLp = Math.max(maxLp, Math.abs(Math.max(L[i], -30) - Math.max(lpPy[i], -30)));
    const j = V2I.judge(lp.data, T, V, entry);
    const jPy = V2I.judge(lpPy, lpPy.length / V, V, entry);   // chỉ phần chấm (bỏ qua sai lệch của model)
    const rawS = (x) => x.map((p) => p[0]).join(" ");
    const pyRes = (r.sim >= 0.9 || r.rank === 1) ? "correct" : Math.round(r.sim * 100) >= 60 ? "near" : "bad";
    const ok = { raw: rawS(j.raw) === rawS(r.raw), sim: Math.abs(j.sim - r.sim) < 1e-3, rank: j.rank === r.rank,
      result: j.result === pyRes, simPy: Math.abs(jPy.sim - r.sim) < 1e-3, rankPy: jPy.rank === r.rank };
    for (const k in ok) same[k] += ok[k];
    console.log(`${r.n} ${r.target.padEnd(9)} fbΔ ${d.toExponential(1)} ${ms}ms | py sim ${r.sim} rank ${r.rank} ${r.heard_as}`
      + ` | js sim ${j.sim.toFixed(4)} rank ${j.rank} ${j.heardAs} ${j.result}`
      + ` | js(logp py) sim ${jPy.sim.toFixed(4)} rank ${jPy.rank}`
      + (ok.raw ? "" : `\n     raw py: ${rawS(r.raw)}\n     raw js: ${rawS(j.raw)}`));
  }
  console.log("khớp:", same, "fbank Δmax", maxFb.toExponential(2), "logp Δmax", maxLp.toFixed(3));
})().catch((e) => { console.error(e); process.exit(1); });
