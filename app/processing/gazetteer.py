"""Regional geographical catalog and resolver for Odesa District and southern Ukraine."""

from __future__ import annotations

import re
from typing import Dict, List, Optional

from app.domain.entities import GeoCoordinate


KNOWN_LOCATIONS: Dict[str, GeoCoordinate] = {
    # Odesa District & immediate perimeter
    "одеса": GeoCoordinate(lat=46.4825, lon=30.7233),
    "одесу": GeoCoordinate(lat=46.4825, lon=30.7233),
    "одеси": GeoCoordinate(lat=46.4825, lon=30.7233),
    "одесі": GeoCoordinate(lat=46.4825, lon=30.7233),
    "одесса": GeoCoordinate(lat=46.4825, lon=30.7233),
    "одессу": GeoCoordinate(lat=46.4825, lon=30.7233),
    "чорноморськ": GeoCoordinate(lat=46.3015, lon=30.6568),
    "чорноморська": GeoCoordinate(lat=46.3015, lon=30.6568),
    "чорноморську": GeoCoordinate(lat=46.3015, lon=30.6568),
    "черноморск": GeoCoordinate(lat=46.3015, lon=30.6568),
    "фонтанка": GeoCoordinate(lat=46.5647, lon=30.8586),
    "фонтанку": GeoCoordinate(lat=46.5647, lon=30.8586),
    "южне": GeoCoordinate(lat=46.6225, lon=31.1008),
    "южного": GeoCoordinate(lat=46.6225, lon=31.1008),
    "південне": GeoCoordinate(lat=46.6225, lon=31.1008),
    "південного": GeoCoordinate(lat=46.6225, lon=31.1008),
    "таїрове": GeoCoordinate(lat=46.3958, lon=30.6483),
    "таирово": GeoCoordinate(lat=46.3958, lon=30.6483),
    "крижанівка": GeoCoordinate(lat=46.5611, lon=30.7961),
    "крыжановка": GeoCoordinate(lat=46.5611, lon=30.7961),
    "усатове": GeoCoordinate(lat=46.5361, lon=30.6556),
    "усатово": GeoCoordinate(lat=46.5361, lon=30.6556),
    "овідіополь": GeoCoordinate(lat=46.2464, lon=30.4431),
    "овидиополь": GeoCoordinate(lat=46.2464, lon=30.4431),
    "біляївка": GeoCoordinate(lat=46.4833, lon=30.2000),
    "беляевка": GeoCoordinate(lat=46.4833, lon=30.2000),
    "затока": GeoCoordinate(lat=46.0667, lon=30.4667),
    "затоку": GeoCoordinate(lat=46.0667, lon=30.4667),
    "кароліно-бугаз": GeoCoordinate(lat=46.1436, lon=30.5261),
    "дачне": GeoCoordinate(lat=46.5833, lon=30.5500),
    "нерубайське": GeoCoordinate(lat=46.5417, lon=30.6333),

    # Dniester / Coastal approach (South-West of Odesa)
    "білгород-дністровський": GeoCoordinate(lat=46.1917, lon=30.3444),
    "білгород-дністровського": GeoCoordinate(lat=46.1917, lon=30.3444),
    "аккерман": GeoCoordinate(lat=46.1917, lon=30.3444),
    "тузли": GeoCoordinate(lat=45.8600, lon=30.0900),
    "курортне": GeoCoordinate(lat=45.9333, lon=30.3000),
    "татарбунари": GeoCoordinate(lat=45.8500, lon=29.6167),
    "маяки": GeoCoordinate(lat=46.4167, lon=30.2667),
    "паланка": GeoCoordinate(lat=46.4100, lon=30.1000),

    # Danube Ports (Southern Odesa Oblast - 150-200 km from Odesa)
    "ізмаїл": GeoCoordinate(lat=45.3500, lon=28.8333),
    "ізмаїла": GeoCoordinate(lat=45.3500, lon=28.8333),
    "измаил": GeoCoordinate(lat=45.3500, lon=28.8333),
    "рені": GeoCoordinate(lat=45.4500, lon=28.2833),
    "рени": GeoCoordinate(lat=45.4500, lon=28.2833),
    "кілія": GeoCoordinate(lat=45.4475, lon=29.2689),
    "килия": GeoCoordinate(lat=45.4475, lon=29.2689),
    "вилкове": GeoCoordinate(lat=45.3986, lon=29.5936),
    "вилково": GeoCoordinate(lat=45.3986, lon=29.5936),

    # Transit corridors & Launch Areas
    "чорне море": GeoCoordinate(lat=45.8000, lon=31.2000),
    "чорного моря": GeoCoordinate(lat=45.8000, lon=31.2000),
    "черное море": GeoCoordinate(lat=45.8000, lon=31.2000),
    "крим": GeoCoordinate(lat=45.0000, lon=34.0000),
    "криму": GeoCoordinate(lat=45.0000, lon=34.0000),
    "крым": GeoCoordinate(lat=45.0000, lon=34.0000),
    "чауда": GeoCoordinate(lat=45.0050, lon=35.8360),
    "севастополь": GeoCoordinate(lat=44.6000, lon=33.5333),
    "миколаїв": GeoCoordinate(lat=46.9667, lon=31.9833),
    "миколаївщина": GeoCoordinate(lat=46.9667, lon=31.9833),
    "николаев": GeoCoordinate(lat=46.9667, lon=31.9833),
    "очаків": GeoCoordinate(lat=46.6167, lon=31.5500),
    "очаков": GeoCoordinate(lat=46.6167, lon=31.5500),
    "коблове": GeoCoordinate(lat=46.6667, lon=31.2000),
    "коблево": GeoCoordinate(lat=46.6667, lon=31.2000),
    "вознесенськ": GeoCoordinate(lat=47.5667, lon=31.3333),
}

CANONICAL_PLACE_MAPPING: Dict[str, str] = {
    "одесу": "одеса",
    "одеси": "одеса",
    "одесі": "одеса",
    "одесса": "одеса",
    "одессу": "одеса",
    "чорноморська": "чорноморськ",
    "чорноморську": "чорноморськ",
    "черноморск": "чорноморськ",
    "фонтанку": "фонтанка",
    "южного": "южне",
    "південного": "південне",
    "таїрова": "таїрове",
    "ізмаїла": "ізмаїл",
    "ізмаїлу": "ізмаїл",
    "измаил": "ізмаїл",
    "рени": "рені",
    "кілії": "кілія",
    "килия": "кілія",
    "вилкова": "вилкове",
    "вилково": "вилкове",
    "чорного моря": "чорне море",
    "черное море": "чорне море",
    "криму": "крим",
    "крым": "крим",
}


class RegionalGazetteer:
    """Geographic resolver for Odesa District, Odesa Oblast, and maritime corridors."""

    def __init__(self, catalog: Optional[Dict[str, GeoCoordinate]] = None) -> None:
        self.catalog = catalog or dict(KNOWN_LOCATIONS)

    def resolve(self, place_name: str) -> Optional[GeoCoordinate]:
        """Resolve a place name or alias to a GeoCoordinate."""
        if not place_name:
            return None
        cleaned = place_name.strip().lower()
        cleaned = re.sub(r"[!?,.:;\"'«»()]+$", "", cleaned).strip()
        if cleaned in self.catalog:
            return self.catalog[cleaned]

        for key, coord in self.catalog.items():
            if key == cleaned or (len(key) > 4 and key in cleaned):
                return coord
        return None

    def extract_places(self, text: str) -> List[str]:
        """Extract mentioned known geographical entities from text, mapped to canonical names."""
        if not text:
            return []
        lower = text.lower()
        found: List[str] = []
        for name in sorted(self.catalog.keys(), key=len, reverse=True):
            pattern = rf"\b{re.escape(name)}\b"
            if re.search(pattern, lower):
                canonical = CANONICAL_PLACE_MAPPING.get(name, name)
                if canonical not in found:
                    found.append(canonical)
        return found
