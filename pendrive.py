"""Detecta pendrives (unidades removíveis) conectados no Windows."""
from __future__ import annotations

import shutil
import string
import sys
from dataclasses import dataclass
from pathlib import Path

DRIVE_REMOVABLE = 2  # código que o Windows usa para "unidade removível"


@dataclass
class Unidade:
    raiz: Path      # ex.: E:\
    nome: str       # nome do pendrive, ex.: "KINGSTON"
    livre_gb: float

    def rotulo(self) -> str:
        return f"{self.raiz.drive}  {self.nome}  ({self.livre_gb:.1f} GB livres)"


def listar_pendrives() -> list[Unidade]:
    """Retorna os pendrives conectados. Fora do Windows retorna lista vazia."""
    if sys.platform != "win32":
        return []

    import ctypes

    kernel32 = ctypes.windll.kernel32
    # Evita a janela "Insira um disco" em leitores de cartão vazios.
    kernel32.SetErrorMode(1)

    mascara = kernel32.GetLogicalDrives()
    encontrados: list[Unidade] = []
    for i, letra in enumerate(string.ascii_uppercase):
        if not mascara & (1 << i):
            continue
        raiz = f"{letra}:\\"
        if kernel32.GetDriveTypeW(raiz) != DRIVE_REMOVABLE:
            continue
        nome = ctypes.create_unicode_buffer(261)
        if not kernel32.GetVolumeInformationW(raiz, nome, 261, None, None, None, None, 0):
            continue  # unidade sem mídia (ex.: leitor de cartão vazio)
        try:
            livre = shutil.disk_usage(raiz).free / 1024**3
        except OSError:
            continue
        encontrados.append(Unidade(Path(raiz), nome.value or "PENDRIVE", livre))
    return encontrados
