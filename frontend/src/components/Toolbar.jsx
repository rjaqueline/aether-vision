import { Play, FolderOutput, Trash2 } from "lucide-react";

export default function Toolbar({
  podeProcessar,
  processando,
  podeExportar,
  temItens,
  onProcessar,
  onExportar,
  onLimpar,
}) {
  return (
    <div className="flex flex-wrap gap-3">
      <button
        onClick={onProcessar}
        disabled={!podeProcessar}
        className="flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-gray-300"
      >
        <Play size={16} />
        {processando ? "Processando…" : "Processar"}
      </button>
      <button
        onClick={onExportar}
        disabled={!podeExportar}
        className="flex items-center gap-2 rounded-md border border-gray-300 bg-white px-4 py-2.5 text-sm font-semibold text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
      >
        <FolderOutput size={16} />
        Exportar
      </button>
      <button
        onClick={onLimpar}
        disabled={!temItens}
        className="ml-auto flex items-center gap-2 rounded-md border border-gray-300 bg-white px-4 py-2.5 text-sm font-semibold text-gray-700 hover:bg-red-50 hover:text-red-700 hover:border-red-200 disabled:cursor-not-allowed disabled:opacity-50"
      >
        <Trash2 size={16} />
        Limpar sessão
      </button>
    </div>
  );
}
