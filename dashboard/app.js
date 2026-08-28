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

/**
 * TODO(FE-03): connect to `${CORE_URL}/api/stream`, handle `ticket.created`
 * / `ticket.updated` / `metrics` events, and on reconnect resend
 * Last-Event-ID so the server replays missed events (docs/TRD.md 3.4).
 */
function connectStream() {
  // const source = new EventSource(`${CORE_URL}/api/stream`);
  // source.addEventListener("ticket.created", (e) => addTicket(JSON.parse(e.data)));
  console.log("TODO(FE-03): SSE connection not yet implemented.");
}

/**
 * TODO(FE-05): filter chips for urgency/district/time-window, filtering the
 * in-memory `tickets` array and re-rendering both the stream and the map.
 */
function applyFilters() {
  throw new Error("not implemented");
}

document.addEventListener("DOMContentLoaded", connectStream);
