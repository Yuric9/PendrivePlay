"""Trilha original no estilo flashback / anos 80 para o vídeo do PendrivePlay.

Tudo é sintetizado aqui (sem samples nem músicas de terceiros), então a trilha
é livre de direitos autorais.

Uso: python gerar_trilha.py [saida.wav] [duracao_em_segundos]
"""
import sys
import wave

import numpy as np

TAXA = 44100
BPM = 112
BATIDA = 60 / BPM            # duração de uma batida (s)
COMPASSO = 4 * BATIDA        # 4 batidas por compasso

saida = sys.argv[1] if len(sys.argv) > 1 else "trilha_flashback.wav"
duracao = float(sys.argv[2]) if len(sys.argv) > 2 else 33.0
n_total = int(duracao * TAXA)
rng = np.random.default_rng(80)  # sempre gera a mesma trilha

esq = np.zeros(n_total)
dir_ = np.zeros(n_total)


def nota(nome: str) -> float:
    """Converte 'A3', 'C#4' etc. em frequência (Hz)."""
    semis = {"C": -9, "C#": -8, "D": -7, "D#": -6, "E": -5, "F": -4, "F#": -3,
             "G": -2, "G#": -1, "A": 0, "A#": 1, "B": 2}
    oitava = int(nome[-1])
    return 440.0 * 2 ** ((semis[nome[:-1]] + 12 * (oitava - 4)) / 12)


def tempo(n: int) -> np.ndarray:
    return np.arange(n) / TAXA


def passa_baixa(sinal: np.ndarray, corte: float) -> np.ndarray:
    """Filtro simples de um polo: deixa o som mais 'quente', como sintetizador analógico."""
    a = np.exp(-2 * np.pi * corte / TAXA)
    saida_f = np.empty_like(sinal)
    y = 0.0
    for i, x in enumerate(sinal):
        y = (1 - a) * x + a * y
        saida_f[i] = y
    return saida_f


def serra(freq: float, n: int, desafinar: float = 0.0) -> np.ndarray:
    t = tempo(n)
    f = freq * (1 + desafinar)
    return 2 * ((t * f) % 1) - 1


def quadrada(freq: float, n: int) -> np.ndarray:
    return np.sign(np.sin(2 * np.pi * freq * tempo(n)))


def envelope(n: int, ataque: float, soltura: float) -> np.ndarray:
    env = np.ones(n)
    a = min(n, int(ataque * TAXA))
    r = min(n, int(soltura * TAXA))
    if a:
        env[:a] = np.linspace(0, 1, a)
    if r:
        env[-r:] *= np.linspace(1, 0, r)
    return env


def somar(sinal: np.ndarray, inicio: float, vol: float, pan: float = 0.0) -> None:
    """Coloca o som na trilha (pan: -1 esquerda, 0 centro, 1 direita)."""
    i = int(inicio * TAXA)
    if i >= n_total:
        return
    s = sinal[: n_total - i] * vol
    esq[i:i + len(s)] += s * (1 - max(0, pan))
    dir_[i:i + len(s)] += s * (1 + min(0, pan))


# Progressão clássica de flashback: Lá menor - Fá - Dó - Sol
ACORDES = [
    ("A2", ["A3", "C4", "E4"]),
    ("F2", ["F3", "A3", "C4"]),
    ("C3", ["G3", "C4", "E4"]),
    ("G2", ["G3", "B3", "D4"]),
]
n_compassos = int(np.ceil(duracao / COMPASSO))
BATERIA_ENTRA = 2   # bateria entra no 3º compasso (perto de "Transforme em TV multimídia")

# ---------- sons de bateria ----------
def bumbo() -> np.ndarray:
    n = int(0.35 * TAXA)
    t = tempo(n)
    freq = 45 + 110 * np.exp(-t * 28)
    fase = 2 * np.pi * np.cumsum(freq) / TAXA
    return np.sin(fase) * np.exp(-t * 9)


def caixa_80() -> np.ndarray:
    """Caixa com o famoso 'reverb cortado' (gated reverb) dos anos 80."""
    n = int(0.42 * TAXA)
    t = tempo(n)
    ruido = rng.uniform(-1, 1, n)
    corpo = np.sin(2 * np.pi * 190 * t) * np.exp(-t * 25)
    cauda = passa_baixa(ruido, 6000) * np.exp(-t * 4)
    portao = np.where(t < 0.30, 1.0, np.exp(-(t - 0.30) * 60))   # corta a cauda de repente
    return (corpo * 0.8 + cauda * 0.9) * portao


def chimbal() -> np.ndarray:
    n = int(0.05 * TAXA)
    ruido = rng.uniform(-1, 1, n)
    agudo = ruido - passa_baixa(ruido, 7000)
    return agudo * np.exp(-tempo(n) * 70)


BUMBO, CAIXA, CHIMBAL = bumbo(), caixa_80(), chimbal()

for c in range(n_compassos):
    ini = c * COMPASSO
    baixo_nome, acorde = ACORDES[c % 4]

    # pad (acordes longos com serras desafinadas)
    n = int(COMPASSO * TAXA)
    pad = sum(serra(nota(x), n, d) for x in acorde for d in (-0.004, 0.004))
    pad = passa_baixa(pad / 6, 1400) * envelope(n, 0.35, 0.3)
    somar(pad, ini, 0.32, -0.3)
    somar(pad, ini + 0.012, 0.32, 0.3)       # pequeno atraso: som "largo" em estéreo

    # baixo pulsante em colcheias
    for k in range(8):
        n = int(BATIDA / 2 * TAXA * 0.9)
        b = serra(nota(baixo_nome), n) + 0.5 * serra(nota(baixo_nome) * 2, n)
        b = passa_baixa(b, 700) * envelope(n, 0.005, 0.05)
        somar(b, ini + k * BATIDA / 2, 0.42)

    # arpejo em semicolcheias com eco
    sequencia = acorde + [acorde[1]]
    for k in range(16):
        freq = nota(sequencia[k % 4]) * 2
        n = int(BATIDA / 4 * TAXA * 0.8)
        a = quadrada(freq, n) * 0.5 + serra(freq, n) * 0.5
        a = passa_baixa(a, 2600) * envelope(n, 0.003, 0.06)
        t_nota = ini + k * BATIDA / 4
        vol = 0.13 if c >= 1 else 0.13 * (k / 16)        # entra crescendo
        somar(a, t_nota, vol, 0.4 * (1 if k % 2 else -1))
        somar(a, t_nota + BATIDA * 0.75, vol * 0.35, -0.5)  # eco

    # bateria
    if c >= BATERIA_ENTRA:
        for k in range(4):
            somar(BUMBO, ini + k * BATIDA, 0.9)
            if k in (1, 3):
                somar(CAIXA, ini + k * BATIDA, 0.5)
        for k in range(8):
            somar(CHIMBAL, ini + k * BATIDA / 2, 0.22 if k % 2 else 0.14, 0.25)
    elif c == BATERIA_ENTRA - 1:
        # virada de caixa antes da bateria entrar
        for k in range(4):
            somar(CAIXA, ini + 3 * BATIDA + k * BATIDA / 4, 0.18 + 0.08 * k)

# ---------- mixagem final ----------
mix = np.stack([esq, dir_], axis=1)
fade_in = int(0.4 * TAXA)
fade_out = int(2.5 * TAXA)
mix[:fade_in] *= np.linspace(0, 1, fade_in)[:, None]
mix[-fade_out:] *= np.linspace(1, 0, fade_out)[:, None]
mix = np.tanh(mix * 1.1)                 # saturação suave, como fita
mix /= np.max(np.abs(mix)) * 1.12        # deixa uma folga no volume
pcm = (mix * 32767).astype(np.int16)

with wave.open(saida, "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(TAXA)
    w.writeframes(pcm.tobytes())
print(f"Trilha salva em {saida} ({duracao:.0f} s, {BPM} BPM)")
