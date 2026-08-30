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
  const conf = ticket.extraction_conf ?? 0;

  // Audio: try messageCache first (populated by SSE ingest event), then
  // fall back to ticket fields if Person A adds them to the join later.
  const cached     = messageCache.get(ticket.message_id) || {};
  const audioPath  = cached.audio_path  || ticket.audio_path  || null;
  const modality   = cached.modality    || ticket.modality    || null;
  const transcript = cached.raw_text    || ticket.raw_text    || null;

  // Audio section
  const audioSection = (modality === "audio" && audioPath)
    ? `<div class="drawer-section">
        <div class="drawer-section-label">Audio</div>
        <audio controls
          src="${window.CORE_URL}/audio/${encodeURIComponent(audioPath.split(/[\/\\]/).pop())}"
          class="drawer-audio"></audio>
        ${cached.audio_duration_s
          ? `<span class="drawer-audio-dur t-mono">${Math.round(cached.audio_duration_s)}s voice note</span>`
          : ""}
      </div>`
    : modality === "audio" && !audioPath
      ? `<div class="drawer-section">
          <div class="drawer-section-label">Audio</div>
          <div class="drawer-no-audio">Audio file not available — path not returned by API</div>
        </div>`
      : "";

  // Confidence waveform bars scaled to extraction_conf
  const waveHeights = [0.4,0.7,1.0,0.9,0.6,0.8,1.0,0.7,0.5,0.8,0.9,0.6,
                       0.4,0.75,1.0,0.85,0.5,0.7,0.95,0.6];
  const waveHtml = waveHeights
    .map((h) => `<span class="drawer-wave-bar" style="height:${Math.max(4, Math.round(h * conf * 56))}px"></span>`)
    .join("");

  // Transcript
  const transcriptSection = transcript
    ? `<div class="drawer-section">
        <div class="drawer-section-label">Transcript</div>
        <div class="urdu-text drawer-transcript">${transcript}</div>
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
      <span class="state-dot ${state}">
        ${isConfirmed ? "Confirmed" : isDisputed ? "Disputed" : "Unconfirmed"}
      </span>
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
}
