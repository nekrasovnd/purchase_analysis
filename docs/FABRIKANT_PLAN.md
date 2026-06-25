# Fabrikant.ru — план реализации source sprint

Статус: **идея / не реализовано**. Документ описывает технический подход для написания `scripts/fabrikant_prompt2_source_sprint_v2.py` и `src/purchase_analysis/clients/fabrikant.py` в соответствии со стандартами проекта.

---

## Что известно о Fabrikant

| Параметр | Значение |
|---|---|
| URL | `https://www.fabrikant.ru` |
| Технология | Next.js App Router (React Server Components) |
| Авторизация | Не требуется для просмотра |
| Bot-block | Лёгкий — без JS fingerprint блокировок не обнаружено |
| Размер | ~1.2 млн процедур (поле `countAll` в RSC payload) |
| Секции | Закупки по 44-ФЗ, по 223-ФЗ, коммерческие |

### RSC endpoint

```
GET https://www.fabrikant.ru/procedure/search/purchases
Headers:
  Accept: text/x-component
  RSC: 1
```

Возвращает Next.js RSC payload (line-based формат):

```
1:"$Sreact.fragment"
2:I[40437, [...chunks], ...]
...
N:["$", "$Lc2", null, {"type":"purchases","countAll":1243397,"lastTrade":{...}}]
```

Поле с данными о процедурах находится в строке с `"type":"purchases"`.

### Проблема фильтрации

URL-параметры `?customer_inn=...`, `?organizer_inn=...`, `?inn=...` — **игнорируются**. `countAll` не меняется. Правильный способ передачи фильтра неизвестен без анализа network calls в браузере.

---

## Шаг 0: разведка API (обязательна перед реализацией)

> [!IMPORTANT]
> Без этого шага реализацию начинать бессмысленно — правильные параметры фильтра неизвестны.

Открыть Chrome DevTools → Network → XHR/Fetch. Перейти на:
```
https://www.fabrikant.ru/procedure/search/purchases
```
Ввести ИНН в поле фильтра, применить. Найти запрос с типом `text/x-component` или `application/json` где в response изменился `countAll`.

Записать:
- точный URL запроса
- точные query params / тело POST
- заголовки (особенно `Cookie`, `X-CSRF-Token`, если есть)

Это займёт ~10 минут и даст точный API endpoint.

---

## Архитектура клиента

По образцу `src/purchase_analysis/clients/b2b_center.py`.

### `src/purchase_analysis/clients/fabrikant.py`

```python
from __future__ import annotations

from dataclasses import asdict, dataclass
from urllib.parse import urljoin
import json
import re

import requests

from purchase_analysis.utils.text import normalize_spaces, parse_ru_decimal

BASE_URL = "https://www.fabrikant.ru"
SEARCH_URL = f"{BASE_URL}/procedure/search/purchases"  # уточнить после разведки

# Next.js RSC — заголовки для получения данных без JS рендеринга
RSC_HEADERS = {
    "Accept": "text/x-component",
    "RSC": "1",
    "Next-Router-Prefetch": "1",
}


@dataclass(slots=True)
class FabrikantSearchItem:
    source_system: str
    platform_section: str
    entity_name: str
    customer_query: str
    procedure_number: str
    lot_number: str
    subject: str
    customer_name: str
    customer_inn: str
    region: str
    status: str
    tender_type: str
    price_rub: float | None
    deadline_at: str | None
    detail_url: str
    tags: str
    published_at: str | None
    application_deadline: str | None
    method_name: str
    currency: str
    organizer_name: str
    organizer_inn: str


def create_session(timeout: int = 30) -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        ),
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.7,en;q=0.6",
    })
    session.request_timeout = timeout
    return session


def build_search_params(
    *,
    customer_inn: str | None = None,
    organizer_inn: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, str]:
    """
    Собрать query params для поиска процедур.
    ВНИМАНИЕ: точные имена параметров нужно уточнить через browser devtools.
    """
    params: dict[str, str] = {}
    if customer_inn:
        params["customer_inn"] = normalize_spaces(customer_inn)   # уточнить имя
    if organizer_inn:
        params["organizer_inn"] = normalize_spaces(organizer_inn) # уточнить имя
    if date_from:
        params["date_from"] = normalize_spaces(date_from)
    if date_to:
        params["date_to"] = normalize_spaces(date_to)
    params["page_number"] = str(page)
    return params


def _extract_rsc_data(rsc_text: str) -> dict:
    """
    Разобрать RSC (React Server Components) payload.
    Формат: каждая строка — `ID:data`, data — JSON.
    Ищем строку с ключом 'countAll' (содержит данные поиска).
    """
    for line in rsc_text.split("\n"):
        if "countAll" not in line:
            continue
        colon_idx = line.find(":")
        if colon_idx < 0:
            continue
        raw = line[colon_idx + 1:]
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            continue
        result = _find_count_all_node(parsed)
        if result is not None:
            return result
    return {}


def _find_count_all_node(obj: object, depth: int = 0) -> dict | None:
    if depth > 8:
        return None
    if isinstance(obj, dict) and "countAll" in obj:
        return obj
    if isinstance(obj, list):
        for item in obj:
            found = _find_count_all_node(item, depth + 1)
            if found is not None:
                return found
    if isinstance(obj, dict):
        for value in obj.values():
            found = _find_count_all_node(value, depth + 1)
            if found is not None:
                return found
    return None


def fetch_search_page(
    *,
    customer_inn: str | None = None,
    organizer_inn: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    page: int = 1,
    page_size: int = 20,
    session: requests.Session | None = None,
    timeout: int = 30,
) -> tuple[dict, str]:
    """Получить одну страницу результатов поиска. Возвращает (rsc_data_node, url)."""
    session = session or create_session(timeout=timeout)
    params = build_search_params(
        customer_inn=customer_inn,
        organizer_inn=organizer_inn,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )
    response = session.get(
        SEARCH_URL,
        params=params,
        headers=RSC_HEADERS,
        timeout=timeout,
    )
    response.raise_for_status()
    return _extract_rsc_data(response.text), str(response.url)


def parse_total(rsc_data: dict) -> int:
    return int(rsc_data.get("countAll", 0))


def parse_search_items(
    rsc_data: dict,
    *,
    entity_name: str,
    customer_query: str,
) -> list[FabrikantSearchItem]:
    """
    Разобрать список процедур из RSC data node.
    ВНИМАНИЕ: точная структура полей зависит от реального RSC payload.
    Нужно уточнить имена полей после разведки.
    """
    procedures = rsc_data.get("procedures") or rsc_data.get("items") or []
    items: list[FabrikantSearchItem] = []
    for proc in procedures:
        if not isinstance(proc, dict):
            continue
        # Имена полей — предположительные, уточнить по реальному RSC
        procedure_number = normalize_spaces(str(proc.get("id") or proc.get("number") or ""))
        subject = normalize_spaces(proc.get("title") or proc.get("subject") or "")
        customer = proc.get("customer") or {}
        organizer = proc.get("organizer") or proc.get("organiser") or {}
        price_raw = proc.get("price") or proc.get("startPrice") or proc.get("nmck")
        items.append(
            FabrikantSearchItem(
                source_system="fabrikant",
                platform_section=normalize_spaces(proc.get("section") or ""),
                entity_name=entity_name,
                customer_query=customer_query,
                procedure_number=procedure_number,
                lot_number="1",
                subject=subject,
                customer_name=normalize_spaces(
                    customer.get("name") or customer.get("fullName") or ""
                ),
                customer_inn=normalize_spaces(customer.get("inn") or ""),
                region=normalize_spaces(proc.get("region") or ""),
                status=normalize_spaces(proc.get("status") or ""),
                tender_type=normalize_spaces(proc.get("type") or ""),
                price_rub=parse_ru_decimal(str(price_raw)) if price_raw else None,
                deadline_at=normalize_spaces(proc.get("deadlineAt") or proc.get("deadline") or "") or None,
                detail_url=urljoin(BASE_URL, normalize_spaces(proc.get("url") or proc.get("link") or "")),
                tags="",
                published_at=normalize_spaces(proc.get("publishedAt") or proc.get("datePublished") or "") or None,
                application_deadline=normalize_spaces(proc.get("applicationDeadline") or "") or None,
                method_name=normalize_spaces(proc.get("methodName") or ""),
                currency=normalize_spaces(proc.get("currency") or "RUB"),
                organizer_name=normalize_spaces(
                    organizer.get("name") or organizer.get("fullName") or ""
                ),
                organizer_inn=normalize_spaces(organizer.get("inn") or ""),
            )
        )
    return items


def search_item_to_dict(item: FabrikantSearchItem) -> dict:
    return asdict(item)
```

---

## Архитектура скрипта

По образцу `scripts/b2b_center_prompt2_source_sprint_v2.py`.

### `scripts/fabrikant_prompt2_source_sprint_v2.py` — скелет

```python
# Ключевые аргументы (как в b2b_center):
# --batch-name, --inns, --throttle-seconds, --request-timeout
# --resume (пропускать entity уже в summary.csv)
# --browser-profile (если RSC без JS не работает)

def candidate_queries(entity: EntityIdentity) -> list[str]:
    """
    Для Fabrikant поиск ведётся по ИНН напрямую.
    Нет промежуточного поиска организаций (в отличие от B2B-Center).
    """
    return entity_resolution.build_search_terms(entity, source_system="fabrikant")
```

### Стратегия поиска

Fabrikant не требует предварительного поиска org_id (в отличие от B2B-Center). Запрос делается напрямую по ИНН:

```
1. customer_inn=<inn>  → закупки где entity — заказчик
2. organizer_inn=<inn> → закупки где entity — организатор
3. Дедупликация по procedure_number (аналогично B2B-Center)
4. Пагинация: page=1..N пока есть items
```

---

## Если RSC не работает — Playwright fallback

Если INN-фильтр работает только в JS-rendered контексте (cookie-based state):

```python
# bootstrap сессии — аналогично scripts/b2b_bootstrap_session.py
python scripts/fabrikant_bootstrap_session.py --browser-profile .local/fabrikant_profile

# основной прогон через браузер
python scripts/fabrikant_prompt2_source_sprint_v2.py \
    --batch-name fabrikant-probe-2026-xx-xx \
    --inns 7736663049 \
    --browser-profile .local/fabrikant_profile
```

`BrowserSession` уже реализован в `src/purchase_analysis/clients/browser_session.py` (включая капча-resolver). Достаточно добавить аргумент `--browser-profile`.

---

## Inclusion policy (как для всех новых источников)

1. **Positive probe** на 1–2 entity: `--inns 7736663049` (Сбербанк-Сервис)
2. Проверить `items.csv` на правильные роли (customer/organizer, не supplier/seller)
3. Full scope run, отдельный `batch-name`
4. `merge_sprints.py --dry-run` с ожидаемым duplicate report
5. Обновить `configs/source_sprints_allowlist.csv` и `configs/source_sprints_manifest.csv`
6. Добавить тест в `tests/test_fabrikant.py` по образцу `tests/test_b2b_center.py`

---

## Приоритет

**Средний.** Fabrikant ориентирован на промышленные компании и госзакупки. Вероятность найти значимый объём закупок именно Сбера — невысокая. Рекомендуется сначала сделать разведку API (Шаг 0) и проверить наличие хотя бы одного лота с ИНН Сбера вручную на сайте.
