# Vision — Sistema Inteligente de Padronização de Imagens

Padroniza fotos de empregados para cadastro no Senior e impressão de crachás.
Saída: PNG, 200 × 267 px, proporção 3×4.

Desenvolvido por Jaqueline Batista.

---

## Situação atual: Etapa 5 concluída

Backend (pipeline + API local) e frontend rodando juntos, tela única de
upload → processamento → prévia → exportação. Ainda falta o painel de
revisão manual e o empacotamento como executável Windows.

| Etapa | O quê | Situação |
|---|---|---|
| 1 | Núcleo de imagem (proporção, redimensionamento, saída, CSV) | ✅ pronta |
| 2 | Detecção facial e recorte cabeça + pescoço + ombros | ✅ pronta |
| 3 | PDF: imagens embutidas e páginas escaneadas | ✅ pronta |
| 4 | API FastAPI | ✅ pronta |
| 5 | Frontend React + Vite | ✅ pronta |
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

## Subindo backend + frontend juntos (Etapa 5)

Dois processos, cada um no seu terminal, na raiz do projeto:

```bash
# terminal 1 — API (porta 8000)
.venv\Scripts\activate
uvicorn backend.main:app --reload

# terminal 2 — frontend (porta 5173)
cd frontend
npm install   # só na primeira vez
npm run dev
```

Abrir `http://localhost:5173`. O frontend já sabe conversar com a API em
`http://127.0.0.1:8000` (CORS liberado para `localhost`/`127.0.0.1` em
qualquer porta — ver `backend/main.py`); nenhuma configuração extra é
necessária. Se a API não estiver no ar, a tela mostra um aviso claro em vez
de falhar silenciosamente.

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
Vision_Processadas_AAAA-MM-DD_HHhMM/
├── aprovadas/
├── revisar/
├── debug/
└── relatorio_processamento.csv
```

O nome da pasta leva a data e hora do processamento (ver
`storage.nome_pasta_saida`), para que lotes processados em momentos
diferentes não se misturem ao exportar para o mesmo destino.

Ao exportar pelo frontend, o modal sugere Área de trabalho, Documentos e
Downloads do usuário atual como atalhos de um clique (`GET
/pastas-sugeridas`) e valida o caminho digitado em tempo real — existência e
permissão de escrita (`POST /validar-pasta`). Esse fluxo de digitar/colar o
caminho é provisório: será substituído pelo seletor de pasta nativo do
sistema operacional na Etapa 7, junto do empacotamento como executável
Windows.

O CSV usa `;` como separador e UTF-8 com BOM, para abrir no Excel
em português sem acento quebrado.

## Decisões de projeto

- **Não varre subpastas.** O Vision olha só a pasta escolhida.
  Para mudar, alterar `VARRER_SUBPASTAS` em `backend/config.py`.
- **Originais nunca são alterados.** Toda escrita acontece dentro de
  `Vision_Processadas_AAAA-MM-DD_HHhMM/`.
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
