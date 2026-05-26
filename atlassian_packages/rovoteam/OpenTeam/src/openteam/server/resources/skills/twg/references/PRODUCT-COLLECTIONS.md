# Atlassian Product Collections

How TWG CLI surfaces map to Atlassian product collections.

## Collections

### Teamwork (TWC)

Atlas/Townsquare — goals, projects, teams, org alignment.

| Surface | Description |
|---------|-------------|
| `goals` | Atlas goals — OKRs, key results, status tracking |
| `projects` | Atlas projects — cross-team initiatives, updates, status |
| `teams` | Atlas teams — membership, hierarchy, team discovery |

### Knowledge Management

Confluence — collaborative content, documentation, knowledge sharing.

| Surface | Description |
|---------|-------------|
| `confluence` | Pages, blogs, spaces, search (CQL) |

### Software Development

Jira Software + Bitbucket — issue tracking, code, CI/CD.

| Surface | Description |
|---------|-------------|
| `jira` | Workitems (issues), spaces (Jira projects), sprints, filters, boards |
| `bitbucket` / `bb` | Repos, PRs, branches, commits, pipelines, deployments |

### Service Collection (ServCo)

Service management, customer support, and operational tooling.

| Surface | Description |
|---------|-------------|
| `jsm` | Jira Service Management — queues, SLAs, request types |
| `csm` | Customer Service Management |
| `assets` | IT asset management (CMDB) |

### Strategy Collection (StratCo)

Strategic planning, talent, and portfolio alignment.

| Surface | Description |
|---------|-------------|
| `focus-areas` | Mercury focus areas — strategic priorities |
| `talent` | Talent/position management (RadarPosition) |
| `jira-align` | Portfolio-level planning and alignment |

## Common disambiguation

- **"Projects"** = Atlas projects (TWC), accessed via `twg projects`. These are cross-team initiative trackers with status updates, linked goals, and contributors.
- **"Spaces" in Jira** = Jira projects, accessed via `twg jira space`. These are issue containers with workflows, issue types, and boards.
- **"Spaces" in Confluence** = Confluence spaces, accessed via `twg confluence spaces`. These are content containers for pages and blogs.

Never confuse Atlas projects with Jira spaces — they serve different purposes in different collections.
