window.VEDOMOST_LEGAL = {
  ru: {
    privacy: [
      ["Журнал и отмена записей", "Для проверки операций сохраняются время действия, снимки полей ученика и сведения о добавлении или отмене оплаты, включая указанную причину. Удаление ученика не удаляет ранее созданные события журнала; отмена взноса не удаляет его исходную запись. Используйте только вымышленные сведения."],
      [
        "Область действия и автор",
        "Эта редакция описывает локальную демонстрационную версию «Ведомости» для ознакомления в контексте законодательства России. Автор программы — Павлович Александр Кириллович. Разработчик не предоставляет здесь облачный сервис учебного центра и автоматически не получает записи из вашей базы. Выбор языка меняет редакцию уведомления, а не определяет применимое право.",
      ],
      [
        "Какие данные обрабатываются",
        "Формы позволяют ввести имя, телефон, группу, месяц начала обучения, месячный тариф, исходные сумму и валюту оплаты и дату. Для платежа также сохраняются эквивалент в UZS и сведения о применённом курсе. В демонстрации используйте только вымышленные сведения. Записи передаются браузером локальному серверу для ведения журнала и расчёта долга; реквизиты банковских карт, паспортные данные и платёжные токены приложение не запрашивает.",
      ],
      [
        "Хранение, доступ и сроки",
        "Записи сохраняются в SQLite на компьютере, где запущен сервер, до удаления владельцем этой установки. Автоматического срока удаления и облачной синхронизации нет. Ученика с оплатами интерфейс не удаляет: это защита истории, а не установленное законом основание бессрочного хранения. Полный процесс исполнения требований об уничтожении данных в демоверсии не реализован. Журнал запуска сервера может содержать сетевой адрес, путь запроса и статус ответа.",
      ],
      [
        "Cookies и настройки",
        "Приложение не устанавливает cookies и не использует рекламные трекеры или аналитику. В localStorage браузера сохраняются только тема, язык и валюта отображения: vedomost-theme, vedomost-language и vedomost-currency. Настройки можно удалить через средства браузера; при запрете хранилища приложение продолжает работать с настройками по умолчанию. Шрифты, иконки и документация загружаются с того же сервера. Для обновления курсов сервер запрашивает публичные данные ЦБ Узбекистана и, при недоступности, Банка России. Эти сайты получают сетевой адрес сервера и сведения о HTTP-запросе; записи учеников и оплат им не передаются. По внешним ссылкам действуют правила соответствующих сайтов.",
      ],
      [
        "Защита и ограничения",
        "Сервер предназначен для запуска на 127.0.0.1. В текущей версии нет авторизации, ролевого доступа, шифрования файла базы и автоматических резервных копий. Не размещайте эту демоверсию в открытой сети и не вводите реальные сведения об учениках, включая несовершеннолетних. Платежи здесь только учитываются, деньги не переводятся.",
      ],
      [
        "Россия: перед обработкой реальных данных",
        "Для реального использования оператор должен определить цели, состав данных и законное основание по Федеральному закону №152-ФЗ, опубликовать собственную политику, организовать защиту и исполнение прав субъектов. Применимость уведомления Роскомнадзора, локализации, согласий и правил обработки данных детей проверяется для конкретного оператора и схемы работы. Реальный оператор учебного центра, его адрес, сроки хранения и контакт для обращений в этой демонстрации не определены.",
      ],
      [
        "Обращения",
        "Вопросы о программе можно направить автору по адресу hello@dobropalm.tech. По реальным персональным данным обращаться следует к оператору, который решил использовать программу и контролирует соответствующую базу. Автор не может удалённо получить, исправить или удалить записи из вашей локальной установки.",
      ],
    ],
    terms: [
      [
        "Назначение",
        "«Ведомость» — локальная демонстрация мини-учёта оплат для оценки тестового проекта. Используйте вымышленные записи об учениках и оплатах. Программа записывает полученные оплаты, не переводит деньги и не формирует кассовые чеки или бухгалтерскую отчётность.",
      ],
      [
        "Правила расчёта",
        "Начисления начинаются с указанного месяца начала обучения. Тариф и долг рассчитываются в UZS; переплата не переносится, изменение тарифа влияет и на прошлые месяцы. Платёж вводится в UZS, RUB или USD. При записи сохраняются исходные сумма и валюта, неизменяемый эквивалент в UZS и сведения об официальном курсе. Для RUB/USD нужен свежий официальный курс сервера; для задней даты применяется курс на момент записи. Без свежего курса иностранный платёж не записывается, а UZS работает офлайн. Суммы округляются до сотых по правилу half up. Переключатель валюты показа использует текущий справочный курс и не меняет тарифы или записанные платежи.",
      ],
      [
        "Доступ и использование",
        "Лицензия в LICENSE.txt разрешает ознакомление с исходным кодом и локальную оценку проекта. Для коммерческого внедрения, распространения и перепродажи нужно письменное разрешение. В приложении нет платных подписок, оферты на обучение или оформления договора с учебным центром.",
      ],
      [
        "Ограничения",
        "Программа предоставлена «как есть». Демонстрационная версия не гарантирует пригодность для реального учёта и не заменяет обязательные документы или процедуры оператора. Ничто в этих условиях не исключает права и ответственность, которые нельзя ограничить применимым законодательством России. Для реального запуска нужна отдельная оценка условий и лицензия.",
      ],
    ],
    rights: [
      [
        "Автор и лицензия",
        "©2026 Павлович Александр Кириллович. Исходный код опубликован для ознакомления и оценки. Публичный доступ не означает разрешения на коммерческое внедрение, передачу или перепродажу. Условия определены LICENSE.txt; эта страница даёт краткое пояснение.",
      ],
      [
        "Сторонние материалы и AI",
        "Шрифт Manrope, иконки Lucide и программные зависимости сохраняют собственные лицензии. Разработка велась с помощью Codex, план подготовлен с участием Astra, выбранный визуальный макет создан через Higgsfield. Исключительные права на общую идею учёта, требования тестового или чужие материалы не заявляются.",
      ],
      [
        "Россия и обязательные нормы",
        "Вопросы использования и защиты результатов оцениваются по применимому законодательству, включая часть IV ГК РФ. Публикация исходников технически не предотвращает копирование. Эти условия не гарантируют объём охраны каждого AI-сгенерированного элемента и не отменяют обязательные положения закона. Запросы на разрешение использования: hello@dobropalm.tech.",
      ],
    ],
  },
  uz: {
    privacy: [
      ["Jurnal va bekor qilingan yozuvlar", "Amallarni tekshirish uchun vaqt, o‘quvchi maydonlari nusxalari hamda to‘lovni qo‘shish yoki bekor qilish tafsilotlari, shu jumladan kiritilgan sabab saqlanadi. O‘quvchini o‘chirish avvalgi jurnal hodisalarini yo‘q qilmaydi; to‘lovni bekor qilish uning asl yozuvini o‘chirmaydi. Faqat xayoliy ma’lumotlardan foydalaning."],
      [
        "Qo‘llanish doirasi va muallif",
        "Ushbu tahrir «Vedomost» mahalliy demo versiyasini O‘zbekiston qonunchiligi doirasida tanishtirish uchun tavsiflaydi. Dastur muallifi — Pavlovich Aleksandr Kirillovich. Ishlab chiquvchi bu yerda o‘quv markazining bulutli xizmatini ko‘rsatmaydi va mahalliy bazangizdagi qaydlarni avtomatik olmaydi. Til tanlash xabarnoma tahririni o‘zgartiradi, qo‘llaniladigan huquqni belgilamaydi.",
      ],
      [
        "Qanday ma’lumotlar qayta ishlanadi",
        "Shakllarga ism, telefon, guruh, o‘qish boshlangan oy, oylik tarif, to‘lovning dastlabki summasi va valyutasi hamda sanasini kiritish mumkin. To‘lov uchun UZSdagi ekvivalent va qo‘llangan kurs ma’lumotlari ham saqlanadi. Demoda faqat xayoliy ma’lumotlardan foydalaning. Brauzer yozuvlarni hisob yuritish va qarzni hisoblash uchun mahalliy serverga yuboradi. Bank kartasi rekvizitlari, pasport ma’lumotlari va to‘lov tokenlari so‘ralmaydi.",
      ],
      [
        "Saqlash, kirish va muddatlar",
        "Qaydlar server ishlayotgan kompyuterdagi SQLite bazasida ushbu o‘rnatma egasi o‘chirmaguncha saqlanadi. Avtomatik o‘chirish muddati va bulutli sinxronlash yo‘q. To‘lovlari bor o‘quvchini interfeys o‘chirmaydi: bu tarixni saqlash mexanizmi, cheksiz saqlash uchun huquqiy asos emas. Ma’lumotni yo‘q qilish haqidagi talablarni bajarish jarayoni demoda to‘liq amalga oshirilmagan. Server jurnali tarmoq manzili, so‘rov yo‘li va javob holatini saqlashi mumkin.",
      ],
      [
        "Cookies va sozlamalar",
        "Ilova cookies o‘rnatmaydi, reklama kuzatuvchilari va tahlil xizmatlaridan foydalanmaydi. Brauzer localStorage xotirasida faqat mavzu, til va ko‘rsatish valyutasi — vedomost-theme, vedomost-language hamda vedomost-currency saqlanadi. Ularni brauzer sozlamalarida o‘chirish mumkin. Xotira bloklansa, ilova standart sozlamalar bilan ishlaydi. Shriftlar, belgilar va hujjatlar ayni serverdan yuklanadi. Kurslarni yangilash uchun server O‘zbekiston Markaziy bankidan, u mavjud bo‘lmaganda Rossiya Bankidan ochiq ma’lumotlarni so‘raydi. Bu saytlar serverning tarmoq manzili va HTTP so‘rovi haqidagi ma’lumotlarni oladi; o‘quvchilar va to‘lovlar qaydlari ularga yuborilmaydi. Tashqi havolalardagi saytlarning o‘z qoidalari amal qiladi.",
      ],
      [
        "Himoya va cheklovlar",
        "Server 127.0.0.1 manzilida mahalliy ishga tushirish uchun mo‘ljallangan. Bu versiyada avtorizatsiya, rollar, baza faylini shifrlash va avtomatik zaxiralash yo‘q. Demoni ochiq tarmoqqa joylashtirmang, haqiqiy o‘quvchilar, jumladan voyaga yetmaganlar haqidagi ma’lumotlarni kiritmang. Ilova to‘lovlarni faqat qayd etadi, pul o‘tkazmaydi.",
      ],
      [
        "O‘zbekiston: haqiqiy ma’lumotlardan oldin",
        "Amaliy ishga tushirishdan oldin ma’lumotlar mulkdori va operatori O‘RQ-547-son «Shaxsga doir ma’lumotlar to‘g‘risida»gi Qonunga muvofiq maqsadlar, zarur ma’lumotlar, ishlov berish asosi va himoya choralarini belgilashi kerak. Rozilik, bazani ro‘yxatdan o‘tkazish, saqlash joyi, transchegaraviy uzatish va voyaga yetmaganlar ma’lumotlariga oid talablarning qo‘llanishi haqiqiy ish sharoitiga qarab tekshiriladi. Demoda o‘quv markazining haqiqiy operatori, manzili, saqlash muddatlari va murojaatlar uchun mas’ul shaxs belgilanmagan.",
      ],
      [
        "Murojaatlar",
        "Dastur bo‘yicha savollarni hello@dobropalm.tech manziliga yuborish mumkin. Haqiqiy shaxsga doir ma’lumotlar bo‘yicha dasturdan foydalanish maqsadini belgilagan va bazani boshqaradigan mulkdor yoki operatorga murojaat qiling. Muallif mahalliy o‘rnatmangizdagi qaydlarni masofadan ololmaydi, tuzatolmaydi yoki o‘chirolmaydi.",
      ],
    ],
    terms: [
      [
        "Maqsad",
        "«Vedomost» — sinov loyihasini baholash uchun to‘lovlar hisobining mahalliy demosi. O‘quvchilar va to‘lovlar haqida faqat xayoliy ma’lumotlardan foydalaning. Dastur olingan to‘lovlarni qayd etadi, pul o‘tkazmaydi, fiskal cheklar yoki buxgalteriya hisobotlarini yaratmaydi.",
      ],
      [
        "Hisoblash qoidalari",
        "Hisoblash ko‘rsatilgan o‘qish boshlangan oydan boshlanadi. Tarif va qarz UZSda hisoblanadi; ortiqcha to‘lov boshqa oyga o‘tmaydi, tarif o‘zgarishi oldingi oylarga ham ta’sir qiladi. To‘lov UZS, RUB yoki USDda kiritiladi. Dastlabki summa va valyuta, UZSdagi o‘zgarmas ekvivalent va qo‘llangan rasmiy kurs ma’lumotlari saqlanadi. RUB/USD uchun serverda yangi rasmiy kurs bo‘lishi kerak; oldingi sana kiritilsa ham, yozuv paytidagi kurs qo‘llanadi. Yangi kurs bo‘lmasa, chet el valyutasidagi to‘lov yozilmaydi; UZS internetsiz ishlaydi. Summalar half up qoidasi bilan yuzdan birgacha yaxlitlanadi. Ko‘rsatish valyutasi almashtirgichi joriy ma’lumot kursidan foydalanadi va tariflar yoki yozilgan to‘lovlarni o‘zgartirmaydi.",
      ],
      [
        "Foydalanish",
        "Ochiq repozitoriy LICENSE.txt doirasida tanishish va mahalliy baholashga ruxsat beradi. Yozma ruxsatsiz tijoriy joriy etish, tarqatish va qayta sotish huquqi berilmaydi. Ilovada pullik obunalar, ta’lim uchun ommaviy oferta yoki o‘quv markazi bilan avtomatik shartnoma tuzish yo‘q.",
      ],
      [
        "Cheklovlar",
        "Dastur mavjud holatida taqdim etiladi. Demo haqiqiy hisob yuritishga yaroqlilik kafolati bermaydi va operatorning majburiy hujjatlari yoki tartib-taomillarini almashtirmaydi. O‘zbekistonning qo‘llaniladigan majburiy qonun normalari bilan cheklab bo‘lmaydigan huquq va javobgarlik saqlanadi. Haqiqiy ishga tushirish uchun alohida baholash va litsenziya zarur.",
      ],
    ],
    rights: [
      [
        "Muallif va litsenziya",
        "©2026 Pavlovich Aleksandr Kirillovich. Manba kodi tanishish va baholash uchun e’lon qilingan. Ochiq kirish tijoriy joriy etish, boshqalarga berish yoki qayta sotish uchun ruxsat bermaydi. Shartlar LICENSE.txt faylida; bu sahifa qisqa izohdir.",
      ],
      [
        "Boshqa materiallar va AI",
        "Manrope shrifti, Lucide belgilari va dasturiy kutubxonalar o‘z litsenziyalarini saqlaydi. Ishlab chiqishda Codex, rejalashda Astra, tanlangan dizayn maketida Higgsfield ishlatilgan. Hisob yuritishning umumiy g‘oyasi, sinov talablari va boshqa shaxslarning materiallariga mutlaq huquq da’vo qilinmaydi.",
      ],
      [
        "O‘zbekiston va majburiy normalar",
        "Foydalanish va huquqlarni himoya qilish masalalari qo‘llaniladigan qonunchilik, jumladan O‘zbekistonning mualliflik huquqi va turdosh huquqlar to‘g‘risidagi normalari asosida baholanadi. Ochiq kod nusxa olishni texnik jihatdan to‘sib qo‘ymaydi. Ushbu shartlar har bir AI yaratgan elementning huquqiy himoyasini kafolatlamaydi va qonunning majburiy qoidalarini bekor qilmaydi. Ruxsat so‘rash uchun: hello@dobropalm.tech.",
      ],
    ],
  },
  en: {
    privacy: [
      ["Activity and voided records", "To review operations, the application stores timestamps, snapshots of student fields and payment creation or cancellation details, including the reason provided. Deleting a student does not erase earlier activity events; voiding a payment does not erase its original record. Use fictional data only."],
      [
        "Scope and developer",
        "This notice describes the local Vedomost demo, with EU/EEA and US supplements below. The software author is Alexander Kirillovich Pavlovich. The developer is not operating a hosted school service here and does not automatically receive your local ledger entries. Selecting a language selects a notice edition; applicable law depends on actual activities and jurisdiction.",
      ],
      [
        "Data and purpose",
        "The forms accept a student’s name, phone, group, enrollment month, monthly fee, and a payment’s original amount, currency and date. Each payment also stores its UZS equivalent and applied rate details. Use fictional records only in this demo. The browser sends entries to the local server to maintain the ledger and calculate balances. The app does not request card details, identity documents or payment tokens and does not transfer money.",
      ],
      [
        "Storage and retention",
        "Entries remain in SQLite on the computer running the server until that installation’s owner removes them. There is no automatic retention period or cloud sync. The interface prevents deletion of students with payments; that history safeguard is not a legal basis for indefinite retention. A complete data-rights/deletion workflow is not implemented. Server logs may contain network addresses, request paths and response status.",
      ],
      [
        "Cookies, preferences and recipients",
        "The app sets no cookies and includes no advertising trackers or analytics. Browser localStorage holds only theme, language and display-currency preferences under vedomost-theme, vedomost-language and vedomost-currency. You can remove them in browser settings; blocking storage does not prevent the app from working. Fonts, icons and documentation are served locally. The demo does not sell, share for behavioural advertising, or automatically send ledger records to external recipients. To update exchange rates, the server requests public data from the Central Bank of Uzbekistan, or the Bank of Russia if that source is unavailable. These providers receive the server’s network address and HTTP request information, but no student or payment records. Linked third-party sites have their own policies.",
      ],
      [
        "Security and children",
        "Run the demo on loopback address 127.0.0.1. It has no authentication, role controls, database-file encryption or automatic backups. Do not expose it publicly or enter real student information, including children’s information. It is not a production service for collecting children’s data.",
      ],
      [
        "EU/EEA supplement",
        "Where GDPR applies, a real deployment must identify its controller and contact details, purposes and legal bases, recipients and transfers, retention, and the relevant rights and complaint route. Rights may include access, rectification, erasure, restriction, portability, objection and withdrawal of consent where applicable. This demo does not identify an actual school controller or provide those organisational processes; this notice is not a completed Article 13 notice for a production school. Requests about real records must go to the controller operating that installation.",
      ],
      [
        "United States supplement",
        "US requirements vary by state and context; there is no single universal US privacy policy. Where CCPA/CPRA or other applicable state laws apply, the responsible business must provide the required collection notice and request channels. Depending on applicable law, rights may include access, correction, deletion, non-discrimination and opting out of sale/sharing. The demo has no sale, targeted-advertising or profiling functionality. Applicability thresholds, children’s privacy and education-record rules require a deployment-specific assessment.",
      ],
      [
        "Contact and production readiness",
        "For software enquiries contact hello@dobropalm.tech. The developer cannot remotely access or erase records in your local installation. Before using real data, the deploying organisation must supply its legal identity, address, privacy contact, lawful basis, actual retention and safeguards, and arrange compliant request handling. No GDPR, CCPA or worldwide compliance certification is claimed.",
      ],
    ],
    terms: [
      [
        "Purpose",
        "Vedomost is a local demonstration of a payment ledger for reviewing a candidate exercise. Use fictional student and payment records. It records payments already received; it does not transfer money, issue fiscal receipts or prepare financial statements.",
      ],
      [
        "Calculation rules",
        "Charges start in the recorded enrollment month. Tariffs and debt are calculated in UZS. Overpayments do not carry forward; changing a fee also changes past monthly balances. Payments may be entered in UZS, RUB or USD. Each record keeps the original amount and currency, an immutable UZS equivalent, and the applied official rate details. RUB/USD payments require a fresh official server rate; a backdated payment uses the rate available when recorded, not the historical rate for its payment date. Without a fresh rate, foreign-currency payments cannot be recorded; UZS works offline. Amounts are rounded to hundredths using half up. The display-currency switch uses current indicative rates and does not change tariffs or booked payments.",
      ],
      [
        "Permitted use",
        "The public repository permits local inspection and evaluation only within LICENSE.txt. Commercial deployment, redistribution and resale require prior written permission. The app offers no paid subscription, education contract or automatic contract with a school.",
      ],
      [
        "Mandatory rights and limits",
        "The software is provided as is for evaluation, subject to applicable law. These terms do not remove non-waivable consumer, privacy or other statutory rights in the EU/EEA or United States. Availability of source code is not a warranty of fitness for real accounting. A production deployment needs its own legal and operational assessment; this is not a universal choice-of-law or service agreement.",
      ],
    ],
    rights: [
      [
        "Author and licence",
        "©2026 Alexander Kirillovich Pavlovich. Source is available for inspection and evaluation; public access does not grant commercial deployment, redistribution or resale rights. LICENSE.txt contains the source licence. This page is a summary.",
      ],
      [
        "Third-party work and AI",
        "Manrope, Lucide and software dependencies retain their own licences. Codex assisted implementation, Astra assisted planning, and Higgsfield generated the selected visual reference. No exclusive rights are claimed in the general accounting idea, exercise requirements or third-party material.",
      ],
      [
        "EU/US and mandatory law",
        "Ownership and enforceability are subject to applicable copyright law. No claim is made that every AI-generated element is independently protected. This licence does not override statutory rights that cannot lawfully be restricted. Public source can technically be copied; legal terms are not copy protection. For licensing enquiries: hello@dobropalm.tech.",
      ],
    ],
  },
};
