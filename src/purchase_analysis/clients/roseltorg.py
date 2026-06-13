from dataclasses import asdict, dataclass
import html
import json
import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from purchase_analysis.utils.text import (
    normalize_spaces,
    parse_ru_datetime,
    parse_ru_decimal,
)

BASE_URL = "https://www.roseltorg.ru"
SEARCH_URL = f"{BASE_URL}/procedures/search_ajax"


@dataclass(slots=True)
class RoseltorgSearchItem:
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


@dataclass(slots=True)
class RoseltorgLotDetail:
    procedure_number: str
    lot_number: str
    published_at: str | None
    application_deadline: str | None
    detail_price_rub: float | None
    okpd_code: str
    okpd_name: str
    quantity: float | None
    unit: str
    delivery_place: str
    method_name: str
    currency: str
    seller_name: str
    seller_tax_id: str
    documents_available: bool


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


def fetch_search_page(
    customer_query: str,
    date_from: str,
    date_to: str,
    page: int,
    session: requests.Session | None = None,
    timeout: int = 30,
) -> tuple[str, str]:
    session = session or create_session(timeout=timeout)
    response = session.get(
        SEARCH_URL,
        params={
            "sale": "1",
            "customer": customer_query,
            "start_date_published": date_from,
            "end_date_published": date_to,
            "page": page,
        },
        timeout=timeout,
    )
    response.raise_for_status()
    return response.text, response.url


def parse_search_items(
    html_text: str,
    entity_name: str,
    customer_query: str,
) -> list[RoseltorgSearchItem]:
    soup = BeautifulSoup(html_text, "lxml")
    items: list[RoseltorgSearchItem] = []
    for block in soup.select(".search-results__item"):
        subject_link = block.select_one(".search-results__subject a")
        customer_link = block.select_one(".search-results__customer a")
        customer_tag = block.select_one(".search-results__customer p")
        deadline_text = normalize_spaces(
            block.select_one("time.search-results__time").get_text(" ", strip=True)
            if block.select_one("time.search-results__time")
            else ""
        )
        deadline = parse_ru_datetime(deadline_text)

        tag_texts: list[str] = []
        for tag in block.select(
            ".search-results__customer .search-results__tags .procedure-tags > a.chip, "
            ".search-results__data > .search-results__tags.mobile .procedure-tags > a.chip"
        ):
            text = normalize_spaces(tag.get_text(" ", strip=True))
            if text and text not in tag_texts:
                tag_texts.append(text)

        raw_price = normalize_spaces(
            " ".join(tag.get_text(" ", strip=True) for tag in block.select(".search-results__sum"))
        )
        customer_title = customer_tag.get("title", "") if customer_tag else ""
        customer_title = normalize_spaces(
            BeautifulSoup(html.unescape(customer_title), "lxml").get_text(" ", strip=True)
        )
        customer_title = re.sub(r"\s*ИНН\s+\d+\s*$", "", customer_title, flags=re.IGNORECASE)
        customer_title = re.sub(r'"\s+', '"', customer_title)
        customer_name = customer_title
        if not customer_name and customer_link:
            customer_name = normalize_spaces(customer_link.get_text(" ", strip=True))
        if not customer_name and customer_tag:
            customer_name = normalize_spaces(customer_tag.get_text(" ", strip=True))

        items.append(
            RoseltorgSearchItem(
                source_system="roseltorg",
                platform_section=normalize_spaces(
                    block.select_one(".search-results__section").get_text(" ", strip=True)
                )
                if block.select_one(".search-results__section")
                else "",
                entity_name=entity_name,
                customer_query=customer_query,
                procedure_number=block.get("data-feature-favorite-lots-procedure-number", ""),
                lot_number=block.get("data-feature-favorite-lots-lot-number", ""),
                subject=normalize_spaces(subject_link.get_text(" ", strip=True)) if subject_link else "",
                customer_name=customer_name,
                region=normalize_spaces(
                    " ".join(
                        tag.get_text(" ", strip=True)
                        for tag in block.select(".search-results__region p")
                    )
                ),
                status=normalize_spaces(
                    " ".join(
                        tag.get_text(" ", strip=True)
                        for tag in block.select(".search-results__status")
                    )
                ),
                tender_type=normalize_spaces(
                    " ".join(
                        tag.get_text(" ", strip=True)
                        for tag in block.select(".search-results__type")
                    )
                ),
                price_rub=None if "не указано" in raw_price.lower() else parse_ru_decimal(raw_price),
                deadline_at=deadline.isoformat() if deadline else None,
                detail_url=urljoin(BASE_URL, subject_link.get("href", "")) if subject_link else "",
                tags=" | ".join(tag_texts),
            )
        )
    return items


def fetch_lot_detail(
    detail_url: str,
    session: requests.Session | None = None,
    timeout: int = 30,
) -> str:
    session = session or create_session(timeout=timeout)
    response = session.get(detail_url, timeout=timeout)
    response.raise_for_status()
    return response.text


def _extract_product_schema(soup: BeautifulSoup) -> dict:
    for script in soup.select('script[type="application/ld+json"]'):
        raw = script.string or script.get_text()
        if not normalize_spaces(raw):
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        candidates = payload if isinstance(payload, list) else [payload]
        for candidate in candidates:
            if isinstance(candidate, dict) and candidate.get("@type") == "Product":
                return candidate
    return {}


def parse_lot_detail(
    html_text: str,
    procedure_number: str,
    lot_number: str,
) -> tuple[RoseltorgLotDetail, list[dict]]:
    soup = BeautifulSoup(html_text, "lxml")
    schema = _extract_product_schema(soup)
    additional = {
        item.get("name", ""): item.get("value", "")
        for item in schema.get("additionalProperty", [])
        if isinstance(item, dict)
    }

    published_at = None
    for heading in soup.select(".lot-steps__heading"):
        title = normalize_spaces(
            heading.select_one(".lot-steps__title").get_text(" ", strip=True)
            if heading.select_one(".lot-steps__title")
            else ""
        ).lower()
        if "публикация" not in title:
            continue
        description = normalize_spaces(
            heading.select_one(".lot-steps__description").get_text(" ", strip=True)
            if heading.select_one(".lot-steps__description")
            else heading.get_text(" ", strip=True)
        )
        dt = parse_ru_datetime(description)
        if dt:
            published_at = dt.isoformat()
            break

    quantity = parse_ru_decimal(
        soup.select_one(".lot-unit__quantity").get_text(" ", strip=True)
        if soup.select_one(".lot-unit__quantity")
        else None
    )
    unit = normalize_spaces(
        soup.select_one(".lot-unit__okei").get_text(" ", strip=True)
        if soup.select_one(".lot-unit__okei")
        else ""
    )
    okpd_name = normalize_spaces(
        soup.select_one(".lot-unit__okpd-name").get_text(" ", strip=True)
        if soup.select_one(".lot-unit__okpd-name")
        else ""
    )
    delivery_place = normalize_spaces(
        soup.select_one(".lot-delivery__text .lot-expand-text__text").get_text(" ", strip=True)
        if soup.select_one(".lot-delivery__text .lot-expand-text__text")
        else ""
    )
    price_text = normalize_spaces(
        soup.select_one(".lot-item__sum").get_text(" ", strip=True)
        if soup.select_one(".lot-item__sum")
        else ""
    )

    deadline = parse_ru_datetime(
        additional.get("\u0414\u0430\u0442\u0430 \u043e\u043a\u043e\u043d\u0447\u0430\u043d\u0438\u044f \u043f\u0440\u0438\u0435\u043c\u0430 \u0437\u0430\u044f\u0432\u043e\u043a")
    )
    offers = schema.get("offers", {})
    seller: dict = {}
    if isinstance(offers.get("seller"), list) and offers["seller"]:
        seller = offers["seller"][0]
    elif isinstance(offers.get("seller"), dict):
        seller = offers["seller"]

    documents: list[dict] = []
    for link in soup.select("#documents a[href]"):
        documents.append(
            {
                "procedure_number": procedure_number,
                "lot_number": lot_number,
                "document_name": normalize_spaces(link.get_text(" ", strip=True)),
                "document_url": urljoin(BASE_URL, link.get("href", "")),
                "is_available": True,
            }
        )

    detail = RoseltorgLotDetail(
        procedure_number=procedure_number,
        lot_number=lot_number,
        published_at=published_at,
        application_deadline=deadline.isoformat() if deadline else None,
        detail_price_rub=None
        if "\u043d\u0435 \u0443\u043a\u0430\u0437\u0430\u043d\u043e" in price_text.lower()
        else parse_ru_decimal(str(offers.get("price"))),
        okpd_code=normalize_spaces(
            additional.get("\u041a\u043e\u0434 \u041e\u041a\u041f\u0414", "")
        ),
        okpd_name=okpd_name,
        quantity=quantity,
        unit=unit,
        delivery_place=delivery_place,
        method_name=normalize_spaces(
            additional.get("\u0421\u043f\u043e\u0441\u043e\u0431 \u043f\u0440\u043e\u0432\u0435\u0434\u0435\u043d\u0438\u044f", "")
        ),
        currency=normalize_spaces(offers.get("priceCurrency", "RUB")),
        seller_name=normalize_spaces(seller.get("legalName", "")),
        seller_tax_id=normalize_spaces(seller.get("taxID", "")),
        documents_available=bool(documents),
    )
    return detail, documents


def search_item_to_dict(item: RoseltorgSearchItem) -> dict:
    return asdict(item)


def detail_to_dict(item: RoseltorgLotDetail) -> dict:
    return asdict(item)
