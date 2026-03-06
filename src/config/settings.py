from pydantic import model_validator
from pydantic_settings import BaseSettings


def _fetch_vault_secret(key: str) -> str:
    """Vault'tan secret çeker. TODO: Vault client entegrasyonunu buraya ekle."""
    return "vault-dummy-secret"


class Settings(BaseSettings):
    """Application settings — all values from .env, no hardcoded defaults."""

    # vLLM
    vllm_base_url: str
    vllm_model_name: str
    vllm_api_key: str

    # Langfuse
    langfuse_public_key: str
    langfuse_secret_key: str
    langfuse_host: str
    langfuse_enabled: bool
    langfuse_prompt_management_enabled: bool
    langfuse_prompt_cache_ttl: int

    # App
    app_env: str
    app_port: int
    chat_history_enabled: bool
    chat_history_max_tokens: int

    # Gateway (Vault'tan çekilir)
    gateway_secret: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}

    @model_validator(mode="after")
    def fetch_secrets_from_vault(self):
        self.gateway_secret = _fetch_vault_secret("gateway_secret")
        return self


settings = Settings()
