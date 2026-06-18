@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0sync_local_postgres.ps1" %*
