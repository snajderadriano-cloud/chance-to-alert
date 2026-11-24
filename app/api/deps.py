"""Dependency injection container and application state."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional
from app.config import AppConfig, get_config
from app.domain.entities import ThreatSignal
from app.learning.calibration_engine import CalibrationEngine
from app.processing.ad_filter import ContentFilter
from app.processing.school_analyzer import SchoolRemoteAnalyzer
from app.processing.threat_parser import ThreatParser
from app.services.ai_copilot import TacticalAICopilot
from app.services.attendance_service import AttendanceService
from app.services.broadcaster import BroadcasterService
from app.services.probability_service import ProbabilityCalculationService
from app.services.tracking_service import ThreatTrackingService
from app.storage.sqlite import SQLiteStorage


class AppState:
    """Central container for stateful application dependencies."""

    def __init__(self, config: Optional[AppConfig] = None) -> None:
        self.config = config or get_config()
        db_path = os.environ.get("ALERT_DB_PATH", str(Path(__file__).resolve().parent.parent.parent / "data" / "alerts.db"))
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.storage = SQLiteStorage(db_path=db_path)
        self.learner = CalibrationEngine(self.storage)
        self.attendance = AttendanceService(self.storage)
        self.ai_copilot = TacticalAICopilot()
        self.tracker = ThreatTrackingService()
        self.broadcaster = BroadcasterService()
        self.content_filter = ContentFilter()
        self.parser = ThreatParser(content_filter=self.content_filter)
        self.prob_service = ProbabilityCalculationService(config=self.config)
        self.school_analyzer = SchoolRemoteAnalyzer()
        self.active_signals: List[ThreatSignal] = []
        self.history: List[Dict] = [
            {
                "event_id": "init_1",
                "threat_type": "CLEAR",
                "quantity": 0,
                "raw_text": "По югу и Одесской области обстановка спокойная. Активных пусков Шахедов не зафиксировано.",
                "source_channel": "@vanek_nikolaev",
                "timestamp": "07:12:00",
            },
            {
                "event_id": "init_2",
                "threat_type": "STATUS",
                "quantity": 0,
                "raw_text": "Радіолокаційний моніторинг сектору Одещина / Таїрова активний. Ефір чистий.",
                "source_channel": "НЕПТУН",
                "timestamp": "07:05:00",
            },
            {
                "event_id": "init_3",
                "threat_type": "MUNICIPAL",
                "quantity": 0,
                "raw_text": "Одеський ліцей «Гармонія» та заклади освіти міста працюють за очним графіком. Сховища чергують.",
                "source_channel": "@dep_osvity",
                "timestamp": "06:45:00",
            },
            {
                "event_id": "init_4",
                "threat_type": "MILITARY",
                "quantity": 0,
                "raw_text": "Повітряний простір України під контролем ППО. Загрози по балістиці та крилатим ракетам немає.",
                "source_channel": "@kpszsu",
                "timestamp": "06:30:00",
            },
        ]


_state: Optional[AppState] = None


def get_app_state() -> AppState:
    """Retrieve or initialize singleton AppState."""
    global _state
    if _state is None:
        _state = AppState()
    return _state
