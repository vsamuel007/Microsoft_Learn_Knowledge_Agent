import os
from pathlib import Path

from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition, MCPTool


def load_skill_gap_agent_instructions() -> str:
    """Load the system prompt text from SkillGap.agent.md."""
    default_instructions = (
        "You are a Skill Gap Analysis Agent. Use tools to get user profile and role requirements, "
        "assess gaps, and return valid JSON."
    )

    prompt_file = Path(__file__).with_name("SkillGap.agent.md")
    if not prompt_file.exists():
        return default_instructions

    content = prompt_file.read_text(encoding="utf-8")
    marker = "## System Prompt"
    marker_idx = content.find(marker)
    if marker_idx == -1:
        return default_instructions

    start = marker_idx + len(marker)
    remaining = content[start:].lstrip()
    next_section_idx = remaining.find("\n## ")
    prompt = remaining[:next_section_idx].strip() if next_section_idx != -1 else remaining.strip()

    return prompt or default_instructions


def main() -> None:
    # Load environment variables from parent agents/.env file.
    env_file = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(dotenv_path=env_file)

    project_endpoint = os.getenv("PROJECT_ENDPOINT")
    model_deployment = os.getenv("MODEL_DEPLOYMENT_NAME")
    skill_gap_mcp_server_url = os.getenv("SKILL_GAP_MCP_SERVER_URL")

    if not project_endpoint:
        raise ValueError("PROJECT_ENDPOINT is required in src/agents/.env")
    if not model_deployment:
        raise ValueError("MODEL_DEPLOYMENT_NAME is required in src/agents/.env")
    if not skill_gap_mcp_server_url:
        raise ValueError(
            "SKILL_GAP_MCP_SERVER_URL is required for portal demo. "
            "Set it to a reachable MCP server URL (HTTP/SSE/streamable endpoint)."
        )

    agent_instructions = load_skill_gap_agent_instructions()

    with (
        DefaultAzureCredential() as credential,
        AIProjectClient(endpoint=project_endpoint, credential=credential) as project_client,
    ):
        mcp_tool = MCPTool(
            server_label="skill-gap-tools",
            server_url=skill_gap_mcp_server_url,
            require_approval="always",
        )

        agent = project_client.agents.create_version(
            agent_name="SkillGapAgent",
            definition=PromptAgentDefinition(
                model=model_deployment,
                instructions=agent_instructions,
                tools=[mcp_tool],
            ),
        )

        print(f"Portal-ready agent created (id: {agent.id}, name: {agent.name}, version: {agent.version})")
        print(f"Tool endpoint configured: {skill_gap_mcp_server_url}")


if __name__ == "__main__":
    main()
