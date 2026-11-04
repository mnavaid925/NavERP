# Review Findings — Sub-module 10.4: Data Modeling & Semantic Layer (Module 10: Business Intelligence, `bi`)

- **Sub-module:** 10.4 Data Modeling & Semantic Layer
- **Module:** 10 Business Intelligence
- **Target app:** `apps/bi`
- **Review date:** 2026-11-04
- **Base SHA:** `069fb344d5ed505ef7ef4373b47d5ed6938ce6ed`
- **Status:** Complete (All 6 Review Passes Finished: code-reviewer, explorer, frontend-reviewer, performance-reviewer, qa-smoke-tester, security-reviewer)

---

## Prioritized Findings (Deduplicated)

### Critical Findings

- [ ] **[C1] Universal `write_audit_log` parameter mismatch crashes all 15 POST mutations and delete-after-call bug**
  - **Found by:** code-reviewer, explorer, qa-smoke-tester, security-reviewer
  - **Locations:**
    - `apps/bi/views/SemanticLayer/SemanticModels.py:L134, L161, L191, L218, L254`
    - `apps/bi/views/SemanticLayer/BusinessGlossaryTerms.py:L112, L139, L169, L196`
    - `apps/bi/views/SemanticLayer/CalculatedMeasures.py:L109, L136, L167`
    - `apps/bi/views/SemanticLayer/DrillHierarchies.py:L98, L125, L155`
  - **Description:** `write_audit_log` signature is `(user, obj, action, changes=None, tenant=None)` but called with 6 positional arguments `(request.tenant, request.user, "<action>", "<Model>", pk, message)`. This throws `TypeError` on every mutating POST, causing 500 server crashes. On delete views, it is called after `instance.delete()`, losing valid target references.
  - **Fix:** Update all 15 call sites to `write_audit_log(request.user, instance, "<action>", tenant=request.tenant)`. On delete views, call before `instance.delete()`.

- [ ] **[C2] Missing Compound Foreign Key Index for Reverse Lookup on `CalculatedMeasure` (`tenant`, `glossary_term`)**
  - **Found by:** performance-reviewer
  - **Location:** `apps/bi/models/SemanticLayer/CalculatedMeasures.py:135-138`
  - **Description:** In `business_glossary_term_detail`, `term.measures.filter(tenant=request.tenant)` executes without a compound index starting with `(tenant, glossary_term)`, forcing sequential scans on tenant records.
  - **Fix:** Add `models.Index(fields=["tenant", "glossary_term"], name="idx_bcms_ten_glossary")` to `CalculatedMeasure.Meta.indexes` and generate/apply migration `0012`.

---

### Important Findings

- [ ] **[I1] Cross-tenant user enumeration and IDOR assignment via unscoped user fields in forms**
  - **Found by:** code-reviewer, explorer, security-reviewer
  - **Locations:** `apps/bi/forms/SemanticLayer/SemanticModels.py:L58, L62` (`owner`), `apps/bi/forms/SemanticLayer/BusinessGlossaryTerms.py:L47, L56` (`steward`)
  - **Description:** Form fields query `User.objects.filter(is_active=True)` without tenant scoping, leaking usernames across tenants and allowing cross-tenant assignment. Missing from `reject_foreign`.
  - **Fix:** Scope user querysets in `__init__` to `tenant=self.tenant`, preserve existing instance users on edit, order by username, and include in `reject_foreign` in `clean()`.

- [ ] **[I2] Mass assignment & governance bypass of certification status in standard CRUD forms**
  - **Found by:** security-reviewer
  - **Locations:** `apps/bi/forms/SemanticLayer/SemanticModels.py`, `apps/bi/forms/SemanticLayer/BusinessGlossaryTerms.py`
  - **Description:** `certification_status` and `certification_notes` are in `Meta.fields` of general CRUD forms, allowing users to declare datasets certified without sign-off notes or certifier stamping (`certified_by=None`).
  - **Fix:** Remove `certification_status` and `certification_notes` from `Meta.fields` in `SemanticModelForm` and `BusinessGlossaryTermForm`, letting status transitions occur solely via dedicated certification views.

- [ ] **[I3] Missing compound indexes for ordering & filtering on `SemanticModel` and `BusinessGlossaryTerm`**
  - **Found by:** performance-reviewer
  - **Locations:** `apps/bi/models/SemanticLayer/SemanticModels.py:139-144`, `apps/bi/models/SemanticLayer/BusinessGlossaryTerms.py:103-107`
  - **Description:** Missing `["tenant", "-created_at"]` (`idx_bsmd_ten_created`), `["tenant", "data_mart"]` (`idx_bsmd_ten_mart`), and `["tenant", "domain_category", "name"]` (`idx_bglo_ten_domain_name`).
  - **Fix:** Add indexes to `Meta.indexes` and include in migration `0012`.

- [ ] **[I4] Unvalidated non-numeric string in foreign key GET filter parameters triggers unhandled `ValueError` 500**
  - **Found by:** code-reviewer, explorer, qa-smoke-tester, security-reviewer
  - **Locations:** `SemanticModels.py:L60` (`data_mart`), `CalculatedMeasures.py:L35` (`model`), `DrillHierarchies.py:L33` (`model`)
  - **Description:** Querying `?data_mart=invalid` or `?model=invalid` causes unhandled `ValueError: Field 'id' expected a number`.
  - **Fix:** Guard integer FK filters with `if mart_filter.isdigit():` and `if model_filter.isdigit():`.

- [ ] **[I5] Stale certification metadata retained when uncertifying/demoting assets**
  - **Found by:** code-reviewer, explorer, security-reviewer
  - **Locations:** `SemanticModels.py:L214-L217`, `BusinessGlossaryTerms.py:L192-L195`
  - **Description:** Transitioning out of `certified` (to draft, in_review, or deprecated) leaves `certified_by` and `certified_at` populated.
  - **Fix:** Set `model.certified_by = None` and `model.certified_at = None` when `new_status != 'certified'`.

- [ ] **[I6] Missing filter dropdowns in list templates and pagination query param loss**
  - **Found by:** code-reviewer, explorer, frontend-reviewer
  - **Locations:**
    - `templates/bi/semantic_layer/semantic_model/list.html`: missing `scd_type` dropdown; pagination drops `scd_type` and `is_active`.
    - `templates/bi/semantic_layer/calculated_measure/list.html`: missing `time_intelligence` dropdown; pagination drops `time_intelligence` and `is_active`.
    - `business_glossary_term/list.html` and `drill_hierarchy/list.html`: pagination drops `is_active`.
  - **Fix:** Add missing filter controls and ensure pagination links include all active GET filters.

- [ ] **[I7] Virtual analytical view missing SQL validation**
  - **Found by:** code-reviewer, explorer
  - **Location:** `apps/bi/forms/SemanticLayer/SemanticModels.py:60`
  - **Description:** When `is_virtual_view` is true, `sql_definition` can be submitted blank.
  - **Fix:** Require `sql_definition` in `clean()` if `cleaned_data.get("is_virtual_view")` is true.

- [ ] **[I8] Unstyled `badge-purple` used across multiple list templates (Theme.css color system violation)**
  - **Found by:** code-reviewer, explorer, frontend-reviewer
  - **Locations:**
    - `templates/bi/semantic_layer/semantic_model/list.html:129`
    - `templates/bi/semantic_layer/business_glossary_term/list.html:121`
    - `templates/bi/semantic_layer/drill_hierarchy/list.html:123`
  - **Fix:** Replace `badge-purple` with `badge-info` (the theme's indigo/purple hue) or `badge-slate`.

- [ ] **[I9] Detail templates missing "Back to List" button in `.page-actions`**
  - **Found by:** frontend-reviewer
  - **Locations:** all 4 `detail.html` templates (`semantic_model`, `business_glossary_term`, `calculated_measure`, `drill_hierarchy`)
  - **Fix:** Add `<a href="..." class="btn btn-outline"><i data-lucide="arrow-left"></i><span>Back to ...</span></a>`.

- [ ] **[I10] Overview certification status badge lacks 'deprecated' branch and fallback**
  - **Found by:** frontend-reviewer
  - **Location:** `templates/bi/semantic_layer/semantic_overview.html:190-196`
  - **Fix:** Add `elif sm.certification_status == 'deprecated'` (`badge-red`) and fallback to `{{ sm.get_certification_status_display }}`.

- [ ] **[I11] Defense-in-depth IDOR check in schema introspection**
  - **Found by:** security-reviewer
  - **Location:** `apps/bi/views/SemanticLayer/SemanticModels.py:235-241`
  - **Description:** `semantic_model_introspect` should verify `model.warehouse_table.tenant_id == request.tenant.pk` before reading schema metadata.
  - **Fix:** Add check and return error message if mismatch.

- [ ] **[I12] Query optimization: remove unused double-join in `semantic_model_list` and unused M2M prefetch in glossary list**
  - **Found by:** performance-reviewer
  - **Locations:** `SemanticModels.py:29-32` (`hierarchy_count`), `BusinessGlossaryTerms.py:23` (`prefetch_related("related_terms")`)
  - **Fix:** Remove `hierarchy_count` from `annotate()` in semantic_model_list; remove `.prefetch_related("related_terms")` from glossary list view.

- [ ] **[I13] Duplicate query triggered by `count` in template header before loop**
  - **Found by:** performance-reviewer
  - **Locations:** `semantic_model/detail.html` (`measures`, `drill_hierarchies`), `business_glossary_term/detail.html` (`related_measures`)
  - **Fix:** Evaluate to `list()` in view, use `|length` in template.

- [ ] **[I14] Combine sequential count queries in `semantic_overview` with conditional aggregation**
  - **Found by:** performance-reviewer
  - **Location:** `apps/bi/views/SemanticLayer/SemanticOverviewViews.py:19-24`
  - **Fix:** Use `Count("id", filter=Q(...))` to eliminate redundant queries.

- [ ] **[I15] Standardize pagination page size (15 instead of 25) across all four list views**
  - **Found by:** performance-reviewer
  - **Locations:** `SemanticModels.py:69`, `BusinessGlossaryTerms.py:53`, `CalculatedMeasures.py:52`, `DrillHierarchies.py:46`
  - **Fix:** Change `25` to `15` to adhere to NavERP `per_page=15` standard.

---

### Minor Findings

- [ ] **[M1] Missing `aria-label` on icon-only buttons across templates**
  - **Found by:** frontend-reviewer
  - **Locations:** `semantic_overview.html`, all list and detail templates.
  - **Fix:** Add descriptive `aria-label` to `.btn.btn-icon` elements.

- [ ] **[M2] Missing `for` and `id` pairings on filter inputs and detail inline forms**
  - **Found by:** frontend-reviewer
  - **Locations:** list filter forms and detail certification forms.
  - **Fix:** Add `id` on inputs and matching `for` on labels.

- [ ] **[M3] None-safe method calls on nullable Foreign Keys in templates**
  - **Found by:** frontend-reviewer
  - **Locations:** `semantic_model/detail.html:400`, `business_glossary_term/list.html:131`, `business_glossary_term/detail.html:259`
  - **Fix:** Wrap with explicit `{% if ... %}` checks (rule L10).

- [ ] **[M4] Inaccurate fallback label in `semantic_overview.html`**
  - **Found by:** explorer
  - **Location:** `templates/bi/semantic_layer/semantic_overview.html:L187`
  - **Fix:** Check `if sm.is_virtual_view` else `No Table Bound`.

- [ ] **[M5] Raw underscores in overview distribution cards**
  - **Found by:** code-reviewer
  - **Location:** `templates/bi/semantic_layer/semantic_overview.html:L288, L307`
  - **Fix:** Replace underscores with spaces / clean formatting.

- [ ] **[M6] Unused import `tenant_admin_required` and dead local variable `model_pk`**
  - **Found by:** code-reviewer, explorer
  - **Locations:** `SemanticModels.py:L20`, `CalculatedMeasures.py:L165`
  - **Fix:** Clean up dead code.

- [ ] **[M7] Introspection surrogate key override logic**
  - **Found by:** code-reviewer, explorer
  - **Location:** `SemanticModels.py:L247`
  - **Fix:** `if (not model.primary_key_column or model.primary_key_column == "id") and table.primary_key_column:`.

- [ ] **[M8] Add `tenant` to `readonly_fields` in ModelAdmin classes**
  - **Found by:** security-reviewer
  - **Location:** `apps/bi/admin.py:124-158`
  - **Fix:** Add `"tenant"` to `readonly_fields` across all 4 admin classes.

- [ ] **[M9] `Command.help` in `seed_bi.py` omits 10.4**
  - **Found by:** code-reviewer
  - **Location:** `apps/bi/management/commands/seed_bi.py:L28`
  - **Fix:** Update help string to mention 10.4 Semantic Layer.
