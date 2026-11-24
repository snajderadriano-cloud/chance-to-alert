"""Unit tests for the self-learning calibration engine."""

import sqlite3
from app.learning.calibration_engine import CalibrationEngine


def test_calibration_engine_learning_curve():
    conn = sqlite3.connect(":memory:")
    engine = CalibrationEngine(conn)

    # Initially no metrics
    metrics = engine.get_channel_metrics()
    assert len(metrics) == 0

    # Record 3 confirmed detections from Vanek with good lead time
    w1 = engine.record_signal_outcome("vanek_nikolaev", is_confirmed=True, lead_time_minutes=15.0, base_weight=0.95)
    assert w1 >= 0.95

    w2 = engine.record_signal_outcome("vanek_nikolaev", is_confirmed=True, lead_time_minutes=20.0, base_weight=0.95)
    assert w2 >= w1

    # Record 1 false alarm / unconfirmed post
    w3 = engine.record_signal_outcome("vanek_nikolaev", is_confirmed=False, lead_time_minutes=0.0, base_weight=0.95)
    assert w3 < w2  # Weight penalized for unconfirmed post

    # Verify metrics output
    metrics = engine.get_channel_metrics()
    assert len(metrics) == 1
    m = metrics[0]
    assert m.channel == "vanek_nikolaev"
    assert m.total_signals == 3
    assert m.confirmed_signals == 2
    assert m.unconfirmed_signals == 1
    assert m.accuracy_percent == 66.7


def test_corridor_hourly_stats():
    conn = sqlite3.connect(":memory:")
    engine = CalibrationEngine(conn)

    engine.record_corridor_observation("Тузли -> Маяки", "SHAHED")
    engine.record_corridor_observation("Тузли -> Маяки", "SHAHED")
    engine.record_corridor_observation("Крим -> Коблеве", "BALLISTIC")

    stats = engine.get_hourly_corridor_stats()
    assert len(stats) >= 2
    top = stats[0]
    assert top["corridor_name"] == "Тузли -> Маяки"
    assert top["occurrence_count"] == 2
