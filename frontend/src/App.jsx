import { useCallback, useEffect, useRef, useState } from "react";
import { CheckCircle2, ImageIcon } from "lucide-react";
import {
  API_BASE_URL,
  criarSessao,
  enviarArquivos,
  processar,
  obterStatus,
  exportar,
  removerSessao,
  removerSessaoAoFechar,
  isErroDeConexao,
} from "./api/client";
import UploadZone from "./components/UploadZone";
import FileList from "./components/FileList";
import ProgressBar from "./components/ProgressBar";
import Summary from "./components/Summary";
import Toolbar from "./components/Toolbar";
import ErrorBanner from "./components/ErrorBanner";
import PreviewModal from "./components/PreviewModal";
import ExportModal from "./components/ExportModal";
import ConfirmDialog from "./components/ConfirmDialog";

function normalizarItensUpload(itensUpload) {
  return itensUpload.map((item) => ({
    item_id: item.item_id,
    arquivo_original: item.arquivo_original,
    arquivo_saida: "",
    status: item.status,
    motivo: "",
    origem: item.origem || "",
    detalhe: "",
    largura_original: 0,
    altura_original: 0,
  }));
}

function mensagemDeErro(erro) {
  if (isErroDeConexao(erro)) {
    return `Servidor não encontrado. Verifique se o backend está rodando em ${API_BASE_URL}.`;
  }
  return erro?.response?.data?.detail || "Ocorreu um erro inesperado ao falar com o servidor.";
}

export default function App() {
  const [sessaoId, setSessaoId] = useState(null);
  const [itens, setItens] = useState([]);
  const [estadoSessao, setEstadoSessao] = useState("aguardando");
  const [progresso, setProgresso] = useState({ concluidos: 0, total: 0 });

  const [carregandoSessao, setCarregandoSessao] = useState(true);
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState(null);

  const [itemPreview, setItemPreview] = useState(null);
  const [mostrarExportModal, setMostrarExportModal] = useState(false);
  const [exportando, setExportando] = useState(false);
  const [erroExportar, setErroExportar] = useState(null);
  const [exportOk, setExportOk] = useState(null);
  const [mostrarConfirmLimpar, setMostrarConfirmLimpar] = useState(false);

  const sessaoIdRef = useRef(null);
  sessaoIdRef.current = sessaoId;

  const iniciarSessao = useCallback(async () => {
    setCarregandoSessao(true);
    setErro(null);
    try {
      const id = await criarSessao();
      setSessaoId(id);
    } catch (e) {
      setErro(mensagemDeErro(e));
    } finally {
      setCarregandoSessao(false);
    }
  }, []);

  useEffect(() => {
    iniciarSessao();
  }, [iniciarSessao]);

  // Garante que a sessão (e seus temporários) não fiquem esquecidos no
  // servidor se a aba for fechada com fotos ainda carregadas.
  useEffect(() => {
    function aoFechar() {
      if (sessaoIdRef.current) removerSessaoAoFechar(sessaoIdRef.current);
    }
    window.addEventListener("pagehide", aoFechar);
    return () => window.removeEventListener("pagehide", aoFechar);
  }, []);

  // Polling de status enquanto a sessão está processando — para assim que
  // termina, sem deixar requisição rodando à toa.
  useEffect(() => {
    if (estadoSessao !== "processando" || !sessaoId) return undefined;

    const intervalId = setInterval(async () => {
      try {
        const resposta = await obterStatus(sessaoId);
        setItens(resposta.itens);
        setProgresso({ concluidos: resposta.concluidos, total: resposta.total });
        setEstadoSessao(resposta.estado);
        if (resposta.estado === "concluido") {
          clearInterval(intervalId);
        }
      } catch (e) {
        setErro(mensagemDeErro(e));
        clearInterval(intervalId);
      }
    }, 1000);

    return () => clearInterval(intervalId);
  }, [estadoSessao, sessaoId]);

  async function handleArquivos(arquivos) {
    if (!sessaoId) return;
    setEnviando(true);
    setErro(null);
    try {
      const itensResp = await enviarArquivos(sessaoId, arquivos);
      setItens(normalizarItensUpload(itensResp));
    } catch (e) {
      setErro(mensagemDeErro(e));
    } finally {
      setEnviando(false);
    }
  }

  async function handleProcessar() {
    if (!sessaoId) return;
    setErro(null);
    try {
      const resp = await processar(sessaoId);
      setEstadoSessao(resp.estado);
    } catch (e) {
      setErro(mensagemDeErro(e));
    }
  }

  async function handleExportar(pasta) {
    setExportando(true);
    setErroExportar(null);
    try {
      const resp = await exportar(sessaoId, pasta);
      setExportOk(resp.pasta_saida);
      setMostrarExportModal(false);
    } catch (e) {
      setErroExportar(mensagemDeErro(e));
    } finally {
      setExportando(false);
    }
  }

  async function handleLimparConfirmado() {
    setMostrarConfirmLimpar(false);
    const idAtual = sessaoId;
    setItens([]);
    setEstadoSessao("aguardando");
    setProgresso({ concluidos: 0, total: 0 });
    setExportOk(null);
    setErro(null);
    if (idAtual) {
      try {
        await removerSessao(idAtual);
      } catch {
        // Sessão pode já não existir no servidor — segue para criar uma nova de qualquer forma.
      }
    }
    await iniciarSessao();
  }

  const processando = estadoSessao === "processando";
  const podeProcessar = Boolean(sessaoId) && itens.length > 0 && estadoSessao === "aguardando" && !enviando;
  const podeExportar = estadoSessao === "concluido";

  const prontas = itens.filter((i) => i.status === "Pronto").length;
  const revisar = itens.filter((i) => i.status === "Revisar").length;
  const errosCount = itens.filter((i) => i.status === "Erro").length;

  return (
    <div className="min-h-screen">
      <ErrorBanner
        mensagem={erro}
        onRetry={sessaoId ? undefined : iniciarSessao}
        onFechar={() => setErro(null)}
      />

      <header className="border-b border-gray-200 bg-white px-6 py-4">
        <div className="mx-auto flex max-w-4xl items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gray-900">
            <ImageIcon size={18} className="text-white" />
          </div>
          <div>
            <h1 className="text-lg font-semibold text-gray-900">Vision</h1>
            <p className="text-sm text-gray-500">Padronização de fotos de empregados</p>
          </div>
        </div>
      </header>

      <main className="mx-auto flex max-w-4xl flex-col gap-5 px-6 py-6">
        {carregandoSessao && !erro && <p className="text-sm text-gray-500">Conectando ao servidor…</p>}

        <UploadZone onArquivos={handleArquivos} desabilitado={!sessaoId || estadoSessao !== "aguardando" || enviando} />

        <Toolbar
          podeProcessar={podeProcessar}
          processando={processando}
          podeExportar={podeExportar}
          temItens={itens.length > 0}
          onProcessar={handleProcessar}
          onExportar={() => setMostrarExportModal(true)}
          onLimpar={() => setMostrarConfirmLimpar(true)}
        />

        {processando && <ProgressBar concluidos={progresso.concluidos} total={progresso.total} />}

        {exportOk && (
          <div className="flex items-center gap-2 rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-800">
            <CheckCircle2 size={18} className="shrink-0" />
            <span>
              Exportado com sucesso para <strong>{exportOk}</strong>.
            </span>
          </div>
        )}

        {estadoSessao === "concluido" && <Summary prontas={prontas} revisar={revisar} erros={errosCount} />}

        <FileList itens={itens} sessaoId={sessaoId} estadoSessao={estadoSessao} onAbrirPreview={setItemPreview} />
      </main>

      <footer className="mx-auto max-w-4xl px-6 py-6 text-center text-xs text-gray-400">
        Vision — desenvolvido por Jaqueline Batista
      </footer>

      {itemPreview && <PreviewModal sessaoId={sessaoId} item={itemPreview} onFechar={() => setItemPreview(null)} />}

      {mostrarExportModal && (
        <ExportModal
          exportando={exportando}
          erro={erroExportar}
          onExportar={handleExportar}
          onCancelar={() => {
            setMostrarExportModal(false);
            setErroExportar(null);
          }}
        />
      )}

      {mostrarConfirmLimpar && (
        <ConfirmDialog
          titulo="Limpar sessão?"
          mensagem="Todos os arquivos enviados e resultados desta sessão serão apagados do servidor. Essa ação não pode ser desfeita."
          textoConfirmar="Limpar sessão"
          onConfirmar={handleLimparConfirmado}
          onCancelar={() => setMostrarConfirmLimpar(false)}
        />
      )}
    </div>
  );
}
