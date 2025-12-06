import re

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.database.requests import get_games, get_categories_by_game, get_items_by_category # db(sqlite for now)
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

async def games_kb():
    all_games = await get_games()
    kb = InlineKeyboardBuilder()
    # Если игр нет в базе данных
    if not all_games:
        kb.row(InlineKeyboardButton(text="Нет доступных игр", callback_data="main_menu"))
        return kb.as_markup()
    # Если игры есть
    for game in all_games:
        kb.row(InlineKeyboardButton(text=game.name, callback_data=f"game_{game.id}"))
    kb.row(InlineKeyboardButton(text="На главную", callback_data="main_menu"))
    return kb.as_markup()

async def categories_kb(game_id: int):
    all_categories = await get_categories_by_game(game_id)
    kb = InlineKeyboardBuilder()
    # Если категорий нет в базе данных
    if not all_categories:
        kb.row(InlineKeyboardButton(text="Нет категорий для этой игры", callback_data="back_to_games"))
        return kb.as_markup()
    # Если категории есть
    for category in all_categories:
        kb.row(InlineKeyboardButton(text=category.name, callback_data=f"category_{category.id}"))
    kb.row(InlineKeyboardButton(text="🔙 Назад к играм", callback_data="back_to_games"))
    kb.row(InlineKeyboardButton(text="На главную", callback_data="main_menu"))
    return kb.as_markup()


async def items_kb(user_id: int, category_id: int):
    """Рисует клавиатуру с доступными товарами."""
    category_items = await get_items_by_category(category_id)
    kb = InlineKeyboardBuilder()
    # Если товаров нет в базе данных
    if not category_items:
        kb.row(InlineKeyboardButton(text="Нет товаров в этой категории", callback_data="back_to_categories"))
        return kb.as_markup()
    # Если товары есть
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

    # Кнопки управления корзиной
    kb.row(
        InlineKeyboardButton(
            text="🛒 Корзина",
            callback_data="view_cart"
        ),
        InlineKeyboardButton(
            text="🗑 Сбросить",
            callback_data=f"reset_cart_category_{category_id}"
        )
    )

    # Навигация и подтверждение
    kb.row(
        InlineKeyboardButton(
            text="🔙 Назад к категориям", 
            callback_data="back_to_categories"
        ),
        InlineKeyboardButton(
            text="✅Подтвердить", 
            callback_data="create_order"
        )
    )
    return kb.as_markup()


async def cart_view_kb(category_id: int):
    """
    Клавиатура для просмотра корзины.
    
    Args:
        category_id: ID текущей категории для возврата
        
    Returns:
        InlineKeyboardMarkup с кнопками навигации
    """
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(
            text="🔙 Вернуться к товарам",
            callback_data=f"back_to_items_{category_id}"
        )
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
            # Убираем счетчик товаров - (xN)
            new_text = re.sub(r' \(.+\)', '', button.text)
            new_button = InlineKeyboardButton(
                text=new_text,
                callback_data=button.callback_data,
                url=button.url
            )
            new_row.append(new_button)
        new_kb.inline_keyboard.append(new_row)
    return new_kb

def payment_kb():
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="Оплатил", callback_data="paid"))
    return kb.as_markup()