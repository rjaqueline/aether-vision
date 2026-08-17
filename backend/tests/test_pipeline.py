"""Testes de integração do pipeline: cada caso de qualidade de detecção facial
leva ao status e motivo corretos, e toda saída aprovada exige exatamente um
rosto válido e passa pelo recorte guiado por ele — a proporção original da
entrada nunca decide nada.

Também cobre PDFs: cada página vira um ResultadoItem independente, com a
coluna `origem` registrando de onde veio a imagem, sem derrubar o lote
inteiro quando um PDF individual está corrompido ou protegido.
"""

import io
from pathlib import Path

import pymupdf
from PIL import Image

from backend import config
from backend.schemas.resultado import Motivo, Status
from backend.services import face_service, pipeline
from backend.services.face_service import Rosto


def _criar_imagem(caminho: Path, largura: int, altura: int, cor=(120, 60, 200)) -> None:
    Image.new("RGB", (largura, altura), cor).save(caminho)


def _rosto_valido(x=200, y=150, largura=200, altura=250) -> Rosto:
    centro_x = x + largura / 2
    return Rosto(
        x=x,
        y=y,
        largura=largura,
        altura=altura,
        confianca=0.99,
        olho_direito=(centro_x - 50, y + altura * 0.3),
        olho_esquerdo=(centro_x + 50, y + altura * 0.3),
        nariz=(centro_x, y + altura * 0.5),
        boca_direita=(centro_x - 40, y + altura * 0.8),
        boca_esquerda=(centro_x + 40, y + altura * 0.8),
    )


def _processar_um(tmp_path: Path, largura: int, altura: int, deteccao_falsa, monkeypatch):
    caminho = tmp_path / "empregado.jpg"
    _criar_imagem(caminho, largura, altura)
    monkeypatch.setattr(face_service, "detectar_rostos", deteccao_falsa)
    resultados = pipeline.processar_pasta(tmp_path)
    return resultados[0]


def test_nenhum_rosto_vai_para_revisar(tmp_path: Path):
    # imagem em branco: o detector real não encontra rosto nenhum
    _criar_imagem(tmp_path / "empregado.jpg", 600, 800)

    resultados = pipeline.processar_pasta(tmp_path)

    resultado = resultados[0]
    assert resultado.status == Status.REVISAR
    assert resultado.motivo == Motivo.NENHUM_ROSTO
    saida = tmp_path / config.NOME_PASTA_SAIDA / config.NOME_PASTA_REVISAR / "empregado.png"
    assert saida.exists()
    with Image.open(saida) as imagem:
        assert imagem.size == (config.LARGURA_FINAL, config.ALTURA_FINAL)


def test_multiplos_rostos_vai_para_revisar(tmp_path: Path, monkeypatch):
    resultado = _processar_um(
        tmp_path, 600, 800, lambda imagem: [_rosto_valido(), _rosto_valido(x=400)], monkeypatch
    )
    assert resultado.status == Status.REVISAR
    assert resultado.motivo == Motivo.MULTIPLOS_ROSTOS


def test_rosto_pequeno_vai_para_revisar(tmp_path: Path, monkeypatch):
    # altura do rosto bem menor que ALTURA_MINIMA_ROSTO da altura da imagem
    resultado = _processar_um(
        tmp_path, 600, 800, lambda imagem: [_rosto_valido(altura=50)], monkeypatch
    )
    assert resultado.status == Status.REVISAR
    assert resultado.motivo == Motivo.ROSTO_PEQUENO


def test_rosto_lateral_vai_para_revisar(tmp_path: Path, monkeypatch):
    rosto_lateral = Rosto(
        x=200, y=150, largura=200, altura=250, confianca=0.95,
        olho_direito=(280, 220), olho_esquerdo=(420, 220),  # assimetria forte perto do nariz
        nariz=(300, 280), boca_direita=(260, 340), boca_esquerda=(340, 340),
    )
    resultado = _processar_um(tmp_path, 600, 800, lambda imagem: [rosto_lateral], monkeypatch)
    assert resultado.status == Status.REVISAR
    assert resultado.motivo == Motivo.ROSTO_LATERAL


def test_ombros_cortados_vai_para_revisar(tmp_path: Path, monkeypatch):
    # imagem pequena: nem a janela ideal (150*1.85=277.5) nem a mínima (150*1.7=255) cabem
    rosto = _rosto_valido(x=100, y=50, largura=100, altura=150)
    resultado = _processar_um(tmp_path, 300, 200, lambda imagem: [rosto], monkeypatch)
    assert resultado.status == Status.REVISAR
    assert resultado.motivo == Motivo.OMBROS_CORTADOS


def test_janela_ideal_nao_cabe_mas_minima_cabe_e_aprovado_com_ajuste(tmp_path: Path, monkeypatch):
    # altura=265: a janela ideal (150*1.85=277.5) não cabe, mas a mínima (150*1.7=255) cabe
    rosto = _rosto_valido(x=100, y=50, largura=100, altura=150)
    resultado = _processar_um(tmp_path, 300, 265, lambda imagem: [rosto], monkeypatch)
    assert resultado.status == Status.PRONTO
    assert resultado.motivo == Motivo.ROSTO_VALIDO_RECORTADO_AJUSTADO


def test_rosto_valido_fora_de_3x4_e_aprovado_com_recorte_facial(tmp_path: Path, monkeypatch):
    rosto = _rosto_valido(x=150, y=100, largura=200, altura=250)
    resultado = _processar_um(tmp_path, 800, 800, lambda imagem: [rosto], monkeypatch)
    assert resultado.status == Status.PRONTO
    assert resultado.motivo == Motivo.ROSTO_VALIDO_RECORTADO

    saida = (
        tmp_path
        / config.NOME_PASTA_SAIDA
        / config.NOME_PASTA_APROVADAS
        / resultado.arquivo_saida
    )
    with Image.open(saida) as imagem:
        assert imagem.size == (config.LARGURA_FINAL, config.ALTURA_FINAL)


# --- PDF --------------------------------------------------------------------


def _pdf_com_imagem(tmp_path: Path, nome: str, largura: int, altura: int, cor=(120, 60, 200)) -> Path:
    """Cria um PDF de uma página com uma única imagem embutida do tamanho dado."""
    documento = pymupdf.open()
    pagina = documento.new_page(width=595, height=842)
    buffer = io.BytesIO()
    Image.new("RGB", (largura, altura), cor).save(buffer, format="PNG")
    pagina.insert_image(pymupdf.Rect(50, 50, 300, 300), stream=buffer.getvalue())
    caminho = tmp_path / nome
    documento.save(caminho)
    documento.close()
    return caminho


def test_pdf_com_imagem_embutida_vira_item_com_pagina_na_origem(tmp_path: Path, monkeypatch):
    _pdf_com_imagem(tmp_path, "formulario.pdf", 600, 800)
    rosto = _rosto_valido(x=200, y=150, largura=200, altura=250)
    monkeypatch.setattr(face_service, "detectar_rostos", lambda imagem: [rosto])

    resultados = pipeline.processar_pasta(tmp_path)

    assert len(resultados) == 1
    resultado = resultados[0]
    assert resultado.status == Status.PRONTO
    assert resultado.arquivo_original == "formulario.pdf"
    assert resultado.origem == "página 1 (imagem embutida)"
    assert resultado.arquivo_saida == "formulario_pagina_01.png"
    saida = tmp_path / config.NOME_PASTA_SAIDA / config.NOME_PASTA_APROVADAS / resultado.arquivo_saida
    assert saida.exists()
    with Image.open(saida) as imagem:
        assert imagem.size == (config.LARGURA_FINAL, config.ALTURA_FINAL)


def test_pdf_escaneado_sem_imagem_embutida_e_rasterizado(tmp_path: Path, monkeypatch):
    documento = pymupdf.open()
    pagina = documento.new_page(width=595, height=842)
    pagina.insert_text((50, 50), "documento escaneado, sem imagem embutida")
    caminho = tmp_path / "scan.pdf"
    documento.save(caminho)
    documento.close()

    monkeypatch.setattr(face_service, "detectar_rostos", lambda imagem: [])

    resultados = pipeline.processar_pasta(tmp_path)

    assert len(resultados) == 1
    resultado = resultados[0]
    assert resultado.status == Status.REVISAR
    assert resultado.motivo == Motivo.NENHUM_ROSTO
    assert resultado.origem == "página 1 (rasterizada — nenhuma candidata válida)"
    assert resultado.arquivo_saida == "scan_pagina_01.png"


def test_pdf_com_candidata_descartada_por_filtro_e_rasterizado_com_motivo_no_origem(
    tmp_path: Path, monkeypatch
):
    # única imagem embutida é um logo pequeno demais: descartada pelo filtro
    # de área, não por ausência de imagem — a origem precisa distinguir isso
    documento = pymupdf.open()
    pagina = documento.new_page(width=595, height=842)
    logo = Image.new("RGB", (60, 60), (10, 10, 10))
    buffer = io.BytesIO()
    logo.save(buffer, format="PNG")
    pagina.insert_image(pymupdf.Rect(50, 50, 90, 90), stream=buffer.getvalue())
    caminho = tmp_path / "form_so_com_logo.pdf"
    documento.save(caminho)
    documento.close()

    monkeypatch.setattr(face_service, "detectar_rostos", lambda imagem: [])

    resultados = pipeline.processar_pasta(tmp_path)

    assert len(resultados) == 1
    assert resultados[0].origem == "página 1 (rasterizada — 1 candidata(s) descartada(s) por filtro)"


def test_pdf_multiplas_paginas_vira_um_item_por_pagina(tmp_path: Path, monkeypatch):
    documento = pymupdf.open()
    for _ in range(3):
        pagina = documento.new_page(width=595, height=842)
        buffer = io.BytesIO()
        Image.new("RGB", (600, 800), (120, 60, 200)).save(buffer, format="PNG")
        pagina.insert_image(pymupdf.Rect(50, 50, 300, 300), stream=buffer.getvalue())
    caminho = tmp_path / "lote.pdf"
    documento.save(caminho)
    documento.close()

    rosto = _rosto_valido(x=200, y=150, largura=200, altura=250)
    monkeypatch.setattr(face_service, "detectar_rostos", lambda imagem: [rosto])

    resultados = pipeline.processar_pasta(tmp_path)

    assert len(resultados) == 3
    assert [r.origem for r in resultados] == [
        "página 1 (imagem embutida)",
        "página 2 (imagem embutida)",
        "página 3 (imagem embutida)",
    ]
    assert [r.arquivo_saida for r in resultados] == [
        "lote_pagina_01.png",
        "lote_pagina_02.png",
        "lote_pagina_03.png",
    ]
    assert all(r.arquivo_original == "lote.pdf" for r in resultados)
    assert all(r.status == Status.PRONTO for r in resultados)


def test_pdf_corrompido_vira_item_de_erro_sem_derrubar_o_lote(tmp_path: Path, monkeypatch):
    (tmp_path / "corrompido.pdf").write_bytes(b"nao e um pdf valido, so bytes aleatorios")
    _criar_imagem(tmp_path / "empregado.jpg", 600, 800)
    rosto = _rosto_valido(x=200, y=150, largura=200, altura=250)
    monkeypatch.setattr(face_service, "detectar_rostos", lambda imagem: [rosto])

    resultados = pipeline.processar_pasta(tmp_path)

    por_nome = {r.arquivo_original: r for r in resultados}
    assert por_nome["corrompido.pdf"].status == Status.ERRO
    assert por_nome["corrompido.pdf"].motivo == Motivo.PDF_CORROMPIDO
    assert por_nome["empregado.jpg"].status == Status.PRONTO


def test_falha_inesperada_em_um_item_nao_derruba_o_lote(tmp_path: Path, monkeypatch):
    # simula uma regressão não prevista em _processar_pdf/_processar_arquivo
    # (ex.: falha ao ler page_count, ou ao fechar o documento) — o item vira
    # erro isolado, sem impedir que os demais arquivos do lote sejam processados
    _criar_imagem(tmp_path / "quebra.jpg", 600, 800)
    _criar_imagem(tmp_path / "empregado.jpg", 600, 800)
    rosto = _rosto_valido(x=200, y=150, largura=200, altura=250)
    monkeypatch.setattr(face_service, "detectar_rostos", lambda imagem: [rosto])

    original = pipeline._processar_arquivo

    def _processar_arquivo_com_falha(caminho, aprovadas, revisar, debug):
        if caminho.name == "quebra.jpg":
            raise RuntimeError("falha inesperada simulada")
        return original(caminho, aprovadas, revisar, debug)

    monkeypatch.setattr(pipeline, "_processar_arquivo", _processar_arquivo_com_falha)

    resultados = pipeline.processar_pasta(tmp_path)

    por_nome = {r.arquivo_original: r for r in resultados}
    assert por_nome["quebra.jpg"].status == Status.ERRO
    assert por_nome["quebra.jpg"].motivo == Motivo.FALHA_INESPERADA
    assert por_nome["empregado.jpg"].status == Status.PRONTO


def test_falha_ao_gerar_debug_nao_invalida_resultado_ja_salvo(tmp_path: Path, monkeypatch):
    rosto = _rosto_valido(x=150, y=100, largura=200, altura=250)
    monkeypatch.setattr(face_service, "detectar_rostos", lambda imagem: [rosto])
    monkeypatch.setattr(
        pipeline.debug_service,
        "salvar_visualizacao",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("falha simulada ao salvar debug")),
    )

    resultado = _processar_um(tmp_path, 800, 800, lambda imagem: [rosto], monkeypatch)

    assert resultado.status == Status.PRONTO
    assert resultado.motivo == Motivo.ROSTO_VALIDO_RECORTADO
    assert "debug" in resultado.detalhe.lower()

    saida = (
        tmp_path
        / config.NOME_PASTA_SAIDA
        / config.NOME_PASTA_APROVADAS
        / resultado.arquivo_saida
    )
    assert saida.exists()


def test_pdf_protegido_vira_item_de_erro(tmp_path: Path):
    documento = pymupdf.open()
    documento.new_page()
    caminho = tmp_path / "protegido.pdf"
    documento.save(caminho, encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw="dono123", user_pw="usuario123")
    documento.close()

    resultados = pipeline.processar_pasta(tmp_path)

    assert len(resultados) == 1
    assert resultados[0].status == Status.ERRO
    assert resultados[0].motivo == Motivo.PDF_PROTEGIDO
