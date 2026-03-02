"""Layer 2: FastAPI endpoint tests."""

import json

import pytest


# --- POST /chat ---


@pytest.mark.integration
async def test_post_chat_success(app_client, valid_chat_request):
    resp = await app_client.post("/chat", json=valid_chat_request)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["message"]["role"] == "assistant"
    assert len(data["message"]["content"]) > 0


@pytest.mark.integration
async def test_post_chat_default_agent(app_client):
    """When agent_name is omitted, main agent handles the request."""
    payload = {
        "app_id": "test",
        "user_id": "u1",
        "session_id": "s-default",
        "messages": [{"role": "user", "content": "Hi there"}],
    }
    resp = await app_client.post("/chat", json=payload)
    data = resp.json()
    assert data["success"] is True
    assert data["agent_name"] == "main"


@pytest.mark.integration
async def test_post_chat_specific_agent(app_client):
    payload = {
        "app_id": "test",
        "user_id": "u1",
        "session_id": "s-product",
        "agent_name": "product",
        "messages": [{"role": "user", "content": "Search for laptops"}],
    }
    resp = await app_client.post("/chat", json=payload)
    data = resp.json()
    assert data["success"] is True
    assert data["agent_name"] == "product"


async def test_post_chat_invalid_agent(app_client):
    payload = {
        "app_id": "test",
        "user_id": "u1",
        "agent_name": "xyz",
        "messages": [{"role": "user", "content": "Hi"}],
    }
    resp = await app_client.post("/chat", json=payload)
    data = resp.json()
    assert data["success"] is False
    assert data["error"]["code"] == "agent_not_found"


async def test_post_chat_missing_fields(app_client):
    """Missing required field returns 422."""
    resp = await app_client.post("/chat", json={"user_id": "u1"})
    assert resp.status_code == 422


@pytest.mark.integration
async def test_post_chat_usage_returned(app_client, valid_chat_request):
    resp = await app_client.post("/chat", json=valid_chat_request)
    data = resp.json()
    assert data["success"] is True
    assert data["usage"] is not None
    assert data["usage"]["prompt_tokens"] > 0
    assert data["usage"]["total_tokens"] > 0


@pytest.mark.integration
async def test_post_chat_echo_fields(app_client):
    payload = {
        "app_id": "echo-app",
        "user_id": "echo-user",
        "session_id": "echo-sess",
        "messages": [{"role": "user", "content": "ping"}],
    }
    resp = await app_client.post("/chat", json=payload)
    data = resp.json()
    assert data["app_id"] == "echo-app"
    assert data["user_id"] == "echo-user"
    assert data["session_id"] == "echo-sess"


# --- POST /chat/stream ---


@pytest.mark.integration
async def test_stream_tokens(app_client, valid_chat_request):
    """SSE stream produces token events."""
    resp = await app_client.post(
        "/chat/stream",
        json=valid_chat_request,
        headers={"Accept": "text/event-stream"},
    )
    assert resp.status_code == 200
    text = resp.text
    assert "event: token" in text


@pytest.mark.integration
async def test_stream_done(app_client, valid_chat_request):
    """SSE stream ends with done event."""
    resp = await app_client.post(
        "/chat/stream",
        json=valid_chat_request,
        headers={"Accept": "text/event-stream"},
    )
    assert "event: done" in resp.text


async def test_stream_invalid_agent(app_client):
    payload = {
        "app_id": "test",
        "user_id": "u1",
        "agent_name": "nonexistent",
        "messages": [{"role": "user", "content": "Hi"}],
    }
    resp = await app_client.post(
        "/chat/stream",
        json=payload,
        headers={"Accept": "text/event-stream"},
    )
    assert "event: error" in resp.text
    assert "agent_not_found" in resp.text


# --- GET /agents ---


async def test_get_agents_json(app_client):
    resp = await app_client.get("/agents?format=json")
    assert resp.status_code == 200
    data = resp.json()
    assert "agents" in data
    names = [a["name"] for a in data["agents"]]
    assert "main" in names
    assert "product" in names
    assert "order" in names


async def test_get_agents_toon(app_client):
    resp = await app_client.get("/agents")
    assert resp.status_code == 200
    assert "text/toon" in resp.headers["content-type"]


async def test_get_agents_tool_metadata(app_client):
    resp = await app_client.get("/agents?format=json")
    data = resp.json()
    product_agent = next(a for a in data["agents"] if a["name"] == "product")
    tool_names = [t["name"] for t in product_agent["tools"]]
    assert "search_products" in tool_names
    for tool in product_agent["tools"]:
        assert "name" in tool
        assert "description" in tool
        assert "parameters" in tool
