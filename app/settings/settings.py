from pydantic_settings import BaseSettings, SettingsConfigDict

# Время(секунды), после которого корзина клиента автоматически очистится в случае если он не оформит заказ
CART_TTL = 3600
# Время истечения срока хранения товаров в категориях
ITEMS_TTL = 3600
# Время на оплату заказа
PAYMENT_TIMEOUT = 600

# Константы статусов заказов
ORDER_STATUS_PENDING_PAYMENT = "pending_payment"
ORDER_STATUS_AWAITING_CONFIRMATION = "awaiting_executor_confirmation"
ORDER_STATUS_IN_PROGRESS = "in_progress"
ORDER_STATUS_COMPLETED = "completed"
ORDER_STATUS_CANCELLED = "cancelled"

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    TG_TOKEN: str
    DB_URL: str


settings = Settings()
