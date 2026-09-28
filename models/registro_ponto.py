"""Registro confirmado, independente da origem dos horários."""
from datetime import date, time
from pydantic import BaseModel, field_validator


class RegistroPonto(BaseModel):
    funcionario: str = ""
    data: date
    entrada_manha: time | None = None
    saida_manha: time | None = None
    entrada_tarde: time | None = None
    saida_tarde: time | None = None

    @field_validator("entrada_manha", "saida_manha", "entrada_tarde", "saida_tarde", mode="before")
    @classmethod
    def normalizar_vazio(cls, valor):
        return None if valor == "" else valor
