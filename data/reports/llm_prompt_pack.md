# LLM Prompt Pack

Ниже собран компактный контекст для внешнего LLM-анализа закупок группы Сбер.
Использование:
1. Передайте этот файл в модель как контекст.
2. Попросите модель сформировать наблюдения, гипотезы и ограничения.
3. Не запрашивайте персональные данные и не скачивайте бинарные вложения без отдельного контура доступа.

## Quality Summary

```json
{
  "entities_total":9,
  "entities_with_observed_lots":8,
  "lots_total":927,
  "lots_duplicates_removed":2,
  "lots_with_disclosed_price":570,
  "price_coverage_ratio":0.6149,
  "items_total":927,
  "document_links_total":6,
  "macro_days_total":613,
  "source_breakdown":{
    "sberbank_ast":912,
    "roseltorg":15
  },
  "coverage_note":"EIS works as official coverage control; Roseltorg and Sberbank-AST supply the observed lot-level sample; ZakazRF and Lot-Online are reproduced as exact probe sources."
}
```

## Source Assessment

```csv
source_system,platform_name,platform_url,operational_status,inclusion_status,access_mode,rationale,coverage_note
rts_tender,РТС-Тендер,https://www.rts-tender.ru,blocked,researched_not_used,anti_ddos_block,Public homepage returns Anti-DDoS protection page from the execution environment.,External blocker; reproducible adapter was not feasible in this environment.
eis,ЕИС,https://zakupki.gov.ru,operational,used_in_pipeline,public_html,Official source for entity resolution and 223-FZ coverage control.,Used as authoritative customer registry and count-control layer.
lot_online,ЛотОнлайн,https://tender.lot-online.ru/etp/app/SearchLots/,operational,used_in_pipeline_probe_only,public_hidden_json_endpoint,Frontend searchServlet endpoint was reverse-engineered; exact customer/organizer filters are reproducible.,"Operational exact-probe adapter implemented; exact INN filters return zero Sber-scope hits, while broad title search is retained only in probe artifacts because precision is too weak for the core mart."
roseltorg,Росэлторг,https://www.roseltorg.ru,operational,used_in_pipeline,public_html,Public search and detail cards expose lot-level metadata and document links.,Used for directly observed lot cards and enrichment.
sberbank_ast,Сбербанк-АСТ,https://utp.sberbank-ast.ru/Main/List/UnitedPurchaseListNew,operational,used_in_pipeline,public_html_plus_public_json,Public long dictionary and search endpoint support reproducible customer resolution and paging.,Used for large 2024-2025 procurement samples on SberB2B / AST public registry.
zakazrf,ЗаказРФ,https://etp.zakazrf.ru/NotificationEx,operational,used_in_pipeline_probe_only,public_html_plus_hidden_form_post,Public customer selector and exact NotificationEx filtering were reproduced with pure HTTP.,"Operational exact-probe adapter implemented; Sber-scope customer matches currently return zero public notifications, so no ZakazRF rows enter the core lot mart in this run."
etpgpb,ЭТП ГПБ,https://etpgpb.ru/procedures/,research_only,researched_not_used,public_html_with_client_hydration,"Public procedures page is accessible, but plain HTTP queries do not reproduce filtered result sets.",Needs browser-side request discovery before safe adapter implementation.
tektorg,ТЭК-Торг,https://www.tektorg.ru/procedures,research_only,researched_not_used,public_html,"Search endpoint is public, but exact legal-entity precision is too weak for reliable group collection.","Useful as scout source, not yet robust enough as primary ingest."
```

## Yearly Summary

```csv
publication_year,lots_count,total_price_rub,median_price_rub,unique_regions,unique_categories,unique_sources
2024,99,367209259.58000004,2772000.0,1,7,1
2025,828,745086395.6700001,117500.0,2,8,2
```

## YoY Category Changes

```csv
publication_year,focus_category,lots_count,total_price_rub,prev_year_lots_count,prev_year_total_price_rub,lots_count_delta,lots_count_growth_ratio,total_price_delta_rub,total_price_growth_ratio
2024,Consulting,2,2399535.34,,,,,,
2025,Consulting,5,451850.0,2.0,2399535.34,3.0,2.5,-1947685.3399999999,0.18830729119413595
2025,Infrastructure,14,2473.67,,,,,,
2024,Logistics,1,,,,,,,
2025,Logistics,17,760866.0,1.0,,16.0,17.0,,
2024,Office & Admin,3,214795.24,,,,,,
2025,Office & Admin,47,4901564.08,3.0,214795.24,44.0,15.666666666666666,4686768.84,22.8197053156299
2024,Other,37,34083330.0,,,,,,
2025,Other,599,67697476.69,37.0,34083330.0,562.0,16.18918918918919,33614146.69,1.9862342291671617
2024,Security,1,2772000.0,,,,,,
2025,Security,1,,1.0,2772000.0,0.0,1.0,,
2024,Software & Cloud,9,,,,,,,
2025,Software & Cloud,16,3451175.0,9.0,,7.0,1.7777777777777777,,
2024,Telecom & Devices,46,327739599.0,,,,,,
2025,Telecom & Devices,129,667820990.23,46.0,327739599.0,83.0,2.8043478260869565,340081391.23,2.037657311681766
```

## Anomalies

```csv
entity_name,procedure_number,lot_number,subject,focus_category,price_rub,category_median_price,value_ratio_to_category_median,anomaly_type,anomaly_reason,detail_url
ООО Сбербанк-Телеком,SBR028-2509160031.1,1,"Поставка и внедрение Программного Комплекса, включающего функциональные модули: PCEF, DPI, TDF для нужд ООО Сбербанк-Телеком",Telecom & Devices,186025058.33,2600000.0,71.54809935769231,price_outlier,price >= 2x category median,https://utp.sberbank-ast.ru/VIP/NBT/PurchaseView/45/0/0/3413508
ООО Сбербанк-Телеком,SBR028-2410010034.1,1,Оказание комплекса услуг по проведению приемки-передачи предметов лизинга для нужд ООО «Сбербанк-Телеком»,Telecom & Devices,160489600.0,2600000.0,61.72676923076923,price_outlier,price >= 2x category median,https://utp.sberbank-ast.ru/VIP/NBT/PurchaseView/45/0/0/2348639
ООО Сбербанк-Телеком,SBR028-2508210056.1,1,Поставка аппаратного обеспечения для ООО Сбербанк-Телеком,Telecom & Devices,155097500.0,2600000.0,59.652884615384615,price_outlier,price >= 2x category median,https://utp.sberbank-ast.ru/VIP/NBT/PurchaseView/48/0/0/3350017
ООО Сбербанк-Телеком,SBR028-2411020013.1,1,Оказание комплекса услуг по проведению приемки-передачи предметов лизинга для нужд ООО «Сбербанк-Телеком»,Telecom & Devices,101000000.0,2600000.0,38.84615384615385,price_outlier,price >= 2x category median,https://utp.sberbank-ast.ru/VIP/NBT/PurchaseView/45/0/0/2444890
ООО Сбербанк-Телеком,SBR028-2510140031.1,1,Поставка и внедрение части компонентов нового биллингового решения BILRND (2-я часть компонентов) для ООО «СБЕРБАНК-ТЕЛЕКОМ»,Telecom & Devices,99999999.0,2600000.0,38.46153807692308,price_outlier,price >= 2x category median,https://utp.sberbank-ast.ru/VIP/NBT/PurchaseView/45/0/0/3485637
ООО Сбербанк-Телеком,SBR028-2510100053.1,1,Поставка сетевого оборудования (коммутаторы ЦОД) для ООО Сбербанк-Телеком,Telecom & Devices,56526412.96,2600000.0,21.74092806153846,price_outlier,price >= 2x category median,https://utp.sberbank-ast.ru/VIP/NBT/PurchaseView/48/0/0/3477662
ООО Сбербанк-Телеком,SBR028-2408190016.1,1,ОКАЗАНИЕ УСЛУГ ПРОВЕДЕНИЯ ИМИДЖЕВОЙ ФОТОСЕССИИ ДЛЯ НУЖД ООО «СБЕРБАНК-ТЕЛЕКОМ»,Telecom & Devices,49999999.0,2600000.0,19.230768846153847,price_outlier,price >= 2x category median,https://utp.sberbank-ast.ru/VIP/NBT/PurchaseView/45/0/0/2230349
ООО Сбербанк-Телеком,SBR028-2408290026.1,1,На услуги по ведению и продвижению официальных аккаунтов СберМобайл в социальных сетях,Other,20000000.0,100250.0,199.50124688279303,price_outlier,price >= 2x category median,https://utp.sberbank-ast.ru/VIP/NBT/PurchaseView/45/0/0/2259044
ООО Сбербанк-Телеком,SBR028-2410290075.1,1,"Оказание комплекса услуг по логистике, дистрибуции и рекламной поддержке сим-карт в сети Гипермаркетов «Лента для ООО «СБЕРБАНК-ТЕЛЕКОМ»",Telecom & Devices,10750000.0,2600000.0,4.134615384615385,price_outlier,price >= 2x category median,https://utp.sberbank-ast.ru/VIP/NBT/PurchaseView/45/0/0/2430091
ООО Сбербанк-Телеком,SBR028-2508270004.7,1,Оказание услуг по предоставлению во временное пользование канала передачи данных (GN) для нужд ООО «Сбербанк-Телеком»,Telecom & Devices,10464000.12,2600000.0,4.024615430769231,price_outlier,price >= 2x category median,https://utp.sberbank-ast.ru/VIP/NBT/PurchaseView/48/0/0/3361589
ООО Сбербанк-Телеком,SBR028-2508270004.8,1,Оказание услуг по предоставлению во временное пользование канала передачи данных (GN) для нужд ООО «Сбербанк-Телеком»,Telecom & Devices,10464000.12,2600000.0,4.024615430769231,price_outlier,price >= 2x category median,https://utp.sberbank-ast.ru/VIP/NBT/PurchaseView/48/0/0/3361589
ООО Сбербанк-Телеком,SBR028-2509190014.1,1,"Поставка Программного Комплекса Классификатора трафика с открытым исходным кодом и комплектом сигнатур, для нужд ООО Сбербанк-Телеком",Telecom & Devices,9800000.0,2600000.0,3.769230769230769,price_outlier,price >= 2x category median,https://utp.sberbank-ast.ru/VIP/NBT/PurchaseView/45/0/0/3421003
ООО Сбербанк-Телеком,SBR028-2507060001.1,1,Поставка серверного оборудования для нужд Сбербанк-Телеком,Telecom & Devices,9000000.0,2600000.0,3.4615384615384617,price_outlier,price >= 2x category median,https://utp.sberbank-ast.ru/VIP/NBT/PurchaseView/45/0/0/3232278
ООО Сбербанк-Телеком,SBR028-2409170027.1,1,Услуги технической поддержки серверов SPARC (3 года),Other,9000000.0,100250.0,89.77556109725685,price_outlier,price >= 2x category median,https://utp.sberbank-ast.ru/VIP/NBT/PurchaseView/45/0/0/2308544
ООО Сбербанк-Телеком,SBR028-2508270004.4,1,Оказание услуг по предоставлению во временное пользование канала передачи данных (GN) для нужд ООО «Сбербанк-Телеком»,Telecom & Devices,7776000.0,2600000.0,2.9907692307692306,price_outlier,price >= 2x category median,https://utp.sberbank-ast.ru/VIP/NBT/PurchaseView/48/0/0/3361589
ООО Сбербанк-Телеком,SBR028-2508270004.3,1,Оказание услуг по предоставлению во временное пользование канала передачи данных (GN) для нужд ООО «Сбербанк-Телеком»,Telecom & Devices,7416000.0,2600000.0,2.852307692307692,price_outlier,price >= 2x category median,https://utp.sberbank-ast.ru/VIP/NBT/PurchaseView/48/0/0/3361589
ООО Сбербанк-Телеком,SBR028-2511060040.1,1,"Поставка коммутаторов Brocade для ООО ""СБЕРБАНК-ТЕЛЕКОМ""",Telecom & Devices,7340423.0,2600000.0,2.8232396153846153,price_outlier,price >= 2x category median,https://utp.sberbank-ast.ru/VIP/NBT/PurchaseView/48/0/0/3545283
ООО Сбербанк-Телеком,SBR028-2508270026.29,1,Оказание услуг по предоставлению во временное пользование канала передачи данных (MPLS) для нужд ООО «Сбербанк-Телеком»,Telecom & Devices,5699999.88,2600000.0,2.192307646153846,price_outlier,price >= 2x category median,https://utp.sberbank-ast.ru/VIP/NBT/PurchaseView/48/0/0/3363073
ООО Сбербанк-Телеком,SBR028-2508270026.30,1,Оказание услуг по предоставлению во временное пользование канала передачи данных (MPLS) для нужд ООО «Сбербанк-Телеком»,Telecom & Devices,5699999.88,2600000.0,2.192307646153846,price_outlier,price >= 2x category median,https://utp.sberbank-ast.ru/VIP/NBT/PurchaseView/48/0/0/3363073
ООО Сбербанк-Телеком,SBR028-2512230030.1,1,Предоставление права использования лицензий PT Sandbox для ООО «Сбербанк-Телеком»,Telecom & Devices,5500000.0,2600000.0,2.1153846153846154,price_outlier,price >= 2x category median,https://utp.sberbank-ast.ru/VIP/NBT/PurchaseView/48/0/0/3703094
ООО Сбербанк-Телеком,SBR028-2508270004.2,1,Оказание услуг по предоставлению во временное пользование канала передачи данных (GN) для нужд ООО «Сбербанк-Телеком»,Telecom & Devices,5303999.88,2600000.0,2.039999953846154,price_outlier,price >= 2x category median,https://utp.sberbank-ast.ru/VIP/NBT/PurchaseView/48/0/0/3361589
ООО Сбербанк-Телеком,SBR028-2508270004.1,1,Оказание услуг по предоставлению во временное пользование канала передачи данных (GN) для нужд ООО «Сбербанк-Телеком»,Telecom & Devices,5013000.0,2600000.0,1.928076923076923,price_outlier,top 15% by price,https://utp.sberbank-ast.ru/VIP/NBT/PurchaseView/48/0/0/3361589
ООО Сбербанк-Телеком,SBR028-2511180038.1,1,Оказание услуг по организации Новогоднего корпоратива для ООО «СБЕРБАНК-ТЕЛЕКОМ»,Telecom & Devices,5000000.0,2600000.0,1.9230769230769231,price_outlier,top 15% by price,https://utp.sberbank-ast.ru/VIP/NBT/PurchaseView/45/0/0/3576567
ООО Сбербанк-Телеком,SBR028-2403280016.1,1,Оказание услуг Контактного центра по исходящему обзвону абонентов с целью удержания,Other,4974000.0,100250.0,49.61596009975062,price_outlier,price >= 2x category median,https://utp.sberbank-ast.ru/VIP/NBT/PurchaseView/45/0/0/1778054
ООО Сбербанк-Телеком,SBR028-2508270004.6,1,Оказание услуг по предоставлению во временное пользование канала передачи данных (GN) для нужд ООО «Сбербанк-Телеком»,Telecom & Devices,4284000.0,2600000.0,1.6476923076923078,price_outlier,top 15% by price,https://utp.sberbank-ast.ru/VIP/NBT/PurchaseView/48/0/0/3361589
ООО Сбербанк-Телеком,SBR028-2508270004.5,1,Оказание услуг по предоставлению во временное пользование канала передачи данных (GN) для нужд ООО «Сбербанк-Телеком»,Telecom & Devices,4023000.0,2600000.0,1.5473076923076923,price_outlier,top 15% by price,https://utp.sberbank-ast.ru/VIP/NBT/PurchaseView/48/0/0/3361589
ООО Сбербанк-Телеком,SBR028-2508270004.10,1,Оказание услуг по предоставлению во временное пользование канала передачи данных (GN) для нужд ООО «Сбербанк-Телеком»,Telecom & Devices,3708000.0,2600000.0,1.426153846153846,price_outlier,top 15% by price,https://utp.sberbank-ast.ru/VIP/NBT/PurchaseView/48/0/0/3361589
ООО Сбербанк-Телеком,SBR028-2508270026.5,1,Оказание услуг по предоставлению во временное пользование канала передачи данных (MPLS) для нужд ООО «Сбербанк-Телеком»,Telecom & Devices,3444000.12,2600000.0,1.3246154307692308,price_outlier,top 15% by price,https://utp.sberbank-ast.ru/VIP/NBT/PurchaseView/48/0/0/3363073
ООО Сбербанк-Телеком,SBR028-2508270026.6,1,Оказание услуг по предоставлению во временное пользование канала передачи данных (MPLS) для нужд ООО «Сбербанк-Телеком»,Telecom & Devices,3444000.12,2600000.0,1.3246154307692308,price_outlier,top 15% by price,https://utp.sberbank-ast.ru/VIP/NBT/PurchaseView/48/0/0/3363073
ООО Сбербанк-Телеком,SBR028-2408270012.1,1,"Поставка персонализированных SIM-карт USIM в форм факторе микросхемы (MFF2, VQFN-8, VFDFPN8 5 × 6 mm)",Telecom & Devices,3100000.0,2600000.0,1.1923076923076923,price_outlier,top 15% by price,https://utp.sberbank-ast.ru/VIP/NBT/PurchaseView/45/0/0/2251605
ООО Страховой брокер Сбербанка,SBR003-240017162400003.1,1,"Оказание услуг по администрированию Positive Technologies Application Firewall (PT AF), мониторингу и реагированию на инциденты безопасности и нарушения работоспособности PT AF для нужд ООО «Страховой брокер Сбербанка».",Security,2772000.0,2772000.0,1.0,price_outlier,top 15% by price,https://utp.sberbank-ast.ru/Trade/NBT/PurchaseView/13/0/0/2241914
ООО Сбербанк-Телеком,SBR028-2508270004.9,1,Оказание услуг по предоставлению во временное пользование канала передачи данных (GN) для нужд ООО «Сбербанк-Телеком»,Telecom & Devices,2763000.0,2600000.0,1.0626923076923076,price_outlier,top 15% by price,https://utp.sberbank-ast.ru/VIP/NBT/PurchaseView/48/0/0/3361589
ООО Сбербанк-Телеком,SBR028-2508270026.7,1,Оказание услуг по предоставлению во временное пользование канала передачи данных (MPLS) для нужд ООО «Сбербанк-Телеком»,Telecom & Devices,2616000.12,2600000.0,1.0061538923076923,price_outlier,top 15% by price,https://utp.sberbank-ast.ru/VIP/NBT/PurchaseView/48/0/0/3363073
ООО Сбербанк-Телеком,SBR028-2508270026.8,1,Оказание услуг по предоставлению во временное пользование канала передачи данных (MPLS) для нужд ООО «Сбербанк-Телеком»,Telecom & Devices,2616000.12,2600000.0,1.0061538923076923,price_outlier,top 15% by price,https://utp.sberbank-ast.ru/VIP/NBT/PurchaseView/48/0/0/3363073
ООО Сбербанк-Телеком,SBR028-2511100087.1,1,"Поставка лицензий RedCheck для ООО ""СБЕРБАНК-ТЕЛЕКОМ""",Telecom & Devices,2600000.0,2600000.0,1.0,price_outlier,top 15% by price,https://utp.sberbank-ast.ru/VIP/NBT/PurchaseView/48/0/0/3554113
ООО Сбербанк-Телеком,SBR028-2408290007.1,1,оказание услуг разработке API OTRS для технологического обслуживания сетей Партнера и ООО «Сбербанк-Телеком»,Telecom & Devices,2400000.0,2600000.0,0.9230769230769231,price_outlier,top 15% by price,https://utp.sberbank-ast.ru/VIP/NBT/PurchaseView/45/0/0/2256929
ООО Сбербанк-Телеком,SBR028-2508270026.1,1,Оказание услуг по предоставлению во временное пользование канала передачи данных (MPLS) для нужд ООО «Сбербанк-Телеком»,Telecom & Devices,2295000.0,2600000.0,0.8826923076923077,price_outlier,top 15% by price,https://utp.sberbank-ast.ru/VIP/NBT/PurchaseView/48/0/0/3363073
ООО Сбербанк-Телеком,SBR028-2508270026.2,1,Оказание услуг по предоставлению во временное пользование канала передачи данных (MPLS) для нужд ООО «Сбербанк-Телеком»,Telecom & Devices,2295000.0,2600000.0,0.8826923076923077,price_outlier,top 15% by price,https://utp.sberbank-ast.ru/VIP/NBT/PurchaseView/48/0/0/3363073
АО Сбербанк Лизинг,96495614,1,Оказание услуг по организации видеосъемки и проведению онлайн-трансляций,Other,2250000.0,100250.0,22.443890274314214,price_outlier,price >= 2x category median,https://sberb2b.ru/request/supplier/preview/263e2099-2e7a-40e4-8c80-ac2ef6e75bb2
ООО Сбербанк-Телеком,SBR028-2508270026.11,1,Оказание услуг по предоставлению во временное пользование канала передачи данных (MPLS) для нужд ООО «Сбербанк-Телеком»,Telecom & Devices,2177280.0,2600000.0,0.8374153846153846,price_outlier,top 15% by price,https://utp.sberbank-ast.ru/VIP/NBT/PurchaseView/48/0/0/3363073
ООО Сбербанк-Телеком,SBR028-2508270026.12,1,Оказание услуг по предоставлению во временное пользование канала передачи данных (MPLS) для нужд ООО «Сбербанк-Телеком»,Telecom & Devices,2177280.0,2600000.0,0.8374153846153846,price_outlier,top 15% by price,https://utp.sberbank-ast.ru/VIP/NBT/PurchaseView/48/0/0/3363073
ООО Сбербанк-Телеком,SBR028-2508270026.21,1,Оказание услуг по предоставлению во временное пользование канала передачи данных (MPLS) для нужд ООО «Сбербанк-Телеком»,Telecom & Devices,2062800.0,2600000.0,0.7933846153846154,price_outlier,top 15% by price,https://utp.sberbank-ast.ru/VIP/NBT/PurchaseView/48/0/0/3363073
ООО Сбербанк-Телеком,SBR028-2508270026.22,1,Оказание услуг по предоставлению во временное пользование канала передачи данных (MPLS) для нужд ООО «Сбербанк-Телеком»,Telecom & Devices,2062800.0,2600000.0,0.7933846153846154,price_outlier,top 15% by price,https://utp.sberbank-ast.ru/VIP/NBT/PurchaseView/48/0/0/3363073
ООО Сбербанк-Телеком,SBR028-2508270026.3,1,Оказание услуг по предоставлению во временное пользование канала передачи данных (MPLS) для нужд ООО «Сбербанк-Телеком»,Telecom & Devices,2045520.0,2600000.0,0.7867384615384615,price_outlier,top 15% by price,https://utp.sberbank-ast.ru/VIP/NBT/PurchaseView/48/0/0/3363073
ООО Сбербанк-Телеком,SBR028-2508270026.4,1,Оказание услуг по предоставлению во временное пользование канала передачи данных (MPLS) для нужд ООО «Сбербанк-Телеком»,Telecom & Devices,2045520.0,2600000.0,0.7867384615384615,price_outlier,top 15% by price,https://utp.sberbank-ast.ru/VIP/NBT/PurchaseView/48/0/0/3363073
ООО Сбербанк-Телеком,SBR028-2508270026.10,1,Оказание услуг по предоставлению во временное пользование канала передачи данных (MPLS) для нужд ООО «Сбербанк-Телеком»,Telecom & Devices,1893359.88,2600000.0,0.7282153384615384,price_outlier,top 15% by price,https://utp.sberbank-ast.ru/VIP/NBT/PurchaseView/48/0/0/3363073
ООО Сбербанк-Телеком,SBR028-2508270026.9,1,Оказание услуг по предоставлению во временное пользование канала передачи данных (MPLS) для нужд ООО «Сбербанк-Телеком»,Telecom & Devices,1893359.88,2600000.0,0.7282153384615384,price_outlier,top 15% by price,https://utp.sberbank-ast.ru/VIP/NBT/PurchaseView/48/0/0/3363073
ООО Сбербанк-Телеком,SBR028-2511260061.1,1,Оказание услуг технической поддержки для программного комплекса по анализу конфигураций сетевого оборудования «Нетхаб» для ООО «Сбербанк-Телеком»,Telecom & Devices,1800000.0,2600000.0,0.6923076923076923,price_outlier,top 15% by price,https://utp.sberbank-ast.ru/VIP/NBT/PurchaseView/48/0/0/3605409
ООО Сбербанк-Телеком,SBR028-2508270026.13,1,Оказание услуг по предоставлению во временное пользование канала передачи данных (MPLS) для нужд ООО «Сбербанк-Телеком»,Telecom & Devices,1656000.0,2600000.0,0.6369230769230769,price_outlier,top 15% by price,https://utp.sberbank-ast.ru/VIP/NBT/PurchaseView/48/0/0/3363073
ООО Сбербанк-Телеком,SBR028-2508270026.14,1,Оказание услуг по предоставлению во временное пользование канала передачи данных (MPLS) для нужд ООО «Сбербанк-Телеком»,Telecom & Devices,1656000.0,2600000.0,0.6369230769230769,price_outlier,top 15% by price,https://utp.sberbank-ast.ru/VIP/NBT/PurchaseView/48/0/0/3363073
```

## Suggested Prompt

Сформируй аналитическую записку по закупкам группы Сбер за 2024–2025 годы. Для каждого блока дай Observation, Interpretation, Significance и Limitation. Отдельно перечисли аномалии, оцени полноту покрытия по источникам и предложи 5 гипотез для следующего исследования.
