# Проверка — 28 октября 2026

- `python -m pytest -q`: 20 passed. В тестовом клиенте Starlette есть предупреждение о будущем переходе с httpx на httpx2; ошибки выполнения нет.
- `ruff check app tests`: PASS; `ruff format --check app tests`: PASS.
- `node --check app/static/app.js`: PASS.
- `pip check`: зависимости совместимы.
- Новое отдельное venv: установка только requirements.txt и `python -m app.demo --database ...` прошли. Команда не требует тестового клиента/httpx.
- Браузер: создание ученика с тарифом 123,45 увеличило долг с 11 900,00 до 12 023,45. Удаление этого ученика без оплат вернуло прежний итог.
- Оплата Марка 100,00 уменьшила общий долг с 12 000,00 до 11 900,00 и появилась в истории. Попытка удалить Марка отклонена с объяснением сохранения истории.
- После перезагрузки браузера оплата сохранена. Сохранность после пересоздания приложения дополнительно проверена API-тестом.
- Экран 375×812: карточки в одну колонку, форма ниже списка, ширина документа и viewport равны 375px. Настольный и мобильный скриншоты сохранены рядом.

Проверки проводились на вымышленных локальных данных. Продакшен, нагрузочное тестирование, банковские операции и проверка на физическом телефоне не выполнялись.

## Редизайн и темы

Выбранный макет Higgsfield и реализация сопоставлены при1024×688 (одинаковая плотность), полный экран и область таблицы: design/comparison.png и design/comparison-detail.png. Итоговый отчёт: ../design-qa.md. Светлая и тёмная темы проверены при375×812; горизонтальной прокрутки нет. Переключение сохраняется после reload. При новой оплате0,01 за28сентября в браузере получено подтверждение, запись появилась в истории Марка, октябрьский долг не изменился. Консоль проверочного экрана без ошибок/предупреждений. Платежи только вымышленные.

## Локализация и страницы документов

- `node --test tests/i18n.test.cjs`: 3 passed. Регрессии: сохранение `{id}` в примерах API, явные узбекские названия месяцев, полнота ключей и региональных редакций.
- RU / UZ / EN проверены в браузере: подписи основной формы, суммы, месяц, навигация, страницы политики/условий/прав и API. Текст пользовательских записей остаётся без перевода. Английская форма нового ученика открывается с английскими полями.
- Переключение языка сохраняет введённую сумму основной формы; значение затем очищено без отправки. Узбекский язык и светлая тема сохранились после перезагрузки.
- Политика UZ в светлой теме и API в тёмной при375×812: viewport и scrollWidth равны375px. Документация RU при1024×768: обе ширины1024px. Скриншоты: api-dark.png, privacy-mobile-uz.png.
- Локальная консоль `/docs`: GET /students вернул HTTP200 и фиктивные записи; записывающие методы в этой проверке не отправлялись.
- Дополнительные HTML-страницы, редирект `/redoc`, тексты лицензий и OpenAPI доступны. HTTP-проверка не обнаружила Set-Cookie. Это не юридическая сертификация и не тест производственной обработки персональных данных.

## Валюта и правдоподобные фикстуры

Суммы, тарифы, история и поля ввода имеют обозначение UZS (сум / so‘m / UZS). Визуально проверены RU1024px и UZ375px с общим долгом1340000.00; денежные колонки и мобильные карточки поправлены под более длинные суммы. Смена языка не конвертирует значения. Новая пустая временная БД заполнена через app.demo: тарифы800000,500000,850000,600000UZS подтверждены API. Текущие локальные четыре вымышленные записи и пять тестовых платежей обновлены с резервной копией; пользовательские базы автоматически не мигрируют. Скриншоты README обновлены.

## Рефакторинг, локальная граница и валюты

25pytest прошли, включая чужой Host/Origin, JSON Content-Type, одновременные идемпотентные запросы, конфликт ключа, неразрушающее обновление старой схемы и запрет БД в static. 5Node проверок: локализация и пересчёт UZS/RUB/USD с возвратом к исходной сумме, allowlist сохранённой валюты. При обновлении текущей локальной БД сохранена резервная копия data/before-refactor.sqlite3; integrity_check=ok, foreign_key_check пуст,4ученика/5оплат сохранены. API запускается на прежнем порту; полный браузерный DNS exploit не выполнялся. Статический аудит выявил условный localhost DNS rebinding (low), закрытый Host/Origin guard и регрессионными проверками. Это не сертификат безопасности публичного сервиса.

Браузер после рефакторинга: RUB≈9051.61, USD≈112.43, возвратUZS1340000.00; строки/тарифы/история пересчитываются, ввод остаётсяUZS. СохранённаяUSD восстановилась послеreload. При375px DOMscrollWidth=375; API-консольGET/students вернулаHTTP200 под новымCSP. Консоль проверенной вкладки безwarning/error. Скриншот docs/currency-rub.png. Измерение ширины не заменяет физический мобильный тест.

## Повторная проверка: исторические даты

34pytest и6Node-проверок: начало обучения/старые отчёты/задние даты/идемпотентность, запрет переноса начала поверх истории, обновление без start_month, неправильные месяцы,0001/0099, високосные1900/2000/2024, декабрь9999 и ID за signed64. Браузер:2020-01 показывает0 и«Начислений ещё нет»;2026-09 — толькоМарка с известной сентябрьской оплатой. «Внести» очищает октябрьскую дату и ограничивает её2026-09-01…30 с явным пояснением. Новая оплата при этой проверке не отправлялась.

Локальная миграция: резервная копияdata/before-enrollment.sqlite3; integrity_check=ok, foreign_key_check пуст,5оплат сохранены. Начало1/3/4=2026-10,2=2026-09 по известной оплате. Повторный независимый статический аудит20cf392 не подтвердил новых уязвимостей; последующие изменения дат проверены отдельными регрессиями. Это не повторный аудит итогового коммита, не проверка эксплуатации или зависимостей.


## Повторный независимый аудит и гонки интерфейса

Три независимых агента проверили границы безопасности, API/SQLite и интерфейс. Security baseline clean6d76422: подтверждённых уязвимостей в локальном демо не найдено; без проверки advisory зависимостей, exploit, истории Git и production. После исправлений выполнен точечный просмотр diff.

34pytest и13Node PASS, Ruff lint/format и синтаксис JS PASS. Семь новых тестов исполняют реальные обработчики app.js в минимальном DOM с управляемыми задержанными ответами: очистка customValidity, защита оплаты во время запроса и смены отображения, успех/ошибка старого сохранения и удаления после открытия новой формы, загрузка/ошибка нового месяца. Новый набор не проходит на исходном app.js; временная копия исходников использована без изменения рабочего дерева.

Дополнительные disposable SQLite проверки агента: миграции v0/v1/v2, откат при внедрённой ошибке после ALTER,20гонок оплаты/смены начала обучения, максимальные денежные значения и крайние даты. Нарушений не обнаружено; рабочая база не менялась.

Браузер: прежняя последовательность «Сохранить» пустую оплату → «Внести Марка» воспроизвела customError=true до исправления и false после. Пустая форма ученика после ошибки, закрытия и повторного открытия также не сохраняет customError. Записывающих запросов в браузере не выполнялось. Консоль без warning/error. Скриншот refactor-ui-state.png.

## Полный QA-проход: 28 октября 2026

В отдельной временной БД через браузер создан вымышленный ученик с тарифом 1000,50 и началом обучения 2026-09: за август долг нулевой, платеж 31 августа отклонён. Платежи 300,10 и 700,40 за 15 сентября дали нулевой долг за сентябрь и 1000,50 за октябрь; история показала две записи. Удаление ученика с оплатами и перенос начала обучения на ноябрь отклонены (409). После смены имени и тарифа на 1100,50 долг стал 100 за сентябрь и 1100,50 за октябрь. Учебная запись с нулевым тарифом создана и удалена. После перезагрузки данные сохранились. Ввод `<script>` отображён как текст; переключение на UZ/USD не изменило введённые 700,40 UZS.

Исправлено обновление пояснения периода оплаты при смене языка; после смены на EN оно отображается по-английски. Добавлена регрессионная проверка. Итог: 34 pytest и 14 Node-проверок прошли; Ruff lint/format и `pip check` прошли. Независимый расчёт для временной БД (12 учеников, 120 оплат, 8 месяцев) совпал с целочисленными суммами. На ширине 375px горизонтальной прокрутки нет; локальная GET `/students` вернула 200. SQLite integrity check успешен, внешних ключей без пары нет; основная БД осталась без изменений. Скриншот: full-flow-qa.png. Данные вымышленные.

## Повторный обзор b343125

Три независимых агента GPT-6 Luna проверили безопасность исходников, API/БД и интерфейс. Подтверждённых уязвимостей в проверенных runtime-путях и новых ошибок расчёта БД не найдено. Это ограниченный Standard source review: без dependency advisory, exploit, истории Git и исчерпывающей проверки статического контента/дизайн-материалов. 34pytest,15Node и Ruff проходят.

Найдена и исправлена ошибка API-консоли: после пустого ID или месяца скрытое поле продолжало блокировать запрос к другому маршруту. Неиспользуемые поля теперь disabled, а customValidity сбрасывается при выборе маршрута; активные поля сохраняют required. Регрессионный тест использует настоящий document.js, на исходной версии падает. В браузере оба сценария «неверное поле → GET /students» возвращают HTTP200 после исправления; до него скрытый ID имел customError=true и willValidate=true. Записывающих запросов не выполнялось. Основная БД: integrityok,FKнарушений0,4ученика/5оплат. Скриншот api-console-validation.png.

## Сверка с ТЗ и редактура

Требования и ограничения сопоставлены в [проверке готовности](readiness.md). Рассказ об AI сокращён до восьми предложений, убрано неподтверждённое утверждение о журнале времени. Luna вычитала README, AI-описание и журнал дизайна; старые числа проверок сохранены как история этапов. В условиях RU/UZ/EN исправлена устаревшая фраза об отсутствии конвертации и добавлено начало начислений с месяца зачисления. Три Node-проверки локализации и синтаксис legal-content.js проходят. В браузере все редакции условий показывают UZS для учёта и RUB/USD для справочного отображения; снимок legal-terms-qa.png. Правовая сверка ограничена уведомлениями локальной демонстрации, не подтверждает готовность оператора к работе с реальными данными.

## Автоматические курсы валют

Проходят 45 тестов Python и 20 тестов JavaScript, Ruff lint/format и проверка синтаксиса JS. Новые тесты используют подставной транспорт и проверяют:

- нормализацию CBU и кросс-курс CBR с учётом Nominal, запрос на заданную дату;
- отклонение будущих, некорректных и слишком больших ответов, XML с DTD;
- сохранение и перезапуск кеша, сбой диска и сети, часовой TTL, смену даты в Москве, пятиминутный интервал повторов и параллельные запросы;
- сохранность БД с именем exchange-rates.json: кеш получает отдельное имя;
- обновление браузера по таймеру, online и видимости, объединение одновременных запросов, резервный курс и сохранение последней ставки.

Реальный CBU HTTPS-запрос в этой сети завершился TLS EOF; проверка TLS не отключалась. Датированный CBR-запрос за 28.10.2026 успешно вернул 80,5307 RUB за 1 USD и 67,8899 RUB за 10 000 UZS. Приложение получило 147,29731521183564 UZS за 1 RUB и 11861,955902129772 UZS за 1 USD со статусом fresh и источником CBR. Запрос без даты возвращал 29.10.2026, поэтому в реализации дата обязательна. Повторный GET /exchange-rates использовал кеш с тем же fetched_at.

В браузере итог 1 340 000 UZS показан как ≈112,97 USD и ≈9 097,25 RUB. Введённые 123,45 UZS сохранились при смене валюты; затем поле очищено без отправки. Источник, дата действия и время получения видны, после перезагрузки данные снова получены через локальный API. При ширине 375 px scrollWidth равен 375. Основная БД проверена только на чтение: integrity_check=ok, нарушений внешних ключей нет, 4 ученика и 5 оплат сохранены. Скриншот automatic-rates.png. Запросы курса не содержат данных ведомости.

## Multicurrency payment booking — 28 October 2026

50 pytest tests and22 Node tests pass; Ruff lint/format and diff checks pass. Added coverage for original currency retention, mixed debt aggregation, half-up conversion, unavailable rates, idempotent replay after rate changes, range checks and legacy schema migration. Browser QA used a separate database copy:2USD saved as23723.91UZS at the official quote; history retained2USD and the frozen booked amount. Main database migration retained all5existing payments, dates, amounts and idempotency records; integrity_check=ok, foreign_key_check empty. Mobile viewport375px had no horizontal overflow. Screenshots: [form](multicurrency-form.png), [history in QA copy](multicurrency-history.png). Tariffs remain UZS. Historical verification sections describe earlier versions.

## Payment and FX logic recheck — 28 October 2026

Added a mixed ledger test:1000UZS+10RUB at150+2USD at12000 books26500UZS against a50000UZS fee, leaving23500UZS. Changing live quotes, reading /exchange-rates and restarting the application preserve the full payment history and base debt. A later payment uses the new rate; overpayment produces no negative debt and does not carry into the next month. An exact half-cent conversion rounds up (0.01RUB×150.5=1.51UZS). A browser unit test confirms that display conversion changes with the quote while the original amount and booked base remain intact.

Found and fixed an extreme-value failure: individually valid foreign conversions could together overflow SQLite SUM. The payment transaction now checks the student/month combined total using Python integers before insertion, under the same write lock. Over-limit writes return422 without changing history; the report remains available. Existing ordinary and idempotent behavior is covered by the suite. This review does not change enrollment, tariff-history or carry-forward rules.

## Parallel review after multicurrency — 28 October 2026

Three bounded agents reviewed backend/accounting, frontend behavior and security. Confirmed and repaired: large-value display lost cents through Number; CBR cross-rate float normalization could change one booked cent; payment errors misidentified amount limits as invalid months. Decimal source normalization at60digits and booking at80digits preserve the source rate; snapshots persist exact booking_rates and payment exchange_rate is a decimal string. Browser formatting uses BigInt decimal division and exact string formatting. Regression:7548371392.39USD at CBR source values80.5307RUB/USD and67.8899RUB/10000UZS now books89538448589428.08UZS. Existing payment snapshots remain unchanged.

The Standard security scan was pinned to d5bf618 and retained a low conditional finding for forged Host when externally bound. The current patch adds loopback peer enforcement; regression tests reject external IPv4/private/IPv6 peers even with Host:localhost and retain IPv6 loopback support. The sealed scan predates this fix and is not represented as a clean scan of the final patch. Source review used a single-worker fallback because scan delegation was unavailable. An incidental search traversed Git log paths; redacted path markers were not used as audit evidence. Subsequent patch validation is covered by targeted tests and parent review.

Browser check on the main local page: changing display currency retained the exact123.45USD draft; it was cleared without submission. Main database still has5payments totaling141000100minorUZS units, integrity_check ok and no foreign-key violations. No schema migration or monetary data rewrite was needed in this iteration.

Final checks for this patch:61pytest and29Node tests pass; Ruff lint/format, JS syntax, diff check and staged secret scan pass. Live localhost GET/debtors returned200 with unchanged1340000.00UZS debt after restart. Screenshot: [review-v7.png](review-v7.png). The local-only/no-auth deployment limitation remains; no claim of production readiness or absence of all vulnerabilities is made.

## User-facing copy cleanup — 28 October 2026

Removed the redundant payment-recording disclaimer and API documentation link from the main screen. Exchange-rate metadata is collapsed under an accessible details control; freshness remains visible in its summary. Shortened enrollment and retry messages in RU/UZ/EN. Legal pages and developer documentation remain available at their existing routes.29Node tests pass; browser verified expansion/collapse and retained amounts without writes. Screenshot: [clean-interface.png](clean-interface.png).

## Inline exchange-rate display

The rate control is a quiet text disclosure below the balance caption. Foreign display currencies show the quote and effective date; UZS hides the rate control because no display conversion is needed. Stale/fallback warnings remain visible. Numeric dates avoid missing Uzbek month names in browser Intl data. Public browser checks covered Russian/Uzbek date rendering, USD conversion and the native disclosure. 29 JavaScript tests pass. Screenshot: [inline rate](inline-rate.png). No ledger data changed.

## Cancellation / activity — 29 October 2026

92 Python and42 Node tests pass. New adapter-parametrized tests cover void/retry/conflicting reason, immutable FX snapshots on void and replacement, debt/statement totals, concurrent voids (one event), visitor isolation/CSRF, failed-write preservation, audit pagination and schema3→4 migration without invented events. UI tests cover RUB overpayment followed by selecting another student and a stalled payment request that unlocks controls while retaining its retry key.

Separate disposable SQLite DB on127.0.0.1:8786: browser recorded10000RUB overpayment, selectedTimur andAnna afterwards, voided with a reason, prepared and saved500000UZS replacement, and voided it again. Original history remained, debt restored, audit ordered. No user/public session changed.24 responsive combinations (320/390/720/1440 × RU/UZ/EN ×2themes) for activity/history/void dialog: no measured horizontal overflow. Later public/mobile hit-testing reproduced the reported button failure: the positioned .debtor-person spanned the pay button and intercepted taps. Replaced its right padding with an80px outside margin so its actual hit box ends before the button. The timeout separately prevents indefinite locking on stalled network requests. Evidence stays private in review/operations-ui-matrix.json.

Mobile tap regression: after the hit-box fix,72 real pay-button clicks (3students ×4widths ×3languages ×2themes) selected the intended student. Before the fix, DOM hit-testing returned the debtor-person overlay and the form remained unchanged. Evidence: review/payment-button-taps.json.

## Async correction and session recovery — 29 October 2026

The read-only review found two reproducible UI races. Correction now keeps its blocking dialog open through the report refresh, closing only immediately before preparing the replacement draft. The regression checks that the dialog cannot be closed during that wait and that a subsequent different payment retains its fields and retry key after a failed request.

Hosted session initialization now has a15-second deadline covering the Web Lock wait, fetch and response body. Expiration aborts the pending operation and clears the shared initialization promise so concurrent retries share a new attempt. Tests separately stall the fetch, JSON body and lock queue; all recover on retry. Existing two-tab cookie serialization remains covered. Full checks:92Python and46Node tests pass, Ruff check/format pass. No database or stored payment change is required.

## Исправления по полному аудиту — 29 октября 2026

Локальные изменения после опубликованной версии `19e4b45`:

- Консоль API ограничивает ожидание ответа и тела 20 секундами, снимает блокировку управления и не повторяет записывающий запрос автоматически. Тайм-аут сообщает о неизвестном результате операции.
- Кнопки расчёта долга озвучивают ученика, действие и отображаемую сумму с валютой. Стрелки месяца восстанавливают пустое/некорректное поле относительно текущего локального месяца и соблюдают пределы 0001–9999.
- Выбор `?lang=ru|uz|en` работает при запрете localStorage. Консоль явно обозначена как подмножество API со ссылкой на полную схему.
- Cloud API возвращает отсутствующие поля отмены активных оплат как `null`, включая чтение прежних сеансов и повтор по ключу. Исторические снимки журнала не переписываются. Месяц оплаты извлекается из ISO-даты без зависимости от системного strftime.
- CI устанавливает корневой lock-файл, фиксирует Node22 и включает Python3.11/3.13; эти два задания CI в данном проходе ещё не запускались. Облачные зависимости остаются отдельными, со своей средой выполнения.

Проверено на Python3.13: **109 pytest**, **58 Node tests**, Ruff check/format, Cloudflare asset build и `git diff --check` — PASS. Есть прежнее предупреждение Starlette о будущем переходе тестового клиента с httpx на httpx2. Новые регрессии проверяют зависание fetch/тела, отсутствие автоматического повтора, журнал/пагинацию/устаревшие ответы/языки, откат позднего сбоя миграции, атомарный отказ пяти операций при лимите событий, старые валютные записи и крайние годы.

В браузере локальный сервер с отдельной вымышленной БД: очистка месяца → стрелка восстановила корректный ноябрь2026; RU/EN/UZ сменили подписи и доступные имена; переключение темы сохранило данные; GET из API-консоли вернул200 и разблокировал кнопку. Это точечная проверка Chromium, а не новая полная матрица устройств.

Оставшиеся отдельные проверки: физический Safari/iPhone и Firefox; нагрузка и конкуренция реального Worker/D1; ограничение размера потокового ответа поставщика курсов до полного чтения; согласование/проверка облачной матрицы зависимостей. Эти пункты не объявлены выполненными. Экспорт, история тарифов и атомарная замена взноса остаются возможным развитием вне исходного ТЗ.
