from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart

import app.keyboards.client_kb as client_kb
from app.database.requests import set_user # main db
from app.database.requests import add_to_cart, clear_cart # redis
from app.database.requests import get_cart_total
from app.settings.messages import First_message


client_router = Router()

class OrderForm(StatesGroup):
    choosing_game = State()
    choosing_category = State()
    waiting_for_payment = State()

@client_router.message(CommandStart())
async def start(message: Message):
    is_new = await set_user(message.from_user.id)
    # if user is not new, we need to clear his cart
    if not is_new:
        await clear_cart(user_id=message.from_user.id)
    await message.answer(text=First_message, reply_markup=client_kb.menu)


@client_router.callback_query(F.data == "main_menu")
async def start(callback: CallbackQuery):
    await clear_cart(user_id=callback.from_user.id)
    await callback.answer('')
    try:
        await callback.message.edit_text(text=First_message, reply_markup=client_kb.menu)
    except TelegramBadRequest:
        await callback.message.delete()
        await callback.message.answer(text=First_message, reply_markup=client_kb.menu)


@client_router.callback_query(F.data == "catalog")
async def send_catalog(callback: CallbackQuery, state: FSMContext):
    await clear_cart(user_id=callback.from_user.id)
    await state.set_state(OrderForm.choosing_game)
    await callback.answer('')
    await callback.message.edit_text("Выберите категорию:", reply_markup=await client_kb.categories_kb())

# Выбор товара в категории
@client_router.callback_query(OrderForm.choosing_game, F.data.startswith("category_"))
async def send_items(callback: CallbackQuery, state: FSMContext):
    await callback.answer('')
    await state.set_state(OrderForm.choosing_category)
    category_id = callback.data.removeprefix("category_") # category_1 -> getting category id 1
    category_id = int(category_id) # get_items_kb should get int type
    await callback.message.edit_text("Выберите товар:", reply_markup=await client_kb.items_kb(
        user_id=callback.from_user.id,
        category_id=category_id
    ))

# Добавление товара в корзину + появление/увеличение счетчика + итоговая сумма заказа
@client_router.callback_query(OrderForm.choosing_category, F.data.startswith("add_item_"))
async def add_item_to_cart(callback: CallbackQuery):
    await callback.answer('')
    # add_item_{category_id}_{item_id}
    # item_id equal product_id
    category_id, product_id = map(int, callback.data[len("add_item_"):].split("_"))

    await add_to_cart(callback.from_user.id, product_id, 1)
    total_sum = await get_cart_total(callback.from_user.id)
    await callback.message.edit_text(
        text=f"🌑 Итого: {total_sum}р.",
        reply_markup=await client_kb.items_kb(
            user_id=callback.from_user.id,
            category_id=category_id
        )
    )

# Функция для сброса клавиатуры(убрать xКоличество_товара)
@client_router.callback_query(OrderForm.choosing_category, F.data.startswith("reset_cart_category_"))
async def reset_cart(callback: CallbackQuery):
    await callback.answer('')
    # Очищаем корзину клиента в редис
    await clear_cart(user_id=callback.from_user.id)
    await callback.message.edit_text(
        text="🌑 Итого: 0р.",
        reply_markup=await client_kb.reset_items_count(callback.message.reply_markup)
    )


@client_router.callback_query(OrderForm.choosing_category, F.data == "create_order")
async def create_order(callback: CallbackQuery):
    await callback.answer('')
    # await