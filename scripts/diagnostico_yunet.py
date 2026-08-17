"""Diagnóstico isolado do detector YuNet: compara a confiança da detecção
com a imagem no tamanho original vs. pré-redimensionada para no máximo
LADO_MAXIMO px no maior lado, escalando a caixa de volta ao final.

Não usa face_service nem o pipeline — cria detectores YuNet à parte para
cada variante, com score_threshold=0.0 para sempre ver a confiança real,
mesmo quando ela ficaria abaixo do limiar configurado.

Ferramenta de diagnóstico, não faz parte do sistema — por isso mora fora do
pacote backend.

Uso: python scripts/diagnostico_yunet.py "caminho/da/pasta"
"""

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import config

LADO_MAXIMO = 800


def _abrir(caminho: Path) -> np.ndarray:
    imagem = Image.open(caminho)
    imagem = ImageOps.exif_transpose(imagem)
    imagem = imagem.convert("RGB")
    return cv2.cvtColor(np.array(imagem), cv2.COLOR_RGB2BGR)


def _detectar(imagem_bgr: np.ndarray) -> tuple[float | None, int]:
    """Roda o YuNet com score_threshold=0.0 e devolve (maior confiança, nº de rostos)."""
    altura, largura = imagem_bgr.shape[:2]
    detector = cv2.FaceDetectorYN.create(
        str(config.CAMINHO_MODELO_YUNET),
        "",
        (largura, altura),
        score_threshold=0.0,
        nms_threshold=config.NMS_LIMIAR_IOU,
        top_k=config.TOP_K_ROSTOS,
    )
    _, deteccoes = detector.detect(imagem_bgr)
    if deteccoes is None or len(deteccoes) == 0:
        return None, 0
    confiancas = [float(linha[14]) for linha in deteccoes]
    return max(confiancas), len(deteccoes)


def _redimensionar(imagem_bgr: np.ndarray, lado_maximo: int) -> np.ndarray:
    altura, largura = imagem_bgr.shape[:2]
    escala = lado_maximo / max(altura, largura)
    if escala >= 1.0:
        return imagem_bgr
    nova_largura = round(largura * escala)
    nova_altura = round(altura * escala)
    return cv2.resize(imagem_bgr, (nova_largura, nova_altura), interpolation=cv2.INTER_AREA)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compara confiança do YuNet com/sem pré-redimensionamento.")
    parser.add_argument("pasta", help="Pasta com as imagens a testar")
    args = parser.parse_args(argv)

    pasta = Path(args.pasta)
    if not pasta.is_dir():
        print(f"Erro: pasta não encontrada: {pasta}")
        return 1

    arquivos = sorted(p for p in pasta.iterdir() if p.suffix.lower() in config.FORMATOS_IMAGEM)
    if not arquivos:
        print("Nenhuma imagem encontrada na pasta.")
        return 1

    linhas = []
    for caminho in arquivos:
        imagem_bgr = _abrir(caminho)
        altura, largura = imagem_bgr.shape[:2]

        conf_original, n_original = _detectar(imagem_bgr)

        imagem_redim = _redimensionar(imagem_bgr, LADO_MAXIMO)
        conf_redim, n_redim = _detectar(imagem_redim)

        linhas.append((caminho.name, largura, altura, n_original, conf_original, n_redim, conf_redim))

    cab = f"{'arquivo':35} {'dimensoes':12} {'orig(n/conf)':16} {'800px(n/conf)':16}"
    print(cab)
    print("-" * len(cab))
    for nome, largura, altura, n_o, c_o, n_r, c_r in linhas:
        dim = f"{largura}x{altura}"
        orig = f"{n_o}/{c_o:.3f}" if c_o is not None else f"{n_o}/--"
        redim = f"{n_r}/{c_r:.3f}" if c_r is not None else f"{n_r}/--"
        print(f"{nome:35} {dim:12} {orig:16} {redim:16}")

    print()
    print(f"Limiar configurado atualmente: CONFIANCA_MINIMA_ROSTO = {config.CONFIANCA_MINIMA_ROSTO}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
