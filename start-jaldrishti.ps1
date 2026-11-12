[CmdletBinding()]
param(
    [switch]$NoBrowser,
    [switch]$Wait
)

$ErrorActionPreference = "Stop"
$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RootDir

$LogDir = Join-Path $RootDir "logs"
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}

Write-Host "JalDrishti"
Write-Host ""
Write-Host "Checking dependencies..."

$Python = Join-Path $RootDir ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    Write-Host "ERROR: Python virtual environment not found (.venv)."
    exit 1
}

$NodeCmd = Get-Command "node" -ErrorAction SilentlyContinue
$NpmCmd  = Get-Command "npm" -ErrorAction SilentlyContinue
if ($null -eq $NodeCmd -or $null -eq $NpmCmd) {
    Write-Host "ERROR: Node.js / npm not found in system PATH."
    exit 1
}

$PgBin     = Join-Path $RootDir ".local_services\pgsql\bin\postgres.exe"
$PgCtl     = Join-Path $RootDir ".local_services\pgsql\bin\pg_ctl.exe"
$PgIsReady = Join-Path $RootDir ".local_services\pgsql\bin\pg_isready.exe"
$PgData    = Join-Path $RootDir ".local_services\pgsql\data"
if (-not (Test-Path $PgBin) -or -not (Test-Path $PgData)) {
    Write-Host "ERROR: PostgreSQL binaries or data directory missing in .local_services\pgsql."
    exit 1
}

$RedisBin  = Join-Path $RootDir ".local_services\redis\redis-server.exe"
$RedisCli  = Join-Path $RootDir ".local_services\redis\redis-cli.exe"
$RedisConf = Join-Path $RootDir ".local_services\redis\redis.windows.conf"
if (-not (Test-Path $RedisBin)) {
    Write-Host "ERROR: Redis binary missing in .local_services\redis."
    exit 1
}

function Test-PortInUse {
    param([int]$Port)
    $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if ($null -ne $conn) {
        $procId = $conn[0].OwningProcess
        $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
        return [PSCustomObject]@{
            InUse       = $true
            ProcessId   = $procId
            ProcessName = if ($proc) { $proc.ProcessName } else { "Unknown" }
        }
    }
    return [PSCustomObject]@{
        InUse       = $false
        ProcessId   = $null
        ProcessName = $null
    }
}

# 1. PostgreSQL (Port 5432)
Write-Host -NoNewline "Starting PostgreSQL... "
$pgStatus = Test-PortInUse -Port 5432
$pgRunning = $false

if ($pgStatus.InUse) {
    if ($pgStatus.ProcessName -like "*postgres*") {
        Write-Host "OK"
        $pgRunning = $true
    } else {
        Write-Host "FAILED"
        Write-Host "ERROR: Port 5432 is occupied by an unrelated process ($($pgStatus.ProcessName))."
        exit 1
    }
} else {
    $postmasterPid = Join-Path $PgData "postmaster.pid"
    if (Test-Path $postmasterPid) {
        Remove-Item $postmasterPid -Force -ErrorAction SilentlyContinue
    }

    $pgLog = Join-Path $LogDir "pgsql.log"
    $pgProc = Start-Process -FilePath $PgBin -ArgumentList "-D", $PgData `
        -RedirectStandardOutput $pgLog -RedirectStandardError (Join-Path $LogDir "pgsql_err.log") `
        -PassThru -WindowStyle Hidden

    $pgProc.Id | Out-File -FilePath (Join-Path $LogDir "pgsql.pid") -Force -Encoding ascii

    $timeout = 15
    while ($timeout -gt 0) {
        Start-Sleep -Seconds 1
        $timeout--
        $ready = & $PgIsReady -h localhost -p 5432 -U jaldrishti_user -d jaldrishti 2>$null
        if ($LASTEXITCODE -eq 0) {
            $pgRunning = $true
            break
        }
    }

    if (-not $pgRunning) {
        Write-Host "FAILED"
        Write-Host "ERROR: PostgreSQL failed to start. Inspect $pgLog for details."
        exit 1
    }
    Write-Host "OK"
}

# 2. Redis (Port 6379)
Write-Host -NoNewline "Starting Redis... "
$redisStatus = Test-PortInUse -Port 6379
$redisRunning = $false

if ($redisStatus.InUse) {
    Write-Host "OK"
    $redisRunning = $true
} else {
    $redisLog = Join-Path $LogDir "redis.log"
    $redisArgs = @($RedisConf)
    $redisProc = Start-Process -FilePath $RedisBin -ArgumentList $redisArgs `
        -RedirectStandardOutput $redisLog -RedirectStandardError (Join-Path $LogDir "redis_err.log") `
        -PassThru -WindowStyle Hidden

    $redisProc.Id | Out-File -FilePath (Join-Path $LogDir "redis.pid") -Force -Encoding ascii

    $timeout = 10
    while ($timeout -gt 0) {
        Start-Sleep -Seconds 1
        $timeout--
        $pong = & $RedisCli ping 2>$null
        if ($pong -like "*PONG*") {
            $redisRunning = $true
            break
        }
    }

    if (-not $redisRunning) {
        Write-Host "FAILED"
        Write-Host "ERROR: Redis failed to start. Inspect $redisLog for details."
        exit 1
    }
    Write-Host "OK"
}

# 3. AI Service (Port 8010)
Write-Host -NoNewline "Starting AI service... "
$aiStatus = Test-PortInUse -Port 8010
$aiRunning = $false

if ($aiStatus.InUse) {
    Write-Host "OK"
    $aiRunning = $true
} else {
    $aiDir = Join-Path $RootDir "ai"
    $aiLog = Join-Path $LogDir "ai.log"
    $aiErrLog = Join-Path $LogDir "ai_err.log"

    $aiProc = Start-Process -FilePath $Python `
        -ArgumentList "-u", "-m", "uvicorn", "service.app:app", "--host", "127.0.0.1", "--port", "8010", "--app-dir", $aiDir `
        -WorkingDirectory $aiDir `
        -RedirectStandardOutput $aiLog -RedirectStandardError $aiErrLog `
        -PassThru -WindowStyle Hidden

    $aiProc.Id | Out-File -FilePath (Join-Path $LogDir "ai.pid") -Force -Encoding ascii

    $timeout = 25
    while ($timeout -gt 0) {
        Start-Sleep -Seconds 1
        $timeout--
        try {
            $health = Invoke-RestMethod -Uri "http://127.0.0.1:8010/health" -TimeoutSec 2 -ErrorAction Stop
            if ($health.status -eq "ok") {
                $aiRunning = $true
                break
            }
        } catch {}
    }

    if (-not $aiRunning) {
        Write-Host "FAILED"
        Write-Host "ERROR: AI service failed to start. Inspect $aiErrLog for details."
        exit 1
    }
    Write-Host "OK"
}

# 4. Backend (Port 8000)
Write-Host -NoNewline "Starting backend... "
$backendStatus = Test-PortInUse -Port 8000
$backendRunning = $false

if ($backendStatus.InUse) {
    Write-Host "OK"
    $backendRunning = $true
} else {
    $backendDir = Join-Path $RootDir "backend"
    $backendLog = Join-Path $LogDir "backend.log"
    $backendErrLog = Join-Path $LogDir "backend_err.log"

    $backendProc = Start-Process -FilePath $Python `
        -ArgumentList "-u", "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000", "--app-dir", $backendDir `
        -WorkingDirectory $backendDir `
        -RedirectStandardOutput $backendLog -RedirectStandardError $backendErrLog `
        -PassThru -WindowStyle Hidden

    $backendProc.Id | Out-File -FilePath (Join-Path $LogDir "backend.pid") -Force -Encoding ascii

    $timeout = 25
    while ($timeout -gt 0) {
        Start-Sleep -Seconds 1
        $timeout--
        try {
            $health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/health" -TimeoutSec 2 -ErrorAction Stop
            if ($health.status -eq "ok") {
                $backendRunning = $true
                break
            }
        } catch {}
    }

    if (-not $backendRunning) {
        Write-Host "FAILED"
        Write-Host "ERROR: Backend failed to start. Inspect $backendErrLog for details."
        exit 1
    }
    Write-Host "OK"
}

# 5. Frontend (Port 3000)
Write-Host -NoNewline "Starting frontend... "
$frontendStatus = Test-PortInUse -Port 3000
$frontendRunning = $false

if ($frontendStatus.InUse) {
    Write-Host "OK"
    $frontendRunning = $true
} else {
    $frontendDir = Join-Path $RootDir "frontend"
    $frontendLog = Join-Path $LogDir "frontend.log"
    $frontendErrLog = Join-Path $LogDir "frontend_err.log"

    $frontendProc = Start-Process -FilePath "cmd.exe" `
        -ArgumentList "/c", "npm start" `
        -WorkingDirectory $frontendDir `
        -RedirectStandardOutput $frontendLog -RedirectStandardError $frontendErrLog `
        -PassThru -WindowStyle Hidden

    $frontendProc.Id | Out-File -FilePath (Join-Path $LogDir "frontend.pid") -Force -Encoding ascii

    $timeout = 35
    while ($timeout -gt 0) {
        Start-Sleep -Seconds 2
        $timeout -= 2
        try {
            $resp = Invoke-WebRequest -Uri "http://127.0.0.1:3000" -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
            if ($resp.StatusCode -eq 200) {
                $frontendRunning = $true
                break
            }
        } catch {}
    }

    if (-not $frontendRunning) {
        if ($frontendProc -and -not $frontendProc.HasExited) {
            $frontendRunning = $true
        } else {
            Write-Host "FAILED"
            Write-Host "ERROR: Frontend failed to start. Inspect $frontendErrLog for details."
            exit 1
        }
    }
    Write-Host "OK"
}

Write-Host ""
Write-Host "JalDrishti is running."
Write-Host ""
Write-Host "Dashboard: http://localhost:3000"
Write-Host "Backend: http://localhost:8000/docs"
Write-Host "AI service: http://localhost:8010/docs"
Write-Host ""
Write-Host "To stop: .\stop-jaldrishti.ps1"

if ($Wait) {
    try {
        while ($true) {
            Start-Sleep -Seconds 2
        }
    } finally {
        & (Join-Path $RootDir "stop-jaldrishti.ps1")
    }
}
