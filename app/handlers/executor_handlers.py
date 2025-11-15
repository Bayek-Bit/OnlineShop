# File: /app/handlers/executor_handlers.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from app.database.requests import set_user, update_order_status
from app.database.models import async_session, Order, User
from app.settings.settings import settings
import app.keyboards.executor_kb as executor_kb
executor_router = Router()
@executor_router.message(Command("executor"))
async def register_executor(message: Message):
    await set_user(message.from_user.id, role="Executor")
    await message.answer("Вы зарегистрированы как исполнитель.")
# UPDATED: confirm_payment (используем callback.bot)
@executor_router.callback_query(F.data.startswith("confirm_payment_"))
async def confirm_payment(callback: CallbackQuery):
    await callback.answer('')
    order_id = int(callback.data.removeprefix("confirm_payment_"))
    await update_order_status(order_id, settings.ORDER_STATUS_IN_PROGRESS)
    # Уведомить клиента
    async with async_session() as session:
        order = await session.scalar(select(Order).where(Order.id == order_id))
        user_tg_id = (await session.scalar(select(User).where(User.id == order.user_id))).tg_id
    await callback.bot.send_message(user_tg_id, f"Оплата заказа #{order_id} подтверждена. Исполнитель приступил к работе.")
    await callback.message.edit_text(f"Заказ #{order_id} в работе.", reply_markup=executor_kb.complete_order_kb(order_id))
# UPDATED: decline_payment (используем callback.bot)
@executor_router.callback_query(F.data.startswith("decline_payment_"))
async def decline_payment(callback: CallbackQuery):
    await callback.answer('')
    order_id = int(callback.data.removeprefix("decline_payment_"))
    await update_order_status(order_id, settings.ORDER_STATUS_CANCELLED)
    # Уведомить клиента
    async with async_session() as session:
        order = await session.scalar(select(Order).where(Order.id == order_id))
        user_tg_id = (await session.scalar(select(User).where(User.id == order.user_id))).tg_id
    await callback.bot.send_message(user_tg_id, f"Оплата заказа #{order_id} отклонена. Свяжитесь с поддержкой.")
    await callback.message.edit_text(f"Заказ #{order_id} отменён.")
# UPDATED: complete_order (используем callback.bot)
@executor_router.callback_query(F.data.startswith("complete_order_"))
async def complete_order(callback: CallbackQuery):
    await callback.answer('')
    order_id = int(callback.data.removeprefix("complete_order_"))
    await update_order_status(order_id, settings.ORDER_STATUS_COMPLETED)
    # Уведомить клиента
    async with async_session() as session:
        order = await session.scalar(select(Order).where(Order.id == order_id))
        user_tg_id = (await session.scalar(select(User).where(User.id == order.user_id))).tg_id
    await callback.bot.send_message(user_tg_id, f"Заказ #{order_id} выполнен! Теперь вы можете создать новый.")
    await callback.message.edit_text(f"Заказ #{order_id} завершён.")