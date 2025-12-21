from datetime import datetime, timedelta

def calcular_total_horas(registro):
    total = timedelta()

    if registro.entrada_manha and registro.saida_manha:
        total += (
            datetime.combine(registro.data, registro.saida_manha)
            - datetime.combine(registro.data, registro.entrada_manha)
        )

    if registro.entrada_tarde and registro.saida_tarde:
        total += (
            datetime.combine(registro.data, registro.saida_tarde)
            - datetime.combine(registro.data, registro.entrada_tarde)
        )

    return round(total.total_seconds() / 3600, 2)
