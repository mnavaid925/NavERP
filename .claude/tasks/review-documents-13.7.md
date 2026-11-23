# Consolidated Review Findings: Sub-module 13.7 Document Security & Access Control

**Base Commit:** `3abacc78c4f4746dac415dea33896cbeafbfc963`
**Head Commit:** `fab9aabc556593c1e8b32680f2a8a38ffe55b252`

---

## Executive Summary
Six serial reviewer passes were executed in accordance with project guidelines:
1. `code-reviewer`: Evaluated multi-tenancy, authorization, form handling, and error cases.
2. `explorer`: Validated 1-to-1 package layout, contract compliance, re-exports, and URLs.
3. `frontend-reviewer`: Evaluated design system compliance (theme.css classes), accessibility, and template safety.
4. `performance-reviewer`: Checked query counts, N+1 lookups, select_related, and indexing.
5. `qa-smoke-tester`: Executed 75 runtime tests (200 OK, content assertion, 404 IDOR isolation). All 75 passed.
6. `security-reviewer`: Conducted security review on ACL enforcement, privilege escalation, and ReDoS.

---

## Actionable Findings Checklist

### Critical (Must Fix Before Merge)
- [x] **C1: Missing administrative authorization (`@tenant_admin_required`) on privileged actions and policy mutations**
  - **Files & Lines**:
    - `apps/documents/views/SecurityAccessControl/DocumentDrmPolicies.py:147` (`drm_kill_switch`)
    - `apps/documents/views/SecurityAccessControl/DlpIncidents.py:90` (`dlp_incident_resolve`)
    - `apps/documents/views/SecurityAccessControl/DocumentAccessPermissions.py:114,142,168` (`permission_create`, `permission_edit`, `permission_delete`)
    - `apps/documents/views/SecurityAccessControl/DocumentDrmPolicies.py:84,115,136` (`drm_policy_create`, `drm_policy_edit`, `drm_policy_delete`)
    - `apps/documents/views/SecurityAccessControl/DlpPolicies.py:83,114,136` (`dlp_policy_create`, `dlp_policy_edit`, `dlp_policy_delete`)
    - `apps/documents/views/SecurityAccessControl/WatermarkPolicies.py:86,117,138` (`watermark_create`, `watermark_edit`, `watermark_delete`)
  - **Description**: Mutating security policies, emergency DRM kill-switch, DLP incident resolution, and granting/editing document permissions are decorated only with `@login_required` instead of `@tenant_admin_required`, allowing standard employees to escalate privileges or revoke policies company-wide.
  - **Fix**: Add `@tenant_admin_required` (from `apps.core.decorators`) to these views and hide administrative buttons in templates when the user is not a tenant admin.
- [x] **C2: Unbounded table scan and memory bloat in `permission_simulate`**
  - **Files & Lines**: `apps/documents/views/SecurityAccessControl/DocumentAccessPermissions.py:183-184`
  - **Description**: On every hit to `/documents/permissions/simulate/`, queries fetch all documents and users for the tenant without limits or `.only(...)` column projections. In enterprise tenants with 10k+ documents, this causes full table scans and high memory consumption.
  - **Fix**: Add `.only("id", "number", "title", "classification")[:200]` and `.only("id", "username", "first_name", "last_name")[:200]`.

---

### Important (Should Fix Before Merge)
- [x] **I1: Unchecked `doc_id` query param causes HTTP 500 on non-numeric input in `SecureViewer`**
  - **Files & Lines**: `apps/documents/views/SecurityAccessControl/SecureViewer.py:22-27`
  - **Description**: `pk = request.GET.get("doc_id")` passes unvalidated input to `get_object_or_404(docs_qs, pk=pk)`, raising `ValueError` on non-numeric input (e.g. `?doc_id=abc`), violating L11.
  - **Fix**: Guard with `if not pk and request.GET.get("doc_id", "").strip().isdigit(): pk = int(request.GET.get("doc_id", "").strip())`.
- [x] **I2: Unenforced permissions and revocation bypass in Secure Web Viewer**
  - **Files & Lines**: `apps/documents/views/SecurityAccessControl/SecureViewer.py:20-86`
  - **Description**:
    1. `secure_viewer` retrieves documents without checking if user is document owner, tenant admin, or has `can_read` grant in `DocumentAccessPermission`.
    2. If a matching `DocumentDrmPolicy` has `is_revoked=True`, `secure_viewer` filters `is_revoked=False` when fetching policies and falls back to rendering the document unblocked rather than terminating access.
  - **Fix**: Check read permission or admin status before displaying document; if matching DRM policy is revoked (`is_revoked=True`), block viewing with an emergency revocation notice.
- [x] **I3: Missing view-level status guard on `drm_kill_switch`**
  - **Files & Lines**: `apps/documents/views/SecurityAccessControl/DocumentDrmPolicies.py:150`
  - **Description**: The view does not check `if policy.is_revoked:` before calling `policy.revoke()`, so a direct POST can repeatedly re-revoke an already killed policy, overwriting audit timestamp and reason.
  - **Fix**: Add view-level guard: `if policy.is_revoked: messages.info(request, "This DRM policy has already been revoked."); return redirect("documents:drm_policy_detail", pk=policy.pk)`.
- [x] **I4: Departmental ACL rules fail to match in `permission_simulate`**
  - **Files & Lines**: `apps/documents/views/SecurityAccessControl/DocumentAccessPermissions.py:233-247`
  - **Description**: `user_dept = getattr(target_user, "department", None)` evaluates to `None` because `User` model has no `department` column in NavERP (mapped via `Employment.org_unit` on `target_user.party`).
  - **Fix**: Resolve `user_dept` via `Employment.objects.filter(tenant=request.tenant, party=getattr(target_user, "party", None)).order_by("-id").first()`.
- [x] **I5: Missing POST-only Delete action on DRM Policy detail page**
  - **Files & Lines**: `templates/documents/security_access_control/document_drm_policy/detail.html:28-44`
  - **Description**: `drm_policy_delete` view and URL pattern exist, but `detail.html` omits the standard POST-only delete button with CSRF token and `confirm(...)` dialog.
  - **Fix**: Add the standard POST-only Delete form button to `page-actions`.
- [x] **I6: Invalid badge property on `Document` in `secure_viewer.html`**
  - **Files & Lines**: `templates/documents/security_access_control/secure_viewer.html:19,48`
  - **Description**: Lines 19 and 48 call `document.classification_badge`, but on `Document` model the property is `classification_badge_class`, resulting in unstyled badge pills `<span class="badge ">`.
  - **Fix**: Use `{{ document.classification_badge_class }}` and `{{ doc.classification_badge_class }}`.
- [x] **I7: Wasted database queries in `permission_list`**
  - **Files & Lines**: `apps/documents/views/SecurityAccessControl/DocumentAccessPermissions.py:67-68`
  - **Description**: `documents` and `folders` are queried (`[:100]`) and passed to context, but not rendered in template filters.
  - **Fix**: Remove unused queries and context variables.
- [x] **I8: Missing `select_related("department")` in `secure_viewer`**
  - **Files & Lines**: `apps/documents/views/SecurityAccessControl/SecureViewer.py:20` & `templates/documents/security_access_control/secure_viewer.html:145`
  - **Description**: Template renders `document.department.name`, causing an extra query on every viewer load.
  - **Fix**: Add `.select_related("department")` to `docs_qs`.
- [x] **I9: Missing `list_select_related` in Django Admin**
  - **Files & Lines**: `apps/documents/admin.py:242-246,273-278`
  - **Description**: `DocumentAccessPermissionAdmin` and `DlpIncidentAdmin` render foreign key columns without `list_select_related`, triggering `1 + 4N` queries.
  - **Fix**: Add `list_select_related` to both admin classes.
- [ ] **I10: ReDoS protection in Custom DLP Rules**
  - **Files & Lines**: `apps/documents/forms/SecurityAccessControl/DlpPolicies.py:66-73`
  - **Description**: `DlpPolicyForm.clean_custom_regex` does not prevent catastrophic backtracking regexes.
  - **Fix**: Reject nested quantifiers (e.g. `(a+)+`) or excessively complex patterns during form validation.

---

### Minor (Clean-up & Polish)
- [ ] **M1: Form inheritance inconsistency in `DlpIncidentResolveForm`**
  - **Files & Lines**: `apps/documents/forms/SecurityAccessControl/DlpIncidents.py:6`
  - **Description**: Inherits from `forms.ModelForm` instead of `TenantModelForm`.
  - **Fix**: Inherit from `TenantModelForm`.
- [ ] **M2: Filter state dropped on pagination in `dlp_incident_list` and `permission_list`**
  - **Files & Lines**:
    - `templates/documents/security_access_control/dlp_incident/list.html:143`
    - `templates/documents/security_access_control/document_access_permission/list.html:191`
  - **Description**: Pagination links do not preserve `policy` or `document`/`folder` filters.
  - **Fix**: Append filter params to pagination links.
- [ ] **M3: Stale grantee foreign keys in `DocumentAccessPermissionForm`**
  - **Files & Lines**: `apps/documents/forms/SecurityAccessControl/DocumentAccessPermissions.py:83`
  - **Description**: If user changes `grantee_type` (e.g. from `org_unit` to `user`), non-matching FK fields are not cleared in `clean()`.
  - **Fix**: Clear non-matching grantee fields based on `grantee_type`.
- [ ] **M4: Missing package `__init__.py` markers in `SecurityAccessControl` subdirectories**
  - **Files & Lines**: `apps/documents/{models,forms,views,urls}/SecurityAccessControl/`
  - **Description**: Add empty `__init__.py` files for consistency with sibling packages.
  - **Fix**: Create empty `__init__.py` in each.
- [ ] **M5: Hardcoded badge in visual studio preview**
  - **Files & Lines**: `templates/documents/security_access_control/watermark_policy/preview.html:71`
  - **Description**: Line 71 hardcodes `badge-amber`.
  - **Fix**: Use `{{ policy.classification_badge|default:'badge-amber' }}`.
- [ ] **M6: Unconditional `Ctrl+P` blocking in `secure_viewer.html`**
  - **Files & Lines**: `templates/documents/security_access_control/secure_viewer.html:215-219`
  - **Description**: Intercepts `Ctrl+P` even when `allow_print` is True.
  - **Fix**: Check `allowPrint` before blocking.
- [ ] **M7: Missing composite indexes for ordering**
  - **Files & Lines**: `apps/documents/models/SecurityAccessControl/DocumentAccessPermissions.py:121`, `DlpIncidents.py:113`
  - **Description**: Missing index on `(tenant, created_at)`.
  - **Fix**: Add composite indexes in next migration or future pass.
