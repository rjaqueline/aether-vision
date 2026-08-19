# Vision — frontend

Tela única em React + Vite que consome a API local do Vision (`backend/`, Etapa 4).

## Rodando em desenvolvimento

Pré-requisito: o backend rodando em `http://127.0.0.1:8000` (ver README na raiz do projeto).

```
npm install
npm run dev
```

Abre em `http://localhost:5173`. A URL da API pode ser trocada com a variável de ambiente
`VITE_API_BASE_URL` (padrão `http://127.0.0.1:8000`).

## Build

```
npm run build
```

Gera `dist/` — arquivos estáticos que serão empacotados junto do executável na Etapa 7.
