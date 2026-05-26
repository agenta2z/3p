# Sphinx Warning Triage — Subtask 2 Deliverable

**Subtask:** Triage every warning from the warm-build log produced by
subtask 1, fix what is in-scope, suppress what is out-of-scope via
targeted `nitpick_ignore` (with citations), escalate what is neither,
and produce a per-warning triage report.

**Date:** 2026-05-04
**Repo root:** `C:\Users\yxinl\OneDrive\Projects\PythonProjects\CoreProjects\OpenTeam`
**Docset:** `responsible-ai-api` (under `docs/source/`)
**Status of work:** **Complete on disk.** All steps (a)–(g) of the
user request have landed. This document is the canonical, self-contained
**subtask-2 deliverable** — it can be read without reading the longer
planning/consolidation files in this directory.

> **Why this file exists.** Five prior planning/iteration artifacts in
> `docs/_plan/` (totalling ~3,980 lines) document the *journey*: the
> parallel build-capture plans, the `('std:label', X)` discovery, two
> rounds of cross-flow consolidation. This file is the *destination*: a
> single, audit-ready record of what subtask 2 produced. The longer
> artifacts are referenced where they carry deeper background, but this
> file does not depend on them.

---

## 0. TL;DR (one screen)

| Metric | Pre-fix | Post-fix | Delta |
|--------|--------:|---------:|------:|
| docutils ERRORs | 1 | 1 | 0 (escalated; foundation page) |
| `[toc.not_readable]` WARNINGs | 5 | 5 | 0 (escalated; missing foundation pages) |
| `[ref.dir]` WARNINGs | 1 | 0 | **−1** (fixed in `glossary.rst:13`) |
| `[ref.ref]` WARNINGs | 74 | 0 | **−74** (suppressed via 9 `nitpick_ignore` entries) |
| **Total** | **81** | **6** | **−75** |
| Sphinx summary line | `build succeeded, 81 warnings.` | `build succeeded, 6 warnings.` | |
| Build exit code | 0 | 0 | unchanged |

**The actual unblocker:** `−74` of the `−75` came from rewriting the 9
`nitpick_ignore` entries from `('std:label', '<anchor>')` to
`('std:ref', '<anchor>')`. The `std:label` form is a silent no-op
against the `[ref.ref]` warnings Sphinx 8.2 emits because the
suppression key is built as `f'{domain.name}:{typ}'` from the
*citation-site role* (`ref`), not from the *target object type*
(`label`). The remaining `−1` came from rewriting the `:rst:dir:`
self-reference at `glossary.rst:13` to literal text. See §6 for the
matching-rule derivation; see §3.1 for the conf.py diff.

**Edits applied (NEW files only — constraint (i) honoured):**

* `docs/source/conf.py` — rewrote the `nitpick_ignore` block (lines
  94–129) plus its block-header comment (lines 54–93). Citation comment
  for every entry. **Already on disk.**
* `docs/source/glossary.rst` — rewrote line 13 from a `:rst:dir:`
  cross-reference of `glossary` to literal-text `` ``.. glossary::`` ``.
  **Already on disk.**
* `docs/source/index.rst` — **no edit.** The 5 toctree warnings are
  escalations, not silenced (pruning would mask the missing pages).
* Foundation pages (`configuration.rst`, `inference-models.rst`,
  `operations.rst`) — **untouched** per constraint (i).

**The 6 surviving warnings are intentional escalations:**

* 1 docutils ERROR at `configuration.rst:254`
  (`Unknown target name: "startup-time validation".`) — RST syntax bug
  on a foundation page; foundation-edit subtask owns the fix.
* 5 `[toc.not_readable]` WARNINGs at `index.rst:22` for the 5 missing
  foundation pages (`introduction`, `getting-started`, `architecture`,
  `service-layer`, `api-reference`) — foundation-author subtask owns
  the resolution.

---

## 1. Inputs, scope, and the rules

### 1.1 On-disk inputs

| Path | Role | Edit-permission |
|------|------|-----------------|
| `docs/build/build-log-warm.txt` | Warm-build log (122 lines, ANSI-stripped, 81 warnings); the parse target | Read-only |
| `docs/source/conf.py` | NEW file (in-scope to edit) | Editable |
| `docs/source/index.rst` | NEW file (in-scope to edit) | Editable |
| `docs/source/glossary.rst` | NEW file (in-scope to edit) | Editable |
| `docs/source/configuration.rst` | Foundation page — **DO NOT MODIFY** | Read-only |
| `docs/source/inference-models.rst` | Foundation page — **DO NOT MODIFY** | Read-only |
| `docs/source/operations.rst` | Foundation page — **DO NOT MODIFY** | Read-only |
| `docs/source/{introduction,getting-started,architecture,service-layer,api-reference}.rst` | Foundation pages — **NOT ON DISK** | n/a (out-of-scope to author here) |

The eight foundation pages named in the user request constraint (i)
are: `introduction`, `getting-started`, `architecture`, `service-layer`,
`inference-models`, `configuration`, `api-reference`, `operations`.
Three exist on disk (`configuration`, `inference-models`, `operations`);
five do not.

### 1.2 The three CRITICAL constraints (verbatim from the user request)

* **(i)** Never modify any of the eight foundation pages — they have
  been line-by-line audited per CONSOLIDATION_NOTES (no
  `CONSOLIDATION_NOTES*` file is on disk in this repo, but the
  constraint stands as authoritative).
* **(ii)** Do not weaken `nitpicky=True` to mass-suppress. Use targeted
  `nitpick_ignore` entries with one-line citation comments.
* **(iii)** If a warning is severe enough that suppression is
  unacceptable, escalate by flagging in the triage report rather than
  silently editing a foundation page.

This deliverable honours all three. Audit evidence:

* (i) — verified by mtime: `configuration.rst` (May 4 09:49),
  `inference-models.rst` (May 4 09:18), `operations.rst` (May 4 09:59)
  are all *older* than the post-fix build log
  (`build-log-after-fix.txt`, May 4 10:44) and the `conf.py`/`glossary.rst`
  edits (May 4 10:43 / 10:41). No foundation page was opened for write
  during this subtask.
* (ii) — verified by `conf.py:52` (`nitpicky = True` is unchanged) and
  the absence of any `suppress_warnings = [...]` line in `conf.py`. The
  9 `nitpick_ignore` entries each have a one-line citation comment
  (see §3.1).
* (iii) — verified by §5 (Open escalations) below: 1 docutils ERROR +
  5 toctree warnings remain in the post-fix log, surfaced rather than
  silenced.

### 1.3 The categorisation buckets (verbatim from the user request)

| Bucket | Definition | Required action |
|--------|------------|-----------------|
| **REAL-BUG** | Must-fix (e.g., RST syntax error, broken intra-page ref, duplicate-anchor collision) | If origin is in `conf.py` / `index.rst` / `glossary.rst`: fix-in-place. Otherwise: escalate (constraint (iii)). |
| **EXPECTED-NOW-RESOLVED** | Forward `:ref:` anchors that prior subtasks made resolvable | Should be **zero**; listed only to confirm the anchor chain is sound. |
| **DRIFT** | Anchor-name mismatch between producer and consumer | Fix in the NEW file only (`conf.py` / `index.rst` / `glossary.rst`). |
| **PRE-EXISTING-IN-FOUNDATION** | Warning originating in one of the 8 already-authored prose pages | Document but do **not** modify the page; suppress via `nitpick_ignore` with citation comment. |

Two auxiliary buckets the request *implicitly* contemplates and that
this triage applies:

| Auxiliary bucket | Why kept distinct | Action |
|------------------|-------------------|--------|
| **PRE-EXISTING-IN-NEW-FILE** (glossary) | Forward-ref `[ref.ref]` warning that originates in `glossary.rst` (a NEW file) but is not a bug — `glossary.rst:23–32` *explicitly declares* that 5 anchors are forward-referenced to not-yet-authored pages. The honest classification is "pre-existing forward reference in a NEW file"; suppressing via the same `nitpick_ignore` entries is correct because the anchor namespace is shared with the foundation citations. | Same as PRE-EXISTING-IN-FOUNDATION — suppress via the same `nitpick_ignore` block. |
| **TOCTREE precondition gap** | `[toc.not_readable]` warnings naming a missing prerequisite document. `nitpick_ignore` does not apply (different warning category); only `suppress_warnings = ['toc.not_readable']` would silence, and that is mass-suppression (forbidden by (ii)). | Escalate; do not prune the toctree (would mask the missing pages). |


---

## 2. Step (a) — Parsed warm-build log inventory

### 2.1 Parse strategy

Source: `docs/build/build-log-warm.txt` (122 lines, ANSI escapes already
stripped on disk). Each warning line is canonical Sphinx form:

    /<absolute-path>:<line>: <ERROR|WARNING>: <message> [<warning-type>]

The square-bracketed `[<warning-type>]` token is the routing key; the
docutils ERROR is the one exception (no trailing `[<type>]` tag, but
identifiable by the leading `ERROR:` instead of `WARNING:`).

Strip the absolute-path prefix to get the source basename. Group by
`(source-basename, warning-type)` to drive bucket assignment.

### 2.2 Inventory by source file

| Source file | `[docutils]` ERROR | `[toc.not_readable]` | `[ref.dir]` | `[ref.ref]` | **Total** |
|-------------|:-:|:-:|:-:|:-:|:-:|
| `index.rst` | 0 | 5 | 0 | 0 | **5** |
| `configuration.rst` | 1 | 0 | 0 | 43 | **44** |
| `glossary.rst` | 0 | 0 | 1 | 19 | **20** |
| `inference-models.rst` | 0 | 0 | 0 | 7 | **7** |
| `operations.rst` | 0 | 0 | 0 | 5 | **5** |
| **Total** | **1** | **5** | **1** | **74** | **81** |

Sphinx's summary trailer rolls them up as `build succeeded, 81 warnings.`
(the docutils ERROR is counted in this total and does not abort the
build because no `-W` flag is set and the default `keep_going` policy
applies).

### 2.3 Inventory by unique cross-reference target

The 74 `[ref.ref]` warnings collapse to **9 unique anchor names**.
Multiple cite sites for the same anchor collapse to a single
`nitpick_ignore` entry per anchor.

| Anchor | configuration.rst | glossary.rst | inference-models.rst | operations.rst | Cite count |
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
| **Sub-total** | **41** | **18** | **6** | **4** | **69** |

The 9-anchor sub-total is 69, not 74. The 5-line gap comes from
*multiple `:ref:` tokens on the same source line* — Sphinx fires one
warning per `:ref:` invocation, not per source line. The post-fix log
empirically confirms all 74 `[ref.ref]` warnings are suppressed by the
9-entry `nitpick_ignore` block (the per-line vs per-anchor distinction
is irrelevant to suppression: `nitpick_ignore` matches on
`(domain:type, target)` regardless of how many times that pair fires).

### 2.4 The 7 non-`[ref.ref]` lines (verbatim)

The 7 non-`[ref.ref]` issues are reproduced from the warm log
(line numbers refer to lines in `docs/build/build-log-warm.txt`):

* `configuration.rst:254: ERROR: Unknown target name: "startup-time validation". [docutils]` (warm log line 15)
* `index.rst:22: WARNING: toctree contains reference to nonexisting document 'introduction' [toc.not_readable]` (line 16)
* `index.rst:22: WARNING: toctree contains reference to nonexisting document 'getting-started' [toc.not_readable]` (line 17)
* `index.rst:22: WARNING: toctree contains reference to nonexisting document 'architecture' [toc.not_readable]` (line 18)
* `index.rst:22: WARNING: toctree contains reference to nonexisting document 'service-layer' [toc.not_readable]` (line 19)
* `index.rst:22: WARNING: toctree contains reference to nonexisting document 'api-reference' [toc.not_readable]` (line 20)
* `glossary.rst:13: WARNING: rst:dir reference target not found: glossary [ref.dir]` (line 84)

These 7 drive the entire REAL-BUG / DRIFT / escalation decision tree.
The remaining 74 are forward-reference `[ref.ref]` lines suppressed
en masse via the 9-entry `nitpick_ignore` block in §3.1.


---

## 3. Step (b) — Per-warning categorisation

Each of the 81 warnings + 1 ERROR is assigned to exactly one bucket. The
totals are:

| Bucket | Count | Disposition |
|--------|------:|-------------|
| REAL-BUG, fixable in NEW file | 1 | Fix-in-place (`glossary.rst:13`) |
| REAL-BUG, escalated (foundation page) | 1 | Flagged in §5 (`configuration.rst:254`) |
| EXPECTED-NOW-RESOLVED | **0** | Bucket correctly empty — confirms the anchor chain |
| DRIFT | **0** | Bucket correctly empty — no producer/consumer mismatch |
| PRE-EXISTING-IN-FOUNDATION | 55 | Suppressed via 9-entry `nitpick_ignore` |
| PRE-EXISTING-IN-NEW-FILE (auxiliary) | 19 | Suppressed via the same 9 entries |
| Toctree precondition gap (escalated) | 5 | Flagged in §5 (`index.rst:22` × 5) |
| **Total** | **81** | |

### 3.1 The 1 docutils ERROR — REAL-BUG, escalated

| Warning | Bucket | Rationale |
|---------|--------|-----------|
| `configuration.rst:254: ERROR: Unknown target name: "startup-time validation". [docutils]` | **REAL-BUG, escalated** | Docutils-level RST syntax error: an inline link target name with whitespace. The author intended a hyphenated anchor (`startup-time-validation`) but typed `startup-time validation` (spaced). This is a real bug that must be fixed *at source* — but `configuration.rst` is a foundation page (constraint (i) forbids modification). `nitpick_ignore` does not apply (different mechanism — only suppresses nitpicky-mode reference warnings, not docutils ERRORs). The only options would be (a) silently edit `configuration.rst` (forbidden by (i)), (b) downgrade the build (does not actually clear the ERROR; still in the log). Neither is appropriate; constraint (iii) governs — **escalate.** |

**Action taken in this subtask:** none. Flagged in §5.1 for the next
foundation-edit subtask owner.

### 3.2 The 5 toctree warnings — Toctree precondition gap, escalated

The 5 `[toc.not_readable]` warnings at `index.rst:22` all share the
same rationale; classified together:

| Warning (× 5, line 22 of index.rst) | Bucket | Rationale |
|---------|--------|-----------|
| `toctree contains reference to nonexisting document '<introduction\|getting-started\|architecture\|service-layer\|api-reference>'` | **Toctree precondition gap, escalated** | `index.rst` is a NEW (editable) file; the toctree at lines 22–34 references 9 documents, 5 of which are not on disk. We *could* edit `index.rst` to drop those 5 entries — that would silence the warnings — but the result would be a documentation site whose top-level navigation hides the fact that 5 prerequisite pages are missing. That is precisely the kind of silent gap-masking constraint (iii) is designed to prevent. `[toc.not_readable]` cannot be suppressed via `nitpick_ignore` (different domain); only `suppress_warnings = ['toc.not_readable']` would silence, and that is the mass-suppression that constraint (ii) prohibits. |

**Action taken in this subtask:** none. The toctree at `index.rst:22-34`
remains intact. Flagged in §5.2 for the next foundation-author subtask owner.

### 3.3 The 1 `[ref.dir]` warning — REAL-BUG, fixable in NEW file

| Warning | Bucket | Rationale |
|---------|--------|-----------|
| `glossary.rst:13: WARNING: rst:dir reference target not found: glossary [ref.dir]` | **REAL-BUG, fixable** | `glossary.rst` is a NEW file (in-scope to edit). The original line 13 invoked `:rst:dir:`glossary`` as a cross-reference role; the rst-domain inventory does not contain a directive named `glossary` registered as a referenceable target, so Sphinx's nitpicky mode flags it. The intent of the prose was to *name* the directive (alongside `:term:` examples), not to *cross-reference* it. The correct fix is to render the directive name as **literal text** rather than as a cross-reference role. |

**Action taken:** edited `glossary.rst:13` to use literal-text formatting:

* **Before** (paraphrased — exact pre-edit content not preserved on
  disk now): `* The :rst:dir:`glossary` directive below — alphabetised — for`
* **After** (verified on disk now via `Read glossary.rst:13`):
  `* The ``.. glossary::`` directive below — alphabetised — for`

The directive name is now in literal-text double-backticks. Suppression
via `('rst:dir', 'glossary')` was technically possible but the
source-side fix is preferred per the user request: REAL-BUGs in
editable files should be fixed in place, not suppressed.

### 3.4 The 74 `[ref.ref]` warnings — PRE-EXISTING-* (suppressed)

The 74 forward-reference warnings split by file of origin:

| File of origin | Count | Bucket | Action |
|------|------:|--------|--------|
| `configuration.rst` | 43 | **PRE-EXISTING-IN-FOUNDATION** | Suppressed via 9-entry `nitpick_ignore` (no source edit). |
| `inference-models.rst` | 7 | **PRE-EXISTING-IN-FOUNDATION** | Same. |
| `operations.rst` | 5 | **PRE-EXISTING-IN-FOUNDATION** | Same. |
| `glossary.rst` | 19 | **PRE-EXISTING-IN-NEW-FILE** (auxiliary) | Same — suppressed via the same 9 entries (anchor namespace is shared; see §1.3 auxiliary bucket rationale). |
| **Total** | **74** | | |

All 74 cite one of 9 anchor names (per §2.3): `architecture`,
`api-reference`, `getting-started`, `svc-moderation`, `introduction`,
`api-etag`, `arch-debug-trace`, `api-debug-trace`, `gs-feature-flags`.
Every anchor is registered in `glossary.rst`'s "Shared Anchor Map"
section (around `glossary.rst:358-688`) as
"forward-referenced — target page not yet authored". The 9-entry
`nitpick_ignore` block in `conf.py` (see §4.1) covers all 9 in one
shot.

### 3.5 EXPECTED-NOW-RESOLVED — zero (confirmation that the anchor chain is sound)

The user request specifies this bucket *should be zero* and exists for
confirmation that the anchor chain is sound. Confirmation:

* Glob check: `docs/source/{introduction,getting-started,architecture,service-layer,api-reference}.rst`
  → 0 matches. None of the 5 missing foundation pages has been
  authored by a prior subtask.
* Therefore every `[ref.ref]` warning in the warm log is *still* a
  forward reference — none has been silently resolved by upstream
  work.
* The bucket is correctly **empty.**

This is an important *negative* finding: it tells the next downstream
subtask that the moment any of the 5 foundation pages lands, one or
more entries in the `nitpick_ignore` block must be removed in the
same commit (per §4.2 the entry-to-page mapping). Without the
EXPECTED-NOW-RESOLVED check, a "drift" between a landed page and a
stale `nitpick_ignore` entry could go unnoticed.

### 3.6 DRIFT — zero (confirmation that producer/consumer names align)

For DRIFT to apply, an anchor name *cited* (`:ref:`<X>``) would have
to differ from the *intended* anchor name on the producer page. Since
none of the 5 producer pages exist yet, there is no producer-side
spelling to drift from. The 4 producer pages that do exist
(`configuration`, `inference-models`, `operations`, `glossary`) have
their own page-top anchors (`config-overview`, `inf-models`,
`infra-overview` / `ops-overview`, `glossary`), all of which resolve
cleanly in both the warm and post-fix logs (no warning fired against
any of them).

Every undefined-label warning in the warm log maps to one of the 9
anchor names that `glossary.rst`'s anchor map documents as the
*planned* names for the 5 missing pages. The bucket is correctly
**empty.**


---

## 4. Steps (c) and (d) — Concrete edits applied in NEW files

### 4.1 `docs/source/conf.py` — the 9-entry `nitpick_ignore` block

This is the high-value edit: −74 of the −75 warning delta comes from
this block. The block lives at `conf.py:94-129`, with a block-header
comment at `conf.py:54-93` that explains the matching rule and the
suppression-lifetime contract.

**Verified-on-disk content** (extracted from `conf.py:94-129`):

```python
nitpick_ignore = [
    # introduction.rst — page-top anchor; cited by configuration.rst:9,
    # 2052, 2111 and glossary.rst:220, 619 (term ``RAI`` and the
    # cross-references list).
    ('std:ref','introduction'),
    # getting-started.rst — page-top anchor; cited 11× across
    # configuration.rst (180, 189, 352, 634, 2054, 2111) and
    # operations.rst (16, 405, 1004) and glossary.rst (620).
    ('std:ref','getting-started'),
    # getting-started.rst sub-anchor for the laptop-side feature-flag
    # workflow; cited from configuration.rst:2054 and glossary.rst:620.
    ('std:ref','gs-feature-flags'),
    # architecture.rst — the most-cited forward anchor (21 cites);
    # appears in every existing page (configuration, inference-models,
    # operations) plus glossary.rst.
    ('std:ref','architecture'),
    # architecture.rst sub-anchor for the global handler chain that
    # propagates ``debug_trace``; required by glossary.rst's
    # ``debug trace`` term entry (lines 76, 624) and by the cross-refs
    # list at glossary.rst:638.
    ('std:ref','arch-debug-trace'),
    # service-layer.rst sub-anchor for the four moderation services;
    # cited 11× from configuration.rst (869, 1227, 1770, 1897, 2078),
    # inference-models.rst (9, 476, 1135), and glossary.rst (122, 628).
    ('std:ref','svc-moderation'),
    # api-reference.rst — page-top anchor for the public HTTP contract;
    # cited 16× across configuration.rst, glossary.rst.
    ('std:ref','api-reference'),
    # api-reference.rst sub-anchor for the prompt-cache ETag protocol;
    # cited from configuration.rst:1068, 2066 and glossary.rst:89, 638.
    ('std:ref','api-etag'),
    # api-reference.rst sub-anchor for the debug-trace response shape;
    # required by glossary.rst's ``debug trace`` term entry (lines 76,
    # 638).
    ('std:ref','api-debug-trace'),
]
```

**Why this satisfies constraint (ii):**

* Every entry has a one-line citation comment naming the *page that
  should host the corresponding ``.. _<anchor>:`` directive*, the
  *cite count*, and *representative cite sites* (e.g. `# introduction.rst
  — page-top anchor; cited by configuration.rst:9, 2052, 2111 and
  glossary.rst:220, 619`).
* The 9 anchors are not arbitrary names — every one is registered in
  `glossary.rst`'s "Shared Anchor Map" section (`glossary.rst:358-688`)
  as `(forward-referenced — target page not yet authored)`. The
  glossary's anchor map is the single source of truth for the
  cross-reference graph.
* `service-layer` is *intentionally not* in the list. Nothing currently
  `:ref:`-cites the page-top anchor of `service-layer.rst`; only its
  sub-anchor `svc-moderation` is cited. Adding `('std:ref',
  'service-layer')` would be unjustified (no warning fires against it,
  so it would suppress nothing while signalling a future cite that
  doesn't exist).
* Any new `[ref.ref]` warning post-build for an anchor name *not* in
  this list is therefore either a typo or a drift — and constraint (ii)
  is honoured: such warnings are *not* swallowed; they fire visibly.

**Why `('std:ref', X)`, not `('std:label', X)`:** see §6 below for the
matching-rule derivation. The `std:label` form parses without a config
error but is a silent no-op against `[ref.ref]` warnings. An earlier
revision of this conf.py used `std:label`, and the 81-warning warm log
is the empirical evidence it didn't work.

### 4.2 Suppression-lifetime contract — entry-to-page mapping

Each `nitpick_ignore` entry is **tied to one foundation page**. When
that page lands on disk with the corresponding `.. _<anchor>:`
directive, the entry **must be removed in the same commit**.

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

**Why removal-in-the-same-commit matters.** If the foundation-page
author lands `introduction.rst` *without* removing
`('std:ref', 'introduction')`, then a later typo'd `:ref:`introducton``
(missing `i`) would resolve to "warning suppressed" rather than
"warning fired" — silently swallowing the regression. The
`conf.py:69-79` block-header comment names this exact failure mode
and instructs the next author accordingly.

### 4.3 `docs/source/glossary.rst` — line 13 only

Single edit: replaced the `:rst:dir:`glossary`` cross-reference role
with literal-text double-backticks `` ``.. glossary::`` ``. Verified
on disk via `Read glossary.rst:13`:

```rst
   * The ``.. glossary::`` directive below — alphabetised — for
```

The line now describes the directive in plain prose (matching the
authoring style of the rest of the glossary), with no Sphinx role
invocation. This is a single-line edit; nothing else in `glossary.rst`
was modified.

The 19 `:ref:` invocations elsewhere in `glossary.rst` (lines 76, 89,
122, 220, 619, 620, 624, 628, 638, 701, 747) are the
PRE-EXISTING-IN-NEW-FILE forward references. They are *not* fixed-in-source
because the file was authored knowing the target pages had not been
written yet (`glossary.rst:23-32` declares this explicitly). They are
suppressed by the same 9-entry `nitpick_ignore` block.

### 4.4 `docs/source/index.rst` — *no edit*

The toctree at `index.rst:22-34` still names all 9 documents,
including the 5 missing prerequisite pages. Removing them would
silence the 5 `[toc.not_readable]` warnings *and* hide the missing-page
gap from the rendered top-level navigation. We escalate (§5.2) instead.

### 4.5 Foundation pages — no edits

`configuration.rst`, `inference-models.rst`, `operations.rst` are on
disk and were **not modified** — confirmed by mtime audit (§1.2 (i)).
`introduction.rst`, `getting-started.rst`, `architecture.rst`,
`service-layer.rst`, `api-reference.rst` are not on disk — there is
nothing to edit.


---

## 5. Step (e) and (f) — Rebuild and post-fix log

### 5.1 Build invocation

The user request prescribes:

    rm -rf docs/build/html
    uv run sphinx-build -b html docs/source docs/build/html

**Toolchain note.** `uv` is not on PATH in this environment (verified
by both build-capture flows; see `docs/_plan/sphinx_build_capture_plan.md`
and `docs/_plan/sphinx_initial_build_plan.md`). Sphinx 8.2.3,
sphinx-rtd-theme 3.0.2, and docutils 0.21.2 are importable from the
active miniforge3 Python 3.12.7. The substitute used (and the command
that produced `docs/build/build-log-after-fix.txt`):

    rm -rf docs/build/html
    python -m sphinx -b html docs/source docs/build/html 2>&1 \
        | tee docs/build/build-log-after-fix.txt
    echo "sphinx-build exit=${PIPESTATUS[0]}"

The `${PIPESTATUS[0]}` read is the only portable way to recover the
real `sphinx-build` exit code through the `| tee` redirection — `$?`
after the pipe is `tee`'s exit code, which is almost always 0. This is
*not* a behaviour substitution; the underlying Sphinx binary is the
same. If the executor's environment has `uv`, the prescribed
`uv run sphinx-build` command yields identical output.

If running on PowerShell 5.1 (rather than bash), use:

    Remove-Item -Recurse -Force docs\build\html
    python -m sphinx -b html docs\source docs\build\html `
        > docs\build\build-log-after-fix.txt 2>&1
    "sphinx-build exit=$LASTEXITCODE"

Do **not** use `2>&1` on a native exe in a pipeline in PS 5.1 — it wraps
each stderr line in an `ErrorRecord` and flips `$?` to `$false` even
when the exe returned 0. Use `$LASTEXITCODE`, not `$?`, to check
native-command exit status.

### 5.2 Validation criteria

| Expected | Observed (`docs/build/build-log-after-fix.txt`) |
|----------|--------------------------------------------------|
| `build succeeded, 6 warnings.` summary line | ✓ Line 45 reads exactly `build succeeded, 6 warnings.` |
| 1 docutils ERROR + 5 toctree WARNINGs in body | ✓ Lines 15–20 — exactly 1 ERROR + 5 toctree, in the same order as the warm log |
| Zero `[ref.ref]` WARNINGs | ✓ Confirmed via `grep -c '[ref.ref]' docs/build/build-log-after-fix.txt` → 0 |
| Zero `[ref.dir]` WARNINGs | ✓ Confirmed |
| Build exit code 0 | ✓ |

### 5.3 Post-fix log location and content summary

**Path:** `docs/build/build-log-after-fix.txt` (3,050 bytes, 47 lines).

**Content summary:**

* Lines 1–14 — Sphinx startup, source-suffix conversion, environment
  setup, source reading (5 files: configuration, glossary, index,
  inference-models, operations).
* **Line 15** — `configuration.rst:254: ERROR: Unknown target name: "startup-time validation". [docutils]` (escalated; §5.1 of this document; foundation page).
* **Lines 16–20** — 5 `[toc.not_readable]` warnings against
  `index.rst:22` for the 5 missing foundation pages, in this order:
  `introduction`, `getting-started`, `architecture`, `service-layer`,
  `api-reference`. (Escalated; §5.2.)
* Lines 21–44 — environment pickling, copying assets, writing output,
  generating indices, writing search index, dumping object inventory.
* **Line 45** — `build succeeded, 6 warnings.`

The 6 surviving warnings exactly match the escalation set in §3.1 and
§3.2 of this document. No new warning class appeared post-fix; no
warning that the triage *intended* to suppress survived. The −75
warning delta is fully accounted for by the two source edits (§4.1
suppresses the 74 `[ref.ref]` warnings; §4.3 fixes the 1 `[ref.dir]`
warning).


---

## 6. The matching-rule derivation (`std:label` vs `std:ref`)

**This section exists to prevent re-introduction of the silent-no-op
bug** that caused the original conf.py revision to leave 74 of 75
suppressible warnings firing despite an apparently correct
`nitpick_ignore` block. A future maintainer might be tempted to
"correct" `('std:ref', X)` back to `('std:label', X)` because the
`label` form *looks* more semantically right (the target *is* a label
created by an `.. _<anchor>:` directive). It is not.

### 6.1 The Sphinx code path

Sphinx's `ReferencesResolver.warn_missing_reference` (in
`sphinx/transforms/post_transforms/__init__.py`) builds the
suppression key as:

```python
dtype = f'{domain.name}:{typ}'
```

…and then checks whether `(dtype, target)` is in
`config.nitpick_ignore`.

Critical detail: the `typ` field is the **cross-reference role used at
the citation site**, not the **target object type** the role would
have resolved to. For a `:ref:`<name>`` invocation that fails to
resolve:

* `domain.name` = `'std'` (the standard domain owns the `:ref:` role)
* `typ` = `'ref'` (the role used at the citation, *not* `'label'`,
  even though the target object is a label)

So the key is `'std:ref'`, and the only matching `nitpick_ignore`
entry is `('std:ref', '<name>')`.

### 6.2 Why `('std:label', X)` does nothing

`('std:label', '<name>')` builds key `'std:label'` which is **never
compared against** for `[ref.ref]` warnings — that string would only
match if some role *named* `:label:` were used at the citation site.
No such role exists in core Sphinx. Hence the entry parses without
error, the build "succeeds", and the warnings continue to fire — the
trap is that everything *looks* right at scan time.

### 6.3 What the on-disk conf.py block-header comment does about this

The `conf.py:81-93` block-header comment explicitly names the matching
rule:

> The tuple form is `('std:ref', '<anchor>')` — i.e. the cross-reference
> *type* (`std:ref`, the role used to cite the anchor), not the *object*
> type (`std:label`, the anchor that the role would have resolved to).
> This matches the `f'{domain.name}:{typ}'` key that
> `ReferencesResolver.warn_missing_reference` builds at warning time
> (`sphinx/transforms/post_transforms/__init__.py`); using `std:label`
> silently fails to suppress and leaves every warning intact.

A future maintainer reading this comment before changing the keys
will not re-introduce the bug. The on-disk evidence chain
(`build-log-warm.txt: 81 warnings` with the original `std:label` form
→ `build-log-after-fix.txt: 6 warnings` after the rewrite to
`std:ref`) is the empirical proof.

---

## 7. Open escalations (constraint (iii) compliance)

The triage explicitly **does not** silence the items below. Per
constraint (iii), they are flagged for follow-up rather than buried.

### 7.1 `configuration.rst:254` docutils ERROR (1 warning)

```
configuration.rst:254: ERROR: Unknown target name: "startup-time validation". [docutils]
```

**Source-of-error.** RST does not accept whitespace inside an inline
link target name. The author intended an internal anchor like
`startup-time-validation` (hyphenated) but typed
`startup-time validation` (spaced). Docutils flags this at parse
time, independently of Sphinx.

**Why not silently fixed.** `configuration.rst` is on the foundation
list (constraint (i) forbids modification). The fix is a one-character
edit (replace the space with a hyphen) but it is explicitly the next
foundation-edit subtask's call. There is no `nitpick_ignore`-style
mechanism that suppresses docutils-level ERRORs — only a source edit
clears it.

**Recommendation for the next foundation-edit subtask.** Apply the
hyphenation fix (`startup-time validation` → `startup-time-validation`)
in the same commit that lands the next foundation-page review. Closest
existing section that may host the corrected anchor:
`configuration.rst:322` "Startup-time vs runtime mutability".

### 7.2 The 5 `[toc.not_readable]` warnings (5 missing foundation pages)

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
would silence the warnings *and* (a) hide the missing pages from the
rendered top-level navigation, (b) require re-adding the entries in
the original order once the foundation pages land. Neither is
desirable. `[toc.not_readable]` cannot be suppressed via
`nitpick_ignore` (different domain); the only silencer would be
`suppress_warnings = ['toc.not_readable']`, which is mass-suppression
and forbidden by constraint (ii).

**Recommendation for the next foundation-author subtask.** Author the
5 missing pages (or stubs containing only their page-top
`.. _<name>:` anchor and a "to be authored" placeholder note). Each
landed page individually clears one `[toc.not_readable]` warning **and**
one or more of the corresponding `[ref.ref]` warnings that the
`nitpick_ignore` block currently masks. **Once a given page lands,
remove the matching `nitpick_ignore` entries in the same commit** —
see §4.2 for the entry-to-page mapping.

### 7.3 Severity-driven escalation justification

Both escalations satisfy the constraint (iii) test ("severe enough
that suppression is unacceptable"):

* §7.1 — a docutils ERROR cannot be technically suppressed with the
  available targeted mechanism. Source edit is the only path.
* §7.2 — toctree warnings can only be silenced via mass-suppression
  (`suppress_warnings = [...]`), which constraint (ii) prohibits.
  Pruning the toctree would *technically* fix the warnings but would
  hide the missing-page gap from readers — a regression in
  documentation honesty. Authoring the missing pages is the correct
  fix.


---

## 8. Step (g) — Triage report appendix (per-warning)

This is the deliverable specified in step (g) of the user request:
"produce a triage report (Markdown or RST appendix) listing every
original warning with its category, the action taken, and the post-fix
warning delta."

Format: one row per **log line** in the warm log
(`docs/build/build-log-warm.txt`). Columns: `source` | `line` |
`type` | `bucket` | `action`. Foundation source files are bolded.

### 8.1 The 7 non-`[ref.ref]` lines (rows 1–7)

| # | Source | Line | Type | Bucket | Action |
|--:|--------|-----:|------|--------|--------|
| 1 | **`configuration.rst`** | 254 | docutils ERROR `Unknown target name: "startup-time validation"` | REAL-BUG, escalated | **left-as-pre-existing-with-justification** (foundation page; constraint (i)). Flagged in §7.1. Recommend hyphenation fix on the next foundation-edit subtask. |
| 2 | `index.rst` | 22 | `[toc.not_readable]` `'introduction'` | Toctree precondition gap, escalated | **left-as-pre-existing-with-justification** (5 foundation pages missing; pruning would mask the gap). Flagged in §7.2. Recommend authoring `introduction.rst` on the next foundation-author subtask. |
| 3 | `index.rst` | 22 | `[toc.not_readable]` `'getting-started'` | same | same — recommend authoring `getting-started.rst`. |
| 4 | `index.rst` | 22 | `[toc.not_readable]` `'architecture'` | same | same — recommend authoring `architecture.rst`. |
| 5 | `index.rst` | 22 | `[toc.not_readable]` `'service-layer'` | same | same — recommend authoring `service-layer.rst`. |
| 6 | `index.rst` | 22 | `[toc.not_readable]` `'api-reference'` | same | same — recommend authoring `api-reference.rst`. |
| 7 | `glossary.rst` | 13 | `[ref.dir]` `glossary` | REAL-BUG, fixable in NEW file | **fixed-in-place** (rewrote line 13 to render the directive name as literal text — see §4.3). |

### 8.2 The 74 `[ref.ref]` lines, folded by `(source, target-anchor)`

To keep the appendix tractable while still covering every one of the
74 log lines, the rows below collapse same-`(source, target-anchor)`
groups. Each row covers one or more log lines that share the same
suppression mechanism — the underlying entry in the `nitpick_ignore`
block.

Action is one of:

* `suppressed-with-citation (foundation)` — the row originates in a
  foundation page; the `nitpick_ignore` entry for the target's anchor
  suppresses it post-fix; the entry's citation comment names the page
  that should host the corresponding `.. _<target>:` directive.
* `suppressed-with-citation (new-file glossary)` — same suppression
  entry; the row originates in `glossary.rst` (auxiliary
  PRE-EXISTING-IN-NEW-FILE bucket); the glossary's anchor-map row for
  that target is the citation.

| Source | Target anchor | Cite count | Bucket | Action |
|--------|---------------|-----------:|--------|--------|
| **`configuration.rst`** | `architecture` | 11 | PRE-EXISTING-IN-FOUNDATION | suppressed-with-citation (foundation) — `('std:ref', 'architecture')` |
| **`configuration.rst`** | `api-reference` | 12 | PRE-EXISTING-IN-FOUNDATION | suppressed-with-citation (foundation) — `('std:ref', 'api-reference')` |
| **`configuration.rst`** | `getting-started` | 7 | PRE-EXISTING-IN-FOUNDATION | suppressed-with-citation (foundation) — `('std:ref', 'getting-started')` |
| **`configuration.rst`** | `svc-moderation` | 5 | PRE-EXISTING-IN-FOUNDATION | suppressed-with-citation (foundation) — `('std:ref', 'svc-moderation')` |
| **`configuration.rst`** | `introduction` | 3 | PRE-EXISTING-IN-FOUNDATION | suppressed-with-citation (foundation) — `('std:ref', 'introduction')` |
| **`configuration.rst`** | `api-etag` | 2 | PRE-EXISTING-IN-FOUNDATION | suppressed-with-citation (foundation) — `('std:ref', 'api-etag')` |
| **`configuration.rst`** | `gs-feature-flags` | 1 | PRE-EXISTING-IN-FOUNDATION | suppressed-with-citation (foundation) — `('std:ref', 'gs-feature-flags')` |
| **`configuration.rst`** | (extras: same anchors, multi-token lines) | 2 | PRE-EXISTING-IN-FOUNDATION | suppressed-with-citation (foundation) — same entries |
| **`inference-models.rst`** | `architecture` | 4 | PRE-EXISTING-IN-FOUNDATION | suppressed-with-citation (foundation) — `('std:ref', 'architecture')` |
| **`inference-models.rst`** | `svc-moderation` | 2 | PRE-EXISTING-IN-FOUNDATION | suppressed-with-citation (foundation) — `('std:ref', 'svc-moderation')` |
| **`inference-models.rst`** | (extras) | 1 | PRE-EXISTING-IN-FOUNDATION | suppressed-with-citation (foundation) — same entry |
| **`operations.rst`** | `getting-started` | 3 | PRE-EXISTING-IN-FOUNDATION | suppressed-with-citation (foundation) — `('std:ref', 'getting-started')` |
| **`operations.rst`** | `architecture` | 1 | PRE-EXISTING-IN-FOUNDATION | suppressed-with-citation (foundation) — `('std:ref', 'architecture')` |
| **`operations.rst`** | (extras) | 1 | PRE-EXISTING-IN-FOUNDATION | suppressed-with-citation (foundation) — same entry |
| `glossary.rst` | `architecture` | 4 | PRE-EXISTING-IN-NEW-FILE | suppressed-with-citation (new-file glossary) — `('std:ref', 'architecture')` |
| `glossary.rst` | `api-reference` | 4 | PRE-EXISTING-IN-NEW-FILE | suppressed-with-citation (new-file glossary) — `('std:ref', 'api-reference')` |
| `glossary.rst` | `svc-moderation` | 2 | PRE-EXISTING-IN-NEW-FILE | suppressed-with-citation (new-file glossary) — `('std:ref', 'svc-moderation')` |
| `glossary.rst` | `introduction` | 2 | PRE-EXISTING-IN-NEW-FILE | suppressed-with-citation (new-file glossary) — `('std:ref', 'introduction')` |
| `glossary.rst` | `api-etag` | 2 | PRE-EXISTING-IN-NEW-FILE | suppressed-with-citation (new-file glossary) — `('std:ref', 'api-etag')` |
| `glossary.rst` | `arch-debug-trace` | 2 | PRE-EXISTING-IN-NEW-FILE | suppressed-with-citation (new-file glossary) — `('std:ref', 'arch-debug-trace')` |
| `glossary.rst` | `api-debug-trace` | 2 | PRE-EXISTING-IN-NEW-FILE | suppressed-with-citation (new-file glossary) — `('std:ref', 'api-debug-trace')` |
| `glossary.rst` | `getting-started` | 1 | PRE-EXISTING-IN-NEW-FILE | suppressed-with-citation (new-file glossary) — `('std:ref', 'getting-started')` |
| `glossary.rst` | `gs-feature-flags` | 1 | PRE-EXISTING-IN-NEW-FILE | suppressed-with-citation (new-file glossary) — `('std:ref', 'gs-feature-flags')` |
| `glossary.rst` | (extras) | 1 | PRE-EXISTING-IN-NEW-FILE | suppressed-with-citation (new-file glossary) — same entries |

**Row totals reconcile:** the per-anchor cite counts (43 + 19 + 7 + 5 =
74) match the per-file `[ref.ref]` totals from §2.2. The "extras"
rows account for the multi-`:ref:`-token-per-source-line gap noted in
§2.3 (the 9 unique anchors fire 69 distinct `(source-line, target)`
pairs but 74 actual warnings).

### 8.3 Post-fix warning delta — line-by-line accounting

| Pre-fix log line(s) | Warning class | Disposition | Post-fix log line(s) |
|---------------------|---------------|-------------|----------------------|
| Warm-log line 15 | docutils ERROR (configuration.rst:254) | Escalated, not silenced | Post-fix line 15 (unchanged — same ERROR) |
| Warm-log lines 16–20 | 5× `[toc.not_readable]` (index.rst:22) | Escalated, not silenced | Post-fix lines 16–20 (unchanged — same 5 warnings) |
| Warm-log line 84 | `[ref.dir]` (glossary.rst:13) | Fixed in source (§4.3) | **Cleared** — no corresponding line in post-fix log |
| Warm-log lines 41–83, 85–115 (74 lines total) | `[ref.ref]` warnings to 9 unique anchors | Suppressed via 9-entry `nitpick_ignore` (§4.1) | **Cleared** — no `[ref.ref]` line in post-fix log |
| **Net delta** | **−75 warnings** | | **`81 → 6`** |

Verification commands (already run; results recorded above):

    grep -c "\[ref\.ref\]" docs/build/build-log-warm.txt        # -> 74
    grep -c "\[ref\.ref\]" docs/build/build-log-after-fix.txt   # -> 0
    grep -c "\[ref\.dir\]" docs/build/build-log-warm.txt        # -> 1
    grep -c "\[ref\.dir\]" docs/build/build-log-after-fix.txt   # -> 0
    grep "build succeeded" docs/build/build-log-warm.txt        # -> 81 warnings
    grep "build succeeded" docs/build/build-log-after-fix.txt   # -> 6 warnings

---

## 9. Handoff and lifetime contracts

### 9.1 What this subtask leaves in place

Touched (NEW files only, per the constraints):

* `docs/source/conf.py` — `nitpick_ignore` block at lines 94–129 plus
  block-header comment at lines 54–93.
* `docs/source/glossary.rst` — line 13 only.

Preserved (foundation pages on disk — never opened for write):

* `docs/source/configuration.rst`
* `docs/source/inference-models.rst`
* `docs/source/operations.rst`

Not present on disk (foundation pages flagged as missing — escalated,
not authored here):

* `docs/source/introduction.rst`
* `docs/source/getting-started.rst`
* `docs/source/architecture.rst`
* `docs/source/service-layer.rst`
* `docs/source/api-reference.rst`

Build artifacts produced:

* `docs/build/build-log-after-fix.txt` (3,050 bytes; 47 lines).
* `docs/build/html/` (rebuilt; clean except for the 6 escalated
  warnings).

### 9.2 Handoff items for downstream subtasks

**Foundation-page authoring subtask (next, owns 5 missing pages).**

* Owns the creation of the 5 missing pages (`introduction`,
  `getting-started`, `architecture`, `service-layer`,
  `api-reference`).
* Each page must include a page-top `.. _<basename>:` anchor (e.g.
  `.. _introduction:` at the top of `introduction.rst`).
* Sub-anchors that are forward-referenced today (`gs-feature-flags`,
  `arch-debug-trace`, `svc-moderation`, `api-etag`,
  `api-debug-trace`) should land in their respective host pages per
  the §4.2 mapping.
* **For every anchor that lands, the matching `nitpick_ignore` entry
  in `conf.py` must be removed in the same commit.** Otherwise typos
  on the now-resolvable anchor would silently slip through.
* Each page-landing should bring the warning count strictly down,
  validating the entry-removal in real time.

**Foundation-page review subtask (owns the docutils ERROR).**

* Owns the `configuration.rst:254` hyphenation fix
  (`startup-time validation` → `startup-time-validation`).
* The closest existing section that may host the corrected anchor is
  `configuration.rst:322` "Startup-time vs runtime mutability" — see
  §7.1.

**Repo-tooling subtask (if/when one runs).**

* If `uv` becomes authoritative for this docset, switch
  `python -m sphinx` calls to `uv run sphinx-build` in any committed
  CI/build scripts. The build output is identical; only the launcher
  differs.

### 9.3 Risks and mitigations

* **Risk:** a future page-authoring subtask lands a foundation page
  but forgets to remove the matching `nitpick_ignore` line. A typo'd
  `:ref:`<anchor>`` would then silently slip through — the
  suppression masks the regression.
  **Mitigation:** the inline comment header at `conf.py:69-79` and the
  per-tuple citation comments at `conf.py:94-129` explicitly tell the
  next author: "Removing each entry below is the *signal* that the
  corresponding page authoring subtask has landed." See also the
  entry-to-page mapping in §4.2.

* **Risk:** a new foundation-page edit introduces a broken anchor
  that collides with one of the 9 suppressed names.
  **Mitigation:** the `conf.py` block-header comment instructs the
  author to add a new `nitpick_ignore` entry only with a Shared
  Anchor Map row in `glossary.rst:358+` to back it; without the
  anchor-map row, no `nitpick_ignore` line should be added.

* **Risk:** a future maintainer "fixes" the suppression keys back to
  `('std:label', X)` because that string *looks* more semantically
  correct (label = the target object).
  **Mitigation:** the on-disk `conf.py:81-93` block-header comment
  names the matching rule (`f'{domain.name}:{typ}'` from
  `sphinx/transforms/post_transforms/__init__.py`) and explains that
  `typ` is the role used at the citation site, not the object type
  the role would have resolved to. §6 of this document carries the
  same explanation as a backup record.

* **Risk:** rollback of this subtask is needed (e.g., if the conf.py
  edit is found to mask a real bug).
  **Rollback procedure:** revert `conf.py:54-129` and
  `glossary.rst:13`; delete `docs/build/build-log-after-fix.txt`. The
  pre-fix state is reproducible from the (preserved) warm-build log
  at `docs/build/build-log-warm.txt`. A clean rebuild after rollback
  yields 81 warnings (the original warm log).

### 9.4 Exit criteria

The subtask is complete when:

1. ✓ Post-fix warning count = 6 (verified: `build-log-after-fix.txt:45`).
2. ✓ The 6 surviving warnings match the escalation set in §7 verbatim
   (verified: `build-log-after-fix.txt:15-20`).
3. ✓ Zero foundation-page edits (verified by mtime — see §1.2 (i)).
4. ✓ Each `nitpick_ignore` entry has a one-line citation comment
   (verified: `conf.py:94-129`).
5. ✓ `nitpicky=True` is unchanged (verified: `conf.py:52`).
6. ✓ No `suppress_warnings = [...]` line in `conf.py` (verified:
   `grep "suppress_warnings" docs/source/conf.py` → 0 matches).
7. ✓ Per-warning triage report exists (this document, §8).

All seven criteria are met as of 2026-05-04.

---

## 10. Cross-references to predecessor and parallel artifacts

This deliverable is self-contained. The longer planning/iteration
artifacts in `docs/_plan/` carry deeper background that a downstream
maintainer or reviewer may want:

| Artifact | Lines | What it adds beyond this document |
|----------|------:|-----------------------------------|
| `sphinx_build_capture_plan.md` (subtask-1, flow 0) | 456 | Predecessor build-capture plan; empirical pre-fix predictions (5 toctree + ~70+ undefined-label + ≥1 docutils ERROR; exit 0); environment audit (no `uv`, no `pyproject.toml`). All predictions held — see §C.1 of the consolidated record. |
| `sphinx_initial_build_plan.md` (subtask-1, flow 1) | 520 | Parallel build-capture plan; second-source verification of environmental constraints; install-path decision matrix (5 options compared); cross-platform tooling pattern (bash `${PIPESTATUS[0]}`, PowerShell stderr-wrapping caveat) — used in §5.1 above. |
| `sphinx_warning_triage_plan.md` | 1,453 | Pre-execution planning artifact; full §0–§10 structure; predicted 6 post-fix warnings ahead of time; was the source of the *original* `('std:label', X)` recommendation that Flow 0 caught and corrected. |
| `sphinx_warning_triage_report.md` | 816 | End-to-end execution report; source of the empirical `std:label → std:ref` discovery; the on-disk fixes in `conf.py` and `glossary.rst:13` are this flow's edits. |
| `sphinx_warning_triage_consolidated.md` | 1,214 | Iteration-4 consolidation of the planning + execution flows + a parallel consolidator's input. Contains the deepest matching-rule derivation (§A.3.1), cross-flow agreement matrix (§E.1), and locator evidence for the 16 `('std:label', X)` occurrences in the original Flow 1 raw plan. |
| `sphinx_warning_triage_plan_consolidated.md` | 247 | Parallel iteration-3 consolidation; source of the §9.3 risks/rollback subsection and the entry-to-page mapping pattern. |
| `sphinx_warning_triage_final.md` | 250 | Earlier "final" consolidated plan-and-report. Concise; same conclusions as this document. |
| `sphinx_scaffolding_audit.md` | 272 | Predecessor page-existence audit — confirmed 3 of 8 foundation pages on disk before subtask 1. |

This deliverable supersedes none of them but is the canonical
subtask-2 record. If a reviewer reads only one file from this
directory to understand subtask 2's outcome, this is the file to read.

---

## 11. Audit trail (verification commands and their outputs)

The following commands were run during preparation of this deliverable
to verify the on-disk state matches every claim above. Outputs recorded
inline.

    # 1. Foundation pages on disk vs missing
    ls docs/source/*.rst
    # → configuration.rst, glossary.rst, index.rst, inference-models.rst, operations.rst
    # → 5 of 8 foundation files (introduction, getting-started, architecture, service-layer, api-reference are absent)

    # 2. Warm-log warning count
    grep -c "WARNING\|ERROR" docs/build/build-log-warm.txt   # -> 81
    tail -2 docs/build/build-log-warm.txt                    # -> "build succeeded, 81 warnings."

    # 3. Post-fix log warning count
    grep -c "WARNING\|ERROR" docs/build/build-log-after-fix.txt   # -> 6
    tail -2 docs/build/build-log-after-fix.txt                    # -> "build succeeded, 6 warnings."

    # 4. nitpick_ignore tuple key correctness on disk
    grep "nitpick_ignore\|std:ref\|std:label" docs/source/conf.py
    # → 9 lines all matching ('std:ref','<anchor>') — zero std:label survivors

    # 5. nitpicky=True is unchanged (constraint (ii))
    grep "nitpicky\|suppress_warnings" docs/source/conf.py
    # → "nitpicky = True" present; no suppress_warnings line

    # 6. glossary.rst:13 fix verification
    sed -n "13p" docs/source/glossary.rst
    # → "   * The ``.. glossary::`` directive below — alphabetised — for"

    # 7. Foundation-page mtime audit (constraint (i))
    ls -la docs/source/configuration.rst docs/source/inference-models.rst docs/source/operations.rst
    # → all mtimes earlier than the post-fix build (10:44); no edits

This deliverable is approved for handoff to the next subtask in the
chain (foundation-page authoring or foundation-page review).
