# Review Findings: Module 12.7 Incoming Quality Control (IQC)

**Base SHA**: `26ff399f4f232c2b7b5e9925b0982ff06915ed58`
**Head SHA**: `76a34927345ce0e0392f786314bc684b966fff81`
**Date**: 2026-11-18
**Target Sub-module**: 12.7 Incoming Quality Control (IQC)

---

## Findings Summary

- **Critical**: 3
- **Important**: 10
- **Minor**: 7
- **Total**: 20

---

## Critical Findings

- [x] `[C1]` **Multi-Tenant User Isolation Leakage in Forms**:
  - **Location**: `apps/quality/forms/IncomingQuality/IncomingInspectionLots.py:122-123`, `156-170` & `apps/quality/forms/IncomingQuality/QualityReturnAuthorizations.py:83-85`, `95-99`
  - **Description**: In `IncomingInspectionLotForm`, `decided_by` and `inspector` querysets use `User.objects.filter(is_active=True)` without `tenant=self.tenant`, and are omitted from `reject_foreign(...)` in `clean()`. In `QualityReturnAuthorizationForm`, `assigned_coordinator` is similarly not tenant-scoped and omitted from `reject_foreign(...)`. This allows active users from all tenants to leak into dropdowns and cross-tenant assignment.
  - **Remediation**: Filter User querysets by `User.objects.filter(tenant=self.tenant, is_active=True).order_by("username")` and include `"decided_by"`, `"inspector"`, and `"assigned_coordinator"` in `reject_foreign(...)`.

- [x] `[C2]` **Unhandled `NaN` / `Infinity` in Sample Value Hand-Parsing (DoS / DB Crash Risk)**:
  - **Location**: `apps/quality/views/IncomingQuality/IncomingInspectionLots.py:180-206` & `apps/quality/models/IncomingQuality/IncomingInspectionLots.py:210-225`
  - **Description**: In `incoming_inspection_lot_record_sample`, `float(reading_val)` accepts `"nan"` and `"inf"` without raising `ValueError`. When `"nan"` is stored, `recalculate_spc()` computes `Decimal('nan')`, which crashes with database errors (`decimal.InvalidOperation`) upon save.
  - **Remediation**: Check `math.isfinite(val_float)` immediately after parsing in the view and ignore non-finite numbers in `recalculate_spc()`.

- [x] `[C3]` **Missing Admin Permission Check on List Template Delete Forms**:
  - **Location**: `templates/quality/incoming_quality/certificate_of_analysis/list.html:148-154`, `incoming_inspection_plan/list.html:157-163`, `incoming_inspection_lot/list.html:162-168`, `quality_return_authorization/list.html:143-149`
  - **Description**: Detail templates guard delete forms with `{% if request.user.is_superuser or request.user.is_tenant_admin %}` matching the `@tenant_admin_required` view decorator. List templates expose the destructive delete form in the table actions to all authenticated users.
  - **Remediation**: Wrap each table action delete `<form>` in list templates with `{% if request.user.is_superuser or request.user.is_tenant_admin %}`.

---

## Important Findings

- [ ] `[I1]` **View/Template Contract Failure: ControlledDocument `.document_number` Non-Existent Attribute**:
  - **Location**: `templates/quality/incoming_quality/incoming_inspection_plan/detail.html:139` & `templates/quality/incoming_quality/certificate_of_analysis/detail.html:163`
  - **Description**: Templates reference `.document_number`, but the attribute on `ControlledDocument` is `.number`. Document numbers render blank in UI.
  - **Remediation**: Replace `{{ plan.sop_document.document_number }}` and `{{ coa.supporting_document.document_number }}` with `.number`.

- [ ] `[I2]` **SPC Capability Not Computed on Sample Entry Due to Missing Tolerances Lookup**:
  - **Location**: `apps/quality/views/IncomingQuality/IncomingInspectionLots.py:199` & `apps/quality/models/IncomingQuality/IncomingInspectionLots.py:198-238`
  - **Description**: `recalculate_spc()` is called without `lsl`/`usl`. Because it does not inspect `self.inspection_plan.characteristics_matrix` for the matching characteristic's tolerances, `spc_cp` and `spc_cpk` remain `None`.
  - **Remediation**: Look up `lsl` and `usl` from `self.inspection_plan.characteristics_matrix` for `characteristic_name` if not explicitly provided.

- [ ] `[I3]` **Foreign Key Traversal in `QualityReturnAuthorization.__str__` (N+1 & Unsaved Risk)**:
  - **Location**: `apps/quality/models/IncomingQuality/QualityReturnAuthorizations.py:154-155`
  - **Description**: `__str__` accesses `self.supplier.name` and `self.inspection_lot.lot_number`, triggering 2 extra queries on every `write_audit_log` call and risking exceptions on unsaved instances.
  - **Remediation**: Use local scalar attributes: `return f"{self.number} - Lot {self.inspection_lot_id}"`.

- [ ] `[I4]` **Dashboard KPI Query Fragmentation and Dead Query**:
  - **Location**: `apps/quality/views/IncomingQuality/IqcSpcDashboard.py:17-50`
  - **Description**: `completed_lots` query at line 18 is unused. Six separate count/aggregate queries are executed against the same queryset.
  - **Remediation**: Remove `completed_lots` and collapse the remaining 5 queries into a single conditional `aggregate()` call.

- [ ] `[I5]` **Missing `.distinct()` and `.only('id', 'name')` on Supplier Role Lookups in Forms**:
  - **Location**: `apps/quality/forms/IncomingQuality/IncomingInspectionPlans.py:71-74`, `IncomingInspectionLots.py:112-115`, `CertificatesOfAnalysis.py:67-70`, `QualityReturnAuthorizations.py:79-82`
  - **Description**: Filtering `Party` by `roles__role__in=("supplier", "vendor")` without `.distinct()` creates duplicate supplier options for parties with multiple roles.
  - **Remediation**: Add `.only("id", "name").distinct()` to the supplier queryset in all four form `__init__` methods.

- [ ] `[I6]` **Prohibited `stat-icon red` Class Modifier (L33 Violation)**:
  - **Location**: `templates/quality/incoming_quality/certificate_of_analysis/detail.html:67`, `quality_return_authorization/detail.html:52`, `spc_dashboard.html:76`
  - **Description**: `stat-icon red` is an invalid class under design system rules (only `blue`, `green`, `orange`, `purple`, `slate` exist).
  - **Remediation**: Replace `red` with `orange`.

- [ ] `[I7]` **Template Detail Grid Markup Non-Conformance (`detail-grid` / `detail-item`) & Standalone `<dt>`/`<dd>`**:
  - **Location**: `templates/quality/incoming_quality/incoming_inspection_plan/detail.html:99, 155, 165-170`, `incoming_inspection_lot/detail.html:181, 247, 297-302`, `certificate_of_analysis/detail.html:120, 179, 191-196`, `quality_return_authorization/detail.html:136, 172, 214-219`
  - **Description**: Ad-hoc Tailwind grid `<dl class="grid grid-cols-2...">` bypasses responsive `.detail-grid` theme styles, and notes cards contain invalid standalone `<dt>/<dd>` outside `<dl>`.
  - **Remediation**: Refactor definition lists to `<dl class="detail-grid"><div class="detail-item"><dt>...</dt><dd>...</dd></div></dl>` and replace standalone `<dt>/<dd>` in notes sections with standard container markup.

- [ ] `[I8]` **Analytical Spec Bypass in CoA Verification via `NaN`**:
  - **Location**: `apps/quality/models/IncomingQuality/CertificatesOfAnalysis.py:141-150`
  - **Description**: In `verify_specifications()`, `act_f = float(actual)` does not check `math.isfinite()`. An actual value of `"nan"` evaluates to `False` on both `< lsl` and `> usl`, erroneously marking failing parameters as passed.
  - **Remediation**: Reject non-finite values by setting `is_pass = False` if `not math.isfinite(act_f)`.

- [ ] `[I9]` **Unguarded Status Transitions in `quality_return_authorization_advance`**:
  - **Location**: `apps/quality/views/IncomingQuality/QualityReturnAuthorizations.py:163-185`
  - **Description**: The endpoint permits transitioning an RMA to any status in `STATUS_CHOICES` without lifecycle transition validation.
  - **Remediation**: Define an `ALLOWED_TRANSITIONS` map and reject invalid state transitions.

- [ ] `[I10]` **Unrestricted Quality Usage Decision Overwrite & Sample Entry on Terminal Lots**:
  - **Location**: `apps/quality/views/IncomingQuality/IncomingInspectionLots.py:173-245`
  - **Description**: Usage decisions can be overwritten and samples can be recorded even when a lot is already `completed` or `cancelled`.
  - **Remediation**: Guard `record_sample` and `make_decision` against lots in terminal stages (`completed`, `cancelled`) or non-pending usage decisions.

---

## Minor Findings

- [ ] `[M1]` **Missing `|escapejs` on `obj.number` in List View Delete Confirmation Dialogs**:
  - **Location**: List templates across all four entities (`list.html`).
  - **Remediation**: Interpolate `{{ obj.number|escapejs }}` in inline `confirm(...)` dialogs.

- [ ] `[M2]` **Missing `aria-label` on Icon-Only Table Action Buttons & Next Status Dropdown**:
  - **Location**: Table action buttons in list templates and `quality_return_authorization/detail.html:105`.
  - **Remediation**: Add `aria-label` attributes for accessibility.

- [ ] `[M3]` **Hardcoded Fallback `avg_cpk = 1.45` on Empty SPC Dashboard**:
  - **Location**: `apps/quality/views/IncomingQuality/IqcSpcDashboard.py:27`
  - **Remediation**: Fallback to `None` and render `|default:"—"`.

- [ ] `[M4]` **Missing Cross-Module Hyperlink to SCM PO and GRN**:
  - **Location**: `templates/quality/incoming_quality/incoming_inspection_lot/detail.html:202, 212`
  - **Remediation**: Link to `scm:purchaseorder_detail` and `scm:goodsreceipt_detail` when present.

- [ ] `[M5]` **CSV Exports Iterate Queryset Without `.iterator()`**:
  - **Location**: `export_csv` views across all four entities.
  - **Remediation**: Use `qs.iterator(chunk_size=1000)` to stream records efficiently.

- [ ] `[M6]` **Unnecessary Join in `iqc_spc_dashboard` Recent Alerts**:
  - **Location**: `apps/quality/views/IncomingQuality/IqcSpcDashboard.py:37`
  - **Remediation**: Remove unused `inspection_plan` from `select_related`.

- [ ] `[M7]` **Missing Composite Indexes for SPC Alerts and Ordering**:
  - **Location**: `IncomingInspectionLot` models.
  - **Remediation**: Add `models.Index(fields=["tenant", "spc_out_of_control"], name="idx_qiil_ten_spc_alert")` and `models.Index(fields=["tenant", "-created_at"], name="idx_<prefix>_ten_created")`.
