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


def nome_livre(pasta: Path, nome: str, ext: str) -> Path:
    """Evita sobrescrever: 'musica.mp3' -> 'musica (2).mp3'."""
    caminho = pasta / f"{nome}.{ext}"
    n = 2
    while caminho.exists():
        caminho = pasta / f"{nome} ({n}).{ext}"
        n += 1
    return caminho


def _rodar_ffmpeg(cmd: list[str]) -> None:
    r = subprocess.run(cmd, capture_output=True, text=True, errors="replace",
                       creationflags=SEM_JANELA)
    if r.returncode != 0:
        ultimas = "\n".join(r.stderr.strip().splitlines()[-5:])
        raise RuntimeError(f"Erro na conversão:\n{ultimas}")


def converter_para_tv(ffmpeg: str, origem: Path, saida: Path) -> None:
    """MP4 720p H.264 baseline: toca em TVs antigas, Smart TVs e TV Box."""
    _rodar_ffmpeg([
        ffmpeg, "-y", "-i", str(origem),
        "-c:v", "libx264", "-preset", "veryfast",
        "-profile:v", "baseline", "-level", "3.1",  # 3.1 é o nível certo para 720p
        "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,"
               "pad=1280:720:(ow-iw)/2:(oh-ih)/2,setsar=1",
        "-b:v", "1500k", "-maxrate", "2000k", "-bufsize", "3000k",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-ac", "2",
        "-movflags", "+faststart",
        str(saida),
    ])


def converter_para_mp3(ffmpeg: str, origem: Path, saida: Path) -> None:
    _rodar_ffmpeg([
        ffmpeg, "-y", "-i", str(origem), "-vn",
        "-c:a", "libmp3lame", "-b:a", "192k", "-ar", "44100",
        str(saida),
    ])


def salvar_no_pendrive(ffmpeg: str, origem: Path, destino: Path, formato: str,
                       tmp: Path) -> Path:
    """Converte no PC e copia o arquivo pronto para o pendrive.

    A cópia usa um nome provisório e só recebe o nome final no fim. Assim,
    se o pendrive for removido no meio, não fica um vídeo "quebrado" com
    nome de vídeo bom.
    """
    convertido = tmp / f"convertido.{formato}"
    if formato == "mp4":
        converter_para_tv(ffmpeg, origem, convertido)
    else:
        converter_para_mp3(ffmpeg, origem, convertido)

    final = nome_livre(destino, origem.stem, formato)
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
           aviso: Aviso = print, progresso: Progresso = lambda p: None) -> list[Path]:
    """Baixa o link (vídeo ou playlist) e salva no pendrive.

    Retorna a lista de arquivos salvos.
    """
    if formato not in FORMATOS:
        raise ValueError(f"Formato inválido: {formato}")
    raiz = Path(raiz_destino)
    if not raiz.exists():
        raise RuntimeError(f"Destino não encontrado: {raiz}\nO pendrive está conectado?")

    destino = preparar_destino(raiz, formato)
    ffmpeg = achar_ffmpeg()
    from yt_dlp import YoutubeDL

    titulo_atual = {"nome": None}

    def gancho(d: dict) -> None:
        if d["status"] == "downloading":
            nome = d.get("info_dict", {}).get("title")
            if nome and nome != titulo_atual["nome"]:
                titulo_atual["nome"] = nome
                aviso(f"Baixando: {nome}")
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            if total:
                progresso(min(d.get("downloaded_bytes", 0) / total * 100, 100))

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

        with YoutubeDL(opcoes) as ydl:
            ydl.download([url])

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
            aviso(f"{etapa} ({i}/{len(arquivos)}): {arq.stem}")
            salvos.append(salvar_no_pendrive(ffmpeg, arq, destino, formato, tmp))
            aviso(f"Salvo: {salvos[-1]}")
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


@dataclass
class Resultado:
    salvos: list[Path] = field(default_factory=list)
    erros: dict[str, str] = field(default_factory=dict)  # link -> mensagem


def baixar_varios(links: list[str], formato: str, raiz_destino: str | Path,
                  aviso: Aviso = print, progresso: Progresso = lambda p: None) -> Resultado:
    """Baixa vários links, um de cada vez.

    Se um link der erro, anota e continua com os próximos.
    A barra de progresso vai de 0 a 100 considerando todos os links.
    """
    resultado = Resultado()
    total = len(links)
    for i, link in enumerate(links):
        aviso(f"[{i + 1}/{total}] {link}")

        def progresso_geral(p: float, i=i) -> None:
            progresso((i + p / 100) / total * 100)

        try:
            resultado.salvos += baixar(link, formato, raiz_destino, aviso, progresso_geral)
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
