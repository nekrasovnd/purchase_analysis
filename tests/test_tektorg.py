import unittest

from purchase_analysis.clients.tektorg import (
    build_request_xml,
    parse_fault,
    parse_search_response,
    parse_total,
)


FAULT_XML = """<?xml version="1.0" encoding="UTF-8"?>
<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
  <SOAP-ENV:Body>
    <SOAP-ENV:Fault>
      <faultcode>SOAP-ENV:Client</faultcode>
      <faultstring>Customers not found by INN.</faultstring>
    </SOAP-ENV:Fault>
  </SOAP-ENV:Body>
</SOAP-ENV:Envelope>
"""


SUCCESS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/"
                   xmlns:SOAP-ENC="http://schemas.xmlsoap.org/soap/encoding/"
                   SOAP-ENV:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
  <SOAP-ENV:Body>
    <SOAP-ENV:proceduresResponse>
      <totalProcedures>1</totalProcedures>
      <currentPage>1</currentPage>
      <totalPage>1</totalPage>
      <limitProceduresInPage>5</limitProceduresInPage>
      <sectionName>Государственные закупки</sectionName>
      <sectionCode>44fz</sectionCode>
      <procedures>
        <procedure id="857955">
          <remoteId>857955</remoteId>
          <url_to_showcase>https://www.tektorg.ru/44-fz/procedures/19204112</url_to_showcase>
          <registryNumber>0318300194126000208</registryNumber>
          <title>Оказание услуг по организации и обеспечению лечебным питанием</title>
          <datePublished>2026-06-14T20:29:34+03:00</datePublished>
          <dateEndRegistration>2026-06-19T09:00:00+03:00</dateEndRegistration>
          <procedureType>
            <id>2</id>
            <title>Запрос котировок в электронной форме</title>
          </procedureType>
          <currency>RUB</currency>
          <organizer>
            <id>85549</id>
            <fullName><![CDATA[ГОСУДАРСТВЕННОЕ БЮДЖЕТНОЕ УЧРЕЖДЕНИЕ ЗДРАВООХРАНЕНИЯ "КАВКАЗСКАЯ ЦЕНТРАЛЬНАЯ РАЙОННАЯ БОЛЬНИЦА"]]></fullName>
            <inn>2332001562</inn>
            <legal>
              <region>Краснодарский край</region>
            </legal>
          </organizer>
          <lots>
            <lot id="22371236">
              <remoteId>857954</remoteId>
              <number>1</number>
              <subject>Оказание услуг по организации и обеспечению лечебным питанием</subject>
              <startPrice>599999</startPrice>
              <status>Приём заявок</status>
              <customers>
                <customer>
                  <id>-85549</id>
                  <fullName><![CDATA[ГОСУДАРСТВЕННОЕ БЮДЖЕТНОЕ УЧРЕЖДЕНИЕ ЗДРАВООХРАНЕНИЯ "КАВКАЗСКАЯ ЦЕНТРАЛЬНАЯ РАЙОННАЯ БОЛЬНИЦА"]]></fullName>
                  <inn>2332001562</inn>
                </customer>
              </customers>
            </lot>
          </lots>
        </procedure>
      </procedures>
    </SOAP-ENV:proceduresResponse>
  </SOAP-ENV:Body>
</SOAP-ENV:Envelope>
"""


class TektorgClientTest(unittest.TestCase):
    def test_build_request_xml(self) -> None:
        xml_text = build_request_xml(
            customer_inn="7707083893",
            start_date="2024-01-01T00:00:00+05:00",
            end_date="2025-12-31T23:59:59+05:00",
            page=2,
            limit_page=50,
        )
        self.assertIn("<customerINN", xml_text)
        self.assertIn("7707083893", xml_text)
        self.assertIn("2024-01-01T00:00:00+05:00", xml_text)
        self.assertIn("<page xsi:type=\"xsd:int\">2</page>", xml_text)
        self.assertIn("<limitPage xsi:type=\"xsd:int\">50</limitPage>", xml_text)

    def test_parse_fault(self) -> None:
        self.assertEqual(parse_fault(FAULT_XML), "Customers not found by INN.")

    def test_parse_search_response(self) -> None:
        response = parse_search_response(
            SUCCESS_XML,
            entity_name="ПАО Сбербанк России",
            customer_query="7707083893",
        )
        self.assertEqual(parse_total(SUCCESS_XML), 1)
        self.assertEqual(response.total_procedures, 1)
        self.assertEqual(response.total_pages, 1)
        self.assertEqual(len(response.items), 1)
        item = response.items[0]
        self.assertEqual(item.procedure_number, "0318300194126000208")
        self.assertEqual(item.lot_number, "1")
        self.assertEqual(item.customer_inn, "2332001562")
        self.assertEqual(item.organizer_inn, "2332001562")
        self.assertEqual(item.region, "Краснодарский край")
        self.assertAlmostEqual(item.price_rub or 0, 599999.0)
        self.assertEqual(item.method_name, "Запрос котировок в электронной форме")
        self.assertEqual(item.platform_section, "Государственные закупки")


if __name__ == "__main__":
    unittest.main()
