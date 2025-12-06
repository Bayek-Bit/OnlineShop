from datetime import datetime, timezone, timedelta
from sqlalchemy import String, BigInteger, Integer, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship, DeclarativeBase
from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine

from app.settings.settings import settings


engine = create_async_engine(url=settings.DB_URL, echo=True)

async_session = async_sessionmaker(engine)


class Base(AsyncAttrs, DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, nullable=False)
    tg_id = mapped_column(BigInteger, unique=True, nullable=False)
    role: Mapped[str] = mapped_column(String(25), nullable=False)
    # Активные заказы для клиента и исполнителя
    orders_as_client: Mapped[list["Order"]] = relationship("Order",
                                                            foreign_keys="Order.user_id",
                                                            back_populates="user")
    orders_as_executor: Mapped[list["Order"]] = relationship("Order",
                                                            foreign_keys="Order.executor_id",
                                                            back_populates="executor")


class Game(Base):
    __tablename__ = "games"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, nullable=False)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    categories: Mapped[list["Category"]] = relationship("Category", back_populates="game")

class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, nullable=False)
    name: Mapped[str] = mapped_column(String(25), unique=True, nullable=False)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), nullable=False)
    game: Mapped["Game"] = relationship("Game", back_populates="categories")
    items: Mapped[list["Item"]] = relationship("Item", back_populates="category")

class Item(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, nullable=False)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), nullable=False)
    category: Mapped["Category"] = relationship("Category", back_populates="items")
    name: Mapped[str] = mapped_column(String(25), nullable=False)
    description: Mapped[str] = mapped_column(String(512), nullable=True)
    price: Mapped[int] = mapped_column(Integer, nullable=False)

class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    total_sum: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(25), default=settings.ORDER_STATUS_PENDING_PAYMENT, nullable=False)
    executor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True)
    executor: Mapped["User"] = relationship("User", foreign_keys=[executor_id])
    # время создания
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    # дедлайн оплаты
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    # подтверждение оплаты клиентом
    payment_confirmed_by_user: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

async def create_tables(drop_existing: bool = False):
    """
    Создает таблицы в базе данных.
    
    Args:
        drop_existing: Если True, удаляет существующие таблицы перед созданием.
                      ВНИМАНИЕ: Это удалит все данные! Используйте только для разработки.
    
    Warning:
        Никогда не используйте drop_existing=True в продакшене!
    """
    async with engine.begin() as conn:
        if drop_existing:
            await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)