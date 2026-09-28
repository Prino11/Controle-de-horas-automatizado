"""Um lote por competência; gravação atômica de rascunhos e confirmações."""
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from config.settings import LOTES_DIR
from models.lote import LoteCartoes


def pasta_lote(lote, raiz: Path = LOTES_DIR):
    return raiz / f"{lote.ano:04d}-{lote.mes:02d}"


def salvar_lote(lote: LoteCartoes, pasta: Path):
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / "lote.json"
    lote.atualizado_em = datetime.now(timezone.utc)
    temporario = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=pasta,
                                         prefix=".lote_", suffix=".tmp", delete=False) as arquivo:
            temporario = Path(arquivo.name)
            arquivo.write(lote.model_dump_json(indent=2))
            arquivo.flush()
            os.fsync(arquivo.fileno())
        os.replace(temporario, destino)
    finally:
        if temporario and temporario.exists():
            temporario.unlink()
    return destino


def carregar_lote(caminho: Path) -> LoteCartoes:
    return LoteCartoes.model_validate_json(caminho.read_text(encoding="utf-8"))
