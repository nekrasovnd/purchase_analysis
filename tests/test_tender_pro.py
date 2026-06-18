from pathlib import Path
import unittest

from purchase_analysis.clients.tender_pro import (
    TenderProCompanyProfile,
    build_paged_url,
    parse_company_candidates,
    parse_company_profile,
    parse_purchase_items,
    parse_purchase_pages,
)


ROOT_DIR = Path(__file__).resolve().parents[1]


SEARCH_HTML = """
<div class="content__company-list">
  <div class="company-card">
    <div class="company-card__description">
      <div class="company-card__name">
        <a class="text-d-none _black" href="/api/company/338232/view?sid=">
          Инстамарт Сервис (Москва)
        </a>
      </div>
      <div class="company-card__roles">
        <div class="company-card__role">Покупатель</div>
        <div class="company-card__role">Продавец</div>
      </div>
    </div>
  </div>
</div>
"""


COMPANY_HTML = """
<div class="card-company">
  <div class="page-header _wide pt-16">
    <div class="page-header__box">
      <h1 class="page-header__title">Закупки Инстамарт Сервис</h1>
    </div>
    <div class="page-header__subtitle mt-12">ИНН/КПП 9705118142/770501001</div>
    <div class="page-header__subtitle mt-12">Онлайн сервис доставки продуктов</div>
    <div class="page-header__stat">
      <div class="badge-box _level-2">
        <div class="badge"><img alt="Покупатель" title="Покупатель"/></div>
        <div class="badge"><img alt="Продавец" title="Продавец"/></div>
      </div>
    </div>
    <div class="page-header__stat">
      <a class="statistics" href="/api/company/338232/stat?sid=">Статистика</a>
    </div>
  </div>
  <div class="page-body">
    <div class="tabs__item" data-id="purchases">
      <div class="content">
        <div class="content__body">
          <ul class="tender-list">
            <li class="tender-list__item _bd-1">
              <div class="card-v2">
                <div class="card-v2__top-line">
                  <a class="company-name" href="/api/company/338232/view?sid=" rel="nofollow">Инстамарт Сервис</a>
                  <div class="t-status is-closed _color">Закрыт</div>
                </div>
                <a class="tender-name _big mb-8" href="/api/tender/845030/view_public" rel="nofollow">
                  Запрос предложений на поставку мусорных контейнеров для нужд ООО «СберЛогистика» (2 тур) (id845030)
                </a>
                <div class="c-gray mb-12 _text-first-letter-up">закрытый тендер на закупку</div>
                <div class="card-v2__bottom-line">
                  <div class="date-block">
                    <div class="t-time"><span class="c-gray _width">Создан:</span><span class="c-text">15.01.2024</span></div>
                    <div class="t-time"><span class="c-gray _width">Завершится:</span><span class="c-text">17.01.2024 в 15:00</span></div>
                  </div>
                  <div class="id-block">
                    <div class="tender-id"><span class="c-gray _width">ID компании:</span>338232</div>
                    <div class="tender-id"><span class="c-gray _width">ID конкурса:</span>845030</div>
                  </div>
                </div>
              </div>
            </li>
          </ul>
          <ul class="pagination">
            <li class="pagination__item"><a class="pagination__link" href="/api/company/338232/view?active_tab=purchases&amp;order=3&amp;page=1">1</a></li>
            <li class="pagination__item"><a class="pagination__link" href="/api/company/338232/view?active_tab=purchases&amp;order=3&amp;page=2">2</a></li>
            <li class="pagination__item"><a class="pagination__link" href="/api/company/338232/view?active_tab=purchases&amp;order=3&amp;page=3">3</a></li>
          </ul>
        </div>
      </div>
    </div>
    <div class="tabs__item" data-id="about">
      <div class="flex-table">
        <div class="flex-table__row">
          <div class="flex-table__col-right">
            <div class="table">
              <div class="table__row"><div class="table__header">ID</div><div class="table__col">338232</div></div>
              <div class="table__row"><div class="table__header">Полное название</div><div class="table__col">Общество с ограниченной ответственностью Инстамарт Сервис</div></div>
              <div class="table__row"><div class="table__header">Краткое название</div><div class="table__col">Инстамарт Сервис</div></div>
              <div class="table__row"><div class="table__header">Адрес</div><div class="table__col">115035, г. Москва, Садовническая набережная</div></div>
              <div class="table__row"><div class="table__header">Юридический адрес</div><div class="table__col">142111, г. Москва, Щербинка</div></div>
              <div class="table__row"><div class="table__header">Сайт</div><div class="table__col">http://www.kuper.ru</div></div>
              <div class="table__row"><div class="table__header">ИНН/КПП</div><div class="table__col">9705118142/770501001</div></div>
              <div class="table__row"><div class="table__header">ОКВЭД</div><div class="table__col">63.11</div></div>
              <div class="table__row"><div class="table__header">ОГРН</div><div class="table__col">1187746494980</div></div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</div>
"""


class TenderProClientTest(unittest.TestCase):
    def test_parse_company_candidates(self) -> None:
        candidates = parse_company_candidates(SEARCH_HTML)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].company_id, "338232")
        self.assertEqual(candidates[0].display_name, "Инстамарт Сервис (Москва)")
        self.assertEqual(candidates[0].roles, "Покупатель | Продавец")

    def test_parse_company_profile(self) -> None:
        profile = parse_company_profile(
            COMPANY_HTML,
            url="https://www.tender.pro/api/company/338232/view?active_tab=purchases",
        )
        self.assertEqual(profile.company_id, "338232")
        self.assertEqual(profile.full_name, "Общество с ограниченной ответственностью Инстамарт Сервис")
        self.assertEqual(profile.short_name, "Инстамарт Сервис")
        self.assertEqual(profile.inn, "9705118142")
        self.assertEqual(profile.kpp, "770501001")
        self.assertEqual(profile.ogrn, "1187746494980")
        self.assertEqual(profile.roles, "Покупатель | Продавец")

    def test_parse_purchase_items_and_pages(self) -> None:
        profile = TenderProCompanyProfile(
            company_id="338232",
            company_url="https://www.tender.pro/api/company/338232/view?sid=",
            purchases_url="https://www.tender.pro/api/company/338232/view?active_tab=purchases",
            display_name="Инстамарт Сервис",
            full_name="Общество с ограниченной ответственностью Инстамарт Сервис",
            short_name="Инстамарт Сервис",
            inn="9705118142",
            kpp="770501001",
            ogrn="1187746494980",
            address="",
            legal_address="",
            site_url="",
            okved="",
            description="",
            roles="Покупатель | Продавец",
            region="Москва",
        )
        items = parse_purchase_items(COMPANY_HTML, entity_name="ООО Инстамарт Сервис", profile=profile)
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item.procedure_number, "845030")
        self.assertEqual(item.customer_inn, "9705118142")
        self.assertEqual(item.customer_kpp, "770501001")
        self.assertEqual(item.status, "Закрыт")
        self.assertEqual(item.tender_type, "закрытый тендер на закупку")
        self.assertEqual(item.published_at, "2024-01-15T00:00:00")
        self.assertEqual(item.application_deadline, "2024-01-17T15:00:00")

        pages = parse_purchase_pages(
            COMPANY_HTML,
            current_url="https://www.tender.pro/api/company/338232/view?active_tab=purchases",
        )
        self.assertEqual(pages, [1, 2, 3])
        self.assertEqual(
            build_paged_url(
                "https://www.tender.pro/api/company/338232/view?active_tab=purchases&order=3&page=2",
                page=5,
            ),
            "https://www.tender.pro/api/company/338232/view?active_tab=purchases&order=3&page=5",
        )


if __name__ == "__main__":
    unittest.main()
