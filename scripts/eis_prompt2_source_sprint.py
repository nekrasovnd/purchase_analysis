from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd
from bs4 import BeautifulSoup

from purchase_analysis.clients import eis
from purchase_analysis.config import RAW_DIR
from purchase_analysis import entity_resolution
from purchase_analysis.utils.io import ensure_dir, write_json, write_text
from purchase_analysis.utils.text import normalize_spaces, safe_slug


ROOT_DIR = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT_DIR / "output" / "source_sprints" / "eis_prompt2"
RAW_PROMPT2_DIR = RAW_DIR / "eis" / "prompt2"
DATE_FROM = "01.01.2024"
DATE_TO = "31.12.2025"


def fetch_chooser(session, search_term: str, place: str) -> str:
    response = session.get(
        eis.ORG_CHOOSER_URL,
        params={
            "searchString": search_term,
            "page": 1,
            "organizationType": "ALL",
            "placeOfSearch": place,
            "inputId": "customerIdOrg",
        },
        timeout=60,
    )
    response.raise_for_status()
    return response.text


def fetch_results(session, candidate: eis.EisEntityCandidate, law: str) -> tuple[str, str]:
    params = {
        "searchString": "",
        "morphology": "on",
        "sortBy": "UPDATE_DATE",
        "recordsPerPage": "_50",
        "showLotsInfoHidden": "false",
        "customerIdOrg": eis.build_customer_filter_value(candidate),
        "publishDateFrom": DATE_FROM,
        "publishDateTo": DATE_TO,
    }
    params[law] = "on"
    response = session.get(eis.RESULTS_URL, params=params, timeout=60)
    response.raise_for_status()
    return response.text, response.url


def parse_cards(html: str) -> list[dict[str, object]]:
    soup = BeautifulSoup(html, "lxml")
    cards: list[dict[str, object]] = []
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
        links = [
            {
                "text": normalize_spaces(anchor.get_text(" ", strip=True)),
                "href": urljoin(eis.BASE_URL, anchor.get("href") or ""),
            }
            for anchor in block.select("a[href]")[:12]
        ]
        cards.append(
            {
                "procedure_number_guess": number,
                "price_guess": price_match.group(1) if price_match else "",
                "text_preview": text[:1000],
                "links_json": json.dumps(links, ensure_ascii=False),
            }
        )
    return cards


def main() -> None:
    ensure_dir(OUT_DIR)
    ensure_dir(RAW_PROMPT2_DIR)

    scope_rows = entity_resolution.load_entity_scope(ROOT_DIR / "configs" / "entity_scope.csv")
    session = eis.create_session(timeout=60)
    # On some Windows setups requests picks up a broken system proxy even when
    # env proxy variables are empty.
    session.trust_env = False

    summary_rows: list[dict[str, object]] = []
    accepted_rows: list[dict[str, object]] = []
    review_rows: list[dict[str, object]] = []
    errors: list[dict[str, str]] = []

    for scope in scope_rows:
        entity_name = scope.entity_name
        expected_inn = scope.inn
        search_term = scope.eis_search_term
        slug = safe_slug(entity_name)
        for law, place in [("fz223", "FZ_223"), ("fz44", "FZ_44")]:
            try:
                candidates: list[eis.EisEntityCandidate] = []
                best: eis.EisEntityCandidate | None = None
                query_used = ""
                for query in entity_resolution.build_search_terms(scope, source_system="eis"):
                    chooser_html = fetch_chooser(session, query, place)
                    write_text(
                        RAW_PROMPT2_DIR / f"{slug}_{law}_chooser_{safe_slug(query)}.html",
                        chooser_html,
                    )
                    current_candidates = eis.parse_choose_organization_table(chooser_html, query)
                    candidates.extend(current_candidates)
                    current_best = eis.select_best_candidate(
                        current_candidates,
                        entity_name,
                        inn=expected_inn or None,
                    )
                    if not current_best:
                        continue
                    match_decision = entity_resolution.classify_entity_match(
                        scope,
                        candidate_name=current_best.name,
                        candidate_inn=current_best.inn,
                        candidate_ogrn=current_best.ogrn,
                        candidate_kpp=current_best.kpp,
                        role="customer",
                    )
                    if match_decision.accepted:
                        best = current_best
                        query_used = query
                        break
                if not best:
                    summary_rows.append(
                        {
                            "entity_name": entity_name,
                            "law": law,
                            "search_term": search_term,
                            "query_used": query_used,
                            "expected_inn": expected_inn,
                            "candidate_count": len(candidates),
                            "selected_inn": "",
                            "selected_name": "",
                            "results_total": 0,
                            "card_blocks": 0,
                            "accepted_cards": 0,
                            "status": "no_exact_candidate",
                            "results_url": "",
                            "raw_results_file": "",
                        }
                    )
                    continue

                html, url = fetch_results(session, best, law)
                results_path = RAW_PROMPT2_DIR / f"{slug}_{law}_results.html"
                write_text(results_path, html)
                cards = parse_cards(html)
                total = eis.parse_results_total(html)
                accepted_count = 0
                selected_match = entity_resolution.classify_entity_match(
                    scope,
                    candidate_name=best.name,
                    candidate_inn=best.inn,
                    candidate_ogrn=best.ogrn,
                    candidate_kpp=best.kpp,
                    role="customer",
                )

                for card in cards:
                    text = str(card["text_preview"])
                    record = {
                        "entity_name": entity_name,
                        "entity_key": scope.entity_id,
                        "law": law,
                        "selected_inn": best.inn,
                        "selected_ogrn": best.ogrn,
                        "selected_kpp": best.kpp,
                        "selected_name": best.name,
                        "entity_match_decision": selected_match.decision,
                        "entity_match_reason": selected_match.reason,
                        "entity_match_confidence": selected_match.confidence,
                        "procedure_number_guess": card["procedure_number_guess"],
                        "price_guess": card["price_guess"],
                        "raw_results_file": str(results_path),
                        "results_url": url,
                        "text_preview": text,
                        "links_json": card["links_json"],
                    }
                    if card["procedure_number_guess"] and selected_match.accepted:
                        accepted_count += 1
                        accepted_rows.append(
                            record | {"acceptance_reason": "accepted_by_exact_customer_filter"}
                        )
                    else:
                        review_rows.append(record | {"acceptance_reason": "rejected_or_manual_review"})

                summary_rows.append(
                    {
                        "entity_name": entity_name,
                        "law": law,
                        "search_term": search_term,
                        "query_used": query_used,
                        "expected_inn": expected_inn,
                        "candidate_count": len(candidates),
                        "selected_inn": best.inn,
                        "selected_name": best.name,
                        "results_total": total,
                        "card_blocks": len(cards),
                        "accepted_cards": accepted_count,
                        "status": (
                            "accepted_card_candidates_need_dedup"
                            if accepted_count
                            else ("exact_probe_zero" if total == 0 and not cards else "needs_manual_parse_review")
                        ),
                        "results_url": url,
                        "raw_results_file": str(results_path),
                    }
                )
            except Exception as exc:  # pragma: no cover - source sprint diagnostics
                errors.append({"entity_name": entity_name, "law": law, "error": repr(exc)})
                summary_rows.append(
                    {
                        "entity_name": entity_name,
                        "law": law,
                        "search_term": search_term,
                        "query_used": "",
                        "expected_inn": expected_inn,
                        "candidate_count": 0,
                        "selected_inn": "",
                        "selected_name": "",
                        "results_total": 0,
                        "card_blocks": 0,
                        "accepted_cards": 0,
                        "status": f"error:{exc.__class__.__name__}",
                        "results_url": "",
                        "raw_results_file": "",
                    }
                )

    summary_df = pd.DataFrame(summary_rows)
    accepted_df = pd.DataFrame(accepted_rows)
    review_df = pd.DataFrame(review_rows)

    lots_df = pd.read_csv(ROOT_DIR / "data" / "curated" / "procurement_lots.csv", encoding="utf-8-sig", dtype=str)
    core_numbers = set(lots_df["procedure_number"].astype(str))
    if not accepted_df.empty:
        accepted_df["duplicate_in_core"] = accepted_df["procedure_number_guess"].astype(str).isin(core_numbers)
        accepted_df["core_source_system"] = accepted_df["procedure_number_guess"].map(
            lambda number: ";".join(
                sorted(set(lots_df.loc[lots_df["procedure_number"].astype(str) == str(number), "source_system"]))
            )
        )
        accepted_df["decision"] = accepted_df["duplicate_in_core"].map(
            lambda duplicate: "duplicate_skip_core" if duplicate else "new_candidate_manual_review"
        )

    summary_df.to_csv(OUT_DIR / "eis_prompt2_summary.csv", index=False, encoding="utf-8-sig")
    accepted_df.to_csv(
        OUT_DIR / "eis_prompt2_accepted_card_candidates.csv", index=False, encoding="utf-8-sig"
    )
    accepted_df.to_csv(OUT_DIR / "eis_prompt2_dedup_decisions.csv", index=False, encoding="utf-8-sig")
    review_df.to_csv(OUT_DIR / "eis_prompt2_review_candidates.csv", index=False, encoding="utf-8-sig")
    write_json(OUT_DIR / "eis_prompt2_errors.json", errors)

    print(summary_df["status"].value_counts().to_string())
    print(f"accepted_before_dedup={len(accepted_df)}")
    print(
        "new_candidates="
        f"{0 if accepted_df.empty else int((accepted_df['decision'] == 'new_candidate_manual_review').sum())}"
    )


if __name__ == "__main__":
    main()
