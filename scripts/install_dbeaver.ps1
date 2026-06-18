param()

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$DownloadDir = Join-Path $RepoRoot ".local\downloads"
$AppsDir = Join-Path $RepoRoot ".local\apps"
$WorkspaceDir = Join-Path $RepoRoot ".local\dbeaver-workspace"
$ZipPath = Join-Path $DownloadDir "dbeaver-ce-26.1.0-windows-x86_64.zip"
$ChecksumPath = Join-Path $DownloadDir "dbeaver-ce-26.1.0-windows-x86_64.zip.sha256"
$InstallDir = Join-Path $AppsDir "dbeaver"
$DBeaverUrl = "https://dbeaver.io/files/26.1.0/dbeaver-ce-26.1.0-windows-x86_64.zip"
$ChecksumUrl = "https://downloads.dbeaver.net/community/26.1.0/checksum/dbeaver-ce-26.1.0-windows-x86_64.zip.sha256"
$DriversRoot = Join-Path $env:APPDATA "DBeaverData\drivers\maven\maven-central"

function Download-MavenJar {
    param(
        [string]$Group,
        [string]$Artifact,
        [string]$Version
    )

    $GroupPath = $Group -replace "\.", "/"
    $TargetDir = Join-Path $DriversRoot $Group
    $FileName = "$Artifact-$Version.jar"
    $TargetPath = Join-Path $TargetDir $FileName
    if (Test-Path $TargetPath) {
        return
    }
    New-Item -ItemType Directory -Force -Path $TargetDir | Out-Null
    $Url = "https://repo1.maven.org/maven2/$GroupPath/$Artifact/$Version/$FileName"
    Write-Host "Downloading JDBC dependency $FileName..."
    curl.exe -L --fail --output $TargetPath $Url | Out-Null
}

New-Item -ItemType Directory -Force -Path $DownloadDir, $AppsDir, $WorkspaceDir | Out-Null

if (-not (Test-Path $ZipPath)) {
    Write-Host "Downloading DBeaver portable archive..."
    curl.exe -L --fail --output $ZipPath $DBeaverUrl | Out-Null
}
if (-not (Test-Path $ChecksumPath)) {
    curl.exe -L --fail --output $ChecksumPath $ChecksumUrl | Out-Null
}

$ExpectedHash = (Get-Content $ChecksumPath).Split()[0].ToLower()
$ActualHash = (Get-FileHash $ZipPath -Algorithm SHA256).Hash.ToLower()
if ($ExpectedHash -ne $ActualHash) {
    throw "DBeaver archive checksum mismatch."
}

if (-not (Test-Path (Join-Path $InstallDir "dbeaver.exe"))) {
    if (Test-Path $InstallDir) {
        Remove-Item -LiteralPath $InstallDir -Recurse -Force
    }
    Write-Host "Extracting DBeaver portable archive..."
    Expand-Archive -LiteralPath $ZipPath -DestinationPath $AppsDir -Force
}

$JdbcDeps = @(
    @{ Group = "org.postgresql"; Artifact = "postgresql"; Version = "42.7.11" },
    @{ Group = "net.postgis"; Artifact = "postgis-jdbc"; Version = "2.5.0" },
    @{ Group = "net.postgis"; Artifact = "postgis-geometry"; Version = "2.5.0" },
    @{ Group = "com.github.waffle"; Artifact = "waffle-jna"; Version = "3.5.1" },
    @{ Group = "net.java.dev.jna"; Artifact = "jna"; Version = "5.16.0" },
    @{ Group = "net.java.dev.jna"; Artifact = "jna-platform"; Version = "5.16.0" },
    @{ Group = "org.slf4j"; Artifact = "jcl-over-slf4j"; Version = "2.0.16" },
    @{ Group = "org.slf4j"; Artifact = "slf4j-api"; Version = "2.0.16" },
    @{ Group = "com.github.ben-manes.caffeine"; Artifact = "caffeine"; Version = "3.1.8" },
    @{ Group = "org.checkerframework"; Artifact = "checker-qual"; Version = "3.37.0" },
    @{ Group = "org.checkerframework"; Artifact = "checker-qual"; Version = "3.48.3" },
    @{ Group = "com.google.errorprone"; Artifact = "error_prone_annotations"; Version = "2.21.1" },
    @{ Group = "net.bytebuddy"; Artifact = "byte-buddy"; Version = "1.15.11" },
    @{ Group = "net.bytebuddy"; Artifact = "byte-buddy-agent"; Version = "1.15.11" }
)

foreach ($Dep in $JdbcDeps) {
    Download-MavenJar -Group $Dep.Group -Artifact $Dep.Artifact -Version $Dep.Version
}

Write-Host "DBeaver portable is ready in $InstallDir"
