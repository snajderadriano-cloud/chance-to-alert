"""Configuration loader for Chance to Alert.App.

Loads regional presets, channel lists, and operational scoring parameters from YAML
configuration files, with full environment variable override support.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml

from app.domain.entities import GeoCoordinate, TargetPreset
from app.domain.enums import ThreatType


@dataclass
class ChannelConfig:
    """Configuration for an operational Telegram threat monitoring channel."""

    id: str
    name: str
    username: str
    enabled: bool = True
    reliability_weight: float = 0.9
    threat_focus: List[ThreatType] = field(default_factory=list)
    language: str = "uk"
    description: str = ""
    url: str = ""
    channel_type: str = "AIR_THREAT_RADAR"
    filter_ads: bool = False

    def __post_init__(self) -> None:
        self.reliability_weight = max(0.0, min(1.0, float(self.reliability_weight)))
        parsed_focus: List[ThreatType] = []
        for item in self.threat_focus:
            if isinstance(item, ThreatType):
                parsed_focus.append(item)
            else:
                parsed_focus.append(ThreatType.from_str(str(item)))
        self.threat_focus = parsed_focus

    def to_dict(self) -> Dict[str, Any]:
        """Convert channel config to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "username": self.username,
            "enabled": self.enabled,
            "reliability_weight": self.reliability_weight,
            "threat_focus": [tf.value for tf in self.threat_focus],
            "language": self.language,
            "description": self.description,
            "url": self.url,
            "channel_type": self.channel_type,
            "filter_ads": self.filter_ads,
        }


@dataclass
class AppConfig:
    """Global application configuration holding active presets and channels."""

    default_preset: str
    presets: Dict[str, TargetPreset] = field(default_factory=dict)
    channels: List[ChannelConfig] = field(default_factory=list)
    config_dir: Path = field(default_factory=lambda: Path("config"))
    env: str = "development"
    log_level: str = "INFO"

    def get_preset(self, preset_name: Optional[str] = None) -> TargetPreset:
        """Retrieve target preset by name, falling back to default_preset."""
        name = preset_name or self.default_preset
        if name not in self.presets:
            available = ", ".join(self.presets.keys())
            raise KeyError(f"Preset '{name}' not found. Available presets: {available}")
        return self.presets[name]


def _find_default_config_dir() -> Path:
    """Locate the default configuration directory relative to this file or cwd."""
    env_dir = os.environ.get("CONFIG_DIR")
    if env_dir:
        candidate = Path(env_dir)
        if candidate.is_dir():
            return candidate

    # Check relative to current working directory
    cwd_candidate = Path.cwd() / "config"
    if cwd_candidate.is_dir():
        return cwd_candidate

    # Check relative to module path (app/../config)
    module_candidate = Path(__file__).resolve().parent.parent / "config"
    if module_candidate.is_dir():
        return module_candidate

    return Path("config")


def load_presets_from_yaml(presets_path: Path) -> Dict[str, TargetPreset]:
    """Load TargetPreset entities from a presets YAML file."""
    if not presets_path.exists():
        raise FileNotFoundError(f"Presets file not found: {presets_path}")

    with open(presets_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    raw_presets = data.get("presets", {})
    loaded_presets: Dict[str, TargetPreset] = {}

    for key, pdata in raw_presets.items():
        centroid_data = pdata.get("centroid", {})
        centroid = GeoCoordinate(
            lat=float(centroid_data.get("lat", 0.0)),
            lon=float(centroid_data.get("lon", 0.0)),
        )
        preset = TargetPreset(
            name=pdata.get("name", key),
            centroid=centroid,
            radius_km=float(pdata.get("radius_km", 35.0)),
            warning_radius_km=float(pdata.get("warning_radius_km", 100.0)),
            zones={str(zk): float(zv) for zk, zv in pdata.get("zones", {}).items()},
            monitored_places=[str(p) for p in pdata.get("monitored_places", [])],
            transit_corridors=[str(c) for c in pdata.get("transit_corridors", [])],
            description=pdata.get("description", ""),
        )
        loaded_presets[key] = preset

    return loaded_presets


def load_channels_from_yaml(channels_path: Path) -> List[ChannelConfig]:
    """Load ChannelConfig items from a channels YAML file."""
    if not channels_path.exists():
        raise FileNotFoundError(f"Channels file not found: {channels_path}")

    with open(channels_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    raw_channels = data.get("channels", [])
    loaded_channels: List[ChannelConfig] = []

    for cdata in raw_channels:
        channel = ChannelConfig(
            id=str(cdata.get("id", "")),
            name=str(cdata.get("name", "")),
            username=str(cdata.get("username", "")),
            enabled=bool(cdata.get("enabled", True)),
            reliability_weight=float(cdata.get("reliability_weight", 0.9)),
            threat_focus=cdata.get("threat_focus", []),
            language=str(cdata.get("language", "uk")),
            description=str(cdata.get("description", "")),
            url=str(cdata.get("url", "")),
            channel_type=str(cdata.get("channel_type", "AIR_THREAT_RADAR")),
            filter_ads=bool(cdata.get("filter_ads", False)),
        )
        loaded_channels.append(channel)

    return loaded_channels


def load_config(config_dir: Optional[Union[str, Path]] = None) -> AppConfig:
    """Load application configuration from directory or default location with env overrides."""
    if config_dir is not None:
        target_dir = Path(config_dir)
    else:
        target_dir = _find_default_config_dir()

    # Determine default preset with TARGET_DISTRICT or DEFAULT_PRESET env override
    default_preset = (
        os.environ.get("TARGET_DISTRICT")
        or os.environ.get("DEFAULT_PRESET")
        or "odesa_district"
    )
    env = os.environ.get("APP_ENV", "development")
    log_level = os.environ.get("LOG_LEVEL", "INFO")

    presets_file = target_dir / "presets_odesa.yaml"
    channels_file = target_dir / "channels.yaml"

    presets = load_presets_from_yaml(presets_file) if presets_file.exists() else {}
    channels = load_channels_from_yaml(channels_file) if channels_file.exists() else []

    return AppConfig(
        default_preset=default_preset,
        presets=presets,
        channels=channels,
        config_dir=target_dir,
        env=env,
        log_level=log_level,
    )


# Singleton-style default cached config
_cached_config: Optional[AppConfig] = None


def get_config(reload: bool = False) -> AppConfig:
    """Get the active configuration instance, caching for performance."""
    global _cached_config
    if _cached_config is None or reload:
        _cached_config = load_config()
    return _cached_config


def get_preset(preset_name: Optional[str] = None, config: Optional[AppConfig] = None) -> TargetPreset:
    """Convenience function to get a TargetPreset by name."""
    cfg = config or get_config()
    return cfg.get_preset(preset_name)


def list_presets(config: Optional[AppConfig] = None) -> Dict[str, TargetPreset]:
    """Convenience function to list all configured TargetPresets."""
    cfg = config or get_config()
    return cfg.presets


def list_channels(config: Optional[AppConfig] = None) -> List[ChannelConfig]:
    """Convenience function to list all configured ChannelConfigs."""
    cfg = config or get_config()
    return cfg.channels
