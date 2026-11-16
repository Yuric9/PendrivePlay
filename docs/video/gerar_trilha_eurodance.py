"""Trilha original estilo eurodance anos 90 para o vídeo do PendrivePlay.

Clima de pista dos anos 90 (bumbo reto, piano house, baixo no contratempo,
sintetizador com melodia-tema), com melodia e arranjo próprios. Tudo é
sintetizado aqui, sem samples nem trechos de músicas de terceiros, então a
trilha é livre de direitos autorais.

Uso: python gerar_trilha_eurodance.py [saida.wav] [duracao_em_segundos]
Precisa de numpy e scipy.
"""
import sys
import wave

import numpy as np
from scipy.signal import butter, fftconvolve, sosfilt

TAXA = 44100
BPM = 128
BATIDA = 60 / BPM           # ~0,469 s
SEMI = BATIDA / 4           # semicolcheia
COMPASSO = 4 * BATIDA       # ~1,875 s

saida = sys.argv[1] if len(sys.argv) > 1 else "trilha_eurodance.wav"
duracao = float(sys.argv[2]) if len(sys.argv) > 2 else 33.0
N = int(duracao * TAXA)
rng = np.random.default_rng(1994)


def bus():
    return np.zeros((N, 2))


bateria, baixo, piano, cordas, lider, efeitos, envio_reverb = (bus() for _ in range(7))


# ---------------------------------------------------------------- utilitários
def nota(nome):
    semis = {"C": -9, "C#": -8, "D": -7, "D#": -6, "E": -5, "F": -4, "F#": -3,
             "G": -2, "G#": -1, "A": 0, "A#": 1, "B": 2}
    return 440.0 * 2 ** ((semis[nome[:-1]] + 12 * (int(nome[-1]) - 4)) / 12)


def t_(n):
    return np.arange(n) / TAXA


def filtro(x, corte, tipo="low", ordem=2):
    corte = float(np.clip(corte, 20, TAXA / 2 - 100))
    return sosfilt(butter(ordem, corte, btype=tipo, fs=TAXA, output="sos"), x, axis=0)


def serra(f, n, fase=0.0):
    return 2 * ((t_(n) * f + fase) % 1) - 1


def env(n, a=0.004, d=0.0, s=1.0, r=0.04):
    e = np.ones(n) * s
    na = min(n, int(a * TAXA)); e[:na] = np.linspace(0, 1, na)
    nd = int(d * TAXA)
    if nd:
        fim = min(n, na + nd); e[na:fim] = np.linspace(1, s, fim - na)
    nr = min(n, int(r * TAXA))
    if nr:
        e[-nr:] *= np.linspace(1, 0, nr)
    return e


def por(b, s, inicio, vol=1.0, pan=0.0):
    i = int(round(inicio * TAXA))
    if not 0 <= i < N:
        return
    if s.ndim == 1:
        s = np.stack([s * (1 - max(0, pan)), s * (1 + min(0, pan))], 1)
    s = s[: N - i] * vol
    b[i:i + len(s)] += s


def varredura(x, cortes, tipo="low"):
    """Aplica um filtro que muda com o tempo (em pedaços)."""
    partes = np.array_split(np.arange(len(x)), len(cortes))
    return np.concatenate([filtro(x[p], c, tipo) for p, c in zip(partes, cortes)])


# ---------------------------------------------------------------- instrumentos
def bumbo():
    n = int(0.4 * TAXA); t = t_(n)
    f = 50 + 170 * np.exp(-t * 40)
    corpo = np.sin(2 * np.pi * np.cumsum(f) / TAXA) * np.exp(-t * 8)
    clique = filtro(rng.uniform(-1, 1, n), 4000, "high") * np.exp(-t * 400) * 0.5
    return np.tanh((corpo + clique) * 2.2)


def palmas():
    n = int(0.35 * TAXA); t = t_(n); x = np.zeros(n)
    for atraso in (0, 0.009, 0.019, 0.03):
        i = int(atraso * TAXA)
        x[i:] += filtro(rng.uniform(-1, 1, n - i), 1100, "high") * np.exp(-t_(n - i) * (40 if atraso < 0.03 else 14))
    corpo = np.sin(2 * np.pi * 200 * t) * np.exp(-t * 30) * 0.5
    return (x * 0.7 + corpo) * 0.9


def chimbal(aberto=False):
    n = int((0.2 if aberto else 0.04) * TAXA)
    return filtro(rng.uniform(-1, 1, n), 7500, "high", 4) * np.exp(-t_(n) * (16 if aberto else 80))


def prato():
    n = int(2.0 * TAXA)
    return filtro(rng.uniform(-1, 1, n), 4500, "high") * np.exp(-t_(n) * 2.0)


def piano_house(freqs, dur):
    """Piano 'house' dos anos 90: ataque brilhante e decaimento rápido."""
    n = int(dur * TAXA); t = t_(n); x = np.zeros(n)
    for f in freqs:
        for h, (amp, dec) in enumerate([(1.0, 6), (0.55, 9), (0.35, 12), (0.22, 15), (0.12, 19), (0.07, 24)], 1):
            inarm = 1 + 0.0004 * h * h
            x += amp * np.sin(2 * np.pi * f * h * inarm * t + rng.random()) * np.exp(-t * dec)
    x = x / len(freqs) * env(n, 0.002, r=0.05)
    esq = x; dir_ = np.roll(x, int(0.006 * TAXA))   # leve abertura estéreo
    return np.stack([esq, dir_], 1)


def supersaw(f, n, vozes=6, abertura=0.01):
    e = np.zeros(n); d = np.zeros(n)
    for k in range(vozes):
        det = (k - (vozes - 1) / 2) / ((vozes - 1) / 2) * abertura
        onda = serra(f * (1 + det), n, rng.random())
        pan = (k / (vozes - 1)) * 2 - 1
        e += onda * (1 - max(0, pan)); d += onda * (1 + min(0, pan))
    return np.stack([e, d], 1) / vozes


BUMBO, PALMAS, HH, HHA, PRATO = bumbo(), palmas(), chimbal(), chimbal(True), prato()

# ---------------------------------------------------------------- harmonia e tema
PROG = [
    ("A1", ["A3", "C4", "E4", "A4"]),
    ("F1", ["F3", "A3", "C4", "F4"]),
    ("G1", ["G3", "B3", "D4", "G4"]),
    ("E1", ["E3", "G#3", "B3", "E4"]),   # Mi maior: a "tensão" típica da eurodance
]
# piano: semicolcheias com ataque (ritmo sincopado próprio)
PIANO_RITMO = [0, 3, 6, 10, 12, 14]
# melodia-tema do sintetizador (colcheias; "-" segura, "." pausa)
TEMA = [
    ["A4", "-", "C5", "E5", "-", "D5", "C5", "."],
    ["A4", "-", "C5", "F5", "-", "E5", "C5", "."],
    ["B4", "-", "D5", "G5", "-", "F5", "D5", "."],
    ["E5", "-", "D5", "-", "B4", "-", "G#4", "."],
]
n_comp = int(np.ceil(duracao / COMPASSO))
DROP = 1          # explosão no 2º compasso (~1,9 s)
FINAL = 15        # refrão final (~28,1 s)
PAUSA = 9         # compasso com a bateria mais leve (respiro no meio)

for c in range(n_comp):
    ini = c * COMPASSO
    nome_baixo, acorde = PROG[c % 4]
    freqs = [nota(x) for x in acorde]

    # ----- piano house
    for s in PIANO_RITMO:
        p = piano_house(freqs, SEMI * 1.8)
        vol = 0.5 if c >= DROP else 0.35
        if c == 0:
            p = varredura(p, np.linspace(600, 4000, 8))   # introdução abafada abrindo
        por(piano, p, ini + s * SEMI, vol)
        por(envio_reverb, p, ini + s * SEMI, 0.18)

    if c < DROP:
        continue

    # ----- cordas / acordes de fundo
    n = int(COMPASSO * TAXA)
    pad = sum(supersaw(nota(x), n) for x in acorde[:3]) / 3
    pad = filtro(pad, 2400) * env(n, 0.05, r=0.1)[:, None]
    por(cordas, pad, ini, 0.35)
    por(envio_reverb, pad, ini, 0.2)

    # ----- baixo no contratempo (marca da eurodance) + nota no tempo, mais suave
    for k in range(8):
        f = nota(nome_baixo) * (2 if k % 2 else 1)
        nb = int(BATIDA / 2 * TAXA * 0.8)
        b = serra(f, nb) * 0.65 + np.sin(2 * np.pi * f * t_(nb)) * 0.6
        b = filtro(b, 1100 if k % 2 else 600) * env(nb, 0.003, 0.06, 0.55, 0.03)
        por(baixo, b, ini + k * BATIDA / 2, 0.8 if k % 2 else 0.45)

    # ----- melodia-tema (a partir do 3º compasso; mais forte no final)
    if c >= 3:
        linha = TEMA[c % 4]
        k = 0
        while k < 8:
            if linha[k] in "-.":
                k += 1; continue
            dur = 1
            while k + dur < 8 and linha[k + dur] == "-":
                dur += 1
            nn = int(dur * BATIDA / 2 * TAXA * 0.92)
            f = nota(linha[k])
            vib = 1 + 0.005 * np.sin(2 * np.pi * 6 * t_(nn)) * np.clip(t_(nn) * 5, 0, 1)
            fase = np.cumsum(f * vib) / TAXA
            som = (2 * (fase % 1) - 1) + 0.5 * (2 * ((fase * 1.005) % 1) - 1)
            # filtro que abre e fecha a cada nota: som de "metal" sintético
            som = varredura(som, 1500 + 3500 * np.exp(-np.linspace(0, 4, 10)))
            som *= env(nn, 0.005, 0.12, 0.7, 0.05)
            vol = 0.4 if c >= FINAL else 0.3
            por(lider, som, ini + k * BATIDA / 2, vol, 0.1)
            por(envio_reverb, som, ini + k * BATIDA / 2, vol * 0.5)
            k += dur

    # ----- bateria
    leve = c == PAUSA
    for b in range(4):
        if not leve:
            por(bateria, BUMBO, ini + b * BATIDA, 1.0)
        if b in (1, 3):
            por(bateria, PALMAS, ini + b * BATIDA, 0.5)
            por(envio_reverb, PALMAS, ini + b * BATIDA, 0.12)
        por(bateria, HHA, ini + b * BATIDA + BATIDA / 2, 0.2, 0.25)
    for s in range(16):
        por(bateria, HH, ini + s * SEMI, 0.08 if s % 2 else 0.045, -0.3)

    # viradas antes da pausa e do final
    if c in (PAUSA, FINAL - 1):
        for s in range(8):
            por(bateria, PALMAS, ini + 2 * BATIDA + s * SEMI, 0.15 + 0.05 * s)

for c in (DROP, PAUSA + 1, FINAL):
    por(bateria, PRATO, c * COMPASSO, 0.35)


# ---------------------------------------------------------------- efeitos
def subida(dur):
    n = int(dur * TAXA)
    return varredura(rng.uniform(-1, 1, n), 300 + 8000 * np.linspace(0, 1, 24) ** 2) * np.linspace(0, 1, n) ** 2


def whoosh():
    n = int(0.6 * TAXA)
    return varredura(rng.uniform(-1, 1, n), 800 + 5000 * np.sin(np.linspace(0, np.pi, 12))) * np.sin(np.linspace(0, np.pi, n))


def impacto():
    n = int(1.6 * TAXA); t = t_(n)
    return np.tanh(np.sin(2 * np.pi * np.cumsum(36 + 70 * np.exp(-t * 6)) / TAXA) * np.exp(-t * 2.4) * 2)


por(efeitos, subida(COMPASSO - 0.1), 0.05, 0.3)
for troca in (5, 11, 17, 22):
    por(efeitos, whoosh(), troca - 0.35, 0.28, 0.5 if troca % 2 else -0.5)
por(efeitos, subida(1.4), FINAL * COMPASSO - 1.4, 0.32)
por(efeitos, impacto(), FINAL * COMPASSO, 0.65)

# acorde final de piano + cordas segurando
fim_ini = duracao - 2.4
por(piano, piano_house([nota(x) for x in ["A3", "C4", "E4", "A4"]], 2.4), fim_ini, 0.7)
n = int(2.4 * TAXA)
pad = sum(supersaw(nota(x), n) for x in ["A3", "C4", "E4"]) / 3
por(cordas, filtro(pad, 2600) * env(n, 0.01, r=1.6)[:, None], fim_ini, 0.4)
por(envio_reverb, pad * env(n, 0.01, r=1.6)[:, None], fim_ini, 0.35)

# ---------------------------------------------------------------- mixagem
# "pumping" a cada bumbo nas cordas e no baixo
pump = np.ones(N)
tb = t_(int(BATIDA * TAXA)); curva = 1 - 0.5 * np.exp(-tb / 0.08)
for i in range(int(np.ceil(duracao / BATIDA))):
    if i * BATIDA < DROP * COMPASSO or PAUSA * COMPASSO <= i * BATIDA < (PAUSA + 1) * COMPASSO:
        continue
    a = int(i * BATIDA * TAXA); seg = curva[: max(0, min(len(curva), N - a))]
    pump[a:a + len(seg)] = seg
cordas *= pump[:, None]; baixo *= (0.45 + 0.55 * pump)[:, None]; piano *= (0.75 + 0.25 * pump)[:, None]

nir = int(1.6 * TAXA)
ir = rng.uniform(-1, 1, (nir, 2)) * np.exp(-t_(nir) * 3.5)[:, None]
ir = filtro(ir, 5500)
reverb = np.stack([fftconvolve(envio_reverb[:, k], ir[:, k])[:N] for k in range(2)], 1)
reverb /= np.max(np.abs(reverb)) + 1e-9

atraso = int(BATIDA * 0.75 * TAXA)
eco = np.zeros_like(lider)
eco[atraso:, 0] = lider[:-atraso, 1] * 0.3; eco[atraso:, 1] = lider[:-atraso, 0] * 0.3

mix = bateria * 1.0 + baixo * 0.85 + piano * 0.75 + cordas * 0.5 + lider * 0.8 + eco * 0.8 + efeitos * 0.85 + reverb * 0.2
mix = mix - filtro(mix, 30)                       # tira graves inaudíveis
fade = int(1.0 * TAXA); mix[-fade:] *= np.linspace(1, 0, fade)[:, None]
mix /= np.percentile(np.abs(mix), 99.7) + 1e-9
mix = np.tanh(mix * 1.2) / np.tanh(1.2)
mix *= 0.95 / (np.max(np.abs(mix)) + 1e-9)

with wave.open(saida, "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(TAXA)
    w.writeframes((mix * 32767).astype(np.int16).tobytes())
print(f"Trilha salva em {saida} ({duracao:.0f} s, {BPM} BPM)")
