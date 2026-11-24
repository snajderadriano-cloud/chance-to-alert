"""Auto-join all monitored radar channels via our authorized Telethon session."""
import asyncio, sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from telethon import TelegramClient
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import ImportChatInviteRequest
from telethon.errors import UserAlreadyParticipantError, InviteHashExpiredError
import yaml

def load_env():
    cfg = {}
    for line in (BASE / ".env").read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            cfg[k.strip()] = v.strip()
    return cfg

async def main():
    env = load_env()
    client = TelegramClient(str(BASE / "data" / "telegram"), int(env["TELEGRAM_API_ID"]), env["TELEGRAM_API_HASH"])
    await client.connect()
    if not await client.is_user_authorized():
        print("Not authorized!"); return

    with open(BASE / "config" / "channels.yaml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    print("🔗 Подключаюсь к каналам...\n")
    for ch in cfg["channels"]:
        username = ch.get("username", "")
        invite_link = ch.get("invite_link", "")
        name = ch["name"]

        if not username and not invite_link:
            continue

        try:
            if invite_link:
                # Private channel via invite hash
                try:
                    await client(ImportChatInviteRequest(invite_link))
                    print(f"  ✅ Вступил в приватный канал: {name}")
                except UserAlreadyParticipantError:
                    print(f"  ✔️ Уже состою: {name}")
                except InviteHashExpiredError:
                    print(f"  ⚠️  Инвайт-ссылка устарела: {name}")
            else:
                entity = await client.get_entity(f"@{username}")
                await client(JoinChannelRequest(entity))
                print(f"  ✅ Подписан: @{username} — {name}")
        except UserAlreadyParticipantError:
            print(f"  ✔️ Уже подписан: @{username} — {name}")
        except Exception as e:
            err = str(e)[:60]
            print(f"  ⚠️  @{username} — {err}")

        await asyncio.sleep(1.5)  # Rate limit: be polite to Telegram API

    print("\n✅ Готово! Все каналы подключены.")
    await client.disconnect()

asyncio.run(main())
