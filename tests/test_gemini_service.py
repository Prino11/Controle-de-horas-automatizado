from types import SimpleNamespace
import pytest
from services.gemini_service import LeituraIndisponivel, analisar_cartao


def test_cliente_injetado_recebe_imagem_e_schema(tmp_path):
    imagem = tmp_path / "scan.png"
    imagem.write_bytes(b"imagem de teste")
    chamadas = []

    def gerar(**kwargs):
        chamadas.append(kwargs)
        return SimpleNamespace(text='{"funcionario":"Ana","mes":1,"ano":2026,"registros":[]}')

    cliente = SimpleNamespace(models=SimpleNamespace(generate_content=gerar))
    resultado = analisar_cartao(imagem, ["dia 1 entrada_manha"], client=cliente)
    assert resultado.funcionario == "Ana"
    assert chamadas[0]["contents"][0].inline_data.data == imagem.read_bytes()
    assert "dia 1 entrada_manha" in chamadas[0]["contents"][1]
    assert chamadas[0]["config"].response_mime_type == "application/json"


def test_resposta_invalida_nao_vaza_detalhes(tmp_path):
    imagem = tmp_path / "scan.png"
    imagem.write_bytes(b"x")
    cliente = SimpleNamespace(models=SimpleNamespace(generate_content=lambda **kwargs: SimpleNamespace(text="errado")))
    with pytest.raises(LeituraIndisponivel):
        analisar_cartao(imagem, client=cliente)
