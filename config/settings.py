"""Caminhos e configuração local."""
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = BASE_DIR / "assets"
load_dotenv(BASE_DIR / ".env")
SCANS_DIR = BASE_DIR / "input" / "scans"
PROCESSED_DIR = BASE_DIR / "data" / "processed"
LOTES_DIR = BASE_DIR / "data" / "lotes"
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


def _inteiro_ambiente(nome: str, padrao: int, minimo: int, maximo: int) -> int:
    try:
        return max(minimo, min(maximo, int(os.getenv(nome, str(padrao)))))
    except ValueError:
        return padrao


GEMINI_MAX_WORKERS = _inteiro_ambiente("GEMINI_MAX_WORKERS", 2, 1, 4)
GEMINI_MAX_RETRIES = _inteiro_ambiente("GEMINI_MAX_RETRIES", 1, 0, 3)


def gemini_api_key() -> str | None:
    return os.getenv("GEMINI_API_KEY") or None
