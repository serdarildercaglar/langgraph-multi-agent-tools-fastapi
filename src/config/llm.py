"""Shared LLM instance — tüm agent'lar buradan alır."""

from langchain_openai import ChatOpenAI

from src.config.settings import settings

llm = ChatOpenAI(
    base_url=settings.vllm_base_url,
    model=settings.vllm_model_name,
    api_key=settings.vllm_api_key,
)
