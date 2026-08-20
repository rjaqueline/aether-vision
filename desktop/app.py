"""Launcher desktop do Vision (Etapa 7): uvicorn + pywebview num único processo.

Empacotado como executável Windows via packaging/vision.spec (ver
scripts/build_exe.py); também roda direto de fonte com `python -m desktop.app`,
sem precisar dos dois terminais do fluxo de dev (README). backend/main.py não
é alterado por este módulo — só é importado e, aqui de fora, ganha o mount
estático do frontend já buildado (ver _montar_frontend).
"""

import multiprocessing
import socket
import sys
import threading
import time
from pathlib import Path

import uvicorn
import webview
from fastapi.staticfiles import StaticFiles

from backend.main import app

_TITULO = "Vision"

# Nome do app + "Iniciando..." enquanto o uvicorn sobe (YuNet/opencv/pymupdf
# levam alguns segundos para carregar) — sem isso a janela fica em branco e
# parece travamento. Trocada por load_url() assim que o servidor responde.
_HTML_CARREGANDO = """
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<style>
  html, body {
    height: 100%; margin: 0; display: flex; align-items: center; justify-content: center;
    background: #0f172a; color: #e2e8f0; font-family: system-ui, sans-serif;
  }
  .caixa { text-align: center; }
  .titulo { font-size: 1.5rem; font-weight: 600; margin-bottom: 0.5rem; }
</style>
</head>
<body>
  <div class="caixa">
    <div class="titulo">Vision</div>
    <div>Iniciando...</div>
  </div>
</body>
</html>
"""


def _base_dir_desktop() -> Path:
    """Pasta base para localizar frontend/dist empacotado (mesma lógica de backend/config._base_dir()).

    Duplicado aqui em vez de reaproveitado porque é uma pasta diferente
    (frontend/dist, não backend/models) e este módulo não deveria depender de
    detalhe interno do config do backend para algo que não é dele.
    """
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent.parent


def _montar_frontend() -> None:
    """Serve frontend/dist (buildado antecipadamente, ver README) na própria app FastAPI.

    Aplicado de fora, depois que os routers de sessão já estão registrados
    (backend/main.py), para que /sessao/..., /pastas-sugeridas etc. continuem
    respondendo antes do catch-all estático.
    """
    pasta_dist = _base_dir_desktop() / "frontend" / "dist"
    app.mount("/", StaticFiles(directory=str(pasta_dist), html=True), name="frontend")


def _porta_livre() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _aguardar_porta(porta: int, timeout: float = 15.0) -> None:
    prazo = time.monotonic() + timeout
    while time.monotonic() < prazo:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.2)
            if s.connect_ex(("127.0.0.1", porta)) == 0:
                return
        time.sleep(0.1)
    raise TimeoutError(f"Servidor não respondeu em 127.0.0.1:{porta} dentro de {timeout}s")


class Api:
    """Métodos expostos ao frontend via window.pywebview.api (ver ExportModal.jsx)."""

    def escolher_pasta_destino(self) -> str | None:
        janela = webview.windows[0]
        resultado = janela.create_file_dialog(webview.FileDialog.FOLDER)
        return resultado[0] if resultado else None


def _iniciar_servidor(janela: webview.Window) -> None:
    """Roda em background (via webview.start(func, args)): sobe o uvicorn e troca a tela de carregamento pela UI real."""
    porta = _porta_livre()
    servidor_config = uvicorn.Config(app, host="127.0.0.1", port=porta, log_level="warning")
    servidor = uvicorn.Server(servidor_config)
    thread_servidor = threading.Thread(target=servidor.run, daemon=True)
    thread_servidor.start()

    def _ao_fechar() -> None:
        # events.closing bloqueia o fechamento real da janela até este handler
        # retornar (Event(should_lock=True)) — por isso dá pra esperar o
        # shutdown do lifespan (sessao_service.store.limpar_tudo()) terminar
        # antes do processo sair, em vez de confiar só no fim do interpretador.
        servidor.should_exit = True
        thread_servidor.join(timeout=5.0)

    janela.events.closing += _ao_fechar

    _aguardar_porta(porta)
    janela.load_url(f"http://127.0.0.1:{porta}/")


def main() -> None:
    multiprocessing.freeze_support()
    _montar_frontend()

    janela = webview.create_window(_TITULO, html=_HTML_CARREGANDO, js_api=Api(), width=1100, height=800)
    webview.start(_iniciar_servidor, janela)


if __name__ == "__main__":
    main()
