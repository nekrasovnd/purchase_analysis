@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "REPO_ROOT=%%~fI"
set "DBeaverExe=%REPO_ROOT%\.local\apps\dbeaver\dbeaver.exe"
set "Workspace=%REPO_ROOT%\.local\dbeaver-workspace"
set "ExploreSql=%REPO_ROOT%\db\queries\001_explore.sql"
set "RecentLotsSql=%REPO_ROOT%\db\queries\003_recent_lots.sql"
set "PricedLotsSql=%REPO_ROOT%\db\queries\004_priced_lots.sql"
set "EntityFocusSql=%REPO_ROOT%\db\queries\005_entity_focus_template.sql"
set "AnomaliesSql=%REPO_ROOT%\db\queries\006_anomalies.sql"
set "DocumentsSql=%REPO_ROOT%\db\queries\007_documents.sql"

if not exist "%DBeaverExe%" (
  echo DBeaver not found: %DBeaverExe%
  exit /b 1
)

call "%SCRIPT_DIR%start_local_postgres.cmd"
if errorlevel 1 exit /b 1

start "" "%DBeaverExe%" ^
  -newInstance ^
  -reuseWorkspace ^
  -nosplash ^
  -data "%Workspace%" ^
  -con "driver=postgresql|host=127.0.0.1|port=55432|database=purchase_analysis|user=postgres|password=|savePassword=true|name=purchase_analysis|save=true|connect=true|openConsole=true" ^
  -f "%ExploreSql%" ^
  -f "%RecentLotsSql%" ^
  -f "%PricedLotsSql%" ^
  -f "%EntityFocusSql%" ^
  -f "%AnomaliesSql%" ^
  -f "%DocumentsSql%"
