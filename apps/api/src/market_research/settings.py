"""Backend-only environment settings; secret values are excluded from repr."""
from pydantic import SecretStr, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")
    nebius_api_key: SecretStr | None = None
    nebius_model: str | None = None
    tavily_api_key: SecretStr | None = None
    sec_user_agent: str | None = Field(default=None, repr=False)
    provider_timeout_seconds: float = Field(default=30, gt=0, le=120)
