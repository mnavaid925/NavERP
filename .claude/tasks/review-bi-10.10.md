# Review findings — bi 10.10 Self-Service & Ad-Hoc Analytics

Range: `49d6b473b6af678ad33ad0bb9e4a1da0d9b1df91...HEAD` — Generated: 2026-11-06
Wave (serial): code-reviewer → explorer → frontend-reviewer → performance-reviewer → qa-smoke-tester → security-reviewer

## Summary

| Severity | Count |
|---|---|
| Critical | 2 |
| Important | 10 |
| Minor | 7 |
| **Total (deduped)** | **19** |

| Agent | Raw findings |
|---|---|
| code-reviewer | 8 |
| explorer | 10 |
| frontend-reviewer | 4 |
| performance-reviewer | 6 |
| qa-smoke-tester | 3 |
| security-reviewer | 4 |

## How to work this file (code-fixer)

Fix in ID order: every `C`, then every `I`, then every `M`. One fix → one file → one `git add` + one
`git commit`. Update each **Status** line to `[x] fixed — <commit subject>` or `[~] skipped — <reason>`
as you go. Never delete a finding; a wrong one gets `[~] skipped — not a defect: <why>`. Never `git push`.

---

## Critical

### C1 — Pervasive `write_audit_log` call signature mismatch causes HTTP 500 on all mutations
- **Found by:** qa-smoke-tester, security-reviewer
- **Location:**
  - `apps/bi/views/SelfServiceAnalytics/AdHocQueries.py:146, 181, 212, 249`
  - `apps/bi/views/SelfServiceAnalytics/AdHocCalculatedFields.py:84, 115, 146`
  - `apps/bi/views/SelfServiceAnalytics/DataBlendDefinitions.py:100, 134, 165`
  - `apps/bi/views/SelfServiceAnalytics/SavedAnalysisViews.py:107, 140, 171, 199, 218`
- **Problem:** `apps.core.utils.write_audit_log(user, obj, action, changes=None, tenant=None)` expects `user` as first positional arg. The views pass `(request, action=..., instance=..., description=...)` which raises `TypeError: write_audit_log() got an unexpected keyword argument 'instance'` on every create, edit, delete, composer save, share, and clone POST.
- **Fix:** Update all calls across the four view modules to pass:
  ```python
  write_audit_log(
      user=request.user,
      obj=instance_obj,
      action="create",  # or "update" / "delete"
      tenant=request.tenant,
      changes=form.cleaned_data if 'form' in locals() else None,
  )
  ```
- **Status:** [ ] open

### C2 — Duplicate clone slug collision causes HTTP 500 and sequence retry exhaustion
- **Found by:** code-reviewer, explorer, qa-smoke-tester
- **Location:** `apps/bi/views/SelfServiceAnalytics/SavedAnalysisViews.py:186`
- **Problem:** `saved_analysis_view_clone` derives slug as `slugify(f"Copy of {original.name}")[:100]` which yields duplicate slugs on subsequent clones, causing `django.db.utils.IntegrityError` (HTTP 500) against `bi_bsav_tenant_slug_uniq`.
- **Fix:** De-duplicate slug with loop counter before create:
  ```python
  base_slug = slugify(f"Copy of {original.name}")[:90] or "view-copy"
  slug = base_slug
  counter = 1
  while SavedAnalysisView.objects.filter(tenant=request.tenant, slug=slug).exists():
      slug = f"{base_slug}-{counter}"
      counter += 1
  ```
- **Status:** [ ] open

---

## Important

### I1 — State mutation & DB record creation on HTTP GET without CSRF in `saved_analysis_view_clone`
- **Found by:** code-reviewer, explorer, security-reviewer
- **Location:**
  - `apps/bi/views/SelfServiceAnalytics/SavedAnalysisViews.py:183`
  - `templates/bi/self_service_analytics/saved_analysis_view/list.html:124`
  - `templates/bi/self_service_analytics/saved_analysis_view/detail.html:34`
  - `templates/bi/self_service_analytics/saved_analysis_view/explore.html:29`
- **Problem:** Endpoint creates records on GET requests via `<a href>` links without CSRF protection.
- **Fix:** Add `@require_POST`, wrap in `transaction.atomic()`, and update template links to use a small POST form with `{% csrf_token %}`.
- **Status:** [ ] open

### I2 — Intra-tenant authorization bypass on personal saved views (Horizontal Privilege Escalation)
- **Found by:** security-reviewer
- **Location:** `apps/bi/views/SelfServiceAnalytics/SavedAnalysisViews.py:66-86, 131-162, 166-179, 210-236, 239-278`
- **Problem:** Detail, explore, edit, delete, and share actions fetch by PK and tenant without checking `sharing_scope` or `created_by`. Non-admin tenant users can view, modify, or delete another user's private "personal" views.
- **Fix:** Enforce access control in `SavedAnalysisViews.py`:
  - In `detail` and `explore`: allow access if `view_obj.sharing_scope != "personal"` or `view_obj.created_by == request.user` or `request.user.is_superuser` or `getattr(request, "is_tenant_admin", False)`.
  - In `edit`, `delete`, `share`: allow access only if `view_obj.created_by == request.user` or `request.user.is_superuser` or `getattr(request, "is_tenant_admin", False)`.
- **Status:** [ ] open

### I3 — State mutation on HTTP GET in `ad_hoc_query_execute`
- **Found by:** security-reviewer
- **Location:**
  - `apps/bi/views/SelfServiceAnalytics/AdHocQueries.py:293-324`
  - `templates/bi/self_service_analytics/ad_hoc_query/composer.html:265`
- **Problem:** `ad_hoc_query_execute` mutates execution statistics and runtime counters on GET requests.
- **Fix:** Add `@require_POST` to `ad_hoc_query_execute` and update `composer.html` JavaScript to issue a POST request with `X-CSRFToken`.
- **Status:** [ ] open

### I4 — Design system palette violation: `badge-purple` is invalid in `theme.css` (Lesson L33)
- **Found by:** explorer, frontend-reviewer
- **Location:**
  - `apps/bi/models/SelfServiceAnalytics/AdHocCalculatedFields.py:73`
  - `apps/bi/models/SelfServiceAnalytics/DataBlendDefinitions.py:128`
  - `templates/bi/self_service_analytics/ad_hoc_query/composer.html:108`
  - `templates/bi/self_service_analytics/saved_analysis_view/list.html:115`
  - `templates/bi/self_service_analytics/saved_analysis_view/detail.html:21`
- **Problem:** `badge-purple` is not defined in `static/css/theme.css` (only `badge-green/red/amber/info/muted/slate` exist).
- **Fix:** Replace `badge-purple` with `badge-info` (and `badge-amber` for `full_outer`).
- **Status:** [ ] open

### I5 — Contract mismatch & blank cells in explore data grid
- **Found by:** code-reviewer, explorer
- **Location:** `templates/bi/self_service_analytics/saved_analysis_view/explore.html:69-70`
- **Problem:** Table headers dynamically iterate `preview_results.columns`, but table row cells hardcode `{{ row.Period }}` and `{{ row.Revenue }}`.
- **Fix:** Dynamically iterate over `row.items` or `row.values`.
- **Status:** [ ] open

### I6 — View-template contract omission in `saved_analysis_view_list` filter bar
- **Found by:** explorer
- **Location:**
  - `apps/bi/views/SelfServiceAnalytics/SavedAnalysisViews.py:47`
  - `templates/bi/self_service_analytics/saved_analysis_view/list.html:33-65`
- **Problem:** `org_units` passed in context but omitted from template filter bar; `template=1` filter option missing from dropdown; pagination links drop `&template=` and `&org_unit=`.
- **Fix:** Support `org_unit` filter in view, add `org_unit` select dropdown and `template=1` option in `list.html`, and preserve query params in pagination links.
- **Status:** [ ] open

### I7 — Dropped `query` filter on pagination in calculated field list
- **Found by:** code-reviewer, explorer
- **Location:** `templates/bi/self_service_analytics/ad_hoc_calculated_field/list.html:155`
- **Problem:** Pagination links omit `&query={{ request.GET.query }}`, dropping filter on page 2+.
- **Fix:** Preserve `{% if request.GET.query %}&query={{ request.GET.query }}{% endif %}` on pagination links.
- **Status:** [ ] open

### I8 — Hardcoded domain `https://erp.nav.local` in share token URL
- **Found by:** code-reviewer, explorer, frontend-reviewer
- **Location:** `templates/bi/self_service_analytics/saved_analysis_view/share.html:57`
- **Problem:** Shareable token input hardcodes domain `https://erp.nav.local`.
- **Fix:** Replace with `{{ request.scheme }}://{{ request.get_host }}{% url 'bi:saved_analysis_view_detail' view_obj.pk %}?token={{ view_obj.share_token }}`.
- **Status:** [ ] open

### I9 — Missing 10.10 tables in seeder `--flush` block
- **Found by:** code-reviewer, explorer
- **Location:** `apps/bi/management/commands/seed_bi.py:66-70`
- **Problem:** The `if flush:` block omits the four 10.10 tables (`SavedAnalysisView`, `AdHocCalculatedField`, `AdHocQuery`, `DataBlendDefinition`), breaking `--flush` wipe idempotence.
- **Fix:** Add deletion of `SavedAnalysisView`, `AdHocCalculatedField`, `AdHocQuery`, `DataBlendDefinition` to flush block.
- **Status:** [ ] open

### I10 — Missing composite database indexes on tenant-filtered FKs
- **Found by:** performance-reviewer
- **Location:**
  - `apps/bi/models/SelfServiceAnalytics/SavedAnalysisViews.py:62`
  - `apps/bi/models/SelfServiceAnalytics/DataBlendDefinitions.py:95`
- **Problem:** Missing composite indexes on `(tenant, query)` for `SavedAnalysisView` and `(tenant, created_by)` for `DataBlendDefinition`.
- **Fix:** Add composite indexes to `Meta.indexes` and generate a clean migration.
- **Status:** [ ] open

---

## Minor

### M1 — Redundant SELECT queries in Create, Edit, and Composer views
- **Found by:** code-reviewer, explorer, performance-reviewer
- **Location:**
  - `apps/bi/views/SelfServiceAnalytics/AdHocQueries.py:133`
  - `apps/bi/views/SelfServiceAnalytics/DataBlendDefinitions.py:89`
  - `apps/bi/views/SelfServiceAnalytics/SavedAnalysisViews.py:91`
  - `apps/bi/views/SelfServiceAnalytics/AdHocCalculatedFields.py:69`
- **Problem:** View functions execute manual queries for models that `TenantModelForm` already scopes.
- **Fix:** Remove unused manual model queries and context variables.
- **Status:** [ ] open

### M2 — Literal route declared after parameterized `<int:pk>/` route
- **Found by:** code-reviewer, explorer
- **Location:** `apps/bi/urls/SelfServiceAnalytics/AdHocCalculatedFields.py:11`
- **Problem:** `calculated-fields/validate/` declared after `calculated-fields/<int:pk>/`.
- **Fix:** Move literal route above parameterized route.
- **Status:** [ ] open

### M3 — Missing `<label for>` and `<input id>` association
- **Found by:** frontend-reviewer
- **Location:** `templates/bi/self_service_analytics/saved_analysis_view/share.html:55-57`
- **Problem:** Share token input has no `id` and label has no `for`.
- **Fix:** Add `for="id_shareable_token_url"` and `id="id_shareable_token_url"`.
- **Status:** [ ] open

### M4 — Filter grid column balance in calculated field list
- **Found by:** frontend-reviewer
- **Location:** `templates/bi/self_service_analytics/ad_hoc_calculated_field/list.html:33`
- **Problem:** Filter grid specifies `lg:grid-cols-4` but contains only 3 elements.
- **Fix:** Change `lg:grid-cols-4` to `lg:grid-cols-3`.
- **Status:** [ ] open

### M5 — Action column icon consistency in data blend list
- **Found by:** frontend-reviewer
- **Location:** `templates/bi/self_service_analytics/data_blend_definition/list.html:129`
- **Problem:** Eye icon in action column links to preview instead of standard detail view.
- **Fix:** Link eye icon to detail view and sliders/play icon to preview.
- **Status:** [ ] open

### M6 — Lazy FK retrieval in `saved_analysis_view_clone`
- **Found by:** performance-reviewer
- **Location:** `apps/bi/views/SelfServiceAnalytics/SavedAnalysisViews.py:184-197`
- **Problem:** `original.query` and `original.org_unit` dereference FK instances, causing lazy queries.
- **Fix:** Use `query_id=original.query_id` and `org_unit_id=original.org_unit_id`.
- **Status:** [ ] open

### M7 — `DataBlendDefinitionAdmin.list_select_related` omits warehouse tables
- **Found by:** performance-reviewer
- **Location:** `apps/bi/admin.py:385`
- **Problem:** `list_select_related` omits `primary_warehouse_table` and `secondary_warehouse_table`.
- **Fix:** Add warehouse table fields to `list_select_related`.
- **Status:** [ ] open

---

## Raw agent reports

### Pass 1: code-reviewer
- **Verdict:** Commit after fixing Critical+Important.
- Critical: `SavedAnalysisViews.py:186` slug collision on view cloning.
- Important: `seed_bi.py:66` flush wipe missing 10.10 models; `SavedAnalysisViews.py:183` GET mutation on clone; `ad_hoc_calculated_field/list.html:155` pagination dropping `?query=`; `share.html:57` hardcoded domain.
- Minor: Redundant queries in create/edit views; literal route order in calculated fields URLs; hardcoded row fields in explore preview.

### Pass 2: explorer
- **Verdict:** Commit after fixing Critical + Important.
- Critical: `SavedAnalysisViews.py:186` slug collision on view cloning.
- Important: `badge-purple` invalid in theme.css (L33); `explore.html:69` hardcoded row cells; `saved_analysis_view/list.html` filter contract omission (`org_units` and `template`); GET mutation on clone; `seed_bi.py` flush wipe; dropped `query` filter in pagination; hardcoded share domain.
- Minor: Redundant queries; literal route ordering.

### Pass 3: frontend-reviewer
- **Verdict:** Passed with Minor / Important Findings.
- Important: `badge-purple` in `composer.html`, `detail.html`, `list.html`, and model properties (L33); missing `<label for>` and `<input id>` in `share.html`.
- Minor: Filter form grid balance in calculated field list; action column icon in data blends list.
- Verified: Zero comment leaks (L2); None-safe lookups (L10); pagination guards (L9); CSRF on delete forms.

### Pass 4: performance-reviewer
- **Verdict:** PASS with Important Optimizations.
- Important: Redundant queries in create/edit/composer views; missing composite indexes on `(tenant, query)` and `(tenant, created_by)`.
- Minor: Lazy FK retrieval in clone; `admin.py` list_select_related omits warehouse tables.
- Verified: Zero N+1 query loops; single SQL aggregate for KPIs; pagination before slicing; targeted `update_fields`.

### Pass 5: qa-smoke-tester
- **Verdict:** FAIL — 2 Critical defects identified.
- Critical: Pervasive `write_audit_log` call signature mismatch across all 4 views modules causing 500 on all mutations; duplicate clone slug collision causing 500 / sequence retry exhaustion.
- Important: Missing transaction.atomic in clone view.
- Verified: 28 URLs sweep tested with `admin_acme`; zero comment leaks; IDOR returns 404 across all 28 endpoints.

### Pass 6: security-reviewer
- **Verdict:** Commit after fixing Critical + Important.
- Critical: `write_audit_log` signature mismatch breaking mutations and audit logging.
- Important: State mutation on GET in `saved_analysis_view_clone`; intra-tenant horizontal privilege escalation on personal saved views; state mutation on GET in `ad_hoc_query_execute`.
- Minor: Share token query parameter inconsistency.
- Verified: Strict multi-tenant scoping; pure ORM (no SQL injection); no XSS; CSV formula injection defense (`csv_safe`); mass assignment defense; CSRF protection.
