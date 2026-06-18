@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_local_postgres.ps1" %*
