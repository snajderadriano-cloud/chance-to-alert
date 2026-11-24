@echo off
chcp 65001 >nul
title Chance to Alert - Cloudflare Mobile Tunnel
echo ========================================================
echo     CHANCE TO ALERT — ДОСТУП С ТЕЛЕФОНА (CLOUDFLARE)
echo ========================================================
echo.
echo [1/3] Запуск локального API сервера...
start "Chance to Alert API" /min cmd /c "python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"
timeout /t 2 /nobreak >nul

echo [2/3] Запуск приёмника 17 Telegram-каналов...
start "Telegram Live Radar" /min cmd /c "python -m app.ingestion.telegram_live"

echo [3/3] Запуск защищённого туннеля Cloudflare...
echo.
echo ========================================================
echo  Сейчас ниже появится ВАША ПУБЛИЧНАЯ ССЫЛКА вида:
echo  https://xxxx-xxxx-xxxx.trycloudflare.com
echo.
echo  Откройте её на ТЕЛЕФОНЕ — всё работает 24/7!
echo ========================================================
echo.
cloudflared.exe tunnel --protocol http2 --url http://localhost:8000
pause
