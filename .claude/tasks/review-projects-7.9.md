# Review — Projects 7.9 Collaboration & Communication

Six read-only lanes ran **serially** (code-reviewer → explorer → frontend-reviewer →
performance-reviewer → qa-smoke-tester → security-reviewer) over the 7.9 file set
(25 new backend files under `apps/projects/{models,forms,views,urls}/CollaborationCommunication/`,
17 templates under `templates/projects/collaboration/`, the six integration surfaces
(the four `__init__.py` re-exports, `admin.py`, `seed_projects.py` `_collab`, `navigation.py`
`LIVE_LINKS["7.9"]`, `Overview.py` + `overview.html`), migration `0012`, and the frozen contract
`.claude/tasks/contract-projects-7.9.md`). Scope is pinned by **file globs, NOT by commit range** —
parallel sessions are live in this tree (L46/L48).

**BASE** = `d978cac5ae35aa259ffa7e90c2fbc5c9905e63d7` (the 7.8 close-out).
**HEAD at review time** = `ec735337` (59 build commits + 2 verification fixes).

## Build-phase context for the lanes

- **Smoke gate** (`temp/smoke_79.py`, inline, Step 3 verify): **276/276 PASS**. It renders all 41
  routes with CONTENT assertions, asserts the 18 POST-only verbs answer GET with 405, throws
  **35 junk-param combinations** at the six registers (L11/L35), walks page 2, hits the empty and
  no-param states, checks **30 cross-tenant IDOR probes → 404**, exercises every verb state machine
  in both directions, verifies `AuditLog.changes["verb"]` for all 12 verbs, and asserts the
  mention→notification fan-out (one row per target, author skipped, cross-tenant target rejected).
- **Two Criticals were found and fixed DURING Step 3 verification, before any lane ran.** They are
  already committed (`a187eada`, `ec735337`) and the smoke is green against the fixes. Lanes should
  **sanity-check the fixes** rather than re-report them:
  - **C-A (fixed):** `mtg_start`/`mtg_complete`/`mtg_cancel` refusal paths carried a **Django
    template filter inside a Python f-string** — `f"{obj.get_status_display()|lower}"` — so every
    refusal raised `NameError: name 'lower' is not defined`, i.e. a **500 on the guard path** of all
    three lifecycle verbs. Fixed to `.lower()`. A repo-wide grep for the same leak (`\}\|[a-z_]+`)
    found **no other occurrence** in `apps/`.
  - **C-B (fixed):** `msg_edit` called `form.save_m2m()` after `form.save()`. `ModelForm.save()` at
    the default `commit=True` calls `_save_m2m()` internally and deliberately does **not** leave a
    `save_m2m` attribute (only `commit=False` does), so the call was an `AttributeError` — **every
    message edit 500'd**. The `msg_create` pairing (`save(commit=False)` + `save_m2m()`) is correct
    and was left alone.
- **Two further defects were found by an extended Step 3 probe (after lanes 1–4 had run) and are
  also already fixed** — committed as `1 ok`…`4 ok` (the four `fix(projects): 7.9 …` commits
  immediately preceding `HEAD`). Lanes 5–6 review the FIXED tree; lanes 1–4 reviewed the tree
  before these two were closed:
  - **C-C (fixed):** `chn_list`, `msg_list` and `mtg_list` **paginated an unordered queryset**.
    Adding `.annotate(...)` puts a `GROUP BY` on the query, and Django's `QuerySet.ordered` returns
    `False` whenever a GROUP BY is present — so `Meta.ordering` was silently ignored and
    `Paginator` sliced an unordered set (a row can appear on two pages or be skipped entirely;
    Django raises `UnorderedObjectListWarning`). This pattern was **new in 7.9**: none of the
    pre-7.9 `projects` list views warn. Fixed by re-stating each model's own `Meta.ordering`
    explicitly via `.order_by(...)` on the three querysets.
  - **C-D (fixed):** the `_collab` seeder created **13** messages where contract §8.3 pinned **≥16**
    ("enough for the `msg_list` register reaches page 2"), and its own docstring claimed 17 — so the
    message register could never paginate and the contract's stated pagination demonstration did not
    exist. Fixed by seeding five more messages (**18** per tenant) and correcting the docstring's
    breakdown.
  - **The smoke itself was under-asserting on both.** Its old page-2 checks grepped the rendered HTML
    for the row prefix — but `Paginator.get_page()` **falls back to the last in-range page** when
    `?page=` overshoots, so the prefix appears even on a single-page register. That is a false pass.
    The checks now assert (a) `page_obj.paginator.num_pages > 1`, (b) that page 2 carries row numbers
    page 1 does not, and (c) that no `UnorderedObjectListWarning` is raised. The script also now
    calls `setup_test_environment()`, without which `response.context` is `None` and every
    context-key assertion silently degrades to a no-op.
- **Contract §10 records five build-phase amendments** (per-row notification save instead of
  `bulk_create`; the channel-composer hidden `channel` input; the page-local `collab-` CSS prefix;
  `as_db_int` imported from `apps.core.crud`; `_changed` likewise). Lanes should treat §10 as
  superseding any §-pinned line it contradicts.
- **Deliberate boundary rulings** the lanes should test against, not re-litigate: 7.10 owns the
  document repository/version history (7.9 ships the *share* of an existing `core.Document`);
  7.17 owns notification trigger rules, reminders and the recurrence **engine**
  (`Meeting.recurrence` merely *declares* the pattern); 7.13 owns sprint/retro boards; 7.18 owns
  file-storage sync. `ProjectNotification` has **no form and no create/edit route by design** —
  rows are minted by triggers only.
- **Seeded shape** (both tenants): 3 channels (one archived), 13 messages, 4 document shares
  (all three access levels, one revoked, one claimed), 4 meetings (one per status), 8 agenda items,
  7 action items (one overdue, one task-linked), 18 notifications (all five kinds, both read
  states).

---

## Lane findings (raw, appended per lane)

### Lane 1 — code-reviewer (serial pass 1)

**Scope check.** Read in full: all **25** backend files under
`apps/projects/{models,forms,views,urls}/CollaborationCommunication/`; all **17** templates under
`templates/projects/collaboration/`; migration `0012_…`; and all five integration surfaces (the four
top-level `__init__.py` re-exports, the `admin.py` 7.9 block, `seed_projects.py` `_collab` +
`--flush` ordering + imports, `navigation.py` `LIVE_LINKS["7.9"]`, `Overview.py` +
`overview.html`). Read for context: `apps/core/crud.py`, `apps/core/forms/_common.py`,
`apps/core/utils.py`, `apps/core/models/AuditLog.py`, `apps/core/models/Document.py`,
`apps/projects/models/_base.py`, `views/_common.py`, `views/_helpers.py`, `forms/_common.py`, and
`static/css/theme.css` (class-existence only). **Could not verify:** anything runtime — this is a
static lane, so the smoke gate's 247/247, the 30 IDOR probes and the per-page query counts are taken
as reported rather than re-executed; `manage.py check`/`makemigrations --check` were not run.

**C-A sanity check — PASS.** `grep -rnE '\}\|[a-zA-Z_]+' apps/ --include=*.py` returns exactly one
hit and it is a crm *test* string (`apps/crm/tests/test_documents_19.py:334`), not an f-string. All
three lifecycle refusal paths now use a plain method call —
`Meetings.py:130`, `:149`, `:168` are `{obj.get_status_display().lower()}` with no template filter.
The claim "no other occurrence" holds repo-wide.

**C-B sanity check — PASS.** `grep -rn save_m2m apps/` shows `ChannelMessages.py:63` only (plus the
two explanatory comment lines at `:92-93`); `msg_edit` no longer calls it. The surviving
`msg_create` pairing is correct: `save(commit=False)` → stamp `tenant`/`created_by` → `save()` →
`form.save_m2m()` (`:59-63`). No other 7.9 view calls `save_m2m()`, and the only other callers in the
tree (`crud.py:184`, `accounts`, `hrm`, `procurement`) all pair it with `commit=False`.

**Coverage — clean categories (no findings filed).**
- *Correctness / data safety:* the status machine, all five toggles (`chn_archive`, `dsh_revoke`,
  `agi_cover`, `mai_toggle`, `ntf_mark_read`) clear **every** sibling stamp in the clearing direction,
  and every mutating verb captures `previous` **before** mutating. All 12 audit verbs write
  `action ∈ {create, update, delete}` (≤10 chars) with the verb in `changes`, and every `changes`
  value is JSON-serialisable (bools, ints, strings, `None`). `mtg_minutes` correctly does not touch
  `status`. The only correctness defect is **I1**.
- *Multi-tenancy:* clean. Every queryset in all six view modules is `filter(tenant=request.tenant)`
  (or reached through a tenant-verified parent, e.g. `obj.messages` / `obj.document_shares` in
  `chn_detail`); `crud_detail`/`crud_edit`/`crud_delete` all fetch with `pk=…, tenant=request.tenant`;
  no `Model.objects.all()` anywhere in the 7.9 views. Every form is a `TenantModelForm` (FK
  `ModelChoiceField`s auto-scoped) plus `_reject_foreign` on the tenant-scoped FKs only; the
  `mentions` M2M is explicitly narrowed in `ChannelMessageForm.__init__` (`:41-43`) and deliberately
  excluded from `_reject_foreign`. `shared_with`/`presenter`/`assignee` are User FKs, exempt as
  designed, and still bounded by the scoped `ModelChoiceField`.
- *Contract fidelity:* all **41** route names in contract §5 exist with the pinned view functions and
  methods (the contract's "40 patterns" is an arithmetic slip — the table itself lists 41, as the
  smoke gate's "41 routes" confirms). Every context key in contract §5/§6.1–6.7 is present with the
  pinned name — checked key by key, including `threads`/`message_count`/`reply_count`/`shares`,
  `agenda_total`/`agenda_covered`/`open_action_count`/`overdue_action_count`, `mine`/`unread_count`,
  and all 12 `activity_feed` keys. All 43 distinct `{% url %}` names used in the templates resolve
  (`projects:prj_detail`, `projects:tsk_detail`, `projects:overview` verified in the earlier
  modules). `chn_detail`'s `reply_count` is `len(rows) - len(roots)`, arithmetically identical to the
  contract's `sum(len(t["replies"]) …)`.
- *L-rules:* L2 clean (no multi-line `{# #}`; every long note is `{% comment %}`); L7/L8 clean (see
  above); L9 clean (both lists and every detail page use the safe `partials/pagination.html`); L10
  clean (every `|default:` on a nullable FK sits behind an `{% if %}`; the unguarded `|default:"—"`
  uses are on `TextField`/`CharField` only); L11/L35 clean (`crud_list` guards every int-FK and enum
  param, and `activity_feed` uses `as_db_int` + explicit allow-lists for all three of its params);
  L16 clean (`timezone.now()` for datetimes, `timezone.localdate()` in `MeetingActionItem.is_overdue`
  and `Overview.py`); L27 clean (all 7.9 views are `@login_required` member-level, no
  `tenant_admin_required`); L28/L29 clean (`core.Document` reused by string, no second file store, no
  money column, no `accounting.*` FK); L33 clean (`grep` shows only `badge-green/red/amber/info/muted/
  slate` and `stat-icon blue/green/orange/purple/red/slate`, all defined in `theme.css`; no semantic
  `-success/-danger` anywhere).
- *N+1 / query shape:* clean apart from **M1**. No model ships a `.count()` property
  (`Channel.message_count`, `ChannelMessage.reply_count`, `Meeting.agenda_*` are all view annotations
  or Python counts over one materialised list, exactly as §3.1/§3.2/§3.4 pin); the three `mtg_list`
  `Count`s all carry `distinct=True` over two joins; `chn_detail` builds the thread tree from ONE
  materialised list.
- *Migration:* `0012` matches the six models exactly (fields, `null`/`default`, `on_delete`, all
  indexes, both `unique_together` sets on `Channel`), and `dependencies` correctly name the leaf
  `0011`. No destructive operation.
- *Readability / dead code:* no `print`/`TODO`/`FIXME`/`pdb` in any 7.9 file; docstrings are accurate
  against the code. Two cosmetic notes, not filed: the contract's "40 patterns" and the matching
  "40 routes across six modules" comment in `views/__init__.py:325` should both read 41; and
  `channel/list.html:31-35` hardcodes the two `KIND_CHOICES` values instead of taking a
  `kind_choices` context key — the contract's §6.1 context list deliberately omits that key (unlike
  §6.4/§6.5 for meetings/notifications), and the hardcoded values match the model exactly, so this is
  a drift risk only, not a defect today.

**Findings.**

- [I1] Editing a thread ROOT message lets it move to another channel, stranding its replies
  file: `apps/projects/views/CollaborationCommunication/ChannelMessages.py`  lines: 86-104
  finding: `msg_edit` binds the full `ChannelMessageForm`, whose `Meta.fields` includes `channel`
  (`forms/CollaborationCommunication/ChannelMessages.py:34`), so the edit form renders a channel
  `<select>` and a POST may repoint a message at a different channel. `ChannelMessage.clean()`
  returns early when `parent_id is None` (`models/CollaborationCommunication/ChannelMessages.py:70-72`),
  so the move of a **root** is accepted and its existing replies keep the OLD `channel_id` — now
  violating the model's own documented invariant ("A reply must stay in the channel its parent message
  belongs to"). `chn_detail` builds `roots` from the channel-scoped `obj.messages` and keys `replies`
  by parent pk, so a reply whose root has left the channel is silently dropped from `threads`
  (`Channels.py:53-60`) while `reply_count = len(rows) - len(roots)` (`Channels.py:65`) still counts
  it — the page then says "N in thread" and renders none of them. Reachable from the ordinary edit
  page (`message/form.html` renders every field), so it is not an admin-only path. Graded Important
  rather than Critical because no row is destroyed and no tenant boundary is crossed — the rows
  merely become unreachable from their thread — but it is a genuine invariant break on a mainline
  edit, and the model claims to enforce the invariant.
  fix: Guard the move in `msg_edit` — reject a channel change when the message is a root with
  `obj.replies.exists()` (add the error to the form so it re-renders), or make `channel` read-only in
  that state, or re-stamp `replies.update(channel_id=…)` inside the same `transaction.atomic()`.
  Mirror the same-channel rule that `clean()` already enforces for replies.

- [M1] `ntf_list` dereferences `obj.message` but omits `"message"` from `select_related` (N+1)
  file: `apps/projects/views/CollaborationCommunication/ProjectNotifications.py`  lines: 29-30
  finding: the register's `select_related` tuple is `("project", "recipient", "channel", "task",
  "meeting", "triggered_by")`, but `templates/projects/collaboration/notification/list.html:86`
  dereferences `obj.message.number` for every row that carries a message — one extra query per such
  row, i.e. up to `per_page` = 15 extra queries per page of the inbox. Contract §6.5 pins this exact
  tuple, so it is the template's extra dereference that drifted, not the view (the same
  `tsk_detail`-style N+1 the 7.8 pass removed elsewhere; also routable to performance-reviewer).
  fix: add `"message"` to the `select_related(...)` call in `ntf_list`.

- [M2] Notification list builds a `chn_detail` URL from a nullable `channel_id`
  file: `templates/projects/collaboration/notification/list.html`  lines: 86
  finding: `{% if obj.message %}<a href="{% url 'projects:chn_detail' obj.channel_id %}">` guards on
  `obj.message` but reads `obj.channel_id`. Both FKs are `SET_NULL` and can be NULL independently —
  `ProjectNotificationAdmin` leaves `channel` editable (`admin.py:502-509`; only `is_read`/`read_at`
  are read-only) — so an admin can clear `channel` while `message` stays set, and `{% url %}` then
  receives `None` → `NoReverseMatch` → 500 on the inbox. No 7.9 route can produce that state
  (deleting a channel cascades its messages, so both FKs null together), hence Minor.
  fix: guard on both — `{% if obj.message and obj.channel %}…{% elif obj.channel %}…` — or add
  `channel` to `ProjectNotificationAdmin.readonly_fields`.

- [M3] `activity_feed` zeroes the other four kind counts whenever `?kind=` is set
  file: `apps/projects/views/CollaborationCommunication/ActivityFeed.py`  lines: 85-86, 89-161, 179
  finding: `counts` starts all-zero and only the kinds in `want` are ever filled, so `?kind=message`
  renders the Meeting / Document share / Notification / Audit stat cards as `0` even though rows
  exist in the window. Contract §6.7 pins `counts` as "kind→int over the window BEFORE the cap,
  EXACTLY the five `_FEED_KINDS` keys" and documents exactly one zeroing rule — "`audit` is `0` when
  `project` is set" — while the `?kind=` filter is documented to narrow only the entries. The card row
  is therefore misleading on a filtered view. Flagged Minor because it is a display figure, not the
  filter itself; if the zeroing is deliberate the contract wording needs amending.
  fix: always compute the five counts (the `qs.count()` for each source, with `project` scoping and
  the `audit`-when-`project` rule), and let `want` gate only the fetch loop.

- [M4] The activity feed's `truncated` notice is hidden under a project filter
  file: `templates/projects/collaboration/activity_feed.html`  lines: 82-86
  finding: the "showing the most recent {{ entry_count }}" caveat sits only in the `{% else %}`
  (no-project) branch, so a project-filtered feed silently drops it even when
  `total_count > entry_count`. Contract §7 lists "the `truncated` notice" as part of the page without
  exempting the project-filtered state.
  fix: hoist the truncated sentence out of the `{% if project %}…{% else %}` split (or repeat it in
  the `{% if project %}` branch).

### Lane 2 — explorer (serial pass 2)

**Scope check.** All six verification areas completed, cross-repo and strictly read-only (no
state-mutating command was run; the only file written is this one). Read in full: the frozen
contract; all **5** 7.9 model files, **4** form files, **6** view files, **6** url modules; the four
sub-package `__init__.py`; the four top-level `__init__.py` 7.9 blocks; migration
`0012_channel_channelmessage_documentshare_meeting_and_more`; the `admin.py` 7.9 block; the
`navigation.py` `LIVE_LINKS["7.9"]` block; the `seed_projects.py` `_collab` block; and the
`templates/projects/collaboration/` tree. Ran repo-wide greps over `apps/*/models/`,
`apps/*/migrations/` and `templates/`, and compared 7.9 against the most recently closed sibling
sub-module `TaskWorkManagement/` (7.8). **Nothing in the six areas was unverifiable.** I did not
duplicate Lane 1's findings; I independently agree with all of them (including the C-A/C-B sanity
checks and I1/M1–M4) and found no basis to dispute any.

**Area verdicts (coverage — a clean area is a result):**

1. **Spine reuse (L28/L29) — CLEAN.** `DocumentShare.document` FKs `"core.Document"` by string
   (`models/CollaborationCommunication/DocumentShares.py:47-48`; migration `to='core.document'`), and
   7.9 ships **no** `FileField`/`ImageField`/`BinaryField`/`upload_to` and **no** version column — no
   second file store. `MeetingActionItem.task` FKs `"projects.ProjectTask"`
   (`Meetings.py:182-184`) and 7.9 defines **no** task model. The feed reads the existing
   `core.AuditLog` (`views/.../ActivityFeed.py:28,153`) and mints **no** log table. Repo-wide grep of
   the 7.9 trees for `accounting` returns only one *docstring* mention; the five model files contain
   **no** `DecimalField`/`FloatField` and **no** `accounting.*` FK — the only money-word hits are the
   five "No money column" docstrings. L29 holds.
2. **Namespace collisions — CLEAN (no genuine collision).** Each of `CHN`/`CHM`/`DSH`/`MTG`/`AGI`/
   `MAIT`/`NTF` occurs exactly once in the tree and it is 7.9's (`MSG`→`scm.IntegrationMessage`,
   `MAI`→`hrm.MeetingActionItem` confirmed as the only other owners). Of the seven model class names
   only `MeetingActionItem` is duplicated, in `hrm` — **deliberately documented** in the model
   docstring (`Meetings.py:152-169`), so per the brief it is not a defect. Every 7.9 `related_name`
   was checked against its **target** model: `channels`/`meetings`/`project_shares`/`channel_mentions`/
   `received_document_shares`/`presented_agenda_items`/`triggered_notifications` are unique repo-wide;
   `messages`, `document_shares`, `action_items`, `meeting_action_items` also exist in `scm`/`hrm` but
   on **different target models** (`scm.IntegrationEndpoint`, `scm.PortalAccount`,
   `hrm.OneOnOneMeeting`, `hrm.EmployeeProfile` — verified not a `User` proxy), so there is no
   reverse-accessor clash. All 18 `chn_*`/`chm_*`/`dsh_*`/`mtg_*`/`agi_*`/`mait_*`/`ntf_*` index names
   are unique repo-wide (each appears only in its model file + migration) and are ≤30 chars; the
   `hrm.MeetingActionItem` indexes are `hrm_mai_tenant_*_idx`, a **different** string from 7.9's
   `mait_tnt_*_idx` — no real clash.
3. **URL segment disjointness — CLEAN, 1 contract-count error (M5).** Independent extraction
   (`grep -rhoE 'path\("[^/"]*/' apps/projects/urls/ | sort -u`) yields **46** distinct first
   segments: the 8 new ones (`channels/`, `messages/`, `shared-documents/`, `meetings/`,
   `agenda-items/`, `action-items/`, `notifications/`, `activity-feed/`) plus 38 pre-existing — all
   46 distinct, so the 8 are disjoint from every existing segment and from each other. No route in the
   app uses a converter in its first component (`grep -rnE 'path\("<' apps/projects/urls/` → no
   match), so no module can shadow another's namespace. Ordering constraints hold: every module lists
   literals before `<int:pk>/`, and `notifications/read-all/` precedes `notifications/<int:pk>/`
   (`urls/CollaborationCommunication/ProjectNotifications.py:13-15`). 41 patterns total
   (6+4+8+17+5+1). The contract's *conclusion* is right; only its §1 count is wrong (M5).
4. **Layer/package structure — 1 finding (M7).** All four layers are packages with a
   `CollaborationCommunication/` sub-package and one file per entity; filenames line up across layers
   (`Channels`, `ChannelMessages`, `DocumentShares`, `Meetings` in all four; `ProjectNotifications` in
   models/views/urls only, `ActivityFeed` in views/urls only — both asymmetries **explicitly
   authorised** by the contract and matching the sibling's own asymmetry, e.g. 7.8 `ProjectTasks.py`
   in forms/views/urls but not models). The sub-package `__init__.py` files carry **docstrings only,
   no imports/re-exports** — the same "intentionally empty of re-exports" shape as the sibling — and
   every re-export lives in the four top-level `__init__.py`. `Meetings.py` holding three models is
   CLAUDE.md rule 2 (primary + its children). The one drift is template nesting depth (M7).
5. **Convention drift vs siblings — CLEAN, plus the M7 layout note.** Against 7.8
   `TaskWorkManagement/`: module docstrings on every file (both); view function name == url name
   (both); decorator order `@login_required` then `@require_POST` (both, e.g.
   `views/.../Channels.py:109-111` vs `TaskChecklistItems.py:77-78`); `crud_list`/`crud_detail`/
   `crud_edit`/`crud_delete` used and `crud_create` **not** used — 7.9 hand-rolls the create views
   exactly like the sibling's `tcl_create` (tenant-None guard → `messages.error` →
   `redirect("dashboard:home")`, then `save(commit=False)` + stamp `tenant`/`created_by` + audit +
   success naming `obj.number` + redirect to detail; compare `views/.../Channels.py:73-91` with
   `TaskChecklistItems.py:40-59`); seeder `_collab` uses the identical per-tenant guard shape as
   `_taskwork` (`seed_projects.py:1989-1992` vs `:1867-1870`). No un-authorised divergence found.
6. **Migration sanity — CLEAN.** `0012` is additive-only: exactly 7 `CreateModel`, 18 `AddIndex`, 7
   `AlterUniqueTogether`; **no** `DeleteModel`/`AlterField`/`RemoveField`/`AddField`-on-existing. The
   18 indexes match the models' `Meta.indexes` one-for-one (Channel 2, ChannelMessage 2,
   DocumentShare 3, Meeting 3, MeetingActionItem 3, MeetingAgendaItem 2, ProjectNotification 3 — no
   missing, no extra), and both `Channel` constraints are carried. It creates exactly the **seven**
   models the contract's §3 names and nothing beyond. `dependencies` are right: the projects leaf
   `0011_…`, `swappable_dependency(AUTH_USER_MODEL)`, and `('core','0004_add_candidate_party_role')`
   — the last is the established idiom for a `core.Document` FK (procurement `0020`/`0028` and
   projects `0001` all use `0004`; `Document` is created in core `0001`, which `0004` depends on).

**Findings.**

- [M5] Contract §1 miscounts the existing URL first segments (35 stated, 38 real)
  file: `.claude/tasks/contract-projects-7.9.md`  lines: 50
  finding: the §1 ground-truth row claims "**35 existing URL first segments** (incl. `""`)" and then
  lists **38** non-empty segments. Independent extraction finds 38 pre-existing first segments (46
  distinct total minus the 8 new 7.9 ones), i.e. 39 whole components including the root `""`. The
  disjointness conclusion itself is correct (verified above), but the count is the anchor of that
  proof and a false number in the frozen "verified ground truth" table weakens the audit trail — and
  a re-verification run that trusted "35" would flag three legitimate segments as suspicious.
  fix: correct §1 to "38 existing URL first segments (39 incl. `""`)" (or drop the numeral and keep
  the enumerated list, which is accurate).

- [M6] Contract's table/entity counts are internally inconsistent (§0 "six tables", §7 "four entities")
  file: `.claude/tasks/contract-projects-7.9.md`  lines: 9, 298, 561
  finding: §0 line 9 says "five entity files, **six tables**"; §3.6 line 298 says the migration
  "carries all six" and instructs "anything beyond the **six** tables in §3 means **STOP** and
  report"; §7 line 561 says "7.9 has **four entities**". The build ships **seven** models across
  **five** entity files (`Meetings.py` holds `Meeting` + its two children), and migration `0012`
  correctly creates seven — which matches the brief's own "exactly the seven models" expectation. The
  code is right and the §3 model list is right; the arithmetic in §0/§3.6/§7 is wrong, and §3.6's
  "STOP if beyond six" is actively misleading for a future re-verification (it would halt on the
  correct seven-model migration).
  fix: correct §0/§3.6 to "seven tables/models" and §7 to "five entities
  (`channel/`, `message/`, `documentshare/`, `meeting/`, `notification/`)".

- [M7] 7.9 introduces the repo's first three-level template nesting (`meeting/agendaitem/`, `meeting/actionitem/`)
  file: `templates/projects/collaboration/meeting/agendaitem/form.html`, `templates/projects/collaboration/meeting/actionitem/form.html`  lines: n/a (new directories)
  finding: these two are the **only** 5-component template directories in the entire repo
  (`find templates -type d | awk -F/ 'NF==5'` returns exactly these two; every other module stops at
  `templates/<app>/<submodule>/<entity>/`, 4 components). CLAUDE.md rule 2 pins "**Two** folder
  levels: sub-module → entity", and rule 5's child-entity example (`budget/line/form.html`) is 4
  components precisely because `budget` is a single-entity sub-module that doubles as the entity
  folder (rule 3). Here `collaboration` is a **multi-entity** sub-module, so `meeting/` is already
  the entity level and `meeting/agendaitem/` adds a third level the rule does not describe. Contract
  §7 explicitly authorises it ("child entities of the meeting folder"), so this is **not** an
  un-authorised deviation and the choice is defensible (the child genuinely belongs to `Meeting`) —
  but it is a new depth with zero precedent, and the next sub-module that copies it (or copies 7.8's
  two-level shape instead) forks the convention silently.
  fix: either flatten to `collaboration/agendaitem/form.html` + `collaboration/actionitem/form.html`
  (two levels, matching rule 5's literal "own folder under the sub-module"), or add one sentence to
  CLAUDE.md rule 5 recording that a child entity of a multi-entity sub-module nests under its parent
  entity (`sub-module/entity/child/`).

### Lane 3 — frontend-reviewer (serial pass 3)

**Scope check.** Read **all 17/17** templates under `templates/projects/collaboration/` in full
(including the two three-level child forms `meeting/agendaitem/form.html` and
`meeting/actionitem/form.html`), plus both in-scope edits — `templates/projects/overview.html`
(the 7.9 stat cards at `:47-50` and quick-link rows at `:251-274`) and
`templates/partials/pagination.html` as consumed by the five new list pages. Read for context:
`static/css/theme.css` (class-existence), `apps/core/crud.py` (the `filters` machinery the filter
bars drive), all six 7.9 view modules, `forms/CollaborationCommunication/{ChannelMessages,Meetings}.py`,
`views/ProjectInitiation/Overview.py:145-155`, and the 7.8 sibling
`templates/projects/taskwork/checklistitem/{list,detail}.html` for the house shape.
**Could not verify:** anything runtime — this is a static lane, so the smoke gate's 247/247, the 30
IDOR probes and the per-page query counts are taken as reported rather than re-executed; no
state-mutating command was run and no test was run. I did not duplicate Lanes 1–2; I independently
agree with all of their findings (I1, M1–M7) and found no basis to dispute any.

**Praise first.** The amendment-2 fix is exactly right and is the thing that most easily ships broken:
`channel/detail.html:48` carries `<input type="hidden" name="channel" value="{{ obj.pk }}">` **and**
a `{% comment %}` (`:44-47`) explaining *why* the field travels hidden rather than as a second
`<select>` that could disagree with the URL — and the composer renders `body` + `mentions` only, so no
duplicate `channel` widget is produced. Relatedly, all **25** `confirm('…')` literals across the nine
POSTing templates interpolate `obj.number`/`item.number` only — never a free-text title or name — so
none can break on an apostrophe (the L42 trap). That is careful work.

**Area verdicts (coverage — a clean area is a result):**

1. **Theme-class validity — CLEAN (0 findings).** Every one of the **67** distinct class tokens used
   across the 17 templates + `overview.html` is either defined in `theme.css` or defined page-locally.
   Mechanically checked: `comm -23` of the used-class set against `theme.css`'s selector set **plus**
   the page-local names is **empty**. `badge-*` is colour-named only (`green/red/amber/info/muted/slate`
   — no `-success/-danger/-warning` anywhere); every `stat-icon` variant used (`blue/green/orange/purple/
   red/slate`) exists as a compound selector; `stat-card`/`stat-value`/`stat-label` always sit inside a
   `stat-grid` wrapper (`activity_feed.html:48-74`, `meeting/detail.html:30-56`,
   `notification/list.html:20-26`, `overview.html:15-51`). The two documented page-local blocks are
   **self-contained and collide with nothing**: `collab-entry*` (`activity_feed.html:111-116`) and the
   `collab-thread/msg/reply*` family (`channel/detail.html:149-157`) each return **0** hits for every
   name in `theme.css`. (See M13 for the block §10.3 does not mention.)
2. **L-rule compliance — 2 findings (M8, M9), both the same badge-fallback rule.** L2 **clean**: no
   `{#` opens without closing `#}` on the same line anywhere in the 7.9 tree, and all 13 long notes
   use `{% comment %}…{% endcomment %}`. L9 **clean**: `partials/pagination.html` guards both
   `previous_page_number`/`next_page_number` behind `has_previous`/`has_next`, and preserves every GET
   param except `page` — the five new list pages just include it. L10 **clean**: all **22** `|default:`
   uses sit behind an `{% if %}` on the same value (`obj.archived_by`, `s.shared_with`,
   `thread.root.created_by`, `reply.created_by`, `obj.claimed_by`, `obj.revoked_by`, `obj.created_by`,
   `obj.minutes_by`, `item.presenter`, `item.assignee`, `obj.triggered_by`, `entry.actor`, and the
   non-nullable `recipient`/`u`/`document`); no nullable FK appears as a `default:` argument. The
   pinned "every badge ternary ends `{% else %}{{ obj.get_<field>_display }}{% endif %}`" rule is
   broken twice, both in the channel templates.
3. **Context-key completeness (L7/L8) — 2 findings (M10, M11); no blank-render bug.** Extracted every
   top-level name referenced by each template and diffed it against the contract §6 rows **and** the
   view code: every key a template reads is supplied, and every contract-pinned key is supplied except
   the two notes below. `threads`/`message_count`/`reply_count`/`message_form`/`shares` (chn_detail),
   `agenda_items`/`action_items`/`agenda_total`/`agenda_covered`/`open_action_count`/
   `overdue_action_count`/`agenda_form`/`action_form` (mtg_detail), `mine`/`unread_count`/`recipients`
   (ntf_list) and all 12 `activity_feed` keys are present with the pinned names. M10 is a pinned key
   that is **never rendered**; M11 is a key a template **does** read that the contract never pins.
4. **Filter-bar fidelity — CLEAN (0 findings).** All five registers + the feed reflect `request.GET`
   (`q` via `{{ q }}`; every FK `<select>` compared with `|stringformat:"d"` — `project`, `channel`,
   `author`, `recipient`; every enum compared as a string), and `is_archived`/`is_active`/`is_read` use
   the `"True"`/`"False"` strings `crud_list` maps at `apps/core/crud.py:147` — the mapping is real, not
   assumed. Every list region has an `{% empty %}` `.empty-state` (5 registers + the feed + all four
   detail-page panels), and every `colspan` matches its header count. `notification/list.html:31` and
   `:67` correctly carry the `?mine=1` lens through a filter submit and its Reset.
5. **Form-page correctness — CLEAN (0 findings).** All six form pages use the house
   `{% for field in form %}` render inside `.form-grid` with `{% csrf_token %}` and an `is_edit`
   heading switch; both child-entity forms and the two inline meeting panels POST without a `meeting`
   field because `MeetingAgendaItemForm`/`MeetingActionItemForm` genuinely exclude it
   (`forms/CollaborationCommunication/Meetings.py:58`, `:70`) and the view stamps it from the URL.
   **The amendment-2 hidden input is present and correct** (`channel/detail.html:48`), and I then walked
   **every** required field of all seven forms against every page that renders it: no other page or
   inline panel omits a required field. The channel composer is the only one that ever did, and it is
   fixed.
6. **Destructive-action safety — CLEAN (0 findings).** All 25 mutating controls are `<form method="post">`
   with `{% csrf_token %}` — none is a bare link — and every one carries
   `onsubmit="return confirm('…')"`. The confirm literal-in-a-comment trap is **absent**: a
   case-insensitive search for `confirm` across the 17 templates + `overview.html` returns **only**
   `onsubmit` attributes (`grep -rni confirm … | grep -v onsubmit=` → empty), there is no `onclick`
   anywhere, and there is no HTML comment in the tree at all — so no comment can match the repo's
   rendered-HTML scan (`apps/projects/tests/test_planning_security.py:187`, `:584`).
7. **Accessibility & polish — 3 findings (M12, M14, M15) plus M13.** Icon-only controls carry `title`
   (the house convention — 7.8's `checklistitem/list.html:58-64` does the same, so this is consistent,
   not a drift); every filter `<select>` and search `<input>` carries `aria-label`; every form field has
   a `<label for>` bound to `{{ field.id_for_label }}`; no duplicate element ids across the two forms
   co-rendered on `meeting/detail.html`; every container/inline tag balances (awk tag-balance pass over
   all 17 files is clean) and no `<td>` count varies per row (each list table is N headers / N body
   cells + 1 empty-state row). Remaining items are RTL, one ambiguous header, and one promised link.

**Findings.**

- [M8] The channel register's kind badge hardcodes its fallback label instead of `get_kind_display`
  file: `templates/projects/collaboration/channel/list.html`  lines: 57-58
  finding: the badge ternary ends `{% else %}<span class="badge badge-info">Discussion</span>{% endif %}`
  — a hardcoded label, not the model's display. Contract §7 (line 539) and CLAUDE.md's badge rule pin
  "every badge ternary ends `{% else %}{{ obj.get_<field>_display }}{% endif %}`", and the same page's
  sibling `channel/detail.html:26` gets it right (`{% else %}{{ obj.get_kind_display }}{% endif %}`), so
  the two pages disagree on the same field. Benign today because `KIND_CHOICES` has exactly two values —
  but a third kind, or a renamed one, silently mislabels as "Discussion" with no signal. (This is the
  *badge*; Lane 1's unfiled note about `:31-35` is the adjacent filter `<select>` — a different element.)
  fix: replace the else label with `{{ obj.get_kind_display }}`.

- [M9] The pinned-document panel's access badge hardcodes its fallback label
  file: `templates/projects/collaboration/channel/detail.html`  lines: 124-126
  finding: same rule, same defect — `{% else %}<span class="badge badge-muted">View only</span>{% endif %}`
  should read `{{ s.get_access_level_display }}`. Both other renderers of `access_level` do it correctly
  (`documentshare/list.html:67-69`, `documentshare/detail.html:41-43`), so the channel panel is the only
  inconsistent one. Currently correct by coincidence (`ACCESS_CHOICES` has three values and the else *is*
  `view`), so this is latent drift, not a wrong label today.
  fix: `{% else %}<span class="badge badge-muted">{{ s.get_access_level_display }}</span>{% endif %}`.

- [M10] `minutes_form` is pinned by the contract and built by the view but never rendered
  file: `templates/projects/collaboration/meeting/detail.html`  lines: 140-155
  finding: contract §6.4 pins `minutes_form` on `mtg_detail`, and §7 (line 552) describes the detail
  page's minutes panel as "(`minutes_form` POSTing to `mtg_minutes`, `minutes_by`/`minutes_at` stamps)".
  `apps/projects/views/CollaborationCommunication/Meetings.py:103` still constructs
  `MeetingMinutesForm(initial={"minutes": obj.minutes})`, but the template renders a read-only panel
  plus a link to `meeting/minutes.html` — `minutes_form` appears nowhere in the rendered page. So a
  contract-pinned key is dead on **every** detail render (one wasted `MeetingMinutesForm` build per
  request), and §7's described shape does not match the built page. Not user-visible — the dedicated
  `mtg_minutes` page is linked and works — so this is Minor, but triage must consciously resolve it:
  either §7 is wrong or the panel is incomplete.
  fix: either render it inline (`<form method="post" action="{% url 'projects:mtg_minutes' obj.pk %}">`
  around `{{ minutes_form.minutes }}` + `{% csrf_token %}`), or drop `minutes_form` from `mtg_detail`'s
  context and amend §6.4/§7 to say the panel links out to `mtg_minutes`.

- [M11] The two child-entity edit pages read a `meeting` key the contract never pins for them
  file: `templates/projects/collaboration/meeting/agendaitem/form.html`, `templates/projects/collaboration/meeting/actionitem/form.html`  lines: 6-7 (both)
  finding: both templates use `{{ meeting.number }}`, `{{ meeting.title }}`, `{{ meeting.scheduled_start }}`
  and `{% url 'projects:mtg_detail' meeting.pk %}` **unconditionally**, including on the edit path.
  Contract §6.4 pins `agi_edit`/`mai_edit` context as `form`, `obj`, `is_edit=True` **only** — no
  `meeting` (the *create* rows are pinned with it). The code does supply it
  (`Meetings.py:242` and `:317` pass `"meeting": obj.meeting`), so there is no blank and no
  `NoReverseMatch` today — but this is precisely the L7/L8 shape: a template key that the contract does
  not pin is one refactor away from a 500 on a mainline edit page, and a contract-only re-verification
  would flag it as drift. Lane 1's contract-vs-code sweep could not catch this because it checks
  contract → code, not code/template → contract.
  fix: add `meeting` to the `agi_edit`/`mai_edit` context rows in contract §6.4 (and, cheaply, a one-line
  comment in each view recording that the breadcrumb needs it).

- [M12] Reply indentation in the channel page-local CSS hard-codes left, breaking RTL
  file: `templates/projects/collaboration/channel/detail.html`  lines: 153, 156
  finding: `.collab-reply { margin-left: 2rem; border-left: 2px solid var(--border); padding-left: 0.75rem; }`
  and `.collab-reply-form { margin-left: 2rem; }` use physical left properties, so under
  `html[dir="rtl"]` the reply gutter and its rule stay on the left while the conversation flows right —
  the indentation then reads as an outdent. The repo does support RTL (`theme.css:157-158`, `:427`) and
  its own nested-indentation component uses logical properties for exactly this case
  (`theme.css:346-347` — `.tree-children` uses `margin-inline-start` / `padding-inline-start` /
  `border-inline-start`), so the house idiom exists and 7.9 diverges from it. The block is otherwise
  self-contained and collides with nothing (verified).
  fix: `margin-inline-start: 2rem;` / `border-inline-start: 2px solid var(--border);`
  `padding-inline-start: .75rem;` — or promote the block into `theme.css` beside `.tree-children` and
  reuse the logical form.

- [M13] Three page-local `collab-` blocks duplicate one row style; contract §10.3 says there is only one
  file: `templates/projects/collaboration/channel/detail.html`, `templates/projects/collaboration/activity_feed.html`, `templates/projects/collaboration/meeting/detail.html`  lines: 149-157, 111-116, 220-222
  finding: contract §10 amendment 3 states the page-local rules are "contained to that one page"
  (`channel/detail.html`). Three pages actually carry one: `collab-entry*` (`activity_feed.html`),
  the `collab-thread`/`collab-msg`/`collab-reply*` family (`channel/detail.html`) and `collab-minutes`
  (`meeting/detail.html`). The first two are near-duplicate "divider + flex head + body" rules that
  differ only in class name, which is the ad-hoc styling the persona's design-system check asks to fold
  into a theme component. Nothing is broken today — every `collab-*` name returns 0 hits in `theme.css`
  (verified) — so this is a maintenance/documentation finding, not a rendering bug, and it also means
  the "promote when a second page needs it" trigger §10.3 sets has already fired.
  fix: promote the shared divider/flex-head/body rules into `theme.css` as one component (e.g.
  `.thread-row` + `.thread-row-head` / `.thread-row-body`) and use it on all three pages; at minimum,
  correct §10.3 to name all three pages so the next sub-module copies the real convention.

- [M14] The agenda table's `Minutes` header labels a duration column on a page that also has a `Minutes` panel
  file: `templates/projects/collaboration/meeting/detail.html`  lines: 92, 99
  finding: the agenda table's fourth `<th>` reads "Minutes" while its cell renders
  `{{ item.duration_minutes }}` — a duration in minutes, not the meeting's minutes. The same page has a
  "Minutes" card (`:140-155`) that holds the actual minutes, so one word labels two different concepts
  on one screen; a reader scanning the table (or a screen-reader announcing column headers) has nothing
  to disambiguate them. The `<td>`/`<th>` counts are otherwise correct (6/6).
  fix: rename the header to state its subject and unit, e.g. `<th>Duration (min)</th>`.

- [M15] §7 promises four guarded deep-links on the notification detail page; only three are links
  file: `templates/projects/collaboration/notification/detail.html`  lines: 43-48 (specifically 45)
  finding: contract §7 (line 558) specifies "the four source deep-links (`channel`/`message`/`task`/
  `meeting`, each `{% if %}`-guarded)". All four are correctly `{% if %}`-guarded (L10-safe), but
  `message` renders as **plain text** (`{{ obj.message.number }} — {{ obj.message.body|truncatechars:60 }}`)
  with no `<a>`. That is forced by the route table: §5 ships no `msg_detail`, and the only message route
  is `msg_edit`, which is a poor deep-link target. So the contract's "four deep-links" is not buildable
  as written — the build made the right call and the contract needs the amendment.
  fix: amend §7 to "three deep-links (`channel`/`task`/`meeting`) plus a guarded text reference to the
  source message", or add a read-only message view in a later pass and link it.

### Lane 4 — performance-reviewer (serial pass 4)

**Scope check.** Read in full: the six 7.9 view modules (`Channels.py`, `ChannelMessages.py`,
`DocumentShares.py`, `Meetings.py`, `ProjectNotifications.py`, `ActivityFeed.py`), all five 7.9 model
files, `views/ProjectInitiation/Overview.py`, the `_collab` block of `seed_projects.py` (incl. its
`--flush` ordering at `:261-267` and its call site at `:370`), migration `0012`, and all **17** templates
under `templates/projects/collaboration/` plus the 7.9 cards/rows in `templates/projects/overview.html`.
Read for context: `apps/core/crud.py` (`crud_list`/`crud_detail`/`paginate`), `apps/projects/models/_base.py`,
`views/_helpers.py`, `apps/accounts/models.py` (`User.__str__`), `apps/core/models/Document.py`,
`apps/projects/models/TaskWorkManagement/TaskBlocks.py` (the 7.8 sibling), and the installed Django source
(`venv/Lib/site-packages/django/db/models/base.py:1387-1423`, `db/models/fields/related.py:1074-1096`) to
confirm what `full_clean()` actually costs. I did not duplicate Lanes 1–3 and I **independently agree with
every one of their findings** (I1, M1–M15) — no basis to dispute any. I re-verified Lane 1's `ntf_list`
`select_related("message")` gap myself (it is real) but did **not** re-file it; see the area-5 verdict.
**Could not verify:** anything runtime. This is a read-only lane — no query count was measured with
`django_assert_max_num_queries`, no page was rendered, and no test was run. Every cost below is derived
from the ORM→SQL shape and (where a Django internal decides the count) from the source read cited inline,
not from a profiler. Two notes outside my eight areas, offered for triage rather than filed:
(a) `_collab`'s docstring says "17 messages" and §8.3 of the contract requires **≥16** so `msg_list`
reaches page 2, but the block creates **13** (`seed_projects.py:2092-2119`; the enumerated description in
its own docstring sums to 13) — with `per_page=15` the register never reaches a real page 2, and
`Paginator.get_page(2)` on a 13-row set silently returns page 1, so the smoke gate's "walks page 2" would
pass without exercising anything. That is a data-coverage gap, not a query-count one, so it is outside
this lane's remit — Lane 1/5 territory. (b) A few `select_related` entries are never dereferenced
(`msg_list`'s `"parent"`, `chn_detail`'s `"parent"`, `dsh_list`'s `"claimed_by"`, `msg_list`'s
`"channel__project"` is used but `channels`' own `select_related("project")` is not) — each is one extra
LEFT JOIN per row, contract-pinned, and not worth a finding.

**Area verdicts (an area with no findings is a result — coverage is explicit):**

1. **The `.count()`-as-a-property trap — CLEAN (0 findings).** No 7.9 model ships a property that calls
   `.filter()`/`.count()`/`.all()`. Every derived property is pure-Python over already-loaded state
   (`Channel.is_open`, `ChannelMessage.is_reply`/`is_edited`, `DocumentShare.is_revoked`/`is_claimed`/
   `is_co_editable`, `Meeting.is_upcoming`/`is_past`, `MeetingActionItem.is_overdue`,
   `ProjectNotification.is_unread`). Critically, I checked the **shadowing** direction the brief asks for:
   `Channel` has **no** `message_count`, `ChannelMessage` has **no** `reply_count`, and `Meeting` has
   **no** `agenda_total`/`agenda_covered`/`open_actions` — so the three annotated names are unambiguous and
   a template `{{ obj.message_count }}` resolves to the annotation, never to a re-query. Template side:
   `grep -nE '\.count|\.all\b|\.filter\b' templates/projects/collaboration/` returns **no matches**, and
   `overview.html`'s 7.9 region (`:47-50`, `:251-274`) is pure `{{ key }}` interpolation — no related
   manager is touched inside a `{% for %}` anywhere in the 7.9 tree.
2. **`distinct=True` on the multi-join `Count`s — CLEAN (0 findings).** `mtg_list`
   (`Meetings.py:43-48`) annotates three `Count`s over two reverse relations and **all three** carry
   `distinct=True` (`:44`, `:46`, `:48`). The two single-join annotations that legitimately do not need it
   also do not have it, which is correct: `chn_list`'s `Count("messages")` (`Channels.py:35`) and
   `msg_list`'s `Count("replies")` (`ChannelMessages.py:37`) each traverse exactly one reverse relation, so
   there is no second join to multiply by and no filter that could add one.
3. **Detail-view single-materialization — CLEAN (0 findings).** `chn_detail` builds the whole thread tree
   from **ONE** materialized list (`Channels.py:53-60`) and derives `message_count`/`reply_count` from that
   same list (`:64-65`) — no `obj.messages.filter(parent=…)` anywhere, i.e. the 7.8 `tsk_detail` 31→13
   lesson is applied, not just cited. `mtg_detail` materializes `agenda_items` and `action_items` exactly
   once each (`Meetings.py:93-94`) and computes all four figures in Python over those lists (`:99-102`).
   Total detail cost is a flat 1 + 1 + 1 (+ 1 for `shares`/forms) regardless of thread or agenda size.
4. **`Prefetch` vs chained `select_related` — CLEAN (0 findings, vacuously).** `grep -n Prefetch
   apps/projects/views/CollaborationCommunication/` returns nothing — 7.9 uses no `Prefetch` object at all,
   so there is no `Prefetch("a__b")` to collapse. The five chained dereferences it does need are all
   already written in the one-query chained form: `msg_list` `"channel__project"` (`ChannelMessages.py:36`),
   `ActivityFeed.py:94` `"channel__project"`, and the `"meeting__project"` chains in `admin.py`.
5. **`select_related` completeness — 1 finding, already filed by Lane 1; I confirm it and found no
   others.** I walked every FK dereference in all 17 templates (and the 7.9 `overview.html` region) against
   its view's `select_related`/`prefetch_related`. Exactly **one** gap exists: `ntf_list`
   (`ProjectNotifications.py:30`) omits `"message"` while `notification/list.html:86` renders
   `obj.message.number` — I independently confirm Lane 1's **M1** (worst case 15 extra queries per page of
   the inbox) and I agree the *template* is the drift, since §6.5 pins that tuple. **No other gap**: the
   five other list views, all four detail views and the feed are complete (`ntf_detail`'s 8-way tuple even
   carries `message`). I also checked the chained-`__str__` variant of this class (L18): every related model
   the templates render has a column-only `__str__` (`User.__str__` → `self.email`,
   `apps/accounts/models.py:82`; `Project.__str__` → `f"{number} — {name}"`, `Projects.py:122`;
   `Channel`/`Meeting`/`DocumentShare`/`ProjectNotification` likewise), so no `select_related` needs a
   second hop. No new filing.
6. **`activity_feed`'s five capped source queries — CLEAN (0 findings).** All five caps are real database
   `LIMIT`s, not Python slices: each source is `qs.select_related(…).order_by(…)[:_SOURCE_CAP]`
   (`ActivityFeed.py:95, 111, 126, 141, 155`) applied to an **unevaluated** queryset, so the slice compiles
   to `LIMIT 100`; nothing materializes the full table first. The `counts` are exact pre-cap `COUNT`s
   (`:93, 109, 124, 139, 154`), the merge/sort happens in Python over at most 5 × 100 = 500 dicts
   (`:163`), and `_FEED_CAP` truncates that list (`:165`). Per-source `select_related` is complete for the
   fields the entry dicts read (`row.channel.project` via `channel__project`, `row.document`,
   `row.recipient`, `row.user`). Fixed cost ≈ 12 queries per render (1 project lookup + 1 project
   dropdown + 5 counts + 5 selects) **independent of tenant history size** — which is the whole point of
   the caps and is achieved.
7. **`ntf_mark_all_read` — 1 finding (M16).** The contract's "one audit row for the bulk" is honoured
   (`ProjectNotifications.py:108-109`) and the queryset is correctly scoped to the caller
   (`:97-98`). The per-row `save()` is **not** an oversight: its stated reason is real —
   `updated_at` is `auto_now` (`_base.py:48`) and `queryset.update()` does not fire `auto_now`, so a naive
   bulk update would leave `updated_at` stale. But that reason is fully satisfiable inside a single
   `UPDATE`, so the honest verdict is "defensible, but N statements where 1 will do" — filed Minor below.
8. **Index coverage — 3 findings (I2, M17, M18).** First the good news, verified: **all 18 declared
   indexes have `tenant` as their first column** (the always-applied filter), and each of the 13 that map
   to a real access path does so — `chn_tnt_project_idx`/`chn_tnt_archived_idx` ← `chn_list`'s two facets,
   `chm_tnt_channel_idx`/`chm_tnt_parent_idx` ← `msg_list`'s two int-FK lenses plus its leading sort key,
   `dsh_tnt_project_idx`/`dsh_tnt_active_idx` ← `dsh_list`, `mtg_tnt_project_idx`/`mtg_tnt_status_idx`/
   `mtg_tnt_start_idx` ← `mtg_list`'s filters and its `-scheduled_start` ordering,
   `mait_tnt_done_idx` ← `Overview.py:150-151`, `ntf_tnt_recipient_idx` ← `?mine=1` **and**
   `Overview.py:152-153` (the `(tenant, recipient, is_read)` order is exactly the inbox's query),
   `ntf_tnt_kind_idx`/`ntf_tnt_project_idx` ← `ntf_list`'s facets. The gaps are below: a hot
   filter+order path with **no** index on any of the four feed models (I2), a facet whose composite cannot
   serve it (M17), and five declared indexes no 7.9 query can use (M18).

**Extra area (9) — write paths, reviewed because `_notify_mentions` and the seeder are in scope: 2
findings (I3, M19).** The `--flush` path is **correct and verified**: `seed_projects.py:261-267` deletes
children-first (`ProjectNotification` → `MeetingActionItem` → `MeetingAgendaItem` → `DocumentShare` →
`ChannelMessage` → `Meeting` → `Channel`), i.e. every FK to a not-yet-deleted parent is cleared first, and
`_collab` is called after `_taskwork` (`:370`) with its own per-tenant guard (`:1989-1992`). What is *not*
free is the per-row `full_clean()` both paths use.

**Findings.**

- [I2] The activity feed and two 7.9 registers filter/order on `created_at`, which no 7.9 model indexes
  file: `apps/projects/models/CollaborationCommunication/DocumentShares.py`, `.../ProjectNotifications.py`, `.../ChannelMessages.py`, `.../Meetings.py`  lines: 73-79 / 79-87 / 52-57 / 88-92 (models); `apps/projects/views/CollaborationCommunication/ActivityFeed.py` 90, 106, 121, 136, 153
  finding: `activity_feed` runs `Model.objects.filter(tenant=tenant, created_at__gte=since)
  .order_by("-created_at", "-id")[:100]` against **four** models, and **not one** of them has an index
  whose leading columns are `(tenant, created_at)`: `ChannelMessage` declares `(tenant, channel)` and
  `(tenant, parent)`; `Meeting` `(tenant, project)`, `(tenant, status)`, `(tenant, scheduled_start)`;
  `DocumentShare` `(tenant, project)`, `(tenant, is_active)`, `(tenant, document)`; `ProjectNotification`
  `(tenant, recipient, is_read)`, `(tenant, kind)`, `(tenant, project)`. The only usable index is the
  single-column FK index on `tenant_id`, so each of the four feed sources is a tenant-wide range filter
  **plus a filesort of the whole tenant's rows** before the `LIMIT 100` can be satisfied — the `LIMIT` caps
  the transfer, not the work, which is the one thing that would have made §6.7's "ten queries however much
  history" claim hold. The same missing index costs `dsh_list` and `ntf_list` a filesort on **every** page
  render, because both declare `Meta.ordering = ["-created_at", "-id"]` (`DocumentShares.py:73`,
  `ProjectNotifications.py:79`) with no covering index. This is not a novel demand: it is the
  projects-module's own established pattern — `prj_tnt_created_idx`, `prq_tnt_created_idx`,
  `pko_tnt_created_idx`, `pst_tnt_created_idx`, `rsk_tnt_created_idx`, `iss_tnt_created_idx`,
  `rra_tnt_created_idx`, `req_tnt_created_idx`, `qpl_tnt_created_idx`, `qdf_tnt_created_idx` all exist, and
  `ProjectStakeholders.py:117` and `Projects.py:118` say so in a comment: *"in-pattern add: ["tenant",
  "created_at"] already ships on 20+ models app-wide."* 7.9 (and, it should be said, 7.8's `TaskBlock`,
  which shares the `["-created_at", "-id"]` ordering and the omission) skipped it.
  fix: add `models.Index(fields=["tenant", "-created_at"], name="chm_tnt_created_idx")` to
  `ChannelMessage`, `dsh_tnt_created_idx` to `DocumentShare`, `ntf_tnt_created_idx` to
  `ProjectNotification`, and `mtg_tnt_created_idx` to `Meeting` (the feed orders all four by `-created_at`
  even though `Meeting.Meta.ordering` is `-scheduled_start`), in one `0013` migration. `DocumentShare` and
  `ProjectNotification` are the two that must not be skipped — they are register orderings, not just feed
  paths.

- [I3] `_notify_mentions` runs a full `full_clean()` per notification row — 7 existence SELECTs per mention
  file: `apps/projects/views/CollaborationCommunication/ChannelMessages.py`  lines: 137-155 (specifically 152)
  finding: the fan-out loop does `row.full_clean(exclude=["number"]); row.save()` per recipient. The
  per-row `save()` is contract-pinned and justified (`TenantNumbered.save()` is what mints `NTF-#####`,
  §10.1), but `full_clean()` is not required by that argument and is expensive: `clean_fields()` calls
  `ForeignKey.validate()` on every non-null FK, and that method issues one `qs.exists()` per FK
  (`venv/Lib/site-packages/django/db/models/fields/related.py:1074-1096`, verified). A minted
  `ProjectNotification` has **seven** non-null FKs (`tenant`, `project`, `recipient`, `channel`, `message`,
  `triggered_by`, `created_by`), so each row costs **7 SELECTs + 1 INSERT + 1 `next_number()` SELECT ≈ 9
  queries** instead of 2. `unique_together ("tenant", "number")` is correctly skipped by
  `exclude=["number"]` (`django/db/models/base.py:1413-1417`, verified), so the count is entirely FK
  existence checks — and `ProjectNotification` has no `clean()` (contract §3.5), so `full_clean()` buys
  **no model rule at all** here: the values are all objects already fetched and validated by the form. The
  fan-out size is user-controlled (the `mentions` multi-select is an unbounded
  `ModelMultipleChoiceField` over every user in the tenant, and a crafted POST may name all of them), so
  one message POST can be turned into ~9N queries — 50 mentions ≈ 450 queries on a single request.
  `msg_edit` pays the same cost through the same helper (`:96`).
  fix: drop the `full_clean()` and keep the per-row `save()` — that preserves §10.1's number-minting
  requirement exactly and removes 7 queries per row. If the FK existence guard is wanted, assert it once
  against the form's already-validated `channel`/`mentions` rather than once per row per FK. This
  deliberately contradicts §6.6's pinned `row.full_clean(exclude=["number"]); row.save()`: the contract's
  own §10.1 rationale covers the `save()`, not the `full_clean()`.

- [M16] `ntf_mark_all_read` issues one UPDATE per unread row where a single UPDATE would do
  file: `apps/projects/views/CollaborationCommunication/ProjectNotifications.py`  lines: 97-109 (specifically 103-106)
  finding: `rows = list(…)` (1 SELECT) then `for row in rows: … row.save(update_fields=[…])` — **N UPDATE
  statements** for a bulk verb, on top of the pinned single audit row. The docstring's justification
  ("`auto_now` fires only on `save()`, so a bulk update would leave every `updated_at` stale") is
  **factually correct** — `queryset.update()` bypasses `auto_now` — so this is not a bug, and I do not
  disagree with the trade as written. But the reason is satisfiable in one statement, so the honest verdict
  is "defensible, not necessary": the same single audit row is still written, the same `read_at` value is
  still stamped, and the only thing lost is nothing. Cost is 1 + N queries; an inbox with 200 unread rows
  (a plausible return-from-leave state) is 201 round trips for one button.
  fix: `ProjectNotification.objects.filter(tenant=request.tenant, recipient=request.user,
  is_read=False).update(is_read=True, read_at=now, updated_at=now)` — one UPDATE, `updated_at` explicitly
  stamped (so the docstring's concern is met head-on rather than side-stepped), then keep the single
  `write_audit_log` and the `messages.success` count. Note the count must be captured before the update.

- [M17] `ntf_list`'s workspace-wide `?is_read=` facet cannot use `ntf_tnt_recipient_idx`
  file: `apps/projects/views/CollaborationCommunication/ProjectNotifications.py`  lines: 29-40; `apps/projects/models/CollaborationCommunication/ProjectNotifications.py`  lines: 81-87
  finding: `ntf_tnt_recipient_idx` is `(tenant, recipient, is_read)`, so it can only serve a query that
  constrains `recipient`. The register's `("is_read", "is_read", False)` filter (`:40`) applied **without**
  `?mine=1` is `filter(tenant=X, is_read=False)` — no `recipient` predicate — so MariaDB can use the index
  for the `tenant` prefix only and then filters `is_read` per row: effectively a tenant-wide scan. That is
  a natural filter for this register ("show me everything unread") and it is the one facet of the four
  whose index does not cover it (`?project=`/`?kind=` are covered by `ntf_tnt_project_idx`/`ntf_tnt_kind_idx`;
  `?recipient=` and `?mine=1` are covered). Graded Minor because the *hot* lens is `?mine=1` and that one is
  perfectly indexed, and because the `unread_count` stat card (`:46-47`) shares the same covering index.
  fix: add `models.Index(fields=["tenant", "is_read"], name="ntf_tnt_read_idx")` in the same `0013` as I2
  (one extra index on the fastest-growing 7.9 table), or leave it and record in §3.5 that the
  workspace-wide read facet is intentionally unindexed.

- [M18] Five of the eighteen declared indexes match no access path in any 7.9 view
  file: `apps/projects/models/CollaborationCommunication/DocumentShares.py`, `.../Meetings.py`  lines: 78; 144-145, 199-201
  finding: `dsh_tnt_document_idx` (no 7.9 view filters `document`; `dsh_list`'s `document__name` search is
  an `icontains` on the *joined* `core_document`, which a `(tenant, document)` index cannot serve);
  `agi_tnt_meeting_idx` and `agi_tnt_is_covered` (`mtg_detail` reads `obj.agenda_items`, i.e.
  `filter(meeting_id=…)` with **no** `tenant` predicate, so the FK's own single-column index is what
  serves it, and nothing filters `is_covered` — `agi_cover` is per-pk); `mait_tnt_meeting_idx` (same
  shape) and `mait_tnt_assignee_idx` (there is no `mai_list` and no assignee filter anywhere). Each is
  pure write-path cost — an extra B-tree maintained on every INSERT/UPDATE — with no read to offset it in
  this sub-module. These are the house `(tenant, <dimension>)` idiom and are contract-pinned (§3.3/§3.4),
  so they are forward-looking rather than wrong (a tenant-scoped child register, or the admin's
  `list_select_related`, would want them); graded Minor so triage can consciously keep them.
  fix: either keep them and record in the contract that they are reserved for a later tenant-scoped child
  listing, or drop `dsh_tnt_document_idx` / `mait_tnt_assignee_idx` and the two `(tenant, meeting)` child
  indexes. Do **not** drop `mait_tnt_done_idx` — `Overview.py:150-151` uses it.

- [M19] `_collab`'s per-row `full_clean()` costs ~5-7 existence SELECTs per seeded row (app-wide idiom)
  file: `apps/projects/management/commands/seed_projects.py`  lines: 2005-2081 (specifically 2012, 2022, 2044, 2055, 2068, 2079)
  finding: every row in the block goes through `full_clean(exclude=["number"]); save()`. By construction
  (same Django path as I3) each call issues one `.exists()` per non-null FK — `channel()` 3,
  `message()` 3-4, `meeting()` 3-4, the agenda items ~4, the action items ~4-5, `notify()` 5-6 (it passes
  up to eight FK kwargs) — so the ~59 rows cost roughly **250-280 existence SELECTs** out of the block's
  ~380-410 queries, the rest being the ~59 `next_number()` lookups (1 per `TenantNumbered.save()`, pinned
  by §10.1) and the ~59 INSERTs. `_collab` runs once per tenant, so this is not a request-path cost — but
  the persona treats seeders as a hot path, and the FK checks are the majority of the block's queries for
  no semantic gain (`ProjectNotification` and `Channel` have no `clean()`, and every FK value is a row the
  block itself just fetched). **This is the repo-wide seeder idiom, not a 7.9 fork** — `_taskwork`
  (`:1960-1961`), `_risk`, `_scope` all do the same — so the fix belongs in an app-wide seeder pass, and I
  am filing it only because the brief put the seeder's query count in scope.
  fix: drop `full_clean()` on the 7.9 rows whose FKs are all already-materialized objects (keep it on
  `Channel`, the one model with a `unique_together` the `number` exclusion does not skip:
  `("tenant", "project", "name")`), and/or hoist the block's writes into `bulk_create` per model. Note
  `bulk_create` cannot replace the per-row `save()` for the numbered models (§10.1) — the FK-check removal
  is the part that is free.

**Disagreements with Lanes 1–3: none.** I re-derived Lane 1's M1 independently (confirmed, not re-filed)
and agree with its attribution of the drift to the template rather than the view. I agree with Lane 1's
unfiled note that `channel/list.html:31-35` hardcodes `KIND_CHOICES` — I will add one performance-adjacent
observation on it: because §6.1 passes no `kind_choices` key, the view builds no extra queryset for it, so
that hardcoding is the *cheaper* option today and fixing M8/the filter bar will not add a query.

**Recommended query-count assertions (hand to the test-writer).** These are the figures I would pin, all
derived above rather than measured: `chn_detail` ≤ 4 queries (channel + messages + shares + form selects)
**independent of thread count**; `mtg_detail` ≤ 8 **independent of agenda/action count**; `activity_feed`
≤ 14 **independent of tenant history size** (the cap proof); `dsh_list`/`ntf_list`/`mtg_list`/`chn_list`
≤ 6 + the filter dropdowns; and `msg_create` with a 3-person mention ≤ 12 (which fails at ~28 today —
that is I3).

### Lane 5 — qa-smoke-tester (serial pass 5, report-only)

**Reproduced.** `cd /c/xampp/htdocs/NavERP && venv/Scripts/python.exe temp/smoke_79.py`

```
PASSED 276   FAILED 0
```

Re-run three times from a pristine seed (`manage.py seed_projects --flush` first each time) — **276/276
every time, no deviation from the reported figure.** The DB was left re-seeded to its pristine 7.9 shape
(`chn=3 chm=18 dsh=4 mtg=4 agi=8 mai=7 ntf=18` per tenant) after the probes.

**Adversarial probes written (all under `temp/`, gitignored).** `probe_lane5.py` (uncovered POST paths,
verb repetition, `?page=` edges, junk-every-param, empty tenant, tenant-less guards, derived figures,
feed window/cap), `probe_lane5b.py` (positive-value filter correctness, second-user verbs, correct window
assertion), `probe_lane5c.py` (exact HTML evidence for the false-pass assertions + the `distinct=True`
value proof), `probe_lane5d.py` (live repro of Lane 1's I1), `probe_lane5e.py` (audit-verb coverage),
`probe_counts.py` (row counters).

**Bottom line: I found NO functional defect in the build.** Every probe of the shipped code came back
correct. My findings are all about the **smoke harness's coverage and its false-pass assertions** — which
is the gate the whole review leans on.

#### Route coverage — which of the 41 the harness actually exercises

The harness references all **41** route names, but the *manner* is thin. Coverage of the 41:

| Route group | Smoke coverage | Verdict |
|---|---|---|
| 13 GET pages/registers (`*_list`, `*_detail`, `*_create`, `*_edit`, `*_minutes`, `activity_feed`, `overview`) | GET 200 + (for 14 of 32 GET labels) a substring | content assertion on **14 of 32**; the other 18 pass `needle=None` and assert only "no comment leak" |
| 18 POST-only verbs | GET → **405** | method guard only — never a successful POST (except the 6 toggles/lifecycle exercised below) |
| 18 create/edit/delete routes | GET 200 **or** cross-tenant IDOR POST → 404 | **never POSTed successfully** (see I5) |
| `mtg_start`/`mtg_complete`/`mtg_minutes`/`agi_cover`/`mai_toggle`/`dsh_claim`/`dsh_release`/`dsh_revoke`/`ntf_mark_read`/`ntf_mark_all_read`/`chn_archive`/`msg_edit` | POST with state assertions | genuine success-path coverage |
| `mtg_cancel` | POST **only on an already-`completed` meeting** (the refusal) | the success edge is never executed |
| `?page=2` | asserted with `num_pages > 1` + disjoint rows | genuine (the C-C strengthening holds — I re-confirmed no `UnorderedObjectListWarning` on `chn_list`/`msg_list`/`mtg_list`) |
| junk params | 36 combinations, all 200 | genuine |
| cross-tenant IDOR | 30 probes → 404 | genuine |

**Positive-value filters are never tested on any register.** The `JUNK` list (lines 202-218) contains only
*junk* (`nope`, `abc`, `²`, `0`, `9999`) plus `?mine=1`; no register is ever hit with a valid
`?kind=announcement` / `?status=completed` / `?access_level=view` / `?is_read=True` / `?channel=<pk>`. I
exercised all 37 positive lenses myself (`probe_lane5b.py` §I) and **every one returns the exact DB count**
— but a mis-wired `filters` tuple would render 200 and pass the smoke silently.

#### Findings

- [I4] The harness's only `mtg_list` annotation check is a false-pass; the `distinct=True` guard it nominally protects is load-bearing and asserted nowhere
  file: `temp/smoke_79.py`  lines: 576-580
  finding: `check("mtg_list renders each meeting once", b.count("MTG-") >= n_meetings)`. With the pristine
  seed the rendered page contains **8** `MTG-` tokens for **4** meetings, because each number is rendered
  twice — the link cell (`templates/projects/collaboration/meeting/list.html:63`) and the delete
  `confirm()` literal (`:79`) — so `>=` is satisfied with a 2× margin. The property `distinct=True`
  actually protects is the annotation **value**, not the row count: `probe_lane5c.py` §6 prints
  ```
  WITH    distinct=True : {'MTG-00001': (3, 3, 5), 'MTG-00002': (3, 0, 0), ...}
  WITHOUT distinct=True : {'MTG-00001': (18, 18, 15), 'MTG-00002': (3, 0, 0), ...}
  differ: True
  smoke check is: b.count('MTG-') >= n_meetings  ->  8 >= 4
  ```
  Dropping `distinct=True` (the exact regression contract §6.4 calls mandatory) renders **18/18/15** where
  it should render **3/3/5**, the result-row count stays 4, the token count stays 8, and the assertion
  still passes. The smoke never reads `agenda_total`/`agenda_covered`/`open_actions` anywhere.
  fix: assert the values — for each `m` in `page_obj.object_list`, `m.agenda_total == m.agenda_items.count()`,
  `m.agenda_covered == m.agenda_items.filter(is_covered=True).count()`,
  `m.open_actions == m.action_items.filter(is_done=False).count()` — and replace `>=` with an exact
  per-number count (`== 2 * n_meetings` for the link+confirm pair, or count only the table cell).

- [I5] 18 of the 41 routes are never POSTed successfully; the header's "renders all 41 routes with CONTENT assertions" overstates the coverage
  file: `temp/smoke_79.py`  lines: 119-152 (GETS), 177-199 (VERBS), 294-325 (IDOR)
  finding: every create/edit/delete route is reached only by GET (200) or by the cross-tenant IDOR POST
  (404). The success paths never run: `chn_create`/`chn_edit`/`chn_delete`, `dsh_create`/`dsh_edit`/
  `dsh_delete`, `mtg_create`/`mtg_edit`/`mtg_delete`, `agi_create`/`agi_edit`/`agi_delete`,
  `mai_create`/`mai_edit`/`mai_delete`, `msg_delete`, `ntf_delete` — **17 routes** — plus `mtg_cancel`'s
  success edge. `probe_lane5.py` §A drives all 18 and every one returns **302 with the correct DB effect**
  (`[A1]…[A18]`, e.g. `chn_create POST -> 302 created=True`, `dsh_delete POST -> 302 gone=True`), so no
  bug is hiding today. But the C-B class of defect — `save_m2m()` after a committing `save()` — lives in
  exactly these uncovered edit paths, and a regression there leaves the gate green. Also, 18 of the 32 GET
  checks pass `needle=None`, so the header's "with CONTENT assertions" applies to only 14.
  fix: add one create → edit → delete round-trip per entity (and a successful `mtg_cancel`) to the smoke.

- [I6] Four more assertions of the false-pass shape survive in the harness
  file: `temp/smoke_79.py`  lines: 167-168, 170-174, 147, 120
  finding: the C-C/C-D strengthening fixed the page-2 checks but left these four, each satisfied by a token
  that is present whether or not the page did its job (`probe_lane5c.py` §1-5):
  - `:167-168` `check("feed excludes audit when project set", "Audit entries" in body(...))` — `"Audit entries"`
    is the static stat-card **label** and prints `True` on the **unfiltered** page too; the assertion never
    reads `counts["audit"]` (which is `0` and correct). It passes whether or not audit rows are excluded.
  - `:171-172` `check("ntf_list shows unread stat", "Unread" in b or "unread" in b)` — `"Unread"` is a static
    filter `<option>` (`<option> values containing 'nread': ['Unread']`), present regardless of the stat card.
  - `:173-174` `check("mine=1 renders", "NTF-" in b or "Nothing" in b or "No notifications" in b)` — `"NTF-"`
    prints with `?mine=1`, with `?mine=0`, **and** with `?mine=garbage`; it cannot tell the lens applied from
    the lens being ignored.
  - `:147`/`:120` `("activity_feed", …, "Activity Feed")` and `("overview", …, "Activity Feed")` — `"Activity Feed"`
    is the page `<title>` (`<title>Activity Feed · NavERP</title>`) / a nav label, so the feed check passes on a
    feed rendering zero entries.
  fix: assert the real signals — `counts["audit"] == 0` under the project lens; `ctx("unread_count") ==
  ProjectNotification.objects.filter(tenant=…, recipient=user, is_read=False).count()`; `page_obj.paginator.count`
  for `?mine=1` vs the unfiltered count; `len(ctx("entries")) > 0` (or a specific entry `label`) for the feed.

- [I7] The harness asserts `changes["verb"]` for 11 of the contract's 13 mutating verbs, and never runs `mtg_cancel`'s success path
  file: `temp/smoke_79.py`  lines: 500-504
  finding: the assertion loop covers `chn_archive, mtg_start, mtg_complete, agi_cover, mai_toggle, dsh_claim,
  dsh_release, dsh_revoke, ntf_mark_read, ntf_mark_all_read, msg_edit` — **11**. The contract's verb set is
  **13**: `mtg_cancel` and `mtg_minutes` are missing. `mtg_minutes` is at least executed; `mtg_cancel` is
  posted **only** against an already-`completed` meeting (`:372`), which returns before the audit write, so
  its success edge is never exercised. `probe_lane5e.py` confirms both verbs write correctly — successful
  cancel → `audit_verb_present=True`; `mtg_minutes` → `audit_verb_present=True` — so no bug today, but the
  header's "verifies `AuditLog.changes['verb']` for all 12 verbs" is both the wrong count (13) and an
  overstatement (11 asserted).
  fix: add `mtg_cancel`/`mtg_minutes` to the loop and add a successful `mtg_cancel` (scheduled → cancelled)
  to the state-machine section.

- [M20] The smoke harness is not re-entrant — a second run aborts with an `AttributeError` instead of reporting
  file: `temp/smoke_79.py`  lines: 70-73 (fixture), 138 (crash site)
  finding: run twice in a row with no re-seed:
  ```
  --- run 1 ---   PASSED 276   FAILED 0
  --- run 2 ---   FIXTURE GAP — no such seeded row: ['mtg_sched']
                  Traceback (most recent call last):
                    File ".../temp/smoke_79.py", line 138, in <module>
                      ("mtg_edit", reverse("projects:mtg_edit", args=[mtg_sched.pk]), None),
                  AttributeError: 'NoneType' object has no attribute 'pk'
  ```
  Run 1's `mtg_start`/`mtg_complete` consume the only `scheduled` meeting, so `mtg_sched` is `None` on run 2.
  The "276/276" figure is therefore valid **only** from a pristine seed; a fixer re-running the gate after a
  partial fix gets a traceback, not a pass/fail signal. The header's own "35 junk-param combinations" is
  actually **36** (counted from the source), and Lanes 1 and 3's "247/247" contradicts the header's "276/276"
  (the real number is **276**).
  fix: make the fixture block self-healing — assert-or-create a `scheduled` meeting (or re-seed at the top of
  the script) — and correct the counts in this file's header.

- [M21] Coverage the smoke lacks that would catch a silent regression: positive filters, `?page=` edge values, the empty tenant, and second-user verbs
  file: `temp/smoke_79.py`  lines: 202-218 (JUNK), 265-291 (pagination)
  finding: four whole classes are untested —
  (a) **positive filter values** on any register (only junk is thrown; see the route-coverage section above);
  (b) **`?page=` edge values** — only `9999` is tried; `0`, `-1`, `abc`, `1.5` and the 19-digit overflow are
  never sent. `probe_lane5.py` §C sends all six to all five registers → **30/30 return 200**;
  (c) **an empty tenant** (no projects, no collab rows) — the smoke only uses `Acme`/`Globex`, both fully
  seeded. `probe_lane5.py` §E creates a scratch tenant + user and renders all 11 GET pages plus
  `ntf_mark_all_read` → **all 200, no 500**;
  (d) **second-user verbs** — the smoke tests `dsh_claim` contention and the `ntf_mark_all_read` inbox
  boundary with a *single* logged-in user. `probe_lane5b.py` §L drives a second `Acme` user:
  `[L1]` a held claim cannot be stolen (`holder 2->2`), `[L2]` any member may release (`claimed_by=None`),
  `[L3]` `mark_all_read` leaves the admin's inbox untouched (`admin unread 4->4`) — all correct, but
  unverified by the gate.
  fix: add one positive-value assertion per register facet, the six `?page=` edge values, an empty-tenant
  smoke tenant, and a two-client section for the claim/inbox verbs.

#### Could not reproduce / unverified (report as clean, with evidence)

- **The project-memory 500 class — NOT reproduced.** The recorded bug ("a new context key computed from a
  project-scoped variable 500'd on a page with no `?project=`") does not occur anywhere in 7.9. Every 7.9
  page renders **200** with: no params at all; `?project=` naming a real project that has **no** collaboration
  rows (`probe_lane5b.py` §K3 → `counts` all 0); `?project=` naming a **non-existent** id (§K4 →
  `project_ctx=None` + the "not in this workspace" warning in the HTML); and junk in **every** param of every
  list (`probe_lane5.py` §D, 14 combinations). A **tenant with no data at all** (§E) renders all 11 GET pages
  + `ntf_mark_all_read` at 200. The tenant-`None` guards also hold: the four create views 302 → `/`; the six
  lists render 200 empty (§F).
- **`activity_feed` window and caps — verified correct.** `?days=` changes the real window, not just the
  label: with one message back-dated 40 days, `counts["message"]` is 17 / 17 / 18 for 7 / 30 / 90
  (`probe_lane5b.py` §K1-K2) — the old row is excluded from 7d and 30d and included in 90d. `counts` is
  **pre-cap** and `entries` is **post-cap**: after minting 150 notifications, `counts["notification"] == 167`,
  `total_count == 2545`, `entry_count == 100`, `truncated == True` (`probe_lane5.py` §H3). A project lens
  zeroes the audit half (`counts["audit"] == 0`, §H4) and `?kind=` zeroes the other four cards (§H5) —
  the latter **confirms Lane 1's M3**, which I did not re-file.
- **Verb repetition — all safe, no 500s** (`probe_lane5.py` §B). `mtg_start`/`mtg_complete` refuse on the
  second call (`in_progress→in_progress`, `completed→completed`); `mtg_cancel` refuses a terminal meeting;
  `dsh_claim` re-claim is a stable no-op (holder **and** `claimed_at` unchanged); `dsh_release` refuses an
  unheld claim; `ntf_mark_all_read` on an empty inbox is a 200. `chn_archive`, `dsh_revoke`, `agi_cover`,
  `mai_toggle` and `ntf_mark_read` flip back on the second call — **by design** (each is a contract-pinned
  toggle, one writer per direction), not a double-mutation bug.
- **Seeder idempotency and flush re-entrancy — clean.** `seed_projects` twice with no `--flush` leaves every
  count identical (`chn=3 chm=18 dsh=4 mtg=4 agi=8 mai=7 ntf=18` both times) — a pure no-op. `--flush`
  **twice in a row** restores the same working state both times, with no FK-ordering error (the
  `ProjectNotification`-first ordering holds).
- **Lane 1's I1 — live-reproduced and confirmed, not contradicted** (`probe_lane5d.py`). I created a root +
  reply in `CHN-00001`, then repointed the root to `CHN-00002` via `msg_edit` (accepted, 200). Afterwards
  `CHN-00001` renders `message_count=11 reply_count=6` but only **5** replies, and `CHN-00002` shows the moved
  root with no replies — the reply is invisible on both channels while still counted. No 500 on either page.
  This corroborates Lane 1's I1 exactly (Important); I did not re-file it.
- **`mtg_list` row multiplication — does NOT occur.** The `object_list` contains exactly 4 objects for 4
  meetings, so `distinct=True` is doing its job (the 8 tokens are the link + `confirm()` pair, not extra
  rows). The *value* multiplication without `distinct` is I4's subject.

### Lane 6 — security-reviewer (serial pass 6)

**Scope check.** Read in full: the frozen contract (esp. §2 L27, §3, §4, §5, §6, §10); the six 7.9 view
modules, four form modules, five model modules and six url modules under
`apps/projects/{views,forms,models,urls}/CollaborationCommunication/`; the four shared toolkits they lean
on (`apps/core/forms/_common.py`, `apps/projects/forms/_common.py`, `apps/core/crud.py`,
`apps/core/utils.py`, `apps/projects/models/_base.py`); all 17 templates under
`templates/projects/collaboration/` plus the 7.9 regions of `templates/projects/overview.html`; the
`accounts.User` model (to confirm it carries a nullable `tenant`, which is what makes `TenantModelForm`
scope the `shared_with`/`presenter`/`assignee` User FKs); and lanes 1–5's findings. This lane is
**adversarial and empirical**, not static: I wrote three throwaway probe scripts
(`temp/probe_lane6.py`, `temp/probe_lane6b.py`, `temp/probe_lane6c.py` — all gitignored, every mutating
probe wrapped in a transaction that is rolled back) and **executed 60+ probes**, including the
crafted-cross-tenant-POST-body class the build's own harness does *not* cover. The live seed is left
pristine (`Acme`/`Globex` both `chn=3 chm=18 dsh=4 mtg=4 agi=8 mai=7 ntf=18`). **Could not verify:**
concurrency/TOCTOU behaviour (no parallel-request harness) and anything outside the 7.9 file set
(global `settings.py` security config, the test suite) — listed at the end rather than asserted.

**Area verdicts (coverage — a clean area is a result):**

1. **Tenant isolation — CLEAN (0 findings).** Every one of the 41 views is `@login_required` and every
   queryset/fetch is tenant-scoped: all 20 `get_object_or_404` sites carry `tenant=request.tenant` (or a
   `filter(tenant=…)` queryset), and `grep -rnE '\.objects\.all\(\)|\.objects\.get\('` over the six view
   modules returns **nothing**. Verified by execution, not by reading: **11 pk-carrying verbs**
   (`chn_archive`, `dsh_revoke`/`claim`/`release`, `mtg_start`/`complete`/`cancel`, `agi_cover`,
   `mai_toggle`, `ntf_mark_read`, `ntf_delete`) each return **404** on a Globex pk via POST (and 405 on
   GET, where `@require_POST` applies); `mtg_minutes` returns 404 on both GET and POST; the five foreign
   `*_detail`/`*_edit` GETs return 404. The two **child** routes are safe against a crafted POST that
   names a foreign parent: `agi_create`/`mai_create` resolve `meeting` from the URL with
   `get_object_or_404(Meeting, pk=pk, tenant=request.tenant)` → **404** on a Globex meeting, and their
   forms exclude `meeting` entirely, so the FK cannot be repointed. `msg_create`/`dsh_create`/
   `chn_create`/`mtg_create` reject a **foreign pk in the POST body** (the case the build harness never
   tested): `msg_create` + Globex `channel` → 200 + 0 new rows; `dsh_create` + Globex `document` or
   `project` or `channel` → 200 + 0 new rows; `chn_create`/`mtg_create` + Globex `project` → 200 + 0 new
   rows; `mai_create` + Globex `task` → 200 + 0 new rows. The **edit-repoint** vectors are closed too —
   `msg_edit` cannot move a message onto a foreign `channel`, `chn_edit`/`mtg_edit` cannot repoint
   `project`, `dsh_edit` cannot repoint `project`/`document` (each POST → 200, id unchanged). The five
   registers + the feed with `?<fk>=<foreign pk>` all return **200 with 0 rows** (the feed degrades to the
   tenant-scoped whole-workspace feed per §6.7 — see the unverified list). **No cross-tenant read, write
   or delete was found by any probe.**
2. **The M2M authorization boundary — CLEAN (0 findings).** `mentions` is the **only**
   `ModelMultipleChoiceField` in 7.9 (grep-confirmed; `filter_horizontal=("mentions",)` exists in
   `admin.py` only), and `ChannelMessageForm.__init__` narrows it explicitly
   (`forms/CollaborationCommunication/ChannelMessages.py:41-43`), which is the boundary
   `ModelMultipleChoiceField.clean()` re-validates against. Executed: `msg_create` with a Globex user pk
   → 200 with `errors={'mentions': ['Select a valid choice. 5 is not one of the available choices.']}`,
   0 new messages and **0 new notification rows in the Globex inbox**; a **mixed** valid-Acme +
   foreign-Globex mention list rejects the *whole* POST (no partial fan-out, no half-written message);
   the same on the `msg_edit` path; and a **tenant-less** user pk (the `admin` superuser) is rejected too
   (`.filter(tenant=self.tenant)` excludes it). The narrowing is correct and complete for this pass.
3. **Mass assignment — CLEAN (0 findings).** Every verb-written flag is absent from its form's
   `Meta.fields` **and** unreachable from raw request data. The 22 flags (`is_archived`/`archived_by`/
   `archived_at`; `is_active`/`revoked_by`/`revoked_at`/`claimed_by`/`claimed_at`; `is_read`/`read_at`;
   `is_covered`/`covered_by`/`covered_at`; `is_done`/`done_by`/`done_at`; `edited_by`/`edited_at`;
   `status`/`minutes`/`minutes_by`/`minutes_at`/`actual_start`/`actual_end`) plus `tenant`/`number`/
   `created_by` appear in no `Meta.fields`, and every assignment in the six view modules is a literal,
   `request.user`, `timezone.now()`, or `form.cleaned_data["minutes"]` (a plain `forms.Form` with that one
   field). Executed on the edit forms: a POST carrying `is_archived=True` to `chn_edit`, `is_active=False`
   + `claimed_by=<me>` to `dsh_edit`, `status=completed` + `minutes=FORGED` + `actual_end` to `mtg_edit`,
   `is_covered=True` + `covered_by` to `agi_edit`, `is_done=True` + `done_by` to `mai_edit` — **all
   ignored** (302, stored values unchanged), and `chn_create` cannot create a pre-archived channel. No
   `ProjectNotification` form exists at all, so `is_read`/`read_at` are unreachable from any POST.
4. **XSS / injection — CLEAN (0 findings).** `grep` over the 7.9 backend + templates for
   `|safe`/`mark_safe`/`autoescape off`/`format_html` returns **nothing** (the one hit is the `is_open`
   *property name*). The `activity_feed` `label`/`detail` strings are Python f-strings rendered through
   auto-escaping `{{ }}` (`activity_feed.html:95,103`), and every `{% url %}` argument is a pk. Executed:
   posting `<script>alert('xss')</script>` as a message body, a channel `topic`, and meeting `minutes`,
   then rendering the channel detail + the feed + the meeting detail, leaves **no raw payload** in the
   HTML (`&lt;script&gt;` present instead). No `eval`/`new Function`/inline handler carrying user data; no
   `.raw()`/`.extra()`/`cursor.execute` anywhere in 7.9.
5. **CSRF — CLEAN (0 findings).** No `@csrf_exempt` in any 7.9 view. All **37** `method="post"` forms in
   the 17 templates carry `{% csrf_token %}` (mechanically counted: 37 forms / 37 tokens, and a
   form-block scan finds no POST form missing the token). The one GET-only page (`activity_feed`) has no
   form.
6. **Authorization granularity — 1 finding (I8).** Everything else under the L27 member-level ruling is
   internally consistent: `dsh_release` letting any member release a stale claim is **explicitly
   authorised** by contract §6.3 ("a stale claim must not deadlock the document"), so it is *not* a
   finding; `ntf_mark_all_read` is correctly caller-scoped (executed: caller `4→0` unread, the other
   member `4→4`). The one defect is the two **single** notification verbs, which are tenant-scoped but not
   recipient-scoped — I8.
7. **Audit integrity — CLEAN (0 findings).** All **13** mutating verbs write
   `action ∈ {create, update, delete}` (≤10 chars — the `AuditLog.action` varchar(10) is never fed a verb
   name) with the verb in `changes`. Every one captures `previous` **before** mutating (verified by
   reading each view: `previous = obj.<flag>` precedes the branch in all five toggles, all three lifecycle
   verbs, `mtg_minutes`, `dsh_claim`/`release`). Executed: `chn_archive` writes
   `action='update'`, `changes={'verb': 'chn_archive', 'from': False, 'to': True}` — the direction is
   truthful. Every `changes` value is JSON-serialisable (bools/ints/strings/None).
8. **Uploads / file paths / SSRF / secrets — CLEAN (0 findings).** The contract's claim holds: grep for
   `FileField|ImageField|BinaryField|upload_to` in the 7.9 models returns **nothing** (the shared
   `core.Document` is reached by FK only — no second file store), and grep for
   `requests.|urllib|subprocess|open(|os.path|shutil` in the 7.9 backend returns **nothing**. No
   user-controlled path, no outbound HTTP, no secret/credential field, no money column.

**Findings.**

- [I8] One member can mark a teammate's notification read — or delete it outright
  file: `apps/projects/views/CollaborationCommunication/ProjectNotifications.py`  lines: 63-84 (`ntf_mark_read`), 114-123 (`ntf_delete`)
  finding: both verbs fetch `get_object_or_404(ProjectNotification, pk=pk, tenant=request.tenant)` —
  tenant-scoped but **not recipient-scoped** — while the sibling bulk verb is deliberately caller-scoped
  (`:97-98`, `filter(tenant=request.tenant, recipient=request.user, is_read=False)`) and the model
  docstring asserts the row is "one person's delivery row" and "an inbox is personal"
  (`models/CollaborationCommunication/ProjectNotifications.py:15-17`). Any workspace member can therefore
  clear a colleague's unread badge or destroy the colleague's delivery row, because
  `notification/list.html:100-105` renders both POST controls on **every** row of the register and the
  default lens is the whole workspace (executed: default `ntf_list` paginator count **18** of 18 tenant
  rows; only `?mine=1` narrows to **6**). I ran the attack as `admin_acme`:
  `POST /projects/notifications/<another Acme member's unread pk>/read/` → **302**, and the row read back
  `is_read=True`; `POST /projects/notifications/<same>/delete/` → **302** and the row was gone. This is
  not a tenant-boundary breach (no foreign row is reachable) and the register is already
  workspace-readable, so the impact is integrity/business, not confidentiality — but it directly
  contradicts the contract's own rationale for the bulk verb ("a bulk verb that could clear a teammate's
  is a privilege escalation with no upside"), i.e. it breaks the stated per-recipient delivery model
  rather than merely exercising the L27 member-level gate.
  fix: scope both fetches to the recipient, mirroring the bulk verb —
  `get_object_or_404(ProjectNotification, pk=pk, tenant=request.tenant, recipient=request.user)` in
  `ntf_mark_read`, and the same three kwargs for `ntf_delete` (fetch tenant+recipient, then delete, so the
  redirect target stays). Then stop offering the now-404 controls on someone else's row in
  `notification/list.html:97-107` and `notification/detail.html:11-13,52-56`
  (`{% if obj.recipient_id == request.user.pk %}`) — the L27 converse rule. If triage instead rules the
  workspace register intentionally co-managed, amend §3.5/§6.5 and drop the "inbox is personal" wording —
  but the single verbs and the bulk verb should not disagree.

**Could not verify (reported as such, not asserted).**

- **`dsh_claim` TOCTOU — not filed as a security finding.** The claim check (`:152`) and the save
  (`:158-160`) are not inside one conditional `UPDATE`/`select_for_update()`, so two simultaneous claims
  could both win. I did not build a parallel-request harness to test it, and it grants nothing a plain
  `dsh_release` + `dsh_claim` does not already grant — the contract deliberately lets **any** member
  release (`:170-184`). Noted only so triage can decide whether the "one holder at a time" affordance
  needs the atomic form.
- **Global security config, not this lane's file set.** `DEBUG`, `ALLOWED_HOSTS`, `SECURE_SSL_REDIRECT`,
  `HSTS`, `SESSION_COOKIE_SECURE`/`HTTPONLY`, `CSRF_COOKIE_SECURE`, `SECURE_CONTENT_TYPE_NOSNIFF` and
  `XFrameOptionsMiddleware` live in `config/settings.py` and were **not** re-verified here (7.9 adds no
  setting). `manage.py check` and the test suite were not run by this lane.
- **Concurrency generally.** `next_number()` and the audit `previous` capture are correct on every
  sequential path I exercised, but I did not test parallel writes.
- **`activity_feed` with `?project=<foreign pk>` returns the whole-workspace feed** (my probe initially
  flagged this as a possible leak, then I confirmed it is the contract-pinned §6.7 degradation: the id
  resolves to `None`, a `messages.warning` says so, and every source queryset is still
  `filter(tenant=tenant)`, so **no foreign-tenant row can appear**). It is a warning-plus-fallback, not a
  leak.

**Probe evidence (all rolled back; live seed verified pristine afterwards).**
`temp/probe_lane6.py` — 42 pass / 2 fail (the two fails are I8's two verbs, expected-and-reported);
`temp/probe_lane6b.py` — 12/12 pass (M2M rejection mechanism + XSS); `temp/probe_lane6c.py` — 12 pass /
1 "fail" that is the documented `activity_feed` fallback, not a defect; plus the inline `msg_edit`
mention + tenant-less-target probes (both rejected).

---

## Consolidated triage (post-lane-6; deduped, ordered Critical → Important → Minor)

**Lane yield:** 0 Critical filed by any lane · **8 Important** · **21 Minor** = 29 findings.
The four Criticals (C-A…C-D) were found by Step-3 verification **before** the lanes ran and are
already committed, so no lane re-filed them — the header above records all four.

**Independent verification of the two consequential Importants** (re-run by the orchestrator at
`temp/verify_79_I1_I8.py` against a pristine `--flush` seed, because a lane's claim is a claim
until it is reproduced):

- **I1 CONFIRMED, and worse than filed.** Repointing a root moved `CHM-00001` from `CHN-00001` to
  `CHN-00003` while its two replies (`CHM-00002`, `CHM-00003`) stayed in `CHN-00001`. The replies
  are then rendered on **neither** channel — not merely dropped from one view, as filed. Silent
  disappearance of user-authored content.
- **I8 CONFIRMED.** As `admin_acme`, `POST notifications/<ops_acme's row>/read/` → 302 and the row
  came back `is_read=True`; `POST notifications/<sales_acme's row>/delete/` → 302 and the tenant's
  row count went 18 → 17. The **bulk** verb is correctly caller-scoped (`mine` 4→0, `theirs` 7→7),
  so the two single-row verbs contradict both the model's per-recipient-delivery docstring and
  their own sibling.

### Dispositions

Legend: **FIX** = change shipped code · **DOC** = change the contract/comment only · **HARNESS** =
change `temp/smoke_79.py` or carry into the test-writing phase · **NO-ACTION** = ruled correct.

| ID | Sev | Disposition | Note |
|---|---|---|---|
| I1 | Important | **FIX** | Reject a channel change that would orphan replies |
| I2 | Important | **FIX** | Add the missing `(tenant, created_at)` indexes (migration) |
| I3 | Important | **FIX** | `_notify_mentions` per-row `full_clean()` cost |
| I8 | Important | **FIX** | Scope the two single-row notification verbs to the caller |
| M1 | Minor | **FIX** | `ntf_list` `select_related("message")` |
| M2 | Minor | **FIX** | Nullable `channel_id` into `{% url %}` |
| M3 | Minor | **FIX** | `?kind=` must not zero the other four feed counts |
| M4 | Minor | **FIX** | `truncated` notice hidden under a project filter |
| M8 | Minor | **FIX** | Badge fallback → `get_kind_display` |
| M9 | Minor | **FIX** | Badge fallback → `get_access_level_display` |
| M10 | Minor | **FIX** | Contract pins `minutes_form`; render it (or unpin it) |
| M11 | Minor | **FIX** | Child edit pages read an unpinned `meeting` key |
| M12 | Minor | **FIX** | RTL-hostile hard-coded reply indent |
| M13 | Minor | **FIX** | Three page-local blocks vs contract §10.3's one |
| M14 | Minor | **FIX** | Agenda `Minutes` header is ambiguous beside the minutes panel |
| M15 | Minor | **FIX** | Notification detail: §7 promises four guarded deep-links |
| M16 | Minor | **FIX** | `ntf_mark_all_read` one UPDATE per row |
| M18 | Minor | **FIX** | Indexes matching no access path — drop or wire up |
| M19 | Minor | **NO-ACTION** | Seeder per-row `full_clean()` is the app-wide idiom and runs off the request path |
| M5 | Minor | **DOC** | Contract §1 says 35 first segments; 38 is correct |
| M6 | Minor | **DOC** | Contract §0/§7 internal count inconsistency (six/four vs seven/five) |
| M7 | Minor | **NO-ACTION** | Three-level nesting is contract-authorised (§7) and the `cash/…/import.html` precedent |
| M17 | Minor | **NO-ACTION** | Superseded by I2's fix — the new index serves the facet |
| I4 | Important | **HARNESS** | `mtg_list` `distinct=True` asserted nowhere; the check is a false pass |
| I5 | Important | **HARNESS** | 18 of 41 routes never POSTed successfully |
| I6 | Important | **HARNESS** | Four surviving false-pass assertions |
| I7 | Important | **HARNESS** | `changes["verb"]` asserted for 11 of 13 verbs; `mtg_cancel` success never runs |
| M20 | Minor | **HARNESS** | Smoke is not re-entrant |
| M21 | Minor | **HARNESS** | Missing coverage: positive filters, `?page=` edges, empty tenant, second-user verbs |

### Explicit NO-ACTION rulings (recorded so coverage is visible)

- **`hrm.MeetingActionItem` name collision** — a same-named model in another app, deliberately
  documented in 7.9's docstring with the prefix `MAIT` (not `MAI`). Not a defect. *(Lane 2)*
- **The `ProjectNotification` no-form / no-create-route ruling** — rows are minted by triggers only;
  the absence of a form is the design. *(Lanes 1, 6)*
- **Deferred boundaries** — the document repository/version history (7.10), notification trigger
  rules + reminders + the recurrence engine (7.17), file-storage sync (7.18), sprint/retro boards
  (7.13), real-time co-editing, message reactions/attachments/rich text. None filed by any lane.
- **Member-level authorization** — L27 makes every 7.9 view member-level by contract, so a plain
  member mutating project collaboration data is intended, not a hole. I8 is filed not because a
  member may write, but because the row is *another person's* inbox delivery and the sibling verb
  already scopes to the caller.
- **`dsh_claim` TOCTOU** — Lane 6 noted the check-then-write is not locked but did not file it,
  because the contract deliberately lets **any** member release a stale claim. Accepted as-is.
- **Tenant isolation** — verified CLEAN by Lane 6 over 60+ probes including crafted cross-tenant
  POST **bodies** (foreign `channel`/`project`/`document`/`task`/`shared_with`/`assignee`/
  `presenter`/mention pks all rejected, 0 rows written, 0 foreign inbox rows; foreign pks on all 11
  pk-carrying verbs → 404). Lane 5's 30 IDOR probes agree. No finding.
