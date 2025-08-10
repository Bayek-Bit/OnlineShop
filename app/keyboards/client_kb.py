from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.database.requests import get_categories, get_items_by_category
from app.settings.messages import reviews_channel, main_channel


menu = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Каталог ✨", callback_data="catalog")],
    [InlineKeyboardButton(text="Наш канал 🪄", url=main_channel), InlineKeyboardButton(text="Отзывы 📗", url=reviews_channel)]
])

async def categories_kb():
    all_categories = await get_categories()
    kb = InlineKeyboardBuilder()
    for category in all_categories:
        print(category.name)
        kb.row(InlineKeyboardButton(text=category.name, callback_data=f"category_{category.id}"))
    kb.row(InlineKeyboardButton(text="На главную", callback_data="main_menu"))
    return kb.as_markup()


async def items_kb(category_id: int):
    category_items_kb = await get_items_by_category(category_id)
    kb = InlineKeyboardBuilder()
    for item in category_items_kb:
        kb.row(InlineKeyboardButton(text=item.name, callback_data=f"item_{item.id}"))
    kb.row(InlineKeyboardButton(text="На главную", callback_data="catalog"))
    return kb.as_markup()