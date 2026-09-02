import os
import sys
from pathlib import Path

FROZEN = getattr(sys, "frozen", False)


def _packaged_user_data_dir():
    """Where a packaged (PyInstaller) build keeps its data. Never the
    bundle's own extraction dir (sys._MEIPASS/the .exe's folder) — on
    macOS that's inside the read-only .app bundle, and PyInstaller's
    onefile mode re-extracts to a fresh temp dir on every launch, so
    anything written there is lost the moment the app closes."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or str(Path.home())
        return Path(base) / "Pausaljivac"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Pausaljivac"
    return Path.home() / ".local" / "share" / "pausaljivac"


BASE_DIR = Path(__file__).resolve().parent
# PyInstaller extracts bundled data files (schema.sql, templates/, static/)
# under sys._MEIPASS at runtime; that's read-only reference data, fine to
# read from there, but never a place to write persistent data (see above).
BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", BASE_DIR))

DATA_DIR = _packaged_user_data_dir() if FROZEN else BASE_DIR / "data"
DB_PATH = DATA_DIR / "app.db"
DOCUMENTS_DIR = DATA_DIR / "documents"
SCHEMA_PATH = BUNDLE_DIR / "schema.sql"
SIGNATURE_PATH = DATA_DIR / "signature.png"
TMP_DIR = DATA_DIR / "tmp"
LOG_DIR = DATA_DIR / "logs"
LOG_PATH = LOG_DIR / "app.log"
BANK_PACKAGE_DIR = DATA_DIR / "bank_packages"

DOCUMENT_CATEGORIES = ["resenje", "contract", "other", "invoice", "bank_report"]

PAUSAL_LIMIT_RSD = 6_000_000
VAT_THRESHOLD_RSD = 8_000_000

LIMIT_WARN_RATIO = 0.80
LIMIT_DANGER_RATIO = 0.95

SUPPORTED_CURRENCIES = ["EUR", "USD", "RSD"]

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
