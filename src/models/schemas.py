from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


# --- Message ---------------------------------------------------------------

class Message(BaseModel):
    """OpenAI-compatible message format."""

    role: Literal["user", "assistant", "system", "tool"] = Field(
        description="Message role",
    )
    content: str | list[dict[str, Any]] = Field(
        description="Text string or multimodal content list (OpenAI format)",
    )


# --- Request ---------------------------------------------------------------

class ChatRequest(BaseModel):
    """Agent invocation request."""

    app_id: str = Field(min_length=1, description="Application identifier")
    user_id: str = Field(min_length=1, description="User identifier")
    agent_name: str = Field(
        default="main",
        min_length=1,
        description="Target agent: 'main', 'product', 'order', etc.",
    )
    session_id: str | None = Field(
        default=None,
        description="Session ID for chat history. None = stateless.",
    )
    messages: list[Message] = Field(
        min_length=1,
        description="Conversation messages (OpenAI format)",
    )
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Custom key-value pairs (department, priority, etc.)",
    )


# --- Response --------------------------------------------------------------

class Usage(BaseModel):
    """Token usage statistics."""

    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)


class ErrorDetail(BaseModel):
    """Structured error information."""

    code: str = Field(
        description="Error code: agent_not_found, invalid_request, llm_error",
    )
    message: str = Field(description="Human-readable error message")
    details: dict[str, Any] | None = Field(
        default=None,
        description="Extra context (validation errors, etc.)",
    )


class ChatResponse(BaseModel):
    """Agent invocation response."""

    id: str = Field(description="Unique response ID (UUID)")
    success: bool = Field(description="Whether the request succeeded")
    message: Message | None = Field(
        default=None,
        description="Agent response message (null on error)",
    )
    error: ErrorDetail | None = Field(
        default=None,
        description="Error details (null on success)",
    )
    usage: Usage | None = Field(
        default=None,
        description="Token usage statistics",
    )
    agent_name: str | None = Field(
        default=None,
        description="Which agent handled the request",
    )
    app_id: str = Field(description="Echo of request app_id")
    user_id: str = Field(description="Echo of request user_id")
    session_id: str | None = Field(
        default=None,
        description="Echo of request session_id",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Response timestamp (UTC)",
    )
