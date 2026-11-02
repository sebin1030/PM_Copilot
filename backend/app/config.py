from pathlib import Path
import os

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")

DATA_DIR = Path(os.getenv("PM_COPILOT_DATA_DIR", ROOT_DIR / "data")).resolve()
PROJECTS_DIR = DATA_DIR / "projects"
UPLOAD_LIMIT_BYTES = 10 * 1024 * 1024

# Set both values to switch from the local development store to Supabase.
SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_PUBLISHABLE_KEY = os.getenv("SUPABASE_PUBLISHABLE_KEY", "")
ALLOWED_ORIGINS = [
    origin.strip() for origin in os.getenv(
        "PM_COPILOT_ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",") if origin.strip()
]


def supabase_enabled() -> bool:
    return bool(SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY)

CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-5.6-luna")
DOCUMENT_MODEL = os.getenv("OPENAI_DOCUMENT_MODEL", "gpt-5.6-terra")

AVAILABLE_MODELS = [
    {"id": "gpt-5.6-luna", "label": "GPT-5.6 Luna", "use": "빠른 대화·분류"},
    {"id": "gpt-5.6-terra", "label": "GPT-5.6 Terra", "use": "균형 잡힌 문서 생성"},
    {"id": "gpt-5.6-sol", "label": "GPT-5.6 Sol", "use": "복잡한 분석·최종 검수"},
]

