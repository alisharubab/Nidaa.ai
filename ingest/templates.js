// Every outbound Roman Urdu string lives here, and only here. core/ never
// composes user-facing text — it sends a template name + vars via
// POST /internal/reply (docs/TRD.md section 3.2), and this file renders it.
// Optimized for mobile WhatsApp bubble widths (no awkward mid-sentence linebreaks).

function consentNotice() {
  return (
    "🚨 *Nidaa-AI (Rescue Triage Bot)*\n\n" +
    "Ye ek automated rescue triage system hai. Aap ka message AI se process hoga taake rescue team tak jaldi pohnche.\n\n" +
    "• Aap ka message aur voice note process kiya jayega\n" +
    "• Aap ka number sirf rescue team ko dikhega (masked)\n" +
    "• Data 72 ghantay baad delete ho jata hai\n" +
    "• Ye AI hai, insan nahi. Ghalti mumkin hai.\n" +
    "• Rukne ke liye likhein: *BAND*\n\n" +
    "⚠️ Emergency? Rescue *1122* / *1129* par call bhi karein."
  );
}

function readback({ adm2, province, items, urgency }) {
  return (
    "📋 *Nidaa-AI ne ye samjha hai:*\n\n" +
    `📍 *Jagah:* ${adm2}, ${province}\n` +
    `📦 *Zaroorat:* ${items}\n` +
    `⚠️ *Halat:* ${urgency}\n\n` +
    "Sahi hai? Jawab dein:\n" +
    "*1* = Haan, sahi hai\n" +
    "*2* = Nahi, ghalat hai"
  );
}

function readbackAck({ confirmed }) {
  return confirmed
    ? "✅ *Shukriya!* Aap ki report confirm ho chuki hai aur rescue teams tak pohncha di gayi hai."
    : "⚠️ *Noted!* Aap ki report review queue mein bhej di gayi hai taake rescue team dobara check kare.";
}

function audioUnintelligible() {
  return (
    "🔇 *Nidaa-AI: Awaz saaf nahi aa rahi (background shor zyada hai).*\n\n" +
    "Baraye meherbani apna message *TYPE* kar ke bhejein, ya WhatsApp ki *LIVE LOCATION* share karein.\n\n" +
    "Zaroori maloomat: Jagah, kitne log, aur kya madad chahiye."
  );
}

function locationMissing() {
  return (
    "📍 *Nidaa-AI: Jagah samajh nahi aayi.*\n\n" +
    "Baraye meherbani WhatsApp par *LIVE LOCATION* share karein, ya jagah ka naam type kar ke bhejein."
  );
}

const TEMPLATES = {
  consent_notice: consentNotice,
  readback,
  readback_ack: readbackAck,
  audio_unintelligible: audioUnintelligible,
  location_missing: locationMissing,
};

function render(templateName, vars = {}) {
  const fn = TEMPLATES[templateName];
  if (!fn) throw new Error(`Unknown reply template: ${templateName}`);
  return fn(vars);
}

module.exports = { render, TEMPLATES };
