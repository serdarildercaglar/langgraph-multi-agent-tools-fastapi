"""Langfuse prompt management middleware — runtime'da system prompt çeker.

Her LLM çağrısında agent adını tespit eder, Langfuse'dan ilgili prompt'u çeker
ve system message'ı override eder. Cache TTL default 60s (stale-while-revalidate).
Langfuse erişilemezse hardcoded fallback prompt ile devam eder.
"""

import logging

from langchain.agents.middleware import wrap_model_call
from langchain_core.messages import SystemMessage
from langgraph.config import get_config

from src.config.settings import settings

logger = logging.getLogger(__name__)

_langfuse_client = None


def _get_langfuse_client():
    """Return a cached Langfuse client instance (lazy init)."""
    global _langfuse_client
    if _langfuse_client is None:
        from langfuse import Langfuse

        _langfuse_client = Langfuse()
    return _langfuse_client


@wrap_model_call
async def langfuse_prompt(request, handler):
    """Fetch the Langfuse prompt for the current agent and override system_message.

    Agent name: get_config()["metadata"]["lc_agent_name"] (create_agent name= ile set edilir).
    Fallback: mevcut system_message (hardcoded prompt).
    """
    try:
        config = get_config()
        agent_name = config["metadata"]["lc_agent_name"]
    except (KeyError, TypeError):
        logger.debug("Could not resolve agent name from config, skipping prompt override")
        return await handler(request)

    fallback_text = request.system_message.content if request.system_message else ""

    try:
        client = _get_langfuse_client()
        prompt = client.get_prompt(
            agent_name,
            fallback=fallback_text,
            cache_ttl_seconds=settings.langfuse_prompt_cache_ttl,
        )

        if prompt.is_fallback:
            logger.warning("Using fallback prompt for %r — Langfuse unreachable", agent_name)

        compiled = prompt.compile()
        request = request.override(system_message=SystemMessage(content=compiled))
    except Exception:
        logger.warning(
            "Langfuse prompt fetch failed for %r, using existing system_prompt",
            agent_name,
            exc_info=True,
        )

    return await handler(request)


def warm_prompt_cache(agents: dict) -> None:
    """Pre-fetch prompts at startup to avoid cold-cache blocking on first request.

    Args:
        agents: AGENTS dict from providers.py. Her entry'nin "agent" key'inde
                compiled agent objesi bulunur; agent.name Langfuse prompt adı olarak kullanılır.
    """
    client = _get_langfuse_client()
    for entry in agents.values():
        agent = entry["agent"]
        name = agent.name
        if not name:
            continue
        try:
            client.get_prompt(
                name,
                fallback="",
                cache_ttl_seconds=settings.langfuse_prompt_cache_ttl,
            )
            logger.info("Warmed Langfuse prompt cache for %r", name)
        except Exception:
            logger.warning("Failed to warm prompt cache for %r", name, exc_info=True)
