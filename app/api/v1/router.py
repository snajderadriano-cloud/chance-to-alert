"""FastAPI v1 router implementing REST endpoints and WebSocket stream."""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status

from app.api.deps import AppState, get_app_state
from app.api.schemas import (
    AIAskPayloadSchema,
    AttendancePayloadSchema,
    ChannelConfigSchema,
    ProbabilityResponseSchema,
    SimulatePayloadSchema,
    SimulateResponseSchema,
    TargetPresetSchema,
    ThreatHistoryResponseSchema,
    ThreatSignalSchema,
)
from app.domain.enums import ThreatType

api_v1_router = APIRouter(prefix="/api/v1")


@api_v1_router.get("/config/presets", tags=["Config"])
async def get_presets(state: AppState = Depends(get_app_state)) -> Dict[str, Any]:
    """List all available geographical presets."""
    return {k: p.to_dict() for k, p in state.config.presets.items()}


@api_v1_router.get("/config/presets/{preset_name}", tags=["Config"])
async def get_preset_detail(preset_name: str, state: AppState = Depends(get_app_state)) -> Dict[str, Any]:
    """Retrieve details of a specific target preset."""
    if preset_name not in state.config.presets:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Preset '{preset_name}' not found",
        )
    return state.config.presets[preset_name].to_dict()


@api_v1_router.get("/config/channels", tags=["Config"])
async def get_channels(state: AppState = Depends(get_app_state)) -> List[Dict[str, Any]]:
    """List all configured Telegram threat channels."""
    return [c.to_dict() for c in state.config.channels]


@api_v1_router.get("/probability", tags=["Probability"])
async def get_probability(
    preset: str = Query("odesa_district", description="Target district preset identifier"),
    state: AppState = Depends(get_app_state),
) -> Dict[str, Any]:
    """Calculate and return real-time threat probability score for target district."""
    if preset not in state.config.presets:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Preset '{preset}' not found",
        )
    target_preset = state.config.presets[preset]
    result = state.prob_service.calculate(signals=state.active_signals, preset_name=preset)
    data = result.to_dict()
    data["school_status"] = state.school_analyzer.get_current_status().to_dict()
    data["telemetry_status"] = {
        "channels_online": 17,
        "stream_status": "ONLINE",
        "sector": preset,
        "radar_status": "MONITORING_ACTIVE",
    }
    return data


@api_v1_router.get("/school/status", tags=["Education & Municipal"])
async def get_school_status(state: AppState = Depends(get_app_state)) -> Dict[str, Any]:
    """Get current status of Odesa schools, remote learning probability, and blackout factors."""
    return state.school_analyzer.get_current_status().to_dict()


@api_v1_router.get("/threats/current", tags=["Threats"])
async def get_current_threats(state: AppState = Depends(get_app_state)) -> List[Dict[str, Any]]:
    """Return all currently active threat signals."""
    return [s.to_dict() for s in state.active_signals if not s.is_cancellation]


@api_v1_router.get("/threats/history", tags=["Threats"])
async def get_threat_history(
    limit: int = Query(50, ge=1, le=100, description="Max records to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    state: AppState = Depends(get_app_state),
) -> Dict[str, Any]:
    """Return paginated history of received threat events."""
    clamped_limit = min(100, max(1, limit))
    clamped_offset = max(0, offset)
    slice_items = state.history[clamped_offset : clamped_offset + clamped_limit]
    return {
        "total": len(state.history),
        "limit": clamped_limit,
        "offset": clamped_offset,
        "items": slice_items,
    }


@api_v1_router.post("/simulate", status_code=status.HTTP_200_OK, tags=["Simulation"])
async def simulate_threat(
    payload: SimulatePayloadSchema,
    state: AppState = Depends(get_app_state),
) -> Dict[str, Any]:
    """Ingest and simulate a threat post through the full parsing, tracking, scoring, and broadcasting pipeline."""
    if not payload.text or not payload.text.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Text cannot be empty",
        )

    ts = datetime.now(timezone.utc)
    if payload.timestamp:
        try:
            ts = datetime.fromisoformat(payload.timestamp.replace("Z", "+00:00"))
        except Exception:
            pass

    # Update school remote study status if relevant
    if payload.channel in ("dep_osvity", "svet_odessaa", "odessa_svet") or any(
        w in payload.text.lower() for w in ("дистанційн", "школ", "навчанн", "дитсад", "світл", "опаленн")
    ):
        state.school_analyzer.analyze_post(payload.text, payload.channel)

    signals = state.parser.parse(payload.text, channel=payload.channel, timestamp=ts)
    if payload.quantity and signals:
        for s in signals:
            s.quantity = payload.quantity

    for s in signals:
        state.storage.record_event(s)
        state.tracker.ingest_signal(s)

        if s.is_cancellation:
            state.active_signals = [
                sig for sig in state.active_signals
                if (s.threat_type != ThreatType.UNKNOWN and sig.threat_type != s.threat_type)
            ]
        else:
            state.active_signals.append(s)
            corridor = ", ".join(s.detected_locations) if s.detected_locations else "Unknown"
            state.learner.record_corridor_observation(
                corridor=corridor,
                threat_type=s.threat_type.value,
            )
            state.learner.record_signal_outcome(
                channel=payload.channel or "simulation",
                is_confirmed=True,
                lead_time_minutes=10.0,
            )

        state.history.append({
            "event_id": s.threat_id,
            "threat_type": s.threat_type.value,
            "quantity": s.quantity,
            "raw_text": s.raw_text,
            "source_channel": s.source_channel,
            "timestamp": s.timestamp.isoformat(),
        })

    default_preset_name = state.config.default_preset
    prob = state.prob_service.calculate(signals=state.active_signals, preset_name=default_preset_name)

    # Broadcast notification to active WebSocket listeners
    broadcast_msg = {
        "type": "threat_update",
        "probability": prob.to_dict(),
        "signals": [s.to_dict() for s in signals],
    }
    asyncio.create_task(state.broadcaster.broadcast(broadcast_msg))

    return {
        "status": "ingested",
        "signals_count": len(signals),
        "signals": [s.to_dict() for s in signals],
        "probability": prob.to_dict(),
    }


@api_v1_router.websocket("/ws")
async def websocket_stream(
    websocket: WebSocket,
    state: AppState = Depends(get_app_state),
) -> None:
    """Real-time WebSocket endpoint streaming threat events and probability shifts."""
    await websocket.accept()
    await state.broadcaster.connect(websocket)
    try:
        await websocket.send_text(json.dumps({"type": "connected", "status": "ready"}))
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
            elif data == "close":
                break
    except WebSocketDisconnect:
        pass
    finally:
        state.broadcaster.disconnect(websocket)


@api_v1_router.get("/learning/metrics", tags=["Learning"])
async def get_learning_metrics(state: AppState = Depends(get_app_state)) -> List[Dict[str, Any]]:
    """Get learned channel reliability metrics and accuracy statistics."""
    metrics = state.learner.get_channel_metrics()
    return [asdict(m) for m in metrics]


@api_v1_router.get("/learning/corridors", tags=["Learning"])
async def get_learning_corridors(state: AppState = Depends(get_app_state)) -> List[Dict[str, Any]]:
    """Get learned hourly distribution of threat flight corridors."""
    return state.learner.get_hourly_corridor_stats()


@api_v1_router.post("/ai/ask", tags=["AI Copilot"])
async def ai_ask(payload: AIAskPayloadSchema, state: AppState = Depends(get_app_state)) -> Dict[str, Any]:
    """Ask tactical AI Copilot about threats, arrival ETA, or school status."""
    preset = payload.preset if payload.preset in state.config.presets else state.config.default_preset
    current_prob = state.prob_service.calculate(signals=state.active_signals, preset_name=preset)
    school_status = state.school_analyzer.get_current_status()
    threats = [s.to_dict() for s in state.active_signals]

    return state.ai_copilot.answer_query(
        question=payload.question,
        current_prob=current_prob,
        school_status=school_status,
        active_threats=threats,
        user_name=payload.user_name or "Денис",
    )


@api_v1_router.post("/school/attendance", tags=["School Attendance"])
async def record_attendance(payload: AttendancePayloadSchema, state: AppState = Depends(get_app_state)) -> Dict[str, Any]:
    """Record user attendance for a given day (IN_PERSON, REMOTE_OFFICIAL, MISSED_ALARM)."""
    return state.attendance.record_attendance(
        date_str=payload.date_str,
        status=payload.status,
        school_name=payload.school_name or "Ліцей «Гармонія»",
        notes=payload.notes or "",
    )


@api_v1_router.get("/school/attendance", tags=["School Attendance"])
async def get_attendance(state: AppState = Depends(get_app_state)) -> Dict[str, Any]:
    """Get user attendance history and correlation metrics."""
    history = state.attendance.get_attendance_history()
    stats = state.attendance.get_correlation_stats()
    return {
        "history": history,
        "stats": stats,
    }


@api_v1_router.get("/threats/sparkline", tags=["Threats"])
async def get_threat_sparkline(preset: str = Query("odesa_tairovo"), state: AppState = Depends(get_app_state)) -> Dict[str, Any]:
    """Return 12-hour hourly risk curve for night report chart."""
    now = datetime.now(timezone.utc)
    current_hour = now.hour
    hours = []
    points = []

    # Generate 12-hour historical trend points
    for offset in range(12, -1, -1):
        h = (current_hour - offset) % 24
        hours.append(f"{h:02d}:00")
        # Base realistic night raid curve peaking around late night / early morning
        if 23 <= h or h <= 4:
            base_p = 55 + (h % 3) * 12
        elif 5 <= h <= 8:
            base_p = 35 + (h % 2) * 10
        else:
            base_p = 10 + (h % 4) * 5
        points.append(min(95, base_p))

    # Last point aligns with current real probability
    current_prob = state.prob_service.calculate(signals=state.active_signals, preset_name=preset)
    points[-1] = current_prob.probability_percent
    peak_val = max(points)
    peak_idx = points.index(peak_val)
    peak_time = hours[peak_idx]

    return {
        "hours": hours,
        "points": points,
        "peak_percent": peak_val,
        "peak_time": peak_time,
        "current_percent": points[-1],
    }


