"""Ponto de entrada da API local do Vision (FastAPI).

Roda só na máquina do usuário: sem autenticação, sem deploy, nenhuma imagem
sai para a internet. É consumida por um frontend local (Etapa 5) e será
empacotada como executável Windows (Etapa 7). A API é uma casca fina sobre
backend.services.pipeline — toda a lógica de processamento de imagem já
existe em backend/services e não é duplicada aqui (ver backend/api/sessoes.py
e backend/services/sessao_service.py).

Subir localmente:

    uvicorn backend.main:app --reload

Docs interativas em http://127.0.0.1:8000/docs.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api import sessoes
from backend.services import sessao_service

# http(s)://localhost ou 127.0.0.1, em qualquer porta — cobre o frontend rodando
# em dev (Vite etc., porta variável) e também empacotado (Etapa 7), sem abrir
# para nenhuma origem que não seja a própria máquina do usuário.
_ORIGEM_LOCALHOST_REGEX = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"


@asynccontextmanager
async def _lifespan(app: FastAPI):
    yield
    # Encerramento do app: nenhuma sessão deve deixar temporários para trás
    # na máquina do usuário (ver Sessao.pasta em sessao_service.py).
    sessao_service.store.limpar_tudo()


app = FastAPI(
    title="Vision API",
    description="API local do Vision — padronização de fotos de empregado para o ERP Senior e crachás.",
    lifespan=_lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=_ORIGEM_LOCALHOST_REGEX,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sessoes.router)
