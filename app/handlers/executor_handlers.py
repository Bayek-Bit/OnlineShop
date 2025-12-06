"""
Обработчики для исполнителей бота.

Содержит логику обработки команд и callback-запросов от исполнителей:
- Регистрация исполнителя
- Подтверждение/отклонение оплаты заказа
- Завершение заказа
"""
import logging

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command

import app.keyboards.executor_kb as executor_kb
from app.database.requests import (
    set_user, update_order_status, get_user_tg_id, get_order_by_id
)
from app.database.models import async_session, User, Order
from sqlalchemy import select
from app.settings.settings import settings
from app.utils.validators import validate_order_id

logger = logging.getLogger(__name__)

executor_router = Router()


# ==================== Регистрация ====================

@executor_router.message(Command("executor"))
async def register_executor(message: Message):
    """
    Регистрирует пользователя как исполнителя.
    
    Команда: /executor
    ВАЖНО: В продакшене должна быть проверка прав доступа!
    """
    # TODO: Добавить проверку прав доступа через ADMIN_IDS
    # if message.from_user.id not in settings.ADMIN_IDS:
    #     await message.answer("У вас нет прав для этой команды.")
    #     return
    
    try:
        await set_user(message.from_user.id, role="Executor")
        await message.answer("Вы зарегистрированы как исполнитель.")
    except Exception as e:
        logger.exception(f"Error in register_executor: {e}")
        await message.answer("Произошла ошибка. Попробуйте позже.")


# ==================== Работа с заказами ====================

@executor_router.callback_query(F.data.startswith("confirm_payment_"))
async def confirm_payment(callback: CallbackQuery):
    """
    Подтверждает оплату заказа и переводит его в статус "в работе".
    
    Формат callback_data: confirm_payment_{order_id}
    Уведомляет клиента о подтверждении оплаты.
    Проверяет, что заказ назначен этому исполнителю.
    """
    await callback.answer('')
    
    try:
        order_id = int(callback.data.removeprefix("confirm_payment_"))
    except ValueError:
        logger.warning(f"Invalid order_id in confirm_payment: {callback.data}")
        await callback.answer("Ошибка: неверный формат данных", show_alert=True)
        return
    
    if not await validate_order_id(order_id):
        await callback.answer("Заказ не найден", show_alert=True)
        return
    
    # Проверяем, что заказ назначен этому исполнителю
    order = await get_order_by_id(order_id)
    if not order:
        await callback.answer("Заказ не найден", show_alert=True)
        return
    
    # Проверяем права доступа
    async with async_session() as session:
        executor = await session.scalar(
            select(User).where(User.tg_id == callback.from_user.id)
        )
        if not executor or executor.id != order.executor_id:
            await callback.answer(
                "Этот заказ не назначен вам", 
                show_alert=True
            )
            return
    
    try:
        await update_order_status(
            order_id, 
            settings.ORDER_STATUS_IN_PROGRESS
        )
        
        # Уведомляем клиента
        user_tg_id = await get_user_tg_id(order.user_id)
        if user_tg_id:
            try:
                await callback.bot.send_message(
                    user_tg_id, 
                    f"Оплата заказа #{order_id} подтверждена. "
                    f"Исполнитель приступил к работе."
                )
            except Exception as e:
                logger.error(f"Failed to send message to user {user_tg_id}: {e}")
        
        await callback.message.edit_text(
            f"Заказ #{order_id} в работе.", 
            reply_markup=executor_kb.complete_order_kb(order_id)
        )
    except Exception as e:
        logger.exception(f"Error in confirm_payment: {e}")
        await callback.answer("Произошла ошибка. Попробуйте позже.", show_alert=True)


@executor_router.callback_query(F.data.startswith("decline_payment_"))
async def decline_payment(callback: CallbackQuery):
    """
    Отклоняет оплату заказа и отменяет заказ.
    
    Формат callback_data: decline_payment_{order_id}
    Уведомляет клиента об отклонении оплаты.
    Проверяет, что заказ назначен этому исполнителю.
    """
    await callback.answer('')
    
    try:
        order_id = int(callback.data.removeprefix("decline_payment_"))
    except ValueError:
        logger.warning(f"Invalid order_id in decline_payment: {callback.data}")
        await callback.answer("Ошибка: неверный формат данных", show_alert=True)
        return
    
    if not await validate_order_id(order_id):
        await callback.answer("Заказ не найден", show_alert=True)
        return
    
    # Проверяем, что заказ назначен этому исполнителю
    order = await get_order_by_id(order_id)
    if not order:
        await callback.answer("Заказ не найден", show_alert=True)
        return
    
    async with async_session() as session:
        executor = await session.scalar(
            select(User).where(User.tg_id == callback.from_user.id)
        )
        if not executor or executor.id != order.executor_id:
            await callback.answer(
                "Этот заказ не назначен вам", 
                show_alert=True
            )
            return
    
    try:
        await update_order_status(
            order_id, 
            settings.ORDER_STATUS_CANCELLED
        )
        
        # Уведомляем клиента
        user_tg_id = await get_user_tg_id(order.user_id)
        if user_tg_id:
            try:
                await callback.bot.send_message(
                    user_tg_id, 
                    f"Оплата заказа #{order_id} отклонена. "
                    f"Свяжитесь с поддержкой."
                )
            except Exception as e:
                logger.error(f"Failed to send message to user {user_tg_id}: {e}")
        
        await callback.message.edit_text(f"Заказ #{order_id} отменён.")
    except Exception as e:
        logger.exception(f"Error in decline_payment: {e}")
        await callback.answer("Произошла ошибка. Попробуйте позже.", show_alert=True)


@executor_router.callback_query(F.data.startswith("complete_order_"))
async def complete_order(callback: CallbackQuery):
    """
    Завершает заказ и переводит его в статус "выполнен".
    
    Формат callback_data: complete_order_{order_id}
    Уведомляет клиента о завершении заказа.
    Проверяет, что заказ назначен этому исполнителю.
    """
    await callback.answer('')
    
    try:
        order_id = int(callback.data.removeprefix("complete_order_"))
    except ValueError:
        logger.warning(f"Invalid order_id in complete_order: {callback.data}")
        await callback.answer("Ошибка: неверный формат данных", show_alert=True)
        return
    
    if not await validate_order_id(order_id):
        await callback.answer("Заказ не найден", show_alert=True)
        return
    
    # Проверяем, что заказ назначен этому исполнителю
    order = await get_order_by_id(order_id)
    if not order:
        await callback.answer("Заказ не найден", show_alert=True)
        return
    
    async with async_session() as session:
        executor = await session.scalar(
            select(User).where(User.tg_id == callback.from_user.id)
        )
        if not executor or executor.id != order.executor_id:
            await callback.answer(
                "Этот заказ не назначен вам", 
                show_alert=True
            )
            return
    
    try:
        await update_order_status(
            order_id, 
            settings.ORDER_STATUS_COMPLETED
        )
        
        # Уведомляем клиента
        user_tg_id = await get_user_tg_id(order.user_id)
        if user_tg_id:
            try:
                await callback.bot.send_message(
                    user_tg_id, 
                    f"Заказ #{order_id} выполнен! "
                    f"Теперь вы можете создать новый."
                )
            except Exception as e:
                logger.error(f"Failed to send message to user {user_tg_id}: {e}")
        
        await callback.message.edit_text(f"Заказ #{order_id} завершён.")
    except Exception as e:
        logger.exception(f"Error in complete_order: {e}")
        await callback.answer("Произошла ошибка. Попробуйте позже.", show_alert=True)
