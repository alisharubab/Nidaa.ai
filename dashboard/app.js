// app.js — boot file. Loads existing tickets from REST, then hands off to
// SSE stream. All logic lives in the module files:
//   tickets.js  — data store, card render, counts, ack/flag
//   drawer.js   — detail drawer (FE-07)
//   filters.js  — urgency + queue filters (FE-05)
//   stream.js   — SSE client, TTT polling, status cards (FE-08/FE-11)
//   map.js      — Leaflet map, pins, pin shapes (FE-06/FE-09)
//
// docs/TRD.md sections 3.3/3.4, docs/UI-UX-REQUIREMENTS.md sections 6.1–6.5

"use strict";

const CORE_URL = window.NIDAA_CORE_URL || "http://127.0.0.1:8000";

// ---------------------------------------------------------------------------
// Fetch existing tickets on load (REST backfill before SSE catches up)
// ---------------------------------------------------------------------------

async function loadExistingTickets() {
  try {
    const res = await fetch(`${CORE_URL}/api/tickets`);
    if (!res.ok) return;
    const { tickets: existing } = await res.json();
    // existing is newest-first; add them oldest-first so the local array
    // stays newest-first after each addTicket() unshift
    for (const t of [...existing].reverse()) {
      addTicket(t);
    }
  } catch (err) {
    console.warn("[app] could not load existing tickets:", err.message);
  }
}

// ---------------------------------------------------------------------------
// Presentation mode (UI-UX §10)
// ---------------------------------------------------------------------------

function checkPresentMode() {
  if (new URLSearchParams(window.location.search).get("present") === "true") {
    document.body.classList.add("present-mode");
  }
}

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------

document.addEventListener("DOMContentLoaded", async () => {
  checkPresentMode();
  initFilterChips();
  await loadExistingTickets();
  connectStream();
  pollMetrics();

  // Keyboard: Esc closes drawer; A acknowledges open ticket (UI-UX §9.3)
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeDrawer();
    if ((e.key === "a" || e.key === "A") && _drawerTicket) {
      acknowledgeTicket(_drawerTicket.id);
    }
  });

  // Scrim click closes drawer
  document.getElementById("drawer-scrim")
    ?.addEventListener("click", closeDrawer);
});
