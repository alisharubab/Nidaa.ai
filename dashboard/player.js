// player.js — inline voice-note player for ticket cards and the drawer.
// The redesign's "live voice cards": a real, clickable, hearable player
// replacing the old decorative static waveform bars.
//
// Single persistent Audio engine: opening/closing drawer or scrolling never
// stops, restarts, or interrupts playback. All active waveform instances for
// the same messageId stay synchronized in real time.

"use strict";

const VoicePlayer = (() => {
  let _ctx = null;              // AudioContext, lazily created for decoding
  const _peaks = new Map();     // message_id -> Float32Array (0..1 amplitudes)
  const _decodeFailed = new Set();

  // Single shared audio engine
  const _audio = new Audio();
  let _currentMsgId = null;
  const _listeners = new Set(); // active UI sync callbacks

  const _css = (name, fallback) => {
    const v = getComputedStyle(document.documentElement).getPropertyValue(name);
    return (v && v.trim()) || fallback;
  };

  function _audioCtx() {
    if (!_ctx) _ctx = new (window.AudioContext || window.webkitAudioContext)();
    return _ctx;
  }

  function audioUrl(audioPath) {
    return `${window.CORE_URL}/audio/${encodeURIComponent(audioPath.split(/[\/\\]/).pop())}`;
  }

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
      _notifyAll();
    } catch {
      _decodeFailed.add(messageId);
    }
  }

  function _fmtTime(s) {
    if (!Number.isFinite(s) || s < 0) return "";
    const m = Math.floor(s / 60);
    const r = Math.floor(s % 60);
    return `${m}:${String(r).padStart(2, "0")}`;
  }

  let _rafId = null;

  function _notifyAll() {
    for (const fn of _listeners) fn();
  }

  function _onTick() {
    _notifyAll();
    if (!_audio.paused && !Number.isNaN(_audio.duration)) {
      _rafId = requestAnimationFrame(_onTick);
    } else {
      _rafId = null;
    }
  }

  function _startLoop() {
    if (!_rafId) _rafId = requestAnimationFrame(_onTick);
  }

  _audio.addEventListener("play", () => {
    _startLoop();
    _notifyAll();
  });
  _audio.addEventListener("pause", () => {
    if (_rafId) { cancelAnimationFrame(_rafId); _rafId = null; }
    _notifyAll();
  });
  _audio.addEventListener("ended", () => {
    if (_rafId) { cancelAnimationFrame(_rafId); _rafId = null; }
    _currentMsgId = null;
    _notifyAll();
  });
  _audio.addEventListener("timeupdate", _notifyAll);
  _audio.addEventListener("loadedmetadata", _notifyAll);

  /**
   * Build a player element for a ticket's voice note.
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
    `;

    const btn    = root.querySelector(".vp-btn");
    const canvas = root.querySelector(".vp-wave");
    const timeEl = root.querySelector(".vp-time");

    const isThisPlaying = () => _currentMsgId === messageId && !_audio.paused;

    const total = () => {
      if (_currentMsgId === messageId && Number.isFinite(_audio.duration) && _audio.duration > 0) {
        return _audio.duration;
      }
      return duration || 0;
    };

    const elapsed = () => (_currentMsgId === messageId ? _audio.currentTime : 0);

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

      const barCount = Math.max(24, Math.floor(w / 5));
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
        const y = (h - bh) / 2, r = Math.min(barW / 2, bh / 2);
        ctx2d.roundRect ? ctx2d.roundRect(x, y, barW, bh, r) : ctx2d.rect(x, y, barW, bh);
        ctx2d.fill();
      }
    }

    function renderTime() {
      const t = total();
      const e = elapsed();
      const playing = isThisPlaying();
      timeEl.textContent = playing && t
        ? `${_fmtTime(e)} / ${_fmtTime(t)}`
        : (t ? _fmtTime(t) : "—:—");
    }

    function sync() {
      if (!root.isConnected) {
        _listeners.delete(sync);
        return;
      }
      const playing = isThisPlaying();
      root.classList.toggle("playing", playing);
      draw();
      renderTime();
    }

    _listeners.add(sync);

    async function togglePlay() {
      if (isThisPlaying()) {
        _audio.pause();
      } else {
        if (_currentMsgId !== messageId) {
          _audio.src = url;
          _currentMsgId = messageId;
          _audio.currentTime = 0;
        }
        try {
          await _audio.play();
        } catch (err) {
          console.warn("[player] playback failed:", err.message);
        }
      }
      _notifyAll();
    }

    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      togglePlay();
    });

    // Click waveform to seek
    canvas.addEventListener("click", (e) => {
      e.stopPropagation();
      const rect = canvas.getBoundingClientRect();
      const frac = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
      const dur = total();
      if (dur > 0) {
        if (_currentMsgId !== messageId) {
          _audio.src = url;
          _currentMsgId = messageId;
        }
        _audio.currentTime = frac * dur;
        if (_audio.paused) {
          _audio.play().catch(() => {});
        }
        _notifyAll();
      }
    });

    // Initial paint and async peak decoding
    sync();
    _decodePeaks(messageId, url, 96).then(() => { if (root.isConnected) sync(); });

    return root;
  }

  function stopAll() {
    _audio.pause();
    _currentMsgId = null;
    _notifyAll();
  }

  return { create, audioUrl, stopAll };
})();
