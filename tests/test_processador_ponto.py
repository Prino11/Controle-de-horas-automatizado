from datetime import date
import pytest
from models.registro_ponto import RegistroPonto
from services.processador_ponto import calcular_total_horas, calcular_total_texto, converter_horario


@pytest.mark.parametrize("horas,esperado", [
    (("08:00", "12:00", "13:00", "17:00"), 8.0),
    (("08:30", "12:00", "13:00", "17:30"), 8.0),
    (("08:00", "12:00", None, None), 4.0),
    (("08:00", None, "13:00", "17:00"), 4.0),
])
def test_total(horas, esperado):
    registro = RegistroPonto(data=date(2026, 1, 1), entrada_manha=horas[0],
                            saida_manha=horas[1], entrada_tarde=horas[2], saida_tarde=horas[3])
    assert calcular_total_horas(registro) == esperado


@pytest.mark.parametrize("valor", ["25:90", "12:70", "abc", "8h30", "0800", "8:00"])
def test_horario_invalido(valor):
    with pytest.raises(ValueError):
        converter_horario(valor)


def test_vazio_e_saida_anterior():
    assert converter_horario(None) is None
    assert converter_horario("") is None
    with pytest.raises(ValueError):
        calcular_total_texto({"entrada_manha": "08:00", "saida_manha": "07:00"})
