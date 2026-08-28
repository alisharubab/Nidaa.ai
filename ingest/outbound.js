// Single outbound reply queue, human-paced. docs/TRD.md section 6.
// Every reply — consent notice, readback, unintelligible fallback, etc. —
// must go through this queue. Never add a second send path: the jittered
// pacing here is the main practical defence against the linked number
// being flagged (docs/PRD.md section 13.4).

const MIN_DELAY_MS = 1500;
const MAX_DELAY_MS = 3000;

class OutboundQueue {
  constructor(sendFn) {
    this.sendFn = sendFn; // (jid, text) => Promise<void>, from the Baileys socket
    this.queue = [];
    this.running = false;
  }

  enqueue(jid, text) {
    this.queue.push({ jid, text });
    this._pump();
  }

  async _pump() {
    if (this.running) return;
    this.running = true;
    while (this.queue.length > 0) {
      const { jid, text } = this.queue.shift();
      await this.sendFn(jid, text);
      const jitter = MIN_DELAY_MS + Math.random() * (MAX_DELAY_MS - MIN_DELAY_MS);
      await new Promise((resolve) => setTimeout(resolve, jitter));
    }
    this.running = false;
  }
}

module.exports = { OutboundQueue };
