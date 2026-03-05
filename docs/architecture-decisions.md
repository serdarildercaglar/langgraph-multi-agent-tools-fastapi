# Architecture Decisions Record (ADR)

Bu doküman projedeki mimari kararları, gerekçelerini ve kod kanıtlarını içerir. Yeni ekip üyelerinin "neden böyle yapılmış?" sorusuna cevap bulması için yazılmıştır.

---

## Genel İlkeler

### ADR-01: Template Odaklı Tasarım

**Karar:** Proje belirli bir domain'e bağlı değildir. Mevcut telco senaryosu sadece örnektir — template herhangi bir domain'e uyarlanabilir.

**Gerekçe:** Farklı ekiplerin yazdığı agent'ların aynı modüler standartta olmasını sağlamak. Yeni bir agent çıkarmak 4 adımla mümkün olmalı (tools → agent → providers → API).

**Kanıt:** Tüm agent'lar aynı pattern'ı takip eder:
- `src/agents/subscription_agent.py` — `create_agent(model=llm, tools=[...], middleware=[...], system_prompt="...", name="...")`
- `src/agents/billing_agent.py` — aynı yapı
- `src/agents/technical_agent.py` — aynı yapı

---

### ADR-02: Wrapper / Factory Fonksiyon Yasağı

**Karar:** `build_*`, `make_*`, `create_*` gibi wrapper fonksiyonlar yazılmaz. Her agent dosyası module-level `agent = create_agent(...)` ile biter.

**Gerekçe:** Indirection katmanı eklemek template'in okunabilirliğini düşürür. Yeni bir agent ekleyen geliştirici, dosyayı açtığında doğrudan `create_agent` çağrısını görmeli — araya fonksiyon sarmak gereksiz soyutlama yaratır.

**Kanıt:**
- `src/agents/main_agent.py:76-91` — doğrudan `agent = create_agent(...)`
- `src/agents/subscription_agent.py:25-37` — aynı pattern
- `src/agents/billing_agent.py:50-63` — aynı pattern
- `src/agents/technical_agent.py:24-37` — aynı pattern

---

### ADR-03: Circular Import'ı Önleyen Import Zinciri

**Karar:** Modüller arası import sırası sabittir:

```
config → middleware → tools → agents → providers → router → main
```

Bu zincir tersine çevrilmez.

**Gerekçe:** Agent'lar tool'ları import eder, provider'lar agent'ları import eder, router provider'ları import eder. Bu tek yönlü akış circular import'u yapısal olarak imkansız kılar.

**Kanıt:**
- `src/config/llm.py` → hiçbir proje modülünü import etmez (sadece `settings`)
- `src/middleware/trim.py` → sadece `settings` import eder
- `src/tools/billing_tools.py` → hiçbir proje modülünü import etmez
- `src/agents/billing_agent.py` → `llm`, `settings`, `middleware`, `tools` import eder
- `src/providers.py` → `agents` import eder
- `src/api/router.py` → `providers`, `schemas`, `settings` import eder
- `main.py` → `router`, `providers`, `settings`, `checkpointer` import eder

---

## LLM ve Agent Tasarımı

### ADR-04: create_agent Tercih Edildi (create_react_agent Deprecated)

**Karar:** `from langchain.agents import create_agent` kullanılır. `create_react_agent` kullanılmaz.

**Gerekçe:** `create_react_agent` LangChain 2.0'da deprecated olarak işaretlenmiştir. `create_agent` aynı işlevselliği sunar ve `middleware`, `name`, `checkpointer`, `store` gibi ek parametreleri destekler.

**Kanıt:** Tüm agent dosyaları:
```python
from langchain.agents import create_agent
```

---

### ADR-05: Tek Shared LLM Instance

**Karar:** Tüm agent'lar aynı `ChatOpenAI` instance'ını kullanır. Her agent kendi LLM'ini oluşturmaz.

**Gerekçe:**
- Connection pool paylaşımı — her agent ayrı bağlantı açmaz
- Konfigürasyon tek noktada yönetilir — model değişikliği tek dosyadan yapılır
- vLLM endpoint bilgisi tekrarlanmaz

**Kanıt:** `src/config/llm.py:7-11`:
```python
llm = ChatOpenAI(
    base_url=settings.vllm_base_url,
    model=settings.vllm_model_name,
    api_key=settings.vllm_api_key,
)
```

Tüm agent'lar bu instance'ı import eder:
```python
from src.config.llm import llm
```

---

### ADR-06: Default Agent — main

**Karar:** `ChatRequest.agent_name` default değeri `"main"`. Client agent adı göndermezse istek `main` agent'a yönlenir. `get_agent()` fonksiyonu da default olarak `"main"` alır.

**Gerekçe:** `main_agent` supervisor rolündedir — alt agent'lara routing yapar. Agent adı bilmeyen veya göndermeyen client'lar otomatik olarak doğru giriş noktasına ulaşır. Bu, API'nin keşfedilebilirliğini artırır: yeni bir client ilk isteğini agent adı bilmeden gönderebilir.

**Kanıt:**
- `src/models/schemas.py:38-41`:
  ```python
  agent_name: str = Field(default="main", min_length=1, ...)
  ```
- `src/providers.py:42`:
  ```python
  def get_agent(agent_name: str = "main"):
  ```
- `src/providers.py:13-16` — AGENTS dict'inde `"main"` key'i her zaman mevcut

**Kısıt:** Registry'de `"main"` key'i her zaman bulunmalıdır. Aksi halde agent adı göndermeyen tüm client'lar `agent_not_found` hatası alır.

---

### ADR-07: LangGraph Sadece Altyapıda

**Karar:** `StateGraph`, `add_node`, `add_edge` gibi direkt LangGraph API'si kullanılmaz. LangGraph'tan sadece `AsyncSqliteSaver` (checkpointer) ve `RemoveMessage`/`REMOVE_ALL_MESSAGES` (trimming) kullanılır.

**Gerekçe:** `create_agent` dahili olarak LangGraph `CompiledStateGraph` döner ve tool çağrılarını, state yönetimini otomatik halleder. Manuel graf tanımlamak gereksiz karmaşıklık ekler ve template'in sadeliğini bozar.

**Kanıt:** Projede hiçbir dosyada `StateGraph`, `add_node`, `add_edge` import'u yok. Agent'lar `create_agent()` ile oluşturulur, bu fonksiyon arkada graf yapısını kurar.

---

## State Yönetimi

### ADR-08: Agent'lar Stateless Oluşturulur, Checkpointer Lifespan'da Wire Edilir

**Karar:** `create_agent(...)` çağrısında `checkpointer` parametresi verilmez. Checkpointer FastAPI lifespan'da oluşturulur ve `wire_checkpointer()` ile tüm agent'lara atanır.

**Gerekçe:**
- Agent'lar module-level'da oluşturulur (import time) — bu noktada async DB bağlantısı henüz mevcut değildir
- `AsyncSqliteSaver` async context gerektirir, module-level'da `await` kullanılamaz
- Tek bir checkpointer instance'ı tüm agent'lar arasında paylaşılır — her agent ayrı DB bağlantısı açmaz

**Kanıt:**
- Agent dosyalarında `checkpointer` parametresi yok:
  ```python
  # src/agents/subscription_agent.py:25-37
  agent = create_agent(model=llm, tools=[...], middleware=[...], system_prompt="...", name="...")
  ```
- Lifespan'da wire:
  ```python
  # main.py:29-30
  checkpointer = await init_checkpointer()
  wire_checkpointer(checkpointer)
  ```
- Wire fonksiyonu (`providers.py:33-39`):
  ```python
  def wire_checkpointer(checkpointer):
      for entry in AGENTS.values():
          entry["agent"].checkpointer = checkpointer
  ```

---

### ADR-09: Composite Thread ID

**Karar:** Thread ID formatı: `{app_id}:{user_id}:{session_id}`.

**Gerekçe:** Aynı agent'a farklı uygulamalardan gelen isteklerin state'lerini izole eder. Sadece `session_id` kullanılsaydı, farklı uygulamaların aynı session_id üretme ihtimali state karışmasına yol açardı.

**Kanıt:** `src/api/router.py:42`:
```python
thread_id = f"{req.app_id}:{req.user_id}:{req.session_id}"
```

Örnekler:
- `mobile-app:user-42:sess-abc` → mobil uygulamanın konuşması
- `web-portal:user-42:sess-xyz` → web portalın konuşması (aynı kullanıcı, tamamen ayrı state)

---

### ADR-10: Agent-as-Tool Ephemeral Thread ID

**Karar:** Sub-agent tool olarak çağrıldığında `tool:{uuid}` formatında tek kullanımlık thread_id verilir.

**Gerekçe:**
- Tool çağrısının sonucu zaten parent agent'ın state'ine yazılır (`AIMessage.tool_calls` + `ToolMessage`)
- Sub-agent'ın ayrıca history tutması çift kayıt oluşturur
- Her tool çağrısı izole ve tek kullanımlık olmalı — önceki çağrılardan etkilenmemeli

**Kanıt:** `src/agents/main_agent.py:31-34`:
```python
result = await subscription_agent.ainvoke(
    {"messages": [{"role": "user", "content": question}]},
    config={"configurable": {"thread_id": f"tool:{uuid.uuid4()}"}},
)
```

Aynı pattern `billing_agent.py:35-38`'de de kullanılır.

**Yerleşim kuralı:** Agent-as-tool wrapper fonksiyonu, tool'u **kullanan** agent'ın dosyasında tanımlanır — sub-agent'ın kendi dosyasında değil. Örneğin `ask_subscription_specialist` tool'u `subscription_agent.py`'de değil, onu çağıran `main_agent.py`'de tanımlıdır. `suggest_plan_change` tool'u da `billing_agent.py`'de tanımlıdır çünkü billing agent subscription agent'ı tool olarak kullanır.

| Tool wrapper | Tanımlandığı dosya | Çağırdığı sub-agent |
|---|---|---|
| `ask_subscription_specialist` | `src/agents/main_agent.py:23-35` | `subscription_agent` |
| `ask_billing_specialist` | `src/agents/main_agent.py:38-50` | `billing_agent` |
| `ask_technical_specialist` | `src/agents/main_agent.py:53-65` | `technical_agent` |
| `suggest_plan_change` | `src/agents/billing_agent.py:27-39` | `subscription_agent` |

---

### ADR-11: Session ID Yoksa Stateless

**Karar:** `session_id` gönderilmezse (`null`) agent stateless çalışır — checkpointer kullanılmaz, history tutulmaz.

**Gerekçe:** Tek seferlik sorgular (örn. "bugünkü hava durumu") için state tutmak gereksiz. Client stateful/stateless modu kendisi belirleyebilmeli.

**Kanıt:** `src/api/router.py:41-43`:
```python
if settings.chat_history_enabled and req.session_id:
    thread_id = f"{req.app_id}:{req.user_id}:{req.session_id}"
    config.setdefault("configurable", {})["thread_id"] = thread_id
```

`session_id` `None` ise `thread_id` config'e eklenmez → checkpointer devreye girmez.

---

## Middleware

### ADR-12: Middleware Sırası — Prompt Önce, Trim Sonra

**Karar:** Middleware listesi: `[langfuse_prompt, trim_old_messages]`. Langfuse prompt override ilk sırada, message trimming ikinci sırada çalışır.

**Gerekçe:** System prompt'un önce güncellenmesi gerekir, çünkü trim işlemi system prompt'u koruyarak (`include_system=True`) diğer mesajları kırpar. Sıra ters olsaydı, eski system prompt'a göre kırpma yapılır, ardından system prompt değişirdi — tutarsızlık oluşurdu.

**Kanıt:** Tüm agent dosyalarında aynı pattern (`main_agent.py:70-74`, `billing_agent.py:44-48`, `subscription_agent.py:19-23`, `technical_agent.py:18-22`):
```python
_middleware = [trim_old_messages]
if settings.langfuse_prompt_management_enabled:
    from src.middleware.prompt import langfuse_prompt
    _middleware.insert(0, langfuse_prompt)  # ← başa ekler
```

---

### ADR-13: Message Trimming Checkpoint'ten de Siler

**Karar:** Kırpılan mesajlar sadece LLM context'inden değil, checkpoint store'dan da `RemoveMessage(id=REMOVE_ALL_MESSAGES)` ile temizlenir.

**Gerekçe:** Sadece LLM context'ini kırpmak yetmez — checkpoint'te eski mesajlar kalırsa, bir sonraki istekte tekrar yüklenir ve tekrar kırpılır. Bu gereksiz I/O ve hesaplama maliyeti oluşturur. Checkpoint'ten silmek kalıcı çözümdür.

**Kanıt:** `src/middleware/trim.py:34-35`:
```python
return {
    "messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES), *trimmed],
}
```

`REMOVE_ALL_MESSAGES` özel bir sentinel — checkpoint'teki tüm mesajları siler, ardından `trimmed` listesini yeni state olarak yazar.

---

### ADR-14: Trim Eşiği — 4 Mesaj Altında Kırpma Yapılmaz

**Karar:** Mesaj sayısı 4 veya altındaysa trim atlanır.

**Gerekçe:** System prompt + user mesajı + assistant yanıtı + user mesajı = 4 mesaj. Bu minimal bir konuşma turu. Token sayısına bakmadan kırpmak anlamsız — bu eşik gereksiz `trim_messages` çağrısını önler.

**Kanıt:** `src/middleware/trim.py:19-20`:
```python
if len(messages) <= 4:
    return None
```

---

## Konfigürasyon

### ADR-15: Hardcoded Default Yasağı

**Karar:** `Settings` model'inde hiçbir alan default değer almaz. Tüm config `.env`'den okunur.

**Gerekçe:** Default değerler production'da tehlikelidir — `.env` dosyası eksik olduğunda uygulama sessizce yanlış değerlerle başlayabilir. Default olmadığında `.env` eksikse uygulama hemen başlangıçta hata verir (fail-fast).

**Kanıt:** `src/config/settings.py:4-25` — tüm alanlar default'suz:
```python
class Settings(BaseSettings):
    vllm_base_url: str          # default yok
    vllm_model_name: str        # default yok
    vllm_api_key: str           # default yok
    langfuse_enabled: bool      # default yok
    app_port: int               # default yok
    chat_history_enabled: bool  # default yok
    # ... tümü aynı
```

**Tek istisna:** `ChatRequest.agent_name` default'u `"main"` — bu API kontratının parçasıdır, config değil (bkz. ADR-06).

---

### ADR-16: Feature Toggle Pattern

**Karar:** Üç bağımsız feature flag ile özellikler açılıp kapatılabilir:
- `CHAT_HISTORY_ENABLED` — checkpointer ve state yönetimi
- `LANGFUSE_ENABLED` — observability ve tracing
- `LANGFUSE_PROMPT_MANAGEMENT_ENABLED` — runtime prompt override

**Gerekçe:** Özellikler birbirine bağımlı değil. Langfuse olmadan chat history çalışabilir, chat history olmadan Langfuse tracing çalışabilir. Bu bağımsızlık farklı deployment senaryolarını destekler (dev ortamında Langfuse kapalı, production'da açık gibi).

**Kanıt:**
- `main.py:28` — `if settings.chat_history_enabled:`
- `main.py:33` — `if settings.langfuse_prompt_management_enabled:`
- `providers.py:104` — `if not settings.langfuse_enabled: return {}`
- `router.py:41` — `if settings.chat_history_enabled and req.session_id:`

---

## Langfuse Entegrasyonu

### ADR-17: Langfuse Client Lazy Init + Singleton

**Karar:** Langfuse client ilk kullanımda oluşturulur ve global değişkende cache'lenir.

**Gerekçe:** Agent dosyaları module-level'da import edilir. Langfuse client'ı module-level'da oluşturmak, Langfuse kapalıyken bile bağlantı denemesi yapar. Lazy init ile client sadece gerçekten ihtiyaç duyulduğunda oluşturulur.

**Kanıt:** `src/middleware/prompt.py:18-28`:
```python
_langfuse_client = None

def _get_langfuse_client():
    global _langfuse_client
    if _langfuse_client is None:
        from langfuse import Langfuse
        _langfuse_client = Langfuse()
    return _langfuse_client
```

---

### ADR-18: Prompt Fallback Stratejisi — Hata Fırlatmaz

**Karar:** Langfuse erişilemezse agent dosyasındaki hardcoded system prompt korunur. Hata fırlatılmaz, sadece warning loglanır.

**Gerekçe:** Langfuse bir observability aracıdır — erişilememesi agent'ın çalışmasını durdurmamalıdır. Graceful degradation: Langfuse varsa güncel prompt kullanılır, yoksa hardcoded fallback ile devam edilir.

**Kanıt:** `src/middleware/prompt.py:45-67`:
```python
fallback_text = request.system_message.content if request.system_message else ""

try:
    prompt = client.get_prompt(agent_name, fallback=fallback_text, ...)
    # ...
    request = request.override(system_message=SystemMessage(content=compiled))
except Exception:
    logger.warning("Langfuse prompt fetch failed for %r, using existing system_prompt", ...)
```

---

### ADR-19: Startup'ta Prompt Cache Warm

**Karar:** Lifespan'da tüm agent'ların prompt'ları Langfuse'dan önceden çekilir.

**Gerekçe:** İlk kullanıcı isteğinde cold-cache nedeniyle oluşacak latency'yi önler. Langfuse `get_prompt` çağrısı cache TTL süresince (default 60s) tekrar network isteği yapmaz — startup'ta çekilen prompt'lar ilk isteklerde anında kullanılır.

**Kanıt:** `main.py:33-37`:
```python
if settings.langfuse_prompt_management_enabled:
    from src.middleware.prompt import warm_prompt_cache
    warm_prompt_cache(AGENTS)
```

`prompt.py:70-91` — her agent için `client.get_prompt(name, ...)` çağrılır.

---

### ADR-20: Agent Name = Langfuse Prompt Name

**Karar:** `create_agent(name="billing_agent")` ile verilen ad, Langfuse'da prompt araması için kullanılır. Ayrı bir mapping tablosu yoktur.

**Gerekçe:** Convention over configuration. Agent adı tek bir yerde tanımlanır (`create_agent(name=...)`), Langfuse'da aynı adla prompt oluşturulur. Ekstra mapping katmanı gereksiz.

**Kanıt:**
- Agent tanımı: `src/agents/billing_agent.py:62` — `name="billing_agent"`
- Middleware'de okuma: `src/middleware/prompt.py:40` — `config["metadata"]["lc_agent_name"]`
- Langfuse çağrısı: `src/middleware/prompt.py:49` — `client.get_prompt(agent_name, ...)`

---

## API Tasarımı

### ADR-21: OpenAI-Compatible Message Formatı

**Karar:** Request `messages` formatı OpenAI chat completion API'si ile uyumludur. `role` alanı `Literal["user", "assistant", "system", "tool"]`, `content` alanı `str | list[dict]` (multimodal destek).

**Gerekçe:** OpenAI formatı endüstri standardıdır. Mevcut client'lar (mobil app, web portal) minimum değişiklikle entegre olabilir. Multimodal destek (`content` listesi) görsel içerik göndermeyi mümkün kılar.

**Kanıt:** `src/models/schemas.py:20-28`:
```python
class Message(BaseModel):
    role: Literal["user", "assistant", "system", "tool"]
    content: str | list[dict[str, Any]]
```

---

### ADR-22: Response Envelope Pattern

**Karar:** Her yanıt `success` + `message` + `error` zarfında döner. Başarılıda `error=null`, hatada `message=null`.

**Gerekçe:** Client her zaman aynı response yapısını parse eder — HTTP status code'a bakmaya gerek kalmaz. `success` alanı boolean olarak hızlı kontrol sağlar. Hata detayı yapılandırılmış formattadır (`code` + `message` + `details`).

**Kanıt:** `src/models/schemas.py:80-110`:
```python
class ChatResponse(BaseModel):
    id: str
    success: bool
    message: Message | None = None      # başarılıda dolu, hatada null
    error: ErrorDetail | None = None    # hatada dolu, başarılıda null
    usage: Usage | None = None
    agent_name: str | None = None
    app_id: str
    user_id: str
    session_id: str | None = None
    created_at: datetime
```

---

### ADR-23: ErrorCode Closed Set

**Karar:** Hata kodları `Literal` ile kısıtlıdır. Router'da serbest string kullanılmaz. Yeni kod eklemek `ErrorCode` Literal'e eklemeyi gerektirir.

**Gerekçe:** Client'lar hata kodlarını programatik olarak handle eder (`switch/case`, `if/else`). Serbest string kullanılırsa client'lar bilinmeyen kodlarla karşılaşır ve hata handling kırılır. Closed set, API kontratının parçasıdır — yeni kod eklemek bilinçli bir karar olmalıdır.

**Kanıt:** `src/models/schemas.py:8-15`:
```python
ErrorCode = Literal[
    "agent_not_found",
    "invalid_request",
    "llm_error",
    "rate_limit",
    "timeout",
    "internal_error",
]
```

`router.py:76` ve `104` — sadece bu kodlar kullanılır: `"agent_not_found"`, `"llm_error"`.

---

### ADR-24: Discovery API Dual Format (TOON + JSON)

**Karar:** `GET /agents` default olarak TOON formatında, `?format=json` ile JSON formatında yanıt döner.

**Gerekçe:** TOON formatı JSON'a göre %30-60 daha az token kullanır. Bir orchestrator LLM bu endpoint'i okuyarak doğru agent'ı seçecekse, daha az token = daha düşük maliyet ve daha hızlı yanıt. JSON seçeneği insan tarafından okunabilirlik ve standart tooling uyumluluğu için korunmuştur.

**Kanıt:** `src/api/router.py:151-161`:
```python
@router.get("/agents")
async def list_agents(fmt: str = Query("toon", alias="format")):
    metadata = get_agents_metadata()
    if fmt == "json":
        return JSONResponse(content=metadata)
    return Response(content=toon_encode(metadata), media_type="text/toon")
```

---

### ADR-25: Tool Metadata Runtime Extraction

**Karar:** Discovery API'deki tool bilgileri manuel yazılmaz. Compiled agent'ın graph'ından `@tool` decorator bilgileri runtime'da otomatik çıkarılır.

**Gerekçe:** Manuel tool metadata yazmak senkronizasyon sorunu yaratır — tool değiştiğinde metadata güncellenmeyi unutulabilir. Runtime extraction ile `@tool` decorator'daki docstring ve type hint her zaman güncel metadata kaynağıdır.

**Kanıt:** `src/providers.py:50-74`:
```python
def _extract_tools(agent) -> list[dict]:
    tools_node = agent.nodes.get("tools")
    # ...
    tools_by_name = getattr(bound, "tools_by_name", {})
    for tool_obj in tools_by_name.values():
        schema = tool_obj.args_schema.model_json_schema() if tool_obj.args_schema else {}
        # ... parametre bilgilerini çıkar
        result.append({
            "name": tool_obj.name,
            "description": tool_obj.description.split("\n")[0],
            "parameters": ",".join(params),
        })
```

---

## Deployment

### ADR-26: Docker network_mode: host

**Karar:** Container `network_mode: host` ile çalışır.

**Gerekçe:** vLLM genellikle aynı makinede (localhost) çalışır. Bridge network kullanmak container'ın `localhost`'a erişimini engeller. `network_mode: host` ile container doğrudan host network'ünü kullanır ve `VLLM_BASE_URL=http://localhost:8000/v1` çalışır.

**Kanıt:** `docker-compose.yml:4`:
```yaml
services:
  app:
    build: .
    network_mode: host
    env_file: .env
```

**Trade-off:** Port izolasyonu kaybedilir. Production'da vLLM ayrı bir makinedeyse `network_mode: host` yerine bridge network + vLLM URL değişikliği yapılabilir.

---

## Operasyonel Kurallar

### ADR-27: Manuel Agent Registry

**Karar:** Yeni agent'lar `providers.py` içindeki `AGENTS` dict'ine manuel olarak eklenir. Auto-discovery (dosya tarama, decorator ile otomatik kayıt vb.) mekanizması yoktur.

**Gerekçe:**
- Hangi agent'ların aktif olduğu tek bir dosyada (`providers.py`) açıkça görünür
- Auto-discovery gizli bağımlılıklar yaratır — bir dosya silindi mi yoksa kasıtlı olarak registry'den mi çıkarıldı anlaşılmaz
- Import sırası ve circular import kontrolü elle yönetildiğinde daha öngörülebilir

**Kanıt:** `src/providers.py:7-30`:
```python
from src.agents.billing_agent import agent as billing_agent
from src.agents.main_agent import agent as main_agent
from src.agents.subscription_agent import agent as subscription_agent
from src.agents.technical_agent import agent as technical_agent

AGENTS = {
    "main": {
        "agent": main_agent,
        "description": "Customer support manager. Routes to subscription/billing/technical specialists.",
    },
    "subscription": {
        "agent": subscription_agent,
        "description": "Subscription specialist. Plan info, upgrades, comparisons, packages.",
    },
    # ...
}
```

**Yeni agent ekleme checklist'i:**

| # | Adım | Dosya |
|---|---|---|
| 1 | `@tool` fonksiyonlarını yaz | `src/tools/<domain>_tools.py` |
| 2 | Agent'ı oluştur (`create_agent`, checkpointer verme) | `src/agents/<domain>_agent.py` |
| 3 | Agent'ı import et ve `AGENTS` dict'ine ekle | `src/providers.py` |
| 4 | API'den `agent_name: "<domain>"` ile çağır | — |

Agent-as-tool olarak kullanılacaksa ek adım:

| # | Adım | Dosya |
|---|---|---|
| 5 | Sub-agent'ı import et, `@tool async def` wrapper yaz | Çağıran agent'ın dosyası (ör. `src/agents/main_agent.py`) |
| 6 | Wrapper'ı `create_agent(tools=[...])` listesine ekle | Aynı dosya |

> **Not:** `providers.py`'ye eklemeyi unutmak, agent'ın API'den erişilememesine neden olur. `GET /agents` discovery endpoint'i sadece `AGENTS` dict'indeki agent'ları listeler.
