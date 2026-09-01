// tickets.js — ticket data store, card rendering, stream management.
// Imported by app.js (boot). No dependencies on drawer.js or filters.js.
// docs/UI-UX-REQUIREMENTS.md §6.2

"use strict";

// Global config (loaded before other scripts)
window.CORE_URL = window.NIDAA_CORE_URL || "http://127.0.0.1:8000";

// ---------------------------------------------------------------------------
// Data store
// ---------------------------------------------------------------------------

const tickets = [];          // ordered newest-first, client-side (TRD §7)
const messageCache = new Map(); // message_id → { modality, audio_path, raw_text }

// ---------------------------------------------------------------------------
// Urgency helpers
// ---------------------------------------------------------------------------

const URGENCY_LABELS = {
  critical: "Critical", high: "High", moderate: "Moderate", info: "Info",
};

const URGENCY_ORDER = ["critical", "high", "moderate", "info"];

function verificationState(ticket) {
  // Two independent columns: verification_status (sender reply) and
  // dispatcher_verdict (Acknowledge/Flag). See PROGRESS.md CORE-02.
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
    const qty = i.qty ? `${i.qty} ${i.unit || ""}`.trim() + " " : "";
    return qty + i.item;
  }).join(", ");
}

// Waveform placeholder bars shown on cards
function waveformBars() {
  const heights = [6, 14, 20, 16, 10, 6, 4, 12, 18, 14, 8, 4];
  return heights.map((h) =>
    `<span class="waveform-bar" style="height:${h}px;opacity:0.45"></span>`
  ).join("");
}

// ---------------------------------------------------------------------------
// Card renderer (UI-UX §6.2)
// ---------------------------------------------------------------------------

function renderTicketCard(ticket) {
  const urgency  = ticket.urgency || "info";
  const state    = verificationState(ticket);
  const items    = parseItems(ticket.items_json);
  const summary  = itemsSummary(items);
  const pcode    = ticket.pcode || "";
  const time     = formatTime(ticket.created_at);
  const modality = messageCache.get(ticket.message_id)?.modality || ticket.modality || null;
  const duration = ticket.audio_duration_s
    ? `${Math.round(ticket.audio_duration_s)}s`
    : messageCache.get(ticket.message_id)?.audio_duration_s
      ? `${Math.round(messageCache.get(ticket.message_id).audio_duration_s)}s`
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
        ${modality === "audio" ? waveformBars() : ""}
        ${duration ? `<span class="waveform-duration">${duration}</span>` : ""}
      </div>
      <div class="ticket-footer">
        <span class="state-dot ${state}">${state === "confirmed" ? "Confirmed" : state === "disputed" ? "Disputed" : "Unconfirmed"}</span>
        <button class="btn-ack" onclick="event.stopPropagation(); acknowledgeTicket(${ticket.id})">Acknowledge</button>
      </div>
    </div>
  `;

  // Click → drawer
  card.addEventListener("click", () => openDrawer(ticket));

  // Hover ↔ pin bidirectional highlight (UI-UX §6.3)
  card.addEventListener("mouseenter", () => {
    if (typeof highlightPin === "function") highlightPin(ticket.id, true);
  });
  card.addEventListener("mouseleave", () => {
    if (typeof highlightPin === "function") highlightPin(ticket.id, false);
  });

  return card;
}

// ---------------------------------------------------------------------------
// Stream management
// ---------------------------------------------------------------------------

function addTicket(ticket) {
  // SSE replay is not deduplicated server-side: a fresh connection
  // replays every event from seq 0 (main.py stream endpoint), and a
  // reconnect replays from Last-Event-ID -- so ticket.created can arrive
  // for a ticket we already hold (REST backfill or an earlier live event).
  // The created payload is the OLDEST state for that id, so a duplicate
  // must never be inserted; updateTicket() applies the newer states in
  // seq order and converges to current.
  if (tickets.some((t) => t.id === ticket.id)) return;
  tickets.unshift(ticket);
  document.querySelector("#ticket-list #empty-state")?.remove();
  // Cache any message metadata that happens to be on the ticket object
  // (Person A may add modality/audio_path/raw_text to the join later).
  if (ticket.message_id && (ticket.modality || ticket.audio_path || ticket.raw_text || ticket.audio_duration_s)) {
    messageCache.set(ticket.message_id, {
      modality:          ticket.modality,
      audio_path:        ticket.audio_path,
      audio_duration_s:  ticket.audio_duration_s,
      raw_text:          ticket.raw_text,
    });
  }
  applyFilters();
  updateCounts();
}

function updateTicket(ticket) {
  const idx = tickets.findIndex((t) => t.id === ticket.id);
  if (idx === -1) return addTicket(ticket);
  tickets[idx] = ticket;
  applyFilters();
  updateCounts();
  // applyFilters() already calls refreshPins(visible); updatePin is redundant
  if (typeof refreshDrawer === "function") refreshDrawer(ticket);
}

function setLiveIndicator(isLive) {
  const dot  = document.getElementById("live-dot");
  const text = document.getElementById("live-text");
  if (dot)  dot.className  = isLive ? "live-dot" : "live-dot offline";
  if (text) text.textContent = isLive ? "live" : "reconnecting";
}

// ---------------------------------------------------------------------------
// Queue counts (left rail)
// ---------------------------------------------------------------------------

function updateCounts() {
  const total     = tickets.length;
  const critical  = tickets.filter((t) => t.urgency === "critical").length;
  const unlocated = tickets.filter((t) => t.latitude == null || t.longitude == null).length;
  const disputed  = tickets.filter((t) => t.verification_status === "user_disputed").length;

  const set = (id, n) => { const el = document.getElementById(id); if (el) el.textContent = n; };
  set("count-all",            total);
  set("count-critical",       critical);
  set("count-unlocated",      unlocated);
  set("count-unintelligible", 0); // wired via message.status SSE in stream.js
  set("count-disputed",       disputed);

  const sc = document.getElementById("stream-count");
  if (sc) sc.textContent = `${total} ticket${total !== 1 ? "s" : ""}`;
}

// ---------------------------------------------------------------------------
// Acknowledge & Flag (also called from drawer.js)
// ---------------------------------------------------------------------------

async function acknowledgeTicket(id) {
  try {
    const res = await fetch(`${window.CORE_URL}/api/tickets/${id}/verdict`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ verdict: "verified" }),
    });
    if (res.ok) console.log(`[tickets] ticket ${id} acknowledged`);
  } catch (err) { console.error("[tickets] acknowledge failed:", err); }
}

async function flagTicket(id) {
  try {
    // TRD §3.3 / DB CHECK: dispatcher_verdict must be 'verified' or 'rejected'
    const res = await fetch(`${window.CORE_URL}/api/tickets/${id}/verdict`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ verdict: "rejected" }),
    });
    if (res.ok) console.log(`[tickets] ticket ${id} flagged`);
  } catch (err) { console.error("[tickets] flag failed:", err); }
}

// HXL export
function exportHXL() {
  window.open(`${window.CORE_URL}/api/export/hxl.csv`, "_blank");
}
