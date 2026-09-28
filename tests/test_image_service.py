from PIL import Image
import pytest
from services import image_service
from config.settings import ASSETS_DIR


def test_preserva_original_e_proporcao(tmp_path, monkeypatch):
    monkeypatch.setattr(image_service, "SCANS_DIR", tmp_path / "scans")
    origem = tmp_path / "cartao.png"
    Image.new("RGB", (600, 300), "white").save(origem)
    preparado = image_service.preparar_imagem(origem)
    assert preparado.original.read_bytes() == origem.read_bytes()
    assert preparado.preview.size == (600, 300)
    assert Image.open(preparado.processada).size == (600, 300)


def test_arquivo_invalido(tmp_path):
    ruim = tmp_path / "ruim.png"
    ruim.write_text("x")
    with pytest.raises(ValueError):
        image_service.preparar_imagem(ruim)


def test_pdf_todas_as_paginas(tmp_path):
    import pymupdf
    caminho = tmp_path / "duas_paginas.pdf"
    doc = pymupdf.open()
    doc.new_page(width=300, height=200)
    doc.new_page(width=300, height=200)
    doc.save(caminho)
    doc.close()
    imagem, paginas = image_service.carregar_imagem(caminho)
    assert paginas == 2
    assert imagem.size == (600, 800)


def test_modelos_pdf_frente_verso_sao_orientados_e_preservados(tmp_path, monkeypatch):
    monkeypatch.setattr(image_service, "SCANS_DIR", tmp_path / "scans")
    frente = ASSETS_DIR / "lado_a_cartao.pdf"
    verso = ASSETS_DIR / "Lado B cartão.pdf"
    preparado = image_service.preparar_imagens([frente, verso])
    assert preparado.paginas == 2
    assert preparado.preview.height > preparado.preview.width * 2
    assert [p.read_bytes() for p in preparado.originais] == [frente.read_bytes(), verso.read_bytes()]
    assert preparado.processada.exists()


def test_giro_preserva_original(tmp_path, monkeypatch):
    monkeypatch.setattr(image_service, "SCANS_DIR", tmp_path / "scans")
    origem = tmp_path / "cartao.png"
    Image.new("RGB", (600, 300), "white").save(origem)
    preparado = image_service.preparar_imagem(origem)
    image_service.girar_imagem(preparado, 90)
    assert preparado.preview.size == (300, 600)
    assert preparado.original.read_bytes() == origem.read_bytes()
