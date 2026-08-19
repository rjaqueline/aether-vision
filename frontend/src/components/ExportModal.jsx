import { useEffect, useRef, useState } from "react";
import { FolderOpen, CheckCircle2, XCircle } from "lucide-react";
import { obterPastasSugeridas, validarPasta } from "../api/client";

// Espera o usuário parar de digitar antes de validar no servidor, para não
// disparar uma requisição a cada tecla.
const ATRASO_VALIDACAO_MS = 400;

export default function ExportModal({ onExportar, onCancelar, exportando, erro }) {
  const [pasta, setPasta] = useState("");
  const [pastasSugeridas, setPastasSugeridas] = useState([]);
  const [validacao, setValidacao] = useState(null); // null = ainda não validado (campo vazio ou digitando)
  const timeoutRef = useRef(null);

  useEffect(() => {
    obterPastasSugeridas()
      .then(setPastasSugeridas)
      .catch(() => {
        // Atalhos são um extra de conveniência — se a busca falhar, o campo
        // manual continua funcionando normalmente.
      });
  }, []);

  useEffect(() => {
    clearTimeout(timeoutRef.current);
    if (!pasta.trim()) {
      setValidacao(null);
      return undefined;
    }
    setValidacao(null);
    timeoutRef.current = setTimeout(async () => {
      try {
        const resultado = await validarPasta(pasta.trim());
        setValidacao(resultado);
      } catch {
        // Falha ao validar (ex.: backend fora do ar) não deve travar o
        // usuário — sem feedback visual, mas o botão Exportar continua
        // disponível e a checagem real acontece de novo no servidor ao enviar.
        setValidacao(null);
      }
    }, ATRASO_VALIDACAO_MS);
    return () => clearTimeout(timeoutRef.current);
  }, [pasta]);

  function confirmar() {
    if (pasta.trim()) onExportar(pasta.trim());
  }

  const invalida = validacao != null && !validacao.valida;
  const bordaClasse = validacao == null
    ? "border-gray-300 focus:border-gray-500"
    : validacao.valida
      ? "border-green-500 focus:border-green-500"
      : "border-red-500 focus:border-red-500";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
      <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
        <div className="flex items-center gap-2">
          <FolderOpen className="text-gray-700" size={22} />
          <h3 className="text-lg font-semibold text-gray-900">Exportar fotos processadas</h3>
        </div>
        <p className="mt-2 text-sm text-gray-600">
          Informe o caminho completo da pasta de destino no seu computador. Uma pasta com o nome
          Vision_Processadas_AAAA-MM-DD_HHhMM (data e hora do processamento) será criada dentro dela, com as
          fotos aprovadas, as que precisam de revisão e o relatório.
        </p>

        {pastasSugeridas.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {pastasSugeridas.map((sugestao) => (
              <button
                key={sugestao.caminho}
                type="button"
                onClick={() => setPasta(sugestao.caminho)}
                className="rounded-full border border-gray-300 px-3 py-1 text-xs font-medium text-gray-700 hover:bg-gray-50"
              >
                {sugestao.nome}
              </button>
            ))}
          </div>
        )}

        <div className="relative mt-4">
          <input
            type="text"
            value={pasta}
            onChange={(e) => setPasta(e.target.value)}
            placeholder="Ex.: C:\Users\SeuUsuario\Desktop\Fotos"
            autoFocus
            className={`w-full rounded-md border px-3 py-2 pr-9 text-sm focus:outline-none ${bordaClasse}`}
          />
          {validacao != null && (
            <span className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2">
              {validacao.valida ? (
                <CheckCircle2 className="text-green-600" size={18} />
              ) : (
                <XCircle className="text-red-600" size={18} />
              )}
            </span>
          )}
        </div>
        {invalida && <p className="mt-1 text-sm text-red-600">{validacao.mensagem}</p>}

        {erro && <p className="mt-2 text-sm text-red-600">{erro}</p>}
        <div className="mt-6 flex justify-end gap-3">
          <button
            onClick={onCancelar}
            disabled={exportando}
            className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
          >
            Cancelar
          </button>
          <button
            onClick={confirmar}
            disabled={exportando || !pasta.trim() || invalida}
            className="rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-700 disabled:cursor-not-allowed disabled:bg-gray-300"
          >
            {exportando ? "Exportando…" : "Exportar"}
          </button>
        </div>
      </div>
    </div>
  );
}
