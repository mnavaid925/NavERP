# Review Findings: Submodule 12.18 — Traceability & Serialization

**Base Changeset:** `9448e93f0d2646888e2e79a8faafd9f648805e20`
**Head:** `cd78ceda94931a1119a0ca0913ee0244255d36b0`

---

## Critical

- [x] **[C1]** `templates/quality/traceabilityserialization/product_recall/detail.html:211`: `NoReverseMatch` crash on detail view when customer complaint is linked: `{% url 'quality:complaint_detail' product_recall.customer_complaint.pk %}` references non-existent URL name `'complaint_detail'`. Must be `'quality:customer_complaint_detail'`. (fixed in `f383f37c`)
- [x] **[C2]** `templates/quality/traceabilityserialization/product_recall/detail.html:223`: `NoReverseMatch` crash on detail view when CAPA investigation is linked: `{% url 'quality:capa_detail' product_recall.capa_investigation.pk %}` references non-existent URL name `'capa_detail'`. Must be `'quality:capa_investigation_detail'`. (fixed in `f99cacf8`)
- [x] **[C3]** `apps/quality/views/TraceabilitySerialization/TraceabilityDashboard.py:92`: Unbounded memory bloat in Serialized Item CSV export (`for item in serialized_qs:`). Must use `.iterator(chunk_size=1000)` to avoid caching high-volume serialization datasets in memory. (fixed in `380fb9df`)

---

## Important

- [x] **[I1]** `apps/quality/forms/TraceabilitySerialization/BatchRecords.py:20-21` & `apps/quality/views/TraceabilitySerialization/BatchRecords.py:105-113`: Workflow-controlled `release_status` and `status` are exposed directly in `BatchRecordForm` without release-gate validation, allowing users to bypass the `can_release` check and set `status="released"` / `release_status="approved_full"` via direct form submission or POST. Exclude `release_status` from form; in `clean()`, reject transitions to `status="released"` via regular edit so release only occurs via `batch_record_release`. (fixed in `d79af370`, `360fe688`)
- [x] **[I2]** `apps/quality/views/TraceabilitySerialization/BatchRecords.py:126-133` & `templates/quality/traceabilityserialization/batch_record/detail.html:66-72`: Missing view-level status guard on destructive action: `batch_record_delete` allows unconditional deletion of already-released batch manufacturing records (`status="released"`), violating GMP data retention. Guard in view and disable/hide delete button when released. (fixed in `08e4f0b6`, `00fa6e73`)
- [x] **[I3]** `apps/quality/views/TraceabilitySerialization/BatchRecords.py:126, 137`, `DeviceIdentifiers.py:120`, `ProductRecalls.py:125`, `SerializedItems.py:130`: Missing elevated admin gate (`@tenant_admin_required`) on all 4 delete views and `batch_record_release`. Add `@tenant_admin_required` decorator and enclose delete buttons in templates inside `{% if request.user.is_superuser or request.user.is_tenant_admin %}`. (fixed in `3fee3547`, `67cf5b2c`, `ed0fbb90`, `ad19ef87`, `69e94084`, `d67b90be`, `643b1d87`, `6bbbe6b1`, `25944e02`, `1380c0a3`, `9dc593a3`, `23e9f411`)
- [x] **[I4]** `apps/quality/views/TraceabilitySerialization/BatchRecords.py:61-71` & `templates/quality/traceabilityserialization/batch_record/detail.html:105`: Chained secondary FK query on Batch Record detail via `work_order__item` (Lesson L18) when printing `{{ batch_record.work_order }}` whose `__str__` accesses `self.item`. Add `"work_order__item"` to `select_related` in `batch_record_detail`. (fixed in `aef42bf8`)
- [x] **[I5]** `apps/quality/models/TraceabilitySerialization/SerializedItems.py:125-129` & `apps/quality/views/TraceabilitySerialization/SerializedItems.py:40-42`: Missing composite index on hot tenant filter field `(tenant, epcis_state)` on `SerializedItem`. Add `idx_qser_ten_epcis` index to `Meta.indexes` and generate migration. (fixed in `ee6b2cc2`, `b6b57879`)
- [x] **[I6]** `apps/quality/models/TraceabilitySerialization/SerializedItems.py:38`, `ProductRecalls.py:35`, and templates (`serialized_item/list.html:140`, `serialized_item/detail.html:30, 131`, `product_recall/list.html:124`, `product_recall/detail.html:32`): Non-existent CSS badge class `badge-purple` used for `"aggregated"` and `"safety_alert"` statuses, rendering unstyled (L33 violation; `static/css/theme.css` only defines green/red/amber/info/muted/slate). Replace with `badge-info` / `badge-slate` / `badge-amber`. (fixed in `747c3208`, `dc1a8615`, `28d75ed6`, `00de296c`, `23777fe3`, `539431f2`)
- [x] **[I7]** `apps/quality/views/TraceabilitySerialization/ProductRecalls.py:105-115` & `SerializedItems.py:87-96`: Audit trail timestamp fields `closed_at` and `commissioned_at` are excluded from forms per contract but never stamped by view logic when transitioning to completed/commissioned status. Set `timezone.now()` on transition. (fixed in `019b5b1f`, `ebf8d13c`)

---

## Minor

- [x] **[M1]** `apps/quality/models/TraceabilitySerialization/BatchRecords.py:141-146` & `ProductRecalls.py:120-125`: Potential Decimal overflow / MySQL 1264 `Out of range value` crash when actual quantity or recovered quantity is high relative to planned/distributed quantity: `DecimalField(max_digits=5, decimal_places=2)` caps at `999.99`. Clamp calculated percentages to `min(Decimal("999.99"), ...)` in `save()`. (fixed in `7a7bfab4`, `acc6d173`)
- [x] **[M2]** `templates/quality/traceabilityserialization/traceability_dashboard.html:77`: `stat-icon red` used instead of canonical L33 palette (`blue`, `green`, `orange`, `purple`, `slate`). Change to `orange`. (fixed in `89808fab`)
- [x] **[M3]** `apps/quality/views/TraceabilitySerialization/TraceabilityDashboard.py:66-75`: Missing audit log entry for bulk serialized traceability data export. Add `write_audit_log(request.user, SerializedItem(), "export", tenant=request.tenant)`. (fixed in `f63d0499`)
- [x] **[M4]** `apps/quality/views/TraceabilitySerialization/TraceabilityDashboard.py:24-30`: Unconsolidated separate count queries in Dashboard KPIs. Consolidate into `.aggregate(Count(..., filter=...))`. (fixed in `6b25a581`)
- [x] **[M5]** `apps/quality/views/TraceabilitySerialization/DeviceIdentifiers.py:49` & `device_identifier/list.html`: Unused context key `eudamed_status_choices` passed to list view. Add filter dropdown to template and parse in GET parameters. (fixed in `d4537589`, `c010fffc`)
- [x] **[M6]** `templates/quality/traceabilityserialization/*/{detail,list}.html`: Dynamic user-controlled strings inside JavaScript `onsubmit="return confirm('...')"` handlers lack `|escapejs`. Add `|escapejs` filter. (fixed in `1a4d79d8`, `136a8ec2`, `5f7df1f7`, `4e108551`, `49076982`, `1ed0aa26`, `69ab3fde`, `68821fce`)
