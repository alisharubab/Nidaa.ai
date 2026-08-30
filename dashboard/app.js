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
  const stream = document.getElementById("ticket-stream");

  // Remove empty state on first ticket
  const emptyState = document.getElementById("empty-state");
  if (emptyState) emptyState.remove();

  // Insert after the stream header
  const header = stream.querySelector(".stream-header");
  if (header && header.nextSibling) {
    stream.insertBefore(renderTicketCard(ticket), header.nextSibling);
  } else {
    stream.prepend(renderTicketCard(ticket));
  }

  if (typeof renderTicketPin === "function") renderTicketPin(ticket);
  updateCounts();
}

function updateTicket(ticket) {
  const idx = tickets.findIndex((t) => t.id === ticket.id);
  if (idx === -1) return addTicket(ticket);
  tickets[idx] = ticket;
  const stream = document.getElementById("ticket-stream");
  // +1 because the first child is the stream-header
  const existing = stream.children[idx + 1];
  if (existing) existing.replaceWith(renderTicketCard(ticket));
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
  const unlocated = tickets.filter((t) => !t.latitude && !t.longitude).length;
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
  source.addEventListener("open", () => setLiveIndicator(true));
  source.addEventListener("error", () => setLiveIndicator(false));
  source.addEventListener("ticket.created", (e) => addTicket(JSON.parse(e.data)));
  source.addEventListener("ticket.updated", (e) => updateTicket(JSON.parse(e.data)));
  source.addEventListener("message.status", (e) => {
    // TODO(FE-11): surface preflight/unintelligible/failed message states
    // in the UI per docs/UI-UX-REQUIREMENTS.md section 8.
    console.log("message.status", JSON.parse(e.data));
  });
}

// --- Filter chips (TODO FE-05: full logic) --------------------------------

function initFilterChips() {
  const bar = document.getElementById("filter-bar");
  if (!bar) return;
  bar.addEventListener("click", (e) => {
    const chip = e.target.closest(".filter-chip");
    if (!chip) return;
    // Toggle selection (single-select for Day 1; multi-select in FE-05)
    bar.querySelectorAll(".filter-chip").forEach((c) => c.classList.remove("selected"));
    chip.classList.add("selected");
    // TODO(FE-05): actually filter tickets array + re-render stream + map
  });
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
});
