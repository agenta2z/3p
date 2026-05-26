# Tool Run Verification — Common Catalog

> **Purpose**: Shared, tool-agnostic post-run verification checklist for ALL BTA-based OpenTeam tools (`task`, `create_role`, `role_setup`, future tools). Each entry describes **WHAT a problematic run looks like** — not why. Treat as a black-box observer: "If you see X, the run is unhealthy." Causes evolve; observations remain stable.
>
> **Scope**: This catalog covers observations that apply to ANY tool whose execution flows through a BreakdownThenAggregate orchestrator (breakdown → workers → aggregator). Tool-specific observations live in each tool's own `VERIFICATION.md`.
>
> **Last updated**: 2026-05-21

---

## How to use

After every tool run:

1. Set `WS=<latest_workspace_path>` (each tool's `VERIFICATION.md` provides a one-liner)
2. Walk **§1 Common Audit Pack** below — universal yes/no checks (A1–A15)
3. Then walk the tool-specific audit pack in `<tool>/VERIFICATION.md`
4. If any check FAILS, find the matching observation entry (common §2 or tool-specific) to understand what the bad pattern looks like
5. If the failure is genuinely new, add a new observation per the **§3 Authoring Guide** in the appropriate doc (common-if-cross-tool, tool-specific-if-narrow)

> **Important — placement rule**:
> - If the observation could apply to ANY BTA tool → add here (`VERIFICATION_COMMON.md`)
> - If the observation references tool-specific deliverable names, prompt slots, or topology → add to that tool's `VERIFICATION.md`

---

## §1 Common Audit Pack (A1–A15)

| #   | Observation                                            | Pass criterion (✅ = healthy)                                                                                       | Ref  |
|-----|--------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------|------|
| A1  | Run terminated cleanly                                 | Log has no `Traceback`, no `WorkflowAborted`, ends with completion line                                            | O-1  |
| A2  | Workspace at canonical location                        | `$WS` resolves to `<repo>/_runtime/tasks/<tool>/...`, NOT under `src/`                                             | O-2  |
| A3  | All inferencers logged artifacts                       | every `.jsonl.parts/` contains `InferenceInput/` and `InferenceResponse/` subdirs each non-empty; `InferenceArgs/` is present OR JSONL has `InferenceArgs` entry with empty `item={}` (no kwargs passed is valid) | O-3  |
| A4  | Breakdown received the real request                    | `breakdown/.../InferenceInput/*.txt` is non-empty AND contains the user request verbatim                           | O-4  |
| A5  | Each worker got a DISTINCT facet                       | `worker_N/.../InferenceInput/*.txt` are pairwise non-equal AND each matches breakdown JSON index N                  | O-5  |
| A6  | Inferencer inputs look templated (not raw text)        | InferenceInput contains expected template scaffolding (task preamble, sections, etc.), not just the raw user text  | O-6  |
| A7  | Aggregator used file references                        | aggregator `InferenceInput/*.txt` contains `(See file:` references AND is <300 lines (not bloated with `<Response>`) | O-7  |
| A8  | Aggregator invoked exactly ONCE                        | `aggregator/.../InferenceInput/` has exactly 1 file                                                                | O-8  |
| A9  | Canonical deliverable surfaced under final_deliverables | `$WS/outputs/final_deliverables/<deliverable>` exists and contains substantive content (size + structure thresholds defined in tool VERIFICATION) | O-9  |
| A10 | Top-level run summary distinguishable from canonical   | `$WS/outputs/run_summary.md` (or equivalent) exists; no name-collision with the canonical deliverable name at top level | O-10 |
| A11 | No deliverable double-nesting                          | `$WS/outputs/final_deliverables/final_deliverables/` does NOT exist                                                | O-11 |
| A12 | No silent argument loss                                | No "Removing YAML key" warnings for user-relevant params; arguments declared in CLI all appear in logs              | O-12 |
| A13 | Workers' inputs match breakdown sub-tasks              | For each index `i`, `worker_i` `InferenceInput/*.txt` contains the matching sub-task description from `breakdown/outputs/breakdown_output.md` | O-14 |
| A14 | Aggregator references AND actively uses worker outputs | aggregator input has `(See file:` ref per worker (Mode A) AND response shows self-report OR unique fragments from each `worker_i/outputs/<artifact>` appear in `outputs/final_deliverables/*` (Mode B) | O-15 |
| A15 | Inferencer outputs honor `<Response>...</Response>` protocol when instructed | for each inferencer whose input instructs `<Response>` format, the STREAM file (`_runtime/inferencer_cache/.../stream_*.txt`) contains both `<Response>` and `</Response>` | O-16 |
| A16 | Aggregator received aggregation-specific preamble (not default) | aggregator `InferenceInput/*.txt` contains the canonical preamble opening `"You are aggregating the following upstream artifacts"` AND does NOT contain the default planning preamble (`## Planning Context`). Catches wrong template variant, missing template roots, prompt builder bypass, or stale wrapper composition. | O-17 |

### Generic one-liner sanity script

Each tool's `VERIFICATION.md` provides a wrapper that sets `$WS`, `$TOOL`, and (optionally) a canonical deliverable name; below is the common audit body:

```bash
# Assumes $WS, $TOOL, and (optional) $CANONICAL_DELIVERABLE are exported by tool wrapper.
echo "=== A1 abort/error scan ==="
find "$WS" -name "*.log" -exec grep -l "Traceback\|WorkflowAborted\|NameError" {} \; 2>/dev/null

echo "=== A2 canonical workspace location ==="
case "$WS" in
  */src/*) echo "FAIL: workspace under src/ ($WS)";;
  */_runtime/tasks/$TOOL/*) echo "OK: under _runtime/tasks/$TOOL/";;
  *) echo "WARN: non-canonical workspace ($WS)";;
esac

echo "=== A3 .jsonl.parts integrity ==="
for d in $(find "$WS" -type d -name "*.jsonl.parts"); do
  for sub in InferenceInput InferenceResponse; do
    n=$(ls "$d/$sub" 2>/dev/null | wc -l)
    [ "$n" -gt 0 ] || echo "MISSING: $d/$sub"
  done
done

echo "=== A7 aggregator input shape (per aggregator) ==="
for agg in $(find "$WS" -path "*/aggregator/logs/session/*.jsonl.parts/InferenceInput" -type d); do
  inp=$(ls "$agg"/*.txt 2>/dev/null | head -1)
  [ -f "$inp" ] && {
    echo "  $agg:"
    wc -l "$inp"
    echo "    file refs: $(grep -c '(See file:' "$inp")"
    echo "    inlined responses: $(grep -c '<Response>' "$inp")"
  }
done

echo "=== A8 aggregator invocation count (per aggregator) ==="
for agg in $(find "$WS" -path "*/aggregator/logs/session/*.jsonl.parts/InferenceInput" -type d); do
  echo "  $agg: $(ls $agg | wc -l) invocations"
done

echo "=== A11 double-nesting ==="
for nest in $(find "$WS" -path "*/final_deliverables/final_deliverables" -type d 2>/dev/null); do
  echo "FAIL double-nested: $nest"
done || echo "OK: no double-nesting"

echo "=== A13 worker input presence (sizes) ==="
for w in $(find "$WS" -type d -name "worker_*" -not -path "*/_runtime/*" -not -path "*/logs/*"); do
  wid=$(basename "$w")
  win=$(ls "$w"/logs/session/*.jsonl.parts/InferenceInput/*.txt 2>/dev/null | head -1)
  [ -f "$win" ] && echo "  $wid: $(wc -c <"$win") bytes input" || echo "  $wid: MISSING input"
done

echo "=== A14 aggregator references AND uses worker outputs ==="
# Mode A: file ref count
for agg in $(find "$WS" -path "*/aggregator/logs/session/*.jsonl.parts/InferenceInput" -type d); do
  inp=$(ls "$agg"/*.txt 2>/dev/null | head -1)
  agg_parent=$(dirname "$(dirname "$(dirname "$(dirname "$agg")")")")
  parent=$(dirname "$agg_parent")
  siblings=$(find "$parent" -maxdepth 1 -type d -name "worker_*" | wc -l | tr -d ' ')
  [ -f "$inp" ] && {
    refs=$(grep -c "(See file:" "$inp")
    echo "  $(basename $(dirname $agg_parent))/aggregator: refs=$refs siblings=$siblings"
  }
done

# Mode B content traceability — manual per-tool:
#   For each worker, pick a unique fragment from its output and grep the deliverable.

echo "=== A15 <Response> protocol compliance ==="
for stream in $(find "$WS" -path "*_runtime/inferencer_cache/*/stream_*.txt" 2>/dev/null); do
  open=$(grep -c '<Response>' "$stream" 2>/dev/null)
  close=$(grep -c '</Response>' "$stream" 2>/dev/null)
  [ "$open" -ge 1 ] && [ "$close" -ge 1 ] && tag="OK" || tag="MISSING"
  echo "  $tag open=$open close=$close $(basename $stream)"
done

echo "=== A16 aggregator preamble variant ==="
for agg in $(find "$WS" -path "*/aggregator/logs/session/*.jsonl.parts/InferenceInput" -type d); do
  inp=$(ls "$agg"/*.txt 2>/dev/null | head -1)
  [ -f "$inp" ] && {
    agg_preamble=$(grep -c "You are aggregating the following upstream artifacts" "$inp")
    default_pre=$(grep -c "## Planning Context" "$inp")
    echo "  aggregation preamble: $agg_preamble (want >=1)"
    echo "  default preamble (BAD): $default_pre (want 0)"
    [ "$agg_preamble" -ge 1 ] && [ "$default_pre" -eq 0 ] && echo "  PASS" || echo "  FAIL"
  }
done
```

> **Tip — auto-discover $WS**: each tool's `VERIFICATION.md` provides a `WS=$(ls -td …/$TOOL/* | head -1)` snippet.

---

## §2 Common Observation Catalog (O-1 – O-16)

### O-1 — Run aborts unexpectedly
- **Look for**: log/stderr contains `Traceback`, `NameError`, `WorkflowAborted`, OR the launcher process exits non-zero before reaching the completion line
- **Distinguishes from healthy**: healthy runs end with an explicit "completed" line and zero exception traces in any log file

### O-2 — Workspace created in the wrong location
- **Look for**: workspace path contains `/src/` (i.e., under source tree) OR is created in cwd OR under `/tmp/` instead of `<repo>/_runtime/tasks/<tool>/`
- **Distinguishes from healthy**: healthy runs always place workspace under `<repo>/_runtime/tasks/<tool>/<tool>_<YYYYMMDD>_<HHMMSS>_<8hash>/`

### O-3 — Hollow `.jsonl.parts/` directories
- **Look for**: an inferencer's `logs/session/*.jsonl.parts/` directory exists but is empty, OR is missing `InferenceInput/` or `InferenceResponse/` subdirs, OR those subdirs exist but have 0 files. (Note: `InferenceArgs/` may be absent when no kwargs were passed — the framework only externalizes non-primitive values; the JSONL still has a record with `item={}`)
- **Distinguishes from healthy**: every inferencer that ran should have ≥1 file in EACH of the 2 mandatory subdirs (`InferenceInput`, `InferenceResponse`)

### O-4 — Inferencer received empty / wrong input
- **Look for**: `InferenceInput/*.txt` is empty, OR contains a placeholder like `<no_query>`/`<empty>`, OR contains a value that doesn't match what the user/upstream should have passed (e.g., breakdown received some unrelated string)
- **Distinguishes from healthy**: the input text should contain the actual upstream content (user request, parent's output, sub-facet description)

### O-5 — Workers received duplicate / wrong facets
- **Look for**: two or more `worker_N/.../InferenceInput/*.txt` files are byte-identical OR don't correspond to distinct entries in `breakdown/outputs/breakdown_output.md`
- **Distinguishes from healthy**: in an N-way breakdown, each worker should receive a UNIQUE sub-query matching its position in the breakdown plan

### O-6 — Inferencer input is raw, not templated
- **Look for**: `InferenceInput/*.txt` contains ONLY the bare user request (or upstream content) with NO surrounding template scaffolding — no task preamble, no instruction header, no rendered Jinja2 blocks (like deep_mode, elegant_mode, output_path directives)
- **Distinguishes from healthy**: a properly-templated input has 80–200 lines of scaffolding around a small embedded query; a raw input is just the query itself
- **Bonus signal**: log warnings like `Removing YAML key 'template_*' — not a valid __init__ param` indicate the inferencer can't accept template attribs and will silently render nothing

### O-7 — Aggregator input bloated with inlined worker text
- **Look for**: aggregator's `InferenceInput/*.txt` exceeds ~300 lines AND contains literal `<Response>...</Response>` blocks holding full worker outputs (multi-KB chunks of markdown) inlined directly into the prompt; OR has ZERO `(See file: ...)` references when workers produced output files
- **Distinguishes from healthy**: a healthy aggregator input is compact (<300 lines), references upstream artifacts via `(See file: <path>)` lines, and lets the agent read them on demand

### O-8 — Aggregator invoked multiple times within ONE run
- **Look for**: `aggregator/.../InferenceInput/` contains 2 or more `.txt` files in a single run (each timestamped seconds-to-minutes apart with near-identical content)
- **Distinguishes from healthy**: a single run should produce exactly 1 aggregator input. Repeat invocations indicate a retry loop, cache replay, or framework re-entry bug

### O-9 — Canonical deliverable missing or insubstantial
- **Look for**: `$WS/outputs/final_deliverables/<deliverable>` does not exist, OR exists but is suspiciously small (size threshold depends on tool — see tool VERIFICATION), OR has insufficient structure (heading count below tool threshold)
- **Distinguishes from healthy**: a healthy canonical deliverable is the full aggregator output with substantive multi-section content (specific size/heading thresholds in each tool's VERIFICATION.md)

### O-10 — Top-level output ambiguity
- **Look for**: two files with the same name (e.g., `<deliverable>.md`) exist at BOTH `$WS/outputs/` AND `$WS/children/aggregator/outputs/` AND they have different content/size — leaving the user unsure which is "the real one"; OR the top-level `outputs/<deliverable>.md` contains a short summary blurb instead of the real document
- **Distinguishes from healthy**: top-level should have a distinctly-named summary (e.g., `run_summary.md`); the canonical deliverable should live exclusively under `outputs/final_deliverables/`

### O-11 — Deliverable double-nesting
- **Look for**: `$WS/outputs/final_deliverables/final_deliverables/<any_file>` exists (one level too deep)
- **Distinguishes from healthy**: `final_deliverables/` should appear EXACTLY once on any path

### O-12 — Silent argument loss
- **Look for**: a parameter the user explicitly passed at CLI (or via `/tool` slash invocation) does NOT appear in the downstream `InferenceInput/` content; log may show "Removing YAML key" warnings OR no warning at all (silent); OR the breakdown clearly didn't use a provided value
- **Distinguishes from healthy**: every user-provided argument should be observably consumed (either by appearing in rendered prompts, or by altering observable behavior like worker count)

### O-13 — Subagent gives up on out-of-workspace path
- **Look for**: subagent output contains phrases like `"path you provided is outside the current workspace"` OR `"I cannot access that path"` AND the parent agent did NOT fall back to `bash cat <path>` AND the run completed without ever reading the referenced material
- **Distinguishes from healthy/known-workaround**: it's acceptable for a subagent to refuse, AS LONG AS the parent retries via `bash cat` and successfully reads the content. The failure mode is when the parent gives up entirely

### O-14 — Workers don't receive content matching the breakdown
- **Look for**: `breakdown/outputs/breakdown_output.md` defines N sub-tasks with specific descriptions/scopes, but the corresponding `worker_N/.../InferenceInput/*.txt` does NOT contain the matching sub-task description (workers received a different facet, an outdated one, or a generic placeholder)
- **Distinguishes from healthy**: for every entry index `i` in the breakdown plan, `worker_i` should have an `InferenceInput/*.txt` that demonstrably reflects that specific entry's description/scope/todos (verbatim or near-verbatim substring match)
- **Verify**: cross-check by extracting the breakdown JSON, then `grep` each entry's distinguishing phrase against the corresponding worker's InferenceInput

### O-15 — Aggregator either doesn't reference worker outputs OR doesn't actively use them despite the reference
- **Look for** (either failure mode):
  - **Mode A — Missing reference**: aggregator `InferenceInput/*.txt` does NOT contain `(See file: <worker_path>)` lines pointing to each worker's output file (and the worker outputs ARE missing from any other form in the prompt too)
  - **Mode B — Reference ignored**: aggregator `InferenceInput/*.txt` DOES contain the file references, BUT the aggregator's `InferenceResponse/*.txt` (or `_runtime/inferencer_cache/.../stream_*.txt`) shows the agent never read those files (no `view_file`/`read_file`/`bash cat` tool calls against worker output paths), AND the synthesized output is missing content/facts that exist ONLY in worker outputs
- **Distinguishes from healthy**: a healthy run has BOTH (a) per-worker file references in the aggregator input AND (b) evidence of active consumption — either explicit file-read tool calls OR verbatim/unique fragments from each worker file appearing in the synthesis
- **Verify**:
  - Mode A: `grep -c "(See file:" $WS/children/aggregator/logs/session/*.jsonl.parts/InferenceInput/*.txt` should equal N (worker count)
  - Mode B (content traceability — most reliable): for each `worker_i`, pick a unique fragment from `worker_i/outputs/<artifact>` (e.g., a distinctive heading or named concept) and `grep` it in the aggregator's final deliverable; at least 1 fragment per worker should match
  - Mode B (self-report — secondary): `grep -E "I read|consulted|Worker [0-9]+|worker_[0-9]+" $WS/children/aggregator/logs/session/*.jsonl.parts/InferenceResponse/*output*.txt` should show the aggregator naming each worker it consumed
  - **Note**: `_runtime/inferencer_cache/.../stream_*.txt` for RovoDev/RovoChat CLI inferencers contains only the FINAL `<Response>` text, NOT intermediate tool calls; do not rely on it for tool-call detection

### O-16 — Inferencer output missing `<Response>...</Response>` protocol delimiters
- **Look for**: an inferencer's STREAM file (`_runtime/inferencer_cache/<class>/<id>_<ts>/stream_*.txt`) does NOT contain BOTH `<Response>` and `</Response>` tags wrapping the actual deliverable, despite the prompt template's task-response-format instruction (often phrased as "Use literal `<Response>` and `</Response>` in your actual reply — `<ResponseSchema>` is just the example container") being present in the corresponding `InferenceInput/*.txt`
- **Distinguishes from healthy**: a compliant stream contains exactly one `<Response>` and one `</Response>` tag-pair surrounding the deliverable; the framework's `extract_delimited()` then cleanly extracts the inner content. Missing tags force fallback to "use whole output" — silently lenient but fragile.
- **Important**: do NOT check `InferenceResponse/*output*.txt` for the tags — for CLI-based agents (RovoDev/RovoChat) that file captures the full terminal dump (banner, agent setup, ✓ tool calls, formatted output blocks) where `<tag>`-like text may be stripped by terminal rendering. The stream file is the authoritative source of what the agent actually emitted.
- **Verify** (per response file):
  - `open=$(grep -c '<Response>' $stream); close=$(grep -c '</Response>' $stream)` — both should equal 1
  - Confirm input asked for the format: `grep -q '<Response>' $WS/children/<inferencer>/logs/session/*.jsonl.parts/InferenceInput/*.txt`
- **Caveat**: if the corresponding `InferenceInput/*.txt` does NOT instruct the `<Response>` format, then absence in output is expected — not a bug. Always check the input first.

### O-17 — Aggregator received default preamble instead of aggregation-specific preamble
- **Look for**: aggregator's `InferenceInput/*.txt` contains the default planning preamble (`## Planning Context`, generic plan creation instructions) instead of the aggregation-specific preamble (`You are aggregating the following upstream artifacts...` with `{{ upstream_artifacts }}` slot and `{{ aggregation_guidance }}` conditional). The aggregator functions without it (the LLM still synthesizes) but produces hollow output — worker research is not referenced, no `(See file:)` paths, and synthesis quality degrades.
- **Distinguishes from healthy**: a healthy aggregator input starts its `<UserRequest>` block with "You are aggregating the following upstream artifacts..." followed by `### Result N` entries with `(See file: <worker_path>)` references. An unhealthy one starts with `## Planning Context` (the generic default).
- **Root causes** (ordered by frequency):
  1. **Missing template root**: the TemplateManager has only the consumer root (OpenTeam) but not the framework root (AgentFoundation) where `aggregation/default.jinja2` lives. Typically caused by `_template_manager.templates` override clobbering the YAML's two-root list with a single path.
  2. **Wrapper variable composition**: the wrapper variable `context.user_request_with_task_preamble` bakes in the default `task_preamble` during auto-discovery composition, and the caller's correct aggregation preamble arrives too late. Requires `enable_templated_feed=True` AND the wrapper recomposition step in `_resolve_templated_feed()`.
  3. **SLOT_DEFAULTS override**: `template_version` set explicitly on the aggregator gets overridden back to `"aggregation"` by SLOT_DEFAULTS during BTA execution. Use per-variable overrides in `template_variables` instead of `template_version` for task-specific variants.
- **Verify**:
  ```bash
  for agg in $(find "$WS" -path "*/aggregator/logs/session/*.jsonl.parts/InferenceInput" -type d); do
    inp=$(ls "$agg"/*.txt 2>/dev/null | head -1)
    [ -f "$inp" ] && {
      agg_preamble=$(grep -c "You are aggregating the following upstream artifacts" "$inp")
      default=$(grep -c "## Planning Context" "$inp")
      echo "  aggregation preamble: $agg_preamble (want >=1)"
      echo "  default preamble: $default (want 0)"
      [ "$agg_preamble" -ge 1 ] && [ "$default" -eq 0 ] && echo "  PASS" || echo "  FAIL"
    }
  done
  ```
- **Cross-ref**: A14a regression (2026-05-21); root cause documented in `AgentFoundation/_docs/_plan/template_and_variable_versioning_formalization/`

### O-18 — Inner aggregator files written to root workspace instead of own workspace
- **Look for**: in a nested BTA (e.g., role_setup), skill/tool files appear at `$WS/outputs/skills/` or `$WS/outputs/tools/` (root level) instead of `$WS/children/worker_N/children/aggregator/outputs/skills/`. The inner aggregator's own `outputs/` directory is empty or missing the expected deliverables.
- **Distinguishes from healthy**: a healthy nested BTA has files in `children/worker_N/children/aggregator/outputs/skills/` (the inner aggregator's own workspace). Root-level `outputs/skills/` should only contain files written by the OUTER aggregator.
- **Root cause**: `_target_path` cascade from `_run_topology()` propagates the root workspace path to ALL descendant inferencers. The inner aggregator's `effective_cwd` uses `target_path` (root workspace) instead of `_workspace.root` (correct inner workspace). Fix: use `{{ workspace_outputs }}` absolute paths in templates instead of relative `outputs/` paths.
- **Source**: Run `role_setup_20260525_085001_1e13c7db` — 70 files at root `outputs/`, 0 in inner aggregator workspace. Fixed in run `role_setup_20260525_213032_57d3f86c` via `{{ workspace_outputs }}` template variable.

### O-19 — Files in `outputs/` but `final_deliverables/` empty (promotion chain broken)
- **Look for**: an aggregator's `outputs/` directory contains skill/tool files (e.g., `outputs/skills/<name>/SKILL.md`, `outputs/tools/<name>/tool.json`) but `outputs/final_deliverables/` is empty. The parent BTA's `final_deliverables/` is also empty, and the outer aggregator reports no deliverables to integrate.
- **Distinguishes from healthy**: a healthy run has files MOVED from `outputs/` to `outputs/final_deliverables/` by `_finalize_output()`, which then cascade up via `_symlink_child_output()` to the parent BTA's `final_deliverables/`.
- **Root cause**: `output_is_deliverable` not set to `true` on the aggregator inferencer in the YAML. Without this flag, `_finalize_output()` skips the move from `outputs/` to `outputs/final_deliverables/`, breaking the entire promotion chain.
- **Source**: Run `role_setup_20260525_213032_57d3f86c` — inner aggregator had 28 files in `outputs/`, 0 in `final_deliverables/`. Fix: add `output_is_deliverable: true` to aggregator YAML config.

---

## §3 Authoring Guide — Adding a NEW Common Observation

When a run reveals a NEW unhealthy pattern that:
- Could apply to ANY BTA-based tool (not tied to one tool's deliverable names or topology)
- Is purely a **runtime observation** (something an auditor can see post-run by inspecting workspace files or logs) — NOT a static config issue

Then add it HERE (not in a tool-specific VERIFICATION.md):

1. Add a new `O-N` entry in **§2** with exactly two sub-sections:
   - **Look for**: concrete, file-grep-able signals
   - **Distinguishes from healthy**: contrast with the expected pattern
2. Add a row to the **§1 Common Audit Pack** with the verify command + new reference
3. Update the "Last updated" date at the top
4. Update the per-tool `VERIFICATION.md` files if the new check needs tool-specific parameters

> **Important**: Do NOT inline root causes or past fix plan references. Causes vary across recurrences; including them risks anchoring future investigators to outdated diagnoses. Keep observations purely as "what unhealthy looks like."

> **Placement decision rule**:
> - Generic across BTA tools → here (`VERIFICATION_COMMON.md`)
> - References specific tool deliverable names, prompt slots, expected facet count, output shape → tool's own `VERIFICATION.md`

---

## §4 Tool-Specific Verification Docs

Each BTA-based tool has its own `VERIFICATION.md` that:
1. References this common catalog as the baseline
2. Provides tool-specific values for parametrized common checks (e.g., canonical deliverable name + size threshold for A9, expected facet count for A5/A13)
3. Adds tool-specific observations (e.g., role_setup's nested BTA structure, create_role's role-document format)
4. Provides a tool-specific wrapper that sets `$WS`, `$TOOL`, and runs the common one-liner

| Tool | VERIFICATION.md |
|------|-----------------|
| `create_role` | `create_role/VERIFICATION.md` |
| `role_setup`  | `role_setup/VERIFICATION.md` |
| `task`        | `task/VERIFICATION.md` |
