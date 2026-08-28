# Single source of truth for env vars. See docs/TRD.md section 1 for the full list.
# Every other module in core/ imports from here rather than calling os.getenv directly.

import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

STT_MODEL_PRIMARY = os.getenv("STT_MODEL_PRIMARY", "whisper-large-v3-turbo")
STT_MODEL_ESCALATION = os.getenv("STT_MODEL_ESCALATION", "whisper-large-v3")
LLM_MODEL_PRIMARY = os.getenv("LLM_MODEL_PRIMARY", "openai/gpt-oss-120b")
LLM_MODEL_FALLBACK = os.getenv("LLM_MODEL_FALLBACK", "qwen/qwen3.6-27b")

CORE_URL = os.getenv("CORE_URL", "http://127.0.0.1:8000")
INGEST_URL = os.getenv("INGEST_URL", "http://127.0.0.1:3000")

STT_RATE_LIMIT_RPM = int(os.getenv("STT_RATE_LIMIT_RPM", "15"))
LLM_RATE_LIMIT_RPM = int(os.getenv("LLM_RATE_LIMIT_RPM", "25"))
WORKER_CONCURRENCY = int(os.getenv("WORKER_CONCURRENCY", "6"))
AUDIO_TTL_HOURS = int(os.getenv("AUDIO_TTL_HOURS", "72"))

DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"

DB_PATH = os.getenv("DB_PATH", "nidaa.db")
