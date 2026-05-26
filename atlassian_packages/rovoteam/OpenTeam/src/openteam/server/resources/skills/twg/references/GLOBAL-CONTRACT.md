# Global Contract

These patterns recur across TWG surfaces.
All `scripts/twg` examples in this reference set inherit the path-resolution rule from `../SKILL.md`: resolve `scripts/twg` relative to the skill directory, not the caller's current working directory.

## Discovery

```bash
scripts/twg --help
scripts/twg <surface> --help
scripts/twg <surface> <resource> --help
```

## Common patterns

- `query` to search/list
- `get` to fetch one item
- `create`, `update`, `delete` for writes when supported
- `--scope`, `--account-id`, `--since`, `--limit`, `--first`, `--after`, `-s/--site` are common selectors

## Good defaults

- prefer machine-readable output for follow-up analysis
- keep stderr visible
- paginate before asking for huge payloads
- narrow with scope and time filters
- confirm target and intent before writes

## Large outputs

For very large goal exports, prefer SQLite:

```bash
scripts/twg goals --scope org --account-id <id> \
  --include-parent-goal --include-contributing-projects \
  --sqlite-file /tmp/goals.db
```
