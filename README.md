# Telegram Shop Bot

Этот проект представляет собой Telegram-бота, реализующего функциональность интернет-магазина для продажи внутриигровых ценностей (например, гемов) в различных играх.

## Особенности

*   **Асинхронная работа:** Использует `aiogram` и `SQLAlchemy` с асинхронными драйверами для высокой производительности.
*   **ORM:** Для работы с базой данных используется `SQLAlchemy`.
*   **Кэширование и сессии:** Использует `Redis` для кэширования часто запрашиваемых данных (например, товаров в категории) и хранения временных данных пользователей (например, содержимого корзины).
*   **Структурированный код:** Проект разделён на логические модули (`database`, `handlers`, `keyboards`, `settings`) для лучшей читаемости и поддержки.
*   **Управление заказами:** Позволяет пользователям просматривать игры, категории, выбирать товары, добавлять их в корзину и формировать заказы.
*   **Примеры данных:** При запуске автоматически заполняется база данных примерами товаров для Genshin Impact и Brawl Stars.

## Структура проекта
└── ./
    ├── app
    │   ├── database
    │   │   ├── models.py
    │   │   └── requests.py
    │   ├── handlers
    │   │   └── client_handlers.py
    │   ├── keyboards
    │   │   └── client_kb.py
    │   └── settings
    │       ├── messages.py
    │       └── settings.py
    └── main.py


## Установка и запуск

1.  **Клонируйте репозиторий:**
    ```bash
    git clone <URL_ВАШЕГО_РЕПОЗИТОРИЯ>
    cd <НАЗВАНИЕ_ПРОЕКТА>
    ```

2.  **Создайте и активируйте виртуальное окружение (рекомендуется):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3.  **Установите зависимости:**
    ```bash
    pip install -r requirements.txt
    ```
    *(Файл `requirements.txt` должен содержать: `aiogram`, `sqlalchemy`, `asyncpg` (или другой драйвер для вашей БД), `redis`, `pydantic-settings`)*

4.  **Настройте переменные окружения:**
    Создайте файл `.env` в корне проекта и добавьте следующие строки:
    ```env
    # Токен бота, полученный от @BotFather
    TG_TOKEN=YOUR_BOT_TOKEN_HERE

    # Адрес базы данных (например, SQLite или PostgreSQL)
    # Пример для SQLite: sqlite+aiosqlite:///./shop.db
    # Пример для PostgreSQL: postgresql+asyncpg://user:password@localhost/dbname
    DB_URL=sqlite+aiosqlite:///./shop.db
    ```

5.  **Убедитесь, что запущен сервер Redis** на стандартном порту `6379`.

6.  **Запустите бота:**
    ```bash
    python main.py
    ```

## Технологии

*   Python 3.x
*   [Aiogram 3](https://docs.aiogram.dev/en/latest/)
*   [SQLAlchemy 2](https://docs.sqlalchemy.org/en/20/)
*   [Redis-py (async)](https://redis-py.readthedocs.io/en/stable/)
*   [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
