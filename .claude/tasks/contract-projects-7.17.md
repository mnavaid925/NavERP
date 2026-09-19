# Build Contract — Projects 7.17 Workflow & Automation (`projects`)

> Frozen 2026-09-19 against the live tree at commit `adb3f645`.
> This contract is the single source of truth for the entity-by-entity build.
> Every variable name, field name, URL name, context key, and badge class is pinned here.

---

## 0. Scope & Capability Coverage

Five NavERP.md 7.17 capability bullets mapped to 4 primary entities + 2 child logs + 4 computed automation boards:

| Bullet | What 7.17 Owns | Artifacts |
|---|---|---|
| **Visual Workflow Designer** | Trigger-Condition-Action (TCA) automation rule engine, branching logic, execution diagnostics | `ProjectWorkflowRule` [`PWF-`], `WorkflowExecutionLog` (`WorkflowRules.py`) |
| **Approval Automation** | Multi-tier governance approval gates, auto-approval thresholds, timeout SLA escalation, delegation | `ProjectApprovalGate` [`PAR-`] (`ApprovalGates.py`), `approval_inbox` |
| **Notification & Reminder Rules** | Event-driven triggers for deadlines, status changes, and risk/issue alerts | Evaluated by `ProjectWorkflowRule`, dispatched to `projects.ProjectNotification` |
| **Recurring Task Automation** | Cadence-driven schedule generator for repetitive tasks and sprint rituals, template instantiation | `RecurringTaskSchedule` [`RTS-`] (`RecurringTasks.py`), `recurrence_calendar` |
| **Integration Automation (iPaaS)** | Outbound event-driven webhooks, HMAC-SHA256 secret signing (`apps.core.crypto`), delivery logs | `ProjectWebhookEndpoint` [`PWH-`], `ProjectWebhookDelivery` (`Webhooks.py`), `webhook_diagnostics` |

### Non-Goals & Invariants
- **Spine integration**: 7.17 acts as the orchestrator observing and updating existing spine entities (`Project`, `ProjectTask`, `ProjectMilestone`, `ResourceAllocation`, `ProjectBudgetLine`, `ProjectRisk`, `DeliverableInspection`, `ScopeChangeRequest`). It does not duplicate these entities.
- **Audit action strings <= 10 characters**: `create`, `update`, `delete`, `toggle`, `execute`, `approve`, `reject`, `escalate`, `delegate`, `cancel`, `generate`, `skip`, `ping`, `rotate`.
- **Badges strictly colour-named (L33)**: `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate`.
- **Cryptographic secrets**: Outbound webhook secrets encrypted at rest via `apps.core.crypto.encrypt/decrypt`.
- **PowerShell safe commits**: Every file committed individually with `;` separator, never `&&`.

---

## 1. Verified Ground Truth

- `Project` [`PRJ-`] (`apps/projects/models/ProjectInitiation/Projects.py`), url name `projects:prj_detail`.
- `ProjectTask` [`TSK-`] (`apps/projects/models/ProjectPlanningScheduling/ProjectTasks.py`), url name `projects:tsk_detail`.
- `ProjectMilestone` [`MST-`] (`apps/projects/models/ProjectPlanningScheduling/ProjectMilestones.py`), url name `projects:mst_detail`.
- `ProjectNotification` [`NTF-`] (`apps/projects/models/CollaborationCommunication/ProjectNotifications.py`).
- `ProjectRisk` [`RSK-`] (`apps/projects/models/RiskManagement/ProjectRisks.py`).
- `ProjectIssue` [`ISS-`] (`apps/projects/models/RiskManagement/ProjectIssues.py`).
- `ScopeChangeRequest` [`SCR-`] (`apps/projects/models/ScopeRequirements/ScopeChangeRequests.py`).
- `DeliverableInspection` [`QCI-`] (`apps/projects/models/QualityManagement/DeliverableInspections.py`).
- `BudgetRevision` [`BVR-`] (`apps/projects/models/CostManagement/BudgetRevisions.py`).
- `TenantNumbered`, `TenantOwned` (`apps/projects/models/_base.py`).
- `TenantModelForm`, `_reject_foreign` (`apps/projects/forms/_common.py`).
- `crud_list`, `crud_detail`, `crud_create`, `crud_edit`, `crud_delete` (`apps/core/crud.py`).
- `write_audit_log` (`apps/core/utils.py`).
- `encrypt`, `decrypt` (`apps.core.crypto`).

---

## 2. Model & Form Specifications

### 2.1 Entity 1: `ProjectWorkflowRule` [`PWF-`] (`apps/projects/models/WorkflowAutomation/WorkflowRules.py`)
- Base: `TenantNumbered`, `NUMBER_PREFIX = "PWF"`
- Choices:
  - `TRIGGER_ENTITY_CHOICES = [("project", "Project"), ("task", "Task"), ("milestone", "Milestone"), ("risk", "Risk"), ("issue", "Issue"), ("budget", "Budget Line"), ("scope_change", "Scope Change Request"), ("inspection", "Deliverable Inspection")]`
  - `TRIGGER_EVENT_CHOICES = [("created", "Record Created"), ("updated", "Record Updated"), ("status_changed", "Status Changed"), ("due_date_approaching", "Due Date Approaching"), ("threshold_breached", "Threshold Breached"), ("blocked", "Task Blocked")]`
- Fields:
  - `name`: `CharField(max_length=255)`
  - `description`: `TextField(blank=True)`
  - `project`: `ForeignKey("projects.Project", on_delete=models.SET_NULL, null=True, blank=True, related_name="workflow_rules")`
  - `is_active`: `BooleanField(default=True)`
  - `trigger_entity`: `CharField(max_length=30, choices=TRIGGER_ENTITY_CHOICES, default="task")`
  - `trigger_event`: `CharField(max_length=30, choices=TRIGGER_EVENT_CHOICES, default="status_changed")`
  - `trigger_field`: `CharField(max_length=100, blank=True)`
  - `trigger_value`: `CharField(max_length=255, blank=True)`
  - `conditions`: `JSONField(default=list, blank=True)`
  - `actions`: `JSONField(default=list, blank=True)`
  - `execution_count`: `PositiveIntegerField(default=0, editable=False)`
  - `last_fired_at`: `DateTimeField(null=True, blank=True, editable=False)`
  - `owner`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="owned_project_workflows")`
- Child: `WorkflowExecutionLog` (Base: `TenantOwned`):
  - `STATUS_CHOICES = [("success", "Success"), ("failed", "Failed"), ("condition_failed", "Conditions Not Met"), ("simulated", "Simulated Run")]`
  - `rule`: `ForeignKey("projects.ProjectWorkflowRule", on_delete=models.CASCADE, related_name="execution_logs")`
  - `record_label`: `CharField(max_length=255, blank=True)`
  - `target_model`: `CharField(max_length=50, blank=True)`
  - `target_id`: `PositiveIntegerField(null=True, blank=True)`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default="success")`
  - `fired_at`: `DateTimeField(auto_now_add=True)`
  - `error_msg`: `TextField(blank=True)`
  - `duration_ms`: `PositiveIntegerField(default=0)`
  - `evaluated_conditions`: `JSONField(default=dict, blank=True)`
  - `executed_actions`: `JSONField(default=list, blank=True)`
- Forms (`forms/WorkflowAutomation/WorkflowRules.py`):
  - `ProjectWorkflowRuleForm(TenantModelForm)`:
    - `Meta.model = ProjectWorkflowRule`
    - `Meta.fields = ["name", "description", "project", "is_active", "trigger_entity", "trigger_event", "trigger_field", "trigger_value", "conditions", "actions", "owner"]`
  - `WorkflowRuleTestForm(forms.Form)`:
    - `target_id = forms.IntegerField(required=True, label="Test Record ID")`

### 2.2 Entity 2: `ProjectApprovalGate` [`PAR-`] (`apps/projects/models/WorkflowAutomation/ApprovalGates.py`)
- Base: `TenantNumbered`, `NUMBER_PREFIX = "PAR"`
- Choices:
  - `GATE_TYPE_CHOICES = [("phase_gate", "Phase Transition Gate"), ("scope_change", "Scope Change Approval"), ("budget_override", "Budget Baseline Override"), ("deliverable_acceptance", "Deliverable Acceptance"), ("charter_signoff", "Charter Sign-off")]`
  - `STATUS_CHOICES = [("pending", "Pending Review"), ("approved", "Approved"), ("rejected", "Rejected"), ("escalated", "Escalated"), ("auto_approved", "Auto-Approved"), ("cancelled", "Cancelled")]`
- Fields:
  - `project`: `ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="approval_gates")`
  - `rule`: `ForeignKey("projects.ProjectWorkflowRule", on_delete=models.SET_NULL, null=True, blank=True, related_name="spawned_gates")`
  - `gate_type`: `CharField(max_length=30, choices=GATE_TYPE_CHOICES, default="phase_gate")`
  - `title`: `CharField(max_length=255)`
  - `description`: `TextField(blank=True)`
  - `target_model`: `CharField(max_length=50)`
  - `target_id`: `PositiveIntegerField()`
  - `target_label`: `CharField(max_length=255, blank=True)`
  - `requested_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")`
  - `approver`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")`
  - `delegate_approver`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")`
  - `escalate_to`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")`
  - `timeout_hours`: `PositiveIntegerField(default=48)`
  - `threshold_amount`: `DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)`
  - `auto_approve_threshold`: `DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default="pending")`
  - `decision_notes`: `TextField(blank=True)`
  - `decided_at`: `DateTimeField(null=True, blank=True, editable=False)`
  - `escalated_at`: `DateTimeField(null=True, blank=True, editable=False)`
- Forms (`forms/WorkflowAutomation/ApprovalGates.py`):
  - `ProjectApprovalGateForm(TenantModelForm)`:
    - `Meta.model = ProjectApprovalGate`
    - `Meta.fields = ["project", "rule", "gate_type", "title", "description", "target_model", "target_id", "target_label", "requested_by", "approver", "delegate_approver", "escalate_to", "timeout_hours", "threshold_amount", "auto_approve_threshold"]`
  - `ApprovalDecisionForm(forms.Form)`:
    - `decision = forms.ChoiceField(choices=[("approve", "Approve"), ("reject", "Reject")])`
    - `decision_notes = forms.CharField(widget=forms.Textarea, required=False)`
  - `ApprovalDelegateForm(forms.Form)`:
    - `delegate_approver = forms.ModelChoiceField(queryset=None, required=True)`
    - `notes = forms.CharField(widget=forms.Textarea, required=False)`

### 2.3 Entity 3: `RecurringTaskSchedule` [`RTS-`] (`apps/projects/models/WorkflowAutomation/RecurringTasks.py`)
- Base: `TenantNumbered`, `NUMBER_PREFIX = "RTS"`
- Choices:
  - `FREQUENCY_CHOICES = [("daily", "Daily"), ("weekly", "Weekly"), ("biweekly", "Bi-Weekly"), ("monthly", "Monthly"), ("quarterly", "Quarterly"), ("sprint_cadence", "Sprint Cadence")]`
  - `PRIORITY_CHOICES = [("urgent", "Urgent"), ("high", "High"), ("medium", "Medium"), ("low", "Low")]`
  - `ASSIGNEE_STRATEGY_CHOICES = [("fixed_user", "Fixed User"), ("project_manager", "Project Manager"), ("unassigned", "Unassigned")]`
- Fields:
  - `project`: `ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="recurring_schedules")`
  - `title_template`: `CharField(max_length=255)`
  - `description_template`: `TextField(blank=True)`
  - `is_active`: `BooleanField(default=True)`
  - `frequency`: `CharField(max_length=20, choices=FREQUENCY_CHOICES, default="weekly")`
  - `interval_count`: `PositiveSmallIntegerField(default=1)`
  - `days_of_week`: `CharField(max_length=50, blank=True)`
  - `day_of_month`: `PositiveSmallIntegerField(null=True, blank=True)`
  - `priority`: `CharField(max_length=10, choices=PRIORITY_CHOICES, default="medium")`
  - `effort_hours`: `DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))`
  - `assignee_strategy`: `CharField(max_length=20, choices=ASSIGNEE_STRATEGY_CHOICES, default="fixed_user")`
  - `default_assignee`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")`
  - `start_date`: `DateField()`
  - `end_date`: `DateField(null=True, blank=True)`
  - `next_run_date`: `DateField()`
  - `last_run_date`: `DateField(null=True, blank=True, editable=False)`
  - `tasks_created_count`: `PositiveIntegerField(default=0, editable=False)`
- Forms (`forms/WorkflowAutomation/RecurringTasks.py`):
  - `RecurringTaskScheduleForm(TenantModelForm)`:
    - `Meta.model = RecurringTaskSchedule`
    - `Meta.fields = ["project", "title_template", "description_template", "is_active", "frequency", "interval_count", "days_of_week", "day_of_month", "priority", "effort_hours", "assignee_strategy", "default_assignee", "start_date", "end_date", "next_run_date"]`

### 2.4 Entity 4: `ProjectWebhookEndpoint` [`PWH-`] (`apps/projects/models/WorkflowAutomation/Webhooks.py`)
- Base: `TenantNumbered`, `NUMBER_PREFIX = "PWH"`
- Fields:
  - `project`: `ForeignKey("projects.Project", on_delete=models.CASCADE, null=True, blank=True, related_name="webhook_endpoints")`
  - `name`: `CharField(max_length=255)`
  - `target_url`: `URLField(max_length=500)`
  - `secret`: `CharField(max_length=512, blank=True)`
  - `is_active`: `BooleanField(default=True)`
  - `event_types`: `JSONField(default=list)`
  - `custom_headers`: `JSONField(default=dict, blank=True)`
  - `last_status_code`: `PositiveSmallIntegerField(null=True, blank=True, editable=False)`
  - `last_fired_at`: `DateTimeField(null=True, blank=True, editable=False)`
  - `failure_count`: `PositiveIntegerField(default=0, editable=False)`
- Child: `ProjectWebhookDelivery` (Base: `TenantOwned`):
  - `STATUS_CHOICES = [("success", "Success"), ("failed", "Failed"), ("simulated", "Simulated Ping")]`
  - `webhook`: `ForeignKey("projects.ProjectWebhookEndpoint", on_delete=models.CASCADE, related_name="deliveries")`
  - `event`: `CharField(max_length=100)`
  - `payload`: `JSONField(default=dict)`
  - `signature`: `CharField(max_length=255, blank=True)`
  - `status`: `CharField(max_length=15, choices=STATUS_CHOICES, default="success")`
  - `status_code`: `PositiveSmallIntegerField(null=True, blank=True)`
  - `response_body`: `TextField(blank=True)`
  - `attempted_at`: `DateTimeField(auto_now_add=True)`
  - `duration_ms`: `PositiveIntegerField(default=0)`
- Forms (`forms/WorkflowAutomation/Webhooks.py`):
  - `ProjectWebhookEndpointForm(TenantModelForm)`:
    - `Meta.model = ProjectWebhookEndpoint`
    - `Meta.fields = ["project", "name", "target_url", "is_active", "event_types", "custom_headers"]`
  - `WebhookTestPingForm(forms.Form)`:
    - `event_type = forms.CharField(max_length=100, initial="test.ping")`
    - `custom_payload = forms.CharField(widget=forms.Textarea, required=False)`

---

## 3. View Specifications & Context Variable Keys

### 3.1 `WorkflowRules.py`
- `pwf_list(request)`:
  - Template: `projects/workflowautomation/workflow/list.html`
  - Context keys:
    - `rules`: page items
    - `page_obj`: paginator page object
    - `trigger_entity_choices`: `ProjectWorkflowRule.TRIGGER_ENTITY_CHOICES`
    - `trigger_event_choices`: `ProjectWorkflowRule.TRIGGER_EVENT_CHOICES`
    - `projects`: `Project.objects.filter(tenant=request.tenant)`
    - `stats`: dict(`total`, `active`, `executions_today`)
    - `q`, `trigger_entity`, `is_active`: echoed filter params
- `pwf_detail(request, pk)`:
  - Template: `projects/workflowautomation/workflow/detail.html`
  - Context keys:
    - `rule`: `ProjectWorkflowRule` instance
    - `execution_logs`: `WorkflowExecutionLog.objects.filter(rule=rule)[:20]`
    - `test_form`: `WorkflowRuleTestForm()`
- `pwf_create(request)` / `pwf_edit(request, pk)`:
  - Template: `projects/workflowautomation/workflow/form.html`
  - Context keys:
    - `form`: `ProjectWorkflowRuleForm` instance
    - `rule`: instance (edit) or None (create)
    - `is_edit`: boolean
- `pwf_delete(request, pk)`: POST-only, redirects to `projects:pwf_list`.
- `pwf_toggle_active(request, pk)`: POST-only, toggles `is_active`, redirects to `projects:pwf_detail` or `list`.
- `pwf_test_run(request, pk)`: POST-only, executes test simulation, redirects with message.
- `pwf_execute_now(request, pk)`: POST-only, runs rule immediately against target, redirects with message.

### 3.2 `ApprovalGates.py`
- `par_list(request)`:
  - Template: `projects/workflowautomation/approvalgate/list.html`
  - Context keys:
    - `gates`: page items
    - `page_obj`: paginator page object
    - `gate_type_choices`: `ProjectApprovalGate.GATE_TYPE_CHOICES`
    - `status_choices`: `ProjectApprovalGate.STATUS_CHOICES`
    - `projects`: `Project.objects.filter(tenant=request.tenant)`
    - `stats`: dict(`total`, `pending`, `approved`, `escalated`)
    - `q`, `gate_type`, `status`, `project`: echoed filter params
- `par_detail(request, pk)`:
  - Template: `projects/workflowautomation/approvalgate/detail.html`
  - Context keys:
    - `gate`: `ProjectApprovalGate` instance
    - `decision_form`: `ApprovalDecisionForm()`
    - `delegate_form`: `ApprovalDelegateForm()`
- `par_create(request)` / `par_edit(request, pk)`:
  - Template: `projects/workflowautomation/approvalgate/form.html`
  - Context keys:
    - `form`: `ProjectApprovalGateForm` instance
    - `gate`: instance (edit) or None (create)
    - `is_edit`: boolean
- `par_delete(request, pk)`: POST-only, redirects to `projects:par_list`.
- `par_approve(request, pk)`: POST-only, marks approved, syncs target, redirects to `projects:par_detail`.
- `par_reject(request, pk)`: POST-only, marks rejected, redirects to `projects:par_detail`.
- `par_escalate(request, pk)`: POST-only, marks escalated, notifies `escalate_to`, redirects to `projects:par_detail`.
- `par_delegate(request, pk)`: POST-only, sets `delegate_approver`, redirects to `projects:par_detail`.
- `par_cancel(request, pk)`: POST-only, marks cancelled, redirects to `projects:par_detail`.

### 3.3 `RecurringTasks.py`
- `rts_list(request)`:
  - Template: `projects/workflowautomation/recurringtask/list.html`
  - Context keys:
    - `schedules`: page items
    - `page_obj`: paginator page object
    - `frequency_choices`: `RecurringTaskSchedule.FREQUENCY_CHOICES`
    - `priority_choices`: `RecurringTaskSchedule.PRIORITY_CHOICES`
    - `projects`: `Project.objects.filter(tenant=request.tenant)`
    - `stats`: dict(`total`, `active`, `due_this_week`)
    - `q`, `frequency`, `is_active`, `project`: echoed filter params
- `rts_detail(request, pk)`:
  - Template: `projects/workflowautomation/recurringtask/detail.html`
  - Context keys:
    - `schedule`: `RecurringTaskSchedule` instance
    - `recent_tasks`: `ProjectTask.objects.filter(project=schedule.project, description__icontains=schedule.number)[:10]`
- `rts_create(request)` / `rts_edit(request, pk)`:
  - Template: `projects/workflowautomation/recurringtask/form.html`
  - Context keys:
    - `form`: `RecurringTaskScheduleForm` instance
    - `schedule`: instance (edit) or None (create)
    - `is_edit`: boolean
- `rts_delete(request, pk)`: POST-only, redirects to `projects:rts_list`.
- `rts_toggle_active(request, pk)`: POST-only, toggles `is_active`, redirects to `projects:rts_detail`.
- `rts_generate_task(request, pk)`: POST-only, mints task immediately, redirects to `projects:rts_detail`.
- `rts_skip_next(request, pk)`: POST-only, advances `next_run_date`, redirects to `projects:rts_detail`.

### 3.4 `Webhooks.py`
- `pwh_list(request)`:
  - Template: `projects/workflowautomation/webhook/list.html`
  - Context keys:
    - `webhooks`: page items
    - `page_obj`: paginator page object
    - `projects`: `Project.objects.filter(tenant=request.tenant)`
    - `stats`: dict(`total`, `active`, `deliveries_today`, `failed_today`)
    - `q`, `is_active`, `project`: echoed filter params
- `pwh_detail(request, pk)`:
  - Template: `projects/workflowautomation/webhook/detail.html`
  - Context keys:
    - `webhook`: `ProjectWebhookEndpoint` instance
    - `deliveries`: `ProjectWebhookDelivery.objects.filter(webhook=webhook)[:15]`
    - `test_form`: `WebhookTestPingForm()`
- `pwh_create(request)` / `pwh_edit(request, pk)`:
  - Template: `projects/workflowautomation/webhook/form.html`
  - Context keys:
    - `form`: `ProjectWebhookEndpointForm` instance
    - `webhook`: instance (edit) or None (create)
    - `is_edit`: boolean
- `pwh_delete(request, pk)`: POST-only, redirects to `projects:pwh_list`.
- `pwh_toggle_active(request, pk)`: POST-only, toggles `is_active`, redirects to `projects:pwh_detail`.
- `pwh_test_ping(request, pk)`: POST-only, emits ping delivery, redirects to `projects:pwh_detail`.
- `pwh_rotate_secret(request, pk)`: POST-only, rotates HMAC secret, redirects to `projects:pwh_detail`.
- `pwh_delivery_list(request)`:
  - Template: `projects/workflowautomation/webhook/delivery_list.html`
  - Context keys:
    - `deliveries`: page items
    - `page_obj`: paginator page object
    - `status_choices`: `ProjectWebhookDelivery.STATUS_CHOICES`
    - `webhook_id`: echoed filter
- `pwh_delivery_detail(request, pk)`:
  - Template: `projects/workflowautomation/webhook/delivery_detail.html`
  - Context keys:
    - `delivery`: `ProjectWebhookDelivery` instance

### 3.5 `AutomationBoards.py`
- `automation_overview(request)`:
  - Template: `projects/workflowautomation/boards/overview.html`
  - Context keys:
    - `stats`: dict(`rules_count`, `active_rules`, `pending_gates`, `active_schedules`, `active_webhooks`, `deliveries_today`)
    - `pending_gates`: `ProjectApprovalGate.objects.filter(tenant=request.tenant, status="pending")[:5]`
    - `recent_logs`: `WorkflowExecutionLog.objects.filter(tenant=request.tenant)[:10]`
    - `upcoming_recurring`: `RecurringTaskSchedule.objects.filter(tenant=request.tenant, is_active=True).order_by("next_run_date")[:5]`
- `approval_inbox(request)`:
  - Template: `projects/workflowautomation/boards/approval_inbox.html`
  - Context keys:
    - `gates`: `ProjectApprovalGate.objects.filter(tenant=request.tenant, approver=request.user, status="pending")`
    - `delegated_gates`: `ProjectApprovalGate.objects.filter(tenant=request.tenant, delegate_approver=request.user, status="pending")`
    - `stats`: dict(`my_pending`, `delegated_pending`)
- `recurrence_calendar(request)`:
  - Template: `projects/workflowautomation/boards/recurrence_calendar.html`
  - Context keys:
    - `upcoming_schedules`: `RecurringTaskSchedule.objects.filter(tenant=request.tenant, is_active=True).order_by("next_run_date")`
    - `stats`: dict(`total_recurring`, `runs_this_month`)
- `webhook_diagnostics(request)`:
  - Template: `projects/workflowautomation/boards/webhook_diagnostics.html`
  - Context keys:
    - `stats`: dict(`total_endpoints`, `active_endpoints`, `success_rate_pct`, `avg_latency_ms`)
    - `recent_failures`: `ProjectWebhookDelivery.objects.filter(tenant=request.tenant, status="failed")[:10]`
    - `endpoints`: `ProjectWebhookEndpoint.objects.filter(tenant=request.tenant)`

---

## 4. URL Route Specifications

In `apps/projects/urls/WorkflowAutomation/`:

### `WorkflowRules.py`
- `rules/` -> `views.pwf_list`, name=`pwf_list`
- `rules/create/` -> `views.pwf_create`, name=`pwf_create`
- `rules/<int:pk>/` -> `views.pwf_detail`, name=`pwf_detail`
- `rules/<int:pk>/edit/` -> `views.pwf_edit`, name=`pwf_edit`
- `rules/<int:pk>/delete/` -> `views.pwf_delete`, name=`pwf_delete`
- `rules/<int:pk>/toggle/` -> `views.pwf_toggle_active`, name=`pwf_toggle_active`
- `rules/<int:pk>/test-run/` -> `views.pwf_test_run`, name=`pwf_test_run`
- `rules/<int:pk>/execute/` -> `views.pwf_execute_now`, name=`pwf_execute_now`

### `ApprovalGates.py`
- `gates/` -> `views.par_list`, name=`par_list`
- `gates/create/` -> `views.par_create`, name=`par_create`
- `gates/<int:pk>/` -> `views.par_detail`, name=`par_detail`
- `gates/<int:pk>/edit/` -> `views.par_edit`, name=`par_edit`
- `gates/<int:pk>/delete/` -> `views.par_delete`, name=`par_delete`
- `gates/<int:pk>/approve/` -> `views.par_approve`, name=`par_approve`
- `gates/<int:pk>/reject/` -> `views.par_reject`, name=`par_reject`
- `gates/<int:pk>/escalate/` -> `views.par_escalate`, name=`par_escalate`
- `gates/<int:pk>/delegate/` -> `views.par_delegate`, name=`par_delegate`
- `gates/<int:pk>/cancel/` -> `views.par_cancel`, name=`par_cancel`

### `RecurringTasks.py`
- `recurring/` -> `views.rts_list`, name=`rts_list`
- `recurring/create/` -> `views.rts_create`, name=`rts_create`
- `recurring/<int:pk>/` -> `views.rts_detail`, name=`rts_detail`
- `recurring/<int:pk>/edit/` -> `views.rts_edit`, name=`rts_edit`
- `recurring/<int:pk>/delete/` -> `views.rts_delete`, name=`rts_delete`
- `recurring/<int:pk>/toggle/` -> `views.rts_toggle_active`, name=`rts_toggle_active`
- `recurring/<int:pk>/generate/` -> `views.rts_generate_task`, name=`rts_generate_task`
- `recurring/<int:pk>/skip/` -> `views.rts_skip_next`, name=`rts_skip_next`

### `Webhooks.py`
- `webhooks/` -> `views.pwh_list`, name=`pwh_list`
- `webhooks/create/` -> `views.pwh_create`, name=`pwh_create`
- `webhooks/<int:pk>/` -> `views.pwh_detail`, name=`pwh_detail`
- `webhooks/<int:pk>/edit/` -> `views.pwh_edit`, name=`pwh_edit`
- `webhooks/<int:pk>/delete/` -> `views.pwh_delete`, name=`pwh_delete`
- `webhooks/<int:pk>/toggle/` -> `views.pwh_toggle_active`, name=`pwh_toggle_active`
- `webhooks/<int:pk>/test-ping/` -> `views.pwh_test_ping`, name=`pwh_test_ping`
- `webhooks/<int:pk>/rotate-secret/` -> `views.pwh_rotate_secret`, name=`pwh_rotate_secret`
- `webhooks/deliveries/` -> `views.pwh_delivery_list`, name=`pwh_delivery_list`
- `webhooks/deliveries/<int:pk>/` -> `views.pwh_delivery_detail`, name=`pwh_delivery_detail`

### `AutomationBoards.py`
- `automation/overview/` -> `views.automation_overview`, name=`automation_overview`
- `automation/approvals/` -> `views.approval_inbox`, name=`approval_inbox`
- `automation/recurrence-calendar/` -> `views.recurrence_calendar`, name=`recurrence_calendar`
- `automation/webhook-diagnostics/` -> `views.webhook_diagnostics`, name=`webhook_diagnostics`

---

## 5. Template & Badge Specifications

### Badge Classes (theme.css palette)
- `active`: `.badge-green`
- `inactive`: `.badge-slate`
- `approved`, `auto_approved`, `success`: `.badge-green`
- `pending`: `.badge-amber`
- `rejected`, `failed`: `.badge-red`
- `escalated`: `.badge-red`
- `cancelled`: `.badge-slate`
- `simulated`: `.badge-info`
- `phase_gate`, `scope_change`, `budget_override`: `.badge-info`
- `urgent`: `.badge-red`
- `high`: `.badge-amber`
- `medium`: `.badge-info`
- `low`: `.badge-slate`

### Template Paths
- `templates/projects/workflowautomation/workflow/list.html`
- `templates/projects/workflowautomation/workflow/detail.html`
- `templates/projects/workflowautomation/workflow/form.html`
- `templates/projects/workflowautomation/approvalgate/list.html`
- `templates/projects/workflowautomation/approvalgate/detail.html`
- `templates/projects/workflowautomation/approvalgate/form.html`
- `templates/projects/workflowautomation/recurringtask/list.html`
- `templates/projects/workflowautomation/recurringtask/detail.html`
- `templates/projects/workflowautomation/recurringtask/form.html`
- `templates/projects/workflowautomation/webhook/list.html`
- `templates/projects/workflowautomation/webhook/detail.html`
- `templates/projects/workflowautomation/webhook/form.html`
- `templates/projects/workflowautomation/webhook/delivery_list.html`
- `templates/projects/workflowautomation/webhook/delivery_detail.html`
- `templates/projects/workflowautomation/boards/overview.html`
- `templates/projects/workflowautomation/boards/approval_inbox.html`
- `templates/projects/workflowautomation/boards/recurrence_calendar.html`
- `templates/projects/workflowautomation/boards/webhook_diagnostics.html`
