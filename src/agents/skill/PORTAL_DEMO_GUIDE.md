# SkillGap Agent Portal Demo - Quick Reference

## Quick Start (Automated)
Run from the skill folder:
```powershell
cd C:\Projects\MSLearn\Microsoft_Learn_Knowledge_Agent\src\agents\skill
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
cd src\agents\skill
python server.py --transport streamable-http --host 127.0.0.1 --port 8001 --public
```
Wait for: `INFO: Uvicorn running on http://127.0.0.1:8001`

### Terminal 2: Cloudflare Tunnel
From any location:
```powershell
& "$env:TEMP\cloudflared.exe" tunnel --url http://127.0.0.1:8001 --no-autoupdate
```
Wait for output showing: `Your quick Tunnel has been created! Visit it at: https://XXXX.trycloudflare.com`
Copy this URL.

### Terminal 3: Register Portal Agent
From project root:
```powershell
cd C:\Projects\MSLearn\Microsoft_Learn_Knowledge_Agent
.\.venv\Scripts\Activate.ps1

# Edit src/agents/.env and set:
# SKILL_GAP_MCP_SERVER_URL=https://XXXX.trycloudflare.com/mcp

python src/agents/skill/agent.py
```
Wait for: `Portal-ready agent created (id: SkillGapAgent:N, ...`

---

## Test in Foundry Portal

1. Open Foundry portal
2. Navigate to SkillGapAgent → Playground (latest version)
3. Paste this query:
   ```
   Analyze skill gaps for user-123 for Azure Administrator and provide assessment items plus evaluation plan.
   ```
4. Click Run
5. Approve MCP tool calls when prompted
6. View results

---

## Key Components

| Component | Port | Transport | Endpoint |
|-----------|------|-----------|----------|
| Local MCP Server | 8001 | streamable-http | http://127.0.0.1:8001/mcp |
| Cloudflare Tunnel | (remote) | HTTPS | https://XXX.trycloudflare.com/mcp |
| Foundry Agent | (cloud) | - | Uses tunnel URL |

---

## Troubleshooting

**Port 8001 already in use:**
```powershell
netstat -ano | findstr :8001
Stop-Process -Id <PID> -Force
```

**Tunnel connection fails:**
- Check that local server is running first
- Restart cloudflared tunnel
- Verify tunnel URL shows in the tunnel window

**Portal tool enumeration fails:**
- Ensure env file has the correct tunnel URL ending in `/mcp`
- Re-run `python src/agents/skill/agent.py` (from project root)
- Check that cloudflare tunnel is still active (should see no ERR messages)

**Portal cannot reach server:**
- Confirm local server is listening: `netstat -ano | findstr :8001`
- Confirm tunnel is active and shows no errors
- Restart both and re-register agent

---

## Local Testing (Terminal Only, No Portal)

If you just want to test the 5-tool pipeline locally without portal:
```powershell
cd C:\Projects\MSLearn\Microsoft_Learn_Knowledge_Agent\src\agents\skill
python client.py
```
This uses stdio MCP (no tunnel needed) and tests user-123 → Azure Administrator flow locally.

---

## Files to Remember

- **Startup script:** `src/agents/skill/START_DEMO.ps1`
- **Config:** `src/agents/.env` (update tunnel URL each time)
- **Local server:** `src/agents/skill/server.py`
- **Portal agent:** `src/agents/skill/agent.py`
- **Local client:** `src/agents/skill/client.py`
- **This guide:** `src/agents/skill/PORTAL_DEMO_GUIDE.md`
