# Plan — Sphinx Build (Subtask 3, Step 1: Install + Capture)

**Subtask ID:** build-step-1 (capture only; recovery owned by build-step-2)
**Plan author:** scoped for `responsible-ai-api` docset under `docs/source/`
**Plan date:** 2026-05-04
**Repo root:** `C:\Users\yxinl\OneDrive\Projects\PythonProjects\CoreProjects\OpenTeam`

---

## 0. TL;DR

Install Sphinx + RTD theme, run a cold build and a warm build of `docs/source/`,
save the raw stdout+stderr verbatim, record installed versions, exit code, and
HTML page count. Do **not** modify any source file. Hand a manifest off to
subtask 2 for triage.

Two preconditions stated in the original task description are **factually wrong
for this repo** and the plan compensates explicitly (see §2). Without that
compensation, step (a) of the task — `uv add --dev sphinx sphinx-rtd-theme` —
will fail at the first command.

---

## 1. Goals & non-goals

**Goals (what this subtask owns):**

1. Make Sphinx, sphinx-rtd-theme, and the matching docutils available to a
   `sphinx-build` invocation, capturing the exact installed versions.
2. Run `sphinx-build -b html docs/source docs/build/html` twice — once cold
   (no env), once warm (after a fresh `rm -rf docs/build/html`) — capturing
   stdout+stderr verbatim into named log files.
3. Produce a small handoff manifest with versions, exit codes, page count,
   and log paths.

**Non-goals (what this subtask explicitly does NOT do):**

- No edits to `docs/source/conf.py`, `docs/source/index.rst`,
  `docs/source/glossary.rst`, or any of the existing prose pages.
- No authoring or stubbing of the 5 missing pages
  (`introduction`, `getting-started`, `architecture`, `service-layer`,
  `api-reference`).
- No warning triage, no nitpicky-suppression, no `-W` promotion, no
  `nitpick_ignore` edits. Subtask 2 owns recovery.
- No publish step, no link-check, no PDF/epub builders.

---

## 2. Environment audit & spec/reality reconciliation

The original task description names a precondition pair that does not hold in
this repo. The plan calls these out up front so the executor does not blindly
run `uv add --dev …` and crash:

| # | Task description claim | Actual repo state (verified 2026-05-04) | Implication |
|---|---|---|---|
| 1 | "the project is uv-native (per CONSOLIDATION_NOTES item #3 and pyproject.toml)" | No `pyproject.toml` at repo root, no `uv.lock`, no `CONSOLIDATION_NOTES*` file anywhere in tree (`find` + `Grep` both return nothing). | `uv add --dev` requires a project to attach to; without `pyproject.toml` it errors. See §3 step 1 for the install-strategy decision tree. |
| 2 | "use `uv add --dev sphinx sphinx-rtd-theme`" | `uv` is **not on PATH** (`which uv` exit 1; PATH inspected — no uv directory). Active Python is `C:\Users\yxinl\miniforge3\python` 3.12.7. | Cannot invoke `uv` at all from the current shell. Plan needs a non-uv fallback. |
| 3 | "8 already-authored prose pages" + glossary | 4 prose-equivalent files on disk: `configuration.rst`, `inference-models.rst`, `operations.rst`, `glossary.rst`. The `index.rst` toctree references 9 basenames; 5 (`introduction`, `getting-started`, `architecture`, `service-layer`, `api-reference`) do not exist. | Cosmetic to this subtask — we still build whatever is there — but the build WILL emit 5 `toctree contains reference to nonexisting document` warnings. Predict, don't fix. |
| 4 | "Install Sphinx and run the initial build" — implies fresh install | Sphinx 8.2.3, sphinx-rtd-theme 3.0.2, docutils 0.21.2 are **already** importable in the active Python. A prior build already exists at `docs/build/html/` with a stale `docs/build/build-log-warm.txt` (112 lines, "build succeeded, 81 warnings."). | The "install" step may be a no-op or may need to confirm-and-record rather than install fresh. The "cold" build is no longer cold against an empty `docs/build/`; we must explicitly delete `docs/build/` before step 3 to make "cold" honest. |

**Conclusions for the executor:**

- The install-step contract becomes "make `sphinx-build` callable and record
  versions"; the literal command `uv add --dev …` is contingent on uv +
  pyproject.toml existing. See §3 step 1 decision tree.
- Before step 3 (cold build), delete `docs/build/` entirely (not just
  `docs/build/html/`) so the cold log starts from a true empty-output state.
- The existing `docs/build/build-log-warm.txt` is from a prior run and **must
  be overwritten** by this subtask's warm log; don't trust its contents as
  this subtask's deliverable.

---

## 3. Step-by-step execution plan

All commands run from repo root (`C:\Users\yxinl\OneDrive\Projects\PythonProjects\CoreProjects\OpenTeam`).
Use the Bash tool (git-bash on Windows) so that `rm -rf` and `2>&1` behave as
written. PowerShell equivalents are listed where they diverge.

### Step 1 — Install dependencies & record versions

**Branch on uv availability:**

```
1a. Check `command -v uv` AND existence of pyproject.toml at repo root.
1b. If both present  → run `uv add --dev sphinx sphinx-rtd-theme` (the spec'd path).
1c. If uv missing OR no pyproject.toml → fall back per the table below.
```

| Condition | Install command | Notes |
|---|---|---|
| `uv` on PATH **and** `pyproject.toml` exists | `uv add --dev sphinx sphinx-rtd-theme` | Spec'd path. Updates pyproject.toml + uv.lock. |
| `uv` on PATH, no `pyproject.toml` | `uv pip install sphinx sphinx-rtd-theme` (system or active venv) | uv as a pip-shim; no project file mutated. |
| No `uv` (current state) | `python -m pip install --user sphinx sphinx-rtd-theme` OR confirm already-installed via `python -c "import sphinx, sphinx_rtd_theme"` and skip | If imports succeed, do NOT reinstall — the spec wants versions recorded, not necessarily a fresh download. Record the installed versions and proceed. |

**Empirical state (this repo, today):** Path 3 applies. `python -c "import
sphinx; print(sphinx.__version__)"` already returns `8.2.3`; sphinx-rtd-theme
returns `3.0.2`; docutils returns `0.21.2`. The plan will **not** force a
reinstall because (i) these are already the latest stable line for the
Sphinx 8.x track and (ii) reinstalling without an isolated env risks
disturbing other tools the user has installed in miniforge3.

**Version-capture command (always run, regardless of branch):**

```bash
python -c "import sphinx, sphinx_rtd_theme, docutils; \
  print(f'sphinx={sphinx.__version__}'); \
  print(f'sphinx_rtd_theme={sphinx_rtd_theme.__version__}'); \
  print(f'docutils={docutils.__version__}')"
```

Record the three lines verbatim into the manifest (§5).

### Step 2 — Verify the `sphinx-build` invocation

Spec command: `uv run sphinx-build --version`
Fallback (no uv): `python -m sphinx --version` OR `sphinx-build --version`

Record the printed version line into the manifest. Confirm it matches the
`sphinx==X.Y.Z` reported by Step 1 (a mismatch would mean two competing
Sphinx installs, one shadowing the other on PATH — flag and stop).

**Empirical expectation:** `sphinx-build 8.2.3` (or `python -m sphinx 8.2.3`).

### Step 3 — Cold build (full clean → build → capture)

```bash
# Truly cold: nuke the entire build dir, not just html/, so .doctrees and
# any other Sphinx env caches are gone. This makes "cold" honest.
rm -rf docs/build

# Build, capturing combined stdout+stderr verbatim. tee both shows progress
# to the operator and preserves the file. Exit code is captured separately
# because tee swallows the underlying exit code.
sphinx-build -b html docs/source docs/build/html 2>&1 | tee docs/build/build-log-cold.txt
COLD_EXIT=${PIPESTATUS[0]}     # bash-only — captures sphinx-build's exit code, not tee's
echo "cold-exit=$COLD_EXIT"
```

**If invoking via uv (path 1b/1c):** `uv run sphinx-build -b html docs/source docs/build/html 2>&1 | tee …`

**Windows PowerShell equivalent for the `rm -rf` line:**
`Remove-Item -Recurse -Force docs/build -ErrorAction SilentlyContinue`

**ANSI color caveat:** the existing `docs/build/build-log-warm.txt` shows that
`sphinx-build` emits ANSI escape sequences (`[01m…[39;49;00m`) when stderr is a
TTY. Through `tee` to a file, escape codes will be preserved. **Do not strip
them in this subtask** — the spec says "verbatim". Subtask 2 can strip if it
wants cleaner regex matches; preserving here keeps an auditable trail of what
Sphinx actually printed. If subtask 2 needs a clean copy, the standard
post-process is `sed -r 's/\x1B\[[0-9;]*[mK]//g'` against a copy of the log.

### Step 4 — Warm build (rebuild against existing env, then capture)

```bash
# Warm rebuild: keep the .doctrees/ env from the cold build, but force HTML
# regeneration by removing only the HTML output. This is the canonical
# "warm" state per the task description — Sphinx will reuse cached parsed
# trees but re-render templates and re-write HTML. autosectionlabel
# duplicate warnings, intersphinx-cache warnings, and toctree-resolution
# differences vs. cold all surface here.
rm -rf docs/build/html

sphinx-build -b html docs/source docs/build/html 2>&1 | tee docs/build/build-log-warm.txt
WARM_EXIT=${PIPESTATUS[0]}
echo "warm-exit=$WARM_EXIT"
```

**Why the rebuild script removes only `docs/build/html` (not all of `docs/build`):**
This is the difference between cold and warm. Removing only the HTML output
preserves `docs/build/.doctrees/` (Sphinx's cache of parsed sources) and
`docs/build/.buildinfo`. The next `sphinx-build` invocation uses that cache
and is therefore "warm".

### Step 5 — Page count & exit-code summary

```bash
PAGE_COUNT=$(find docs/build/html -maxdepth 1 -name '*.html' -type f | wc -l)
echo "page-count=$PAGE_COUNT"
ls -1 docs/build/html/
```

**Empirical expectation (from the prior build and the disk inventory):**

The `docs/build/html/` directory will contain these top-level HTML files:

```
configuration.html
genindex.html
glossary.html
index.html
inference-models.html
operations.html
search.html
```

That is **7 HTML pages**: 4 from existing source `.rst` files
(`configuration`, `glossary`, `inference-models`, `operations`) + `index.html`
+ 2 auto-generated (`genindex.html`, `search.html`). The 5 missing toctree
basenames produce no HTML output (Sphinx silently skips them after warning).

Plus the auxiliary artifacts (not counted as pages but recorded in §5):
`_sources/`, `_static/`, `objects.inv`, `searchindex.js`.

### Step 6 — Assemble & emit the handoff manifest (§5)

Write the manifest as a small markdown or JSON file under `docs/build/` so it
travels with the logs. Recommended path: `docs/build/build-manifest.md`.
Subtask 2 reads it as the canonical handoff record.

---

## 4. Predicted build signals (from prior empirical run)

A previous run of this exact build (log preserved at
`docs/build/build-log-warm.txt`, 112 lines, dated before this subtask) finished
with `build succeeded, 81 warnings.` The categories observed:

| Category | Count (approx, prior run) | Origin |
|---|---|---|
| `toctree contains reference to nonexisting document` | 5 | `index.rst` line 22 — basenames `introduction`, `getting-started`, `architecture`, `service-layer`, `api-reference`. Predicted in the scaffolding audit (`docs/_plan/sphinx_scaffolding_audit.md` §4). |
| `WARNING: undefined label: '<name>' [ref.ref]` | ~70+ | `nitpicky=True` + extensive use of `:ref:`<bare-name>`` across `configuration.rst` (~25), `glossary.rst` (~30), `inference-models.rst` (~7), `operations.rst` (~5). Targets are anchors that would be defined on the missing pages (`getting-started`, `architecture`, `api-reference`, `svc-moderation`, `api-etag`, etc.). |
| `ERROR: Unknown target name: "<phrase>"` `[docutils]` | ≥1 | At minimum `configuration.rst:254` flags `"startup-time validation"`. Docutils-level error from a malformed `:ref:` or a stray phrase-style cross-reference. **Note:** docutils ERRORs render in the log but, in this conf.py with `nitpicky=True` only (no `-W`), do NOT cause non-zero exit. They WILL escalate under `-W`, which subtask 2 may consider. |
| `:term:` warnings | unknown until run | 50 `:term:` references in `glossary.rst` alone; some may resolve to defined terms, some may not. |
| autosectionlabel duplicate-label warnings | 0 expected on cold; possible on warm | `autosectionlabel_prefix_document = True` should prevent these, but per the user task description these "often only surface on warm rebuild" — so explicitly compare cold vs warm logs in §5 manifest. |

**Source-counting cross-check (Grep, today):**

- `:ref:`<lowercase-name>`` occurrences: 154 across the 5 source files
  (configuration=53, glossary=52, operations=35, inference-models=10, index=2, conf=2).
- `:term:` occurrences: 50 in `glossary.rst` (only).
- Explicit anchor declarations on disk (`.. _foo:`): 6 anchors —
  `infra-overview`, `ops-overview` (operations.rst), `inf-models`
  (inference-models.rst), `config-overview` (configuration.rst), `glossary`,
  `anchor-map` (glossary.rst). The five spec'd anchors expected on the
  missing pages (`introduction`, `getting-started`, `architecture`,
  `service-layer`, `api-reference`) do not exist.

---

## 5. Cold-vs-warm divergence — what to look for

The user task highlights this distinction explicitly. After both builds run,
diff the two logs and record the delta in the manifest. Specifically:

1. **autosectionlabel duplicate-label warnings**: should be absent in both
   builds because of `autosectionlabel_prefix_document = True`. If they
   appear on warm but not cold, that is a meaningful Sphinx behavior signal
   to flag for subtask 2.
2. **toctree warnings**: these fire on both cold and warm — count should be
   identical (5).
3. **Total warning count** at the bottom of each log
   (`build succeeded, N warnings.`): record cold N and warm N. A delta means
   the env cache resolved or unmasked references between runs.
4. **Build durations**: warm is expected to be faster (cached doctrees);
   record both for the manifest.

**Recommended diff command (for the manifest, not as a fix):**
```bash
diff -u docs/build/build-log-cold.txt docs/build/build-log-warm.txt > docs/build/cold-vs-warm.diff || true
```
The `|| true` prevents the diff's nonzero exit (any diff at all returns 1)
from breaking a script.

---

## 6. Failure modes & decision tree

| Symptom at | Action | Stop or continue? |
|---|---|---|
| Step 1 — install fails (network, permission, version conflict) | Capture the error verbatim into the manifest under `install_error:`; if `python -c "import sphinx, sphinx_rtd_theme"` already succeeds, treat install as confirmed and proceed. | Continue if imports succeed; otherwise STOP and hand the install error to subtask 2 (it owns recovery). |
| Step 2 — `sphinx-build --version` fails (`command not found`, `ImportError`) | Try `python -m sphinx --version`. If that also fails, the install is genuinely broken. | STOP. Hand to subtask 2. |
| Step 3 / 4 — `sphinx-build` exits **non-zero** (build failure, not warning) | Capture full stderr+stdout into the relevant log. `sphinx-build` returns non-zero only on (a) a true build failure, (b) `-W` promoted warnings, or (c) configuration errors. With current `conf.py` and no `-W`, only (a) and (c) apply. | STOP per the user task: "if `sphinx-build` exits non-zero (build failure, not warning), capture the error and stop — subtask 2 owns recovery." Mark `cold_exit` / `warm_exit` and complete the manifest with whatever was captured. |
| Step 3 / 4 — `sphinx-build` exits zero with warnings (the expected case based on prior run) | Save logs verbatim. Proceed. | Continue. The whole point of the warning capture is to feed subtask 2. |
| Step 5 — page count is 0 or missing critical files (no `index.html`) | Record the anomaly; this contradicts a "succeeded" exit code and likely means the build was killed mid-render. | STOP. Hand to subtask 2 with the partial manifest. |

**Hard rule (from the user task, restated):** under no circumstance edit
`docs/source/*.rst`, `docs/source/conf.py`, or `docs/source/_static/*` while
recovering from any of the above. This subtask is install + execute +
capture; recovery (including any source edits to fix warnings or errors) is
owned by subtask 2.

---

## 7. Deliverable specification — handoff manifest to subtask 2

Write `docs/build/build-manifest.md` with the following fields, all derived
from steps 1–5 above:

```yaml
# (Format shown as YAML for clarity; emit as a markdown table or YAML block,
# whichever subtask 2 prefers.)

versions:
  sphinx: "8.2.3"                    # from `import sphinx; sphinx.__version__`
  sphinx_rtd_theme: "3.0.2"          # ditto
  docutils: "0.21.2"                 # ditto
  python: "3.12.7"                   # `python --version`
  install_path: "uv|uv-pip|pip|preinstalled"   # which branch of §3 step 1 was taken

invocation:
  sphinx_build_version_line: "sphinx-build 8.2.3"  # raw stdout from `sphinx-build --version`
  invoked_via: "sphinx-build|python -m sphinx|uv run sphinx-build"

cold_build:
  command: "sphinx-build -b html docs/source docs/build/html"
  log_path: "docs/build/build-log-cold.txt"
  exit_code: <int>
  log_byte_size: <int>
  duration_seconds: <float, optional>
  warning_count_reported_by_sphinx: <int>      # parse the `build succeeded, N warnings.` line
  error_count_reported_by_sphinx: <int>        # if the line says `build failed` or counts errors
  notable_categories:                           # rough classification, no fixes
    toctree_missing_doc: <int>
    nitpicky_undefined_label: <int>
    docutils_unknown_target: <int>
    other: <int>

warm_build:
  command: "sphinx-build -b html docs/source docs/build/html  (after rm -rf docs/build/html)"
  log_path: "docs/build/build-log-warm.txt"
  exit_code: <int>
  warning_count_reported_by_sphinx: <int>
  duration_seconds: <float, optional>
  notable_differences_vs_cold: <free text or pointer to cold-vs-warm.diff>

artifacts:
  page_count_html: <int>            # count of *.html files at top level of docs/build/html/
  pages:
    - index.html
    - configuration.html
    - glossary.html
    - inference-models.html
    - operations.html
    - genindex.html
    - search.html
  ancillary:
    - _sources/
    - _static/
    - objects.inv
    - searchindex.js

handoff:
  prepared_for: "build subtask 2 (recovery / warning triage)"
  files_modified_this_subtask:
    - docs/build/build-log-cold.txt              # NEW — written by this subtask
    - docs/build/build-log-warm.txt              # OVERWRITTEN — prior content from earlier run is replaced
    - docs/build/build-manifest.md               # NEW
    - docs/build/cold-vs-warm.diff               # NEW (optional, see §5)
    - docs/build/html/...                        # rewritten by sphinx-build
  files_NOT_modified:
    - docs/source/conf.py
    - docs/source/index.rst
    - docs/source/glossary.rst
    - docs/source/configuration.rst
    - docs/source/inference-models.rst
    - docs/source/operations.rst
    - docs/source/_static/.gitkeep
```

The manifest plus the two log files (and optionally the diff) are the
complete deliverable. Subtask 2 should be able to start triage with no
further information from this subtask.

---

## 8. Out-of-scope / explicit non-actions (restated)

This is a capture-only subtask. Even when the executor sees obvious fixes
during the build, **none** of the following may happen here:

- No `nitpick_ignore` / `nitpick_ignore_regex` additions to `conf.py`.
- No `-W` flag on the rebuild attempts.
- No authoring or stubbing of the 5 missing pages.
- No edits to existing `:ref:` references in the prose pages.
- No deletion of unused anchors.
- No fixes to the docutils `Unknown target name` ERROR
  (`configuration.rst:254`).
- No reordering of the toctree.
- No theme swap (alabaster fallback) regardless of warnings.
- No attempt to silence ANSI color codes in the captured logs.

If during execution any of these temptations arises, document the
observation as free-text in the manifest's `handoff:` section under a
`subtask_2_hints:` subkey — but do not act on it.

---

## 9. Invocation order & a single-pass executable script

Once the executor has read this plan and understands the §2 reconciliation,
the canonical command sequence (assuming current repo state — no uv, sphinx
already installed) is:

```bash
# from repo root
set -euo pipefail

# ---- Step 1: confirm install, capture versions ----
python -c "import sphinx, sphinx_rtd_theme, docutils; \
  print(f'sphinx={sphinx.__version__}'); \
  print(f'sphinx_rtd_theme={sphinx_rtd_theme.__version__}'); \
  print(f'docutils={docutils.__version__}')" \
  | tee /tmp/versions.txt

# ---- Step 2: verify sphinx-build invocation ----
python -m sphinx --version | tee /tmp/sphinx-build-version.txt

# ---- Step 3: cold build ----
rm -rf docs/build
mkdir -p docs/build
set +e
python -m sphinx -b html docs/source docs/build/html 2>&1 \
  | tee docs/build/build-log-cold.txt
COLD_EXIT=${PIPESTATUS[0]}
set -e
echo "cold-exit=$COLD_EXIT"

# ---- Step 4: warm build ----
rm -rf docs/build/html
set +e
python -m sphinx -b html docs/source docs/build/html 2>&1 \
  | tee docs/build/build-log-warm.txt
WARM_EXIT=${PIPESTATUS[0]}
set -e
echo "warm-exit=$WARM_EXIT"

# ---- Step 5: page count ----
PAGE_COUNT=$(find docs/build/html -maxdepth 1 -name '*.html' -type f | wc -l)
echo "page-count=$PAGE_COUNT"

# ---- Step 6: assemble manifest (manual or templated; format per §7) ----
# Optional: emit the cold-vs-warm diff
diff -u docs/build/build-log-cold.txt docs/build/build-log-warm.txt \
  > docs/build/cold-vs-warm.diff || true
```

The `set -e` is paused around the two `sphinx-build` invocations because we
explicitly want to capture non-zero exits in `COLD_EXIT` / `WARM_EXIT` and
write the manifest before halting. Step 6 (manifest emission) must either
be the next thing to run or be wrapped in a final-handler.

---

## 10. Cross-references

- Scaffolding audit (predecessor subtask): `docs/_plan/sphinx_scaffolding_audit.md`
  — definitive source for what `conf.py` and `index.rst` contain and the 9-vs-4
  toctree-vs-disk gap.
- Glossary anchor map: `docs/source/glossary.rst` lines 23–32 + `:ref:`anchor-map``
  — independent corroboration of the 5 missing pages and their forward-referenced
  anchors.
- Prior empirical build log (to be overwritten by this subtask):
  `docs/build/build-log-warm.txt`, 112 lines, ends `build succeeded, 81 warnings.`
- Active Python interpreter: `C:\Users\yxinl\miniforge3\python` 3.12.7.
