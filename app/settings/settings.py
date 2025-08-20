from pydantic_settings import BaseSettings, SettingsConfigDict

# Время, после которого корзина клиента автоматически очистится в случае если он не оформит заказ
CART_TTL = 3600


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    TG_TOKEN: str
    DB_URL: str


settings = Settings()
