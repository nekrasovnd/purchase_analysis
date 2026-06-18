@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0bootstrap_local_db.ps1" %*
