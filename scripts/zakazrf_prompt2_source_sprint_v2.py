from __future__ import annotations

import argparse
import math
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, urlunparse
import time
import requests

import pandas as pd
from bs4 import BeautifulSoup

from purchase_analysis import entity_resolution
from purchase_analysis.clients import zakazrf
from purchase_analysis.config import OUTPUT_DIR, RAW_DIR
from purchase_analysis.utils.io import ensure_dir, write_text
from purchase_analysis.utils.text import normalize_spaces, safe_slug

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_BATCH_NAME = "zakazrf_prompt2_full_scope_" + datetime.now().strftime("%Y-%m-%d")


def read_scope(selected_inns: set[str] | None) -> list[entity_resolution.EntityIdentity]:
    rows = entity_resolution.load_entity_scope(ROOT_DIR / "configs" / "entity_scope.csv")
    if not selected_inns:
        return rows
    return [row for row in rows if row.inn in selected_inns]


def write_frame(path: Path, rows: list[dict[str, object]]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    ensure_dir(path.parent)
    frame.to_csv(path, index=False, encoding="utf-8-sig")
    return frame

def search_item_to_dict(item: zakazrf.ZakazRfSearchItem) -> dict[str, object]:
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
        "deadline_at": item.deadline_at,
    }


def extract_form_state(html_text: str) -> dict[str, str]:
    soup = BeautifulSoup(html_text, "lxml")
    form = soup.select_one("form[id^='form']") or soup.select_one("form")
    if form is None:
        raise ValueError("Could not find ZakazRF form state for pagination")

    values: dict[str, str] = {}
    for element in form.select("input[name], select[name], textarea[name]"):
        name = normalize_spaces(element.get("name"))
        if not name:
            continue
        if element.name == "input":
            input_type = (element.get("type") or "").lower()
            if input_type in {"checkbox", "radio"} and not element.has_attr("checked"):
                continue
            values[name] = element.get("value", "")
            continue
        if element.name == "select":
            selected = element.select("option[selected]")
            if selected:
                values[name] = selected[-1].get("value", "")
            else:
                first = element.select_one("option")
                values[name] = first.get("value", "") if first else ""
            continue
        values[name] = normalize_spaces(element.get_text(" ", strip=True))
    return values


def notifications_index_url(current_url: str) -> str:
    parsed = urlparse(current_url)
    path = parsed.path.rstrip("/")
    if not path.endswith("/Index"):
        path = f"{path}/Index"
    return urlunparse(parsed._replace(path=path))


def fetch_notification_pages(
    first_html: str,
    first_url: str,
    *,
    session: requests.Session,
    timeout: int,
    max_pages: int | None = None,
) -> list[tuple[int, str, str]]:
    pages = [(1, first_html, first_url)]
    total_rows = zakazrf.parse_total_rows(first_html)
    if total_rows <= 0:
        return pages

    state = extract_form_state(first_html)
    page_id = state.get("_orm_PageID", "")
    if not page_id:
        return pages

    page_size = int(state.get(f"PageSize{page_id}", "20") or 20)
    if page_size <= 0:
        page_size = 20
    page_count = math.ceil(total_rows / page_size)
    if max_pages is not None:
        page_count = min(page_count, max_pages)

    post_url = notifications_index_url(first_url)
    for page_number in range(2, page_count + 1):
        payload = dict(state)
        payload[f"PageNumber{page_id}"] = str(page_number)
        response = session.post(post_url, data=payload, timeout=timeout)
        response.raise_for_status()
        pages.append((page_number, response.text, response.url))
    return pages


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-name", default=DEFAULT_BATCH_NAME)
    parser.add_argument("--inns", nargs="*", help="Specific INNs to run")
    parser.add_argument("--throttle", type=float, default=2.0)
    args = parser.parse_args()

    batch_name = safe_slug(args.batch_name)
    raw_dir = RAW_DIR / "zakazrf" / batch_name
    out_dir = OUTPUT_DIR / "source_sprints" / batch_name
    ensure_dir(raw_dir / "search")
    ensure_dir(raw_dir / "purchases")
    ensure_dir(out_dir)

    inns = set(args.inns) if args.inns else None
    scope = read_scope(inns)

    session = zakazrf.create_session(timeout=60)
    session.trust_env = False
    
    registry_html = zakazrf.fetch_registry_page(session=session, timeout=60)
    write_text(raw_dir / "registry.html", registry_html)
    main_page_id = zakazrf.parse_main_page_id(registry_html)

    item_rows: list[dict[str, object]] = []
    unique_rows = 0

    for entity in scope:
        if not entity.inn:
            continue
            
        print(f"[{entity.entity_name}] Searching for INN: {entity.inn}")
        time.sleep(args.throttle)
        
        try:
            dialog_html, dialog_url = zakazrf.fetch_customer_dialog(
                main_page_id,
                dialog_id=f"dialog_{safe_slug(entity.inn)}",
                session=session,
                timeout=60,
            )
            context = zakazrf.parse_customer_dialog_context(dialog_html, main_page_id=main_page_id, dialog_url=dialog_url)
            
            customer_search_html, customer_search_url = zakazrf.search_customer_candidates(
                context,
                dialog_id=f"dialog_{safe_slug(entity.inn)}",
                inn=entity.inn,
                session=session,
                timeout=60,
            )
        except Exception as e:
            print(f"  [ERROR] fetching search page: {e}")
            continue
            
        slug = safe_slug(f"{entity.entity_name}_{entity.inn}")
        write_text(raw_dir / "search" / f"{slug}.html", customer_search_html)
        
        candidates = zakazrf.parse_customer_candidates(customer_search_html)
        print(f"  Found {len(candidates)} company candidates.")
        
        for candidate in candidates:
            # Check if this company really matches? It's searched by exact INN.
            print(f"    -> Fetching purchases for company {candidate.internal_id}")
            time.sleep(args.throttle)
            
            try:
                notifications_html, notifications_url = zakazrf.fetch_notifications(
                    candidate.internal_id,
                    session=session,
                    timeout=60,
                )
                notification_pages = fetch_notification_pages(
                    notifications_html,
                    notifications_url,
                    session=session,
                    timeout=60,
                    max_pages=None,
                )
            except Exception as e:
                print(f"      [ERROR] fetching notifications: {e}")
                continue
                
            for page_number, page_html, page_url in notification_pages:
                write_text(raw_dir / "purchases" / f"{slug}_{candidate.internal_id}_p{page_number}.html", page_html)
                
                try:
                    page_items = zakazrf.parse_notification_rows(
                        page_html,
                        entity_name=entity.entity_name,
                        customer_query=candidate.full_name,
                    )
                except Exception as e:
                    print(f"      [ERROR] parsing notifications: {e}")
                    break
                    
                print(f"      Page {page_number}: found {len(page_items)} lots.")
                for item in page_items:
                    unique_rows += 1
                    item_rows.append(search_item_to_dict(item))

    print("\n--- SPRINT SUMMARY ---")
    print(f"New Unique Lots Found: {unique_rows}")

    if item_rows:
        write_frame(out_dir / "items.csv", item_rows)
        print(f"Saved {len(item_rows)} items to {out_dir / 'items.csv'}")

if __name__ == "__main__":
    main()
