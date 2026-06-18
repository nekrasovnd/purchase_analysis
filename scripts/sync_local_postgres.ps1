param(
    [int]$Port = 55432,
    [string]$Database = "purchase_analysis",
    [string]$User = "postgres"
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$StartScript = Join-Path $PSScriptRoot "start_local_postgres.ps1"

& $StartScript -Port $Port

Push-Location $RepoRoot
try {
    $env:PYTHONPATH = "src"
    python -m purchase_analysis.cli sync-postgres --dsn "postgresql://$User@127.0.0.1:$Port/$Database"
    if ($LASTEXITCODE -ne 0) {
        throw "sync-postgres failed."
    }
}
finally {
    Pop-Location
}
