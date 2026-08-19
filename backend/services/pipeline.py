"""Orquestra o processamento de uma pasta.

Toda imagem passa pela detecção facial — inclusive as que já estão em 3x4.
Só é aprovada quem tiver exatamente um rosto válido, e toda aprovação passa
pelo recorte guiado pela face: a proporção original da entrada nunca decide
nada, nem aprovação nem se o recorte é pulado.

PDFs viram uma imagem por página (ver pdf_service): cada página é um
ResultadoItem independente, com `origem` registrando de onde veio a imagem
("página N (imagem embutida)" ou "página N (rasterizada)") e o nome do
arquivo de saída incluindo o número da página.
"""

import logging
from pathlib import Path
from typing import Callable

import pymupdf
from PIL import Image

from backend import config
from backend.schemas.resultado import Motivo, ResultadoItem, Status
from backend.services import crop_service, debug_service, face_service, image_service, pdf_service, storage
from backend.services.crop_service import JanelaRecorte, ResultadoRecorte
from backend.services.face_service import QualidadeDeteccao, Rosto

_logger = logging.getLogger(__name__)

# Chamado depois de um item (arquivo de imagem ou página de PDF) estar
# completamente resolvido — arquivo já salvo em disco, ResultadoItem já
# montado — com (item, indice_arquivo, total_arquivos, numero_pagina).
# numero_pagina é 1-based e vem do laço de páginas que o pipeline está
# processando agora mesmo (não de uma contagem prévia); é None para arquivo
# de imagem direto. Junto com item.arquivo_original, dá a quem chama uma
# chave estável — (arquivo_original, numero_pagina) — para correlacionar
# este resultado a algo que ela mesma tenha pré-registrado antes de chamar
# processar_pasta, sem depender da ordem de chegada das notificações (ver
# backend/services/sessao_service.py).
_CallbackProgresso = Callable[[ResultadoItem, int, int, int | None], None]

_MOTIVO_POR_QUALIDADE = {
    QualidadeDeteccao.NENHUM_ROSTO: Motivo.NENHUM_ROSTO,
    QualidadeDeteccao.MULTIPLOS_ROSTOS: Motivo.MULTIPLOS_ROSTOS,
    QualidadeDeteccao.ROSTO_PEQUENO: Motivo.ROSTO_PEQUENO,
    QualidadeDeteccao.ROSTO_LATERAL: Motivo.ROSTO_LATERAL,
}


def processar_pasta(
    pasta_base: Path,
    on_item_processado: _CallbackProgresso | None = None,
    pasta_saida: Path | None = None,
) -> list[ResultadoItem]:
    """Processa todas as imagens e PDFs elegíveis de pasta_base e retorna os resultados.

    on_item_processado é opcional (default None não muda em nada o
    comportamento de hoje) e, se informado, é chamado a cada item já
    completamente resolvido — ver _CallbackProgresso. indice_arquivo/
    total_arquivos contam arquivos de entrada, não páginas de PDF: para um
    PDF de várias páginas, todos os itens daquele arquivo compartilham o
    mesmo (indice_arquivo, total_arquivos), porque descobrir o total de
    páginas de antemão exigiria abrir todo PDF antes de começar a processar
    o lote — o que esta função evita. numero_pagina (1-based, None fora de
    PDF) é a chave estável para quem chama correlacionar o resultado a algo
    pré-registrado antes do processamento começar.

    pasta_saida é opcional: se omitida, é criada agora mesmo com
    storage.nome_pasta_saida(). Quem chama e precisa saber o caminho de
    antemão (ex.: sessao_service, para o callback de progresso; cli, para o
    relatório) deve calculá-lo antes e passar aqui, garantindo que seja
    exatamente a mesma pasta usada nos dois lugares.
    """
    pasta_saida = pasta_saida or (pasta_base / storage.nome_pasta_saida())
    aprovadas, revisar, debug = storage.preparar_saida(pasta_saida)
    entradas = storage.listar_entradas(pasta_base)
    total_arquivos = len(entradas)

    resultados = []
    for indice_arquivo, caminho in enumerate(entradas, start=1):
        try:
            if caminho.suffix.lower() in config.FORMATOS_PDF:
                resultados.extend(
                    _processar_pdf(
                        caminho, aprovadas, revisar, debug, on_item_processado, indice_arquivo, total_arquivos
                    )
                )
            else:
                item = _processar_arquivo(caminho, aprovadas, revisar, debug)
                _chamar_callback(on_item_processado, item, indice_arquivo, total_arquivos, None)
                resultados.append(item)
        except Exception:
            # Isolamento por item: qualquer regressão não prevista em
            # _processar_pdf/_processar_arquivo (ex.: falha em page_count, ou
            # ao fechar o documento) vira um item de erro em vez de derrubar
            # o lote inteiro.
            item = ResultadoItem(
                arquivo_original=caminho.name,
                status=Status.ERRO,
                motivo=Motivo.FALHA_INESPERADA,
            )
            _chamar_callback(on_item_processado, item, indice_arquivo, total_arquivos, None)
            resultados.append(item)
    return resultados


def _chamar_callback(
    on_item_processado: _CallbackProgresso | None,
    item: ResultadoItem,
    indice_arquivo: int,
    total_arquivos: int,
    numero_pagina: int | None,
) -> None:
    """Invoca o callback de progresso, se houver, sem deixar uma falha nele afetar o lote.

    O callback é um observador (ex.: atualizar o status de uma sessão da
    API), não um participante do processamento — uma exceção nele é
    registrada e engolida, nunca propaga.
    """
    if on_item_processado is None:
        return
    try:
        on_item_processado(item, indice_arquivo, total_arquivos, numero_pagina)
    except Exception:
        _logger.exception("Callback de progresso falhou para o item %r", item.arquivo_original)


def _processar_arquivo(caminho: Path, aprovadas: Path, revisar: Path, debug: Path) -> ResultadoItem:
    """Processa um único arquivo de imagem, isolando qualquer erro para não interromper o lote."""
    try:
        imagem = image_service.abrir_normalizada(caminho)
    except Exception:
        return ResultadoItem(
            arquivo_original=caminho.name,
            status=Status.ERRO,
            motivo=Motivo.ERRO_LEITURA,
        )

    nome_saida = f"{caminho.stem}.png"
    return _processar_imagem(caminho.name, imagem, nome_saida, "", aprovadas, revisar, debug)


def _processar_pdf(
    caminho: Path,
    aprovadas: Path,
    revisar: Path,
    debug: Path,
    on_item_processado: _CallbackProgresso | None,
    indice_arquivo: int,
    total_arquivos: int,
) -> list[ResultadoItem]:
    """Processa todas as páginas de um PDF, cada uma virando um ResultadoItem independente.

    Notifica on_item_processado por página, assim que cada uma termina — não
    espera o PDF inteiro para notificar, senão um PDF de muitas páginas
    ficaria "parado" no progresso até a última página terminar.
    """
    try:
        documento = pdf_service.abrir(caminho)
    except pdf_service.PdfProtegidoError:
        item = ResultadoItem(arquivo_original=caminho.name, status=Status.ERRO, motivo=Motivo.PDF_PROTEGIDO)
        _chamar_callback(on_item_processado, item, indice_arquivo, total_arquivos, None)
        return [item]
    except pdf_service.PdfCorrompidoError:
        item = ResultadoItem(arquivo_original=caminho.name, status=Status.ERRO, motivo=Motivo.PDF_CORROMPIDO)
        _chamar_callback(on_item_processado, item, indice_arquivo, total_arquivos, None)
        return [item]

    try:
        itens = []
        for indice in range(documento.page_count):
            item = _processar_pagina_pdf(caminho, documento, indice, aprovadas, revisar, debug)
            _chamar_callback(on_item_processado, item, indice_arquivo, total_arquivos, indice + 1)
            itens.append(item)
        return itens
    finally:
        documento.close()


def _processar_pagina_pdf(
    caminho: Path, documento: pymupdf.Document, indice: int, aprovadas: Path, revisar: Path, debug: Path
) -> ResultadoItem:
    """Resolve e processa uma única página de PDF, isolando qualquer erro para não travar as demais."""
    numero = indice + 1
    try:
        pagina = pdf_service.resolver_pagina(documento, indice)
    except Exception:
        return ResultadoItem(
            arquivo_original=caminho.name,
            status=Status.ERRO,
            motivo=Motivo.ERRO_PROCESSAMENTO,
            origem=f"página {numero}",
        )

    nome_saida = f"{caminho.stem}_pagina_{numero:02d}.png"
    origem = _descrever_origem(numero, pagina.origem, pagina.candidatas_descartadas)
    return _processar_imagem(caminho.name, pagina.imagem, nome_saida, origem, aprovadas, revisar, debug)


def _descrever_origem(numero: int, origem: pdf_service.OrigemTipo, candidatas_descartadas: int) -> str:
    """Monta a string de rastreabilidade que aparece na coluna `origem` do relatório.

    Para páginas rasterizadas, distingue "nenhuma imagem embutida" de "tinha
    imagem embutida, mas o filtro descartou todas" — essa segunda situação é
    o sinal de alerta: se aparecer muito em produção, os filtros de
    área/proporção (ver pdf_service) estão calibrados errado para os PDFs
    reais, não é um scan de verdade.
    """
    if origem == pdf_service.OrigemTipo.RASTERIZADA:
        if candidatas_descartadas == 0:
            return f"página {numero} (rasterizada — nenhuma candidata válida)"
        return f"página {numero} (rasterizada — {candidatas_descartadas} candidata(s) descartada(s) por filtro)"
    if candidatas_descartadas > 0:
        return f"página {numero} (imagem embutida, {candidatas_descartadas} candidata(s) descartada(s))"
    return f"página {numero} (imagem embutida)"


def _processar_imagem(
    arquivo_original: str,
    imagem: Image.Image,
    nome_saida: str,
    origem: str,
    aprovadas: Path,
    revisar: Path,
    debug: Path,
) -> ResultadoItem:
    """Leva uma imagem já aberta (de arquivo direto ou de página de PDF) até o resultado final."""
    largura_original, altura_original = imagem.width, imagem.height

    try:
        status, motivo, final, info_recorte = _preparar_imagem_final(imagem)
        pasta_destino = aprovadas if status == Status.PRONTO else revisar
        destino = storage.caminho_disponivel(pasta_destino, nome_saida)
        image_service.salvar_png(final, destino)
    except Exception:
        return ResultadoItem(
            arquivo_original=arquivo_original,
            status=Status.ERRO,
            motivo=Motivo.ERRO_PROCESSAMENTO,
            largura_original=largura_original,
            altura_original=altura_original,
            origem=origem,
        )

    # A saída aprovada/revisar já está gravada em disco neste ponto. A
    # imagem de debug é só um auxiliar de calibração (ver debug_service): se
    # falhar aqui, não pode virar Status.ERRO e deixar o CSV dizendo que o
    # item falhou enquanto o PNG aprovado continua no disco — vira apenas uma
    # observação não-fatal em `detalhe`, o status/motivo originais são mantidos.
    detalhe = ""
    if info_recorte is not None:
        rosto, janela = info_recorte
        try:
            destino_debug = storage.caminho_disponivel(debug, nome_saida)
            debug_service.salvar_visualizacao(imagem, rosto, janela, destino_debug)
        except Exception as erro:
            detalhe = f"Falha ao gerar imagem de depuração: {erro}"

    return ResultadoItem(
        arquivo_original=arquivo_original,
        arquivo_saida=destino.name,
        status=status,
        motivo=motivo,
        largura_original=largura_original,
        altura_original=altura_original,
        origem=origem,
        detalhe=detalhe,
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
    """Prepara a imagem enviada para revisão: sem rosto válido, usa recorte central como fallback.

    ja_em_3x4 só decide o que aparece nesta miniatura de revisão manual —
    pular o recorte central quando a entrada já é 3x4, em vez de aplicá-lo
    sem necessidade. Não afeta status/motivo (já decididos pela detecção
    facial antes de chegar aqui) nem qualquer caminho de aprovação: uma
    imagem aprovada (Status.PRONTO) é sempre recortada guiada pelo rosto,
    nunca por caixa_central_3x4/ja_esta_em_3x4.
    """
    if ja_em_3x4:
        return image_service.redimensionar_para_saida(imagem)
    caixa = image_service.caixa_central_3x4(imagem.width, imagem.height)
    recortada = image_service.recortar(imagem, caixa)
    return image_service.redimensionar_para_saida(recortada)
