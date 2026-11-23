# Module 13.8 Pre-Build Contract — Collaboration & Sharing (`apps/documents/`)

> Frozen in Phase 3.1 before any entity build. Every model field, `max_length`,
> `CHOICES` tuple, badge class (`static/css/theme.css`), index/constraint name (`<= 30` chars),
> form `Meta.fields` + excluded fields, URL route/name (literal before `<int:pk>`), exact view
> context key, filter param, `AuditLog.action` verb (`<= 10` chars), and `LIVE_LINKS["13.8"]`
> entry below is authoritative across backend, templates, smoke tests, reviews, and unit/security tests.

- **Parent App**: `apps.documents` (Extends existing app; claims incremental migration `0014_...`)
- **Package Directories**:
  - `apps/documents/models/CollaborationSharing/`
  - `apps/documents/forms/CollaborationSharing/`
  - `apps/documents/views/CollaborationSharing/`
  - `apps/documents/urls/CollaborationSharing/`
  - `templates/documents/collaboration_sharing/{document_share,coauthor_session,document_task,document_activity}/{list,detail,form}.html` + `collaboration_hub.html` + `public_share_preview.html`
- **AuditLog `action` Max Length (`<= 10` chars, L66)**:
  - Allowed `action` verbs passed to `write_audit_log(request.user, obj, verb, tenant=request.tenant)`:
    `"create"`, `"update"`, `"delete"`, `"share"`, `"revoke"`, `"access"`, `"join"`, `"leave"`, `"complete"` (all `<= 10` chars).
- **Theme CSS Classes (`static/css/theme.css`, L33)**:
  - Allowed badge classes ONLY: `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate`.
  - Detail views use `<dl class="detail-grid"><div class="detail-item"><dt>...</dt><dd>...</dd></div></dl>`.
- **Pagination**:
  - `PAGE_SIZE = 15` (`Paginator(qs, PAGE_SIZE)`).
  - Paginator guards `has_previous` / `has_next` (L9).
- **Tenant Scoping & FK Isolation (L29, L39, L11)**:
  - All foreign keys are tenant-scoped: `accounts.User`, `core.OrgUnit`, `documents.Document`, `documents.DocumentVersion`, `documents.DocumentFolder`, `documents.DocumentReviewComment`.
  - FKs populated in forms using `Model.objects.filter(tenant=self.tenant)` and validated in `clean()` via `reject_foreign(...)`.
  - List view FK query param parsing MUST check `.isdigit()` (L11) before filtering.

---

## 1. Models & Choices Contract (`apps/documents/models/CollaborationSharing/`)

All 4 models inherit `apps.documents.models._base.TenantNumbered` (`tenant` FK `core.Tenant`, `number` `CharField(32, editable=False)`, `created_at`, `updated_at`, collision-retrying `save()`).

### 1.1 `DocumentShare` (`DocumentShares.py`)
- **`NUMBER_PREFIX`**: `"DSHR"`
- **`Meta.ordering`**: `["-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Document Share"` / `"Document Shares"`
- **Choices & Badge Maps**:
  - `SHARE_TYPE_CHOICES` (`max_length=20`):
    - `("internal_user", "Specific Internal User")`
    - `("internal_dept", "Internal Department / OrgUnit")`
    - `("external_email", "Named External Guest")`
    - `("public_link", "Public Unguessable Link")`
  - `ACCESS_LEVEL_CHOICES` (`max_length=20`):
    - `("view_only", "View Only (Preview)")`
    - `("comment", "View & Comment / Annotate")`
    - `("edit", "Full Co-Authoring & Edit")`
  - `SHARE_TYPE_CSS`:
    - `"internal_user": "badge-info"`
    - `"internal_dept": "badge-slate"`
    - `"external_email": "badge-amber"`
    - `"public_link": "badge-green"`
  - `ACCESS_LEVEL_CSS`:
    - `"view_only": "badge-slate"`
    - `"comment": "badge-info"`
    - `"edit": "badge-green"`
  - `STATUS_CSS`:
    - `"active": "badge-green"`
    - `"expired": "badge-amber"`
    - `"revoked": "badge-red"`
    - `"exhausted": "badge-muted"`
- **Fields (exact names & types)**:
  - `document`: `ForeignKey("documents.Document", on_delete=models.CASCADE, related_name="shares", db_index=True)`
  - `folder`: `ForeignKey("documents.DocumentFolder", on_delete=models.CASCADE, null=True, blank=True, related_name="shares")`
  - `version`: `ForeignKey("documents.DocumentVersion", on_delete=models.SET_NULL, null=True, blank=True, related_name="shares")`
  - `share_token`: `CharField(max_length=64, unique=True, db_index=True)`
  - `share_type`: `CharField(max_length=20, choices=SHARE_TYPE_CHOICES, default="public_link", db_index=True)`
  - `access_level`: `CharField(max_length=20, choices=ACCESS_LEVEL_CHOICES, default="view_only", db_index=True)`
  - `allow_download`: `BooleanField(default=True)`
  - `allow_print`: `BooleanField(default=True)`
  - `include_annotations`: `BooleanField(default=False)`
  - `password_hash`: `CharField(max_length=128, blank=True)`
  - `expires_at`: `DateTimeField(null=True, blank=True, db_index=True)`
  - `max_uses`: `PositiveIntegerField(null=True, blank=True)`
  - `access_count`: `PositiveIntegerField(default=0)`
  - `last_accessed_at`: `DateTimeField(null=True, blank=True)`
  - `shared_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_document_shares")`
  - `shared_with_user`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="dms_received_document_shares")`
  - `shared_with_email`: `EmailField(blank=True)`
  - `shared_with_org_unit`: `ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True, related_name="document_shares")`
  - `share_message`: `TextField(blank=True)`
  - `is_active`: `BooleanField(default=True, db_index=True)`
  - `revoked_at`: `DateTimeField(null=True, blank=True)`
  - `revoked_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="revoked_document_shares")`
- **Indexes & Constraints (`<= 30` chars)**:
  - `models.Index(fields=["tenant", "share_token"], name="doc_dshr_tnt_tok_idx")`
  - `models.Index(fields=["tenant", "expires_at"], name="doc_dshr_tnt_exp_idx")`
  - `models.Index(fields=["tenant", "shared_by"], name="doc_dshr_tnt_usr_idx")`
- **Properties & Helper Methods**:
  - `is_expired` (@property): `timezone.now() > self.expires_at` if `self.expires_at` else `False`
  - `is_exhausted` (@property): `self.access_count >= self.max_uses` if `self.max_uses` else `False`
  - `is_valid` (@property): `self.is_active and not self.is_expired and not self.is_exhausted`
  - `has_password` (@property): `bool(self.password_hash)`
  - `set_password(raw_password)`
  - `check_password(raw_password)`
  - `revoke(user)`

---

### 1.2 `CoauthorSession` (`CoauthorSessions.py`)
- **`NUMBER_PREFIX`**: `"DCOA"`
- **`Meta.ordering`**: `["-last_heartbeat"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Coauthor Session"` / `"Coauthor Sessions"`
- **Choices & Badge Maps**:
  - `STATUS_CHOICES` (`max_length=20`):
    - `("active", "Active Editing")`
    - `("idle", "Idle / Inactive")`
    - `("disconnected", "Disconnected / Closed")`
  - `STATUS_CSS`:
    - `"active": "badge-green"`
    - `"idle": "badge-amber"`
    - `"disconnected": "badge-slate"`
- **Fields (exact names & types)**:
  - `document`: `ForeignKey("documents.Document", on_delete=models.CASCADE, related_name="coauthor_sessions", db_index=True)`
  - `version`: `ForeignKey("documents.DocumentVersion", on_delete=models.SET_NULL, null=True, blank=True, related_name="coauthor_sessions")`
  - `draft`: `ForeignKey("documents.DocumentDraft", on_delete=models.SET_NULL, null=True, blank=True, related_name="coauthor_sessions")`
  - `session_token`: `CharField(max_length=64, unique=True, db_index=True)`
  - `user`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="coauthor_sessions")`
  - `guest_name`: `CharField(max_length=100, blank=True)`
  - `color_code`: `CharField(max_length=7, default="#3B82F6")`
  - `cursor_position`: `TextField(blank=True, default="{}")`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default="active", db_index=True)`
  - `is_editing`: `BooleanField(default=False)`
  - `current_section`: `CharField(max_length=100, blank=True)`
  - `client_ip`: `GenericIPAddressField(null=True, blank=True)`
  - `user_agent`: `CharField(max_length=255, blank=True)`
  - `joined_at`: `DateTimeField(auto_now_add=True)`
  - `last_heartbeat`: `DateTimeField(auto_now=True, db_index=True)`
  - `disconnected_at`: `DateTimeField(null=True, blank=True)`
- **Indexes & Constraints (`<= 30` chars)**:
  - `models.Index(fields=["tenant", "session_token"], name="doc_dcoa_tnt_tok_idx")`
  - `models.Index(fields=["tenant", "last_heartbeat"], name="doc_dcoa_tnt_hbt_idx")`
- **Properties & Helper Methods**:
  - `display_name` (@property): `self.user.get_full_name() or self.user.username` if `self.user` else `(self.guest_name or "Guest Collaborator")`
  - `is_timed_out` (@property): `(timezone.now() - self.last_heartbeat).total_seconds() > 90`

---

### 1.3 `DocumentTask` (`DocumentTasks.py`)
- **`NUMBER_PREFIX`**: `"DTSK"`
- **`Meta.ordering`**: `["-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Document Task"` / `"Document Tasks"`
- **Choices & Badge Maps**:
  - `TASK_TYPE_CHOICES` (`max_length=30`):
    - `("review", "Document Review")`
    - `("approval_signoff", "Informal Team Sign-Off")`
    - `("revision_requested", "Author Revision Required")`
    - `("fact_check", "Fact-Check & Verification")`
    - `("redline_review", "Redline / Suggested Edit Review")`
    - `("general_todo", "General Action Item")`
  - `PRIORITY_CHOICES` (`max_length=20`):
    - `("low", "Low")`
    - `("medium", "Medium")`
    - `("high", "High")`
    - `("urgent", "Urgent / Immediate")`
  - `STATUS_CHOICES` (`max_length=20`):
    - `("pending", "Pending")`
    - `("in_progress", "In Progress")`
    - `("completed", "Completed")`
    - `("cancelled", "Cancelled")`
    - `("overdue", "Overdue")`
  - `TASK_TYPE_CSS`:
    - `"review": "badge-info"`
    - `"approval_signoff": "badge-green"`
    - `"revision_requested": "badge-amber"`
    - `"fact_check": "badge-slate"`
    - `"redline_review": "badge-red"`
    - `"general_todo": "badge-muted"`
  - `PRIORITY_CSS`:
    - `"low": "badge-slate"`
    - `"medium": "badge-info"`
    - `"high": "badge-amber"`
    - `"urgent": "badge-red"`
  - `STATUS_CSS`:
    - `"pending": "badge-amber"`
    - `"in_progress": "badge-info"`
    - `"completed": "badge-green"`
    - `"cancelled": "badge-slate"`
    - `"overdue": "badge-red"`
- **Fields (exact names & types)**:
  - `document`: `ForeignKey("documents.Document", on_delete=models.CASCADE, related_name="tasks", db_index=True)`
  - `version`: `ForeignKey("documents.DocumentVersion", on_delete=models.SET_NULL, null=True, blank=True, related_name="tasks")`
  - `review_comment`: `ForeignKey("documents.DocumentReviewComment", on_delete=models.SET_NULL, null=True, blank=True, related_name="action_items")`
  - `title`: `CharField(max_length=255)`
  - `description`: `TextField(blank=True)`
  - `task_type`: `CharField(max_length=30, choices=TASK_TYPE_CHOICES, default="review", db_index=True)`
  - `priority`: `CharField(max_length=20, choices=PRIORITY_CHOICES, default="medium", db_index=True)`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default="pending", db_index=True)`
  - `assigned_to`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_document_tasks")`
  - `assigned_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_document_tasks")`
  - `assigned_org_unit`: `ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True, related_name="document_tasks")`
  - `due_date`: `DateField(null=True, blank=True, db_index=True)`
  - `reminder_date`: `DateField(null=True, blank=True)`
  - `reminder_sent`: `BooleanField(default=False)`
  - `completed_at`: `DateTimeField(null=True, blank=True)`
  - `completed_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="completed_document_tasks")`
  - `completion_notes`: `TextField(blank=True)`
- **Indexes & Constraints (`<= 30` chars)**:
  - `models.Index(fields=["tenant", "due_date"], name="doc_dtsk_tnt_due_idx")`
  - `models.Index(fields=["tenant", "assigned_to"], name="doc_dtsk_tnt_usr_idx")`
- **Properties & Helper Methods**:
  - `is_overdue` (@property): `bool(self.due_date and self.due_date < timezone.now().date() and self.status not in ("completed", "cancelled"))`
  - `complete(user, notes="")`

---

### 1.4 `DocumentActivity` (`DocumentActivities.py`)
- **`NUMBER_PREFIX`**: `"DACT"`
- **`Meta.ordering`**: `["-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Document Activity"` / `"Document Activities"`
- **Choices & Badge Maps**:
  - `ACTION_TYPE_CHOICES` (`max_length=30`):
    - `("document_shared", "Document Shared")`
    - `("share_revoked", "Share Link Revoked")`
    - `("link_accessed", "Share Link Accessed")`
    - `("file_downloaded", "File Downloaded")`
    - `("coauthor_joined", "Collaborator Joined Session")`
    - `("coauthor_left", "Collaborator Left Session")`
    - `("comment_added", "Comment / Annotation Added")`
    - `("task_assigned", "Task / Action Item Assigned")`
    - `("task_completed", "Task Completed")`
    - `("user_mentioned", "User Mentioned in Discussion")`
    - `("version_created", "New Version Uploaded")`
  - `NOTIFICATION_CHANNEL_CHOICES` (`max_length=20`):
    - `("in_app", "In-App Notification")`
    - `("email_digest", "Included in Email Digest")`
    - `("none", "Silent Activity Log")`
  - `ACTION_TYPE_CSS`:
    - `"document_shared": "badge-info"`
    - `"share_revoked": "badge-red"`
    - `"link_accessed": "badge-slate"`
    - `"file_downloaded": "badge-muted"`
    - `"coauthor_joined": "badge-green"`
    - `"coauthor_left": "badge-slate"`
    - `"comment_added": "badge-amber"`
    - `"task_assigned": "badge-info"`
    - `"task_completed": "badge-green"`
    - `"user_mentioned": "badge-amber"`
    - `"version_created": "badge-info"`
- **Fields (exact names & types)**:
  - `document`: `ForeignKey("documents.Document", on_delete=models.CASCADE, related_name="collaboration_activities", db_index=True)`
  - `actor`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="document_activities")`
  - `guest_name`: `CharField(max_length=100, blank=True)`
  - `target_user`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="targeted_document_activities")`
  - `action_type`: `CharField(max_length=30, choices=ACTION_TYPE_CHOICES, db_index=True)`
  - `summary`: `CharField(max_length=255)`
  - `details_json`: `TextField(blank=True, default="{}")`
  - `is_read`: `BooleanField(default=False, db_index=True)`
  - `read_at`: `DateTimeField(null=True, blank=True)`
  - `notification_channel`: `CharField(max_length=20, choices=NOTIFICATION_CHANNEL_CHOICES, default="in_app")`
- **Indexes & Constraints (`<= 30` chars)**:
  - `models.Index(fields=["tenant", "target_user", "is_read"], name="doc_dact_tnt_tgt_idx")`
  - `models.Index(fields=["tenant", "action_type"], name="doc_dact_tnt_act_idx")`
- **Properties & Helper Methods**:
  - `mark_as_read()`

---

## 2. Forms Contract (`apps/documents/forms/CollaborationSharing/`)

### 2.1 `DocumentShareForm` (`DocumentShares.py`)
- **`Meta.model`**: `DocumentShare`
- **`Meta.fields`**: `["document", "folder", "version", "share_type", "access_level", "shared_with_user", "shared_with_email", "shared_with_org_unit", "expires_at", "max_uses", "allow_download", "allow_print", "include_annotations", "share_message"]`
- **Custom Form Fields**: `raw_password = forms.CharField(required=False, widget=forms.PasswordInput)`
- **Explicit Exclusions**: `tenant`, `number`, `share_token`, `password_hash`, `access_count`, `last_accessed_at`, `shared_by`, `is_active`, `revoked_at`, `revoked_by`, `created_at`, `updated_at`.
- **Validation**:
  - Populates tenant-scoped querysets in `__init__` for `document`, `folder`, `version`, `shared_with_user`, `shared_with_org_unit`.
  - In `clean()`: calls `reject_foreign(...)` ensuring all FKs belong to `self.tenant`.
  - In `save()`: auto-generates `share_token` (secrets.token_urlsafe) if empty; sets `password_hash` if `raw_password` provided; assigns `shared_by = self.user` on creation.

### 2.2 `CoauthorSessionForm` (`CoauthorSessions.py`)
- **`Meta.model`**: `CoauthorSession`
- **`Meta.fields`**: `["document", "version", "draft", "user", "guest_name", "color_code", "status", "is_editing", "current_section"]`
- **Explicit Exclusions**: `tenant`, `number`, `session_token`, `cursor_position`, `client_ip`, `user_agent`, `joined_at`, `last_heartbeat`, `disconnected_at`, `created_at`, `updated_at`.
- **Validation**:
  - Populates tenant-scoped querysets in `__init__` for `document`, `version`, `draft`, `user`.
  - Calls `reject_foreign(...)` on all FKs.
  - Generates `session_token` if empty.

### 2.3 `DocumentTaskForm` (`DocumentTasks.py`)
- **`Meta.model`**: `DocumentTask`
- **`Meta.fields`**: `["document", "version", "review_comment", "title", "description", "task_type", "priority", "status", "assigned_to", "assigned_org_unit", "due_date", "reminder_date", "completion_notes"]`
- **Explicit Exclusions**: `tenant`, `number`, `assigned_by`, `reminder_sent`, `completed_at`, `completed_by`, `created_at`, `updated_at`.
- **Validation**:
  - Populates tenant-scoped querysets in `__init__` for `document`, `version`, `review_comment`, `assigned_to`, `assigned_org_unit`.
  - In `clean()`: validates `reminder_date <= due_date` if both provided.
  - In `save()`: assigns `assigned_by = self.user` on create; if `status == "completed"` and not `completed_at`, sets `completed_at = timezone.now()` and `completed_by = self.user`.

### 2.4 `DocumentActivityForm` (`DocumentActivities.py`)
- **`Meta.model`**: `DocumentActivity`
- **`Meta.fields`**: `["document", "actor", "guest_name", "target_user", "action_type", "summary", "notification_channel"]`
- **Explicit Exclusions**: `tenant`, `number`, `details_json`, `is_read`, `read_at`, `created_at`, `updated_at`.
- **Validation**:
  - Populates tenant-scoped querysets in `__init__` for `document`, `actor`, `target_user`.
  - Calls `reject_foreign(...)` on all FKs.

---

## 3. URLs Contract (`apps/documents/urls/CollaborationSharing/`)

Literal routes placed strictly before `<int:pk>`:

```python
urlpatterns = [
    # Collaboration Hub & Consoles
    path("collaboration/", views.collaboration_hub, name="collaboration_hub"),
    
    # Public & Guest Link Viewers (Token based)
    path("shares/public/<str:share_token>/", views.public_share_preview, name="public_share_preview"),
    path("shares/public/<str:share_token>/download/", views.public_share_download, name="public_share_download"),
    
    # DocumentShare CRUD
    path("shares/", views.document_share_list, name="document_share_list"),
    path("shares/create/", views.document_share_create, name="document_share_create"),
    path("shares/<int:pk>/", views.document_share_detail, name="document_share_detail"),
    path("shares/<int:pk>/edit/", views.document_share_edit, name="document_share_edit"),
    path("shares/<int:pk>/delete/", views.document_share_delete, name="document_share_delete"),
    path("shares/<int:pk>/revoke/", views.document_share_revoke, name="document_share_revoke"),
    
    # CoauthorSession CRUD & Presence Handlers
    path("sessions/", views.coauthor_session_list, name="coauthor_session_list"),
    path("sessions/create/", views.coauthor_session_create, name="coauthor_session_create"),
    path("sessions/<int:pk>/", views.coauthor_session_detail, name="coauthor_session_detail"),
    path("sessions/<int:pk>/edit/", views.coauthor_session_edit, name="coauthor_session_edit"),
    path("sessions/<int:pk>/delete/", views.coauthor_session_delete, name="coauthor_session_delete"),
    path("sessions/<str:session_token>/heartbeat/", views.coauthor_session_heartbeat, name="coauthor_session_heartbeat"),
    
    # DocumentTask CRUD & Quick Actions
    path("tasks/", views.document_task_list, name="document_task_list"),
    path("tasks/create/", views.document_task_create, name="document_task_create"),
    path("tasks/<int:pk>/", views.document_task_detail, name="document_task_detail"),
    path("tasks/<int:pk>/edit/", views.document_task_edit, name="document_task_edit"),
    path("tasks/<int:pk>/delete/", views.document_task_delete, name="document_task_delete"),
    path("tasks/<int:pk>/toggle-complete/", views.document_task_toggle_complete, name="document_task_toggle_complete"),
    
    # DocumentActivity CRUD & Read Handlers
    path("activities/", views.document_activity_list, name="document_activity_list"),
    path("activities/<int:pk>/", views.document_activity_detail, name="document_activity_detail"),
    path("activities/<int:pk>/mark-read/", views.document_activity_mark_read, name="document_activity_mark_read"),
    path("activities/mark-all-read/", views.document_activity_mark_all_read, name="document_activity_mark_all_read"),
]
```

---

## 4. View Context Keys Contract

### 4.1 `collaboration_hub`
- Template: `templates/documents/collaboration_sharing/collaboration_hub.html`
- Context keys:
  - `active_tab`: `"shared_with_me"` | `"shared_by_me"` | `"my_tasks"` | `"activity"`
  - `shared_with_me`: queryset of active `DocumentShare` targeting user, user's department, or public
  - `shared_by_me`: queryset of active `DocumentShare` created by `request.user`
  - `my_tasks`: queryset of `DocumentTask` assigned to `request.user` or user's department
  - `activity_feed`: queryset of `DocumentActivity`
  - `active_sessions`: queryset of active `CoauthorSession`
  - `stat_my_tasks_count`: int
  - `stat_overdue_tasks_count`: int
  - `stat_shares_by_me_count`: int
  - `stat_shares_with_me_count`: int
  - `stat_unread_activities_count`: int

### 4.2 `document_share_list`
- Template: `templates/documents/collaboration_sharing/document_share/list.html`
- Context keys:
  - `page_obj`: paginated `DocumentShare` instances
  - `shares`: `page_obj.object_list`
  - `share_type_choices`: `DocumentShare.SHARE_TYPE_CHOICES`
  - `access_level_choices`: `DocumentShare.ACCESS_LEVEL_CHOICES`
  - `status_choices`: `[("active", "Active"), ("expired", "Expired"), ("revoked", "Revoked")]`
  - `total_count`, `active_count`, `expired_count`, `revoked_count`: int
  - `q`: search string
  - `current_share_type`, `current_access_level`, `current_status`: string filter params

### 4.3 `document_share_detail`
- Template: `templates/documents/collaboration_sharing/document_share/detail.html`
- Context keys:
  - `share`: `DocumentShare` instance
  - `share_url`: absolute public access URL
  - `activities`: queryset of `DocumentActivity` matching share events

### 4.4 `document_share_form` (create/edit)
- Template: `templates/documents/collaboration_sharing/document_share/form.html`
- Context keys:
  - `form`: `DocumentShareForm` instance
  - `share`: instance if editing, None if creating
  - `is_edit`: bool

### 4.5 `public_share_preview`
- Template: `templates/documents/collaboration_sharing/public_share_preview.html`
- Context keys:
  - `share`: `DocumentShare` instance
  - `document`: `Document` instance
  - `version`: latest `DocumentVersion` instance
  - `password_required`: bool
  - `password_error`: string or None
  - `can_download`: bool
  - `can_print`: bool
  - `can_comment`: bool
  - `can_edit`: bool
  - `annotations`: review comments queryset if `share.include_annotations`

### 4.6 `coauthor_session_list`
- Template: `templates/documents/collaboration_sharing/coauthor_session/list.html`
- Context keys:
  - `page_obj`: paginated `CoauthorSession` instances
  - `sessions`: `page_obj.object_list`
  - `status_choices`: `CoauthorSession.STATUS_CHOICES`
  - `total_count`, `active_count`, `idle_count`, `disconnected_count`: int
  - `q`, `current_status`: filter params

### 4.7 `coauthor_session_detail`
- Template: `templates/documents/collaboration_sharing/coauthor_session/detail.html`
- Context keys:
  - `session`: `CoauthorSession` instance

### 4.8 `coauthor_session_form` (create/edit)
- Template: `templates/documents/collaboration_sharing/coauthor_session/form.html`
- Context keys:
  - `form`: `CoauthorSessionForm` instance
  - `session`: instance if editing, None if creating
  - `is_edit`: bool

### 4.9 `document_task_list`
- Template: `templates/documents/collaboration_sharing/document_task/list.html`
- Context keys:
  - `page_obj`: paginated `DocumentTask` instances
  - `tasks`: `page_obj.object_list`
  - `task_type_choices`: `DocumentTask.TASK_TYPE_CHOICES`
  - `priority_choices`: `DocumentTask.PRIORITY_CHOICES`
  - `status_choices`: `DocumentTask.STATUS_CHOICES`
  - `total_count`, `pending_count`, `in_progress_count`, `completed_count`, `overdue_count`: int
  - `q`, `current_task_type`, `current_priority`, `current_status`, `assigned_to_filter`: filter params
  - `users`: tenant `User` queryset

### 4.10 `document_task_detail`
- Template: `templates/documents/collaboration_sharing/document_task/detail.html`
- Context keys:
  - `task`: `DocumentTask` instance

### 4.11 `document_task_form` (create/edit)
- Template: `templates/documents/collaboration_sharing/document_task/form.html`
- Context keys:
  - `form`: `DocumentTaskForm` instance
  - `task`: instance if editing, None if creating
  - `is_edit`: bool

### 4.12 `document_activity_list`
- Template: `templates/documents/collaboration_sharing/document_activity/list.html`
- Context keys:
  - `page_obj`: paginated `DocumentActivity` instances
  - `activities`: `page_obj.object_list`
  - `action_type_choices`: `DocumentActivity.ACTION_TYPE_CHOICES`
  - `total_count`, `unread_count`: int
  - `q`, `current_action_type`, `current_filter`: filter params

### 4.13 `document_activity_detail`
- Template: `templates/documents/collaboration_sharing/document_activity/detail.html`
- Context keys:
  - `activity`: `DocumentActivity` instance

---

## 5. Navigation & Sidebar (`apps/core/navigation.py`)

Mapping for `LIVE_LINKS["13.8"]`:
```python
"13.8": {
    "Internal & External Sharing": "documents:collaboration_hub",
    "Real-Time Co-Authoring": "documents:coauthor_session_list",
    "Commenting & Annotation": "documents:review_comment_list",
    "Task Assignment & Document Review": "documents:document_task_list",
    "Activity Feed & Notifications": "documents:document_activity_list",
},
```
