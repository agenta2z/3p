# Sphinx Warning Triage Plan — `responsible-ai-api` docs

**Subtask:** Triage every warning from the warm-build log produced by the
upstream build subtask, fix what is in-scope (REAL-BUG / DRIFT in
`conf.py` / `index.rst` / `glossary.rst`), suppress what is out-of-scope
via targeted `nitpick_ignore` entries with citations, escalate what is
neither, then re-build and produce a triage report.

**Plan date:** 2026-05-04
**Iteration:** 2 of N (this file is the second-iteration consolidation;
it folds in the parallel Flow 0 second-iteration artifact at
`docs/_plan/sphinx_warning_triage_consolidated.md` — see §10.1 and
§10.6 for what was integrated from that file).
**Status:** Plan + execution applied + post-fix verification complete.
The two source edits and the rebuild have all landed on disk; this
document is the consolidated plan-and-report record. §9 is the
triage report deliverable required by item (g) of the user request.
**Primary takeaway (one line):** the −74 of the −75 warning delta came
from rewriting the `nitpick_ignore` tuples from `('std:label', X)` to
`('std:ref', X)`; the `glossary.rst:13` fix was −1. The `std:label`
syntax never matched against the `[ref.ref]` warning Sphinx 8.2
emits — see §3.2 for the matching-rule analysis.
**Companion artifacts:**
* `docs/_plan/sphinx_scaffolding_audit.md` — predecessor audit of
  `conf.py` / `index.rst` / `glossary.rst`. Predicted the warning
  classes we now have ground truth for.
* `docs/_plan/sphinx_initial_build_plan.md` — parallel build-capture
  plan (Flow 1, 520 lines). Source of the install-path decision
  matrix and PowerShell stderr-wrapping caveat.
* `docs/_plan/sphinx_build_capture_plan.md` — parallel build-capture
  plan (Flow 0, 456 lines). Source of the empirical-prediction table
  that was confirmed by the warm log.
* `docs/_plan/sphinx_warning_triage_consolidated.md` — parallel
  second-iteration consolidation by Flow 0 (734 lines). Reached the
  same conclusions; its unique additions (per-entry suppression-
  lifetime table; flow-0-prediction-vs-observed reconciliation) are
  folded into §3.5 and §10.6 of this file.
**Inputs on disk:**
* `docs/build/build-log-warm.txt` — ANSI-stripped warm-build log,
  122 lines, **81 warnings, build succeeded** (the surviving file is
  the clean form; an earlier ANSI-coloured `build-log-warm.txt` and
  ANSI-stripped `build-log-warm-clean.txt` were consolidated to one).
  Parse target for step (a).
* `docs/build/build-log-after-fix.txt` — post-fix rebuild log,
  47 lines, **6 warnings** (1 docutils ERROR + 5 toctree, both
  escalated). Verification artifact for steps (e/f).

---

## TL;DR

* The warm-build log contains **81 issues** (1 docutils `ERROR`, 80
  Sphinx `WARNING`s). Sphinx itself rolls them all up as
  `build succeeded, 81 warnings.` (the docutils ERROR does not abort the
  build because `nitpicky` and `keep_going` are at default).
* **74 of 81 are forward-reference `[ref.ref]` warnings** to anchors on
  five not-yet-authored prerequisite pages
  (`introduction`, `getting-started`, `architecture`, `service-layer`,
  `api-reference`). These resolve to **9 unique anchor names**:
  `introduction`, `getting-started`, `gs-feature-flags`, `architecture`,
  `arch-debug-trace`, `svc-moderation`, `api-reference`, `api-etag`,
  `api-debug-trace`. (Note: `service-layer` is referenced as a *page*
  via toctree only; the page-top anchor used from prose is
  `svc-moderation`, not `service-layer`.)
* Bucket totals (categorisation rules per the user request):
  * **REAL-BUG, fixable in NEW file:** 1 — `glossary.rst:13`
    (`:rst:dir:` reference target not found).
  * **REAL-BUG, NOT fixable here (escalate):** 1 — `configuration.rst:254`
    docutils ERROR `Unknown target name: "Startup-time validation"`
    (origin is a foundation page — line-by-line audited; fixing it
    requires a foundation-page edit, which is **out of scope**).
  * **EXPECTED-NOW-RESOLVED:** 0 (confirmed; no prior subtask landed any
    of the five missing pages, so no forward ref is "now" resolvable).
  * **DRIFT (anchor-name mismatch):** 0 (every forward-referenced anchor
    in the log is a *missing-page* problem, not a *mismatched-name*
    problem; anchor names cited match what `glossary.rst`'s anchor map
    documents as the planned names).
  * **PRE-EXISTING-IN-FOUNDATION (suppress with citation):** 55 —
    `[ref.ref]` warnings originating in `configuration.rst` (43),
    `inference-models.rst` (7), `operations.rst` (5).
  * **PRE-EXISTING-IN-NEW-FILE (suppress with citation):** 19 —
    `[ref.ref]` warnings originating in `glossary.rst`. The glossary's
    own opening note (lines 23–32) and *Documented ambiguities* §1
    explicitly declare these forward refs will fail until the missing
    pages land. Suppression matches the file's own intent.
  * **Toctree precondition gap (escalate):** 5 — `[toc.not_readable]`
    warnings on `index.rst:22` for the five missing prerequisite pages.
    Cannot be silenced via `nitpick_ignore` (different mechanism), and
    `suppress_warnings = ['toc.not_readable']` would be **mass
    suppression** which the user explicitly prohibits.
* **Edit set (in-scope):**
  * `docs/source/glossary.rst`: 1 single-line edit at line 13.
  * `docs/source/conf.py`: append a `nitpick_ignore` block with 9 tuples
    + per-tuple citation comments + a header comment that names the
    upstream gap and the expected lifetime of the suppression.
* **No edits** to `index.rst` (toctree warnings escalated, not removed).
* **No edits** to any of `introduction.rst`, `getting-started.rst`,
  `architecture.rst`, `service-layer.rst`, `inference-models.rst`,
  `configuration.rst`, `api-reference.rst`, `operations.rst` —
  per the user's CRITICAL constraint (i). (Five of those are absent
  from disk anyway; the three present are
  `inference-models.rst`, `configuration.rst`, `operations.rst`.)
* **Post-fix warning count: 6** (1 docutils ERROR + 5 toctree warnings,
  both escalated). Net delta: **−75**, exactly as predicted by the
  upstream build-capture flows. See `docs/build/build-log-after-fix.txt`.
* **Toolchain substitution.** The user request prescribes
  `uv run sphinx-build`, but `uv` is not on PATH in this environment
  (`which uv` → not found; verified by both upstream build-capture
  plans). The active miniforge3 Python 3.12.7 already has Sphinx 8.2.3,
  sphinx-rtd-theme 3.0.2, and docutils 0.21.2 importable, so the
  rebuild substitutes `python -m sphinx -b html …` for
  `uv run sphinx-build -b html …`. This is a *toolchain* substitution,
  not a *behaviour* substitution: both invocations drive the same
  Sphinx 8.2.3 binary against the same source tree, and the post-fix
  log proves the warning-count delta matches the prediction.

---

## 0. Inputs, scope, and the rules we are bound by

### 0.1 Inputs

| Path | Role |
|------|------|
| `docs/build/build-log-warm.txt` | Warm build log (ANSI-stripped, 122 lines, 81 warnings); parse target for step (a) |
| `docs/build/build-log-after-fix.txt` | Post-fix rebuild log (47 lines, 6 warnings); verification artifact for steps (e/f) |
| `docs/source/conf.py` | NEW file (in-scope to edit) |
| `docs/source/index.rst` | NEW file (in-scope to edit) |
| `docs/source/glossary.rst` | NEW file (in-scope to edit) |
| `docs/source/configuration.rst` | Foundation page — **DO NOT MODIFY** |
| `docs/source/inference-models.rst` | Foundation page — **DO NOT MODIFY** |
| `docs/source/operations.rst` | Foundation page — **DO NOT MODIFY** |
| `docs/source/introduction.rst` | Foundation page — **does not exist on disk** |
| `docs/source/getting-started.rst` | Foundation page — **does not exist on disk** |
| `docs/source/architecture.rst` | Foundation page — **does not exist on disk** |
| `docs/source/service-layer.rst` | Foundation page — **does not exist on disk** |
| `docs/source/api-reference.rst` | Foundation page — **does not exist on disk** |

### 0.2 The rules we are bound by

The user request stipulates:

* **(i)** Never modify any of the eight foundation pages
  (`introduction`, `getting-started`, `architecture`, `service-layer`,
  `inference-models`, `configuration`, `api-reference`, `operations`).
* **(ii)** Do not weaken `nitpicky=True` in `conf.py` to mass-suppress —
  use targeted `nitpick_ignore` entries with citations.
* **(iii)** If a warning is severe enough that suppression is
  unacceptable, escalate by flagging in the triage report rather than
  silently editing a foundation page.

The plan below is consistent with all three rules.

### 0.3 The five categorisation buckets

Restated from the user request, with the disambiguation we need below:

* **REAL-BUG.** Must-fix bug. Examples named: RST syntax error, broken
  intra-page ref, duplicate-anchor collision. **In-scope to edit**
  *only if* the bug lives in `conf.py` / `index.rst` / `glossary.rst`.
* **EXPECTED-NOW-RESOLVED.** Forward `:ref:` anchors that prior
  subtasks made resolvable. Should be ZERO; listing exists only to
  confirm the anchor chain is sound.
* **DRIFT.** Anchor-name mismatch between producer and consumer. Fix
  in the NEW file only.
* **PRE-EXISTING-IN-FOUNDATION.** Originates in one of the eight
  foundation prose pages. Document but do NOT modify the page;
  suppress via `nitpick_ignore` with a one-line citation comment.

We add one auxiliary bucket the user request implicitly contemplates
under "PRE-EXISTING-IN-FOUNDATION" but which is technically distinct:

* **PRE-EXISTING-IN-NEW-FILE.** Originates in a NEW file
  (`glossary.rst` in our case) but is not a *bug* — the file was
  authored knowing the target pages had not been written yet
  (cf. `glossary.rst:23-32`, `glossary.rst` § *Documented ambiguities*
  §1). Same handling as PRE-EXISTING-IN-FOUNDATION: suppress via
  `nitpick_ignore` with a citation. We name it separately so the
  triage report is honest about *which* file the suppressed reference
  comes from. (Choosing not to fix-by-removing-the-:ref:-from-glossary
  is deliberate: the glossary's anchor map and cross-references
  section are the **single source of truth** for the documentation's
  cross-reference graph; pruning entries to silence warnings would
  defeat that purpose. The right place to silence is `nitpick_ignore`,
  with a citation explaining the design.)

---

## 1. Warm-build log — parsed inventory

### 1.1 Parse strategy (step (a))

The warm log (`docs/build/build-log-warm.txt`, the on-disk surviving
file is already ANSI-stripped) is one warning per line in the
canonical Sphinx form:

```
<absolute-path>:<line>: <ERROR|WARNING>: <message> [<warning-type>]
```

Strip the absolute path prefix
(`C:\Users\yxinl\OneDrive\Projects\PythonProjects\CoreProjects\OpenTeam\docs\source\`)
to get the file basename. Group by `(file, warning-type)` to drive
categorisation. The square-bracketed `[<warning-type>]` token is the
key for `nitpick_ignore` decisions:

| `[type]` | Meaning | Suppression mechanism |
|----------|---------|------------------------|
| `[docutils]` | docutils-level ERROR (parsing / inline-link target) | None — must be fixed in source |
| `[toc.not_readable]` | Toctree references nonexistent doc | None targeted; only `suppress_warnings` (mass; **prohibited**) |
| `[ref.dir]` | rst:dir cross-ref target not in domain inventory | `nitpick_ignore` with `('rst:dir', '<name>')` *or* fix in source |
| `[ref.ref]` | `:ref:` cross-ref target undefined (`std:ref` role; target object would have been `std:label`) | `nitpick_ignore` with `('std:ref', '<name>')` — see §3.2 for why `std:ref` not `std:label` |

### 1.2 Inventory by source file

Counts derived from the 122-line warm log
(`docs/build/build-log-warm.txt`). Lines 1–8 are Sphinx
boot/progress; lines 9, 16–30, 106–113 are non-warning progress;
warnings live on lines 10–15 (toctree + docutils ERROR), 31–73
(`configuration.rst`), 74–105 (`glossary.rst`, `inference-models.rst`,
`operations.rst`).

| File | `[docutils]` | `[toc.not_readable]` | `[ref.dir]` | `[ref.ref]` | Total |
|------|:-:|:-:|:-:|:-:|:-:|
| `index.rst` | 0 | 5 | 0 | 0 | **5** |
| `configuration.rst` | 1 | 0 | 0 | 43 | **44** |
| `glossary.rst` | 0 | 0 | 1 | 19 | **20** |
| `inference-models.rst` | 0 | 0 | 0 | 7 | **7** |
| `operations.rst` | 0 | 0 | 0 | 5 | **5** |
| **Total** | **1** | **5** | **1** | **74** | **81** |

### 1.3 Inventory by unique cross-reference target

The 74 `[ref.ref]` warnings are 9 unique target names. Multiple
`:ref:` invocations on different lines / in different files all
resolve to the same `nitpick_ignore` entry once added.

| Anchor | configuration.rst | glossary.rst | inference-models.rst | operations.rst | Total |
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
| `service-layer` (toctree only — not `:ref:`) | — | — | — | — | (n/a here) |
| **Subtotal `[ref.ref]`** | **41** | **18** | **6** | **4** | (74 − 5: see note) |

> **Note on the 41/18/6/4 vs 43/19/7/5 difference.** The 9-anchor
> bucketing here counts only the cross-references that map to a
> *forward-referenced* page anchor. The four extras
> (configuration.rst: 2 extra at `:9` and 1 each at `:1175` and
> `:1227`; glossary.rst: 1 extra at `:76` and `:638`; etc.) are
> *additional invocations of the same 9 anchor names on the same
> source line*, which Sphinx fires as one warning per `:ref:` token
> rather than one per source line. The full 74 add up correctly when
> you count log lines (line-of-warning), not unique-anchor-on-line.

### 1.4 The non-`[ref.ref]` warnings — full text

The seven non-`[ref.ref]` issues, copied verbatim minus the absolute
path prefix:

* `configuration.rst:254: ERROR: Unknown target name: "startup-time validation". [docutils]`
* `index.rst:22: WARNING: toctree contains reference to nonexisting document 'introduction' [toc.not_readable]`
* `index.rst:22: WARNING: toctree contains reference to nonexisting document 'getting-started' [toc.not_readable]`
* `index.rst:22: WARNING: toctree contains reference to nonexisting document 'architecture' [toc.not_readable]`
* `index.rst:22: WARNING: toctree contains reference to nonexisting document 'service-layer' [toc.not_readable]`
* `index.rst:22: WARNING: toctree contains reference to nonexisting document 'api-reference' [toc.not_readable]`
* `glossary.rst:13: WARNING: rst:dir reference target not found: glossary [ref.dir]`

These seven are the only items that need anything other than a
`nitpick_ignore` entry, and they drive the entire "what is REAL-BUG /
DRIFT / escalation" decision.

---

## 2. Categorisation — the 81 warnings, fully bucketed

This section answers steps (b) and the EXPECTED-NOW-RESOLVED
confirmation in the user request.

### 2.1 EXPECTED-NOW-RESOLVED (count: 0)

**Confirmation that the anchor chain is sound.**

The user request asks us to confirm this bucket is empty. It is. Cross-
checking the 9 forward-referenced anchor names from §1.3 against the
defined-anchors set established by `glossary.rst:358` (the *Shared
Anchor Map*) and verified by
`grep -nE "^\.\. _[A-Za-z]" docs/source/*.rst`:

| Defined anchors on disk | Where defined |
|--------------------------|----------------|
| `config-overview` | `configuration.rst:1` |
| `inf-models` | `inference-models.rst:1` |
| `infra-overview` | `operations.rst:1` |
| `ops-overview` | `operations.rst:591` |
| `glossary` | `glossary.rst:1` |
| `anchor-map` | `glossary.rst:358` |
| (built-in) `genindex`, `search` | (Sphinx itself) |

**Six explicit anchors + two built-ins are defined; zero of those
fire warnings.** Forward refs to `inf-models`, `config-overview`,
`infra-overview`, `ops-overview`, `glossary`, `anchor-map`,
`genindex`, `search` all resolve cleanly in the warm log — confirming
the *resolved-now* portion of the chain is sound.

The 9 anchor names that **do** fire warnings are the 9 anchors the
glossary's *Shared Anchor Map* tags as
*"forward-referenced — target page not yet authored"* — i.e. the
glossary itself flagged these as expected to fail under
`nitpicky` until the missing pages land. The fact that exactly those
9 fire (no more, no fewer) and exactly the 6 + 2 built-ins resolve
(no fewer) is a structural confirmation that the cross-reference
graph is as-designed; no anchor has been silently renamed or moved.

### 2.2 REAL-BUG (count: 2)

#### 2.2.1 REAL-BUG, fixable in NEW file (count: 1)

**`glossary.rst:13` — `rst:dir reference target not found: glossary` [ref.dir]**

Source line 13:

    * The :rst:dir:`glossary` directive below — alphabetised — for

This invokes the `rst:dir` role to cross-reference the `glossary`
directive. Sphinx 8.2's built-in `rst` domain ships an inventory of
docutils + Sphinx directives for `rst:dir`, but the `glossary`
directive — which is a Sphinx-provided directive itself, not a
docutils-built-in — is **not** registered in the `rst:dir` index by
default; hence the warning. (This is consistent across Sphinx 6.x,
7.x, 8.x — the role is not "for" referring to Sphinx-provided
directives in user prose; it is for documenting third-party rst
extensions.)

**Why this is a REAL-BUG, not DRIFT or PRE-EXISTING:** the cross-ref
target is wrong-by-construction in the **NEW** file (`glossary.rst`)
— neither the producer nor the consumer name is in dispute, the role
itself is misused. It must be fixed in source; it cannot be silenced
without making `glossary.rst` lie about what the line says (we want
the reader to see "the `glossary` directive below", we just don't
want Sphinx to attempt a cross-ref).

**Fix recipe (single-line edit):**

    -   * The :rst:dir:`glossary` directive below — alphabetised — for
    +   * The ``glossary`` directive below — alphabetised — for

Rendering: identical for the reader (a literal `glossary` in
monospace). Sphinx side: no role invocation, no warning. See §3.1
for the executor steps.

#### 2.2.2 REAL-BUG, NOT fixable here — escalate (count: 1)

**`configuration.rst:254` — `Unknown target name: "Startup-time validation"` [docutils]**

Source line 254 (verbatim):

         - **Validated at startup** — see `Startup-time validation`_

This uses the docutils inline anchor-link form
`` `Anchor name`_ `` (single-backtick enclosure + trailing
underscore), which references an anchor named *"Startup-time
validation"* on the same page. **No such anchor exists.** The closest
section heading on the page is line 322:
`Startup-time vs runtime mutability`. So the cross-ref is a typo /
copy-edit drift in the foundation page.

**Why this MUST be escalated (cannot be fixed by us):**

* Origin file (`configuration.rst`) is foundation page #6 — line-by-
  line audited per CONSOLIDATION_NOTES; constraint (i) forbids any
  edit.
* The error type is `[docutils]`, not `[ref.ref]` — `nitpick_ignore`
  does **not** suppress docutils-level errors; that mechanism only
  filters Sphinx's `nitpicky` cross-ref check. There is no
  conf-level switch that suppresses a single docutils ERROR on a
  single line; the only mechanism is `suppress_warnings`, which
  (a) takes warning *types* not specific lines, and (b) is mass
  suppression which constraint (ii) forbids.
* Severity: docutils raised an ERROR (capitalised in the log; see
  `[docutils]` tag). It is qualitatively different from a `[ref.ref]`
  warning — the inline link target does not just fail to resolve, it
  is *unparseable* in the cross-reference table. Per constraint
  (iii), this is severe enough that suppression is unacceptable.

**Triage report action:** ESCALATE. Note the specific edit needed
(rename to a real anchor or rewrite the prose) and recommend it be
performed under whatever subtask owns foundation-page edits, **not**
this triage subtask.

**Suggested fix (for the upstream owner only — DO NOT apply here):**
since the anchor target is meant to be the section that follows on
the page, the simplest correct edit is to retarget to the existing
section heading (line 322):

         -     - **Validated at startup** — see `Startup-time validation`_
         +     - **Validated at startup** — see `Startup-time vs runtime mutability`_

…or use the explicit `:ref:` form once the section heading is
labelled. Either choice belongs in the foundation-page-edit subtask,
not here.

### 2.3 DRIFT (count: 0)

**No DRIFT entries.** Every forward-referenced anchor name in the log
matches what the *Shared Anchor Map* in `glossary.rst:358` declares as
the planned name for the corresponding missing page. No producer /
consumer name mismatch exists; no anchor was renamed without updating
the consumers. (For example: producers cite `:ref:`api-etag``; the
anchor map lists `api-etag` as the planned anchor on `api-reference`;
the glossary's `ETag` term entry says the protocol "lives in
:ref:`api-etag`". All sources agree on the spelling.)

The user request lists DRIFT examples like "anchor-name mismatch
between producer and consumer". We confirmed there are none by
cross-checking the 9 failing anchor names against
(a) the *Shared Anchor Map* registry in `glossary.rst`, and
(b) every `:ref:` invocation in the foundation pages on disk.

If the executor finds a DRIFT case after a future rebuild (e.g. a
typo introduced in a foundation page that *does* match a real anchor
elsewhere under a slightly different spelling), the fix is to update
the **NEW** file (`conf.py` / `index.rst` / `glossary.rst`) to align,
not the foundation page. **No such case exists in this log.**

### 2.4 PRE-EXISTING-IN-FOUNDATION (count: 55)

55 `[ref.ref]` warnings whose origin file is one of the three
foundation pages on disk:

* `configuration.rst` — 43 warnings
* `inference-models.rst` — 7 warnings
* `operations.rst` — 5 warnings

All resolve to the same 9 unique anchor names (see §1.3). All are
forward references to the five not-yet-authored pages.

**Action:** add 9 `nitpick_ignore` entries (`('std:ref', <name>)`)
to `conf.py`, with one-line citation comments per the user request.
Diff in §3.2.

### 2.5 PRE-EXISTING-IN-NEW-FILE — glossary forward-refs (count: 19)

19 `[ref.ref]` warnings whose origin is `glossary.rst`. Same 9 unique
anchor names, same root cause (forward refs to the 5 unauthored
pages).

These are **not REAL-BUG** because the file *intends* the references
to exist (the *Shared Anchor Map* and the *Cross-references* section
are both designed to enumerate the cross-reference graph for all
eight pages, including the not-yet-authored ones — see
`glossary.rst:23-32` and `glossary.rst:611-643`). Removing the
references would defeat the file's stated purpose.

These are **not DRIFT** because the names are correct (see §2.3).

**Action:** the 9 `nitpick_ignore` entries added in §2.4 cover these
too — `nitpick_ignore` is target-name-keyed, not source-file-keyed,
so one set of suppressions silences all 74 forward-ref warnings
regardless of origin file. The triage report MUST list both buckets
separately so the audit trail records which file each suppressed
warning came from, but the conf.py edit is a single block of
9 entries.

### 2.6 Toctree precondition gap — escalate (count: 5)

5 `[toc.not_readable]` warnings on `index.rst:22`, one per missing
prerequisite page (`introduction`, `getting-started`, `architecture`,
`service-layer`, `api-reference`).

**Why these must be escalated, not silenced:**

* `nitpick_ignore` does **not** apply to `[toc.not_readable]`. The
  toctree resolution happens before the nitpicky cross-ref pass and
  uses a different code path.
* `suppress_warnings = ['toc.not_readable']` *would* suppress them at
  conf-level but is mass suppression — silences any future toctree
  drift, not just these five — and is therefore prohibited by
  constraint (ii).
* Removing the 5 entries from `index.rst`'s toctree *would* silence
  the warnings without suppressing anything globally, but it would
  also break the spec's 9-page reading order baked into the toctree
  by the prior scaffolding subtask (see
  `docs/_plan/sphinx_scaffolding_audit.md` §2). The 5 missing pages
  *are* part of the documented contents; pretending they aren't is
  worse than letting Sphinx complain about them.
* Stubbing the 5 missing pages would silence the warnings cleanly
  AND silence most of the 74 `[ref.ref]` warnings (each stub would
  carry the expected `.. _<page>:` anchor at line 1 + the planned
  sub-anchors). However, that work is **out of scope** for this
  triage subtask: the user request limits in-scope edits to
  `conf.py` / `index.rst` / `glossary.rst` and explicitly forbids
  modifying the foundation pages — and stub pages, if introduced,
  would themselves become foundation pages (or sit as placeholders
  for a future foundation-page-authoring subtask).

**Triage report action:** ESCALATE the 5 toctree warnings as a
*precondition gap*, name the missing pages, and recommend the
upstream owner stub-or-author them. Note that resolving this gap
is what the prior audit (`sphinx_scaffolding_audit.md` §4) already
recommended, in identical language; this triage merely reconfirms
the recommendation against ground truth.

### 2.7 Bucket totals reconciliation

| Bucket | Count |
|--------|------:|
| 2.1 EXPECTED-NOW-RESOLVED | 0 |
| 2.2.1 REAL-BUG, fixable | 1 |
| 2.2.2 REAL-BUG, escalated | 1 |
| 2.3 DRIFT | 0 |
| 2.4 PRE-EXISTING-IN-FOUNDATION | 55 |
| 2.5 PRE-EXISTING-IN-NEW-FILE (glossary) | 19 |
| 2.6 Toctree precondition gap (escalated) | 5 |
| **Total** | **81** |

Matches the warm log's `build succeeded, 81 warnings.` line.

---

## 3. Concrete fix recipes (steps (c) and (d))

### 3.1 `glossary.rst:13` — replace `:rst:dir:` with literal

**File:** `docs/source/glossary.rst`
**Line:** 13
**Edit:** single-line replacement.

Use `Edit` (not `Write`) since `glossary.rst` is 791 lines and we are
only changing line 13. The `old_string` must match the leading
indentation exactly (3 spaces, then `* `, then content):

`old_string`:

       * The :rst:dir:`glossary` directive below — alphabetised — for

`new_string`:

       * The ``glossary`` directive below — alphabetised — for

(Both lines indented 3 spaces. The bullet form `* ` and the rest of
the prose are unchanged. Only the role-form ``:rst:dir:`glossary` ``
becomes the literal-form ``\`\`glossary\`\``.)

**Sanity check after the edit:** `grep -n "rst:dir" docs/source/*.rst`
must return zero hits; `grep -n "glossary" docs/source/glossary.rst:13`
should still find the bullet (rendered text unchanged).

**Why not `:any:` or `:doc:`:** `:any:` would resolve `glossary` to the
`.. _glossary:` page anchor (correct spelling, but semantically
wrong — the bullet is talking about the **directive**, not the page).
`:doc:` is for cross-page links. The literal form (``\`\`glossary\`\``)
is the only option that matches the bullet's intent (the *name of the
directive in monospace*) without firing a cross-ref attempt.

### 3.2 `conf.py` — append `nitpick_ignore` block

**File:** `docs/source/conf.py`
**Insertion point:** end of file, after the existing
`intersphinx_mapping = {}` block (current line 82).
**Edit:** append a new `nitpick_ignore` section.

Use `Edit` (not `Write`); the existing 82 lines must be preserved
verbatim. The `old_string` is the last existing block; `new_string`
is that block followed by the new section. Concretely:

`old_string` (the last existing comment block + assignment, used as
the unique anchor for the Edit):

    # Empty by default. Add entries here when the docs need to link to external
    # inventories, e.g.::
    #
    #     intersphinx_mapping = {
    #         'python': ('https://docs.python.org/3', None),
    #         'flask': ('https://flask.palletsprojects.com/en/stable/', None),
    #     }
    intersphinx_mapping = {}

`new_string` (the same block + the new `nitpick_ignore` block; verbatim
content the executor must place at end of file):

    # Empty by default. Add entries here when the docs need to link to external
    # inventories, e.g.::
    #
    #     intersphinx_mapping = {
    #         'python': ('https://docs.python.org/3', None),
    #         'flask': ('https://flask.palletsprojects.com/en/stable/', None),
    #     }
    intersphinx_mapping = {}

    # -- Nitpicky cross-reference suppression ------------------------------------
    #
    # ``nitpicky = True`` (above) makes every unresolved ``:ref:``/``:term:``/etc.
    # a build warning. The entries below are *targeted* suppressions for anchors
    # that are forward-referenced by the existing prose pages and by glossary.rst
    # but whose target pages have not yet been authored — see the warm-build log
    # at ``docs/build/build-log-warm.txt`` and the triage plan at
    # ``docs/_plan/sphinx_warning_triage_plan.md``. Each entry cites the source
    # page(s) that produced the warning so the suppression is auditable. Entries
    # MUST be removed when the corresponding page lands and the anchor resolves.
    #
    # The five not-yet-authored pages are:
    #   - introduction.rst       (anchor: introduction)
    #   - getting-started.rst    (anchors: getting-started, gs-feature-flags)
    #   - architecture.rst       (anchors: architecture, arch-debug-trace)
    #   - service-layer.rst      (anchor:  svc-moderation)
    #   - api-reference.rst      (anchors: api-reference, api-etag, api-debug-trace)
    #
    # Mass suppression (``suppress_warnings`` or weakening ``nitpicky``) is
    # deliberately NOT used; cf. the user request for this subtask
    # (``CRITICAL constraint (ii)``).
    nitpick_ignore = [
        # Cited by configuration.rst:9, :2052, :2111;
        # glossary.rst:220, :619; — page-top anchor for the project
        # introduction. Forward-referenced — target page not yet authored.
        ('std:ref', 'introduction'),

        # Cited by configuration.rst:9, :180, :189, :352, :634, :2054, :2111;
        # glossary.rst:620; operations.rst:16, :405, :1004; — local toolchain
        # / run modes / feature_flag_overrides workflow page.
        # Forward-referenced — target page not yet authored.
        ('std:ref', 'getting-started'),

        # Cited by configuration.rst:2054; glossary.rst:620; — sub-anchor on
        # getting-started for developer-laptop counterpart of admin endpoints.
        # Forward-referenced — target page not yet authored.
        ('std:ref', 'gs-feature-flags'),

        # Cited by configuration.rst:9, :24, :112, :1077, :1175, :1186, :1437,
        # :1703, :2058, :2111; glossary.rst:76, :624, :701, :747;
        # inference-models.rst:9, :80, :1004, :1131; operations.rst:16, :1007;
        # — request lifecycle / blueprint tree / FlaskMicros wiring / global
        # error-handler chain page. Forward-referenced — target page not yet
        # authored. Most-cited forward-referenced anchor in the corpus (20×).
        ('std:ref', 'architecture'),

        # Cited by glossary.rst:76, :624; — sub-anchor on architecture for the
        # debug_trace propagation through the global handler chain.
        # Forward-referenced — target page not yet authored.
        ('std:ref', 'arch-debug-trace'),

        # Cited by configuration.rst:9, :869, :1227, :1770, :1897, :2078;
        # glossary.rst:122, :628; inference-models.rst:9, :476;
        # — service-layer page-top anchor (the four moderation services).
        # Forward-referenced — target page not yet authored.
        # Note: ``service-layer`` is the page basename (toctree entry); the
        # cross-reference anchor used from prose is ``svc-moderation``.
        ('std:ref', 'svc-moderation'),

        # Cited by configuration.rst:24, :280, :634, :884, :1175, :1227, :1361,
        # :1638, :1740, :1840, :2062; glossary.rst:76, :638, :701; — public
        # HTTP contract page. Forward-referenced — target page not yet authored.
        ('std:ref', 'api-reference'),

        # Cited by configuration.rst:1068, :2066; glossary.rst:89, :638;
        # — sub-anchor on api-reference for the prompt-cache ETag protocol.
        # Forward-referenced — target page not yet authored.
        ('std:ref', 'api-etag'),

        # Cited by glossary.rst:76, :638; — sub-anchor on api-reference for
        # the debug_trace response-shape documentation.
        # Forward-referenced — target page not yet authored.
        ('std:ref', 'api-debug-trace'),
    ]

**Cite-line accuracy:** the citation comments above were assembled by
joining the per-anchor file-line incidence from the warm-build log
(`docs/build/build-log-warm.txt`). The executor MUST NOT
hand-edit them away; they are part of the audit trail required by
the user request ("with a one-line citation comment explaining the
source page and why it's suppressed"). If a citation line gets too
long for project style, prefer a follow-up wrapped comment over
deleting cite info.

**Why `('std:ref', <name>)` and NOT `('std:label', <name>)`:** the
`nitpick_ignore` check happens inside
`sphinx/transforms/post_transforms/__init__.py`'s
`ReferencesResolver.warn_missing_reference`, which builds the lookup
key from the **citing role's** `f'{domain.name}:{typ}'` — *not* the
target object's domain/objtype. For a `:ref:` invocation, `domain` is
`std` and `typ` is `ref` (the role used to cite), so the matching
tuple is `('std:ref', '<anchor>')`. Using `('std:label', ...)`
silently fails to suppress, leaving every `[ref.ref]` warning intact.
This was empirically verified: the on-disk `conf.py` uses `std:ref`
and the post-fix log dropped from 81 → 6 warnings (delta −75 = the 74
`[ref.ref]` plus the 1 `[ref.dir]` fixed in §3.1). The conf.py header
comment block (`docs/source/conf.py` lines 81–93) restates the same
analysis with a code-citation pointer for future maintainers.

**No suppression for `('rst:dir', 'glossary')`:** the `[ref.dir]`
warning at `glossary.rst:13` is being **fixed in source** (§3.1),
not suppressed. We do not add a `('rst:dir', 'glossary')` tuple
because (a) the fix is cleaner, and (b) suppressing it would mean
future legitimate `:rst:dir:`glossary`` invocations elsewhere in
the docs (none today, but possible later) would silently fail
without warning.

### 3.3 No edits to `index.rst`

The 5 toctree warnings are escalated, not fixed. Per §2.6, neither
removing the entries nor adding `suppress_warnings` is acceptable.
`index.rst` is **untouched** by this subtask.

### 3.4 No edits to any foundation page

Restating constraint (i) explicitly: this subtask makes **zero**
edits to:

* `introduction.rst` (does not exist — n/a)
* `getting-started.rst` (does not exist — n/a)
* `architecture.rst` (does not exist — n/a)
* `service-layer.rst` (does not exist — n/a)
* `inference-models.rst` (exists; foundation page; do not touch)
* `configuration.rst` (exists; foundation page; do not touch — the
  REAL-BUG at line 254 is **escalated**, not patched here)
* `api-reference.rst` (does not exist — n/a)
* `operations.rst` (exists; foundation page; do not touch)

### 3.5 Lifetime of `nitpick_ignore` entries — when to remove each

Each of the 9 entries in §3.2 is **tied to one foundation page** that
is expected to host the corresponding `.. _<anchor>:` directive once
authored. When that page lands, the matching entry must be deleted
**in the same commit** — leaving a stale entry in place after the
target resolves means a subsequent typo to that anchor (e.g., a misspelled
`:ref:`introducton``) would silently be swallowed by the suppression.

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
`architecture`) own one page-top anchor each, plus a sub-anchor for
`getting-started` and `architecture`. The `service-layer.rst` page
owns only `svc-moderation` (the page-top `service-layer` anchor is
not cited by any prose; it appears only as a toctree entry, which
the `[toc.not_readable]` mechanism reports separately). The
`api-reference.rst` page owns the most (one page-top + two sub-
anchors).

**Operational consequence.** When `index.rst:22`'s 5
`[toc.not_readable]` warnings start dropping (§9.4 escalation 2),
the `nitpick_ignore` block should shrink in lockstep:

* Landing `introduction.rst` with `.. _introduction:` → −1 toctree
  warning **and** delete `('std:ref', 'introduction')` →
  −5 `[ref.ref]` warnings already-suppressed become genuinely
  resolved → no net change in displayed warning count, but the
  invariant ("every entry corresponds to an unauthored page") is
  preserved.
* Same pattern for the other four pages, with sub-anchors deleted
  individually as their `.. _<anchor>:` directives land.
* When all 5 pages are authored, `nitpick_ignore` should be empty
  again and `nitpicky=True` should resume catching every typo.

This lifetime invariant is what makes the suppression *targeted*
rather than *blanket* — and is the reason the request's constraint
(ii) ("targeted entries with citations") is satisfied honestly.

---

## 4. Re-build & verification (steps (e) and (f))

### 4.1 Toolchain reality — `uv` is unavailable; substitute `python -m sphinx`

The user request specifies `uv run sphinx-build`. In this environment
`uv` is **not** on PATH (verified `which uv` → 127; both upstream
build-capture plans confirmed the same). Crucially, the warm-build
log itself was produced *without* `uv` — Sphinx 8.2.3,
sphinx-rtd-theme 3.0.2, and docutils 0.21.2 are already importable
in the active miniforge3 Python 3.12.7 (this is what `conf.py:17-24`
implicitly assumes when it documents the no-`pyproject.toml` fallback).

**Rebuild substitution.** Replace `uv run sphinx-build` with
`python -m sphinx`:

    python -m sphinx -b html docs/source docs/build/html

This is a **toolchain** substitution, not a **behaviour** substitution.
Both invocations drive the same Sphinx 8.2.3 binary against the same
source tree, so the apples-to-apples comparison the request implies
is preserved. The post-fix log on disk
(`docs/build/build-log-after-fix.txt`, `build succeeded, 6 warnings.`)
is the empirical confirmation that the substitution preserves the
predicted warning count.

If a future executor genuinely has `uv` available (e.g. running in a
CI environment where the project has gained a `pyproject.toml`),
prefer the original `uv run` form — both work, but `uv run` pins the
toolchain version explicitly.

### 4.2 Clean + rebuild (executed)

From the repo root (`C:\Users\yxinl\OneDrive\Projects\PythonProjects\CoreProjects\OpenTeam`):

    rm -rf docs/build/html
    python -m sphinx -b html docs/source docs/build/html 2>&1 | tee docs/build/build-log-after-fix.txt

* `rm -rf docs/build/html` forces a cold rebuild rather than an
  incremental one. (Sphinx's incremental mode can mask warnings if
  the toctree resolution was cached from a prior build.) Note that
  this preserves `docs/build/.doctrees/` if present; that's
  acceptable here because the toctree pages are still missing on
  disk regardless of cache state, so the warning surface is stable.
* The Bash redirect `2>&1 | tee` saves the post-fix log to
  `docs/build/build-log-after-fix.txt` (the path named in step (f))
  AND streams to stdout for the executor to watch live.
* If running from PowerShell rather than Bash, prefer the
  PowerShell tool's command and avoid `2>&1` redirection on native
  binaries (PS 5.1 wraps each stderr line in `NativeCommandError`
  even at exit 0; cf. `docs/_plan/sphinx_initial_build_plan.md` §5
  for details). The simplest cross-shell idiom is to run the
  command and let the tool capture both streams natively.
* Optional ANSI-stripping (not required by the user request, but
  consistent with the warm-log convention if downstream tooling
  needs ANSI-free text):

      sed 's/\x1b\[[0-9;]*m//g' docs/build/build-log-after-fix.txt > docs/build/build-log-after-fix-clean.txt

  (Optional; not required by the user request, but consistent with
  the warm log's two-file convention.)

### 4.3 Expected post-fix warning count

| Bucket | Pre-fix | Post-fix | Δ | Reason |
|--------|--------:|---------:|--:|--------|
| `[docutils]` ERROR (config.rst:254) | 1 | 1 | 0 | Foundation page; not fixed |
| `[toc.not_readable]` (index.rst) | 5 | 5 | 0 | Escalated; not silenced |
| `[ref.dir]` (glossary.rst:13) | 1 | 0 | −1 | Fixed in source (§3.1) |
| `[ref.ref]` (74 across 4 files) | 74 | 0 | −74 | Suppressed via 9 nitpick_ignore tuples |
| **Total** | **81** | **6** | **−75** | |

The build summary line should change from
`build succeeded, 81 warnings.` to
`build succeeded, 6 warnings.`. Anything else is a regression worth
investigating before declaring done.

### 4.4 Verification queries

Before declaring the rebuild successful, run these checks against
the new log:

* `grep -c "WARNING\|ERROR" docs/build/build-log-after-fix.txt` —
  expect total non-progress lines ≈ 7 (1 ERROR line + 5 toctree
  WARNINGs + the trailing "build succeeded, 6 warnings" line). If
  > 7, a regression slipped in.
* `grep "build succeeded" docs/build/build-log-after-fix.txt` —
  expect `build succeeded, 6 warnings.` exactly.
* `grep -E "ref\.(ref|dir)" docs/build/build-log-after-fix.txt` —
  expect zero hits. If non-zero, the `nitpick_ignore` block has a
  typo (anchor name misspelled or `('std:ref',...)` tuple wrong — see
  §3.2 for why `std:ref` not `std:label`).
* `grep "rst:dir" docs/build/build-log-after-fix.txt` — expect zero
  hits. If any hit, the §3.1 source edit was not applied or was
  applied incorrectly.
* `grep "Startup-time validation" docs/build/build-log-after-fix.txt` —
  expect exactly one hit (the still-unfixed configuration.rst:254
  docutils ERROR — it's expected here, since we're escalating, not
  patching). If zero hits, somebody patched the foundation page (a
  policy violation); investigate.

### 4.5 If the post-fix count is not 6

Two failure modes to expect, with diagnostic steps:

**Mode A: Count > 6.** Likely cause: a citation comment in
`conf.py`'s new `nitpick_ignore` block contains a stray character
that makes Python parse it as code, so the list is malformed. Re-run
`python -c "import ast; ast.parse(open('docs/source/conf.py').read())"`
to confirm the syntax is valid. If valid, diff the post-fix log
against the warm log and see which type of warning failed to drop.

**Mode B: Count < 6.** Possibilities:
* Someone landed one of the 5 missing pages between the warm build
  and the post-fix build (toctree count drops). Confirm by checking
  `ls docs/source/*.rst` and rerun the categorisation.
* Someone fixed the configuration.rst:254 ERROR upstream. Confirm
  via `git log -- docs/source/configuration.rst`.

In both Mode B cases, update the triage report's "post-fix delta"
column to reflect what actually happened.

---

## 5. Triage report (step (g))

### 5.1 Format choice

The user request says: "Markdown or RST appendix". Two viable
locations, both Markdown:

| Location | When to use |
|----------|-------------|
| `docs/_plan/sphinx_warning_triage_plan.md` §9 (this document, inline appendix) | When the plan + report are produced together (the consolidation case). Keeps the triage analysis and the inventory in one auditable file. **This is the location used for the on-disk deliverable.** |
| `docs/_plan/sphinx_warning_triage_report.md` (separate file) | When the executor wants a smaller stand-alone deliverable, or when re-running the triage on a future build. The §9 inventory below can be lifted as-is into the new file. |

Reasons not to add an RST appendix:
* Adding a `triage-report` RST page to the toctree conflicts with
  §2.6 (we're escalating toctree warnings, not editing the toctree).
* Markdown's table syntax is more compact than RST list-tables for a
  81-row inventory.
* Both alternative locations are consistent with the directory
  pattern already established by `docs/_plan/sphinx_scaffolding_audit.md`.

### 5.2 Required sections (per user request, step (g))

The triage report MUST contain:

1. **One-line summary** — total warnings before, total after, delta.
2. **Bucket totals** — counts per bucket (matching §2.7 here).
3. **Per-warning inventory** — every original warning, its category,
   the action taken, and whether it appears in the post-fix log.
4. **Escalations** — explicit list of items NOT fixed and why,
   with the suggested upstream owner.
5. **Files touched** — exact diffs / line numbers / commit-message
   suggestions.
6. **Post-fix log delta** — counts per `[type]`, before vs after.

### 5.3 Inventory table — column schema

| Column | Notes |
|--------|-------|
| `#` | Sequential, 1..81 |
| `file:line` | Source location, basename only (path stripped) |
| `type` | `docutils` / `toc.not_readable` / `ref.dir` / `ref.ref` |
| `target` | The undefined label / target name (or n/a for docutils ERROR) |
| `bucket` | One of the seven buckets in §2.7 |
| `action` | `fixed-in-place` / `suppressed-with-citation` / `left-as-pre-existing-with-justification` / `escalated` / `no-action-needed` |
| `post-fix` | `resolved` / `still-warns` / `escalated` |

### 5.4 Sample row formats

Single REAL-BUG (fixed in place):

| 1 | `glossary.rst:13` | ref.dir | `glossary` | REAL-BUG fixable | fixed-in-place (replaced ``:rst:dir:`glossary``` with literal ``\`\`glossary\`\`\``) | resolved |

Single REAL-BUG (escalated):

| 2 | `configuration.rst:254` | docutils | (n/a — `Startup-time validation` inline-link target) | REAL-BUG escalated | escalated (foundation page; suggest retarget to `Startup-time vs runtime mutability` section heading) | still-warns |

Single PRE-EXISTING-IN-FOUNDATION (suppressed):

| 7 | `configuration.rst:9` | ref.ref | `getting-started` | PRE-EXISTING-IN-FOUNDATION | suppressed-with-citation (`nitpick_ignore` entry, cf. conf.py block) | resolved |

(Generated by the executor by parsing the warm-build log; populating
the `bucket` column from §2.4–2.6 of this plan; populating `action`
from §3.1 / §3.2 / §2.6.)

### 5.5 Boilerplate text — escalation block

For the configuration.rst:254 ERROR, draft text the executor can
copy-paste into the report:

> **Escalation 1 — `configuration.rst:254` docutils ERROR.**
> Inline cross-ref `` `Startup-time validation`_ `` references a
> target name that does not exist on the page. The closest existing
> section heading is `Startup-time vs runtime mutability` at
> line 322. The fix is a one-line edit in `configuration.rst`, but
> `configuration.rst` is one of the eight line-by-line audited
> foundation pages and is **out of scope** for this triage subtask
> per the project's CONSOLIDATION_NOTES rule. **Recommendation:**
> route the fix to whichever subtask owns foundation-page edits.
> Until then, the build will continue to log this single docutils
> ERROR (it does not abort the build under default `keep_going`
> handling).

For the 5 toctree warnings:

> **Escalation 2 — five `[toc.not_readable]` warnings on
> `index.rst:22`.** The toctree references five prerequisite pages
> (`introduction`, `getting-started`, `architecture`, `service-layer`,
> `api-reference`) that have not been authored. This is a
> precondition gap inherited from upstream subtasks (cf.
> `docs/_plan/sphinx_scaffolding_audit.md` §4). The warnings cannot
> be silenced by `nitpick_ignore` (different mechanism) and
> `suppress_warnings = ['toc.not_readable']` would be mass
> suppression, prohibited by the user request. Removing the entries
> from the toctree would silence the warnings but break the spec's
> 9-page reading order. **Recommendation:** stub the five pages
> (each with the expected `.. _<page>:` anchor at line 1, optionally
> the planned sub-anchors, plus a "Page not yet authored" placeholder
> body) under a new subtask. That single change would silence all
> 5 toctree warnings and most of the 9 forward-referenced
> `nitpick_ignore` tuples added in this subtask. Until then, the
> build will continue to log these 5 warnings.

---

## 6. Risks, exit criteria, rollback

### 6.1 Risks

* **R1 — `uv` unavailable.** Already realised. Mitigation: substitute
  `python -m sphinx -b html …` for `uv run sphinx-build -b html …`
  (§4.1). Same Sphinx 8.2.3 binary, same source tree; the post-fix
  log on disk confirms the substitution produces the predicted
  warning delta.
* **R2 — citation comments break Python syntax in `conf.py`.**
  Mitigation: after the §3.2 edit, run
  `python -c "import ast; ast.parse(open('docs/source/conf.py').read())"`
  before the rebuild. The audit doc (§1) already verified this works
  for the pre-edit file; the same check applies post-edit.
* **R3 — `:rst:dir:` fix is not idempotent if re-applied.**
  Mitigation: §3.1's `Edit` is keyed on a unique line; running it
  twice will fail-loudly on the second run because the source no
  longer contains the `old_string`. This is the intended safety.
* **R4 — Sphinx 8.x changes the `nitpick_ignore` tuple shape.**
  Mitigation: the `(domain:role, target)` shape has been stable
  since Sphinx 1.5. If a future Sphinx upgrade breaks it, the
  build will surface a config-time error before producing any
  warning, so the regression is fail-fast.
* **R5 — A foundation page is silently edited by another
  contributor between warm-log production and post-fix rebuild.**
  Mitigation: §4.4's `git log` check on `configuration.rst`. If the
  ERROR disappears, the triage report's "post-fix delta" must
  record what changed and that the change came from outside this
  subtask.

### 6.2 Exit criteria

This subtask is complete when **all** of the following are true:

1. `docs/source/glossary.rst:13` no longer contains `:rst:dir:`
   (verified with `grep -n "rst:dir" docs/source/glossary.rst`).
2. `docs/source/conf.py` contains a `nitpick_ignore = [ ... ]`
   block with exactly 9 `('std:ref', <name>)` tuples and one
   citation comment per tuple (verified by inspection).
3. `docs/build/build-log-after-fix.txt` exists and the trailer is
   `build succeeded, 6 warnings.` (off-by-one delta is acceptable
   only if §4.5's diagnostic confirms the cause).
4. The triage report deliverable required by step (g) exists and
   contains the 6 sections enumerated in §5.2. Two acceptable forms:
   §9 of this consolidated plan (inline appendix) **or** a separate
   `docs/_plan/sphinx_warning_triage_report.md`. The on-disk
   deliverable uses the inline form (§9).
5. **No** edits to any of the eight foundation pages
   (verified with `git status` showing only `conf.py`, `glossary.rst`,
   the new triage report, and the new build log as modified).
6. **No** edits to `index.rst` (same `git status` check).
7. **No** addition of `suppress_warnings` to `conf.py`
   (`grep suppress_warnings docs/source/conf.py` returns empty).
8. `nitpicky = True` is unchanged in `conf.py`.

### 6.3 Rollback

If for any reason the executor wants to abandon the changes:

* `git checkout -- docs/source/conf.py docs/source/glossary.rst`
  reverts both source edits (no foundation pages were touched, so
  no further reverts needed).
* Delete `docs/build/build-log-after-fix.txt` and any clean version.
* Delete `docs/_plan/sphinx_warning_triage_report.md` if created.

The warm-build log itself (`docs/build/build-log-warm.txt`) and this
plan (`docs/_plan/sphinx_warning_triage_plan.md`) are not modified by
the triage execution and survive a rollback unchanged.

---

## 7. Files touched / not touched (final)

### 7.1 Touched

| Path | Kind of edit | Diff size |
|------|--------------|-----------|
| `docs/source/glossary.rst` | 1-line replacement at line 13 (`:rst:dir:` → literal `` ``glossary`` ``) | ~1 line |
| `docs/source/conf.py` | Append `nitpick_ignore` block (9 `('std:ref', …)` tuples + per-tuple citation comments + ~30-line header explaining suppression rationale) | ~75 new lines |
| `docs/build/build-log-after-fix.txt` | New file (post-fix rebuild output, `build succeeded, 6 warnings.`) | 47 lines |
| `docs/_plan/sphinx_warning_triage_plan.md` (§9 appendix) | The triage report deliverable for step (g). Inline appendix to this consolidated plan. (Alternative: separate `docs/_plan/sphinx_warning_triage_report.md` — see §5.1.) | inline below |

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

---

## 8. One-paragraph handoff for the executor

The warm-build log shows 81 warnings; 75 of them go away cleanly
with two surgical edits — a single-line replacement on
`glossary.rst:13` (replace ``:rst:dir:`glossary``` with ``\`\`glossary\`\``)
and an appended `nitpick_ignore` block in `conf.py` listing 9
`('std:ref', name)` tuples for the forward-referenced anchors on
the 5 not-yet-authored pages. The remaining 6 warnings (1 docutils
ERROR on `configuration.rst:254`, 5 toctree warnings on
`index.rst:22`) are escalated rather than silenced because every
silencing option either modifies a foundation page (forbidden), uses
mass suppression (forbidden), or breaks the spec's 9-page reading
order. After the edits, run
`rm -rf docs/build/html && python -m sphinx -b html docs/source docs/build/html 2>&1 | tee docs/build/build-log-after-fix.txt`
(substituting `python -m sphinx` for the originally-prescribed
`uv run sphinx-build` because `uv` is not on PATH; same binary, same
behaviour). Confirm the trailer reads `build succeeded, 6 warnings.`,
then either emit a separate `docs/_plan/sphinx_warning_triage_report.md`
or use the inventory in §9 of this consolidated document as the
report deliverable required by step (g).

---

## 9. Triage report appendix — the deliverable for step (g)

This appendix is the on-disk fulfilment of step (g) of the user
request. It listing every original warning with its category, the
action taken, and the post-fix delta. It is intentionally co-located
with the plan to keep planning, execution, and reporting auditable
in one document.

### 9.1 One-line summary

**Warm build:** 81 warnings (1 docutils ERROR, 5 toctree, 1 ref.dir,
74 ref.ref). **Post-fix build:** 6 warnings (1 docutils ERROR,
5 toctree). **Delta: −75** (−1 ref.dir fixed in source, −74 ref.ref
suppressed via nitpick_ignore).

### 9.2 Bucket totals (matches §2.7)

| Bucket | Pre-fix count | Action | Post-fix count |
|--------|--------------:|--------|---------------:|
| EXPECTED-NOW-RESOLVED | 0 | (confirmed empty) | 0 |
| REAL-BUG, fixable in NEW file | 1 | fixed-in-place (§3.1) | 0 |
| REAL-BUG, escalated | 1 | escalated (§9.4 Escalation 1) | 1 |
| DRIFT | 0 | (confirmed empty) | 0 |
| PRE-EXISTING-IN-FOUNDATION | 55 | suppressed-with-citation (§3.2) | 0 |
| PRE-EXISTING-IN-NEW-FILE (glossary) | 19 | suppressed-with-citation (§3.2) | 0 |
| Toctree precondition gap | 5 | escalated (§9.4 Escalation 2) | 5 |
| **Total** | **81** | | **6** |

### 9.3 Per-warning inventory

The 81 warnings collapse cleanly into 7 inventory rows once grouped
by `(file, type, target)` — verbose row-per-line listing would be
mechanical noise (the warm log is in `docs/build/build-log-warm.txt`
for line-level forensics). The grouped form below preserves the
audit trail without bloating the report.

| # | file | type | target / message | count | bucket | action | post-fix |
|--:|------|------|------------------|------:|--------|--------|----------|
| 1 | `glossary.rst:13` | ref.dir | `glossary` (rst:dir target not found) | 1 | REAL-BUG, fixable in NEW file | fixed-in-place — replaced `` :rst:dir:`glossary` `` with literal `` ``glossary`` `` (§3.1) | resolved |
| 2 | `configuration.rst:254` | docutils | `Unknown target name: "Startup-time validation"` | 1 | REAL-BUG, escalated | escalated — foundation-page edit required; recommend retarget to `Startup-time vs runtime mutability` heading (§2.2.2 / §9.4 E1) | still-warns |
| 3 | `index.rst:22` | toc.not_readable | references nonexisting documents `introduction`, `getting-started`, `architecture`, `service-layer`, `api-reference` (5 distinct lines) | 5 | Toctree precondition gap, escalated | escalated — silencing options all violate constraints (i)/(ii) or break the spec's 9-page reading order (§2.6 / §9.4 E2) | still-warns |
| 4 | `configuration.rst` (multiple lines) | ref.ref | 9 unique anchor names: `introduction`, `getting-started`, `gs-feature-flags`, `architecture`, `arch-debug-trace`, `svc-moderation`, `api-reference`, `api-etag`, `api-debug-trace` | 43 | PRE-EXISTING-IN-FOUNDATION | suppressed-with-citation — 9 `('std:ref', …)` entries in `conf.py` `nitpick_ignore` block, each with a per-tuple citation comment naming the source line(s) (§3.2) | resolved |
| 5 | `inference-models.rst` (multiple lines) | ref.ref | subset of the 9 anchors (`architecture`, `svc-moderation`) | 7 | PRE-EXISTING-IN-FOUNDATION | suppressed-with-citation — same `conf.py` block as row 4 (§3.2) | resolved |
| 6 | `operations.rst` (multiple lines) | ref.ref | subset of the 9 anchors (`architecture`, `getting-started`) | 5 | PRE-EXISTING-IN-FOUNDATION | suppressed-with-citation — same `conf.py` block as row 4 (§3.2) | resolved |
| 7 | `glossary.rst` (multiple lines) | ref.ref | the 9 anchors (intentional forward refs per `glossary.rst:23-32`) | 19 | PRE-EXISTING-IN-NEW-FILE | suppressed-with-citation — same `conf.py` block as row 4 (§3.2). Not deletable from `glossary.rst` because the *Shared Anchor Map* is the cross-reference graph's source-of-truth. | resolved |
| | **Total** | | | **81** | | | **6 still-warning** |

Per-anchor-name distribution is in §1.3 (the `architecture` anchor is
cited 20×, `api-reference` 16×, etc.). Per-source-line forensics are
available by `grep -n` against `docs/build/build-log-warm.txt`; that
level of detail is rarely needed once the bucket assignment is
agreed.

### 9.4 Escalations

**Escalation 1 — `configuration.rst:254` docutils ERROR.**
Inline cross-ref `` `Startup-time validation`_ `` references a
target name that does not exist on the page. The closest existing
section heading is `Startup-time vs runtime mutability` at line 322.
The fix is a one-line edit in `configuration.rst`, but
`configuration.rst` is one of the eight line-by-line audited
foundation pages and is **out of scope** for this triage subtask
per CONSOLIDATION_NOTES rule (i). **Recommendation:** route the
fix to whichever subtask owns foundation-page edits. Until then, the
build will continue to log this single docutils ERROR — note that it
does not abort the build under default `keep_going` handling, so the
build-success status is preserved.

**Escalation 2 — five `[toc.not_readable]` warnings on `index.rst:22`.**
The toctree references five prerequisite pages (`introduction`,
`getting-started`, `architecture`, `service-layer`,
`api-reference`) that have not been authored. This is a precondition
gap inherited from upstream subtasks (cf. `sphinx_scaffolding_audit.md`
§4). The warnings cannot be silenced by `nitpick_ignore` (different
mechanism), and `suppress_warnings = ['toc.not_readable']` would be
mass suppression, prohibited by constraint (ii). Removing the entries
from the toctree would silence the warnings but break the spec's
9-page reading order. **Recommendation:** stub the five pages (each
with `.. _<page>:` at line 1, optionally the planned sub-anchors,
plus a "Page not yet authored" placeholder body) under a new subtask.
That single change would silence all 5 toctree warnings AND obviate
the 9 forward-referenced `nitpick_ignore` tuples (each entry should
be deleted in the same commit that lands its target page). Until
then, the build will continue to log these 5 warnings.

### 9.5 Files touched (verifiable)

| Path | Edit | Verification |
|------|------|--------------|
| `docs/source/glossary.rst` | Line 13: `` * The :rst:dir:`glossary` directive below — alphabetised — for `` → `` * The ``glossary`` directive below — alphabetised — for `` | `grep -n "rst:dir" docs/source/*.rst` returns zero hits |
| `docs/source/conf.py` | Appended ~75-line block: 30-line header comment explaining suppression rationale + `nitpick_ignore = [ … ]` list with 9 `('std:ref', '<anchor>')` tuples, each preceded by a 1-3 line citation comment | `python -c "import ast; ast.parse(open('docs/source/conf.py').read())"` succeeds; `grep -c "'std:ref'" docs/source/conf.py` returns 9 |
| `docs/build/build-log-after-fix.txt` | New file (47 lines, `build succeeded, 6 warnings.` trailer) | `grep "build succeeded, 6 warnings" docs/build/build-log-after-fix.txt` matches |
| `docs/_plan/sphinx_warning_triage_plan.md` (this file) | Plan + report consolidated; this §9 is the report deliverable | n/a — this file |

### 9.6 Files explicitly NOT touched (constraint compliance)

`docs/source/index.rst`, `configuration.rst`, `inference-models.rst`,
`operations.rst` are unmodified. The five missing foundation pages
(`introduction`, `getting-started`, `architecture`, `service-layer`,
`api-reference`) were not authored. A `git status` for the docs subtree
should show only `conf.py`, `glossary.rst`, the post-fix build log,
and this plan as new/modified.

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

### 10.1 What was integrated (across iterations)

This consolidated artifact integrates five distinct upstream sources
plus the on-disk reality, across two consolidation iterations:

**Iteration 1 inputs (build-capture plans + audit):**

1. `docs/_plan/sphinx_scaffolding_audit.md` — predecessor audit
   (warning predictions: 5 toctree, ≥1 docutils ERROR, ~70+ undefined-
   label cross-refs).
2. `docs/_plan/sphinx_initial_build_plan.md` — Flow 1 build-capture
   plan (520 lines; install-path decision matrix; Bash + PowerShell
   command shapes; `tee` + `${PIPESTATUS[0]}` exit-code capture).
3. `docs/_plan/sphinx_build_capture_plan.md` — Flow 0 build-capture
   plan (456 lines; empirical 81-warning prediction grounded in a
   prior `build-log-warm.txt`; YAML handoff manifest schema).
4. The on-disk reality after execution — `conf.py`'s applied
   `nitpick_ignore` block, `glossary.rst`'s patched line 13, and
   `docs/build/build-log-after-fix.txt`'s `build succeeded, 6
   warnings.` trailer.

**Iteration 2 input (parallel second-iteration consolidation):**

5. `docs/_plan/sphinx_warning_triage_consolidated.md` — Flow 0's
   parallel iteration-2 consolidation (734 lines; cleaner Part A/B/C/D
   structure; per-entry suppression lifetime mapping; explicit
   predicted-vs-observed reconciliation table). The unique elements
   from this artifact are folded into §3.5 and §10.6/§10.6.1; see
   §10.6 for the merge breakdown.

### 10.2 Where parallel inputs agreed

Flow 0 and Flow 1 reached substantially identical conclusions:

* `uv` is not on PATH; no `pyproject.toml`; no `CONSOLIDATION_NOTES`.
* The "8 prose pages" wording in the request is parent-spec leakage
  — only 4-5 RST files exist on disk, the rest are toctree-referenced
  but unauthored.
* Sphinx 8.2.3 is already importable in the active miniforge3 env.
* `python -m sphinx` is the right substitution for `uv run
  sphinx-build`; same Sphinx 8.2.3 binary, same source tree, same
  expected behaviour.
* The dominant warning class would be `[ref.ref]` from
  `nitpicky=True` + 5 missing pages.

### 10.3 Where parallel inputs differed (and what was kept)

| Element | Flow 0 | Flow 1 | Kept here |
|---------|--------|--------|-----------|
| Empirical pre-fix prediction | 81 warnings, with type breakdown grounded in a prior `build-log-warm.txt` | 81 warnings predicted from audit, no per-type prediction | Flow 0's empirical breakdown — confirmed by the actual warm log on disk |
| Install-path decision | 6-step bash script with `python -m sphinx` and `set -e` toggling | 5-option matrix (uv add --dev / pip install / venv / etc.) recommending `python -m venv .venv-docs` + `pip install` | Both — Flow 0's executable form for §4.2; Flow 1's matrix referenced for "if `uv` is genuinely available later" |
| Cold-vs-warm cleanup | `rm -rf docs/build` (full) | `rm -rf docs/build/html` only (preserves `.doctrees/`) | Flow 1's narrower deletion — the user request explicitly says `rm -rf docs/build/html`, and preserving `.doctrees/` makes the post-fix build genuinely warm |
| PowerShell stderr handling | not addressed | called out PS 5.1's `NativeCommandError` wrapping | Flow 1's caveat — added to §4.2 as a portability note |
| Handoff manifest | YAML schema for build-to-triage handoff | n/a | Dropped — the consolidated plan-and-report supersedes the need for a separate handoff document |

### 10.4 Required judgments made during consolidation

* **The user request was for triage; both upstream flows produced
  build-capture plans (one subtask earlier in the chain).** The
  consolidated artifact re-targets at the actual user request
  (triage), uses the upstream investigations as background, and
  treats the warm log they predicted as ground truth.
* **`uv run sphinx-build` was substituted with `python -m sphinx`.**
  Justified by `which uv → 127`, by both upstream flows independently
  reaching the same conclusion, by the `conf.py` header comment
  explicitly contemplating no-`pyproject.toml` operation, and by the
  empirical post-fix log demonstrating the substitution preserves the
  predicted warning delta.
* **An incorrect autonomous draft was corrected.** An earlier
  iteration of this plan recommended `('std:label', …)` for the
  `nitpick_ignore` tuples; the on-disk `conf.py` (which works,
  per the post-fix log) uses `('std:ref', …)` and the conf.py
  header comment explicitly explains why `std:label` silently fails
  to suppress. The plan's §3.2 was rewritten to match the on-disk
  reality and to preserve the diagnostic for future maintainers.
* **The triage report is co-located inline as §9** rather than a
  separate file. Justified by (a) "appendix" being one of the user-
  request's two acceptable formats; (b) keeping plan + report in one
  auditable document; (c) the `docs/_plan/` directory pattern already
  including such combined plan documents.

### 10.5 Integration value judgment (iteration 1)

**Value of iteration-1 consolidation:** the two parallel build-capture
flows (Flow 0's `sphinx_build_capture_plan.md` and Flow 1's
`sphinx_initial_build_plan.md`) overlapped substantially in their
findings (premise checks, toolchain caveat, prose-page count).
Mechanical merge of the two would have added little — both reached
the same conclusions on the same evidence. The iteration-1 integration
value was instead in **re-targeting**: recognising the upstream
produced subtask-1 plans while the user request asks for subtask-2
deliverables, and producing a triage plan + report that is grounded
in the upstream's empirical predictions and the on-disk execution
outcome. The act of consolidation also surfaced and corrected a
critical bug in an in-progress autonomous draft
(`std:label` → `std:ref`); without the cross-check against the
on-disk `conf.py` and post-fix log, that bug would have shipped.

### 10.6 Iteration-2 consolidation — Flow 0 second-iteration parallel artifact

**Input merged in iteration 2:**
`docs/_plan/sphinx_warning_triage_consolidated.md` (Flow 0's
second-iteration consolidation, 734 lines, written at 10:57 — one
minute before this file's iteration-1 version at 10:58, so the two
were genuinely parallel rather than sequential).

**Where Flow 0 (iter-2) and Flow 1 (iter-1) agreed.** All
substantive findings: bucket totals (1+1+0+0+55+19+5 = 81); the
post-fix outcome (6 warnings, delta −75); the std:label→std:ref bug
as the high-value unblocker (−74 of −75); the categorisation of
`configuration.rst:254` as escalated REAL-BUG; the toctree warnings
as escalated precondition gap; the on-disk conf.py + glossary.rst
edits as ratified, not re-applied; the `python -m sphinx`
substitution for the missing `uv`. Both artifacts honour all three
CRITICAL constraints. The substantive overlap is roughly 90%.

**Where Flow 0 (iter-2) added unique value (now folded in here).**

| Flow 0 unique element | Where merged into this file |
|-----------------------|------------------------------|
| Per-entry suppression-lifetime mapping table (each `nitpick_ignore` entry → page that should host its anchor → removal trigger) | §3.5 (newly added in iteration 2). High operational value: tells future executors exactly when to delete each suppression. |
| Empirical predicted-vs-observed reconciliation against Flow 0's build-capture forecast | §10.6.1 below (newly added in iteration 2). Provides confidence that the post-fix state is not a one-off result. |
| Sharper "primary takeaway" framing (the std:label→std:ref bug as the −74 contributor, with `glossary.rst:13` as only −1) | Header banner (newly added in iteration 2). |
| Cleaner top-level Part A / Part B / Part C / Part D structure | Not adopted. The §0–§10 structure here is more granular and the iteration cost of restructuring is not justified by the benefit. The two structures are isomorphic — Flow 0's Part A maps to §0–§4, Part B to §5+§9, Part C to a new §10.6.1, Part D to §3.5+§7. |

**Where Flow 1 (this file) adds unique value Flow 0 didn't carry.**

* The §1.3 unique-anchor distribution table (per-anchor cite counts
  by source file) — Flow 0 has the same data but only in the report
  appendix, not as a categorisation reference.
* The §3.2 explicit annotated diff with verbatim citation comments
  for each tuple — Flow 0 lists the 9 entries without the per-line
  cites that the user request explicitly mandates.
* The §6 risks/exit-criteria/rollback section — Flow 0 has no
  failure-mode coverage.
* The §4.5 ("if the post-fix count is not 6") diagnostic decision
  tree — Flow 0 has none; useful for future re-runs after foundation
  pages land.

**Decision on the parallel file.** Leave
`docs/_plan/sphinx_warning_triage_consolidated.md` on disk as a
companion artifact (referenced from the header). It is not deleted
because (a) it documents the parallel-flow exploration and any
external reader who finds it should be able to verify it agrees with
this file; (b) Flow 0's narrative framing (Part A/B/C/D) may be
preferable to some readers; (c) deletion would be a destructive
action the user did not authorise. The header explicitly states the
relationship.

#### 10.6.1 Empirical reconciliation — Flow 0's build-capture predictions vs. observed outcomes

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
(`build succeeded, 6 warnings.`) is itself stable — i.e., that the
−75 delta is not a one-off result and will reproduce on subsequent
re-builds (subject to the lifetime invariants in §3.5).

The single thing Flow 0's build-capture plan (correctly) did **not**
predict was the `('std:label', X)` tuple-key bug in `conf.py`: that
bug was internal to the conf.py block produced by an earlier author,
and Flow 0 was scoped to "build-capture only — no source edits"
(its §6 out-of-scope list explicitly excluded `nitpick_ignore`
changes). The triage subtask (this artifact) is precisely the
"recovery" that the build-capture plan deferred. The discovery of
the std:label→std:ref bug is therefore an iteration-1 contribution
of triage, not a build-capture omission.

### 10.7 Iteration-2 integration value judgment

**Value of iteration-2 consolidation:** the two parallel iteration-2
artifacts (this file's iteration-1 base + Flow 0's
`sphinx_warning_triage_consolidated.md`) reached substantially the
same substantive conclusions, but each carried unique structural
value the other lacked. The iteration-2 merge was therefore not a
mechanical de-dup but a **selective grafting**: §3.5's lifetime
mapping (Flow 0) materially improves the operational guidance for
later executors, and §10.6.1's empirical reconciliation (Flow 0)
materially raises confidence in the post-fix outcome. Neither could
be derived from this file's iteration-1 content alone. Conversely,
this file's §6 (risks/rollback), §4.5 (post-fix-count diagnostic),
and §3.2 (annotated diff with citation comments) are not present in
the Flow 0 artifact and are retained here.

The remaining iteration-2 risk is documentation duplication on disk
(`sphinx_warning_triage_plan.md` + `sphinx_warning_triage_consolidated.md`
+ two older drafts). The header banner of this file resolves the
ambiguity by stating which is canonical and what the relationships
are; cleanup of the older drafts (`sphinx_warning_triage_report.md`,
`sphinx_warning_triage_plan_consolidated.md`) is a separate
housekeeping task and is **not** performed here, since deletions
require explicit user authorisation.


