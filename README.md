# LangChain Multi-Agent API Template

Agentic projeler için **code template**. LangChain 1.2.x (`create_agent`), FastAPI, Langfuse, vLLM.

Mevcut senaryo (telco customer support) sadece örnek. Template herhangi bir domain'e uyarlanabilir.

## Quick Start

```bash
conda create -n langchain python=3.12 -y
conda activate langchain
pip install -r requirements.txt
cp .env.example .env   # fill in your values
python main.py
```

UI: `http://localhost:{APP_PORT}/ui/`

## Project Structure

```
src/
├── agents/           # Her agent = standalone .py dosyası
│   ├── main_agent.py         # Supervisor — routes to subscription/billing/technical agents
│   ├── subscription_agent.py # Plan info, upgrades, comparisons, packages
│   ├── billing_agent.py      # Invoices, charges, payments (uses subscription_agent as tool)
│   └── technical_agent.py    # Network diagnostics, device compatibility, trouble tickets
├── tools/            # Her agent'ın tool'ları ayrı dosyada
│   ├── subscription_tools.py # @tool: get_current_plan, search_plans, compare_plans, change_plan, add_package
│   ├── billing_tools.py      # @tool: get_invoice, get_payment_history, explain_charges, initiate_payment_plan
│   └── technical_tools.py    # @tool: check_network_status, run_line_diagnostic, check_device_compatibility, create_trouble_ticket
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
notebooks/
└── langfuse_prompts.ipynb    # Langfuse'a prompt yükleme notebook'u
main.py                       # FastAPI entry point + lifespan (checkpointer init/shutdown)
```

## Agent Architecture

```
main_agent (supervisor)
├── ask_subscription_specialist → subscription_agent
│     Tools: get_current_plan, search_plans, compare_plans, change_plan, add_package
├── ask_billing_specialist → billing_agent
│     Tools: get_invoice, get_payment_history, explain_charges, initiate_payment_plan
│     Agent-as-tool: suggest_plan_change → subscription_agent
└── ask_technical_specialist → technical_agent
      Tools: check_network_status, run_line_diagnostic, check_device_compatibility, create_trouble_ticket
```

`agent_name` gönderilmezse istek default olarak `main_agent`'a yönlenir. Main agent supervisor rolündedir — soruyu analiz eder ve doğru specialist agent'a routing yapar.

## Geliştirici Rehberi — Neyi Değiştir, Neye Dokunma

Bu template'i kendi domain'ine uyarlarken hangi dosyaların değişeceğini, hangilerinin sabit kalacağını bilmek önemlidir.

### Değiştirmen Gereken Dosyalar

| Dosya / Klasör | Ne Yaparsın |
|---|---|
| `src/tools/<domain>_tools.py` | Kendi domain tool'larını yaz. Mevcut telco tool'larını sil veya değiştir |
| `src/agents/<domain>_agent.py` | Kendi agent'larını oluştur. `system_prompt` ve `tools` listesini güncelle |
| `src/providers.py` | `AGENTS` dict'ini güncelle: kendi agent'larını import et ve kaydet |
| `.env` | vLLM endpoint, Langfuse key'leri, port vb. kendi ortamına göre ayarla |
| `notebooks/langfuse_prompts.ipynb` | Langfuse kullanıyorsan kendi prompt'larını yükle |

### Dokunma — Sabit Kalan Dosyalar

| Dosya | Neden Sabit |
|---|---|
| `src/models/schemas.py` | API kontratı. Client'lar bu şemaya göre entegre olur. Mevcut alanları değiştirmek breaking change yaratır |
| `src/api/router.py` | Endpoint'ler ve request/response akışı tüm domain'ler için aynı |
| `src/config/settings.py` | Yeni `.env` değişkeni gerekmedikçe dokunma |
| `src/config/llm.py` | Shared LLM instance. Tüm agent'lar buradan alır |
| `src/memory/checkpointer.py` | Checkpointer lifecycle. Farklı DB backend'e geçmedikçe dokunma |
| `src/middleware/trim.py` | Message trimming. Tüm agent'larda aynı şekilde çalışır |
| `src/middleware/prompt.py` | Langfuse prompt management. Tüm agent'larda aynı şekilde çalışır |
| `main.py` | Lifespan, CORS, gateway auth, router mount. Agent sayısı değişse bile değişmez |

### Yardımcı Kod Nereye Yazılır?

Agent'ların kullandığı ama doğrudan `@tool` olmayan yardımcı fonksiyonlar (base64 encode/decode, tarih formatlama, API client wrapper, vb.):

| Durum | Nereye Koy | Örnek |
|---|---|---|
| Tek bir tool dosyasında kullanılan yardımcı | Aynı tool dosyasının içine, `_` prefix ile private fonksiyon | `src/tools/billing_tools.py` → `def _format_currency(amount):` |
| Birden fazla tool dosyasında kullanılan ortak yardımcı | `src/tools/` içine ayrı modül | `src/tools/utils.py` → `def decode_base64(data):` |
| Harici API client veya karmaşık iş mantığı (150+ satır) | `src/tools/` altında klasör yapısı | `src/tools/crm/client.py`, `src/tools/crm/mapper.py` |

```
src/tools/
├── billing_tools.py          ← @tool fonksiyonları
├── subscription_tools.py     ← @tool fonksiyonları
├── utils.py                  ← ortak yardımcı fonksiyonlar (base64, tarih, vb.)
└── crm/                      ← karmaşık harici entegrasyon
    ├── __init__.py
    ├── client.py             ← API client
    └── mapper.py             ← response mapping
```

**Kural:** Yardımcı kodlar `src/tools/` altında kalır. `src/agents/`, `src/config/`, `src/middleware/`, `src/api/`, `src/models/` klasörlerine domain-specific kod eklenmez.

Harici ekiplerden gelen kodların entegrasyon standardı: **[docs/external-tool-guide.md](docs/external-tool-guide.md)**

## API

Üç endpoint mevcuttur:

| Endpoint | Method | Açıklama |
|---|---|---|
| `/chat` | POST | Sync agent çağrısı — tam yanıt döner |
| `/chat/stream` | POST | SSE stream — token token yanıt döner |
| `/agents` | GET | Discovery — kayıtlı agent'ları listeler (TOON veya JSON) |

**Request:**
```json
{
  "app_id": "my-app",
  "user_id": "user-1",
  "agent_name": "main",
  "session_id": "sess-abc",
  "messages": [
    {"role": "user", "content": "Tarifemi değiştirmek istiyorum"}
  ]
}
```

**Response:**
```json
{
  "id": "a1b2c3d4-...",
  "success": true,
  "message": {"role": "assistant", "content": "Tarife değişikliği için size yardımcı olayım..."},
  "usage": {"prompt_tokens": 142, "completion_tokens": 87, "total_tokens": 229},
  "agent_name": "main",
  "created_at": "2026-02-25T14:30:00Z"
}
```

Hata durumunda `success: false` ve `error` alanı döner. Hata kodları: `agent_not_found`, `invalid_request`, `llm_error`, `rate_limit`, `timeout`, `internal_error`.

Full payload detayları, SSE stream formatı, multimodal request ve discovery API örnekleri: **[docs/api-contract.md](docs/api-contract.md)**

## State Management

Agent'lar **stateless** oluşturulur. Checkpointer FastAPI lifespan'da başlatılır ve `wire_checkpointer()` ile agent'lara atanır.

- **Composite thread_id:** `{app_id}:{user_id}:{session_id}` — farklı uygulamalardan gelen istekler izole kalır
- **Stateless mod:** `session_id` gönderilmezse history tutulmaz
- **Message trimming:** `@before_model` middleware ile eski mesajlar kırpılır (`CHAT_HISTORY_MAX_TOKENS`), system prompt korunur
- **Agent-as-tool:** Sub-agent çağrılarında `tool:{uuid}` ephemeral thread_id kullanılır — çift kayıt önlenir

HTTP isteğinin sisteme girişinden agent yanıtına kadar tüm adımlar: **[docs/request-lifecycle.md](docs/request-lifecycle.md)**

## Langfuse Prompt Management

Agent system prompt'ları Langfuse'dan runtime'da çekilir. Prompt güncellemesi **restart gerektirmez** — cache TTL (default 60s) dolunca yeni prompt aktif olur.

- `@wrap_model_call` middleware her LLM çağrısında Langfuse'dan prompt çeker
- **Konvansyon:** Langfuse prompt adı = `create_agent(name=...)` değeri
- Langfuse erişilemezse agent dosyasındaki hardcoded `system_prompt` fallback olarak kullanılır
- Startup'ta `warm_prompt_cache()` ile cold-cache latency'si önlenir
- `LANGFUSE_PROMPT_MANAGEMENT_ENABLED=false` ile tamamen kapatılabilir

## Adding a New Agent

| # | Adım | Dosya |
|---|---|---|
| 1 | `@tool` fonksiyonlarını yaz | `src/tools/<domain>_tools.py` |
| 2 | Agent'ı oluştur (`create_agent`, checkpointer verme) | `src/agents/<domain>_agent.py` |
| 3 | Agent'ı import et ve `AGENTS` dict'ine ekle | `src/providers.py` |
| 4 | Langfuse'a prompt yükle (opsiyonel) | `notebooks/langfuse_prompts.ipynb` |
| 5 | API'den `agent_name: "<domain>"` ile çağır | — |

Agent-as-tool olarak kullanılacaksa:

| # | Adım | Dosya |
|---|---|---|
| 6 | Sub-agent'ı import et, `@tool async def` wrapper yaz | Çağıran agent'ın dosyası |
| 7 | Wrapper'ı `create_agent(tools=[...])` listesine ekle | Aynı dosya |

Agent dosyası template:
```python
from src.config.llm import llm
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

Harici ekiplerden gelen kodların tool olarak entegrasyonu: **[docs/external-tool-guide.md](docs/external-tool-guide.md)**

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
| `LANGFUSE_PROMPT_CACHE_TTL` | Prompt cache TTL in seconds |
| `APP_ENV` | development / production |
| `APP_PORT` | Server port |
| `CHAT_HISTORY_ENABLED` | true = conversational, false = stateless Q&A |
| `CHAT_HISTORY_MAX_TOKENS` | Max tokens to keep in conversation history |
| `GATEWAY_SECRET` | Shared secret for API gateway auth (empty = disabled) |

Tüm config `.env`'den okunur, hardcoded default yoktur. `.env` eksikse uygulama başlamaz (fail-fast).

## Documentation

| Doküman | İçerik |
|---|---|
| [docs/request-lifecycle.md](docs/request-lifecycle.md) | HTTP isteğinden agent yanıtına kadar tüm adımlar, middleware zinciri, tool execution akışı |
| [docs/api-contract.md](docs/api-contract.md) | Request/response şemaları, SSE stream formatı, error code'lar, discovery API |
| [docs/external-tool-guide.md](docs/external-tool-guide.md) | Harici ekiplerden gelen kodların tool olarak entegrasyonu, kod teslim standardı |
| [docs/gateway-setup.md](docs/gateway-setup.md) | API Gateway kurulumu: shared secret, nginx/Traefik/Caddy/HAProxy örnekleri |
| [docs/architecture-decisions.md](docs/architecture-decisions.md) | 28 mimari karar (ADR): gerekçeler ve kod kanıtları |
