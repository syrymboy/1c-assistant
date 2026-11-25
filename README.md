# Ассистент 1С (MVP: Keycloak + приветственная страница + БД)

Дипломный проект: интеллектуальный ассистент для получения управленческой информации из 1С на естественном языке. Подробности и план — в [HANDOFF.md](HANDOFF.md).

## Запуск

```bash
cp .env.example .env   # при необходимости поправить порты
docker compose up --build
```

| Адрес | Что |
|---|---|
| http://localhost:3000 | веб-клиент |
| http://localhost:8000/docs | Swagger backend (порт задаётся `BACKEND_PORT` в `.env`) |
| http://localhost:3000/auth | Keycloak через единый вход (консоль админа — только напрямую: http://localhost:8080/auth, `admin` / `admin`) |

## Доступ снаружи (ngrok)

Фронтенд-nginx — единая точка входа: `/` — приложение, `/api` — backend, `/auth` — Keycloak (консоль и master-realm по этому пути закрыты, 403). Наружу нужен один туннель:

```bash
# в .env: PUBLIC_URL=https://<ваш-домен>.ngrok-free.dev
docker compose up --build -d
ngrok http 3000 --url=$PUBLIC_URL
```

Адрес `PUBLIC_URL` нужно добавить в Valid redirect URIs / Web origins клиента `assistant-web` (realm-файл читается только при первом старте) и сменить тестовые пароли. Бесплатный ngrok один раз показывает страницу-предупреждение.

Если порт 8000 занят, задайте в `.env` другой `BACKEND_PORT` (меняется только прямой порт backend, фронтенд ходит через `/api`).

## Тестовые пользователи (только для локальной разработки!)

| Логин / пароль | Роль |
|---|---|
| `admin1` / `admin1` | admin |
| `analyst1` / `analyst1` | analyst |
| `manager1` / `manager1` | manager |

## Эндпоинты backend

- `GET /api/health` — проверка живости
- `GET /api/me` — профиль (создаёт/обновляет `user_profiles`, пишет вход в `audit_log`)
- `GET /api/admin/ping` — только роль `admin`, иначе 403
- `GET/POST /api/chats`, `GET/DELETE /api/chats/{id}` — диалоги пользователя
- `GET /api/sources`, `PUT /api/sources/{id}` — каталог объектов 1С, доступных роли, и выбор пользователя (демо-каталог)
- `GET /api/billing`, `POST /api/billing/checkout|cancel|resume`, `GET /api/billing/payments/{id}` — тариф, лимит, оплата (тестовый режим)
- `POST /api/webhooks/payments` — вебхук провайдера (подпись HMAC, заголовок `X-Signature: t=<unix>,v1=<hex>`)
- `/api/psp/*` — симулятор платёжного провайдера
- `POST /api/chats/{id}/messages` — вопрос; ответ приходит потоком SSE. Провайдер задаётся `LLM_PROVIDER` (`mock` по умолчанию или `anthropic` + `ANTHROPIC_API_KEY`)

## Оплата (тестовый режим)

Деньги не списываются. Страница оплаты принимает только тестовые карты (срок — любой будущий, CVC — любые 3 цифры):

| Номер | Результат |
|---|---|
| `4242 4242 4242 4242` | успешно |
| `4000 0027 6000 3184` | требуется подтверждение 3-D Secure |
| `4000 0000 0000 0002` | отказ банка |
| `4000 0000 0000 9995` | недостаточно средств |

## Структура

```
keycloak/realm-export.json   realm, клиент assistant-web, роли, пользователи (автоимпорт)
backend/                     FastAPI, SQLAlchemy, Alembic (миграции при старте)
frontend/                    React + Vite + TS → nginx
```

Issuer токена проверяется по внешнему адресу (`OIDC_ISSUER`), ключи берутся по внутреннему (`OIDC_JWKS_URL`).
Не выполняйте `docker compose down -v`: это удалит тома с данными Keycloak и приложения.

## Оплата через Stripe (тестовый режим)

По умолчанию платежи идут через встроенный симулятор. Чтобы использовать настоящий Stripe (только тестовые ключи, деньги не списываются):

1. Зарегистрируйтесь на stripe.com, включите Test mode, возьмите `sk_test_…` в Developers → API keys.
2. В Settings → Billing → Customer portal сохраните настройки портала (нужно один раз для кнопки «Карта и счета»).
3. Запустите пересылку вебхуков и скопируйте выданный `whsec_…`:
   ```bash
   stripe listen --forward-to localhost:3000/api/webhooks/stripe
   ```
4. В `.env`: `PAYMENT_PROVIDER=stripe`, `STRIPE_SECRET_KEY=sk_test_…`, `STRIPE_WEBHOOK_SECRET=whsec_…`, затем `docker compose up --build -d`.

Оплата: карта `4242 4242 4242 4242`, любая будущая дата, любой CVC (отказ — `4000 0000 0000 0002`, 3-D Secure — `4000 0025 0000 3155`). При ngrok вместо CLI можно добавить endpoint `PUBLIC_URL/api/webhooks/stripe` в Dashboard с событиями `invoice.paid`, `invoice.payment_failed`, `customer.subscription.updated`, `customer.subscription.deleted`.

## Подключение к 1С (OData)

Backend читает 1С через стандартный интерфейс OData (только `GET`). По умолчанию вместо настоящей базы поднимается заглушка `onec-mock` с тестовыми данными (продажи, склад, расчёты, зарплата за 12 месяцев): те же адреса, формат ответов и строгость `$filter`, что у платформы. Консоль заглушки: http://localhost:8100/odata/standard.odata/$metadata (логин и пароль `odata`).

- **Каталог источников** подтягивается из `$metadata` при старте backend и по кнопке «Обновить каталог из 1С» на странице «Администрирование» (`POST /api/sources/sync`, только admin). Из 1С берутся объекты и поля; названия, описания и роли хранятся в приложении и не затираются. Новый объект получает роль «только admin». Объект, снятый с публикации, удаляется из каталога.
- **Агент** (`LLM_PROVIDER=gemini`) получает инструменты `query_1c`, `aggregate_1c`, `find_reference`. Бэкенд сам выполняет запросы и проверяет, что объект входит в источники пользователя (роль + его выбор), ограничивает объём (до 100 строк, до 5000 при подсчёте итогов). Ссылки на справочники возвращаются названиями. Выполненные запросы сохраняются в сообщении и показываются в блоке «Как получен ответ».
- **Настоящая 1С:** опубликуйте базу с OData и задайте `ONEC_ODATA_URL`, `ONEC_USER`, `ONEC_PASSWORD` в `.env`, затем `docker compose up -d backend`. Под этим пользователем 1С должны быть только права на чтение.
