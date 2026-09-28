import json
from datetime import date
from pydantic import ValidationError
import pytest

from models.cartao_ponto import CartaoConferido
from models.extracao import CartaoExtraido
from models.registro_ponto import RegistroPonto
from services.storage_service import salvar_cartao


def test_registro_aceita_vazio():
    registro = RegistroPonto(data=date(2026, 1, 1), entrada_manha="")
    assert registro.entrada_manha is None


def test_extracao_e_preservacao(tmp_path):
    vazio = {"valor": None, "status": "VAZIO"}
    bruto = {"funcionario": "Ana", "mes": 1, "ano": 2026, "registros": [
        {"dia": 1, "entrada_manha": {"valor": "08:00", "status": "INCERTO"},
         "saida_manha": vazio, "entrada_tarde": vazio, "saida_tarde": vazio,
         "observacoes": "EXTRA: 18:00"}]}
    extraido = CartaoExtraido.model_validate(bruto)
    cartao = CartaoConferido.da_extracao("scan.png", "modelo", extraido)
    campo = cartao.registros[0].entrada_manha
    campo.valor_confirmado = "08:15"
    campo.foi_editado = True
    destino = salvar_cartao(cartao, tmp_path)
    salvo = json.loads(destino.read_text(encoding="utf-8"))
    assert salvo["extracao_original"]["registros"][0]["entrada_manha"]["valor"] == "08:00"
    assert salvo["registros"][0]["entrada_manha"]["valor_confirmado"] == "08:15"
    assert salvo["registros"][0]["observacoes_confirmadas"] == "EXTRA: 18:00"
    assert salvo["status_revisao"] == "CONFIRMADO"


def test_schema_rejeita_status_desconhecido():
    with pytest.raises(ValidationError):
        CartaoExtraido.model_validate({"registros": [{"dia": 1, "entrada_manha": {"status": "TALVEZ"}}]})
