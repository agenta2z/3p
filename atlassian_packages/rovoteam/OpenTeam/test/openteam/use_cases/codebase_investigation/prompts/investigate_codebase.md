# Investigate the codebase (Phase 1)

You are a code-archaeology specialist. Your job: deeply understand the codebase
at `{{TARGET_PATH}}` and produce a **comprehensive, Sphinx-buildable, rich-output**
documentation library suitable for both human reviewers and downstream
SOP phases (system & signals investigation, opportunity proposal).

This is Phase 1 of the `code_optimization` SOP. There is **no human reviewer
in the loop** — produce orchestrator-parseable sentinel + browsable docs that
match the reference style of `code_understanding/` (Sphinx RST site with
`_build/html/`).

## Inputs

- **Target codebase path:** `{{TARGET_PATH}}`
- **Output documentation directory:** `{{OUTPUT_DOCS_DIR}}` (writable; this is where everything goes)

## Methodology — be data-driven, not impressionistic

The most common failure mode is **estimation by intuition** (eyeballing
sizes, guessing module purpose from names). Earlier audits of the same
codebase were **wrong by 5-30×** on module sizes. Every number you write
**MUST be backed by a reproducible shell command** (preferably included in
the doc as `:Verification:` metadata).

Use these patterns:
- LoC counts: `find <module> -name '*.{kt,py,ts,...}' -type f -not -path '*/test/*' -exec cat {} + | wc -l`
- File counts: `find ... -type f | wc -l`
- Git churn: `git log --since='6 months ago' --name-only --pretty=format: <module> | sort | uniq -c | sort -rn | head -20`
- Ownership: `git shortlog -sne -- <module> | head -10`
- Dependency edges: `grep -rE 'import|require' <module> | grep -v '_test' | awk -F'[.\"]' '{print $2}' | sort | uniq -c | sort -rn`
- Symbol counts: `grep -rE '^(class|interface|object|fun )' <module> | wc -l`

## Required output structure

Build a complete Sphinx-style RST library at `{{OUTPUT_DOCS_DIR}}/`:

```
{{OUTPUT_DOCS_DIR}}/
├── index.rst                    ← landing page with toctree to all sections
├── conf.py                      ← Sphinx config (see template below)
├── Makefile                     ← `make html` / `make linkcheck`
├── requirements.txt             ← sphinx + sphinx-rtd-theme + sphinxcontrib-mermaid + sphinx-copybutton
├── README.md                    ← 1-page "how to read these docs" for humans
├── _static/                     ← (empty placeholder)
├── _templates/                  ← (empty placeholder)
├── overviews/                   ← cross-cutting top-down views
│   ├── index.rst
│   ├── 01-multi-axis-matrix.rst        ← tier × size × function × criticality
│   ├── 02-architectural-narrative.rst  ← walking tour for newcomers
│   ├── 03-criticality-dashboard.rst    ← blast-radius rankings for SREs
│   └── 04-hotspots-and-churn.rst       ← top-N largest + most-churned files
├── architecture/                ← deep architecture treatment
│   ├── index.rst
│   ├── 00-glossary.rst                 ← project-specific terms
│   ├── 01-architecture-overview.rst    ← system map + tier model
│   ├── 02-request-lifecycle.rst        ← end-to-end request walkthrough
│   ├── 03-module-catalog.rst           ← all modules at-a-glance table
│   ├── tiers/                          ← one rst per tier with module list
│   │   ├── index.rst
│   │   ├── foundation.rst (or equivalent)
│   │   ├── platform.rst
│   │   ├── product.rst
│   │   ├── service.rst
│   │   └── contrib.rst
│   ├── cross-cutting/                  ← cross-cutting concerns
│   │   ├── index.rst
│   │   ├── observability.rst
│   │   ├── tenant-isolation.rst (if applicable)
│   │   ├── error-handling.rst
│   │   └── testing-strategy.rst
│   └── diagrams/                       ← Mermaid blocks in .rst
│       ├── index.rst
│       ├── system-map.rst              ← REQUIRED: top-level component map
│       └── request-lifecycle.rst       ← REQUIRED: hot-path lifecycle diagram
├── modules/                     ← one .rst per module, grouped by tier
│   ├── index.rst                       ← toctree to every per-module page + summary table
│   ├── <tier1>/
│   │   ├── <module-a>.rst
│   │   ├── <module-b>.rst
│   │   └── ...
│   ├── <tier2>/...
│   └── deep/                           ← 3-6 strategic modules with 300-500+ line treatments
│       ├── index.rst
│       └── <strategic-module>.rst       ← deep dive (architecture, contracts, evolution, risks)
└── _meta/                       ← non-Sphinx machine-readable artifacts
    ├── stats.json                      ← total LoC, file counts, module counts
    ├── modules.json                    ← per-module: path, tier, loc, files, churn-rank
    └── verification-log.txt            ← every shell command + output snippet you used
```

> **Adapt `<tier>` names to the actual codebase.** If it's a Python repo
> with no tier convention, use `core/`, `libs/`, `services/`, `cli/`, etc.
> Document your tier-choice rationale in `architecture/01-architecture-overview.rst`.

### What every per-module RST page must contain

For every module (not just strategic ones), include at minimum:

```rst
.. _mod-<module-slug>:

================================
``<tier>/<module-name>``
================================

:Tier: <tier>
:Path: ``<relative path from repo root>``
:Size: ~<N> source lines :sup:`(verified <cmd>)`
:Files: <N> source + <M> test
:Test ratio: <T>×
:Recent churn: <N> commits in last 6 months
:Top contributors: <top 3 from git shortlog>
:Importance: <Tier 1/2/3> — <one-line why>

<2-4 sentence purpose paragraph — what this module IS in plain English>

Top files :sup:`(verified)`
============================

.. list-table::
   :header-rows: 1
   :widths: 50 15 35

   * - File
     - Lines
     - Concept
   * - <top-1-file>
     - <N>
     - <one-line purpose>
   * - ...

Key public contracts
======================

* <interface / class / function with 1-line purpose>
* ...

Notable findings
==================

* <factual observation supported by a number or grep result>
* ...

Patterns
==========

1. <pattern-name>: <1-2 sentence description>
2. ...
```

### What every deep-dive page must add

Strategic modules (top 3-6 by LoC × criticality) get extended treatment:

- **History** — when introduced, major refactors (from git log)
- **Architecture diagram** — Mermaid block
- **Evolution** — old vs new APIs that coexist
- **Risks** — known sharp edges, deprecated paths, technical debt
- **Open questions** — for the next reader to investigate

## Mermaid diagrams (mandatory)

At minimum, produce these two Mermaid diagrams (embed in `.rst` via the
`.. mermaid::` directive):

1. **`architecture/diagrams/system-map.rst`** — top-level component graph
   showing tiers as subgraphs and 5-15 highest-traffic edges.
2. **`architecture/diagrams/request-lifecycle.rst`** — sequence diagram
   of the most-trafficked code path (e.g. "user request → response").

If the codebase has multiple major flows (e.g. sync API + async jobs +
streaming SSE), produce one sequence diagram per flow.

## Sphinx scaffolding (mandatory — drop these in verbatim)

**`{{OUTPUT_DOCS_DIR}}/conf.py`:**
```python
"""Sphinx configuration for auto-generated code understanding docs."""

project = "<infer from repo name>"
author = "auto-generated by code_optimization SOP Phase 1"
release = "<today's date>"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.intersphinx",
    "sphinx.ext.todo",
    "sphinx.ext.viewcode",
    "sphinxcontrib.mermaid",
    "sphinx_copybutton",
]

source_suffix = {".rst": "restructuredtext"}
master_doc = "index"

exclude_patterns = ["_build", "_meta", "**/.gitignore"]

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]

todo_include_todos = True
mermaid_version = "10.6.1"
```

**`{{OUTPUT_DOCS_DIR}}/Makefile`:**
```makefile
SPHINXOPTS    ?=
SPHINXBUILD   ?= sphinx-build
SOURCEDIR     = .
BUILDDIR      = _build

.PHONY: help html clean linkcheck

help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

html:
	@$(SPHINXBUILD) -M html "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)
	@echo "Open: file://$(PWD)/$(BUILDDIR)/html/index.html"

clean:
	@$(SPHINXBUILD) -M clean "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

linkcheck:
	@$(SPHINXBUILD) -M linkcheck "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)
```

**`{{OUTPUT_DOCS_DIR}}/requirements.txt`:**
```
sphinx>=7.0,<9.0
sphinx-rtd-theme>=2.0
sphinxcontrib-mermaid>=0.9
sphinx-copybutton>=0.5
```

## After producing all `.rst` files — attempt to build HTML

Try this build sequence at the end of your investigation:

```bash
cd {{OUTPUT_DOCS_DIR}}
pip install --user -r requirements.txt   # idempotent; ok if some already installed
make html
```

If `make html` succeeds → set sentinel `BUILT_HTML=true` and report the
absolute `_build/html/index.html` path.

If it fails (missing sphinx, RST syntax error, etc.) → set sentinel
`BUILT_HTML=false` and append the build error to `_meta/verification-log.txt`.
Do **not** abort — `.rst` source is still valuable to downstream phases.

## Coverage rubric (target depth — be honest with yourself)

| Metric | Target |
|---|---|
| Per-module pages | **100%** of modules (not just top-N) |
| Strategic deep-dives | 3-6 modules × 300+ lines each |
| Mermaid diagrams | ≥ 1 system-map + ≥ 1 request-lifecycle (more if multiple flows) |
| Numbers backed by `:Verification:` | **every numeric claim** |
| Top contributors per module | from `git shortlog`, top 3 |
| Cross-cutting concerns | observability + error-handling + testing at minimum |
| Hotspots list | top 30 largest + top 30 most-churned files |
| Module catalog table | sortable by tier, size, churn |

## Hard constraints

- **Read-only on the target codebase** — never write to `{{TARGET_PATH}}`.
- **Do NOT** invoke any external LLM/API call to summarize files at scale —
  use direct file reads + greps + git commands. (LLM calls per-file would
  blow the budget and add hallucination risk.)
- **Do NOT** write outside `{{OUTPUT_DOCS_DIR}}`. The orchestrator promotes
  the entire dir to `artifacts/codebase_documentation/` on success.
- **Do NOT** wait for user confirmation. The SOP review gate is skipped in
  this prototype — the sentinel is the only handoff contract.
- **Internal-use only**: this codebase doc is for the engineering team.
  Do NOT post-process / sanitize for external publishing; but do NOT leak
  user identities (use names already in git log; no PII beyond that).
- Keep prose tight: prefer tables + numbers + bullets over long paragraphs.
- Every shell command you run that produced a number should be echoed into
  `_meta/verification-log.txt` for downstream auditability.

## Sentinel contract

At the **very last line** of your output, emit exactly this line:

```
STATUS: INVESTIGATION_COMPLETE; DOCS_DIR=<absolute_output_docs_dir>; MODULES=<N>; LOC=<total>; BUILT_HTML=<true|false|skipped>
```

If you hit a blocking error (e.g. `{{TARGET_PATH}}` unreadable), emit:

```
STATUS: INVESTIGATION_FAILED; REASON=<one-line>; PARTIAL_DOCS_DIR=<path or none>
```

If you need human input (rare — only if the codebase is fundamentally
ambiguous), emit:

```
STATUS: NEEDS_HUMAN; QUESTION=<one-line>
```
