"""Extrai fotos de empregado de arquivos PDF, uma por página.

Cada página é resolvida para uma única imagem candidata, em ordem de
preferência:

  1. Imagem embutida na página (caso do PDF digital — formulário do Word
     virado PDF, com a foto colada nele). Candidatas óbvias demais para
     serem foto (logos, ícones, assinaturas, cabeçalhos/rodapés, carimbos)
     são descartadas antes de escolher.
  2. Se não sobrar nenhuma candidata, a página inteira é rasterizada a
     DPI_RASTERIZACAO_PDF (caso do PDF escaneado) — a detecção facial do
     pipeline localiza o rosto dentro da página.

Nunca usa Image.frombytes(pixmap.samples, ...): o layout de bytes muda com o
colorspace (RGB, CMYK, cinza) e com a presença de canal alpha, então essa
chamada quebra silenciosamente ou lança exceção fora desses casos simples.
pixmap.tobytes("png") + Image.open lida com qualquer colorspace porque quem
faz a conversão é o próprio MuPDF.
"""

from dataclasses import dataclass
from enum import Enum
from io import BytesIO
from pathlib import Path

import pymupdf
from PIL import Image

from backend import config
from backend.services import face_service


class OrigemTipo(str, Enum):
    """De onde veio a imagem final de uma página do PDF."""

    IMAGEM_EMBUTIDA = "imagem embutida"
    RASTERIZADA = "rasterizada"


@dataclass
class PaginaPdf:
    """Uma página de PDF já resolvida para uma única imagem candidata a foto.

    candidatas_descartadas tem sentido diferente conforme a origem: em
    IMAGEM_EMBUTIDA é quantas outras candidatas válidas perderam para a
    escolhida (por rosto válido, com desempate por área — ver
    _escolher_candidata); em RASTERIZADA é quantas imagens embutidas existiam
    na página e nenhuma passou no filtro — 0 significa que a página não tinha
    nenhuma imagem embutida. Essa distinção vai para o campo `origem` do
    relatório (ver pipeline._descrever_origem): muitas rasterizações por
    filtro, em vez de por ausência de imagem, é sinal de que
    AREA_MINIMA_CANDIDATA_PDF/PROPORCAO_*_CANDIDATA_PDF estão calibrados
    errado para os PDFs reais.
    """

    numero: int  # 1-based — é o que o usuário vê num leitor de PDF
    imagem: Image.Image
    origem: OrigemTipo
    candidatas_descartadas: int = 0


class PdfProtegidoError(Exception):
    """PDF exige senha que não temos como fornecer."""


class PdfCorrompidoError(Exception):
    """PDF não pôde ser aberto: arquivo corrompido ou não é um PDF válido."""


def abrir(caminho: Path) -> pymupdf.Document:
    """Abre o PDF e devolve o documento pronto para resolver_pagina.

    Levanta PdfCorrompidoError ou PdfProtegidoError se o documento não puder
    ser processado. Quem chama é responsável por fechar o documento (use
    try/finally — documento aberto trava o arquivo no Windows).
    """
    try:
        documento = pymupdf.open(caminho)
    except Exception as erro:
        raise PdfCorrompidoError(str(erro)) from erro

    if documento.needs_pass:
        documento.close()
        raise PdfProtegidoError("PDF protegido por senha")

    return documento


def resolver_pagina(documento: pymupdf.Document, indice: int) -> PaginaPdf:
    """Resolve a página `indice` (0-based) para uma única imagem candidata a foto."""
    pagina = documento[indice]
    candidatas, total_imagens_pagina = _extrair_candidatas(documento, pagina)

    if len(candidatas) == 0:
        imagem = _rasterizar_pagina(pagina)
        return PaginaPdf(
            numero=indice + 1,
            imagem=imagem,
            origem=OrigemTipo.RASTERIZADA,
            candidatas_descartadas=total_imagens_pagina,
        )

    escolhida = _escolher_candidata(candidatas)
    return PaginaPdf(
        numero=indice + 1,
        imagem=escolhida,
        origem=OrigemTipo.IMAGEM_EMBUTIDA,
        candidatas_descartadas=len(candidatas) - 1,
    )


def _escolher_candidata(candidatas: list[Image.Image]) -> Image.Image:
    """Escolhe, entre as candidatas que passaram no filtro, a mais provável de ser a foto do empregado.

    Escolher sempre a maior por área pode pegar um fundo ou ilustração maior
    que a própria foto. Com mais de uma candidata, roda a detecção facial em
    cada uma e prefere a única que tiver um rosto válido. Havendo empate
    (mais de uma com rosto válido) ou nenhuma com rosto, não há como decidir
    por rosto — cai de volta para a maior por área, como antes.
    """
    if len(candidatas) == 1:
        return candidatas[0]

    com_rosto_valido = [imagem for imagem in candidatas if _tem_rosto_valido(imagem)]
    if len(com_rosto_valido) == 1:
        return com_rosto_valido[0]

    return max(candidatas, key=lambda imagem: imagem.width * imagem.height)


def _tem_rosto_valido(imagem: Image.Image) -> bool:
    """Roda a detecção facial numa candidata isolada e diz se ela tem exatamente um rosto válido."""
    rostos = face_service.detectar_rostos(imagem)
    qualidade = face_service.classificar_deteccao(rostos, imagem.height)
    return qualidade == face_service.QualidadeDeteccao.ROSTO_VALIDO


def _extrair_candidatas(documento: pymupdf.Document, pagina: pymupdf.Page) -> tuple[list[Image.Image], int]:
    """Extrai as imagens embutidas da página e descarta as que não parecem foto de empregado.

    Devolve também o total de imagens embutidas encontradas na página (antes
    do filtro), para distinguir "página sem nenhuma imagem embutida" de
    "página com imagens embutidas, mas nenhuma passou no filtro".
    """
    imagens_pagina = pagina.get_images(full=True)
    candidatas = []
    for xref, *_ in imagens_pagina:
        if _e_1_bit(documento, xref):  # carimbo ou scan de texto, não foto
            continue
        try:
            pixmap = pymupdf.Pixmap(documento, xref)
            imagem = _pixmap_para_pil(pixmap)
        except Exception:
            continue
        if _e_candidata_valida(imagem):
            candidatas.append(imagem.convert("RGB"))
    return candidatas, len(imagens_pagina)


def _e_1_bit(documento: pymupdf.Document, xref: int) -> bool:
    """Verifica se a imagem embutida é 1 bit por pixel (bilevel), direto no objeto do PDF.

    Precisa ser checado assim, e não no modo do PIL depois de extraído: o
    Pixmap do MuPDF sempre decodifica para 8 bits por amostra, então depois
    da conversão a imagem já chega ao Pillow como modo "L" — o sinal de que
    era 1 bit já se perdeu nessa altura.
    """
    tipo, valor = documento.xref_get_key(xref, "BitsPerComponent")
    return tipo == "int" and valor == "1"


def _e_candidata_valida(imagem: Image.Image) -> bool:
    """Filtra logos, ícones, assinaturas e cabeçalhos/rodapés — não são foto de empregado."""
    area = imagem.width * imagem.height
    if area < config.AREA_MINIMA_CANDIDATA_PDF:
        return False

    proporcao = imagem.width / imagem.height
    if not (config.PROPORCAO_MINIMA_CANDIDATA_PDF <= proporcao <= config.PROPORCAO_MAXIMA_CANDIDATA_PDF):
        return False

    return True


def _rasterizar_pagina(pagina: pymupdf.Page) -> Image.Image:
    """Rasteriza a página inteira a DPI_RASTERIZACAO_PDF — caso do PDF escaneado."""
    zoom = config.DPI_RASTERIZACAO_PDF / 72  # 72 pontos por polegada é a unidade nativa do PDF
    pixmap = pagina.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom))
    return _pixmap_para_pil(pixmap).convert("RGB")


def _pixmap_para_pil(pixmap: pymupdf.Pixmap) -> Image.Image:
    """Converte um Pixmap para PIL via PNG — evita frombytes(samples), que quebra em CMYK/alpha."""
    return Image.open(BytesIO(pixmap.tobytes("png")))
