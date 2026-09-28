"""Configuração dos registros persistentes do aplicativo."""
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOGS_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_FILE = LOGS_DIR / "aplicativo.log"
MAX_LOG_BYTES = 2 * 1024 * 1024
BACKUP_COUNT = 5


class _FormatoSeguro(logging.Formatter):
    def format(self, record):
        mensagem = super().format(record)
        chave = os.getenv("GEMINI_API_KEY")
        if chave and len(chave) >= 8:
            mensagem = mensagem.replace(chave, "[CHAVE_OCULTA]")
        return mensagem


def configurar_logs(pasta: Path = LOGS_DIR) -> Path:
    """Grava eventos em arquivo com rotação e também no terminal."""
    raiz = logging.getLogger()
    destino = pasta / LOG_FILE.name
    if any(getattr(handler, "_log_aplicativo", None) == destino for handler in raiz.handlers):
        return destino

    formato = _FormatoSeguro("%(asctime)s %(levelname)-8s [%(threadName)s] %(name)s: %(message)s")
    pasta.mkdir(parents=True, exist_ok=True)
    arquivo = RotatingFileHandler(destino, maxBytes=MAX_LOG_BYTES, backupCount=BACKUP_COUNT, encoding="utf-8")
    arquivo.setFormatter(formato)
    arquivo._log_aplicativo = destino
    raiz.addHandler(arquivo)
    raiz.setLevel(logging.INFO)

    if not any(getattr(handler, "_console_aplicativo", False) for handler in raiz.handlers):
        console = logging.StreamHandler()
        console.setFormatter(formato)
        console._console_aplicativo = True
        raiz.addHandler(console)
    return destino
