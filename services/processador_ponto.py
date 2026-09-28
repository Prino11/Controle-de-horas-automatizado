"""Conversão e cálculo de jornada; a interface não calcula horas."""
from datetime import datetime, time, timedelta
import re
from models.registro_ponto import RegistroPonto


def converter_horario(valor: str | time | None) -> time | None:
    if valor is None or valor == "":
        return None
    if isinstance(valor, time):
        return valor
    if not isinstance(valor, str) or not re.fullmatch(r"\d{2}:\d{2}", valor):
        raise ValueError("Use o formato HH:MM")
    try:
        return datetime.strptime(valor, "%H:%M").time()
    except ValueError as exc:
        raise ValueError("Horário fora do intervalo 00:00–23:59") from exc


def duracao_periodo(inicio: str | time | None, fim: str | time | None) -> timedelta:
    entrada, saida = converter_horario(inicio), converter_horario(fim)
    if entrada is None or saida is None:
        return timedelta()
    if saida < entrada:
        raise ValueError("Saída anterior à entrada")
    return datetime.combine(datetime.min.date(), saida) - datetime.combine(datetime.min.date(), entrada)


def calcular_total_horas(registro: RegistroPonto) -> float:
    total = duracao_periodo(registro.entrada_manha, registro.saida_manha)
    total += duracao_periodo(registro.entrada_tarde, registro.saida_tarde)
    return round(total.total_seconds() / 3600, 2)


def formatar_duracao(total: timedelta) -> str:
    minutos = int(total.total_seconds() // 60)
    return f"{minutos // 60:02d}:{minutos % 60:02d}"


def calcular_total_texto(valores: dict[str, str | None]) -> str:
    total = duracao_periodo(valores.get("entrada_manha"), valores.get("saida_manha"))
    total += duracao_periodo(valores.get("entrada_tarde"), valores.get("saida_tarde"))
    return formatar_duracao(total)
