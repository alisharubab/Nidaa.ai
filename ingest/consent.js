// consent_ledger state machine. docs/TRD.md section 2 (schema), section 3.1
// addendum (the /internal/consent/* endpoints), and docs/PRD.md section 3.1.
//
// This module never touches nidaa.db directly (docs/ARCHITECTURE.md 2.1) --
// it calls core/'s /internal/consent/check and /internal/consent/revoke.

const { withScheme } = require("./url");

// Independent copy of index.js's CORE_URL -- this module never imports
// index.js (would create a circular require), so it reads+normalizes the
// env var itself rather than trusting index.js already did it. See url.js
// for why the scheme prefix matters on Render.
const CORE_URL = withScheme(process.env.CORE_URL || "http://127.0.0.1:8000");

/**
 * Call once per inbound message, before anything else. Returns
 * {state: "granted"|"revoked", sendNotice: bool}. If state is "revoked",
 * the caller must drop the message silently and never call
 * POST /internal/ingest for it.
 */
async function checkConsent(senderHash, phoneTail) {
  const res = await fetch(`${CORE_URL}/internal/consent/check`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sender_hash: senderHash, phone_tail: phoneTail }),
  });
  if (!res.ok) throw new Error(`consent check failed: ${res.status}`);
  const { state, send_notice: sendNotice } = await res.json();
  return { state, sendNotice };
}

/**
 * Call on BAND/STOP (case-insensitive), before routing anything else.
 * core/ handles purging that sender's stored audio_path + raw_text.
 */
async function revokeConsent(senderHash) {
  const res = await fetch(`${CORE_URL}/internal/consent/revoke`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sender_hash: senderHash }),
  });
  if (!res.ok) throw new Error(`consent revoke failed: ${res.status}`);
  return res.json();
}

const BAND_KEYWORDS = new Set(["band", "stop"]);

/**
 * Returns true if `text` was a control keyword and was handled (caller
 * should stop processing this message as a triage message). TRD section 6,
 * step 4: BAND/STOP/1/2 never enter the triage pipeline.
 */
async function handleControlKeyword(senderHash, text) {
  const normalised = (text || "").trim().toLowerCase();
  if (BAND_KEYWORDS.has(normalised)) {
    await revokeConsent(senderHash);
    return true;
  }
  // "1" / "2": sender confirming or disputing a readback. Route to
  // POST /internal/readback-reply. TRD §6 step 4 — these never enter
  // the triage pipeline. CORE-23 is the other side of this call.
  if (normalised === "1" || normalised === "2") {
    const res = await fetch(`${CORE_URL}/internal/readback-reply`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sender_hash: senderHash, reply: normalised }),
    });
    if (!res.ok) {
      console.error(`[consent] readback-reply failed: ${res.status}`);
    }
    return true; // handled — never falls through to triage
  }
  return false;
}

module.exports = { checkConsent, revokeConsent, handleControlKeyword };
