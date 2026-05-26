# Sphinx Warning Triage — Consolidated Plan & Triage Report

**Consolidation date:** 2026-05-04
**Upstream inputs:**
* **Flow 1 / step 0** — `docs/_plan/sphinx_warning_triage_plan.md` (1021 lines).
  TL;DR, parsed-warning inventory, per-bucket categorisation, fix recipes,
  rebuild plan, triage report schema. **Substantive input.**
* **Flow 0** — *(no output produced).* Nothing to merge.

**Companion artifact (unchanged):**
`docs/_plan/sphinx_scaffolding_audit.md` — referenced by flow 1 as the
upstream audit that predicted the warning shape we are now triaging.

**Relationship to executed state on disk:**
`docs/source/conf.py` (lines 49–129), `docs/source/glossary.rst:13`, and
`docs/build/build-log-after-fix.txt` already exist on disk and reflect a
*post-fix* state. The build log reports `build succeeded, 6 warnings.`
which **matches flow 1's predicted post-fix count exactly** (Δ = −75).
This consolidation therefore doubles as a verification report.

---

## 1. Consolidation outcome at a glance

| Item | Flow 1 plan | Executed state | Verdict |
|------|-------------|----------------|---------|
| Warm-build warning total | 81 (1 ERROR + 80 WARNs) | 81 (per `build-log-warm.txt`) | ✅ matches |
| REAL-BUG fixable in NEW | 1 (`glossary.rst:13` `:rst:dir:`) | Edit applied — line 13 now uses literal `` ``.. glossary::`` `` | ✅ landed |
| REAL-BUG escalated | 1 (`configuration.rst:254` docutils ERROR) | Still emitted; foundation-page edit out of scope | ✅ correctly escalated |
| DRIFT | 0 | n/a | ✅ |
| PRE-EXISTING-IN-FOUNDATION | 55 `[ref.ref]` | Suppressed via 9 `nitpick_ignore` tuples in `conf.py` | ✅ landed |
| PRE-EXISTING-IN-NEW (glossary fwd-refs) | 19 `[ref.ref]` | Same 9 tuples cover them | ✅ landed |
| Toctree precondition gap | 5 escalated | Still emitted (intentional — see §4) | ✅ correctly escalated |
| Predicted post-fix total | 6 (1 ERROR + 5 toctree) | `build succeeded, 6 warnings.` | ✅ exact match |

---

## 2. Material correction surfaced by consolidation

Flow 1's plan repeatedly specifies the suppression-tuple form as
``('std:label', '<anchor>')`` (plan lines 183, 415, 593, 599, 604, 612,
617, 625, 630, 635, 640, 652, 658, 773, 942, 1010). This is **incorrect**
— Sphinx's `ReferencesResolver.warn_missing_reference`
(`sphinx/transforms/post_transforms/__init__.py`) builds the
nitpick-key as `f'{domain.name}:{typ}'` where `typ` is the *role*
(`ref`), not the *object* (`label`). Using `('std:label', ...)` would
silently fail to suppress and leave all 74 `[ref.ref]` warnings intact.

The executed `conf.py` (lines 81–93, 94–129) uses the correct
``('std:ref', '<anchor>')`` form *and* documents the reasoning inline.
The fact that the rebuilt log shows exactly 6 warnings (the predicted
escalation residue) confirms the corrected mechanism.

**Action for the plan-of-record:** the original
`sphinx_warning_triage_plan.md` should have its 16 `('std:label',…)`
references corrected to `('std:ref',…)` so future readers don't
regress when re-deriving the fix from the plan. This is a doc-only
amendment; no rebuild needed.

> Excerpt from `conf.py:81–93` (kept short for clarity, full text in file):
> > "The tuple form is `('std:ref', '<anchor>')` … using `std:label`
> > silently fails to suppress and leaves every warning intact."

This is the **only** integration delta surfaced by the consolidation
process; everything else in flow 1's plan is consistent with the
executed state.

---

## 3. Inputs and rules (carried forward unchanged from flow 1)

* **Warm log:** `docs/build/build-log-warm.txt` (122 lines incl. preamble),
  ANSI-stripped twin at `build-log-warm-clean.txt`. Sphinx 8.2.3,
  `nitpicky = True`, `keep_going` default; final line is
  `build succeeded, 81 warnings.`.
* **Editable files:** `docs/source/conf.py`, `docs/source/index.rst`,
  `docs/source/glossary.rst`.
* **Read-only foundation files (per CONSOLIDATION_NOTES constraint i):**
  `introduction.rst`, `getting-started.rst`, `architecture.rst`,
  `service-layer.rst`, `inference-models.rst`, `configuration.rst`,
  `api-reference.rst`, `operations.rst`. Five of those eight are
  *absent* from `docs/source/` on disk; only the three line-by-line-
  audited foundation pages physically exist (the other five are the
  unauthored prerequisite pages that produce the toctree warnings).
* **Constraint ii:** `nitpicky = True` may **not** be weakened, and
  `suppress_warnings` may **not** be used as a mass-suppression knob.
* **Constraint iii:** if a warning is unsafe to fix and unsafe to
  suppress, escalate via the triage report.
* **Toolchain:** `uv run sphinx-build -b html docs/source docs/build/html`.

---

## 4. Per-warning triage report (deliverable for original-request step g)

Each row distils a class of warnings from the warm log; full per-line
detail is preserved in flow 1's plan §2.

### 4.1 In-scope fix (action: fixed-in-place)

| # | Warning (warm log) | File:Line | Category | Action taken | Result |
|---|--------------------|-----------|----------|--------------|--------|
| 1 | `:rst:dir:\`glossary\`` reference target not found | `glossary.rst:13` | **REAL-BUG** (NEW file, fixable) | Replaced inline `:rst:dir:\`glossary\`` role with literal `` ``.. glossary::`` `` in the prose bullet | Removed from post-fix log ✅ |

### 4.2 Suppressed via `nitpick_ignore` (action: suppressed-with-citation)

74 `[ref.ref]` warnings collapse to **9 unique forward-referenced
anchor names**. All 9 carry a per-tuple citation comment in `conf.py`
naming the originating page(s), the cite line(s), and the page that
will eventually host the `.. _<anchor>:` directive (per glossary's
Shared Anchor Map at `glossary.rst:358`+).

| # | Anchor (`std:ref` key) | Cited from | Will be defined in (per anchor map) |
|---|------------------------|------------|--------------------------------------|
| 1 | `introduction` | `configuration.rst` (3 cites), `glossary.rst` (2) | `introduction.rst` (top) |
| 2 | `getting-started` | `configuration.rst` (6), `operations.rst` (3), `glossary.rst` (1) — 11× total | `getting-started.rst` (top) |
| 3 | `gs-feature-flags` | `configuration.rst:2054`, `glossary.rst:620` | `getting-started.rst` (sub) |
| 4 | `architecture` | `configuration.rst`, `inference-models.rst`, `operations.rst`, `glossary.rst` — 21× total (most-cited) | `architecture.rst` (top) |
| 5 | `arch-debug-trace` | `glossary.rst:76, 624, 638` | `architecture.rst` (sub) |
| 6 | `svc-moderation` | `configuration.rst` (5), `inference-models.rst` (3), `glossary.rst` (2) — 11× total | `service-layer.rst` (sub) |
| 7 | `api-reference` | `configuration.rst`, `glossary.rst` — 16× total | `api-reference.rst` (top) |
| 8 | `api-etag` | `configuration.rst:1068, 2066`, `glossary.rst:89, 638` | `api-reference.rst` (sub) |
| 9 | `api-debug-trace` | `glossary.rst:76, 638` | `api-reference.rst` (sub) |

By page-of-origin (so the triage matches the
`PRE-EXISTING-IN-FOUNDATION` vs `PRE-EXISTING-IN-NEW-FILE` split the
user request defines):

| Origin page | Warnings collapsed | Justification |
|-------------|-------------------:|---------------|
| `configuration.rst` | 43 of 55 PRE-EXISTING-IN-FOUNDATION | Foundation page (read-only); cites map 1:1 to anchor map |
| `inference-models.rst` | 7 of 55 | Foundation page (read-only) |
| `operations.rst` | 5 of 55 | Foundation page (read-only) |
| `glossary.rst` | 19 PRE-EXISTING-IN-NEW-FILE | NEW file; glossary's own opening note (lines 23–32) and *Documented ambiguities* §1 declare these forward refs will fail until prerequisite pages land — suppression matches the file's own intent |

**Edit shape:** 9 entries appended to `conf.py:nitpick_ignore` with
the correct `('std:ref', '<anchor>')` form (see §2 above), each
followed by an inline citation comment naming the source `file:line`
and the future-defining page. **Removing each entry is the signal
that the corresponding page-authoring subtask has landed.**

### 4.3 Escalated (action: flagged-in-triage-report, no edit applied)

| # | Warning | File:Line | Category | Why escalated | Recommendation |
|---|---------|-----------|----------|---------------|----------------|
| 1 | docutils ERROR `Unknown target name: "Startup-time validation"` | `configuration.rst:254` | **REAL-BUG, NOT fixable here** | Foundation page is line-by-line audited (constraint i); `nitpick_ignore` does not suppress docutils errors (different mechanism) | Owner of `configuration.rst` should change the broken anchor reference, e.g. retarget to `Startup-time vs runtime mutability` (the closest existing section, at `configuration.rst:322`) |
| 2 | toctree references nonexisting `introduction` | `index.rst:22` | **Toctree precondition gap** | Five of the nine pages declared in the toctree are unauthored. Mass-suppression via `suppress_warnings = ['toc.not_readable']` is prohibited (constraint ii); writing stub pages would create new foundation pages (out of scope) | Subtask owner to author or stub the 5 missing pages; same recommendation appears in `sphinx_scaffolding_audit.md §4` |
| 3 | toctree references nonexisting `getting-started` | `index.rst:22` | (same) | (same) | (same) |
| 4 | toctree references nonexisting `architecture` | `index.rst:22` | (same) | (same) | (same) |
| 5 | toctree references nonexisting `service-layer` | `index.rst:22` | (same) | (same) | (same) |
| 6 | toctree references nonexisting `api-reference` | `index.rst:22` | (same) | (same) | (same) |

### 4.4 Confirmed empty buckets

* **EXPECTED-NOW-RESOLVED: 0.** No prior subtask has landed any of the
  five missing prerequisite pages, so no warm-log forward-reference is
  *now* unexpectedly resolvable. The bucket appearing empty is the
  intended confirmation that the anchor chain is sound.
* **DRIFT: 0.** Every forward-referenced anchor name in the warm log
  matches the spelling planned in the Shared Anchor Map
  (`glossary.rst:358–688`). No producer/consumer mismatch needs an
  `index.rst` / `glossary.rst` rename.

---

## 5. Verification (already performed)

The user request step (e) prescribes:
```bash
rm -rf docs/build/html
uv run sphinx-build -b html docs/source docs/build/html
```
This was executed; output is preserved at
`docs/build/build-log-after-fix.txt` (per step f). The log's terminal
line is `build succeeded, 6 warnings.` and the 6 surviving warnings
are exactly the 1 escalated docutils ERROR + 5 escalated toctree
warnings enumerated in §4.3.

**Net delta:** 81 → 6, i.e. **−75**, matching flow 1's prediction.

---

## 6. Files-touched / files-not-touched

* **Touched (and now reflecting the executed state):**
  * `docs/source/conf.py` — appended `nitpick_ignore` block (9 tuples
    + header & per-tuple citation comments) using the corrected
    `('std:ref', …)` form.
  * `docs/source/glossary.rst` — line 13 single-line edit.
  * `docs/build/build-log-after-fix.txt` — saved per step (f).
* **Not touched (per constraint i):** all eight foundation pages,
  `index.rst`, anything outside `docs/source/`.

---

## 7. Risks, exit criteria, rollback

* **Exit criterion:** post-fix warning count = 6 *and* the surviving 6
  match the escalation list verbatim. Already met.
* **Risk: a future page-authoring subtask lands `introduction.rst`
  but forgets to remove the matching `nitpick_ignore` line.** Then a
  typo'd `:ref:\`introduction\`` would silently slip through. Mitigation:
  the inline comment header in `conf.py:69–73` explicitly tells the
  next author "*Removing each entry below is the signal that the
  corresponding page authoring subtask has landed*."
* **Risk: a new foundation-page edit introduces a broken anchor that
  matches one of the 9 suppressed names.** Same mitigation —
  comment header instructs the author to add only with a
  Shared-Anchor-Map row to back it.
* **Rollback:** revert the two file edits and delete the after-fix
  log. The warm-build state is reproducible from current source.

---

## 8. Executor handoff (one paragraph)

The work prescribed by the original-request steps (a)–(g) is already
complete on disk: warnings parsed (§3 of flow 1's plan), categorised
(§2 of flow 1's plan, totals reconciled in §1 above), in-place fixes
applied to `glossary.rst:13` and `conf.py.nitpick_ignore`, rebuild
executed, post-fix log saved at `docs/build/build-log-after-fix.txt`,
and this consolidated triage report (§4) covers the per-warning
delivery for step (g). The single remaining doc-hygiene amendment
surfaced by consolidation is to correct the 16 `('std:label', …)`
references in `sphinx_warning_triage_plan.md` to `('std:ref', …)` so
the plan-of-record matches the executed mechanism (§2). Two
escalations remain owner-action items: the `configuration.rst:254`
"Startup-time validation" anchor (foundation-page edit) and the five
unauthored prerequisite pages referenced from `index.rst:22`.

---

## 9. Integration value-add assessment (required by the task)

Flow 0 produced no artifact; flow 1 supplied the only substantive
input. The consolidation therefore could not draw on competing
perspectives. Cross-checking flow 1's plan against the on-disk
executed state did surface **one material correction** worth
recording — the `std:label` → `std:ref` mechanism error in the
plan's recipe section, which the executor evidently caught and
corrected when applying the fix. Beyond that, this artifact is
substantively equivalent to the upstream plan.

The integration step's contribution is therefore **modest but
non-zero** (one correction, plus the verification cross-check that
prediction matched reality). With no second flow to triangulate
against, further iterations of consolidation would not surface
additional signal.
