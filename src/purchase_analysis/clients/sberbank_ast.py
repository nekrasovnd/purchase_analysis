from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import re
from xml.etree import ElementTree as ET

import requests
from bs4 import BeautifulSoup, Tag

from purchase_analysis.utils.text import normalize_spaces, parse_ru_datetime, parse_ru_decimal

BASE_URL = "https://utp.sberbank-ast.ru"
REGISTRY_URL = f"{BASE_URL}/Main/List/UnitedPurchaseListNew"
SEARCH_URL = f"{BASE_URL}/Main/SearchQuery/UnitedPurchaseListNew"
LONG_DICTIONARY_URL = f"{BASE_URL}/LongDictionary"
OUT_OF_SCOPE_SECTIONS = {
    "Реализация имущества",
    "Продажа имущества (предприятия) банкротов",
}
OUT_OF_SCOPE_METHOD_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bпродаж[аеи]\b",
        r"\bбанкрот\w*\b",
    )
)
ASSET_SALE_SUBJECT_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bкупл[яи]\s*-\s*продаж[аеи]\b",
        r"\bпрост\w+\s+продаж[аеи]\b",
        r"\bпроцедур\w*\s+продаж[аеи]\b",
        r"\bпродаж[аеи]\s+(?:б\s*[./-]?\s*у|бывш\w*\s+в\s+употреблен\w*)\b",
        r"\bпродаж[аеи]\s+(?:имуществ\w*|транспортн\w+\s+средств\w*|автомобил\w*|оборудовани\w*)\b",
        r"\bреализац\w+\s+(?:имуществ\w*|б\s*[./-]?\s*у|бывш\w*\s+в\s+употреблен\w*)\b",
        r"\bна\s+право\s+заключени\w+\s+договор\w+\s+(?:реализац\w+|доходн\w+\s+утилизац\w+)\b",
        r"\bна\s+право\s+заключени\w+\s+договор\w+\s+аренд\w+.*\bнежил\w+\b",
    )
)


@dataclass(slots=True)
class SberbankAstCustomerCandidate:
    query: str
    bu_inn: str
    bu_kpp: str
    bu_inn_kpp: str
    full_name: str


@dataclass(slots=True)
class SberbankAstSearchItem:
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


@dataclass(slots=True)
class SberbankAstSearchResponse:
    total: int
    table_xml: str
    raw_data: str
    search_url: str
    request_xml: str


def create_session(timeout: int = 30) -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            ),
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.7,en;q=0.6",
            "X-Requested-With": "XMLHttpRequest",
        }
    )
    session.request_timeout = timeout
    return session


def fetch_registry_page(
    session: requests.Session | None = None,
    timeout: int = 30,
) -> str:
    session = session or create_session(timeout=timeout)
    response = session.get(REGISTRY_URL, timeout=timeout)
    response.raise_for_status()
    return response.text


def _post_long_dictionary(
    query: str,
    from_offset: int = 0,
    session: requests.Session | None = None,
    timeout: int = 30,
) -> dict:
    session = session or create_session(timeout=timeout)
    response = session.post(
        LONG_DICTIONARY_URL,
        data={"data": query, "from": from_offset},
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("result") != "success":
        return {}
    try:
        return json.loads(payload.get("data", "{}"))
    except ValueError:
        return {}


def search_customer_candidates(
    queries: list[str],
    session: requests.Session | None = None,
    timeout: int = 30,
) -> list[SberbankAstCustomerCandidate]:
    session = session or create_session(timeout=timeout)
    seen: set[tuple[str, str]] = set()
    items: list[SberbankAstCustomerCandidate] = []
    for query in queries:
        query = normalize_spaces(query)
        if not query:
            continue
        payload = _post_long_dictionary(
            query=query,
            from_offset=0,
            session=session,
            timeout=timeout,
        )
        for hit in payload.get("hits", {}).get("hits", []):
            source = hit.get("_source", {})
            candidate = SberbankAstCustomerCandidate(
                query=query,
                bu_inn=normalize_spaces(source.get("buINN")),
                bu_kpp=normalize_spaces(source.get("buKPP")),
                bu_inn_kpp=normalize_spaces(source.get("buInnKpp")),
                full_name=normalize_spaces(source.get("FullName")),
            )
            if not candidate.bu_inn_kpp:
                continue
            key = (candidate.bu_inn_kpp, candidate.full_name)
            if key in seen:
                continue
            seen.add(key)
            items.append(candidate)
    return items


def _token_set(value: str) -> set[str]:
    return {
        token
        for token in re.split(r"[^0-9a-zа-я]+", value.lower())
        if token and len(token) > 1
    }


def select_best_candidates(
    candidates: list[SberbankAstCustomerCandidate],
    expected_name: str,
    inn: str | None = None,
) -> list[SberbankAstCustomerCandidate]:
    if not candidates:
        return []

    if inn:
        exact_inn = [item for item in candidates if item.bu_inn == inn]
        if exact_inn:
            return exact_inn

    expected_tokens = _token_set(expected_name)

    def score(candidate: SberbankAstCustomerCandidate) -> tuple[int, int, int]:
        full_name = candidate.full_name.lower()
        overlap = len(expected_tokens & _token_set(candidate.full_name))
        contains = int(normalize_spaces(expected_name).lower() in full_name)
        query_overlap = len(_token_set(candidate.query) & _token_set(candidate.full_name))
        return contains, overlap, query_overlap

    ranked = sorted(candidates, key=score, reverse=True)
    best_score = score(ranked[0])
    return [item for item in ranked if score(item) == best_score]


def _leaf_value(tag: Tag) -> str:
    if tag.name == "input":
        return tag.get("value", "")
    return tag.get_text("", strip=True)


def _render_content_tree(tag: Tag) -> ET.Element | list[ET.Element] | None:
    content = tag.get("content")
    if not content:
        rendered_items: list[ET.Element] = []
        for child in tag.children:
            if not isinstance(child, Tag):
                continue
            rendered = _render_content_tree(child)
            if isinstance(rendered, list):
                rendered_items.extend(rendered)
            elif rendered is not None:
                rendered_items.append(rendered)
        return rendered_items

    kind, name = content.split(":", 1)
    if kind == "leaf":
        element = ET.Element(name)
        element.text = _leaf_value(tag)
        return element

    element = ET.Element(name)
    for child in tag.children:
        if not isinstance(child, Tag):
            continue
        rendered = _render_content_tree(child)
        if isinstance(rendered, list):
            for item in rendered:
                element.append(item)
        elif rendered is not None:
            element.append(rendered)
    return element


def _date_floor(value: str) -> str:
    value = normalize_spaces(value)
    return f"{value} 00:00" if len(value) == 10 else value


def _date_ceiling(value: str) -> str:
    value = normalize_spaces(value)
    return f"{value} 23:59" if len(value) == 10 else value


def build_request_xml(
    registry_html: str,
    customer: SberbankAstCustomerCandidate,
    date_from: str,
    date_to: str,
    offset: int = 0,
    page_size: int = 20,
) -> str:
    soup = BeautifulSoup(registry_html, "lxml")
    mutations = [
        ('[content="node:PublicDate"] input[content="leaf:minvalue"]', _date_floor(date_from)),
        ('[content="node:PublicDate"] input[content="leaf:maxvalue"]', _date_ceiling(date_to)),
        ('[content="node:CustomerDictionary"] [content="leaf:value"]', customer.bu_inn_kpp),
        ('[content="node:customer"] [content="leaf:visiblepart"]', customer.full_name),
        ('#PageSize', str(page_size)),
        ('#CurrPage', str(offset)),
    ]
    for selector, value in mutations:
        element = soup.select_one(selector)
        if element is None:
            continue
        if element.name == "input":
            element["value"] = value
        else:
            element.string = value

    root_tag = soup.select_one('#xmlContainer > div[content="node:elasticrequest"]')
    if root_tag is None:
        raise ValueError("Could not find xmlContainer root on Sberbank-AST page")
    rendered = _render_content_tree(root_tag)
    if rendered is None or isinstance(rendered, list):
        raise ValueError("Could not render Sberbank-AST XML request")
    return ET.tostring(rendered, encoding="unicode")


def fetch_search_results(
    registry_html: str,
    customer: SberbankAstCustomerCandidate,
    date_from: str,
    date_to: str,
    offset: int = 0,
    page_size: int = 20,
    session: requests.Session | None = None,
    timeout: int = 30,
) -> SberbankAstSearchResponse:
    session = session or create_session(timeout=timeout)
    request_xml = build_request_xml(
        registry_html=registry_html,
        customer=customer,
        date_from=date_from,
        date_to=date_to,
        offset=offset,
        page_size=page_size,
    )
    response = session.post(
        SEARCH_URL,
        data={
            "xmlData": request_xml,
            "orgId": "0",
            "buId": "0",
            "personId": "0",
            "buMainId": "0",
            "personMainId": "0",
        },
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    data = payload.get("data", {}).get("Data", {})
    table_xml = data.get("tableXml", "")
    raw_data = data.get("data", "")
    total = parse_total(table_xml)
    return SberbankAstSearchResponse(
        total=total,
        table_xml=table_xml,
        raw_data=raw_data,
        search_url=REGISTRY_URL,
        request_xml=request_xml,
    )


def parse_total(table_xml: str) -> int:
    if not table_xml.strip():
        return 0
    root = ET.fromstring(table_xml)
    total_text = root.findtext("./total/value") or "0"
    try:
        return int(total_text)
    except ValueError:
        return 0


def parse_search_items(
    table_xml: str,
    entity_name: str,
    customer_query: str,
) -> list[SberbankAstSearchItem]:
    if not table_xml.strip():
        return []
    root = ET.fromstring(table_xml)
    items: list[SberbankAstSearchItem] = []
    for hit in root.findall("./hits"):
        source = hit.find("./_source")
        if source is None:
            continue
        published_at = parse_ru_datetime(source.findtext("PublicDate"))
        deadline_at = parse_ru_datetime(source.findtext("RequestDate") or source.findtext("EndDate"))
        raw_price = parse_ru_decimal(source.findtext("purchAmount"))
        items.append(
            SberbankAstSearchItem(
                source_system="sberbank_ast",
                platform_section=normalize_spaces(source.findtext("SourceTerm")),
                entity_name=entity_name,
                customer_query=customer_query,
                procedure_number=normalize_spaces(
                    source.findtext("purchCode") or source.findtext("purchCodeTerm")
                ),
                lot_number="1",
                subject=normalize_spaces(source.findtext("purchName") or source.findtext("BidName")),
                customer_name=normalize_spaces(
                    source.findtext("OrgName") or source.findtext("CustomerFullName")
                ),
                region="",
                status=normalize_spaces(
                    source.findtext("purchStateName") or source.findtext("BidStatusName")
                ),
                tender_type=normalize_spaces(source.findtext("PurchaseTypeName")),
                price_rub=raw_price if raw_price and raw_price > 0 else None,
                deadline_at=deadline_at.isoformat() if deadline_at else None,
                detail_url=normalize_spaces(source.findtext("objectHrefTerm")),
                tags=" | ".join(
                    part
                    for part in [
                        normalize_spaces(source.findtext("SourceTerm")),
                        "SMP" if normalize_spaces(source.findtext("IsSMP")) == "1" else "",
                    ]
                    if part
                ),
                published_at=published_at.isoformat() if published_at else None,
                application_deadline=deadline_at.isoformat() if deadline_at else None,
                method_name=normalize_spaces(source.findtext("PurchaseTypeName")),
                currency=normalize_spaces(source.findtext("purchCurrency") or "RUB"),
            )
        )
    return items


def is_procurement_relevant(item: SberbankAstSearchItem) -> bool:
    if item.platform_section in OUT_OF_SCOPE_SECTIONS:
        return False
    lowered_url = item.detail_url.lower()
    if "/property/" in lowered_url or "/bankruptcy/" in lowered_url:
        return False

    method_text = normalize_spaces(" ".join([item.tender_type, item.method_name]))
    if any(pattern.search(method_text) for pattern in OUT_OF_SCOPE_METHOD_PATTERNS):
        return False

    subject = normalize_spaces(item.subject)
    return not any(pattern.search(subject) for pattern in ASSET_SALE_SUBJECT_PATTERNS)


def search_item_to_dict(item: SberbankAstSearchItem) -> dict:
    return asdict(item)
