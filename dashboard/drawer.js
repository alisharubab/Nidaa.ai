// drawer.js — ticket detail drawer (FE-07).
// Spec: UI-UX-REQUIREMENTS.md §6.5
// Depends on: tickets.js (verificationState, URGENCY_LABELS, parseItems, itemsSummary)

"use strict";

// CORE_URL is set once in tickets.js (loaded earlier)

let _drawerTicket = null;

// ---------------------------------------------------------------------------
// Open / close
// ---------------------------------------------------------------------------

function openDrawer(ticket) {
  _drawerTicket = ticket;
  const scrim  = document.getElementById("drawer-scrim");
  const drawer = document.getElementById("detail-drawer");
  if (!scrim || !drawer) return;
  _renderDrawerContent(ticket);
  scrim.classList.add("open");
  drawer.classList.add("open");
  drawer.focus();
  _backfillMessageFields(ticket);
}

// ticket.created / ticket.updated SSE payloads come from get_ticket(),
// which selects the tickets table only — modality/audio_path/raw_text
// (joined from messages in list_tickets, db.py) are missing on live
// tickets. Fetch them lazily on first drawer open and re-render once.
async function _backfillMessageFields(ticket) {
  if (ticket.message_id == null || messageCache.has(ticket.message_id)) return;
  try {
    const res = await fetch(`${window.CORE_URL}/api/tickets`);
    if (!res.ok) return;
    const { tickets: list } = await res.json();
    const full = list.find((t) => t.id === ticket.id);
    if (!full) return;
    messageCache.set(full.message_id, {
      modality:         full.modality,
      audio_path:       full.audio_path,
      audio_duration_s: full.audio_duration_s,
      raw_text:         full.raw_text,
    });
    // Re-render only if the user is still looking at this ticket
    if (_drawerTicket && _drawerTicket.id === full.id) {
      _renderDrawerContent(full);
    }
  } catch { /* core unreachable — drawer just stays without audio */ }
}

function closeDrawer() {
  _drawerTicket = null;
  document.getElementById("drawer-scrim")?.classList.remove("open");
  document.getElementById("detail-drawer")?.classList.remove("open");
}

// Called by updateTicket() in tickets.js when an SSE ticket.updated arrives
function refreshDrawer(ticket) {
  if (!_drawerTicket || _drawerTicket.id !== ticket.id) return;
  _drawerTicket = ticket;
  _renderDrawerContent(ticket);
}

// ---------------------------------------------------------------------------
// Content renderer
// ---------------------------------------------------------------------------

function _renderDrawerContent(ticket) {
  const drawer = document.getElementById("detail-drawer");
  if (!drawer) return;

  const urgency = ticket.urgency || "info";
  const state   = verificationState(ticket);
  const items   = parseItems(ticket.items_json);
  const missing = (() => {
    try { return JSON.parse(ticket.missing_fields || "[]"); } catch { return []; }
  })();
  const summary = structuredSummary(ticket, items);
  const conf    = ticket.extraction_conf ?? 0;

  // Audio: try messageCache first (populated by SSE ingest event), then
  // fall back to ticket fields if Person A adds them to the join later.
  const cached     = messageCache.get(ticket.message_id) || {};
  const audioPath  = cached.audio_path  || ticket.audio_path  || null;
  const modality   = cached.modality    || ticket.modality    || null;
  const transcript = cached.raw_text    || ticket.raw_text    || null;

  // Audio section. Three cases: the shared VoicePlayer (same waveform
  // component as the feed cards) when we have the path, a loading hint
  // when the backfill fetch is still in flight, and a genuine
  // not-available note when the path is missing.
  const audioSection = (modality === "audio" && audioPath)
    ? `<div class="drawer-section">
        <div class="drawer-section-label">Audio</div>
        <div data-drawer-player></div>
        ${(cached.audio_duration_s || ticket.audio_duration_s)
          ? `<span class="drawer-audio-dur t-mono">${Math.round(cached.audio_duration_s || ticket.audio_duration_s)}s voice note</span>`
          : ""}
      </div>`
    : modality === "audio" && !audioPath
      ? `<div class="drawer-section">
          <div class="drawer-section-label">Audio</div>
          <div class="drawer-no-audio">Audio file not available — path not returned by API</div>
        </div>`
      : modality == null && ticket.message_id != null
        ? `<div class="drawer-section">
            <div class="drawer-section-label">Audio</div>
            <div class="drawer-no-audio">Loading message details…</div>
          </div>`
        : "";

  // Confidence waveform bars scaled to extraction_conf
  const waveHeights = [0.4,0.7,1.0,0.9,0.6,0.8,1.0,0.7,0.5,0.8,0.9,0.6,
                       0.4,0.75,1.0,0.85,0.5,0.7,0.95,0.6];
  const waveHtml = waveHeights
    .map((h) => `<span class="drawer-wave-bar" style="height:${Math.max(4, Math.round(h * conf * 56))}px"></span>`)
    .join("");

  // Dual-script Transcript Section
  const transcriptSection = transcript
    ? `<div class="drawer-section">
        <div class="drawer-section-top">
          <div class="drawer-section-label">Transcript</div>
          <div class="transcript-toggle-group">
            <button class="btn-tab-pill active" onclick="event.stopPropagation(); _toggleTranscript(this, 'urdu')">اردو</button>
            <button class="btn-tab-pill" onclick="event.stopPropagation(); _toggleTranscript(this, 'latin')">Latin / Meaning</button>
          </div>
        </div>
        <div class="drawer-transcript urdu-text" id="drawer-transcript-box"
             data-urdu="${escapeHtml(transcript)}"
             data-latin="${escapeHtml(summary || itemsSummary(items) || transcript)}">
          ${escapeHtml(transcript)}
        </div>
      </div>`
    : "";

  // Extracted fields table
  const fields = [
    { key: "Location",   val: ticket.adm2_name
        ? `${ticket.adm2_name}${ticket.adm1_name ? ", " + ticket.adm1_name : ""}`
        : null },
    { key: "P-code",     val: ticket.pcode     || null },
    { key: "Intent",     val: ticket.intent    || null },
    { key: "Urgency",    val: URGENCY_LABELS[urgency] || urgency },
    { key: "Needs",      val: items.length ? itemsSummary(items) : null },
    { key: "Affected",   val: ticket.people_affected > 0 ? String(ticket.people_affected) : null },
    { key: "Casualties", val: ticket.casualties > 0 ? String(ticket.casualties) : null },
    { key: "Geocode",    val: ticket.geocode_method || "none" },
    { key: "Confidence", val: `${Math.round(conf * 100)}%` },
  ];

  const fieldsHtml = fields.map(({ key, val }) => `
    <div class="drawer-field">
      <span class="drawer-field-key">${key}</span>
      <span class="drawer-field-val ${!val ? "drawer-missing" : ""}">${val || "—"}</span>
    </div>`
  ).join("");

  const missingBadges = missing.length
    ? `<div class="drawer-missing-row">${
        missing.map((f) => `<span class="drawer-missing-badge">${f}</span>`).join("")
      }</div>`
    : "";

  const reasoningSection = ticket.reasoning_note
    ? `<div class="drawer-section">
        <div class="drawer-section-label">AI Reasoning</div>
        <div class="drawer-reasoning">${ticket.reasoning_note}</div>
      </div>`
    : "";

  const isConfirmed = state === "confirmed";
  const isDisputed  = state === "disputed";

  drawer.innerHTML = `
    <div class="drawer-header">
      <div class="drawer-header-top">
        <span class="ticket-urgency-badge urgency-${urgency}-badge">${URGENCY_LABELS[urgency]}</span>
        <button class="drawer-close" aria-label="Close drawer" onclick="closeDrawer()">×</button>
      </div>
      <h2 class="t-title drawer-title">
        ${ticket.adm2_name || "Unlocated"}${ticket.adm1_name ? ", " + ticket.adm1_name : ""}
      </h2>
      ${ticket.pcode ? `<span class="drawer-pcode t-mono">${ticket.pcode}</span>` : ""}
    </div>
    <div class="drawer-body">
      ${audioSection}
      <div class="drawer-section">
        <div class="drawer-section-label">Confidence waveform</div>
        <div class="drawer-waveform">${waveHtml}</div>
        <div class="drawer-conf-bar">
          <div class="drawer-conf-fill" style="width:${Math.round(conf * 100)}%"></div>
        </div>
        <div class="drawer-conf-label t-mono-sm">
          ${Math.round(conf * 100)}% extraction confidence · geocode: ${ticket.geocode_method || "none"}
        </div>
      </div>
      ${transcriptSection}
      <div class="drawer-section">
        <div class="drawer-section-label">Extracted fields</div>
        <div class="drawer-fields">${fieldsHtml}</div>
        ${missingBadges}
      </div>
      ${reasoningSection}
    </div>
    <div class="drawer-footer">
      <div class="drawer-footer-left">
        <span class="state-dot ${state}">
          ${isConfirmed ? "Confirmed" : isDisputed ? "Disputed" : "Unconfirmed"}
        </span>
        <button class="btn-drawer-dismiss" onclick="dismissTicket(${ticket.id}); closeDrawer();" title="Remove from active stream">
          Dismiss Ticket
        </button>
      </div>
      <div class="drawer-actions">
        <button class="btn-flag"
          onclick="flagTicket(${ticket.id})"
          ${isDisputed ? "disabled" : ""}>Flag</button>
        <button class="btn-ack"
          onclick="event.stopPropagation(); acknowledgeTicket(${ticket.id})"
          ${isConfirmed ? "disabled" : ""}>Acknowledge</button>
      </div>
    </div>
  `;

  // Mount the shared voice player (same component as the feed cards)
  const playerMount = drawer.querySelector("[data-drawer-player]");
  if (playerMount && modality === "audio" && audioPath) {
    playerMount.replaceWith(VoicePlayer.create(ticket, audioPath));
  }
}

function _toggleTranscript(btn, script) {
  const box = document.getElementById("drawer-transcript-box");
  if (!box) return;
  const parent = btn.closest(".transcript-toggle-group");
  if (parent) {
    parent.querySelectorAll(".btn-tab-pill").forEach((b) => b.classList.remove("active"));
  }
  btn.classList.add("active");
  if (script === "urdu") {
    box.textContent = box.dataset.urdu || "";
    box.className = "drawer-transcript urdu-text";
  } else {
    box.textContent = box.dataset.latin || "";
    box.className = "drawer-transcript latin-text";
  }
}
