// player.js — inline voice-note player for ticket cards and the drawer.
// The redesign's "live voice cards": a real, clickable, hearable player
// replacing the old decorative static waveform bars.
//
// Waveform: the audio file is fetched through CORS (core sends
// Access-Control-Allow-Origin: *) and decoded with the Web Audio API, so
// the bars are genuine amplitude peaks of the actual voice note. Playback
// runs on a plain <audio> element (no CORS requirement for playback), so
// sound works even if the peak decode ever fails.
//
// Only one voice plays at a time; clicking the waveform seeks.

"use strict";

const VoicePlayer = (() => {
  let _ctx = null;              // AudioContext, lazily created for decoding
  const _peaks = new Map();     // message_id -> Float32Array (0..1 amplitudes)
  const _decodeFailed = new Set();
  let _active = null;           // currently playing player instance

  const _css = (name, fallback) => {
    const v = getComputedStyle(document.documentElement).getPropertyValue(name);
    return (v && v.trim()) || fallback;
  };

  function _audioCtx() {
    if (!_ctx) _ctx = new (window.AudioContext || window.webkitAudioContext)();
    return _ctx;
  }

  function audioUrl(audioPath) {
    // Absolute Windows paths arrive from core; the static mount serves the
    // bare filename (same normalisation the drawer used).
    return `${window.CORE_URL}/audio/${encodeURIComponent(audioPath.split(/[\/\\]/).pop())}`;
  }

  // Fallback peaks when the CORS decode is unavailable (network blip, decode
  // error). Deterministic per message_id, shaped like a speech envelope.
  // Honest degradation: playback is unaffected — only the bar heights are
  // synthetic, and only when the real ones could not be read.
  function _fallbackPeaks(messageId, n) {
    let seed = ((messageId || 1) * 2654435761) % 4294967296;
    const peaks = new Float32Array(n);
    for (let i = 0; i < n; i++) {
      seed = (seed * 1664525 + 1013904223) % 4294967296;
      const env = Math.sin((Math.PI * (i + 0.5)) / n);
      peaks[i] = 0.18 + 0.75 * (seed / 4294967296) * env;
    }
    return peaks;
  }

  async function _decodePeaks(messageId, url, n) {
    if (_peaks.has(messageId) || _decodeFailed.has(messageId)) return;
    try {
      const res = await fetch(url);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const buf = await res.arrayBuffer();
      const audio = await _audioCtx().decodeAudioData(buf);
      const data = audio.getChannelData(0);
      const block = Math.floor(data.length / n) || 1;
      const peaks = new Float32Array(n);
      let max = 0.0001;
      for (let i = 0; i < n; i++) {
        let m = 0;
        const start = i * block;
        for (let j = start; j < start + block && j < data.length; j += 8) {
          const a = Math.abs(data[j]);
          if (a > m) m = a;
        }
        peaks[i] = m;
        if (m > max) max = m;
      }
      for (let i = 0; i < n; i++) peaks[i] = Math.max(0.08, peaks[i] / max);
      _peaks.set(messageId, peaks);
    } catch {
      _decodeFailed.add(messageId); // don't retry every re-render
    }
  }

  function _fmtTime(s) {
    if (!Number.isFinite(s) || s < 0) return "";
    const m = Math.floor(s / 60);
    const r = Math.floor(s % 60);
    return `${m}:${String(r).padStart(2, "0")}`;
  }

  /**
   * Build a player element for a ticket's voice note.
   * @param {{id:number, message_id:number, audio_duration_s:?number}} ticket
   * @param {string} audioPath absolute path from the messages join
   * @returns {HTMLElement} .voice-player root (callers insert it as-is)
   */
  function create(ticket, audioPath) {
    const url = audioUrl(audioPath);
    const messageId = ticket.message_id ?? ticket.id;
    const duration = ticket.audio_duration_s
      ?? messageCache.get(ticket.message_id)?.audio_duration_s ?? null;

    const root = document.createElement("div");
    root.className = "voice-player";
    root.innerHTML = `
      <button class="vp-btn" type="button" aria-label="Play voice note">
        <svg viewBox="0 0 12 12" width="12" height="12" class="vp-icon-play" aria-hidden="true">
          <path d="M3 1.8v8.4L10 6z" fill="currentColor"/>
        </svg>
        <svg viewBox="0 0 12 12" width="12" height="12" class="vp-icon-pause" aria-hidden="true">
          <rect x="2.5" y="1.8" width="2.6" height="8.4" fill="currentColor"/>
          <rect x="6.9" y="1.8" width="2.6" height="8.4" fill="currentColor"/>
        </svg>
      </button>
      <canvas class="vp-wave" height="36" role="slider"
        aria-label="Voice note waveform — click to seek"></canvas>
      <span class="vp-time"></span>
      <audio preload="metadata" src="${url}"></audio>
    `;

    const btn    = root.querySelector(".vp-btn");
    const canvas = root.querySelector(".vp-wave");
    const timeEl = root.querySelector(".vp-time");
    const audio  = root.querySelector("audio");

    let barCount = 0;
    let playing = false;
    let raf = 0;

    const total = () => (Number.isFinite(audio.duration) && audio.duration > 0)
      ? audio.duration : (duration || 0);
    const elapsed = () => (playing ? audio.currentTime : audio.currentTime) || 0;

    function draw() {
      const dpr = window.devicePixelRatio || 1;
      const w = canvas.clientWidth || 240;
      const h = 36;
      if (canvas.width !== Math.round(w * dpr)) {
        canvas.width = Math.round(w * dpr);
        canvas.height = Math.round(h * dpr);
      }
      const ctx2d = canvas.getContext("2d");
      ctx2d.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx2d.clearRect(0, 0, w, h);

      barCount = Math.max(24, Math.floor(w / 5));
      const peaks = _peaks.get(messageId);
      const barW = 3, gap = (w - barCount * barW) / (barCount - 1);
      const playedColor = _css("--indus", "#0D6E80");
      const idleColor = _css("--bar-idle", "#CBD5E1");
      const frac = total() > 0 ? Math.min(1, elapsed() / total()) : 0;

      for (let i = 0; i < barCount; i++) {
        const v = peaks ? peaks[Math.floor((i / barCount) * peaks.length)] : 0.22;
        const bh = Math.max(3, v * (h - 6));
        ctx2d.fillStyle = (i / barCount) <= frac ? playedColor : idleColor;
        const x = i * (barW + gap);
        ctx2d.beginPath();
        // rounded bar
        const y = (h - bh) / 2, r = Math.min(barW / 2, bh / 2);
        ctx2d.roundRect ? ctx2d.roundRect(x, y, barW, bh, r) : ctx2d.rect(x, y, barW, bh);
        ctx2d.fill();
      }
    }

    function renderTime() {
      const t = total();
      const e = elapsed();
      timeEl.textContent = playing && t
        ? `${_fmtTime(e)} / ${_fmtTime(t)}`
        : (t ? _fmtTime(t) : "—:—");
    }

    function sync() {
      if (!root.isConnected) { // drawer re-render / filter rebuild removed us
        audio.pause();
        playing = false;
        cancelAnimationFrame(raf);
        if (_active === api) _active = null;
        return;
      }
      draw();
      renderTime();
      if (playing) raf = requestAnimationFrame(sync);
    }

    function stopOther() {
      if (_active && _active !== api) _active.pause();
      _active = api;
    }

    async function play() {
      try {
        stopOther();
        await audio.play();
        playing = true;
        root.classList.add("playing");
        sync();
      } catch (err) {
        console.warn("[player] playback failed:", err.message);
      }
    }

    function pause() {
      audio.pause();
      playing = false;
      root.classList.remove("playing");
      sync();
    }

    const api = {
      pause,
      messageId,
      isPlaying: () => playing,
      getTime: () => audio.currentTime,
    };

    // If this exact message was already playing in another instance (e.g. card in feed),
    // seamlessly transfer playback and time position into this drawer player
    if (_active && _active.messageId === messageId && _active.isPlaying()) {
      const prevTime = _active.getTime();
      _active.pause();
      audio.currentTime = prevTime;
      play();
    }

    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      playing ? pause() : play();
    });

    // Click the waveform to seek (real info: position maps to audio time)
    canvas.addEventListener("click", (e) => {
      e.stopPropagation();
      const rect = canvas.getBoundingClientRect();
      const frac = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
      if (total() > 0) {
        audio.currentTime = frac * total();
        if (!playing) play();
        sync();
      }
    });

    audio.addEventListener("loadedmetadata", () => { sync(); });
    audio.addEventListener("ended", () => {
      playing = false;
      audio.currentTime = 0;
      root.classList.remove("playing");
      if (_active === api) _active = null;
      sync();
    });
    audio.addEventListener("error", () => {
      root.classList.add("unavailable");
      btn.disabled = true;
      timeEl.textContent = "unavailable";
      sync();
    });

    // Initial paint (idle bars), then upgrade to real peaks when decoded
    sync();
    _decodePeaks(messageId, url, 96).then(() => { if (root.isConnected) sync(); });

    return root;
  }

  function stopAll() {
    if (_active) {
      _active.pause();
      _active = null;
    }
  }

  return { create, audioUrl, stopAll };
})();
