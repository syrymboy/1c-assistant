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

## Структура

```
keycloak/realm-export.json   realm, клиент assistant-web, роли, пользователи (автоимпорт)
backend/                     FastAPI, SQLAlchemy, Alembic (миграции при старте)
frontend/                    React + Vite + TS → nginx
```

Issuer токена проверяется по внешнему адресу (`OIDC_ISSUER`), ключи берутся по внутреннему (`OIDC_JWKS_URL`).
Не выполняйте `docker compose down -v`: это удалит тома с данными Keycloak и приложения.
