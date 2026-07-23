from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    test_database_url: str
    secret_key: str
    access_token_expire_minutes: int = 720
    student_token_expire_minutes: int = 120


@lru_cache
def get_settings() -> Settings:
    return Settings()
