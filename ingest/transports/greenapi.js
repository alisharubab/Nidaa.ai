// Green API WhatsApp transport — HTTP API polling, no public endpoint needed.
//
// Green API exposes a managed WhatsApp Web gateway: QR code scan once in their
// console (console.green-api.com) links the account; messages are then
// available via a simple ReceiveNotification / DeleteNotification poll loop.
//
// API reference: https://green-api.com/en/docs/api/receiving/technology-http-api/
//
// Used as the primary dev/test transport when direct Baileys pairing is not
// available. Switch back to Baileys with INGEST_TRANSPORT=whatsapp.
// docs/ARCHITECTURE.md section 4 (transport adapters).

const fs   = require("fs");
const path = require("path");
const { convertToWav, STORAGE_DIR } = require("../media");

const ID_INSTANCE    = process.env.GREEN_API_ID_INSTANCE    || "";
const API_TOKEN      = process.env.GREEN_API_TOKEN          || "";
const API_URL        = `https://api.green-api.com/waInstance${ID_INSTANCE}`;
const POLL_DELAY_MS  = 1000;  // delay between empty-queue polls
const RETRY_DELAY_MS = 3000;  // backoff on network / API errors

// --- HTTP helpers ------------------------------------------------------------

async function ga(method, endpoint, body = null) {
  const url  = `${API_URL}/${endpoint}/${API_TOKEN}`;
  const opts = { method };
  if (body) {
    opts.headers = { "Content-Type": "application/json" };
    opts.body    = JSON.stringify(body);
  }
  const res = await fetch(url, opts);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`green-api ${method} ${endpoint} ${res.status}: ${text}`);
  }
  // Green API returns an empty body (not JSON) when the notification queue
  // is empty — guard against JSON parse failure.
  const text = await res.text();
  if (!text || text.trim() === "") return null;
  return JSON.parse(text);
}

// deleteNotification uses a different URL shape:
//   DELETE /waInstance{id}/deleteNotification/{token}/{receiptId}
// (token before receiptId, unlike all other methods where token is last)
async function gaDelete(receiptId) {
  const url = `${API_URL}/deleteNotification/${API_TOKEN}/${receiptId}`;
  const res = await fetch(url, { method: "DELETE" });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`green-api DELETE deleteNotification ${res.status}: ${text}`);
  }
  return null;
}

// --- Incoming message normaliser ---------------------------------------------

/**
 * Parse one ReceiveNotification body into { endpointId, messageId, text, voice }
 * or null if the notification type / message type is not handled.
 */
function parseNotification(notif) {
  const body = notif.body;
  if (!body) return null;

  // Only handle incoming messages; ignore outgoing acks, status changes, calls
  if (body.typeWebhook !== "incomingMessageReceived") return null;

  const chatId = body.senderData?.chatId || "";

  // Groups end in @g.us — skip. TRD section 6 step 1: direct messages only.
  if (chatId.endsWith("@g.us")) return null;

  // endpointId = bare phone number (strip @c.us suffix)
  const endpointId = chatId.replace(/@c\.us$/, "");
  const messageId  = `ga-${endpointId}-${body.idMessage}`;
  const msgData    = body.messageData || {};
  const type       = msgData.typeMessage;

  if (type === "textMessage") {
    const text = msgData.textMessageData?.textMessage || null;
    if (!text) return null;
    return { endpointId, messageId, text, voice: null };
  }

  if (type === "audioMessage") {
    const url      = msgData.fileMessageData?.downloadUrl || null;
    const mimeType = msgData.fileMessageData?.mimeType    || "audio/ogg";
    if (!url) return null;
    return {
      endpointId,
      messageId,
      text:  null,
      voice: { handle: url, mimeType, duration: null },
    };
  }

  // Other types (image, video, sticker, document, location...) — out of scope
  return null;
}

// --- Audio download ----------------------------------------------------------

async function downloadVoice(voice) {
  // voice.handle is the direct download URL from the notification
  const res = await fetch(voice.handle);
  if (!res.ok) throw new Error(`green-api file download ${res.status}: ${voice.handle}`);
  const buffer = Buffer.from(await res.arrayBuffer());

  // Determine extension from mimeType (ogg / mpga / mp4 / etc.)
  const ext     = (voice.mimeType || "audio/ogg").split("/")[1]?.split(";")[0] || "ogg";
  const tmpName = `ga_${Date.now()}_${Math.random().toString(36).slice(2)}`;
  const tmpPath = path.join(STORAGE_DIR, `${tmpName}.${ext}`);
  const wavPath = path.join(STORAGE_DIR, `${tmpName}.wav`);

  fs.writeFileSync(tmpPath, buffer);
  try {
    await convertToWav(tmpPath, wavPath);
  } finally {
    try { fs.unlinkSync(tmpPath); } catch (_) { /* ignore */ }
  }

  return { path: wavPath, duration: voice.duration };
}

// --- Transport entry point ---------------------------------------------------

async function start({ onInbound }) {
  if (!ID_INSTANCE || !API_TOKEN) {
    throw new Error(
      "GREEN_API_ID_INSTANCE and GREEN_API_TOKEN must be set in .env\n" +
      "Get them from console.green-api.com after scanning the QR code."
    );
  }

  console.log(`[greenapi] starting poll loop for instance ${ID_INSTANCE}`);

  // Poll loop runs detached; start() returns the transport interface immediately.
  (async function pollLoop() {
    while (true) {
      try {
        // ReceiveNotification returns { receiptId, body } or null/empty on timeout
        const notif = await ga("GET", "receiveNotification");

        if (!notif || !notif.receiptId) {
          // Empty queue — wait briefly before next poll
          await new Promise((r) => setTimeout(r, POLL_DELAY_MS));
          continue;
        }

        const receiptId = notif.receiptId;

        // Parse and dispatch — errors in the handler must not block DeleteNotification
        try {
          const msg = parseNotification(notif);
          if (msg) await onInbound(msg);
        } catch (err) {
          console.error("[greenapi] handler error:", err.message);
        }

        // Always delete to advance the queue, even if the handler failed
        try {
          await gaDelete(receiptId);
        } catch (err) {
          console.error("[greenapi] deleteNotification failed:", err.message);
        }

      } catch (err) {
        console.error("[greenapi] poll error:", err.message);
        await new Promise((r) => setTimeout(r, RETRY_DELAY_MS));
      }
    }
  })();

  return {
    name: "greenapi",
    sendText: async (endpointId, text) => {
      // chatId must include @c.us suffix for the sendMessage endpoint
      const chatId = endpointId.includes("@") ? endpointId : `${endpointId}@c.us`;
      await ga("POST", "sendMessage", { chatId, message: text });
    },
    downloadVoice,
  };
}

module.exports = { start };
