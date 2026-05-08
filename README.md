# Microsoft Learn Knowledge Agent

This repository now centers on three MCP-based Azure AI Foundry agents:

- `MicrosoftLearnSearchAgent` for Microsoft Learn content discovery
- `SkillGapAgent` for mock user profile and skill gap analysis
- `LearningPathAgent` for phased learning path synthesis

The current working architecture is agent-first. The next implementation step is Microsoft Teams integration so a Teams user query can flow into `LearningPathAgent` as the orchestrator.

---

## Current Status

Implemented now:

- Search agent registration against the Microsoft Learn hosted MCP endpoint
- Skill Gap MCP server and SkillGap agent registration
- LearningPath MCP server and LearningPath agent registration
- Local portal demo helpers for SkillGap and LearningPath

Still to implement:

- Microsoft Teams integration
- Wiring a Teams message flow into `LearningPathAgent`
- Returning LearningPath results back to Teams as a user-facing response

Target runtime flow:

```text
User Query (Teams)
        ↓
LearningPathAgent (Orchestrator)
        ↓
    ┌───────┴───────┐
    ↓               ↓
Search tools     Skill Gap tools
(MS Learn MCP)   (SkillGap MCP)
    ↓               ↓
    └───────┬───────┘
            ↓
LearningPath synthesis tools
            ↓
Personalized Learning Path
```

---

## Project Structure

```text
src/
├── agents/
│   ├── search/
│   │   ├── agent.py
│   │   ├── Search.agent.md
│   │   └── requirements.txt
│   ├── skill/
│   │   ├── agent.py
│   │   ├── server.py
│   │   ├── SkillGap.agent.md
│   │   ├── START_DEMO.ps1
│   │   ├── print_mcp_url.py
│   │   └── PORTAL_DEMO_GUIDE.md
│   └── learningpath/
│       ├── agent.py
│       ├── server.py
│       ├── LearningPath.agent.md
│       ├── START_DEMO.ps1
│       ├── print_mcp_url.py
│       └── PORTAL_DEMO_GUIDE.md
└── teams/
    ├── bot.py
    ├── adaptive_cards.py
    ├── voice_handler.py
    └── __init__.py
```

Notes:

- `src/agents/search` registers the Search agent directly against `https://learn.microsoft.com/api/mcp`.
- `src/agents/skill/server.py` exposes the Skill Gap MCP tools used by `SkillGapAgent`.
- `src/agents/learningpath/server.py` exposes synthesis tools used by `LearningPathAgent`.
- `src/teams` remains for the upcoming Teams integration pass.

---

## Agent Overview

### Search Agent

Purpose:

- Search Microsoft Learn content
- Restrict responses to Microsoft and Microsoft Learn topics

Implementation:

- Agent registration: `src/agents/search/agent.py`
- Prompt/spec: `src/agents/search/Search.agent.md`
- MCP endpoint: `https://learn.microsoft.com/api/mcp`

### SkillGap Agent

Purpose:

- Return mock user profile data
- Return target role or certification requirements
- Compute prioritized skill gaps
- Generate and evaluate mock assessments

Implementation:

- MCP server: `src/agents/skill/server.py`
- Agent registration: `src/agents/skill/agent.py`
- Prompt/spec: `src/agents/skill/SkillGap.agent.md`

### LearningPath Agent

Purpose:

- Orchestrate Search tools and Skill Gap tools
- Synthesize both inputs into a phased learning path
- Prioritize high-value learning items first
- Estimate effort and sequencing

Implementation:

- MCP server: `src/agents/learningpath/server.py`
- Agent registration: `src/agents/learningpath/agent.py`
- Prompt/spec: `src/agents/learningpath/LearningPath.agent.md`

---

## Environment Setup

The current agent scripts read environment variables from:

- `src/agents/.env`

Expected values:

```env
PROJECT_ENDPOINT=https://your-foundry-project-endpoint
MODEL_DEPLOYMENT_NAME=your-model-deployment

SKILL_GAP_MCP_SERVER_URL=https://your-skillgap-tunnel.trycloudflare.com/mcp
LEARNING_PATH_MCP_SERVER_URL=https://your-learningpath-tunnel.trycloudflare.com/mcp

# Teams bot runtime (Bot Framework channel auth)
MicrosoftAppId=your-bot-app-id
MicrosoftAppPassword=your-bot-app-password

# Optional Teams defaults/overrides
DEFAULT_SKILL_GAP_USER_ID=user-123
LEARNING_PATH_AGENT_NAME=LearningPathAgent
SEARCH_AGENT_NAME=MicrosoftLearnSearchAgent
SKILL_GAP_AGENT_NAME=SkillGapAgent
```

Notes:

- `PROJECT_ENDPOINT` and `MODEL_DEPLOYMENT_NAME` are used by all three agent registration scripts.
- `SKILL_GAP_MCP_SERVER_URL` is used by both `SkillGapAgent` and `LearningPathAgent`.
- `LEARNING_PATH_MCP_SERVER_URL` is used by `LearningPathAgent`.
- The Search agent does not require a Search MCP env var because it uses the Microsoft Learn hosted MCP endpoint directly.
- `MicrosoftAppId` and `MicrosoftAppPassword` are required when running the Teams endpoint against the Bot Framework channel.
- `DEFAULT_SKILL_GAP_USER_ID` is used when the Teams user ID does not match the mock user pattern (`user-123`, etc.).

---

## Portal Demos

For local MCP server plus tunnel plus Foundry playground testing:

- SkillGap demo guide: [src/agents/skill/PORTAL_DEMO_GUIDE.md](/c:/Projects/MSLearn/Microsoft_Learn_Knowledge_Agent/src/agents/skill/PORTAL_DEMO_GUIDE.md)
- LearningPath demo guide: [src/agents/learningpath/PORTAL_DEMO_GUIDE.md](/c:/Projects/MSLearn/Microsoft_Learn_Knowledge_Agent/src/agents/learningpath/PORTAL_DEMO_GUIDE.md)

Convenience helpers:

- SkillGap startup script: [src/agents/skill/START_DEMO.ps1](/c:/Projects/MSLearn/Microsoft_Learn_Knowledge_Agent/src/agents/skill/START_DEMO.ps1)
- LearningPath startup script: [src/agents/learningpath/START_DEMO.ps1](/c:/Projects/MSLearn/Microsoft_Learn_Knowledge_Agent/src/agents/learningpath/START_DEMO.ps1)
- SkillGap MCP URL helper: [src/agents/skill/print_mcp_url.py](/c:/Projects/MSLearn/Microsoft_Learn_Knowledge_Agent/src/agents/skill/print_mcp_url.py)
- LearningPath MCP URL helper: [src/agents/learningpath/print_mcp_url.py](/c:/Projects/MSLearn/Microsoft_Learn_Knowledge_Agent/src/agents/learningpath/print_mcp_url.py)

Typical flow:

1. Start the local MCP server with the agent's `START_DEMO.ps1` script.
2. Copy the public Cloudflare tunnel URL and update `src/agents/.env`.
3. Re-run the corresponding `agent.py` to register a fresh Foundry agent version.
4. Open the Foundry playground and approve MCP tool calls during the test run.

---

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

If needed, install the agent server packages first to avoid dependency resolution conflicts:

```bash
pip install azure-ai-agentserver-agentframework==1.0.0b16 \
            azure-ai-agentserver-core==1.0.0b16 \
            agent-dev-cli==0.0.1b260316
```

---

## Teams Integration Next

Teams wiring is now updated for the MCP-based architecture.

Implemented in `src/teams`:

- `bot.py`: direct Foundry invocation of `LearningPathAgent`, `MicrosoftLearnSearchAgent`, and `SkillGapAgent`
- `app.py`: aiohttp host entrypoint with `/api/messages` and `/healthz`
- `smoke_test_foundry.py`: direct invocation smoke test for all three agents
- `adaptive_cards.py`: card rendering aligned to new JSON payload shapes

Reference files:

- Teams env template: [src/teams/.env.example](/c:/Projects/MSLearn/Microsoft_Learn_Knowledge_Agent/src/teams/.env.example)
- Local validation checklist: [src/teams/LOCAL_TEAMS_CHECKLIST.md](/c:/Projects/MSLearn/Microsoft_Learn_Knowledge_Agent/src/teams/LOCAL_TEAMS_CHECKLIST.md)

### Run Foundry Smoke Test

```bash
python src/teams/smoke_test_foundry.py --user-id user-123 --target-role "Azure Administrator"
```

### Run Teams Bot Host

```bash
python src/teams/app.py
```

This starts:

- `POST /api/messages` for Teams bot traffic
- `GET /healthz` for readiness check

### Expected Runtime Flow

1. Teams receives user query.
2. Teams bot forwards intent to `LearningPathAgent`.
3. `LearningPathAgent` orchestrates Search tools, Skill Gap tools, and LearningPath synthesis tools.
4. Teams returns card-based response to user.

---

## Notes

- The legacy `src/tools`, `src/scripts`, `src/orchestrator`, and `src/config` folders have been removed.
- Agent markdown files remain the source of truth for prompt behavior.
- The current repository state is optimized for MCP-based Foundry agent creation and portal validation.