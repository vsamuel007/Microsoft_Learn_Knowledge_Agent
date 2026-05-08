"""Microsoft Teams bot for invoking MCP-based Foundry agents directly."""

import asyncio
import json
import logging
import os
import re
from pathlib import Path
from typing import Any

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from botbuilder.core import ActivityHandler, MessageFactory, TurnContext
from botbuilder.schema import Activity, ActivityTypes, ChannelAccount
from dotenv import load_dotenv
from openai.types.responses.response_input_param import McpApprovalResponse

try:
    # Package import path (preferred when loaded as src.teams.bot).
    from .adaptive_cards import AdaptiveCardBuilder
    from .voice_handler import VoiceHandler
except ImportError:
    # Script execution path: python src/teams/app.py or python app.py from src/teams.
    from adaptive_cards import AdaptiveCardBuilder
    from voice_handler import VoiceHandler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / "agents" / ".env", override=False)


class FoundryMcpAgentInvoker:
    """Invoke deployed Foundry agents by name and auto-approve MCP tool calls."""

    def __init__(self, project_endpoint: str):
        self.project_endpoint = project_endpoint

    async def invoke_json_agent(self, agent_name: str, prompt: str) -> dict[str, Any]:
        return await asyncio.to_thread(self._invoke_json_agent_sync, agent_name, prompt)

    def _invoke_json_agent_sync(self, agent_name: str, prompt: str) -> dict[str, Any]:
        if not self.project_endpoint:
            return {"status": "error", "error": "PROJECT_ENDPOINT is not configured"}

        with (
            DefaultAzureCredential() as credential,
            AIProjectClient(endpoint=self.project_endpoint, credential=credential) as project_client,
            project_client.get_openai_client() as openai_client,
        ):
            conversation = openai_client.conversations.create()
            response = openai_client.responses.create(
                conversation=conversation.id,
                input=prompt,
                extra_body=self._agent_reference(agent_name),
            )

            while True:
                approvals = []
                for item in response.output:
                    if getattr(item, "type", None) == "mcp_approval_request" and getattr(item, "id", None):
                        approvals.append(
                            McpApprovalResponse(
                                type="mcp_approval_response",
                                approve=True,
                                approval_request_id=item.id,
                            )
                        )

                if not approvals:
                    break

                response = openai_client.responses.create(
                    input=approvals,
                    previous_response_id=response.id,
                    extra_body=self._agent_reference(agent_name),
                )

            parsed = self._extract_json_payload((response.output_text or "").strip())
            if parsed is None:
                return {
                    "status": "error",
                    "error": f"{agent_name} did not return valid JSON",
                    "raw_text": response.output_text,
                }
            return parsed if isinstance(parsed, dict) else {"status": "ok", "result": parsed}

    @staticmethod
    def _agent_reference(agent_name: str) -> dict[str, Any]:
        return {"agent_reference": {"name": agent_name, "type": "agent_reference"}}

    @staticmethod
    def _extract_json_payload(text: str) -> Any:
        if not text:
            return None

        candidate = text.strip()
        if candidate.startswith("```"):
            candidate = re.sub(r"^```(?:json)?\s*", "", candidate)
            candidate = re.sub(r"\s*```$", "", candidate)

        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

        decoder = json.JSONDecoder()
        for marker in ["{", "["]:
            start = candidate.find(marker)
            if start == -1:
                continue
            try:
                parsed, _ = decoder.raw_decode(candidate[start:])
                return parsed
            except json.JSONDecodeError:
                continue
        return None


class LearningPathBot(ActivityHandler):
    """Teams bot wired directly to Foundry Search, SkillGap, and LearningPath agents."""

    def __init__(
        self,
        project_endpoint: str,
        learning_path_agent_name: str = "LearningPathAgent",
        search_agent_name: str = "MicrosoftLearnSearchAgent",
        skill_gap_agent_name: str = "SkillGapAgent",
    ):
        super().__init__()
        self.agent_invoker = FoundryMcpAgentInvoker(project_endpoint)
        self.learning_path_agent_name = learning_path_agent_name
        self.search_agent_name = search_agent_name
        self.skill_gap_agent_name = skill_gap_agent_name
        self.default_skill_user_id = os.getenv("DEFAULT_SKILL_GAP_USER_ID", "user-123")

        self.card_builder = AdaptiveCardBuilder()
        self.voice_handler = VoiceHandler()
        self.user_sessions: dict[str, dict[str, Any]] = {}

    async def on_message_activity(self, turn_context: TurnContext):
        """Handle incoming text messages from Teams."""
        user_id = turn_context.activity.from_property.id
        user_name = turn_context.activity.from_property.name or "there"
        message_text = (turn_context.activity.text or "").strip()

        logger.info("Received message from %s (%s): %s", user_name, user_id, message_text)

        lowered = message_text.lower()
        if lowered.startswith(("hello", "hi")):
            await self._handle_greeting(turn_context, user_name)
        elif lowered.startswith("create learning path"):
            await self._handle_create_learning_path(turn_context, user_id, message_text)
        elif lowered.startswith("my skills"):
            await self._handle_view_skills(turn_context, user_id)
        elif lowered == "help":
            await self._handle_help(turn_context)
        else:
            await self._handle_learning_query(turn_context, query=message_text)

    async def on_members_added_activity(self, members_added: list[ChannelAccount], turn_context: TurnContext):
        """Handle when bot is added to a conversation."""
        for member in members_added:
            if member.id != turn_context.activity.recipient.id:
                await turn_context.send_activity(
                    MessageFactory.text(
                        "Hello. I'm your Learning Path Assistant. "
                        "I can use the Search, Skill Gap, and LearningPath agents to build personalized Microsoft Learn plans.\n\n"
                        "Type 'help' to see available commands."
                    )
                )

    async def _handle_greeting(self, turn_context: TurnContext, user_name: str):
        greeting_card = self.card_builder.create_welcome_card(user_name)
        await turn_context.send_activity(MessageFactory.attachment(greeting_card))

    async def _handle_create_learning_path(self, turn_context: TurnContext, user_id: str, message_text: str):
        """Handle learning path creation by invoking LearningPathAgent directly."""
        await self._send_typing_indicator(turn_context)

        target_role = self._extract_role_from_message(message_text)
        if not target_role:
            await turn_context.send_activity(
                "Please specify your target role. For example:\n"
                "Create learning path for Azure Administrator"
            )
            return

        skill_user_id = self._resolve_skill_user_id(user_id)
        await turn_context.send_activity(
            f"Analyzing skills and building a learning path for {target_role}. This may take a few moments."
        )

        try:
            learning_path_result = await self.agent_invoker.invoke_json_agent(
                self.learning_path_agent_name,
                self._learning_path_prompt(skill_user_id, target_role),
            )
            if learning_path_result.get("status") != "ok":
                await turn_context.send_activity(
                    f"Unable to create a learning path: {learning_path_result.get('error', 'Unknown error')}"
                )
                return

            skill_profile_result = await self.agent_invoker.invoke_json_agent(
                self.skill_gap_agent_name,
                self._skills_prompt(skill_user_id),
            )
            learning_path_card = self.card_builder.create_learning_path_card(
                learning_path_result,
                skill_profile_result,
            )
            await turn_context.send_activity(MessageFactory.attachment(learning_path_card))

            self.user_sessions[user_id] = {
                "learning_path": learning_path_result.get("learning_path", {}),
                "target_role": target_role,
                "skill_user_id": skill_user_id,
            }
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("Error creating learning path: %s", exc)
            await turn_context.send_activity(
                "An error occurred while creating your learning path. Please try again."
            )

    async def _handle_view_skills(self, turn_context: TurnContext, user_id: str):
        """Show the SkillGapAgent profile instead of a hardcoded local card."""
        await self._send_typing_indicator(turn_context)
        skill_user_id = self._resolve_skill_user_id(user_id)

        try:
            result = await self.agent_invoker.invoke_json_agent(
                self.skill_gap_agent_name,
                self._skills_prompt(skill_user_id),
            )
            if result.get("status") != "ok":
                await turn_context.send_activity(
                    f"Unable to fetch your skills: {result.get('error', 'Unknown error')}"
                )
                return

            skills_card = self.card_builder.create_skills_card(result)
            await turn_context.send_activity(MessageFactory.attachment(skills_card))
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("Error fetching skills: %s", exc)
            await turn_context.send_activity("Unable to fetch your skills at this time.")

    async def _handle_learning_query(self, turn_context: TurnContext, query: str):
        """Handle natural language learning topic queries via MicrosoftLearnSearchAgent."""
        await self._send_typing_indicator(turn_context)
        await turn_context.send_activity(f"Searching for Microsoft Learn resources about: {query}")

        try:
            result = await self.agent_invoker.invoke_json_agent(
                self.search_agent_name,
                self._search_prompt(query),
            )
            resources = self._extract_resources(result)
            if resources:
                resources_card = self.card_builder.create_resources_card(query, resources)
                await turn_context.send_activity(MessageFactory.attachment(resources_card))
            else:
                await turn_context.send_activity(
                    f"No Microsoft Learn resources were found for '{query}'. Try a different search term."
                )
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("Error searching resources: %s", exc)
            await turn_context.send_activity("Unable to search for resources at this time.")

    async def _handle_help(self, turn_context: TurnContext):
        help_card = self.card_builder.create_help_card()
        await turn_context.send_activity(MessageFactory.attachment(help_card))

    async def _send_typing_indicator(self, turn_context: TurnContext):
        typing_activity = Activity(type=ActivityTypes.typing, relates_to=turn_context.activity.relates_to)
        await turn_context.send_activity(typing_activity)

    def _resolve_skill_user_id(self, teams_user_id: str) -> str:
        if re.fullmatch(r"user-\d+", teams_user_id):
            return teams_user_id
        return self.default_skill_user_id

    @staticmethod
    def _extract_role_from_message(message: str) -> str:
        match = re.search(r"for (.+)", message, re.IGNORECASE)
        return match.group(1).strip() if match else ""

    @staticmethod
    def _learning_path_prompt(user_id: str, target_role: str) -> str:
        return (
            "Create a personalized Microsoft Learn learning path. "
            f"Use user_id '{user_id}' and target_role '{target_role}'. "
            "Use learning_pace 'moderate' and time_commitment 10. "
            "Return JSON only."
        )

    @staticmethod
    def _skills_prompt(user_id: str) -> str:
        return (
            "Get the current skill profile for the learner. "
            f"Use user_id '{user_id}'. "
            "Return JSON only in the shape {status, profile}."
        )

    @staticmethod
    def _search_prompt(query: str) -> str:
        return (
            "Search Microsoft Learn for relevant resources. "
            f"Query: '{query}'. "
            "Return JSON only in the shape {status, resources: [...]} where each resource includes "
            "title, url, description, level, and duration when available."
        )

    @staticmethod
    def _extract_resources(result: dict[str, Any]) -> list[dict[str, Any]]:
        resources = result.get("resources")
        if isinstance(resources, list):
            return resources
        data = result.get("result")
        if isinstance(data, dict) and isinstance(data.get("resources"), list):
            return data["resources"]
        return []


def create_bot(config: dict[str, str]) -> LearningPathBot:
    """Factory function to create a Teams bot for direct Foundry agent invocation."""
    project_endpoint = (
        config.get("PROJECT_ENDPOINT")
        or config.get("FOUNDRY_PROJECT_ENDPOINT")
        or config.get("FOUNDRY_ENDPOINT", "")
        or os.getenv("PROJECT_ENDPOINT", "")
    )
    if not project_endpoint:
        logger.warning("Project endpoint is not configured. Set PROJECT_ENDPOINT or FOUNDRY_PROJECT_ENDPOINT.")

    return LearningPathBot(
        project_endpoint=project_endpoint,
        learning_path_agent_name=config.get("LEARNING_PATH_AGENT_NAME", os.getenv("LEARNING_PATH_AGENT_NAME", "LearningPathAgent")),
        search_agent_name=config.get("SEARCH_AGENT_NAME", os.getenv("SEARCH_AGENT_NAME", "MicrosoftLearnSearchAgent")),
        skill_gap_agent_name=config.get("SKILL_GAP_AGENT_NAME", os.getenv("SKILL_GAP_AGENT_NAME", "SkillGapAgent")),
    )
