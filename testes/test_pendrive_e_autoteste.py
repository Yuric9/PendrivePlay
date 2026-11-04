"""Testes da detecção de pendrive e do autoteste."""
import sys
from pathlib import Path

import autoteste
import pendrive


def test_listar_pendrives_nao_quebra():
    unidades = pendrive.listar_pendrives()
    assert isinstance(unidades, list)
    if sys.platform != "win32":
        assert unidades == []
    for u in unidades:  # no Windows, cada item precisa estar completo
        assert u.raiz.exists()
        assert u.livre_gb >= 0


def test_rotulo_do_pendrive():
    u = pendrive.Unidade(Path("E:\\"), "KINGSTON", 14.62)
    assert "KINGSTON" in u.rotulo()
    assert "14.6 GB livres" in u.rotulo()


def test_autoteste_passa(tmp_path):
    saida = tmp_path / "resultado.txt"
    codigo = autoteste.rodar(saida)
    texto = saida.read_text(encoding="utf-8")
    assert codigo == 0, texto
    assert "RESULTADO: TUDO CERTO" in texto
