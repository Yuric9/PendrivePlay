@echo off
chcp 65001 >nul
title PendrivePlay - Criar instalador
cd /d "%~dp0"

echo ========================================
echo  PendrivePlay - Gerador do instalador
echo ========================================
echo.

echo [1/5] Verificando Python...
python --version >nul 2>&1
if errorlevel 1 (
  echo [ERRO] Python nao encontrado. Instale em https://python.org
  echo        e marque "Add python.exe to PATH".
  goto fim
)

echo [2/5] Criando ambiente isolado .venv-build...
if not exist .venv-build python -m venv .venv-build
set PY=.venv-build\Scripts\python.exe
%PY% -m pip install --upgrade pip -q
%PY% -m pip install -r requirements.txt -r requirements-build.txt -q
if errorlevel 1 ( echo [ERRO] Falha ao instalar dependencias. & goto fim )

echo [3/5] Gerando o programa com PyInstaller...
rem imageio_ffmpeg fica de fora: o ffmpeg.exe e copiado separado (evita 100 MB duplicados)
%PY% -m PyInstaller --noconfirm --clean --windowed --name PendrivePlay --exclude-module imageio_ffmpeg app.py
if errorlevel 1 ( echo [ERRO] Falha no PyInstaller. & goto fim )

echo [4/5] Copiando ffmpeg para junto do programa...
%PY% -c "import imageio_ffmpeg, shutil; shutil.copy(imageio_ffmpeg.get_ffmpeg_exe(), r'dist\PendrivePlay\ffmpeg.exe')"
if errorlevel 1 ( echo [ERRO] Falha ao copiar o ffmpeg. & goto fim )

echo [5/5] Montando o instalador com Inno Setup...
set ISCC=
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set ISCC="%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set ISCC="%ProgramFiles%\Inno Setup 6\ISCC.exe"
if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set ISCC="%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not defined ISCC (
  echo.
  echo [AVISO] Inno Setup nao encontrado, entao o instalador nao foi gerado.
  echo         Instale com:  winget install JRSoftware.InnoSetup
  echo         ou baixe em https://jrsoftware.org/isdl.php e rode este arquivo de novo.
  echo.
  echo O programa ja funciona sem instalar em: dist\PendrivePlay\PendrivePlay.exe
  goto fim
)
%ISCC% /Q instalador\PendrivePlay.iss
if errorlevel 1 ( echo [ERRO] Falha no Inno Setup. & goto fim )

echo.
echo ========================================
echo  PRONTO! Instalador em: saida\
echo ========================================

:fim
if not defined CI pause
