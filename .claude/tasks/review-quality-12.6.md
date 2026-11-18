# Review Findings: Sub-module 12.6 Supplier & Vendor Quality Management (`apps/quality/`)

**Target Range**: `585db911e9d93d64932a42f765dae39dbb5756a1...HEAD`  
**Date**: November 18, 2026  
**Status**: In Progress (Pass 4 of 6 completed)

---

## Pass 1: `code-reviewer` Findings

### Critical
*None.*

### Important
1. **CR-I1**: Unguarded nullable User Foreign Key lookups in templates (Lesson L10).
   - `templates/quality/supplierquality/supplier_qualification_audit/detail.html:124` (`audit.lead_auditor`)
   - `templates/quality/supplierquality/supplier_quality_scorecard/detail.html:214` (`scorecard.evaluated_by`)
   - `templates/quality/supplierquality/supplier_corrective_action/detail.html:236` (`scar.verified_by`)
   - `templates/quality/supplierquality/supplier_change_notification/detail.html:210` (`scn.approved_by`)
   - `templates/quality/supplierquality/supplier_change_notification/detail.html:279` (`scn.evaluated_by`)
   - Fix: Guard with `{% if obj.user_fk %}{{ obj.user_fk.get_full_name|default:obj.user_fk.email }}{% else %}—{% endif %}`.
2. **CR-I2**: Disallowed `badge-purple` theme CSS class (Lesson L33 violation).
   - `apps/quality/models/SupplierQuality/SupplierQualityScorecards.py:37` (`"annual": "badge-purple"`)
   - `apps/quality/models/SupplierQuality/SupplierCorrectiveActions.py:52` (`"effectiveness_verified": "badge-purple"`)
   - `templates/quality/supplierquality/supplier_change_notification/detail.html:184` (`<span class="badge badge-purple text-xs">`)
   - Fix: Change to standard theme.css badge classes (`badge-slate`, `badge-info`, or `badge-green`).
3. **CR-I3**: Manual override disconnect in `SupplierQualityScorecard` Form & Model.
   - `apps/quality/models/SupplierQuality/SupplierQualityScorecards.py:199-204`
   - `apps/quality/forms/SupplierQuality/SupplierQualityScorecards.py:17-35`
   - Fix: In `save()`, calculate standard defaults if override values are blank (`if not self.is_manual_override or self.overall_score is None: ...`).

### Minor
1. **CR-M1**: Context key `scns` passed in `supplier_qualification_audit_detail` view but omitted in template.
   - Fix: Add SCNs sub-table in `supplier_qualification_audit/detail.html`.
2. **CR-M2**: Missing filter bar dropdowns in list templates (`result` in audit list, `status` in scorecard list, `category` in SCAR list, `category`/`supplier` in SCN list).
   - Fix: Add corresponding `<select>` elements to list filter bars.
3. **CR-M3**: Unused `crud_*` imports in view files (`SupplierQualificationAudits.py`, `SupplierQualityScorecards.py`, `SupplierCorrectiveActions.py`, `SupplierChangeNotifications.py`).
   - Fix: Remove unused imports.
4. **CR-M4**: Non-standard `text-2xs` utility class in templates (`supplier_change_notification/list.html`, `supplier_corrective_action/list.html`, `supplier_corrective_action/detail.html`).
   - Fix: Replace with `text-xs`.
5. **CR-M5**: Inactive user selection allowed in form dropdowns (`lead_auditor`, `evaluated_by`, `verified_by`, `approved_by`).
   - Fix: Add `.filter(is_active=True)` to User querysets.

---

## Pass 2: `explorer` Findings

### Critical
*None.*

### Important
1. **EXP-I1**: Unguarded nullable user FK lookups in templates (corroborates CR-I1; L10 risk).
2. **EXP-I2**: Disallowed `badge-purple` theme CSS class (corroborates CR-I2; L33 violation).
3. **EXP-I3**: Disconnect between scorecard manual override and form exclusions (corroborates CR-I3; fallback calculation recommended in `save()`).

### Minor
1. **EXP-M1**: Context key `scns` passed in audit detail view but omitted in template (corroborates CR-M1).
2. **EXP-M2**: List filter bars omit choices handled in views/context (corroborates CR-M2).
3. **EXP-M3**: Inactive user selection allowed in form foreign keys (corroborates CR-M5).
4. **EXP-M4**: Non-standard `text-2xs` utility class in templates (corroborates CR-M4).
5. **EXP-M5**: Unused `crud_*` imports in view files (corroborates CR-M3).

---

## Pass 3: `frontend-reviewer` Findings

### Critical
1. **FE-C1**: Filter chaining logic bug in `supplier_corrective_action/detail.html:28` causes date to render blank:
   `{{ scar.issued_date|date:"Y-m-d"|default:scar.created_at|date:"Y-m-d" }}` passes already-formatted string into second `|date`, yielding `""`.
   - Fix: `{% if scar.issued_date %}{{ scar.issued_date|date:"Y-m-d" }}{% else %}{{ scar.created_at|date:"Y-m-d" }}{% endif %}`.
2. **FE-C2**: None-unsafe user FK attribute lookups without `{% if %}` guard (Lesson L10).
   - `supplier_qualification_audit/detail.html:124` (`audit.lead_auditor`)
   - `supplier_quality_scorecard/detail.html:214` (`scorecard.evaluated_by`)
   - `supplier_corrective_action/detail.html:236` (`scar.verified_by`)
   - `supplier_change_notification/detail.html:210` (`scn.approved_by`)
   - `supplier_change_notification/detail.html:279` (`scn.evaluated_by`)
   - Fix: Wrap each with `{% if fk %}...{% else %}Not Assigned{% endif %}`.

### Important
1. **FE-I1**: Undefined badge class `badge-purple` in `supplier_change_notification/detail.html:184` (Lesson L33).
   - Fix: Replace with `badge-info`.
2. **FE-I2**: Non-existent CSS class `text-2xs` in `supplier_corrective_action/{list,detail}.html` and `supplier_change_notification/list.html`.
   - Fix: Replace with `text-xs`.

### Minor
1. **FE-M1**: Unsurfaced filter options in SCAR and SCN list filter bars (corroborates CR-M2 and EXP-M2).

---

## Pass 4: `performance-reviewer` Findings

### Critical
*None.*

### Important
1. **PRF-I1**: Multiple isolated `.count()` queries on AVL directory stat cards instead of consolidated aggregate.
   - `apps/quality/views/SupplierQuality/SupplierQualityDirectory.py:20-23`
   - Fix: Consolidate into single `.aggregate(Count(..., filter=Q(...)))` query.
2. **PRF-I2**: Missing compound index for default ordering on `SupplierQualityScorecard`.
   - `apps/quality/models/SupplierQuality/SupplierQualityScorecards.py:138`
   - Fix: Add index `["tenant", "-period_end", "-created_at"]` in `Meta.indexes`.

### Minor
1. **PRF-M1**: Supplier filter dropdowns issue 2 queries (`exists()` + wide row fetch).
   - Fix: Materialize with `.only("id", "name")` into a list once.
2. **PRF-M2**: Over-eager `select_related` in list views (unused FKs joined on list tables).
   - Fix: Limit list views to `.select_related("supplier")`.
3. **PRF-M3**: Missing composite index for `(tenant, dock_to_stock_eligible)` on `SupplierQualificationAudit`.



