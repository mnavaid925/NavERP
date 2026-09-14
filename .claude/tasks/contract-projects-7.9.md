# Build contract — Projects 7.9 Collaboration & Communication (`projects`)

> Frozen 2026-09-14 against the live tree at commit `d978cac5` (**BASE** — the 7.8 close-out).
> This file is the single source of truth for the entity-by-entity build: every name below is
> resolved against the real code, not aspirational. Anything not pinned here is not authorized.

## 0. Scope (frozen by the research pass)

Five NavERP.md bullets → **five entity files, six tables, one computed page**:

| Bullet (verbatim NavERP.md 7.9) | What 7.9 owns | Artifact |
|---|---|---|
| **Team Messaging & Channels** | project channels + threaded messages + `@mention` capture | `Channel` [CHN-], `ChannelMessage` [CHM-] |
| **Document Sharing & Co-Editing** | share an existing `core.Document` into a project/channel at an access level, plus a single-editor claim | `DocumentShare` [DSH-] |
| **Meeting Management** | agenda builder + minutes capture + action-item tracking + a declared recurrence | `Meeting` [MTG-] + `MeetingAgendaItem` [AGI-] + `MeetingActionItem` [MAIT-] |
| **Notifications & Alerts** | the per-recipient notification ROWS + the in-app inbox + read state | `ProjectNotification` [NTF-] |
| **Activity Streams & Feeds** | one merged chronological feed over the four registers + `core.AuditLog` | computed page `activity_feed` (no table) |

### Explicit non-goals (each has an owner; do NOT build them here)

| Deferred capability | Owner | Why not here |
|---|---|---|
| Document repository, folders, metadata tags, **version history**, check-in/out, knowledge base, retention | **7.10** | 7.10 is "Document & Knowledge Management" and owns the repository. 7.9 ships the *share* of an already-stored `core.Document`, never a second file store (the 7.1 `charter_document` ruling). |
| **Real-time** collaborative editing (websockets / OT / CRDT) | **7.17 / 7.18** | No async/websocket stack exists in the repo. 7.9 ships the honest non-realtime affordance: an access level + a single-editor claim/release. |
| Notification **trigger rules**, reminders, escalation-on-timeout, delegation | **7.17** ("Notification & Reminder Rules") | 7.9 ships the notification rows, the inbox and the two read verbs; the rule engine that would generate them on a schedule is 7.17's. The seeder and `msg_create` mint rows directly, the way 7.17 will. |
| Recurrence **engine** (auto-creating the next occurrence) | **7.17** | `Meeting.recurrence` *declares* the pattern; nothing schedules it. |
| File-storage sync (SharePoint / Drive / Box / Dropbox) | **7.18** | "File Storage & Collaboration" is 7.18's bullet. |
| Sprint / retrospective boards, standup velocity, team sentiment | **7.13** | 7.9's `Meeting.kind="standup"` is a meeting, not a sprint board. |
| Reactions / likes / social engagement counters beyond reply counts | — | Deferred: a reaction needs its own table and is not load-bearing for the feed. The feed surfaces reply counts instead. |
| Rich-text editor, attachments on a message, edit history of a message body | — | `ChannelMessage` is plain text; a message is a working row. Attachments go through `DocumentShare`. |

**Reuse, not duplication (L28/L29).** `core.Document` EXISTS (`apps/core/models/Document.py:5` — `tenant`, `file`, `name`, `classification`, `version`, GFK `related`) so `DocumentShare.document` FKs it **by string**. `core.AuditLog` EXISTS and backs the feed's audit half. No money column anywhere in 7.9 — cost lives on 7.4's registers.

## 1. Verified ground truth (read, not assumed)

| Fact | Verified at |
|---|---|
| `Project` [PRJ-] `name`/`status`/`STATUS_CHOICES` (`draft/chartered/kickoff/active/on_hold/completed/cancelled`); url name `prj_detail` | `apps/projects/models/ProjectInitiation/Projects.py:56`, `:46`; `templates/projects/taskwork/checklistitem/detail.html:8` |
| `ProjectTask` [TSK-] `number`/`name`; url name `tsk_detail` | `templates/projects/taskwork/checklistitem/list.html:47` |
| `TenantNumbered` (`NUMBER_PREFIX`, `number` CharField(20, editable=False), 5-retry `next_number` loop) + `TenantOwned` (`tenant` rn `+`, `created_at`/`updated_at`) | `apps/projects/models/_base.py:54` / `:41` |
| `core.Document` fields: `tenant`, `file`, `name`, `classification`, `version` (CharField 20, default `"1.0"`), `uploaded_at` | `apps/core/models/Document.py:5` |
| `core.AuditLog`: `tenant` (SET_NULL, db_index), `user`, `target` (CharField 255), `action` varchar(10) `create/update/delete`, `changes` JSON, `at` (auto_now_add); `ordering = ["-at"]`; index `auditlog_tenant_at_idx` | `apps/core/models/AuditLog.py:5` |
| `TenantModelForm` scopes **`ModelChoiceField` only** — a M2M (`ModelMultipleChoiceField`) is **NOT** auto-scoped; it also themes widgets (`form-select` / `form-input` / `form-textarea` / `form-check`) and sets `input_formats` on date/datetime | `apps/core/forms/_common.py:25-56` |
| `crud_list` signature `(request, qs, template, *, search_fields, filters, extra_context, per_page=15)`; context `object_list`/`page_obj`/`q`; the `_enum_values` guard skips a junk enum, `as_db_int` skips junk ints, `0` is skipped for pk lookups only | `apps/core/crud.py:115-168` |
| `crud_detail(..., select_related=())` → context `obj`; `crud_edit` → `form`/`obj`/`is_edit=True`; `crud_create` → `form`/`is_edit=False` (calls `form.save_m2m()`) | `apps/core/crud.py:171-221` |
| `views/_helpers.py` exports `projects(tenant)`, `owners(tenant)` (both `.none()` for a tenant-less user) | `apps/projects/views/_helpers.py:43`, `:79` |
| Badge classes: `badge-green badge-red badge-amber badge-info badge-muted badge-slate` (colour-named ONLY, L33). Stat-icon variants: `blue green orange purple red slate`. `stat-card`/`stat-value`/`stat-label` in use | `static/css/theme.css:286-291`; `templates/projects/taskwork/task_priority.html:57-76` |
| `templates/partials/pagination.html` is L9-safe and preserves every GET param except `page` | `templates/partials/pagination.html` |
| Migration leaf = `0011_taskblock_taskchecklistitem_projecttask_actual_end_and_more` → **7.9's is `0012_…`, assigned by `makemigrations` at generation, NEVER reserved** | `ls apps/projects/migrations/` |
| **35 existing URL first segments** (incl. `""`): `project-requests/ projects/ stakeholders/ kickoffs/ tasks/ dependencies/ milestones/ baselines/ resource-profiles/ allocations/ time-entries/ capacity-demand/ budgetlines/ controlaccounts/ revisions/ expenses/ risks/ responses/ issues/ escalations/ risk-analysis/ risk-monitoring/ quality-plans/ quality-reviews/ inspections/ defects/ quality-improvement/ quality-acceptance/ requirements/ scope-items/ scope-changes/ scope-verifications/ scope-matrix/ checklist-items/ blocks/ task-board/ gantt-timeline/ task-priority/`. The **eight** new segments in §4 are disjoint from all of them and from each other. No route uses a converter in its first component | `apps/projects/urls/__init__.py` |
| Route volume precedent: 7.7 ScopeRequirements = 37 patterns, 7.1 = 32, 7.6 = 32, app total = 222 | `grep -c 'path(' apps/projects/urls/*/*.py` |
| Prefixes **free**: `CHN`, `CHM`, `DSH`, `MTG`, `AGI`, `MAIT`, `NTF`. **Taken**: `MSG` (`scm.IntegrationMessage`), `MAI` (`hrm.MeetingActionItem`), `TSK`/`TASK`/`DEP`/`TCL`/`TBK`/`PRJ` | `grep -rhoE 'NUMBER_PREFIX = "[A-Z]+"' apps/*/models/` |
| Related names **free in `apps/projects`**: `channels`, `messages`, `replies`, `document_shares`, `meetings`, `agenda_items`, `action_items`, `project_notifications`. (The repo-wide hits for `messages`/`document_shares`/`action_items` are on `scm.IntegrationEndpoint` / `scm.PortalAccount` / `hrm.OneOnOneMeeting` — different target models, so no reverse-accessor clash) | `grep -rn 'related_name="…"' apps/*/models/` |
| **Peer territory (DO NOT TOUCH)**: `apps/projects/tests/conftest.py`, any `apps/projects/tests/test_*.py` that is not `test_collab_*`, and `.claude/tasks/test-contract-projects-7.8.md` | — |

## 2. House invariants that bind every 7.9 artifact

- **L16** — every date comparison / stamp uses `timezone.localdate()`; every datetime stamp uses `timezone.now()`.
- **L27** — every 7.9 view is `@login_required` **member-level**; NO `tenant_admin_required` gate anywhere this pass.
- **L11/L35** — every GET int through `as_db_int` (`apps.core.crud`); every enum allow-listed against its CHOICES (or handed to `crud_list`'s own `_enum_values` guard); derived figures are pre-scoped in the VIEW, never faked as DB lookups.
- **L7/L8** — every context key in §5 is pinned; a name not in the template's context renders blank at 200.
- **L10** — no nullable FK inside a `|default:` filter argument (`parent`, `channel`, `shared_with`, `recipient`, `presenter`, `assignee`, `task`, `meeting`, `message` — guard each with `{% if %}…{% else %}—{% endif %}`).
- **L2** — multi-line template notes use `{% comment %} … {% endcomment %}`, never multi-line `{# #}`.
- **L29** — no money column, no `accounting.*` FK anywhere in 7.9.
- **Audit** — `core.AuditLog.action` is varchar(10): 7.9 writes only `create` / `update` / `delete`; the verb goes in `changes={"verb": …, "from": …, "to": …}`. **Every mutating verb captures `previous` BEFORE mutating.**
- **Verbs are POST-only** (`@require_POST`) except the three GET+POST form pages `msg_create`, `mtg_minutes`, `agi_create`, `mai_create`. Every queryset is `filter(tenant=request.tenant)`, never `.all()`.
- **Imports absolute** in all four layers; FKs declared by string (`"projects.Channel"`, `"core.Document"`, `settings.AUTH_USER_MODEL`); no cross-app model import at module level.
- **Layer files**: `apps/projects/{models,forms,views,urls}/CollaborationCommunication/<Entity>.py` — the same file name in all four layers where a forms/urls counterpart exists; **sub-package `__init__.py` files stay EMPTY**; re-exports only in the four top-level `__init__.py` (Integrate step, §7).

## 3. Models

### 3.1 `Channel` [CHN-] — `models/CollaborationCommunication/Channels.py`

Base `TenantNumbered`, `NUMBER_PREFIX = "CHN"`. Docstring must carry: realizes bullet 1's *channels*; a channel is the project's conversation container and owns nothing but its messages and the shares pinned into it; `is_archived`/`archived_by`/`archived_at` are **VERB-WRITTEN by `chn_archive` only** (the verb toggles both directions and stamps/clears together); no money column.

```python
KIND_CHOICES = [("discussion", "Discussion"), ("announcement", "Announcement")]
project = models.ForeignKey("projects.Project", on_delete=models.CASCADE,
                            related_name="channels")
name = models.CharField(max_length=100)
topic = models.CharField(max_length=255, blank=True)
kind = models.CharField(max_length=12, choices=KIND_CHOICES, default="discussion")
is_archived = models.BooleanField(default=False)          # verb-written, OFF the form
archived_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                null=True, blank=True, editable=False, related_name="+")
archived_at = models.DateTimeField(null=True, blank=True, editable=False)
created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                               null=True, blank=True, editable=False, related_name="+")
```

- `Meta.ordering = ["project_id", "name", "id"]`
- `unique_together = (("tenant", "number"), ("tenant", "project", "name"))` — a project cannot carry two channels of the same name.
- `indexes = [models.Index(fields=["tenant", "project"], name="chn_tnt_project_idx"), models.Index(fields=["tenant", "is_archived"], name="chn_tnt_archived_idx")]`
- `@property is_open` → `not self.is_archived`
- `__str__` = `f"{self.number} — {self.name}"`
- **No `clean()`** (no cross-model guard; `project` is `_reject_foreign`-checked on the form).
- **No `message_count` property** — a `.count()` property re-queries per row and defeats `prefetch_related`. The count is annotated/prefetched in the VIEW (§5).

### 3.2 `ChannelMessage` [CHM-] — `models/CollaborationCommunication/ChannelMessages.py`

Base `TenantNumbered`, `NUMBER_PREFIX = "CHM"` (**`MSG` is taken by `scm.IntegrationMessage`** — do not reuse it). Docstring must carry: realizes bullet 1's *threaded discussions* + `@mention` notifications; a thread reply is a row with `parent` set (self-FK), one level of nesting is the UI's business not the schema's; `edited_by`/`edited_at` are **VERB-WRITTEN by `msg_edit` only**; `mentions` is the recorded audience and `msg_create`/`msg_edit` mint the `ProjectNotification` delivery rows from it; no money column.

```python
channel = models.ForeignKey("projects.Channel", on_delete=models.CASCADE,
                            related_name="messages")
parent = models.ForeignKey("self", on_delete=models.CASCADE, null=True, blank=True,
                           related_name="replies")
body = models.TextField()
mentions = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True,
                                  related_name="channel_mentions")
edited_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                              null=True, blank=True, editable=False, related_name="+")
edited_at = models.DateTimeField(null=True, blank=True, editable=False)
created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                               null=True, blank=True, editable=False, related_name="+")
```

- `Meta.ordering = ["channel_id", "created_at", "id"]` (a conversation reads chronologically)
- `unique_together = ("tenant", "number")`
- `indexes = [models.Index(fields=["tenant", "channel"], name="chm_tnt_channel_idx"), models.Index(fields=["tenant", "parent"], name="chm_tnt_parent_idx")]`
- `@property is_reply` → `self.parent_id is not None`
- `@property is_edited` → `self.edited_at is not None`
- `__str__` = `f"{self.number} — {self.body[:60]}"`
- **`clean()`** — the app's `TaskDependency` same-parent guard idiom: when `parent` is set and `parent.channel_id != self.channel_id`, raise `ValidationError({"parent": "A reply must stay in its own channel."})`. Also reject a reply whose parent is itself a reply (`parent.parent_id is not None` → one nesting level).
- **`reply_count` is NOT a property** (same `.count()` ruling as `Channel.message_count`) — the channel detail view builds the thread tree in Python from ONE materialized list.

### 3.3 `DocumentShare` [DSH-] — `models/CollaborationCommunication/DocumentShares.py`

Base `TenantNumbered`, `NUMBER_PREFIX = "DSH"`. Docstring must carry: realizes bullet 2's *document sharing*; the FILE and its VERSION are `core.Document`'s (7.10 owns the repository and version history) — this row is the **share**, i.e. who in this project may do what with an already-stored document; real-time co-editing is deferred (no websocket stack) so the honest affordance is `access_level` + a single-editor **claim** (`claimed_by`/`claimed_at`, verb-written by `dsh_claim`/`dsh_release`); `is_active`/`revoked_by`/`revoked_at` are **VERB-WRITTEN by `dsh_revoke` only**; no money column, no second file store.

```python
ACCESS_CHOICES = [("view", "View only"), ("comment", "Comment"), ("edit", "Can edit")]
project = models.ForeignKey("projects.Project", on_delete=models.CASCADE,
                            related_name="document_shares")
channel = models.ForeignKey("projects.Channel", on_delete=models.SET_NULL, null=True,
                            blank=True, related_name="document_shares")
document = models.ForeignKey("core.Document", on_delete=models.CASCADE,
                             related_name="project_shares")
access_level = models.CharField(max_length=8, choices=ACCESS_CHOICES, default="view")
shared_with = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                null=True, blank=True, related_name="received_document_shares")
note = models.TextField(blank=True)
is_active = models.BooleanField(default=True)              # verb-written, OFF the form
revoked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                               null=True, blank=True, editable=False, related_name="+")
revoked_at = models.DateTimeField(null=True, blank=True, editable=False)
claimed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                               null=True, blank=True, editable=False, related_name="+")
claimed_at = models.DateTimeField(null=True, blank=True, editable=False)
created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                               null=True, blank=True, editable=False, related_name="+")
```

- `Meta.ordering = ["-created_at", "-id"]`
- `unique_together = ("tenant", "number")`
- `indexes = [models.Index(fields=["tenant", "project"], name="dsh_tnt_project_idx"), models.Index(fields=["tenant", "is_active"], name="dsh_tnt_active_idx"), models.Index(fields=["tenant", "document"], name="dsh_tnt_document_idx")]`
- `@property is_revoked` → `not self.is_active`; `@property is_claimed` → `self.claimed_at is not None`; `@property is_co_editable` → `self.is_active and self.access_level == "edit"`
- `__str__` = `f"{self.number} — {self.document.name}"`
- **No `clean()`** (all three FKs are `_reject_foreign`-checked on the form).

### 3.4 `Meeting` [MTG-] + children — `models/CollaborationCommunication/Meetings.py`

**File holds three models** (primary + its two children — the `Invoices.py` = `Invoice` + `InvoiceLine` rule; neither child has an independent register, both are edited on the meeting detail page).

#### `Meeting` — base `TenantNumbered`, `NUMBER_PREFIX = "MTG"`

Docstring must carry: realizes bullet 3; `recurrence` **DECLARES** the pattern only — no scheduler creates the next occurrence (7.17); `minutes`/`minutes_by`/`minutes_at` are **VERB-WRITTEN by `mtg_minutes` only**; `actual_start`/`actual_end` are **VERB-WRITTEN by `mtg_start`/`mtg_complete`**; the status machine is `scheduled → in_progress → completed`, with `cancelled` reachable from `scheduled`/`in_progress`; no money column.

```python
KIND_CHOICES = [("standup", "Standup"), ("review", "Review"),
                ("steering", "Steering Committee"), ("workshop", "Workshop"),
                ("other", "Other")]
MODE_CHOICES = [("in_person", "In person"), ("virtual", "Virtual"), ("hybrid", "Hybrid")]
RECURRENCE_CHOICES = [("none", "One-off"), ("daily", "Daily"), ("weekly", "Weekly"),
                      ("biweekly", "Bi-weekly"), ("monthly", "Monthly")]
STATUS_CHOICES = [("scheduled", "Scheduled"), ("in_progress", "In Progress"),
                  ("completed", "Completed"), ("cancelled", "Cancelled")]
project = models.ForeignKey("projects.Project", on_delete=models.CASCADE,
                            related_name="meetings")
title = models.CharField(max_length=200)
kind = models.CharField(max_length=12, choices=KIND_CHOICES, default="standup")
scheduled_start = models.DateTimeField()
scheduled_end = models.DateTimeField(null=True, blank=True)
location = models.CharField(max_length=200, blank=True)
mode = models.CharField(max_length=10, choices=MODE_CHOICES, default="virtual")
recurrence = models.CharField(max_length=10, choices=RECURRENCE_CHOICES, default="none")
status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="scheduled")
minutes = models.TextField(blank=True)
minutes_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                               null=True, blank=True, editable=False, related_name="+")
minutes_at = models.DateTimeField(null=True, blank=True, editable=False)
actual_start = models.DateTimeField(null=True, blank=True, editable=False)
actual_end = models.DateTimeField(null=True, blank=True, editable=False)
created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                               null=True, blank=True, editable=False, related_name="+")
```

- `Meta.ordering = ["-scheduled_start", "-id"]`
- `unique_together = ("tenant", "number")`
- `indexes = [models.Index(fields=["tenant", "project"], name="mtg_tnt_project_idx"), models.Index(fields=["tenant", "status"], name="mtg_tnt_status_idx"), models.Index(fields=["tenant", "scheduled_start"], name="mtg_tnt_start_idx")]`
- `@property is_upcoming` → `self.status == "scheduled" and self.scheduled_start >= timezone.now()`
- `@property is_past` → `self.scheduled_start < timezone.now()`
- `__str__` = `f"{self.number} — {self.title}"`
- **No `clean()`**; **no `agenda_count`/`agenda_progress` property** (the `.count()` ruling — §5.4 computes both in the view).

#### `MeetingAgendaItem` [AGI-] — base `TenantNumbered`, `NUMBER_PREFIX = "AGI"`

```python
meeting = models.ForeignKey("projects.Meeting", on_delete=models.CASCADE,
                            related_name="agenda_items")
title = models.CharField(max_length=255)
presenter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                              null=True, blank=True, related_name="presented_agenda_items")
duration_minutes = models.PositiveSmallIntegerField(default=0)
sequence = models.PositiveSmallIntegerField(default=0)
is_covered = models.BooleanField(default=False)            # verb-written by agi_cover, OFF the form
covered_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                               null=True, blank=True, editable=False, related_name="+")
covered_at = models.DateTimeField(null=True, blank=True, editable=False)
created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                               null=True, blank=True, editable=False, related_name="+")
```

- `Meta.ordering = ["meeting_id", "sequence", "id"]`; `unique_together = ("tenant", "number")`
- `indexes = [models.Index(fields=["tenant", "meeting"], name="agi_tnt_meeting_idx"), models.Index(fields=["tenant", "is_covered"], name="agi_tnt_covered_idx")]`
- `__str__` = `f"{self.number} — {self.title}"`; **no `clean()`**

#### `MeetingActionItem` [MAIT-] — base `TenantNumbered`, `NUMBER_PREFIX = "MAIT"`

> ⚠️ **`hrm.MeetingActionItem` ALREADY EXISTS** (`apps/hrm/models/ContinuousFeedback/Meetingactionitem.py:5`, HRM 3.20 — an action item on a **1-on-1 meeting**, `NUMBER_PREFIX = "MAI"`). Different app, different domain, no Python or DB conflict — and **do NOT "fix" it by renaming or merging**. The docstring must say so, following the three-`PRJ-`-models precedent in `apps/projects/models/ProjectInitiation/Projects.py:6-17`. This is why the prefix here is `MAIT`, not `MAI`.

Docstring must also carry: realizes bullet 3's *action item tracking*; `is_done`/`done_by`/`done_at` are **VERB-WRITTEN by `mai_toggle` only** (one writer per direction); `task` is an **optional** link to a real `projects.ProjectTask` so a minute can point at the work it produced — 7.9 does **not** create tasks (that is 7.8's register and 7.2's WBS); no money column.

```python
meeting = models.ForeignKey("projects.Meeting", on_delete=models.CASCADE,
                            related_name="action_items")
description = models.TextField()
assignee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                             null=True, blank=True, related_name="meeting_action_items")
due_date = models.DateField(null=True, blank=True)
task = models.ForeignKey("projects.ProjectTask", on_delete=models.SET_NULL, null=True,
                         blank=True, related_name="meeting_action_items")
is_done = models.BooleanField(default=False)               # verb-written by mai_toggle, OFF the form
done_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                            null=True, blank=True, editable=False, related_name="+")
done_at = models.DateTimeField(null=True, blank=True, editable=False)
created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                               null=True, blank=True, editable=False, related_name="+")
```

- `Meta.ordering = ["meeting_id", "id"]`; `unique_together = ("tenant", "number")`
- `indexes = [models.Index(fields=["tenant", "meeting"], name="mai_tnt_meeting_idx"), models.Index(fields=["tenant", "is_done"], name="mai_tnt_done_idx"), models.Index(fields=["tenant", "assignee"], name="mai_tnt_assignee_idx")]`
- `@property is_overdue` → `bool(self.due_date) and not self.is_done and self.due_date < timezone.localdate()` (L16 clock)
- `__str__` = `f"{self.number} — {self.description[:60]}"`; **no `clean()`**

### 3.5 `ProjectNotification` [NTF-] — `models/CollaborationCommunication/ProjectNotifications.py`

Base `TenantNumbered`, `NUMBER_PREFIX = "NTF"`. **Evidence-row ruling (verbatim constraint):** rows are **minted by triggers only** — `msg_create`/`msg_edit` (a `mention`), the seeder, and later 7.17's rule engine — and are **read/closed by `ntf_mark_read`** and **dismissed by `ntf_delete`**. There is **no `ProjectNotification` ModelForm and no `ntf_create`/`ntf_edit` route at all**; `ntf_mark_read` is the ONE writer of `is_read`/`read_at` (one writer per direction, `previous` captured BEFORE mutating). Unlike 7.8's `TaskBlock`, an inbox row IS deletable — it is per-recipient delivery, not shared evidence.

Docstring must also carry: realizes bullet 4's *notification rows* (the trigger RULES are 7.17's) and delivers bullet 1's *@mention notifications*; the four optional source FKs (`channel`/`message`/`task`/`meeting`) are what the feed and the inbox deep-link from; no money column.

```python
KIND_CHOICES = [("mention", "Mention"), ("assignment", "Assignment"),
                ("due_date", "Due Date"), ("status_change", "Status Change"),
                ("system", "System")]
project = models.ForeignKey("projects.Project", on_delete=models.CASCADE,
                            related_name="project_notifications")
recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                              related_name="project_notifications")
kind = models.CharField(max_length=16, choices=KIND_CHOICES, default="system")
title = models.CharField(max_length=255)
body = models.TextField(blank=True)
channel = models.ForeignKey("projects.Channel", on_delete=models.SET_NULL, null=True,
                            blank=True, related_name="project_notifications")
message = models.ForeignKey("projects.ChannelMessage", on_delete=models.SET_NULL, null=True,
                            blank=True, related_name="project_notifications")
task = models.ForeignKey("projects.ProjectTask", on_delete=models.SET_NULL, null=True,
                         blank=True, related_name="project_notifications")
meeting = models.ForeignKey("projects.Meeting", on_delete=models.SET_NULL, null=True,
                            blank=True, related_name="project_notifications")
triggered_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                 null=True, blank=True, related_name="triggered_notifications")
is_read = models.BooleanField(default=False)               # verb-written, OFF any form
read_at = models.DateTimeField(null=True, blank=True, editable=False)
created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                               null=True, blank=True, editable=False, related_name="+")
```

- `Meta.ordering = ["-created_at", "-id"]`
- `unique_together = ("tenant", "number")`
- `indexes = [models.Index(fields=["tenant", "recipient", "is_read"], name="ntf_tnt_recipient_idx"), models.Index(fields=["tenant", "kind"], name="ntf_tnt_kind_idx"), models.Index(fields=["tenant", "project"], name="ntf_tnt_project_idx")]`
- `@property is_unread` → `not self.is_read`
- `__str__` = `f"{self.number} — {self.title}"`
- **No `clean()`**

### 3.6 Migration

`0011_taskblock_taskchecklistitem_projecttask_actual_end_and_more` is the disk leaf → **expect `0012_…`, assigned by `makemigrations` at generation, NEVER reserved.** Announce-then-generate: `manage.py makemigrations projects --dry-run` first; read every model it names — anything beyond the six tables in §3 means **STOP and report**. ONE migration carries all six (build order: `Channel` → `ChannelMessage` → `DocumentShare` → `Meeting` → `MeetingAgendaItem` → `MeetingActionItem` → `ProjectNotification`).

## 4. Forms (`forms/CollaborationCommunication/`)

`TenantUniqueMixin` mixed in **FIRST** on every ModelForm (the house idiom); `tenant=request.tenant` passed on every instantiation. **`_reject_foreign` is applied to tenant-scoped FKs only — NEVER to a `settings.AUTH_USER_MODEL` FK** (users can be tenant-less; the 7.8 `assignee` exemption) and **NEVER to a M2M** (it is a list, so `getattr(chosen, "tenant_id")` would raise `AttributeError`).

| File | Form | `Meta.fields` (in order) | `clean()` |
|---|---|---|---|
| `Channels.py` | `ChannelForm(TenantUniqueMixin, TenantModelForm)` | `["project", "name", "topic", "kind"]` | `_reject_foreign(self, cleaned, ["project"])` |
| `ChannelMessages.py` | `ChannelMessageForm(TenantUniqueMixin, TenantModelForm)` | `["channel", "parent", "body", "mentions"]` | `_reject_foreign(self, cleaned, ["channel", "parent"])` — **`mentions` is NOT passed** (M2M) |
| `DocumentShares.py` | `DocumentShareForm(TenantUniqueMixin, TenantModelForm)` | `["project", "channel", "document", "access_level", "shared_with", "note"]` | `_reject_foreign(self, cleaned, ["project", "channel", "document"])` — **`shared_with` is NOT passed** (User FK) |
| `Meetings.py` | `MeetingForm(TenantUniqueMixin, TenantModelForm)` | `["project", "title", "kind", "scheduled_start", "scheduled_end", "location", "mode", "recurrence"]` | `_reject_foreign(self, cleaned, ["project"])` |
| `Meetings.py` | `MeetingMinutesForm(forms.Form)` | — (`minutes = forms.CharField(required=True, widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 8}))`) | none (the verb body) |
| `Meetings.py` | `MeetingAgendaItemForm(TenantUniqueMixin, TenantModelForm)` | `["title", "presenter", "duration_minutes", "sequence"]` — **`meeting` is EXCLUDED: it comes from the URL pk** | none (`presenter` is a User FK) |
| `Meetings.py` | `MeetingActionItemForm(TenantUniqueMixin, TenantModelForm)` | `["description", "assignee", "due_date", "task"]` — **`meeting` is EXCLUDED: it comes from the URL pk** | `_reject_foreign(self, cleaned, ["task"])` |

### The one non-obvious rule — the M2M scoping gap (do not skip)

`TenantModelForm.__init__` scopes `forms.ModelChoiceField` **only** (`apps/core/forms/_common.py:52`). `mentions` is a `ModelMultipleChoiceField`, so it is **NOT** auto-scoped and a crafted POST could mention a user in **another workspace**, leaking that user's name/email into this tenant's message. `ChannelMessageForm.__init__` MUST close it explicitly:

```python
def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    # TenantModelForm scopes ModelChoiceField only — an M2M is a ModelMultipleChoiceField and
    # is NOT auto-scoped, so a crafted POST could mention a user from another workspace. The
    # narrowed queryset IS the authorization boundary (ModelMultipleChoiceField re-validates
    # every pk against it), which is also why `mentions` is NOT passed to _reject_foreign — a
    # M2M cleaned value is a LIST, and getattr(list, "tenant_id") would raise.
    qs = get_user_model().objects.all() if self.tenant is None \
        else get_user_model().objects.filter(tenant=self.tenant)
    self.fields["mentions"].queryset = qs.order_by("email")
```

`get_user_model()` is imported in the form module (not via `views/_helpers.py` — a form must not import a view helper).

## 5. URLs (`urls/CollaborationCommunication/` — six modules)

Full route table (paths are under the app mount `/projects/`; `app_name = "projects"`). View function name == url name everywhere (house convention).

| Path literal | URL name | View function | Methods | View module |
|---|---|---|---|---|
| `channels/` | `chn_list` | `chn_list` | GET | `urls/CollaborationCommunication/Channels.py` |
| `channels/add/` | `chn_create` | `chn_create` | GET, POST | same |
| `channels/<int:pk>/` | `chn_detail` | `chn_detail` | GET | same |
| `channels/<int:pk>/edit/` | `chn_edit` | `chn_edit` | GET, POST | same |
| `channels/<int:pk>/delete/` | `chn_delete` | `chn_delete` | POST | same |
| `channels/<int:pk>/archive/` | `chn_archive` | `chn_archive` | POST | same |
| `messages/` | `msg_list` | `msg_list` | GET | `urls/CollaborationCommunication/ChannelMessages.py` |
| `messages/add/` | `msg_create` | `msg_create` | GET, POST | same |
| `messages/<int:pk>/edit/` | `msg_edit` | `msg_edit` | GET, POST | same |
| `messages/<int:pk>/delete/` | `msg_delete` | `msg_delete` | POST | same |
| `shared-documents/` | `dsh_list` | `dsh_list` | GET | `urls/CollaborationCommunication/DocumentShares.py` |
| `shared-documents/add/` | `dsh_create` | `dsh_create` | GET, POST | same |
| `shared-documents/<int:pk>/` | `dsh_detail` | `dsh_detail` | GET | same |
| `shared-documents/<int:pk>/edit/` | `dsh_edit` | `dsh_edit` | GET, POST | same |
| `shared-documents/<int:pk>/delete/` | `dsh_delete` | `dsh_delete` | POST | same |
| `shared-documents/<int:pk>/revoke/` | `dsh_revoke` | `dsh_revoke` | POST | same |
| `shared-documents/<int:pk>/claim/` | `dsh_claim` | `dsh_claim` | POST | same |
| `shared-documents/<int:pk>/release/` | `dsh_release` | `dsh_release` | POST | same |
| `meetings/` | `mtg_list` | `mtg_list` | GET | `urls/CollaborationCommunication/Meetings.py` |
| `meetings/add/` | `mtg_create` | `mtg_create` | GET, POST | same |
| `meetings/<int:pk>/` | `mtg_detail` | `mtg_detail` | GET | same |
| `meetings/<int:pk>/edit/` | `mtg_edit` | `mtg_edit` | GET, POST | same |
| `meetings/<int:pk>/delete/` | `mtg_delete` | `mtg_delete` | POST | same |
| `meetings/<int:pk>/start/` | `mtg_start` | `mtg_start` | POST | same |
| `meetings/<int:pk>/complete/` | `mtg_complete` | `mtg_complete` | POST | same |
| `meetings/<int:pk>/cancel/` | `mtg_cancel` | `mtg_cancel` | POST | same |
| `meetings/<int:pk>/minutes/` | `mtg_minutes` | `mtg_minutes` | GET, POST | same |
| `meetings/<int:pk>/agenda/add/` | `agi_create` | `agi_create` | GET, POST | same |
| `agenda-items/<int:pk>/edit/` | `agi_edit` | `agi_edit` | GET, POST | same |
| `agenda-items/<int:pk>/delete/` | `agi_delete` | `agi_delete` | POST | same |
| `agenda-items/<int:pk>/cover/` | `agi_cover` | `agi_cover` | POST | same |
| `meetings/<int:pk>/actions/add/` | `mai_create` | `mai_create` | GET, POST | same |
| `action-items/<int:pk>/edit/` | `mai_edit` | `mai_edit` | GET, POST | same |
| `action-items/<int:pk>/delete/` | `mai_delete` | `mai_delete` | POST | same |
| `action-items/<int:pk>/toggle/` | `mai_toggle` | `mai_toggle` | POST | same |
| `notifications/` | `ntf_list` | `ntf_list` | GET | `urls/CollaborationCommunication/ProjectNotifications.py` |
| `notifications/read-all/` | `ntf_mark_all_read` | `ntf_mark_all_read` | POST | same |
| `notifications/<int:pk>/` | `ntf_detail` | `ntf_detail` | GET | same |
| `notifications/<int:pk>/read/` | `ntf_mark_read` | `ntf_mark_read` | POST | same |
| `notifications/<int:pk>/delete/` | `ntf_delete` | `ntf_delete` | POST | same |
| `activity-feed/` | `activity_feed` | `activity_feed` | GET | `urls/CollaborationCommunication/ActivityFeed.py` |

**40 patterns.** Ordering constraints (first-match-wins):

- Within every module, literal routes precede `<int:pk>/` routes.
- **`notifications/read-all/` MUST be listed BEFORE `notifications/<int:pk>/`** even though `read-all` cannot match an int converter — belt and braces, and it keeps the module readable (the `tasks/bulk-update/` precedent in 7.8's `ProjectTasks.py`).
- The four `meetings/<int:pk>/…` child routes (`agenda/add/`, `actions/add/`) are literal leaves below the int converter — they cannot collide with `meetings/add/` (an int converter does not match `add`).
- **Eight NEW first segments** — `channels/`, `messages/`, `shared-documents/`, `meetings/`, `agenda-items/`, `action-items/`, `notifications/`, `activity-feed/` — disjoint from all 35 existing (§1) and from each other. No route uses a converter in its first component.
- Integrate appends to `urls/__init__.py`: six imports (`from .CollaborationCommunication.ActivityFeed import urlpatterns as _cc_activityfeed`, `…Channels import … as _cc_channels`, `…ChannelMessages import … as _cc_messages`, `…DocumentShares import … as _cc_shares`, `…Meetings import … as _cc_meetings`, `…ProjectNotifications import … as _cc_notifications`) and the concat block appended AFTER the `+ _tw_priority` line, with a `# 7.9 Collaboration & Communication — first segments (…)` disjointness comment matching the 7.2–7.8 blocks.

## 6. Views (`views/CollaborationCommunication/`) — decorators, templates, CONTEXT KEYS

Common: every view `@login_required`; every queryset `filter(tenant=request.tenant)`; absolute imports; `projects(tenant)` / `owners(tenant)` reused from `views/_helpers.py` (**nothing added to `_helpers.py`** — each helper below has one consumer).

### 6.1 `Channels.py`

- **`chn_list`** — `crud_list(request, qs, "projects/collaboration/channel/list.html", search_fields=["number", "name", "topic"], filters=[("project", "project_id", True), ("kind", "kind", False), ("is_archived", "is_archived", False)], extra_context={…})`, `qs = Channel.objects.filter(tenant=request.tenant).select_related("project").annotate(message_count=Count("messages"))`.
  Context: `object_list` (page of `Channel`, each carrying the `message_count` annotation), `page_obj`, `q`, `projects` = `projects(tenant)`.
  **`message_count` is an ANNOTATION, never a model property** (§3.1) — one join, no per-row query.
- **`chn_detail`** — `crud_detail(request, model=Channel, pk=pk, template="projects/collaboration/channel/detail.html", select_related=("project", "created_by", "archived_by"), extra_context={…})`.
  Context: `obj`, plus —
  - `threads` — `list[dict]`, one per ROOT message (`parent_id is None`) in `(created_at, id)` order: `{"root": ChannelMessage, "replies": list[ChannelMessage]}`. Built in Python from **ONE** materialized list `list(obj.messages.select_related("parent", "created_by").order_by("created_at", "id"))` — the `tsk_detail` 31→13-query lesson; never `obj.messages.filter(...)` per thread.
  - `message_count` — `len(<that same list>)` (int).
  - `reply_count` — `sum(len(t["replies"]) for t in threads)` (int).
  - `message_form` — `ChannelMessageForm(tenant=request.tenant, initial={"channel": obj.pk})`.
  - `shares` — `obj.document_shares.select_related("document", "shared_with").filter(is_active=True)` (the pinned-document panel).
- **`chn_create`** — `@login_required`; FIRST LINE tenant-None guard → `messages.error` + `redirect("dashboard:home")` (the `tcl_create` shape). POST: `ChannelForm(request.POST, tenant=request.tenant)`; valid → `form.save(commit=False)`, stamp `tenant` + `created_by`, `save()`, audit `create`, `messages.success` naming `obj.number`, redirect `projects:chn_detail`. Context: `form`, `is_edit=False`.
- **`chn_edit`** — `crud_edit(request, model=Channel, pk=pk, form_class=ChannelForm, template="projects/collaboration/channel/form.html", success_url="projects:chn_list")`. Context: `form`, `obj`, `is_edit=True`. The form cannot touch `is_archived`/`archived_by`/`archived_at` (not in `Meta.fields`).
- **`chn_delete`** — `@login_required` `@require_POST`; `crud_delete(..., success_url="projects:chn_list")`.
- **`chn_archive`** — `@login_required` `@require_POST`. Tenant-scoped `get_object_or_404`. **Toggle**, one writer for both directions: `previous = obj.is_archived` captured BEFORE mutating; archiving sets `is_archived=True`, `archived_by=request.user`, `archived_at=timezone.now()`; unarchiving clears all three to `False`/`None`/`None`. `save(update_fields=["is_archived", "archived_by", "archived_at", "updated_at"])`; audit `update` `changes={"verb": "chn_archive", "from": previous, "to": obj.is_archived}`; `messages.success`; redirect `projects:chn_detail`.

### 6.2 `ChannelMessages.py`

- **`msg_list`** — `crud_list(request, qs, "projects/collaboration/message/list.html", search_fields=["number", "body"], filters=[("channel", "channel_id", True), ("parent", "parent_id", True), ("author", "created_by_id", True)], extra_context={…})`, `qs = ChannelMessage.objects.filter(tenant=request.tenant).select_related("channel", "channel__project", "parent", "created_by").annotate(reply_count=Count("replies"))`.
  Context: `object_list` (each carrying the `reply_count` annotation), `page_obj`, `q`, `channels` = `Channel.objects.filter(tenant=tenant).select_related("project").order_by("number")`, `owners` = `owners(tenant)`.
  The `?parent=` filter is the **thread lens**; a junk value is skipped by `crud_list`'s `as_db_int` guard, and `?parent=0` is skipped by the pk-zero guard.
- **`msg_create`** — `@login_required`; tenant-None guard first (as `chn_create`). Parses `?channel=` and `?parent=` through `as_db_int`. GET → `ChannelMessageForm(tenant=request.tenant, initial={"channel": …, "parent": …})`. POST → valid: `obj = form.save(commit=False)`; stamp `tenant` + `created_by`; `save()`; `form.save_m2m()`; **then `_notify_mentions(request, obj, added=obj.mentions.all())`** (§6.6); audit `create`; `messages.success` naming `obj.number`; redirect `projects:chn_detail` (the channel). Context: `form`, `is_edit=False`.
- **`msg_edit`** — `@login_required`. NOT `crud_edit` (the mention diff needs the before/after set): tenant-scoped `get_object_or_404`; GET → `ChannelMessageForm(instance=obj, tenant=request.tenant)`; POST → capture `before = set(obj.mentions.values_list("pk", flat=True))` **BEFORE** `form.save()`, then `form.save_m2m()`, then `_notify_mentions(request, obj, added=obj.mentions.exclude(pk__in=before))`; stamp `edited_by=request.user`, `edited_at=timezone.now()` and save those two fields; audit `update` with `crud._changed(form)` merged with `{"verb": "msg_edit"}`; redirect `projects:chn_detail`. Context: `form`, `obj`, `is_edit=True`.
- **`msg_delete`** — `@login_required` `@require_POST`; `crud_delete(..., success_url="projects:chn_list")` (a message has no register to return to — it goes back to the channel register).

### 6.3 `DocumentShares.py`

- **`dsh_list`** — `crud_list(request, qs, "projects/collaboration/documentshare/list.html", search_fields=["number", "note", "document__name"], filters=[("project", "project_id", True), ("channel", "channel_id", True), ("access_level", "access_level", False), ("is_active", "is_active", False)], extra_context={…})`, `qs = DocumentShare.objects.filter(tenant=request.tenant).select_related("project", "channel", "document", "shared_with", "claimed_by")`.
  Context: `object_list`, `page_obj`, `q`, `projects` = `projects(tenant)`, `channels` = `Channel.objects.filter(tenant=tenant).select_related("project").order_by("number")`, `access_choices` = `DocumentShare.ACCESS_CHOICES`.
- **`dsh_create`** — tenant-None guard; parses `?project=`/`?channel=` through `as_db_int` for `initial`; `DocumentShareForm(request.POST, tenant=request.tenant)`; valid → stamp `tenant` + `created_by`, `save()`, audit `create`, success naming `obj.number`, redirect `projects:dsh_detail`. Context: `form`, `is_edit=False`.
- **`dsh_detail`** — `crud_detail(..., select_related=("project", "channel", "document", "shared_with", "claimed_by", "revoked_by", "created_by"))`. Context: `obj`.
- **`dsh_edit`** — `crud_edit(..., success_url="projects:dsh_list")`. Context: `form`, `obj`, `is_edit=True`.
- **`dsh_delete`** — `@require_POST`; `crud_delete(..., success_url="projects:dsh_list")`.
- **`dsh_revoke`** — `@login_required` `@require_POST`. **One writer of `is_active`/`revoked_by`/`revoked_at`.** Toggle, `previous` captured BEFORE mutating: revoking → `is_active=False` + stamps; restoring → `is_active=True` + both cleared. A revoke also **releases any active claim** (a revoked share cannot stay claimed). `save(update_fields=["is_active", "revoked_by", "revoked_at", "claimed_by", "claimed_at", "updated_at"])`; audit `update` `changes={"verb": "dsh_revoke", "from": previous, "to": obj.is_active}`; redirect `projects:dsh_detail`.
- **`dsh_claim`** — `@login_required` `@require_POST`. Refused with `messages.error` when `obj.is_revoked` or `obj.access_level != "edit"` (only a co-editable share can be claimed) or when **another user already holds the claim** (the refusal names the holder). On success: `claimed_by=request.user`, `claimed_at=timezone.now()`; audit `update` `changes={"verb": "dsh_claim", "from": previous_holder, "to": request.user.username}`; redirect `projects:dsh_detail`. Re-claiming your OWN share is a no-op with an info message (not an error).
- **`dsh_release`** — `@login_required` `@require_POST`. Refused with `messages.info` when no claim is held. **Any member may release** (a stale claim must not deadlock the document) — the message names whose claim was released. Clears `claimed_by`/`claimed_at`; audit `update` `changes={"verb": "dsh_release", "from": holder, "to": None}`; redirect `projects:dsh_detail`.

### 6.4 `Meetings.py`

- **`mtg_list`** — `crud_list(request, qs, "projects/collaboration/meeting/list.html", search_fields=["number", "title", "location"], filters=[("project", "project_id", True), ("kind", "kind", False), ("status", "status", False), ("mode", "mode", False)], extra_context={…})`, `qs = Meeting.objects.filter(tenant=request.tenant).select_related("project").annotate(agenda_total=Count("agenda_items", distinct=True), agenda_covered=Count("agenda_items", filter=Q(agenda_items__is_covered=True), distinct=True), open_actions=Count("action_items", filter=Q(action_items__is_done=False), distinct=True))`.
  Context: `object_list` (carrying the three annotations), `page_obj`, `q`, `projects` = `projects(tenant)`, `status_choices` = `Meeting.STATUS_CHOICES`, `kind_choices` = `Meeting.KIND_CHOICES`, `mode_choices` = `Meeting.MODE_CHOICES`.
  **All three figures are ANNOTATIONS** (`distinct=True` is mandatory — two `Count`s over two different joins would otherwise multiply rows), never model properties.
- **`mtg_create`** — tenant-None guard; parses `?project=` through `as_db_int` for `initial`; `MeetingForm(request.POST, tenant=request.tenant)`; valid → stamp `tenant` + `created_by`, `save()`, audit `create`, success naming `obj.number`, redirect `projects:mtg_detail`. Context: `form`, `is_edit=False`.
- **`mtg_detail`** — `crud_detail(request, model=Meeting, pk=pk, template="projects/collaboration/meeting/detail.html", select_related=("project", "minutes_by", "created_by"), extra_context={…})`.
  Context: `obj`, plus —
  - `agenda_items` — `list(obj.agenda_items.select_related("presenter").order_by("sequence", "id"))` (**ONE** query, materialized).
  - `action_items` — `list(obj.action_items.select_related("assignee", "task").order_by("id"))` (**ONE** query).
  - `agenda_total` / `agenda_covered` — ints computed in Python over `agenda_items` (§3.4 has no such property, deliberately).
  - `open_action_count` — `sum(1 for a in action_items if not a.is_done)` (int).
  - `overdue_action_count` — `sum(1 for a in action_items if a.is_overdue)` (int).
  - `minutes_form` — `MeetingMinutesForm(initial={"minutes": obj.minutes})`.
  - `agenda_form` — `MeetingAgendaItemForm(tenant=request.tenant)`.
  - `action_form` — `MeetingActionItemForm(tenant=request.tenant)`.
- **`mtg_edit`** — `crud_edit(..., success_url="projects:mtg_list")`. Context: `form`, `obj`, `is_edit=True`. `minutes`/`actual_start`/`actual_end`/`status` are unreachable (not in `Meta.fields`).
- **`mtg_delete`** — `@require_POST`; `crud_delete(..., success_url="projects:mtg_list")`.
- **`mtg_start`** — `@login_required` `@require_POST`. Refused with `messages.error` unless `obj.status == "scheduled"`. `previous = obj.status`; `obj.status = "in_progress"`; `obj.actual_start = timezone.now()`; `save(update_fields=["status", "actual_start", "updated_at"])`; audit `update` `changes={"verb": "mtg_start", "from": previous, "to": obj.status}`; redirect `projects:mtg_detail`.
- **`mtg_complete`** — `@login_required` `@require_POST`. Refused unless `obj.status == "in_progress"`. `previous = obj.status`; `obj.status = "completed"`; `obj.actual_end = timezone.now()`; save those three + `updated_at`; audit `update` `changes={"verb": "mtg_complete", …}`; redirect `projects:mtg_detail`.
- **`mtg_cancel`** — `@login_required` `@require_POST`. Refused with `messages.info` when already `completed` or `cancelled` (terminal). `previous = obj.status`; `obj.status = "cancelled"`; `save(update_fields=["status", "updated_at"])`; audit `update` `changes={"verb": "mtg_cancel", …}`; redirect `projects:mtg_detail`.
- **`mtg_minutes`** — `@login_required` (GET, POST). Tenant-scoped `get_object_or_404`. GET → `MeetingMinutesForm(initial={"minutes": obj.minutes})`. POST → binds `MeetingMinutesForm(request.POST)`; invalid → re-render with the form; valid → `previous = bool(obj.minutes)` captured BEFORE mutating; `obj.minutes = form.cleaned_data["minutes"]`; `obj.minutes_by = request.user`; `obj.minutes_at = timezone.now()`; `save(update_fields=["minutes", "minutes_by", "minutes_at", "updated_at"])`; audit `update` `changes={"verb": "mtg_minutes", "from": previous, "to": True}`; `messages.success`; redirect `projects:mtg_detail`. Context: `form`, `obj`, `is_edit=True`.
  **`mtg_minutes` does NOT change `status`** — capturing minutes is not completing the meeting (`mtg_complete` is).
- **`agi_create`** — `@login_required` (GET, POST). Resolves the meeting from the URL pk tenant-scoped (`get_object_or_404`) → 404 for another workspace's meeting. GET → `MeetingAgendaItemForm(tenant=request.tenant)`. POST → binds; valid → `obj = form.save(commit=False)`; `obj.tenant = request.tenant`; `obj.meeting = meeting`; `obj.created_by = request.user`; `save()`; audit `create`; success naming `obj.number`; redirect `projects:mtg_detail`. Context: `form`, `meeting`, `is_edit=False`.
- **`agi_edit`** — `@login_required` (GET, POST). Tenant-scoped `get_object_or_404(MeetingAgendaItem, pk=pk, tenant=…)`; GET → form with `instance`; POST → valid → `form.save()`; audit `update` with `crud._changed(form)`; redirect `projects:mtg_detail`. Context: `form`, `obj`, `is_edit=True`. `is_covered`/`covered_by`/`covered_at` are unreachable.
- **`agi_delete`** — `@require_POST`; tenant-scoped fetch then `crud_delete(..., success_url="projects:mtg_detail")` — **but `crud_delete` redirects with no pk**, so this view redirects to the MEETING: fetch `obj`, capture `meeting_pk = obj.meeting_id`, audit `delete`, `obj.delete()`, `messages.success`, `redirect("projects:mtg_detail", pk=meeting_pk)`.
- **`agi_cover`** — `@login_required` `@require_POST`. Toggle, one writer for both directions: `previous = obj.is_covered` captured BEFORE mutating; covering stamps `covered_by=request.user`, `covered_at=timezone.now()`, `is_covered=True`; uncovering clears all three. `save(update_fields=["is_covered", "covered_by", "covered_at", "updated_at"])`; audit `update` `changes={"verb": "agi_cover", "from": previous, "to": obj.is_covered}`; redirect `projects:mtg_detail`.
- **`mai_create`** — mirror of `agi_create` for `MeetingActionItemForm`; the `meeting` FK is stamped from the URL pk; audit `create`; redirect `projects:mtg_detail`. Context: `form`, `meeting`, `is_edit=False`.
- **`mai_edit`** — mirror of `agi_edit`; `_reject_foreign(["task"])` runs in the form; audit `update`; redirect `projects:mtg_detail`. `is_done`/`done_by`/`done_at` unreachable.
- **`mai_delete`** — mirror of `agi_delete` (redirect to the meeting).
- **`mai_toggle`** — mirror of `agi_cover` for `is_done`/`done_by`/`done_at`; audit `changes={"verb": "mai_toggle", …}`; redirect `projects:mtg_detail`.

### 6.5 `ProjectNotifications.py`

- **`ntf_list`** — `@login_required`. `qs = ProjectNotification.objects.filter(tenant=request.tenant).select_related("project", "recipient", "kind"→no, "channel", "task", "meeting", "triggered_by")` — i.e. `.select_related("project", "recipient", "channel", "task", "meeting", "triggered_by")`. The **`?mine=1` lens is pre-scoped BEFORE `crud_list`** (only the exact string `"1"` activates; the `tbk_list ?active=1` idiom) → `qs = qs.filter(recipient=request.user)`. Then `crud_list(request, qs, "projects/collaboration/notification/list.html", search_fields=["number", "title", "body"], filters=[("project", "project_id", True), ("recipient", "recipient_id", True), ("kind", "kind", False), ("is_read", "is_read", False)], extra_context={…})`.
  Context: `object_list`, `page_obj`, `q`, `projects` = `projects(tenant)`, `recipients` = `owners(tenant)`, `kind_choices` = `ProjectNotification.KIND_CHOICES`, `mine` (bool), `unread_count` = `ProjectNotification.objects.filter(tenant=tenant, recipient=request.user, is_read=False).count()`.
- **`ntf_detail`** — `crud_detail(..., select_related=("project", "recipient", "channel", "message", "task", "meeting", "triggered_by", "created_by"))`. Context: `obj`.
- **`ntf_mark_read`** — `@login_required` `@require_POST`. Toggle, one writer for both directions: `previous = obj.is_read` captured BEFORE mutating; read → `is_read=True`, `read_at=timezone.now()`; unread → both cleared. `save(update_fields=["is_read", "read_at", "updated_at"])`; audit `update` `changes={"verb": "ntf_mark_read", "from": previous, "to": obj.is_read}`; redirect `projects:ntf_detail`.
- **`ntf_mark_all_read`** — `@login_required` `@require_POST`. Bulk over the **caller's own unread rows only** (`filter(tenant=tenant, recipient=request.user, is_read=False)`) — never another user's inbox. One audit entry per row is not warranted for a bulk read (the `rte_approve_week` precedent) — instead write ONE `AuditLog` row per affected row is **rejected**; this view writes a **single** audit row via `write_audit_log(request.user, <first row>, "update", changes={"verb": "ntf_mark_all_read", "from": count, "to": 0})` only when at least one row changed. `messages.success` naming the count; redirect `projects:ntf_list`.
- **`ntf_delete`** — `@login_required` `@require_POST`. Tenant-scoped fetch; audit `delete`; `obj.delete()`; `messages.success`; redirect `projects:ntf_list`. (An inbox row is per-recipient delivery, not shared evidence — the 7.8 `TaskBlock` no-delete ruling does NOT apply here; §3.5.)

### 6.6 The mention→notification helper (module-private, ONE consumer)

`views/CollaborationCommunication/ChannelMessages.py` defines `_notify_mentions(request, message, added)` — used by BOTH `msg_create` and `msg_edit`, so it lives in the module that owns both (the `_helpers.py` rule: only cross-sub-module helpers move to `_helpers.py`).

```python
def _notify_mentions(request, message, added):
    """Mint one `mention` notification per newly-added mention (never a duplicate).

    `added` is the set of users this call is responsible for — `msg_create` passes every
    mention; `msg_edit` passes only the ones the edit introduced. The author is skipped: you
    do not get notified for mentioning yourself.
    """
```

Each row: `kind="mention"`, `title=f"Mentioned in {channel.number} — {channel.name}"`, `body=message.body[:200]`, `project=channel.project`, `channel=channel`, `message=message`, `recipient=user`, `triggered_by=request.user`, `created_by=request.user`. **The author is skipped** (you are not notified for mentioning yourself), and **the rows are saved one at a time with `row.full_clean(exclude=["number"]); row.save()`** — see the amendment in §10. No per-row audit is written (the trigger is audited on the MESSAGE, which is the row that changed).

### 6.7 `activity_feed` — GET-only, no model (the `task_board` / `gantt_timeline` precedent)

`views/CollaborationCommunication/ActivityFeed.py`, template `projects/collaboration/activity_feed.html`. Module constants pinned:

```python
_FEED_KINDS = [("message", "Channel Message"), ("meeting", "Meeting"),
               ("share", "Document Share"), ("notification", "Notification"),
               ("audit", "Audit Trail")]
_WINDOW_CHOICES = [(7, "Last 7 days"), (30, "Last 30 days"), (90, "Last 90 days")]
_DEFAULT_DAYS = 30
_FEED_CAP = 100        # entries rendered
_SOURCE_CAP = 100      # rows fetched per source before the merge
```

Query params — **exactly these three, nothing else**:
- `?project=` → `as_db_int`, resolved against `Project.objects.filter(tenant=tenant, pk=…)`; a well-formed id that resolves to nothing degrades to the unfiltered feed **with a `messages.warning` naming the fallback** (the 7.8 M11 ruling).
- `?kind=` → allow-listed against `_FEED_KINDS`; a junk value is IGNORED (no filter).
- `?days=` → allow-listed against `{7, 30, 90}`; a junk value falls back to `_DEFAULT_DAYS`.

`since = timezone.now() - timedelta(days=days)`. Five capped source queries (`created_at__gte=since` / `at__gte=since`, each `.select_related(...)`, each `.order_by("-created_at")[: _SOURCE_CAP]`), then merged and sorted in Python by `at` desc, then truncated to `_FEED_CAP`.

**Ruling — audit rows are EXCLUDED when `?project=` is set.** `core.AuditLog` has only a GFK (`content_type`/`object_id`) and a free-text `target`; it cannot be attributed to a project without a join per row type, and guessing from `target` would be a fabricated attribution. So a project-filtered feed is the four collaboration sources, and the page says so in a `{% comment %}` plus visible copy.

Context contract (exact keys):

| Key | Type / content |
|---|---|
| `projects` | tenant `Project` queryset — `projects(tenant)` |
| `project` | `Project` or `None` (from `?project=`) |
| `kinds` | `_FEED_KINDS` — the kind filter dropdown |
| `kind` | `str` — the active kind, or `""` |
| `windows` | `_WINDOW_CHOICES` — the window dropdown |
| `days` | `int` — the resolved window (7/30/90) |
| `since` | `datetime` — `timezone.now() - timedelta(days=days)` |
| `entries` | `list[dict]`, newest first, capped at `_FEED_CAP`: `{"at": datetime, "kind": str, "kind_label": str, "actor": User\|None, "project": Project\|None, "label": str, "detail": str, "url": str\|None, "badge": str}` |
| `counts` | `dict` kind→int over the window BEFORE the cap, EXACTLY the five `_FEED_KINDS` keys (`{"message": int, "meeting": int, "share": int, "notification": int, "audit": int}`); `audit` is `0` when `project` is set |
| `total_count` | `int` — the sum of `counts` (pre-cap) |
| `entry_count` | `int` — `len(entries)` (post-cap) |
| `truncated` | `bool` — `total_count > entry_count` |

Per-kind entry fields (pinned):
- `message` → `actor=created_by`, `project=channel.project`, `label=f"{number} in {channel.name}"`, `detail=body[:160]`, `url=reverse("projects:chn_detail", args=[channel_id])`, `badge="badge-info"`
- `meeting` → `actor=created_by`, `project=project`, `label=title`, `detail=f"{get_kind_display()} · {get_status_display()}"`, `url=reverse("projects:mtg_detail", args=[pk])`, `badge="badge-green"`
- `share` → `actor=created_by`, `project=project`, `label=document.name`, `detail=f"{get_access_level_display()} · v{document.version}"`, `url=reverse("projects:dsh_detail", args=[pk])`, `badge="badge-amber"`
- `notification` → `actor=triggered_by`, `project=project`, `label=title`, `detail=f"{get_kind_display()} → {recipient}"`, `url=reverse("projects:ntf_detail", args=[pk])`, `badge="badge-muted"`
- `audit` → `actor=user`, `project=None`, `label=target or "(no target)"`, `detail=get_action_display()`, `url=None`, `badge="badge-slate"`

Badge classes are colour-named only (L33) and were verified in `theme.css:286-291`.

## 7. Templates (`templates/projects/collaboration/`)

Every page `{% extends "base.html" %}` and fills `{% block title %}` + `{% block content %}`; lists include `{% include "partials/pagination.html" %}` (L9-safe) and a filter bar reflecting `request.GET` with FK `<select>` comparisons via `|stringformat:"d"`. Colour-named badges only; every badge ternary ends `{% else %}{{ obj.get_<field>_display }}{% endif %}`. **No nullable FK inside `|default:`** (L10) — `{% if %}`…`{% else %}—{% endif %}`. Empty states on every list region.

| Path | Rendered by | Shape |
|---|---|---|
| `collaboration/channel/list.html` | `chn_list` | filter bar (`q`, `project`, `kind`, `is_archived`), Actions column (view/edit/delete POST + `confirm()` + `{% csrf_token %}` + the archive toggle POST to `chn_archive`), the `message_count` annotation column |
| `collaboration/channel/detail.html` | `chn_detail` | `obj` header, the thread list from `threads` (root + indented `replies` with per-reply author/`is_edited` badge), the inline composer POSTing to `msg_create` (`message_form`), the pinned-documents panel from `shares`, the archive toggle |
| `collaboration/channel/form.html` | `chn_create` / `chn_edit` | the house `{% for field in form %}` render, `is_edit` heading |
| `collaboration/message/list.html` | `msg_list` | filter bar (`q`, `channel`, `parent`, `author`), Actions column (edit/delete), the `reply_count` annotation column, a "Reply" badge from `is_reply` |
| `collaboration/message/form.html` | `msg_create` / `msg_edit` | the house form render; `mentions` renders as a multi-select; a `{% comment %}` explains that a mention mints a notification on save |
| `collaboration/documentshare/list.html` | `dsh_list` | filter bar (`q`, `project`, `channel`, `access_level`, `is_active`), Actions column (view/edit/delete + the revoke toggle POST), access-level badge, claim badge from `is_claimed` |
| `collaboration/documentshare/detail.html` | `dsh_detail` | `obj` fields, the `document` link (name + `version` + `classification`), the claim panel (claim POST when free and `is_co_editable`; release POST when held), the revoke toggle, a `{% comment %}` recording that version history is 7.10's |
| `collaboration/documentshare/form.html` | `dsh_create` / `dsh_edit` | the house form render; `document` renders as a select over `core.Document` |
| `collaboration/meeting/list.html` | `mtg_list` | filter bar (`q`, `project`, `kind`, `status`, `mode`), the three annotation columns (`agenda_covered`/`agenda_total`, `open_actions`), status badge, Actions column (view/edit/delete) |
| `collaboration/meeting/detail.html` | `mtg_detail` | `obj` header + status badge + the lifecycle verbs (`mtg_start`/`mtg_complete`/`mtg_cancel`, each shown only for the statuses it accepts), the agenda panel (`agenda_items` + `agenda_form` POSTing to `agi_create` + per-item cover toggle POST to `agi_cover` + edit/delete), the minutes panel (`minutes_form` POSTing to `mtg_minutes`, `minutes_by`/`minutes_at` stamps), the action-item panel (`action_items` + `action_form` POSTing to `mai_create` + per-item toggle POST to `mai_toggle` + edit/delete), the `agenda_total`/`agenda_covered`/`open_action_count`/`overdue_action_count` stat row |
| `collaboration/meeting/form.html` | `mtg_create` / `mtg_edit` | the house form render; a `{% comment %}` records that `recurrence` DECLARES the pattern only (no scheduler — 7.17) |
| `collaboration/meeting/minutes.html` | `mtg_minutes` | the minutes editor (`form`), the `obj` header, the existing stamps |
| `collaboration/meeting/agendaitem/form.html` | `agi_create` / `agi_edit` | the house form render (`meeting` is NOT a field — it comes from the URL) |
| `collaboration/meeting/actionitem/form.html` | `mai_create` / `mai_edit` | the house form render (`meeting` is NOT a field — it comes from the URL) |
| `collaboration/notification/list.html` | `ntf_list` | filter bar (`q`, `project`, `recipient`, `kind`, `is_read`) + the "Mine only" lens link (`?mine=1`), the `unread_count` stat, Actions column (view/delete + the read toggle POST), kind badge, unread dot |
| `collaboration/notification/detail.html` | `ntf_detail` | `obj` fields, the four source deep-links (`channel`/`message`/`task`/`meeting`, each `{% if %}`-guarded), the read toggle, `triggered_by`/`read_at` stamps |
| `collaboration/activity_feed.html` | `activity_feed` | the kind filter + window dropdown + project picker, the `counts` stat row (five cards), the merged `entries` timeline (kind badge from `entries[].badge`, `actor`, `label`, `detail`, `at`, the `url` link when set), the `truncated` notice, and the audit-exclusion note when `project` is set |

**Entity SUB-FOLDERS exist for all four entity groups** (`channel/`, `message/`, `documentshare/`, `meeting/` — 7.9 has four entities, so CLAUDE.md rule 3's single-entity collapse does NOT apply); the `activity_feed.html` computed page stands FLAT at the `collaboration/` root (rule 6), as do `meeting/minutes.html` (a secondary entity-action page inside the entity folder — the `cash/bank_transaction/import.html` idiom) and the two child forms under `meeting/agendaitem/` and `meeting/actionitem/` (child entities of the meeting folder).

`templates/projects/collaboration/` is new (verified absent).

**Surgical edits of existing templates** (Integrate): none — 7.9's pages are reachable from `templates/projects/overview.html` (§7.4) and from each other; no existing sub-module's template changes.

## 8. Integration surfaces (Integrate step — single writer, surgical `Edit` with re-read anchors, path-limited commits)

1. **Four top-level `__init__.py`** — append a `# --- 7.9 Collaboration & Communication ---…` block AFTER the existing `# --- 7.8` block in each. A missing re-export is a runtime `ImportError`.
   - `models/__init__.py`: `from .CollaborationCommunication.ChannelMessages import ChannelMessage` + `from .CollaborationCommunication.Channels import Channel` + `from .CollaborationCommunication.DocumentShares import DocumentShare` + `from .CollaborationCommunication.Meetings import (Meeting, MeetingActionItem, MeetingAgendaItem)` + `from .CollaborationCommunication.ProjectNotifications import ProjectNotification` (all `# noqa: F401`).
   - `forms/__init__.py`: `from .CollaborationCommunication.ChannelMessages import ChannelMessageForm` + `from .CollaborationCommunication.Channels import ChannelForm` + `from .CollaborationCommunication.DocumentShares import DocumentShareForm` + `from .CollaborationCommunication.Meetings import (MeetingActionItemForm, MeetingAgendaItemForm, MeetingForm, MeetingMinutesForm)` (grouped per file-of-origin, the 7.8 shape). **No `ProjectNotifications` import — that entity has no form (§3.5).**
   - `views/__init__.py`: `from .CollaborationCommunication.ActivityFeed import activity_feed` + `from .CollaborationCommunication.Channels import (chn_archive, chn_create, chn_delete, chn_detail, chn_edit, chn_list)` + `from .CollaborationCommunication.ChannelMessages import (msg_create, msg_delete, msg_edit, msg_list)` + `from .CollaborationCommunication.DocumentShares import (dsh_claim, dsh_create, dsh_delete, dsh_detail, dsh_edit, dsh_list, dsh_release, dsh_revoke)` + `from .CollaborationCommunication.Meetings import (agi_cover, agi_create, agi_delete, agi_edit, mai_create, mai_delete, mai_edit, mai_toggle, mtg_cancel, mtg_complete, mtg_create, mtg_delete, mtg_detail, mtg_edit, mtg_list, mtg_minutes, mtg_start)` + `from .CollaborationCommunication.ProjectNotifications import (ntf_delete, ntf_detail, ntf_list, ntf_mark_all_read, ntf_mark_read)` (alphabetized inside parens, the 7.8 shape).
   - `urls/__init__.py`: the six imports + concat block per §5.
2. **`admin.py`** — append after the 7.8 block:
   - `ChannelAdmin`: `list_display = ("number", "name", "project", "kind", "is_archived", "tenant")`; `list_filter = ("kind", "is_archived")`; `list_select_related = ("tenant", "project", "created_by")`; `search_fields = ("number", "name", "topic")`; `readonly_fields = ("is_archived", "archived_by", "archived_at", "created_by", "created_at", "updated_at")`.
   - `ChannelMessageAdmin`: `list_display = ("number", "channel", "parent", "created_by", "created_at", "tenant")`; `list_filter = ("created_at",)`; `list_select_related = ("tenant", "channel", "channel__project", "parent", "created_by")`; `search_fields = ("number", "body")`; `readonly_fields = ("edited_by", "edited_at", "created_by", "created_at", "updated_at")`; `filter_horizontal = ("mentions",)`.
   - `DocumentShareAdmin`: `list_display = ("number", "document", "project", "access_level", "shared_with", "is_active", "claimed_by", "tenant")`; `list_filter = ("access_level", "is_active")`; `list_select_related = ("tenant", "project", "channel", "document", "shared_with", "claimed_by")`; `search_fields = ("number", "note", "document__name")`; `readonly_fields = ("is_active", "revoked_by", "revoked_at", "claimed_by", "claimed_at", "created_by", "created_at", "updated_at")`.
   - `MeetingAdmin`: `list_display = ("number", "title", "project", "kind", "status", "scheduled_start", "recurrence", "tenant")`; `list_filter = ("kind", "status", "mode", "recurrence")`; `list_select_related = ("tenant", "project", "created_by")`; `search_fields = ("number", "title", "location")`; `readonly_fields = ("status", "minutes", "minutes_by", "minutes_at", "actual_start", "actual_end", "created_by", "created_at", "updated_at")`.
   - `MeetingAgendaItemAdmin`: `list_display = ("number", "meeting", "title", "sequence", "is_covered", "presenter", "tenant")`; `list_filter = ("is_covered",)`; `list_select_related = ("tenant", "meeting", "meeting__project", "presenter")`; `search_fields = ("number", "title")`; `readonly_fields = ("is_covered", "covered_by", "covered_at", "created_by", "created_at", "updated_at")`.
   - `MeetingActionItemAdmin`: `list_display = ("number", "meeting", "assignee", "due_date", "is_done", "task", "tenant")`; `list_filter = ("is_done", "due_date")`; `list_select_related = ("tenant", "meeting", "meeting__project", "assignee", "task")`; `search_fields = ("number", "description")`; `readonly_fields = ("is_done", "done_by", "done_at", "created_by", "created_at", "updated_at")`.
   - `ProjectNotificationAdmin`: `list_display = ("number", "kind", "title", "recipient", "project", "is_read", "created_at", "tenant")`; `list_filter = ("kind", "is_read")`; `list_select_related = ("tenant", "project", "recipient", "channel", "triggered_by")`; `search_fields = ("number", "title", "body")`; `readonly_fields = ("is_read", "read_at", "created_by", "created_at", "updated_at")`; **`has_add_permission` → `False`** (rows are minted by triggers — an admin add would create a notification with no trigger behind it, the 7.8 `TaskBlockAdmin` ruling).
   - **No surgical edit of any existing admin class.**
3. **`seed_projects.py`** — a `_collab` block with its OWN guard (`Channel.objects.filter(tenant=tenant).exists()`), called after `self._taskwork(tenant, now)` in `_seed_tenant`. Creates, per tenant:
   - **3 channels** on the active project (one `discussion`, one `announcement`, one **archived** with its `archived_by`/`archived_at` stamps) — enough for the `is_archived` facet.
   - **Messages**: a 2-level thread on the discussion channel (1 root + 2 replies, so `threads`/`reply_count` are non-trivial), a root with **no** replies (the empty-thread state), a root with `mentions` (2 users) plus the matching `mention` notifications, one **edited** row (`edited_by`/`edited_at` stamped), and one root on the announcement channel. **≥16 rows total** so the `msg_list` register reaches page 2.
   - **4 `DocumentShare` rows** on the active project: one `edit` + **claimed** (with stamps), one `edit` + unclaimed (so Claim is exercisable), one `comment`, one `view` + **revoked** (with `revoked_by`/`revoked_at`) — every `access_level` and both `is_active` states. The `document` FK reuses a `core.Document` row already on the tenant (create one named "Project status pack" if none exists — **never a second file store**).
   - **3 meetings** on the active project: one `completed` with full minutes + a covered agenda + a mix of open/done action items (one **overdue**), one `in_progress` with an uncovered agenda, one `scheduled` with a recurrence and no agenda. Covers all four statuses across the three plus one `cancelled` — **4 meetings** total then, one per status.
   - **Agenda items**: ≥6 across the meetings, mixing `is_covered` and the `presenter`/`duration_minutes` fields.
   - **Action items**: ≥6 across the meetings, mixing `is_done`, one `is_overdue`, one linked to an existing `ProjectTask` (reuse 7.2's WBS — **never create a task**), one unassigned.
   - **Notifications**: ≥18 rows covering **every** `kind`, both read states, some with each optional source FK set (`channel`/`message`/`task`/`meeting`), a mix of recipients (so the `?recipient=` and `?mine=1` lenses both have rows) — enough for page 2.
   - `--flush`: add `ProjectNotification.objects.all().delete()` **first** (it FKs `Channel`/`ChannelMessage`/`ProjectTask`/`Meeting`), then `MeetingActionItem`, `MeetingAgendaItem`, `DocumentShare`, `ChannelMessage`, `Meeting`, `Channel` — all before `ProjectTask`/`Project`. Update the `add_arguments` help text and extend the imports with all six models.
   - Extend the module docstring with the `_collab` paragraph.
4. **`apps/core/navigation.py`** — one new `LIVE_LINKS["7.9"]` immediately after the `"7.8"` block, keys VERBATIM (character-for-character against NavERP.md 7.9):
   `"Team Messaging & Channels": "projects:chn_list"`; `"Document Sharing & Co-Editing": "projects:dsh_list"`; `"Meeting Management": "projects:mtg_list"`; `"Notifications & Alerts": "projects:ntf_list"`; `"Activity Streams & Feeds": "projects:activity_feed"`. Plus the extra live leaf `"Message Register": "projects:msg_list"` (bullet 1's messaging half has its own register). Justification comments record the two deliberate mappings — bullet 2 → the SHARE register (the repository/version history is 7.10's) and bullet 4 → the notification ROWS (the trigger rules are 7.17's) — mirroring the 7.8 justification-comment style. `_safe_reverse` supports `?query=` (confirmed).
5. **`templates/projects/overview.html` + `views/ProjectInitiation/Overview.py`** — 7.9 quick-link rows in the "Start here" table (channels, meetings, shared documents, notifications, activity feed) + stat cards with NEW context keys `channel_count`, `meeting_count`, `open_action_count`, `unread_notification_count` (`unread_notification_count` scoped to `request.user`; the other three flat per-table counts — the `open_defect_count` shape); extend the intro layer sentence with the 7.9 collaboration layer.
6. **Peer boundary** — none of the above touches `apps/projects/tests/conftest.py` or any `apps/projects/tests/test_*.py`.

## 9. Names reserved for later steps (not built this pass)

Tests: `test_collab_{models,forms,views,security}.py`, fixture block `collab_*`, helpers `_collab_*` (no collision with `test_initiation_*`/`test_planning_*`/`test_resource_*`/`test_cost_*`/`test_risk_*`/`test_quality_*`/`test_scope_*`/`test_taskwork_*`). Smoke script `temp/smoke_79.py` (the `smoke_78.py` sibling). Review file `.claude/tasks/review-projects-7.9.md`. Skill section in `.claude/skills/projects/SKILL.md`; README row → **8 of 19**.

Deferred by ruling (do NOT build): the document repository/folders/versions (7.10), real-time co-editing (7.17/7.18), notification trigger rules + reminders (7.17), the recurrence engine (7.17), file-storage sync (7.18), sprint/retro boards (7.13), message reactions/attachments, rich-text bodies, message edit history, mention autocomplete UI, client-facing channels (7.14), and any mail/push delivery (no mail worker).

## 10. Build-phase amendments (pre-review, 2026-09-14)

Corrections made while writing the code, before any reviewer ran. Where an amendment supersedes a
§-pinned line above, THIS section wins.

1. **`_notify_mentions` saves its rows one at a time, not with `bulk_create`** (amends §6.6).
   `ProjectNotification` inherits `TenantNumbered`, whose `save()` is the ONLY thing that mints the
   per-tenant `NTF-#####` number. `bulk_create` bypasses `save()` entirely, so every fanned-out row
   would have landed with `number=""` — and the **second** one would then have violated
   `unique_together ("tenant", "number")` outright, making a two-person mention a 500. A message
   names a handful of people, so per-row `save()` (the seeder's own path) is the correct trade.
2. **The channel-detail composer carries `channel` as a hidden input** (amends §7's
   `collaboration/channel/detail.html` row). `ChannelMessageForm` requires `channel`, and the
   inline composer on the channel page does not render that `<select>` — the channel is fixed by
   the page. Without the hidden field every post from the channel page would have failed
   validation with "This field is required."
3. **Page-local CSS uses the `collab-` prefix** on `channel/detail.html` (the 7.8 §9.6 `tw-`
   precedent). The rules are contained to that one page and reuse the theme's `--border`
   variable; promotion into `theme.css` is left for when a second page needs them.
4. **`as_db_int` is imported from `apps.core.crud`, not from `views/_common`** (amends §6's
   "Common" paragraph, which lists the shared decorators/helpers). `views/_common.py` re-exports
   the four `crud_*` helpers but not `as_db_int`; the 7.8 `TaskChecklistItems.py` view imports it
   from `apps.core.crud` directly and 7.9 follows that.
5. **`_changed` is imported from `apps.core.crud`** for the `msg_edit` audit (the `hrm`/`scm`
   precedent for a view that audits without `crud_edit`).
