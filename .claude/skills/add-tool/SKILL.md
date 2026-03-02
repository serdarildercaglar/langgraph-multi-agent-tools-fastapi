---
name: add-tool
description: Add new tools to an existing agent following the @tool pattern. Use when adding functions, capabilities, or integrations to agents.
argument-hint: "[domain-name] [tool-description]"
---

# Add New Tool

Add a new tool to the `$0` agent domain.

## Tool Template

Add to `src/tools/{domain}_tools.py`:

```python
@tool
def tool_name(param1: str, param2: int) -> str:
    """One-line description — this shows in the discovery API.

    Args:
        param1: Clear description of first parameter.
        param2: Clear description of second parameter.
    """
    # Implementation
    return "result string"
```

## Rules

### Imports
- `from langchain.tools import tool` — NOT `langchain_core.tools`

### Docstring Format
- **First line**: One sentence, imperative mood (e.g., "Search products by keyword.")
- **Args section**: Every parameter documented with type and purpose
- The docstring is what the LLM reads to decide when to use the tool — write it carefully

### Function Signature
- All parameters must have type hints
- Return type is always `str`
- Use descriptive parameter names (not `q`, `x`, `data`)
- Optional parameters: use `param: str = "default"` with type hint

### Async Tools (for agent-as-tool only)
```python
@tool
async def delegate_to_agent(question: str) -> str:
    """Delegate to specialist agent."""
    result = await other_agent.ainvoke(
        {"messages": [{"role": "user", "content": question}]},
        config={"configurable": {"thread_id": f"tool:{uuid.uuid4()}"}},
    )
    return result["messages"][-1].content
```

### After Adding
1. Import the new tool in the agent file: `from src.tools.{domain}_tools import new_tool`
2. Add to the agent's `tools=[..., new_tool]` list
3. The discovery API (`GET /agents`) will automatically pick up the new tool metadata

## Forbidden
- No side effects unless calling real backend APIs
- No hardcoded URLs or credentials — use settings
- No `langchain_core.tools` imports
- No class-based tools — use `@tool` decorated functions
