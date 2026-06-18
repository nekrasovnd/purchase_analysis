@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop_local_postgres.ps1" %*
