---
name: review-pattern
description: Review code changes for compliance with the project's design patterns and conventions. Use after modifying agents, tools, providers, or middleware to verify pattern adherence.
---

# Review Pattern Compliance

Review all recent code changes against the project's strict design conventions.

## Checklist

### 1. Import Rules
- [ ] `create_agent` from `langchain.agents` (NOT `create_react_agent`, NOT `langgraph.prebuilt`)
- [ ] `tool` from `langchain.tools` (NOT `langchain_core.tools`)
- [ ] `llm` from `src.config.llm` (NOT creating new ChatOpenAI instances)
- [ ] `trim_old_messages` from `src.middleware.trim`
- [ ] No circular imports. Valid chain: config -> middleware -> tools -> agents -> providers -> router -> main

### 2. Agent Creation
- [ ] Module-level `agent = create_agent(...)` — no factory/wrapper functions (build_*, make_*, create_*)
- [ ] `_middleware` list built conditionally: `[trim_old_messages]` + `langfuse_prompt` if enabled
- [ ] `checkpointer` parameter NOT passed (wired at lifespan)
- [ ] `name` parameter is lowercase snake_case matching filename — **also the Langfuse prompt name**
- [ ] `system_prompt` is clear and domain-specific (serves as fallback when Langfuse unreachable)

### 3. Tool Definitions
- [ ] `@tool` decorator on every tool function
- [ ] Docstring with one-line summary + Args section
- [ ] All parameters have type hints
- [ ] Return type is `str`
- [ ] Agent-as-tool wrappers are `async def`
- [ ] Ephemeral thread_id: `f"tool:{uuid.uuid4()}"` for sub-agent calls

### 4. Provider Registration
- [ ] Agent added to AGENTS dict in `src/providers.py`
- [ ] Dict entry has `"agent"` and `"description"` keys
- [ ] Description is concise and meaningful for discovery API

### 5. Config & Environment
- [ ] No hardcoded defaults anywhere — all from `.env` via settings
- [ ] No new ChatOpenAI/LLM instances — use shared `llm`
- [ ] New error codes added to `ErrorCode` Literal in `src/models/schemas.py` (not free-form strings)
- [ ] Router error responses use only codes defined in `ErrorCode`

### 6. State Management
- [ ] Composite thread_id format: `"{app_id}:{user_id}:{session_id}"`
- [ ] Agent-as-tool uses ephemeral thread_id: `f"tool:{uuid.uuid4()}"`
- [ ] No checkpointer passed to create_agent

### 7. Langfuse Prompt Management (if enabled)
- [ ] `langfuse_prompt` middleware conditionally added: `if settings.langfuse_prompt_management_enabled`
- [ ] `langfuse_prompt` inserted at index 0 (before `trim_old_messages`)
- [ ] `create_agent(name=...)` matches Langfuse prompt name
- [ ] Hardcoded `system_prompt` kept as fallback
- [ ] No direct Langfuse client usage in agent files — only via middleware

### 8. Code Style
- [ ] Files named `{domain}_tools.py` and `{domain}_agent.py`
- [ ] No unnecessary abstractions or over-engineering
- [ ] No wrapper/factory functions
- [ ] No extra docstrings/comments on unchanged code

## How to Review

1. Read all changed files
2. Check each item in the checklist above
3. Report violations with file path and line number
4. Suggest specific fixes for each violation

## Common Violations

| Violation | Fix |
|---|---|
| `from langchain_core.tools import tool` | Change to `from langchain.tools import tool` |
| `create_react_agent(...)` | Change to `create_agent(...)` from `langchain.agents` |
| `agent = create_agent(..., checkpointer=cp)` | Remove `checkpointer` param |
| `def build_agent():` wrapper | Replace with module-level `agent = create_agent(...)` |
| `ChatOpenAI(...)` in agent file | Import `llm` from `src.config.llm` |
| Missing `middleware=[trim_old_messages]` | Add middleware param |
| `def sync_tool():` for agent-as-tool | Change to `async def` |
| Missing `langfuse_prompt` in middleware (when enabled) | Add conditional `_middleware` pattern |
| `create_agent(name=...)` doesn't match Langfuse prompt | Ensure name matches exactly |
