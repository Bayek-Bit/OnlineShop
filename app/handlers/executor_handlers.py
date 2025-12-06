"""
Обработчики для исполнителей бота.

Содержит логику обработки команд и callback-запросов от исполнителей:
- Регистрация исполнителя
- Подтверждение/отклонение оплаты заказа
- Завершение заказа
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command

import app.keyboards.executor_kb as executor_kb
from app.database.requests import (
    set_user, update_order_status, get_user_tg_id, get_order_by_id
)
from app.settings.settings import settings

executor_router = Router()


# ==================== Регистрация ====================

@executor_router.message(Command("executor"))
async def register_executor(message: Message):
    """
    Регистрирует пользователя как исполнителя.
    
    Команда: /executor
    """
    await set_user(message.from_user.id, role="Executor")
    await message.answer("Вы зарегистрированы как исполнитель.")


# ==================== Работа с заказами ====================

@executor_router.callback_query(F.data.startswith("confirm_payment_"))
async def confirm_payment(callback: CallbackQuery):
    """
    Подтверждает оплату заказа и переводит его в статус "в работе".
    
    Формат callback_data: confirm_payment_{order_id}
    Уведомляет клиента о подтверждении оплаты.
    """
    await callback.answer('')
    order_id = int(callback.data.removeprefix("confirm_payment_"))
    
    await update_order_status(
        order_id, 
        settings.ORDER_STATUS_IN_PROGRESS
    )
    
    # Уведомляем клиента
    order = await get_order_by_id(order_id)
    if order:
        user_tg_id = await get_user_tg_id(order.user_id)
        if user_tg_id:
            await callback.bot.send_message(
                user_tg_id, 
                f"Оплата заказа #{order_id} подтверждена. "
                f"Исполнитель приступил к работе."
            )
    
    await callback.message.edit_text(
        f"Заказ #{order_id} в работе.", 
        reply_markup=executor_kb.complete_order_kb(order_id)
    )


@executor_router.callback_query(F.data.startswith("decline_payment_"))
async def decline_payment(callback: CallbackQuery):
    """
    Отклоняет оплату заказа и отменяет заказ.
    
    Формат callback_data: decline_payment_{order_id}
    Уведомляет клиента об отклонении оплаты.
    """
    await callback.answer('')
    order_id = int(callback.data.removeprefix("decline_payment_"))
    
    await update_order_status(
        order_id, 
        settings.ORDER_STATUS_CANCELLED
    )
    
    # Уведомляем клиента
    order = await get_order_by_id(order_id)
    if order:
        user_tg_id = await get_user_tg_id(order.user_id)
        if user_tg_id:
            await callback.bot.send_message(
                user_tg_id, 
                f"Оплата заказа #{order_id} отклонена. "
                f"Свяжитесь с поддержкой."
            )
    
    await callback.message.edit_text(f"Заказ #{order_id} отменён.")


@executor_router.callback_query(F.data.startswith("complete_order_"))
async def complete_order(callback: CallbackQuery):
    """
    Завершает заказ и переводит его в статус "выполнен".
    
    Формат callback_data: complete_order_{order_id}
    Уведомляет клиента о завершении заказа.
    """
    await callback.answer('')
    order_id = int(callback.data.removeprefix("complete_order_"))
    
    await update_order_status(
        order_id, 
        settings.ORDER_STATUS_COMPLETED
    )
    
    # Уведомляем клиента
    order = await get_order_by_id(order_id)
    if order:
        user_tg_id = await get_user_tg_id(order.user_id)
        if user_tg_id:
            await callback.bot.send_message(
                user_tg_id, 
                f"Заказ #{order_id} выполнен! "
                f"Теперь вы можете создать новый."
            )
    
    await callback.message.edit_text(f"Заказ #{order_id} завершён.")
