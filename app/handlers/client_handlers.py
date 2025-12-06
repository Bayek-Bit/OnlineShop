from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
import app.keyboards.client_kb as client_kb
from app.database.requests import set_user, has_active_order
from app.database.requests import add_to_cart, clear_cart, create_order_in_db, confirm_user_payment
from app.database.requests import get_cart_total, assign_executor, retry_assign_executor
from app.settings.messages import First_message
from app.settings.settings import settings, PAYMENT_TIMEOUT
import asyncio  # NEW: для таймеров
client_router = Router()
class OrderForm(StatesGroup):
    choosing_game = State()
    choosing_category = State()
    choosing_item = State()
    waiting_for_payment = State()
# UPDATED: Добавил проверку на активный заказ в start и catalog
@client_router.message(CommandStart())
async def start(message: Message):
    is_new = await set_user(message.from_user.id)
    if not is_new:
        await clear_cart(user_id=message.from_user.id)
    if await has_active_order(message.from_user.id):
        await message.answer("У вас есть активный заказ. Завершите его перед новым.")
        return
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
    if await has_active_order(callback.from_user.id):
        await callback.answer("У вас есть активный заказ. Завершите его.")
        return
    await state.set_state(OrderForm.choosing_game)
    await callback.answer('')
    await callback.message.edit_text("Выберите игру:", reply_markup=await client_kb.games_kb())
# Выбор категории
@client_router.callback_query(OrderForm.choosing_game, F.data.startswith("game_"))
async def send_categories(callback: CallbackQuery, state: FSMContext):
    await callback.answer('')
    game_id = int(callback.data.removeprefix("game_"))
    await state.update_data(game_id = game_id)
    await state.set_state(OrderForm.choosing_category)
    await callback.message.edit_text("Выберите категорию:", reply_markup=await client_kb.categories_kb(game_id))
# Выбор товара
@client_router.callback_query(OrderForm.choosing_category, F.data.startswith("category_"))
async def send_items(callback: CallbackQuery, state: FSMContext):
    await callback.answer('')
    category_id = int(callback.data.removeprefix("category_"))
    await state.update_data(category_id=category_id) # Сохраняем для будущего
    await state.set_state(OrderForm.choosing_item)
    await callback.message.edit_text("Выберите товар:", reply_markup=await client_kb.items_kb(
        user_id=callback.from_user.id,
        category_id=category_id
    ))
# Добавление товара в корзину + появление/увеличение счетчика + итоговая сумма заказа
@client_router.callback_query(OrderForm.choosing_item, F.data.startswith("add_item_"))
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
@client_router.callback_query(OrderForm.choosing_item, F.data.startswith("reset_cart_category_"))
async def reset_cart(callback: CallbackQuery):
    await callback.answer('')
    # Очищаем корзину клиента в редис
    await clear_cart(user_id=callback.from_user.id)
    await callback.message.edit_text(
        text="🌑 Итого: 0р.",
        reply_markup=await client_kb.reset_items_count(callback.message.reply_markup)
    )
# Бэк к категориям из товаров
@client_router.callback_query(OrderForm.choosing_item, F.data == "back_to_categories")
async def back_to_categories(callback: CallbackQuery, state: FSMContext):
    await callback.answer('')
    data = await state.get_data()
    game_id = data.get('game_id')
    if game_id:
        await state.set_state(OrderForm.choosing_category)
        await callback.message.edit_text("Выберите категорию:", reply_markup=await client_kb.categories_kb(game_id))
    else:
        # Fallback, если game_id потерян
        await callback.message.edit_text("Ошибка. Вернитесь в каталог.", reply_markup=client_kb.menu)
        await state.clear()
# Бэк к играм из категорий (если нужно, но "catalog" уже есть)
@client_router.callback_query(OrderForm.choosing_category, F.data == "back_to_games")
async def back_to_games(callback: CallbackQuery, state: FSMContext):
    await callback.answer('')
    await state.set_state(OrderForm.choosing_game)
    await callback.message.edit_text("Выберите игру:", reply_markup=await client_kb.games_kb())
# UPDATED: create_order (используем callback.bot)
@client_router.callback_query(OrderForm.choosing_item, F.data == "create_order")
async def create_order(callback: CallbackQuery, state: FSMContext):
    await callback.answer('')
    total_sum = await get_cart_total(callback.from_user.id)
    if total_sum == 0:
        await callback.message.edit_text("Корзина пуста.")
        return
    order = await create_order_in_db(callback.from_user.id, total_sum)
    await clear_cart(callback.from_user.id)
    await state.set_state(OrderForm.waiting_for_payment)
    await state.update_data(order_id=order.id)
    # Отправляем реквизиты с кнопкой
    await callback.message.edit_text(
        f"Заказ #{order.id} создан. Сумма: {total_sum}р.\nРеквизиты: [вставь свои реквизиты].\nОплатите в течение {PAYMENT_TIMEOUT//60} мин.",
        reply_markup=client_kb.payment_kb()
    )
    # Фоновая задача для таймера (передаём callback.bot)
    asyncio.create_task(check_payment_timeout(callback.bot, order.id, callback.from_user.id, state))
# UPDATED: user_confirm_payment (используем callback.bot)
@client_router.callback_query(OrderForm.waiting_for_payment, F.data == "paid")
async def user_confirm_payment(callback: CallbackQuery, state: FSMContext):
    await callback.answer('')
    data = await state.get_data()
    order_id = data.get('order_id')
    if not order_id:
        return
    await confirm_user_payment(order_id)
    assigned = await assign_executor(order_id)
    if assigned:
        # Уведомить исполнителя
        async with async_session() as session:
            order = await session.scalar(select(Order).where(Order.id == order_id))
            executor_tg_id = (await session.scalar(select(User).where(User.id == order.executor_id))).tg_id
        await callback.bot.send_message(executor_tg_id, f"Новый заказ #{order_id}. Подтвердите оплату.", reply_markup=executor_kb.confirm_payment_kb(order_id))
        await callback.message.edit_text("Оплата подтверждена. Ждите подтверждения от исполнителя.")
    else:
        asyncio.create_task(retry_assign_executor(callback.bot, order_id, callback.from_user.id))  # Передаём callback.bot
        await callback.message.edit_text("Нет свободных исполнителей. Подождите 5 мин.")
# UPDATED: check_payment_timeout (принимает bot)
async def check_payment_timeout(bot, order_id: int, user_tg_id: int, state: FSMContext):  # Убрали type hint Bot, чтобы избежать импорта, если не нужно
    async with async_session() as session:
        order = await session.scalar(select(Order).where(Order.id == order_id))
        await asyncio.sleep((order.expires_at - datetime.now(timezone.utc)).total_seconds())
        if order.status == settings.ORDER_STATUS_PENDING_PAYMENT and not order.payment_confirmed_by_user:
            await update_order_status(order_id, settings.ORDER_STATUS_CANCELLED)
            await bot.send_message(user_tg_id, f"Время на оплату заказа #{order_id} истекло. Заказ отменён.")
            await state.clear()