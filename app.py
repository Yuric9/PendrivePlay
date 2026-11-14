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

VERSAO = "1.1.0"
DICA = "Cole os links aqui, um por linha..."

FUNDO = "#0f1115"
CAIXA = "#1a1d24"
TEXTO = "#e5e7eb"
APAGADO = "#9ca3af"
VERDE = "#22c55e"
ESCOLHER_PASTA = "Escolher outra pasta..."


COMO_USAR = """COMO USAR
1. Conecte o pendrive. Ele aparece sozinho em "Salvar em".
2. Cole os links, um por linha, ou use "Carregar lista .txt".
3. Escolha "Vídeo MP4 para TV" ou "Música MP3" e clique em Baixar.
4. Quando terminar, ejete o pendrive no Windows antes de tirar.

PLAYLISTS
- Vídeo aberto dentro de uma playlist (o link tem "list=" no final):
  o programa pergunta se você quer só o vídeo ou a playlist inteira.
- Link da própria playlist (youtube.com/playlist?list=...):
  baixa todos os vídeos dela.
- Cada vídeo vai para o pendrive assim que termina.

NO PENDRIVE
- Vídeos ficam na pasta VIDEOS_TV, e músicas na pasta MP3.
- Os nomes ficam curtos, sem acentos e sem símbolos,
  para a TV conseguir abrir.

DICAS
- Pausar para na hora; Continuar segue de onde parou.
- Cancelar mantém o que já terminou. Os links que faltaram
  voltam para a caixa.
- Se um link der erro, o motivo aparece no quadro de mensagens.
- Atalho: Ctrl+Enter na caixa de links começa a baixar.
- Passe o mouse em cima de um botão para ver o que ele faz."""


class Dica:
    """Mostra um texto de ajuda quando o mouse para em cima de um elemento."""

    def __init__(self, widget: tk.Widget, texto: str, espera_ms: int = 500):
        self.widget, self.texto, self.espera_ms = widget, texto, espera_ms
        self._agendado = None
        self._janela: tk.Toplevel | None = None
        widget.bind("<Enter>", self._agendar, add="+")
        widget.bind("<Leave>", self._esconder, add="+")
        widget.bind("<ButtonPress>", self._esconder, add="+")

    def _agendar(self, _e=None) -> None:
        self._cancelar_agenda()
        self._agendado = self.widget.after(self.espera_ms, self.mostrar)

    def _cancelar_agenda(self) -> None:
        if self._agendado:
            self.widget.after_cancel(self._agendado)
            self._agendado = None

    def mostrar(self) -> None:
        if self._janela:
            return
        x = self.widget.winfo_rootx() + 12
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        self._janela = tk.Toplevel(self.widget)
        self._janela.wm_overrideredirect(True)
        self._janela.wm_geometry(f"+{x}+{y}")
        tk.Label(self._janela, text=self.texto, justify="left", bg="#111827", fg=TEXTO,
                 relief="solid", bd=1, font=("Segoe UI", 9), padx=8, pady=5,
                 wraplength=340).pack()

    def _esconder(self, _e=None) -> None:
        self._cancelar_agenda()
        if self._janela:
            self._janela.destroy()
            self._janela = None


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
        topo = ttk.Frame(f)
        topo.place(relx=1.0, y=0, anchor="ne")
        ttk.Button(topo, text="Como usar", command=self.como_usar).pack(side="left", padx=(0, 6))
        ttk.Button(topo, text="Sobre", command=self.sobre).pack(side="left")
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
        botao_limpar = ttk.Button(linha, text="Limpar", command=self.limpar_links)
        botao_limpar.pack(side="right")
        botao_txt = ttk.Button(linha, text="Carregar lista .txt", command=self.carregar_txt)
        botao_txt.pack(side="right", padx=(0, 8))
        Dica(self.entrada, "Cole um link por linha. Links repetidos são ignorados.\n"
                           "Se o link for de um vídeo dentro de uma playlist (tem \"list=\"), "
                           "o programa pergunta se você quer só o vídeo ou a playlist inteira.")
        Dica(botao_txt, "Traz os links de um arquivo de texto (um link por linha).")
        Dica(botao_limpar, "Apaga todos os links da caixa.")

        # Formato
        self.formato = tk.StringVar(value="mp4")
        linha = ttk.Frame(f)
        linha.pack(fill="x", pady=12)
        opcao_mp4 = ttk.Radiobutton(linha, text="Vídeo MP4 para TV", variable=self.formato,
                                    value="mp4")
        opcao_mp4.pack(side="left", padx=(0, 20))
        opcao_mp3 = ttk.Radiobutton(linha, text="Música MP3", variable=self.formato, value="mp3")
        opcao_mp3.pack(side="left")
        Dica(opcao_mp4, "Vídeo em HD (720p) no formato que TVs antigas, Smart TVs e TV Box "
                        "conseguem tocar. Vai para a pasta VIDEOS_TV.")
        Dica(opcao_mp3, "Só o áudio, em MP3 192 kbps. Bom para música no carro ou no som. "
                        "Vai para a pasta MP3.")

        # Destino (pendrive)
        ttk.Label(f, text="Salvar em:").pack(anchor="w")
        linha = ttk.Frame(f)
        linha.pack(fill="x", pady=(4, 0))
        self.destino = ttk.Combobox(linha, state="readonly", font=("Segoe UI", 10))
        self.destino.pack(side="left", fill="x", expand=True, ipady=4)
        self.destino.bind("<<ComboboxSelected>>", self._destino_escolhido)
        botao_atualizar = ttk.Button(linha, text="Atualizar", command=self.atualizar_destinos)
        botao_atualizar.pack(side="left", padx=(8, 0))
        Dica(self.destino, "O pendrive aparece aqui sozinho quando é conectado. "
                           "Para salvar em outro lugar, escolha \"Escolher outra pasta...\".")
        Dica(botao_atualizar, "Procura de novo os pendrives conectados.")
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
        botao_abrir = ttk.Button(linha, text="Abrir pasta", command=self.abrir_pasta)
        botao_abrir.pack(side="left", padx=5)
        Dica(self.botao, "Começa a baixar todos os links da caixa, um de cada vez. "
                         "Cada arquivo vai para o pendrive assim que fica pronto. (Ctrl+Enter)")
        Dica(self.botao_pausar, "Para o download na hora. Clique em Continuar para seguir de "
                                "onde parou. Durante a conversão, pausa ao terminar o arquivo atual.")
        Dica(self.botao_cancelar, "Para tudo. O que já terminou fica no pendrive, e os links "
                                  "que faltaram voltam para a caixa.")
        Dica(botao_abrir, "Abre no Windows a pasta do pendrive onde os arquivos estão sendo salvos.")
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
        texto = "Nenhum link" if n == 0 else "1 link" if n == 1 else f"{n} links"
        com_playlist = sum(baixador.tipo_link(l) != "simples" for l in links)
        if com_playlist:
            texto += f"  ({com_playlist} com playlist)"
        self.contador.config(text=texto)
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

    def _escolher_playlist(self, quantos: int) -> str | None:
        """Pergunta o que fazer com links de vídeo dentro de playlist.

        Retorna "video", "playlist" ou None (cancelou).
        """
        janela = tk.Toplevel(self.root)
        janela.title("Vídeo dentro de uma playlist")
        janela.configure(bg=FUNDO)
        janela.transient(self.root)
        janela.resizable(False, False)
        escolha: dict[str, str | None] = {"valor": None}

        if quantos == 1:
            texto = ("Este link é de um vídeo aberto dentro de uma playlist.\n\n"
                     "O que você quer baixar?")
            so_video, inteira = "Só este vídeo", "A playlist inteira"
        else:
            texto = (f"{quantos} links são de vídeos abertos dentro de playlists.\n\n"
                     "O que você quer baixar?")
            so_video, inteira = "Só os vídeos", "As playlists inteiras"

        ttk.Label(janela, text=texto, wraplength=420, justify="left").pack(
            padx=22, pady=(20, 14), anchor="w")
        linha = ttk.Frame(janela)
        linha.pack(padx=22, pady=(0, 20))

        def escolher(valor: str | None) -> None:
            escolha["valor"] = valor
            janela.destroy()

        botao_video = ttk.Button(linha, text=so_video, command=lambda: escolher("video"))
        botao_video.pack(side="left", padx=(0, 8))
        ttk.Button(linha, text=inteira, command=lambda: escolher("playlist")).pack(
            side="left", padx=(0, 8))
        ttk.Button(linha, text="Cancelar", command=lambda: escolher(None)).pack(side="left")
        janela.protocol("WM_DELETE_WINDOW", lambda: escolher(None))
        janela.bind("<Escape>", lambda e: escolher(None))
        janela.bind("<Return>", lambda e: escolher("video"))

        janela.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - janela.winfo_width()) // 2
        y = self.root.winfo_rooty() + 120
        janela.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        janela.grab_set()
        botao_video.focus_set()
        self.root.wait_window(janela)
        return escolha["valor"]

    def como_usar(self) -> None:
        janela = tk.Toplevel(self.root)
        janela.title("Como usar o PendrivePlay")
        janela.configure(bg=FUNDO)
        janela.transient(self.root)
        texto = tk.Text(janela, width=64, height=25, bg=CAIXA, fg=TEXTO, relief="flat",
                        font=("Segoe UI", 10), padx=14, pady=12, wrap="word")
        texto.insert("1.0", COMO_USAR)
        texto.config(state="disabled")
        texto.pack(fill="both", expand=True, padx=12, pady=(12, 6))
        ttk.Button(janela, text="Fechar", command=janela.destroy).pack(pady=(0, 12))
        janela.bind("<Escape>", lambda e: janela.destroy())

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

        na_playlist = [l for l in links if baixador.tipo_link(l) == "video_na_playlist"]
        if na_playlist:
            escolha = self._escolher_playlist(len(na_playlist))
            if escolha is None:
                return
            if escolha == "video":
                links = list(dict.fromkeys(
                    baixador.so_o_video(l) if l in na_playlist else l for l in links))
                self.escrever_log("Baixando só o vídeo de cada link (sem a playlist).")
            else:
                self.escrever_log("Baixando as playlists inteiras.")

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
