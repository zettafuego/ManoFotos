@echo off
title Mano abierta = fotos Taylor + Bob Esponja
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (
    set PY=py
) else (
    set PY=python
)

echo Instalando dependencias si faltan...
%PY% -m pip install -r requirements.txt
if errorlevel 1 (
    echo No pude instalar las librerias. Revisa que Python este instalado.
    pause
    exit /b 1
)

echo.
echo Abre la mano frente a la camara para descargar fotos.
echo Q = salir   D = descargar ahora   O = abrir carpeta
echo.
%PY% main.py
echo.
pause
