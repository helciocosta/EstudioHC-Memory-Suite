@echo off
setlocal
echo ==============================================================================
echo [Comutador EstudioHC] Redirecionando Hub para o SERVIDOR LOCAL (100.107.208.50)
echo ==============================================================================

powershell -NoProfile -ExecutionPolicy Bypass -Command "$f = 'C:\Windows\System32\drivers\etc\hosts'; (Get-Content $f) -replace '.*hub\.estudiohc', '100.107.208.50 hub.estudiohc' | Set-Content $f"

echo [OK] Arquivo hosts atualizado: hub.estudiohc -^> 100.107.208.50
echo.
echo [1/2] Testando API Central (:5050 HTTPS)...
curl.exe -sk --connect-timeout 3 https://hub.estudiohc:5050/api/status
echo.
echo.
echo [2/2] Testando Servidor MCP SSE (:5051)...
curl.exe -s -m 2 http://hub.estudiohc:5051/sse | findstr /i "endpoint"
echo.
echo [CONCLUIDO] Hub EstudioHC ativo no Servidor Local de contingencia.
pause
