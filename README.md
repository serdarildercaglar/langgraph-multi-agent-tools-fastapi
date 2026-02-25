# LangChain Multi-Agent API Template

Agentic projeler için **code template**. LangChain 1.2.x (`create_agent`), FastAPI, Langfuse, vLLM.

## Project Structure

```
src/
├── agents/
│   ├── product_agent.py      # Product search, details, recommendations
│   ├── order_agent.py        # Order tracking, returns, exchanges (uses product_agent as tool)
│   └── main_agent.py         # Supervisor — routes to product/order agents
├── tools/
│   ├── product_tools.py      # @tool: search_products, get_product_details, get_recommendations
│   └── order_tools.py        # @tool: track_order, initiate_return, initiate_exchange
├── api/
│   └── router.py             # POST /chat  &  POST /chat/stream (SSE)
├── config/
│   ├── settings.py           # pydantic-settings (.env)
│   └── llm.py                # Shared ChatOpenAI instance
├── models/
│   └── schemas.py            # ChatRequest / ChatResponse (stable API contract)
├── memory/
│   └── checkpointer.py       # SqliteSaver (checkpoints.db)
└── providers.py              # Agent registry & Langfuse handler
main.py                       # FastAPI entry point
```

## Quick Start

```bash
conda create -n langchain python=3.12 -y
conda activate langchain
pip install -r requirements.txt
cp .env.example .env   # fill in your values
python main.py
```

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
| `APP_ENV` | development / production |
| `APP_PORT` | Server port |
| `CHAT_HISTORY_ENABLED` | true = conversational, false = stateless Q&A |
