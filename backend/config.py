from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    binance_testnet: bool = True

    main_label: str = "Principal"
    main_api_key: str = ""
    main_api_secret: str = ""

    sub_label: str = "Subcuenta"
    sub_api_key: str = ""
    sub_api_secret: str = ""

    host: str = "127.0.0.1"
    port: int = 8000


settings = Settings()
