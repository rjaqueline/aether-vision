"""Gera imagens de depuração para calibrar o recorte guiado por rosto.

Para cada foto aprovada, desenha sobre a imagem original a caixa do rosto
detectado e a janela de recorte calculada — permite conferir visualmente se
FATOR_ALTURA_JANELA e FATOR_MARGEM_TOPO (ver config.py) estão bem calibrados.
"""

from pathlib import Path

from PIL import Image, ImageDraw

from backend.services.crop_service import JanelaRecorte
from backend.services.face_service import Rosto

_COR_ROSTO = (255, 0, 0)  # vermelho: caixa do rosto detectado
_COR_JANELA = (0, 200, 0)  # verde: janela de recorte calculada
_ESPESSURA_LINHA = 4


def salvar_visualizacao(imagem: Image.Image, rosto: Rosto, janela: JanelaRecorte, destino: Path) -> None:
    """Desenha as duas caixas sobre uma cópia da imagem original e salva em destino."""
    visualizacao = imagem.copy()
    desenho = ImageDraw.Draw(visualizacao)

    caixa_rosto = (rosto.x, rosto.y, rosto.x + rosto.largura, rosto.y + rosto.altura)
    desenho.rectangle(caixa_rosto, outline=_COR_ROSTO, width=_ESPESSURA_LINHA)

    caixa_janela = (janela.esquerda, janela.topo, janela.direita, janela.base)
    desenho.rectangle(caixa_janela, outline=_COR_JANELA, width=_ESPESSURA_LINHA)

    visualizacao.save(destino, format="PNG")
