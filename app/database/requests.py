import json

from app.database.models import async_session, User, Game, Category, Item
from sqlalchemy import select, update, delete
import redis.asyncio as redis

from app.settings.settings import CART_TTL, ITEMS_TTL


r = redis.Redis(host="localhost", port=6379, decode_responses=True)


async def set_user(tg_id):
    """Returns True if user is new. False if exists"""
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))

        if not user:
            session.add(User(tg_id=tg_id, role="Client"))
            await session.commit()
            return True
        return False


async def get_games():
    async with async_session() as session:
        games = await session.scalars(select(Game))
        return games.all()


async def get_categories_by_game(game_id: int):
    async with async_session() as session:
        categories = await session.scalars(select(Category).where(Category.game_id == game_id))
        return categories.all()


async def get_items_by_category(category_id: int) -> list[Item]:
    """
    Возвращает список товаров категории.
    Сначала проверяет Redis, если нет – берёт из БД и кладёт в Redis.
    """
    redis_key = f"category:{category_id}:items"
    cached_items = await r.hgetall(redis_key) # {"ID": 'json'}
    # Example: "1": '{"id":1,"name":"Gems 400","price":199,"description":"..."}'

    if cached_items:
        items: list[Item] = []
        # Декодируем json
        for item_id, item_json in cached_items.items():
            data = json.loads(item_json)
            items.append(Item(
                id=data["id"],
                category_id=category_id,
                name=data["name"],
                description=data.get("description"),
                price=data["price"]
                )
            )
        # Так как мы получаем json обьект из хеша, он не упорядочен, поэтому сортируем по id
        items.sort(key=lambda x: x.id)
        return items

    # Если нет в redis - тащим из основной БД.
    async with async_session() as session:
        items_obj = await session.scalars(
            select(Item).where(Item.category_id == category_id)
        )
        items = items_obj.all()

    # Кладем в redis как json
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
        await r.expire(redis_key, ITEMS_TTL)

    return items


async def update_prices():
    """Обновление цен на товары в редисе"""
    async with async_session() as session:
        items = await session.scalars(select(Item))
        items = items.all()
        data = {str(item.id): str(item.price) for item in items}
        await r.delete("prices")
        if data:
            await r.hset("prices", mapping=data)


async def add_to_cart(user_id: int, product_id: int, qty: int = 1):
    """Добавить товар в корзину(увеличить количество на 1)"""
    key = f"cart:{user_id}"
    current_qty_raw = await r.hget(key, str(product_id))
    current_qty = int(current_qty_raw) if current_qty_raw else 0
    # Количество товара не превышает 10 единиц.
    new_qty = min(current_qty + qty, 10)
    # hset принимает value типом str
    new_qty = str(new_qty)

    await r.hset(key, str(product_id), new_qty)
    await r.expire(key, CART_TTL)



async def get_cart_item_qty(user_id: int, product_id: int):
    """Получить количество конкретного товара"""
    qty = await r.hget(f"cart:{user_id}", str(product_id))
    return int(qty) if qty else 0


async def clear_cart(user_id: int):
    """Очистить корзину"""
    await r.delete(f"cart:{user_id}")


async def get_cart_total(user_id: int):
    """Подсчёт общей суммы корзины"""
    cart = await r.hgetall(f"cart:{user_id}")
    if not cart:
        return 0

    prices = await r.hgetall("prices")
    if not prices:
        await update_prices()
        prices = await r.hgetall("prices")
    total = 0

    for pid_str, qty_str in cart.items():
        try:
            qty = int(qty_str)
            price = int(prices.get(pid_str, '0'))
        except ValueError:
            continue
        total += qty * price
    return total

async def populate_db():
    """Автозаполнение БД тестовыми данными (idempotently)."""
    async with async_session() as session:
        # Игры
        genshin_exists = await session.scalar(select(Game).where(Game.name == "Genshin Impact"))
        if not genshin_exists:
            genshin = Game(name="Genshin Impact")
            session.add(genshin)
            await session.flush()
            genshin_id = genshin.id
            print("Добавлена игра: Genshin Impact")
        else:
            genshin_id = genshin_exists.id
            print("Игра Genshin Impact уже существует")

        brawl_exists = await session.scalar(select(Game).where(Game.name == "Brawl Stars"))
        if not brawl_exists:
            brawl = Game(name="Brawl Stars")
            session.add(brawl)
            await session.flush()
            brawl_id = brawl.id
            print("Добавлена игра: Brawl Stars")
        else:
            brawl_id = brawl_exists.id
            print("Игра Brawl Stars уже существует")

        # Категории (unique names из-за модели)
        genshin_cat_name = "Гемы (Genshin Impact)"
        genshin_cat_exists = await session.scalar(
            select(Category).where((Category.name == genshin_cat_name) & (Category.game_id == genshin_id))
        )
        if not genshin_cat_exists:
            cat_genshin = Category(name=genshin_cat_name, game_id=genshin_id)
            session.add(cat_genshin)
            await session.flush()
            cat_genshin_id = cat_genshin.id
            print("Добавлена категория: Гемы (Genshin Impact)")
        else:
            cat_genshin_id = genshin_cat_exists.id
            print("Категория Гемы (Genshin Impact) уже существует")

        brawl_cat_name = "Гемы (Brawl Stars)"
        brawl_cat_exists = await session.scalar(
            select(Category).where((Category.name == brawl_cat_name) & (Category.game_id == brawl_id))
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

        # Товары Genshin Impact (⭐ + количество)
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
                select(Item).where((Item.category_id == cat_genshin_id) & (Item.name == name))
            )
            if not item_exists:
                item = Item(category_id=cat_genshin_id, name=name, price=price)
                session.add(item)
                added_genshin += 1
        print(f"Добавлено {added_genshin} товаров для Genshin")

        # Товары Brawl Stars (количество + Gems)
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
                select(Item).where((Item.category_id == cat_brawl_id) & (Item.name == name))
            )
            if not item_exists:
                item = Item(category_id=cat_brawl_id, name=name, price=price)
                session.add(item)
                added_brawl += 1
        print(f"Добавлено {added_brawl} товаров для Brawl Stars")

        await session.commit()
        print("База данных успешно заполнена!")