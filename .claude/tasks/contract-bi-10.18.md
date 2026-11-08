# Contract — Sub-module 10.18: Collaboration & Data Storytelling (Module 10: Business Intelligence, `bi`)

- **Sub-module:** 10.18 Collaboration & Data Storytelling • **Module:** 10 Business Intelligence • **App:** `apps/bi`
- **Date:** 2026-11-08 • **Status:** FROZEN PRE-BUILD CONTRACT • **Phase:** 3.1 Spec
- **App Status:** Existing app `apps/bi/` (extended across 10.1 through 10.17). Incremental migration: `0039_...`
- **Package Layout:** `CollaborationStorytelling/` across `models/`, `forms/`, `views/`, `urls/`, and templates `templates/bi/collaboration_storytelling/`.

---

## 1. Models & CHOICES Contract

All 4 models inherit from `apps.bi.models._base.TenantNumbered` (`tenant`, `number`, `created_at`, `updated_at`).

### 1.1 `BiSharedWorkspace` (`apps/bi/models/CollaborationStorytelling/BiSharedWorkspaces.py`)
- **Table:** `bi_shared_workspace`
- **Number Prefix:** `WSPC` (`WSPC-00001`)
- **CHOICES:**
  - `ACCESS_LEVEL_CHOICES = [('viewer', 'Viewer (Read-Only)'), ('contributor', 'Contributor (Add Content)'), ('member', 'Member (Edit & Share)'), ('admin', 'Workspace Admin')]`
  - `STATUS_CHOICES = [('active', 'Active'), ('archived', 'Archived')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='bi_shared_workspaces')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `name`: `CharField(max_length=200)`
  - `slug`: `SlugField(max_length=220, blank=True)`
  - `description`: `TextField(blank=True)`
  - `department`: `ForeignKey('core.OrgUnit', null=True, blank=True, on_delete=models.SET_NULL, related_name='bi_workspaces')`
  - `owner`: `ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='bi_owned_workspaces')`
  - `default_access_level`: `CharField(max_length=20, choices=ACCESS_LEVEL_CHOICES, default='contributor')`
  - `status`: `CharField(max_length=16, choices=STATUS_CHOICES, default='active')`
  - `is_public`: `BooleanField(default=False)`
  - `is_favorite`: `BooleanField(default=False)`
  - `color`: `CharField(max_length=20, default='#3b82f6')`
  - `icon`: `CharField(max_length=50, default='folder')`
  - `pinned_dashboard_ids`: `JSONField(default=list, blank=True)`
  - `pinned_report_ids`: `JSONField(default=list, blank=True)`
  - `pinned_story_ids`: `JSONField(default=list, blank=True)`
  - `members_json`: `JSONField(default=list, blank=True)`
  - `created_by`: `ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='bi_created_workspaces')`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_wspc_ten_num_uniq')`
  - `UniqueConstraint(fields=['tenant', 'slug'], name='bi_wspc_ten_slug_uniq')`
  - `Index(fields=['tenant', 'status'], name='idx_wspc_ten_stat')`
  - `Index(fields=['tenant', 'department'], name='idx_wspc_ten_dept')`
  - `Index(fields=['tenant', 'owner'], name='idx_wspc_ten_owner')`
  - `Index(fields=['tenant', 'created_at'], name='idx_wspc_ten_created')`

---

### 1.2 `BiDataStory` (`apps/bi/models/CollaborationStorytelling/BiDataStories.py`)
- **Table:** `bi_data_story`
- **Number Prefix:** `DSTY` (`DSTY-00001`)
- **CHOICES:**
  - `STORY_TYPE_CHOICES = [('narrative_deck', 'Executive Presentation Deck'), ('annotated_walkthrough', 'Annotated Walkthrough'), ('dashboard_snapshot', 'Guided Dashboard Tour'), ('kpi_review', 'KPI & Business Review')]`
  - `STATUS_CHOICES = [('draft', 'Draft'), ('published', 'Published'), ('archived', 'Archived')]`
  - `PRESENTATION_THEME_CHOICES = [('light_executive', 'Executive Clean Light'), ('dark_boardroom', 'Boardroom Navy Dark'), ('vibrant_accent', 'Modern Vibrant')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='bi_data_stories')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `title`: `CharField(max_length=200)`
  - `slug`: `SlugField(max_length=220, blank=True)`
  - `summary`: `TextField(blank=True)`
  - `workspace`: `ForeignKey('bi.BiSharedWorkspace', null=True, blank=True, on_delete=models.SET_NULL, related_name='stories')`
  - `story_type`: `CharField(max_length=24, choices=STORY_TYPE_CHOICES, default='narrative_deck')`
  - `status`: `CharField(max_length=16, choices=STATUS_CHOICES, default='draft')`
  - `theme`: `CharField(max_length=24, choices=PRESENTATION_THEME_CHOICES, default='light_executive')`
  - `author`: `ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='bi_authored_stories')`
  - `allow_live_drilldown`: `BooleanField(default=True)`
  - `slides_data`: `JSONField(default=list, blank=True)`
  - `slides_count`: `PositiveIntegerField(default=0)`
  - `view_count`: `PositiveIntegerField(default=0)`
  - `office_embed_token`: `CharField(max_length=64, blank=True)`
  - `excel_export_settings`: `JSONField(default=dict, blank=True)`
  - `last_presented_at`: `DateTimeField(null=True, blank=True)`
  - `created_by`: `ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='bi_created_stories')`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_dsty_ten_num_uniq')`
  - `UniqueConstraint(fields=['tenant', 'slug'], name='bi_dsty_ten_slug_uniq')`
  - `Index(fields=['tenant', 'status'], name='idx_dsty_ten_stat')`
  - `Index(fields=['tenant', 'story_type'], name='idx_dsty_ten_type')`
  - `Index(fields=['tenant', 'workspace'], name='idx_dsty_ten_wspc')`
  - `Index(fields=['tenant', 'author'], name='idx_dsty_ten_author')`
  - `Index(fields=['tenant', 'created_at'], name='idx_dsty_ten_created')`

---

### 1.3 `BiVisualComment` (`apps/bi/models/CollaborationStorytelling/BiVisualComments.py`)
- **Table:** `bi_visual_comment`
- **Number Prefix:** `VCOM` (`VCOM-00001`)
- **CHOICES:**
  - `TARGET_TYPE_CHOICES = [('dashboard', 'Dashboard Canvas'), ('widget', 'Visual Chart / Card'), ('report', 'Operational Report'), ('story', 'Data Story Slide')]`
  - `STATUS_CHOICES = [('open', 'Open'), ('in_review', 'In Review'), ('acknowledged', 'Acknowledged'), ('resolved', 'Resolved')]`
  - `PRIORITY_CHOICES = [('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('urgent', 'Urgent / Action Required')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='bi_visual_comments')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `target_type`: `CharField(max_length=20, choices=TARGET_TYPE_CHOICES, default='dashboard')`
  - `dashboard`: `ForeignKey('bi.BiDashboard', null=True, blank=True, on_delete=models.SET_NULL, related_name='comments')`
  - `widget`: `ForeignKey('bi.BiDashboardWidget', null=True, blank=True, on_delete=models.SET_NULL, related_name='comments')`
  - `report`: `ForeignKey('bi.ReportDefinition', null=True, blank=True, on_delete=models.SET_NULL, related_name='comments')`
  - `story`: `ForeignKey('bi.BiDataStory', null=True, blank=True, on_delete=models.SET_NULL, related_name='comments')`
  - `slide_id`: `CharField(max_length=50, blank=True)`
  - `parent_comment`: `ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='replies')`
  - `content`: `TextField()`
  - `status`: `CharField(max_length=16, choices=STATUS_CHOICES, default='open')`
  - `priority`: `CharField(max_length=16, choices=PRIORITY_CHOICES, default='medium')`
  - `filter_snapshot`: `JSONField(default=dict, blank=True)`
  - `coordinate_x`: `FloatField(null=True, blank=True)`
  - `coordinate_y`: `FloatField(null=True, blank=True)`
  - `mentions_json`: `JSONField(default=list, blank=True)`
  - `author`: `ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='bi_authored_comments')`
  - `resolved_by`: `ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='bi_resolved_comments')`
  - `resolved_at`: `DateTimeField(null=True, blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_vcom_ten_num_uniq')`
  - `Index(fields=['tenant', 'status'], name='idx_vcom_ten_stat')`
  - `Index(fields=['tenant', 'target_type'], name='idx_vcom_ten_type')`
  - `Index(fields=['tenant', 'dashboard'], name='idx_vcom_ten_dash')`
  - `Index(fields=['tenant', 'story'], name='idx_vcom_ten_story')`
  - `Index(fields=['tenant', 'author'], name='idx_vcom_ten_author')`
  - `Index(fields=['tenant', 'created_at'], name='idx_vcom_ten_created')`

---

### 1.4 `BiDecisionLog` (`apps/bi/models/CollaborationStorytelling/BiDecisionLogs.py`)
- **Table:** `bi_decision_log`
- **Number Prefix:** `DLOG` (`DLOG-00001`)
- **CHOICES:**
  - `CATEGORY_CHOICES = [('strategic', 'Strategic Initiative'), ('operational', 'Operational Adjustment'), ('pricing', 'Pricing & Commercial'), ('budget', 'Budget / Cost Control'), ('inventory', 'Supply / Inventory Policy')]`
  - `STATUS_CHOICES = [('proposed', 'Proposed / Under Review'), ('approved', 'Approved & Enacted'), ('superseded', 'Superseded'), ('revoked', 'Revoked / Rolled Back')]`
  - `MARKER_STYLE_CHOICES = [('pin_flag', 'Pin Flag Marker'), ('vertical_line_event', 'Vertical Milestone Line'), ('highlight_band', 'Highlight Region Band')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='bi_decision_logs')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `title`: `CharField(max_length=200)`
  - `slug`: `SlugField(max_length=220, blank=True)`
  - `category`: `CharField(max_length=24, choices=CATEGORY_CHOICES, default='operational')`
  - `status`: `CharField(max_length=16, choices=STATUS_CHOICES, default='approved')`
  - `decision_date`: `DateField()`
  - `problem_statement`: `TextField(blank=True)`
  - `rationale`: `TextField()`
  - `alternatives_considered`: `TextField(blank=True)`
  - `expected_impact`: `TextField(blank=True)`
  - `actual_outcome`: `TextField(blank=True)`
  - `workspace`: `ForeignKey('bi.BiSharedWorkspace', null=True, blank=True, on_delete=models.SET_NULL, related_name='decision_logs')`
  - `dashboard`: `ForeignKey('bi.BiDashboard', null=True, blank=True, on_delete=models.SET_NULL, related_name='decision_logs')`
  - `widget`: `ForeignKey('bi.BiDashboardWidget', null=True, blank=True, on_delete=models.SET_NULL, related_name='decision_logs')`
  - `kpi`: `ForeignKey('bi.KpiDefinition', null=True, blank=True, on_delete=models.SET_NULL, related_name='decision_logs')`
  - `decision_maker`: `ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='bi_made_decisions')`
  - `show_on_charts`: `BooleanField(default=True)`
  - `marker_style`: `CharField(max_length=24, choices=MARKER_STYLE_CHOICES, default='pin_flag')`
  - `marker_color`: `CharField(max_length=20, default='#10b981')`
  - `supporting_documents`: `JSONField(default=list, blank=True)`
  - `review_date`: `DateField(null=True, blank=True)`
  - `created_by`: `ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='bi_created_decisions')`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_dlog_ten_num_uniq')`
  - `UniqueConstraint(fields=['tenant', 'slug'], name='bi_dlog_ten_slug_uniq')`
  - `Index(fields=['tenant', 'status'], name='idx_dlog_ten_stat')`
  - `Index(fields=['tenant', 'category'], name='idx_dlog_ten_cat')`
  - `Index(fields=['tenant', 'decision_date'], name='idx_dlog_ten_date')`
  - `Index(fields=['tenant', 'dashboard'], name='idx_dlog_ten_dash')`
  - `Index(fields=['tenant', 'kpi'], name='idx_dlog_ten_kpi')`
  - `Index(fields=['tenant', 'created_at'], name='idx_dlog_ten_created')`

---

## 2. Forms Contract

1. `BiSharedWorkspaceForm` (`apps/bi/forms/CollaborationStorytelling/BiSharedWorkspaces.py`)
   - `Meta.model = BiSharedWorkspace`
   - `Meta.fields = ['name', 'slug', 'description', 'department', 'owner', 'default_access_level', 'status', 'is_public', 'is_favorite', 'color', 'icon', 'pinned_dashboard_ids', 'pinned_report_ids', 'pinned_story_ids', 'members_json']`
   - Excluded: `tenant`, `number`, `created_by`, `created_at`, `updated_at`

2. `BiDataStoryForm` (`apps/bi/forms/CollaborationStorytelling/BiDataStories.py`)
   - `Meta.model = BiDataStory`
   - `Meta.fields = ['title', 'slug', 'summary', 'workspace', 'story_type', 'status', 'theme', 'author', 'allow_live_drilldown', 'slides_data', 'excel_export_settings']`
   - Excluded: `tenant`, `number`, `slides_count`, `view_count`, `office_embed_token`, `last_presented_at`, `created_by`, `created_at`, `updated_at`

3. `BiVisualCommentForm` (`apps/bi/forms/CollaborationStorytelling/BiVisualComments.py`)
   - `Meta.model = BiVisualComment`
   - `Meta.fields = ['target_type', 'dashboard', 'widget', 'report', 'story', 'slide_id', 'parent_comment', 'content', 'status', 'priority', 'filter_snapshot', 'coordinate_x', 'coordinate_y', 'mentions_json', 'resolved_by']`
   - Excluded: `tenant`, `number`, `author`, `resolved_at`, `created_at`, `updated_at`

4. `BiDecisionLogForm` (`apps/bi/forms/CollaborationStorytelling/BiDecisionLogs.py`)
   - `Meta.model = BiDecisionLog`
   - `Meta.fields = ['title', 'slug', 'category', 'status', 'decision_date', 'problem_statement', 'rationale', 'alternatives_considered', 'expected_impact', 'actual_outcome', 'workspace', 'dashboard', 'widget', 'kpi', 'decision_maker', 'show_on_charts', 'marker_style', 'marker_color', 'supporting_documents', 'review_date']`
   - Excluded: `tenant`, `number`, `created_by`, `created_at`, `updated_at`

---

## 3. URLs Contract

- `app_name = 'bi'`

| URL Pattern | Name | View Function |
|---|---|---|
| `workspaces/` | `bi_shared_workspace_list` | `bi_shared_workspace_list` |
| `workspaces/create/` | `bi_shared_workspace_create` | `bi_shared_workspace_create` |
| `workspaces/<int:pk>/` | `bi_shared_workspace_detail` | `bi_shared_workspace_detail` |
| `workspaces/<int:pk>/edit/` | `bi_shared_workspace_edit` | `bi_shared_workspace_edit` |
| `workspaces/<int:pk>/delete/` | `bi_shared_workspace_delete` | `bi_shared_workspace_delete` |
| `stories/` | `bi_data_story_list` | `bi_data_story_list` |
| `stories/create/` | `bi_data_story_create` | `bi_data_story_create` |
| `stories/<int:pk>/` | `bi_data_story_detail` | `bi_data_story_detail` |
| `stories/<int:pk>/edit/` | `bi_data_story_edit` | `bi_data_story_edit` |
| `stories/<int:pk>/delete/` | `bi_data_story_delete` | `bi_data_story_delete` |
| `stories/<int:pk>/presentation/` | `bi_data_story_presentation` | `bi_data_story_presentation` |
| `stories/<int:pk>/export-office/` | `bi_data_story_export_office` | `bi_data_story_export_office` |
| `comments/` | `bi_visual_comment_list` | `bi_visual_comment_list` |
| `comments/create/` | `bi_visual_comment_create` | `bi_visual_comment_create` |
| `comments/<int:pk>/` | `bi_visual_comment_detail` | `bi_visual_comment_detail` |
| `comments/<int:pk>/edit/` | `bi_visual_comment_edit` | `bi_visual_comment_edit` |
| `comments/<int:pk>/delete/` | `bi_visual_comment_delete` | `bi_visual_comment_delete` |
| `comments/<int:pk>/resolve/` | `bi_visual_comment_resolve` | `bi_visual_comment_resolve` |
| `decisions/` | `bi_decision_log_list` | `bi_decision_log_list` |
| `decisions/create/` | `bi_decision_log_create` | `bi_decision_log_create` |
| `decisions/<int:pk>/` | `bi_decision_log_detail` | `bi_decision_log_detail` |
| `decisions/<int:pk>/edit/` | `bi_decision_log_edit` | `bi_decision_log_edit` |
| `decisions/<int:pk>/delete/` | `bi_decision_log_delete` | `bi_decision_log_delete` |

---

## 4. View Context Keys Contract

### 4.1 List Views
- `bi_shared_workspace_list`:
  - `workspaces`: page_obj
  - `bi_shared_workspaces`: page_obj
  - `total_count`: integer
  - `active_count`: integer
  - `public_count`: integer
  - `status_choices`: `BiSharedWorkspace.STATUS_CHOICES`
  - `access_level_choices`: `BiSharedWorkspace.ACCESS_LEVEL_CHOICES`
  - `departments`: `core.OrgUnit.objects.filter(tenant=request.tenant)`

- `bi_data_story_list`:
  - `stories`: page_obj
  - `bi_data_stories`: page_obj
  - `total_count`: integer
  - `published_count`: integer
  - `draft_count`: integer
  - `status_choices`: `BiDataStory.STATUS_CHOICES`
  - `story_type_choices`: `BiDataStory.STORY_TYPE_CHOICES`
  - `workspaces`: `BiSharedWorkspace.objects.filter(tenant=request.tenant)`

- `bi_visual_comment_list`:
  - `comments`: page_obj
  - `bi_visual_comments`: page_obj
  - `total_count`: integer
  - `open_count`: integer
  - `resolved_count`: integer
  - `status_choices`: `BiVisualComment.STATUS_CHOICES`
  - `target_type_choices`: `BiVisualComment.TARGET_TYPE_CHOICES`
  - `priority_choices`: `BiVisualComment.PRIORITY_CHOICES`
  - `dashboards`: `BiDashboard.objects.filter(tenant=request.tenant)`
  - `stories`: `BiDataStory.objects.filter(tenant=request.tenant)`

- `bi_decision_log_list`:
  - `decisions`: page_obj
  - `bi_decision_logs`: page_obj
  - `total_count`: integer
  - `approved_count`: integer
  - `strategic_count`: integer
  - `status_choices`: `BiDecisionLog.STATUS_CHOICES`
  - `category_choices`: `BiDecisionLog.CATEGORY_CHOICES`
  - `dashboards`: `BiDashboard.objects.filter(tenant=request.tenant)`
  - `workspaces`: `BiSharedWorkspace.objects.filter(tenant=request.tenant)`

### 4.2 Detail Views
- `bi_shared_workspace_detail`:
  - `workspace`: object
  - `bi_shared_workspace`: object
  - `obj`: object
  - `stories`: queryset of `BiDataStory`
  - `decision_logs`: queryset of `BiDecisionLog`

- `bi_data_story_detail`:
  - `story`: object
  - `bi_data_story`: object
  - `obj`: object
  - `comments`: queryset of `BiVisualComment`

- `bi_data_story_presentation`:
  - `story`: object
  - `bi_data_story`: object
  - `obj`: object
  - `slides`: list of dicts from `story.slides_data`

- `bi_visual_comment_detail`:
  - `comment`: object
  - `bi_visual_comment`: object
  - `obj`: object
  - `replies`: queryset of `BiVisualComment`

- `bi_decision_log_detail`:
  - `decision`: object
  - `bi_decision_log`: object
  - `obj`: object

### 4.3 Form Views (Create / Edit)
- Every create/edit view passes:
  - `form`: ModelForm
  - `title`: string
  - `is_edit`: boolean
  - Entity alias vars (`workspace`/`obj`, `story`/`obj`, `comment`/`obj`, `decision`/`obj` on edit)

---

## 5. Templates Contract

Paths strictly mirror the entity structure:
- `templates/bi/collaboration_storytelling/bisharedworkspace/list.html`
- `templates/bi/collaboration_storytelling/bisharedworkspace/detail.html`
- `templates/bi/collaboration_storytelling/bisharedworkspace/form.html`

- `templates/bi/collaboration_storytelling/bidatastory/list.html`
- `templates/bi/collaboration_storytelling/bidatastory/detail.html`
- `templates/bi/collaboration_storytelling/bidatastory/form.html`
- `templates/bi/collaboration_storytelling/bidatastory/presentation.html`

- `templates/bi/collaboration_storytelling/bivisualcomment/list.html`
- `templates/bi/collaboration_storytelling/bivisualcomment/detail.html`
- `templates/bi/collaboration_storytelling/bivisualcomment/form.html`

- `templates/bi/collaboration_storytelling/bidecisionlog/list.html`
- `templates/bi/collaboration_storytelling/bidecisionlog/detail.html`
- `templates/bi/collaboration_storytelling/bidecisionlog/form.html`

All templates extend `templates/base.html` (except `presentation.html` which is a distraction-free presentation canvas, while still inheriting styling and assets) and use color-named badges (`badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate`).

---

## 6. Navigation Contract

In `apps/core/navigation.py`:
```python
"10.18": {
    "Data Stories & Presentations": "bi:bi_data_story_list",
    "Comments & Discussions": "bi:bi_visual_comment_list",
    "Shared Workspaces": "bi:bi_shared_workspace_list",
    "Annotations & Decision Logging": "bi:bi_decision_log_list",
    "Export & Embed to Office": "bi:bi_data_story_list",
},
```
