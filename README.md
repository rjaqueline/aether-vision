# Vision — Sistema Inteligente de Padronização de Imagens

Padroniza fotos de empregados para cadastro no Senior e impressão de crachás.
Saída: PNG, 200 × 267 px, proporção 3×4.

Desenvolvido por Jaqueline Batista.

---

## Situação atual: Etapa 1 concluída

O núcleo de imagem está pronto e testado, rodando por linha de comando.
Ainda não há detecção facial, leitura de PDF, API nem interface.

| Etapa | O quê | Situação |
|---|---|---|
| 1 | Núcleo de imagem (proporção, redimensionamento, saída, CSV) | ✅ pronta |
| 2 | Detecção facial e recorte cabeça + pescoço + ombros | ⬜ |
| 3 | PDF: imagens embutidas e páginas escaneadas | ⬜ |
| 4 | API FastAPI | ⬜ |
| 5 | Frontend React + Vite | ⬜ |
| 6 | Painel de revisão manual | ⬜ |
| 7 | Empacotamento Windows (.exe) | ⬜ |

---

## Instalação

Na pasta `vision/`:

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

## Como executar

```bash
python -m backend.cli "C:/Users/jbdsantos.TABOCA/Desktop/fotos"
```

Importante rodar de dentro da pasta `vision/`, e com `-m`.
É isso que faz o Python enxergar `backend` como pacote.

## Como testar

```bash
pytest
```

19 testes cobrindo proporção, redimensionamento, recorte, nomes únicos,
não-varredura de subpastas e preservação dos originais.

---

## O que acontece com cada foto hoje

```
foto entra
   │
   ▼ corrige orientação pelo EXIF, converte para RGB
   │
   ├── já está em 3×4 (±3%)? → redimensiona → aprovadas/
   │
   └── não está → recorte central provisório → revisar/
```

O recorte central é **temporário**. Na Etapa 2 ele é substituído pela
janela calculada a partir da posição real do rosto.

## Saída gerada

```
Vision_Processadas/
├── aprovadas/
├── revisar/
└── relatorio_processamento.csv
```

O CSV usa `;` como separador e UTF-8 com BOM, para abrir no Excel
em português sem acento quebrado.

## Decisões de projeto

- **Não varre subpastas.** O Vision olha só a pasta escolhida.
  Para mudar, alterar `VARRER_SUBPASTAS` em `backend/config.py`.
- **Originais nunca são alterados.** Toda escrita acontece dentro de
  `Vision_Processadas/`.
- **Nada é sobrescrito.** Nomes repetidos ganham sufixo `_2`, `_3`...
- **Todo número calibrável mora em `config.py`.** Nenhum valor mágico
  espalhado pelo código.

## Herança do AETHER VISION

Aproveitado: a lógica de nome único e o `exif_transpose` no início do
pipeline — as duas decisões mais certas do código original.

Corrigido: o antigo mantinha a proporção original da foto, então uma
imagem deitada saía deitada. Agora a proporção 3×4 é garantida por
construção, não por sorte.
# aether-vision
Python tool for automated facial image processing using OpenCV, including face detection, cropping and image standardization.
