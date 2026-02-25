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
├── config/
│   ├── settings.py   # .env'den okur, hardcoded default yok
│   └── llm.py        # shared ChatOpenAI — tüm agent'lar buradan alır
├── models/schemas.py # Stable API contract — DEĞİŞTİRME
├── memory/checkpointer.py  # AsyncSqliteSaver (checkpoints.db)
├── api/router.py     # POST /chat, POST /chat/stream (SSE)
└── providers.py      # AGENTS dict (registry) + wire_checkpointer + Langfuse handler
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

### Akış
```
main.py lifespan → init_checkpointer() → wire_checkpointer(checkpointer)
                                              ↓
API isteği → router._build_config() → composite thread_id oluştur
                                              ↓
         agent.ainvoke(config={thread_id}) → checkpointer state yükler/kaydeder
                                              ↓
         agent tool çağırırsa → sub_agent.ainvoke(thread_id="tool:{uuid}")
                                              ↓
                                   ephemeral, izole, tek kullanım
```

## Yeni agent ekleme (4 adım)

1. `tools/<domain>_tools.py` — pure @tool fonksiyonları yaz
2. `agents/<domain>_agent.py` — `from src.config.llm import llm`, `agent = create_agent(...)` yaz (checkpointer verme)
3. `providers.py` → AGENTS dict'ine `"<domain>": agent` ekle
4. API'den `agent_name: "<domain>"` ile çağır

Bir agent başka bir agent'ı tool olarak kullanacaksa:
- O agent'ın `agent` objesini import et
- `@tool` + `async def` ile sar
- `await agent.ainvoke(...)` çağır, `config={"configurable": {"thread_id": f"tool:{uuid.uuid4()}"}}` geç

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
- Circular import oluşturma. Akış: config → tools → agents → providers → router → main
- Mevcut template pattern'ını bozma. Yeni dosya eklerken mevcut agent/tool dosyalarını referans al
