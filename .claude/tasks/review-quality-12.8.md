# Review Findings: Sub-module 12.8 In-Process Quality Control (IPQC)

**Base Commit**: `26ff399f4f232c2b7b5e9925b0982ff06915ed58`  
**HEAD Commit**: `76a34927345ce0e0392f786314bc684b966fff81`  
**Target App**: `apps/quality` (Sub-module 12.8: In-Process Quality Control)  
**Review Status**: 6-Reviewer Pass Complete (`code-reviewer`, `explorer`, `frontend-reviewer`, `performance-reviewer`, `qa-smoke-tester`, `security-reviewer`)

---

## Critical Severity Findings

- [ ] **C1** — URL reverse lookup crash `NoReverseMatch` on `{% url 'quality:nonconformance_detail' ... %}` across all 4 detail templates (`templates/quality/inprocessquality/in_process_inspection/detail.html:298`, `first_article_inspection/detail.html:307`, `process_parameter_log/detail.html:254`, `layered_process_audit/detail.html:261`). In `apps/quality`, the route name is `quality:non_conformance_report_detail`. Navigating to any record with an escalated NCR crashes with a 500 error.
  - **Fix**: Update all 4 detail templates to `{% url 'quality:non_conformance_report_detail' <obj>.non_conformance.pk %}`.

- [ ] **C2** — N+1 queries in `layered_process_audit_export_csv` (`apps/quality/views/InProcessQuality/LayeredProcessAudits.py:192-226`). Loops over records accessing `item.work_center.code` without `select_related("work_center")` causing 1 + N queries.
  - **Fix**: Add `.select_related("work_center")` to `LayeredProcessAudit.objects.filter(...)` in export view.

- [ ] **C3** — Chained N+1 query on `work_order__item` in Form choice fields (`apps/quality/forms/InProcessQuality/InProcessInspections.py:98-100`, `FirstArticleInspections.py:92-94`, `ProcessParameterLogs.py:86-88`). When form renders `<select name="work_order">`, each option evaluates `WorkOrder.__str__` which accesses `self.item`, triggering an un-prefetched DB query per work order.
  - **Fix**: Add `.select_related("item")` to `self.fields["work_order"].queryset` in all three forms.

---

## Important Severity Findings

- [ ] **I1** — Unprotected FAI production release endpoint and missing state guards (`apps/quality/views/InProcessQuality/FirstArticleInspections.py:192`). `first_article_inspection_release` only requires `@login_required`, allowing unprivileged users to release production runs. Also lacks idempotency and inspection completion checks (`total_characteristics_inspected > 0` and zero out-of-spec characteristics).
  - **Fix**: Add `@tenant_admin_required`, check `total_characteristics_inspected > 0` and `characteristics_out_of_spec == 0`, and set `approved_by=request.user` server-side.

- [ ] **I2** — Mass assignment & sign-off spoofing in `FirstArticleInspectionForm` (`apps/quality/forms/InProcessQuality/FirstArticleInspections.py:43` & `templates/quality/inprocessquality/first_article_inspection/form.html:238-240`). Form includes `"approved_by"` in `Meta.fields` and renders an approval user dropdown, allowing arbitrary users to fake approval sign-off during creation/editing.
  - **Fix**: Remove `"approved_by"` from `Meta.fields`, `widgets`, `__init__`, and `clean()`, and remove the dropdown from `form.html`.

- [ ] **I3** — User attribution tampering in `ProcessParameterLogForm` (`apps/quality/forms/InProcessQuality/ProcessParameterLogs.py:34` & `templates/quality/inprocessquality/process_parameter_log/form.html:183-186`). `logged_by` is in `Meta.fields` with a user select dropdown, permitting operators to log out-of-control parameters under other workers' names.
  - **Fix**: Remove `"logged_by"` from `ProcessParameterLogForm`, remove from `form.html`, and assign `log.logged_by = request.user` server-side in `process_parameter_log_create`.

- [ ] **I4** — Delete action button in list templates rendered unconditionally to non-admin users (`templates/quality/inprocessquality/in_process_inspection/list.html:205-210`, `first_article_inspection/list.html:216-221`, `process_parameter_log/list.html:203-208`, `layered_process_audit/list.html:209-214`). Unlike detail templates, list templates render delete buttons to non-admins, leading to 403 Forbidden redirects upon submission.
  - **Fix**: Wrap delete forms in all 4 list templates with `{% if request.user.is_superuser or request.user.is_tenant_admin %}`.

- [ ] **I5** — Linked `ControlledDocument` number field accessed as `.document_number` instead of `.number` in detail templates (`templates/quality/inprocessquality/in_process_inspection/detail.html:235` and `layered_process_audit/detail.html:250`), rendering empty link text ` — <Title>`.
  - **Fix**: Replace `.document_number` with `.number` in both detail templates.

- [ ] **I6** — FAI list template pagination links drop `setup_reason` parameter (`templates/quality/inprocessquality/first_article_inspection/list.html:238, 244`), and filter bar lacks workflow `status` dropdown (`lines 85-136`).
  - **Fix**: Add `<select name="status">` dropdown to FAI list filter bar, and add `{% if current_reason %}&setup_reason={{ current_reason }}{% endif %}` to pagination links.

- [ ] **I7** — Automatic SPC excursion detection in `ProcessParameterLogForm` requires both control limits (`lcl is not None and ucl is not None`), causing single-sided control limits (only UCL or only LCL) to bypass auto-detection (`apps/quality/forms/InProcessQuality/ProcessParameterLogs.py:120`).
  - **Fix**: Update condition to `elif (ucl is not None and recorded > ucl) or (lcl is not None and recorded < lcl):`.

- [ ] **I8** — Uncombined count queries on all 4 list views (`apps/quality/views/InProcessQuality/*.py`). Each view executes 4 separate `.count()`/`.aggregate()` database calls instead of 1 combined `.aggregate()`.
  - **Fix**: Consolidate each list view's stat metrics into a single `.aggregate()` call using conditional `Count("id", filter=Q(...))` and `Avg(...)`.

- [ ] **I9** — Chained N+1 query in detail views for `work_order__item` (`InProcessInspections.py:114`, `FirstArticleInspections.py:114`, `ProcessParameterLogs.py:106`). Detail templates evaluate `{{ obj.work_order }}`, triggering a lookup for `scm_item`.
  - **Fix**: Add `"work_order__item"` to `select_related` in detail views.

---

## Minor Severity Findings

- [ ] **M1** — Model dictionary constant naming divergent from contract spec (`apps/quality/models/InProcessQuality/InProcessInspections.py:62, 70`). Defined as `TYPE_CSS` and `DEFECT_CSS` instead of `INSPECTION_TYPE_CSS` and `DEFECT_CATEGORY_CSS`.
  - **Fix**: Add class-level aliases `INSPECTION_TYPE_CSS = TYPE_CSS` and `DEFECT_CATEGORY_CSS = DEFECT_CSS`.

- [ ] **M2** — Audit logging omitted on all 4 CSV export views (`apps/quality/views/InProcessQuality/*.py`).
  - **Fix**: Add `write_audit_log(request.user, Model(), "export", tenant=request.tenant)` before streaming CSV response.

- [ ] **M3** — Specification tolerance ordering validation omits bounding check for `target_nominal_value` within `[lower_spec_limit, upper_spec_limit]` and control limits within spec limits (`apps/quality/forms/InProcessQuality/ProcessParameterLogs.py:110`).
  - **Fix**: Validate `lsl <= target_nominal_value <= usl` and `lsl <= lcl` / `ucl <= usl` when present in `clean()`.

- [ ] **M4** — Total characteristic consistency validation has redundant `and total_chars > 0` condition (`apps/quality/forms/InProcessQuality/FirstArticleInspections.py:113`).
  - **Fix**: Change check to `if (conforming_chars + oos_chars) > total_chars:`.

- [ ] **M5** — In-Process Inspection pagination links omit `&defect_category={{ current_defect }}` (`templates/quality/inprocessquality/in_process_inspection/list.html:227, 233`).
  - **Fix**: Add parameter check in pagination links.

- [ ] **M6** — Icon-only action buttons lack explicit `aria-label` attribute across list templates (`templates/quality/inprocessquality/*/{list.html}`).
  - **Fix**: Add `aria-label` matching `title` on icon-only buttons.

- [ ] **M7** — Potential numeric database overflow in `LayeredProcessAudit.save()` (`apps/quality/models/InProcessQuality/LayeredProcessAudits.py:168-171`).
  - **Fix**: Clamp calculated `score` between `Decimal("0.00")` and `Decimal("100.00")` before saving.

- [ ] **M8** — Missing composite database indexes on hot tenant-scoped filter columns (`["tenant", "defect_category"]` on InProcessInspection, `["tenant", "containment_action"]` and `["tenant", "excursion_status", "-recorded_at"]` on ProcessParameterLog).
  - **Fix**: Add composite indexes to model `Meta.indexes`.
