import asyncio
from pathlib import Path
from telethon import TelegramClient

BASE = Path(__file__).resolve().parent.parent

def load_env():
    cfg = {}
    env = BASE / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                cfg[k.strip()] = v.strip()
    return cfg

async def main():
    env = load_env()
    client = TelegramClient(str(BASE / 'data' / 'telegram'), int(env['TELEGRAM_API_ID']), env['TELEGRAM_API_HASH'])
    await client.connect()
    for ch in ['@vanek_nikolaev', '@Shturval_media', '@raketa_trevoga', '@odessa_inform']:
        try:
            ent = await client.get_entity(ch)
            msgs = await client.get_messages(ent, limit=2)
            print(f"=== {ent.title} ({ch}) ===")
            for m in msgs:
                if m.raw_text:
                    ts = m.date.strftime("%H:%M")
                    clean = m.raw_text.replace('\n', ' ')[:110]
                    print(f"  [{ts}] {clean}")
        except Exception as e:
            print(ch, e)
    await client.disconnect()

asyncio.run(main())
