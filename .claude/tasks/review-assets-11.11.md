# Sub-module 11.11 Consolidated Review Findings — Compliance & Regulatory Management

- **Base SHA:** `af494e50b130876319671d67c7a39fa5ed1b9188`
- **Scope:** NavERP Sub-module 11.11 (`apps/assets/` and `templates/assets/assetcompliance/`)
- **Models:** `AssetComplianceFramework`, `AssetComplianceAudit`, `AssetPermitLicense`, `AssetComplianceIncident`
- **Review Passes:** 6 serial passes completed (`code-reviewer`, `explorer`, `frontend-reviewer`, `performance-reviewer`, `qa-smoke-tester`, `security-reviewer`)

---

## Action Item Register

### Critical

- [x] **C1: Broken `write_audit_log` Call Signature Across All 17 View Call Sites (HTTP 500 on all POST actions)**
  - **Files**:
    - `apps/assets/views/AssetCompliance/AssetComplianceFrameworks.py:106, 137, 168`
    - `apps/assets/views/AssetCompliance/AssetComplianceAudits.py:118, 153, 183, 202, 224`
    - `apps/assets/views/AssetCompliance/AssetPermitLicenses.py:121, 156, 187, 205`
    - `apps/assets/views/AssetCompliance/AssetComplianceIncidents.py:134, 175, 205, 226, 250`
  - **Issue**: Views call `write_audit_log(request.tenant, request.user, action, ModelName, pk, message)` (6 arguments) instead of `write_audit_log(user, obj, action, changes=None, tenant=None)`. Causes `TypeError` / HTTP 500 on every create, edit, delete, and workflow transition.
  - **Fix**: Update all 17 call sites to pass `write_audit_log(request.user, instance, action, changes=..., tenant=request.tenant)`.

- [x] **C2: Missing User Foreign-Key Scoping in Form `reject_foreign` (Cross-Tenant IDOR Risk)**
  - **Files**:
    - `apps/assets/forms/AssetCompliance/AssetComplianceAudits.py:63` (`lead_auditor_user`)
    - `apps/assets/forms/AssetCompliance/AssetComplianceIncidents.py:71` (`assigned_investigator`)
  - **Issue**: `reject_foreign` checks Party and Asset, but omits User foreign keys. Users from other workspaces could be assigned via manipulated POST requests.
  - **Fix**: Include `"lead_auditor_user"` in `AssetComplianceAuditForm.clean()` and `"assigned_investigator"` in `AssetComplianceIncidentForm.clean()`.

---

### Important

- [x] **I1: Missing Filter `<select>` Elements in List Templates**
  - **Files**:
    - `templates/assets/assetcompliance/asset_compliance_framework/list.html:52-82` (missing `<select name="category">`)
    - `templates/assets/assetcompliance/asset_compliance_audit/list.html:59-97` (missing `<select name="framework">`)
    - `templates/assets/assetcompliance/asset_compliance_incident/list.html:59-97` (missing `<select name="agency">`)
  - **Issue**: Views pass `category_list`, `framework_list`, and `agency_list` in context, but the template filter forms lack the respective dropdown inputs.
  - **Fix**: Add the missing `<select>` elements with `pk|stringformat:"d"` comparison.

- [x] **I2: Pagination Links Drop Active Foreign Key Query Parameters**
  - **Files**:
    - `templates/assets/assetcompliance/asset_compliance_framework/list.html:188, 198` (`category`)
    - `templates/assets/assetcompliance/asset_compliance_audit/list.html:186, 196` (`framework`)
    - `templates/assets/assetcompliance/asset_compliance_incident/list.html:198, 208` (`agency`)
  - **Issue**: Prev/Next pagination links drop the foreign key filter parameters when navigating across pages.
  - **Fix**: Append `{% if request.GET.<param> %}&<param>={{ request.GET.<param> }}{% endif %}` to pagination links.

- [x] **I3: Unhandled `ProtectedError` on Compliance Framework Deletion**
  - **Files**:
    - `apps/assets/views/AssetCompliance/AssetComplianceFrameworks.py:163-177`
  - **Issue**: `AssetComplianceAudit.framework` uses `on_delete=models.PROTECT`. Deleting a framework with audits causes an unhandled `ProtectedError` (HTTP 500).
  - **Fix**: Wrap `framework.delete()` in `try...except ProtectedError`, set user-friendly error message, and redirect to detail page.

- [x] **I4: Seeder `--flush` Omission Leaves 11.11 Records in Database**
  - **Files**:
    - `apps/assets/management/commands/seed_assets.py:75-109`
  - **Issue**: `--flush` deletes models from 11.1-11.10 but does not purge 11.11 compliance models.
  - **Fix**: Add deletion calls in reverse dependency order for `AssetComplianceIncident`, `AssetPermitLicense`, `AssetComplianceAudit`, and `AssetComplianceFramework`.

- [x] **I5: Status Guards Missing on Destructive / Modification View Endpoints**
  - **Files**:
    - `apps/assets/views/AssetCompliance/AssetComplianceAudits.py:147-193`
    - `apps/assets/views/AssetCompliance/AssetComplianceIncidents.py:169-215`
    - `apps/assets/views/AssetCompliance/AssetPermitLicenses.py:201-215`
  - **Issue**: Completed audits, settled incidents with assessed fines, and revoked/suspended permits lack status guards in view logic on delete/edit/renew.
  - **Fix**: Add view-level status validation guards preventing modification or deletion of completed audits and settled incidents with fines, and blocking renewal of revoked/suspended permits.

- [x] **I6: Missing `@tenant_admin_required` on Delete Views**
  - **Files**:
    - `apps/assets/views/AssetCompliance/AssetComplianceFrameworks.py:161`
    - `apps/assets/views/AssetCompliance/AssetComplianceAudits.py:177`
    - `apps/assets/views/AssetCompliance/AssetPermitLicenses.py:180`
    - `apps/assets/views/AssetCompliance/AssetComplianceIncidents.py:199`
  - **Issue**: Delete actions handle statutory regulatory records but do not require tenant admin role.
  - **Fix**: Apply `@tenant_admin_required` decorator to all four delete views.

- [x] **I7: Form `status` Mass Assignment Bypassing Workflow State Machines**
  - **Files**:
    - `apps/assets/forms/AssetCompliance/AssetComplianceAudits.py:32`
    - `apps/assets/forms/AssetCompliance/AssetComplianceIncidents.py:36`
  - **Issue**: `status` is included in `Meta.fields` of edit forms, allowing users to bypass dedicated transition endpoints (`complete`, `resolve`, `close`) and their timestamp tracking.
  - **Fix**: Exclude `status` from `AssetComplianceAuditForm` and `AssetComplianceIncidentForm`, or restrict form choices to pre-completion statuses.

- [x] **I8: Consolidate Multi-Query KPI Metrics in List Views**
  - **Files**:
    - `apps/assets/views/AssetCompliance/AssetComplianceFrameworks.py:49-54`
    - `apps/assets/views/AssetCompliance/AssetComplianceAudits.py:57-64`
    - `apps/assets/views/AssetCompliance/AssetPermitLicenses.py:57-68`
    - `apps/assets/views/AssetCompliance/AssetComplianceIncidents.py:60-75`
  - **Issue**: List views execute 3-4 separate SQL count/aggregate queries instead of 1 combined aggregate.
  - **Fix**: Consolidate queries into a single `.aggregate(Count(..., filter=Q(...)), Sum(...))` call per view.

---

### Minor

- [x] **M1: Falsy `0%` Fallback Bug in Framework Readiness Score**
  - **File**: `apps/assets/views/AssetCompliance/AssetComplianceFrameworks.py:53`
  - **Fix**: Change to `round(avg_readiness if avg_readiness is not None else 100)`.

- [x] **M2: Missing Helper Properties on `AssetComplianceFramework`**
  - **File**: `apps/assets/models/AssetCompliance/AssetComplianceFrameworks.py`
  - **Fix**: Add `@property def is_active(self): return self.status == "active"` and `is_audit_due` property.

- [x] **M3: Missing `incidents` in Framework Detail View Context**
  - **File**: `apps/assets/views/AssetCompliance/AssetComplianceFrameworks.py:80-96`
  - **Fix**: Include linked incidents via `AssetComplianceIncident.objects.filter(tenant=request.tenant, audit__framework=framework)[:10]` in detail context.

- [x] **M4: Form Numeric and Date Boundary Validations**
  - **Files**:
    - `apps/assets/forms/AssetCompliance/AssetPermitLicenses.py` (`expiration_date >= effective_date`)
    - `apps/assets/forms/AssetCompliance/AssetComplianceAudits.py` (`passed_checkpoints <= total_checkpoints`)
    - `apps/assets/forms/AssetCompliance/AssetComplianceIncidents.py` (`fine_paid <= fine_assessed`)
  - **Fix**: Add validation logic in form `clean()` methods.

- [x] **M5: None-Safe Comparison in Permit Detail Template**
  - **File**: `templates/assets/assetcompliance/asset_permit_license/detail.html:152`
  - **Fix**: Guard with `{% if permit.days_to_expiration is not None and permit.days_to_expiration < 0 %}`.

- [x] **M6: Model Index Optimization on High-Traffic Foreign Keys**
  - **Files**: Models under `apps/assets/models/AssetCompliance/`
  - **Fix**: Add composite indexes on `(tenant, framework)` and `(tenant, applicable_category)` where needed.

- [x] **M7: Unused `tenant_admin_required` Import Cleanup**
  - **Files**: All 4 view files in `apps/assets/views/AssetCompliance/`
  - **Fix**: Use the decorator for delete views (resolving I6 and M7 together).

- [x] **M8: Incident Form Fine Field Defaults**
  - **File**: `apps/assets/forms/AssetCompliance/AssetComplianceIncidents.py`
  - **Fix**: Default `fine_assessed` and `fine_paid` to `Decimal("0.00")` if left blank.

---
