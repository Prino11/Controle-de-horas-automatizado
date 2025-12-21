from datetime import date, time
from pydantic import BaseModel
from typing import Optional

class RegistroPonto(BaseModel):
    funcionario: str
    data: date
    entrada_manha: Optional[time] = None
    saida_manha: Optional[time] = None
    entrada_tarde: Optional[time] = None
    saida_tarde: Optional[time] = None
