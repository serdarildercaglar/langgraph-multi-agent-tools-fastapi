from pydantic_settings import BaseSettings


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

    # App
    app_env: str
    app_port: int
    chat_history_enabled: bool
    chat_history_max_tokens: int

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
