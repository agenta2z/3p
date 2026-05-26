# Sphinx Scaffolding Audit — `responsible-ai-api` docs

**Subtask:** Author `docs/source/conf.py` and `docs/source/index.rst` that wire
the prose pages + glossary into a buildable site. Build itself is out of scope
(owned by subtask 3).

**Audit date:** 2026-05-04
**Auditor scope:** Inspection only — no `sphinx-build` invocation per task rules.

---

## TL;DR

* `conf.py` already exists at `docs/source/conf.py` and meets every spec item
  in the task description (13/13 settings present and correct, Python parses
  and executes cleanly).
* `index.rst` already exists at `docs/source/index.rst` and meets every spec
  item (title with matching underlines, hero paragraphs naming the four
  endpoint families and principal modules, single `:maxdepth: 2` toctree in
  the exact 9-page reading order, indices/tables section).
* `docs/source/_static/` exists and is effectively empty (one `.gitkeep`).
* **Disk-vs-toctree mismatch is the only flagged issue:** of the 9 toctree
  basenames, 4 resolve to existing `.rst` files; **5 do not exist on disk
  yet** (`introduction`, `getting-started`, `architecture`, `service-layer`,
  `api-reference`). The glossary itself acknowledges this state — see
  `glossary.rst` lines 23–32 — so the gap is known to the docs work as a
  whole, not a regression introduced by scaffolding.
* No edits required to either scaffolding file. Subtask 3 (build) will need
  to either author or stub the 5 missing pages before the build will succeed
  with `nitpicky = True`.

---

## 1. `conf.py` audit (`docs/source/conf.py`, 82 lines)

Verified by `python -c "import ast; ast.parse(open(...).read())"` (parses
cleanly) and `runpy.run_path` (executes cleanly with no import side-effects on
the build env — confirmed by reading values back).

| # | Spec item | Required value | Observed | Line |
|---|-----------|----------------|----------|------|
| 1 | `project` | `'responsible-ai-api'` | `'responsible-ai-api'` | 15 |
| 2 | `author` | from pyproject.toml or `'Atlassian RAI Team'` | `'Atlassian RAI Team'` (fallback; no pyproject.toml found at repo root or under `docs/`, so fallback is correct and is documented in the comment at lines 17–19) | 20 |
| 3 | `version` | from pyproject.toml or `'0.1.0'` w/ comment | `'0.1.0'` hardcoded; comment at lines 22–24 explains the fallback and points at `tomllib` as the upgrade path; `release = version` at line 26 | 25–26 |
| 4 | Theme | `sphinx_rtd_theme` | `html_theme = 'sphinx_rtd_theme'` | 61 |
| 5 | Alabaster fallback comment | top-of-file | Lines 8–11: explains alabaster is the swap, ships with Sphinx, no extra install | 8–11 |
| 6 | Extensions | `['sphinx.ext.autosectionlabel', 'sphinx.ext.intersphinx']` | exactly that, with rationale comments per extension explaining why `autosectionlabel` is essential and that `intersphinx_mapping` is empty by default | 30–39 |
| 7 | `autosectionlabel_prefix_document` | `True` | `True`; comment (lines 41–46) correctly notes this only prefixes auto-generated section labels, not explicit `.. _foo:` anchors. **This nuance matters** — see §4. | 47 |
| 8 | `nitpicky` | `True` | `True`, with comment (lines 49–51) explicitly handing the triage responsibility off to subtask 3 | 52 |
| 9 | `source_suffix` | `'.rst'` | `'.rst'` | 54 |
| 10 | `master_doc` | `'index'` | `'index'` | 55 |
| 11 | `exclude_patterns` | `['_build', 'Thumbs.db', '.DS_Store']` | exact match | 57 |
| 12 | `html_static_path` | `['_static']` (and dir exists) | `['_static']`; dir at `docs/source/_static/` contains `.gitkeep` only | 63 |
| 13 | `html_theme_options` | dict with `'navigation_depth': 4` | `{'navigation_depth': 4}` with rationale comment about deep `api-reference` / `service-layer` toctrees | 65–71 |

**Runtime sanity (no Sphinx run, just `runpy`):**

```
project                                   = 'responsible-ai-api'
author                                    = 'Atlassian RAI Team'
version                                   = '0.1.0'
release                                   = '0.1.0'
extensions                                = ['sphinx.ext.autosectionlabel', 'sphinx.ext.intersphinx']
autosectionlabel_prefix_document          = True
nitpicky                                  = True
source_suffix                             = '.rst'
master_doc                                = 'index'
exclude_patterns                          = ['_build', 'Thumbs.db', '.DS_Store']
html_theme                                = 'sphinx_rtd_theme'
html_static_path                          = ['_static']
html_theme_options                        = {'navigation_depth': 4}
intersphinx_mapping                       = {}
```

All spec keys present, no extras that conflict with the spec.

**Verdict:** No changes required.

---

## 2. `index.rst` audit (`docs/source/index.rst`, 40 lines)

| # | Spec item | Observed | Line(s) |
|---|-----------|----------|---------|
| 1 | Title `Responsible AI API Documentation` | Title text matches exactly; 32-char overline + 32-char underline (`========================================` × 32) framing the title — Sphinx accepts both styles, and the matched overline+underline style is conventional for the document root | 1–3 |
| 2 | Hero paragraphs | Two paragraphs (lines 5–13 and 15–20) covering: HTTP service for content moderation, the four endpoint families verbatim ("text moderation, image moderation, admin (feature-flag and configuration) controls, and health/observability endpoints"), the principal modules namedrop (`controllers`, per-kind `service` orchestrators, `inference_models` clients with Triton/AI Gateway/SageMaker, plus the cross-cutting `config`, `feature_service`, `slauth`, `metrics`); second paragraph explains the docset's intent (read end-to-end then reference) | 5–20 |
| 3 | `.. toctree::` directive | Single directive, options `:maxdepth: 2` and `:caption: Contents:` exactly as specified; blank line separates options from entries (RST-mandatory) | 22–24 |
| 4 | Toctree entries (exact order, file basenames, no `.rst`) | `introduction` → `getting-started` → `architecture` → `service-layer` → `inference-models` → `configuration` → `api-reference` → `operations` → `glossary`. Order matches spec verbatim. | 26–34 |
| 5 | Indices and tables section | `Indices and tables` heading with matching 18-char `==================` underline, `:ref:`genindex`` and `:ref:`search`` bullets | 36–40 |

**Inspection-only RST sanity checks:**

* Title overline/underline lengths both = title length (32 chars). ✓
* Indices section underline length (18) = heading length (18). ✓
* Toctree directive followed by blank line, then indented entries. ✓
* No tabs in indentation; consistent 3-space indent under `.. toctree::`. ✓
* No stray directives, no malformed inline markup detected on visual scan.

**Verdict:** No changes required.

---

## 3. `_static/` directory

Path: `docs/source/_static/`
Contents: `.gitkeep` (zero bytes).

The spec said "create the empty `_static/` dir". The directory exists and is
functionally empty; the `.gitkeep` is a standard convention for keeping an
empty directory under git and is harmless to Sphinx (Sphinx copies `_static/`
contents to the build output as-is; a `.gitkeep` is just a hidden zero-byte
file in the static asset tree, not a referenced asset).

**Verdict:** Compliant. If a strict reading of "empty" is required by a
downstream gate, the `.gitkeep` can be removed — but doing so would untrack
the directory in git.

---

## 4. Cross-check: toctree basenames vs `.rst` files on disk

This is the critical finding. The toctree lists 9 page basenames. Disk
inventory of `docs/source/*.rst`:

| Toctree basename | Expected file | Exists? |
|------------------|----------------|---------|
| `introduction` | `docs/source/introduction.rst` | **MISSING** |
| `getting-started` | `docs/source/getting-started.rst` | **MISSING** |
| `architecture` | `docs/source/architecture.rst` | **MISSING** |
| `service-layer` | `docs/source/service-layer.rst` | **MISSING** |
| `inference-models` | `docs/source/inference-models.rst` | exists (57,929 bytes) |
| `configuration` | `docs/source/configuration.rst` | exists (104,685 bytes) |
| `api-reference` | `docs/source/api-reference.rst` | **MISSING** |
| `operations` | `docs/source/operations.rst` | exists (48,870 bytes) |
| `glossary` | `docs/source/glossary.rst` | exists (35,858 bytes) |

**Score: 4 of 9 entries resolve to a file on disk.**

### Tension with the task description

The user request opens with: *"Author the Sphinx scaffolding … that wires the
**eight already-authored prose pages** plus the glossary (subtask 2) into a
buildable site"* and later: *"Do NOT modify any of the eight already-authored
pages — they have been line-by-line audited and changes risk regression"*.

In reality only **three prose pages** (`configuration`, `inference-models`,
`operations`) and the glossary are authored. Five prose pages
(`introduction`, `getting-started`, `architecture`, `service-layer`,
`api-reference`) do not exist on disk.

This is **not a scaffolding bug** — both `conf.py` and `index.rst` faithfully
encode the spec, which itself dictates the 9-page toctree. It is a precondition
gap upstream of this subtask.

### Independent corroboration from `glossary.rst`

The glossary's own lead note (lines 23–32) flags the same gap, in its own
words:

> Five pages — ``introduction``, ``getting-started``, ``architecture``,
> ``service-layer``, ``api-reference`` — are forward-referenced by anchor
> name from the existing pages but are **not yet authored**. Their anchors
> appear in the :ref:`anchor-map` below tagged as ``(forward-referenced —
> target page not yet authored)`` so the registry is honest about what
> currently resolves under :term:`nitpicky mode`.

So the inconsistency between the task description ("eight already-authored
prose pages") and disk reality (three) is something the docs work as a whole
already knows about and tracks in the anchor map — the glossary is internally
honest about the gap.

### Build-time impact for subtask 3

When subtask 3 runs `sphinx-build`, the following will fire even *before*
`nitpicky` triage:

1. **Five "toctree contains reference to nonexisting document"** warnings
   (one per missing basename). These are toctree-resolution errors and fire
   at any nitpicky setting; they are the loudest and are usually the first
   thing to triage.
2. **Many `:ref:` warnings under `nitpicky`**: every `:ref:`introduction``,
   `:ref:`getting-started``, `:ref:`architecture``, `:ref:`service-layer``,
   `:ref:`api-reference`` in the existing pages will fail to resolve. The
   existing `configuration.rst`, `inference-models.rst`, `operations.rst`,
   and `glossary.rst` all use these forward references.
3. **`:term:` warnings** if any term referenced from prose pages is not
   defined in `glossary.rst`. (Out of scope for this audit; flagged for
   subtask 3.)

### Recommendation for subtask 3 (informational only — out of scope here)

Two options for closing the gap, in increasing order of effort:

* **(A) Stub pages**: create five minimal `.rst` files, each with the
  expected explicit anchor at the top (`.. _introduction:`, `.. _getting-started:`,
  `.. _architecture:`, `.. _service-layer:`, `.. _api-reference:`) and a
  short "Page not yet authored — see :ref:`glossary` for forward-referenced
  anchors" placeholder. This silences the toctree errors and most of the
  `:ref:` errors immediately, at the cost of putting placeholder pages in
  the rendered site.
* **(B) Author the full pages** as their own subtasks. This is the durable
  fix and is presumably what the task graph contemplates (subtask 2 was the
  glossary; the five missing pages are presumably their own, separate
  subtasks).

Either way, the scaffolding itself does not need to change.

---

## 5. Why `autosectionlabel_prefix_document = True` is correct here

Worth recording explicitly because it is a subtle interaction:

* The flag prefixes **auto-generated section labels** with the document name
  (e.g. the H1 "Inference Models" on `inference-models.rst` becomes the
  label `inference-models:Inference Models`, not `Inference Models`).
* It does **not** affect explicit `.. _foo:` anchors. Those still resolve
  as the bare name `foo` regardless of which document declared them.
* The existing prose pages mix both styles: explicit anchors at the top of
  each page (e.g. `.. _config-overview:`, `.. _inf-models:`,
  `.. _infra-overview:`, `.. _ops-overview:`, `.. _glossary:`) and section
  headings that autosectionlabel turns into auto labels.
* Cross-page references in the existing pages use bare names
  (`:ref:`config-overview``, `:ref:`introduction``) — which **only work**
  if the target is an explicit `.. _foo:` anchor on the destination page.
  The five missing pages are expected to provide `.. _introduction:`,
  `.. _getting-started:`, `.. _architecture:`, `.. _service-layer:`,
  `.. _api-reference:` anchors at their top.
* If `autosectionlabel_prefix_document` were `False`, every common heading
  ("Purpose & scope", "Documented ambiguities", "See also") that recurs
  on every page would collide and Sphinx would warn about duplicate labels.
  With it `True`, each H2/H3 gets prefixed by its document name and there
  are no collisions.

The explanatory comment at `conf.py:41–46` already captures this — included
here so the audit trail does not lose it.

---

## 6. Files touched by this subtask

None. Both scaffolding files were already on disk and correct; the
`_static/` directory was already in place. This subtask's deliverable is
the audit/verification report itself (this document).

For the avoidance of doubt, the following paths are **unchanged**:

* `docs/source/conf.py`
* `docs/source/index.rst`
* `docs/source/_static/` (and `.gitkeep`)
* `docs/source/configuration.rst` (untouched per "do not modify" rule)
* `docs/source/inference-models.rst` (untouched)
* `docs/source/operations.rst` (untouched)
* `docs/source/glossary.rst` (untouched)

---

## 7. Handoff to subtask 3 (the build)

Subtask 3 should proceed expecting these signals from the build:

1. Five `toctree contains reference to nonexisting document` warnings
   for the missing basenames listed in §4.
2. Numerous `nitpicky`-mode `:ref:` warnings for forward references to the
   missing pages' anchors.
3. Possible `:term:` warnings if forward-referenced terms are not in the
   glossary (not investigated here).

If subtask 3's mandate is to drive the build to a clean state, it must
either (a) stub the missing pages or (b) wait for the page-authoring
subtasks to complete. The scaffolding (conf.py + index.rst) does **not**
need any further change to support either path.
