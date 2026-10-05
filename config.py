import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _int(name, default):
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return int(default)


def _float(name, default):
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return float(default)


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-library-secret-change-me")
    DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
    DB_PORT = _int("DB_PORT", "3306")
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_NAME = os.getenv("DB_NAME", "library_db")
    # Single source for late-return charges. Change FINE_PER_DAY in .env.
    FINE_PER_DAY = _float("FINE_PER_DAY", "5")
    LOAN_DAYS = _int("LOAN_DAYS", "14")
    ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
    PORT = _int("PORT", "5000")
