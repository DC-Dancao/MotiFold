from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "Motifold"
    DATABASE_URL: str = "postgresql+asyncpg://user:password@postgres:5432/motifold"
    REDIS_URL: str = "redis://redis:6379/0"
    SECRET_KEY: str = "supersecretkey"  # Change in production
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    COOKIE_SECURE: bool = False
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = ""
    OPENAI_MODEL_MAX: str = "gpt-4o"
    OPENAI_MODEL_PRO: str = "gpt-4o"
    OPENAI_MODEL_MINI: str = "gpt-4o-mini"

    # Comma-separated list or JSON array
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://localhost:13000",
        "http://localhost:18000",
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            v = v.strip()
            # Support JSON array: CORS_ORIGINS='["http://a.com","http://b.com"]'
            if v.startswith("["):
                import json as _json
                try:
                    return _json.loads(v)
                except _json.JSONDecodeError:
                    raise ValueError(f"Invalid JSON string format for CORS_ORIGINS: {v}")
            # Support comma-separated: CORS_ORIGINS=http://a.com,http://b.com
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
