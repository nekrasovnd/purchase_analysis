# Entity Resolution Protocol

Актуальный протокол сопоставления юрлиц для source sprint парсеров.

## Цель

Искать шире, принимать в core строже. Любой источник может использовать ИНН, ОГРН, КПП, официальные названия, brand/search terms и JSON aliases для поиска, но строка попадает в clean dataset только после строгого match заказчика/организатора/покупателя.

## Scope

Основной файл: `configs/entity_scope.csv`.

Ключевые поля:

- `entity_key` - стабильный ключ юрлица.
- `inn` - основной ИНН, для текущего scope обязателен и уникален.
- `ogrn` - только подтвержденный ОГРН.
- `kpp_list` - `;`-разделенный список подтвержденных КПП.
- `official_name`, `short_name`, `brand_aliases`, `search_terms` - имена и поисковые термины.
- `aliases` - JSON-массив строк, только после review.
- `identity_source`, `identity_confidence`, `notes` - evidence и пояснения.

## Поиск

Source sprint должен загружать scope через `purchase_analysis.source_sprint.read_scope(...)` и строить запросы через:

```python
entity_resolution.build_search_terms(entity, source_system="<source>")
```

Разрешенные поисковые ключи:

- ИНН;
- ОГРН;
- КПП, если источник поддерживает поиск по КПП;
- официальное и короткое название;
- `brand_aliases`;
- `search_terms`;
- подтвержденные JSON `aliases`;
- source-specific query fields.

## Принятие в core

Результат источника должен пройти:

```python
entity_resolution.classify_entity_match(...)
```

Автоматический `accept`:

- совпал `candidate_inn == entity.inn`;
- совпал `candidate_ogrn == entity.ogrn`;
- совпал `candidate_kpp` и одновременно точное доверенное имя;
- роль безопасна: `customer`, `buyer`, `organizer`, `заказчик`, `покупатель`, `организатор`.

`review`, а не core:

- совпало только название без идентификатора;
- найден бренд в заголовке или тексте закупки;
- источник отдаёт неструктурированное совпадение.

`reject`:

- роль `supplier`, `seller`, `operator`, `platform`, `title_mention`, `text_mention`;
- Сбербанк-АСТ найден как оператор/площадка, а не как заказчик/организатор;
- нет точной идентичности юрлица;
- дата вне периода 2024-2025.

## Enrichment

Парсер может писать candidates в `output/source_sprints/<batch>/identity_enrichment_candidates.csv`, но не должен сам менять `configs/entity_scope.csv`.

`scripts/merge_aliases.py` - review helper:

- dry-run по умолчанию;
- пишет только JSON `aliases`;
- запись только с `--apply` после просмотра предложений;
- не используется как обязательный шаг pipeline.

## Output и dedupe

Source sprint пишет `items.csv` через `source_sprint.write_items_csv(...)`. Стандартный локальный dedupe: `procedure_number + lot_number`, fallback на `detail_url` только если нет procedure number.

Cross-source dedupe выполняет `scripts/merge_sprints.py`; default batch-и берутся из `configs/source_sprints_allowlist.csv`, полная карта batch-ов - `configs/source_sprints_manifest.csv`.
