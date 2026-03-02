"""Layer 1: Langfuse prompt management tests."""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.middleware.prompt import langfuse_prompt, warm_prompt_cache


class TestLangfusePromptMiddleware:
    """Test the @wrap_model_call langfuse_prompt middleware."""

    async def test_fallback_on_unreachable(self, caplog):
        """When Langfuse is unreachable, fallback prompt is used and WARNING logged."""
        mock_client = MagicMock()
        mock_prompt = MagicMock()
        mock_prompt.is_fallback = True
        mock_prompt.compile.return_value = "fallback system prompt"
        mock_client.get_prompt.return_value = mock_prompt

        mock_request = MagicMock()
        mock_request.system_message.content = "fallback system prompt"
        mock_handler = AsyncMock(return_value="handler_result")

        mock_config = {"metadata": {"lc_agent_name": "test_agent"}}

        with (
            patch("src.middleware.prompt._get_langfuse_client", return_value=mock_client),
            patch("src.middleware.prompt.get_config", return_value=mock_config),
            caplog.at_level(logging.WARNING, logger="src.middleware.prompt"),
        ):
            result = await langfuse_prompt.awrap_model_call(mock_request, mock_handler)

        assert "fallback" in caplog.text.lower()
        mock_handler.assert_called_once()

    async def test_skip_without_agent_name(self, caplog):
        """When lc_agent_name is missing from config, middleware skips."""
        mock_request = MagicMock()
        mock_handler = AsyncMock(return_value="handler_result")

        with (
            patch("src.middleware.prompt.get_config", return_value={"metadata": {}}),
            caplog.at_level(logging.DEBUG, logger="src.middleware.prompt"),
        ):
            result = await langfuse_prompt.awrap_model_call(mock_request, mock_handler)

        mock_handler.assert_called_once_with(mock_request)


class TestWarmPromptCache:
    """Test warm_prompt_cache function."""

    def test_warm_cache_logs_success(self, caplog):
        mock_client = MagicMock()

        mock_agent = MagicMock()
        mock_agent.name = "test_agent"
        agents = {"test": {"agent": mock_agent, "description": "Test"}}

        with (
            patch("src.middleware.prompt._get_langfuse_client", return_value=mock_client),
            caplog.at_level(logging.INFO, logger="src.middleware.prompt"),
        ):
            warm_prompt_cache(agents)

        assert "test_agent" in caplog.text
        mock_client.get_prompt.assert_called_once()

    def test_warm_cache_handles_failure(self, caplog):
        """warm_prompt_cache does not raise on Langfuse failure."""
        mock_client = MagicMock()
        mock_client.get_prompt.side_effect = ConnectionError("Langfuse down")

        mock_agent = MagicMock()
        mock_agent.name = "failing_agent"
        agents = {"fail": {"agent": mock_agent, "description": "Fail"}}

        with (
            patch("src.middleware.prompt._get_langfuse_client", return_value=mock_client),
            caplog.at_level(logging.WARNING, logger="src.middleware.prompt"),
        ):
            # Should not raise
            warm_prompt_cache(agents)

        assert "failing_agent" in caplog.text
