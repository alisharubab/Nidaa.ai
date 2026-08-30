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

  // Click opens the detail drawer (FE-07)
  card.addEventListener("click", () => openDrawer(ticket));

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
  applyFilters();
  updateCounts();
  // FE-09: update pin style in-place without a full map redraw
  if (typeof updatePin === "function") updatePin(ticket);
  // FE-07: if the drawer is open on this ticket, refresh it
  if (typeof refreshDrawer === "function") refreshDrawer(ticket);
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
    // FE-11: surface preflight/unintelligible/failed message states in stream
    try { addStatusCard(JSON.parse(e.data)); } catch { /* ignore malformed */ }
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

// --- FE-07: Detail Drawer -------------------------------------------------
// Spec: UI-UX-REQUIREMENTS.md §6.5
// 520px wide, paper background, --r-xl on left corners, --e-3, full height.
// Contents: audio player, confidence waveform, transcript, entity list,
// confidence bar + geocode badge, verdict buttons.

let _drawerTicket = null;

function openDrawer(ticket) {
  _drawerTicket = ticket;
  const scrim = document.getElementById("drawer-scrim");
  const drawer = document.getElementById("detail-drawer");
  if (!scrim || !drawer) return;

  _renderDrawerContent(ticket);

  scrim.classList.add("open");
  drawer.classList.add("open");
  drawer.focus();
}

function closeDrawer() {
  _drawerTicket = null;
  const scrim = document.getElementById("drawer-scrim");
  const drawer = document.getElementById("detail-drawer");
  if (scrim) scrim.classList.remove("open");
  if (drawer) drawer.classList.remove("open");
}

// Called by updateTicket() to keep an open drawer in sync
function refreshDrawer(ticket) {
  if (!_drawerTicket || _drawerTicket.id !== ticket.id) return;
  _drawerTicket = ticket;
  _renderDrawerContent(ticket);
}

function _renderDrawerContent(ticket) {
  const drawer = document.getElementById("detail-drawer");
  if (!drawer) return;

  const urgency  = ticket.urgency || "info";
  const state    = verificationState(ticket);
  const items    = parseItems(ticket.items_json);
  const missing  = (() => { try { return JSON.parse(ticket.missing_fields || "[]"); } catch { return []; } })();

  // Audio player — only rendered if modality = audio
  const audioSection = ticket.audio_path
    ? `<div class="drawer-section">
        <div class="drawer-section-label">Audio</div>
        <audio controls src="${CORE_URL}/audio/${encodeURIComponent(ticket.audio_path.split(/[\/\\]/).pop())}" class="drawer-audio"></audio>
        ${ticket.audio_duration_s ? `<span class="drawer-audio-dur t-mono">${Math.round(ticket.audio_duration_s)}s voice note</span>` : ""}
      </div>`
    : "";

  // Confidence waveform — bar heights proportional to extraction_conf
  const conf  = ticket.extraction_conf ?? 0;
  const bars  = [0.4, 0.7, 1.0, 0.9, 0.6, 0.8, 1.0, 0.7, 0.5, 0.8, 0.9, 0.6,
                 0.4, 0.75, 1.0, 0.85, 0.5, 0.7, 0.95, 0.6]
                .map((h) => Math.round(h * conf * 48));
  const waveHtml = bars.map((h) =>
    `<span class="drawer-wave-bar" style="height:${Math.max(4, h)}px"></span>`
  ).join("");

  // Transcript row
  const transcriptSection = ticket.transcript
    ? `<div class="drawer-section">
        <div class="drawer-section-label">Transcript</div>
        <div class="urdu-text drawer-transcript">${ticket.transcript}</div>
      </div>`
    : "";

  // Extracted fields
  const fieldsHtml = [
    ["Location",   ticket.adm2_name ? `${ticket.adm2_name}, ${ticket.adm1_name || ""}` : `<span class='drawer-missing'>missing</span>`],
    ["P-code",     ticket.pcode     || `<span class='drawer-missing'>—</span>`],
    ["Intent",     ticket.intent    || "—"],
    ["Urgency",    URGENCY_LABELS[urgency] || urgency],
    ["Needs",      items.length ? itemsSummary(items) : `<span class='drawer-missing'>none extracted</span>`],
    ["Affected",   ticket.people_affected > 0 ? ticket.people_affected : `<span class='drawer-missing'>unknown</span>`],
    ["Casualties", ticket.casualties > 0 ? ticket.casualties : `<span class='drawer-missing'>none reported</span>`],
    ["Geocode",    ticket.geocode_method || "none"],
    ["Conf",       `${Math.round(conf * 100)}%`],
  ].map(([k, v]) =>
    `<div class="drawer-field"><span class="drawer-field-key">${k}</span><span class="drawer-field-val">${v}</span></div>`
  ).join("");

  const missingBadges = missing.length
    ? `<div class="drawer-missing-row">${missing.map((f) => `<span class="drawer-missing-badge">${f}</span>`).join("")}</div>`
    : "";

  const reasoningSection = ticket.reasoning_note
    ? `<div class="drawer-section">
        <div class="drawer-section-label">AI Reasoning</div>
        <div class="drawer-reasoning">${ticket.reasoning_note}</div>
      </div>`
    : "";

  drawer.innerHTML = `
    <div class="drawer-header">
      <span class="ticket-urgency-badge urgency-${urgency}" style="align-self:flex-start">${URGENCY_LABELS[urgency]}</span>
      <span class="t-title drawer-title">${ticket.adm2_name || "Unlocated"}${ticket.adm1_name ? ", " + ticket.adm1_name : ""}</span>
      <button class="drawer-close" aria-label="Close drawer" onclick="closeDrawer()">×</button>
    </div>
    <div class="drawer-body">
      ${audioSection}
      <div class="drawer-section">
        <div class="drawer-section-label">Confidence waveform</div>
        <div class="drawer-waveform">${waveHtml}</div>
        <div class="drawer-conf-bar"><div class="drawer-conf-fill" style="width:${Math.round(conf * 100)}%"></div></div>
        <div class="drawer-conf-label t-mono-sm">${Math.round(conf * 100)}% extraction confidence · geocode: ${ticket.geocode_method || "none"}</div>
      </div>
      ${transcriptSection}
      <div class="drawer-section">
        <div class="drawer-section-label">Extracted fields</div>
        <div class="drawer-fields">${fieldsHtml}</div>
        ${missingBadges}
      </div>
      ${reasoningSection}
    </div>
    <div class="drawer-footer">
      <span class="state-dot ${state}">${state === "confirmed" ? "Confirmed" : state === "disputed" ? "Disputed" : "Unconfirmed"}</span>
      <div class="drawer-actions">
        <button class="btn-flag" onclick="flagTicket(${ticket.id})" ${state === "disputed" ? "disabled" : ""}>Flag</button>
        <button class="btn-ack" onclick="event.stopPropagation(); acknowledgeTicket(${ticket.id})" ${state === "confirmed" ? "disabled" : ""}>Acknowledge</button>
      </div>
    </div>
  `;
}

async function flagTicket(id) {
  try {
    const res = await fetch(`${CORE_URL}/api/tickets/${id}/verdict`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ verdict: "disputed" }),
    });
    if (res.ok) console.log(`Ticket ${id} flagged`);
  } catch (err) { console.error("Flag failed:", err); }
}

// --- FE-11: message.status cards in stream --------------------------------
// Surfaces AUDIO_UNINTELLIGIBLE and preflight fail events as non-ticket cards.

const statusCards = new Map(); // messageId → card element

function addStatusCard(data) {
  const stream = document.getElementById("ticket-stream");
  if (!stream) return;
  const emptyState = document.getElementById("empty-state");
  if (emptyState) emptyState.remove();

  const card = document.createElement("div");
  card.className = "status-card";
  card.dataset.msgId = data.message_id || data.sender_hash || Date.now();

  const isUnintelligible = data.status === "audio_unintelligible";
  card.innerHTML = `
    <div class="status-card-icon">${isUnintelligible ? "🔇" : "⚠️"}</div>
    <div class="status-card-body">
      <div class="status-card-title">${isUnintelligible ? "Audio Unintelligible" : "Message Failed"}</div>
      <div class="status-card-sub">${isUnintelligible
        ? "Nidaa could not hear this. Listen yourself."
        : data.reason || data.status || "Processing failed"}</div>
    </div>
  `;

  // Insert below stream-header
  const header = stream.querySelector(".stream-header");
  if (header && header.nextSibling) {
    stream.insertBefore(card, header.nextSibling);
  } else {
    stream.appendChild(card);
  }
  statusCards.set(card.dataset.msgId, card);
}

// --- Boot -----------------------------------------------------------------

document.addEventListener("DOMContentLoaded", () => {
  checkPresentMode();
  initFilterChips();
  connectStream();
  pollMetrics();

  // Keyboard: Esc closes drawer; A acknowledges focused/open ticket (UI-UX §9.3)
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeDrawer();
    if (e.key === "a" || e.key === "A") {
      if (_drawerTicket) acknowledgeTicket(_drawerTicket.id);
    }
  });

  // Scrim click closes drawer
  const scrim = document.getElementById("drawer-scrim");
  if (scrim) scrim.addEventListener("click", closeDrawer);
});
