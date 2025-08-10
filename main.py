from os import getenv
import asyncio
from aiogram import Bot, Dispatcher
from dotenv import load_dotenv

async def main():
    load_dotenv()
    bot = Bot(getenv("TG_TOKEN"))
    dp = Dispatcher()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())