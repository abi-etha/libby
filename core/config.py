"""
config.py — Environment-aware configuration.
On Railway (or any server): reads from environment variables.
Locally: uses sensible temp-dir defaults.
"""

import os
import tempfile
from pathlib import Path

# ── Base dir is the deploy root (parent of core/) ─────────
BASE_DIR = Path(__file__).parent.parent

# ── Paths: env vars on Railway, tmp defaults locally ──────
_tmp = Path(tempfile.gettempdir())

WATCH_FOLDER  = Path(os.environ.get("WATCH_FOLDER",  str(BASE_DIR / "incoming")))
OUTPUT_FOLDER = Path(os.environ.get("OUTPUT_FOLDER", str(_tmp / "libby_output")))
LOG_FOLDER    = Path(os.environ.get("LOG_FOLDER",    str(_tmp / "libby_logs")))
PREFIX        = os.environ.get("PREFIX", "CLIENT")
EXTENSIONS    = {".pdf"}
IGNORE_PREFIXES = ["AUTO_", "CLIENT_", "AMEX_", "CHASE_", "ATT_", "SPECTRUM_", "UFCU_"]

# ── Vendors CSV lives next to app.py in the deploy ────────
VENDORS_CSV = Path(os.environ.get("VENDORS_CSV", str(BASE_DIR / "vendors.csv")))

# ── API key — set LIBBY_API_KEY in Railway env vars ───────
API_KEY = os.environ.get("LIBBY_API_KEY", "")

# ── Ensure output dirs exist ───────────────────────────────
OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)
LOG_FOLDER.mkdir(parents=True, exist_ok=True)
