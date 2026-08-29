// SSE client, ticket stream rendering, filters. docs/TRD.md sections 3.3/3.4,
// docs/UI-UX-REQUIREMENTS.md sections 6.1-6.3.

const CORE_URL = window.NIDAA_CORE_URL || "http://127.0.0.1:8000";

let tickets = []; // in-memory array, filtered client-side (docs/TRD.md section 7)

function renderTicketCard(ticket) {
  const card = document.createElement("div");
  card.className = `ticket-card urgency-${ticket.urgency || "info"}`;
  card.innerHTML = `
    <strong>${ticket.adm2_name || "Unlocated"}</strong>
    <p>${(ticket.items_json && JSON.parse(ticket.items_json).map((i) => i.item).join(", ")) || ""}</p>
  `;
  // TODO(FE-02/FE-03): full card markup per UI-UX section 6.2 (waveform,
  // state dot, Acknowledge button), arrival animation per section 6.3.
  return card;
}

function addTicket(ticket) {
  tickets.unshift(ticket);
  const stream = document.getElementById("ticket-stream");
  const emptyState = stream.querySelector(".empty-state");
  if (emptyState) emptyState.remove();
  stream.prepend(renderTicketCard(ticket));

  if (typeof renderTicketPin === "function") renderTicketPin(ticket);
}

function setLiveIndicator(isLive) {
  const el = document.getElementById("live-indicator");
  if (el) el.textContent = isLive ? "● live" : "○ reconnecting";
}

function updateTicket(ticket) {
  const idx = tickets.findIndex((t) => t.id === ticket.id);
  if (idx === -1) return addTicket(ticket);
  tickets[idx] = ticket;
  const stream = document.getElementById("ticket-stream");
  const existing = stream.children[idx];
  if (existing) existing.replaceWith(renderTicketCard(ticket));
}

/**
 * SSE client. The browser's native EventSource already resends
 * Last-Event-ID on reconnect (docs/TRD.md 3.4) -- no manual bookkeeping
 * needed here.
 */
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

/**
 * TODO(FE-05): filter chips for urgency/district/time-window, filtering the
 * in-memory `tickets` array and re-rendering both the stream and the map.
 */
function applyFilters() {
  throw new Error("not implemented");
}

document.addEventListener("DOMContentLoaded", connectStream);
