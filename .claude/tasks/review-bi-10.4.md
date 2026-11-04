# Review Findings — Sub-module 10.4: Data Modeling & Semantic Layer (Module 10 — Business Intelligence, `bi`)

- **Sub-module:** 10.4 Data Modeling & Semantic Layer
- **Module:** 10 Business Intelligence
- **Target app:** `apps/bi`
- **Review date:** 2026-11-04
- **Base SHA:** `069fb344d5ed505ef7ef4373b47d5ed6938ce6ed`
- **Status:** In Progress (Pass 5/6 complete)

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

---

## Pass 3: frontend-reviewer Findings

### Important
- **[FE-IMP-1]** Unstyled `badge-purple` used across multiple list templates (L33 Theme.css color system violation):
  - `templates/bi/semantic_layer/semantic_model/list.html:129`
  - `templates/bi/semantic_layer/business_glossary_term/list.html:121`
  - `templates/bi/semantic_layer/drill_hierarchy/list.html:123`
  - Fix: Replace `badge-purple` with `badge-info` (the indigo/purple theme hue) or `badge-slate`.
- **[FE-IMP-2]** Detail templates missing "Back to List" button in `.page-actions`:
  - `templates/bi/semantic_layer/semantic_model/detail.html:39-68`
  - `templates/bi/semantic_layer/business_glossary_term/detail.html:39-55`
  - `templates/bi/semantic_layer/calculated_measure/detail.html:32-48`
  - `templates/bi/semantic_layer/drill_hierarchy/detail.html:32-48`
  - Fix: Add standard `<a href="..." class="btn btn-outline"><i data-lucide="arrow-left"></i><span>Back to ...</span></a>` action button.
- **[FE-IMP-3]** Overview certification status badge lacks 'deprecated' branch and fallback:
  - `templates/bi/semantic_layer/semantic_overview.html:190-196`
  - Fix: Handle `deprecated` (`badge-red`) and fallback to `{{ sm.get_certification_status_display }}`.
- **[FE-IMP-4]** Missing `aria-label` on icon-only buttons across templates:
  - `templates/bi/semantic_layer/semantic_overview.html:199,259`
  - `templates/bi/semantic_layer/semantic_model/list.html:80,184,187,192`
  - `templates/bi/semantic_layer/semantic_model/detail.html:210,213,280,283`
  - `templates/bi/semantic_layer/business_glossary_term/list.html:71,158,161,166`
  - `templates/bi/semantic_layer/business_glossary_term/detail.html:153`
  - `templates/bi/semantic_layer/calculated_measure/list.html:71,156,159,164`
  - `templates/bi/semantic_layer/drill_hierarchy/list.html:71,146,149,154`
  - Fix: Add descriptive `aria-label` attributes to all icon-only buttons.

### Minor
- **[FE-MIN-1]** Missing `for` and `id` associations on list filter inputs and detail inline forms:
  - `templates/bi/semantic_layer/semantic_model/list.html:43,47,56,65`
  - `templates/bi/semantic_layer/business_glossary_term/list.html:43,47,56`
  - `templates/bi/semantic_layer/calculated_measure/list.html:43,47,56`
  - `templates/bi/semantic_layer/drill_hierarchy/list.html:43,47,56`
  - `templates/bi/semantic_layer/semantic_model/detail.html:348,352`
  - `templates/bi/semantic_layer/business_glossary_term/detail.html:235,239`
  - Fix: Add `id` attributes to filter inputs and pair them with `for="..."` on `<label>`. On detail forms, use `for="{{ certify_form.<field>.id_for_label }}"`.
- **[FE-MIN-2]** None-safe method calls on nullable Foreign Keys:
  - `templates/bi/semantic_layer/semantic_model/detail.html:400`
  - `templates/bi/semantic_layer/business_glossary_term/list.html:131`
  - `templates/bi/semantic_layer/business_glossary_term/detail.html:259`
  - Fix: Wrap with explicit `{% if model.owner %}...{% else %}Unassigned{% endif %}` check (rule L10).

---

## Pass 4: performance-reviewer Findings

### Critical
- **[PERF-CRIT-1]** Missing Compound Foreign Key Index for Reverse Lookup on `CalculatedMeasure` (`tenant`, `glossary_term`):
  - `apps/bi/models/SemanticLayer/CalculatedMeasures.py:135-138`
  - In `business_glossary_term_detail`, reverse query filters by `(tenant, glossary_term)`. Missing compound index forces sequential table scan across tenant records.
  - Fix: Add `models.Index(fields=["tenant", "glossary_term"], name="idx_bcms_ten_glossary")` to `CalculatedMeasure.Meta.indexes`.

### Important
- **[PERF-IMP-1]** Missing Compound Indexes for Ordering & Filtering on `SemanticModel` and `BusinessGlossaryTerm`:
  - `apps/bi/models/SemanticLayer/SemanticModels.py:139-144`: missing `["tenant", "-created_at"]` (`idx_bsmd_ten_created`) and `["tenant", "data_mart"]` (`idx_bsmd_ten_mart`).
  - `apps/bi/models/SemanticLayer/BusinessGlossaryTerms.py:103-107`: missing `["tenant", "domain_category", "name"]` (`idx_bglo_ten_domain_name`).
  - Fix: Add these indexes to Meta.indexes and generate migration.
- **[PERF-IMP-2]** Unnecessary Double-Join Cartesian Product in `semantic_model_list`:
  - `apps/bi/views/SemanticLayer/SemanticModels.py:29-32`
  - `hierarchy_count=Count("drill_hierarchies", distinct=True)` forces extra table join and cartesian expansion, but is never rendered in list template.
  - Fix: Remove `hierarchy_count` from `annotate()`.
- **[PERF-IMP-3]** Unused M2M `prefetch_related("related_terms")` on Glossary List View:
  - `apps/bi/views/SemanticLayer/BusinessGlossaryTerms.py:23`
  - Executes extra SQL query per list view request for a field not rendered in list template.
  - Fix: Remove `.prefetch_related("related_terms")` from glossary list view.
- **[PERF-IMP-4]** Duplicate Query Triggered by `{{ queryset.count }}` in Template Header Before Table Loop:
  - `templates/bi/semantic_layer/semantic_model/detail.html:154, 234` & `apps/bi/views/SemanticLayer/SemanticModels.py:103-104`
  - `templates/bi/semantic_layer/business_glossary_term/detail.html:110` & `apps/bi/views/SemanticLayer/BusinessGlossaryTerms.py:82`
  - Calling `.count` then `{% for %}` fires COUNT(*) then SELECT.
  - Fix: Evaluate to `list()` in view, use `{{ measures|length }}` in template.
- **[PERF-IMP-5]** Six Sequential `.count()` Queries in `semantic_overview` Instead of Conditional Aggregation:
  - `apps/bi/views/SemanticLayer/SemanticOverviewViews.py:19-24`
  - Fix: Combine total and certified counts with `Count("id", filter=Q(certification_status="certified"))`.
- **[PERF-IMP-6]** Non-standard Pagination Page Size (25 instead of 15) Across All Four List Views:
  - `apps/bi/views/SemanticLayer/SemanticModels.py:69`
  - `apps/bi/views/SemanticLayer/BusinessGlossaryTerms.py:53`
  - `apps/bi/views/SemanticLayer/CalculatedMeasures.py:52`
  - `apps/bi/views/SemanticLayer/DrillHierarchies.py:46`
  - Fix: Change `25` to `15` to match NavERP standard `per_page=15`.

---

## Pass 5: qa-smoke-tester Findings

### Critical
- **[QA-CRIT-1]** `write_audit_log` call signature mismatch crashes ALL 15 POST mutations across Semantic Layer with HTTP 500:
  - Runtime verification with test client confirmed `TypeError: write_audit_log() takes from 3 to 5 positional arguments but 6 were given` on all 15 POST mutation endpoints:
    - SemanticModel: create, edit, delete, certify, introspect
    - BusinessGlossaryTerm: create, edit, delete, certify
    - CalculatedMeasure: create, edit, delete
    - DrillHierarchy: create, edit, delete
  - Fix: Update all 15 call sites in `apps/bi/views/SemanticLayer/*.py` to `write_audit_log(request.user, instance, action, tenant=request.tenant)`. On delete views, call before `instance.delete()`.

### Important
- **[QA-IMP-1]** Unvalidated string query parameters on Foreign Key ID filters cause HTTP 500 (`ValueError`):
  - In `SemanticModels.py:L60` (`?data_mart=invalid`), `CalculatedMeasures.py:L35` (`?model=invalid`), and `DrillHierarchies.py:L33` (`?model=invalid`), non-numeric strings cause `ValueError: Field 'id' expected a number but got ...`.
  - Fix: Guard with `if mart_filter.isdigit():` and `if model_filter.isdigit():`.

### Pass Verifications
- Zero comment leaks (`{#`) across all 11 Semantic Layer templates and rendered output.
- Data rendering (no silent blanks) verified across all 17 GET views with real seeded attributes.
- Cross-tenant IDOR protection 100% verified (all 8 GET and 7 POST cross-tenant requests returned HTTP 404).
