"""Self-learning and weight calibration engine for Chance to Alert.App.

Tracks channel accuracy, true positives, false alarms, and warning lead-time.
Adapts reliability weights over time using Bayesian / Exponential Moving Average updates.
Also records diurnal (hourly) patterns and corridor transition statistics.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import logging
import sqlite3
from typing import Any, Dict, List, Optional

logger = logging.getLogger("learning_engine")


@dataclass
class ChannelAccuracyMetric:
    channel: str
    total_signals: int
    confirmed_signals: int
    unconfirmed_signals: int
    average_lead_time_minutes: float
    current_calibrated_weight: float
    accuracy_percent: float
    last_updated: str


class CalibrationEngine:
    """Calibrates channel reliability weights and analyzes corridor frequencies over time."""

    def __init__(self, storage: Any):
        self.storage = storage
        self._init_learning_tables()

    @property
    def conn(self) -> sqlite3.Connection:
        if hasattr(self.storage, "conn"):
            return self.storage.conn
        return self.storage

    def _init_learning_tables(self) -> None:
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS channel_performance (
                    channel TEXT PRIMARY KEY,
                    total_signals INTEGER NOT NULL DEFAULT 0,
                    confirmed_signals INTEGER NOT NULL DEFAULT 0,
                    unconfirmed_signals INTEGER NOT NULL DEFAULT 0,
                    total_lead_time_minutes REAL NOT NULL DEFAULT 0.0,
                    calibrated_weight REAL NOT NULL DEFAULT 0.85,
                    last_updated TEXT NOT NULL
                )
            """)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS corridor_hourly_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    hour_of_day INTEGER NOT NULL,
                    corridor_name TEXT NOT NULL,
                    threat_type TEXT NOT NULL,
                    occurrence_count INTEGER NOT NULL DEFAULT 1,
                    last_observed TEXT NOT NULL,
                    UNIQUE(hour_of_day, corridor_name, threat_type)
                )
            """)

    def record_signal_outcome(
        self,
        channel: str,
        is_confirmed: bool,
        lead_time_minutes: float = 0.0,
        base_weight: float = 0.85,
    ) -> float:
        """Update a channel's learning metrics based on event confirmation.

        Uses an Exponential Moving Average (EMA) learning rate alpha=0.10.
        Rewards early accurate warnings; penalizes uncorroborated single-source claims.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        cur = self.conn.cursor()
        cur.execute(
            "SELECT total_signals, confirmed_signals, unconfirmed_signals, total_lead_time_minutes, calibrated_weight "
            "FROM channel_performance WHERE channel = ?",
            (channel,),
        )
        row = cur.fetchone()

        if row:
            total, confirmed, unconfirmed, total_lead, current_weight = row
            total += 1
            if is_confirmed:
                confirmed += 1
                total_lead += max(0.0, lead_time_minutes)
                # Performance score: accuracy reward + small lead time bonus
                lead_bonus = min(0.10, lead_time_minutes * 0.01)
                event_score = min(0.99, base_weight + 0.05 + lead_bonus)
            else:
                unconfirmed += 1
                event_score = max(0.35, current_weight - 0.15)

            # EMA update with learning rate alpha = 0.10
            alpha = 0.10
            new_weight = round((1.0 - alpha) * current_weight + alpha * event_score, 3)
            new_weight = max(0.30, min(0.99, new_weight))

            with self.conn:
                self.conn.execute(
                    "UPDATE channel_performance SET "
                    "total_signals = ?, confirmed_signals = ?, unconfirmed_signals = ?, "
                    "total_lead_time_minutes = ?, calibrated_weight = ?, last_updated = ? "
                    "WHERE channel = ?",
                    (total, confirmed, unconfirmed, total_lead, new_weight, now_iso, channel),
                )
            return new_weight
        else:
            total = 1
            confirmed = 1 if is_confirmed else 0
            unconfirmed = 0 if is_confirmed else 1
            total_lead = lead_time_minutes if is_confirmed else 0.0
            initial_weight = min(0.99, base_weight + 0.02) if is_confirmed else max(0.40, base_weight - 0.10)

            with self.conn:
                self.conn.execute(
                    "INSERT INTO channel_performance "
                    "(channel, total_signals, confirmed_signals, unconfirmed_signals, total_lead_time_minutes, calibrated_weight, last_updated) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (channel, total, confirmed, unconfirmed, total_lead, initial_weight, now_iso),
                )
            return initial_weight

    def record_corridor_observation(self, corridor: str, threat_type: str, dt: Optional[datetime] = None) -> None:
        """Record arrival time and corridor for hourly threat clustering analysis."""
        now = dt or datetime.now(timezone.utc)
        hour = now.hour
        now_iso = now.isoformat()

        with self.conn:
            self.conn.execute(
                """
                INSERT INTO corridor_hourly_stats (hour_of_day, corridor_name, threat_type, occurrence_count, last_observed)
                VALUES (?, ?, ?, 1, ?)
                ON CONFLICT(hour_of_day, corridor_name, threat_type) DO UPDATE SET
                    occurrence_count = occurrence_count + 1,
                    last_observed = excluded.last_observed
                """,
                (hour, corridor, threat_type, now_iso),
            )

    def get_channel_metrics(self) -> List[ChannelAccuracyMetric]:
        """Retrieve current learned accuracy metrics for all channels."""
        cur = self.conn.cursor()
        cur.execute(
            "SELECT channel, total_signals, confirmed_signals, unconfirmed_signals, total_lead_time_minutes, calibrated_weight, last_updated "
            "FROM channel_performance ORDER BY confirmed_signals DESC"
        )
        results = []
        for row in cur.fetchall():
            ch, total, conf, unconf, lead, weight, updated = row
            acc = round((conf / total * 100.0) if total > 0 else 0.0, 1)
            avg_lead = round((lead / conf) if conf > 0 else 0.0, 1)
            results.append(
                ChannelAccuracyMetric(
                    channel=ch,
                    total_signals=total,
                    confirmed_signals=conf,
                    unconfirmed_signals=unconf,
                    average_lead_time_minutes=avg_lead,
                    current_calibrated_weight=weight,
                    accuracy_percent=acc,
                    last_updated=updated,
                )
            )
        return results

    def get_hourly_corridor_stats(self) -> List[Dict]:
        """Retrieve historical threat distribution by hour and corridor."""
        cur = self.conn.cursor()
        cur.execute(
            "SELECT hour_of_day, corridor_name, threat_type, occurrence_count, last_observed "
            "FROM corridor_hourly_stats ORDER BY occurrence_count DESC"
        )
        return [
            {
                "hour_of_day": r[0],
                "corridor_name": r[1],
                "threat_type": r[2],
                "occurrence_count": r[3],
                "last_observed": r[4],
            }
            for r in cur.fetchall()
        ]
