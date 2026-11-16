#!/usr/bin/env bash
# Monta o áudio do comercial: locução estilo loja (voz Faber, do Piper) + trilha eurodance.
# Uso: ./montar_audio.sh <pasta_de_trabalho> <modelo pt_BR-faber-medium.onnx>
# Cada linha de narracao.txt é: segundo_de_inicio|duracao_maxima|texto
set -euo pipefail
PASTA="$1"; MODELO="$2"; AQUI="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$PASTA"; cd "$PASTA"
python3 "$AQUI/gerar_trilha_eurodance.py" trilha.wav 33
i=0; atrasos=()
while IFS='|' read -r ini max texto; do
  i=$((i+1))
  echo "$texto" | piper -m "$MODELO" --length-scale 0.8 --noise-scale 0.8 --noise-w-scale 0.95 -f "bruta$i.wav"
  # voz de locutor de loja: um pouco mais aguda e rápida, com presença e compressão forte
  ffmpeg -y -loglevel error -i "bruta$i.wav" -af "asetrate=22050*1.04,aresample=44100,highpass=f=100,equalizer=f=3000:t=q:w=1.2:g=4,equalizer=f=200:t=q:w=1:g=2,acompressor=threshold=-24dB:ratio=4:attack=3:release=80:makeup=4" "fala$i.wav"
  atrasos+=("$(python3 -c "print(int($ini*1000))")")
done < "$AQUI/narracao.txt"
ffmpeg -y -loglevel error $(for n in $(seq 1 $i); do echo -n "-i fala$n.wav "; done) -filter_complex "\
$(for n in $(seq 1 $i); do a=${atrasos[$((n-1))]}; echo -n "[$((n-1))]adelay=$a|$a[a$n];"; done)\
$(for n in $(seq 1 $i); do echo -n "[a$n]"; done)amix=inputs=$i:normalize=0,aformat=sample_rates=44100:channel_layouts=stereo,\
apad=whole_dur=33[v]" -map "[v]" -t 33 voz.wav
# a música abaixa sozinha quando a voz fala (sidechain)
ffmpeg -y -loglevel error -i trilha.wav -i voz.wav -filter_complex "\
[1]asplit=2[voz][sc];[0]volume=0.5[m];[m][sc]sidechaincompress=threshold=0.025:ratio=10:attack=15:release=300[mduck];\
[voz]volume=1.8[vz];[mduck][vz]amix=inputs=2:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11" -ar 44100 -t 33 audio_final.wav
echo "Áudio pronto: $PASTA/audio_final.wav"
