import { useState } from "react";
import { ImageOff } from "lucide-react";
import { urlPreview } from "../api/client";

export default function Thumbnail({ sessaoId, itemId, tamanho = "h-16 w-16" }) {
  const [comErro, setComErro] = useState(false);

  return (
    <div className={`${tamanho} flex shrink-0 items-center justify-center overflow-hidden rounded-md border border-gray-100 bg-gray-50`}>
      {comErro ? (
        <ImageOff size={18} className="text-gray-300" />
      ) : (
        <img
          src={urlPreview(sessaoId, itemId, "original")}
          alt=""
          className="h-full w-full object-cover"
          onError={() => setComErro(true)}
        />
      )}
    </div>
  );
}
