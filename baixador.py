"""Núcleo do PendrivePlay: baixa, converte e salva direto no pendrive.

Uso pelo terminal (opcional):
    python baixador.py mp4 E:\\ "LINK1" "LINK2" ...
    python baixador.py mp3 E:\\ "LINK1" "LINK2" ...
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
import threading
import unicodedata
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

PASTA_VIDEOS = "VIDEOS_TV"
PASTA_MP3 = "MP3"
FORMATOS = ("mp4", "mp3")

Aviso = Callable[[str], None]
Progresso = Callable[[float], None]  # recebe um número de 0 a 100

# No Windows, impede que o ffmpeg abra uma janela preta de console.
SEM_JANELA = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


def pasta_do_programa() -> Path:
    """Pasta onde o programa está (funciona no .py e no .exe)."""
    if getattr(sys, "frozen", False):  # rodando como .exe (PyInstaller)
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent


def achar_ffmpeg() -> str:
    """Encontra o ffmpeg: ao lado do programa, no PATH ou via imageio-ffmpeg."""
    nome = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
    local = pasta_do_programa() / nome
    if local.exists():
        return str(local)
    no_path = shutil.which("ffmpeg")
    if no_path:
        return no_path
    try:
        from imageio_ffmpeg import get_ffmpeg_exe
    except ImportError:
        raise RuntimeError("ffmpeg não encontrado. Rode: pip install -r requirements.txt")
    # Copia com o nome "ffmpeg" para o yt-dlp reconhecer o arquivo.
    shutil.copy(get_ffmpeg_exe(), local)
    local.chmod(0o755)
    return str(local)


def preparar_destino(raiz: Path, formato: str) -> Path:
    """Cria (se não existir) a pasta VIDEOS_TV ou MP3 no pendrive."""
    pasta = Path(raiz) / (PASTA_VIDEOS if formato == "mp4" else PASTA_MP3)
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


LIMITE_NOME = 60  # muitas TVs não leem nomes longos


def nome_seguro(titulo: str, limite: int = LIMITE_NOME) -> str:
    """Transforma o título num nome de arquivo que qualquer TV consegue ler.

    - troca letras "especiais" pela versão comum (｜ -> |, ： -> :)
    - tira acentos (Canção -> Cancao) e símbolos/emojis
    - troca separadores (| : / etc.) por " - "
    - corta em até `limite` caracteres, sem quebrar palavra no meio
    """
    texto = unicodedata.normalize("NFKC", titulo)          # ｜ -> |   ： -> :
    texto = texto.replace("\u29f8", "/").replace("\u29f9", "\\")  # ⧸ ⧹ do yt-dlp
    texto = unicodedata.normalize("NFKD", texto)           # ã -> a + ~
    texto = texto.encode("ascii", "ignore").decode("ascii")  # remove ~ e emojis
    texto = re.sub(r"(\w)[/\\](\w)", r"\1-\2", texto)       # AC/DC -> AC-DC
    texto = re.sub(r"\s*[|:/\\]+\s*", " - ", texto)        # separadores
    texto = re.sub(r"[^A-Za-z0-9 ()\[\]&,.'!+_-]", "", texto)  # só caracteres seguros
    texto = re.sub(r"\s+", " ", texto)
    texto = re.sub(r"(\s*-\s*){2,}", " - ", texto)         # "- -" vira um só
    sobra = " .-_,(&+"  # o que não pode ficar solto no começo ou no fim
    texto = texto.strip(sobra)
    if len(texto) > limite:
        corte = texto[:limite]
        if " " in corte[limite // 2:]:
            corte = corte[:corte.rfind(" ")]
        texto = corte.strip(sobra)
    return texto or "video"


def nome_livre(pasta: Path, nome: str, ext: str) -> Path:
    """Evita sobrescrever: 'musica.mp3' -> 'musica (2).mp3'."""
    caminho = pasta / f"{nome}.{ext}"
    n = 2
    while caminho.exists():
        caminho = pasta / f"{nome} ({n}).{ext}"
        n += 1
    return caminho


class Cancelado(Exception):
    """O usuário clicou em Cancelar."""


class Controle:
    """Botões Pausar/Continuar/Cancelar, compartilhados entre a tela e o download.

    A tela chama pausar(), retomar() e cancelar(). O download chama checar()
    em pontos seguros: ali ele espera se estiver pausado, ou para se foi cancelado.
    """

    def __init__(self) -> None:
        self._cancelar = threading.Event()
        self._liberado = threading.Event()
        self._liberado.set()

    def pausar(self) -> None:
        self._liberado.clear()

    def retomar(self) -> None:
        self._liberado.set()

    def cancelar(self) -> None:
        self._cancelar.set()
        self._liberado.set()  # se estava pausado, solta para poder parar

    @property
    def pausado(self) -> bool:
        return not self._liberado.is_set()

    @property
    def cancelado(self) -> bool:
        return self._cancelar.is_set()

    def checar(self) -> None:
        self._liberado.wait()
        if self.cancelado:
            raise Cancelado()


def _rodar_ffmpeg(cmd: list[str], controle: Controle | None = None) -> None:
    """Roda o ffmpeg. Se o usuário cancelar, encerra o ffmpeg na hora."""
    proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                            stderr=subprocess.PIPE, text=True, errors="replace",
                            creationflags=SEM_JANELA)
    while True:
        try:
            _, erros = proc.communicate(timeout=0.3)
            break
        except subprocess.TimeoutExpired:
            if controle and controle.cancelado:
                proc.kill()
                proc.communicate()
                raise Cancelado()
    if proc.returncode != 0:
        ultimas = "\n".join(erros.strip().splitlines()[-5:])
        raise RuntimeError(f"Erro na conversão:\n{ultimas}")


def converter_para_tv(ffmpeg: str, origem: Path, saida: Path,
                      controle: Controle | None = None) -> None:
    """MP4 720p H.264 baseline: toca em TVs antigas, Smart TVs e TV Box."""
    _rodar_ffmpeg([
        ffmpeg, "-y", "-i", str(origem),
        "-c:v", "libx264", "-preset", "veryfast",
        "-profile:v", "baseline", "-level", "3.1",  # 3.1 é o nível certo para 720p
        "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,"
               "pad=1280:720:(ow-iw)/2:(oh-ih)/2,setsar=1",
        "-b:v", "1500k", "-maxrate", "2000k", "-bufsize", "3000k",
        "-pix_fmt", "yuv420p",
        "-fpsmax", "30", "-fps_mode", "cfr",  # 720p no nível 3.1 vai até 30 quadros/s
        "-c:a", "aac", "-b:a", "192k", "-ac", "2",
        "-movflags", "+faststart",
        str(saida),
    ], controle)


def converter_para_mp3(ffmpeg: str, origem: Path, saida: Path,
                       controle: Controle | None = None) -> None:
    _rodar_ffmpeg([
        ffmpeg, "-y", "-i", str(origem), "-vn",
        "-c:a", "libmp3lame", "-b:a", "192k", "-ar", "44100",
        str(saida),
    ], controle)


def salvar_no_pendrive(ffmpeg: str, origem: Path, destino: Path, formato: str,
                       tmp: Path, controle: Controle | None = None) -> Path:
    """Converte no PC e copia o arquivo pronto para o pendrive.

    A cópia usa um nome provisório e só recebe o nome final no fim. Assim,
    se o pendrive for removido no meio, não fica um vídeo "quebrado" com
    nome de vídeo bom.
    """
    convertido = tmp / f"convertido.{formato}"
    if formato == "mp4":
        converter_para_tv(ffmpeg, origem, convertido, controle)
    else:
        converter_para_mp3(ffmpeg, origem, convertido, controle)
    if controle:
        controle.checar()  # cancelou no fim da conversão: não copia

    final = nome_livre(destino, nome_seguro(origem.stem), formato)
    provisorio = final.with_name(final.name + ".parcial")
    shutil.copyfile(convertido, provisorio)
    provisorio.rename(final)
    convertido.unlink()
    return final


class _Registro:
    """Recebe as mensagens do yt-dlp (no .exe não existe console)."""

    def __init__(self, aviso: Aviso):
        self.aviso = aviso
        self.erros: list[str] = []

    def debug(self, msg: str) -> None:
        pass

    def info(self, msg: str) -> None:
        pass

    def warning(self, msg: str) -> None:
        pass

    def error(self, msg: str) -> None:
        msg = msg.replace("ERROR: ", "")
        self.erros.append(msg)
        self.aviso(f"Erro: {msg}")


def baixar(url: str, formato: str, raiz_destino: str | Path,
           aviso: Aviso = print, progresso: Progresso = lambda p: None,
           controle: Controle | None = None) -> list[Path]:
    """Baixa o link (vídeo ou playlist) e salva no pendrive.

    Retorna a lista de arquivos salvos. Levanta Cancelado se o usuário cancelar.
    """
    controle = controle or Controle()
    if formato not in FORMATOS:
        raise ValueError(f"Formato inválido: {formato}")
    raiz = Path(raiz_destino)
    if not raiz.exists():
        raise RuntimeError(f"Destino não encontrado: {raiz}\nO pendrive está conectado?")

    destino = preparar_destino(raiz, formato)
    ffmpeg = achar_ffmpeg()
    from yt_dlp import YoutubeDL
    from yt_dlp.utils import DownloadCancelled

    titulo_atual = {"nome": None}
    partes = {"prontas": 0}  # vídeo e áudio vêm em arquivos separados

    def gancho(d: dict) -> None:
        # Chamado pelo yt-dlp várias vezes por segundo durante o download.
        # Aqui ele espera se estiver pausado e para se foi cancelado.
        try:
            controle.checar()
        except Cancelado:
            raise DownloadCancelled("cancelado pelo usuário")
        info = d.get("info_dict", {})
        n_partes = len(info.get("requested_formats") or []) or 1
        if d["status"] == "finished":
            partes["prontas"] = min(partes["prontas"] + 1, n_partes)
        if d["status"] == "downloading":
            nome = info.get("title")
            if nome and nome != titulo_atual["nome"]:
                titulo_atual["nome"] = nome
                partes["prontas"] = 0
                aviso(f"Baixando: {nome}")
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            if total:
                fracao = min(d.get("downloaded_bytes", 0) / total, 1)
                # o download vai até 90%; os 10% finais são da conversão
                progresso(min((partes["prontas"] + fracao) / n_partes, 1) * 90)

    registro = _Registro(aviso)
    with tempfile.TemporaryDirectory(prefix="pendriveplay_") as pasta_tmp:
        tmp = Path(pasta_tmp)
        baixados = tmp / "baixados"
        opcoes = {
            "outtmpl": str(baixados / "%(title).80B.%(ext)s"),
            "windowsfilenames": True,      # nomes válidos no Windows/pendrive
            "ffmpeg_location": ffmpeg,
            "noplaylist": False,           # playlist baixa todos os vídeos
            "ignoreerrors": True,          # um vídeo com erro não para a playlist
            "progress_hooks": [gancho],
            "logger": registro,
            "noprogress": True,
        }
        if formato == "mp4":
            opcoes["format"] = ("bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]"
                                "/best[height<=720]/best")
            opcoes["merge_output_format"] = "mp4"
        else:
            opcoes["format"] = "bestaudio/best"

        try:
            with YoutubeDL(opcoes) as ydl:
                ydl.download([url])
        except (DownloadCancelled, Cancelado):
            raise Cancelado()
        controle.checar()

        arquivos = sorted(
            a for a in baixados.glob("*")
            if a.is_file() and a.suffix not in (".part", ".ytdl", ".json")
        ) if baixados.exists() else []
        if not arquivos:
            motivo = registro.erros[-1] if registro.erros else "confira o link e a internet"
            raise RuntimeError(f"Nada foi baixado ({motivo}).")

        salvos = []
        for i, arq in enumerate(arquivos, 1):
            etapa = "Convertendo para TV" if formato == "mp4" else "Convertendo para MP3"
            controle.checar()
            aviso(f"{etapa} ({i}/{len(arquivos)}): {arq.stem}")
            salvos.append(salvar_no_pendrive(ffmpeg, arq, destino, formato, tmp, controle))
            aviso(f"Salvo: {salvos[-1]}")
            progresso(90 + 10 * i / len(arquivos))
    return salvos


def separar_links(texto: str) -> list[str]:
    """Acha todos os links num texto (um por linha, ou misturados com texto).

    Ignora linhas que começam com # e remove links repetidos.
    """
    links: list[str] = []
    for linha in texto.splitlines():
        if linha.strip().startswith("#"):
            continue
        for link in re.findall(r"https?://[^\s<>\"']+", linha):
            link = link.rstrip(".,;)")
            if link not in links:
                links.append(link)
    return links


# ---------- links e playlists ----------

def tipo_link(url: str) -> str:
    """Classifica o link sem usar a internet.

    "video_na_playlist": vídeo aberto dentro de uma playlist (tem v= e list=)
    "playlist":          página da playlist (youtube.com/playlist?list=...)
    "simples":           qualquer outro link
    """
    partes = urlparse(url)
    consulta = parse_qs(partes.query)
    if "list" not in consulta:
        return "simples"
    if partes.path.rstrip("/").endswith("/playlist"):
        return "playlist"
    if "v" in consulta or partes.netloc.endswith("youtu.be"):
        return "video_na_playlist"
    return "playlist"


def so_o_video(url: str) -> str:
    """Tira a playlist do link, deixando só o vídeo.

    https://www.youtube.com/watch?v=ABC&list=PL1&index=2 -> https://www.youtube.com/watch?v=ABC
    """
    partes = urlparse(url)
    consulta = parse_qs(partes.query)
    for chave in ("list", "index", "start_radio", "pp"):
        consulta.pop(chave, None)
    return urlunparse(partes._replace(query=urlencode(consulta, doseq=True)))


def _itens_da_playlist(info: dict) -> list[tuple[str, str]]:
    """Extrai (link, título) de cada vídeo da resposta do yt-dlp."""
    itens: list[tuple[str, str]] = []
    for entrada in info.get("entries") or []:
        if not entrada:  # vídeo indisponível/removido
            continue
        link = entrada.get("url") or entrada.get("webpage_url")
        if link and not link.startswith("http"):
            link = None
        if not link and entrada.get("id") and entrada.get("ie_key", "Youtube") == "Youtube":
            link = f"https://www.youtube.com/watch?v={entrada['id']}"
        if link and all(link != l for l, _ in itens):
            itens.append((link, entrada.get("title") or link))
    return itens


def listar_playlist(url: str, aviso: Aviso = print) -> list[tuple[str, str]]:
    """Busca a lista de vídeos de uma playlist (só os links, sem baixar nada)."""
    from yt_dlp import YoutubeDL

    registro = _Registro(aviso)
    opcoes = {"extract_flat": "in_playlist", "noplaylist": False, "logger": registro,
              "ignoreerrors": True, "noprogress": True}
    with YoutubeDL(opcoes) as ydl:
        info = ydl.extract_info(url, download=False) or {}
    if info.get("_type") not in ("playlist", "multi_video"):
        return [(url, info.get("title") or url)]   # no fim era um vídeo só
    itens = _itens_da_playlist(info)
    if not itens:
        motivo = registro.erros[-1] if registro.erros else "playlist vazia ou privada"
        raise RuntimeError(f"Não consegui ler a playlist ({motivo}).")
    return itens


def montar_fila(links: list[str], aviso: Aviso = print,
                controle: Controle | None = None) -> tuple[list[tuple[str, str]], dict[str, str]]:
    """Transforma a lista de links numa fila de vídeos.

    Cada playlist vira um item por vídeo, para que cada um seja salvo no pendrive
    assim que terminar. Retorna (fila, erros).
    """
    fila: list[tuple[str, str]] = []
    erros: dict[str, str] = {}
    for link in links:
        if controle:
            controle.checar()
        if tipo_link(link) == "simples":
            itens = [(link, link)]
        else:
            aviso(f"Lendo a playlist: {link}")
            try:
                itens = listar_playlist(link, aviso)
            except Exception as erro:
                erros[link] = str(erro)
                aviso(f"Erro na playlist, indo para o próximo: {erro}")
                continue
            if len(itens) > 1:
                aviso(f"Playlist com {len(itens)} vídeos.")
        for item in itens:
            if all(item[0] != l for l, _ in fila):
                fila.append(item)
    return fila, erros


@dataclass
class Resultado:
    salvos: list[Path] = field(default_factory=list)
    erros: dict[str, str] = field(default_factory=dict)  # link -> mensagem
    cancelado: bool = False
    pendentes: list[str] = field(default_factory=list)   # links que não terminaram


def baixar_varios(links: list[str], formato: str, raiz_destino: str | Path,
                  aviso: Aviso = print, progresso: Progresso = lambda p: None,
                  controle: Controle | None = None) -> Resultado:
    """Baixa vários links, um vídeo de cada vez.

    Playlists viram um item por vídeo: cada um é salvo no pendrive assim que termina.
    Se um vídeo der erro, anota e continua com os próximos.
    Se o usuário cancelar, para e guarda em "pendentes" os links que faltaram.
    A barra de progresso vai de 0 a 100 considerando todos os vídeos.
    """
    controle = controle or Controle()
    resultado = Resultado()
    try:
        fila, resultado.erros = montar_fila(links, aviso, controle)
    except Cancelado:
        resultado.cancelado = True
        resultado.pendentes = list(links)
        return resultado
    links = [link for link, _ in fila]
    total = len(fila)
    for i, (link, titulo) in enumerate(fila):
        aviso(f"[{i + 1}/{total}] {titulo}")

        def progresso_geral(p: float, i=i) -> None:
            progresso((i + p / 100) / total * 100)

        try:
            controle.checar()
            resultado.salvos += baixar(link, formato, raiz_destino, aviso,
                                       progresso_geral, controle)
        except Cancelado:
            resultado.cancelado = True
            resultado.pendentes = links[i:]
            aviso("Cancelado. Os arquivos já salvos continuam no pendrive.")
            return resultado
        except Exception as erro:
            resultado.erros[link] = str(erro)
            aviso(f"Erro neste link, indo para o próximo: {erro}")
        progresso((i + 1) / total * 100)
    return resultado


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)
    fmt, pasta, lista = sys.argv[1].lower(), sys.argv[2], separar_links("\n".join(sys.argv[3:]))
    r = baixar_varios(lista, fmt, pasta)
    for f in r.salvos:
        print("OK:", f)
    for link, erro in r.erros.items():
        print("ERRO:", link, "-", erro)
    sys.exit(1 if r.erros else 0)
