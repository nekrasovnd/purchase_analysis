# B2B-Center Handoff

Дата: `2026-06-18`

## Ready Prompt

Скопируй текст ниже в новый чат.

```text
Ты работаешь в репозитории:
D:\Nikita\Work\purchase_analysis

Сфокусируйся только на источнике B2B-Center.

Перед работой прочитай:
1. `docs/b2b_center_handoff_2026-06-18.md`
2. `docs/gpt54_handoff_prompt.md`
3. `docs/collaboration_prompts.md`
4. `docs/entity_resolution_protocol.md`

Текущая цель:
- не переоткрывать B2B-Center с нуля;
- использовать уже найденные рабочие части;
- честно учитывать антибот/403/captcha как внешний блокер, а не как "в источнике нет данных";
- сначала максимально добирать value из уже сохранённых raw HTML и локальных артефактов;
- только потом пытаться live-run маленькими батчами.

Что уже сделано:
- есть клиент `src/purchase_analysis/clients/b2b_center.py`
- есть source sprint `scripts/b2b_center_prompt2_source_sprint.py`
- есть offline re-enrichment `scripts/b2b_center_reenrich_saved_details.py`
- есть тесты `tests/test_b2b_center.py`
- market-next detail pages уже распарсены через inline `var __pinia=...` + `js2py`
- exact organization matching уже работает через `api/search/organizations/`
- search/list pages B2B сейчас часто упираются в anti-bot: captcha/rate-limit или plain 403 Forbidden

Правила:
- не запускать `run-all`;
- не делать вид, что B2B пустой, если live search blocked;
- не ломать текущий resolver-протокол;
- не добавлять в core name-only/title-only совпадения;
- не пытаться автоматом ломать captcha.

Что проверить первым делом:
1. `git status --short`
2. прогнать `python -m unittest discover -s tests -p test_b2b_center.py -v`
3. посмотреть уже сохранённые артефакты:
   - `data/raw/b2b_center/b2b_center_probe_7736663049/`
   - `output/source_sprints/b2b_center_probe_7736663049/`
   - `output/source_sprints/b2b_center_probe_7736663049_forbidden/`

Практический следующий шаг по умолчанию:
- сначала использовать `scripts/b2b_center_reenrich_saved_details.py`
- потом, только если нужно, пробовать новый очень маленький live batch

Если понадобится ручная помощь человека:
- проси только конкретный шаг: URL, фильтр, что сохранить, куда положить HTML/HAR/CSV
- не проси логин/пароль в чат
```

## Current State

### Что получилось

- Добавлен B2B-клиент:
  - `src/purchase_analysis/clients/b2b_center.py`
- Добавлен source sprint:
  - `scripts/b2b_center_prompt2_source_sprint.py`
- Добавлен офлайн-скрипт дообогащения:
  - `scripts/b2b_center_reenrich_saved_details.py`
- Добавлены тесты:
  - `tests/test_b2b_center.py`
- `market-next` detail pages теперь парсятся не по хрупкому DOM, а по inline-state:
  - из `var __pinia=...`
  - через `js2py`
- Клиент умеет детектить:
  - rate-limit / captcha page
  - plain `403 Forbidden` anti-bot page

### Что реально добыто

- В одном удачном старом probe по `ООО Сбербанк-Сервис` уже были найдены B2B-строки:
  - batch: `b2b_center_probe_7736663049`
  - items: `output/source_sprints/b2b_center_probe_7736663049/items.csv`
- После нового офлайн-дообогащения из уже сохранённых detail HTML:
  - output: `output/source_sprints/b2b_center_probe_7736663049/items_reenriched.csv`
  - всего строк в batch: `97`
  - detail-карточек успешно дообогащено: `6`
  - priced rows поднято: `2`
  - blocked detail cards: `2`
- Поднятые цены:
  - procedure `3688284` -> `10331548 RUB без НДС`
  - procedure `3695172` -> `852905 RUB без НДС`

## What Works

### 1. Exact organization lookup

Работает endpoint:

- `https://www.b2b-center.ru/api/search/organizations/`

Через него уже работает поиск организации по:

- `ИНН`
- `ОГРН`
- `КПП`
- точному названию

Дальше кандидат прогоняется через общий resolver:

- `classify_entity_match(...)`

То есть проблема сейчас не в entity matching, а именно в transport/search pages.

### 2. Market-next detail parsing

Работает парсинг сохранённых `market-next` detail HTML.

Из них вытаскиваются как минимум:

- `subject`
- `organizer_name`
- `organizer_profile_url`
- `published_at`
- `deadline_at`
- `positions_count`
- `delivery_address`
- `status`
- `category`
- `total price`, если B2B её раскрыл в `trade_result_money`

### 3. Offline re-enrichment

Рабочий путь:

```powershell
python scripts/b2b_center_reenrich_saved_details.py
```

Он не требует новых запросов к B2B и безопасно поднимает value из уже сохранённых raw detail HTML.

## Problems

### Главная проблема

Сейчас B2B-Center режет live transport.

Наблюдались 2 режима блокировки:

1. captcha/rate-limit page
   - текст про `превышен максимальный лимит скорости просмотра страниц`
   - текст про `регламент площадки не допускает использование ботов`

2. plain `403 Forbidden`
   - с текстом вида:
     - `If you are not a bot, please copy the report and send it to our support team.`

### Где именно блокирует

Чаще всего блокируются:

- search/list pages вида:
  - `/market/?searching=1&trade=all&firm_id=...`
  - `/market/?searching=1&trade=all&customer_id=...`

Также в какой-то момент live-block распространился даже на:

- root `/`
- `/market/`
- `/firms/...`
- direct `market-next` URLs

То есть текущий внешний блокер стал сильнее, чем был в начале sprint.

## What Was Tried

Ниже уже проверенные гипотезы, чтобы их не переоткрывать с нуля.

### 1. Обычный requests с browser headers

Что делали:

- `requests.Session()`
- browser-like `User-Agent`
- `Accept-Language`

Результат:

- organization search endpoint иногда работает
- search/list pages всё равно часто уходят в captcha/rate-limit или 403

### 2. Дробление по датам

Что делали:

- `show=all`
- `date_start_dmy/date_end_dmy`
- рекурсивное деление окна по датам

Зачем:

- обойти кривую пагинацию B2B

Результат:

- технически логика рабочая
- но transport всё равно упирается в anti-bot

### 3. Throttling / retries

Что делали:

- паузы между запросами
- retry loops

Результат:

- не решило проблему transport
- иногда меняло тип блока с "какое-то время работало" на "сразу blocked"

### 4. Playwright / headless browser

Что делали:

- открывали B2B через браузер
- проверяли search pages
- проверяли detail pages
- снимали текст и сеть

Результат:

- search/list pages всё равно могли уходить в captcha
- browser fingerprint сам по себе проблему не снял
- зато именно через browser inspection удалось понять структуру `market-next`

### 5. Попытка вытащить данные из DOM `market-next`

Что делали:

- анализировали rendered text
- искали лейблы вроде:
  - `Общая сумма закупки`
  - `Количество позиций`
  - `Организатор`
  - `Адрес поставки / оказания услуг`

Результат:

- визуально поля видны
- но надёжнее оказалось парсить не DOM, а inline `__pinia`

### 6. Разбор inline-state `var __pinia=...`

Что делали:

- извлекали встроенный JS-state из detail page
- парсили его через `js2py`

Результат:

- это сработало
- это текущий лучший способ парсить `market-next`

### 7. Альтернативные публичные входы B2B

Что делали:

- пробовали `/firms/...`
- смотрели `robots.txt`
- смотрели `sitemap.xml`
- пробовали "прогреть" сессию перед search

Результат:

- нового устойчивого transport path не нашли
- `/firms/...` тоже мог возвращать `403 Forbidden`
- `sitemap.xml` полезного обходного канала не дал

## Key Artifacts

### Код

- `src/purchase_analysis/clients/b2b_center.py`
- `scripts/b2b_center_prompt2_source_sprint.py`
- `scripts/b2b_center_reenrich_saved_details.py`
- `tests/test_b2b_center.py`

### Raw

- `data/raw/b2b_center/b2b_center_probe_7736663049/`

### Outputs

- `output/source_sprints/b2b_center_probe_7736663049/items.csv`
- `output/source_sprints/b2b_center_probe_7736663049/items_reenriched.csv`
- `output/source_sprints/b2b_center_probe_7736663049/report.md`
- `output/source_sprints/b2b_center_probe_7736663049_forbidden/overflow_windows.csv`
- `output/source_sprints/b2b_center_probe_7736663049_forbidden/report.md`

## Recommended Next Steps

### Safe default

1. Не лезть сразу в новый большой live-run.
2. Сначала добрать всё возможное из уже сохранённых raw detail HTML.
3. Если появятся новые локальные HTML от ручного шага, сразу прогнать через offline re-enrichment.

### Если пробовать live снова

Делать только маленьким батчем:

- 1 юрлицо
- 1 роль
- 1 короткое окно
- без массового detail-fetch

И сразу сохранять:

- raw HTML
- blocked pages
- overflow report

### Если нужен человек

Лучший ручной шаг:

- открыть конкретный B2B search URL в обычном браузере
- сохранить HTML результата или HAR
- положить файл в локальную папку проекта

Не просить:

- логин
- пароль
- "просто пройти капчу за меня" без артефакта

## Useful Commands

Проверка тестов:

```powershell
$env:PYTHONPATH='src'
python -m unittest discover -s tests -p test_b2b_center.py -v
```

Полный unit test sweep:

```powershell
$env:PYTHONPATH='src'
python -m unittest discover -s tests -v
```

Офлайн-дообогащение:

```powershell
python scripts/b2b_center_reenrich_saved_details.py
```

## Honest Bottom Line

По B2B уже есть реальный прогресс:

- entity resolution работает
- `market-next` detail parsing решён
- из saved HTML подняты новые поля и 2 цены

Но live B2B search сейчас ограничен внешним антиботом. Это не значит, что B2B бесполезен; это значит, что следующий шаг должен либо использовать уже сохранённые артефакты, либо идти через маленький ручной/browser-assisted flow, а не через большой автоматический прогон.
