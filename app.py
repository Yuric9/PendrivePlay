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
DICA = "Cole os links aqui, um por linha..."

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
        root.geometry("720x680")
        root.minsize(600, 620)
        root.configure(bg=FUNDO)
        self._estilos()
        self._montar_tela()
        root.protocol("WM_DELETE_WINDOW", self.fechar_janela)

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
        ttk.Button(f, text="Sobre", command=self.sobre).place(relx=1.0, y=0, anchor="ne")
        ttk.Label(f, text="Baixa e salva direto no pendrive, pronto para a TV.",
                  style="Fraco.TLabel").pack(anchor="w", pady=(0, 14))

        # Link
        self.entrada = tk.Text(f, height=5, font=("Segoe UI", 10), bg=CAIXA, fg=APAGADO,
                               insertbackground=TEXTO, relief="flat", wrap="none",
                               padx=10, pady=8, undo=True)
        self.entrada.pack(fill="x")
        self.entrada.insert("1.0", DICA)
        self.entrada.bind("<FocusIn>", self._limpar_dica)
        self.entrada.bind("<FocusOut>", self._mostrar_dica)
        self.entrada.bind("<KeyRelease>", lambda e: self._contar_links())
        self.entrada.bind("<<Paste>>", lambda e: self.root.after(10, self._contar_links))
        self.entrada.bind("<Control-Return>", lambda e: (self.iniciar(), "break")[1])

        linha = ttk.Frame(f)
        linha.pack(fill="x", pady=(6, 0))
        self.contador = ttk.Label(linha, text="Nenhum link", style="Fraco.TLabel")
        self.contador.pack(side="left")
        ttk.Button(linha, text="Limpar", command=self.limpar_links).pack(side="right")
        ttk.Button(linha, text="Carregar lista .txt", command=self.carregar_txt).pack(
            side="right", padx=(0, 8))

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
        self.botao_pausar = ttk.Button(linha, text="Pausar", command=self.pausar_ou_continuar)
        self.botao_pausar.pack(side="left", padx=5)
        self.botao_cancelar = ttk.Button(linha, text="Cancelar", command=self.cancelar)
        self.botao_cancelar.pack(side="left", padx=5)
        ttk.Button(linha, text="Abrir pasta", command=self.abrir_pasta).pack(
            side="left", padx=5)
        self.botao_pausar.state(["disabled"])
        self.botao_cancelar.state(["disabled"])

        # Progresso e status
        self.barra = ttk.Progressbar(f, mode="determinate", maximum=100)
        self.barra.pack(fill="x")
        self.status = ttk.Label(f, text="Pronto", style="Fraco.TLabel")
        self.status.pack(anchor="w", pady=(6, 6))

        self.log = tk.Text(f, height=8, bg=CAIXA, fg=APAGADO, relief="flat",
                           font=("Consolas", 9), state="disabled", wrap="word")
        self.log.pack(fill="both", expand=True)

    # ---------- campo de link ----------
    def _texto_links(self) -> str:
        texto = self.entrada.get("1.0", "end").strip()
        return "" if texto == DICA else texto

    def _limpar_dica(self, _e=None) -> None:
        if self.entrada.get("1.0", "end").strip() == DICA:
            self.entrada.delete("1.0", "end")
            self.entrada.config(fg=TEXTO)

    def _mostrar_dica(self, _e=None) -> None:
        if not self._texto_links():
            self.entrada.delete("1.0", "end")
            self.entrada.insert("1.0", DICA)
            self.entrada.config(fg=APAGADO)

    def _contar_links(self) -> list[str]:
        links = baixador.separar_links(self._texto_links())
        n = len(links)
        self.contador.config(text="Nenhum link" if n == 0 else
                             "1 link" if n == 1 else f"{n} links")
        return links

    def limpar_links(self) -> None:
        self.entrada.delete("1.0", "end")
        self.entrada.config(fg=TEXTO)
        self._mostrar_dica()
        self._contar_links()

    def carregar_txt(self) -> None:
        caminho = filedialog.askopenfilename(
            title="Escolha a lista de links",
            filetypes=[("Arquivo de texto", "*.txt"), ("Todos os arquivos", "*.*")])
        if not caminho:
            return
        texto = Path(caminho).read_text(encoding="utf-8", errors="replace")
        self._limpar_dica()
        atual = self._texto_links()
        self.entrada.delete("1.0", "end")
        self.entrada.config(fg=TEXTO)
        self.entrada.insert("1.0", (atual + "\n" + texto).strip() if atual else texto.strip())
        n = len(self._contar_links())
        self.escrever_log(f"Lista carregada: {Path(caminho).name} ({n} links no total)")

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

    def sobre(self) -> None:
        abrir = messagebox.askyesno(
            "Sobre o PendrivePlay",
            f"PendrivePlay {VERSAO}\n"
            "Baixa vídeos e músicas e salva no pendrive, pronto para a TV.\n\n"
            "Software livre, licença MIT. Inclui o FFmpeg (GPLv3) e o yt-dlp.\n"
            "Código: github.com/Yuric9/PendrivePlay\n\n"
            "Baixe apenas conteúdo que você tem direito de baixar e respeite "
            "os termos de uso de cada site.\n\n"
            "Abrir a pasta com as licenças completas?")
        if abrir:
            self._abrir_no_explorador(baixador.pasta_do_programa() / "licencas")

    def _abrir_no_explorador(self, pasta: Path) -> None:
        if not pasta.exists():
            messagebox.showwarning("PendrivePlay", f"Pasta não encontrada:\n{pasta}")
            return
        if sys.platform == "win32":
            os.startfile(pasta)
        else:
            subprocess.Popen(["xdg-open", str(pasta)])

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
        links = self._contar_links()
        if not links:
            messagebox.showwarning("PendrivePlay", "Cole pelo menos um link (começando com http).")
            return
        raiz = self.destinos.get(self.destino.get())
        if raiz is None:
            messagebox.showwarning("PendrivePlay", "Conecte um pendrive ou escolha uma pasta.")
            return

        self.ocupado = True
        self.controle = baixador.Controle()
        self.botao.state(["disabled"])
        self.botao_pausar.state(["!disabled"])
        self.botao_pausar.config(text="Pausar")
        self.botao_cancelar.state(["!disabled"])
        self.barra["value"] = 0
        self.escrever_log(f"--- {len(links)} link(s)")
        formato = self.formato.get()
        threading.Thread(target=self._trabalho,
                         args=(links, formato, raiz, self.controle), daemon=True).start()

    def pausar_ou_continuar(self) -> None:
        if not self.ocupado:
            return
        if self.controle.pausado:
            self.controle.retomar()
            self.botao_pausar.config(text="Pausar")
            self.status.config(text="Continuando...")
            self.escrever_log("Continuando.")
        else:
            self.controle.pausar()
            self.botao_pausar.config(text="Continuar")
            self.status.config(text="Pausado. Clique em Continuar quando quiser.")
            self.escrever_log("Pausado. (Se estiver convertendo, pausa ao terminar o arquivo atual.)")

    def cancelar(self) -> bool:
        """Pergunta e cancela. Retorna True se cancelou."""
        if not self.ocupado:
            return True
        if not messagebox.askyesno(
                "PendrivePlay",
                "Cancelar os downloads?\n\n"
                "Os arquivos que já terminaram continuam no pendrive.\n"
                "Os links que faltaram ficam na caixa para baixar depois."):
            return False
        self.controle.cancelar()
        self.botao_pausar.state(["disabled"])
        self.botao_cancelar.state(["disabled"])
        self.status.config(text="Cancelando...")
        return True

    def fechar_janela(self) -> None:
        if self.ocupado and not self.cancelar():
            return
        self.root.destroy()

    def _trabalho(self, links: list[str], formato: str, raiz: Path,
                  controle: baixador.Controle) -> None:
        """Roda em outra thread: só conversa com a tela pela fila."""
        try:
            resultado = baixador.baixar_varios(
                links, formato, raiz,
                aviso=lambda m: self.fila.put(("aviso", m)),
                progresso=lambda p: self.fila.put(("progresso", p)),
                controle=controle,
            )
            self.fila.put(("fim", resultado))
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
                    self._mostrar_resumo(dado)
                elif tipo == "erro":
                    self._terminar()
                    self.status.config(text="Deu erro. Veja abaixo.")
                    self.escrever_log(f"ERRO: {dado}")
                    messagebox.showerror("PendrivePlay", dado)
        except queue.Empty:
            pass
        self.root.after(100, self._ler_fila)

    def _mostrar_resumo(self, r: baixador.Resultado) -> None:
        salvos, erros, faltam = len(r.salvos), len(r.erros), len(r.pendentes)
        if r.cancelado:
            self.status.config(text=f"Cancelado. {salvos} arquivo(s) salvo(s) antes.")
        else:
            self.barra["value"] = 100
            self.status.config(text=f"Pronto! {salvos} arquivo(s) salvo(s)"
                                    + (f", {erros} link(s) com erro." if erros else "."))
        partes = []
        if r.cancelado:
            partes.append(f"Cancelado. {faltam} link(s) não foram baixados.")
        if salvos:
            pastas = sorted({str(f.parent) for f in r.salvos})
            partes.append(f"{salvos} arquivo(s) salvo(s) em:\n" + "\n".join(pastas))
        if erros:
            lista = "\n".join(f"• {link}" for link in list(r.erros)[:5])
            if erros > 5:
                lista += f"\n• ... e mais {erros - 5}"
            partes.append(f"{erros} link(s) com erro (detalhes no quadro abaixo):\n{lista}")
            for link, erro in r.erros.items():
                self.escrever_log(f"ERRO em {link}: {erro}")
        sobraram = list(r.erros) + r.pendentes
        if sobraram:
            # deixa na caixa só os links que não terminaram, para tentar de novo
            self.entrada.delete("1.0", "end")
            self.entrada.config(fg=TEXTO)
            self.entrada.insert("1.0", "\n".join(sobraram))
            self._contar_links()
            partes.append("Os links que não terminaram ficaram na caixa.")
        if salvos:
            partes.append("Antes de tirar o pendrive, use \"Ejetar\" no Windows.")

        mensagem = "\n\n".join(partes)
        if r.cancelado:
            messagebox.showinfo("PendrivePlay", mensagem)
        elif erros and not salvos:
            messagebox.showerror("PendrivePlay", mensagem)
        elif erros:
            messagebox.showwarning("PendrivePlay", mensagem)
        else:
            messagebox.showinfo("PendrivePlay", mensagem)

    def _terminar(self) -> None:
        self.ocupado = False
        self.botao.state(["!disabled"])
        self.botao_pausar.state(["disabled"])
        self.botao_pausar.config(text="Pausar")
        self.botao_cancelar.state(["disabled"])
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
