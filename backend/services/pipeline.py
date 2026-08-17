"""Orquestra o processamento de uma pasta.

Toda imagem passa pela detecção facial — inclusive as que já estão em 3x4.
Só é aprovada quem tiver exatamente um rosto válido, e toda aprovação passa
pelo recorte guiado pela face: a proporção original da entrada nunca decide
nada, nem aprovação nem se o recorte é pulado.
"""

from pathlib import Path

from PIL import Image

from backend.schemas.resultado import Motivo, ResultadoItem, Status
from backend.services import crop_service, debug_service, face_service, image_service, storage
from backend.services.crop_service import JanelaRecorte, ResultadoRecorte
from backend.services.face_service import QualidadeDeteccao, Rosto

_MOTIVO_POR_QUALIDADE = {
    QualidadeDeteccao.NENHUM_ROSTO: Motivo.NENHUM_ROSTO,
    QualidadeDeteccao.MULTIPLOS_ROSTOS: Motivo.MULTIPLOS_ROSTOS,
    QualidadeDeteccao.ROSTO_PEQUENO: Motivo.ROSTO_PEQUENO,
    QualidadeDeteccao.ROSTO_LATERAL: Motivo.ROSTO_LATERAL,
}


def processar_pasta(pasta_base: Path) -> list[ResultadoItem]:
    """Processa todas as imagens elegíveis de pasta_base e retorna os resultados."""
    aprovadas, revisar, debug = storage.preparar_saida(pasta_base)
    entradas = storage.listar_entradas(pasta_base)
    return [_processar_arquivo(caminho, aprovadas, revisar, debug) for caminho in entradas]


def _processar_arquivo(caminho: Path, aprovadas: Path, revisar: Path, debug: Path) -> ResultadoItem:
    """Processa um único arquivo, isolando qualquer erro para não interromper o lote."""
    try:
        imagem = image_service.abrir_normalizada(caminho)
    except Exception:
        return ResultadoItem(
            arquivo_original=caminho.name,
            status=Status.ERRO,
            motivo=Motivo.ERRO_LEITURA,
        )

    largura_original, altura_original = imagem.width, imagem.height
    nome_saida = f"{caminho.stem}.png"

    try:
        status, motivo, final, info_recorte = _preparar_imagem_final(imagem)
        pasta_destino = aprovadas if status == Status.PRONTO else revisar
        destino = storage.caminho_disponivel(pasta_destino, nome_saida)
        image_service.salvar_png(final, destino)
        if info_recorte is not None:
            rosto, janela = info_recorte
            destino_debug = storage.caminho_disponivel(debug, nome_saida)
            debug_service.salvar_visualizacao(imagem, rosto, janela, destino_debug)
    except Exception:
        return ResultadoItem(
            arquivo_original=caminho.name,
            status=Status.ERRO,
            motivo=Motivo.ERRO_PROCESSAMENTO,
            largura_original=largura_original,
            altura_original=altura_original,
        )

    return ResultadoItem(
        arquivo_original=caminho.name,
        arquivo_saida=destino.name,
        status=status,
        motivo=motivo,
        largura_original=largura_original,
        altura_original=altura_original,
    )


_InfoRecorte = tuple[Rosto, JanelaRecorte] | None


def _preparar_imagem_final(imagem: Image.Image) -> tuple[Status, Motivo, Image.Image, _InfoRecorte]:
    """Decide status e motivo pela qualidade da detecção facial e devolve a imagem final.

    O quarto item devolvido é (rosto, janela) só quando o recorte guiado por
    rosto é de fato aplicado — usado por _processar_arquivo para gerar a
    imagem de depuração (ver debug_service).
    """
    rostos = face_service.detectar_rostos(imagem)
    qualidade = face_service.classificar_deteccao(rostos, imagem.height)

    if qualidade != QualidadeDeteccao.ROSTO_VALIDO:
        motivo = _MOTIVO_POR_QUALIDADE[qualidade]
        ja_em_3x4 = image_service.ja_esta_em_3x4(imagem)
        return Status.REVISAR, motivo, _imagem_para_revisao(imagem, ja_em_3x4), None

    janela, resultado_recorte = crop_service.calcular_janela(rostos[0], imagem.width, imagem.height)
    if resultado_recorte == ResultadoRecorte.OMBROS_CORTADOS:
        ja_em_3x4 = image_service.ja_esta_em_3x4(imagem)
        return Status.REVISAR, Motivo.OMBROS_CORTADOS, _imagem_para_revisao(imagem, ja_em_3x4), None

    motivo = (
        Motivo.ROSTO_VALIDO_RECORTADO
        if resultado_recorte == ResultadoRecorte.JANELA_VALIDA
        else Motivo.ROSTO_VALIDO_RECORTADO_AJUSTADO
    )
    caixa = (round(janela.esquerda), round(janela.topo), round(janela.direita), round(janela.base))
    recortada = image_service.recortar(imagem, caixa)
    final = image_service.redimensionar_para_saida(recortada)
    return Status.PRONTO, motivo, final, (rostos[0], janela)


def _imagem_para_revisao(imagem: Image.Image, ja_em_3x4: bool) -> Image.Image:
    """Prepara a imagem enviada para revisão: sem rosto válido, usa recorte central como fallback."""
    if ja_em_3x4:
        return image_service.redimensionar_para_saida(imagem)
    caixa = image_service.caixa_central_3x4(imagem.width, imagem.height)
    recortada = image_service.recortar(imagem, caixa)
    return image_service.redimensionar_para_saida(recortada)
