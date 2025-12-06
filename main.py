"""
Точка входа в приложение Telegram-бота для онлайн магазина.

Инициализирует бота, подключает роутеры и запускает polling.

# TODO: роль администратора, регистрация исполнителей через администратора
"""
import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher

from app.settings.settings import settings
from app.handlers.client_handlers import client_router
from app.handlers.executor_handlers import executor_router
from app.database.requests import update_prices, populate_db
from app.database.models import create_tables

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


async def main():
    """
    Основная функция запуска бота.
    
    Инициализирует бота, обновляет цены в Redis,
    подключает роутеры и запускает polling.
    """
    # Раскомментируйте для создания таблиц и заполнения БД:
    # await create_tables(drop_existing=False)  # ВНИМАНИЕ: drop_existing=True удалит все данные!
    # await populate_db()
    
    # Обновляем цены в Redis при старте
    try:
        await update_prices()
        logger.info("Prices updated successfully")
    except Exception as e:
        logger.error(f"Failed to update prices: {e}")
        logger.warning("Continuing without price update...")
        # Можно продолжить работу, но лучше проверить подключение к Redis
    
    # Инициализация бота и диспетчера
    try:
        bot = Bot(settings.TG_TOKEN)
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Bot initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize bot: {e}")
        raise
    
    dp = Dispatcher()
    dp.include_router(client_router)
    dp.include_router(executor_router)
    
    # Запуск polling
    logger.info("Starting bot polling...")
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.exception(f"Error in polling: {e}")
        raise
    finally:
        await bot.session.close()
        logger.info("Bot stopped")


if __name__ == "__main__":
    asyncio.run(main())
