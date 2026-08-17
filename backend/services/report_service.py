"""Geração do relatório CSV com o resultado do processamento do lote."""

import csv
from pathlib import Path

from backend import config
from backend.schemas.resultado import ResultadoItem


def gerar_relatorio(pasta_base: Path, resultados: list[ResultadoItem]) -> Path:
    """Escreve o relatório CSV em Vision_Processadas e retorna o caminho gerado.

    Separador ; e encoding utf-8-sig para abrir corretamente no Excel em pt-BR.
    """
    caminho_relatorio = pasta_base / config.NOME_PASTA_SAIDA / config.NOME_RELATORIO
    with caminho_relatorio.open("w", newline="", encoding="utf-8-sig") as arquivo:
        escritor = csv.writer(arquivo, delimiter=";")
        escritor.writerow(ResultadoItem.cabecalho_csv())
        for resultado in resultados:
            escritor.writerow(resultado.para_linha_csv())
    return caminho_relatorio
