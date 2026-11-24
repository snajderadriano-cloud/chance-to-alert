"""Deterministic NLP parser extracting ThreatSignals from sanitized Ukrainian Telegram posts."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import List, Optional

from app.domain.entities import GeoCoordinate, ThreatSignal, TrajectoryVector
from app.domain.enums import ThreatType
from app.domain.geo import calculate_azimuth
from app.processing.ad_filter import ContentFilter, PostClassification
from app.processing.gazetteer import RegionalGazetteer
from app.processing.lexicon import (
    CANCELLATION_PATTERNS,
    DIRECTION_PATTERNS,
    QUANTITY_PATTERNS,
    THREAT_PATTERNS,
)
from app.processing.sanitizer import TextSanitizer


class ThreatParser:
    """Extracts structured ThreatSignals from Ukrainian military monitoring posts."""

    def __init__(
        self,
        gazetteer: Optional[RegionalGazetteer] = None,
        sanitizer: Optional[TextSanitizer] = None,
        content_filter: Optional[ContentFilter] = None,
    ) -> None:
        self.gazetteer = gazetteer or RegionalGazetteer()
        self.sanitizer = sanitizer or TextSanitizer()
        self.content_filter = content_filter or ContentFilter()

    def parse(
        self,
        text: str,
        channel: str = "general",
        timestamp: Optional[datetime] = None,
    ) -> List[ThreatSignal]:
        """Parse raw post text into structured ThreatSignal entities."""
        if not text or not text.strip():
            return []

        ts = timestamp or datetime.now(timezone.utc)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        clean = self.sanitizer.sanitize(text)
        if not clean or not clean.strip():
            return []

        # 0. Noise & Advertising filtering
        filter_result = self.content_filter.filter_post(clean, channel_username=channel)
        if not filter_result.is_threat_relevant:
            return []

        lower = clean.lower()

        # 1. Check for cancellation / all-clear
        is_cancellation = any(pattern.search(lower) for pattern in CANCELLATION_PATTERNS)
        if is_cancellation:
            cancelled_type = ThreatType.UNKNOWN
            # Priority order for cancellation check
            priority_types = [
                ThreatType.RECON_DRONE,
                ThreatType.SHAHED,
                ThreatType.BALLISTIC,
                ThreatType.CRUISE_MISSILE,
                ThreatType.TACTICAL_AVIATION,
            ]
            for tt in priority_types:
                patterns = THREAT_PATTERNS.get(tt, [])
                if any(p.search(lower) for p in patterns):
                    cancelled_type = tt
                    break

            signals = [
                ThreatSignal(
                    threat_type=cancelled_type,
                    quantity=1,
                    raw_text=clean,
                    source_channel=channel,
                    timestamp=ts,
                    is_cancellation=True,
                )
            ]
            if re.search(r"\b(залишається\s+загроза|загроза\s+балістики)\b", lower):
                signals.append(
                    ThreatSignal(
                        threat_type=ThreatType.BALLISTIC,
                        quantity=1,
                        raw_text=clean,
                        source_channel=channel,
                        timestamp=ts,
                        is_cancellation=False,
                    )
                )
            return signals

        # 2. Detect ThreatTypes in priority order
        detected_types: List[ThreatType] = []
        priority_types = [
            ThreatType.BALLISTIC,
            ThreatType.CRUISE_MISSILE,
            ThreatType.TACTICAL_AVIATION,
            ThreatType.RECON_DRONE,
            ThreatType.SHAHED,
        ]
        for tt in priority_types:
            patterns = THREAT_PATTERNS.get(tt, [])
            if any(p.search(lower) for p in patterns):
                # If recon drone already matched, don't also add Shahed because of the word "дрон"
                if tt == ThreatType.SHAHED and ThreatType.RECON_DRONE in detected_types:
                    continue
                detected_types.append(tt)

        if not detected_types:
            detected_types = [ThreatType.UNKNOWN]

        # 3. Extract quantity
        qty = 1
        qty_match = QUANTITY_PATTERNS[0].search(lower)
        if qty_match:
            try:
                val = int(qty_match.group(1))
                if 1 <= val <= 500:
                    qty = val
            except (ValueError, TypeError):
                qty = 1
        elif QUANTITY_PATTERNS[1].search(lower):
            qty = 2
        elif QUANTITY_PATTERNS[2].search(lower):
            qty = 4

        # 4. Heading & direction detection
        negated_heading = bool(DIRECTION_PATTERNS["away_from_odesa"].search(lower))
        towards_odesa = bool(DIRECTION_PATTERNS["towards_odesa"].search(lower))

        origin = None
        if DIRECTION_PATTERNS["sea_approach"].search(lower):
            origin = "Чорне море"
        elif DIRECTION_PATTERNS["crimea_approach"].search(lower):
            origin = "Крим"

        # 5. Extract mentioned geographical locations
        detected_places = self.gazetteer.extract_places(clean)
        current_coord: Optional[GeoCoordinate] = None
        for place in detected_places:
            coord = self.gazetteer.resolve(place)
            if coord:
                current_coord = coord
                break

        # If origin is known and current_coord is not set
        if current_coord is None and origin:
            current_coord = self.gazetteer.resolve(origin)

        target_heading = None
        trajectory: Optional[TrajectoryVector] = None

        if not negated_heading:
            if towards_odesa or any("одес" in p or "чорноморськ" in p for p in detected_places):
                target_heading = "Одеса"
        else:
            target_heading = "інший напрямок"

        if current_coord:
            heading_deg = None
            if target_heading == "Одеса":
                odesa_centroid = GeoCoordinate(lat=46.4825, lon=30.7233)
                heading_deg = calculate_azimuth(current_coord, odesa_centroid)
            elif negated_heading:
                heading_deg = 270.0

            trajectory = TrajectoryVector(
                current=current_coord,
                heading_degrees=heading_deg,
            )

        signals: List[ThreatSignal] = []
        for tt in detected_types:
            sig = ThreatSignal(
                threat_type=tt,
                quantity=qty,
                raw_text=clean,
                source_channel=channel,
                timestamp=ts,
                origin_location=origin,
                target_heading=target_heading,
                detected_locations=detected_places,
                current_coordinate=current_coord,
                trajectory=trajectory,
                is_cancellation=False,
            )
            signals.append(sig)

        return signals
