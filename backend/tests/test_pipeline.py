"""Testes de integração do pipeline: cada caso de qualidade de detecção facial
leva ao status e motivo corretos, e toda saída aprovada exige exatamente um
rosto válido e passa pelo recorte guiado por ele — a proporção original da
entrada nunca decide nada.
"""

from pathlib import Path

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
