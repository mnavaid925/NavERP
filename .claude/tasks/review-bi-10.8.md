# Consolidated Review Findings: Sub-module 10.8 Dashboards & Visualization

**Commit Range:** `7d343a2af8e7ae61ab20168cfdec164cec1e4ed0...HEAD`  
**Review Passes:**
1. Code Reviewer — Completed
2. Explorer (Architecture & Contract) — Completed
3. Frontend Reviewer — Pending
4. Performance Reviewer — Pending
5. QA Smoke Tester — Pending
6. Security Reviewer — Pending

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

