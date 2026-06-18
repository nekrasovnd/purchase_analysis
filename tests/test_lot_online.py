import unittest

from purchase_analysis.clients.lot_online import (
    build_query_payload,
    parse_search_items,
    parse_total,
)


PAYLOAD = {
    "userAutorized": False,
    "count": 1,
    "totalCount": 1,
    "list": [
        {
            "type": "BUYING",
            "title": 'Право заключения договора на поставку оборудования для ПАО "Тест"',
            "features": ["SMP"],
            "okdp2": ["25.73.60.150"],
            "price": "<div class='aright'>369 900,00 руб.<br/>(в т.ч. НДС 20%)</div>",
            "state": {"title": "Идет прием заявок"},
            "identifier": "RAD260028418",
            "lotNumber": 1,
            "gdEndDate": "17.06.2026 12:00&nbsp;МСК",
            "placementDateTime": "11.06.2026 18:16",
            "regionCodes": ["Липецкая, обл"],
            "organizer": {
                "inn": "6901067107",
                "title": 'Филиал ПАО "Россети Центр" - "Липецкэнерго"',
            },
            "placementType": "Сравнение цен в электронной форме",
            "lotLink": "/etp/app/LotCard/page?LotCard.lotEntity=test",
            "customer": [
                {
                    "inn": "6901067107",
                    "title": 'Филиал ПАО "Россети Центр" - "Липецкэнерго"',
                }
            ],
        }
    ],
}


class LotOnlineClientTest(unittest.TestCase):
    def test_build_query_payload_customer(self) -> None:
        payload = build_query_payload(customer_title="7707083893")
        self.assertEqual(payload["customer"]["title"], "7707083893")
        self.assertEqual(payload["types"], ["BUYING", "RFI", "SMALL_PURCHASE"])

    def test_parse_search_items(self) -> None:
        items = parse_search_items(
            PAYLOAD,
            entity_name="ПАО Сбербанк России",
            customer_query="7707083893",
        )
        self.assertEqual(parse_total(PAYLOAD), 1)
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item.procedure_number, "RAD260028418")
        self.assertEqual(item.lot_number, "1")
        self.assertEqual(item.status, "Идет прием заявок")
        self.assertEqual(item.platform_section, "Сравнение цен в электронной форме")
        self.assertEqual(item.tender_type, "BUYING")
        self.assertEqual(item.customer_inn, "6901067107")
        self.assertEqual(item.organizer_inn, "6901067107")
        self.assertAlmostEqual(item.price_rub or 0, 369900.0)
        self.assertEqual(item.currency, "RUB")
        self.assertTrue(item.detail_url.endswith("LotCard.lotEntity=test"))


if __name__ == "__main__":
    unittest.main()
