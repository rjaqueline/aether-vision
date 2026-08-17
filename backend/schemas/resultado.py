"""Estruturas de dados que representam o resultado do processamento de cada imagem."""

from dataclasses import dataclass
from enum import Enum


class Status(str, Enum):
    """Estado de uma imagem ao longo do pipeline."""

    AGUARDANDO = "Aguardando"
    PROCESSANDO = "Processando"
    PRONTO = "Pronto"
    REVISAR = "Revisar"
    ERRO = "Erro"


class Motivo(str, Enum):
    """Motivo específico associado ao status final de uma imagem."""

    ROSTO_VALIDO_RECORTADO = "Recorte guiado por detecção facial"
    ROSTO_VALIDO_RECORTADO_AJUSTADO = "Recorte guiado por detecção facial (enquadramento reduzido para caber)"
    NENHUM_ROSTO = "Nenhum rosto detectado"
    MULTIPLOS_ROSTOS = "Múltiplos rostos detectados"
    ROSTO_PEQUENO = "Rosto pequeno demais"
    ROSTO_LATERAL = "Rosto de perfil"
    OMBROS_CORTADOS = "Ombros cortados no recorte guiado por rosto"
    ARQUIVO_INVALIDO = "Arquivo não é uma imagem válida"
    ERRO_LEITURA = "Erro ao ler o arquivo"
    ERRO_PROCESSAMENTO = "Erro durante o processamento"
    NENHUM = "-"


@dataclass
class ResultadoItem:
    """Resultado do processamento de um único arquivo, pronto para virar linha de CSV."""

    arquivo_original: str
    status: Status
    motivo: Motivo
    arquivo_saida: str = ""
    largura_original: int = 0
    altura_original: int = 0

    def para_linha_csv(self) -> list[str]:
        """Converte o resultado em uma lista de strings na ordem das colunas do relatório."""
        return [
            self.arquivo_original,
            self.arquivo_saida,
            self.status.value,
            self.motivo.value,
            str(self.largura_original),
            str(self.altura_original),
        ]

    @staticmethod
    def cabecalho_csv() -> list[str]:
        """Cabeçalho correspondente às colunas de para_linha_csv."""
        return [
            "arquivo_original",
            "arquivo_saida",
            "status",
            "motivo",
            "largura_original",
            "altura_original",
        ]
