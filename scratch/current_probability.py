"""Live probability check: grab recent posts from radar channels and score threat to Tairova."""
import asyncio, sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from telethon import TelegramClient
import yaml

def load_env():
    cfg = {}
    env = BASE / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                cfg[k.strip()] = v.strip()
    return cfg

RADAR_CHANNELS = [
    "@raketa_trevoga",
    "@odessa_inform",
    "@vanek_nikolaev",
    "@war_monitor",
    "@Shturval_media",
    "@kpszsu",
]

async def main():
    env = load_env()
    api_id = int(env["TELEGRAM_API_ID"])
    api_hash = env["TELEGRAM_API_HASH"]
    client = TelegramClient(str(BASE / "data" / "telegram"), api_id, api_hash)
    await client.connect()

    if not await client.is_user_authorized():
        print("Not authorized!"); return

    from app.processing.ad_filter import ContentFilter
    from app.processing.threat_parser import ThreatParser
    from app.services.probability_service import ProbabilityCalculationService
    from app.domain.entities import GeoCoordinate, TargetPreset

    filt = ContentFilter()
    parser = ThreatParser(content_filter=filt)
    prob_service = ProbabilityCalculationService()
    target = TargetPreset(
        name="Таїрова / Ліцей Гармонія",
        centroid=GeoCoordinate(lat=46.4020, lon=30.7180),
        radius_km=7.0,
        warning_radius_km=50.0,
    )

    all_signals = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=2)

    print(f"\n🔍 Читаю последние 2 часа из радарных каналов...\n")
    for ch_name in RADAR_CHANNELS:
        try:
            entity = await client.get_entity(ch_name)
        except Exception as e:
            print(f"  ⚠️  {ch_name} — не доступен: {e}")
            continue

        messages = await client.get_messages(entity, limit=20)
        ch_signals = []
        for m in messages:
            if not m.date or m.date < cutoff:
                continue
            txt = m.raw_text or ""
            if not txt.strip():
                continue
            fr = filt.filter_post(txt)
            if not fr.is_threat_relevant:
                continue
            sigs = parser.parse(txt)
            if sigs:
                ch_signals.extend(sigs)
                all_signals.extend(sigs)

        status = f"{len(ch_signals)} сигналов" if ch_signals else "тихо"
        print(f"  📡 {entity.title:35s} → {status}")

    print()
    now = datetime.now(timezone.utc)
    result = prob_service.calculate(
        signals=all_signals,
        preset_name="odesa_tairovo",
        reference_time=now,
    )

    color = {"GREEN":"🟢","YELLOW":"🟡","ORANGE":"🟠","RED":"🔴"}.get(result.alert_level.value, "⚪")
    print("=" * 55)
    print(f" {color} ШАНС ТРЕВОГИ ДЛЯ ТАИРОВОЙ ПРЯМО СЕЙЧАС: {result.probability_percent}%")
    print(f" Уровень: {result.alert_level.value}")
    if result.estimated_time_to_impact_minutes:
        print(f" ETA подлёта: ~{result.estimated_time_to_impact_minutes} мин")
    print(f" Активных сигналов учтено: {len(all_signals)}")
    print(f" Описание: {result.summary}")
    print("=" * 55)
    await client.disconnect()

asyncio.run(main())
