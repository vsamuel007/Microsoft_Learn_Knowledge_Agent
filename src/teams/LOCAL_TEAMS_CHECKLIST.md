# Local Teams Integration Checklist

Use this checklist to validate the end-to-end Teams flow against the MCP-based Foundry agents.

## Prerequisites

- Python virtual environment created and activated.
- All dependencies installed from repository `requirements.txt`.
- Foundry agents already registered:
  - `MicrosoftLearnSearchAgent`
  - `SkillGapAgent`
  - `LearningPathAgent`
- `SKILL_GAP_MCP_SERVER_URL` and `LEARNING_PATH_MCP_SERVER_URL` are live and reachable.

## 1. Configure Environment

1. Copy `src/teams/.env.example` values into your active environment source (`src/agents/.env` in this repo).
2. Set at minimum:
   - `PROJECT_ENDPOINT`
   - `MicrosoftAppId`
   - `MicrosoftAppPassword`
3. Optional overrides:
   - `DEFAULT_SKILL_GAP_USER_ID`
   - `LEARNING_PATH_AGENT_NAME`
   - `SEARCH_AGENT_NAME`
   - `SKILL_GAP_AGENT_NAME`

## 2. Run Foundry Smoke Test

From repo root:

```powershell
python src/teams/smoke_test_foundry.py --user-id user-123 --target-role "Azure Administrator"
```

Expected:
- Search agent returns JSON payload.
- SkillGap agent returns JSON payload.
- LearningPath agent returns `status: ok` with `learning_path`.

## 3. Start Teams Bot Host

From repo root:

```powershell
python src/teams/app.py
```

Or use one-command demo startup (starts bot host + Cloudflare tunnel):

```powershell
powershell -ExecutionPolicy Bypass -File src/teams/START_DEMO.ps1
```

Expected:
- Server starts on `http://localhost:3978`
- Health endpoint responds:

```powershell
curl http://localhost:3978/healthz
```

Expected response: `ok`

## 4. Validate with Bot Framework Emulator (local)

1. Open Bot Framework Emulator.
2. Connect to bot URL:
   - `http://localhost:3978/api/messages`
3. Use App ID / Password from env.
4. Test messages:
   - `hello`
   - `my skills`
   - `create learning path for Azure Administrator`
   - `I want to learn Azure networking`

Expected:
- Adaptive card greeting for hello.
- Skills profile card for `my skills`.
- Learning path card for create command.
- Resources card for search query.

## 5. Validate from Teams (channel)

When testing from Teams channel:

1. Expose local host with tunnel (e.g., ngrok/cloudflared) to reach `/api/messages`.
2. Update Bot Channel Messaging Endpoint to:
   - `https://<public-host>/api/messages`
3. Keep `src/teams/app.py` running.
4. Send the same test messages from Teams.

Expected:
- Same behavior as Emulator.
- No auth errors in bot host logs.

## Troubleshooting

- `PROJECT_ENDPOINT is not configured`:
  - Set `PROJECT_ENDPOINT` in env source loaded by app.
- Agent returns non-JSON:
  - Re-check system prompts to enforce JSON-only responses.
- Skill profile fallback always uses `user-123`:
  - This is expected when Teams user ID does not match `user-###`.
  - Set `DEFAULT_SKILL_GAP_USER_ID` to desired demo profile.
- Teams channel 401/403:
  - Verify `MicrosoftAppId` and `MicrosoftAppPassword`.
  - Ensure messaging endpoint is `/api/messages`.
