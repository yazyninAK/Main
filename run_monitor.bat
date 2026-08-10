@echo off
REM Запускает проверку объявлений. Используется Планировщиком заданий Windows.
REM %~dp0 - папка, где лежит этот .bat файл (корень репозитория).
cd /d "%~dp0"
python scripts\main.py >> monitor_log.txt 2>&1
