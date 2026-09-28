"""Importação independente por página e concorrência limitada sem acesso a widgets."""
import logging
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timezone
from pathlib import Path
from shutil import copy2
from threading import Event
from uuid import uuid4

from PIL import Image, ImageOps
import pymupdf

from config.settings import GEMINI_MAX_RETRIES, GEMINI_MAX_WORKERS, GEMINI_MODEL
from models.lote import PaginaCartao
from services.gemini_service import LeituraIndisponivel, analisar_pagina
from services.image_service import EXTENSOES, _salvar_analise

LOG = logging.getLogger(__name__)


def importar_paginas(caminhos, lado, pasta: Path, cancelar=None):
    """Gera arquivos por página sem acumular bitmaps do lote inteiro na memória."""
    scans, processed = pasta / "scans", pasta / "processed"
    scans.mkdir(parents=True, exist_ok=True)
    processed.mkdir(parents=True, exist_ok=True)
    for caminho in caminhos:
        if cancelar and cancelar.is_set():
            return
        origem = Path(caminho)
        copia = scans / f"{uuid4().hex}{origem.suffix.lower()}"
        try:
            if origem.suffix.lower() not in EXTENSOES:
                raise ValueError("Formato não suportado")
            copy2(origem, copia)
            if origem.suffix.lower() == ".pdf":
                with pymupdf.open(copia) as pdf:
                    if pdf.needs_pass or not len(pdf):
                        raise ValueError("PDF protegido ou vazio")
                    for numero in range(len(pdf)):
                        if cancelar and cancelar.is_set():
                            return
                        pagina = PaginaCartao(arquivo_origem=str(copia), nome_arquivo=origem.name,
                                              pagina_origem=numero + 1, lado_esperado=lado)
                        try:
                            page = pdf[numero]
                            escala = min(3.0, 3200 / max(page.rect.width, page.rect.height))
                            pix = page.get_pixmap(matrix=pymupdf.Matrix(escala, escala), colorspace=pymupdf.csRGB, alpha=False)
                            imagem = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                            _preparar_pagina(pagina, imagem, scans, processed)
                        except Exception:
                            LOG.exception("Erro ao preparar página PDF: id=%s número=%d", pagina.id, numero + 1)
                            pagina.erro = "Não foi possível renderizar esta página"
                        yield pagina
            else:
                pagina = PaginaCartao(arquivo_origem=str(copia), nome_arquivo=origem.name, lado_esperado=lado)
                with Image.open(copia) as imagem:
                    _preparar_pagina(pagina, ImageOps.exif_transpose(imagem).convert("RGB"), scans, processed)
                yield pagina
        except Exception:
            LOG.exception("Erro ao importar arquivo: %s", origem.name)
            yield PaginaCartao(arquivo_origem=str(copia if copia.exists() else origem), nome_arquivo=origem.name,
                               lado_esperado=lado, erro="Arquivo não pôde ser aberto; confira o formato, integridade e senha")


def _preparar_pagina(pagina, imagem, scans, processed):
    original = scans / f"{pagina.id}.png"
    imagem.save(original)
    if imagem.width > 1.5 * imagem.height:
        imagem = imagem.rotate(90, expand=True)
    destino = processed / f"{pagina.id}.png"
    _salvar_analise(imagem, destino)
    pagina.imagem_original, pagina.imagem_processada = str(original), str(destino)


def _ler(pagina, cancelar, analisar, retries):
    pagina = pagina.model_copy(deep=True)
    if not pagina.imagem_processada:
        return pagina
    for tentativa in range(retries + 1):
        try:
            pagina.leitura = analisar(Path(pagina.imagem_processada))
            pagina.revisao_manual = None
            pagina.erro = None
            pagina.modelo_ia = GEMINI_MODEL
            pagina.processado_em = datetime.now(timezone.utc)
            return pagina
        except LeituraIndisponivel as exc:
            pagina.erro = str(exc)
            LOG.warning("Leitura indisponível: página=%s tentativa=%d/%d motivo=%s causa=%s",
                        pagina.id, tentativa + 1, retries + 1, exc,
                        type(exc.__cause__).__name__ if exc.__cause__ else "não informada")
            if not exc.transitorio or tentativa == retries or cancelar.wait(2 ** tentativa):
                break
        except Exception:
            LOG.exception("Falha inesperada na leitura de página: id=%s", pagina.id)
            pagina.erro = "Leitura falhou; revise a página ou tente novamente"
            break
    return pagina


def processar_paginas(paginas, emitir, cancelar=None, analisar=analisar_pagina,
                      max_workers=GEMINI_MAX_WORKERS, retries=GEMINI_MAX_RETRIES):
    cancelar = cancelar or Event()
    emitir("total", len(paginas))
    pendentes = {}
    fonte = iter(paginas)
    esgotado = False
    with ThreadPoolExecutor(max_workers=max(1, max_workers)) as executor:
        while pendentes or not esgotado:
            while len(pendentes) < max(1, max_workers) and not esgotado:
                if cancelar.is_set():
                    esgotado = True
                    break
                pagina = next(fonte, None)
                if pagina is None:
                    esgotado = True
                    break
                pendentes[executor.submit(_ler, pagina, cancelar, analisar, retries)] = pagina.id
            if not pendentes:
                break
            prontos, _ = wait(pendentes, return_when=FIRST_COMPLETED)
            for futuro in prontos:
                pendentes.pop(futuro)
                emitir("resultado", futuro.result())


def processar_importacao(caminhos, lado, pasta, emitir, cancelar):
    paginas = []
    for pagina in importar_paginas(caminhos, lado, pasta, cancelar):
        emitir("pagina", pagina.model_copy(deep=True))
        paginas.append(pagina)
    processar_paginas(paginas, emitir, cancelar)
