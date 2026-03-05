# Request Lifecycle

Bir HTTP isteğinin sisteme girişinden agent yanıtının dönmesine kadar tüm adımları kapsar.

---

## 1. Mimari Genel Bakış

```
                         ┌─────────────────────────────────────────────────┐
                         │                  main.py                        │
                         │  FastAPI app + lifespan (startup/shutdown)      │
                         └──────────────┬──────────────────────────────────┘
                                        │
                                        ▼
┌──────────┐    ┌──────────────┐    ┌──────────┐    ┌───────────────────┐
│  Client   │───▶  CORS        │───▶  Router   │───▶  Agent            │
│  (HTTP)   │    │  Middleware  │    │  router.py│    │  (CompiledGraph) │
└──────────┘    └──────────────┘    └──────────┘    └────────┬──────────┘
                                                             │
                                    ┌────────────────────────┼────────────────────┐
                                    │                        │                    │
                                    ▼                        ▼                    ▼
                             ┌─────────────┐    ┌────────────────┐    ┌───────────────┐
                             │  Middleware  │    │    LLM Call     │    │  Tool Exec    │
                             │  (prompt +   │    │  (ChatOpenAI /  │    │  (@tool veya  │
                             │   trim)      │    │   vLLM)         │    │   agent-as-   │
                             └─────────────┘    └────────────────┘    │   tool)       │
                                                                      └───────────────┘
```

### Dosya Haritası

| Dosya | Sorumluluk |
|---|---|
| `main.py` | FastAPI app, lifespan (checkpointer init, prompt cache warmup), CORS, static UI mount |
| `src/api/router.py` | HTTP endpoint'leri (`POST /chat`, `POST /chat/stream`, `GET /agents`) |
| `src/providers.py` | Agent registry (`AGENTS` dict), `get_agent()`, `wire_checkpointer()`, Langfuse handler, discovery metadata |
| `src/config/settings.py` | `.env`'den tüm konfigürasyonu okur (`Settings` Pydantic model) |
| `src/config/llm.py` | Shared `ChatOpenAI` instance (vLLM backend) |
| `src/memory/checkpointer.py` | `AsyncSqliteSaver` lifecycle (`init_checkpointer`, `shutdown_checkpointer`) |
| `src/middleware/trim.py` | `@before_model` — LLM çağrısı öncesi mesaj kırpma |
| `src/middleware/prompt.py` | `@wrap_model_call` — Langfuse'dan runtime system prompt override |
| `src/agents/*.py` | Agent tanımları (`create_agent` ile module-level `agent` objesi) |
| `src/tools/*.py` | `@tool` fonksiyonları (her agent'ın tool'ları ayrı dosyada) |
| `src/models/schemas.py` | API kontratı: `ChatRequest`, `ChatResponse`, `ErrorDetail`, `Usage`, `Message` |

---

## 2. Uygulama Başlangıcı (Lifespan)

Herhangi bir HTTP isteği işlenmeden önce `main.py` içindeki `lifespan` fonksiyonu çalışır. Bu adım agent'ların stateful çalışabilmesi için zorunludur.

**Dosya:** `main.py:24-43`

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Checkpointer başlat
    if settings.chat_history_enabled:
        checkpointer = await init_checkpointer()   # checkpointer.py → AsyncSqliteSaver
        wire_checkpointer(checkpointer)             # providers.py → her agent'a ata

    # 2. Langfuse prompt cache'i ısıt (opsiyonel)
    if settings.langfuse_prompt_management_enabled:
        from src.middleware.prompt import warm_prompt_cache
        warm_prompt_cache(AGENTS)

    yield  # ← Uygulama burada çalışır, HTTP istekleri işlenir

    # 3. Shutdown: DB bağlantısını kapat
    if settings.chat_history_enabled:
        await shutdown_checkpointer()
```

### Adım adım:

| # | İşlem | Dosya | Fonksiyon |
|---|---|---|---|
| 1 | SQLite bağlantısı aç, `AsyncSqliteSaver` oluştur | `src/memory/checkpointer.py` | `init_checkpointer()` |
| 2 | Tüm agent'lara checkpointer ata | `src/providers.py` | `wire_checkpointer(checkpointer)` |
| 3 | Langfuse'dan prompt'ları ön-yükle (cold-cache engelleme) | `src/middleware/prompt.py` | `warm_prompt_cache(AGENTS)` |
| 4 | Shutdown'da SQLite bağlantısını kapat | `src/memory/checkpointer.py` | `shutdown_checkpointer()` |

> **Not:** `wire_checkpointer` her `AGENTS` dict entry'sindeki agent objesinin `.checkpointer` attribute'unu set eder. Agent'lar `create_agent(...)` ile checkpointer **verilmeden** oluşturulur — atama runtime'da yapılır.

---

## 3. HTTP İsteği Girişi

Client bir HTTP isteği gönderir. FastAPI şu sırayla işler:

```
Client → Uvicorn → FastAPI app → CORSMiddleware → Router dispatch
```

**CORS yapılandırması** (`main.py:52-57`):

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Router `main.py:59`'da bağlanır:

```python
app.include_router(router)
```

Üç endpoint mevcuttur:

| Endpoint | Method | Açıklama |
|---|---|---|
| `/chat` | POST | Sync agent çağrısı — tam yanıt döner |
| `/chat/stream` | POST | SSE stream — token token yanıt döner |
| `/agents` | GET | Discovery API — kayıtlı agent'ları listeler |

---

## 4. POST /chat — Sync Akış

**Dosya:** `src/api/router.py:65-109`

### Adım 4.1: Agent Lookup

```python
agent = get_agent(req.agent_name)
```

`providers.py:42-47` — `AGENTS` dict'inden agent aranır. Bulunamazsa `ValueError` fırlatılır ve `agent_not_found` hatası döner:

```python
def get_agent(agent_name: str = "main"):
    entry = AGENTS.get(agent_name)
    if entry is None:
        raise ValueError(f"Unknown agent_name: {agent_name!r}. Choose from {list(AGENTS)}")
    return entry["agent"]
```

### Adım 4.2: Config Build

```python
config = _build_config(req)
```

**Dosya:** `src/api/router.py:29-44`

Bu fonksiyon iki şey yapar:

**a) Langfuse callback handler oluşturma:**

```python
config = get_langfuse_handler(
    user_id=req.user_id,
    session_id=req.session_id,
    app_id=req.app_id,
)
```

`providers.py:94-122` — `LANGFUSE_ENABLED=true` ise `CallbackHandler` oluşturulur, metadata dict'e `langfuse_user_id`, `langfuse_session_id`, `langfuse_app_id` eklenir. `LANGFUSE_ENABLED=false` ise boş dict döner.

**b) Composite thread_id oluşturma:**

```python
if settings.chat_history_enabled and req.session_id:
    thread_id = f"{req.app_id}:{req.user_id}:{req.session_id}"
    config.setdefault("configurable", {})["thread_id"] = thread_id
```

Thread ID formatı: `{app_id}:{user_id}:{session_id}`

Bu composite key, farklı uygulamalardan gelen isteklerin state'lerinin karışmasını önler. `session_id` yoksa agent stateless çalışır (checkpointer kullanılmaz).

### Adım 4.3: Mesajları Hazırlama

```python
_build_messages(req)  # → [m.model_dump() for m in req.messages]
```

Request'teki `Message` nesneleri dict formatına dönüştürülür.

### Adım 4.4: Agent Invocation

```python
result = await agent.ainvoke(
    {"messages": _build_messages(req)},
    config=config,
)
```

Bu çağrı `CompiledStateGraph.ainvoke()` metodunu tetikler. Dahili akış:

1. **Checkpointer** — `thread_id` varsa mevcut state'i (önceki mesajları) yükler
2. **Gelen mesajları state'e ekler**
3. **Middleware zincirini çalıştırır** (bkz. Adım 5)
4. **LLM çağrısı yapar** (bkz. Adım 6)
5. **Tool çağrısı gerekiyorsa** tool'u çalıştırır, sonucu state'e ekler, LLM'e geri döner (bkz. Adım 7)
6. **Final state'i checkpointer'a kaydeder**

### Adım 4.5: Response Oluşturma

```python
ai_message = result["messages"][-1]
return ChatResponse(
    id=response_id,
    success=True,
    message=Message(role="assistant", content=ai_message.content),
    usage=_extract_usage(result),
    ...
)
```

`_extract_usage()` (`router.py:52-62`) — Son AI mesajındaki `usage_metadata`'dan token sayılarını çıkarır:

```python
def _extract_usage(result: dict) -> Usage | None:
    ai_message = result["messages"][-1]
    usage_meta = getattr(ai_message, "usage_metadata", None)
    if usage_meta:
        return Usage(
            prompt_tokens=usage_meta.get("input_tokens", 0),
            completion_tokens=usage_meta.get("output_tokens", 0),
            total_tokens=usage_meta.get("total_tokens", 0),
        )
    return None
```

### Adım 4.6: Hata Durumu

Herhangi bir exception oluşursa `llm_error` kodu ile hata yanıtı döner:

```python
except Exception as e:
    logger.exception("Agent invocation failed")
    return ChatResponse(
        id=response_id,
        success=False,
        error=ErrorDetail(code="llm_error", message=str(e)),
        ...
    )
```

---

## 5. Middleware Zinciri

Agent her LLM çağrısından önce middleware zincirini çalıştırır. Middleware'ler agent oluşturulurken `middleware=[...]` listesiyle verilir.

### Middleware sırası (agent dosyalarından):

```python
# src/agents/main_agent.py:70-74
_middleware = [trim_old_messages]
if settings.langfuse_prompt_management_enabled:
    from src.middleware.prompt import langfuse_prompt
    _middleware.insert(0, langfuse_prompt)
# Sonuç: [langfuse_prompt, trim_old_messages] veya [trim_old_messages]
```

### 5.1 Langfuse Prompt Override (opsiyonel)

**Dosya:** `src/middleware/prompt.py:31-67`
**Dekoratör:** `@wrap_model_call`

```
LLM çağrısı tetiklendi
    ↓
langfuse_prompt middleware çalışır
    ↓
get_config()["metadata"]["lc_agent_name"] ile agent adı alınır
    ↓
Langfuse client.get_prompt(agent_name, ...) çağrılır (cache TTL: LANGFUSE_PROMPT_CACHE_TTL)
    ↓
prompt.compile() → system message override: request.override(system_message=SystemMessage(...))
    ↓
await handler(request) → sonraki middleware'e veya LLM'e geç
```

Langfuse erişilemezse mevcut system prompt (agent dosyasındaki hardcoded prompt) korunur.

### 5.2 Message Trimming

**Dosya:** `src/middleware/trim.py:15-36`
**Dekoratör:** `@before_model`

```
LLM çağrısı tetiklendi (langfuse_prompt'tan sonra)
    ↓
trim_old_messages çalışır
    ↓
Mesaj sayısı ≤ 4 → kırpma yapılmaz, None döner
    ↓
trim_messages(strategy="last", token_counter="approximate",
              max_tokens=CHAT_HISTORY_MAX_TOKENS, include_system=True, start_on="human")
    ↓
Kırpma gerekiyorsa → RemoveMessage(id=REMOVE_ALL_MESSAGES) + kırpılmış mesajlar döner
    ↓
Checkpoint'teki eski mesajlar silinir, kırpılmış mesajlar yeni state olur
```

**Önemli:** `include_system=True` ile system prompt her zaman korunur. `start_on="human"` ile kırpma sonrası ilk mesaj her zaman bir human mesajı olur.

---

## 6. LLM Çağrısı

**Dosya:** `src/config/llm.py:7-11`

Tüm agent'lar aynı `ChatOpenAI` instance'ını kullanır:

```python
llm = ChatOpenAI(
    base_url=settings.vllm_base_url,    # vLLM endpoint
    model=settings.vllm_model_name,
    api_key=settings.vllm_api_key,
)
```

LLM'in yanıtı iki türde olabilir:

| Yanıt Tipi | Açıklama | Sonraki Adım |
|---|---|---|
| **Direkt metin** | LLM doğrudan kullanıcıya cevap verir | → Response oluştur, state'e kaydet |
| **Tool call** | LLM bir tool çağırma kararı verir (`AIMessage.tool_calls`) | → Tool execution (Adım 7) |

---

## 7. Tool Execution

LLM bir tool çağırma kararı verdiğinde agent framework tool'u çalıştırır.

### 7.1 Normal Tool Çağrısı

`@tool` ile tanımlı fonksiyon direkt çalıştırılır. Örnek (`src/tools/billing_tools.py:6-27`):

```python
@tool
def get_invoice(msisdn: str, period: str = "") -> str:
    """Get the invoice for a specific billing period."""
    ...
    return "Invoice for ..."
```

Akış: LLM tool_call kararı → framework tool'u çağırır → sonuç `ToolMessage` olarak state'e eklenir → LLM tekrar çağrılır (sonucu yorumlaması için)

### 7.2 Agent-as-Tool Çağrısı

Bir agent başka bir agent'ı tool olarak kullanabilir. Örnek (`src/agents/main_agent.py:23-35`):

```python
@tool
async def ask_subscription_specialist(question: str) -> str:
    """Delegate subscription and plan questions to the subscription specialist."""
    result = await subscription_agent.ainvoke(
        {"messages": [{"role": "user", "content": question}]},
        config={"configurable": {"thread_id": f"tool:{uuid.uuid4()}"}},
    )
    return result["messages"][-1].content
```

**Kritik noktalar:**

- **Ephemeral thread_id:** `tool:{uuid}` formatında tek kullanımlık thread_id verilir
- **İzole state:** Sub-agent'ın kendi conversation history'si olmaz — her çağrı temiz başlar
- **Sonuç parent'a yazılır:** Tool'un return değeri parent agent'ın state'ine `ToolMessage` olarak eklenir
- **Çift kayıt önlenir:** Sub-agent ayrıca history tutmaz çünkü sonuç zaten parent'ta

### Agent-as-Tool akışı:

```
Parent Agent (main_agent)
    ↓ LLM: "ask_subscription_specialist çağır"
    ↓
    ├─ @tool async def ask_subscription_specialist(question)
    │      ↓
    │      subscription_agent.ainvoke(
    │          messages=[{"role": "user", "content": question}],
    │          config={"thread_id": "tool:a1b2c3d4-..."}  ← ephemeral
    │      )
    │      ↓
    │      Sub-agent kendi middleware'lerini çalıştırır (trim, prompt)
    │      Sub-agent kendi tool'larını çağırabilir (get_current_plan, search_plans, ...)
    │      Sub-agent LLM yanıtı üretir
    │      ↓
    │      return result["messages"][-1].content  ← string olarak döner
    │
    ↓ ToolMessage olarak parent state'e eklenir
    ↓ Parent LLM tekrar çağrılır → kullanıcıya yanıt oluşturur
```

---

## 8. POST /chat/stream — SSE Akışı

**Dosya:** `src/api/router.py:112-148`

Stream akışı sync akışla aynı config build ve agent lookup adımlarını kullanır. Fark `ainvoke` yerine `astream` kullanılmasıdır:

```python
async for token, metadata in agent.astream(
    {"messages": _build_messages(req)},
    config=config,
    stream_mode="messages",
):
    if hasattr(token, "content") and token.content:
        yield {"event": "token", "data": json.dumps({"content": token.content})}

yield {"event": "done", "data": "{}"}
```

SSE event tipleri:

| Event | Data | Açıklama |
|---|---|---|
| `token` | `{"content": "..."}` | LLM'den gelen bir token parçası |
| `done` | `{}` | Stream başarıyla tamamlandı |
| `error` | `{"code": "...", "message": "..."}` | Hata oluştu |

`EventSourceResponse` (`sse-starlette` kütüphanesi) async generator'ı SSE formatına çevirir.

---

## 9. GET /agents — Discovery API

**Dosya:** `src/api/router.py:151-161`

Agent kataloğunu döner. Orchestrator agent'lar bu endpoint'i okuyarak doğru agent'ı seçebilir.

```python
@router.get("/agents")
async def list_agents(fmt: str = Query("toon", alias="format")):
    metadata = get_agents_metadata()
    if fmt == "json":
        return JSONResponse(content=metadata)
    return Response(content=toon_encode(metadata), media_type="text/toon")
```

`get_agents_metadata()` (`providers.py:77-91`) — `AGENTS` dict'inden agent adı ve description'ı, compiled agent'tan tool bilgilerini çeker:

- Tool bilgileri `_extract_tools()` ile runtime'da agent'ın `nodes['tools'].bound.tools_by_name` üzerinden alınır
- `@tool` decorator'daki docstring ve parametre bilgileri otomatik olarak metadata'ya yansır

| Format | Content-Type | Query Param |
|---|---|---|
| TOON (default) | `text/toon` | `?format=toon` veya param yok |
| JSON | `application/json` | `?format=json` |

---

## 10. Hata Akışları Özeti

| Hata Noktası | Error Code | Tetikleyen |
|---|---|---|
| Agent bulunamadı | `agent_not_found` | `get_agent()` → `ValueError` |
| LLM hatası (timeout, API error, vb.) | `llm_error` | `agent.ainvoke()` veya `agent.astream()` exception |
| Langfuse erişilemez | — (hata değil) | Fallback: hardcoded system prompt kullanılır |
| Middleware kırpma | — (hata değil) | Token limiti aşılmışsa eski mesajlar kırpılır |

---

## 11. Tam Akış Diyagramı

```
Client HTTP POST /chat
    │
    ▼
main.py: FastAPI app → CORSMiddleware
    │
    ▼
router.py: chat() endpoint
    │
    ├─ get_agent(req.agent_name)                    ← providers.py AGENTS dict
    │     └─ bulunamazsa → ChatResponse(error=agent_not_found)
    │
    ├─ _build_config(req)                           ← router.py
    │     ├─ get_langfuse_handler(...)              ← providers.py → CallbackHandler + metadata
    │     └─ thread_id = app_id:user_id:session_id  (session_id varsa)
    │
    ├─ _build_messages(req)                         ← router.py → [m.model_dump()]
    │
    ▼
agent.ainvoke({"messages": [...]}, config=config)   ← CompiledStateGraph
    │
    ├─ Checkpointer: state yükle (thread_id varsa)  ← checkpointer.py AsyncSqliteSaver
    │
    ├─ Middleware: langfuse_prompt                   ← middleware/prompt.py (opsiyonel)
    │     └─ Langfuse'dan system prompt çek → override
    │
    ├─ Middleware: trim_old_messages                 ← middleware/trim.py
    │     └─ Token limiti aşılmışsa eski mesajları kırp
    │
    ├─ LLM çağrısı                                  ← config/llm.py ChatOpenAI (vLLM)
    │     ├─ Direkt yanıt → state'e kaydet → response dön
    │     └─ Tool call → tool çalıştır ↓
    │
    ├─ Tool Execution
    │     ├─ Normal @tool → fonksiyon çalışır → ToolMessage → LLM'e geri dön
    │     └─ Agent-as-tool → sub_agent.ainvoke(thread_id="tool:{uuid}")
    │           └─ Ephemeral, izole → sonuç parent'a ToolMessage olarak döner
    │
    ├─ Checkpointer: state kaydet
    │
    ▼
router.py: ChatResponse(success=True, message=..., usage=...)
    │
    ▼
Client HTTP Response (JSON)
```
