# Sphinx Warning Triage — Subtask 2 Report

**Subtask:** Triage every warning from the warm-build log (subtask 1 output),
fix in-scope items in `conf.py` / `index.rst` / `glossary.rst`, suppress
out-of-scope items via targeted `nitpick_ignore` entries with citation
comments, escalate what cannot be silenced, then re-build and report.

**Date:** 2026-05-04
**Repo root:** `C:\Users\yxinl\OneDrive\Projects\PythonProjects\CoreProjects\OpenTeam`
**Docset:** `responsible-ai-api` (under `docs/source/`)
**Scope:** Subtask 2 only — consumes subtask 1's `docs/build/build-log-warm.txt`
as input; does not re-run the install / cold-build / warm-build capture.

---

## TL;DR

| Metric | Value |
|--------|------:|
| Warm-log warnings (input) | **81** |
| Post-fix warnings (output) | **6** |
| Net delta | **−75** |
| Source files edited | **2** (`conf.py`, `glossary.rst`) |
| Source files left unedited | **3 foundation pages + `index.rst`** |
| `nitpick_ignore` entries added | **9** (one per unique forward-referenced anchor) |
| Real bugs fixed in NEW file | **1** (`glossary.rst:13` `:rst:dir:` self-reference) |
| Real bugs escalated | **1** (`configuration.rst:254` docutils ERROR — foundation page) |
| Toctree gaps escalated | **5** (missing prerequisite pages) |

**Single most important finding** (carried forward from prior triage
iterations and re-verified on this rebuild): the `nitpick_ignore`
tuple key must be `('std:ref', '<anchor>')`, **not** `('std:label', ...)`.
Sphinx 8.2's `ReferencesResolver.warn_missing_reference` builds the
suppression key as `f'{domain.name}:{typ}'` where `typ` is the **role**
that cited the anchor (`std:ref`), not the **node type** of the anchor
itself (`std:label`). Using `std:label` silently fails to suppress and
leaves all 74 `[ref.ref]` warnings intact. This is the `−74` driver of
the `−75` total delta; the remaining `−1` is the `glossary.rst:13` fix.

---

## 0. Scope, constraints, and bucket definitions

### 0.1 Verbatim CRITICAL constraints from the user request

(i) **NEVER modify** `introduction.rst`, `getting-started.rst`,
`architecture.rst`, `service-layer.rst`, `inference-models.rst`,
`configuration.rst`, `api-reference.rst`, or `operations.rst` — these are
line-by-line audited per `CONSOLIDATION_NOTES`. (Five of the eight are
not on disk; the three that are — `inference-models.rst`,
`configuration.rst`, `operations.rst` — must remain untouched.)

(ii) **Do NOT weaken `nitpicky=True`** in `conf.py` to mass-suppress
warnings. Use targeted `nitpick_ignore` entries with one-line citation
comments naming the source page and reason.

(iii) **Escalate, do not silence**, if a warning is severe enough that
suppression would be unacceptable.

### 0.2 The four request-defined buckets, with disposition rules

| Bucket | Definition | Action |
|--------|------------|--------|
| **REAL-BUG** | Must-fix: RST syntax error, broken intra-page ref, duplicate-anchor collision, etc. | Fix in place if origin is `conf.py` / `index.rst` / `glossary.rst`; **escalate** if origin is a foundation page. |
| **EXPECTED-NOW-RESOLVED** | A forward `:ref:` anchor that a prior subtask has since made resolvable. | Should be **ZERO** entries — listed only for confirmation that the anchor chain is sound. |
| **DRIFT** | Anchor-name mismatch between producer (the `.. _<name>:`) and consumer (the `:ref:<name>`) — fix in the **NEW file only** (`conf.py` / `index.rst` / `glossary.rst`). | Fix the consumer in the new file; if the consumer is in a foundation page, escalate. |
| **PRE-EXISTING-IN-FOUNDATION** | Warning originating in one of the eight already-authored prose pages — document but **do NOT modify the page**. | Add a `nitpick_ignore` entry in `conf.py` with a one-line citation comment, OR escalate (if not suppressible). |

### 0.3 Two extension buckets (categorisation refinements)

The four buckets above cover the anchor-resolution warnings. Two
warning shapes in the warm log fall outside them and need explicit
disposition rules — neither lives in scope (the warning *origin*) the
buckets describe:

| Extension bucket | Warning shape | Why it isn't in the four buckets |
|------------------|---------------|----------------------------------|
| **PRE-EXISTING-IN-NEW-FILE** | `[ref.ref]` warnings originating in `glossary.rst` (a NEW file) whose target is one of the same forward-referenced anchors. | The four-bucket schema implicitly assumes ref.ref warnings live in foundation pages. The `glossary.rst` ones are functionally identical (forward-ref to a not-yet-authored page) and are caught by the **same** `nitpick_ignore` entries (anchor namespace is shared, not file-scoped). They are not REAL-BUGs (the ref *itself* is correct) and are not DRIFT (no name mismatch). |
| **TOCTREE-PRECONDITION-GAP** | `[toc.not_readable]` warnings originating in `index.rst` for documents that don't exist on disk. | Not an anchor warning at all — it names whole missing files. Constraint (ii) forbids `suppress_warnings = ['toc.not_readable']`; pruning the toctree would mask the gap. **Escalation** is the only acceptable action. |

---

## 1. Inputs — warm-build log inventory

### 1.1 Source artifact

`docs/build/build-log-warm.txt` — 122 lines (ANSI-stripped),
`build succeeded, 81 warnings.`, exit 0. Generated by subtask 1 with:

* Sphinx 8.2.3
* docutils 0.21.2
* sphinx_rtd_theme 3.0.2
* Python 3.12.7 (miniforge3) — `uv` is not on PATH (verified again at the
  top of subtask 2; see §3)

### 1.2 Aggregate counts

```
sources read:               5  (configuration, glossary, index, inference-models, operations)
build status:               succeeded  (keep_going default; ERRORs do not abort)
total reported issues:      81
  ├─ docutils ERROR:         1   (configuration.rst:254)
  ├─ [toc.not_readable]:     5   (index.rst:22)
  ├─ [ref.dir]:              1   (glossary.rst:13)
  └─ [ref.ref]:             74   (across configuration, glossary, inference-models, operations)
```

### 1.3 Per-source × per-tag breakdown

| Source file | docutils ERROR | toc.not_readable | ref.dir | ref.ref | Total |
|-------------|---------------:|-----------------:|--------:|--------:|------:|
| `configuration.rst` (foundation) | 1 | 0 | 0 | 43 | **44** |
| `glossary.rst` (NEW) | 0 | 0 | 1 | 19 | **20** |
| `index.rst` (NEW) | 0 | 5 | 0 | 0 | **5** |
| `inference-models.rst` (foundation) | 0 | 0 | 0 | 7 | **7** |
| `operations.rst` (foundation) | 0 | 0 | 0 | 5 | **5** |
| **Total** | **1** | **5** | **1** | **74** | **81** |

### 1.4 The 74 `[ref.ref]` warnings collapse to 9 unique anchors

Per-anchor cite counts (sorted descending):

| Anchor | Cites | Producer page (expected) | Consumer pages |
|--------|------:|--------------------------|----------------|
| `architecture` | 21 | `architecture.rst` (not on disk) | configuration, glossary, inference-models, operations |
| `api-reference` | 16 | `api-reference.rst` (not on disk) | configuration, glossary, inference-models |
| `getting-started` | 11 | `getting-started.rst` (not on disk) | configuration, glossary, operations |
| `svc-moderation` | 11 | `service-layer.rst` (not on disk) | configuration, glossary, inference-models |
| `introduction` | 5 | `introduction.rst` (not on disk) | configuration, glossary |
| `api-etag` | 4 | `api-reference.rst` sub-anchor | configuration, glossary |
| `gs-feature-flags` | 2 | `getting-started.rst` sub-anchor | configuration, glossary |
| `arch-debug-trace` | 2 | `architecture.rst` sub-anchor | glossary |
| `api-debug-trace` | 2 | `api-reference.rst` sub-anchor | glossary |
| **Total cites** | **74** | (5 missing pages) | (4 cite-side pages) |

The 9 unique anchors fully cover all `[ref.ref]` warnings; no further
`nitpick_ignore` entries are needed.

### 1.5 Distinct call-sites

`74` cites correspond to `72` distinct `(source_file, line_number, anchor)`
triples — three lines emit two cites because they cite the same anchor
twice on the same line (e.g., `configuration.rst:24` cites `api-reference`
twice). Sphinx counts each emission separately. The `nitpick_ignore`
mechanism suppresses each emission, so the count is fully accounted for
in the post-fix delta.

---

## 2. Categorisation — every warning, every bucket

### 2.1 Bucket summary

| Bucket | Count | Action taken | Verified by |
|--------|------:|--------------|-------------|
| EXPECTED-NOW-RESOLVED | **0** | None — no upstream subtask landed any of the 5 missing pages | Disk audit: only 3 foundation pages on disk; all 9 anchors still unresolved → bucket correctly empty |
| REAL-BUG, **fixable** in NEW file | **1** | `glossary.rst:13` — replaced `:rst:dir:`glossary`` self-reference with literal `` ``.. glossary::`` `` text | post-fix log: 0 `[ref.dir]` warnings (was 1) |
| REAL-BUG, **escalated** (foundation page) | **1** | `configuration.rst:254` docutils ERROR `Unknown target name: "Startup-time validation"` — left as-is, flagged in §5 | post-fix log: still 1 docutils ERROR |
| DRIFT (anchor-name mismatch) | **0** | None — every undefined-label warning is a *missing-page* problem (the producer page has not been authored yet), not a *misnamed-anchor* problem. Verified by grepping `:ref:`<anchor>`` against the glossary's "Shared Anchor Map" registry. | Glossary "anchor-map" registry shows producer-side and consumer-side spellings agree for all 9 forward-referenced anchors |
| PRE-EXISTING-IN-FOUNDATION (`[ref.ref]` in foundation pages) | **55** | Suppressed via 9-entry `nitpick_ignore` block in `conf.py` (one entry per unique anchor; 55 cite emissions silenced collectively) | post-fix log: 0 `[ref.ref]` warnings (was 55 from foundation pages) |
| PRE-EXISTING-IN-NEW-FILE (extension bucket: `[ref.ref]` in `glossary.rst`) | **19** | Suppressed via the **same 9 `nitpick_ignore` entries** — anchor namespace is shared, not file-scoped | post-fix log: 0 `[ref.ref]` warnings (was 19 from `glossary.rst`) |
| TOCTREE-PRECONDITION-GAP (extension bucket: `[toc.not_readable]` in `index.rst`) | **5** | Escalated — pruning toctree would mask the gap; blanket `suppress_warnings` violates constraint (ii) | post-fix log: still 5 `[toc.not_readable]` warnings (intentional residual) |
| **Total** | **81** | | |

### 2.2 Verifying the EXPECTED-NOW-RESOLVED bucket is empty

Per the request: "Verify the EXPECTED-NOW-RESOLVED bucket is empty
(forward refs from foundation pages to svc/inf/config/infra/ops anchors
should all resolve)". Procedure:

1. Enumerate the 9 unique forward-referenced anchor names from the warm
   log (§1.4).
2. For each, grep `docs/source/*.rst` for an `.. _<anchor>:` definition.
3. Bucket as RESOLVED if found, UNRESOLVED if not.

Result:

| Anchor | Grep target | Found? | Bucket |
|--------|-------------|-------:|--------|
| `introduction` | `^\.\. _introduction:` | No | UNRESOLVED |
| `getting-started` | `^\.\. _getting-started:` | No | UNRESOLVED |
| `gs-feature-flags` | `^\.\. _gs-feature-flags:` | No | UNRESOLVED |
| `architecture` | `^\.\. _architecture:` | No | UNRESOLVED |
| `arch-debug-trace` | `^\.\. _arch-debug-trace:` | No | UNRESOLVED |
| `svc-moderation` | `^\.\. _svc-moderation:` | No | UNRESOLVED |
| `api-reference` | `^\.\. _api-reference:` | No | UNRESOLVED |
| `api-etag` | `^\.\. _api-etag:` | No | UNRESOLVED |
| `api-debug-trace` | `^\.\. _api-debug-trace:` | No | UNRESOLVED |

**0 anchors resolved → EXPECTED-NOW-RESOLVED bucket is empty.** This
confirms the anchor chain is sound: the unresolved labels are unresolved
because the *page* is missing, not because a prior subtask landed the
page with a different anchor name. (If even one anchor had been
RESOLVED here, that would mean a page authoring subtask had landed and
the corresponding `nitpick_ignore` line should be deleted; that
condition does not yet hold.)

### 2.3 Per-warning detail table — all 81 warnings

The full per-warning record. Columns: `#` (sequence in the warm log),
`Source` (file), `Line`, `Severity`, `Tag` (Sphinx warning category),
`Target` (anchor / document / target name in the message), `Bucket`,
`Action`. Sorted by source file then line number for readability.

| # | Source | Line | Sev | Tag | Target | Bucket | Action |
|---|--------|-----:|-----|-----|--------|--------|--------|
| 1 | configuration.rst | 254 | ERROR | docutils | "Startup-time validation" | REAL-BUG (escalated) | Foundation page — flag in §5; next foundation-edit subtask owns the fix |
| 2 | configuration.rst | 9 | W | ref.ref | introduction | PRE-EXISTING-IN-FOUNDATION | Suppress via `('std:ref','introduction')` in `conf.py` |
| 3 | configuration.rst | 9 | W | ref.ref | getting-started | PRE-EXISTING-IN-FOUNDATION | Suppress via `('std:ref','getting-started')` |
| 4 | configuration.rst | 9 | W | ref.ref | architecture | PRE-EXISTING-IN-FOUNDATION | Suppress via `('std:ref','architecture')` |
| 5 | configuration.rst | 9 | W | ref.ref | api-reference | PRE-EXISTING-IN-FOUNDATION | Suppress via `('std:ref','api-reference')` |
| 6 | configuration.rst | 9 | W | ref.ref | svc-moderation | PRE-EXISTING-IN-FOUNDATION | Suppress via `('std:ref','svc-moderation')` |
| 7 | configuration.rst | 9 | W | ref.ref | architecture | PRE-EXISTING-IN-FOUNDATION | Same suppression — duplicate cite on line 9 |
| 8 | configuration.rst | 24 | W | ref.ref | architecture | PRE-EXISTING-IN-FOUNDATION | Suppressed |
| 9 | configuration.rst | 24 | W | ref.ref | api-reference | PRE-EXISTING-IN-FOUNDATION | Suppressed |
| 10 | configuration.rst | 24 | W | ref.ref | api-reference | PRE-EXISTING-IN-FOUNDATION | Same — duplicate cite |
| 11 | configuration.rst | 112 | W | ref.ref | architecture | PRE-EXISTING-IN-FOUNDATION | Suppressed |
| 12 | configuration.rst | 180 | W | ref.ref | getting-started | PRE-EXISTING-IN-FOUNDATION | Suppressed |
| 13 | configuration.rst | 189 | W | ref.ref | getting-started | PRE-EXISTING-IN-FOUNDATION | Suppressed |
| 14 | configuration.rst | 280 | W | ref.ref | api-reference | PRE-EXISTING-IN-FOUNDATION | Suppressed |
| 15 | configuration.rst | 352 | W | ref.ref | getting-started | PRE-EXISTING-IN-FOUNDATION | Suppressed |
| 16 | configuration.rst | 634 | W | ref.ref | api-reference | PRE-EXISTING-IN-FOUNDATION | Suppressed |
| 17 | configuration.rst | 634 | W | ref.ref | getting-started | PRE-EXISTING-IN-FOUNDATION | Suppressed |
| 18 | configuration.rst | 869 | W | ref.ref | svc-moderation | PRE-EXISTING-IN-FOUNDATION | Suppressed |
| 19 | configuration.rst | 884 | W | ref.ref | api-reference | PRE-EXISTING-IN-FOUNDATION | Suppressed |
| 20 | configuration.rst | 1068 | W | ref.ref | api-etag | PRE-EXISTING-IN-FOUNDATION | Suppressed |
| 21 | configuration.rst | 1077 | W | ref.ref | architecture | PRE-EXISTING-IN-FOUNDATION | Suppressed |
| 22 | configuration.rst | 1175 | W | ref.ref | architecture | PRE-EXISTING-IN-FOUNDATION | Suppressed |
| 23 | configuration.rst | 1175 | W | ref.ref | api-reference | PRE-EXISTING-IN-FOUNDATION | Suppressed |
| 24 | configuration.rst | 1186 | W | ref.ref | architecture | PRE-EXISTING-IN-FOUNDATION | Suppressed |
| 25 | configuration.rst | 1227 | W | ref.ref | api-reference | PRE-EXISTING-IN-FOUNDATION | Suppressed |
| 26 | configuration.rst | 1227 | W | ref.ref | svc-moderation | PRE-EXISTING-IN-FOUNDATION | Suppressed |
| 27 | configuration.rst | 1361 | W | ref.ref | api-reference | PRE-EXISTING-IN-FOUNDATION | Suppressed |
| 28 | configuration.rst | 1437 | W | ref.ref | architecture | PRE-EXISTING-IN-FOUNDATION | Suppressed |
| 29 | configuration.rst | 1638 | W | ref.ref | api-reference | PRE-EXISTING-IN-FOUNDATION | Suppressed |
| 30 | configuration.rst | 1703 | W | ref.ref | architecture | PRE-EXISTING-IN-FOUNDATION | Suppressed |
| 31 | configuration.rst | 1740 | W | ref.ref | api-reference | PRE-EXISTING-IN-FOUNDATION | Suppressed |
| 32 | configuration.rst | 1770 | W | ref.ref | svc-moderation | PRE-EXISTING-IN-FOUNDATION | Suppressed |
| 33 | configuration.rst | 1840 | W | ref.ref | api-reference | PRE-EXISTING-IN-FOUNDATION | Suppressed |
| 34 | configuration.rst | 1897 | W | ref.ref | svc-moderation | PRE-EXISTING-IN-FOUNDATION | Suppressed |
| 35 | configuration.rst | 2052 | W | ref.ref | introduction | PRE-EXISTING-IN-FOUNDATION | Suppressed |
| 36 | configuration.rst | 2054 | W | ref.ref | getting-started | PRE-EXISTING-IN-FOUNDATION | Suppressed |
| 37 | configuration.rst | 2054 | W | ref.ref | gs-feature-flags | PRE-EXISTING-IN-FOUNDATION | Suppressed |
| 38 | configuration.rst | 2058 | W | ref.ref | architecture | PRE-EXISTING-IN-FOUNDATION | Suppressed |
| 39 | configuration.rst | 2062 | W | ref.ref | api-reference | PRE-EXISTING-IN-FOUNDATION | Suppressed |
| 40 | configuration.rst | 2066 | W | ref.ref | api-etag | PRE-EXISTING-IN-FOUNDATION | Suppressed |
| 41 | configuration.rst | 2078 | W | ref.ref | svc-moderation | PRE-EXISTING-IN-FOUNDATION | Suppressed |
| 42 | configuration.rst | 2111 | W | ref.ref | introduction | PRE-EXISTING-IN-FOUNDATION | Suppressed |
| 43 | configuration.rst | 2111 | W | ref.ref | getting-started | PRE-EXISTING-IN-FOUNDATION | Suppressed |
| 44 | configuration.rst | 2111 | W | ref.ref | architecture | PRE-EXISTING-IN-FOUNDATION | Suppressed |
| 45 | glossary.rst | 13 | W | ref.dir | glossary | REAL-BUG (fixable in NEW) | **EDITED** — `glossary.rst:13` rewritten; replaced `:rst:dir:`glossary`` self-reference with literal `` ``.. glossary::`` `` text |
| 46 | glossary.rst | 76 | W | ref.ref | api-reference | PRE-EXISTING-IN-NEW-FILE | Suppressed |
| 47 | glossary.rst | 76 | W | ref.ref | api-debug-trace | PRE-EXISTING-IN-NEW-FILE | Suppressed |
| 48 | glossary.rst | 76 | W | ref.ref | architecture | PRE-EXISTING-IN-NEW-FILE | Suppressed |
| 49 | glossary.rst | 76 | W | ref.ref | arch-debug-trace | PRE-EXISTING-IN-NEW-FILE | Suppressed |
| 50 | glossary.rst | 89 | W | ref.ref | api-etag | PRE-EXISTING-IN-NEW-FILE | Suppressed |
| 51 | glossary.rst | 122 | W | ref.ref | svc-moderation | PRE-EXISTING-IN-NEW-FILE | Suppressed |
| 52 | glossary.rst | 220 | W | ref.ref | introduction | PRE-EXISTING-IN-NEW-FILE | Suppressed |
| 53 | glossary.rst | 619 | W | ref.ref | introduction | PRE-EXISTING-IN-NEW-FILE | Suppressed |
| 54 | glossary.rst | 620 | W | ref.ref | getting-started | PRE-EXISTING-IN-NEW-FILE | Suppressed |
| 55 | glossary.rst | 620 | W | ref.ref | gs-feature-flags | PRE-EXISTING-IN-NEW-FILE | Suppressed |
| 56 | glossary.rst | 624 | W | ref.ref | architecture | PRE-EXISTING-IN-NEW-FILE | Suppressed |
| 57 | glossary.rst | 624 | W | ref.ref | arch-debug-trace | PRE-EXISTING-IN-NEW-FILE | Suppressed |
| 58 | glossary.rst | 628 | W | ref.ref | svc-moderation | PRE-EXISTING-IN-NEW-FILE | Suppressed |
| 59 | glossary.rst | 638 | W | ref.ref | api-reference | PRE-EXISTING-IN-NEW-FILE | Suppressed |
| 60 | glossary.rst | 638 | W | ref.ref | api-debug-trace | PRE-EXISTING-IN-NEW-FILE | Suppressed |
| 61 | glossary.rst | 638 | W | ref.ref | api-etag | PRE-EXISTING-IN-NEW-FILE | Suppressed |
| 62 | glossary.rst | 701 | W | ref.ref | architecture | PRE-EXISTING-IN-NEW-FILE | Suppressed |
| 63 | glossary.rst | 701 | W | ref.ref | api-reference | PRE-EXISTING-IN-NEW-FILE | Suppressed |
| 64 | glossary.rst | 747 | W | ref.ref | architecture | PRE-EXISTING-IN-NEW-FILE | Suppressed |
| 65 | index.rst | 22 | W | toc.not_readable | introduction | TOCTREE-PRECONDITION-GAP | Escalated (do not prune toctree, do not blanket-suppress) |
| 66 | index.rst | 22 | W | toc.not_readable | getting-started | TOCTREE-PRECONDITION-GAP | Escalated |
| 67 | index.rst | 22 | W | toc.not_readable | architecture | TOCTREE-PRECONDITION-GAP | Escalated |
| 68 | index.rst | 22 | W | toc.not_readable | service-layer | TOCTREE-PRECONDITION-GAP | Escalated |
| 69 | index.rst | 22 | W | toc.not_readable | api-reference | TOCTREE-PRECONDITION-GAP | Escalated |
| 70 | inference-models.rst | 9 | W | ref.ref | architecture | PRE-EXISTING-IN-FOUNDATION | Suppressed |
| 71 | inference-models.rst | 9 | W | ref.ref | svc-moderation | PRE-EXISTING-IN-FOUNDATION | Suppressed |
| 72 | inference-models.rst | 80 | W | ref.ref | architecture | PRE-EXISTING-IN-FOUNDATION | Suppressed |
| 73 | inference-models.rst | 476 | W | ref.ref | svc-moderation | PRE-EXISTING-IN-FOUNDATION | Suppressed |
| 74 | inference-models.rst | 1004 | W | ref.ref | architecture | PRE-EXISTING-IN-FOUNDATION | Suppressed |
| 75 | inference-models.rst | 1131 | W | ref.ref | architecture | PRE-EXISTING-IN-FOUNDATION | Suppressed |
| 76 | inference-models.rst | 1135 | W | ref.ref | svc-moderation | PRE-EXISTING-IN-FOUNDATION | Suppressed |
| 77 | operations.rst | 16 | W | ref.ref | getting-started | PRE-EXISTING-IN-FOUNDATION | Suppressed |
| 78 | operations.rst | 16 | W | ref.ref | architecture | PRE-EXISTING-IN-FOUNDATION | Suppressed |
| 79 | operations.rst | 405 | W | ref.ref | getting-started | PRE-EXISTING-IN-FOUNDATION | Suppressed |
| 80 | operations.rst | 1004 | W | ref.ref | getting-started | PRE-EXISTING-IN-FOUNDATION | Suppressed |
| 81 | operations.rst | 1007 | W | ref.ref | architecture | PRE-EXISTING-IN-FOUNDATION | Suppressed |

(`Sev: W` = WARNING; `ERROR` is shown explicitly. Row order is by
source/line, not by warm-log emission order.)



---

## 3. Tooling note — `uv run sphinx-build` substitution

The user request prescribes:

```bash
rm -rf docs/build/html
uv run sphinx-build -b html docs/source docs/build/html
```

`uv` is **not on PATH** in this environment (verified via
`command -v uv` -> not found; consistent with subtask 1's environment
audit). The active interpreter is miniforge3 Python 3.12.7, which has
the required toolchain importable:

```
sphinx 8.2.3        # required: 8.x
docutils 0.21.2     # required: >= 0.20
sphinx_rtd_theme 3.0.2
```

Substitution applied for the rebuild:

```bash
rm -rf docs/build/html
python -m sphinx -b html --no-color docs/source docs/build/html \
    > docs/build/build-log-after-fix.txt 2>&1
```

This is a **toolchain** substitution, not a **behaviour** substitution
- same Sphinx 8.2.3 binary, same source tree, same `nitpicky=True`
flag. The `--no-color` suppresses the ANSI escapes that would otherwise
embed in the redirected log; the previously-captured warm log was
similarly ANSI-stripped. Empirically, both runs produce the same
warning counts as the upstream prediction (warm: 81; post-fix: 6),
which validates the substitution.

If/when `uv` lands on PATH (e.g., after a `pipx install uv` or a global
tool install), the original command form should be used verbatim - no
behavioural difference is expected.

---

## 4. Action register - what was edited, what was suppressed

### 4.1 `docs/source/conf.py` - added 9-entry `nitpick_ignore` block

**File status before:** ~3.4 KB, no `nitpick_ignore` attribute defined.
**File status after:** ~7.7 KB, with a 49-line annotated `nitpick_ignore`
block (lines 54-129) plus a 26-line preamble explaining the matching
rule (lines 54-93) and 9 entries each carrying a citation comment
(lines 94-129).

**Form of each entry:** `('std:ref', '<anchor>')` - the **role** form
(`std:ref`), not the object form (`std:label`). See section 5.4 for the
correctness rationale.

**Entries added** (preserved as a self-documenting registry):

| # | Anchor | Citation comment summary |
|--:|--------|--------------------------|
| 1 | `introduction` | introduction.rst page-top anchor; cited at configuration.rst:9, 2052, 2111 and glossary.rst:220, 619 |
| 2 | `getting-started` | getting-started.rst page-top anchor; cited 11x across configuration, operations, glossary |
| 3 | `gs-feature-flags` | getting-started.rst sub-anchor for the laptop-side feature-flag workflow; cited from configuration.rst:2054 and glossary.rst:620 |
| 4 | `architecture` | architecture.rst - the most-cited forward anchor (21 cites); appears in every existing page plus glossary |
| 5 | `arch-debug-trace` | architecture.rst sub-anchor for the global handler chain that propagates `debug_trace`; required by glossary.rst:76, 624, 638 |
| 6 | `svc-moderation` | service-layer.rst sub-anchor for the four moderation services; cited 11x from configuration, inference-models, glossary |
| 7 | `api-reference` | api-reference.rst page-top anchor for the public HTTP contract; cited 16x across configuration, glossary |
| 8 | `api-etag` | api-reference.rst sub-anchor for the prompt-cache ETag protocol; cited from configuration.rst:1068, 2066 and glossary.rst:89, 638 |
| 9 | `api-debug-trace` | api-reference.rst sub-anchor for the debug-trace response shape; required by glossary.rst:76, 638 |

The `service-layer` page-top anchor itself is **not** listed because
nothing in the warm log `:ref:`-cites it (only its sub-anchor
`svc-moderation` is cited). When `service-layer.rst` lands and someone
adds a `:ref:`service-layer`` cite, the entry will need to be added -
but that is the correct workflow: a missing entry surfaces an honest
warning that someone should pair with an anchor-map registration.

**Header preamble** (verbatim from `conf.py:54-93`) explains why
suppression is appropriate, why each entry is a forward-reference (not
a typo), why the tuple key is `('std:ref', ...)`, and what conditions
should cause an entry to be **deleted** (= the corresponding page
landing). This satisfies constraint (ii) - every suppression carries a
citation, and the suppression is targeted (one anchor per entry), not
blanket.

### 4.2 `docs/source/glossary.rst:13` - replaced `:rst:dir:` self-reference

**Before** (warm log):

```
glossary.rst:13: WARNING: 'rst:dir' reference target not found: glossary [ref.dir]
```

The line at glossary.rst:13 used a `:rst:dir:` cross-reference role
pointing at "glossary". `:rst:dir:` is the Sphinx role for cross-
referencing an RST directive in the `std:doc:rst:dir:` domain. There
is no such directive named "glossary" in the inventory the docset
builds (the `glossary` directive ships from Sphinx itself, but the
`:rst:dir:` role does not auto-resolve to it unless `sphinx.ext.rst`
or a similar inventory is loaded). Treating the directive's name as
live code in narrative prose is incorrect - the right form is literal
text (double-backtick).

**After:** the line now renders the directive name as plain literal
formatting (double-backtick), which is content-equivalent: a reader
still sees the directive name in monospaced font; only the (unused,
broken) cross-ref has been removed.

**Verification:** `grep -n 'rst:dir|:rst:dir:' docs/source/glossary.rst`
returns no matches; post-fix log emits 0 `[ref.dir]` warnings.

### 4.3 `docs/source/index.rst` - **NOT EDITED**

The 5 `[toc.not_readable]` warnings on `index.rst:22` name the 5
not-yet-authored prerequisite pages: `introduction`, `getting-started`,
`architecture`, `service-layer`, `api-reference`. Three options were
considered:

| Option | Action | Verdict |
|--------|--------|---------|
| Prune the toctree | Remove the 5 missing entries from `index.rst:22` | **Rejected** - masks the gap; no signal to subsequent subtasks that 5 pages are still owed |
| Comment out per-entry | Wrap each missing page in `..` comment | **Rejected** - same masking effect; harder to un-comment cleanly when pages land |
| Leave as-is | Accept 5 residual `[toc.not_readable]` warnings | **Adopted** - preserves the manifest, provides per-build progress signal |

`index.rst` is therefore unchanged. The 5 residual warnings are
escalated in section 5 with the recommendation that the authoring
subtask for each missing page lands the file (which auto-clears the
corresponding warning).

### 4.4 Foundation pages - **NOT EDITED**

Per constraint (i), `inference-models.rst`, `configuration.rst`, and
`operations.rst` are out of scope. The 55 `[ref.ref]` warnings
originating in them are suppressed via `nitpick_ignore` (above); the 1
docutils ERROR in `configuration.rst:254` is escalated (section 5).

---

## 5. Escalations - items neither fixed nor suppressed

### 5.1 `configuration.rst:254` - docutils `Unknown target name` ERROR

**Warm log line:**
```
configuration.rst:254: ERROR: Unknown target name: "startup-time validation". [docutils]
```

**Source context (configuration.rst:250-260):**
```rst
       ``"localhost":"50050"``. ``TenantContextClient`` reads this
       once at construction (see `Tenant context (TCS)`_).
   * - ``asap_signer``
     - ``ASAP_ISSUER`` + ``ASAP_PRIVATE_KEY``
     - **Validated at startup** - see `Startup-time validation`_
       below. In local mode with ``NO_ASAP_SIGNER=true`` it is set to
       a ``unittest.mock.Mock(JWTAuthSigner)``.
```

The line uses an anonymous-named docutils reference target - the
backtick-quoted phrase followed by an underscore. Docutils requires
this to match either an explicit `.. _startup-time validation:`
directive or a section heading literally titled "Startup-time
validation". The closest candidates in the file are:

* Line 322: section heading `Startup-time vs runtime mutability` (close
  but not equal - would need to be retitled or anchored)
* Line 330: prose `Two settings have *startup-time validation*:` (in
  text body, not a heading; cannot be the target)

**Recommended fix (for the foundation-edit subtask that owns
configuration.rst):** add an explicit anchor where the target should
land - e.g., insert `.. _startup-time validation:` immediately above
the `Startup-time vs runtime mutability` heading (renaming the heading
itself would also work). Either option is a one-line edit that
resolves the ERROR. **Constraint (i) prevents applying this fix in
subtask 2.**

**Why not suppress?** The docutils ERROR is *intra-page* - the producer
and consumer both live in `configuration.rst`. There is no
`nitpick_ignore` shape that suppresses inline-reference docutils
ERRORs (the entries match `(domain, target)` for the std-domain
`:ref:` warnings only; the `[docutils]` warning class is emitted by
docutils itself before Sphinx's nitpick layer runs). Constraint (iii)
applies: **escalation is the only acceptable action.**

### 5.2 `index.rst:22` - 5x `[toc.not_readable]` for missing prerequisite pages

The 5 missing documents (`introduction`, `getting-started`,
`architecture`, `service-layer`, `api-reference`) are
**prerequisites**, not optional sections. The toctree in `index.rst`
encodes the full read-end-to-end manifest of the docset; pruning it
would mask the gap and break the read-once narrative. Suppressing
`toc.not_readable` would require a blanket `suppress_warnings` entry
that violates constraint (ii).

**Disposition:** flag in section 7 ("Open escalations carried forward
to subsequent subtasks"). When each missing page is authored and lands
under `docs/source/`, the corresponding warning will auto-clear
without any further `index.rst` edit.

### 5.3 Why these residual 6 are an *acceptable* end state

The post-fix log shows `build succeeded, 6 warnings.` - non-zero, but
deliberately so:

* All 6 residuals are **escalation flags** that signal an upstream
  authoring gap, not a regression.
* All 6 residuals will **self-clear** when the upstream gap closes
  (1 docutils ERROR clears when configuration.rst:254 gets a real
  target; 5 toctree warnings clear when the 5 pages are authored).
* Suppressing them would silently swallow the same authoring gap on
  every future build - exactly the regression that constraints (ii)
  and (iii) are designed to prevent.

This satisfies the request's "(or explicitly-triaged)" carve-out: a
clean **or explicitly-triaged** end state is the success criterion;
the 6 residuals are explicitly triaged here.

### 5.4 Correctness side-bar - why `('std:ref', X)` and not `('std:label', X)`

This is the load-bearing piece of analysis from the prior triage
iterations, recorded here so it isn't lost.

* When Sphinx encounters an unresolved `:ref:`<name>``, the
  `ReferencesResolver.warn_missing_reference` transform builds a
  suppression key as `f'{domain.name}:{typ}'` where `typ` is the
  **role** that emitted the cite - i.e., `ref` (the `:ref:` role lives
  in the `std` domain), giving `'std:ref'`.
* The intuitive but wrong key is `('std:label', ...)` - the **object
  type** that the role would have resolved to (`std:label` is the
  domain-object class for explicit `.. _name:` anchors). Sphinx never
  matches against the would-be-resolved object type; only against the
  emitting role's domain:type pair.
* Empirically (from the prior triage iteration that landed the fix on
  disk): rebuilding with `('std:label', X)` entries leaves all 74
  `[ref.ref]` warnings emitted; rewriting them as `('std:ref', X)`
  drops them all to 0. This single key-form rewrite is the -74
  driver of the -75 total delta.

The `conf.py:81-93` preamble paragraph documents this rule for the
next reader.

---

## 6. Verification - re-build after fixes

### 6.1 Command issued (subtask 2)

```bash
rm -rf docs/build/html
python -m sphinx -b html --no-color docs/source docs/build/html \
    > docs/build/build-log-after-fix.txt 2>&1
echo "exit: $?"
```

(`uv run` substituted with `python -m sphinx` per section 3.)

### 6.2 Result

```
exit: 0
docs/build/build-log-after-fix.txt   - 37 lines, ANSI-stripped
build succeeded, 6 warnings.
```

### 6.3 Per-warning post-fix log (verbatim)

| # | Source | Line | Sev | Tag | Message head |
|---|--------|-----:|-----|-----|--------------|
| 1 | configuration.rst | 254 | ERROR | docutils | Unknown target name: "startup-time validation". |
| 2 | index.rst | 22 | W | toc.not_readable | toctree contains reference to nonexisting document 'introduction' |
| 3 | index.rst | 22 | W | toc.not_readable | toctree contains reference to nonexisting document 'getting-started' |
| 4 | index.rst | 22 | W | toc.not_readable | toctree contains reference to nonexisting document 'architecture' |
| 5 | index.rst | 22 | W | toc.not_readable | toctree contains reference to nonexisting document 'service-layer' |
| 6 | index.rst | 22 | W | toc.not_readable | toctree contains reference to nonexisting document 'api-reference' |

### 6.4 Delta breakdown

| Tag | Warm | Post-fix |  Delta | How the delta was achieved |
|-----|-----:|---------:|-------:|----------------------------|
| docutils ERROR | 1 | 1 | 0 | Escalated (foundation page; cannot edit) |
| `[toc.not_readable]` | 5 | 5 | 0 | Escalated (5 prerequisite pages still unauthored) |
| `[ref.dir]` | 1 | 0 | **-1** | Fixed in `glossary.rst:13` |
| `[ref.ref]` | 74 | 0 | **-74** | Suppressed via 9-entry `nitpick_ignore` block |
| **Total** | **81** | **6** | **-75** | |

### 6.5 Predicted-vs-observed reconciliation

| Predicted (from prior triage planning) | Observed | Match? |
|-----------------------------------------|----------|--------|
| `[ref.ref]` drops to 0 after `('std:ref', X)` rewrite | 0 | yes |
| `[ref.dir]` drops to 0 after `glossary.rst:13` fix | 0 | yes |
| `[toc.not_readable]` unchanged | 5 | yes |
| `docutils ERROR` unchanged | 1 | yes |
| Final summary `build succeeded, 6 warnings.` | 6 warnings | yes |
| Build exit code 0 | 0 | yes |

All 6 predictions land. No surprise residuals.

---

## 7. Open escalations carried forward to subsequent subtasks

The following items are explicitly out-of-scope for subtask 2 but must
not be lost. Each will close cleanly when the named upstream subtask
lands.

### 7.1 5 missing foundation pages - owned by per-page authoring subtasks

| Page | Closes warnings | Triggers nitpick_ignore deletions in `conf.py` |
|------|-----------------|------------------------------------------------|
| `introduction.rst` | `index.rst:22 -> 'introduction'` (1 toc warning) | `('std:ref','introduction')` |
| `getting-started.rst` | `index.rst:22 -> 'getting-started'` (1 toc warning) | `('std:ref','getting-started')`, `('std:ref','gs-feature-flags')` |
| `architecture.rst` | `index.rst:22 -> 'architecture'` (1 toc warning) | `('std:ref','architecture')`, `('std:ref','arch-debug-trace')` |
| `service-layer.rst` | `index.rst:22 -> 'service-layer'` (1 toc warning) | `('std:ref','svc-moderation')` (page-top anchor not currently cited; sub-anchor is) |
| `api-reference.rst` | `index.rst:22 -> 'api-reference'` (1 toc warning) | `('std:ref','api-reference')`, `('std:ref','api-etag')`, `('std:ref','api-debug-trace')` |

**Discipline:** when a page lands, the corresponding `nitpick_ignore`
line in `conf.py` should be **deleted in the same commit** - leaving
the entry in place after the anchor resolves would silently swallow
typos pointing at that anchor. The 9-entry block is intentionally
self-deleting in this sense; each entry's citation comment names the
condition for its own removal.

### 7.2 `configuration.rst:254` docutils ERROR - owned by the foundation-edit subtask for `configuration.rst`

Recommended one-line edit (to be applied by that subtask, not here):

```rst
.. _startup-time validation:

Startup-time vs runtime mutability
----------------------------------
```

inserted at line 322 (immediately above the existing section heading).
Alternatively, retitle the heading to `Startup-time validation` (one
word change). Either resolves the docutils ERROR with no other
collateral.

### 7.3 No outstanding triage items

EXPECTED-NOW-RESOLVED, DRIFT, REAL-BUG-fixable-in-NEW-file are all
**fully drained**:

* EXPECTED-NOW-RESOLVED: 0 - no upstream subtask landed any of the 5
  missing pages.
* DRIFT: 0 - no producer/consumer name mismatches; every undefined
  label is a missing-page problem.
* REAL-BUG-fixable: 1, fixed in section 4.2.

---

## 8. Cross-references and provenance

* **Inputs (read-only):**
  * `docs/build/build-log-warm.txt` (122 lines, 81 warnings) - subtask 1 output
  * `docs/source/configuration.rst`, `inference-models.rst`,
    `operations.rst` - foundation pages (read for site analysis only;
    not modified)
  * `docs/source/glossary.rst` "Shared Anchor Map" registry
    (lines 358-688) - source-of-truth for the producer-side spelling
    of the 9 forward-referenced anchors
  * Sphinx 8.2 source: `sphinx/transforms/post_transforms/__init__.py`
    `ReferencesResolver.warn_missing_reference` - for the
    `f'{domain.name}:{typ}'` matching rule (section 5.4)

* **Outputs (written by this subtask):**
  * `docs/source/conf.py` - added 9-entry `nitpick_ignore` block (lines
    54-129) and preamble explaining the matching rule
  * `docs/source/glossary.rst` - line 13 rewritten (replaced
    `:rst:dir:` self-reference with literal text)
  * `docs/build/build-log-after-fix.txt` - 37-line ANSI-stripped log,
    `build succeeded, 6 warnings.`
  * `docs/_plan/sphinx_warning_triage_subtask2_report.md` - this
    document

* **Predecessor planning artifacts** (preserved for context; not
  re-used as inputs by this report):
  * `docs/_plan/sphinx_warning_triage_plan.md` (1453 lines) - Flow 1
    iteration-2 consolidation; source of the section 3.2 verbatim diff
    citations
  * `docs/_plan/sphinx_warning_triage_consolidated.md` (1214 lines) -
    Flow 0 iteration-3 consolidation; source of the cross-platform
    rebuild tooling and Part E.1 cross-flow verification matrix
  * `docs/_plan/sphinx_warning_triage_final.md` (250 lines) - earlier
    "final consolidated" plan-and-report; this subtask 2 report
    supersedes its section 9 deliverable
  * `docs/_plan/sphinx_warning_triage_report.md` (816 lines) -
    end-to-end execution narrative
  * `docs/_plan/sphinx_warning_triage_plan_consolidated.md` (247
    lines) - earlier partial consolidation
  * `docs/_plan/sphinx_scaffolding_audit.md` (272 lines) - predecessor
    audit confirming 3 of 8 foundation pages on disk
  * `docs/_plan/sphinx_initial_build_plan.md` (520 lines) - subtask 1
    build-capture plan
  * `docs/_plan/sphinx_build_capture_plan.md` (456 lines) - subtask 1
    capture plan with environment audit

The redundancy across the predecessor artifacts reflects iterative
refinement on the same data; this subtask 2 report is the single
canonical artifact for the warning-triage deliverable specified in the
user request.

---

## 9. Compliance with the request's CRITICAL constraints

| Constraint | Honored? | Evidence |
|------------|---------:|----------|
| (i) Never modify the 8 foundation pages | yes | Only `conf.py` and `glossary.rst:13` edited; the 3 on-disk foundation pages (`configuration.rst`, `inference-models.rst`, `operations.rst`) are byte-unchanged; the 5 not-on-disk foundation pages were not authored here |
| (ii) Do not weaken `nitpicky=True`; use targeted `nitpick_ignore` with citations | yes | `conf.py:52` retains `nitpicky = True`; the 9 `nitpick_ignore` entries are each per-anchor (not blanket); each carries a multi-line citation comment naming source pages and reason; no `suppress_warnings = [...]` was added |
| (iii) Escalate (do not silently edit) when suppression is unacceptable | yes | 1 docutils ERROR + 5 toctree warnings escalated in sections 5 and 7 with recommended owners and recommended fixes; no foundation-page edits performed |

---

## 10. End-state declaration

The docset's warning state is now **explicitly triaged**:

* **0** unexplained warnings.
* **0** in-scope-and-fixable warnings outstanding.
* **6** explicitly-escalated warnings, each with an owner and a clearing
  condition (section 7).

Subtask 2 closes here. Subsequent subtasks (per-page authoring; the
foundation-edit subtask for `configuration.rst:254`) will draw down
the 6 residuals as a side-effect of doing their primary work.
