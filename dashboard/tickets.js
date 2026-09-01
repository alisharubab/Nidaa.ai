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

// --- Live voice card helpers (image-2 redesign) ---------------------------

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[c]);
}

function timeAgo(iso) {
  if (!iso) return "";
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return "";
  const s = Math.max(0, (Date.now() - t) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short" });
}

const INTENT_SUMMARY = {
  resource_request: "Resource request",
  incident_report: "Incident report",
  infrastructure_damage: "Infrastructure damage",
  non_actionable: "Non-actionable",
};

// English structured line derived from the extraction — pairs with the
// Urdu transcript below it for the card's dual-script presentation.
function structuredSummary(ticket, items) {
  const parts = [];
  if (ticket.intent === "resource_request" && items.length) {
    parts.push("Needs " + itemsSummary(items));
  } else if (ticket.intent) {
    parts.push(INTENT_SUMMARY[ticket.intent] || ticket.intent);
  }
  if (ticket.people_affected > 0) parts.push(`≈${ticket.people_affected} affected`);
  if (ticket.casualties > 0) {
    parts.push(`${ticket.casualties} ${ticket.casualties === 1 ? "casualty" : "casualties"}`);
  }
  return parts.join(" · ");
}

// Colourful relief-supply badges — Food 🍲 / Boats 🚤 / Medical 💊 etc.
// Item names are the pipeline's normalised vocabulary (extract.py).
const ITEM_META = {
  water:            { emoji: "💧", cls: "item-water" },
  food:             { emoji: "🍲", cls: "item-food" },
  medicine:         { emoji: "💊", cls: "item-med" },
  medical:          { emoji: "💊", cls: "item-med" },
  "medical supplies": { emoji: "💊", cls: "item-med" },
  "health supplies": { emoji: "💊", cls: "item-med" },
  boat:             { emoji: "🚤", cls: "item-boat" },
  boats:            { emoji: "🚤", cls: "item-boat" },
  blanket:          { emoji: "🧣", cls: "item-blanket" },
  blankets:         { emoji: "🧣", cls: "item-blanket" },
  shelter:          { emoji: "⛺", cls: "item-shelter" },
};

function itemBadges(items) {
  if (!items || items.length === 0) return "";
  return items.map((i) => {
    const name = (i.item || "").toString().trim();
    const meta = ITEM_META[name.toLowerCase()] || { emoji: "📦", cls: "item-other" };
    const qty = i.qty ? `${escapeHtml(String(i.qty))} ` : "";
    return `<span class="item-badge ${meta.cls}">${meta.emoji} ${qty}${escapeHtml(name)}</span>`;
  }).join("");
}

const URDU_SCRIPT = /[\u0600-\u06FF]/;

// ---------------------------------------------------------------------------
// Card renderer — live voice card (image-2 redesign, UI-UX §6.2 basis)
// District & urgency header + timestamp, playable voice waveform, dual-script
// transcript, relief badges, acknowledge action.
// ---------------------------------------------------------------------------

function renderTicketCard(ticket) {
  const urgency  = ticket.urgency || "info";
  const state    = verificationState(ticket);
  const items    = parseItems(ticket.items_json);
  const pcode    = ticket.pcode || "";
  const time     = formatTime(ticket.created_at);
  const ago      = timeAgo(ticket.created_at);

  // Message fields: cache (REST join / backfill) first, ticket fields second
  const cached    = messageCache.get(ticket.message_id) || {};
  const modality  = cached.modality          || ticket.modality          || null;
  const audioPath = cached.audio_path        || ticket.audio_path        || null;
  const transcript = cached.raw_text          || ticket.raw_text          || null;
  const isUrdu    = URDU_SCRIPT.test(transcript || "");

  const summary   = structuredSummary(ticket, items);
  const badges    = itemBadges(items);
  const acked     = state === "confirmed";

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
        <div class="ticket-head-left">
          <span class="ticket-district">${escapeHtml(ticket.adm2_name || "Unlocated")}</span>
          <span class="ticket-loc-sub">${[
              ticket.adm1_name ? escapeHtml(ticket.adm1_name) : "",
              pcode ? escapeHtml(pcode) : "",
              modality === "audio" ? "Voice note" : modality === "text" ? "Text" : "",
            ].filter(Boolean).join(" · ")}</span>
        </div>
        <div class="ticket-head-right">
          <span class="ticket-urgency-badge">${URGENCY_LABELS[urgency]}</span>
          <span class="ticket-time" title="${escapeHtml(time)}">${escapeHtml(ago)}</span>
          <button class="btn-card-dismiss" title="Dismiss ticket" onclick="event.stopPropagation(); dismissTicket(${ticket.id})">✕</button>
        </div>
      </div>
      ${modality === "audio" ? '<div class="ticket-player-mount" data-player-mount></div>' : ""}
      ${summary ? `<div class="ticket-summary">${escapeHtml(summary)}</div>` : ""}
      ${transcript
        ? `<div class="ticket-transcript ${isUrdu ? "urdu-text" : "latin-text"}">${escapeHtml(transcript)}</div>`
        : ""}
      ${badges ? `<div class="ticket-items">${badges}</div>` : ""}
      <div class="ticket-footer">
        <span class="state-dot ${state}">${state === "confirmed" ? "Confirmed" : state === "disputed" ? "Disputed" : "Unconfirmed"}</span>
        <button class="btn-ack${acked ? " acked" : ""}" onclick="event.stopPropagation(); acknowledgeTicket(${ticket.id})"
          ${acked ? "disabled" : ""}>${acked ? "✓ Acknowledged" : "Acknowledge"}</button>
      </div>
    </div>
  `;

  // Real playable waveform — replaces the old decorative static bars
  const mount = card.querySelector("[data-player-mount]");
  if (mount) {
    if (audioPath) {
      mount.replaceWith(VoicePlayer.create(ticket, audioPath));
    } else {
      // Voice message whose path isn't known yet (SSE-created, backfill in
      // flight) — the backfill re-renders with the real player.
      mount.remove();
    }
  }

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
  } else {
    // SSE-created tickets lack the message join (get_ticket selects tickets
    // only) — pull the joined fields once so cards can show the real
    // transcript + audio player.
    _ensureMessageFields();
  }
  applyFilters();
  updateCounts();
}

// Fetches GET /api/tickets (whose rows carry the messages join) into the
// messageCache, then re-renders so live cards gain transcript + player.
// Re-fetches at most once per 30 s window (replay bursts hit the cache).
let _messageFieldsAt = 0;
function _ensureMessageFields() {
  if (Date.now() - _messageFieldsAt < 30000) return;
  _messageFieldsAt = Date.now();
  (async () => {
    try {
      const res = await fetch(`${window.CORE_URL}/api/tickets`);
      if (!res.ok) return;
      const { tickets: list } = await res.json();
      for (const t of list) {
        if (t.message_id == null || messageCache.has(t.message_id)) continue;
        messageCache.set(t.message_id, {
          modality:          t.modality,
          audio_path:        t.audio_path,
          audio_duration_s:  t.audio_duration_s,
          raw_text:          t.raw_text,
        });
      }
      applyFilters(); // re-render: transcripts + players now available
    } catch { /* core unreachable — cards stay without transcripts */ }
  })();
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

// Persistent client-side dismissals (saved in localStorage across page reloads)
const dismissedTickets = new Set(
  JSON.parse(localStorage.getItem("nidaa_dismissed_tickets") || "[]")
);

function dismissTicket(id) {
  dismissedTickets.add(id);
  try {
    localStorage.setItem("nidaa_dismissed_tickets", JSON.stringify([...dismissedTickets]));
  } catch { /* ignore quota */ }
  applyFilters();
  updateCounts();
}

function restoreTicket(id) {
  dismissedTickets.delete(id);
  try {
    localStorage.setItem("nidaa_dismissed_tickets", JSON.stringify([...dismissedTickets]));
  } catch { /* ignore quota */ }
  applyFilters();
  updateCounts();
}

function updateCounts() {
  const activeTickets = tickets.filter((t) => !dismissedTickets.has(t.id));
  const total        = activeTickets.length;
  const critical     = activeTickets.filter((t) => t.urgency === "critical").length;
  const unlocated    = activeTickets.filter((t) => t.latitude == null || t.longitude == null).length;
  const acknowledged = activeTickets.filter((t) => t.dispatcher_verdict === "verified" || t.verification_status === "user_confirmed").length;
  const disputed     = activeTickets.filter((t) => t.verification_status === "user_disputed").length;

  const set = (id, n) => { const el = document.getElementById(id); if (el) el.textContent = n; };
  set("count-all",            total);
  set("count-critical",       critical);
  set("count-unlocated",      unlocated);
  set("count-acknowledged",   acknowledged);
  set("count-unintelligible", 0); // wired via message.status SSE in stream.js
  set("count-disputed",       disputed);

  const sc = document.getElementById("stream-count");
  if (sc) sc.textContent = `${total} active ticket${total !== 1 ? "s" : ""}`;
  const mfc = document.getElementById("m-feed-count");
  if (mfc) mfc.textContent = total;

  updateDistrictTicker();
}

function updateDistrictTicker() {
  const el = document.getElementById("ticker-content");
  if (!el) return;
  const active = tickets.filter((t) => !dismissedTickets.has(t.id) && t.adm2_name);
  if (!active.length) {
    el.textContent = "No active located incidents.";
    return;
  }
  const districtMap = new Map();
  for (const t of active) {
    const d = t.adm2_name;
    const items = parseItems(t.items_json);
    const summary = items.length ? itemsSummary(items) : (t.intent || "assistance");
    if (!districtMap.has(d)) districtMap.set(d, []);
    districtMap.get(d).push(summary);
  }
  const text = Array.from(districtMap.entries())
    .slice(0, 8)
    .map(([dist, needs]) => `${dist}: ${needs.slice(0, 2).join(", ")}`)
    .join("   ·   ");
  el.textContent = text;
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

// HXL export (DATA-06 / DoD-9). Anchor+download instead of window.open:
// popup blockers regularly eat window.open for non-user-visible navigation,
// which would silently kill the export mid-demo.
function exportHXL() {
  const a = document.createElement("a");
  a.href = `${window.CORE_URL}/api/export/hxl.csv`;
  a.download = `nidaa-hxl-${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
}
