"""
Настройки приложения.

Все настройки загружаются из переменных окружения или .env файла.
"""
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки приложения."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8"
    )
    
    # Telegram
    TG_TOKEN: str
    
    # Database
    DB_URL: str
    
    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    
    # TTLs (Time To Live)
    CART_TTL: int = 3600  # Время жизни корзины в секундах
    ITEMS_TTL: int = 3600  # Время жизни кэша товаров в секундах
    PAYMENT_TIMEOUT: int = 600  # Время на оплату заказа в секундах (10 минут)
    
    # Order statuses
    ORDER_STATUS_PENDING_PAYMENT: str = "pending_payment"
    ORDER_STATUS_AWAITING_CONFIRMATION: str = "awaiting_executor_confirmation"
    ORDER_STATUS_IN_PROGRESS: str = "in_progress"
    ORDER_STATUS_COMPLETED: str = "completed"
    ORDER_STATUS_CANCELLED: str = "cancelled"
    
    # Admin IDs (для проверки прав доступа)
    ADMIN_IDS: list[int] = []


settings = Settings()

# Для обратной совместимости (можно удалить после обновления всех импортов)
CART_TTL = settings.CART_TTL
ITEMS_TTL = settings.ITEMS_TTL
PAYMENT_TIMEOUT = settings.PAYMENT_TIMEOUT