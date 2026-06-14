import unittest

from purchase_analysis.clients.sberbank_ast import (
    SberbankAstCustomerCandidate,
    SberbankAstSearchItem,
    build_request_xml,
    is_procurement_relevant,
    parse_search_items,
    parse_total,
    select_best_candidates,
)


REGISTRY_HTML = """
<div id="xmlContainer">
  <div content="node:elasticrequest">
    <div content="node:filters">
      <div content="node:PublicDate">
        <input content="leaf:minvalue" value="" />
        <input content="leaf:maxvalue" value="" />
      </div>
      <div content="node:CustomerDictionary">
        <span content="leaf:value"></span>
      </div>
      <div content="node:customer">
        <div content="leaf:visiblepart"></div>
      </div>
    </div>
    <div content="node:fields">
      <div content="leaf:field">purchCode</div>
      <div content="leaf:field">purchName</div>
    </div>
    <div content="node:sort">
      <input content="leaf:value" value="default" />
      <input content="leaf:direction" value="" />
    </div>
    <div content="node:aggregations">
      <span content="node:empty">
        <input content="leaf:filterType" value="filter_aggregation" />
        <input content="leaf:field" value="" />
        <input content="leaf:min_doc_count" value="0" />
        <input content="leaf:order" value="asc" />
      </span>
    </div>
    <div>
      <input content="leaf:size" id="PageSize" value="20" />
      <input content="leaf:from" id="CurrPage" value="0" />
    </div>
  </div>
</div>
"""


TABLE_XML = """
<datarow>
  <total>
    <value>2</value>
    <relation>eq</relation>
  </total>
  <hits>
    <_source>
      <PurchaseTypeName>Запрос предложений</PurchaseTypeName>
      <purchStateName>Подача заявок</purchStateName>
      <BidName>Запрос №1</BidName>
      <purchCode>79442871</purchCode>
      <objectHrefTerm>https://example.test/request/79442871</objectHrefTerm>
      <OrgName>АО "СБЕРБАНК ЛИЗИНГ"</OrgName>
      <purchName>Поставка воды</purchName>
      <SourceTerm>SberB2B</SourceTerm>
      <IsSMP>1</IsSMP>
      <purchCurrency>RUB</purchCurrency>
      <PublicDate>19.12.2025 07:56</PublicDate>
      <RequestDate>25.12.2025 12:00</RequestDate>
      <purchAmount>15 000,00</purchAmount>
    </_source>
  </hits>
</datarow>
"""


def make_item(subject: str, platform_section: str = "Торги коммерческих заказчиков") -> SberbankAstSearchItem:
    return SberbankAstSearchItem(
        source_system="sberbank_ast",
        platform_section=platform_section,
        entity_name="ПАО Сбербанк России",
        customer_query="ПАО Сбербанк России",
        procedure_number="SBR028-TEST",
        lot_number="1",
        subject=subject,
        customer_name="ПАО Сбербанк России",
        region="",
        status="Завершена",
        tender_type="Запрос предложений",
        price_rub=100000.0,
        deadline_at=None,
        detail_url="https://utp.sberbank-ast.ru/VIP/NBT/PurchaseView/18/0/0/1",
        tags=platform_section,
        published_at=None,
        application_deadline=None,
        method_name="Запрос предложений",
        currency="RUB",
    )


class SberbankAstClientTest(unittest.TestCase):
    def test_build_request_xml(self) -> None:
        candidate = SberbankAstCustomerCandidate(
            query="Сбербанк Лизинг",
            bu_inn="7707009586",
            bu_kpp="503201001",
            bu_inn_kpp="7707009586_503201001",
            full_name='АКЦИОНЕРНОЕ ОБЩЕСТВО "СБЕРБАНК ЛИЗИНГ"',
        )
        xml_text = build_request_xml(
            registry_html=REGISTRY_HTML,
            customer=candidate,
            date_from="01.01.2024",
            date_to="31.12.2025",
            offset=40,
            page_size=100,
        )
        self.assertIn("<from>40</from>", xml_text)
        self.assertIn("<size>100</size>", xml_text)
        self.assertIn("<value>7707009586_503201001</value>", xml_text)
        self.assertIn("СБЕРБАНК ЛИЗИНГ", xml_text)
        self.assertIn("31.12.2025 23:59", xml_text)

    def test_parse_search_items(self) -> None:
        items = parse_search_items(
            TABLE_XML,
            entity_name="АО Сбербанк Лизинг",
            customer_query='АКЦИОНЕРНОЕ ОБЩЕСТВО "СБЕРБАНК ЛИЗИНГ"',
        )
        self.assertEqual(parse_total(TABLE_XML), 2)
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item.procedure_number, "79442871")
        self.assertEqual(item.subject, "Поставка воды")
        self.assertEqual(item.customer_name, 'АО "СБЕРБАНК ЛИЗИНГ"')
        self.assertEqual(item.platform_section, "SberB2B")
        self.assertAlmostEqual(item.price_rub or 0, 15000.0)
        self.assertTrue(is_procurement_relevant(item))

    def test_select_best_candidates_prefers_exact_inn(self) -> None:
        candidates = [
            SberbankAstCustomerCandidate(
                query="foo",
                bu_inn="1",
                bu_kpp="1",
                bu_inn_kpp="1_1",
                full_name="ООО ДРУГАЯ КОМПАНИЯ",
            ),
            SberbankAstCustomerCandidate(
                query="foo",
                bu_inn="7707009586",
                bu_kpp="503201001",
                bu_inn_kpp="7707009586_503201001",
                full_name='АКЦИОНЕРНОЕ ОБЩЕСТВО "СБЕРБАНК ЛИЗИНГ"',
            ),
        ]
        selected = select_best_candidates(
            candidates,
            expected_name="АО Сбербанк Лизинг",
            inn="7707009586",
        )
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0].bu_inn, "7707009586")

    def test_filter_excludes_property_sales(self) -> None:
        item = parse_search_items(
            """
            <datarow>
              <total><value>1</value></total>
              <hits>
                <_source>
                  <PurchaseTypeName>Английский аукцион</PurchaseTypeName>
                  <purchStateName>Подача заявок</purchStateName>
                  <purchCode>SBR001</purchCode>
                  <purchName>Продажа имущества</purchName>
                  <OrgName>ПАО Сбербанк</OrgName>
                  <SourceTerm>Реализация имущества</SourceTerm>
                  <objectHrefTerm>https://utp.sberbank-ast.ru/Property/NBT/PurchaseView/43/0/0/1</objectHrefTerm>
                </_source>
              </hits>
            </datarow>
            """,
            entity_name="ПАО Сбербанк России",
            customer_query="ПАО Сбербанк России",
        )[0]
        self.assertFalse(is_procurement_relevant(item))

    def test_filter_excludes_vip_asset_sales_by_subject(self) -> None:
        item = make_item("Процедура продажи б.у. ИТ оборудования")
        self.assertFalse(is_procurement_relevant(item))

    def test_filter_keeps_procurements_with_false_positive_words(self) -> None:
        kept_subjects = [
            "Поставка канализационной насосной установки Sololift (с измельчителем отходов)",
            "Оказание услуг по организации розыгрыша, трансляции и реализации тура",
            "Выполнение работ по предпродажной подготовке, техническому обслуживанию и ремонту автомобилей",
        ]
        for subject in kept_subjects:
            with self.subTest(subject=subject):
                self.assertTrue(is_procurement_relevant(make_item(subject)))


if __name__ == "__main__":
    unittest.main()
