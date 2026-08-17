"""Operações de sistema de arquivos: descobrir entradas, preparar saída, evitar sobrescrita."""

from pathlib import Path

from backend import config


def preparar_saida(pasta_base: Path) -> tuple[Path, Path, Path]:
    """Cria (se preciso) as subpastas de saída e retorna (aprovadas, revisar, debug)."""
    pasta_saida = pasta_base / config.NOME_PASTA_SAIDA
    aprovadas = pasta_saida / config.NOME_PASTA_APROVADAS
    revisar = pasta_saida / config.NOME_PASTA_REVISAR
    debug = pasta_saida / config.NOME_PASTA_DEBUG
    aprovadas.mkdir(parents=True, exist_ok=True)
    revisar.mkdir(parents=True, exist_ok=True)
    debug.mkdir(parents=True, exist_ok=True)
    return aprovadas, revisar, debug


def listar_entradas(pasta_base: Path) -> list[Path]:
    """Lista os arquivos de imagem elegíveis em pasta_base, ignorando a própria pasta de saída.

    Nunca varre subpastas: o Vision só deve tocar no que o usuário escolheu
    explicitamente (ver config.VARRER_SUBPASTAS).
    """
    pasta_saida = (pasta_base / config.NOME_PASTA_SAIDA).resolve()
    candidatos = pasta_base.rglob("*") if config.VARRER_SUBPASTAS else pasta_base.glob("*")

    entradas = []
    for caminho in candidatos:
        if not caminho.is_file():
            continue
        if caminho.suffix.lower() not in config.FORMATOS_IMAGEM:
            continue
        caminho_resolvido = caminho.resolve()
        if caminho_resolvido == pasta_saida or pasta_saida in caminho_resolvido.parents:
            continue
        entradas.append(caminho)
    return sorted(entradas)


def caminho_disponivel(pasta_destino: Path, nome_arquivo: str) -> Path:
    """Retorna um caminho livre em pasta_destino, adicionando _2, _3... se o nome já existir.

    Garante que originais e saídas anteriores nunca sejam sobrescritos.
    """
    destino = pasta_destino / nome_arquivo
    if not destino.exists():
        return destino

    stem = destino.stem
    sufixo = destino.suffix
    contador = 2
    while True:
        candidato = pasta_destino / f"{stem}_{contador}{sufixo}"
        if not candidato.exists():
            return candidato
        contador += 1
