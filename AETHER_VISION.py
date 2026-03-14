# AETHER VISION – Sistema de Inteligência Visual Sensível
# Dev by Jaqueline Batista dos Santos


import os
import cv2
import numpy as np
from PIL import Image
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
from tkinter import ttk
import shutil

FINAL_SIZE = (160, 160)


face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

def ajustar_qualidade(imagem_pil, caminho_saida):
    imagem_pil = imagem_pil.convert("RGB")
    qualidade = 95
    while True:
        imagem_pil.save(caminho_saida, format="JPEG", quality=qualidade, optimize=True, progressive=False, subsampling=0)
        tamanho_kb = os.path.getsize(caminho_saida) / 1024
        if tamanho_kb <= MAX_KB or qualidade <= 50:
            break
        qualidade -= 5
    return round(tamanho_kb, 2)

def mover_para_ruins(caminho_img, nome_arquivo, motivo, base_dir):
    destino = os.path.join(base_dir, "FotosRuins", motivo, nome_arquivo)
    shutil.copy(caminho_img, destino)
    return f"⛔ [{motivo.replace('_', ' ').title()}] {nome_arquivo}"

def processar_imagem(caminho_img, nome_arquivo, base_dir):
    if nome_arquivo.lower().endswith(".pdf"):
        return mover_para_ruins(caminho_img, nome_arquivo, "formato_pdf", base_dir)

    imagem_cv = cv2.imdecode(np.fromfile(caminho_img, dtype=np.uint8), cv2.IMREAD_COLOR)
    if imagem_cv is None:
        return f"⚠️ Imagem ignorada: {nome_arquivo} (nome contém acentos ou está corrompida)"

    faces = face_cascade.detectMultiScale(imagem_cv, scaleFactor=1.1, minNeighbors=5)
    if len(faces) == 0:
        return mover_para_ruins(caminho_img, nome_arquivo, "sem_rosto", base_dir)
    elif len(faces) > 1:
        return mover_para_ruins(caminho_img, nome_arquivo, "multiplos_rostos", base_dir)

    x, y, w, h = faces[0]
    if w < 80 or h < 80:
        return mover_para_ruins(caminho_img, nome_arquivo, "rosto_pequeno", base_dir)

    margem = 0.6
    lado_crop = int(max(w, h) * (1 + margem))
    centro_x = x + w // 2
    centro_y = y + h // 2
    esquerda = max(0, centro_x - lado_crop // 2)
    topo = max(0, centro_y - lado_crop // 2)
    direita = esquerda + lado_crop
    inferior = topo + lado_crop

    imagem_cropada = imagem_cv[topo:inferior, esquerda:direita]
    imagem_pil = Image.fromarray(cv2.cvtColor(imagem_cropada, cv2.COLOR_BGR2RGB)).convert("RGB")
    imagem_redimensionada = imagem_pil.resize(FINAL_SIZE, Image.LANCZOS)

    novo_nome = os.path.splitext(nome_arquivo)[0] + ".jpeg"
    caminho_saida = os.path.join(base_dir, "FotosEditadas", novo_nome)
    tamanho_final = ajustar_qualidade(imagem_redimensionada, caminho_saida)
    return f"✅ [Aprovada] {novo_nome} salva com {tamanho_final}KB"

def selecionar_pasta():
    pasta = filedialog.askdirectory()
    if pasta:
        entrada_var.set(pasta)

def rodar_fiscal():
    entrada = entrada_var.get()
    if not entrada or not os.path.exists(entrada):
        messagebox.showerror("Erro", "Selecione uma pasta válida.")
        return

    base_dir = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(os.path.join(base_dir, "FotosEditadas"), exist_ok=True)
    for sub in ["sem_rosto", "multiplos_rostos", "rosto_pequeno", "formato_pdf"]:
        os.makedirs(os.path.join(base_dir, "FotosRuins", sub), exist_ok=True)

    log_text.delete("1.0", tk.END)

    # Coleta todas as imagens em subpastas
    arquivos = []
    for raiz, _, nomes in os.walk(entrada):
        for nome in nomes:
            if nome.lower().endswith((".jpg", ".jpeg", ".png", ".pdf")):
                arquivos.append((os.path.join(raiz, nome), nome))

    total = len(arquivos)
    if total == 0:
        messagebox.showinfo("Aviso", "Nenhuma imagem encontrada.")
        return

    barra_progresso["maximum"] = total
    barra_progresso["value"] = 0

    for i, (caminho_img, nome_arquivo) in enumerate(arquivos, start=1):
        resultado = processar_imagem(caminho_img, nome_arquivo, base_dir)
        log_text.insert(tk.END, resultado + "\n")
        log_text.see(tk.END)
        barra_progresso["value"] = i
        janela.update_idletasks()

# Interface gráfica
janela = tk.Tk()
janela.title("AETHER VISION – por Jaqueline Batista")
janela.geometry("600x450")
janela.iconbitmap(default='')

entrada_var = tk.StringVar()

frame = tk.Frame(janela)
frame.pack(pady=10)

tk.Label(frame, text="Pasta principal com fotos:").pack(side=tk.LEFT, padx=5)
tk.Entry(frame, textvariable=entrada_var, width=40).pack(side=tk.LEFT, padx=5)
tk.Button(frame, text="Selecionar", command=selecionar_pasta).pack(side=tk.LEFT, padx=5)

tk.Button(janela, text="Rodar AETHER VISION", command=rodar_fiscal, bg="green", fg="white").pack(pady=10)

barra_progresso = ttk.Progressbar(janela, orient="horizontal", length=500, mode="determinate")
barra_progresso.pack(pady=5)

log_text = scrolledtext.ScrolledText(janela, width=70, height=15)
log_text.pack(pady=10)

janela.mainloop()
