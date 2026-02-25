# CLAUDE.md

## Bu proje nedir

LangChain + FastAPI tabanlı **agentic projeler için code template**.
Amaç: Bu template'i kullanarak hızlıca yeni agent'lar çıkarmak ve farklı ekiplerin yazdığı agent'ların aynı modüler standartta olmasını sağlamak.

Mevcut senaryo (e-commerce customer support) sadece örnek. Template herhangi bir domain'e uyarlanabilir.

Stack: LangChain 1.2.x (`create_agent`), FastAPI, Langfuse, vLLM (OpenAI-compatible).
LangGraph sadece altyapıda (checkpointer: `AsyncSqliteSaver`). Direkt LangGraph API'si (StateGraph vb.) kullanılmıyor.

## Komutlar

```bash
conda activate langchain          # Python 3.12
pip install -r requirements.txt
python main.py                    # port: APP_PORT (.env)
```

## Template yapısı

```
src/
├── agents/           # Her agent = standalone .py dosyası
│   └── <domain>_agent.py
├── tools/            # Her agent'ın tool'ları ayrı dosyada
│   └── <domain>_tools.py
├── middleware/
│   └── trim.py       # @before_model — trim_messages ile history kırpma
├── config/
│   ├── settings.py   # .env'den okur, hardcoded default yok
│   └── llm.py        # shared ChatOpenAI — tüm agent'lar buradan alır
├── models/schemas.py # Stable API contract — DEĞİŞTİRME
├── memory/checkpointer.py  # AsyncSqliteSaver (checkpoints.db)
├── api/router.py     # POST /chat, POST /chat/stream (SSE), GET /agents (discovery)
└── providers.py      # AGENTS dict (registry) + wire_checkpointer + Langfuse handler + discovery metadata
UI/                   # Static frontend (FastAPI /ui/ ile serve edilir)
main.py               # FastAPI app + lifespan (checkpointer init/shutdown)
```

## schemas.py — sabit API kontratı

`schemas.py` değiştirilmez. Tüm projeler bu standartlara uyar:
- Request: OpenAI chat completion formatı (`messages` listesi, multimodal destekli)
- Response: `success` + `message` + `error` zarfı, `id`, `usage`, `created_at`
- Validation: `min_length`, `Literal` role, `ge=0` token sayıları
- Yeni alan eklemek gerekirse mevcut alanları BOZMA, sadece optional alan ekle

## Checkpointer ve state yönetimi

### Mimari prensip
- Agent'lar **stateless** oluşturulur (checkpointer create_agent'a verilmez)
- Checkpointer **lifespan'da** oluşturulur → `wire_checkpointer()` ile agent'lara atanır
- State izolasyonu **composite thread_id** ile sağlanır

### Composite thread_id
```
thread_id = "{app_id}:{user_id}:{session_id}"
```
Farklı uygulamalardan aynı agent'a gelen istekler birbirinden izole:
- `appA:user1:sess1` → A uygulamasının konuşması
- `appB:user5:sess3` → B uygulamasının konuşması (tamamen ayrı state)

### Agent-as-tool çağrılarında state
Sub-agent tool olarak çağrıldığında **ephemeral thread_id** kullanılır (`tool:{uuid}`):
- Tool çağrısının sonucu zaten **parent agent'ın state'ine** yazılır (AIMessage.tool_calls + ToolMessage)
- Sub-agent'ın ayrıca history tutmasına gerek yok — çift kayıt olur
- Her tool çağrısı izole ve tek kullanımlık

### Message trimming (middleware)
- `@before_model` middleware her LLM çağrısından önce çalışır
- `trim_messages(strategy="last", token_counter="approximate", max_tokens=CHAT_HISTORY_MAX_TOKENS)`
- System prompt her zaman korunur (`include_system=True`)
- Kırpılan mesajlar checkpoint'ten silinir (`RemoveMessage(id=REMOVE_ALL_MESSAGES)`)
- Tüm agent'lar `middleware=[trim_old_messages]` ile oluşturulmalı
- Token limiti `.env`'den `CHAT_HISTORY_MAX_TOKENS` ile ayarlanır

### Akış
```
main.py lifespan → init_checkpointer() → wire_checkpointer(checkpointer)
                                              ↓
API isteği → router._build_config() → composite thread_id oluştur
                                              ↓
         agent.ainvoke(config={thread_id}) → checkpointer state yükler/kaydeder
                                              ↓
         @before_model trim_old_messages → eski mesajları kırp
                                              ↓
         agent tool çağırırsa → sub_agent.ainvoke(thread_id="tool:{uuid}")
                                              ↓
                                   ephemeral, izole, tek kullanım
```

## Yeni agent ekleme (4 adım)

1. `tools/<domain>_tools.py` — pure @tool fonksiyonları yaz
2. `agents/<domain>_agent.py` — `from src.config.llm import llm`, `from src.middleware.trim import trim_old_messages`, `agent = create_agent(..., middleware=[trim_old_messages])` yaz (checkpointer verme)
3. `providers.py` → AGENTS dict'ine ekle: `"<domain>": {"agent": agent, "description": "Kısa açıklama."}`
4. API'den `agent_name: "<domain>"` ile çağır — `GET /agents` otomatik olarak yeni agent'ı listeler

Bir agent başka bir agent'ı tool olarak kullanacaksa:
- O agent'ın `agent` objesini import et
- `@tool` + `async def` ile sar
- `await agent.ainvoke(...)` çağır, `config={"configurable": {"thread_id": f"tool:{uuid.uuid4()}"}}` geç

## Discovery API — GET /agents

Cross-app agent keşfi için. Bir orchestrator agent bu endpoint'i okuyup doğru agent'ı seçebilir.

### Format
- **Default: TOON** (`text/toon`) — LLM-friendly, JSON'a göre %30-60 daha az token
- **JSON:** `?format=json` query param ile

### Metadata kaynağı
- Agent adı ve description → `providers.py` AGENTS dict'inden
- Tool bilgileri → compiled agent'tan runtime'da çekilir (`agent.nodes['tools'].bound.tools_by_name`)
- Manuel tool metadata yazmaya gerek yok — `@tool` decorator'dan otomatik gelir

### AGENTS dict formatı
```python
AGENTS = {
    "<domain>": {
        "agent": agent,           # compiled agent objesi
        "description": "Kısa açıklama.",  # discovery API'de görünür
    },
}
```

## Kurallar — kesinlikle uy

- `schemas.py`'yi DEĞİŞTİRME. Bu dosya sabit API kontratı
- Wrapper / factory fonksiyon YAZMA (build_*, make_*, create_* def'leri yasak)
- Agent dosyası module-level `agent = create_agent(...)` ile bitmeli, fonksiyona sarma
- Agent'a create_agent'da checkpointer VERME — lifespan'da wire edilir
- Agent-as-tool wrapper'lar `async def` olmalı, `await agent.ainvoke()` kullanmalı
- `from langchain.agents import create_agent` kullan. `create_react_agent` KULLANMA (deprecated)
- `from langchain.tools import tool` kullan. `langchain_core` değil
- Config'e hardcoded default KOYMA, her şey .env'den gelmeli
- LLM tekrarlama, `src.config.llm.llm`'den import et
- Circular import oluşturma. Akış: config → middleware → tools → agents → providers → router → main
- Mevcut template pattern'ını bozma. Yeni dosya eklerken mevcut agent/tool dosyalarını referans al
