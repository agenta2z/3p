---
name: risk-governance
description: >
  Manage AI risk registers in Jira, perform severity-based triage with NIST AI RMF
  alignment, drive time-sensitive Slack escalation notifications, and generate
  Confluence governance dashboards. Covers SOP3 (AI Risk Escalation & Governance
  Review) workflows.
labels:
  - risk-management
  - governance
  - nist-ai-rmf
  - escalation
  - jira
metadata:
  tools: [twg, slack_find_channel, slack_send_message, slack_search_messages]
---

# Risk Governance Skill

## 1. Skill Overview

- **Name**: `risk-governance`
- **Description**: Domain guidance for creating and managing AI risk registers in Jira,
  scoring risks using Likelihood × Impact matrices, mapping to NIST AI RMF functions,
  triggering severity-based Slack escalations with time-bound SLAs, and generating
  Confluence governance reports.
- **Leveraged Tools**:
  - `twg` — Create/update/query Jira Risk issues, manage Confluence risk register pages,
    traverse org-tree for escalation chains.
  - `slack_find_channel` — Discover governance/escalation channels by naming pattern.
  - `slack_send_message` — Send severity-based escalation alerts and digest notifications.
  - `slack_search_messages` — Check for prior escalations to avoid duplicate alerts.

## 2. Workflow Mappings

### 2.1 Workflow: Create / Update Risk Record

**Trigger**: User says "log a risk", "new AI risk for initiative X", "update risk RISK-123".

**Step-by-step**:

1. **Collect risk details** (ask if not provided):
   - Summary (short title)
   - Description (cause, consequence, context)
   - Risk Category: `Team | Communications | Technical | Business | Compliance | AI-Ethics`
   - AI Risk Domain: `Accountability | Transparency | Explainability | Privacy | Fairness | Security`
   - Likelihood (1–5): Rare → Almost Certain
   - Impact (1–5): Insignificant → Catastrophic
   - Mitigation strategy
   - Risk owner (person/team)
   - Affected initiative (Jira epic or Atlas project key)
   - Target mitigation date and next review date

2. **Compute derived fields**:
   - `Risk Score = Likelihood × Impact` (1–25)
   - `Severity Band`:
     - 1–4 → **Low**
     - 5–9 → **Medium**
     - 10–14 → **High**
     - 15–25 → **Critical**

3. **Map to NIST AI RMF function** (suggest based on description):
   - "Roles and governance unclear" → `GOVERN`
   - "Scope or impact not assessed" → `MAP`
   - "No metrics or evaluation" → `MEASURE`
   - "No mitigation or monitoring plan" → `MANAGE`
   - Present suggestion; require human confirmation.

4. **Create Jira Risk issue**:
   ```
   twg jira workitem create --space AIRISK --type Risk \
     --summary "RISK – <short description>" \
     --description "<structured description with context, NIST mapping, mitigation>"
   ```
   - Set custom fields: Likelihood, Impact, Risk Score, Severity Band, Risk Category, AI Risk Domain, NIST AI RMF Function, Owner, Next Review Date.
   - Link to affected initiative: `relates to <EPIC-KEY>`.

5. **If Severity is High or Critical** → trigger escalation workflow (§2.3).

**Status workflow**:
```
Identified → Assessed → Approved → Mitigated → Closed
```
- **Identified**: Logged, not yet scored. (Also covers OPEN/WATCH.)
- **Assessed**: Likelihood/Impact set, Risk Score computed, Severity determined.
- **Approved**: Governance/Risk Council acknowledged.
- **Mitigated**: Mitigations in progress or implemented; residual risk tracked.
- **Closed**: No longer relevant / fully transferred / accepted.

**Validators** (enforce before transitions):
- Before `Assessed`: Likelihood + Impact must be set.
- Before `Approved`: Risk Owner and Risk Category must be set.
- Before `Closed`: Human confirmation always required.

---

### 2.2 Workflow: Query Risk Register

**Trigger**: User says "show me open risks", "top AI risks for program X", "risks due for review".

**Step-by-step**:

1. **Parse query parameters**: initiative, severity band, status, NIST function, time frame.

2. **Build and execute query** via TWG:
   ```
   twg jira workitem get --id <RISK-KEY>
   ```
   Or search:
   ```
   twg work query --scope me --since 30d
   ```

3. **Aggregate and rank results**:
   - Sort by Risk Score descending.
   - Group by: Category, Owner, NIST Function (as requested).

4. **Return structured summary**:
   - Top N risks table: Key | Summary | Score | Rating | Owner | Status | Review Date | NIST Function.
   - Distribution: X Critical, Y High, Z Medium, W Low.
   - Overdue reviews count.

5. **Include caveat**: "This summary is based on Jira risk entries only and does not guarantee the absence of unknown risks."

---

### 2.3 Workflow: Severity-Based Slack Escalation (SOP3)

**Trigger**: Risk created/updated with Severity = High or Critical, OR scheduled daily scan.

**Severity routing configuration**:
```yaml
severity_routing:
  CRITICAL:
    notify_within_hours: 4
    primary_channel: "#ai-risk-critical"
    backup_channel: "#ai-risk-escalations"
    ack_sla: "30 minutes"
  HIGH:
    notify_within_hours: 24
    primary_channel: "#ai-risk-high"
    backup_channel: "#ai-risk-escalations"
    ack_sla: "4 hours"
```

**Step-by-step**:

1. **Determine if escalation is needed**:
   ```
   created_at = risk issue created timestamp
   severity = risk severity band
   config = severity_routing[severity]
   deadline = created_at + config.notify_within_hours
   if now <= deadline AND not already_notified:
       proceed with escalation
   ```

2. **Locate Slack channel**:
   ```
   slack_find_channel --channel_name ai-risk-critical
   ```
   Try primary → backup → fallback. If none found, add Jira comment:
   "AI could not find escalation channel; please escalate manually."

3. **Check for prior escalation** (avoid duplicates):
   ```
   slack_search_messages "RISK-123" --count 5
   ```

4. **Construct and send escalation message**:
   ```
   slack_send_message <channel_id> "🚨 AI Risk Escalation – CRITICAL 🚨

   *Risk ID:* RISK-123 – [Open in Jira](url)
   *Title:* <summary>
   *Severity:* Critical (Score: 20)
   *Created:* <timestamp> (<age> elapsed)
   *Owner:* <owner> (@slack_mention)
   *AI Domain:* <domain> (NIST: <function>)
   *Affected initiative:* <EPIC-KEY>

   *Why escalated now (SOP3):*
   - Critical risks must notify stakeholders within 4h
   - Status: Identified (open for <duration>)

   *Requested:*
   1. Acknowledge in-thread within 30 minutes
   2. Confirm investigation lead and next update time
   3. Add relevant context or runbooks"
   ```

5. **Log escalation in Jira**:
   - Add comment: "Escalation sent to #ai-risk-critical at <timestamp>."

6. **Re-escalation** (Critical only, human-confirmed):
   - After 60 min with no thread reply containing "ACK" or "Taking lead":
   - Draft secondary escalation to `#ai-risk-escalations` tagging leadership.
   - Present draft for human confirmation before sending.

**Autonomy levels**:
- ✅ Autonomous: Compute whether notification is due, locate channels, send first-line alerts, log in Jira.
- ❌ Human confirmation: Re-escalation to leadership, any message to exec channels, marking risk as Accepted/Closed.

---

### 2.4 Workflow: Generate Risk Governance Dashboard (Confluence)

**Trigger**: User says "create risk dashboard", "update risk summary page for program X".

**Step-by-step**:

1. **Query all risks** for the program/initiative via TWG.

2. **Draft Confluence page content**:
   ```markdown
   # <Program> – AI Risk Overview

   ## Executive Summary
   - Open risks: X (Y Critical, Z High)
   - New this period: N | Mitigated: M
   - Overdue reviews: K

   ## Top Risks (Score ≥ 10)
   | Key | Summary | Score | Rating | Owner | Status | Review Date | NIST |
   |-----|---------|-------|--------|-------|--------|-------------|------|

   ## Risks by NIST AI RMF Function
   ### GOVERN
   - <risks>
   ### MAP
   - <risks>
   ### MEASURE
   - <risks>
   ### MANAGE
   - <risks>

   ## Upcoming Reviews (Next 30 Days)
   | Key | Summary | Review Date | Owner |
   |-----|---------|-------------|-------|
   ```

3. **Create/update Confluence page**:
   ```
   twg confluence pages create --space <SPACE> --title "<Program> – Risk Overview" \
     --body-file risk_overview.md --body-format markdown
   ```

---

## 3. Domain Guidance

### Risk Scoring Matrix

| Likelihood \ Impact | 1 (Insignificant) | 2 (Minor) | 3 (Moderate) | 4 (Major) | 5 (Catastrophic) |
|--------------------:|:--:|:--:|:--:|:--:|:--:|
| **5 (Almost Certain)** | 5 Med | 10 High | 15 Crit | 20 Crit | 25 Crit |
| **4 (Likely)** | 4 Low | 8 Med | 12 High | 16 Crit | 20 Crit |
| **3 (Possible)** | 3 Low | 6 Med | 9 Med | 12 High | 15 Crit |
| **2 (Unlikely)** | 2 Low | 4 Low | 6 Med | 8 Med | 10 High |
| **1 (Rare)** | 1 Low | 2 Low | 3 Low | 4 Low | 5 Med |

### NIST AI RMF Function Mapping

| Function | When to Tag | Examples |
|----------|------------|---------|
| **GOVERN** | Governance, policy, roles, oversight gaps | "No incident response owner defined" |
| **MAP** | Context/impact scoping, stakeholder assessment | "Third-party model not assessed for bias" |
| **MEASURE** | Metrics, evaluation, testing gaps | "No fairness benchmark for production model" |
| **MANAGE** | Mitigation, monitoring, incident handling | "No rollback plan for model deployment" |

### AI Risk Domain Taxonomy

- **Accountability & Transparency** (NIST 3.4)
- **Explainability & Interpretability** (NIST 3.5)
- **Privacy** (NIST 3.6)
- **Security & Resilience** (NIST 3.3)
- **Fairness & Bias**
- **Safety & Harm**
- **Legal & Compliance**

### Status Terminology Normalization

| Project-Specific Status | Normalized |
|------------------------|-----------|
| OPEN, WATCH | Identified |
| STABLE, Mitigating | Mitigation in Progress |
| Remediated | Mitigated |
| Risk Accepted | Accepted |
| Closed | Closed |

---

## 4. Integration Metadata

### Tools Referenced
- `twg` commands: `jira workitem create`, `jira workitem get`, `jira workitem update`,
  `confluence pages create`, `org-tree`
- `slack_find_channel`: Locate `#ai-risk-critical`, `#ai-risk-high`, `#ai-risk-escalations`
- `slack_send_message`: Post escalation alerts with structured templates
- `slack_search_messages`: Check for prior escalations (dedup)

### Cross-Tool Patterns
- **Risk escalation**: `twg jira` (detect severity) → `slack_find_channel` → `slack_search_messages` (dedup) → `slack_send_message` → `twg jira` (log comment)
- **Risk dashboard**: `twg jira` (query risks) → aggregate → `twg confluence pages create`
- **Investigation task**: `twg jira workitem create` (linked task with due date from severity SLA)

### Autonomy Levels
| Operation | Level |
|-----------|-------|
| Read risk data, compute scores/bands | Fully autonomous |
| Send first-line Slack escalation | Fully autonomous |
| Draft Confluence risk pages | Fully autonomous |
| Create investigation Jira tasks | Autonomous (adjustable) |
| Set NIST AI RMF mapping | Suggest, human confirms |
| Transition to Approved/Accepted/Closed | Human confirmation |
| Re-escalate to leadership | Human confirmation |
| Modify severity downward | Human confirmation |

---

## 5. Guardrails and Escalation

### Safety Boundaries
- **Never mark a risk as "Accepted" or "Closed" autonomously** — always require human confirmation.
- **Never downgrade severity** without explicit human approval.
- **Never send leadership escalations** (to `#ai-risk-escalations` or exec channels) without human confirmation.
- **Never create/modify Jira automation rules** autonomously — generate instructions for admin.
- When summarizing risks, always include: "This is based on Jira risk entries only and does not guarantee absence of unknown risks."

### Escalation Triggers
- Risk Score ≥ 15 (Critical) → immediate Slack escalation within 4 hours.
- Risk Score 10–14 (High) → Slack notification within 24 hours.
- Risk overdue for review by >7 days → reminder to Risk Owner.
- No acknowledgment of Critical escalation within 60 min → propose secondary escalation (human-confirmed).

### Error Handling
- If `slack_find_channel` returns no channel → add Jira comment explaining manual escalation needed, STOP.
- If risk creation fails (missing fields) → prompt user for required fields before retrying.
- If NIST mapping is ambiguous → present top 2 suggestions, require human selection.
