"""Pydantic schemas for request and response validation."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class GeoCoordinateSchema(BaseModel):
    lat: float = Field(..., ge=-90.0, le=90.0, description="Latitude")
    lon: float = Field(..., ge=-180.0, le=180.0, description="Longitude")


class TargetPresetSchema(BaseModel):
    name: str
    centroid: GeoCoordinateSchema
    radius_km: float
    warning_radius_km: float
    zones: Dict[str, float] = Field(default_factory=dict)
    monitored_places: List[str] = Field(default_factory=list)
    transit_corridors: List[str] = Field(default_factory=list)
    description: str = ""


class ChannelConfigSchema(BaseModel):
    id: str
    name: str
    username: str
    enabled: bool = True
    reliability_weight: float = 0.90
    threat_focus: List[str] = Field(default_factory=list)
    language: str = "uk"
    description: str = ""


class ThreatContributionSchema(BaseModel):
    threat_id: str
    threat_type: str
    raw_probability: float
    decayed_probability: float
    distance_km: Optional[float] = None
    heading_factor: Optional[float] = None
    time_to_impact_minutes: Optional[float] = None
    description: str = ""


class ThreatSignalSchema(BaseModel):
    threat_id: str
    threat_type: str
    quantity: int
    raw_text: str
    source_channel: str
    timestamp: str
    origin_location: Optional[str] = None
    target_heading: Optional[str] = None
    detected_locations: List[str] = Field(default_factory=list)
    current_coordinate: Optional[GeoCoordinateSchema] = None
    trajectory: Optional[Dict[str, Any]] = None
    is_cancellation: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ThreatEventSchema(BaseModel):
    event_id: str
    threat_type: str
    quantity: int
    raw_text: str
    source_channel: str
    timestamp: str


class ThreatHistoryResponseSchema(BaseModel):
    total: int
    limit: int
    offset: int
    items: List[ThreatEventSchema]


class ProbabilityResponseSchema(BaseModel):
    target_district: str
    probability_percent: int = Field(..., ge=0, le=100)
    alert_level: str
    active_threat_count: int
    primary_threat_type: Optional[str] = None
    estimated_time_to_impact_minutes: Optional[int] = None
    contributing_threats: List[ThreatContributionSchema] = Field(default_factory=list)
    summary: str
    calculated_at: str


class SimulatePayloadSchema(BaseModel):
    text: str = Field(..., min_length=1, description="Raw threat post text from Telegram")
    channel: str = Field("vanek_nikolaev", description="Source Telegram channel name or username")
    timestamp: Optional[str] = Field(None, description="ISO timestamp override")
    quantity: Optional[int] = Field(None, ge=1, le=500, description="Explicit quantity override")


class SimulateResponseSchema(BaseModel):
    status: str
    signals_count: int
    signals: List[Dict[str, Any]]
    probability: ProbabilityResponseSchema


class AIAskPayloadSchema(BaseModel):
    question: str = Field(..., min_length=1, max_length=500, description="User's tactical inquiry")
    preset: str = Field("odesa_tairovo", description="Target district preset")
    user_name: Optional[str] = Field("Денис", description="User's preferred name")


class AttendancePayloadSchema(BaseModel):
    date_str: str = Field(..., description="Date in YYYY-MM-DD format")
    status: str = Field(..., description="IN_PERSON, REMOTE_OFFICIAL, MISSED_ALARM")
    school_name: Optional[str] = Field("Ліцей «Гармонія»", description="School identifier")
    notes: Optional[str] = Field("", description="Optional user commentary")

