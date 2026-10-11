const fs = require('fs');
const path = require('path');
const {
  Document, Packer, Paragraph, TextRun, ImageRun, Table, TableRow, TableCell, WidthType, ShadingType,
  AlignmentType, HeadingLevel, BorderStyle, LevelFormat, PageBreak, Footer, PageNumber,
} = require('docx');

const SHOTS = path.join(__dirname, '..', '.local', 'shots');
const FONT = 'Times New Roman';
const W = 9356; // ширина текста, DXA
const GRAY = 'D9D9D9';

const p = (text, o = {}) => new Paragraph({
  alignment: o.align ?? AlignmentType.JUSTIFIED,
  spacing: { after: o.after ?? 120, line: 340 },
  indent: o.noIndent ? undefined : { firstLine: 567 },
  children: [].concat(text).map((t) => typeof t === 'string' ? new TextRun({ text: t, ...(o.run || {}) }) : t),
});
const b = (t) => new TextRun({ text: t, bold: true });
const code = (t) => new TextRun({ text: t, font: 'Courier New', size: 22 });
const h1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(t)] });
const h2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(t)] });
const bullet = (t) => new Paragraph({
  numbering: { reference: 'bul', level: 0 }, alignment: AlignmentType.JUSTIFIED, spacing: { after: 60, line: 320 },
  children: [].concat(t).map((x) => typeof x === 'string' ? new TextRun(x) : x),
});
const center = (t, o = {}) => new Paragraph({
  alignment: AlignmentType.CENTER, spacing: { after: o.after ?? 120 },
  children: [new TextRun({ text: t, bold: o.bold, size: o.size, allCaps: o.caps })],
});

const border = { style: BorderStyle.SINGLE, size: 4, color: '808080' };
const borders = { top: border, bottom: border, left: border, right: border };
function table(cols, header, rows) {
  const cell = (txt, w, head) => new TableCell({
    borders, width: { size: w, type: WidthType.DXA },
    shading: head ? { fill: GRAY, type: ShadingType.CLEAR, color: 'auto' } : undefined,
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
    children: [new Paragraph({ spacing: { after: 0 }, children: [new TextRun({ text: txt, bold: head, size: 22 })] })],
  });
  return new Table({
    width: { size: W, type: WidthType.DXA }, columnWidths: cols,
    rows: [new TableRow({ tableHeader: true, children: header.map((h, i) => cell(h, cols[i], true)) }),
      ...rows.map((r) => new TableRow({ cantSplit: true, children: r.map((c, i) => cell(c, cols[i], false)) }))],
  });
}
const SIZES = { 'c-01-landing.jpg': [1180, 494], 'c-02-keycloak-login.jpg': [1180, 704], 'c-03-home.jpg': [1180, 428], 'c-04-admin.jpg': [1180, 164], 'c-05-swagger.jpg': [1180, 468] };
let figN = 0;
function figure(file, caption, w = 560) {
  const buf = fs.readFileSync(path.join(SHOTS, file));
  const [iw, ih] = SIZES[file];
  figN++;
  return [
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 120, after: 60 }, keepNext: true,
      children: [new ImageRun({ type: 'jpg', data: buf, transformation: { width: w, height: Math.round(w * ih / iw) },
        altText: { title: caption, description: caption, name: file } })] }),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 },
      children: [new TextRun({ text: `Рисунок ${figN} — ${caption}`, italics: true, size: 22 })] }),
  ];
}
const spacer = (n = 1) => Array.from({ length: n }, () => new Paragraph({ children: [] }));

// ---------- Титульный лист ----------
const title = [
  center('Международный университет информационных технологий', { bold: true, size: 28 }),
  center('International Information Technology University (IITU)', { bold: true, size: 28, after: 1800 }),
  center('ОТЧЁТ', { bold: true, size: 36, after: 240 }),
  center('по проекту', { size: 28, after: 240 }),
  center('«Разработка интеллектуального ассистента для получения управленческой информации из 1С:Предприятие на естественном языке с применением больших языковых моделей»', { bold: true, size: 28, after: 240 }),
  center('Этап 1: MVP — авторизация (Keycloak), приветственная страница и база данных', { size: 26, after: 2200 }),
  new Paragraph({ indent: { left: 4800 }, spacing: { after: 120 }, children: [b('Выполнили студенты:')] }),
  new Paragraph({ indent: { left: 4800 }, spacing: { after: 0 }, children: [new TextRun('Мырзакулов Сырым')] }),
  new Paragraph({ indent: { left: 4800 }, spacing: { after: 120 }, children: [new TextRun('Конратов Сагынтай')] }),
  new Paragraph({ indent: { left: 4800 }, spacing: { after: 360 }, children: [b('Группа: '), new TextRun('IT1-2317')] }),
  new Paragraph({ indent: { left: 4800 }, spacing: { after: 1500 }, children: [b('Преподаватель: '), new TextRun('______________________')] }),
  center('Алматы, 2026', { size: 26 }),
  new Paragraph({ children: [new PageBreak()] }),
];

// ---------- Содержание ----------
const toc = [
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 240 }, children: [new TextRun({ text: 'СОДЕРЖАНИЕ', bold: true, size: 28 })] }),
  ...['1. Цель и задачи проекта', '2. Архитектура решения', '3. Используемые инструменты и технологии',
    '4. Реализация', '5. Результаты и тестирование', '6. Доступ извне (демонстрация второму разработчику)',
    '7. Возникшие проблемы и их решение', '8. Дальнейшие шаги', 'Заключение']
    .map((t) => new Paragraph({ spacing: { after: 100 }, indent: { left: 567 }, children: [new TextRun({ text: t, size: 26 })] })),
  new Paragraph({ children: [new PageBreak()] }),
];

// ---------- Основная часть ----------
const body = [
  h1('1. Цель и задачи проекта'),
  p('Тема работы — интеллектуальный ассистент, который позволяет руководителю, финансисту или менеджеру задать вопрос к данным 1С:Предприятие обычным языком (например, «Выручка за сентябрь по филиалам?»), а в ответ получить текст, таблицу и при необходимости график. Система должна превращать вопрос в запрос к 1С с помощью большой языковой модели (LLM), выполнять его только на чтение и показывать, как именно получен ответ.'),
  p('Проект разбит на этапы. Данный отчёт описывает первый этап — MVP-инфраструктуру. Чат, LLM и подключение к 1С на этом этапе намеренно не реализуются: сначала нужен надёжный фундамент — авторизация, роли, база данных и воспроизводимое окружение.'),
  p('Задачи первого этапа:', { noIndent: true }),
  bullet('развернуть всё окружение одной командой (Docker Compose);'),
  bullet('настроить сервер авторизации Keycloak с ролями admin, analyst, manager;'),
  bullet('реализовать backend с проверкой JWT-токена и ограничением доступа по ролям;'),
  bullet('создать схему базы данных приложения (профили, чаты, сообщения, подключения к 1С, журнал аудита);'),
  bullet('сделать веб-клиент: вход, приветственная страница с профилем, страница администратора;'),
  bullet('записывать входы пользователей в журнал аудита.'),

  h1('2. Архитектура решения'),
  p('Система состоит из пяти контейнеров, объединённых в один файл docker-compose.yml. Единой точкой входа для пользователя служит веб-сервер nginx, который отдаёт готовый фронтенд и проксирует запросы: адреса, начинающиеся с /api, уходят в backend, а адреса /auth — в Keycloak. Благодаря этому браузер работает с одним адресом и не возникает проблем с CORS.'),
  table([2100, 2500, 4756], ['Сервис', 'Технология', 'Назначение'], [
    ['frontend', 'React + Vite → nginx', 'Веб-интерфейс; единая точка входа (порт 3000)'],
    ['backend', 'FastAPI (Python 3.12)', 'REST API, проверка JWT, роли, работа с БД, аудит'],
    ['keycloak', 'Keycloak 26', 'Аутентификация пользователей (OIDC), роли, выдача токенов'],
    ['keycloak-db', 'PostgreSQL 16', 'Служебная БД Keycloak (таблицы создаёт сам Keycloak)'],
    ['app-db', 'PostgreSQL 16', 'БД приложения (таблицы создаёт Alembic)'],
  ]),
  ...spacer(),
  p('Последовательность входа: пользователь нажимает «Войти» → браузер перенаправляется на страницу Keycloak → после ввода логина и пароля Keycloak возвращает код авторизации → фронтенд обменивает его на токен (Authorization Code Flow с PKCE) → при каждом запросе к API токен передаётся в заголовке Authorization: Bearer → backend проверяет подпись токена по открытым ключам Keycloak (JWKS), срок действия и издателя, достаёт роли и обрабатывает запрос.'),
  p('Пароли пользователей хранятся только в Keycloak. В базе приложения паролей нет — там лежат лишь профили, привязанные к идентификатору пользователя из Keycloak.'),

  h1('3. Используемые инструменты и технологии'),
  table([2200, 1700, 5456], ['Инструмент', 'Версия', 'Назначение и обоснование выбора'], [
    ['Docker, Docker Compose', '29 / 5', 'Сборка и запуск всех сервисов одной командой; воспроизводимость окружения на любой машине'],
    ['Keycloak', '26.0', 'Готовый сервер авторизации (OIDC, SSO, роли, возможная интеграция с AD/LDAP); не нужно писать свою систему паролей'],
    ['PostgreSQL', '16', 'Надёжная реляционная БД; в дальнейшем — расширение pgvector для поиска по метаданным 1С'],
    ['Python', '3.12', 'Основная экосистема для работы с LLM'],
    ['FastAPI', '0.115', 'Современный быстрый веб-фреймворк, автоматическая документация Swagger, поддержка асинхронности (пригодится для потоковых ответов)'],
    ['SQLAlchemy', '2.0', 'ORM для работы с БД из Python'],
    ['Alembic', '1.14', 'Миграции схемы БД; применяются автоматически при старте backend'],
    ['PyJWT', '2.10', 'Проверка подписи и claims JWT-токена, загрузка ключей JWKS'],
    ['React + TypeScript', '18.3 / 5.6', 'Компонентный веб-интерфейс со статической типизацией'],
    ['Vite', '5.4', 'Быстрая сборка фронтенда'],
    ['keycloak-js', '26', 'Клиентская библиотека входа через Keycloak (PKCE S256)'],
    ['axios', '1.7', 'HTTP-клиент; автоматически подставляет и обновляет токен'],
    ['nginx', '1.27', 'Раздача статики и обратный прокси для /api и /auth'],
    ['ngrok', '3.39', 'Временный публичный адрес для показа приложения другому разработчику'],
    ['Git', '—', 'Контроль версий; небольшие коммиты в стиле feat/fix/docs/style'],
    ['Claude Code', '—', 'ИИ-помощник разработчика, использован при написании кода и документации'],
  ]),
  ...spacer(),
  p('Альтернативы, которые рассматривались и не были выбраны: Streamlit и Gradio (слабая авторизация и ролевая модель), Telegram-бот как основной интерфейс (возможен позже как дополнительный канал).'),

  h1('4. Реализация'),
  h2('4.1. Keycloak'),
  p('Настройка Keycloak полностью описана в файле keycloak/realm-export.json и импортируется автоматически при первом старте (ключ --import-realm). Ручная настройка в консоли не требуется. В файле заданы:'),
  bullet('область (realm) assistant;'),
  bullet('публичный клиент assistant-web с потоком Authorization Code и обязательным PKCE (S256);'),
  bullet('роли admin, analyst, manager; они добавляются в токен в claim realm_access.roles с помощью protocol mapper;'),
  bullet('тестовые пользователи admin1, analyst1, manager1 (только для локальной разработки).'),
  p('Особенность Docker-сети: браузер обращается к Keycloak по внешнему адресу, а backend — по внутреннему имени keycloak. Поэтому поле iss в токене содержит внешний адрес, и backend проверяет издателя по нему (переменная OIDC_ISSUER), а ключи подписи берёт по внутреннему адресу (OIDC_JWKS_URL).'),

  h2('4.2. База данных приложения'),
  p('Таблицы создаются миграцией Alembic при старте backend. Таблицы под будущие этапы созданы сразу, чтобы не менять схему позже.'),
  table([2300, 7056], ['Таблица', 'Содержимое'], [
    ['user_profiles', 'Профиль пользователя: идентификатор из Keycloak (sub), логин, e-mail, имя, время последнего входа'],
    ['infobases', 'Подключения к базам 1С (название, адрес OData, логин, признак активности). На этапе MVP пуста'],
    ['chat_sessions', 'Диалоги пользователей. На этапе MVP пуста'],
    ['messages', 'Сообщения диалога: роль, текст, сформированный запрос. На этапе MVP пуста'],
    ['audit_log', 'Журнал аудита: пользователь, действие, данные в формате JSONB, время'],
  ]),
  ...spacer(),

  h2('4.3. Backend'),
  p('Backend написан на FastAPI. Зависимость get_current_user проверяет токен, зависимость require_role("admin") ограничивает доступ по роли. Реализованы эндпоинты:'),
  table([2800, 2200, 4356], ['Эндпоинт', 'Доступ', 'Описание'], [
    ['GET /api/health', 'всем', 'Проверка работоспособности'],
    ['GET /api/me', 'любой вошедший', 'Возвращает профиль; создаёт или обновляет запись в user_profiles; при первом обращении в рамках сессии Keycloak пишет вход в audit_log'],
    ['GET /api/admin/ping', 'только admin', 'Проверка ролевого доступа: остальным возвращает 403'],
  ]),
  ...spacer(),
  p('Вход записывается в аудит один раз на сессию Keycloak (по идентификатору sid), поэтому повторные запросы /api/me не создают дубликатов.'),

  h2('4.4. Frontend'),
  p('Веб-клиент написан на React и TypeScript. Страницы: главная (экран входа для неавторизованных, профиль и заготовка чата для вошедших) и страница администрирования, доступная только роли admin. Интерфейс оформлен в светлой и тёмной теме, переключаемой автоматически по настройкам системы, и выполнен по образцу компактных профессиональных платформ: панель профиля слева, рабочая область справа, список примеров вопросов.'),

  h1('5. Результаты и тестирование'),
  h2('5.1. Интерфейс'),
  p('Неавторизованный пользователь видит приветствие и кнопку «Войти». Ниже показаны примеры вопросов, которые ассистент сможет разбирать.'),
  ...figure('c-01-landing.jpg', 'Главная страница до входа'),
  p('После нажатия на кнопку происходит перенаправление на страницу входа Keycloak.'),
  ...figure('c-02-keycloak-login.jpg', 'Страница входа Keycloak (realm assistant)', 480),
  p('После успешного входа показывается страница профиля: имя, роль, e-mail и время последнего входа берутся из ответа backend (/api/me).'),
  ...figure('c-03-home.jpg', 'Главная страница после входа (пользователь с ролью admin)'),
  p('Пользователю с ролью admin доступна страница администрирования, которая обращается к защищённому эндпоинту /api/admin/ping. Остальные роли видят сообщение «Нет доступа».'),
  ...figure('c-04-admin.jpg', 'Страница администрирования'),
  h2('5.2. Документация API'),
  p('Swagger-документация генерируется FastAPI автоматически и доступна по адресу /docs backend.'),
  ...figure('c-05-swagger.jpg', 'Swagger UI backend'),
  h2('5.3. Проверка ролей и защиты API'),
  p('Токены трёх тестовых пользователей были получены от Keycloak и использованы для обращения к API. Результаты:'),
  table([2900, 2000, 2000, 2456], ['Пользователь / запрос', 'GET /api/me', 'GET /api/admin/ping', 'Ожидание'], [
    ['admin1 (admin)', '200', '200', 'выполнено'],
    ['analyst1 (analyst)', '200', '403', 'выполнено'],
    ['manager1 (manager)', '200', '403', 'выполнено'],
    ['без токена', '401', '—', 'выполнено'],
  ]),
  ...spacer(),
  h2('5.4. Проверка базы данных и устойчивости'),
  bullet('После входа пользователей в user_profiles появились записи для admin1, analyst1 и manager1, в audit_log — записи о входах (action = login, в payload сохраняются sid сессии и роли).'),
  bullet('Повторное обращение к /api/me в рамках той же сессии новых записей в аудит не добавляет.'),
  bullet('После остановки и повторного запуска (docker compose down и up без удаления томов) пользователи Keycloak и данные приложения сохранились.'),
  bullet('Вход, выход и страница /admin проверены в браузере; для роли analyst страница /admin показывает «Нет доступа».'),

  h1('6. Доступ извне (демонстрация второму разработчику)'),
  p('Чтобы второй разработчик смог попробовать приложение, оно было опубликовано через ngrok. Бесплатный тариф ngrok выдаёт только один домен, поэтому три отдельных туннеля (фронтенд, Keycloak, backend) использовать нельзя: запросы распределялись бы между ними случайно. Решение — единая точка входа на nginx: наружу открыт один порт 3000, а Keycloak и API доступны по путям /auth и /api.'),
  p('Меры безопасности: пароли тестовых пользователей и администратора Keycloak заменены на случайные; консоль администратора и master-realm Keycloak закрыты на уровне nginx (ответ 403) и доступны только локально; файлы с паролями и адресами исключены из репозитория (.gitignore). Страница-предупреждение ngrok показывается один раз каждому посетителю.'),

  h1('7. Возникшие проблемы и их решение'),
  table([3300, 6056], ['Проблема', 'Решение'], [
    ['Порт 8000 на машине разработчика занят другим контейнером', 'Порт backend на хосте вынесен в переменную BACKEND_PORT (в локальной среде 8010); чужой контейнер не затрагивался'],
    ['Alembic не находил пакет app при старте контейнера', 'В Dockerfile добавлена переменная окружения PYTHONPATH=/srv'],
    ['Issuer токена не совпадал при работе в Docker-сети', 'Issuer проверяется по внешнему адресу, ключи JWKS берутся по внутреннему'],
    ['Бесплатный ngrok даёт один домен', 'Единая точка входа через nginx: /api → backend, /auth → Keycloak'],
    ['Первая версия интерфейса была без оформления', 'Добавлены стили, светлая и тёмная темы, интерфейс переработан'],
  ]),
  ...spacer(),

  h1('8. Дальнейшие шаги'),
  bullet('Чат: хранение диалогов и сообщений, интерфейс чата, потоковый вывод ответа.'),
  bullet('Абстракция LLM-провайдера (облачный API или локальная модель) и первый провайдер.'),
  bullet('Подключение к 1С (учебная версия, демо-база, публикация OData, права только на чтение).'),
  bullet('Каталог метаданных 1С с векторным поиском (pgvector): в запрос к модели попадает только релевантная часть схемы.'),
  bullet('Оркестратор в двух вариантах (генерация запроса и вызов готовых функций), валидатор запросов и самокоррекция при ошибках.'),
  bullet('Таблицы и графики в ответах, выгрузка в Excel, блок «Как получен ответ».'),
  bullet('Оценки ответов, тестовый набор вопросов и сравнение нескольких моделей для раздела экспериментов.'),
  bullet('Подготовка к промышленной эксплуатации: HTTPS, Keycloak в режиме production, хранение секретов вне репозитория.'),

  h1('Заключение'),
  p('В результате первого этапа создана рабочая основа будущего ассистента: все сервисы поднимаются одной командой, авторизация и ролевой доступ работают через Keycloak и проверяются на стороне backend, схема базы данных подготовлена под последующие этапы, входы пользователей фиксируются в журнале аудита, а веб-клиент имеет законченный интерфейс. Исходный код находится в локальном Git-репозитории проекта, текущее состояние и план дальнейшей работы зафиксированы в файле HANDOFF.md, инструкция по запуску — в README.md.'),
];

const doc = new Document({
  creator: 'Мырзакулов Сырым, Конратов Сагынтай',
  title: 'Отчёт: ассистент 1С — этап 1 (MVP)',
  styles: {
    default: { document: { run: { font: FONT, size: 24 } } },
    paragraphStyles: [
      { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 28, bold: true, font: FONT }, paragraph: { spacing: { before: 360, after: 160 }, outlineLevel: 0, keepNext: true } },
      { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 26, bold: true, font: FONT }, paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 1, keepNext: true } },
    ],
  },
  numbering: { config: [{ reference: 'bul', levels: [{ level: 0, format: LevelFormat.BULLET, text: '–', alignment: AlignmentType.LEFT,
    style: { paragraph: { indent: { left: 1000, hanging: 360 } } } }] }] },
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1134, bottom: 1134, left: 1700, right: 850 }, pageNumbers: { start: 1 } }, titlePage: true },
    footers: {
      default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ children: [PageNumber.CURRENT] })] })] }),
      first: new Footer({ children: [new Paragraph({ children: [] })] }),
    },
    children: [...title, ...toc, ...body],
  }],
});
Packer.toBuffer(doc).then((buf) => { fs.writeFileSync(path.join(__dirname, 'Otchet_1c-assistant_IT1-2317.docx'), buf); console.log('ok'); });
