"""Funções puras de manipulação de pixels: abrir, normalizar, medir proporção, recortar e redimensionar.

Este módulo não sabe nada sobre pastas, relatórios ou fluxo de aprovação — só imagens.
"""

from pathlib import Path

from PIL import Image, ImageOps

from backend import config

try:
    _RESAMPLE_LANCZOS = Image.Resampling.LANCZOS
except AttributeError:  # Pillow < 9.1
    _RESAMPLE_LANCZOS = Image.LANCZOS


def abrir_normalizada(caminho: Path) -> Image.Image:
    """Abre a imagem, aplica a orientação EXIF e converte para RGB.

    exif_transpose evita que fotos de celular apareçam giradas; a conversão
    para RGB garante que PNGs com transparência ou modos exóticos não quebrem
    o restante do pipeline.
    """
    imagem = Image.open(caminho)
    imagem = ImageOps.exif_transpose(imagem)
    return imagem.convert("RGB")


def ja_esta_em_3x4(imagem: Image.Image) -> bool:
    """Verifica se a proporção da imagem já é 3x4 dentro da tolerância configurada."""
    proporcao = imagem.width / imagem.height
    desvio = abs(proporcao - config.PROPORCAO_ALVO) / config.PROPORCAO_ALVO
    return desvio <= config.TOLERANCIA_PROPORCAO


def caixa_central_3x4(largura: int, altura: int) -> tuple[int, int, int, int]:
    """Calcula a maior caixa 3x4 centralizada que cabe dentro da imagem, sem estourar borda.

    Usada como recorte de fallback quando a imagem vai para revisão sem um
    rosto válido guiando o enquadramento (ver pipeline.py).
    """
    proporcao_atual = largura / altura

    if proporcao_atual > config.PROPORCAO_ALVO:
        # imagem "larga demais" para 3x4: mantém a altura inteira e corta a largura
        altura_caixa = altura
        largura_caixa = round(altura * config.PROPORCAO_ALVO)
    else:
        # imagem "alta demais" para 3x4: mantém a largura inteira e corta a altura
        largura_caixa = largura
        altura_caixa = round(largura / config.PROPORCAO_ALVO)

    largura_caixa = min(largura_caixa, largura)
    altura_caixa = min(altura_caixa, altura)

    esquerda = (largura - largura_caixa) // 2
    topo = (altura - altura_caixa) // 2

    return esquerda, topo, esquerda + largura_caixa, topo + altura_caixa


def recortar(imagem: Image.Image, caixa: tuple[int, int, int, int]) -> Image.Image:
    """Aplica um recorte a partir de (esquerda, topo, direita, base), preso aos limites da imagem."""
    esquerda, topo, direita, base = caixa
    esquerda = max(0, esquerda)
    topo = max(0, topo)
    direita = min(imagem.width, direita)
    base = min(imagem.height, base)
    return imagem.crop((esquerda, topo, direita, base))


def redimensionar_para_saida(imagem: Image.Image) -> Image.Image:
    """Redimensiona para as dimensões finais exatas (200x267) usando LANCZOS.

    Único lugar que decide o tamanho final — garante por construção que toda
    saída tem exatamente LARGURA_FINAL x ALTURA_FINAL, independente da
    entrada. 200x267 não é um 3x4 matematicamente exato: 267 é o
    arredondamento de 266,67 (200 / PROPORCAO_ALVO) para pixel inteiro, um
    desvio de ~0,1% aceito deliberadamente (ver config.py).
    """
    return imagem.resize((config.LARGURA_FINAL, config.ALTURA_FINAL), _RESAMPLE_LANCZOS)


def salvar_png(imagem: Image.Image, caminho: Path) -> None:
    """Salva a imagem como PNG no caminho informado."""
    imagem.save(caminho, format="PNG")
