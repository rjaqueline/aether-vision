"""Testes do núcleo de processamento: proporção, tamanho de saída, recorte, nomes
únicos, não-varredura de subpastas e preservação dos originais.
"""

from pathlib import Path

import pytest
from PIL import Image

from backend import config
from backend.schemas.resultado import Motivo
from backend.services import face_service, image_service, pipeline, storage


def _criar_imagem(caminho: Path, largura: int, altura: int, cor=(120, 60, 200)) -> None:
    Image.new("RGB", (largura, altura), cor).save(caminho)


def _pasta_saida(pasta_base: Path) -> Path:
    """Localiza a pasta de saída (com timestamp) criada por um processar_pasta anterior em pasta_base."""
    return next(pasta_base.glob(f"{config.PREFIXO_PASTA_SAIDA}_*"))


# --- proporção ---------------------------------------------------------


def test_ja_esta_em_3x4_aceita_proporcao_exata():
    imagem = Image.new("RGB", (300, 400))  # 300/400 = 0.75
    assert image_service.ja_esta_em_3x4(imagem)


def test_ja_esta_em_3x4_aceita_dentro_da_tolerancia():
    imagem = Image.new("RGB", (306, 400))  # ~0.765, desvio ~2% < 3%
    assert image_service.ja_esta_em_3x4(imagem)


def test_ja_esta_em_3x4_rejeita_fora_da_tolerancia():
    imagem = Image.new("RGB", (400, 400))  # quadrada, bem fora de 3x4
    assert not image_service.ja_esta_em_3x4(imagem)


def test_caixa_central_3x4_produz_proporcao_alvo():
    caixa = image_service.caixa_central_3x4(1000, 400)
    esquerda, topo, direita, base = caixa
    proporcao = (direita - esquerda) / (base - topo)
    assert proporcao == pytest.approx(config.PROPORCAO_ALVO, abs=0.01)


# --- tamanho exato da saída ---------------------------------------------


def test_redimensionar_para_saida_gera_tamanho_exato():
    imagem = Image.new("RGB", (900, 1300))
    final = image_service.redimensionar_para_saida(imagem)
    assert final.size == (config.LARGURA_FINAL, config.ALTURA_FINAL)


# --- recorte que não estoura borda ---------------------------------------


def test_caixa_central_3x4_nao_estoura_borda_imagem_larga():
    largura, altura = 1000, 400
    esquerda, topo, direita, base = image_service.caixa_central_3x4(largura, altura)
    assert 0 <= esquerda < direita <= largura
    assert 0 <= topo < base <= altura


def test_caixa_central_3x4_nao_estoura_borda_imagem_alta():
    largura, altura = 400, 1000
    esquerda, topo, direita, base = image_service.caixa_central_3x4(largura, altura)
    assert 0 <= esquerda < direita <= largura
    assert 0 <= topo < base <= altura


def test_recortar_nao_estoura_quando_caixa_ultrapassa_bordas():
    imagem = Image.new("RGB", (100, 100))
    recortada = image_service.recortar(imagem, (-10, -10, 150, 150))
    assert recortada.size == (100, 100)


# --- nomes únicos ---------------------------------------------------------


def test_caminho_disponivel_gera_sufixos_unicos(tmp_path: Path):
    (tmp_path / "foto.png").touch()
    (tmp_path / "foto_2.png").touch()

    destino = storage.caminho_disponivel(tmp_path, "foto.png")

    assert destino.name == "foto_3.png"


def test_caminho_disponivel_nao_altera_nome_livre(tmp_path: Path):
    destino = storage.caminho_disponivel(tmp_path, "foto.png")
    assert destino.name == "foto.png"


# --- validação de pasta destino --------------------------------------------


def test_validar_pasta_destino_rejeita_caminho_relativo():
    # caminho relativo resolveria contra o cwd do servidor, não contra algo
    # previsível para quem digitou — precisa ser recusado sem tocar o disco
    valida, mensagem = storage.validar_pasta_destino(Path(".test-tmp"))

    assert valida is False
    assert "absoluto" in mensagem.lower()


def test_validar_pasta_destino_nao_cria_pasta_inexistente(tmp_path: Path):
    pasta_inexistente = tmp_path / "nao_existe"

    valida, mensagem = storage.validar_pasta_destino(pasta_inexistente)

    assert valida is False
    assert mensagem == "Pasta não encontrada."
    assert not pasta_inexistente.exists()


def test_validar_pasta_destino_aceita_pasta_existente_e_remove_temporario(tmp_path: Path):
    valida, mensagem = storage.validar_pasta_destino(tmp_path)

    assert (valida, mensagem) == (True, "")
    assert list(tmp_path.iterdir()) == []


# --- não-varredura de subpastas -------------------------------------------


def test_listar_entradas_nao_varre_subpastas(tmp_path: Path):
    _criar_imagem(tmp_path / "raiz.jpg", 300, 400)
    subpasta = tmp_path / "sub"
    subpasta.mkdir()
    _criar_imagem(subpasta / "dentro.jpg", 300, 400)

    entradas = storage.listar_entradas(tmp_path)

    assert [c.name for c in entradas] == ["raiz.jpg"]


def test_listar_entradas_ignora_pasta_de_saida(tmp_path: Path):
    _criar_imagem(tmp_path / "raiz.jpg", 300, 400)
    pasta_saida = tmp_path / storage.nome_pasta_saida()
    storage.preparar_saida(pasta_saida)
    _criar_imagem(pasta_saida / config.NOME_PASTA_APROVADAS / "ja_processada.png", 200, 267)

    entradas = storage.listar_entradas(tmp_path)

    assert [c.name for c in entradas] == ["raiz.jpg"]


# --- preservação dos originais e integração do pipeline --------------------


def test_processar_pasta_preserva_originais(tmp_path: Path):
    caminho_original = tmp_path / "empregado.jpg"
    _criar_imagem(caminho_original, 300, 400)
    conteudo_antes = caminho_original.read_bytes()

    pipeline.processar_pasta(tmp_path)

    assert caminho_original.read_bytes() == conteudo_antes


def test_processar_pasta_aprova_imagem_ja_em_3x4_com_rosto_valido(tmp_path: Path, monkeypatch):
    """Mesmo já em 3x4, a aprovação passa pelo recorte guiado por rosto — não há mais atalho."""
    _criar_imagem(tmp_path / "empregado.jpg", 600, 800)  # já é 3x4

    rosto_valido = face_service.Rosto(
        x=200, y=150, largura=200, altura=250, confianca=0.99,
        olho_direito=(250, 220), olho_esquerdo=(350, 220),
        nariz=(300, 280), boca_direita=(260, 340), boca_esquerda=(340, 340),
    )
    monkeypatch.setattr(face_service, "detectar_rostos", lambda imagem: [rosto_valido])

    resultados = pipeline.processar_pasta(tmp_path)

    assert resultados[0].motivo == Motivo.ROSTO_VALIDO_RECORTADO
    saida = _pasta_saida(tmp_path) / config.NOME_PASTA_APROVADAS / "empregado.png"
    assert saida.exists()
    with Image.open(saida) as imagem:
        assert imagem.size == (config.LARGURA_FINAL, config.ALTURA_FINAL)


def test_processar_pasta_manda_para_revisar_quando_sem_rosto_mesmo_em_3x4(tmp_path: Path):
    _criar_imagem(tmp_path / "empregado.jpg", 600, 800)  # já é 3x4, mas sem rosto detectável

    pipeline.processar_pasta(tmp_path)

    saida = _pasta_saida(tmp_path) / config.NOME_PASTA_REVISAR / "empregado.png"
    assert saida.exists()


def test_processar_pasta_manda_para_revisar_quando_fora_de_3x4(tmp_path: Path):
    _criar_imagem(tmp_path / "empregado.jpg", 500, 500)  # quadrada

    pipeline.processar_pasta(tmp_path)

    saida = _pasta_saida(tmp_path) / config.NOME_PASTA_REVISAR / "empregado.png"
    assert saida.exists()
    with Image.open(saida) as imagem:
        assert imagem.size == (config.LARGURA_FINAL, config.ALTURA_FINAL)


def test_processar_pasta_gera_nomes_unicos_para_arquivos_repetidos(tmp_path: Path, monkeypatch):
    _criar_imagem(tmp_path / "a.jpg", 600, 800)
    rosto_valido = face_service.Rosto(
        x=200, y=150, largura=200, altura=250, confianca=0.99,
        olho_direito=(250, 220), olho_esquerdo=(350, 220),
        nariz=(300, 280), boca_direita=(260, 340), boca_esquerda=(340, 340),
    )
    monkeypatch.setattr(face_service, "detectar_rostos", lambda imagem: [rosto_valido])
    pipeline.processar_pasta(tmp_path)

    # simula um segundo arquivo que resultaria no mesmo nome de saída
    pasta_aprovadas = _pasta_saida(tmp_path) / config.NOME_PASTA_APROVADAS
    destino = storage.caminho_disponivel(pasta_aprovadas, "a.png")

    assert destino.name == "a_2.png"
