"""Interface de linha de comando do Vision.

Uso: python -m backend.cli "caminho/da/pasta"
"""

import argparse
import sys
from pathlib import Path

from backend.schemas.resultado import ResultadoItem, Status
from backend.services import pipeline, report_service


def main(argv: list[str] | None = None) -> int:
    """Ponto de entrada da CLI: processa a pasta informada e imprime um resumo."""
    parser = argparse.ArgumentParser(
        prog="python -m backend.cli",
        description="Vision — padroniza fotos de empregados para o ERP Senior e crachás.",
    )
    parser.add_argument("pasta", help="Caminho da pasta com as fotos originais")
    args = parser.parse_args(argv)

    pasta_base = Path(args.pasta)
    if not pasta_base.is_dir():
        print(f"Erro: pasta não encontrada: {pasta_base}")
        return 1

    resultados = pipeline.processar_pasta(pasta_base)
    caminho_relatorio = report_service.gerar_relatorio(pasta_base, resultados)

    _imprimir_resumo(resultados, caminho_relatorio)
    return 0


def _imprimir_resumo(resultados: list[ResultadoItem], caminho_relatorio: Path) -> None:
    """Imprime a contagem por status e o caminho do relatório gerado."""
    total = len(resultados)
    prontos = sum(1 for r in resultados if r.status == Status.PRONTO)
    revisar = sum(1 for r in resultados if r.status == Status.REVISAR)
    erros = sum(1 for r in resultados if r.status == Status.ERRO)

    print(f"Total processado: {total}")
    print(f"  Aprovadas direto: {prontos}")
    print(f"  Para revisar:     {revisar}")
    print(f"  Erros:            {erros}")
    print(f"Relatório: {caminho_relatorio}")


if __name__ == "__main__":
    sys.exit(main())
