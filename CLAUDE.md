# Nidaa-AI — project instructions

Read this before touching any code. It's the condensed, non-negotiable subset of [docs/PRD.md](docs/PRD.md), [docs/TRD.md](docs/TRD.md), and [docs/UI-UX-REQUIREMENTS.md](docs/UI-UX-REQUIREMENTS.md) — the rules that must survive no matter which person, session, or AI assistant is doing the work. When in doubt, the full docs are the source of truth; this file exists so you don't have to re-read all three every time to avoid breaking something.

**Also read:** [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for module boundaries, [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) for the task breakdown, [PROGRESS.md](PROGRESS.md) for current state. If you're working inside `dashboard/`, also read `dashboard/CLAUDE.md` — its rules are scoped and stricter.

---

## What this project is

A 6-day MVP that turns a WhatsApp voice note in code-switched Urdu into a structured, HXL-tagged, map-pinned relief ticket, with a measured median Time-to-Triage under 5 seconds. Three independent runtimes — `ingest/` (Node/Baileys), `core/` (Python/FastAPI), `dashboard/` (static JS) — that only ever talk to each other over the HTTP contract in TRD §3. See docs/ARCHITECTURE.md before assuming you can import across those boundaries — you can't.

## Hard rules — never violate these regardless of what task you're doing

1. **The DB schema (TRD §2) and API contract (TRD §3) are frozen.** Do not rename a field, change a route shape, or add a new cross-module call without updating `docs/TRD.md` in the same change and flagging it to the human explicitly. Silent contract drift is the one thing that breaks the other person's in-flight work.
2. **No cross-imports between `ingest/`, `core/`, and `dashboard/`.** They talk over HTTP only. If you find yourself wanting to `require()` or `import` across those directory boundaries, stop — that's a sign the contract is missing something, not a shortcut to take.
3. **The LLM extraction step must never emit latitude, longitude, or a P-code.** Coordinates come only from `core/pipeline/geocode.py`'s deterministic offline cascade (alias → exact → fuzzy ≥85 → none). If geocoding can't resolve a location, the correct output is `NULL` coordinates routed to the Unlocated queue — never a guessed or inferred coordinate, ever, from any code path.
4. **A transcript that fails the STT confidence gate twice must never reach the extraction LLM.** Set `status=audio_unintelligible` and stop. Feeding low-confidence audio to an LLM produces confident, fabricated tickets — the single worst failure mode this system can have.
5. **Consent is not optional and not decorative.** First-contact notice fires exactly once per sender. `BAND`/`STOP` immediately revokes and purges that sender's stored audio and transcript. Never send a message to a number that hasn't messaged first, and never send outside the single jittered outbound queue in `ingest/outbound.js` (1.5–3.0s pacing) — a second send path is how the linked number gets banned.
6. **All outbound Groq calls acquire from the token buckets in `core/queue.py`.** Don't add a call site that bypasses rate limiting — the buckets are deliberately tuned below the free-tier ceiling on purpose (TRD §4.1).
7. **Phone numbers are stored as a SHA-256 hash + last 3 digits only.** Never log, store, or display a full phone number anywhere, including in debug output.
8. **Never report an accuracy or confidence number without its sample size attached.** The gold set is 25 messages. That's enough to demonstrate a pipeline, not enough to claim a production rate (PRD §13) — say so every time the number comes up.
9. **The dashboard has no build step.** Don't introduce a bundler, framework, or npm dependency graph into `dashboard/` — it must keep loading from `file://` with zero install. See `dashboard/CLAUDE.md`.
10. **Update [PROGRESS.md](PROGRESS.md)** when a task is actually done end-to-end — not when the code compiles, when it's tested. Reference the task ID (`CORE-07`, `ING-04`, etc.) from `docs/IMPLEMENTATION_PLAN.md` in commits where it's useful.

## Working conventions

* Python 3.11, type hints on function signatures in `core/`. Node 20+ in `ingest/`, CommonJS (matches the existing `require`/`module.exports` style already in the scaffold — don't switch to ESM mid-project).
* Don't add abstractions, config flags, or generalized helpers beyond what the current task needs — this is a 6-day scope-controlled build, not a platform.
* Every pipeline stage in `core/pipeline/` is a function of its inputs to its outputs — it doesn't reach into `db.py` itself. `main.py`'s worker loop is the only orchestrator.
* Before assuming a Groq model ID is current, check the note in `docs/TRD.md` §1 — the free-tier lineup moves and has already deprecated models once mid-project.
