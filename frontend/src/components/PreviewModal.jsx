import { X } from "lucide-react";
import { urlPreview } from "../api/client";
import StatusBadge from "./StatusBadge";

export default function PreviewModal({ sessaoId, item, onFechar }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4" onClick={onFechar}>
      <div
        className="max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-xl bg-white p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h3 className="text-lg font-semibold text-gray-900">{item.arquivo_original}</h3>
            {item.origem && <p className="text-sm text-gray-500">{item.origem}</p>}
            <div className="mt-2">
              <StatusBadge status={item.status} />
            </div>
            {item.motivo && item.motivo !== "-" && <p className="mt-1 text-sm text-gray-600">{item.motivo}</p>}
          </div>
          <button onClick={onFechar} className="rounded-md p-1.5 text-gray-500 hover:bg-gray-100">
            <X size={20} />
          </button>
        </div>

        <div className="mt-5 grid grid-cols-2 gap-4">
          <div>
            <p className="mb-2 text-center text-sm font-medium text-gray-500">Original</p>
            <img
              src={urlPreview(sessaoId, item.item_id, "original")}
              alt="Original"
              className="mx-auto max-h-[50vh] rounded-lg border border-gray-200 object-contain"
            />
          </div>
          <div>
            <p className="mb-2 text-center text-sm font-medium text-gray-500">Processado</p>
            <img
              src={urlPreview(sessaoId, item.item_id, "processada")}
              alt="Processado"
              className="mx-auto max-h-[50vh] rounded-lg border border-gray-200 object-contain"
            />
          </div>
        </div>
      </div>
    </div>
  );
}
