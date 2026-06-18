import unittest

import pandas as pd

from purchase_analysis.analysis import (
    build_procurement_items_frame,
    build_procurements_frame,
    build_unit_price_benchmarks_mart,
)


class AnalysisEnrichmentTest(unittest.TestCase):
    def test_extra_items_replace_lot_fallback_and_build_benchmark(self) -> None:
        lots = pd.DataFrame(
            [
                {
                    "source_system": "sberbank_ast",
                    "entity_name": "ПАО Сбербанк",
                    "procedure_number": "1",
                    "lot_number": "1",
                    "subject": "Стулья офисные",
                    "okpd_code": "",
                    "okpd_name": "",
                    "quantity": None,
                    "unit": "",
                    "focus_category": "Office & Admin",
                    "price_rub": 30000,
                }
            ]
        )
        extra = [
            {
                "source_system": "sberbank_ast",
                "entity_name": "ПАО Сбербанк",
                "procedure_number": "1",
                "lot_number": "1",
                "line_no": 1,
                "item_name": "Стул офисный",
                "okpd_code": "31.01.11.150",
                "okpd_name": "Мебель офисная",
                "quantity": 10,
                "unit": "шт",
                "unit_price_rub": 3000,
                "line_total_rub": 30000,
                "price_rub": 30000,
            },
            {
                "source_system": "sberbank_ast",
                "entity_name": "ПАО Сбербанк",
                "procedure_number": "2",
                "lot_number": "1",
                "line_no": 1,
                "item_name": "Стул офисный",
                "okpd_code": "31.01.11.150",
                "okpd_name": "Мебель офисная",
                "quantity": 1,
                "unit": "шт",
                "unit_price_rub": 7000,
                "line_total_rub": 7000,
                "price_rub": 7000,
            },
        ]
        lots = pd.concat(
            [
                lots,
                lots.assign(procedure_number="2", price_rub=7000),
            ],
            ignore_index=True,
        )
        items = build_procurement_items_frame(lots, extra)
        self.assertEqual(len(items), 2)
        self.assertTrue((items["unit_price_source"] != "lot_total_fallback").all())
        benchmarks = build_unit_price_benchmarks_mart(items)
        self.assertEqual(len(benchmarks), 2)
        self.assertIn("ratio_to_median_unit_price", benchmarks.columns)

    def test_procurements_use_detail_publication_date_fallback(self) -> None:
        search_rows = [
            {
                "source_system": "roseltorg",
                "platform_section": "Roseltorg.Business",
                "entity_name": "Sber entity",
                "customer_query": "Sber entity",
                "procedure_number": "B0104251649415",
                "lot_number": "1",
                "subject": "Service procurement",
                "customer_name": "Sber entity",
                "region": "",
                "status": "",
                "tender_type": "",
                "price_rub": "1000",
                "deadline_at": "2025-04-10T00:00:00",
                "detail_url": "https://example.test/procedure/B0104251649415/1",
                "tags": "",
                "published_at": None,
                "application_deadline": None,
                "method_name": None,
                "currency": None,
            },
            {
                "source_system": "roseltorg",
                "platform_section": "Roseltorg.Business",
                "entity_name": "Sber entity",
                "customer_query": "Sber entity",
                "procedure_number": "B0101260000001",
                "lot_number": "1",
                "subject": "Out of range procurement",
                "customer_name": "Sber entity",
                "region": "",
                "status": "",
                "tender_type": "",
                "price_rub": "1000",
                "deadline_at": "2026-01-10T00:00:00",
                "detail_url": "https://example.test/procedure/B0101260000001/1",
                "tags": "",
                "published_at": None,
                "application_deadline": None,
                "method_name": None,
                "currency": None,
            },
        ]
        detail_rows = [
            {
                "procedure_number": "B0104251649415",
                "lot_number": "1",
                "published_at": "2025-04-01T00:00:00",
                "application_deadline": "2025-04-10T00:00:00",
                "method_name": "request",
                "currency": "RUB",
                "detail_price_rub": "1000",
            },
            {
                "procedure_number": "B0101260000001",
                "lot_number": "1",
                "published_at": "2026-01-01T00:00:00",
                "application_deadline": "2026-01-10T00:00:00",
                "method_name": "request",
                "currency": "RUB",
                "detail_price_rub": "1000",
            }
        ]

        lots = build_procurements_frame(search_rows, detail_rows, date_from="01.01.2024", date_to="31.12.2025")

        self.assertEqual(len(lots), 1)
        self.assertEqual(lots.loc[0, "procedure_number"], "B0104251649415")
        self.assertEqual(int(lots.loc[0, "publication_year"]), 2025)
        self.assertEqual(str(lots.loc[0, "publication_month"]), "2025-04")
        self.assertTrue(pd.notna(lots.loc[0, "published_at"]))


if __name__ == "__main__":
    unittest.main()
