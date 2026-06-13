from collections import defaultdict
from dataclasses import dataclass
import re
from typing import Iterable

import requests
from bs4 import BeautifulSoup

from purchase_analysis.utils.text import html_unescape, normalize_spaces

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
