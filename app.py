"""PendrivePlay - janela principal (Tkinter)."""
from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import baixador
from pendrive import listar_pendrives

VERSAO = "1.0.0"
DICA = "Cole o link do vídeo aqui..."

FUNDO = "#0f1115"
CAIXA = "#1a1d24"
TEXTO = "#e5e7eb"
APAGADO = "#9ca3af"
VERDE = "#22c55e"
ESCOLHER_PASTA = "Escolher outra pasta..."


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.fila: queue.Queue = queue.Queue()  # mensagens da thread de download
        self.ocupado = False
        self.destinos: dict[str, Path] = {}     # texto da lista -> pasta
        self.ultima_pasta: Path | None = None

        root.title(f"PendrivePlay {VERSAO}")
        root.geometry("720x560")
        root.minsize(600, 500)
        root.configure(bg=FUNDO)
        self._estilos()
        self._montar_tela()

        self.atualizar_destinos()
        self.root.after(100, self._ler_fila)
        self.root.after(3000, self._vigiar_pendrives)

    # ---------- aparência ----------
    def _estilos(self) -> None:
        s = ttk.Style()
        s.theme_use("clam")
        s.configure("TFrame", background=FUNDO)
        s.configure("TLabel", background=FUNDO, foreground=TEXTO, font=("Segoe UI", 10))
        s.configure("Titulo.TLabel", font=("Segoe UI", 16, "bold"))
        s.configure("Fraco.TLabel", foreground=APAGADO)
        s.configure("TRadiobutton", background=FUNDO, foreground=TEXTO,
                    font=("Segoe UI", 10, "bold"), indicatorbackground=CAIXA,
                    indicatorforeground=VERDE, upperbordercolor=APAGADO,
                    lowerbordercolor=APAGADO)
        s.map("TRadiobutton", background=[("active", FUNDO)],
              indicatorbackground=[("pressed", CAIXA), ("selected", CAIXA)])
        s.configure("TCombobox", fieldbackground=CAIXA, background=CAIXA,
                    foreground=TEXTO, arrowcolor=TEXTO)
        s.map("TCombobox", fieldbackground=[("readonly", CAIXA)],
              foreground=[("readonly", TEXTO)])
        s.configure("TButton", background="#1f2937", foreground=TEXTO,
                    borderwidth=0, padding=(12, 6))
        s.map("TButton", background=[("active", "#374151")])
        s.configure("Baixar.TButton", background=VERDE, foreground="#052e16",
                    font=("Segoe UI", 12, "bold"), padding=(30, 10))
        s.map("Baixar.TButton", background=[("disabled", "#14532d"), ("active", "#16a34a")])
        s.configure("Horizontal.TProgressbar", background=VERDE, troughcolor=CAIXA,
                    borderwidth=0)

    def _montar_tela(self) -> None:
        f = ttk.Frame(self.root, padding=20)
        f.pack(fill="both", expand=True)

        ttk.Label(f, text="PendrivePlay", style="Titulo.TLabel").pack(anchor="w")
        ttk.Label(f, text="Baixa e salva direto no pendrive, pronto para a TV.",
                  style="Fraco.TLabel").pack(anchor="w", pady=(0, 14))

        # Link
        self.entrada = tk.Entry(f, font=("Segoe UI", 11), bg=CAIXA, fg=APAGADO,
                                insertbackground=TEXTO, relief="flat")
        self.entrada.pack(fill="x", ipady=9)
        self.entrada.insert(0, DICA)
        self.entrada.bind("<FocusIn>", self._limpar_dica)
        self.entrada.bind("<FocusOut>", self._mostrar_dica)
        self.entrada.bind("<Return>", lambda e: self.iniciar())

        # Formato
        self.formato = tk.StringVar(value="mp4")
        linha = ttk.Frame(f)
        linha.pack(fill="x", pady=12)
        ttk.Radiobutton(linha, text="Vídeo MP4 para TV", variable=self.formato,
                        value="mp4").pack(side="left", padx=(0, 20))
        ttk.Radiobutton(linha, text="Música MP3", variable=self.formato,
                        value="mp3").pack(side="left")

        # Destino (pendrive)
        ttk.Label(f, text="Salvar em:").pack(anchor="w")
        linha = ttk.Frame(f)
        linha.pack(fill="x", pady=(4, 0))
        self.destino = ttk.Combobox(linha, state="readonly", font=("Segoe UI", 10))
        self.destino.pack(side="left", fill="x", expand=True, ipady=4)
        self.destino.bind("<<ComboboxSelected>>", self._destino_escolhido)
        ttk.Button(linha, text="Atualizar", command=self.atualizar_destinos).pack(
            side="left", padx=(8, 0))
        self.info_destino = ttk.Label(f, text="", style="Fraco.TLabel")
        self.info_destino.pack(anchor="w", pady=(4, 0))

        # Botões
        linha = ttk.Frame(f)
        linha.pack(pady=14)
        self.botao = ttk.Button(linha, text="Baixar", style="Baixar.TButton",
                                command=self.iniciar)
        self.botao.pack(side="left", padx=5)
        ttk.Button(linha, text="Abrir pasta", command=self.abrir_pasta).pack(
            side="left", padx=5)

        # Progresso e status
        self.barra = ttk.Progressbar(f, mode="determinate", maximum=100)
        self.barra.pack(fill="x")
        self.status = ttk.Label(f, text="Pronto", style="Fraco.TLabel")
        self.status.pack(anchor="w", pady=(6, 6))

        self.log = tk.Text(f, height=8, bg=CAIXA, fg=APAGADO, relief="flat",
                           font=("Consolas", 9), state="disabled", wrap="word")
        self.log.pack(fill="both", expand=True)

    # ---------- campo de link ----------
    def _limpar_dica(self, _e=None) -> None:
        if self.entrada.get() == DICA:
            self.entrada.delete(0, "end")
            self.entrada.config(fg=TEXTO)

    def _mostrar_dica(self, _e=None) -> None:
        if not self.entrada.get().strip():
            self.entrada.delete(0, "end")
            self.entrada.insert(0, DICA)
            self.entrada.config(fg=APAGADO)

    # ---------- pendrive ----------
    def atualizar_destinos(self) -> None:
        atual = self.destinos.get(self.destino.get())
        self.destinos = {u.rotulo(): u.raiz for u in listar_pendrives()}
        if self.ultima_pasta and self.ultima_pasta not in self.destinos.values():
            self.destinos[str(self.ultima_pasta)] = self.ultima_pasta
        opcoes = list(self.destinos) + [ESCOLHER_PASTA]
        self.destino["values"] = opcoes

        # mantém a escolha anterior se ela ainda existir
        for rotulo, raiz in self.destinos.items():
            if raiz == atual:
                self.destino.set(rotulo)
                break
        else:
            self.destino.set(opcoes[0] if self.destinos else "")
        self._mostrar_info_destino()

    def _vigiar_pendrives(self) -> None:
        """A cada 3 s confere se um pendrive foi conectado ou removido."""
        if not self.ocupado:
            antes = set(self.destinos.values())
            depois = {u.raiz for u in listar_pendrives()}
            if self.ultima_pasta:
                depois.add(self.ultima_pasta)
            if antes != depois:
                self.atualizar_destinos()
        self.root.after(3000, self._vigiar_pendrives)

    def _destino_escolhido(self, _e=None) -> None:
        if self.destino.get() == ESCOLHER_PASTA:
            pasta = filedialog.askdirectory(title="Escolha onde salvar")
            if pasta:
                self.ultima_pasta = Path(pasta)
            self.atualizar_destinos()
            if pasta:
                self.destino.set(str(self.ultima_pasta))
        self._mostrar_info_destino()

    def _mostrar_info_destino(self) -> None:
        raiz = self.destinos.get(self.destino.get())
        if raiz is None:
            self.info_destino.config(
                text="Nenhum pendrive encontrado. Conecte um (aparece sozinho) "
                     "ou escolha outra pasta.", foreground="#f59e0b")
        else:
            self.info_destino.config(
                text=f"Vídeos → {raiz / baixador.PASTA_VIDEOS}     "
                     f"Músicas → {raiz / baixador.PASTA_MP3}", foreground=APAGADO)

    def abrir_pasta(self) -> None:
        raiz = self.destinos.get(self.destino.get())
        if raiz is None:
            return
        pasta = baixador.preparar_destino(raiz, self.formato.get())
        if sys.platform == "win32":
            os.startfile(pasta)
        else:
            subprocess.Popen(["xdg-open", str(pasta)])

    # ---------- download ----------
    def iniciar(self) -> None:
        if self.ocupado:
            return
        url = self.entrada.get().strip()
        if not url.startswith("http"):
            messagebox.showwarning("PendrivePlay", "Cole um link de vídeo válido.")
            return
        raiz = self.destinos.get(self.destino.get())
        if raiz is None:
            messagebox.showwarning("PendrivePlay", "Conecte um pendrive ou escolha uma pasta.")
            return

        self.ocupado = True
        self.botao.state(["disabled"])
        self.barra["value"] = 0
        self.escrever_log(f"--- {url}")
        formato = self.formato.get()
        threading.Thread(target=self._trabalho, args=(url, formato, raiz),
                         daemon=True).start()

    def _trabalho(self, url: str, formato: str, raiz: Path) -> None:
        """Roda em outra thread: só conversa com a tela pela fila."""
        try:
            salvos = baixador.baixar(
                url, formato, raiz,
                aviso=lambda m: self.fila.put(("aviso", m)),
                progresso=lambda p: self.fila.put(("progresso", p)),
            )
            self.fila.put(("fim", salvos))
        except Exception as erro:  # mostra qualquer erro na tela
            self.fila.put(("erro", str(erro)))

    def _ler_fila(self) -> None:
        """Roda na thread da tela e aplica as mensagens da fila."""
        try:
            while True:
                tipo, dado = self.fila.get_nowait()
                if tipo == "aviso":
                    self.status.config(text=dado[:90])
                    self.escrever_log(dado)
                elif tipo == "progresso":
                    self.barra["value"] = dado
                elif tipo == "fim":
                    self._terminar()
                    self.barra["value"] = 100
                    self.status.config(text=f"Pronto! {len(dado)} arquivo(s) salvo(s).")
                    messagebox.showinfo(
                        "PendrivePlay",
                        f"{len(dado)} arquivo(s) salvo(s) em:\n{dado[0].parent}\n\n"
                        "Antes de tirar o pendrive, use \"Ejetar\" no Windows.")
                elif tipo == "erro":
                    self._terminar()
                    self.status.config(text="Deu erro. Veja abaixo.")
                    self.escrever_log(f"ERRO: {dado}")
                    messagebox.showerror("PendrivePlay", dado)
        except queue.Empty:
            pass
        self.root.after(100, self._ler_fila)

    def _terminar(self) -> None:
        self.ocupado = False
        self.botao.state(["!disabled"])
        self.atualizar_destinos()  # atualiza o espaço livre

    def escrever_log(self, texto: str) -> None:
        self.log.config(state="normal")
        self.log.insert("end", texto + "\n")
        self.log.see("end")
        self.log.config(state="disabled")


def main() -> None:
    if "--autoteste" in sys.argv:
        import autoteste
        i = sys.argv.index("--autoteste")
        saida = sys.argv[i + 1] if len(sys.argv) > i + 1 else None
        sys.exit(autoteste.rodar(Path(saida) if saida else None))

    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
