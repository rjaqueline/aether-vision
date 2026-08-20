# -*- mode: python ; coding: utf-8 -*-
"""Spec do PyInstaller para o Vision (Etapa 7).

Onedir (não onefile) — usado para os dois formatos de entrega: o "portátil" é
esta pasta compactada em .zip, e um instalador futuro empacotaria o mesmo
conteúdo. Onefile foi descartado de propósito: ele reextrai opencv/pymupdf/
YuNet para uma pasta temporária a cada execução (vários segundos de espera
toda vez que alguém abre o programa) e é o padrão que mais desperta suspeita
de antivírus — dois modos de empacotamento dobrariam a superfície de bug pelo
mesmo resultado.

Gerado a partir de `pyi-makespec` e ajustado à mão (datas do modelo YuNet e do
frontend buildado, ícone). Não editar name='Vision' sem também ajustar
scripts/build_exe.py, que assume esse nome para achar o .exe final.

Rodar via scripts/build_exe.py (que builda o frontend antes) — não direto.
"""

from pathlib import Path

RAIZ = Path(SPECPATH).resolve().parent  # noqa: F821 — SPECPATH (pasta deste spec, packaging/) é injetado pelo PyInstaller

datas = [
    (str(RAIZ / "backend" / "models" / "face_detection_yunet_2023mar.onnx"), "models"),
    (str(RAIZ / "frontend" / "dist"), "frontend/dist"),
]

a = Analysis(
    [str(RAIZ / "desktop" / "app.py")],
    pathex=[str(RAIZ)],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Vision",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # Se um antivírus (comum em ambiente corporativo, ex.: Taboca) acusar
    # falso positivo no .exe, o primeiro passo é trocar para upx=False aqui
    # antes de escalar para assinatura de código — ver README.md.
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # Sem ícone dedicado ainda (nenhum .ico no repo) — sai com o padrão do
    # PyInstaller neste primeiro build; item de acompanhamento posterior.
    icon=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Vision",
)
