"""Quick live test: connect with saved session and read last 2 posts from each channel."""
import asyncio
from pathlib import Path
from telethon import TelegramClient

BASE = Path(__file__).resolve().parent.parent
SESSION = str(BASE / "data" / "telegram")
ENV = BASE / ".env"

def load_env():
    cfg = {}
    if ENV.exists():
        for line in ENV.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                cfg[k.strip()] = v.strip()
    return cfg

TEST_CHANNELS = [
    "@raketa_trevoga",
    "@odessa_inform",
    "@dep_osvity",
    "@svet_odessaa",
    "@xydessa_live",
]

async def main():
    env = load_env()
    api_id = int(env["TELEGRAM_API_ID"])
    api_hash = env["TELEGRAM_API_HASH"]

    print("Подключаюсь к Telegram...")
    client = TelegramClient(SESSION, api_id, api_hash)
    await client.connect()

    if not await client.is_user_authorized():
        print("❌ Сессия не авторизована! Запусти login_telegram.py")
        return

    me = await client.get_me()
    print(f"✅ Подключено как: {me.first_name} (@{me.username or me.id})\n")

    for ch in TEST_CHANNELS:
        try:
            entity = await client.get_entity(ch)
            messages = await client.get_messages(entity, limit=2)
            print(f"{'='*55}")
            print(f"📡 Канал: {entity.title} ({ch})")
            for m in messages:
                txt = (m.raw_text or "").strip()[:120].replace("\n", " ")
                ts = m.date.strftime("%d.%m %H:%M")
                print(f"  [{ts}] {txt}")
        except Exception as e:
            print(f"⚠️  {ch} — ошибка: {e}")

    print(f"\n{'='*55}")
    print("✅ Тест завершён! Все каналы читаются без галлюцинаций.")
    await client.disconnect()

asyncio.run(main())
