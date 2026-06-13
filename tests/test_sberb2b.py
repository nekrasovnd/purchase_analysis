import html
import json
import unittest

from purchase_analysis.clients import sberb2b


NEED = {
    "id": "need-1",
    "number": "88830046",
    "name": "Ящики с крышкой и клипсами",
    "created_at": "2025-12-30T13:50:09+03:00",
    "status": "published",
    "state": "active",
    "public_request_status": "published",
    "customer": {"short_name": "ПАО СБЕРБАНК", "inn": "7707083893"},
    "need_condition": {
        "id": "condition-1",
        "total_price": 9876.0,
        "medias": [
            {
                "web_path": "/uploads/documents/aa/bb/",
                "name": "stored.bin",
                "original_name": "Техническое задание.docx",
                "size": 123,
                "file": {
                    "web_path": "/uploads/documents/aa/bb/",
                    "name": "stored.bin",
                    "original_name": "Техническое задание.docx",
                    "size": 123,
                    "type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    "file_hash": "hash-1",
                },
            }
        ],
    },
}


GOODS = {
    "success": True,
    "data": {
        "page": 1,
        "limit": 20,
        "total": 1,
        "goods": [
            {
                "c_id": "line-1",
                "c_description": "Ящик 70 литров",
                "c_comment": "Материал: полипропилен",
                "c_priceWithTax": 1927.0,
                "c_count": 3.0,
                "c_okpd2Code": "22.29.29.190",
                "c_okpd2Name": "Изделия пластмассовые прочие",
                "c_unitName": "шт",
                "c_unitOkeiCode": "796",
            }
        ],
    },
}


class SberB2BClientTest(unittest.TestCase):
    def test_parse_public_need(self) -> None:
        payload = html.escape(json.dumps(NEED, ensure_ascii=False))
        page = f"<need-for-public-page :need=\"{payload}\"></need-for-public-page>"
        need = sberb2b.parse_public_need(page)
        self.assertEqual(need.procedure_number, "88830046")
        self.assertEqual(need.condition_id, "condition-1")
        self.assertEqual(need.customer_inn, "7707083893")
        self.assertAlmostEqual(need.detail_price_rub or 0, 9876.0)

    def test_goods_payload_to_item_rows(self) -> None:
        payload = html.escape(json.dumps(NEED, ensure_ascii=False))
        page = f"<need-for-public-page :need=\"{payload}\"></need-for-public-page>"
        need = sberb2b.parse_public_need(page)
        rows = sberb2b.goods_payload_to_item_rows(GOODS, need, entity_name="ПАО Сбербанк")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["okpd_code"], "22.29.29.190")
        self.assertAlmostEqual(rows[0]["unit_price_rub"], 1927.0)
        self.assertAlmostEqual(rows[0]["line_total_rub"], 5781.0)

    def test_iter_public_documents(self) -> None:
        docs = sberb2b.iter_public_documents(NEED)
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]["document_name"], "Техническое задание.docx")
        self.assertEqual(docs[0]["document_hash"], "hash-1")
        self.assertTrue(docs[0]["document_url"].startswith("https://sberb2b.ru/uploads/"))


if __name__ == "__main__":
    unittest.main()
