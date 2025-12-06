"""
Модуль для работы с базой данных и Redis.

Содержит функции для:
- Работы с пользователями, играми, категориями и товарами
- Управления корзиной покупок (Redis)
- Создания и управления заказами
- Назначения исполнителей
"""
import json
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select, update
import redis.asyncio as redis
from redis.exceptions import (
    ConnectionError as RedisConnectionError,
    RedisError,
    TimeoutError as RedisTimeoutError
)
from aiogram import Bot

from app.database.models import (
    async_session, User, Game, Category, Item, Order
)
from app.settings.settings import settings

# Настройка логирования
logger = logging.getLogger(__name__)

# Подключение к Redis с настройками из конфигурации
try:
    r = redis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=settings.REDIS_DB,
        password=settings.REDIS_PASSWORD,
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
        retry_on_timeout=True
    )
except Exception as e:
    logger.error(f"Failed to connect to Redis: {e}")
    raise


# ==================== Работа с пользователями ====================

async def set_user(tg_id: int, role: str = "Client") -> bool:
    """
    Создает нового пользователя или возвращает False, если пользователь существует.
    
    Args:
        tg_id: Telegram ID пользователя
        role: Роль пользователя (Client или Executor)
        
    Returns:
        True если пользователь новый, False если уже существует
    """
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            session.add(User(tg_id=tg_id, role=role))
            await session.commit()
            return True
        return False


# ==================== Работа с играми, категориями и товарами ====================

async def get_games() -> list[Game]:
    """Возвращает список всех игр из базы данных."""
    async with async_session() as session:
        games = await session.scalars(select(Game))
        return games.all()


async def get_categories_by_game(game_id: int) -> list[Category]:
    """Возвращает список категорий для указанной игры."""
    async with async_session() as session:
        categories = await session.scalars(
            select(Category).where(Category.game_id == game_id)
        )
        return categories.all()


async def get_category_by_id(category_id: int) -> Optional[Category]:
    """Возвращает категорию по её ID или None, если категория не найдена."""
    async with async_session() as session:
        return await session.scalar(
            select(Category).where(Category.id == category_id)
        )


async def get_items_by_category(category_id: int) -> list[Item]:
    """
    Возвращает список товаров категории.
    
    Сначала проверяет кэш в Redis, если данных нет - 
    загружает из БД и сохраняет в Redis для последующих запросов.
    
    Args:
        category_id: ID категории
        
    Returns:
        Список товаров категории, отсортированный по ID
    """
    redis_key = f"category:{category_id}:items"
    cached_items = await r.hgetall(redis_key)
    
    # Если данные есть в кэше, возвращаем их
    if cached_items:
        items: list[Item] = []
        for item_id, item_json in cached_items.items():
            data = json.loads(item_json)
            items.append(Item(
                id=data["id"],
                category_id=category_id,
                name=data["name"],
                description=data.get("description"),
                price=data["price"]
            ))
        items.sort(key=lambda x: x.id)
        return items

    # Если данных нет в кэше, загружаем из БД
    async with async_session() as session:
        items_obj = await session.scalars(
            select(Item).where(Item.category_id == category_id)
        )
        items = items_obj.all()
    
    # Сохраняем в Redis для кэширования
    if items:
        mapping = {
            str(item.id): json.dumps({
                "id": item.id,
                "name": item.name,
                "description": item.description,
                "price": item.price
            }) for item in items
        }
        await r.hset(redis_key, mapping=mapping)
        await r.expire(redis_key, settings.ITEMS_TTL)
    
    return items


async def update_prices():
    """
    Обновляет цены на товары в Redis.
    
    Загружает все товары из БД и сохраняет их цены в Redis
    для быстрого доступа при подсчете суммы корзины.
    """
    try:
        async with async_session() as session:
            items = await session.scalars(select(Item))
            items = items.all()
            
            if not items:
                logger.warning("No items found in database for price update")
                return
            
            # Формируем словарь {item_id: price} для сохранения в Redis
            data = {str(item.id): str(item.price) for item in items}
            
            try:
                await r.delete("prices")
                if data:
                    await r.hset("prices", mapping=data)
                    logger.info(f"Updated prices for {len(data)} items in Redis")
                else:
                    logger.warning("Empty data dict for price update")
            except (RedisConnectionError, RedisError) as e:
                logger.error(f"Redis error in update_prices: {e}")
                raise
    except (RedisConnectionError, RedisError) as e:
        logger.error(f"Redis connection error in update_prices: {e}")
        raise
    except Exception as e:
        logger.exception(f"Unexpected error in update_prices: {e}")
        raise


# ==================== Работа с корзиной (Redis) ====================

async def add_to_cart(user_id: int, product_id: int, qty: int = 1):
    """
    Добавляет товар в корзину или увеличивает его количество.
    
    Максимальное количество одного товара в корзине - 10.
    
    Args:
        user_id: Telegram ID пользователя
        product_id: ID товара
        qty: Количество для добавления (по умолчанию 1)
        
    Raises:
        Exception: При ошибке работы с Redis
    """
    key = f"cart:{user_id}"
    product_id_str = str(product_id)

    try:
        # Получаем текущее количество товара в корзине
        current_qty_raw = await r.hget(key, product_id_str)
        if current_qty_raw:
            try:
                current_qty = int(str(current_qty_raw).strip())
            except (ValueError, AttributeError, TypeError):
                current_qty = 0
        else:
            current_qty = 0
        
        # Увеличиваем количество, но не более 10
        new_qty = min(current_qty + qty, 10)
        
        # Сохраняем в Redis
        await r.hset(key, product_id_str, str(new_qty))
        await r.expire(key, settings.CART_TTL)
            
    except (RedisConnectionError, RedisTimeoutError) as e:
        logger.error(f"Redis connection error in add_to_cart for "
                    f"user_id={user_id}, product_id={product_id}: {e}")
        raise
    except RedisError as e:
        logger.error(f"Redis error in add_to_cart for "
                    f"user_id={user_id}, product_id={product_id}: {e}")
        raise
    except Exception as e:
        logger.exception(f"Unexpected error in add_to_cart for "
                        f"user_id={user_id}, product_id={product_id}: {e}")
        raise


async def get_cart_item_qty(user_id: int, product_id: int) -> int:
    """
    Получает количество конкретного товара в корзине.
    
    Args:
        user_id: Telegram ID пользователя
        product_id: ID товара
        
    Returns:
        Количество товара в корзине (0 если товара нет)
    """
    try:
        qty = await r.hget(f"cart:{user_id}", str(product_id))
        if qty:
            try:
                return int(str(qty).strip())
            except (ValueError, TypeError, AttributeError):
                return 0
        return 0
    except (RedisConnectionError, RedisTimeoutError) as e:
        logger.error(f"Redis connection error in get_cart_item_qty for "
                    f"user_id={user_id}, product_id={product_id}: {e}")
        return 0
    except RedisError as e:
        logger.error(f"Redis error in get_cart_item_qty for "
                    f"user_id={user_id}, product_id={product_id}: {e}")
        return 0
    except Exception as e:
        logger.exception(f"Unexpected error in get_cart_item_qty for "
                        f"user_id={user_id}, product_id={product_id}: {e}")
        return 0


async def clear_cart(user_id: int):
    """
    Очищает корзину пользователя.
    
    Args:
        user_id: Telegram ID пользователя
        
    Raises:
        RedisError: При ошибке работы с Redis
    """
    try:
        await r.delete(f"cart:{user_id}")
    except (RedisConnectionError, RedisTimeoutError) as e:
        logger.error(f"Redis connection error in clear_cart for user_id={user_id}: {e}")
        raise
    except RedisError as e:
        logger.error(f"Redis error in clear_cart for user_id={user_id}: {e}")
        raise


async def get_cart_items_with_details(user_id: int) -> list[dict]:
    """
    Получает все товары из корзины с их деталями.
    
    Args:
        user_id: Telegram ID пользователя
        
    Returns:
        Список словарей с информацией о товарах:
        [
            {
                'product_id': int,
                'name': str,
                'category_name': str,
                'quantity': int,
                'price': int,
                'total': int
            },
            ...
        ]
    """
    cart = await r.hgetall(f"cart:{user_id}")
    if not cart:
        return []
    
    # Получаем цены из Redis
    prices = await r.hgetall("prices")
    if not prices:
        await update_prices()
        prices = await r.hgetall("prices")
    
    items_details = []
    
    async with async_session() as session:
        for pid_str, qty_str in cart.items():
            try:
                product_id = int(pid_str)
                qty = int(str(qty_str).strip())
                
                # Получаем информацию о товаре из БД
                item = await session.scalar(
                    select(Item).where(Item.id == product_id)
                )
                if not item:
                    continue
                
                # Получаем цену
                price_str = prices.get(pid_str)
                if not price_str:
                    # Если цены нет в Redis, используем цену из БД
                    price = item.price
                else:
                    price = int(str(price_str).strip())
                
                # Получаем название категории
                category = await session.scalar(
                    select(Category).where(Category.id == item.category_id)
                )
                category_name = category.name if category else "Неизвестно"
                
                items_details.append({
                    'product_id': product_id,
                    'name': item.name,
                    'category_name': category_name,
                    'quantity': qty,
                    'price': price,
                    'total': qty * price
                })
                
            except (ValueError, TypeError) as e:
                logger.warning(f"Error processing cart item pid={pid_str}, "
                             f"qty={qty_str}: {e}")
                continue
    
    return items_details


async def get_cart_game_id(user_id: int) -> Optional[int]:
    """
    Получает game_id всех товаров в корзине.
    
    Если все товары принадлежат одной игре, возвращает её ID.
    Если товары из разных игр или корзина пуста, возвращает None.
    
    Args:
        user_id: Telegram ID пользователя
        
    Returns:
        ID игры, если все товары из одной игры, иначе None
    """
    cart = await r.hgetall(f"cart:{user_id}")
    if not cart:
        return None
    
    game_ids = set()
    
    async with async_session() as session:
        for pid_str in cart.keys():
            try:
                product_id = int(pid_str)
                item = await session.scalar(
                    select(Item).where(Item.id == product_id)
                )
                if item:
                    category = await session.scalar(
                        select(Category).where(Category.id == item.category_id)
                    )
                    if category:
                        game_ids.add(category.game_id)
            except (ValueError, TypeError):
                continue
    
    # Если все товары из одной игры, возвращаем её ID
    if len(game_ids) == 1:
        return game_ids.pop()
    return None


async def get_cart_total(user_id: int) -> int:
    """
    Подсчитывает общую сумму корзины.
    
    Умножает количество каждого товара на его цену и суммирует.
    Если цены нет в Redis, обновляет их из БД.
    
    Args:
        user_id: Telegram ID пользователя
        
    Returns:
        Общая сумма корзины в рублях
    """
    cart = await r.hgetall(f"cart:{user_id}")
    if not cart:
        return 0

    # Получаем цены из Redis
    prices = await r.hgetall("prices")
    if not prices:
        await update_prices()
        prices = await r.hgetall("prices")
    
    total = 0

    for pid_str, qty_str in cart.items():
        try:
            qty = int(str(qty_str).strip())
            price_str = prices.get(pid_str)
            
            # Если цена не найдена, обновляем цены и пробуем снова
            if price_str is None:
                logger.warning(f"Price not found for product_id={pid_str}, "
                             f"updating prices...")
                try:
                    await update_prices()
                    prices = await r.hgetall("prices")
                    price_str = prices.get(pid_str)
                except (RedisConnectionError, RedisError) as e:
                    logger.error(f"Failed to update prices: {e}")
                    continue
                
                if price_str is None:
                    available_ids = list(prices.keys())[:10]
                    logger.warning(f"Price still not found for "
                                 f"product_id={pid_str} after update. "
                                 f"Available product IDs: {available_ids}")
                    continue
            
            try:
                price = int(str(price_str).strip())
                item_total = qty * price
                total += item_total
                logger.debug(f"Cart item: product_id={pid_str}, qty={qty}, "
                           f"price={price}, item_total={item_total}, total={total}")
            except (ValueError, TypeError) as e:
                logger.warning(f"Invalid price value for "
                             f"product_id={pid_str}: {price_str}, error: {e}")
                continue
                
        except (ValueError, TypeError) as e:
            logger.warning(f"Error processing cart item pid={pid_str}, "
                         f"qty={qty_str}: {e}")
            continue
        except (RedisConnectionError, RedisError) as e:
            logger.error(f"Redis error in get_cart_total: {e}")
            # Возвращаем текущую сумму, даже если не все товары обработаны
            break
    
    logger.debug(f"Final cart total for user_id={user_id}: {total}")
    return total


# ==================== Работа с заказами ====================

async def has_active_order(user_tg_id: int) -> bool:
    """
    Проверяет наличие активного заказа у пользователя.
    
    Активными считаются заказы со статусами:
    - pending_payment (ожидание оплаты)
    - awaiting_executor_confirmation (ожидание подтверждения исполнителем)
    - in_progress (в работе)
    
    Args:
        user_tg_id: Telegram ID пользователя
        
    Returns:
        True если есть активный заказ, False в противном случае
    """
    async with async_session() as session:
        user = await session.scalar(
            select(User).where(User.tg_id == user_tg_id)
        )
        if not user:
            return False
        
        active_statuses = [
            settings.ORDER_STATUS_PENDING_PAYMENT,
            settings.ORDER_STATUS_AWAITING_CONFIRMATION,
            settings.ORDER_STATUS_IN_PROGRESS
        ]
        
        active_orders = await session.scalars(
            select(Order).where(
                (Order.user_id == user.id) &
                (Order.status.in_(active_statuses))
            )
        )
        return bool(active_orders.first())


async def create_order_in_db(user_tg_id: int, total_sum: int) -> Order:
    """
    Создает новый заказ в базе данных.
    
    Args:
        user_tg_id: Telegram ID пользователя
        total_sum: Общая сумма заказа
        
    Returns:
        Созданный объект заказа
        
    Raises:
        ValueError: Если пользователь не найден
    """
    async with async_session() as session:
        user = await session.scalar(
            select(User).where(User.tg_id == user_tg_id)
        )
        if not user:
            raise ValueError("User not found")
        
        order = Order(
            user_id=user.id,
            total_sum=total_sum,
            expires_at=datetime.now(timezone.utc) + 
                       timedelta(seconds=settings.PAYMENT_TIMEOUT)
        )
        session.add(order)
        await session.commit()
        await session.refresh(order)
        return order


async def get_order_by_id(order_id: int) -> Optional[Order]:
    """Возвращает заказ по его ID или None, если заказ не найден."""
    async with async_session() as session:
        return await session.scalar(
            select(Order).where(Order.id == order_id)
        )


async def update_order_status(order_id: int, new_status: str):
    """Обновляет статус заказа."""
    async with async_session() as session:
        await session.execute(
            update(Order)
            .where(Order.id == order_id)
            .values(status=new_status)
        )
        await session.commit()


async def confirm_user_payment(order_id: int):
    """Отмечает, что пользователь подтвердил оплату заказа."""
    async with async_session() as session:
        await session.execute(
            update(Order)
            .where(Order.id == order_id)
            .values(payment_confirmed_by_user=True)
        )
        await session.commit()


# ==================== Работа с исполнителями ====================

async def assign_executor(order_id: int) -> bool:
    """
    Назначает свободного исполнителя на заказ.
    
    Свободным считается исполнитель, у которого нет заказов
    со статусом in_progress.
    
    Args:
        order_id: ID заказа
        
    Returns:
        True если исполнитель назначен, False если свободных нет
    """
    async with async_session() as session:
        # Находим свободного исполнителя (нет заказов in_progress)
        free_executor = await session.scalar(
            select(User).where(
                (User.role == "Executor") &
                ~User.id.in_(
                    select(Order.executor_id).where(
                        Order.status == settings.ORDER_STATUS_IN_PROGRESS
                    )
                )
            ).limit(1)
        )
        
        if not free_executor:
            return False
        
        # Назначаем исполнителя на заказ
        order = await session.scalar(
            select(Order).where(Order.id == order_id)
        )
        order.executor_id = free_executor.id
        order.status = settings.ORDER_STATUS_AWAITING_CONFIRMATION
        await session.commit()
        return True


async def retry_assign_executor(bot: Bot, order_id: int, user_tg_id: int):
    """
    Повторно пытается назначить исполнителя через 5 минут.
    
    Если исполнитель не найден, отменяет заказ и уведомляет пользователя.
    
    Args:
        bot: Экземпляр бота для отправки сообщений
        order_id: ID заказа
        user_tg_id: Telegram ID пользователя
    """
    await asyncio.sleep(300)  # 5 минут
    
    assigned = await assign_executor(order_id)
    if assigned:
        await bot.send_message(
            user_tg_id, 
            "Заказ назначен исполнителю!"
        )
    else:
        # Если всё ещё нет свободных исполнителей, отменяем заказ
        await update_order_status(
            order_id, 
            settings.ORDER_STATUS_CANCELLED
        )
        await bot.send_message(
            user_tg_id, 
            "Нет доступных исполнителей. Заказ отменён."
        )


async def get_user_tg_id(user_id: int) -> Optional[int]:
    """
    Получает Telegram ID пользователя по его ID в базе данных.
    
    Args:
        user_id: ID пользователя в БД
        
    Returns:
        Telegram ID пользователя или None, если пользователь не найден
    """
    async with async_session() as session:
        user = await session.scalar(
            select(User).where(User.id == user_id)
        )
        return user.tg_id if user else None


async def get_executor_tg_id_by_order(order_id: int) -> Optional[int]:
    """
    Получает Telegram ID исполнителя заказа.
    
    Args:
        order_id: ID заказа
        
    Returns:
        Telegram ID исполнителя или None, если заказ не найден
        или исполнитель не назначен
    """
    async with async_session() as session:
        order = await session.scalar(
            select(Order).where(Order.id == order_id)
        )
        if not order or not order.executor_id:
            return None
        
        executor = await session.scalar(
            select(User).where(User.id == order.executor_id)
        )
        return executor.tg_id if executor else None


async def check_payment_timeout(bot: Bot, order_id: int, user_tg_id: int):
    """
    Проверяет таймаут оплаты заказа.
    
    Если время истекло и оплата не подтверждена пользователем,
    отменяет заказ и уведомляет пользователя.
    
    Args:
        bot: Экземпляр бота для отправки сообщений
        order_id: ID заказа
        user_tg_id: Telegram ID пользователя
    """
    async with async_session() as session:
        order = await session.scalar(
            select(Order).where(Order.id == order_id)
        )
        if not order:
            return
        
        # Вычисляем время до истечения
        now = datetime.now(timezone.utc)
        if order.expires_at:
            # Убеждаемся, что expires_at имеет timezone
            # (для совместимости с SQLite, который может возвращать naive datetime)
            expires_at = order.expires_at
            if expires_at.tzinfo is None:
                # Если naive datetime, предполагаем что это UTC
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            
            time_until_expiry = (expires_at - now).total_seconds()
            if time_until_expiry > 0:
                await asyncio.sleep(time_until_expiry)
        
        # После ожидания проверяем актуальный статус заказа
        async with async_session() as session:
            order = await session.scalar(
                select(Order).where(Order.id == order_id)
            )
            if not order:
                return
            
            # Отменяем заказ, если оплата не подтверждена
            if (order.status == settings.ORDER_STATUS_PENDING_PAYMENT and 
                not order.payment_confirmed_by_user):
                await update_order_status(
                    order_id, 
                    settings.ORDER_STATUS_CANCELLED
                )
                try:
                    await bot.send_message(
                        user_tg_id, 
                        f"Время на оплату заказа #{order_id} истекло. "
                        f"Заказ отменён."
                    )
                except Exception:
                    # Игнорируем ошибки отправки сообщения
                    pass


# ==================== Заполнение базы данных ====================

async def populate_db():
    """
    Автозаполнение БД тестовыми данными.
    
    Создает игры, категории и товары для Genshin Impact и Brawl Stars.
    Функция идемпотентна - не создает дубликаты при повторном вызове.
    """
    async with async_session() as session:
        # Создание игр
        genshin_exists = await session.scalar(
            select(Game).where(Game.name == "Genshin Impact")
        )
        if not genshin_exists:
            genshin = Game(name="Genshin Impact")
            session.add(genshin)
            await session.flush()
            genshin_id = genshin.id
            print("Добавлена игра: Genshin Impact")
        else:
            genshin_id = genshin_exists.id
            print("Игра Genshin Impact уже существует")
        
        brawl_exists = await session.scalar(
            select(Game).where(Game.name == "Brawl Stars")
        )
        if not brawl_exists:
            brawl = Game(name="Brawl Stars")
            session.add(brawl)
            await session.flush()
            brawl_id = brawl.id
            print("Добавлена игра: Brawl Stars")
        else:
            brawl_id = brawl_exists.id
            print("Игра Brawl Stars уже существует")
        
        # Создание категорий
        genshin_cat_name = "Гемы (Genshin Impact)"
        genshin_cat_exists = await session.scalar(
            select(Category).where(
                (Category.name == genshin_cat_name) & 
                (Category.game_id == genshin_id)
            )
        )
        if not genshin_cat_exists:
            cat_genshin = Category(
                name=genshin_cat_name, 
                game_id=genshin_id
            )
            session.add(cat_genshin)
            await session.flush()
            cat_genshin_id = cat_genshin.id
            print("Добавлена категория: Гемы (Genshin Impact)")
        else:
            cat_genshin_id = genshin_cat_exists.id
            print("Категория Гемы (Genshin Impact) уже существует")
        
        brawl_cat_name = "Гемы (Brawl Stars)"
        brawl_cat_exists = await session.scalar(
            select(Category).where(
                (Category.name == brawl_cat_name) & 
                (Category.game_id == brawl_id)
            )
        )
        if not brawl_cat_exists:
            cat_brawl = Category(name=brawl_cat_name, game_id=brawl_id)
            session.add(cat_brawl)
            await session.flush()
            cat_brawl_id = cat_brawl.id
            print("Добавлена категория: Гемы (Brawl Stars)")
        else:
            cat_brawl_id = brawl_cat_exists.id
            print("Категория Гемы (Brawl Stars) уже существует")
        
        # Создание товаров для Genshin Impact
        genshin_items = [
            ("⭐ 60", 99),
            ("⭐ 300", 299),
            ("⭐ 980", 799),
            ("⭐ 1980", 1499),
            ("⭐ 3280", 2399),
            ("⭐ 6480", 4499),
        ]
        added_genshin = 0
        for name, price in genshin_items:
            item_exists = await session.scalar(
                select(Item).where(
                    (Item.category_id == cat_genshin_id) & 
                    (Item.name == name)
                )
            )
            if not item_exists:
                item = Item(
                    category_id=cat_genshin_id, 
                    name=name, 
                    price=price
                )
                session.add(item)
                added_genshin += 1
        print(f"Добавлено {added_genshin} товаров для Genshin")
        
        # Создание товаров для Brawl Stars
        brawl_items = [
            ("170 Gems", 99),
            ("500 Gems", 249),
            ("1100 Gems", 499),
            ("2400 Gems", 999),
            ("5000 Gems", 1999),
        ]
        added_brawl = 0
        for name, price in brawl_items:
            item_exists = await session.scalar(
                select(Item).where(
                    (Item.category_id == cat_brawl_id) & 
                    (Item.name == name)
                )
            )
            if not item_exists:
                item = Item(
                    category_id=cat_brawl_id, 
                    name=name, 
                    price=price
                )
                session.add(item)
                added_brawl += 1
        print(f"Добавлено {added_brawl} товаров для Brawl Stars")
        
        await session.commit()
        print("База данных успешно заполнена!")
