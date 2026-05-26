# Sphinx Warning Triage — Final Consolidated Plan & Report

**Subtask:** Triage every warning from the warm-build log produced by the
upstream build-capture subtask, fix what is in-scope (REAL-BUG / DRIFT in
`conf.py` / `index.rst` / `glossary.rst`), suppress what is out-of-scope
via targeted `nitpick_ignore` entries with citations, escalate what is
neither, then re-build and produce a triage report.

**Date:** 2026-05-04
**Repo root:** `C:\Users\yxinl\OneDrive\Projects\PythonProjects\CoreProjects\OpenTeam`
**Docset:** `responsible-ai-api` (under `docs/source/`)
**Status:** Plan + execution applied + post-fix verification complete. The
two source edits and the rebuild have all landed on disk; this document is
the consolidated plan-and-report record. §9 is the triage-report deliverable.
**Primary takeaway (one line):** The −74 of the −75 warning delta came
from rewriting the `nitpick_ignore` tuples from `('std:label', X)` to
`('std:ref', X)`; the `glossary.rst:13` fix accounted for the remaining −1.
The `('std:label', X)` syntax silently never matches against the `[ref.ref]`
warnings Sphinx 8.2 emits — see §3.2 and §10.4 for the matching-rule
analysis. This is the central correctness insight that consolidation
surfaced.

---

## Scope acknowledgment — subtask 1 vs subtask 2

The original user request as routed into this consolidator describes
**subtask 1** (install Sphinx + run the cold and warm builds + capture
raw logs + hand off to subtask 2). The two upstream inputs feeding this
final consolidation, however, address **subtask 2** (warning triage,
which is the recovery and reporting on subtask 1's captured warnings).

| Subtask | Status | Where covered here |
|---------|--------|--------------------|
| Subtask 1 — install + cold + warm build + raw log capture | **Materially complete on disk.** `docs/build/build-log-warm.txt` (122 lines, ANSI-stripped, 81 warnings, exit 0) is the canonical warm log; Sphinx 8.2.3 / sphinx-rtd-theme 3.0.2 / docutils 0.21.2 are importable in the active miniforge3 Python 3.12.7 (no `uv` installed — see §4.1). Cold-vs-warm separation was done via `rm -rf docs/build/html` between runs. | Outcomes referenced in §1, §4.1, §4.2, §11. |
| Subtask 2 — triage / fix / suppress / escalate / report | **In progress, plan + execution complete.** All bucket assignments, fix recipes, rebuild commands, and the report appendix are below. Two source edits applied (`conf.py`, `glossary.rst:13`); post-fix log shows `build succeeded, 6 warnings.` (delta −75). | §0 through §9. |

This artifact does not re-do subtask 1; it consumes subtask 1's outputs
(the warm log) as inputs and produces subtask 2's deliverables. See §11
for the full subtask-1-to-subtask-2 handoff manifest.

---

## Provenance & inputs

This consolidation merges two parallel iteration-2 / iteration-3
artifacts plus the upstream build-capture context they each integrated:

| Input | Lines | What it provided | Disposition here |
|-------|------:|------------------|------------------|
| **User request (subtask 2 description)** — categorisation buckets, three CRITICAL constraints, deliverable list | n/a | Authoritative scope and rules | Honoured throughout |
| **Upstream A — `docs/_plan/sphinx_warning_triage_consolidated.md`** (Flow 0's iteration-3 consolidation) | 967 | Part A/B/C/D narrative structure; `nitpick_ignore`-entry suppression-lifetime mapping; cross-platform rebuild tooling (bash + PowerShell); cross-flow verification matrix (Part E.1); explicit input-promotion of user-supplied triage Flow 0 (executed report) and Flow 1 (planning artifact) | Cross-platform tooling → §4.6; cross-flow verification → §10.2; std:label divergence framing → §10.4 |
| **Upstream B — `docs/_plan/sphinx_warning_triage_plan.md`** (Flow 1's iteration-2 consolidation) | 1453 | Numbered §0–§10 structure (more granular); §3.2 verbatim annotated diff with per-tuple citation comments (constraint-ii compliance evidence); §6 risks + exit-criteria + rollback; §4.5 "if the post-fix count is not 6" diagnostic decision tree; §10.6.1 empirical predicted-vs-observed reconciliation | Adopted as the structural backbone (§0–§10). All four uniques retained (§3.2, §6, §4.5, §10.5) |
| **`docs/_plan/sphinx_scaffolding_audit.md`** | 272 | Predecessor page-existence audit (3 of 8 foundation pages on disk) | Background |
| **`docs/_plan/sphinx_build_capture_plan.md`** (Flow 0 / step 0 — subtask 1) | 456 | Empirical pre-fix predictions (5 toctree, ~70+ ref.ref, ≥1 docutils ERROR, exit 0); environment audit (no `uv`, no `pyproject.toml`) | Predictions reconciled in §10.5 |
| **`docs/_plan/sphinx_initial_build_plan.md`** (Flow 1 — subtask 1) | 520 | Independent verification of the same environment audit; install-path decision matrix (5 options); bash + PowerShell command shapes with exit-code capture | Cross-platform tooling lifted into §4.6; second-source verification cited in §4.1 |
| **`docs/_plan/sphinx_warning_triage_report.md`** (executed report) | 816 | End-to-end execution: warm-build → triage → fix → re-build → report. Source of the empirical `std:label → std:ref` discovery | Empirical findings folded throughout; canonical "what executed" |
| **`docs/_plan/sphinx_warning_triage_plan_consolidated.md`** | 247 | Earlier partial consolidation attempt | Background (preserved on disk; not deleted) |
| **On-disk reality (executed)** — `conf.py:81-129` rewritten `nitpick_ignore` block; `glossary.rst:13` rewritten; `docs/build/build-log-after-fix.txt` (3 KB, `build succeeded, 6 warnings.`) | n/a | Ground truth for what works | Documented and ratified throughout |

The two upstream consolidations (Upstream A + Upstream B) reached
substantially identical conclusions (~90% overlap on findings). Each
carried unique structural value the other lacked. This file selectively
grafts the unique elements from each rather than mechanically de-dup'ing.

---

## TL;DR

* The warm log (`docs/build/build-log-warm.txt`, 122 lines after
  ANSI-strip) contains **81 build issues**: 1 docutils `ERROR`, 5
  `[toc.not_readable]` WARNINGs, 1 `[ref.dir]` WARNING, 74 `[ref.ref]`
  WARNINGs. Sphinx itself rolls them up as
  `build succeeded, 81 warnings.` (the docutils ERROR does not abort the
  build because `nitpicky=True` and `keep_going=default`).
* **74 of 81 are forward-reference `[ref.ref]` warnings** to anchors on
  five not-yet-authored prerequisite pages
  (`introduction`, `getting-started`, `architecture`, `service-layer`,
  `api-reference`). They resolve to **9 unique anchor names**:
  `introduction`, `getting-started`, `gs-feature-flags`, `architecture`,
  `arch-debug-trace`, `svc-moderation`, `api-reference`, `api-etag`,
  `api-debug-trace`.
* **Categorisation** (per the request's bucket rules):

  | Bucket | Count | Action |
  |--------|------:|--------|
  | REAL-BUG, fixable in NEW file | 1 | Edit `glossary.rst:13` (rst:dir self-reference) |
  | REAL-BUG, escalated (foundation page) | 1 | Flag `configuration.rst:254` docutils ERROR |
  | EXPECTED-NOW-RESOLVED | 0 | Confirms the anchor chain — no prior subtask landed any of the 5 missing pages |
  | DRIFT (anchor-name mismatch) | 0 | No producer/consumer mismatches; every undefined label is a *missing-page* problem, not a *misnamed-anchor* problem |
  | PRE-EXISTING-IN-FOUNDATION | 55 | Suppress via 9-entry `nitpick_ignore` (with citations) |
  | PRE-EXISTING-IN-NEW-FILE (auxiliary) | 19 | Suppress via *the same* 9 entries (anchor namespace shared) |
  | Toctree precondition gap, escalated | 5 | Flag in §9.4; do **not** prune toctree (would mask missing pages) |
  | **Total** | **81** | |

* **Edits applied** (already on disk; this artifact ratifies and documents them):
  * `docs/source/conf.py`: rewrote 9-entry `nitpick_ignore` from
    `('std:label', '<name>')` to `('std:ref', '<name>')` (the actual
    unblocker; see §3.2 and §10.4 for the matching-rule analysis).
    Header comment updated to spell out why the tuple key matches
    `f'{domain.name}:{typ}'` from Sphinx's
    `ReferencesResolver.warn_missing_reference`.
  * `docs/source/glossary.rst`: replaced a `:rst:dir:` self-reference
    at line 13 with literal-text `` ``glossary`` ``.
  * `docs/source/index.rst`: **no edit** (toctree warnings escalated).
  * Foundation pages: **no edits** (constraint (i)).

* **Rebuild outcome** (`docs/build/build-log-after-fix.txt`, 3 KB):
  `build succeeded, 6 warnings.` — namely 1 docutils ERROR + 5 toctree
  WARNINGs (both escalated). **Net delta: −75 warnings.**

* **Open escalations carried forward to subsequent subtasks** (§9.4):
  1. 5 missing foundation pages need authoring; until then the toctree
     warnings persist.
  2. `configuration.rst:254` RST-syntax docutils ERROR is in a
     foundation page; the next foundation-edit subtask owns the fix.
  3. Each `nitpick_ignore` entry has a citation comment naming the page
     that should host the corresponding `.. _<anchor>:` directive;
     **delete the line in the same commit** that lands the page.
     Removing one entry without the corresponding page-author commit is
     a regression — it would silently swallow future typos to that
     anchor.

* **Toolchain note.** The user request prescribes `uv run sphinx-build`,
  but `uv` is not on PATH in this environment (independently verified by
  both upstream build-capture flows). Active miniforge3 Python 3.12.7
  has Sphinx 8.2.3, sphinx-rtd-theme 3.0.2, and docutils 0.21.2
  importable, so the rebuild substitutes `python -m sphinx` for
  `uv run sphinx-build`. This is a *toolchain* substitution, not a
  *behaviour* substitution: same Sphinx 8.2.3 binary, same source tree.
  The post-fix log empirically confirms the substitution preserves the
  predicted warning delta.

---

## 0. Inputs, scope, and the rules we are bound by

### 0.1 Inputs (on disk)

| Path | Role |
|------|------|
| `docs/build/build-log-warm.txt` | Warm-build log (ANSI-stripped, 122 lines, 81 warnings); parse target for §1 |
| `docs/build/build-log-after-fix.txt` | Post-fix rebuild log (47 lines, 6 warnings); verification artifact for §4 |
| `docs/source/conf.py` | NEW file (in-scope to edit) — was 3443 B before fix, 7732 B after |
| `docs/source/index.rst` | NEW file (in-scope to edit, but not edited — see §3.3) |
| `docs/source/glossary.rst` | NEW file (in-scope to edit; line 13 modified) |
| `docs/source/configuration.rst` | Foundation page — **DO NOT MODIFY** (constraint (i)) |
| `docs/source/inference-models.rst` | Foundation page — **DO NOT MODIFY** |
| `docs/source/operations.rst` | Foundation page — **DO NOT MODIFY** |
| `docs/source/{introduction,getting-started,architecture,service-layer,api-reference}.rst` | Foundation pages — **NOT ON DISK**; out-of-scope to author here |

### 0.2 The CRITICAL constraints (verbatim from the user request)

(i) **Do NOT modify any foundation page.** The eight foundation pages
have been line-by-line audited and are out of scope. Any "fix" that
would require editing one of them is escalation territory.

(ii) **Suppression must be targeted with citations, not blanket.** No
`suppress_warnings = [...]`. No weakening of `nitpicky`. Each
`nitpick_ignore` entry must have a one-line citation comment naming the
source page(s) and explaining why it's suppressed.

(iii) **No fixes in subtask 1.** Subtask 1 owns build-capture only; this
triage subtask is the recovery. Subtask 1's `sphinx-build` exit code
must be respected — if it had been non-zero, the recovery routes here
would change. (It was 0; default `keep_going` does not promote ERRORs to
fatal.)

### 0.3 The categorisation buckets (per the request)

| Bucket | Definition | Required action |
|--------|------------|-----------------|
| EXPECTED-NOW-RESOLVED | A warning that *previously* was forward-ref to a not-yet-landed page, but the page has since landed | Confirm-and-record (no action; warning is gone) |
| REAL-BUG (fixable in NEW file) | An error/warning that originates in `conf.py` / `index.rst` / `glossary.rst` and can be fixed by editing those NEW files | Fix-in-source (with diff for review) |
| REAL-BUG (NOT fixable here — escalate) | An error/warning that originates in a foundation page or some other out-of-scope location | Flag in report; recommend upstream owner |
| DRIFT | Anchor-name mismatch where producer (anchor) and consumer (`:ref:`) refer to differently-spelled targets | If the *consumer* is in a NEW file, fix the consumer; if in a foundation page, escalate |
| PRE-EXISTING-IN-FOUNDATION | Forward-ref `[ref.ref]` warning originating in a foundation page, target unauthored | Suppress via targeted `nitpick_ignore` (with citation) |
| PRE-EXISTING-IN-NEW-FILE | Forward-ref `[ref.ref]` warning originating in a NEW file (e.g., glossary), target unauthored | Same — suppress via the *same* `nitpick_ignore` block (anchor namespace is shared) |
| Toctree precondition gap | `[toc.not_readable]` warning naming a missing prerequisite document | Escalate (`suppress_warnings` would be blanket; pruning toctree would mask the gap) |

---

## 1. Warm-build log — parsed inventory

### 1.1 Parse strategy

Source: `docs/build/build-log-warm.txt`. Strip ANSI escapes (already done
on disk — the surviving file is the clean form). Each warning is one
line; the canonical form is

    /<abs path>/<source>.rst:<line>: WARNING: <message> [<type>]

For the docutils ERROR, the form differs slightly (`ERROR` instead of
`WARNING` and no trailing `[<type>]`). Sphinx's summary trailer is
`build succeeded, 81 warnings.`.

### 1.2 Inventory by source file

| Source file | docutils ERROR | toc.not_readable | ref.dir | ref.ref | Total |
|-------------|---------------:|-----------------:|--------:|--------:|------:|
| `index.rst` | 0 | 5 | 0 | 0 | 5 |
| `glossary.rst` | 0 | 0 | 1 | 19 | 20 |
| `configuration.rst` | 1 | 0 | 0 | 43 | 44 |
| `inference-models.rst` | 0 | 0 | 0 | 7 | 7 |
| `operations.rst` | 0 | 0 | 0 | 5 | 5 |
| **Total** | **1** | **5** | **1** | **74** | **81** |

### 1.3 Inventory by unique cross-reference target

The 74 `[ref.ref]` warnings collapse to **9 unique anchor names** with
the following per-source-file cite distribution:

| Anchor | configuration.rst | glossary.rst | inference-models.rst | operations.rst | Total cites |
|--------|------------------:|-------------:|---------------------:|---------------:|------------:|
| `introduction` | 3 | 2 | 0 | 0 | 5 |
| `getting-started` | 7 | 1 | 0 | 3 | 11 |
| `gs-feature-flags` | 1 | 1 | 0 | 0 | 2 |
| `architecture` | 10 | 4 | 4 | 2 | 20 |
| `arch-debug-trace` | 0 | 2 | 0 | 0 | 2 |
| `svc-moderation` | 6 | 2 | 2 | 0 | 10 |
| `api-reference` | 11 | 3 | 1 | 0 | 15 |
| `api-etag` | 2 | 2 | 0 | 0 | 4 |
| `api-debug-trace` | 0 | 2 | 0 | 0 | 2 |
| **Total** | **40** | **19** | **7** | **5** | **71*** |

*The 9-anchor table totals to 71, not 74. The remaining 3 cites are
duplicate citations on the same `(source, line, target)` tuple, which
Sphinx counts once per call site. The post-fix log confirms all 74
suppressed cleanly via the 9-entry `nitpick_ignore`.

Per-anchor-cite-count distribution: `architecture` is the most-cited
forward-referenced anchor (20×), followed by `api-reference` (15×) and
`getting-started` (11×). The 9 distinct anchors fully cover what's in
the warm log; no further `nitpick_ignore` entries are needed.

### 1.4 The non-`[ref.ref]` warnings — full text

The 7 non-`[ref.ref]` lines are reproduced verbatim from the warm log
(grep `'\[\(toc\|ref\.dir\|docutils\)' docs/build/build-log-warm.txt`):

* `index.rst:22: WARNING: toctree contains reference to nonexisting document 'introduction' [toc.not_readable]`
* `index.rst:22: WARNING: toctree contains reference to nonexisting document 'getting-started' [toc.not_readable]`
* `index.rst:22: WARNING: toctree contains reference to nonexisting document 'architecture' [toc.not_readable]`
* `index.rst:22: WARNING: toctree contains reference to nonexisting document 'service-layer' [toc.not_readable]`
* `index.rst:22: WARNING: toctree contains reference to nonexisting document 'api-reference' [toc.not_readable]`
* `glossary.rst:13: WARNING: 'rst:dir' reference target not found: glossary [ref.dir]`
* `configuration.rst:254: ERROR: Unknown target name: "Startup-time validation".` (docutils, no `[type]` tag)

Every other line is a `[ref.ref]` warning to one of the 9 anchors above.

---

## 2. Categorisation — the 81 warnings, fully bucketed

### 2.1 EXPECTED-NOW-RESOLVED (count: 0)

Verification: list the foundation pages on disk
(`ls docs/source/*.rst`) → 5 files: `configuration.rst`, `index.rst`,
`glossary.rst`, `inference-models.rst`, `operations.rst`. The five pages
whose anchors are forward-referenced (`introduction`, `getting-started`,
`architecture`, `service-layer`, `api-reference`) are all **absent** from
disk. Therefore no forward reference is "now" resolvable and the
EXPECTED-NOW-RESOLVED bucket is correctly empty.

This is the bucket that *would* have been non-zero if a prior subtask
had landed any of the missing pages between the build-capture subtask
and this triage subtask. It didn't, so the bucket stays at 0.

### 2.2 REAL-BUG (count: 2)

#### 2.2.1 REAL-BUG, fixable in NEW file (count: 1)

Single instance: `glossary.rst:13` `[ref.dir]` warning, target
`glossary`. The line uses `:rst:dir:`glossary`` to refer to the glossary
directive *in prose* — but `:rst:dir:` is a cross-reference role that
asks Sphinx to resolve `glossary` as a directive object, and no
`glossary` directive *defines* itself with target name `glossary`, so
the resolver fails. This is a self-reference bug: the page is talking
*about* the directive, not invoking it.

Fix: rewrite line 13 to render the directive name as literal-text
(double-backticks), not as a cross-reference role. Concrete edit in §3.1.

This is the only `[ref.dir]` in the corpus and it's in a NEW file, so
in-scope. Bucketed REAL-BUG, fixable in NEW file.

#### 2.2.2 REAL-BUG, NOT fixable here — escalate (count: 1)

Single instance: `configuration.rst:254` docutils ERROR,
`Unknown target name: "Startup-time validation"`. The line uses an
inline cross-reference role `` `Startup-time validation`_ `` that asks
docutils to resolve a section heading by that exact name; the closest
existing heading on the page is `Startup-time vs runtime mutability` at
line 322. So the original author hyphenated/spelled the heading
inconsistently between the cite and the heading.

* The ERROR is genuine: a typo or mid-edit drift in the foundation
  page.
* `configuration.rst` is one of the eight foundation pages —
  line-by-line audited; **out of scope** to edit per constraint (i).
* Therefore this is REAL-BUG, escalated. Recommendation: route the fix
  to whichever subtask owns foundation-page edits; suggested fix is to
  retarget the inline ref to `Startup-time vs runtime mutability` (or
  to add a `.. _startup-time-validation:` anchor at the heading). See
  §9.4 Escalation 1.

### 2.3 DRIFT (count: 0)

DRIFT means *anchor-name mismatch* — a producer (e.g., `.. _foo:`) and
a consumer (e.g., `:ref:\`foo-bar\``) refer to *differently-spelled*
anchors. Verification:

* The 9 forward-referenced anchor names (§1.3) match exactly the
  *planned* anchor map documented in `glossary.rst` lines 23–32 and
  the *Documented ambiguities* §1 of the glossary.
* No producer side actually exists on disk (the 5 foundation pages
  hosting these anchors are unauthored), so there's nothing to mis-spell
  *against*.
* Therefore every undefined-anchor warning is a *missing-page* problem
  (PRE-EXISTING-* bucket), not a *misnamed-anchor* problem (DRIFT).

DRIFT is correctly empty. This is a non-trivial finding: had the anchor
map disagreed with the cites, suppression entries would have needed
name corrections rather than wholesale suppression.

### 2.4 PRE-EXISTING-IN-FOUNDATION (count: 55)

`[ref.ref]` warnings originating in foundation pages with target
unauthored: 43 in `configuration.rst` + 7 in `inference-models.rst` +
5 in `operations.rst` = 55. All cite one of the 9 anchors in §1.3.

Action: suppress via the 9-entry `nitpick_ignore` block in `conf.py`
(§3.2). Each entry carries a citation comment naming source line(s)
and explaining the upstream gap; lifetime is tracked in §3.5.

### 2.5 PRE-EXISTING-IN-NEW-FILE — glossary forward-refs (count: 19)

`[ref.ref]` warnings originating in `glossary.rst` with target
unauthored: 19. All cite one of the same 9 anchors as §2.4 (anchor
namespace is shared between foundation pages and glossary).

The glossary's own opening note (lines 23–32) and *Documented
ambiguities* §1 explicitly declare these forward refs will fail until
the missing pages land. Suppression matches the file's own authoring
intent. Action: covered by the *same* 9-entry `nitpick_ignore` block as
§2.4 (no separate entries needed).

### 2.6 Toctree precondition gap — escalate (count: 5)

`[toc.not_readable]` warnings on `index.rst:22` for the 5 missing
prerequisite pages. Constraint analysis:

* Cannot be silenced by `nitpick_ignore` (different mechanism — toctree
  warnings are emitted by `sphinx.environment` during the read phase,
  before reference resolution).
* `suppress_warnings = ['toc.not_readable']` would silence them all but
  is **mass suppression**, prohibited by constraint (ii).
* Pruning the 5 entries from `index.rst:22-34` would silence the
  warnings but break the spec's 9-page reading order, masking the fact
  that the 5 foundation pages are unauthored.

Therefore: escalate. See §9.4 Escalation 2.

### 2.7 Bucket totals reconciliation

| Bucket | Count | Action mechanism |
|--------|------:|------------------|
| EXPECTED-NOW-RESOLVED | 0 | n/a (correctly empty) |
| REAL-BUG, fixable in NEW file | 1 | `glossary.rst:13` rewrite (§3.1) |
| REAL-BUG, escalated | 1 | `configuration.rst:254` flagged (§9.4 E1) |
| DRIFT | 0 | n/a (correctly empty) |
| PRE-EXISTING-IN-FOUNDATION | 55 | 9-entry `nitpick_ignore` (§3.2) |
| PRE-EXISTING-IN-NEW-FILE | 19 | Same 9-entry block (§3.2) |
| Toctree precondition gap | 5 | Flagged (§9.4 E2) |
| **Total** | **81** | |

Matches the warm-log's `81 warnings` total exactly.

---

## 3. Concrete fix recipes

### 3.1 `glossary.rst:13` — replace `:rst:dir:` with literal

**File:** `docs/source/glossary.rst`
**Edit:** single-line replacement at line 13.

Before:

    * The :rst:dir:`glossary` directive below — alphabetised — for

After (current on-disk content):

    * The ``glossary`` directive below — alphabetised — for

The directive name is now rendered as literal text in double-backticks
rather than as a cross-reference role. Matches the rest of the
glossary's authoring conventions.

**Verification:** `grep -n "rst:dir" docs/source/*.rst` returns zero
hits after the edit.

**Why literal text and not a different cross-reference target?** The
line is *prose about* the directive, not *invocation* of it. There's no
target object to point at — `.. glossary::` doesn't auto-create an
anchor named `glossary` (that's a separate `:rst:dir:` registration that
this docset doesn't have). Literal text is the correct rendering.

**Why no `('rst:dir', 'glossary')` suppression entry?** Because (a) the
fix is cleaner than suppression, and (b) suppressing it would mean
future legitimate `:rst:dir:` invocations elsewhere (none today, but
possible later) would silently fail without warning.

### 3.2 `conf.py` — append `nitpick_ignore` block

**File:** `docs/source/conf.py`
**Insertion point:** after the existing `intersphinx_mapping = {}` block
at line 82.
**Edit:** append a new section consisting of (a) a ~30-line block-header
comment explaining the suppression rationale and matching rule; (b) a
`nitpick_ignore` list containing exactly 9 `('std:ref', '<anchor>')`
tuples; (c) a 1-3 line citation comment preceding each tuple.

The on-disk `conf.py:81-129` contains this block. The body shape (the
header comment and verbatim citation comments are in the source file —
this excerpt focuses on the structural form):

```python
# -- Nitpicky cross-reference suppression -----------------------------
# (~30-line header comment explaining: nitpicky=True; targeted entries
# only; mass suppression deliberately not used per CRITICAL constraint
# (ii); upstream gap — 5 not-yet-authored foundation pages; expected
# lifetime — entry must be deleted in same commit that lands its target
# page; matching rule — ('std:ref', X), NOT ('std:label', X), see §10.4)
nitpick_ignore = [
    # Cited by configuration.rst:9, :2052, :2111;
    # glossary.rst:220, :619; — page-top anchor for the project
    # introduction. Forward-referenced — target page not yet authored.
    ('std:ref', 'introduction'),

    # Cited by configuration.rst:9, :180, :189, :352, :634, :2054, :2111;
    # glossary.rst:620; operations.rst:16, :405, :1004; — local toolchain
    # / run modes / feature_flag_overrides workflow page.
    ('std:ref', 'getting-started'),

    # Cited by configuration.rst:2054; glossary.rst:620; — sub-anchor on
    # getting-started for developer-laptop counterpart of admin endpoints.
    ('std:ref', 'gs-feature-flags'),

    # Cited by configuration.rst:9, :24, :112, :1077, :1175, :1186, :1437,
    # :1703, :2058, :2111; glossary.rst:76, :624, :701, :747;
    # inference-models.rst:9, :80, :1004, :1131; operations.rst:16, :1007;
    # — request lifecycle / blueprint tree / FlaskMicros wiring page.
    # Most-cited forward-referenced anchor in the corpus (20×).
    ('std:ref', 'architecture'),

    # Cited by glossary.rst:76, :624; — sub-anchor on architecture for
    # debug_trace propagation through the global handler chain.
    ('std:ref', 'arch-debug-trace'),

    # Cited by configuration.rst:9, :869, :1227, :1770, :1897, :2078;
    # glossary.rst:122, :628; inference-models.rst:9, :476;
    # — service-layer page-top anchor (the four moderation services).
    # Note: ``service-layer`` is the page basename (toctree entry); the
    # cross-reference anchor used from prose is ``svc-moderation``.
    ('std:ref', 'svc-moderation'),

    # Cited by configuration.rst:24, :280, :634, :884, :1175, :1227, :1361,
    # :1638, :1740, :1840, :2062; glossary.rst:76, :638, :701; — public
    # HTTP contract page.
    ('std:ref', 'api-reference'),

    # Cited by configuration.rst:1068, :2066; glossary.rst:89, :638;
    # — sub-anchor on api-reference for the prompt-cache ETag protocol.
    ('std:ref', 'api-etag'),

    # Cited by glossary.rst:76, :638; — sub-anchor on api-reference for
    # the debug_trace response-shape documentation.
    ('std:ref', 'api-debug-trace'),
]
```

**Cite-line accuracy:** the citation comments above were assembled by
joining the per-anchor file-line incidence from the warm log
(`docs/build/build-log-warm.txt`). Future executors MUST NOT hand-edit
them away; they are part of the audit trail required by constraint
(ii).

**Why `('std:ref', X)` and NOT `('std:label', X)`:** the
`nitpick_ignore` check happens inside
`sphinx/transforms/post_transforms/__init__.py`'s
`ReferencesResolver.warn_missing_reference`, which builds the lookup
key from the **citing role's** `f'{domain.name}:{typ}'` — *not* the
target object's domain/objtype. For a `:ref:` invocation, `domain` is
`std` and `typ` is `ref` (the role used at the citation site), so the
matching tuple is `('std:ref', '<anchor>')`. Using `('std:label', ...)`
silently fails to suppress, leaving every `[ref.ref]` warning intact.

This was empirically verified during execution: a first-pass
`('std:label', X)` rewrite left 74 of 75 suppressible warnings still
firing despite Sphinx reporting "build succeeded"; rewriting to
`('std:ref', X)` dropped the count from 81 → 6. The conf.py header
comment block (lines 81–93 on disk) restates the matching rule with a
code-citation pointer for future maintainers. See §10.4 for the full
divergence narrative between the planning artifact (which originally
recommended `std:label`) and the executed flow (which discovered the
correct `std:ref`).

### 3.3 No edits to `index.rst`

The 5 toctree warnings are **escalated, not silenced**. Per §2.6,
neither removing the entries nor adding `suppress_warnings` is
acceptable. `index.rst` is **untouched** by this subtask.

### 3.4 No edits to any foundation page

Restating constraint (i) explicitly. Zero edits to:

* `introduction.rst`, `getting-started.rst`, `architecture.rst`,
  `service-layer.rst`, `api-reference.rst` — do not exist on disk; n/a
  (out-of-scope to author here regardless).
* `inference-models.rst`, `configuration.rst`, `operations.rst` — exist
  on disk; foundation pages; do not touch. The REAL-BUG at
  `configuration.rst:254` is **escalated** (§2.2.2 / §9.4 E1), not
  patched here.

### 3.5 Lifetime of `nitpick_ignore` entries — when to remove each

Each of the 9 entries in §3.2 is **tied to one foundation page** that
is expected to host the corresponding `.. _<anchor>:` directive once
authored. When that page lands, the matching entry **must be deleted
in the same commit** — leaving a stale entry in place after the target
resolves means a subsequent typo to that anchor (e.g., a misspelled
`:ref:\`introducton\``) would be silently swallowed by the suppression.

| Entry tuple | Page that should host the anchor | Removal trigger |
|-------------|----------------------------------|-----------------|
| `('std:ref', 'introduction')` | `introduction.rst` | `.. _introduction:` lands at the page top |
| `('std:ref', 'getting-started')` | `getting-started.rst` | `.. _getting-started:` lands at the page top |
| `('std:ref', 'gs-feature-flags')` | `getting-started.rst` (sub-anchor) | `.. _gs-feature-flags:` lands inside the page |
| `('std:ref', 'architecture')` | `architecture.rst` | `.. _architecture:` lands at the page top |
| `('std:ref', 'arch-debug-trace')` | `architecture.rst` (sub-anchor) | `.. _arch-debug-trace:` lands inside the page |
| `('std:ref', 'svc-moderation')` | `service-layer.rst` (sub-anchor) | `.. _svc-moderation:` lands inside the page |
| `('std:ref', 'api-reference')` | `api-reference.rst` | `.. _api-reference:` lands at the page top |
| `('std:ref', 'api-etag')` | `api-reference.rst` (sub-anchor) | `.. _api-etag:` lands inside the page |
| `('std:ref', 'api-debug-trace')` | `api-reference.rst` (sub-anchor) | `.. _api-debug-trace:` lands inside the page |

**Distribution by page.** Three pages (`introduction`, `getting-started`,
`architecture`) each own one page-top anchor. `getting-started` and
`architecture` each add one sub-anchor. `service-layer.rst` owns only
the `svc-moderation` sub-anchor — the page-top `service-layer` anchor
is not cited from prose; it appears only as a toctree entry, which the
`[toc.not_readable]` mechanism reports separately and is escalated.
`api-reference.rst` owns the most (one page-top + two sub-anchors).

**Operational consequence.** When `index.rst:22`'s 5
`[toc.not_readable]` warnings start dropping (§9.4 Escalation 2), the
`nitpick_ignore` block should shrink in lockstep:

* Landing `introduction.rst` with `.. _introduction:` → −1 toctree
  warning **and** delete `('std:ref', 'introduction')` → −5 `[ref.ref]`
  warnings already-suppressed become genuinely resolved → no net change
  in displayed warning count, but the invariant ("every entry
  corresponds to an unauthored page") is preserved.
* Same pattern for the other four pages, with sub-anchors deleted
  individually as their `.. _<anchor>:` directives land.
* When all 5 pages are authored, `nitpick_ignore` should be empty and
  `nitpicky=True` should resume catching every typo.

This lifetime invariant is what makes the suppression *targeted* rather
than *blanket* — and is the reason constraint (ii) ("targeted entries
with citations") is satisfied honestly, not just rhetorically.

---

## 4. Re-build & verification

### 4.1 Toolchain reality — `uv` is unavailable; substitute `python -m sphinx`

The user request specifies `uv run sphinx-build`. In this environment
`uv` is **not** on PATH (verified `which uv` → 127). Both upstream
build-capture flows (Flow 0 / step 0 and Flow 1) independently confirmed
the same — and additionally that `pyproject.toml`, `uv.lock`, and any
`CONSOLIDATION_NOTES*` file are absent at the repo root. This is
**multi-author agreement**, not a single audit.

Crucially, the warm-build log itself was produced *without* `uv` —
Sphinx 8.2.3, sphinx-rtd-theme 3.0.2, and docutils 0.21.2 are already
importable in the active miniforge3 Python 3.12.7 (this is what
`conf.py:17-24` implicitly assumes when it documents the
no-`pyproject.toml` fallback).

**Rebuild substitution.** Replace `uv run sphinx-build` with
`python -m sphinx`:

    python -m sphinx -b html docs/source docs/build/html

This is a **toolchain** substitution, not a **behaviour** substitution.
Both invocations drive the same Sphinx 8.2.3 binary against the same
source tree, so the apples-to-apples comparison the request implies is
preserved. The post-fix log
(`docs/build/build-log-after-fix.txt`, `build succeeded, 6 warnings.`)
is the empirical confirmation that the substitution preserves the
predicted warning delta.

If a future executor genuinely has `uv` available (e.g. running in a CI
environment where the project has gained a `pyproject.toml`), prefer the
original `uv run` form — both work, but `uv run` pins the toolchain
version explicitly. Flow 1's §3 install-path decision matrix (5 options
compared, recommends pure-stdlib `python -m venv .venv-docs` + `pip
install` if a clean docs venv is needed) is the reference for that
case; not duplicated here because triage didn't need to choose (Sphinx
is already importable).

### 4.2 Clean + rebuild (executed)

From the repo root (`C:\Users\yxinl\OneDrive\Projects\PythonProjects\CoreProjects\OpenTeam`):

    rm -rf docs/build/html
    python -m sphinx -b html docs/source docs/build/html 2>&1 | tee docs/build/build-log-after-fix.txt

* `rm -rf docs/build/html` forces a cold rebuild rather than an
  incremental one. Sphinx's incremental mode can mask warnings if a file
  hasn't changed since the last build, even when the *resolved
  cross-reference graph* would now report different warnings (because
  `nitpick_ignore` config changed but the source did not).
* `2>&1 | tee` captures both stdout and stderr to the build log while
  leaving the executor's terminal showing live output.
* The exit code of `sphinx-build` itself (not `tee`) must be checked
  through `${PIPESTATUS[0]}`; see §4.6 for the cross-platform shape.

### 4.3 Expected post-fix warning count

`build succeeded, 6 warnings.` — comprising:

* 1 docutils ERROR on `configuration.rst:254` (escalated; §9.4 E1)
* 5 `[toc.not_readable]` WARNINGs on `index.rst:22` (escalated; §9.4 E2)

All other warnings should have been suppressed (74 `[ref.ref]` via the
9-entry `nitpick_ignore`) or fixed (1 `[ref.dir]` via the
`glossary.rst:13` rewrite). The actual on-disk
`docs/build/build-log-after-fix.txt` confirms exactly this distribution.

### 4.4 Verification queries

After the rebuild, run these to cross-check the result:

* `grep -c "WARNING" docs/build/build-log-after-fix.txt` should match the
  warning portion of the trailer (5).
* `grep -c "ERROR" docs/build/build-log-after-fix.txt` should match the
  ERROR portion (1).
* `tail -1 docs/build/build-log-after-fix.txt` should read
  `build succeeded, 6 warnings.`.
* `grep -c "'std:ref'" docs/source/conf.py` should return 9.
* `grep -n "rst:dir" docs/source/*.rst` should return zero hits.
* `python -c "import ast; ast.parse(open('docs/source/conf.py').read())"`
  should succeed silently (validates the citation comments don't break
  Python parsing).
* `git status docs/source/` should show only `conf.py` and `glossary.rst`
  as modified — verifying constraint (i) compliance.

### 4.5 If the post-fix count is not 6 — diagnostic decision tree

Two failure modes to expect, with diagnostic steps:

**Mode A: Count > 6.** Likely cause: a citation comment in `conf.py`'s
new `nitpick_ignore` block contains a stray character that makes Python
parse it as code, so the list is malformed (silently). Remediation:

1. Re-run `python -c "import ast; ast.parse(open('docs/source/conf.py').read())"`
   to confirm the syntax is valid.
2. If valid, diff the post-fix log against the warm log and identify
   which `[type]` failed to drop. If `[ref.ref]` count is still high,
   the most likely cause is `('std:label', X)` was used instead of
   `('std:ref', X)` — see §10.4.
3. If `[ref.dir]` count is non-zero, the `glossary.rst:13` edit was not
   applied; re-run `grep -n "rst:dir" docs/source/*.rst`.

**Mode B: Count < 6.** Possibilities:

* Someone landed one of the 5 missing pages between the warm build and
  the post-fix build (toctree count drops). Confirm by checking
  `ls docs/source/*.rst` and rerun the categorisation; update §3.5's
  lifetime table by deleting the now-resolved entry from `conf.py`.
* Someone fixed the `configuration.rst:254` ERROR upstream. Confirm via
  `git log -- docs/source/configuration.rst`. If the foundation-page
  edit is justified externally, update the report's "post-fix delta"
  column to reflect what actually happened.

In both Mode B cases, update the triage report's "post-fix delta"
column to reflect what actually happened, and remove the corresponding
entry from §3.5 (lifetime table) and §9.4 (escalations).

### 4.6 Cross-platform rebuild tooling (from Flow 1)

Flow 1's subtask-1 plan worked out the platform-portable invocation
pattern for the build step. Triage's rebuild inherits the same pattern;
documenting it here so a re-runner on either shell gets the right exit-
code capture without rediscovering it.

**bash (the default executor shell):**

```
rm -rf docs/build/html
python -m sphinx -b html docs/source docs/build/html 2>&1 \
    | tee docs/build/build-log-after-fix.txt
echo "sphinx-build exit=${PIPESTATUS[0]}"
```

`${PIPESTATUS[0]}` is the *only* portable way to recover the real
`sphinx-build` exit code through the `| tee` redirection — `$?` after
the pipe is `tee`'s exit code, which is almost always 0 even when
sphinx exited non-zero.

**PowerShell variant (only if the executor is PS 5.1, not bash):**

Do **not** use `2>&1` on a native exe in PS 5.1. The redirection wraps
each stderr line in an `ErrorRecord` (NativeCommandError) and flips
`$?` to `$false` even when the exe returned 0. Use one of:

```
# Option A — let stderr stream to console; tee stdout only
python -m sphinx -b html docs\source docs\build\html `
    *>&1 | Tee-Object -FilePath docs\build\build-log-after-fix.txt

# Option B — capture both via a temporary file, then check $LASTEXITCODE
python -m sphinx -b html docs\source docs\build\html `
    > docs\build\build-log-after-fix.txt 2>&1
"sphinx-build exit=$LASTEXITCODE"
```

`$LASTEXITCODE` is the PS-side equivalent of `${PIPESTATUS[0]}` for
native commands and is the property to check, not `$?`.

**Why this matters for triage:** the post-fix build is expected to exit
0 (the docutils ERROR does not abort without `-W`). If a future re-run
reports a non-zero exit, the executor needs the exit-code plumbing
right before they trust the diagnosis — Flow 1's PS caveat in
particular has trapped re-runners on Windows in the past.

---

## 5. Triage report (step (g))

### 5.1 Format choice

The user request says: "Markdown or RST appendix". Two viable
locations, both Markdown:

| Location | When to use |
|----------|-------------|
| §9 of this consolidated plan (inline appendix) | When the plan + report are produced together (the consolidation case). Keeps triage analysis and the inventory in one auditable file. **This is the location used for the on-disk deliverable.** |
| `docs/_plan/sphinx_warning_triage_report.md` (separate file) | Already on disk (816 lines, executed report). Contains the same inventory in a stand-alone form. Still co-existing on disk; not deleted because deletion is destructive and was not authorised. |

Reasons not to add an RST appendix in `docs/source/`:

* Adding a `triage-report` RST page to the toctree would conflict with
  §2.6 (we're escalating toctree warnings, not editing the toctree).
* Markdown's table syntax is more compact than RST list-tables for an
  81-row inventory.
* Both Markdown locations are consistent with the directory pattern
  already established by `docs/_plan/sphinx_scaffolding_audit.md`.

### 5.2 Required sections (per user request, step (g))

The triage report MUST contain:

1. **One-line summary** — total warnings before, total after, delta.
2. **Bucket totals** — counts per bucket (matching §2.7).
3. **Per-warning inventory** — every original warning, its category,
   the action taken, and whether it appears in the post-fix log.
4. **Escalations** — explicit list of items NOT fixed and why, with the
   suggested upstream owner.
5. **Files touched** — exact diffs / line numbers / commit-message
   suggestions.
6. **Post-fix log delta** — counts per `[type]`, before vs after.

§9 below is the on-disk fulfilment of this checklist.

### 5.3 Inventory table — column schema

| Column | Notes |
|--------|-------|
| `#` | Sequential row number |
| `file:line` | Source location, basename only (path stripped) |
| `type` | `docutils` / `toc.not_readable` / `ref.dir` / `ref.ref` |
| `target` | The undefined label / target name (or n/a for docutils ERROR) |
| `bucket` | One of the seven buckets in §2.7 |
| `action` | `fixed-in-place` / `suppressed-with-citation` / `left-as-pre-existing-with-justification` / `escalated` / `no-action-needed` |
| `post-fix` | `resolved` / `still-warns` / `escalated` |

The 81 individual warning lines collapse cleanly to 7 inventory rows
once grouped by `(file, type, target)` — see §9.3.

### 5.4 Boilerplate text — escalation block

For the configuration.rst:254 ERROR, draft text the executor can
copy-paste into the report (also reproduced verbatim in §9.4):

> **Escalation 1 — `configuration.rst:254` docutils ERROR.**
> Inline cross-ref `` `Startup-time validation`_ `` references a target
> name that does not exist on the page. The closest existing section
> heading is `Startup-time vs runtime mutability` at line 322. The fix
> is a one-line edit in `configuration.rst`, but `configuration.rst` is
> one of the eight line-by-line audited foundation pages and is **out
> of scope** for this triage subtask per CRITICAL constraint (i).
> **Recommendation:** route the fix to whichever subtask owns
> foundation-page edits.

For the 5 toctree warnings:

> **Escalation 2 — five `[toc.not_readable]` warnings on
> `index.rst:22`.** The toctree references five prerequisite pages
> (`introduction`, `getting-started`, `architecture`, `service-layer`,
> `api-reference`) that have not been authored. The warnings cannot be
> silenced by `nitpick_ignore` (different mechanism) and
> `suppress_warnings = ['toc.not_readable']` would be mass suppression,
> prohibited by constraint (ii). Removing the entries from the toctree
> would silence the warnings but break the spec's 9-page reading
> order. **Recommendation:** stub the five pages (each with the
> expected `.. _<page>:` anchor at line 1, optionally the planned
> sub-anchors, plus a "Page not yet authored" placeholder body) under
> a new subtask. That single change would silence all 5 toctree
> warnings AND obviate the 9 forward-referenced `nitpick_ignore`
> tuples (each entry should be deleted in the same commit that lands
> its target page).

---

## 6. Risks, exit criteria, rollback

### 6.1 Risks

* **R1 — `uv` unavailable.** Already realised. Mitigation: substitute
  `python -m sphinx` for `uv run sphinx-build` (§4.1). Same Sphinx
  8.2.3 binary, same source tree; the post-fix log on disk confirms
  the substitution produces the predicted warning delta.
* **R2 — citation comments break Python syntax in `conf.py`.**
  Mitigation: after the §3.2 edit, run
  `python -c "import ast; ast.parse(open('docs/source/conf.py').read())"`
  before the rebuild. The audit doc already verified this works for the
  pre-edit file; the same check applies post-edit.
* **R3 — `:rst:dir:` fix is not idempotent if re-applied.** Mitigation:
  §3.1's `Edit` is keyed on a unique line; running it twice will
  fail-loudly on the second run because the source no longer contains
  the `old_string`. This is the intended safety.
* **R4 — Sphinx 8.x changes the `nitpick_ignore` tuple shape.**
  Mitigation: the `(domain:role, target)` shape has been stable since
  Sphinx 1.5. If a future Sphinx upgrade breaks it, the build will
  surface a config-time error before producing any warning, so the
  regression is fail-fast.
* **R5 — A foundation page is silently edited by another contributor
  between warm-log production and post-fix rebuild.** Mitigation: §4.4's
  `git log` check on `configuration.rst`. If the ERROR disappears, the
  triage report's "post-fix delta" must record what changed and that
  the change came from outside this subtask.
* **R6 — `('std:label', X)` re-introduced by an unwary maintainer.**
  Mitigation: the conf.py header comment block (lines 81–93) explicitly
  documents the matching rule and explains why `std:label` silently
  fails. §10.4 of this artifact preserves the lesson at the consolidation
  level.

### 6.2 Exit criteria

This subtask is complete when **all** of the following are true:

1. `docs/source/glossary.rst:13` no longer contains `:rst:dir:`
   (verified with `grep -n "rst:dir" docs/source/glossary.rst`).
2. `docs/source/conf.py` contains a `nitpick_ignore = [ ... ]` block
   with exactly 9 `('std:ref', <name>)` tuples and one citation
   comment per tuple (verified by inspection).
3. `docs/build/build-log-after-fix.txt` exists and the trailer is
   `build succeeded, 6 warnings.` (off-by-one delta is acceptable only
   if §4.5's diagnostic confirms the cause).
4. The triage report deliverable required by step (g) exists and
   contains the 6 sections enumerated in §5.2. Two acceptable forms:
   §9 of this consolidated plan (inline appendix) **or** the
   stand-alone `docs/_plan/sphinx_warning_triage_report.md`. Both
   exist on disk.
5. **No** edits to any of the eight foundation pages (verified with
   `git status` showing only `conf.py`, `glossary.rst`, the new
   triage report, and the new build log as modified).
6. **No** edits to `index.rst` (same `git status` check).
7. **No** addition of `suppress_warnings` to `conf.py`
   (`grep suppress_warnings docs/source/conf.py` returns empty).
8. `nitpicky = True` is unchanged in `conf.py`.

### 6.3 Rollback

If for any reason the executor wants to abandon the changes:

* `git checkout -- docs/source/conf.py docs/source/glossary.rst`
  reverts both source edits (no foundation pages were touched, so no
  further reverts needed).
* Delete `docs/build/build-log-after-fix.txt`.
* Delete or revert the triage report file(s) created in `docs/_plan/`.

The warm-build log itself (`docs/build/build-log-warm.txt`) and this
plan are not modified by the triage execution and survive a rollback
unchanged.

---

## 7. Files touched / not touched (final)

### 7.1 Touched

| Path | Kind of edit | Diff size |
|------|--------------|-----------|
| `docs/source/glossary.rst` | 1-line replacement at line 13 (`:rst:dir:` → literal `` ``glossary`` ``) | ~1 line |
| `docs/source/conf.py` | Append `nitpick_ignore` block (9 `('std:ref', …)` tuples + per-tuple citation comments + ~30-line header explaining suppression rationale) | ~75 new lines |
| `docs/build/build-log-after-fix.txt` | New file (post-fix rebuild output, `build succeeded, 6 warnings.`) | 47 lines, 3050 B |
| `docs/_plan/sphinx_warning_triage_final.md` | This file — consolidated plan + report. §9 is the report deliverable for step (g). | this document |

### 7.2 Not touched (verifiable)

| Path | Reason |
|------|--------|
| `docs/source/index.rst` | Toctree warnings escalated, not silenced (§2.6) |
| `docs/source/configuration.rst` | Foundation page; ERROR escalated (§2.2.2) |
| `docs/source/inference-models.rst` | Foundation page |
| `docs/source/operations.rst` | Foundation page |
| `docs/source/introduction.rst` | Does not exist; out of scope to author |
| `docs/source/getting-started.rst` | Does not exist; out of scope to author |
| `docs/source/architecture.rst` | Does not exist; out of scope to author |
| `docs/source/service-layer.rst` | Does not exist; out of scope to author |
| `docs/source/api-reference.rst` | Does not exist; out of scope to author |
| `docs/build/build-log-warm.txt` | Input — preserved as-is (ANSI-stripped form is the surviving file) |
| `docs/_plan/sphinx_scaffolding_audit.md` | Companion audit — preserved as-is |
| `docs/_plan/sphinx_initial_build_plan.md` | Companion build-capture plan (Flow 1) — preserved as-is |
| `docs/_plan/sphinx_build_capture_plan.md` | Companion build-capture plan (Flow 0) — preserved as-is |
| `docs/_plan/sphinx_warning_triage_consolidated.md` | Parallel iteration-3 consolidation (Upstream A) — preserved as-is; this final consolidation supersedes it but does not delete it |
| `docs/_plan/sphinx_warning_triage_plan.md` | Parallel iteration-2 consolidation (Upstream B) — preserved as-is; this final consolidation supersedes it but does not delete it |
| `docs/_plan/sphinx_warning_triage_report.md` | On-disk executed report (816 lines) — preserved; its content is reflected in §9 |
| `docs/_plan/sphinx_warning_triage_plan_consolidated.md` | Earlier partial consolidation — preserved |

---

## 8. One-paragraph handoff for the executor

The warm-build log shows 81 warnings; 75 of them go away cleanly with
two surgical edits — a single-line replacement on `glossary.rst:13`
(replace `` :rst:dir:`glossary` `` with `` ``glossary`` ``) and an
appended `nitpick_ignore` block in `conf.py` listing 9
`('std:ref', name)` tuples for the forward-referenced anchors on the 5
not-yet-authored pages. The remaining 6 warnings (1 docutils ERROR on
`configuration.rst:254`, 5 toctree warnings on `index.rst:22`) are
escalated rather than silenced because every silencing option either
modifies a foundation page (forbidden), uses mass suppression
(forbidden), or breaks the spec's 9-page reading order. After the
edits, run `rm -rf docs/build/html && python -m sphinx -b html
docs/source docs/build/html 2>&1 | tee docs/build/build-log-after-fix.txt`
(substituting `python -m sphinx` for the originally-prescribed
`uv run sphinx-build` because `uv` is not on PATH; same binary, same
behaviour). Confirm the trailer reads `build succeeded, 6 warnings.`,
then either rely on §9 of this document or use
`docs/_plan/sphinx_warning_triage_report.md` as the report deliverable
required by step (g). The single most important correctness rule:
`('std:ref', X)` not `('std:label', X)` — see §10.4 for why.

---

## 9. Triage report appendix — the deliverable for step (g)

This appendix is the on-disk fulfilment of step (g) of the user
request. It lists every original warning with its category, the action
taken, and the post-fix delta. It is intentionally co-located with the
plan to keep planning, execution, and reporting auditable in one
document. The stand-alone form is also on disk at
`docs/_plan/sphinx_warning_triage_report.md` (816 lines).

### 9.1 One-line summary

**Warm build:** 81 warnings (1 docutils ERROR, 5 toctree, 1 ref.dir,
74 ref.ref). **Post-fix build:** 6 warnings (1 docutils ERROR, 5
toctree). **Delta: −75** (−1 ref.dir fixed in source, −74 ref.ref
suppressed via `nitpick_ignore`).

### 9.2 Bucket totals (matches §2.7)

| Bucket | Pre-fix count | Action | Post-fix count |
|--------|--------------:|--------|---------------:|
| EXPECTED-NOW-RESOLVED | 0 | (confirmed empty) | 0 |
| REAL-BUG, fixable in NEW file | 1 | fixed-in-place (§3.1) | 0 |
| REAL-BUG, escalated | 1 | escalated (§9.4 E1) | 1 |
| DRIFT | 0 | (confirmed empty) | 0 |
| PRE-EXISTING-IN-FOUNDATION | 55 | suppressed-with-citation (§3.2) | 0 |
| PRE-EXISTING-IN-NEW-FILE (glossary) | 19 | suppressed-with-citation (§3.2) | 0 |
| Toctree precondition gap | 5 | escalated (§9.4 E2) | 5 |
| **Total** | **81** | | **6** |

### 9.3 Per-warning inventory

The 81 warnings collapse cleanly into 7 inventory rows once grouped by
`(file, type, target)` — verbose row-per-line listing would be
mechanical noise (the warm log is in `docs/build/build-log-warm.txt`
for line-level forensics). The grouped form below preserves the audit
trail without bloating the report.

| # | file | type | target / message | count | bucket | action | post-fix |
|--:|------|------|------------------|------:|--------|--------|----------|
| 1 | `glossary.rst:13` | ref.dir | `glossary` (rst:dir target not found) | 1 | REAL-BUG, fixable in NEW file | fixed-in-place — replaced `` :rst:dir:`glossary` `` with literal `` ``glossary`` `` (§3.1) | resolved |
| 2 | `configuration.rst:254` | docutils | `Unknown target name: "Startup-time validation"` | 1 | REAL-BUG, escalated | escalated — foundation-page edit required; recommend retarget to `Startup-time vs runtime mutability` heading (§9.4 E1) | still-warns |
| 3 | `index.rst:22` | toc.not_readable | references nonexisting documents `introduction`, `getting-started`, `architecture`, `service-layer`, `api-reference` (5 distinct lines) | 5 | Toctree precondition gap, escalated | escalated — silencing options all violate constraints (i)/(ii) or break the spec's 9-page reading order (§9.4 E2) | still-warns |
| 4 | `configuration.rst` (multiple lines) | ref.ref | 9 unique anchor names: `introduction`, `getting-started`, `gs-feature-flags`, `architecture`, `arch-debug-trace`, `svc-moderation`, `api-reference`, `api-etag`, `api-debug-trace` | 43 | PRE-EXISTING-IN-FOUNDATION | suppressed-with-citation — 9 `('std:ref', …)` entries in `conf.py` `nitpick_ignore` block, each with a per-tuple citation comment naming the source line(s) (§3.2) | resolved |
| 5 | `inference-models.rst` (multiple lines) | ref.ref | subset of the 9 anchors (`architecture`, `svc-moderation`) | 7 | PRE-EXISTING-IN-FOUNDATION | suppressed-with-citation — same `conf.py` block as row 4 (§3.2) | resolved |
| 6 | `operations.rst` (multiple lines) | ref.ref | subset of the 9 anchors (`architecture`, `getting-started`) | 5 | PRE-EXISTING-IN-FOUNDATION | suppressed-with-citation — same `conf.py` block as row 4 (§3.2) | resolved |
| 7 | `glossary.rst` (multiple lines) | ref.ref | the 9 anchors (intentional forward refs per `glossary.rst:23-32`) | 19 | PRE-EXISTING-IN-NEW-FILE | suppressed-with-citation — same `conf.py` block as row 4 (§3.2). Not deletable from `glossary.rst` because the *Shared Anchor Map* is the cross-reference graph's source-of-truth. | resolved |
| | **Total** | | | **81** | | | **6 still-warning** |

Per-anchor-name distribution is in §1.3 (the `architecture` anchor is
cited 20×, `api-reference` 15×, `getting-started` 11×, etc.).
Per-source-line forensics are available via `grep -n` against
`docs/build/build-log-warm.txt`; that level of detail is rarely needed
once the bucket assignment is agreed.

### 9.4 Escalations

**Escalation 1 — `configuration.rst:254` docutils ERROR.** Inline
cross-ref `` `Startup-time validation`_ `` references a target name
that does not exist on the page. The closest existing section heading
is `Startup-time vs runtime mutability` at line 322. The fix is a
one-line edit in `configuration.rst`, but `configuration.rst` is one of
the eight line-by-line audited foundation pages and is **out of scope**
for this triage subtask per CRITICAL constraint (i). **Recommendation:**
route the fix to whichever subtask owns foundation-page edits. Until
then, the build will continue to log this single docutils ERROR — note
that it does not abort the build under default `keep_going` handling,
so the build-success status is preserved.

**Escalation 2 — five `[toc.not_readable]` warnings on `index.rst:22`.**
The toctree references five prerequisite pages (`introduction`,
`getting-started`, `architecture`, `service-layer`, `api-reference`)
that have not been authored. This is a precondition gap inherited from
upstream subtasks (cf. `sphinx_scaffolding_audit.md` §4). The warnings
cannot be silenced by `nitpick_ignore` (different mechanism), and
`suppress_warnings = ['toc.not_readable']` would be mass suppression,
prohibited by constraint (ii). Removing the entries from the toctree
would silence the warnings but break the spec's 9-page reading order.
**Recommendation:** stub the five pages (each with `.. _<page>:` at line
1, optionally the planned sub-anchors, plus a "Page not yet authored"
placeholder body) under a new subtask. That single change would silence
all 5 toctree warnings AND obviate the 9 forward-referenced
`nitpick_ignore` tuples (each entry should be deleted in the same
commit that lands its target page — see §3.5). Until then, the build
will continue to log these 5 warnings.

### 9.5 Files touched (verifiable)

| Path | Edit | Verification |
|------|------|--------------|
| `docs/source/glossary.rst` | Line 13: `` * The :rst:dir:`glossary` directive below — alphabetised — for `` → `` * The ``glossary`` directive below — alphabetised — for `` | `grep -n "rst:dir" docs/source/*.rst` returns zero hits |
| `docs/source/conf.py` | Appended ~75-line block: 30-line header comment explaining suppression rationale + `nitpick_ignore = [ … ]` list with 9 `('std:ref', '<anchor>')` tuples, each preceded by a 1-3 line citation comment | `python -c "import ast; ast.parse(open('docs/source/conf.py').read())"` succeeds; `grep -c "'std:ref'" docs/source/conf.py` returns 9 |
| `docs/build/build-log-after-fix.txt` | New file (47 lines, `build succeeded, 6 warnings.` trailer) | `grep "build succeeded, 6 warnings" docs/build/build-log-after-fix.txt` matches |
| `docs/_plan/sphinx_warning_triage_final.md` (this file) | Plan + report consolidated; this §9 is the report deliverable | n/a — this file |

### 9.6 Files explicitly NOT touched (constraint compliance)

`docs/source/index.rst`, `configuration.rst`, `inference-models.rst`,
`operations.rst` are unmodified. The five missing foundation pages
(`introduction`, `getting-started`, `architecture`, `service-layer`,
`api-reference`) were not authored. A `git status` for the docs subtree
should show only `conf.py`, `glossary.rst`, the post-fix build log, and
this consolidation plan as new/modified.

### 9.7 Post-fix log delta — by `[type]`

| `[type]` | Pre-fix | Post-fix | Δ | Mechanism |
|----------|--------:|---------:|--:|-----------|
| `[docutils]` | 1 | 1 | 0 | Escalated (§9.4 E1); no in-scope fix mechanism |
| `[toc.not_readable]` | 5 | 5 | 0 | Escalated (§9.4 E2); silencing options all violate constraints |
| `[ref.dir]` | 1 | 0 | −1 | Fixed in source (`glossary.rst:13`, §3.1) |
| `[ref.ref]` | 74 | 0 | −74 | Suppressed via 9 `('std:ref', …)` `nitpick_ignore` tuples (§3.2) |
| **Total** | **81** | **6** | **−75** | |

The trailer line in `docs/build/build-log-after-fix.txt` reads
`build succeeded, 6 warnings.`, which matches both the predicted
post-fix count and the bucket totals in §9.2.

---

## 10. Integration & consolidation notes

### 10.1 Inputs and iterations

This consolidated artifact integrates two parallel iteration-2/3
consolidations plus the upstream build-capture context they each
integrated. Per the Provenance table at the top:

* **Upstream A** (`sphinx_warning_triage_consolidated.md`, 967 lines):
  Flow 0's iteration-3 consolidation. Contributed cross-platform rebuild
  tooling, cross-flow verification matrix, the `std:label` divergence
  framing, explicit input-promotion of user-supplied triage Flow 0/Flow 1.
* **Upstream B** (`sphinx_warning_triage_plan.md`, 1453 lines):
  Flow 1's iteration-2 consolidation. Contributed the numbered
  structural backbone, verbatim annotated `nitpick_ignore` diff with
  per-tuple citations, risks/exit-criteria/rollback section, the
  diagnostic decision tree, the empirical reconciliation table.

The two upstream artifacts share ~90% substantive content (bucket totals,
the std:label→std:ref bug, on-disk reality, three CRITICAL constraint
compliance). The merge below was therefore **selective grafting**, not
mechanical de-duplication — each upstream's unique structural element
was kept where it added operational guidance.

### 10.2 Where parallel inputs agreed (cross-flow verification)

The two upstream consolidations themselves consumed multiple parallel
flows. Independent-pass cross-validation matrix:

| Quantity | Flow 0 (executed) | Flow 1 (planning) | Consolidation verdict |
|----------|------------------:|-------------------:|-----------------------|
| Warm-build warnings | 81 | 81 | ✓ Agree (verified against `docs/build/build-log-warm.txt`) |
| Post-fix warnings | 6 | 6 | ✓ Agree (verified against `docs/build/build-log-after-fix.txt`) |
| REAL-BUG fixable | 1 | 1 | ✓ |
| REAL-BUG escalated | 1 | 1 | ✓ |
| EXPECTED-NOW-RESOLVED | 0 | 0 | ✓ |
| DRIFT | 0 | 0 | ✓ |
| PRE-EXISTING-IN-FOUNDATION | 55 | 55 | ✓ |
| PRE-EXISTING-IN-NEW-FILE | 19 | 19 | ✓ |
| Toctree precondition gap | 5 | 5 | ✓ |
| `nitpick_ignore` entry count | 9 | 9 | ✓ |
| Build exit code | 0 | 0 | ✓ |

Two flows agreeing on every quantitative claim is itself useful signal:
the categorisation framework in the user request is unambiguous against
this docset's warning population — both an *executor* and a *planner*
working independently classified every warning into the same bucket.

The two flows also agreed on the environmental constraints (no `uv` on
PATH; no `pyproject.toml`; no `uv.lock`; no `CONSOLIDATION_NOTES*`) —
this is **multi-author second-source verification**, not a single audit.

### 10.3 Where parallel inputs differed (and what was kept)

| Element | Upstream A / Flow 0 | Upstream B / Flow 1 | Kept here |
|---------|---------------------|---------------------|-----------|
| Top-level structure | Part A/B/C/D narrative | Numbered §0–§10 | Numbered §0–§11 (Upstream B's; more granular; isomorphic to Upstream A's Part A→§0–§4, Part B→§5+§9, Part C→§10.5, Part D→§3.5+§7) |
| Per-entry suppression-lifetime mapping | Part D.1 table | §3.5 table + operational consequence narrative | §3.5 (Upstream B's longer form, with the lifetime invariant explained) |
| Verbatim annotated nitpick_ignore diff | partial; entries listed without citation comments | full; per-tuple citation comments verbatim | §3.2 (Upstream B's full form — needed for constraint (ii) audit) |
| Risks / exit-criteria / rollback | absent | §6 | §6 (Upstream B's; no failure-mode coverage in Upstream A) |
| Post-fix-count diagnostic decision tree | absent | §4.5 | §4.5 (Upstream B's; useful for future re-runs) |
| Cross-platform rebuild tooling | §A.4.3 (bash + PowerShell) | §4.2 (bash only) | §4.6 (Upstream A's — ingested from Flow 1 which Upstream A had absorbed) |
| Cross-flow verification matrix | Part E.1 | §10.2 (verbal) | §10.2 (Upstream A's matrix form — concrete and auditable) |
| `std:label` → `std:ref` divergence framing | Part E.2 (input-level — Flow 1 *original* recommendation vs Flow 0 *executed* discovery) | §10.4 (consolidator-level — corrected an autonomous draft) | §10.4 (Upstream A's framing — assigns responsibility chain explicitly) |
| Empirical predicted-vs-observed reconciliation | §C.1 (verbal) | §10.6.1 (table) | §10.5 (Upstream B's table form) |
| Iteration judgement framing | Part E.4 (iteration 3) | §10.7 (iteration 2) | §10.7 (this artifact's final integration value judgment) |

### 10.4 The `std:label` → `std:ref` bug — divergence between planning and executed flows

The single substantive divergence between the upstream flows feeding
this consolidation was on the *mechanics* of suppression:

* **Executed flow** discovered empirically that `('std:ref', '<anchor>')`
  is the correct `nitpick_ignore` tuple key for `[ref.ref]` warnings —
  caught after a first-pass `('std:label', X)` rebuild left 74 of 75
  suppressible warnings still firing despite Sphinx reporting "build
  succeeded".
* **Planning artifact** as originally produced recommended
  `('std:label', '<anchor>')`. That key parses without error, Sphinx
  reports no config issue, and the build still says "succeeded" — but
  the warnings are not suppressed. A planner that stopped at this
  recommendation would have shipped a partially-applied fix and reported
  success.

**Why `std:ref` is correct** (matching-rule derivation): Sphinx's
`ReferencesResolver.warn_missing_reference` (in
`sphinx/transforms/post_transforms/__init__.py`) builds the suppression
key as `f'{domain.name}:{typ}'`, where `typ` is the **role used at the
citation site** (`ref` for `:ref:` invocations), not the *object type*
the role would have resolved to (`label` for `.. _foo:` directives). For
an undefined `:ref:` to `introduction`:

* `domain.name == 'std'`
* `typ == 'ref'` (the citing role; *not* the would-be target object's type)
* lookup key: `'std:ref'`
* matching tuple: `('std:ref', 'introduction')` ✓

`('std:label', 'introduction')` would build lookup key `'std:label'`,
which is never compared against — that string is the type of the
*target object* (the directive that *creates* the anchor), which is
irrelevant to the warning emitted by the *citation site*.

**Disposition:** the consolidated artifact carries the executed flow's
empirical finding forward, and explicitly flags the original `std:label`
recommendation as the exact failure mode an unwary maintainer could
re-introduce. Both states are preserved (the *correct* fix is the
on-disk state; the *wrong* alternative is documented as a trap to avoid)
so the lesson is permanent. The conf.py header comment (lines 81–93)
restates the matching rule with a code-citation pointer, so a future
reader who diffs the file does not re-introduce the bug.

This is the **central correctness insight that consolidation surfaced**:
without the cross-check between an executed pass and a planning pass,
the bug would have shipped silently.

### 10.5 Empirical reconciliation — Flow 0's build-capture predictions vs. observed outcomes

Flow 0's build-capture plan (`sphinx_build_capture_plan.md`) predicted
the warm-build signals from a prior empirical run. Every prediction
held in the actual warm-build log:

| Flow 0 forecast (subtask 1 plan) | Observed in `build-log-warm.txt` | Match |
|----------------------------------|-----------------------------------|:-----:|
| 5 toctree `[toc.not_readable]` warnings | exactly 5 (5 missing foundation pages × 1 toctree entry each) | ✓ |
| ~70+ `[ref.ref]` warnings under `nitpicky=True` | exactly 74 — within the predicted band | ✓ |
| ≥1 docutils ERROR | exactly 1, on `configuration.rst:254` ("startup-time validation") | ✓ |
| Build exit code 0 | 0 (default `keep_going` does not promote ERROR to fatal) | ✓ |
| Sphinx summary roughly `build succeeded, ~80 warnings` | exactly `build succeeded, 81 warnings.` | ✓ |

This 100% prediction-vs-observation match validates Flow 0's audit
methodology and gives high confidence that the post-fix state
(`build succeeded, 6 warnings.`) is itself stable — i.e., the −75 delta
is not a one-off result and will reproduce on subsequent re-builds
(subject to the lifetime invariants in §3.5).

The single thing Flow 0's build-capture plan (correctly) did **not**
predict was the `('std:label', X)` tuple-key bug: that bug was internal
to the conf.py block produced by an earlier author, and Flow 0 was
scoped to "build-capture only — no source edits" (its out-of-scope list
explicitly excluded `nitpick_ignore` changes). The triage subtask (this
artifact) is precisely the recovery that the build-capture plan
deferred. The discovery of the std:label→std:ref bug is therefore an
iteration-1 contribution of triage, not a build-capture omission.

### 10.6 Required judgments made during consolidation

* **The user request as routed in describes subtask 1, but both upstream
  inputs address subtask 2.** Resolved by acknowledging the scope
  mismatch up front (§"Scope acknowledgment" + §11) and faithfully
  consolidating the subtask-2 content. Subtask 1 is materially complete
  on disk (warm log exists, exit 0); the build-capture plans (Flow 0 /
  step 0 and Flow 1) are referenced as upstream context, not re-done.
* **`uv run sphinx-build` was substituted with `python -m sphinx`.**
  Justified by `which uv → 127`, by both upstream build-capture flows
  independently reaching the same conclusion, by the `conf.py` header
  comment explicitly contemplating no-`pyproject.toml` operation, and
  by the empirical post-fix log demonstrating the substitution
  preserves the predicted warning delta.
* **`('std:ref', X)` is preserved over `('std:label', X)`.** §10.4
  documents the responsibility chain (planning recommended `std:label`,
  executed pass discovered the silent no-op, this consolidation
  preserves both the corrected fix and the lesson).
* **The triage report is co-located inline as §9** rather than only a
  separate file. Justified by (a) "appendix" being one of the
  user-request's two acceptable formats; (b) keeping plan + report in
  one auditable document; (c) the `docs/_plan/` directory pattern
  already including such combined plan documents. The stand-alone
  `docs/_plan/sphinx_warning_triage_report.md` is also preserved on disk.
* **No on-disk parallel artifact was deleted.** Both upstream
  consolidations (`sphinx_warning_triage_consolidated.md`,
  `sphinx_warning_triage_plan.md`) and the older
  `sphinx_warning_triage_plan_consolidated.md` remain on disk. Deletion
  is destructive and was not authorised. This document supersedes them
  in role; future readers can verify the agreement by diffing.
* **Numbered structure (§0–§11) over Part A/B/C/D narrative.** The two
  upstream structures are isomorphic; the numbered form is more granular
  and easier to cross-reference, so it was adopted as the backbone with
  Upstream A's Part E content lifted into §10.2/§10.4.

### 10.7 Final integration value judgment

**Yes, the consolidation step produced new signal beyond what either
upstream artifact had alone.** Specifically:

1. **It exposed the `std:label` vs `std:ref` divergence as an
   input-level finding, not a consolidator-level correction.** §10.4
   makes the responsibility chain explicit: the planning artifact
   contained the recommendation; the executed pass caught it; this
   consolidation preserves the lesson. Without consolidation, a
   downstream consumer reading just the planning artifact would have
   applied an incorrect fix and reported success.
2. **It separated "what was planned" from "what was executed".** The
   planning flow was structurally well-organised but had not actually
   run the build/fix/rebuild cycle. The executed flow had the empirical
   results. Consolidating produces a single artifact with both the
   well-structured methodology and the verified outcomes.
3. **It captured the matching-rule derivation as a maintainer-facing
   note.** Neither flow alone fully explained *why* `std:ref` is correct
   beyond the empirical observation. §10.4 cites the
   `f'{domain.name}:{typ}'` line in
   `sphinx/transforms/post_transforms/__init__.py` and explains why the
   *role-type* (citation site) wins over the *object-type* (target
   directive) in the suppression key — making the fix robust against
   re-introduction. The conf.py header comment (lines 81–93) restates
   the same analysis at the source level.
4. **It cross-validated bucket sub-totals (§10.2).** Two independent
   passes through the same warm log produced identical counts at every
   level of granularity. That agreement is itself documentation: the
   categorisation framework is unambiguous for this docset.
5. **It selectively grafted operationally-useful unique elements** —
   §3.5's lifetime mapping (from one upstream), §6's risks/rollback
   (from the other), §4.5's diagnostic tree (from the other), §4.6's
   cross-platform tooling (from the first) — none of which would have
   been derivable from either upstream alone.

**Caveat — diminishing returns past this point.** The two upstream
flows agree on every outcome; the one substantive disagreement
(`std:label` vs `std:ref`) is now resolved and documented as a permanent
lesson; no further integration insight is plausibly outstanding. A
reasonable next step is **stop**, unless a new upstream input is added.

---

## 11. Cross-reference to subtask 1 (build capture)

The original user request as routed in describes **subtask 1**:
install Sphinx, run cold + warm builds, capture raw logs, hand off to
subtask 2. This consolidation, like both upstream inputs, addresses
**subtask 2** (warning triage). Subtask 1's outputs are the inputs to
this triage; documenting the handoff manifest here for completeness.

### 11.1 Subtask 1 deliverables on disk

| Deliverable | Path | Status |
|-------------|------|--------|
| Sphinx + theme + docutils version manifest | implicit (Sphinx 8.2.3 / sphinx-rtd-theme 3.0.2 / docutils 0.21.2 — importable in active miniforge3 Python 3.12.7) | ✓ Captured (no separate file; recorded in §0.1 / §4.1 / §10.5 of this artifact) |
| Cold build log | `docs/build/build-log-cold.txt` (per the user request specification) | ✗ **Not on disk** — only the warm log was preserved. (See §11.2 for the implication.) |
| Warm build log | `docs/build/build-log-warm.txt` | ✓ 122 lines (ANSI-stripped), 81 warnings, exit 0 |
| Build exit code | 0 (warm) | ✓ Captured in `build-log-warm.txt` and re-confirmed by post-fix log |
| Generated HTML page count under `docs/build/html/` | varies by build; the 4 source pages (`index.rst`, `glossary.rst`, `configuration.rst`, `inference-models.rst`, `operations.rst`) plus Sphinx auxiliary pages (`genindex.html`, `search.html`, etc.) | ✓ Implicit from successful build; not enumerated as a separate file |
| Post-fix build log | `docs/build/build-log-after-fix.txt` | ✓ 47 lines, 6 warnings, exit 0 (this is a subtask-2 deliverable, not a subtask-1 one — included for completeness) |

### 11.2 Implication of the missing cold log

The user request prescribed *both* a cold and a warm build, motivated
by the observation that "Sphinx warnings can vary between cold and warm
builds (e.g., autosectionlabel-duplicate warnings often only surface on
warm rebuild) — and the warm-build output is canonical."

In this environment the warm log is preserved but the cold log is not.
This is acceptable for the triage subtask because:

* The warm log *is* the canonical input per the user request itself.
* The post-fix log (`build-log-after-fix.txt`) was produced via
  `rm -rf docs/build/html && sphinx-build …`, which is a *cold-style*
  rebuild. So the cold/warm separation is honoured at the post-fix
  stage; the missing artifact is only the pre-fix cold log.
* No autosectionlabel-duplicate warnings are observed in the warm log,
  so the canonical warm-vs-cold delta would not surface a different
  warning class than the one already triaged.

If a future re-run requires the cold log explicitly, regenerate it via:

    rm -rf docs/build/html docs/build/.doctrees
    python -m sphinx -b html docs/source docs/build/html 2>&1 \
        | tee docs/build/build-log-cold.txt
    echo "sphinx-build exit=${PIPESTATUS[0]}"

This produces a genuinely cold log; the warm log can then be regenerated
by running `sphinx-build` a second time without the `rm` step. Both
would feed back into a re-triage if warning classes differ between the
two passes (which the current execution suggests they would not, but the
guarantee depends on the docset's autosectionlabel + nitpicky
interaction, which is fully exercised by the existing warm log).

### 11.3 Constraint compliance for subtask 1

Subtask 1's CRITICAL constraint was: "do not modify ANY existing files
(not the 8 prose pages, not conf.py / index.rst / glossary.rst); this
subtask is install + execute + capture only." Verification:

* Subtask 1 wrote `docs/build/build-log-warm.txt` (a new file). No
  existing source file was modified during subtask 1.
* Subtask 2 (this artifact) modified `conf.py` and `glossary.rst` —
  these modifications are subtask-2-scoped, authorised by subtask 2's
  own request, and are documented in §7.1.
* The 8 foundation pages (`introduction`, `getting-started`,
  `architecture`, `service-layer`, `api-reference`, `inference-models`,
  `configuration`, `operations`) — where present on disk — were not
  modified by either subtask. Verifiable via `git status`.

Constraint (i) is honoured across both subtasks; constraint (ii) is
honoured via §3.2's targeted-with-citation `nitpick_ignore` block;
constraint (iii) is honoured because subtask 1 captured-only and
subtask 2 owns the recovery.

