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

// CORE_URL is set once in tickets.js (loaded earlier)

// ---------------------------------------------------------------------------
// Fetch existing tickets on load (REST backfill before SSE catches up)
// ---------------------------------------------------------------------------

async function loadExistingTickets() {
  try {
    const res = await fetch(`${window.CORE_URL}/api/tickets`);
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
// Audio Chime & Keyboard Shortcuts (Hackathon 9.8+ Upgrade)
// ---------------------------------------------------------------------------

let _soundAlertsEnabled = localStorage.getItem("nidaa_sound_alerts") !== "false";

function toggleSoundAlerts() {
  _soundAlertsEnabled = !_soundAlertsEnabled;
  localStorage.setItem("nidaa_sound_alerts", _soundAlertsEnabled ? "true" : "false");
  const icon = document.getElementById("sound-icon");
  if (icon) icon.textContent = _soundAlertsEnabled ? "🔔" : "🔕";
  if (_soundAlertsEnabled) playCriticalChime();
}

function playCriticalChime() {
  if (!_soundAlertsEnabled) return;
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const now = ctx.currentTime;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    osc.type = "sine";
    osc.frequency.setValueAtTime(587.33, now); // D5
    osc.frequency.exponentialRampToValueAtTime(880.00, now + 0.08); // A5

    gain.gain.setValueAtTime(0.15, now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.2);

    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.start(now);
    osc.stop(now + 0.2);
  } catch { /* audio context blocked until user interaction */ }
}

// ---------------------------------------------------------------------------
// Mobile View Switcher
// ---------------------------------------------------------------------------

function switchMobileView(tab) {
  const mapPane = document.getElementById("map-pane");
  const streamPane = document.getElementById("ticket-stream");
  const btnMap = document.getElementById("tab-btn-map");
  const btnFeed = document.getElementById("tab-btn-feed");

  if (tab === "map") {
    mapPane?.classList.remove("mobile-hidden");
    streamPane?.classList.add("mobile-hidden");
    btnMap?.classList.add("active");
    btnFeed?.classList.remove("active");
    if (typeof map !== "undefined" && map) map.invalidateSize();
  } else {
    mapPane?.classList.add("mobile-hidden");
    streamPane?.classList.remove("mobile-hidden");
    btnMap?.classList.remove("active");
    btnFeed?.classList.add("active");
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

  // Initialize sound icon
  const icon = document.getElementById("sound-icon");
  if (icon) icon.textContent = _soundAlertsEnabled ? "🔔" : "🔕";

  // Keyboard navigation (UI-UX §9.3)
  document.addEventListener("keydown", (e) => {
    // Ignore keystrokes in inputs
    if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;

    if (e.key === "Escape") closeDrawer();

    // 'A': Acknowledge open or top ticket
    if (e.key === "a" || e.key === "A") {
      const targetId = _drawerTicket ? _drawerTicket.id : tickets[0]?.id;
      if (targetId) acknowledgeTicket(targetId);
    }

    // 'D': Dismiss open or top ticket
    if (e.key === "d" || e.key === "D") {
      const targetId = _drawerTicket ? _drawerTicket.id : tickets[0]?.id;
      if (targetId) {
        dismissTicket(targetId);
        if (_drawerTicket && _drawerTicket.id === targetId) closeDrawer();
      }
    }

    // 'J' / 'K': Navigate tickets
    if (e.key === "j" || e.key === "J") {
      const active = tickets.filter((t) => !dismissedTickets.has(t.id));
      if (!active.length) return;
      const curIdx = _drawerTicket ? active.findIndex((t) => t.id === _drawerTicket.id) : -1;
      const next = active[Math.min(active.length - 1, curIdx + 1)];
      if (next) openDrawer(next);
    }
    if (e.key === "k" || e.key === "K") {
      const active = tickets.filter((t) => !dismissedTickets.has(t.id));
      if (!active.length) return;
      const curIdx = _drawerTicket ? active.findIndex((t) => t.id === _drawerTicket.id) : 0;
      const prev = active[Math.max(0, curIdx - 1)];
      if (prev) openDrawer(prev);
    }
  });

  // Scrim click closes drawer
  document.getElementById("drawer-scrim")
    ?.addEventListener("click", closeDrawer);
});
