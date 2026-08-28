// consent_ledger state machine. docs/TRD.md section 2 (schema) and
// docs/PRD.md section 3.1. States: pending -> granted | revoked.
// NOTE: this module talks to core/'s SQLite indirectly — it does NOT open
// nidaa.db directly (docs/ARCHITECTURE.md section 2.1, no cross-imports).
// It calls core/'s HTTP routes, or maintains its own lightweight local
// ledger if core/ doesn't expose one — decide this together on Day 1 and
// note the decision here.

/**
 * TODO(ING-06):
 *   - checkConsent(senderHash): look up state; if none, create `pending`.
 *   - On `pending`: send consent_notice (once), mark notice_sent_at, and
 *     still process the current message (implied consent per PRD 3.1).
 *   - On `revoked`: drop the message silently, no reply.
 *   - handleControlKeyword(senderHash, text): if text is BAND or STOP
 *     (case-insensitive), set state=revoked, revoked_at=now, and trigger
 *     purge of that sender's stored audio + transcript.
 */

async function checkConsent(senderHash) {
  throw new Error("not implemented");
}

async function handleControlKeyword(senderHash, text) {
  throw new Error("not implemented");
}

module.exports = { checkConsent, handleControlKeyword };
