"""Operações de sistema de arquivos: descobrir entradas, preparar saída, evitar
sobrescrita, sugerir/validar pasta de destino da exportação."""

import uuid
from datetime import datetime
from pathlib import Path

from backend import config


def nome_pasta_saida(momento: datetime | None = None) -> str:
    """Nome da pasta de saída para um processamento, com timestamp (ver config.PREFIXO_PASTA_SAIDA).

    Calculado uma vez por processamento (não a cada chamada) por quem
    orquestra o lote — pipeline.processar_pasta, sessao_service e cli —
    para que a mesma pasta seja usada do início ao fim de um mesmo lote,
    mesmo que o processamento atravesse a virada do minuto.
    """
    momento = momento or datetime.now()
    return f"{config.PREFIXO_PASTA_SAIDA}_{momento.strftime(config.FORMATO_TIMESTAMP_PASTA_SAIDA)}"


def preparar_saida(pasta_saida: Path) -> tuple[Path, Path, Path]:
    """Cria (se preciso) as subpastas de saída dentro de pasta_saida e retorna (aprovadas, revisar, debug)."""
    aprovadas = pasta_saida / config.NOME_PASTA_APROVADAS
    revisar = pasta_saida / config.NOME_PASTA_REVISAR
    debug = pasta_saida / config.NOME_PASTA_DEBUG
    aprovadas.mkdir(parents=True, exist_ok=True)
    revisar.mkdir(parents=True, exist_ok=True)
    debug.mkdir(parents=True, exist_ok=True)
    return aprovadas, revisar, debug


def listar_entradas(pasta_base: Path) -> list[Path]:
    """Lista os arquivos de imagem e PDF elegíveis em pasta_base, ignorando pastas de saída.

    Ignora qualquer subpasta cujo nome comece com config.PREFIXO_PASTA_SAIDA —
    não só a do processamento atual, mas também as de execuções anteriores
    (cada uma leva um timestamp diferente no nome, ver nome_pasta_saida).
    Nunca varre subpastas além disso: o Vision só deve tocar no que o usuário
    escolheu explicitamente (ver config.VARRER_SUBPASTAS).
    """
    formatos_aceitos = config.FORMATOS_IMAGEM | config.FORMATOS_PDF
    candidatos = pasta_base.rglob("*") if config.VARRER_SUBPASTAS else pasta_base.glob("*")

    entradas = []
    for caminho in candidatos:
        if not caminho.is_file():
            continue
        if caminho.suffix.lower() not in formatos_aceitos:
            continue
        partes_intermediarias = caminho.relative_to(pasta_base).parts[:-1]
        if any(parte.startswith(config.PREFIXO_PASTA_SAIDA) for parte in partes_intermediarias):
            continue
        entradas.append(caminho)
    return sorted(entradas)


# Nome físico real da pasta no disco (não o rótulo traduzido que o Explorer
# exibe) — desde o Windows Vista as pastas conhecidas ficam em inglês no
# sistema de arquivos mesmo em instalações localizadas; só o desktop.ini
# muda o que aparece na tela.
_PASTAS_CONHECIDAS = [
    ("Área de trabalho", "Desktop"),
    ("Documentos", "Documents"),
    ("Downloads", "Downloads"),
]


def pastas_sugeridas() -> list[tuple[str, Path]]:
    """Atalhos de pasta do usuário atual (Área de trabalho, Documentos, Downloads) que existem no disco."""
    home = Path.home()
    return [(nome, home / pasta) for nome, pasta in _PASTAS_CONHECIDAS if (home / pasta).is_dir()]


def validar_pasta_destino(caminho: Path) -> tuple[bool, str]:
    """Confirma que caminho é absoluto, existe e aceita escrita; devolve (valida, mensagem — "" quando válida).

    Chamada a cada digitação no campo de destino do frontend (debounced) e de
    novo antes de exportar — por isso não pode ter efeito colateral surpresa:
    exige caminho absoluto (um relativo resolveria contra o cwd do processo do
    servidor, não contra algo previsível para quem digitou) e nunca cria a
    pasta em si, só confirma que ela já existe.

    A checagem de escrita tenta de fato criar um arquivo em vez de inspecionar
    permissões (ex.: os.access): no Windows, ACLs e atributos de pastas do
    sistema não são bem representados por uma checagem de bits, e tentar
    escrever é o único jeito confiável de saber. O arquivo de teste usa nome
    identificável (prefixo vision_write_test) e é sempre removido em finally,
    mesmo se a escrita falhar no meio.
    """
    if not caminho.is_absolute():
        return False, "Informe um caminho absoluto."
    if not caminho.exists():
        return False, "Pasta não encontrada."
    if not caminho.is_dir():
        return False, "O caminho informado não é uma pasta."

    arquivo_teste = caminho / f".vision_write_test_{uuid.uuid4().hex}"
    try:
        arquivo_teste.write_bytes(b"")
    except OSError:
        return False, "Sem permissão de escrita nesta pasta."
    finally:
        arquivo_teste.unlink(missing_ok=True)
    return True, ""


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
