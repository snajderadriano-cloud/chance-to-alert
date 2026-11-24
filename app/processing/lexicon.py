"""Ukrainian military monitoring lexicon and regex patterns."""

from __future__ import annotations

import re
from typing import Dict, List, Pattern

from app.domain.enums import ThreatType


THREAT_PATTERNS: Dict[ThreatType, List[Pattern]] = {
    ThreatType.SHAHED: [
        re.compile(r"\b(шахед\w*|shahed|бпла|мопед\w*|дрон\w*|реактивн\w*|безпілотник\w*|беспилотник\w*)\b", re.IGNORECASE),
        re.compile(r"\b(герань|герані|гербера|гербери)\b", re.IGNORECASE),
        re.compile(r"\b(жовтий|желтый|червоний|красный)\s+(рівень|уровень)\b", re.IGNORECASE),
    ],
    ThreatType.BALLISTIC: [
        re.compile(r"\b(балістик\w*|баллистик\w*)\b", re.IGNORECASE),
        re.compile(r"\b(іскандер\w*|искандер\w*|кинджал\w*|кинжал\w*)\b", re.IGNORECASE),
        re.compile(r"\b(загроза\s+застосування\s+балістичного\s+озброєння|угроза\s+баллистики)\b", re.IGNORECASE),
    ],
    ThreatType.CRUISE_MISSILE: [
        re.compile(r"\b(крилат\w*|крылат\w*|ракета|ракети|ракет\w*)\b", re.IGNORECASE),
        re.compile(r"\b(калібр\w*|калибр\w*|х-101|х101|х-555|х555|х-59|х59|х-69|х69)\b", re.IGNORECASE),
    ],
    ThreatType.TACTICAL_AVIATION: [
        re.compile(r"\b(тактичн\w*\s+авіаці\w*|тактическ\w*\s+авиаци\w*|активность\s+авиации|пуски\s+каб|каб\w*)\b", re.IGNORECASE),
        re.compile(r"\b(су-34|су-35|су34|су35|ту-22|ту22|ту-95|ту95)\b", re.IGNORECASE),
    ],
    ThreatType.RECON_DRONE: [
        re.compile(r"\b(розвідник\w*|разведчик\w*|розвідувальн\w*\s+дрон|разведывательн\w*\s+дрон|розвід-бпла|бпла-розвідник)\b", re.IGNORECASE),
        re.compile(r"\b(орлан|орлан-10|zala|зала|суперкам|supercam)\b", re.IGNORECASE),
    ],
}

CANCELLATION_PATTERNS: List[Pattern] = [
    re.compile(r"\b(відбій\w*|отбой\w*|чисто|загроза\s+минула|угроза\s+миновала|відбій\s+загрози)\b", re.IGNORECASE),
    re.compile(r"\b(дорозвідка\w*|доразведка\w*)\b", re.IGNORECASE),
]

DIRECTION_PATTERNS: Dict[str, Pattern] = {
    "towards_odesa": re.compile(r"\b(курсом\s+на|в\s+напрямку|в\s+направлении|в\s+бік|в\s+сторону|на)\s+(одес\w*|чорноморськ\w*|черноморск\w*|черноморк\w*|чорноморк\w*|таїров\w*|таиров\w*|совиньон\w*|совіньйон\w*|гармон\w*|южн\w*|фонтанк\w*)", re.IGNORECASE),
    "away_from_odesa": re.compile(r"\b(не\s+в\s+бік|не\s+на|повз|мимо|віддаля\w*|удаля\w*|в\s+інший\s+бік|в\s+другую\s+сторону)\s+(одес\w*|чорноморськ\w*|черноморск\w*)", re.IGNORECASE),
    "sea_approach": re.compile(r"\b((з|с)\s+моря|(чорного|черного)\s+моря|акваторі\w*|акватори\w*)\b", re.IGNORECASE),
    "crimea_approach": re.compile(r"\b((з|с)\s+криму|(с|из)\s+крыма|чауда|мис\s+чауда|севастополь|джанкой)\b", re.IGNORECASE),
    "mykolaiv_transit": re.compile(r"\b(через\s+миколаївщину|з\s+миколаївщини|через\s+николаевскую|очаків|очаков|коблове|коблево)\b", re.IGNORECASE),
}

QUANTITY_PATTERNS: List[Pattern] = [
    re.compile(r"(\d+)\s*(?:х|x|\-|\s)*(?:бпла|шахед|ракет|ціл|штук|од|на\s+[а-яіїєґa-z]+)", re.IGNORECASE),
    re.compile(r"^(\d+)\s+на\s+[а-яіїєґa-z]+", re.IGNORECASE),
    re.compile(r"\b(декілька|несколько|пара|два|дві|две)\b", re.IGNORECASE),
    re.compile(r"\b(група|группа|рій|рой|зграя|стая|кілька\s+груп|несколько\s+групп)\b", re.IGNORECASE),
]
