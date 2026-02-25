"""FastAPI router — /chat (sync), /chat/stream (SSE), /agents (discovery)."""

from __future__ import annotations

import json
import logging
import uuid

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse, Response
from sse_starlette.sse import EventSourceResponse
from toon import encode as toon_encode

from src.config.settings import settings
from src.models.schemas import (
    ChatRequest,
    ChatResponse,
    ErrorDetail,
    Message,
    Usage,
)
from src.providers import get_agent, get_agents_metadata, get_langfuse_handler

logger = logging.getLogger(__name__)

router = APIRouter()


def _build_config(req: ChatRequest) -> dict:
    """Merge Langfuse metadata and optional thread_id into a single config.

    thread_id = app_id:user_id:session_id
    Bu composite key farklı uygulamalardan gelen isteklerin
    aynı agent üzerinde state karışmasını önler.
    """
    config = get_langfuse_handler(
        user_id=req.user_id,
        session_id=req.session_id,
        app_id=req.app_id,
    )
    if settings.chat_history_enabled and req.session_id:
        thread_id = f"{req.app_id}:{req.user_id}:{req.session_id}"
        config.setdefault("configurable", {})["thread_id"] = thread_id
    return config


def _build_messages(req: ChatRequest) -> list[dict]:
    """Convert request messages to dict format for the agent."""
    return [m.model_dump() for m in req.messages]


def _extract_usage(result: dict) -> Usage | None:
    """Extract token usage from agent result if available."""
    ai_message = result["messages"][-1]
    usage_meta = getattr(ai_message, "usage_metadata", None)
    if usage_meta:
        return Usage(
            prompt_tokens=usage_meta.get("input_tokens", 0),
            completion_tokens=usage_meta.get("output_tokens", 0),
            total_tokens=usage_meta.get("total_tokens", 0),
        )
    return None


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    """Invoke the agent and return the final response."""
    response_id = str(uuid.uuid4())

    try:
        agent = get_agent(req.agent_name)
    except ValueError as e:
        return ChatResponse(
            id=response_id,
            success=False,
            error=ErrorDetail(code="agent_not_found", message=str(e)),
            app_id=req.app_id,
            user_id=req.user_id,
            session_id=req.session_id,
        )

    try:
        config = _build_config(req)
        result = await agent.ainvoke(
            {"messages": _build_messages(req)},
            config=config,
        )
        ai_message = result["messages"][-1]
        return ChatResponse(
            id=response_id,
            success=True,
            message=Message(role="assistant", content=ai_message.content),
            usage=_extract_usage(result),
            agent_name=req.agent_name,
            app_id=req.app_id,
            user_id=req.user_id,
            session_id=req.session_id,
        )
    except Exception as e:
        logger.exception("Agent invocation failed")
        return ChatResponse(
            id=response_id,
            success=False,
            error=ErrorDetail(code="llm_error", message=str(e)),
            agent_name=req.agent_name,
            app_id=req.app_id,
            user_id=req.user_id,
            session_id=req.session_id,
        )


@router.post("/chat/stream")
async def chat_stream(req: ChatRequest) -> EventSourceResponse:
    """Stream agent output token-by-token via Server-Sent Events."""
    try:
        agent = get_agent(req.agent_name)
    except ValueError as e:
        async def error_generator():
            yield {
                "event": "error",
                "data": json.dumps({"code": "agent_not_found", "message": str(e)}),
            }
        return EventSourceResponse(error_generator())

    config = _build_config(req)

    async def event_generator():
        try:
            async for token, metadata in agent.astream(
                {"messages": _build_messages(req)},
                config=config,
                stream_mode="messages",
            ):
                if hasattr(token, "content") and token.content:
                    yield {
                        "event": "token",
                        "data": json.dumps({"content": token.content}),
                    }
            yield {"event": "done", "data": "{}"}
        except Exception as e:
            logger.exception("Stream failed")
            yield {
                "event": "error",
                "data": json.dumps({"code": "llm_error", "message": str(e)}),
            }

    return EventSourceResponse(event_generator())


@router.get("/agents")
async def list_agents(fmt: str = Query("toon", alias="format")):
    """Return agent catalog for discovery.

    Default: TOON format (LLM-friendly, fewer tokens).
    ?format=json for standard JSON.
    """
    metadata = get_agents_metadata()
    if fmt == "json":
        return JSONResponse(content=metadata)
    return Response(content=toon_encode(metadata), media_type="text/toon")
