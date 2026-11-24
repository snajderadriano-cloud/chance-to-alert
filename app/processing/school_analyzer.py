"""Analyzer for municipal school status and remote learning probability in Odesa."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional


class RemoteStudyStatus(str, Enum):
    OFFICIAL_REMOTE = "OFFICIAL_REMOTE"      # Confirmed official remote learning
    HIGH_RISK_REMOTE = "HIGH_RISK_REMOTE"    # High probability due to blackouts or overnight attacks
    NORMAL_IN_PERSON = "NORMAL_IN_PERSON"    # In-person classes operating normally
    UNKNOWN = "UNKNOWN"


@dataclass
class SchoolStatusResult:
    """Status of school operations and remote study prediction in Odesa."""
    is_remote: bool
    status: RemoteStudyStatus
    remote_probability_percent: int
    headline: str
    target_school: str = "Ліцей «Гармонія» (Таїрова)"
    district_focus: str = "Таїрова / Київський район"
    official_quote: Optional[str] = None
    source_channel: Optional[str] = None
    infrastructure_factors: List[str] = field(default_factory=list)
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "is_remote": self.is_remote,
            "status": self.status.value,
            "remote_probability_percent": self.remote_probability_percent,
            "headline": self.headline,
            "target_school": self.target_school,
            "district_focus": self.district_focus,
            "official_quote": self.official_quote,
            "source_channel": self.source_channel,
            "infrastructure_factors": list(self.infrastructure_factors),
            "updated_at": self.updated_at.isoformat(),
        }


class SchoolRemoteAnalyzer:
    """Analyzes posts from Department of Education and municipal utility channels."""

    # Explicit official remote learning announcements
    OFFICIAL_REMOTE_PATTERNS = [
        re.compile(r"\b(навчаються\s+дистанційно|дистанційн\w*\s+навчанн\w*|переходять\s+на\s+дистант)\b", re.I),
        re.compile(r"\b(школи\s+(?:будуть\s+)?навчатис\w*\s+дистанційно|освітній\s+процес\s+дистанційно)\b", re.I),
        re.compile(r"\b(заняття\s+в\s+школах\s+(?:скасовано|відмінено|онлайн))\b", re.I),
        re.compile(r"\b(дистанційний\s+формат\s+навчання)\b", re.I),
    ]

    # In-person return announcements
    IN_PERSON_PATTERNS = [
        re.compile(r"\b(повертаються\s+до\s+очного\s+навчання|очне\s+навчання|школи\s+відновлюють\s+роботу)\b", re.I),
        re.compile(r"\b(заняття\s+у\s+звичайному\s+режимі|школярі\s+йдуть\s+до\s+школи)\b", re.I),
    ]

    # Infrastructure failure triggers (severe blackouts, transport down)
    INFRASTRUCTURE_TRIGGERS = [
        (re.compile(r"\b(без\s+світла|знеструмлено|відключення\s+електроенергії|блекаут)\b", re.I), "Проблеми з електропостачанням"),
        (re.compile(r"\b(без\s+тепла|відсутнє\s+опалення)\b", re.I), "Відсутність опалення в місті"),
        (re.compile(r"\b(електротранспорт\s+не\s+курсує|трамваї\s+не\s+ходять)\b", re.I), "Зупинка міського електротранспорту"),
    ]

    def __init__(self) -> None:
        self._current_status = SchoolStatusResult(
            is_remote=False,
            status=RemoteStudyStatus.NORMAL_IN_PERSON,
            remote_probability_percent=10,
            headline="Навчання у школах Одеси за звичайним графіком",
            infrastructure_factors=[],
        )

    def analyze_post(self, text: str, channel: str = "") -> SchoolStatusResult:
        """Parse incoming post from educational or utility channels."""
        if not text:
            return self._current_status

        lower = text.lower()
        now = datetime.now(timezone.utc)

        # 1. Check for official remote announcement
        for pat in self.OFFICIAL_REMOTE_PATTERNS:
            m = pat.search(lower)
            if m:
                factors = []
                for infra_pat, desc in self.INFRASTRUCTURE_TRIGGERS:
                    if infra_pat.search(lower):
                        factors.append(desc)

                self._current_status = SchoolStatusResult(
                    is_remote=True,
                    status=RemoteStudyStatus.OFFICIAL_REMOTE,
                    remote_probability_percent=100,
                    headline="Школи Одеси навчаються ДИСТАНЦІЙНО (Офіційно)",
                    official_quote=text[:250].strip() + ("..." if len(text) > 250 else ""),
                    source_channel=channel,
                    infrastructure_factors=factors,
                    updated_at=now,
                )
                return self._current_status

        # 2. Check for return to in-person
        for pat in self.IN_PERSON_PATTERNS:
            if pat.search(lower):
                self._current_status = SchoolStatusResult(
                    is_remote=False,
                    status=RemoteStudyStatus.NORMAL_IN_PERSON,
                    remote_probability_percent=5,
                    headline="Школи повернулися до очного навчання",
                    official_quote=text[:200].strip(),
                    source_channel=channel,
                    infrastructure_factors=[],
                    updated_at=now,
                )
                return self._current_status

        # 3. Check for severe utility failure in municipal channels (e.g. svet_odessa)
        detected_infra = []
        for infra_pat, desc in self.INFRASTRUCTURE_TRIGGERS:
            if infra_pat.search(lower):
                detected_infra.append(desc)

        if len(detected_infra) >= 2:
            self._current_status = SchoolStatusResult(
                is_remote=True,
                status=RemoteStudyStatus.HIGH_RISK_REMOTE,
                remote_probability_percent=75,
                headline="Високий ризик дистанційного навчання через проблеми з інфраструктурою",
                official_quote=text[:200].strip(),
                source_channel=channel,
                infrastructure_factors=detected_infra,
                updated_at=now,
            )
            return self._current_status

        return self._current_status

    def get_current_status(self) -> SchoolStatusResult:
        return self._current_status
