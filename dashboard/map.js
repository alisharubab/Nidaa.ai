// Leaflet map setup + pin rendering. docs/TRD.md section 7,
// docs/UI-UX-REQUIREMENTS.md section 6.4.

const PAKISTAN_FLOOD_BOUNDS = {
  center: [26.5, 68.0], // roughly Sindh / southern Punjab
  zoom: 7,
};

let map;
let pinLayer;

function initMap() {
  map = L.map("map").setView(PAKISTAN_FLOOD_BOUNDS.center, PAKISTAN_FLOOD_BOUNDS.zoom);

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 18,
  }).addTo(map);

  // TODO(FE-10): desaturate/lighten tiles per UI-UX 6.4
  // (filter: saturate(0.55) brightness(1.08) contrast(0.94)) and cache an
  // offline tile set for this bounding box.

  pinLayer = L.layerGroup().addTo(map);
}

/**
 * TODO(FE-04/FE-09): custom SVG divIcon per verification/urgency state
 * (solid/hollow/double-ring/cluster-badge -- UI-UX section 2.3), plus the
 * arrival animation in UI-UX section 6.3.
 */
function renderTicketPin(ticket) {
  if (!pinLayer || ticket.latitude == null || ticket.longitude == null) return;
  const marker = L.circleMarker([ticket.latitude, ticket.longitude], {
    radius: 8,
    color: "#0D6E80",
  });
  marker.bindTooltip(`${ticket.adm2_name || "Unknown district"} — ${ticket.urgency}`);
  marker.addTo(pinLayer);
}

document.addEventListener("DOMContentLoaded", initMap);
