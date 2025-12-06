"""
Обработчики для клиентов бота.

Содержит логику обработки команд и callback-запросов от клиентов:
- Навигация по каталогу (игры, категории, товары)
- Работа с корзиной
- Создание и оплата заказов
"""
import asyncio

from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart

import app.keyboards.client_kb as client_kb
import app.keyboards.executor_kb as executor_kb
from app.database.requests import (
    set_user, has_active_order, add_to_cart, clear_cart,
    create_order_in_db, confirm_user_payment, get_cart_total,
    assign_executor, retry_assign_executor, check_payment_timeout,
    get_executor_tg_id_by_order, get_cart_game_id,
    get_cart_items_with_details, get_category_by_id
)
from app.settings.messages import First_message
from app.settings.settings import settings, PAYMENT_TIMEOUT

client_router = Router()


class OrderForm(StatesGroup):
    """Состояния FSM для процесса оформления заказа."""
    choosing_game = State()
    choosing_category = State()
    choosing_item = State()
    waiting_for_payment = State()


# ==================== Начало работы ====================

@client_router.message(CommandStart())
async def start(message: Message):
    """
    Обработчик команды /start.
    
    Регистрирует пользователя, очищает корзину (если пользователь не новый)
    и проверяет наличие активных заказов.
    """
    is_new = await set_user(message.from_user.id)
    if not is_new:
        await clear_cart(user_id=message.from_user.id)
    
    if await has_active_order(message.from_user.id):
        await message.answer(
            "У вас есть активный заказ. Завершите его перед новым."
        )
        return
    
    await message.answer(
        text=First_message, 
        reply_markup=client_kb.menu
    )


@client_router.callback_query(F.data == "main_menu")
async def main_menu(callback: CallbackQuery):
    """
    Обработчик возврата в главное меню.
    
    Очищает корзину и возвращает пользователя на главный экран.
    """
    await clear_cart(user_id=callback.from_user.id)
    await callback.answer('')
    
    try:
        await callback.message.edit_text(
            text=First_message, 
            reply_markup=client_kb.menu
        )
    except TelegramBadRequest:
        # Если не удалось отредактировать сообщение, удаляем и создаем новое
        await callback.message.delete()
        await callback.message.answer(
            text=First_message, 
            reply_markup=client_kb.menu
        )


# ==================== Навигация по каталогу ====================

@client_router.callback_query(F.data == "catalog")
async def send_catalog(callback: CallbackQuery, state: FSMContext):
    """
    Открывает каталог игр.
    
    Проверяет наличие активных заказов и переводит пользователя
    в состояние выбора игры.
    """
    if await has_active_order(callback.from_user.id):
        await callback.answer("У вас есть активный заказ. Завершите его.")
        return
    
    await state.set_state(OrderForm.choosing_game)
    await callback.answer('')
    await callback.message.edit_text(
        "Выберите игру:", 
        reply_markup=await client_kb.games_kb()
    )


@client_router.callback_query(
    OrderForm.choosing_game, 
    F.data.startswith("game_")
)
async def send_categories(callback: CallbackQuery, state: FSMContext):
    """
    Показывает категории выбранной игры.
    
    Сохраняет game_id в состоянии и переводит в состояние выбора категории.
    """
    await callback.answer('')
    game_id = int(callback.data.removeprefix("game_"))
    await state.update_data(game_id=game_id)
    await state.set_state(OrderForm.choosing_category)
    
    await callback.message.edit_text(
        "Выберите категорию:", 
        reply_markup=await client_kb.categories_kb(game_id)
    )


@client_router.callback_query(
    OrderForm.choosing_category, 
    F.data.startswith("category_")
)
async def send_items(callback: CallbackQuery, state: FSMContext):
    """
    Показывает товары выбранной категории.
    
    Сохраняет category_id в состоянии и переводит в состояние выбора товара.
    Если в корзине есть товары из другой игры, очищает корзину.
    """
    await callback.answer('')
    category_id = int(callback.data.removeprefix("category_"))
    
    # Получаем game_id выбранной категории
    category = await get_category_by_id(category_id)
    
    if category:
        # Проверяем, есть ли в корзине товары из другой игры
        cart_game_id = await get_cart_game_id(callback.from_user.id)
        if cart_game_id is not None and cart_game_id != category.game_id:
            # Очищаем корзину, если товары из другой игры
            await clear_cart(callback.from_user.id)
            await callback.answer(
                "Корзина очищена. Вы можете заказать товары только из одной игры.",
                show_alert=True
            )
    
    await state.update_data(category_id=category_id)
    await state.set_state(OrderForm.choosing_item)
    
    # Получаем итоговую сумму для отображения
    total_sum = await get_cart_total(callback.from_user.id)
    message_text = f"Выберите товар:\n\n🌑 Итого: {total_sum}р."
    
    await callback.message.edit_text(
        message_text,
        reply_markup=await client_kb.items_kb(
            user_id=callback.from_user.id,
            category_id=category_id
        )
    )


# ==================== Работа с корзиной ====================

@client_router.callback_query(
    OrderForm.choosing_item, 
    F.data.startswith("add_item_")
)
async def add_item_to_cart(callback: CallbackQuery):
    """
    Добавляет товар в корзину.
    
    Формат callback_data: add_item_{category_id}_{item_id}
    Обновляет клавиатуру с обновленным счетчиком товара и итоговой суммой.
    """
    await callback.answer('')
    
    # Парсим category_id и product_id из callback_data
    # Формат: add_item_{category_id}_{item_id}
    data_parts = callback.data[len("add_item_"):].split("_")
    category_id, product_id = map(int, data_parts)
    
    await add_to_cart(callback.from_user.id, product_id, 1)
    total_sum = await get_cart_total(callback.from_user.id)
    
    message_text = f"Выберите товар:\n\n🌑 Итого: {total_sum}р."
    
    await callback.message.edit_text(
        text=message_text,
        reply_markup=await client_kb.items_kb(
            user_id=callback.from_user.id,
            category_id=category_id
        )
    )


@client_router.callback_query(
    OrderForm.choosing_item, 
    F.data.startswith("reset_cart_category_")
)
async def reset_cart(callback: CallbackQuery, state: FSMContext):
    """
    Очищает корзину и обновляет клавиатуру, убирая счетчики товаров.
    """
    await callback.answer('')
    await clear_cart(user_id=callback.from_user.id)
    
    data = await state.get_data()
    category_id = data.get('category_id')
    
    message_text = "Выберите товар:\n\n🌑 Итого: 0р."
    
    await callback.message.edit_text(
        text=message_text,
        reply_markup=await client_kb.items_kb(
            user_id=callback.from_user.id,
            category_id=category_id
        )
    )


@client_router.callback_query(
    OrderForm.choosing_item,
    F.data == "view_cart"
)
async def view_cart(callback: CallbackQuery, state: FSMContext):
    """
    Показывает содержимое корзины со всеми выбранными товарами.
    """
    await callback.answer('')
    
    cart_items = await get_cart_items_with_details(callback.from_user.id)
    total_sum = await get_cart_total(callback.from_user.id)
    
    if not cart_items:
        message_text = "Корзина пуста."
    else:
        # Формируем список товаров по категориям
        message_lines = ["🛒 <b>Ваша корзина:</b>\n"]
        
        # Группируем товары по категориям
        items_by_category = {}
        for item in cart_items:
            cat_name = item['category_name']
            if cat_name not in items_by_category:
                items_by_category[cat_name] = []
            items_by_category[cat_name].append(item)
        
        # Выводим товары по категориям
        for cat_name, items in items_by_category.items():
            message_lines.append(f"\n📦 <b>{cat_name}:</b>")
            for item in items:
                message_lines.append(
                    f"  • {item['name']} x{item['quantity']} "
                    f"= {item['total']}р."
                )
        
        message_lines.append(f"\n\n🌑 <b>Итого: {total_sum}р.</b>")
        message_text = "\n".join(message_lines)
    
    data = await state.get_data()
    category_id = data.get('category_id')
    
    await callback.message.edit_text(
        text=message_text,
        reply_markup=await client_kb.cart_view_kb(category_id),
        parse_mode="HTML"
    )


# ==================== Навигация назад ====================

@client_router.callback_query(
    OrderForm.choosing_item,
    F.data.startswith("back_to_items_")
)
async def back_to_items(callback: CallbackQuery, state: FSMContext):
    """
    Возвращает пользователя к просмотру товаров категории.
    
    Формат callback_data: back_to_items_{category_id}
    """
    await callback.answer('')
    category_id = int(callback.data.removeprefix("back_to_items_"))
    await state.update_data(category_id=category_id)
    
    total_sum = await get_cart_total(callback.from_user.id)
    message_text = f"Выберите товар:\n\n🌑 Итого: {total_sum}р."
    
    await callback.message.edit_text(
        text=message_text,
        reply_markup=await client_kb.items_kb(
            user_id=callback.from_user.id,
            category_id=category_id
        )
    )


@client_router.callback_query(
    OrderForm.choosing_item, 
    F.data == "back_to_categories"
)
async def back_to_categories(callback: CallbackQuery, state: FSMContext):
    """
    Возвращает пользователя к выбору категорий.
    
    Использует сохраненный game_id из состояния.
    """
    await callback.answer('')
    data = await state.get_data()
    game_id = data.get('game_id')
    
    if game_id:
        await state.set_state(OrderForm.choosing_category)
        await callback.message.edit_text(
            "Выберите категорию:", 
            reply_markup=await client_kb.categories_kb(game_id)
        )
    else:
        # Fallback, если game_id потерян
        await callback.message.edit_text(
            "Ошибка. Вернитесь в каталог.", 
            reply_markup=client_kb.menu
        )
        await state.clear()


@client_router.callback_query(
    OrderForm.choosing_category, 
    F.data == "back_to_games"
)
async def back_to_games(callback: CallbackQuery, state: FSMContext):
    """Возвращает пользователя к выбору игр."""
    await callback.answer('')
    await state.set_state(OrderForm.choosing_game)
    await callback.message.edit_text(
        "Выберите игру:", 
        reply_markup=await client_kb.games_kb()
    )


# ==================== Создание и оплата заказа ====================

@client_router.callback_query(
    OrderForm.choosing_item, 
    F.data == "create_order"
)
async def create_order(callback: CallbackQuery, state: FSMContext):
    """
    Создает заказ из товаров в корзине.
    
    Сохраняет order_id в состоянии и запускает фоновую задачу
    для проверки таймаута оплаты.
    """
    await callback.answer('')
    total_sum = await get_cart_total(callback.from_user.id)
    
    if total_sum == 0:
        await callback.message.edit_text("Корзина пуста.")
        return
    
    # Получаем список товаров ДО очистки корзины
    cart_items = await get_cart_items_with_details(callback.from_user.id)
    
    # Создаем заказ
    order = await create_order_in_db(callback.from_user.id, total_sum)
    await clear_cart(callback.from_user.id)
    await state.set_state(OrderForm.waiting_for_payment)
    await state.update_data(order_id=order.id)
    
    # Формируем сообщение с товарами
    message_lines = [f"✅ <b>Заказ #{order.id} создан</b>\n"]
    
    if cart_items:
        message_lines.append("\n📦 <b>Состав заказа:</b>")
        
        # Группируем товары по категориям
        items_by_category = {}
        for item in cart_items:
            cat_name = item['category_name']
            if cat_name not in items_by_category:
                items_by_category[cat_name] = []
            items_by_category[cat_name].append(item)
        
        # Выводим товары по категориям
        for cat_name, items in items_by_category.items():
            message_lines.append(f"\n<b>{cat_name}:</b>")
            for item in items:
                message_lines.append(
                    f"  • {item['name']} x{item['quantity']} "
                    f"= {item['total']}р."
                )
    
    message_lines.append(f"\n\n🌑 <b>Итого: {total_sum}р.</b>")
    message_lines.append(f"\n💳 <b>Реквизиты:</b> [вставь свои реквизиты]")
    message_lines.append(
        f"\n⏰ Оплатите в течение {PAYMENT_TIMEOUT // 60} мин."
    )
    
    # Отправляем сообщение с товарами и реквизитами
    await callback.message.edit_text(
        "\n".join(message_lines),
        reply_markup=client_kb.payment_kb(),
        parse_mode="HTML"
    )
    
    # Запускаем фоновую задачу для проверки таймаута оплаты
    asyncio.create_task(
        check_payment_timeout(
            callback.bot, 
            order.id, 
            callback.from_user.id
        )
    )


@client_router.callback_query(
    OrderForm.waiting_for_payment, 
    F.data == "paid"
)
async def user_confirm_payment(callback: CallbackQuery, state: FSMContext):
    """
    Обрабатывает подтверждение оплаты от пользователя.
    
    Назначает исполнителя на заказ и уведомляет его.
    Если свободных исполнителей нет, запускает повторную попытку через 5 минут.
    """
    await callback.answer('')
    data = await state.get_data()
    order_id = data.get('order_id')
    
    if not order_id:
        return
    
    await confirm_user_payment(order_id)
    assigned = await assign_executor(order_id)
    
    if assigned:
        # Уведомляем исполнителя о новом заказе
        executor_tg_id = await get_executor_tg_id_by_order(order_id)
        if executor_tg_id:
            await callback.bot.send_message(
                executor_tg_id, 
                f"Новый заказ #{order_id}. Подтвердите оплату.", 
                reply_markup=executor_kb.confirm_payment_kb(order_id)
            )
        await callback.message.edit_text(
            "Оплата подтверждена. Ждите подтверждения от исполнителя."
        )
    else:
        # Если свободных исполнителей нет, пробуем через 5 минут
        asyncio.create_task(
            retry_assign_executor(
                callback.bot, 
                order_id, 
                callback.from_user.id
            )
        )
        await callback.message.edit_text(
            "Нет свободных исполнителей. Подождите 5 мин."
        )
