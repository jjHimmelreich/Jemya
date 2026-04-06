/**
 * audio-processor.js — Runs in page context on open.spotify.com
 *
 * Creates a true dry/wet Web Audio EQ routing:
 * source -> dry -> destination
 * source -> 10-band filter chain -> wet -> destination
 */

let audioContext = null;
let sourceNode = null;
let audioElRef = null;
let eqEnabled = false;
let connected = false;

let inputGain = null;
let dryGain = null;
let wetGain = null;
const BAND_DEFS = [
  { key: 'hz32', freq: 32, type: 'lowshelf', q: 0.7 },
  { key: 'hz64', freq: 64, type: 'peaking', q: 0.9 },
  { key: 'hz125', freq: 125, type: 'peaking', q: 0.9 },
  { key: 'hz250', freq: 250, type: 'peaking', q: 0.9 },
  { key: 'hz500', freq: 500, type: 'peaking', q: 0.9 },
  { key: 'hz1000', freq: 1000, type: 'peaking', q: 0.9 },
  { key: 'hz2000', freq: 2000, type: 'peaking', q: 0.9 },
  { key: 'hz4000', freq: 4000, type: 'peaking', q: 0.9 },
  { key: 'hz8000', freq: 8000, type: 'peaking', q: 0.9 },
  { key: 'hz16000', freq: 16000, type: 'highshelf', q: 0.7 },
];

const filtersByBand = {};

function getAudioContext() {
  if (!audioContext) {
    audioContext = new (window.AudioContext || window.webkitAudioContext)();
    console.log('[Jemya/EQ] AudioContext created:', audioContext.state);
  }
  return audioContext;
}

function tryResumeContext() {
  const ctx = getAudioContext();
  if (ctx.state === 'suspended') {
    ctx.resume().catch(() => {});
  }
}

function ensureGraph() {
  if (!sourceNode || connected) return;

  const ctx = getAudioContext();
  inputGain = ctx.createGain();
  dryGain = ctx.createGain();
  wetGain = ctx.createGain();

  BAND_DEFS.forEach((band) => {
    const filter = ctx.createBiquadFilter();
    filter.type = band.type;
    filter.frequency.value = band.freq;
    if (band.type === 'peaking') {
      filter.Q.value = band.q;
    }
    filter.gain.value = 0;
    filtersByBand[band.key] = filter;
  });

  sourceNode.connect(inputGain);

  inputGain.connect(dryGain);
  dryGain.connect(ctx.destination);

  let prev = inputGain;
  BAND_DEFS.forEach((band) => {
    const filter = filtersByBand[band.key];
    prev.connect(filter);
    prev = filter;
  });
  prev.connect(wetGain);
  wetGain.connect(ctx.destination);

  connected = true;
  applyBypass();
  console.log('[Jemya/EQ] EQ graph connected');
}

function applyBypass() {
  if (!dryGain || !wetGain || !audioContext) return;
  const t = audioContext.currentTime;
  dryGain.gain.setValueAtTime(eqEnabled ? 0 : 1, t);
  wetGain.gain.setValueAtTime(eqEnabled ? 1 : 0, t);
}

function initWithAudioElement() {
  tryResumeContext();

  const el = document.querySelector('audio');
  if (!el) {
    console.log('[Jemya/EQ] Waiting for audio element');
    return false;
  }

  if (!sourceNode || audioElRef !== el) {
    audioElRef = el;
    sourceNode = getAudioContext().createMediaElementAudioSource(el);
    connected = false;
    console.log('[Jemya/EQ] MediaElementAudioSource created');
  }

  ensureGraph();
  return true;
}

function setBand(band, gainDb) {
  const gain = Math.max(-24, Math.min(24, Number(gainDb)));
  if (!Number.isFinite(gain)) return;
  const filter = filtersByBand[band];
  if (!filter || !audioContext) return;
  filter.gain.setValueAtTime(gain, audioContext.currentTime);
}

function setEnabled(enabled) {
  eqEnabled = !!enabled;
  applyBypass();
  console.log('[Jemya/EQ] Enabled:', eqEnabled);
}

function startInitLoop() {
  if (initWithAudioElement()) return;
  const timer = setInterval(() => {
    if (initWithAudioElement()) {
      clearInterval(timer);
    }
  }, 1000);
}

function bindUserGestureResume() {
  const onGesture = () => tryResumeContext();
  window.addEventListener('click', onGesture, { passive: true });
  window.addEventListener('keydown', onGesture, { passive: true });
}

window.addEventListener('message', (event) => {
  if (event.source !== window) return;
  const msg = event.data;
  if (!msg || typeof msg.type !== 'string' || !msg.type.startsWith('JEMYA_EQ_')) return;

  if (!sourceNode) initWithAudioElement();

  switch (msg.type) {
    case 'JEMYA_EQ_INIT':
      initWithAudioElement();
      break;
    case 'JEMYA_EQ_ENABLE':
      setEnabled(msg.enabled);
      break;
    case 'JEMYA_EQ_SET_BAND':
      setBand(msg.band, msg.gainDb);
      break;
  }
});

bindUserGestureResume();
startInitLoop();

console.log('[Jemya/EQ] Processor loaded');
