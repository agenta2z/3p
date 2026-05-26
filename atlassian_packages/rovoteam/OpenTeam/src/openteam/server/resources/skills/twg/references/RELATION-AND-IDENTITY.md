# Relation and Identity

Use these surfaces to resolve people first, then pivot into work, meetings, or collaboration views.

## Main surfaces

- `user` — current user or one known account ID
- `user-search` / `resolve` — turn a name or email into an account ID
- `collaborators` — relationship-focused view across work items

## Common shapes

```bash
scripts/twg user
scripts/twg user 557058:abc...

scripts/twg user-search --name "Jane Doe"
scripts/twg user-search --email "jdoe@atlassian.com"
scripts/twg resolve --name "Jane Doe"

scripts/twg collaborators --scope me
```

## High-signal flags

- `--name`
- `--email`
- `--limit`
- `-s, --site`
- `--scope`

## Typical pivots

```bash
# resolve person -> inspect recent work
scripts/twg user-search --name "Jane Doe"
scripts/twg work query --scope user --account-id <id> --since 30d

# resolve person -> inspect meetings
scripts/twg user-search --email "jdoe@atlassian.com"
scripts/twg meetings --account-id <id> --since 2w
```
