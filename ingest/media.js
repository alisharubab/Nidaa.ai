// Media download + conversion. docs/TRD.md section 6, step 5.
// Downloads inbound audio via Baileys, converts to 16kHz mono PCM WAV
// (small payload, Whisper-friendly), writes to storage/audio/.

const { spawn } = require("child_process");
const path = require("path");

const STORAGE_DIR = path.join(__dirname, "..", "storage", "audio");

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

module.exports = { convertToWav, STORAGE_DIR };
