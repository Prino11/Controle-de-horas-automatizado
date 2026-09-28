"""Estado persistente do lote, incluindo páginas ainda sem funcionário."""
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4
from pydantic import BaseModel, Field
from models.cartao_ponto import CartaoConferido
from models.extracao import LeituraCartao, TipoLadoCartao


class StatusCartao(str, Enum):
    AGUARDANDO_LADO_B = "AGUARDANDO_LADO_B"
    COMPLETO = "COMPLETO"
    REVISAO_NECESSARIA = "REVISAO_NECESSARIA"
    PAREAMENTO_PENDENTE = "PAREAMENTO_PENDENTE"
    CONFIRMADO = "CONFIRMADO"
    ERRO_LEITURA = "ERRO_LEITURA"


class PaginaCartao(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    arquivo_origem: str
    nome_arquivo: str = ""
    pagina_origem: int = 1
    imagem_original: str = ""
    imagem_processada: str = ""
    lado_esperado: TipoLadoCartao
    leitura: LeituraCartao | None = None
    revisao_manual: LeituraCartao | None = None
    status: str = "AGUARDANDO_LEITURA"
    erro: str | None = None
    ignorada: bool = False
    lado_aceito_manualmente: bool = False
    associar_a: str | None = None
    pareamento_manual: bool = False
    alertas: list[str] = Field(default_factory=list)
    modelo_ia: str | None = None
    processado_em: datetime | None = None

    @property
    def resultado(self) -> LeituraCartao | None:
        return self.revisao_manual or self.leitura


class CartaoMensalFuncionario(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    nome: str = ""
    matricula: str | None = None
    mes: int
    ano: int
    lado_a: str
    lado_b: str | None = None
    pareamento_manual: bool = False
    status: StatusCartao = StatusCartao.AGUARDANDO_LADO_B
    alertas: list[str] = Field(default_factory=list)
    assinatura_fontes: str = ""
    conferencia: CartaoConferido
    identificacao_revisada: bool = False


class LoteCartoes(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    mes: int = Field(ge=1, le=12)
    ano: int = Field(ge=1900, le=2200)
    criado_em: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    atualizado_em: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "EM_ANDAMENTO"
    paginas: dict[str, PaginaCartao] = Field(default_factory=dict)
    funcionarios: list[CartaoMensalFuncionario] = Field(default_factory=list)
