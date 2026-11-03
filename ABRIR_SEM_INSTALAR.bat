@echo off
chcp 65001 >nul
title PendrivePlay
cd /d "%~dp0"

rem Para testar o programa durante o desenvolvimento, sem gerar o instalador.
python --version >nul 2>&1
if errorlevel 1 (
  echo [ERRO] Python nao encontrado. Instale em https://python.org
  pause
  exit /b
)
if not exist .venv python -m venv .venv
.venv\Scripts\python.exe -m pip install -q -r requirements.txt
.venv\Scripts\python.exe app.py
if errorlevel 1 pause
