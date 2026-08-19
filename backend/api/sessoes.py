"""Rotas de sessão da API do Vision.

Casca fina sobre backend.services.sessao_service e backend.services.pipeline:
este módulo só traduz HTTP <-> chamadas de serviço, sem tomar nenhuma
decisão de processamento de imagem por conta própria.
"""

import shutil
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile
from fastapi.responses import Response

from backend import config
from backend.schemas.resultado import Motivo, Status
from backend.schemas.sessao import (
    ExportarRequest,
    ExportarResposta,
    ItemStatusResposta,
    ItemUploadResposta,
    PastaSugerida,
    PastasSugeridasResposta,
    ProcessarResposta,
    SessaoCriadaResposta,
    SessaoStatusResposta,
    UploadResposta,
    ValidarPastaRequest,
    ValidarPastaResposta,
)
from backend.services import sessao_service, storage
from backend.services.sessao_service import EstadoSessao, ItemSessao, Sessao

router = APIRouter(tags=["sessao"])


def _obter_sessao_ou_404(sessao_id: str) -> Sessao:
    sessao = sessao_service.store.obter(sessao_id)
    if sessao is None:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")
    return sessao


def _item_para_upload(item: ItemSessao) -> ItemUploadResposta:
    return ItemUploadResposta(
        item_id=item.item_id,
        arquivo_original=item.arquivo_original,
        status=item.status.value,
        origem=item.origem,
        total_candidatas=item.total_candidatas,
    )


def _item_para_status(item: ItemSessao) -> ItemStatusResposta:
    return ItemStatusResposta(
        item_id=item.item_id,
        arquivo_original=item.arquivo_original,
        arquivo_saida=item.arquivo_saida,
        status=item.status.value,
        motivo=(item.motivo or Motivo.NENHUM).value,
        origem=item.origem,
        detalhe=item.detalhe,
        largura_original=item.largura_original,
        altura_original=item.altura_original,
    )


@router.post("/sessao", response_model=SessaoCriadaResposta)
def criar_sessao() -> SessaoCriadaResposta:
    """Cria uma sessão de trabalho isolada (pasta temporária própria) e devolve seu id."""
    sessao = sessao_service.store.criar()
    return SessaoCriadaResposta(id=sessao.id)


@router.post("/sessao/{sessao_id}/arquivos", response_model=UploadResposta)
async def enviar_arquivos(sessao_id: str, arquivos: list[UploadFile] = File(...)) -> UploadResposta:
    """Recebe upload de imagens/PDFs, guarda na pasta da sessão e devolve os itens (Status.AGUARDANDO)."""
    sessao = _obter_sessao_ou_404(sessao_id)
    if sessao.estado != EstadoSessao.AGUARDANDO:
        raise HTTPException(
            status_code=409, detail="Sessão já está processando ou já foi concluída — não aceita mais arquivos"
        )
    if not arquivos:
        raise HTTPException(status_code=400, detail="Nenhum arquivo enviado")

    formatos_aceitos = config.FORMATOS_IMAGEM | config.FORMATOS_PDF
    for arquivo in arquivos:
        nome = Path(arquivo.filename or "").name
        if not nome or Path(nome).suffix.lower() not in formatos_aceitos:
            raise HTTPException(status_code=400, detail=f"Formato não suportado: {arquivo.filename!r}")

    for arquivo in arquivos:
        nome = Path(arquivo.filename).name
        conteudo = await arquivo.read()
        (sessao.pasta / nome).write_bytes(conteudo)

    sessao_service.reconstruir_itens(sessao)
    return UploadResposta(itens=[_item_para_upload(item) for item in sessao.listar_itens()])


@router.post("/sessao/{sessao_id}/processar", response_model=ProcessarResposta)
def processar(sessao_id: str, tarefas: BackgroundTasks) -> ProcessarResposta:
    """Dispara o processamento da sessão em background; o progresso é consultado via GET /status."""
    sessao = _obter_sessao_ou_404(sessao_id)
    if sessao.estado != EstadoSessao.AGUARDANDO:
        raise HTTPException(status_code=409, detail="Sessão já está processando ou já foi concluída")
    if not sessao.listar_itens():
        raise HTTPException(status_code=400, detail="Sessão vazia — envie arquivos antes de processar")

    sessao.estado = EstadoSessao.PROCESSANDO
    tarefas.add_task(sessao_service.processar_em_background, sessao_id)
    return ProcessarResposta(estado=sessao.estado.value)


@router.get("/sessao/{sessao_id}/status", response_model=SessaoStatusResposta)
def status(sessao_id: str) -> SessaoStatusResposta:
    """Progresso e status de cada item da sessão — para o frontend fazer polling."""
    sessao = _obter_sessao_ou_404(sessao_id)
    itens = sessao.listar_itens()
    concluidos = sum(1 for item in itens if item.status != Status.AGUARDANDO)
    return SessaoStatusResposta(
        estado=sessao.estado.value,
        total=len(itens),
        concluidos=concluidos,
        itens=[_item_para_status(item) for item in itens],
    )


@router.get("/sessao/{sessao_id}/preview/{item_id}")
def preview(sessao_id: str, item_id: str, versao: Literal["processada", "original"] = "processada") -> Response:
    """Devolve a imagem original ou a já processada de um item, para exibição no frontend."""
    sessao = _obter_sessao_ou_404(sessao_id)
    item = sessao.obter_item(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item não encontrado nesta sessão")

    if versao == "processada":
        if item.caminho_processado is None or not item.caminho_processado.exists():
            raise HTTPException(status_code=404, detail="Item ainda não tem saída processada")
        return Response(content=item.caminho_processado.read_bytes(), media_type="image/png")

    conteudo, media_type = sessao_service.gerar_preview_original(item)
    if conteudo is None:
        raise HTTPException(status_code=404, detail="Não foi possível gerar a imagem original deste item")
    return Response(content=conteudo, media_type=media_type)


@router.post("/sessao/{sessao_id}/exportar", response_model=ExportarResposta)
def exportar(sessao_id: str, corpo: ExportarRequest) -> ExportarResposta:
    """Copia a pasta de saída da sessão (aprovadas, revisar, debug, CSV) para a pasta escolhida pelo usuário."""
    sessao = _obter_sessao_ou_404(sessao_id)
    if sessao.estado != EstadoSessao.CONCLUIDO:
        raise HTTPException(status_code=409, detail="Sessão ainda não foi processada")

    destino = Path(corpo.pasta_destino)
    valida, mensagem = storage.validar_pasta_destino(destino)
    if not valida:
        raise HTTPException(status_code=400, detail=mensagem)

    if sessao.pasta_saida is None or not sessao.pasta_saida.exists():
        raise HTTPException(status_code=500, detail="Sessão concluída sem pasta de saída — reprocesse")

    destino_final = destino / sessao.pasta_saida.name
    shutil.copytree(sessao.pasta_saida, destino_final, dirs_exist_ok=True)

    return ExportarResposta(
        pasta_saida=str(destino_final),
        relatorio=str(destino_final / config.NOME_RELATORIO),
    )


@router.get("/pastas-sugeridas", response_model=PastasSugeridasResposta, tags=["pastas"])
def pastas_sugeridas() -> PastasSugeridasResposta:
    """Atalhos de pasta do usuário atual (Área de trabalho, Documentos, Downloads), para o modal de exportação."""
    pastas = [PastaSugerida(nome=nome, caminho=str(caminho)) for nome, caminho in storage.pastas_sugeridas()]
    return PastasSugeridasResposta(pastas=pastas)


@router.post("/validar-pasta", response_model=ValidarPastaResposta, tags=["pastas"])
def validar_pasta(corpo: ValidarPastaRequest) -> ValidarPastaResposta:
    """Confirma que o caminho informado existe e aceita escrita, para feedback imediato no campo de destino."""
    valida, mensagem = storage.validar_pasta_destino(Path(corpo.caminho))
    return ValidarPastaResposta(valida=valida, mensagem=mensagem)


@router.delete("/sessao/{sessao_id}", status_code=204)
def remover_sessao(sessao_id: str) -> Response:
    """Apaga a sessão e os temporários associados a ela."""
    _obter_sessao_ou_404(sessao_id)
    sessao_service.store.remover(sessao_id)
    return Response(status_code=204)
