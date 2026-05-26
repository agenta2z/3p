# Native Surfaces

Use native surfaces for product-specific detail, richer actions, and writes.

> For how these surfaces map to Atlassian product collections (TWC, ServCo, StratCo, etc.), see `references/PRODUCT-COLLECTIONS.md`.

## Main surfaces

- `jira`
- `confluence`
- `bitbucket` / `bb`
- `goals`
- `projects`
- `focus-areas`
- `teams`
- also available: `assets`, `csm`, `jsm`, `jira-align`, `talent`

## Common shapes

```bash
# Jira
scripts/twg jira workitem get --id PROJ-123
scripts/twg jira workitem create --space PROJ --type Task --summary "New task" --assignee me
scripts/twg jira workitem update --id PROJ-123 --summary "Updated title" --assignee me
scripts/twg jira workitem transition --id PROJ-123 --transition-id 21
scripts/twg jira sprint start --board-id <board-id> --id <id> --name "Sprint 42" --start-date 2026-03-01 --end-date 2026-03-14
scripts/twg jira space status list --id-or-key PROJ               # list all statuses for a project, grouped by category (use for accurate JQL)
scripts/twg jira space status list --id-or-key PROJ --output json # machine-readable output

# Confluence
scripts/twg confluence pages get 12345 --body-format adf
scripts/twg confluence pages create --space-id ENG --title "Runbook" --body-file ./content.adf --body-format adf
scripts/twg confluence pages update 12345 --title "Runbook" --body-file ./content.adf --body-format adf -y
scripts/twg confluence search query --cql 'type=page AND title ~ "Runbook"'

# Bitbucket
scripts/twg bb repos
scripts/twg bb prs
scripts/twg bb pr 42
scripts/twg bb pr 42 --approve
scripts/twg bb pr-create --title "My change" --source feature/branch
scripts/twg bb pipeline 123 --logs

# Goals / projects / focus areas / teams
scripts/twg goals --scope me
scripts/twg goals --scope org --account-id <id> --include-parent-goal --include-contributing-projects
scripts/twg projects --scope me --role contributor
scripts/twg focus-areas --scope org --account-id <id> --include-linked-goals
scripts/twg teams query --query Platform
scripts/twg teams get "Platform Engineering"
```

## High-signal flags

- `--scope`
- `--role`
- `--status`
- `--account-id`
- `--updated-since` / `--created-since`
- `--include-parent-goal`
- `--include-contributing-projects`
- `--include-linked-goals`

## Large goal exports

```bash
scripts/twg goals --scope org --account-id <id> \
  --include-parent-goal --include-contributing-projects \
  --sqlite-file /tmp/goals.db
```

## Typical pivots

```bash
# Cross-product doc -> native Confluence
scripts/twg docs query --since 14d
scripts/twg confluence pages get 12345 --body-format adf

# Issue context -> native Jira
scripts/twg context jira workitem PROJ-123 --depth 2
scripts/twg jira workitem get --id PROJ-123
```

## Gotchas

- Use `confluence search query --cql ...` for structured lookup, especially when you already know a page title or want exact field filters.
- Prefer title-oriented CQL for page lookup, for example:

```bash
scripts/twg confluence search query --cql 'type=page AND title = "Runbook"'
scripts/twg confluence search query --cql 'type=page AND title ~ "Runbook"'
```

- Do **not** treat Confluence CQL as semantic content search. CQL is best for structured metadata filters and title matching, not meaning-based retrieval across page bodies.
- Semantic or fuzzy page-content search is not implemented here yet, so avoid implying that CQL provides that behavior.
