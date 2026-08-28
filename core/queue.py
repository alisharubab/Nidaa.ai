# Async queue + token-bucket rate limiting. See docs/TRD.md section 4.1.
# Two independent buckets (STT, LLM) tuned BELOW Groq's free-tier ceilings.
# Every outbound Groq call — anywhere in core/ — must acquire from one of
# these buckets first. Do not add a second call site that bypasses this.

import asyncio
import time

from config import STT_RATE_LIMIT_RPM, LLM_RATE_LIMIT_RPM, WORKER_CONCURRENCY


class TokenBucket:
    """Simple RPM-based token bucket. acquire() awaits until a token is
    available rather than dropping the request (docs/TRD.md 4.1: "Nothing
    is dropped, only delayed")."""

    def __init__(self, rpm: int):
        self.capacity = rpm
        self.tokens = float(rpm)
        self.refill_rpm = float(rpm)
        self.updated_at = time.monotonic()
        self._lock = asyncio.Lock()

    def _refill(self):
        now = time.monotonic()
        elapsed_minutes = (now - self.updated_at) / 60.0
        self.tokens = min(self.capacity, self.tokens + elapsed_minutes * self.refill_rpm)
        self.updated_at = now

    async def acquire(self):
        while True:
            async with self._lock:
                self._refill()
                if self.tokens >= 1:
                    self.tokens -= 1
                    return
            await asyncio.sleep(60.0 / max(self.refill_rpm, 1))

    def halve_refill_for(self, seconds: float = 60.0):
        """Call on a 429 response (docs/TRD.md 4.1): halve the refill rate
        for `seconds`, then restore it."""
        # TODO(CORE-12): implement the temporary halving + restore timer.
        raise NotImplementedError


stt_bucket = TokenBucket(STT_RATE_LIMIT_RPM)
llm_bucket = TokenBucket(LLM_RATE_LIMIT_RPM)


class PipelineQueue:
    """asyncio.Queue-backed worker pool. Each worker pulls one message,
    runs it through pipeline/preflight -> stt -> extract -> geocode ->
    urgency -> dedupe in order, and writes results via db.py + events.py."""

    def __init__(self, concurrency: int = WORKER_CONCURRENCY):
        self.queue: asyncio.Queue = asyncio.Queue()
        self.concurrency = concurrency
        self.depth = 0

    async def put(self, message_id: int):
        self.depth += 1
        await self.queue.put(message_id)

    async def worker_loop(self):
        while True:
            message_id = await self.queue.get()
            try:
                # TODO(CORE-09 / CORE-11): run the pipeline stages for
                # message_id here, acquiring stt_bucket / llm_bucket before
                # each external call.
                pass
            finally:
                self.depth -= 1
                self.queue.task_done()

    def start(self):
        return [asyncio.create_task(self.worker_loop()) for _ in range(self.concurrency)]
