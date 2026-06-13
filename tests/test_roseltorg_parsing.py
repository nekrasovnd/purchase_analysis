import unittest

from purchase_analysis.clients.roseltorg import parse_search_items


HTML_SNIPPET = """
<div class="search-results__item"
     data-feature-favorite-lots-lot-number="6"
     data-feature-favorite-lots-procedure-number="B2603251659113">
  <div class="search-results__subject">
    <a href="/procedure/B2603251659113/6"
       class="search-results__link search-results__link--description">Infinix ZERO 30</a>
  </div>
  <div class="search-results__section">
    <p>Росэлторг.Бизнес</p>
  </div>
  <div class="search-results__region">
    <p title="Регион заказчика">77. г. Москва</p>
  </div>
  <div class="search-results__customer">
    <p title="ОБЩЕСТВО С ОГРАНИЧЕННОЙ ОТВЕТСТВЕННОСТЬЮ &quot;СБЕРБАНК-ТЕЛЕКОМ&quot;">
      ООО "СБЕРБАНК-ТЕЛЕКОМ"
    </p>
  </div>
  <div class="search-results__status">
    <p>Прием заявок</p>
  </div>
  <div class="search-results__type">
    <p>Запрос цен</p>
  </div>
  <div class="search-results__sum">
    <p>33 990,00 ₽</p>
  </div>
  <div class="search-results__time">
    <p>До 31.03.2026 12:00</p>
  </div>
  <div class="search-results__tags">
    <div class="chip"><a>Смартфоны</a></div>
  </div>
</div>
"""


class RoseltorgParsingTest(unittest.TestCase):
    def test_parse_search_items(self) -> None:
        items = parse_search_items(
            HTML_SNIPPET,
            entity_name="ООО Сбербанк-Телеком",
            customer_query="СБЕРБАНК-ТЕЛЕКОМ",
        )
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item.procedure_number, "B2603251659113")
        self.assertEqual(item.lot_number, "6")
        self.assertEqual(item.subject, "Infinix ZERO 30")
        self.assertEqual(item.customer_name, 'ОБЩЕСТВО С ОГРАНИЧЕННОЙ ОТВЕТСТВЕННОСТЬЮ "СБЕРБАНК-ТЕЛЕКОМ"')
        self.assertEqual(item.platform_section, "Росэлторг.Бизнес")
        self.assertAlmostEqual(item.price_rub or 0, 33990.0)


if __name__ == "__main__":
    unittest.main()
