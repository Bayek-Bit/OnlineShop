# Обработка исключений по подключению редиса и тп
# Обработчик для about (about us)
# Когда выходишь из категории и потом снова заходишь, нужно добавлять счетчик итого или заказы ток из 1 категории
import asyncio
from aiogram import Bot, Dispatcher

from app.settings.settings import settings

from app.handlers.client_handlers import client_router
from app.handlers.executor_handlers import executor_router
from app.database.requests import populate_db
from app.database.models import create_tables


async def main():
    await create_tables()
    await populate_db()
    bot = Bot(settings.TG_TOKEN)
    await bot.delete_webhook(drop_pending_updates=True)
    dp = Dispatcher()
    dp.include_router(client_router)
    dp.include_router(executor_router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())