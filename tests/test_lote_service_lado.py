import pytest

from models.extracao import (
    CampoExtraido,
    CampoNumeroExtraido,
    LeituraCartao,
    StatusLeitura,
    TipoLadoCartao,
)
from services.lote_service import detectar_lado


def _leitura(numero, cabecalho, lado, status):
    vazio = CampoExtraido(valor=None, status=StatusLeitura.VAZIO)
    numero_vazio = CampoNumeroExtraido(valor=None, status=StatusLeitura.VAZIO)
    return LeituraCartao(
        lado=lado,
        numero_lado=numero,
        cabecalho_quinzena=cabecalho,
        status_lado=status,
        matricula=vazio,
        nome=vazio,
        mes=numero_vazio,
        ano=numero_vazio,
        registros=[],
    )


@pytest.mark.parametrize(
    "numero,cabecalho,lado,status,esperado",
    [
        (1, "2ª QUINZENA", TipoLadoCartao.LADO_B, StatusLeitura.CONFIRMADO, TipoLadoCartao.LADO_A),
        (2, "1ª QUINZENA", TipoLadoCartao.LADO_A, StatusLeitura.CONFIRMADO, TipoLadoCartao.LADO_B),
        (None, "1ª QUINZENA", TipoLadoCartao.LADO_A, StatusLeitura.CONFIRMADO, TipoLadoCartao.DESCONHECIDO),
        (1, "1ª QUINZENA", TipoLadoCartao.LADO_A, StatusLeitura.INCERTO, TipoLadoCartao.DESCONHECIDO),
    ],
)
def test_numero_estampado_define_lado(numero, cabecalho, lado, status, esperado):
    assert detectar_lado(_leitura(numero, cabecalho, lado, status)) == esperado
