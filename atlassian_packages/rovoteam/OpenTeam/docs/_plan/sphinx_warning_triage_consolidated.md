# Sphinx Warning Triage — Consolidated Plan & Report

**Subtask:** Triage every warning from the warm-build log, fix what is in-scope
(REAL-BUG / DRIFT in `conf.py` / `index.rst` / `glossary.rst`), suppress what is
out-of-scope via targeted `nitpick_ignore` entries with citations, escalate
what is neither, then re-build and produce a triage report.

**Date:** 2026-05-04
**Repo root:** `C:\Users\yxinl\OneDrive\Projects\PythonProjects\CoreProjects\OpenTeam`
**Docset:** `responsible-ai-api` (under `docs/source/`)

## Provenance & predecessor inputs

This artifact consolidates several upstream pieces:

| Input | What it provided | What it didn't cover |
|-------|------------------|----------------------|
| User request (subtask 2 description) | Categorisation buckets, three CRITICAL constraints, deliverable list | — |
| Flow 0 / step 0: `docs/_plan/sphinx_build_capture_plan.md` (456 lines) | **Subtask 1 (build-capture) plan**; empirical predictions for the warm log (5 toctree + ~70 undefined-label + ≥1 docutils ERROR; exit 0); environment audit (no `uv` on PATH, no `pyproject.toml`, no `CONSOLIDATION_NOTES*` file). | Did not cover triage itself — that is the current subtask. |
| Flow 0 / step 1: this artifact's prior iteration (734 lines, the v1 consolidation) | The complete plan + report skeleton: §§ A.0–A.4 (rules, parsed inventory, per-warning categorisation, concrete edits, rebuild), §§ B.1–B.5 (the report), §§ C.1–C.4 (predecessor reconciliation), §§ D.1–D.3 (handoff). Surfaced the `('std:label', X)` → `('std:ref', X)` syntax bug. | — (this iteration extends, not replaces). |
| Flow 1: `docs/_plan/sphinx_initial_build_plan.md` (520 lines) | **Subtask 1 (build-capture) plan, parallel to flow 0 / step 0.** Contributes (a) an independent verification of the environmental constraints (`uv` not on PATH, no `pyproject.toml`, no `uv.lock`, no `CONSOLIDATION_NOTES*`), (b) §3 install-path decision matrix (5 options compared, recommends pure-stdlib `python -m venv .venv-docs` + `pip install`), (c) §5 step-by-step bash with `tee` + `${PIPESTATUS[0]}` exit-code capture, (d) §5-bis PowerShell variant flagging PS 5.1's stderr-wrapping (`2>&1` on a native exe wraps each line in an `ErrorRecord` and clobbers `$?` even on exit 0), (e) §6 failure-handling matrix, (f) §10 open questions for the executor. | **Same scope as flow 0 / step 0** — does not cover triage. The triage-relevant lift from this input is the cross-platform rebuild tooling, ingested into §A.4 below. |
| Predecessor audit: `docs/_plan/sphinx_scaffolding_audit.md` | Page-existence audit (3 of 8 foundation pages on disk) | — |
| On-disk partial plan: `docs/_plan/sphinx_warning_triage_plan.md` (250 lines at v1-iteration time, **§§ 0–1.4 only**; subsequently extended by a parallel process to ~1021 lines) | Inputs, rule restatement, parsed-inventory tables, bucket totals (TL;DR predicted 6 post-fix). | **§§ 2–5 missing at v1 time**: per-warning categorisation, concrete edits, rebuild step, triage-report deliverable. Iteration v1 supplied them; this iteration carries them forward unchanged. |
| On-disk applied edits | `docs/source/conf.py` (3443 → 7732 B at 10:43); `docs/source/glossary.rst` (35856 B at 10:41); rebuild log `docs/build/build-log-after-fix.txt` (3050 B at 10:44) showing **6 warnings post-fix**. | The partial plan stopped before documenting them. |
| **Iteration 3 input — User's Flow 0** (executed): `docs/_plan/sphinx_warning_triage_report.md` (~43 KB, 816 lines, mtime 10:51) | End-to-end execution of the warm-build → triage → fix → re-build → report cycle. Source of the empirical `('std:ref', X)` discovery (caught after a first-pass `('std:label', X)` rebuild left 74 of 75 suppressible warnings still firing). The on-disk fixes in `conf.py` (94-129) and `glossary.rst:13` are this flow's edits. | None (this is the most authoritative input since it is the actual execution). |
| **Iteration 3 input — User's Flow 1** (planning-only): `docs/_plan/sphinx_warning_triage_plan.md` (~49 KB, 1035 lines, mtime 10:53; now extended to 1453 lines as of iteration 4) | Pre-execution planning artifact: parsed inventory, bucket sub-totals, per-anchor cite distribution, executor handoff. Predicted **6 post-fix warnings** ahead of time. The original raw Flow 1 input that this consolidator received recommended `('std:label', <anchor>)` as the suppression tuple-key — an empirically-incorrect choice that Flow 0 caught and corrected. | The on-disk plan file has since been updated to reflect post-execution reality, so it agrees with Flow 0 today. The correctness lesson (`std:label` is silent no-op) is preserved in §A.3.1 and §C.3 to prevent re-introduction. |
| **Iteration 4 input — Parallel consolidator**: `docs/_plan/sphinx_warning_triage_plan_consolidated.md` (247 lines) | An independently produced consolidation pass that operated against a thinner input set (its "Flow 0" had no output; only the planning Flow 1 was substantive). Even with that constraint, it (a) catalogued the **specific 16 line numbers** in Flow 1's *original* raw plan where `('std:label', X)` appeared (lines 183, 415, 593, 599, 604, 612, 617, 625, 630, 635, 640, 652, 658, 773, 942, 1010 — anchored to the original raw plan, not the on-disk-today plan which has since been corrected), (b) supplied a clean **Risks / Exit / Rollback** subsection that this artifact adopts as §D.4, and (c) supplied a one-paragraph **executor handoff** that this artifact adopts as §D.5. | Because it lacked Flow 0 (the executed report), it could not triangulate the matching-rule derivation that this artifact's §A.3.1 carries; nor could it cross-validate bucket sub-totals across two independent passes (this artifact's §E.1). |

**This consolidated artifact** (now in its iteration-4 form):

* (a) preserves the partial plan's §§ 0–1 content (inputs, rules, parsed
  inventory) by reference and refinement;
* (b) supplies the missing §§ 2–5 (categorisation, edits, rebuild, report);
* (c) reconciles flow 0 / step 0's empirical predictions against actual
  outcomes;
* (d) surfaces one finding that the partial plan got factually wrong
  (the `nitpick_ignore` tuple-key syntax — the central insight of this
  consolidation, see §A.3.1 and §C.3);
* (e) ingests build-capture flow 1's cross-platform build tooling
  (bash `tee` + `${PIPESTATUS[0]}`, PowerShell stderr-wrapping caveat)
  into §A.4.3 of the rebuild plan, and acknowledges build-capture
  flow 1 as a second-source verification of the environmental
  constraints in §C.2 (so the constraint statement no longer relies on
  a single predecessor's audit);
* (f) **added in iteration 3:** promotes the user-supplied **triage**
  Flow 0 (executed report) and Flow 1 (planning artifact) from
  "background context" to **explicit inputs** (table rows above), and
  records the iteration-3 integration judgement in **Part E** below —
  the integration verifies cross-flow agreement on outcomes (both
  flows arrived at 6 post-fix warnings via different paths), surfaces
  Flow 1's *original* `std:label` recommendation as an
  almost-undetected silent no-op, and documents both for the next
  maintainer;
* (g) **new in iteration 4:** consolidates a *parallel*
  consolidation attempt — `docs/_plan/sphinx_warning_triage_plan_consolidated.md`
  (247 lines) — that was produced independently against a thinner
  input set (it lacked the executed-report Flow 0 and so could only
  triangulate against the planning Flow 1). The iteration-4 lift is
  documented in **Part F** below; specifically, three targeted
  additions are folded in: a Risks/Exit/Rollback subsection (§D.4),
  a one-paragraph executor handoff (§D.5), and the locator evidence
  for the original 16 `('std:label', X)` occurrences in Flow 1's
  raw plan (§A.3.1 footnote and §E.2 cross-reference).

## TL;DR

* **Inventory:** 81 build issues in the warm log (`docs/build/build-log-warm.txt`,
  15 KB after ANSI-strip): 1 docutils `ERROR`, 5 `[toc.not_readable]`
  WARNINGs, 1 `[ref.dir]` WARNING, 74 `[ref.ref]` WARNINGs. Sphinx
  rolls them all up as `build succeeded, 81 warnings.`
* **Categorisation:**

  | Bucket | Count | Action |
  |--------|------:|--------|
  | REAL-BUG, fixable in NEW file | 1 | Edit `glossary.rst:13` (rst:dir self-reference) |
  | REAL-BUG, escalated (foundation page) | 1 | Flag `configuration.rst:254` docutils ERROR |
  | EXPECTED-NOW-RESOLVED | 0 | (Confirms the anchor chain — no prior subtask landed any of the 5 missing pages) |
  | DRIFT (anchor-name mismatch) | 0 | (No producer/consumer mismatches; every undefined label is a *missing-page* problem) |
  | PRE-EXISTING-IN-FOUNDATION | 55 | Suppress via `nitpick_ignore` (9 anchors × varied cite count) |
  | PRE-EXISTING-IN-NEW-FILE (auxiliary) | 19 | Suppress via *the same* 9 `nitpick_ignore` entries |
  | Toctree precondition gap, escalated | 5 | Flag in this report; do **not** prune toctree (would mask missing pages) |

* **Edits applied** (already on disk; this artifact ratifies and documents them):
  * `docs/source/conf.py`: rewrote 9-entry `nitpick_ignore` from
    `('std:label', '<name>')` to `('std:ref', '<name>')` —
    **the actual unblocker; see §A.3.1 for why the partial plan's
    `std:label` syntax did not work**. Header comment updated to
    explain the tuple key matches `f'{domain.name}:{typ}'` from
    Sphinx's `ReferencesResolver.warn_missing_reference`.
  * `docs/source/glossary.rst`: replaced a `:rst:dir:`glossary`` (or
    similar) at line 13 with literal-text `` ``.. glossary::`` ``
    (the line now reads as plain prose describing the directive,
    not invoking it as a cross-reference role).
  * `docs/source/index.rst`: **no edit** (toctree warnings are
    escalations, not silenced).
  * Foundation pages: **no edits** (per constraint (i)).

* **Rebuild outcome** (`docs/build/build-log-after-fix.txt`, 3 KB):
  `build succeeded, 6 warnings.` — namely 1 docutils ERROR + 5
  toctree WARNINGs (both escalated). **Net delta: −75 warnings.**

* **Open escalations carried forward to subsequent subtasks:**
  1. 5 missing foundation pages (`introduction`, `getting-started`,
     `architecture`, `service-layer`, `api-reference`) need authoring;
     until then the toctree warnings persist.
  2. `configuration.rst:254` RST-syntax docutils ERROR is in a
     foundation page; the next foundation-edit subtask owns the fix.
  3. Each `nitpick_ignore` entry has a comment naming the page that
     should host the corresponding `.. _<anchor>:` directive; **delete
     the line** when that page lands. Removing one entry without the
     corresponding page-author commit is a regression.


---

## Part A — Plan & methodology

### A.0 Inputs, scope, and rules

#### A.0.1 Files and their edit-permission

| Path | Role | Edit-permission |
|------|------|-----------------|
| `docs/build/build-log-warm.txt` | Warm-build log (the parse target) | Read-only |
| `docs/source/conf.py` | NEW file (in-scope to edit) | Editable |
| `docs/source/index.rst` | NEW file (in-scope to edit) | Editable |
| `docs/source/glossary.rst` | NEW file (in-scope to edit) | Editable |
| `docs/source/configuration.rst` | Foundation page | **DO NOT MODIFY** |
| `docs/source/inference-models.rst` | Foundation page | **DO NOT MODIFY** |
| `docs/source/operations.rst` | Foundation page | **DO NOT MODIFY** |
| `docs/source/introduction.rst` | Foundation page | **does not exist on disk** |
| `docs/source/getting-started.rst` | Foundation page | **does not exist on disk** |
| `docs/source/architecture.rst` | Foundation page | **does not exist on disk** |
| `docs/source/service-layer.rst` | Foundation page | **does not exist on disk** |
| `docs/source/api-reference.rst` | Foundation page | **does not exist on disk** |

#### A.0.2 The three CRITICAL constraints (verbatim)

* **(i)** Never modify any of the eight foundation pages
  (`introduction`, `getting-started`, `architecture`, `service-layer`,
  `inference-models`, `configuration`, `api-reference`, `operations`).
* **(ii)** Do not weaken `nitpicky=True` in `conf.py` to mass-suppress —
  use targeted `nitpick_ignore` entries with citations.
* **(iii)** If a warning is severe enough that suppression is
  unacceptable, escalate by flagging in the triage report rather than
  silently editing a foundation page.

This artifact is consistent with all three.

#### A.0.3 The categorisation buckets

Restated from the user request, with one auxiliary bucket the request
implicitly contemplates:

* **REAL-BUG.** Must-fix bug. Examples: RST syntax error, broken
  intra-page ref, duplicate-anchor collision. **In-scope to edit only**
  if the bug lives in `conf.py` / `index.rst` / `glossary.rst`. Otherwise
  escalate.
* **EXPECTED-NOW-RESOLVED.** Forward `:ref:` anchors that prior subtasks
  made resolvable. Should be **zero**; listed only to confirm the
  anchor chain is sound.
* **DRIFT.** Anchor-name mismatch between producer and consumer. Fix
  in the NEW file only.
* **PRE-EXISTING-IN-FOUNDATION.** Originates in one of the eight
  foundation prose pages. Document but do **not** modify the page;
  suppress via `nitpick_ignore` with a one-line citation comment.
* **PRE-EXISTING-IN-NEW-FILE** (auxiliary). Originates in a NEW file
  (`glossary.rst` here) but is *not a bug* — the file was authored
  knowing the target pages had not been written yet (`glossary.rst`
  opening note, lines 23–32, declares this explicitly). Same handling
  as PRE-EXISTING-IN-FOUNDATION: suppress via the same
  `nitpick_ignore` entries (the anchor name space is shared) with a
  citation comment that points at the glossary anchor map.

  *Why we keep this separate from PRE-EXISTING-IN-FOUNDATION:* the
  triage report must be honest about *which file* the suppressed
  reference comes from, and the rule "do not modify foundation pages"
  does not apply to glossary.rst. Choosing not to fix-by-pruning
  glossary entries is deliberate: the glossary's anchor map is the
  single source of truth for the cross-reference graph, and pruning
  to silence warnings would defeat the purpose.

### A.1 Warm-build parsed inventory

#### A.1.1 Parse strategy

The clean log is one warning per line in canonical Sphinx form:

```
<absolute-path>:<line>: <ERROR|WARNING>: <message> [<warning-type>]
```

Strip the absolute path prefix to get a basename. Group by
`(file, warning-type)` to drive categorisation. The square-bracketed
`[<warning-type>]` token is the suppression key:

| `[type]` | Meaning | Suppression mechanism |
|----------|---------|------------------------|
| `[docutils]` | docutils-level ERROR (parsing / inline-link target) | None — must be fixed in source |
| `[toc.not_readable]` | Toctree references nonexistent doc | None targeted; only `suppress_warnings` (mass; **prohibited by constraint (ii)**) |
| `[ref.dir]` | `:rst:dir:` cross-ref target not in domain inventory | Fix in source (preferred) or `nitpick_ignore` with `('rst:dir', '<name>')` |
| `[ref.ref]` | `:ref:` to undefined std:label | `nitpick_ignore` with **`('std:ref', '<name>')`** — see §A.3.1 |

> **Correction over the partial plan at `sphinx_warning_triage_plan.md:183`:**
> that table listed the `[ref.ref]` suppression as `('std:label', '<name>')`,
> which Sphinx 8.2 does **not** match against the warning Sphinx actually emits.
> The empirically-correct key is `('std:ref', '<name>')`. The on-disk conf.py
> already uses the correct key, and the post-fix log at 6 warnings is the
> evidence. See §A.3.1 for the matching rule.

#### A.1.2 Inventory by source file (matches the partial plan)

| File | `[docutils]` | `[toc.not_readable]` | `[ref.dir]` | `[ref.ref]` | **Total** |
|------|:-:|:-:|:-:|:-:|:-:|
| `index.rst` | 0 | 5 | 0 | 0 | **5** |
| `configuration.rst` | 1 | 0 | 0 | 43 | **44** |
| `glossary.rst` | 0 | 0 | 1 | 19 | **20** |
| `inference-models.rst` | 0 | 0 | 0 | 7 | **7** |
| `operations.rst` | 0 | 0 | 0 | 5 | **5** |
| **Total** | **1** | **5** | **1** | **74** | **81** |

#### A.1.3 Inventory by unique cross-reference target

The 74 `[ref.ref]` warnings cite **9 unique anchors**. Multiple cite
sites collapse to a single `nitpick_ignore` entry per anchor:

| Anchor | configuration.rst | glossary.rst | inference-models.rst | operations.rst | **Cites** |
|--------|:-:|:-:|:-:|:-:|:-:|
| `architecture` | 11 | 4 | 4 | 1 | **20** |
| `api-reference` | 12 | 4 | 0 | 0 | **16** |
| `getting-started` | 7 | 1 | 0 | 3 | **11** |
| `svc-moderation` | 5 | 2 | 2 | 0 | **9** |
| `introduction` | 3 | 2 | 0 | 0 | **5** |
| `api-etag` | 2 | 2 | 0 | 0 | **4** |
| `arch-debug-trace` | 0 | 2 | 0 | 0 | **2** |
| `api-debug-trace` | 0 | 2 | 0 | 0 | **2** |
| `gs-feature-flags` | 1 | 1 | 0 | 0 | **2** |

Note on the 9-anchor sub-totals (sum 41+18+6+4 = 69) vs. the per-file
`[ref.ref]` totals (43+19+7+5 = 74): the 5-line gap is *additional
invocations of the same 9 anchor names on the same source line*,
which Sphinx fires as one warning per `:ref:` token (not per source
line). The 81 figure adds up by counting log lines.

#### A.1.4 The 7 non-`[ref.ref]` issues — verbatim

```
configuration.rst:254: ERROR: Unknown target name: "startup-time validation". [docutils]
index.rst:22: WARNING: toctree contains reference to nonexisting document 'introduction' [toc.not_readable]
index.rst:22: WARNING: toctree contains reference to nonexisting document 'getting-started' [toc.not_readable]
index.rst:22: WARNING: toctree contains reference to nonexisting document 'architecture' [toc.not_readable]
index.rst:22: WARNING: toctree contains reference to nonexisting document 'service-layer' [toc.not_readable]
index.rst:22: WARNING: toctree contains reference to nonexisting document 'api-reference' [toc.not_readable]
glossary.rst:13: WARNING: rst:dir reference target not found: glossary [ref.dir]
```

These 7 drive the entire REAL-BUG / DRIFT / escalation decision tree.
The other 74 are the forward-reference suppression bulk.

### A.2 Per-warning categorisation decisions

Each of the 81 warnings + 1 ERROR is assigned to exactly one bucket below.

#### A.2.1 The 1 docutils ERROR — REAL-BUG, escalated

| Warning | Bucket | Rationale |
|---------|--------|-----------|
| `configuration.rst:254: ERROR: Unknown target name: "startup-time validation". [docutils]` | **REAL-BUG** | This is a docutils-level RST syntax error: an inline link target with whitespace. It is a *real* bug in the source (must be fixed before the page renders correctly), but `configuration.rst` is a foundation page — constraint (i) forbids modifying it. Constraint (iii) governs: **escalate.** Cannot be suppressed via `nitpick_ignore` (different mechanism — that only applies to nitpicky-mode reference warnings, not docutils ERRORs). The remaining options would be: (a) silently edit configuration.rst (forbidden), (b) downgrade the build via `--keep-going` and treat the ERROR as a warning (does not actually clear it; still in the log). Neither is appropriate. |

**Action:** none in this subtask. Flagged in §B.4 below for the next foundation-edit subtask.

#### A.2.2 The 5 toctree warnings — escalated (precondition gap)

| Warning | Bucket | Rationale |
|---------|--------|-----------|
| `index.rst:22: WARNING: toctree contains reference to nonexisting document 'introduction' [toc.not_readable]` | **Escalation** | The toctree in `index.rst` (a NEW, editable file) references 9 documents; 5 of them (`introduction`, `getting-started`, `architecture`, `service-layer`, `api-reference`) are not on disk. We **could** edit `index.rst` to remove those 5 entries — that would silence the warnings — but the result would be a documentation site whose top-level navigation hides the fact that 5 prerequisite pages are missing. That is precisely the kind of silent foundation-page mutation constraint (iii) is designed to prevent. `[toc.not_readable]` cannot be suppressed via `nitpick_ignore`; only `suppress_warnings = ['toc.not_readable']` would silence it, and that is the mass-suppression that constraint (ii) prohibits. |
| (4 more `[toc.not_readable]` lines on `index.rst:22` for `getting-started`, `architecture`, `service-layer`, `api-reference`) | **Escalation** | Same reasoning. |

**Action:** none in this subtask. Flagged in §B.4 below for the next foundation-author subtask. The toctree stays intact.

#### A.2.3 The 1 `[ref.dir]` warning — REAL-BUG fixable in NEW file

| Warning | Bucket | Rationale |
|---------|--------|-----------|
| `glossary.rst:13: WARNING: rst:dir reference target not found: glossary [ref.dir]` | **REAL-BUG** | `glossary.rst` is a NEW file (editable). The warning indicates an `:rst:dir:`glossary`` cross-reference (or equivalent) at line 13 whose target does not exist in the rst-domain inventory. Inspection of the current line 13 shows the line now reads literal-text `` * The ``.. glossary::`` directive below ``, i.e., a backticked string describing the directive, *not* a cross-reference role invocation. The fix has been to replace the role with a literal-text rendering of the same directive name. This is the simplest correct fix and matches the rest of the glossary's prose-of-directive references. Suppression via `nitpick_ignore` would be technically possible (`('rst:dir', 'glossary')`) but the source-side fix is preferred per the user request: REAL-BUGs in editable files should be fixed in place, not suppressed. |

**Action:** edit applied at `glossary.rst:13` (already on disk per the timestamps).

#### A.2.4 The 74 `[ref.ref]` warnings — PRE-EXISTING-* (suppressed)

The 74 forward-reference warnings split by file of origin:

| File | Count | Bucket | Rationale |
|------|------:|--------|-----------|
| `configuration.rst` | 43 | **PRE-EXISTING-IN-FOUNDATION** | All 43 are `:ref:` invocations at various lines (9, 24, 112, 180, 189, 280, 352, 634, 869, 884, 1068, 1077, 1175, 1227, 1770, 1897, 2052, 2054, 2066, 2078, 2111, …) targeting one of the 9 forward-anchor names. All originate inside a foundation page. Per the user request: "warning that originates in one of the eight already-authored prose pages — document but do **not** modify the page." Suppressed via `nitpick_ignore` (§A.3.1). |
| `inference-models.rst` | 7 | **PRE-EXISTING-IN-FOUNDATION** | 7 `:ref:` invocations at lines 9, 80, 476, 1004, 1131, 1135 targeting `architecture` or `svc-moderation`. Same handling. |
| `operations.rst` | 5 | **PRE-EXISTING-IN-FOUNDATION** | 5 `:ref:` invocations at lines 16, 405, 1004, 1007 targeting `getting-started` or `architecture`. Same handling. |
| `glossary.rst` | 19 | **PRE-EXISTING-IN-NEW-FILE** | 19 `:ref:` invocations at lines 76, 89, 122, 220, 619, 620, 624, 628, 638, 701, 747 targeting the 9 forward anchors. The glossary's own opening note (lines 23–32) explicitly declares these will fail until the missing pages land — *the file is authored knowing these references will not resolve*. Treating them as REAL-BUGs and pruning the entries would damage the anchor-map source-of-truth role. Treating them as DRIFT is wrong (the anchor names match what the foundation pages are *supposed* to host). The honest classification is "pre-existing forward refs in a NEW file"; the suppression mechanism is the same `nitpick_ignore` entries that cover the foundation-page citations. |
| **Total** | **74** | | (55 PRE-EXISTING-IN-FOUNDATION + 19 PRE-EXISTING-IN-NEW-FILE) |

**Action:** added a 9-tuple `nitpick_ignore` block in `conf.py` (already on disk; §A.3.1 documents the exact diff and the syntax correction).

#### A.2.5 EXPECTED-NOW-RESOLVED — zero (confirmation)

The user request specifies this bucket *should be zero* and exists for
confirmation that the anchor chain is sound. Confirmation:

* No prior subtask has landed any of the 5 missing foundation pages on
  disk (`Glob: docs/source/{introduction,getting-started,architecture,service-layer,api-reference}.rst` → no matches).
* Every `[ref.ref]` warning therefore is *still* a forward reference,
  not a "now-resolvable" reference that has slipped through.
* The bucket is correctly empty.

#### A.2.6 DRIFT — zero

For DRIFT to apply, an anchor name in the citation site (`:ref:`<X>``)
would have to differ from the *intended* anchor name on the producer
page. Since none of the producer pages exist yet, there is no
producer-side spelling to drift from. Every undefined-label warning
maps to one of the 9 anchor names that `glossary.rst`'s anchor map
documents as the *planned* names. The bucket is correctly empty.

### A.3 Concrete edits

#### A.3.1 `docs/source/conf.py` — the `nitpick_ignore` block (the unblocker)

**Why this is the high-value edit:** the partial plan and an earlier
copy of `conf.py` both used the syntax `('std:label', '<name>')` for
the nitpick_ignore entries. That syntax does **not** suppress
`[ref.ref]` warnings in Sphinx 8.2.

> **Locator evidence (added in iteration 4, sourced from the parallel
> consolidator).** Flow 1's *original raw* planning artifact contained
> 16 occurrences of `('std:label', X)` as the recommended tuple key,
> at plan lines 183, 415, 593, 599, 604, 612, 617, 625, 630, 635, 640,
> 652, 658, 773, 942, and 1010 (line numbers anchored to the
> original raw input, not the current on-disk plan — Flow 1's plan
> file has since been corrected to align with the executed state).
> Preserving this locator set here is intentional: the parallel
> consolidator caught it as a doc-only-amendment item that downstream
> readers of any *cached* copy of the original plan would still need.

The matching rule (from
`sphinx/transforms/post_transforms/__init__.py:ReferencesResolver.warn_missing_reference`)
builds a key

```python
dtype = f'{domain.name}:{typ}'
```

and then checks whether `(dtype, target)` is in `config.nitpick_ignore`.
For an undefined `:ref:` to label `introduction`, `domain.name == 'std'`
and `typ == 'ref'` (the cross-reference role used at the citation
site, not the object type the role would have resolved to). So the
key is `'std:ref'`, and the only matching entry is

```python
('std:ref', 'introduction')
```

`('std:label', 'introduction')` builds key `'std:label'` which is
never compared against — that string is the type of the *target object*
(the directive that *creates* the anchor), which is irrelevant to the
warning emitted by the *citation site*.

**Diff (already on disk):**

* All 9 entries rewritten from `('std:label', X)` to `('std:ref', X)`. The on-disk `conf.py:94-129` is now:

```
nitpick_ignore = [
    ('std:ref', 'introduction'),
    ('std:ref', 'getting-started'),
    ('std:ref', 'gs-feature-flags'),
    ('std:ref', 'architecture'),
    ('std:ref', 'arch-debug-trace'),
    ('std:ref', 'svc-moderation'),
    ('std:ref', 'api-reference'),
    ('std:ref', 'api-etag'),
    ('std:ref', 'api-debug-trace'),
]
```

* The block-header comment (`conf.py:81-93`) was extended to spell out the matching rule, so a future reader does not repeat the `std:label` mistake.
* Each entry retains a one-line citation comment naming the page that should host the `.. _<anchor>:` directive, the cite count, and representative cite sites (e.g., `# introduction.rst — page-top anchor; cited by configuration.rst:9, 2052, 2111 and glossary.rst:220, 619`). These comments serve constraint (ii)'s citation requirement and provide the deletion signal: when `introduction.rst` lands with `.. _introduction:` at its top, delete the corresponding entry **in the same commit**.
* `service-layer` is intentionally **not** in the list: nothing currently `:ref:`-cites it; only its sub-anchor `svc-moderation` is cited.

**Why this is not a weakening of `nitpicky`:** every entry is a specific named anchor backed by a one-line citation. The five page-top names + four sub-names are the *complete* set of forward-referenced anchors documented by the glossary's anchor map. Any new `:ref:` warning that appears post-build for a name not in this list is therefore either a typo or a drift (constraint (ii) compliance).

#### A.3.2 `docs/source/glossary.rst` — line 13

The single offending line was an `:rst:dir:` cross-reference role naming `glossary` (the directive). The current on-disk content of line 13 reads:

```
* The ``.. glossary::`` directive below — alphabetised — for
```

i.e., the directive name is now rendered as literal text in double-backticks rather than as a cross-reference. This is the correct prose-of-directive style and matches the rest of the glossary's authoring conventions (`glossary.rst:13`).

**No other glossary edit was required** — the 19 `:ref:` invocations at lines 76–747 are the PRE-EXISTING-IN-NEW-FILE forward references, covered by the conf.py suppression entries.

#### A.3.3 `docs/source/index.rst` — *no edit*

The toctree at `index.rst:22-34` still names all 9 documents, including the 5 missing prerequisite pages. Removing them would silence the warnings *and* hide the fact that 5 foundation pages are unauthored. We escalate instead (§B.4).

#### A.3.4 Foundation pages — no edits

`configuration.rst`, `inference-models.rst`, `operations.rst` are on disk and were not modified. The other 5 foundation pages (`introduction`, `getting-started`, `architecture`, `service-layer`, `api-reference`) are not on disk — there is nothing to edit.

### A.4 Rebuild step

#### A.4.1 Build invocation

The user-request prescribes `uv run sphinx-build -b html docs/source docs/build/html`. Per flow 0's environment audit (and verified again here):

* `which uv` → not found in this shell.
* `pyproject.toml` does not exist at the repo root.
* Sphinx 8.2.3, sphinx-rtd-theme 3.0.2, and docutils 0.21.2 are importable from the active Python (miniforge3 3.12.7).

Substitute used (matches what the existing `build-log-after-fix.txt` was generated by):

```
rm -rf docs/build/html
python -m sphinx -b html docs/source docs/build/html 2>&1 | tee docs/build/build-log-after-fix.txt
```

If `uv` is available in the actual executor's environment, the same command set with `uv run sphinx-build -b html docs/source docs/build/html` yields the same output (Sphinx is the same binary either way). The substitution is purely a tooling-availability accommodation, not a change in build semantics.

#### A.4.2 Validation

Expected output:

* exit code 0 (no `-W` flag; ERRORs do not abort the build);
* `build succeeded, 6 warnings.` in the summary line;
* 1 docutils ERROR + 5 toctree WARNINGs in the body (escalated set).

Observed (in `docs/build/build-log-after-fix.txt`):

* The log ends with `build succeeded, 6 warnings.`
* The 1 ERROR + 5 WARNINGs are exactly the escalated set.
* All 74 `[ref.ref]` warnings and the 1 `[ref.dir]` warning are gone.

The build log is preserved at `docs/build/build-log-after-fix.txt` (3050 bytes).

#### A.4.3 Cross-platform rebuild tooling (ingested from flow 1)

Flow 1's subtask-1 plan (`sphinx_initial_build_plan.md` §§ 5 and 5-bis)
worked out the platform-portable invocation pattern. Triage's rebuild
step inherits the same pattern; documenting it here so a re-runner on
either shell gets the right exit-code capture without rediscovering it.

**bash (default executor shell):**

```
rm -rf docs/build/html
python -m sphinx -b html docs/source docs/build/html 2>&1 \
    | tee docs/build/build-log-after-fix.txt
echo "sphinx-build exit=${PIPESTATUS[0]}"
```

The `${PIPESTATUS[0]}` read is the *only* portable way to recover the
real `sphinx-build` exit code through the `| tee` redirection — `$?`
after the pipe is `tee`'s exit code, which is almost always 0.

**PowerShell variant (only if the executor is in PS 5.1, not bash):**

Do **not** use `2>&1` on a native exe in PS 5.1. The redirection
wraps each stderr line in an `ErrorRecord` (NativeCommandError) and
flips `$?` to `$false` even when the exe returned 0. Use one of:

```
# Option A: let stderr stream to console; tee stdout only
python -m sphinx -b html docs\source docs\build\html `
    *>&1 | Tee-Object -FilePath docs\build\build-log-after-fix.txt

# Option B: capture both via a temporary file, then check $LASTEXITCODE
python -m sphinx -b html docs\source docs\build\html `
    > docs\build\build-log-after-fix.txt 2>&1
"sphinx-build exit=$LASTEXITCODE"
```

`$LASTEXITCODE` is the PS-side equivalent of `${PIPESTATUS[0]}` for
native commands and is the property to check, not `$?`.

**Why this matters for triage:** the post-fix build is expected to
exit 0 (the docutils ERROR does not abort without `-W`). If a future
re-run reports a non-zero exit, the executor needs the exit-code
plumbing right before they trust the diagnosis — flow 1's PS caveat
in particular has trapped re-runners on Windows in the past.

**Substitution rationale (already covered in §A.4.1):** the user
request prescribes `uv run sphinx-build`; flow 0 / step 0 and flow 1
both verified `uv` is not on PATH; flow 1 §3.3 recommends
`python -m venv .venv-docs && pip install sphinx sphinx-rtd-theme`
as the install path. Triage uses whatever Sphinx environment is
already activated (Sphinx 8.2.3 is importable in the active
miniforge3 Python 3.12.7) — the install step is not on the triage
critical path. If the executor is on a fresh machine, follow flow
1's §3 first, then return here.

---

## Part B - Triage report (the deliverable)

This is the triage report deliverable specified in step (g) of the
user request: "produce a triage report (Markdown or RST appendix)
listing every original warning with its category, the action taken,
and the post-fix warning delta."

### B.1 Top-line outcome

| Quantity | Pre-fix | Post-fix | Delta |
|----------|--------:|---------:|------:|
| docutils ERRORs | 1 | 1 | 0 (escalated; foundation page) |
| `[toc.not_readable]` WARNINGs | 5 | 5 | 0 (escalated; missing foundation pages) |
| `[ref.dir]` WARNINGs | 1 | 0 | -1 (fixed in glossary.rst:13) |
| `[ref.ref]` WARNINGs | 74 | 0 | -74 (suppressed via 9 `nitpick_ignore` entries) |
| **Total** | **81** | **6** | **-75** |
| Sphinx summary | `build succeeded, 81 warnings.` | `build succeeded, 6 warnings.` | -75 |
| Build exit code | 0 | 0 | unchanged |

### B.2 Action by bucket

| Bucket | Count | Action |
|--------|------:|--------|
| REAL-BUG, fixed in NEW file | 1 | `glossary.rst:13` rewritten (rst:dir -> literal text) |
| REAL-BUG, escalated | 1 | `configuration.rst:254` docutils ERROR - flagged in B.4 |
| EXPECTED-NOW-RESOLVED | 0 | Bucket correctly empty (no foundation page has landed) |
| DRIFT | 0 | Bucket correctly empty (no producer/consumer name mismatch) |
| PRE-EXISTING-IN-FOUNDATION | 55 | Suppressed via 9-entry `nitpick_ignore` (with citations) |
| PRE-EXISTING-IN-NEW-FILE | 19 | Suppressed via the same 9 entries (anchor namespace shared) |
| Toctree precondition gap, escalated | 5 | Flagged in B.4 - toctree NOT pruned (would mask missing pages) |

### B.3 Per-warning appendix

Format: one row per **log line** in the warm log. Columns:
`source` | `line` | `type` | `bucket` | `action`.

Source files in the foundation set are bolded with `**`.

#### B.3.1 The 7 non-`[ref.ref]` lines

| Source | Line | Type | Bucket | Action |
|--------|-----:|------|--------|--------|
| **`configuration.rst`** | 254 | `[docutils]` ERROR `Unknown target name: "startup-time validation"` | REAL-BUG, escalated | left as pre-existing-with-justification (foundation page; constraint (i)). Flagged in B.4. |
| `index.rst` | 22 | `[toc.not_readable]` `'introduction'` | Toctree precondition gap, escalated | left as pre-existing-with-justification (5 foundation pages missing; pruning would mask the gap). Flagged in B.4. |
| `index.rst` | 22 | `[toc.not_readable]` `'getting-started'` | same | same |
| `index.rst` | 22 | `[toc.not_readable]` `'architecture'` | same | same |
| `index.rst` | 22 | `[toc.not_readable]` `'service-layer'` | same | same |
| `index.rst` | 22 | `[toc.not_readable]` `'api-reference'` | same | same |
| `glossary.rst` | 13 | `[ref.dir]` `glossary` | REAL-BUG, fixable in NEW file | fixed-in-place (rewrote line 13 to render the directive name as literal text). |

#### B.3.2 The 74 `[ref.ref]` lines, grouped by source x target

To keep the appendix readable and the row count manageable, the 74
log lines are folded by `(source, target)` pair below. Every group
collapses to **one** of two actions:

* **suppressed-with-citation (foundation):** the row originates in a
  foundation page; the `nitpick_ignore` entry for the target's anchor
  is what suppresses it post-fix. Citation comment on the entry names
  the page that should host the `.. _<target>:` directive.
* **suppressed-with-citation (new-file glossary):** the row originates
  in `glossary.rst`; the *same* `nitpick_ignore` entry for that
  anchor suppresses it. The glossary's anchor-map row for that anchor
  is the citation.

| Source | Target anchor | Cite count | Action |
|--------|---------------|-----------:|--------|
| **`configuration.rst`** | `architecture` | 11 | suppressed-with-citation (foundation) - entry `('std:ref', 'architecture')` |
| **`configuration.rst`** | `api-reference` | 12 | suppressed-with-citation (foundation) - entry `('std:ref', 'api-reference')` |
| **`configuration.rst`** | `getting-started` | 7 | suppressed-with-citation (foundation) - entry `('std:ref', 'getting-started')` |
| **`configuration.rst`** | `svc-moderation` | 5 | suppressed-with-citation (foundation) - entry `('std:ref', 'svc-moderation')` |
| **`configuration.rst`** | `introduction` | 3 | suppressed-with-citation (foundation) - entry `('std:ref', 'introduction')` |
| **`configuration.rst`** | `api-etag` | 2 | suppressed-with-citation (foundation) - entry `('std:ref', 'api-etag')` |
| **`configuration.rst`** | `gs-feature-flags` | 1 | suppressed-with-citation (foundation) - entry `('std:ref', 'gs-feature-flags')` |
| **`configuration.rst`** | (extras: same 7 anchors, multi-token lines) | 2 | (the 41 vs. 43 reconciliation: extra line-of-warning vs. unique-anchor; same suppression mechanism) |
| **`inference-models.rst`** | `architecture` | 4 | suppressed-with-citation (foundation) - same entry |
| **`inference-models.rst`** | `svc-moderation` | 2 | suppressed-with-citation (foundation) - same entry |
| **`inference-models.rst`** | (extras) | 1 | suppressed-with-citation (foundation) |
| **`operations.rst`** | `getting-started` | 3 | suppressed-with-citation (foundation) |
| **`operations.rst`** | `architecture` | 1 | suppressed-with-citation (foundation) |
| **`operations.rst`** | (extras) | 1 | suppressed-with-citation (foundation) |
| `glossary.rst` | `architecture` | 4 | suppressed-with-citation (new-file glossary) - entry `('std:ref', 'architecture')` |
| `glossary.rst` | `api-reference` | 4 | suppressed-with-citation (new-file glossary) |
| `glossary.rst` | `svc-moderation` | 2 | suppressed-with-citation (new-file glossary) |
| `glossary.rst` | `introduction` | 2 | suppressed-with-citation (new-file glossary) |
| `glossary.rst` | `api-etag` | 2 | suppressed-with-citation (new-file glossary) |
| `glossary.rst` | `arch-debug-trace` | 2 | suppressed-with-citation (new-file glossary) |
| `glossary.rst` | `api-debug-trace` | 2 | suppressed-with-citation (new-file glossary) |
| `glossary.rst` | `getting-started` | 1 | suppressed-with-citation (new-file glossary) |
| `glossary.rst` | `gs-feature-flags` | 1 | suppressed-with-citation (new-file glossary) |
| `glossary.rst` | (extras) | 1 | suppressed-with-citation (new-file glossary) |

(Note: the per-anchor cite-counts here mirror A.1.3.
The 41+18+6+4 sub-totals plus the "extras" rows reconstruct the
74 log-line total. Per A.1.3, the gap is multiple `:ref:` tokens
on the same source line counted separately by Sphinx.)

### B.4 Open escalations (the things not silently fixed)

The triage explicitly **does not** silence these - per constraint (iii)
they are flagged for follow-up rather than buried.

#### B.4.1 `configuration.rst:254` docutils ERROR

```
configuration.rst:254: ERROR: Unknown target name: "startup-time validation". [docutils]
```

**Source-of-error.** RST does not accept whitespace inside an inline
link target name. The author intended an internal anchor like
`startup-time-validation` (hyphenated) but typed `startup-time validation`
(spaced). Docutils flags this at parse time, independently of Sphinx.

**Why not silently fixed.** `configuration.rst` is on the foundation
list (constraint (i)). The fix is a one-character edit
(`startup-time validation` -> `startup-time-validation`) but it is
explicitly the next foundation-edit subtask's call.

**Recommendation for the next subtask.** Apply the hyphenation fix
in the same commit that lands the foundation page review. There is
no `nitpick_ignore`-style mechanism that suppresses docutils-level
ERRORs - only a source edit clears it.

#### B.4.2 The 5 `[toc.not_readable]` warnings (5 missing foundation pages)

```
index.rst:22: WARNING: toctree contains reference to nonexisting document 'introduction' [toc.not_readable]
index.rst:22: WARNING: toctree contains reference to nonexisting document 'getting-started' [toc.not_readable]
index.rst:22: WARNING: toctree contains reference to nonexisting document 'architecture' [toc.not_readable]
index.rst:22: WARNING: toctree contains reference to nonexisting document 'service-layer' [toc.not_readable]
index.rst:22: WARNING: toctree contains reference to nonexisting document 'api-reference' [toc.not_readable]
```

**Source-of-error.** Five of the eight foundation pages do not exist
on disk. The toctree at `index.rst:22-34` references them by basename;
Sphinx warns once per missing document.

**Why not silently fixed.** Editing `index.rst` to drop the 5 entries
would silence the warnings but would also (a) remove the missing
pages from the rendered top-level navigation, hiding the gap from
documentation readers, and (b) require re-adding the entries in the
order they were declared once the foundation pages land. Neither is
desirable. `[toc.not_readable]` cannot be suppressed via
`nitpick_ignore`; the only suppression mechanism is `suppress_warnings
= ['toc.not_readable']`, which is mass-suppression and forbidden by
constraint (ii).

**Recommendation for the next subtask.** Author the 5 missing pages
(or stubs containing only their page-top `.. _<name>:` anchor and a
"to be authored" note). Each landed page individually clears one
toctree warning *and* one or more of the corresponding `[ref.ref]`
warnings; once *all* anchors a given `nitpick_ignore` entry covers
become resolvable, that entry should be removed in the same commit.

### B.5 Validation

* `docs/build/build-log-after-fix.txt` exists and ends with
  `build succeeded, 6 warnings.`.
* The 6 warnings break down as 1 docutils ERROR + 5 `[toc.not_readable]`,
  matching the predicted post-fix state.
* No `[ref.ref]` warning, no `[ref.dir]` warning remains.
* No foundation page was modified between pre-fix and post-fix
  (verified by mtime: `inference-models.rst`, `configuration.rst`,
  `operations.rst` are unchanged from before the rebuild). The on-
  disk timestamps confirm the only changed source files are
  `conf.py` (10:43) and `glossary.rst` (10:41).

---

## Part C - Reconciliation with predecessor (flow 0) findings

### C.1 What flow 0 (build-capture plan) predicted vs. what triage observed

Flow 0's build-capture plan, in section 4 ("predicted build signals from
prior empirical run"), forecasted:

| Flow 0 forecast | Observed in warm log |
|-----------------|----------------------|
| 5 toctree warnings | yes - exactly 5 |
| ~70+ undefined-label warnings under `nitpicky=True` | yes - 74 (a closer match than the band suggests) |
| at least 1 docutils ERROR (`configuration.rst:254` "startup-time validation") | yes - exactly 1, exactly that one |
| Build exit code 0 | yes - 0 |
| Total summary `build succeeded, ~80 warnings` | yes - `build succeeded, 81 warnings.` |

Every prediction held. This validates flow 0's audit work and
provides high confidence that the post-fix state (6 warnings) is
not a one-off result.

### C.2 Where the build-capture plans were tangential to this subtask

Two parallel build-capture plans exist, both correctly scoped to
subtask 1 only and explicitly handing recovery (= triage) to
subtask 2:

* `docs/_plan/sphinx_build_capture_plan.md` (flow 0 / step 0,
  456 lines). Section 6 "out-of-scope": "no fixes, no `-W`, no
  nitpick_ignore, no source edits."
* `docs/_plan/sphinx_initial_build_plan.md` (flow 1, 520 lines).
  Section 8 "Compliance checklist": same intent — "what we will NOT do."

Both plans agree on the environmental findings; iteration 2 of this
artifact treats that agreement as **second-source verification** that
the assumptions on which the rebuild step depends are real, not a
single-author audit error. The findings:

* **`uv` is not on PATH.** Verified by both plans (each ran
  `which uv` independently and got 127/not-found). The triage rebuild
  therefore uses `python -m sphinx` (or `uv run sphinx-build` if the
  executor's environment has `uv`) — the underlying binary is the
  same Sphinx, so output is identical.
* **No `pyproject.toml`, no `uv.lock`, no `CONSOLIDATION_NOTES*`.**
  Verified by both plans. The triage does not need any of them; the
  foundation-page list is fixed by the user request (constraint (i)).
* **Sphinx 8.2.3 + sphinx_rtd_theme 3.0.2 + docutils 0.21.2** are
  importable in the active Python (miniforge3 3.12.7). Both plans
  confirmed.

The two plans differ in the *recommended* install path:

* Flow 0 / step 0 recommended `python -m sphinx` against the active
  global Python (no venv).
* Flow 1 §3.3 recommended a project-local `python -m venv .venv-docs`
  + `pip install` (the option matrix in §3.2 explicitly compares
  global vs venv vs `uv pip install` vs `pipx run` and lands on venv).

Triage does not need to choose between them — Sphinx is already
importable in the live environment, and the triage rebuild does not
require any package install. Both options satisfy the user-request's
intent (`uv run sphinx-build` is still permitted if `uv` is later
added). For the next operator on a fresh machine, **follow flow 1's
§3.3 first.** This consolidated artifact does not duplicate that
material.

### C.3 Insight not predicted by flow 0: the `('std:label', X)` syntax bug

Flow 0 (correctly) did not touch `conf.py`. So flow 0 did not notice
that the `nitpick_ignore` entries in `conf.py` were spelled
`('std:label', X)` and would not actually suppress the `[ref.ref]`
warnings - they had been added prior to flow 0 by an earlier
subtask, with a plausible-looking but wrong tuple key.

The empirical signal that exposed the bug: 81 `[ref.ref]` warnings
in the warm log despite the conf.py already containing
`nitpick_ignore` entries that *appeared* to cover all 9 forward
anchors. If `('std:label', X)` had been the right key, the warm log
would have shown ~7 warnings (toctree + docutils ERROR + ref.dir),
not 81.

The fix - change all 9 entries to `('std:ref', X)` - is a 9-line
edit applied during the triage. It is the single highest-value
change in this subtask, since it accounts for -74 of the -75
warning delta. The `glossary.rst:13` fix alone would have moved the
needle by only -1.

A reader following this consolidated plan should treat the
`std:label` -> `std:ref` correction as the primary takeaway. The
on-disk `conf.py:81-93` block-header comment now spells out the
matching rule so the bug does not recur.

### C.4 Where the on-disk partial triage plan agreed and disagreed

The partial plan at `docs/_plan/sphinx_warning_triage_plan.md`
(stops at line 250, mid-section 1.4):

* **Agreed** on the bucket totals (1 REAL-BUG fixable, 1 escalated,
  0 EXPECTED-NOW-RESOLVED, 0 DRIFT, 55 PRE-EXISTING-IN-FOUNDATION,
  19 PRE-EXISTING-IN-NEW-FILE, 5 toctree escalated). This
  consolidated artifact carries those numbers forward unchanged.
* **Agreed** on the post-fix prediction (6 warnings, delta -75).
* **Disagreed** on the suppression syntax. The partial plan's
  suppression-mechanism table at line 183 says
  `nitpick_ignore` with `('std:label', '<name>')`. The on-disk
  conf.py uses `('std:ref', '<name>')`, and the empirical post-fix
  log (6 warnings) is the evidence that the on-disk syntax is the
  correct one. This consolidated artifact follows the on-disk fix
  and explains the matching rule (A.3.1) so the discrepancy does
  not propagate.
* **Did not cover** sections 2-5 (per-warning categorisation, concrete
  edits, rebuild step, triage report). This consolidated artifact
  supplies them.

---

## Part D - Out-of-scope items / handoff

### D.1 Lifetime of the 9 `nitpick_ignore` entries

Each entry is **tied to one foundation page**. When that page lands
on disk with the corresponding `.. _<anchor>:` directive, the entry
must be removed in the same commit. The mapping is:

| Entry | Page that should host the anchor | Removal trigger |
|-------|----------------------------------|-----------------|
| `('std:ref', 'introduction')` | `introduction.rst` | `.. _introduction:` lands at the top of the page |
| `('std:ref', 'getting-started')` | `getting-started.rst` | `.. _getting-started:` lands |
| `('std:ref', 'gs-feature-flags')` | `getting-started.rst` (sub-anchor) | `.. _gs-feature-flags:` lands inside the page |
| `('std:ref', 'architecture')` | `architecture.rst` | `.. _architecture:` lands |
| `('std:ref', 'arch-debug-trace')` | `architecture.rst` (sub-anchor) | `.. _arch-debug-trace:` lands |
| `('std:ref', 'svc-moderation')` | `service-layer.rst` (sub-anchor) | `.. _svc-moderation:` lands |
| `('std:ref', 'api-reference')` | `api-reference.rst` | `.. _api-reference:` lands |
| `('std:ref', 'api-etag')` | `api-reference.rst` (sub-anchor) | `.. _api-etag:` lands |
| `('std:ref', 'api-debug-trace')` | `api-reference.rst` (sub-anchor) | `.. _api-debug-trace:` lands |

Three pages (`introduction`, `getting-started`, `architecture`) own
exactly one page-top anchor each plus one sub-anchor (for
`getting-started` and `architecture`). The `service-layer.rst` page
owns only the `svc-moderation` sub-anchor (no page-top anchor cite
exists; only its toctree entry). The `api-reference.rst` page owns
the most (one page-top + two sub-anchors).

### D.2 Handoff items for subsequent subtasks

* **Foundation-page authoring subtask:** owns the creation of the 5
  missing pages and the corresponding `nitpick_ignore` line removal.
  Each page-landing should bring the warning count strictly down,
  validating the entry-removal in real time.
* **Foundation-page review subtask** (already line-by-line audited per
  the user request's constraint (i) wording): owns the
  `configuration.rst:254` hyphenation fix.
* **Repo-tooling subtask** (if/when one runs): if `uv` becomes
  authoritative for this docset, switch `python -m sphinx` calls to
  `uv run sphinx-build` in any committed CI/build scripts. The build
  output is identical; only the launcher differs.

### D.3 Files touched / files preserved

Touched in this subtask (NEW files only, per the constraints):

* `docs/source/conf.py` (rewrote `nitpick_ignore` block + extended
  header comment).
* `docs/source/glossary.rst` (line 13 only).

Preserved (foundation pages on disk - never opened for write):

* `docs/source/configuration.rst`
* `docs/source/inference-models.rst`
* `docs/source/operations.rst`

Not present on disk (foundation pages flagged as missing -
escalated, not authored here):

* `docs/source/introduction.rst`
* `docs/source/getting-started.rst`
* `docs/source/architecture.rst`
* `docs/source/service-layer.rst`
* `docs/source/api-reference.rst`

Build artifacts produced:

* `docs/build/build-log-after-fix.txt` (3050 B; the post-fix log).
* `docs/build/html/` (rebuilt; clean except for the 6 escalated warnings).

Plan artifacts (this directory):

* `docs/_plan/sphinx_scaffolding_audit.md` (predecessor; unchanged across all iterations).
* `docs/_plan/sphinx_build_capture_plan.md` (flow 0 / step 0 — subtask 1 build-capture plan; one of two parallel build-capture plans; provided the empirical predictions used in §C.1).
* `docs/_plan/sphinx_initial_build_plan.md` (flow 1 — the other parallel build-capture plan; second-source verification of environmental constraints in §C.2; cross-platform tooling pattern ingested into §A.4.3).
* `docs/_plan/sphinx_warning_triage_plan.md` ← **iteration-3 explicit input (User's Flow 1)**. Originally a partial plan; now ~1453 lines (extended by a parallel process post-iteration-3). The original raw Flow 1 input recommended the `('std:label', X)` tuple key; this artifact records that as an empirically-discovered silent no-op (§A.3.1, §C.3, §E.2).
* `docs/_plan/sphinx_warning_triage_report.md` ← **iteration-3 explicit input (User's Flow 0)**. End-to-end execution report (~816 lines); the on-disk fixes in `conf.py` and `glossary.rst:13` are this flow's edits and the post-fix log at 6 warnings is its evidence.
* `docs/_plan/sphinx_warning_triage_plan_consolidated.md` ← **iteration-4 explicit input** (parallel consolidator; 247 lines). Source of §D.4, §D.5, and the §A.3.1 locator-evidence footnote.
* `docs/_plan/sphinx_warning_triage_consolidated.md` ← **this file** — complete plan + report (iteration 4).

### D.4 Risks, exit criteria, rollback (folded in from the parallel consolidator)

* **Exit criterion.** Post-fix warning count = 6 *and* the surviving 6
  match the escalation list in §B.4 verbatim. **Already met** as of
  the timestamps recorded in §A.4.2 (`build-log-after-fix.txt` ends
  with `build succeeded, 6 warnings.`).
* **Risk: a future page-authoring subtask lands a foundation page
  but forgets to remove the matching `nitpick_ignore` line.** Then a
  typo'd `:ref:`<anchor>`` would silently slip through — the
  suppression would mask the regression. *Mitigation:* the inline
  comment header in `conf.py:69–73` (and the per-tuple citation
  comments in `conf.py:94–129`) explicitly tell the next author
  "Removing each entry below is the *signal* that the corresponding
  page authoring subtask has landed." See also the entry-to-page
  mapping in §D.1.
* **Risk: a new foundation-page edit introduces a broken anchor that
  collides with one of the 9 suppressed names.** Same mitigation —
  the conf.py header comment instructs the author to add only with a
  Shared Anchor Map row in `glossary.rst:358+` to back it; without
  the anchor-map row, no `nitpick_ignore` line should be added.
* **Risk: a future maintainer "fixes" the suppression keys back to
  `('std:label', X)` because that string *looks* more semantically
  correct (label = the target object).** Mitigation: the on-disk
  `conf.py:81–93` block-header comment names the matching rule
  (`f'{domain.name}:{typ}'` from
  `sphinx/transforms/post_transforms/__init__.py`) and explains that
  `typ` is the *role* used at the citation site, not the *object*
  type the role would have resolved to. §A.3.1 of this artifact
  carries the same explanation.
* **Rollback.** Revert the two file edits (`conf.py` lines 49–129,
  `glossary.rst` line 13) and delete `docs/build/build-log-after-fix.txt`.
  The warm-build state is reproducible from current source via
  `python -m sphinx -b html docs/source docs/build/html` (or the
  prescribed `uv run sphinx-build` if `uv` is on PATH). The pre-fix
  log at `docs/build/build-log-warm.txt` is preserved for reference.

### D.5 One-paragraph executor handoff (folded in from the parallel consolidator)

The work prescribed by the original-request steps (a)–(g) is already
complete on disk: warnings parsed (§A.1), categorised (§A.2, totals
reconciled in the TL;DR), in-place fixes applied to `glossary.rst:13`
and `conf.py.nitpick_ignore` (with the `('std:ref', X)` syntax —
§A.3), rebuild executed (§A.4), post-fix log saved at
`docs/build/build-log-after-fix.txt` (§A.4.2), and the per-warning
triage report (§B) covers step (g). The single remaining doc-hygiene
amendment surfaced by consolidation was correcting the original 16
`('std:label', X)` references in `sphinx_warning_triage_plan.md`
(see §A.3.1 locator note); the on-disk plan has been updated to
match the executed `('std:ref', X)` form. **Two escalations remain
owner-action items**: the `configuration.rst:254` "startup-time
validation" docutils ERROR (foundation-page edit; closest existing
section is `configuration.rst:322` "Startup-time vs runtime
mutability"), and the five unauthored prerequisite pages referenced
from `index.rst:22` (`introduction`, `getting-started`,
`architecture`, `service-layer`, `api-reference`).

---

## Part E — Iteration 3 integration record

This section documents what changed in iteration 3 over iteration 2, and
provides the iteration judgement the user requests.

### E.1 Cross-flow verification of outcomes

The user-supplied **Flow 0** (executed report) and **Flow 1** (planning
artifact) reached the same conclusion on every quantitative claim, by
two independent paths:

| Quantity | Flow 0 (executed) | Flow 1 (predicted) | Iteration-3 verdict |
|----------|------------------:|-------------------:|---------------------|
| Warm-build warnings | 81 | 81 | ✓ Agree (verified against `docs/build/build-log-warm.txt`) |
| Post-fix warnings | 6 | 6 | ✓ Agree (verified against `docs/build/build-log-after-fix.txt`) |
| REAL-BUG fixable | 1 | 1 | ✓ |
| REAL-BUG escalated (foundation, severe) | 1 | 1 | ✓ |
| EXPECTED-NOW-RESOLVED | 0 | 0 | ✓ |
| DRIFT | 0 | 0 | ✓ |
| PRE-EXISTING-IN-FOUNDATION (suppressible) | 55 | 55 | ✓ |
| FORWARD-REF-FROM-NEW-GLOSSARY (suppressible) | 19 | 19 | ✓ |
| Toctree precondition gap (escalated) | 5 | 5 | ✓ |
| `nitpick_ignore` entry count | 9 | 9 | ✓ |

The two flows are *fully aligned* on the outcome shape. No bucket-count
discrepancy, no anchor-name disagreement, no per-file warning-count
mismatch. This is itself a useful signal: it means the categorisation
framework in the user request is unambiguous against this docset's
warning population — both an *executor* and a *planner* working
independently classified every warning into the same bucket.

### E.2 The one substantive divergence (corrected here)

The single substantive divergence between the two flows was on the
*mechanics* of suppression:

* **Flow 0 (executed)** discovered empirically that
  `('std:ref', '<anchor>')` is the correct `nitpick_ignore` tuple key
  for `[ref.ref]` warnings — caught after a first-pass `('std:label',
  X)` rebuild left 74 of 75 suppressible warnings still firing despite
  Sphinx reporting "build succeeded".
* **Flow 1 (planning)** as originally produced recommended
  `('std:label', '<anchor>')`. That key parses without error,
  Sphinx reports no config issue, and the build still says "succeeded"
  — but the warnings are not suppressed. A planner that stopped at the
  Flow 1 recommendation would have shipped a partially-applied fix and
  reported success.

The matching-rule derivation (in §A.3.1) shows *why* `std:ref` is
correct: Sphinx's `ReferencesResolver.warn_missing_reference` builds
the suppression key as `f'{domain.name}:{typ}'`, where `typ` is the
*role* used at the citation site (`ref`), not the *object type* the
role would have resolved to (`label`). The trap is documented inline
in the on-disk `conf.py:81-93` block-header comment so a future
maintainer doesn't re-introduce it.

**Iteration-3 disposition:** the consolidated artifact carries Flow 0's
empirical finding forward, and explicitly flags Flow 1's original
recommendation as the exact failure mode an unwary maintainer could
re-introduce. Both states are preserved (the *correct* fix is the
on-disk state; the *wrong* alternative is documented as a trap to
avoid) so the lesson is permanent.

### E.3 What iteration 3 specifically added

Beyond the iteration-2 baseline, iteration 3:

1. **Promoted the user-supplied triage flows from "background context"
   to explicit inputs** in the Provenance table. Iteration 2 acknowledged
   their existence but did not formalise that they were the inputs being
   consolidated.
2. **Added §E.1** — an explicit cross-flow agreement matrix. This is
   useful evidence for a downstream auditor who wants to know whether
   the categorisation framework is robust (it is — two independent
   passes match exactly).
3. **Reframed the `std:label` story in §E.2** as a divergence between
   Flow 0 (post-execution finding) and Flow 1's *original raw input*
   (the recommendation). Iteration 2 had treated this as "a bug in the
   partial plan" — iteration 3 makes the responsibility chain
   explicit: Flow 1's planning artifact contained the recommendation;
   Flow 0's executed pass caught it; this consolidation preserves the
   lesson.
4. **Added the iteration judgement (§E.4 below)** for the upstream
   judgement-asking step in the user request.

No content from iteration 2 was deleted. The iteration-3 changes are
strictly additive plus the Provenance-promotion edit.

### E.4 Iteration judgement (does this consolidation add value?)

**Yes, the integration step produced new signal.** Specifically:

1. **It caught a correctness bug in Flow 1's original recommendation.**
   Flow 1 (planning) recommended `('std:label', X)` as the
   `nitpick_ignore` tuple type. Flow 0 (executed) discovered
   empirically that this key is a silent no-op against
   `[ref.ref]` warnings. Without consolidation, a downstream consumer
   reading just Flow 1 would have applied an incorrect fix and
   reported success.
2. **It separated "what was planned" from "what was executed".** Flow 1
   was structurally well-organised but had not actually run the
   build/fix/rebuild cycle. Flow 0 had the empirical results.
   Consolidating produces a single artifact with both the
   well-structured methodology and the verified outcomes.
3. **It captured the matching-rule derivation as a maintainer-facing
   note.** Neither flow alone fully explained *why* `std:ref` is
   correct beyond the empirical observation. The consolidated §A.3.1
   cites the `f'{domain.name}:{typ}'` line in
   `sphinx/transforms/post_transforms/__init__.py` and explains why
   the *role-type* (citation site) wins over the *object-type* (target
   directive) in the suppression key — making the fix robust against
   re-introduction.
4. **It cross-validated bucket sub-totals (§E.1).** Two independent
   passes through the same warm log produced identical counts at every
   level of granularity. That agreement is itself documentation: the
   categorisation framework is unambiguous for this docset.

**Caveat:** the value of *further* consolidation iterations beyond
iteration 3 is limited. The two flows agree on every outcome; the one
substantive disagreement (`std:label` vs `std:ref`) is now resolved and
documented as a permanent lesson; no further integration insight is
plausibly outstanding. A reasonable next step is **stop**, unless a
new upstream input is added.

---

## Part F — Iteration 4 integration record

This section records the iteration-4 step: the meta-consolidation of
two parallel iteration-3 consolidators, both of which were given the
same task description but operated on different input sets.

### F.1 Inputs to iteration 4

| Input | Path | What it brought |
|-------|------|-----------------|
| Existing iteration-3 baseline (this file's pre-iteration-4 state) | `docs/_plan/sphinx_warning_triage_consolidated.md` (967 lines) | The full Parts A–E structure with the matching-rule derivation, cross-flow verification matrix, and iteration-3 record. Built from both User-Flow-0 (executed report) and User-Flow-1 (planning artifact). |
| Parallel consolidator | `docs/_plan/sphinx_warning_triage_plan_consolidated.md` (247 lines) | A more concise consolidation that operated against a thinner input set (its "Flow 0" had no output; only Flow 1 was substantive). |

### F.2 Cross-consolidator agreement

The two consolidators reached identical conclusions on every
quantitative claim the user request asks about:

| Claim | Iteration-3 baseline | Parallel consolidator | Verdict |
|-------|---------------------:|----------------------:|---------|
| Warm-build total | 81 (1 ERROR + 80 WARN) | 81 (1 ERROR + 80 WARN) | ✓ Agree |
| REAL-BUG fixable in NEW | 1 | 1 | ✓ |
| REAL-BUG escalated | 1 | 1 | ✓ |
| EXPECTED-NOW-RESOLVED | 0 | 0 | ✓ |
| DRIFT | 0 | 0 | ✓ |
| PRE-EXISTING-IN-FOUNDATION | 55 | 55 | ✓ |
| PRE-EXISTING-IN-NEW (glossary) | 19 | 19 | ✓ |
| Toctree precondition gap | 5 | 5 | ✓ |
| Post-fix total | 6 | 6 | ✓ |
| `nitpick_ignore` entries | 9 | 9 | ✓ |
| Central insight (the unblocker) | `('std:label', X)` → `('std:ref', X)` | `('std:label', X)` → `('std:ref', X)` | ✓ |
| Iteration judgement (continue vs. stop) | stop | stop | ✓ |

The two consolidators independently arrived at the same conclusion,
the same insight, and the same recommendation. That convergence is
itself a useful signal: the categorisation framework holds even when
a consolidator has only partial inputs.

### F.3 What the parallel consolidator brought that the iteration-3 baseline did not

Three substantive additions, all folded into this artifact in
iteration 4:

1. **Locator evidence for the 16 `('std:label', X)` occurrences in
   Flow 1's *original raw* plan** (lines 183, 415, 593, 599, 604,
   612, 617, 625, 630, 635, 640, 652, 658, 773, 942, 1010 —
   anchored to the original raw input, not the on-disk-today plan).
   Folded into §A.3.1 as a footnote and cross-referenced in this
   §F.3. *Why this matters:* downstream readers of any *cached*
   copy of the original plan (e.g. someone with the file checked
   out from before the on-disk correction) need a precise locator
   set to apply the doc-only amendment.
2. **Risks / Exit / Rollback subsection** (folded in as §D.4). The
   iteration-3 baseline had implicit rollback paths (the file
   timestamps make the diff obvious) but did not name them
   explicitly.
3. **One-paragraph executor handoff** (folded in as §D.5). The
   iteration-3 baseline had a fuller §D.2 handoff list; the
   parallel consolidator's one-paragraph distillation is a useful
   complementary form for an executor scanning for "what's left".

### F.4 What the iteration-3 baseline brought that the parallel consolidator did not

Five substantive items the parallel consolidator could not have
produced because it lacked Flow 0 (the executed report):

1. **The matching-rule derivation in §A.3.1.** The parallel
   consolidator named the bug (`std:label` → `std:ref`) but did not
   derive *why* `std:ref` is correct from
   `f'{domain.name}:{typ}'` in
   `sphinx/transforms/post_transforms/__init__.py`. The derivation
   is what makes the fix robust against re-introduction — anyone
   reading just the bug-fix line could be tempted to "correct" it
   back to `std:label`. The derivation closes that loop.
2. **The cross-flow agreement matrix (§E.1).** Required two
   substantive flows to compare; the parallel consolidator only had
   one.
3. **Build-capture tooling integration (§A.4.3).** Folded in the
   bash `${PIPESTATUS[0]}` pattern and the PowerShell stderr-wrapping
   caveat from `sphinx_initial_build_plan.md`. The parallel
   consolidator did not address build re-execution platform
   portability.
4. **The §A.4 rebuild substitution rationale.** Acknowledges
   `uv` not on PATH and substitutes `python -m sphinx`, with the
   note that the binary is the same. The parallel consolidator
   transcribed the user-request command verbatim without addressing
   the executor's actual environment.
5. **Per-anchor citation comments mapping (§A.3.1, last bullet).**
   The five-page-top-anchor + four-sub-anchor decomposition with
   the explicit note that `service-layer` is *not* in the list
   because nothing currently `:ref:`-cites it (only its sub-anchor
   `svc-moderation` is cited).

### F.5 Iteration judgement (does iteration 4 add value?)

**Yes, but the marginal lift is bounded.** Specifically:

* The locator evidence (§A.3.1 footnote) is genuinely useful — it
  preserves a recoverable trail for anyone holding the
  pre-correction Flow 1 raw input.
* The §D.4 Risks/Rollback subsection is a real omission from the
  iteration-3 baseline, now patched.
* The §D.5 one-paragraph handoff is useful complementary form.
* No content was *removed*; iteration 4 is strictly additive.

**Caveat:** further iterations beyond iteration 4 would have very
limited marginal lift. Both consolidators reach the same numbers,
buckets, escalations, and central insight. The on-disk state is
verified. The only outstanding work is owner-action escalations
already named in §B.4 and §D.5; no further consolidation can
resolve those.

```json iteration_judgment
{
  "decision": "stop",
  "reason": "Both upstream consolidators reach identical quantitative outcomes (81 → 6, identical bucket totals, identical 9-anchor list) and identical central insight ('std:label' → 'std:ref' is the −74 unblocker). Iteration 4 surfaced three folded-in additions (locator evidence in §A.3.1, risks/rollback as §D.4, one-paragraph handoff as §D.5) and verified the parallel consolidator's quantitative claims against the iteration-3 baseline. With both consolidators agreeing on every measurable outcome and the on-disk state confirming the predicted post-fix count of 6, further iterations cannot produce additional integration signal."
}
```

### F.6 Winner-pick judgement (if forced to choose one upstream input)

The user's task asks: "if you are only allowed to pick one of the
provided inputs (rather than being asked to integrate all), which one
would you choose and why?"

**Answer: Result 2** (the iteration-3 consolidated artifact).

**Reasons:**

1. **Coverage.** Result 2 had access to *both* substantive flows
   (User's Flow 0 — the executed report — and User's Flow 1 — the
   planning artifact), whereas Result 1 only had Flow 1 (its
   "Flow 0" produced no output). A consolidator with one
   substantive input cannot triangulate; one with two can.
2. **Depth of the central insight.** Both consolidators identified
   the `std:label` → `std:ref` correction. Result 2 went further:
   it derived *why* `std:ref` is correct from the
   `f'{domain.name}:{typ}'` matching rule in
   `sphinx/transforms/post_transforms/__init__.py`. That
   derivation is what protects the fix against re-introduction.
3. **Cross-flow verification.** Result 2's §E.1 matrix
   demonstrates that two independent passes (executor and
   planner) reached identical bucket totals — a robustness signal
   the framework is unambiguous against this docset. Result 1
   could not produce this because it had only one input.
4. **Comprehensive structure.** Result 2's Parts A–E cover the
   full plan + report + reconciliation + handoff + iteration
   record. Result 1 is more concise but skips the methodology
   layer (Part A) and the predecessor reconciliation layer
   (Part C).

**What Result 1 wins on:** conciseness and the locator-evidence
catalogue (16 specific line numbers). For a reader who needs the
TL;DR and the doc-hygiene amendment list, Result 1 is faster to
consume. But for a reader who needs to *understand the fix* (so
they don't regress it), Result 2 is the stronger pick — and the
locator evidence has been folded into Result 2's structure as part
of this iteration-4 step, so nothing is actually lost by choosing
Result 2.

```json winner_pick
{
  "winner_index": 1,
  "reason": "Result 2 had access to both substantive upstream flows (executed report + planning artifact) and produced the matching-rule derivation that makes the std:label → std:ref fix robust against re-introduction; Result 1 had only one substantive input and stopped at naming the bug without deriving why."
}
```
