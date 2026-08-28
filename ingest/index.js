// Socket bootstrap, pairing, and the inbound message handler.
// docs/TRD.md section 6, docs/ARCHITECTURE.md section 4.

require("dotenv").config({ path: require("path").join(__dirname, "..", ".env") });
const crypto = require("crypto");

const { checkConsent, handleControlKeyword } = require("./consent");
const { OutboundQueue } = require("./outbound");
const { downloadAndConvert } = require("./media");
const { render } = require("./templates");

const CORE_URL = process.env.CORE_URL || "http://127.0.0.1:8000";
const SENDER_HASH_SALT = process.env.SENDER_HASH_SALT || "change-me";

function senderHash(jid) {
  return "sha256:" + crypto.createHash("sha256").update(jid + SENDER_HASH_SALT).digest("hex");
}

function phoneTail(jid) {
  const digits = jid.replace(/\D/g, "");
  return digits.slice(-3);
}

/**
 * TODO(ING-01/ING-02):
 *   - makeWASocket({ auth: state, printQRInTerminal or pairing code })
 *   - persist auth_state/ via useMultiFileAuthState
 *   - reconnect on DisconnectReason.restartRequired, hard stop on loggedOut
 *
 * TODO(ING-03/ING-05): on `messages.upsert`:
 *   1. Ignore fromMe, groups, status broadcasts.
 *   2. Compute senderHash + phoneTail.
 *   3. checkConsent(...) -- send consent_notice via outboundQueue if pending.
 *   4. handleControlKeyword(...) for BAND/STOP/1/2 -- these never enter the
 *      triage pipeline (docs/TRD.md section 6, step 4).
 *   5. For audio: downloadAndConvert(msg) -> wav path.
 *   6. POST to `${CORE_URL}/internal/ingest` with the payload shape in
 *      docs/TRD.md section 3.1.
 */
async function main() {
  // eslint-disable-next-line no-console
  console.log("Nidaa-AI ingestion daemon -- scaffold only, see TODOs above.");
}

main();

module.exports = { senderHash, phoneTail };
