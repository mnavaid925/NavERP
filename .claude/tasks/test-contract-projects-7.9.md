# Test contract — Projects 7.9 Collaboration & Communication (`projects`)

> Pinned **before** any test file was written, per the close-out workflow. Every fixture name,
> every hand-computed figure and every assertion target below is decided here first, so the tests
> cannot drift into asserting whatever the code happens to do.
>
> Isolation basis: `pytest.ini` sets `--reuse-db` (schema reuse only). The `db` fixture wraps each
> test in a transaction that is rolled back, so **within one test the database contains only what
> that test's fixtures created** — which is why the figures below can be pinned EXACTLY rather
> than as `>=`. No 7.9 fixture calls `write_audit_log`, so `AuditLog` is empty unless a test
> itself POSTs a verb.

## 1. Fixtures — helpers (`_collab_*`, module-private to `conftest.py`)

All helpers follow the `_taskwork_*` idiom: build the instance, `full_clean(exclude=["number"])`,
`save()`, return it. `number` is minted by `TenantNumbered.save()`, never passed.

| Helper | Signature | Defaults |
|---|---|---|
| `_collab_document` | `(tenant, **overrides)` | `name="Project status pack.pdf"`, `file="documents/2026/09/status-pack.pdf"` (a bare storage path — `FileField` accepts a string without touching the filesystem), `classification="internal"` |
| `_collab_channel` | `(tenant, project, **overrides)` | `name="Delivery standup"`, `topic="Daily coordination."`, `kind="discussion"`, `is_archived=False` |
| `_collab_message` | `(tenant, channel, **overrides)` | `body="Standing update."`, `parent=None` |
| `_collab_share` | `(tenant, project, document, **overrides)` | `access_level="view"`, `is_active=True`, `shared_with=None`, `channel=None` |
| `_collab_meeting` | `(tenant, project, **overrides)` | `title="Delivery standup"`, `kind="standup"`, `status="scheduled"`, `mode="virtual"`, `recurrence="none"`, `scheduled_start=now+1d`, `scheduled_end=now+1d+1h` |
| `_collab_agenda` | `(tenant, meeting, **overrides)` | `title="Status round"`, `sequence=<next>`, `duration_minutes=10`, `is_covered=False` |
| `_collab_action` | `(tenant, meeting, **overrides)` | `description="Chase the vendor."`, `due_date=None`, `is_done=False`, `assignee=None` |
| `_collab_notification` | `(tenant, project, recipient, **overrides)` | `kind="system"`, `title="Workspace notice"`, `body=""`, `is_read=False`, all four source FKs `None` |

## 2. Fixtures — public (`collab_*`)

Tenant A actors are the root-conftest `tenant_a` / `admin_user` / `member_user` / `client_a` /
`member_client`; tenant B uses `tenant_b` / `admin_b` / `planning_project_b`. Projects reuse
`planning_project_a` / `planning_project_b` (the existing `Project` fixtures) — 7.9 invents no
project.

### Tenant A — subjects
| Fixture | Depends on | Shape |
|---|---|---|
| `collab_document_a` | `tenant_a` | one `core.Document` |
| `collab_channel_a` | `planning_project_a` | open `discussion` |
| `collab_channel_archived_a` | `planning_project_a`, `admin_user` | `is_archived=True` + both stamps |
| `collab_thread_root_a` | `collab_channel_a` | a root with **2** replies |
| `collab_reply_a` | `collab_thread_root_a` | one of those replies |
| `collab_message_bare_a` | `collab_channel_a` | a root with **0** replies |
| `collab_share_edit_free_a` | `planning_project_a`, `collab_document_a` | `access_level="edit"`, active, **unclaimed** |
| `collab_share_edit_claimed_a` | …same | `edit`, active, `claimed_by=admin_user` + `claimed_at` |
| `collab_share_view_a` | …same | `access_level="view"`, active |
| `collab_share_revoked_a` | …same, `admin_user` | `is_active=False` + both revoke stamps |
| `collab_meeting_scheduled_a` | `planning_project_a` | `status="scheduled"` |
| `collab_meeting_in_progress_a` | `planning_project_a` | `status="in_progress"` + `actual_start` |
| `collab_meeting_completed_a` | `planning_project_a` | `status="completed"` + both actual stamps + `minutes`/`minutes_by`/`minutes_at` |
| `collab_meeting_cancelled_a` | `planning_project_a` | `status="cancelled"` |
| `collab_agenda_covered_a` | `collab_meeting_completed_a`, `admin_user` | `is_covered=True` + `covered_by`/`covered_at` |
| `collab_agenda_open_a` | `collab_meeting_completed_a` | `is_covered=False` |
| `collab_action_open_a` | `collab_meeting_completed_a` | `is_done=False`, **no** due date |
| `collab_action_done_a` | `collab_meeting_completed_a`, `admin_user` | `is_done=True` + `done_by`/`done_at` |
| `collab_action_overdue_a` | `collab_meeting_completed_a` | `is_done=False`, `due_date = today - 3` |
| `collab_notification_unread_a` | `planning_project_a`, `admin_user` | `recipient=admin_user`, `is_read=False` |
| `collab_notification_read_a` | `planning_project_a`, `admin_user` | `is_read=True` + `read_at` |
| `collab_notification_other_a` | `planning_project_a`, `member_user` | `recipient=member_user` — **the I8 subject** |

### Tenant A — the figure graph (`collab_figures_a`)
One fixture that builds a **closed, deterministic graph** so the annotated/derived figures are
hand-computable. It returns a dict of the rows it built. All rows hang off `planning_project_a`:

```
2 channels:  ch1 "Figures"   -> 2 messages (root R + 1 reply)
             ch2 "Figures two" -> 1 message  (bare root B)
1 meeting:   "Figures review", status=scheduled
             3 agenda items, 2 covered
             3 action items, 2 open (one of them overdue), 1 done
3 shares:    2 active (edit + view), 1 revoked
4 notifications to admin_user: 3 unread, 1 read
```

**Pinned figures — these are the numbers the tests assert, and they are computed by hand from the
graph above, not read off the code:**

| Figure | Pinned value | Where |
|---|---|---|
| `ch1.message_count` (annotation) | **2** | `chn_list` |
| `ch2.message_count` (annotation) | **1** | `chn_list` |
| `R.reply_count` (annotation) | **1** | `msg_list` |
| `B.reply_count` (annotation) | **0** | `msg_list` |
| `meeting.agenda_total` | **3** | `mtg_list` |
| `meeting.agenda_covered` | **2** | `mtg_list` |
| `meeting.open_actions` | **2** | `mtg_list` |
| `mtg_detail` `open_action_count` | **2** | view context |
| `mtg_detail` `overdue_action_count` | **1** | view context |
| `ntf_list` `unread_count` | **3** (admin_user's own unread) | view context |
| feed `counts["message"]` (`?project=`) | **3** | `activity_feed` |
| feed `counts["meeting"]` (`?project=`) | **1** | `activity_feed` |
| feed `counts["share"]` (`?project=`) | **3** | `activity_feed` |
| feed `counts["notification"]` (`?project=`) | **4** | `activity_feed` |
| feed `counts["audit"]` (`?project=`) | **0** — audit is excluded under a project filter | `activity_feed` |
| feed `total_count` (`?project=`) | **11** = 3+1+3+4+0 | `activity_feed` |
| feed `truncated` (`?project=`) | **False** (11 ≤ `_FEED_CAP` 100) | `activity_feed` |

`counts["audit"]` with **no** project filter is **0** in these tests, because no fixture writes an
audit row and the feed's audit source is tenant- and window-scoped.

### Tenant B — the IDOR subjects (404 as tenant A)
`collab_document_b`, `collab_channel_b`, `collab_message_b`, `collab_share_b`, `collab_meeting_b`,
`collab_agenda_b`, `collab_action_b`, `collab_notification_b`.

### Clients
`collab_admin_client` → `client_a`; `collab_member_client` → `member_client`;
`collab_anon_client` → a bare `Client()`; `collab_tenantless_client` → a `Client()` logged in as a
`tenant=None` user (the tenant-None guard subject).

## 3. `test_collab_models.py` — model contracts

- `NUMBER_PREFIX` for all seven models is exactly `CHN/CHM/DSH/MTG/AGI/MAIT/NTF`, and `MSG`/`MAI`
  are **not** used (the two documented collisions).
- `TenantNumbered.save()` mints `"<PREFIX>-00001"`-shaped numbers, per tenant, with **no blank and
  no duplicate** across two tenants.
- `Channel.unique_together`: a second channel with the same `(tenant, project, name)` raises
  `IntegrityError`; the same name in a DIFFERENT project or tenant is fine.
- `ChannelMessage.clean()`: a reply whose `parent` lives in another channel is rejected; a reply
  whose parent is itself a reply is rejected (one nesting level).
- **I1 regression:** `clean()` refuses to change a root's channel while it has replies elsewhere,
  and **allows** a reply-less root to change channel and a reply's body to be edited in place.
- Derived properties, each pinned: `Channel.is_open`, `ChannelMessage.is_reply`/`is_edited`,
  `DocumentShare.is_revoked`/`is_claimed`/`is_co_editable` (false for a revoked share even at
  `edit`), `Meeting.is_upcoming`/`is_past`, `MeetingActionItem.is_overdue` (true only for an open
  item with a past `due_date`; false for a done item with the same date), `ProjectNotification.is_unread`.
- `Meta.ordering` on all seven models matches the contract §3.
- The seven tables exist with the seven `(tenant, number)` `unique_together` constraints and the
  index names from §3 (plus the four `(tenant, -created_at)` indexes added by migration `0013`).

## 4. `test_collab_forms.py` — form contracts

- `Meta.fields` on all six forms is EXACTLY the contract §4 list, in order — in particular
  `MeetingAgendaItemForm` / `MeetingActionItemForm` **exclude** `meeting`, and every verb-written
  flag is absent from every form (the mass-assignment guard).
- `ChannelMessageForm` M2M scoping: `mentions.queryset` is tenant-scoped; a crafted POST naming a
  **tenant B** user pk is **invalid** (the M2M authorization boundary).
- `ChannelMessageForm` scopes `mentions` to `.none()` for a `tenant=None` form.
- `_reject_foreign` re-checks `channel`/`parent` (message), `project`/`channel`/`document` (share),
  `project` (channel, meeting), `task` (action item) — a crafted POST naming a tenant B pk for each
  is invalid. It must **not** be applied to a User FK (`shared_with`, `assignee`, `presenter`) or
  to the M2M — a tenant B *user* pk on those must be rejected by the queryset, not crash.
- `TenantUniqueMixin` stamps `tenant` before `full_clean()`, so a create-path `clean()` can read it.
- `MeetingMinutesForm` requires a non-empty `minutes`; `MeetingForm` carries the four enum choice
  sets.

## 5. `test_collab_views.py` — view contracts

- Every one of the 41 routes resolves by name; GET pages are 200 for a member and contain the
  pinned content (the object's `number`, and the figure from §2 where the page shows one).
- **Pinned figures are asserted on the RENDERED page**, not just in the context — the
  `collab_figure_project_a` graph's 2/1/3/2/2/1 figures above.
- `activity_feed`: the exact `counts` dict and `total_count` from §2 under `?project=`; `audit`
  excluded and the visible copy says so; `?days=` accepts only 7/30/90 (junk → 30);
  `?kind=` accepts only the five `_FEED_KINDS` (junk ignored); `?project=` naming an unresolvable
  id degrades to the unfiltered feed; `truncated` false at 11 entries.
- **Verb state machines, both directions, each asserting the audit `changes["verb"]`:**
  `chn_archive` (archive → unarchive, stamps set then cleared), `mtg_start` (refused unless
  `scheduled`), `mtg_complete` (refused unless `in_progress`), `mtg_cancel` (refused when terminal),
  `mtg_minutes` (writes body + stamps, **does not** change `status`, refuses empty),
  `agi_cover`, `mai_toggle`, `dsh_revoke` (also releases a claim), `dsh_claim` (refused on
  non-`edit`, refused on revoked, refused when another holds it, own re-claim is a no-op),
  `dsh_release`, `ntf_mark_read`.
- **POST-only:** all 18 verb routes answer GET with **405** (never 302/200).
- **Pagination:** the registers are ordered (no `UnorderedObjectListWarning`) — the C-C regression;
  `?page=9999` is a guarded 200; a register longer than one page yields a page 2 with rows page 1
  does not have.
- **Junk params (L11/L35):** `?project=abc`, `?project=0`, `?project=999999999999999999999`,
  `?kind=nope`, `?status=nope`, `?is_read=nope`, `?page=9999` on the registers → 200, and a junk
  enum must be **skipped, not applied** (the register must not silently empty).
- **Empty state:** every page 200 with no params, and `activity_feed` with a `?project=` that has
  no collaboration rows.
- **The tenant-None guard:** `chn_create` / `msg_create` / `dsh_create` / `mtg_create` redirect to
  the dashboard for a tenant-less user rather than raising.

## 6. `test_collab_security.py` — security contracts

- **Anonymous** → redirect to login on all 41 routes.
- **Cross-tenant IDOR** → **404** for every pk-carrying route (all 30+ GET and POST verbs) as
  tenant A against tenant B's rows.
- **Crafted cross-tenant POST bodies** → invalid form / no row written / no foreign notification
  minted: a tenant B `channel`, `project`, `document`, `task`, `shared_with`, `assignee`,
  `presenter`, or mention pk.
- **I8 regression:** `ntf_mark_read` and `ntf_delete` are **404** for a row addressed to another
  user, and the row is unchanged; the **caller's own** row still works; `ntf_mark_all_read` clears
  only the caller's rows.
- **I1 regression (view level):** a crafted `msg_edit` POST that repoints a root with replies is
  refused and leaves both the root's channel and its replies' visibility intact.
- **CSRF:** every POSTing form page renders `csrfmiddlewaretoken`, and a POST without a token is
  rejected when CSRF is enforced.
- **Mass assignment:** a crafted POST cannot set any verb-written flag (`is_archived`, `is_active`,
  `claimed_by`, `is_read`, `is_covered`, `is_done`, `edited_by`, `status`, `minutes`, `actual_start`).
- **No `|safe`/`mark_safe`/`format_html`** on user-authored text; a `<script>` payload in a message
  body / channel topic / meeting title renders escaped.

## 7. Gate

Iterate with `--nomigrations` while writing; the **final gate is the full unfiltered app suite**
(`apps.projects`) — never `-k`-filtered (L47). Authoritative counts come from a `--junitxml=` file
parsed with `xml.etree`, not from grepping stdout (the shell can swallow the summary line).

Names reserved for later steps (§9 of the build contract): test files `test_collab_{models,forms,
views,security}.py`; the conftest block is **append-only** (L43).
