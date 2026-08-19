export default function ProgressBar({ concluidos, total }) {
  const percentual = total > 0 ? Math.round((concluidos / total) * 100) : 0;
  return (
    <div className="rounded-lg border border-blue-200 bg-blue-50 px-4 py-3">
      <div className="mb-1.5 flex items-center justify-between text-sm font-medium text-blue-800">
        <span>Processando fotos…</span>
        <span>
          {concluidos} de {total} ({percentual}%)
        </span>
      </div>
      <div className="h-2.5 w-full overflow-hidden rounded-full bg-blue-100">
        <div
          className="h-full rounded-full bg-blue-500 transition-all duration-300"
          style={{ width: `${percentual}%` }}
        />
      </div>
    </div>
  );
}
