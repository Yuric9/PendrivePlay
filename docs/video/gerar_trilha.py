"""Trilha original estilo flashback dance anos 80 para o vídeo do PendrivePlay.

Tudo é sintetizado aqui (sem samples nem músicas de terceiros), então a trilha
é livre de direitos autorais.

Estrutura (120 BPM, 1 compasso = 2 s, casando com as cenas do vídeo):
  0-2 s    introdução: acordes filtrados + subida de ruído
  2 s      "explosão": bateria, baixo em oitavas, acordes e melodia
  5/11/17/22 s  efeito de transição (whoosh) nas trocas de cena
  27-28 s  virada de caixa
  28 s     impacto no final + último refrão
  31,5 s   acorde final com eco

Uso: python gerar_trilha.py [saida.wav] [duracao_em_segundos]
Precisa de numpy e scipy.
"""
import sys
import wave

import numpy as np
from scipy.signal import butter, fftconvolve, sosfilt

TAXA = 44100
BPM = 120
BATIDA = 60 / BPM          # 0,5 s
COMPASSO = 4 * BATIDA      # 2 s

saida = sys.argv[1] if len(sys.argv) > 1 else "trilha_flashback.wav"
duracao = float(sys.argv[2]) if len(sys.argv) > 2 else 33.0
N = int(duracao * TAXA)
rng = np.random.default_rng(1985)   # sempre gera a mesma trilha

# barramentos (estéreo) para mixar cada grupo separado
def barramento():
    return np.zeros((N, 2))

bateria, baixo, acordes, melodia, efeitos, eco_envio = (barramento() for _ in range(6))


# ---------------------------------------------------------------- utilitários
def nota(nome: str) -> float:
    semis = {"C": -9, "C#": -8, "D": -7, "D#": -6, "E": -5, "F": -4, "F#": -3,
             "G": -2, "G#": -1, "A": 0, "A#": 1, "B": 2}
    return 440.0 * 2 ** ((semis[nome[:-1]] + 12 * (int(nome[-1]) - 4)) / 12)


def t_(n):
    return np.arange(n) / TAXA


def filtro(sinal, corte, tipo="low", ordem=2):
    corte = np.clip(corte, 20, TAXA / 2 - 100)
    sos = butter(ordem, corte, btype=tipo, fs=TAXA, output="sos")
    return sosfilt(sos, sinal)


def serra(f, n, fase=0.0):
    return 2 * ((t_(n) * f + fase) % 1) - 1


def supersaw(f, n, vozes=7, abertura=0.012):
    """Várias serras levemente desafinadas: o som 'gordo' dos sintetizadores dos anos 80."""
    esq = np.zeros(n); dir_ = np.zeros(n)
    for k in range(vozes):
        d = (k - (vozes - 1) / 2) / ((vozes - 1) / 2) * abertura
        onda = serra(f * (1 + d), n, rng.random())
        pan = (k / (vozes - 1)) * 2 - 1
        esq += onda * (1 - max(0, pan)); dir_ += onda * (1 + min(0, pan))
    return np.stack([esq, dir_], 1) / vozes


def env(n, a=0.005, d=0.0, s=1.0, r=0.05):
    e = np.ones(n) * s
    na, nd, nr = int(a * TAXA), int(d * TAXA), int(r * TAXA)
    na = min(na, n); e[:na] = np.linspace(0, 1, na)
    if nd:
        fim = min(n, na + nd); e[na:fim] = np.linspace(1, s, fim - na)
    if nr:
        nr = min(nr, n); e[-nr:] *= np.linspace(1, 0, nr)
    return e


def por(bus, sinal, inicio, vol=1.0, pan=0.0):
    i = int(round(inicio * TAXA))
    if i >= N or i < 0:
        return
    if sinal.ndim == 1:
        sinal = np.stack([sinal * (1 - max(0, pan)), sinal * (1 + min(0, pan))], 1)
    s = sinal[: N - i] * vol
    bus[i:i + len(s)] += s


# ---------------------------------------------------------------- bateria
def bumbo():
    n = int(0.45 * TAXA); t = t_(n)
    f = 48 + 150 * np.exp(-t * 35)
    corpo = np.sin(2 * np.pi * np.cumsum(f) / TAXA) * np.exp(-t * 7)
    clique = filtro(rng.uniform(-1, 1, n), 3000, "high") * np.exp(-t * 300) * 0.4
    return np.tanh((corpo + clique) * 1.8)


def caixa_palmas():
    """Caixa + palmas, com cauda curta (o 'gated reverb' dos anos 80)."""
    n = int(0.5 * TAXA); t = t_(n)
    tom = np.sin(2 * np.pi * 185 * t) * np.exp(-t * 22)
    ruido = filtro(rng.uniform(-1, 1, n), 1200, "high") * np.exp(-t * 9)
    palmas = np.zeros(n)
    for atraso in (0, 0.011, 0.022):
        i = int(atraso * TAXA)
        palmas[i:] += filtro(rng.uniform(-1, 1, n - i), 1500, "high") * np.exp(-t_(n - i) * 28)
    portao = np.where(t < 0.26, 1.0, np.exp(-(t - 0.26) * 70))
    return (tom * 0.7 + ruido * 0.8 + palmas * 0.6) * portao


def chimbal(aberto=False):
    n = int((0.22 if aberto else 0.045) * TAXA)
    r = filtro(rng.uniform(-1, 1, n), 8000, "high", 4)
    return r * np.exp(-t_(n) * (14 if aberto else 75))


def prato():
    n = int(2.2 * TAXA)
    r = filtro(rng.uniform(-1, 1, n), 5000, "high", 2)
    return r * np.exp(-t_(n) * 2.2)


BUMBO, CAIXA, HH, HHA, PRATO = bumbo(), caixa_palmas(), chimbal(), chimbal(True), prato()

# ---------------------------------------------------------------- harmonia
# Lá menor - Fá - Dó - Sol (a progressão clássica do flashback)
PROG = [("A1", ["A3", "C4", "E4"]), ("F1", ["F3", "A3", "C4"]),
        ("C2", ["E3", "G3", "C4"]), ("G1", ["D3", "G3", "B3"])]
# melodia-tema (colcheias; "-" = segura a nota anterior, "." = pausa)
TEMA = [
    ["E5", "-", "E5", "D5", "C5", "-", "A4", "."],
    ["C5", "-", "C5", "D5", "E5", "-", "D5", "."],
    ["E5", "-", "G5", "-", "E5", "D5", "C5", "."],
    ["D5", "-", "B4", "-", "G4", "-", "B4", "D5"],
]
n_comp = int(np.ceil(duracao / COMPASSO))
DROP = 1            # compasso em que a música "explode" (2 s)
FINAL = 14          # compasso da cena final (28 s)

for c in range(n_comp):
    ini = c * COMPASSO
    nome_baixo, acorde = PROG[c % 4]
    ativo = c >= DROP

    # ----- acordes (supersaw) com o filtro abrindo na introdução
    n = int(COMPASSO * TAXA)
    pad = sum(supersaw(nota(x), n) for x in acorde) / len(acorde)
    corte = 900 + 1800 * (c >= DROP) + (600 * np.linspace(0, 1, n) if c == 0 else 0)
    if np.isscalar(corte):
        pad = np.stack([filtro(pad[:, k], corte) for k in range(2)], 1)
    else:  # varredura de filtro na introdução (feita em pedaços)
        pedacos = np.array_split(np.arange(n), 16)
        pad = np.concatenate([np.stack([filtro(pad[p, k], corte[p].mean()) for k in range(2)], 1) for p in pedacos])
    pad *= env(n, 0.02 if ativo else 0.6, r=0.08)[:, None]
    por(acordes, pad, ini, 0.55)
    por(eco_envio, pad, ini, 0.25)

    if not ativo:
        continue

    # ----- baixo em oitavas (colcheias), típico da dance dos anos 80
    for k in range(8):
        f = nota(nome_baixo) * (2 if k % 2 else 1)
        nb = int(BATIDA / 2 * TAXA * 0.85)
        b = serra(f, nb) * 0.7 + np.sign(np.sin(2 * np.pi * f * t_(nb))) * 0.3
        b = filtro(b, 900) * env(nb, 0.003, 0.08, 0.6, 0.03)
        por(baixo, b, ini + k * BATIDA / 2, 0.75)

    # ----- melodia-tema (a partir do 3º compasso, e mais forte no final)
    if c >= 3:
        linha = TEMA[c % 4]
        k = 0
        while k < 8:
            if linha[k] in ("-", "."):
                k += 1; continue
            dur = 1
            while k + dur < 8 and linha[k + dur] == "-":
                dur += 1
            nn = int(dur * BATIDA / 2 * TAXA * 0.95)
            f = nota(linha[k])
            vib = 1 + 0.004 * np.sin(2 * np.pi * 5.5 * t_(nn)) * np.clip(t_(nn) * 4, 0, 1)
            fase = np.cumsum(f * vib) / TAXA
            som = (2 * (fase % 1) - 1) * 0.6 + np.sign(np.sin(2 * np.pi * fase)) * 0.25
            som = filtro(som, 3200) * env(nn, 0.006, 0.1, 0.75, 0.06)
            vol = 0.42 if c >= FINAL else 0.32
            por(melodia, som, ini + k * BATIDA / 2, vol, 0.15)
            por(eco_envio, som, ini + k * BATIDA / 2, vol * 0.6)
            k += dur

    # ----- bateria
    for b in range(4):
        por(bateria, BUMBO, ini + b * BATIDA, 0.95)
        if b in (1, 3):
            por(bateria, CAIXA, ini + b * BATIDA, 0.55)
            por(eco_envio, CAIXA, ini + b * BATIDA, 0.15)
        por(bateria, HHA, ini + b * BATIDA + BATIDA / 2, 0.16, 0.3)
    for s in range(16):
        por(bateria, HH, ini + s * BATIDA / 4, 0.09 if s % 2 else 0.05, -0.3)

    # virada de caixa antes do final
    if c == FINAL - 1:
        for s in range(8):
            por(bateria, CAIXA, ini + 2 * BATIDA + s * BATIDA / 4, 0.18 + 0.05 * s)

# prato na "explosão" e no final
por(bateria, PRATO, DROP * COMPASSO, 0.35)
por(bateria, PRATO, FINAL * COMPASSO, 0.4)

# ---------------------------------------------------------------- efeitos
def subida(dur):
    """Ruído que sobe de tom (riser) antes de uma explosão."""
    n = int(dur * TAXA)
    r = rng.uniform(-1, 1, n)
    pedacos = np.array_split(np.arange(n), 24)
    out = np.concatenate([filtro(r[p], 300 + 7000 * (i / 24) ** 2, "band" if False else "low") for i, p in enumerate(pedacos)])
    return out * np.linspace(0, 1, n) ** 2


def whoosh():
    n = int(0.6 * TAXA)
    r = rng.uniform(-1, 1, n)
    pedacos = np.array_split(np.arange(n), 12)
    out = np.concatenate([filtro(r[p], 800 + 5000 * np.sin(np.pi * i / 12)) for i, p in enumerate(pedacos)])
    return out * np.sin(np.linspace(0, np.pi, n))


def impacto():
    n = int(1.5 * TAXA); t = t_(n)
    boom = np.sin(2 * np.pi * np.cumsum(38 + 60 * np.exp(-t * 6)) / TAXA) * np.exp(-t * 2.5)
    return np.tanh(boom * 2)


por(efeitos, subida(1.9), 0.1, 0.35)
for troca in (5, 11, 17, 22):
    por(efeitos, whoosh(), troca - 0.35, 0.3, 0.5 if troca % 2 else -0.5)
por(efeitos, subida(1.0), FINAL * COMPASSO - 1.0, 0.3)
por(efeitos, impacto(), FINAL * COMPASSO, 0.7)

# acorde final segurado
n = int(2.5 * TAXA)
fim = sum(supersaw(nota(x), n) for x in ["A3", "C4", "E4", "A4"]) / 4
fim = np.stack([filtro(fim[:, k], 3000) for k in range(2)], 1) * env(n, 0.01, r=1.5)[:, None]
por(acordes, fim, duracao - 2.6, 0.6)
por(eco_envio, fim, duracao - 2.6, 0.4)

# ---------------------------------------------------------------- mixagem
# "pumping": acordes e baixo abaixam a cada bumbo (marca registrada da dance)
pump = np.ones(N)
tb = t_(int(BATIDA * TAXA))
curva = 1 - 0.55 * np.exp(-tb / 0.09)
for i in range(int(np.ceil(duracao / BATIDA))):
    ini = int(i * BATIDA * TAXA)
    if i * BATIDA < DROP * COMPASSO:
        continue
    seg = curva[: max(0, min(len(curva), N - ini))]
    pump[ini:ini + len(seg)] = seg
acordes *= pump[:, None]
baixo *= (0.4 + 0.6 * pump)[:, None]

# reverb: resposta ao impulso feita de ruído com decaimento (estéreo)
nir = int(1.8 * TAXA)
ir = rng.uniform(-1, 1, (nir, 2)) * np.exp(-t_(nir) * 3.2)[:, None]
ir[:, 0] = filtro(ir[:, 0], 6000); ir[:, 1] = filtro(ir[:, 1], 6000)
reverb = np.stack([fftconvolve(eco_envio[:, k], ir[:, k])[:N] for k in range(2)], 1)
reverb /= np.max(np.abs(reverb)) + 1e-9

# eco em colcheia pontuada na melodia
atraso = int(BATIDA * 0.75 * TAXA)
eco = np.zeros_like(melodia)
eco[atraso:, 0] = melodia[:-atraso, 1] * 0.35
eco[atraso:, 1] = melodia[:-atraso, 0] * 0.35

mix = (bateria * 1.0 + baixo * 0.85 + acordes * 0.55 + melodia * 0.8 + eco * 0.8
       + efeitos * 0.9 + reverb * 0.22)
mix[:, 0] = mix[:, 0] - filtro(mix[:, 0], 30, "low")   # tira graves inaudíveis
mix[:, 1] = mix[:, 1] - filtro(mix[:, 1], 30, "low")

# fade de saída e "masterização" simples
fade = int(1.2 * TAXA)
mix[-fade:] *= np.linspace(1, 0, fade)[:, None]
mix /= np.percentile(np.abs(mix), 99.7) + 1e-9
mix = np.tanh(mix * 1.15) / np.tanh(1.15)
mix *= 0.95 / (np.max(np.abs(mix)) + 1e-9)

pcm = (mix * 32767).astype(np.int16)
with wave.open(saida, "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(TAXA)
    w.writeframes(pcm.tobytes())
print(f"Trilha salva em {saida} ({duracao:.0f} s, {BPM} BPM)")
