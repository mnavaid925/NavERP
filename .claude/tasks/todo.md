---
# Module 3 — HRM — Sub-module 3.20 Continuous Feedback (continuous-feedback) — plan from research-hrm-continuous-feedback.md (2026-07-06)

Third Performance-Management sub-module (3.18 Goal Setting -> 3.19 Performance Review -> **3.20
Continuous Feedback** -> 3.21 Performance Improvement). Ongoing/informal layer: real-time kudos/
appreciation/constructive feedback (incl. request-feedback pull + anonymous masking), 1:1 meetings
with shared/private notes + action items, and a given/received/requested feedback dashboard that is
a computed view, not a 5th model. PIP/warning-letters/coaching notes stay OUT of scope (3.21).

Reuses (never duplicates): `hrm.EmployeeProfile` (every person FK), `hrm.Objective` (3.18, optional
work-context link), `hrm.PerformanceReview` (3.19, optional review-context link), and — critically —
the 3.19 confidentiality precedents: `PerformanceReview.private_notes` (manager-only text never
rendered to the subject) and `PerformanceReview.is_anonymous` + `_can_view_review`/`_is_admin`/
`_current_employee_profile` (the masking + access-gate pattern). 3.20 clones these as
`OneOnOneMeeting.manager_private_notes` and `Feedback.is_anonymous` + new `_can_view_feedback`/
`_visible_feedback_q` helpers — do not re-derive the pattern from scratch, mirror it field-for-field.

## Models (from research)

- [ ] **`Feedback`** [FBK-, `TenantNumbered`] — the real-time feedback row (any employee -> any
  employee, any time; folds "request feedback" into the same table via `status`).
  - `giver` = FK `hrm.EmployeeProfile` (`on_delete=PROTECT`, `related_name="feedback_given"`,
    `null=True, blank=True` — nullable ONLY so a future true-anonymous-to-admin case can null it;
    the ordinary anonymous case keeps the FK and masks it on RENDER, mirroring
    `PerformanceReview.reviewer` + `is_anonymous`. Do not null it by default in forms/views.)
  - `receiver` = FK `hrm.EmployeeProfile` (`on_delete=PROTECT`, `related_name="feedback_received"`)
  - `feedback_type` CharField choices (driver: 3.20 · Real-time Feedback "Kudos, appreciation,
    constructive feedback" bullet + the must-have Request-feedback finding):
    `kudos` / `appreciation` / `constructive` / `request` — default `"kudos"`
  - `visibility` CharField choices (driver: public-vs-private-per-item, Keka/Matter/Small
    Improvements): `private` (receiver + giver + admin only) / `team` (receiver's org unit) /
    `public` (social feed) — default `"private"`
  - `status` CharField choices (driver: must-have Request-feedback pull workflow — Workday Inbox
    task / SAP "Requests Sent" tab / greytHR): `requested` / `given` / `acknowledged` — default
    `"given"` (a plain kudos is born already-`given`; a pull request is born `requested` and
    becomes `given` once the target responds)
  - `message` TextField (blank=True when `status="requested"` — the ask itself may be a bare
    request with no message yet; required at the form layer once `status` flips to `given`)
  - `is_anonymous` BooleanField default False (driver: must-have Anonymous Feedback bullet — direct
    reuse of `PerformanceReview.is_anonymous`; masks `giver` on render for non-privileged viewers)
  - `badge` = FK `hrm.KudosBadge` `null=True, blank=True`, `on_delete=SET_NULL`,
    `related_name="feedback_items"` (driver: values/badge-tagging feature, Bonusly/Kudos/Small
    Improvements/Matter — optional per-item, most feedback has none)
  - `related_objective` = FK `hrm.Objective` `null=True, blank=True`, `on_delete=SET_NULL`,
    `related_name="feedback_items"` (driver: "Feedback tied to work — project/goal/review context",
    Lattice/Leapsome/BetterWorks/15Five — reuses 3.18, never duplicates goal fields)
  - `related_review` = FK `hrm.PerformanceReview` `null=True, blank=True`, `on_delete=SET_NULL`,
    `related_name="feedback_items"` (same driver — reuses 3.19)
  - `requested_from` = self-FK `"self"` `null=True, blank=True`, `on_delete=SET_NULL`,
    `related_name="requested_responses"` (driver: folds request/response into ONE table per
    research's explicit recommendation — points at the `Feedback` row this one is answering, i.e.
    a `status="given"` response row's `requested_from` points back at the `status="requested"` ask;
    the ask row itself has `requested_from=None`)
  - `acknowledged_at` DateTimeField `null=True, blank=True, editable=False` (driver: SAP's Requests
    Sent + Workday's Inbox-task-closed precedent — set only by the `feedback_acknowledge` action,
    mirrors `PerformanceReview.acknowledged_at`)
  - `Meta.ordering = ["-created_at"]`; `unique_together = ("tenant", "number")`; indexes on
    `(tenant, receiver)`, `(tenant, giver)`, `(tenant, feedback_type)`, `(tenant, visibility)`,
    `(tenant, status)`
  - `clean()`: forbid `giver_id == receiver_id` outright (a person cannot give feedback to
    themselves), mirroring how `PerformanceReview.clean()` enforces subject/reviewer identity rules
    for its review_type
  - `__str__`: `f"{self.number} · {self.get_feedback_type_display()} -> {self.receiver.party.name}"`
  - Reuses `hrm.EmployeeProfile` (giver/receiver), optionally `hrm.Objective`, `hrm.PerformanceReview`
    — adds only the new `Feedback` table + the small `KudosBadge` catalog.

- [ ] **`OneOnOneMeeting`** [O2O-, `TenantNumbered`] — manager/employee 1:1 meeting shell.
  (NOTE: research's [1O1- or OOM-] suggestion is not a clean unambiguous prefix next to `FBK-`/
  `MAI-` — use **`O2O-`** instead, matching the "one-on-one" name; confirm no collision via
  `next_number` per-tenant sequencing, same mechanism as every other `NUMBER_PREFIX`.)
  - `manager` = FK `hrm.EmployeeProfile` (`on_delete=PROTECT`, `related_name="oneonones_as_manager"`)
  - `employee` = FK `hrm.EmployeeProfile` (`on_delete=PROTECT`, `related_name="oneonones_as_employee"`)
  - `scheduled_at` DateTimeField (driver: must-have recurring-1:1-schedule bullet, universal across
    all 14 leaders surveyed)
  - `status` CharField choices: `scheduled` / `completed` / `cancelled` — default `"scheduled"`
  - `agenda` TextField blank=True (driver: "Shared/collaborative agenda — talking points", Culture
    Amp/Small Improvements/Keka/SAP — editable by either party pre-meeting)
  - `shared_notes` TextField blank=True (driver: must-have shared-notes bullet — visible to both
    manager and employee post-meeting)
  - `manager_private_notes` TextField blank=True (driver: the private-notes-split confidentiality
    finding, Culture Amp "private bookmarks"/SAP "Save and Finish" — **direct clone of
    `PerformanceReview.private_notes`**: manager-only, NEVER rendered on the employee-facing detail
    view; help_text should say so verbatim like the reviewed precedent)
  - `related_objective` = FK `hrm.Objective` `null=True, blank=True`, `on_delete=SET_NULL`,
    `related_name="oneonones"` (driver: "1:1 wired to goals/OKRs", BetterWorks/Lattice/15Five)
  - `completed_at` DateTimeField `null=True, blank=True, editable=False` (set by the
    `oneononemeeting_complete` action, not the create/edit form)
  - `Meta.ordering = ["-scheduled_at"]`; `unique_together = ("tenant", "number")`; indexes on
    `(tenant, manager)`, `(tenant, employee)`, `(tenant, status)`, `(tenant, scheduled_at)`
  - `clean()`: forbid `manager_id == employee_id` (a 1:1 needs two distinct people)
  - Meeting history feature = **no new table** — `OneOnOneMeeting.objects.filter(employee=X)
    .order_by("-scheduled_at")` IS the history (mirrors how `GoalCheckIn` rows ARE the KeyResult
    history) — encode this as a list-view default ordering + no delete-then-recreate pattern
  - `__str__`: `f"{self.number} · {self.manager.party.name} & {self.employee.party.name}
    ({self.scheduled_at:%Y-%m-%d})"`
  - Reuses `hrm.EmployeeProfile` (manager/employee — manager resolved from the existing DERIVED
    `EmployeeProfile.manager` property, no new manager-lookup table), optionally `hrm.Objective`.

- [ ] **`MeetingActionItem`** [MAI-, `TenantNumbered`, child of `OneOnOneMeeting`] — mirrors the
  `KeyResult`->`Objective` / `ReviewRating`->`PerformanceReview` child-row pattern exactly.
  - `meeting` = FK `hrm.OneOnOneMeeting` (`on_delete=CASCADE`, `related_name="action_items"`)
  - `description` TextField (driver: "Action items with owner + due date" bullet, explicitly named
    in NavERP.md's 1:1 Meetings bullet; universal across Small Improvements/Culture Amp/Lattice/
    BetterWorks/greytHR/Keka)
  - `owner` = FK `hrm.EmployeeProfile` (`on_delete=PROTECT`, `related_name="meeting_action_items"`)
  - `due_date` DateField `null=True, blank=True`
  - `status` CharField choices: `open` / `done` — default `"open"`
  - `completed_at` DateTimeField `null=True, blank=True, editable=False` (set on status flip to
    `done` by the `meetingactionitem_toggle` action — mirrors how other HRM child rows timestamp
    their terminal state, e.g. `GoalCheckIn`/`ReviewRating` conventions)
  - `Meta.ordering = ["meeting", "due_date", "description"]`; `unique_together = ("tenant",
    "number")`; index on `(tenant, meeting)`, `(tenant, owner)`, `(tenant, status)`
  - `__str__`: `f"{self.number} · {self.description[:40]}"`
  - Reuses `hrm.EmployeeProfile` (owner), FKs its own new parent `OneOnOneMeeting`.

- [ ] **`KudosBadge`** [no prefix, `TenantOwned` only — small catalog, identical shape to
  `hrm.JobGrade`/`hrm.GoalPeriod`/`hrm.ReviewCycle`: identified by `name`, not auto-numbered].
  - `name` CharField max_length=100
  - `description` TextField blank=True
  - `icon` CharField max_length=50 blank=True (free-text — e.g. an emoji or icon class for a UI chip)
  - `color` CharField max_length=20 blank=True (free-text hex/Tailwind class for the chip)
  - `linked_value` CharField max_length=100 blank=True (driver: values/company-values tagging,
    Bonusly/Kudos/Small Improvements — a free-text tag to a company value, not a new Value model)
  - `is_active` BooleanField default=True
  - `Meta.ordering = ["name"]`; `unique_together = ("tenant", "name")`; index on
    `(tenant, is_active)`
  - `__str__`: `self.name`
  - Marked **optional-to-trim**: if scope pressure hits, fold into a single free-text
    `badge_label` CharField directly on `Feedback` instead and drop this model — but KEEP IT for
    this pass per the research's recommendation (small, adds the recognition-catalog feature, no
    real cost). `TenantOwned` only (no `NUMBER_PREFIX`) — confirms this is a lookup/catalog table,
    not a numbered transaction row.

## Confidentiality rules (explicit design point — carry through backend + templates)

- [ ] `OneOnOneMeeting.manager_private_notes` is **never** rendered on the employee-facing detail
  view or exposed via the edit form to a non-manager/non-admin — clone the exact
  `PerformanceReview.private_notes` gate: a `show_private = is_admin or is_manager` boolean computed
  in `oneononemeeting_detail` and passed to the template, which wraps the private-notes block in
  `{% if show_private %}`.
- [ ] `Feedback.is_anonymous=True` masks `giver` on **read** for everyone except a tenant admin —
  the `receiver` (and anyone else) sees a masked placeholder ("Anonymous") instead of the real name
  (mirrors `PerformanceReview.reviewer_anonymized` / `show_reviewer` computed flags exactly — do not
  invent new masking semantics). Add a `giver_anonymized` property on `Feedback`: `return
  self.is_anonymous` (kept as a property, not a raw field read, so future per-type masking rules
  have one place to change).
- [ ] New view-layer helpers in `apps/hrm/views.py` (placed in the 3.20 section, right after the
  existing 3.19 `_current_employee_profile`/`_is_admin` — reuse those two helpers, do not redefine):
  - `_can_view_feedback(request, feedback)` — a tenant admin, the `giver`, or the `receiver` may
    view a `Feedback` row's full content; a `visibility="public"` row is additionally viewable
    (giver masked if anonymous) by ANY employee since it's the public feed — mirror
    `_can_view_review`'s shape but branch on `visibility`.
  - `_visible_feedback_q(request)` — returns a `Q` restricting `feedback_list` to: public rows
    (any visibility) OR rows where the requester is giver/receiver OR (`visibility="team"` AND the
    requester shares the receiver's `EmployeeProfile.department` org unit). Returns `None` for a
    tenant admin (no restriction) — same `None`-means-unrestricted contract as `_visible_reviews_q`.
  - `_can_edit_feedback(request, feedback)` — only the `giver` (never the receiver) or a tenant
    admin, and only while `status != "acknowledged"` — mirrors `_can_edit_review`'s
    status-lock-plus-author-check shape.
- [ ] `KudosBadge`/`MeetingActionItem` have no confidentiality dimension — plain tenant-scoped CRUD.

## Backend (apps/hrm/ — EXTEND, do not create a new app)

- [ ] **models.py** — append a new `# 3.20 Continuous Feedback` section directly after the existing
  `# 3.19 Performance Review` block (after `ReviewRating`, ~line 5480), in this order: `KudosBadge`
  -> `Feedback` -> `OneOnOneMeeting` -> `MeetingActionItem` (catalog first, then the two
  parent/child pairs — mirrors the 3.18/3.19 ordering of catalog-then-transaction-then-child).
  Add the module-level docstring comment block matching the 3.19 style (explains what's reused vs.
  new, references NavERP-ERD.md, no new core-spine entity, posts no GL).
- [ ] **forms.py** — 4 new `TenantModelForm` subclasses, placed after `ReviewRatingForm`:
  - `KudosBadgeForm` — fields `["name", "description", "icon", "color", "linked_value",
    "is_active"]` (no tenant-FK dependent queryset needed, like `GoalPeriodForm`)
  - `FeedbackForm` — fields `["receiver", "feedback_type", "visibility", "message", "is_anonymous",
    "badge", "related_objective", "related_review", "requested_from"]` — **exclude** `giver`
    (resolved from `request.user` in the view, mirroring how `created_by` is set server-side on
    `GoalCheckIn`, never form-typed), `status`/`number`/`acknowledged_at` (workflow-owned, changed
    only by the create-as-request path and the `feedback_acknowledge` action — same reasoning
    comment as `PerformanceReviewForm`'s "workflow/calibration fields...never on this form").
    `__init__` scopes `receiver`/`related_objective`/`related_review`/`badge`/`requested_from`
    querysets to `self.tenant` (mirror `ObjectiveForm.__init__`'s tenant-scoping block).
  - `OneOnOneMeetingForm` — fields `["manager", "employee", "scheduled_at", "agenda",
    "shared_notes", "manager_private_notes", "related_objective"]` — **exclude `status`** (mirrors
    the 3.18/3.19 fixed bug where exposing `status` let a non-admin bypass a workflow gate; changed
    only via `oneononemeeting_complete`/`oneononemeeting_cancel` actions). Keep `manager_private_notes`
    ON the form (unlike a read-side gate — the writer, here the manager, must be able to type it;
    the READ-side gate is what's confidential, not the write side). `__init__` scopes
    `manager`/`employee`/`related_objective` to `self.tenant`.
  - `MeetingActionItemForm` — fields `["description", "owner", "due_date"]` — **exclude `status`**
    (changed only by `meetingactionitem_toggle`, mirrors why `KeyResultForm`/`ReviewRatingForm`
    keep workflow fields off nested-child forms where a toggle action exists); `meeting` set from
    the URL in the nested create view, `number`/`completed_at` auto/workflow.
- [ ] **views.py** — append a new `# 3.20 Continuous Feedback (Performance Mgmt)` section directly
  after the 3.19 block (after `reviewrating_delete`). Reuse `_current_employee_profile`/`_is_admin`
  from the 3.19 section rather than redefining. All views `@login_required`, tenant-scoped via
  `get_object_or_404(Model, pk=pk, tenant=request.tenant)` / `.filter(tenant=request.tenant)`.
  - `_can_view_feedback`, `_visible_feedback_q`, `_can_edit_feedback` helpers (see Confidentiality
    section above) placed first in the block.
  - `kudosbadge_list` / `_create` / `_detail` / `_edit` / `_delete` — plain `crud_list`/`crud_create`/
    `crud_detail`/`crud_edit`/`crud_delete` wrappers (search on `name`, filter on `is_active`), same
    shape as `goalperiod_*`.
  - `feedback_list` — `crud_list` over `Feedback.objects.filter(tenant=request.tenant)
    .select_related("giver__party", "receiver__party", "badge", "related_objective",
    "related_review")`, apply `_visible_feedback_q` before `crud_list`; search on
    `("number", "message", "giver__party__name", "receiver__party__name")`; filters:
    `feedback_type`, `visibility`, `status`; extra `?is_anonymous=1` filter branch (maps to
    `is_anonymous=True`, serves the "Anonymous Feedback" nav bullet); extra_context passes
    `feedback_type_choices`, `visibility_choices`, `status_choices`,
    `employees` (for a receiver-filter dropdown), `?given=1`/`?received=1`/`?requested=1` query-param
    branches (mirror `?mine=1` on `performancereview_list`) so the same list view backs the
    given/received/requested cuts if a link needs it outside the dashboard.
  - `feedback_create` — resolves `giver = _current_employee_profile(request)` server-side (never
    form-typed); if the POST carries `?respond_to=<pk>` (answering a request), sets
    `requested_from_id` and `status="given"`; otherwise default `status` per `feedback_type`
    (`"request"` type -> `status="requested"`, everything else -> `status="given"`).
  - `feedback_detail` — gate with `_can_view_feedback`, compute `giver_display` (masked "Anonymous"
    label vs. `obj.giver.party.name`) and pass to template — never let the template read
    `obj.giver` directly when masking applies.
  - `feedback_edit` — gate with `_can_edit_feedback`.
  - `feedback_delete` — `@require_POST`, gate: admin OR (giver AND `status != "acknowledged"`).
  - `feedback_acknowledge` — `@require_POST`, only the `receiver` (or admin) may acknowledge;
    guard `status in ("given",)` -> `"acknowledged"` + `acknowledged_at=timezone.now()`;
    `write_audit_log(..., "update", {"action": "acknowledge"})` (mirror
    `performancereview_acknowledge`).
  - `feedback_respond` — `@require_POST` or a small form view: turns a `status="requested"` row
    into a completed ask by creating (or redirecting to `feedback_create?respond_to=<pk>`) — decide
    at build time whichever is simpler; either is acceptable as long as the requester ends up seeing
    a `status="given"` row with `requested_from` pointing at the original ask.
  - `oneononemeeting_list` — `crud_list` scoped to rows where the requester is `manager` OR
    `employee` OR is a tenant admin (a 1:1 is inherently two-party, not tenant-public — no third
    "public" case here, so either build a small analogous `_visible_meetings_q` helper or inline the
    two-branch filter directly in the view, whichever reads cleaner at build time); search on
    `("number", "manager__party__name", "employee__party__name")`; filters: `status`, `manager`,
    `employee`; extra_context `status_choices`, `employees`.
  - `oneononemeeting_create` / `_detail` (gate: admin/manager/employee only, `show_private =
    is_admin or is_manager` passed to template so `manager_private_notes` block can be conditioned)
    / `_edit` (same gate) / `_delete` (`@require_POST`).
  - `oneononemeeting_complete` — `@require_POST`, admin/manager only, guard `status="scheduled"` ->
    `"completed"` + `completed_at=timezone.now()`.
  - `oneononemeeting_cancel` — `@require_POST`, admin/manager only, guard `status="scheduled"` ->
    `"cancelled"`.
  - `meetingactionitem_create` — nested under a meeting (`meeting_pk` in the URL), gate: only the
    meeting's manager/employee/admin may add an action item.
  - `meetingactionitem_detail` / `_edit` / `_delete` — same nested-gate pattern as
    `reviewrating_detail`/`_edit`/`_delete` (gate via the parent `OneOnOneMeeting`, not a standalone
    permission).
  - `meetingactionitem_toggle` — `@require_POST`, flips `open<->done`, sets/clears
    `completed_at`; gate: the item's `owner`, the meeting's manager, or admin.
  - `feedback_dashboard` — the **computed view, not a model** (per research — mirror
    `calibration_board`'s report-view shape: no CRUD, `@login_required` not `@tenant_admin_required`
    since every employee views their OWN dashboard, admin can view any via `?employee=<pk>`).
    Resolve `target = _current_employee_profile(request)` (or the admin-selected `?employee=`);
    build 3 annotated querysets over `Feedback.objects.filter(tenant=request.tenant)`:
    `given = qs.filter(giver=target, status__in=("given","acknowledged"))`,
    `received = qs.filter(receiver=target, status__in=("given","acknowledged"))`,
    `requested = qs.filter(giver=target, status="requested")` (mirrors SAP SuccessFactors'
    Received/Given/Requests-Sent 3-tab precedent named explicitly in the research). Add a
    `feedback_type` breakdown via `.values("feedback_type").annotate(Count("id"))` for each of
    given/received (serves the "sentiment/type breakdown" common-priority feature) and a simple
    `created_at__gte=<30 days ago>` recency count (serves "feedback velocity" common-priority
    feature) — all Python/ORM aggregation, no new stored column, exactly like `Objective.progress_pct`
    /`PerformanceReview.overall_rating`.
- [ ] **urls.py** — append inside the existing `hrm` `app_name` urlpatterns list, directly after
  the `reviewrating_*` block:
  ```
  path("kudos-badges/", views.kudosbadge_list, name="kudosbadge_list"),
  path("kudos-badges/add/", views.kudosbadge_create, name="kudosbadge_create"),
  path("kudos-badges/<int:pk>/", views.kudosbadge_detail, name="kudosbadge_detail"),
  path("kudos-badges/<int:pk>/edit/", views.kudosbadge_edit, name="kudosbadge_edit"),
  path("kudos-badges/<int:pk>/delete/", views.kudosbadge_delete, name="kudosbadge_delete"),

  path("feedback/", views.feedback_list, name="feedback_list"),
  path("feedback/add/", views.feedback_create, name="feedback_create"),
  path("feedback/<int:pk>/", views.feedback_detail, name="feedback_detail"),
  path("feedback/<int:pk>/edit/", views.feedback_edit, name="feedback_edit"),
  path("feedback/<int:pk>/delete/", views.feedback_delete, name="feedback_delete"),
  path("feedback/<int:pk>/acknowledge/", views.feedback_acknowledge, name="feedback_acknowledge"),
  path("feedback/<int:pk>/respond/", views.feedback_respond, name="feedback_respond"),
  path("feedback/dashboard/", views.feedback_dashboard, name="feedback_dashboard"),

  path("one-on-ones/", views.oneononemeeting_list, name="oneononemeeting_list"),
  path("one-on-ones/add/", views.oneononemeeting_create, name="oneononemeeting_create"),
  path("one-on-ones/<int:pk>/", views.oneononemeeting_detail, name="oneononemeeting_detail"),
  path("one-on-ones/<int:pk>/edit/", views.oneononemeeting_edit, name="oneononemeeting_edit"),
  path("one-on-ones/<int:pk>/delete/", views.oneononemeeting_delete, name="oneononemeeting_delete"),
  path("one-on-ones/<int:pk>/complete/", views.oneononemeeting_complete, name="oneononemeeting_complete"),
  path("one-on-ones/<int:pk>/cancel/", views.oneononemeeting_cancel, name="oneononemeeting_cancel"),

  path("one-on-ones/<int:meeting_pk>/action-items/add/", views.meetingactionitem_create, name="meetingactionitem_create"),
  path("action-items/<int:pk>/", views.meetingactionitem_detail, name="meetingactionitem_detail"),
  path("action-items/<int:pk>/edit/", views.meetingactionitem_edit, name="meetingactionitem_edit"),
  path("action-items/<int:pk>/delete/", views.meetingactionitem_delete, name="meetingactionitem_delete"),
  path("action-items/<int:pk>/toggle/", views.meetingactionitem_toggle, name="meetingactionitem_toggle"),
  ```
  (URL-name convention matches existing `hrm/urls.py` — verify no name collision against the 60+
  existing url names before commit.)
- [ ] **admin.py** — 4 new `@admin.register` blocks after `ReviewRatingAdmin`:
  - `KudosBadgeAdmin` — `list_display = ("name", "linked_value", "is_active", "tenant")`,
    `list_filter = ("tenant", "is_active")`, `search_fields = ("name",)`.
  - `FeedbackAdmin` — `list_display = ("number", "giver", "receiver", "feedback_type", "visibility",
    "status", "tenant")`, `list_filter = ("tenant", "feedback_type", "visibility", "status",
    "is_anonymous")`, `search_fields = ("number", "message", "giver__party__name",
    "receiver__party__name")`, `raw_id_fields = ("giver", "receiver", "badge", "related_objective",
    "related_review", "requested_from")`, `readonly_fields = ("number", "acknowledged_at",
    "created_at", "updated_at")`.
  - `OneOnOneMeetingAdmin` — `list_display = ("number", "manager", "employee", "scheduled_at",
    "status", "tenant")`, `list_filter = ("tenant", "status")`, `search_fields = ("number",
    "manager__party__name", "employee__party__name")`, `raw_id_fields = ("manager", "employee",
    "related_objective")`, `readonly_fields = ("number", "completed_at", "created_at", "updated_at")`.
  - `MeetingActionItemAdmin` — `list_display = ("number", "meeting", "description", "owner",
    "due_date", "status", "tenant")`, `list_filter = ("tenant", "status")`, `search_fields =
    ("number", "description")`, `raw_id_fields = ("meeting", "owner")`, `readonly_fields =
    ("number", "completed_at", "created_at", "updated_at")`.
- [ ] **seed_hrm.py** — add a `_seed_feedback(self, tenant, *, flush)` method, called from `handle()`
  right after the existing `self._seed_reviews(tenant, flush=options["flush"])` line. Idempotent
  per the Seed Command Rules: `if flush:` delete `MeetingActionItem`/`OneOnOneMeeting`/`Feedback`/
  `KudosBadge` (child-to-parent order) for the tenant; `if Feedback.objects.filter(tenant=tenant)
  .exists(): notice + return`; guard `len(emps) < 2` skip like `_seed_reviews` does. **Reuse the
  EXISTING `EmployeeProfile.objects.filter(tenant=tenant)` queryset** (same `emps`/`emp(i)`/
  `manager_profile_of` helper pattern already in `_seed_reviews` — do not create a second employee
  fixture set). Create:
  - 3-4 `KudosBadge` rows (e.g. "Team Player" / "Above & Beyond" / "Customer Hero" / "Innovator",
    each with an `icon`/`color`/`linked_value` filled in)
  - 5-6 `Feedback` rows spanning types/visibility/status: a public kudos with a badge, a private
    constructive-feedback item, a team-visibility appreciation, an anonymous peer feedback
    (`is_anonymous=True`), a `related_objective`-linked feedback (FK an existing seeded `Objective`
    if one exists for the tenant), and one `status="requested"` row + its `status="given"` response
    row (`requested_from` wired) to demonstrate the pull workflow end-to-end
  - 2 `OneOnOneMeeting` rows (one `status="completed"` with `shared_notes` +
    `manager_private_notes` filled in + 2 `MeetingActionItem` children (one `open`, one `done` with
    `completed_at` set), one `status="scheduled"` upcoming with just an `agenda`)
  - Print a `self.stdout.write(self.style.SUCCESS(...))` summary line matching the `_seed_reviews`
    style (counts of badges/feedback/meetings/action items).

## Wire-up

- [ ] `config/settings.py` — no change needed (`apps.hrm` already in `INSTALLED_APPS`).
- [ ] `config/urls.py` — no change needed (`hrm/` already included).
- [ ] `apps/core/navigation.py` `LIVE_LINKS["3.20"]` — add directly after the existing `"3.19"` dict
  entry, matching the exact NavERP.md §3.20 bullet text as dict keys:
  ```python
  # 3.20 Continuous Feedback — third Performance-Management sub-module (real-time kudos/
  # appreciation/constructive feedback incl. request-pull + anonymous masking; 1:1 meetings with
  # shared/private notes + action items; a given/received/requested feedback dashboard). PIP/
  # warning-letters/coaching notes are 3.21.
  "3.20": {
      "Real-time Feedback": "hrm:feedback_list",                          # bullet (Feedback CRUD, all types/visibility)
      "1:1 Meetings": "hrm:oneononemeeting_list",                         # bullet (OneOnOneMeeting + MeetingActionItem)
      "Feedback Dashboard": "hrm:feedback_dashboard",                     # bullet (given/received/requested computed view)
      "Anonymous Feedback": "hrm:feedback_list?is_anonymous=1",           # bullet (is_anonymous=True slice)
  },
  ```

## Templates (templates/hrm/feedback/)

One sub-module folder (`feedback/`, matching the NavERP.md §3.20 slug — a new folder, distinct from
the shared `performance/` folder that 3.18/3.19 already use), one entity folder per model inside it:

- [ ] `templates/hrm/feedback/kudosbadge/list.html` — filter bar (`is_active`), Actions column
  (view/edit/delete), pagination, empty-state.
- [ ] `templates/hrm/feedback/kudosbadge/form.html` — create/edit (name/description/icon/color/
  linked_value/is_active).
- [ ] `templates/hrm/feedback/kudosbadge/detail.html` — badge chip preview + usage count
  (`feedback_items.count`).
- [ ] `templates/hrm/feedback/feedback/list.html` — filter bar reflecting `request.GET`
  (`feedback_type`, `visibility`, `status`, receiver dropdown, `is_anonymous=1` toggle), Actions
  column (view/edit-if-`can_edit`/delete-if-`can_edit`/acknowledge-button-if-receiver-and-pending),
  masked giver name where `is_anonymous` applies, badge chip render, pagination, empty-state.
- [ ] `templates/hrm/feedback/feedback/form.html` — create/edit; conditionally render `message` as
  optional when `feedback_type == "request"` (progressive enhancement via a small script or just
  leave server-side validation as the source of truth); receiver/badge/related_objective/
  related_review dropdowns.
- [ ] `templates/hrm/feedback/feedback/detail.html` — shows masked-or-real giver per
  `giver_display`, message, badge chip, related objective/review links (if set), acknowledge button
  (receiver only, `status="given"`), respond button (giver only, `status="requested"`), Actions
  sidebar (edit/delete conditional on `_can_edit_feedback`, Back to List).
- [ ] `templates/hrm/feedback/oneononemeeting/list.html` — filter bar (`status`, manager/employee
  dropdowns), Actions column (view/edit/delete/complete-button-if-scheduled/cancel-button-if-
  scheduled), pagination, empty-state.
- [ ] `templates/hrm/feedback/oneononemeeting/form.html` — create/edit (manager/employee/
  scheduled_at/agenda/shared_notes/manager_private_notes/related_objective).
- [ ] `templates/hrm/feedback/oneononemeeting/detail.html` — agenda + shared_notes visible to both;
  `manager_private_notes` block wrapped `{% if show_private %}`; action items sub-list with an
  inline "add action item" link + a toggle-done control per row; complete/cancel buttons
  (conditional on `status="scheduled"` + gate); Actions sidebar (edit/delete/Back to List).
- [ ] `templates/hrm/feedback/meetingactionitem/form.html` — nested create/edit (description/owner/
  due_date) — reachable only from a meeting's detail page.
- [ ] `templates/hrm/feedback/meetingactionitem/detail.html` — description/owner/due_date/status/
  completed_at, link back to parent meeting.
- [ ] `templates/hrm/feedback/dashboard.html` — the **Feedback Dashboard** standalone page (no
  entity folder — a computed view per the Template Folder Structure rule's "standalone pages" carve-
  out, same tier as `hrm/hrm_overview.html`/`calibration_board.html`): 3-column or 3-tab layout
  (Given / Received / Requested) each listing recent `Feedback` rows + counts, a `feedback_type`
  breakdown mini-chart-or-table for given and received, a 30-day recency count, an admin
  `?employee=<pk>` selector when `is_admin`.

## Verify

- [ ] `python manage.py makemigrations hrm` — expect a single new incremental migration
  `0034_<autoname>.py` (4 new models + their indexes; NOT a renumbered `0001`).
- [ ] `python manage.py migrate`
- [ ] `python manage.py seed_hrm` run TWICE — second run must print the "already exists...use
  --flush" notice for the new feedback data, not raise `IntegrityError`/duplicate rows (idempotency
  proof for `KudosBadge`/`Feedback`/`OneOnOneMeeting`/`MeetingActionItem`).
- [ ] `python manage.py check` — zero errors/warnings.
- [ ] `temp/` render-sweep script (mirror the 3.19 smoke pattern): hit every new `hrm:*` url name
  added above as a logged-in tenant admin — expect 200 (GET pages) / 302 (POST-only actions without
  POST, or successful redirects after POST); grep rendered HTML for a leaked `{#`/`{% comment`
  Django-comment-tag string (must never appear in served output); cross-tenant IDOR check — log in
  as tenant A, request tenant B's `feedback_detail`/`oneononemeeting_detail`/
  `meetingactionitem_detail`/`kudosbadge_detail` pks -> expect 404 (the `tenant=request.tenant`
  filter in `get_object_or_404` already gives this "for free", the sweep just PROVES it holds for
  each of the 4 new models).
- [ ] Confirm the sidebar (`apps/core/navigation.py` `LIVE_LINKS`) shows all 4 of 3.20's bullets as
  **Live** (not "Coming Soon") when logged in as a tenant admin.
- [ ] Manually exercise the confidentiality boundaries once, end to end: (a) log in as an employee
  who is neither giver/receiver/team-mate of a `visibility="private"` Feedback row -> `feedback_
  detail` denies/404s or the row is absent from their `feedback_list`; (b) log in as the RECEIVER of
  an `is_anonymous=True` Feedback row -> giver name renders as masked, not the real name; (c) log in
  as the EMPLOYEE side of an `OneOnOneMeeting` -> `manager_private_notes` block is absent from the
  rendered detail HTML (grep the response body for the private-notes text, expect it NOT found);
  (d) log in as the MANAGER/admin side -> the same block IS present.

## Close-out

- [ ] `code-reviewer` agent — apply findings, commit.
- [ ] `explorer` agent — apply findings, commit.
- [ ] `frontend-reviewer` agent — apply findings, commit.
- [ ] `performance-reviewer` agent — apply findings, commit (watch for the same N+1 shape the 3.19
  code-reviewer flagged: `feedback_dashboard`/`feedback_list` must `select_related`/`prefetch_related`
  giver/receiver/badge before rendering rows, exactly like the fix applied to
  `performancereview_list`/`_detail`).
- [ ] `qa-smoke-tester` agent — apply findings, commit.
- [ ] `security-reviewer` agent — apply findings, commit (the confidentiality boundaries above —
  `manager_private_notes` leak, anonymous-giver leak, cross-tenant IDOR — are exactly the class of
  bug this agent caught on 3.19's `private_notes`; expect it to probe the same shape here).
- [ ] `test-writer` agent — apply output, commit (expect a similar split to 3.19's 111 view-tests +
  94 security-tests: CRUD round-trips per model, the acknowledge/complete/cancel/toggle/respond
  custom actions, `_can_view_feedback`/`_can_edit_feedback`/`_visible_feedback_q` boundary tests
  including the anonymous-giver-masked-on-read case and the private-notes-never-in-employee-response
  case, cross-tenant IDOR 404 across all 4 models' detail/edit/delete, CSRF + anon-redirect, form-
  smuggling guards on `status`/`number`/`acknowledged_at`/`completed_at`).
- [ ] Update `.claude/skills/hrm/SKILL.md` — add the 3.20 model table (`Feedback`/`OneOnOneMeeting`/
  `MeetingActionItem`/`KudosBadge`), the confidentiality design point
  (`_can_view_feedback`/`_visible_feedback_q`/`_can_edit_feedback`, `manager_private_notes` gate),
  routes, `feedback/` templates, `_seed_feedback` note, `LIVE_LINKS["3.20"]`; bump the model count
  and built-list/frontmatter/LIVE_LINKS range through 3.20; note deferrals to 3.21.

## Later passes / deferred (carried over from research — do not build this pass)

- Points/leaderboards/redeemable-rewards catalog (Bonusly/Kudos/Matter coins) — needs a
  `PointLedger` + `RewardCatalog` pair + a payment/gift-card vendor integration.
- Public social feed with likes/comments on feedback items — the feed QUERY (`visibility="public"`
  rows) is built this pass; a first-class `FeedbackReaction`/`FeedbackComment` model is deferred.
- Milestone auto-celebrations (birthdays, work anniversaries) — derivable from existing
  `EmployeeProfile`/`core.Employment` dates via a scheduled job; no new table, not in this pass's
  view layer.
- Reminders when feedback/1:1 cadence lapses (Leapsome) — belongs on the core `Notification` model
  (Module 0) triggered by a scheduled task reading `Feedback`/`OneOnOneMeeting` recency.
- AI-synthesized sentiment insights (Peakon) — requires an LLM integration.
- Calendar sync (Google/Outlook) for 1:1 scheduling (Keka) — `OneOnOneMeeting.scheduled_at` is
  enough of a data model to build the integration against later.
- Pre-meeting engagement pulse / post-meeting "rate this conversation" (Trakstar/Darwinbox) — a
  differentiator in only 2 of 14 surveyed products; better suited to a future engagement-survey
  capability.
- Two-way anonymous reply threads (preserving asymmetric masking) — real complexity beyond a simple
  `is_anonymous` boolean; a candidate `Feedback.in_reply_to` enhancement in a LATER pass (distinct
  from `requested_from`, which is built this pass).
- Org-wide anonymous pulse-survey engine (Peakon's core product) — a materially different
  aggregate-survey instrument, out of scope for NavERP.md's 3.20 bullet wording.
- Bulk-invite to recurring 1:1 channels at scale (SAP SuccessFactors) — an admin UI/UX convenience
  over the existing `OneOnOneMeeting` model, not a modeling requirement.
- 3.21 Performance Improvement (PIP Management / Warning Letters / Coaching Notes) — the next
  sub-module in the Performance-Management cluster; explicitly out of scope for 3.20.

## Review notes

**Built 3.20 Continuous Feedback end-to-end (2026-07-06).** 4 models as planned — `KudosBadge` (catalog),
`Feedback` [FBK-], `OneOnOneMeeting` [O2O-], `MeetingActionItem` [MAI-] — + a computed `feedback_dashboard` (no
5th model). Migrations `0034` (the 4 tables + 13 indexes) and `0035` (the terminal `responded` status added during
review). Seeder `_seed_feedback` idempotent, both tenants, in the central flush teardown before `EmployeeProfile`.
`LIVE_LINKS["3.20"]` wires all 4 NavERP.md bullets. Templates under `templates/hrm/performance/` (consistent with
3.18/3.19, NOT the `feedback/` folder the plan first suggested).

**All 7 review agents applied** (per the mandatory sequence):
- **code-reviewer** — 1 Critical (`kudosbadge_detail` recent-awards bypassed `_visible_feedback_q` → leaked private/
  team feedback recipients) + 2 Important (request→response never closed the loop / re-answerable forever → added the
  terminal `responded` status; `FeedbackForm.related_review` leaked the 3.19 review roster → scoped to the giver's
  visible reviews) + minors; also the app-wide audit gap (`private_notes`/`manager_private_notes` now in
  `_SENSITIVE_AUDIT_FIELDS`).
- **explorer** — 1 real silent-blank bug: `feedback/detail.html` read `obj.giver_display` (a bare context key, not a
  model attr) → the "From" row rendered blank for everyone; fixed to `giver_display`. + action-item affordance gating.
- **frontend-reviewer** — gated the standalone `meetingactionitem/detail.html` Edit/Delete (was unconditional).
- **performance-reviewer** — clean (indexes/annotations/no-N+1 confirmed); trimmed 3 unused `select_related` JOINs.
- **qa-smoke-tester** — 45/45 checks (GET sweep, content assertions, workflow POSTs, IDOR, idempotency) green.
- **security-reviewer** — no Critical/High; 1 Medium fixed (`_can_manage_action_item` + `MeetingActionItemForm.owner`
  — edit rights could exceed view rights for a non-participant owner).
- **test-writer** — **258 tests** (51 model + 109 view + 98 security), all green; **HRM 3,550 / project-wide 6,197**,
  full suite exit 0. No product bugs surfaced.

**Deferred to 3.21 (Performance Improvement):** PIP/warning-letters/coaching. Other deferrals (points/leaderboards,
social feed reactions, AI sentiment, calendar sync, pulse surveys) per the research catalog. **Next: 3.21.**
