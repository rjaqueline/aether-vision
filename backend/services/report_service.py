"""Geração do relatório CSV com o resultado do processamento do lote."""

import csv
from pathlib import Path

from backend import config
from backend.schemas.resultado import ResultadoItem


def gerar_relatorio(pasta_saida: Path, resultados: list[ResultadoItem]) -> Path:
    """Escreve o relatório CSV dentro de pasta_saida e retorna o caminho gerado.

    pasta_saida é a pasta já resolvida (com timestamp, ver
    storage.nome_pasta_saida) usada pelo mesmo processamento — não a pasta
    base de entrada.

    Separador ; e encoding utf-8-sig para abrir corretamente no Excel em pt-BR.
    """
    caminho_relatorio = pasta_saida / config.NOME_RELATORIO
    with caminho_relatorio.open("w", newline="", encoding="utf-8-sig") as arquivo:
        escritor = csv.writer(arquivo, delimiter=";")
        escritor.writerow(ResultadoItem.cabecalho_csv())
        for resultado in resultados:
            escritor.writerow(resultado.para_linha_csv())
    return caminho_relatorio
