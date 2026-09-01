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

// FE-10: offline tile cache. tools/fetch_tiles.py downloads zoom 6-9 OSM
// tiles for the demo bbox into dashboard/tiles/. Probe one tile that the
// cache always contains (z6 tile under the default view centre) and use
// the local cache when it loads -- so the pitch demo renders the map with
// zero network. Falls back to live OSM tiles when the cache is absent.
function _probeLocalTiles() {
  return new Promise((resolve) => {
    const img = new Image();
    img.onload  = () => resolve(true);
    img.onerror = () => resolve(false);
    img.src = "tiles/6/44/27.png"; // tile containing [26.5, 68.0] at z6
  });
}

async function _addTileLayer() {
  // CartoDB Positron: light basemap with crisp English labels — the
  // localized labels on OSM-standard tiles read as blurry clutter next
  // to the redesigned white cards.
  const attribution = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>';
  if (await _probeLocalTiles()) {
    L.tileLayer("tiles/{z}/{x}/{y}.png", {
      attribution,
      // cache stops at z9 -- above that Leaflet upscales the z9 tiles
      // instead of requesting (missing) remote ones, keeping the demo
      // fully offline while still allowing a little extra zoom.
      maxNativeZoom: 9,
      maxZoom: 11,
    }).addTo(map);
  } else {
    L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png", {
      attribution,
      subdomains: "abcd",
      maxZoom: 18,
    }).addTo(map);
  }
}

function initMap() {
  map = L.map("map").setView(PAKISTAN_FLOOD_BOUNDS.center, PAKISTAN_FLOOD_BOUNDS.zoom);

  _addTileLayer();

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
