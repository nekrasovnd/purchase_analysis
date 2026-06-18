import unittest

import pandas as pd

from purchase_analysis.postgres_loader import (
    build_document_link_load_frame,
    build_document_text_load_frame,
    build_entity_scope_load_frame,
    build_procurement_item_load_frame,
    build_procurement_lot_load_frame,
    build_procurement_participant_load_frame,
)


class PostgresLoaderTest(unittest.TestCase):
    def test_build_entity_scope_load_frame_merges_scope_and_coverage(self) -> None:
        scope_df = pd.DataFrame(
            [
                {
                    "entity_key": "main_bank",
                    "group_name": "Sber Group",
                    "entity_name": "ПАО Сбербанк России",
                    "entity_type": "bank",
                    "inn": "7707083893",
                    "ogrn": "1027700132195",
                    "kpp_list": "773601001",
                    "official_name": "ПАО Сбербанк России",
                    "short_name": "Сбербанк",
                    "brand_aliases": "Сбер",
                    "search_terms": "Сбербанк",
                    "eis_search_term": "Сбербанк",
                    "roseltorg_customer_query": "СБЕРБАНК",
                    "is_priority_focus": "1",
                    "identity_source": "eis_exact",
                    "identity_confidence": "verified",
                    "notes": "seed",
                },
                {
                    "entity_key": "new_entity",
                    "group_name": "Sber Group",
                    "entity_name": "ООО Новый Контур",
                    "entity_type": "service",
                    "inn": "1234567890",
                    "is_priority_focus": "0",
                    "identity_source": "manual",
                    "identity_confidence": "review",
                },
            ]
        )
        coverage_df = pd.DataFrame(
            [
                {
                    "entity_name": "ПАО   Сбербанк   России",
                    "resolved_inn": "7707083893",
                    "eis_entity_code": "EIS-1",
                    "eis_entity_name": "ПАО Сбербанк России",
                    "eis_resolved_inn": "7707083893",
                    "eis_resolved_kpp": "773601001",
                    "eis_resolved_ogrn": "1027700132195",
                    "eis_fz94id": "fz94",
                    "eis_fz223id": "fz223",
                    "eis_223_open_count": "3",
                    "eis_results_url": "https://example.test/eis",
                    "roseltorg_lot_count": "5",
                    "sberbank_ast_candidate_count": "7",
                    "sberbank_ast_lot_count": "11",
                    "zakazrf_candidate_count": "1",
                    "zakazrf_lot_count": "0",
                    "lot_online_lot_count": "2",
                    "lot_online_title_mention_count": "9",
                }
            ]
        )

        result = build_entity_scope_load_frame(scope_df, coverage_df)

        self.assertEqual(len(result), 2)
        first_row = result.iloc[0]
        self.assertEqual(first_row["entity_key"], "main_bank")
        self.assertEqual(first_row["resolved_inn"], "7707083893")
        self.assertEqual(first_row["eis_entity_code"], "EIS-1")
        self.assertEqual(int(first_row["eis_223_open_count"]), 3)
        self.assertEqual(int(first_row["sberbank_ast_lot_count"]), 11)
        self.assertTrue(bool(first_row["is_priority_focus"]))
        self.assertEqual(first_row["identity_notes"], "seed")

        second_row = result[result["entity_key"] == "new_entity"].iloc[0]
        self.assertEqual(int(second_row["lot_online_lot_count"]), 0)
        self.assertTrue(pd.isna(second_row["resolved_inn"]))
        self.assertFalse(bool(second_row["is_priority_focus"]))

    def test_build_procurement_lot_load_frame_resolves_entity_ids_and_parses_values(self) -> None:
        lots_df = pd.DataFrame(
            [
                {
                    "entity_name": "ООО   Сбер Тест",
                    "source_system": "sberbank_ast",
                    "platform_section": "SberB2B",
                    "procedure_number": "100",
                    "lot_number": "1",
                    "subject": "Тестовый лот",
                    "customer_name": "ООО Сбер Тест",
                    "customer_inn": "7701000000",
                    "price_rub": "1250.50",
                    "currency": "RUB",
                    "published_at": "2025-01-02T10:30:00+03:00",
                    "deadline_at": "2025-01-10 12:00:00",
                    "application_deadline": "2025-01-10 12:00:00",
                    "method_name": "Запрос предложений",
                    "detail_url": "https://example.test/lot/100",
                    "duplicate_group_size": "2",
                }
            ]
        )
        entity_lookup = pd.DataFrame([{"entity_id": 42, "entity_name": "ООО Сбер Тест"}])

        result = build_procurement_lot_load_frame(lots_df, entity_lookup)

        self.assertEqual(len(result), 1)
        row = result.iloc[0]
        self.assertEqual(int(row["entity_id"]), 42)
        self.assertEqual(row["customer_inn"], "7701000000")
        self.assertEqual(float(row["price_rub"]), 1250.5)
        self.assertEqual(int(row["duplicate_group_size"]), 2)
        self.assertEqual(row["published_at"].year, 2025)
        self.assertIsNone(row["published_at"].tzinfo)

    def test_build_procurement_lot_load_frame_resolves_approved_aliases(self) -> None:
        lots_df = pd.DataFrame(
            [
                {
                    "entity_name": "ООО СберТех",
                    "customer_name": 'АО "СБЕРТЕХ"',
                    "customer_inn": "7736632467",
                    "source_system": "sberbank_ast",
                    "procedure_number": "200",
                    "lot_number": "1",
                },
                {
                    "entity_name": "ООО Сбербанк-Телеком",
                    "customer_name": 'ООО "СБЕРБАНК-ТЕЛЕКОМ"',
                    "source_system": "roseltorg",
                    "procedure_number": "201",
                    "lot_number": "2",
                },
            ]
        )
        entity_lookup = pd.DataFrame(
            [
                {
                    "entity_id": 7,
                    "entity_name": "АО Сбербанк-Технологии (СберТех)",
                    "official_name": 'АКЦИОНЕРНОЕ ОБЩЕСТВО "СБЕРБАНК - ТЕХНОЛОГИИ"',
                    "short_name": "Сбербанк-Технологии",
                    "brand_aliases": "СберТех;Сбербанк-Технологии",
                    "search_terms": "СберТех;Сбербанк Технологии",
                    "inn": "7736632467",
                },
                {
                    "entity_id": 9,
                    "entity_name": "ООО Сбербанк-Телеком (СберМобайл)",
                    "official_name": 'ОБЩЕСТВО С ОГРАНИЧЕННОЙ ОТВЕТСТВЕННОСТЬЮ "СБЕРБАНК-ТЕЛЕКОМ"',
                    "short_name": "Сбербанк-Телеком",
                    "brand_aliases": "СберМобайл;Сбербанк-Телеком",
                    "search_terms": "Сбербанк-Телеком;Сбербанк Телеком",
                    "inn": "7736264044",
                },
            ]
        )

        result = build_procurement_lot_load_frame(lots_df, entity_lookup)

        self.assertEqual([int(value) for value in result["entity_id"].tolist()], [7, 9])

    def test_related_load_frames_resolve_lot_and_document_ids(self) -> None:
        lot_lookup = pd.DataFrame(
            [
                {
                    "lot_id": 10,
                    "source_system": "sberbank_ast",
                    "procedure_number": "100",
                    "lot_number": "1",
                }
            ]
        )
        item_df = pd.DataFrame(
            [
                {
                    "source_system": "sberbank_ast",
                    "procedure_number": "100",
                    "lot_number": "1",
                    "line_no": "2",
                    "item_name": "Ноутбук",
                    "unit_price_rub": "150000",
                    "line_total_rub": "300000",
                    "price_rub": "300000",
                }
            ]
        )
        document_links_df = pd.DataFrame(
            [
                {
                    "source_system": "",
                    "procedure_number": "100",
                    "lot_number": "1",
                    "document_name": "spec.docx",
                    "document_url": "https://example.test/spec.docx",
                    "local_path": "D:/docs/spec.docx",
                    "document_size_bytes": "1024",
                    "ocr_required": "false",
                    "pii_findings_count": "2",
                    "is_available": "true",
                }
            ]
        )
        document_lookup = pd.DataFrame(
            [
                {
                    "document_id": 77,
                    "lot_id": 10,
                    "document_name": "spec.docx",
                    "local_path": "D:/docs/spec.docx",
                }
            ]
        )
        document_texts_df = pd.DataFrame(
            [
                {
                    "source_system": "",
                    "procedure_number": "100",
                    "lot_number": "1",
                    "document_name": "spec.docx",
                    "local_path": "D:/docs/spec.docx",
                    "text_chars": "123",
                    "ocr_required": "1",
                    "pii_findings_count": "4",
                    "text_preview": "masked",
                }
            ]
        )
        participants_df = pd.DataFrame(
            [
                {
                    "source_system": "sberbank_ast",
                    "procedure_number": "100",
                    "lot_number": "1",
                    "participant_role": "supplier",
                    "participant_name": "ООО Поставщик",
                    "offer_price_rub": "99000",
                    "is_winner": "true",
                }
            ]
        )

        items_result = build_procurement_item_load_frame(item_df, lot_lookup)
        links_result = build_document_link_load_frame(document_links_df, lot_lookup)
        texts_result = build_document_text_load_frame(document_texts_df, lot_lookup, document_lookup)
        participants_result = build_procurement_participant_load_frame(participants_df, lot_lookup)

        self.assertEqual(int(items_result.iloc[0]["lot_id"]), 10)
        self.assertEqual(int(items_result.iloc[0]["line_no"]), 2)
        self.assertEqual(int(links_result.iloc[0]["document_size_bytes"]), 1024)
        self.assertFalse(bool(links_result.iloc[0]["ocr_required"]))
        self.assertTrue(bool(links_result.iloc[0]["is_available"]))
        self.assertTrue(bool(links_result.iloc[0]["pii_masked"]))
        self.assertEqual(int(texts_result.iloc[0]["document_id"]), 77)
        self.assertEqual(int(texts_result.iloc[0]["text_chars"]), 123)
        self.assertTrue(bool(texts_result.iloc[0]["ocr_required"]))
        self.assertEqual(int(participants_result.iloc[0]["lot_id"]), 10)
        self.assertTrue(bool(participants_result.iloc[0]["is_winner"]))


if __name__ == "__main__":
    unittest.main()
