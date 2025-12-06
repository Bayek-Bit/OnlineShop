"""
Утилиты для валидации входных данных.
"""
import logging

from app.database.models import async_session, Item, Category, Order
from sqlalchemy import select

logger = logging.getLogger(__name__)


async def validate_product_id(product_id: int) -> bool:
    """
    Проверяет, существует ли товар с указанным ID.
    
    Args:
        product_id: ID товара
        
    Returns:
        True если товар существует, False в противном случае
    """
    if not isinstance(product_id, int) or product_id <= 0:
        return False
    
    try:
        async with async_session() as session:
            item = await session.scalar(
                select(Item).where(Item.id == product_id)
            )
            return item is not None
    except Exception as e:
        logger.error(f"Error validating product_id={product_id}: {e}")
        return False


async def validate_category_id(category_id: int) -> bool:
    """
    Проверяет, существует ли категория с указанным ID.
    
    Args:
        category_id: ID категории
        
    Returns:
        True если категория существует, False в противном случае
    """
    if not isinstance(category_id, int) or category_id <= 0:
        return False
    
    try:
        async with async_session() as session:
            category = await session.scalar(
                select(Category).where(Category.id == category_id)
            )
            return category is not None
    except Exception as e:
        logger.error(f"Error validating category_id={category_id}: {e}")
        return False


async def validate_order_id(order_id: int) -> bool:
    """
    Проверяет, существует ли заказ с указанным ID.
    
    Args:
        order_id: ID заказа
        
    Returns:
        True если заказ существует, False в противном случае
    """
    if not isinstance(order_id, int) or order_id <= 0:
        return False
    
    try:
        async with async_session() as session:
            order = await session.scalar(
                select(Order).where(Order.id == order_id)
            )
            return order is not None
    except Exception as e:
        logger.error(f"Error validating order_id={order_id}: {e}")
        return False


def validate_quantity(qty: int) -> bool:
    """
    Проверяет валидность количества товара.
    
    Args:
        qty: Количество
        
    Returns:
        True если количество валидно (1-10), False в противном случае
    """
    return isinstance(qty, int) and 1 <= qty <= 10


def parse_callback_data(data: str, prefix: str, expected_parts: int = 2) -> tuple[int, ...]:
    """
    Парсит callback_data и возвращает кортеж целых чисел.
    
    Args:
        data: Строка callback_data
        prefix: Префикс для удаления (например, "add_item_")
        expected_parts: Ожидаемое количество частей после префикса
        
    Returns:
        Кортеж целых чисел
        
    Raises:
        ValueError: Если формат данных неверный
    """
    try:
        parts_str = data[len(prefix):].split("_")
        if len(parts_str) != expected_parts:
            raise ValueError(
                f"Expected {expected_parts} parts, got {len(parts_str)}"
            )
        return tuple(map(int, parts_str))
    except (ValueError, IndexError) as e:
        raise ValueError(f"Invalid callback_data format: {data}") from e

