"""Testes de pausar e cancelar.

Os testes "real" usam o yt-dlp de verdade, baixando de um servidor HTTP
criado no próprio computador (sem internet).
"""
import functools
import http.server
import shutil
import threading
import time

import pytest

import autoteste
import baixador


# ---------- servidor local + yt-dlp de verdade ----------

@pytest.fixture(scope="module")
def servidor(tmp_path_factory):
    """Serve um vídeo de ~2 MB em http://127.0.0.1:PORTA/filme.mp4."""
    pasta = tmp_path_factory.mktemp("servidor")
    ffmpeg = baixador.achar_ffmpeg()
    baixador._rodar_ffmpeg([
        ffmpeg, "-y", "-f", "lavfi", "-i", "testsrc=size=640x360:rate=30:duration=20",
        "-f", "lavfi", "-i", "sine=duration=20", "-c:v", "mpeg4", "-b:v", "800k",
        "-c:a", "aac", "-shortest", str(pasta / "filme.mp4"),
    ])
    Handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(pasta))
    Handler.log_message = lambda *a: None
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_port}/filme.mp4"
    httpd.shutdown()


@pytest.fixture
def ytdlp_lento(monkeypatch):
    """yt-dlp de verdade, mas limitado a ~1 MB/s para dar tempo de pausar."""
    import yt_dlp
    Original = yt_dlp.YoutubeDL

    class Lento(Original):
        def __init__(self, opcoes):
            super().__init__(dict(opcoes, ratelimit=1_000_000, proxy=""))

    monkeypatch.setattr(yt_dlp, "YoutubeDL", Lento)


def _rodar_em_thread(links, formato, pendrive, controle):
    progresso, res = [], {}

    def trabalho():
        res["r"] = baixador.baixar_varios(links, formato, pendrive, aviso=lambda m: None,
                                          progresso=progresso.append, controle=controle)

    t = threading.Thread(target=trabalho)
    t.start()
    return t, progresso, res


def _esperar_progresso(progresso, minimo=1, limite=15):
    fim = time.time() + limite
    while time.time() < fim:
        if progresso and progresso[-1] >= minimo:
            return
        time.sleep(0.05)
    raise AssertionError("o download não começou")


def test_real_baixa_e_converte(servidor, ytdlp_lento, pendrive, ffmpeg):
    r = baixador.baixar_varios([servidor], "mp4", pendrive, aviso=lambda m: None)
    assert r.erros == {}
    assert [f.name for f in r.salvos] == ["filme.mp4"]
    info = autoteste.descrever_midia(ffmpeg, r.salvos[0])
    assert "h264 (Constrained Baseline)" in info and "1280x720" in info


def test_real_pausar_e_continuar(servidor, ytdlp_lento, pendrive):
    controle = baixador.Controle()
    t, progresso, res = _rodar_em_thread([servidor], "mp3", pendrive, controle)
    _esperar_progresso(progresso)

    controle.pausar()
    time.sleep(0.5)
    parado_em = progresso[-1]
    time.sleep(2)
    assert progresso[-1] == parado_em, "o download andou durante a pausa"
    assert parado_em < 100

    controle.retomar()
    t.join(60)
    r = res["r"]
    assert not r.cancelado and r.erros == {}
    assert [f.name for f in r.salvos] == ["filme.mp3"]


@pytest.mark.parametrize("pausar_antes", [False, True])
def test_real_cancelar_no_meio_do_download(servidor, ytdlp_lento, pendrive, pausar_antes):
    controle = baixador.Controle()
    links = [servidor, servidor + "?2"]
    t, progresso, res = _rodar_em_thread(links, "mp4", pendrive, controle)
    _esperar_progresso(progresso)

    if pausar_antes:
        controle.pausar()
        time.sleep(0.5)
    inicio = time.time()
    controle.cancelar()
    t.join(30)

    assert time.time() - inicio < 5, "demorou para cancelar"
    r = res["r"]
    assert r.cancelado
    assert r.salvos == []
    assert r.pendentes == links                    # os dois voltam para a caixa
    assert not [p for p in pendrive.rglob("*") if p.is_file()]  # nada pela metade


# ---------- sem servidor ----------

def test_cancelar_entre_links_guarda_os_que_faltam(ytdlp_falso, video_teste, pendrive):
    ytdlp_falso.videos = [video_teste]
    controle = baixador.Controle()
    links = ["https://exemplo/1", "https://exemplo/2", "https://exemplo/3"]

    def aviso(msg):
        if msg.startswith("Salvo:"):   # cancela logo depois do 1º arquivo
            controle.cancelar()

    r = baixador.baixar_varios(links, "mp3", pendrive, aviso=aviso, controle=controle)
    assert r.cancelado
    assert len(r.salvos) == 1                      # o que já terminou fica
    assert r.pendentes == links[1:]


def test_cancelar_encerra_o_ffmpeg_na_hora(ffmpeg, tmp_path):
    longo = tmp_path / "longo.mp4"
    baixador._rodar_ffmpeg([
        ffmpeg, "-y", "-f", "lavfi", "-i", "testsrc=size=1920x1080:rate=30:duration=90",
        "-c:v", "mpeg4", "-q:v", "10", str(longo),
    ])
    controle = baixador.Controle()
    threading.Timer(0.5, controle.cancelar).start()
    inicio = time.time()
    with pytest.raises(baixador.Cancelado):
        baixador.converter_para_tv(ffmpeg, longo, tmp_path / "saida.mp4", controle)
    assert time.time() - inicio < 5


def test_controle_estados():
    c = baixador.Controle()
    assert not c.pausado and not c.cancelado
    c.pausar()
    assert c.pausado
    c.retomar()
    assert not c.pausado
    c.pausar()
    c.cancelar()                                   # cancelar solta a pausa
    assert c.cancelado and not c.pausado
    with pytest.raises(baixador.Cancelado):
        c.checar()
