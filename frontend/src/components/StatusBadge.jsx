import { STATUS_INFO } from "../utils/status";

export default function StatusBadge({ status }) {
  const info = STATUS_INFO[status] ?? STATUS_INFO.Aguardando;
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-sm font-medium ${info.cor}`}>
      <span className={`h-2 w-2 rounded-full ${info.ponto}`} />
      {status}
    </span>
  );
}
