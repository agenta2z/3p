# OpenTeam MCP Integration

## Install (one-time)

```bash
# 1. Install OpenTeam
cd ~/MyProjects/CoreProjects/OpenTeam
uv tool install -e .                            # or: pip install -e .

# 2. Verify console scripts exist
which openteam-mcp openteam-task openteam-create-role openteam-role-setup openteam-project-onboarding
openteam-mcp --help                             # Typer help
openteam-task --help                            # tool.json-driven CLI help

# 3. Wire up RovoDev (one-time)
mkdir -p ~/.rovodev/skills/openteam
cp src/openteam/mcp_server/templates/SKILL.md ~/.rovodev/skills/openteam/
# Merge mcp.json snippet into ~/.rovodev/mcp.json
jq -s 'add' ~/.rovodev/mcp.json src/openteam/mcp_server/templates/mcp.json > ~/.rovodev/mcp.json.new
mv ~/.rovodev/mcp.json.new ~/.rovodev/mcp.json

# 4. Smoke-test the MCP server in isolation (run from OpenTeam root)
fastmcp dev "src/openteam/mcp_server/server.py:create_openteam_server"

# 5. End-to-end in RovoDev TUI
# - /task --help             -> tool.json parameters listed
# - /task "what is 2+2"      -> streamed output, exit 0
# - /mcp                     -> openteam server green, 4 tools
```

## Architecture

```
Slash surface:  /task <args>  ->  subprocess openteam-task  ->  executor.execute()
MCP surface:    mcp__openteam__openteam_task(...)  ->  in-process  ->  executor.execute()
CLI surface:    openteam-task <args>  ->  tool_cli.run_cli  ->  executor.execute()
```

All three surfaces reach the same `executor.execute()`. Zero business-logic duplication.

## Environment Variables

| Variable | Used by | Purpose |
|---|---|---|
| `OPENTEAM_HOME` | slash handler fallback | Path to OpenTeam checkout |
| `OPENTEAM_SIBLINGS_ROOT` | bootstrap.py | Path to dir containing AgentFoundation/ + PythonUtils/ |
| `OPENTEAM_PYTHON` | slash handler fallback | Python interpreter for `python -m` fallback (default: `python3`) |
| `OPENTEAM_LLM_BACKEND` | mcp.json env | Backend: mock, rovodev, claude_cli |
| `OPENTEAM_LLM_MODEL` | mcp.json env | Model identifier |
| `OPENTEAM_WORKING_DIR` | context.py | Agent working directory |

## Console Scripts

| Script | Entry Point | Purpose |
|---|---|---|
| `openteam-mcp` | `openteam.mcp_server.cli:app` | MCP server (Typer) |
| `openteam-task` | `task.cli:main` | Task tool standalone CLI |
| `openteam-create-role` | `create_role.cli:main` | Create-role standalone CLI |
| `openteam-role-setup` | `role_setup.cli:main` | Role-setup standalone CLI |
| `openteam-project-onboarding` | `project_onboarding.cli:main` | Project-onboarding standalone CLI |
