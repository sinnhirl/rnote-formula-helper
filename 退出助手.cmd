@echo off
chcp 65001 >nul
powershell -NoProfile -ExecutionPolicy Bypass -Command "$p = Get-Content '%~dp0.pid' -ErrorAction SilentlyContinue; if ($p -and (Get-Process -Id $p -ErrorAction SilentlyContinue)) { Stop-Process -Id $p -Force; Write-Host '已退出 Rnote 公式助手' } else { Write-Host '助手未在运行' }"
timeout /t 2 >nul
