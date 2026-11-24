"""Interactive Telegram Authentication Script for Chance to Alert.App.

This script safely signs you in using Telethon and stores the session
locally in data/telegram.session (never committed, never shared).
"""

import asyncio
import getpass
import os
from pathlib import Path
import sys

from telethon import TelegramClient
from telethon.errors import (
    PasswordHashInvalidError,
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    PhoneNumberInvalidError,
    SessionPasswordNeededError,
)

DATA_DIR = Path(__file__).resolve().parent / "data"
SESSION_PATH = DATA_DIR / "telegram"
ENV_PATH = Path(__file__).resolve().parent / ".env"


def load_env():
    """Load existing .env values if available."""
    config = {}
    if ENV_PATH.exists():
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    config[k.strip()] = v.strip().strip("\"'")
    return config


def save_env(api_id: str, api_hash: str):
    """Save api credentials to .env file securely."""
    env = load_env()
    env["TELEGRAM_API_ID"] = api_id
    env["TELEGRAM_API_HASH"] = api_hash
    with open(ENV_PATH, "w", encoding="utf-8") as f:
        for k, v in env.items():
            f.write(f"{k}={v}\n")


async def main():
    print("=" * 65)
    print("      CHANCE TO ALERT — ВХОД В TELEGRAM (TELETHON CLIENT)")
    print("=" * 65)
    print("Все данные и сессия сохраняются ТОЛЬКО локально на твоём ПК.")
    print("Сессия пишется в папку data/telegram.session (в .gitignore).\n")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    env = load_env()

    saved_api_id = env.get("TELEGRAM_API_ID", "39209465")
    saved_api_hash = env.get("TELEGRAM_API_HASH", "")

    # Check if valid credentials are already saved in .env
    try:
        api_id_int = int(saved_api_id)
        has_valid_id = 1 <= api_id_int <= 2147483647
    except ValueError:
        has_valid_id = False
        api_id_int = 39209465

    has_valid_hash = bool(saved_api_hash and len(saved_api_hash) == 32)

    if has_valid_id and has_valid_hash:
        print(f"✔️ Ключи API загружены из .env:")
        print(f"   • App api_id:   {api_id_int}")
        print(f"   • App api_hash: {saved_api_hash[:4]}...{saved_api_hash[-4:]}")
        api_id = api_id_int
        api_hash = saved_api_hash
    else:
        # Prompt for API_ID with bounds check
        while True:
            prompt_def = str(api_id_int) if has_valid_id else "39209465"
            api_id_input = input(f"Введите Telegram App api_id [{prompt_def}]: ").strip()
            api_id_str = api_id_input if api_id_input else prompt_def
            try:
                val = int(api_id_str)
                if not (1 <= val <= 2147483647):
                    print(f"❌ Ошибка: {val} слишком большое число! Telegram api_id должен быть от 1 до 2147483647.")
                    print("Подсказка: на my.telegram.org это именно App api_id (например, 39209465), а не ваш ID пользователя.")
                    continue
                api_id = val
                break
            except ValueError:
                print("❌ Ошибка: API ID должен быть числом!")

        # Prompt for API_HASH
        prompt_hash = f"[{saved_api_hash[:4]}...{saved_api_hash[-4:]}]" if saved_api_hash else ""
        api_hash_input = input(f"Введите Telegram App api_hash {prompt_hash}: ").strip()
        api_hash = api_hash_input if api_hash_input else saved_api_hash

        if not api_hash or len(api_hash) < 20:
            print("❌ Ошибка: API HASH не может быть пустым.")
            sys.exit(1)

        save_env(str(api_id), api_hash)
        print("✔️ API ключи сохранены в .env\n")

    client = TelegramClient(str(SESSION_PATH), api_id, api_hash)
    await client.connect()

    if await client.is_user_authorized():
        me = await client.get_me()
        print(f"\n✅ ВЫ УЖЕ АВТОРИЗОВАНЫ как: {me.first_name} (@{me.username or 'без_юзернейма'}, ID: {me.id})")
        print(f"Файл сессии готов: {SESSION_PATH}.session")
        await client.disconnect()
        return

    # User not authorized - start login flow
    print()
    phone = input("Введите ваш номер телефона Telegram (+380XXXXXXXXX): ").strip()
    # Strip spaces, dashes, brackets
    import re as _re
    phone = _re.sub(r'[\s\-\(\)]', '', phone)
    if not phone.startswith("+"):
        # Ukrainian number without country code: 0XXXXXXXXX or XXXXXXXXX (9-10 digits)
        if phone.startswith("0") and len(phone) == 10:
            phone = "+380" + phone[1:]
        elif len(phone) == 9:
            phone = "+380" + phone
        else:
            phone = "+" + phone

    try:
        sent = await client.send_code_request(phone)
    except PhoneNumberInvalidError:
        print("❌ Неверный номер телефона. Проверьте правильность кода страны.")
        await client.disconnect()
        return
    except Exception as e:
        print(f"❌ Ошибка отправки кода: {e}")
        await client.disconnect()
        return

    print("📨 Код отправлен в ваше приложение Telegram!")
    code = input("Введите код подтверждения из Telegram: ").strip()

    try:
        await client.sign_in(phone=phone, code=code, phone_code_hash=sent.phone_code_hash)
    except SessionPasswordNeededError:
        print("\n🔒 Включена двухфакторная аутентификация (2FA Cloud Password).")
        password = getpass.getpass("Введите ваш облачный пароль 2FA: ")
        try:
            await client.sign_in(password=password)
        except PasswordHashInvalidError:
            print("❌ Неверный пароль 2FA.")
            await client.disconnect()
            return
    except PhoneCodeInvalidError:
        print("❌ Неверный код подтверждения!")
        await client.disconnect()
        return
    except PhoneCodeExpiredError:
        print("❌ Время действия кода истекло. Запустите скрипт заново.")
        await client.disconnect()
        return
    except Exception as e:
        print(f"❌ Ошибка входа: {e}")
        await client.disconnect()
        return

    me = await client.get_me()
    print("\n" + "=" * 65)
    print(f"🎉 УСПЕШНО! Вход выполнен под аккаунтом: {me.first_name} (@{me.username or 'без_юзернейма'})")
    print(f"Сессия сохранена в: {SESSION_PATH}.session")
    print("=" * 65)
    print("\nТеперь можно запускать 'Запуск_Мониторинга.bat'!")
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
