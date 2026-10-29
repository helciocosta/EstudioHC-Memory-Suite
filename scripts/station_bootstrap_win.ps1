# ==============================================================================
# EstudioHC Station Bootstrap & Auto-Update v2.0 (Windows)
# Executado no logon ou via Task Scheduler para manter o Coletor Local ativo
# ==============================================================================
$ErrorActionPreference = "SilentlyContinue"
[System.Net.ServicePointManager]::ServerCertificateValidationCallback = { $true }

Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] [StationBootstrap] Iniciando bootstrap v2.0 da estacao Windows..." -ForegroundColor Cyan

# 1. Verificar Tailscale
$tsIp = (tailscale ip -4) 2>$null
if ($tsIp) {
    Write-Host "[StationBootstrap] Tailscale ativo: $tsIp" -ForegroundColor Green
} else {
    $tsIp = "desconhecido"
}

# 2. Garantir mapeamento hub.estudiohc no hosts
$hostsPath = "C:\Windows\System32\drivers\etc\hosts"
$hostsContent = Get-Content $hostsPath -Raw -ErrorAction SilentlyContinue
if ($hostsContent -notmatch "hub\.estudiohc") {
    Write-Host "[StationBootstrap] Inserindo hub.estudiohc no arquivo hosts..." -ForegroundColor Yellow
    Add-Content -Path $hostsPath -Value "`n100.64.117.78 hub.estudiohc" -Force
}

# 3. Iniciar Obsidian Collector v2.0 em segundo plano se não estiver rodando
$collectorScript = "C:\Users\helcio\scripts\obsidian_collector.py"
$runningCollector = Get-CimInstance Win32_Process | Where-Object { $_.Name -match "^python" -and $_.CommandLine -like "*obsidian_collector.py*" }
if (-not $runningCollector -and (Test-Path $collectorScript)) {
    Write-Host "[StationBootstrap] Iniciando obsidian_collector.py v2.0 em segundo plano..." -ForegroundColor Green
    $pyExe = "C:\Python315\pythonw.exe"
    if (-not (Test-Path $pyExe)) { $pyExe = "python" }
    Start-Process -FilePath $pyExe -ArgumentList "`"$collectorScript`"" -WindowStyle Hidden
} else {
    Write-Host "[StationBootstrap] obsidian_collector.py ja em execucao." -ForegroundColor Gray
}

# 4. Sincronizar Agenda Local
$agendaScript = "C:\Users\helcio\scripts\agenda_sync.py"
if (Test-Path $agendaScript) {
    Write-Host "[StationBootstrap] Sincronizando agenda local..." -ForegroundColor Cyan
    & python "$agendaScript"
}

# 5. Testar conectividade com a API Central
try {
    $res = Invoke-RestMethod -Uri "https://hub.estudiohc:5050/api/status" -TimeoutSec 3
    Write-Host "[StationBootstrap] Conectado ao Hub EstudioHC: $($res.status) ($($res.servidor))" -ForegroundColor Green
} catch {
    Write-Host "[StationBootstrap] Aviso: Falha ao contactar hub.estudiohc. O coletor acionara failover automatico se necessario." -ForegroundColor Yellow
}
