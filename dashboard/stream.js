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

  // CORE-15: real-time queue_depth every 2s — patch just the queue badge,
  // leaving median/p95/baseline written by pollMetrics().
  source.addEventListener("metrics", (e) => {
    try {
      const m = JSON.parse(e.data);
      if (m.queue_depth == null) return;
      const el = document.getElementById("ttt-summary");
      if (!el) return;
      el.querySelectorAll(".ttt-queue").forEach((n) => n.remove());
      const span = document.createElement("span");
      span.className = "ttt-queue";
      span.innerHTML = ` · queue <strong>${m.queue_depth}</strong>`;
      el.appendChild(span);
    } catch { /* ignore */ }
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
// TTT header polling (FE-08) — 5s cycle for median/p95/baseline
// ---------------------------------------------------------------------------

function pollMetrics() {
  async function fetch_and_render() {
    try {
      const res = await fetch(`${window.CORE_URL}/api/metrics`);
      if (!res.ok) return;
      const m = await res.json();

      const fmt = (ms) =>
        ms == null ? "—" : ms < 1000 ? `${Math.round(ms)}ms` : `${(ms / 1000).toFixed(1)}s`;

      const el = document.getElementById("ttt-summary");
      if (!el) return;

      // Preserve the .ttt-queue span written by the SSE handler above
      const existingQueue = el.querySelector(".ttt-queue");
      el.innerHTML =
        `median <strong>${fmt(m.median_ttt_ms)}</strong>` +
        ` · p95 <strong>${fmt(m.p95_ttt_ms)}</strong>` +
        ` · baseline <strong>${fmt(m.human_baseline_ms)}</strong>`;
      if (existingQueue) el.appendChild(existingQueue);
      else if (m.queue_depth != null) {
        const span = document.createElement("span");
        span.className = "ttt-queue";
        span.innerHTML = ` · queue <strong>${m.queue_depth}</strong>`;
        el.appendChild(span);
      }
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

function addStatusCard(data) {
  const stack = document.getElementById("status-stack");
  if (!stack) return;

  // Track unintelligible count for the queue nav badge
  if (data.status === "audio_unintelligible") {
    _unintelligibleCount++;
    const el = document.getElementById("count-unintelligible");
    if (el) el.textContent = _unintelligibleCount;
  }

  const card = document.createElement("div");
  card.className = "status-card";
  const key = data.message_id || data.sender_hash || Date.now();
  card.dataset.msgId = key;
  card.dataset.status = data.status || "";

  const isUnintelligible = data.status === "audio_unintelligible";
  card.innerHTML = `
    <div class="status-card-icon">${isUnintelligible ? "🔇" : "⚠️"}</div>
    <div class="status-card-body">
      <div class="status-card-title">
        ${isUnintelligible ? "Audio Unintelligible" : "Message Failed"}
      </div>
      <div class="status-card-sub">
        ${isUnintelligible
          ? "Nidaa could not hear this. Listen yourself."
          : data.reason || data.status || "Processing failed"}
      </div>
    </div>
  `;

  stack.insertBefore(card, stack.firstChild);
  _statusCards.set(key, card);
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
