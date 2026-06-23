from collections import defaultdict
from dataclasses import dataclass
import re
from typing import Iterable

import requests
from bs4 import BeautifulSoup

from purchase_analysis.utils.text import html_unescape, normalize_spaces, parse_ru_datetime

BASE_URL = "https://zakupki.gov.ru"
ORG_CHOOSER_URL = (
    f"{BASE_URL}/epz/organization/chooseOrganization/chooseOrganizationTableModal.html"
)
RESULTS_URL = f"{BASE_URL}/epz/order/extendedsearch/results.html"

MAP_LINE_RE = re.compile(
    r"_customerIdOrg_all_checkedtempMap(?P<idx>\d+)\.set\('(?P<field>[^']+)', \"(?P<value>.*?)\"\);"
)
TOTAL_RE = re.compile(r"(\d+)\s+запис")


@dataclass(slots=True)
class EisEntityCandidate:
    search_term: str
    code: str
    name: str
    fz94id: str
    fz223id: str
    inn: str
    kpp: str
    ogrn: str
    draft_id: str


@dataclass(slots=True)
class EisSearchItem:
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
    published_at: str | None
    deadline_at: str | None
    tender_url: str | None = None


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


def fetch_choose_organization_table(
    search_term: str,
    session: requests.Session | None = None,
    timeout: int = 30,
) -> str:
    session = session or create_session(timeout=timeout)
    response = session.get(
        ORG_CHOOSER_URL,
        params={
            "searchString": search_term,
            "page": 1,
            "organizationType": "ALL",
            "placeOfSearch": "FZ_223",
            "inputId": "customerIdOrg",
        },
        timeout=timeout,
    )
    response.raise_for_status()
    return response.text


def parse_choose_organization_table(
    html_text: str,
    search_term: str,
) -> list[EisEntityCandidate]:
    grouped: dict[str, dict[str, str]] = defaultdict(dict)
    for match in MAP_LINE_RE.finditer(html_text):
        grouped[match.group("idx")][match.group("field")] = html_unescape(
            match.group("value")
        )

    candidates: list[EisEntityCandidate] = []
    for record in grouped.values():
        if not record.get("code") or not record.get("name"):
            continue
        candidates.append(
            EisEntityCandidate(
                search_term=search_term,
                code=record.get("code", ""),
                name=normalize_spaces(record.get("name")),
                fz94id=record.get("fz94id", ""),
                fz223id=record.get("fz223id", ""),
                inn=record.get("inn", ""),
                kpp=record.get("kpp", ""),
                ogrn=record.get("ogrn", ""),
                draft_id=record.get("draftId", ""),
            )
        )
    return candidates


def _token_set(value: str) -> set[str]:
    return {
        token
        for token in re.split(r"[^0-9a-zа-я]+", value.lower())
        if token and len(token) > 1
    }


def select_best_candidate(
    candidates: Iterable[EisEntityCandidate],
    expected_name: str,
    inn: str | None = None,
) -> EisEntityCandidate | None:
    candidates = list(candidates)
    if not candidates:
        return None
    if inn:
        exact = next((item for item in candidates if item.inn == inn), None)
        if exact:
            return exact

    expected_tokens = _token_set(expected_name)

    def score(candidate: EisEntityCandidate) -> tuple[int, int]:
        name_tokens = _token_set(candidate.name)
        overlap = len(expected_tokens & name_tokens)
        contains = int(normalize_spaces(expected_name).lower() in candidate.name.lower())
        return contains, overlap

    return max(candidates, key=score)


def build_customer_filter_value(candidate: EisEntityCandidate) -> str:
    return (
        f"{candidate.code}:{candidate.name}zZ{candidate.code}"
        f"zZ{candidate.fz94id}zZ{candidate.fz223id}zZ{candidate.inn}"
        f"zZ{candidate.draft_id}zZ{candidate.kpp}zZ{candidate.ogrn}"
    )


def fetch_procurement_results(
    candidate: EisEntityCandidate,
    date_from: str,
    date_to: str,
    session: requests.Session | None = None,
    timeout: int = 30,
) -> tuple[str, str]:
    session = session or create_session(timeout=timeout)
    response = session.get(
        RESULTS_URL,
        params={
            "searchString": "",
            "morphology": "on",
            "sortBy": "UPDATE_DATE",
            "recordsPerPage": "_10",
            "showLotsInfoHidden": "false",
            "fz223": "on",
            "customerIdOrg": build_customer_filter_value(candidate),
            "publishDateFrom": date_from,
            "publishDateTo": date_to,
        },
        timeout=timeout,
    )
    response.raise_for_status()
    return response.text, response.url


def parse_results_total(html_text: str) -> int:
    soup = BeautifulSoup(html_text, "lxml")
    total_block = soup.select_one(".search-results__total")
    if not total_block:
        return 0
    match = TOTAL_RE.search(normalize_spaces(total_block.get_text(" ", strip=True)))
    return int(match.group(1)) if match else 0


def count_procurements_223(
    candidate: EisEntityCandidate,
    date_from: str,
    date_to: str,
    session: requests.Session | None = None,
    timeout: int = 30,
) -> tuple[int, str, str]:
    html_text, url = fetch_procurement_results(
        candidate=candidate,
        date_from=date_from,
        date_to=date_to,
        session=session,
        timeout=timeout,
    )
    return parse_results_total(html_text), html_text, url


def parse_cards(
    html_text: str,
    *,
    entity_name: str,
    customer_query: str,
    customer_name: str,
    law: str,
) -> list[EisSearchItem]:
    soup = BeautifulSoup(html_text, "lxml")
    cards: list[EisSearchItem] = []
    seen: set[str] = set()
    for block in soup.select(".search-registry-entry-block"):
        text = normalize_spaces(block.get_text(" ", strip=True))
        if len(text) < 50:
            continue
        number_match = re.search(r"(?:№\s*)?([0-9]{11,25})", text)
        number = number_match.group(1) if number_match else ""
        key = number or text[:500]
        if key in seen:
            continue
        seen.add(key)
        
        price_match = re.search(r"([0-9][0-9\s.,]+)\s*(?:₽|руб)", text, flags=re.I)
        price_str = price_match.group(1).replace(" ", "").replace(",", ".") if price_match else None
        price_rub = float(price_str) if price_str else None
        
        subject_match = block.select_one(".registry-entry__body-value")
        subject = normalize_spaces(subject_match.get_text(" ", strip=True)) if subject_match else text[:200]
        
        published_at = None
        for data_block in block.select(".data-block, .data-block__title"):
            # sometimes .data-block__title and .data-block__value are siblings instead of being inside .data-block
            # wait, actually let's just search all titles
            pass
        
        # Simpler approach: find all titles, look at next sibling
        for title_node in block.select(".data-block__title"):
            t_text = normalize_spaces(title_node.get_text(" ", strip=True)).lower()
            if "размещено" in t_text:
                val_node = title_node.find_next_sibling(class_="data-block__value")
                if val_node:
                    dt = parse_ru_datetime(val_node.get_text(" ", strip=True))
                    if dt:
                        published_at = dt.isoformat()
        
        status_match = block.select_one(".registry-entry__header-mid__title")
        status = normalize_spaces(status_match.get_text(" ", strip=True)) if status_match else ""
        
        tender_url = None
        for a_tag in block.select("a[href]"):
            href = a_tag["href"]
            if number and number in href:
                if "printForm" in href:
                    continue
                if href.startswith("/"):
                    tender_url = f"{BASE_URL}{href}"
                else:
                    tender_url = href
                break
        
        cards.append(EisSearchItem(
            source_system="eis",
            platform_section=law,
            entity_name=entity_name,
            customer_query=customer_query,
            procedure_number=number,
            lot_number="",
            subject=subject,
            customer_name=customer_name,
            region="",
            status=status,
            tender_type="",
            price_rub=price_rub,
            published_at=published_at,
            deadline_at=None,
            tender_url=tender_url,
        ))
    return cards


def search_item_to_dict(item: EisSearchItem) -> dict[str, object]:
    return {
        "source_system": item.source_system,
        "platform_section": item.platform_section,
        "entity_name": item.entity_name,
        "customer_query": item.customer_query,
        "procedure_number": item.procedure_number,
        "lot_number": item.lot_number,
        "subject": item.subject,
        "customer_name": item.customer_name,
        "region": item.region,
        "status": item.status,
        "tender_type": item.tender_type,
        "price_rub": item.price_rub,
        "published_at": item.published_at,
        "deadline_at": item.deadline_at,
        "tender_url": item.tender_url,
    }


def fetch_document_links(session: requests.Session, tender_url: str) -> list[tuple[str, str]]:
    """Returns list of (file_name, download_url)"""
    if not tender_url:
        return []
        
    doc_url = tender_url.replace("common-info.html", "documents.html")
    doc_url = doc_url.replace("notice_info.html", "documents.html")
    
    # Fallback if the link was still malformed
    if "documents.html" not in doc_url:
        if "regNumber=" in tender_url:
            import urllib.parse
            parsed = urllib.parse.urlparse(tender_url)
            qs = urllib.parse.parse_qs(parsed.query)
            if "regNumber" in qs:
                doc_url = f"{BASE_URL}/epz/order/notice/ea20/view/documents.html?regNumber={qs['regNumber'][0]}"
    
    try:
        resp = session.get(doc_url, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        
        docs = []
        for a_tag in soup.select("a[href]"):
            href = a_tag["href"]
            if "file.html" in href or "download" in href or "getFile" in href or "attachment" in href:
                name = normalize_spaces(a_tag.get_text(" ", strip=True))
                if not name:
                    name = a_tag.get("title", "document").strip()
                if href.startswith("/"):
                    href = f"{BASE_URL}{href}"
                
                # Check to avoid duplicate links
                if not any(d_url == href for _, d_url in docs):
                    docs.append((name or "document", href))
        return docs
    except Exception as e:
        print(f"    [WARN] Error fetching documents from {doc_url}: {e}")
        return []
