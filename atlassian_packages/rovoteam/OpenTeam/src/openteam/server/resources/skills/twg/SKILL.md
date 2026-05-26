---
name: twg
description: >
  Query and manage Atlassian Teamwork Graph data — Jira, Confluence, Atlas, Loom, Bitbucket,
  Google Docs, Sharepoint and other work data. Use for cross-product activity, entity details,
  team/user insights, and create/update actions.
labels:
  - atlassian
  - teamwork-graph
  - productivity
metadata:
  requires:
    env: [TWG_USER, TWG_SITE, TWG_TOKEN, TWG_BBC_TOKEN]
  tools: [twg]
---

# TWG (Teamwork Graph)

## Overview

Use the `twg` tool to query and manage Atlassian Teamwork Graph data.
Start with federated surfaces for cross-product requests, native surfaces for product-specific detail or mutations,
and projection surfaces for activity, hierarchy, and issue context.
For very large goal exports, prefer `--sqlite-file`.

## Prerequisites

- **macOS** (arm64 or x64) or **Linux** (x64)
- TWG installed via the normal setup flow
- Auth via `TWG_USER` + `TWG_TOKEN`, or the normal `twg login` setup
- Bitbucket commands also need `TWG_BBC_TOKEN`
- Pass `-s <site>` when you need to override the configured site

## Required Reading — Load Before Executing

Before running any TWG command, read the following reference files (in this order):

1. **`references/ROUTING.md`** — how to pick the right surface. Read this first to avoid trial-and-error.
2. **`references/GLOBAL-CONTRACT.md`** — shared grammar, filters, pagination, output conventions, and write safety rules.
3. **`references/COMMANDS.md`** — compact index of all references; use it to decide which additional guide to open.

Then load the reference matching your task:

| Task type | Reference to load |
|-----------|-------------------|
| Cross-product queries (docs, videos, meetings, spaces) | `references/FEDERATED-SURFACES.md` |
| Activity, org hierarchy, or issue context | `references/PROJECTION-SURFACES.md` |
| Product-specific detail or mutations (Jira, Confluence, Bitbucket, goals, projects, teams) | `references/NATIVE-SURFACES.md` |
| Resolving a person (name/email → account ID) | `references/RELATION-AND-IDENTITY.md` |
| Which surface belongs to which Atlassian product collection | `references/PRODUCT-COLLECTIONS.md` |
| Generating ADF bodies for Confluence pages | `references/ADF-SCHEMA.md` |
| Exploring the Teamwork Graph schema (node types, relationships) | `references/METAGRAPH.md` |
| Setup, packaging, diagnostics, or integration help | `references/CONTROL-PLANE.md` |

**Do not rely solely on `--help` for surface selection.** The references contain routing logic, fallback strategies, and gotchas that CLI help does not expose. Use `--help` for flag-level details *after* you've chosen the right surface from the references.

## Surface Routing

- **Federated surfaces** (cross-product): `docs`, `videos`, `meetings`, `spaces`, `recently-viewed`
- **Native surfaces** (product-specific): `jira`, `confluence`, `bitbucket`, `goals`, `projects`, `teams`
- **Projection surfaces** (activity/hierarchy): `work`, `context`, `org-tree`
- **Identity**: `user-search`, `resolve`, `collaborators`

## Workflow

1. **Route** — read `references/ROUTING.md` to pick the correct surface. Use federated surfaces first (`docs`, `videos`, `meetings`, `spaces`), native surfaces for product-specific work (`jira`, `confluence`, `bitbucket`, `goals`, `projects`, `teams`), and projections for broad views (`work`, `context`, `org-tree`).
2. **Load** — read the matching reference file for your chosen surface to understand available commands, flags, and patterns.
3. **Discover** — run `twg <surface> <resource> --help` for flag-level detail if needed.
4. **Execute** — run the command. Keep stderr visible. Avoid shell redirection unless you truly need a file.
5. **Pivot** — if a surface returns empty or insufficient results, pivot to the next surface family (e.g., federated → native). Don't repeat the same empty surface.
6. **Summarize** — extract the key IDs, titles, statuses, URLs, and owners for the user.
7. **Writes** — state intended changes before write operations unless the user explicitly asked to execute them.

## Guidance

- Prefer the TWG CLI surfaces for Teamwork Graph-backed data and actions.
- Avoid using the integrations MCP tools for Teamwork Graph work, or for requests already covered by the TWG CLI surfaces.
- For Confluence pages, prefer valid ADF bodies. For simple content, plain text/markdown converted to ADF is acceptable.
- For rich layout-sensitive Confluence content such as tables with structured cells, panels, status lozenges, expanders, or similar constructs, try to generate ADF directly instead of relying on markdown conversion.
- Do not generate storage XML for Confluence page create/update.
- For ADF structure, node catalog, and examples, see `references/ADF-SCHEMA.md`. For deeper per-node details, follow the URL patterns documented there.

## Common Patterns

```bash
# Cross-product
twg docs query --since 7d
twg videos query
twg meetings --since 14d --with-recordings
twg spaces query --keyword platform
twg recently-viewed --since 7d

# Activity / hierarchy / context
twg work query --scope me --since 7d
twg work query --scope user --account-id <id> --since 30d
twg org-tree --name "Jane Doe" --up-only
twg context jira workitem PROJ-123 --depth 2

# Product-specific
twg jira workitem get --id PROJ-123
twg confluence pages get 12345 --body-format adf
twg confluence search query --cql 'type=page AND contributor=currentUser() ORDER BY lastmodified DESC'
twg goals --scope me
twg projects --scope me --role contributor
twg teams query --query Platform
twg bb pr 42

# Identity
twg user-search --name "Jane Doe"
twg resolve --name "Jane Doe"
```

For large goal exports:
```bash
twg goals --scope org --account-id <id> \
  --include-parent-goal --include-contributing-projects \
  --sqlite-file /tmp/goals_$(date +%s).db
```

## Advanced

Use `twg cypher ...` only when the typed surfaces do not cover the request. See `references/METAGRAPH.md` for schema exploration and Cypher syntax rules.

## References

- `references/COMMANDS.md` — compact index for the reference set
- `references/ROUTING.md` — how to pick the right surface
- `references/GLOBAL-CONTRACT.md` — grammar, filters, pagination, output, and mutation safety
- `references/FEDERATED-SURFACES.md` — cross-product surfaces
- `references/PROJECTION-SURFACES.md` — work, context, and org hierarchy
- `references/NATIVE-SURFACES.md` — product-specific surfaces
- `references/RELATION-AND-IDENTITY.md` — user lookup and collaborators
- `references/PRODUCT-COLLECTIONS.md` — which surfaces belong to which Atlassian product collections
- `references/METAGRAPH.md` — Teamwork Graph schema exploration via Cypher
- `references/ADF-SCHEMA.md` — compact ADF node/mark catalog, examples, pitfalls, and deep reference URLs
- `references/CONTROL-PLANE.md` — setup/package commands the agent should mention when relevant, not run by default
