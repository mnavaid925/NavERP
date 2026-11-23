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
