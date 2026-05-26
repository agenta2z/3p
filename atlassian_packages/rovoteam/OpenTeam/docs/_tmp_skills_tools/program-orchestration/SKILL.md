---
name: program-orchestration
description: >
  Orchestrate AI program work structures in Jira using TWG CLI — create and manage
  epic/task/sub-task hierarchies for program workstreams, track cross-team dependencies
  via issue links, coordinate across teams using TWG org-tree and work queries, and
  build stakeholder maps with RACI matrices. Covers SOP2 (Program Execution &
  Cross-Team Coordination) workflows.
labels:
  - program-management
  - jira
  - dependencies
  - cross-team
  - stakeholder-mapping
metadata:
  tools: [twg, slack_send_message, slack_find_channel, create_role, role_setup]
---

# Program Orchestration Skill

## 1. Skill Overview

- **Name**: `program-orchestration`
- **Description**: Domain guidance for structuring program work in Jira, managing
  cross-team dependencies, coordinating across teams, and building stakeholder maps —
  all powered by TWG CLI and Slack tools.
- **Leveraged Tools**:
  - `twg` — Query and manage Jira work items (create/update/transition), Atlas goals/projects,
    teams and org-tree, cross-product work activity. Single `command` string parameter.
  - `slack_find_channel` — Resolve channel names to IDs for targeted coordination messages.
  - `slack_send_message` — Post dependency alerts, coordination requests, and status updates.

## 2. Workflow Mappings

### 2.1 Workflow: Create Program Hierarchy

**Trigger**: User says "create a program", "set up workstreams for X", "add deliverables under epic Y".

**Step-by-step**:

1. **Clarify intent and scope**
   - Ask: Program name/goal, single-team or multi-team, new program Epic or attach to existing.

2. **Search for existing program Epics**
   ```
   twg jira workitem get --id <KEY>
   ```
   Or search by label/summary:
   ```
   twg work query --scope me --since 90d
   ```
   If multiple matches → ask user to disambiguate.

3. **Create program Epic** (workstream level)
   ```
   twg jira workitem create --space <PROJECT> --type Epic --summary "[Program] – [Workstream]"
   ```
   Add labels: `program-<name>`, `workstream-<name>`.

4. **Create deliverable Tasks under Epic**
   ```
   twg jira workitem create --space <PROJECT> --type Task --parent <EPIC-KEY> --summary "<deliverable>"
   ```
   Structure description with standard sections:
   ```markdown
   ### Objective
   [plain language description]

   ### Acceptance Criteria
   - [criterion 1]
   - [criterion 2]

   ### Dependencies
   - [JIRA-KEY blocks this] (if known)

   ### Links
   - [Confluence design doc](...)
   ```

5. **Create action-item Sub-tasks** (optional)
   ```
   twg jira workitem create --space <PROJECT> --type Sub-task --parent <TASK-KEY> --summary "<action item>"
   ```

6. **Set labels and link artifacts**
   - Add program label to all created issues for cross-cutting queries.

**Validation rules** (MUST enforce):
- **Never create Sub-tasks directly under Epics** — always under Task/Story/Bug.
- **Never create Epic-under-Epic via parent field** — use `relates to` issue links instead.
- **Always use `parent` field** for hierarchy, never issue links for parent/child.

**Example scenario**:
> User: "Create the AI Reliability program with three workstreams: Data Governance, Evaluation & Monitoring, and Incident Response."
>
> AI creates:
> - Epic: `PROG-101` "AI Reliability: Data Governance Workstream"
> - Epic: `PROG-102` "AI Reliability: Evaluation & Monitoring Workstream"
> - Epic: `PROG-103` "AI Reliability: Incident Response Workstream"
> - Links all three via `relates to` issue links.
> - Adds label `program-ai-reliability` to each.

---

### 2.2 Workflow: Manage Cross-Team Dependencies

**Trigger**: User says "track dependency between X and Y", "what's blocking our initiative", "dependency status for program Z".

**Step-by-step**:

1. **Create a dependency link**
   - Identify upstream (blocker) and downstream (blocked) work items.
   - Use `blocks` / `is blocked by` link type — NOT `relates to`.
   ```
   twg jira workitem update --id <DOWNSTREAM-KEY> --link "is blocked by <UPSTREAM-KEY>"
   ```
   - Add a comment summarizing the dependency contract: what is needed, by when.

2. **Analyze dependencies for a program**
   - Query all issues under the program epic:
   ```
   twg context jira workitem <PROGRAM-EPIC-KEY> --depth 2
   ```
   - Enumerate all `blocks` / `is blocked by` links.
   - Flag at-risk dependencies where:
     - Upstream issue `statusCategory != Done` AND
     - Upstream due date > downstream start/due date, OR
     - Upstream status is `Blocked` or stalled (no updates in >7 days).

3. **Send dependency alerts via Slack**
   - Find the appropriate channel:
   ```
   slack_find_channel --channel_name prog-<initiative>-dependencies
   ```
   - Post structured alert:
   ```
   slack_send_message <channel_id> "🔗 Dependency Alert for <PROGRAM>:
   • <DOWNSTREAM-KEY> is blocked by <UPSTREAM-KEY> (owned by <Team>)
   • Needed by: <date>
   • Current status: <status>
   • Action: @<owner> please confirm feasibility and timeline."
   ```

4. **Create dedicated Dependency issue** (for critical cross-team dependencies)
   ```
   twg jira workitem create --space <PROJECT> --type Task \
     --summary "Dependency: <what> from <owning team> for <dependent work>" \
     --description "Needed-by: <date>\nOwning team: <team>\nRequesting team: <team>"
   ```
   Link via `blocks` / `is blocked by` to both upstream and downstream.

**Autonomy levels**:
- ✅ Autonomous: Reading issues, building dependency graphs, computing risk flags, drafting Slack messages.
- ❌ Human confirmation: Creating new `blocks` links, posting cross-team Slack messages, creating dependency issues.

---

### 2.3 Workflow: Cross-Team Coordination & Activity Monitoring

**Trigger**: User says "who's working on this initiative", "any teams stalled", "cross-team activity report".

**Step-by-step**:

1. **Discover involved teams**
   ```
   twg org-tree --name "<person or team>" --down-only --depth 2
   ```
   And from work relationships:
   ```
   twg work query --scope team --since 14d
   ```

2. **Monitor per-team activity**
   - For each expected team, query recent work:
   ```
   twg work query --scope user --account-id <user-ari> --since 7d
   ```
   - Collect metrics: open vs done issues, blocked items, last update timestamp.

3. **Detect coordination gaps**
   - Teams with **no activity** in past N days on active dependencies → "coordination gap".
   - Teams with **many blocked issues** where blockers belong to *other* teams → "escalation candidate".

4. **Produce coordination summary**
   - Per-team: activity level (High/Medium/Low), cross-team blockers count, stale items.
   - Program-level: top 3 cross-team risk hot-spots.

5. **Send targeted Slack coordination messages**
   ```
   slack_find_channel --channel_name <team-channel>
   slack_send_message <channel_id> "<structured coordination message>"
   ```

---

### 2.4 Workflow: Build Stakeholder Map & RACI

**Trigger**: User says "who are the stakeholders for X", "build a RACI for this program", "stakeholder mapping".

**Step-by-step**:

1. **Identify anchor** (Jira epic or Atlas project/goal).

2. **Discover teams and people via TWG**
   ```
   twg org-tree --name "<sponsor>" --down-only --depth 3
   twg work query --scope team --since 30d
   ```
   - Extract: owning teams, contributing teams, dependent teams.
   - For each team: get members, leads, parent org.

3. **Classify into RACI roles** (heuristics, overridable):
   - **Responsible (R)**: Teams owning primary delivery epics. Assignees of most program work items.
   - **Accountable (A)**: Program owner (Atlas project owner, primary PM/EM). Steering committee.
   - **Consulted (C)**: Dependent teams linked via dependencies. Governance teams (Security, Legal) when relevant risk categories exist.
   - **Informed (I)**: Adjacent teams with low contact but impacted outcomes. Leadership outside direct chain.

4. **Generate RACI table**:
   ```markdown
   | Task / Deliverable | Program Manager | EM (Team A) | TL (Team B) | Security | Exec Sponsor |
   |--------------------|:---:|:---:|:---:|:---:|:---:|
   | Maintain dependency log | R | C | C | I | I |
   | Risk register ownership | R/A | C | C | C | I |
   | Weekly status reporting | R | C | C | I | A |
   ```

5. **Propose Slack channel strategy** per RACI segment:
   - `#prog-<name>-core` → R + A stakeholders (detailed updates).
   - `#prog-<name>-updates` → C + I stakeholders (periodic digests).

**Autonomy levels**:
- ✅ Autonomous: TWG queries, graph building, drafting RACI tables.
- ❌ Human confirmation: Finalizing R/A/C/I assignments, Slack channel selection, publishing to Confluence.

---

## 3. Domain Guidance

### Hierarchy Rules (Canonical Contract)

| User Intent | Issue Type | Parent Rule |
|------------|-----------|-------------|
| "program", "workstream", "objective", "pillar" | Epic | No parent (or `relates to` other Epics) |
| "deliverable", "milestone", "feature", "work package" | Task/Story | `parent` = Epic |
| "action item", "step", "follow-up", "subtask" | Sub-task | `parent` = Task/Story (NEVER Epic) |

### Dependency vs Hierarchy — ALWAYS separate:
- **Hierarchy**: `parent` field (parent-key).
- **Dependencies**: Issue links (`blocks` / `is blocked by`).
- **Soft relationships**: Issue links (`relates to`).

### Synonym Tables

| Domain Term | Maps To |
|------------|---------|
| Program | Collection of Epics (linked via `relates to` + shared label) |
| Workstream / Track | Epic |
| Deliverable / Milestone | Task or Story under Epic |
| Action Item / Next Step | Sub-task under Task/Story |
| Dependency | `blocks`/`is blocked by` issue link |

### Naming Conventions
- Epic summary: `[Program] – [Workstream Name]`
- Labels: `program-<name>`, `workstream-<name>`
- Dependency issue: `Dependency: <what> from <team> for <work>`

---

## 4. Integration Metadata

### Tools Referenced
- `twg` commands: `jira workitem create`, `jira workitem get`, `jira workitem update`,
  `work query`, `context jira workitem`, `org-tree`, `teams`
- `slack_find_channel`: Resolve program/team channels
- `slack_send_message`: Post dependency alerts, coordination messages

### Cross-Tool Patterns
- **Dependency alert**: `twg context` (discover) → compute risk flags → `slack_find_channel` → `slack_send_message`
- **Stakeholder map**: `twg org-tree` + `twg work query` (discover teams) → build RACI → persist to Confluence via `twg confluence pages create`
- **Hierarchy creation**: `twg jira workitem create` (Epic) → `twg jira workitem create` (Task with parent) → `twg jira workitem create` (Sub-task with parent)

### Autonomy Levels
| Operation | Level |
|-----------|-------|
| Read Jira/TWG data, build graphs | Fully autonomous |
| Draft Slack messages, RACI tables | Fully autonomous |
| Create Tasks/Sub-tasks under confirmed parent | Autonomous |
| Create new Epics (when potential match exists) | Human confirmation |
| Create `blocks` links across teams | Human confirmation |
| Post to cross-team Slack channels | Human confirmation |
| Assign work to people on other teams | Human confirmation |

---

## 5. Guardrails and Escalation

### Safety Boundaries
- **Never create Epic-under-Epic** via parent field (invalid without Advanced Roadmaps custom hierarchy).
- **Never create Sub-tasks directly under Epics** — always under Task/Story/Bug.
- **Never emulate parent/child** with `blocks`/`relates to` issue links — use the `parent` field.
- **Never assign cross-team work** without explicit user confirmation.
- **Deduplication check**: Before creating a new Epic, search by summary + project + label. If close match found, ask: "Should I reuse PROG-123 instead of creating a new Epic?"

### Escalation Triggers
- Dependency stalled >7 days with no updates on upstream blocker → escalation candidate.
- >3 cross-team dependencies at risk for a single program → recommend program-level sync meeting.
- Team with zero activity on active dependencies for >14 days → flag coordination gap.

### Error Handling
- If `twg jira workitem create` fails with permission error → suggest user check project permissions.
- If `slack_find_channel` returns no match → log warning, suggest creating the channel or using an alternative.
- If parent issue type validation would fail (e.g., Sub-task under Epic) → explain the constraint and suggest creating a Task first.
