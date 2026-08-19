import Thumbnail from "./Thumbnail";
import StatusBadge from "./StatusBadge";
import { statusExibicao, statusPrioritario } from "../utils/status";

// Um item tem imagem processada em disco (e portanto pode ser clicado para
// prévia lado a lado) sempre que o pipeline chegou a gravar uma saída —
// tanto Pronto quanto Revisar produzem arquivo_saida (ver
// backend/services/pipeline.py::_processar_imagem); só Erro nunca tem.
function temSaidaProcessada(item) {
  return item.status === "Pronto" || item.status === "Revisar";
}

function LinhaItem({ item, sessaoId, estadoSessao, onAbrirPreview }) {
  const clicavel = temSaidaProcessada(item);
  const status = statusExibicao(item, estadoSessao);

  return (
    <button
      type="button"
      onClick={() => clicavel && onAbrirPreview(item)}
      disabled={!clicavel}
      className={`flex w-full items-center gap-3 rounded-md px-2 py-2 text-left ${
        clicavel ? "cursor-pointer hover:bg-gray-50" : "cursor-default"
      }`}
    >
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm text-gray-700">{item.origem || item.arquivo_original}</p>
        {item.motivo && item.motivo !== "-" && <p className="truncate text-xs text-gray-500">{item.motivo}</p>}
      </div>
      <StatusBadge status={status} />
    </button>
  );
}

export default function FileCard({ grupo, sessaoId, estadoSessao, onAbrirPreview }) {
  const primeiroItem = grupo.itens[0];
  const statusGrupo = grupo.isPdf
    ? statusExibicao({ status: statusPrioritario(grupo.itens.map((i) => i.status)) }, estadoSessao)
    : statusExibicao(primeiroItem, estadoSessao);

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4">
      <div className="flex items-start gap-4">
        <Thumbnail sessaoId={sessaoId} itemId={primeiroItem.item_id} />
        <div className="min-w-0 flex-1">
          <p className="truncate font-medium text-gray-900">{grupo.arquivoOriginal}</p>
          {grupo.isPdf && <p className="text-sm text-gray-500">{grupo.itens.length} página(s) identificada(s)</p>}
          <div className="mt-1.5 flex items-center gap-2">
            <StatusBadge status={statusGrupo} />
          </div>
          {!grupo.isPdf && primeiroItem.motivo && primeiroItem.motivo !== "-" && (
            <p className="mt-1 text-sm text-gray-500">{primeiroItem.motivo}</p>
          )}
          {!grupo.isPdf && temSaidaProcessada(primeiroItem) && (
            <button
              type="button"
              onClick={() => onAbrirPreview(primeiroItem)}
              className="mt-2 text-sm font-medium text-blue-600 hover:underline"
            >
              Ver prévia
            </button>
          )}
        </div>
      </div>

      {grupo.isPdf && (
        <ul className="mt-3 divide-y divide-gray-100 border-t border-gray-100 pt-1">
          {grupo.itens.map((item) => (
            <li key={item.item_id}>
              <LinhaItem item={item} sessaoId={sessaoId} estadoSessao={estadoSessao} onAbrirPreview={onAbrirPreview} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
