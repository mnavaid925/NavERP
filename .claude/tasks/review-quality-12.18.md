# Review Findings: Submodule 12.18 — Traceability & Serialization

**Base Changeset:** `9448e93f0d2646888e2e79a8faafd9f648805e20`
**Head:** `cd78ceda94931a1119a0ca0913ee0244255d36b0`

---

## Pass 1: Code Reviewer (`code-reviewer`)

### Critical
- **[CR-C1]** `templates/quality/traceabilityserialization/product_recall/detail.html:211`: `NoReverseMatch` crash on detail view when customer complaint is linked: `{% url 'quality:complaint_detail' product_recall.customer_complaint.pk %}` references non-existent URL name `'complaint_detail'`. Must be `'quality:customer_complaint_detail'`.
- **[CR-C2]** `templates/quality/traceabilityserialization/product_recall/detail.html:223`: `NoReverseMatch` crash on detail view when CAPA investigation is linked: `{% url 'quality:capa_detail' product_recall.capa_investigation.pk %}` references non-existent URL name `'capa_detail'`. Must be `'quality:capa_investigation_detail'`.

### Important
- **[CR-I1]** `apps/quality/forms/TraceabilitySerialization/BatchRecords.py:20-21` & `apps/quality/views/TraceabilitySerialization/BatchRecords.py:105-113`: Workflow-controlled status and release status are exposed directly in `BatchRecordForm` without release-gate validation, allowing users to bypass the `can_release` check and set `status="released"` / `release_status="approved_full"` via direct form submission or POST. Exclude `release_status` from form or validate in `clean()` that transition to `"released"` / `"approved_full"` requires `self.instance.can_release` (or restrict release to the dedicated `batch_record_release` POST action).
- **[CR-I2]** `apps/quality/views/TraceabilitySerialization/BatchRecords.py:127-133`: Missing view-level status guard on destructive action: `batch_record_delete` allows unconditional deletion of already-released batch manufacturing records (`status="released"`), violating GMP data retention. Guard in view and disable/hide delete button when released.
- **[CR-I3]** `apps/quality/models/TraceabilitySerialization/ProductRecalls.py:120-125` & `apps/quality/models/TraceabilitySerialization/BatchRecords.py:141-146`: Potential Decimal overflow / MySQL 1264 `Out of range value` crash when actual quantity or recovered quantity is high relative to planned/distributed quantity: `DecimalField(max_digits=5, decimal_places=2)` caps at `999.99`, but `yield_percentage` and `recovery_rate_pct` can calculate to `>= 1000.00%`. Clamp calculated percentages to `min(Decimal("999.99"), ...)` in `save()`.
- **[CR-I4]** `apps/quality/models/TraceabilitySerialization/SerializedItems.py:38`, `apps/quality/models/TraceabilitySerialization/ProductRecalls.py:35`, and templates (`serialized_item/list.html:140`, `serialized_item/detail.html:30, 131`, `product_recall/list.html:124`, `product_recall/detail.html:32`): Non-existent CSS badge class `badge-purple` used for `"aggregated"` and `"safety_alert"` statuses, rendering unstyled (L33 violation; `static/css/theme.css` only defines green/red/amber/info/muted/slate). Replace with `badge-info` / `badge-slate`.
- **[CR-I5]** `apps/quality/views/TraceabilitySerialization/ProductRecalls.py:105-115` & `apps/quality/views/TraceabilitySerialization/SerializedItems.py:87-96`: Audit trail timestamp fields `closed_at` and `commissioned_at` are excluded from forms per contract but never stamped by view logic when transitioning to completed/commissioned status.

### Minor
- **[CR-M1]** `apps/quality/views/TraceabilitySerialization/TraceabilityDashboard.py:9`: Unused import `write_audit_log` in dashboard.
- **[CR-M2]** `apps/quality/views/TraceabilitySerialization/TraceabilityDashboard.py:4`: Unused import `Count` in dashboard.
- **[CR-M3]** `apps/quality/views/TraceabilitySerialization/DeviceIdentifiers.py:49`: Unused context key `eudamed_status_choices` passed to list view. Add filter or remove.

---

## Pass 2: Explorer (`explorer`)

### Critical
- **[EX-C1]** `templates/quality/traceabilityserialization/product_recall/detail.html:211`: Duplicate of CR-C1. Broken route target `'quality:complaint_detail'` -> change to `'quality:customer_complaint_detail'`.
- **[EX-C2]** `templates/quality/traceabilityserialization/product_recall/detail.html:223`: Duplicate of CR-C2. Broken route target `'quality:capa_detail'` -> change to `'quality:capa_investigation_detail'`.

### Important
- **[EX-I1]** Duplicate of CR-I4. `badge-purple` used in `product_recall/detail.html:32`, `serialized_item/detail.html:30`, and models. Replace with `badge-info`/`badge-slate`.
- **[EX-I2]** Duplicate of CR-M3. `eudamed_status_choices` passed in view context but missing filter dropdown in template.

### Minor
- **[EX-M1]** Duplicate of CR-M1. Unused import `write_audit_log` in `TraceabilityDashboard.py:9`.
- **[EX-M2]** Duplicate of CR-M2. Unused import `Count` in `TraceabilityDashboard.py:4`.

---

## Pass 3: Frontend Reviewer (`frontend-reviewer`)

### Critical
- **[FR-C1]** Duplicate of CR-C1. `templates/quality/traceabilityserialization/product_recall/detail.html:211`: `NoReverseMatch` crash on `{% url 'quality:complaint_detail' ... %}` -> update to `'quality:customer_complaint_detail'`.
- **[FR-C2]** Duplicate of CR-C2. `templates/quality/traceabilityserialization/product_recall/detail.html:223`: `NoReverseMatch` crash on `{% url 'quality:capa_detail' ... %}` -> update to `'quality:capa_investigation_detail'`.

### Important
- **[FR-I1]** Duplicate of CR-I4. `badge-purple` used across 5 template locations (`serialized_item/list.html:140`, `serialized_item/detail.html:30, 131`, `product_recall/list.html:124`, `product_recall/detail.html:32`). Replace with `badge-info`/`badge-slate`/`badge-amber`.
- **[FR-I2]** `templates/quality/traceabilityserialization/traceability_dashboard.html:77`: `stat-icon red` used instead of canonical L33 palette (`blue`, `green`, `orange`, `purple`, `slate`). Change to `orange`.

### Minor
- **[FR-M1]** `batch_record/list.html:150-161`, `device_identifier/list.html:161-172`, `serialized_item/list.html:176-187`, `product_recall/list.html:160-171`: Icon-only action links/buttons missing explicit `aria-label` attributes.

---

## Pass 4: Performance Reviewer (`performance-reviewer`)

### Critical
- **[PR-C1]** `apps/quality/views/TraceabilitySerialization/TraceabilityDashboard.py:92`: Unbounded memory bloat in Serialized Item CSV export (`for item in serialized_qs:`). Must use `.iterator(chunk_size=1000)` to avoid caching high-volume serialization datasets in memory.

### Important
- **[PR-I1]** `apps/quality/views/TraceabilitySerialization/BatchRecords.py:61-71` & `batch_record/detail.html:105`: Chained secondary FK query on Batch Record detail via `work_order__item` (Lesson L18) when printing `{{ batch_record.work_order }}` whose `__str__` accesses `self.item`. Add `"work_order__item"` to `select_related`.
- **[PR-I2]** `apps/quality/models/TraceabilitySerialization/SerializedItems.py:125-129` & `apps/quality/views/TraceabilitySerialization/SerializedItems.py:40-42`: Missing composite index on hot tenant filter field `(tenant, epcis_state)` on `SerializedItem`. Add `idx_qser_ten_epcis` index.

### Minor
- **[PR-M1]** `apps/quality/views/TraceabilitySerialization/TraceabilityDashboard.py:24-30`: Unconsolidated separate count queries in Dashboard KPIs. Consolidate into `.aggregate(Count(..., filter=...))`.
- **[PR-M2]** `traceability_dashboard.html:123` & `serialized_item/detail.html:138`: Redundant extra count queries on querysets iterated immediately after (`.count` -> `|length`).

---

## Pass 5: QA Smoke Tester (`qa-smoke-tester`)

### Critical
- **[QA-C1]** Duplicate of CR-C1 / FR-C1. `templates/quality/traceabilityserialization/product_recall/detail.html:211`: Confirmed empirical 500 crash (`django.urls.exceptions.NoReverseMatch: Reverse for 'complaint_detail' not found`) when rendering product recall linked to `CustomerComplaint`.
- **[QA-C2]** Duplicate of CR-C2 / FR-C2. `templates/quality/traceabilityserialization/product_recall/detail.html:223`: Confirmed empirical 500 crash (`django.urls.exceptions.NoReverseMatch: Reverse for 'capa_detail' not found`) when rendering product recall linked to `CapaInvestigation`.

### Important
- None. (Cross-tenant IDOR confirmed safe: all 4 entities return HTTP 404 when queried across tenants).

### Minor
- None. (26 core routes return HTTP 200/302, CSV export returns `text/csv`, zero comment leaks).
