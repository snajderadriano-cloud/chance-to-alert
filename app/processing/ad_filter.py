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

    # Genuine air threat indicators (must have at least one to qualify as threat)
    THREAT_TRIGGER_PATTERNS: List[Pattern] = [
        # Aerial targets
        re.compile(r"\b(шахед|шахеди|шахедів|бпла|мопед|мопеди|дрон|дрони|ракета|ракети|ракет|балістик\w*|іскандер\w*|кинджал\w*|калібр\w*|х-101|х-59|каб\w*|су-34|су-35|авіаці\w*)\b", re.I),
        # Alert / Radar movement verbs
        re.compile(r"\b(тривог\w*|відбій|відбою|вибух\w*|пуск\w*|виліт\w*|курсом\s+на|в\s+напрямку|в\s+бік|підліт\w*|фіксується|працює\s+ппо|робота\s+ппо|збито|чисто)\b", re.I),
        # Urgent alarms
        re.compile(r"\b(укриття|пройдіть\s+в\s+укриття|небезпека|загроза|не\s+ігноруйте)\b", re.I),
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

        # 6. Post has no threat triggers -> General news / off-topic post (politics, local traffic, weather)
        return FilterResult(
            is_threat_relevant=False,
            classification=PostClassification.GENERAL_NEWS,
            confidence=0.90,
            detected_keywords=[],
            clean_text=text,
            rejection_reason="No aerial threat or air alert keywords found (general news/banter)",
        )
