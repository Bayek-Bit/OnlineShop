# Сначала значок товара - потом название товара

# Валидация(pydantic схема для sqlalchemy обьектов)
# Подтверждение заказа, состояния
# Выбор -> формирование заказа, оплата(назначение на заказ, проверка оплаты) -> Завершенный заказ
# Назначение исполнителя(если нет свободных, то таймер 5 мин и снова попытка назначить)
# Список товаров прямо в модели заказа / получать из redis
# create order
import asyncio
from aiogram import Bot, Dispatcher

from app.settings.settings import settings

from app.handlers.client_handlers import client_router
from app.database.models import create_tables


async def main():
    await create_tables()
    bot = Bot(settings.TG_TOKEN)
    await bot.delete_webhook(drop_pending_updates=True)
    dp = Dispatcher()
    dp.include_router(client_router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())