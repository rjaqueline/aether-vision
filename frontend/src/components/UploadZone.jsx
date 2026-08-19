import { useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { UploadCloud } from "lucide-react";

const ACEITOS = {
  "image/jpeg": [".jpg", ".jpeg"],
  "image/png": [".png"],
  "image/bmp": [".bmp"],
  "image/tiff": [".tif", ".tiff"],
  "image/webp": [".webp"],
  "application/pdf": [".pdf"],
};

export default function UploadZone({ onArquivos, desabilitado }) {
  const onDrop = useCallback(
    (arquivosAceitos) => {
      if (arquivosAceitos.length > 0) onArquivos(arquivosAceitos);
    },
    [onArquivos],
  );

  const { getRootProps, getInputProps, open, isDragActive } = useDropzone({
    onDrop,
    accept: ACEITOS,
    disabled: desabilitado,
    noClick: true,
    noKeyboard: true,
  });

  return (
    <div
      {...getRootProps()}
      className={`flex flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed px-6 py-10 text-center transition-colors ${
        desabilitado
          ? "cursor-not-allowed border-gray-200 bg-gray-50 opacity-60"
          : isDragActive
            ? "border-blue-400 bg-blue-50"
            : "border-gray-300 bg-white hover:border-gray-400"
      }`}
    >
      <input {...getInputProps()} />
      <UploadCloud size={40} className="text-gray-400" />
      <div>
        <p className="text-base font-medium text-gray-700">Arraste imagens ou PDFs aqui</p>
        <p className="mt-1 text-sm text-gray-500">Formatos aceitos: JPG, PNG, BMP, TIFF, WEBP e PDF — múltiplos arquivos</p>
      </div>
      <button
        type="button"
        onClick={open}
        disabled={desabilitado}
        className="mt-1 rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-700 disabled:cursor-not-allowed disabled:bg-gray-300"
      >
        Selecionar arquivos
      </button>
    </div>
  );
}
