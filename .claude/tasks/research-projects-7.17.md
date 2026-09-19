# Research — Sub-module 7.17: Workflow & Automation (Module 7 — Project Management, `projects`)

> **Read this first.** 7.17 is the **automation, governance, and event-orchestration layer** of the Project Management module.
> It does not invent new project records from scratch; instead, it observes, transitions, and orchestrates the rich domain spine
> built across 7.1–7.16 (`Project`, `ProjectTask`, `ProjectMilestone`, `ResourceAllocation`, `ProjectBudgetLine`, `ProjectRisk`,
> `DeliverableInspection`, `ScopeChangeRequest`, `ProjectClientInvoice`).
>
> Commercial leaders (Asana, Jira, monday.com, ClickUp, Smartsheet, Wrike, ServiceNow SPM, Make/Zapier) have unified on a
> **Trigger-Condition-Action (TCA)** architecture with specialized branches for **multi-tier approval gates**, **cadence-driven recurring task generation**,
> and **secure HMAC-signed iPaaS webhooks**.
>
> In NavERP, 7.17 introduces 4 cohesive tenant-scoped models (`ProjectWorkflowRule`, `ProjectApprovalGate`, `RecurringTaskSchedule`,
> `ProjectWebhookEndpoint`) with clean auto-number prefixes (`PWF-`, `PAR-`, `RTS-`, `PWH-`), backed by proven in-repo precedents from
> CRM 1.10 (`apps/crm/models/AutomationWorkflow/`).

---

## Repo state checked first

### LIVE_LINKS built so far in module 7 (`apps/core/navigation.py`)
- **Built (7.1–7.15):** `7.1` (Project Intake & Charter), `7.2` (WBS & Scheduling), `7.3` (Resource Management), `7.4` (Cost & Budget), `7.5` (Risk & Issues), `7.6` (Quality), `7.7` (Scope & Requirements), `7.8` (Task & Work), `7.9` (Collaboration), `7.10` (Documents), `7.11` (Time Tracking), `7.12` (Portfolio/Program), `7.13` (Agile/Scrum), `7.14` (Client Collaboration), `7.15` (Financial & Billing).
- **Staged (7.16):** `ReportingBusinessIntelligence` models (`ProjectDashboards.py`, `DashboardWidgets.py`, `ProjectReports.py`, `ReportRuns.py`).
- **Target (7.17):** Lowest unbuilt sub-module. This pass implements 7.17.

### Sibling models available to FK or trigger upon (verified by `grep -rn "^class " apps/projects/models`)
| Sub-module | Verified Entities | Trigger Events & Target Actions |
|---|---|---|
| **7.1** | `Project`, `ProjectRequest`, `ProjectStakeholder`, `ProjectKickoff` | Status transitions (`draft` → `active` → `on_hold` → `completed`), charter sign-off, budget ceiling checks |
| **7.2** | `ProjectTask`, `TaskDependency`, `ProjectMilestone`, `ScheduleBaseline` | Due date approaching, milestone reached/missed, task status (`todo` → `in_progress` → `review` → `completed`), critical path drift |
| **7.3** | `ResourceAllocation`, `ResourceTimeEntry`, `ResourceProfile` | Over-allocation warnings, timesheet submission/approval, capacity threshold breach |
| **7.4** | `CostControlAccount`, `ProjectBudgetLine`, `ProjectExpense`, `BudgetRevision` | Budget overrun alert (`ac > bac`), expense approval, EVM threshold breach (`cpi < 0.9` or `spi < 0.9`) |
| **7.5** | `ProjectRisk`, `ProjectIssue`, `RiskResponseAction`, `IssueEscalation` | High-severity issue logged (`critical`/`blocker`), risk score above threshold, escalation timeout |
| **7.6** | `QualityPlan`, `QualityReview`, `DeliverableInspection`, `QualityDefect` | Inspection failed, punch-list defect logged, deliverable acceptance gate |
| **7.7** | `Requirement`, `ScopeItem`, `ScopeChangeRequest`, `ScopeVerification` | CCB scope change approval, scope creep threshold, requirement sign-off |
| **7.8** | `TaskBlock`, `TaskChecklistItem` | Task blocked event, checklist 100% completion auto-advance |
| **7.9** | `Meeting`, `MeetingActionItem`, `ProjectNotification`, `ChannelMessage` | Meeting action item due, notification dispatch, @mention broadcast |
| **7.10** | `ProjectFolder`, `ProjectDocument`, `ProjectDocumentRevision` | Document approved/released, retention expiration reminder |
| **7.11** | `TimeActivityCode`, `OvertimeRule`, `ProjectOvertimeRecord` | Overtime limit breach, unsubmitted timesheets reminder |
| **7.12** | `Portfolio`, `Program`, `PortfolioInvestment`, `ProgramDependency` | Strategic score update, investment status review gate |
| **7.13** | `Sprint`, `ProjectEpic`, `ProjectRelease`, `SprintImpediment` | Sprint start/closure rituals, sprint impediment escalation |
| **7.14** | `ClientPortalAccess`, `ClientApprovalRequest`, `StatementOfWork` | Client feedback received, SOW amendment approval |
| **7.15** | `ProjectRateCard`, `ProjectBillingRun`, `ProjectRevenueSchedule`, `ProjectPaymentRecord` | Invoice dispatch trigger, overdue payment alert, revenue recognition threshold |
| **7.16** | `ProjectDashboard`, `DashboardWidget`, `ProjectReport`, `ReportRun` | Scheduled report delivery trigger, KPI threshold alert |

### Spine entities verified to exist (`apps/core/models/` & `apps/accounting/models/`)
- `core.Tenant`: Mandatory tenant isolation on every table (`tenant = ForeignKey("core.Tenant", on_delete=CASCADE)`).
- `core.Party` / `core.PartyRole`: Stakeholders, project managers, approvers, clients, vendors.
- `core.OrgUnit`: Departmental routing, PMO escalation units.
- `core.AuditLog`: Cross-cutting governance audit trail.
- `core.Activity`: Calendar events and activity feed logging.
- `core.Document`: Document attachment linkage.
- `accounting.GLAccount`, `accounting.Currency`: Financial bounds and threshold currencies.

### In-repo architectural precedents
- **CRM 1.10 (`apps/crm/models/AutomationWorkflow/`):**
  - `WorkflowRule` (`WFR-`): Declarative Trigger-Condition-Action (TCA) rule with JSON conditions and JSON actions.
  - `ApprovalRequest` (`APR-`): Status-gated approvals with threshold values, approver/requester FKs, and decision timestamps.
  - `Webhook` (`WH-`): Outbound endpoints with encrypted HMAC secrets (`apps.core.crypto.encrypt/decrypt`) and Fernet protection.
  - `WorkflowLog` & `WebhookDelivery`: Append-only execution history and delivery tracking.
- **Auto-numbering (`apps/projects/models/_base.py`):** `TenantNumbered` base class using `apps.core.utils.next_number`.
- **Prefixes taken in `projects`:** `PRJ`, `PRQ`, `PST`, `PKO`, `TSK`, `TDP`, `PMS`, `SBL`, `RAL`, `RSP`, `RTE`, `CCA`, `PBL`, `PEX`, `BVR`, `RSK`, `ISS`, `RRA`, `ESC`, `QPL`, `QRV`, `DIN`, `QDF`, `REQ`, `SCI`, `SCR`, `SVR`, `TBK`, `TCL`, `CHN`, `CHM`, `MTG`, `AGI`, `MAIT`, `NTF`, `DSH`, `PFD`, `DTM`, `PDM`, `PDR`, `KNW`, `TAC`, `OTR`, `POT`, `PRT`, `PGM`, `PIN`, `PDEP`, `EPC`, `SPT`, `IMP`, `REL`, `RET`, `CPA`, `CFB`, `SOW`, `SWA`, `VHD`, `PCI`, `RTC`, `PBR`, `PRS`, `PPR`, `PDB`, `REP`, `RUN`.
- **Safe free prefixes for 7.17:**
  - `PWF-` (`ProjectWorkflowRule`) — Available and clean.
  - `PAR-` (`ProjectApprovalGate`) — Available and clean.
  - `RTS-` (`RecurringTaskSchedule`) — Available and clean.
  - `PWH-` (`ProjectWebhookEndpoint`) — Available and clean.

---

## Leaders surveyed (with source links)

1. **Asana Rules & Workflow Builder** — No-code workflow orchestration combining "When..." (triggers), "Check if..." (conditions), and "Do this..." (actions), with multi-branch logic, approval task statuses, and date-relative triggers.
   - Sources: [Asana Workflow Builder](https://asana.com/product/workflow-builder), [Asana Rules Guide](https://help.asana.com/s/article/rules), [Asana Approvals](https://help.asana.com/s/article/approvals).
2. **Jira Automation (Atlassian)** — Industry-standard project rule engine with Smart Values (`{{issue.status}}`), multi-branching (subtasks, linked issues), scheduled cron triggers, and webhooks.
   - Sources: [Jira Automation Basics](https://www.atlassian.com/software/jira/features/automation), [Jira Smart Values](https://support.atlassian.com/cloud-automation/docs/smart-values-in-jira-automation/).
3. **monday.com Automations & Integrations** — Natural-language automation recipes ("When status changes to X, notify Y and create item in Z"), recurring automations, and outbound webhooks.
   - Sources: [monday.com Automations](https://monday.com/features/automations), [Automation Recipes Guide](https://support.monday.com/hc/en-us/articles/360001222740-How-to-create-an-automation).
4. **ClickUp Automations** — Event-driven trigger/condition/action builder with native recurring task creation, webhook call actions, and dynamic task templating.
   - Sources: [ClickUp Automations](https://clickup.com/features/automations), [ClickUp Recurring Tasks](https://help.clickup.com/hc/en-us/articles/6309895304727-Use-recurring-tasks).
5. **Smartsheet Automated Workflows** — Tabular process automation with visual branch builder, multi-step approval requests (Approved/Declined branches), automated deadline reminders, and recurring date triggers.
   - Sources: [Smartsheet Automated Workflows](https://help.smartsheet.com/learning-track/level-2-intermediate-users/automated-workflows), [Approval Requests](https://help.smartsheet.com/articles/2476191-approval-requests).
6. **Wrike Automation Engine** — "WHEN–IF–THEN" rule builder featuring dedicated approval triggers (Approval Started, Approver Decided, Approval Finished), recurring task rules, and folder-level webhooks.
   - Sources: [Wrike Automation Engine](https://www.wrike.com/features/automation/), [Wrike Approval Automations](https://help.wrike.com/hc/en-us/articles/360042455934-Approvals-in-Wrike).
7. **ServiceNow Flow Designer (Strategic Portfolio Management - SPM)** — Enterprise low-code workflow engine featuring stage-gate approvals, timeout escalation paths, subflows, and Integration Hub spokes.
   - Sources: [ServiceNow Flow Designer](https://docs.servicenow.com/bundle/washingtondc-build-workflows/page/administer/flow-designer/concept/flow-designer.html), [ServiceNow SPM Governance](https://www.servicenow.com/products/strategic-portfolio-management.html).
8. **Make (Integromat) & Zapier iPaaS Webhooks** — Webhook delivery standard: HMAC-SHA256 signatures, event payload schemas, retry policies, and catch-hook ingestion for project management tools.
   - Sources: [Zapier Webhooks Guide](https://zapier.com/features/webhooks), [Make Webhooks Documentation](https://www.make.com/en/help/tools/webhooks).

---

## Feature catalog (this sub-module only)

### 1. Visual Workflow Designer
- **Trigger-Condition-Action (TCA) Engine** — Declarative rule engine evaluating project events (task status change, milestone reached, budget threshold breached) against structured criteria and executing actions.
  - Seen in: Asana, Jira, monday.com, ClickUp, Smartsheet, Wrike.
  - Priority: `table-stakes`.
  - Spine: New model `ProjectWorkflowRule` [PWF-]. Buildable now.
- **Visual Flow / Recipe Canvas (No-Code Representation)** — Clear structured layout representing Trigger → Conditions (AND/OR) → Actions / Branching paths.
  - Seen in: Asana Workflow Builder, Smartsheet Visual Canvas, ServiceNow Flow Designer.
  - Priority: `table-stakes`.
  - Spine: Django template rendering interactive flowchart cards; JSON structure stored in `ProjectWorkflowRule`. Buildable now.
- **Multi-Branching & Conditional Logic** — Support for `IF / ELSE-IF / ELSE` execution paths (e.g., if priority is High route to PMO, else assign to Team Lead).
  - Seen in: Jira Automation, Asana Rules, Wrike.
  - Priority: `common`.
  - Spine: JSON-based branching rules inside `ProjectWorkflowRule.conditions` and `actions`. Buildable now.
- **Smart Placeholders & Context Interpolation** — Dynamic tokens for messages and payloads (e.g., `{{project.name}}`, `{{task.title}}`, `{{assignee.name}}`, `{{task.due_date}}`).
  - Seen in: Jira Smart Values, monday.com, ClickUp.
  - Priority: `common`.
  - Spine: Template rendering helper in `apps/projects/services/workflow_engine.py`. Buildable now.
- **Workflow Execution History & Diagnostics** — Audit log recording rule executions, match status, evaluated conditions, executed actions, and error messages.
  - Seen in: Jira Audit Log, Asana Rule Activity, Wrike Automation Log.
  - Priority: `table-stakes`.
  - Spine: Child model `WorkflowExecutionLog` on `ProjectWorkflowRule`. Buildable now.

### 2. Approval Automation
- **Multi-Tier Gate & Threshold Approvals** — Structured governance gates for phase transitions, deliverable acceptances, scope changes, and budget baseline overrides.
  - Seen in: ServiceNow SPM, Smartsheet, Wrike, Asana Approvals.
  - Priority: `table-stakes`.
  - Spine: New model `ProjectApprovalGate` [PAR-]. Buildable now.
- **Auto-Approval within Tolerances** — Automated bypass when change or expense is below predefined monetary or schedule thresholds (e.g., budget variance < $500 or schedule shift < 2 days).
  - Seen in: ServiceNow SPM, Jira Service Management.
  - Priority: `differentiator`.
  - Spine: `auto_approve_threshold` field on `ProjectApprovalGate`. Buildable now.
- **Timeout & Escalation Routing** — Automatic escalation or reminder dispatch if an approval remains pending past a designated SLA duration (e.g., escalate to PMO Director after 48 hours).
  - Seen in: ServiceNow Flow Designer, Smartsheet, Wrike.
  - Priority: `common`.
  - Spine: `timeout_hours`, `escalate_to`, and `escalated_at` fields on `ProjectApprovalGate`. Buildable now.
- **Delegation & Out-of-Office Routing** — Ability to designate temporary or role-based proxy approvers.
  - Seen in: ServiceNow SPM, Wrike.
  - Priority: `common`.
  - Spine: `delegate_approver` field (FK to `auth.User`) on `ProjectApprovalGate`. Buildable now.
- **Approval Decision Tracking & Status Sync** — Immutable recording of decision (`approved`, `rejected`, `delegated`), timestamp, feedback comments, and automated status transition of the underlying project record.
  - Seen in: Asana, Smartsheet, Wrike.
  - Priority: `table-stakes`.
  - Spine: `decision_status`, `decided_at`, `decision_notes` on `ProjectApprovalGate`. Buildable now.

### 3. Notification & Reminder Rules
- **Deadline & SLA Milestone Reminders** — Automated alerts triggered $N$ days/hours prior to or after a task or milestone due date.
  - Seen in: Asana, monday.com, Smartsheet, ClickUp.
  - Priority: `table-stakes`.
  - Spine: Handled by `ProjectWorkflowRule` with `trigger_event="date_reached"` or `"deadline_approaching"`. Buildable now.
- **Status Change & Stage Transition Alerts** — Real-time notification when high-visibility tasks or projects change status (e.g., task becomes `blocked` or project changes to `at_risk`).
  - Seen in: Asana, monday.com, Jira.
  - Priority: `table-stakes`.
  - Spine: Handled by `ProjectWorkflowRule` with `trigger_event="status_changed"`. Dispatches to `projects.ProjectNotification` and `core.Activity`. Buildable now.
- **Risk & Issue Threshold Alerts** — Automated escalation alerts when a project risk exposure exceeds tolerance or a critical issue is filed.
  - Seen in: Wrike, ServiceNow SPM.
  - Priority: `common`.
  - Spine: Handled by `ProjectWorkflowRule` targeting `ProjectRisk` / `ProjectIssue`. Buildable now.
- **Multi-Channel Dispatch Integration** — In-app notification creation with extensible hooks for email notifications.
  - Seen in: Slack/Teams integrations in Asana, Jira, monday.com.
  - Priority: `table-stakes`.
  - Spine: Reuses `projects.ProjectNotification` (7.9) and `core.Activity`. Buildable now.

### 4. Recurring Task Automation
- **Cadence & Schedule Generation** — Cron/interval pattern generator (Daily, Weekly, Bi-Weekly, Monthly, Sprint Cadence, First Monday of Month) for recurring project activities.
  - Seen in: ClickUp, monday.com, Wrike, Smartsheet.
  - Priority: `table-stakes`.
  - Spine: New model `RecurringTaskSchedule` [RTS-]. Buildable now.
- **Template-Driven Task & Checklist Instantiation** — Automatic creation of new `ProjectTask` rows complete with description, priority, estimated effort, checklist items, and tags from a prototype template.
  - Seen in: ClickUp, Asana, Wrike.
  - Priority: `table-stakes`.
  - Spine: `RecurringTaskSchedule` points to prototype fields or existing `ProjectTask` template, minting new `ProjectTask` (7.2/7.8) and `TaskChecklistItem` rows. Buildable now.
- **Auto-Assignment & Role Resolution** — Assigning newly minted recurring tasks to a fixed team member, project manager, or current sprint lead.
  - Seen in: ClickUp, monday.com.
  - Priority: `common`.
  - Spine: `assignee_strategy` and `default_assignee` fields on `RecurringTaskSchedule`. Buildable now.
- **Recurrence Controls (Pause, Skip, End-Date)** — Lifecycle management allowing recurring schedules to be paused during project hiatus, skipping holidays, or terminating on project closure.
  - Seen in: ClickUp, Wrike.
  - Priority: `common`.
  - Spine: `is_active`, `start_date`, `end_date`, `next_run_date`, `skip_holidays` on `RecurringTaskSchedule`. Buildable now.

### 5. Integration Automation (iPaaS)
- **Outbound Event-Driven Webhooks** — Webhook dispatcher emitting structured JSON payloads when project events occur (task completed, milestone achieved, gate approved).
  - Seen in: Zapier, Make, Jira, monday.com, Wrike.
  - Priority: `table-stakes`.
  - Spine: New model `ProjectWebhookEndpoint` [PWH-]. Buildable now.
- **HMAC-SHA256 Secret Signing & Cryptographic Security** — Outbound payloads signed using SHA256 HMAC digest in headers (`X-NavERP-Signature`), with secrets encrypted at rest via `apps.core.crypto.encrypt/decrypt`.
  - Seen in: Zapier, GitHub, Stripe, Shopify, CRM 1.10.
  - Priority: `table-stakes`.
  - Spine: Encrypted `secret` field on `ProjectWebhookEndpoint`. Reuses `apps.core.crypto`. Buildable now.
- **Zapier / Make Compatible Payload Formatting** — Clean standardized JSON payload containing event type, tenant ID, project info, entity state, actor, and ISO timestamps.
  - Seen in: Zapier Webhooks, Make Integromat connectors.
  - Priority: `common`.
  - Spine: Payload generator in `apps/projects/services/webhook_dispatcher.py`. Buildable now.
- **Webhook Delivery Logs & Diagnostic Auditing** — Append-only delivery records capturing payload, signature, HTTP response status, latency, and failure count.
  - Seen in: Jira Webhook logs, CRM 1.10 `WebhookDelivery`.
  - Priority: `table-stakes`.
  - Spine: Child model `ProjectWebhookDelivery` on `ProjectWebhookEndpoint`. Buildable now.

### Beyond the bullets
- **Automation Execution Quotas & Circuit Breakers** — Guarding against runaway loops (e.g., rule A triggers rule B which triggers rule A) with max execution depth (limit = 5) and hourly execution counters.
  - Seen in: Jira Automation loop detection, Zapier throttling.
  - Priority: `differentiator`.
  - Spine: Runtime loop detection in `apps/projects/services/workflow_engine.py`. Buildable now.
- **Rule Dry-Run & Simulation Mode** — Ability for project managers to test an automation rule against an existing task/project to preview what actions *would* execute without mutating data.
  - Seen in: Jira Automation Rule Sandbox, ServiceNow Flow Test.
  - Priority: `differentiator`.
  - Spine: Test action in view returning simulated JSON response. Buildable now.

---

## Recommended build scope (this pass — 4 models)

To cleanly satisfy all 5 feature bullets in NavERP.md with high architectural cohesion and zero bloat, we recommend **4 primary tenant-scoped models** (each with an assigned auto-number prefix):

### 1. `ProjectWorkflowRule` [PWF-]
- **Purpose:** Primary Trigger-Condition-Action (TCA) automation rule engine. Satisfies *Visual Workflow Designer* and *Notification & Reminder Rules*.
- **Fields:**
  - `number` [PWF-xxxxx]
  - `tenant` (FK `core.Tenant`)
  - `project` (FK `projects.Project`, null=True for organization-wide rules)
  - `name` (CharField 255)
  - `description` (TextField, blank=True)
  - `is_active` (BooleanField, default=True)
  - `trigger_entity` (CharField: `project`, `task`, `milestone`, `risk`, `budget`, `scope_change`, `inspection`)
  - `trigger_event` (CharField: `created`, `updated`, `status_changed`, `due_date_approaching`, `threshold_breached`, `blocked`)
  - `trigger_field` (CharField 100, blank=True)
  - `trigger_value` (CharField 255, blank=True)
  - `conditions` (JSONField, default=list: `[{field, operator, value, logical_op}]`)
  - `actions` (JSONField, default=list: `[{type: "update_field|notify|request_approval|fire_webhook|create_task", params: {...}}]`)
  - `execution_count` (PositiveIntegerField, default=0)
  - `last_fired_at` (DateTimeField, null=True, blank=True)
  - `owner` (FK `settings.AUTH_USER_MODEL`, null=True, blank=True)
- **Child Log:** `WorkflowExecutionLog` (`rule`, `tenant`, `record_label`, `status`, `fired_at`, `error_msg`, `duration_ms`).

### 2. `ProjectApprovalGate` [PAR-]
- **Purpose:** Formal project governance approval gates with threshold auto-approval, timeout escalation, and delegation. Satisfies *Approval Automation*.
- **Fields:**
  - `number` [PAR-xxxxx]
  - `tenant` (FK `core.Tenant`)
  - `project` (FK `projects.Project`)
  - `rule` (FK `ProjectWorkflowRule`, null=True, blank=True)
  - `gate_type` (CharField: `phase_gate`, `scope_change`, `budget_override`, `deliverable_acceptance`, `charter_signoff`)
  - `title` (CharField 255)
  - `description` (TextField, blank=True)
  - `target_model` (CharField 50)
  - `target_id` (PositiveIntegerField)
  - `target_label` (CharField 255, blank=True)
  - `requested_by` (FK `settings.AUTH_USER_MODEL`, related_name="+")
  - `approver` (FK `settings.AUTH_USER_MODEL`, related_name="+")
  - `delegate_approver` (FK `settings.AUTH_USER_MODEL`, null=True, blank=True, related_name="+")
  - `escalate_to` (FK `settings.AUTH_USER_MODEL`, null=True, blank=True, related_name="+")
  - `timeout_hours` (PositiveIntegerField, default=48)
  - `threshold_amount` (DecimalField 14, 2, null=True, blank=True)
  - `auto_approve_threshold` (DecimalField 14, 2, null=True, blank=True)
  - `status` (CharField: `pending`, `approved`, `rejected`, `escalated`, `auto_approved`, `cancelled`)
  - `decision_notes` (TextField, blank=True)
  - `decided_at` (DateTimeField, null=True, blank=True)

### 3. `RecurringTaskSchedule` [RTS-]
- **Purpose:** Cadence-driven schedule generator for repetitive tasks and sprint rituals. Satisfies *Recurring Task Automation*.
- **Fields:**
  - `number` [RTS-xxxxx]
  - `tenant` (FK `core.Tenant`)
  - `project` (FK `projects.Project`)
  - `title_template` (CharField 255 — supports `{{date}}`, `{{week}}`, `{{project}}`)
  - `description_template` (TextField, blank=True)
  - `is_active` (BooleanField, default=True)
  - `frequency` (CharField: `daily`, `weekly`, `biweekly`, `monthly`, `quarterly`, `sprint_cadence`)
  - `interval_count` (PositiveSmallIntegerField, default=1)
  - `days_of_week` (CharField 50, blank=True — e.g. "MON,WED,FRI")
  - `day_of_month` (PositiveSmallIntegerField, null=True, blank=True)
  - `priority` (CharField: `urgent`, `high`, `medium`, `low`, default="medium")
  - `effort_hours` (DecimalField 6, 2, default=0)
  - `assignee_strategy` (CharField: `fixed_user`, `project_manager`, `unassigned`)
  - `default_assignee` (FK `settings.AUTH_USER_MODEL`, null=True, blank=True, related_name="+")
  - `start_date` (DateField)
  - `end_date` (DateField, null=True, blank=True)
  - `next_run_date` (DateField)
  - `last_run_date` (DateField, null=True, blank=True)
  - `tasks_created_count` (PositiveIntegerField, default=0)

### 4. `ProjectWebhookEndpoint` [PWH-]
- **Purpose:** Outbound event webhook configuration and iPaaS dispatcher for Make/Zapier integration. Satisfies *Integration Automation (iPaaS)*.
- **Fields:**
  - `number` [PWH-xxxxx]
  - `tenant` (FK `core.Tenant`)
  - `project` (FK `projects.Project`, null=True, blank=True — null means tenant-wide)
  - `name` (CharField 255)
  - `target_url` (URLField 500)
  - `secret` (CharField 512, blank=True — encrypted HMAC signing key via `apps.core.crypto`)
  - `is_active` (BooleanField, default=True)
  - `event_types` (JSONField, default=list — e.g. `["task.created", "task.completed", "milestone.reached", "gate.approved"]`)
  - `custom_headers` (JSONField, default=dict, blank=True)
  - `last_status_code` (PositiveSmallIntegerField, null=True, blank=True)
  - `last_fired_at` (DateTimeField, null=True, blank=True)
  - `failure_count` (PositiveIntegerField, default=0)
- **Child Log:** `ProjectWebhookDelivery` (`webhook`, `tenant`, `event`, `payload`, `signature`, `status`, `status_code`, `response_body`, `attempted_at`).

---

## Belongs to sibling sub-modules (parked, not scoped here)

- **Deep Bidirectional System Synchronization (SAP, Oracle, Jira, GitHub, Salesforce sync)** → Parked for **7.18 Integration & API Hub**.
- **External Client Approvals & SOW Sign-offs** → Already built in **7.14 Client & External Collaboration** (`ClientApprovalRequest` `CFB-`).
- **Project Template & Methodology Master Data** → Parked for **7.19 Master Data & Configuration**.
- **Timesheet Submission & Review Loops** → Already built in **7.11 Time & Attendance Tracking** (`ResourceTimeEntry` approvals).
- **Change Control Board (CCB) Impact Evaluation** → Already built in **7.7 Scope & Requirements Management** (`ScopeChangeRequest` `SCR-`).
- **Meeting Recurrence & Minutes Action Items** → Already built in **7.9 Collaboration & Communication** (`Meeting`, `MeetingActionItem`).

---

## Deferred (later passes / integrations)

- **Drag-and-drop Visual Canvas UI (React Flow / jsPlumb)**: Full drag-and-drop graph editing deferred to later frontend enhancements; 7.17 ships a clean, no-code card/step wizard with a Mermaid/SVG visualization diagram.
- **Asynchronous Celery Task Runner**: NavERP standard relies on synchronous transaction hooks and on-demand execution. A full background worker daemon (Celery/Redis) is deferred to platform-level infrastructure.
- **Inbound Arbitrary Script Execution**: Sandboxed Python/JavaScript evaluation on webhook ingestion is deferred for security; initial webhook handling uses declarative field mapping.
