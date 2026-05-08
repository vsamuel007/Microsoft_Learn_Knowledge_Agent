import os
import asyncio
import copy
import json
import sys
from dotenv import load_dotenv
from pathlib import Path
from contextlib import AsyncExitStack
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import FunctionTool
from azure.identity import DefaultAzureCredential
from azure.ai.projects.models import PromptAgentDefinition
from openai.types.responses.response_input_param import FunctionCallOutput, ResponseInputParam

# Add references
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


# Clear the console
os.system('cls' if os.name=='nt' else 'clear')

# Load environment variables from parent agents/.env file
env_file = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_file)
project_endpoint = os.getenv("PROJECT_ENDPOINT")
model_deployment = os.getenv("MODEL_DEPLOYMENT_NAME")


def load_skill_gap_agent_instructions() -> str:
    """Load the system prompt text from SkillGap.agent.md."""
    default_instructions = (
        "You are a Skill Gap Analysis Agent. Use available tools to retrieve profile and requirements, "
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


def _extract_tool_schema(tool) -> dict:
    def _normalize_object_schemas(schema_fragment):
        if isinstance(schema_fragment, dict):
            if schema_fragment.get("type") == "object":
                schema_fragment.setdefault("properties", {})
                # OpenAI function parameters require explicit additionalProperties=false.
                schema_fragment["additionalProperties"] = False
                # OpenAI strict mode expects required to include every key in properties.
                schema_fragment["required"] = list(schema_fragment["properties"].keys())

            for key in ("properties", "patternProperties", "$defs", "definitions"):
                nested = schema_fragment.get(key)
                if isinstance(nested, dict):
                    for value in nested.values():
                        _normalize_object_schemas(value)

            if "items" in schema_fragment:
                _normalize_object_schemas(schema_fragment["items"])

            for key in ("oneOf", "anyOf", "allOf"):
                variants = schema_fragment.get(key)
                if isinstance(variants, list):
                    for variant in variants:
                        _normalize_object_schemas(variant)

        elif isinstance(schema_fragment, list):
            for item in schema_fragment:
                _normalize_object_schemas(item)

    schema = (
        getattr(tool, "inputSchema", None)
        or getattr(tool, "input_schema", None)
        or getattr(tool, "parameters", None)
    )

    if isinstance(schema, dict) and schema.get("type") == "object":
        normalized_schema = copy.deepcopy(schema)
        _normalize_object_schemas(normalized_schema)
        return normalized_schema

    return {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    }


def _tool_result_to_text(result) -> str:
    content = getattr(result, "content", None)
    if not content:
        if hasattr(result, "model_dump"):
            return json.dumps(result.model_dump())
        return json.dumps({"status": "ok"})

    text_chunks = []
    for chunk in content:
        text = getattr(chunk, "text", None)
        if text is not None:
            text_chunks.append(text)

    if text_chunks:
        return "\n".join(text_chunks)

    if hasattr(result, "model_dump"):
        return json.dumps(result.model_dump())
    return str(result)


async def connect_to_server(exit_stack: AsyncExitStack):
    server_script = Path(__file__).with_name("server.py")
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[str(server_script)],
        env=None
    )

    # Start the MCP server
    stdio_transport = await exit_stack.enter_async_context(stdio_client(server_params))
    stdio, write = stdio_transport


    # Create an MCP client session
    session = await exit_stack.enter_async_context(ClientSession(stdio, write))
    await session.initialize()
    

    # List available tools
    response = await session.list_tools()
    tools = response.tools
    print("\nConnected to server with tools:", [tool.name for tool in tools])
   

    return session


async def run_tool_calls(openai_client, agent_name: str, response, functions_dict: dict):
    """Execute model-requested function calls until the model returns text only."""
    max_tool_rounds = 8
    tool_round = 0

    while True:
        tool_round += 1
        if tool_round > max_tool_rounds:
            print("Reached maximum tool-call rounds; returning latest model response.")
            return response

        tool_call_outputs: ResponseInputParam = []
        function_calls = [item for item in response.output if item.type == "function_call"]

        if not function_calls:
            return response

        print(f"Processing tool round {tool_round} with {len(function_calls)} function call(s)...")

        for item in function_calls:
            function_name = item.name
            required_function = functions_dict.get(function_name)
            print(f"  Calling tool: {function_name}")

            try:
                kwargs = json.loads(item.arguments) if item.arguments else {}
            except json.JSONDecodeError:
                kwargs = {}

            if required_function is None:
                output_text = json.dumps({"status": "error", "error": f"Unknown function '{function_name}'"})
            else:
                try:
                    output = await required_function(**kwargs)
                    output_text = _tool_result_to_text(output)
                    print(f"  Tool completed: {function_name}")
                except Exception as ex:  # pylint: disable=broad-except
                    output_text = json.dumps({"status": "error", "error": f"Tool execution failed: {str(ex)}"})
                    print(f"  Tool failed: {function_name}")

            tool_call_outputs.append(
                FunctionCallOutput(
                    type="function_call_output",
                    call_id=item.call_id,
                    output=output_text,
                )
            )

        response = openai_client.responses.create(
            input=tool_call_outputs,
            previous_response_id=response.id,
            extra_body={"agent_reference": {"name": agent_name, "type": "agent_reference"}},
        )


async def chat_loop(session):

    # Connect to the agents client
    with (
        DefaultAzureCredential() as credential,
        AIProjectClient(endpoint=project_endpoint, credential=credential) as project_client,
        project_client.get_openai_client() as openai_client,
    ):

        # Get the MCP tools available from the local server
        response = await session.list_tools()
        tools = response.tools

        # Build a callable wrapper for each MCP tool.
        def make_tool_func(tool_name):
            async def tool_func(**kwargs):
                result = await session.call_tool(tool_name, kwargs)
                return result
                
            tool_func.__name__ = tool_name
            return tool_func

        # Store the functions in a dictionary for easy access when processing function calls
        functions_dict = {tool.name: make_tool_func(tool.name) for tool in tools}


        # Create FunctionTool definitions for the agent.
        mcp_function_tools = []
        for tool in tools:
            function_tool = FunctionTool(
                name=tool.name,
                description=tool.description,
                parameters=_extract_tool_schema(tool),
                strict=True
            )
            mcp_function_tools.append(function_tool)
        
        agent_instructions = load_skill_gap_agent_instructions()

        # Create the agent
        agent = project_client.agents.create_version(
            agent_name="SkillGapAgentLocalMock",
            definition=PromptAgentDefinition(
                model=model_deployment,
                instructions=agent_instructions,
                tools=mcp_function_tools
            ),
        )


        # Create a thread for the chat session
        conversation = openai_client.conversations.create()

        while True:
            user_input = input("Enter a prompt for the skill-gap agent. Use 'quit' to exit.\nUSER: ").strip()
            if user_input.lower() == "quit":
                print("Exiting chat.")
                break

            # Send a prompt to the agent
            openai_client.conversations.items.create(
                conversation_id=conversation.id,
                items=[{"type": "message", "role": "user", "content": user_input}],
            )

            # Retrieve the agent's response, which may include function calls to the MCP server tools
            print("Running agent response...")
            response = openai_client.responses.create(
                conversation=conversation.id,
                extra_body={"agent_reference": {"name": agent.name, "type": "agent_reference"}},
            )

            # Check the run status for failures
            if response.status == "failed":
                print(f"Response failed: {response.error}")

            response = await run_tool_calls(openai_client, agent.name, response, functions_dict)
            print(f"Agent response: {response.output_text}")
           
           
        # Delete the agent when done
        print("Cleaning up agents:")
        project_client.agents.delete_version(agent_name=agent.name, agent_version=agent.version)
        print("Deleted local mock skill-gap agent.")


async def main():
    import sys
    exit_stack = AsyncExitStack()
    try:
        session = await connect_to_server(exit_stack)
        await chat_loop(session)
    finally:
        await exit_stack.aclose()

if __name__ == "__main__":
    asyncio.run(main())