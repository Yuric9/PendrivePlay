# PendrivePlay

Programa para Windows que baixa vídeos e músicas e salva **direto no pendrive**,
já no formato que TVs antigas, Smart TVs e TV Box conseguem tocar.

Projeto de uso pessoal e de estudo. Respeite os direitos autorais e os termos de
uso das plataformas.

## Como funciona

1. Conecte o pendrive: ele aparece sozinho na lista "Salvar em".
2. Cole **um ou vários links**, um por linha, ou clique em **Carregar lista .txt**.
3. Escolha **Vídeo MP4 para TV** ou **Música MP3** e clique em **Baixar**.

Os links são baixados um de cada vez. Se algum der erro, o programa continua
com os outros e, no final, deixa na caixa só os que falharam, para você tentar
de novo. Links repetidos e linhas começando com `#` são ignorados.

**Pausar e cancelar:**

- **Pausar** para o download na hora; **Continuar** retoma de onde parou. Se a
  pausa acontecer durante a conversão, ela vale ao terminar o arquivo atual.
  Em pausas muito longas (horas), o link pode expirar: ele volta para a caixa
  como erro e é só baixar de novo.
- **Cancelar** para tudo na hora. O que já terminou fica no pendrive, nada fica
  pela metade, e os links que faltaram voltam para a caixa.
- Fechar a janela durante um download pergunta se você quer cancelar.

O programa cria as pastas no pendrive, se ainda não existirem:

```
E:\
├── VIDEOS_TV\   ← vídeos MP4
└── MP3\         ← músicas
```

O download e a conversão acontecem numa pasta temporária do PC, e só o arquivo
pronto é copiado para o pendrive. Assim, se o pendrive for removido no meio,
não fica arquivo pela metade com nome de arquivo bom.

| Formato | Detalhes |
|---|---|
| MP4 para TV | 1280x720, H.264 baseline nível 3.1, AAC 192k, faststart |
| MP3 | 192 kbps, 44.1 kHz |

Links de playlist baixam todos os vídeos.

## Instalar

Baixe o `PendrivePlay_Instalador_x.x.x.exe` na página **Releases** do GitHub e
execute. Ele não pede senha de administrador e cria um atalho na área de trabalho.

> O Windows pode mostrar "O Windows protegeu o computador", porque o instalador
> não tem assinatura digital. Clique em **Mais informações → Executar assim mesmo**.

## Gerar o instalador

**Opção 1: no GitHub (automático).** Na aba *Actions*, abra
"Testes e instalador" e clique em *Run workflow*. Ao final, o instalador fica
em *Artifacts*. Se você criar uma tag (`v1.0.0`), ele também vai para *Releases*.

**Opção 2: no seu PC.**

1. Instale o [Python 3.12+](https://python.org) (marque *Add python.exe to PATH*).
2. Instale o [Inno Setup 6](https://jrsoftware.org/isdl.php) (ou `winget install JRSoftware.InnoSetup`).
3. Dê duplo clique em `CRIAR_INSTALADOR.bat`.
4. O instalador aparece na pasta `saida\`.

## Desenvolvimento

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Ou dê duplo clique em `ABRIR_SEM_INSTALAR.bat`.

Também dá para usar pelo terminal:

```bash
python baixador.py mp4 E:\ "LINK1" "LINK2"
```

### Testes

```bash
pip install -r requirements-dev.txt
python -m pytest
```

Os testes não usam a internet: eles geram um vídeo de teste com o ffmpeg e
trocam o yt-dlp por uma versão falsa. Eles rodam sozinhos no GitHub (Linux e
Windows) a cada envio de código.

### Autoteste do programa instalado

Para conferir se o programa instalado está completo (ffmpeg, yt-dlp e conversões):

```bash
"%LOCALAPPDATA%\Programs\PendrivePlay\PendrivePlay.exe" --autoteste resultado.txt
```

O resultado fica em `resultado.txt`. O GitHub faz esse mesmo teste depois de
gerar o instalador.

### Estrutura

| Arquivo | Função |
|---|---|
| `app.py` | Janela (Tkinter) |
| `baixador.py` | Download (yt-dlp) e conversão (ffmpeg) |
| `pendrive.py` | Detecta pendrives conectados no Windows |
| `autoteste.py` | Autoteste (`--autoteste`) |
| `testes/` | Testes automáticos (pytest) |
| `licencas/` | Licenças dos componentes (FFmpeg GPLv3 etc.) |
| `docs/gumroad/` | Guia em PDF, página de venda, capa e capturas de tela |
| `instalador/PendrivePlay.iss` | Script do instalador (Inno Setup) |
| `CRIAR_INSTALADOR.bat` | Gera o `.exe` e o instalador |
| `.github/workflows/` | Gera o instalador automaticamente no GitHub |

## Problemas comuns

- **Parou de baixar:** os sites mudam com frequência e o `yt-dlp` precisa ser
  atualizado. Gere o instalador de novo (ele já usa a versão mais nova do yt-dlp).
- **O pendrive não aparece:** clique em *Atualizar*. Alguns HDs externos não são
  reconhecidos como pendrive; nesse caso use *Escolher outra pasta...*.
- **A TV não abre o vídeo:** confira se o arquivo está na pasta `VIDEOS_TV` e
  se o pendrive está em FAT32 ou exFAT.

## Licença

MIT. O instalador inclui o FFmpeg (GPLv3) e outros componentes com licenças
próprias: veja [`licencas/TERCEIROS.txt`](licencas/TERCEIROS.txt).
