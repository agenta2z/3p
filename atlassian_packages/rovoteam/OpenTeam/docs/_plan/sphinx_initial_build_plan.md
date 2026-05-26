# Sphinx Initial Build & Log Capture — Execution Plan

**Subtask:** Install Sphinx, run cold + warm builds against `docs/source/`, capture raw logs and a version manifest. **Do not fix anything; do not modify any existing file.**

**Plan author:** assistant (Claude)
**Plan date:** 2026-05-04
**Repo:** `C:\Users\yxinl\OneDrive\Projects\PythonProjects\CoreProjects\OpenTeam`
**Hands-off target:** subtask 2 ("recovery" — owns triage and any source edits the build motivates).

---

## 0. TL;DR for the executor

This subtask is mechanically simple (install → build → save logs) but the task description makes two premises that **do not hold** in this repo:

1. The task says use `uv add --dev sphinx sphinx-rtd-theme` because the project is "uv-native (per CONSOLIDATION_NOTES item #3 and pyproject.toml)." Neither `pyproject.toml`, `uv.lock`, nor any `CONSOLIDATION_NOTES*` file exists in this repo, and `uv` itself is not on `PATH`. `uv add` will hard-fail.
2. The task says "do not modify ANY existing files (not the 8 prose pages, not conf.py / index.rst / glossary.rst)." Only **3** prose pages exist on disk (`configuration.rst`, `inference-models.rst`, `operations.rst`) plus `index.rst` and `glossary.rst`. The "8 prose pages" wording is inherited from a parent spec; the prior audit at `docs/_plan/sphinx_scaffolding_audit.md` already flagged this gap.

Both gaps are **upstream of this subtask** and are **not blockers for the build itself** (the build runs against whatever is on disk; missing pages produce warnings, not hard errors). The plan below executes the original intent (install Sphinx, build, capture logs) using the closest viable substitute for each premise that does not hold, and surfaces every deviation explicitly so subtask 2 can reason about it.

The deliverable set is the same as what the user requested:

- `docs/build/build-log-cold.txt` — raw stdout+stderr of the first build
- `docs/build/build-log-warm.txt` — raw stdout+stderr of the second build (after `rm -rf docs/build/html`)
- A version manifest (Sphinx, sphinx-rtd-theme, docutils, Python)
- Build exit code (per build)
- HTML page count under `docs/build/html/` (after warm build)

---

## 1. Pre-flight findings (verified at plan time)

### 1.1 Disk inventory under `docs/source/`

```
docs/source/
├── _static/                    (per prior audit — `.gitkeep` only)
├── conf.py                     ← exists, 82 lines, validated by prior audit
├── index.rst                   ← exists, 40 lines, validated by prior audit
├── configuration.rst           ← exists (~104 KB)
├── inference-models.rst        ← exists (~58 KB)
├── operations.rst              ← exists (~49 KB)
└── glossary.rst                ← exists (~36 KB)
```

The toctree in `index.rst` (lines 22–34) lists 9 page basenames:

| toctree entry      | file on disk?        |
|--------------------|----------------------|
| `introduction`     | **MISSING**          |
| `getting-started`  | **MISSING**          |
| `architecture`     | **MISSING**          |
| `service-layer`    | **MISSING**          |
| `inference-models` | exists               |
| `configuration`    | exists               |
| `api-reference`    | **MISSING**          |
| `operations`       | exists               |
| `glossary`         | exists               |

This is reproduced verbatim from `docs/_plan/sphinx_scaffolding_audit.md` §4. The build will warn about the 5 missing pages — that is expected, and triaging it is subtask 2's job, not this subtask's.

### 1.2 `conf.py` settings that affect the build (per prior audit; not re-verified at plan time)

Settings that materially shape the build output:

- `extensions = ['sphinx.ext.autosectionlabel', 'sphinx.ext.intersphinx']`
- `autosectionlabel_prefix_document = True` — section labels are doc-prefixed (mitigates duplicate-label warnings across pages with the same H2/H3 names)
- `nitpicky = True` — unresolved cross-references (`:ref:`, `:term:`, `:doc:`) become warnings, not silent drops. **This is the dominant noise generator on this docset right now.**
- `html_theme = 'sphinx_rtd_theme'` — install dependency for this subtask. `conf.py` lines 8–11 document `alabaster` as the manual fallback (no install), but `alabaster` is the default Sphinx theme and switching to it requires editing `conf.py`, which is out of scope here.
- `master_doc = 'index'`, `source_suffix = '.rst'`, `exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']`
- `intersphinx_mapping = {}` — empty, so intersphinx is loaded but does no network I/O.

### 1.3 Repo-level inventory (uv premise check)

| File                              | Exists?           |
|-----------------------------------|-------------------|
| `pyproject.toml` at repo root     | **NO**            |
| `pyproject.toml` under `docs/`    | **NO**            |
| `uv.lock`                         | **NO**            |
| `CONSOLIDATION_NOTES*` (any path) | **NO**            |

Verified via `Glob` for `**/*.toml` (no results) and `**/CONSOLIDATION*` (no results), and direct `ls pyproject.toml uv.lock` (both "No such file or directory"). The `conf.py` source itself acknowledges this state in its header comments (lines 17–24): *"No pyproject.toml is checked in alongside this docset… there is no pyproject.toml [project].version available at scaffold time."*

### 1.4 Tool inventory on the host

| Tool          | Available?  | Source check                                                         |
|---------------|-------------|----------------------------------------------------------------------|
| `uv`          | **NO**      | `which uv` → exit 127, `uv --version` → "command not found"          |
| `python` 3.12 | YES         | `C:\Users\yxinl\AppData\Local\Programs\Python\Python312\Scripts` is on `PATH` |
| `python` (miniforge) | YES  | `C:\Users\yxinl\miniforge3` is on `PATH`                             |
| `pip`         | YES (assume) | comes with both Python installs                                      |

The `OPENSTARTUP_PYTHON` environment variable in `CLAUDE.md` documents `/opt/homebrew/anaconda3/bin/python` as the default — that path is mac-specific and irrelevant on this Windows host.

---

## 2. Discrepancies with the user request — and how the plan handles each

| # | Premise in user request | Reality | Plan handles by |
|---|--------------------------|---------|-----------------|
| 1 | "the project is uv-native (per CONSOLIDATION_NOTES item #3 and pyproject.toml)" | No pyproject.toml; no uv.lock; no CONSOLIDATION_NOTES file; `uv` not on PATH | §3 picks an alternate install path that mirrors the *intent* of "uv-native" (project-isolated venv, recorded versions) without inventing a pyproject.toml the audit explicitly recorded as absent |
| 2 | `uv add --dev sphinx sphinx-rtd-theme` | `uv add` requires a `pyproject.toml`; would error `error: No \`pyproject.toml\` found in current directory or any parent directory` | Substitute install command per §3; the *deliverable* (a recorded version manifest + a working `sphinx-build`) is unchanged |
| 3 | "do not modify ANY existing files (not the 8 prose pages, not conf.py / index.rst / glossary.rst)" | Only 3 prose pages exist on disk (3 prose + index + glossary = 5 RST files). The phrase "8 prose pages" is parent-spec leakage | The "do not modify" constraint applies to *whatever exists on disk*. Plan does not touch any file under `docs/source/` |
| 4 | "subtask 2 owns recovery"; the prior audit at `docs/_plan/sphinx_scaffolding_audit.md` calls the build "subtask 3" | Different subtask numberings between parent task graphs | Plan treats *this* request's numbering as authoritative: this subtask is install+build+capture; "subtask 2" is the next one and owns triage |
| 5 | "Sphinx warnings can vary between cold and warm builds (e.g., autosectionlabel-duplicate warnings often only surface on warm rebuild), and the warm-build output is canonical" | True in general. With `autosectionlabel_prefix_document = True`, duplicate-label warnings should be largely suppressed on this docset, but other warm-only warnings (e.g. stale doctree handling, `:ref:` resolution diffs) can still appear | Plan still runs both builds (cold + warm) and captures both, exactly as requested |

**None of the gaps above warrants stopping or asking before proceeding** — they are all install-path / accounting issues, not "the build cannot run." The plan proceeds and the executor records every deviation in the handoff notes.

---

## 3. Decision: how to install Sphinx (since `uv add` is not viable)

### 3.1 Hard constraints

- The user request says do **not** modify or create any source content. Creating non-source files (a venv directory, a build directory, log files) is in scope by definition — the request itself prescribes saving logs under `docs/build/`.
- `pyproject.toml` does not exist. Creating one would be a workspace-level configuration change with implications beyond docs (it would pyproject-ify the *whole repo*). That is **out of scope** for an "install + execute + capture only" subtask. **Do not create a repo-root pyproject.toml.**
- We need *recorded, exact versions* of Sphinx, sphinx-rtd-theme, and docutils for the build report.

### 3.2 Options considered

| Option | Command sketch | Tradeoffs |
|--------|---------------|-----------|
| **A.** Bootstrap `uv`, then `uv tool install sphinx --with sphinx-rtd-theme` | `pip install --user uv` (or `winget install astral-sh.uv`), then `uv tool install sphinx --with sphinx-rtd-theme`, then `uv tool run sphinx-build …` | Closest to "uv-native" intent. No pyproject.toml needed (`uv tool install` is global, isolated per-tool). Adds a host-level dependency (uv itself); takes one extra install step. Versions captured with `uv tool list` and `uv pip list --tool sphinx`. |
| **B.** `uv venv .venv-docs` + `uv pip install sphinx sphinx-rtd-theme` | After bootstrapping uv: create a project-local venv under `.venv-docs/`, install into it, run `sphinx-build` from inside it. | Project-local; closer to the "uv add --dev" *spirit* (a tracked dev-dependency env). Still needs uv bootstrap. Creates a `.venv-docs/` directory at the repo root — not a "modify" but does add a directory. |
| **C.** `python -m venv .venv-docs` + `pip install` | Pure stdlib + pip. `python -m venv .venv-docs` then `.venv-docs/Scripts/pip install sphinx sphinx-rtd-theme` then `.venv-docs/Scripts/sphinx-build …` | No new host tool. No pyproject.toml. `pip freeze` gives the version manifest cleanly. Creates `.venv-docs/` at repo root. Slowest of the three on cold cache. Does not honor "uv-native" framing at all. |
| **D.** `pip install --user sphinx sphinx-rtd-theme` against the system Python | Installs into the user-site for the active `python` interpreter. | No venv overhead; fastest. Pollutes the user-site for other projects on this host. Version capture via `pip show` is fine but the install is *not* isolated to docs. **Not recommended.** |
| **E.** `pipx install sphinx --include-deps` then `pipx inject sphinx sphinx-rtd-theme` | Per-tool isolated env via pipx. | Clean isolation; pipx may or may not be installed (check with `pipx --version` first). |

### 3.3 Recommendation

**Primary: Option B** if the host already has `uv` after a quick bootstrap (`pip install --user uv`), **otherwise Option C**. Both produce a project-local, reproducible env under `.venv-docs/` and a clean `pip freeze`-style version manifest. Both are equally compatible with "do not modify any existing file" — they create new files (the venv) and that is unavoidable for any install path.

Why not Option A (`uv tool install`)? The "uv tool" path puts the install under `%USERPROFILE%\.local\share\uv\tools\sphinx\` — outside the repo. That is fine for execution but breaks reproducibility against the repo (a teammate cloning the repo gets nothing). The user request's framing ("uv-native, dev-dependency") strongly implies a project-local install, which is what Option B/C produce.

Why not Option D (--user)? Pollutes the host's user-site and risks version conflicts with whatever is already there.

**Concrete recommended commands** (Option C, since it avoids the uv-bootstrap step and is the most likely-to-succeed first-try path on this host):

```bash
# from repo root
python -m venv .venv-docs
.venv-docs/Scripts/python -m pip install --upgrade pip
.venv-docs/Scripts/pip install sphinx sphinx-rtd-theme
```

If the team prefers uv-native and accepts the extra bootstrap step, **Option B**:

```bash
# from repo root
python -m pip install --user uv          # bootstrap uv
"$(python -c 'import site,os;print(os.path.join(site.USER_BASE,"Scripts"))')/uv.exe" venv .venv-docs
.venv-docs/Scripts/python -m pip install sphinx sphinx-rtd-theme   # uv pip install also fine
```

The plan from §5 onward is written against Option C; switching to Option B only changes the install step and the source of the version manifest (`uv pip freeze` vs `pip freeze`).

### 3.4 .gitignore consideration

`.venv-docs/` should be added to `.gitignore` — but `.gitignore` is an existing file. **Do not edit it in this subtask.** The venv is local, gitignored or not it does not affect the build. If subtask 2 wants to permanently track the venv-name pattern, that is its decision.

---

## 4. Expected build signals (predicted from prior audit + conf.py inspection)

This is **not** the executor's job to triage — subtask 2 owns that. But predicting what the cold + warm logs will contain is useful for the executor to (a) know they are not surprised by warning volume and (b) detect a *true* hard failure as distinct from "very noisy but successful build."

### 4.1 Predicted warnings (high confidence, from §1.1 + audit §7)

1. **`toctree contains reference to nonexisting document`** × 5 — one per missing page (`introduction`, `getting-started`, `architecture`, `service-layer`, `api-reference`). Fires regardless of `nitpicky`. These are the loudest single signal.
2. **`undefined label`** / **`unknown document`** under `nitpicky` — every `:ref:` and `:doc:` from existing pages to the 5 missing pages will warn. Volume is unknown without grepping the source pages, but is likely 10s to low 100s based on the audit's note that "every prose page links to others via named `:ref:` anchors."
3. **`term not in glossary`** — possible if any prose page uses `:term:` for something not yet in `glossary.rst`. Audit §4 explicitly flags this as "Out of scope for this audit; flagged for subtask 3."

### 4.2 Predicted absences (also high confidence)

- **No duplicate-label warnings** for common headings ("Purpose & scope", "Documented ambiguities", "See also") — `autosectionlabel_prefix_document = True` prefixes every auto-generated section label with the document name, eliminating cross-page collisions. (Audit §5 explains this in detail.)
- **No intersphinx-related warnings** — `intersphinx_mapping = {}` so the extension is loaded but does no resolution.

### 4.3 Hard-failure shapes (these would mean the build did NOT produce HTML)

- `ExtensionError: Could not import extension sphinx.ext.autosectionlabel` — would mean Sphinx itself didn't install correctly.
- `ThemeError: no theme named 'sphinx_rtd_theme' found` — would mean `sphinx-rtd-theme` install failed silently.
- `RST syntax error` followed by an early bail — would indicate a bad `.rst` file. Possible but unlikely given the audit verified `index.rst` parses cleanly and the prose files are large but presumably authored by a competent author.
- `MasterDocNotFoundError` — would mean `index.rst` is somehow not at `docs/source/index.rst`. Already verified it is.

In all four cases, exit code is non-zero and HTML output is incomplete. Per the user request: **stop and capture, do not attempt fixes.**

### 4.4 Cold vs warm differences to watch for

The user request explicitly notes: *"Sphinx warnings can vary between cold and warm builds (e.g., autosectionlabel-duplicate warnings often only surface on warm rebuild), and the warm-build output is canonical."*

Mechanism: a cold build builds the doctree from scratch in one pass; a warm build re-uses cached doctrees from `docs/build/.doctrees/` (or wherever they were cached) and re-resolves cross-references. Some classes of warnings (notably duplicate labels and stale `:ref:` warnings) only surface during the resolution phase against a fully-populated doctree cache. On this docset:

- Duplicate-label warnings: **probably won't appear** (autosectionlabel prefixing handles it). But the user's general advice still applies — capture both anyway, because exceptions exist (e.g. explicit `.. _foo:` anchors that happen to collide).
- `:ref:` resolution warnings: **may differ** between cold and warm in count or order, but the set should be similar.
- Toctree-missing warnings: **identical** between cold and warm (toctree resolution happens early in both passes).

The user request specifies the warm log is canonical. Subtask 2 should diff cold vs warm; the executor in this subtask just captures both faithfully.

### 4.5 Note on `rm -rf docs/build/html` between builds

The user request says to do `rm -rf docs/build/html` between cold and warm. This deletes only the *output HTML*, not the cached doctrees under `docs/build/.doctrees/`. That is **intentional and correct** for measuring "warm rebuild" warnings: the doctree cache persists, and re-resolution is what surfaces the warm-only warnings.

Do **not** delete `docs/build/.doctrees/` between runs — that would convert the warm build into a second cold build, defeating the purpose.

---

## 5. Step-by-step execution

All commands assume the working directory is the repo root: `C:\Users\yxinl\OneDrive\Projects\PythonProjects\CoreProjects\OpenTeam`. Bash syntax (the platform's primary shell per CLAUDE.md). Forward slashes throughout.

### Step 1 — Install Sphinx and sphinx-rtd-theme into a project-local venv

```bash
# 1a. create the venv (idempotent: skip if .venv-docs already exists)
[ -d .venv-docs ] || python -m venv .venv-docs

# 1b. upgrade pip inside the venv (avoids spurious "pip is outdated" lines in the install log)
.venv-docs/Scripts/python -m pip install --upgrade pip

# 1c. install Sphinx + theme; pin nothing (we want "current latest" recorded in the manifest)
.venv-docs/Scripts/pip install sphinx sphinx-rtd-theme
```

**Expected:** install succeeds; final lines mention `Successfully installed sphinx-X.Y.Z sphinx-rtd-theme-A.B.C docutils-D.E.F` and several transitive dependencies (e.g. `Pygments`, `Jinja2`, `MarkupSafe`, `imagesize`, `babel`, `requests`, `snowballstemmer`).

**On failure (non-zero exit, network error, dependency conflict):**
- Capture stdout+stderr to `docs/build/install-log.txt`.
- Stop. Hand off the install log + the failure mode to subtask 2. Do not attempt the build.

### Step 2 — Verify install

```bash
.venv-docs/Scripts/sphinx-build --version
```

**Expected:** A single line like `sphinx-build 7.4.7` (or whatever version pip just installed). Exit code 0.

**On failure (`sphinx-build` not found, ImportError):**
- This means the venv install did not actually deposit a `sphinx-build` shim or the import fails at runtime. Capture stderr, stop, hand off.

### Step 3 — Capture the version manifest

```bash
mkdir -p docs/build
{
  echo "=== Sphinx initial build subtask — version manifest ==="
  echo "Generated: $(date -Iseconds)"
  echo "Host: $(uname -a 2>/dev/null || echo 'win32')"
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

The manifest is **strictly informational** — subtask 2 uses it to know exactly which Sphinx + theme + docutils were under test. The user request specifically calls out `docutils` as a thing to record because docutils is a frequent source of RST-parser warnings whose phrasing has shifted between minor versions.

### Step 4 — Cold build

```bash
# Ensure no prior build artifacts exist for a true cold build
rm -rf docs/build/html docs/build/.doctrees

# Run the build, redirect both stdout and stderr to the cold log.
# Use `2>&1 | tee` so the log captures everything in order while the executor
# also sees the live output. Trap exit code separately because tee swallows it.
.venv-docs/Scripts/sphinx-build -b html docs/source docs/build/html 2>&1 \
  | tee docs/build/build-log-cold.txt
COLD_EXIT=${PIPESTATUS[0]}
echo "EXIT_CODE=${COLD_EXIT}" >> docs/build/build-log-cold.txt
echo "Cold build exit code: ${COLD_EXIT}"
```

**Notes on the redirection:**

- `2>&1` merges stderr into stdout *before* the pipe, so `tee` writes both into the file in the order Sphinx emitted them. That is what "verbatim stdout+stderr" means in the user request.
- `tee` always exits 0 itself, which would mask the real Sphinx exit code. `${PIPESTATUS[0]}` (bash-specific) recovers Sphinx's exit code.
- On Windows Git Bash, `${PIPESTATUS[0]}` works. PowerShell does not have it natively — see §5-bis below for a PowerShell variant if the executor is running PS instead of bash.
- Appending `EXIT_CODE=…` to the log file makes the exit code self-contained inside the artifact, so subtask 2 doesn't need a separate file to read it.

**Acceptable cold-build outcomes:**

| `COLD_EXIT` | Meaning | What to do |
|-------------|---------|------------|
| `0` | Build succeeded; warnings (likely many) recorded in log. | Proceed to Step 5 (warm build). |
| `1` | Build failed (one of: extension import error, theme not found, syntax error, master-doc missing, etc.) — Sphinx aborted before producing complete HTML. | **Stop. Hand off cold log + manifest to subtask 2. Do NOT proceed to warm build.** Per user request: "if `sphinx-build` exits non-zero (build failure, not warning), capture the error and stop — subtask 2 owns recovery." |
| `2` | Build failed with a configuration error in `conf.py`. | Same as exit 1 — stop and hand off. |

**Important:** with `nitpicky = True`, **warnings still produce exit code 0** (they are warnings, not errors). The build is *expected* to be very noisy here but exit clean. If exit is non-zero, that is a real failure and the plan stops.

### Step 5 — Warm build

```bash
# Per the user request, remove only the HTML output. Leave .doctrees in place
# so the warm rebuild re-uses the cached doctree (this is what makes it "warm"
# and is the configuration that surfaces warm-only warnings).
rm -rf docs/build/html

# Confirm .doctrees is still present (sanity check, will print directory listing)
ls -la docs/build/.doctrees/ 2>&1 | head -5 || echo "WARNING: .doctrees missing — warm build will be a second cold build"

# Run the build again with the same redirection pattern.
.venv-docs/Scripts/sphinx-build -b html docs/source docs/build/html 2>&1 \
  | tee docs/build/build-log-warm.txt
WARM_EXIT=${PIPESTATUS[0]}
echo "EXIT_CODE=${WARM_EXIT}" >> docs/build/build-log-warm.txt
echo "Warm build exit code: ${WARM_EXIT}"
```

**Acceptable warm-build outcomes:**

| `WARM_EXIT` | Meaning | What to do |
|-------------|---------|------------|
| `0` | Warm build succeeded. | Proceed to Step 6. |
| Non-zero | Warm build failed, even though the cold build succeeded. This is rare but possible (e.g. an `:any:` cross-reference that resolved during cold pass via tentative resolution but failed under warm re-resolution). | Stop. Capture log. Hand off. |

### Step 6 — Count generated HTML pages

```bash
PAGE_COUNT=$(find docs/build/html -name '*.html' -type f | wc -l)
echo "Generated HTML page count: ${PAGE_COUNT}" | tee -a docs/build/build-log-warm.txt
```

**Notes:**

- The user request says "Count generated HTML files under `docs/build/html/`". This counts every `.html` regardless of where in the output tree (Sphinx may produce `genindex.html`, `search.html`, `_static/…/*.html` if any, plus per-page outputs).
- Expected count: **9** if all 9 toctree pages had on-disk source, plus `index.html`, `genindex.html`, `search.html`. Given 4 of 9 pages exist on disk: realistically 4 (existing) + 1 (`index`) + 2 (`genindex`, `search`) = **7 HTML files**, give or take. The exact number is data; subtask 2 will compare to expectation.

### Step 7 — Final handoff log

```bash
{
  echo "=== Sphinx initial build subtask — handoff summary ==="
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
  echo "--- Warning-line counts (rough triage hint for subtask 2) ---"
  echo "Cold WARNING lines: $(grep -c 'WARNING' docs/build/build-log-cold.txt 2>/dev/null || echo 0)"
  echo "Warm WARNING lines: $(grep -c 'WARNING' docs/build/build-log-warm.txt 2>/dev/null || echo 0)"
  echo "Cold ERROR lines:   $(grep -c -E '^Error|ERROR' docs/build/build-log-cold.txt 2>/dev/null || echo 0)"
  echo "Warm ERROR lines:   $(grep -c -E '^Error|ERROR' docs/build/build-log-warm.txt 2>/dev/null || echo 0)"
} > docs/build/handoff-summary.txt
```

The handoff summary is the **single file subtask 2 should read first** to get its bearings; everything else is referenced from it.

### 5-bis. PowerShell variant (if the executor is in PS, not bash)

The `2>&1 | Tee-Object` form on PS 5.1 is treacherous — PS's `2>&1` for native exes wraps stderr lines in `ErrorRecord` objects and can flip `$?` to `$false` even on success. Per the PowerShell tool guidance, *don't* use `2>&1` on native executables in PS 5.1.

Use this alternative:

```powershell
# Step 4 (cold) under PowerShell
Remove-Item -Recurse -Force docs/build/html, docs/build/.doctrees -ErrorAction SilentlyContinue
& .venv-docs/Scripts/sphinx-build.exe -b html docs/source docs/build/html `
    *> docs/build/build-log-cold.txt   # PS *> redirects ALL streams (stdout, stderr, info, warning) to one file
$ColdExit = $LASTEXITCODE
Add-Content docs/build/build-log-cold.txt "EXIT_CODE=$ColdExit"
"Cold build exit code: $ColdExit"
```

`*>` in PS 5.1 redirects *every* stream to the file in stream-event order, which is the closest equivalent to bash `2>&1`. `$LASTEXITCODE` carries the native exe exit code untouched.

The bash form is preferred because the user request mentions "verbatim stdout+stderr into a saveable buffer" and bash's `tee` + `${PIPESTATUS[0]}` is the cleanest expression of that.

---

## 6. Failure-handling matrix (full)

This consolidates the failure paths from §3, §4, and §5 into one table for the executor's convenience.

| Stage | Failure shape | Action | Hand-off contains |
|-------|---------------|--------|-------------------|
| 1. install | venv creation fails | Stop. | stderr from `python -m venv`; OS / Python version |
| 1. install | `pip install` fails (network, no binary wheel, dep conflict) | Stop. | install stdout+stderr to `docs/build/install-log.txt`; stop reason |
| 2. verify | `sphinx-build --version` errors out | Stop. | stderr; output of `.venv-docs/Scripts/python -c 'import sphinx; print(sphinx.__version__)'` if it works |
| 3. manifest | `pip show` / `pip freeze` errors | Continue but flag — manifest is informational, not blocking | Whatever was captured |
| 4. cold | `sphinx-build` exit ≠ 0 | Stop. **Do not run warm build.** | cold log only; exit code; manifest |
| 4. cold | `sphinx-build` exit = 0 but `docs/build/html/index.html` missing | Treat as failure even though exit was 0 (anomalous). | cold log; directory listing of `docs/build/html/`; manifest |
| 5. warm | `rm -rf docs/build/html` errors (permission, file lock) | Stop. | error message; current state of `docs/build/` |
| 5. warm | `sphinx-build` exit ≠ 0 (after cold succeeded) | Stop. Note: this is rare and interesting — call it out explicitly in the handoff summary because it indicates warm-only resolution failure. | both logs; both exit codes |
| 6. count | `find` returns 0 HTML files even with exit 0 | Treat as anomaly. Hand off both logs and the empty `docs/build/html/` listing. | everything |

**Across all rows, the rule is: capture all relevant stdout/stderr and stop. Do not attempt to repair `conf.py`, do not edit any `.rst` file, do not stub missing pages, do not change theme.** Those are subtask 2's calls.

---

## 7. Deliverables manifest (what subtask 2 receives)

After this plan runs to completion (all steps), the directory state is:

```
docs/build/
├── build-log-cold.txt        ← raw stdout+stderr of cold build, with EXIT_CODE=N appended
├── build-log-warm.txt        ← raw stdout+stderr of warm build, with EXIT_CODE=N appended,
│                                and "Generated HTML page count: N" appended (Step 6)
├── version-manifest.txt      ← Python, Sphinx, sphinx-rtd-theme, docutils, full pip freeze
├── handoff-summary.txt       ← exit codes, page count, file listing, WARNING/ERROR counts
├── .doctrees/                ← Sphinx's doctree cache (NOT to be deleted between runs)
└── html/                     ← canonical output from the warm build
    ├── index.html
    ├── *.html (per existing source page)
    ├── genindex.html
    ├── search.html
    └── _static/, _images/, etc.
```

If install or build failed before Step 5, the warm log is absent and the handoff summary is partial — that is the signal to subtask 2 that the build stopped early.

**Subtask 2's expected entry point:** `docs/build/handoff-summary.txt`. It contains exit codes, page count, top-level listing, and WARNING/ERROR line counts; from there subtask 2 picks which log to triage first.

### What this subtask does NOT deliver

- A *clean* build. Warnings are expected and not in scope to fix.
- A list of *which* warnings need fixing. That is a triage decision subtask 2 owns.
- An updated `conf.py`. Even if the build reveals a config-level cause (e.g. `nitpicky = True` is in fact too aggressive for this docset's current state), that is subtask 2's call.
- A list of pages that need to be authored/stubbed. The audit at `docs/_plan/sphinx_scaffolding_audit.md` §4 already enumerates these — this subtask just confirms via the build log that they are still missing.

---

## 8. Compliance checklist (what we will NOT do)

Per the user request: *"do not modify ANY existing files (not the 8 prose pages, not conf.py / index.rst / glossary.rst); this subtask is install + execute + capture only."*

The plan does **not**:

- Modify or create any file under `docs/source/` (verified by inspection of every command in §5).
- Modify `.gitignore`, `pyproject.toml` (which doesn't exist), or any other repo-root config file.
- Touch `src/`, `test/`, `conftest.py`, or any other code directory.
- Stub or author any of the 5 missing prose pages.
- Edit `conf.py` to lower `nitpicky` or change theme.
- Run `git add` / `git commit` / `git push` of any kind. The user did not ask for a commit, and per the harness's git-safety rules we don't commit unless asked.

The plan **does** create:

- `.venv-docs/` at the repo root (a Python venv directory; gitignored implicitly by most setups; if needed subtask 2 can decide whether to keep or rm it).
- `docs/build/` and contents (the user request explicitly prescribes log files inside it).

Neither of those is a "modify existing file."

### Note for the executor on the `.venv-docs/` location

If creating a directory at the repo root is itself unwelcome, an alternative is to put the venv under `docs/.venv/`. That keeps it strictly inside `docs/` (which is already a tooling sub-tree). The plan as written assumes `.venv-docs/` at repo root because that is the convention most reproducibility tools (uv, hatch, poetry) follow on Python projects, but either works.

---

## 9. Quick-start cheatsheet (the same plan, condensed for copy-paste)

For the executor who wants the minimum viable command sequence:

```bash
# from repo root, bash
python -m venv .venv-docs
.venv-docs/Scripts/python -m pip install --upgrade pip
.venv-docs/Scripts/pip install sphinx sphinx-rtd-theme

.venv-docs/Scripts/sphinx-build --version

mkdir -p docs/build
.venv-docs/Scripts/pip freeze > docs/build/version-manifest.txt
.venv-docs/Scripts/sphinx-build --version >> docs/build/version-manifest.txt

rm -rf docs/build/html docs/build/.doctrees
.venv-docs/Scripts/sphinx-build -b html docs/source docs/build/html 2>&1 \
  | tee docs/build/build-log-cold.txt
COLD_EXIT=${PIPESTATUS[0]}
echo "EXIT_CODE=${COLD_EXIT}" >> docs/build/build-log-cold.txt
[ "${COLD_EXIT}" -ne 0 ] && echo "COLD BUILD FAILED — STOP" && exit "${COLD_EXIT}"

rm -rf docs/build/html
.venv-docs/Scripts/sphinx-build -b html docs/source docs/build/html 2>&1 \
  | tee docs/build/build-log-warm.txt
WARM_EXIT=${PIPESTATUS[0]}
echo "EXIT_CODE=${WARM_EXIT}" >> docs/build/build-log-warm.txt

PAGE_COUNT=$(find docs/build/html -name '*.html' -type f | wc -l)
echo "Generated HTML page count: ${PAGE_COUNT}" >> docs/build/build-log-warm.txt

# handoff summary
{
  echo "Cold exit: ${COLD_EXIT}"
  echo "Warm exit: ${WARM_EXIT}"
  echo "HTML pages: ${PAGE_COUNT}"
  echo "Cold WARNINGs: $(grep -c WARNING docs/build/build-log-cold.txt)"
  echo "Warm WARNINGs: $(grep -c WARNING docs/build/build-log-warm.txt)"
} > docs/build/handoff-summary.txt
```

Read the handoff-summary first; everything else is in `docs/build/`.

---

## 10. Open questions / explicit asks-for-confirmation

These are not blockers (the plan can proceed without answers), but the executor may want to confirm with the requester before running:

1. **Is creating `.venv-docs/` at the repo root acceptable**, given the "do not modify existing files" framing? (The plan reads the constraint as applying to source/config files, not to a tooling venv. If the executor wants belt-and-suspenders, put the venv under `docs/.venv/` or under `%TEMP%`.)
2. **Should the install pin specific versions** (e.g. `sphinx==7.4.7 sphinx-rtd-theme==2.0.0`) or take whatever pip resolves? The user request says "record the exact installed versions… for the build report" — that implies the install can take latest and the manifest captures whatever lands. Plan assumes the latter.
3. **If the cold build fails, is the executor authorized to debug** to the point of identifying *what* went wrong (e.g. read the traceback, check that `sphinx_rtd_theme` actually imports), or is the rule strictly "capture and stop, no diagnostic poking"? Plan assumes "capture and stop" per the user request's exact wording.
4. **Is the `.venv-docs/` allowed to persist** as the docs-builder env for subtask 2 and beyond, or should this subtask remove it on completion? Plan assumes persistence (subtask 2 will need it to re-run the build during triage).

If the executor proceeds without answers, default to the plan's stated assumptions (above) and surface them in the handoff summary.
