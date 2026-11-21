// Chạy model ZIPA + chấm điểm ở luồng riêng để hoạt cảnh không bị khựng.
// Tin nhắn vào:  {type:"init", model: ArrayBuffer}  ·  {type:"judge", id, audio: Float32Array 16 kHz, entry}
// Tin nhắn ra:   {type:"ready", ms} · {type:"result", id, ...} · {type:"error", id?, message}
const ORT_VER = "1.31.1";
const ORT_CDN = `https://cdn.jsdelivr.net/npm/onnxruntime-web@${ORT_VER}/dist/`;
importScripts(ORT_CDN + "ort.wasm.min.js", "core.js");

let session = null;

async function getBuf(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`tải ${url}: HTTP ${r.status}`);
  return r.arrayBuffer();
}

async function init(model) {
  const t0 = performance.now();
  ort.env.wasm.numThreads = 1;               // GitHub Pages không gửi COOP/COEP: không có SharedArrayBuffer
  ort.env.wasm.wasmPaths = ORT_CDN;
  const [fbankBuf, lexBuf, lexJson, words] = await Promise.all([
    getBuf("../data/fbank.bin"), getBuf("../data/lex.bin"),
    fetch("../data/lex.json").then((r) => r.json()), fetch("../data/words.json").then((r) => r.json()),
  ]);
  V2I.init({ fbankBuf, lexBuf, lexJson, words });
  session = await ort.InferenceSession.create(model, { executionProviders: ["wasm"] });
  // chạy nháp 1 lần cho wasm "nóng" (lần chấm đầu tiên đỡ chậm)
  const fb = V2I.fbank(V2I.padAudio(new Float32Array(8000)));
  await run(fb);
  postMessage({ type: "ready", ms: Math.round(performance.now() - t0) });
}

async function run(fb) {
  const out = await session.run({
    x: new ort.Tensor("float32", fb.data, [1, fb.frames, 80]),
    x_lens: new ort.Tensor("int64", BigInt64Array.from([BigInt(fb.frames)]), [1]),
  });
  return out.log_probs;
}

async function judge(id, audio, entry) {
  const t0 = performance.now();
  const why = V2I.check(audio);
  if (why) return postMessage({ type: "result", id, error: why });
  const fb = V2I.fbank(V2I.padAudio(audio));
  const lp = await run(fb);
  const [, T, V] = lp.dims;
  const r = V2I.judge(lp.data, T, V, entry);
  r.ms = Math.round(performance.now() - t0);
  postMessage({ type: "result", id, ...r });
}

onmessage = (e) => {
  const m = e.data;
  const fail = (err) => postMessage({ type: "error", id: m.id, message: String(err && err.message || err) });
  if (m.type === "init") init(m.model).catch(fail);
  else if (m.type === "judge") judge(m.id, m.audio, m.entry).catch(fail);
};
