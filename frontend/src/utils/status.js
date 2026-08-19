// Vocabulário de status espelha backend/schemas/resultado.py::Status — os
// valores chegam prontos da API (item.status), nada é traduzido aqui.
export const STATUS_INFO = {
  Aguardando: { cor: "bg-gray-200 text-gray-700", ponto: "bg-gray-400" },
  Processando: { cor: "bg-blue-100 text-blue-700", ponto: "bg-blue-500" },
  Pronto: { cor: "bg-green-100 text-green-700", ponto: "bg-green-500" },
  Revisar: { cor: "bg-amber-100 text-amber-800", ponto: "bg-amber-500" },
  Erro: { cor: "bg-red-100 text-red-700", ponto: "bg-red-500" },
};

// Ordem de prioridade para o status "pior primeiro" de um grupo (card de
// PDF com várias páginas) — o que mais precisa de atenção decide a cor do
// card principal.
const PRIORIDADE = ["Erro", "Revisar", "Processando", "Aguardando", "Pronto"];

// O backend só marca um item como Processando implicitamente: enquanto a
// sessão está processando, um item ainda Aguardando está, na prática, na
// fila ou sendo processado agora — não há granularidade maior na API (ver
// backend/services/sessao_service.py, ItemSessao nunca grava Status.PROCESSANDO).
export function statusExibicao(item, estadoSessao) {
  if (item.status === "Aguardando" && estadoSessao === "processando") {
    return "Processando";
  }
  return item.status;
}

export function statusPrioritario(statusList) {
  for (const status of PRIORIDADE) {
    if (statusList.includes(status)) return status;
  }
  return "Aguardando";
}

// Agrupa itens da sessão por arquivo de origem — cada página de PDF vira um
// item próprio na API (ver ItemSessao/_itens_para_pdf), mas para o usuário
// deve aparecer como subitem de um único card do arquivo.
export function agruparPorArquivo(itens) {
  const grupos = [];
  const porNome = new Map();
  for (const item of itens) {
    let grupo = porNome.get(item.arquivo_original);
    if (!grupo) {
      grupo = { arquivoOriginal: item.arquivo_original, itens: [] };
      porNome.set(item.arquivo_original, grupo);
      grupos.push(grupo);
    }
    grupo.itens.push(item);
  }
  for (const grupo of grupos) {
    grupo.isPdf = grupo.itens.length > 1 || grupo.arquivoOriginal.toLowerCase().endsWith(".pdf");
  }
  return grupos;
}
