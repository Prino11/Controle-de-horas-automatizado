"""Guarda o scan original e produz uma cópia legível para análise."""
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from shutil import copy2
from typing import Sequence
from uuid import uuid4

from PIL import Image, ImageEnhance, ImageOps, UnidentifiedImageError
from config.settings import SCANS_DIR

EXTENSOES = {".png", ".jpg", ".jpeg", ".pdf"}


@dataclass
class ImagemPreparada:
    original: Path
    originais: list[Path]
    processada: Path
    preview: Image.Image
    paginas: int = 1


def carregar_imagem(caminho: Path) -> tuple[Image.Image, int]:
    if caminho.suffix.lower() == ".pdf":
        try:
            import pymupdf
        except ImportError as exc:
            raise ValueError("Suporte a PDF indisponível. Instale PyMuPDF.") from exc
        with pymupdf.open(caminho) as doc:
            if len(doc) == 0:
                raise ValueError("PDF sem páginas")
            if len(doc) > 4:
                raise ValueError("Selecione um PDF de até quatro páginas")
            paginas = []
            for page in doc:
                pix = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
                with Image.open(BytesIO(pix.tobytes("png"))) as img:
                    paginas.append(img.convert("RGB"))
            largura = max(img.width for img in paginas)
            altura = sum(img.height for img in paginas)
            if largura * altura > 40_000_000:
                raise ValueError("PDF grande demais para análise local")
            combinado = Image.new("RGB", (largura, altura), "white")
            y = 0
            for img in paginas:
                combinado.paste(img, (0, y))
                y += img.height
            return combinado, len(doc)
    with Image.open(caminho) as img:
        return ImageOps.exif_transpose(img).convert("RGB"), 1


def preparar_imagem(caminho: str | Path) -> ImagemPreparada:
    return preparar_imagens([caminho])


def preparar_imagens(caminhos: Sequence[str | Path]) -> ImagemPreparada:
    """Agrupa frente e verso sem alterar os arquivos fornecidos."""
    if not 1 <= len(caminhos) <= 2:
        raise ValueError("Selecione um ou dois arquivos do mesmo cartão")
    origens = [Path(caminho).resolve() for caminho in caminhos]
    if any(p.suffix.lower() not in EXTENSOES or not p.is_file() for p in origens):
        raise ValueError("Selecione arquivos PNG, JPG, JPEG ou PDF existentes")
    imagens = []
    paginas = 0
    for origem in origens:
        try:
            imagem, quantidade = carregar_imagem(origem)
        except (OSError, UnidentifiedImageError, ValueError) as exc:
            raise ValueError(f"Não foi possível abrir {origem.name}") from exc
        # Os cartões do projeto foram escaneados deitados. A regra também vale
        # para scans do mesmo formato; o usuário pode ajustar o giro na tela.
        if origem.suffix.lower() == ".pdf" and imagem.width > imagem.height * 1.5:
            imagem = imagem.rotate(90, expand=True)
        imagens.append(imagem)
        paginas += quantidade
    largura = max(imagem.width for imagem in imagens)
    altura = sum(imagem.height for imagem in imagens)
    if largura * altura > 40_000_000:
        raise ValueError("Imagens grandes demais para análise local")
    preview = Image.new("RGB", (largura, altura), "white")
    y = 0
    for imagem in imagens:
        preview.paste(imagem, ((largura - imagem.width) // 2, y))
        y += imagem.height
    SCANS_DIR.mkdir(parents=True, exist_ok=True)
    destinos = []
    for origem in origens:
        destino = SCANS_DIR / f"{uuid4().hex}{origem.suffix.lower()}"
        copy2(origem, destino)
        destinos.append(destino)
    processada = SCANS_DIR / f"{destinos[0].stem}_processada.png"
    _salvar_analise(preview, processada)
    return ImagemPreparada(destinos[0], destinos, processada, preview, paginas)


def _salvar_analise(preview: Image.Image, processada: Path) -> None:
    analise = preview.copy()
    analise.thumbnail((2400, 3200), Image.Resampling.LANCZOS)
    analise = ImageEnhance.Contrast(analise).enhance(1.15)
    analise.save(processada, optimize=True)


def girar_imagem(preparada: ImagemPreparada, graus: int) -> None:
    """Gira apenas o preview e a cópia de análise; o scan original é intocado."""
    preparada.preview = preparada.preview.rotate(graus, expand=True)
    _salvar_analise(preparada.preview, preparada.processada)
