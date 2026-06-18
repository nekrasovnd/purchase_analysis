param(
    [int]$Port = 55432,
    [string]$Database = "purchase_analysis",
    [string]$User = "postgres",
    [string]$Command = ""
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$StartScript = Join-Path $PSScriptRoot "start_local_postgres.ps1"
$Psql = Join-Path $RepoRoot ".local\pgsql16\pgsql\bin\psql.exe"

if (-not (Test-Path $Psql)) {
    throw "psql not found: $Psql"
}

& $StartScript -Port $Port

if ($Command) {
    & $Psql -h 127.0.0.1 -p $Port -U $User -d $Database -c $Command
}
else {
    & $Psql -h 127.0.0.1 -p $Port -U $User -d $Database
}
