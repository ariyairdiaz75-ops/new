from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    binance_testnet: bool = True

    main_label: str = "Cuenta A"
    main_api_key: str = ""
    main_api_secret: str = ""

    sub_label: str = "Cuenta B"
    sub_api_key: str = ""
    sub_api_secret: str = ""

    # Token propio para proteger el panel/API cuando el servidor está
    # público en internet (Railway). Se manda como header X-Dashboard-Token
    # o como ?token= en el websocket. Si queda vacío, NO se exige token
    # (solo recomendado para correr en tu propia máquina, 127.0.0.1).
    dashboard_token: str = ""

    host: str = "127.0.0.1"
    port: int = 8000


settings = Settings()
