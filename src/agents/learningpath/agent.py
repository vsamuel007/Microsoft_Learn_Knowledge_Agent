import os
from pathlib import Path

from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition, MCPTool


def load_learning_path_agent_instructions() -> str:
    """Load the system prompt text from LearningPath.agent.md."""
    default_instructions = (
        "You are a Learning Path Designer Agent. "
        "Orchestrate tool calls to gather skill_gaps from SkillGap MCP tools and "
        "resources from Microsoft Learn MCP tools. "
        "Validate both inputs are non-empty, then invoke learning path synthesis tools "
        "to produce a structured, sequential plan. "
        "Prioritize highest skill gaps first, include only Microsoft Learn content, "
        "and return valid JSON with at most 6 phases."
    )

    prompt_file = Path(__file__).with_name("LearningPath.agent.md")
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
    learning_path_mcp_server_url = os.getenv("LEARNING_PATH_MCP_SERVER_URL")

    if not project_endpoint:
        raise ValueError("PROJECT_ENDPOINT is required in src/agents/.env")
    if not model_deployment:
        raise ValueError("MODEL_DEPLOYMENT_NAME is required in src/agents/.env")
    if not skill_gap_mcp_server_url:
        raise ValueError(
            "SKILL_GAP_MCP_SERVER_URL is required. "
            "Set it to the reachable endpoint of the SkillGap MCP server (e.g. your Cloudflare tunnel + /mcp)."
        )
    if not learning_path_mcp_server_url:
        raise ValueError(
            "LEARNING_PATH_MCP_SERVER_URL is required. "
            "Set it to the reachable endpoint of the LearningPath MCP server (server.py in this folder)."
        )

    agent_instructions = load_learning_path_agent_instructions()

    with (
        DefaultAzureCredential() as credential,
        AIProjectClient(endpoint=project_endpoint, credential=credential) as project_client,
    ):
        # Tool 1 - Search tools (MS Learn MCP)
        mslearn_tool = MCPTool(
            server_label="search-tools",
            server_url="https://learn.microsoft.com/api/mcp",
            require_approval="always",
        )

        # Tool 2 - Skill Gap tools (SkillGap MCP)
        skill_gap_tool = MCPTool(
            server_label="skill-gap-tools",
            server_url=skill_gap_mcp_server_url,
            require_approval="always",
        )

        # Tool 3 - LearningPath synthesis tools
        learning_path_tool = MCPTool(
            server_label="learning-path-tools",
            server_url=learning_path_mcp_server_url,
            require_approval="always",
        )

        agent = project_client.agents.create_version(
            agent_name="LearningPathAgent",
            definition=PromptAgentDefinition(
                model=model_deployment,
                instructions=agent_instructions,
                tools=[mslearn_tool, skill_gap_tool, learning_path_tool],
            ),
        )

        print(f"LearningPath agent created (id: {agent.id}, name: {agent.name}, version: {agent.version})")
        print("MCP tools configured:")
        print(f"  search-tools         → https://learn.microsoft.com/api/mcp")
        print(f"  skill-gap-tools      → {skill_gap_mcp_server_url}")
        print(f"  learning-path-tools  → {learning_path_mcp_server_url}")


if __name__ == "__main__":
    main()
