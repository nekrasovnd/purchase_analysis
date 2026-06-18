param(
    [int]$Port = 55432,
    [string]$Database = "purchase_analysis"
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$DownloadDir = Join-Path $RepoRoot ".local\downloads"
$InstallDir = Join-Path $RepoRoot ".local\pgsql16"
$DataDir = Join-Path $RepoRoot ".local\pgdata"
$ZipPath = Join-Path $DownloadDir "postgresql-16.14-2-windows-x64-binaries.zip"
$PostgresUrl = "https://sbp.enterprisedb.com/getfile.jsp?fileid=1260308"
$InitDb = Join-Path $InstallDir "pgsql\bin\initdb.exe"
$Createdb = Join-Path $InstallDir "pgsql\bin\createdb.exe"
$Psql = Join-Path $InstallDir "pgsql\bin\psql.exe"
$StartScript = Join-Path $PSScriptRoot "start_local_postgres.ps1"

New-Item -ItemType Directory -Force -Path $DownloadDir, $InstallDir | Out-Null

if (-not (Test-Path $InitDb)) {
    if (-not (Test-Path $ZipPath)) {
        Write-Host "Downloading PostgreSQL portable binaries..."
        curl.exe -L --fail --output $ZipPath $PostgresUrl | Out-Null
    }
    Write-Host "Extracting PostgreSQL portable binaries..."
    tar -xf $ZipPath -C $InstallDir
}

if (-not (Test-Path $InitDb)) {
    throw "PostgreSQL initdb.exe not found after extraction: $InitDb"
}

if (-not (Test-Path (Join-Path $DataDir "PG_VERSION"))) {
    Write-Host "Initializing PostgreSQL data directory..."
    & $InitDb -D $DataDir -U postgres -A trust --encoding=UTF8 --no-locale
    if ($LASTEXITCODE -ne 0) {
        throw "initdb failed."
    }
}

& $StartScript -Port $Port

$Exists = (& $Psql -h 127.0.0.1 -p $Port -U postgres -d postgres -tAc "select 1 from pg_database where datname = '$Database'").Trim()
if ($Exists -ne "1") {
    Write-Host "Creating database $Database..."
    & $Createdb -h 127.0.0.1 -p $Port -U postgres $Database
    if ($LASTEXITCODE -ne 0) {
        throw "createdb failed."
    }
}

Write-Host "Portable PostgreSQL is ready on 127.0.0.1:$Port / database $Database"
