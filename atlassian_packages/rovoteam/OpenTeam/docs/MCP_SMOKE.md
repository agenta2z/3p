# OpenTeam MCP Smoke Test Procedures

## Prerequisites

```bash
cd ~/MyProjects/CoreProjects/OpenTeam
uv tool install -e .   # or pip install -e .
```

## 1. Console Scripts

```bash
which openteam-mcp openteam-task openteam-create-role openteam-role-setup openteam-project-onboarding
# Expected: 5 paths returned

openteam-task --help
# Expected: tool.json parameters listed (no PYTHONPATH set)

openteam-create-role --help
# Expected: parameters listed (proves bootstrap works for module-level agent_foundation import)
```

## 2. MCP Server

```bash
# From OpenTeam root:
fastmcp dev "src/openteam/mcp_server/server.py:create_openteam_server"
# Expected: MCP inspector lists 4 tools
```

## 3. RovoDev TUI (if slash commands installed)

```
/task --help                           -> tool.json parameters
/task "what is 2+2"                    -> streamed output, exit 0
/task --plan "list 3 ways to learn py" -> plan mode
/create-role "Senior Backend Engineer" -> role document path
/role-setup ./roles/engineer.md        -> setup report path
/project-onboarding ./docs/role.md     -> runs (no ImportError)
/help                                  -> lists all 4 OpenTeam commands
/mcp                                   -> openteam server green, 4 tools
```

## 4. Cancellation

Start a long `/task` run, press Ctrl-C. Subprocess should SIGTERM within 5 seconds.

## 5. Automated Tests

```bash
cd ~/MyProjects/CoreProjects/OpenTeam
pytest test/openteam/ -v
```
