# Federated Surfaces

Start here for cross-product requests.
If the result is not rich enough, pivot to the product-native surface.

## Use these first

- `docs` — cross-product documents
- `videos` — cross-product videos
- `meetings` — meetings and recordings
- `spaces` — Jira spaces/projects by keyword or key
- `recently-viewed` — recent views across products
- `pr` — one PR by ARI

## Common shapes

```bash
scripts/twg docs query --since 7d
scripts/twg docs get <id-or-ari>

scripts/twg videos query
scripts/twg videos get <id-or-ari>

scripts/twg meetings --account-id <id> --since 2w --with-recordings
scripts/twg meetings get <id-or-ari>

scripts/twg spaces query --keyword platform
scripts/twg spaces get GQLGW

scripts/twg recently-viewed --since 7d
scripts/twg pr "ari:cloud:graph::pull-request/..."
```

## High-signal flags

- `--since`
- `--account-id`
- `--first` / `--after`
- `--with-recordings`
- `--keyword`
- `-s, --site`

## Typical pivots

```bash
# federated doc -> native Confluence details
scripts/twg docs query --since 14d
scripts/twg confluence pages get 12345 --body-format adf

# PR by ARI -> repo-scoped PR workflow
scripts/twg pr "ari:cloud:graph::pull-request/..."
scripts/twg bb pr 42
```

## Notes

- `recently-viewed` has a 30-day TTL.
- Prefer query first, then get.
