# Telegram Chat Filter — Web + User Client (Pyrogram)

Этот репозиторий поднимает сайт (FastAPI) и «юзер‑клиент» Telegram (Pyrogram), чтобы:
- «Зайти» в свой Telegram (авторизация по номеру телефона и коду/2FA);
- Выбрать чаты для мониторинга;
- Получать на сайте сообщения **только** из выбранных чатов;
- Настроить фильтр «рабочих» сообщений по ключевым словам (include/exclude);
- Отвечать в выбранные чаты прямо из веб‑интерфейса.

> Важно: этот проект использует **юзер‑клиент** (MTProto) — авторизацию под вашим аккаунтом Telegram. Это НЕ Telegram Bot API.
> Соблюдайте правила безопасности, храните .session файлы в секьюрном месте. Юзер‑клиенты официально не поддерживаются Telegram как «боты».
> Используйте на свой страх и риск. Для compliant‑варианта добавляйте классического бота в нужные группы/каналы и читайте только те чаты, где бот — участник.

## Быстрый старт

1. Получите `api_id` и `api_hash` на https://my.telegram.org/apps
2. Скопируйте `.env.example` в `.env` и заполните значения:
   ```env
   TELEGRAM_API_ID=123456
   TELEGRAM_API_HASH=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   SESSION_SECRET=change-me
   DATABASE_URL=sqlite+aiosqlite:///./data/app.db
   SESSION_DIR=./data/sessions
   ```
3. Установите зависимости и запустите:
   ```bash
   python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   uvicorn app.main:app --reload
   ```
4. Откройте http://127.0.0.1:8000 — введите телефон, получите код, завершите авторизацию.
5. Перейдите в «Выбор чатов», отметьте галочками нужные диалоги.
6. В «Ленте» увидите только сообщения из выбранных чатов (живой стрим через WebSocket). Можно отвечать прямо со страницы.
7. Настройте фильтр (вкладка «Фильтр») — include/exclude ключевые слова (через запятую). Сообщения проходят, если **совпало хотя бы одно** include (если список не пустой) и **не совпал ни один** exclude.

## Что под капотом

- **FastAPI** (веб, API, WebSocket), Jinja2 (шаблоны).
- **Pyrogram** — отдельный клиент на пользователя. Сессии лежат в `./data/sessions`.
- **SQLite** (через SQLAlchemy async) — пользователи, чаты, сообщения, настройки фильтра.
- **WebSocket** — пушим новые сообщения в браузер.
- Фоновый listener для каждого авторизованного пользователя: ловит входящие сообщения, фильтрует и складывает в БД + пушит в веб.

## Структура

```
app/
  main.py           # Точка входа FastAPI
  db.py             # Соединение с БД
  models.py         # SQLAlchemy модели
  schemas.py        # Pydantic-схемы
  telegram_client.py# Менеджер Pyrogram клиентов
  ws_manager.py     # Рассылка WebSocket-сообщений
  filters.py        # Логика include/exclude фильтра
  auth_routes.py    # Маршруты авторизации (телефон -> код -> 2FA)
  chat_routes.py    # Чаты, лента, отправка сообщений
  templates/        # Jinja2 HTML
  static/           # CSS
data/
  app.db            # SQLite (после первого запуска)
  sessions/         # *.session файлы Pyrogram
```

## GitLab CI/CD (опционально)

Добавьте `Dockerfile` и pipeline по желанию. Локальный запуск — самый быстрый способ проверить.

## Лицензия

MIT
