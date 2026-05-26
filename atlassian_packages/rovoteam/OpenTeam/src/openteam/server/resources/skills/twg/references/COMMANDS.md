# Reference Index

`COMMANDS.md` is the compact table of contents for this reference set.
Use it to decide which guide to open next; it is not meant to mirror raw CLI help.
All `scripts/twg` examples in this reference set inherit the path-resolution rule from `../SKILL.md`: resolve `scripts/twg` relative to the skill directory, not the caller's current working directory.

## Start here

- `ROUTING.md` — pick the right surface
- `GLOBAL-CONTRACT.md` — shared command patterns, filters, pagination, and write safety

## By surface family

- `FEDERATED-SURFACES.md` — `docs`, `videos`, `meetings`, `spaces`, `recently-viewed`, `pr`
- `PROJECTION-SURFACES.md` — `work query`, `org-tree`, `context jira workitem`
- `NATIVE-SURFACES.md` — `jira`, `confluence`, `bitbucket`/`bb`, `goals`, `projects`, `focus-areas`, `teams`, and related product surfaces
- `RELATION-AND-IDENTITY.md` — `user`, `user-search`, `resolve`, `collaborators`
- `CONTROL-PLANE.md` — `login`, `skills`, `integrations`, `echo`

## Quick routing

- Cross-product request -> `FEDERATED-SURFACES.md`
- Broad work/activity/hierarchy/context -> `PROJECTION-SURFACES.md`
- Product-specific detail or mutation -> `NATIVE-SURFACES.md`
- Need to resolve a person first -> `RELATION-AND-IDENTITY.md`
- Need to tell the user about setup/package/runtime commands -> `CONTROL-PLANE.md`
