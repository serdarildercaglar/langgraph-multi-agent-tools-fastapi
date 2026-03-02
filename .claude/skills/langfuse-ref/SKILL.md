---
name: langfuse-ref
description: Langfuse 3.14.5 integration reference for LangChain agents. Use when configuring observability, tracing, or debugging Langfuse integration.
user-invocable: false
---

# Langfuse 3.14.5 Quick Reference

## LangChain Integration

```python
from langfuse.langchain import CallbackHandler

# No constructor args — config via env vars
handler = CallbackHandler()

# Pass to agent via config
result = await agent.ainvoke(
    {"messages": [...]},
    config={"callbacks": [handler]}
)
```

**IMPORTANT:** Import from `langfuse.langchain` (NOT `langfuse.callback` — that's v2).

## Environment Variables

| Variable | Example |
|---|---|
| `LANGFUSE_SECRET_KEY` | `sk-lf-...` |
| `LANGFUSE_PUBLIC_KEY` | `pk-lf-...` |
| `LANGFUSE_HOST` | `https://cloud.langfuse.com` |

No constructor arguments needed when env vars are set.

## Metadata Passing

Use `langfuse_` prefixed keys in LangChain config metadata:

```python
config = {
    "callbacks": [handler],
    "metadata": {
        "langfuse_user_id": "user-123",
        "langfuse_session_id": "session-456",
        "langfuse_tags": ["production"],
    },
}
```

## Observe Decorator (for custom functions)

```python
from langfuse import observe

@observe(name="my-operation")
async def my_function():
    # Automatically traced
    pass

# Disable I/O capture for sensitive data
@observe(capture_input=False, capture_output=False)
async def sensitive_function():
    pass
```

## Client Lifecycle (FastAPI)

```python
from langfuse import get_client

langfuse = get_client()    # Singleton
langfuse.flush()           # Send buffered observations
langfuse.shutdown()        # Flush + terminate threads (call on app shutdown)
```

## v3 Breaking Changes from v2

| Area | v2 | v3 |
|---|---|---|
| Import | `langfuse.callback` | `langfuse.langchain` |
| Client | `Langfuse()` | `get_client()` singleton |
| Trace | `langfuse.trace()` | `start_as_current_observation()` |
| Init | `enabled` param | `tracing_enabled` param |

## This Project's Pattern

In `src/providers.py`:
```python
def get_langfuse_handler(user_id, session_id, ...):
    if not settings.langfuse_enabled:
        return {}
    handler = CallbackHandler()
    config = {
        "callbacks": [handler],
        "metadata": {
            "langfuse_user_id": user_id,
            "langfuse_session_id": session_id,
        },
    }
    return config
```

Toggle via `LANGFUSE_ENABLED` env var. Handler merged with agent config in router.

## Prompt Management (runtime system prompts)

Agent system prompt'ları Langfuse'dan runtime'da çekilir. `src/middleware/prompt.py`:

```python
from langfuse import Langfuse

client = Langfuse()  # lazy init, env vars ile config

# Fetch with cache (60s TTL, stale-while-revalidate)
prompt = client.get_prompt(
    "agent_name",                    # = create_agent(name=...) değeri
    fallback="hardcoded fallback",   # Langfuse çökerse
    cache_ttl_seconds=60,            # .env'den LANGFUSE_PROMPT_CACHE_TTL
)
compiled = prompt.compile()          # str döner (text type)
prompt.is_fallback                   # True ise Langfuse erişilemedi
```

### Cache Davranışı (kaynak koddan doğrulanmış)

| Senaryo | Ne olur | Event loop bloklar mı? |
|---|---|---|
| Cache sıcak (<TTL) | `dict.get()` + timestamp check | Hayır (~μs) |
| Cache expire (stale) | Stale döner + daemon thread'de HTTP refresh | Hayır (~μs) |
| Cache boş (ilk çağrı) | Blocking `httpx.request()` | EVET — startup'ta ısıt! |

### Startup Warm (main.py lifespan)

```python
if settings.langfuse_prompt_management_enabled:
    from src.middleware.prompt import warm_prompt_cache
    warm_prompt_cache(AGENTS)
```

### Middleware Pattern

```python
@wrap_model_call
async def langfuse_prompt(request, handler):
    agent_name = get_config()["metadata"]["lc_agent_name"]
    prompt = client.get_prompt(agent_name, fallback=..., cache_ttl_seconds=...)
    return await handler(request.override(system_message=SystemMessage(content=prompt.compile())))
```

**Not:** `async def` zorunlu — agent'lar `ainvoke` ile çağrıldığında `@wrap_model_call` decorator async fonksiyon bekler (`awrap_model_call` hook). Sync `def` kullanılırsa `NotImplementedError` fırlatılır.

### get_prompt API (doğrulanmış, langfuse 3.14.5)

```python
def get_prompt(
    name: str,
    *,
    version: int | None = None,        # Belirli versiyon
    label: str | None = None,          # "production" (default), "staging", "latest"
    type: Literal["chat", "text"] = "text",
    cache_ttl_seconds: int | None = None,  # Default 60s, 0 = cache kapalı
    fallback: str | list | None = None,    # Langfuse çökerse
    max_retries: int | None = None,        # Default 2, max 4
    fetch_timeout_seconds: int | None = None,  # Default 5s
) -> PromptClient
```

### Env Vars

```
LANGFUSE_PROMPT_MANAGEMENT_ENABLED=true
LANGFUSE_PROMPT_CACHE_TTL=60
```

### Konvansyon

Langfuse prompt adı = `create_agent(name=...)` değeri:
- `main_agent` → Langfuse'da "main_agent" prompt'u
- `product_agent` → Langfuse'da "product_agent" prompt'u
- `order_agent` → Langfuse'da "order_agent" prompt'u
