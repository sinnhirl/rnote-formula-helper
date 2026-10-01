@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 正在启动 Rnote 公式助手（调试模式，日志显示在此窗口；关闭窗口或 Ctrl+C 即退出）
echo.
".venv\Scripts\python.exe" app.py
echo.
echo 程序已退出，按任意键关闭窗口。
pause >nul
