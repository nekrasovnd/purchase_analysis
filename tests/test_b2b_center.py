import unittest

from purchase_analysis.clients import b2b_center


ORG_PAYLOAD = {
    "data": [
        {
            "value": 284642,
            "text": 'ООО "СБЕРБАНК-СЕРВИС"',
            "inn": "7736663049",
        }
    ]
}


SEARCH_HTML = """
<div class="search-stat">
  <a class="btn btn-default" data-status="actual" href="/market/?searching=1&amp;trade=all&amp;firm_id=284642">
    <span class="btn-txt">Актуально • 0</span>
  </a>
  <a class="btn btn-default" data-status="archive" href="/market/?searching=1&amp;trade=all&amp;firm_id=284642&amp;show=archive">
    <span class="btn-txt">В архиве • 178</span>
  </a>
  <a class="active btn btn-default" data-status="all" href="/market/?searching=1&amp;trade=all&amp;firm_id=284642&amp;show=all">
    <span class="btn-txt">Все • 178</span>
  </a>
</div>
<table class="search-results">
  <tbody>
    <tr>
      <td>
        <small style="color:#AAA;">Вода питьевая</small><br />
        <a href="/market/tekhnicheskoe-obsluzhivaniiu-i-remont-purifaiera-ecotronic-m30-u4le/tender-4225153/" class="search-results-title visited" target="_blank">
          Запрос цен № 4225153
          <div class="search-results-title-desc">Техническое обслуживание пурифайера Ecotronic М30-U4LE</div>
        </a>
      </td>
      <td><a target="_blank" href="/firms/ooo-sberbank-servis/284642/" class="visited">ООО "СБЕРБАНК-СЕРВИС"</a></td>
      <td class="nowrap">05.11.2025 09:48</td>
      <td class="nowrap">11.11.2025 12:00</td>
    </tr>
  </tbody>
</table>
<div class="pagi">
  <ul class="pagi-list">
    <li class="pagi-item pagi-item-current">1</li>
    <li class="pagi-item">2</li>
  </ul>
</div>
"""


DETAIL_HTML = """
<html>
  <body>
    <h1>Техническое обслуживанию и ремонт пурифайера Ecotronic М30-U4LE.</h1>
    <table border="0" cellpadding="3" cellspacing="0" width="100%">
      <tr class="c2"><td width="40%" class="fname">Тег:</td><td>Вода питьевая</td></tr>
      <tr class="c1" id="trade-info-lot-quantity"><td width="40%" class="fname">Количество:</td><td>4&nbsp;усл.ед.</td></tr>
      <tr class="c2" id="trade-info-lot-price"><td width="40%" class="fname">Общая стоимость закупки:</td><td>Без указания цены</td></tr>
      <tr class="c1" id="trade-info-lot-price-currency"><td width="40%" class="fname">Вид валюты:</td><td>руб.</td></tr>
      <tr class="c1" id="trade_info_date_begin"><td width="40%" class="fname">Дата публикации:</td><td><span itemprop="datePublished" content="2025-11-05">05.11.2025 09:48</span></td></tr>
      <tr class="c2" data-end-date="1762851600" id="trade_info_date_end"><td width="40%" class="fname">Дата окончания подачи заявок:</td><td><span class="imp">11.11.2025 12:00</span></td></tr>
      <tr class="c1" id="trade-info-organizer-name"><td width="40%" class="fname">Организатор:</td><td><a target="_blank" href="/firms/span-itemprop-author-ooo-sberbank-servis-span/284642/" class="visited"><span>ООО "СБЕРБАНК-СЕРВИС"</span></a></td></tr>
      <tr class="c2"><td width="40%" class="fname">Адрес места поставки товара, проведения работ или оказания услуг:</td><td>392027, Россия, Тамбовская обл, г. Тамбов, ул. Чичерина, д. 62а</td></tr>
    </table>
    <div>Процедура находится в архиве</div>
    <div>Статус объявления: в архиве.</div>
  </body>
</html>
"""


MARKET_NEXT_HTML = """
<html>
  <body>
    <script>
      var __pinia = {
        TradePage: {
          tradeAggregateRaw: {
            trade: {
              date_published: "2024-06-13T17:11:40+03:00",
              firm: {
                full_name: "ОБЩЕСТВО С ОГРАНИЧЕННОЙ ОТВЕТСТВЕННОСТЬЮ \\"СБЕРБАНК-СЕРВИС\\"",
                short_name: "ООО \\"СБЕРБАНК-СЕРВИС\\"",
                inn: "7736663049",
                ogrn: "1137746703709",
                url: "https://www.b2b-center.ru/firms/ooo-sberbank-servis/284642/"
              },
              fields_values: {
                subject: { value: "Закупка ИТ оборудования" },
                okpd2: {
                  okpd2_category_list: [
                    { name: "Блоки, части и принадлежности вычислительных машин" }
                  ]
                },
                delivery_address: [
                  {
                    address: {
                      address_string: "Россия, г. Москва, 111024, ул. 2-я Кабельная, д. 2 стр. 19"
                    }
                  }
                ],
                offers_stage_date_end: { value: "2024-06-21T15:00:59+03:00" },
                main_price_type: { option: { name: { hint: { title: "без НДС" } } } },
                currency: { currency: { symbol: "RUB" } },
                hide_prices: { value: true }
              }
            },
            trade_result: {
              trade_result: { date_finished: "2024-06-24T11:10:35+03:00" },
              trade_result_money: {
                money_with_tax: 0,
                money_without_tax: 0,
                currency: { symbol: "RUB" },
                tax_percent: null,
                is_no_tax: true,
                is_different_tax: false,
                different_taxes_values: []
              }
            },
            positions_count: 11,
            trade_view_status: { value: "finished", name: { hint: { title: "Завершена" } } },
            trade_view_statuses_list: [
              { value: "accept-applications", name: { hint: { title: "Приём заявок" } } },
              { value: "consider", name: { hint: { title: "Рассмотрение" } } },
              { value: "finished", name: { hint: { title: "Завершена" } } }
            ]
          }
        }
      };
    </script>
  </body>
</html>
"""


MARKET_NEXT_PRICED_HTML = """
<html>
  <body>
    <script>
      var __pinia = {
        TradePage: {
          tradeAggregateRaw: {
            trade: {
              date_published: "2024-06-06T11:34:41+03:00",
              firm: {
                short_name: "ООО \\"СБЕРБАНК-СЕРВИС\\"",
                url: "https://www.b2b-center.ru/firms/ooo-sberbank-servis/284642/"
              },
              fields_values: {
                subject: { value: "Закупка ЗИП для принтеров" },
                okpd2: {
                  okpd2_category_list: [
                    { name: "Принтеры и комплектующие" }
                  ]
                },
                delivery_address: [
                  {
                    address: {
                      address_string: "Россия, г. Москва"
                    }
                  }
                ],
                offers_stage_date_end: { value: "2024-06-13T15:00:59+03:00" },
                main_price_type: { option: { name: { hint: { title: "без НДС" } } } },
                currency: { currency: { symbol: "RUB" } },
                hide_prices: { value: true }
              }
            },
            trade_result: {
              trade_result_money: {
                money_with_tax: 12397865,
                money_without_tax: 10331548,
                currency: { symbol: "RUB" },
                tax_percent: null,
                is_no_tax: true,
                is_different_tax: false,
                different_taxes_values: []
              }
            },
            positions_count: 16,
            trade_view_status: { value: "finished", name: { hint: { title: "Завершена" } } }
          }
        }
      };
    </script>
  </body>
</html>
"""


FORBIDDEN_HTML = """
<html>
  <body>
    <h1>Forbidden</h1>
    <p>If you are not a bot, please copy the report and send it to our support team.</p>
  </body>
</html>
"""


class B2BCenterClientTest(unittest.TestCase):
    def test_parse_organization_candidates(self) -> None:
        candidates = b2b_center.parse_organization_candidates(
            ORG_PAYLOAD,
            query="Сбербанк-Сервис",
            search_action="SearchOrganizer",
        )
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].role_mode, "organizer")
        self.assertEqual(candidates[0].organization_id, "284642")
        self.assertEqual(candidates[0].inn, "7736663049")

    def test_build_market_search_params(self) -> None:
        params = b2b_center.build_market_search_params(
            organization_id="284642",
            role_mode="organizer",
            show="archive",
            date_kind="1",
            date_start="01.04.2025",
            date_end="30.04.2025",
        )
        self.assertEqual(params["firm_id"], "284642")
        self.assertEqual(params["show"], "archive")
        self.assertEqual(params["date_start_dmy"], "01.04.2025")
        self.assertEqual(params["date_end_dmy"], "30.04.2025")

    def test_parse_status_counts_and_search_items(self) -> None:
        counts = b2b_center.parse_status_counts(SEARCH_HTML)
        self.assertEqual(counts, {"actual": 0, "archive": 178, "all": 178})
        self.assertTrue(b2b_center.search_has_pager(SEARCH_HTML))

        items = b2b_center.parse_search_items(
            SEARCH_HTML,
            entity_name='ООО "СБЕРБАНК-СЕРВИС"',
            customer_query="7736663049",
            role_mode="organizer",
            show="all",
            organization_name='ООО "СБЕРБАНК-СЕРВИС"',
            organization_inn="7736663049",
        )
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item.procedure_number, "4225153")
        self.assertEqual(item.platform_section, "Вода питьевая")
        self.assertEqual(item.method_name, "Запрос цен")
        self.assertEqual(item.organizer_name, 'ООО "СБЕРБАНК-СЕРВИС"')
        self.assertEqual(item.organizer_inn, "7736663049")
        self.assertEqual(item.published_at, "2025-11-05T09:48:00")
        self.assertEqual(item.application_deadline, "2025-11-11T12:00:00")

    def test_parse_procedure_detail(self) -> None:
        detail = b2b_center.parse_procedure_detail(
            DETAIL_HTML,
            detail_url="https://www.b2b-center.ru/market/tekhnicheskoe-obsluzhivaniiu-i-remont-purifaiera-ecotronic-m30-u4le/tender-4225153/",
        )
        self.assertEqual(detail.category, "Вода питьевая")
        self.assertEqual(detail.quantity_text, "4 усл.ед.")
        self.assertEqual(detail.total_price_text, "Без указания цены")
        self.assertIsNone(detail.total_price_rub)
        self.assertEqual(detail.currency, "руб.")
        self.assertEqual(detail.organizer_name, 'ООО "СБЕРБАНК-СЕРВИС"')
        self.assertEqual(detail.procedure_status, "archive")
        self.assertEqual(detail.price_note, "without_price")
        self.assertEqual(detail.published_at, "2025-11-05T09:48:00")
        self.assertEqual(detail.deadline_at, "2025-11-11T12:00:00")

    def test_parse_market_next_detail_without_price(self) -> None:
        detail = b2b_center.parse_procedure_detail(
            MARKET_NEXT_HTML,
            detail_url="https://www.b2b-center.ru/app/market-next/zakupka-it-oborudovaniia/tender-3699172/",
        )
        self.assertEqual(detail.subject, "Закупка ИТ оборудования")
        self.assertEqual(detail.category, "Блоки, части и принадлежности вычислительных машин")
        self.assertEqual(detail.quantity_text, "11")
        self.assertEqual(detail.total_price_text, "Не указана")
        self.assertIsNone(detail.total_price_rub)
        self.assertEqual(detail.currency, "RUB")
        self.assertEqual(detail.organizer_name, 'ООО "СБЕРБАНК-СЕРВИС"')
        self.assertEqual(detail.organizer_profile_url, "https://www.b2b-center.ru/firms/ooo-sberbank-servis/284642/")
        self.assertEqual(detail.procedure_status, "archive")
        self.assertEqual(detail.price_note, "without_price")
        self.assertEqual(detail.location, "Россия, г. Москва, 111024, ул. 2-я Кабельная, д. 2 стр. 19")

    def test_parse_market_next_detail_with_price(self) -> None:
        detail = b2b_center.parse_procedure_detail(
            MARKET_NEXT_PRICED_HTML,
            detail_url="https://www.b2b-center.ru/app/market-next/zakupka-zip-dlia-printerov/tender-3688284/",
        )
        self.assertEqual(detail.quantity_text, "16")
        self.assertEqual(detail.total_price_text, "10331548 RUB без НДС")
        self.assertEqual(detail.total_price_rub, 10331548.0)
        self.assertEqual(detail.price_note, "")

    def test_parse_procedure_detail_raises_on_forbidden_page(self) -> None:
        self.assertTrue(b2b_center.is_forbidden_page(FORBIDDEN_HTML))
        with self.assertRaisesRegex(ValueError, "anti-bot"):
            b2b_center.parse_procedure_detail(
                FORBIDDEN_HTML,
                detail_url="https://www.b2b-center.ru/market/example/tender-1/",
            )


if __name__ == "__main__":
    unittest.main()
