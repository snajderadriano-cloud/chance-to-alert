"""Unit tests for Ukrainian threat parser."""

from datetime import datetime, timezone
import pytest

from app.domain.enums import ThreatType
from app.processing.threat_parser import ThreatParser


@pytest.fixture
def parser():
    return ThreatParser()


class TestThreatParser:
    def test_parse_shahed_group_towards_odesa(self, parser):
        text = "Увага! 4х БПЛА Shahed з моря курсом на Одесу!"
        signals = parser.parse(text, channel="vanek")
        assert len(signals) == 1
        sig = signals[0]
        assert sig.threat_type == ThreatType.SHAHED
        assert sig.quantity == 4
        assert sig.origin_location == "Чорне море"
        assert sig.target_heading == "Одеса"
        assert not sig.is_cancellation

    def test_parse_ballistic_threat(self, parser):
        text = "Загроза застосування балістичного озброєння з Криму!"
        signals = parser.parse(text, channel="alerts")
        assert len(signals) >= 1
        assert signals[0].threat_type == ThreatType.BALLISTIC
        assert signals[0].origin_location == "Крим"

    def test_parse_cruise_missiles(self, parser):
        text = "Пуски Калібрів з акваторії Чорного моря!"
        signals = parser.parse(text)
        assert len(signals) >= 1
        assert signals[0].threat_type == ThreatType.CRUISE_MISSILE

    def test_parse_tactical_aviation(self, parser):
        text = "Активність тактичної авіації ворога Су-34, загроза пусків КАБ"
        signals = parser.parse(text)
        assert len(signals) >= 1
        assert signals[0].threat_type == ThreatType.TACTICAL_AVIATION

    def test_parse_recon_drone(self, parser):
        text = "Розвідувальний дрон Орлан-10 фіксується над морем біля Чорноморська"
        signals = parser.parse(text)
        assert len(signals) >= 1
        assert signals[0].threat_type == ThreatType.RECON_DRONE

    def test_parse_cancellation_signal(self, parser):
        text = "Відбій загрози по БПЛА! Чисто."
        signals = parser.parse(text)
        assert len(signals) >= 1
        assert signals[0].is_cancellation is True
        assert signals[0].threat_type == ThreatType.SHAHED

    def test_parse_direction_negation(self, parser):
        text = "Шахеди не в бік Одеси, повз Одесу на північ"
        signals = parser.parse(text)
        assert len(signals) == 1
        assert signals[0].target_heading == "інший напрямок"

    def test_parse_empty_string(self, parser):
        assert parser.parse("") == []
        assert parser.parse("   ") == []
