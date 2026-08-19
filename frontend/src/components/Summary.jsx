import { CheckCircle2, AlertCircle, XCircle } from "lucide-react";

export default function Summary({ prontas, revisar, erros }) {
  return (
    <div className="grid grid-cols-3 gap-3">
      <div className="flex items-center gap-3 rounded-lg border border-green-200 bg-green-50 px-4 py-3">
        <CheckCircle2 className="text-green-600" size={22} />
        <div>
          <p className="text-lg font-semibold leading-none text-green-800">{prontas}</p>
          <p className="text-sm text-green-700">prontas</p>
        </div>
      </div>
      <div className="flex items-center gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3">
        <AlertCircle className="text-amber-600" size={22} />
        <div>
          <p className="text-lg font-semibold leading-none text-amber-800">{revisar}</p>
          <p className="text-sm text-amber-700">para revisar</p>
        </div>
      </div>
      <div className="flex items-center gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3">
        <XCircle className="text-red-600" size={22} />
        <div>
          <p className="text-lg font-semibold leading-none text-red-800">{erros}</p>
          <p className="text-sm text-red-700">com erro</p>
        </div>
      </div>
    </div>
  );
}
