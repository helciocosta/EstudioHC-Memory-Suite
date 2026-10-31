@echo off
cd /d "C:\Users\helcio\scripts"
echo Iniciando Failover Monitor para EstudioHC...
call "C:\Users\helcio\Projetos\momentonabolsa\venv\Scripts\activate.bat" 2>nul || echo "AVISO: Não foi possível ativar o venv do momentonabolsa, tentando Python do sistema..."
python failover_monitor.py
pause