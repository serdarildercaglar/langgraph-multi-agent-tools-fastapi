"""Layer 6a: Schema validation tests."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.models.schemas import (
    ChatRequest,
    ChatResponse,
    ErrorCode,
    ErrorDetail,
    Message,
    Usage,
)


# --- ChatRequest ---


def test_chat_request_valid():
    req = ChatRequest(
        app_id="app1",
        user_id="user1",
        messages=[Message(role="user", content="hi")],
    )
    assert req.app_id == "app1"
    assert req.agent_name == "main"


def test_default_agent_name():
    req = ChatRequest(
        app_id="a", user_id="u", messages=[Message(role="user", content="x")]
    )
    assert req.agent_name == "main"


def test_empty_app_id_fails():
    with pytest.raises(ValidationError):
        ChatRequest(
            app_id="", user_id="u", messages=[Message(role="user", content="x")]
        )


def test_empty_messages_fails():
    with pytest.raises(ValidationError):
        ChatRequest(app_id="a", user_id="u", messages=[])


def test_invalid_role_fails():
    with pytest.raises(ValidationError):
        Message(role="admin", content="hi")


# --- ErrorDetail & ErrorCode ---


def test_valid_error_code():
    err = ErrorDetail(code="agent_not_found", message="not found")
    assert err.code == "agent_not_found"


def test_invalid_error_code_fails():
    with pytest.raises(ValidationError):
        ErrorDetail(code="unknown_code", message="bad")


def test_all_error_codes_valid():
    codes = [
        "agent_not_found",
        "invalid_request",
        "llm_error",
        "rate_limit",
        "timeout",
        "internal_error",
    ]
    for code in codes:
        err = ErrorDetail(code=code, message="test")
        assert err.code == code


# --- ChatResponse ---


def test_created_at_auto():
    resp = ChatResponse(
        id="123",
        success=True,
        app_id="a",
        user_id="u",
    )
    assert isinstance(resp.created_at, datetime)
    assert resp.created_at.tzinfo is not None


# --- Usage ---


def test_negative_tokens_fails():
    with pytest.raises(ValidationError):
        Usage(prompt_tokens=-1, completion_tokens=0, total_tokens=0)


# --- Multimodal ---


def test_multimodal_content():
    msg = Message(
        role="user",
        content=[
            {"type": "text", "text": "What is this?"},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}},
        ],
    )
    assert isinstance(msg.content, list)
    assert len(msg.content) == 2
