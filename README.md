# LangChain Multi-Agent API Template

Agentic projeler için **code template**. LangChain 1.2.x (`create_agent`), FastAPI, Langfuse, vLLM.

Mevcut senaryo (e-commerce customer support) sadece örnek. Template herhangi bir domain'e uyarlanabilir.

## Project Structure

```
src/
├── agents/           # Her agent = standalone .py dosyası
│   ├── main_agent.py         # Supervisor — routes to product/order agents
│   ├── product_agent.py      # Product search, details, recommendations
│   └── order_agent.py        # Order tracking, returns, exchanges (uses product_agent as tool)
├── tools/            # Her agent'ın tool'ları ayrı dosyada
│   ├── product_tools.py      # @tool: search_products, get_product_details, get_recommendations
│   └── order_tools.py        # @tool: track_order, initiate_return, initiate_exchange
├── middleware/
│   ├── trim.py               # @before_model — trim_messages ile history kırpma
│   └── prompt.py             # @wrap_model_call — Langfuse'dan runtime system prompt
├── api/
│   └── router.py             # POST /chat, POST /chat/stream (SSE), GET /agents (discovery)
├── config/
│   ├── settings.py           # pydantic-settings (.env)
│   └── llm.py                # Shared ChatOpenAI instance
├── models/
│   └── schemas.py            # ChatRequest / ChatResponse (stable API contract)
├── memory/
│   └── checkpointer.py       # AsyncSqliteSaver (checkpoints.db)
└── providers.py              # Agent registry, checkpointer wiring, Langfuse handler & discovery metadata
UI/                           # Chat arayüzü (FastAPI /ui/ ile serve edilir)
main.py                       # FastAPI entry point + lifespan (checkpointer init/shutdown)
```

## Quick Start

```bash
conda create -n langchain python=3.12 -y
conda activate langchain
pip install -r requirements.txt
cp .env.example .env   # fill in your values
python main.py
```

UI: `http://localhost:{APP_PORT}/ui/`

## State Management & Memory

### Mimari

Agent'lar **stateless** oluşturulur (checkpointer `create_agent`'a verilmez). Checkpointer **FastAPI lifespan'da** oluşturulur ve `wire_checkpointer()` ile agent'lara atanır.

```
main.py lifespan → init_checkpointer() → wire_checkpointer(checkpointer)
                                              ↓
API isteği → router._build_config() → composite thread_id oluştur
                                              ↓
         agent.ainvoke(config={thread_id}) → checkpointer state yükler/kaydeder
                                              ↓
         @before_model trim_old_messages → eski mesajları kırp (CHAT_HISTORY_MAX_TOKENS)
```

### Message Trimming

Her LLM çağrısından önce `@before_model` middleware çalışır. `trim_messages` ile eski mesajlar kırpılır:
- `strategy="last"` — son N token'lık mesajları tutar
- `include_system=True` — system prompt her zaman korunur
- `start_on="human"` — kırpılan mesajlar human mesajla başlar
- Token limiti `.env`'den `CHAT_HISTORY_MAX_TOKENS` ile ayarlanır
- Kırpılan mesajlar checkpoint'ten de silinir (`RemoveMessage + REMOVE_ALL_MESSAGES`)

### Composite thread_id — Cross-App Isolation

Her istek `app_id`, `user_id` ve `session_id` içerir. Bunlardan tek bir thread_id oluşturulur:

```
thread_id = "{app_id}:{user_id}:{session_id}"
```

Bu sayede farklı uygulamalardan aynı agent'a gelen istekler birbirinden izole kalır:

| İstek kaynağı | thread_id | State |
|---------------|-----------|-------|
| App A, user-1, sess-1 | `appA:user-1:sess-1` | Kendi konuşması |
| App B, user-1, sess-1 | `appB:user-1:sess-1` | Tamamen ayrı state |

### Agent-as-Tool — Ephemeral thread_id

Bir agent başka bir agent'ı tool olarak çağırdığında **ephemeral thread_id** kullanılır (`tool:{uuid}`):

```python
result = await product_agent.ainvoke(
    {"messages": [{"role": "user", "content": question}]},
    config={"configurable": {"thread_id": f"tool:{uuid.uuid4()}"}},
)
```

Neden:
- Tool çağrısının sonucu zaten **parent agent'ın state'ine** yazılır (AIMessage.tool_calls + ToolMessage)
- Sub-agent'ın ayrıca history tutmasına gerek yok — çift kayıt olur
- Her tool çağrısı izole ve tek kullanımlık

## API

### POST /chat

**Request:**
```json
{
  "app_id": "my-app",
  "user_id": "user-1",
  "agent_name": "main",
  "session_id": "sess-abc",
  "messages": [
    {"role": "user", "content": "I want to return my order ORD-78432"}
  ],
  "metadata": {"department": "support"}
}
```

**Response (success):**
```json
{
  "id": "a1b2c3d4-...",
  "success": true,
  "message": {"role": "assistant", "content": "I'll help you with that return..."},
  "error": null,
  "usage": {"prompt_tokens": 142, "completion_tokens": 87, "total_tokens": 229},
  "agent_name": "main",
  "app_id": "my-app",
  "user_id": "user-1",
  "session_id": "sess-abc",
  "created_at": "2026-02-25T14:30:00Z"
}
```

**Response (error):**
```json
{
  "id": "e5f6g7h8-...",
  "success": false,
  "message": null,
  "error": {"code": "agent_not_found", "message": "Unknown agent_name: 'xyz'", "details": null},
  "usage": null,
  "agent_name": null,
  "app_id": "my-app",
  "user_id": "user-1",
  "session_id": null,
  "created_at": "2026-02-25T14:30:00Z"
}
```

**Error Codes:**

| Code | Description |
|------|-------------|
| `agent_not_found` | Geçersiz `agent_name` değeri |
| `invalid_request` | Request validation hatası |
| `llm_error` | LLM çağrısı başarısız |
| `rate_limit` | Rate limiting |
| `timeout` | Agent veya LLM timeout |
| `internal_error` | Beklenmeyen sunucu hatası |

`ErrorDetail.code` alanı `Literal` type ile kısıtlıdır — sadece yukarıdaki kodlar geçerlidir. OpenAPI schema'da enum olarak görünür.

**Multimodal request:**
```json
{
  "app_id": "my-app",
  "user_id": "user-1",
  "messages": [
    {
      "role": "user",
      "content": [
        {"type": "text", "text": "What product is this?"},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}
      ]
    }
  ]
}
```

### POST /chat/stream

Same request body. Returns Server-Sent Events:
- `event: token` — `{"content": "..."}` (partial output)
- `event: done` — `{}` (stream finished)
- `event: error` — `{"code": "...", "message": "..."}` (on failure)

### GET /agents — Discovery API

Agent kataloğunu döner. Cross-app agent keşfi için kullanılır — bir orchestrator agent bu endpoint'i okuyup doğru agent'ı seçebilir.

**Default format: TOON** (`text/toon`) — LLM-friendly, JSON'a göre %30-60 daha az token.
JSON için `?format=json` query param ekle.

```bash
# TOON (default)
curl -s http://localhost:8080/agents

# JSON
curl -s http://localhost:8080/agents?format=json
```

**JSON response örneği:**
```json
{
  "agents": [
    {
      "name": "product",
      "description": "Product specialist. Search, details, recommendations.",
      "endpoint": "/chat",
      "tools": [
        {
          "name": "search_products",
          "description": "Search the product catalog by keyword.",
          "parameters": "query:string"
        }
      ]
    }
  ]
}
```

Tool metadata (`name`, `description`, `parameters`) compiled agent'lardan runtime'da otomatik çekilir — manuel tool metadata yazmaya gerek yok.

## Langfuse Prompt Management

Agent system prompt'ları Langfuse'dan runtime'da çekilir. Prompt güncellemesi **restart gerektirmez** — ~60 saniye içinde tüm agent'lar yeni prompt'u kullanır.

### Nasıl Çalışır

```
Langfuse UI'da prompt güncelle
        ↓
Cache TTL dolana kadar bekle (default: 60s)
        ↓
Stale-while-revalidate: eski prompt döner + arka planda yenisi çekilir
        ↓
Sonraki request → yeni prompt aktif
```

### Mimari

`@wrap_model_call` middleware (`src/middleware/prompt.py`) her LLM çağrısında:
1. Agent adını tespit eder: `get_config()["metadata"]["lc_agent_name"]`
2. Langfuse'dan ilgili prompt'u çeker: `client.get_prompt(agent_name, ...)`
3. System message'ı override eder: `request.override(system_message=...)`
4. Langfuse erişilemezse hardcoded `system_prompt` fallback olarak kullanılır

**Konvansyon:** Langfuse prompt adı = `create_agent(name=...)` değeri

| Agent | `create_agent(name=...)` | Langfuse Prompt Adı |
|-------|--------------------------|---------------------|
| Main | `main_agent` | `main_agent` |
| Product | `product_agent` | `product_agent` |
| Order | `order_agent` | `order_agent` |

### Cache Davranışı

| Senaryo | Ne olur | Latency |
|---------|---------|---------|
| Cache sıcak (<TTL) | Bellekten döner | ~μs |
| Cache expire (stale) | Stale döner + daemon thread'de HTTP refresh | ~μs |
| Cache boş (ilk çağrı) | Blocking HTTP call | ~100ms (startup'ta ısıtılır) |

Startup'ta `warm_prompt_cache(AGENTS)` çağrılarak ilk request'te blocking HTTP call önlenir.

### Kurulum

1. `.env`'de `LANGFUSE_PROMPT_MANAGEMENT_ENABLED=true` ayarla
2. Langfuse UI → Prompts → Create:
   - **Name**: agent adıyla aynı (ör. `main_agent`)
   - **Type**: Text
   - **Content**: system prompt metni
   - **Label**: `production`
3. `python main.py` ile başlat

`LANGFUSE_PROMPT_MANAGEMENT_ENABLED=false` yapılırsa agent dosyalarındaki hardcoded `system_prompt` kullanılır — hiçbir breaking change yok.

## Adding a New Agent

1. `tools/<domain>_tools.py` — pure `@tool` fonksiyonları yaz
2. `agents/<domain>_agent.py` — agent oluştur:
   ```python
   from src.config.settings import settings
   from src.middleware.trim import trim_old_messages

   _middleware = [trim_old_messages]
   if settings.langfuse_prompt_management_enabled:
       from src.middleware.prompt import langfuse_prompt
       _middleware.insert(0, langfuse_prompt)

   agent = create_agent(
       model=llm, tools=[...], middleware=_middleware,
       system_prompt="fallback prompt", name="{domain}_agent",
   )
   ```
3. `providers.py` → AGENTS dict'ine ekle: `"<domain>": {"agent": agent, "description": "Kısa açıklama."}`
4. Langfuse UI'da `{domain}_agent` adıyla Text prompt oluştur (label: `production`)
5. API'den `agent_name: "<domain>"` ile çağır — `GET /agents` otomatik olarak yeni agent'ı listeler

Bir agent başka bir agent'ı tool olarak kullanacaksa:
- O agent'ın `agent` objesini import et
- `@tool` + `async def` ile sar
- `await agent.ainvoke(...)` çağır, `config={"configurable": {"thread_id": f"tool:{uuid.uuid4()}"}}` geç

## Configuration (.env)

| Variable | Description |
|----------|-------------|
| `VLLM_BASE_URL` | vLLM endpoint |
| `VLLM_MODEL_NAME` | Model name |
| `VLLM_API_KEY` | API key |
| `LANGFUSE_PUBLIC_KEY` | Langfuse public key |
| `LANGFUSE_SECRET_KEY` | Langfuse secret key |
| `LANGFUSE_HOST` | Langfuse host URL |
| `LANGFUSE_ENABLED` | Enable/disable tracing |
| `LANGFUSE_PROMPT_MANAGEMENT_ENABLED` | Enable/disable Langfuse prompt management |
| `LANGFUSE_PROMPT_CACHE_TTL` | Prompt cache TTL in seconds (default: 60) |
| `APP_ENV` | development / production |
| `APP_PORT` | Server port |
| `CHAT_HISTORY_ENABLED` | true = conversational, false = stateless Q&A |
| `CHAT_HISTORY_MAX_TOKENS` | Max tokens to keep in conversation history (approximate) |
