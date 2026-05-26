# role_setup — Post-Run Verification

**Shared baseline**: see [`../VERIFICATION_COMMON.md`](../VERIFICATION_COMMON.md) (A1-A15).
This file lists **only the role_setup-specific** checks layered on top.

> Usage: After every test run, set `WS=<workspace path>`, then execute the
> **Common Quick-Audit Pack** from `VERIFICATION_COMMON.md` **plus** the
> role_setup-only checks below.

---

# §0 Tool Profile

| Aspect | Value |
|---|---|
| **CLI** | `python -m openteam.server.resources.tools.role_setup` |
| **Required positional arg** | `role_document_path` (path to a markdown role doc on disk) |
| **Default `--max-facets`** | 3 (outer: skills/tools the role uses) |
| **Default `--max-inner-facets`** | 2 (inner: research subtasks per skill) |
| **Topology** | **Nested BTA** (no Dual wrapper) — outer BTA spawns N worker_* per skill; creation workers are **inner BTAs** with K worker_* per research subtask; association worker is a single leaf |
| **Canonical deliverable filename** | `role_setup_report.md` (vs `role_document.md` for create_role) |
| **YAML** | `src/openteam/server/resources/tools/role_setup/role_setup.yaml` (outer), `role_setup_skill_tool_creation.yaml` (inner BTA) |
| **Inferencer split** | RovoDevCLI for breakdown + aggregators + investigation workers + association; RovoChat for research workers |

---

# §1 Tool-Specific Quick-Audit Pack

Run **after** the Common A1-A15 checks pass. Replace `$WS` with the workspace path
(`_runtime/tasks/role_setup/role_setup_<TS>_<UUID>/`).

| # | Check | Pass criterion | Observation if FAIL |
|---|---|---|---|
| **R1** | Nested-BTA outer worker shape | `ls $WS/children/worker_*` shows ≥ 2 outer dirs (one per skill facet) | O-R1 |
| **R2** | Nested-BTA inner worker shape | Each creation `$WS/children/worker_N` (inner BTA, not the association leaf) contains its own `children/worker_*` subdirs | O-R2 |
| **R3** | Inner BTA isolation | Each outer worker's inner workers write to **their own** outputs, not shared paths | O-R3 (would reproduce as cross-worker symlinks, see common O-1) |
| **R4** | Canonical deliverable filename | `$WS/outputs/final_deliverables/role_setup_report.md` exists (NOT `role_document.md`) | O-R4 |
| **R5** | Role doc content was actually consumed | The outer aggregator's `$WS/children/aggregator/.../InferenceInput/*.txt` contains snippets / references from the user-supplied role doc (not just generic boilerplate) | O-R5 |
| **R6** | Skill decomposition matches role doc | The breakdown output's facet names (or `(See file: ...)` paths to outer worker outputs) reference skills/tools mentioned in the user's role doc | O-R6 |
| **R7** | Inner aggregators created actual skill/tool deliverables | `find $WS -name SKILL.md -type f` returns ≥ 1 AND `find $WS -name tool.json -type f` returns ≥ 1; `$WS/outputs/final_deliverables/` contains `skills/` and/or `tools/` subdirectories with structured deliverables, not just flat catalog documents | O-R7 |

## Quick One-Liner

```bash
WS=/path/to/role_setup_<TS>_<UUID>
echo "=== R1: outer-BTA worker count ==="
ls -d $WS/children/worker_* 2>/dev/null | wc -l
echo "=== R2: inner-BTA worker count per outer ==="
for w in $WS/children/worker_*; do
  inner=$(ls -d $w/children/worker_* 2>/dev/null | wc -l)
  echo "  $(basename $w): $inner inner workers"
done
echo "=== R4: canonical deliverable filename ==="
ls -la $WS/outputs/final_deliverables/role_setup_report.md 2>&1 | head -1
echo "=== R5: role-doc content in aggregator input ==="
grep -ci "machine learning\|MLE\|ML Engineer" \
  $WS/children/aggregator/logs/session/*.jsonl.parts/InferenceInput/*.txt \
  2>/dev/null | head -3
echo "=== R7: inner aggregators created actual skill/tool files ==="
echo "SKILL.md: $(find $WS -name SKILL.md -type f 2>/dev/null | wc -l | tr -d ' ')"
echo "tool.json: $(find $WS -name tool.json -type f 2>/dev/null | wc -l | tr -d ' ')"
ls -d $WS/outputs/final_deliverables/skills $WS/outputs/final_deliverables/tools 2>/dev/null
```

---

# §2 Tool-Specific Observations

### O-R1 — Outer-BTA workers missing or wrong count
- **Look for**: `$WS/children/worker_*` returns 0 dirs, or far fewer than `--max-facets`
- **Distinguishes from healthy**: N outer workers, where N ≈ min(LLM-produced-facets, max_facets). LLM may legitimately produce fewer than the cap.

### O-R2 — Inner-BTA workers missing (outer worker has no inner subdivision)
- **Look for**: A creation outer `worker_N/children/` directory has 0 `worker_*` dirs inside (only `breakdown/` and `aggregator/`), OR the inner BTA structure is entirely missing
- **Distinguishes from healthy**: Each creation outer worker (not the association leaf) has its own inner BTA that spawned K inner workers. The association worker is a leaf with no `children/` subdirectory — that is expected.

### O-R3 — Inner BTA isolation broken (cross-contamination)
- **Look for**: Symlinks or duplicated outputs across different outer workers' inner subtrees; an inner worker writing to a different outer worker's path
- **Distinguishes from healthy**: All paths are confined to their owning outer worker's subtree; `find $WS -type l` shows ZERO cross-outer-worker symlinks
- **Note**: This is the same class of bug as Common O-1 but at the nested-BTA layer (twice the surface area to inspect)

### O-R4 — Canonical deliverable has wrong filename
- **Look for**: `$WS/outputs/final_deliverables/role_document.md` exists (create_role filename leaked) instead of `role_setup_report.md`
- **Distinguishes from healthy**: Filename matches the `output_path` declared in `role_setup.yaml` (i.e., `role_setup_report.md`)
- **Why this matters**: A wrong filename here means BTA's `output_path` is being shadowed by another inferencer's, exactly the kind of A10/O-10 confusion the surfacing fix addresses

### O-R5 — Role doc content was not consumed by aggregator
- **Look for**: Aggregator `InferenceInput/*.txt` contains no terms from the user-supplied role doc (e.g., the role title, distinctive skills listed in the doc)
- **Distinguishes from healthy**: At minimum, the aggregator input contains either the verbatim role-doc text OR `(See file: ...)` references that point to worker outputs which themselves processed the role doc
- **Why this matters**: If the role doc never reaches the aggregator (directly or via workers), the synthesis is generic-LLM-knowledge rather than role-doc-grounded — defeating the purpose of providing a role doc

### O-R6 — Skill decomposition doesn't match the input role doc
- **Look for**: The breakdown phase produces facets that are entirely unrelated to the skills/tools enumerated in the role doc (e.g., role doc lists "PyTorch, Ray, KServe" but breakdown produces facets like "frontend frameworks, UI design")
- **Distinguishes from healthy**: At least some breakdown facets correspond directly to skills/tools in the role doc; the inner subtasks dive into those specific skills

### O-R7 — Inner aggregators produced catalog documents instead of skill/tool files
- **Look for**: `$WS/outputs/final_deliverables/` contains only flat `.md` report files (e.g., `MASTER_INVENTORY.md`, `ml_lifecycle_execution_stack.md`) but no `skills/` or `tools/` subdirectories. `find $WS -name SKILL.md` returns 0. Inner aggregator outputs are large consolidated catalog documents describing what skills/tools *should* be created, rather than the actual `SKILL.md`, `tool.json`, and `executor.py` files.
- **Distinguishes from healthy**: A healthy run has `outputs/final_deliverables/skills/<name>/SKILL.md` and `outputs/final_deliverables/tools/<name>/tool.json` subdirectories with structured deliverable files. The inner aggregator's `InferenceInput` contains the `skill_tool_creation` task_instructions (not the generic aggregation default).
- **Root causes** (both contributed in the observed failure):
  1. **Template cascade fallback**: `task_instructions/aggregation/skill_tool_creation.jinja2` did not exist. With `master_version=aggregation`, the cascade found `aggregation/default.jinja2` (generic "consolidate") before reaching the flat `skill_tool_creation.jinja2` (which has SKILL.md/tool.json writing instructions). Fix: moved `skill_tool_creation.jinja2` into the `aggregation/` subdirectory.
  2. **Preamble framing**: The implementation aggregation preamble said "Each input artifact is the outcome of one **execution** subtask... they should **compose, not compete**" — but inputs were research reports, not execution results. The aggregator interpreted this as "consolidate finished products" rather than "synthesize research into new deliverables." Fix: updated preamble to flexible wording matching the plan space.
- **Source**: Run `role_setup_20260524_202046_e4cfd3a7` — 0 SKILL.md, 0 tool.json produced. Fixed in run `role_setup_20260525_085001_1e13c7db` — 12 SKILL.md, 15 tool.json produced.

### O-R8 — Full role document inlined in outer aggregator prompt instead of path reference
- **Look for**: outer aggregator's `InferenceInput/*.txt` contains the full role document text (hundreds of lines of role responsibilities, SOPs, competencies) inside `<UserRequest>`. The prompt is 500+ lines when it should be ~100 lines (upstream artifacts + short reference + task instructions).
- **Distinguishes from healthy**: a healthy outer aggregator prompt has a short `{{ input }}` (e.g., "Set up the role defined at: <path>") and references the role document via `{{ role_doc_path }}` in the task_instructions. The full document is available on disk for the agent to read when needed.
- **Root cause**: the executor passed `request=role_doc_text` (full text) instead of `request=f"Set up the role defined at: {role_doc_abs}"` (path reference). All inferencers already have `{{ role_doc_path }}` in `template_extra_feed` for on-demand file access.
- **Source**: Runs `role_setup_20260524_202046_e4cfd3a7` and `role_setup_20260525_085001_1e13c7db` — outer aggregator input was 559-641 lines. Fixed by passing path reference as the BTA query.

---

# §3 Run Comparison Table

| Run | Date | `--max-facets` × `--max-inner-facets` | Outer workers | Inner workers (avg) | Deliverable size | Result |
|---|---|---|---|---|---|---|
| `role_setup_20260524_202046_e4cfd3a7` | 2026-05-24 | 3 × 2 | 3 (1 leaf + 2 inner BTA) | 20 (16 + 24) | 4 catalog docs, 0 SKILL.md, 0 tool.json | R7 FAIL — template cascade fallback produced catalogs instead of deliverables |
| `role_setup_20260525_085001_1e13c7db` | 2026-05-25 | 3 × 2 | 3 (1 leaf + 2 inner BTA) | 20 (14 + 26) | 12 SKILL.md, 15 tool.json, 15 executor.py, 4 knowledge blocks | A16 PASS, R7 PASS — template cascade + preamble fixes verified. O-18 FAIL (files at root), O-19 FAIL (empty final_deliverables), O-R8 FAIL (role doc inlined) |
| `role_setup_20260525_213032_57d3f86c` | 2026-05-25 | 3 × 2 | 3 (1 leaf + 2 inner BTA) | 21 (15 + 27) | 36 SKILL.md, 46 tool.json, 46 executor.py (inner agg) + outer agg re-built 18 skills, 22 tools, 6 knowledge | O-18 PASS (files in correct workspace), O-19 FAIL (output_is_deliverable missing), Issue 5 PASS (no CAPB, LLM-judgment). Fixes pending: output_is_deliverable + role doc path reference |
