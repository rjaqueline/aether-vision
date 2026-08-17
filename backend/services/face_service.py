"""Detecção facial com o modelo YuNet do OpenCV.

Localiza rostos numa imagem PIL (caixa, confiança e os 5 landmarks) e
classifica a qualidade da detecção nos casos que o pipeline usa para decidir
entre aprovação direta e revisão manual.
"""

import threading
from dataclasses import dataclass
from enum import Enum

import cv2
import numpy as np
from PIL import Image

from backend import config

# Cache global de processo: cv2.FaceDetectorYN é caro de criar (carrega o
# modelo ONNX), então é criado uma vez e reaproveitado entre chamadas.
#
# NÃO é thread-safe por conta própria: _obter_detector faz setInputSize(...)
# e quem chama faz detector.detect(...) em seguida, como duas operações
# separadas sobre o mesmo objeto cv2.FaceDetectorYN. Threads concorrentes
# podem intercalar essas chamadas e uma thread detectar com o InputSize
# setado pela outra. Isso era só uma anotação enquanto o pipeline era
# sequencial (CLI); virou risco real na Etapa 4, com o FastAPI atendendo
# requisições concorrentes — por isso _detector_lock serializa o par
# setInputSize+detect (ver detectar_rostos) em vez de dar um detector por
# thread: o modelo ONNX carregado é o mesmo custo caro de _obter_detector
# citado acima, e duplicá-lo por worker gastaria memória sem necessidade
# real, já que este é um app local de usuário único (poucas sessões
# concorrentes, não um servidor de alto tráfego) — serializar a detecção
# em si é uma perda de paralelismo aceitável nesse cenário.
_detector: cv2.FaceDetectorYN | None = None
_detector_lock = threading.Lock()


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
    imagem_deteccao, escala_x, escala_y = _redimensionar_para_deteccao(imagem_bgr, config.LADO_MAXIMO_DETECCAO)
    altura, largura = imagem_deteccao.shape[:2]

    # setInputSize (dentro de _obter_detector) e detect formam uma seção
    # crítica: são duas chamadas separadas sobre o mesmo cv2.FaceDetectorYN
    # cacheado globalmente, e precisam executar como uma unidade atômica
    # mesmo com requisições concorrentes (ver comentário em _detector acima).
    with _detector_lock:
        detector = _obter_detector(largura, altura)
        _, deteccoes = detector.detect(imagem_deteccao)

    if deteccoes is None:
        return []
    return [_linha_para_rosto(linha, escala_x, escala_y) for linha in deteccoes]


def _redimensionar_para_deteccao(imagem_bgr: np.ndarray, lado_maximo: int) -> tuple[np.ndarray, float, float]:
    """Reduz a imagem para no máximo `lado_maximo` px no maior lado antes de detectar.

    O YuNet degrada em imagens grandes; detectar numa cópia reduzida produz
    confiança maior. As dimensões reduzidas (nova_largura, nova_altura) são
    arredondadas para pixel inteiro, o que desalinha ligeiramente a razão
    largura/altura em relação à imagem original — por isso a escala efetiva
    de cada eixo é calculada separadamente (nova_largura/largura e
    nova_altura/altura, já pós-arredondamento) e devolvida como
    (escala_x, escala_y), para reposicionar caixa e landmarks nas coordenadas
    da imagem original sem herdar esse erro de arredondamento.
    """
    altura, largura = imagem_bgr.shape[:2]
    escala = min(1.0, lado_maximo / max(altura, largura))
    if escala == 1.0:
        return imagem_bgr, 1.0, 1.0
    nova_largura = round(largura * escala)
    nova_altura = round(altura * escala)
    imagem_redimensionada = cv2.resize(imagem_bgr, (nova_largura, nova_altura), interpolation=cv2.INTER_AREA)
    escala_x = nova_largura / largura
    escala_y = nova_altura / altura
    return imagem_redimensionada, escala_x, escala_y


def _linha_para_rosto(linha: np.ndarray, escala_x: float, escala_y: float) -> Rosto:
    """Converte uma linha da saída do YuNet (caixa + 5 landmarks + score) em Rosto.

    Ordem da saída do YuNet: x, y, largura, altura, depois 5 pares (x, y) para
    olho direito, olho esquerdo, ponta do nariz, canto direito e esquerdo da
    boca, e por fim o score de confiança. As coordenadas vêm na escala da
    imagem passada ao detector, por isso os valores de eixo x são divididos
    por `escala_x` e os de eixo y por `escala_y` (ver
    _redimensionar_para_deteccao) para voltar ao tamanho original.
    """
    valores = [float(v) / escala_x if indice % 2 == 0 else float(v) / escala_y for indice, v in enumerate(linha[:14])]
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
