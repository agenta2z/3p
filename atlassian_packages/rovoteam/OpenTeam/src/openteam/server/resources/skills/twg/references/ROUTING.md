# Routing

Use this guide to pick the right surface first.

## Default order

1. **Federated** for cross-product requests: `docs`, `videos`, `meetings`, `spaces`
2. **Native** for product-specific detail or mutations: `jira`, `confluence`, `bb`, `goals`, `projects`, `teams`
3. **Projection** for broad activity, hierarchy, or perimeter: `work query`, `org-tree`, `context jira workitem`
4. **Cypher** only if the typed surfaces do not cover the request

## Query then get

When both exist, search first and fetch one item second.

```bash
scripts/twg teams query --query Platform
scripts/twg teams get "Platform Engineering"

scripts/twg docs query --since 7d
scripts/twg docs get <id-or-ari>
```

## Typical pivots

```bash
# Cross-product docs -> native Confluence details
scripts/twg docs query --since 14d
scripts/twg confluence pages get 12345 --body-format adf

# Issue perimeter -> native Jira details
scripts/twg context jira workitem PROJ-123 --depth 2
scripts/twg jira workitem get --id PROJ-123
```
