param(
    [switch]$OpenDBeaver
)

$ErrorActionPreference = "Stop"

$InstallPostgres = Join-Path $PSScriptRoot "install_local_postgres.ps1"
$SyncPostgres = Join-Path $PSScriptRoot "sync_local_postgres.ps1"
$InstallDBeaver = Join-Path $PSScriptRoot "install_dbeaver.ps1"
$OpenDBeaverCmd = Join-Path $PSScriptRoot "open_dbeaver_purchase_analysis.cmd"

& $InstallPostgres
& $SyncPostgres
& $InstallDBeaver

if ($OpenDBeaver) {
    cmd /c $OpenDBeaverCmd
}

Write-Host "Local PostgreSQL + curated load + DBeaver are ready."
