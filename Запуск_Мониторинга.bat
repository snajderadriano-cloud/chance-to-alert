@echo off
chcp 65001 >nul
title Chance to Alert - Live Radar
echo ========================================================
echo        CHANCE TO ALERT — ЖИВОЙ МОНИТОРИНГ
echo ========================================================
echo.
echo [1/2] Запуск локального API сервера (доступен по сети для телефона)...
start "Chance to Alert API" /min cmd /c "python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"
timeout /t 2 /nobreak >nul

echo [2/2] Запуск слушателя Telegram...
echo.
echo ========================================================
echo  Веб-интерфейс для ПК:      http://localhost:8000
echo  Для входа с ТЕЛЕФОНА:      http://192.168.1.114:8000
echo ========================================================
echo.
python -m app.ingestion.telegram_live
pause
