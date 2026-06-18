param()

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$PgCtl = Join-Path $RepoRoot ".local\pgsql16\pgsql\bin\pg_ctl.exe"
$DataDir = Join-Path $RepoRoot ".local\pgdata"

if (-not (Test-Path $PgCtl)) {
    throw "PostgreSQL binaries not found: $PgCtl"
}
if (-not (Test-Path $DataDir)) {
    throw "PostgreSQL data directory not found: $DataDir"
}

& $PgCtl -D $DataDir status *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "PostgreSQL is already stopped."
    exit 0
}

& $PgCtl -D $DataDir stop
if ($LASTEXITCODE -ne 0) {
    throw "Failed to stop local PostgreSQL."
}

Write-Host "PostgreSQL stopped."
