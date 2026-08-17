"""Schemas Pydantic de request/response da API local (ver backend/api/sessoes.py).

São a casca HTTP em cima de backend/services/sessao_service.py — não
carregam nenhuma decisão de processamento de imagem, só formatam o que o
serviço de sessão já decidiu.
"""

from pydantic import BaseModel, Field


class SessaoCriadaResposta(BaseModel):
    """Resposta de POST /sessao."""

    id: str


class ItemUploadResposta(BaseModel):
    """Um item da sessão logo após o upload — ainda Status.AGUARDANDO."""

    item_id: str
    arquivo_original: str
    status: str
    origem: str = ""
    total_candidatas: int | None = None  # só preenchido para páginas de PDF (ver pdf_service.inspecionar_paginas)


class UploadResposta(BaseModel):
    """Resposta de POST /sessao/{id}/arquivos."""

    itens: list[ItemUploadResposta]


class ProcessarResposta(BaseModel):
    """Resposta de POST /sessao/{id}/processar — o processamento roda em background."""

    estado: str


class ItemStatusResposta(BaseModel):
    """Um item da sessão no momento da consulta de status (ver GET /status)."""

    item_id: str
    arquivo_original: str
    arquivo_saida: str = ""
    status: str
    motivo: str = ""
    origem: str = ""
    detalhe: str = ""
    largura_original: int = 0
    altura_original: int = 0


class SessaoStatusResposta(BaseModel):
    """Resposta de GET /sessao/{id}/status — pensada para o frontend fazer polling."""

    estado: str
    total: int
    concluidos: int
    itens: list[ItemStatusResposta]


class ExportarRequest(BaseModel):
    """Corpo de POST /sessao/{id}/exportar."""

    pasta_destino: str = Field(..., min_length=1)


class ExportarResposta(BaseModel):
    """Resposta de POST /sessao/{id}/exportar."""

    pasta_saida: str
    relatorio: str
