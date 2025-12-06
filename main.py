"""
Точка входа в приложение Telegram-бота для онлайн магазина.

Инициализирует бота, подключает роутеры и запускает polling.
"""
import asyncio

from aiogram import Bot, Dispatcher

from app.settings.settings import settings
from app.handlers.client_handlers import client_router
from app.handlers.executor_handlers import executor_router
from app.database.requests import update_prices
from app.database.models import create_tables


async def main():
    """
    Основная функция запуска бота.
    
    Инициализирует бота, обновляет цены в Redis,
    подключает роутеры и запускает polling.
    """
    # Раскомментируйте для создания таблиц и заполнения БД:
    # await create_tables()
    # await populate_db()
    
    # Обновляем цены в Redis при старте
    await update_prices()
    
    # Инициализация бота и диспетчера
    bot = Bot(settings.TG_TOKEN)
    await bot.delete_webhook(drop_pending_updates=True)
    
    dp = Dispatcher()
    dp.include_router(client_router)
    dp.include_router(executor_router)
    
    # Запуск polling
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
