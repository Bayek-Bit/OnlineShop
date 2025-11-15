from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def confirm_payment_kb(order_id: int):
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="Подтвердить оплату", callback_data=f"confirm_payment_{order_id}"))
    kb.row(InlineKeyboardButton(text="Отклонить", callback_data=f"decline_payment_{order_id}"))
    return kb.as_markup()

def complete_order_kb(order_id: int):
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="Завершить заказ", callback_data=f"complete_order_{order_id}"))
    return kb.as_markup()