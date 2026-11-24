# Руководство по интеграции (iOS Shortcuts, виджеты, каналы) 📱

В этом руководстве описано, как подключить созданный бэкенд к смартфону, создать шорткат в iOS, виджет на рабочий стол, настроить мониторинг Telegram-каналов и фильтрацию рекламы.

---

## 1. Быстрый шорткат для iPhone (Apple Shortcuts)

С помощью встроенного приложения **«Команды» (Shortcuts)** на iOS можно настроить:
1. Кнопку на рабочем столе для проверки шанса тревоги;
2. Автоматическое утреннее голосовое оповещение о **дистанционном обучении в школе** и шансе тревоги.

### Утренний шорткат «Учёба и Тревога»:
1. Откройте приложение **Команды** на iPhone и нажмите **+**.
2. Добавьте действие **«Получить содержимое URL» (Get Contents of URL)**:
   - URL: `http://<IP_СЕРВЕРА>:8000/api/v1/probability?preset=odesa_district`
   - Метод: `GET`
3. Добавьте действие **«Получить значение словаря»**:
   - Ключ: `school_status.headline` (получает статус «Школи Одеси навчаються ДИСТАНЦІЙНО» или «Школи працюють очно»)
4. Добавьте действие **«Получить значение словаря»**:
   - Ключ: `probability_percent` (получает текущий шанс тревоги)
5. Добавьте действие **«Показать уведомление»** или **«Произнести текст»**:
   - Текст: *«Одесса. Шанс тревоги: [Шанс]%. Статус школы: [Статус]»*.

---

## 2. Интерактивный виджет на рабочий стол iPhone (Scriptable)

Бесплатное приложение **Scriptable** в App Store позволяет вывести красивый цветной виджет с двумя карточками: **Шанс Тревоги** и **Статус Учёбы / Дистанционки**.

```javascript
const API_URL = "http://<IP_СЕРВЕРА>:8000/api/v1/probability?preset=odesa_district";

let req = new Request(API_URL);
let data = await req.loadJSON();

let widget = new ListWidget();
widget.setPadding(12, 12, 12, 12);

// Фон меняется по уровню тревоги
if (data.alert_level === "RED") {
  widget.backgroundColor = new Color("#7f1d1d"); // Красный
} else if (data.alert_level === "ORANGE") {
  widget.backgroundColor = new Color("#7c2d12"); // Оранжевый
} else if (data.alert_level === "YELLOW") {
  widget.backgroundColor = new Color("#713f12"); // Желтый
} else {
  widget.backgroundColor = new Color("#064e3b"); // Спокойный зеленый
}

// Заголовок
let header = widget.addText("🛡️ ОДЕССА: РАДАР & ДИСТАНТ");
header.font = Font.boldSystemFont(11);
header.textColor = new Color("#f8fafc");

widget.addSpacer(6);

// Шанс тревоги
let chance = widget.addText(data.probability_percent + "% Шанс");
chance.font = Font.heavySystemFont(32);
chance.textColor = Color.white();

widget.addSpacer(4);

// Блок статуса школы / дистанционки
let school = data.school_status;
let schoolIcon = school.is_remote ? "💻 " : "🏫 ";
let schoolText = widget.addText(schoolIcon + (school.is_remote ? "ДИСТАНЦИОНКА" : "Очное обучение"));
schoolText.font = Font.boldSystemFont(13);
schoolText.textColor = school.is_remote ? new Color("#fde047") : new Color("#86efac");

if (school.infrastructure_factors && school.infrastructure_factors.length > 0) {
  let note = widget.addText("⚠️ " + school.infrastructure_factors[0]);
  note.font = Font.systemFont(10);
  note.textColor = new Color("#e2e8f0");
}

Script.setWidget(widget);
Script.complete();
widget.presentMedium();
```

---

## 3. Фильтрация рекламы, спама и новостного шума

В файле `config/channels.yaml` подключены каналы разных типов. 
В каналах новостей и городских пабликах (`xydessa_live`, `UaOnlii`, `times_ukraina`, `voynareal`) работает автоматический интеллектуальный фильтр `ContentFilter`:

1. **Блокировка рекламы и казино**:
   - Посты с хештегами `#реклама`, промокодами, ссылками на слоты, 1xbet, казино, бонусами к депозиту или финансовыми схемами **автоматически отбрасываются**.
2. **Блокировка кликбейта**:
   - «Читайте продолжение по ссылке», скрытые ссылки `t.me/+...`, «Куда прилетело смотрите тут» — **блокируются**.
3. **Фильтрация обычных новостей**:
   - Политика, курс валют, дорожные ДТП и бытовые новости **не создают тревог**.
4. **Сквозной пропуск реальных угроз**:
   - Если даже в новостном канале выходит срочный пост: *«В Одесі пролунав вибух! Працює ППО!»*, фильтр распознает маркеры опасности и передает сообщение в расчет вероятности!
