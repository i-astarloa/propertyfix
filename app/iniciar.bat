@echo off
REM Arranque de PropertyFix en Windows: doble clic en este archivo.
cd /d "%~dp0"
chcp 65001 >nul

if not exist ".venv\Scripts\python.exe" (
  where python >nul 2>nul
  if errorlevel 1 (
    echo [!] No se encuentra Python. Instala Python 3.12 desde https://www.python.org/downloads/ marcando "Add python.exe to PATH".
    pause & exit /b 1
  )
  echo Creando el entorno virtual e instalando dependencias ^(solo la primera vez, 1-2 minutos^)...
  python -m venv .venv || (pause & exit /b 1)
  ".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
  ".venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt || (pause & exit /b 1)
)

where ollama >nul 2>nul
if errorlevel 1 (
  echo [!] Ollama no esta instalado. La app arrancara, pero los agentes usaran reglas de respaldo.
  echo     Instalalo desde https://ollama.com/download y ejecuta:  ollama pull qwen2.5:3b
) else (
  ollama list | findstr /C:"qwen2.5:3b" >nul || (echo Descargando el modelo qwen2.5:3b ^(1,9 GB, solo la primera vez^)... & ollama pull qwen2.5:3b)
)

".venv\Scripts\python.exe" -m propertyfix
pause
