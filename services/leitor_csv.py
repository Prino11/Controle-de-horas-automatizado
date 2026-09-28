"""Importação opcional do formato temporário de quatro marcações."""
import csv
import logging
from pathlib import Path
from models.registro_ponto import RegistroPonto

LOG = logging.getLogger(__name__)
CAMPOS = ("funcionario", "data", "entrada_manha", "saida_manha", "entrada_tarde", "saida_tarde")


def ler_registros_csv(caminho_csv: str | Path) -> list[RegistroPonto]:
    registros = []
    try:
        with Path(caminho_csv).open(encoding="utf-8-sig", newline="") as arquivo:
            leitor = csv.DictReader(arquivo)
            if not set(CAMPOS).issubset(leitor.fieldnames or []):
                LOG.warning("CSV sem as colunas de quatro marcações; importação ignorada")
                return registros
            for numero, linha in enumerate(leitor, 2):
                try:
                    registros.append(RegistroPonto(**{campo: linha[campo] for campo in CAMPOS}))
                except (ValueError, TypeError) as exc:
                    LOG.warning("Linha %s do CSV inválida: %s", numero, type(exc).__name__)
    except (OSError, UnicodeError) as exc:
        LOG.error("Não foi possível ler CSV: %s", type(exc).__name__)
    return registros
