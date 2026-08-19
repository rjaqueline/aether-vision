import FileCard from "./FileCard";
import { agruparPorArquivo } from "../utils/status";

export default function FileList({ itens, sessaoId, estadoSessao, onAbrirPreview }) {
  const grupos = agruparPorArquivo(itens);

  if (grupos.length === 0) {
    return <p className="py-8 text-center text-sm text-gray-400">Nenhum arquivo enviado ainda.</p>;
  }

  return (
    <div className="flex flex-col gap-3">
      {grupos.map((grupo) => (
        <FileCard
          key={grupo.arquivoOriginal}
          grupo={grupo}
          sessaoId={sessaoId}
          estadoSessao={estadoSessao}
          onAbrirPreview={onAbrirPreview}
        />
      ))}
    </div>
  );
}
