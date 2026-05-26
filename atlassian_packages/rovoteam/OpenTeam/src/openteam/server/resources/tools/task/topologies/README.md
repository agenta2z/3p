# `/task` Topology Presets

Each `*.yaml` here is a fully-instantiable agent topology. The first leading `# ...` line is the description shown in the UI autocomplete (parsed by `GET /api/task/topologies`).

| Preset | Topology | LLM calls | Cost (rough) | When to use |
|---|---|---|---|---|
| `single` | One ClaudeCodeCli, no wrapping | 1 | ~$0.50-2 | Quick one-shot — same as raw Claude |
| `pti-simple` | PTI (plan + implement, single Claude per phase) | 2 | ~$1-5 | Plan→implement workflow without consensus overhead |
| `pti` *(default)* | PTI + Dual consensus per phase | 4-8 | ~$5-30 | RankEvolve-style — best quality, multi-iteration consensus |
| `bta` | BreakdownThenAggregate, single Claude per slot | 1+N+1 | ~$2-10 | Decompose into N parallel subtasks |
| `bta-dual` | BTA with Dual consensus on every slot | 2+(2N)+2 | ~$10-40 | High-quality decomposition (role_setup-style) |
| `dual` | Plain Dual consensus (proposer + reviewer) | 2-4 | ~$1-5 | Quality boost via consensus, no plan/implement split |
| `multi-flow` | N parallel dynamic LWI flows + aggregator | N+1 | ~$2-10 | Independent perspectives on same task |
| `multi-flow-dual` | MultiFlow propose + Dual review/fix loop (Round 7: self-review-avoidance + winner-as-fixer) | 2N+2-4 | ~$10-40 | Multi-CLI ensemble with iterative refinement |

Costs assume `model_name: opus[1m]` (the default in every preset). Override with `--model sonnet` or `--model haiku` for cheaper iteration. Override any other field via `--override <dotted.key>=<value>`.

## Conventions

- All presets default to `model_name: opus[1m]`, `permission_mode: bypassPermissions`, `idle_timeout_seconds: 300`. Override per-leaf with `--override <slot>.model_name=sonnet` or globally with `--model sonnet`.
- Workspace root is injected by the executor at runtime; YAMLs do not hard-code paths.
- For PTI variants: the `--analysis` and `--multi-iter` flags toggle `enable_analysis` / `enable_multiple_iterations` on the inferencer.
- For non-PTI variants: `--plan` / `--execute` / `--confirm` mode flags are user errors (rejected by the executor before instantiation).
