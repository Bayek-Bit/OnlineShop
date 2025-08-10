from app.database.models import async_session, User, Category, Item
from sqlalchemy import select, update, delete


async def set_user(tg_id):
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))

        if not user:
            session.add(User(tg_id=tg_id, role="Client"))
            await session.commit()


async def get_categories():
    async with async_session() as session:
        categories = await session.scalars(select(Category))
        return categories.all()


async def get_items_by_category(category_id):
    async with async_session() as session:
        items = await session.scalars(select(Item).where(Item.category_id == category_id))
        return items.all()
