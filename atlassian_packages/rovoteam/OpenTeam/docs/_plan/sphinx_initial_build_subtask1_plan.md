# Sphinx Initial Build — Subtask 1 (Install + Capture) Plan

**Plan author:** assistant (Claude)
**Plan date:** 2026-05-04
**Repo:** `C:\Users\yxinl\OneDrive\Projects\PythonProjects\CoreProjects\OpenTeam`
**Subtask scope:** install Sphinx + RTD theme, run cold & warm builds against `docs/source/`, save raw logs and a version manifest. Hand off to **subtask 2** (warning triage / recovery). **Do not modify any existing file.**

---

## 0. TL;DR for the executor

This subtask is mechanically simple — install, build twice, save logs — but two premises in the task description **do not hold** in this repo, and a third premise is already partially satisfied on disk:

1. **"uv-native, per CONSOLIDATION_NOTES item #3 and pyproject.toml"** — neither `pyproject.toml` nor any file matching `CONSOLIDATION_NOTES*` exists at repo root, and `uv` itself is not on `PATH`. `uv add --dev …` will hard-fail. §3 picks the closest viable substitute.
2. **"do not modify ANY existing files (not the 8 prose pages, not conf.py / index.rst / glossary.rst)"** — only **3** prose pages exist on disk (`configuration.rst`, `inference-models.rst`, `operations.rst`) plus `index.rst` and `glossary.rst`. The "8 prose pages" wording is parent-spec leakage already flagged by `docs/_plan/sphinx_scaffolding_audit.md §4`. The "do not modify" constraint is honored against *whatever exists*.
3. **The build was already executed once** — `docs/build/build-log-warm.txt` exists and ends with `build succeeded, 81 warnings.` (Sphinx 8.2.3). A subsequent triage subtask landed fixes in `conf.py` + `glossary.rst:13`; `docs/build/build-log-after-fix.txt` ends with `build succeeded, 6 warnings.` This plan **re-runs the cold + warm capture from scratch** because the user request explicitly asks for fresh `build-log-cold.txt` + `build-log-warm.txt` artifacts and a fresh version manifest, *not* to consume the existing warm log.

The deliverable set (per the user request):

- `docs/build/build-log-cold.txt` — raw stdout+stderr of cold build
- `docs/build/build-log-warm.txt` — raw stdout+stderr of warm build (after `rm -rf docs/build/html` only; `.doctrees` retained)
- Version manifest (Sphinx, sphinx-rtd-theme, docutils, Python)
- Build exit code per build
- HTML page count under `docs/build/html/` (warm build output)

---

## 1. Pre-flight findings (verified at plan time)

### 1.1 Disk inventory — `docs/source/`

```
docs/source/
├── _static/                       (per audit, .gitkeep only)
├── conf.py                        ← exists
├── index.rst                      ← exists, 40 lines
├── configuration.rst              ← exists (~104 KB, foundation, read-only)
├── inference-models.rst           ← exists (~58 KB, foundation, read-only)
├── operations.rst                 ← exists (~49 KB, foundation, read-only)
└── glossary.rst                   ← exists (~36 KB, NEW file, line 13 already fixed)
```

The toctree at `index.rst:22` lists 9 page basenames; **5 are MISSING** on disk: `introduction`, `getting-started`, `architecture`, `service-layer`, `api-reference`. This is reproduced from `docs/_plan/sphinx_scaffolding_audit.md §4` and confirmed by direct listing. The 5 missing pages produce 5 toctree warnings + many `[ref.ref]` warnings on the warm build — that is **expected output**, not a build failure.

### 1.2 `conf.py` settings that materially shape build output

(Read at plan time, not re-listed verbatim — see `docs/source/conf.py` for full text.)

- `extensions = ['sphinx.ext.autosectionlabel', 'sphinx.ext.intersphinx']`
- `autosectionlabel_prefix_document = True` — prefixes auto labels per document, suppressing cross-page H2/H3 collisions
- `nitpicky = True` — unresolved cross-references become warnings; **dominant noise source**
- `nitpick_ignore` block (lines ~81–129) — 9 `('std:ref', '<anchor>')` tuples covering the 9 unique forward-referenced anchor names from the missing-page set, with per-tuple citation comments
- `html_theme = 'sphinx_rtd_theme'` — install dependency for this subtask
- `master_doc = 'index'`, `source_suffix = '.rst'`, `exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']`
- `intersphinx_mapping = {}` — extension loaded but does no network I/O

### 1.3 Repo-level inventory (uv-premise check)

| Artifact                              | Exists?            |
|---------------------------------------|--------------------|
| `pyproject.toml` at repo root         | **NO**             |
| `pyproject.toml` under `docs/`        | **NO**             |
| `uv.lock`                             | **NO**             |
| `CONSOLIDATION_NOTES*` (any path)     | **NO**             |
| `uv` on `PATH`                        | **NO** (assume — re-verify before install) |
| `python` 3.12 on `PATH`               | **YES** (per CLAUDE.md / earlier audit) |

Verified via `Glob` (no `**/*.toml` matches) and direct `ls`. The `conf.py` header (lines 17–24) itself acknowledges the missing-pyproject state: *"No pyproject.toml is checked in alongside this docset… there is no pyproject.toml [project].version available at scaffold time."*

### 1.4 `docs/build/` — existing artifacts on disk

```
docs/build/
├── build-log-after-fix.txt   (post-triage, 6 warnings)
├── build-log-warm.txt        (pre-triage, 81 warnings)
└── html/                     (current — from the post-fix build)
```

**Implication:** the directory is non-empty. To produce a clean cold build, the plan deletes `docs/build/html` *and* `docs/build/.doctrees` (if present) before the cold run. The two existing log files are **kept** — they are upstream evidence already cited by the consolidation report at `docs/_plan/sphinx_warning_triage_plan_consolidated.md §1` and overwriting them would destroy provenance for the prior triage subtask.

The new logs land at `docs/build/build-log-cold.txt` and `docs/build/build-log-warm.txt`. The latter is a **filename collision** with the existing pre-triage log. Per §3.4, the plan renames the existing `build-log-warm.txt` to `build-log-warm-pre-triage.txt` before running, preserving its content under a clearly-distinct name.

### 1.5 Prior-art plans on disk (which this plan complements)

- `docs/_plan/sphinx_scaffolding_audit.md` — upstream audit predicting warning shape; cited.
- `docs/_plan/sphinx_build_capture_plan.md` (456 lines) — first full plan for this subtask.
- `docs/_plan/sphinx_initial_build_plan.md` (520 lines) — second full plan; almost identical scope.
- `docs/_plan/sphinx_warning_triage_*` (multiple) — subtask-2 plans + executed deliverables.

This plan is **not a replacement** for the prior two; it is a *current-state-aware* execution document tailored to this specific phrasing of the request, citing the existing plans where they remain authoritative and diverging only where the on-disk reality has shifted.

---

## 2. Discrepancies with the user request — and how the plan handles each

| # | Premise in request | Reality | Plan's handling |
|---|--------------------|---------|-----------------|
| 1 | "uv-native (per CONSOLIDATION_NOTES item #3 and pyproject.toml)" | None of those artifacts exist | §3 substitutes a project-local venv install path; the **deliverable** (recorded versions + working `sphinx-build`) is unchanged |
| 2 | `uv add --dev sphinx sphinx-rtd-theme` | Would hard-fail with `error: No \`pyproject.toml\` found` | Substitute `python -m venv .venv-docs` + `pip install` (Option C in §3.2). Manifest captured via `pip freeze`/`pip show`. |
| 3 | "do not modify ANY existing files (not the 8 prose pages, not conf.py / index.rst / glossary.rst)" | Only 3 prose + index + glossary on disk | "Do not modify" applies to whatever exists. Plan touches **no** file under `docs/source/`. |
| 4 | "subtask 2 owns recovery" | The audit at `…/sphinx_scaffolding_audit.md` calls the build "subtask 3" — different numbering. Subtask 2 has *already* executed in this repo (post-fix log + consolidation exist) | This plan respects the **current request's numbering**: this run's output goes to subtask-2-of-current-spec. The fact that an earlier subtask 2 (different parent spec) has already executed is informational only and is surfaced in the handoff summary, not used to skip work. |
| 5 | "warm-build output is canonical" | True in general; on this docset `autosectionlabel_prefix_document = True` already mutes the most common cold/warm differential (duplicate labels). Toctree warnings are identical between cold/warm. `[ref.ref]` warnings *can* differ in count/order. | Plan still runs both builds and captures both verbatim, exactly as requested. Subtask 2 diffs them. |
| 6 | "if `sphinx-build` exits non-zero (build failure, not warning), capture the error and stop" | With `nitpicky = True`, warnings stay at exit 0 — the *expected* outcome here is exit 0 with high warning count | Plan codifies the "exit ≠ 0 ⇒ stop" rule in §6 failure matrix. Warnings alone do **not** trigger stop. |

None of these warrants halting before execution; all are accounting / install-path issues, not "the build cannot run."

---

## 3. Decision: how to install Sphinx (since `uv add` is not viable)

### 3.1 Hard constraints recapped

- Must produce *recorded, exact* versions of `sphinx`, `sphinx-rtd-theme`, `docutils`.
- Must not modify any existing file (`docs/source/*`, `.gitignore`, `conf.py`, etc.).
- Must not create `pyproject.toml` at repo root — that is a workspace-wide config change beyond this subtask's scope.
- Should be re-runnable by subtask 2 without re-installing.

### 3.2 Options considered

| # | Approach | Tradeoffs |
|---|----------|-----------|
| A | Bootstrap `uv` (`pip install --user uv`), then `uv tool install sphinx --with sphinx-rtd-theme` | Closest to "uv-native" intent; tool install is host-global, bypasses pyproject; leaves `%USERPROFILE%\.local\share\uv\tools\…` outside repo (low reproducibility for teammates) |
| B | Bootstrap `uv`, then `uv venv .venv-docs` + `uv pip install sphinx sphinx-rtd-theme` | Project-local; "uv add --dev" *spirit*; needs uv bootstrap |
| **C** | **`python -m venv .venv-docs` + `pip install sphinx sphinx-rtd-theme`** | **Pure stdlib + pip; no host-tool dep; project-local; cleanest manifest via `pip freeze`. Recommended.** |
| D | `pip install --user sphinx sphinx-rtd-theme` against system Python | Pollutes user-site; not isolated; not recommended |
| E | `pipx install sphinx --include-deps` + `pipx inject sphinx sphinx-rtd-theme` | Clean isolation; depends on pipx availability |

### 3.3 Recommendation: **Option C**

- Zero host-tool prerequisites beyond `python` (already on PATH).
- Project-local (`.venv-docs/` at repo root) so subtask 2 can re-invoke the same `sphinx-build` shim without re-installing.
- `pip freeze` gives a complete reproducible manifest including transitive deps (`Pygments`, `Jinja2`, `MarkupSafe`, `imagesize`, `babel`, `requests`, `snowballstemmer`, `alabaster`, `sphinxcontrib-*`).
- Closest match to the *intent* of "uv add --dev" without inventing a `pyproject.toml` the audit explicitly recorded as absent.

If the team strongly prefers uv-native and accepts the bootstrap step, Option B is interchangeable; only the install command changes.

### 3.4 Idempotency & artifact preservation

- `.venv-docs/` is created with `[ -d .venv-docs ] || python -m venv .venv-docs` so re-runs reuse it.
- The two existing log files (`build-log-warm.txt`, `build-log-after-fix.txt`) are renamed before this run: `build-log-warm.txt` → `build-log-warm-pre-triage.txt`. This is a *file rename*, not a content modification of either an `.rst` file or `conf.py` — it preserves prior-subtask provenance while freeing the canonical filename for this subtask's deliverable.
- `docs/build/.doctrees/` is deleted before the cold run so the cold pass really is cold.
- `docs/build/html/` is deleted before each build (cold removes both html + .doctrees; warm removes only html so doctree cache persists per the user request).

---

## 4. Expected build signals (predicted)

This is **not** the executor's job to triage — subtask 2 owns triage. But predicting what each log will contain helps the executor distinguish "very noisy but successful" from "true hard failure."

### 4.1 Predicted warnings

Per the existing pre-triage warm log (`docs/build/build-log-warm.txt` — the one this plan will rename to `…-pre-triage.txt`), the warm build produced **81 warnings** before any fix. After the post-triage fix landed (`build-log-after-fix.txt`), the warm build produces **6 warnings** (1 docutils ERROR + 5 toctree-missing).

This subtask runs the build *against the current on-disk source*, which already has the triage fixes landed. So the **expected post-fix warning count is 6** for both the cold and warm builds. If this run produces something materially different (e.g. 81 again, or 0), subtask 2 should investigate why.

| Warning class | Count expected | Why |
|---------------|---------------:|-----|
| `toctree contains reference to nonexisting document` | 5 | One per missing page (introduction, getting-started, architecture, service-layer, api-reference). Fires regardless of `nitpicky`. |
| `Unknown target name: "Startup-time validation"` (docutils ERROR) | 1 | At `configuration.rst:254`; foundation page is read-only so this remains escalated |
| `[ref.ref]` undefined-label | 0 | All 9 unique forward-ref anchors are suppressed via `nitpick_ignore` in `conf.py` |
| Duplicate-label | 0 | `autosectionlabel_prefix_document = True` |
| Intersphinx | 0 | `intersphinx_mapping = {}` |

### 4.2 Hard-failure shapes (these mean HTML did NOT generate)

- `ExtensionError: Could not import extension sphinx.ext.autosectionlabel` — Sphinx itself broken
- `ThemeError: no theme named 'sphinx_rtd_theme' found` — theme install failed
- `MasterDocNotFoundError` — `index.rst` not where conf.py expects it
- Hard RST parse abort — corrupted `.rst` file

In all four, exit code is non-zero and HTML is incomplete. **Stop and capture; do not attempt fixes.**

### 4.3 Cold vs warm differences to expect on this docset

- Toctree warnings: identical (early-pass resolution).
- `nitpick_ignore`-suppressed refs: identical (suppression evaluated at resolve-time).
- `:ref:` warnings (if any leaked past suppression): may differ in *order* but not count.
- Duplicate-label warnings: should not appear (autosectionlabel prefix mutes them).
- The user request's "warm-build is canonical" rule still holds — capture both faithfully and let subtask 2 diff.

### 4.4 Why `rm -rf docs/build/html` (and not also `.doctrees`) between cold and warm

The user request is explicit: *delete the HTML output only*; keep the doctree cache so the second build is genuinely warm. Doctree cache persistence is what surfaces warm-only resolution warnings (when present). This plan honors that exactly in §5 Step 5.

---

## 5. Step-by-step execution

All commands assume the working directory is the repo root: `C:\Users\yxinl\OneDrive\Projects\PythonProjects\CoreProjects\OpenTeam`. **Bash syntax** (the platform's primary shell per CLAUDE.md). PowerShell variant in §5-bis.

### Step 1 — Preserve existing logs

```bash
# Rename the two existing log files so this subtask's logs can land at the
# canonical names without overwriting prior-subtask evidence.
[ -f docs/build/build-log-warm.txt ] && \
  mv docs/build/build-log-warm.txt docs/build/build-log-warm-pre-triage.txt

# build-log-after-fix.txt is already uniquely named; leave it untouched.
ls -la docs/build/
```

**Why preserve:** these are the upstream evidence cited by `sphinx_warning_triage_plan_consolidated.md §1` and the consolidation report's verification claims (e.g. "Δ = -75") rely on them being on-disk, content-intact. A rename keeps content; an overwrite would destroy provenance.

### Step 2 — Install Sphinx and sphinx-rtd-theme into a project-local venv

```bash
# 2a. create the venv (idempotent)
[ -d .venv-docs ] || python -m venv .venv-docs

# 2b. upgrade pip inside the venv
.venv-docs/Scripts/python -m pip install --upgrade pip

# 2c. install Sphinx + theme; pin nothing — manifest captures whatever lands
.venv-docs/Scripts/pip install sphinx sphinx-rtd-theme
```

**Expected:** `Successfully installed sphinx-X.Y.Z sphinx-rtd-theme-A.B.C docutils-D.E.F …` plus transitive deps. **On failure (network, dep conflict, no wheel):** capture stdout+stderr to `docs/build/install-log.txt` and **stop** — hand off to subtask 2.

### Step 3 — Verify install

```bash
.venv-docs/Scripts/sphinx-build --version
```

**Expected:** single line `sphinx-build X.Y.Z`, exit 0. **On failure** (`sphinx-build: command not found`, `ImportError`): capture stderr, stop, hand off.

### Step 4 — Capture version manifest

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

`docutils` is recorded explicitly because the user request flags it: docutils warning phrasing has shifted across minor versions and reproducibility-sensitive triage needs the exact version under test.

### Step 5 — Cold build

```bash
# True cold: remove BOTH html output AND doctree cache.
rm -rf docs/build/html docs/build/.doctrees

# Run; merge stderr into stdout (2>&1) BEFORE the pipe so tee captures both
# in emission order. tee always exits 0, so use ${PIPESTATUS[0]} to recover
# Sphinx's exit code.
.venv-docs/Scripts/sphinx-build -b html docs/source docs/build/html 2>&1 \
  | tee docs/build/build-log-cold.txt
COLD_EXIT=${PIPESTATUS[0]}
echo "EXIT_CODE=${COLD_EXIT}" >> docs/build/build-log-cold.txt
echo "Cold build exit code: ${COLD_EXIT}"
```

| `COLD_EXIT` | Meaning | Action |
|-------------|---------|--------|
| 0 | Build succeeded; warnings recorded in log | proceed to Step 6 |
| 1 | Build failed (extension import, theme not found, syntax error, master-doc missing) | **Stop. Hand off cold log + manifest. Do NOT run warm build.** |
| 2 | Config error in `conf.py` | same — stop and hand off |

**Critical:** with `nitpicky = True`, warnings still produce **exit 0**. The build is *expected* to be noisy but exit clean. Only exit ≠ 0 triggers stop.

### Step 6 — Warm build

```bash
# Per user request: remove ONLY the HTML output; keep .doctrees so this
# rebuild is genuinely warm.
rm -rf docs/build/html

# Sanity check that .doctrees survived (printable, non-fatal).
ls -la docs/build/.doctrees/ 2>&1 | head -5 || \
  echo "WARNING: .doctrees missing — warm build will be a second cold build"

# Run the build with the same redirection pattern.
.venv-docs/Scripts/sphinx-build -b html docs/source docs/build/html 2>&1 \
  | tee docs/build/build-log-warm.txt
WARM_EXIT=${PIPESTATUS[0]}
echo "EXIT_CODE=${WARM_EXIT}" >> docs/build/build-log-warm.txt
echo "Warm build exit code: ${WARM_EXIT}"
```

| `WARM_EXIT` | Meaning | Action |
|-------------|---------|--------|
| 0 | warm build succeeded | proceed to Step 7 |
| ≠ 0 | warm build failed even though cold succeeded — rare, suggests warm-only resolution failure | **stop**, capture, hand off, flag as anomaly |

### Step 7 — Count generated HTML pages

```bash
PAGE_COUNT=$(find docs/build/html -name '*.html' -type f | wc -l)
echo "Generated HTML page count: ${PAGE_COUNT}" | tee -a docs/build/build-log-warm.txt
```

Expected count given current source state (4 `.rst` content pages + `index.rst` + `glossary.rst` exist; 5 toctree entries are missing): roughly **6 content HTML files + `genindex.html` + `search.html` = 8 HTML files**, give or take. Exact number is data; subtask 2 compares to expectation.

### Step 8 — Handoff summary

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
  echo "Cold ERROR lines:   $(grep -cE '^Error|ERROR' docs/build/build-log-cold.txt 2>/dev/null || echo 0)"
  echo "Warm ERROR lines:   $(grep -cE '^Error|ERROR' docs/build/build-log-warm.txt 2>/dev/null || echo 0)"
  echo
  echo "--- Reference: prior-subtask logs preserved as ---"
  echo "  docs/build/build-log-warm-pre-triage.txt   (pre-triage warm, 81 warnings)"
  echo "  docs/build/build-log-after-fix.txt         (post-triage warm, 6 warnings)"
} > docs/build/handoff-summary.txt
```

This is the **single file subtask 2 should read first** — exit codes, page count, warning counts, and pointers to every other artifact produced.

### 5-bis. PowerShell variant

`2>&1 | Tee-Object` on PS 5.1 is treacherous: PS wraps native-exe stderr lines in `ErrorRecord` objects and can flip `$?` to `$false` on success. Use `*>` (all-stream redirect) instead, and capture `$LASTEXITCODE`:

```powershell
# Step 5 (cold) — PowerShell
Remove-Item -Recurse -Force docs/build/html, docs/build/.doctrees -ErrorAction SilentlyContinue
& .venv-docs/Scripts/sphinx-build.exe -b html docs/source docs/build/html `
    *> docs/build/build-log-cold.txt
$ColdExit = $LASTEXITCODE
Add-Content docs/build/build-log-cold.txt "EXIT_CODE=$ColdExit"
"Cold build exit code: $ColdExit"
```

`*>` redirects every stream (stdout, stderr, info, warning, verbose, debug) to the file in stream-event order — closest equivalent to bash `2>&1`. Bash form remains preferred because the user request says "verbatim stdout+stderr into a saveable buffer" and `tee` + `${PIPESTATUS[0]}` is the cleanest expression.

---

## 6. Failure-handling matrix

| Stage | Failure shape | Action | Hand-off contains |
|-------|---------------|--------|-------------------|
| 1. preserve | rename fails (file lock, permissions) | Stop. Don't proceed — would clobber prior log on Step 6. | error message; current `docs/build/` listing |
| 2. install | venv creation fails | Stop. | `python -m venv` stderr; OS / Python version |
| 2. install | `pip install` fails (network, no wheel, dep conflict) | Stop. | install stdout+stderr → `docs/build/install-log.txt`; stop reason |
| 3. verify | `sphinx-build --version` errors | Stop. | stderr; output of `python -c 'import sphinx; print(sphinx.__version__)'` if it works |
| 4. manifest | `pip show` / `pip freeze` errors | **Continue** — manifest is informational, not blocking. | whatever was captured |
| 5. cold | `sphinx-build` exit ≠ 0 | Stop. **Do not run warm build.** | cold log only; exit code; manifest |
| 5. cold | exit = 0 but `docs/build/html/index.html` missing | Treat as anomalous. Hand off both logs + directory listing. | cold log; html listing; manifest |
| 6. warm | `rm -rf docs/build/html` errors (lock, permission) | Stop. | error; current state of `docs/build/` |
| 6. warm | exit ≠ 0 (after cold succeeded) | Stop. **Flag explicitly** as warm-only resolution failure (rare and interesting). | both logs; both exit codes |
| 7. count | `find` returns 0 HTML files even with exit 0 | Treat as anomaly. Hand off everything. | both logs; empty html listing |

**Across all rows: capture stdout/stderr and stop. Do not patch `conf.py`, do not edit any `.rst`, do not stub missing pages, do not change theme. Those are subtask 2's calls.**

---

## 7. Deliverables manifest (what subtask 2 receives)

After this plan runs to completion, the directory state is:

```
docs/build/
├── build-log-cold.txt                     ← THIS subtask, raw cold stdout+stderr + EXIT_CODE=N
├── build-log-warm.txt                     ← THIS subtask, raw warm stdout+stderr + EXIT_CODE=N + page count
├── build-log-warm-pre-triage.txt          ← preserved from prior run (81 warnings, pre-fix)
├── build-log-after-fix.txt                ← preserved from prior run (6 warnings, post-fix)
├── version-manifest.txt                   ← Python, Sphinx, sphinx-rtd-theme, docutils, full pip freeze
├── handoff-summary.txt                    ← exit codes, page count, file listing, WARNING/ERROR counts, ptr to other artifacts
├── install-log.txt                        ← only if pip install failed (else absent)
├── .doctrees/                             ← Sphinx doctree cache (NOT to delete between runs)
└── html/                                  ← canonical output from the warm build
    ├── index.html, configuration.html, inference-models.html, operations.html, glossary.html
    ├── genindex.html, search.html
    └── _static/, _images/, etc.
```

If install or build failed before Step 6, the warm log is absent and the handoff summary is partial — that *is* the signal to subtask 2 that the build stopped early.

**Subtask 2's expected entry point:** `docs/build/handoff-summary.txt`. From there subtask 2 picks which log to triage first and decides whether the post-fix `build-log-after-fix.txt` is still authoritative or has drifted from the new warm log.

### What this subtask does NOT deliver

- A clean build (warnings expected and not in scope to fix here).
- A list of *which* warnings need fixing — subtask 2's call.
- Updated `conf.py` — even if the build reveals config-level cause.
- Stubs / authored content for the 5 missing prose pages — `sphinx_scaffolding_audit.md §4` already enumerates these.
- A diff against the prior pre-triage / post-fix logs — subtask 2 owns that diff.

---

## 8. Compliance checklist (what we will NOT do)

Per the user request: *"do not modify ANY existing files (not the 8 prose pages, not conf.py / index.rst / glossary.rst); this subtask is install + execute + capture only."*

The plan does **not**:

- Modify or create any file under `docs/source/` (verified: every command in §5 writes only under `docs/build/`, `.venv-docs/`, or stdout).
- Modify `.gitignore`, `pyproject.toml` (which doesn't exist), or any other repo-root config file.
- Touch `src/`, `test/`, `conftest.py`, or any code directory.
- Stub or author any of the 5 missing prose pages (`introduction`, `getting-started`, `architecture`, `service-layer`, `api-reference`).
- Edit `conf.py` to lower `nitpicky`, change theme, or alter `nitpick_ignore`.
- Run `git add` / `git commit` / `git push`. The user did not ask for a commit; per harness git-safety rules we don't commit unless asked.
- Overwrite `build-log-warm.txt` or `build-log-after-fix.txt` (Step 1 renames the former to preserve content).

The plan **does** create:

- `.venv-docs/` at repo root (Python venv directory).
- New files under `docs/build/`: `build-log-cold.txt`, `build-log-warm.txt`, `version-manifest.txt`, `handoff-summary.txt`, optionally `install-log.txt`.
- Renames: `build-log-warm.txt` → `build-log-warm-pre-triage.txt` (content preserved verbatim).

Neither directory creation, file creation under `docs/build/`, nor a content-preserving rename qualifies as "modify an existing file" under any reasonable reading of the constraint.

---

## 9. Quick-start cheatsheet (condensed copy-paste)

```bash
# from repo root, bash
# 1. preserve existing logs
[ -f docs/build/build-log-warm.txt ] && \
  mv docs/build/build-log-warm.txt docs/build/build-log-warm-pre-triage.txt

# 2. install
[ -d .venv-docs ] || python -m venv .venv-docs
.venv-docs/Scripts/python -m pip install --upgrade pip
.venv-docs/Scripts/pip install sphinx sphinx-rtd-theme

# 3. verify + manifest
.venv-docs/Scripts/sphinx-build --version
mkdir -p docs/build
{
  .venv-docs/Scripts/python --version
  .venv-docs/Scripts/sphinx-build --version
  .venv-docs/Scripts/pip show sphinx sphinx-rtd-theme docutils
  echo "---"
  .venv-docs/Scripts/pip freeze
} > docs/build/version-manifest.txt 2>&1

# 4. cold build
rm -rf docs/build/html docs/build/.doctrees
.venv-docs/Scripts/sphinx-build -b html docs/source docs/build/html 2>&1 \
  | tee docs/build/build-log-cold.txt
COLD_EXIT=${PIPESTATUS[0]}
echo "EXIT_CODE=${COLD_EXIT}" >> docs/build/build-log-cold.txt
[ "${COLD_EXIT}" -ne 0 ] && echo "COLD BUILD FAILED — STOP" && exit "${COLD_EXIT}"

# 5. warm build
rm -rf docs/build/html
.venv-docs/Scripts/sphinx-build -b html docs/source docs/build/html 2>&1 \
  | tee docs/build/build-log-warm.txt
WARM_EXIT=${PIPESTATUS[0]}
echo "EXIT_CODE=${WARM_EXIT}" >> docs/build/build-log-warm.txt

# 6. count + handoff
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

Read `docs/build/handoff-summary.txt` first; everything else is in `docs/build/`.

---

## 10. Open questions (non-blocking; surface in handoff if not resolved)

1. **Is creating `.venv-docs/` at repo root acceptable** under the "do not modify existing files" framing? Plan reads the constraint as applying to source/config files, not a tooling venv. Belt-and-suspenders alternative: `docs/.venv/`.
2. **Pin versions or take latest?** User request says "record the exact installed versions … for the build report" — implies latest-acceptable, manifest captures whatever lands. Plan assumes latter.
3. **If cold build fails, debug or just capture-and-stop?** Plan assumes strict capture-and-stop per user request's exact wording. If executor is authorized to *peek* (read traceback for handoff context), update handoff with findings — but **do not** edit any `.rst` or `conf.py`.
4. **Should `.venv-docs/` persist** for subtask 2 or be removed on completion? Plan assumes persistence; subtask 2 will need it to re-run the build during triage.
5. **Are the two preserved logs (`build-log-warm-pre-triage.txt`, `build-log-after-fix.txt`) supposed to remain on disk** indefinitely, or is this subtask the right place to archive/delete them? Plan keeps them — they are evidence cited by the consolidation report. Decision deferred to subtask 2 / parent spec owner.

If the executor proceeds without answers, default to the assumptions above and surface them explicitly in `handoff-summary.txt`.

---

## 11. Cross-references

- `docs/_plan/sphinx_scaffolding_audit.md` — upstream audit; predicts toctree-missing warnings + read-only foundation status for `configuration.rst` / `inference-models.rst` / `operations.rst`.
- `docs/_plan/sphinx_build_capture_plan.md` (456 lines) — first prior plan for this subtask.
- `docs/_plan/sphinx_initial_build_plan.md` (520 lines) — second prior plan; near-duplicate scope.
- `docs/_plan/sphinx_warning_triage_plan_consolidated.md` — subtask 2 plan + post-execution verification report (the one that confirms `build-log-after-fix.txt` shows 6 warnings = predicted).
- `docs/_plan/sphinx_warning_triage_subtask2_deliverable.md` — subtask 2 deliverable artifact.
- `docs/source/conf.py` — `nitpicky=True`, `autosectionlabel_prefix_document=True`, 9-tuple `nitpick_ignore` block; the configuration that determines the *shape* of the warm log.
- `docs/build/build-log-warm.txt` (current, pre-rename) — pre-triage 81-warning warm log; will be renamed to `build-log-warm-pre-triage.txt` in Step 1.
- `docs/build/build-log-after-fix.txt` — post-triage 6-warning warm log; preserved untouched.
