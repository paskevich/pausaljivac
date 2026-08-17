from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "app.db"
DOCUMENTS_DIR = DATA_DIR / "documents"
SCHEMA_PATH = BASE_DIR / "schema.sql"

DOCUMENT_CATEGORIES = ["resenje", "contract", "other", "invoice", "bank_report"]

PAUSAL_LIMIT_RSD = 6_000_000
VAT_THRESHOLD_RSD = 8_000_000

LIMIT_WARN_RATIO = 0.80
LIMIT_DANGER_RATIO = 0.95

SUPPORTED_CURRENCIES = ["EUR", "USD"]

DEFAULT_TAX_DUE_DAY = 15

# Auto-fetch via kurs.resenje.org — a public JSON API that mirrors the official NBS
# web service ("srednji kurs" / exchange_middle field), no API key required. Not the
# official NBS endpoint itself, but a well-documented, free proxy over it; manual rate
# entry stays available as a fallback if this service is ever down or discontinued.
ENABLE_NBS_AUTO_FETCH = True
NBS_RATE_API_BASE = "https://kurs.resenje.org/api/v1"
NBS_RATE_API_TIMEOUT = 5

SECRET_KEY = "dev-local-only-not-a-real-secret"

MAX_CONTENT_LENGTH = 32 * 1024 * 1024  # 32MB upload cap
