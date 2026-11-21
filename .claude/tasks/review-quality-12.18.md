# Review Findings: Submodule 12.18 — Traceability & Serialization

**Base Changeset:** `9448e93f0d2646888e2e79a8faafd9f648805e20`
**Head:** `cd78ceda94931a1119a0ca0913ee0244255d36b0`

---

## Critical

- [ ] **[C1]** `templates/quality/traceabilityserialization/product_recall/detail.html:211`: `NoReverseMatch` crash on detail view when customer complaint is linked: `{% url 'quality:complaint_detail' product_recall.customer_complaint.pk %}` references non-existent URL name `'complaint_detail'`. Must be `'quality:customer_complaint_detail'`.
- [ ] **[C2]** `templates/quality/traceabilityserialization/product_recall/detail.html:223`: `NoReverseMatch` crash on detail view when CAPA investigation is linked: `{% url 'quality:capa_detail' product_recall.capa_investigation.pk %}` references non-existent URL name `'capa_detail'`. Must be `'quality:capa_investigation_detail'`.
- [ ] **[C3]** `apps/quality/views/TraceabilitySerialization/TraceabilityDashboard.py:92`: Unbounded memory bloat in Serialized Item CSV export (`for item in serialized_qs:`). Must use `.iterator(chunk_size=1000)` to avoid caching high-volume serialization datasets in memory.

---

## Important

- [ ] **[I1]** `apps/quality/forms/TraceabilitySerialization/BatchRecords.py:20-21` & `apps/quality/views/TraceabilitySerialization/BatchRecords.py:105-113`: Workflow-controlled `release_status` and `status` are exposed directly in `BatchRecordForm` without release-gate validation, allowing users to bypass the `can_release` check and set `status="released"` / `release_status="approved_full"` via direct form submission or POST. Exclude `release_status` from form; in `clean()`, reject transitions to `status="released"` via regular edit so release only occurs via `batch_record_release`.
- [ ] **[I2]** `apps/quality/views/TraceabilitySerialization/BatchRecords.py:126-133` & `templates/quality/traceabilityserialization/batch_record/detail.html:66-72`: Missing view-level status guard on destructive action: `batch_record_delete` allows unconditional deletion of already-released batch manufacturing records (`status="released"`), violating GMP data retention. Guard in view and disable/hide delete button when released.
- [ ] **[I3]** `apps/quality/views/TraceabilitySerialization/BatchRecords.py:126, 137`, `DeviceIdentifiers.py:120`, `ProductRecalls.py:125`, `SerializedItems.py:130`: Missing elevated admin gate (`@tenant_admin_required`) on all 4 delete views and `batch_record_release`. Add `@tenant_admin_required` decorator and enclose delete buttons in templates inside `{% if request.user.is_superuser or request.user.is_tenant_admin %}`.
- [ ] **[I4]** `apps/quality/views/TraceabilitySerialization/BatchRecords.py:61-71` & `templates/quality/traceabilityserialization/batch_record/detail.html:105`: Chained secondary FK query on Batch Record detail via `work_order__item` (Lesson L18) when printing `{{ batch_record.work_order }}` whose `__str__` accesses `self.item`. Add `"work_order__item"` to `select_related` in `batch_record_detail`.
- [ ] **[I5]** `apps/quality/models/TraceabilitySerialization/SerializedItems.py:125-129` & `apps/quality/views/TraceabilitySerialization/SerializedItems.py:40-42`: Missing composite index on hot tenant filter field `(tenant, epcis_state)` on `SerializedItem`. Add `idx_qser_ten_epcis` index to `Meta.indexes` and generate migration.
- [ ] **[I6]** `apps/quality/models/TraceabilitySerialization/SerializedItems.py:38`, `ProductRecalls.py:35`, and templates (`serialized_item/list.html:140`, `serialized_item/detail.html:30, 131`, `product_recall/list.html:124`, `product_recall/detail.html:32`): Non-existent CSS badge class `badge-purple` used for `"aggregated"` and `"safety_alert"` statuses, rendering unstyled (L33 violation; `static/css/theme.css` only defines green/red/amber/info/muted/slate). Replace with `badge-info` / `badge-slate` / `badge-amber`.
- [ ] **[I7]** `apps/quality/views/TraceabilitySerialization/ProductRecalls.py:105-115` & `SerializedItems.py:87-96`: Audit trail timestamp fields `closed_at` and `commissioned_at` are excluded from forms per contract but never stamped by view logic when transitioning to completed/commissioned status. Set `timezone.now()` on transition.

---

## Minor

- [ ] **[M1]** `apps/quality/models/TraceabilitySerialization/BatchRecords.py:141-146` & `ProductRecalls.py:120-125`: Potential Decimal overflow / MySQL 1264 `Out of range value` crash when actual quantity or recovered quantity is high relative to planned/distributed quantity: `DecimalField(max_digits=5, decimal_places=2)` caps at `999.99`. Clamp calculated percentages to `min(Decimal("999.99"), ...)` in `save()`.
- [ ] **[M2]** `templates/quality/traceabilityserialization/traceability_dashboard.html:77`: `stat-icon red` used instead of canonical L33 palette (`blue`, `green`, `orange`, `purple`, `slate`). Change to `orange`.
- [ ] **[M3]** `apps/quality/views/TraceabilitySerialization/TraceabilityDashboard.py:66-75`: Missing audit log entry for bulk serialized traceability data export. Add `write_audit_log(request.user, SerializedItem(), "export", tenant=request.tenant)`.
- [ ] **[M4]** `apps/quality/views/TraceabilitySerialization/TraceabilityDashboard.py:24-30`: Unconsolidated separate count queries in Dashboard KPIs. Consolidate into `.aggregate(Count(..., filter=...))`.
- [ ] **[M5]** `apps/quality/views/TraceabilitySerialization/DeviceIdentifiers.py:49` & `device_identifier/list.html`: Unused context key `eudamed_status_choices` passed to list view. Add filter dropdown to template and parse in GET parameters.
- [ ] **[M6]** `templates/quality/traceabilityserialization/*/{detail,list}.html`: Dynamic user-controlled strings inside JavaScript `onsubmit="return confirm('...')"` handlers lack `|escapejs`. Add `|escapejs` filter.
