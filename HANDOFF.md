# HANDOFF: 1c-assistant — передача работы другому агенту

> Этот файл — единственный источник правды о состоянии проекта для нового разработчика или агента.
> **ОБЯЗАТЕЛЬНОЕ ПРАВИЛО: после КАЖДОГО коммита обновляй этот файл** (разделы «Текущее состояние», «Журнал изменений», «Следующие шаги»). Коммит, после которого файл не актуален, считается незавершённым. Цель — чтобы любой человек или агент мог продолжить работу, не восстанавливая контекст из истории.

Язык общения с пользователем и документации: **русский**. Код, имена переменных и коммиты: английский.

---

## 1. О проекте

Тема дипломной работы: **«Разработка интеллектуального ассистента для получения управленческой информации из 1С:Предприятие на естественном языке с применением больших языковых моделей»**.

Пользователь (руководитель, финансист, менеджер) пишет вопрос в чат на естественном языке («Выручка за сентябрь по филиалам?»). Система превращает вопрос в запрос к 1С, выполняет его и возвращает текстовый вывод, таблицу и при необходимости график. Под ответом можно раскрыть блок «Как получен ответ» (сформированный запрос, источники).

### Финальная архитектура (целевая)

```
Веб-клиент (чат, графики, история)
        │  Bearer JWT
        ▼
Backend (FastAPI)
  ├─ Auth/RBAC (роли из JWT Keycloak)
  ├─ LLM-оркестратор: понять вопрос → найти метаданные → построить запрос → валидировать → выполнить → сформулировать ответ
  ├─ История и аудит
  └─ Коннектор к 1С (OData или HTTP-сервис, только чтение)
        │                         │
        ▼                         ▼
   PostgreSQL (+pgvector)      1С:Предприятие
   профили, чаты, каталог      (учебная версия, демо-база)
   метаданных 1С, аудит
        ▲
        │
   LLM-провайдер (облачный API или локальная модель через Ollama), абстракция провайдера
```

Ключевые идеи для будущих этапов:
- **Каталог метаданных 1С** с эмбеддингами (pgvector): в контекст LLM попадает только релевантная часть схемы (RAG по метаданным).
- Две стратегии оркестратора для сравнения в дипломе: **Text-to-Query** (модель пишет запрос) и **Function calling** (модель выбирает готовую функцию вроде `get_sales(period, group_by)`).
- **Валидатор запросов**: только чтение, права по роли, ограничение тяжести; при ошибке — self-correction, 1–2 попытки.
- **Аудит и оценки 👍/👎** для метрик качества в главе с экспериментами.
- Сравнение 2–3 LLM по точности на наборе тестовых вопросов.

---

## 2. Принятые решения (не пересматривать без согласования с пользователем)

| Решение | Выбор | Причина |
|---|---|---|
| Тип приложения | Веб-приложение | Практично, подходит для корпоративной среды |
| Backend | **Python, FastAPI**, SQLAlchemy 2, Alembic | Основная экосистема LLM — Python; async удобен для стриминга |
| Frontend | **React + Vite + TypeScript** | Разделение фронта и API |
| Авторизация | **Keycloak** (OIDC, Authorization Code + PKCE) | Корпоративный стандарт, SSO, AD/LDAP, роли в токене |
| БД | **PostgreSQL 16**, две отдельные БД: для Keycloak и для приложения | Не смешивать схемы |
| Окружение | **Всё собирается и запускается в Docker Compose** | Воспроизводимость одной командой |
| Таблицы Keycloak | Создаются самим Keycloak автоматически | Вручную не создавать |
| Таблицы приложения | Через Alembic, `alembic upgrade head` при старте backend | — |
| Настройка Keycloak | Через `realm-export.json` с автоимпортом (`--import-realm`) | Без ручной настройки в консоли |

Не использовать: Streamlit/Gradio (слабые авторизация и роли), Telegram-бот как основной интерфейс (возможен позже как дополнительный канал).

---

## 3. Цель текущего этапа: MVP «Keycloak + приветственная страница + БД»

Только инфраструктура, авторизация и приветственная страница. **Чата, LLM и подключения к 1С в MVP нет.**

### Критерии готовности MVP

После `docker compose up --build` в корне проекта:

1. `http://localhost:3000` — главная. Не вошли → кнопка «Войти», редирект на страницу входа Keycloak.
2. После входа (`analyst1` / `analyst1`) — приветственная страница: «Здравствуйте, <имя>», роль, e-mail, заглушка «Здесь будет чат с ассистентом 1С».
3. Профиль приходит из backend `GET /api/me`: backend проверяет JWT, создаёт/обновляет запись в `user_profiles`, возвращает профиль.
4. Кнопка «Выйти» завершает сессию в Keycloak.
5. `http://localhost:8000/docs` — Swagger backend.
6. Страница `/admin` доступна только роли `admin`; остальным — «Нет доступа». Backend `GET /api/admin/ping` отдаёт 403 не-админам.
7. Вход пишется в `audit_log`.

### Сервисы Docker Compose

| Сервис | Технология | Порт |
|---|---|---|
| `keycloak-db` | PostgreSQL 16, healthcheck, volume | — |
| `keycloak` | Keycloak 26, `start-dev --import-realm`, `depends_on: keycloak-db (service_healthy)` | 8080 |
| `app-db` | PostgreSQL 16, healthcheck, volume | — |
| `backend` | FastAPI + Alembic, `depends_on: app-db (service_healthy)` и keycloak | 8000 |
| `frontend` | React (Vite build) → nginx | 3000 |

Пример блока Keycloak:

```yaml
keycloak:
  image: quay.io/keycloak/keycloak:26.0
  command: start-dev --import-realm
  environment:
    KC_DB: postgres
    KC_DB_URL: jdbc:postgresql://keycloak-db:5432/keycloak
    KC_DB_USERNAME: keycloak
    KC_DB_PASSWORD: keycloak
    KEYCLOAK_ADMIN: admin
    KEYCLOAK_ADMIN_PASSWORD: admin
  volumes:
    - ./keycloak/realm-export.json:/opt/keycloak/data/import/realm.json
  depends_on:
    keycloak-db:
      condition: service_healthy
```

### Keycloak (realm `assistant`)

- Клиент `assistant-web`: публичный, Authorization Code + PKCE, redirect URI `http://localhost:3000/*`, web origins `http://localhost:3000`.
- Realm-роли: `admin`, `analyst`, `manager`.
- Тестовые пользователи (только для локальной разработки, пароль = логин): `admin1` (admin), `analyst1` (analyst), `manager1` (manager). Заполнить имя, фамилию, e-mail.
- Роли должны попадать в access token (`realm_access.roles`). Проверить mapper.
- **Нюанс сети Docker**: браузер ходит в Keycloak по `http://localhost:8080`, а backend внутри сети — по `http://keycloak:8080`. Claim `iss` в токене будет `http://localhost:8080/realms/assistant`. Backend должен проверять issuer по **внешнему** адресу (переменная окружения), а JWKS брать по **внутреннему**. Для этого задать `KC_HOSTNAME`/`KC_HOSTNAME_URL` или конфигурируемые `OIDC_ISSUER` и `OIDC_JWKS_URL`.

### Backend

- Зависимость `get_current_user`: проверка подписи по JWKS Keycloak (`authlib` или `python-jose`), срока действия, issuer; извлечение `sub`, `preferred_username`, `email`, `name`, роли.
- Зависимость `require_role("admin")`.
- Эндпоинты: `GET /api/health`, `GET /api/me`, `GET /api/admin/ping`.
- Модели и первая миграция Alembic (применяется при старте контейнера): `user_profiles`, `infobases`, `chat_sessions`, `messages`, `audit_log`.
- CORS для `http://localhost:3000`.

### Схема БД приложения (таблицы под будущее создаются сразу)

```
user_profiles  (id, keycloak_sub UNIQUE, username, email, full_name, last_login_at, created_at)
infobases      (id, name, odata_url, login, is_active, created_at)      -- подключения к 1С, в MVP пусто
chat_sessions  (id, user_id → user_profiles, title, created_at)          -- в MVP пусто
messages       (id, session_id, role[user/assistant], content, generated_query, created_at)  -- в MVP пусто
audit_log      (id, user_id, action, payload JSONB, created_at)
```

Пароли в БД приложения не хранятся: пользователями и паролями владеет Keycloak.

### Frontend

- `keycloak-js`, init с `onLoad: 'check-sso'` / `login-required`, PKCE S256.
- Страницы: приветственная, `/admin` (проверка роли), обработка «нет доступа».
- axios с Bearer-токеном и автообновлением (`updateToken`).
- Конфиг Keycloak (url, realm, clientId) — через переменные окружения/`config.js` на этапе сборки.

### Структура репозитория (целевая)

```
1c-assistant/
├─ HANDOFF.md                 ← этот файл
├─ README.md                  ← запуск, логины, схема, структура (на русском)
├─ docker-compose.yml
├─ .env.example
├─ .gitignore
├─ keycloak/realm-export.json
├─ backend/
│  ├─ Dockerfile
│  ├─ requirements.txt (или pyproject.toml)
│  ├─ alembic.ini, alembic/
│  └─ app/ (main.py, config.py, db.py, models.py, auth.py, routers/)
└─ frontend/
   ├─ Dockerfile, nginx.conf
   ├─ package.json, vite.config.ts
   └─ src/
```

### План проверки (обязательно перед тем как считать этап готовым)

1. `docker compose up --build`, дождаться healthy всех сервисов.
2. Получить токены трёх пользователей (password grant временно включить для проверки или использовать curl по flow) и проверить: `/api/me` у всех возвращает 200; `/api/admin/ping` — 200 для `admin1`, 403 для `analyst1` и `manager1`; без токена — 401.
3. Пройти вход в браузере (встроенный браузер приложения), проверить приветственную страницу, выход, `/admin`.
4. Убедиться, что записи появились в `user_profiles` и `audit_log`.
5. Проверить, что после `docker compose down` + `up` (без `-v`) пользователи и данные сохранились.
6. Если что-то не работает — исправить, а не оставлять как есть. Результаты проверки честно записать в журнал ниже.

---

## 4. Текущее состояние

**Дата актуальности: 2026-10-11.**

- **MVP реализован и проверен** (код в репозитории, коммит `feat: MVP ...`). Все критерии раздела 3 выполнены.
- Работа ведётся на **Linux (Arch)**, проект: `~/myProjects/1c-assistant`. Docker 29 и Git есть, Node на хосте нет (не нужен).
- Порт 8000 на этой машине занят чужим контейнером (`sms-sender-api`), поэтому в локальном `.env` `BACKEND_PORT=8010` (в `.env.example` по умолчанию 8000). Backend: http://localhost:8010, Swagger: `/docs`.
- Решения по реализации: PyJWT + `PyJWKClient` (вместо authlib/jose), синхронный SQLAlchemy + psycopg3; вход в `audit_log` пишется один раз на сессию Keycloak (`sid`) при первом `GET /api/me`; у клиента `assistant-web` password grant выключен (при проверке включался временно через admin API и возвращён).
- Хост-раздел про Windows/PowerShell выше устарел и сохранён лишь как история.

## 5. Следующие шаги (по порядку)

MVP закрыт. Дальше — только по запросу пользователя, см. дорожную карту (раздел 6). Первый пункт: чат (`chat_sessions`/`messages`, UI, стриминг).

## 6. Дорожная карта после MVP (не делать без запроса пользователя)

1. Чат: таблицы `chat_sessions`/`messages`, UI чата, стриминг ответов.
2. Абстракция LLM-провайдера, первый провайдер.
3. Подключение к 1С (учебная платформа, демо-база «Управление торговлей», публикация OData на Apache/IIS, права только на чтение), модель `infobases`.
4. Каталог метаданных + pgvector + RAG по метаданным.
5. Оркестратор (Text-to-Query и Function calling), валидатор, self-correction.
6. Таблицы и графики в ответах, выгрузка в Excel, блок «Как получен ответ».
7. Аудит, оценки 👍/👎, тестовый набор вопросов и сравнение моделей для главы «Эксперименты».
8. Production-настройки: HTTPS, Keycloak в режиме `start`, секреты вне репозитория.

---

## 7. Правила работы с проектом

- **Обновлять этот файл после каждого коммита** (см. шапку).
- Секреты не коммитить: реальные значения только в `.env`, в репозитории `.env.example`. Тестовые пароли из realm-экспорта допустимы только для локальной разработки, отметить это в README.
- Не хранить пароли пользователей в БД приложения.
- Подключение к 1С только на чтение.
- Любое изменение уже принятых решений (раздел 2) согласовывать с пользователем.
- Не выполнять разрушающие действия (`docker compose down -v`, удаление volumes, `git reset --hard`) без явного разрешения пользователя: потеряются данные Keycloak.
- Коммиты небольшие и осмысленные, сообщения на английском, в стиле `feat:`, `fix:`, `docs:`, `chore:`.

---

## 8. Журнал изменений

| Дата | Коммит | Что сделано | Проверено |
|---|---|---|---|
| 2026-10-11 | — | Создан HANDOFF.md с планом и состоянием окружения. Кода нет. | — |
| 2026-10-11 | feat: MVP | Каркас: docker-compose, Keycloak realm, backend (JWT, RBAC, модели, миграция 0001), frontend (вход, профиль, /admin), README. | `/api/me` 200 у трёх ролей; `/api/admin/ping` 200 для admin1, 403 для analyst1/manager1, 401 без токена; вход/выход/`/admin` («Нет доступа» для analyst1) в браузере; записи в `user_profiles` и `audit_log` есть, повторный `/api/me` не дублирует аудит; `down`+`up` без `-v` данные сохраняет. |
| 2026-10-11 | style: frontend | Оформление фронтенда: `frontend/src/styles.css` (светлая/тёмная тема), шапка с навигацией, карточки, бейджи ролей, экран входа. Первая версия была без стилей — недоработка. | Визуально в браузере (экран входа, тёмная тема); сборка в Docker успешна. |
| 2026-10-11 | style: leetcode-like UI | Редизайн в духе LeetCode: компактная шапка, нейтральные панели, акцент оранжевый, профиль слева + рабочая область справа, список примеров вопросов, живой русский текст без «ИИ-шного» центрирования. Тёмная/светлая тема. | Браузер: экран входа, главная и `/admin` под `admin1` (тёмная тема). |
| 2026-10-11 | feat: single entrypoint | Единая точка входа через nginx фронтенда (`/api`, `/auth`), Keycloak на `/auth` (`KC_HTTP_RELATIVE_PATH`), `PUBLIC_URL` в `.env`; наружу один туннель ngrok (бесплатный тариф даёт один домен, три туннеля не годятся). `/auth/admin` и master-realm закрыты (403). В БД Keycloak локально: добавлен публичный redirect URI, пароли тестовых пользователей и консоли админа заменены на случайные (лежат в `.local/ACCESS.txt`, вне git; `.env` с `PUBLIC_URL` тоже вне git). | Через публичный URL: фронт 200, `/api/health` 200, `/auth/realms/assistant` 200, `/auth/admin` 403, кнопка «Войти» ведёт на форму Keycloak. Вход под пользователем через публичный адрес не проверялся. |
| 2026-10-11 | docs: report | Отчёт для преподавателя `docs/Otchet_1c-assistant_IT1-2317.docx` (титульный лист IITU, инструменты, реализация, скриншоты, проверки); генератор `docs/build_report.js` (docx@9, запускается в контейнере node:20-alpine; скриншоты в `.local/shots`, вне git). | Документ отрендерен в PDF через LibreOffice, 10 страниц, проверен визуально. |

