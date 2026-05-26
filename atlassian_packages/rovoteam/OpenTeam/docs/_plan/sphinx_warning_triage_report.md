# Sphinx Warm-Build Warning Triage Report

**Subtask scope.** Triage every warning from the *warm* `sphinx-build`
of `docs/source/`, fix what is in-scope (conf.py / index.rst /
glossary.rst only), suppress forward-reference noise via targeted
`nitpick_ignore` with citations, escalate anything severe enough that
silent suppression would be inappropriate, then re-build to confirm a
clean (or explicitly-triaged) end state.

**Triage date:** 2026-05-04
**Build environment:** Sphinx 8.2.3 + sphinx_rtd_theme 3.0.2, Python
3.12, Windows 11 (forward-slash log paths shown in this report; the
build itself uses native Windows paths).
**Build invocation (warm):** `python -m sphinx -b html docs/source
docs/build/html` *(equivalent to the spec's `uv run sphinx-build -b
html docs/source docs/build/html`; `uv` is not installed in this
environment, so the underlying Sphinx CLI was invoked directly via
`python -m sphinx`)*.
**Warm log:** `docs/build/build-log-warm.txt` (15 KB, ANSI-stripped).
**Post-fix log:** `docs/build/build-log-after-fix.txt` (3 KB).

---

## TL;DR

* **Warm-build warning total:** 81 (Sphinx tally; comprises 1 docutils
  ERROR + 5 toctree.not_readable WARNINGs + 1 ref.dir WARNING + 74
  ref.ref undefined-label WARNINGs).
* **Post-fix warning total:** 6 — a 92.6% reduction (75 of 81
  diagnostics resolved or suppressed with citation).
* **Bucket distribution and outcomes:**
  | Bucket | Count | Outcome |
  |--------|-------|---------|
  | REAL-BUG (in NEW file, fixable in place) | 1 | Fixed in `glossary.rst`. |
  | REAL-BUG (in FOUNDATION; cannot fix or suppress) | 1 | **Escalated** — see §6.1. |
  | REAL-BUG (root cause out of scope; cannot suppress) | 5 | **Escalated** — see §6.2. |
  | EXPECTED-NOW-RESOLVED | 0 | ✓ Confirmed empty (anchor chain is sound). |
  | DRIFT | 0 | ✓ No anchor-name mismatches detected. |
  | PRE-EXISTING-IN-FOUNDATION (suppressible) | 55 | Suppressed via 9 targeted `nitpick_ignore` entries with per-anchor citations. |
  | FORWARD-REF-FROM-NEW-GLOSSARY (treated identically) | 19 | Suppressed by the same 9 `nitpick_ignore` entries (suppression is by anchor name, regardless of citing file). |
* **Files touched (in-scope edits):** `docs/source/conf.py` (added
  `nitpick_ignore` block, ~70 lines including comments) and
  `docs/source/glossary.rst` (1 line — `:rst:dir:` → literal markup).
* **Files NOT touched:** all 3 existing foundation prose pages
  (`configuration.rst`, `inference-models.rst`, `operations.rst`),
  `index.rst` (no edits), and the 5 missing foundation pages
  (`introduction.rst`, `getting-started.rst`, `architecture.rst`,
  `service-layer.rst`, `api-reference.rst` — they don't exist on
  disk; authoring them is out of scope).
* **`nitpicky = True` is preserved** — this triage uses targeted
  per-anchor suppression with citation comments rather than weakening
  the global gate.
* **Discovered subtlety, captured for the next maintainer:** the
  Sphinx `nitpick_ignore` tuple type for `:ref:` warnings is
  `('std:ref', '<anchor>')`, **not** `('std:label', '<anchor>')`. Both
  parse without error and Sphinx reports no config issue, but only
  `std:ref` actually suppresses. The first iteration of this fix
  used `std:label` and produced a "successful" rebuild that silently
  left 74 of the 75 suppressible warnings intact. The discovery and
  the rationale are recorded inline in `conf.py` (the comment block
  above `nitpick_ignore`) so the trap is documented at the point
  someone might re-introduce it.

---

## 1. Inputs

### 1.1 Warm-build log (the input to this triage)

The warm-build log was produced fresh at the start of this subtask by
running

```
rm -rf docs/build/html
python -m sphinx -b html docs/source docs/build/html 2>&1 | tee docs/build/build-log-warm.txt
```

against the state of `docs/source/` *as left by the prior subtasks*:

* `conf.py` — as audited in
  `docs/_plan/sphinx_scaffolding_audit.md` (no `nitpick_ignore` set;
  `nitpicky = True`).
* `index.rst` — same audit; 9-page toctree in canonical order.
* `glossary.rst` — as authored by subtask 2 (35,858 bytes, 791 lines,
  including the anchor-map registry at lines 358–688).
* `configuration.rst`, `inference-models.rst`, `operations.rst` —
  three existing foundation pages, unchanged.

The phrase "warm" in the task description appears to refer to "the
*starting-state* build that produces the inventory of warnings we are
triaging" rather than any kind of incremental cache-warm rebuild —
the build was a clean `rm -rf docs/build/html` build, and all
diagnostics fired against fresh output. No prior warm-log artifact
existed on disk, so this triage *generated* the warm log as its first
step. The spelling and counts in this report come from that log.

### 1.2 What is in scope to edit

Per the task constraints:

* **In-scope (NEW files — may edit):** `conf.py`, `index.rst`,
  `glossary.rst`.
* **Out-of-scope (FOUNDATION pages — must NOT modify):**
  `introduction.rst`, `getting-started.rst`, `architecture.rst`,
  `service-layer.rst`, `inference-models.rst`, `configuration.rst`,
  `api-reference.rst`, `operations.rst` — line-by-line audited per
  CONSOLIDATION_NOTES (referenced in the task brief; the
  `CONSOLIDATION_NOTES` artifact itself is not present in this
  working tree, so the constraint is honoured by the task brief
  list).

Of the 8 foundation pages, only 3 (`configuration.rst`,
`inference-models.rst`, `operations.rst`) are present on disk. The
other 5 do not exist and are *forward-referenced* by anchor name
from the existing pages and the glossary — see §1.3.

### 1.3 Anchor-map registry (the truth source for "what should resolve")

The glossary's *Shared Anchor Map* (`glossary.rst:358-688`) lists
every `.. _<name>:` cross-reference target the docset declares or
expects. Two columns matter for this triage:

* **Defined.** 4 anchors that exist *today*: `config-overview`
  (configuration.rst:1), `inf-models` (inference-models.rst:1),
  `infra-overview` (operations.rst:1), `ops-overview`
  (operations.rst:591). Plus `glossary` and `anchor-map` defined on
  the glossary page itself.
* **Forward-referenced (planned).** 9 anchors that are *cited* but
  not yet defined: `introduction`, `getting-started`,
  `gs-feature-flags`, `architecture`, `arch-debug-trace`,
  `svc-moderation`, `api-reference`, `api-etag`, `api-debug-trace`.
  All 9 live on the 5 not-yet-authored pages. (The
  page-top anchor `service-layer` is reserved by the toctree but no
  `:ref:` cite of it appears in any current source — only its
  sub-anchor `svc-moderation` is consumed.)

Every undefined-label warning in the warm log targets exactly one of
those 9 forward-referenced names. This is the precondition that lets
this triage be a *targeted* nitpick suppression rather than a blanket
mask.


---

## 2. Bucket definitions (verbatim per task)

| Bucket | Definition |
|--------|------------|
| **REAL-BUG** | Must-fix; e.g., RST syntax error, broken intra-page ref, duplicate-anchor collision. |
| **EXPECTED-NOW-RESOLVED** | Forward `:ref:` anchors that prior subtasks made resolvable; should be ZERO entries here, listed for confirmation that the anchor chain is sound. |
| **DRIFT** | Anchor-name mismatch between producer and consumer — fix in the NEW file only (`conf.py` / `index.rst` / `glossary.rst`). |
| **PRE-EXISTING-IN-FOUNDATION** | Warning that originates in one of the eight already-authored prose pages — document but do NOT modify the page. |

**One additional bucket required by reality.** The task's four buckets
do not cleanly cover *forward references emitted from the NEW
glossary file* — these aren't bugs (the glossary intentionally
documents them, see `glossary.rst:23-32` and the anchor-map note at
`glossary.rst:383-390`), aren't yet resolved, aren't drift (the
spellings match the anchor map exactly), and aren't in a foundation
page. They are operationally identical to PRE-EXISTING-IN-FOUNDATION
warnings — same anchor names, same suppression mechanism, same future
resolution path — so they are reported under
**FORWARD-REF-FROM-NEW-GLOSSARY** and treated identically. The
distinction is preserved only so the residual handoff to subtask 5
(page authoring) can tell which file emitted which warning.

---

## 3. Bucket totals (warm-build, 81 warnings)

Counts derived by parsing `docs/build/build-log-warm.txt` with a
short Python regex script (`grep`-style); the per-warning detail is
in §5 below.

| Bucket | Count | % of warm total |
|--------|------:|----------------:|
| REAL-BUG (NEW file, fixable in place) | 1 | 1.2% |
| REAL-BUG (FOUNDATION, severe — escalate) | 1 | 1.2% |
| REAL-BUG (root cause out of scope — escalate) | 5 | 6.2% |
| EXPECTED-NOW-RESOLVED | 0 | 0% ✓ |
| DRIFT | 0 | 0% ✓ |
| PRE-EXISTING-IN-FOUNDATION (suppressible) | 55 | 67.9% |
| FORWARD-REF-FROM-NEW-GLOSSARY (suppressible) | 19 | 23.5% |
| **Total** | **81** | **100%** |

**By Sphinx warning code:**

| Code | Count | Source files |
|------|------:|--------------|
| `[ref.ref]` undefined label | 74 | configuration.rst (43), glossary.rst (19), inference-models.rst (7), operations.rst (5) |
| `[toc.not_readable]` toctree to nonexisting doc | 5 | index.rst |
| `[ref.dir]` `:rst:dir:` target not found | 1 | glossary.rst:13 |
| `[docutils]` Unknown target name | 1 | configuration.rst:254 |

**Cross-check on EXPECTED-NOW-RESOLVED = 0.** The task expects this
bucket to be empty as confirmation that the anchor chain is sound
(i.e. that no warning the prior subtasks were *supposed* to have
fixed is still firing). Verified: the 4 currently-defined anchors
(`config-overview`, `inf-models`, `infra-overview`, `ops-overview`,
plus `glossary` and `anchor-map` on the glossary page) all resolve
cleanly under `nitpicky=True` — none of them appears in any
diagnostic line in the warm log. The chain is sound.

**Cross-check on DRIFT = 0.** Every undefined-label name in the warm
log matches an anchor-map entry in `glossary.rst` exactly:

* `introduction` ↔ anchor map row at `glossary.rst:418`
* `getting-started`, `gs-feature-flags` ↔ rows at `glossary.rst:434, 440`
* `architecture`, `arch-debug-trace` ↔ rows at `glossary.rst:456, 462`
* `svc-moderation` ↔ row at `glossary.rst:480`
* `api-reference`, `api-etag`, `api-debug-trace` ↔ rows at
  `glossary.rst:539, 545, 552`

No producer/consumer-side spelling mismatch found.

---

## 4. Fixes applied (in scope)

### 4.1 `glossary.rst:13` — `:rst:dir:`glossary`` → ``\`\`.. glossary::\`\````

**Diagnostic suppressed:**

```
glossary.rst:13: WARNING: rst:dir reference target not found: glossary [ref.dir]
```

**Root cause.** The role `:rst:dir:` is for cross-references to RST
directives that have been *documented* (typically in the Sphinx
docs' own inventory). The `.. glossary::` directive is a built-in
Sphinx construct but the **rst domain** does not register it as a
target locally — it is documented in Sphinx's own reference docs
and gets pulled in only via `intersphinx` against the Sphinx
inventory. Since this docset's `intersphinx_mapping = {}`, the
reference fails. Three fixes were considered:

* **(A)** Add Sphinx to `intersphinx_mapping`. Out of proportion for
  one prose mention; would also expand the build's network surface
  unnecessarily.
* **(B)** Add `glossary` to `nitpick_ignore`. Suppresses the
  symptom without explaining what `:rst:dir:` is doing in
  `glossary.rst:13` in the first place.
* **(C)** Replace the inline role with literal markup
  ``\`\`.. glossary::\`\``` (consistent with how the surrounding
  prose treats other directive/identifier mentions, e.g.
  ``\`\`:term:\`<term>\`\`\``` on the next line).

**Fix chosen: (C).** Cleaner than suppression, no behavioral change
on the rendered page (literal markup renders identically), and
keeps the build cross-reference inventory honest (no spurious entry
in `nitpick_ignore` whose only justification is "we used the
wrong role").

**Diff:**

```rst
-   * The :rst:dir:`glossary` directive below — alphabetised — for
+   * The ``.. glossary::`` directive below — alphabetised — for
```

### 4.2 `conf.py` — added `nitpick_ignore` for 9 forward-referenced anchors

**Diagnostics suppressed (74):** all `[ref.ref]` undefined-label
warnings, regardless of citing file. After this entry, the warm-log
warnings for `'introduction'`, `'getting-started'`,
`'gs-feature-flags'`, `'architecture'`, `'arch-debug-trace'`,
`'svc-moderation'`, `'api-reference'`, `'api-etag'`,
`'api-debug-trace'` no longer fire.

**Discovered subtlety: `std:ref`, not `std:label`.** The `:ref:`
role's xref `type` field is `'ref'` and its domain is `'std'`.
Sphinx builds the suppression key at warning time as
`f'{domain.name}:{typ}'` (see `sphinx/transforms/post_transforms/__init__.py`,
`ReferencesResolver.warn_missing_reference`). That makes the
correct tuple `('std:ref', '<anchor>')`. Using
`('std:label', '<anchor>')` is *plausible-looking* (since `:ref:`
resolves against std-domain *labels*) and Sphinx accepts it without
config error, but it does not match the warning key — every warning
fires anyway. The first iteration of this fix used `std:label`,
rebuilt successfully reporting 80 warnings (only the glossary
`:rst:dir:` fix had taken), and was caught by inspecting the
post-fix log rather than trusting the build's "build succeeded"
message. The discovery is recorded in a multi-line comment block in
`conf.py` directly above the `nitpick_ignore` list so a future
maintainer doesn't repeat it.

**Citation pattern.** Each of the 9 entries carries a per-line
comment naming the *citing files and line numbers* from the warm
log, e.g.:

```python
    # introduction.rst — page-top anchor; cited by configuration.rst:9,
    # 2052, 2111 and glossary.rst:220, 619 (term ``RAI`` and the
    # cross-references list).
    ('std:ref','introduction'),
```

This satisfies the task's "one-line citation comment explaining the
source page and why it's suppressed" requirement, with the citation
ranging across multiple consumers when the anchor is consumed from
multiple files. The intent is that a maintainer reading just
`conf.py` can audit *why* each suppression exists without grepping
the rest of the docset.

**Removal protocol.** When (e.g.) `architecture.rst` is authored
with `.. _architecture:` at the top, the `('std:ref', 'architecture')`
line in `conf.py` should be deleted in the same commit. The
`nitpick_ignore` block is therefore time-bounded by design.


---

## 5. Per-warning triage table (all 81 warm-log diagnostics)

The numbering matches the order in `docs/build/build-log-warm.txt`
(top to bottom). "Action" is one of:

* **fixed-in-place** — the in-source fix in §4.1 resolves it.
* **suppressed-with-citation** — the `nitpick_ignore` block in §4.2
  resolves it; specific entry named.
* **left-as-pre-existing-with-justification** — out of scope to fix
  here; remains in the post-fix log; rationale in §6.
* **no-action-needed** — would not appear in this list, but kept in
  the legend for completeness.

### 5.1 `index.rst:22` — toctree.not_readable (5 entries, #2–#6)

| # | Target document | Bucket | Action |
|---|-----------------|--------|--------|
| 2 | `introduction` | REAL-BUG (root cause out of scope) | left-as-pre-existing — see §6.2 |
| 3 | `getting-started` | REAL-BUG (root cause out of scope) | left-as-pre-existing — see §6.2 |
| 4 | `architecture` | REAL-BUG (root cause out of scope) | left-as-pre-existing — see §6.2 |
| 5 | `service-layer` | REAL-BUG (root cause out of scope) | left-as-pre-existing — see §6.2 |
| 6 | `api-reference` | REAL-BUG (root cause out of scope) | left-as-pre-existing — see §6.2 |

These warnings emit from `index.rst` (a NEW file, in scope to edit)
but the *root cause* is the absence of 5 foundation pages on disk;
authoring those is a separate subtask. `nitpick_ignore` cannot
suppress `[toc.not_readable]` (which is a structural toctree
resolution warning, not a cross-reference warning). The two
in-place options — (a) author/stub the 5 missing pages, (b) remove
the 5 entries from the index toctree — both contradict prior
subtask outputs (the scaffolding spec and audit explicitly chose
the 9-entry toctree; stubbing creates rendered placeholder pages).
Escalated.

### 5.2 `configuration.rst` — 1 docutils ERROR + 43 ref.ref WARNINGs (#1, #7–#49)

| # | Line | Severity | Target | Bucket | Action |
|---|-----:|----------|--------|--------|--------|
| 1 | 254 | ERROR | "startup-time validation" (anonymous-style hyperlink ref with no matching target anywhere in the docset) | REAL-BUG (in FOUNDATION; severe) | left-as-pre-existing — see §6.1 |
| 7 | 9 | WARNING | `introduction` | PRE-EXISTING-IN-FOUNDATION | suppressed via `('std:ref','introduction')` |
| 8 | 9 | WARNING | `getting-started` | PRE-EXISTING-IN-FOUNDATION | suppressed via `('std:ref','getting-started')` |
| 9 | 9 | WARNING | `architecture` | PRE-EXISTING-IN-FOUNDATION | suppressed via `('std:ref','architecture')` |
| 10 | 9 | WARNING | `api-reference` | PRE-EXISTING-IN-FOUNDATION | suppressed via `('std:ref','api-reference')` |
| 11 | 9 | WARNING | `svc-moderation` | PRE-EXISTING-IN-FOUNDATION | suppressed via `('std:ref','svc-moderation')` |
| 12 | 9 | WARNING | `architecture` (second cite on same line) | PRE-EXISTING-IN-FOUNDATION | suppressed via `('std:ref','architecture')` |
| 13 | 24 | WARNING | `architecture` | PRE-EXISTING-IN-FOUNDATION | suppressed via `('std:ref','architecture')` |
| 14 | 24 | WARNING | `api-reference` | PRE-EXISTING-IN-FOUNDATION | suppressed via `('std:ref','api-reference')` |
| 15 | 24 | WARNING | `api-reference` | PRE-EXISTING-IN-FOUNDATION | suppressed via `('std:ref','api-reference')` |
| 16 | 112 | WARNING | `architecture` | PRE-EXISTING-IN-FOUNDATION | suppressed via `('std:ref','architecture')` |
| 17 | 180 | WARNING | `getting-started` | PRE-EXISTING-IN-FOUNDATION | suppressed via `('std:ref','getting-started')` |
| 18 | 189 | WARNING | `getting-started` | PRE-EXISTING-IN-FOUNDATION | suppressed via `('std:ref','getting-started')` |
| 19 | 280 | WARNING | `api-reference` | PRE-EXISTING-IN-FOUNDATION | suppressed via `('std:ref','api-reference')` |
| 20 | 352 | WARNING | `getting-started` | PRE-EXISTING-IN-FOUNDATION | suppressed via `('std:ref','getting-started')` |
| 21 | 634 | WARNING | `api-reference` | PRE-EXISTING-IN-FOUNDATION | suppressed via `('std:ref','api-reference')` |
| 22 | 634 | WARNING | `getting-started` | PRE-EXISTING-IN-FOUNDATION | suppressed via `('std:ref','getting-started')` |
| 23 | 869 | WARNING | `svc-moderation` | PRE-EXISTING-IN-FOUNDATION | suppressed via `('std:ref','svc-moderation')` |
| 24 | 884 | WARNING | `api-reference` | PRE-EXISTING-IN-FOUNDATION | suppressed via `('std:ref','api-reference')` |
| 25 | 1068 | WARNING | `api-etag` | PRE-EXISTING-IN-FOUNDATION | suppressed via `('std:ref','api-etag')` |
| 26 | 1077 | WARNING | `architecture` | PRE-EXISTING-IN-FOUNDATION | suppressed via `('std:ref','architecture')` |
| 27 | 1175 | WARNING | `architecture` | PRE-EXISTING-IN-FOUNDATION | suppressed via `('std:ref','architecture')` |
| 28 | 1175 | WARNING | `api-reference` | PRE-EXISTING-IN-FOUNDATION | suppressed via `('std:ref','api-reference')` |
| 29 | 1186 | WARNING | `architecture` | PRE-EXISTING-IN-FOUNDATION | suppressed via `('std:ref','architecture')` |
| 30 | 1227 | WARNING | `api-reference` | PRE-EXISTING-IN-FOUNDATION | suppressed via `('std:ref','api-reference')` |
| 31 | 1227 | WARNING | `svc-moderation` | PRE-EXISTING-IN-FOUNDATION | suppressed via `('std:ref','svc-moderation')` |
| 32 | 1361 | WARNING | `api-reference` | PRE-EXISTING-IN-FOUNDATION | suppressed via `('std:ref','api-reference')` |
| 33 | 1437 | WARNING | `architecture` | PRE-EXISTING-IN-FOUNDATION | suppressed via `('std:ref','architecture')` |
| 34 | 1638 | WARNING | `api-reference` | PRE-EXISTING-IN-FOUNDATION | suppressed via `('std:ref','api-reference')` |
| 35 | 1703 | WARNING | `architecture` | PRE-EXISTING-IN-FOUNDATION | suppressed via `('std:ref','architecture')` |
| 36 | 1740 | WARNING | `api-reference` | PRE-EXISTING-IN-FOUNDATION | suppressed via `('std:ref','api-reference')` |
| 37 | 1770 | WARNING | `svc-moderation` | PRE-EXISTING-IN-FOUNDATION | suppressed via `('std:ref','svc-moderation')` |
| 38 | 1840 | WARNING | `api-reference` | PRE-EXISTING-IN-FOUNDATION | suppressed via `('std:ref','api-reference')` |
| 39 | 1897 | WARNING | `svc-moderation` | PRE-EXISTING-IN-FOUNDATION | suppressed via `('std:ref','svc-moderation')` |
| 40 | 2052 | WARNING | `introduction` | PRE-EXISTING-IN-FOUNDATION | suppressed via `('std:ref','introduction')` |
| 41 | 2054 | WARNING | `getting-started` | PRE-EXISTING-IN-FOUNDATION | suppressed via `('std:ref','getting-started')` |
| 42 | 2054 | WARNING | `gs-feature-flags` | PRE-EXISTING-IN-FOUNDATION | suppressed via `('std:ref','gs-feature-flags')` |
| 43 | 2058 | WARNING | `architecture` | PRE-EXISTING-IN-FOUNDATION | suppressed via `('std:ref','architecture')` |
| 44 | 2062 | WARNING | `api-reference` | PRE-EXISTING-IN-FOUNDATION | suppressed via `('std:ref','api-reference')` |
| 45 | 2066 | WARNING | `api-etag` | PRE-EXISTING-IN-FOUNDATION | suppressed via `('std:ref','api-etag')` |
| 46 | 2078 | WARNING | `svc-moderation` | PRE-EXISTING-IN-FOUNDATION | suppressed via `('std:ref','svc-moderation')` |
| 47 | 2111 | WARNING | `introduction` | PRE-EXISTING-IN-FOUNDATION | suppressed via `('std:ref','introduction')` |
| 48 | 2111 | WARNING | `getting-started` | PRE-EXISTING-IN-FOUNDATION | suppressed via `('std:ref','getting-started')` |
| 49 | 2111 | WARNING | `architecture` | PRE-EXISTING-IN-FOUNDATION | suppressed via `('std:ref','architecture')` |

### 5.3 `glossary.rst` — 1 ref.dir + 19 ref.ref WARNINGs (#50–#69)

| # | Line | Target | Bucket | Action |
|---|-----:|--------|--------|--------|
| 50 | 13 | `glossary` (`:rst:dir:` role) | REAL-BUG (NEW file) | **fixed-in-place** — replaced inline role with literal markup ``\`\`.. glossary::\`\``` (see §4.1) |
| 51 | 76 | `api-reference` | FORWARD-REF-FROM-NEW-GLOSSARY | suppressed via `('std:ref','api-reference')` |
| 52 | 76 | `api-debug-trace` | FORWARD-REF-FROM-NEW-GLOSSARY | suppressed via `('std:ref','api-debug-trace')` |
| 53 | 76 | `architecture` | FORWARD-REF-FROM-NEW-GLOSSARY | suppressed via `('std:ref','architecture')` |
| 54 | 76 | `arch-debug-trace` | FORWARD-REF-FROM-NEW-GLOSSARY | suppressed via `('std:ref','arch-debug-trace')` |
| 55 | 89 | `api-etag` | FORWARD-REF-FROM-NEW-GLOSSARY | suppressed via `('std:ref','api-etag')` |
| 56 | 122 | `svc-moderation` | FORWARD-REF-FROM-NEW-GLOSSARY | suppressed via `('std:ref','svc-moderation')` |
| 57 | 220 | `introduction` | FORWARD-REF-FROM-NEW-GLOSSARY | suppressed via `('std:ref','introduction')` |
| 58 | 619 | `introduction` | FORWARD-REF-FROM-NEW-GLOSSARY | suppressed via `('std:ref','introduction')` |
| 59 | 620 | `getting-started` | FORWARD-REF-FROM-NEW-GLOSSARY | suppressed via `('std:ref','getting-started')` |
| 60 | 620 | `gs-feature-flags` | FORWARD-REF-FROM-NEW-GLOSSARY | suppressed via `('std:ref','gs-feature-flags')` |
| 61 | 624 | `architecture` | FORWARD-REF-FROM-NEW-GLOSSARY | suppressed via `('std:ref','architecture')` |
| 62 | 624 | `arch-debug-trace` | FORWARD-REF-FROM-NEW-GLOSSARY | suppressed via `('std:ref','arch-debug-trace')` |
| 63 | 628 | `svc-moderation` | FORWARD-REF-FROM-NEW-GLOSSARY | suppressed via `('std:ref','svc-moderation')` |
| 64 | 638 | `api-reference` | FORWARD-REF-FROM-NEW-GLOSSARY | suppressed via `('std:ref','api-reference')` |
| 65 | 638 | `api-debug-trace` | FORWARD-REF-FROM-NEW-GLOSSARY | suppressed via `('std:ref','api-debug-trace')` |
| 66 | 638 | `api-etag` | FORWARD-REF-FROM-NEW-GLOSSARY | suppressed via `('std:ref','api-etag')` |
| 67 | 701 | `architecture` | FORWARD-REF-FROM-NEW-GLOSSARY | suppressed via `('std:ref','architecture')` |
| 68 | 701 | `api-reference` | FORWARD-REF-FROM-NEW-GLOSSARY | suppressed via `('std:ref','api-reference')` |
| 69 | 747 | `architecture` | FORWARD-REF-FROM-NEW-GLOSSARY | suppressed via `('std:ref','architecture')` |

### 5.4 `inference-models.rst` — 7 ref.ref WARNINGs (#70–#76)

| # | Line | Target | Bucket | Action |
|---|-----:|--------|--------|--------|
| 70 | 9 | `architecture` | PRE-EXISTING-IN-FOUNDATION | suppressed via `('std:ref','architecture')` |
| 71 | 9 | `svc-moderation` | PRE-EXISTING-IN-FOUNDATION | suppressed via `('std:ref','svc-moderation')` |
| 72 | 80 | `architecture` | PRE-EXISTING-IN-FOUNDATION | suppressed via `('std:ref','architecture')` |
| 73 | 476 | `svc-moderation` | PRE-EXISTING-IN-FOUNDATION | suppressed via `('std:ref','svc-moderation')` |
| 74 | 1004 | `architecture` | PRE-EXISTING-IN-FOUNDATION | suppressed via `('std:ref','architecture')` |
| 75 | 1131 | `architecture` | PRE-EXISTING-IN-FOUNDATION | suppressed via `('std:ref','architecture')` |
| 76 | 1135 | `svc-moderation` | PRE-EXISTING-IN-FOUNDATION | suppressed via `('std:ref','svc-moderation')` |

### 5.5 `operations.rst` — 5 ref.ref WARNINGs (#77–#81)

| # | Line | Target | Bucket | Action |
|---|-----:|--------|--------|--------|
| 77 | 16 | `getting-started` | PRE-EXISTING-IN-FOUNDATION | suppressed via `('std:ref','getting-started')` |
| 78 | 16 | `architecture` | PRE-EXISTING-IN-FOUNDATION | suppressed via `('std:ref','architecture')` |
| 79 | 405 | `getting-started` | PRE-EXISTING-IN-FOUNDATION | suppressed via `('std:ref','getting-started')` |
| 80 | 1004 | `getting-started` | PRE-EXISTING-IN-FOUNDATION | suppressed via `('std:ref','getting-started')` |
| 81 | 1007 | `architecture` | PRE-EXISTING-IN-FOUNDATION | suppressed via `('std:ref','architecture')` |

### 5.6 Per-anchor cite distribution (sanity check)

Aggregating the suppressible warnings (entries #7–#49 minus #50,
plus #51–#81; i.e. all 74 ref.ref) by anchor name:

| Anchor | Cites (configuration / glossary / inference-models / operations) | Total |
|--------|------------------------------------------------------------------|------:|
| `architecture` | 11 / 4 / 4 / 2 | 21 |
| `api-reference` | 13 / 3 / 0 / 0 | 16 |
| `getting-started` | 7 / 1 / 0 / 3 | 11 |
| `svc-moderation` | 6 / 2 / 3 / 0 | 11 |
| `introduction` | 3 / 2 / 0 / 0 | 5 |
| `api-etag` | 2 / 2 / 0 / 0 | 4 |
| `gs-feature-flags` | 1 / 1 / 0 / 0 | 2 |
| `api-debug-trace` | 0 / 2 / 0 / 0 | 2 |
| `arch-debug-trace` | 0 / 2 / 0 / 0 | 2 |
| **Total** | **43 / 19 / 7 / 5** | **74** |

Per-file totals (43 / 19 / 7 / 5) match the per-file warning counts
in §5.2–§5.5 minus the two non-`ref.ref` rows (the docutils ERROR
and the `:rst:dir:` warning), confirming the table accounts for
every `[ref.ref]` warning exactly once.

---

## 6. Residual warnings — escalations (the 6 in the post-fix log)

The post-fix build log (`docs/build/build-log-after-fix.txt`)
reports 6 diagnostics. Each is documented below with rationale for
why it was *not* suppressed at this stage.

### 6.1 `configuration.rst:254` — docutils ERROR `Unknown target name: "startup-time validation"`

**Why this exists.** The author of the configuration page wrote:

```rst
- **Validated at startup** — see `Startup-time validation`_
  below. In local mode with ``NO_ASAP_SIGNER=true`` it is set to
  a ``unittest.mock.Mock(JWTAuthSigner)``.
```

The trailing underscore on ``\`Startup-time validation\`_`` is
docutils' *anonymous-style implicit hyperlink* syntax — it tells
docutils "look elsewhere on this page (or in this docset) for a
section heading or `.. _Startup-time validation:` anchor with that
display name". A grep over the entire `docs/source/` tree for the
literal string "Startup-time validation" returns *one* hit: the
`configuration.rst:254` reference itself. There is no defining
section, no `.. _<...>:` target with that name, anywhere.

**Why suppression is not appropriate.**

* `nitpick_ignore` cannot suppress this. The diagnostic is emitted
  by docutils (`[docutils]` warning code), not by Sphinx's
  cross-reference resolver. `nitpick_ignore` only filters Sphinx's
  `warn_missing_reference` path — see `sphinx/transforms/post_transforms/__init__.py`.
  Docutils-level errors fire earlier, in the parse phase, with a
  different machinery.
* `suppress_warnings` (Sphinx config) likewise targets Sphinx
  warning categories, not docutils errors.
* Adding a `.. _Startup-time validation:` anchor to *another* file
  (e.g. `glossary.rst`) would resolve the docutils ERROR by
  side-effect, but it is a hack — the real defect is that
  configuration.rst promises a section that was never written.
  Side-effect resolution would also create a misleading rendered
  link (clicking "Startup-time validation" in configuration.rst
  would land the reader on the glossary page rather than on the
  section the author intended).

**Why fixing in `configuration.rst` is forbidden.** The task's
constraint (i): "NEVER modify [...] configuration.rst, [...] —
these are line-by-line audited per CONSOLIDATION_NOTES." Editing
line 254 to either delete the broken reference or add a defining
section in this file violates that constraint.

**Escalation.** Per the task's escalation rule (constraint iii):
"if a warning is severe enough that suppression is unacceptable,
escalate by flagging in the triage report rather than silently
editing a foundation page". This warning is escalated.
**Recommended owner:** the next configuration.rst editorial pass
(or a re-audit of configuration.rst) should either (a) author the
missing "Startup-time validation" section in configuration.rst —
the surrounding content at lines 252–256 already alludes to ASAP
signer validation, so a 5–10 line subsection on the
`config.asap_signer` validity check is the natural target — or
(b) rephrase line 254 to remove the orphan link.

### 6.2 `index.rst:22` — five `toctree contains reference to nonexisting document` warnings

**Why this exists.** The 9-page toctree in `index.rst` references
five basenames whose corresponding `.rst` files do not exist on
disk: `introduction`, `getting-started`, `architecture`,
`service-layer`, `api-reference`. The scaffolding-audit subtask
(`docs/_plan/sphinx_scaffolding_audit.md`) explicitly acknowledged
this gap (§4) and the glossary's lead note acknowledges it
(`glossary.rst:23-32`).

**Why suppression is not appropriate.**

* `nitpick_ignore` does not cover `[toc.not_readable]` warnings —
  toctree resolution errors are emitted by
  `TocTreeCollector` / `Toctree` directive code, not by the
  cross-reference machinery, and they fire regardless of
  `nitpicky`.
* `suppress_warnings = ['toc.not_readable']` *would* mute these
  in Sphinx config, but doing so would mask any *real* future
  toctree typo in `index.rst` — exactly the kind of "weakening
  the global gate to mass-suppress" the task's constraint (ii)
  forbids.
* Removing the 5 entries from the toctree silences the warnings
  but contradicts the scaffolding spec (which the audit verified
  is followed exactly) and breaks the 9-page reading order
  promise made in the hero paragraphs at `index.rst:5-20`.

**Why the fix is out of scope.** The fix is to author the 5
missing pages (each with a `.. _<basename>:` anchor at the top
plus the page-top section). That is a multi-page authoring task
covered by a separate subtask graph — the scaffolding audit (§4
recommendation) explicitly defers this to the page-authoring
subtasks for `introduction`/`getting-started`/`architecture`/
`service-layer`/`api-reference`.

**Escalation.** All 5 warnings are escalated to the page-authoring
subtask owners. Each warning will resolve *automatically* the
moment the named `.rst` file lands on disk — no further triage
work is needed here.

**Cross-link with §4.2.** Note that the 5 toctree warnings cite
the same file basenames (and therefore, by extension, the same 5
not-yet-authored pages) that host the 9 forward-referenced anchors
suppressed in §4.2. When (e.g.) `architecture.rst` lands, *both*
(a) its toctree warning here and (b) the
`('std:ref', 'architecture')` and `('std:ref', 'arch-debug-trace')`
entries in `conf.py` should disappear in the same commit. The two
escalations have the same root cause and the same resolution path.

---

## 7. Files touched / not touched

### 7.1 Touched (in-scope)

| File | Change | Lines |
|------|--------|------:|
| `docs/source/conf.py` | Added `nitpick_ignore` block (9 entries) with citation comments and a multi-paragraph rationale block above the list, including the `std:ref`-vs-`std:label` discovery note. | +66 (52 → 122) |
| `docs/source/glossary.rst` | One-line edit: replaced `:rst:dir:`glossary`` with ``\`\`.. glossary::\`\``` literal markup at line 13. | 0 net (one substitution) |

### 7.2 Untouched

* `docs/source/index.rst` — no edit. The 5 toctree entries to
  not-yet-authored pages are intentional per the scaffolding spec
  and cannot be fixed by editing `index.rst` without contradicting
  upstream subtasks (see §6.2).
* `docs/source/configuration.rst` — out of scope to modify.
  Contains 1 docutils ERROR + 43 nitpick warnings (all suppressed
  via `nitpick_ignore`).
* `docs/source/inference-models.rst` — out of scope to modify.
  Contains 7 nitpick warnings (all suppressed via
  `nitpick_ignore`).
* `docs/source/operations.rst` — out of scope to modify. Contains
  5 nitpick warnings (all suppressed via `nitpick_ignore`).
* `docs/source/introduction.rst`, `docs/source/getting-started.rst`,
  `docs/source/architecture.rst`, `docs/source/service-layer.rst`,
  `docs/source/api-reference.rst` — *do not exist on disk*. Out of
  scope to author here; their absence drives the 5 toctree
  warnings and the upstream forward-reference set.
* `docs/source/_static/.gitkeep` — unchanged; no static assets
  needed.

### 7.3 New artifacts written by this subtask

| Path | Purpose | Size |
|------|---------|-----:|
| `docs/build/build-log-warm.txt` | Verbatim warm-build log (ANSI-stripped); the input to this triage. | ~15 KB |
| `docs/build/build-log-after-fix.txt` | Verbatim post-fix build log; demonstrates the 81 → 6 reduction. | ~3 KB |
| `docs/build/html/...` | Built HTML site (not part of the deliverable, but populated as a side-effect of the post-fix `sphinx-build` invocation). | ~varies |
| `docs/_plan/sphinx_warning_triage_report.md` | This document. | ~30 KB |

---

## 8. Post-fix verification

### 8.1 Re-build invocation

```
rm -rf docs/build/html
python -m sphinx -b html docs/source docs/build/html 2>&1 \
  | tee docs/build/build-log-after-fix.txt
```

This is the literal sequence the spec requested
(`uv run sphinx-build -b html docs/source docs/build/html` after
`rm -rf docs/build/html`), with `python -m sphinx` standing in for
`uv run sphinx-build` because `uv` is not installed in the build
environment. The Sphinx CLI invocation and behavior are identical.

### 8.2 Build summary

* **Build status:** `build succeeded, 6 warnings.`
* **Build exit code:** 0
* **HTML output:** `docs/build/html/` (5 pages: `configuration`,
  `glossary`, `index`, `inference-models`, `operations`).

### 8.3 Warning delta (warm → post-fix)

| Diagnostic class | Warm | Post-fix | Δ | How resolved |
|------------------|-----:|---------:|--:|--------------|
| `[docutils]` ERROR | 1 | 1 | 0 | Cannot suppress; escalated (§6.1) |
| `[toc.not_readable]` WARNING | 5 | 5 | 0 | Cannot suppress; escalated (§6.2) |
| `[ref.dir]` WARNING (`:rst:dir:` glossary) | 1 | 0 | −1 | Fixed in place (§4.1) |
| `[ref.ref]` WARNING (undefined label) | 74 | 0 | −74 | Suppressed via 9-entry `nitpick_ignore` (§4.2) |
| **Total** | **81** | **6** | **−75** | 92.6% reduction |

### 8.4 Independent re-check

Running the parser script over the post-fix log
(`docs/build/build-log-after-fix.txt`) yields exactly the 6
escalation entries documented in §6, with no additional warnings.
No new diagnostics were introduced by the in-scope edits.

```
$ python -c "import re; raw=open('docs/build/build-log-after-fix.txt').read(); print(sum(1 for l in raw.splitlines() if ' WARNING:' in l or ' ERROR:' in l))"
6
```

### 8.5 Negative check: nitpicky still gates

A spot-check that `nitpicky` is *not* weakened: introducing a
typo'd `:ref:`introduxtion`` (mis-spelt) into any page should still
fire under the post-fix config. Verified by inspection of `conf.py`:
`nitpicky = True` is unchanged at line 52, and the
`nitpick_ignore` list contains only the 9 forward-referenced
anchor names — no wildcard, no `nitpick_ignore_regex`. Any
mis-spelt anchor name not on the 9-element list will still raise a
warning.

---

## 9. Handoff and forward-looking notes

### 9.1 When to remove each `nitpick_ignore` entry

The `nitpick_ignore` list is *time-bounded by design*. The
removal trigger for each entry is the authoring of the
corresponding page or sub-anchor:

| `nitpick_ignore` entry | Remove when... |
|------------------------|----------------|
| `('std:ref', 'introduction')` | `introduction.rst` lands with `.. _introduction:` at the top. |
| `('std:ref', 'getting-started')` | `getting-started.rst` lands with `.. _getting-started:` at the top. |
| `('std:ref', 'gs-feature-flags')` | The relevant section in `getting-started.rst` lands with `.. _gs-feature-flags:` directive. |
| `('std:ref', 'architecture')` | `architecture.rst` lands with `.. _architecture:` at the top. |
| `('std:ref', 'arch-debug-trace')` | The relevant section in `architecture.rst` lands with `.. _arch-debug-trace:` directive. |
| `('std:ref', 'svc-moderation')` | `service-layer.rst` lands with `.. _svc-moderation:` directive at the page-top section (not necessarily the page-top label, since the page-top anchor itself is unused). |
| `('std:ref', 'api-reference')` | `api-reference.rst` lands with `.. _api-reference:` at the top. |
| `('std:ref', 'api-etag')` | The relevant section in `api-reference.rst` lands with `.. _api-etag:` directive. |
| `('std:ref', 'api-debug-trace')` | The relevant section in `api-reference.rst` lands with `.. _api-debug-trace:` directive. |

The same commit that authors the page should delete the
corresponding `nitpick_ignore` line(s); leaving stale entries
weakens the gate over time and creates the risk that a future
typo of (e.g.) `:ref:`api-etag`` aimed at a *different* anchor
would be silently swallowed.

### 9.2 What to verify after each foundation-page authoring subtask

1. Re-run the post-fix build command (§8.1) on a clean tree.
2. Confirm the warning count dropped by at least the number of
   `nitpick_ignore` entries removed in that commit.
3. If the warning count did not drop as expected, grep for
   `:ref:`<name>`` across `docs/source/` to confirm the new
   anchor name on the new page matches the consumer-side spelling
   that prior pages used.
4. Confirm the corresponding `[toc.not_readable]` warning for the
   new page disappeared from `docs/build/build-log-after-fix.txt`.

### 9.3 What to do if a *new* warning appears post-this-subtask

If a fresh `:ref:` warning appears in a future build:

* If the target name is one of the 9 currently in
  `nitpick_ignore`: the warning was *already* suppressible — this
  is unexpected, investigate (could be a Sphinx version difference
  in tuple-key matching).
* If the target name is *not* in `nitpick_ignore`: this is a real
  drift or typo. Do **not** add a new `nitpick_ignore` entry
  without first confirming the spelling matches the glossary's
  anchor map (`glossary.rst:358-688`). Adding a new entry without
  an anchor-map row is the failure mode this triage is designed
  to prevent.

### 9.4 Open questions and known unknowns

* **The docutils ERROR at `configuration.rst:254`** is the most
  immediate follow-up. It is in a foundation page that this
  subtask cannot edit, so the resolution is: a re-audit of
  configuration.rst (or its CONSOLIDATION_NOTES owner) should
  either author the "Startup-time validation" section the
  reference promises, or rephrase the line to remove the orphan
  link. Until then the post-fix log retains 1 docutils ERROR.
* **The 5 missing foundation pages.** Independent of this
  triage, those 5 pages are the largest open gap in the docset
  build state. Authoring them resolves both (a) the 5 toctree
  warnings here and (b) all 9 currently-suppressed
  forward-referenced anchors. Tracking owner: the page-authoring
  subtask graph for `introduction`/`getting-started`/
  `architecture`/`service-layer`/`api-reference`.
* **`uv` not installed locally.** The build invocation used
  `python -m sphinx` instead of `uv run sphinx-build`. If a CI
  pipeline expects `uv`, the CI environment must install it
  (`pip install uv` or equivalent). The Sphinx output is
  identical.
* **`autosectionlabel_prefix_document = True`** means *autogen*
  section labels are document-prefixed (e.g.
  `inference-models:Wire-protocol clients`). None of the warnings
  in either log target an autogen label, so the
  `autosectionlabel_prefix_document` setting does not interact
  with this triage. It is mentioned only so a future maintainer
  searching for "section label" docs is reminded of the
  prefixing.

### 9.5 Consistency with prior subtask deliverables

* Aligns with `docs/_plan/sphinx_scaffolding_audit.md` — that
  audit predicted (§7) "five `toctree contains reference to
  nonexisting document` warnings" and "numerous `nitpicky`-mode
  `:ref:` warnings for forward references". The warm log produced
  exactly those signals plus one additional `[docutils]` ERROR
  and one `[ref.dir]` warning — both of which the audit could not
  have anticipated without running the build itself.
* Aligns with `glossary.rst:358-688` (the anchor map) — every
  suppressed anchor has a corresponding "forward-referenced —
  target page not yet authored" row in that map. No suppression
  here lacks anchor-map backing.
* Preserves `nitpicky = True` in `conf.py:52` — the constraint
  (ii) of the task is honoured.
* Honours the "do not modify foundation pages" constraint — the 3
  existing foundation pages are byte-identical pre/post triage
  (verifiable by a per-file hash; not committed here because
  `docs/source/` is currently untracked in git).

---

## 10. Appendix — exact build commands and reproducibility

To reproduce this triage end-to-end from a clean checkout of
`docs/source/` (in the state left by subtasks 1 and 2, *before*
this triage):

```bash
# 1. Generate the warm log.
mkdir -p docs/build && rm -rf docs/build/html
python -m sphinx -b html docs/source docs/build/html 2>&1 \
  | tee docs/build/build-log-warm.txt
# Expected: build succeeded, 81 warnings.

# 2. Apply fixes (this triage's edits to conf.py + glossary.rst).

# 3. Re-build clean.
rm -rf docs/build/html
python -m sphinx -b html docs/source docs/build/html 2>&1 \
  | tee docs/build/build-log-after-fix.txt
# Expected: build succeeded, 6 warnings.

# 4. Verify the residual count.
python -c "import re; raw=open('docs/build/build-log-after-fix.txt').read(); print(sum(1 for l in raw.splitlines() if ' WARNING:' in l or ' ERROR:' in l))"
# Expected: 6
```

Both logs in `docs/build/` are ANSI-stripped (the original Sphinx
output uses ANSI color codes when stdout is a TTY; `tee` to a file
preserves them, so the logs are post-processed once via
`re.sub(r'\x1b\[[0-9;]*[mK]', '', ...)` to keep them grep-friendly
for downstream tools).
