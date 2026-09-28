"""Estado de conferência; a leitura original permanece intacta."""
from datetime import datetime, timezone
from uuid import uuid4
from pydantic import BaseModel, Field
from models.extracao import CartaoExtraido, StatusLeitura

CAMPOS_HORARIO = ("entrada_manha", "saida_manha", "entrada_tarde", "saida_tarde")


class CampoConferido(BaseModel):
    valor_extraido: str | None = None
    valor_reanalise: str | None = None
    valor_confirmado: str | None = None
    status_leitura: StatusLeitura = StatusLeitura.VAZIO
    observacao: str | None = None
    foi_editado: bool = False


class DiaConferido(BaseModel):
    dia: int
    dia_extraido: int | None = None
    origem_lado: str | None = None
    origem_pagina: str | None = None
    observacoes_extraidas: str | None = None
    observacoes_confirmadas: str | None = None
    entrada_manha: CampoConferido = Field(default_factory=CampoConferido)
    saida_manha: CampoConferido = Field(default_factory=CampoConferido)
    entrada_tarde: CampoConferido = Field(default_factory=CampoConferido)
    saida_tarde: CampoConferido = Field(default_factory=CampoConferido)


class CartaoConferido(BaseModel):
    id_cartao: str = Field(default_factory=lambda: uuid4().hex)
    arquivo_origem: str
    arquivos_origem: list[str] = Field(default_factory=list)
    data_processamento: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    data_confirmacao: datetime | None = None
    modelo_ia: str | None = None
    status_revisao: str = "PENDENTE"
    extracao_original: CartaoExtraido | None = None
    funcionario_extraido: str | None = None
    funcionario_confirmado: str = ""
    mes_extraido: int | None = None
    mes_confirmado: int | None = None
    ano_extraido: int | None = None
    ano_confirmado: int | None = None
    registros: list[DiaConferido] = Field(default_factory=list)

    @classmethod
    def da_extracao(cls, origem: str, modelo: str, extracao: CartaoExtraido):
        dias = []
        for registro in extracao.registros:
            campos = {}
            for nome in CAMPOS_HORARIO:
                campo = getattr(registro, nome)
                campos[nome] = CampoConferido(valor_extraido=campo.valor, valor_confirmado=campo.valor,
                                              status_leitura=campo.status, observacao=campo.observacao)
            dias.append(DiaConferido(dia=registro.dia, observacoes_extraidas=registro.observacoes,
                                     observacoes_confirmadas=registro.observacoes, **campos))
        return cls(arquivo_origem=origem, modelo_ia=modelo, extracao_original=extracao,
                   funcionario_extraido=extracao.funcionario, funcionario_confirmado=extracao.funcionario or "",
                   mes_extraido=extracao.mes, mes_confirmado=extracao.mes,
                   ano_extraido=extracao.ano, ano_confirmado=extracao.ano, registros=dias)
