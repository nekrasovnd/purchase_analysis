@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_local_postgres.ps1" %*
