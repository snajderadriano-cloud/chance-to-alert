"""Smart filter for advertising, spam, and non-threat news noise in Telegram channels."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Pattern


class PostClassification(str, Enum):
    """Classification of an incoming Telegram message."""
    THREAT_SIGNAL = "THREAT_SIGNAL"
    ADVERTISEMENT = "ADVERTISEMENT"
    SCAM_OR_CASINO = "SCAM_OR_CASINO"
    CLICKBAIT_SPAM = "CLICKBAIT_SPAM"
    GENERAL_NEWS = "GENERAL_NEWS"
    MUNICIPAL_STATUS = "MUNICIPAL_STATUS"


@dataclass
class FilterResult:
    """Result of filtering a Telegram post."""
    is_threat_relevant: bool
    classification: PostClassification
    confidence: float
    detected_keywords: List[str]
    clean_text: str
    rejection_reason: Optional[str] = None


class ContentFilter:
    """Detects and suppresses ads, casino spam, clickbait, and unrelated news."""

    TRUSTED_RADAR_CHANNELS = {
        "kpszsu",
        "vanek_nikolaev",
        "war_monitor",
        "raketa_trevoga",
        "odessa_inform",
        "odessa_infonews",
        "shturval_media",
        "delta_odesa",
        "odessa_knight",
        "neptun_radar",
        "xydessa_live",
        "odesa_now",
        "suspilneodesa",
    }

    # Explicit advertising labels
    AD_PATTERNS: List[Pattern] = [
        re.compile(r"(?:^|\s)(#реклама|реклама|на\s+правах\s+реклами|партнерський\s+матеріал|erid\s*:\s*\w+)(?:\s|$)", re.I),
        re.compile(r"\b(промокод|знижк\w*|акція|купити\s+зі\s+знижкою|замовити|розпродаж|доставка\s+безкоштовна)\b", re.I),
    ]

    # Gambling, betting, casinos
    GAMBLING_PATTERNS: List[Pattern] = [
        re.compile(r"\b(казино|слоти|фріспін\w*|вейджер|ставка|парі|онлайн-казино|1xbet|parimatch|cosmolot|favbet|pin-up|slotor)\b", re.I),
        re.compile(r"\b(бонус\s+до\s+депозиту|бездепозитний\s+бонус|покрутити\s+слоти|джекпот)\b", re.I),
    ]

    # Financial scams, "easy money", crypto spam
    SCAM_PATTERNS: List[Pattern] = [
        re.compile(r"\b(пасивний\s+дохід|заробіток\s+від|схема\s+заробітку|безкоштовні\s+usdt|розіграш\s+грошей|айрдроп|airdrop)\b", re.I),
        re.compile(r"\b(заробляти\s+від\s+\$?\d+|грошовий\s+подарунок|вигравай\s+айфон|дарю\s+гроші)\b", re.I),
    ]

    # Clickbait links, invite traps, and fearmongering spam
    CLICKBAIT_PATTERNS: List[Pattern] = [
        re.compile(r"\b(підпишись|вхід\s+за\s+посиланням|посилання\s+в\s+шапці|читати\s+продовження|переходь\s+за\s+посиланням)\b", re.I),
        re.compile(r"\b(натискай\s+тут|детальніше\s+в\s+каналі|подати\s+заявку|клікніть\s+сюди|тисни\s+на\s+посилання)\b", re.I),
        re.compile(r"\b(відео\s+прильоту\s+без\s+цензури|кадри\s+без\s+цензури|списки\s+загиблих|куди\s+влучило\s+дивіться\s+в)\b", re.I),
        re.compile(r"t\.me/\+[A-Za-z0-9_-]+", re.I),
        re.compile(r"t\.me/joinchat/[A-Za-z0-9_-]+", re.I),
    ]

    # Genuine air threat indicators (both Ukrainian and Russian variants, telemetry, levels)
    THREAT_TRIGGER_PATTERNS: List[Pattern] = [
        # Aerial targets
        re.compile(r"\b(шахед\w*|бпла|мопед\w*|дрон\w*|ракета|ракети|ракет\w*|балістик\w*|баллистик\w*|іскандер\w*|искандер\w*|кинджал\w*|кинжал\w*|калібр\w*|калибр\w*|х-101|х-59|каб\w*|су-34|су-35|авіаці\w*|авиаци\w*|реактивн\w*)\b", re.I),
        # Alert / Radar movement verbs & telemetry
        re.compile(r"\b(тривог\w*|тревог\w*|відбій\w*|отбой\w*|вибух\w*|взрыв\w*|пуск\w*|виліт\w*|вылет\w*|курсом\s+на|в\s+напрямку|в\s+направлении|в\s+бік|в\s+сторону|підліт\w*|подлет\w*|фіксується|фиксируется|працює\s+ппо|работает\s+пво|робота\s+ппо|збито|сбито|чисто)\b", re.I),
        # Tactical vectors & distance
        re.compile(r"\b((з|с)\s+моря|(з|с)\s+криму|(с|из)\s+крыма|\d+\s+на\s+[а-яіїєґa-z]+|\d+\s*км)\b", re.I),
        # Urgent alarms & alert levels
        re.compile(r"\b(укриття|укрытие|пройдіть\s+в\s+укриття|внимание|небезпека|опасность|загроза|угроза|не\s+ігноруйте|рівень\s+тривоги|уровень\s+тревоги)\b", re.I),
        re.compile(r"\b(жовтий|желтый|червоний|красный)\s+(рівень|уровень)\b", re.I),
    ]

    def filter_post(self, text: str, channel_username: str = "") -> FilterResult:
        """Analyze a post text and determine if it is a genuine threat update or noise/ad."""
        if not text or not text.strip():
            return FilterResult(
                is_threat_relevant=False,
                classification=PostClassification.GENERAL_NEWS,
                confidence=1.0,
                detected_keywords=[],
                clean_text="",
                rejection_reason="Empty text",
            )

        lower = text.lower()
        detected_keywords: List[str] = []

        # 1. Check for Scam / Gambling
        for pattern in self.GAMBLING_PATTERNS:
            m = pattern.search(lower)
            if m:
                detected_keywords.append(m.group(0))
                return FilterResult(
                    is_threat_relevant=False,
                    classification=PostClassification.SCAM_OR_CASINO,
                    confidence=0.99,
                    detected_keywords=detected_keywords,
                    clean_text=text,
                    rejection_reason=f"Casino / gambling keyword detected: {m.group(0)}",
                )

        # 2. Check for Financial Scams
        for pattern in self.SCAM_PATTERNS:
            m = pattern.search(lower)
            if m:
                detected_keywords.append(m.group(0))
                return FilterResult(
                    is_threat_relevant=False,
                    classification=PostClassification.SCAM_OR_CASINO,
                    confidence=0.98,
                    detected_keywords=detected_keywords,
                    clean_text=text,
                    rejection_reason=f"Scam / crypto bait detected: {m.group(0)}",
                )

        # 3. Check for Explicit Ads
        for pattern in self.AD_PATTERNS:
            m = pattern.search(lower)
            if m:
                detected_keywords.append(m.group(0))
                return FilterResult(
                    is_threat_relevant=False,
                    classification=PostClassification.ADVERTISEMENT,
                    confidence=0.95,
                    detected_keywords=detected_keywords,
                    clean_text=text,
                    rejection_reason=f"Advertisement marker detected: {m.group(0)}",
                )

        # 4. Check for Clickbait invite traps
        for pattern in self.CLICKBAIT_PATTERNS:
            m = pattern.search(lower)
            if m:
                detected_keywords.append(m.group(0))
                # If there are NO verified threat triggers at all, it's pure clickbait
                has_threat_triggers = any(tp.search(lower) for tp in self.THREAT_TRIGGER_PATTERNS)
                if not has_threat_triggers:
                    return FilterResult(
                        is_threat_relevant=False,
                        classification=PostClassification.CLICKBAIT_SPAM,
                        confidence=0.95,
                        detected_keywords=detected_keywords,
                        clean_text=text,
                        rejection_reason=f"Clickbait spam detected: {m.group(0)}",
                    )

        # 5. Check if post contains genuine threat signals
        threat_matches: List[str] = []
        for pattern in self.THREAT_TRIGGER_PATTERNS:
            for match in pattern.finditer(lower):
                threat_matches.append(match.group(0))

        if threat_matches:
            return FilterResult(
                is_threat_relevant=True,
                classification=PostClassification.THREAT_SIGNAL,
                confidence=0.95,
                detected_keywords=threat_matches[:5],
                clean_text=text,
                rejection_reason=None,
            )

        # 5b. Trusted radar channel priority rule:
        # Channels whose primary sole purpose is tactical air defense tracking bypass news filter
        clean_user = channel_username.lower().lstrip("@")
        if clean_user in self.TRUSTED_RADAR_CHANNELS:
            return FilterResult(
                is_threat_relevant=True,
                classification=PostClassification.THREAT_SIGNAL,
                confidence=0.90,
                detected_keywords=["trusted_radar_telemetry"],
                clean_text=text,
                rejection_reason=None,
            )

        # 6. Post has no threat triggers -> General news / off-topic post (politics, local traffic, weather)
        return FilterResult(
            is_threat_relevant=False,
            classification=PostClassification.GENERAL_NEWS,
            confidence=0.90,
            detected_keywords=[],
            clean_text=text,
            rejection_reason="No aerial threat or air alert keywords found (general news/banter)",
        )
