"""Detecção facial com o modelo YuNet do OpenCV.

Localiza rostos numa imagem PIL (caixa, confiança e os 5 landmarks) e
classifica a qualidade da detecção nos casos que o pipeline usa para decidir
entre aprovação direta e revisão manual.
"""

from dataclasses import dataclass
from enum import Enum

import cv2
import numpy as np
from PIL import Image

from backend import config

_detector: cv2.FaceDetectorYN | None = None


@dataclass
class Rosto:
    """Um rosto detectado: caixa delimitadora, confiança e os 5 pontos de referência."""

    x: float
    y: float
    largura: float
    altura: float
    confianca: float
    olho_direito: tuple[float, float]
    olho_esquerdo: tuple[float, float]
    nariz: tuple[float, float]
    boca_direita: tuple[float, float]
    boca_esquerda: tuple[float, float]


class QualidadeDeteccao(str, Enum):
    """Classificação da detecção facial de uma imagem."""

    NENHUM_ROSTO = "nenhum rosto"
    MULTIPLOS_ROSTOS = "múltiplos rostos"
    ROSTO_PEQUENO = "rosto pequeno"
    ROSTO_LATERAL = "rosto lateral"
    ROSTO_VALIDO = "rosto válido"


def _obter_detector(largura: int, altura: int) -> cv2.FaceDetectorYN:
    """Cria (ou reaproveita) o detector YuNet, ajustando o tamanho de entrada à imagem."""
    global _detector
    if _detector is None:
        _detector = cv2.FaceDetectorYN.create(
            str(config.CAMINHO_MODELO_YUNET),
            "",
            (largura, altura),
            score_threshold=config.CONFIANCA_MINIMA_ROSTO,
            nms_threshold=config.NMS_LIMIAR_IOU,
            top_k=config.TOP_K_ROSTOS,
        )
    else:
        _detector.setInputSize((largura, altura))
    return _detector


def detectar_rostos(imagem: Image.Image) -> list[Rosto]:
    """Detecta rostos em uma imagem PIL e devolve caixa, confiança e landmarks de cada um."""
    imagem_bgr = cv2.cvtColor(np.array(imagem.convert("RGB")), cv2.COLOR_RGB2BGR)
    imagem_deteccao, escala = _redimensionar_para_deteccao(imagem_bgr, config.LADO_MAXIMO_DETECCAO)
    altura, largura = imagem_deteccao.shape[:2]
    detector = _obter_detector(largura, altura)
    _, deteccoes = detector.detect(imagem_deteccao)

    if deteccoes is None:
        return []
    return [_linha_para_rosto(linha, escala) for linha in deteccoes]


def _redimensionar_para_deteccao(imagem_bgr: np.ndarray, lado_maximo: int) -> tuple[np.ndarray, float]:
    """Reduz a imagem para no máximo `lado_maximo` px no maior lado antes de detectar.

    O YuNet degrada em imagens grandes; detectar numa cópia reduzida produz
    confiança maior, e o fator de escala devolvido permite reposicionar a
    caixa e os landmarks nas coordenadas da imagem original.
    """
    altura, largura = imagem_bgr.shape[:2]
    escala = min(1.0, lado_maximo / max(altura, largura))
    if escala == 1.0:
        return imagem_bgr, 1.0
    nova_largura = round(largura * escala)
    nova_altura = round(altura * escala)
    imagem_redimensionada = cv2.resize(imagem_bgr, (nova_largura, nova_altura), interpolation=cv2.INTER_AREA)
    return imagem_redimensionada, escala


def _linha_para_rosto(linha: np.ndarray, escala: float) -> Rosto:
    """Converte uma linha da saída do YuNet (caixa + 5 landmarks + score) em Rosto.

    Ordem da saída do YuNet: x, y, largura, altura, depois 5 pares (x, y) para
    olho direito, olho esquerdo, ponta do nariz, canto direito e esquerdo da
    boca, e por fim o score de confiança. As coordenadas vêm na escala da
    imagem passada ao detector, por isso são divididas por `escala` para
    voltar ao tamanho original.
    """
    valores = [float(v) / escala for v in linha[:14]]
    confianca = float(linha[14])
    x, y, largura, altura = valores[0:4]
    olho_direito = (valores[4], valores[5])
    olho_esquerdo = (valores[6], valores[7])
    nariz = (valores[8], valores[9])
    boca_direita = (valores[10], valores[11])
    boca_esquerda = (valores[12], valores[13])
    return Rosto(
        x=x,
        y=y,
        largura=largura,
        altura=altura,
        confianca=confianca,
        olho_direito=olho_direito,
        olho_esquerdo=olho_esquerdo,
        nariz=nariz,
        boca_direita=boca_direita,
        boca_esquerda=boca_esquerda,
    )


def classificar_deteccao(rostos: list[Rosto], altura_imagem: int) -> QualidadeDeteccao:
    """Classifica a lista de rostos detectados em um dos casos de qualidade."""
    if len(rostos) == 0:
        return QualidadeDeteccao.NENHUM_ROSTO
    if len(rostos) > 1:
        return QualidadeDeteccao.MULTIPLOS_ROSTOS

    rosto = rostos[0]
    if rosto.altura < config.ALTURA_MINIMA_ROSTO * altura_imagem:
        return QualidadeDeteccao.ROSTO_PEQUENO
    if _e_rosto_lateral(rosto):
        return QualidadeDeteccao.ROSTO_LATERAL
    return QualidadeDeteccao.ROSTO_VALIDO


def _e_rosto_lateral(rosto: Rosto) -> bool:
    """Mede a assimetria horizontal entre a distância de cada olho ao nariz.

    Num rosto de frente as duas distâncias são parecidas; de perfil, um olho
    fica bem mais perto do nariz (ou é ocluído), disparando uma assimetria
    grande — esse é o sinal que usamos em vez de estimar pose 3D.
    """
    distancia_direita = abs(rosto.nariz[0] - rosto.olho_direito[0])
    distancia_esquerda = abs(rosto.nariz[0] - rosto.olho_esquerdo[0])
    maior_distancia = max(distancia_direita, distancia_esquerda)
    if maior_distancia == 0:
        return True
    assimetria = abs(distancia_direita - distancia_esquerda) / maior_distancia
    return assimetria > config.ASSIMETRIA_MAXIMA_ROSTO_LATERAL
