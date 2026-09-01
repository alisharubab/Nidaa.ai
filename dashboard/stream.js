// stream.js — SSE client, TTT metrics polling, status cards (FE-11).
// Depends on: tickets.js, drawer.js, filters.js

"use strict";

// CORE_URL is set once in tickets.js (loaded earlier)

// ---------------------------------------------------------------------------
// SSE stream (TRD §3.3 / §3.4)
// ---------------------------------------------------------------------------

function connectStream() {
  const source = new EventSource(`${window.CORE_URL}/api/stream`);

  source.addEventListener("open",  () => setLiveIndicator(true));
  source.addEventListener("error", () => setLiveIndicator(false));

  source.addEventListener("ticket.created", (e) => {
    try { addTicket(JSON.parse(e.data)); } catch { /* ignore */ }
  });

  source.addEventListener("ticket.updated", (e) => {
    try { updateTicket(JSON.parse(e.data)); } catch { /* ignore */ }
  });

  // CORE-15: real-time metrics every 2s over SSE — queue depth is the
  // 2-second signal; median/p95/baseline keep their 5s poll values until
  // the next pollMetrics() write.
  source.addEventListener("metrics", (e) => {
    try { updateTTTWidget(JSON.parse(e.data)); } catch { /* ignore */ }
  });

  // FE-11: only actual failures surface as status cards.
  // message.status lifecycle: received → transcribed → extracted (success),
  // or preflight_failed / audio_unintelligible / failed (failure).
  source.addEventListener("message.status", (e) => {
    try {
      const data = JSON.parse(e.data);
      const failureStatuses = ["preflight_failed", "audio_unintelligible", "failed"];
      if (failureStatuses.includes(data.status)) {
        addStatusCard(data);
      }
    } catch { /* ignore */ }
  });
}

// ---------------------------------------------------------------------------
// Time-to-Triage header widget — the 120° arc speedometer (UI-UX §1.3,
// image-2 redesign). Scale: human baseline at the far left, instant at the
// far right, the 5.0s PRD target ticked on the arc; the median sits as a
// marigold dot that slides as new tickets land. A judge reads "how fast"
// in one glance, no arithmetic. Raw figures stay in mono underneath.
// ---------------------------------------------------------------------------

const _fmt = (ms) =>
  ms == null ? "—" : ms < 1000 ? `${Math.round(ms)}ms` : `${(ms / 1000).toFixed(1)}s`;

// Arc geometry (SVG viewBox 0 0 150 74): 120° sweep from 150° (left, baseline)
// over the top to 30° (right, instant).
const ARC = { cx: 75, cy: 68, r: 62 };

function _arcPoint(f) {
  const theta = ((150 - 120 * f) * Math.PI) / 180;
  return {
    x: +(ARC.cx + ARC.r * Math.cos(theta)).toFixed(2),
    y: +(ARC.cy - ARC.r * Math.sin(theta)).toFixed(2),
  };
}

function _set(id, attrs) {
  const el = document.getElementById(id);
  if (!el) return;
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
}

let _lastFigures = {}; // survive queue-only SSE events between polls

function updateTTTWidget(m) {
  if (!m) return;
  _lastFigures = { ..._lastFigures, ...m };

  const { median_ttt_ms: median, p95_ttt_ms: p95,
          human_baseline_ms: baseline, queue_depth: queue } = _lastFigures;

  // --- arc: fill + median dot + 5s target tick + endpoint labels ---------
  if (baseline > 0) {
    const start = _arcPoint(0);
    if (median != null) {
      const f = Math.max(0, Math.min(1, 1 - median / baseline));
      const dot = _arcPoint(f);
      _set("ttt-arc-fill", {
        d: `M ${start.x} ${start.y} A ${ARC.r} ${ARC.r} 0 0 1 ${dot.x} ${dot.y}`,
      });
      _set("ttt-arc-dot", { cx: dot.x, cy: dot.y });
    }
    // 5.0s PRD target tick (radial, r-6 → r+6)
    const ft = Math.max(0, Math.min(1, 1 - 5000 / baseline));
    const theta = ((150 - 120 * ft) * Math.PI) / 180;
    const tickIn = {
      x: +(ARC.cx + (ARC.r - 6) * Math.cos(theta)).toFixed(2),
      y: +(ARC.cy - (ARC.r - 6) * Math.sin(theta)).toFixed(2),
    };
    const tickOut = {
      x: +(ARC.cx + (ARC.r + 6) * Math.cos(theta)).toFixed(2),
      y: +(ARC.cy - (ARC.r + 6) * Math.sin(theta)).toFixed(2),
    };
    _set("ttt-arc-tick", {
      x1: tickIn.x, y1: tickIn.y, x2: tickOut.x, y2: tickOut.y,
    });
    _set("ttt-arc-label-target", {
      x: +(ARC.cx + (ARC.r + 15) * Math.cos(theta)).toFixed(2),
      y: +(ARC.cy - (ARC.r + 15) * Math.sin(theta)).toFixed(2) + 3,
    });
    const left = document.getElementById("ttt-arc-label-left");
    if (left) left.textContent = _fmt(baseline);
  }

  // --- figures -------------------------------------------------------------
  const big = document.getElementById("ttt-median");
  if (big && median != null) big.textContent = _fmt(median);

  const sub = document.getElementById("ttt-sub");
  if (sub) {
    if (baseline > 0 && median != null && median > 0) {
      sub.textContent =
        `vs ${_fmt(baseline)} human baseline · ${(baseline / median).toFixed(1)}× faster`;
    } else if (baseline > 0) {
      sub.textContent = `vs ${_fmt(baseline)} human baseline`;
    }
  }

  const summary = document.getElementById("ttt-summary");
  if (summary) {
    summary.innerHTML =
      `p95 <strong>${_fmt(p95)}</strong>` +
      (queue != null ? ` · queue <strong>${queue}</strong>` : "");
  }

  // --- KPI modal elements --------------------------------------------------
  const km = document.getElementById("kpi-modal-median");
  if (km && median != null) km.textContent = _fmt(median);

  const ks = document.getElementById("kpi-modal-speedup");
  if (ks && baseline > 0 && median != null && median > 0) {
    ks.textContent = `${(baseline / median).toFixed(1)}× FASTER`;
  }

  const kp95 = document.getElementById("kpi-modal-p95");
  if (kp95) kp95.textContent = _fmt(p95);

  const kq = document.getElementById("kpi-modal-queue");
  if (kq) kq.textContent = queue != null ? queue : "0";
}

function pollMetrics() {
  async function fetch_and_render() {
    try {
      const res = await fetch(`${window.CORE_URL}/api/metrics`);
      if (!res.ok) return;
      updateTTTWidget(await res.json());
    } catch { /* silently ignore if core is down */ }
  }
  fetch_and_render();
  setInterval(fetch_and_render, 5000);
}

// ---------------------------------------------------------------------------
// FE-11: message.status cards
// ---------------------------------------------------------------------------

let _unintelligibleCount = 0;
const _statusCards = new Map();

// TRD §9 error taxonomy — human labels for the error_code carried on
// message.status events (CORE-24 made these specific: STT_REPETITION_LOOP
// vs STT_LOW_CONFIDENCE, RATE_LIMITED on exhausted retries).
const ERROR_LABELS = {
  AUDIO_TOO_SHORT:     "Recording too short",
  AUDIO_TOO_LONG:      "Recording too long",
  AUDIO_SILENT:        "Recording is silent",
  STT_LOW_CONFIDENCE:  "Speech unclear — low STT confidence",
  STT_REPETITION_LOOP: "STT repetition loop — transcript untrustworthy",
  RATE_LIMITED:        "AI provider rate-limited, retries exhausted",
  EXTRACTION_INVALID:  "Extraction returned invalid data",
};

function addStatusCard(data) {
  const stack = document.getElementById("status-stack");
  if (!stack) return;

  const key = data.message_id || data.sender_hash || Date.now();

  // SSE replay (fresh connect replays from seq 0) can redeliver a failure
  // event we already rendered -- replace the existing card instead of
  // stacking a duplicate DOM node under the same map key.
  const existingCard = _statusCards.get(key);
  if (existingCard) existingCard.remove();

  // Track unintelligible count for the queue nav badge (only genuinely
  // new cards -- a replayed event replaces its card and must not re-count)
  if (!existingCard && data.status === "audio_unintelligible") {
    _unintelligibleCount++;
    const el = document.getElementById("count-unintelligible");
    if (el) el.textContent = _unintelligibleCount;
  }

  const cached = messageCache.get(data.message_id) || {};
  const audioPath = data.audio_path || cached.audio_path || null;
  const audioFileName = audioPath ? audioPath.split(/[\/\\]/).pop() : null;

  const audioHtml = audioFileName
    ? `<div class="status-audio-row">
        <audio controls class="status-audio" src="${window.CORE_URL}/audio/${encodeURIComponent(audioFileName)}"></audio>
      </div>`
    : isUnintelligible && data.message_id
      ? `<div class="status-audio-row status-audio-loading" data-msg-id="${data.message_id}">
          <span class="t-caption">Resolving audio...</span>
        </div>`
      : "";

  card.innerHTML = `
    <div class="status-card-icon">${isUnintelligible ? "🔇" : "⚠️"}</div>
    <div class="status-card-body">
      <div class="status-card-header">
        <div class="status-card-title">${title}</div>
        <button class="status-card-dismiss" title="Dismiss" onclick="event.stopPropagation(); _statusCards.get('${key}')?.remove(); _statusCards.delete('${key}');">✕</button>
      </div>
      <div class="status-card-sub">${sub}</div>
      ${audioHtml}
      ${data.error_code && isUnintelligible
        ? `<div class="status-card-code t-mono-sm">${data.error_code}</div>`
        : ""}
    </div>
  `;

  stack.insertBefore(card, stack.firstChild);
  _statusCards.set(key, card);

  // If audio path was missing on the SSE event, try lazy backfill
  if (isUnintelligible && !audioFileName && data.message_id) {
    _backfillStatusAudio(data.message_id, card);
  }
}

async function _backfillStatusAudio(messageId, cardEl) {
  try {
    const res = await fetch(`${window.CORE_URL}/api/tickets`);
    if (!res.ok) return;
    const { tickets: list } = await res.json();
    const match = list.find((t) => t.message_id === messageId && t.audio_path);
    if (!match) return;
    const fileName = match.audio_path.split(/[\/\\]/).pop();
    const row = cardEl.querySelector(".status-audio-loading");
    if (row) {
      row.innerHTML = `<audio controls class="status-audio" src="${window.CORE_URL}/audio/${encodeURIComponent(fileName)}"></audio>`;
      row.className = "status-audio-row";
    }
  } catch { /* ignore */ }
}

// Called by filters.js after any filter change so status cards hide/show
// correctly. Only failure cards are rendered; 'Unhearable' queue shows
// audio_unintelligible cards, everything else shows all failure cards.
function refreshStatusCards(activeQueue) {
  for (const card of _statusCards.values()) {
    const isUnintelligible = card.dataset.status === "audio_unintelligible";
    const show = activeQueue === "all" ||
                 activeQueue === "unintelligible" && isUnintelligible ||
                 activeQueue === "critical"; // failure cards are high-signal, show in critical queue too
    card.style.display = show ? "" : "none";
  }
}
