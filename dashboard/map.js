// Leaflet map setup + pin rendering. docs/TRD.md section 7,
// docs/UI-UX-REQUIREMENTS.md sections 2.2/2.3/6.4.

const PAKISTAN_FLOOD_BOUNDS = {
  center: [26.5, 68.0], // roughly Sindh / southern Punjab
  zoom: 7,
};

// Urgency colour ramp (UI-UX §2.2 + token values from styles.css)
const URGENCY_COLOURS = {
  critical: { fill: "#C62A22", border: "#9B1F19" }, // --vermilion
  high:     { fill: "#F5A524", border: "#B86E0C" }, // --marigold-bright / --marigold
  moderate: { fill: "#0D6E80", border: "#073B47" }, // --indus / --indus-deep
  info:     { fill: "#8CA3AD", border: "#60818D" }, // --silt
};

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
 * Shape semantics (solid/hollow/double-ring) are FE-09.
 */
function renderTicketPin(ticket) {
  if (!pinLayer || ticket.latitude == null || ticket.longitude == null) return;

  const urgency = ticket.urgency || "info";
  const { fill, border } = URGENCY_COLOURS[urgency] || URGENCY_COLOURS.info;

  const marker = L.circleMarker([ticket.latitude, ticket.longitude], {
    radius: 9,
    color: border,
    weight: 2,
    fillColor: fill,
    fillOpacity: 0.9,
  });

  marker.bindTooltip(
    `<strong>${ticket.adm2_name || "Unknown district"}</strong><br>` +
    `${urgency.charAt(0).toUpperCase() + urgency.slice(1)}` +
    (ticket.pcode ? ` · ${ticket.pcode}` : ""),
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

document.addEventListener("DOMContentLoaded", initMap);
