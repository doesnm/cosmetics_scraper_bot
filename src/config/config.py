from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False
    )

    # Telegram
    api_id: int = Field(default=12345678)
    api_hash: str = Field(default="some_hash")
    phone_number: str = Field(default="some_phone_number")
    source_channel_id: int = Field(default=-1001581271251)
    target_channel_id: int = Field(default=-1001234567890)

    # Gemini
    gemini_api_key: str = Field(default="some_key")
    gemini_model: str = Field(default="gemini-2.0-flash-lite")

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/cosmetics"
    )


settings = Settings()

