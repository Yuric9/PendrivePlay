#!/usr/bin/env bash
# Edita o vídeo real (gravado na barbearia) em um anúncio vertical de ~25 s.
# Uso: ./montar.sh <video_original.mp4> <pasta_de_trabalho> <modelo_faber.onnx> [comando_piper] [python_com_scipy]
# Saídas em <pasta_de_trabalho>/saida:
#   anuncio_com_locucao.mp4, anuncio_so_musica.mp4, post_som_original.mp4
set -euo pipefail
SRC="$1"; W="$2"; MODELO="$3"; PIPER="${4:-piper}"; PY="${5:-python3}"
AQUI="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$W/saida"; cd "$W"

# trechos: nome inicio_no_original duracao (cortes no ritmo da música, 128 BPM)
TRECHOS="s1 76.0 3.75
s2 0.3 2.8125
s3 24.0 3.28125
s4 39.2 3.28125
s5 64.9 3.75
s6 79.4 3.75"
FIM=4.6875          # cartão final
TOTAL=25.3125
CORTES=(0 3.75 6.5625 9.84375 13.125 16.875 20.625)

AJUSTE="fps=30,scale=1080:-2:flags=lanczos,crop=1080:1920,unsharp=5:5:0.7,eq=contrast=1.06:saturation=1.15:brightness=0.02,setsar=1"

# 1) cortar e estabilizar cada trecho (duas versões do s4: normal e com a lista desfocada)
while read -r nome ini dur; do
  ffmpeg -nostdin -y -loglevel error -ss "$ini" -t "$dur" -i "$SRC" -vf "vidstabdetect=shakiness=6:accuracy=12:result=$nome.trf" -f null -
  ESTAB="vidstabtransform=input=$nome.trf:smoothing=20:zoom=4:interpol=bicubic"
  ffmpeg -nostdin -y -loglevel error -ss "$ini" -t "$dur" -i "$SRC" -vf "$ESTAB,$AJUSTE" -an -c:v libx264 -crf 16 -preset fast "$nome.mp4"
  ffmpeg -nostdin -y -loglevel error -ss "$ini" -t "$dur" -i "$SRC" -vn -af "afade=t=in:d=0.04,afade=t=out:st=$(echo "$dur-0.06" | bc):d=0.06" -ar 44100 -ac 2 "$nome.wav"
  if [ "$nome" = s4 ]; then
    # anúncio: deixa ilegíveis os nomes de artistas da lista da TV (parte de cima do quadro)
    ffmpeg -nostdin -y -loglevel error -ss "$ini" -t "$dur" -i "$SRC" -filter_complex "[0]$ESTAB,split[a][b];[b]crop=iw:ih*0.56:0:0,gblur=sigma=6[c];[a][c]overlay=0:0,$AJUSTE" -an -c:v libx264 -crf 16 -preset fast s4_desfocado.mp4
  fi
done <<< "$TRECHOS"

# 2) fundo do cartão final: último quadro desfocado e parado
ffmpeg -nostdin -y -loglevel error -ss 82.9 -i "$SRC" -frames:v 1 -vf "$AJUSTE,gblur=sigma=18" fim.png
ffmpeg -nostdin -y -loglevel error -loop 1 -t "$FIM" -i fim.png -vf "fps=30,format=yuv420p" -c:v libx264 -crf 16 -preset fast s7.mp4

# 3) legendas (PNG transparentes)
node "$AQUI/legendas.js" "$W/leg"

# 4) juntar trechos + legendas
montar_video() {   # $1 = arquivo do trecho 4, $2 = saída sem áudio
  local entradas="-i s1.mp4 -i s2.mp4 -i s3.mp4 -i $1 -i s5.mp4 -i s6.mp4 -i s7.mp4"
  local leg="-loop 1 -i leg/l1.png -loop 1 -i leg/l2.png -loop 1 -i leg/l3.png -loop 1 -i leg/l4.png -loop 1 -i leg/l5.png -loop 1 -i leg/l6.png -loop 1 -i leg/fim.png"
  local f="[0][1][2][3][4][5][6]concat=n=7:v=1:a=0[base];"
  local ant="base"
  for k in 0 1 2 3 4 5 6; do
    local ini=${CORTES[$k]}; local fim_l
    if [ $k -lt 6 ]; then fim_l=${CORTES[$((k+1))]}; else fim_l=$TOTAL; fi
    f+="[$((7+k))]format=rgba,fade=t=in:st=$ini:d=0.18:alpha=1,trim=0:$TOTAL[l$k];"
    f+="[$ant][l$k]overlay=0:0:enable='between(t,$ini,$fim_l)':shortest=1[v$k];"
    ant="v$k"
  done
  ffmpeg -nostdin -y -loglevel error $entradas $leg -filter_complex "${f%;}" -map "[$ant]" -t $TOTAL -r 30 -c:v libx264 -crf 18 -preset slow -pix_fmt yuv420p "$2"
}
montar_video s4_desfocado.mp4 video_anuncio.mp4
montar_video s4.mp4 video_post.mp4

# 5) áudio
TRILHA_FINAL=11 TRILHA_PAUSA=6 TRILHA_TROCAS="3.75,6.5625,9.84375,16.875" "$PY" "$AQUI/../gerar_trilha_eurodance.py" trilha.wav $TOTAL
i=0; atrasos=()
while IFS='|' read -r ini max texto; do
  i=$((i+1))
  echo "$texto" | "$PIPER" -m "$MODELO" --length-scale 0.8 --noise-scale 0.8 --noise-w-scale 0.95 -f "bruta$i.wav" 2>/dev/null
  ffmpeg -nostdin -y -loglevel error -i "bruta$i.wav" -af "asetrate=22050*1.04,aresample=44100,highpass=f=100,equalizer=f=3000:t=q:w=1.2:g=4,equalizer=f=200:t=q:w=1:g=2,acompressor=threshold=-24dB:ratio=4:attack=3:release=80:makeup=4" "fala$i.wav"
  atrasos+=("$(python3 -c "print(int($ini*1000))")")
done < "$AQUI/narracao.txt"
ffmpeg -nostdin -y -loglevel error $(for n in $(seq 1 $i); do echo -n "-i fala$n.wav "; done) -filter_complex "\
$(for n in $(seq 1 $i); do a=${atrasos[$((n-1))]}; echo -n "[$((n-1))]adelay=$a|$a[a$n];"; done)\
$(for n in $(seq 1 $i); do echo -n "[a$n]"; done)amix=inputs=$i:normalize=0,aformat=sample_rates=44100:channel_layouts=stereo,\
apad=whole_dur=$TOTAL[v]" -map "[v]" -t $TOTAL voz.wav
ffmpeg -nostdin -y -loglevel error -i trilha.wav -i voz.wav -filter_complex "\
[1]asplit=2[voz][sc];[0]volume=0.5[m];[m][sc]sidechaincompress=threshold=0.025:ratio=10:attack=15:release=300[md];\
[voz]volume=1.8[vz];[md][vz]amix=inputs=2:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11" -ar 44100 -t $TOTAL audio_locucao.wav
ffmpeg -nostdin -y -loglevel error -i trilha.wav -af "loudnorm=I=-14:TP=-1.5:LRA=11" -ar 44100 -t $TOTAL audio_musica.wav
# post: som original dos trechos + trilha baixinha por baixo (e no cartão final)
ffmpeg -nostdin -y -loglevel error -i s1.wav -i s2.wav -i s3.wav -i s4.wav -i s5.wav -i s6.wav -i trilha.wav -filter_complex "\
[0][1][2][3][4][5]concat=n=6:v=0:a=1,loudnorm=I=-16,apad=whole_dur=$TOTAL[orig];[6]volume=0.22[m];\
[orig][m]amix=inputs=2:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11" -ar 44100 -t $TOTAL audio_original.wav

# 6) versões finais
juntar() { ffmpeg -nostdin -y -loglevel error -i "$1" -i "$2" -map 0:v -map 1:a -c:v copy -c:a aac -b:a 192k -movflags +faststart -shortest "saida/$3"; }
juntar video_anuncio.mp4 audio_locucao.wav anuncio_com_locucao.mp4
juntar video_anuncio.mp4 audio_musica.wav anuncio_so_musica.mp4
juntar video_post.mp4 audio_original.wav post_som_original.mp4
echo "Pronto: $W/saida"
