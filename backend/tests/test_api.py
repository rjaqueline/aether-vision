"""Testes de integração da API (backend.main:app) via TestClient: fluxo
completo sessão -> upload -> processar -> status -> preview -> exportar ->
delete, e os casos de erro (sessão inexistente, arquivo não suportado,
processar sessão vazia).

O processamento roda em background via BackgroundTasks, mas o TestClient
executa a tarefa de fundo antes de devolver a resposta de POST /processar
(faz parte do ciclo de vida da resposta no Starlette) — por isso os testes
não precisam de espera/polling real: já podem consultar /status logo em
seguida.
"""

import io
from pathlib import Path

import pymupdf
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend.main import app
from backend.services import face_service
from backend.services.face_service import Rosto


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _rosto_valido(x=200, y=150, largura=200, altura=250) -> Rosto:
    centro_x = x + largura / 2
    return Rosto(
        x=x,
        y=y,
        largura=largura,
        altura=altura,
        confianca=0.99,
        olho_direito=(centro_x - 50, y + altura * 0.3),
        olho_esquerdo=(centro_x + 50, y + altura * 0.3),
        nariz=(centro_x, y + altura * 0.5),
        boca_direita=(centro_x - 40, y + altura * 0.8),
        boca_esquerda=(centro_x + 40, y + altura * 0.8),
    )


def _bytes_imagem(largura=600, altura=800, cor=(120, 60, 200)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (largura, altura), cor).save(buffer, format="PNG")
    return buffer.getvalue()


def _bytes_pdf_com_imagem(largura=600, altura=800, cor=(120, 60, 200)) -> bytes:
    """PDF de uma página com uma única imagem embutida do tamanho dado."""
    documento = pymupdf.open()
    pagina = documento.new_page(width=595, height=842)
    buffer_imagem = io.BytesIO()
    Image.new("RGB", (largura, altura), cor).save(buffer_imagem, format="PNG")
    pagina.insert_image(pymupdf.Rect(50, 50, 300, 300), stream=buffer_imagem.getvalue())
    buffer_pdf = io.BytesIO()
    documento.save(buffer_pdf)
    documento.close()
    return buffer_pdf.getvalue()


def _criar_sessao(client: TestClient) -> str:
    resposta = client.post("/sessao")
    assert resposta.status_code == 200
    return resposta.json()["id"]


# --- fluxo completo ----------------------------------------------------------


def test_fluxo_completo_imagem_e_pdf(client: TestClient, tmp_path: Path, monkeypatch):
    rosto = _rosto_valido()
    monkeypatch.setattr(face_service, "detectar_rostos", lambda imagem: [rosto])

    sessao_id = _criar_sessao(client)

    resposta = client.post(
        f"/sessao/{sessao_id}/arquivos",
        files=[
            ("arquivos", ("empregado.jpg", _bytes_imagem(), "image/jpeg")),
            ("arquivos", ("formulario.pdf", _bytes_pdf_com_imagem(), "application/pdf")),
        ],
    )
    assert resposta.status_code == 200
    itens_upload = resposta.json()["itens"]
    assert len(itens_upload) == 2
    assert all(item["status"] == "Aguardando" for item in itens_upload)
    # a página do PDF tem 1 candidata (a imagem embutida) reportada já no upload
    item_pdf = next(item for item in itens_upload if item["arquivo_original"] == "formulario.pdf")
    assert item_pdf["total_candidatas"] == 1

    resposta = client.post(f"/sessao/{sessao_id}/processar")
    assert resposta.status_code == 200

    resposta = client.get(f"/sessao/{sessao_id}/status")
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["estado"] == "concluido"
    assert corpo["total"] == 2
    assert corpo["concluidos"] == 2
    assert all(item["status"] == "Pronto" for item in corpo["itens"])

    item_id = corpo["itens"][0]["item_id"]
    resposta = client.get(f"/sessao/{sessao_id}/preview/{item_id}")
    assert resposta.status_code == 200
    assert resposta.headers["content-type"] == "image/png"
    assert len(resposta.content) > 0

    resposta = client.get(f"/sessao/{sessao_id}/preview/{item_id}?versao=original")
    assert resposta.status_code == 200
    assert len(resposta.content) > 0

    pasta_destino = tmp_path / "destino"
    pasta_destino.mkdir()
    resposta = client.post(f"/sessao/{sessao_id}/exportar", json={"pasta_destino": str(pasta_destino)})
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert Path(corpo["pasta_saida"]).is_dir()
    assert Path(corpo["relatorio"]).is_file()
    assert (Path(corpo["pasta_saida"]) / "aprovadas").is_dir()
    assert any((Path(corpo["pasta_saida"]) / "aprovadas").iterdir())

    resposta = client.delete(f"/sessao/{sessao_id}")
    assert resposta.status_code == 204

    resposta = client.get(f"/sessao/{sessao_id}/status")
    assert resposta.status_code == 404


def test_pdf_sem_imagem_embutida_e_rasterizado_e_reportado_com_zero_candidatas(client: TestClient, monkeypatch):
    # sem rosto detectável: cai para Status.REVISAR, mas o que este teste
    # cobre é o upload reportar 0 candidatas e o processamento marcar a
    # origem como rasterizada, não a aprovação em si (coberta com imagem
    # embutida em test_fluxo_completo_imagem_e_pdf)
    monkeypatch.setattr(face_service, "detectar_rostos", lambda imagem: [])

    documento = pymupdf.open()
    documento.new_page(width=595, height=842)  # página em branco, sem imagem embutida
    buffer_pdf = io.BytesIO()
    documento.save(buffer_pdf)
    documento.close()

    sessao_id = _criar_sessao(client)
    resposta = client.post(
        f"/sessao/{sessao_id}/arquivos",
        files=[("arquivos", ("scan.pdf", buffer_pdf.getvalue(), "application/pdf"))],
    )
    assert resposta.status_code == 200
    itens = resposta.json()["itens"]
    assert len(itens) == 1
    assert itens[0]["total_candidatas"] == 0

    resposta = client.post(f"/sessao/{sessao_id}/processar")
    assert resposta.status_code == 200
    corpo = client.get(f"/sessao/{sessao_id}/status").json()
    assert corpo["itens"][0]["status"] == "Revisar"
    assert "rasterizada" in corpo["itens"][0]["origem"]


# --- casos de erro -------------------------------------------------------------


def test_sessao_inexistente_retorna_404_em_todas_as_rotas(client: TestClient):
    sessao_id = "nao-existe"

    assert client.get(f"/sessao/{sessao_id}/status").status_code == 404
    assert client.post(f"/sessao/{sessao_id}/processar").status_code == 404
    assert client.get(f"/sessao/{sessao_id}/preview/qualquer").status_code == 404
    assert client.post(f"/sessao/{sessao_id}/exportar", json={"pasta_destino": "C:/"}).status_code == 404
    assert client.delete(f"/sessao/{sessao_id}").status_code == 404
    resposta = client.post(
        f"/sessao/{sessao_id}/arquivos", files=[("arquivos", ("a.jpg", _bytes_imagem(), "image/jpeg"))]
    )
    assert resposta.status_code == 404


def test_upload_arquivo_nao_suportado_retorna_400(client: TestClient):
    sessao_id = _criar_sessao(client)

    resposta = client.post(
        f"/sessao/{sessao_id}/arquivos",
        files=[("arquivos", ("documento.txt", b"nao e imagem nem pdf", "text/plain"))],
    )
    assert resposta.status_code == 400

    # o arquivo inválido não pode ter contaminado a sessão com um item parcial
    assert client.get(f"/sessao/{sessao_id}/status").json()["total"] == 0


def test_processar_sessao_vazia_retorna_400(client: TestClient):
    sessao_id = _criar_sessao(client)

    resposta = client.post(f"/sessao/{sessao_id}/processar")
    assert resposta.status_code == 400


def test_processar_sessao_ja_processada_retorna_409(client: TestClient, monkeypatch):
    monkeypatch.setattr(face_service, "detectar_rostos", lambda imagem: [_rosto_valido()])
    sessao_id = _criar_sessao(client)
    client.post(f"/sessao/{sessao_id}/arquivos", files=[("arquivos", ("a.jpg", _bytes_imagem(), "image/jpeg"))])
    client.post(f"/sessao/{sessao_id}/processar")

    resposta = client.post(f"/sessao/{sessao_id}/processar")
    assert resposta.status_code == 409

    resposta = client.post(
        f"/sessao/{sessao_id}/arquivos", files=[("arquivos", ("b.jpg", _bytes_imagem(), "image/jpeg"))]
    )
    assert resposta.status_code == 409


def test_exportar_antes_de_processar_retorna_409(client: TestClient):
    sessao_id = _criar_sessao(client)
    client.post(f"/sessao/{sessao_id}/arquivos", files=[("arquivos", ("a.jpg", _bytes_imagem(), "image/jpeg"))])

    resposta = client.post(f"/sessao/{sessao_id}/exportar", json={"pasta_destino": "C:/"})
    assert resposta.status_code == 409


def test_exportar_pasta_destino_inexistente_retorna_400(client: TestClient, monkeypatch):
    monkeypatch.setattr(face_service, "detectar_rostos", lambda imagem: [_rosto_valido()])
    sessao_id = _criar_sessao(client)
    client.post(f"/sessao/{sessao_id}/arquivos", files=[("arquivos", ("a.jpg", _bytes_imagem(), "image/jpeg"))])
    client.post(f"/sessao/{sessao_id}/processar")

    resposta = client.post(
        f"/sessao/{sessao_id}/exportar", json={"pasta_destino": "Z:/pasta/que/nao/existe/de/verdade"}
    )
    assert resposta.status_code == 400
