---
# Module 3 — HRM — Sub-module 3.21 Performance Improvement (hrm-performance-improvement) — plan from research-hrm-performance-improvement.md (2026-07-07)

Fourth and FINAL Performance-Management sub-module (3.18 Goal Setting -> 3.19 Performance Review ->
3.20 Continuous Feedback -> **3.21 Performance Improvement**). The corrective-action/disciplinary
layer: structured Performance Improvement Plans (PIPs) with an HR-approval workflow, progressive
disciplinary warning letters, and manager-only coaching logs. These are the most sensitive HRM
records in the system (disciplinary/legal exposure) — confidentiality is the design crux.

Reuses (never duplicates): `hrm.EmployeeProfile` (every person FK — subject/manager/issued_to/
issued_by/coach/employee, all by string FK, NEVER a new employee table); optional links to 3.19
`hrm.PerformanceReview` (`triggering_review`, SET_NULL) and to the new `PerformanceImprovementPlan`
itself (`related_pip` off `WarningLetter`/`CoachingNote`, SET_NULL). No new core-spine entity;
nothing posts to the GL. Confidentiality CLONES the 3.19/3.20 precedents field-for-field — do NOT
re-derive from scratch:
- `PerformanceReview.private_notes` + `_can_view_review`/`_visible_reviews_q`/`_can_edit_review` ->
  the shape for `_can_view_pip`/`_visible_pips_q`/`_can_edit_pip` (subject-or-manager-or-admin ONLY,
  no team/public tier — a PIP/warning letter is never "team visible" the way 3.20 Feedback can be).
- `OneOnOneMeeting.manager_private_notes` + `_can_manage_meeting` -> the shape for the WHOLE
  `CoachingNote` model's read/edit gate (coach-or-admin ONLY — the coached employee subject is
  explicitly EXCLUDED; this is the strictest gate in the entire Performance-Management cluster).
- `reviewcycle_advance_phase` (`@tenant_admin_required`, workflow off the form) -> the shape for
  `pip_hr_approve` / `pip_close` / `pip_extend`.

**IMPORTANT — `EmployeeProfile.manager`/`.department` are Python PROPERTIES** (derived from
`employment.manager`/`employment.org_unit`), NOT DB columns. Any ORM filter that needs "this
profile's manager" MUST go through `employment__manager` (a `core.Party` FK) or resolve the
property in Python and filter by `.pk` — never `EmployeeProfile.objects.filter(manager=x)` (mirrors
the `manager_profile_of()` helper already used in `_seed_feedback`).

## Models (from research)

- [ ] **`PerformanceImprovementPlan`** [PIP-, `TenantNumbered`] — the corrective-action plan header.
  - `subject` = FK `hrm.EmployeeProfile` (`on_delete=PROTECT`, `related_name="pips_as_subject"`) —
    the employee on the plan (driver: PerformYard/Culture Amp basic-details section)
  - `manager` = FK `hrm.EmployeeProfile` (`on_delete=PROTECT`, `related_name="pips_as_manager"`) —
    who owns/drives it (usually the direct manager, may differ from `subject.manager` if escalated
    — so store it explicitly, don't derive it) (driver: PerformYard basic-details "manager" field)
  - `triggering_review` = nullable FK `hrm.PerformanceReview` (`on_delete=SET_NULL`,
    `related_name="triggered_pips"`) — optional link back to the 3.19 review that prompted this
    (driver: SAP SuccessFactors rating-trigger + Jackson Lewis' "cites the employee's prior annual
    review findings" legal framing)
  - `status` CharField choices (driver: Lattice/PerformYard "HR must sign off before the employee
    sees it" must-have): `draft` / `pending_hr_approval` / `active` / `closed` — default `"draft"`
  - `outcome` CharField choices, **blank while open** (driver: Culture Amp's 3-way outcome model +
    SAP/Jackson-Lewis termination-endpoint framing): `` / `successful` / `extended` / `failed` /
    `terminated` — blank default; only settable via the close-with-outcome action, never hand-typed
    on the create/edit form while `status != "closed"`
  - `outcome_date` (DateField, null/blank), `outcome_notes` (TextField, blank) — set together with
    `outcome` by the close action
  - `performance_issue` (TextField) — the specific gap, not vague criticism (driver: Jackson Lewis'
    "must appear corrective, not punitive" / legal-defensibility standard)
  - `expected_standards` (TextField) (driver: Culture Amp's structural checklist)
  - `improvement_goals` (TextField) — the SMART expectations (driver: PeopleGoal/Culture Amp "SMART
    improvement goals" must-have)
  - `support_provided` (TextField, blank) — training/coaching/resources the ORG commits to, the
    "not punitive" defensibility framing (driver: Culture Amp, Jackson Lewis)
  - `measurement_criteria` (TextField) — how success is judged (driver: PerformYard/Culture Amp
    section breakdown)
  - `start_date` (DateField), `end_date` (DateField) — the 30/60/90-day window (driver: near-
    universal timeline finding across Culture Amp/AIHR/general PIP literature)
  - `extended_end_date` (DateField, null/blank) — the extension path (driver: Lattice "timeline
    adjustments" + Culture Amp's distinct "extended" outcome)
  - `acknowledged_at` (DateTimeField, null/blank, `editable=False`), `acknowledged_by` (FK
    `hrm.EmployeeProfile`, `on_delete=SET_NULL`, null/blank, `editable=False`,
    `related_name="pips_acknowledged"`) — mirrors `PerformanceReview.acknowledged_at`/
    `acknowledged_by` FIELD-FOR-FIELD (driver: Lattice "employee acknowledgment logs" + PerformYard
    "sign-off and acknowledgment workflows")
  - `hr_approved_at` (DateTimeField, null/blank, `editable=False`), `hr_approved_by` (FK
    `hrm.EmployeeProfile`, `on_delete=SET_NULL`, null/blank, `editable=False`,
    `related_name="pips_hr_approved"`) — the approval-workflow gate (driver: Lattice/PerformYard
    HR-sign-off-before-employee-sees-it must-have)
  - `Meta.ordering = ["-start_date", "number"]`; `unique_together = ("tenant", "number")`; indexes
    on `(tenant, status)`, `(tenant, subject)`, `(tenant, manager)`
  - `clean()`: `subject_id != manager_id` (can't manage your own PIP); `outcome` set only when
    `status == "closed"` (and vice versa — a closed PIP must have an outcome); `end_date > start_date`;
    `extended_end_date`, if set, `> end_date`
  - `__str__`: `f"{self.number} · {self.subject.party.name}"`
  - Reuses `hrm.EmployeeProfile` (no new employee table), `hrm.PerformanceReview` (optional link).
    No new core-spine entity.

- [ ] **`PIPCheckIn`** [PCI-, `TenantNumbered`, child of the PIP] — the scheduled review-checkpoint
  row (mirrors the `ReviewRating`->`PerformanceReview` / `MeetingActionItem`->`OneOnOneMeeting`
  child-row pattern already established in 3.19/3.20).
  - `pip` = FK `PerformanceImprovementPlan` (`on_delete=CASCADE`, `related_name="checkins"`)
  - `checkin_date` (DateField) — the scheduled/actual date (driver: PerformYard's automated
    check-in scheduling + Culture Amp's bi-weekly worked example)
  - `completed_at` (DateTimeField, null/blank, `editable=False`) — actually held vs. just scheduled
    (mirrors `OneOnOneMeeting.completed_at`)
  - `progress_notes` (TextField, blank) — the shared narrative (driver: PerformYard's dual manager+
    employee status-update prompt model)
  - `progress_rating` CharField choices (driver: HR Acuity "guided check-ins" + mirrors
    `Feedback`-adjacent confidence framing / `GoalCheckIn.confidence`): `on_track` / `at_risk` /
    `off_track` — default `"on_track"`
  - `Meta.ordering = ["pip", "checkin_date"]`; `unique_together = ("tenant", "number")`; index on
    `(tenant, pip)`
  - No independent confidentiality gate — inherits the parent PIP's visible-to-subject/manager/
    admin set (view layer checks `_can_view_pip(request, checkin.pip)`)
  - `__str__`: `f"{self.number} · {self.pip.number} ({self.checkin_date})"`

- [ ] **`WarningLetter`** [WRN-, `TenantNumbered`] — the progressive-discipline document.
  - `issued_to` = FK `hrm.EmployeeProfile` (`on_delete=PROTECT`, `related_name="warnings_received"`)
  - `issued_by` = FK `hrm.EmployeeProfile` (`on_delete=PROTECT`, `related_name="warnings_issued"`)
  - `level` CharField choices (driver: AIHR's canonical 4-stage ladder, echoed identically by
    Darwinbox/Keka/general HR-policy sources): `verbal` / `written` / `final` / `suspension` —
    default `"verbal"` (termination itself stays OUT of scope — that's `SeparationCase`, 3.9
    offboarding, already built)
  - `category` CharField choices (driver: AIHR/Darwinbox/Keka's attendance/misconduct/negligence/
    dress-code template categories, folded to 4): `attendance` / `conduct` / `performance` /
    `policy_violation` — default `"conduct"`
  - `incident_date` (DateField)
  - `description` (TextField) — specific behaviors/actions, per the legal-defensibility requirement
    (driver: AIHR/Jackson Lewis/Keka — vague criticism explicitly called out as insufficient)
  - `policy_reference` (CharField, max_length=255, blank) — which policy/handbook section was
    violated (driver: Keka's per-category templates)
  - `related_pip` = nullable FK `PerformanceImprovementPlan` (`on_delete=SET_NULL`,
    `related_name="warning_letters"`) — a warning can stand alone (a single conduct incident) or
    escalate out of an active PIP (driver: general disciplinary literature — PIP is performance,
    warning letter can also be conduct)
  - `status` CharField choices (driver: universal employee-acknowledgment requirement): `draft` /
    `issued` / `acknowledged` / `expired` — default `"draft"`
  - `acknowledged_at` (DateTimeField, null/blank, `editable=False`), `acknowledged_by` (FK
    `hrm.EmployeeProfile`, `on_delete=SET_NULL`, null/blank, `editable=False`,
    `related_name="warnings_acknowledged"`) — mirrors the PIP/Review pattern
  - `employee_response` (TextField, blank) — the employee's optional written comment/rebuttal
    (driver: AIHR "allowing the employee to explain themself")
  - `expiry_date` (DateField, null/blank) — company-policy-dependent staleness window (driver:
    general progressive-discipline literature — no universal duration found, so tenant-set)
  - `Meta.ordering = ["-incident_date", "number"]`; `unique_together = ("tenant", "number")`;
    indexes on `(tenant, issued_to)`, `(tenant, level)`, `(tenant, status)`
  - `clean()`: `issued_to_id != issued_by_id`; `acknowledged_at`/`acknowledged_by` only meaningful
    once `status in ("acknowledged",)`; `expiry_date`, if set, `> incident_date`
  - `@property is_expired` — derived: `bool(self.expiry_date and self.expiry_date < timezone.localdate())`
    (a computed property reading the field, never a stored flag — mirrors `MeetingActionItem.is_overdue`)
  - `@property prior_warnings` — derived query, NOT a stored self-FK (per the research's explicit
    deferral): `WarningLetter.objects.filter(tenant=self.tenant_id, issued_to_id=self.issued_to_id,
    incident_date__lt=self.incident_date).order_by("-incident_date")` — cheap to compute, avoids a
    self-referential FK for a fully-derivable value
  - `__str__`: `f"{self.number} · {self.issued_to.party.name} ({self.get_level_display()})"`
  - Reuses `hrm.EmployeeProfile`. No new core-spine entity.

- [ ] **`CoachingNote`** [CN-, `TenantNumbered`] — the manager's private coaching log ("manager
  journal" pattern). **THE STRICTEST CONFIDENTIALITY MODEL IN THE WHOLE CLUSTER.**
  - `employee` = FK `hrm.EmployeeProfile` (`on_delete=PROTECT`, `related_name="coaching_notes_about"`)
    — the coached party
  - `coach` = FK `hrm.EmployeeProfile` (`on_delete=PROTECT`, `related_name="coaching_notes_authored"`)
    — almost always the manager, named generically since a skip-level/HRBP could also coach
  - `related_pip` = nullable FK `PerformanceImprovementPlan` (`on_delete=SET_NULL`,
    `related_name="coaching_notes"`) — this touchpoint fulfills the PIP's support-and-resources
    commitment; optional, most notes will be standalone day-to-day observations
  - `note_date` (DateField, default `timezone.localdate`) — when the coaching moment happened (may
    differ from `created_at`)
  - `category` CharField choices (driver: general coaching-software theme tagging, kept as a small
    enum not a catalog — cheap field per the research): `skill_development` / `behavior` /
    `career_growth` / `other` — default `"other"`
  - `content` (TextField) — the observation/coaching log itself
  - `Meta.ordering = ["-note_date", "-created_at"]`; `unique_together = ("tenant", "number")`;
    indexes on `(tenant, employee)`, `(tenant, coach)`
  - `clean()`: `employee_id != coach_id` (can't coach yourself)
  - `__str__`: `f"{self.number} · {self.coach.party.name} -> {self.employee.party.name}"`
  - **CONFIDENTIALITY: visible ONLY to `coach` (the author) + tenant admin — NEVER to `employee`
    (the coached subject), at NO lifecycle stage.** This is a whole-model-level clone of
    `OneOnOneMeeting.manager_private_notes`'s read-gate, not a field-level mask — the entire
    list/detail/edit surface excludes the subject. No status/workflow field needed (simple CRUD,
    coach + admin only).
  - Reuses `hrm.EmployeeProfile`. No new core-spine entity.

All four FK `hrm.EmployeeProfile` by string (never a new employee table). `PIPCheckIn` is the only
child row. No new core-spine entity; nothing posts to the GL — consistent with 3.18/3.19/3.20.

## Confidentiality rules (explicit — carry through backend + templates)

- [ ] `_can_view_pip(request, pip)` — admin, OR `profile.pk in (pip.subject_id, pip.manager_id)`.
  **No team/public tier** — mirrors `_can_view_review` exactly, NOT the 3.20 Feedback
  public/team/private 3-tier model.
- [ ] `_visible_pips_q(request)` — `None` for admin (no restriction); else
  `Q(subject=profile) | Q(manager=profile)`; `Q(pk__in=[])` when `profile is None` — mirrors
  `_visible_reviews_q` exactly (same signature, same `None`-for-admin contract).
- [ ] `_can_edit_pip(request, pip)` — editable ONLY by the manager or admin, and ONLY while
  `status == "draft"` (content locks once submitted for HR approval) — mirrors `_can_edit_review`'s
  `status == "draft"` + author/admin shape. The subject is NEVER an editor (mirrors "the subject
  must never reach the edit form" from `_can_edit_review`'s docstring).
- [ ] `pip_hr_approve` (draft/pending_hr_approval -> active, sets `hr_approved_at`/`hr_approved_by`)
  is `@tenant_admin_required` + `@require_POST` — workflow-owned, off the form, mirrors
  `reviewcycle_advance_phase`.
- [ ] `pip_acknowledge` — subject-only (+ admin) `@require_POST` action; sets `acknowledged_at`/
  `acknowledged_by`; only reachable once `status == "active"`.
- [ ] `pip_close` (sets `status="closed"` + `outcome`/`outcome_date`/`outcome_notes` from a small
  outcome form) is `@tenant_admin_required` + `@require_POST` — workflow-owned, mirrors
  `reviewcycle_advance_phase`. Guard: only from `status == "active"`.
- [ ] `pip_extend` (sets `extended_end_date`, keeps `status="active"`) is `@tenant_admin_required` +
  `@require_POST` — same workflow-owned shape (manager-initiated extensions are a nice-to-have but
  keep the write path admin-gated for the audit trail this pass, matching the HR-approval framing).
- [ ] `_can_view_warning(request, letter)` — admin, OR `profile.pk in (letter.issued_to_id,
  letter.issued_by_id)`. Same subject-or-issuer-or-admin shape as the PIP gate — arguably even
  stricter (never "team-visible").
- [ ] `_visible_warnings_q(request)` — `None` for admin; else `Q(issued_to=profile) |
  Q(issued_by=profile)`; `Q(pk__in=[])` when `profile is None`.
- [ ] `_can_edit_warning(request, letter)` — editable ONLY by `issued_by` or admin, and ONLY while
  `status == "draft"` (locks once issued). The `issued_to` employee is NEVER an editor.
- [ ] `warningletter_issue` (`draft -> issued`) is `@tenant_admin_required` + `@require_POST` (mirrors
  the HR-sign-off framing — a manager drafts, HR/admin issues) OR relax to issuer-or-admin if the
  build finds that too strict for a single-issuer conduct note — **decide at build time, default to
  admin-gated for parity with the PIP approval workflow**.
- [ ] `warningletter_acknowledge` — `issued_to`-only (+ admin) `@require_POST` action; accepts an
  optional `employee_response` field in the same POST; sets `acknowledged_at`/`acknowledged_by`,
  `status="acknowledged"`.
- [ ] `_can_view_coaching(request, note)` — admin OR `profile.pk == note.coach_id` **ONLY**. The
  `employee` (coached subject) is explicitly EXCLUDED at every check — no exception, no lifecycle
  stage where they gain access. This is stricter than `_can_view_pip`/`_can_view_warning` (which
  both admit the subject) and stricter than `_can_manage_meeting` (which the 1:1 EMPLOYEE side can
  still partially view via `_can_view_meeting`, just not manage) — `CoachingNote` has NO
  employee-side view path at all.
- [ ] `_visible_coaching_q(request)` — `None` for admin; else `Q(coach=profile)` (NOT
  `Q(coach=profile) | Q(employee=profile)` — the employee leg is deliberately omitted); `Q(pk__in=[])`
  when `profile is None`.
- [ ] `_can_edit_coaching(request, note)` — `coach`-or-admin only, no status-lock needed (simple
  CRUD, no workflow states) but still gate on `_can_view_coaching` first (edit rights never broader
  than view rights, per the `_can_manage_action_item` lesson from 3.20).
- [ ] `coachingnote_list`/`_detail`/`_create`/`_edit`/`_delete` ALL filter/guard through
  `_visible_coaching_q`/`_can_view_coaching` — the list page for a non-coach, non-admin user must
  show ZERO rows about themselves (verify this explicitly in the smoke sweep: log in as the
  `employee` on a seeded coaching note and confirm `coachingnote_list` and `coachingnote_detail`
  both exclude/404 it).
- [ ] `CoachingNoteForm.employee`/`.coach` dropdowns scoped to `tenant` (mirrors `FeedbackForm`'s
  `receiver`/`badge` queryset-scoping lesson from 3.20) — and consider whether `coach` should default
  to `_current_employee_profile(request)` server-side (like `Feedback.giver`) rather than being a
  free form field, so a user can't coach-note as someone else. **Recommend: `coach` is NOT a form
  field — resolved server-side in the view from `request.user`, same pattern as
  `GoalCheckIn.created_by`/`Feedback.giver`.**
- [ ] Redaction: the shared `apps/core/crud.py::_SENSITIVE_AUDIT_FIELDS` frozenset already covers
  `private_notes`/`manager_private_notes` by exact field name. `CoachingNote.content` and
  `WarningLetter.description`/`incident_description`-style fields do NOT share those exact names, so
  they are NOT auto-redacted. **Decision point (keep narrow, don't over-scope per the research's
  Guardrails):** do NOT add `content` to `_SENSITIVE_AUDIT_FIELDS` this pass — a coaching note's
  existence + author + date in the audit log is fine to retain (only the *field value* would leak,
  and audit changes are already admin-only); only add a field there if a build-time review finds a
  genuine plaintext-secret-style leak (there isn't one here — these are prose fields, not
  bank/token-style secrets). Note the decision in the model docstring so a future reviewer doesn't
  re-raise it as a gap.

## Backend (apps/hrm/)

- [ ] **models.py** — add `PerformanceImprovementPlan`, `PIPCheckIn`, `WarningLetter`,
  `CoachingNote` after the 3.20 `MeetingActionItem` class (~line 5698), with a section-header
  docstring comment block mirroring the 3.19/3.20 preamble (states this is the 4th/FINAL
  Performance-Management sub-module, lists what's reused, states the confidentiality precedent
  being cloned). All 4 classes `TenantNumbered`. `NUMBER_PREFIX` = `"PIP"` / `"PCI"` / `"WRN"` /
  `"CN"` respectively.
- [ ] **forms.py** — `PerformanceImprovementPlanForm` (exclude `tenant`, `number`, `status`,
  `outcome`, `outcome_date`, `outcome_notes`, `acknowledged_at`, `acknowledged_by`, `hr_approved_at`,
  `hr_approved_by` — all workflow/derived; scope `subject`/`manager`/`triggering_review` querysets
  to `tenant`), `PIPCheckInForm` (exclude `tenant`, `number`, `completed_at`; `pip` set from the URL
  in the view, not form-typed — mirrors how `key_result`/`meeting` are handled for
  `GoalCheckInForm`/`MeetingActionItemForm`), `WarningLetterForm` (exclude `tenant`, `number`,
  `status`, `acknowledged_at`, `acknowledged_by`, `employee_response` [captured only via the
  acknowledge action's own small form/field, not the main edit form] — scope `issued_to`/
  `issued_by`/`related_pip` querysets to `tenant`), `CoachingNoteForm` (exclude `tenant`, `number`,
  `coach` [resolved server-side from `request.user`, NEVER form-typed — see confidentiality rules
  above]; scope `employee`/`related_pip` querysets to `tenant`). A small `PIPCloseForm`
  (`outcome`, `outcome_date`, `outcome_notes`) and a small `WarningAcknowledgeForm`
  (`employee_response` only) for the two workflow actions that need extra input beyond a bare POST.
- [ ] **views.py** — function-based, `@login_required`, tenant-scoped throughout:
  - `pip_list` (search: `number`, `subject__party__name`, `manager__party__name`; filters: `status`,
    `outcome`, `subject`, `manager`; apply `_visible_pips_q` before pagination; `extra_context`:
    `status_choices`, `outcome_choices=PerformanceImprovementPlan.OUTCOME_CHOICES`, `employees`
    queryset, `is_admin`, `current_profile_id`)
  - `pip_create`, `pip_detail` (raise `PermissionDenied` via `_can_view_pip`; prefetch `checkins`;
    show HR-approve/acknowledge/close/extend buttons conditionally per status + role), `pip_edit`
    (gated by `_can_edit_pip`), `pip_delete` (POST-only; pre-check for child `checkins`/related
    `WarningLetter`/`CoachingNote` rows since those are SET_NULL — safe to delete, but message the
    user that links will be cleared, OR simply allow since SET_NULL is non-blocking)
  - `pip_hr_approve`, `pip_acknowledge`, `pip_close`, `pip_extend` — the 4 workflow actions per the
    Confidentiality rules section above
  - `pipcheckin_create` (nested under a PIP, `pip_id` from URL kwarg, gated by `_can_view_pip` on
    the parent — only subject/manager/admin add a check-in), `pipcheckin_detail`, `_edit`, `_delete`
    (all re-derive the parent PIP's visibility, never an independent gate)
  - `warningletter_list` (search: `number`, `issued_to__party__name`; filters: `level`, `category`,
    `status`, `issued_to`; apply `_visible_warnings_q`), `warningletter_create`, `_detail` (gated by
    `_can_view_warning`; shows `prior_warnings` property + a "print letter" link), `_edit` (gated by
    `_can_edit_warning`), `_delete`
  - `warningletter_issue`, `warningletter_acknowledge` — the 2 workflow actions
  - `warningletter_print` (standalone printable view, `GET`-only, gated by `_can_view_warning`,
    template at `hrm/performance/warningletter/print.html` — mirrors
    `hrm/offboarding/relieving_letter.html`'s existing pattern)
  - `coachingnote_list` (search: `number`, `content`; filters: `category`, `employee`; apply
    `_visible_coaching_q` — **not** `_can_view_coaching` per-row since the list is already
    pre-filtered), `coachingnote_create` (resolves `coach = _current_employee_profile(request)`
    server-side, mirrors `feedback_create`'s `giver` resolution), `coachingnote_detail` (raise
    `PermissionDenied` via `_can_view_coaching`), `coachingnote_edit` (gated by
    `_can_edit_coaching`), `coachingnote_delete`
  - All list views follow the Filter Implementation Rules (CLAUDE.md): view passes every
    `*_choices`/queryset the template needs; string-field comparisons use `request.GET.status ==
    value`; FK/pk comparisons use `|stringformat:"d"`.
- [ ] **urls.py** — `app_name = "hrm"` (already set); add under a `# 3.21 Performance Improvement`
  comment block: `pip_list`, `pip_create`, `pip_detail`, `pip_edit`, `pip_delete`,
  `pip_hr_approve`, `pip_acknowledge`, `pip_close`, `pip_extend`, `pipcheckin_create`,
  `pipcheckin_detail`, `pipcheckin_edit`, `pipcheckin_delete`, `warningletter_list`,
  `warningletter_create`, `warningletter_detail`, `warningletter_edit`, `warningletter_delete`,
  `warningletter_issue`, `warningletter_acknowledge`, `warningletter_print`, `coachingnote_list`,
  `coachingnote_create`, `coachingnote_detail`, `coachingnote_edit`, `coachingnote_delete`.
- [ ] **admin.py** — register all 4 models (`PerformanceImprovementPlanAdmin`, `PIPCheckInAdmin`,
  `WarningLetterAdmin`, `CoachingNoteAdmin`) with `list_display`/`list_filter`/`search_fields`
  mirroring the existing 3.19/3.20 admin registrations (tenant, number, status/level where
  applicable). **`CoachingNoteAdmin` note:** Django admin bypasses the view-layer confidentiality
  gate by design (superuser-only surface) — no extra gating needed there, but do NOT expose
  `CoachingNote` via any non-admin, non-gated path.
- [ ] **migrations** — `makemigrations hrm` (expect `0036_performanceimprovementplan_pipcheckin_...`
  incrementing from 0035; add any follow-up `alter_*` migrations the same way 0031/0032/0035 did for
  prior sub-modules if a field tweak surfaces during build).
- [ ] **seed_hrm.py** — new `_seed_improvement(self, tenant, *, flush)` method:
  - Called from `handle()` immediately after `self._seed_feedback(tenant, flush=options["flush"])`
    (the 5th and final call in the per-tenant loop for the Performance-Management cluster).
  - `if flush:` delete in child-first order: `CoachingNote`, `WarningLetter`, `PIPCheckIn`,
    `PerformanceImprovementPlan` — filtered by `tenant`.
  - Idempotency guard: `if PerformanceImprovementPlan.objects.filter(tenant=tenant).exists() or
    WarningLetter.objects.filter(tenant=tenant).exists():` -> NOTICE + return.
  - Reuse EXISTING `EmployeeProfile` rows (`EmployeeProfile.objects.filter(tenant=tenant)
    .select_related("party", "employment").order_by("party__name")`) — same `len(emps) < N` guard
    style as `_seed_feedback` (need >= 3 distinct people for subject/manager/coach variety).
  - Reuse an existing 3.19 `PerformanceReview` row for `triggering_review`
    (`PerformanceReview.objects.filter(tenant=tenant).order_by("number").first()`).
  - Demo data: 2 PIPs — one `active` with 2 `PIPCheckIn` rows (one `on_track`, one `at_risk`), one
    `closed` with `outcome="successful"`; 2-3 `WarningLetter` rows spanning at least 2 `level`
    values (e.g. one `verbal`/`acknowledged`, one `written`/`issued`, optionally one `related_pip`-
    linked); 2 `CoachingNote` rows (at least one `related_pip`-linked, one standalone).
  - **CRITICAL — Windows cp1252 console bug (repeat of the 3.20 seeder bug):** NO non-cp1252
    characters (no `→`, `↔`, em-dash arrows, etc.) in ANY `self.stdout.write(...)` string — use
    plain ASCII `->` if an arrow is needed. Verify by re-reading the whole method for stray Unicode
    before committing.
  - Update `_seed_tenant`'s big flush-teardown tuple: insert `CoachingNote, WarningLetter,
    PIPCheckIn, PerformanceImprovementPlan,` into the tuple **BEFORE** the 3.20 block (`
    MeetingActionItem, OneOnOneMeeting, Feedback, KudosBadge,`) since all 4 new models PROTECT
    `EmployeeProfile` and must be wiped ahead of it — add a one-line comment explaining the PROTECT
    ordering, matching the style of the existing 3.18/3.19/3.20 comments in that block.
  - Both `management/__init__.py` and `management/commands/__init__.py` already exist (no new dirs
    this pass) — verify, don't recreate.

## Wire-up

- [ ] `config/settings.py` — `apps.hrm` already in `INSTALLED_APPS` (no change needed this pass).
- [ ] `config/urls.py` — `hrm/` include already wired (no change needed this pass).
- [ ] `apps/core/navigation.py` `LIVE_LINKS["3.21"]` — new block mapping the 3 exact NavERP.md 3.21
  bullets (confirmed verbatim from NavERP.md lines 582-585):
  ```python
  "3.21": {
      "PIP Management": "hrm:pip_list",                # bullet (PerformanceImprovementPlan CRUD + workflow)
      "Warning Letters": "hrm:warningletter_list",      # bullet (WarningLetter CRUD + issue/acknowledge/print)
      "Coaching Notes": "hrm:coachingnote_list",        # bullet (CoachingNote — coach/admin only)
  },
  ```
  placed immediately after the existing `"3.20"` block (before the `"3.5"` Job Requisition block),
  with a preamble comment mirroring the 3.18/3.19/3.20 comment style — noting this is the 4th/FINAL
  Performance-Management sub-module and that Coaching Notes intentionally has no
  employee-facing view.

## Templates (templates/hrm/performance/)

- [ ] **Use the SHARED `performance/` folder** — 3.18/3.19/3.20 all live there; do NOT create a new
  `improvement/` folder (per the Template Folder Structure rule — the sub-module folder is
  `performance/` for all 4 Performance-Management sub-modules, one entity folder each).
- [ ] `templates/hrm/performance/pip/list.html` — filter bar (`status`, `outcome`, `subject`,
  `manager` dropdowns reflecting `request.GET`), Actions column (view/edit-if-`_can_edit_pip`/
  delete-POST+confirm+csrf), pagination, empty-state. Row visibility already server-filtered by
  `_visible_pips_q` — no extra client-side hiding needed.
- [ ] `templates/hrm/performance/pip/detail.html` — the 5 structured TextField sections rendered
  read-only; check-ins sub-list (via `obj.checkins.all`, prefetched); HR-approve/acknowledge/
  close/extend buttons conditional on `status` + `is_admin`/subject/manager role (mirror
  `reviewcycle_detail`'s Advance-button conditional pattern); Actions sidebar (Edit conditional on
  `_can_edit_pip`, Delete, Back to List).
- [ ] `templates/hrm/performance/pip/form.html` — create/edit (shared template, `is_edit` flag).
- [ ] `templates/hrm/performance/pipcheckin/list.html`, `/detail.html`, `/form.html` — nested under
  the parent PIP (form pre-fills `pip` from URL, not a dropdown — mirrors `MeetingActionItem`'s
  meeting-scoped creation).
- [ ] `templates/hrm/performance/warningletter/list.html` — filter bar (`level`, `category`,
  `status`, `issued_to`), Actions column.
- [ ] `templates/hrm/performance/warningletter/detail.html` — incident section, `prior_warnings`
  property rendered as a mini-list (escalation context), issue/acknowledge buttons, a "Print Letter"
  link, `employee_response` shown once populated, Actions sidebar.
- [ ] `templates/hrm/performance/warningletter/form.html` — create/edit.
- [ ] `templates/hrm/performance/warningletter/print.html` — standalone printable letter (page =
  secondary entity-action, sits inside the `warningletter/` entity folder per the Template Folder
  Structure rule §5 — mirrors `hrm/offboarding/relieving_letter.html`'s pattern, though that one is
  a standalone sub-module-root page since offboarding is single-entity; here `warningletter/` is one
  entity among 4 so the print page nests inside its own entity folder). Letter-formatted layout
  (tenant letterhead area, employee/date/level/category, incident description, policy reference,
  signature lines) — print-friendly CSS (`@media print`).
- [ ] `templates/hrm/performance/coachingnote/list.html` — filter bar (`category`, `employee` —
  note the employee filter here lets the COACH filter their own notes by who they coached, it does
  NOT let the coached employee find notes about themselves, since the queryset is already
  `_visible_coaching_q`-scoped to `coach=profile` before any GET filter is applied), Actions column.
  **No "view as employee" affordance anywhere on this page.**
- [ ] `templates/hrm/performance/coachingnote/detail.html`, `/form.html` — simple CRUD, coach/admin
  only (view raises `PermissionDenied` otherwise — confirm the template itself never renders if the
  view already 403s, so this is a view-layer guarantee, not a template-layer one).
- [ ] No template renders `hr_approved_by`/`acknowledged_by`/private fields to a viewer who
  shouldn't see them yet — audit each template against the confidentiality rules above before
  marking this section done.

## Verify

- [ ] `python manage.py makemigrations hrm` — review the generated migration file name/number
  before applying (expect `0036_...`).
- [ ] `python manage.py migrate`
- [ ] `python manage.py seed_hrm` — run twice; second run must be a no-op (NOTICE message, zero new
  rows) proving idempotency.
- [ ] `python manage.py check` — zero errors/warnings.
- [ ] `temp/` smoke sweep — all `hrm:pip_*`, `hrm:pipcheckin_*`, `hrm:warningletter_*`,
  `hrm:coachingnote_*` URLs return 200/302 (never 500); no `{#`/`{% comment` template-comment leaks
  in rendered output; cross-tenant IDOR check (a tenant-B admin hitting a tenant-A PIP/warning/
  coaching-note pk returns 404, not the object); **explicit CoachingNote confidentiality check** —
  log in as the seeded `employee` (coached subject, NOT the coach) on a seeded `CoachingNote` and
  confirm `coachingnote_list` shows 0 of their own notes and `coachingnote_detail` on that note's pk
  returns 403/`PermissionDenied` (not a silent redirect that could look like a bug vs. a gate);
  same spot-check for a PIP `subject` hitting `pip_hr_approve`/`pip_close` directly (must be
  blocked — those are `@tenant_admin_required`).
- [ ] Sidebar shows all 3 new 3.21 sub-module bullets as **Live** (PIP Management, Warning Letters,
  Coaching Notes) — confirm via the rendered sidebar, not just the `LIVE_LINKS` dict.

## Close-out

- [ ] Run the 7 review agents in order, applying findings + committing after each (one file per
  commit, no `git push`): `code-reviewer` -> `explorer` -> `frontend-reviewer` ->
  `performance-reviewer` -> `qa-smoke-tester` -> `security-reviewer` -> `test-writer`.
  - Expect `security-reviewer` to specifically probe the `CoachingNote` subject-exclusion gate and
    the `pip_hr_approve`/`pip_close`/`warningletter_issue` admin-gating — these are the highest-risk
    surfaces in this sub-module (mirrors how 3.20's security pass caught the `manager_private_notes`
    read-gate + `_can_manage_action_item` participant-check regression).
  - Expect `test-writer` to cover: full CRUD round-trips x4 models; the PIP workflow chain (draft ->
    pending_hr_approval -> active -> closed, plus the extend path); the WarningLetter issue/
    acknowledge chain incl. `employee_response`; the `prior_warnings` derived-query correctness;
    `CoachingNote`'s subject-exclusion (both list-filtering AND detail-403) as its own dedicated
    security-test block, same weight 3.20 gave the anonymous-giver-masking tests.
- [ ] Update `.claude/skills/hrm/SKILL.md`:
  - Add a `### 3.21 Performance Improvement (4 tables)` section (mirrors the existing 3.18/3.19/3.20
    section format) with the model table (fields, FK targets, confidentiality note per model).
  - Bump the frontmatter/overview "built" sub-module list to include 3.21 and note **the
    Performance-Management cluster (3.18-3.21) is now COMPLETE** (4 of 4 sub-modules shipped) —
    the next HRM pass moves to 3.22 Training Management, a different domain.
  - Extend the "Continuous Feedback (3.20)" routes-list section style with a new "Performance
    Improvement (3.21)" routes bullet list (`hrm:pip_*`, `hrm:warningletter_*`,
    `hrm:coachingnote_*` incl. the workflow actions and `warningletter_print`).
  - Update the seeder section: document `_seed_improvement(tenant)`, its own-exists guard, what it
    creates, and that it runs LAST after `_seed_feedback`.
  - Update the `LIVE_LINKS` section: "3.21: PIP Management -> `hrm:pip_list`; Warning Letters ->
    `hrm:warningletter_list`; Coaching Notes -> `hrm:coachingnote_list`. All 3 NavERP.md 3.21
    bullets are now live." — mirror the exact phrasing style of the 3.19/3.20 lines already there.
  - Update the "Deferred" section (near line 872, which already lists "PIP/warning-letters/coaching
    (3.21; 3.18 Goal Setting + 3.19 Performance Review + 3.20 Continuous Feedback are **built**)")
    to move 3.21 OFF the deferred list and add the sub-module's own carried-forward deferrals (see
    below) — this is now the correct place for them, not the old placeholder line.
  - Commit the SKILL.md update as its own file, per the one-file-per-commit rule.
- [ ] README (if the project keeps a root test-count/module-count summary) — refresh HRM test
  counts after `test-writer` runs, same pattern as the 3.20 README refresh commit.

## Later passes / deferred (carried over from research-hrm-performance-improvement.md)

- **`PIPTemplate` catalog** (admin-customizable PIP form templates, mirrors `hrm.ReviewTemplate`) —
  v1 ships one flexible model with free-text sections; a template layer is additive later.
- **Auto-creating a `SeparationCase` (3.9 offboarding) on a `terminated` PIP/warning outcome** —
  cross-sub-module automation; this pass only sets the `outcome` flag manually.
- **Analytics/trend dashboard across PIPs and warnings** (Lattice's "surface trends individual
  plans can't show") — a computed view once there's enough data volume; candidate for the BI
  module (10) or a later HRM analytics pass.
- **Investigation-workflow state** (Darwinbox's identify->investigate->communicate->act->follow-up
  5-step framework) — folded into `draft` status + free-text `description` for v1.
- **Warning-letter self-FK escalation chain** (`prior_warning` pointer) — deferred in favor of the
  `prior_warnings` derived-query property already specified above.
- **Wiring `CoachingNote` retrieval into the `PerformanceReview` create/edit form** (the "manager
  journal" UX of pulling notes up while writing a review) — the notes exist and are queryable by
  employee this pass; inline surfacing in the 3.19 review form is a follow-on.
- **PIP support-and-resources structured sub-table** (a catalog of "training assigned"/"1:1 cadence"
  rows instead of free text) — `support_provided` ships as text this pass.
- **Letter e-signature / external delivery integration** (DocuSign-style) — the `acknowledged_at`/
  `acknowledged_by` fields capture in-app acknowledgment only this pass.
- **Workday-specific PIP/corrective-action feature detail** — no Workday product page was found
  describing a distinct native PIP feature; flagged as a research gap, not invented.

## Review notes

**Built 3.21 Performance Improvement end-to-end (2026-07-07) — the FINAL Performance-Management sub-module.**
4 models as planned: `PerformanceImprovementPlan` [PIP-], `PIPCheckIn` [PCI-] child, `WarningLetter` [WRN-],
`CoachingNote` [CN-] — migration `0036`; 13 templates under the shared `templates/hrm/performance/` (incl. a
standalone printable warning letter); `LIVE_LINKS["3.21"]`; `_seed_improvement` idempotent (both tenants, in the
central flush teardown before `EmployeeProfile`). Confidentiality was the crux — PIPs/warnings are subject/issuer/
admin-only; **CoachingNote is the strictest gate in the system** (coach/admin only; the coached employee never sees
notes about themselves).

**All 7 review agents applied:**
- **code-reviewer** — 1 Important (the PIP subject could edit/delete a manager check-in + no closed-plan guard →
  added `_can_edit_checkin` [manager/admin, not-closed] + a create guard) + minors (missing manager-filter widget,
  admin-empty cross-link dropdowns → `viewer_is_admin`).
- **explorer** — clean wiring; 1 consistency fix (`warningletter_detail` `is_admin` via context).
- **frontend-reviewer** — 2 Important (2 stale interspersed admin-checks the earlier replace_all missed; ungated
  standalone check-in detail Edit/Delete) + accessibility (extend-input aria-label, ack-textarea label, extend confirm).
- **performance-reviewer** — clean (no N+1, all indexes present, `prior_warnings` DB-limited); 1 dead-JOIN trim.
- **qa-smoke-tester** — 56/56 checks green; verified the CoachingNote subject-exclusion (0 rows + 403), the PIP
  subject blocked from approve/close, and the check-in-tamper block byte-for-byte on real HTTP.
- **security-reviewer** — no Critical/High/Medium; 1 Low (disciplinary prose in the audit log) **declined** — the
  suggested field names (`content`/`description`) are generic and would over-redact unrelated models app-wide, and
  audit reads are already admin-only.
- **test-writer** — **288 tests** (75 model + 132 view + 77 security + 4 query), all green; **HRM 3,838 /
  project-wide 6,485**, both suites exit 0. No product bugs surfaced. (The first run's process was lost mid-run; the
  models file + conftest were committed, then a second run finished views/security/queries.)

**Performance Management (3.18 Goal Setting → 3.19 Performance Review → 3.20 Continuous Feedback → 3.21 Performance
Improvement) is now COMPLETE.** A parallel session has started **3.22 Training Management** (its models/admin/nav are
already committed on `main`). **Next: 3.22 (in progress elsewhere), then 3.23+.**

---
# Module 3 — HRM — Sub-module 3.22 Training Management (hrm-3.22-training-management) — plan from research-hrm-3.22-training-management.md (2026-07-08)

**EXTENDS the existing `apps/hrm` app (already built through 3.21) — no new Django app, no new
`INSTALLED_APPS`/`config/urls.py` entries.** This pass covers ONLY the 5 NavERP.md 3.22 bullets
(Training Calendar / Training Catalog / Classroom Training / Virtual Training / External Training).
Sibling sub-modules **3.23 Learning Management (LMS)** and **3.24 Training Administration**
(nomination/attendance/feedback/certificates/budget) are explicitly OUT of scope — do not add
content-authoring, learning paths, assessments, gamification, progress tracking, nominations,
attendance capture, feedback forms, certificates, or budget rollups this pass.

Reuses (never duplicates): `hrm.EmployeeProfile` (internal instructor, by string FK — never a new
instructor/employee table), `core.Party` (external vendor, `PartyRole.role="vendor"` — reuse
`Party.objects.filter(tenant=tenant, roles__role="vendor").distinct()`, exactly the filter already
used in `apps/accounting/views.py:88` and `apps/accounting/forms.py:120,211` — do NOT create a new
HRM vendor-master table), `accounting.Currency` (global, no tenant FK — **lazy-import**
`from apps.accounting.models import Currency` inside the form `__init__`/view body, mirroring the
existing `PayrollRun`/`Project` lazy-import convention in `apps/hrm/views.py:6092` and
`apps/hrm/management/commands/seed_hrm.py:1344`, never a module-level import — keeps accounting a
runtime, not module-load, dependency). No new core-spine entity; nothing posts to the GL. Neither
model carries the 3.18–3.21 confidentiality machinery (`_can_view_*`/`_visible_*_q`) — Training data
is ordinary tenant-scoped CRUD, visible to every authenticated tenant user (no subject/manager-only
gate), same openness level as 3.2 Designation/JobGrade or 3.12 PublicHoliday.

## Models (from research)

- [ ] **`TrainingCourse`** [`TRC-`, `TenantNumbered`] — the catalog (Training Catalog bullet).
  - `title` (CharField, max_length=255), `description` (TextField, blank)
  - `category` — CharField choices, max_length=20, default `"technical"`: `technical` /
    `compliance` / `leadership` / `soft_skills` / `safety` / `onboarding` / `product` / `other`
    (driver: browsable/filterable catalog — TalentLMS, Arlo)
  - `delivery_mode` — CharField choices, max_length=15, default `"classroom"`: `classroom` /
    `virtual` / `external` / `blended` — the course's TYPICAL mode; the actual per-occurrence mode
    lives on `TrainingSession.delivery_mode` and can differ (driver: classroom/webinar choice —
    TalentLMS, Docebo)
  - `provider_type` — CharField choices, max_length=10, default `"internal"`: `internal` /
    `external` (driver: internal vs. external catalog split — Absorb LMS, Training Orchestra)
  - `duration_hours` — DecimalField(max_digits=6, decimal_places=2, validators=[MinValueValidator(0)])
  - `is_certification` (BooleanField, default False), `certification_name` (CharField,
    max_length=255, blank), `certification_validity_months` (PositiveIntegerField, null/blank)
    (driver: certifications tied to a course — SAP SuccessFactors Learning, Workday)
  - `prerequisite_course` — self-FK (`"self"`), `on_delete=SET_NULL`, null/blank,
    `related_name="unlocks"` (driver: prerequisites — SAP SuccessFactors Learning)
  - `default_capacity` — PositiveIntegerField, null/blank (seeds new sessions; no auto-copy logic
    required this pass — a nice-to-have form/JS pre-fill, not mandatory) (driver: enrollment limits
    — SAP SuccessFactors Learning)
  - `is_active` (BooleanField, default True)
  - `Meta.ordering = ["title"]`; `unique_together = ("tenant", "number")`; indexes on
    `(tenant, category)` (name `hrm_trc_tenant_category_idx`), `(tenant, is_active)`
    (`hrm_trc_tenant_active_idx`)
  - `clean()`: `is_certification` requires non-blank `certification_name`; `prerequisite_course`
    can't be the course itself (`self.pk and self.prerequisite_course_id == self.pk`)
  - `__str__`: `f"{self.number} · {self.title}"`
  - Reuses: nothing external besides tenant scoping — a new HRM-owned master (analogous to
    `Designation`/`PayComponent`, other HRM-owned catalogs).

- [ ] **`TrainingSession`** [`TRS-`, `TenantNumbered`] — the scheduled occurrence (Training
  Calendar + Classroom + Virtual + External bullets, unified via `delivery_mode`).
  - `course` — FK `hrm.TrainingCourse`, `on_delete=PROTECT` (mirrors `SalaryStructureLine
    .pay_component` PROTECT-a-referenced-catalog-row house style — a course with scheduled sessions
    can't be deleted out from under them), `related_name="sessions"`
  - `delivery_mode` — CharField choices, max_length=10, default `"classroom"`: `classroom` /
    `virtual` / `external` (per-occurrence; NOTE narrower than the course's 4-choice set — no
    `blended` at the session level this pass) (driver: course→session→event hierarchy — Docebo, SAP
    SuccessFactors Learning)
  - `status` — CharField choices, max_length=15, default `"scheduled"`: `scheduled` / `confirmed` /
    `ongoing` / `completed` / `cancelled` / `postponed`
  - `start_datetime`, `end_datetime` (DateTimeField), `timezone` (CharField, max_length=50, default
    `"UTC"`)
  - `capacity` — PositiveIntegerField, default 20 (driver: seat limits — SAP SuccessFactors
    Learning), `waitlist_enabled` (BooleanField, default False) (driver: waitlist flag —
    SAP SuccessFactors Learning, Absorb LMS; the waitlist QUEUE workflow itself is a 3.24 Nomination
    concern — this pass ships the flag only)
  - Classroom fields: `venue_name` (CharField, max_length=255, blank), `venue_address` (TextField,
    blank) (driver: venue/room management — Absorb LMS, Arlo — no separate Venue master this pass)
  - Virtual fields: `meeting_platform` — CharField choices, max_length=15, blank: `zoom` / `teams` /
    `webex` / `google_meet` / `gotomeeting` / `other`; `meeting_link` (URLField, blank); `meeting_id`
    (CharField, max_length=100, blank) (driver: videoconferencing platform + join-link fields —
    Docebo, SAP Litmos, 360Learning, Zoho People)
  - Instructor: `instructor_employee` — FK `hrm.EmployeeProfile`, `on_delete=SET_NULL`, null/blank,
    `related_name="training_sessions_instructed"` (driver: instructor assignment — Cornerstone
    OnDemand, Arlo); `external_instructor_name` (CharField, max_length=255, blank — a named
    vendor-side trainer who isn't an `EmployeeProfile`)
  - External/vendor: `external_vendor` — FK `core.Party`, `on_delete=SET_NULL`, null/blank,
    `related_name="training_sessions_as_vendor"`, conceptually scoped to vendor-role parties (form
    queryset = `Party.objects.filter(tenant=tenant, roles__role="vendor").distinct()`, mirrors
    `accounting/forms.py`) (driver: vendor register + vendor-linked instructors — Training
    Orchestra, Cornerstone OnDemand)
  - Cost: `estimated_cost`, `actual_cost` — DecimalField(max_digits=12, decimal_places=2,
    null=True, blank=True); `currency` — FK `accounting.Currency` (string FK
    `"accounting.Currency"`), `on_delete=SET_NULL`, null/blank (global master, NOT tenant-scoped —
    lazy-import in the form, do not add `tenant` filtering to its queryset); `invoice_reference`
    (CharField, max_length=100, blank) (driver: per-session cost tracking, multi-currency —
    Training Orchestra, Arlo)
  - `notes` (TextField, blank)
  - `Meta.ordering = ["-start_datetime", "number"]`; `unique_together = ("tenant", "number")`;
    indexes on `(tenant, status)` (`hrm_trs_tenant_status_idx`), `(tenant, course)`
    (`hrm_trs_tenant_course_idx`), `(tenant, delivery_mode)` (`hrm_trs_tenant_mode_idx`),
    `(tenant, start_datetime)` (`hrm_trs_tenant_start_idx`)
  - `clean()` guards (mirrors the existing HRM `clean()` convention):
    - `end_datetime > start_datetime`
    - `delivery_mode == "classroom"` requires non-blank `venue_name`
    - `delivery_mode == "virtual"` requires non-blank `meeting_link`
    - `delivery_mode == "external"` requires `external_vendor_id` or non-blank
      `external_instructor_name`
    - **Instructor/venue double-booking overlap check** (driver: Absorb LMS): when
      `instructor_employee_id` is set, reject if another `TrainingSession` in the same tenant with
      the same `instructor_employee_id`, `status` not in `("cancelled", "postponed")`, excluding
      `self.pk`, overlaps the time window (`start_datetime__lt=self.end_datetime` AND
      `end_datetime__gt=self.start_datetime`) — raise on `instructor_employee`. Same check for
      `venue_name` (case-insensitive, non-blank) when `delivery_mode == "classroom"` — raise on
      `venue_name`.
  - `@property can_join` — derived (never stored): `True` when `meeting_link` is set and `now` is
    within `[start_datetime - 15min, end_datetime]` (driver: TalentLMS "one-click join… active a
    short window before the session starts" — buildable now as simple date-math, no live
    meeting-platform API call)
  - `@property is_upcoming` — derived: `status not in ("completed", "cancelled") and
    start_datetime > timezone.now()` — used by the calendar view's default filter
  - `__str__`: `f"{self.number} · {self.course.title} ({self.start_datetime:%Y-%m-%d %H:%M})"` if
    `course_id` else `self.number`
  - Reuses: `hrm.EmployeeProfile` (instructor), `core.Party` (external vendor — no new vendor
    table), `accounting.Currency` (cost currency). No new core-spine entity.

Both models are `TenantNumbered` (mirrors every other HRM entity, local abstract base at
`apps/hrm/models.py:52`). Add after the existing `CoachingNote` class (current end of file, line
~5953) with a `# ---... 3.22 Training Management ...` section-header comment block mirroring the
3.18–3.21 preamble style (states this is a NEW domain — not a Performance-Management sub-module —
and lists what's reused / explicitly what's deferred to 3.23/3.24).

## Backend (apps/hrm/)

- [ ] **models.py** — add `TrainingCourse`, `TrainingSession` at the end of the file (after
  `CoachingNote`). `NUMBER_PREFIX = "TRC"` / `"TRS"` respectively.
- [ ] **forms.py** — `TrainingCourseForm` (exclude `tenant`, `number`; fields: `title`,
  `description`, `category`, `delivery_mode`, `provider_type`, `duration_hours`,
  `is_certification`, `certification_name`, `certification_validity_months`,
  `prerequisite_course`, `default_capacity`, `is_active`; `prerequisite_course` queryset scoped to
  `tenant` AND excludes `self.instance.pk` on edit so a course can't be its own prerequisite from
  the dropdown), `TrainingSessionForm` (exclude `tenant`, `number`; fields: `course`,
  `delivery_mode`, `status`, `start_datetime`, `end_datetime`, `timezone`, `capacity`,
  `waitlist_enabled`, `venue_name`, `venue_address`, `meeting_platform`, `meeting_link`,
  `meeting_id`, `instructor_employee`, `external_instructor_name`, `external_vendor`,
  `estimated_cost`, `actual_cost`, `currency`, `invoice_reference`, `notes`; `course`/
  `instructor_employee` querysets auto-scoped to `tenant` by `TenantModelForm`;
  **`external_vendor` queryset explicitly re-scoped** in `__init__` to
  `Party.objects.filter(tenant=tenant, roles__role="vendor").distinct()` (the base class only
  filters by `tenant`, not by role); **`currency` queryset set via lazy import**
  `from apps.accounting.models import Currency` inside `__init__`, `Currency.objects.filter(
  is_active=True).order_by("code")` (global master — do NOT filter by tenant, `Currency` has no
  `tenant` field)).
- [ ] **views.py** — function-based, `@login_required`, tenant-scoped throughout (no
  confidentiality gating needed — ordinary CRUD):
  - `trainingcourse_list` (search: `number`, `title`, `description`; filters: `category`,
    `provider_type`, `delivery_mode`, `is_certification`, `is_active`; `extra_context`:
    `category_choices`, `provider_type_choices`, `delivery_mode_choices=TrainingCourse
    .DELIVERY_MODE_CHOICES`), `trainingcourse_create`, `trainingcourse_detail` (prefetch
    `obj.sessions.order_by("-start_datetime")[:20]` + `obj.unlocks.all()` for courses that require
    this one as a prerequisite), `trainingcourse_edit`, `trainingcourse_delete` (POST-only; note
    `TrainingSession.course` is PROTECT so deleting a course with sessions will raise
    `ProtectedError` — catch it and show a friendly error message rather than a 500, mirroring how
    other PROTECT-guarded deletes in this app are handled)
  - `trainingsession_list` (search: `number`, `course__title`, `venue_name`,
    `instructor_employee__party__name`, `external_vendor__name`; filters: `status`,
    `delivery_mode`, `course`, `instructor_employee`; `extra_context`: `status_choices`,
    `delivery_mode_choices`, `courses` queryset, `instructors` queryset — all Filter Implementation
    Rules from CLAUDE.md apply: view passes every `*_choices`/queryset the template needs; FK/pk
    comparisons in the template use `|stringformat:"d"`), `trainingsession_create` (`select_related`
    course for the form's default `capacity`/`delivery_mode` display — no server-side auto-copy
    required), `trainingsession_detail` (`select_related("course", "instructor_employee__party",
    "external_vendor", "currency")`; shows `can_join` (renders a "Join Meeting" button when True and
    `meeting_link` is set), classroom/virtual/external sections conditional on `delivery_mode`),
    `trainingsession_edit`, `trainingsession_delete`
  - `training_calendar` — standalone `GET`-only query view over `TrainingSession`: default filter
    = upcoming (`start_datetime__gte=today`, `status` not in `("cancelled",)`), optional
    `?delivery_mode=`/`?status=`/`?from=`/`?to=` GET filters, ordered `start_datetime` ascending,
    grouped by date in the view (a dict of `date -> [sessions]`) for the template to iterate; no
    pagination (bounded by the date range) — passes `sessions_by_date`, `delivery_mode_choices`,
    `status_choices`.
- [ ] **urls.py** — `app_name = "hrm"` (already set); add under a `# 3.22 Training Management`
  comment block:
  ```
  path("training-courses/", views.trainingcourse_list, name="trainingcourse_list"),
  path("training-courses/add/", views.trainingcourse_create, name="trainingcourse_create"),
  path("training-courses/<int:pk>/", views.trainingcourse_detail, name="trainingcourse_detail"),
  path("training-courses/<int:pk>/edit/", views.trainingcourse_edit, name="trainingcourse_edit"),
  path("training-courses/<int:pk>/delete/", views.trainingcourse_delete, name="trainingcourse_delete"),

  path("training-sessions/", views.trainingsession_list, name="trainingsession_list"),
  path("training-sessions/add/", views.trainingsession_create, name="trainingsession_create"),
  path("training-sessions/<int:pk>/", views.trainingsession_detail, name="trainingsession_detail"),
  path("training-sessions/<int:pk>/edit/", views.trainingsession_edit, name="trainingsession_edit"),
  path("training-sessions/<int:pk>/delete/", views.trainingsession_delete, name="trainingsession_delete"),

  path("training-calendar/", views.training_calendar, name="training_calendar"),
  ```
- [ ] **admin.py** — register both models:
  - `TrainingCourseAdmin`: `list_display = ("number", "title", "category", "delivery_mode",
    "provider_type", "is_certification", "is_active", "tenant")`; `list_filter = ("tenant",
    "category", "provider_type", "is_certification", "is_active")`; `search_fields = ("number",
    "title")`; `raw_id_fields = ("prerequisite_course",)`; `readonly_fields = ("number",
    "created_at", "updated_at")`
  - `TrainingSessionAdmin`: `list_display = ("number", "course", "delivery_mode", "status",
    "start_datetime", "instructor_employee", "tenant")`; `list_filter = ("tenant",
    "delivery_mode", "status")`; `search_fields = ("number", "course__title", "venue_name")`;
    `raw_id_fields = ("course", "instructor_employee", "external_vendor", "currency")`;
    `readonly_fields = ("number", "created_at", "updated_at")`
- [ ] **migrations** — `python manage.py makemigrations hrm` — expect
  `0037_trainingcourse_trainingsession...` (next after the existing `0036_
  performanceimprovementplan_coachingnote_pipcheckin_and_more.py`).
- [ ] **seed_hrm.py** — new `_seed_training(self, tenant, *, flush)` method:
  - Called from `handle()` immediately after `self._seed_improvement(tenant, flush=options
    ["flush"])` (the 6th call in the per-tenant loop; first call for a NEW domain, not a
    Performance-Management continuation).
  - `if flush:` delete in child-first order: `TrainingSession`, then `TrainingCourse` — filtered by
    `tenant` (session's `course` FK is PROTECT).
  - Idempotency guard: `if TrainingCourse.objects.filter(tenant=tenant).exists():` -> NOTICE +
    return.
  - Reuse EXISTING `EmployeeProfile` rows for `instructor_employee` (`EmployeeProfile.objects
    .filter(tenant=tenant).select_related("party").order_by("party__name")` — need >= 2 for a
    realistic classroom + a distinct one for overlap-safety on a second session).
  - Reuse an existing vendor-role `Party` for `external_vendor`: `Party.objects.filter(tenant=
    tenant, roles__role="vendor").first()` — if `None`, leave `external_vendor` blank on the
    external-mode seed row and rely on `external_instructor_name` alone to satisfy the model's
    `clean()` OR-requirement (do NOT create a new vendor `Party` row here — vendor-master creation
    belongs to accounting/CRM seeding, not this seeder).
  - Reuse an existing `accounting.Currency` (lazy import `from apps.accounting.models import
    Currency`): `Currency.objects.filter(code="USD").first() or Currency.objects.first()` — if
    `None`, leave `currency` blank on the cost-bearing seed rows.
  - Demo data: 3 `TrainingCourse` rows spanning distinct `category`/`provider_type` — e.g.
    "Technical Onboarding Bootcamp" (`category="onboarding"`, `provider_type="internal"`,
    `delivery_mode="classroom"`), "Workplace Safety Certification" (`category="safety"`,
    `is_certification=True`, `certification_name="Certified Safety Associate"`,
    `certification_validity_months=24`), "Leadership Excellence Program" (`category="leadership"`,
    `provider_type="external"`, `prerequisite_course=` the onboarding bootcamp — demonstrates the
    self-FK). At least 4 `TrainingSession` rows covering all three `delivery_mode` values and at
    least 2 `status` values — e.g. one `classroom` `scheduled` session (with `venue_name`,
    `instructor_employee`), one `virtual` `confirmed` session (with `meeting_platform="zoom"`,
    `meeting_link`), one `external` `completed` session (with `external_vendor` or
    `external_instructor_name`, `estimated_cost`/`actual_cost`/`currency`/`invoice_reference`), one
    more `classroom` session on a DIFFERENT instructor/venue and non-overlapping time window (proves
    the overlap `clean()` guard doesn't false-positive on legitimate back-to-back scheduling).
  - **CRITICAL — Windows cp1252 console bug (repeat of the 3.20/3.21 bug):** NO non-cp1252
    characters (no `→`, `↔`, em-dash arrows, etc.) in ANY `self.stdout.write(...)` string — plain
    ASCII `->` only. Re-read the whole method for stray Unicode before committing.
  - Update `_seed_tenant`'s big flush-teardown tuple: insert `TrainingSession, TrainingCourse,`
    immediately BEFORE the existing `# 3.21: PIPs/warnings/coaching...` comment block, with a new
    one-line comment: `# 3.22: TrainingSession.course is PROTECT — wipe sessions before courses;
    instructor_employee is SET_NULL (order-agnostic vs EmployeeProfile).`
  - Both `management/__init__.py` and `management/commands/__init__.py` already exist (no new dirs
    this pass) — verify, don't recreate.

## Wire-up

- [ ] `config/settings.py` — `apps.hrm` already in `INSTALLED_APPS` (no change needed this pass).
- [ ] `config/urls.py` — `hrm/` include already wired (no change needed this pass).
- [ ] `apps/core/navigation.py` `LIVE_LINKS["3.22"]` — new block mapping the 5 exact NavERP.md 3.22
  bullets (confirmed verbatim from `NavERP.md` lines 587–592), placed immediately after the
  existing `"3.21"` block, with a preamble comment noting this is a NEW HRM domain (not a
  Performance-Management continuation) and that 3.23 LMS / 3.24 Training Administration are
  deferred siblings:
  ```python
  # 3.22 Training Management — Instructor-Led Training scheduling/catalog (a NEW HRM domain, not a
  # Performance-Management continuation). Classroom/Virtual/External all resolve to filtered slices
  # of the one TrainingSession list (delivery_mode) so each highlights on its own page (most-specific
  # match wins). 3.23 Learning Management (LMS) and 3.24 Training Administration (nomination/
  # attendance/feedback/certificates/budget) are deferred sibling sub-modules, not built here.
  "3.22": {
      "Training Calendar": "hrm:training_calendar",                              # bullet (upcoming TrainingSession query view)
      "Training Catalog": "hrm:trainingcourse_list",                             # bullet (TrainingCourse CRUD)
      "Classroom Training": "hrm:trainingsession_list?delivery_mode=classroom",  # bullet (classroom slice)
      "Virtual Training": "hrm:trainingsession_list?delivery_mode=virtual",      # bullet (virtual slice)
      "External Training": "hrm:trainingsession_list?delivery_mode=external",    # bullet (external slice)
  },
  ```

## Templates (templates/hrm/training/)

- [ ] **New sub-module folder `training/`** (per the Template Folder Structure rule — 3.22 is a
  distinct NavERP.md sub-module from `performance/`, so it gets its own folder), with one entity
  folder per model:
- [ ] `templates/hrm/training/trainingcourse/list.html` — filter bar (`category`, `provider_type`,
  `delivery_mode`, `is_certification`, `is_active` dropdowns reflecting `request.GET`), Actions
  column (view/edit/delete-POST+confirm+csrf), pagination, empty-state.
- [ ] `templates/hrm/training/trainingcourse/detail.html` — catalog fields read-only,
  certification block conditional on `is_certification`, prerequisite chain (`obj
  .prerequisite_course` link + `obj.unlocks.all` reverse list), recent/upcoming sessions
  sub-list (`obj.sessions...`), Actions sidebar (Edit, Delete, Back to List).
- [ ] `templates/hrm/training/trainingcourse/form.html` — create/edit (shared template, `is_edit`
  flag).
- [ ] `templates/hrm/training/trainingsession/list.html` — filter bar (`status`, `delivery_mode`,
  `course`, `instructor_employee` dropdowns; FK/pk comparisons via `|stringformat:"d"`), Actions
  column.
- [ ] `templates/hrm/training/trainingsession/detail.html` — course link, schedule
  (start/end/timezone), classroom section conditional on `delivery_mode == "classroom"` (venue),
  virtual section conditional on `"virtual"` (platform/link/id + a "Join Meeting" button shown only
  when `obj.can_join`), external section conditional on `"external"` (vendor/instructor name/cost/
  currency/invoice reference), Actions sidebar.
- [ ] `templates/hrm/training/trainingsession/form.html` — create/edit; JS/HTMX toggling of the
  classroom/virtual/external field groups based on the `delivery_mode` select (progressive
  disclosure — all fields still POST-able/validated server-side regardless of JS state, per the
  model's `clean()` guards).
- [ ] `templates/hrm/training/calendar.html` — standalone page (sub-module-root, NO entity folder,
  per Template Folder Structure rule §6 — mirrors `hrm/hrm_overview.html`'s standalone-page
  pattern), sessions grouped by date (`sessions_by_date` from the view), each row shows course
  title/time/delivery_mode badge/status badge + a "Join" button when `can_join`, filter bar
  (`delivery_mode`, `status`, date range) reflecting `request.GET`, empty-state when no upcoming
  sessions.

## Verify

- [ ] `python manage.py makemigrations hrm` — expect `0037_trainingcourse_trainingsession...`;
  review the generated file before applying.
- [ ] `python manage.py migrate`
- [ ] `python manage.py seed_hrm` — run twice; second run must be a no-op (NOTICE message, zero new
  rows) proving idempotency.
- [ ] `python manage.py check` — zero errors/warnings.
- [ ] `temp/` smoke sweep — all `hrm:trainingcourse_*`, `hrm:trainingsession_*`,
  `hrm:training_calendar` URLs return 200/302 (never 500); no `{#`/`{% comment` template-comment
  leaks in rendered output; cross-tenant IDOR check (a tenant-B admin hitting a tenant-A
  TrainingCourse/TrainingSession pk returns 404, not the object); explicit double-booking check —
  attempt to create a second `TrainingSession` with the same `instructor_employee` in an overlapping
  window and confirm the `clean()` guard rejects it with a form error (not a 500/`IntegrityError`);
  confirm deleting a `TrainingCourse` that still has `TrainingSession` rows shows a friendly error
  (PROTECT), not a 500.
- [ ] Sidebar shows all 5 new 3.22 sub-module bullets as **Live** (Training Calendar, Training
  Catalog, Classroom Training, Virtual Training, External Training) — confirm via the rendered
  sidebar, not just the `LIVE_LINKS` dict.

## Close-out

- [ ] Run the 7 review agents in order, applying findings + committing after each (one file per
  commit, no `git push`): `code-reviewer` -> `explorer` -> `frontend-reviewer` ->
  `performance-reviewer` -> `qa-smoke-tester` -> `security-reviewer` -> `test-writer`.
  - Expect `performance-reviewer` to check `trainingsession_list`/`trainingcourse_detail` for N+1s
    (select_related on `course`, `instructor_employee__party`, `external_vendor`, `currency`;
    prefetch on `obj.sessions`/`obj.unlocks`).
  - Expect `security-reviewer` to confirm no cross-tenant leakage in the `prerequisite_course`/
    `external_vendor`/`currency` form querysets (tenant-scoped where applicable; `Currency` is
    intentionally global).
  - Expect `test-writer` to cover: full CRUD round-trips x2 models; all 4 `clean()` guards on
    `TrainingSession` (end>start, classroom needs venue, virtual needs meeting_link, external needs
    vendor-or-instructor-name) each as their own test; the instructor AND venue double-booking
    overlap guards (both a rejecting-overlap case and a legitimate non-overlapping/back-to-back
    case that must NOT be rejected); the `prerequisite_course` self-FK guard; the `can_join`/
    `is_upcoming` derived properties at boundary timestamps.
- [ ] Update `.claude/skills/hrm/SKILL.md`:
  - Add a `### 3.22 Training Management (2 tables)` section (mirrors the existing per-sub-module
    section format) with the model table (fields, FK targets incl. the `core.Party` vendor-role
    reuse and the `accounting.Currency` lazy-import reuse, no confidentiality note needed — this
    sub-module is ordinary open CRUD).
  - Bump the frontmatter/overview "built" sub-module list to include 3.22 and note it is a **NEW
    domain** (Instructor-Led Training scheduling), not a Performance-Management continuation; 3.23
    LMS and 3.24 Training Administration remain deferred siblings.
  - Add a "Training Management (3.22)" routes-list section (`hrm:trainingcourse_*`,
    `hrm:trainingsession_*`, `hrm:training_calendar`).
  - Update the seeder section: document `_seed_training(tenant)`, its own-exists guard, what it
    creates, and that it runs LAST (after `_seed_improvement`).
  - Update the `LIVE_LINKS` section: "3.22: Training Calendar -> `hrm:training_calendar`; Training
    Catalog -> `hrm:trainingcourse_list`; Classroom/Virtual/External Training -> filtered
    `hrm:trainingsession_list` slices. All 5 NavERP.md 3.22 bullets are now live."
  - Update the "Deferred" section to add 3.22's own carried-forward deferrals (see below) alongside
    the existing 3.23/3.24 placeholder line.
  - Commit the SKILL.md update as its own file, per the one-file-per-commit rule.
- [ ] README (if the project keeps a root test-count/module-count summary) — refresh HRM test
  counts after `test-writer` runs, same pattern as the 3.20/3.21 README refresh commits.

## Later passes / deferred (carried over from research-hrm-3.22-training-management.md)

- **3.23 Learning Management (LMS)** — Course Content (videos/documents/SCORM), Learning Paths,
  Assessments, Gamification, Progress Tracking — the content/self-paced-delivery layer on top of
  `TrainingCourse`. Sibling sub-module, own pass.
- **3.24 Training Administration** — Nomination/approval workflow, Attendance Tracking (incl.
  walk-in registration + webinar-synced e-signature check-in), Training Feedback, Certificates,
  Training Budget (consumes `TrainingSession.estimated_cost`/`actual_cost`). Sibling sub-module, own
  pass.
- **Dedicated Venue/Room master** (`TrainingVenue` with capacity/amenities/cross-session calendar) —
  `venue_name`/`venue_address` text fields + the `clean()` overlap guard cover v1; revisit if
  multi-room facility management recurs (could align with Module 11 Asset/Facility).
- **Multi-instructor / co-instructor per session** — a single `instructor_employee` is sufficient
  for v1 (Cornerstone OnDemand/Docebo support a crew; deferred).
- **Live videoconferencing API integration** (Zoom/Teams/Webex auto-provisioning, attendee sync,
  webhook attendance) — this pass stores platform/link as plain organizer-entered data.
- **Notification/reminder delivery pipeline** (registration confirmations, N-hours-before reminders)
  — the data model (`start_datetime`) supports it; the email/scheduling worker is cross-module.
  Session reminders — deferred to that pipeline.
- **Formal vendor scorecard / accreditation extension** — if needed later, extend via a thin
  `TenantOwned` 1:1 profile on `core.Party` (mirroring `accounting.VendorProfile`), not a duplicate
  vendor table.
- **Public/embeddable course catalog & external learner portal with billing** (Arlo, Absorb LMS) —
  out of scope; NavERP 3.22 is an internal employee-training tool, not a training-provider
  storefront.
- **Cost-vs-performance / ROI reporting** — needs 3.24's Training Budget + Training Feedback data
  joined with the cost fields captured here; deferred to 3.24.
- **Auto-generated webinar link on session creation** (360Learning-style API call to mint a join
  link) — integration/later; requires per-tenant Zoom/Teams/Webex API credentials.

## Review notes (3.22 — as-built)

Built exactly the 2-model scope: `TrainingCourse` (TRC-) + `TrainingSession` (TRS-), full CRUD + a
`training_calendar` view, `LIVE_LINKS["3.22"]` (5 bullets, delivery-mode `?query` slices), `_seed_training`
(3 courses + 4 sessions/tenant, idempotent), migrations 0037 (models) + 0038 (perf indexes). Verified:
`manage.py check` clean, seeder idempotent (2nd run no-op), 13-URL smoke sweep 200/302 + no comment leaks,
cross-tenant IDOR → 404, overlap `clean()` guard + `ProtectedError` course-delete confirmed.

**Module Creation Sequence — all 7 review agents run, one at a time, findings applied & committed:**
- **code-reviewer** — 1 Important: the double-booking guard no-op'd on *create* (`crud_create` sets
  `obj.tenant` after `is_valid()`, so `clean()`'s overlap query ran on `tenant_id=None`). Fixed:
  `TrainingSessionForm.__init__` sets `instance.tenant` pre-validation. Regression-pinned in tests.
- **explorer** — wiring fully consistent; dropped redundant `Meta.widgets`/`input_formats` (the base
  `TenantModelForm` already forces datetime-local + round-trip formats, L22).
- **frontend-reviewer** — 2 Important: undefined `.section-title` → `.card-title`; dead "Cancelled" option
  on the calendar status filter removed. + minor: course form reuses `partials/form_field.html`, calendar
  badge future-proofed.
- **performance-reviewer** — added `(tenant, instructor_employee)` + `(tenant, delivery_mode)` indexes
  (mig 0038); trimmed 2 unused `select_related` legs. No N+1s.
- **qa-smoke-tester** — found a latent **app-wide** 500 in the shared `crud_list` boolean filter
  (`?is_active=abc` → uncaught `ValidationError` inside `.filter()`); root-cause fixed in `apps/core/crud.py`
  (try/except, extends the L11 int-guard intent) — protects every module.
- **security-reviewer** — no vulnerabilities (tenant isolation, `URLField` rejects hostile schemes,
  `rel="noopener"`, CSRF, no `|safe`, ORM-only). No changes.
- **test-writer** — 154 tests (64 model/form + 63 view + 27 security), all green; full HRM suite green,
  no regressions.

Skill `.claude/skills/hrm/SKILL.md` updated (models table, flow, routes, `training/` templates, seeder,
LIVE_LINKS, counts 79→81). **3.22 complete; next unbuilt is 3.23 Learning Management (LMS).**

---
# Module 3 — HRM — Sub-module 3.23 Learning Management (LMS) (hrm-3.23-learning-management) — plan from research-hrm-3.23-learning-management.md (2026-07-09)

**EXTENDS the existing `apps/hrm` app (already built through 3.22) — no new Django app, no new
`INSTALLED_APPS`/`config/urls.py` entries, next migration is `0039`.** This pass covers ONLY the 5
NavERP.md 3.23 bullets (Course Content / Learning Paths / Assessments / Gamification / Progress
Tracking) — the self-paced digital-learning layer that hangs off the already-built 3.22
`hrm.TrainingCourse` catalog. Sibling sub-module **3.24 Training Administration**
(nomination/attendance/feedback/certificates/budget) is explicitly OUT of scope this pass, as is a
real question-bank assessment engine, SCORM runtime/xAPI, and an achievement-badge catalog — see
Later passes / deferred.

Reuses (never duplicates): `hrm.TrainingCourse` (TRC-, 3.22 — `is_certification`,
`certification_validity_months`, `prerequisite_course` self-FK already modeled, reused not
re-added), `hrm.EmployeeProfile` (the learner — no new learner table), `hrm.Designation` (3.2, path
role-targeting), `core.OrgUnit` filtered `kind="department"` (3.2's real department master — HRM's
`DepartmentProfile` is a 1:1 companion profile on `OrgUnit`, **not** a standalone department model;
confirmed via grep of `apps/hrm/models.py`/`apps/core/models.py` — `Designation.department` already
FKs `core.OrgUnit` the same way). No new core-spine entity; nothing posts to the GL. Ordinary
tenant-scoped CRUD — no confidentiality gating (same openness level as 3.22).

## Models (from research)

- [ ] **`LearningContentItem`** [no number prefix — `TenantOwned` child of `TrainingCourse`, same
  child shape as `hrm.ClearanceItem`] — covers **Course Content** + the light **Assessments**
  variant.
  - `course` — FK `hrm.TrainingCourse`, `on_delete=CASCADE`, `related_name="content_items"` (a
    course's lessons die with the course — mirrors `ClearanceItem.case` CASCADE, unlike
    `TrainingSession.course`/`LearningPathItem.course`/`LearningProgress.course` which are PROTECT
    catalog references, not ownership)
  - `title` (CharField, max_length=255), `description` (TextField, blank)
  - `content_type` — CharField choices, max_length=15, default `"video"`: `video` / `document` /
    `scorm` / `external_link` / `text` / `assessment` (driver: multi-format content items — Docebo,
    TalentLMS, SAP SuccessFactors, SAP Litmos, iSpring Learn)
  - `sequence` — PositiveIntegerField, default 0 (driver: ordered lessons — Docebo, iSpring Learn)
  - `is_required` — BooleanField, default True (driver: mandatory vs. optional content — Absorb LMS,
    Cornerstone)
  - `estimated_duration_minutes` — PositiveIntegerField, null/blank
  - Content fields (only the one matching `content_type` is expected filled, enforced in `clean()`):
    `video_url` (URLField, blank), `document_file` (FileField, `upload_to="hrm/lms/documents/%Y/%m/"`,
    blank), `scorm_package` (FileField, `upload_to="hrm/lms/scorm/%Y/%m/"`, blank), `external_url`
    (URLField, blank), `body_text` (TextField, blank) (driver: SCORM package storage — Docebo, SAP
    SuccessFactors, LearnUpon, SAP Litmos)
  - Assessment-only fields (used when `content_type="assessment"`): `pass_threshold_percent`
    (PositiveIntegerField, default 70, `MinValueValidator(0)`/`MaxValueValidator(100)`),
    `max_attempts` (PositiveIntegerField, default 1, `MinValueValidator(1)`), `time_limit_minutes`
    (PositiveIntegerField, null/blank) (driver: pass threshold + max attempts + time-limited tests —
    Absorb LMS, LearnUpon, SAP SuccessFactors) — **no question-bank sub-table this pass**, score/pass
    are recorded outcomes on `LearningProgress`
  - `Meta.ordering = ["course", "sequence"]`; indexes `(tenant, course)` (`hrm_lci_tenant_course_idx`),
    `(tenant, content_type)` (`hrm_lci_tenant_ctype_idx`)
  - `clean()`: `content_type="video"` requires non-blank `video_url`; `"document"` requires
    `document_file`; `"scorm"` requires `scorm_package`; `"external_link"` requires non-blank
    `external_url`; `"text"` requires non-blank `body_text`; `"assessment"` has NO required content
    field (score/attempts fields carry the meaning instead) — this only enforces the ONE
    type-matching field is present, it never force-blanks the others (an assessment may still carry
    `body_text` instructions, for example)
  - `__str__`: `f"{self.course.title} · {self.sequence}. {self.title}"` if `course_id` else
    `self.title`
  - Reuses: `hrm.TrainingCourse` only — a new HRM-owned child table (no core-spine change).

- [ ] **`LearningPath`** [`LNP-`, `TenantNumbered`] — covers **Learning Paths** header.
  - `title` (CharField, max_length=255), `description` (TextField, blank)
  - `target_designation` — FK `hrm.Designation`, `on_delete=SET_NULL`, null/blank,
    `related_name="learning_paths"` (driver: role/job-based targeting — Cornerstone, iSpring Learn —
    reuses the existing 3.2 master, no new "Role" table)
  - `target_department` — FK `core.OrgUnit`, `on_delete=SET_NULL`, null/blank,
    `related_name="learning_paths"`, `limit_choices_to={"kind": "department"}` (mirrors
    `DepartmentProfile.cost_center`'s `limit_choices_to` pattern so the dropdown only offers
    department-kind org nodes, not company/branch/cost-center ones) (driver: org-branch targeting —
    Docebo)
  - `is_mandatory` — BooleanField, default False (driver: compliance-style path vs. optional
    development path)
  - `is_active` — BooleanField, default True
  - `Meta.ordering = ["title"]`; `unique_together = ("tenant", "number")`; indexes `(tenant,
    is_active)` (`hrm_lnp_tenant_active_idx`), `(tenant, is_mandatory)`
    (`hrm_lnp_tenant_mandatory_idx`)
  - `__str__`: `f"{self.number} · {self.title}"`
  - Reuses: `hrm.Designation`, `core.OrgUnit` — no new "Role"/"Department" table.

- [ ] **`LearningPathItem`** [no number prefix — `TenantOwned` child of `LearningPath`, same child
  pattern as `hrm.ClearanceItem`] — covers **Learning Paths** ordered content.
  - `path` — FK `LearningPath`, `on_delete=CASCADE`, `related_name="items"`
  - `course` — FK `hrm.TrainingCourse`, `on_delete=PROTECT`, `related_name="path_items"` (a course
    referenced by a path can't be deleted out from under it — mirrors `TrainingSession.course`)
  - `sequence` — PositiveIntegerField, default 0 (driver: ordered completion sequence — SAP Litmos,
    LearnUpon, Moodle Workplace Programs)
  - `is_mandatory` — BooleanField, default True (path-level override of the course's own
    `is_required`-style intent)
  - `Meta.ordering = ["path", "sequence"]`; `unique_together = ("tenant", "path", "course")`; indexes
    `(tenant, path)` (`hrm_lpi_tenant_path_idx`), `(tenant, course)` (`hrm_lpi_tenant_course_idx`)
  - `clean()` — **prerequisite gating** (driver: research feature #43 — reuses
    `TrainingCourse.prerequisite_course` rather than a new rule field): if `self.course.
    prerequisite_course_id` is set AND that prerequisite course is *also* a `LearningPathItem` in
    the same `path` (excluding `self.pk`), that prerequisite item's `sequence` must be `<
    self.sequence` — else raise on `sequence` ("This course's prerequisite must appear earlier in
    the path."). If the prerequisite course is NOT in this path, no error (it's assumed satisfied
    elsewhere) — a light-touch guard, not a hard requirement that every prerequisite be enrolled.
  - `__str__`: `f"{self.path.title} · {self.sequence}. {self.course.title}"`
  - Reuses: `LearningPath`, `hrm.TrainingCourse` — no new rule-engine table.

- [ ] **`LearningProgress`** [no number prefix — `TenantOwned`, unique per employee×course] — covers
  **Progress Tracking**, assessment *outcomes*, and lightweight **Gamification**.
  - `employee` — FK `hrm.EmployeeProfile`, `on_delete=CASCADE`, `related_name="learning_progress"`
    (mirrors the `LeaveRequest`/`Timesheet`/`AttendanceRecord` house style: a per-employee tracking
    row dies with the employee profile)
  - `course` — FK `hrm.TrainingCourse`, `on_delete=PROTECT`, `related_name="learner_progress"`
    (mirrors `TrainingSession.course`/`LearningPathItem.course` — a course with recorded progress
    can't vanish silently; NOTE `trainingcourse_delete`'s existing generic `ProtectedError` catch,
    built in 3.22 for `TrainingSession.course`, already covers this and `LearningPathItem.course`
    too — Django's `ProtectedError` aggregates every protecting relation across the whole delete
    collector, so no additional catch code is needed there)
  - `learning_path` — FK `LearningPath`, `on_delete=SET_NULL`, null/blank, `related_name="progress_
    records"` ("enrolled via this path", if applicable)
  - `status` — CharField choices, max_length=15, default `"not_started"`: `not_started` /
    `in_progress` / `completed` / `failed` / `expired` (all 11 surveyed products)
  - `percent_complete` — PositiveIntegerField, default 0, `MinValueValidator(0)`/
    `MaxValueValidator(100)` (Docebo, SAP Litmos, Moodle Workplace)
  - `time_spent_minutes` — PositiveIntegerField, default 0 (SAP SuccessFactors)
  - `score` — DecimalField(max_digits=5, decimal_places=2), null/blank; `passed` — BooleanField,
    null/blank (Absorb LMS/LearnUpon auto-grading pattern — recorded outcome, not question-bank
    computed, this pass)
  - `attempt_count` — PositiveIntegerField, default 0 (respects the content item's `max_attempts`,
    not DB-enforced this pass — a UI/process convention)
  - `points_earned` — PositiveIntegerField, default 0 (TalentLMS/Absorb LMS/iSpring Learn/Adobe
    Learning Manager gamification points; **leaderboard + level tier are computed queries/properties
    over this field — no new table**)
  - `started_at`, `completed_at` — DateTimeField, null/blank
  - `Meta.ordering = ["-updated_at"]`; `unique_together = ("tenant", "employee", "course")`; indexes
    `(tenant, employee)` (`hrm_lprog_tenant_emp_idx`), `(tenant, course)`
    (`hrm_lprog_tenant_course_idx`), `(tenant, status)` (`hrm_lprog_tenant_status_idx`)
  - `clean()`: `completed_at` (if set) must be `>= started_at` (if set) — else raise on
    `completed_at`
  - `@property certification_expires_on` — derived, **never stored**: `None` unless `completed_at`
    is set AND `course.is_certification` AND `course.certification_validity_months`; otherwise
    `completed_at.date()` advanced by `certification_validity_months` using plain stdlib month-math
    (`calendar.monthrange` for day clamping) — **no `dateutil` dependency added**
  - `@property is_certification_expired` — derived: `certification_expires_on` is not None and is in
    the past (`< timezone.now().date()`)
  - `__str__`: `f"{self.employee} · {self.course.title} ({self.get_status_display()})"`
  - Reuses: `hrm.EmployeeProfile`, `hrm.TrainingCourse`, `LearningPath` — no new learner/course table.

All four models are children of / satellites around the existing `hrm.TrainingCourse` catalog — add
after the existing `TrainingSession` class (current end of file, line ~6047 in `apps/hrm/models.py`)
with a `# ---... 3.23 Learning Management (LMS) ...` section-header comment block (mirrors the
3.18–3.22 preamble style: states this BUILDS ON 3.22's catalog rather than re-creating one, and lists
what's reused / explicitly deferred to 3.24).

## Backend (apps/hrm/)

- [ ] **models.py** — add `LearningContentItem`, `LearningPath`, `LearningPathItem`,
  `LearningProgress` at the end of the file. `LearningPath.NUMBER_PREFIX = "LNP"`; the other three
  models extend `TenantOwned` (no `NUMBER_PREFIX`, no `number` field).
- [ ] **forms.py**:
  - `LearningContentItemForm` (`TenantModelForm`; excludes `tenant`, `course` — `course` is set from
    the URL in the nested create view, mirrors `PIPCheckInForm` excluding `pip`; fields: `title`,
    `description`, `content_type`, `sequence`, `is_required`, `estimated_duration_minutes`,
    `video_url`, `document_file`, `scorm_package`, `external_url`, `body_text`,
    `pass_threshold_percent`, `max_attempts`, `time_limit_minutes`). Add module constants
    `ALLOWED_SCORM_EXTENSIONS = {".zip"}` / `MAX_SCORM_BYTES = 50 * 1024 * 1024` (50 MB) next to the
    existing `ALLOWED_ONBOARDING_DOC_EXTENSIONS`/`MAX_ONBOARDING_DOC_BYTES` (10 MB, reused as-is for
    `document_file`). `clean_scorm_package()` (extension + size guard, mirrors `clean_photo`/
    `EmployeeDocumentForm.clean_file`) and `clean_document_file()` (reuses
    `ALLOWED_ONBOARDING_DOC_EXTENSIONS`/`MAX_ONBOARDING_DOC_BYTES`). **WARNING (carry the research
    file's flag into the code comment):** this pass stores the SCORM zip as an opaque file only — it
    is never extracted. Any FUTURE SCORM-extraction handler MUST validate archive member paths
    (zip-slip / path-traversal guard, reject `../` and absolute paths) before writing extracted
    files to disk — do not trust package internals.
  - `LearningPathForm` (`TenantModelForm`; excludes `tenant`, `number`; fields: `title`,
    `description`, `target_designation`, `target_department`, `is_mandatory`, `is_active`;
    `target_designation`/`target_department` auto-scoped to `tenant` by the `TenantModelForm` base +
    `limit_choices_to` narrows `target_department` to `kind="department"` at the model-field level,
    no extra `__init__` override needed).
  - `LearningPathItemForm` (`TenantModelForm`; excludes `tenant`, `path` — set from the URL in the
    nested create view; fields: `course`, `sequence`, `is_mandatory`; `__init__` scopes `course` to
    `TrainingCourse.objects.filter(tenant=self.tenant, is_active=True)`).
  - `LearningProgressForm` (`TenantModelForm`; excludes `tenant`; fields: `employee`, `course`,
    `learning_path`, `status`, `percent_complete`, `time_spent_minutes`, `score`, `passed`,
    `attempt_count`, `points_earned`, `started_at`, `completed_at`).
    **CRITICAL — proactively apply the 3.22 code-reviewer fix, don't wait to rediscover it:**
    `learningprogress_create`/`_edit` are FLAT (not URL-nested), so if built on the generic
    `crud_create` helper the tenant is only set on `obj` AFTER `form.is_valid()` — but Django's
    `ModelForm._post_clean()` calls `instance.validate_unique()` *during* `is_valid()`, so the
    `("tenant","employee","course")` `unique_together` check would silently run against
    `tenant_id=None` and never catch a real duplicate. Fix at the form level exactly like
    `TrainingSessionForm`'s create-path fix: `LearningProgressForm.__init__` must set
    `self.instance.tenant = self.tenant` when `self.instance.tenant_id` is None and `self.tenant` is
    set, so `validate_unique()` runs against the real tenant even on the create path. Regression-pin
    this in `test-writer`'s output (duplicate employee+course via the CREATE view, not just the ORM,
    must be rejected).
- [ ] **views.py** — function-based, `@login_required`, tenant-scoped throughout (ordinary CRUD, no
  confidentiality gating):
  - `learningcontentitem_create(request, course_pk)` — **nested**, mirrors `pipcheckin_create`:
    `course = get_object_or_404(TrainingCourse, pk=course_pk, tenant=request.tenant)`; builds the
    form with `instance=LearningContentItem(tenant=request.tenant, course=course)` (tenant set
    BEFORE validation — sidesteps the `crud_create` gotcha entirely for this model); on success
    `write_audit_log` + redirect to `hrm:trainingcourse_detail` (pk=course.pk) so the new lesson
    shows immediately in the course's content list.
  - `learningcontentitem_list` — `crud_list`, `search_fields=["title", "description",
    "course__title"]`, `filters=[("content_type", "content_type", False), ("course", "course_id",
    True), ("is_required", "is_required", False)]`, `extra_context={"content_type_choices":
    LearningContentItem.CONTENT_TYPE_CHOICES, "courses": TrainingCourse.objects.filter(tenant=
    request.tenant).order_by("title")}`.
  - `learningcontentitem_detail` — `crud_detail`, `select_related=("course",)`.
  - `learningcontentitem_edit` — `crud_edit`, `success_url="hrm:learningcontentitem_list"`.
  - `learningcontentitem_delete` — manual (mirrors `clearanceitem_delete`'s parent-redirect style):
    capture `course_id` before delete, `write_audit_log`, delete, `messages.success`, redirect to
    `hrm:learningcontentitem_list`.
  - `learningpath_list` — `crud_list`, `search_fields=["number", "title", "description"]`,
    `filters=[("is_mandatory", "is_mandatory", False), ("is_active", "is_active", False),
    ("target_designation", "target_designation_id", True), ("target_department",
    "target_department_id", True)]`, `extra_context={"designations": ..., "departments":
    OrgUnit.objects.filter(tenant=request.tenant, kind="department").order_by("name")}`.
  - `learningpath_create` — `crud_create`, `success_url="hrm:learningpath_list"`.
  - `learningpath_detail` — `crud_detail` with `prefetch_related` on `items__course`, ordered by
    `sequence`; passes the ordered `items` + a nested "Add course to this path" link.
  - `learningpath_edit` — `crud_edit`, `success_url="hrm:learningpath_list"`.
  - `learningpath_delete` — `crud_delete`, `success_url="hrm:learningpath_list"` (note:
    `LearningPathItem.path` is CASCADE, so deleting a path cascades its items — no `ProtectedError`
    concern here, unlike `TrainingCourse` delete).
  - `learningpathitem_create(request, path_pk)` — **nested**, same manual-instance pattern as
    `learningcontentitem_create`: `instance=LearningPathItem(tenant=request.tenant, path=path)`;
    redirect to `hrm:learningpath_detail` (pk=path.pk) on success.
  - `learningpathitem_list` — `crud_list`, `search_fields=["path__title", "course__title"]`,
    `filters=[("path", "path_id", True), ("course", "course_id", True), ("is_mandatory",
    "is_mandatory", False)]`, `extra_context={"paths": ..., "courses": ...}`.
  - `learningpathitem_detail` — `crud_detail`, `select_related=("path", "course")`.
  - `learningpathitem_edit` — `crud_edit`, `success_url="hrm:learningpathitem_list"`.
  - `learningpathitem_delete` — manual, parent-redirect to `hrm:learningpath_detail` (pk=path_id),
    mirrors `clearanceitem_delete`.
  - `learningprogress_list` — `crud_list`, `search_fields=["employee__party__name",
    "course__title"]`, `filters=[("status", "status", False), ("course", "course_id", True),
    ("employee", "employee_id", True), ("learning_path", "learning_path_id", True)]`,
    `extra_context={"status_choices": LearningProgress.STATUS_CHOICES, "courses": ..., "employees":
    ..., "paths": ...}` — **all Filter Implementation Rules apply**: every `*_choices`/queryset the
    template needs is passed explicitly, FK/pk comparisons use `|stringformat:"d"`.
  - `learningprogress_create` — `crud_create`, `success_url="hrm:learningprogress_list"`.
  - `learningprogress_detail` — `crud_detail`, `select_related=("employee__party", "course",
    "learning_path")`; template surfaces `obj.certification_expires_on`/`obj.is_certification_expired`.
  - `learningprogress_edit` — `crud_edit`, `success_url="hrm:learningprogress_list"`.
  - `learningprogress_delete` — `crud_delete`, `success_url="hrm:learningprogress_list"`.
  - `learning_leaderboard` — standalone `GET`-only query view (covers **Gamification**):
    `LearningProgress.objects.filter(tenant=request.tenant).values("employee_id",
    "employee__party__name").annotate(total_points=Sum("points_earned"), courses_completed=Count(
    "id", filter=Q(status="completed"))).order_by("-total_points")`; a small module-level
    `_LMS_LEVEL_THRESHOLDS = [(0, "Bronze"), (150, "Silver"), (400, "Gold"), (800, "Platinum")]` +
    `_lms_level_for_points(points)` helper computes each row's tier (the "Levels" research feature —
    computed, no new table); passes `leaderboard_rows`.
  - `learning_team_progress` — standalone `GET`-only manager rollup (covers **Progress Tracking**'s
    manager dashboard): resolve `_current_employee_profile(request)`; if `None`, `messages.error` +
    redirect `dashboard:home`; `qs = LearningProgress.objects.filter(tenant=request.tenant).filter(
    Q(employee=profile) | Q(employee__employment__manager=profile.party)).select_related(
    "employee__party", "course")` — **exact reuse of the existing manager-rollup filter pattern**
    already used at `apps/hrm/views.py:7493` for goal ownership; optional `?status=`/`?course=` GET
    filters; passes `progress_rows` + simple summary counts (total/completed/in_progress).
  - **Cross-touch (existing 3.22 file):** extend `trainingcourse_detail`'s context with
    `content_items=obj.content_items.all()` (already `Meta.ordering`-sorted by `sequence`) and a
    nested "Add content" link to `learningcontentitem_create` (course_pk=obj.pk) — a one-line view
    change plus a template addition to the ALREADY-BUILT `templates/hrm/training/trainingcourse/
    detail.html`.
- [ ] **urls.py** — `app_name = "hrm"` (already set); add under a `# 3.23 Learning Management (LMS)`
  comment block:
  ```
  path("training-courses/<int:course_pk>/content/add/", views.learningcontentitem_create, name="learningcontentitem_create"),
  path("learning-content/", views.learningcontentitem_list, name="learningcontentitem_list"),
  path("learning-content/<int:pk>/", views.learningcontentitem_detail, name="learningcontentitem_detail"),
  path("learning-content/<int:pk>/edit/", views.learningcontentitem_edit, name="learningcontentitem_edit"),
  path("learning-content/<int:pk>/delete/", views.learningcontentitem_delete, name="learningcontentitem_delete"),

  path("learning-paths/", views.learningpath_list, name="learningpath_list"),
  path("learning-paths/add/", views.learningpath_create, name="learningpath_create"),
  path("learning-paths/<int:pk>/", views.learningpath_detail, name="learningpath_detail"),
  path("learning-paths/<int:pk>/edit/", views.learningpath_edit, name="learningpath_edit"),
  path("learning-paths/<int:pk>/delete/", views.learningpath_delete, name="learningpath_delete"),
  path("learning-paths/<int:path_pk>/items/add/", views.learningpathitem_create, name="learningpathitem_create"),

  path("learning-path-items/", views.learningpathitem_list, name="learningpathitem_list"),
  path("learning-path-items/<int:pk>/", views.learningpathitem_detail, name="learningpathitem_detail"),
  path("learning-path-items/<int:pk>/edit/", views.learningpathitem_edit, name="learningpathitem_edit"),
  path("learning-path-items/<int:pk>/delete/", views.learningpathitem_delete, name="learningpathitem_delete"),

  path("learning-progress/", views.learningprogress_list, name="learningprogress_list"),
  path("learning-progress/add/", views.learningprogress_create, name="learningprogress_create"),
  path("learning-progress/<int:pk>/", views.learningprogress_detail, name="learningprogress_detail"),
  path("learning-progress/<int:pk>/edit/", views.learningprogress_edit, name="learningprogress_edit"),
  path("learning-progress/<int:pk>/delete/", views.learningprogress_delete, name="learningprogress_delete"),

  path("learning-leaderboard/", views.learning_leaderboard, name="learning_leaderboard"),
  path("learning-team-progress/", views.learning_team_progress, name="learning_team_progress"),
  ```
- [ ] **admin.py** — register all four models:
  - `LearningContentItemAdmin`: `list_display = ("course", "sequence", "title", "content_type",
    "is_required", "tenant")`; `list_filter = ("tenant", "content_type", "is_required")`;
    `search_fields = ("title", "course__title")`; `raw_id_fields = ("course",)`; `readonly_fields =
    ("created_at", "updated_at")`
  - `LearningPathAdmin`: `list_display = ("number", "title", "target_designation",
    "target_department", "is_mandatory", "is_active", "tenant")`; `list_filter = ("tenant",
    "is_mandatory", "is_active")`; `search_fields = ("number", "title")`; `raw_id_fields =
    ("target_designation", "target_department")`; `readonly_fields = ("number", "created_at",
    "updated_at")`
  - `LearningPathItemAdmin`: `list_display = ("path", "sequence", "course", "is_mandatory",
    "tenant")`; `list_filter = ("tenant", "is_mandatory")`; `search_fields = ("path__title",
    "course__title")`; `raw_id_fields = ("path", "course")`; `readonly_fields = ("created_at",
    "updated_at")`
  - `LearningProgressAdmin`: `list_display = ("employee", "course", "status", "percent_complete",
    "points_earned", "tenant")`; `list_filter = ("tenant", "status")`; `search_fields = (
    "employee__party__name", "course__title")`; `raw_id_fields = ("employee", "course",
    "learning_path")`; `readonly_fields = ("created_at", "updated_at")`
- [ ] **migrations** — `python manage.py makemigrations hrm` — expect a `0039_...` migration creating
  all four models (Django's autodetector names it after the model set, e.g.
  `0039_learningcontentitem_learningpath_learningpathitem_learningprogress.py` or similar — next
  after the existing `0038_...` perf-index migration).
- [ ] **seed_hrm.py** — new `_seed_lms(self, tenant, *, flush)` method:
  - Called from `handle()` immediately after `self._seed_training(tenant, flush=options["flush"])`
    (the 7th call in the per-tenant loop).
  - `if flush:` delete in child-first order: `LearningProgress`, `LearningPathItem`, `LearningPath`,
    `LearningContentItem` — filtered by `tenant`.
  - Idempotency guard: look up the 3 existing courses by exact title (`TrainingCourse.objects.
    filter(tenant=tenant, title="Technical Onboarding Bootcamp").first()`, `"Workplace Safety
    Certification"`, `"Leadership Excellence Program"`) — if any is missing (training not seeded
    yet, or `_seed_training` skipped for <2 employees), NOTICE + return. Then `if
    LearningContentItem.objects.filter(tenant=tenant).exists():` -> NOTICE + return (mirrors the
    existing-data guard style).
  - Reuse EXISTING `EmployeeProfile` rows (`emps = EmployeeProfile.objects.filter(tenant=tenant)
    .select_related("party").order_by("party__name")` — need >= 2, ideally >= 3 for a meaningful
    leaderboard spread; gracefully use fewer if that's all that exists).
  - Reuse `hrm.Designation.objects.filter(tenant=tenant).first()` and `core.OrgUnit.objects.filter(
    tenant=tenant, kind="department").first()` (lazy top-level import already present:
    `from apps.core.models import OrgUnit` — mirror the existing import at
    `apps/hrm/management/commands/seed_hrm.py:16`) for `LearningPath.target_designation`/
    `target_department` — create NO new Designation/OrgUnit rows here.
  - Demo data — `LearningContentItem` (6 rows, deliberately skipping `document`/`scorm` content
    types since a management command has no real file to attach — a management-command limitation,
    not a model limitation; note this explicitly in the seeder docstring):
    - Bootcamp course: `video` "Welcome to Engineering" (seq 1, required, 15 min, `video_url=...`),
      `external_link` "Read: Company Engineering Handbook" (seq 2, required, 20 min,
      `external_url=...`), `text` "Team Norms & Communication Guidelines" (seq 3, optional, 10 min,
      `body_text=...`), `assessment` "Onboarding Knowledge Check" (seq 4, required,
      `pass_threshold_percent=80`, `max_attempts=2`, `time_limit_minutes=20`).
    - Safety course: `video` "Workplace Hazards Overview" (seq 1, required, 20 min), `assessment`
      "Safety Certification Exam" (seq 2, required, `pass_threshold_percent=90`, `max_attempts=1`,
      `time_limit_minutes=45`).
  - Demo data — `LearningPath` (2 rows): "New Hire Foundations" (`LNP-00001`,
    `target_designation`=the reused designation, `target_department`=the reused dept OrgUnit,
    `is_mandatory=True`) with `LearningPathItem` rows `[bootcamp seq 1 mandatory, safety seq 2
    mandatory]`; "Engineering Leadership Track" (`LNP-00002`, `is_mandatory=False`) with
    `LearningPathItem` rows `[bootcamp seq 1 mandatory, leadership seq 2 mandatory]` — this second
    path deliberately exercises the prerequisite-gating `clean()` guard (leadership's
    `prerequisite_course=bootcamp`, and bootcamp sits at an earlier `sequence` in the same path, so
    it validates cleanly).
  - Demo data — `LearningProgress` (using up to the first 3 employees, fewer if that's all that
    exists): employee[0] × bootcamp `completed` (100%, score 92, passed, 150 pts, via New Hire
    Foundations path); employee[0] × safety `completed` (100%, score 95, passed, 200 pts, via New
    Hire Foundations — exercises `certification_expires_on` against the course's 24-month validity);
    employee[1] × bootcamp `in_progress` (60%, 60 pts, via New Hire Foundations); employee[1] ×
    leadership `not_started` (0%, via Engineering Leadership Track); employee[2] × safety `failed`
    (100% attempted, score 55, not passed, 20 pts) if a 3rd employee exists.
  - **CRITICAL — Windows cp1252 console bug (repeat of the 3.20/3.21/3.22 bug):** ASCII-only
    `self.stdout.write(...)` strings (`->` not `→`, plain hyphen not em-dash). Re-read the whole
    method for stray Unicode before committing.
  - Update `_seed_tenant`'s big flush-teardown tuple: insert `LearningProgress, LearningPathItem,
    LearningPath, LearningContentItem,` immediately BEFORE the existing `TrainingSession,
    TrainingCourse,` line, with a comment: `# 3.23: LearningPathItem.course and LearningProgress
    .course are PROTECT — wipe before TrainingCourse; LearningContentItem.course is CASCADE
    (auto-clears with its course); LearningProgress.employee is CASCADE and .learning_path is
    SET_NULL (both order-agnostic vs EmployeeProfile/LearningPath).`
  - Both `management/__init__.py` and `management/commands/__init__.py` already exist (no new dirs
    this pass) — verify, don't recreate.

## Wire-up

- [ ] `config/settings.py` — `apps.hrm` already in `INSTALLED_APPS` (no change needed this pass).
- [ ] `config/urls.py` — `hrm/` include already wired (no change needed this pass).
- [ ] `apps/core/navigation.py` `LIVE_LINKS["3.23"]` — new block mapping the 5 exact NavERP.md 3.23
  bullets (confirmed verbatim from `NavERP.md` lines 594–599), placed immediately after the existing
  `"3.22"` block, with a preamble comment noting this sub-module BUILDS ON 3.22's course catalog and
  that 3.24 Training Administration is a deferred sibling:
  ```python
  # 3.23 Learning Management (LMS) — the self-paced digital-learning layer on top of the 3.22
  # TrainingCourse catalog (no new course table). "Assessments" is a filtered slice of the Course
  # Content list (content_type=assessment) rather than a dedicated question-bank UI this pass.
  # "Gamification" is the points leaderboard (levels/leaderboard are computed, not stored). 3.24
  # Training Administration (nomination/attendance/feedback/certificates/budget) is a deferred
  # sibling sub-module, not built here.
  "3.23": {
      "Course Content": "hrm:learningcontentitem_list",                                # bullet (LearningContentItem CRUD)
      "Learning Paths": "hrm:learningpath_list",                                       # bullet (LearningPath CRUD)
      "Assessments": "hrm:learningcontentitem_list?content_type=assessment",           # bullet (assessment-type slice)
      "Gamification": "hrm:learning_leaderboard",                                      # bullet (computed points leaderboard)
      "Progress Tracking": "hrm:learningprogress_list",                                # bullet (LearningProgress CRUD)
  },
  ```

## Templates (templates/hrm/lms/)

- [ ] **New sub-module folder `lms/`** (per the Template Folder Structure rule — 3.23 is a distinct
  NavERP.md sub-module from `training/`), with one entity folder per model:
- [ ] `templates/hrm/lms/learningcontentitem/list.html` — filter bar (`content_type`, `course`,
  `is_required` dropdowns reflecting `request.GET`; FK/pk comparison via `|stringformat:"d"`),
  Actions column (view/edit/delete-POST+confirm+csrf), pagination, empty-state.
- [ ] `templates/hrm/lms/learningcontentitem/detail.html` — course link, content_type badge, the
  ONE populated content field rendered conditionally on `content_type` (video embed/link, document
  download link, SCORM package download link + a note that it's storage-only this pass, external
  link, or the text body), assessment fields block conditional on `content_type == "assessment"`,
  Actions sidebar (Edit, Delete, Back to course).
- [ ] `templates/hrm/lms/learningcontentitem/form.html` — create/edit (shared, `is_edit` flag); JS
  toggling which content-field group is visible based on the `content_type` select (progressive
  disclosure, mirrors `trainingsession/form.html`'s delivery_mode toggling — all fields still
  server-validated regardless of JS state).
- [ ] `templates/hrm/lms/learningpath/list.html` — filter bar (`is_mandatory`, `is_active`,
  `target_designation`, `target_department`), Actions column.
- [ ] `templates/hrm/lms/learningpath/detail.html` — path header fields, ordered `items` sub-list
  (course title, sequence, mandatory badge) with a nested "Add course to this path" link, Actions
  sidebar.
- [ ] `templates/hrm/lms/learningpath/form.html` — create/edit.
- [ ] `templates/hrm/lms/learningpathitem/list.html` — filter bar (`path`, `course`, `is_mandatory`),
  Actions column.
- [ ] `templates/hrm/lms/learningpathitem/detail.html` — path + course links, sequence, mandatory
  flag, Actions sidebar (Back to path).
- [ ] `templates/hrm/lms/learningpathitem/form.html` — nested create/edit (`path` shown read-only as
  context, not a field, on the create form).
- [ ] `templates/hrm/lms/learningprogress/list.html` — filter bar (`status`, `course`, `employee`,
  `learning_path`), Actions column, status badges (not_started/in_progress/completed/failed/expired
  matching the model's exact CHOICES values).
- [ ] `templates/hrm/lms/learningprogress/detail.html` — employee/course/path links, percent-complete
  progress bar, score/passed, `certification_expires_on`/`is_certification_expired` block shown only
  when the course `is_certification`, Actions sidebar.
- [ ] `templates/hrm/lms/learningprogress/form.html` — create/edit.
- [ ] `templates/hrm/lms/leaderboard.html` — standalone page (sub-module-root, NO entity folder, per
  Template Folder Structure rule §6), ranked table (`leaderboard_rows`: rank, employee, total_points,
  courses_completed, level-tier badge), empty-state when no progress rows exist yet.
- [ ] `templates/hrm/lms/team_progress.html` — standalone manager-rollup page (`progress_rows` +
  summary counts), filter bar (`status`, `course`), empty-state for a non-manager (message: "You have
  no direct reports.") vs. an empty team (message: "Your team has no learning activity yet.").
- [ ] **Cross-touch:** `templates/hrm/training/trainingcourse/detail.html` (existing 3.22 file) — add
  a "Course Content" section rendering `content_items` (title/content_type badge/sequence/required
  flag) + an "Add content" link to the nested create route.

## Verify

- [ ] `python manage.py makemigrations hrm` — expect a new `0039_...` migration; review the generated
  file before applying.
- [ ] `python manage.py migrate`
- [ ] `python manage.py seed_hrm` — run twice; second run must be a no-op (NOTICE message, zero new
  rows) proving idempotency.
- [ ] `python manage.py check` — zero errors/warnings.
- [ ] `temp/` smoke sweep — all `hrm:learningcontentitem_*`, `hrm:learningpath_*`,
  `hrm:learningpathitem_*`, `hrm:learningprogress_*`, `hrm:learning_leaderboard`,
  `hrm:learning_team_progress` URLs return 200/302 (never 500); no `{#`/`{% comment` template-comment
  leaks in rendered output; cross-tenant IDOR check (a tenant-B admin hitting a tenant-A
  `LearningContentItem`/`LearningPath`/`LearningPathItem`/`LearningProgress` pk returns 404, not the
  object — INCLUDING the nested create routes: `training-courses/<tenant-A course pk>/content/add/`
  and `learning-paths/<tenant-A path pk>/items/add/` hit as tenant B must 404, not silently create a
  cross-tenant-linked row); explicit `LearningPathItem` prerequisite-gating check (adding leadership
  before bootcamp in the same path, at an earlier sequence, must be rejected by `clean()`; adding it
  after must succeed); explicit `LearningProgress` duplicate check via the CREATE VIEW (not just the
  ORM) — submitting a second employee+course pair through `learningprogress_create` must show a form
  validation error, not silently create a duplicate row (the exact regression class the 3.22
  code-reviewer caught on `TrainingSessionForm`); file-upload guard checks (oversized/wrong-extension
  `document_file`/`scorm_package` rejected with a form error, not a 500).
- [ ] Sidebar shows all 5 new 3.23 sub-module bullets as **Live** (Course Content, Learning Paths,
  Assessments, Gamification, Progress Tracking) — confirm via the rendered sidebar, not just the
  `LIVE_LINKS` dict.

## Close-out

- [ ] Run the 7 review agents in order, applying findings + committing after each (one file per
  commit, no `git push`): `code-reviewer` -> `explorer` -> `frontend-reviewer` ->
  `performance-reviewer` -> `qa-smoke-tester` -> `security-reviewer` -> `test-writer`.
  - Expect `code-reviewer` to double-check the `LearningProgressForm` tenant-pre-validation fix was
    actually applied (see the forms.py note above) rather than re-discovering the 3.22 bug fresh.
  - Expect `performance-reviewer` to check `learningcontentitem_list`/`learningpath_detail`/
    `learning_leaderboard`/`learning_team_progress` for N+1s (select_related on `course`,
    `employee__party`, `learning_path`; prefetch on `path.items.select_related("course")`; the
    leaderboard's `.values().annotate()` should not additionally N+1 per row when the template
    renders employee names).
  - Expect `security-reviewer` to confirm: tenant scoping on the two nested-create routes
    (`course_pk`/`path_pk` looked up with `tenant=request.tenant`, never a bare `get_object_or_404`
    without the tenant filter); the SCORM/document upload extension+size guards are present and the
    zip-slip WARNING comment is in place for future extraction work; no `|safe` on any
    user-supplied text field (`description`, `body_text`, notes-like fields).
  - Expect `test-writer` to cover: full CRUD round-trips × 4 models (incl. the two nested-create
    routes); the `LearningContentItem.clean()` content-type/field-match guard (one positive + one
    mismatched-field-negative case per `content_type`); the `LearningPathItem.clean()`
    prerequisite-gating guard (both the rejecting out-of-order case and the accepting in-order case,
    AND the case where the prerequisite isn't in the path at all — must not error); the
    `LearningPathItem`/`LearningProgress` `unique_together` guards, WITH the `LearningProgress`
    create-path regression pin (form sets `instance.tenant` pre-validation); `certification_expires_
    on`/`is_certification_expired` at exact boundary dates (day before/after expiry, and `None` when
    the course isn't a certification or `completed_at` is unset); the leaderboard's points ordering
    + level-tier thresholds; `learning_team_progress`'s manager-scoping (a manager sees only self +
    direct reports, never the whole tenant; a non-manager sees only their own row(s)); the file
    upload extension/size `clean_*` guards.
- [ ] Update `.claude/skills/hrm/SKILL.md`:
  - Add a `### 3.23 Learning Management (LMS) (4 tables)` section (mirrors the existing per-sub-module
    section format) with the model table (fields, FK targets incl. the `core.OrgUnit`
    `kind="department"` reuse and the `hrm.TrainingCourse.prerequisite_course` gating reuse), the
    nested-create routes, and the SCORM-is-storage-only + zip-slip WARNING note.
  - Bump the frontmatter/overview "built" sub-module list to include 3.23 and note it BUILDS ON 3.22
    (not a new course table); 3.24 Training Administration remains a deferred sibling.
  - Add a "Learning Management (3.23)" routes-list section (`hrm:learningcontentitem_*`,
    `hrm:learningpath_*`, `hrm:learningpathitem_*`, `hrm:learningprogress_*`,
    `hrm:learning_leaderboard`, `hrm:learning_team_progress`).
  - Update the seeder section: document `_seed_lms(tenant)`, its own-exists guard (+ the "training
    must already be seeded" dependency), what it creates, and that it runs LAST (after
    `_seed_training`).
  - Update the `LIVE_LINKS` section: "3.23: Course Content -> `hrm:learningcontentitem_list`;
    Learning Paths -> `hrm:learningpath_list`; Assessments -> filtered `hrm:learningcontentitem_list`
    slice; Gamification -> `hrm:learning_leaderboard`; Progress Tracking ->
    `hrm:learningprogress_list`. All 5 NavERP.md 3.23 bullets are now live."
  - Update the "Deferred" section to add 3.23's own carried-forward deferrals (see below) alongside
    the existing 3.24 placeholder line.
  - Commit the SKILL.md update as its own file, per the one-file-per-commit rule.
- [ ] README (if the project keeps a root test-count/module-count summary) — refresh HRM test counts
  after `test-writer` runs, same pattern as the 3.20/3.21/3.22 README refresh commits.

## Later passes / deferred (carried over from research-hrm-3.23-learning-management.md)

- **Question-bank assessment authoring** (Question, Choice, per-attempt Answer tables, multiple
  question types, AI-suggested questions) — this pass ships pass/fail + score as recorded outcomes
  only, no authored question bank. (TalentLMS, Absorb LMS, LearnUpon, 360Learning)
- **SCORM runtime / xAPI LRS integration** — the JS SCORM API handshake and a proper Learning Record
  Store for xAPI statements are specialized runtime services; this pass stores the SCORM package
  file + metadata only. **Vulnerability note carried forward:** any future SCORM upload/extraction
  handler MUST validate archive contents (zip-slip / path-traversal guard) before writing extracted
  files to disk. (Docebo, SAP SuccessFactors, LearnUpon, Adobe Learning Manager)
- **AICC support** — legacy content-packaging standard; low priority, mostly-enterprise ask.
- **Achievement badge catalog + award table** — a real LMS badge system (icon, criteria, award log)
  distinct from HRM 3.20's `KudosBadge` (peer recognition); would be a 5th/6th model, dropped from
  this pass's budget. (TalentLMS, Absorb LMS, iSpring Learn, Adobe Learning Manager)
- **Flexible completion rules for path sub-groups** ("all in order" / "all in any order" / "at least
  N of M") — this pass ships a single strict sequence + light prerequisite gating; a full rule engine
  is deferred. (Moodle Workplace Programs)
- **Adaptive/conditional ("if/then") learning journeys** and **dynamic auto-enrollment rules** (by
  job role, hire date, location) — needs a rules/automation engine layered on `LearningPath`.
  (Cornerstone, LearnUpon, 360Learning, Moodle Workplace)
- **Path-level certificate issuance** (the PDF/print artifact + issuance record) — this pass only
  computes *eligibility* via `LearningProgress`/`TrainingCourse.is_certification`; issuance mechanics
  belong to 3.24 Certificates. (LearnUpon, Moodle Workplace, SAP Litmos)
- **Content-provider marketplace / licensed course library** — a commercial content-licensing
  integration, not a data-model concern. (Docebo, SAP Litmos)
- **AI content/quiz generation** — external AI service integration. (360Learning, TalentLMS, Docebo)
- **Challenge mode / peer competitions** and **redeemable rewards for points** — differentiator
  gamification mechanics beyond points+leaderboard+levels; likely never needed for an internal ERP
  LMS. (360Learning, TalentLMS)
- **Predictive analytics / org-wide skill-gap dashboards** — a reporting-layer feature to revisit
  once enough `LearningProgress` data exists. (SAP SuccessFactors, Adobe Learning Manager)
- **Renewal-reminder delivery** (notifications as a certification nears/passes expiry) — the data
  model (`certification_expires_on`) supports the calculation; the email/scheduling worker is
  cross-module, same deferred pipeline noted in 3.22.
- **3.24 Training Administration (sibling sub-module, NOT built here):**
  - **Nomination** — employee nomination/approval workflow for being enrolled (into a
    `TrainingSession` or a `LearningPath`/course).
  - **Attendance Tracking** — per-`TrainingSession` (ILT) attendance marking — distinct from this
    sub-module's self-paced `LearningProgress.status`/`percent_complete`.
  - **Training Feedback** — post-training evaluation forms.
  - **Certificates** — auto-generation/issuance of the completion certificate document (this pass
    only computes eligibility, not the artifact).
  - **Training Budget** — budget allocation/utilization rollups (aggregates `TrainingSession
    .actual_cost` from 3.22, not anything in 3.23).

## Review notes
(filled in at the end)
