from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.database.requests import get_categories, get_items_by_category # db(sqlite for now)
from app.database.requests import get_cart_item_qty # redis
from app.settings.messages import reviews_channel, main_channel


menu = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Каталог ✨", callback_data="catalog")],
    [InlineKeyboardButton(text="О нас", callback_data="about")]
])

about_us = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="Наш канал 🪄", url=main_channel),
        InlineKeyboardButton(text="Отзывы 📗", url=reviews_channel)
     ]
])

async def categories_kb():
    all_categories = await get_categories()
    kb = InlineKeyboardBuilder()
    for category in all_categories:
        print(category.name)
        kb.row(InlineKeyboardButton(text=category.name, callback_data=f"category_{category.id}"))
    kb.row(InlineKeyboardButton(text="На главную", callback_data="main_menu"))
    return kb.as_markup()


async def items_kb(user_id: int, category_id: int):
    """Рисует клавиатуру с доступными товарами."""
    category_items = await get_items_by_category(category_id)
    kb = InlineKeyboardBuilder()
    for item in category_items:
        # Ищем в redis количество выбранного товара (0 - если нет)
        # Не добавляем "Товар (xКол-во)" в случае, если товар не был выбран хоть раз
        count = await get_cart_item_qty(user_id, item.id)
        if count > 0:
            button_text = f"{item.name} (x{count})" # Товар (xКоличество выбранного товара)
        else:
            button_text = item.name

        kb.row(InlineKeyboardButton(
            text=button_text,
            callback_data=f"add_item_{category_id}_{item.id}"
        ))

    # Передаем category_id, чтобы отобразить новую клавиатуру с товарами этой категории
    kb.row(InlineKeyboardButton(
        text="🗑 Сбросить корзину",
        callback_data=f"reset_cart_category_{category_id}"
        )
    )

    kb.row(
        InlineKeyboardButton(text="🏠На главную", callback_data="catalog"),
        InlineKeyboardButton(text="✅ Подтвердить", callback_data="create_order")
    )
    return kb.as_markup()


async def reset_items_count(markup: InlineKeyboardMarkup) -> InlineKeyboardMarkup:
    """
    Возвращает клавиатуру с товарами без счетчиков возле названия товара.
    Input: Item (x1)
    Output: Item
    """
    new_kb = InlineKeyboardMarkup(inline_keyboard=[])
    for row in markup.inline_keyboard:
        new_row = []
        for button in row:
            new_text = button.text.split(" (x")[0] if "(x" in button.text else button.text
            new_button = InlineKeyboardButton(
                text=new_text,
                callback_data=button.callback_data,
                url=button.url
            )
            new_row.append(new_button)
        new_kb.inline_keyboard.append(new_row)
    return new_kb
