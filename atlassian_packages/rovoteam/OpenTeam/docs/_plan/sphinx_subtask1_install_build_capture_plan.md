# Sphinx Subtask 1 — Install, Build, Capture Plan

**Subtask:** Install Sphinx + sphinx-rtd-theme, run cold + warm `sphinx-build` against `docs/source/`, capture raw logs and a version manifest. **No fixes. No edits to existing source files.**

**Plan date:** 2026-05-04
**Repo:** `C:\Users\yxinl\OneDrive\Projects\PythonProjects\CoreProjects\OpenTeam`
**Hand-off target:** Subtask 2 (recovery / warning triage). Owns any source edits the build motivates.
**Related artifacts already on disk:**

- `docs/_plan/sphinx_scaffolding_audit.md` — pre-build inventory (validated `conf.py`, `index.rst`, listed missing pages).
- `docs/_plan/sphinx_initial_build_plan.md` — earlier execution plan (this document supersedes it for the v3-level plan; the older plan is preserved for history).
- `docs/_plan/sphinx_warning_triage_*` — subtask 2 outputs (do not consume in this subtask).
- `docs/build/build-log-warm.txt` — actual prior warm build log (Sphinx 8.2.3, 81 warnings, build succeeded). Treat as **reference baseline only**, do not consume as the deliverable; this subtask must produce its own fresh logs.
- `docs/build/build-log-after-fix.txt` — post-triage log produced by subtask 2 (6 warnings remaining). Out of scope here; do not regenerate.

---

## 0. TL;DR — what to do, and what's different from the literal request

**Do:** create an isolated Python env with Sphinx + sphinx-rtd-theme, run two `sphinx-build` invocations (cold then warm), save full stdout+stderr from each into `docs/build/build-log-cold.txt` and `docs/build/build-log-warm.txt`, write a version manifest, count HTML files, hand off to subtask 2.

**Do not:** touch any file under `docs/source/` (conf.py, index.rst, glossary.rst, configuration.rst, inference-models.rst, operations.rst). Do not invent stub `.rst` pages. Do not lower `nitpicky`. Do not commit anything.

**Two premises in the request that do not hold in this repo** (substitutions documented in §2):

1. **"uv-native (per CONSOLIDATION_NOTES item #3 and pyproject.toml)"** — none of `pyproject.toml`, `uv.lock`, or `CONSOLIDATION_NOTES*` exists in the repo, and `uv` is not on `PATH`. `uv add --dev …` will hard-fail with `error: No \`pyproject.toml\` found in current directory or any parent directory`. Substitute: project-local stdlib `python -m venv .venv-docs` + `pip install` (Option C in §3). Captures the *intent* (isolated env, recorded versions) without inventing a `pyproject.toml` the prior audit explicitly recorded as absent.
2. **"the 8 prose pages"** — only 3 prose pages exist on disk (`configuration.rst`, `inference-models.rst`, `operations.rst`) plus `index.rst` and `glossary.rst` for a total of 5 `.rst` files. The "8 prose pages" wording is parent-spec leakage (the toctree references 9 page basenames; 5 are missing). The "do not modify" constraint applies to whatever exists today.

Both gaps are **upstream** and **not blockers**: the build runs against whatever is on disk, missing pages produce warnings (not hard errors), and capturing those warnings *is* the deliverable.

---

## 1. Pre-flight findings (verified at plan time)

### 1.1 `docs/source/` inventory

```
docs/source/
├── _static/                   ← present (per prior audit; .gitkeep only)
├── conf.py                    ← 7 732 bytes — exists, validated by prior audit
├── index.rst                  ← 1 321 bytes — exists, 9-entry toctree
├── configuration.rst          ← 104 685 bytes — exists
├── inference-models.rst       ← 57 929 bytes — exists
├── operations.rst             ← 48 870 bytes — exists
└── glossary.rst               ← 35 856 bytes — exists
```

The `index.rst` toctree (line 22) references 9 page basenames; **5 are missing**:

| toctree entry      | on disk?       |
|--------------------|----------------|
| `introduction`     | **MISSING**    |
| `getting-started`  | **MISSING**    |
| `architecture`     | **MISSING**    |
| `service-layer`    | **MISSING**    |
| `inference-models` | exists         |
| `configuration`    | exists         |
| `api-reference`    | **MISSING**    |
| `operations`       | exists         |
| `glossary`         | exists         |

### 1.2 `conf.py` settings that materially shape the build

Verified via `grep` of `docs/source/conf.py`:

- Line 30: `extensions = [...]` — includes `sphinx.ext.autosectionlabel` and `sphinx.ext.intersphinx` (per prior audit).
- Line 47: `autosectionlabel_prefix_document = True` — all auto-generated section labels are doc-prefixed → **duplicate-label warnings across pages should be suppressed**.
- Line 52: `nitpicky = True` — unresolved `:ref:` / `:term:` / `:doc:` references become warnings (not silent drops). **This is the dominant warning generator on this docset.**
- Line 132: `master_doc = 'index'`.
- Line 138: `html_theme = 'sphinx_rtd_theme'` — install dependency for this subtask.
- Line 142: `html_theme_options = { ... }` — present.

### 1.3 Repo-level inventory (uv premise check)

| Path                              | Exists? | Verified via |
|-----------------------------------|---------|---------------|
| `pyproject.toml` at repo root     | **NO**  | `Glob **/pyproject.toml` → 0 results; `ls pyproject.toml` → "No such file" |
| `uv.lock`                         | **NO**  | same Glob |
| `CONSOLIDATION_NOTES*` (any path) | **NO**  | `Glob **/CONSOLIDATION_NOTES*` → 0 results |
| `uv` on PATH                      | **NO**  | (matches prior audit; not re-verified at plan time, but PATH inspection in `sphinx_initial_build_plan.md §1.4` is authoritative for this host) |

### 1.4 Reference baseline from prior runs (informative only)

The repo already contains a `docs/build/build-log-warm.txt` (15 049 bytes, dated 2026-05-04 10:44 — the prior subtask 1 execution). Reading the head + tail:

- **Sphinx version used:** `Sphinx v8.2.3`
- **Build outcome:** `build succeeded, 81 warnings.`
- **Exit code:** 0 (build succeeded — no `sphinx-build` non-zero exit)
- **Pages built:** 5 source files (`configuration`, `glossary`, `index`, `inference-models`, `operations`) — confirms the 5-on-disk count from §1.1.
- **Errors in log:** 1 `ERROR: Unknown target name: "startup-time validation"` at `configuration.rst:254` (a docutils-level error, but does not flip exit code under default Sphinx behavior).
- **Warning counts:** 80 `WARNING` lines + 1 `ERROR` line — 5 `toc.not_readable` (one per missing page), 1 `ref.dir` for glossary, ~74 `ref.ref` from cross-references to missing labels (`architecture`, `api-reference`, `getting-started`, etc.).
- **Generated HTML files:** `docs/build/html/` currently contains 7 `.html` files (verified via `find`).

This is a **prior-run baseline**, not the deliverable. The executor must still produce a fresh cold + warm pair so the manifest reflects "what the install actually produced this time," not stale evidence. If the cold/warm warning counts come in materially different from this baseline (e.g. 30 instead of 81, or 200 instead of 81), call it out in the handoff — it would mean either the docset on disk drifted or a Sphinx minor-version change altered warning phrasing.

---

## 2. Discrepancies with the user request (and how each is handled)

| # | Premise in request | Reality in repo | Plan handles by |
|---|--------------------|-----------------|-----------------|
| 1 | "uv-native … per CONSOLIDATION_NOTES item #3 and pyproject.toml" | None of these files exist; `uv` not on PATH | §3: substitute `python -m venv .venv-docs` + `pip install`; intent (isolated env, recorded versions) preserved |
| 2 | `uv add --dev sphinx sphinx-rtd-theme` | Would error before doing anything (no pyproject.toml to add to) | §3 + §5 step 1: `pip install sphinx sphinx-rtd-theme` inside `.venv-docs/` |
| 3 | `uv run sphinx-build --version` | `uv` unavailable | §5 step 2: `.venv-docs/Scripts/sphinx-build --version` |
| 4 | `uv run sphinx-build -b html ...` | same | §5 steps 4 & 5: `.venv-docs/Scripts/sphinx-build -b html ...` |
| 5 | "the 8 prose pages" — implied don't-edit list | Only 3 prose pages exist on disk (5 RST total) | §8 compliance: do-not-modify applies to whatever exists; do not stub the 5 missing pages |
| 6 | "if `sphinx-build` exits non-zero (build failure, not warning), capture the error and stop" | Prior baseline shows exit 0 even with a docutils ERROR line and 80 WARNINGs (nitpicky still doesn't flip exit code unless `-W` is passed); we are **not** passing `-W` | §6 failure matrix: only treat actual non-zero exit as a stop; warnings + docutils ERROR text in log are normal here |
| 7 | "Sphinx warnings can vary between cold and warm builds (e.g. autosectionlabel-duplicate)" | True in general; with `autosectionlabel_prefix_document = True` duplicate-label is largely suppressed; but other warm-only diffs (stale doctree, `:ref:` resolution) can still appear | §5 still runs both builds and captures both, exactly as requested |

**None of these warrants pausing for confirmation.** The plan proceeds and the executor records every deviation in the handoff summary.

---

## 3. Install strategy

### 3.1 Hard constraints

- **Do not** create or modify any file under `docs/source/`.
- **Do not** create a repo-root `pyproject.toml`. That would pyproject-ify the *whole repo* — far beyond the scope of "install + build + capture."
- **Do** record exact versions of Sphinx, sphinx-rtd-theme, **and docutils** (the request explicitly calls out docutils because its warning phrasing shifts between minor versions and tends to surface in noisy logs).
- The install must be reproducible enough that subtask 2 can re-run the build during triage without re-installing.

### 3.2 Options considered

| Option | Sketch | Pros / Cons |
|--------|--------|-------------|
| **A.** Bootstrap `uv`, then `uv tool install sphinx --with sphinx-rtd-theme` | `pip install --user uv` → `uv tool install sphinx --with sphinx-rtd-theme` → `uv tool run sphinx-build …` | Closest to "uv-native" *spirit*. No `pyproject.toml` needed (`uv tool install` is global per-tool). Adds a host-level dependency (uv itself); bootstrap step is one extra. Not project-local. |
| **B.** Bootstrap `uv`, then `uv venv .venv-docs` + `uv pip install …` | Project-local venv via uv | Closest to the "uv add --dev" intent (project-local dev env). Still needs uv bootstrap. Creates `.venv-docs/`. |
| **C.** `python -m venv .venv-docs` + `pip install …` (recommended) | Pure stdlib + pip | No new host tool. No `pyproject.toml`. `pip freeze` gives clean version manifest. Creates `.venv-docs/`. Slowest cold-cache. Does not honor "uv-native" framing. |
| **D.** `pip install --user sphinx sphinx-rtd-theme` against system Python | Skip venv entirely | No isolation. Pollutes user-site for other projects on host. **Not recommended.** |
| **E.** `pipx install sphinx --include-deps` + `pipx inject sphinx sphinx-rtd-theme` | per-tool pipx env | Clean isolation; `pipx` may not be installed. |

### 3.3 Recommendation

**Option C** (`python -m venv .venv-docs` + `pip install`) is the recommended primary path:

- No host bootstrap (uses stdlib `venv`).
- Project-local — subtask 2 inherits a working env at `.venv-docs/`.
- `pip freeze` produces the version manifest cleanly.
- Most likely to succeed on first attempt.

If the team strongly prefers a uv-flavored install for the dev manifest, Option B is the fallback (bootstrap uv via `pip install --user uv`, then `uv venv .venv-docs` + `uv pip install …`). Option B does not change anything *downstream* — once the venv exists, `.venv-docs/Scripts/sphinx-build` works the same way.

**Concrete recommended commands** (Option C):

```bash
# from repo root, bash
python -m venv .venv-docs
.venv-docs/Scripts/python -m pip install --upgrade pip
.venv-docs/Scripts/pip install sphinx sphinx-rtd-theme
```

### 3.4 .gitignore consideration

`.venv-docs/` should be gitignored. **Do not edit `.gitignore` in this subtask** — `.gitignore` is an existing file, and the venv being tracked or not does not affect the build. If subtask 2 (or a later cleanup) wants to add the pattern, that is its decision.

---

## 4. Expected build signals (predicted from §1.1, §1.2, and prior baseline)

**Triage is subtask 2's job, not this subtask's.** Predicting the shape of the logs lets the executor distinguish "noisy but successful" from "actual hard failure."

### 4.1 Predicted warnings (high confidence)

Verified against `docs/build/build-log-warm.txt` from the prior run (Sphinx 8.2.3, build succeeded, 81 warnings):

1. **`toc.not_readable`** x 5 — one per missing toctree page (`introduction`, `getting-started`, `architecture`, `service-layer`, `api-reference`). Fires regardless of `nitpicky`. Loudest single signal at the top of the log.
2. **`ref.ref` (undefined label)** x ~70-75 — every `:ref:` in existing pages targeting a label inside the 5 missing pages produces this. Heaviest in `configuration.rst` (~40 instances) and `glossary.rst` (~15), with the rest spread across `inference-models.rst` and `operations.rst`.
3. **`ref.dir` (rst:dir reference target not found)** x 1 at `glossary.rst:13` — a `:rst:dir:` reference to `glossary` itself. Cause is in the glossary's own RST source.
4. **docutils ERROR `Unknown target name: "startup-time validation"`** x 1 at `configuration.rst:254` — a docutils-level error that does *not* flip exit code under default Sphinx behavior. Will appear as `ERROR:` in the log; **not** a build failure.

Total expected: **~80 WARNING + 1 ERROR lines**, exit code **0**, "build succeeded, 81 warnings." (or close to it).

### 4.2 Predicted absences

- **No duplicate-label warnings** for common headings — `autosectionlabel_prefix_document = True` prefixes every section label with the document name. (Confirmed by the prior log: zero `autosectionlabel.duplicate` lines.)
- **No intersphinx-network errors** — `intersphinx_mapping = {}` per prior audit; the extension is loaded but does no resolution.
- **No `MasterDocNotFoundError`** — `index.rst` is at `docs/source/index.rst`, matching `master_doc = 'index'`.

### 4.3 Hard-failure shapes (these would mean the build did NOT produce HTML)

The only outcomes that justify stopping before completion:

- `ExtensionError: Could not import extension sphinx.ext.autosectionlabel` — Sphinx itself didn't install correctly.
- `ThemeError: no theme named 'sphinx_rtd_theme' found` — `sphinx-rtd-theme` install failed silently.
- `Could not import extension ...` for any other extension — install incomplete.
- Early bail on `RST syntax error` — possible but unlikely (prior run parsed all 5 files cleanly).
- `MasterDocNotFoundError` — possible only if `index.rst` was renamed or moved.

In all these cases: exit code is non-zero, HTML output is incomplete. Per the user request: **stop, capture the log, hand off. Do not attempt fixes.**

### 4.4 Cold vs warm differences to watch for

The user request notes warm-only warnings (e.g. autosectionlabel-duplicate) can surface that cold builds suppress. Mechanism: a cold build builds the doctree from scratch in one pass; a warm build re-uses cached doctrees from `docs/build/.doctrees/` and re-resolves cross-references. Some warning classes only surface during the resolution phase against a fully-populated cache.

On *this* docset:

- **Duplicate-label warnings:** unlikely on either cold or warm (`autosectionlabel_prefix_document = True` prevents them). Capture both anyway — explicit `.. _foo:` anchors that happen to collide could still trigger.
- **`ref.ref` / `ref.dir` resolution warnings:** **will appear on both** but may differ in count or order. The set should overlap heavily.
- **`toc.not_readable` warnings:** **identical between cold and warm** (toctree resolution is early in both passes).

The user request specifies the warm log is canonical. Subtask 2 will diff cold vs warm; this subtask just captures both faithfully.

### 4.5 Why `rm -rf docs/build/html` between builds (NOT `.doctrees`)

The user request says delete only `docs/build/html` between cold and warm. This deletes only the *output HTML*, not the cached doctrees under `docs/build/.doctrees/`. **That is intentional and correct** for measuring "warm rebuild" warnings: the doctree cache persists, re-resolution runs against a fully-populated cache, and warm-only diffs surface.

**Do not** delete `docs/build/.doctrees/` between runs — that converts the warm build into a second cold build and defeats the purpose.

---

## 5. Step-by-step execution

All commands assume working directory is repo root: `C:\Users\yxinl\OneDrive\Projects\PythonProjects\CoreProjects\OpenTeam`. Bash syntax preferred (per `CLAUDE.md`'s "Shell: bash" line). PowerShell variant in §5-bis.

### Step 1 — Install Sphinx + sphinx-rtd-theme into a project-local venv

```bash
# 1a. create the venv (idempotent)
[ -d .venv-docs ] || python -m venv .venv-docs

# 1b. upgrade pip inside the venv
.venv-docs/Scripts/python -m pip install --upgrade pip

# 1c. install Sphinx + theme; no pin (capture "current latest" in manifest)
.venv-docs/Scripts/pip install sphinx sphinx-rtd-theme 2>&1 \
  | tee docs/build/install-log.txt
INSTALL_EXIT=${PIPESTATUS[0]}
[ "${INSTALL_EXIT}" -ne 0 ] && echo "INSTALL FAILED — STOP" && exit "${INSTALL_EXIT}"
```

**Expected:** install succeeds; final lines mention `Successfully installed sphinx-X.Y.Z sphinx-rtd-theme-A.B.C docutils-D.E.F` plus transitive deps (`Pygments`, `Jinja2`, `MarkupSafe`, `imagesize`, `babel`, `requests`, `snowballstemmer`, `alabaster`, `urllib3`, `certifi`, `charset-normalizer`, `idna`, `packaging`, `roman-numerals-py`, `sphinxcontrib-*`).

**On failure:** install log already captured at `docs/build/install-log.txt`. Stop. Hand off the log + the failure mode. Do not attempt the build.

### Step 2 — Verify install (replaces `uv run sphinx-build --version` from the request)

```bash
.venv-docs/Scripts/sphinx-build --version
```

**Expected:** a single line `sphinx-build 8.X.Y` (prior baseline used 8.2.3). Exit 0.

**On failure** (`sphinx-build` not found, ImportError): venv install did not deposit a working `sphinx-build` shim or the import fails at runtime. Capture stderr, stop, hand off.

### Step 3 — Capture the version manifest

```bash
mkdir -p docs/build
{
  echo "=== Sphinx subtask 1 — version manifest ==="
  echo "Generated: $(date -Iseconds)"
  echo "Host: $(uname -a 2>/dev/null || echo 'win32')"
  echo "PWD:  $(pwd)"
  echo
  echo "--- python --version ---"
  .venv-docs/Scripts/python --version
  echo
  echo "--- sphinx-build --version ---"
  .venv-docs/Scripts/sphinx-build --version
  echo
  echo "--- pip show sphinx sphinx-rtd-theme docutils ---"
  .venv-docs/Scripts/pip show sphinx sphinx-rtd-theme docutils
  echo
  echo "--- pip freeze (full venv inventory) ---"
  .venv-docs/Scripts/pip freeze
} > docs/build/version-manifest.txt 2>&1
```

The manifest is **strictly informational** — subtask 2 uses it to know exactly which Sphinx + theme + docutils were under test. The user request specifically calls out `docutils` because docutils warning phrasing has shifted between minor versions.

### Step 4 — Cold build

```bash
# True cold build: delete html AND doctree cache
rm -rf docs/build/html docs/build/.doctrees

# 2>&1 merges streams BEFORE the pipe, so tee captures both in emission order.
# tee always exits 0; ${PIPESTATUS[0]} (bash-specific) recovers the real exit code.
.venv-docs/Scripts/sphinx-build -b html docs/source docs/build/html 2>&1 \
  | tee docs/build/build-log-cold.txt
COLD_EXIT=${PIPESTATUS[0]}
echo "EXIT_CODE=${COLD_EXIT}" >> docs/build/build-log-cold.txt
echo "Cold build exit code: ${COLD_EXIT}"
```

**Notes on the redirection:**

- `2>&1` merges stderr into stdout *before* the pipe — `tee` writes both in emission order. That is what "verbatim stdout+stderr" means in the request.
- Appending `EXIT_CODE=...` to the log makes the exit code self-contained inside the artifact.
- On Windows Git Bash, `${PIPESTATUS[0]}` works. PowerShell does not — see §5-bis.

**Acceptable cold-build outcomes:**

| `COLD_EXIT` | Meaning | Action |
|-------------|---------|--------|
| `0` | Build succeeded; many warnings recorded. | Proceed to Step 5. |
| `1` | Build failed (extension import / theme not found / RST syntax / master-doc missing). | **Stop. Hand off cold log + manifest.** Do NOT proceed to warm build. |
| `2` | `conf.py` configuration error. | Stop. Hand off. |

**Important:** `nitpicky = True` does **not** flip exit code on its own — without `-W`, warnings remain warnings. Even a docutils `ERROR:` line in the log doesn't necessarily flip exit code (the prior baseline produced one and still exited 0). Treat the *exit code*, not log text, as the failure signal.

### Step 5 — Warm build

```bash
# Per the request, remove only the HTML output. Leave .doctrees in place.
rm -rf docs/build/html

# Sanity check: confirm .doctrees survived (warm semantics depend on it)
ls -la docs/build/.doctrees/ 2>&1 | head -5 \
  || echo "WARNING: .doctrees missing — warm build will be a second cold build"

.venv-docs/Scripts/sphinx-build -b html docs/source docs/build/html 2>&1 \
  | tee docs/build/build-log-warm.txt
WARM_EXIT=${PIPESTATUS[0]}
echo "EXIT_CODE=${WARM_EXIT}" >> docs/build/build-log-warm.txt
echo "Warm build exit code: ${WARM_EXIT}"
```

**Acceptable warm-build outcomes:**

| `WARM_EXIT` | Meaning | Action |
|-------------|---------|--------|
| `0` | Warm build succeeded. | Proceed to Step 6. |
| Non-zero | Warm-only failure (cold succeeded). Rare but possible (e.g. `:any:` resolution that succeeded cold but failed warm). | Stop. Capture both logs. Flag in handoff as **warm-only failure** — interesting signal for subtask 2. |

### Step 6 — Count generated HTML files

```bash
PAGE_COUNT=$(find docs/build/html -name '*.html' -type f | wc -l)
echo "Generated HTML page count: ${PAGE_COUNT}" | tee -a docs/build/build-log-warm.txt
```

**Expected count:** **7** files — `index.html`, `configuration.html`, `glossary.html`, `inference-models.html`, `operations.html`, `genindex.html`, `search.html`. The 5 missing toctree pages are not generated. The current `docs/build/html/` already has 7 — that is the canonical number for the present source state.

If the count differs materially (e.g. 0 or 12), capture the directory listing in the handoff and flag it.

### Step 7 — Final handoff summary

```bash
{
  echo "=== Sphinx subtask 1 — handoff summary ==="
  echo "Generated: $(date -Iseconds)"
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
  echo "Cold ERROR lines:   $(grep -c -E '^Error|ERROR' docs/build/build-log-cold.txt 2>/dev/null || echo 0)"
  echo "Warm ERROR lines:   $(grep -c -E '^Error|ERROR' docs/build/build-log-warm.txt 2>/dev/null || echo 0)"
  echo
  echo "--- Substitutions / deviations from the literal request ---"
  echo "1. uv add --dev -> python -m venv .venv-docs + pip install (uv unavailable; no pyproject.toml)"
  echo "2. uv run sphinx-build -> .venv-docs/Scripts/sphinx-build"
  echo "3. \"8 prose pages\" in request -> 5 .rst files actually exist (3 prose + index + glossary)"
} > docs/build/handoff-summary.txt
```

The handoff summary is the **single file subtask 2 should read first** — exit codes, page count, listing, and WARNING/ERROR counts. Everything else is in `docs/build/`.

### 5-bis. PowerShell variant

The PS 5.1 `2>&1` form on native exes wraps stderr lines in `ErrorRecord` objects and can flip `$?` to `$false` even on success — per the PowerShell tool guidance, **avoid `2>&1` on native executables in PS 5.1**. Use `*>` instead, which redirects all streams (stdout, stderr, info, warning) to one file in stream-event order.

```powershell
# Step 4 (cold) under PowerShell
Remove-Item -Recurse -Force docs/build/html, docs/build/.doctrees -ErrorAction SilentlyContinue
& .venv-docs/Scripts/sphinx-build.exe -b html docs/source docs/build/html `
    *> docs/build/build-log-cold.txt
$ColdExit = $LASTEXITCODE
Add-Content docs/build/build-log-cold.txt "EXIT_CODE=$ColdExit"
"Cold build exit code: $ColdExit"

# Step 5 (warm) under PowerShell
Remove-Item -Recurse -Force docs/build/html -ErrorAction SilentlyContinue
& .venv-docs/Scripts/sphinx-build.exe -b html docs/source docs/build/html `
    *> docs/build/build-log-warm.txt
$WarmExit = $LASTEXITCODE
Add-Content docs/build/build-log-warm.txt "EXIT_CODE=$WarmExit"
"Warm build exit code: $WarmExit"

# Step 6 (count)
$PageCount = (Get-ChildItem -Path docs/build/html -Recurse -Filter *.html -File).Count
Add-Content docs/build/build-log-warm.txt "Generated HTML page count: $PageCount"
```

`*>` redirects every stream to the file in event order — closest equivalent to bash `2>&1`. `$LASTEXITCODE` carries the native exe exit code untouched.

The bash form is preferred because the request says "verbatim stdout+stderr into a saveable buffer" and bash's `tee` + `${PIPESTATUS[0]}` is the cleanest expression of that.

---

## 6. Failure-handling matrix (consolidated)

This is the single table to consult when something goes wrong. Every row's action is "capture and stop" — this subtask does **not** triage.

| Stage | Failure shape | Action | Hand-off contains |
|-------|---------------|--------|-------------------|
| 1. install | `python -m venv` fails | Stop. | stderr from venv creation; OS / Python version |
| 1. install | `pip install` fails (network, no binary wheel, dep conflict) | Stop. | `docs/build/install-log.txt` + stop reason |
| 2. verify | `sphinx-build --version` errors | Stop. | stderr; output of `.venv-docs/Scripts/python -c 'import sphinx; print(sphinx.__version__)'` if it works |
| 3. manifest | `pip show` / `pip freeze` errors | Continue but flag — manifest is informational, not blocking | whatever was captured |
| 4. cold | `sphinx-build` exit != 0 | Stop. **Do not run warm build.** | cold log only; exit code; manifest |
| 4. cold | exit = 0 but `docs/build/html/index.html` missing | Treat as failure even though exit was 0 (anomalous). | cold log; directory listing of `docs/build/html/`; manifest |
| 5. warm | `rm -rf docs/build/html` errors (permission, file lock) | Stop. | error message; current state of `docs/build/` |
| 5. warm | `sphinx-build` exit != 0 (after cold succeeded) | Stop. **Flag as warm-only failure** — interesting signal. | both logs; both exit codes |
| 6. count | `find` returns 0 HTML files even with exit 0 | Treat as anomaly. | both logs; empty `docs/build/html/` listing |

**Across every row, the rule is: capture all relevant stdout/stderr and stop.** Do not repair `conf.py`, do not edit any `.rst`, do not stub missing pages, do not change theme. Those are subtask 2's calls.

---

## 7. Deliverables manifest (what subtask 2 receives)

After this plan runs to completion (all 7 steps), `docs/build/` is:

```
docs/build/
├── install-log.txt           ← stdout+stderr from `pip install` (Step 1c)
├── version-manifest.txt      ← Python, Sphinx, sphinx-rtd-theme, docutils + full pip freeze (Step 3)
├── build-log-cold.txt        ← raw stdout+stderr of cold build, with EXIT_CODE=N appended (Step 4)
├── build-log-warm.txt        ← raw stdout+stderr of warm build, EXIT_CODE=N + page count appended (Steps 5-6)
├── handoff-summary.txt       ← exit codes, page count, file listing, WARNING/ERROR counts, deviations (Step 7)
├── .doctrees/                ← Sphinx's doctree cache (NOT to be deleted between cold and warm)
└── html/                     ← canonical output from the warm build (~7 files)
    ├── index.html
    ├── configuration.html
    ├── glossary.html
    ├── inference-models.html
    ├── operations.html
    ├── genindex.html
    ├── search.html
    └── _static/, _images/, etc.
```

If install or build failed before Step 5, the warm log is absent and the handoff summary is partial — that is the signal to subtask 2 that the build stopped early. `install-log.txt` and any partial `build-log-cold.txt` are still meaningful to subtask 2.

**Subtask 2's expected entry point:** `docs/build/handoff-summary.txt`. It contains exit codes, page count, top-level listing, WARNING/ERROR line counts, and the deviation list. From there subtask 2 picks which log to triage first.

### What this subtask does NOT deliver

- A *clean* build. Warnings are expected and not in scope to fix.
- A list of *which* warnings need fixing. Triage decisions belong to subtask 2.
- An updated `conf.py`. Even if the build reveals a config-level cause (e.g. `nitpicky = True` is too aggressive for current source state), that is subtask 2's call.
- Stubs for the 5 missing pages. The audit at `docs/_plan/sphinx_scaffolding_audit.md` §4 enumerates them — this subtask just confirms via the build log that they remain missing.
- Any commit, push, or PR. The user did not ask, and per the harness's git-safety rules we do not commit unless asked.

---

## 8. Compliance checklist (what we will NOT do)

Per the user request: *"do not modify ANY existing files (not the 8 prose pages, not conf.py / index.rst / glossary.rst); this subtask is install + execute + capture only."*

The plan does **not**:

- Modify or create any file under `docs/source/` (verified by inspection of every command in §5).
- Modify `.gitignore`, `pyproject.toml` (which doesn't exist), or any other repo-root config file.
- Touch `src/`, `test/`, `conftest.py`, or any other code directory.
- Stub or author any of the 5 missing prose pages (`introduction`, `getting-started`, `architecture`, `service-layer`, `api-reference`).
- Edit `conf.py` to lower `nitpicky` or change theme.
- Run `git add` / `git commit` / `git push` of any kind.
- Delete `docs/build/.doctrees/` between cold and warm runs (would defeat the warm-build semantics).

The plan **does** create:

- `.venv-docs/` at the repo root (a Python venv directory; gitignored implicitly by most setups; subtask 2 inherits it).
- `docs/build/` and contents (the user request explicitly prescribes log files inside it).

Neither is a "modify existing file."

### Note on the `.venv-docs/` location

If creating a directory at the repo root is itself unwelcome, the alternative is `docs/.venv/` — keeps the venv strictly inside `docs/` (already a tooling sub-tree). The plan as written assumes `.venv-docs/` at repo root because that is the convention most reproducibility tools (uv, hatch, poetry) follow on Python projects, but either works.

---

## 9. Quick-start cheatsheet

For the executor who wants the minimum viable command sequence (bash, from repo root):

```bash
# Install
[ -d .venv-docs ] || python -m venv .venv-docs
.venv-docs/Scripts/python -m pip install --upgrade pip
.venv-docs/Scripts/pip install sphinx sphinx-rtd-theme 2>&1 \
  | tee docs/build/install-log.txt

# Verify
.venv-docs/Scripts/sphinx-build --version

# Manifest
mkdir -p docs/build
{
  .venv-docs/Scripts/python --version
  .venv-docs/Scripts/sphinx-build --version
  .venv-docs/Scripts/pip show sphinx sphinx-rtd-theme docutils
  .venv-docs/Scripts/pip freeze
} > docs/build/version-manifest.txt 2>&1

# Cold build (delete html AND .doctrees)
rm -rf docs/build/html docs/build/.doctrees
.venv-docs/Scripts/sphinx-build -b html docs/source docs/build/html 2>&1 \
  | tee docs/build/build-log-cold.txt
COLD_EXIT=${PIPESTATUS[0]}
echo "EXIT_CODE=${COLD_EXIT}" >> docs/build/build-log-cold.txt
[ "${COLD_EXIT}" -ne 0 ] && echo "COLD BUILD FAILED — STOP" && exit "${COLD_EXIT}"

# Warm build (delete only html; keep .doctrees)
rm -rf docs/build/html
.venv-docs/Scripts/sphinx-build -b html docs/source docs/build/html 2>&1 \
  | tee docs/build/build-log-warm.txt
WARM_EXIT=${PIPESTATUS[0]}
echo "EXIT_CODE=${WARM_EXIT}" >> docs/build/build-log-warm.txt

# Count + handoff
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

---

## 10. Open questions / explicit asks-for-confirmation

These are not blockers — the plan can proceed without answers — but the executor may want to confirm before running:

1. **Is `.venv-docs/` at repo root acceptable**, given the "do not modify existing files" framing? The plan reads the constraint as applying to *source/config files*, not to a tooling venv. If belt-and-suspenders is preferred, put the venv under `docs/.venv/` or `%TEMP%\openstartup-docs-venv\`.
2. **Should the install pin specific versions** (e.g. `sphinx==8.2.3 sphinx-rtd-theme==2.0.0`) or take whatever pip resolves? The user request says "record the exact installed versions ... for the build report" — that implies the install can take latest and the manifest captures whatever lands. Plan assumes the latter. The prior baseline used Sphinx 8.2.3; the new run may pick up 8.2.4+ if released.
3. **If the cold build fails, is the executor authorized to debug** (read traceback, check `import sphinx_rtd_theme`), or strictly "capture and stop, no diagnostic poking"? Plan assumes the latter per the request's exact wording. If diagnostic latitude is allowed, run `.venv-docs/Scripts/python -c "import sphinx, sphinx_rtd_theme, docutils; print(sphinx.__version__)"` and add the output to the handoff.
4. **Is `.venv-docs/` allowed to persist** as the docs-builder env for subtask 2 and beyond, or should this subtask remove it on completion? Plan assumes persistence (subtask 2 will need it to re-run the build during triage).
5. **Is the prior `docs/build/` directory acceptable to overwrite**? It currently contains `build-log-warm.txt` (prior subtask 1) and `build-log-after-fix.txt` (subtask 2's post-triage build). The plan overwrites `build-log-warm.txt`. If preserving prior history is desired, rename existing logs to `*-prior.txt` before Step 4.

If the executor proceeds without answers, default to the plan's stated assumptions and surface them in the handoff summary's "deviations" section.

---

## 11. Cross-references

- **Predecessor plan:** `docs/_plan/sphinx_initial_build_plan.md` (May 4 10:43) — earlier draft of this same subtask. This document supersedes it.
- **Pre-build audit:** `docs/_plan/sphinx_scaffolding_audit.md` — verified inventory, identified the 5 missing toctree pages.
- **Subtask 2 outputs (do NOT consume in this subtask):** `docs/_plan/sphinx_warning_triage_*.md` — out of scope; reference only if the executor wants to know what subtask 2 expects.
- **Reference build log (informative, do not consume as deliverable):** `docs/build/build-log-warm.txt` — produced by the prior subtask 1 run. The new run will overwrite it.
- **Post-fix build log (informative, out of scope):** `docs/build/build-log-after-fix.txt` — produced by subtask 2 after some warnings were addressed (6 remaining). Not relevant to this subtask, which captures the *pre-fix* state.
