# Review Findings: Sub-module 12.6 Supplier & Vendor Quality Management (`apps/quality/`)

**Target Range**: `585db911e9d93d64932a42f765dae39dbb5756a1...HEAD`  
**Date**: November 18, 2026  
**Status**: Deduplicated & Prioritized (Ready for Phase 5 `code-fixer`)  
**Passes Completed**: 6 of 6 (`code-reviewer`, `explorer`, `frontend-reviewer`, `performance-reviewer`, `qa-smoke-tester`, `security-reviewer`)

---

## Consolidated & Prioritized Action Items

### Critical (Must Fix Immediately)

- [x] **C1**: Filter chaining logic bug in `supplier_corrective_action/detail.html:28` causes date to render blank.
  - **Location**: `templates/quality/supplierquality/supplier_corrective_action/detail.html:28`
  - **Problem**: `{{ scar.issued_date|date:"Y-m-d"|default:scar.created_at|date:"Y-m-d" }}` passes already-formatted string into second `|date`, returning empty string `""`.
  - **Fix**: Use `{% if scar.issued_date %}{{ scar.issued_date|date:"Y-m-d" }}{% else %}{{ scar.created_at|date:"Y-m-d" }}{% endif %}`.

---

### Important (High Priority / Conventions & Safety)

- [x] **I1**: Unguarded nullable User Foreign Key lookups in templates (Lesson L10).
  - **Locations**:
    - `templates/quality/supplierquality/supplier_qualification_audit/detail.html:124` (`audit.lead_auditor`)
    - `templates/quality/supplierquality/supplier_quality_scorecard/detail.html:214` (`scorecard.evaluated_by`)
    - `templates/quality/supplierquality/supplier_corrective_action/detail.html:236` (`scar.verified_by`)
    - `templates/quality/supplierquality/supplier_change_notification/detail.html:210` (`scn.approved_by`)
    - `templates/quality/supplierquality/supplier_change_notification/detail.html:279` (`scn.evaluated_by`)
  - **Fix**: Wrap with `{% if fk %}{{ fk.get_full_name|default:fk.email }}{% else %}Not Assigned{% endif %}`.

- [x] **I2**: Disallowed `badge-purple` theme CSS class (Lesson L33 violation).
  - **Locations**:
    - `apps/quality/models/SupplierQuality/SupplierQualityScorecards.py:37` (`"annual": "badge-purple"`)
    - `apps/quality/models/SupplierQuality/SupplierCorrectiveActions.py:52` (`"effectiveness_verified": "badge-purple"`)
    - `templates/quality/supplierquality/supplier_change_notification/detail.html:184` (`<span class="badge badge-purple text-xs">`)
  - **Fix**: Change to standard theme.css badge classes (`badge-slate`, `badge-info`, or `badge-green`).

- [x] **I3**: Manual override disconnect in `SupplierQualityScorecard` Form & Model.
  - **Locations**:
    - `apps/quality/models/SupplierQuality/SupplierQualityScorecards.py:199-204`
  - **Fix**: In `save()`, if `is_manual_override=True` but `overall_score is None`, calculate default composite score as baseline fallback.

- [x] **I4**: SCN disposition bypass & mass assignment in `SupplierChangeNotificationForm`.
  - **Locations**:
    - `apps/quality/forms/SupplierQuality/SupplierChangeNotifications.py:42-45`
    - `templates/quality/supplierquality/supplier_change_notification/form.html:132-160`
  - **Fix**: Exclude `"disposition"`, `"approved_by"`, `"disposition_notes"` from form `Meta.fields` and form template so disposition is governed exclusively by the `@tenant_admin_required` action view.

- [x] **I5**: Privileged status transition bypass via CRUD edit forms.
  - **Locations**:
    - `apps/quality/forms/SupplierQuality/SupplierQualityScorecards.py:22` (`status`)
    - `apps/quality/forms/SupplierQuality/SupplierCorrectiveActions.py:26` (`status`)
  - **Fix**: Restrict selectable choices in forms so `"published"` and `"closed"` transitions are performed via dedicated workflow action views.

- [x] **I6**: Delete endpoints lack `@tenant_admin_required`.
  - **Locations**:
    - `apps/quality/views/SupplierQuality/SupplierQualificationAudits.py:171`
    - `apps/quality/views/SupplierQuality/SupplierQualityScorecards.py:163`
    - `apps/quality/views/SupplierQuality/SupplierCorrectiveActions.py:172`
    - `apps/quality/views/SupplierQuality/SupplierChangeNotifications.py:173`
  - **Fix**: Add `@tenant_admin_required` decorator to all delete views.

- [x] **I7**: Multiple isolated `.count()` queries on AVL directory stat cards.
  - **Location**: `apps/quality/views/SupplierQuality/SupplierQualityDirectory.py:20-23`
  - **Fix**: Consolidate the 4 `.count()` queries into a single `.aggregate(Count(..., filter=Q(...)))`.

- [x] **I8**: Missing compound index for default ordering on `SupplierQualityScorecard`.
  - **Location**: `apps/quality/models/SupplierQuality/SupplierQualityScorecards.py:147-154`
  - **Fix**: Add `models.Index(fields=["tenant", "-period_end", "-created_at"], name="idx_qssc_ten_pend_created")` in `Meta.indexes`.

---

### Minor (Polish & Hygiene)

- [x] **M1**: Context key `scns` passed in `supplier_qualification_audit_detail` view but omitted in template.
  - **Location**: `templates/quality/supplierquality/supplier_qualification_audit/detail.html`
  - **Fix**: Add SCNs sub-table below SCARs sub-table.

- [x] **M2**: Missing filter bar dropdowns in list templates.
  - **Locations**:
    - `templates/quality/supplierquality/supplier_qualification_audit/list.html` (add `result` dropdown)
    - `templates/quality/supplierquality/supplier_quality_scorecard/list.html` (add `status` dropdown)
    - `templates/quality/supplierquality/supplier_corrective_action/list.html` (add `category` dropdown)
    - `templates/quality/supplierquality/supplier_change_notification/list.html` (add `category` and `supplier` dropdowns)
  - **Fix**: Add `<select>` elements to filter forms.

- [x] **M3**: Unused `crud_*` imports in view files.
  - **Locations**:
    - `apps/quality/views/SupplierQuality/SupplierQualificationAudits.py:11`
    - `apps/quality/views/SupplierQuality/SupplierQualityScorecards.py:11`
    - `apps/quality/views/SupplierQuality/SupplierCorrectiveActions.py:12`
    - `apps/quality/views/SupplierQuality/SupplierChangeNotifications.py:12`
  - **Fix**: Remove unused import statements.

- [x] **M4**: Non-standard `text-2xs` utility class in templates.
  - **Locations**:
    - `templates/quality/supplierquality/supplier_corrective_action/list.html:144, 153`
    - `templates/quality/supplierquality/supplier_corrective_action/detail.html:57`
    - `templates/quality/supplierquality/supplier_change_notification/list.html:146, 148`
  - **Fix**: Replace with `text-xs`.

- [x] **M5**: Inactive user selection allowed in form dropdowns.
  - **Locations**:
    - `apps/quality/forms/SupplierQuality/SupplierQualificationAudits.py:74`
    - `apps/quality/forms/SupplierQuality/SupplierQualityScorecards.py:65`
    - `apps/quality/forms/SupplierQuality/SupplierCorrectiveActions.py:108`
    - `apps/quality/forms/SupplierQuality/SupplierChangeNotifications.py:89`
  - **Fix**: Add `.filter(is_active=True)` to User querysets.

- [ ] **M6**: Optimize supplier filter dropdown population with `.only("id", "name")`.
  - **Locations**: List views in `SupplierQualificationAudits.py`, `SupplierQualityScorecards.py`, `SupplierCorrectiveActions.py`, `SupplierChangeNotifications.py`.
  - **Fix**: Materialize list once with `.only("id", "name")`.

- [ ] **M7**: Over-eager `select_related` in list views.
  - **Locations**: List views in all 4 view files.
  - **Fix**: Limit list views to `.select_related("supplier")`.

- [ ] **M8**: Privileged action forms rendered to non-admin users in detail templates.
  - **Locations**: Detail templates across the 4 entities.
  - **Fix**: Wrap administrative action cards in `{% if request.user.is_superuser or request.user.is_tenant_admin %}`.

- [ ] **M9**: Whitespace-stripping defense-in-depth for formula injection in `_csv_safe`.
  - **Locations**: All 4 view files `_csv_safe` helper.
  - **Fix**: Use `s.lstrip().startswith(("=", "+", "-", "@", "\t", "\r"))`.
