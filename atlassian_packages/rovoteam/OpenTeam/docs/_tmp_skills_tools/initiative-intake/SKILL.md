---
name: initiative-intake
description: >
  Manage the AI Initiative Intake pipeline — log new AI initiative proposals in Jira,
  apply weighted prioritization scoring (RICE-like), drive triage workflows, promote
  approved initiatives to program charters in Confluence, and document decisions using
  RAID/Decision patterns. Covers SOP1 (AI Initiative Intake → Prioritization →
  Execution) workflows.
labels:
  - intake
  - prioritization
  - program-charter
  - decision-documentation
  - sop1
metadata:
  tools: [twg, slack_find_channel, slack_send_message]
---

# Initiative Intake Skill

## 1. Skill Overview

- **Name**: `initiative-intake`
- **Description**: End-to-end guidance for logging AI initiative proposals, triaging
  and scoring them with a weighted framework, promoting approved initiatives to
  programs with Confluence charters, and documenting decisions across Confluence, Jira,
  and Slack. Powers SOP1 workflows.
- **Leveraged Tools**:
  - `twg` — Create/update Jira intake issues and program Epics, create Confluence
    charter pages, search for duplicate initiatives, manage issue transitions.
  - `slack_find_channel` — Locate intake/program channels for notifications.
  - `slack_send_message` — Notify stakeholders of new intakes, scoring results, approvals.

## 2. Workflow Mappings

### 2.1 Workflow: Log New AI Initiative Intake

**Trigger**: User says "new AI initiative", "log an intake for X", "we have an idea for Y".

**Step-by-step**:

1. **Parse and classify user input** into structured fields:

   **Who / Origin:**
   - Requester (person)
   - Originating Team / BU
   - Source Channel (Slack, email, exec sponsor, JSM)

   **What / Problem:**
   - Summary (short title)
   - Problem Statement (detailed)
   - Target Users / Segment
   - Product / Area
   - AI Modality (GenAI, ML model, rules + AI assist, etc.)

   **Value / Impact:**
   - Primary Business Goal (increase revenue, reduce cost, improve experience)
   - Expected Outcome Metric (e.g., "Reduce AHT by 15%")
   - Strategic Theme / OKR alignment

   **Effort / Dependencies:**
   - Estimated Complexity (Low/Medium/High)
   - Dependencies (text or issue links)
   - Requires PII / Sensitive Data? (Yes/No/Unknown)

   **AI Risk Pre-Screen (SOP3 hooks):**
   - AI Risk Category (None / Low / Medium / High)
   - Risk Drivers (checkboxes: PII, Safety, Legal/Compliance, Reputation, Bias/Fairness)

2. **Ask for missing required fields**:
   - Problem Statement, Target Users, Product Area, and Business Goal are required.
   - If Risk Drivers include PII/health/finance, ask explicit follow-up questions.

3. **Deduplication check**:
   ```
   twg work query --scope me --since 90d
   ```
   Search by summary + project + label for similar existing intake issues.
   If close match found → ask: "Should I update existing AIINTAKE-42 instead?"

4. **Create Jira intake issue**:
   ```
   twg jira workitem create --space AIINTAKE --type Task \
     --summary "[AI Intake] <short title>" \
     --description "<structured description with all fields>"
   ```
   Add labels: `ai-intake`, `source-<channel>`, `risk-<level>`.

5. **Set initial status** → `Needs Triage`.

6. **Notify via Slack** (optional):
   ```
   slack_find_channel --channel_name ai-intake-triage
   slack_send_message <channel_id> "📋 New AI Initiative Intake logged:
   • <KEY> – <summary>
   • Requester: <name> (<team>)
   • Risk pre-screen: <level>
   • Business goal: <goal>
   Link: <url>"
   ```

**Autonomy**: Autonomous for parsing and creating issues with status `Needs Triage`. Human confirmation for posting to Slack.

---

### 2.2 Workflow: Triage and Prioritization Scoring

**Trigger**: User says "triage this intake", "score AIINTAKE-42", "prioritize the intake backlog".

**Step-by-step**:

1. **Ensure required triage fields** are populated:
   - Problem statement, target users, product area, business goal, complexity, risk category.
   - If any missing → prompt user.

2. **Transition status**: `Needs Triage → In Triage → Ready for Scoring`.

3. **Collect or propose scoring inputs** (1-5 scale each):

   | Field | Description | How AI Estimates |
   |-------|------------|-----------------|
   | Impact Score | Business value if successful | From outcome metric magnitude |
   | Confidence Score | Evidence strength | From specificity of proposal |
   | Effort Score | Implementation complexity | From stated complexity + dependencies |
   | Risk Score | Risk level for this initiative | From risk pre-screen fields |

4. **Compute derived scores**:
   ```
   Value Score = (Impact × Confidence) / Effort
   Risk Penalty = Risk Score × 0.5  (configurable weight)
   Adjusted Priority Score = Value Score - Risk Penalty
   ```

5. **Present scores for human confirmation**:
   ```
   Proposed scores for AIINTAKE-42 "LLM Customer Triage":
   • Impact: 4  |  Confidence: 3  |  Effort: 2  |  Risk: 2
   • Value Score: 6.0  |  Risk Penalty: 1.0
   • Adjusted Priority: 5.0
   Confirm or adjust?
   ```

6. **On confirmation, update Jira fields and transition** → `Scored`:
   ```
   twg jira workitem update --id AIINTAKE-42 --transition "Scored"
   ```

**Autonomy**: AI proposes scores (flagged as "AI-suggested"). Human must confirm before setting.

---

### 2.3 Workflow: Promote Intake to Program (Go/No-Go)

**Trigger**: User says "approve this initiative", "promote AIINTAKE-42 to a program".

**Pre-check**: Ensure intake is `Scored` and has:
- Non-empty problem statement
- At least one objective & metric
- Risk category selected

**Step-by-step**:

1. **Ask for confirmation**: "Do you want me to:
   1) Create an AI Program epic
   2) Generate a program charter page
   3) Suggest initial execution epics?"

2. **Create AI Program Epic**:
   ```
   twg jira workitem create --space AIPROG --type Epic \
     --summary "[AI Program] <initiative name>" \
     --description "<copy structured fields from intake>"
   ```
   Add labels: `ai-program`, `promoted-from-<INTAKE-KEY>`.

3. **Create Confluence Program Charter page**:
   ```markdown
   # [AI Program] <Name> — Program Charter

   **Sponsor:** {exec_sponsor}
   **Program Manager:** {pm_name}
   **Created:** {date}
   **Source Intake:** <INTAKE-KEY>

   ## Purpose & Problem
   {from intake problem statement}

   ## Objectives & Success Metrics
   {from intake outcome metrics and business goal}

   ## Scope
   ### In Scope
   - {items}
   ### Out of Scope
   - {items}

   ## Workstreams / Epics
   {initial workstream suggestions}

   ## Stakeholders & Roles
   | Role | Person/Team |
   |------|------------|
   | Sponsor | {sponsor} |
   | Program Manager | {pm} |

   ## Risks & Dependencies
   {from intake risk pre-screen and dependencies}

   ## Governance & Cadence
   - Weekly status updates
   - Monthly business review
   - Quarterly portfolio review

   ## Links
   - Jira Program Epic: <EPIC-KEY>
   - Original Intake: <INTAKE-KEY>
   - Slack: #prog-<name>
   ```

   ```
   twg confluence pages create --space <SPACE> --title "[AI Program] <Name> – Charter" \
     --body-file charter.md --body-format markdown
   ```

4. **Link artifacts**:
   - Set `Program Charter Link` on both Program epic and Intake issue.
   - Add issue link: Intake → Program (`is implemented by`).

5. **Transition intake status** → `Approved for Program`:
   ```
   twg jira workitem update --id <INTAKE-KEY> --transition "Approved for Program"
   ```

6. **Notify stakeholders via Slack**:
   ```
   slack_send_message <channel_id> "✅ AI Initiative approved and promoted to program:
   • Program Epic: <EPIC-KEY>
   • Charter: <confluence_url>
   • Original Intake: <INTAKE-KEY>"
   ```

**Autonomy**: Human confirmation required for all promotion steps. AI drafts everything.

---

### 2.4 Workflow: Decision Documentation (RAID Pattern)

**Trigger**: User says "record a decision", "log decision for program X", "decision: we chose option A".

**Step-by-step**:

1. **Identify the program's Confluence implementation/charter page**.

2. **Structure the decision record**:
   ```markdown
   **Decision:** {statement}
   **Decision Maker:** @{person}
   **Date:** {YYYY-MM-DD}
   **Context:** {why this decision was made}
   **Related Issues:** {JIRA-KEY-1, JIRA-KEY-2}
   **NIST AI RMF Function:** {if applicable: GOVERN/MAP/MEASURE/MANAGE}
   ```

3. **For changed decisions** (replaces a prior one):
   - Prepend new decision with current date + "Replaces".
   - Keep old decision with strikethrough for audit trail.

4. **Optionally create a Jira Decision issue**:
   ```
   twg jira workitem create --space <PROJECT> --type Task \
     --summary "Decision: <short statement>" \
     --description "<structured decision record>"
   ```
   Add label: `decision`.
   Link to parent initiative/epic.

5. **Update Confluence page** with the decision entry.

---

### 2.5 Workflow: Benefit Realization Tracking (Post-Launch)

**Trigger**: User says "track benefits for launch X", "post-launch review", "are we realizing value".

**Step-by-step**:

1. **Identify the launch** (Jira epic or Atlas project).

2. **Create Benefit Tracker Jira issue**:
   ```
   twg jira workitem create --space <PROJECT> --type Task \
     --summary "Benefit Realization – <feature/launch name>" \
     --description "Objective: <benefit>\nMetric: <name>\nBaseline: <value>\nTarget: <value>"
   ```
   Link to launch epic.

3. **At review time, pull metrics** and update:
   ```
   twg jira workitem update --id <BENEFIT-KEY>
   ```

4. **Create Post-Launch Review Confluence page**:
   ```markdown
   # <Program> – Post-Launch Review – {date}

   ## Overview
   - Feature / Launch: {name}
   - GA Date: {date}

   ## Expected vs Actual Metrics
   | Metric | Baseline | Target | Current | Delta | Status |
   |--------|---------|--------|---------|-------|--------|

   ## Key Decisions Made
   {link to decision log}

   ## Follow-up Actions
   - [ ] {action} — Owner: @{person} — Due: {date}
   ```

5. **Post Slack summary** linking to the review page.

---

## 3. Domain Guidance

### Intake Status Workflow
```
New → Needs Triage → In Triage → Ready for Scoring → Scored
  → Approved for Program
  → Not This Cycle
  → Rejected
```

### Prioritization Formula
```
Value Score = (Impact × Confidence) / Effort
Risk Penalty = Risk Score × weight  (default weight = 0.5)
Adjusted Priority = Value Score - Risk Penalty
```

### AI Risk Pre-Screen Categories
| Category | Triggers |
|----------|---------|
| None | No PII, no safety concerns, internal tool only |
| Low | Minor data handling, limited user exposure |
| Medium | PII involved, moderate user-facing impact |
| High | Safety-critical, regulatory, reputation risk, bias concerns |

If intake risk is **High** → recommend creating a formal Risk issue (link to `risk-governance` skill).

### Program Charter Sections (Canonical)
1. Purpose & Problem
2. Objectives & Success Metrics
3. Scope (In/Out)
4. Workstreams / Epics
5. Stakeholders & Roles
6. Risks & Dependencies
7. Governance & Cadence
8. Links (Jira, Confluence, Slack)

### Decision Record Fields
- Decision statement
- Decision maker + date
- Context / rationale
- Related Jira issues
- NIST AI RMF function (if AI-related)
- Replaces (previous decision reference, if applicable)

---

## 4. Integration Metadata

### Tools Referenced
- `twg` commands: `jira workitem create/get/update`, `work query`,
  `confluence pages create`, `confluence search query`
- `slack_find_channel`: intake triage and program channels
- `slack_send_message`: notifications for new intakes, approvals, decisions

### Cross-Tool Patterns
- **Intake → Score → Promote**: `twg jira create` (intake) → `twg jira update` (score + transition) → `twg jira create` (program epic) + `twg confluence pages create` (charter) → `slack_send_message` (announce)
- **Decision documentation**: Record in Confluence (charter page) + `twg jira create` (decision issue) → `slack_send_message` (notify stakeholders)
- **Benefit tracking**: `twg jira create` (benefit tracker) → periodic `twg jira update` → `twg confluence pages create` (post-launch review)

### Autonomy Levels
| Operation | Level |
|-----------|-------|
| Parse user input into structured fields | Fully autonomous |
| Create intake issues (status: Needs Triage) | Fully autonomous |
| Propose prioritization scores | Autonomous (flagged as suggestion) |
| Set confirmed scores, transition to Scored | Human confirms scores first |
| Transition to Approved for Program | Human confirmation required |
| Create program Epic and charter page | Human confirmation required |
| Create decision records | Autonomous (human reviews content) |
| Post Slack notifications | Human confirmation |

---

## 5. Guardrails and Escalation

### Safety Boundaries
- **Never autonomously transition to "Approved for Program"** — always require explicit approval from designated approvers.
- **Never set risk category to "None"** if PII/health/finance indicators are detected — flag as at least "Medium" and ask.
- **Never create bulk program structures** from ambiguous natural-language input without confirmation.
- **Deduplication**: Always check for similar existing intakes before creating new ones.

### Escalation Triggers
- Intake with AI Risk Category = "High" → recommend formal risk registration (cross-reference `risk-governance` skill).
- Intake stalled in "Needs Triage" for >5 business days → remind assignee and escalate to PM lead.
- Scored intake with Adjusted Priority > 4.0 and no action for >10 days → surface in next stand-up summary.

### Error Handling
- If Jira project/issue type doesn't exist → suggest project setup steps, don't fail silently.
- If Confluence charter creation fails → output markdown for manual creation.
- If scoring inputs are ambiguous → default to medium (3) and clearly mark as "needs human refinement".
