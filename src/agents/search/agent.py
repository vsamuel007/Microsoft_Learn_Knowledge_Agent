import os
from pathlib import Path
from dotenv import load_dotenv

# Add references
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition, MCPTool
from openai.types.responses.response_input_param import McpApprovalResponse, ResponseInputParam


# Load environment variables from .env file
env_file = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_file)
project_endpoint = os.getenv("PROJECT_ENDPOINT")
model_deployment = os.getenv("MODEL_DEPLOYMENT_NAME")


def load_search_agent_instructions() -> str:
    """Load the system prompt text from Search.agent.md."""
    default_instructions = (
        "You are MicrosoftLearnSearchAgent. Help only with Microsoft and Microsoft Learn topics. "
        "For non-Microsoft topics, refuse politely and redirect to Microsoft alternatives."
    )

    prompt_file = Path(__file__).with_name("Search.agent.md")
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
    if next_section_idx != -1:
        prompt = remaining[:next_section_idx].strip()
    else:
        prompt = remaining.strip()

    return prompt or default_instructions


agent_instructions = load_search_agent_instructions()

# Connect to the agents client
with (
    DefaultAzureCredential() as credential,
    AIProjectClient(endpoint=project_endpoint, credential=credential) as project_client,
    project_client.get_openai_client() as openai_client,
):


    # Initialize agent MCP tool
    mcp_tool = MCPTool(
        server_label="api-specs",
        server_url="https://learn.microsoft.com/api/mcp",
        require_approval="always",
    )

    # Create a new agent with the MCP tool
    agent = project_client.agents.create_version(
        agent_name="MicrosoftLearnSearchAgent",
        definition=PromptAgentDefinition(
            model=model_deployment,
            instructions=agent_instructions,
            tools=[mcp_tool],
        ),
    )
    print(f"Agent created (id: {agent.id}, name: {agent.name}, version: {agent.version})")
    

    # Create a conversation thread
    conversation = openai_client.conversations.create()
    print(f"Created conversation (id: {conversation.id})")
    

    # Send initial request that will trigger the MCP tool
    response = openai_client.responses.create(
        conversation=conversation.id,
        input="Give me the Azure CLI commands to create an Azure Container App with a managed identity.",
        extra_body={"agent_reference": {"name": agent.name, "type": "agent_reference"}},
    )
    

    # Process any MCP approval requests that were generated
    input_list: ResponseInputParam = []
    for item in response.output:
        if item.type == "mcp_approval_request":
            if item.server_label == "api-specs" and item.id:
                # Automatically approve the MCP request to allow the agent to proceed
                input_list.append(
                    McpApprovalResponse(
                        type="mcp_approval_response",
                        approve=True,
                        approval_request_id=item.id,
                    )
                )

    print("Final input:")
    print(input_list)


    # Send the approval response back and retrieve a response
    response = openai_client.responses.create(
        input=input_list,
        previous_response_id=response.id,
        extra_body={"agent_reference": {"name": agent.name, "type": "agent_reference"}},
    )

    print(f"\nAgent response: {response.output_text}")
    
    
    # Clean up resources by deleting the agent version
    #project_client.agents.delete_version(agent_name=agent.name, agent_version=agent.version)
    #print("Agent deleted")
    