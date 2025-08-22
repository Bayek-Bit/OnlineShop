from pydantic_settings import BaseSettings, SettingsConfigDict

# Время(секунды), после которого корзина клиента автоматически очистится в случае если он не оформит заказ
CART_TTL = 3600
# Время истечения срока хранения товаров в категориях
ITEMS_TTL = 3600

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    TG_TOKEN: str
    DB_URL: str


settings = Settings()
