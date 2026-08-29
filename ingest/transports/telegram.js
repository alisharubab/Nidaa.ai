// Telegram Bot API transport — long polling, no public endpoint needed.
//
// This is a DEV/TEST transport so the full ingestion path (consent gate,
// voice download, POST /internal/ingest) can be exercised before the WhatsApp
// burner SIM is paired. The hackathon demo remains WhatsApp (Baileys) +
// DEMO_MODE simulator; switch back with INGEST_TRANSPORT=whatsapp.
//
// Shares the single jittered outbound queue and every inbound rule with
// WhatsApp, so pacing and consent semantics apply here too.
// docs/ARCHITECTURE.md section 4 (transport adapters).

const fs = require("fs");
const path = require("path");
const { convertToWav, STORAGE_DIR } = require("../media");

const TELEGRAM_TOKEN = process.env.TELEGRAM_BOT_TOKEN || "";
const POLL_TIMEOUT_S = 30; // hold the getUpdates connection open
const RETRY_DELAY_MS = 3000; // backoff on poll errors (incl. 429)

async function tg(method, params = {}) {
  const res = await fetch(`https://api.telegram.org/bot${TELEGRAM_TOKEN}/${method}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`telegram ${method} ${res.status}: ${body}`);
  }
  return res.json();
}

async function handleUpdate(upd, onInbound) {
  const msg = upd.message;
  if (!msg) return;

  // TRD section 6 step 1: direct messages only, no groups/channels
  if (msg.chat.type !== "private") return;
  // Bot commands (/start, /help...) never enter the triage pipeline
  if (msg.text && msg.text.startsWith("/")) return;

  const text = msg.text || null;
  const voice = msg.voice || null; // in-chat voice note (ogg/opus)
  if (!text && !voice) return; // stickers, photos, documents: out of scope

  await onInbound({
    endpointId: String(msg.chat.id),
    messageId: `tg-${msg.chat.id}-${msg.message_id}`,
    text,
    voice: voice ? { handle: voice.file_id, duration: voice.duration ?? null } : null,
  });
}

async function start({ onInbound }) {
  if (!TELEGRAM_TOKEN) {
    throw new Error("TELEGRAM_BOT_TOKEN not set in .env");
  }

  // Defensive: clear any webhook registered in earlier experiments so
  // getUpdates is allowed to run. Fails softly if none was set.
  try { await tg("deleteWebhook"); } catch (err) {
    console.warn("[telegram] deleteWebhook:", err.message);
  }

  const me = await tg("getMe");
  console.log(`[telegram] polling as @${me.result.username}`);

  // Skip messages queued before daemon start (sent while the bot sat idle)
  // and start listening from "now".
  let offset = 0;
  try {
    const last = await tg("getUpdates", { offset: -1, limit: 1 });
    if (last.result && last.result.length > 0) {
      offset = last.result[0].update_id + 1;
    }
  } catch (_) { /* empty queue is fine */ }

  const downloadVoice = async (voice) => {
    // voice.handle is the Telegram file_id
    const info = await tg("getFile", { file_id: voice.handle });
    const fileRes = await fetch(
      `https://api.telegram.org/file/bot${TELEGRAM_TOKEN}/${info.result.file_path}`
    );
    if (!fileRes.ok) throw new Error(`telegram file download ${fileRes.status}`);
    const buffer = Buffer.from(await fileRes.arrayBuffer());

    const tmpName = `tg_${Date.now()}_${Math.random().toString(36).slice(2)}`;
    const tmpPath = path.join(STORAGE_DIR, `${tmpName}.ogg`);
    const wavPath = path.join(STORAGE_DIR, `${tmpName}.wav`);
    fs.writeFileSync(tmpPath, buffer);
    try {
      await convertToWav(tmpPath, wavPath);
    } finally {
      try { fs.unlinkSync(tmpPath); } catch (_) { /* ignore */ }
    }
    return { path: wavPath, duration: voice.duration };
  };

  // Poll loop runs detached; start() returns the transport interface first.
  (async function pollLoop() {
    while (true) {
      try {
        const data = await tg("getUpdates", {
          offset,
          timeout: POLL_TIMEOUT_S,
          allowed_updates: ["message"],
        });
        for (const upd of data.result || []) {
          offset = upd.update_id + 1;
          try {
            await handleUpdate(upd, onInbound);
          } catch (err) {
            console.error("[telegram] handler error:", err.message);
          }
        }
      } catch (err) {
        console.error("[telegram] poll error:", err.message);
        await new Promise((resolve) => setTimeout(resolve, RETRY_DELAY_MS));
      }
    }
  })();

  return {
    name: "telegram",
    sendText: async (chatId, text) => {
      await tg("sendMessage", { chat_id: chatId, text });
    },
    downloadVoice,
  };
}

module.exports = { start };
