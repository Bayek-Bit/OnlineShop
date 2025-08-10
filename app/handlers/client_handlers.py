from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart

import app.keyboards.client_kb as client_kb
from app.database.requests import set_user
from app.settings.messages import First_message


client_router = Router()

@client_router.message(CommandStart())
async def start(message: Message):
    await set_user(message.from_user.id)
    await message.answer(text=First_message, reply_markup=client_kb.menu)


@client_router.callback_query(F.data == "main_menu")
async def start(callback: CallbackQuery):
    await callback.answer('')
    await callback.message.edit_text(text=First_message, reply_markup=client_kb.menu)


@client_router.callback_query(F.data == "catalog")
async def send_catalog(callback: CallbackQuery):
    await callback.answer('')
    await callback.message.edit_text("Выберите категорию:", reply_markup=await client_kb.categories_kb())


@client_router.callback_query(F.data.startswith("category_"))
async def send_items(callback: CallbackQuery):
    await callback.answer('')
    category_id = callback.data.lstrip("category_") # category_1 -> getting category id 1
    category_id = int(category_id) # get_items_kb should get int type
    await callback.message.edit_text("Выберите товар:", reply_markup=await client_kb.items_kb(category_id))