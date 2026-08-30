// filters.js — urgency chips + queue rail filtering (FE-05).
// Depends on: tickets.js (tickets array, renderTicketCard, updateCounts)
// map.js (refreshPins)

"use strict";

let activeUrgency = "all";
let activeQueue   = "all";

// ---------------------------------------------------------------------------
// Filter predicate
// ---------------------------------------------------------------------------

function ticketMatchesFilter(ticket) {
  if (activeQueue !== "all") {
    if (activeQueue === "critical"       && ticket.urgency !== "critical")                          return false;
    if (activeQueue === "unlocated"      && !(ticket.latitude == null || ticket.longitude == null)) return false;
    if (activeQueue === "unintelligible" && ticket.error_code !== "STT_LOW_CONFIDENCE")             return false;
    if (activeQueue === "disputed"       && ticket.verification_status !== "user_disputed")         return false;
  }
  if (activeUrgency !== "all" && ticket.urgency !== activeUrgency) return false;
  return true;
}

// ---------------------------------------------------------------------------
// Re-render stream + map on filter change
// ---------------------------------------------------------------------------

function applyFilters() {
  const list = document.getElementById("ticket-list");
  if (!list) return;

  list.innerHTML = "";

  const visible = tickets.filter(ticketMatchesFilter);

  if (visible.length === 0) {
    const empty = document.createElement("div");
    empty.className = "filter-empty";
    empty.textContent = "No tickets match this filter.";
    list.appendChild(empty);
  } else {
    visible.forEach((t) => list.appendChild(renderTicketCard(t)));
  }

  if (typeof refreshPins === "function") refreshPins(visible);
  if (typeof refreshStatusCards === "function") refreshStatusCards(activeQueue);
  updateChipCounts();
}

// ---------------------------------------------------------------------------
// Chip count badges
// ---------------------------------------------------------------------------

function updateChipCounts() {
  const bar = document.getElementById("filter-bar");
  if (!bar) return;
  const counts = { all: tickets.length, critical: 0, high: 0, moderate: 0, info: 0 };
  tickets.forEach((t) => { if (counts[t.urgency] !== undefined) counts[t.urgency]++; });
  bar.querySelectorAll(".filter-chip").forEach((chip) => {
    const u = chip.dataset.urgency;
    let badge = chip.querySelector(".chip-count");
    if (!badge) {
      badge = document.createElement("span");
      badge.className = "chip-count";
      chip.appendChild(badge);
    }
    badge.textContent = counts[u] ?? "";
  });
}

// ---------------------------------------------------------------------------
// Wire up filter UI interactions
// ---------------------------------------------------------------------------

function initFilterChips() {
  // Map bar urgency chips
  const bar = document.getElementById("filter-bar");
  if (bar) {
    bar.addEventListener("click", (e) => {
      const chip = e.target.closest(".filter-chip");
      if (!chip) return;
      bar.querySelectorAll(".filter-chip").forEach((c) => c.classList.remove("selected"));
      chip.classList.add("selected");
      activeUrgency = chip.dataset.urgency || "all";
      applyFilters();
    });
  }

  // Left rail queue nav
  const queueList = document.getElementById("queue-list");
  if (queueList) {
    queueList.addEventListener("click", (e) => {
      const btn = e.target.closest(".queue-item");
      if (!btn) return;
      queueList.querySelectorAll(".queue-item").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      activeQueue = btn.dataset.filter || "all";
      applyFilters();
    });
  }
}
