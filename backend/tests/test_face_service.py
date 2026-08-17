"""Testes de face_service: classificação da qualidade da detecção e integração
básica com o detector YuNet.
"""

from PIL import Image

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
