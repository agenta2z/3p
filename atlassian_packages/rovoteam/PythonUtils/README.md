# PythonUtils

A batteries-included foundation library for the **rovoteam** workspace — 19
sub-packages spanning filesystem, I/O, strings, parallelism, NLP, statistics,
configuration, retrieval, sessions, and a small DSL for **dynamic-expansion
workflows / work-graphs** that are the substrate of AgentFoundation and
OpenTeam.

```
python_utils/
├── algorithms/         # graphs, trees, arrays, search
├── cli_utils/          # shell command rendering + execution
├── common_objects/     # Serializable, Workflow, WorkGraph, Stategraph, VariableManager
├── common_utils/       # array/iter/map/typing helpers + async glue
├── config_utils/       # YAML+Hydra instantiate, alias registry
├── console_utils/      # multi-backend coloured output (Rich / Colorama / Textual)
├── datetime_utils/     # timers, date iteration, format inference
├── external/           # vendored deps (rank_bm25, colorama, …)
├── io_utils/           # JSON / pickle / CSV / artifacts / on-storage lists
├── mp_utils/           # parallel_process, queued_executor (sync + async)
├── nlp_utils/          # sanitization, readability, POS-entity extraction
├── path_utils/         # AllowedPath, MergedSpace, resolve, workspace
├── pd_utils/           # pandas selection / transformation / time-series
├── retrieval_utils/    # IR index/query primitives
├── service_utils/      # storage / search / messaging / sessions backends
├── stat_utils/         # aggregation + pairwise metrics
└── string_utils/       # 24 modules: matching, parsing, templating, casing
```

## Install

```bash
# from rovoteam workspace root
uv sync                    # installs python-utils + siblings + dev deps
```

`python_utils` is also `pip install -e PythonUtils/` -compatible if used outside
the workspace; it has no required runtime deps beyond stdlib (each sub-package
declares its extras lazily — e.g. `omegaconf` for `config_utils`, `pandas` for
`pd_utils`).

## Quickstart

### Dynamic-expansion workflow (the headline feature)

A planner step emits N worker steps **at runtime**; they splice in between the
planner and any downstream steps. Deterministic by default; resumable.

```python
from python_utils.common_objects.workflow import Workflow, StepWrapper, ExpansionResult

def plan(text):
    topics = ["summarize", "extract", "verify"]
    return ExpansionResult(
        result=text,
        new_steps=[StepWrapper(lambda prev, t=t: worker(t, prev), name=f"work_{t}")
                   for t in topics],
    )

wf = Workflow(
    steps=[StepWrapper(plan, name="plan"), StepWrapper(finalize, name="finalize")],
    max_expansion_events=3,                  # opt-in gate
)
result = wf.run("input text")
```

The companion `WorkGraph` is the DAG analogue — a leaf node returns a
`GraphExpansionResult(subgraph=SubgraphSpec(nodes=…, entry_nodes=…))` and the
attached subgraph is wired into the node's `next`. See
[`examples/python_utils/common_objects/workflow/`](examples/python_utils/common_objects/workflow/)
and [`workgraph/`](examples/python_utils/common_objects/workgraph/) for 12
runnable scenarios incl. nested expansion, BTA diamond, resumability after
LLM-driven breakdown, and splice-mode pure-planner.

### Config-driven instantiation

```python
from python_utils.config_utils import register_class, load_config, instantiate

@register_class("my.alias")
class MyService: ...

cfg = load_config("config.yaml")            # OmegaConf + Hydra
service = instantiate(cfg.service)          # resolves alias -> class -> __init__
```

### Path access with policy

```python
from python_utils.path_utils import AllowedPath, MergedSpace, PathAccess

space = MergedSpace(roots=[".overlay", ".base"], write_root=".overlay")
text = space.read_text("config.yaml")       # first-match-wins across roots
space.write_text("config.yaml", text)        # writes go to overlay only

ap = AllowedPath("./data", access=PathAccess.READ | PathAccess.WRITE)
```

### Parallel + colored output

```python
from python_utils.mp_utils import parallel_process
from python_utils.console_utils import hprint, print_table

results = parallel_process(items, fn=process_one, n_workers=8, mode="pool")
hprint("done", color="green")
print_table(results, headers=["id", "status"])
```

---

## Sub-package reference

### Foundations

#### `path_utils` · filesystem with policy
- `AllowedPath`, `PathAccess` (IntFlag R/W/X) — declare what a process may touch
- `MergedSpace` — overlay multiple roots, first-match reads, configurable write target
- `resolve_path_()` — resolve with glob fallback
- `ensure_parent_dir_existence()` — make parents before write

#### `io_utils` · multi-format I/O
- `read_all_text_()` / `write_all_text_()` — text with encoding
- `jsonfy()` / `write_json()` — JSON with **artifact part-splitting**
- `pickle_save()` / `pickle_load()` — gzip + parts
- `CSVReader` / `CSVWriter` — typed CSV
- `OnStorageLists` — list where each item is its own file
- `@artifact` / `@artifact_type` — decorators marking class fields for part-extraction

#### `string_utils` · 24 modules
- `contains_any()` / `contains_all()` — multi-substring predicates
- `extract_between()` / `extract_multiple_between()` — substring extraction
- `string_compare()` / `string_check()` — flexible matching modes
- `dedup_string_list()` — dedupe by method (exact, case-insensitive, regex)
- `camel_to_snake_case()` / `snake_to_camel_case()`
- `formatting.template_manager.TemplateManager` — Jinja2/Handlebars/Python templating

#### `datetime_utils` · timing
- `random_sleep()` — sleep in bounded range
- `TicToc` — lightweight benchmark timer
- `iter_dates()` — date-range iteration
- `solve_date_time_format_by_granularity()` — infer format from hourly/daily/…

#### `config_utils` · YAML → objects
- `load_config()` — OmegaConf + Hydra-style instantiate
- `merge_configs()` — merge OmegaConf trees
- `instantiate()` — config dict → Python object
- `register()` / `register_class()` / `register_alias()` — alias registry
- `resolve_target()` — alias → full import path

#### `console_utils` · adaptive colored output
- `hprint()` / `hprint_message()` — auto-picks Rich, Colorama, or Textual
- `print_table()` — Rich tables
- `eprint()` / `wprint()` — error / warning printers
- `prompt_confirm()` — interactive y/N (Textual backend)
- `get_current_backend()` — query active backend

#### `cli_utils` · shell command building
- `execute_cmd()` — run shell with Jinja2 substitution
- `listdir()` / `list_files()` / `list_subdirs()` — directory queries
- `substitute_placeholders()` — resolve `{{…}}` in command strings
- `scrub_shell_metachars()` / `render_argv()` — safe argv construction

### Domain objects & orchestration

#### `common_objects`
- `Serializable` — dict/pickle serialization with field metadata
- `VariableManager` / `FileBasedVariableManager` — variable resolution with cycle detection
- **`Workflow`** — DAG runner with checkpoint/resume + dynamic step expansion
- **`WorkGraph`** — composable subgraph engine for modular workflow composition
- `Stategraph` — state machine with transition validation

#### `common_utils`
- `array_helper`, `iter_helper`, `map_helper`, `typing_helper`, `attr_helper`
- `async_utils.call_maybe_async()` — uniform sync/async invocation

#### `algorithms`
- `dag.build_nodes_from_paths()` — DAG from path sequences with subpath merging
- `graph.traversal` — BFS/DFS with cycle detection + topo sort
- `tree.Tree` / `BinaryTree` / `Trie`
- `array.binary_search` (variants) / `array.sorting` (custom comparators)

### Concurrency & data

#### `mp_utils`
- `parallel_process()` — fork-based pool/batch
- `queued_executor` / `async_queued_executor` — bounded-queue executors
- `data_partition` — workload partitioning strategies
- `mp_target` — target wrappers for multiprocessing

#### `nlp_utils`
- `string_sanitization` — diacritic removal, whitespace normalization
- `string_patterns` — email/URL/phone regexes
- `readability` — Flesch-Kincaid, syllable counting
- `part_of_speech.pos_based_entity_extraction` — NLTK / Flair
- `metrics.edit_distance` — Levenshtein + variants
- `numbers` — numeric string parsing

#### `stat_utils`
- `agg_values_()` — multi-method aggregation (mean, sum, concat, custom)
- `aggregate_by_key()` — group-by with merge strategies
- `pairwise_metrics` — Euclidean / cosine / Hamming

#### `pd_utils`
- `selection`, `transformation`, `labeling`, `time_series` — pandas helpers

### Services & external

#### `service_utils` · backend-rich integration layer
- **`keyvalue_service`** — Memory / File / SQLite / Redis stores
- **`retrieval_service`** — Chroma / Elasticsearch / LanceDB / SQLite-FTS5
- **`graph_service`** — Neo4j / NetworkX / memory / file-backed
- **`queue_service`** — Redis / thread / email / storage-backed
- `session_management` — session tracking with manifest + monitoring
- `email_utils` — Gmail + SMTP clients

#### `retrieval_utils`
- IR index/query primitives (BM25, hybrid scoring)

#### `external`
- Vendored libs: `rank_bm25`, `colorama`, …

---

## Examples

`examples/python_utils/` (directory name preserved for legacy reasons; contents
import from `python_utils`):

- **`common_objects/workflow/`** · 6 numbered scenarios + `README.md`
  - basic expansion → expansion with local loop → splice-mode pure planner →
    deterministic resumability → LLM-undeterministic resumability → nested expansion
- **`common_objects/workgraph/`** · 6 numbered scenarios + `README.md`
  - leaf-to-subgraph → BTA diamond → insert-mode preserves downstream →
    resumability mid-subgraph → undeterministic LLM breakdown → nested subgraph

Each scenario file is runnable: `python examples/python_utils/common_objects/workflow/01_basic_expansion.py`.

---

## Design notes

- **No required dependencies.** Each sub-package is opt-in; heavy deps
  (`pandas`, `omegaconf`, `chromadb`, `elasticsearch`, `neo4j`, `flair`, `nltk`,
  …) are imported lazily inside the modules that need them.
- **Workflow / WorkGraph are deterministic by default.** Non-deterministic
  (LLM-driven) planners are explicitly opt-in via `seed + reconstruct_from_seed`
  for resumability.
- **Source of truth** for this package is `CoreProjects/PythonUtils`; the
  rovoteam-mirrored copy here rewrites `python_utils → python_utils` in
  every import. See the workspace [root README](../README.md) for the sync
  convention.

## Development

```bash
# from workspace root
uv run pytest PythonUtils/                  # run all tests
uv run pytest PythonUtils/test/python_utils/common_objects/workflow/   # focused
```

The test tree mirrors the source tree 1:1 (the test directory is named
`test/python_utils/` for legacy compatibility; contents use `python_utils`
imports throughout).

## Further reading

- [`examples/python_utils/common_objects/workflow/README.md`](examples/python_utils/common_objects/workflow/README.md) — workflow expansion patterns
- [`examples/python_utils/common_objects/workgraph/README.md`](examples/python_utils/common_objects/workgraph/README.md) — work-graph composition patterns
- [`../README.md`](../README.md) — rovoteam workspace overview & integration roadmap
