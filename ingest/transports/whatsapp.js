// Baileys (WhatsApp) transport — the primary, demo-path transport.
// Extracted from index.js into the transports/ adapter pattern: this module
// only owns WhatsApp-specific concerns (socket, pairing, message filtering,
// media download). Everything transport-independent lives in index.js.
// docs/TRD.md section 6 (inbound handler steps), docs/ARCHITECTURE.md section 4.

const {
  default: makeWASocket,
  useMultiFileAuthState,
  DisconnectReason,
  downloadMediaMessage,
  Browsers,
} = require("@whiskeysockets/baileys");
const fs = require("fs");
const path = require("path");
const { convertToWav, STORAGE_DIR } = require("../media");

const PAIRING_PHONE = process.env.PAIRING_PHONE_NUMBER || "";
const AUTH_STATE_DIR = path.join(__dirname, "..", "auth_state");

// Module-level so the sendText closure always targets the live socket after
// a reconnect swaps it.
let sock = null;

async function downloadVoice(voice) {
  // voice.handle is the raw Baileys message object
  const buffer = await downloadMediaMessage(voice.handle, "buffer", {});
  const tmpName = `wa_${Date.now()}_${Math.random().toString(36).slice(2)}`;
  const tmpPath = path.join(STORAGE_DIR, `${tmpName}_raw`);
  const wavPath = path.join(STORAGE_DIR, `${tmpName}.wav`);
  fs.writeFileSync(tmpPath, buffer);
  try {
    await convertToWav(tmpPath, wavPath);
  } finally {
    try { fs.unlinkSync(tmpPath); } catch (_) { /* ignore */ }
  }
  return { path: wavPath, duration: voice.duration };
}

// TRD section 6 step 1: ignore fromMe, groups, status broadcasts — then
// normalize into the shared inbound shape.
async function handleRaw(raw, onInbound) {
  if (raw.key.fromMe) return;
  const remoteJid = raw.key.remoteJid || "";
  if (remoteJid.endsWith("@g.us")) return;
  if (remoteJid === "status@broadcast") return;

  const text =
    raw.message?.conversation ||
    raw.message?.extendedTextMessage?.text ||
    null;
  const audio = raw.message?.audioMessage || null;

  await onInbound({
    endpointId: remoteJid,
    messageId: raw.key.id || `wa-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    text,
    voice: audio ? { handle: raw, duration: audio.seconds ?? null } : null,
  });
}

async function start({ onInbound }) {
  const connect = async () => {
    const { state, saveCreds } = await useMultiFileAuthState(AUTH_STATE_DIR);

    // pairingCode: true tells Baileys to use the pairing-code flow instead
    // of the QR code flow. Must be set at construction time, not later.
    const needsPairing = !state.creds.registered;
    sock = makeWASocket({
      auth: state,
      browser: Browsers.windows("Nidaa-AI"),
      printQRInTerminal: false,
    });

    sock.ev.on("creds.update", saveCreds);

    // Request the pairing code immediately after socket creation, before
    // any connection events. This is the correct Baileys v6 timing —
    // requestPairingCode must be called while the socket is still in the
    // handshake phase. Calling it from isNewLogin (which fires AFTER
    // pairing succeeds) is too late and causes "QR refs attempts ended".
    if (needsPairing) {
      if (!PAIRING_PHONE) {
        console.error(
          "[whatsapp] no saved auth_state and PAIRING_PHONE_NUMBER not set in .env\n" +
          "Set PAIRING_PHONE_NUMBER (country code + number, digits only, e.g. 923001234567)"
        );
        process.exit(1);
      }
      // Small delay so the WebSocket handshake completes before we send
      // the pairing-code IQ stanza — Baileys needs the noise session up.
      await new Promise((resolve) => setTimeout(resolve, 3000));
      try {
        const code = await sock.requestPairingCode(PAIRING_PHONE);
        console.log(`\n  Pairing code: ${code}`);
        console.log("  On your phone: WhatsApp → ⋮ → Linked Devices → Link a Device");
        console.log("  Tap 'Link with phone number instead' → enter this 8-digit code\n");
      } catch (err) {
        console.error("[whatsapp] pairing code request failed:", err.message);
        // Reconnect loop will retry
      }
    }

    sock.ev.on("connection.update", async (update) => {
      const { connection, lastDisconnect } = update;

      if (connection === "open") {
        console.log("[whatsapp] connected and ready.");
      }

      if (connection === "close") {
        const reason = lastDisconnect?.error?.output?.statusCode;
        if (reason === DisconnectReason.loggedOut) {
          console.error("[whatsapp] logged out — hard stop, re-pair required.");
          process.exit(1);
        }
        console.log(`[whatsapp] connection closed (code ${reason}), reconnecting...`);
        setTimeout(connect, 3000);
      }
    });

    sock.ev.on("messages.upsert", async ({ messages, type }) => {
      if (type !== "notify") return;
      for (const raw of messages) {
        try {
          await handleRaw(raw, onInbound);
        } catch (err) {
          console.error("[whatsapp] handler error:", err);
        }
      }
    });
  };

  await connect();

  return {
    name: "whatsapp",
    sendText: (jid, text) => sock.sendMessage(jid, { text }),
    downloadVoice,
  };
}

module.exports = { start };
