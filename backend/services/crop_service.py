"""Calcula a janela de recorte 3x4 a partir de um rosto detectado.

A largura da janela é sempre derivada da sua altura (altura * PROPORCAO_ALVO):
o 3x4 é garantido por construção, nunca calculado de outro jeito.
"""

from dataclasses import dataclass
from enum import Enum

from backend import config
from backend.services.face_service import Rosto


class ResultadoRecorte(str, Enum):
    """Desfecho do cálculo da janela de recorte guiada por rosto."""

    JANELA_VALIDA = "janela válida"
    JANELA_AJUSTADA = "janela ajustada"
    OMBROS_CORTADOS = "ombros cortados"


@dataclass
class JanelaRecorte:
    """Janela de recorte em coordenadas de pixel da imagem original."""

    esquerda: float
    topo: float
    direita: float
    base: float


def calcular_janela(
    rosto: Rosto, largura_imagem: int, altura_imagem: int
) -> tuple[JanelaRecorte | None, ResultadoRecorte]:
    """Calcula a janela 3x4 centrada no rosto, deslocando-a para dentro da imagem se preciso.

    Tenta primeiro a janela ideal (FATOR_ALTURA_JANELA). Se não couber mesmo
    deslocada, tenta de novo com a janela mínima (FATOR_ALTURA_MINIMO) antes
    de desistir — selfies onde o rosto já ocupa boa parte do quadro raramente
    cabem na janela ideal, mas um enquadramento um pouco mais apertado ainda
    rende uma foto de cadastro válida. Só quando nem a mínima cabe é que
    devolve OMBROS_CORTADOS (e janela None) para a imagem ir para revisão.
    """
    janela = _calcular_janela_para_fator(rosto, largura_imagem, altura_imagem, config.FATOR_ALTURA_JANELA)
    if janela is not None:
        return janela, ResultadoRecorte.JANELA_VALIDA

    janela = _calcular_janela_para_fator(rosto, largura_imagem, altura_imagem, config.FATOR_ALTURA_MINIMO)
    if janela is not None:
        return janela, ResultadoRecorte.JANELA_AJUSTADA

    return None, ResultadoRecorte.OMBROS_CORTADOS


def _calcular_janela_para_fator(
    rosto: Rosto, largura_imagem: int, altura_imagem: int, fator_altura: float
) -> JanelaRecorte | None:
    """Calcula a janela 3x4 para um fator de altura específico, ou None se não couber."""
    altura_face = rosto.altura
    altura_janela = altura_face * fator_altura
    largura_janela = altura_janela * config.PROPORCAO_ALVO

    centro_horizontal = rosto.x + rosto.largura / 2
    if _landmarks_dos_olhos_disponiveis(rosto):
        centro_horizontal = (rosto.olho_direito[0] + rosto.olho_esquerdo[0]) / 2

    topo = rosto.y - altura_face * config.FATOR_MARGEM_TOPO
    esquerda = centro_horizontal - largura_janela / 2
    direita = esquerda + largura_janela
    base = topo + altura_janela

    esquerda, topo, direita, base = _deslocar_para_dentro(
        esquerda, topo, direita, base, largura_imagem, altura_imagem
    )

    if esquerda < 0 or topo < 0 or direita > largura_imagem or base > altura_imagem:
        return None

    return JanelaRecorte(esquerda, topo, direita, base)


def _landmarks_dos_olhos_disponiveis(rosto: Rosto) -> bool:
    """Considera os olhos indisponíveis quando o YuNet devolve (0, 0), seu valor de ausência."""
    return rosto.olho_direito != (0.0, 0.0) and rosto.olho_esquerdo != (0.0, 0.0)


def _deslocar_para_dentro(
    esquerda: float,
    topo: float,
    direita: float,
    base: float,
    largura_imagem: int,
    altura_imagem: int,
) -> tuple[float, float, float, float]:
    """Desloca a janela para dentro da imagem preservando seu tamanho, sem encolher."""
    if esquerda < 0:
        deslocamento = -esquerda
        esquerda += deslocamento
        direita += deslocamento
    if direita > largura_imagem:
        deslocamento = direita - largura_imagem
        esquerda -= deslocamento
        direita -= deslocamento

    if topo < 0:
        deslocamento = -topo
        topo += deslocamento
        base += deslocamento
    if base > altura_imagem:
        deslocamento = base - altura_imagem
        topo -= deslocamento
        base -= deslocamento

    return esquerda, topo, direita, base
