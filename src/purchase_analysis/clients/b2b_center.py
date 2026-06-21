from __future__ import annotations

from dataclasses import asdict, dataclass
import math
import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
import js2py

from purchase_analysis.utils.text import normalize_spaces, parse_ru_datetime, parse_ru_decimal

BASE_URL = "https://www.b2b-center.ru"
MARKET_URL = f"{BASE_URL}/market/"
ORG_SEARCH_URL = f"{BASE_URL}/api/search/organizations/"

ROLE_MODE_TO_ACTION = {
    "organizer": "SearchOrganizer",
    "customer": "SearchCustomer",
}
ACTION_TO_ROLE_MODE = {value: key for key, value in ROLE_MODE_TO_ACTION.items()}

RATE_LIMIT_MARKERS = (
    "превышен максимальный лимит скорости просмотра страниц",
    "регламент площадки не допускает использование ботов",
)

FORBIDDEN_PAGE_MARKERS = (
    "forbidden",
    "if you are not a bot",
    "send it to our support team",
)


@dataclass(slots=True)
class B2BCenterOrganizationCandidate:
    query: str
    search_action: str
    role_mode: str
    organization_id: str
    name: str
    inn: str


@dataclass(slots=True)
class B2BCenterSearchItem:
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


@dataclass(slots=True)
class B2BCenterProcedureDetail:
    detail_url: str
    subject: str
    category: str
    quantity_text: str
    total_price_text: str
    total_price_rub: float | None
    currency: str
    published_at: str | None
    deadline_at: str | None
    organizer_name: str
    organizer_profile_url: str
    procedure_status: str
    price_note: str
    location: str


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


def normalize_role_mode(value: str) -> str:
    lowered = normalize_spaces(value).lower()
    if lowered in ROLE_MODE_TO_ACTION:
        return lowered
    if value in ACTION_TO_ROLE_MODE:
        return ACTION_TO_ROLE_MODE[value]
    raise ValueError(f"Unsupported B2B-Center role mode: {value}")


def parse_organization_candidates(
    payload: dict,
    *,
    query: str,
    search_action: str,
) -> list[B2BCenterOrganizationCandidate]:
    role_mode = normalize_role_mode(search_action)
    items: list[B2BCenterOrganizationCandidate] = []
    for row in payload.get("data") or []:
        candidate = B2BCenterOrganizationCandidate(
            query=normalize_spaces(query),
            search_action=search_action,
            role_mode=role_mode,
            organization_id=normalize_spaces(str(row.get("value") or "")),
            name=normalize_spaces(row.get("text")),
            inn=normalize_spaces(row.get("inn")),
        )
        if candidate.organization_id and candidate.name:
            items.append(candidate)
    return items


def search_organization_candidates(
    query: str,
    *,
    search_action: str = "SearchOrganizer",
    session: requests.Session | None = None,
    timeout: int = 30,
) -> list[B2BCenterOrganizationCandidate]:
    session = session or create_session(timeout=timeout)
    response = session.get(
        ORG_SEARCH_URL,
        params={"action": search_action, "query": normalize_spaces(query)},
        timeout=timeout,
    )
    response.raise_for_status()
    return parse_organization_candidates(
        response.json(),
        query=query,
        search_action=search_action,
    )


def build_market_search_params(
    *,
    organization_id: str,
    role_mode: str,
    show: str | None = "all",
    date_kind: str | None = None,
    date_start: str | None = None,
    date_end: str | None = None,
    order_by: int | None = None,
    order_dir: int | None = None,
) -> dict[str, str]:
    role_mode = normalize_role_mode(role_mode)
    params = {
        "searching": "1",
        "trade": "all",
        "firm_id" if role_mode == "organizer" else "customer_id": normalize_spaces(organization_id),
    }
    if show:
        params["show"] = normalize_spaces(show)
    if date_kind:
        params["date"] = normalize_spaces(date_kind)
    if date_start:
        params["date_start_dmy"] = normalize_spaces(date_start)
    if date_end:
        params["date_end_dmy"] = normalize_spaces(date_end)
    if order_by is not None:
        params["order_by"] = str(order_by)
    if order_dir is not None:
        params["order_dir"] = str(order_dir)
    return params


def fetch_search_page(
    *,
    organization_id: str,
    role_mode: str,
    show: str | None = "all",
    date_kind: str | None = None,
    date_start: str | None = None,
    date_end: str | None = None,
    order_by: int | None = None,
    order_dir: int | None = None,
    session: requests.Session | None = None,
    timeout: int = 30,
) -> tuple[str, str]:
    session = session or create_session(timeout=timeout)
    response = session.get(
        MARKET_URL,
        params=build_market_search_params(
            organization_id=organization_id,
            role_mode=role_mode,
            show=show,
            date_kind=date_kind,
            date_start=date_start,
            date_end=date_end,
            order_by=order_by,
            order_dir=order_dir,
        ),
        timeout=timeout,
    )
    response.raise_for_status()
    return response.text, response.url


def parse_status_counts(html_text: str) -> dict[str, int]:
    soup = BeautifulSoup(html_text, "lxml")
    counts = {"actual": 0, "archive": 0, "all": 0}
    for anchor in soup.select("a[data-status]"):
        status = normalize_spaces(anchor.get("data-status")).lower()
        if status not in counts:
            continue
        text = normalize_spaces(anchor.get_text(" ", strip=True))
        match = re.search(r"(\d+)\s*$", text)
        if match:
            counts[status] = int(match.group(1))
    return counts


def search_has_pager(html_text: str) -> bool:
    soup = BeautifulSoup(html_text, "lxml")
    return soup.select_one(".pagi") is not None


def is_rate_limited_page(html_text: str) -> bool:
    text = normalize_spaces(BeautifulSoup(html_text, "lxml").get_text(" ", strip=True)).lower()
    return any(marker in text for marker in RATE_LIMIT_MARKERS)


def is_forbidden_page(html_text: str) -> bool:
    text = normalize_spaces(BeautifulSoup(html_text, "lxml").get_text(" ", strip=True)).lower()
    return all(marker in text for marker in FORBIDDEN_PAGE_MARKERS)


def _search_item_subject(title_text: str) -> str:
    return normalize_spaces(re.sub(r"^.+?№\s*\d+\s*", "", title_text))


def _search_item_method(title_text: str) -> str:
    match = re.match(r"(.+?)\s*№\s*\d+", title_text)
    return normalize_spaces(match.group(1) if match else "")


def parse_search_items(
    html_text: str,
    *,
    entity_name: str,
    customer_query: str,
    role_mode: str,
    show: str | None = "all",
    organization_name: str = "",
    organization_inn: str = "",
) -> list[B2BCenterSearchItem]:
    role_mode = normalize_role_mode(role_mode)
    soup = BeautifulSoup(html_text, "lxml")
    items: list[B2BCenterSearchItem] = []
    for row in soup.select("table.search-results tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) < 4:
            continue
        anchor = row.select_one("a.search-results-title")
        if anchor is None:
            continue
        category_tag = row.select_one("small")
        category = normalize_spaces(category_tag.get_text(" ", strip=True) if category_tag else "")
        title_text = normalize_spaces(anchor.get_text(" ", strip=True))
        procedure_match = re.search(r"№\s*(\d+)", title_text)
        if procedure_match is None:
            continue
        procedure_number = procedure_match.group(1)
        detail_url = urljoin(BASE_URL, (anchor.get("href") or "").split("#", 1)[0])
        organization_cell_name = normalize_spaces(cells[1].get_text(" ", strip=True)) or organization_name
        published_at = parse_ru_datetime(cells[2].get_text(" ", strip=True))
        deadline_at = parse_ru_datetime(cells[3].get_text(" ", strip=True))
        organizer_name = organization_cell_name if role_mode == "organizer" else ""
        organizer_inn = organization_inn if role_mode == "organizer" else ""
        customer_name = organization_cell_name if role_mode == "customer" else ""
        customer_inn = organization_inn if role_mode == "customer" else ""
        tags = " | ".join(part for part in [category, role_mode, normalize_spaces(show)] if part)
        items.append(
            B2BCenterSearchItem(
                source_system="b2b_center",
                platform_section=category,
                entity_name=entity_name,
                customer_query=normalize_spaces(customer_query),
                procedure_number=procedure_number,
                lot_number="1",
                subject=_search_item_subject(title_text),
                customer_name=customer_name,
                customer_inn=customer_inn,
                region="",
                status=normalize_spaces(show),
                tender_type=_search_item_method(title_text),
                price_rub=None,
                deadline_at=deadline_at.isoformat() if deadline_at else None,
                detail_url=detail_url,
                tags=tags,
                published_at=published_at.isoformat() if published_at else None,
                application_deadline=deadline_at.isoformat() if deadline_at else None,
                method_name=_search_item_method(title_text),
                currency="",
                organizer_name=organizer_name,
                organizer_inn=organizer_inn,
            )
        )
    return items


def fetch_procedure_detail(
    detail_url: str,
    *,
    session: requests.Session | None = None,
    timeout: int = 30,
) -> tuple[str, str]:
    session = session or create_session(timeout=timeout)
    response = session.get(detail_url, timeout=timeout)
    response.raise_for_status()
    return response.text, response.url


def _detail_value_by_row_id(soup: BeautifulSoup, row_id: str) -> str:
    row = soup.select_one(f"tr#{row_id}")
    if row is None:
        return ""
    cells = row.find_all("td", recursive=False)
    if len(cells) < 2:
        return ""
    return normalize_spaces(cells[1].get_text(" ", strip=True))


def _procedure_status(text: str) -> str:
    lowered = text.lower()
    if "статус объявления: в архиве" in lowered or "процедура находится в архиве" in lowered:
        return "archive"
    if "статус объявления: актуально" in lowered:
        return "actual"
    return ""


def _detail_price_note(price_text: str) -> str:
    lowered = price_text.lower()
    if "без указания цены" in lowered or "не указана" in lowered:
        return "without_price"
    if "договорная" in lowered:
        return "negotiable"
    return ""


def _market_next_script(html_text: str) -> str:
    match = re.search(r"var\s+__pinia\s*=", html_text)
    if match is None:
        return ""
    start = match.start()
    end = html_text.find("</script>", start)
    if end < 0:
        return ""
    return html_text[start:end]


def _market_next_trade_aggregate(html_text: str) -> dict[str, object] | None:
    script = _market_next_script(html_text)
    if not script:
        return None
    context = js2py.EvalJs({})
    context.execute(script)
    try:
        trade_aggregate = context.__pinia.TradePage.tradeAggregateRaw.to_dict()
    except Exception:
        return None
    return trade_aggregate if isinstance(trade_aggregate, dict) else None


def _market_next_status_bucket(trade_aggregate: dict[str, object]) -> str:
    status = ""
    trade_view_status = trade_aggregate.get("trade_view_status") or {}
    if isinstance(trade_view_status, dict):
        status = normalize_spaces(trade_view_status.get("value")).lower()
    if status == "finished":
        return "archive"
    if status:
        return "actual"
    trade_result = trade_aggregate.get("trade_result") or {}
    if (
        isinstance(trade_result, dict)
        and isinstance(trade_result.get("trade_result"), dict)
        and trade_result["trade_result"].get("date_finished")
    ):
        return "archive"
    return ""


def _market_next_location(fields_values: dict[str, object]) -> str:
    delivery_addresses = fields_values.get("delivery_address") or []
    if not isinstance(delivery_addresses, list) or not delivery_addresses:
        return ""
    first = delivery_addresses[0] or {}
    if not isinstance(first, dict):
        return ""
    address = first.get("address") or {}
    if isinstance(address, dict) and address.get("address_string"):
        return normalize_spaces(address.get("address_string"))
    return normalize_spaces(first.get("address_string"))


def _market_next_category(fields_values: dict[str, object]) -> str:
    okpd2 = fields_values.get("okpd2") or {}
    if not isinstance(okpd2, dict):
        return ""
    categories = okpd2.get("okpd2_category_list") or []
    if not isinstance(categories, list) or not categories:
        return ""
    first = categories[0] or {}
    if not isinstance(first, dict):
        return ""
    return normalize_spaces(first.get("name"))


def _market_next_price_payload(
    trade_aggregate: dict[str, object],
    fields_values: dict[str, object],
) -> tuple[str, float | None, str, str]:
    trade_result = trade_aggregate.get("trade_result") or {}
    if not isinstance(trade_result, dict):
        trade_result = {}
    money = trade_result.get("trade_result_money") or {}
    if not isinstance(money, dict):
        money = {}

    currency_field = fields_values.get("currency") or {}
    raw_currency = ""
    if isinstance(currency_field, dict) and isinstance(currency_field.get("currency"), dict):
        raw_currency = currency_field["currency"].get("symbol") or ""
    if not raw_currency and isinstance(money.get("currency"), dict):
        raw_currency = money["currency"].get("symbol") or ""
    currency = normalize_spaces(raw_currency)

    price_mode = ""
    price_type = fields_values.get("main_price_type") or {}
    if isinstance(price_type, dict):
        price_mode = normalize_spaces(
            price_type.get("option", {}).get("name", {}).get("hint", {}).get("title")
        ).lower()

    money_without_tax = money.get("money_without_tax")
    money_with_tax = money.get("money_with_tax")
    total_price_rub: float | None = None

    if isinstance(money_without_tax, (int, float)) and not math.isclose(float(money_without_tax), 0.0):
        total_price_rub = float(money_without_tax)
    if total_price_rub is None and isinstance(money_with_tax, (int, float)) and not math.isclose(float(money_with_tax), 0.0):
        total_price_rub = float(money_with_tax)

    if total_price_rub is None:
        hide_prices = False
        hide_prices_field = fields_values.get("hide_prices") or {}
        if isinstance(hide_prices_field, dict):
            hide_prices = bool(hide_prices_field.get("value"))
        price_text = "Не указана" if hide_prices or money_without_tax == 0 or money_with_tax == 0 else ""
        return price_text, None, currency, _detail_price_note(price_text)

    suffix = ""
    if "без ндс" in price_mode:
        suffix = " без НДС"
    elif "ндс" in price_mode:
        suffix = " с НДС"

    amount_text = str(int(total_price_rub)) if float(total_price_rub).is_integer() else f"{total_price_rub:g}"
    price_text = f"{amount_text} {currency}{suffix}".strip()
    return price_text, total_price_rub, currency, ""


def _market_next_detail(
    html_text: str,
    *,
    detail_url: str,
) -> B2BCenterProcedureDetail | None:
    trade_aggregate = _market_next_trade_aggregate(html_text)
    if not trade_aggregate:
        return None

    trade = trade_aggregate.get("trade") or {}
    if not isinstance(trade, dict):
        return None
    fields_values = trade.get("fields_values") or {}
    if not isinstance(fields_values, dict):
        fields_values = {}
    firm = trade.get("firm") or {}
    if not isinstance(firm, dict):
        firm = {}

    price_text, total_price_rub, currency, price_note = _market_next_price_payload(
        trade_aggregate,
        fields_values,
    )

    quantity_text = ""
    positions_count = trade_aggregate.get("positions_count")
    if isinstance(positions_count, (int, float)):
        quantity_text = str(int(positions_count))
    elif positions_count not in (None, ""):
        quantity_text = normalize_spaces(str(positions_count))

    return B2BCenterProcedureDetail(
        detail_url=detail_url,
        subject=normalize_spaces(fields_values.get("subject", {}).get("value")),
        category=_market_next_category(fields_values),
        quantity_text=quantity_text,
        total_price_text=price_text,
        total_price_rub=total_price_rub,
        currency=currency,
        published_at=normalize_spaces(trade.get("date_published")),
        deadline_at=normalize_spaces(fields_values.get("offers_stage_date_end", {}).get("value")),
        organizer_name=normalize_spaces(firm.get("short_name") or firm.get("full_name")),
        organizer_profile_url=normalize_spaces(firm.get("url")),
        procedure_status=_market_next_status_bucket(trade_aggregate),
        price_note=price_note,
        location=_market_next_location(fields_values),
    )


def parse_procedure_detail(
    html_text: str,
    *,
    detail_url: str,
) -> B2BCenterProcedureDetail:
    if is_rate_limited_page(html_text) or is_forbidden_page(html_text):
        raise ValueError("B2B-Center detail page is blocked by anti-bot")

    market_next_detail = _market_next_detail(html_text, detail_url=detail_url)
    if market_next_detail is not None:
        return market_next_detail

    soup = BeautifulSoup(html_text, "lxml")
    body_text = normalize_spaces(soup.get_text(" ", strip=True))
    title_tag = soup.select_one("h1")
    category = _detail_value_by_row_id(soup, "trade-info-lot-category")
    if not category:
        category = _detail_value_by_row_id(soup, "trade-info-tag")
    if not category:
        tag_row = soup.find("td", string=re.compile(r"^\s*Тег:\s*$"))
        if tag_row and tag_row.parent:
            cells = tag_row.parent.find_all("td", recursive=False)
            if len(cells) >= 2:
                category = normalize_spaces(cells[1].get_text(" ", strip=True))

    quantity_text = _detail_value_by_row_id(soup, "trade-info-lot-quantity")
    total_price_text = _detail_value_by_row_id(soup, "trade-info-lot-price")
    currency = _detail_value_by_row_id(soup, "trade-info-lot-price-currency")
    published_at = parse_ru_datetime(_detail_value_by_row_id(soup, "trade_info_date_begin"))
    deadline_at = parse_ru_datetime(_detail_value_by_row_id(soup, "trade_info_date_end"))
    organizer_row = soup.select_one("tr#trade-info-organizer-name a")
    organizer_name = normalize_spaces(organizer_row.get_text(" ", strip=True) if organizer_row else "")
    organizer_profile_url = urljoin(BASE_URL, organizer_row.get("href", "")) if organizer_row else ""
    location_row = soup.find("td", string=re.compile(r"Адрес места поставки", re.IGNORECASE))
    location = ""
    if location_row and location_row.parent:
        cells = location_row.parent.find_all("td", recursive=False)
        if len(cells) >= 2:
            location = normalize_spaces(cells[1].get_text(" ", strip=True))
    return B2BCenterProcedureDetail(
        detail_url=detail_url,
        subject=normalize_spaces(title_tag.get_text(" ", strip=True) if title_tag else ""),
        category=category,
        quantity_text=quantity_text,
        total_price_text=total_price_text,
        total_price_rub=parse_ru_decimal(total_price_text),
        currency=currency,
        published_at=published_at.isoformat() if published_at else None,
        deadline_at=deadline_at.isoformat() if deadline_at else None,
        organizer_name=organizer_name,
        organizer_profile_url=organizer_profile_url,
        procedure_status=_procedure_status(body_text),
        price_note=_detail_price_note(total_price_text),
        location=location,
    )


def search_item_to_dict(item: B2BCenterSearchItem) -> dict:
    return asdict(item)


def procedure_detail_to_dict(detail: B2BCenterProcedureDetail) -> dict:
    return asdict(detail)
