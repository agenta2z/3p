---
name: openteam
description: OpenTeam multi-agent workflow tools (agent topologies, role lifecycle, project onboarding)
allowed-tools:
  - mcp__openteam__openteam_task
  - mcp__openteam__openteam_create_role
  - mcp__openteam__openteam_role_setup
  - mcp__openteam__openteam_project_onboarding
---
# OpenTeam Tools — slash vs MCP

Two surfaces for the same four tools:

| Surface | Best for | Timeout |
|---|---|---|
| **Slash** — `/task`, `/create-role`, `/role-setup`, `/project-onboarding` | Direct user invocation; long-running jobs (5-30 min). Streamed live. | **None** — subprocess. |
| **MCP** — `mcp__openteam__openteam_task`, etc. | Programmatic agent orchestration. | **295 s default** (hardcoded in MCPClient). For long jobs re-route to the slash command. |

**Common pitfalls:**
- For `openteam_task`, the four mutually-exclusive flags are collapsed into a single `mode` enum at the MCP surface (default `"full"`). The slash CLI still accepts the four flags individually.
- Long topology runs WILL hit the 295 s MCP timeout. Re-route to the slash command.
- Default `OPENTEAM_HOME` is `~/MyProjects/CoreProjects/OpenTeam`; override if your checkout lives elsewhere.

**Setup (one-time):**
```bash
cd ~/MyProjects/CoreProjects/OpenTeam
uv tool install -e .                # ships openteam-mcp + 4 openteam-<tool> scripts
mkdir -p ~/.rovodev/skills/openteam
cp src/openteam/mcp_server/templates/SKILL.md ~/.rovodev/skills/openteam/
# merge mcp.json snippet into ~/.rovodev/mcp.json (jq -s 'add' or hand-edit)
```
