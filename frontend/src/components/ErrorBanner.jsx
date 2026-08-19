import { AlertTriangle, X } from "lucide-react";

export default function ErrorBanner({ mensagem, onRetry, onFechar }) {
  if (!mensagem) return null;
  return (
    <div className="flex items-center justify-between gap-4 border-b border-red-200 bg-red-50 px-6 py-3 text-red-800">
      <div className="flex items-center gap-2">
        <AlertTriangle size={20} className="shrink-0" />
        <span className="text-sm font-medium">{mensagem}</span>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        {onRetry && (
          <button
            onClick={onRetry}
            className="rounded-md border border-red-300 bg-white px-3 py-1.5 text-sm font-medium text-red-700 hover:bg-red-100"
          >
            Tentar novamente
          </button>
        )}
        {onFechar && (
          <button onClick={onFechar} className="rounded-md p-1.5 text-red-700 hover:bg-red-100" aria-label="Fechar aviso">
            <X size={16} />
          </button>
        )}
      </div>
    </div>
  );
}
