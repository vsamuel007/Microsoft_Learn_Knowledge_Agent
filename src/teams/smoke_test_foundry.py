"""Smoke test utility for direct Foundry agent invocation used by Teams bot."""

import argparse
import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv


SRC_DIR = Path(__file__).resolve().parent.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from teams.bot import FoundryMcpAgentInvoker


load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / "agents" / ".env", override=False)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke test Foundry agents used by Teams integration")
    parser.add_argument("--query", default="I want to learn Azure identity management", help="Search query")
    parser.add_argument("--user-id", default=os.getenv("DEFAULT_SKILL_GAP_USER_ID", "user-123"), help="SkillGap mock user id")
    parser.add_argument("--target-role", default="Azure Administrator", help="Target role for learning path generation")
    parser.add_argument("--project-endpoint", default=os.getenv("PROJECT_ENDPOINT", ""), help="Foundry project endpoint")
    args = parser.parse_args()

    if not args.project_endpoint:
        raise ValueError("PROJECT_ENDPOINT is required (arg or env in src/agents/.env)")

    invoker = FoundryMcpAgentInvoker(args.project_endpoint)

    print("[1/3] Search agent...")
    search_result = await invoker.invoke_json_agent(
        "MicrosoftLearnSearchAgent",
        (
            "Search Microsoft Learn and return JSON only in shape "
            "{status, resources:[{title,url,description,level,duration}]}. "
            f"Query: {args.query}"
        ),
    )
    print(search_result)

    print("\n[2/3] SkillGap agent...")
    skill_result = await invoker.invoke_json_agent(
        "SkillGapAgent",
        f"Get user profile for user_id '{args.user_id}'. Return JSON only.",
    )
    print(skill_result)

    print("\n[3/3] LearningPath agent...")
    learning_result = await invoker.invoke_json_agent(
        "LearningPathAgent",
        (
            "Create a personalized Microsoft Learn learning path and return JSON only. "
            f"Use user_id '{args.user_id}', target_role '{args.target_role}', "
            "learning_pace 'moderate', time_commitment 10."
        ),
    )
    print(learning_result)


if __name__ == "__main__":
    asyncio.run(main())
