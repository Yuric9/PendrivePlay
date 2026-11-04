"""Autoteste do PendrivePlay: confere se tudo que o programa precisa funciona.

Uso:
    PendrivePlay.exe --autoteste resultado.txt
    python app.py --autoteste resultado.txt

Grava o resultado no arquivo e termina com código 0 (tudo certo) ou 1 (falhou).
Não usa a internet: gera um vídeo de teste com o próprio ffmpeg.
"""
from __future__ import annotations

import re
import subprocess
import tempfile
import traceback
from pathlib import Path

import baixador
from pendrive import listar_pendrives


def _gerar_video_teste(ffmpeg: str, destino: Path) -> None:
    """Cria um vídeo de 2 s em pé (480x854), com som, só com o ffmpeg."""
    baixador._rodar_ffmpeg([
        ffmpeg, "-y",
        "-f", "lavfi", "-i", "testsrc=size=480x854:rate=30:duration=2",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
        "-c:v", "mpeg4", "-c:a", "aac", "-shortest", str(destino),
    ])


def descrever_midia(ffmpeg: str, arquivo: Path) -> str:
    """Retorna as linhas 'Stream' do ffmpeg (codec, perfil, tamanho)."""
    r = subprocess.run([ffmpeg, "-hide_banner", "-i", str(arquivo)],
                       capture_output=True, text=True, errors="replace",
                       creationflags=baixador.SEM_JANELA)
    return "\n".join(l.strip() for l in r.stderr.splitlines() if "Stream #" in l)


def rodar(arquivo_saida: Path | None = None) -> int:
    linhas: list[str] = []
    falhas = 0

    def passo(nome: str, funcao) -> object:
        nonlocal falhas
        try:
            resultado = funcao()
            linhas.append(f"OK     {nome}: {resultado}")
            return resultado
        except Exception as erro:
            falhas += 1
            linhas.append(f"FALHA  {nome}: {erro}")
            linhas.append(traceback.format_exc())
            return None

    ffmpeg = passo("ffmpeg encontrado", baixador.achar_ffmpeg)

    def versao_ytdlp() -> str:
        from yt_dlp.version import __version__
        return __version__

    passo("yt-dlp carregado", versao_ytdlp)
    passo("detecção de pendrive", lambda: f"{len(listar_pendrives())} pendrive(s) conectado(s)")

    if ffmpeg:
        with tempfile.TemporaryDirectory(prefix="pendriveplay_teste_") as pasta:
            tmp = Path(pasta)
            pendrive_falso = tmp / "PENDRIVE"
            pendrive_falso.mkdir()
            original = tmp / "video teste.mp4"
            passo("gerar vídeo de teste", lambda: _gerar_video_teste(ffmpeg, original) or "ok")

            def teste_mp4() -> str:
                destino = baixador.preparar_destino(pendrive_falso, "mp4")
                final = baixador.salvar_no_pendrive(ffmpeg, original, destino, "mp4", tmp)
                info = descrever_midia(ffmpeg, final)
                if not re.search(r"h264 \(Constrained Baseline\)", info):
                    raise RuntimeError(f"vídeo não está em H.264 baseline:\n{info}")
                if "1280x720" not in info or "aac" not in info:
                    raise RuntimeError(f"vídeo fora do padrão de TV:\n{info}")
                return f"{final.relative_to(pendrive_falso)} em H.264 baseline 1280x720 + AAC"

            def teste_mp3() -> str:
                destino = baixador.preparar_destino(pendrive_falso, "mp3")
                final = baixador.salvar_no_pendrive(ffmpeg, original, destino, "mp3", tmp)
                info = descrever_midia(ffmpeg, final)
                if "Audio: mp3" not in info:
                    raise RuntimeError(f"áudio não está em MP3:\n{info}")
                return f"{final.relative_to(pendrive_falso)} em MP3"

            if original.exists():
                passo("conversão MP4 para TV", teste_mp4)
                passo("conversão MP3", teste_mp3)

    linhas.append("")
    linhas.append("RESULTADO: TUDO CERTO" if falhas == 0 else f"RESULTADO: {falhas} FALHA(S)")
    texto = "\n".join(linhas)
    if arquivo_saida:
        Path(arquivo_saida).write_text(texto, encoding="utf-8")
    else:
        print(texto)
    return 0 if falhas == 0 else 1
