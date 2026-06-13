import unittest

import pandas as pd

from purchase_analysis.analysis import build_procurement_items_frame, build_unit_price_benchmarks_mart


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


if __name__ == "__main__":
    unittest.main()
