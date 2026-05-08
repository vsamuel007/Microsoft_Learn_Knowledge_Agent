# LearningPath Agent Portal Demo - Quick Reference

## Quick Start (Automated)
Run from the learningpath folder:
```powershell
cd C:\Projects\MSLearn\Microsoft_Learn_Knowledge_Agent\src\agents\learningpath
.\START_DEMO.ps1
```
This opens two windows automatically. Then follow the "Manual Steps" section below.

---

## Manual Steps (if you prefer to do it step-by-step)

### Terminal 1: Local MCP Server
From project root:
```powershell
cd C:\Projects\MSLearn\Microsoft_Learn_Knowledge_Agent
.\.venv\Scripts\Activate.ps1
cd src\agents\learningpath
python server.py --transport streamable-http --host 127.0.0.1 --port 8002 --public
```
Wait for the server startup output showing it is listening on `http://127.0.0.1:8002`.

### Terminal 2: Cloudflare Tunnel
From any location:
```powershell
& "$env:TEMP\cloudflared.exe" tunnel --url http://127.0.0.1:8002 --no-autoupdate
```
Wait for output showing a public URL such as:
`https://XXXX.trycloudflare.com`
Copy this URL.

### Terminal 3: Register Portal Agent
From project root:
```powershell
cd C:\Projects\MSLearn\Microsoft_Learn_Knowledge_Agent
.\.venv\Scripts\Activate.ps1

# Edit src/agents/.env and set:
# LEARNING_PATH_MCP_SERVER_URL=https://XXXX.trycloudflare.com/mcp

python src/agents/learningpath/agent.py
```
Wait for output showing the new LearningPath agent version was created successfully.

---

## Test in Foundry Portal

1. Open Foundry portal
2. Navigate to LearningPathAgent -> Playground (latest version)
3. Paste a query such as:
   ```
   Create a personalized learning path for user-123 targeting Azure Administrator with a moderate pace and 5 hours per week.
   ```
4. Click Run
5. Approve MCP tool calls when prompted
6. Review the synthesized phases, milestones, and estimated duration

---

## Key Components

| Component | Port | Transport | Endpoint |
|-----------|------|-----------|----------|
| Local MCP Server | 8002 | streamable-http | http://127.0.0.1:8002/mcp |
| Cloudflare Tunnel | (remote) | HTTPS | https://XXX.trycloudflare.com/mcp |
| Foundry Agent | (cloud) | - | Uses tunnel URL |

---

## Example Env Values

```env
SKILL_GAP_MCP_SERVER_URL=https://your-skillgap-tunnel.trycloudflare.com/mcp
LEARNING_PATH_MCP_SERVER_URL=https://your-learningpath-tunnel.trycloudflare.com/mcp
```

Notes:
- `SKILL_GAP_MCP_SERVER_URL` is still required because LearningPathAgent uses Skill Gap tools.
- Microsoft Learn MCP does not need an env var because it is fixed in code as `https://learn.microsoft.com/api/mcp`.

---

## Troubleshooting

**Port 8002 already in use:**
```powershell
netstat -ano | findstr :8002
Stop-Process -Id <PID> -Force
```

**Tunnel connection fails:**
- Check that the local server is running first
- Restart the cloudflared tunnel
- Verify the public URL appears in the tunnel window

**Portal tool enumeration fails:**
- Ensure `src/agents/.env` has the correct `LEARNING_PATH_MCP_SERVER_URL` ending in `/mcp`
- Re-run `python src/agents/learningpath/agent.py`
- Confirm the Cloudflare tunnel is still active and has no errors

**LearningPathAgent fails because Skill Gap tools are unavailable:**
- Ensure `SKILL_GAP_MCP_SERVER_URL` is still valid in `src/agents/.env`
- Restart the SkillGap MCP server and its tunnel if needed
- Re-register the LearningPath agent after updating env values

**Portal cannot reach server:**
- Confirm local server is listening: `netstat -ano | findstr :8002`
- Confirm tunnel is active and shows no errors
- Restart both and re-register the agent

---

## Helper Commands

If you want the exact env value generated for a known public base URL:
```powershell
cd C:\Projects\MSLearn\Microsoft_Learn_Knowledge_Agent\src\agents\learningpath
python print_mcp_url.py --transport streamable-http --public-base-url https://XXXX.trycloudflare.com
```

This prints:
```text
LEARNING_PATH_MCP_SERVER_URL=https://XXXX.trycloudflare.com/mcp
```

---

## Files to Remember

- **Startup script:** `src/agents/learningpath/START_DEMO.ps1`
- **URL helper:** `src/agents/learningpath/print_mcp_url.py`
- **Config:** `src/agents/.env`
- **Local server:** `src/agents/learningpath/server.py`
- **Portal agent:** `src/agents/learningpath/agent.py`
- **Prompt spec:** `src/agents/learningpath/LearningPath.agent.md`
- **This guide:** `src/agents/learningpath/PORTAL_DEMO_GUIDE.md`
