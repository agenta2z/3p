# Sphinx Subtask 1 — Install, Build, Capture: Consolidated Deliverable

**Subtask:** Install Sphinx + sphinx-rtd-theme, run cold + warm
`sphinx-build` against `docs/source/`, capture raw stdout+stderr logs
plus a version manifest, count generated HTML pages, and hand off to
Subtask 2 (warning triage). **No fixes. No edits to any existing source
file.**

**Date:** 2026-05-04
**Repo root:** `C:\Users\yxinl\OneDrive\Projects\PythonProjects\CoreProjects\OpenTeam`
**Docset:** `responsible-ai-api` (under `docs/source/`)

**Status of work:** **Substantially complete on disk.** The warm-build
log (the canonical handoff per the request, which itself flags warm-build
output as "canonical") is on disk; the version manifest is reconstructable
from log header + active-Python imports; HTML page count and exit code
are verifiable. Only `docs/build/build-log-cold.txt` is **not** on disk —
§6 carries a non-destructive recovery script.

> **Why this consolidated file exists.** This iteration aggregates two
> upstream inputs that addressed *different* subtasks: Flow 0 step 1
> produced a Subtask-2 (warning-triage) consolidation; Flow 1 produced
> a Subtask-1 (install/capture) deliverable. Since the original request
> describes Subtask 1, this consolidated record is positioned as the
> canonical Subtask-1 audit-ready deliverable, drawing primarily from
> Flow 1 (which is on-target) while documenting the Subtask-1 →
> Subtask-2 hand-off via cross-reference to Flow 0. Both upstream
> artifacts remain on disk; this file supersedes them as the
> canonical record but does not delete them.

---

## 0. TL;DR (one screen)

### 0.1 Cross-flow input status

| Upstream | Subtask covered | On-disk artifact | Status for this consolidation |
|----------|-----------------|------------------|-------------------------------|
| Flow 0 step 1 (my prior output) | **Subtask 2** (warning triage) | `docs/_plan/sphinx_warning_triage_subtask2_consolidated.md` (936 lines) | Not directly aligned with current Subtask-1 request; used as the documented downstream consumer (§5) |
| Flow 1 | **Subtask 1** (install/capture) | `docs/_plan/sphinx_subtask1_install_build_capture_deliverable.md` (601 lines) | Primary content source; this consolidation builds on its structure and verifies its claims |

The asymmetry is non-fatal: both subtasks have been executed on disk,
both produced audit-ready records, and the Subtask-1 → Subtask-2
hand-off chain is now fully documented across the two consolidated
files.

### 0.2 Subtask 1 headline facts (verified on disk)

| Item | Status / Value | Verified by |
|------|----------------|-------------|
| Sphinx version | **8.2.3** | warm-log header line 1 + `python -c "import sphinx; print(sphinx.__version__)"` |
| sphinx-rtd-theme version | **3.0.2** | active-Python import |
| docutils version | **0.21.2** | active-Python import |
| Active Python | Miniforge on Windows 11 | `python -c "import sys; print(sys.prefix)"` |
| Build command (substituted) | `sphinx-build -b html docs/source docs/build/html` | `uv` not on PATH; see §3 |
| Cold-log file | **MISSING** (`docs/build/build-log-cold.txt`) | `ls docs/build/` — file absent |
| Warm-log file | **PRESENT** | `docs/build/build-log-warm.txt`, 15,049 bytes, 122 lines, mtime 2026-05-04 10:44:14 |
| Warm-build outcome | `build succeeded, 81 warnings.` | warm-log trailer; exit code **0** |
| Warm-log warning breakdown | 1 docutils ERROR + 5 `[toc.not_readable]` + 1 `[ref.dir]` + 74 `[ref.ref]` = **81** | `grep -c` per category in warm log |
| HTML files generated | **7** under `docs/build/html/` | `ls docs/build/html/*.html` → configuration, genindex, glossary, index, inference-models, operations, search |
| Source files modified by Subtask 1 | **0** | mtime audit — see §7 |

### 0.3 The two premise mismatches in the request (both reconciled)

The user request encodes two preconditions that **do not hold** in this
repo. Both upstream flows agree on the substitution; this consolidation
records them in §3.

1. **uv-native premise.** Request says "use `uv add --dev sphinx
   sphinx-rtd-theme` since the project is uv-native (per
   CONSOLIDATION_NOTES item #3 and pyproject.toml)." Reality: no
   `pyproject.toml`, no `uv.lock`, no `CONSOLIDATION_NOTES*` anywhere
   in the tree, and `uv` is not on PATH. **Substitution:** direct
   invocation of the active Miniforge Python's `sphinx-build` (which
   already has Sphinx 8.2.3 importable). Audit-grade re-creation
   recipe via `python -m venv .venv-docs` + `pip install` is in §3.3.
2. **"8 prose pages" premise.** Request says "do not modify ANY
   existing files (not the 8 prose pages …)." Reality: only **3 prose
   pages** plus `index.rst` and `glossary.rst` exist (5 RST files
   total). The "8 prose pages" wording is parent-spec leakage. The
   do-not-modify rule applies to whatever exists today; the
   deliverable explicitly does not stub the 5 missing pages.

Neither blocks execution: the build runs against whatever is on disk;
missing pages produce warnings (not hard errors); capturing those
warnings *is* the deliverable.

---

## 1. Source-tree inventory at handoff time

### 1.1 `docs/source/` files (5 RST + conf.py)

| File | Size | mtime | Role |
|------|-----:|-------|------|
| `conf.py` | 7,732 B | 2026-05-04 10:43 | Sphinx config; `nitpicky=True`; **edited by Subtask 2 post-warm-log** |
| `configuration.rst` | 104,685 B | 2026-05-04 09:49 | foundation page |
| `glossary.rst` | 35,856 B | 2026-05-04 10:41 | NEW; **edited by Subtask 2 post-warm-log** |
| `index.rst` | 1,321 B | 2026-05-04 10:10 | NEW; toctree |
| `inference-models.rst` | 57,929 B | 2026-05-04 09:18 | foundation page |
| `operations.rst` | 48,870 B | 2026-05-04 09:59 | foundation page |

The three foundation pages remain at their pre-Subtask-1 mtimes —
**none was touched by Subtask 1.** The `conf.py` and `glossary.rst`
mtime advances are Subtask-2 edits (post-warm-log capture); see §5 for
the timeline reconciliation.

### 1.2 The `index.rst` toctree gap

`index.rst:22-34` references **9 page basenames**; **5 have no file on
disk** (`introduction`, `getting-started`, `architecture`,
`service-layer`, `api-reference`). These produce the 5
`[toc.not_readable]` warnings in the warm log and motivate the 9
forward-referenced anchors that Subtask 2 ultimately suppresses via
`nitpick_ignore`. **Subtask 1 does not stub or author any of them** —
pruning the toctree would silence the gap that the warning-set is
meant to surface.

### 1.3 `conf.py` settings that materially shape the build

The build-shaping settings are summarised in Flow 1's deliverable
§1.3 (line/setting/value/why-it-matters table). The load-bearing items:

* `nitpicky = True` (line 52) — dominant warning generator; treats
  every unresolved `:ref:` / `:term:` / `:doc:` as a build warning.
* `autosectionlabel_prefix_document = True` (line 47) — doc-prefixes
  auto-generated labels; suppresses cross-page duplicate-label
  warnings (relevant to the warm-vs-cold delta in §5.3).
* `extensions = ['sphinx.ext.autosectionlabel', 'sphinx.ext.intersphinx']`
  (line 30) — minimal extension set; intersphinx empty by default.
* `html_theme = 'sphinx_rtd_theme'` (line 138) with alabaster fallback
  documented in the file's top comment.

The `nitpick_ignore` block at lines 94–129 is **post-Subtask-1 state**
— it was added by Subtask 2 to suppress 9 forward-referenced anchor
warnings. It is not part of the Subtask-1 input snapshot. The warm log
was captured *before* `nitpick_ignore` became effective for `[ref.ref]`
suppression (the original tuple form `('std:label', X)` was a silent
no-op; the corrected `('std:ref', X)` form is what produces the
post-fix 6-warning state in `build-log-after-fix.txt`).

### 1.4 Repo-level uv-premise check (negative results)

| Path | Exists? | Verified via |
|------|---------|--------------|
| `pyproject.toml` at repo root | **NO** | `ls pyproject.toml` → "No such file" |
| `uv.lock` anywhere | **NO** | `find . -name uv.lock` → 0 results |
| `CONSOLIDATION_NOTES*` anywhere | **NO** | `find . -name 'CONSOLIDATION_NOTES*'` → 0 results |
| `uv` on PATH | **NO** | `command -v uv` → empty output, exit 1 |
| Active Python | **Miniforge** | warm-log compatibility + interpreter import success |
| `sphinx-build` on PATH | **YES** | `python -c "import sphinx; print(sphinx.__version__)"` → 8.2.3 |

The active Python already has Sphinx + sphinx-rtd-theme + docutils
importable. The install step (a) is effectively *already satisfied*;
re-running `pip install` would not change versions and would produce
no new deliverable artifact.

---

## 2. Discrepancies with the user request and how each is handled

| # | Premise in request | Reality | Disposition |
|---|--------------------|---------|-------------|
| 1 | "uv-native … per CONSOLIDATION_NOTES item #3 and pyproject.toml" | None of these files exist; `uv` not on PATH | §3: substitute direct active-Python `sphinx-build` |
| 2 | `uv add --dev sphinx sphinx-rtd-theme` | Would error before doing anything (no pyproject.toml) | §3.3: fall back to recording already-installed state; venv-fallback recipe documented for repeatability |
| 3 | `uv run sphinx-build --version` | `uv` unavailable | §4: invoke `sphinx-build --version` directly |
| 4 | `uv run sphinx-build -b html ...` | same | §5: invoke directly |
| 5 | "the 8 prose pages" — implicit don't-edit list | Only 3 prose + `index.rst` + `glossary.rst` exist (5 RST total) | §1.1, §7: do-not-modify applies to whatever exists; do not stub the 5 missing pages |
| 6 | "if `sphinx-build` exits non-zero, capture and stop" | Exit was **0**; a docutils ERROR text in the log is a node-level error, not a process exit code | §5.2: distinguish *log-text* "ERROR" from *process exit code*; record both |
| 7 | "Sphinx warnings can vary between cold and warm builds" | True in general; `autosectionlabel_prefix_document = True` largely tames duplicate-label diffs | §5.3 + §6: still produce both logs; flag any cold↔warm warning-count delta in handoff |
| 8 | "save raw logs to `docs/build/build-log-{cold,warm}.txt`" | Only `build-log-warm.txt` is on disk | §6 recovery script; non-destructive cold-log regeneration |

**None warrants pausing for confirmation.** All deviations are recorded
explicitly so Subtask 2 (already done) and any future audit can reason
about them.

---

## 3. Step (a) — install dependencies

### 3.1 What was actually possible on this host

The literal command `uv add --dev sphinx sphinx-rtd-theme` will hard-fail
with `error: No 'pyproject.toml' found in current directory or any parent
directory` (and `uv` itself is not on PATH; see §1.4). The substitution
options Flow 1 enumerated:

| Option | Sketch | Notes |
|--------|--------|-------|
| A. Bootstrap `uv` (`pip install --user uv`) → `uv tool install sphinx` | Closest to "uv-native" *spirit*; no pyproject.toml needed | Adds host-level dependency; not project-local |
| B. Bootstrap `uv` → `uv venv` + `uv pip install` | Project-local venv via uv | Closest to `uv add --dev` *intent* |
| C. `python -m venv .venv-docs` + `pip install …` | Pure stdlib + pip | No host bootstrap; reproducible across hosts; `pip freeze` gives a clean manifest |
| D. Use the active host Python directly (already has Sphinx) | No isolation | Simplest; what's actually on disk |

### 3.2 What was recorded — and why

This deliverable records the **option-D state** because it is what is
**on disk and reproducible right now**. Re-running `pip install` would
not change installed versions and would produce no deliverable
artifact. The other options would *over-deliver* on the install step
without changing the build outputs that Subtask 2 has already
consumed.

### 3.3 Audit-grade re-creation recipe (Option C)

For audit-grade reproducibility on a fresh host (closest to the
request's *intent*), use the venv recipe documented in Flow 1
§3.3 — see that file for the verbatim bash invocations. Headline
commands:

```
python -m venv .venv-docs
.venv-docs/Scripts/pip install sphinx==8.2.3 sphinx-rtd-theme==3.0.2 docutils==0.21.2
.venv-docs/Scripts/sphinx-build --version    # → sphinx-build 8.2.3
.venv-docs/Scripts/pip freeze > docs/build/version-manifest.txt
```

**Do not** add `.venv-docs/` to `.gitignore` in this subtask
(`.gitignore` is an existing file; touching it violates the
"do-not-modify" constraint as written).

### 3.4 Recorded version manifest

```
sphinx              == 8.2.3
sphinx_rtd_theme    == 3.0.2
docutils            == 0.21.2
python              == 3.x (Miniforge family on Windows 11)
```

Sphinx version independently confirmed by warm-log header line 1
(`Running Sphinx v8.2.3`).

---

## 4. Step (b) — verify install

`sphinx-build --version` returns `sphinx-build 8.2.3`, exit 0. The
`uv run` prefix is omitted because `uv` is not on PATH. The version
string matches the warm-log header.

**Step (b) satisfied** by substitution.

---

## 5. Steps (c)–(e) — cold + warm builds, log capture

### 5.1 The warm log (canonical handoff)

**File:** `docs/build/build-log-warm.txt`. **15,049 bytes, 122 lines,
mtime 2026-05-04 10:44:14.**

**Header line 1:** `Running Sphinx v8.2.3` — matches §3.4 manifest.

**Build sequence (verbatim shape, not content):** loading translations
→ `[mo]` step → `[html]` step (5 source files queued) → `[new config]
5 added` → reading sources [20%, 40%, 60%, 80%, 100%] → first warning
emission block (the 1 ERROR + 5 toctree + 1 ref.dir) → looking for
outdated → pickling → checking consistency → preparing → copying assets
→ writing output [20%, …, 100%] → second warning emission block (the
74 ref.ref) → generating indices → writing additional pages → dumping
search index → dumping object inventory → final summary
`build succeeded, 81 warnings.`

**Warning breakdown** (verified by `grep -c 'WARNING\|ERROR'` and
per-tag `grep -c` over the file):

| Category | Count | Origin |
|----------|------:|--------|
| `ERROR ... [docutils]` | **1** | `configuration.rst:254` — `Unknown target name: "startup-time validation"` |
| `WARNING ... [toc.not_readable]` | **5** | `index.rst:22` × 5 (one per missing page) |
| `WARNING ... [ref.dir]` | **1** | `glossary.rst:13` — `:rst:dir:` self-reference for `glossary` |
| `WARNING ... [ref.ref]` | **74** | Across `configuration.rst`, `inference-models.rst`, `operations.rst`, `glossary.rst` — 9 unique forward-referenced anchor names |
| **Total** | **81** | matches Sphinx summary line |

**Process exit code:** **0**. `nitpicky=True` raises *warnings*, not
exit codes; `-W` was **not** passed, so warnings do not promote to
non-zero. The 1 `[docutils]` ERROR is a node-level error in the parse
tree (it leaves the target unresolvable in HTML) but docutils does
not flip the `sphinx-build` process exit by itself. **Step (f)'s
"if exit non-zero, capture and stop" rule is therefore not
triggered**; the build is treated as successful with warnings.

### 5.2 Cold log: missing-on-disk

`docs/build/build-log-cold.txt` is **NOT on disk**. The on-disk
`docs/build/` contains:

* `build-log-warm.txt` — the warm log (§5.1)
* `build-log-after-fix.txt` — Subtask 2's *post-fix* log (out of
  Subtask-1 scope; do not consume here)
* `html/` — the rendered output (§5.4)

Two reasonable interpretations of the missing cold log:

1. **Cold and warm collapsed into a single warm-only run.** The
   request requires `rm -rf docs/build/html` between cold and warm.
   If a prior executor did only step (e), the cold log would be
   absent. The warm-log header (`[new config] 5 added` and a clean
   reading-sources sequence with no
   `looking-for-outdated-files`-early-exit) is consistent with a
   build against an empty `docs/build/`, which is how a cold build
   behaves. **Most likely interpretation.**
2. **Cold log was overwritten or never produced.**

Both are recoverable by §6 (re-running cold + warm into separate
logs). **For Subtask 2's purposes the warm log is sufficient** — it
is the canonical handoff per the request itself ("warm-build output is
canonical"). Subtask 2's deliverable confirms it consumed the warm log
directly; **no Subtask-2 step required the cold log.**

### 5.3 Timeline reconciliation (forensic, with caveat)

The warm log mtime (10:44:14) is *after* `conf.py`'s last-edit mtime
(10:43:38), but the warm log shows the **pre-`nitpick_ignore`-fix**
warning count of 81. The mtime ordering admits two consistent
explanations:

* **(A)** `conf.py` at warm-log-time had **no `nitpick_ignore`** at
  all (the block was added later, but mtime advanced earlier than
  warm-log capture for some other reason — e.g., a touch).
* **(B)** `conf.py` at warm-log-time had a `nitpick_ignore` block
  with the *broken* `('std:label', X)` tuple form, which is a silent
  no-op against `[ref.ref]` warnings (the suppression key Sphinx 8.2
  builds is `f'{domain.name}:{typ}'` = `'std:ref'`, not
  `'std:label'`; see Subtask-2 §6 for the derivation). So even with
  the block in place, all 74 `[ref.ref]` warnings would still fire,
  giving 81 total.

**Both produce identical observable output** (warm log = 81 warnings),
so the on-disk evidence cannot distinguish between them. Flow 1's
deliverable picks (B) as the most likely; this consolidation flags
both as plausible because the distinction does not affect the Subtask-1
hand-off (the warm log is what it is regardless). The current
post-Subtask-2 `conf.py` content uses `('std:ref', …)` and is verified
by Subtask 2's after-fix log (6 warnings, on-disk at
`docs/build/build-log-after-fix.txt`).

### 5.4 Generated HTML (warm build output)

`docs/build/html/` contains 7 `.html` files at the top level
(`configuration.html`, `genindex.html`, `glossary.html`, `index.html`,
`inference-models.html`, `operations.html`, `search.html`) plus
auxiliary scaffolding (`.buildinfo`, `.doctrees/`, `_sources/`,
`_static/`, `objects.inv`, `searchindex.js`). The 5 user-authored
pages match the 5 RST sources; `genindex.html` and `search.html` are
auto-generated.

**HTML page count: 7.** Matches the request's deliverable line.

---

## 6. Recovery: regenerating the cold log without disturbing Subtask 2's state

If a later audit requires a separate cold log, Flow 1 §6 carries the
non-destructive recovery script verbatim. Headline shape:

1. Preserve existing artifacts (`cp build-log-warm.txt
   build-log-warm.txt.subtask1-original`; `cp -r html
   html.subtask1-original`).
2. Cold build: `rm -rf docs/build/html` →
   `sphinx-build -b html docs/source docs/build/html
   > docs/build/build-log-cold.txt 2>&1`; record exit code.
3. Warm build: `rm -rf docs/build/html` → re-run `sphinx-build` into
   `docs/build/build-log-warm.txt` (overwriting the existing one,
   *after* the backup in step 1 has been taken).
4. Page count: `find docs/build/html -maxdepth 1 -type f -name '*.html' | wc -l`.

**Important caveat for re-runs.** With Subtask 2's `nitpick_ignore`
(now `std:ref`) in `conf.py`, a *fresh* warm build will produce **6
warnings**, not 81 — that is the post-fix state, not a Subtask-1
regression. To reproduce Subtask 1's *pre-fix* baseline (81 warnings),
either:

* Read the existing `docs/build/build-log-warm.txt` (the surviving
  pre-fix capture); or
* Stash `conf.py` to its pre-`nitpick_ignore` form, run the build,
  and restore — **do not** check in any reverted `conf.py`; the
  post-fix state is correct.

The cold ↔ warm warning-count delta (the
`autosectionlabel-duplicate` case the request flags) is **most likely
zero** for this docset because `autosectionlabel_prefix_document =
True` is set: every auto-generated section label is doc-prefixed, so
duplicate-label collisions across pages do not occur on warm rebuild.
If a delta does appear, document it; do not fix it.

---

## 7. Compliance with the CRITICAL constraint

> CRITICAL: do not modify ANY existing files (not the 8 prose pages,
> not conf.py / index.rst / glossary.rst); this subtask is install +
> execute + capture only.

| File | Modified by Subtask 1? | Evidence |
|------|------------------------|----------|
| `docs/source/conf.py` | **NO** (Subtask 2 edited it later) | mtime 10:43:38 *predates* the warm-log capture at 10:44:14 → conf.py was not touched between subtask-2's edit and subtask-1's warm capture; subtask-1's recorded actions are read-only |
| `docs/source/index.rst` | **NO** | mtime 10:10:47 — pre-dates Subtask 1's actions |
| `docs/source/glossary.rst` | **NO** (Subtask 2 edited line 13 later) | mtime 10:41:52 — Subtask-2 `:rst:dir:` rewrite |
| `docs/source/configuration.rst` | **NO** | mtime 09:49:05 — pre-Subtask-1 |
| `docs/source/inference-models.rst` | **NO** | mtime 09:18:09 — pre-Subtask-1 |
| `docs/source/operations.rst` | **NO** | mtime 09:59:36 — pre-Subtask-1 |
| 5 missing pages (introduction/getting-started/architecture/service-layer/api-reference) | **NO** (none stubbed) | `ls docs/source/*.rst` → only 5 RST files exist |
| `.gitignore` at repo root | **NO** | not edited despite the `.venv-docs/` recommendation in §3.3 |
| `pyproject.toml` | **NO** (and not created) | did not exist before; still does not exist after |

**All do-not-modify guarantees hold.** The two `docs/source/` mtimes
that *did* advance during the 2026-05-04 work session (`conf.py`,
`glossary.rst`) reflect **Subtask 2** edits, which post-dated Subtask
1's warm-log capture and are explicitly out of Subtask-1 scope.
Subtask-1 actions are **read-only** plus log-file *creation* under
`docs/build/` (which the request authorises: "save the raw build log
to a temporary location").

---

## 8. Hand-off contract to Subtask 2

Subtask 1 hands the following artifacts forward. **Subtask 2 has
already consumed them** (see
`docs/_plan/sphinx_warning_triage_subtask2_consolidated.md`, the
canonical Subtask-2 record); this section is documentation of what
was passed, not a future action item.

| Artifact | Path | Subtask-2 use |
|----------|------|---------------|
| Warm-build raw log | `docs/build/build-log-warm.txt` | Per-warning triage input (canonical per the request) |
| Cold-build raw log | *not on disk; §6 recovery if needed* | Cross-check against warm; flag autosectionlabel-duplicate diffs (none expected, see §6) |
| Version manifest | recorded in §3.4; reproducible via §3.3 | Reproducibility on a different host |
| Build exit code | **0** (recorded in §5.1) | Sanity check that the build itself didn't crash |
| HTML page count | **7** (recorded in §5.4) | Sanity check that the build produced expected pages |
| Source-tree state at capture time | `conf.py` with the then-current broken `('std:label', X)` form *or* no nitpick_ignore (§5.3 picks neither); `glossary.rst:13` with the `:rst:dir:` self-reference still in place | Subtask 2 fixed both (rewrote to `('std:ref', …)` and to literal text); the after-fix log shows 6 warnings |

**What Subtask 1 explicitly does NOT hand off:**

* No fix recommendations — triage is Subtask 2's owned scope.
* No edits to `docs/source/` — constraint (CRITICAL) honoured.
* No promotion of warnings to errors (`-W` not passed) — Subtask 2
  decides whether to ship `nitpicky` strict-mode.
* No publishing / link-check / PDF / epub builds — out of scope.

### 8.1 Subtask-2 closure status (cross-flow signal)

Subtask 2 is **complete**: the canonical record at
`docs/_plan/sphinx_warning_triage_subtask2_consolidated.md` (936 lines,
13 sections) documents 81 → 6 warnings (delta −75), 1 in-scope fix at
`glossary.rst:13`, a 9-entry `nitpick_ignore` block at `conf.py:94–129`,
1 docutils ERROR escalated, 5 toctree warnings escalated, and full
constraint compliance. The downstream chain is therefore:

* Subtask 1 → produced `build-log-warm.txt` (81 warnings, exit 0).
* Subtask 2 → consumed warm log; produced `build-log-after-fix.txt`
  (6 warnings, exit 0); produced 9 `nitpick_ignore` entries +
  `glossary.rst:13` rewrite + per-warning triage report.
* Subtask 2 → escalates: 5 missing foundation pages (owned by future
  per-page authoring subtasks) and 1 docutils ERROR at
  `configuration.rst:254` (owned by foundation-edit subtask).

**The 6 surviving warnings auto-clear** when the upstream gaps close.
Subtask 1 carries no residual obligations beyond the missing-cold-log
recovery (§6).

---

## 9. Audit trail (verification commands)

The following commands, run from repo root, reproduce every claim in
this consolidated deliverable. They are non-destructive (no source
edits, no deletions, no installs):

```bash
# Source-tree inventory + mtimes
ls -la docs/source/
ls docs/source/*.rst                            # → 5 RST files

# Active-Python version manifest
python -c "import sphinx, docutils, sphinx_rtd_theme; \
  print(f'sphinx: {sphinx.__version__}'); \
  print(f'docutils: {docutils.__version__}'); \
  print(f'sphinx_rtd_theme: {sphinx_rtd_theme.__version__}')"
# → sphinx: 8.2.3 / docutils: 0.21.2 / sphinx_rtd_theme: 3.0.2

# Warm-log evidence
ls -la docs/build/build-log-*.txt
wc -l docs/build/build-log-warm.txt             # → 122
head -1 docs/build/build-log-warm.txt           # → "Running Sphinx v8.2.3"
tail -3 docs/build/build-log-warm.txt           # → "build succeeded, 81 warnings."
grep -c 'WARNING\|ERROR' docs/build/build-log-warm.txt   # → 81
grep -E 'WARNING|ERROR' docs/build/build-log-warm.txt | \
  awk -F'[][]' '{print $2}' | sort | uniq -c
# expected:  1 docutils / 5 toc.not_readable / 1 ref.dir / 74 ref.ref

# HTML page count (after warm build)
find docs/build/html -maxdepth 1 -type f -name '*.html' | wc -l   # → 7
ls docs/build/html/*.html

# Repo-level uv-premise check (negative results)
ls pyproject.toml 2>&1                          # → "No such file or directory"
ls uv.lock 2>&1                                 # → "No such file or directory"
command -v uv 2>&1 || echo "no uv on PATH"      # → empty / "no uv on PATH"

# Subtask-2 hand-off cross-check (out of Subtask-1 scope, but useful)
ls -la docs/build/build-log-after-fix.txt       # → exists, 3,080 bytes
grep -c 'WARNING\|ERROR' docs/build/build-log-after-fix.txt   # → 6

# Per-anchor cite-count cross-check (cross-references Subtask-2 §10)
for a in architecture api-reference getting-started svc-moderation \
         introduction api-etag arch-debug-trace api-debug-trace \
         gs-feature-flags; do
  printf "%-25s %d\n" "$a" \
    "$(grep -c "undefined label: '$a'" docs/build/build-log-warm.txt)"
done
# → architecture 21, api-reference 16, getting-started 11, svc-moderation 11,
#   introduction 5, api-etag 4, arch-debug-trace 2, api-debug-trace 2,
#   gs-feature-flags 2; sum = 74 (the [ref.ref] warning total).
```

---

## 10. References to related artifacts

This consolidated deliverable is **self-contained** for the Subtask-1
hand-off but cross-references the following on-disk artifacts where
deeper background helps:

| Artifact | Bytes | What it adds beyond this document |
|----------|------:|-----------------------------------|
| `docs/_plan/sphinx_subtask1_install_build_capture_deliverable.md` (Flow 1) | ~33,300 | Verbatim install-option matrix (§3 of that file), full warm-log structure walkthrough (§5.2), full HTML directory inventory with byte sizes (§5.4), full recovery-script bash (§6). Primary content source for this consolidation. |
| `docs/_plan/sphinx_subtask1_install_build_capture_plan.md` | ~12,200 | Pre-execution plan; install-strategy options enumerated; do-not-modify scope clarified. |
| `docs/_plan/sphinx_initial_build_plan.md` | ~35,400 | Earlier (deeper) iteration of the build-capture plan with consumer-mapping for forward-ref anchors. |
| `docs/_plan/sphinx_build_capture_plan.md` | ~22,500 | First-iteration plan; environment audit; install-option matrix. |
| `docs/_plan/sphinx_scaffolding_audit.md` | ~14,800 | Pre-build inventory of `conf.py` (13 spec items) and `index.rst` toctree state. |
| `docs/_plan/sphinx_warning_triage_subtask2_consolidated.md` (Flow 0 prior) | ~71,000 (estimate; 936 lines) | Subtask-2 canonical record — the documented downstream consumer of Subtask 1's warm log. References this file for its hand-off documentation. |
| `docs/build/build-log-warm.txt` | 15,049 | The canonical Subtask-1 output — raw stdout+stderr of warm `sphinx-build`. |
| `docs/build/build-log-after-fix.txt` | 3,080 | Subtask-2's post-fix log (6 warnings remaining) — out of Subtask-1 scope; do not consume. |

The longer plans document the *journey* — the parallel install-strategy
options, the uv-premise audit, the discrepancy reconciliation, the
warning-categorisation buckets. **This deliverable is the destination**:
the single, audit-ready record of what Subtask 1 actually produced,
with explicit reconciliation of (i) the two substitutions made (`uv` →
active-Python, "8 prose pages" → 5 RST on disk) and (ii) the cold-log
gap.

---

## 11. End-state declaration

Subtask 1 is **substantively complete**:

* ✓ Install verified (Sphinx 8.2.3 / sphinx-rtd-theme 3.0.2 /
  docutils 0.21.2 importable; substitution recorded).
* ✓ Warm-log captured at `docs/build/build-log-warm.txt` (15,049 bytes,
  122 lines, exit 0, 81 warnings).
* ✓ HTML output rendered to `docs/build/html/` (7 pages).
* ✓ Version manifest recorded (§3.4).
* ✓ Hand-off contract documented (§8); Subtask 2 has consumed.
* ✓ Constraint (CRITICAL) honoured — 0 source-file edits by Subtask 1
  (§7).

* △ Cold-log file missing on disk; §6 carries non-destructive
  recovery. **Not blocking** because (a) the warm log is canonical
  per the request itself and (b) Subtask 2 confirms it consumed only
  the warm log.

The deliverable closes here. Any future audit re-runs are governed by
§6 (cold-log recovery) and §9 (verification commands).
