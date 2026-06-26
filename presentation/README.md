# Дашборд «Аналитика закупок группы Сбер»

Интерактивный дашборд для демонстрации результатов анализа закупок Сбербанка и дочерних юрлиц за 2024–2025 годы.

**Стек:** React 19 · Vite 8 · Recharts · Framer Motion · Lucide React · Vanilla CSS

## Быстрый запуск

```bash
npm install
npm run dev
# http://localhost:5173
```

## Структура

```
src/
  data.json          # единственный источник данных для всех компонентов
  App.jsx            # тема (isDark state), layout
  index.css          # дизайн-система (токены, dark/light mode)
  components/
    Dashboard.jsx    # все 5 вкладок, графики, анимации
  assets/            # статика
generate_defense_speech.py  # генерирует Defense_Speech.docx
Defense_Speech_FINAL.docx   # готовая защитная речь (по вкладкам дашборда)
```

## Вкладки дашборда

| # | Вкладка | Содержимое |
|---|---|---|
| 1 | **История** | 6 шагов от 10 юрлиц до 3 161 лота. Playwright CAPTCHA bypass. Fabrikant (4 попытки, blocked). Clean Merge. |
| 2 | **Топ закупок** | Горизонтальный bar chart top-12 по цене. Cloud.ru 72.5% бюджета. |
| 3 | **Макроэк.** | USD + ставка ЦБ, лаг CCF 3 мес (r=0.546). Тепловая карта публикаций. Декабрьский «слив». |
| 4 | **ML Аномалии** | HHI-шкала (5698). Scatter — Isolation Forest. Radar (нормализован). Treemap. |
| 5 | **AI Инсайты** | 6 аномалий с Risk Score 1–10. A1: мегалот 13.3 млрд, Z=19.96. |

## Данные

Все данные в `src/data.json`. Для обновления — редактировать только `data.json`. Граф KPI:

- **3 161** закупка
- **30,5 млрд ₽** суммарный бюджет
- **22** юрлица с закупками (из 32 в скопе)
- **HHI = 5 698** — концентрация вендоров

## Защитная речь

```bash
# Закрой Defense_Speech.docx в Word перед запуском
python generate_defense_speech.py
# Результат: Defense_Speech.docx
```

Речь идёт последовательно по 5 вкладкам дашборда. Раздел «Архитектура» вынесен в приложение (Appendix). 14 подсказок для комиссии с объяснением технических терминов.

`Defense_Speech_FINAL.docx` — готовая копия, если оригинал заблокирован Word.

## Тема

Кнопка Sun/Moon в правом верхнем углу переключает тёмную/светлую тему без перезагрузки.

## Демонстрация БД (отдельно от дашборда)

```bash
# Из корня проекта:
python export_to_sqlite.py
# -> purchase_analysis.db + demo_queries.sql

# Открыть в DB Browser for SQLite:
# File -> Open Database -> purchase_analysis.db
```
