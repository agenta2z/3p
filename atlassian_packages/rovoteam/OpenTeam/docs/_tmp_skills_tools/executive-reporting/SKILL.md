---
name: executive-reporting
description: >
  Generate weekly stand-up summaries, Monthly Business Reviews (MBR), Quarterly
  Portfolio Reviews (QBR), and executive portfolio health reports using TWG work
  queries, Atlas goals/projects, and Jira sprint data. Outputs to Slack and Confluence.
labels:
  - reporting
  - executive
  - standup
  - mbr
  - qbr
  - portfolio
metadata:
  tools: [twg, slack_find_channel, slack_send_message]
---

# Executive Reporting Skill

## 1. Skill Overview

- **Name**: `executive-reporting`
- **Description**: Automate periodic reporting for a Program Manager — weekly async
  stand-ups, monthly business reviews, quarterly portfolio reviews, and ad-hoc executive
  health reports. Pull data from TWG (goals, projects, Jira, work activity), synthesize
  into structured summaries, publish to Confluence and Slack.
- **Leveraged Tools**:
  - `twg` — Query goals (`goals`), projects (`projects`), Jira work items (`jira workitem`),
    cross-product activity (`work query`), org-tree for stakeholder context.
  - `slack_find_channel` — Locate team/program channels for posting summaries.
  - `slack_send_message` — Post stand-up digests, MBR/QBR summaries with Confluence links.

## 2. Workflow Mappings

### 2.1 Workflow: Weekly Async Stand-Up Summary

**Trigger**: User says "prepare stand-up", "weekly summary for my team", "post async stand-up".

**Phase 1: Gather Data**

1. Resolve team (user-specified or from TWG teams):
   ```
   twg org-tree --name "<team or person>" --down-only --depth 1
   ```

2. Per-person activity (last 7 days):
   ```
   twg work query --scope user --account-id <user-ari> --since 7d
   ```
   Capture: completed Jira items (statusCategory=Done), merged PRs, updated Confluence pages.

3. Sprint context (if applicable):
   ```
   twg jira workitem get --id <BOARD-EPIC>
   ```

**Phase 2: Synthesize**

Classify each work item into:
- **Shipped/Done**: Jira `statusCategory=Done` or `completedAt` in window; PRs merged.
- **In Progress**: Jira `statusCategory=In Progress`.
- **Blockers**: Status `Blocked`/`On Hold`, or comments containing "blocked", "waiting on".

Per person: generate ~3 "Last 7 days" bullets (outcome-focused), ~2 "Next focus" bullets, blockers.

Team level: total shipped count, sprint completion %, risk summary.

**Phase 3: Format & Post**

Slack template:
```
Weekly async stand-up – Week of {week_start}

🟢 Team Summary
• Shipped: {N} issues, {M} PRs merged, {K} docs updated
• Sprint: {X}/{Y} points completed ({pct}%)
• Risks: {count} blocked items

👤 @alice
Last 7d:
• Closed PROJ-123 "Fix login bug" (reduced auth failures ~30%)
• Merged PR #456 "Refactor auth middleware"
Next:
• Finish PROJ-140 "Add rate limiting" (ETA Thu)
Blockers:
• Waiting on security review for PROJ-140

👤 @bob
...
```

Post via:
```
slack_find_channel --channel_name team-<name>-standup
slack_send_message <channel_id> "<formatted summary>"
```

**Autonomy**: Autonomous for data gathering and drafting. Human confirmation before posting to Slack.

---

### 2.2 Workflow: Monthly Business Review (MBR) Prep

**Trigger**: User says "prepare MBR", "monthly review for AI Platform".

**Step-by-step**:

1. **Determine scope**: pillar/focus area, org, period (e.g., "March FY26").

2. **Query TWG goals for OKR progress**:
   ```
   twg goals --scope me
   ```
   For each objective: count KRs by status (on_track/at_risk/off_track), compute average progress.

3. **Query TWG projects for initiative status**:
   ```
   twg projects --scope me
   ```
   Compute: # active initiatives, % at risk, upcoming milestone dates.

4. **Pull delivery metrics from Jira**:
   ```
   twg work query --scope team --since 30d
   ```
   Compute: epic completion %, story throughput, spillover rate.

5. **Compose MBR Confluence page**:
   ```markdown
   # Monthly Business Review – {Pillar} – {Month} {FY}

   **Sponsor:** {name} | **DRI:** {name} | **Date:** {date}

   ## 1. Executive Summary
   [2-3 sentence overview: where portfolio stands, top themes]

   ## 2. Highlights & Lowlights
   ### Wins
   - {3-5 major wins}
   ### Challenges
   - {3-5 issues with causal explanation}

   ## 3. OKRs & Goal Progress
   | Objective | Owner | KRs On Track | KRs At Risk | Health |
   |-----------|-------|:---:|:---:|:---:|

   ## 4. Portfolio / Initiative Status
   | Initiative | Owner | Status | Target Date | Summary |
   |-----------|-------|--------|-------------|---------|

   ## 5. Success Metrics
   | Project | Metric | Target | Last Month | This Month | 🚦 |
   |---------|--------|--------|-----------|-----------|:--:|

   ## 6. Risks & Decisions
   - {risk items}
   - {decision items}

   ## 7. Actions
   - [ ] {action} — **Owner:** @{person} — Due {date}
   ```

6. **Create Confluence page**:
   ```
   twg confluence pages create --space <SPACE> --title "MBR – {Pillar} – {Month} {FY}" \
     --body-file mbr_draft.md --body-format markdown
   ```

7. **Post Slack summary** with link to Confluence page.

---

### 2.3 Workflow: Quarterly Portfolio Review (QBR) Prep

**Trigger**: User says "prepare QBR", "quarterly review for org X".

**Step-by-step**:

1. **Fetch org-scope goals**:
   ```
   twg goals --scope me
   ```
   Group into 3-5 portfolio pillars by focus area.

2. **Fetch initiative status** and cross-program dependencies from Jira.

3. **Compose QBR Confluence page** with canonical sections:
   - Executive Summary
   - Highlights & Lowlights
   - Business Performance & Key Metrics
   - Portfolio Priorities — Next Quarter
   - Transformation / Portfolio Health
   - Initiative Status & Dependencies
   - Risks & Blockers
   - Stakeholder Engagement & Decisions
   - Next Steps & Actions

4. **Apply quality rubric** (score 0-4 on each dimension):
   - Executive Sponsorship & Engagement
   - Outcomes Achieved & Value Narrative
   - Quality of Content & Delivery
   If any dimension < 2, recommend specific remediation.

5. **Create Confluence page and post Slack summary**.

---

### 2.4 Workflow: Ad-Hoc Executive Portfolio Health Report

**Trigger**: User says "executive summary", "portfolio status", "health report for focus area X".

**Step-by-step**:

1. Run TWG data collection (goals + projects + Jira + work activity).
2. Produce **Confluence page** (canonical record) and **Slack message** (condensed).

Slack format:
```
*Portfolio status – Week of {date}* (🟡 At Risk)

*Since last week*
• [Goal G1] moved from 🟢 → 🟡 due to [reason]
• [Program X] slipped release by 1 week
• Adoption for [Feature Z] reached 65% of target

*By area*
• Platform – 🟢 On Track (4/6 epics done)
• Growth – 🟡 At Risk (2 deps blocked)
• Support – 🔴 Off Track (backlog +30%)

Full details: <CONFLUENCE_URL>
```

---

## 3. Domain Guidance

### Cadence Mapping

| Cadence | Time Window | TWG `--since` | Focus |
|---------|-----------|--------------|-------|
| Weekly (WBR) | 7 days | `7d` | Current vs next week, blockers |
| Monthly (MBR) | 30 days | `30d` | Trends, target vs actual, diagnostics |
| Quarterly (QBR) | Quarter dates | Aligned | OKR outcomes, portfolio health, benefit realization |

### Report Quality Rubric (for QBR)

| Dimension | Score 0-1 | Score 2-3 | Score 4 |
|-----------|---------|---------|---------|
| Exec Engagement | No exec involvement | Exec attends | Exec leads, assigns follow-ups |
| Outcomes & Value | No outcomes/roadmap | Partial metrics | Full value narrative with ROI |
| Content Quality | Poor structure | Adequate data | Best-in-class, exec-ready |

### Stand-Up Classification Rules

| TWG Node Type / Field | Stand-Up Category |
|----------------------|-------------------|
| Jira `statusCategory=Done` | Shipped |
| PR `state=merged` | Shipped (under related Jira item) |
| Confluence page updated | "Docs updated" |
| Jira `statusCategory=In Progress` | In Progress |
| Jira status `Blocked`/`On Hold` | Blocker |

---

## 4. Integration Metadata

### Tools Referenced
- `twg` commands: `goals`, `projects`, `work query`, `jira workitem get/query`,
  `confluence pages create`, `org-tree`
- `slack_find_channel`: team/program channels
- `slack_send_message`: post summaries and digests

### Cross-Tool Patterns
- **Stand-up**: `twg work query` (per-user) → classify → format → `slack_send_message`
- **MBR/QBR**: `twg goals` + `twg projects` + `twg jira` → synthesize → `twg confluence pages create` → `slack_send_message` (link)
- **Health report**: Same as MBR but on-demand with both Confluence + Slack outputs

### Autonomy Levels
| Operation | Level |
|-----------|-------|
| Run TWG queries, compute metrics | Fully autonomous |
| Draft report content | Fully autonomous |
| Create Confluence draft pages | Autonomous |
| Post to team Slack channels | Human confirmation |
| Post to exec/leadership channels | Human confirmation |
| Mark MBR/QBR as "final" | Human confirmation |

---

## 5. Guardrails and Escalation

### Safety Boundaries
- **Never post to executive channels** without explicit human approval.
- **Never mark a report as "final"** — always tag as `Status: Draft – Awaiting Review`.
- **Never modify OKR values** (progress/targets) — only read and report.
- For inference-rich commentary ("we're behind plan"), use thresholds (e.g., <60% committed completed) but allow human override.

### Error Handling
- If TWG returns empty results for a team/goal → note "No data available" rather than omitting the section.
- If `slack_find_channel` fails → skip Slack posting, provide the formatted summary in-chat for manual posting.
- If Confluence page creation fails → output content as markdown for manual creation.
