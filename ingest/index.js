// Entry point + transport-agnostic inbound handler.
//
// Transports live in ./transports/ (whatsapp.js, telegram.js). Each one
// normalizes inbound messages into { endpointId, messageId, text, voice } and
// calls onInbound(); each exposes sendText() + downloadVoice(). Everything
// transport-independent — consent gate, control keywords, the
// POST /internal/ingest contract, the jittered outbound queue, the
// /internal/reply server — lives here, so switching INGEST_TRANSPORT never
// changes pipeline behaviour.
// docs/TRD.md section 6 (inbound handler), sections 3.1/3.2 (contracts).

require("dotenv").config({ path: require("path").join(__dirname, "..", ".env") });
const crypto = require("crypto");
const http = require("http");
const fs = require("fs");

const { checkConsent, handleControlKeyword } = require("./consent");
const { OutboundQueue } = require("./outbound");
const { render } = require("./templates");

const CORE_URL = process.env.CORE_URL || "http://127.0.0.1:8000";
const INGEST_URL = process.env.INGEST_URL || "http://127.0.0.1:3000";
const SENDER_HASH_SALT = process.env.SENDER_HASH_SALT || "nidaa-default-salt";
const TRANSPORT = (process.env.INGEST_TRANSPORT || "whatsapp").toLowerCase();

function senderHash(endpointId) {
  return "sha256:" + crypto
    .createHash("sha256")
    .update(endpointId + SENDER_HASH_SALT)
    .digest("hex");
}

function phoneTail(endpointId) {
  const digits = String(endpointId).replace(/\D/g, "");
  return digits.slice(-3);
}

// --- Active transport + single outbound queue --------------------------------

let activeTransport = null;
let outboundQueue = null;

// sender_hash -> endpointId (WhatsApp JID or Telegram chat id). Populated on
// every inbound message so the /internal/reply server can route core-initiated
// replies (readback, fallbacks) back to the right chat on the right transport.
const endpointMap = new Map();

async function sendViaTransport(endpointId, text) {
  // The transport is assigned right after transport.start() resolves; the
  // brief wait guards the startup race if a message lands first.
  for (let i = 0; i < 20 && !activeTransport; i++) {
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  if (!activeTransport) throw new Error("no transport ready");
  return activeTransport.sendText(endpointId, text);
}

// --- Shared inbound handler (TRD section 6 steps 2-6) ------------------------

async function handleInbound({ endpointId, messageId, text, voice }) {
  // Step 2: sender hash + phone tail
  const sHash = senderHash(endpointId);
  const tail = phoneTail(endpointId);
  endpointMap.set(sHash, endpointId);

  // Step 3: consent gate — first contact fires the notice exactly once
  const consent = await checkConsent(sHash, tail);
  if (consent.state === "revoked") return; // drop silently
  if (consent.sendNotice) {
    outboundQueue.enqueue(endpointId, render("consent_notice"));
  }

  // Step 4: control keywords (BAND/STOP); 1/2 route to readback in ING-10
  if (text) {
    const handled = await handleControlKeyword(sHash, text);
    if (handled) return;
  }

  // Step 5: audio download + convert (transport-specific), else plain text
  const modality = voice ? "audio" : "text";
  let audioPath = null;
  let audioDurationS = null;

  if (voice) {
    try {
      const result = await activeTransport.downloadVoice(voice);
      audioPath = result.path;
      audioDurationS = result.duration;
    } catch (err) {
      console.error("[ingest] voice download/convert failed:", err.message);
      return; // cannot process without the file
    }
  }

  // Step 6: POST /internal/ingest (TRD section 3.1)
  //
  // audio_data_b64/audio_filename addendum (post-v1.0.0, added for Render
  // deploy): ingest/ and core/ run as separate Render services with
  // separate disks, so a bare `audio_path` string from ingest's filesystem
  // means nothing to core's pipeline (preflight/stt read the file by path).
  // Sending the bytes alongside the path lets core save its own copy under
  // its own storage/audio/ and rewrite audio_path to that local copy --
  // same behaviour locally (one code path for both topologies), just an
  // extra harmless round-trip when ingest/core happen to share a disk.
  let audioDataB64 = null;
  let audioFilename = null;
  if (audioPath) {
    try {
      audioDataB64 = fs.readFileSync(audioPath).toString("base64");
      audioFilename = require("path").basename(audioPath);
    } catch (err) {
      console.error(`[ingest] could not read ${audioPath} to forward to core:`, err.message);
    }
  }

  const payload = {
    wa_message_id: messageId,
    sender_hash: sHash,
    phone_tail: tail,
    modality,
    audio_path: audioPath,
    audio_data_b64: audioDataB64,
    audio_filename: audioFilename,
    audio_duration_s: audioDurationS,
    text: text || null,
    received_at: new Date().toISOString(),
  };

  try {
    const res = await fetch(`${CORE_URL}/internal/ingest`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      console.error(`[ingest] POST /internal/ingest failed: ${res.status} ${await res.text()}`);
    } else {
      const result = await res.json();
      console.log(
        `[ingest] ${modality} message ${messageId} -> message_id ${result.message_id}, queue_depth ${result.queue_depth}`
      );
    }
  } catch (err) {
    console.error(`[ingest] POST /internal/ingest error: ${err.message}`);
  }
}

// --- /internal/reply server (TRD section 3.2) ---------------------------------
// core/ tells us a template name + vars; we compose the text (templates.js)
// and enqueue through the single jittered queue. Never a second send path.

function startReplyServer() {
  const server = http.createServer(async (req, res) => {
    // GET /health: real health check, and doubles as a keepalive target for
    // an external pinger (e.g. UptimeRobot/cron-job.org) on Render's free
    // tier -- Render spins a free web service down after 15 minutes with no
    // *inbound* traffic, and this service's own outbound Green API polling
    // loop doesn't count as inbound, so without something pinging it, the
    // WhatsApp bridge silently stops receiving messages. Upgrading to a paid
    // instance type removes the spin-down entirely; see README's deployment
    // section for both options.
    if (req.method === "GET" && req.url === "/health") {
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ status: "ok", transport: TRANSPORT }));
      return;
    }
    if (req.method !== "POST" || req.url !== "/internal/reply") {
      res.writeHead(404);
      res.end();
      return;
    }
    let body = "";
    req.on("data", (chunk) => (body += chunk));
    req.on("end", async () => {
      try {
        const { sender_hash, template, vars } = JSON.parse(body);
        const endpointId = endpointMap.get(sender_hash);
        if (!endpointId) {
          console.error(`[reply] no endpoint mapped for ${sender_hash}`);
          res.writeHead(404);
          res.end(JSON.stringify({ error: "endpoint not found" }));
          return;
        }
        outboundQueue.enqueue(endpointId, render(template, vars || {}));
        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ ok: true }));
      } catch (err) {
        console.error("[reply] failed:", err.message);
        res.writeHead(500);
        res.end(JSON.stringify({ error: err.message }));
      }
    });
  });
  // Render (and most PaaS hosts) assign the listen port dynamically via
  // $PORT and route their own public HTTPS URL to it -- INGEST_URL's own
  // port (or the 3000 default) only applies to plain local/VM dev where
  // nothing else picks the port for us.
  const port = process.env.PORT || new URL(INGEST_URL).port || 3000;
  server.listen(port, () => {
    console.log(`[ingest] reply server listening on port ${port}`);
  });
}

// --- Entry point --------------------------------------------------------------

async function main() {
  console.log(`[ingest] Nidaa-AI ingestion daemon starting (transport: ${TRANSPORT})`);
  startReplyServer();
  outboundQueue = new OutboundQueue(sendViaTransport);

  let transportModule;
  try {
    transportModule = require(`./transports/${TRANSPORT}`);
  } catch (err) {
    console.error(
      `[ingest] cannot load transport "${TRANSPORT}" (expected whatsapp|telegram): ${err.message}`
    );
    process.exit(1);
  }

  activeTransport = await transportModule.start({ onInbound: handleInbound });
  console.log(`[ingest] transport "${activeTransport.name || TRANSPORT}" active`);
}

main().catch((err) => {
  console.error("[ingest] Fatal:", err);
  process.exit(1);
});

module.exports = { senderHash, phoneTail };
