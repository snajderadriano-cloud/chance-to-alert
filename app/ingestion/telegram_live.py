"""Real-time Telegram Live Listener for Chance to Alert.App.

Connects to Telegram using the authenticated local session in data/telegram.session,
streams posts from monitored radar/monitoring/school channels, filters ads/spam,
evaluates threat probability for Таирова (Лицей «Гармония»), and pushes events to the API.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import sys
from typing import Dict, List, Optional, Set
import urllib.request
import yaml

from telethon import TelegramClient, events
from telethon.tl.types import Channel, Chat, PeerChannel

from app.domain.entities import GeoCoordinate, TargetPreset
from app.domain.enums import AlertLevel
from app.processing.ad_filter import ContentFilter
from app.processing.school_analyzer import SchoolRemoteAnalyzer
from app.processing.threat_parser import ThreatParser
from app.services.probability_service import ProbabilityCalculationService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("telegram_live")

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
SESSION_PATH = DATA_DIR / "telegram"
CHANNELS_CFG_PATH = BASE_DIR / "config" / "channels.yaml"
PRESETS_CFG_PATH = BASE_DIR / "config" / "presets_odesa.yaml"
API_BASE_URL = os.environ.get("ALERT_API_URL", "http://127.0.0.1:8000")


def load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


class TelegramLiveListener:
    def __init__(self, api_url: str = API_BASE_URL):
        self.api_url = api_url.rstrip("/")
        self.content_filter = ContentFilter()
        self.parser = ThreatParser(content_filter=self.content_filter)
        self.school_analyzer = SchoolRemoteAnalyzer()
        self.prob_service = ProbabilityCalculationService()

        # Load target preset for Tairova / Harmoniya Lyceum
        presets = load_yaml(PRESETS_CFG_PATH).get("presets", {})
        tairovo_data = presets.get("odesa_tairovo", {})
        centroid = tairovo_data.get("centroid", {"lat": 46.4020, "lon": 30.7180})
        self.target_preset = TargetPreset(
            name=tairovo_data.get("name", "Таїрова / Ліцей Гармонія"),
            centroid=GeoCoordinate(lat=centroid["lat"], lon=centroid["lon"]),
            radius_km=float(tairovo_data.get("radius_km", 7.0)),
            warning_radius_km=float(tairovo_data.get("warning_radius_km", 50.0)),
        )

        # Monitored channels mapping
        self.channels_cfg = load_yaml(CHANNELS_CFG_PATH).get("channels", [])
        self.channel_weights: Dict[str, float] = {}
        self.channel_types: Dict[str, str] = {}
        self.monitored_usernames: Set[str] = set()

        for ch in self.channels_cfg:
            uname = ch.get("username", "").lower().lstrip("@")
            if uname:
                self.monitored_usernames.add(uname)
                self.channel_weights[uname] = float(ch.get("reliability_weight", 0.8))
                self.channel_types[uname] = ch.get("channel_type", "LOCAL_MONITOR")

        self.client: Optional[TelegramClient] = None

    def _push_to_api(self, text: str, source: str) -> None:
        """Forward raw event to backend API if running."""
        try:
            url = f"{self.api_url}/api/v1/simulate"
            payload = json.dumps({"text": text, "source": source}).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                pass
        except Exception:
            # API might be offline; local processing continues seamlessly
            pass

    async def handle_message(self, event: events.NewMessage.Event) -> None:
        """Handle incoming post from a channel."""
        text = event.raw_text or ""
        if not text.strip():
            return

        chat = await event.get_chat()
        username = (getattr(chat, "username", None) or "").lower()
        title = getattr(chat, "title", "Неизвестный канал")
        channel_ref = f"@{username}" if username else title

        # Check if chat is in monitored list (or match by title)
        is_monitored = username in self.monitored_usernames
        if not is_monitored:
            # If not in explicit list, check if user joined it or title matches
            is_monitored = True  # process all subscribed channels for safety

        ch_type = self.channel_types.get(username, "LOCAL_MONITOR")
        ch_weight = self.channel_weights.get(username, 0.85)

        # 1. Filter Spam / Casino / Ads
        filter_result = self.content_filter.filter_post(text, channel_username=username)
        if not filter_result.is_threat_relevant:
            reason = filter_result.rejection_reason or "нерелевантно"
            print(f"\n[РЕКЛАМА/ШУМ] [FILTERED]  [{channel_ref}] Отфильтровано: {reason}")
            return

        # 2. Analyze School & Remote Study Status
        if ch_type in ("EDUCATION_OFFICIAL", "MUNICIPAL_UTILITIES") or "школ" in text.lower() or "дистант" in text.lower():
            school_res = self.school_analyzer.analyze_post(text, channel=channel_ref)
            if school_res.is_remote:
                print("\n" + "[EDUCATION]" * 30)
                print(f" [ДИСТАНЦИОНКА] [SCHOOL] {school_res.headline}")
                print(f" Школа/Район: {school_res.target_school}")
                print(f" Вероятность онлайна: {school_res.remote_probability_percent}%")
                print(f" Источник: {channel_ref}")
                print(f" Цитата: {school_res.official_quote}")
                print("[EDUCATION]" * 30 + "\n")
                self._push_to_api(text, channel_ref)
                return

        # 3. Parse Military Threats (Shahed, Ballistics, Cruise Missiles, etc.)
        signals = self.parser.parse(text, channel=channel_ref)
        if not signals:
            return

        # Push to backend API
        self._push_to_api(text, channel_ref)

        # 4. Compute probability for Tairova / Harmoniya Lyceum
        prob_result = self.prob_service.calculate(
            signals=signals,
            preset_name="odesa_tairovo",
            reference_time=datetime.now(timezone.utc),
        )

        alert_color = "[ALERT: GREEN]"
        if prob_result.alert_level == AlertLevel.YELLOW:
            alert_color = "[ALERT: YELLOW]"
        elif prob_result.alert_level == AlertLevel.ORANGE:
            alert_color = "[ALERT: ORANGE]"
        elif prob_result.alert_level == AlertLevel.RED:
            alert_color = "[ALERT: RED]"

        print("\n" + "=" * 65)
        print(f" {alert_color} [ОБНАРУЖЕНА УГРОЗА В ПОТОКЕ] Источник: {channel_ref}")
        print(f" Уровень опасности: {prob_result.alert_level.value} | Шанс тревоги для Таирова: {prob_result.probability_percent}%")
        if prob_result.estimated_time_to_impact_minutes:
            print(f" Оценочное время подлёта (ETA): ~{prob_result.estimated_time_to_impact_minutes} мин")

        for sig in signals:
            loc_str = ", ".join(sig.detected_locations) if sig.detected_locations else "Не указано"
            bearing_str = f", курс: {sig.trajectory.heading_degrees}°" if sig.trajectory and sig.trajectory.heading_degrees else ""
            print(f"   • Тип: {sig.threat_type.value} | Локация: {loc_str}{bearing_str}")

        print(f" Сводка: {prob_result.summary}")
        print("=" * 65 + "\n")

    async def start(self) -> None:
        """Start streaming listener."""
        session_str = os.environ.get("TELEGRAM_STRING_SESSION")
        if not session_str and (DATA_DIR / "telegram_string_session.txt").exists():
            try:
                with open(DATA_DIR / "telegram_string_session.txt", "r", encoding="utf-8") as f:
                    session_str = f.read().strip()
            except Exception:
                pass

        session_target = None
        if session_str:
            from telethon.sessions import StringSession
            session_target = StringSession(session_str)
        else:
            session_file = SESSION_PATH.with_suffix(".session")
            if session_file.exists():
                session_target = str(SESSION_PATH)

        if not session_target:
            print("\n[ERROR] Файл сессии не найден!")
            print("Сначала запустите скрипт авторизации: python login_telegram.py")
            print("или дважды кликните по 'Войти_в_Telegram.bat'\n")
            return

        env_file = BASE_DIR / ".env"
        api_id = 39209465
        api_hash = ""
        if env_file.exists():
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("TELEGRAM_API_ID="):
                        api_id = int(line.split("=", 1)[1].strip())
                    elif line.startswith("TELEGRAM_API_HASH="):
                        api_hash = line.split("=", 1)[1].strip()

        if not api_hash:
            api_hash = os.environ.get("TELEGRAM_API_HASH", "")

        if not api_hash:
            print("[ERROR] TELEGRAM_API_HASH не задан в .env файле!")
            print("Запустите python login_telegram.py для настройки.")
            return

        print("=" * 65)
        print(" [RADAR]  CHANCE TO ALERT — ЖИВОЙ ПРИЁМНИК TELEGRAM ЗАПУЩЕН")
        print(f" Целевой район: Таирова / Лицей «Гармония» (Одесса)")
        print(f" Отслеживаемых каналов: {len(self.monitored_usernames)}")
        print(" Фильтрация рекламы и казино: АКТИВНА")
        print(" Радар тревог и дистанционки: СЛУШАЕТ...")
        print("=" * 65)

        self.client = TelegramClient(session_target, api_id, api_hash)
        await self.client.connect()

        if not await self.client.is_user_authorized():
            print("[ERROR] Сессия не авторизована! Запустите: python login_telegram.py")
            await self.client.disconnect()
            return

        me = await self.client.get_me()
        print(f"[OK] Подключено через Telegram-аккаунт: {me.first_name} (@{me.username or 'id_' + str(me.id)})")
        print("Ожидание новых сообщений из каналов... (Нажмите Ctrl+C для выхода)\n")

        @self.client.on(events.NewMessage)
        async def on_new_message(event):
            await self.handle_message(event)

        await self.client.run_until_disconnected()


if __name__ == "__main__":
    listener = TelegramLiveListener()
    try:
        asyncio.run(listener.start())
    except KeyboardInterrupt:
        print("\n[STOPPED] Приёмник остановлен пользователем.")
