@echo off
chcp 65001 >nul
title Разрешить доступ в домашней сети
echo ========================================================
echo   ОТКРЫТИЕ ПОРТА 8000 ДЛЯ ДОМАШНЕГО WI-FI
echo ========================================================
echo.
echo Добавление правила в Брандмауэр Windows (требуются права администратора)...
netsh advfirewall firewall add rule name="Chance to Alert Port 8000" dir=in action=allow protocol=TCP localport=8000 profile=any
echo.
echo Готово! Теперь адрес http://192.168.1.114:8000 будет открываться по Wi-Fi.
echo.
pause
