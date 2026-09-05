// filters.js — urgency chips + queue rail filtering (FE-05).
// Depends on: tickets.js (tickets array, renderTicketCard, updateCounts)
// map.js (refreshPins)

"use strict";

let activeUrgency = "all";
let activeQueue   = "all";
let activeSort    = localStorage.getItem("nidaa_sort_mode") || "urgency";

// ---------------------------------------------------------------------------
// Sorting helper (deterministic order across initial load, reload & live arrivals)
// ---------------------------------------------------------------------------

const URGENCY_RANK = {
  critical: 4,
  high: 3,
  moderate: 2,
  info: 1,
};

function sortTickets(list) {
  return [...list].sort((a, b) => {
    if (activeSort === "urgency") {
      const wa = URGENCY_RANK[a.urgency] || 0;
      const wb = URGENCY_RANK[b.urgency] || 0;
      if (wb !== wa) return wb - wa; // Highest urgency first
    }
    // Chronological (newest first)
    const ta = a.created_at ? new Date(a.created_at).getTime() : 0;
    const tb = b.created_at ? new Date(b.created_at).getTime() : 0;
    if (tb !== ta) return tb - ta;
    return (b.id || 0) - (a.id || 0);
  });
}

// ---------------------------------------------------------------------------
// Filter predicate
// ---------------------------------------------------------------------------

function ticketMatchesFilter(ticket) {
  // Hide dismissed tickets from normal queue feeds
  if (typeof dismissedTickets !== "undefined" && dismissedTickets.has(ticket.id)) {
    return false;
  }

  if (activeQueue !== "all") {
    if (activeQueue === "critical"       && ticket.urgency !== "critical")                          return false;
    if (activeQueue === "unlocated"      && !(ticket.latitude == null || ticket.longitude == null)) return false;
    if (activeQueue === "acknowledged"   && ticket.dispatcher_verdict !== "verified")              return false;
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

  const filtered = tickets.filter(ticketMatchesFilter);
  const visible  = sortTickets(filtered);

  // "Unhearable" queue: unintelligible messages yield status cards in
  // #status-stack, never tickets — the failure cards above ARE the content,
  // so a "No tickets match" message below them would be misleading (UI-UX §8).
  const hasUnintelligibleCards = document.querySelectorAll(
    '#status-stack .status-card[data-status="audio_unintelligible"]'
  ).length > 0;

  if (visible.length === 0 && !(activeQueue === "unintelligible" && hasUnintelligibleCards)) {
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

  // Live feed sort selector
  const sortSel = document.getElementById("sort-select");
  if (sortSel) {
    sortSel.value = activeSort;
    sortSel.addEventListener("change", (e) => {
      activeSort = e.target.value;
      localStorage.setItem("nidaa_sort_mode", activeSort);
      applyFilters();
    });
  }
}
