# Review Findings: Sub-module 7.17 — Workflow & Automation

**Base:** `c7c4eab96c5a1d5c90be88e1e0ba8379a919877c`
**Target:** `apps/projects/` and `templates/projects/workflowautomation/` (Sub-module 7.17)
**Date:** 2026-09-19
**Reviewers:** 6/6 completed (`code-reviewer`, `explorer`, `frontend-reviewer`, `performance-reviewer`, `qa-smoke-tester`, `security-reviewer`)

---

## Summary of Findings

| Category | Total | Open | Fixed | Skipped |
|---|---|---|---|---|
| Critical | 8 | 8 | 0 | 0 |
| Important | 12 | 12 | 0 | 0 |
| Minor | 7 | 7 | 0 | 0 |
| **Total** | **27** | **27** | **0** | **0** |

---

## Critical Findings

- [ ] **C1** — `apps/projects/views/WorkflowAutomation/*.py`
  - **Issue:** Systemic `write_audit_log` argument signature inversion across all 4 view modules (`WorkflowRules.py`, `ApprovalGates.py`, `RecurringTasks.py`, `Webhooks.py`). Core signature is `write_audit_log(user, obj, action, changes=None, tenant=None)` but views call `write_audit_log(request.tenant, request.user, action, obj, message)`. This passes string message to `tenant` FK raising `ValueError` and HTTP 500 error on every mutative POST operation.
  - **Fix:** Update all `write_audit_log` calls to pass `user=request.user, obj=..., action=..., changes={"description": ...}, tenant=request.tenant`.

- [ ] **C2** — `apps/projects/models/WorkflowAutomation/RecurringTasks.py:130`
  - **Issue:** `RecurringTaskSchedule.generate_task` parameter mismatch with `ProjectTask`. Calls `ProjectTask.objects.create()` with invalid kwargs (`estimated_hours`, `assigned_to`, `start_date`, `due_date`, and status `"todo"`), raising fatal `TypeError` on task minting.
  - **Fix:** Map to `ProjectTask` schema: `effort_hours=self.effort_hours`, `assignee=assigned_to`, `planned_start=self.next_run_date`, `planned_end=self.next_run_date + timedelta(days=5)`, `status="planned"`, and map `self.priority` to valid `ProjectTask.PRIORITY_CHOICES`.

- [ ] **C3** — `apps/projects/forms/WorkflowAutomation/ApprovalGates.py:57` & `apps/projects/views/WorkflowAutomation/ApprovalGates.py:278`
  - **Issue:** Cross-tenant user leakage and delegation vulnerability in `ApprovalDelegateForm`. `delegate_approver` evaluates `User.objects.filter(is_active=True)` without tenant scoping, and `par_delegate` saves without verifying that the chosen delegate belongs to `request.tenant`, allowing cross-tenant approval delegation.
  - **Fix:** Accept `tenant` in `ApprovalDelegateForm.__init__`, filter `queryset=User.objects.filter(tenant=tenant, is_active=True)`, pass `tenant=request.tenant` in view, and verify `delegate.tenant == request.tenant` before saving.

- [ ] **C4** — `apps/projects/views/WorkflowAutomation/ApprovalGates.py:194-271`
  - **Issue:** Broken object-level authorization & requester self-approval in approval gates. `par_approve`, `par_reject`, `par_delegate`, and `par_escalate` do not verify that `request.user` is authorized (`gate.approver`, `gate.delegate_approver`, or `request.user.is_tenant_admin`), and allow self-approval where `gate.requested_by == request.user`.
  - **Fix:** Enforce approver or admin check, and block requester self-approval (`if request.user == gate.requested_by and not is_admin: error(...)`).

- [ ] **C5** — `apps/projects/forms/WorkflowAutomation/ApprovalGates.py:16-32` & `apps/projects/views/WorkflowAutomation/ApprovalGates.py:101-109`
  - **Issue:** Client-controlled `auto_approve_threshold` enables instant self-approval of governance gates. `ProjectApprovalGateForm` exposes `auto_approve_threshold` in `Meta.fields`, allowing any user to set it equal to `threshold_amount` and bypass review.
  - **Fix:** Remove `auto_approve_threshold` from `ProjectApprovalGateForm.Meta.fields`.

- [ ] **C6** — `templates/projects/workflowautomation/boards/overview.html:85` & `boards/approval_inbox.html:63, 140`
  - **Issue:** Non-existent attribute `gate.name` used instead of `gate.title`, rendering blank gate titles on operational boards.
  - **Fix:** Replace `{{ gate.name }}` with `{{ gate.title }}`.

- [ ] **C7** — `templates/projects/workflowautomation/boards/overview.html:204, 221`
  - **Issue:** Non-existent attributes `log.trigger_entity`, `log.trigger_event`, and `log.executed_at` used on `WorkflowExecutionLog`, rendering blank strings and timestamps.
  - **Fix:** Change to `{{ log.rule.get_trigger_entity_display }}`, `{{ log.rule.get_trigger_event_display }}`, and `{{ log.fired_at|date:"Y-m-d H:i" }}`.

- [ ] **C8** — `apps/projects/views/WorkflowAutomation/RecurringTasks.py:80`
  - **Issue:** N+1 query trap in recurring task detail view. `rts_detail` fetches recent `ProjectTask` rows without `.select_related("assignee")`, causing 1 + 10 queries inside template loop.
  - **Fix:** Add `.select_related("assignee")` to `recent_tasks` query in `rts_detail`.

---

## Important Findings

- [ ] **I1** — `apps/projects/views/WorkflowAutomation/ApprovalGates.py:174-190`
  - **Issue:** Missing status guard in `par_delete`. Deletes approval gates unconditionally without checking `gate.is_terminal`, allowing users to destroy historical audit records of approved or rejected gates.
  - **Fix:** Add check `if gate.status not in ("pending", "cancelled"):` to block deletion of decided gates.

- [ ] **I2** — `apps/projects/views/WorkflowAutomation/Webhooks.py:99, 259` & `templates/projects/workflowautomation/webhook/detail.html`
  - **Issue:** Webhook HMAC signing secret discarded and never revealed to the user on create or rotate, leaving the user unable to configure the receiving system.
  - **Fix:** Capture `raw_secret = webhook.generate_secret()`, store in `request.session["_whk_secret_reveal"] = {"pk": webhook.pk, "secret": raw_secret}`, pop once in `pwh_detail`, and render one-time reveal card in `detail.html`.

- [ ] **I3** — `apps/projects/views/WorkflowAutomation/*.py` (WorkflowRules:38, ApprovalGates:35, RecurringTasks:33, Webhooks:35, 278)
  - **Issue:** Unvalidated GET parameters (`project`, `webhook`) passed directly to `.filter(project_id=...)` without `.isdigit()`, causing 500 error on non-integer input.
  - **Fix:** Guard with `if param.isdigit(): qs = qs.filter(...)`.

- [ ] **I4** — `templates/projects/workflowautomation/recurringtask/detail.html:151`
  - **Issue:** Generated tasks table references non-existent attributes `t.assigned_to` and `t.due_date` instead of `t.assignee` and `t.planned_end`, rendering blank values.
  - **Fix:** Replace with `t.assignee` and `t.planned_end`.

- [ ] **I5** — `templates/projects/workflowautomation/workflow/detail.html:253`
  - **Issue:** Rule "Execute Now" form hardcodes `<input type="hidden" name="target_id" value="1">` instead of allowing user input.
  - **Fix:** Bind `target_id` to `test_form.target_id` or an explicit user input field.

- [ ] **I6** — `templates/projects/workflowautomation/boards/*.html` (overview, approval_inbox, recurrence_calendar, webhook_diagnostics)
  - **Issue:** Board templates use non-existent `.table-responsive` instead of theme.css `.table-wrap`, and `.btn-xs` instead of `.btn-sm`.
  - **Fix:** Replace `.table-responsive` with `.table-wrap` and `.btn-xs` with `.btn-sm` across board templates.

- [ ] **I7** — `templates/projects/workflowautomation/webhook/delivery_detail.html:54`
  - **Issue:** Webhook delivery status check treats all non-200 codes as errors (`badge-red`), ignoring valid 2xx HTTP response codes (201, 204).
  - **Fix:** Use `delivery.status_badge` or check `delivery.response_status >= 200 and delivery.response_status < 300`.

- [ ] **I8** — `apps/projects/views/WorkflowAutomation/*.py` (RecurringTasks:208, WorkflowRules:246, Webhooks:227)
  - **Issue:** Non-atomic multi-step mutations in `rts_generate_task`, `pwf_execute_now`, and `pwh_test_ping` risk partial commits on error.
  - **Fix:** Wrap mutations in `with transaction.atomic():`.

- [ ] **I9** — `apps/projects/models/WorkflowAutomation/WorkflowRules.py:103` & `Webhooks.py:123`
  - **Issue:** Missing database indexes on `WorkflowExecutionLog` for `(tenant, -fired_at)` and `ProjectWebhookDelivery` for `(tenant, -attempted_at)` and `(tenant, status, -attempted_at)`.
  - **Fix:** Add composite indexes to model `Meta.indexes`.

- [ ] **I10** — `apps/projects/views/WorkflowAutomation/AutomationBoards.py:132` & list views
  - **Issue:** Unconsolidated multi-scan queries in `webhook_diagnostics` (6 separate queries) and multiple count queries across list views.
  - **Fix:** Consolidate into single `aggregate()` queries.

- [ ] **I11** — `apps/projects/views/WorkflowAutomation/WorkflowRules.py:204, 242`
  - **Issue:** Unvalidated `target_id` in `pwf_test_run` and `pwf_execute_now` allows specifying IDs without verifying tenant ownership.
  - **Fix:** Validate that `target_id` belongs to `request.tenant` if model is resolvable, or ensure tenant scope check.

- [ ] **I12** — `apps/projects/management/commands/seed_projects.py:4170`
  - **Issue:** Seeder data format inconsistencies: `rule.conditions` seeded as dict instead of list of condition dicts; `title_template` seeded with `{week}` instead of `{{week}}`.
  - **Fix:** Standardize seeder formats to match runtime schemas.

---

## Minor Findings

- [ ] **M1** — `apps/projects/models/WorkflowAutomation/WorkflowRules.py:101` & `views/WorkflowAutomation/WorkflowRules.py:218`
  - **Issue:** `WorkflowExecutionLog.executed_actions` is typed with `default=list`, but `pwf_test_run` stores a dict `{"actions": rule.actions, "simulated": True}`.
  - **Fix:** Standardize `executed_actions` format to a list of dicts across all log creation paths.

- [ ] **M2** — `templates/projects/workflowautomation/recurringtask/detail.html:151`
  - **Issue:** Unguarded filter lookup on nullable FK `{{ t.assignee.get_full_name|default:t.assignee.username|default:"Unassigned" }}` (Lesson L10).
  - **Fix:** Wrap in `{% if t.assignee %}`.

- [ ] **M3** — `apps/projects/forms/WorkflowAutomation/Webhooks.py:21`
  - **Issue:** `event_types` validation allows empty array `[]`, creating webhooks that never fire.
  - **Fix:** Add validation ensuring at least one event type is selected.

- [ ] **M4** — `apps/projects/forms/WorkflowAutomation/ApprovalGates.py:25`
  - **Issue:** Client spoofing of `requested_by` in `ProjectApprovalGateForm`.
  - **Fix:** Exclude `requested_by` from `Meta.fields` and set `gate.requested_by = request.user` in `par_create`.

- [ ] **M5** — `templates/projects/workflowautomation/boards/*.html`
  - **Issue:** Board KPI stat cards bypass design system `.stat-grid` / `.stat-card` / `.stat-label` / `.stat-value`.
  - **Fix:** Refactor board stat cards to use standard design system classes.

- [ ] **M6** — `apps/projects/views/WorkflowAutomation/AutomationBoards.py:72, 104`
  - **Issue:** Redundant `COUNT(*)` queries before iteration (count vs len) in `approval_inbox` and `recurrence_calendar`.
  - **Fix:** Use `len()` on sliced/evaluated querysets or pass precomputed counts.

- [ ] **M7** — `apps/projects/models/WorkflowAutomation/WorkflowRules.py:110` & `Webhooks.py:130`
  - **Issue:** Chained N+1 query risk in `__str__` accessing foreign key `.number` without guarantee of prefetch.
  - **Fix:** Fall back safely or use `self.rule_id` / `self.webhook_id`.
