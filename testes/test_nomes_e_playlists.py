"""Testes dos nomes de arquivo, do limite de 30 fps e das playlists."""
import pytest

import autoteste
import baixador


# ---------- nomes que a TV consegue ler ----------

@pytest.mark.parametrize("titulo,esperado", [
    ("Canção ｜ Ao Vivo", "Cancao - Ao Vivo"),                  # yt-dlp troca | por ｜
    ("Música： Ação", "Musica - Acao"),
    ("AC⧸DC - Thunderstruck (Official Video)", "AC-DC - Thunderstruck (Official Video)"),
    ("🔥 MIX 2024 🔥", "MIX 2024"),
    ("3 Doors Down - Here Without You (Official Music Video)",
     "3 Doors Down - Here Without You (Official Music Video)"),  # nome simples não muda
    ("？？？", "video"),                                          # nada sobrou
])
def test_nome_seguro(titulo, esperado):
    assert baixador.nome_seguro(titulo) == esperado


def test_nome_seguro_corta_nomes_longos_sem_quebrar_palavra():
    titulo = ("Alan Walker, Avicii, Dua Lipa, Coldplay, Martin Garrix & Kygo, "
              "The Chainsmokers Style - Feeling Me")
    nome = baixador.nome_seguro(titulo)
    assert len(nome) <= baixador.LIMITE_NOME
    assert titulo.startswith(nome)              # cortou numa palavra inteira
    assert not nome.endswith(("&", ",", " "))


def test_nome_seguro_so_tem_caracteres_simples():
    nome = baixador.nome_seguro("Ünïcödé «aspas» ★ ½ — teste ™ 日本語")
    assert nome.isascii()
    assert all(c.isalnum() or c in " ()[]&,.'!+_-" for c in nome)


def test_arquivo_salvo_com_nome_seguro(ffmpeg, video_teste, pendrive, tmp_path):
    origem = tmp_path / "Canção ｜ Ao Vivo.mp4"
    origem.write_bytes(video_teste.read_bytes())
    destino = baixador.preparar_destino(pendrive, "mp3")
    final = baixador.salvar_no_pendrive(ffmpeg, origem, destino, "mp3", tmp_path)
    assert final.name == "Cancao - Ao Vivo.mp3"


# ---------- limite de 30 quadros por segundo ----------

def test_video_60fps_vira_30fps(ffmpeg, tmp_path):
    origem = tmp_path / "clipe60.mp4"
    baixador._rodar_ffmpeg([
        ffmpeg, "-y", "-f", "lavfi", "-i", "testsrc=size=1280x720:rate=60:duration=2",
        "-c:v", "mpeg4", str(origem),
    ])
    assert "60 fps" in autoteste.descrever_midia(ffmpeg, origem)
    saida = tmp_path / "tv.mp4"
    baixador.converter_para_tv(ffmpeg, origem, saida)
    info = autoteste.descrever_midia(ffmpeg, saida)
    assert "30 fps" in info, info


def test_video_25fps_continua_25fps(ffmpeg, tmp_path):
    origem = tmp_path / "video25.mp4"
    baixador._rodar_ffmpeg([
        ffmpeg, "-y", "-f", "lavfi", "-i", "testsrc=size=640x360:rate=25:duration=2",
        "-c:v", "mpeg4", str(origem),
    ])
    saida = tmp_path / "tv.mp4"
    baixador.converter_para_tv(ffmpeg, origem, saida)
    assert "25 fps" in autoteste.descrever_midia(ffmpeg, saida)


# ---------- reconhecer links de playlist ----------

@pytest.mark.parametrize("url,tipo", [
    ("https://www.youtube.com/watch?v=abc", "simples"),
    ("https://www.youtube.com/watch?v=abc&t=30s", "simples"),
    ("https://www.youtube.com/watch?v=abc&list=PL123&index=2", "video_na_playlist"),
    ("https://youtu.be/abc?list=PL123", "video_na_playlist"),
    ("https://music.youtube.com/watch?v=abc&list=RDabc", "video_na_playlist"),
    ("https://www.youtube.com/playlist?list=PL123", "playlist"),
    ("https://exemplo.com/video.mp4", "simples"),
])
def test_tipo_link(url, tipo):
    assert baixador.tipo_link(url) == tipo


@pytest.mark.parametrize("url,esperado", [
    ("https://www.youtube.com/watch?v=abc&list=PL123&index=2",
     "https://www.youtube.com/watch?v=abc"),
    ("https://youtu.be/abc?list=PL123&t=10", "https://youtu.be/abc?t=10"),
    ("https://www.youtube.com/watch?v=abc", "https://www.youtube.com/watch?v=abc"),
])
def test_so_o_video(url, esperado):
    assert baixador.so_o_video(url) == esperado
    assert baixador.tipo_link(baixador.so_o_video(url)) == "simples"


def test_itens_da_playlist():
    info = {"_type": "playlist", "entries": [
        {"url": "https://www.youtube.com/watch?v=a", "title": "Primeira"},
        None,                                                    # vídeo removido
        {"id": "b", "ie_key": "Youtube", "title": "Segunda"},    # só o id
        {"url": "https://www.youtube.com/watch?v=a", "title": "Repetida"},
        {"url": "https://www.youtube.com/watch?v=c"},            # sem título
    ]}
    assert baixador._itens_da_playlist(info) == [
        ("https://www.youtube.com/watch?v=a", "Primeira"),
        ("https://www.youtube.com/watch?v=b", "Segunda"),
        ("https://www.youtube.com/watch?v=c", "https://www.youtube.com/watch?v=c"),
    ]


# ---------- playlist vira fila: cada vídeo salvo na hora ----------

PLAYLIST = "https://www.youtube.com/playlist?list=PL123"
ITENS = [(f"https://www.youtube.com/watch?v={i}", f"Musica {i}") for i in (1, 2, 3)]


@pytest.fixture
def playlist_falsa(monkeypatch):
    lidas = []

    def listar(url, aviso=print):
        lidas.append(url)
        if "quebrada" in url:
            raise RuntimeError("playlist privada")
        return ITENS

    monkeypatch.setattr(baixador, "listar_playlist", listar)
    return lidas


def test_playlist_salva_cada_video_antes_do_proximo(playlist_falsa, ytdlp_falso,
                                                    video_teste, pendrive):
    ytdlp_falso.videos = [video_teste]
    avisos = []
    r = baixador.baixar_varios([PLAYLIST], "mp3", pendrive, aviso=avisos.append)

    assert len(r.salvos) == 3 and r.erros == {}
    assert "Playlist com 3 vídeos." in avisos
    assert "[2/3] Musica 2" in avisos
    # o 1º vídeo foi salvo no pendrive antes de começar o 2º
    salvo_1 = next(i for i, a in enumerate(avisos) if a.startswith("Salvo:"))
    assert salvo_1 < avisos.index("[2/3] Musica 2")


def test_cancelar_playlist_guarda_os_videos_que_faltam(playlist_falsa, ytdlp_falso,
                                                       video_teste, pendrive):
    ytdlp_falso.videos = [video_teste]
    controle = baixador.Controle()

    def aviso(msg):
        if msg.startswith("Salvo:"):
            controle.cancelar()

    r = baixador.baixar_varios([PLAYLIST], "mp3", pendrive, aviso=aviso, controle=controle)
    assert r.cancelado
    assert len(r.salvos) == 1                                # o 1º ficou no pendrive
    assert r.pendentes == [ITENS[1][0], ITENS[2][0]]         # voltam os vídeos, não a playlist


def test_playlist_com_erro_nao_para_os_outros_links(playlist_falsa, ytdlp_falso,
                                                    video_teste, pendrive):
    ytdlp_falso.videos = [video_teste]
    quebrada = "https://www.youtube.com/playlist?list=quebrada"
    r = baixador.baixar_varios([quebrada, "https://exemplo/video"], "mp3", pendrive,
                               aviso=lambda m: None)
    assert "playlist privada" in r.erros[quebrada]
    assert len(r.salvos) == 1


def test_link_simples_nao_le_playlist(playlist_falsa, ytdlp_falso, video_teste, pendrive):
    ytdlp_falso.videos = [video_teste]
    baixador.baixar_varios(["https://www.youtube.com/watch?v=abc"], "mp3", pendrive,
                           aviso=lambda m: None)
    assert playlist_falsa == []
