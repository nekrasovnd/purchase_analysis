from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from purchase_analysis.utils.text import normalize_spaces, parse_ru_datetime, parse_ru_decimal

BASE_URL = "https://tender.lot-online.ru"
SEARCH_PAGE_URL = f"{BASE_URL}/etp/app/SearchLots/"
SEARCH_URL = f"{BASE_URL}/etp/searchServlet"
DEFAULT_TYPES = ("BUYING", "RFI", "SMALL_PURCHASE")
RUBLE_TOKEN = "\u0440\u0443\u0431"
MSK_TOKEN = "\u041c\u0421\u041a"


@dataclass(slots=True)
class LotOnlineSearchItem:
    source_system: str
    platform_section: str
    entity_name: str
    customer_query: str
    procedure_number: str
    lot_number: str
    subject: str
    customer_name: str
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
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            ),
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.7,en;q=0.6",
        }
    )
    session.request_timeout = timeout
    return session


def build_query_payload(
    *,
    title: str | None = None,
    customer_title: str | None = None,
    organizer_title: str | None = None,
    types: tuple[str, ...] = DEFAULT_TYPES,
) -> dict:
    query: dict[str, object] = {"types": list(types)}
    provided = sum(bool(value) for value in [title, customer_title, organizer_title])
    if provided == 0:
        raise ValueError("At least one Lot-Online search field must be provided")
    if title:
        query["title"] = normalize_spaces(title)
    if customer_title:
        query["customer"] = {"title": normalize_spaces(customer_title)}
    if organizer_title:
        query["organizer"] = {"title": normalize_spaces(organizer_title)}
    return query


def fetch_search_page(
    query: dict,
    *,
    offset: int = 0,
    page_size: int = 20,
    default: bool = False,
    session: requests.Session | None = None,
    timeout: int = 30,
) -> tuple[dict, str]:
    session = session or create_session(timeout=timeout)
    response = session.get(
        SEARCH_URL,
        params={
            "query": json.dumps(query, ensure_ascii=False, separators=(",", ":")),
            "filter": json.dumps({"state": ["ALL"]}, ensure_ascii=False, separators=(",", ":")),
            "sort": json.dumps({"placementDate": False}, ensure_ascii=False, separators=(",", ":")),
            "limit": json.dumps(
                {"min": offset, "max": offset + page_size, "updateTotalCount": True},
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            "default": str(default).lower(),
        },
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json(), response.url


def fetch_all_search_pages(
    query: dict,
    *,
    max_pages: int,
    page_size: int = 20,
    default: bool = False,
    session: requests.Session | None = None,
    timeout: int = 30,
) -> list[tuple[dict, str]]:
    pages: list[tuple[dict, str]] = []
    for page_index in range(max_pages):
        payload, url = fetch_search_page(
            query,
            offset=page_index * page_size,
            page_size=page_size,
            default=default,
            session=session,
            timeout=timeout,
        )
        pages.append((payload, url))
        returned_items = payload.get("list") or []
        if not returned_items or len(returned_items) < page_size:
            break
    return pages


def parse_total(payload: dict) -> int:
    try:
        return int(payload.get("count") or len(payload.get("list") or []))
    except (TypeError, ValueError):
        return 0


def _price_text(value: str | None) -> str:
    if not value:
        return ""
    return normalize_spaces(BeautifulSoup(value, "lxml").get_text(" ", strip=True))


def _price_value(value: str) -> float | None:
    match = re.search(r"-?\d[\d\s]*,\d{2}", value)
    if match:
        return parse_ru_decimal(match.group(0))
    return parse_ru_decimal(value)


def _currency_from_price(value: str) -> str:
    lowered = value.lower()
    if RUBLE_TOKEN in lowered:
        return "RUB"
    if "usd" in lowered or "$" in lowered:
        return "USD"
    if "eur" in lowered or "\u20ac" in lowered:
        return "EUR"
    return "RUB"


def _clean_datetime_text(value: str | None) -> str:
    cleaned = normalize_spaces(
        BeautifulSoup((value or "").replace("&nbsp;", " "), "lxml").get_text(" ", strip=True)
    )
    cleaned = re.sub(rf"\s+{MSK_TOKEN}$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*\(\+\d{2}:\d{2}\)$", "", cleaned)
    return normalize_spaces(cleaned)


def parse_search_items(
    payload: dict,
    *,
    entity_name: str,
    customer_query: str,
) -> list[LotOnlineSearchItem]:
    items: list[LotOnlineSearchItem] = []
    for raw_item in payload.get("list", []):
        organizer = raw_item.get("organizer") or {}
        customer_rows = raw_item.get("customer") or []
        customer_names = [
            normalize_spaces(item.get("title"))
            for item in customer_rows
            if normalize_spaces(item.get("title"))
        ]
        tags = [
            normalize_spaces(str(value))
            for value in [*(raw_item.get("features") or []), *(raw_item.get("okdp2") or [])]
            if normalize_spaces(str(value))
        ]
        price_text = _price_text(raw_item.get("price"))
        deadline = parse_ru_datetime(_clean_datetime_text(raw_item.get("gdEndDate")))
        published = parse_ru_datetime(
            _clean_datetime_text(
                raw_item.get("placementDateTime")
                or raw_item.get("placementDate")
                or raw_item.get("gdStartDate")
            )
        )
        items.append(
            LotOnlineSearchItem(
                source_system="lot_online",
                platform_section=normalize_spaces(raw_item.get("placementType") or raw_item.get("type")),
                entity_name=entity_name,
                customer_query=customer_query,
                procedure_number=normalize_spaces(
                    str(raw_item.get("filingNumber") or raw_item.get("identifier") or raw_item.get("uuid") or "")
                ),
                lot_number=str(raw_item.get("lotNumber") or "1"),
                subject=normalize_spaces(raw_item.get("title")),
                customer_name=" | ".join(dict.fromkeys(customer_names)),
                region=" | ".join(
                    normalize_spaces(value)
                    for value in raw_item.get("regionCodes") or []
                    if normalize_spaces(value)
                ),
                status=normalize_spaces((raw_item.get("state") or {}).get("title")),
                tender_type=normalize_spaces(raw_item.get("type")),
                price_rub=_price_value(price_text),
                deadline_at=deadline.isoformat() if deadline else None,
                detail_url=urljoin(BASE_URL, raw_item.get("lotLink", "")),
                tags=" | ".join(dict.fromkeys(tags)),
                published_at=published.isoformat() if published else None,
                application_deadline=deadline.isoformat() if deadline else None,
                method_name=normalize_spaces(raw_item.get("placementType")),
                currency=_currency_from_price(price_text),
                organizer_name=normalize_spaces(organizer.get("title")),
                organizer_inn=normalize_spaces(organizer.get("inn")),
            )
        )
    return items


def search_item_to_dict(item: LotOnlineSearchItem) -> dict:
    return asdict(item)
