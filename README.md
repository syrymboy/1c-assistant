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
| http://localhost:8080 | Keycloak (консоль: `admin` / `admin`) |

Если порт 8000 занят, задайте в `.env` другой `BACKEND_PORT` и пересоберите (`docker compose up --build`): адрес API вшивается во фронтенд при сборке.

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
