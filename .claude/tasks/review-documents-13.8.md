# Review Findings: Sub-module 13.8 Collaboration & Sharing

## Overview
- **Changeset Reviewed**: `3abacc78c4f4746dac415dea33896cbeafbfc963...HEAD`
- **Review Passes Executed**: 6 sequential passes (`code-reviewer` -> `explorer` -> `frontend-reviewer` -> `performance-reviewer` -> `qa-smoke-tester` -> `security-reviewer`)
- **Status**: Ready for Phase 5 remediation by `code-fixer`

---

## Critical

### [ ] C1: `tenant_id` null constraint violation on entity create POST endpoints
- **Location**:
  - `apps/documents/views/CollaborationSharing/DocumentShares.py:118-120`
  - `apps/documents/views/CollaborationSharing/CoauthorSessions.py:85-87`
  - `apps/documents/views/CollaborationSharing/DocumentTasks.py:110-112`
- **Problem**: Submitting valid form data to `document_share_create`, `coauthor_session_create`, or `document_task_create` raises `django.db.utils.IntegrityError: Column 'tenant_id' cannot be null` and returns HTTP 500. `TenantModelForm` excludes `tenant` from form fields, and the create views called `form.save()` directly without setting `obj.tenant = request.tenant`.
- **Fix**: In each create view, assign `tenant` to the instance before saving:
  ```python
  obj = form.save(commit=False)
  obj.tenant = request.tenant
  obj.save()
  form.save_m2m()
  ```

### [ ] C2: HTTP 500 crash on `document_share_detail` when share activities include guest/unauthenticated actions
- **Location**: `templates/documents/collaboration_sharing/document_share/detail.html:200`
- **Problem**: When a share activity is created by an external guest (e.g. `action_type="link_accessed"` or `action_type="file_downloaded"`, where `actor=None`), line 200 executes `By {{ act.actor.get_full_name|default:act.actor.username|default:"Guest" }}`. In Django templates, evaluating filter argument `act.actor.username` crashes with `VariableDoesNotExist: Failed lookup for key [username] in None` (Lesson L10).
- **Fix**: Replace line 200 with the safe property:
  ```html
  By {{ act.actor_display_name }} &bull; {{ act.created_at|date:"M d, Y H:i" }}
  ```

---

## Important

### [ ] I1: Public share preview extends internal staff `base.html` shell
- **Location**: `templates/documents/collaboration_sharing/public_share_preview.html:1`
- **Problem**: `public_share_preview.html` extends `"base.html"`, which includes `partials/sidebar.html` and `partials/topbar.html`. Because `public_share_preview` is an unauthenticated public route intended for external guests, rendering `base.html` exposes the entire internal ERP module navigation structure to unauthenticated visitors.
- **Fix**: Update `public_share_preview.html` to extend `"base_auth.html"`:
  ```html
  {% extends "base_auth.html" %}
  ```

### [ ] I2: Open redirect and `NoReverseMatch` crash on quick actions
- **Location**:
  - `apps/documents/views/CollaborationSharing/DocumentTasks.py:201`
  - `apps/documents/views/CollaborationSharing/DocumentActivities.py:92`
- **Problem**: In `document_task_toggle_complete` and `document_activity_mark_read`, the view executes `redirect(request.META.get("HTTP_REFERER") or "documents:document_task_detail", pk=task.pk)`. When `HTTP_REFERER` is present, passing `pk=task.pk` causes `django.shortcuts.resolve_url` to invoke `reverse(url, kwargs={'pk': ...})`, raising `NoReverseMatch`. Additionally, unvalidated referers allow open redirection to external phishing sites.
- **Fix**: Validate referer using `django.utils.http.url_has_allowed_host_and_scheme(referer, allowed_hosts={request.get_host()})`. Redirect to `referer` alone when valid, and fallback to the specific named route with kwargs when invalid or missing.

### [ ] I3: Broken object-level authorization on notification inbox mark-read
- **Location**: `apps/documents/views/CollaborationSharing/DocumentActivities.py:88-93`
- **Problem**: `document_activity_mark_read` only verifies tenant scoping and does not check that `activity.target_user == request.user`. Any tenant user can submit a POST to mark another user's private notification as read.
- **Fix**: Ensure `activity = get_object_or_404(DocumentActivity.objects.filter(tenant=request.tenant, target_user=request.user), pk=pk)`.

### [ ] I4: Public share usage limit (`max_uses`) and audit logging bypass
- **Location**: `apps/documents/views/CollaborationSharing/PublicShare.py:36-47,78-119`
- **Problem**:
  1. In `public_share_preview`, access recording and activity creation are guarded by `if not password_required and request.method == "GET":`. Submitting passcode via POST bypasses `record_access()` while rendering the decrypted document body.
  2. In `public_share_download`, `share.record_access()` is never called, allowing unlimited downloads regardless of `max_uses`.
- **Fix**:
  1. In `public_share_preview`, implement Post-Redirect-Get upon successful passcode verification so subsequent GET correctly increments `access_count` and logs the audit event.
  2. In `public_share_download`, call `share.record_access()` before returning the file attachment.

### [ ] I5: Active shares count query excludes shares with no expiration date
- **Location**: `apps/documents/views/CollaborationSharing/DocumentShares.py:24`
- **Problem**: `active_count = base_qs.filter(is_active=True, expires_at__gt=timezone.now()).count()` omits active shares with no expiration date (`expires_at=None`) because SQL `NULL > now` evaluates to false.
- **Fix**: Update query to:
  ```python
  active_count = base_qs.filter(is_active=True).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())).count()
  ```

### [ ] I6: Department resolution failure on `User` in CollaborationHub
- **Location**: `apps/documents/views/CollaborationSharing/CollaborationHub.py:21-48`
- **Problem**: `user_org_unit = getattr(user, "department", None)` returns `None` because `User` has no `department` field in NavERP. As a result, department-scoped shares and department-routed tasks are omitted from `my_tasks` and "Shared With Me" tabs.
- **Fix**: Resolve user org unit via:
  ```python
  from apps.core.models import Employment
  employment = Employment.objects.filter(tenant=tenant, party=user.party).order_by("-id").first()
  user_org_unit = employment.org_unit if employment else None
  ```

### [ ] I7: Cross-record relational integrity bypass in forms
- **Location**:
  - `apps/documents/forms/CollaborationSharing/DocumentShares.py:56-72`
  - `apps/documents/forms/CollaborationSharing/DocumentTasks.py:52-65`
  - `apps/documents/forms/CollaborationSharing/CoauthorSessions.py:39-46`
- **Problem**: Forms check that related entities belong to `self.tenant`, but fail to verify that `version.document_id == document.id`, `review_comment.document_id == document.id`, or `draft.document_id == document.id`. Users can bind Document A with Version B from Document C.
- **Fix**: In each form's `clean()`, validate that related child objects belong to the selected document.

### [ ] I8: Broken object-level authorization on document share and coauthor mutations
- **Location**:
  - `apps/documents/views/CollaborationSharing/DocumentShares.py:151-201`
  - `apps/documents/views/CollaborationSharing/CoauthorSessions.py:116-145`
- **Problem**: Any authenticated tenant user can edit, delete, or revoke another user's `DocumentShare` or `CoauthorSession`.
- **Fix**: In `document_share_edit`, `document_share_delete`, `document_share_revoke`, `coauthor_session_edit`, and `coauthor_session_delete`, check that `request.user.is_tenant_admin or obj.shared_by_id == request.user.id or obj.document.owner_id == request.user.id` (or `obj.user_id == request.user.id` for coauthor session). If unauthorized, flash an error and redirect.

### [ ] I9: N+1 queries in views
- **Location**:
  - `apps/documents/views/CollaborationSharing/DocumentShares.py:101-105`
  - `apps/documents/views/CollaborationSharing/DocumentShares.py:19-21`
  - `apps/documents/views/CollaborationSharing/DocumentTasks.py:95-100`
  - `apps/documents/views/CollaborationSharing/DocumentTasks.py:19-21`
- **Problem**:
  - `document_share_detail`: `activities` lacks `.select_related("actor")`.
  - `document_share_list`: missing `"version"` in `select_related`.
  - `document_task_detail`: `task.review_comment.author` accessed without `"review_comment__author"` in `select_related` (Lesson L18).
  - `document_task_list`: `task.review_comment` accessed without `"review_comment"` in `select_related`.
- **Fix**: Add missing foreign keys and chained hops to `select_related`.

### [ ] I10: Tab alias compatibility in CollaborationHub
- **Location**: `apps/documents/views/CollaborationSharing/CollaborationHub.py:71-74`
- **Problem**: View only matches `?tab=activity`. When `?tab=activity_feed` is requested, it falls back to `shared_with_me`.
- **Fix**: Add alias: `if active_tab == "activity_feed": active_tab = "activity"`.

### [ ] I11: Redundant multiple `.count()` queries instead of single aggregate
- **Location**: `apps/documents/views/CollaborationSharing/DocumentShares.py:23-26`, `CoauthorSessions.py:25-28`, `DocumentTasks.py:24-28`, `CollaborationHub.py:61-64`
- **Problem**: Multiple `.count()` SQL queries run across list views and hub stat cards.
- **Fix**: Replace multiple `.count()` calls with single `.aggregate(Count('id', filter=Q(...)))`.

---

## Minor

### [ ] M1: Duplicate "Overdue" option in status dropdown filter
- **Location**: `templates/documents/collaboration_sharing/document_task/list.html:109-112`
- **Problem**: "Overdue" option is hardcoded on line 109 and also looped from `status_choices` on line 111.
- **Fix**: Remove the hardcoded `<option value="overdue">` on line 109.

### [ ] M2: Literal URL route ordering in `DocumentActivities.py`
- **Location**: `apps/documents/urls/CollaborationSharing/DocumentActivities.py:7-9`
- **Problem**: Literal route `path("activities/mark-all-read/", ...)` is declared after parameterized route `path("activities/<int:pk>/", ...)`.
- **Fix**: Reorder `DocumentActivities.py` so that literal routes are strictly before `<int:pk>`.

### [ ] M3: `password_hash` field exposed as editable in Django Admin
- **Location**: `apps/documents/admin.py:281-287`
- **Problem**: `DocumentShareAdmin` displays `password_hash` as editable text in Django admin.
- **Fix**: Add `password_hash` to `readonly_fields` in `DocumentShareAdmin`.

### [ ] M4: Missing regex validation on `color_code` rendered into inline style attributes
- **Location**: `apps/documents/models/CollaborationSharing/CoauthorSessions.py:70`
- **Problem**: `color_code` is interpolated into inline `style="..."` attributes without regex validation (Lesson L26).
- **Fix**: Add `RegexValidator(regex=r"^#[0-9A-Fa-f]{6}$")` to `color_code`.

### [ ] M5: Confidential document title disclosed prior to passcode challenge
- **Location**: `templates/documents/collaboration_sharing/public_share_preview.html:4`
- **Problem**: `<title>` renders document title unconditionally on passcode-protected links.
- **Fix**: Condition `<title>` on `password_required`.

### [ ] M6: Missing accessible labels and RTL styling
- **Location**:
  - `templates/documents/collaboration_sharing/collaboration_hub.html:363-365` (missing aria-label on icon button)
  - `templates/documents/collaboration_sharing/collaboration_hub.html:284` & `document_task/list.html:165` (missing aria-label on toggle button)
  - `templates/documents/collaboration_sharing/coauthor_session/detail.html:46` & `document_task/detail.html:159,167` (physical CSS left properties)
- **Fix**: Add `aria-label` attributes and replace physical CSS with logical CSS properties (`border-inline-start`, `border-s-4`, `ps-3`).

### [ ] M7: Missing composite database indexes on hot query and append-only tables
- **Location**: `apps/documents/models/CollaborationSharing/DocumentActivities.py`, `CoauthorSessions.py`, `DocumentShares.py`
- **Problem**: Missing composite indexes on `(tenant, created_at)` for `DocumentActivity`, `(tenant, status)` for `CoauthorSession`, and `(tenant, shared_with_user)` for `DocumentShare`.
- **Fix**: Add index definitions to model `Meta.indexes`.

### [ ] M8: Contract document related_name update
- **Location**: `.claude/tasks/contract-documents-13.8.md:80`
- **Problem**: Contract doc listed `related_name="received_document_shares"`, while code was disambiguated to `dms_received_document_shares` to avoid clash with `apps.projects`.
- **Fix**: Update contract doc to reflect `dms_received_document_shares`.
