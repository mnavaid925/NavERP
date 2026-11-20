# Review Findings — Quality Management 12.11: Audit Management

Changeset: `e052bfb46552937ccf9713c99c1f4e2d31fca73e...HEAD`

---

## 1. Code Reviewer Findings

### Critical
- [ ] `apps/quality/views/AuditManagement/AuditFindings.py:233-242` — `audit_finding_create_capa` crashes with `TypeError` and `django.db.IntegrityError` because `CapaInvestigation.objects.create` passes non-existent fields (`problem_description`, `severity`, `target_completion_date`), an invalid status (`"initiated"`), and omits the non-nullable required FK `quality_owner`. Fix: Map to `CapaInvestigation` fields: `issue_summary=...`, `risk_priority="critical" if finding.severity == "critical" else "major"`, `target_closure_date=finding.response_due_date`, `status="draft"`, and provide `quality_owner=finding.audit.lead_auditor or request.user`.

### Important
- [ ] `apps/quality/views/AuditManagement/AuditFindings.py:226-250` — `audit_finding_create_capa` performs multi-model writes across `CapaInvestigation` and `AuditFinding` without `transaction.atomic()`, risking orphaned records on partial failure. Fix: Wrap the creation and finding update block in `with transaction.atomic():`.
- [ ] `apps/quality/models/AuditManagement/AuditFindings.py:145-148` — `AuditFinding.delete()` is not overridden to sync parent audit findings counters, leaving `QualityAudit.total_findings_count` and severity breakdown counts permanently stale after finding deletion. Fix: Override `delete(self, *args, **kwargs)` on `AuditFinding` to call `self.audit.sync_findings_counts()` after deletion.
- [ ] `apps/quality/views/AuditManagement/AuditFindings.py:194-206` — Missing view-level status guard in `audit_finding_submit_response` allows direct POSTs to reopen findings that are already in `status="closed"`. Fix: Add guard `if finding.status not in ("draft", "issued", "response_submitted", "escalated"):` returning a warning redirect.
- [ ] `apps/quality/views/AuditManagement/AuditPrograms.py:162-175` — `audit_program_approve` lacks an authorization gate; `tenant_admin_required` was imported at line 13 but omitted from the view, allowing any tenant user to approve annual audit programs. Fix: Decorate `audit_program_approve` with `@tenant_admin_required`.
- [ ] `apps/quality/views/AuditManagement/RegulatoryInspectionHosts.py:191,207` — `regulatory_inspection_host_log_request` and `regulatory_inspection_host_fulfill_request` unconditionally redirect to inspection detail, kicking users out of the active `audit_war_room` command center on every logged or fulfilled document request. Fix: Check for `request.POST.get("source") == "war_room"` or referer to redirect back to `quality:audit_war_room` with `?host={host.pk}`.
- [ ] `apps/quality/views/AuditManagement/AuditFindings.py:210-222` — `audit_finding_verify_close` lacks an auditor independence check, permitting the cited auditee `assignee` to self-verify and close their own non-conformance. Fix: Enforce that `request.user != finding.assignee` and `request.user in (finding.audit.lead_auditor, ...)` or require admin permissions to close.

### Minor
- [ ] `apps/quality/views/AuditManagement/AuditPrograms.py:13` — Unused import `tenant_admin_required` if not applied to `audit_program_approve`. Fix: Apply decorator or remove unused import.
- [ ] `templates/quality/auditmanagement/audit_program/list.html:220,226` — Year filter parameter `year` is dropped in pagination links. Fix: Add `{% if selected_year %}&year={{ selected_year }}{% endif %}` to previous/next pagination links.
- [ ] `templates/quality/auditmanagement/quality_audit/list.html:257,263` — `program` and `org_unit` filter query parameters are omitted from pagination links. Fix: Interpolate `selected_program` and `selected_org_unit` into pagination hrefs.
- [ ] `templates/quality/auditmanagement/audit_finding/list.html:231,237` — `org_unit` and `assignee` filter query parameters are omitted from pagination links. Fix: Interpolate `selected_org_unit` and `selected_assignee` into pagination hrefs.
- [ ] `apps/quality/views/AuditManagement/QualityAudits.py:196-217` — `quality_audit_publish_report` and `quality_audit_close` lack guards rejecting actions when `audit.status == "cancelled"`. Fix: Add `if audit.status == "cancelled":` validation guard.

---

## 2. Explorer Findings

### Important
- [ ] `apps/quality/models/AuditManagement/AuditFindings.py:136-140` and `apps/quality/views/AuditManagement/AuditFindings.py:69-72` — Overdue SLA status divergence: `is_overdue` and view query flag findings with `response_submitted`, `capa_in_progress`, or `verification_pending` as overdue. Fix: Restrict overdue check to statuses `("draft", "issued", "escalated")`.
- [ ] `apps/quality/views/AuditManagement/AuditFindings.py:180-190` — Stale finding counts on deletion: deleting a finding via `audit_finding_delete` does not call `audit.sync_findings_counts()`. Fix: Call `audit.sync_findings_counts()` after deleting finding.
- [ ] `templates/quality/auditmanagement/quality_audit/list.html:68-116` & `templates/quality/auditmanagement/audit_finding/list.html:67-107` — Dropped filter dropdowns and pagination query params for `program`, `org_unit`, and `assignee`. Fix: Add filter dropdowns and preserve parameters in pagination links.

### Minor
- [ ] `apps/quality/views/AuditManagement/{AuditPrograms,QualityAudits,AuditFindings,RegulatoryInspectionHosts}.py` — CSV export views only inspect `q` and ignore active dropdown filter params (`status`, `type`, etc.). Fix: Apply active filters in export views.
- [ ] `apps/quality/views/AuditManagement/AuditActionTracker.py:1` — Unused import `from datetime import date`. Fix: Remove unused import.

---

## 3. Frontend Reviewer Findings

### Important
- [ ] `templates/quality/auditmanagement/audit_finding/list.html:47,56`, `regulatory_inspection_host/list.html:50`, `audit_action_tracker.html:40,49` — Banned `stat-icon red` class (Rule 2 / L33): Theme design system strictly supports `blue`, `green`, `orange`, `purple`, `slate`. Fix: Replace `stat-icon red` with `stat-icon orange` (for critical/alert stat cards) or `stat-icon slate`.
- [ ] `templates/quality/auditmanagement/audit_finding/list.html:168`, `regulatory_inspection_host/list.html:136,153`, `audit_war_room.html:176` — Non-existent `text-2xs` utility class used. Fix: Replace with standard `text-xs`.

### Minor
- [ ] `templates/quality/auditmanagement/audit_finding/detail.html:211-219`, `regulatory_inspection_host/detail.html:186-194`, `audit_war_room.html:121-130` — Missing `<label for="...">` bindings and missing label on request description. Fix: Add explicit `for` attributes bound to `id_for_label` and missing label tag.
- [ ] `templates/quality/auditmanagement/{audit_program,quality_audit,audit_finding,regulatory_inspection_host}/list.html` — Icon-only action buttons have `title` but lack explicit `aria-label`. Fix: Add `aria-label` matching title for screen reader accessibility.

---

## 4. Performance Reviewer Findings

### Critical
- [ ] `templates/quality/auditmanagement/audit_program/list.html:175-177` & `AuditPrograms.py:100-117` — N+1 SQL query explosion in audit program list loop: rendering `prog.progress_percentage` invokes `self.total_audits_count` and `self.completed_audits_count` 4 times per row. Fix: Annotate `annotated_total` and `annotated_completed` with `Count("audits")` in `audit_program_list` view, and have model properties reuse annotations when present.

### Important
- [ ] `apps/quality/models/AuditManagement/QualityAudits.py:215-228` — `sync_findings_counts` fires 5 separate `COUNT` queries per finding save. Fix: Replace with single `.aggregate(Count("id", filter=Q(...)))`.
- [ ] `apps/quality/views/AuditManagement/{QualityAudits,AuditPrograms,AuditFindings,RegulatoryInspectionHosts}.py` — Sequential unaggregated `SELECT COUNT(*)` queries for KPI stat cards across all 4 list views (14 queries total). Fix: Consolidate into single `.aggregate()` calls per list view.
- [ ] `apps/quality/views/AuditManagement/AuditWarRoom.py:11-32` — Wasted database query evaluating `total_active_count` which is never rendered in template, and multiple queryset evaluations. Fix: Remove dead query and evaluate `list(active_qs)` once.
- [ ] `apps/quality/views/AuditManagement/AuditActionTracker.py:17-25` — Dead queries (`escalated_findings`) and in-memory list comprehension over all tenant findings for overdue calculations. Fix: Remove unused query and filter `overdue_findings` at the ORM level.
- [ ] `apps/quality/models/AuditManagement/AuditFindings.py:116` — Cross-table default ordering `ordering = ["-audit__planned_start_date", "finding_number_in_audit"]` forces SQL INNER JOIN on all queries. Fix: Change default ordering to local fields `["-created_at", "finding_number_in_audit"]`.
- [ ] `apps/quality/views/AuditManagement/AuditFindings.py:226-250` — Missing `transaction.atomic` in multi-model write `audit_finding_create_capa`. Fix: Wrap in `with transaction.atomic():`.

### Minor
- [ ] `templates/quality/auditmanagement/audit_program/detail.html` & `quality_audit/detail.html` — Bypassing prefetched relations in detail templates causing extra SQL counts. Fix: Precompute in view from prefetched querysets.
- [ ] `apps/quality/models/AuditManagement/QualityAudits.py:113` — Missing composite tenant index on `(tenant, standard_framework)`. Fix: Add `models.Index(fields=["tenant", "standard_framework"], name="idx_qaud_ten_framework")`.
- [ ] `apps/quality/views/AuditManagement/AuditFindings.py:78-80` — Unrestricted column loading for dropdown filter querysets. Fix: Add `.only("id", "number", "title")` to `audits` queryset.

---

## 5. QA Smoke Tester Findings

### Critical
- [ ] `apps/quality/views/AuditManagement/AuditFindings.py:233-242` — CAPA Initiation 500 Crash: POSTing to `audit_finding_create_capa` raises `TypeError: CapaInvestigation() got unexpected keyword arguments: 'problem_description', 'severity', 'target_completion_date'`, misses required non-nullable `quality_owner` FK and supplies invalid status `"initiated"`. Fix: Map fields to `CapaInvestigation` schema: `issue_summary`, `risk_priority`, `target_closure_date`, `status="draft"`, and provide `quality_owner=finding.audit.lead_auditor or request.user`.

### Important
- [ ] `apps/quality/views/AuditManagement/AuditPrograms.py:164-175` — Missing authorization on program approval: `audit_program_approve` omits `@tenant_admin_required`, allowing non-admin auditees to approve corporate audit programs. Fix: Decorate with `@tenant_admin_required`.
- [ ] `apps/quality/views/AuditManagement/AuditFindings.py:210-222` — Auditor independence violation on finding closure: `audit_finding_verify_close` lacks an auditor independence check, permitting the cited auditee `assignee` to verify/close their own non-conformance. Fix: Add view-level guard enforcing `request.user != finding.assignee` and auditor/staff permission.
- [ ] `apps/quality/views/AuditManagement/AuditFindings.py:194-206` — Closed findings reopened via direct response POST: `audit_finding_submit_response` lacks status guard, allowing closed findings to transition back to `"response_submitted"`. Fix: Add guard `if finding.status not in ("draft", "issued", "response_submitted", "escalated"):`.
- [ ] `apps/quality/views/AuditManagement/RegulatoryInspectionHosts.py:191,207` — Inspection War Room ejection on request actions: `regulatory_inspection_host_log_request` and `fulfill_request` unconditionally redirect to inspection detail, kicking users out of the active War Room command center. Fix: Check `request.POST.get("source") == "war_room"` or referer and redirect back to `quality:audit_war_room?host={host.pk}`.
- [ ] `apps/quality/views/AuditManagement/AuditFindings.py:180-190` & `AuditFindings.py:145-148` — Stale finding counters on finding deletion: deleting a finding does not invoke `self.audit.sync_findings_counts()`. Fix: Override `delete()` on `AuditFinding` to call `self.audit.sync_findings_counts()`.

### Minor
- [ ] `apps/quality/views/AuditManagement/QualityAudits.py:196-217` — Cancelled audit mutation: `quality_audit_publish_report` and `quality_audit_close` lack state checks for `audit.status == "cancelled"`. Fix: Add guard rejecting actions when status is cancelled.




