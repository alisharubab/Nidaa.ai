// Every outbound Roman Urdu string lives here, and only here. core/ never
// composes user-facing text — it sends a template name + vars via
// POST /internal/reply (docs/TRD.md section 3.2), and this file renders it.
// Exact copy from docs/PRD.md sections 3.1, 3.2, and 6.

function consentNotice() {
  return (
    "Nidaa-AI (Rescue Triage Bot)\n\n" +
    "Ye ek automated rescue triage system hai. Aap ka message AI\n" +
    "se process hoga taake rescue team tak jaldi pohnche.\n\n" +
    "• Aap ka message aur voice note process kiya jayega\n" +
    "• Aap ka number sirf rescue team ko dikhega (masked)\n" +
    "• Data 72 ghantay baad delete ho jata hai\n" +
    "• Ye AI hai, insan nahi. Ghalti mumkin hai.\n" +
    "• Rukne ke liye likhein: BAND\n\n" +
    "Emergency? Rescue 1122 / 1129 par call bhi karein."
  );
}

function readback({ adm2, province, items, urgency }) {
  return (
    "Nidaa-AI ne ye samjha hai:\n\n" +
    `Jagah: ${adm2}, ${province}\n` +
    `Zaroorat: ${items}\n` +
    `Halat: ${urgency}\n\n` +
    "Sahi hai? Jawab dein:\n" +
    "1 = Haan, sahi hai\n" +
    "2 = Nahi, ghalat hai"
  );
}

function audioUnintelligible() {
  return (
    "Nidaa-AI: Awaz saaf nahi aa rahi (background shor bohat zyada hai).\n" +
    "Baraye meherbani apna message TYPE kar ke bhejein, ya WhatsApp\n" +
    "ki LIVE LOCATION bhejein. Rescue team ko itni maloomat chahiye:\n" +
    "jagah, kitne log, kya chahiye."
  );
}

function locationMissing() {
  // TODO(ING-08): confirm final copy with the team — PRD does not give an
  // exact string for this template, only the requirement (docs/PRD.md
  // section 3.3 / docs/TRD.md GEOCODE_NO_MATCH row). Keep tone consistent
  // with the other templates above.
  return (
    "Nidaa-AI: Jagah samajh nahi aayi. Baraye meherbani WhatsApp ki\n" +
    "LIVE LOCATION share karein, ya jagah ka naam type karein."
  );
}

const TEMPLATES = {
  consent_notice: consentNotice,
  readback,
  audio_unintelligible: audioUnintelligible,
  location_missing: locationMissing,
};

function render(templateName, vars = {}) {
  const fn = TEMPLATES[templateName];
  if (!fn) throw new Error(`Unknown reply template: ${templateName}`);
  return fn(vars);
}

module.exports = { render, TEMPLATES };
