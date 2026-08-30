# Async queue + token-bucket rate limiting. See docs/TRD.md section 4.1.
# Two independent buckets (STT, LLM) tuned BELOW Groq's free-tier ceilings.
# Every outbound Groq call — anywhere in core/ — must acquire from one of
# these buckets first. Do not add a second call site that bypasses this.

import asyncio
import random
import time

import groq

import db
from config import STT_RATE_LIMIT_RPM, LLM_RATE_LIMIT_RPM, WORKER_CONCURRENCY

RETRY_MAX_ATTEMPTS = 3
RETRY_BASE_DELAY_S = 1.0


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
        immediately, then restore it to the full configured rate after
        `seconds`. If called again before the restore fires (repeated
        429s), it halves again from the already-reduced rate -- each call
        schedules its own restore-to-full, which is safe even if more than
        one is pending (restoring to `capacity` twice is a no-op the
        second time)."""
        self.refill_rpm = max(self.refill_rpm / 2.0, 1.0)

        async def _restore():
            await asyncio.sleep(seconds)
            self.refill_rpm = self.capacity

        asyncio.create_task(_restore())


stt_bucket = TokenBucket(STT_RATE_LIMIT_RPM)
llm_bucket = TokenBucket(LLM_RATE_LIMIT_RPM)


async def call_with_retry(bucket: TokenBucket, fn, *args, **kwargs):
    """Acquires a token from `bucket`, then runs the blocking `fn` in a
    thread (the Groq SDK is synchronous -- calling it directly from an
    async worker would block every other worker on this event loop, not
    just the one waiting on it). On a transient Groq API failure, retries
    with exponential backoff + jitter, max RETRY_MAX_ATTEMPTS total
    (docs/TRD.md 4.1). A 429 specifically halves the bucket's refill rate
    for 60s before the next attempt.

    Deliberately does NOT catch non-Groq exceptions (e.g.
    pipeline.extract.ExtractionValidationError) -- those are business-logic
    failures, not transient API failures, and retrying the identical call
    won't fix a model that returned bad JSON. The caller decides what to do
    with those (e.g. switch to the fallback model), this function only
    owns "is the Groq API itself being flaky right now."
    """
    last_exc = None
    for attempt in range(1, RETRY_MAX_ATTEMPTS + 1):
        await bucket.acquire()
        try:
            return await asyncio.to_thread(fn, *args, **kwargs)
        except groq.RateLimitError as e:
            last_exc = e
            bucket.halve_refill_for(60.0)
        except groq.APIError as e:
            last_exc = e
        if attempt < RETRY_MAX_ATTEMPTS:
            delay = RETRY_BASE_DELAY_S * (2 ** (attempt - 1)) + random.uniform(0, 0.5)
            await asyncio.sleep(delay)
    raise last_exc


class PipelineQueue:
    """asyncio.Queue-backed worker pool. Each worker pulls one message id
    and hands it to `handler` (main.py's async pipeline orchestrator --
    this class stays generic and doesn't know about db.py's tables or the
    pipeline stages themselves, per ../CLAUDE.md's "main.py's worker loop
    is the only orchestrator")."""

    def __init__(self, handler, concurrency: int = WORKER_CONCURRENCY):
        self.handler = handler
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
                await self.handler(message_id)
            except Exception as e:
                # A single bad message must never permanently kill a
                # worker (that would silently shrink WORKER_CONCURRENCY
                # over time) or leave the message stuck at whatever status
                # it happened to be at when the unexpected error hit --
                # TRD section 9: "there are no silent failures."
                print(f"[pipeline_queue] message {message_id} failed unexpectedly: {e!r}", flush=True)
                try:
                    with db.get_connection() as conn:
                        db.update_message_status(conn, message_id, "failed", error_code="PIPELINE_ERROR")
                except Exception as inner:
                    print(f"[pipeline_queue] also failed to record the failure for {message_id}: {inner!r}", flush=True)
            finally:
                self.depth -= 1
                self.queue.task_done()

    def start(self):
        return [asyncio.create_task(self.worker_loop()) for _ in range(self.concurrency)]
