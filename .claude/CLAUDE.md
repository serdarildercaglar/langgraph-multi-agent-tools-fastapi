# CLAUDE.md

## Bu proje nedir

LangChain + FastAPI tabanlı **agentic projeler için code template**.
Amaç: Bu template'i kullanarak hızlıca yeni agent'lar çıkarmak ve farklı ekiplerin yazdığı agent'ların aynı modüler standartta olmasını sağlamak.

Mevcut senaryo (e-commerce customer support) sadece örnek. Template herhangi bir domain'e uyarlanabilir.

Stack: LangChain 1.2.x (`create_agent`), FastAPI, Langfuse, vLLM (OpenAI-compatible).
LangGraph sadece altyapıda (checkpointer: `langgraph.checkpoint.memory.MemorySaver`). Direkt LangGraph API'si (StateGraph vb.) kullanılmıyor.

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
├── models/schemas.py # ChatRequest (agent_name) / ChatResponse
├── memory/checkpointer.py  # MemorySaver singleton
├── api/router.py     # POST /chat, POST /chat/stream (SSE)
└── providers.py      # AGENTS dict (registry) + Langfuse handler
```

## Yeni agent ekleme (4 adım)

1. `tools/<domain>_tools.py` — pure @tool fonksiyonları yaz
2. `agents/<domain>_agent.py` — llm, checkpointer import et, `agent = create_agent(...)` yaz
3. `providers.py` → AGENTS dict'ine `"<domain>": agent` ekle
4. API'den `agent_name: "<domain>"` ile çağır

Bir agent başka bir agent'ı tool olarak kullanacaksa: o agent'ın `agent` objesini import edip `@tool` ile sar.

## Kurallar — kesinlikle uy

- Wrapper / factory fonksiyon YAZMA (build_*, make_*, create_* def'leri yasak)
- Agent dosyası module-level `agent = create_agent(...)` ile bitmeli, fonksiyona sarma
- `from langchain.agents import create_agent` kullan. `create_react_agent` KULLANMA (deprecated)
- `from langchain.tools import tool` kullan. `langchain_core` değil
- Config'e hardcoded default KOYMA, her şey .env'den gelmeli
- LLM tekrarlama, `src.config.llm.llm`'den import et
- Circular import oluşturma. Akış: config → tools → agents → providers → router → main
- Mevcut template pattern'ını boz. Yeni dosya eklerken mevcut agent/tool dosyalarını referans al
