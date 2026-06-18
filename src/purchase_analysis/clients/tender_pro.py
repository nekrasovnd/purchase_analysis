from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

from purchase_analysis.utils.text import normalize_spaces, parse_ru_datetime

BASE_URL = "https://www.tender.pro"
COMPANY_SEARCH_URL = f"{BASE_URL}/api/companies/list"


@dataclass(slots=True)
class TenderProCompanyCandidate:
    company_id: str
    display_name: str
    company_url: str
    roles: str


@dataclass(slots=True)
class TenderProCompanyProfile:
    company_id: str
    company_url: str
    purchases_url: str
    display_name: str
    full_name: str
    short_name: str
    inn: str
    kpp: str
    ogrn: str
    address: str
    legal_address: str
    site_url: str
    okved: str
    description: str
    roles: str
    region: str


@dataclass(slots=True)
class TenderProPurchaseItem:
    source_system: str
    platform_section: str
    entity_name: str
    source_company_id: str
    source_company_name: str
    procedure_number: str
    lot_number: str
    subject: str
    customer_name: str
    customer_inn: str
    customer_kpp: str
    region: str
    status: str
    tender_type: str
    price_rub: float | None
    currency: str
    published_at: str | None
    deadline_at: str | None
    application_deadline: str | None
    method_name: str
    detail_url: str
    tags: str


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


def build_company_search_params(
    *,
    title: str | None = None,
    inn: str | None = None,
    page: int = 1,
) -> dict[str, object]:
    params: dict[str, object] = {"search_type": "company"}
    title_value = normalize_spaces(title)
    inn_value = normalize_identifier(inn)
    if not title_value and not inn_value:
        raise ValueError("Tender.Pro company search requires either title or inn")
    if title_value:
        params["title"] = title_value
    if inn_value:
        params["inn"] = inn_value
    if page > 1:
        params["page"] = page
    return params


def fetch_company_search_page(
    *,
    title: str | None = None,
    inn: str | None = None,
    page: int = 1,
    session: requests.Session | None = None,
    timeout: int = 30,
) -> tuple[str, str]:
    session = session or create_session(timeout=timeout)
    response = session.get(
        COMPANY_SEARCH_URL,
        params=build_company_search_params(title=title, inn=inn, page=page),
        timeout=timeout,
    )
    response.raise_for_status()
    return response.text, response.url


def fetch_url(
    url: str,
    *,
    session: requests.Session | None = None,
    timeout: int = 30,
) -> tuple[str, str]:
    session = session or create_session(timeout=timeout)
    response = session.get(url, timeout=timeout)
    response.raise_for_status()
    return response.text, response.url


def fetch_company_purchases_page(
    company_id: str,
    *,
    page: int = 1,
    session: requests.Session | None = None,
    timeout: int = 30,
) -> tuple[str, str]:
    url = build_company_view_url(company_id, active_tab="purchases", page=page)
    return fetch_url(url, session=session, timeout=timeout)


def build_company_view_url(company_id: str, *, active_tab: str = "purchases", page: int = 1) -> str:
    base_url = f"{BASE_URL}/api/company/{company_id}/view"
    if page <= 1:
        return f"{base_url}?active_tab={active_tab}"
    return f"{base_url}?active_tab={active_tab}&page={page}"


def parse_company_candidates(html_text: str) -> list[TenderProCompanyCandidate]:
    soup = BeautifulSoup(html_text, "lxml")
    results: list[TenderProCompanyCandidate] = []
    seen: set[str] = set()
    nodes = soup.select("div.content__company-list div.company-card")
    if not nodes:
        nodes = soup.select("div.content__company-list")
    for node in nodes:
        link = node.select_one("a.text-d-none._black[href*='/api/company/']")
        if link is None:
            continue
        company_url = urljoin(BASE_URL, link.get("href", ""))
        company_id = _company_id_from_url(company_url)
        if not company_id or company_id in seen:
            continue
        roles = [
            normalize_spaces(role.get_text(" ", strip=True))
            for role in node.select("div.company-card__role")
            if normalize_spaces(role.get_text(" ", strip=True))
        ]
        results.append(
            TenderProCompanyCandidate(
                company_id=company_id,
                display_name=normalize_spaces(link.get_text(" ", strip=True)),
                company_url=company_url,
                roles=" | ".join(roles),
            )
        )
        seen.add(company_id)
    return results


def parse_company_profile(html_text: str, *, url: str = "") -> TenderProCompanyProfile:
    soup = BeautifulSoup(html_text, "lxml")
    card = soup.select_one("div.card-company")
    if card is None:
        raise ValueError("Could not find Tender.Pro company card")

    table_rows = _parse_company_table_rows(card)
    company_url = url or _first_href(card, "a.statistics[href*='/api/company/']")
    company_id = normalize_spaces(table_rows.get("ID")) or _company_id_from_url(company_url)
    purchases_url = build_company_view_url(company_id, active_tab="purchases") if company_id else company_url

    inn_kpp_source = normalize_spaces(table_rows.get("ИНН/КПП")) or _first_inn_kpp_subtitle(card)
    inn, kpp = _split_inn_kpp(inn_kpp_source)
    roles = [
        normalize_spaces(image.get("title") or image.get("alt"))
        for image in card.select("div.badge img")
        if normalize_spaces(image.get("title") or image.get("alt"))
    ]
    subtitles = [
        normalize_spaces(node.get_text(" ", strip=True))
        for node in card.select("div.page-header__subtitle.mt-12")
        if normalize_spaces(node.get_text(" ", strip=True))
    ]
    description = ""
    for subtitle in subtitles:
        if "ИНН/КПП" in subtitle:
            continue
        if any(role in subtitle for role in roles):
            continue
        description = subtitle
        break

    short_name = normalize_spaces(table_rows.get("Краткое название"))
    display_name = short_name or _headline_company_name(card.select_one("h1"))
    return TenderProCompanyProfile(
        company_id=company_id,
        company_url=company_url,
        purchases_url=purchases_url,
        display_name=display_name,
        full_name=normalize_spaces(table_rows.get("Полное название")) or display_name,
        short_name=short_name or display_name,
        inn=inn,
        kpp=kpp,
        ogrn=normalize_identifier(table_rows.get("ОГРН")),
        address=normalize_spaces(table_rows.get("Адрес")),
        legal_address=normalize_spaces(table_rows.get("Юридический адрес")),
        site_url=normalize_spaces(table_rows.get("Сайт")),
        okved=normalize_spaces(table_rows.get("ОКВЭД")),
        description=description,
        roles=" | ".join(roles),
        region=_region_from_name(display_name),
    )


def parse_purchase_items(
    html_text: str,
    *,
    entity_name: str,
    profile: TenderProCompanyProfile,
) -> list[TenderProPurchaseItem]:
    soup = BeautifulSoup(html_text, "lxml")
    results: list[TenderProPurchaseItem] = []
    for node in soup.select("li.tender-list__item"):
        subject_link = node.select_one("a.tender-name[href*='/api/tender/']")
        if subject_link is None:
            continue
        detail_url = urljoin(BASE_URL, subject_link.get("href", ""))
        procedure_number = _tender_id_from_url(detail_url)
        if not procedure_number:
            procedure_number = _label_value(node, "ID конкурса")
        tender_type = normalize_spaces(
            node.select_one("div.c-gray.mb-12._text-first-letter-up").get_text(" ", strip=True)
            if node.select_one("div.c-gray.mb-12._text-first-letter-up")
            else ""
        )
        published_at = _parse_item_date(_label_value(node, "Создан"))
        deadline_at = _parse_item_date(_label_value(node, "Завершится"))
        status = normalize_spaces(node.select_one("div.t-status").get_text(" ", strip=True) if node.select_one("div.t-status") else "")
        results.append(
            TenderProPurchaseItem(
                source_system="tender_pro",
                platform_section="purchases",
                entity_name=entity_name,
                source_company_id=profile.company_id,
                source_company_name=profile.short_name or profile.display_name,
                procedure_number=procedure_number,
                lot_number="1",
                subject=normalize_spaces(subject_link.get_text(" ", strip=True)),
                customer_name=profile.full_name or profile.short_name or profile.display_name,
                customer_inn=profile.inn,
                customer_kpp=profile.kpp,
                region=profile.region,
                status=status,
                tender_type=tender_type,
                price_rub=None,
                currency="",
                published_at=published_at,
                deadline_at=deadline_at,
                application_deadline=deadline_at,
                method_name=tender_type,
                detail_url=detail_url,
                tags="",
            )
        )
    return results


def parse_purchase_pages(html_text: str, *, current_url: str = "") -> list[int]:
    page_urls = parse_purchase_page_urls(html_text)
    pages: set[int] = {1}
    for href in page_urls:
        query = parse_qs(urlparse(href).query)
        try:
            pages.add(int((query.get("page") or ["1"])[0]))
        except (TypeError, ValueError):
            continue
    if current_url:
        query = parse_qs(urlparse(current_url).query)
        try:
            pages.add(int((query.get("page") or ["1"])[0]))
        except (TypeError, ValueError):
            pass
    return sorted(pages)


def parse_purchase_page_urls(html_text: str) -> list[str]:
    soup = BeautifulSoup(html_text, "lxml")
    urls: list[str] = []
    seen: set[str] = set()
    for link in soup.select("a.pagination__link[href]"):
        href = urljoin(BASE_URL, link.get("href", ""))
        if href and href not in seen:
            seen.add(href)
            urls.append(href)
    return urls


def build_paged_url(reference_url: str, *, page: int) -> str:
    parsed = urlparse(reference_url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    query["page"] = [str(page)]
    flat_query = [(key, value) for key, values in query.items() for value in values]
    return urlunparse(parsed._replace(query=urlencode(flat_query)))


def company_candidate_to_dict(candidate: TenderProCompanyCandidate) -> dict:
    return asdict(candidate)


def company_profile_to_dict(profile: TenderProCompanyProfile) -> dict:
    return asdict(profile)


def purchase_item_to_dict(item: TenderProPurchaseItem) -> dict:
    return asdict(item)


def normalize_identifier(value: str | None) -> str:
    return re.sub(r"\D+", "", value or "")


def _parse_company_table_rows(card: BeautifulSoup) -> dict[str, str]:
    rows: dict[str, str] = {}
    for row in card.select("div.flex-table__row div.table__row"):
        header = row.select_one("div.table__header")
        value = row.select_one("div.table__col")
        if header is None or value is None:
            continue
        key = normalize_spaces(header.get_text(" ", strip=True))
        if key and key not in rows:
            rows[key] = normalize_spaces(value.get_text(" ", strip=True))
    return rows


def _first_href(card: BeautifulSoup, selector: str) -> str:
    node = card.select_one(selector)
    return urljoin(BASE_URL, node.get("href", "")) if node else ""


def _first_inn_kpp_subtitle(card: BeautifulSoup) -> str:
    for subtitle in card.select("div.page-header__subtitle.mt-12"):
        value = normalize_spaces(subtitle.get_text(" ", strip=True))
        if "ИНН/КПП" in value:
            return value
    return ""


def _split_inn_kpp(value: str) -> tuple[str, str]:
    match = re.search(r"(\d{10,12})\s*/\s*(\d{9})", value)
    if match:
        return match.group(1), match.group(2)
    digits = normalize_identifier(value)
    if len(digits) >= 19:
        return digits[:10], digits[10:19]
    return "", ""


def _region_from_name(value: str) -> str:
    match = re.search(r"\(([^)]*)\)\s*$", value)
    return normalize_spaces(match.group(1)) if match else ""


def _headline_company_name(node: BeautifulSoup | None) -> str:
    text = normalize_spaces(node.get_text(" ", strip=True) if node else "")
    return normalize_spaces(re.sub(r"^(Закупки|Продажи|Прайс-лист|О компании)\s+", "", text, flags=re.IGNORECASE))


def _company_id_from_url(url: str) -> str:
    match = re.search(r"/api/company/(\d+)/view", url)
    return match.group(1) if match else ""


def _tender_id_from_url(url: str) -> str:
    match = re.search(r"/api/tender/(\d+)/view_public", url)
    return match.group(1) if match else ""


def _label_value(node: BeautifulSoup, label: str) -> str:
    for block in node.select("div.t-time, div.tender-id"):
        text = " ".join(block.stripped_strings)
        if label in text:
            value = text.split(":", 1)[-1]
            return normalize_spaces(value)
    return ""


def _parse_item_date(value: str) -> str | None:
    if not value:
        return None
    cleaned = normalize_spaces(value.replace(" в ", " ").replace(" MSK", ""))
    parsed = parse_ru_datetime(cleaned)
    return parsed.isoformat() if parsed else None
