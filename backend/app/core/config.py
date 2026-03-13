from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "InvestIQ"
    debug: bool = False

    # Database
    database_url: str = "postgresql+asyncpg://investiq:investiq@db.mase.fi:5432/investiq"

    # CORS
    cors_origins: list[str] = ["http://localhost:5173"]

    # Data refresh intervals (minutes)
    index_refresh_interval: int = 15  # 1m OHLCV fetch for indices
    data_refresh_interval: int = 60   # Fund NAV refresh

    model_config = {"env_file": ".env", "env_prefix": "INVESTIQ_"}


settings = Settings()
