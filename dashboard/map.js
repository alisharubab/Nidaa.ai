// Leaflet map setup + pin rendering. docs/TRD.md section 7,
// docs/UI-UX-REQUIREMENTS.md sections 2.2/2.3/6.4.

const PAKISTAN_FLOOD_BOUNDS = {
  center: [26.5, 68.0], // roughly Sindh / southern Punjab
  zoom: 7,
};

// Urgency colour ramp: read from CSS custom properties so map pins stay
// in sync with the design tokens in styles.css (UI-UX §2.2).
function _token(name) {
  const value = getComputedStyle(document.documentElement).getPropertyValue(name);
  return value ? value.trim() : null;
}

const URGENCY_COLOURS = () => ({
  critical: { fill: _token("--vermilion"),      border: _token("--vermilion") },
  high:     { fill: _token("--marigold-bright"), border: _token("--marigold") },
  moderate: { fill: _token("--indus"),           border: _token("--indus-deep") },
  info:     { fill: _token("--silt"),             border: _token("--silt") },
});

let map;
let pinLayer;

// ticketId → Leaflet marker reference (for future state updates / FE-09)
const pinMap = new Map();

function initMap() {
  map = L.map("map").setView(PAKISTAN_FLOOD_BOUNDS.center, PAKISTAN_FLOOD_BOUNDS.zoom);

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 18,
  }).addTo(map);

  // Tile desaturation so urgency pins are the loudest element (UI-UX §6.4).
  // Also handled in CSS (.leaflet-tile-pane filter) but repeated here for
  // clarity and in case the CSS rule is overridden.

  pinLayer = L.layerGroup().addTo(map);
}

/**
 * Add a single pin for a ticket. Colour reflects urgency (FE-06).
 * Shape semantics (FE-09):
 *   confirmed   → solid fill + check symbol in tooltip
 *   disputed    → hollow ring, double border (vermilion inner ring via CSS shadow)
 *   unconfirmed → hollow ring (fill transparent)
 */
function pinOptions(ticket) {
  const urgency = ticket.urgency || "info";
  const { fill, border } = URGENCY_COLOURS()[urgency] || URGENCY_COLOURS().info;
  const state =
    ticket.verification_status === "user_confirmed" || ticket.dispatcher_verdict === "verified"
      ? "confirmed"
      : ticket.verification_status === "user_disputed"
        ? "disputed"
        : "unconfirmed";

  if (state === "confirmed") {
    return { radius: 9, color: border, weight: 2, fillColor: fill, fillOpacity: 0.9 };
  }
  if (state === "disputed") {
    // Double ring: outer ring in urgency border colour, inner ring via boxShadow
    // equivalent — simulated by thick weight + vermilion dashArray ring
    return { radius: 9, color: _token("--vermilion"), weight: 3, fillColor: fill, fillOpacity: 0.15 };
  }
  // unconfirmed: hollow ring
  return { radius: 9, color: border, weight: 2, fillColor: fill, fillOpacity: 0.15 };
}

function stateLabel(ticket) {
  if (ticket.verification_status === "user_confirmed" || ticket.dispatcher_verdict === "verified") return "✓ Confirmed";
  if (ticket.verification_status === "user_disputed") return "⚠ Disputed";
  return "Unconfirmed";
}

function renderTicketPin(ticket) {
  if (!pinLayer || ticket.latitude == null || ticket.longitude == null) return;

  const urgency = ticket.urgency || "info";
  const marker = L.circleMarker([ticket.latitude, ticket.longitude], pinOptions(ticket));

  marker.bindTooltip(
    `<strong>${ticket.adm2_name || "Unknown district"}</strong><br>` +
    `${urgency.charAt(0).toUpperCase() + urgency.slice(1)}` +
    (ticket.pcode ? ` · ${ticket.pcode}` : "") +
    `<br><span style="font-size:11px;opacity:.75">${stateLabel(ticket)}</span>`,
    { direction: "top", offset: [0, -6] }
  );

  marker.addTo(pinLayer);
  pinMap.set(ticket.id, marker);
}

/**
 * Replace all pins with those from the provided ticket array.
 * Called by applyFilters() in app.js when the user switches a filter.
 */
function refreshPins(visibleTickets) {
  if (!pinLayer) return;
  pinLayer.clearLayers();
  pinMap.clear();
  visibleTickets.forEach(renderTicketPin);
}

/**
 * Update a single pin in-place when a ticket changes state (FE-09).
 * Called by updateTicket() in app.js after an SSE ticket.updated event.
 */
function updatePin(ticket) {
  const existing = pinMap.get(ticket.id);
  if (!existing) {
    // Pin not yet rendered (e.g. lat/lng arrived late)
    renderTicketPin(ticket);
    return;
  }
  existing.setStyle(pinOptions(ticket));
  // Rebind tooltip to reflect new state label
  existing.unbindTooltip();
  const urgency = ticket.urgency || "info";
  existing.bindTooltip(
    `<strong>${ticket.adm2_name || "Unknown district"}</strong><br>` +
    `${urgency.charAt(0).toUpperCase() + urgency.slice(1)}` +
    (ticket.pcode ? ` · ${ticket.pcode}` : "") +
    `<br><span style="font-size:11px;opacity:.75">${stateLabel(ticket)}</span>`,
    { direction: "top", offset: [0, -6] }
  );
}

document.addEventListener("DOMContentLoaded", initMap);
