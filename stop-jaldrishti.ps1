[CmdletBinding()]
param()

$ErrorActionPreference = "Continue"
$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RootDir

$LogDir = Join-Path $RootDir "logs"

Write-Host "Stopping JalDrishti..."
Write-Host ""

function Stop-TrackedProcess {
    param(
        [string]$PidFileName,
        [int]$Port
    )

    $pidFile = Join-Path $LogDir $PidFileName
    if (Test-Path $pidFile) {
        $rawId = (Get-Content $pidFile -Raw -ErrorAction SilentlyContinue)
        if ($null -ne $rawId) {
            $rawId = $rawId.Trim()
            if ($rawId -match '^\d+$') {
                $id = [int]$rawId
                & taskkill.exe /PID $id /T /F 2>$null | Out-Null
            }
        }
        Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
    }

    if ($Port -gt 0) {
        $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        if ($null -ne $conn) {
            foreach ($c in $conn) {
                $procId = $c.OwningProcess
                if ($procId -gt 4) {
                    & taskkill.exe /PID $procId /T /F 2>$null | Out-Null
                }
            }
        }
    }
}

# 1. Stop Frontend
Stop-TrackedProcess -PidFileName "frontend.pid" -Port 3000
Write-Host "Frontend stopped."

# 2. Stop Backend
Stop-TrackedProcess -PidFileName "backend.pid" -Port 8000
Write-Host "Backend stopped."

# 3. Stop AI Service
Stop-TrackedProcess -PidFileName "ai.pid" -Port 8010
Write-Host "AI service stopped."

# 4. Stop Redis
$redisCli = Join-Path $RootDir ".local_services\redis\redis-cli.exe"
if (Test-Path $redisCli) {
    & $redisCli shutdown 2>$null | Out-Null
}
Stop-TrackedProcess -PidFileName "redis.pid" -Port 6379
Write-Host "Redis stopped."

# 5. Stop PostgreSQL
$pgCtl  = Join-Path $RootDir ".local_services\pgsql\bin\pg_ctl.exe"
$pgData = Join-Path $RootDir ".local_services\pgsql\data"
if ((Test-Path $pgCtl) -and (Test-Path $pgData)) {
    & $pgCtl -D $pgData stop -m fast 2>$null | Out-Null
}
Stop-TrackedProcess -PidFileName "pgsql.pid" -Port 5432
if (Test-Path $pgData) {
    $postmasterPid = Join-Path $pgData "postmaster.pid"
    if (Test-Path $postmasterPid) {
        Remove-Item $postmasterPid -Force -ErrorAction SilentlyContinue
    }
}
Write-Host "PostgreSQL stopped."

Write-Host ""
Write-Host "JalDrishti stopped."
