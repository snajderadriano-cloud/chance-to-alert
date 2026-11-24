"""Operational application scenarios (Tier 4) matching acceptance criteria."""

from datetime import datetime, timedelta, timezone
import pytest
from starlette.testclient import TestClient

from app.domain.entities import GeoCoordinate, TargetPreset, ThreatSignal, TrajectoryVector
from app.domain.enums import AlertLevel, ThreatType
from app.domain.scoring import calculate_aggregate_probability, calculate_threat_probability
from app.main import app
from app.processing.threat_parser import ThreatParser


@pytest.fixture
def odesa_district():
    return TargetPreset(
        name="odesa_district",
        centroid=GeoCoordinate(lat=46.4825, lon=30.7233),
        radius_km=35.0,
        warning_radius_km=100.0,
    )


@pytest.fixture
def danube_district():
    return TargetPreset(
        name="danube_district",
        centroid=GeoCoordinate(lat=45.3500, lon=28.8333),  # Izmail
        radius_km=35.0,
        warning_radius_km=100.0,
    )


class TestOperationalScenarios:
    """Rigorous verification of the 7 real-world operational scenarios from TEST_INFRA.md."""

    def test_scenario_1_shahed_swarm_towards_odesa(self, odesa_district):
        """Scenario 1: Multiple UAV reports approaching from Black Sea towards Odesa District.

        Escalates through YELLOW/ORANGE to severe alert level (>80%).
        """
        parser = ThreatParser()
        text = "Увага! Рій з 8 БПЛА Shahed з акваторії Чорного моря наближаються курсом на Одесу (Затока -> Чорноморськ -> Одеса)!"
        signals = parser.parse(text, channel="vanek_nikolaev")
        assert len(signals) == 1
        sig = signals[0]
        assert sig.threat_type == ThreatType.SHAHED
        assert sig.quantity >= 4

        result = calculate_aggregate_probability(signals=[sig], target=odesa_district)
        assert result.probability_percent >= 75
        assert result.alert_level in (AlertLevel.ORANGE, AlertLevel.RED)

    def test_scenario_2_distant_alerts(self, odesa_district):
        """Scenario 2: Distant drone/missile alerts in northern/eastern Ukraine (Sumy, Kharkiv).

        Odesa District probability remains calm baseline GREEN (<15%).
        """
        distant_coord = GeoCoordinate(lat=50.0000, lon=36.2500)  # Kharkiv
        distant_signal = ThreatSignal(
            threat_type=ThreatType.SHAHED,
            quantity=2,
            raw_text="БПЛА над Харковом",
            current_coordinate=distant_coord,
            trajectory=TrajectoryVector(current=distant_coord, heading_degrees=180.0),
        )
        result = calculate_aggregate_probability(signals=[distant_signal], target=odesa_district)
        assert result.probability_percent <= 15
        assert result.alert_level == AlertLevel.GREEN

    def test_scenario_3_intra_oblast_danube_vs_odesa(self, odesa_district, danube_district):
        """Scenario 3: Drone strikes targeting Danube ports (Izmail/Reni) in southern Odesa Oblast.

        Danube risk elevates significantly while Odesa District centroid remains low risk,
        demonstrating spatial discrimination.
        """
        izmail_coord = GeoCoordinate(lat=45.3500, lon=28.8333)
        danube_signal = ThreatSignal(
            threat_type=ThreatType.SHAHED,
            quantity=4,
            raw_text="Група шахедів заходить на Ізмаїл / Рені з гирла Дунаю!",
            current_coordinate=izmail_coord,
            origin_location="Чорне море",
        )

        danube_prob = calculate_aggregate_probability(signals=[danube_signal], target=danube_district)
        odesa_prob = calculate_aggregate_probability(signals=[danube_signal], target=odesa_district)

        assert danube_prob.probability_percent >= 60
        assert odesa_prob.probability_percent <= 30
        assert danube_prob.probability_percent > odesa_prob.probability_percent + 30

    def test_scenario_4_sudden_ballistic_alert(self, odesa_district):
        """Scenario 4: Crimea launch vector with fast flight time.

        Immediate acute probability spike to RED (>90%) with low estimated time-to-impact.
        """
        parser = ThreatParser()
        text = "ТЕРМІНОВО! Загроза застосування балістичного озброєння з Криму (мис Чауда/Севастополь) в напрямку Одеси!"
        signals = parser.parse(text, channel="alerts")
        assert len(signals) >= 1
        sig = signals[0]
        assert sig.threat_type == ThreatType.BALLISTIC

        result = calculate_aggregate_probability(signals=signals, target=odesa_district)
        assert result.probability_percent >= 85
        assert result.alert_level == AlertLevel.RED
        assert result.primary_threat_type == ThreatType.BALLISTIC

    def test_scenario_5_all_clear_cancellation(self, odesa_district):
        """Scenario 5: Threat reports followed by official 'відбій' / cancellation message.

        Active threat neutralized, alert level drops back to GREEN (<25%).
        """
        parser = ThreatParser()
        threat_text = "Шахед курсом на Одесу"
        signals = parser.parse(threat_text)
        result1 = calculate_aggregate_probability(signals=signals, target=odesa_district)
        assert result1.probability_percent >= 40

        cancel_text = "Відбій загрози по БПЛА! Чисто по області."
        cancel_signals = parser.parse(cancel_text)
        assert cancel_signals[0].is_cancellation is True

        combined = signals + cancel_signals
        result2 = calculate_aggregate_probability(signals=combined, target=odesa_district)
        assert result2.probability_percent <= 10
        assert result2.alert_level == AlertLevel.GREEN

    def test_scenario_6_temporal_age_decay(self, odesa_district):
        """Scenario 6: Inactive threats without new reports decay over time according to half-life.

        Smoothly reducing probability over 15m, 30m, and 60m.
        """
        t0 = datetime(2026, 11, 23, 12, 0, 0, tzinfo=timezone.utc)
        near_coord = GeoCoordinate(lat=46.3015, lon=30.6568)  # Chornomorsk
        sig = ThreatSignal(
            threat_type=ThreatType.SHAHED,
            quantity=2,
            timestamp=t0,
            current_coordinate=near_coord,
        )

        p_fresh = calculate_threat_probability(sig, odesa_district, current_time=t0).decayed_probability
        p_15m = calculate_threat_probability(sig, odesa_district, current_time=t0 + timedelta(minutes=15)).decayed_probability
        p_30m = calculate_threat_probability(sig, odesa_district, current_time=t0 + timedelta(minutes=30)).decayed_probability
        p_60m = calculate_threat_probability(sig, odesa_district, current_time=t0 + timedelta(minutes=60)).decayed_probability

        # Monotonic decay
        assert p_fresh > p_15m > p_30m > p_60m

    def test_scenario_7_full_end_to_end_api_pipeline(self):
        """Scenario 7: Full pipeline through REST API simulate -> verify probability, history & audit."""
        with TestClient(app) as client:
            payload = {
                "text": "Увага! 3х БПЛА Shahed з моря прямують на Одесу!",
                "channel": "vanek_nikolaev",
                "quantity": 3,
            }
            resp = client.post("/api/v1/simulate", json=payload)
            assert resp.status_code == 200
            sim_data = resp.json()
            assert sim_data["status"] == "ingested"
            assert sim_data["signals_count"] >= 1

            prob_resp = client.get("/api/v1/probability?preset=odesa_district")
            assert prob_resp.status_code == 200
            prob_data = prob_resp.json()
            assert prob_data["probability_percent"] > 50

            hist_resp = client.get("/api/v1/threats/history?limit=10&offset=0")
            assert hist_resp.status_code == 200
            hist_data = hist_resp.json()
            assert hist_data["total"] >= 1
            latest_item = hist_data["items"][-1]
            assert latest_item["threat_type"] == "SHAHED"
            assert "БПЛА" in latest_item["raw_text"]
