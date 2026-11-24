# Спецификация REST & WebSocket API (API Specification) 🔌

Базовый URL: `http://localhost:8000/api/v1`

---

## 1. Получение текущего шанса тревоги и статуса школ

### `GET /api/v1/probability`
Возвращает актуальный расчет вероятности тревоги, уровень опасности, ETA, текстовую сводку и **статус дистанционного обучения в школах Одессы**.

**Параметры запроса:**
- `preset` *(string, optional, default: "odesa_district")*: идентификатор пресета района (`odesa_district` или `odesa_oblast`).

**Пример ответа (200 OK):**
```json
{
  "target_district": "odesa_district",
  "probability_percent": 82,
  "alert_level": "RED",
  "active_threat_count": 2,
  "primary_threat_type": "SHAHED",
  "estimated_time_to_impact_minutes": 18,
  "contributing_threats": [
    {
      "threat_id": "97a61d67-4e0e-436f-bca1-74400e47959c",
      "threat_type": "SHAHED",
      "raw_probability": 0.91,
      "decayed_probability": 0.76,
      "distance_km": 34.2,
      "heading_factor": 0.98,
      "time_to_impact_minutes": 18.0,
      "description": "SHAHED x4 at 34.2 km ETA ~18m"
    }
  ],
  "school_status": {
    "is_remote": true,
    "status": "OFFICIAL_REMOTE",
    "remote_probability_percent": 100,
    "headline": "Школи Одеси навчаються ДИСТАНЦІЙНО (Офіційно)",
    "official_quote": "Усі школярі сьогодні навчаються дистанційно. Електротранспорт не курсує...",
    "source_channel": "dep_osvity",
    "infrastructure_factors": [
      "Проблеми з електропостачанням",
      "Відсутність опалення в місті"
    ],
    "updated_at": "2026-11-23T13:30:00Z"
  },
  "summary": "RED Alert (82%): 2 active threat track(s) for odesa_district. Primary: SHAHED at 34.2 km ETA ~18m.",
  "calculated_at": "2026-11-23T13:30:00Z"
}
```

---

## 2. Статус дистанционного обучения в школах

### `GET /api/v1/school/status`
Специальный легковесный эндпоинт для виджета или утреннего шортката на телефоне:
```json
{
  "is_remote": true,
  "status": "OFFICIAL_REMOTE",
  "remote_probability_percent": 100,
  "headline": "Школи Одеси навчаються ДИСТАНЦІЙНО (Офіційно)",
  "official_quote": "Усі школярі сьогодні навчаються дистанційно...",
  "source_channel": "dep_osvity",
  "infrastructure_factors": [
    "Проблеми з електропостачанням",
    "Зупинка міського електротранспорту"
  ],
  "updated_at": "2026-11-23T13:30:00Z"
}
```

---

## 3. Список активных угроз

### `GET /api/v1/threats/current`
Возвращает список всех активных целей в воздухе (отфильтрованных от рекламы и спама).

---

## 4. История событий

### `GET /api/v1/threats/history`
Возвращает журнал зафиксированных событий с пагинацией (`limit`, `offset`).

---

## 5. Симуляция / Прием сообщений

### `POST /api/v1/simulate`
Принимает текст поста из Telegram, прогоняет через:
1. `ContentFilter`: фильтрация рекламы, казино, скама, спам-ссылок и нерелевантных новостей.
2. `SchoolRemoteAnalyzer`: анализ решений Департамента образования и графиков света.
3. `ThreatParser`: выделение векторов и расчет шанса.

**Тело запроса:**
```json
{
  "text": "3х БПЛА Shahed курсом на Одесу з моря!",
  "channel": "vanek_nikolaev",
  "quantity": 3
}
```

---

## 6. WebSocket поток в реальном времени

### `WS /api/v1/ws`
Двусторонний сокет. Мгновенно рассылает обновления клиентам при появлении новых сигналов, пересчете вероятности или решениях по школам.
