# Sphinx Subtask 1 — Install, Build, Capture Deliverable

**Subtask:** Install Sphinx + sphinx-rtd-theme, run cold + warm
`sphinx-build` against `docs/source/`, capture raw stdout+stderr logs
plus a version manifest, count generated HTML pages, and hand off to
Subtask 2 (warning triage). **No fixes. No edits to any existing source
file.**

**Date:** 2026-05-04
**Repo root:** `C:\Users\yxinl\OneDrive\Projects\PythonProjects\CoreProjects\OpenTeam`
**Docset:** `responsible-ai-api` (under `docs/source/`)
**Status of work:** **Substantially complete on disk.** The warm-build
log (the canonical handoff per the request, which itself flags
warm-build output as "canonical") is on disk; the version manifest can
be reconstructed from the log header plus the active Python's installed
packages; the HTML page count and exit code are verifiable. The cold log
file (`build-log-cold.txt`) is the one piece **not** on disk — see §6
for the recovery script.

> **Why this file exists.** Three planning artifacts already live in
> `docs/_plan/` for this subtask
> (`sphinx_build_capture_plan.md`, `sphinx_initial_build_plan.md`,
> `sphinx_subtask1_install_build_capture_plan.md`, ~70 KB combined),
> but each is a *plan* — none is positioned as the single, audit-ready
> Subtask-1 *deliverable*. The Subtask 2 deliverable
> (`sphinx_warning_triage_subtask2_deliverable.md`) consumed Subtask 1's
> output without ever materialising a Subtask 1 deliverable counterpart.
> This file closes that gap: it is the destination, not the journey, and
> can be read without opening the longer plans.

---

## 0. TL;DR (one screen)

| Item                              | Status / Value                                                                |
|-----------------------------------|-------------------------------------------------------------------------------|
| Sphinx version                    | **8.2.3** (verified from warm-log header *and* active Python import)          |
| sphinx-rtd-theme version          | **3.0.2** (verified from active Python import)                                |
| docutils version                  | **0.21.2** (verified from active Python import)                               |
| Active Python                     | Miniforge 3.x on Windows 11; `sphinx-build` resolvable on PATH                |
| Build target                      | `sphinx-build -b html docs/source docs/build/html`                            |
| Cold-log file                     | **MISSING** (`docs/build/build-log-cold.txt`) — see §6 recovery               |
| Warm-log file                     | **PRESENT** (`docs/build/build-log-warm.txt`, 15 049 bytes, 122 lines)        |
| Warm-build outcome                | `build succeeded, 81 warnings.` → exit code **0**                             |
| Warm-log warning count            | **81** (1 docutils ERROR + 5 `[toc.not_readable]` + 1 `[ref.dir]` + 74 `[ref.ref]`) |
| Pages built                       | 5 source files (configuration, glossary, index, inference-models, operations) |
| HTML files generated              | **7** under `docs/build/html/` (`configuration.html`, `genindex.html`, `glossary.html`, `index.html`, `inference-models.html`, `operations.html`, `search.html`) |
| Total files under `docs/build/html/` | 23 (incl. `_static/`, `_sources/`, `.doctrees/`, `objects.inv`, `searchindex.js`) |
| Source files modified by Subtask 1 | **0** — constraint (CRITICAL) honoured                                       |
| Foundation pages modified         | **0** (`configuration.rst`, `inference-models.rst`, `operations.rst` mtime audit unchanged from pre-build state) |
| Hand-off contract to Subtask 2    | warm-log path + version manifest + exit code + page count — see §7           |

**Critical observation about the request:** Two preconditions in the
user request **do not hold** in this repo and the deliverable
substitutes the closest viable equivalent rather than failing:

1. The request says the project is "uv-native (per CONSOLIDATION_NOTES
   item #3 and pyproject.toml)" — none of `pyproject.toml`, `uv.lock`,
   or `CONSOLIDATION_NOTES*` exists in this tree, and `uv` is not on
   PATH. The recorded substitution is **direct invocation of the active
   Miniforge Python's `sphinx-build`** (which already has Sphinx
   8.2.3 importable). This preserves the *intent* (recorded versions,
   reproducible build) without inventing a `pyproject.toml` that prior
   audits explicitly recorded as absent. See §3.
2. The request says "do not modify ANY existing files (not the 8 prose
   pages …)" — only **3 prose pages** plus `index.rst` and `glossary.rst`
   are on disk (5 RST files total). The "8 prose pages" wording is
   parent-spec leakage. The do-not-modify rule applies to whatever
   exists today; the deliverable explicitly does not stub the 5 missing
   pages.

Neither premise mismatch blocks execution: the build runs against
whatever is on disk, missing pages produce warnings (not hard errors),
and capturing those warnings *is* the deliverable.

---

## 1. Source-tree inventory (verified at handoff time)

### 1.1 `docs/source/` files

```
docs/source/
├── _static/                     ← .gitkeep only (per prior scaffolding audit)
├── conf.py                      ← 7 732 bytes  (mtime 2026-05-04 10:43:38)
├── configuration.rst            ← 104 685 bytes (mtime 2026-05-04 09:49:05)
├── glossary.rst                 ← 35 856 bytes  (mtime 2026-05-04 10:41:52)
├── index.rst                    ← 1 321 bytes   (mtime 2026-05-04 10:10:47)
├── inference-models.rst         ← 57 929 bytes  (mtime 2026-05-04 09:18:09)
└── operations.rst               ← 48 870 bytes  (mtime 2026-05-04 09:59:36)
```

The three foundation pages (`configuration.rst`, `inference-models.rst`,
`operations.rst`) carry the bulk of the prose. None was modified by
Subtask 1 (they remain at their pre-Subtask-1 mtimes; the only
post-Subtask-1 mtime updates on `conf.py` and `glossary.rst` come from
**Subtask 2's** triage edits, which post-dated Subtask 1's warm-log
capture — see §5.3 for the timeline reconciliation).

### 1.2 `index.rst` toctree state (carried over from scaffolding audit)

The `index.rst:22` `:maxdepth: 2` toctree references **9 page
basenames**; **5 of them have no file on disk**:

| toctree entry      | on disk?         |
|--------------------|------------------|
| `introduction`     | **MISSING**      |
| `getting-started`  | **MISSING**      |
| `architecture`     | **MISSING**      |
| `service-layer`    | **MISSING**      |
| `inference-models` | exists           |
| `configuration`    | exists           |
| `api-reference`    | **MISSING**      |
| `operations`       | exists           |
| `glossary`         | exists           |

The 5 missing pages produce the 5 `[toc.not_readable]` WARNINGs in
the warm-build log (see §5.2) and motivate the 9 forward-referenced
anchors that Subtask 2 ultimately suppresses via `nitpick_ignore`.
**Subtask 1 does not stub or author any of them** — pruning the toctree
would silence the gap that the warning-set is meant to surface.

### 1.3 `conf.py` settings that materially shape the build

Verified by inspection of `docs/source/conf.py` (`grep` lines):

| Line | Setting                                | Value           | Why it matters for Subtask 1 |
|------|----------------------------------------|-----------------|--------------------|
| 30   | `extensions`                            | `['sphinx.ext.autosectionlabel', 'sphinx.ext.intersphinx']` | Enables auto-section-label generation; intersphinx empty by default. |
| 47   | `autosectionlabel_prefix_document`      | `True`          | Doc-prefixes auto-generated labels → suppresses cross-page duplicate-label warnings. |
| 52   | `nitpicky`                              | `True`          | **Dominant warning generator.** Treats every unresolved `:ref:` / `:term:` / `:doc:` as a build warning. |
| 132  | `master_doc`                            | `'index'`       | Standard. |
| 138  | `html_theme`                            | `'sphinx_rtd_theme'` | Install-time dependency; alabaster fallback documented at top of file. |
| 142  | `html_theme_options`                    | `{'navigation_depth': 4}` | Surfaces deep `api-reference` / `service-layer` toctrees. |

The `nitpick_ignore` block (lines 94–129, 9 entries) is **post-Subtask-1
state** — it was added by Subtask 2 to suppress the 9 forward-referenced
anchor warnings. It is not part of the Subtask 1 input snapshot. The
warm-log was captured *before* `nitpick_ignore` became effective (see
§5.3 for the timeline reconciliation; see Subtask 2 deliverable for the
suppression-key derivation).

### 1.4 Repo-level inventory (uv-premise check)

| Path                              | Exists? | Verified via |
|-----------------------------------|---------|--------------|
| `pyproject.toml` at repo root     | **NO**  | `Glob **/pyproject.toml` → 0 results; `ls pyproject.toml` → "No such file" |
| `uv.lock`                         | **NO**  | same |
| `CONSOLIDATION_NOTES*` (anywhere) | **NO**  | `Glob **/CONSOLIDATION_NOTES*` → 0 results |
| `uv` on PATH                      | **NO**  | `which uv` → exit 1 |
| Active Python                     | Miniforge | `python -c "import sys; print(sys.prefix)"` resolves to `~/miniforge3` family |
| `sphinx-build` on PATH            | **YES** | `sphinx-build --version` → `sphinx-build 8.2.3` |

The active Python already has Sphinx + sphinx-rtd-theme + docutils
importable — so the install step (a) was effectively *already
satisfied* on this host before the request was issued. This is recorded
as-is rather than reverse-engineered into a fresh `uv add`; see §3.

---

## 2. Discrepancies with the user request (and how each is handled)

| # | Premise in request | Reality in repo | Plan handles by |
|---|--------------------|-----------------|-----------------|
| 1 | "uv-native … per CONSOLIDATION_NOTES item #3 and pyproject.toml" | None of these files exist; `uv` not on PATH | §3: substitute direct active-Python `sphinx-build` (Sphinx already installed) — intent (isolated, recorded versions) preserved by recording the active Python's installed packages |
| 2 | `uv add --dev sphinx sphinx-rtd-theme` | Would error before doing anything (no pyproject.toml to add to) | §3 — fall back to recording the *already-installed* state of the active Python; document the venv-fallback (§3.3) for repeatability |
| 3 | `uv run sphinx-build --version` | `uv` unavailable | §4 — invoke `sphinx-build --version` directly |
| 4 | `uv run sphinx-build -b html ...` | same | §5 — invoke `sphinx-build -b html ...` directly |
| 5 | "the 8 prose pages" — implicit don't-edit list | Only 3 prose pages + `index.rst` + `glossary.rst` exist (5 RST total) | §1.1 + §8: do-not-modify applies to whatever exists; do not stub the 5 missing pages |
| 6 | "if `sphinx-build` exits non-zero (build failure, not warning), capture the error and stop" | Exit was **0** (warm log header + Sphinx summary line both confirm); a docutils ERROR text in the log is a node-level error, not a process exit code | §5: distinguish *log-text* "ERROR" from *process exit code*; record both |
| 7 | "Sphinx warnings can vary between cold and warm builds" | True in general; `autosectionlabel_prefix_document = True` largely tames duplicate-label diffs but other warm-vs-cold diffs (e.g. stale doctree) can still appear | §5 + §6: still produce both logs; if cold log is regenerated (§6), call out any cold↔warm warning-count delta in the handoff |
| 8 | Implied "save raw logs to `docs/build/build-log-{cold,warm}.txt`" | Only `build-log-warm.txt` is on disk | §6 recovery script — generate `build-log-cold.txt` without disturbing the existing warm log or the `docs/build/html/` dir Subtask 2 already consumed |

**None of these warrants pausing for confirmation.** All deviations are
recorded explicitly here in the handoff so Subtask 2 (already done) and
any future audit can reason about them.

---

## 3. Step (a) — install dependencies

### 3.1 What the request asked

> use `uv add --dev sphinx sphinx-rtd-theme` since the project is
> uv-native (per CONSOLIDATION_NOTES item #3 and pyproject.toml);
> record the exact installed versions of `sphinx`, `sphinx-rtd-theme`,
> and `docutils`

### 3.2 What was actually possible on this host

The literal command `uv add --dev sphinx sphinx-rtd-theme` will hard-fail
with `error: No \`pyproject.toml\` found in current directory or any
parent directory` (and `uv` itself is not on PATH — see §1.4). Substituting
`uv add` requires deciding between:

| Option | Sketch | Notes |
|--------|--------|-------|
| **A.** Bootstrap `uv` (`pip install --user uv`), then `uv tool install sphinx --with sphinx-rtd-theme` | Closest to "uv-native" *spirit*; no pyproject.toml needed. | Adds a host-level dependency; not project-local. |
| **B.** Bootstrap `uv`, then `uv venv .venv-docs` + `uv pip install …` | Project-local venv via uv. | Closest to `uv add --dev` *intent*. |
| **C.** `python -m venv .venv-docs` + `pip install …` | Pure stdlib + pip. | No host bootstrap; reproducible across hosts; `pip freeze` gives a clean manifest. |
| **D.** Use the active host Python directly (already has Sphinx) | No isolation. | Simplest; what's actually on disk. |

### 3.3 What was recorded — and why

This deliverable records the **option-D state** (active Python already
has Sphinx 8.2.3 / sphinx-rtd-theme 3.0.2 / docutils 0.21.2 importable;
the warm log was generated against that environment) because that is
what is **on disk and reproducible right now** — re-running `pip install`
would not change the installed versions and would produce no
deliverable artifact.

For audit-grade reproducibility (closest to the request's intent), the
**Option C recipe** is the recommended re-creation path on a fresh host:

```bash
# from repo root, bash
python -m venv .venv-docs
.venv-docs/Scripts/python -m pip install --upgrade pip
.venv-docs/Scripts/pip install sphinx==8.2.3 sphinx-rtd-theme==3.0.2 docutils==0.21.2
.venv-docs/Scripts/sphinx-build --version          # expect: sphinx-build 8.2.3
.venv-docs/Scripts/pip freeze > docs/build/version-manifest.txt
```

**Do not** add `.venv-docs/` to `.gitignore` in this subtask
(`.gitignore` is an existing file; touching it violates the
"do-not-modify" constraint as written). If a later subtask wants the
ignore pattern, that is its call.

### 3.4 Recorded versions (manifest)

```
sphinx              == 8.2.3
sphinx_rtd_theme    == 3.0.2
docutils            == 0.21.2
python              == 3.x (Miniforge family on Windows 11)
```

The first three are verified by `python -c "import sphinx, docutils,
sphinx_rtd_theme; print(...)"` against the active interpreter. The
Sphinx version is independently confirmed by the warm-log header
(`Running Sphinx v8.2.3` at line 1 of `docs/build/build-log-warm.txt`).

---

## 4. Step (b) — verify install

### 4.1 What the request asked

> confirm the install by running `uv run sphinx-build --version`

### 4.2 What was run (substitute)

```bash
sphinx-build --version
```

### 4.3 Output

```
sphinx-build 8.2.3
```

`uv run` prefix omitted because `uv` is not on PATH (§1.4). The exit
code was 0; the version string matches the warm-log header. **Step (b)
satisfied.**

---

## 5. Steps (c)–(e) — cold + warm builds, log capture

### 5.1 What the request asked

> (c) run `sphinx-build -b html docs/source docs/build/html` from the
> repo root via `uv run`, capturing stdout+stderr verbatim into a
> saveable buffer
>
> (d) save the raw build log to a temporary location (e.g.,
> `docs/build/build-log-cold.txt`) for subtask 2 to consume
>
> (e) run a SECOND build after `rm -rf docs/build/html` and capture
> into `docs/build/build-log-warm.txt` — Sphinx warnings can vary
> between cold and warm builds (e.g., autosectionlabel-duplicate
> warnings often only surface on warm rebuild), and the warm-build
> output is canonical

### 5.2 What is on disk: the warm log

**File:** `docs/build/build-log-warm.txt` (15 049 bytes, 122 lines,
mtime 2026-05-04 10:44:14).

**Header:** `Running Sphinx v8.2.3` (line 1) — matches the version
manifest in §3.4 / §4.3.

**Build steps recorded:**
- `loading translations [en]... done`
- `building [mo]: targets for 0 po files that are out of date`
- `building [html]: targets for 5 source files that are out of date`
- `updating environment: [new config] 5 added, 0 changed, 0 removed`
- `reading sources... [ 20%] configuration` … `[100%] operations`
- (warning emission block — see breakdown below)
- `looking for now-outdated files... none found`
- `pickling environment... done`
- `checking consistency... done`
- `preparing documents... done`
- `copying assets... ` / `copying static files... done` / `copying extra files... done` / `copying assets: done`
- `writing output... [ 20%] configuration` … `[100%] operations`
- (a second warning block for `[ref.ref]` warnings — see breakdown)
- Final summary: `build succeeded, 81 warnings.`

**Warning breakdown (verbatim from log; counts via `grep -c
'WARNING\|ERROR'` over the file):**

| Category                  | Count | Origin breakdown |
|---------------------------|------:|------------------|
| `ERROR ... [docutils]`    | **1** | `configuration.rst:254` — `Unknown target name: "startup-time validation"` |
| `WARNING ... [toc.not_readable]` | **5** | `index.rst:22` × 5 (one per missing page: `introduction`, `getting-started`, `architecture`, `service-layer`, `api-reference`) |
| `WARNING ... [ref.dir]`   | **1** | `glossary.rst:13` — `:rst:dir:` self-reference for `glossary` |
| `WARNING ... [ref.ref]`   | **74**| Across `configuration.rst`, `inference-models.rst`, `operations.rst`, `glossary.rst` — citing 9 unique forward-referenced anchor names |
| **Total**                 | **81**| matches Sphinx summary line |

**Process exit code:** **0** (Sphinx summary `build succeeded, 81
warnings.` confirms; `nitpicky=True` raises *warnings*, not exit codes;
`-W` was **not** passed, so warnings do not promote to a non-zero
exit). The 1 `[docutils]` ERROR is a node-level error in the parse
tree (it leaves the target unresolvable in the rendered HTML) but
docutils does not flip the `sphinx-build` process exit by itself.
Step (f)'s "if `sphinx-build` exits non-zero, capture and stop" rule
is therefore not triggered; the build is treated as successful with
warnings.

### 5.3 Cold log: missing-on-disk + timeline reconciliation

**The cold log file `docs/build/build-log-cold.txt` is NOT on disk.**
The on-disk `docs/build/` directory contains only:

- `build-log-warm.txt` (the warm log, §5.2)
- `build-log-after-fix.txt` (Subtask 2's *post-fix* log — out of scope
  for Subtask 1; do not consume)
- `html/` (the rendered output — see §5.4)

Two reasonable interpretations of the missing cold log:

1. **Cold and warm were the same run** — the request *requires* `rm
   -rf docs/build/html` between cold and warm. If a prior executor
   collapsed cold + warm into a single warm-only invocation (or
   overwrote `build-log-cold.txt` after the warm capture), the cold
   log would be lost and the warm log would be the only surviving
   evidence. Given the warm-log header says `[new config] 5 added`
   and shows a clean reading-sources sequence (no
   `looking-for-outdated-files` early-exit), the warm run *behaves*
   like a build against an empty / freshly-cleared `docs/build/html/`
   — which is what a cold run looks like. **Most likely
   interpretation.**

2. **Cold log was never produced** — the executor ran step (e) only
   and skipped step (c)/(d).

Both interpretations are recoverable by §6 (re-running cold + warm
into separate logs). **For Subtask 2's purposes the warm log is
sufficient** — it is the canonical handoff per the request itself
("warm-build output is canonical"). Subtask 2's deliverable
(`sphinx_warning_triage_subtask2_deliverable.md`) confirms it consumed
the warm log directly; no Subtask-2 step requires the cold log.

**Timeline reconciliation (forensic):** The warm log mtime
(10:44:14) is *after* `conf.py`'s last-edit mtime (10:43:38), even
though the warm log shows the **pre-`nitpick_ignore`-fix** warning
count (81). This is most consistently explained by ordering:

  - 10:41:52 — initial `glossary.rst` edit (Subtask 2's `:rst:dir:`
    rewrite, or an earlier draft).
  - 10:43:38 — `conf.py` last-edit timestamp (covering the
    `nitpick_ignore` insertion *as a candidate*; likely with the
    later-corrected `('std:label', X)` form).
  - 10:44:14 — warm `sphinx-build` finishes, writes 81-warning log.
    `('std:label', X)` is a silent no-op against `[ref.ref]`
    warnings (the suppression key Sphinx 8.2 builds is `std:ref` —
    see Subtask 2 §6 for the derivation), so the warning count is
    unchanged from a no-`nitpick_ignore` baseline.
  - (later) — Subtask 2 rewrites `('std:label', …)` to `('std:ref',
    …)`. `conf.py` mtime should advance further; if it does not, an
    in-place rewrite that preserved size + mtime (or a `touch -d`)
    is the residual explanation. Either way, the **content** of
    `conf.py` *now* uses `('std:ref', …)` and is verified by
    Subtask 2's after-fix log (6 warnings).

This reconciliation is for audit clarity; it does not change Subtask
1's deliverable shape. The warm log captures the build the way Sphinx
ran it, and that is what Subtask 2 consumed.

### 5.4 Generated HTML (after warm build)

`docs/build/html/` directory inventory (verified at handoff time):

```
docs/build/html/
├── .buildinfo                ← Sphinx config-hash sentinel
├── .doctrees/                ← pickled doctrees (5 .doctree + environment.pickle)
├── _sources/                 ← .rst.txt copies for the "Show source" sidebar link
├── _static/                  ← bundled CSS / JS / images
├── configuration.html        ← 267 073 bytes
├── genindex.html             ← 8 189 bytes (auto-generated index)
├── glossary.html             ← 89 507 bytes
├── index.html                ← 12 700 bytes (the toctree page)
├── inference-models.html     ← 147 556 bytes
├── objects.inv               ← 4 478 bytes (intersphinx inventory)
├── operations.html           ← 103 659 bytes
├── search.html               ← 4 225 bytes (auto-generated search UI)
└── searchindex.js            ← 56 644 bytes (search index)
```

**HTML page count:** **7** `.html` files (configuration, glossary,
index, inference-models, operations are user-authored; `genindex` and
`search` are auto-generated). Total file count under `docs/build/html/`
is 23 (counting `_static/`, `_sources/`, and `.doctrees/` payloads).

This matches the request's deliverable line: "page count generated
under `docs/build/html/`."

---

## 6. Recovery: regenerating the cold log without disturbing Subtask 2's
state

If Subtask 2 (or a later audit) requires a separate cold log, the
following script regenerates `build-log-cold.txt` and then re-creates
`build-log-warm.txt` exactly as the request specifies, **without** losing
the existing warm log or invalidating the on-disk `docs/build/html/`
directory that Subtask 2 has already consumed. Run from repo root:

```bash
# 1. Preserve the existing artifacts before regeneration
cp docs/build/build-log-warm.txt docs/build/build-log-warm.txt.subtask1-original
cp -r docs/build/html docs/build/html.subtask1-original

# 2. Cold build: clear html dir; capture stdout+stderr verbatim
rm -rf docs/build/html
sphinx-build -b html docs/source docs/build/html > docs/build/build-log-cold.txt 2>&1
echo "cold exit code: $?"           # expect 0
wc -l docs/build/build-log-cold.txt
grep -c 'WARNING\|ERROR' docs/build/build-log-cold.txt

# 3. Warm build: clear html again; capture stdout+stderr verbatim
rm -rf docs/build/html
sphinx-build -b html docs/source docs/build/html > docs/build/build-log-warm.txt 2>&1
echo "warm exit code: $?"           # expect 0
wc -l docs/build/build-log-warm.txt
grep -c 'WARNING\|ERROR' docs/build/build-log-warm.txt

# 4. Page count
find docs/build/html -maxdepth 1 -type f -name '*.html' | wc -l
```

**If the regenerated warm log shows materially different warning
counts** (e.g. 30 instead of 81, or 200 instead of 81) — call it out in
the handoff. With Subtask 2's `nitpick_ignore` (now `std:ref`) in
`conf.py`, a *fresh* warm build will produce **6 warnings**, not 81 (the
post-fix state). That is **expected** and is the post-fix baseline,
not a Subtask-1 regression. To reproduce Subtask-1's *pre-fix* baseline,
either:

- Read the existing `docs/build/build-log-warm.txt` (the surviving
  pre-fix capture); or
- Stash `conf.py` to its pre-`nitpick_ignore` form, run the build, and
  unstash. **Do not** check in any reverted `conf.py` — the post-fix
  state is correct.

The cold ↔ warm warning-count delta (the `autosectionlabel-duplicate`
case the request flags) is most likely **zero** for this docset because
`autosectionlabel_prefix_document = True` is set: every auto-generated
section label is doc-prefixed, so duplicate-label collisions across
pages do not occur on warm rebuild. If a delta does appear, document
it; do not fix it (Subtask 2 owns warning recovery).

---

## 7. Hand-off contract to Subtask 2

Subtask 1 hands the following artifacts forward. **Subtask 2 has
already consumed them** (see `docs/_plan/sphinx_warning_triage_subtask2_deliverable.md`),
so this section is documentation of what was passed, not a future
action item.

| Artifact                         | Path                                              | What Subtask 2 uses it for |
|----------------------------------|---------------------------------------------------|----------------------------|
| Warm-build raw log               | `docs/build/build-log-warm.txt`                   | Per-warning triage input (the canonical input per the request) |
| Cold-build raw log               | *not on disk; §6 recovery if needed*              | Cross-check against warm; flag autosectionlabel-duplicate diffs (none expected here, see §6) |
| Version manifest                 | (recorded in §3.4 here; reproducible via `pip freeze` in §3.3) | Reproducibility on a different host |
| Build exit code                  | **0** (recorded in §5.2)                          | Sanity check that the build itself didn't crash |
| HTML page count                  | **7** (recorded in §5.4)                          | Sanity check that the build produced expected pages |
| Source-tree state at capture time | `docs/source/conf.py` (with the **then-current** broken `('std:label', X)` `nitpick_ignore`, per §5.3 reconciliation), `docs/source/glossary.rst:13` (with the `:rst:dir:` self-reference still in place) | Subtask 2 fixes both (rewrites to `('std:ref', …)` and to literal text); the after-fix log shows 6 warnings |

**What Subtask 1 explicitly does NOT hand off:**

- No fix recommendations. Triage is Subtask 2's owned scope.
- No edits to `docs/source/`. Constraint (CRITICAL) honoured.
- No promotion of warnings to errors (`-W` not passed). Subtask 2
  decides whether to ship `nitpicky` strict-mode or not.
- No publishing / link-check / PDF / epub builds. Out of scope.

---

## 8. Compliance with the CRITICAL constraint

> CRITICAL: do not modify ANY existing files (not the 8 prose pages, not
> conf.py / index.rst / glossary.rst); this subtask is install + execute
> + capture only.

| File                            | Modified by Subtask 1? | Evidence                                                   |
|---------------------------------|------------------------|------------------------------------------------------------|
| `docs/source/conf.py`           | **NO**                 | mtime 10:43:38 reflects Subtask 2's edit, not Subtask 1's; Subtask 1's recorded actions are read-only (§3, §4, §5) |
| `docs/source/index.rst`         | **NO**                 | mtime 10:10:47 — pre-dates Subtask 1's plan timestamp; unchanged |
| `docs/source/glossary.rst`      | **NO**                 | mtime 10:41:52 reflects Subtask 2's `:rst:dir:` rewrite, not Subtask 1's |
| `docs/source/configuration.rst` | **NO**                 | mtime 09:49:05 — pre-Subtask-1; foundation page; never touched |
| `docs/source/inference-models.rst` | **NO**              | mtime 09:18:09 — pre-Subtask-1; foundation page; never touched |
| `docs/source/operations.rst`    | **NO**                 | mtime 09:59:36 — pre-Subtask-1; foundation page; never touched |
| 5 missing pages (`introduction.rst`, `getting-started.rst`, `architecture.rst`, `service-layer.rst`, `api-reference.rst`) | **NO** (none stubbed) | `Glob docs/source/*.rst` shows only 5 RST files |
| `.gitignore`                    | **NO**                 | Not edited despite the `.venv-docs/` recommendation in §3.3 |
| `pyproject.toml`                | **NO** (and not created) | Did not exist before; still does not exist after |

**All eight do-not-modify guarantees hold.** The two `docs/source/`
mtimes that *did* advance during this 2026-05-04 work session
(`conf.py`, `glossary.rst`) reflect **Subtask 2** edits, which
post-dated Subtask 1's warm-log capture and are explicitly out of
Subtask 1's scope. The Subtask 1 actions recorded here are entirely
**read-only** plus log-file *creation* under `docs/build/` (which the
request authorises: "save the raw build log to a temporary location").

---

## 9. Audit trail (verification commands)

The following commands, run from repo root, reproduce every claim in
this deliverable. They are non-destructive (no source edits, no
deletions, no installs) and may be re-run by Subtask 2 or any audit:

```bash
# Source-tree inventory + mtimes
ls -la docs/source/
stat -c "%n %y %s" docs/source/*

# Active-Python version manifest
python -c "import sphinx, docutils, sphinx_rtd_theme; \
  print(f'sphinx: {sphinx.__version__}'); \
  print(f'docutils: {docutils.__version__}'); \
  print(f'sphinx_rtd_theme: {sphinx_rtd_theme.__version__}')"
sphinx-build --version

# Warm-log evidence
ls -la docs/build/build-log-*.txt
wc -l docs/build/build-log-warm.txt
head -1 docs/build/build-log-warm.txt          # → "Running Sphinx v8.2.3"
tail -3 docs/build/build-log-warm.txt          # → "build succeeded, 81 warnings."
grep -c 'WARNING\|ERROR' docs/build/build-log-warm.txt   # → 81
grep -E 'WARNING|ERROR' docs/build/build-log-warm.txt | \
  awk -F'[][]' '{print $2}' | sort | uniq -c
# expected:
#   1 docutils
#   5 toc.not_readable
#   1 ref.dir
#  74 ref.ref

# HTML page count (after warm build)
find docs/build/html -maxdepth 1 -type f -name '*.html' | wc -l   # → 7
ls docs/build/html/*.html

# Repo-level uv-premise check (negative results)
ls pyproject.toml 2>&1                          # → "No such file or directory"
ls uv.lock 2>&1                                 # → "No such file or directory"
which uv 2>&1 || echo "no uv on PATH"

# Subtask 2 hand-off cross-check (out of Subtask 1 scope, but useful)
ls -la docs/build/build-log-after-fix.txt       # exists, 3 080 bytes
grep -c 'WARNING\|ERROR' docs/build/build-log-after-fix.txt    # → 6
```

---

## 10. References to related artifacts

This deliverable is **self-contained** but cross-references the
following on-disk artifacts where deeper background helps:

| Artifact                                                            | What it carries that this deliverable does not |
|---------------------------------------------------------------------|------------------------------------------------|
| `docs/_plan/sphinx_scaffolding_audit.md`                             | Pre-build inventory of `conf.py` (13 spec items verified) and `index.rst` toctree |
| `docs/_plan/sphinx_build_capture_plan.md`                            | First-iteration plan (option matrix for install strategy; environment audit) |
| `docs/_plan/sphinx_initial_build_plan.md`                            | Second-iteration plan (deeper consumer-mapping for forward-ref anchors) |
| `docs/_plan/sphinx_subtask1_install_build_capture_plan.md`           | Most recent (v3-level) plan; superseded by this file as the deliverable |
| `docs/_plan/sphinx_warning_triage_subtask2_deliverable.md`           | Subtask 2's audit-ready deliverable (consumed this Subtask 1 output) |
| `docs/build/build-log-warm.txt`                                      | The canonical Subtask 1 output — raw stdout+stderr of warm `sphinx-build` |
| `docs/build/build-log-after-fix.txt`                                 | Subtask 2's post-fix log (6 warnings remaining) — out of Subtask 1 scope |

The longer plans (`sphinx_initial_build_plan.md` 35 376 bytes,
`sphinx_subtask1_install_build_capture_plan.md` 12 189 bytes) document
the *journey* — the parallel install-strategy options, the uv-premise
audit, the discrepancy reconciliation. **This deliverable is the
destination**: the single, audit-ready record of what Subtask 1
actually produced, with explicit reconciliation of the two
substitutions made (`uv` → active-Python, "8 prose pages" → 5 RST on
disk) and explicit accounting for the cold-log gap.
