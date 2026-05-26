# Projection Surfaces

Use projections for broad views rather than product-native CRUD.

## Main surfaces

- `work query` — recent work across entities
- `org-tree` — management chain or reporting tree
- `context jira workitem` — issue perimeter and nearby artifacts

## Common shapes

```bash
scripts/twg work query --scope me --since 7d
scripts/twg work query --scope user --account-id <id> --since 30d
scripts/twg work query --first 50 --after "cursor=="

scripts/twg org-tree --name "Jane Doe" --up-only
scripts/twg org-tree --email "jdoe@example.com" --depth 5
scripts/twg org-tree --include-profile-title --include-location --include-dept

scripts/twg context jira workitem PROJ-123 --depth 2
scripts/twg jira workitem get --id PROJ-123
```

## High-signal flags

- `--scope`
- `--account-id`
- `--since`
- `--first` / `--after`
- `--name` / `--email`
- `--depth`
- `--up-only` / `--down-only`

## Good defaults

- use `work query` for “what has this person worked on?”
- use `org-tree` for hierarchy questions
- use `context jira workitem` before drilling into native Jira details
