from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    openai_api_key: str
    supabase_admin_url: str
    supabase_readonly_url: str
    supabase_url: str
    supabase_service_role_key: str
    supabase_jwt_secret: str
    upstash_redis_rest_url: str
    upstash_redis_rest_token: str
    frontend_origin: str = "http://localhost:3000"
    admin_emails: str = ""
    local_development: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
