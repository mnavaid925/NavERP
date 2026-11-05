# Consolidated Review Findings: Sub-module 10.8 Dashboards & Visualization

**Commit Range:** `7d343a2af8e7ae61ab20168cfdec164cec1e4ed0...HEAD`  
**Review Passes:**
1. Code Reviewer — Completed
2. Explorer (Architecture & Contract) — Completed
3. Frontend Reviewer — Completed
4. Performance Reviewer — Completed
5. QA Smoke Tester — Completed
6. Security Reviewer — Completed (inline)

---

## Pass 1: Code Reviewer

### Critical
None. Multi-tenant isolation is strict (all 4 models inherit `TenantNumbered`, unique constraints are composite with tenant, forms enforce `reject_foreign`, views use `bi_scope` / `bi_object`), schema migration 0019 is complete, and no plaintext secrets are exposed.

### Important
1. `templates/bi/dashboards/dashboard/detail.html:109` — Unhandled nullable FK traversal inside filter argument `{{ dashboard.created_by.get_full_name|default:dashboard.created_by.username|default:"System Seed" }}` raises `VariableDoesNotExist` and 500s when `created_by` is None (Lesson L10). Fix: Guard with `{% if dashboard.created_by %}{{ dashboard.created_by.get_full_name|default:dashboard.created_by.username }}{% else %}System Seed{% endif %}`.
2. `apps/bi/views/Dashboards/BiDashboardWidgets.py:38` — Unguarded integer FK filter `dashboard_id` raises unhandled `ValueError` 500 on non-numeric input e.g. `?dashboard=abc` (Lesson L11). Fix: Guard with `if dashboard_id.isdigit():`.
3. `apps/bi/views/Dashboards/BiDashboardBookmarks.py:36` — Unguarded integer FK filter `dashboard_id` raises unhandled `ValueError` 500 on non-numeric input e.g. `?dashboard=abc` (Lesson L11). Fix: Guard with `if dashboard_id.isdigit():`.
4. `apps/bi/views/Dashboards/BiDashboardFilters.py:33` — Unguarded integer FK filter `dashboard_id` raises unhandled `ValueError` 500 on non-numeric input e.g. `?dashboard=abc` (Lesson L11). Fix: Guard with `if dashboard_id.isdigit():`.
5. `apps/bi/views/Dashboards/BiDashboardCanvasViews.py:59` — Unguarded `bookmark_id` query param passed directly to `.filter(pk=bookmark_id)` raises unhandled `ValueError` 500 on non-numeric input (Lesson L11). Fix: Guard with `if bookmark_id and bookmark_id.isdigit():`.
6. `templates/bi/dashboards/canvas/viewer.html:112` & `templates/bi/dashboards/canvas/viewer.html:128` — Invalid `dictsort` template filter on `request.GET` (`request.GET|dictsort:f.filter_key`) evaluates to empty string `''`, causing active filter query selections to be completely ignored by the canvas dropdowns and text inputs. Fix: In `bi_dashboard_canvas_view` (`apps/bi/views/Dashboards/BiDashboardCanvasViews.py:82`), attach `f.current_value = filter_values.get(f.filter_key, f.default_value)` to each filter in `filters`, and in the template compare `{% if f.current_value == opt.value %}selected{% endif %}` and `value="{{ f.current_value }}"`.
7. `apps/bi/views/Dashboards/BiDashboardCanvasViews.py:120` — Missing authorization check on `bi_dashboard_canvas_builder`; any authenticated user in the tenant can access the visual layout builder and issue AJAX POST requests to mutate widget grid positions and dimensions on any dashboard. Fix: Add `@tenant_admin_required` or enforce creator/admin check (`if not (request.user.is_superuser or getattr(request, "is_tenant_admin", False) or dashboard.created_by == request.user): return HttpResponseForbidden(...)`).
8. `apps/bi/forms/Dashboards/BiDashboardForms.py:47` — `BiDashboardForm` attempts auto-slugification in `clean()`, but `self.fields["slug"].required` defaults to `True`, causing blank slug submissions to fail field validation before `clean()` can run. Fix: Add `self.fields["slug"].required = False` in `__init__`.
9. `apps/bi/forms/Dashboards/BiDashboardFilterForms.py:39` — `BiDashboardFilterForm` attempts auto-slugification for `filter_key` in `clean()`, but `self.fields["filter_key"].required` defaults to `True`, causing blank key submissions to fail field validation. Fix: Add `self.fields["filter_key"].required = False` in `__init__`.
10. `apps/bi/management/commands/seed_bi.py:58` — Seeder flush wipe block omits all four 10.8 dashboard models (`BiDashboardBookmark`, `BiDashboardFilter`, `BiDashboardWidget`, `BiDashboard`), leaving stale data when `seed_bi --flush` is executed. Fix: Add `BiDashboardBookmark.objects.all().delete()`, `BiDashboardFilter.objects.all().delete()`, `BiDashboardWidget.objects.all().delete()`, and `BiDashboard.objects.all().delete()` at the top of the flush block.
11. `templates/bi/dashboards/widget/list.html:132` — Actions column on widget list omits standard POST-only delete form with CSRF and confirm dialogue. Fix: Add POST delete form button to the actions column.
12. `templates/bi/dashboards/bookmark/list.html:125` — Actions column on bookmark list omits standard POST-only delete form with CSRF and confirm dialogue. Fix: Add POST delete form button to the actions column.
13. `templates/bi/dashboards/filter/list.html:118` — Actions column on filter list omits standard POST-only delete form with CSRF and confirm dialogue. Fix: Add POST delete form button to the actions column.

### Minor
1. `apps/bi/views/Dashboards/BiDashboardBookmarks.py:211` — Hardcoded URL `/bi/dashboards/{bookmark.dashboard_id}/view/?bookmark={bookmark.pk}` used instead of reverse lookup. Fix: Use `reverse("bi:bi_dashboard_canvas_view", kwargs={"pk": bookmark.dashboard_id}) + f"?bookmark={bookmark.pk}"`.
2. `apps/bi/views/Dashboards/BiDashboardCanvasViews.py:97` — `bi_dashboard_kiosk_view` renders full-screen wallboard without checking `dashboard.is_kiosk_enabled`. Fix: Return `HttpResponseForbidden` if `not dashboard.is_kiosk_enabled`.
3. `apps/bi/views/Dashboards/BiDashboards.py:227` — `bi_dashboard_duplicate` does not catch or handle duplicate slug collisions for `request.tenant` prior to `BiDashboard.objects.create()`. Fix: Check slug existence and append incremental suffix if slug already exists.
4. `apps/bi/views/Dashboards/BiDashboardCanvasViews.py:134` — Bulk widget repositioning AJAX action does not write an `AuditLog` entry. Fix: Add `write_audit_log` call inside the transaction.

---

## Pass 2: Explorer (Architecture & Contract)

### Critical
None. Multi-tenant data isolation is strictly enforced across models via `TenantNumbered` and `TenantUniqueMixin`, SQL injection and XSS protections are standard, and no schema corruption or system crashes exist.

### Important
1. `apps/bi/views/Dashboards/BiDashboardCanvasViews.py:33-36` — Broken Role Resolution on Role-Restricted Dashboards: View checks `user_roles.filter(code=dashboard.role_required)`, but NavERP User model has single `role` FK with `name`. Fix: Use `request.user.role and request.user.role.name.lower() == dashboard.role_required.lower()`.
2. `apps/bi/views/Dashboards/BiDashboardCanvasViews.py:60` — Cross-User Bookmark Privacy Leak (IDOR): `?bookmark=<id>` retrieves bookmark without checking ownership or sharing scope. Fix: Scope with `Q(user=request.user) | Q(is_shared=True)`.
3. `templates/bi/dashboards/canvas/viewer.html:111,127` — Invalid `dictsort` template filter on QueryDict silently evaluates to `""`, causing query filters to be ignored. Fix: Attach `current_value` to filters in view and compare in template.
4. `apps/bi/forms/Dashboards/BiDashboardBookmarkForms.py:9-37` — Unhandled DB IntegrityError on Duplicate Bookmark Submission: Excluded `user` field bypasses validation, triggering 500 on duplicate name for same user. Fix: Accept `user` in `__init__` and validate uniqueness in `clean()`.
5. `templates/bi/dashboards/dashboard/detail.html:48-73` vs `apps/bi/views/Dashboards/BiDashboards.py:118, 150, 180, 200` — Creator Action Buttons Result in 403 PermissionDenied: `detail.html` shows buttons to author, but views enforce `@tenant_admin_required`. Fix: Align permissions between views and templates.
6. `apps/bi/views/Dashboards/BiDashboardCanvasViews.py:120-146` — Missing Authorization Check on Visual Builder and Drag-and-Drop Layout AJAX Endpoint. Fix: Add `@tenant_admin_required` or author/admin check.
7. `apps/bi/views/Dashboards/BiDashboardBookmarks.py:205-211` — Missing Shared Scope Check and Hardcoded URL in Bookmark Apply. Fix: Enforce `bookmark.user == request.user or bookmark.is_shared or is_tenant_admin` and reverse URL.
8. `apps/bi/views/Dashboards/BiDashboardCanvasViews.py:21-40, 97-116` — Unpublished Draft Dashboards Accessible to Regular Users without publish guard. Fix: Return 403 if `not dashboard.is_published and not is_admin_or_author`.

### Minor
1. `templates/bi/dashboards/widget/detail.html:47-157` — Unrendered Pinned Context Variable `data_preview`. Fix: Add sample dataset preview card.
2. `templates/bi/dashboards/bookmark/detail.html:82-90` — Unrendered Pinned Context Variable `crossfilter_state_pretty`. Fix: Add JSON preformatted block.
3. `templates/bi/dashboards/canvas/builder.html:90-125` — Omission of `warehouse_tables` in Builder Sidebar Toolbox. Fix: Add Analytical Warehouse Tables section under Available Metric Sources.
4. `templates/bi/dashboards/dashboard/list.html:151` & `apps/bi/views/Dashboards/BiDashboards.py:20` — N+1 Queries on Dashboard List Page (`d.widgets.count`). Fix: Annotate `widget_count` in view.
5. `apps/bi/views/Dashboards/BiDashboardCanvasViews.py:97-104` — Kiosk Mode Verification Missing (`is_kiosk_enabled`). Fix: Guard with 403 when kiosk is disabled.
6. `apps/bi/views/Dashboards/BiDashboardCanvasViews.py:134-144` — Unvalidated Coordinate Ingestion in Canvas Builder AJAX Handler. Fix: Validate with `BiDashboardWidgetPositionForm`.
7. `templates/bi/dashboards/canvas/viewer.html:226` — Duplicate Chart.js Script Inclusion (already loaded by `base.html`). Fix: Remove redundant CDN script tag.
8. `templates/bi/dashboards/dashboard/list.html:70-112` — Theme Filter Omitted in Dashboard List UI. Fix: Add Theme select dropdown and preserve in pagination.

---

## Pass 3: Frontend Reviewer

### Critical
1. `templates/bi/dashboards/dashboard/detail.html:109` — Lesson L10 Violation: Nullable FK in Filter Argument `{{ dashboard.created_by.get_full_name|default:dashboard.created_by.username|default:"System Seed" }}` raises `VariableDoesNotExist` and 500s when `created_by` is None. Fix: Guard with `{% if dashboard.created_by %}{{ dashboard.created_by.get_full_name|default:dashboard.created_by.username }}{% else %}System Seed{% endif %}`.
2. `templates/bi/dashboards/canvas/viewer.html:111,127` — Invalid `|dictsort` filter on `request.GET` evaluates to empty string, breaking active filter choices and search terms. Fix: Attach active filter value to filter object in view and compare in template.

### Important
1. `templates/bi/dashboards/widget/list.html:132-139` — Missing Standardized POST-Delete Form with CSRF and confirm prompt in Widget List Actions Column. Fix: Add inline POST delete form.
2. `templates/bi/dashboards/bookmark/list.html:125-138` — Missing Standardized POST-Delete Form with CSRF and confirm prompt in Bookmark List Actions Column. Fix: Add ownership-guarded POST delete form.
3. `templates/bi/dashboards/filter/list.html:118-126` — Missing Standardized POST-Delete Form with CSRF and confirm prompt in Filter List Actions Column. Fix: Add inline POST delete form.
4. `templates/bi/dashboards/dashboard/list.html:168-180` — Missing Direct Edit and Delete Actions on Dashboard Card Grid footer. Fix: Add edit and delete actions to card footer cluster.

### Minor
1. `templates/bi/dashboards/canvas/viewer.html:83,137,161` & `templates/bi/dashboards/canvas/builder.html:32,61` — Missing `aria-label` Attributes on Icon-Only Buttons. Fix: Add descriptive `aria-label`.
2. `templates/bi/dashboards/canvas/viewer.html:33-38` — Missing Outside Click Dismissal on Bookmark Menu. Fix: Add document click listener to close dropdown when clicking outside.
3. `templates/bi/dashboards/canvas/builder.html:51` — Builder Template Lacks Client-Side Drag-and-Drop Script for Coordinates AJAX Endpoint. Fix: Add interactive JS grid script to POST updated coordinates to builder endpoint.

---

## Pass 4: Performance Reviewer

### Critical
None. Multi-tenant isolation is strictly enforced across all querysets (`tenant=request.tenant`), list views are paginated with `Paginator`, mutating actions run within `transaction.atomic()`, and no unconstrained Cartesian joins or memory-exhausting operations exist.

### Important
1. `templates/bi/dashboards/dashboard/list.html:151` & `apps/bi/views/Dashboards/BiDashboards.py:20` — N+1 Queries on Dashboard Card Grid (`{{ d.widgets.count }}`). Fix: Annotate `widget_count` in view with `Count('widgets', filter=Q(widgets__is_active=True))`.
2. `apps/bi/views/Dashboards/BiDashboards.py:90` & `templates/bi/dashboards/dashboard/detail.html:202-210` — N+1 Queries on Dashboard Detail Widgets Table (`calculated_measure`, `semantic_model`, `warehouse_table`). Fix: Add `.select_related("calculated_measure", "semantic_model", "warehouse_table")`.
3. `apps/bi/views/Dashboards/BiDashboards.py:92-94` & `templates/bi/dashboards/dashboard/detail.html:147` — N+1 Queries on Dashboard Detail Bookmarks List (`bm.user.username`). Fix: Add `.select_related("user")`.
4. `apps/bi/views/Dashboards/BiDashboards.py:81` & `apps/bi/views/Dashboards/BiDashboardCanvasViews.py:27, 102, 125` — Redundant Prefetches Discarded by Sub-queries in `bi_object`. Fix: Remove redundant `prefetch_related` from `bi_object` calls when queries re-filter.
5. `apps/bi/views/Dashboards/BiDashboards.py:21-23` — Multiple Unaggregated Stat Count Queries in Dashboard List View. Fix: Consolidate 3 `.count()` queries into single `.aggregate()`.
6. `apps/bi/models/Dashboards/BiDashboardBookmarks.py:61-62` — Chained N+1 Risk via Foreign Key Hop in `__str__` (`self.dashboard.title`). Fix: Simplify `__str__` to `f"{self.name} ({self.number})"` without FK traversal.
7. `apps/bi/views/Dashboards/BiDashboardCanvasViews.py:151-153` & `templates/bi/dashboards/canvas/builder.html:90-125` — Unbounded Unindexed Full-Table Queryset Fetch in Canvas Builder. Fix: Remove unused `warehouse_tables` and slice `.only("id", "name")[:10]` on models and measures.

### Minor
1. `templates/bi/dashboards/canvas/viewer.html:35, 41` & `templates/bi/dashboards/canvas/builder.html:48, 52` — Dual Query Trigger via `.count` Followed by Immediate Iteration. Fix: Use `{{ bookmarks|length }}` and `{{ widgets|length }}` in templates.
2. `apps/bi/views/Dashboards/BiDashboardWidgets.py:50` — Unused Related Model Queryset `semantic_models` in Widget List View. Fix: Remove unrendered query from view.
3. `apps/bi/views/Dashboards/BiDashboardWidgets.py:49`, `apps/bi/views/Dashboards/BiDashboardBookmarks.py:49`, `apps/bi/views/Dashboards/BiDashboardFilters.py:44` — Heavy Field Loading on Filter Dropdown Querysets. Fix: Add `.only("id", "title")` to `dashboards` dropdown querysets.
4. `apps/bi/views/Dashboards/BiDashboardWidgets.py:23`, `apps/bi/views/Dashboards/BiDashboardBookmarks.py:21`, `apps/bi/views/Dashboards/BiDashboardFilters.py:19` — Omission of `.defer()` on Unrendered JSON Fields in List Views. Fix: Defer heavy unrendered JSON fields on list querysets.
5. `apps/bi/models/Dashboards/BiDashboards.py:95-108` & `apps/bi/models/Dashboards/BiDashboardWidgets.py:117-130` — Missing Composite Tenant Indexes for Hot Ordering and Foreign Keys. Fix: Add `(tenant, -created_at)` on `BiDashboard` and `(tenant, warehouse_table)` on `BiDashboardWidget`.
6. `apps/bi/management/commands/seed_bi.py:2115` — Dead Query in Seeder Command (`drill_ref`). Fix: Remove unused query line.

---

## Pass 5: QA Smoke Tester

### Critical
1. `apps/bi/views/Dashboards/BiDashboards.py:128,158,186,207,270`, `apps/bi/views/Dashboards/BiDashboardWidgets.py:118,148,177`, `apps/bi/views/Dashboards/BiDashboardBookmarks.py:117,159,191`, `apps/bi/views/Dashboards/BiDashboardFilters.py:90,120,149` — Systemic HTTP 500 on All Mutating Actions: `write_audit_log` is called with invalid keyword argument `actor=request.user` instead of signature `(user, obj, action, changes=None, tenant=None)` (`apps/core/utils.py:10`), raising `TypeError: write_audit_log() got an unexpected keyword argument 'actor'` across every dashboard create, edit, delete, publish, duplicate, widget create/edit/delete, bookmark create/edit/delete, and filter create/edit/delete. Fix: Call `write_audit_log(request.user, <instance>, "<action>", changes=..., tenant=request.tenant)`.
2. `templates/bi/dashboards/dashboard/detail.html:109` — Runtime HTTP 500 on Dashboard Detail when `created_by` is None: `{{ dashboard.created_by.get_full_name|default:dashboard.created_by.username|default:"System Seed" }}` resolves the filter argument `dashboard.created_by.username` before evaluating `default:`, raising `VariableDoesNotExist: Failed lookup for key [username] in None` and 500ing on any system-seeded or null-creator dashboard (Lesson L10). Fix: Guard with `{% if dashboard.created_by %}{{ dashboard.created_by.get_full_name|default:dashboard.created_by.username }}{% else %}System Seed{% endif %}`.

### Important
1. `apps/bi/views/Dashboards/BiDashboardWidgets.py:38` — Unhandled `ValueError` 500 on non-numeric filter input: `dashboard_id = request.GET.get("dashboard")` passed to `.filter(dashboard_id=dashboard_id)` raises unhandled `ValueError: Field 'id' expected a number but got 'invalid_id'` on junk query parameters like `?dashboard=invalid` (Lesson L11). Fix: Guard with `if dashboard_id and dashboard_id.isdigit():`.
2. `apps/bi/views/Dashboards/BiDashboardBookmarks.py:36` — Unhandled `ValueError` 500 on non-numeric filter input: `dashboard_id = request.GET.get("dashboard")` passed to `.filter(dashboard_id=dashboard_id)` raises unhandled `ValueError: Field 'id' expected a number but got 'invalid_id'` on junk query parameters like `?dashboard=invalid` (Lesson L11). Fix: Guard with `if dashboard_id and dashboard_id.isdigit():`.
3. `apps/bi/views/Dashboards/BiDashboardFilters.py:33` — Unhandled `ValueError` 500 on non-numeric filter input: `dashboard_id = request.GET.get("dashboard")` passed to `.filter(dashboard_id=dashboard_id)` raises unhandled `ValueError: Field 'id' expected a number but got 'invalid_id'` on junk query parameters like `?dashboard=invalid` (Lesson L11). Fix: Guard with `if dashboard_id and dashboard_id.isdigit():`.
4. `apps/bi/views/Dashboards/BiDashboardCanvasViews.py:59` — Unhandled `ValueError` 500 on non-numeric bookmark query param: `bookmark_id = request.GET.get("bookmark")` passed directly to `dashboard.bookmarks.filter(pk=bookmark_id)` raises unhandled `ValueError: Field 'id' expected a number but got 'invalid_bm_id'` on junk query parameters like `?bookmark=abc` (Lesson L11). Fix: Guard with `if bookmark_id and bookmark_id.isdigit():`.
5. `templates/bi/dashboards/canvas/viewer.html:111,127` — Broken Dynamic Filter Selection in Viewer UI: `request.GET|dictsort:f.filter_key` on a `QueryDict` silently evaluates to empty string `""`, completely ignoring active GET filter parameters in dropdowns and text inputs. Fix: Attach `current_value` to each filter in `bi_dashboard_canvas_view` and compare `{% if f.current_value == opt.value %}selected{% endif %}` and `value="{{ f.current_value }}"`.
6. `apps/bi/views/Dashboards/BiDashboardCanvasViews.py:60` & `apps/bi/views/Dashboards/BiDashboardBookmarks.py:205` — Cross-User Bookmark Privacy Leak (IDOR): `?bookmark=<id>` on canvas view and `bi_dashboard_bookmark_apply` load and apply private bookmarks belonging to other users without scoping to `Q(user=request.user) | Q(is_shared=True)`. Fix: Filter active bookmark with `.filter(Q(user=request.user) | Q(is_shared=True))`.
7. `apps/bi/views/Dashboards/BiDashboardCanvasViews.py:120` — Missing Authorization Check on Canvas Builder: `bi_dashboard_canvas_builder` uses `@login_required` instead of `@tenant_admin_required`, allowing non-admin tenant members to access the visual builder and modify widget positions/dimensions via AJAX POST. Fix: Add `@tenant_admin_required` (or restrict to author/admin).
8. `apps/bi/views/Dashboards/BiDashboardCanvasViews.py:21-40` — Unpublished Draft Dashboards Accessible to Regular Users: `bi_dashboard_canvas_view` lacks a check on `dashboard.is_published`, allowing non-creator non-admin users to view unfinished draft dashboards. Fix: Return 403 if `not dashboard.is_published and not is_admin_or_author`.

### Minor
1. `apps/bi/views/Dashboards/BiDashboardCanvasViews.py:97` — Kiosk View Ignores Disabled Flag: `bi_dashboard_kiosk_view` renders full-screen wallboard even when `dashboard.is_kiosk_enabled=False`. Fix: Return 403 if `not dashboard.is_kiosk_enabled`.
2. `apps/bi/views/Dashboards/BiDashboardCanvasViews.py:134-143` — Unvalidated Coordinate Ingestion in Drag-and-Drop Handler: AJAX handler updates `pos_x`, `pos_y`, `width_cols`, `height_rows` without boundary validation (e.g., negative coords or `width_cols > 12`). Fix: Validate with bounds checks `max(0, min(11, pos_x))` and `max(1, min(12, width_cols))`.
3. `apps/bi/views/Dashboards/BiDashboardCanvasViews.py:33-36` — Role Restriction Attribute Check: `user_roles = getattr(request.user, "roles", None)` checks `.filter(code=...)`, but NavERP user model has single `role` FK (`request.user.role.name`). Fix: Check `request.user.role and request.user.role.name.lower() == dashboard.role_required.lower()`.
4. `apps/bi/views/Dashboards/BiDashboardBookmarks.py:211` — Hardcoded URL in Bookmark Apply: Redirect string `/bi/dashboards/{bookmark.dashboard_id}/view/?bookmark={bookmark.pk}` bypasses reverse routing. Fix: Use `reverse("bi:bi_dashboard_canvas_view", kwargs={"pk": bookmark.dashboard_id}) + f"?bookmark={bookmark.pk}"`.

### Route Verification Table

| Route Name | Method | Status | Cross-Tenant IDOR | Comment Leak | Notes |
|---|---|---|---|---|---|
| `bi:bi_dashboard_list` | GET | 200 PASS | N/A | PASS | Base dashboard list view |
| `bi:bi_dashboard_list (filtered)` | GET | 200 PASS | N/A | PASS | Filtered by category, status, query |
| `bi:bi_dashboard_list (junk params)` | GET | 200 PASS | N/A | PASS | Junk parameters handled safely |
| `bi:bi_dashboard_list (page 2)` | GET | 200 PASS | N/A | PASS | Pagination guard verified |
| `bi:bi_dashboard_create` | GET | 200 PASS | N/A | PASS | Dashboard create form |
| `bi:bi_dashboard_detail` | GET | 200 PASS | 404 PASS | PASS | Detail view & IDOR (500 if `created_by=None`) |
| `bi:bi_dashboard_edit` | GET | 200 PASS | 404 PASS | PASS | Dashboard edit form & cross-tenant IDOR |
| `bi:bi_dashboard_duplicate` | GET | 200 PASS | 404 PASS | PASS | Dashboard clone form & IDOR (POST 500 on audit log) |
| `bi:bi_dashboard_canvas_view` | GET | 200 PASS | 404 PASS | PASS | Visual canvas viewer & IDOR (500 if `?bookmark=invalid`) |
| `bi:bi_dashboard_canvas_builder` | GET | 200 PASS | 404 PASS | PASS | Drag-and-drop layout builder & IDOR |
| `bi:bi_dashboard_kiosk_view` | GET | 200 PASS | 404 PASS | PASS | Kiosk fullscreen wallboard & IDOR |
| `bi:bi_dashboard_publish` | POST | 500 FAIL | 404 PASS | PASS | Dashboard publish toggle (500 on audit log keyword) |
| `bi:bi_dashboard_delete` | POST | 500 FAIL | 404 PASS | PASS | Dashboard delete action (500 on audit log keyword) |
| `bi:bi_dashboard_widget_list` | GET | 200 PASS | N/A | PASS | Widget list view (500 if `?dashboard=invalid`) |
| `bi:bi_dashboard_widget_list (filtered)` | GET | 200 PASS | N/A | PASS | Filtered by dashboard, widget_type |
| `bi:bi_dashboard_widget_create` | GET | 200 PASS | N/A | PASS | Widget create form |
| `bi:bi_dashboard_widget_detail` | GET | 200 PASS | 404 PASS | PASS | Widget detail view & cross-tenant IDOR |
| `bi:bi_dashboard_widget_edit` | GET | 200 PASS | 404 PASS | PASS | Widget edit form & cross-tenant IDOR |
| `bi:bi_dashboard_widget_data` | GET | 200 PASS | 404 PASS | PASS | Widget JSON telemetry API & cross-tenant IDOR |
| `bi:bi_dashboard_widget_delete` | POST | 500 FAIL | 404 PASS | PASS | Widget delete action (500 on audit log keyword) |
| `bi:bi_dashboard_bookmark_list` | GET | 200 PASS | N/A | PASS | Bookmark list view (500 if `?dashboard=invalid`) |
| `bi:bi_dashboard_bookmark_create` | GET | 200 PASS | N/A | PASS | Bookmark create form |
| `bi:bi_dashboard_bookmark_detail` | GET | 200 PASS | 404 PASS | PASS | Bookmark detail view & cross-tenant IDOR |
| `bi:bi_dashboard_bookmark_edit` | GET | 200 PASS | 404 PASS | PASS | Bookmark edit form & cross-tenant IDOR |
| `bi:bi_dashboard_bookmark_apply` | GET | 302 PASS | 404 PASS | PASS | Bookmark apply redirect & cross-tenant IDOR |
| `bi:bi_dashboard_bookmark_delete` | POST | 500 FAIL | 404 PASS | PASS | Bookmark delete action (500 on audit log keyword) |
| `bi:bi_dashboard_filter_list` | GET | 200 PASS | N/A | PASS | Filter list view (500 if `?dashboard=invalid`) |
| `bi:bi_dashboard_filter_create` | GET | 200 PASS | N/A | PASS | Filter create form |
| `bi:bi_dashboard_filter_detail` | GET | 200 PASS | 404 PASS | PASS | Filter detail view & cross-tenant IDOR |
| `bi:bi_dashboard_filter_edit` | GET | 200 PASS | 404 PASS | PASS | Filter edit form & cross-tenant IDOR |
| `bi:bi_dashboard_filter_delete` | POST | 500 FAIL | 404 PASS | PASS | Filter delete action (500 on audit log keyword) |

---

## Pass 6: Security Reviewer (Inline)

### Critical
1. `apps/bi/views/Dashboards/BiDashboards.py:128-135`, `BiDashboardWidgets.py:118-125`, `BiDashboardBookmarks.py:117-124`, `BiDashboardFilters.py:90-97`, and all other `write_audit_log` callsites — **Wrong `write_audit_log` signature breaks ALL mutations**: Every call uses `write_audit_log(tenant=..., actor=..., action=..., target_model=..., target_id=..., changes=...)` but the real signature is `write_audit_log(user, obj, action, changes=None, tenant=None)`. This causes `TypeError` 500 on every create/edit/delete/publish/duplicate action. Fix: Rewrite all calls to `write_audit_log(request.user, <instance>, "<action>", changes=..., tenant=request.tenant)`.

### Important
1. `apps/bi/views/Dashboards/BiDashboardCanvasViews.py:60` — **Cross-User Bookmark IDOR**: `?bookmark=<id>` loads any tenant bookmark without ownership/sharing scope. Fix: Add `.filter(Q(user=request.user) | Q(is_shared=True))` to the bookmark lookup.
2. `apps/bi/views/Dashboards/BiDashboardBookmarks.py:206` — **Bookmark Apply Missing Ownership Check**: `bi_dashboard_bookmark_apply` loads and applies any bookmark (including other users' private bookmarks) without scoping. Fix: Add guard `if bookmark.user != request.user and not bookmark.is_shared and not getattr(request, "is_tenant_admin", False): return HttpResponseForbidden(...)`.
3. `apps/bi/views/Dashboards/BiDashboardCanvasViews.py:119-120` — **Canvas Builder Missing Authorization**: `@login_required` only; any tenant member can modify widget positions via AJAX POST. Fix: Add `@tenant_admin_required` or author check.
4. `apps/bi/views/Dashboards/BiDashboardCanvasViews.py:21-40, 97-116` — **Unpublished Draft Dashboards Exposed**: Both `canvas_view` and `kiosk_view` render without checking `dashboard.is_published`. Fix: Return 403 if `not dashboard.is_published and not (is_superuser or is_tenant_admin or dashboard.created_by == request.user)`.
5. `apps/bi/views/Dashboards/BiDashboardCanvasViews.py:128-146` — **Unvalidated AJAX JSON Coordinate Ingestion**: Raw user-supplied JSON values for `pos_x`, `pos_y`, `width_cols`, `height_rows` are passed directly to `.update()` without type checking or bounds validation. Fix: Validate types are `int`, clamp bounds (`0 <= pos_x <= 11`, `1 <= width_cols <= 12`, etc.).
6. `apps/bi/views/Dashboards/BiDashboardCanvasViews.py:145-146` — **Exception Message Leaks Internal State**: `str(e)` is returned directly in `JsonResponse({"status": "error", "message": str(e)})`, potentially exposing internal model names, SQL errors, or file paths. Fix: Return generic error message `"Invalid position data"`.
7. `apps/bi/forms/Dashboards/BiDashboardForms.py:13-27` — **`is_published` Mass Assignment**: `BiDashboardForm.Meta.fields` includes `is_published`, allowing any user submitting the form to self-publish dashboards bypassing the dedicated `bi_dashboard_publish` toggle which requires `@tenant_admin_required`. Fix: Remove `is_published` from `Meta.fields`; publication is managed exclusively via the publish endpoint.

### Minor
1. `apps/bi/views/Dashboards/BiDashboardCanvasViews.py:33-36` — Broken role check uses `getattr(request.user, "roles", None)` and `.filter(code=...)` but NavERP `User` has single `role` FK with `name` field. Fix: Use `request.user.role and request.user.role.name.lower() == dashboard.role_required.lower()`.
2. `apps/bi/views/Dashboards/BiDashboardBookmarks.py:211` — Hardcoded redirect URL bypasses reverse routing. Fix: Use `reverse("bi:bi_dashboard_canvas_view", ...)`.

---

## Deduplicated & Prioritized Findings Checklist (All 6 Passes)

### Critical
- [ ] **C1**: `apps/bi/views/Dashboards/*.py` — All `write_audit_log` calls use wrong signature (`actor=...`, `target_model=...`, `target_id=...`) instead of positional `(user, obj, action, changes=None, tenant=None)`, causing `TypeError` 500 on every mutating action (create/edit/delete/publish/duplicate across all 4 entities). Fix: Rewrite all 15+ callsites to `write_audit_log(request.user, <instance>, "<action>", changes=..., tenant=request.tenant)`.
- [ ] **C2**: `templates/bi/dashboards/dashboard/detail.html:109` — Nullable FK in filter argument raises `VariableDoesNotExist` 500 when `created_by` is None (L10). Fix: Guard with `{% if dashboard.created_by %}...{% else %}System Seed{% endif %}`.

### Important
- [ ] **I1**: `apps/bi/views/Dashboards/BiDashboardWidgets.py:38`, `BiDashboardBookmarks.py:36`, `BiDashboardFilters.py:33` — Unguarded `dashboard_id` filter raises `ValueError` 500 on non-numeric `?dashboard=abc` (L11). Fix: Guard with `if dashboard_id and dashboard_id.isdigit():` in all 3 views.
- [ ] **I2**: `apps/bi/views/Dashboards/BiDashboardCanvasViews.py:59` — Unguarded `bookmark_id` raises `ValueError` 500 on non-numeric `?bookmark=abc` (L11). Fix: `if bookmark_id and bookmark_id.isdigit():`.
- [ ] **I3**: `templates/bi/dashboards/canvas/viewer.html:111,127` — Invalid `dictsort` filter on `request.GET` breaks active filter selection. Fix: Attach `f.current_value = filter_values.get(f.filter_key, f.default_value)` in view and compare in template.
- [ ] **I4**: `apps/bi/views/Dashboards/BiDashboardCanvasViews.py:119-120` — Missing authorization on canvas builder (AJAX position mutation). Fix: Add `@tenant_admin_required` or creator/admin check.
- [ ] **I5**: `apps/bi/views/Dashboards/BiDashboardCanvasViews.py:60` & `BiDashboardBookmarks.py:206` — Cross-user bookmark IDOR: private bookmarks loadable by any tenant member. Fix: Scope with `Q(user=request.user) | Q(is_shared=True)` and add ownership check on `apply`.
- [ ] **I6**: `apps/bi/views/Dashboards/BiDashboardCanvasViews.py:21-40, 97-116` — Unpublished draft dashboards accessible to regular users. Fix: Return 403 if `not dashboard.is_published and not is_admin_or_author`.
- [ ] **I7**: `apps/bi/views/Dashboards/BiDashboardCanvasViews.py:33-36` — Broken role resolution check (`user_roles.filter(code=...)` but User has single `role` FK with `name`). Fix: Check `request.user.role.name.lower() == dashboard.role_required.lower()`.
- [ ] **I8**: `apps/bi/forms/Dashboards/BiDashboardForms.py:47` — `slug` field `required=True` blocks auto-slugification in `clean()`. Fix: `self.fields["slug"].required = False`.
- [ ] **I9**: `apps/bi/forms/Dashboards/BiDashboardFilterForms.py:39` — `filter_key` field `required=True` blocks auto-slugification in `clean()`. Fix: `self.fields["filter_key"].required = False`.
- [ ] **I10**: `apps/bi/management/commands/seed_bi.py:58` — Flush block omits 10.8 dashboard models. Fix: Add all 4 model deletes to flush.
- [ ] **I11**: `templates/bi/dashboards/widget/list.html:132`, `bookmark/list.html:125`, `filter/list.html:118` — Actions columns omit POST-delete forms with CSRF+confirm. Fix: Add inline POST delete forms.
- [ ] **I12**: `apps/bi/forms/Dashboards/BiDashboardBookmarkForms.py:9-37` — Excluded `user` field bypasses uniqueness validation, causing unhandled `IntegrityError` 500 on duplicate names. Fix: Accept user in `__init__` and validate uniqueness in `clean()`.
- [ ] **I13**: `templates/bi/dashboards/dashboard/detail.html:48-73` vs `apps/bi/views/Dashboards/BiDashboards.py:118,150,180,200` — Creator action buttons display for authors but views enforce `@tenant_admin_required` → 403. Fix: Align permissions.
- [ ] **I14**: `apps/bi/views/Dashboards/BiDashboards.py:90` — Missing `select_related("calculated_measure", "semantic_model", "warehouse_table")` on detail widgets queryset → N+1. Fix: Add select_related.
- [ ] **I15**: `apps/bi/views/Dashboards/BiDashboards.py:92-94` — Missing `.select_related("user")` on detail bookmarks queryset → N+1. Fix: Add select_related.
- [ ] **I16**: `apps/bi/views/Dashboards/BiDashboards.py:21-23` — 3 separate `.count()` queries instead of single `.aggregate()`. Fix: Consolidate.
- [ ] **I17**: `apps/bi/views/Dashboards/BiDashboards.py:81`, `BiDashboardCanvasViews.py:27,102,125` — Redundant `prefetch_related` discarded by subsequent `.filter()` calls. Fix: Remove wasted prefetches.
- [ ] **I18**: `apps/bi/forms/Dashboards/BiDashboardForms.py:14` — `is_published` in `Meta.fields` allows mass-assignment bypass of dedicated publish endpoint. Fix: Remove from fields.
- [ ] **I19**: `apps/bi/views/Dashboards/BiDashboardCanvasViews.py:145-146` — Exception `str(e)` leaked in JSON response. Fix: Return generic error message.
- [ ] **I20**: `apps/bi/views/Dashboards/BiDashboardCanvasViews.py:128-146` — Unvalidated coordinate values from raw JSON. Fix: Type-check + bounds-clamp.

### Minor
- [ ] **M1**: `apps/bi/views/Dashboards/BiDashboardBookmarks.py:211` — Hardcoded URL in bookmark apply. Fix: Use `reverse(...)`.
- [ ] **M2**: `apps/bi/views/Dashboards/BiDashboardCanvasViews.py:97` — Kiosk view ignores `is_kiosk_enabled`. Fix: Return 403 when disabled.
- [ ] **M3**: `apps/bi/views/Dashboards/BiDashboards.py:227` — Duplicate slug collision unhandled. Fix: Check existence and append suffix.
- [ ] **M4**: `apps/bi/views/Dashboards/BiDashboardCanvasViews.py:134` — Builder AJAX missing `AuditLog` entry. Fix: Add `write_audit_log`.
- [ ] **M5**: `templates/bi/dashboards/canvas/viewer.html:83,137,161` & `builder.html:32,61` — Missing `aria-label` on icon-only buttons. Fix: Add descriptive labels.
- [ ] **M6**: `templates/bi/dashboards/canvas/viewer.html:33-38` — Missing outside-click dismiss on bookmark menu. Fix: Add document click listener.
- [ ] **M7**: `templates/bi/dashboards/widget/detail.html` — Unrendered `data_preview` context var. Fix: Add preview card.
- [ ] **M8**: `templates/bi/dashboards/bookmark/detail.html` — Unrendered `crossfilter_state_pretty` context var. Fix: Add JSON block.
- [ ] **M9**: `templates/bi/dashboards/dashboard/list.html:151` — N+1 via `{{ d.widgets.count }}` in loop. Fix: Annotate `widget_count` in view.
- [ ] **M10**: `apps/bi/models/Dashboards/BiDashboardBookmarks.py:61-62` — FK hop in `__str__` → N+1 risk (L18). Fix: Simplify to `f"{self.name} ({self.number})"`.
- [ ] **M11**: `apps/bi/views/Dashboards/BiDashboardWidgets.py:50` — Unused `semantic_models` queryset. Fix: Remove.
- [ ] **M12**: `apps/bi/views/Dashboards/BiDashboardWidgets.py:49`, `BiDashboardBookmarks.py:49`, `BiDashboardFilters.py:44` — Heavy field loading on dropdown querysets. Fix: `.only("id", "title")`.
- [ ] **M13**: `apps/bi/views/Dashboards/BiDashboardWidgets.py:23`, `BiDashboardBookmarks.py:21`, `BiDashboardFilters.py:19` — Missing `.defer()` on unrendered JSON fields. Fix: Defer heavy JSON columns.
- [ ] **M14**: `apps/bi/models/Dashboards/BiDashboards.py:95-108` & `BiDashboardWidgets.py:117-130` — Missing composite tenant indexes. Fix: Add `(tenant, -created_at)` and `(tenant, warehouse_table)`.
- [ ] **M15**: `apps/bi/management/commands/seed_bi.py:2115` — Dead `drill_ref` query. Fix: Remove.
- [ ] **M16**: `templates/bi/dashboards/canvas/viewer.html:226` — Duplicate Chart.js script inclusion. Fix: Remove redundant CDN tag.
- [ ] **M17**: `templates/bi/dashboards/dashboard/list.html:70-112` — Theme filter omitted from UI. Fix: Add theme dropdown.
- [ ] **M18**: `templates/bi/dashboards/canvas/viewer.html:35,41` & `builder.html:48,52` — `.count` + iteration dual query. Fix: Use `|length`.
- [ ] **M19**: `apps/bi/views/Dashboards/BiDashboardCanvasViews.py:151-153` — Unbounded queryset fetch in builder. Fix: Slice and `.only()`.
- [ ] **M20**: `templates/bi/dashboards/dashboard/list.html:168-180` — Missing direct edit/delete on card grid. Fix: Add edit/delete to card footer.

