"""Testes de face_service: classificação da qualidade da detecção e integração
básica com o detector YuNet.
"""

import numpy as np
from PIL import Image

from backend.services import face_service
from backend.services.face_service import QualidadeDeteccao, Rosto, classificar_deteccao, detectar_rostos


def _rosto(
    altura=200,
    x=100,
    largura=160,
    y=50,
    dist_olho_direito=40,
    dist_olho_esquerdo=45,
) -> Rosto:
    """Constrói um Rosto de teste com landmarks plausíveis e assimetria controlável.

    O nariz fica fixo em x=300; os olhos são posicionados a `dist_olho_*` de
    distância horizontal dele, o que permite forçar simetria ou assimetria.
    """
    centro_nariz_x = 300
    return Rosto(
        x=x,
        y=y,
        largura=largura,
        altura=altura,
        confianca=0.95,
        olho_direito=(centro_nariz_x - dist_olho_direito, y + altura * 0.3),
        olho_esquerdo=(centro_nariz_x + dist_olho_esquerdo, y + altura * 0.3),
        nariz=(centro_nariz_x, y + altura * 0.5),
        boca_direita=(centro_nariz_x - 20, y + altura * 0.8),
        boca_esquerda=(centro_nariz_x + 20, y + altura * 0.8),
    )


# --- classificação da qualidade --------------------------------------------


def test_classificar_deteccao_sem_rostos():
    assert classificar_deteccao([], altura_imagem=1000) == QualidadeDeteccao.NENHUM_ROSTO


def test_classificar_deteccao_multiplos_rostos():
    rostos = [_rosto(), _rosto(x=400)]
    assert classificar_deteccao(rostos, altura_imagem=1000) == QualidadeDeteccao.MULTIPLOS_ROSTOS


def test_classificar_deteccao_rosto_pequeno():
    # altura do rosto = 100, imagem = 1000 -> 10% < ALTURA_MINIMA_ROSTO (15%)
    rostos = [_rosto(altura=100)]
    assert classificar_deteccao(rostos, altura_imagem=1000) == QualidadeDeteccao.ROSTO_PEQUENO


def test_classificar_deteccao_rosto_lateral():
    # assimetria = (100-20)/100 = 0.8, bem acima do limiar (0.4)
    rostos = [_rosto(altura=200, dist_olho_direito=20, dist_olho_esquerdo=100)]
    assert classificar_deteccao(rostos, altura_imagem=1000) == QualidadeDeteccao.ROSTO_LATERAL


def test_classificar_deteccao_rosto_valido():
    # altura suficiente (20%) e distâncias olho-nariz parecidas
    rostos = [_rosto(altura=200, dist_olho_direito=40, dist_olho_esquerdo=45)]
    assert classificar_deteccao(rostos, altura_imagem=1000) == QualidadeDeteccao.ROSTO_VALIDO


# --- integração com o detector real -----------------------------------------


def test_detectar_rostos_nao_encontra_nada_em_imagem_em_branco():
    imagem = Image.new("RGB", (400, 400), (120, 60, 200))
    assert detectar_rostos(imagem) == []


# --- escala por eixo no redimensionamento para detecção ---------------------


def test_redimensionar_para_deteccao_calcula_escala_efetiva_por_eixo():
    # imagem bem alongada: o arredondamento das dimensões reduzidas faz a
    # escala efetiva do eixo x divergir nitidamente da do eixo y
    imagem_bgr = np.zeros((3, 1801, 3), dtype=np.uint8)

    redimensionada, escala_x, escala_y = face_service._redimensionar_para_deteccao(imagem_bgr, lado_maximo=800)

    assert redimensionada.shape[:2] == (1, 800)  # altura, largura
    assert escala_x == 800 / 1801
    assert escala_y == 1 / 3
    assert escala_x != escala_y


def test_redimensionar_para_deteccao_nao_reduz_quando_ja_cabe():
    imagem_bgr = np.zeros((300, 400, 3), dtype=np.uint8)

    redimensionada, escala_x, escala_y = face_service._redimensionar_para_deteccao(imagem_bgr, lado_maximo=800)

    assert redimensionada is imagem_bgr
    assert (escala_x, escala_y) == (1.0, 1.0)


def test_linha_para_rosto_usa_escala_de_cada_eixo_separadamente():
    # x,y,largura,altura, 5 pares (x,y) de landmarks, score — todos os
    # valores na escala da imagem reduzida
    linha = np.array(
        [100.0, 40.0, 60.0, 80.0, 110.0, 60.0, 150.0, 60.0, 130.0, 90.0, 115.0, 110.0, 145.0, 110.0, 0.95]
    )
    escala_x, escala_y = 0.5, 0.25

    rosto = face_service._linha_para_rosto(linha, escala_x, escala_y)

    assert rosto.x == 100.0 / escala_x
    assert rosto.y == 40.0 / escala_y
    assert rosto.largura == 60.0 / escala_x
    assert rosto.altura == 80.0 / escala_y
    assert rosto.olho_direito == (110.0 / escala_x, 60.0 / escala_y)
    assert rosto.olho_esquerdo == (150.0 / escala_x, 60.0 / escala_y)
    assert rosto.nariz == (130.0 / escala_x, 90.0 / escala_y)
    assert rosto.boca_direita == (115.0 / escala_x, 110.0 / escala_y)
    assert rosto.boca_esquerda == (145.0 / escala_x, 110.0 / escala_y)
    assert rosto.confianca == 0.95
