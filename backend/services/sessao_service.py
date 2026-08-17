"""Gerencia as sessões de trabalho da API local: pasta temporária isolada por
sessão, itens esperados (imagem direta ou página de PDF) e o progresso do
processamento em background sobre backend.services.pipeline.

É uma camada de estado em cima do pipeline existente — não reimplementa
nenhuma decisão de processamento de imagem, só rastreia o que o pipeline já
decide e mantém isso disponível para a API (ver backend/api/sessoes.py)
consultar via polling.
"""

import logging
import mimetypes
import shutil
import tempfile
import threading
import uuid
from dataclasses import dataclass, field
from enum import Enum
from io import BytesIO
from pathlib import Path

from backend import config
from backend.schemas.resultado import Motivo, ResultadoItem, Status
from backend.services import pdf_service, pipeline, report_service, storage

_logger = logging.getLogger(__name__)

_NOME_PASTA_BASE_SESSOES = "vision_api_sessoes"


class EstadoSessao(str, Enum):
    """Estado geral de uma sessão de trabalho."""

    AGUARDANDO = "aguardando"
    PROCESSANDO = "processando"
    CONCLUIDO = "concluido"


@dataclass
class ItemSessao:
    """Um item esperado da sessão: um arquivo de imagem enviado direto, ou uma página de PDF.

    Pré-registrado no upload (ver reconstruir_itens) com status AGUARDANDO, e
    depois atualizado quando o ResultadoItem correspondente chega via o
    callback de progresso do pipeline — correlacionado por chave estável
    (arquivo_original, número da página), não por posição/ordem de chegada
    (ver _chave_item e processar_em_background). arquivo_original +
    pagina_indice já são, juntos, essa chave.
    """

    item_id: str
    arquivo_original: str
    caminho_arquivo: Path  # arquivo salvo na pasta da sessão (a imagem, ou o PDF de origem)
    pagina_indice: int | None = None  # 0-based; None para arquivo de imagem enviado direto
    total_candidatas: int | None = None  # só para página de PDF (ver pdf_service.inspecionar_paginas)
    status: Status = Status.AGUARDANDO
    motivo: Motivo | None = None
    arquivo_saida: str = ""
    origem: str = ""
    detalhe: str = ""
    largura_original: int = 0
    altura_original: int = 0
    caminho_processado: Path | None = None

    def aplicar_resultado(self, resultado: ResultadoItem, pasta_saida: Path) -> None:
        """Copia o ResultadoItem já resolvido pelo pipeline para este item da sessão."""
        self.status = resultado.status
        self.motivo = resultado.motivo
        self.arquivo_saida = resultado.arquivo_saida
        self.origem = resultado.origem or self.origem
        self.detalhe = resultado.detalhe
        self.largura_original = resultado.largura_original
        self.altura_original = resultado.altura_original
        if resultado.arquivo_saida:
            subpasta = config.NOME_PASTA_APROVADAS if resultado.status == Status.PRONTO else config.NOME_PASTA_REVISAR
            self.caminho_processado = pasta_saida / subpasta / resultado.arquivo_saida


@dataclass
class Sessao:
    """Uma sessão de trabalho: pasta temporária isolada, itens e estado de progresso."""

    id: str
    pasta: Path
    estado: EstadoSessao = EstadoSessao.AGUARDANDO
    itens: list[ItemSessao] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def listar_itens(self) -> list[ItemSessao]:
        with self.lock:
            return list(self.itens)

    def obter_item(self, item_id: str) -> ItemSessao | None:
        with self.lock:
            return next((item for item in self.itens if item.item_id == item_id), None)


class _SessaoStore:
    """Registro em memória de todas as sessões ativas neste processo da API."""

    def __init__(self) -> None:
        self._sessoes: dict[str, Sessao] = {}
        self._lock = threading.Lock()

    def criar(self) -> Sessao:
        sessao_id = uuid.uuid4().hex
        pasta = _pasta_base_sessoes() / sessao_id
        pasta.mkdir(parents=True, exist_ok=True)
        sessao = Sessao(id=sessao_id, pasta=pasta)
        with self._lock:
            self._sessoes[sessao_id] = sessao
        return sessao

    def obter(self, sessao_id: str) -> Sessao | None:
        with self._lock:
            return self._sessoes.get(sessao_id)

    def remover(self, sessao_id: str) -> None:
        with self._lock:
            sessao = self._sessoes.pop(sessao_id, None)
        if sessao is not None:
            shutil.rmtree(sessao.pasta, ignore_errors=True)

    def limpar_tudo(self) -> None:
        """Remove os temporários de todas as sessões — chamado ao encerrar o app (ver backend/main.py)."""
        with self._lock:
            sessoes = list(self._sessoes.values())
            self._sessoes.clear()
        for sessao in sessoes:
            shutil.rmtree(sessao.pasta, ignore_errors=True)


store = _SessaoStore()


def _pasta_base_sessoes() -> Path:
    base = Path(tempfile.gettempdir()) / _NOME_PASTA_BASE_SESSOES
    base.mkdir(parents=True, exist_ok=True)
    return base


def reconstruir_itens(sessao: Sessao) -> None:
    """Reconstrói a lista de itens esperados da sessão a partir do que está gravado em disco.

    A ordem replica exatamente storage.listar_entradas mais a expansão de
    páginas de PDF — a mesma ordem em que pipeline.processar_pasta processa
    e chama on_item_processado — o que permite correlacionar cada callback
    ao item certo só pela posição (ver processar_em_background). Chamada
    depois de cada upload; seguro reconstruir do zero porque uploads só são
    aceitos enquanto a sessão está AGUARDANDO (ver backend/api/sessoes.py).
    """
    entradas = storage.listar_entradas(sessao.pasta)
    itens: list[ItemSessao] = []

    for caminho in entradas:
        if caminho.suffix.lower() in config.FORMATOS_PDF:
            itens.extend(_itens_para_pdf(caminho))
        else:
            itens.append(ItemSessao(item_id=uuid.uuid4().hex, arquivo_original=caminho.name, caminho_arquivo=caminho))

    with sessao.lock:
        sessao.itens = itens


def _itens_para_pdf(caminho: Path) -> list[ItemSessao]:
    """Um item por página esperada do PDF, ou um único item se o PDF nem abre.

    Espelha os dois desfechos de pipeline._processar_pdf: PdfProtegidoError/
    PdfCorrompidoError viram um item de arquivo inteiro (o pipeline também só
    produz um ResultadoItem nesse caso); do contrário, um item por página.
    """
    try:
        documento = pdf_service.abrir(caminho)
    except (pdf_service.PdfProtegidoError, pdf_service.PdfCorrompidoError):
        return [ItemSessao(item_id=uuid.uuid4().hex, arquivo_original=caminho.name, caminho_arquivo=caminho)]

    try:
        infos = pdf_service.inspecionar_paginas(documento)
    finally:
        documento.close()

    return [
        ItemSessao(
            item_id=uuid.uuid4().hex,
            arquivo_original=caminho.name,
            caminho_arquivo=caminho,
            pagina_indice=info.numero - 1,
            total_candidatas=info.total_candidatas,
            origem=f"página {info.numero}",
        )
        for info in infos
    ]


def _chave_item(item: ItemSessao) -> tuple[str, int | None]:
    """Chave estável (arquivo_original, número da página 1-based) — ver ItemSessao."""
    numero_pagina = item.pagina_indice + 1 if item.pagina_indice is not None else None
    return (item.arquivo_original, numero_pagina)


def processar_em_background(sessao_id: str) -> None:
    """Roda pipeline.processar_pasta para a sessão, atualizando o progresso item a item.

    Chamado via BackgroundTasks (ver backend/api/sessoes.py): a resposta de
    POST /processar já foi enviada antes desta função rodar, então uma
    exceção aqui não tem mais como virar resposta HTTP — só é registrada via
    log, e o finally garante que a sessão nunca fique presa em PROCESSANDO.
    """
    sessao = store.obter(sessao_id)
    if sessao is None:
        return

    pasta_saida = sessao.pasta / config.NOME_PASTA_SAIDA
    with sessao.lock:
        por_chave = {_chave_item(item): item for item in sessao.itens}

    def on_item(item: ResultadoItem, _indice_arquivo: int, _total_arquivos: int, numero_pagina: int | None) -> None:
        chave = (item.arquivo_original, numero_pagina)
        with sessao.lock:
            alvo = por_chave.get(chave)
            if alvo is None:
                # A pasta da sessão mudou entre o upload (reconstruir_itens)
                # e este momento — fora do fluxo normal da API, já que
                # uploads só são aceitos com a sessão AGUARDANDO. Registrado
                # bem alto porque, sem isso, o resultado ficaria sem para
                # onde ir e o item pré-registrado correspondente (se algum
                # existir) nunca sairia de AGUARDANDO.
                _logger.warning(
                    "Sessão %s: ResultadoItem %r não corresponde a nenhum item pré-registrado — criando novo",
                    sessao_id,
                    chave,
                )
                alvo = ItemSessao(
                    item_id=uuid.uuid4().hex,
                    arquivo_original=item.arquivo_original,
                    caminho_arquivo=sessao.pasta,
                    pagina_indice=(numero_pagina - 1) if numero_pagina is not None else None,
                )
                sessao.itens.append(alvo)
                por_chave[chave] = alvo
            alvo.aplicar_resultado(item, pasta_saida)

    try:
        resultados = pipeline.processar_pasta(sessao.pasta, on_item_processado=on_item)
        report_service.gerar_relatorio(sessao.pasta, resultados)
    except Exception:
        _logger.exception("Falha ao processar a sessão %s", sessao_id)
    finally:
        with sessao.lock:
            sessao.estado = EstadoSessao.CONCLUIDO


def gerar_preview_original(item: ItemSessao) -> tuple[bytes | None, str]:
    """Gera os bytes da versão "original" de um item, para GET /preview.

    Para um arquivo de imagem enviado direto, é o próprio arquivo salvo no
    upload. Para uma página de PDF, resolve a página de novo (ver
    pdf_service.resolver_pagina) — essa imagem não fica guardada em disco à
    parte, então recriá-la sob demanda evita duplicar armazenamento por conta
    de um caso de uso que é só visualização.
    """
    if item.pagina_indice is None:
        if not item.caminho_arquivo.exists():
            return None, ""
        media_type = mimetypes.guess_type(item.caminho_arquivo.name)[0] or "application/octet-stream"
        return item.caminho_arquivo.read_bytes(), media_type

    try:
        documento = pdf_service.abrir(item.caminho_arquivo)
    except Exception:
        return None, ""
    try:
        pagina = pdf_service.resolver_pagina(documento, item.pagina_indice)
    except Exception:
        return None, ""
    finally:
        documento.close()

    buffer = BytesIO()
    pagina.imagem.save(buffer, format="PNG")
    return buffer.getvalue(), "image/png"
