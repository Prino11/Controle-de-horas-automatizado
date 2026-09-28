"""Validação independente de IA, sem corrigir valores silenciosamente."""
import calendar
from dataclasses import dataclass

from models.cartao_ponto import CAMPOS_HORARIO, CartaoConferido, DiaConferido
from models.extracao import CartaoExtraido
from services.processador_ponto import converter_horario


@dataclass(frozen=True)
class Problema:
    dia: int | None
    campo: str
    mensagem: str


def validar_dia(registro: DiaConferido) -> list[Problema]:
    problemas = []
    horarios = {}
    for nome in CAMPOS_HORARIO:
        valor = getattr(registro, nome).valor_confirmado
        try:
            horarios[nome] = converter_horario(valor)
        except ValueError as exc:
            problemas.append(Problema(registro.dia, nome, str(exc)))
            horarios[nome] = None
    for entrada, saida in (("entrada_manha", "saida_manha"), ("entrada_tarde", "saida_tarde")):
        a, b = horarios[entrada], horarios[saida]
        if (a is None) != (b is None):
            problemas.append(Problema(registro.dia, entrada if a is not None else saida,
                                      "Período incompleto"))
        elif a is not None and b is not None and b < a:
            problemas.append(Problema(registro.dia, saida, "Saída anterior à entrada"))
    if horarios["saida_manha"] and horarios["entrada_tarde"]:
        if horarios["entrada_tarde"] < horarios["saida_manha"]:
            problemas.append(Problema(registro.dia, "entrada_tarde", "Tarde começa antes do fim da manhã"))
    return problemas


def validar_cartao(cartao: CartaoConferido) -> list[Problema]:
    problemas = []
    if not cartao.funcionario_confirmado.strip():
        problemas.append(Problema(None, "funcionario", "Informe o funcionário"))
    try:
        dias_mes = calendar.monthrange(cartao.ano_confirmado, cartao.mes_confirmado)[1]
    except (TypeError, ValueError):
        problemas.append(Problema(None, "mes", "Informe mês e ano válidos"))
        dias_mes = 0
    vistos = set()
    for dia in cartao.registros:
        if dia.dia in vistos:
            problemas.append(Problema(dia.dia, "dia", "Dia duplicado"))
        vistos.add(dia.dia)
        if not 1 <= dia.dia <= dias_mes:
            problemas.append(Problema(dia.dia, "dia", "Dia inválido para o mês"))
        problemas.extend(validar_dia(dia))
    return problemas


def validar_extracao(extracao: CartaoExtraido) -> list[Problema]:
    cartao = CartaoConferido.da_extracao("", "", extracao)
    return validar_cartao(cartao)
