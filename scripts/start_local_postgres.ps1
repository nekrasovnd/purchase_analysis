param(
    [int]$Port = 55432
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$PgCtl = Join-Path $RepoRoot ".local\pgsql16\pgsql\bin\pg_ctl.exe"
$DataDir = Join-Path $RepoRoot ".local\pgdata"
$LogPath = Join-Path $RepoRoot ".local\pg.log"

if (-not (Test-Path $PgCtl)) {
    throw "PostgreSQL binaries not found: $PgCtl"
}
if (-not (Test-Path $DataDir)) {
    throw "PostgreSQL data directory not found: $DataDir"
}

& $PgCtl -D $DataDir status *> $null
if ($LASTEXITCODE -eq 0) {
    Write-Host "PostgreSQL already running on 127.0.0.1:$Port"
    exit 0
}

& $PgCtl -D $DataDir -l $LogPath -o "-p $Port -h 127.0.0.1" start
if ($LASTEXITCODE -ne 0) {
    throw "Failed to start local PostgreSQL."
}

Write-Host "PostgreSQL started on 127.0.0.1:$Port"
