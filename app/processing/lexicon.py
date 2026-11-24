"""Ukrainian military monitoring lexicon and regex patterns."""

from __future__ import annotations

import re
from typing import Dict, List, Pattern

from app.domain.enums import ThreatType


THREAT_PATTERNS: Dict[ThreatType, List[Pattern]] = {
    ThreatType.SHAHED: [
        re.compile(r"\b(шахед|шахеди|шахедів|шахедами|шахеда|shahed|бпла|мопед|мопеди|дрон|дрони|дронів)\b", re.IGNORECASE),
        re.compile(r"\b(герань|герані|гербера|гербери)\b", re.IGNORECASE),
    ],
    ThreatType.BALLISTIC: [
        re.compile(r"\b(балістик|балістика|балістична|балістику|балістикою)\b", re.IGNORECASE),
        re.compile(r"\b(іскандер|іскандери|іскандера|кинджал|кинджали|кинжал)\b", re.IGNORECASE),
        re.compile(r"\b(загроза\s+застосування\s+балістичного\s+озброєння)\b", re.IGNORECASE),
    ],
    ThreatType.CRUISE_MISSILE: [
        re.compile(r"\b(крилат|крилата|крилаті|крилатих|ракета|ракети|ракет|ракетами)\b", re.IGNORECASE),
        re.compile(r"\b(калібр|калібри|калібрів|х-101|х101|х-555|х555|х-59|х59|х-69|х69)\b", re.IGNORECASE),
    ],
    ThreatType.TACTICAL_AVIATION: [
        re.compile(r"\b(тактичн\w*\s+авіаці\w*|активність\s+авіації|пуски\s+каб|каб|каби|кабів)\b", re.IGNORECASE),
        re.compile(r"\b(су-34|су-35|су34|су35|ту-22|ту22|ту-95|ту95)\b", re.IGNORECASE),
    ],
    ThreatType.RECON_DRONE: [
        re.compile(r"\b(розвідник|розвідувальн\w*\s+дрон|розвід-бпла|бпла-розвідник)\b", re.IGNORECASE),
        re.compile(r"\b(орлан|орлан-10|zala|зала|суперкам|supercam)\b", re.IGNORECASE),
    ],
}

CANCELLATION_PATTERNS: List[Pattern] = [
    re.compile(r"\b(відбій|відбою|відбій\s+тривоги|чисто|загроза\s+минула|відбій\s+загрози)\b", re.IGNORECASE),
    re.compile(r"\b(дорозвідка|дорозвідка\s+повітряного\s+простору)\b", re.IGNORECASE),
]

DIRECTION_PATTERNS: Dict[str, Pattern] = {
    "towards_odesa": re.compile(r"\b(курсом\s+на|в\s+напрямку|в\s+бік|на)\s+(одес|чорноморськ|южне|фонтанк)", re.IGNORECASE),
    "away_from_odesa": re.compile(r"\b(не\s+в\s+бік|не\s+на|повз|віддаля\w*|в\s+інший\s+бік)\s+(одес|чорноморськ)", re.IGNORECASE),
    "sea_approach": re.compile(r"\b(з\s+моря|чорного\s+моря|акваторі\w*\s+чорного\s+моря)\b", re.IGNORECASE),
    "crimea_approach": re.compile(r"\b(з\s+криму|чауда|мис\s+чауда|севастополь|джанкой)\b", re.IGNORECASE),
    "mykolaiv_transit": re.compile(r"\b(через\s+миколаївщину|з\s+миколаївщини|очаків|коблове)\b", re.IGNORECASE),
}

QUANTITY_PATTERNS: List[Pattern] = [
    re.compile(r"(\d+)\s*(?:х|x|\-|\s)*(?:бпла|шахед|ракет|ціл|штук|од)", re.IGNORECASE),
    re.compile(r"\b(декілька|пара|два|дві)\b", re.IGNORECASE),
    re.compile(r"\b(група|рій|зграя|кілька\s+груп)\b", re.IGNORECASE),
]
