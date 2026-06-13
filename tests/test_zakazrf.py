import unittest

from purchase_analysis.clients.zakazrf import (
    filter_exact_customer_candidates,
    parse_customer_candidates,
    parse_customer_dialog_context,
    parse_main_page_id,
    parse_notification_rows,
    parse_total_rows,
)


MAIN_HTML = """
<form id="form91182E96173849BB" action="javascript:;">
  <input type="hidden" name="_orm_PageID" value="91182E96173849BB" />
</form>
"""


DIALOG_HTML = """
<form id="form745FAE9C9FB43A73" action="javascript:;">
  <input type="hidden" name="_orm_PageID" value="745FAE9C9FB43A73" />
  <input type="hidden" name="PageSize745FAE9C9FB43A73" value="20" />
  <input type="hidden" name="_orm_SerializableTable" value="ABC;DEF;" />
  <input type="hidden" name="_orm_SerializableTableKey" value="HASH" />
</form>
"""


CUSTOMER_RESULTS_HTML = """
<div id="DivTableList745FAE9C9FB43A73">
  <table id="TableList745FAE9C9FB43A73" class="reporttable">
    <tr class="orm-grid-table-header">
      <th>Полное наименование</th><th>ИНН</th><th>Роль организации на сайте</th><th>Дата регистрации</th><th>Адрес</th>
    </tr>
    <tr>
      <td class="act311353">ОАО "Сбербанка России" Октябрьское отделение № 4676</td>
      <td class="act311353">7707083893</td>
      <td class="act311353">Заказчик</td>
      <td class="act311353">04.10.2010</td>
      <td class="act311353">Татарстан</td>
    </tr>
    <tr>
      <td class="act311354">ПУБЛИЧНОЕ АКЦИОНЕРНОЕ ОБЩЕСТВО "СБЕРБАНК РОССИИ"</td>
      <td class="act311354">7707083893</td>
      <td class="act311354">Банк</td>
      <td class="act311354">14.03.2014</td>
      <td class="act311354">Москва</td>
    </tr>
  </table>
  <script type="text/javascript">
    function SelectRow1_745FAE9C9FB43A73(){ $('#form91182E96173849BB').find('#Filter_Customer').val(aposDecode('2384')); $('#form91182E96173849BB').find('#Filter_Customer_editView').val(aposDecode('ОАО "Сбербанка России" Октябрьское отделение № 4676')); }
    function SelectRow2_745FAE9C9FB43A73(){ $('#form91182E96173849BB').find('#Filter_Customer').val(aposDecode('465053')); $('#form91182E96173849BB').find('#Filter_Customer_editView').val(aposDecode('ПУБЛИЧНОЕ АКЦИОНЕРНОЕ ОБЩЕСТВО "СБЕРБАНК РОССИИ"')); }
  </script>
</div>
"""


NOTIFICATION_RESULTS_HTML = """
<input type="hidden" name="TotalRows91182E96173849BB" value="2" />
<table id="TableList91182E96173849BB" class="reporttable">
  <tr class="orm-grid-table-header">
    <th>ФЗ</th><th>Номер закупки</th><th>Состояние закупки</th><th>Способ закупки</th><th>Предмет закупки</th><th>Начальная цена</th><th>Организатор</th><th>Заказчик</th><th>Контактное лицо</th><th>Дата размещения*</th><th>Дата изменения</th><th>Дата и время окончания срока подачи заявок</th><th>Дата окончания рассмотрения заявок</th><th>Дата и время подачи ценовых предложений</th><th>Дата подведения итогов</th>
  </tr>
  <tr>
    <td>223-ФЗ</td>
    <td class="IgnoreRowAction RowActionRaw"><a href="/NotificationEx/id/2042796" target="_blank">32616109797</a></td>
    <td>Идет подача заявок</td>
    <td>Извещение Иное</td>
    <td>Бумага для офисной техники А4</td>
    <td>8 150,00</td>
    <td>ООО "ТЕТЮШСКОЕ"</td>
    <td>ООО "ТЕТЮШСКОЕ"</td>
    <td>Ахметов Рифкат Талгатович</td>
    <td>11.06.2026</td>
    <td>11.06.2026</td>
    <td>22.06.2026 13:45 (+03:00)</td>
    <td></td>
    <td></td>
    <td>22.06.2026</td>
  </tr>
</table>
"""


class ZakazRfClientTest(unittest.TestCase):
    def test_parse_main_page_id(self) -> None:
        self.assertEqual(parse_main_page_id(MAIN_HTML), "91182E96173849BB")

    def test_parse_customer_dialog_context(self) -> None:
        context = parse_customer_dialog_context(
            DIALOG_HTML,
            main_page_id="91182E96173849BB",
            dialog_url="https://etp.zakazrf.ru/Customer",
        )
        self.assertEqual(context.dialog_page_id, "745FAE9C9FB43A73")
        self.assertEqual(context.page_size, 20)
        self.assertEqual(context.serializable_table_key, "HASH")

    def test_parse_customer_candidates(self) -> None:
        candidates = parse_customer_candidates(CUSTOMER_RESULTS_HTML)
        self.assertEqual(len(candidates), 2)
        self.assertEqual(candidates[0].internal_id, "2384")
        self.assertEqual(candidates[0].role_name, "Заказчик")
        self.assertEqual(candidates[1].internal_id, "465053")
        self.assertEqual(candidates[1].full_name, 'ПУБЛИЧНОЕ АКЦИОНЕРНОЕ ОБЩЕСТВО "СБЕРБАНК РОССИИ"')

    def test_filter_exact_customer_candidates_by_inn(self) -> None:
        candidates = parse_customer_candidates(CUSTOMER_RESULTS_HTML)
        exact = filter_exact_customer_candidates(candidates, "7707083893")
        self.assertEqual(len(exact), 2)
        self.assertEqual(filter_exact_customer_candidates(candidates, ""), [])
        self.assertEqual(filter_exact_customer_candidates(candidates, "0000000000"), [])

    def test_parse_notification_rows(self) -> None:
        self.assertEqual(parse_total_rows(NOTIFICATION_RESULTS_HTML), 2)
        items = parse_notification_rows(
            NOTIFICATION_RESULTS_HTML,
            entity_name="ПАО Сбербанк России",
            customer_query="7707083893",
        )
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item.platform_section, "223-ФЗ")
        self.assertEqual(item.procedure_number, "32616109797")
        self.assertEqual(item.subject, "Бумага для офисной техники А4")
        self.assertEqual(item.method_name, "Извещение Иное")
        self.assertAlmostEqual(item.price_rub or 0, 8150.0)
        self.assertTrue(item.detail_url.endswith("/NotificationEx/id/2042796"))


if __name__ == "__main__":
    unittest.main()
