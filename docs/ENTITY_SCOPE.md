# Entity Scope Policy

`configs/entity_scope.csv` - проверенный identity layer для группы Сбер и дочерних юрлиц. Сейчас в scope 32 entity.

## Назначение

Scope отвечает на два разных вопроса:

- чем искать на площадках;
- какие найденные организации можно принять в core как закупки Сбера.

Искать можно шире, принимать нужно строго.

## Обязательные поля

- `entity_key` - стабильный внутренний ключ.
- `entity_name` - человекочитаемое имя.
- `inn` - основной ИНН; для текущего scope должен быть заполнен и уникален.
- `ogrn` - только подтвержденный ОГРН.
- `kpp_list` - `;`-разделенный список подтвержденных КПП.
- `official_name`, `short_name` - нормальные имена для match/search.
- `brand_aliases`, `search_terms` - `;`-разделенные поисковые термины.
- `aliases` - JSON-массив строк. Не `;`, не Python-list, не свободный текст.
- `identity_source`, `identity_confidence`, `notes` - почему данным можно доверять.

## Aliases

`aliases` добавлены для совместимости и ручного review, но не должны превращаться в мусорный merge всех найденных названий.

Правила:

- формат строго JSON array, например `["ПАО Сбербанк", "Сбербанк"]`;
- новые aliases добавляются только после review;
- `scripts/merge_aliases.py` по умолчанию dry-run;
- обычный dry-run не использует `candidate_name` и должен давать 0 автоматических additions на текущих clean batch-ах;
- `candidate_name` можно рассматривать только вручную через `--include-candidate-name`;
- запись в `configs/entity_scope.csv` только через `scripts/merge_aliases.py --apply`, когда список просмотрен человеком/агентом;
- филиалы, отделения, посторонние организации и vendor/supplier имена не добавляются автоматически.

## Матчинг

Код: `src/purchase_analysis/entity_resolution.py`.

Автоматический `accept`:

- точный `candidate_inn == entity.inn`;
- точный `candidate_ogrn == entity.ogrn`;
- `candidate_kpp` входит в `kpp_list` и имя точно совпадает с доверенным именем;
- роль безопасна: customer/buyer/organizer/заказчик/покупатель/организатор.

`review`, а не core:

- совпало только имя;
- совпал бренд в заголовке или описании;
- источник возвращает неструктурированное совпадение.

`reject`:

- роль supplier/seller/operator/platform/title_mention/text_mention;
- Сбербанк-АСТ найден как оператор площадки, а не как заказчик/организатор;
- нет точного идентификатора;
- дата вне 2024-2025.

## Поиск

Source sprint должен строить запросы через:

```python
entity_resolution.build_search_terms(entity, source_system="<source>")
```

Функция использует ИНН, ОГРН, КПП, официальные имена, brand/search terms и JSON aliases. Это не значит, что все найденные строки идут в core: каждая строка должна пройти `classify_entity_match`.

## Проверка

```powershell
python -m pytest tests/test_entity_resolution.py -q
```
