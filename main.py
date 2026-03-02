"""Application entry point."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.api.router import router
from src.config.settings import settings
from src.memory.checkpointer import init_checkpointer, shutdown_checkpointer
from src.providers import AGENTS, wire_checkpointer

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init async checkpointer → wire to agents → warm prompt cache.
    Shutdown: close DB connection.
    """
    if settings.chat_history_enabled:
        checkpointer = await init_checkpointer()
        wire_checkpointer(checkpointer)
        logger.info("AsyncSqliteSaver initialized and wired to agents")

    if settings.langfuse_prompt_management_enabled:
        from src.middleware.prompt import warm_prompt_cache

        warm_prompt_cache(AGENTS)
        logger.info("Langfuse prompt cache warmed")

    yield

    if settings.chat_history_enabled:
        await shutdown_checkpointer()
        logger.info("AsyncSqliteSaver connection closed")


app = FastAPI(
    title="LangGraph Agent API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

# Serve UI static files
ui_dir = Path(__file__).parent / "UI"
if ui_dir.exists():
    app.mount("/ui", StaticFiles(directory=str(ui_dir), html=True), name="ui")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.app_port,
        reload=settings.app_env == "development",
    )
