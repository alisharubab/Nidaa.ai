// Media download + conversion. docs/TRD.md section 6, step 5.
// Downloads inbound audio via Baileys, converts to 16kHz mono PCM WAV
// (small payload, Whisper-friendly), writes to storage/audio/.

const { spawn } = require("child_process");
const path = require("path");

const STORAGE_DIR = path.join(__dirname, "..", "storage", "audio");

/**
 * TODO(ING-04):
 *   1. downloadMediaMessage(msg, ...) from Baileys -> raw buffer.
 *   2. Write raw buffer to a temp file.
 *   3. ffmpeg -i <temp> -ar 16000 -ac 1 -c:a pcm_s16le <STORAGE_DIR>/<id>.wav
 *   4. Return the final wav path for the /internal/ingest payload.
 */
async function downloadAndConvert(msg) {
  throw new Error("not implemented");
}

function convertToWav(inputPath, outputPath) {
  return new Promise((resolve, reject) => {
    const ff = spawn("ffmpeg", [
      "-y",
      "-i", inputPath,
      "-ar", "16000",
      "-ac", "1",
      "-c:a", "pcm_s16le",
      outputPath,
    ]);
    ff.on("error", reject);
    ff.on("close", (code) => (code === 0 ? resolve(outputPath) : reject(new Error(`ffmpeg exited ${code}`))));
  });
}

module.exports = { downloadAndConvert, convertToWav, STORAGE_DIR };
