# create_role — Run Verification Catalog

> **Purpose**: Tool-specific post-run verification for `create_role`. Use **together with** the common catalog at `../VERIFICATION_COMMON.md` (covers all observations A1–A15 / O-1 – O-16 that apply to any BTA-based tool).
>
> **Last updated**: 2026-05-21

---

## Tool Profile

| Property | Value |
|----------|-------|
| **Topology** | Single-level BTA — breakdown → workers → aggregator |
| **Breakdown inferencer** | `RovoChat` (template-rendered via `task_breakdown/main/initial.jinja2`) |
| **Worker inferencer**   | `RovoChat` per facet (template-rendered via `deep_research/main/initial.jinja2`) |
| **Aggregator inferencer**| `RovoDevCLI` (template-rendered via `plan/main/initial.jinja2` + `task_instructions/create_role.jinja2`) |
| **Canonical deliverable**| `role_document.md` |
| **Worker artifact**     | `facet.md` |
| **Default `--max-facets`** | 3 (CLI override possible) |
| **Required env**        | `ROVOCHAT_EMAIL`, `ROVOCHAT_API_TOKEN` (or `JIRA_EMAIL`/`JIRA_API_TOKEN` via the test_create_role.sh script) |

---

## How to use

1. Run the tool (e.g., `./test_create_role.sh "hire a machine learning engineer (MLE)"`)
2. Auto-discover latest workspace:
   ```bash
   export TOOL=create_role
   export CANONICAL_DELIVERABLE=role_document.md
   export WS=$(ls -td /Users/tchen7/MyProjects/CoreProjects/OpenTeam/_runtime/tasks/create_role/create_role_* | head -1)
   echo "Auditing: $WS"
   ```
3. Run the **common audit body** (paste from `../VERIFICATION_COMMON.md` §1 one-liner sanity script) — verifies A1–A15
4. Run the **tool-specific audit pack** below (CR-1 – CR-N) — adds create_role-only checks
5. If any check FAILS, consult `../VERIFICATION_COMMON.md` §2 (common observations) FIRST, then §2 below (create_role-specific) — root cause may be tool-agnostic.

---

## §1 create_role-Specific Audit Pack

In addition to common A1–A16, verify:

| #    | Observation                                          | Pass criterion                                                                              | Ref  |
|------|------------------------------------------------------|---------------------------------------------------------------------------------------------|------|
| CR-1 | Canonical role document size + structure             | `$WS/outputs/final_deliverables/role_document.md` exists, >5 KB, has 8+ markdown headings (`grep -c '^#'`) | CR-O-1 |
| CR-2 | Top-level summary naming convention                  | `$WS/outputs/run_summary.md` exists (small ~1–3 KB); NO top-level `$WS/outputs/role_document.md` (only under final_deliverables) | CR-O-2 |
| CR-3 | Facet count matches `--max-facets`                   | Number of `worker_N/` subdirs == `--max-facets` value (default 3); breakdown JSON has exactly that many entries | CR-O-3 |
| CR-4 | Each facet worker produced `facet.md`                | For each `worker_N/`, `worker_N/outputs/facet.md` exists, >1 KB                              | CR-O-4 |
| CR-5 | RovoChat creds resolved                              | Log contains `ConversationCreated: id=<uuid>` for each RovoChat inferencer; no `RovoChatAuthError` | CR-O-5 |
| CR-6 | Aggregator task_instructions use canonical template  | Aggregator `InferenceInput/*.txt` contains canonical section names from `aggregation/create_role.jinja2` ("Domain Operational Artifacts" OR "AI-Specific Work Philosophy" OR "Day-One Readiness") | CR-O-6 |
| CR-7 | No stale ROLE_SYNTHESIS_INSTRUCTIONS constant content | Aggregator `InferenceInput/*.txt` does NOT contain sections from the deleted constant ("Growth Path & Career Development", "Guardrails & Autonomy", "Onboarding Plan" as section 11) | CR-O-7 |

### Quick wrapper

```bash
export TOOL=create_role
export CANONICAL_DELIVERABLE=role_document.md
export WS=$(ls -td /Users/tchen7/MyProjects/CoreProjects/OpenTeam/_runtime/tasks/create_role/create_role_* | head -1)
echo "=== auditing $WS ==="

# Run common audit body (see VERIFICATION_COMMON.md §1 one-liner)
# Then run tool-specifics:

echo "=== CR-1 canonical role document ==="
canonical="$WS/outputs/final_deliverables/role_document.md"
[ -f "$canonical" ] && {
  ls -lh "$canonical"
  echo "  headings: $(grep -c '^#' "$canonical")"
} || echo "FAIL: missing $canonical"

echo "=== CR-2 top-level naming convention ==="
[ -f "$WS/outputs/run_summary.md" ] && echo "OK: run_summary.md present" || echo "WARN: run_summary.md missing"
[ -f "$WS/outputs/role_document.md" ] && echo "WARN: ambiguous: top-level role_document.md present" || echo "OK: no top-level role_document.md"

echo "=== CR-3 facet count ==="
n_workers=$(find "$WS/children" -maxdepth 1 -type d -name "worker_*" | wc -l | tr -d ' ')
echo "  workers spawned: $n_workers"

echo "=== CR-4 worker facet.md presence ==="
for w in $(find "$WS/children" -maxdepth 1 -type d -name "worker_*"); do
  f="$w/outputs/facet.md"
  [ -f "$f" ] && echo "  OK $(basename $w): $(ls -lh "$f" | awk '{print $5}')" || echo "  FAIL $(basename $w): no facet.md"
done

echo "=== CR-5 RovoChat creds ==="
log=$(ls -t "$WS"/../../../create_role_*.log 2>/dev/null | head -1)
[ -f "$log" ] && {
  conv=$(grep -c "ConversationCreated:" "$log")
  err=$(grep -c "RovoChatAuthError" "$log")
  echo "  ConversationCreated count: $conv"
  echo "  RovoChatAuthError count: $err"
} || echo "  WARN: launcher log not found (auto-discovery limited)"

echo "=== CR-6 canonical task_instructions ==="
agg_inp=$(find "$WS" -path "*/aggregator/logs/session/*.jsonl.parts/InferenceInput/*.txt" 2>/dev/null | head -1)
[ -f "$agg_inp" ] && {
  domain=$(grep -c "Domain Operational" "$agg_inp")
  aiphil=$(grep -c "AI-Specific Work Philosophy" "$agg_inp")
  dayone=$(grep -c "Day-One Readiness" "$agg_inp")
  echo "  Domain Operational Artifacts: $domain (want >=1)"
  echo "  AI-Specific Work Philosophy: $aiphil (want >=1)"
  echo "  Day-One Readiness: $dayone (want >=1)"
  [ "$domain" -ge 1 ] || [ "$aiphil" -ge 1 ] || [ "$dayone" -ge 1 ] && echo "  PASS" || echo "  FAIL: canonical sections missing"
} || echo "  SKIP: no aggregator input"

echo "=== CR-7 no stale constant sections ==="
[ -f "$agg_inp" ] && {
  growth=$(grep -c "Growth Path" "$agg_inp")
  guard=$(grep -c "Guardrails & Autonomy" "$agg_inp")
  echo "  Growth Path (stale): $growth (want 0)"
  echo "  Guardrails & Autonomy (stale): $guard (want 0)"
  [ "$growth" -eq 0 ] && [ "$guard" -eq 0 ] && echo "  PASS" || echo "  FAIL: stale constant sections present"
} || echo "  SKIP: no aggregator input"
```

---

## §2 create_role-Specific Observation Catalog

### CR-O-1 — Canonical role document insubstantial
- **Look for**: `$WS/outputs/final_deliverables/role_document.md` exists but <5 KB OR has fewer than 8 markdown headings (indicates placeholder/summary instead of full synthesis)
- **Distinguishes from healthy**: a healthy run produces a 20–40 KB role document with 10+ headings spanning multi-section structure (responsibilities, skills, tools, SOPs, KPIs, etc.)
- **Cross-ref**: this is the create_role-specific size threshold for common O-9

### CR-O-2 — Top-level deliverable name collision
- **Look for**: BOTH `$WS/outputs/role_document.md` AND `$WS/outputs/final_deliverables/role_document.md` exist with different content; OR top-level `$WS/outputs/role_document.md` is a short summary
- **Distinguishes from healthy**: top-level should have `run_summary.md` (the BTA's small summary, ~1–3 KB) as the only top-level deliverable; the canonical role document lives ONLY under `final_deliverables/`
- **Cross-ref**: tool-specific manifestation of common O-10

### CR-O-3 — Facet count mismatch
- **Look for**: Number of `worker_*/` subdirs doesn't equal the `--max-facets` value; OR breakdown JSON has more entries than workers spawned (breakdown JSON should be truncated to max_breakdown by BTA)
- **Distinguishes from healthy**: exactly `--max-facets` workers should spawn, each consuming one entry from the breakdown's JSON array

### CR-O-4 — Worker facet.md missing
- **Look for**: A `worker_N/` subdir exists but `worker_N/outputs/facet.md` does NOT, OR is empty (<1 KB)
- **Distinguishes from healthy**: every spawned worker should produce a `facet.md` (its facet research output) for the aggregator to reference

### CR-O-5 — RovoChat credentials not resolved
- **Look for**: Launcher log contains `RovoChatAuthError` OR no `ConversationCreated: id=` lines appear at all
- **Distinguishes from healthy**: each RovoChat inferencer (breakdown + per-worker) should log `ConversationCreated: id=<uuid>` once before its first inference
- **Bonus signal**: For the bash script, this most often indicates missing/wrong `ROVOCHAT_EMAIL`/`ROVOCHAT_API_TOKEN` env vars

### CR-O-6 — Aggregator task_instructions missing canonical sections
- **Look for**: aggregator's `InferenceInput/*.txt` does NOT contain section names from the canonical `plan/main/_variables/task_instructions/aggregation/create_role.jinja2` template — specifically "Domain Operational Artifacts", "AI-Specific Work Philosophy", or "Day-One Readiness". Instead it may contain generic aggregation instructions or stale constant content.
- **Distinguishes from healthy**: a healthy run's aggregator input contains the full 11-section role document structure from the canonical template file. Missing canonical sections indicates the aggregator resolved `task_instructions` from a fallback (generic `aggregation/default.jinja2`) or a stale hardcoded constant instead of the role-specific `aggregation/create_role.jinja2`.
- **Root cause history**: the original `ROLE_SYNTHESIS_INSTRUCTIONS` constant (deleted 2026-05-23) diverged from the canonical template file after the template was updated with new sections on 2026-04-27. The constant had old sections (#8 Guardrails & Autonomy, #10 Growth Path, #11 Onboarding Plan) while the canonical file had evolved to (#4 Domain Operational Artifacts, #10 AI-Specific Work Philosophy, #11 Day-One Readiness).

### CR-O-7 — Stale ROLE_SYNTHESIS_INSTRUCTIONS constant content detected
- **Look for**: aggregator's `InferenceInput/*.txt` contains section names that existed ONLY in the deleted `ROLE_SYNTHESIS_INSTRUCTIONS` constant — specifically "Growth Path & Career Development" or "Guardrails & Autonomy" as standalone sections. These sections were replaced in the canonical template but persisted in the hardcoded constant.
- **Distinguishes from healthy**: a healthy run uses the canonical template file (via `template_variables={"task_instructions": "create_role"}` with `master_version="aggregation"`), which never contains these stale section names. Their presence means the executor is injecting a hardcoded constant instead of resolving from the template system.
- **If detected**: check whether `ROLE_SYNTHESIS_INSTRUCTIONS` (or similar large prompt constant) has been reintroduced in `create_role/executor.py`. The canonical source of truth is `plan/main/_variables/task_instructions/aggregation/create_role.jinja2`.

---

## §3 Run Comparison — Historical Baselines

| Run ID                       | Date              | Status      | Notes                                                       |
|------------------------------|-------------------|-------------|-------------------------------------------------------------|
| `create_role_*_159d8dda`     | 2026-05-18 16:46  | ⚠️ partial  | Aggregator gold-quality but failed O-9, O-10 (pre-surfacing-fix)|
| `create_role_*_5255d7cb`     | 2026-05-18 20:34  | ✅ baseline | First run with surfacing fix in place                       |
| `create_role_20260520_170707_b898e8ea` | 2026-05-20 17:07 | ✅ baseline | All A1–A15 + CR-1–CR-5 pass |
| `create_role_20260521_025236_*`        | 2026-05-21 02:52 | 🔄          | Post-consolidation run (pending audit)                      |
| `create_role_20260521_181230_29041e31` | 2026-05-21 18:12 | ❌ A14a     | A14a regression confirmed: 0 `(See file:)`, no aggregation preamble, 130 lines |
| `create_role_20260523_203617_b3e6c971` | 2026-05-23 20:36 | ✅ baseline | **A14a FIXED**: A1-A16 + CR-1-CR-7 all pass. FileSpaceManager + master_version + wrapper recomposition + centralized template roots. |

> Add new rows after each notable run. Use `task_id` from workspace name (last 8 chars) for fast lookup.
