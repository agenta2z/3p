# MRS RankEvolve

Welcome! Type your message and press **Enter** to send.

**Commands:**
- `/exit` or `Ctrl+C` — quit
- `/clear` — clear conversation history
- `/model <name>` — switch chat model
- `/set-session-root [path]` — show or set the session root path for `/task`
- `/task <request>` — run a task with dual-agent workflow
- `/kn <knowledge>` — add/load/search knowledge
- `/help` — show all commands

---

## Dual Agent `/task` Command

**Inline options** (override CLI defaults):
```
/task --plan <request>           # Plan-only mode (stops at plan_consensus)
/task --full <request>           # Full workflow (plan + execution)
/task --confirm <request>        # Plan then confirm mode
/task --execute <request>        # Execute-only mode
/task --claude-only <request>    # Use Claude for both agents (bypass Devmate)
/task --model opus <request>     # Use specific Claude model (opus, sonnet)
```

**Combine options:**
```
/task --plan --claude-only --model opus Can you help with...
```

**CLI options** (set at launch):
- `--claude-model <model>` — Claude model for tasks (sonnet, opus, claude-opus-4-5)
- `--use-claude-only` — Use Claude for both planner and reviewer agents
- `--execution-mode <mode>` — Default mode: plan, full, confirm, execute
- `--output-dir <path>` — Custom output directory for artifacts

---

## Knowledge `/kn` Command

- `/kn add <text>` — Add knowledge with LLM classification
- `/kn load <file>` — Load and ingest a file (.md, .txt, .json)
- `/kn <file>` — Auto-detect and load a file
- `/kn search <query>` — Search stored knowledge
- `/kn list` — List all knowledge pieces
- `/kn clear` — Clear all knowledge
- `/kn status` — Show LLM ingestion status

---

**Multi-line input:** Press `Escape` then `Enter`, or `Ctrl+O` for a new line.
