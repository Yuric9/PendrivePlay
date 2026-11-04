"""Testes do baixador: pastas, nomes, conversão e o fluxo completo."""
import pytest

import autoteste
import baixador


# ---------- pastas e nomes ----------

def test_cria_pasta_de_videos_no_pendrive(pendrive):
    pasta = baixador.preparar_destino(pendrive, "mp4")
    assert pasta == pendrive / "VIDEOS_TV"
    assert pasta.is_dir()


def test_cria_pasta_de_mp3_no_pendrive(pendrive):
    pasta = baixador.preparar_destino(pendrive, "mp3")
    assert pasta == pendrive / "MP3"
    assert pasta.is_dir()


def test_nao_sobrescreve_arquivo_existente(pendrive):
    (pendrive / "musica.mp3").write_text("já existe")
    (pendrive / "musica (2).mp3").write_text("também existe")
    assert baixador.nome_livre(pendrive, "musica", "mp3").name == "musica (3).mp3"


def test_formato_invalido_e_recusado(pendrive):
    with pytest.raises(ValueError):
        baixador.baixar("https://exemplo", "avi", pendrive)


def test_pendrive_desconectado_da_erro_claro(tmp_path):
    with pytest.raises(RuntimeError, match="pendrive está conectado"):
        baixador.baixar("https://exemplo", "mp4", tmp_path / "E_nao_existe")


# ---------- conversão ----------

def test_converte_para_formato_de_tv(ffmpeg, video_teste, tmp_path):
    saida = tmp_path / "tv.mp4"
    baixador.converter_para_tv(ffmpeg, video_teste, saida)
    info = autoteste.descrever_midia(ffmpeg, saida)
    assert "h264 (Constrained Baseline)" in info
    assert "1280x720" in info  # vídeo em pé ganha bordas, não é esticado
    assert "aac" in info


def test_converte_para_mp3(ffmpeg, video_teste, tmp_path):
    saida = tmp_path / "musica.mp3"
    baixador.converter_para_mp3(ffmpeg, video_teste, saida)
    info = autoteste.descrever_midia(ffmpeg, saida)
    assert "Audio: mp3" in info
    assert "Video" not in info


def test_nao_deixa_arquivo_parcial_no_pendrive(ffmpeg, video_teste, pendrive, tmp_path):
    destino = baixador.preparar_destino(pendrive, "mp3")
    final = baixador.salvar_no_pendrive(ffmpeg, video_teste, destino, "mp3", tmp_path)
    assert final.exists()
    assert not list(pendrive.rglob("*.parcial"))


# ---------- fluxo completo (com yt-dlp falso, sem internet) ----------

@pytest.mark.parametrize("formato,pasta", [("mp4", "VIDEOS_TV"), ("mp3", "MP3")])
def test_baixar_salva_tudo_no_pendrive(formato, pasta, ytdlp_falso, video_teste,
                                       pendrive, tmp_path):
    # simula uma playlist com 2 vídeos
    segundo = tmp_path / "segundo video.mp4"
    segundo.write_bytes(video_teste.read_bytes())
    ytdlp_falso.videos = [video_teste, segundo]

    avisos = []
    salvos = baixador.baixar("https://exemplo/playlist", formato, pendrive,
                             aviso=avisos.append)

    assert len(salvos) == 2
    nomes = sorted(f.name for f in (pendrive / pasta).iterdir())
    assert nomes == [f"segundo video.{formato}", f"video original.{formato}"]
    assert any("Baixando" in a for a in avisos)


def test_opcoes_enviadas_ao_ytdlp(ytdlp_falso, video_teste, pendrive):
    ytdlp_falso.videos = [video_teste]
    baixador.baixar("https://exemplo", "mp4", pendrive)
    opcoes = ytdlp_falso.opcoes_recebidas
    assert opcoes["ffmpeg_location"]          # bug antigo: ffmpeg não era passado
    assert opcoes["windowsfilenames"] is True
    assert opcoes["noplaylist"] is False
    assert "height<=720" in opcoes["format"]


def test_link_sem_nada_baixado_da_erro(ytdlp_falso, pendrive):
    ytdlp_falso.videos = []
    with pytest.raises(RuntimeError, match="Nada foi baixado"):
        baixador.baixar("https://exemplo", "mp4", pendrive)
