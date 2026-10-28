// A take's voice in numbers, worked out here in the browser from the microphone's samples, which are then dropped:
// no audio is kept or sent. What leaves is seven numbers, each a change from the visitor's usual voice.

const RATE = 12000; // the samples are taken down to this before anything is measured
const FRAME = 512; // ~43 ms
const HOP = 128; // ~11 ms
const LOW = 70; // Hz, the lowest pitch read
const HIGH = 420;

/** The microphone, listening until stop() is called; level(v) is told how loud it is as it goes. */
export async function listen(level) {
  // Auto gain off: loudness is one of the measures.
  const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false } });
  const ctx = new AudioContext();
  const source = ctx.createMediaStreamSource(stream);
  const node = ctx.createScriptProcessor(4096, 1, 1);
  const chunks = [];
  node.onaudioprocess = (e) => {
    const x = e.inputBuffer.getChannelData(0);
    chunks.push(new Float32Array(x));
    let s = 0;
    for (let i = 0; i < x.length; i++) s += x[i] * x[i];
    level?.(Math.sqrt(s / x.length));
  };
  source.connect(node);
  node.connect(ctx.destination);
  return {
    async stop() {
      node.disconnect();
      source.disconnect();
      stream.getTracks().forEach((t) => t.stop());
      const rate = ctx.sampleRate;
      await ctx.close();
      const raw = features(downsample(chunks, rate));
      chunks.length = 0; // the samples go here
      return raw;
    },
  };
}

function downsample(chunks, rate) {
  const step = rate / RATE;
  const total = chunks.reduce((n, c) => n + c.length, 0);
  const out = new Float32Array(Math.floor(total / step));
  let i = 0;
  let acc = 0;
  let n = 0;
  let next = step;
  let at = 0;
  for (const c of chunks) {
    for (let j = 0; j < c.length; j++, at++) {
      acc += c[j];
      n++;
      if (at + 1 >= next) {
        if (i < out.length) out[i++] = acc / n;
        acc = 0;
        n = 0;
        next += step;
      }
    }
  }
  return out;
}

const semis = (hz) => 12 * Math.log2(hz / 100);
const quantile = (xs, q) => {
  if (!xs.length) return 0;
  const s = [...xs].sort((a, b) => a - b);
  return s[Math.min(s.length - 1, Math.max(0, Math.round(q * (s.length - 1))))];
};
const mean = (xs) => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : 0);

/** The take's own numbers: pitch, its range and wobble, loudness, pace, pauses, seconds spoken. */
export function features(x) {
  const frames = [];
  for (let start = 0; start + FRAME <= x.length; start += HOP) {
    const f = x.subarray(start, start + FRAME);
    let e = 0;
    for (let i = 0; i < FRAME; i++) e += f[i] * f[i];
    frames.push({ rms: Math.sqrt(e / FRAME), f, e });
  }
  if (frames.length < 20) return null;
  const floor = quantile(frames.map((f) => f.rms), 0.1);
  const gate = Math.max(floor * 3, 0.004);
  const loud = frames.map((f) => f.rms > gate);
  const first = loud.indexOf(true);
  const last = loud.lastIndexOf(true);
  if (first < 0 || last - first < 20) return null;

  const pitches = [];
  const db = [];
  for (let k = first; k <= last; k++) {
    if (!loud[k]) continue;
    db.push(20 * Math.log10(frames[k].rms));
    const hz = pitchOf(frames[k].f, frames[k].e);
    pitches[k] = hz;
  }
  const voiced = pitches.map((hz, k) => (hz ? { k, s: semis(hz) } : null)).filter(Boolean);
  if (voiced.length < 10) return null;
  const st = voiced.map((v) => v.s);
  const jumps = [];
  for (let i = 1; i < voiced.length; i++) {
    const d = Math.abs(voiced[i].s - voiced[i - 1].s);
    if (voiced[i].k - voiced[i - 1].k === 1 && d < 2) jumps.push(d);
  }

  // Syllables: peaks of the smoothed loudness inside the spoken span, at least ~100 ms apart.
  const env = [];
  for (let k = first; k <= last; k++) {
    let s = 0;
    let n = 0;
    for (let j = Math.max(first, k - 4); j <= Math.min(last, k + 4); j++, n++) s += frames[j].rms;
    env.push(s / n);
  }
  let peaks = 0;
  let lastPeak = -100;
  for (let i = 1; i < env.length - 1; i++) {
    if (env[i] > gate * 1.5 && env[i] >= env[i - 1] && env[i] > env[i + 1] && i - lastPeak > 9) {
      peaks++;
      lastPeak = i;
    }
  }
  const spanFrames = last - first + 1;
  const seconds = (spanFrames * HOP) / RATE;
  const silent = loud.slice(first, last + 1).filter((v) => !v).length;
  return {
    pitch: quantile(st, 0.5),
    range: Math.max(0.5, quantile(st, 0.9) - quantile(st, 0.1)),
    loudness: mean(db),
    pace: Math.max(0.5, peaks / Math.max(0.5, seconds)),
    pauses: silent / spanFrames,
    wobble: Math.max(0.02, mean(jumps)),
    seconds,
  };
}

/** The frame's pitch in Hz by autocorrelation, or 0 when it is not clearly voiced. */
function pitchOf(f, energy) {
  const lo = Math.floor(RATE / HIGH);
  const hi = Math.ceil(RATE / LOW);
  let best = 0;
  let bestLag = 0;
  for (let lag = lo; lag <= hi; lag++) {
    let s = 0;
    for (let i = 0; i + lag < FRAME; i++) s += f[i] * f[i + lag];
    const r = s / energy;
    if (r > best) {
      best = r;
      bestLag = lag;
    }
  }
  return best > 0.45 ? RATE / bestLag : 0;
}

/** The usual voice: each number's median over the takes Ada was told were the truth. */
export function usual(takes) {
  const keys = ['pitch', 'range', 'loudness', 'pace', 'pauses', 'wobble', 'perWord'];
  return Object.fromEntries(keys.map((k) => [k, quantile(takes.map((t) => t[k]), 0.5)]));
}

/** A take as Ada reads it: each number against the usual voice. Seconds a word only when the words are known. */
export function against(raw, base) {
  const ratio = (a, b) => (b > 0 ? a / b : 1);
  return {
    pitch: raw.pitch - base.pitch,
    range: ratio(raw.range, base.range),
    loudness: raw.loudness - base.loudness,
    pace: ratio(raw.pace, base.pace),
    pauses: raw.pauses - base.pauses,
    wobble: ratio(raw.wobble, base.wobble),
    length: raw.perWord ? ratio(raw.perWord, base.perWord) : 1,
  };
}
