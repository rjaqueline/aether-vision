import axios from "axios";

// A API roda só localmente (ver backend/main.py) — porta fixa do uvicorn,
// mas o host pode ser trocado via VITE_API_BASE_URL se necessário.
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

const http = axios.create({ baseURL: API_BASE_URL });

// Erro sem resposta do servidor (backend fora do ar, porta errada, etc.) —
// distinto de um erro HTTP normal (404, 409...), que a UI trata caso a caso.
export function isErroDeConexao(erro) {
  return !erro?.response;
}

export async function criarSessao() {
  const { data } = await http.post("/sessao");
  return data.id;
}

export async function enviarArquivos(sessaoId, arquivos) {
  const formData = new FormData();
  for (const arquivo of arquivos) {
    formData.append("arquivos", arquivo);
  }
  const { data } = await http.post(`/sessao/${sessaoId}/arquivos`, formData);
  return data.itens;
}

export async function processar(sessaoId) {
  const { data } = await http.post(`/sessao/${sessaoId}/processar`);
  return data;
}

export async function obterStatus(sessaoId) {
  const { data } = await http.get(`/sessao/${sessaoId}/status`);
  return data;
}

export async function exportar(sessaoId, pastaDestino) {
  const { data } = await http.post(`/sessao/${sessaoId}/exportar`, { pasta_destino: pastaDestino });
  return data;
}

export async function obterPastasSugeridas() {
  const { data } = await http.get("/pastas-sugeridas");
  return data.pastas;
}

export async function validarPasta(caminho) {
  const { data } = await http.post("/validar-pasta", { caminho });
  return data;
}

export async function removerSessao(sessaoId) {
  await http.delete(`/sessao/${sessaoId}`);
}

// Chamado a partir de beforeunload/pagehide: precisa ser "keepalive" para o
// navegador garantir o envio mesmo com a página sendo descartada.
export function removerSessaoAoFechar(sessaoId) {
  try {
    fetch(`${API_BASE_URL}/sessao/${sessaoId}`, { method: "DELETE", keepalive: true });
  } catch {
    // Página fechando — não há mais nada a fazer se isso falhar.
  }
}

export function urlPreview(sessaoId, itemId, versao) {
  return `${API_BASE_URL}/sessao/${sessaoId}/preview/${itemId}?versao=${versao}`;
}
