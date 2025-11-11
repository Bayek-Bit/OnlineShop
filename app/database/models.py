from datetime import datetime
from sqlalchemy import String, BigInteger, Integer, ForeignKey, DateTime
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


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, nullable=False)
    name: Mapped[str] = mapped_column(String(25), unique=True, nullable=False)
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
    user: Mapped[int] = relationship("User", foreign_keys=[user_id])
    total_sum: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(25), default="pending_payment", nullable=False)
    executor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True)
    executor: Mapped["User"] = relationship("User", foreign_keys=[executor_id])
    # время создания
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now(), nullable=False)
    # дедлайн оплаты
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

async def create_tables():
    async with engine.begin() as conn:
        # await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)