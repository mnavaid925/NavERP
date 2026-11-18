# Review Findings: Sub-module 12.6 Supplier & Vendor Quality Management (`apps/quality/`)

**Target Range**: `585db911e9d93d64932a42f765dae39dbb5756a1...HEAD`  
**Date**: November 18, 2026  
**Status**: In Progress (Pass 1 of 6 completed)

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
   - Fix: Include `grade` in form or calculate standard defaults in `save()` if override values are blank.

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
