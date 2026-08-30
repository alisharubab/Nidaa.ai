// SSE client, ticket stream rendering, filters. docs/TRD.md sections 3.3/3.4,
// docs/UI-UX-REQUIREMENTS.md sections 6.1-6.3.

const CORE_URL = window.NIDAA_CORE_URL || "http://127.0.0.1:8000";

let tickets = []; // in-memory array, filtered client-side (docs/TRD.md section 7)

// --- Urgency helpers (UI-UX §2.2) ------------------------------------------

const URGENCY_LABELS = {
  critical: "Critical", high: "High", moderate: "Moderate", info: "Info",
};

const URGENCY_ORDER = ["critical", "high", "moderate", "info"];

function verificationState(ticket) {
  // verification_status (sender 1/2 reply) and dispatcher_verdict
  // (Acknowledge/Flag) are two independent columns as of the schema fix
  // in docs/TRD.md section 2 -- there is no "dispatcher_verified" value
  // in verification_status any more. See PROGRESS.md CORE-02 notes.
  if (ticket.verification_status === "user_confirmed" ||
      ticket.dispatcher_verdict === "verified") return "confirmed";
  if (ticket.verification_status === "user_disputed") return "disputed";
  return "unconfirmed";
}

function formatTime(iso) {
  if (!iso) return "";
  try { return new Date(iso).toLocaleTimeString("en-GB", { hour12: false }); }
  catch { return ""; }
}

function parseItems(itemsJson) {
  if (!itemsJson) return [];
  try { return typeof itemsJson === "string" ? JSON.parse(itemsJson) : itemsJson; }
  catch { return []; }
}

function itemsSummary(items) {
  if (!items || items.length === 0) return "";
  return items.map((i) => {
    const qty = i.qty ? `${i.qty} ${i.unit || ""} `.trim() + " " : "";
    return qty + i.item;
  }).join(", ");
}

// Waveform placeholder bars (full Confidence Waveform in FE-07)
function waveformBars() {
  // Generate pseudo-random bar heights for the placeholder
  const heights = [6, 14, 20, 16, 10, 6, 4, 12, 18, 14, 8, 4];
  return heights.map((h) =>
    `<span class="waveform-bar" style="height:${h}px;opacity:0.45"></span>`
  ).join("");
}

// --- Ticket card (UI-UX §6.2) ---------------------------------------------

function renderTicketCard(ticket) {
  const urgency = ticket.urgency || "info";
  const state = verificationState(ticket);
  const items = parseItems(ticket.items_json);
  const summary = itemsSummary(items);
  const pcode = ticket.pcode || "";
  const time = formatTime(ticket.created_at);
  const duration = ticket.audio_duration_s
    ? `${Math.round(ticket.audio_duration_s)}s`
    : "";

  const card = document.createElement("div");
  card.className = `ticket-card urgency-${urgency}`;
  card.setAttribute("tabindex", "0");
  card.setAttribute("role", "button");
  card.setAttribute("aria-label",
    `${URGENCY_LABELS[urgency]} ticket, ${ticket.adm2_name || "Unlocated"}, ${state}`);
  card.dataset.ticketId = ticket.id;

  card.innerHTML = `
    <div class="ticket-body">
      <div class="ticket-top">
        <span class="ticket-urgency-badge">${URGENCY_LABELS[urgency]}</span>
        <span class="ticket-time">${time}</span>
      </div>
      <div class="ticket-location">
        <span class="ticket-district">${ticket.adm2_name || "Unlocated"}${ticket.adm1_name ? ", " + ticket.adm1_name : ""}</span>
        ${pcode ? `<span class="ticket-pcode">${pcode}</span>` : ""}
      </div>
      ${summary ? `<div class="ticket-summary">${summary}</div>` : ""}
      <div class="ticket-waveform">
        ${waveformBars()}
        ${duration ? `<span class="waveform-duration">${duration}</span>` : ""}
      </div>
      <div class="ticket-footer">
        <span class="state-dot ${state}">${state === "confirmed" ? "Confirmed" : state === "disputed" ? "Disputed" : "Unconfirmed"}</span>
        <button class="btn-ack" onclick="event.stopPropagation(); acknowledgeTicket(${ticket.id})">Acknowledge</button>
      </div>
    </div>
  `;

  // Click opens the detail drawer (TODO FE-07)
  card.addEventListener("click", () => {
    console.log("TODO(FE-07): open detail drawer for ticket", ticket.id);
  });

  return card;
}

// --- Stream management ----------------------------------------------------

function addTicket(ticket) {
  tickets.unshift(ticket);
  const emptyState = document.getElementById("empty-state");
  if (emptyState) emptyState.remove();
  // applyFilters() calls refreshPins(visible) which redraws all pins;
  // no need to call renderTicketPin(ticket) separately here.
  applyFilters();
  updateCounts();
}

function updateTicket(ticket) {
  const idx = tickets.findIndex((t) => t.id === ticket.id);
  if (idx === -1) return addTicket(ticket);
  tickets[idx] = ticket;
  applyFilters();  // re-renders stream + pins respecting active filters
  updateCounts();
}

function setLiveIndicator(isLive) {
  const dot = document.getElementById("live-dot");
  const text = document.getElementById("live-text");
  if (dot) dot.className = isLive ? "live-dot" : "live-dot offline";
  if (text) text.textContent = isLive ? "live" : "reconnecting";
}

// --- Queue counts (left rail) ---------------------------------------------

function updateCounts() {
  const total = tickets.length;
  const critical = tickets.filter((t) => t.urgency === "critical").length;
  const unlocated = tickets.filter((t) => t.latitude == null || t.longitude == null).length;
  const disputed = tickets.filter((t) => t.verification_status === "user_disputed").length;

  const setCount = (id, n) => {
    const el = document.getElementById(id);
    if (el) el.textContent = n;
  };

  setCount("count-all", total);
  setCount("count-critical", critical);
  setCount("count-unlocated", unlocated);
  setCount("count-unintelligible", 0); // TODO: wire from message.status events
  setCount("count-disputed", disputed);

  const streamCount = document.getElementById("stream-count");
  if (streamCount) streamCount.textContent = `${total} ticket${total !== 1 ? "s" : ""}`;
}

// --- Acknowledge (verdict) ------------------------------------------------

async function acknowledgeTicket(id) {
  try {
    const res = await fetch(`${CORE_URL}/api/tickets/${id}/verdict`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ verdict: "verified" }),
    });
    if (res.ok) {
      console.log(`Ticket ${id} acknowledged`);
      // TODO(FE-07): show toast notification per UI-UX §6.9
    }
  } catch (err) {
    console.error("Acknowledge failed:", err);
  }
}

// --- HXL Export ------------------------------------------------------------

function exportHXL() {
  window.open(`${CORE_URL}/api/export/hxl.csv`, "_blank");
}

// --- SSE client (docs/TRD.md 3.3/3.4) ------------------------------------

function connectStream() {
  const source = new EventSource(`${CORE_URL}/api/stream`);
  source.addEventListener("open",   () => setLiveIndicator(true));
  source.addEventListener("error",  () => setLiveIndicator(false));
  source.addEventListener("ticket.created",  (e) => addTicket(JSON.parse(e.data)));
  source.addEventListener("ticket.updated",  (e) => updateTicket(JSON.parse(e.data)));
  source.addEventListener("metrics", (e) => {
    // Real-time queue_depth from CORE-15's 2s SSE broadcast — faster than
    // the 5s pollMetrics() HTTP poll. Only update queue_depth here; the
    // full metrics row (median/p95/baseline) still comes from pollMetrics().
    try {
      const m = JSON.parse(e.data);
      if (m.queue_depth != null) {
        const el = document.getElementById("ttt-summary");
        if (el) {
          // Patch just the queue badge without touching the rest of the line
          el.querySelectorAll(".ttt-queue").forEach((n) => n.remove());
          const span = document.createElement("span");
          span.className = "ttt-queue";
          span.innerHTML = ` · queue <strong>${m.queue_depth}</strong>`;
          el.appendChild(span);
        }
      }
    } catch { /* ignore malformed event */ }
  });
  source.addEventListener("message.status", (e) => {
    // TODO(FE-11): surface preflight/unintelligible/failed message states
    // in the UI per docs/UI-UX-REQUIREMENTS.md section 8.
    console.log("message.status", JSON.parse(e.data));
  });
}

// --- TTT header (FE-08) --------------------------------------------------

/**
 * Poll GET /api/metrics every 5s and update the TTT header display.
 * Metrics shape (TRD §3.3): { median_ttt_ms, p95_ttt_ms, human_baseline_ms,
 *   queue_depth, ... }
 */
function pollMetrics() {
  async function fetch_and_render() {
    try {
      const res = await fetch(`${CORE_URL}/api/metrics`);
      if (!res.ok) return;
      const m = await res.json();

      const fmt = (ms) =>
        ms == null ? "—" : ms < 1000 ? `${Math.round(ms)}ms` : `${(ms / 1000).toFixed(1)}s`;

      const el = document.getElementById("ttt-summary");
      if (el) {
        // Write median/p95/baseline; queue_depth is patched live by the
        // SSE metrics event handler (connectStream) every 2s — don't
        // overwrite it here, just preserve any existing .ttt-queue span.
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
      }
    } catch { /* silently ignore if core is down */ }
  }

  fetch_and_render();
  setInterval(fetch_and_render, 5000);
}

// --- Filter chips (FE-05) -----------------------------------------------

// Active filter state. urgency is one of: all|critical|high|moderate|info
// queue is one of: all|critical|unlocated|unintelligible|disputed
// Both can be active simultaneously; the stream shows the intersection.
let activeUrgency = "all";
let activeQueue   = "all";

/** Return true if ticket passes the current active filters. */
function ticketMatchesFilter(ticket) {
  // Queue filter (left rail)
  if (activeQueue !== "all") {
    if (activeQueue === "critical"       && ticket.urgency !== "critical") return false;
    if (activeQueue === "unlocated"      && !(ticket.latitude == null || ticket.longitude == null)) return false;
    if (activeQueue === "unintelligible" && ticket.error_code !== "STT_LOW_CONFIDENCE") return false;
    if (activeQueue === "disputed"       && ticket.verification_status !== "user_disputed") return false;
  }
  // Urgency chip filter (map overlay bar)
  if (activeUrgency !== "all" && ticket.urgency !== activeUrgency) return false;
  return true;
}

/** Re-render the ticket stream and map pins to match current filters. */
function applyFilters() {
  const stream = document.getElementById("ticket-stream");

  // Remove all cards (leave the stream-header)
  const header = stream.querySelector(".stream-header");
  stream.innerHTML = "";
  if (header) stream.appendChild(header);

  const visible = tickets.filter(ticketMatchesFilter);

  if (visible.length === 0) {
    const empty = document.createElement("div");
    empty.className = "filter-empty";
    empty.textContent = "No tickets match this filter.";
    stream.appendChild(empty);
  } else {
    visible.forEach((t) => stream.appendChild(renderTicketCard(t)));
  }

  // Re-draw map pins for visible tickets only
  if (typeof refreshPins === "function") refreshPins(visible);

  // Update chip counts
  updateChipCounts();
}

/** Update the count badges on each urgency chip. */
function updateChipCounts() {
  const bar = document.getElementById("filter-bar");
  if (!bar) return;
  const counts = { all: tickets.length, critical: 0, high: 0, moderate: 0, info: 0 };
  tickets.forEach((t) => {
    if (counts[t.urgency] !== undefined) counts[t.urgency]++;
  });
  bar.querySelectorAll(".filter-chip").forEach((chip) => {
    const u = chip.dataset.urgency;
    let badge = chip.querySelector(".chip-count");
    if (!badge) {
      badge = document.createElement("span");
      badge.className = "chip-count";
      chip.appendChild(badge);
    }
    badge.textContent = counts[u] ?? "";
  });
}

function initFilterChips() {
  // Map filter bar chips (urgency)
  const bar = document.getElementById("filter-bar");
  if (bar) {
    bar.addEventListener("click", (e) => {
      const chip = e.target.closest(".filter-chip");
      if (!chip) return;
      bar.querySelectorAll(".filter-chip").forEach((c) => c.classList.remove("selected"));
      chip.classList.add("selected");
      activeUrgency = chip.dataset.urgency || "all";
      applyFilters();
    });
  }

  // Left rail queue nav
  const queueList = document.getElementById("queue-list");
  if (queueList) {
    queueList.addEventListener("click", (e) => {
      const btn = e.target.closest(".queue-item");
      if (!btn) return;
      queueList.querySelectorAll(".queue-item").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      activeQueue = btn.dataset.filter || "all";
      applyFilters();
    });
  }
}

// --- Presentation mode (UI-UX §10) ---------------------------------------

function checkPresentMode() {
  if (new URLSearchParams(window.location.search).get("present") === "true") {
    document.body.classList.add("present-mode");
  }
}

// --- Boot -----------------------------------------------------------------

document.addEventListener("DOMContentLoaded", () => {
  checkPresentMode();
  initFilterChips();
  connectStream();
  pollMetrics();
});
