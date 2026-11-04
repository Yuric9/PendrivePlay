"""Configuração compartilhada dos testes (o pytest carrega este arquivo sozinho)."""
import shutil
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))  # permite "import baixador" nos testes

import autoteste  # noqa: E402
import baixador  # noqa: E402


@pytest.fixture(scope="session")
def ffmpeg() -> str:
    return baixador.achar_ffmpeg()


@pytest.fixture(scope="session")
def video_teste(ffmpeg, tmp_path_factory) -> Path:
    """Um vídeo curto, em pé, gerado na hora (não usa internet)."""
    arquivo = tmp_path_factory.mktemp("origem") / "video original.mp4"
    autoteste._gerar_video_teste(ffmpeg, arquivo)
    return arquivo


@pytest.fixture
def pendrive(tmp_path) -> Path:
    """Uma pasta vazia fazendo papel de pendrive."""
    p = tmp_path / "PENDRIVE"
    p.mkdir()
    return p


class YoutubeDLFalso:
    """Substitui o yt-dlp: em vez de baixar, copia vídeos locais."""

    videos: list[Path] = []
    opcoes_recebidas: dict = {}

    def __init__(self, opcoes):
        self.opcoes = opcoes
        YoutubeDLFalso.opcoes_recebidas = opcoes

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def download(self, urls):
        pasta = Path(self.opcoes["outtmpl"]).parent
        pasta.mkdir(parents=True, exist_ok=True)
        for video in self.videos:
            for gancho in self.opcoes["progress_hooks"]:
                gancho({"status": "downloading", "info_dict": {"title": video.stem},
                        "downloaded_bytes": 50, "total_bytes": 100})
            shutil.copy(video, pasta / video.name)


@pytest.fixture
def ytdlp_falso(monkeypatch):
    import yt_dlp
    YoutubeDLFalso.videos = []
    monkeypatch.setattr(yt_dlp, "YoutubeDL", YoutubeDLFalso)
    return YoutubeDLFalso
