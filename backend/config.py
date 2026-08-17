"""Configurações centrais do Vision.

Todo número calibrável do pipeline mora aqui — nenhum valor mágico deve
aparecer espalhado pelos outros módulos.
"""

from pathlib import Path

LARGURA_FINAL = 200
ALTURA_FINAL = 267
PROPORCAO_ALVO = 3 / 4  # largura / altura de um retrato 3x4
TOLERANCIA_PROPORCAO = 0.03  # desvio máximo aceito para considerar "já em 3x4"

FORMATOS_IMAGEM = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"}

# O Vision só deve tocar no que o usuário escolheu explicitamente, nunca em
# pastas dentro dela.
VARRER_SUBPASTAS = False

# Parâmetros da janela de recorte guiada por detecção facial: altura da
# janela como múltiplo da altura do rosto detectado, e margem acima do rosto
# até o topo do enquadramento (ver crop_service.calcular_janela).
#
# Calibrado para selfies de braço esticado (celular), não para fotos tiradas
# à distância: nelas o rosto detectado já ocupa 35-45% da altura da imagem,
# então qualquer fator acima de ~2.2 pede uma janela maior que a própria
# imagem e nunca cabe — a "janela" acaba virando o frame inteiro sem recorte
# real nenhum. 1.85 foi calibrado olhando as imagens de depuração: 2.0 ainda
# deixava cenário demais nas laterais e cortava acima da linha dos ombros.
FATOR_ALTURA_JANELA = 1.85

# Piso da janela quando a ideal (FATOR_ALTURA_JANELA) não cabe na imagem:
# em vez de reprovar direto, tenta um enquadramento mais apertado até este
# fator. Abaixo dele a foto vira um retrato de rosto sem ombro — não serve
# para crachá — e aí sim vai para revisão como "ombros cortados".
FATOR_ALTURA_MINIMO = 1.7

FATOR_MARGEM_TOPO = 0.40

# --- detecção facial (YuNet) ----------------------------------------------

CAMINHO_MODELO_YUNET = Path(__file__).resolve().parent / "models" / "face_detection_yunet_2023mar.onnx"
CONFIANCA_MINIMA_ROSTO = 0.75  # score_threshold do YuNet: abaixo disso a detecção é descartada
NMS_LIMIAR_IOU = 0.3  # nms_threshold do YuNet: funde caixas sobrepostas do mesmo rosto
TOP_K_ROSTOS = 5000  # número máximo de candidatos considerados pelo YuNet antes do NMS

# O YuNet perde confiança em imagens grandes; a detecção roda numa cópia
# reduzida a no máximo este tamanho no maior lado, e o resultado é reescalado
# de volta às coordenadas da imagem original (ver face_service._redimensionar_para_deteccao).
LADO_MAXIMO_DETECCAO = 800

# Um rosto é "pequeno demais" quando sua altura é menor que esta fração da
# altura total da imagem original.
ALTURA_MINIMA_ROSTO = 0.15

# Assimetria máxima aceita entre a distância horizontal de cada olho ao nariz
# antes de classificar o rosto como "lateral" (fora de frente).
ASSIMETRIA_MAXIMA_ROSTO_LATERAL = 0.4

NOME_PASTA_SAIDA = "Vision_Processadas"
NOME_PASTA_APROVADAS = "aprovadas"
NOME_PASTA_REVISAR = "revisar"
NOME_PASTA_DEBUG = "debug"
NOME_RELATORIO = "relatorio_processamento.csv"
