"""Testes de pdf_service: escolha de imagem candidata por página (embutida vs.
rasterizada), filtros que descartam logos/assinaturas/carimbos, e tratamento
de PDF corrompido ou protegido por senha.
"""

import io
from pathlib import Path

import pymupdf
import pytest
from PIL import Image

from backend.services import pdf_service
from backend.services.pdf_service import OrigemTipo, PdfCorrompidoError, PdfProtegidoError


def _pagina_com_imagens(tmp_path: Path, imagens: list[Image.Image], modo_1_bit: bool = False) -> Path:
    """Cria um PDF de uma página com as imagens dadas embutidas lado a lado."""
    documento = pymupdf.open()
    pagina = documento.new_page(width=595, height=842)

    x = 20
    for imagem in imagens:
        buffer = io.BytesIO()
        (imagem.convert("1") if modo_1_bit else imagem).save(buffer, format="PNG")
        retangulo = pymupdf.Rect(x, 20, x + 100, 120)
        pagina.insert_image(retangulo, stream=buffer.getvalue())
        x += 120

    caminho = tmp_path / "documento.pdf"
    documento.save(caminho)
    documento.close()
    return caminho


def _pagina_sem_imagens(tmp_path: Path, nome: str = "documento.pdf") -> Path:
    """Cria um PDF de uma página só com texto — simula a página escaneada (sem imagem embutida útil)."""
    documento = pymupdf.open()
    pagina = documento.new_page(width=595, height=842)
    pagina.insert_text((50, 50), "conteúdo escaneado sem imagem embutida")
    caminho = tmp_path / nome
    documento.save(caminho)
    documento.close()
    return caminho


def test_abrir_levanta_pdf_corrompido_para_arquivo_invalido(tmp_path: Path):
    caminho = tmp_path / "corrompido.pdf"
    caminho.write_bytes(b"isto nao e um pdf valido, so bytes aleatorios")

    with pytest.raises(PdfCorrompidoError):
        pdf_service.abrir(caminho)


def test_abrir_levanta_pdf_protegido_para_pdf_com_senha(tmp_path: Path):
    documento = pymupdf.open()
    documento.new_page()
    caminho = tmp_path / "protegido.pdf"
    documento.save(caminho, encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw="dono123", user_pw="usuario123")
    documento.close()

    with pytest.raises(PdfProtegidoError):
        pdf_service.abrir(caminho)


def test_resolver_pagina_usa_imagem_embutida_quando_ha_exatamente_uma_candidata(tmp_path: Path):
    foto = Image.new("RGB", (600, 800), (120, 60, 200))
    caminho = _pagina_com_imagens(tmp_path, [foto])

    documento = pdf_service.abrir(caminho)
    try:
        pagina = pdf_service.resolver_pagina(documento, 0)
    finally:
        documento.close()

    assert pagina.numero == 1
    assert pagina.origem == OrigemTipo.IMAGEM_EMBUTIDA
    assert pagina.candidatas_descartadas == 0
    assert pagina.imagem.size == (600, 800)
    assert pagina.imagem.mode == "RGB"


def test_resolver_pagina_rasteriza_quando_nao_ha_imagem_embutida(tmp_path: Path):
    caminho = _pagina_sem_imagens(tmp_path)

    documento = pdf_service.abrir(caminho)
    try:
        pagina = pdf_service.resolver_pagina(documento, 0)
    finally:
        documento.close()

    assert pagina.origem == OrigemTipo.RASTERIZADA
    assert pagina.candidatas_descartadas == 0
    # A4 a 200 DPI: ~1653x2339px — bem maior que o tamanho de página em pontos
    assert pagina.imagem.width > 1000
    assert pagina.imagem.height > 1000


def test_resolver_pagina_escolhe_maior_candidata_e_registra_descartadas(tmp_path: Path):
    menor = Image.new("RGB", (600, 800), (120, 60, 200))
    maior = Image.new("RGB", (750, 1000), (50, 150, 90))
    caminho = _pagina_com_imagens(tmp_path, [menor, maior])

    documento = pdf_service.abrir(caminho)
    try:
        pagina = pdf_service.resolver_pagina(documento, 0)
    finally:
        documento.close()

    assert pagina.origem == OrigemTipo.IMAGEM_EMBUTIDA
    assert pagina.candidatas_descartadas == 1
    assert pagina.imagem.size == (750, 1000)


def test_resolver_pagina_descarta_candidata_pequena_demais_e_rasteriza(tmp_path: Path):
    logo = Image.new("RGB", (60, 60), (10, 10, 10))  # área 3.600 px² < AREA_MINIMA_CANDIDATA_PDF
    caminho = _pagina_com_imagens(tmp_path, [logo])

    documento = pdf_service.abrir(caminho)
    try:
        pagina = pdf_service.resolver_pagina(documento, 0)
    finally:
        documento.close()

    assert pagina.origem == OrigemTipo.RASTERIZADA
    # havia 1 imagem embutida na página, mas o filtro de área a descartou
    assert pagina.candidatas_descartadas == 1


def test_resolver_pagina_descarta_candidata_alongada_demais_e_rasteriza(tmp_path: Path):
    cabecalho = Image.new("RGB", (900, 100), (200, 200, 200))  # proporção 9.0, fora de 0.4-1.6
    caminho = _pagina_com_imagens(tmp_path, [cabecalho])

    documento = pdf_service.abrir(caminho)
    try:
        pagina = pdf_service.resolver_pagina(documento, 0)
    finally:
        documento.close()

    assert pagina.origem == OrigemTipo.RASTERIZADA
    # havia 1 imagem embutida na página, mas o filtro de proporção a descartou
    assert pagina.candidatas_descartadas == 1


def test_resolver_pagina_descarta_candidata_1_bit_e_rasteriza(tmp_path: Path):
    carimbo = Image.new("RGB", (400, 400), (255, 255, 255))  # área e proporção passariam, só o modo não
    caminho = _pagina_com_imagens(tmp_path, [carimbo], modo_1_bit=True)

    documento = pdf_service.abrir(caminho)
    try:
        pagina = pdf_service.resolver_pagina(documento, 0)
    finally:
        documento.close()

    assert pagina.origem == OrigemTipo.RASTERIZADA
    # havia 1 imagem embutida na página, mas o filtro de 1 bit a descartou
    assert pagina.candidatas_descartadas == 1


def test_resolver_pagina_funciona_por_indice_em_pdf_multiplas_paginas(tmp_path: Path):
    documento_construcao = pymupdf.open()
    fotos = [Image.new("RGB", (600, 800), cor) for cor in [(255, 0, 0), (0, 255, 0), (0, 0, 255)]]
    for foto in fotos:
        pagina = documento_construcao.new_page(width=595, height=842)
        buffer = io.BytesIO()
        foto.save(buffer, format="PNG")
        pagina.insert_image(pymupdf.Rect(50, 50, 250, 250), stream=buffer.getvalue())
    caminho = tmp_path / "varias_paginas.pdf"
    documento_construcao.save(caminho)
    documento_construcao.close()

    documento = pdf_service.abrir(caminho)
    try:
        assert documento.page_count == 3
        paginas = [pdf_service.resolver_pagina(documento, indice) for indice in range(3)]
    finally:
        documento.close()

    assert [p.numero for p in paginas] == [1, 2, 3]
    assert all(p.origem == OrigemTipo.IMAGEM_EMBUTIDA for p in paginas)
