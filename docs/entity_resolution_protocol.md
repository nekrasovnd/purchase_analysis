# Entity Resolution Protocol

Дата обновления: 2026-06-14.

## Зачем

Парсинг источников больше не должен начинаться с одного поля `ИНН` или одного бренда. Сначала есть проверенная карточка юрлица в `configs/entity_scope.csv`, потом каждый source sprint строит набор поисковых ключей, а результаты проходят общий фильтр идентичности.

Цель: искать шире, но принимать в core строже.

## Карточка юрлица

`configs/entity_scope.csv` теперь хранит:

- `entity_key` - стабильный внутренний идентификатор.
- `inn` - основной ИНН.
- `ogrn` - только если подтвержден локальными evidence.
- `kpp_list` - подтвержденные КПП из EIS/AST evidence.
- `official_name`, `short_name`, `brand_aliases`, `search_terms` - имена и алиасы для поиска.
- `eis_search_term`, `roseltorg_customer_query` - обратная совместимость со старыми клиентами.
- `identity_source`, `identity_confidence`, `notes` - почему данным можно доверять.

Пустые поля не считаются ошибкой, если нет проверенного evidence. Нельзя заполнять ОГРН/КПП из памяти или случайной выдачи.

## Поиск

Кодовый слой: `src/purchase_analysis/entity_resolution.py`.

Каждый источник должен получать запросы через:

```python
build_search_terms(entity, source_system="<source>")
```

Разрешенные поисковые ключи:

- ИНН;
- ОГРН;
- КПП, если источник поддерживает поиск по КПП;
- официальное название;
- короткое название;
- безопасные алиасы бренда;
- source-specific query fields.

## Принятие в core

Результат источника должен пройти:

```python
classify_entity_match(...)
```

Автоматический `accept`:

- совпал `candidate_inn == entity.inn`;
- совпал `candidate_ogrn == entity.ogrn`;
- совпал `candidate_kpp` и одновременно точное официальное имя;
- роль явно не является `supplier`, `operator`, `platform`, `title_mention`, `text_mention`.

`review`, а не core:

- совпало только название без ИНН/ОГРН/КПП;
- найден бренд в заголовке или тексте закупки;
- источник возвращает неструктурированное совпадение.

`reject`:

- совпадение только по оператору площадки;
- совпадение по поставщику/продавцу вместо заказчика/организатора;
- нет точной идентичности юрлица;
- период не 2024-2025.

## Дозаполнение пустых полей

Да, пустые поля можно заполнять во время парсинга, но не напрямую в `entity_scope.csv`.

Правило:

1. Источник нашел новый ОГРН/КПП/официальное имя.
2. Сначала пишем proposed value в review/enrichment artifact с evidence.
3. Если совпадение подтверждено точным ИНН/ОГРН или ручной проверкой, переносим в `entity_scope.csv`.
4. Если evidence слабый, оставляем в review и не используем как core-фильтр.

Для этого в коде есть helper `enrichment_row(...)`; source sprint должен писать такие строки в отчет источника, например `output/source_sprints/<source>/identity_enrichment_candidates.csv`.

## Следующий source sprint

Перед разбором нового источника:

1. Загрузи scope через `load_entity_scope`.
2. Для каждого юрлица построй `build_search_terms`.
3. Сохрани raw evidence.
4. Прогони кандидатов через `classify_entity_match`.
5. Раздели accepted / duplicate / review / rejected.
6. Если появились новые идентификаторы, положи их в enrichment candidates, не в core напрямую.
