"""Gera o executável Windows do Vision (Etapa 7): builda o frontend e roda o
PyInstaller sobre packaging/Vision.spec.

Pré-requisito: `pip install -r requirements.txt -r requirements-build.txt`
(o segundo arquivo tem o PyInstaller — só quem empacota precisa dele).

Uso: python scripts/build_exe.py
"""

import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CAMINHO_ONNX = RAIZ / "backend" / "models" / "face_detection_yunet_2023mar.onnx"
PASTA_FRONTEND = RAIZ / "frontend"
ESPECIFICACAO = RAIZ / "packaging" / "Vision.spec"
PASTA_DIST = RAIZ / "dist"
PASTA_BUILD = RAIZ / "build"


def main() -> int:
    if not CAMINHO_ONNX.is_file():
        print(f"Erro: modelo YuNet não encontrado em {CAMINHO_ONNX}")
        return 1

    print("Buildando o frontend (npm run build)...")
    resultado = subprocess.run(["npm", "run", "build"], cwd=PASTA_FRONTEND, shell=True)
    if resultado.returncode != 0:
        print("Erro: falha ao buildar o frontend.")
        return 1

    print("Gerando o executável (PyInstaller)...")
    resultado = subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            str(ESPECIFICACAO),
            "--noconfirm",
            "--distpath",
            str(PASTA_DIST),
            "--workpath",
            str(PASTA_BUILD),
        ],
        cwd=RAIZ,
    )
    if resultado.returncode != 0:
        print("Erro: falha ao gerar o executável.")
        return 1

    caminho_exe = PASTA_DIST / "Vision" / "Vision.exe"
    print(f"\nExecutável gerado em: {caminho_exe}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
