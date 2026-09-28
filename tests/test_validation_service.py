from models.cartao_ponto import CartaoConferido, DiaConferido, CampoConferido
from services.validation_service import validar_cartao, validar_dia


def campo(valor):
    return CampoConferido(valor_confirmado=valor)


def test_incompleto_e_saida_anterior():
    dia = DiaConferido(dia=1, entrada_manha=campo("08:00"),
                       entrada_tarde=campo("13:00"), saida_tarde=campo("12:00"))
    mensagens = [p.mensagem for p in validar_dia(dia)]
    assert "Período incompleto" in mensagens
    assert "Saída anterior à entrada" in mensagens


def test_dia_invalido_duplicado_e_horario_invalido():
    cartao = CartaoConferido(arquivo_origem="x", funcionario_confirmado="Pessoa",
                             mes_confirmado=2, ano_confirmado=2025,
                             registros=[DiaConferido(dia=29, entrada_manha=campo("25:90")),
                                        DiaConferido(dia=29)])
    mensagens = [p.mensagem for p in validar_cartao(cartao)]
    assert "Dia inválido para o mês" in mensagens
    assert "Dia duplicado" in mensagens
    assert any("Horário fora" in m for m in mensagens)
