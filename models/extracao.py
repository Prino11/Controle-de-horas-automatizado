"""Contrato da resposta estruturada do Gemini."""
from enum import Enum
from pydantic import BaseModel, ConfigDict, Field


class StatusLeitura(str, Enum):
    CONFIRMADO = "CONFIRMADO"
    INCERTO = "INCERTO"
    ILEGIVEL = "ILEGIVEL"
    VAZIO = "VAZIO"


class CampoExtraido(BaseModel):
    model_config = ConfigDict(extra="forbid")
    valor: str | None = None
    status: StatusLeitura
    observacao: str | None = None


class RegistroDiaExtraido(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dia: int
    entrada_manha: CampoExtraido
    saida_manha: CampoExtraido
    entrada_tarde: CampoExtraido
    saida_tarde: CampoExtraido
    observacoes: str | None = None


class CartaoExtraido(BaseModel):
    model_config = ConfigDict(extra="forbid")
    funcionario: str | None = None
    mes: int | None = Field(default=None, ge=1, le=12)
    ano: int | None = Field(default=None, ge=1900, le=2200)
    registros: list[RegistroDiaExtraido]


class TipoLadoCartao(str, Enum):
    LADO_A = "A"
    LADO_B = "B"
    DESCONHECIDO = "DESCONHECIDO"


class CampoNumeroExtraido(BaseModel):
    model_config = ConfigDict(extra="forbid")
    valor: int | None = None
    status: StatusLeitura
    observacao: str | None = None


class LeituraCartao(BaseModel):
    """Uma página, com evidências da face e identificação sem inferência."""
    model_config = ConfigDict(extra="forbid")
    lado: TipoLadoCartao
    numero_lado: int | None = None
    cabecalho_quinzena: str | None = None
    status_lado: StatusLeitura
    matricula: CampoExtraido
    nome: CampoExtraido
    mes: CampoNumeroExtraido
    ano: CampoNumeroExtraido
    registros: list[RegistroDiaExtraido]
