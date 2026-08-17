"""Testes de sessao_service focados na correlação entre o ResultadoItem que
volta do callback de progresso do pipeline e o ItemSessao pré-registrado no
upload — ver processar_em_background e _chave_item.
"""

from PIL import Image

from backend.schemas.resultado import Status
from backend.services import face_service, sessao_service


def test_correlacao_por_chave_independe_da_ordem_de_registro(tmp_path, monkeypatch):
    """A correlação é por (arquivo_original, número de página), não por posição na lista.

    Cria dois arquivos com desfechos diferentes e deliberadamente embaralha
    sessao.itens depois de reconstruir_itens, simulando uma divergência entre
    a ordem de registro e a ordem real de processamento. Se a correlação
    fosse posicional (um contador incrementado a cada callback indexando a
    lista), isso trocaria os resultados entre os dois itens.
    """

    def deteccao_condicional(imagem):
        # só "a.jpg" (pixel (10,10,10)) tem rosto válido; "b.jpg" não tem nenhum
        if imagem.getpixel((0, 0)) == (10, 10, 10):
            return [face_service.Rosto(
                x=200, y=150, largura=200, altura=250, confianca=0.99,
                olho_direito=(250, 225), olho_esquerdo=(350, 225),
                nariz=(300, 275), boca_direita=(260, 325), boca_esquerda=(340, 325),
            )]
        return []

    monkeypatch.setattr(face_service, "detectar_rostos", deteccao_condicional)

    sessao = sessao_service.store.criar()
    try:
        Image.new("RGB", (600, 800), (10, 10, 10)).save(sessao.pasta / "a.jpg")
        Image.new("RGB", (600, 800), (200, 200, 200)).save(sessao.pasta / "b.jpg")
        sessao_service.reconstruir_itens(sessao)

        with sessao.lock:
            sessao.itens.reverse()  # diverge deliberadamente da ordem de processamento
        id_a = next(item.item_id for item in sessao.itens if item.arquivo_original == "a.jpg")
        id_b = next(item.item_id for item in sessao.itens if item.arquivo_original == "b.jpg")

        sessao_service.processar_em_background(sessao.id)

        item_a = sessao.obter_item(id_a)
        item_b = sessao.obter_item(id_b)
        assert item_a.status == Status.PRONTO
        assert item_b.status == Status.REVISAR
    finally:
        sessao_service.store.remover(sessao.id)


def test_correlacao_por_chave_distingue_paginas_do_mesmo_pdf(tmp_path, monkeypatch):
    """Duas páginas do mesmo PDF (mesmo arquivo_original) só se distinguem pelo número da página."""
    import io

    import pymupdf

    def deteccao_condicional(imagem):
        if imagem.getpixel((0, 0)) == (10, 10, 10):
            return [face_service.Rosto(
                x=200, y=150, largura=200, altura=250, confianca=0.99,
                olho_direito=(250, 225), olho_esquerdo=(350, 225),
                nariz=(300, 275), boca_direita=(260, 325), boca_esquerda=(340, 325),
            )]
        return []

    monkeypatch.setattr(face_service, "detectar_rostos", deteccao_condicional)

    documento = pymupdf.open()
    for cor in [(10, 10, 10), (200, 200, 200)]:
        pagina = documento.new_page(width=595, height=842)
        buffer = io.BytesIO()
        Image.new("RGB", (600, 800), cor).save(buffer, format="PNG")
        pagina.insert_image(pymupdf.Rect(50, 50, 300, 300), stream=buffer.getvalue())

    sessao = sessao_service.store.criar()
    try:
        documento.save(sessao.pasta / "lote.pdf")
        documento.close()
        sessao_service.reconstruir_itens(sessao)

        with sessao.lock:
            sessao.itens.reverse()
        pagina1 = next(item.item_id for item in sessao.itens if item.pagina_indice == 0)
        pagina2 = next(item.item_id for item in sessao.itens if item.pagina_indice == 1)

        sessao_service.processar_em_background(sessao.id)

        assert sessao.obter_item(pagina1).status == Status.PRONTO
        assert sessao.obter_item(pagina2).status == Status.REVISAR
    finally:
        sessao_service.store.remover(sessao.id)
