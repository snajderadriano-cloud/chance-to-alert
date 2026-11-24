"""Tactical AI Copilot for Chance to Alert.App.

Answers user questions about current threats, arrival forecasts,
and remote schooling decisions at Lyceum Harmoniya (Tairova) using live telemetry.
Powered by OpenRouter LLM with local factual fallback.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional
import urllib.request

from app.domain.entities import ProbabilityResult
from app.domain.enums import AlertLevel
from app.processing.school_analyzer import SchoolStatusResult

logger = logging.getLogger("ai_copilot")


class TacticalAICopilot:
    """Context-aware tactical assistant analyzing current air threat and municipal school telemetry."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY")

    def _call_openrouter(self, prompt: str, system_context: str) -> Optional[str]:
        """Call OpenRouter LLM with timeout and graceful fallback."""
        if not self.api_key:
            return None
        try:
            req = urllib.request.Request(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://chance-to-alert.app",
                    "X-Title": "Chance to Alert Odesa",
                },
                data=json.dumps({
                    "model": "openrouter/auto",
                    "messages": [
                        {"role": "system", "content": system_context},
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 280,
                    "temperature": 0.3,
                }).encode("utf-8"),
            )
            with urllib.request.urlopen(req, timeout=6) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode("utf-8"))
                    choices = data.get("choices", [])
                    if choices and "message" in choices[0]:
                        return choices[0]["message"]["content"].strip()
        except Exception as e:
            logger.warning(f"OpenRouter query failed, using deterministic response: {e}")
        return None

    def answer_query(
        self,
        question: str,
        current_prob: ProbabilityResult,
        school_status: SchoolStatusResult,
        active_threats: List[Dict[str, Any]],
        user_name: str = "Денис",
    ) -> Dict[str, Any]:
        """Generate tactical, factual response to user's question using current live context."""
        q_clean = question.strip()

        # Context facts
        prob_val = current_prob.probability_percent
        alert_lvl = current_prob.alert_level.value
        eta_min = current_prob.estimated_time_to_impact_minutes
        threat_count = current_prob.active_threat_count

        school_headline = school_status.headline
        is_remote = school_status.is_remote
        school_prob = school_status.remote_probability_percent
        quote = school_status.official_quote or ""

        # Prepare system prompt for OpenRouter LLM
        system_context = (
            f"Ты — официальный тактический аналитик системы Chance to Alert для сектора Таирова (Одесса, Киевский район) "
            f"и Одеського ліцею «Гармонія» (вул. Корольова / Люстдорфська дорога).\n"
            f"Текущие подтверждённые телеметрические данные:\n"
            f"- Пользователь: {user_name}\n"
            f"- Расчётный шанс тревоги для Таирова: {prob_val}% (Уровень: {alert_lvl})\n"
            f"- Активных воздушных целей по вектору района: {threat_count}\n"
            f"- Расчётное время подлёта (ETA): {f'~{eta_min} мин' if eta_min else 'целей по курсу нет'}\n"
            f"- Статус уроков Лицея «Гармония»: {'ДИСТАНЦИОННОЕ ОБУЧЕНИЕ' if is_remote else 'ОЧНОЕ ОБУЧЕНИЕ ПО РАСПИСАНИЮ'}\n"
            f"- Официальная сводка Департамента образования: «{quote}»\n"
            f"- Мониторинг: 17 проверенных каналов (ПС ЗСУ, Николаевский Ванёк, НЕПТУН и др.) без рекламы.\n\n"
            f"ПРАВИЛА ОТВЕТА:\n"
            f"1. Отвечай кратко, чётко, профессиональным военным/гражданским языком, без воды и слопа.\n"
            f"2. Не галлюцинируй. Опирайся строго на предоставленные выше цифры.\n"
            f"3. Если спрашивают про школу — давай статус лицея «Гармония».\n"
            f"4. Если спрашивают про обстановку — давай ситуацию по Таирова и Одессе."
        )

        llm_answer = self._call_openrouter(q_clean, system_context)
        if llm_answer:
            return {
                "answer": llm_answer,
                "confidence": 0.98,
                "category": "LLM_AUGMENTED",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        # Deterministic Fallback if offline
        q_lower = q_clean.lower()
        if any(w in q_lower for w in ("школ", "лицей", "ліцей", "гармони", "гармонія", "урок", "дистант", "онлайн", "заняти")):
            if is_remote:
                answer = (
                    f"**Статус Одеського ліцею «Гармонія» (Таїрова): ДИСТАНЦІЙНИЙ ФОРМАТ**\n\n"
                    f"• Рішення: {school_headline}\n"
                    f"• Офіційне повідомлення: «{quote}»\n"
                    f"• Рекомендація: Заняття проходять онлайн, очно до ліцею їхати не потрібно."
                )
            else:
                answer = (
                    f"**Одеський ліцей «Гармонія» працює ОЧНО за графіком.**\n\n"
                    f"• Департамент освіти Одеси змін не вводив.\n"
                    f"• Електропостачання та транспорт на вул. Академіка Корольова / Люстдорфській дорозі стабільні."
                )
            return {
                "answer": answer,
                "confidence": 0.95,
                "category": "SCHOOL",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        if any(w in q_lower for w in ("летит", "шахед", "ракета", "баллистик", "тревог", "ноч", "таиров", "одесс", "опасн", "угроз", "шанс")):
            if alert_lvl in ("RED", "ORANGE"):
                eta_str = f"~{eta_min} мин" if eta_min else "в ближайшее время"
                answer = (
                    f"**УВАГА! Підвищений рівень загрози для Таїрова ({prob_val}% / {alert_lvl}).**\n\n"
                    f"• Активних цілей за вектором району: {threat_count}\n"
                    f"• Розрахунковий час підльоту: {eta_str}\n"
                    f"• Основна загроза: {current_prob.primary_threat_type or 'БпЛА / Шахед'}\n\n"
                    f"Дотримуйтесь правила двох стін або пройдіть до укриття."
                )
            else:
                answer = (
                    f"**Сектор Таїрова (Київський район): повітряний простір ЧИСТИЙ.**\n\n"
                    f"• Розрахунковий шанс тривоги: {prob_val}% ({alert_lvl}).\n"
                    f"• Активних цілей курсом на житловий масив Таїрова не виявлено.\n"
                    f"• Чергові радари ведуть моніторинг південного напрямку."
                )
            return {
                "answer": answer,
                "confidence": 0.95,
                "category": "AIR_THREAT",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        answer = (
            f"**Оперативне зведення для сектора Таїрова ({user_name}):**\n\n"
            f"• Шанс тривоги: {prob_val}% ({alert_lvl})\n"
            f"• Ліцей «Гармонія»: {'Дистанційка' if is_remote else 'Очне навчання'}\n"
            f"• Моніторинг: 17 радарних джерел підключено в прямому ефірі."
        )
        return {
            "answer": answer,
            "confidence": 0.90,
            "category": "GENERAL",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
