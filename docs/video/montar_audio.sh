#!/usr/bin/env bash
# Monta o áudio do vídeo: narração (voz Faber, do Piper) + trilha flashback.
# Uso: ./montar_audio.sh <pasta_de_trabalho> <modelo pt_BR-faber-medium.onnx>
# Cada linha de narracao.txt é: segundo_de_inicio|duracao_maxima|texto
set -euo pipefail
PASTA="$1"; MODELO="$2"; AQUI="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$PASTA"; cd "$PASTA"
python3 "$AQUI/gerar_trilha.py" trilha.wav 33
i=0; atrasos=()
while IFS='|' read -r ini max texto; do
  i=$((i+1))
  echo "$texto" | piper -m "$MODELO" --length-scale 0.88 --noise-scale 0.75 --noise-w-scale 0.9 -f "fala$i.wav"
  atrasos+=("$(python3 -c "print(int($ini*1000))")")
done < "$AQUI/narracao.txt"
ffmpeg -y -loglevel error $(for n in $(seq 1 $i); do echo -n "-i fala$n.wav "; done) -filter_complex "\
$(for n in $(seq 1 $i); do a=${atrasos[$((n-1))]}; echo -n "[$((n-1))]adelay=$a|$a[a$n];"; done)\
$(for n in $(seq 1 $i); do echo -n "[a$n]"; done)amix=inputs=$i:normalize=0,aformat=sample_rates=44100:channel_layouts=stereo,\
highpass=f=90,acompressor=threshold=-20dB:ratio=3:attack=5:release=120,apad=whole_dur=33[v]" -map "[v]" -t 33 voz.wav
# a música abaixa sozinha quando a voz fala (sidechain)
ffmpeg -y -loglevel error -i trilha.wav -i voz.wav -filter_complex "\
[1]asplit=2[voz][sc];[0]volume=0.55[m];[m][sc]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=350[mduck];\
[voz]volume=1.6[vz];[mduck][vz]amix=inputs=2:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11" -ar 44100 -t 33 audio_final.wav
echo "Áudio pronto: $PASTA/audio_final.wav"
