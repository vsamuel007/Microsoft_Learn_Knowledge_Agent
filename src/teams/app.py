"""Teams bot host entrypoint for MCP-based Foundry agent integration."""

import logging
import os
from pathlib import Path
from typing import Any

from aiohttp import web
from botbuilder.core import BotFrameworkAdapter, BotFrameworkAdapterSettings, TurnContext
from botbuilder.schema import Activity
from dotenv import load_dotenv

try:
    # Package import path (preferred when loaded by other modules).
    from .bot import create_bot
except ImportError:
    # Script execution path: python src/teams/app.py
    from bot import create_bot


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Keep env loading consistent with the current agent scripts.
load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / "agents" / ".env", override=False)


def _config_from_env() -> dict[str, str]:
    """Build bot config from environment variables."""
    return {
        "PROJECT_ENDPOINT": os.getenv("PROJECT_ENDPOINT", ""),
        "LEARNING_PATH_AGENT_NAME": os.getenv("LEARNING_PATH_AGENT_NAME", "LearningPathAgent"),
        "SEARCH_AGENT_NAME": os.getenv("SEARCH_AGENT_NAME", "MicrosoftLearnSearchAgent"),
        "SKILL_GAP_AGENT_NAME": os.getenv("SKILL_GAP_AGENT_NAME", "SkillGapAgent"),
    }


def _adapter_settings() -> BotFrameworkAdapterSettings:
    """Use standard Teams bot credentials for Bot Framework channel auth."""
    app_id = os.getenv("MicrosoftAppId", "")
    app_password = os.getenv("MicrosoftAppPassword", "")
    return BotFrameworkAdapterSettings(app_id=app_id, app_password=app_password)


async def _on_error(context: TurnContext, error: Exception):
    logger.exception("Unhandled bot error: %s", error)
    await context.send_activity("The bot encountered an internal error. Please try again.")


def create_app(config: dict[str, str] | None = None) -> web.Application:
    """Create aiohttp application that hosts the Teams bot endpoint."""
    merged_config = _config_from_env()
    if config:
        merged_config.update(config)

    bot = create_bot(merged_config)
    adapter = BotFrameworkAdapter(_adapter_settings())
    adapter.on_turn_error = _on_error

    async def messages(request: web.Request) -> web.StreamResponse:
        if request.content_type != "application/json":
            return web.Response(status=415, text="Content-Type must be application/json")

        body: dict[str, Any] = await request.json()
        auth_header = request.headers.get("Authorization", "")
        activity = Activity().deserialize(body)

        invoke_response = await adapter.process_activity(activity, auth_header, bot.on_turn)
        if invoke_response:
            return web.json_response(data=invoke_response.body, status=invoke_response.status)
        return web.Response(status=201)

    app = web.Application()
    app.router.add_post("/api/messages", messages)
    app.router.add_get("/healthz", lambda _: web.Response(text="ok"))

    return app


def main() -> None:
    port = int(os.getenv("PORT", "3978"))
    app = create_app()
    logger.info("Starting Teams bot host on port %s", port)
    web.run_app(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
