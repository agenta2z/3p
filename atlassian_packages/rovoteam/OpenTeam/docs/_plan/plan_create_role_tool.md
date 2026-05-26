# Plan: "Create Role" Tool — Breakdown-Then-Aggregate via RovoChat

> **Date**: 2026-04-06  
> **Author**: Rovo Dev  
> **Status**: Draft — awaiting approval

---

## 1. Executive Summary

Build a **"create role"** tool under `OpenTeam/src/server/resources/tools/` that, given a
high-level description of an AI employee role (e.g. *"Senior Backend Engineer focused on
microservices and API design"*), automatically:

1. **Breaks down** the role into research queries covering distinct facets (responsibilities,
   required skills, collaboration patterns, success metrics, growth path, etc.)
2. **Researches** each facet in parallel via `RovoChatInferencer` (Atlassian's Rovo knowledge search)
3. **Aggregates** all research results into a cohesive **Role Responsibility Document**

The orchestration engine is `BreakdownThenAggregateInferencer` from AgentFoundation.

An end-to-end test script (CLI-runnable, similar to `test_plan_then_implement.py`) is provided
under `OpenTeam/test/resources/tools/create_role/`.

---

## 2. Architecture Overview

```
User Request: "Create a role for an AI DevOps Engineer"
        │
        ▼
┌─────────────────────────────────────┐
│  create_role tool (tool.json)       │  ← Tool definition (rankevolve style)
│  + executor.py                      │  ← Wiring logic
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│  BreakdownThenAggregateInferencer                           │
│  (AgentFoundation flow_inferencers)                         │
│                                                             │
│  ┌─────────────────────┐                                    │
│  │ Breakdown Inferencer │  Uses BREAKDOWN prompt template   │
│  │ (RovoChatInferencer) │  → produces numbered list of      │
│  └──────────┬──────────┘    research queries                │
│             │                                               │
│     ┌───────┼───────┬─────────┐                             │
│     ▼       ▼       ▼         ▼                             │
│  ┌──────┐┌──────┐┌──────┐┌──────┐                           │
│  │Worker││Worker││Worker││Worker│  Each = RovoChatInferencer │
│  │  0   ││  1   ││  2   ││  N   │  researching one facet    │
│  └──┬───┘└──┬───┘└──┬───┘└──┬───┘                           │
│     └───────┴───────┴───────┘                               │
│             │                                               │
│             ▼                                               │
│  ┌──────────────────────┐                                   │
│  │ Aggregator Inferencer │  Uses AGGREGATE prompt template  │
│  │ (RovoChatInferencer)  │  → merges all facet research     │
│  └──────────────────────┘    into a role responsibility doc │
│                                                             │
└─────────────────────────────────────────────────────────────┘
               │
               ▼
    Role Responsibility Document (Markdown)
```

---

## 3. Key Design Decisions & Critical Thinking

### 3.1 Why BreakdownThenAggregateInferencer (not DualInferencer/PTI)?

- **DualInferencer** is for propose→review consensus loops — not our pattern.
- **PlanThenImplementInferencer** chains plan→execute — overkill for a single-stage research task.
- **BreakdownThenAggregateInferencer** is precisely the diamond fan-out/fan-in pattern
  we need: one query → N parallel sub-queries → aggregated result.
- From the source code, its graph structure is:
  ```
  Layer 1 (start_nodes):  worker_0, worker_1, ..., worker_N   (parallel fan-out)
                               \        |            /
  Layer 2:                        aggregator                  (fan-in)
  ```
  The breakdown step runs *before* the graph is constructed (since the number
  of worker nodes depends on its output).

### 3.2 Why RovoChatInferencer for all three stages?

| Stage | Why RovoChat | Alternative Considered |
|-------|-------------|----------------------|
| **Breakdown** | General-purpose reasoning to decompose a role into research facets | Raw LLM (Claude) — simpler but adds a second inferencer type |
| **Worker** | **Primary value** — searches across Atlassian knowledge (Confluence, Jira, etc.) to find relevant org-specific information for each facet | No alternative — this is the whole point |
| **Aggregation** | Synthesizes research with knowledge grounding; can cross-reference org knowledge during synthesis | Raw LLM — would work but loses grounding |

**Decision**: Keep all three stages as RovoChat for uniformity and simplicity. The tool can be
reconfigured later by swapping the `worker_factory` or `aggregator_inferencer`.

### 3.3 Prompt Template Strategy

We define **three** prompt template modules as Python string constants:

| Template | Purpose | Key Variables |
|----------|---------|---------------|
| `breakdown_templates.py` | Decompose role into research queries | `{role_description}` |
| `worker_templates.py` | Research a single facet via Rovo knowledge search | `{sub_query}` |
| `aggregate_templates.py` | Merge all facet results into a role doc | `{worker_results}`, `{original_query}` |

**Why Python string constants instead of Jinja2/.j2 files?**
- The rankevolve `prompt_templates/` directory uses `.jinja2` files with `TemplateManager`,
  but the E2E test scripts (`test_plan_then_implement.py`, `test_dual_inferencer`) use Python
  string constants with simple `.format()` substitution — this is our closer reference pattern.
- OpenTeam doesn't yet have a `TemplateManager` dependency, so Python constants are
  simpler and self-contained.
- Migration to Jinja2 is straightforward if needed later.

### 3.4 BreakdownThenAggregateInferencer Wiring Details

From reading the source code, the key constructor parameters are:

```python
BreakdownThenAggregateInferencer(
    breakdown_inferencer=...,       # InferencerBase — runs first, produces list of sub-queries
    worker_factory=...,             # Callable(sub_query=str, index=int) -> InferencerBase
    aggregator_inferencer=...,      # InferencerBase — receives all worker results
    aggregator_prompt_builder=...,  # Optional: Callable(worker_results, original_query) -> str
    max_breakdown=8,                # Cap on number of sub-queries
    max_concurrency=3,              # Semaphore limit for parallel async workers
    breakdown_parser=None,          # Optional: custom parser (default: parse_numbered_list)
)
```

The `worker_factory(sub_query, index)` creates a fresh inferencer per sub-query. Each worker's
`ainfer(sub_query)` is called by the graph. The `aggregator_prompt_builder` lets us customize
how worker results are fed to the aggregator (default: numbered "### Result N" blocks).

### 3.5 RovoChatInferencer Configuration

From the source code, key constructor params:

```python
RovoChatInferencer(
    cloud_id="...",                 # Required: Atlassian cloud ID
    uct_token="...",                # Auth: UCT token (or use ASAP/basic)
    base_url="...",                 # Optional: override (default from env/staging)
    agent_named_id="...",           # Optional: route to specific Rovo agent
    auto_continue=True,             # Auto-reply to clarification questions
    max_continuations=5,            # Max auto-continuation turns
    auto_resume=False,              # Reuse previous conversation
)
```

For the **breakdown** inferencer, we prepend the breakdown prompt as the query itself
(the input to `ainfer()` is the full prompt with the role description embedded).

For **workers**, each gets a fresh `RovoChatInferencer` instance (new conversation per facet).

For the **aggregator**, we use a custom `aggregator_prompt_builder` that formats all worker
results with the aggregation prompt template.

### 3.6 Authentication

RovoChatInferencer reads credentials from environment variables with fallbacks:
- `ROVOCHAT_CLOUD_ID` (fallback: `JIRA_CLOUD_ID`, `ATLASSIAN_CLOUD_ID`)
- `ROVOCHAT_UCT_TOKEN` (fallback: `JIRA_UCT_TOKEN`)
- `ROVOCHAT_BASE_URL` (fallback: `JIRA_BASE_URL`)

The test script accepts `--cloud-id` and `--uct-token` CLI flags that override env vars.

---

## 4. File Structure

### 4.1 Tool Definition

```
src/server/resources/tools/
├── __init__.py
└── create_role/
    ├── __init__.py              # Exports: build_create_role_inferencer
    ├── tool.json                # Declarative tool metadata (rankevolve style)
    └── executor.py              # Wiring: builds BTA pipeline with RovoChat
```

### 4.2 Prompt Templates

```
src/server/resources/prompt_templates/
├── __init__.py
└── create_role/
    ├── __init__.py              # Exports all template constants
    ├── breakdown_templates.py   # BREAKDOWN_PROMPT — decomposes role into facets
    ├── worker_templates.py      # WORKER_PROMPT — researches one facet
    └── aggregate_templates.py   # AGGREGATE_PROMPT — merges results into doc
```

### 4.3 End-to-End Test

```
test/resources/tools/create_role/
├── __init__.py                  # Package marker
├── __main__.py                  # CLI entry point (delegates to test_create_role.main)
└── test_create_role.py          # Main test script with click CLI
```

### 4.4 Package Init Files (to create if missing)

```
src/server/resources/__init__.py
src/server/resources/tools/__init__.py
src/server/resources/prompt_templates/__init__.py
test/__init__.py                     # if missing
test/resources/__init__.py           # if missing
test/resources/tools/__init__.py     # if missing
```

---

## 5. Detailed File Specifications

### 5.1 `tool.json`

```json
{
  "name": "create_role",
  "description": "Create an AI employee role by researching responsibilities, skills, collaboration patterns, success metrics, and growth paths via Atlassian Rovo knowledge search. Produces a comprehensive role responsibility document.",
  "tool_type": "Action",
  "category": "workflow",
  "parameters": [
    {
      "name": "role_description",
      "type": "string",
      "required": true,
      "positional": true,
      "description": "High-level description of the role to create (e.g., 'Senior Backend Engineer focused on microservices')."
    },
    {
      "name": "--output-path",
      "type": "path",
      "description": "Path to write the generated role responsibility document."
    },
    {
      "name": "--max-facets",
      "type": "int",
      "default": 8,
      "description": "Maximum number of facets to research (caps the breakdown output)."
    },
    {
      "name": "--max-concurrency",
      "type": "int",
      "default": 3,
      "description": "Maximum parallel RovoChat queries for worker stage."
    }
  ],
  "returns": "Markdown role responsibility document with sections for responsibilities, skills, collaboration patterns, metrics, and growth path.",
  "examples": [
    "create_role \"AI DevOps Engineer specializing in CI/CD and infrastructure automation\"",
    "create_role \"Senior ML Engineer for recommendation systems\" --max-facets 10",
    "create_role \"Product Manager for developer tools\" --output-path ./roles/pm_devtools.md"
  ]
}
```

### 5.2 `executor.py` — Pipeline Wiring

```python
def build_create_role_inferencer(
    cloud_id: str,
    uct_token: str | None = None,
    base_url: str | None = None,
    agent_named_id: str | None = None,
    max_facets: int = 8,
    max_concurrency: int = 3,
) -> BreakdownThenAggregateInferencer:
    """Build a BreakdownThenAggregateInferencer wired for role creation."""
```

Key implementation logic:

1. **Create breakdown inferencer**: A `RovoChatInferencer` instance. The breakdown prompt
   is injected as part of the `ainfer()` input (not as a system prompt — RovoChat doesn't
   have a configurable system prompt; the prompt IS the user message). The full input to
   `ainfer()` will be: `BREAKDOWN_PROMPT.format(role_description=user_input)`.

   → We wrap this in a thin `PromptWrapperInferencer` (defined in executor.py) that
   prepends the template before delegating to the underlying RovoChat inferencer.

2. **Define worker_factory**: `def factory(sub_query, index) -> RovoChatInferencer`. Each
   call creates a new `RovoChatInferencer` with the same auth config. The sub-query is
   passed directly to `ainfer()` by the BTA graph, but we want to prepend the worker prompt.
   → Same `PromptWrapperInferencer` pattern.

3. **Create aggregator inferencer**: Another `RovoChatInferencer` with the aggregation prompt.

4. **Define `aggregator_prompt_builder`**: Custom function that takes `(worker_results, original_query)`
   and formats them using `AGGREGATE_PROMPT`.

5. **Wire BTA**:
   ```python
   return BreakdownThenAggregateInferencer(
       breakdown_inferencer=breakdown_inf,
       worker_factory=factory,
       aggregator_inferencer=aggregator_inf,
       aggregator_prompt_builder=agg_prompt_builder,
       max_breakdown=max_facets,
       max_concurrency=max_concurrency,
   )
   ```

### 5.3 `PromptWrapperInferencer` — Thin Adapter

Since `RovoChatInferencer` treats its input as the user message (no separate system prompt),
we need a wrapper that prepends the prompt template to the input before calling `ainfer()`.

```python
class PromptWrapperInferencer(InferencerBase):
    """Wraps an inferencer with a prompt template applied to the input."""

    def __init__(self, inferencer, prompt_template, **kwargs):
        self.inferencer = inferencer
        self.prompt_template = prompt_template

    def _infer(self, input, inference_config=None, **kwargs):
        formatted = self.prompt_template.format(input=input)
        return self.inferencer.infer(formatted, inference_config=inference_config, **kwargs)

    async def _ainfer(self, input, inference_config=None, **kwargs):
        formatted = self.prompt_template.format(input=input)
        return await self.inferencer.ainfer(formatted, inference_config=inference_config, **kwargs)
```

### 5.4 Prompt Template Content

#### `breakdown_templates.py`

```python
BREAKDOWN_PROMPT = """\
I need to create a comprehensive role description for an AI employee position. \
Please break down the following role into specific research questions that I should \
investigate to build a complete understanding. Each question should target a distinct \
aspect of the role.

Role to create: {input}

Please provide exactly 5-8 research questions as a numbered list. Each question should \
be specific, actionable, and focused on a single aspect. Cover these dimensions:
1. Core responsibilities and day-to-day activities
2. Required technical skills and domain expertise
3. Cross-functional collaboration and stakeholder interactions
4. Key performance indicators and success metrics
5. Career growth trajectory and skill development path
6. Tools, platforms, and technologies involved
7. Common challenges and mitigation strategies
8. Team structure and reporting relationships

Output ONLY the numbered list — no preamble, no explanation.
"""
```

#### `worker_templates.py`

```python
WORKER_PROMPT = """\
Please research the following question thoroughly using available organizational \
knowledge, best practices, and industry standards. Provide detailed, actionable findings.

Research question: {input}

Structure your response with:
- **Key Findings**: 3-5 specific findings with supporting details
- **Best Practices**: Industry-standard approaches relevant to this aspect
- **Recommendations**: Concrete, actionable recommendations
- **Examples**: Real-world examples or templates where applicable

Be thorough but concise. Focus on practical, implementable insights.
"""
```

#### `aggregate_templates.py`

```python
AGGREGATE_PROMPT = """\
I've completed research on multiple facets of an AI employee role. Please synthesize \
all the research findings below into a single, cohesive Role Responsibility Document.

Original role request: {original_query}

Research findings:
{worker_results}

Create a comprehensive Role Responsibility Document in Markdown with these sections:

## 1. Role Overview
Brief description of the role, its purpose, and where it fits in the organization.

## 2. Core Responsibilities
Day-to-day activities and primary duties, organized by priority.

## 3. Required Skills & Competencies
Technical skills, soft skills, and domain expertise needed. Distinguish "required" vs "nice-to-have".

## 4. Collaboration & Communication
Key stakeholders, cross-functional interactions, reporting structure, and communication patterns.

## 5. Success Metrics & KPIs
Measurable outcomes that define success in this role, with suggested targets.

## 6. Tools & Technologies
Platforms, frameworks, and tools the role works with daily.

## 7. Challenges & Mitigation Strategies
Common obstacles and recommended approaches to handle them.

## 8. Growth Path & Career Development
Progression opportunities, skill development areas, and mentorship expectations.

## 9. Onboarding Plan
First 30/60/90 day milestones for ramping up in this role.

Ensure the document is internally consistent, avoids redundancy across sections, \
and reads as a professional role specification that could be used for hiring or \
onboarding. Synthesize and deduplicate — do NOT simply concatenate the research results.
"""
```

### 5.5 `test_create_role.py` — E2E Test Script

Pattern follows `test_plan_then_implement.py`:

```python
@click.command()
@click.option("--role-description", required=True, help="Role to create")
@click.option("--cloud-id", envvar="ROVOCHAT_CLOUD_ID", help="RovoChat cloud ID")
@click.option("--uct-token", envvar="ROVOCHAT_UCT_TOKEN", help="UCT auth token")
@click.option("--base-url", envvar="ROVOCHAT_BASE_URL", default=None)
@click.option("--agent-named-id", default=None, help="Rovo agent UUID")
@click.option("--max-facets", default=8, type=int)
@click.option("--max-concurrency", default=3, type=int)
@click.option("--output-dir", default=None, type=click.Path())
@click.option("--verbose", is_flag=True)
def main(role_description, cloud_id, uct_token, base_url, agent_named_id,
         max_facets, max_concurrency, output_dir, verbose):
```

**Execution flow**:

1. Setup logging (DEBUG if `--verbose`)
2. Validate auth (require `cloud_id` + either `uct_token` or env vars)
3. Create workspace: `output_dir or f"create_role_workspace_{timestamp}"`
4. Save config to `workspace/config.json`
5. Import and call `build_create_role_inferencer()` from executor
6. Run `asyncio.run(inferencer.ainfer(role_description))`
7. Save results:
   - `workspace/results/role_document.md` — the final output
   - `workspace/results/summary.json` — metadata (timing, facet count, etc.)
8. Print summary to stdout

**`__main__.py`**:
```python
from test.resources.tools.create_role.test_create_role import main
main()
```

---

## 6. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| RovoChat rate limiting with parallel workers | Medium | Medium | `max_concurrency=3` default; configurable |
| RovoChat auth token expiry during long runs | Low | High | Each worker creates fresh client; short-lived tokens refreshed per request |
| Breakdown produces too few/many facets | Low | Low | `max_breakdown` cap; prompt tuned for 5-8 range |
| Worker returns empty/irrelevant results | Medium | Medium | Aggregation prompt designed to handle gracefully; warnings logged |
| AgentFoundation import path issues | Medium | High | Test script validates imports upfront; document exact install requirements |
| Network timeouts on individual workers | Medium | Low | BTA `retry_on_exceptions=(Exception,)` on WorkGraphNodes provides automatic retry |
| `parse_numbered_list` fails on RovoChat output format | Low | Medium | Breakdown prompt explicitly requests numbered list format; BTA has fallback parsing |

---

## 7. Implementation Order

| Step | Files | Depends On | Effort |
|------|-------|-----------|--------|
| 1 | `prompt_templates/create_role/*.py` | Nothing | Small |
| 2 | `tools/create_role/tool.json` | Nothing | Small |
| 3 | `tools/create_role/executor.py` + `__init__.py` | Step 1 + AgentFoundation | Medium |
| 4 | `test/resources/tools/create_role/*.py` | Step 3 | Medium |
| 5 | Package `__init__.py` files | Nothing | Trivial |
| 6 | Manual E2E verification | Steps 1-5 + RovoChat credentials | Manual |

---

## 8. Open Questions

1. **Agent selection**: Should we route to a specific Rovo agent (via `agent_named_id`) for
   better domain-specific research, or use the default general-purpose agent?  
   → **Default**: Use general-purpose; configurable via CLI flag.

2. **Output format**: Should the role document also produce a structured JSON for the
   OpenTeam `Employee` data model (from `models.py`)?  
   → **Out of scope** for v1; Markdown first, JSON can be parsed or added later.

3. **Integration with OpenTeam routes**: Should `create_role` be callable via
   `role_skill_routes.py`?  
   → **Out of scope** for this PR; can be wired in as a follow-up.

4. **Conversation reuse**: Should all workers share the same RovoChat conversation, or
   each get a fresh one?  
   → **Fresh per worker** — avoids context pollution between facets, enables true parallelism.
