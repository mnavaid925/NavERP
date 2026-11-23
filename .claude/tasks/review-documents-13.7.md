# Review Findings: Sub-module 13.7 Document Security & Access Control

**Base Commit:** `3abacc78c4f4746dac415dea33896cbeafbfc963`
**Head Commit:** `fab9aabc556593c1e8b32680f2a8a38ffe55b252`

---

## 1. Code Reviewer Pass (`code-reviewer`)

### Verdict
Commit after fixing Critical+Important (no Critical bugs found; 4 Important issues identified regarding GET parameter validation, kill-switch authorization and status guarding, and departmental rights simulation).

### Critical
None. Multi-tenant isolation is strictly enforced across models, querysets, and forms (`reject_foreign`, `TenantModelForm`, `TenantUniqueMixin`), migrations are fully synchronized in `0014_...`, and all models declare tenant FKs.

### Important
1. `apps/documents/views/SecurityAccessControl/SecureViewer.py:22` — Unguarded `doc_id` query param: `pk = request.GET.get("doc_id")` passes unvalidated user input directly into `get_object_or_404(docs_qs, pk=pk)`, which raises an unhandled `ValueError` (HTTP 500) when given non-numeric input like `?doc_id=abc` (violating L11). Fix: guard with `.isdigit()`: `if not pk and request.GET.get("doc_id", "").isdigit(): pk = int(request.GET.get("doc_id"))`.
2. `apps/documents/views/SecurityAccessControl/DocumentDrmPolicies.py:146` — Missing privileged authorization gate on emergency kill-switch: `drm_kill_switch` is decorated only with `@login_required`, permitting any regular non-admin user to trigger emergency DRM revocation company-wide. Fix: enforce tenant admin privileges via `@tenant_admin_required` or check `if not (request.user.is_superuser or getattr(request.user, "is_tenant_admin", False)): messages.error(request, "Only tenant administrators can engage the emergency kill-switch."); return redirect("documents:drm_policy_detail", pk=policy.pk)`.
3. `apps/documents/views/SecurityAccessControl/DocumentDrmPolicies.py:150` — Missing view-level status guard on `drm_kill_switch`: the view does not check `if policy.is_revoked:` before calling `policy.revoke()`, so a direct POST can repeatedly re-revoke an already killed policy, overwriting the original audit timestamp and revocation reason. Fix: add a view-level status guard: `if policy.is_revoked: messages.info(request, "This DRM policy has already been revoked."); return redirect("documents:drm_policy_detail", pk=policy.pk)`.
4. `apps/documents/views/SecurityAccessControl/DocumentAccessPermissions.py:233` — Effective rights simulator fails to match departmental ACL rules: `user_dept = getattr(target_user, "department", None)` always evaluates to `None` because the `User` model has no `department` column in NavERP (user departments are mapped via `Employment.org_unit` linked to `target_user.party`, per `apps/core/scoping.py:68`), causing `grantee_type="org_unit"` ACL permissions to never match in the simulator. Fix: import `Employment` and query `employment = Employment.objects.filter(tenant=request.tenant, party=getattr(target_user, "party", None)).order_by("-id").first()`, then use `user_dept = employment.org_unit if employment else None`.
5. `templates/documents/security_access_control/document_drm_policy/detail.html:28` — Missing POST-only Delete action on detail page: `drm_policy_delete` view and URL pattern exist (and the button is present on the list page), but `detail.html` omits the standard POST-only delete button with CSRF token and `confirm(...)` dialog, violating the CRUD completeness contract for detail pages. Fix: add the standard POST-only Delete form button alongside Back and Edit in `page-actions`.

### Minor
1. `apps/documents/views/SecurityAccessControl/DlpIncidents.py:50` & `templates/documents/security_access_control/dlp_incident/list.html:143` — Filter state dropped on pagination: `dlp_incident_list` filters by `policy_id = request.GET.get("policy")` when navigating from a policy detail page, but does not pass `policy_id` to context or append `&policy={{ policy_id }}` to pagination links, causing page 2 to display incidents from all policies. Fix: include `"policy_id": policy_id` in context and add `{% if policy_id %}&policy={{ policy_id }}{% endif %}` to pagination links.
2. `apps/documents/views/SecurityAccessControl/DocumentAccessPermissions.py:70` & `templates/documents/security_access_control/document_access_permission/list.html:191` — Filter state dropped on pagination: `permission_list` filters by `document` and `folder` GET params, but neither `doc_id` nor `folder_id` are passed to template context or pagination links. Fix: include them in context and append `{% if doc_id %}&document={{ doc_id }}{% endif %}{% if folder_id %}&folder={{ folder_id }}{% endif %}` to pagination links.
3. `apps/documents/forms/SecurityAccessControl/DocumentAccessPermissions.py:83` — Stale grantee foreign keys: if a user changes `grantee_type` (e.g. from `org_unit` to `user`), the unselected FK fields (`org_unit`, `role_name`) are not cleared in `clean()`. Fix: clear non-matching grantee fields based on `grantee_type` in `clean()`.

### Done well
- Robust tenant isolation across all 5 models (`DocumentAccessPermission`, `WatermarkPolicy`, `DocumentDrmPolicy`, `DlpPolicy`, `DlpIncident`) inheriting `TenantNumbered` with retry collision sequences and composite tenant unique constraints.
- Sandboxed zero-download secure viewer (`secure_viewer.html`) with client-side screen-shield focus-loss blur, right-click and keyboard interception, and dynamic on-the-fly forensic watermark overlay.
- Watermark text engine with token interpolation (`{{user_name}}`, `{{user_email}}`, `{{classification}}`, `{{ip_address}}`, `{{timestamp}}`) and proper use of `{% verbatim %}` tags in templates to prevent template syntax collisions.
- Strict compliance with `static/css/theme.css` color palettes (`badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-slate`, `badge-muted`) with zero unauthorized badge classes.
- Seeder idempotency verified with safe `--flush` wipe ordering and tenant scoping in `seed_documents.py`.

### Suggested tests
- `apps/documents/tests/test_security_access_control_views.py`:
  - `test_secure_viewer_junk_doc_id`: Assert `GET /documents/secure-viewer/?doc_id=invalid` does not 500 (returns 404 or falls back to first document).
  - `test_drm_kill_switch_requires_admin`: Assert non-tenant-admin users receiving 403 or redirect when posting to `drm_kill_switch`.
  - `test_drm_kill_switch_status_guard`: Assert repeated POST to `drm_kill_switch` on an already revoked policy does not update `revoked_at`.
  - `test_permission_simulate_org_unit_resolution`: Assert `permission_simulate` matches `grantee_type="org_unit"` permissions when user has an active `Employment` with that `OrgUnit`.
- `apps/documents/tests/test_security_access_control_models.py`:
  - `test_watermark_policy_token_rendering`: Assert `render_watermark()` interpolates user and document attributes without leaking raw tokens.
  - `test_dlp_policy_pci_card_inspection`: Assert `inspect_text()` detects credit card PCI numbers and returns redacted snippets.
- `apps/documents/tests/test_security_access_control_security.py`:
  - `test_security_access_control_cross_tenant_isolation`: Assert cross-tenant IDOR requests to permission, watermark, DRM, and DLP detail/edit/delete endpoints return 404.

### Routing
- performance-reviewer: Review `DlpPolicy.incidents` feed in `dlp_policy_detail` to verify index coverage on `(tenant, policy, resolution_status)`.
- security-reviewer: Verify that the client-side sandboxing controls in `secure_viewer.html` (clipboard, print, and context menu blockers) are documented as visual deterrents and backed by server-side payload access controls.
- frontend-reviewer: Review `kill_switch_modal` in `document_drm_policy/detail.html` to ensure Escape key event listeners close the modal cleanly.


---

## 2. Explorer Reviewer Pass (`explorer`)

### Verdict
PASS WITH MINOR FINDINGS. Architectural layout adheres cleanly to the 1-to-1 entity-by-entity package structure, complete tenant isolation is maintained, and all pre-build contract obligations are satisfied.

### Critical
None.

### Important
1. `apps/documents/views/SecurityAccessControl/SecureViewer.py:22-27` — Unchecked `doc_id` query param causes HTTP 500: `pk = request.GET.get("doc_id")` passes unvalidated user input into `get_object_or_404(docs_qs, pk=pk)`, raising `ValueError` on non-numeric input (e.g. `?doc_id=abc`), violating L11. Fix: guard with `.isdigit()` before setting `pk`.

### Minor
1. `apps/documents/{models,forms,views,urls}/SecurityAccessControl/` — Missing package `__init__.py` markers: Add empty `__init__.py` files in each of the 4 `SecurityAccessControl` subdirectories for consistency with sibling modules.
2. `apps/documents/forms/SecurityAccessControl/DlpPolicies.py:25` — Form omits `target_document_types` and `target_classifications` JSON fields: Contract section 2.4 specifies these in `Meta.fields`.
3. `apps/documents/models/SecurityAccessControl/DocumentAccessPermissions.py:34,43` — CSS badge substitution: Mapped `badge-purple` to `badge-slate` and `badge-amber` to maintain strict compliance with `static/css/theme.css` (L33).

### Done well
- Strict 1-to-1 backend layer alignment across models, forms, views, and urls.
- All models, forms, and views re-exported in package `__init__.py` and included in `__all__`.
- Literal URL routes strictly precede parameterized routes.
- Full contract compliance across all 5 models and their view context dictionaries.
- Multi-tenancy and audit logging enforced across all mutation operations.


---

## 3. Frontend Reviewer Pass (`frontend-reviewer`)

### Verdict
Commit after fixing Critical+Important (no Critical bugs found; 2 Important issues identified regarding missing badge class method lookup in Secure Viewer and missing POST-only Delete action on DRM Policy detail page).

### Critical
None.

### Important
1. `templates/documents/security_access_control/secure_viewer.html:19,48` — Invalid badge property on `Document` model renders blank badge classes: Lines 19 and 48 call `.classification_badge`, but `Document` model defines `classification_badge_class`, resulting in unstyled badge pills `<span class="badge ">`. Fix: use `{{ document.classification_badge_class }}` and `{{ doc.classification_badge_class }}`.
2. `templates/documents/security_access_control/document_drm_policy/detail.html:28-44` — Missing POST-only Delete action in detail page actions: `drm_policy_delete` view and URL pattern exist, but `detail.html` omits the standard POST-only delete button with CSRF token and `confirm(...)` dialog. Fix: add the standard POST-only Delete form button to `page-actions`.

### Minor
1. `templates/documents/security_access_control/secure_viewer.html:215-219` — Unconditional `Ctrl+P` print blocking ignores `allow_print` context: Keyboard handler intercepts `Ctrl+P` even when `allow_print` is True. Fix: check `allowPrint` before blocking.
2. `templates/documents/security_access_control/dlp_incident/list.html:143-149` — Pagination drops `policy` filter query parameter: Navigating to page 2 drops the policy filter. Fix: append `{% if policy_id %}&policy={{ policy_id }}{% endif %}` to pagination links.
3. `templates/documents/security_access_control/document_access_permission/list.html:191-195` — Pagination drops `document` and `folder` filter query parameters. Fix: append `{% if doc_id %}&document={{ doc_id }}{% endif %}{% if folder_id %}&folder={{ folder_id }}{% endif %}` to pagination links.
4. `templates/documents/security_access_control/watermark_policy/preview.html:71` — Hardcoded badge class in visual studio preview: Line 71 hardcodes `<span class="badge badge-amber">`. Fix: use `{{ policy.classification_badge|default:'badge-amber' }}`.

### Done well
- Strict Theme.css badge compliance across all 17 templates (no invalid classes).
- Zero comment leaks (`{# ... #}`).
- Robust CSRF and POST protections on all mutating actions.
- Sandboxed zero-download viewer with focus-loss blur overlay, context-menu blocking, and forensic watermark overlay.
- Visual Watermark Studio with real-time slider controls.
- Effective Rights Simulator with rich ACL contributing rule breakdown.


---

## 4. Performance Reviewer Pass (`performance-reviewer`)

### Verdict
Strong adherence to core database performance hygiene in primary list views (all 5 list views enforce pagination before evaluation and configure `select_related`). 1 Critical issue (unbounded, unprojected table scans in `permission_simulate`), 4 Important issues (redundant queries on `permission_list`, lazy FK on `document.department` in `secure_viewer`, lazy FK lookup on `self.tenant.name` in `render_watermark`, and missing `list_select_related` in Django Admin).

### Critical
1. `apps/documents/views/SecurityAccessControl/DocumentAccessPermissions.py:183-184` — Unbounded, unprojected table scans in `permission_simulate`: Queries fetch all documents and users for the tenant without limits or `.only(...)`. Fix: add `.only("id", "number", "title", "classification")[:200]` and `.only("id", "username", "first_name", "last_name")[:200]`.

### Important
1. `apps/documents/views/SecurityAccessControl/DocumentAccessPermissions.py:67-68` — Wasted database queries in `permission_list`: `documents` and `folders` are queried (`[:100]`) and passed to context, but not rendered in template filters. Fix: remove unused queries and context variables.
2. `apps/documents/views/SecurityAccessControl/SecureViewer.py:20` — Missing `select_related("department")` in `secure_viewer`: Template renders `document.department.name`, causing an extra query. Fix: add `.select_related("department")` to `docs_qs`.
3. `apps/documents/models/SecurityAccessControl/WatermarkPolicies.py:141` — Lazy FK evaluation of `self.tenant.name` in `WatermarkPolicy.render_watermark`: Accessing `self.tenant.name` triggers an extra query. Fix: pass `tenant_name` or prefetch tenant.
4. `apps/documents/admin.py:242-246,273-278` — Missing `list_select_related` in Django Admin: `DocumentAccessPermissionAdmin` and `DlpIncidentAdmin` render foreign key columns without `list_select_related`, triggering `1 + 4N` queries. Fix: add `list_select_related` tuples.

### Minor
1. `apps/documents/views/SecurityAccessControl/SecureViewer.py:46-60` — Sequential 2-query fallback for DRM policy resolution: Can be consolidated with `Q(target_document=document) | Q(classification=document.classification)`.
2. `apps/documents/models/SecurityAccessControl/DocumentAccessPermissions.py:121` & `DlpIncidents.py:113` — Missing composite index on `(tenant, created_at)` for reverse-chronological pagination.
3. `apps/documents/models/SecurityAccessControl/DocumentDrmPolicies.py:107` — Missing composite index on `(tenant, target_document, is_active, is_revoked)`.
4. `apps/documents/views/SecurityAccessControl/WatermarkPolicies.py:176` — Unprojected `policies` queryset in `watermark_preview`: Add `.only("id", "name", "classification")`.

### Done well
- Clean N+1 prevention across all 5 list views with explicit `select_related`.
- Denormalized `incident_count` counter on `DlpPolicy` avoids subquery performance degradation.
- Paginator count caching properly utilized.
- In-memory sliced length used in `dlp_policy_detail`.


---

## 5. QA Smoke Tester Pass (`qa-smoke-tester`)

### Verdict
PASS — All 75 runtime verification tests for Sub-module 13.7 (Document Security & Access Control) passed cleanly. 0 Critical, 0 Important, 0 Minor defects identified.

### Critical
None.

### Important
None.

### Minor
None.

### Done well
- Rigorous Multi-Tenant Isolation (Anti-IDOR): All cross-tenant access attempts by `admin_acme` targeting `globex` entities returned strict `404 Not Found` across detail, edit, delete (POST), custom action (kill-switch, resolve), and viewer routes.
- Interactive ACL Simulator: The permission simulation tool (`documents:permission_simulate`) dynamically aggregates active document and folder permissions, accounts for role inheritance, and accurately diagnoses owner/admin bypasses.
- Zero-Download Secure Web Viewer: DOM sandbox correctly renders forensic watermarking, screen-shield blur overlays, and right-click interceptors linked directly to the document's effective DRM policy.
- Dynamic Watermarking Engine: Runtime token interpolation (`{{user_email}}`, `{{ip_address}}`, etc.) functions seamlessly on both the policy detail view and the interactive visual watermark studio.
- Resilient Query & Filter Handling: List views gracefully handle garbage filter values and invalid/far pagination (`?page=abc`, `?page=999999`) without raising HTTP 500 errors.
- Navigation & Authentication Guard: All 6 `LIVE_LINKS["13.7"]` entries resolve to active routes and enforce `@login_required` redirects (`302`) for unauthenticated requests.
