/**
 * audio-processor.js — Runs in page context on open.spotify.com
 *
 * Creates Web Audio API AudioContext and connects Spotify's audio through
 * a 3-band parametric EQ (Low 125Hz, Mid 1kHz, High 8kHz).
 *
 * Injected by content-bridge.js into the page world to bypass CSP restrictions.
 */

let audioContext = null;
let sourceNode = null;
let eqFilters = null;
let eqEnabled = false;
let gainNodes = {};

class AudioEQ {
  constructor() {
    this.connected = false;
    this.eqBands = {
      low: { freq: 125, gain: 0, q: 0.7 },
      mid: { freq: 1000, gain: 0, q: 0.7 },
      high: { freq: 8000, gain: 0, q: 0.7 },
    };
  }

  init() {
    try {
      // Get or create AudioContext
      if (!audioContext) {
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
        console.log('[Jemya/EQ] 🎵 AudioContext created:', audioContext.state);
      }

      // Find Spotify's audio element
      const audioEl = document.querySelector('audio');
      if (!audioEl) {
        console.warn('[Jemya/EQ] ⚠️ No audio element found');
        setTimeout(() => this.init(), 1000); // Retry
        return;
      }

      // Resume audio context if suspended
      if (audioContext.state === 'suspended') {
        audioContext.resume().then(() => {
          console.log('[Jemya/EQ] ▶️ AudioContext resumed');
        });
      }

      // Create source from audio element (only once)
      if (!sourceNode) {
        sourceNode = audioContext.createMediaElementAudioSource(audioEl);
        console.log('[Jemya/EQ] 🔗 MediaElementAudioSource created');
      }

      // Build EQ filter chain if not already done
      if (!eqFilters) {
        this.buildFilterChain();
      }

      this.connected = true;
      console.log('[Jemya/EQ] ✅ Audio processor initialized');
    } catch (e) {
      console.error('[Jemya/EQ] ❌ Init failed:', e.message);
      setTimeout(() => this.init(), 2000);
    }
  }

  buildFilterChain() {
    if (!audioContext || !sourceNode) return;

    const dst = audioContext.destination;
    gainNodes = {};

    // Create 3 parallel gain nodes for the three EQ bands
    // Source → [Low Band + Mid Band + High Band] → Destination
    // Each band: gain (for 0dB unity) → biquad filter → master gain

    // Low band (125 Hz, peaking)
    gainNodes.lowInput = audioContext.createGain();
    const lowFilter = audioContext.createBiquadFilter();
    lowFilter.type = 'peaking';
    lowFilter.frequency.value = this.eqBands.low.freq;
    lowFilter.Q.value = this.eqBands.low.q;
    lowFilter.gain.value = 0;
    gainNodes.lowGain = audioContext.createGain();
    gainNodes.lowGain.gain.value = 1;

    sourceNode.connect(gainNodes.lowInput);
    gainNodes.lowInput.connect(lowFilter);
    lowFilter.connect(gainNodes.lowGain);
    gainNodes.lowGain.connect(dst);

    // Mid band (1 kHz, peaking)
    gainNodes.midInput = audioContext.createGain();
    const midFilter = audioContext.createBiquadFilter();
    midFilter.type = 'peaking';
    midFilter.frequency.value = this.eqBands.mid.freq;
    midFilter.Q.value = this.eqBands.mid.q;
    midFilter.gain.value = 0;
    gainNodes.midGain = audioContext.createGain();
    gainNodes.midGain.gain.value = 1;

    sourceNode.connect(gainNodes.midInput);
    gainNodes.midInput.connect(midFilter);
    midFilter.connect(gainNodes.midGain);
    gainNodes.midGain.connect(dst);

    // High band (8 kHz, peaking)
    gainNodes.highInput = audioContext.createGain();
    const highFilter = audioContext.createBiquadFilter();
    highFilter.type = 'peaking';
    highFilter.frequency.value = this.eqBands.high.freq;
    highFilter.Q.value = this.eqBands.high.q;
    highFilter.gain.value = 0;
    gainNodes.highGain = audioContext.createGain();
    gainNodes.highGain.gain.value = 1;

    sourceNode.connect(gainNodes.highInput);
    gainNodes.highInput.connect(highFilter);
    highFilter.connect(gainNodes.highGain);
    gainNodes.highGain.connect(dst);

    eqFilters = { lowFilter, midFilter, highFilter };
    console.log('[Jemya/EQ] 🎚️ 3-band EQ filter chain built');
  }

  setBand(band, gainDb) {
    if (!eqFilters || !eqFilters[`${band}Filter`]) {
      console.warn(`[Jemya/EQ] ⚠️ Filter not ready for band: ${band}`);
      return;
    }

    const filter = eqFilters[`${band}Filter`];
    filter.gain.setValueAtTime(gainDb, audioContext.currentTime);
    console.log(`[Jemya/EQ] 🎚️ Set ${band} to ${gainDb} dB`);
  }

  enable(enabled) {
    eqEnabled = enabled;
    if (!sourceNode) return;

    if (enabled && !this.connected) {
      // Rebuild chain if needed
      if (eqFilters) {
        console.log('[Jemya/EQ] ✅ EQ enabled');
      }
    } else if (!enabled && this.connected) {
      console.log('[Jemya/EQ] ❌ EQ disabled');
    }
  }
}

// ── Initialization ────────────────────────────────────────────────────────────

const eq = new AudioEQ();

// Try to initialize when DOM is ready
if (document.body) {
  eq.init();
} else {
  document.addEventListener('DOMContentLoaded', () => eq.init());
}

// Also try on a delay in case rapid init is needed
setTimeout(() => {
  if (!eq.connected) eq.init();
}, 500);

// ── Message handling from content script ──────────────────────────────────────

window.addEventListener('message', (event) => {
  // Only accept messages from ourselves
  if (event.source !== window) return;

  const msg = event.data;
  if (!msg.type || !msg.type.startsWith('JEMYA_EQ_')) return;

  switch (msg.type) {
    case 'JEMYA_EQ_INIT':
      console.log('[Jemya/EQ] Init message received');
      if (!eq.connected) eq.init();
      break;

    case 'JEMYA_EQ_SET_BAND':
      eq.setBand(msg.band, msg.gainDb);
      break;

    case 'JEMYA_EQ_ENABLE':
      eq.enable(msg.enabled);
      break;

    case 'JEMYA_EQ_SET_PRESET':
      console.log('[Jemya/EQ] Preset changed:', msg.preset);
      // Preset values will be set via individual JEMYA_EQ_SET_BAND messages
      break;
  }
});

console.log('[Jemya/EQ] 🎵 Audio processor script loaded and listening');
