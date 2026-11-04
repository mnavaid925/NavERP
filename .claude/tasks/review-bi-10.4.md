# Review Findings — Sub-module 10.4: Data Modeling & Semantic Layer (Module 10 — Business Intelligence, `bi`)

- **Sub-module:** 10.4 Data Modeling & Semantic Layer
- **Module:** 10 Business Intelligence
- **Target app:** `apps/bi`
- **Review date:** 2026-11-04
- **Base SHA:** `069fb344d5ed505ef7ef4373b47d5ed6938ce6ed`
- **Status:** In Progress (Pass 2/6 complete)

---

## Pass 1: code-reviewer Findings

### Critical
- **[CRIT-1]** `write_audit_log` parameter mismatch and delete-after-call bug across all 15 views:
  - `apps/bi/views/SemanticLayer/SemanticModels.py:L134, L161, L191, L218, L254`
  - `apps/bi/views/SemanticLayer/BusinessGlossaryTerms.py:L112, L139, L169, L196`
  - `apps/bi/views/SemanticLayer/CalculatedMeasures.py:L109, L136, L167`
  - `apps/bi/views/SemanticLayer/DrillHierarchies.py:L98, L125, L155`
  - `write_audit_log` signature is `(user, obj, action, changes=None, tenant=None)` but called with `(request.tenant, request.user, "<action>", "<Model>", pk, message)`, which throws `TypeError` on every mutating POST. Also on delete views, it is called after `instance.delete()`. Fix: pass `(request.user, instance, "<action>", tenant=request.tenant)` and call before `delete()`.

### Important
- **[IMP-1]** Unscoped user queries in `owner` and `steward` form fields:
  - `apps/bi/forms/SemanticLayer/SemanticModels.py:L58, L62`
  - `apps/bi/forms/SemanticLayer/BusinessGlossaryTerms.py:L47, L56`
  - `owner` and `steward` fields query `User.objects.filter(is_active=True)` without tenant scoping, leaking users across tenants and allowing cross-tenant assignment. Fix: filter `tenant=self.tenant` and include in `reject_foreign`.
- **[IMP-2]** Missing filters and pagination parameter loss in list templates and non-integer FK param crash:
  - `templates/bi/semantic_layer/semantic_model/list.html` missing `scd_type` dropdown; pagination drops `scd_type` and `is_active`.
  - `templates/bi/semantic_layer/calculated_measure/list.html` missing `time_intelligence` dropdown; pagination drops `time_intelligence` and `is_active`.
  - `templates/bi/semantic_layer/business_glossary_term/list.html` and `drill_hierarchy/list.html` pagination drops `is_active`.
  - Views query `data_mart_id=mart_filter` and `semantic_model_id=model_filter` without checking `.isdigit()`. Fix: add missing filters, update pagination query params, and guard with `.isdigit()`.
- **[IMP-3]** Stale certification metadata when uncertifying:
  - `apps/bi/views/SemanticLayer/SemanticModels.py:L214-L217`
  - `apps/bi/views/SemanticLayer/BusinessGlossaryTerms.py:L192-L195`
  - Transitioning from `certified` to `draft`, `in_review`, or `deprecated` does not clear `certified_by` or `certified_at`. Fix: set them to `None` when `new_status != 'certified'`.
- **[IMP-4]** Virtual view without SQL validation:
  - `apps/bi/forms/SemanticLayer/SemanticModels.py:L60-L63`
  - When `is_virtual_view` is checked, `sql_definition` can be empty. Fix: require `sql_definition` in `clean()` when `is_virtual_view` is true.

### Minor
- **[MIN-1]** Unstyled `.badge-purple` used in templates:
  - `templates/bi/semantic_layer/semantic_model/list.html:L129`
  - `templates/bi/semantic_layer/business_glossary_term/list.html:L121`
  - `templates/bi/semantic_layer/drill_hierarchy/list.html:L123`
  - Theme CSS only defines green, red, amber, info, muted, slate. Fix: use `badge-info` or `badge-slate`.
- **[MIN-2]** Unused import `tenant_admin_required`:
  - `apps/bi/views/SemanticLayer/SemanticModels.py:L20`
  - Fix: remove unused import.
- **[MIN-3]** Unused variable `model_pk` before redirect:
  - `apps/bi/views/SemanticLayer/CalculatedMeasures.py:L165`
  - Fix: remove unused variable.
- **[MIN-4]** Introspection does not override default surrogate key "id":
  - `apps/bi/views/SemanticLayer/SemanticModels.py:L247`
  - Fix: `if (not model.primary_key_column or model.primary_key_column == "id") and table.primary_key_column:`.
- **[MIN-5]** `Command.help` in `seed_bi.py` omits 10.4:
  - `apps/bi/management/commands/seed_bi.py:L28`
  - Fix: update help string.
- **[MIN-6]** Raw underscores in overview distribution cards:
  - `templates/bi/semantic_layer/semantic_overview.html:L288, L307`
  - Fix: format labels cleanly.

---

## Pass 2: explorer Findings

### Critical
- **[EXP-CRIT-1]** `write_audit_log` parameter mismatch & post-delete invocation across all 15 mutating views:
  - `apps/bi/views/SemanticLayer/SemanticModels.py:L134, L161, L191, L218, L254`
  - `apps/bi/views/SemanticLayer/BusinessGlossaryTerms.py:L112, L139, L169, L196`
  - `apps/bi/views/SemanticLayer/CalculatedMeasures.py:L109, L136, L167`
  - `apps/bi/views/SemanticLayer/DrillHierarchies.py:L98, L125, L155`
  - Positional argument mismatch throws TypeError on mutate. On delete views, called after `instance.delete()`. Fix: `write_audit_log(request.user, instance, "<action>", tenant=request.tenant)` called before deletion.

### Important
- **[EXP-IMP-1]** Unscoped user queries and missing `reject_foreign` for user fields in forms:
  - `apps/bi/forms/SemanticLayer/SemanticModels.py:L58, L62`
  - `apps/bi/forms/SemanticLayer/BusinessGlossaryTerms.py:L47, L56`
  - Cross-tenant user assignment vulnerability. Fix: scope querysets to `tenant=self.tenant` and reject foreign values.
- **[EXP-IMP-2]** Missing filter dropdowns in list templates & query parameter loss in pagination:
  - `templates/bi/semantic_layer/semantic_model/list.html:L41`: missing `scd_type` filter dropdown.
  - `templates/bi/semantic_layer/calculated_measure/list.html:L41`: missing `time_intelligence` filter dropdown.
  - Pagination links drop `scd_type`, `time_intelligence`, and `is_active` query parameters.
- **[EXP-IMP-3]** Non-integer FK query parameters crash list views with unhandled `ValueError`:
  - `apps/bi/views/SemanticLayer/SemanticModels.py:L53` (`data_mart_id=mart_filter`)
  - `apps/bi/views/SemanticLayer/CalculatedMeasures.py:L51` (`semantic_model_id=model_filter`)
  - `apps/bi/views/SemanticLayer/DrillHierarchies.py:L47` (`semantic_model_id=model_filter`)
  - Fix: guard with `.isdigit()`.
- **[EXP-IMP-4]** Missing SQL validation when `is_virtual_view` is true:
  - `apps/bi/forms/SemanticLayer/SemanticModels.py:L60`
  - Virtual views can be saved with empty `sql_definition`. Fix: validate `sql_definition` presence in `clean()`.
- **[EXP-IMP-5]** Stale certification metadata retained on status transition:
  - `apps/bi/views/SemanticLayer/SemanticModels.py:L214-L217`
  - `apps/bi/views/SemanticLayer/BusinessGlossaryTerms.py:L192-L195`
  - Transitioning out of `certified` leaves `certified_by` and `certified_at` populated. Fix: clear fields if `new_status != 'certified'`.

### Minor
- **[EXP-MIN-1]** Inconsistent file naming across `forms/` and `views/` packages:
  - `apps/bi/forms/SemanticLayer/CalculatedMeasureForms.py` and `DrillHierarchyForms.py` use plural `Forms.py` suffix, while models and views use plural entity names (`CalculatedMeasures.py`, `DrillHierarchies.py`).
- **[EXP-MIN-2]** Inaccurate fallback label in `semantic_overview.html`:
  - `templates/bi/semantic_layer/semantic_overview.html:L187`: displays "Virtual View" if `warehouse_table` is empty, even when `is_virtual_view` is false.
- **[EXP-MIN-3]** Unsupported CSS class `.badge-purple`:
  - `semantic_model/list.html`, `business_glossary_term/list.html`, `drill_hierarchy/list.html`. Replace with `badge-info` or `badge-slate`.
- **[EXP-MIN-4]** Unused import and dead local variable:
  - `tenant_admin_required` in `SemanticModels.py:L20` and `model_pk` in `CalculatedMeasures.py:L165`.
- **[EXP-MIN-5]** Introspection surrogate key override logic:
  - `apps/bi/views/SemanticLayer/SemanticModels.py:L247`.
