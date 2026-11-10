# Sub-module 11.11 Review Findings — Compliance & Regulatory Management

- **Base SHA:** `af494e50b130876319671d67c7a39fa5ed1b9188`
- **Scope:** NavERP Sub-module 11.11 (`apps/assets/` and `templates/assets/assetcompliance/`)
- **Models:** `AssetComplianceFramework`, `AssetComplianceAudit`, `AssetPermitLicense`, `AssetComplianceIncident`
- **Review Passes:** 6 serial passes (`code-reviewer`, `explorer`, `frontend-reviewer`, `performance-reviewer`, `qa-smoke-tester`, `security-reviewer`)

---

## Pass 1: Code Reviewer (`code-reviewer`)

### Critical
- **C1: Broken `write_audit_log` Call Signature Across All Views (HTTP 500 on all POST actions)**
  - `apps/assets/views/AssetCompliance/AssetComplianceFrameworks.py:106-113, 137-144, 168-175`
  - `apps/assets/views/AssetCompliance/AssetComplianceAudits.py:118-125, 153-160, 183-190, 202-209, 224-231`
  - `apps/assets/views/AssetCompliance/AssetPermitLicenses.py:121-128, 156-163, 187-194, 205-212`
  - `apps/assets/views/AssetCompliance/AssetComplianceIncidents.py:134-141, 175-182, 205-212, 226-233, 250-257`
  - *Issue:* Signature in `apps/core/utils.py` is `write_audit_log(user, obj, action, changes=None, tenant=None)`. All 17 view call sites passed 6 positional arguments `(request.tenant, request.user, action, ModelName, pk, message)`.
  - *Fix:* Update all 17 call sites to `write_audit_log(request.user, instance, action, changes=..., tenant=request.tenant)`.

### Important
- **I1: Missing User FK Scoping in `reject_foreign` (Cross-Tenant IDOR Risk)**
  - `apps/assets/forms/AssetCompliance/AssetComplianceAudits.py:63` (`lead_auditor_user`)
  - `apps/assets/forms/AssetCompliance/AssetComplianceIncidents.py:71` (`assigned_investigator`)
  - *Fix:* Include `"lead_auditor_user"` in `AssetComplianceAuditForm.clean()` and `"assigned_investigator"` in `AssetComplianceIncidentForm.clean()`.
- **I2: Unhandled `ProtectedError` on Framework Deletion (HTTP 500)**
  - `apps/assets/views/AssetCompliance/AssetComplianceFrameworks.py:163-177`
  - *Fix:* Wrap `framework.delete()` in `try...except ProtectedError`, display friendly error message, and redirect back to detail page.
- **I3: Missing Filter Dropdowns in List Templates**
  - `templates/assets/assetcompliance/asset_compliance_framework/list.html:52-82` (missing `<select name="category">`)
  - `templates/assets/assetcompliance/asset_compliance_audit/list.html:59-97` (missing `<select name="framework">`)
  - `templates/assets/assetcompliance/asset_compliance_incident/list.html:59-97` (missing `<select name="agency">`)
  - *Fix:* Add the missing `<select>` filter elements using `category_list`, `framework_list`, and `agency_list` with `pk|stringformat:"d"` comparison.
- **I4: Seeder `--flush` Omission Leaves 11.11 Data Intact**
  - `apps/assets/management/commands/seed_assets.py:75-109`
  - *Fix:* Add deletion calls for the four 11.11 models to the flush block.

### Minor
- **M1: Pagination Query Parameters Drop Active Filters**
  - `templates/assets/assetcompliance/asset_compliance_framework/list.html:188, 198`
  - `templates/assets/assetcompliance/asset_compliance_audit/list.html:186, 196`
  - `templates/assets/assetcompliance/asset_compliance_incident/list.html:198, 208`
  - *Fix:* Append `&category={{ request.GET.category }}`, `&framework={{ request.GET.framework }}`, and `&agency={{ request.GET.agency }}` to pagination links.
- **M2: Falsy `0%` Fallback Bug in Framework KPI Calculation**
  - `apps/assets/views/AssetCompliance/AssetComplianceFrameworks.py:53`
  - *Fix:* Change to `round(avg_readiness if avg_readiness is not None else 100)`.
- **M3: Missing Date and Numeric Cross-Field Validations in Forms**
  - `apps/assets/forms/AssetCompliance/AssetPermitLicenses.py:47-50` (`expiration_date >= effective_date`)
  - `apps/assets/forms/AssetCompliance/AssetComplianceAudits.py:61-64` (`passed_checkpoints <= total_checkpoints`)
  - `apps/assets/forms/AssetCompliance/AssetComplianceIncidents.py:69-72` (`fine_paid <= fine_assessed`, require `fine_payment_date` if `fine_paid > 0`)
  - `apps/assets/models/AssetCompliance/AssetComplianceFrameworks.py:90` (`readiness_score` validators)
  - *Fix:* Add cross-field validation in form `clean()` methods.
- **M4: Unused Imports in View Modules**
  - `apps/assets/views/AssetCompliance/AssetComplianceFrameworks.py:12`
  - `apps/assets/views/AssetCompliance/AssetComplianceAudits.py:13`
  - `apps/assets/views/AssetCompliance/AssetPermitLicenses.py:15`
  - `apps/assets/views/AssetCompliance/AssetComplianceIncidents.py:14`
  - *Fix:* Remove unused `tenant_admin_required` import.
- **M5: Contract Drift on Helper Properties and View Context**
  - `apps/assets/models/AssetCompliance/AssetComplianceFrameworks.py`
  - `apps/assets/views/AssetCompliance/AssetComplianceFrameworks.py:80-96`
  - *Fix:* Add `is_active` and `is_audit_due` properties on `AssetComplianceFramework`, and include `incidents` in detail context.

---

## Pass 2: Contract Explorer (`explorer`)

### Critical
- **C1 / C2: Broken `write_audit_log` Call Signature Across All 17 View Call Sites** (Confirmed)
  - 6 positional arguments `(request.tenant, request.user, action, ModelName, pk, message)` passed instead of `(user, obj, action, changes=None, tenant=None)`. Raises `TypeError` on every POST action.

### Important
- **I1: Missing Filter `<select>` Elements in List Templates** (Confirmed)
  - `category_list`, `framework_list`, and `agency_list` context variables passed but `<select>` widgets omitted from list templates.
- **I2: User IDOR Validation Gap in Forms** (Confirmed)
  - `lead_auditor_user` and `assigned_investigator` need explicit tenant validation.
- **I3: Unhandled `ProtectedError` on Framework Deletion** (Confirmed)
  - Linked audits cause unhandled `ProtectedError` (HTTP 500) when deleting a framework.
- **I4: Seeder `--flush` Omission** (Confirmed)
  - `--flush` does not delete 11.11 records.

### Minor
- **M1: Missing Helper Properties on `AssetComplianceFramework` (`is_active`, `is_audit_due`)** (Confirmed)
- **M2: Missing `incidents` Context Key in Framework Detail View** (Confirmed)
- **M3: Pagination Links Drop Active FK Filters** (Confirmed)
- **M4: Average Readiness Score Falsy 0 Fallback Bug** (Confirmed)
- **M5: Unused `tenant_admin_required` Imports in Views** (Confirmed)

---

## Pass 3: Frontend Reviewer (`frontend-reviewer`)

### Critical
- *None.*

### Important
- **I1 / I3: Missing Filter `<select>` Elements and Pagination Drop in List Templates** (Confirmed)
  - `templates/assets/assetcompliance/asset_compliance_framework/list.html:52-82, 188, 198` (missing `<select name="category">` and `&category=`)
  - `templates/assets/assetcompliance/asset_compliance_audit/list.html:59-97, 186, 196` (missing `<select name="framework">` and `&framework=`)
  - `templates/assets/assetcompliance/asset_compliance_incident/list.html:59-97, 198, 208` (missing `<select name="agency">` and `&agency=`)

### Minor
- **M6: Guard Potential `None` in Expiration Days Comparison**
  - `templates/assets/assetcompliance/asset_permit_license/detail.html:152`
  - *Fix:* Use `{% if permit.days_to_expiration is not None and permit.days_to_expiration < 0 %}`.

---

## Pass 4: Performance Reviewer (`performance-reviewer`)

### Critical
- *None.* Zero N+1 regressions. Complete `select_related()` and `.defer()` on large text fields.

### Important
- **I5: Consolidate Multi-Query KPI Metrics in List Views**
  - `apps/assets/views/AssetCompliance/AssetComplianceFrameworks.py:49-54` (3 queries -> 1 single aggregate)
  - `apps/assets/views/AssetCompliance/AssetComplianceAudits.py:57-64` (4 queries -> 1 single aggregate)
  - `apps/assets/views/AssetCompliance/AssetPermitLicenses.py:57-68` (4 queries -> 1 single aggregate)
  - `apps/assets/views/AssetCompliance/AssetComplianceIncidents.py:60-75` (4 queries -> 1 single aggregate)
  - *Fix:* Use Django conditional aggregation `Count("id", filter=Q(...))` and `Sum(...)` to consolidate KPI metrics into 1 query per view.
- **I6: Add Composite Foreign-Key Indexes on Tenant-Scoped Models**
  - `AssetComplianceAudit`: `(tenant, framework)`, `(tenant, asset)`
  - `AssetComplianceIncident`: `(tenant, audit)`, `(tenant, permit)`
  - `AssetComplianceFramework`: `(tenant, applicable_category)`
  - *Fix:* Add composite `models.Index(fields=["tenant", "<fk>"])` to `Meta.indexes`.

### Minor
- **M7: Use `.only('id', 'name')` for Filter Dropdown QuerySets**
  - `apps/assets/views/AssetCompliance/AssetPermitLicenses.py:69`
  - *Fix:* Project only required fields for dropdown choices (`Party.objects.filter(...).only("id", "name")`).

---

## Pass 5: QA Smoke Tester (`qa-smoke-tester`)

### Critical
- **C1: All 17 POST Mutation Endpoints Crash with `TypeError` in `write_audit_log`** (Confirmed via 54 live tests)
  - All 17 create, edit, delete, and workflow POST action routes crash with `TypeError: write_audit_log() takes from 3 to 5 positional arguments but 6 were given`.
  - Verified: 16 GET views return 200 OK, zero comment leaks, 8 cross-tenant IDOR checks return 404, but all 17 POST actions 500.

### Important
- **I7: `TenantNumbered.save()` Masks Non-Null DB Integrity Errors as Sequence Collisions**
  - In `apps/assets/models/_base.py`, `save()` catches all `IntegrityError` exceptions, assuming duplicate `number`, retries 5 times, and raises misleading sequence collision error, masking genuine DB column nullability errors.

### Minor
- **M8: `AssetComplianceIncidentForm` Requires Fine Amounts Instead of Defaulting to 0.00**
  - Make `fine_assessed` and `fine_paid` default to `Decimal("0.00")` if left blank.

---
