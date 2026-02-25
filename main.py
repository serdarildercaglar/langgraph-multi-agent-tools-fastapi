"""Application entry point."""

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI

from src.api.router import router
from src.config.settings import settings

app = FastAPI(
    title="LangGraph Agent API",
    version="0.1.0",
)

app.include_router(router)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.app_port,
        reload=settings.app_env == "development",
    )
