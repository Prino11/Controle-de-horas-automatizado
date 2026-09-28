"""Persistência local com substituição atômica."""
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from config.settings import PROCESSED_DIR
from models.cartao_ponto import CartaoConferido


def salvar_cartao(cartao: CartaoConferido, pasta: Path = PROCESSED_DIR) -> Path:
    pasta.mkdir(parents=True, exist_ok=True)
    cartao.status_revisao = "CONFIRMADO"
    cartao.data_confirmacao = datetime.now(timezone.utc)
    destino = pasta / f"{cartao.id_cartao}.json"
    temporario = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=pasta,
                                         prefix=".cartao_", suffix=".tmp", delete=False) as arquivo:
            temporario = Path(arquivo.name)
            arquivo.write(cartao.model_dump_json(indent=2))
            arquivo.flush()
            os.fsync(arquivo.fileno())
        os.replace(temporario, destino)
    finally:
        if temporario and temporario.exists():
            temporario.unlink()
    return destino
