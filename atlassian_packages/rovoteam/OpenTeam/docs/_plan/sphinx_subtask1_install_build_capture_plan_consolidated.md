# Sphinx Subtask 1 — Install + Build + Capture — Consolidated Plan

**Plan author:** assistant (Claude), consolidating two parallel-flow plans plus newly-verified evidence
**Plan date:** 2026-05-04
**Repo:** `C:\Users\yxinl\OneDrive\Projects\PythonProjects\CoreProjects\OpenTeam`
**Subtask scope:** install Sphinx + sphinx-rtd-theme, run cold + warm `sphinx-build` against `docs/source/`, save raw logs and a version manifest. Hand off to **subtask 2** (warning triage / recovery). **No fixes. No edits to existing source files.**

---

## 0. Consolidation note

This document consolidates two upstream plans that addressed the same subtask in parallel:

- **Flow 0** — `docs/_plan/sphinx_subtask1_install_build_capture_plan.md` (560 lines). Strongest on: install-option matrix reasoning, exit-code-vs-log-text discipline, cold/warm semantics, failure-handling matrix.
- **Flow 1** — `docs/_plan/sphinx_initial_build_subtask1_plan.md` (513 lines). Strongest on: current-state-aware prediction (6 warnings, not 81), log-preservation rename step, awareness that a prior subtask 2 has already executed.

Both flows independently and correctly identified that **two premises in the user request do not hold** (no `pyproject.toml`/`uv.lock`/`CONSOLIDATION_NOTES`; only 5 RST files exist, not 8). They agree on Option C as the recommended install path, on `2>&1 | tee` + `${PIPESTATUS[0]}` as the canonical capture pattern, and on the deliverable shape.

**One substantive divergence**, reconciled here: Flow 0 predicted ~80 warnings + 1 ERROR based on the existing `docs/build/build-log-warm.txt`. Flow 1 predicted **6 warnings (1 docutils ERROR + 5 toctree-missing)** based on the current state of `conf.py` (which now includes a `nitpick_ignore` block suppressing 9 forward-ref anchors). **Flow 1 is correct** — the `build-log-warm.txt` on disk is *pre-triage* (now stale relative to `conf.py`); the `build-log-after-fix.txt` (post-triage, 6 warnings) is the better baseline and was independently verified at consolidation time. §5 below carries Flow 1's prediction.

**Independent verifications added at consolidation time** (not in either upstream):

- `python -c "import sphinx, sphinx_rtd_theme, docutils; print(...)"` succeeds against system Python (`/c/Users/yxinl/miniforge3/python`, Python 3.12.7) and reports `sphinx==8.2.3`, `sphinx_rtd_theme==3.0.2`, `docutils==0.21.2`. **System Python already satisfies the install dependency.** This adds **Option 0** (use system Python, no install at all) to §4 — the cheapest path that the user request also accepts since the deliverable is "record exact installed versions," not "produce a fresh isolated env."
- `uv` confirmed absent from `PATH` at consolidation time (matches both flows' assumptions).
- Current `docs/build/html/` contains exactly **7** `.html` files (verified by `find`): `index, configuration, inference-models, operations, glossary, genindex, search`. Sharpens Flow 1's "~8 give or take" estimate to a known number.
- A *prior* consolidation file already exists at `docs/_plan/sphinx_initial_build_subtask1_plan_consolidated.md` (218 lines). It consolidated Flow 1 alone (Flow 0 had not yet been produced) plus the system-Python finding. **This document supersedes it** by additionally integrating Flow 0's depth on install-option reasoning, exit-code discipline, and failure-matrix coverage. The prior consolidation is preserved on disk but is now the older artifact.

**Integration value:** moderate. The two upstream flows agree on ~80% of substance; the meaningful delta is Flow 1's correct prediction + preservation step, which Flow 0 missed. Capturing that delta with evidence (conf.py inspection + existing post-fix log) is the principal value-add. A second value-add is **Option 0** from independent verification, which materially shortcuts the install step. Beyond those, this consolidation primarily harmonizes terminology and tightens prose.

---

## 1. TL;DR — what to do, what's different from the literal request

**Do:** record current Sphinx + sphinx-rtd-theme + docutils versions (already importable from system Python — Option 0), or create a project-local venv if isolation is preferred (Option C). Rename the existing `docs/build/build-log-warm.txt` to `build-log-warm-pre-triage.txt` so the prior log is preserved (it is upstream evidence cited by `sphinx_warning_triage_plan_consolidated.md`). Run two `sphinx-build` invocations (cold then warm) against `docs/source/`, capturing full stdout+stderr to `docs/build/build-log-cold.txt` and `docs/build/build-log-warm.txt`. Write a version manifest, count the HTML files, write a handoff summary, hand off to subtask 2.

**Do not:** touch any file under `docs/source/` (`conf.py`, `index.rst`, `glossary.rst`, `configuration.rst`, `inference-models.rst`, `operations.rst`). Do not invent stub `.rst` pages. Do not lower `nitpicky` or alter `nitpick_ignore`. Do not delete `docs/build/.doctrees/` between cold and warm runs (would defeat warm semantics). Do not commit anything.

**Three premises in the user request that do not hold cleanly** (substitutions documented in §3):

1. *"uv-native (per CONSOLIDATION_NOTES item #3 and pyproject.toml)"* — none of `pyproject.toml`, `uv.lock`, or `CONSOLIDATION_NOTES*` exists in the repo, and `uv` is not on `PATH`. `uv add --dev …` would hard-fail. Substitute Option 0 (system Python) or Option C (`python -m venv .venv-docs` + `pip install`).
2. *"the 8 prose pages"* — only **3** prose pages exist on disk (`configuration.rst`, `inference-models.rst`, `operations.rst`) plus `index.rst` and `glossary.rst` for a total of **5** `.rst` files. The "8 prose pages" wording is parent-spec leakage. The "do not modify" constraint applies to whatever exists.
3. *"subtask 2 owns recovery"* — a prior triage subtask has *already* executed against this repo (the post-triage `build-log-after-fix.txt` and the `nitpick_ignore` block in `conf.py` are its outputs). The current request's "subtask 2" is a fresh subtask under the current parent spec; the older subtask-2 artifacts are informational only and are surfaced in the handoff summary, not used to skip work.

None of these warrants pausing for confirmation. Each is recorded in the handoff.

---

## 2. Pre-flight findings (verified at consolidation time)

### 2.1 `docs/source/` inventory

```
docs/source/
├── _static/                       (per audit, .gitkeep only)
├── conf.py                        ← exists (~7.7 KB, validated by prior audit)
├── index.rst                      ← exists, toctree at lines 22-34 (9 entries)
├── configuration.rst              ← exists (~104 KB, foundation, read-only)
├── inference-models.rst           ← exists (~58 KB, foundation, read-only)
├── operations.rst                 ← exists (~49 KB, foundation, read-only)
└── glossary.rst                   ← exists (~36 KB; line 13 already fixed by prior triage)
```

The toctree at `index.rst:22` lists 9 page basenames; **5 are MISSING** on disk:

| toctree entry      | on disk?    |
|--------------------|-------------|
| `introduction`     | **MISSING** |
| `getting-started`  | **MISSING** |
| `architecture`     | **MISSING** |
| `service-layer`    | **MISSING** |
| `inference-models` | exists      |
| `configuration`    | exists      |
| `api-reference`    | **MISSING** |
| `operations`       | exists      |
| `glossary`         | exists      |

### 2.2 `conf.py` settings that materially shape build output

Verified by direct read of `docs/source/conf.py`:

- `extensions = ['sphinx.ext.autosectionlabel', 'sphinx.ext.intersphinx']` (lines 30-39).
- `autosectionlabel_prefix_document = True` (line 47) — auto-generated section labels are doc-prefixed; **duplicate-label warnings across pages are suppressed**.
- `nitpicky = True` (line 52) — unresolved cross-references become warnings (not silent drops). **Dominant warning generator on this docset by default.**
- `nitpick_ignore = [...]` (lines 94-129) — **9 `('std:ref', '<anchor>')` tuples** suppressing the 9 forward-referenced anchor names (`introduction`, `getting-started`, `gs-feature-flags`, `architecture`, `arch-debug-trace`, `svc-moderation`, `api-reference`, `api-etag`, `api-debug-trace`). Each tuple has an inline comment naming the citing files and line numbers. **This block is what reduces `[ref.ref]` warnings from ~74 (pre-triage) to 0 (post-triage).**
- `master_doc = 'index'` (line 132).
- `html_theme = 'sphinx_rtd_theme'` (line 138) — the install dependency for this subtask.
- `intersphinx_mapping = {}` (line 159) — extension is loaded but does no network resolution.

### 2.3 Repo-level inventory (uv premise + system Python check)

| Artifact                                  | Status                                                         |
|-------------------------------------------|----------------------------------------------------------------|
| `pyproject.toml` at repo root             | **NO** — `Glob **/pyproject.toml` → 0 results                  |
| `pyproject.toml` under `docs/`            | **NO**                                                         |
| `uv.lock`                                 | **NO**                                                         |
| `CONSOLIDATION_NOTES*` (any path)         | **NO** — `Glob **/CONSOLIDATION_NOTES*` → 0 results            |
| `uv` on `PATH`                            | **NO** — `which uv` → not found at consolidation time          |
| `python` on `PATH`                        | **YES** — `/c/Users/yxinl/miniforge3/python`, Python 3.12.7    |
| `sphinx` importable from system Python    | **YES** — `8.2.3`                                              |
| `sphinx_rtd_theme` importable             | **YES** — `3.0.2`                                              |
| `docutils` importable                     | **YES** — `0.21.2`                                             |

The `conf.py` header (lines 17-24) itself acknowledges the missing-pyproject state: *"No pyproject.toml is checked in alongside this docset… there is no pyproject.toml [project].version available at scaffold time."*

**The system-Python availability is decisive for §4.** The `uv add --dev` step in the request expresses intent ("install + record versions"); that intent is already satisfied by the existing system Python interpreter. The plan offers Option 0 (use system Python directly, zero install) and Option C (project-local venv, isolated) as both viable.

### 2.4 `docs/build/` — existing artifacts on disk

```
docs/build/
├── build-log-after-fix.txt   (post-triage, 6 warnings — Sphinx 8.2.3 against current source)
├── build-log-warm.txt        (PRE-triage, 81 warnings — stale relative to current conf.py)
└── html/                     (current — from the post-fix build, 7 HTML files)
```

The `html/` listing confirmed by `find docs/build/html -name '*.html'`: `configuration.html`, `genindex.html`, `glossary.html`, `index.html`, `inference-models.html`, `operations.html`, `search.html` — **exactly 7 `.html` files**, plus `_sources/`, `_static/`, `objects.inv`, `searchindex.js`.

**Implication:** the directory is non-empty and contains evidence cited by upstream plans. To produce a clean cold build, this plan deletes `docs/build/html/` *and* `docs/build/.doctrees/` (if present) before the cold run — but **renames** the existing `build-log-warm.txt` to `build-log-warm-pre-triage.txt` first. The rename is a content-preserving operation and does not violate the "do not modify existing files" constraint (which targets source/config files, not log artifacts in a build output directory). Without the rename, Step 6 would clobber the pre-triage log that `sphinx_warning_triage_plan_consolidated.md §1` cites as evidence for "Δ = -75 warnings."

### 2.5 Prior plans on disk (which this consolidation complements)

- `docs/_plan/sphinx_scaffolding_audit.md` — pre-build inventory; identifies the 5 missing toctree pages and read-only foundation status.
- `docs/_plan/sphinx_build_capture_plan.md` (456 lines) — earliest plan for this subtask.
- `docs/_plan/sphinx_initial_build_plan.md` (520 lines) — second-iteration plan.
- `docs/_plan/sphinx_subtask1_install_build_capture_plan.md` (560 lines) — **Flow 0 input** to this consolidation.
- `docs/_plan/sphinx_initial_build_subtask1_plan.md` (513 lines) — **Flow 1 input** to this consolidation.
- `docs/_plan/sphinx_initial_build_subtask1_plan_consolidated.md` (218 lines) — *prior* consolidation (Flow 1 + system-Python finding only, before Flow 0 existed). Superseded by this document.
- `docs/_plan/sphinx_warning_triage_plan_consolidated.md` — subtask-2 plan + post-execution verification (cites `build-log-warm.txt` and `build-log-after-fix.txt` for the Δ = -75 claim).
- `docs/_plan/sphinx_warning_triage_subtask2_deliverable.md` — prior subtask-2 deliverable artifact.

---

## 3. Discrepancies with the user request — and how each is handled

| # | Premise in request | Reality in repo | Plan's handling |
|---|--------------------|-----------------|-----------------|
| 1 | "uv-native … per CONSOLIDATION_NOTES item #3 and pyproject.toml" | None of those artifacts exist; `uv` not on PATH | §4 substitutes Option 0 (system Python — already satisfies dep) or Option C (`python -m venv .venv-docs` + `pip install`); intent (recorded versions, working `sphinx-build`) preserved |
| 2 | `uv add --dev sphinx sphinx-rtd-theme` | Would hard-fail with `error: No \`pyproject.toml\` found` | §6 Step 2: Option 0 needs no install; Option C uses `pip install` inside `.venv-docs/` |
| 3 | `uv run sphinx-build --version` | `uv` unavailable | §6 Step 3: `python -m sphinx --version` (Option 0) or `.venv-docs/Scripts/sphinx-build --version` (Option C) |
| 4 | `uv run sphinx-build -b html …` | same | §6 Steps 5 & 6: same substitution |
| 5 | "the 8 prose pages" — implied don't-edit list | Only 3 prose + index + glossary on disk (5 RST total) | §9 compliance: do-not-modify applies to whatever exists; do not stub the 5 missing pages |
| 6 | "if `sphinx-build` exits non-zero (build failure, not warning), capture the error and stop" | Prior baselines show **exit 0** even with WARNING + docutils ERROR text in log; `nitpicky` does not flip exit code without `-W`, and we do not pass `-W` | §7 failure matrix: only **exit code ≠ 0** triggers stop; warnings + docutils ERROR text in the log are normal here |
| 7 | "Sphinx warnings can vary between cold and warm builds (autosectionlabel-duplicate)" | True in general; here `autosectionlabel_prefix_document = True` already mutes that class. Toctree warnings identical cold/warm; `nitpick_ignore`-suppressed refs identical cold/warm | §6 still runs both builds and captures both verbatim, exactly as requested. Subtask 2 owns the diff. |
| 8 | "subtask 2 owns recovery" | Prior subtask 2 (different parent spec) has already landed `nitpick_ignore` + `glossary.rst:13` fix. Post-triage log shows 6 warnings | Plan respects current request's numbering: this run's output goes to the *current* spec's subtask 2. Pre-existing artifacts are surfaced but not consumed. |

**None of these warrants halting before execution.** Each is an accounting / install-path / framing issue, not "the build cannot run."

---

## 4. Install strategy

### 4.1 Hard constraints

- Must produce *recorded, exact* versions of `sphinx`, `sphinx-rtd-theme`, `docutils` (the request explicitly calls out `docutils` because its warning phrasing shifts between minor versions).
- Must not modify any file under `docs/source/`.
- Must not create a repo-root `pyproject.toml`. That would pyproject-ify the *whole repo*, far beyond the scope of "install + build + capture."
- Should be re-runnable by subtask 2 without re-installing.

### 4.2 Options considered

| # | Approach | Tradeoffs |
|---|----------|-----------|
| **0** | **Use system Python directly.** `python` already imports `sphinx==8.2.3`, `sphinx_rtd_theme==3.0.2`, `docutils==0.21.2` (verified §2.3). | **Zero install step. Cheapest path. Manifest is `pip show` / `pip freeze` against the same interpreter. Accepts host's Python as the reproducibility boundary; less portable across machines but adequate for one-shot capture.** |
| A | Bootstrap `uv` (`pip install --user uv`), then `uv tool install sphinx --with sphinx-rtd-theme` | Closest to "uv-native" *intent*. Tool install is host-global (bypasses pyproject), leaves `%USERPROFILE%\.local\share\uv\tools\…` outside repo (low reproducibility). Adds a host-level dependency. |
| B | Bootstrap `uv`, then `uv venv .venv-docs` + `uv pip install sphinx sphinx-rtd-theme` | Project-local; closest to "uv add --dev" *spirit*. Still needs uv bootstrap. Functionally equivalent to Option C downstream. |
| **C** | **`python -m venv .venv-docs` + `pip install sphinx sphinx-rtd-theme`** | **Pure stdlib + pip; no host-tool dep; project-local; cleanest manifest via `pip freeze`. Most reproducible across machines. Recommended default if isolation matters.** |
| D | `pip install --user sphinx sphinx-rtd-theme` against system Python | Pollutes user-site for other projects on host. **Not recommended.** |
| E | `pipx install sphinx --include-deps` + `pipx inject sphinx sphinx-rtd-theme` | Clean isolation; depends on pipx availability. |

### 4.3 Recommendation

**Two acceptable paths**, depending on the executor's priority. Both produce the same on-disk deliverables in `docs/build/`.

- **Option 0** (system Python) — pick this if the goal is *just to produce the deliverable as fast as possible* and the host Python is the accepted reproducibility boundary. The user request's wording ("record the exact installed versions … for the build report") is satisfied with **zero new files at the repo root**. This is the cheatsheet's primary form (§10).
- **Option C** (project-local venv) — pick this if the goal is *isolated, machine-independent reproducibility*. Adds `.venv-docs/` at repo root (a tooling directory; not a source/config file, so does not violate the "do not modify existing files" constraint). Substitute `python` → `.venv-docs/Scripts/python` and `sphinx-build` → `.venv-docs/Scripts/sphinx-build` in every command; behavior is otherwise identical.

If the team strongly prefers a uv-native install for the dev manifest, Option B is interchangeable with Option C; only the install command line changes (`uv pip install …` instead of `pip install …`). Once a venv exists at `.venv-docs/`, the downstream `sphinx-build` invocation is the same.

### 4.4 Idempotency & artifact preservation

- (Option C only) `.venv-docs/` is created with `[ -d .venv-docs ] || python -m venv .venv-docs` so re-runs reuse it.
- The two existing build logs (`build-log-warm.txt`, `build-log-after-fix.txt`) are preserved before this run executes:
  - `build-log-warm.txt` → `build-log-warm-pre-triage.txt` (rename; content preserved verbatim).
  - `build-log-after-fix.txt` is uniquely-named already; left untouched.
- `docs/build/.doctrees/` is deleted before the cold run so the cold pass really is cold.
- `docs/build/html/` is deleted before each build; cold removes both `html` + `.doctrees`, warm removes only `html` so the doctree cache persists per the user request.

### 4.5 `.gitignore` consideration (Option C)

`.venv-docs/` should be gitignored. **This subtask does not edit `.gitignore`** — it is an existing file, and tracking-or-not of the venv does not affect the build. Subtask 2 (or a later cleanup) can decide.

---

## 5. Expected build signals (predicted)

Triage is **subtask 2's job, not this subtask's**. Predicting the shape of the logs lets the executor distinguish "noisy but successful" from "actual hard failure."

### 5.1 Predicted warnings (high confidence, current source state)

The current source state on disk reflects post-triage fixes: `conf.py` has the 9-tuple `nitpick_ignore` block, and `glossary.rst:13` is fixed. The reference baseline is therefore `docs/build/build-log-after-fix.txt`, which ends with `build succeeded, 6 warnings.` — **not** the older `docs/build/build-log-warm.txt` (81 warnings, pre-triage).

**Expected post-fix warning count: 6** for both cold and warm. If this run materially diverges (e.g. 81 warnings reappear, or 0), subtask 2 should investigate why (drift in `conf.py`, Sphinx version change, etc.).

| Warning class | Count expected | Why |
|---------------|---------------:|-----|
| `toctree contains reference to nonexisting document` | 5 | One per missing page (`introduction`, `getting-started`, `architecture`, `service-layer`, `api-reference`). Fires regardless of `nitpicky`. |
| docutils `ERROR: Unknown target name: "Startup-time validation"` | 1 | At `configuration.rst:254`; foundation page is read-only so this remains escalated. **Note:** this is a docutils-level ERROR line in the log; it does **not** flip Sphinx's exit code under default behavior. |
| `[ref.ref]` undefined-label | 0 | All 9 unique forward-ref anchors are suppressed via `nitpick_ignore` in `conf.py` (lines 94-129). |
| Duplicate-label | 0 | `autosectionlabel_prefix_document = True`. |
| Intersphinx | 0 | `intersphinx_mapping = {}`. |

**Predicted HTML page count = 7** (verified against current `docs/build/html/`): `index.html`, `configuration.html`, `inference-models.html`, `operations.html`, `glossary.html`, `genindex.html`, `search.html`. The 5 missing toctree pages are not generated. (Earlier upstream estimate was "~8 give or take"; current state confirms 7. Off-by-one was due to `objects.inv` and `searchindex.js` not being `.html`.)

**Predicted exit code = 0** for both cold and warm. `nitpicky = True` does **not** flip exit code on its own; only `-W` would, and we are not passing `-W`.

### 5.2 Hard-failure shapes (these mean HTML did NOT generate)

The only outcomes that justify stopping before completion:

- `ExtensionError: Could not import extension sphinx.ext.autosectionlabel` — Sphinx itself didn't install correctly.
- `ThemeError: no theme named 'sphinx_rtd_theme' found` — `sphinx-rtd-theme` install failed silently.
- `Could not import extension ...` for any other extension — install incomplete.
- `MasterDocNotFoundError` — possible only if `index.rst` was renamed or moved.
- Hard RST parse abort — possible but unlikely (prior runs parsed all 5 files cleanly).

In all these cases: exit code is non-zero, HTML output is incomplete. Per the user request: **stop, capture the log, hand off. Do not attempt fixes.**

### 5.3 Cold vs warm differences to expect on this docset

Mechanism: a cold build builds the doctree from scratch in one pass; a warm build re-uses cached doctrees from `docs/build/.doctrees/` and re-resolves cross-references. Some warning classes only surface during the resolution phase against a fully-populated cache.

On this docset specifically:

- **Toctree-missing warnings:** identical between cold and warm (early-pass resolution).
- **`nitpick_ignore`-suppressed refs:** identical (suppression evaluated at resolve time on both paths).
- **Duplicate-label warnings:** unlikely on either pass (`autosectionlabel_prefix_document = True` mutes them). Capture both anyway — explicit `.. _foo:` anchors that happen to collide could still trigger, though none are known on this docset.
- **`[ref.ref]` warnings (if any leaked past suppression):** may differ in *order* but not count; resolver is deterministic per pass.

The user request specifies the warm log is canonical. Subtask 2 will diff cold vs warm; this subtask just captures both faithfully.

### 5.4 Why `rm -rf docs/build/html` between builds (NOT `.doctrees`)

The user request says delete only `docs/build/html` between cold and warm. This deletes only the *output HTML*, not the cached doctrees under `docs/build/.doctrees/`. **That is intentional and correct** for measuring "warm rebuild" warnings: the doctree cache persists, re-resolution runs against a fully-populated cache, and warm-only diffs surface.

**Do not** delete `docs/build/.doctrees/` between runs — that converts the warm build into a second cold build and defeats the purpose.

---

## 6. Step-by-step execution

All commands assume the working directory is the repo root: `C:\Users\yxinl\OneDrive\Projects\PythonProjects\CoreProjects\OpenTeam`. **Bash syntax** (the platform's primary shell per `CLAUDE.md`). PowerShell variant in §6-bis. The cheatsheet in §10 shows Option 0 (system Python); for Option C, substitute `python` → `.venv-docs/Scripts/python` and `sphinx-build` → `.venv-docs/Scripts/sphinx-build`.

### Step 1 — Preserve existing logs

```bash
# Rename the existing pre-triage warm log so this subtask's logs can land at
# the canonical names without overwriting prior-subtask evidence.
[ -f docs/build/build-log-warm.txt ] && \
  mv docs/build/build-log-warm.txt docs/build/build-log-warm-pre-triage.txt

# build-log-after-fix.txt is uniquely named already; leave it untouched.
ls -la docs/build/
```

**Why preserve, not overwrite:** the existing `build-log-warm.txt` is upstream evidence cited by `sphinx_warning_triage_plan_consolidated.md §1` and the consolidation report's "Δ = -75 warnings" verification depends on this log being on-disk and content-intact. A rename keeps content; an overwrite would destroy provenance.

### Step 2 — Install Sphinx + sphinx-rtd-theme

**Option 0 (system Python — recommended for fastest path):** *no install needed.* Skip to Step 3.

**Option C (project-local venv — recommended for isolation):**

```bash
# 2a. create the venv (idempotent)
[ -d .venv-docs ] || python -m venv .venv-docs

# 2b. upgrade pip inside the venv
.venv-docs/Scripts/python -m pip install --upgrade pip

# 2c. install Sphinx + theme; pin nothing — manifest captures whatever lands
.venv-docs/Scripts/pip install sphinx sphinx-rtd-theme 2>&1 \
  | tee docs/build/install-log.txt
INSTALL_EXIT=${PIPESTATUS[0]}
[ "${INSTALL_EXIT}" -ne 0 ] && echo "INSTALL FAILED — STOP" && exit "${INSTALL_EXIT}"
```

**Expected (Option C):** install succeeds; final lines mention `Successfully installed sphinx-X.Y.Z sphinx-rtd-theme-A.B.C docutils-D.E.F` plus transitive deps (`Pygments`, `Jinja2`, `MarkupSafe`, `imagesize`, `babel`, `requests`, `snowballstemmer`, `alabaster`, `urllib3`, `certifi`, `charset-normalizer`, `idna`, `packaging`, `roman-numerals-py`, `sphinxcontrib-*`).

**On failure (Option C):** install log already captured at `docs/build/install-log.txt`. Stop. Hand off the log + the failure mode. Do not attempt the build.

### Step 3 — Verify install

```bash
# Option 0
python -m sphinx --version

# Option C
# .venv-docs/Scripts/sphinx-build --version
```

**Expected:** a single line `sphinx-build X.Y.Z` (Option 0 should print `sphinx-build 8.2.3`). Exit 0.

**On failure** (`sphinx-build: command not found`, `ImportError`): capture stderr, stop, hand off. For Option C, also run `.venv-docs/Scripts/python -c 'import sphinx; print(sphinx.__version__)'` to disambiguate "shim missing" from "import broken."

### Step 4 — Capture version manifest

```bash
mkdir -p docs/build
{
  echo "=== Sphinx subtask 1 — version manifest ==="
  echo "Generated: $(date -Iseconds)"
  echo "Host: $(uname -a 2>/dev/null || echo 'win32')"
  echo "PWD:  $(pwd)"
  echo "Install option: 0 (system Python) | C (.venv-docs)"   # fill in which one
  echo
  echo "--- python --version ---"
  python --version
  echo
  echo "--- sphinx-build --version ---"
  python -m sphinx --version
  echo
  echo "--- pip show sphinx sphinx-rtd-theme docutils ---"
  python -m pip show sphinx sphinx-rtd-theme docutils
  echo
  echo "--- pip freeze (full env inventory) ---"
  python -m pip freeze
} > docs/build/version-manifest.txt 2>&1
```

(For Option C, replace `python` → `.venv-docs/Scripts/python`.)

`docutils` is recorded explicitly because the user request flags it: docutils warning phrasing has shifted across minor versions and reproducibility-sensitive triage needs the exact version under test.

### Step 5 — Cold build

```bash
# True cold build: delete html AND doctree cache.
rm -rf docs/build/html docs/build/.doctrees

# 2>&1 merges streams BEFORE the pipe so tee captures both in emission order.
# tee always exits 0; ${PIPESTATUS[0]} (bash-specific) recovers the real exit code.
python -m sphinx -b html docs/source docs/build/html 2>&1 \
  | tee docs/build/build-log-cold.txt
COLD_EXIT=${PIPESTATUS[0]}
echo "EXIT_CODE=${COLD_EXIT}" >> docs/build/build-log-cold.txt
echo "Cold build exit code: ${COLD_EXIT}"
```

**Notes on the redirection:**

- `2>&1` merges stderr into stdout *before* the pipe — `tee` writes both in emission order. That is what "verbatim stdout+stderr" means in the request.
- Appending `EXIT_CODE=...` to the log makes the exit code self-contained inside the artifact (subtask 2 doesn't need a separate file).
- `${PIPESTATUS[0]}` is bash-specific. For PowerShell, see §6-bis.

**Acceptable cold-build outcomes:**

| `COLD_EXIT` | Meaning                                                                                  | Action                                                                 |
|-------------|------------------------------------------------------------------------------------------|------------------------------------------------------------------------|
| `0`         | Build succeeded; warnings recorded in log.                                               | Proceed to Step 6.                                                     |
| `1`         | Build failed (extension import / theme not found / RST syntax / master-doc missing).     | **Stop. Hand off cold log + manifest. Do NOT proceed to warm build.**  |
| `2`         | `conf.py` configuration error.                                                           | Stop. Hand off.                                                        |

**Critical:** `nitpicky = True` does **not** flip exit code on its own — without `-W`, warnings remain warnings. Even a docutils `ERROR:` line in the log doesn't necessarily flip exit code (the prior baselines produced one and still exited 0). **Treat the exit code, not log text, as the failure signal.**

### Step 6 — Warm build

```bash
# Per the request, remove only the HTML output. Leave .doctrees in place.
rm -rf docs/build/html

# Sanity check: confirm .doctrees survived (warm semantics depend on it).
ls -la docs/build/.doctrees/ 2>&1 | head -5 \
  || echo "WARNING: .doctrees missing — warm build will be a second cold build"

python -m sphinx -b html docs/source docs/build/html 2>&1 \
  | tee docs/build/build-log-warm.txt
WARM_EXIT=${PIPESTATUS[0]}
echo "EXIT_CODE=${WARM_EXIT}" >> docs/build/build-log-warm.txt
echo "Warm build exit code: ${WARM_EXIT}"
```

**Acceptable warm-build outcomes:**

| `WARM_EXIT` | Meaning                                                                                                  | Action                                                                                |
|-------------|----------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------|
| `0`         | Warm build succeeded.                                                                                    | Proceed to Step 7.                                                                    |
| Non-zero    | Warm-only failure (cold succeeded). Rare but possible (e.g. `:any:` resolution that succeeded cold but failed warm). | **Stop. Capture both logs. Flag in handoff as warm-only failure** — interesting signal for subtask 2. |

### Step 7 — Count generated HTML files

```bash
PAGE_COUNT=$(find docs/build/html -name '*.html' -type f | wc -l)
echo "Generated HTML page count: ${PAGE_COUNT}" | tee -a docs/build/build-log-warm.txt
```

**Expected count:** **7** files — `index.html`, `configuration.html`, `inference-models.html`, `operations.html`, `glossary.html`, `genindex.html`, `search.html`. The 5 missing toctree pages are not generated. The current `docs/build/html/` already has 7 — that is the canonical number for the present source state.

If the count differs materially (e.g. 0 or 12), capture the directory listing in the handoff and flag it.

### Step 8 — Handoff summary

```bash
{
  echo "=== Sphinx subtask 1 — handoff summary ==="
  echo "Generated: $(date -Iseconds)"
  echo "Install option used: 0 (system Python) | C (.venv-docs)"   # fill in
  echo
  echo "Cold build exit code: ${COLD_EXIT}"
  echo "Warm build exit code: ${WARM_EXIT}"
  echo "Generated HTML files: ${PAGE_COUNT}"
  echo
  echo "--- Top-level docs/build/html/ listing ---"
  ls -la docs/build/html/ 2>&1 | head -40
  echo
  echo "--- All HTML files (relative paths) ---"
  find docs/build/html -name '*.html' -type f | sort
  echo
  echo "--- WARNING / ERROR line counts ---"
  echo "Cold WARNING lines: $(grep -c 'WARNING' docs/build/build-log-cold.txt 2>/dev/null || echo 0)"
  echo "Warm WARNING lines: $(grep -c 'WARNING' docs/build/build-log-warm.txt 2>/dev/null || echo 0)"
  echo "Cold ERROR lines:   $(grep -cE '^Error|ERROR' docs/build/build-log-cold.txt 2>/dev/null || echo 0)"
  echo "Warm ERROR lines:   $(grep -cE '^Error|ERROR' docs/build/build-log-warm.txt 2>/dev/null || echo 0)"
  echo
  echo "--- Reference: prior-subtask logs preserved as ---"
  echo "  docs/build/build-log-warm-pre-triage.txt   (pre-triage warm, 81 warnings)"
  echo "  docs/build/build-log-after-fix.txt         (post-triage warm, 6 warnings)"
  echo
  echo "--- Substitutions / deviations from the literal request ---"
  echo "1. uv add --dev -> system Python (Option 0) or python -m venv .venv-docs + pip install (Option C)"
  echo "2. uv run sphinx-build -> python -m sphinx (Option 0) or .venv-docs/Scripts/sphinx-build (Option C)"
  echo "3. \"8 prose pages\" in request -> 5 .rst files actually exist (3 prose + index + glossary)"
  echo "4. Prior subtask 2 (different parent spec) already executed; its log is preserved as build-log-after-fix.txt"
} > docs/build/handoff-summary.txt
```

The handoff summary is the **single file subtask 2 should read first** — exit codes, page count, listing, WARNING/ERROR counts, deviations, and pointers to all other artifacts.

### 6-bis. PowerShell variant

PS 5.1 `2>&1` on native exes wraps stderr lines in `ErrorRecord` objects and can flip `$?` to `$false` even on success — per the `PowerShell` tool's edition guidance, **avoid `2>&1` on native executables in PS 5.1**. Use `*>` instead, which redirects all streams (stdout, stderr, info, warning, verbose, debug) to one file in stream-event order:

```powershell
# Step 5 (cold) under PowerShell — Option 0 (system Python)
Remove-Item -Recurse -Force docs/build/html, docs/build/.doctrees -ErrorAction SilentlyContinue
& python -m sphinx -b html docs/source docs/build/html `
    *> docs/build/build-log-cold.txt
$ColdExit = $LASTEXITCODE
Add-Content docs/build/build-log-cold.txt "EXIT_CODE=$ColdExit"
"Cold build exit code: $ColdExit"

# Step 6 (warm)
Remove-Item -Recurse -Force docs/build/html -ErrorAction SilentlyContinue
& python -m sphinx -b html docs/source docs/build/html `
    *> docs/build/build-log-warm.txt
$WarmExit = $LASTEXITCODE
Add-Content docs/build/build-log-warm.txt "EXIT_CODE=$WarmExit"
"Warm build exit code: $WarmExit"

# Step 7 (count)
$PageCount = (Get-ChildItem -Path docs/build/html -Recurse -Filter *.html -File).Count
Add-Content docs/build/build-log-warm.txt "Generated HTML page count: $PageCount"
```

For Option C, swap `& python -m sphinx` → `& .venv-docs/Scripts/sphinx-build.exe`. `*>` redirects every stream to the file in event order — closest equivalent to bash `2>&1`. `$LASTEXITCODE` carries the native exe's exit code untouched.

The bash form is preferred because the user request says "verbatim stdout+stderr into a saveable buffer" and bash's `tee` + `${PIPESTATUS[0]}` is the cleanest expression.

---

## 7. Failure-handling matrix (consolidated)

This is the single table to consult when something goes wrong. Every row's action is "capture and stop" — this subtask does **not** triage.

| Stage | Failure shape | Action | Hand-off contains |
|-------|---------------|--------|-------------------|
| 1. preserve | Rename of `build-log-warm.txt` fails (file lock, permission) | Stop. Don't proceed — Step 6 would clobber prior log. | error message; current `docs/build/` listing |
| 2. install (Option C) | `python -m venv` fails | Stop. | stderr from venv creation; OS / Python version |
| 2. install (Option C) | `pip install` fails (network, no binary wheel, dep conflict) | Stop. | `docs/build/install-log.txt` + stop reason |
| 3. verify | `sphinx-build --version` errors | Stop. | stderr; output of `python -c 'import sphinx; print(sphinx.__version__)'` if it works |
| 4. manifest | `pip show` / `pip freeze` errors | **Continue** — manifest is informational, not blocking | whatever was captured |
| 5. cold | `sphinx-build` exit ≠ 0 | Stop. **Do not run warm build.** | cold log only; exit code; manifest |
| 5. cold | exit = 0 but `docs/build/html/index.html` missing | Treat as anomaly even though exit was 0 | cold log; directory listing of `docs/build/html/`; manifest |
| 6. warm | `rm -rf docs/build/html` errors (permission, file lock) | Stop. | error message; current state of `docs/build/` |
| 6. warm | `sphinx-build` exit ≠ 0 (after cold succeeded) | Stop. **Flag explicitly as warm-only failure** — interesting signal for subtask 2. | both logs; both exit codes |
| 7. count | `find` returns 0 HTML files even with exit 0 | Treat as anomaly | both logs; empty `docs/build/html/` listing |

**Across every row, the rule is: capture all relevant stdout/stderr and stop.** Do not patch `conf.py`, do not edit any `.rst`, do not stub missing pages, do not change theme. Those are subtask 2's calls.

---

## 8. Deliverables manifest (what subtask 2 receives)

After this plan runs to completion (all 8 steps), `docs/build/` is:

```
docs/build/
├── install-log.txt                 ← only if Option C used and pip install ran (Step 2c)
├── version-manifest.txt            ← Python, Sphinx, sphinx-rtd-theme, docutils + full pip freeze (Step 4)
├── build-log-cold.txt              ← raw stdout+stderr of cold build, with EXIT_CODE=N appended (Step 5)
├── build-log-warm.txt              ← raw stdout+stderr of warm build, EXIT_CODE=N + page count appended (Steps 6-7)
├── build-log-warm-pre-triage.txt   ← preserved from prior run (81 warnings, pre-fix) — Step 1 rename
├── build-log-after-fix.txt         ← preserved from prior run (6 warnings, post-fix) — untouched
├── handoff-summary.txt             ← exit codes, page count, file listing, WARNING/ERROR counts, deviations (Step 8)
├── .doctrees/                      ← Sphinx doctree cache (NOT to be deleted between cold and warm)
└── html/                           ← canonical output from the warm build (~7 files)
    ├── index.html, configuration.html, inference-models.html, operations.html, glossary.html
    ├── genindex.html, search.html
    └── _static/, _images/, etc.
```

If install or build failed before Step 6, the warm log is absent and the handoff summary is partial — *that is the signal* to subtask 2 that the build stopped early. `install-log.txt` and any partial `build-log-cold.txt` are still meaningful.

**Subtask 2's expected entry point:** `docs/build/handoff-summary.txt`. From there subtask 2 picks which log to triage first and decides whether the post-fix `build-log-after-fix.txt` is still authoritative or has drifted from the new warm log.

### What this subtask does NOT deliver

- A *clean* build. Warnings are expected and not in scope to fix.
- A list of *which* warnings need fixing. Triage decisions belong to subtask 2.
- An updated `conf.py`. Even if the build reveals a config-level cause, that is subtask 2's call.
- Stubs for the 5 missing pages. The audit at `docs/_plan/sphinx_scaffolding_audit.md §4` enumerates them.
- A diff against the prior pre-triage / post-fix logs — subtask 2 owns that diff.
- Any commit, push, or PR. The user did not ask, and per the harness's git-safety rules we do not commit unless asked.

---

## 9. Compliance checklist (what we will NOT do)

Per the user request: *"do not modify ANY existing files (not the 8 prose pages, not conf.py / index.rst / glossary.rst); this subtask is install + execute + capture only."*

The plan does **not**:

- Modify or create any file under `docs/source/` (verified: every command in §6 writes only under `docs/build/`, optionally `.venv-docs/`, or stdout).
- Modify `.gitignore`, `pyproject.toml` (which doesn't exist), or any other repo-root config file.
- Touch `src/`, `test/`, `conftest.py`, or any other code directory.
- Stub or author any of the 5 missing prose pages (`introduction`, `getting-started`, `architecture`, `service-layer`, `api-reference`).
- Edit `conf.py` to lower `nitpicky`, change theme, or alter `nitpick_ignore`.
- Run `git add` / `git commit` / `git push` of any kind.
- Delete `docs/build/.doctrees/` between cold and warm runs (would defeat warm-build semantics).
- Overwrite `build-log-warm.txt` — Step 1 renames it to `build-log-warm-pre-triage.txt` first.
- Overwrite `build-log-after-fix.txt` — uniquely named, kept verbatim.

The plan **does** create:

- (Option C only) `.venv-docs/` at the repo root — a Python venv directory.
- New files under `docs/build/`: `build-log-cold.txt`, `build-log-warm.txt`, `version-manifest.txt`, `handoff-summary.txt`, optionally `install-log.txt`.
- One rename: `build-log-warm.txt` → `build-log-warm-pre-triage.txt` (content preserved verbatim).

Neither directory creation, file creation under `docs/build/`, nor a content-preserving rename qualifies as "modify an existing file" under any reasonable reading of the constraint.

---

## 10. Quick-start cheatsheet (Option 0; fastest path)

For the executor who wants the minimum viable command sequence (bash, from repo root, Option 0 — system Python). For Option C, replace `python` → `.venv-docs/Scripts/python` in every command after creating the venv.

```bash
# 0. preserve existing logs
[ -f docs/build/build-log-warm.txt ] && \
  mv docs/build/build-log-warm.txt docs/build/build-log-warm-pre-triage.txt

# 1. (Option 0) verify system Python already has the deps
python -m sphinx --version
python -c "import sphinx, sphinx_rtd_theme, docutils; \
  print(sphinx.__version__, sphinx_rtd_theme.__version__, docutils.__version__)"

# 2. version manifest
mkdir -p docs/build
{
  echo "=== version manifest ==="
  date -Iseconds
  python --version
  python -m sphinx --version
  python -m pip show sphinx sphinx-rtd-theme docutils
  echo "---"
  python -m pip freeze
} > docs/build/version-manifest.txt 2>&1

# 3. cold build (delete html AND .doctrees)
rm -rf docs/build/html docs/build/.doctrees
python -m sphinx -b html docs/source docs/build/html 2>&1 \
  | tee docs/build/build-log-cold.txt
COLD_EXIT=${PIPESTATUS[0]}
echo "EXIT_CODE=${COLD_EXIT}" >> docs/build/build-log-cold.txt
[ "${COLD_EXIT}" -ne 0 ] && echo "COLD BUILD FAILED — STOP" && exit "${COLD_EXIT}"

# 4. warm build (delete only html; keep .doctrees)
rm -rf docs/build/html
python -m sphinx -b html docs/source docs/build/html 2>&1 \
  | tee docs/build/build-log-warm.txt
WARM_EXIT=${PIPESTATUS[0]}
echo "EXIT_CODE=${WARM_EXIT}" >> docs/build/build-log-warm.txt

# 5. count + handoff
PAGE_COUNT=$(find docs/build/html -name '*.html' -type f | wc -l)
echo "Generated HTML page count: ${PAGE_COUNT}" >> docs/build/build-log-warm.txt
{
  echo "Cold exit: ${COLD_EXIT}"
  echo "Warm exit: ${WARM_EXIT}"
  echo "HTML pages: ${PAGE_COUNT}"
  echo "Cold WARNINGs: $(grep -c WARNING docs/build/build-log-cold.txt)"
  echo "Warm WARNINGs: $(grep -c WARNING docs/build/build-log-warm.txt)"
} > docs/build/handoff-summary.txt
```

Read `docs/build/handoff-summary.txt` first; everything else is alongside it in `docs/build/`.

**Expected result for the cheatsheet on the current source state:** `Cold exit: 0`, `Warm exit: 0`, `HTML pages: 7`, `Cold WARNINGs: 5`, `Warm WARNINGs: 5` (the 1 docutils ERROR line matches `^Error|ERROR` not `WARNING`, so it lands in the ERROR count — `Cold ERRORs: 1`, `Warm ERRORs: 1`, totaling 6 issues). If the numbers diverge, capture and surface in handoff.

---

## 11. Open questions / explicit asks-for-confirmation

These are non-blocking — the plan can proceed without answers — but the executor may want to confirm before running:

1. **Option 0 (system Python) vs Option C (project-local venv)?** Plan shows Option 0 as the primary cheatsheet because system Python already satisfies the dependency. If isolation/portability matters more than speed, use Option C. Surface the choice in the handoff summary.
2. **Is `.venv-docs/` at repo root acceptable (Option C only)** under "do not modify existing files"? Plan reads the constraint as applying to source/config files, not a tooling venv. If belt-and-suspenders is preferred, put the venv under `docs/.venv/` or `%TEMP%\openstartup-docs-venv\`.
3. **Pin specific versions** (e.g. `sphinx==8.2.3 sphinx-rtd-theme==3.0.2 docutils==0.21.2`) **or take latest?** The user request says "record the exact installed versions … for the build report" — that implies the install can take latest and the manifest captures whatever lands. Plan assumes the latter. Option 0 already pins to the system-installed versions (currently 8.2.3 / 3.0.2 / 0.21.2).
4. **If the cold build fails, is the executor authorized to debug** (read traceback, check `import sphinx_rtd_theme`), or strictly "capture and stop, no diagnostic poking"? Plan assumes the latter per the request's exact wording. If diagnostic latitude is allowed, run `python -c "import sphinx, sphinx_rtd_theme, docutils; print(sphinx.__version__)"` and add the output to the handoff.
5. **Should `.venv-docs/` persist** as the docs-builder env for subtask 2 and beyond, or remove it on completion? Plan assumes persistence (subtask 2 will need the env to re-run the build during triage). Option 0 has nothing to clean up.
6. **Are the two preserved logs (`build-log-warm-pre-triage.txt`, `build-log-after-fix.txt`) supposed to remain on disk** indefinitely, or is this subtask the right place to archive/delete them? Plan keeps them — they are evidence cited by `sphinx_warning_triage_plan_consolidated.md`. Decision deferred to subtask 2 / parent spec owner.

If the executor proceeds without answers, default to the plan's stated assumptions and surface them in `handoff-summary.txt`'s deviations section.

---

## 12. Cross-references

- **Pre-build audit:** `docs/_plan/sphinx_scaffolding_audit.md` — verified inventory, identified the 5 missing toctree pages.
- **Earlier subtask plans (not consumed; for context):** `docs/_plan/sphinx_build_capture_plan.md` (456 lines), `docs/_plan/sphinx_initial_build_plan.md` (520 lines).
- **Direct upstream inputs to this consolidation:**
  - `docs/_plan/sphinx_subtask1_install_build_capture_plan.md` (560 lines, Flow 0)
  - `docs/_plan/sphinx_initial_build_subtask1_plan.md` (513 lines, Flow 1)
- **Prior consolidation (superseded):** `docs/_plan/sphinx_initial_build_subtask1_plan_consolidated.md` (218 lines, Flow 1 + system-Python only). This document supersedes it.
- **Subtask 2 outputs (NOT consumed in this subtask; informative only):** `docs/_plan/sphinx_warning_triage_*` — out of scope.
- **Reference build logs (informative; preserved on disk):**
  - `docs/build/build-log-warm.txt` — pre-triage, 81 warnings; will be renamed to `build-log-warm-pre-triage.txt` in Step 1.
  - `docs/build/build-log-after-fix.txt` — post-triage, 6 warnings; predicts the shape of *this subtask's* fresh warm log.
- **Configuration source-of-truth:** `docs/source/conf.py` — `nitpicky=True`, `autosectionlabel_prefix_document=True`, 9-tuple `nitpick_ignore` block. Determines the *shape* of the warm log on the current source state.

---

## 13. Iteration / consolidation judgment

**Did this consolidation add value over the upstream Flow 0 + Flow 1 inputs?**

**Yes, moderately.** The two upstream flows agreed on ~80% of substance — install path, capture pattern, compliance, deliverables. The meaningful deltas reconciled here are:

1. **Warning prediction:** Flow 0 predicted ~81 warnings (using stale `build-log-warm.txt`); Flow 1 correctly predicted 6 warnings (recognizing the `nitpick_ignore` block now in `conf.py`). Direct evidence (conf.py inspection + `build-log-after-fix.txt`) confirms Flow 1's prediction. Carrying the wrong number forward would have caused the executor to either (a) panic when the build came in at 6 instead of 81, or (b) panic when the build came in at 81 if `nitpick_ignore` had drifted. The reconciled prediction with named warning classes (5 toctree-missing + 1 docutils ERROR) is the actionable form.
2. **Log-preservation step:** Flow 1's Step 1 (rename `build-log-warm.txt` → `build-log-warm-pre-triage.txt`) is essential to avoid clobbering upstream evidence cited by `sphinx_warning_triage_plan_consolidated.md`. Flow 0 omitted this step. Carrying Flow 0 forward unmodified would have destroyed the "Δ = -75 warnings" provenance.
3. **Option 0 (system Python):** independent verification at consolidation time confirmed that `python` already imports the three target packages with versions matching the existing `build-log-after-fix.txt`. Neither upstream flow checked this. Adds a meaningfully cheaper path for the deliverable.

Beyond those three, the consolidation primarily harmonizes terminology (e.g. "exit code, not log text, as failure signal" from Flow 0 → carried into Flow 1's structure), tightens the discrepancy table (8 rows merging both upstreams), and adds the awareness that a *prior* consolidation file already exists and is superseded.

A subsequent iteration would have diminishing returns: the substance is now settled, and further parallel flows would mostly produce stylistic variation. The recommendation to the loop owner is **stop** after this consolidation.
