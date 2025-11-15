# File: /app/settings/settings.py
from pydantic_settings import BaseSettings, SettingsConfigDict

# UPDATED: Переместил константы внутрь класса как дефолтные атрибуты с типами
CART_TTL: int = 3600  # Время(секунды), после которого корзина клиента автоматически очистится
ITEMS_TTL: int = 3600  # Время истечения срока хранения товаров в категориях
PAYMENT_TIMEOUT: int = 600  # Время на оплату заказа в секундах (по умолчанию 10 минут)

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
    TG_TOKEN: str
    DB_URL: str
    ORDER_STATUS_PENDING_PAYMENT: str = "pending_payment"
    ORDER_STATUS_AWAITING_CONFIRMATION: str = "awaiting_executor_confirmation"
    ORDER_STATUS_IN_PROGRESS: str = "in_progress"
    ORDER_STATUS_COMPLETED: str = "completed"
    ORDER_STATUS_CANCELLED: str = "cancelled"
settings = Settings()