"""Testes de crop_service: a janela de recorte guiada por rosto é sempre 3x4,
é deslocada para dentro da imagem quando encosta na borda, degrada para o
fator mínimo quando a ideal não cabe, e só vira "ombros cortados" quando nem
o fator mínimo cabe.
"""

import pytest

from backend import config
from backend.services.crop_service import ResultadoRecorte, calcular_janela
from backend.services.face_service import Rosto


def _rosto(x, y, largura=80, altura=100) -> Rosto:
    """Rosto de teste com olhos simétricos, centrados horizontalmente na caixa."""
    centro_x = x + largura / 2
    return Rosto(
        x=x,
        y=y,
        largura=largura,
        altura=altura,
        confianca=0.95,
        olho_direito=(centro_x - 20, y + altura * 0.3),
        olho_esquerdo=(centro_x + 20, y + altura * 0.3),
        nariz=(centro_x, y + altura * 0.5),
        boca_direita=(centro_x - 15, y + altura * 0.8),
        boca_esquerda=(centro_x + 15, y + altura * 0.8),
    )


def test_calcular_janela_sempre_produz_proporcao_3x4():
    rosto = _rosto(x=200, y=150)
    janela, resultado = calcular_janela(rosto, largura_imagem=1000, altura_imagem=1000)

    assert resultado == ResultadoRecorte.JANELA_VALIDA
    largura_janela = janela.direita - janela.esquerda
    altura_janela = janela.base - janela.topo
    assert largura_janela / altura_janela == pytest.approx(config.PROPORCAO_ALVO)


def test_calcular_janela_desloca_para_dentro_quando_encosta_na_borda_esquerda():
    # rosto perto da borda esquerda: a janela naive estouraria x < 0
    rosto = _rosto(x=10, y=150)
    janela, resultado = calcular_janela(rosto, largura_imagem=500, altura_imagem=1000)

    assert resultado == ResultadoRecorte.JANELA_VALIDA
    assert janela.esquerda == pytest.approx(0)
    assert janela.direita <= 500
    largura_janela = janela.direita - janela.esquerda
    altura_janela = janela.base - janela.topo
    assert largura_janela / altura_janela == pytest.approx(config.PROPORCAO_ALVO)


def test_calcular_janela_desloca_para_dentro_quando_encosta_na_borda_superior():
    # rosto perto do topo: topo da janela (ty - Hf*0.5) fica negativo
    rosto = _rosto(x=400, y=5)
    janela, resultado = calcular_janela(rosto, largura_imagem=1000, altura_imagem=1000)

    assert resultado == ResultadoRecorte.JANELA_VALIDA
    assert janela.topo == pytest.approx(0)
    assert janela.base <= 1000


def test_calcular_janela_devolve_ombros_cortados_quando_nao_ha_espaco_suficiente():
    # altura_imagem=200: nem a janela ideal (altura 150*1.85=277.5) nem a
    # mínima (altura 150*1.7=255) cabem, mesmo deslocadas para o canto.
    rosto = _rosto(x=100, y=50, largura=100, altura=150)
    janela, resultado = calcular_janela(rosto, largura_imagem=300, altura_imagem=200)

    assert resultado == ResultadoRecorte.OMBROS_CORTADOS
    assert janela is None


def test_calcular_janela_degrada_para_fator_minimo_quando_ideal_nao_cabe():
    # altura_imagem=265: a janela ideal (altura 150*1.85=277.5) não cabe, mas
    # a mínima (altura 150*1.7=255) cabe deslocada para dentro.
    rosto = _rosto(x=100, y=50, largura=100, altura=150)
    janela, resultado = calcular_janela(rosto, largura_imagem=300, altura_imagem=265)

    assert resultado == ResultadoRecorte.JANELA_AJUSTADA
    altura_janela = janela.base - janela.topo
    largura_janela = janela.direita - janela.esquerda
    assert altura_janela == pytest.approx(150 * config.FATOR_ALTURA_MINIMO)
    assert largura_janela / altura_janela == pytest.approx(config.PROPORCAO_ALVO)
    assert janela.topo == pytest.approx(0)
    assert janela.base <= 265
    assert 0 <= janela.esquerda and janela.direita <= 300
