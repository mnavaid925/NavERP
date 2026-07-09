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

## Review notes (3.23 — as-built)

Built exactly the 4-model scope: `LearningContentItem` (CASCADE child of `TrainingCourse`), `LearningPath` (LNP-) +
`LearningPathItem`, `LearningProgress` (unique per employee×course), all extending the 3.22 catalog. Full CRUD +
nested-create children (content under a course, items under a path), a computed `learning_leaderboard` +
`learning_team_progress` rollup, `LIVE_LINKS["3.23"]` (5 bullets, Assessments = `?content_type=assessment` slice),
`_seed_lms` (6 content + 2 paths + 4 path-courses + 5 progress/tenant, idempotent), migration 0039, and a
`trainingcourse_detail` cross-touch. Verified: `manage.py check` clean, seeder idempotent, 20-URL smoke sweep
200/302 + no leaks, cross-tenant IDOR → 404, prerequisite-gating + dual duplicate-guards + ProtectedError delete.

**Two bugs caught by my own smoke sweep BEFORE the review agents:** (1) `learningpath_list` ordered `Designation` by
a non-existent `title` field (it's `name`) → 500; (2) the `LearningProgressForm` uniqueness guard didn't fire —
Django's `validate_unique()` SKIPS a `unique_together` involving the form-excluded `tenant` field, so `instance.tenant`
alone can't help; replaced with an explicit `clean()` duplicate check.

**Module Creation Sequence — all 7 review agents run in order, findings applied & committed:**
- **code-reviewer** — 1 Critical: `LearningPathItemForm` had the SAME missing duplicate-guard (L28 sibling of the
  LearningProgressForm bug) → re-adding a course to a path 500'd; fixed with a `clean()` guard. + Important: generalized
  the `trainingcourse_delete` ProtectedError message (3.23 added 2 new PROTECT refs). + Minor: content-form edit
  breadcrumb `{% elif obj %}` fallback.
- **explorer** — wiring fully consistent, no changes.
- **frontend-reviewer** — 2 Minor: `team_progress` bare `.stat-grid` (dropped a redundant inline style) + value-before-
  label stat-card order. No comment leaks, all badge/utility classes real.
- **performance-reviewer** — 1 Minor: `learningpathitem_detail` select_relates `course__prerequisite_course` (2nd FK
  hop shown in the template). select_related complete elsewhere; all 8 indexes present; leaderboard = 1 aggregate query.
- **qa-smoke-tester** — 41 requests all 200/302, no defects, no changes.
- **security-reviewer** — no Critical/High/Medium; 1 Low doc comment (MEDIA-serving WARNING on the upload cleaners).
  SCORM confirmed opaque (no extraction code), URLFields reject hostile schemes, CSRF/tenant-isolation clean.
- **test-writer** — 220 tests (87 model/form + 83 view + 50 security), all green; full HRM suite 4212/4212, no regressions.

Skill `.claude/skills/hrm/SKILL.md` updated (models table, LMS flow, routes, `lms/` templates, seeder, LIVE_LINKS,
counts 81→85). **3.23 complete; next unbuilt is 3.24 Training Administration.**

---
# Module 3 — HRM — Sub-module 3.24 Training Administration (hrm-3.24-training-administration) — plan from research-hrm-3.24-training-administration.md (2026-07-09)

**EXTENDS the existing `apps/hrm` app (already built through 3.23) — no new Django app, no new
`INSTALLED_APPS`/`config/urls.py` entries, next migration is `0040`.** This is the FINAL sub-module
of the 3.22 (ILT catalog) / 3.23 (LMS) / 3.24 (Administration) training cluster — it adds only the
**operational/transactional layer** (who's nominated, who showed up, what they thought, what they
earned) and must not re-model the catalog (`TrainingCourse`), the ILT occurrence
(`TrainingSession`), or self-paced progress (`LearningProgress`) already built. Four models cover
Nomination / Attendance Tracking / Training Feedback / Certificates; **Training Budget does NOT get
a model** — it's a computed aggregate over `TrainingSession.actual_cost`/`estimated_cost` (3.22) and
`hrm.CostCenterProfile.budget_annual` (3.2), matching the research finding that budget *tracking* is
a differentiator (Training Orchestra's specialty), not a table-stakes stored feature.

Reuses (never duplicates): `hrm.TrainingSession` (TRS-, 3.22 — `capacity`, `waitlist_enabled`,
`status`, `start_datetime`, `estimated_cost`/`actual_cost`/`currency`), `hrm.TrainingCourse` (TRC-,
3.22 — `is_certification`, `certification_name`, `certification_validity_months`),
`hrm.LearningProgress` (3.23 — the LMS completion path a certificate can also be issued from),
`hrm.EmployeeProfile` (nominee/attendee/certificate holder — no new learner table),
`hrm.CostCenterProfile`/`core.OrgUnit` (kind `department`/`cost_center`, 3.2 — the budget path via
`DepartmentProfile.cost_center`), `accounting.Currency` (global, lazy-import, already on
`TrainingSession`). No new core-spine entity; nothing posts to the GL. Ordinary tenant-scoped CRUD —
no confidentiality gating, except `TrainingFeedback.is_anonymous` masks the attendee's identity on
render (direct clone of the 3.20 `Feedback.is_anonymous`/`giver_anonymized` pattern, reusing the
already-defined `_is_admin(request.user)` helper at `apps/hrm/views.py:7721`), and nomination
approve/reject/waitlist mirror `LeaveRequest.approve`/`reject`'s privileged-action shape
(`apps/hrm/views.py:985-1039`) but allow the nominee's manager too, not just a tenant admin.

**GOTCHA — apply proactively, don't wait to rediscover it (learned the hard way across 3.22/3.23):**
any model with `unique_together` involving a field EXCLUDED from its ModelForm needs an EXPLICIT
`clean()` duplicate query — Django's `validate_unique()` silently SKIPS a `unique_together` tuple
when ANY field in it isn't a form field (regardless of what's pre-set on `self.instance`), surfacing
only as a 500 IntegrityError. This applies to:
- `TrainingNominationForm` — `(tenant, session, employee)`, both `session`/`employee` are ordinary
  form fields but `tenant` is always excluded → skipped.
- `TrainingAttendanceForm` — `(tenant, session, employee)`, same shape.
- `TrainingFeedbackForm` — **a THIRD application, self-caught here, not explicitly named in the
  brief but the identical root cause**: `attendance` is set from the URL (nested create, excluded
  from `Meta.fields` entirely) and `tenant` is always excluded, so `unique_together=(tenant,
  attendance)` has BOTH fields form-excluded — the skip is even more certain than the other two.
  All three forms need the same explicit `clean()` guard; do not assume pre-setting
  `self.instance.attendance`/`.session`/`.employee` before `is_valid()` fixes it (that only fixes the
  *different* `tenant_id=None`-at-validation-time bug from `LearningProgressForm`, 3.23 — a separate
  gotcha, not this one).

## Models (from research)

- [ ] **`TrainingNomination`** [`NOM-`, `TenantNumbered`] — covers **Nomination**.
  - `session` — FK `hrm.TrainingSession`, `on_delete=PROTECT`, `related_name="nominations"` (a
    session with nominations can't vanish silently)
  - `employee` — FK `hrm.EmployeeProfile`, `on_delete=PROTECT`, `related_name="training_nominations"`
    (the nominee)
  - `nominated_by` — FK `hrm.EmployeeProfile`, `on_delete=SET_NULL`, null/blank,
    `related_name="nominations_made"` (null = self-nominated)
  - `nomination_type` — CharField choices, max_length=10, default `"self"`: `self` / `manager` /
    `hr` (driver: self- or manager-initiated nomination — SAP SuccessFactors Learning, SAP Litmos,
    Workday Learning's Manager Enroll task, Cornerstone automated enrollment; `hr` covers "Assign as
    Required" per Workday Learning — a manual force-assign this pass, no rule-based auto-trigger)
  - `status` — CharField choices, max_length=12, default `"pending"`: `pending` / `approved` /
    `rejected` / `waitlisted` / `cancelled` / `withdrawn` (driver: single-approver workflow —
    `LeaveRequest` precedent; waitlist queue — SAP Litmos + the `TrainingSession.waitlist_enabled`
    help-text's explicit promise "the queue itself is 3.24 Nomination")
  - `approver` — FK `hrm.EmployeeProfile`, `on_delete=SET_NULL`, null/blank,
    `related_name="nominations_approved"` (an `EmployeeProfile`, not `AUTH_USER_MODEL` like
    `LeaveRequest.approver` — deliberate: the manager-permission check compares against
    `employee.employment.manager`, a `core.Party`, so keeping the decision-maker as an employee/party
    identity avoids a second User→Party lookup at every permission check)
  - `approved_at` — DateTimeField, null/blank, `editable=False` (workflow-owned)
  - `rejected_reason` — TextField, blank (workflow-owned, set by the reject action)
  - `cancelled_reason` — TextField, blank (workflow-owned, set by cancel/withdraw — added beyond the
    brief's literal field list, mirroring `LeaveRequest.cancelled_reason`'s exact house style so
    cancel/withdraw have somewhere to record why, same as every other HRM workflow model)
  - `justification` — TextField, blank (why this nomination — free text from the nominator)
  - `priority` — CharField choices, max_length=10, default `"normal"`: `low` / `normal` / `high`
  - `Meta.ordering = ["-created_at"]`; `unique_together = ("tenant", "session", "employee")`; indexes
    `(tenant, session)` (`hrm_nom_tenant_session_idx`), `(tenant, employee)`
    (`hrm_nom_tenant_emp_idx`), `(tenant, status)` (`hrm_nom_tenant_status_idx`)
  - `clean()`: if `self.session_id` and `self.session.status in ("completed", "cancelled")`, raise on
    `session` ("Cannot nominate for a completed or cancelled session.") — plus the explicit
    duplicate-guard is in the FORM's `clean()`, not the model's (model-level `unique_together`
    already raises via `validate_unique()` for any path that DOES include both fields, e.g. the admin
    site or a direct `full_clean()`; the form-level guard is the belt-and-suspenders fix for the
    gotcha above)
  - `__str__`: `f"{self.number} · {self.employee} · {self.session}"`
  - **Cross-touch (existing 3.22 `TrainingSession` class):** add two `@property` methods —
    `approved_nomination_count` (`self.nominations.filter(status="approved").count()`) and `is_full`
    (`self.approved_nomination_count >= self.capacity`) — fulfilling the research's "waitlisted
    computed against session.capacity vs approved count" requirement with NO new field/migration
    (properties only; `related_name="nominations"` already makes `self.nominations` valid the moment
    `TrainingNomination` exists).
  - Reuses: `hrm.TrainingSession`, `hrm.EmployeeProfile`, `EmployeeProfile.employment.manager` (a
    `core.Party`) for the approve/reject manager-permission check — no new "Role"/approval-chain
    table. **Design note (deviation from the literal brief, documented):** no separate `_submit`
    workflow view — this scope has no `draft` status, so a created nomination is born `pending`
    directly via `trainingnomination_create`; `submit` is folded into create. If a future draft-save
    capability is added, a real `_submit` (`draft`→`pending`) would slot in then.

- [ ] **`TrainingAttendance`** [`TenantOwned`, unique per (tenant, session, employee)] — covers
  **Attendance Tracking**.
  - `session` — FK `hrm.TrainingSession`, `on_delete=PROTECT`, `related_name="attendance_records"`
  - `employee` — FK `hrm.EmployeeProfile`, `on_delete=PROTECT`, `related_name="training_attendance"`
  - `nomination` — FK `TrainingNomination`, `on_delete=SET_NULL`, null/blank,
    `related_name="attendance_records"` (null = unregistered — links back when the attendee WAS
    nominated)
  - `attendance_status` — CharField choices, max_length=10, default `"registered"`: `registered` /
    `present` / `absent` / `partial` / `walk_in` (driver: present/absent/partial marking — Docebo,
    SAP Litmos, Arlo; **walk-in is a status value, not a separate boolean** — a `walk_in` row with
    `nomination=None` fully captures Docebo's "add walk-ins at the door" feature with one field, not
    two)
  - `completion_status` — CharField choices, max_length=15, default `"not_completed"`:
    `not_completed` / `completed` / `failed` (driver: session-level completion independent of
    attendance presence, with manual override — Docebo)
  - `check_in_at` — DateTimeField, null/blank; `check_out_at` — DateTimeField, null/blank (driver:
    arrival/departure audit trail — Arlo mobile check-in, Cornerstone audit-ready documentation)
  - `notes` — TextField, blank
  - `Meta.ordering = ["-session__start_datetime", "employee__party__name"]`; `unique_together =
    ("tenant", "session", "employee")`; indexes `(tenant, session)` (`hrm_att_tenant_session_idx`),
    `(tenant, employee)` (`hrm_att_tenant_emp_idx`), `(tenant, attendance_status)`
    (`hrm_att_tenant_status_idx`)
  - `clean()`: `check_out_at` (if set) must be `>= check_in_at` (if set) — else raise on
    `check_out_at`; if `self.nomination_id`, the nomination's `session_id`/`employee_id` must match
    `self.session_id`/`self.employee_id` — else raise on `nomination` ("This nomination is for a
    different session/employee.") — a defense-in-depth consistency check, cheap since `nomination`
    is already scoped to the tenant by the form
  - `__str__`: `f"{self.employee} · {self.session} ({self.get_attendance_status_display()})"`
  - **OPTIONAL (nice-to-have, base CRUD is mandatory, this is a stretch goal if time allows):** a
    per-session "mark attendance" roster action — `trainingattendance_roster(request, session_pk)`
    (GET renders every `approved`/`waitlisted` nominee for the session next to their existing
    attendance row if any; POST bulk-updates `attendance_status` per employee in one submit).
  - Reuses: `hrm.TrainingSession`, `hrm.EmployeeProfile`, `TrainingNomination` — no new table.

- [ ] **`TrainingFeedback`** [`TenantOwned`, unique per (tenant, attendance)] — covers **Training
  Feedback** (Kirkpatrick Level-1 "Reaction").
  - `attendance` — FK `TrainingAttendance`, `on_delete=CASCADE`, `related_name="feedback"` (a plain
    FK per the brief, not a Django `OneToOneField` — the 1:1 cardinality is enforced instead by
    `unique_together=(tenant, attendance)`, functionally identical, matches the literal field type
    requested)
  - `overall_rating` — PositiveSmallIntegerField, `validators=[MinValueValidator(1),
    MaxValueValidator(5)]`; `content_rating` — same; `trainer_rating` — same (driver: Kirkpatrick
    Level-1 course/content/trainer rating — TalentLMS survey units, Kirkpatrick-model best-practice
    guidance)
  - `would_recommend` — BooleanField, default True (driver: TalentLMS's satisfaction+recommend
    framing)
  - `comments` — TextField, blank
  - `is_anonymous` — BooleanField, default False (driver: masks the attendee — direct clone of the
    3.20 `Feedback.is_anonymous` mask-on-render pattern; **no `submitted_at` field** —
    `TenantOwned.created_at` already carries "when submitted", avoiding a redundant column)
  - `Meta.ordering = ["-created_at"]`; `unique_together = ("tenant", "attendance")`; no extra indexes
    needed beyond the one the `unique_together` constraint already provides
  - `clean()`: **no rating-range logic here** — the `MinValueValidator`/`MaxValueValidator` on each
    field already enforce 1–5 at the form/field level (matches the brief: "ratings in 1..5
    (validators handle it)"); `clean()` on the FORM (not the model) carries the
    `(tenant, attendance)` duplicate guard from the GOTCHA above
  - `@property giver_anonymized` — `return self.is_anonymous` (mirrors `Feedback.giver_anonymized`
    exactly, one place to change if a future per-type masking rule is needed)
  - `__str__`: `f"Feedback · {self.attendance}"`
  - Reuses: `TrainingAttendance` (no duplicate session/employee FKs — the attendee IS
    `attendance.employee`, there's no separate "giver" field).

- [ ] **`TrainingCertificate`** [`CERT-`, `TenantNumbered`] — covers **Certificates**.
  - `employee` — FK `hrm.EmployeeProfile`, `on_delete=PROTECT`, `related_name="training_certificates"`
  - `course` — FK `hrm.TrainingCourse`, `on_delete=PROTECT`, `related_name="certificates"` (the
    certifying course)
  - `source_attendance` — FK `TrainingAttendance`, `on_delete=SET_NULL`, null/blank,
    `related_name="certificates_issued"` (the ILT completion that earned it)
  - `source_progress` — FK `hrm.LearningProgress`, `on_delete=SET_NULL`, null/blank,
    `related_name="certificates_issued"` (the LMS completion that earned it)
  - `title` — CharField, max_length=255, blank (defaulted in `save()` from
    `course.certification_name` or `course.title` — never required from the user)
  - `issued_on` — DateField (form default = today, set by the view's `initial=`)
  - `expires_on` — DateField, null/blank, `editable=False` (computed ONCE at `save()` time, from
    `issued_on` + `course.certification_validity_months`, using the SAME stdlib month-math as
    `LearningProgress.certification_expires_on` — see the shared-helper extraction below; **stored**,
    not derived-on-read, because it's an issued artifact and must not silently drift if the course's
    validity setting changes later)
  - `verification_code` — CharField, max_length=20, `unique=True`, `editable=False`, blank (generated
    once in `save()`: `secrets.token_hex(8).upper()`, 16 hex chars, 64 bits of entropy — same
    `secrets`-module standard the project already uses for `public_token`/`token` fields
    (`apps/crm/models.py`, `apps/tenants/models.py`, `apps/accounts/models.py`); global `unique=True`
    mirrors `NPSSurvey.token`'s exact pattern — no per-tenant uniqueness loop needed at this entropy)
  - `status` — CharField choices, max_length=10, default `"issued"`: `issued` / `revoked` / `expired`
  - `revoked_reason` — TextField, blank
  - **Design note (deviation from the research doc, documented, not silently dropped):** NO
    `certificate_file` FileField and NO `issued_by` FK this pass — the brief's literal field list
    omits both. `certificate_file` (a future PDF-render/upload target) is pushed to Later
    passes/deferred rather than shipped half-used; `issued_by` is dropped as redundant — every create
    already runs `write_audit_log(request.user, obj, "create")`, which already answers "who/when
    issued" via `AuditLog`, the project's general mechanism, without a duplicate column.
  - `Meta.ordering = ["-issued_on"]`; `unique_together = ("tenant", "number")`; indexes `(tenant,
    employee)` (`hrm_cert_tenant_emp_idx`), `(tenant, course)` (`hrm_cert_tenant_course_idx`),
    `(tenant, status)` (`hrm_cert_tenant_status_idx`)
  - `clean()`: both `source_attendance` and `source_progress` set at once → raise on
    `source_progress` ("Link only one source — attendance OR progress, not both."). Neither set is
    ALLOWED (a flat/manual/administrative issuance, e.g. a legacy-system import or a non-ILT/non-LMS
    training) — the brief does not mandate "exactly one required", so this stays permissive but still
    catches the genuinely ambiguous double-sourced case. If `source_attendance_id`, its `employee_id`
    must equal `self.employee_id` and its `session.course_id` must equal `self.course_id` — else
    raise (cross-consistency). Same check mirrored for `source_progress` (`employee_id`/`course_id`
    must match).
  - `save()`: (1) `if not self.title:` default from `course.certification_name or course.title`; (2)
    `if not self.verification_code:` generate it; (3) `if self.expires_on is None and self.issued_on
    and self.course_id:` compute it via the shared month-math helper, only if
    `course.is_certification` and `course.certification_validity_months` are both set (else stays
    `None`) — computed ONCE, on first save, never recomputed after.
  - **Shared-helper extraction (elegance, avoid duplicating the month-math a second time):** pull
    `LearningProgress.certification_expires_on`'s inline `calendar.monthrange` day-clamp logic out
    into a module-level `_advance_months(d: date, months: int) -> date` helper near the top of
    `models.py` (alongside `TenantOwned`/`TenantNumbered`); refactor `LearningProgress
    .certification_expires_on` to call it (no behavior change, existing tests must still pass
    unmodified); `TrainingCertificate.save()` calls the same helper. Do not re-derive the
    `calendar.monthrange` logic inline a second time.
  - `@property is_expired` — `bool(self.expires_on and self.expires_on < timezone.localdate())`
    (derived, live truth). **Design tension, flagged not hidden:** `status` ALSO has a stored
    `expired` choice (per the brief's literal list), but nothing in this pass auto-flips a stored
    `issued` row to `expired` when its date passes — there is no scheduled job. Templates/badges MUST
    render off the live `is_expired` property, not solely off `obj.status == "expired"` (which an
    admin can still set manually, e.g. after an external audit) — document this explicitly in the
    detail template comment and in the SKILL.md close-out so it isn't rediscovered as a "bug" later.
  - `__str__`: `f"{self.number} · {self.employee} · {self.title}"` if `self.number` else `self.title`
  - Reuses: `hrm.TrainingCourse.is_certification`/`certification_name`/
    `certification_validity_months` (3.22), `hrm.LearningProgress` (3.23), `TrainingAttendance` (this
    pass) — issues the artifact, never recomputes eligibility itself.

All four models are transactional satellites around the already-built `TrainingSession`/
`TrainingCourse`/`LearningProgress` — add after the existing `LearningProgress` class (current end of
file, `apps/hrm/models.py`) with a `# --- 3.24 Training Administration ... ---` section-header
comment block (mirrors the 3.22/3.23 preamble style: states this is the operational layer, lists what
it reuses, and notes Training Budget is a computed view with no model).

## Backend (apps/hrm/)

- [ ] **models.py**:
  - Add a module-level `_advance_months(d, months)` helper (the shared-extraction above) placed near
    `TenantOwned`/`TenantNumbered`, imports already present (`calendar`, `date` — both already
    imported for `LearningProgress`).
  - Refactor `LearningProgress.certification_expires_on` to call `_advance_months` (no behavior
    change).
  - Add `TrainingNomination`, `TrainingAttendance`, `TrainingFeedback`, `TrainingCertificate` at the
    end of the file. `TrainingNomination.NUMBER_PREFIX = "NOM"`, `TrainingCertificate.NUMBER_PREFIX =
    "CERT"`; the other two extend `TenantOwned` (no `NUMBER_PREFIX`, no `number` field).
  - Add the `approved_nomination_count`/`is_full` `@property` pair to the EXISTING `TrainingSession`
    class (cross-touch, no migration — properties only).
- [ ] **forms.py**:
  - `TrainingNominationForm` (`TenantModelForm`; excludes `tenant`, `status`, `approver`,
    `approved_at`, `rejected_reason`, `cancelled_reason`; fields: `session`, `employee`,
    `nominated_by`, `nomination_type`, `justification`, `priority`). `__init__` scopes `session` to
    `TrainingSession.objects.filter(tenant=self.tenant).exclude(status__in=("cancelled",
    "postponed"))` (auto-scoped tenant + a sane active-session default; `employee`/`nominated_by` are
    already tenant-scoped by the `TenantModelForm` base). `clean()`: explicit `(tenant, session,
    employee)` duplicate guard — `TrainingNomination.objects.filter(tenant=self.tenant,
    session=cleaned["session"], employee=cleaned["employee"]).exclude(pk=self.instance.pk).exists()`
    → raise on `employee` ("This employee is already nominated for this session.").
  - `TrainingAttendanceForm` (`TenantModelForm`; excludes `tenant`; fields: `session`, `employee`,
    `nomination`, `attendance_status`, `completion_status`, `check_in_at`, `check_out_at`, `notes`).
    `__init__` scopes `nomination` to `TrainingNomination.objects.filter(tenant=self.tenant,
    status__in=("approved", "waitlisted"))` (only real, decided nominations in the dropdown). Same
    `(tenant, session, employee)` duplicate-guard `clean()` as above.
  - `TrainingFeedbackForm` (`TenantModelForm`; excludes `tenant`, `attendance` — set from the URL in
    the nested create view; fields: `overall_rating`, `content_rating`, `trainer_rating`,
    `would_recommend`, `comments`, `is_anonymous`). `clean()`: explicit `(tenant, attendance)`
    duplicate guard — `TrainingFeedback.objects.filter(tenant=self.tenant,
    attendance=self.instance.attendance).exclude(pk=self.instance.pk).exists()` → raise on
    `__all__`/a non-field error ("Feedback has already been submitted for this attendance record.")
    — **the THIRD gotcha application**, see the GOTCHA note above; the view must set
    `form.instance.attendance = attendance` (and `.tenant`) BEFORE calling `form.is_valid()` so this
    `clean()` has something to check against.
  - `TrainingCertificateForm` (`TenantModelForm`; excludes `tenant`, `number`, `verification_code`,
    `expires_on`, `status`, `revoked_reason`; fields: `employee`, `course`, `source_attendance`,
    `source_progress`, `title`, `issued_on`). `__init__` scopes `course` to
    `TrainingCourse.objects.filter(tenant=self.tenant).filter(Q(is_certification=True) |
    Q(pk=self.instance.course_id))` (only certification-granting courses in the dropdown, but an
    existing edited row's course stays selectable even if it's since been unmarked). ONE form serves
    all three create entry points (flat + the two "issue from ..." convenience routes) — the nested
    routes pass `initial=` (pre-selected but still-editable dropdown values), not `instance=`
    pre-sets, so no unique-together gotcha applies here (only `unique_together=(tenant, number)`,
    whose `number` is never a form field anyway — the standard, already-safe `TenantNumbered`
    pattern used everywhere in this codebase).
- [ ] **views.py** — function-based, `@login_required`, tenant-scoped throughout:
  - **TrainingNomination:**
    - `trainingnomination_list` — `crud_list`, `search_fields=["number", "session__course__title",
      "employee__party__name", "justification"]`, `filters=[("status", "status", False), ("session",
      "session_id", True), ("employee", "employee_id", True), ("nomination_type", "nomination_type",
      False)]`, `extra_context={"status_choices": TrainingNomination.STATUS_CHOICES,
      "nomination_type_choices": TrainingNomination.NOMINATION_TYPE_CHOICES, "sessions":
      TrainingSession.objects.filter(tenant=request.tenant).order_by("-start_datetime"), "employees":
      EmployeeProfile.objects.filter(tenant=request.tenant).order_by("party__name")}`.
    - `trainingnomination_create` — `crud_create`, `success_url="hrm:trainingnomination_list"`.
    - `trainingnomination_detail` — `crud_detail`, `select_related=("session__course",
      "employee__party", "nominated_by__party", "approver__party")`.
    - `trainingnomination_edit` — manual wrapper around `crud_edit`: pre-check `if obj.status !=
      "pending": messages.error(...); return redirect("hrm:trainingnomination_detail", pk=obj.pk)`
      before delegating (only an undecided nomination is freely editable).
    - `trainingnomination_delete` — manual (mirrors `leaverequest_delete`'s guard): block delete when
      `status in ("approved", "waitlisted")` (message: "A decided nomination cannot be deleted —
      cancel or withdraw it instead."); otherwise `write_audit_log` + delete + redirect to list.
    - `_can_decide_nomination(request, obj)` — local helper: `_is_admin(request.user) or
      (profile is not None and obj.employee.employment_id and
      obj.employee.employment.manager_id == profile.party_id)` (`profile =
      _current_employee_profile(request)`) — lets a tenant admin OR the nominee's own manager decide,
      per the brief's "approve/reject `@tenant_admin_required` or manager".
    - `trainingnomination_approve(request, pk)` — `@login_required`, `@require_POST`; 403/redirect
      with an error message if `not _can_decide_nomination(...)`; only if `status == "pending"`:
      compute `full = obj.session.is_full`; if not full → `status="approved"`; elif
      `obj.session.waitlist_enabled` → `status="waitlisted"` (+ an info message explaining why);
      else → stay `pending` + `messages.error("Session is full and waitlisting is disabled.")` (no
      state change); on an actual transition set `approver=profile`, `approved_at=timezone.now()`,
      `write_audit_log`.
    - `trainingnomination_reject(request, pk)` — same permission guard; `status in ("pending",
      "waitlisted")` → `rejected`, `rejected_reason=request.POST.get("rejected_reason", "").strip()`,
      `approver=profile`.
    - `trainingnomination_waitlist(request, pk)` — `@tenant_admin_required` (admin-only manual
      override, unlike approve/reject); `status == "pending"` → `waitlisted` regardless of current
      capacity (an admin deliberately queues someone).
    - `trainingnomination_cancel(request, pk)` — `@login_required`; allowed for `_can_decide_nomination`
      OR the original `nominated_by`; `status in ("pending", "approved", "waitlisted")` → `cancelled`,
      `cancelled_reason=request.POST.get(...)`.
    - `trainingnomination_withdraw(request, pk)` — `@login_required`, nominee-only self-service
      (`profile is not None and profile.pk == obj.employee_id`); `status in ("pending", "approved",
      "waitlisted")` → `withdrawn`, `cancelled_reason` reused for the withdrawal note.
  - **TrainingAttendance:**
    - `trainingattendance_list` — `crud_list`, `search_fields=["session__course__title",
      "employee__party__name", "notes"]`, `filters=[("attendance_status", "attendance_status",
      False), ("completion_status", "completion_status", False), ("session", "session_id", True),
      ("employee", "employee_id", True)]`, `extra_context={"attendance_status_choices": ...,
      "completion_status_choices": ..., "sessions": ..., "employees": ...}`.
    - `trainingattendance_create` — `crud_create`, `success_url="hrm:trainingattendance_list"`.
    - `trainingattendance_detail` — `crud_detail`, `select_related=("session__course",
      "employee__party", "nomination")`; template surfaces an "Issue Certificate" button when
      `completion_status == "completed"` and `session.course.is_certification` and no
      `certificates_issued` row already exists for this attendance, linking to
      `trainingcertificate_issue_from_attendance`. Also a "Leave Feedback" link to
      `trainingfeedback_create` (attendance_pk) when no `feedback` row exists yet.
    - `trainingattendance_edit` — `crud_edit`, `success_url="hrm:trainingattendance_list"`.
    - `trainingattendance_delete` — `crud_delete`, `success_url="hrm:trainingattendance_list"`.
    - `trainingattendance_roster(request, session_pk)` — **OPTIONAL/stretch**, see the model note.
  - **TrainingFeedback:**
    - `trainingfeedback_create(request, attendance_pk)` — **nested**, mirrors
      `learningcontentitem_create`: `attendance = get_object_or_404(TrainingAttendance,
      pk=attendance_pk, tenant=request.tenant)`; builds the form with `instance=TrainingFeedback(
      tenant=request.tenant, attendance=attendance)` (tenant + parent set BEFORE validation — the
      form's `clean()` duplicate-guard still fires because it queries the DB directly, not because of
      pre-setting the instance); on success `write_audit_log` + redirect to
      `hrm:trainingattendance_detail` (pk=attendance.pk).
    - `trainingfeedback_list` — `crud_list`, `search_fields=["attendance__session__course__title",
      "comments"]`, `filters=[("would_recommend", "would_recommend", False), ("session",
      "attendance__session_id", True)]`, `extra_context={"sessions": ..., "is_admin":
      _is_admin(request.user)}` — list template masks `row.attendance.employee` behind "Anonymous"
      when `row.giver_anonymized and not is_admin`.
    - `trainingfeedback_detail` — `crud_detail`, `select_related=("attendance__session__course",
      "attendance__employee__party")`; `extra_context={"is_admin": _is_admin(request.user)}`, same
      masking rule.
    - `trainingfeedback_edit` — `crud_edit`, `success_url="hrm:trainingfeedback_list"`.
    - `trainingfeedback_delete` — `crud_delete`, `success_url="hrm:trainingfeedback_list"`.
  - **TrainingCertificate:**
    - `trainingcertificate_list` — `crud_list`, `search_fields=["number", "title",
      "verification_code", "employee__party__name", "course__title"]`, `filters=[("status", "status",
      False), ("course", "course_id", True), ("employee", "employee_id", True)]`,
      `extra_context={"status_choices": ..., "courses": TrainingCourse.objects.filter(tenant=
      request.tenant, is_certification=True).order_by("title"), "employees": ...}`.
    - `trainingcertificate_create` — `crud_create`, `success_url="hrm:trainingcertificate_list"`
      (flat/manual admin issuance path, `initial={"issued_on": timezone.localdate()}`).
    - `trainingcertificate_issue_from_attendance(request, attendance_pk)` — GET/POST; tenant-scoped
      lookup; guard `attendance.completion_status == "completed"` and
      `attendance.session.course.is_certification` (else `messages.error` + redirect to
      `hrm:trainingattendance_detail`); builds `TrainingCertificateForm` with `initial={"employee":
      attendance.employee_id, "course": attendance.session.course_id, "source_attendance":
      attendance.pk, "issued_on": timezone.localdate(), "title":
      attendance.session.course.certification_name}`; on success redirect to the new certificate's
      detail.
    - `trainingcertificate_issue_from_progress(request, progress_pk)` — same shape, guards
      `progress.status == "completed"` and `progress.course.is_certification`; `initial={"employee":
      progress.employee_id, "course": progress.course_id, "source_progress": progress.pk,
      "issued_on": timezone.localdate(), "title": progress.course.certification_name}`.
    - `trainingcertificate_detail` — `crud_detail`, `select_related=("employee__party", "course",
      "source_attendance__session", "source_progress")`; surfaces `obj.is_expired`,
      `verification_code`, a "Print" link (`trainingcertificate_print`) when `status == "issued"`, a
      "Revoke" action when `status == "issued"`.
    - `trainingcertificate_edit` — `crud_edit`, `success_url="hrm:trainingcertificate_list"`.
    - `trainingcertificate_delete` — manual, guarded: block delete when `status == "issued"` (message:
      "An issued certificate cannot be deleted — revoke it instead."); allow when `status ==
      "revoked"` (audit-trail integrity, matches the Arlo/Cornerstone research finding on full
      certificate audit trails).
    - `trainingcertificate_revoke(request, pk)` — `@tenant_admin_required`, `@require_POST`; `status
      == "issued"` → `revoked`, `revoked_reason=request.POST.get(...)`, `write_audit_log`.
    - `trainingcertificate_print(request, pk)` — `@login_required`, GET-only, tenant-scoped; renders
      `hrm/trainingadmin/trainingcertificate/print.html` (no sidebar, print-friendly layout, mirrors
      `hrm/offboarding/relieving_letter.html`'s standalone-print convention) — a pure render, no
      side effect (unlike `separationcase_generate_relieving_letter`, which is POST + creates an
      `EmployeeDocument`; this pass has no document-generation mechanism, just a printable page of
      the stored fields + `verification_code`).
  - **`training_budget(request)`** — standalone `GET`-only computed view (covers **Training Budget**,
    no model): `?year=` GET param (default current year via `timezone.localdate().year`); year-choices
    dropdown from `TrainingSession.objects.filter(tenant=request.tenant).dates("start_datetime",
    "year")`. Tenant-wide totals: `TrainingSession.objects.filter(tenant=request.tenant,
    start_datetime__year=year).aggregate(total_estimated=Sum("estimated_cost"),
    total_actual=Sum("actual_cost"))`; total allocated =
    `CostCenterProfile.objects.filter(tenant=request.tenant,
    budget_year=year).aggregate(Sum("budget_annual"))`. Per-cost-center breakdown: for each
    `CostCenterProfile.objects.filter(tenant=request.tenant, budget_year=year,
    is_active=True).select_related("org_unit")`, actual spend = `TrainingSession.objects.filter(
    tenant=request.tenant, start_datetime__year=year,
    attendance_records__employee__employment__org_unit__department_profile__cost_center_id=
    cc.org_unit_id).distinct().aggregate(Sum("actual_cost"))` (the join path: session →
    attendance_records → employee → employment.org_unit (department) → department_profile.cost_center
    → this cost center) — **flag for `performance-reviewer`**: this is one query per cost center,
    acceptable for typical cost-center cardinality (single digits/low tens per tenant) but note it as
    a batch-with-`annotate()` follow-up if a tenant ever has dozens. Passes `rows` (cost center, name,
    allocated, actual, estimated, variance, utilization %) + tenant-wide totals to the template.
  - **Cross-touch (existing 3.22 file):** extend `trainingsession_detail`'s context with
    `nominations=obj.nominations.select_related("employee__party").all()` and
    `attendance=obj.attendance_records.select_related("employee__party").all()`, plus "Nominate
    someone" / "Mark attendance" links — a one-line view change + a template addition to the
    ALREADY-BUILT `templates/hrm/training/trainingsession/detail.html`.
  - **Cross-touch (existing 3.23 file):** extend `learningprogress_detail`'s context with an "Issue
    Certificate" button (same eligibility guard as the standalone view: `status == "completed"` and
    `course.is_certification` and no existing `certificates_issued` row) linking to
    `trainingcertificate_issue_from_progress` — a one-line view change + a template addition to the
    ALREADY-BUILT `templates/hrm/lms/learningprogress/detail.html`.
- [ ] **urls.py** — `app_name = "hrm"` (already set); add under a `# 3.24 Training Administration`
  comment block:
  ```
  path("training-nominations/", views.trainingnomination_list, name="trainingnomination_list"),
  path("training-nominations/add/", views.trainingnomination_create, name="trainingnomination_create"),
  path("training-nominations/<int:pk>/", views.trainingnomination_detail, name="trainingnomination_detail"),
  path("training-nominations/<int:pk>/edit/", views.trainingnomination_edit, name="trainingnomination_edit"),
  path("training-nominations/<int:pk>/delete/", views.trainingnomination_delete, name="trainingnomination_delete"),
  path("training-nominations/<int:pk>/approve/", views.trainingnomination_approve, name="trainingnomination_approve"),
  path("training-nominations/<int:pk>/reject/", views.trainingnomination_reject, name="trainingnomination_reject"),
  path("training-nominations/<int:pk>/waitlist/", views.trainingnomination_waitlist, name="trainingnomination_waitlist"),
  path("training-nominations/<int:pk>/cancel/", views.trainingnomination_cancel, name="trainingnomination_cancel"),
  path("training-nominations/<int:pk>/withdraw/", views.trainingnomination_withdraw, name="trainingnomination_withdraw"),

  path("training-attendance/", views.trainingattendance_list, name="trainingattendance_list"),
  path("training-attendance/add/", views.trainingattendance_create, name="trainingattendance_create"),
  path("training-attendance/<int:pk>/", views.trainingattendance_detail, name="trainingattendance_detail"),
  path("training-attendance/<int:pk>/edit/", views.trainingattendance_edit, name="trainingattendance_edit"),
  path("training-attendance/<int:pk>/delete/", views.trainingattendance_delete, name="trainingattendance_delete"),
  path("training-sessions/<int:session_pk>/attendance/roster/", views.trainingattendance_roster, name="trainingattendance_roster"),

  path("training-attendance/<int:attendance_pk>/feedback/add/", views.trainingfeedback_create, name="trainingfeedback_create"),
  path("training-feedback/", views.trainingfeedback_list, name="trainingfeedback_list"),
  path("training-feedback/<int:pk>/", views.trainingfeedback_detail, name="trainingfeedback_detail"),
  path("training-feedback/<int:pk>/edit/", views.trainingfeedback_edit, name="trainingfeedback_edit"),
  path("training-feedback/<int:pk>/delete/", views.trainingfeedback_delete, name="trainingfeedback_delete"),

  path("training-certificates/", views.trainingcertificate_list, name="trainingcertificate_list"),
  path("training-certificates/add/", views.trainingcertificate_create, name="trainingcertificate_create"),
  path("training-attendance/<int:attendance_pk>/issue-certificate/", views.trainingcertificate_issue_from_attendance, name="trainingcertificate_issue_from_attendance"),
  path("learning-progress/<int:progress_pk>/issue-certificate/", views.trainingcertificate_issue_from_progress, name="trainingcertificate_issue_from_progress"),
  path("training-certificates/<int:pk>/", views.trainingcertificate_detail, name="trainingcertificate_detail"),
  path("training-certificates/<int:pk>/edit/", views.trainingcertificate_edit, name="trainingcertificate_edit"),
  path("training-certificates/<int:pk>/delete/", views.trainingcertificate_delete, name="trainingcertificate_delete"),
  path("training-certificates/<int:pk>/revoke/", views.trainingcertificate_revoke, name="trainingcertificate_revoke"),
  path("training-certificates/<int:pk>/print/", views.trainingcertificate_print, name="trainingcertificate_print"),

  path("training-budget/", views.training_budget, name="training_budget"),
  ```
  (`trainingattendance_roster` stays in the file even if the OPTIONAL view is deferred — remove the
  line if the view isn't built this pass, don't ship a dangling URL.)
- [ ] **admin.py** — register all four models:
  - `TrainingNominationAdmin`: `list_display = ("number", "session", "employee", "nomination_type",
    "status", "tenant")`; `list_filter = ("tenant", "status", "nomination_type")`; `search_fields =
    ("number", "session__course__title", "employee__party__name")`; `raw_id_fields = ("session",
    "employee", "nominated_by", "approver")`; `readonly_fields = ("number", "created_at",
    "updated_at")`
  - `TrainingAttendanceAdmin`: `list_display = ("session", "employee", "attendance_status",
    "completion_status", "tenant")`; `list_filter = ("tenant", "attendance_status",
    "completion_status")`; `search_fields = ("session__course__title", "employee__party__name")`;
    `raw_id_fields = ("session", "employee", "nomination")`; `readonly_fields = ("created_at",
    "updated_at")`
  - `TrainingFeedbackAdmin`: `list_display = ("attendance", "overall_rating", "trainer_rating",
    "would_recommend", "is_anonymous", "tenant")`; `list_filter = ("tenant", "would_recommend",
    "is_anonymous")`; `search_fields = ("attendance__session__course__title",)`; `raw_id_fields =
    ("attendance",)`; `readonly_fields = ("created_at", "updated_at")`
  - `TrainingCertificateAdmin`: `list_display = ("number", "employee", "course", "status",
    "issued_on", "expires_on", "tenant")`; `list_filter = ("tenant", "status")`; `search_fields = (
    "number", "title", "verification_code", "employee__party__name", "course__title")`;
    `raw_id_fields = ("employee", "course", "source_attendance", "source_progress")`;
    `readonly_fields = ("number", "verification_code", "expires_on", "created_at", "updated_at")`
- [ ] **migrations** — `python manage.py makemigrations hrm` — expect a `0040_...` migration creating
  all four models (no schema change from the `TrainingSession` property cross-touch or the
  `_advance_months` refactor — those don't touch the DB).
- [ ] **seed_hrm.py** — new `_seed_trainingadmin(self, tenant, *, flush)` method:
  - Called from `handle()` immediately after `self._seed_lms(tenant, flush=options["flush"])` (the
    22nd call in the per-tenant loop).
  - `if flush:` delete in order: `TrainingCertificate`, `TrainingFeedback`, `TrainingAttendance`,
    `TrainingNomination` — filtered by `tenant`.
  - Idempotency guards: `sessions = list(TrainingSession.objects.filter(tenant=tenant)
    .select_related("course").order_by("start_datetime"))` — if empty, NOTICE "Training sessions
    missing for '{tenant}' - run the training seed first; skipping training-admin seed." + return.
    `emps = list(EmployeeProfile.objects.filter(tenant=tenant).select_related("party")
    .order_by("party__name"))` — if `len(emps) < 2`, NOTICE + return. Then `if
    TrainingNomination.objects.filter(tenant=tenant).exists():` → NOTICE + return.
  - Reuse the EXISTING sessions from `_seed_training` (3.22) by lookup, not by index (session order
    isn't guaranteed): `session_a = TrainingSession.objects.filter(tenant=tenant,
    course__title="Technical Onboarding Bootcamp", venue_name="HQ Training Room A").first()`
    (day+7 classroom), `session_b = TrainingSession.objects.filter(tenant=tenant,
    course__title="Technical Onboarding Bootcamp", venue_name="HQ Training Room B").first()`
    (day+14 classroom repeat), `session_safety = TrainingSession.objects.filter(tenant=tenant,
    course__title="Workplace Safety Certification").first()` (day+10 virtual, confirmed),
    `session_leadership = TrainingSession.objects.filter(tenant=tenant,
    course__title="Leadership Excellence Program", status="completed").first()` (day-20 external,
    the only COMPLETED session in the existing 3.22 seed). If any of these four is `None`, NOTICE +
    return (defensive — the 3.22 seed's exact shape not present).
  - Also reuse the 3.23-seeded `progress_safety = LearningProgress.objects.filter(tenant=tenant,
    employee=emps[0], course__title="Workplace Safety Certification", status="completed").first()`
    for the certificate-from-progress demo (may be `None` if `_seed_lms` was skipped — degrade
    gracefully, skip that one certificate row if so, don't hard-fail the whole method).
  - Demo data — **`TrainingNomination`** (6 rows, using up to 3 employees, degrading gracefully with
    `if len(emps) > 2:` guards exactly like `_seed_lms`; every (session, employee) pair distinct to
    respect the `unique_together`):
    - `(session_a, emps[1])` — `self`, `approved`, `approver=emps[0]`, `approved_at=now`.
    - `(session_b, emps[0])` — `hr`, `approved`, `approver=emps[1]` if it exists else `None`,
      `approved_at=now` (demonstrates the "Assign as Required" HR-assigned path).
    - `(session_safety, emps[0])` — `self`, `waitlisted` (a directly-seeded demo state — not the
      product of running the real approve action against actual capacity, same convention as other
      seeders picking an illustrative status directly).
    - `(session_safety, emps[1])` — `manager`, `rejected`, `nominated_by=emps[0]` if role fits,
      `rejected_reason="Scheduling conflict with a client deliverable."`.
    - `(session_a, emps[2])` if it exists — `self`, `withdrawn`.
    - `(session_safety, emps[2])` if it exists — `manager`, `pending`, `nominated_by=emps[1]`.
  - Demo data — **`TrainingAttendance`** (up to 4 rows, on the one COMPLETED session
    `session_leadership` plus one upcoming `session_a` to show a pre-session `registered` row):
    - `(session_leadership, emps[0])` — `present` / `completed`, `check_in_at`/`check_out_at` set
      ~7 hours apart, `nomination=None`.
    - `(session_leadership, emps[1])` — `absent` / `not_completed`, no check-in/out.
    - `(session_leadership, emps[2])` if it exists — `walk_in` / `completed`, `nomination=None`,
      `notes="Walked in without prior registration."`.
    - `(session_a, emps[1])` — `registered` / `not_completed`, `nomination=` the `(session_a,
      emps[1])` approved nomination row above (demonstrates the nomination→attendance link).
  - Demo data — **`TrainingFeedback`** (nested under the `completed` attendance rows only):
    - Under `(session_leadership, emps[0])`'s attendance: `overall_rating=5`, `content_rating=4`,
      `trainer_rating=5`, `would_recommend=True`,
      `comments="Excellent leadership program, very practical."`, `is_anonymous=False`.
    - Under `(session_leadership, emps[2])`'s attendance, if it exists: `overall_rating=3`,
      `content_rating=3`, `trainer_rating=4`, `would_recommend=False`,
      `comments="Content felt rushed for a walk-in."`, `is_anonymous=True` (exercises the
      mask-on-render path).
  - Demo data — **`TrainingCertificate`** (2 rows, both on the Safety course — the only
    `is_certification=True` course in the existing 3.22/3.23 seed; the `source_attendance` path isn't
    exercised here since no existing COMPLETED ILT session grants a certification course — noted as a
    seeder limitation, covered instead by `test-writer`'s purpose-built fixture):
    - `employee=emps[0]`, `course=safety`, `source_progress=progress_safety` (if found),
      `title="Certified Safety Associate"`, `issued_on=today`, `status="issued"` — `expires_on` is
      computed automatically in `save()`.
    - `employee=emps[1]` (if it exists, else reuse `emps[0]`), `course=safety`,
      `source_attendance=None`, `source_progress=None` (the flat/manual path), `title="Certified
      Safety Associate (Manual Issue)"`, `issued_on=today - 60 days`, `status="revoked"`,
      `revoked_reason="Issued in error - employee had not completed the certification exam."`
      (exercises the revoke state + the no-source manual-issuance path in one row).
  - **CRITICAL — Windows cp1252 console bug (repeat of the 3.20/3.21/3.22/3.23 bug):** ASCII-only
    `self.stdout.write(...)` strings (`->` not `→`, plain hyphen not em-dash, no `·`/`—`). Re-read the
    whole method for stray Unicode before committing.
  - Update `_seed_tenant`'s big flush-teardown tuple: insert `TrainingCertificate, TrainingFeedback,
    TrainingAttendance, TrainingNomination,` immediately BEFORE the existing `# 3.23:
    LearningPathItem.course...` comment / `LearningProgress, LearningPathItem, LearningPath,
    LearningContentItem,` line, with a comment: `# 3.24: TrainingNomination.session/
    TrainingAttendance.session are PROTECT - wipe before TrainingSession below;
    TrainingCertificate.employee/course and TrainingAttendance.employee/TrainingNomination.employee
    are PROTECT - wipe before EmployeeProfile (much later in this tuple); TrainingFeedback.attendance
    is CASCADE (auto-clears with its attendance) but listed explicitly for a clean, explicit teardown;
    TrainingCertificate.source_attendance/source_progress are SET_NULL (order-agnostic).`
  - Both `management/__init__.py` and `management/commands/__init__.py` already exist (no new dirs
    this pass) — verify, don't recreate.

## Wire-up

- [ ] `config/settings.py` — `apps.hrm` already in `INSTALLED_APPS` (no change needed this pass).
- [ ] `config/urls.py` — `hrm/` include already wired (no change needed this pass).
- [ ] `apps/core/navigation.py` `LIVE_LINKS["3.24"]` — new block mapping the 5 exact NavERP.md 3.24
  bullets (confirmed verbatim from `NavERP.md` lines 601–606), placed immediately after the existing
  `"3.23"` block, with a preamble comment noting Training Budget is computed, not a model:
  ```python
  # 3.24 Training Administration — the operational/admin layer on top of 3.22 (TrainingSession) and
  # 3.23 (LearningProgress); it does not re-model the course catalog, the ILT occurrence, or self-paced
  # progress. "Training Budget" is a COMPUTED aggregate view (TrainingSession.actual_cost /
  # CostCenterProfile.budget_annual) — no stored model. This is the final sub-module of the 3.22/3.23/
  # 3.24 training cluster.
  "3.24": {
      "Nomination": "hrm:trainingnomination_list",                # bullet (TrainingNomination CRUD + approval workflow)
      "Attendance Tracking": "hrm:trainingattendance_list",        # bullet (TrainingAttendance CRUD)
      "Training Feedback": "hrm:trainingfeedback_list",            # bullet (TrainingFeedback CRUD)
      "Certificates": "hrm:trainingcertificate_list",              # bullet (TrainingCertificate CRUD + issue/revoke/print)
      "Training Budget": "hrm:training_budget",                    # bullet (computed budget aggregate view)
  },
  ```

## Templates (templates/hrm/trainingadmin/)

- [ ] **New sub-module folder `trainingadmin/`** (per the Template Folder Structure rule — 3.24 is a
  distinct NavERP.md sub-module from `training/`/`lms/`), with one entity folder per model:
- [ ] `templates/hrm/trainingadmin/trainingnomination/list.html` — filter bar (`status`,
  `nomination_type`, `session`, `employee` dropdowns reflecting `request.GET`; FK/pk comparison via
  `|stringformat:"d"`), status badges matching the exact 6 CHOICES values, Actions column
  (view/edit/delete-POST+confirm+csrf + inline Approve/Reject/Waitlist/Cancel/Withdraw buttons gated
  on `obj.status`), pagination, empty-state.
- [ ] `templates/hrm/trainingadmin/trainingnomination/detail.html` — session/employee/nominator
  links, status badge, decision fields (`approver`, `approved_at`, `rejected_reason`) shown only when
  populated, Actions sidebar with the same workflow buttons as the list row (each its own POST form +
  `{% csrf_token %}` + `confirm()`), Back to List link.
- [ ] `templates/hrm/trainingadmin/trainingnomination/form.html` — create/edit (shared, `is_edit`
  flag); no workflow fields shown (those are action-only).
- [ ] `templates/hrm/trainingadmin/trainingattendance/list.html` — filter bar (`attendance_status`,
  `completion_status`, `session`, `employee`), status badges, Actions column.
- [ ] `templates/hrm/trainingadmin/trainingattendance/detail.html` — session/employee/nomination
  links, check-in/out times, the conditional "Issue Certificate" / "Leave Feedback" links described
  above, Actions sidebar.
- [ ] `templates/hrm/trainingadmin/trainingattendance/form.html` — create/edit.
- [ ] `templates/hrm/trainingadmin/trainingfeedback/list.html` — filter bar (`would_recommend`,
  `session`), rating stars/badges, attendee name masked to "Anonymous" per-row when
  `row.giver_anonymized and not is_admin`, Actions column.
- [ ] `templates/hrm/trainingadmin/trainingfeedback/detail.html` — masked-or-real attendee identity
  (same rule, using the `is_admin` context var), the 3 ratings, would-recommend, comments, Actions
  sidebar (Back to attendance).
- [ ] `templates/hrm/trainingadmin/trainingfeedback/form.html` — nested create/edit (`attendance`
  shown read-only as context on the create form, not a field).
- [ ] `templates/hrm/trainingadmin/trainingcertificate/list.html` — filter bar (`status`, `course`,
  `employee`), status badges (issued/revoked/expired) rendered from **`obj.is_expired`** first (live
  truth) with the stored `status` as a secondary badge — matches the design-tension note above,
  Actions column + "Print" link when `status == "issued"`.
- [ ] `templates/hrm/trainingadmin/trainingcertificate/detail.html` — employee/course/source links
  (whichever of `source_attendance`/`source_progress` is set), `verification_code`, `issued_on`/
  `expires_on`, the live `is_expired` badge, Actions sidebar (Edit, Revoke when `status=="issued"`,
  Delete only when `status=="revoked"`, Print, Back to List).
- [ ] `templates/hrm/trainingadmin/trainingcertificate/form.html` — create/edit (shared by the flat
  create AND the two "issue from ..." routes, since they all post to the same form shape with
  different `initial=`).
- [ ] `templates/hrm/trainingadmin/trainingcertificate/print.html` — standalone print-friendly layout
  (NO `{% extends "base.html" %}` sidebar chrome — mirrors `hrm/offboarding/relieving_letter.html`):
  certificate title, employee name, course/certification name, issued/expiry dates,
  `verification_code`, a "Print this page" JS button (`window.print()`).
- [ ] `templates/hrm/trainingadmin/budget.html` — standalone page (sub-module-root, NO entity folder,
  per Template Folder Structure rule §6): year filter dropdown, tenant-wide totals card
  (allocated/estimated/actual/variance), per-cost-center breakdown table, empty-state when no
  `CostCenterProfile` rows exist for the selected year.
- [ ] **OPTIONAL** `templates/hrm/trainingadmin/trainingattendance/roster.html` — only if the
  OPTIONAL `trainingattendance_roster` view is built this pass.
- [ ] **Cross-touch:** `templates/hrm/training/trainingsession/detail.html` (existing 3.22 file) —
  add "Nominations" and "Attendance" sections (name, status/attendance badges) + "Nominate someone" /
  "Mark attendance" links.
- [ ] **Cross-touch:** `templates/hrm/lms/learningprogress/detail.html` (existing 3.23 file) — add
  the conditional "Issue Certificate" button described above.

## Verify

- [ ] `python manage.py makemigrations hrm` — expect a new `0040_...` migration; review the generated
  file before applying (confirm no unwanted schema diff from the `TrainingSession` property
  cross-touch or the `_advance_months` refactor — neither should appear in the migration at all).
- [ ] `python manage.py migrate`
- [ ] `python manage.py seed_hrm` — run twice; second run must be a no-op (NOTICE message, zero new
  rows) proving idempotency.
- [ ] `python manage.py check` — zero errors/warnings.
- [ ] `temp/` smoke sweep — all `hrm:trainingnomination_*` (incl. approve/reject/waitlist/cancel/
  withdraw), `hrm:trainingattendance_*`, `hrm:trainingfeedback_*`, `hrm:trainingcertificate_*` (incl.
  issue-from-attendance/issue-from-progress/revoke/print), `hrm:training_budget` URLs return 200/302
  (never 500); no `{#`/`{% comment` template-comment leaks in rendered output; cross-tenant IDOR check
  (a tenant-B admin hitting a tenant-A row's pk on any of the 4 models' detail/edit/delete/action URLs
  returns 404, not the object — INCLUDING every nested/action route: `training-attendance/<tenant-A
  attendance pk>/feedback/add/`, `training-attendance/<tenant-A pk>/issue-certificate/`,
  `learning-progress/<tenant-A progress pk>/issue-certificate/`, and every `/approve/`, `/reject/`,
  `/waitlist/`, `/cancel/`, `/withdraw/`, `/revoke/` action against a tenant-A pk while logged in as
  tenant B must 404, not silently act on a cross-tenant row); explicit duplicate checks via the
  CREATE VIEWS (not just the ORM) for all three GOTCHA forms
  (`TrainingNominationForm`/`TrainingAttendanceForm`/`TrainingFeedbackForm`) — a second submission for
  the same `(session, employee)`/`(session, employee)`/`attendance` must show a form validation error,
  not a 500; nomination capacity/waitlist logic (`trainingnomination_approve` against a full session
  with `waitlist_enabled=True` sets `waitlisted`, not `approved`; against a full session with
  `waitlist_enabled=False` stays `pending` with an error message); `TrainingFeedback.is_anonymous`
  masking verified as an admin (sees the real name) vs. a non-admin (sees "Anonymous"); certificate
  `expires_on`/`is_expired` boundary check (day before/after expiry) and the `is_expired`-vs-stored-
  `status` design-tension note actually rendered correctly in the list/detail badges.
- [ ] Sidebar shows all 5 new 3.24 sub-module bullets as **Live** (Nomination, Attendance Tracking,
  Training Feedback, Certificates, Training Budget) — confirm via the rendered sidebar, not just the
  `LIVE_LINKS` dict. This completes the FULL 3.22/3.23/3.24 training cluster (all 15 NavERP.md bullets
  across the 3 sub-modules now live).

## Close-out

- [ ] Run the 7 review agents in order, applying findings + committing after each (one file per
  commit, no `git push`): `code-reviewer` -> `explorer` -> `frontend-reviewer` ->
  `performance-reviewer` -> `qa-smoke-tester` -> `security-reviewer` -> `test-writer`.
  - Expect `code-reviewer` to double-check all THREE duplicate-guard forms
    (`TrainingNominationForm`/`TrainingAttendanceForm`/`TrainingFeedbackForm`) actually got the
    explicit `clean()` fix (see the GOTCHA note above) rather than re-discovering the pattern fresh a
    fourth time; also to sanity-check the `_advance_months` extraction didn't change
    `LearningProgress.certification_expires_on`'s existing behavior (no regression on 3.23's own
    tests).
  - Expect `performance-reviewer` to check `trainingnomination_list`/`trainingattendance_list`/
    `trainingfeedback_list`/`trainingcertificate_list`/`training_budget` for N+1s (select_related on
    every FK the template renders) and to weigh in on the `training_budget` per-cost-center loop
    flagged above (fine at typical cardinality; note if a batch-`annotate()` rewrite is warranted).
  - Expect `security-reviewer` to confirm: tenant scoping on every nested/action route (session_pk/
    attendance_pk/progress_pk always looked up with `tenant=request.tenant`); the manager-permission
    check (`_can_decide_nomination`) can't be bypassed by a non-manager POSTing directly to
    `/approve/`; `verification_code`'s `secrets.token_hex(8)` entropy is adequate for its purpose (not
    a security-critical secret, just a lookup key — no `|safe` on any user-supplied text field
    (`comments`, `justification`, `notes`, `revoked_reason`)).
  - Expect `test-writer` to cover: full CRUD round-trips × 4 models (incl. all nested/action routes);
    the nomination capacity/waitlist decision logic (under capacity → approved; at capacity +
    waitlist_enabled → waitlisted; at capacity + not waitlist_enabled → stays pending with an error);
    the manager-vs-admin-vs-neither permission matrix on approve/reject/cancel/withdraw; all THREE
    duplicate-guard forms' create-path regression pins; `TrainingCertificate.clean()`'s
    both-sources-set rejection AND the cross-consistency checks (mismatched employee/course via
    source_attendance or source_progress); `expires_on`/`is_expired` at exact boundary dates
    (including the "no certification_validity_months" and "course not is_certification" None-cases);
    `TrainingFeedback.giver_anonymized` masking (admin sees real name, non-admin sees "Anonymous",
    the underlying FK is never actually altered); the `_advance_months` shared helper (both call
    sites, LearningProgress AND TrainingCertificate, produce identical results for the same inputs,
    e.g. Jan 31 + 1 month == Feb 28/29 in both).
- [ ] Update `.claude/skills/hrm/SKILL.md`:
  - Add a `### 3.24 Training Administration (4 tables)` section (mirrors the existing per-sub-module
    section format) with the model table (fields, FK targets incl. the deliberate
    `approver`-as-`EmployeeProfile` deviation from `LeaveRequest`'s `AUTH_USER_MODEL` pattern, the
    `is_expired`-vs-stored-`status` design tension, the `_advance_months` shared-helper extraction),
    the nested/action routes, and the certificate no-`certificate_file`/no-`issued_by` design notes.
  - Bump the frontmatter/overview "built" sub-module list to include 3.24 and note the FULL 3.22/
    3.23/3.24 training cluster is now complete (all 15 bullets live).
  - Add a "Training Administration (3.24)" routes-list section (`hrm:trainingnomination_*` incl.
    workflow actions, `hrm:trainingattendance_*`, `hrm:trainingfeedback_*`,
    `hrm:trainingcertificate_*` incl. issue/revoke/print, `hrm:training_budget`).
  - Update the seeder section: document `_seed_trainingadmin(tenant)`, its own-exists guard (+ the
    "training AND LMS must already be seeded" dependency), what it creates, and that it runs LAST
    (after `_seed_lms`).
  - Update the `LIVE_LINKS` section: "3.24: Nomination -> `hrm:trainingnomination_list`; Attendance
    Tracking -> `hrm:trainingattendance_list`; Training Feedback -> `hrm:trainingfeedback_list`;
    Certificates -> `hrm:trainingcertificate_list`; Training Budget -> `hrm:training_budget` (computed,
    no model). All 5 NavERP.md 3.24 bullets are now live — the training cluster (3.22/3.23/3.24) is
    complete."
  - Update the "Deferred" section, replacing the old 3.24-placeholder line with 3.24's own
    carried-forward deferrals (see below).
  - Commit the SKILL.md update as its own file, per the one-file-per-commit rule.
- [ ] README (if the project keeps a root test-count/module-count summary) — refresh HRM test counts
  after `test-writer` runs, same pattern as the 3.20/3.21/3.22/3.23 README refresh commits.

## Later passes / deferred (carried over from research-hrm-3.24-training-administration.md)

- **Full N-step configurable approval-role engine** (SAP SuccessFactors Learning-style Manager
  L1/L2/HRBP chains) — this pass ships a single approver + manager-or-admin permission check; a
  role-chain engine is a distinct, reusable HRM-wide capability (leave/PIP/nomination could all use
  it), out of scope for one sub-module.
- **Rule-based auto-nomination / auto-enrollment** (assign training automatically when an employee
  joins a department/role, per Cornerstone's automated enrollment rules) — needs an event/trigger
  framework; this pass supports manual `hr`-type "assign as required" only.
- **QR-code / self-check-in kiosk flow** (Arlo, Cornerstone) — a device/scanning UI beyond a single
  Django CRUD pass; the `TrainingAttendance` row this pass creates is what such a flow would
  eventually write to.
- **Multi-level Kirkpatrick evaluation (L2 knowledge test / L3 on-the-job / L4 ROI) with delayed
  30/60/90-day follow-up surveys** — this pass ships only the Level-1 reaction form
  (`TrainingFeedback`); Level-2 knowledge checks already exist via `LearningContentItem
  (content_type="assessment")` (3.23).
- **Branded certificate template designer + PDF mail-merge rendering** — this pass ships the
  certificate RECORD (`number`, `verification_code`, dates, source links) + a login-gated print page;
  no PDF engine, no `certificate_file` upload field this pass (explicitly deferred, not silently
  dropped — see the model's design note above).
- **Public/anonymous certificate verification page** (a third party checks authenticity by
  `verification_code` without logging in) — this pass keeps `trainingcertificate_detail`/`_print`
  login-gated; a public verify-by-code endpoint is a distinct, smaller follow-up once the record shape
  is proven.
- **Certificate/nomination expiry and renewal email reminders** — needs the notification/scheduler
  infrastructure; the computed `expires_on`/`is_expired` fields this pass produces are what a reminder
  job would query. Also needed: the job that would auto-flip `status` to `expired` (see the
  design-tension note — nothing does this automatically yet).
- **Dedicated `TrainingBudget` allocation model** (a ring-fenced training-only sub-pool per
  department/period, separate from `CostCenterProfile.budget_annual`'s whole-department budget) —
  deferred; this pass ships utilization as a computed aggregate over `TrainingSession.actual_cost`/
  `estimated_cost` joined via `TrainingAttendance` to `core.OrgUnit`/`CostCenterProfile`. A true
  training-specific budget pool is a one-model follow-up if Finance later needs it.
- **Cost-vs-performance ROI reporting** (Training Orchestra's differentiator: budget × outcome score
  correlation) — needs both the `training_budget` aggregate and `TrainingFeedback`/`LearningProgress`
  outcome data joined; a reporting-pass concern once both sides have enough data.
- **Multi-currency training budget ALLOCATION** (Training Orchestra: per-site budgets in local
  currency) — the SPEND side already supports currency via `TrainingSession.currency`; a
  currency-aware allocation is deferred with the dedicated-budget-model item above.
- **Per-session bulk "mark attendance" roster UI** — flagged OPTIONAL above; if not built this pass,
  it's the first thing to pick up next for 3.24 (the underlying `TrainingAttendance` CRUD already
  supports it one row at a time).

## Review notes (3.24 — as-built)

Built the 4-model scope: `TrainingNomination` (NOM-, approval workflow), `TrainingAttendance`, `TrainingFeedback`
(Kirkpatrick-L1 + anonymity), `TrainingCertificate` (CERT-, issuance/revoke/print) + a computed `training_budget`
view (no model), all extending 3.22 sessions + 3.23 LMS. Shared `_advance_months` helper refactored out of
LearningProgress; `TrainingSession` gained `approved_nomination_count`/`is_full` cross-touch props; two detail
cross-touches (trainingsession + learningprogress). Migrations 0040 (models) + 0041 (perf index). Verified:
`manage.py check` clean, seeder idempotent, 24-URL smoke sweep + workflow POSTs + IDOR 404 + all 3 duplicate-guards.
The optional per-session roster UI was NOT built (base attendance CRUD covers it one row at a time).

**Module Creation Sequence — all 7 review agents run in order, findings applied & committed:**
- **code-reviewer** — 1 Critical (TrainingFeedback had NO ownership gate — added `_can_manage_feedback`) + 4
  Important (certificate duplicate-issuance guard; attendance-delete guard for feedback/cert refs; block editing a
  revoked cert; recompute expires_on on issued_on change; drop dead `redirect_ok` param).
- **explorer** — 1 real bug: `trainingsession_delete` had no ProtectedError guard but 3.24 added PROTECT children →
  500; fixed (+ generalized trainingcourse_delete's message to name certificates).
- **frontend-reviewer** — 8 fixes: cert Edit hidden on revoked; cert detail status badge honors is_expired; reject
  input aria-label + cancel/withdraw reason inputs; feedback Edit/Delete + attendance Leave-Feedback gated to
  giver/admin; budget floatformat:2.
- **performance-reviewer** — (tenant, completion_status) index (mig 0041); consistent select_related on the 5
  nomination workflow actions + cert revoke (audit-log str(obj) was firing extra queries); nomination-detail
  employee__employment; compute profile once; precompute obj.feedback.first().
- **qa-smoke-tester** — 67/67 checks passed, no defects.
- **security-reviewer** — 2 High: (1) certificate WRITE chain ungated → any employee could self-mark a completed
  attendance and self-issue a verifiable credential — fixed with `@tenant_admin_required` on
  create/edit/issue_from_*/delete (revoke already was) + hid the buttons; (2) attendance-detail "View Feedback" link
  de-anonymized anonymous feedback — hidden for non-admin/non-attendee. The Medium (attendance/nomination edit
  ownership) is an app-wide pattern (leaverequest_edit identical) — left consistent now that the credential step is
  admin-gated.
- **test-writer** — 317 tests (101 model/form + 146 view + 70 security), all green; full HRM suite 4212→4529, no
  regressions.

Skill `.claude/skills/hrm/SKILL.md` updated (models table, flow, routes, `trainingadmin/` templates, seeder,
LIVE_LINKS, fixed model count 81→89). **3.24 complete — the training cluster (3.22 ILT + 3.23 LMS + 3.24 Admin) is
done; next unbuilt HRM sub-module is 3.25 Personal Information (Self-Service).**
