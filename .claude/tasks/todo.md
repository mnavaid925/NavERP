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

---
# Module 3 — HRM — Sub-module 3.25 Personal Information (Self-Service) (hrm-3.25-personal-information) — plan from research-hrm-3.25-personal-information.md (2026-07-11)

**EXTENDS the existing `apps/hrm` app (already built through 3.24) — no new Django app, no new
`INSTALLED_APPS`/`config/urls.py` entries, next migration is `0042`.** Per the research's scope note,
this sub-module is the **Employee Self-Service (ESS) personal-information layer**, NOT a re-model of
`hrm.EmployeeProfile` — it does not duplicate the existing flat columns (bank/emergency-contact/address/
personal-file fields already on `EmployeeProfile`). It adds three proper **child tables** the flat/
2-slot columns can't model (unlimited emergency contacts, multiple bank accounts with one designated
salary account, family/dependent members) plus a **maker-checker change-request model** that gates the
sensitive fields (legal name, DOB, national ID, passport, all bank-account writes, all family-member
writes) behind HR approval while address/personal-email/mobile/emergency-contacts stay direct-edit.

**"My profile" resolution — ALREADY BUILT, reuse it, don't reinvent it:** `apps/hrm/views.py:7408`
already has `_current_employee_profile(request)` (`request.user.party` → reverse-O2O
`employee_profile`, `None`-safe for a user with no linked party/profile) and `apps/hrm/views.py:7733`
already has `_is_admin(user)` (`user.is_superuser or user.is_tenant_admin`). Every ESS view in this pass
uses these two existing helpers — no new resolution logic.

Reuses (never duplicates): `hrm.EmployeeProfile` (`current_address`/`permanent_address`/
`personal_email`/`work_email`/`mobile`/`national_id`/`passport_number`/`date_of_birth`/`photo` — the ESS
surface edits/reads these, doesn't re-model them), `EmployeeProfile._mask_last4` (ported/duplicated onto
`EmployeeBankAccount`, matching the existing per-model-duplication convention already used at
`EmployeeStatutoryIdentifier._mask_last4`, `models.py:3890`), `core.Party.name` (the actual legal-name
column — `EmployeeProfile.name` is a `@property` proxy, not a DB column, so the change-request `apply()`
special-cases `legal_name` to write `party.name`, not an `EmployeeProfile` column), `core.Employment`
(`org_unit`/`manager`/`job_title`/`hired_on` — the read-only employment context on the hub page, via the
already-existing `EmployeeProfile.department`/`.manager` properties), `django.contrib.contenttypes`
(`ContentType`/`GenericForeignKey` — the same pattern already used by `core.AuditLog`/`core.Activity`/
`core.Document`; this is the **first** use of a GenericForeignKey inside `apps/hrm` itself, so
`GenericForeignKey`/`ContentType` need fresh imports at the top of `apps/hrm/models.py`), the existing
`@tenant_admin_required` decorator (`apps/core/decorators.py`) for every admin-only write, and the
existing `EmployeeDocument.mark_verified`/`.reject` action-pair shape (`apps/hrm/views.py` — 3.1) as the
template for `EmployeeBankAccount`'s own verify/reject actions.

**Design decision (bridges the research's slightly different field lists — documented, not an
oversight):** the research catalog's per-model field lists (`change_type`/`field_name`/`old_value`/
`new_value`/`effective_date` on the change-request; `unverified`/`pending`/`verified` on
`verification_status`) are the earlier, more granular sketch; the task brief that launched this plan
refined them to a leaner shape (`field_changes` JSON instead of one-field-at-a-time rows so ONE request
can propose an entire new bank-account/family-member row in one shot; `pending`/`verified`/`rejected` on
`verification_status`, workflow-owned via dedicated verify/reject actions). This plan builds the
**leaner, task-brief shape** — it is a strict refinement of the research (same capabilities, fewer
fields), not a scope cut.

## Models (from research)

- [ ] **`EmergencyContact`** [`TenantOwned`] — covers **Emergency Contacts**. Direct self-edit, **no
  approval gate** (deliberate scope choice per the research catalog — matches the majority of the ten
  leaders surveyed).
  - `employee` — FK `hrm.EmployeeProfile`, `on_delete=CASCADE`, `related_name="emergency_contacts"`
    (a true owned child — deleted with the employee, unlike `TrainingNomination`'s `PROTECT`)
  - `name` — CharField(255)
  - `relationship` — CharField(100, blank=True) — free text, mirrors the existing
    `EmployeeProfile.emergency_contact_relation`'s free-text shape (driver: BambooHR/Zoho People/
    Darwinbox all show relationship as a short label, not a fixed enum)
  - `phone` — CharField(30); `alt_phone` — CharField(30, blank=True) (driver: BambooHR/Zoho People
    alt-phone field)
  - `email` — EmailField(blank=True); `address` — TextField(blank=True)
  - `is_primary` — BooleanField(default=False) — "which contact to call first" (driver: BambooHR,
    Workday primary/priority ordering)
  - `priority_order` — PositiveSmallIntegerField(default=1)
  - `notes` — TextField(blank=True)
  - `Meta.ordering = ["employee", "priority_order", "-is_primary"]`; index `(tenant, employee)`
    (`hrm_ec_tenant_emp_idx`)
  - `save()`: if `self.is_primary`, demote siblings first inside `transaction.atomic()` —
    `EmergencyContact.objects.filter(tenant_id=self.tenant_id, employee_id=self.employee_id,
    is_primary=True).exclude(pk=self.pk).update(is_primary=False)` — enforcing "one `True` per
    employee" the same auto-demote way `EmployeeBankAccount.is_salary_account` does below (consistent
    UX, no hard validation error).
  - `__str__`: `f"{self.name} ({self.relationship}) - {self.employee}"`
  - Reuses `hrm.EmployeeProfile` as parent; the flat `emergency_contact_*`/`emergency_contact_2_*`
    fields on `EmployeeProfile` stay as-is (legacy quick-reference, not migrated away this pass).

- [ ] **`EmployeeBankAccount`** [`TenantOwned`] — covers **Bank Details**. **All create/edit routes
  through `EmployeeInfoChangeRequest`** — the model's own create/edit/delete views are
  `@tenant_admin_required` (admin-direct management), never reachable by a plain employee (highest
  fraud-risk field group — every leader surveyed gates it).
  - `employee` — FK `hrm.EmployeeProfile`, `on_delete=CASCADE`, `related_name="bank_accounts"`
  - `bank_name` — CharField(255); `account_holder_name` — CharField(255)
  - `account_number` — CharField(64) — **WARNING: plaintext for demo purposes**, mirror the
    `EmployeeProfile.bank_account` note verbatim (encrypt at rest in production); NEVER rendered raw —
    only via `masked_account_number()`
  - `routing_number` — CharField(20, blank=True) — IFSC/ABA/sort-code equivalent
  - `account_type` — CharField choices, max_length=10, default `"checking"`: `checking` / `savings` /
    `other`
  - `is_salary_account` — BooleanField(default=False) — "exactly one designated salary account"
    (driver: greytHR single active Bank Account card, ADP, Gusto default account)
  - `split_percentage` — DecimalField(max_digits=5, decimal_places=2, null=True, blank=True,
    validators `[MinValueValidator(0), MaxValueValidator(100)]`) — Gusto-style split-deposit intent;
    stored only, NOT wired to any payroll-run disbursement math this pass (deferred — 3.14/3.17
    territory); **no cross-row "splits sum to 100%" validation this pass** (deliberately simple)
  - `verification_status` — CharField choices, max_length=10, default `"pending"`: `pending` /
    `verified` / `rejected` — workflow-owned via dedicated `employeebankaccount_verify`/`_reject`
    POST actions (`@tenant_admin_required`), mirroring the EXISTING `EmployeeDocument.mark_verified`/
    `.reject` action-pair shape (3.1) rather than inventing a new verify pattern
  - `status` — CharField choices, max_length=10, default `"active"`: `active` / `inactive`
  - `Meta.ordering = ["employee", "-is_salary_account", "bank_name"]`; index `(tenant, employee)`
    (`hrm_eba_tenant_emp_idx`)
  - `save()`: same auto-demote pattern as `EmergencyContact.is_primary` — if `self.is_salary_account`,
    `EmployeeBankAccount.objects.filter(tenant_id=..., employee_id=..., is_salary_account=True)
    .exclude(pk=self.pk).update(is_salary_account=False)` inside `transaction.atomic()` before
    `super().save()`.
  - `_mask_last4()` (staticmethod, duplicated verbatim from `EmployeeProfile._mask_last4` — matches the
    existing per-model-duplication convention, not a shared util) → `masked_account_number()` /
    `masked_routing_number()`.
  - `__str__`: `f"{self.bank_name} ****{last4} - {self.employee}"` (via the masked helper — never the
    raw number, not even in `__str__`/admin/audit-log `str(obj)` calls)
  - **Cross-touch:** add `"account_number"` to `apps/core/crud.py`'s `_SENSITIVE_AUDIT_FIELDS`
    frozenset (mirrors the existing `bank_account`/`bank_routing`/`national_id`/`passport_number`
    entries — redacts the raw account number from `AuditLog.changes` on every create/edit).
  - Reuses `hrm.EmployeeProfile` as parent, the exact `_mask_last4` pattern, and the
    `_SENSITIVE_AUDIT_FIELDS` redaction convention.

- [ ] **`FamilyMember`** [`TenantOwned`] — covers **Family Details**. Create/edit routes through
  `EmployeeInfoChangeRequest` (same sensitivity tier as bank/legal-name); the model's own create/edit/
  delete views are `@tenant_admin_required`.
  - `employee` — FK `hrm.EmployeeProfile`, `on_delete=CASCADE`, `related_name="family_members"`
  - `name` — CharField(255)
  - `relationship` — CharField choices, max_length=10, default `"spouse"`: `spouse` / `child` /
    `father` / `mother` / `sibling` / `other`
  - `date_of_birth` — DateField(null=True, blank=True)
  - `gender` — CharField choices, max_length=20, blank=True — **reuses
    `EmployeeProfile.GENDER_CHOICES`** directly (no duplicate CHOICES tuple; same file, direct
    reference)
  - `occupation` — CharField(255, blank=True); `phone` — CharField(30, blank=True)
  - `is_dependent` — BooleanField(default=False) — benefits/insurance eligibility (driver: ADP Manage
    Dependents, greytHR)
  - `is_minor` — BooleanField(default=False); `guardian_name` — CharField(255, blank=True);
    `guardian_relationship` — CharField(100, blank=True) (driver: greytHR Minor checkbox + guardian
    fields, "required when checked")
  - `is_nominee` — BooleanField(default=False); `nominee_percentage` — DecimalField(max_digits=5,
    decimal_places=2, null=True, blank=True, validators `[MinValueValidator(0),
    MaxValueValidator(100)]`) — **one simplified percentage field this pass, NOT a per-scheme
    (EPF/EPS/ESI/Gratuity) nomination sub-table** and **no cross-row "nominees sum to 100%"
    validation** (both explicitly deferred — needs 3.15 Statutory Compliance as the consumer)
  - `notes` — TextField(blank=True)
  - `Meta.ordering = ["employee", "name"]`; index `(tenant, employee)` (`hrm_fam_tenant_emp_idx`)
  - `clean()`: if `self.is_minor` and not `self.guardian_name`, raise on `guardian_name` ("Guardian
    name is required for a minor family member.") — the greytHR "required when checked" rule, enforced
    in code.
  - `__str__`: `f"{self.name} ({self.get_relationship_display()}) - {self.employee}"`
  - Reuses `hrm.EmployeeProfile` as parent and its `GENDER_CHOICES`.

- [ ] **`EmployeeInfoChangeRequest`** [`ICR-`, `TenantNumbered`] — the maker-checker workflow
  connecting all 5 NavERP.md bullets. **First GenericForeignKey inside `apps/hrm`** — add
  `from django.contrib.contenttypes.fields import GenericForeignKey` and
  `from django.contrib.contenttypes.models import ContentType` to the top of `apps/hrm/models.py`.
  - `employee` — FK `hrm.EmployeeProfile`, `on_delete=CASCADE`, `related_name="info_change_requests"`
    (whose record is being changed — always the requester's own profile, enforced in `clean()`)
  - `content_type` — FK `ContentType`, `on_delete=SET_NULL`, null/blank; `object_id` — BigIntegerField,
    null/blank (**`None` = this request PROPOSES CREATING a brand-new `EmployeeBankAccount`/
    `FamilyMember` row** — there is no existing target to point at yet; set = propose an edit to an
    existing row); `target = GenericForeignKey("content_type", "object_id")`
  - `request_type` — CharField choices, max_length=15, default `"profile_field"`: `profile_field` /
    `bank` / `family` — **for `profile_field`, `content_type` is ALWAYS `hrm.EmployeeProfile` and
    `object_id` is ALWAYS `self.employee_id`** (per the brief: "gate sensitive fields on
    EmployeeProfile itself"); the one exception is the `legal_name` pseudo-field, special-cased in
    `apply()` below to write through to `target.party.name` since `EmployeeProfile.name` is a
    `@property`, not a column
  - `field_changes` — `models.JSONField(default=dict)` — `{"field_name": {"old": ..., "new": ...},
    ...}`; for a `profile_field` request this holds exactly ONE key (one sensitive field per request,
    keeps the review UI simple); for `bank`/`family` it holds every proposed field on that row (a full
    create OR a full edit in one shot — this is the leaner refinement over the research's
    one-field-at-a-time `field_name`/`old_value`/`new_value` sketch)
  - `reason` — TextField(blank=True) — the employee's justification
  - `status` — CharField choices, max_length=10, default `"pending"`, `editable=False` (workflow-
    owned): `pending` / `approved` / `rejected` / `cancelled`
  - `requested_by` — FK `settings.AUTH_USER_MODEL`, `on_delete=SET_NULL`, null/blank,
    `editable=False`, `related_name="+"` (who submitted — usually `request.user`, but an admin may
    submit on an employee's behalf)
  - `reviewed_by` — FK `settings.AUTH_USER_MODEL`, `on_delete=SET_NULL`, null/blank,
    `editable=False`, `related_name="+"`; `reviewed_at` — DateTimeField, null/blank, `editable=False`
  - `decision_note` — TextField(blank=True) — HR's note on approve/reject
  - `Meta.ordering = ["-created_at"]`; `unique_together = ("tenant", "number")`; indexes
    `(tenant, employee)` (`hrm_icr_tenant_emp_idx`), `(tenant, status)` (`hrm_icr_tenant_status_idx`)
  - `clean()`: `field_changes` must be a non-empty dict — else raise; for `request_type="profile_field"`
    the resolved `content_type` must be `hrm.EmployeeProfile` and `object_id` must equal
    `self.employee_id` (anti-tamper — you can only request changes against your own profile); for
    `bank`/`family`, if `object_id` is set, `self.target.employee_id` must equal `self.employee_id`
    (can't propose an edit to someone else's bank account/family member).
  - `apply(user)` — called ONLY from the approve action, inside `transaction.atomic()`:
    ```python
    def apply(self, user):
        with transaction.atomic():
            if self.request_type == "profile_field":
                obj = self.employee
            elif self.object_id:
                obj = self.target
            else:
                Model = self.content_type.model_class()
                obj = Model(tenant=self.tenant, employee=self.employee)
            for field, change in self.field_changes.items():
                if field == "legal_name":
                    obj.party.name = change["new"]; obj.party.save(update_fields=["name"])
                else:
                    setattr(obj, field, change["new"])
            obj.full_clean(); obj.save()
            if self.object_id is None and self.request_type != "profile_field":
                self.object_id = obj.pk   # backfill so the ICR keeps pointing at what it created
            self.status, self.reviewed_by, self.reviewed_at = "approved", user, timezone.now()
            self.save(update_fields=["status", "object_id", "reviewed_by", "reviewed_at", "updated_at"])
    ```
    (illustrative — the build step wires the exact `update_fields` list and error handling; the
    contract is: sensitive-field profile writes go through `EmployeeProfile`/`Party`, bank/family
    writes create-or-update the child row, and the request always ends in `approved` with a full
    audit trail via the existing `write_audit_log` call in the view.)
  - `SENSITIVE_PROFILE_FIELDS` — module-level tuple near this class:
    `("legal_name", "date_of_birth", "national_id", "national_id_type", "passport_number",
    "passport_expiry")` — the hardcoded sensitive-field list (Keka's per-field matrix concept,
    simplified to a fixed list this pass, per the research's explicit "hardcoded list, full
    per-tenant configurable matrix deferred" note).
  - `__str__`: `f"{self.number} · {self.get_request_type_display()} · {self.employee}"`
  - Reuses the GenericForeignKey pattern already established by `core.AuditLog`/`core.Activity`/
    `core.Document` — no new polymorphic-reference shape invented.

## Backend (apps/hrm/)

- [ ] **models.py** — add `GenericForeignKey`/`ContentType` imports at the top; append the 4 classes
  above with a `# --- 3.25 Personal Information (Self-Service) ... ---` section-header comment block
  (mirrors the 3.22/3.23/3.24 preamble style: states this is the ESS layer over the existing
  `EmployeeProfile`, lists what's reused (`EmployeeProfile` flat columns, `core.Party.name`,
  `core.Employment`, the GenericForeignKey pattern) vs. what's new (the 3 child tables +
  `EmployeeInfoChangeRequest`), and explicitly notes Profile Management/Contact Update get NO new
  model — they're an ESS view/edit surface over `EmployeeProfile` itself).
- [ ] **forms.py**:
  - `EmergencyContactForm(TenantModelForm)` — `Meta.fields = ["name", "relationship", "phone",
    "alt_phone", "email", "address", "is_primary", "priority_order", "notes"]` — **`employee` is
    EXCLUDED** (set in the view from `_current_employee_profile(request)` for a non-admin, or from an
    `?employee=<id>` picker for an admin — mirrors the existing nested-create pattern where
    `TrainingFeedbackForm` excludes `attendance`).
  - `EmployeeBankAccountForm(TenantModelForm)` — `Meta.fields = ["bank_name", "account_holder_name",
    "account_number", "routing_number", "account_type", "is_salary_account", "split_percentage",
    "verification_status", "status"]` — `employee` excluded, same pattern.
  - `FamilyMemberForm(TenantModelForm)` — `Meta.fields = ["name", "relationship", "date_of_birth",
    "gender", "occupation", "phone", "is_dependent", "is_minor", "guardian_name",
    "guardian_relationship", "is_nominee", "nominee_percentage", "notes"]` — `employee` excluded, same
    pattern.
  - `EmployeeProfileMyInfoForm(TenantModelForm)` — `Meta.model = EmployeeProfile`, `Meta.fields =
    ["current_address", "permanent_address", "personal_email", "mobile", "photo"]` — the DIRECT-EDIT,
    non-gated subset only (no `work_email`, no bank/national-ID/DOB/name fields — those are read-only
    on this form, editable only via a change request).
  - Three plain `forms.Form` (NOT `ModelForm` — they assemble `field_changes` JSON, they don't save a
    model instance directly) for `changerequest_create`, each applying the same widget CSS classing
    `TenantModelForm.__init__` does (`form-input`/`form-select`/`form-textarea` — copy the same
    attrs-setting loop or factor a tiny shared mixin, since plain `forms.Form` doesn't get it for
    free):
    - `ProfileFieldChangeForm` — `field_name = ChoiceField(choices=[(f, f.replace("_", " ").title())
      for f in EmployeeInfoChangeRequest.SENSITIVE_PROFILE_FIELDS])`, `new_value = CharField(255)`,
      `reason = CharField(widget=Textarea)`.
    - `BankAccountChangeForm` — `existing_account = ModelChoiceField(queryset=..., required=False,
      empty_label="-- Propose a new account --")` (queryset scoped to the requester's own accounts in
      `__init__`), plus `bank_name`/`account_holder_name`/`account_number`/`routing_number`/
      `account_type`/`split_percentage`/`reason` (NO `verification_status`/`status` — those stay
      admin/workflow-only, never proposable by the employee).
    - `FamilyMemberChangeForm` — `existing_member = ModelChoiceField(...)` (same pattern) plus
      `name`/`relationship`/`date_of_birth`/`gender`/`occupation`/`phone`/`is_dependent`/`is_minor`/
      `guardian_name`/`guardian_relationship`/`is_nominee`/`nominee_percentage`/`reason`.
- [ ] **views.py** — new `# 3.25 Personal Information (Self-Service)` section:
  - `_can_manage_own_child(request, obj)` helper — `_is_admin(request.user) or (profile := 
    _current_employee_profile(request)) is not None and obj.employee_id == profile.pk` (mirrors the
    existing `_is_reviewer`/`_can_edit_review` ownership-helper shape at `views.py:7738`).
  - `my_info(request)` — `@login_required`; resolves `profile = _current_employee_profile(request)`;
    404/redirect-with-message if `None` (an admin user with no employee record); renders the read-only
    employment context (`profile.designation`, `profile.department`, `profile.manager`,
    `profile.employment.hired_on` if `profile.employment_id`), the direct-edit fields as read display
    + "Edit Contact Info" link, the sensitive fields MASKED (`profile.masked_national_id()`,
    `profile.masked_passport_number()`, `profile.date_of_birth`, `profile.party.name`) + "Request a
    Change" links pre-filled per field, and roster summaries (first 3 `emergency_contacts`/
    `bank_accounts`/`family_members` + "Manage all" links) plus the requester's own recent
    `info_change_requests` (last 5, any status).
  - `my_info_edit(request)` — `@login_required`; same profile resolution; `crud_edit`-shaped but
    scoped to `profile` itself (not a generic pk lookup) using `EmployeeProfileMyInfoForm`; on success
    redirect to `my_info`.
  - **EmergencyContact CRUD** (`emergencycontact_list/_create/_detail/_edit/_delete`) — `@login_required`
    throughout (no admin gate — direct self-edit). `list`: admin sees ALL tenant rows + an `employee`
    filter dropdown (per Filter Implementation Rules — pass the tenant's `EmployeeProfile` queryset to
    the template); non-admin sees only `qs.filter(employee=profile)`, no employee-filter UI shown.
    `create`: employee resolved as above (admin may pass `?employee=<id>`, validated
    `tenant=request.tenant`; non-admin forced to self, 403/redirect if no profile). `edit`/`delete`:
    `get_object_or_404(..., tenant=request.tenant)` then gate with `_can_manage_own_child` — else
    `PermissionDenied`/redirect with an error message (not a silent 404, so a legitimate cross-employee
    attempt is distinguishable from an IDOR in logs — but a CROSS-TENANT pk must still 404 via the
    `tenant=request.tenant` filter in `get_object_or_404`, checked in Verify below).
  - **EmployeeBankAccount CRUD** — `list`/`detail`: `@login_required`, same admin-sees-all /
    non-admin-sees-own scoping as EmergencyContact; ALWAYS renders `masked_account_number()`, never
    `account_number` raw. `create`/`edit`/`delete`: `@tenant_admin_required` (no employee self-save —
    the only employee-initiated path is `changerequest_create` with `request_type="bank"`).
    `employeebankaccount_verify`/`_reject` — `@tenant_admin_required`, `@require_POST`, set
    `verification_status` + `write_audit_log(..., "update", {"action": "verify"/"reject"})` (mirrors
    `employee_document_mark_verified`/`_reject`).
  - **FamilyMember CRUD** — same shape as `EmployeeBankAccount`: `list`/`detail` `@login_required` with
    admin-sees-all/non-admin-sees-own scoping; `create`/`edit`/`delete` `@tenant_admin_required`.
  - **EmployeeInfoChangeRequest CRUD** (`changerequest_*`):
    - `changerequest_list` — `@login_required`; admin sees ALL tenant rows + `status`/`request_type`/
      `employee` filters; non-admin sees only `qs.filter(employee=profile)`.
    - `changerequest_create` — `@login_required`; branches on `request.GET.get("type",
      "profile_field")`/POST `request_type` to instantiate the matching plain `Form`; resolves
      `employee` (admin picker or self, same pattern as the child-entity creates); on valid POST,
      assembles `content_type`/`object_id`/`field_changes` per the model docstring above (reading the
      CURRENT value for `"old"` off the live target — `getattr(employee, field_name)` or
      `employee.party.name` for `legal_name`, or the existing bank/family row's current field values,
      or `None` for every field when proposing a brand-new bank/family row), creates the
      `EmployeeInfoChangeRequest` with `status="pending"`, `requested_by=request.user`,
      `write_audit_log(request.user, obj, "create")`, redirect to `changerequest_detail`.
    - `changerequest_detail` — `@login_required`; gate: `_is_admin` or the request's own `employee`;
      renders `field_changes` as an old→new diff table, the resolved `target` (or "will create a new
      {model}" when `object_id` is `None`), status, decision fields.
    - `changerequest_edit`/`_delete` — allowed only while `status == "pending"` AND (`_is_admin` or
      owner) — else redirect with an error message (mirrors `trainingnomination_edit`'s
      "only a pending nomination can be edited" gate).
    - `changerequest_cancel` — `@login_required`, `@require_POST`; owner or admin; only while
      `status == "pending"`; sets `status="cancelled"`.
    - `changerequest_approve` — `@tenant_admin_required`, `@require_POST`; only while
      `status == "pending"`; calls `obj.apply(request.user)` inside the view's own
      `try/except ValidationError` (a stale/invalid proposal — e.g. the target row was deleted since
      submission — shows a form error instead of a 500); `write_audit_log(request.user, obj, "update",
      {"action": "approve"})`.
    - `changerequest_reject` — `@tenant_admin_required`, `@require_POST`; only while
      `status == "pending"`; requires `decision_note` (non-blank — HR must say why); sets
      `status="rejected"`, `reviewed_by`, `reviewed_at`.
- [ ] **urls.py** — `app_name = "hrm"` (already set); add under a `# 3.25 Personal Information
  (Self-Service)` comment block:
  ```
  path("my-info/", views.my_info, name="my_info"),
  path("my-info/edit/", views.my_info_edit, name="my_info_edit"),

  path("emergency-contacts/", views.emergencycontact_list, name="emergencycontact_list"),
  path("emergency-contacts/add/", views.emergencycontact_create, name="emergencycontact_create"),
  path("emergency-contacts/<int:pk>/", views.emergencycontact_detail, name="emergencycontact_detail"),
  path("emergency-contacts/<int:pk>/edit/", views.emergencycontact_edit, name="emergencycontact_edit"),
  path("emergency-contacts/<int:pk>/delete/", views.emergencycontact_delete, name="emergencycontact_delete"),

  path("bank-accounts/", views.employeebankaccount_list, name="employeebankaccount_list"),
  path("bank-accounts/add/", views.employeebankaccount_create, name="employeebankaccount_create"),
  path("bank-accounts/<int:pk>/", views.employeebankaccount_detail, name="employeebankaccount_detail"),
  path("bank-accounts/<int:pk>/edit/", views.employeebankaccount_edit, name="employeebankaccount_edit"),
  path("bank-accounts/<int:pk>/delete/", views.employeebankaccount_delete, name="employeebankaccount_delete"),
  path("bank-accounts/<int:pk>/verify/", views.employeebankaccount_verify, name="employeebankaccount_verify"),
  path("bank-accounts/<int:pk>/reject/", views.employeebankaccount_reject, name="employeebankaccount_reject"),

  path("family-members/", views.familymember_list, name="familymember_list"),
  path("family-members/add/", views.familymember_create, name="familymember_create"),
  path("family-members/<int:pk>/", views.familymember_detail, name="familymember_detail"),
  path("family-members/<int:pk>/edit/", views.familymember_edit, name="familymember_edit"),
  path("family-members/<int:pk>/delete/", views.familymember_delete, name="familymember_delete"),

  path("change-requests/", views.changerequest_list, name="changerequest_list"),
  path("change-requests/add/", views.changerequest_create, name="changerequest_create"),
  path("change-requests/<int:pk>/", views.changerequest_detail, name="changerequest_detail"),
  path("change-requests/<int:pk>/edit/", views.changerequest_edit, name="changerequest_edit"),
  path("change-requests/<int:pk>/delete/", views.changerequest_delete, name="changerequest_delete"),
  path("change-requests/<int:pk>/cancel/", views.changerequest_cancel, name="changerequest_cancel"),
  path("change-requests/<int:pk>/approve/", views.changerequest_approve, name="changerequest_approve"),
  path("change-requests/<int:pk>/reject/", views.changerequest_reject, name="changerequest_reject"),
  ```
- [ ] **admin.py** — register all 4 models:
  - `EmergencyContactAdmin`: `list_display = ("name", "relationship", "employee", "is_primary",
    "tenant")`; `list_filter = ("tenant", "is_primary")`; `search_fields = ("name",
    "employee__party__name", "phone")`; `raw_id_fields = ("employee",)`; `readonly_fields =
    ("created_at", "updated_at")`.
  - `EmployeeBankAccountAdmin`: `list_display = ("bank_name", "employee", "account_type",
    "is_salary_account", "verification_status", "status", "tenant")`; `list_filter = ("tenant",
    "account_type", "verification_status", "status")`; `search_fields = ("bank_name",
    "account_holder_name", "employee__party__name")`; `raw_id_fields = ("employee",)`;
    `readonly_fields = ("created_at", "updated_at")` (admin CAN see/edit `account_number` in the raw
    Django admin — that's an accepted trade-off of `ModelAdmin`, note it in a comment, don't try to
    mask it there).
  - `FamilyMemberAdmin`: `list_display = ("name", "relationship", "employee", "is_dependent",
    "is_minor", "is_nominee", "tenant")`; `list_filter = ("tenant", "relationship", "is_dependent",
    "is_minor", "is_nominee")`; `search_fields = ("name", "employee__party__name")`; `raw_id_fields =
    ("employee",)`; `readonly_fields = ("created_at", "updated_at")`.
  - `EmployeeInfoChangeRequestAdmin`: `list_display = ("number", "employee", "request_type", "status",
    "requested_by", "tenant")`; `list_filter = ("tenant", "request_type", "status")`; `search_fields =
    ("number", "employee__party__name", "reason")`; `raw_id_fields = ("employee", "requested_by",
    "reviewed_by")`; `readonly_fields = ("number", "status", "requested_by", "reviewed_by",
    "reviewed_at", "created_at", "updated_at")`.
- [ ] **migrations** — `python manage.py makemigrations hrm` — expect a new `0042_...` migration
  creating all 4 models (no unrelated schema diff).
- [ ] **Cross-touch:** `apps/core/crud.py` — add `"account_number"` to `_SENSITIVE_AUDIT_FIELDS`.
- [ ] **seed_hrm.py** — new `_seed_selfservice(self, tenant, *, flush)` method:
  - Called from `handle()` immediately after `self._seed_trainingadmin(tenant, flush=options["flush"])`
    (the 23rd call in the per-tenant loop — LAST, since it's the final 3.x sub-module built).
  - `if flush:` delete in order: `EmployeeInfoChangeRequest`, `FamilyMember`, `EmployeeBankAccount`,
    `EmergencyContact` — filtered by `tenant`.
  - Idempotency guards: `emps = list(EmployeeProfile.objects.filter(tenant=tenant)
    .select_related("party").order_by("party__name"))` — if `len(emps) < 2`, NOTICE "Not enough
    employees for '{tenant.name}' - skipping self-service seed." + return. Then `if
    EmergencyContact.objects.filter(tenant=tenant).exists():` → NOTICE "Self-service data already
    exists for '{tenant.name}'. Use --flush to re-seed." + return.
  - `actor = get_user_model().objects.filter(tenant=tenant).order_by("id").first()` (mirrors the
    existing generic-actor convention used elsewhere in this seeder) for `requested_by`/`reviewed_by`.
  - Demo data — **`EmergencyContact`** (3 rows): `emps[0]` gets 2 (`is_primary=True` spouse +
    `is_primary=False` sibling, distinct `priority_order`); `emps[1]` gets 1 (`is_primary=True`
    parent).
  - Demo data — **`EmployeeBankAccount`** (3 rows): `emps[0]` gets 2 (`is_salary_account=True`,
    `verification_status="verified"`, `account_type="checking"` + a second `is_salary_account=False`,
    `split_percentage=20.00`, `verification_status="pending"`, `account_type="savings"` —
    demonstrates the Gusto-style split-intent field); `emps[1]` gets 1 (`is_salary_account=True`,
    `verification_status="verified"`).
  - Demo data — **`FamilyMember`** (3 rows): `emps[0]` gets a spouse (`is_dependent=True`,
    `is_nominee=True`, `nominee_percentage=60.00`) + a child (`is_dependent=True`, `is_minor=True`,
    `guardian_name=emps[0].name`, `guardian_relationship="Parent"`); `emps[1]` gets 1 dependent parent
    (`is_dependent=True`, `is_nominee=False`).
  - Demo data — **`EmployeeInfoChangeRequest`** (4 rows, across the workflow states, mirroring the
    `TrainingNomination` "across the workflow states" seeding convention):
    - `emps[1]`, `request_type="profile_field"`, `field_changes={"national_id": {"old": emps[1]
      .national_id, "new": "<corrected demo value>"}}`, `reason="Typo in the originally recorded
      national ID."`, `status="pending"`, `requested_by=actor`.
    - `emps[0]`, `request_type="bank"`, `object_id=None` (a NEW-account proposal),
      `field_changes={...the 3rd bank account's fields as "new", "old": None...}`,
      `status="approved"`, `requested_by=actor`, `reviewed_by=actor`, `reviewed_at=now`,
      `decision_note="Verified with the employee over a call."` — **seeded directly in the
      `approved` state** (not by actually calling `.apply()`), matching this seeder's established
      convention of seeding illustrative end-states directly rather than replaying every workflow
      action.
    - `emps[1]`, `request_type="family"`, existing `object_id` = one of `emps[1]`'s seeded
      `FamilyMember` rows, `status="rejected"`, `decision_note="Please attach a supporting document
      for the guardian change."`.
    - `emps[0]`, `request_type="profile_field"`, `field_changes={"date_of_birth": {...}}`,
      `status="cancelled"`.
  - **CRITICAL — Windows cp1252 console bug (repeat of the 3.20–3.24 bug):** ASCII-only
    `self.stdout.write(...)` strings.
  - Update `_seed_tenant`'s flush-teardown tuple: insert `EmployeeInfoChangeRequest, FamilyMember,
    EmployeeBankAccount, EmergencyContact,` with a comment: `# 3.25: all four CASCADE from
    EmployeeProfile (EmergencyContact/EmployeeBankAccount/FamilyMember.employee are CASCADE) or
    SET_NULL (EmployeeInfoChangeRequest.content_type/requested_by/reviewed_by) - EmployeeInfoChangeRequest
    itself has no PROTECT dependents, order-agnostic vs EmployeeProfile, listed here for a clean
    explicit teardown.` — placed anywhere before the `EmployeeProfile` deletion.

## Wire-up

- [ ] `config/settings.py` — `apps.hrm` already in `INSTALLED_APPS` (no change needed).
- [ ] `config/urls.py` — `hrm/` include already wired (no change needed).
- [ ] `apps/core/navigation.py` `LIVE_LINKS["3.25"]` — new block mapping the 5 exact NavERP.md 3.25
  bullets (confirmed verbatim from `NavERP.md` lines 609–613), placed immediately after the existing
  `"3.24"` block:
  ```python
  # 3.25 Personal Information (Self-Service) — the ESS layer over the existing EmployeeProfile.
  # Profile Management/Contact Update get NO new model — they're the my_info hub + its edit form over
  # EmployeeProfile's existing flat columns. Emergency Contacts/Bank Details/Family Details are proper
  # child tables lifting the 2-slot/1-slot flat-column limits. EmployeeInfoChangeRequest is the
  # maker-checker workflow connecting all five — added as an extra live leaf, not its own bullet.
  "3.25": {
      "Profile Management": "hrm:my_info",                          # bullet (ESS hub — view + read-only employment context)
      "Contact Update": "hrm:my_info_edit",                         # bullet (direct-edit form: address/personal_email/mobile/photo)
      "Emergency Contacts": "hrm:emergencycontact_list",            # bullet (EmergencyContact CRUD, direct self-edit)
      "Bank Details": "hrm:employeebankaccount_list",               # bullet (EmployeeBankAccount CRUD, admin-gated writes)
      "Family Details": "hrm:familymember_list",                    # bullet (FamilyMember CRUD, admin-gated writes)
      "Change Requests": "hrm:changerequest_list",                  # extra live leaf (EmployeeInfoChangeRequest maker-checker queue)
  },
  ```

## Templates (templates/hrm/selfservice/)

- [ ] **New sub-module folder `selfservice/`** (per the Template Folder Structure rule — 3.25 is a
  distinct NavERP.md sub-module), with one entity folder per model plus the standalone hub pages at
  the sub-module root:
- [ ] `templates/hrm/selfservice/my_info.html` — standalone hub: employment-context card (read-only:
  designation, department, manager, hired_on, employee_type, work_email, work_location), direct-edit
  fields card (address ×2, personal_email, mobile, photo) + "Edit" button → `my_info_edit`, sensitive
  fields card (masked national ID/passport, DOB, legal name) each with its own "Request a Change" link
  pre-filled (`?type=profile_field&field=national_id`), 3 roster summary cards (emergency contacts /
  bank accounts / family members — first 3 rows + "Manage all" links + "Add" links), a "My Pending
  Requests" mini-list (last 5 `info_change_requests` with status badges) + "View all" link.
- [ ] `templates/hrm/selfservice/my_info_edit.html` — standalone direct-edit form (address/
  personal_email/mobile/photo only), Cancel link back to `my_info`.
- [ ] `templates/hrm/selfservice/emergencycontact/list.html` — filter bar (`employee` dropdown,
  admin-only per the Filter Implementation Rules — pass `employees` queryset only when `is_admin`),
  primary badge, Actions column (view/edit/delete-POST+confirm+csrf, gated by
  `_can_manage_own_child`), pagination, empty-state.
- [ ] `templates/hrm/selfservice/emergencycontact/detail.html` — full contact card, Actions sidebar
  (Edit/Delete gated by `_can_manage_own_child`), Back to List.
- [ ] `templates/hrm/selfservice/emergencycontact/form.html` — create/edit (shared, `is_edit` flag);
  the `employee` picker shown ONLY when `is_admin` (else a fixed "For: {{ profile }}" display line).
- [ ] `templates/hrm/selfservice/employeebankaccount/list.html` — filter bar (`employee` dropdown
  admin-only, `verification_status`, `account_type`), masked account number column (NEVER the raw
  value), salary-account badge, verification-status badge, Actions column (view always; edit/delete
  only when `is_admin`; Verify/Reject buttons when `is_admin` and `verification_status == "pending"`).
- [ ] `templates/hrm/selfservice/employeebankaccount/detail.html` — masked number/routing, all other
  fields, Actions sidebar (Edit/Delete admin-only; Verify/Reject admin-only + pending-only).
- [ ] `templates/hrm/selfservice/employeebankaccount/form.html` — admin-only create/edit (masked
  helper text under the account-number field: "Only the last 4 digits are ever displayed after
  saving.").
- [ ] `templates/hrm/selfservice/familymember/list.html` — filter bar (`employee` dropdown admin-only,
  `relationship`, `is_dependent`), dependent/minor/nominee badges, Actions column (view always; edit/
  delete admin-only).
- [ ] `templates/hrm/selfservice/familymember/detail.html` — full record, guardian fields shown only
  when `is_minor`, Actions sidebar (admin-only Edit/Delete).
- [ ] `templates/hrm/selfservice/familymember/form.html` — admin-only create/edit; guardian fields
  shown/required via a small `x-show`/plain-JS toggle on `is_minor` (progressive enhancement — the
  server-side `clean()` is the real enforcement).
- [ ] `templates/hrm/selfservice/changerequest/list.html` — filter bar (`status`, `request_type`,
  `employee` dropdown admin-only), status badges (pending/approved/rejected/cancelled), Actions column
  (view always; edit/delete/cancel gated to owner-or-admin + pending-only; Approve/Reject buttons
  admin-only + pending-only).
- [ ] `templates/hrm/selfservice/changerequest/detail.html` — target summary ("Editing {{
  target }}" or "Proposing a new {{ content_type.model }}" when `object_id` is null), `field_changes`
  rendered as an old→new diff table, reason, decision fields (`reviewed_by`/`reviewed_at`/
  `decision_note`) shown only once decided, Actions sidebar (same gated buttons as the list row, each
  its own POST form + `{% csrf_token %}` + `confirm()` on Approve/Reject/Cancel/Delete).
- [ ] `templates/hrm/selfservice/changerequest/form.html` — create form: a `request_type` selector
  (3 radio/tab options) toggles which of the 3 plain sub-forms renders (`ProfileFieldChangeForm`/
  `BankAccountChangeForm`/`FamilyMemberChangeForm`) — plain `<details>`/CSS `:target` or minimal JS is
  fine, no HTMX dependency required for a 3-way toggle; pre-selects `request_type`/`field_name` from
  `?type=`/`?field=` query params when arriving from a `my_info.html` "Request a Change" link.

## Verify

- [ ] `python manage.py makemigrations hrm` — expect a new `0042_...` migration; review the generated
  file before applying (confirm the 4 new tables + their indexes, no unrelated diff).
- [ ] `python manage.py migrate`
- [ ] `python manage.py seed_hrm` — run twice; second run must be a no-op (NOTICE message, zero new
  rows) proving idempotency.
- [ ] `python manage.py check` — zero errors/warnings.
- [ ] `temp/` smoke sweep — all `hrm:my_info`/`hrm:my_info_edit`, `hrm:emergencycontact_*`,
  `hrm:employeebankaccount_*` (incl. verify/reject), `hrm:familymember_*`, `hrm:changerequest_*`
  (incl. approve/reject/cancel) URLs return 200/302 (never 500); no `{#`/`{% comment` template-comment
  leaks in rendered output; cross-tenant IDOR check (a tenant-B admin/employee hitting a tenant-A row's
  pk on any of the 4 models' detail/edit/delete/action URLs returns 404, not the object); cross-EMPLOYEE
  IDOR check WITHIN the same tenant (employee A, logged in as a non-admin, hitting employee B's
  `emergencycontact`/`employeebankaccount`/`familymember`/`changerequest` detail/edit/delete pk must be
  denied — 403 or redirect-with-error, not a silent edit); admin-gate check (a non-admin POSTing
  directly to `employeebankaccount_create`/`_edit`/`_delete`, `familymember_create`/`_edit`/`_delete`,
  `employeebankaccount_verify`/`_reject`, `changerequest_approve`/`_reject` must be denied); masked-
  display check (raw `account_number` never appears in any rendered response body — grep the smoke-test
  HTML dumps for the seeded raw digits, only the masked `••••NNNN` form should appear); the
  `is_salary_account`/`is_primary` auto-demote-on-save behavior (setting a 2nd row `True` flips the
  1st back to `False`, verified via the ORM after a POST); `EmployeeInfoChangeRequest.apply()`
  end-to-end (submit a real `changerequest_create` POST for each of the 3 `request_type`s, approve it
  as admin, confirm the target row/field actually changed — including the `legal_name` special case
  writing through to `party.name`, and a `bank`/`family` `object_id=None` proposal actually creating a
  new row and backfilling `object_id`); reject path leaves the target UNCHANGED; cancel path is
  requester-or-admin only and pending-only.
- [ ] Sidebar shows all 5 new 3.25 sub-module bullets as **Live** (Profile Management, Contact Update,
  Emergency Contacts, Bank Details, Family Details) plus the extra "Change Requests" leaf — confirm via
  the rendered sidebar, not just the `LIVE_LINKS` dict.

## Close-out

- [ ] Run the 7 review agents in order, applying findings + committing after each (one file per
  commit, no `git push`): `code-reviewer` -> `explorer` -> `frontend-reviewer` ->
  `performance-reviewer` -> `qa-smoke-tester` -> `security-reviewer` -> `test-writer`.
  - Expect `code-reviewer` to scrutinize `EmployeeInfoChangeRequest.apply()` closely (the highest-risk
    piece of new logic this pass — a bug here writes bad data into `EmployeeProfile`/`Party`/
    `EmployeeBankAccount`/`FamilyMember` under an admin's own approval action) and to double-check the
    `legal_name` → `party.name` special case doesn't silently no-op if `field_changes` uses a
    differently-cased key.
  - Expect `explorer` to check for `ProtectedError`-shaped surprises on `EmployeeProfile`/`Party`/
    `EmployeeBankAccount`/`FamilyMember` deletes now that `EmployeeInfoChangeRequest` (SET_NULL) and
    the 3 child tables (CASCADE) exist — CASCADE means no guard needed for the child-table deletes
    themselves, but confirm `employee_delete`/any `Party`-delete path still behaves.
  - Expect `frontend-reviewer` to check the masked-account-number rule is honored on EVERY render path
    (list/detail/admin — flag if the raw admin.py `ModelAdmin` change-form exposes it, which is an
    accepted, documented trade-off, not a bug to "fix" by hiding the admin field) and that the
    `changerequest/form.html` 3-way toggle doesn't leak all 3 sub-forms' hidden-but-still-POSTed field
    names ambiguously.
  - Expect `performance-reviewer` to check `my_info`'s roster-summary queries use `select_related`/
    `[:3]` slicing (not loading full querysets to show 3 rows) and that the admin `list` views'
    `employee` filter dropdown queryset is `select_related("party")`.
  - Expect `security-reviewer` to confirm: the cross-EMPLOYEE (same-tenant) IDOR checks above are
    real (not just cross-tenant); `changerequest_create`'s `content_type`/`object_id` resolution can't
    be tampered with client-side to point at an arbitrary model/row (the view computes them
    server-side from `request_type` + the resolved `employee`/existing-row ownership check, never
    trusts a client-submitted `content_type`); `EmployeeBankAccountForm`/`FamilyMemberChangeForm`
    never accept `verification_status`/admin-only fields from a non-admin path; `account_number` stays
    out of every non-admin-facing template AND out of `AuditLog.changes` (the `_SENSITIVE_AUDIT_FIELDS`
    addition).
  - Expect `test-writer` to cover: full CRUD × 4 models (incl. the admin-gate matrix — non-admin
    blocked from bank/family writes, allowed on emergency contacts); the `is_salary_account`/
    `is_primary` auto-demote behavior; `FamilyMember.clean()`'s guardian-required-when-minor rule;
    `EmployeeInfoChangeRequest.apply()` for all 3 `request_type`s × both `object_id is None`/`is not
    None` paths (6 combinations), incl. the `legal_name` special case; the cross-EMPLOYEE and
    cross-TENANT IDOR matrix on every model + every action route; `changerequest_cancel`/`_approve`/
    `_reject` status-gate (only from `pending`).
- [ ] Update `.claude/skills/hrm/SKILL.md`:
  - Add a `### 3.25 Personal Information (Self-Service) (4 tables)` section (mirrors the existing
    per-sub-module section format) with the model table, the ESS-vs-admin-CRUD split, the
    `apply()`/GenericForeignKey design, and the `legal_name` → `party.name` special case.
  - Bump the frontmatter/overview "built" sub-module list to include 3.25 and the model count
    89 → 93.
  - Add a "Personal Information / Self-Service (3.25)" routes-list section (`hrm:my_info*`,
    `hrm:emergencycontact_*`, `hrm:employeebankaccount_*` incl. verify/reject,
    `hrm:familymember_*`, `hrm:changerequest_*` incl. approve/reject/cancel).
  - Update the seeder section: document `_seed_selfservice(tenant)`, its own-exists guard, what it
    creates, and that it runs LAST (after `_seed_trainingadmin`).
  - Update the `LIVE_LINKS` section for `"3.25"` (all 5 bullets + the extra Change Requests leaf).
  - Update the "Deferred" section, replacing the old 3.25-placeholder line (if any) with 3.25's own
    carried-forward deferrals (see below).
  - Commit the SKILL.md update as its own file, per the one-file-per-commit rule.
- [ ] README (if the project keeps a root test-count/module-count summary) — refresh HRM test counts
  after `test-writer` runs, same pattern as the 3.20–3.24 README refresh commits.

## Later passes / deferred (carried over from research-hrm-3.25-personal-information.md)

- **Full per-tenant configurable field-permission matrix** (Keka-style: admin sets per-field
  mandatory/viewable/editable/approval-required) — this pass hardcodes `SENSITIVE_PROFILE_FIELDS`; a
  true configuration UI is a distinct, reusable capability (other self-service sub-modules could reuse
  it) and belongs with Module 0's form-builder/custom-fields infrastructure (0.10).
- **True effective-dated / slowly-changing-dimension replay of `EmployeeProfile`** (Workday, SAP
  SuccessFactors EC) — this pass has no `effective_date` field at all (dropped from the research's
  earlier sketch in the task-brief refinement); a change applies immediately on approval, no dated
  future-effective queue.
- **Multiple address types with full address history** — the existing 2 flat fields on
  `EmployeeProfile` are reused as-is (direct-edit via `my_info_edit`); no `core.Address` rows added.
- **Per-scheme statutory nomination (EPF/EPS/ESI/Gratuity)** matching greytHR's exact business rules —
  deferred until 3.15 Statutory Compliance exists as the consumer; this pass ships one simplified
  `nominee_percentage` field on `FamilyMember` with no cross-row sum-to-100% validation.
- **Life-event-triggered benefits re-enrollment** (ADP: birth/marriage/divorce auto-prompts a benefits
  change) — deferred to 3.37 Compensation & Benefits, which doesn't exist yet.
- **Live bank-account verification** (Plaid/Open Banking) — `verification_status` is admin-set via the
  verify/reject actions this pass; the API integration is Module 0.13-territory.
- **Split-deposit disbursement math wired into an actual payroll run** —
  `EmployeeBankAccount.split_percentage` is stored this pass; consuming it during a payroll run is
  3.14/3.17 territory.
- **Notification delivery** (email/push to HR on a pending request, to the employee on a decision) —
  this pass ships the in-app `changerequest_list` pending queue only; delivery channels are Module
  0.12 infrastructure.
- **Supporting document attachment on a change request** (e.g. proof of DOB/marriage/legal-name
  change, reusing `core.Document`'s GenericForeignKey) — the research flagged this "buildable now", but
  it's NOT in this pass's model/view scope (no field, no upload UI on `changerequest/form.html`); the
  `EmployeeInfoChangeRequest` GFK-target design doesn't block adding it as a same-shaped follow-up.
- **Preferred/display name distinct from legal name** — this pass only has `party.name` (the single
  legal name) as a gated field; no separate preferred-name column.

## Review notes

**3.25 Personal Information (Self-Service) — BUILT & reviewed (2026-07-11).** As-built matches the plan (4 models,
migration `0042`, 14 templates under `templates/hrm/selfservice/`, `LIVE_LINKS["3.25"]`, `_seed_selfservice`). All 5
NavERP.md bullets are Live in the sidebar + a `Change Requests` extra leaf. Verified end-to-end: migrate clean, seed
idempotent (2nd run no-op), `manage.py check` clean, a throwaway smoke sweep (all pages 200/302, cross-tenant IDOR
404, masked-PII never leaks the raw account number, `apply()` works for all 3 request types × new-row/edit incl. the
`legal_name`→`Party.name` write-through), and a live browser pass (bank list masked, change-request diff + workflow).

**Review-agent findings applied** (Module Creation Sequence, one commit each):
- **code-reviewer** (0 Critical): added the maker-checker **self-approval guard** (`_is_own_change_request` blocks the
  requester/subject from approving/rejecting their own request), a **lost-update guard** in `apply()` (stored `old`
  snapshot must match the live value), **per-field validation** on `ProfileFieldChangeForm` (dates parse, text
  length-capped), wrapped `changerequest` create/edit `clean()` in try/except (friendly error not 500), redact-aware
  audit diff on child edits, dropped a dead context var.
- **explorer**: auto-cancel pending change requests targeting a bank/family row when it is deleted (GenericForeignKey
  has no referential integrity on the target-row delete).
- **frontend-reviewer**: hid the dead-end Approve/Reject controls for an admin's own request (+ note), dropped the
  blind list-row Approve, added `required` to the reject input, `urlencode` on tab links, a photo preview, and a
  `.form-check` theme rule for the previously-unstyled checkboxes.
- **performance-reviewer** (0 Critical/Important): `select_related` on `changerequest_approve` (so `apply()` doesn't
  re-fetch employee/party), trimmed unused joins.
- **qa-smoke-tester**: no bugs — full URL sweep + IDOR + masking + workflow all PASS.
- **security-reviewer**: **High** — masked `account_number`/`routing_number` in the `changerequest_detail` diff table
  (the one surface that was rendering the raw stored value); **Low** — added `routing_number` to
  `_SENSITIVE_AUDIT_FIELDS`. Confirmed the maker-checker + content_type/object_id anti-tamper design is solid.
- **test-writer**: added a 3.25 test trio (`test_selfservice_models/_security/_views.py`, ~245 tests) + conftest
  fixtures, and **found a real bug I'd introduced**: `my_info` used an invalid `select_related("employment__manager__party")`
  (Employment.manager is a FK straight to `core.Party`) + `profile.manager.party.name` in the template — a 500 for any
  employee viewing their own hub (my manual pass missed it because the demo admin has no profile → redirects). Fixed
  the view path (`employment__manager`) + template (`profile.manager.name`); the pinned xfail tests now pass normally.

**Deferred** (carried from research/todo): per-tenant configurable field-permission matrix, effective-dated/temporal
history, per-scheme statutory nomination (EPF/EPS/ESI/Gratuity), live bank verification (Plaid), split-deposit payroll
wiring, notification delivery, preferred-name column. Next unbuilt HRM sub-module: **3.26 Request Management (Self-Service)**.

---
# Module 3 — HRM — Sub-module 3.26 Request Management (Self-Service) (hrm) — plan from research-hrm-3.26.md, authoritative design C:\Users\user\.claude\plans\snug-knitting-rose.md (2026-07-12)

**EXTENDS the existing `apps/hrm` app (already built through 3.25) — no new Django app, no new
`INSTALLED_APPS`/`config/urls.py` entries.** Covers the 5 NavERP.md 3.26 bullets (Leave Requests /
Attendance Regularization / Document Requests / ID Card Request / Asset Requests) by **REUSING**
`LeaveRequest` (3.10, `LR-`) and `AttendanceRegularization` (3.9, `REG-`) verbatim — link from the hub,
no new fields/views for either — and adding **3 new models** (`DocumentRequest`, `IdCardRequest`,
`AssetRequest`) + a view-only **My Requests** ESS hub (no new table). All 3 new models subclass
`TenantNumbered` and follow the `draft → pending → approved/rejected/cancelled` (+ one fulfillment tail
state) lifecycle mirroring `LeaveRequest`/`AttendanceRegularization`, with a **3.25-style self-approval
guard** on approve/reject (an admin who is also the requesting employee cannot approve/reject their own
row) and a **stricter-than-`LeaveRequest`** ownership gate on submit/cancel (see Views below).

Reuses (never duplicates): `hrm.EmployeeProfile` (the `employee` FK on all 3 new models — never a new
employee table); the existing ESS helpers verbatim from `apps/hrm/views.py`: `_current_employee_profile`
(7429), `_is_admin` (7754), `_require_own_profile` (10366), `_can_manage_own_child` (10377), `_ss_scope`
(10386), `_ss_employees` (10397), and — critically — the **shared self-service child-CRUD helpers**
`_ss_child_create` (10457), `_ss_child_edit` (10491), `_ss_child_detail` (10512), `_ss_child_delete`
(10522) already built generically enough (any model with `tenant`+`employee` FKs) to reuse **verbatim**
for all 3 new models' create/detail/edit/delete — no per-model employee-resolution logic to reimplement.
`_ss_child_delete`'s `EmployeeInfoChangeRequest` GFK auto-cancel check is a safe no-op here (none of these
3 models are ever an ICR target). `hrm.AssetAllocation` (`AST-`) is reused as the fulfillment ledger for
`AssetRequest` only (`allocation` FK, created+linked on fulfill) — **not** for `IdCardRequest` (card
issuance is tracked with plain `card_number`/`issued_at` fields on the request itself this pass; linking
ID-card issuance into `AssetAllocation` too is a documented deferral, see below). No new core-spine
entity; nothing posts to the GL.

## Models (from research + the approved design)

- [ ] **`DocumentRequest`** [`DOCREQ-`, `TenantNumbered`] — official-letter requests (Document Requests
  bullet: experience letter, salary certificate).
  - `employee` = FK `hrm.EmployeeProfile` (`on_delete=CASCADE`, `related_name="document_requests"`)
  - `document_type` — CharField(max_length=30), choices `experience_letter` / `salary_certificate` /
    `address_proof` / `employment_verification` / `noc` / `relieving_letter_copy` / `other`, default
    `"experience_letter"` (driver: NavERP.md 3.26 + Darwinbox/Freshservice letter catalogs)
  - `purpose` — TextField, required (driver: "why the document is needed" — visa/bank loan/education)
  - `addressed_to` — CharField(max_length=255, blank=True) (driver: "To Whom It May Concern" / named
    recipient convention)
  - `copies` — PositiveSmallIntegerField, default `1`, `validators=[MinValueValidator(1)]`
  - `delivery_method` — CharField(max_length=15), choices `soft_copy` / `hard_copy` / `both`, default
    `"soft_copy"`
  - `needed_by` — DateField, null/blank (SLA target date)
  - `status` — CharField(max_length=20), choices `draft` / `pending` / `approved` / `rejected` /
    `cancelled` / `fulfilled`, default `"draft"`; `OPEN_STATUSES = ("draft", "pending")`
  - `approver` — FK `settings.AUTH_USER_MODEL` (`on_delete=SET_NULL`, null/blank,
    `related_name="hrm_documentrequest_approvals"`) — **workflow-owned**
  - `approved_at` — DateTimeField, null/blank — **workflow-owned**
  - `decision_note` — TextField, blank — **workflow-owned** (also used for cancel notes — no separate
    `cancelled_reason` field, unlike `LeaveRequest`)
  - `fulfilled_at` — DateTimeField, null/blank, `editable=False` — **workflow-owned**
  - `output_file` — FileField(`upload_to="hrm/requests/documents/%Y/%m/"`, blank=True) — the HR-uploaded
    signed letter, set only by `document_fulfill` (never a create/edit form field) — **workflow-owned**
  - `Meta.ordering = ["-created_at"]`; `unique_together = ("tenant", "number")`; indexes
    `(tenant, employee)` → `hrm_docreq_tenant_emp_idx`, `(tenant, status)` → `hrm_docreq_tenant_status_idx`
  - `__str__`: `f"{self.number} · {self.employee} · {self.get_document_type_display()}"`
  - **Excluded from `DocumentRequestForm`:** `tenant`, `number`, `status`, `approver`, `approved_at`,
    `decision_note`, `fulfilled_at`, `output_file`, `employee` (resolved server-side by `_ss_child_create`)

- [ ] **`IdCardRequest`** [`IDREQ-`, `TenantNumbered`] — new/replacement/correction ID cards (ID Card
  Request bullet).
  - `employee` = FK `hrm.EmployeeProfile` (`on_delete=CASCADE`, `related_name="idcard_requests"`)
  - `request_type` — CharField(max_length=15), choices `new` / `replacement` / `correction` /
    `renewal`, default `"new"`
  - `reason_type` — CharField(max_length=20), choices `lost` / `damaged` / `stolen` / `expired` /
    `name_change` / `designation_change` / `first_issue` / `other`, default `"first_issue"` (driver:
    greytHR's reason taxonomy)
  - `reason` — TextField, required
  - `delivery_location` — CharField(max_length=255, blank=True)
  - `status` — CharField(max_length=20), choices `draft` / `pending` / `approved` / `rejected` /
    `cancelled` / `issued`, default `"draft"`; `OPEN_STATUSES = ("draft", "pending")`
  - `approver` — FK `settings.AUTH_USER_MODEL` (`on_delete=SET_NULL`, null/blank,
    `related_name="hrm_idcardrequest_approvals"`) — **workflow-owned**
  - `approved_at` — DateTimeField, null/blank — **workflow-owned**
  - `decision_note` — TextField, blank — **workflow-owned**
  - `card_number` — CharField(max_length=100, blank=True) — set only by `idcardrequest_issue` —
    **workflow-owned**
  - `issued_at` — DateTimeField, null/blank, `editable=False` — **workflow-owned**
  - `Meta.ordering = ["-created_at"]`; `unique_together = ("tenant", "number")`; indexes
    `(tenant, employee)` → `hrm_idreq_tenant_emp_idx`, `(tenant, status)` → `hrm_idreq_tenant_status_idx`
  - `__str__`: `f"{self.number} · {self.employee} · {self.get_request_type_display()}"`
  - **Excluded from `IdCardRequestForm`:** `tenant`, `number`, `status`, `approver`, `approved_at`,
    `decision_note`, `card_number`, `issued_at`, `employee`

- [ ] **`AssetRequest`** [`ASSETREQ-`, `TenantNumbered`] — equipment requests (Asset Requests bullet:
  laptop, equipment).
  - `employee` = FK `hrm.EmployeeProfile` (`on_delete=CASCADE`, `related_name="asset_requests"`)
  - `asset_category` — CharField(max_length=30), choices = **reuse
    `AssetAllocation.ASSET_CATEGORY_CHOICES`** as-is (laptop/desktop/phone/id_card/access_card/uniform/
    vehicle/sim/other — same taxonomy as what fulfillment creates), default `"other"`
  - `asset_name` — CharField(max_length=255), required
  - `justification` — TextField, required (business reason)
  - `priority` — CharField(max_length=10), choices `low` / `normal` / `high` / `urgent`, default
    `"normal"`
  - `needed_by` — DateField, null/blank
  - `status` — CharField(max_length=20), choices `draft` / `pending` / `approved` / `rejected` /
    `cancelled` / `fulfilled`, default `"draft"`; `OPEN_STATUSES = ("draft", "pending")`
  - `approver` — FK `settings.AUTH_USER_MODEL` (`on_delete=SET_NULL`, null/blank,
    `related_name="hrm_assetrequest_approvals"`) — **workflow-owned**
  - `approved_at` — DateTimeField, null/blank — **workflow-owned**
  - `decision_note` — TextField, blank — **workflow-owned**
  - `allocation` — FK `hrm.AssetAllocation` (`on_delete=SET_NULL`, null/blank, `editable=False`,
    `related_name="fulfilled_requests"`) — created + linked by `assetrequest_fulfill` inside
    `transaction.atomic()` — **workflow-owned**
  - `Meta.ordering = ["-created_at"]`; `unique_together = ("tenant", "number")`; indexes
    `(tenant, employee)` → `hrm_astreq_tenant_emp_idx`, `(tenant, status)` → `hrm_astreq_tenant_status_idx`
  - `__str__`: `f"{self.number} · {self.employee} · {self.asset_name}"`
  - **Excluded from `AssetRequestForm`:** `tenant`, `number`, `status`, `approver`, `approved_at`,
    `decision_note`, `allocation`, `employee`

All 3 FK `hrm.EmployeeProfile` by string (never a new employee table); no independent confidentiality
gate needed (ordinary self-service visibility via `_ss_scope`, same openness level as `EmergencyContact`/
`EmployeeBankAccount`, not the 3.18–3.21 subject/manager-only tier). Add after the existing
`EmployeeInfoChangeRequest` class (current end of `models.py`) with a `# --- 3.26 Request Management
(Self-Service) ---` section-header comment block stating what's reused (`LeaveRequest`/
`AttendanceRegularization` verbatim, `EmployeeProfile`, `AssetAllocation` for `AssetRequest` only) and
that Leave/Attendance get **no** new model.

## Backend (apps/hrm/)

- [ ] **models.py** — add `DocumentRequest`, `IdCardRequest`, `AssetRequest` per the field lists above.
- [ ] **migrations** — `python manage.py makemigrations hrm` (expect `0043_documentrequest_idcardrequest_assetrequest...`, incrementing from `0042`).
- [ ] **forms.py** — `DocumentRequestForm(TenantModelForm)` (fields: `document_type`, `purpose`,
  `addressed_to`, `copies`, `delivery_method`, `needed_by`), `IdCardRequestForm(TenantModelForm)`
  (fields: `request_type`, `reason_type`, `reason`, `delivery_location`), `AssetRequestForm
  (TenantModelForm)` (fields: `asset_category`, `asset_name`, `justification`, `priority`,
  `needed_by`) — all exclude `tenant`/`number`/`status`/`employee`/reviewer+fulfillment fields per the
  per-model "Excluded" notes above. Plus **`DocumentFulfillForm(forms.Form)`** — a single optional
  `output_file = forms.FileField(required=False, ...)`; `clean_output_file` calls the shared
  `_validate_upload(f, allowed_ext=ALLOWED_ONBOARDING_DOC_EXTENSIONS, max_bytes=MAX_ONBOARDING_DOC_BYTES,
  label="Letter")` — **reuse the existing constants, no new `ALLOWED_*`/`MAX_*` pair** (PDF/DOC/DOCX/JPG/
  PNG already covers a signed letter scan). Mirrors 3.21's `WarningAcknowledgeForm`/`PIPCloseForm`
  small-action-form pattern. New `# --- 3.26 Request Management (Self-Service) ---` section banner.
- [ ] **views.py** — new `_is_own_hr_request(request, obj)` helper (near `_is_own_change_request`):
  `profile = _current_employee_profile(request); return profile is not None and obj.employee_id ==
  profile.pk` — the 3.26 self-approval guard (no separate `requested_by` leg needed — `employee` IS the
  submitter on these 3 models). Then per model (`documentrequest_*` / `idcardrequest_*` /
  `assetrequest_*`):
  - `_list` (`@login_required`): `_ss_scope`-filtered qs (`select_related("employee__party",
    "approver")`), `crud_list` with search fields (`number`, `employee__party__name`, +
    `purpose`/`reason`/`justification`), filters `status` + the model's type field(s) (`document_type`;
    `request_type`+`reason_type`; `asset_category`+`priority`), `extra_context` = `status_choices` +
    type-choice constants + (`employees`: `_ss_employees(request)` when admin, mirrors
    `emergencycontact_list`).
  - `_create` (`@login_required`): `_ss_child_create(request, <Form>, "<template>",
    "hrm:<model>_list")` verbatim.
  - `_detail` (`@login_required`): `_ss_child_detail(request, <Model>, pk, "<template>",
    select_related=("employee__party", "approver"))` verbatim (raises `PermissionDenied` via
    `_can_manage_own_child`).
  - `_edit` (`@login_required`): fetch the obj, **status-gate** (`if obj.status not in
    <Model>.OPEN_STATUSES: messages.error(...); return redirect("hrm:<model>_detail", pk=obj.pk)` —
    mirrors `leaverequest_edit`), then delegate to `_ss_child_edit(...)` verbatim.
  - `_delete` (`@login_required @require_POST`): status-gate (only `draft`/`pending`/`approved`
    deletable — a `rejected`/`cancelled`/fulfilled-tail row is a closed record, mirrors
    `leaverequest_delete`'s "decided request cannot be deleted" guard), then delegate to
    `_ss_child_delete(request, <Model>, pk, "hrm:<model>_list")` verbatim.
  - `_submit` (`@login_required @require_POST`): fetch obj, **gate with `_can_manage_own_child(request,
    obj)`** (own employee or admin — 403/redirect otherwise) — **NOTE: stricter than the older
    `leaverequest_submit`/`attendanceregularization`-precedent, which has no ownership gate; 3.26
    intentionally follows the more correct 3.25 `_can_manage_own_child` pattern**; `draft → pending`.
  - `_cancel` (`@login_required @require_POST`): same `_can_manage_own_child` gate; `draft`/`pending` →
    `cancelled`, optional note captured into `decision_note` (`request.POST.get("decision_note",
    "").strip()[:2000]`).
  - `_approve` (`@tenant_admin_required @require_POST`): `_is_own_hr_request` **self-approval block**
    first (error + redirect if true); from `pending` → `approved`, stamp `approver`/`approved_at`;
    `write_audit_log(..., {"action": "approve"})`.
  - `_reject` (`@tenant_admin_required @require_POST`): `_is_own_hr_request` block first; **requires
    non-blank `decision_note`** (error + redirect if blank — stricter than the existing
    `attendanceregularization_reject`, which allows a blank note); from `pending` → `rejected`, stamp
    `approver`/`approved_at`/`decision_note`.
  - Fulfillment action per model:
    - `document_fulfill` (`@tenant_admin_required @require_POST`): from `approved` → `fulfilled`, stamp
      `fulfilled_at`; validate+attach an optional `output_file` via `DocumentFulfillForm`.
    - `idcardrequest_issue` (`@tenant_admin_required @require_POST`): from `approved` → `issued`;
      requires non-blank POST `card_number` (error + redirect if blank); stamps `card_number`/`issued_at`.
    - `assetrequest_fulfill` (`@tenant_admin_required @require_POST`): from `approved` → `fulfilled`;
      inside `transaction.atomic()` creates `AssetAllocation(tenant=request.tenant, program=None,
      employee=obj.employee, asset_name=obj.asset_name, asset_category=obj.asset_category,
      status="issued", issued_at=timezone.now(), issued_by=request.user,
      serial_number=request.POST.get("serial_number", "").strip(),
      asset_tag=request.POST.get("asset_tag", "").strip())`, links `obj.allocation`, sets
      `obj.status = "fulfilled"`.
  - `my_requests` (`@login_required`): `profile, redirect_resp = _require_own_profile(request)` (redirect
    if none); for each of the 5 request types build `_ss_scope(request, <Model>.objects.filter(
    tenant=request.tenant))` and compute an open-count + total-count + the 5 most recent rows;
    `extra_context`: `is_admin`, deep links to each type's list/create + `hrm:leaverequest_list` /
    `hrm:leaverequest_create` / `hrm:attendanceregularization_list` /
    `hrm:attendanceregularization_create`.
  - All list views follow the Filter Implementation Rules (CLAUDE.md): every `*_choices`/queryset the
    template needs is passed explicitly; string-field comparisons use `request.GET.status == value`;
    FK/pk comparisons use `|stringformat:"d"`.
- [ ] **urls.py** — append a `# 3.26 Request Management (Self-Service)` block under the existing 3.25
  block: `my-requests/` (`my_requests`), then for each of `document-requests/`, `id-card-requests/`,
  `asset-requests/`: the 5 CRUD paths + `submit/` + `cancel/` + `approve/` + `reject/` + the
  fulfill/issue path (`fulfill/` for document/asset, `issue/` for id-card), all names `<model>_<action>`
  (mirrors the `leave-requests/`/`regularizations/` block shape exactly).
- [ ] **admin.py** — register `DocumentRequestAdmin`, `IdCardRequestAdmin`, `AssetRequestAdmin`
  (`list_display`/`list_filter`/`search_fields` mirroring the existing `LeaveRequestAdmin`/
  `AttendanceRegularizationAdmin` registrations — tenant, number, employee, status, type field).
- [ ] **seed_hrm.py** — new `_seed_requests(self, tenant, *, flush)` method:
  - Called from `handle()` immediately after `self._seed_selfservice(tenant, flush=options["flush"])`
    (the new last call in the per-tenant loop).
  - `if flush:` delete `AssetRequest`, `IdCardRequest`, `DocumentRequest` — filtered by `tenant` (all
    `employee` CASCADE, order-agnostic vs `EmployeeProfile`; `AssetRequest.allocation` is `SET_NULL`
    so no ordering hazard vs `AssetAllocation` either, but wipe requests before allocations for a tidy
    teardown).
  - Idempotency guard: `if DocumentRequest.objects.filter(tenant=tenant).exists():` → NOTICE + return.
  - Reuse existing `EmployeeProfile` rows (same `select_related("party").order_by("party__name")` +
    `len(emps) < 2` guard style as `_seed_selfservice`).
  - Demo data: 2–3 `DocumentRequest` rows spanning `pending`/`approved`/`fulfilled` (the fulfilled one
    stamped with `fulfilled_at`, no real `output_file` upload needed); 2 `IdCardRequest` rows spanning
    `pending`/`issued` (the issued one stamped with `card_number`/`issued_at`); 2 `AssetRequest` rows
    spanning `pending`/`fulfilled` — **seed the fulfilled row's `AssetAllocation` directly** (create +
    link `allocation=`, `status="fulfilled"`) rather than replaying the view action, matching
    `_seed_selfservice`'s "seed end-states directly" convention.
  - Insert `AssetRequest, IdCardRequest, DocumentRequest,` into the `_seed_tenant` flush teardown tuple
    immediately before the existing 3.25 block (`EmployeeInfoChangeRequest, FamilyMember,
    EmployeeBankAccount, EmergencyContact,`), with a one-line comment explaining the (non-blocking,
    tidy-teardown-only) ordering.
  - ASCII-only `self.stdout.write(...)` (no `→`/em-dash arrows — repeat of the 3.20/3.21 cp1252 bug).
  - Both `management/__init__.py` and `management/commands/__init__.py` already exist — no new dirs.

## Wire-up

- [ ] `config/settings.py` / `config/urls.py` — already wired for `apps.hrm`; no change needed.
- [ ] `apps/core/navigation.py` — new `LIVE_LINKS["3.26"]` block placed immediately after the existing
  `"3.25"` block, with a preamble comment noting Leave/Attendance are reused verbatim (no new model) and
  this is the only place their bullets get a Live entry alongside 3.9/3.10 (mirrors the existing
  `hrm:leaverequest_list` reuse under both "Leave Application" and "Leave Calendar"):
  ```python
  "3.26": {
      "Leave Requests": "hrm:leaverequest_list",                          # bullet (reuse 3.10 LeaveRequest, no new model)
      "Attendance Regularization": "hrm:attendanceregularization_list",   # bullet (reuse 3.9 AttendanceRegularization, no new model)
      "Document Requests": "hrm:documentrequest_list",                    # bullet (new DocumentRequest CRUD + workflow)
      "ID Card Request": "hrm:idcardrequest_list",                        # bullet (new IdCardRequest CRUD + workflow)
      "Asset Requests": "hrm:assetrequest_list",                          # bullet (new AssetRequest CRUD + workflow)
      "My Requests": "hrm:my_requests",                                   # extra (unified ESS hub over all 5 types)
  },
  ```

## Templates (templates/hrm/requests/)

- [ ] `templates/hrm/requests/my_requests.html` — standalone sub-module-root page (ESS hub): 5 tiles
  (Leave / Attendance Regularization / Document / ID Card / Asset) each with an open-count badge, a
  "View All" link to that type's list, and a "Raise New Request" launcher into its create form; recent-5
  mini-list per type.
- [ ] `templates/hrm/requests/documentrequest/{list,detail,form}.html` — list: filter bar (`status`,
  `document_type`, admin-only `employee`) reflecting `request.GET`, Actions column (view/edit-if-open/
  submit/cancel/delete-POST+confirm+csrf), pagination, empty-state. detail: purpose/addressed-to/
  copies/delivery fields, workflow buttons (Submit/Cancel/Approve/Reject/Fulfill) gated by `status` +
  `is_admin`/ownership, `output_file` download link once fulfilled, Actions sidebar. form: create/edit
  shared template (`is_edit` flag).
- [ ] `templates/hrm/requests/idcardrequest/{list,detail,form}.html` — same shape; detail shows
  `card_number`/`issued_at` once issued, an Issue action form (admin-only, `card_number` text input).
- [ ] `templates/hrm/requests/assetrequest/{list,detail,form}.html` — same shape; detail shows the linked
  `allocation` (serial number/asset tag) once fulfilled, a Fulfill action form (admin-only, optional
  `serial_number`/`asset_tag` inputs).
- [ ] All list/detail templates use exact model-choice values for badges with `{{ obj.get_<field>_display
  }}` fallback (CLAUDE.md Badge rule); reject/cancel action forms include the note/reason textarea +
  `{% csrf_token %}`.

## Verify

- [ ] `python manage.py makemigrations hrm` — review the generated file name/number before applying
  (expect `0043_...`).
- [ ] `python manage.py migrate`
- [ ] `python manage.py seed_hrm` — run **twice**; second run must be a no-op (NOTICE, zero new rows).
- [ ] `python manage.py check` — zero errors/warnings.
- [ ] `temp/` smoke sweep: every new `hrm:documentrequest_*`, `hrm:idcardrequest_*`, `hrm:assetrequest_*`,
  `hrm:my_requests` URL returns 200/302 (never 500); no `{#`/`{% comment` leak markers in rendered output.
- [ ] **Cross-tenant IDOR**: `admin_acme` hitting an `admin_globex` document/ID-card/asset-request pk (any
  action route: detail/edit/submit/cancel/approve/reject/fulfill) → 404.
- [ ] **ESS scoping**: a plain (non-admin) employee's `_list` shows only their own rows across all 3 new
  models; another employee's `_detail`/`_edit`/`_submit`/`_cancel` on a pk that isn't theirs →
  403/`PermissionDenied` or blocked redirect (not the object).
- [ ] **Self-approval**: an admin who is the requesting employee is blocked from approving/rejecting their
  own row (`_is_own_hr_request`), on all 3 models.
- [ ] **Reject requires `decision_note`**: a blank-note reject POST is rejected with an error message, on
  all 3 models.
- [ ] **AssetRequest fulfill** creates + links an `AssetAllocation` (`program=None`) atomically; confirm a
  second fulfill attempt on an already-`fulfilled` row is a no-op (status guard).
- [ ] **Document fulfill** upload passes through `_validate_upload` (reject a `.exe`/oversized file with a
  friendly error, not a 500).
- [ ] Sidebar shows all 6 3.26 entries as **Live** (5 bullets + My Requests) — confirm via the rendered
  sidebar, not just the `LIVE_LINKS` dict.

## Close-out

- [ ] Run the 7 review agents in order, applying findings + committing after each (one file per commit,
  no `git push`): `code-reviewer` → `explorer` → `frontend-reviewer` → `performance-reviewer` →
  `qa-smoke-tester` → `security-reviewer` → `test-writer`.
  - Expect `security-reviewer` to specifically probe the new `_can_manage_own_child`-gated
    submit/cancel (confirm it's actually wired, not just planned) and the `_is_own_hr_request`
    self-approval block on all 3 models — mirrors how the 3.25 pass's security review focused on the
    maker-checker anti-tamper design.
  - Expect `performance-reviewer` to check `_list`/`my_requests` use `select_related("employee__party",
    "approver")` (no N+1 across 3 new list pages + the 5-type hub).
  - Expect `test-writer` to cover: full CRUD × 3 models; the workflow chain (draft → pending →
    approved/rejected/cancelled + the fulfillment tail) × 3 models; self-approval block + reject-note
    requirement as their own dedicated security-test block (mirrors 3.21/3.25's weighting); the
    `AssetRequest` fulfill → `AssetAllocation` linkage; cross-tenant + cross-employee IDOR matrix on
    every action route.
- [ ] Update `.claude/skills/hrm/SKILL.md`: add a `### 3.26 Request Management (Self-Service) (3 tables)`
  section (model table + reuse notes), bump the frontmatter/overview built-list + model count, add a
  "Request Management (3.26)" routes-list section, document `_seed_requests(tenant)` in the seeder
  section, update the `LIVE_LINKS` section for `"3.26"`, update the Deferred section with this pass's
  carried-forward deferrals. Commit as its own file.
- [ ] README.md — add `/3.26` to the Module 3 header line (line ~265) + a new bullet describing the hub +
  3 new models + the maker-checker-adjacent approve/reject/fulfill workflow; refresh HRM test counts
  after `test-writer` runs.

## Later passes / deferred (carried over from research-hrm-3.26.md)

- **Multi-level configurable approval chains (1–5 stages), auto-forward-on-inactivity, reopen,
  auto-close** — greytHR Request Hub's differentiator; a cross-cutting workflow-engine feature better
  solved once, module-wide, not per sub-module.
- **SLA breach auto-escalation** — `needed_by` is captured now; the scheduled-job escalation/alerting
  engine is integration/later.
- **Auto-merge document generation from a template engine** (pull name/designation/DOJ/salary into a
  letter body) — v1 ships request → approve → HR-uploads-the-signed-file; template rendering is a
  follow-up pass.
- **Digital / e-signature on generated letters** — needs an e-sign provider integration, out of scope.
- **Email/courier dispatch automation for `delivery_method`** — the field is captured now; actual
  dispatch integration is later.
- **Linking `IdCardRequest` issuance into `hrm.AssetAllocation`** (the research's recommended
  `fulfilled_asset` FK) — the approved design simplified this to plain `card_number`/`issued_at` fields
  on the request itself; adding the `AssetAllocation` link later is additive, not a breaking change.
- **FAQ / knowledge-base article linkage per request type** — belongs with 3.27 Communication Hub / Help
  Desk, not 3.26.
- **CC/watcher notifications, push/email alerts on status change** — needs notification infrastructure
  common to many modules; not built per sub-module.
- **App/software/license access requests (SaaS, VPN, system access)** — needs a software/license
  inventory entity NavERP doesn't have yet; candidate for a future IT/Assets module (Module 11) pass.
- **Automatic asset-retrieval prompts on offboarding** — already indirectly covered by 3.4
  `SeparationCase` → `ClearanceItem` reusing `AssetAllocation`; no new 3.26 work needed.
- **Bulk document generation/download, catalog/SKU-level asset picker with pricing** — nice-to-have
  breadth features, not required for a first tenant-scoped CRUD pass.
- **Estimated cost / budget check before approval** on `AssetRequest` — not in the approved model's
  field list this pass (dropped from the research sketch); add `estimated_cost` in a later pass if
  procurement budget-checking becomes a requirement.

## Review notes

**3.26 Request Management (Self-Service) — BUILT & reviewed (2026-07-12).** As-built matches the plan: 3 new
`TenantNumbered` models (`DocumentRequest` DOCREQ-, `IdCardRequest` IDREQ-, `AssetRequest` ASSETREQ-) on the
`draft→pending→approved/rejected/cancelled` (+ fulfillment tail) lifecycle, a view-only **My Requests** hub, and the
two reuse bullets (Leave→3.10 `LeaveRequest`, Attendance Regularization→3.9 `AttendanceRegularization`, LIVE_LINKS
only). Reuses the 3.25 ESS helpers verbatim (`_ss_child_*`, `_ss_scope`, `_can_manage_own_child`,
`_require_own_profile`); new `_is_own_hr_request` self-approval guard + 5 shared `_hr_request_*` workflow helpers.
`assetrequest_fulfill` creates+links an `AssetAllocation`(program=None) atomically. Migrations 0043 (create) + 0044
(swap to the `(tenant,employee,status)` composite index). 10 templates under `templates/hrm/requests/`.

**Review-agent findings applied:**
- **explorer F1** — locked `status` readonly on the 3 admins (stop `/admin/` bypassing the workflow, esp. a
  fulfilled AssetRequest with `allocation=None`).
- **frontend-reviewer** — hub RTL-safe `margin-inline-start`, breadcrumb wording, dead-CSS drop; **and** scoped the
  My Requests hub to `employee=profile` (was `_ss_scope`, which showed admins the whole tenant on their own hub).
- **performance-reviewer** — `(tenant,employee,status)` composite index on all 3 models (parity with LeaveRequest);
  hub counts collapsed to one conditional aggregate (15→10 queries); dropped unused `approver`/`allocation` joins
  from the list querysets + the dead `employee__party` join on the hub recent list.
- **security-reviewer** — **Medium**: reordered `_hr_request_edit`/`_hr_request_delete` to check ownership BEFORE
  status (closed a cross-employee request-status oracle via the flash message); **Low**: dropped the plaintext
  `card_number` from the `idcardrequest_issue` audit metadata.
- **code-reviewer / qa-smoke-tester** — no code changes required (clean; qa verified the full lifecycle + IDOR + the
  atomic AssetAllocation creation end-to-end).
- **test-writer** — 258 tests (54 models + 116 views + 88 security), all green; full HRM suite still green.

**Deferred (as scoped):** configurable multi-level approval chains, SLA auto-escalation, template-driven letter
generation, e-signature, delivery-channel dispatch, notifications/watchers, software/license access requests,
linking ID-card issuance into `AssetAllocation`. **Next unbuilt HRM sub-module: 3.27 Communication Hub.**

---
# Module 3 — HRM — Sub-module 3.27 Communication Hub (hrm) — plan from research-hrm-3.27.md, authoritative design C:\Users\user\.claude\plans\snug-knitting-rose.md (2026-07-12)

**EXTENDS the existing `apps/hrm` app (already built through 3.26) — no new Django app, no new
`INSTALLED_APPS`/`config/urls.py` entries.** Covers 4 of the 5 NavERP.md 3.27 bullets with real models
(Announcements / Birthday-Anniversary / Surveys / Suggestions) + defers **Help Desk** to the future
**3.36 Helpdesk** sub-module — the 3.27 "Help Desk" `LIVE_LINKS` entry points at `hrm:suggestion_list`
as the interim lightweight query channel, with a code comment noting full ticketing lives in 3.36. Adds
**4 new tenant-scoped models** + a **derived `celebrations` view (no model)**.

Reuses (never duplicates): the ESS/viewer helpers already in `apps/hrm/views.py` — `_current_employee_profile`
(7429), `_is_admin` (7754), `_require_own_profile` (10366), `_can_manage_own_child` (10377), `_ss_scope`
(10386), `_ss_employees` (10397), `_ss_child_create`/`_ss_child_detail` (10457/10512) — plus, **critically**,
the 3.26 **generic** shared workflow helpers `_hr_request_submit`/`_hr_request_cancel`/`_hr_request_approve`/
`_hr_request_reject`/`_hr_request_edit`/`_hr_request_delete` + `_is_own_hr_request` (11006–11104), which take
`(request, model, pk, ...)` and are already model-agnostic — `Suggestion` reuses all six **verbatim, zero
edits**. `LearningPath.target_department`/`target_designation` (3.23, `apps/hrm/models.py:6307-6312`) is the
audience-targeting precedent for `Announcement`. `org_chart` (`apps/hrm/views.py:661`) is the derived-view
precedent for `celebrations` — same iterative/no-model/capped-queryset shape. No new core-spine entity;
nothing posts to the GL.

**IMPORTANT naming correction vs. the loose "reviewer/reviewed_at" phrasing in the research/design prose:**
`_hr_request_approve`/`_hr_request_reject` **hard-code** `obj.approver = request.user` and
`obj.approved_at = timezone.now()` (verified in `apps/hrm/views.py:11049-11085`) — they are NOT
field-name-configurable. For "`Suggestion` reuses `_hr_request_*` verbatim" to be literally true (not just
prose), `Suggestion`'s reviewer fields **must be named `approver`/`approved_at`**, exactly matching
`DocumentRequest`/`IdCardRequest`/`AssetRequest`. Building it with `reviewer`/`reviewed_at` instead would
silently break `suggestion_approve`/`suggestion_reject` (AttributeError) or force forking two helper
functions for one model — the less elegant path. **Use `approver`/`approved_at`.**

## Models (from research + the approved design)

- [ ] **`Announcement`** [`ANN-`, `TenantNumbered`] — admin-authored company news/updates feed (Announcements
  bullet).
  - `title` — CharField(max_length=255)
  - `body` — TextField (driver: Staffbase/Simpplr post body)
  - `category` — CharField(max_length=15), choices `general`/`news`/`policy`/`event`/`it`/`hr`/`benefits`,
    default `"general"` (driver: Simpplr categorization, BambooHR mixed-category widget)
  - `audience_type` — CharField(max_length=15), choices `all`/`department`/`designation`, default `"all"`
    (driver: Staffbase/Simpplr/Keka audience targeting; **copies the `LearningPath` 3.23 precedent**)
  - `target_department` — FK `core.OrgUnit` (`on_delete=SET_NULL`, null/blank,
    `limit_choices_to={"kind": "department"}`, `related_name="announcements"`) — same shape as
    `LearningPath.target_department`
  - `target_designation` — FK `hrm.Designation` (`on_delete=SET_NULL`, null/blank,
    `related_name="announcements"`) — same shape as `LearningPath.target_designation`
  - `is_pinned` — BooleanField, default `False` (driver: Zoho Connect "pin it up high", Keka)
  - `status` — CharField(max_length=10), choices `draft`/`published`/`archived`, default `"draft"`
    (driver: Staffbase editorial workflow, Simpplr draft/schedule/track)
  - `published_at` — DateTimeField, null/blank, `editable=False` — **workflow-owned**, stamped only by
    `announcement_publish`
  - `expires_at` — DateField, null/blank (driver: Simpplr lifecycle/auto-hide)
  - `author` — FK `settings.AUTH_USER_MODEL` (`on_delete=SET_NULL`, null/blank, `editable=False`,
    `related_name="hrm_announcement_authored"`) — **workflow-owned**, set to `request.user` server-side on
    create, never a form field (mirrors `DocumentRequest.approver` FK shape)
  - `clean()`: raise `ValidationError` if `audience_type == "department"` and `target_department` is blank,
    or `audience_type == "designation"` and `target_designation` is blank (matching-target-FK rule)
  - `Meta.ordering = ["-is_pinned", "-published_at", "-created_at"]`; `unique_together = ("tenant", "number")`;
    indexes `(tenant, status)` → `hrm_ann_tenant_status_idx`
  - `__str__`: `f"{self.number} · {self.title}"` (fallback to `self.title` when unsaved)
  - **Excluded from `AnnouncementForm`:** `tenant`, `number`, `status`, `author`, `published_at`

- [ ] **`Survey`** [`SUR-`, `TenantNumbered`] — admin-authored engagement survey (Surveys bullet).
  - `title` — CharField(max_length=255)
  - `description` — TextField, blank=True
  - `questions` — JSONField, list of `{"text": str, "type": "rating"|"text"|"single_choice", "options":
    [...]}` (driver: Lattice/Culture Amp/Officevibe question-type taxonomy — matches the approved
    structured-JSON build scope verbatim; a `rating` question with `min=0,max=10` covers the eNPS pattern
    with no extra schema)
  - `status` — CharField(max_length=10), choices `draft`/`open`/`closed`, default `"draft"`
  - `is_anonymous` — BooleanField, default `False` (driver: Culture Amp Inclusion-vs-Engagement,
    Officevibe anonymous-by-default — display-layer suppression in `survey_results`, `SurveyResponse.employee`
    still stored for respond-once)
  - `opens_at` / `closes_at` — DateField, null/blank (driver: Culture Amp/Officevibe response-window)
  - `author` — FK `settings.AUTH_USER_MODEL` (`on_delete=SET_NULL`, null/blank, `editable=False`,
    `related_name="hrm_survey_authored"`) — **workflow-owned**, set server-side on create
  - `Meta.ordering = ["-created_at"]`; `unique_together = ("tenant", "number")`; indexes `(tenant, status)`
    → `hrm_survey_tenant_status_idx`
  - `__str__`: `f"{self.number} · {self.title}"`
  - **Excluded from `SurveyForm`:** `tenant`, `number`, `status`, `author`

- [ ] **`SurveyResponse`** (`TenantOwned`, no number prefix — child of `Survey`, no standalone CRUD) — one
  employee's answers.
  - `survey` — FK `Survey` (`on_delete=CASCADE`, `related_name="responses"`)
  - `employee` — FK `hrm.EmployeeProfile` (`on_delete=CASCADE`, `related_name="survey_responses"`)
  - `answers` — JSONField, `{"<question_index>": <answer>}` map mirroring `questions`
  - `submitted_at` — DateTimeField, `auto_now_add=True`
  - `Meta.ordering = ["-submitted_at"]`; `unique_together = ("survey", "employee")` — **respond-once**
    (table-stakes across every survey leader surveyed); indexes `(tenant, survey)` →
    `hrm_survresp_tenant_survey_idx`, `(tenant, employee)` → `hrm_survresp_tenant_emp_idx`
  - `__str__`: `f"{self.survey} · {self.employee}"`
  - No `SurveyResponseForm` / no CRUD urls — created only via `survey_respond`, read only via
    `survey_results` aggregation (exempt from the CRUD-list rule, like `LearningPathItem`/`PayslipLine`).

- [ ] **`Suggestion`** [`SUG-`, `TenantNumbered`] — employee idea box, admin-reviewed; **clones the 3.26
  request lifecycle field-for-field** so `_hr_request_*` applies with zero modification (Suggestions bullet).
  - `employee` — FK `hrm.EmployeeProfile` (`on_delete=CASCADE`, `related_name="suggestions"` — **named
    `employee` so `_ss_scope`/`_can_manage_own_child`/`_is_own_hr_request` all work unmodified**)
  - `title` — CharField(max_length=255)
  - `body` — TextField
  - `category` — CharField(max_length=20), choices `process`/`workplace`/`product`/`cost_saving`/
    `wellbeing`/`other`, default `"other"` (driver: Qandle IdeaBox / Workhub / SuggestionOx category pattern)
  - `is_anonymous` — BooleanField, default `False` (driver: SuggestionOx/Workhub/EngageWith anonymous
    submission — display-layer suppression, `employee` FK still stored)
  - `status` — CharField(max_length=10), choices `draft`/`pending`/`approved` (label **"Accepted"**)/
    `rejected`/`cancelled`/`implemented`, default `"draft"`
  - `OPEN_STATUSES = ("draft", "pending")` — exact 3.26 sibling constant
  - `approver` — FK `settings.AUTH_USER_MODEL` (`on_delete=SET_NULL`, null/blank,
    `related_name="hrm_suggestion_approvals"`) — **workflow-owned** (field name required by
    `_hr_request_approve`/`_hr_request_reject`, see naming-correction note above)
  - `approved_at` — DateTimeField, null/blank — **workflow-owned** (same reason)
  - `decision_note` — TextField, blank — **workflow-owned** (set by `_hr_request_cancel`/`_hr_request_reject`)
  - `implementation_note` — TextField, blank — **workflow-owned**, set only by `suggestion_implement`
    (driver: Workhub "assign tasks, follow up" outcome tracking; mirrors `DocumentRequest.output_file`
    tail-state pattern)
  - `implemented_at` — DateTimeField, null/blank, `editable=False` — **workflow-owned**, set only by
    `suggestion_implement` (`approved → implemented`)
  - `Meta.ordering = ["-created_at"]`; `unique_together = ("tenant", "number")`; indexes
    `(tenant, employee, status)` → `hrm_sug_tenant_emp_status_idx` (matches the `DocumentRequest`/
    `IdCardRequest`/`AssetRequest` sibling pattern), `(tenant, status)` → `hrm_sug_tenant_status_idx`
  - `__str__`: `f"{self.number} · {self.employee} · {self.title}"`
  - **Excluded from `SuggestionForm`:** `tenant`, `number`, `status`, `employee`, `approver`, `approved_at`,
    `decision_note`, `implementation_note`, `implemented_at`

- [ ] **Confirm `Celebrations` needs NO model** — pure derived read off `hrm.EmployeeProfile.date_of_birth`
  (line 293) + `core.Employment.hired_on` (line 177, joined via `EmployeeProfile.employment`), computed
  month/day-window in the view (mirrors `org_chart`'s no-table, capped-queryset, Python-bucketed shape).
  Confirmed by every leader surveyed (BambooHR, greytHR, Darwinbox, SAP SuccessFactors all compute this as
  a derived tile, never a stored record).

Add all 4 new classes after `AssetRequest` (current end of `models.py`) under a new
`# --- 3.27 Communication Hub ---` section-header comment stating what's reused (`EmployeeProfile`,
`core.OrgUnit`, `hrm.Designation`, the 3.26 `_hr_request_*` helpers) and that Celebrations gets **no** model.

## Backend (apps/hrm/)

- [ ] **models.py** — add `Announcement`, `Survey`, `SurveyResponse`, `Suggestion` per the field lists above.
- [ ] **migration** — `python manage.py makemigrations hrm` (expect `0045_announcement_survey_...`,
  incrementing from `0044`); review the generated filename before applying.
- [ ] **forms.py** — new `# --- 3.27 Communication Hub ---` section banner, then:
  - `AnnouncementForm(TenantModelForm)` — fields `["title", "body", "category", "audience_type",
    "target_department", "target_designation", "is_pinned", "expires_at"]`, `Textarea` widget on `body`;
    `clean()` re-asserts the matching-target-FK rule (mirrors the model `clean()` so the form surfaces it
    inline, not just on `full_clean()`).
  - `SurveyForm(TenantModelForm)` — fields `["title", "description", "questions", "is_anonymous",
    "opens_at", "closes_at"]`; `questions` widget = `Textarea`; `clean_questions()` parses the textarea as
    JSON and validates it's a list of `{"text": str, "type": one of rating/text/single_choice, "options":
    list (required when type=="single_choice")}` dicts, raising `ValidationError` with a specific message
    per bad entry (index-numbered) rather than a generic "invalid JSON".
  - `SuggestionForm(TenantModelForm)` — fields `["title", "body", "category", "is_anonymous"]`,
    `Textarea` on `body` — mirrors `AssetRequestForm`'s shape exactly (employee resolved server-side by
    `_ss_child_create`).
  - The survey-respond page's dynamic form is **not** a `ModelForm** — built in the view as a plain
    `forms.Form` subclass assembled field-by-field from `survey.questions` (rating → `ChoiceField`/
    `IntegerField` 0–10, text → `CharField(widget=Textarea)`, single_choice → `ChoiceField(choices=
    options)`), styled like the existing `_ThemedForm` base.
- [ ] **views.py** — new `# --- 3.27 Communication Hub ---` section banner, then:
  - `celebrations(request)` (`@login_required`) — mirrors `org_chart` (661): active employees
    `select_related("party", "employment")`, `?window=` (default 30, cap e.g. 90) days-ahead, compute
    upcoming birthdays (`date_of_birth` month/day, handling year-wrap) and work anniversaries
    (`employment.hired_on` month/day + computed tenure-years), cap 500 employees, bucket in Python,
    render `hrm/communication/celebrations.html`.
  - **Announcement**: `announcement_list` (`@login_required` — base qs
    `Announcement.objects.filter(tenant=request.tenant).select_related("target_department",
    "target_designation", "author")`; if `_is_admin(request.user)`: full qs + `crud_list` filters
    `status`/`category`/`audience_type`; else: `profile = _current_employee_profile(request)`, filter
    `status="published"`, `Q(expires_at__isnull=True) | Q(expires_at__gte=today)`, and
    `Q(audience_type="all") | Q(audience_type="department", target_department=<profile's org_unit>) |
    Q(audience_type="designation", target_designation=profile.designation_id)`); `announcement_detail`
    (`@login_required`, 403 for a non-admin whose audience doesn't match / not published); `announcement_create`/
    `_edit`/`_delete` (`@tenant_admin_required`, `crud_create`/`crud_edit`/`crud_delete`, `author=request.user`
    stamped server-side on create — never a form field); `announcement_publish` (`@tenant_admin_required
    @require_POST`, `draft → published`, stamps `published_at=timezone.now()`); `announcement_archive`
    (`@tenant_admin_required @require_POST`, `published → archived`).
  - **Survey**: `survey_list`/`survey_detail` (`@login_required` — readable by every employee, not
    admin-gated, so they can see open surveys to respond); `survey_create`/`_edit`/`_delete`
    (`@tenant_admin_required`); `survey_open`/`survey_close` (`@tenant_admin_required @require_POST`,
    `draft → open` / `open → closed`); `survey_respond` (`@login_required`: 404 unless `status="open"`;
    block a second submission — `SurveyResponse.objects.filter(survey=survey, employee=profile).exists()`
    → error redirect; render/validate the dynamic `forms.Form`, save `SurveyResponse(answers=...)`);
    `survey_results` (`@tenant_admin_required`: aggregate `responses` — per-`rating` question average +
    count, per-`single_choice` question frequency counts, per-`text` question the raw answer list;
    **when `survey.is_anonymous`, never attach `response.employee` to the template context for text
    answers** — display-layer suppression only, per the approved design).
  - **Suggestion** (thin wrappers delegating to the shared 3.26 helpers, all `Suggestion`-typed):
    `suggestion_list` (`@login_required`, `_ss_scope`-filtered qs `select_related("employee__party",
    "approver")`, `crud_list` search `number`/`title`/`body` + filters `status`/`category`, `extra_context`
    = `status_choices`, `category_choices` = `Suggestion.CATEGORY_CHOICES`, `employees` when admin);
    `suggestion_detail` = `_ss_child_detail(request, Suggestion, pk, "hrm/communication/suggestion/detail.html",
    select_related=("employee__party", "approver"))`; `suggestion_create` = `_ss_child_create(request,
    SuggestionForm, "hrm/communication/suggestion/form.html", "hrm:suggestion_list")`; `suggestion_edit` =
    `_hr_request_edit(request, Suggestion, pk, SuggestionForm, "hrm/communication/suggestion/form.html",
    "hrm:suggestion_detail")`; `suggestion_delete` = `_hr_request_delete(request, Suggestion, pk,
    "hrm:suggestion_list")`; `suggestion_submit` = `_hr_request_submit(request, Suggestion, pk,
    "hrm:suggestion_detail")`; `suggestion_cancel` = `_hr_request_cancel(request, Suggestion, pk,
    "hrm:suggestion_detail")`; `suggestion_approve` = `_hr_request_approve(request, Suggestion, pk,
    "hrm:suggestion_detail")`; `suggestion_reject` = `_hr_request_reject(request, Suggestion, pk,
    "hrm:suggestion_detail")` — all six **verbatim, no per-model overrides**, self-approval blocked by
    `_is_own_hr_request` and reject requiring a non-blank `decision_note` for free. New
    `suggestion_implement` (`@tenant_admin_required @require_POST`): `approved → implemented`, stamps
    `implemented_at=timezone.now()`, optional `implementation_note` from POST, `write_audit_log(...,
    {"action": "implement"})`.
  - All list views follow the Filter Implementation Rules (CLAUDE.md): every `*_choices`/queryset the
    template needs is passed explicitly in `extra_context`; string-field comparisons use
    `request.GET.status == value`; FK/pk comparisons use `|stringformat:"d"`.
- [ ] **urls.py** — append a `# 3.27 Communication Hub` block under the existing 3.26 block:
  `celebrations/` (`celebrations`); `announcements/` + `add/` + `<int:pk>/{,edit/,delete/,publish/,
  archive/}` (5 CRUD + 2 actions, names `announcement_*`); `surveys/` + `add/` + `<int:pk>/{,edit/,
  delete/,open/,close/,respond/,results/}` (5 CRUD + 4 actions, names `survey_*`); `suggestions/` + `add/`
  + `<int:pk>/{,edit/,delete/,submit/,cancel/,approve/,reject/,implement/}` (5 CRUD + 5 actions, names
  `suggestion_*`) — mirrors the `document-requests/`/`asset-requests/` block shape exactly.
- [ ] **admin.py** — register `AnnouncementAdmin`, `SurveyAdmin`, `SurveyResponseAdmin`, `SuggestionAdmin`
  (`list_display`/`list_filter`/`search_fields` mirroring `DocumentRequestAdmin` et al.). **Repeat the
  3.26 explorer-F1 fix from day one**: put every workflow-owned field in `readonly_fields` (`status`,
  `published_at`, `author` on Announcement/Survey; `status`, `approver`, `approved_at`,
  `implementation_note`, `implemented_at` on Suggestion) so `/admin/` can't bypass the publish/approve/
  implement workflow (e.g. hand-editing a `Suggestion` to `implemented` with `approver=None`).
- [ ] **seed_hrm.py** — new `_seed_communication(self, tenant, *, flush)` method, called from `handle()`
  immediately after `self._seed_requests(tenant, flush=options["flush"])` (new last call in the per-tenant
  loop):
  - `if flush:` delete `Suggestion`, `SurveyResponse`, `Survey`, `Announcement` — filtered by `tenant`
    (delete `SurveyResponse` before `Survey`/`EmployeeProfile` for a tidy explicit teardown, though CASCADE
    makes ordering non-blocking).
  - Idempotency guard: `if Announcement.objects.filter(tenant=tenant).exists():` → NOTICE + return.
  - Reuse existing `EmployeeProfile` rows + `actor = get_user_model().objects.filter(tenant=tenant).first()`
    (same style as `_seed_requests`).
  - Demo data: 3 `Announcement`s (one `published`/`audience_type="all"`/`is_pinned=True`; one `published`/
    `audience_type="department"` with a real `target_department`; one `draft`); 2 `Survey`s (one `status="open"`
    with 2–3 `SurveyResponse`s from seeded employees covering all 3 question types, one `status="draft"`
    with no responses); 3 `Suggestion`s spanning `pending`/`approved`/`implemented` (the `implemented` one
    stamped `approver`/`approved_at`/`implementation_note`/`implemented_at`, seeded directly in its
    end-state — matching `_seed_requests`'s convention, not replayed through the view actions).
  - Insert `Suggestion, SurveyResponse, Survey, Announcement,` into the `_seed_tenant` flush teardown tuple
    immediately before the existing 3.26 `AssetRequest, IdCardRequest, DocumentRequest,` line, with a
    one-line ordering comment.
  - ASCII-only `self.stdout.write(...)` (repeat of the 3.20/3.21/3.26 cp1252 bug — no arrows/em-dashes).
  - Both `management/__init__.py` and `management/commands/__init__.py` already exist — no new dirs.

## Wire-up

- [ ] `config/settings.py` / `config/urls.py` — already wired for `apps.hrm`; no change needed.
- [ ] `apps/core/navigation.py` — new `LIVE_LINKS["3.27"]` block placed immediately after the existing
  `"3.26"` block, bullet text copied **verbatim** from `NavERP.md` 3.27 (lines 622–627):
  ```python
  "3.27": {
      "Announcements": "hrm:announcement_list",         # bullet (new Announcement CRUD + publish/pin/archive)
      "Birthday/Anniversary": "hrm:celebrations",        # bullet (derived view, no model)
      "Surveys": "hrm:survey_list",                      # bullet (new Survey + SurveyResponse)
      "Suggestions": "hrm:suggestion_list",               # bullet (new Suggestion, clones 3.26 workflow)
      "Help Desk": "hrm:suggestion_list",                # bullet (DEFERRED to future 3.36 Helpdesk — interim: Suggestions box)
  },
  ```

## Templates (templates/hrm/communication/)

- [ ] `templates/hrm/communication/celebrations.html` — standalone sub-module-root page (derived, no
  entity folder): `?window=` selector, two sections (Upcoming Birthdays / Upcoming Work Anniversaries),
  each row shows name/department/date/days-away, empty-state when nothing in the window.
- [ ] `templates/hrm/communication/announcement/{list,detail,form}.html` — list: filter bar (`status`,
  `category`, `audience_type` — admin-only; employees see only their matching feed with no filter bar),
  pinned rows visually distinguished, Actions column (view/edit/delete-POST+confirm+csrf +
  publish/archive buttons gated by `status`+`is_admin`), pagination, empty-state. detail: body render,
  audience/category/pin badges, Publish/Archive/Edit/Delete actions gated by `status`+`is_admin`. form:
  create/edit shared (`is_edit` flag), `target_department`/`target_designation` fields shown/required only
  when `audience_type` matches (progressive disclosure via a small inline script or just always-visible
  with the `clean()` validation as the source of truth).
- [ ] `templates/hrm/communication/survey/{list,detail,form,respond,results}.html` — list/detail visible
  to all employees (filter bar admin-only), Actions column gated by `status`+`is_admin`
  (Open/Close/Results for admins, "Take Survey" link for employees while `status="open"` and they haven't
  responded yet — hide/disable if `SurveyResponse` already exists for them). `respond.html` renders the
  dynamic per-question form. `results.html` shows per-question aggregates (bar/count table, no chart lib
  needed), respecting `is_anonymous`.
- [ ] `templates/hrm/communication/suggestion/{list,detail,form}.html` — same shape as
  `templates/hrm/requests/documentrequest/*` (list: filter bar `status`/`category`, Actions
  view/edit-if-open/submit/cancel/delete; detail: workflow buttons Submit/Cancel/Approve/Reject/Implement
  gated by `status`+`is_admin`/ownership, `is_anonymous` suppresses the employee name in admin-facing
  list/detail when set; form: create/edit shared).
- [ ] All list/detail templates use exact model-choice values for badges with `{{ obj.get_<field>_display
  }}` fallback (CLAUDE.md Badge rule); reject/cancel/implement action forms include the note textarea +
  `{% csrf_token %}`.
- [ ] `templates/hrm/hrm_overview.html` — add 1–2 `<a class="stat-card">` tiles into the existing
  `.stat-grid` (mirrors the `pending_regularizations`/`pending_overtime` tiles at lines 27–30): e.g.
  `stats.birthdays_this_month` → `{% url 'hrm:celebrations' %}` and `stats.pinned_announcements` →
  `{% url 'hrm:announcement_list' %}?status=published`; extend the `stats` dict in `hrm_overview` (view,
  line 381) with the two new counts (`EmployeeProfile.date_of_birth__month=today.month` count;
  `Announcement.objects.filter(tenant=tenant, status="published", is_pinned=True)` count).

## Verify

- [ ] `python manage.py makemigrations hrm` — review the generated file name/number (expect `0045_...`)
  before applying.
- [ ] `python manage.py migrate`
- [ ] `python manage.py seed_hrm` — run **twice**; second run must be a no-op (NOTICE, zero new rows).
- [ ] `python manage.py check` — zero errors/warnings.
- [ ] `temp/` smoke sweep: every new `hrm:celebrations`, `hrm:announcement_*`, `hrm:survey_*`,
  `hrm:suggestion_*` URL returns 200/302 (never 500); no `{#`/`{% comment` leak markers in rendered output;
  a seeded record renders on every list/detail page.
- [ ] **Cross-tenant IDOR**: `admin_acme` hitting an `admin_globex` announcement/survey/suggestion pk (any
  action route: detail/edit/delete/publish/archive/open/close/respond/results/submit/cancel/approve/
  reject/implement) → 404.
- [ ] **Announcement audience filtering**: a plain employee's `announcement_list`/`_detail` shows only
  `published`, un-expired rows whose audience matches them (`all`, or their own department, or their own
  designation) — never a `draft`/`archived`/expired/other-audience row, even by direct-pk URL guess.
- [ ] **Survey respond-once + anonymity**: a second `survey_respond` POST from the same employee on the
  same survey is blocked (error, not a duplicate row or 500); `survey_respond` on a `draft`/`closed`
  survey → blocked; `survey_results` on an `is_anonymous=True` survey never renders a respondent's name
  next to their text answer.
- [ ] **Suggestion workflow + self-approval block**: employee `draft → pending`
  (`suggestion_submit`) → admin `suggestion_approve`/`suggestion_reject` → `suggestion_implement`
  (`approved → implemented`); an admin who is also the requesting employee is blocked from
  approving/rejecting their own row (`_is_own_hr_request`); a blank-note `suggestion_reject` POST is
  rejected with an error, not a silent no-op.
- [ ] `celebrations` renders upcoming birthdays + anniversaries for the seeded employees within the
  default window; `?window=` param changes the result set without erroring on an out-of-range value.
- [ ] Sidebar shows all 5 3.27 entries as **Live** (confirm via the rendered sidebar, not just the
  `LIVE_LINKS` dict) — note "Help Desk" and "Suggestions" both point at `hrm:suggestion_list` by design.

## Close-out

- [ ] Run the 7 review agents in order, applying findings + committing after each (one file per commit,
  no `git push`): `code-reviewer` → `explorer` → `frontend-reviewer` → `performance-reviewer` →
  `qa-smoke-tester` → `security-reviewer` → `test-writer`.
  - Expect `security-reviewer` to specifically probe: the `announcement_detail` audience-visibility gate
    for a direct-pk guess by a non-matching employee; the `survey_respond` respond-once + open-window
    guards; and the `Suggestion` self-approval block (confirm `approver`/`approved_at` naming actually
    made verbatim `_hr_request_*` reuse work, not a silently-forked copy).
  - Expect `performance-reviewer` to check `announcement_list`/`suggestion_list`/`survey_results` use
    `select_related`/`prefetch_related` appropriately (no N+1 across `responses` aggregation in
    `survey_results`, no N+1 on `target_department`/`target_designation`/`author` in `announcement_list`).
  - Expect `test-writer` to cover: full CRUD × 4 models; `Announcement` audience-matrix (all/department/
    designation × draft/published/archived/expired) as its own dedicated test block; `Survey` respond-once
    + anonymity + open/closed-window guards; `Suggestion`'s full workflow chain + self-approval + reject-note
    requirement (mirrors 3.26's weighting); `celebrations` date-window math (including year-wrap); cross-tenant
    IDOR matrix on every action route.
- [ ] Update `.claude/skills/hrm/SKILL.md`: add a `### 3.27 Communication Hub (4 tables)` section (model
  table + reuse notes, incl. the `approver`/`approved_at` naming-correction rationale), bump the
  frontmatter/overview built-list + model count, add a "Communication Hub (3.27)" routes-list section,
  document `_seed_communication(tenant)` in the seeder section, update the `LIVE_LINKS` section for
  `"3.27"`, update the Deferred section with this pass's carried-forward deferrals. Commit as its own file.
- [ ] README.md — add `/3.27` to the Module 3 header line + a new bullet describing the hub + 4 new
  models + the Help-Desk-deferred-to-3.36 note; refresh HRM test counts after `test-writer` runs.

## Later passes / deferred (carried over from research-hrm-3.27.md)

- **Announcement read receipts / mandatory-read tracking + reminder nudges** (Zoho Connect, Staffbase) —
  needs a new `AnnouncementRead` join table + a reminder job; a 5th model, out of scope for this pass.
- **Announcement reactions/comments/view-count social layer** (Zoho Connect, Keka, Darwinbox Vibe) — a
  generic engagement layer better suited to a future cross-module "social" pass, not core comms.
- **Multi-language/auto-translate announcements** (Zoho Connect) — external translation service integration.
- **Email/push/digital-signage delivery fan-out for announcements** (BambooHR, Staffbase) — reuses existing
  notification infra later; ships in-app-only this pass.
- **Manager T-1 celebration reminder emails** (BambooHR) — a scheduled-job/notification concern layered on
  the derived `celebrations` view; the underlying data already supports it.
- **Employee-controlled "wish me on" privacy toggle** (greytHR) — a possible future `EmployeeProfile`
  field, not needed for the first derived-view pass.
- **Birthday/anniversary eCards, kudos/wish posting tied to celebrations** (BambooHR, greytHR, Darwinbox) —
  NavERP already has `KudosBadge` (3.19/3.20); `celebrations` stays display-only.
- **Survey minimum-group-size (k-anonymity) reporting threshold** (Culture Amp, Officevibe) — nice-to-have
  refinement on top of the already-enforced identity-suppression rule.
- **AI-summarized open-text survey feedback** (Workday Peakon Illuminate) — external AI service integration.
- **Survey question templates / reusable libraries** (Culture Amp, Lattice) — the structured JSON
  `questions` field already supports manual reuse; a dedicated template model is over-scope.
- **Suggestion upvote/downvote and peer-support counts** (SuggestionOx, EngageWith, Qandle) — needs a new
  `SuggestionVote` join table; natural v2 extension.
- **Suggestion two-way anonymous follow-up threads** (SuggestionOx) — needs a comment/thread model.
- **Suggestion-to-recognition auto-link on implementation** (Vantage Circle, Workhub) — could reuse
  `KudosBadge` later via a manual cross-reference; not a new FK this pass.
- **Help Desk (HR ticket system)** — fully deferred to the future dedicated **3.36 Helpdesk** sub-module
  (Ticket Management, Categories, SLA, Knowledge Base, Satisfaction Survey) per NavERP.md; not designed here.

## Review notes

**3.27 Communication Hub — BUILT & reviewed (2026-07-12).** As-built matches the plan: 4 new models
(`Announcement` ANN-, `Survey` SUR- + `SurveyResponse`, `Suggestion` SUG-) + a derived `celebrations` view (no
model). Announcement audience targeting reuses the `LearningPath` 3.23 precedent; Suggestion clones the 3.26 request
lifecycle field-for-field (`employee` + `approver`/`approved_at`) so the `_hr_request_*` helpers apply verbatim.
Migration 0045. 12 templates under `templates/hrm/communication/` + 2 `hrm_overview` stat-cards. Help Desk deferred
to the future 3.36 Helpdesk (its `LIVE_LINKS` bullet → the Suggestions box interim). Scope confirmed with the user
(Full hub) before building.

**Review-agent findings applied:**
- **code-reviewer** — **Critical**: `survey_delete` lacked a view-level status guard (a direct POST could delete an
  open survey + CASCADE its responses) → now draft-only; `announcement_create`/`survey_create` lacked the
  `request.tenant is None` guard (superuser → IntegrityError 500) → added. **Important**: the announcement employee
  audience `Q` null-matched a `SET_NULL`'d target → now skips the clause when the viewer's id is None (consistent
  with `_announcement_targets`); `survey_respond` respond-once was check-then-create → wrapped in
  `try/except IntegrityError`. **Minor**: overview pinned tile → `?status=published`.
- **explorer** — all wiring consistent; aligned the `birthdays_this_month` tile to exclude terminated employees
  (matching the celebrations page).
- **frontend-reviewer** — `badge-warning` → `badge-amber` (invented class, lesson L33); survey-list empty-row
  colspan adjusts for the admin-only column; survey-results gates the per-question cards on `response_count`, wraps
  the choice table in `.table-wrap` + `<thead>`, uses logical `text-align:end`; logical `padding-inline-start`.
- **performance-reviewer** — no N+1; celebrations `capped` indicator (org_chart parity); dropped unused
  announcement-list joins; `list_select_related` on the two new admins.
- **qa-smoke-tester** — 98 assertions PASSED end-to-end (created + cleaned up throwaway linked employee users to
  verify the audience feed, survey respond-once, and the self-approval guard); no code changes needed.
- **security-reviewer** — no Critical/High/Medium; **Low**: audience-scoped the overview "Pinned Announcements" tile
  for non-admins (was an aggregate-count disclosure of other-audience announcements).
- **test-writer** — 280 tests (models/views/security), all green; full HRM suite still green.

**Deferred (as scoped):** read receipts / mandatory-read tracking, reactions/comments, delivery fan-out (email/push),
manager reminders, survey k-anonymity threshold / AI summaries / templates, suggestion voting / threads / recognition
auto-link, and the full **Help Desk ticketing system → the dedicated 3.36 Helpdesk sub-module**. **Next unbuilt HRM
sub-module: 3.28 HR Reports.**

---
# Module 3 — HRM — Sub-module 3.28 HR Reports (hrm) — plan from research-hrm-3.28.md (2026-07-12)

**EXTENDS the existing `apps/hrm` app (already built through 3.27) — no new Django app, no new
`INSTALLED_APPS`/`config/urls.py` entries.** This is a **derived-view, read-only reporting sub-module** —
**NO new models, NO migration, NO seeder** — mirroring `apps/accounting/views.py`'s `trial_balance`/
`ap_aging`/`balance_sheet` (`accounting/reports/*.html`) and, closer to home, HRM's own existing derived
reports `timesheet_utilization_report`/`project_time_report` (`apps/hrm/views.py:1678-1699`, rendered from
`templates/hrm/timetracking/utilization_report.html`) and `org_chart`/`celebrations` (no-model, capped,
Python-bucketed views). All 6 report views read data that already exists via `seed_hrm` — nothing new to
seed.

**Sensitivity decision (stated, not left implicit):** these 6 reports aggregate **company-wide** salary,
attrition, and demographic data (gender, age, exit reasons, department-level pay) — not an individual
employee's own record. Unlike `timesheet_utilization_report` (per-employee operational data, `@login_required`
only), 3.28 mirrors the privileged-action precedent already used elsewhere in `apps/hrm/views.py` (leave
approval, encashment approval, payroll-cycle approval — all `@tenant_admin_required`, imported from
`apps.core.decorators`). **All 6 views use `@tenant_admin_required`, not `@login_required`.** A regular
employee hitting any `hrm:*_report` URL gets a 403 (`PermissionDenied`), same as every other admin-only HRM
action route.

## 1. Confirm NO new models / migration / seeder — source fields verified against the codebase

- [ ] State in the PR/commit message: **3.28 adds zero models, zero migrations, zero seed data** — pure
  aggregation views over existing tenant-scoped rows.
- [ ] **Headcount Report** reads: `core.Employment` (`party`, `org_unit` FK `core.OrgUnit`, `hired_on`,
  `status` ∈ active/on_leave/terminated — `apps/core/models.py:167-188`); `hrm.EmployeeProfile`
  (`employment` OneToOne, `designation` FK `hrm.Designation`, `employee_type` — `apps/hrm/models.py:257-345`,
  `.department` is a **Python property**, not a DB column — see gotcha below); `hrm.Designation
  .budgeted_headcount` (`apps/hrm/models.py:147`); `hrm.SeparationCase.actual_last_working_day`
  (`apps/hrm/models.py:1648-1657`, for excluding/counting exits). **All fields confirmed to exist —
  no gaps.**
- [ ] **Attrition Report** reads: `hrm.SeparationCase` (`employee` FK `EmployeeProfile`, `separation_type`,
  `exit_reason`, `actual_last_working_day`, `status` — `apps/hrm/models.py:1599-1705`) + `core.Employment`
  (active-count denominator for the SHRM annualized-turnover formula). **Voluntary/involuntary is a Python
  mapping constant** (`resignation`/`retirement`/`contract_end` → voluntary; `termination`/`layoff`/
  `deceased` → involuntary — no such field exists on the model, confirmed by reading
  `SEPARATION_TYPE_CHOICES`). **All fields confirmed — no gaps.**
- [ ] **Diversity Report** reads: `hrm.EmployeeProfile.gender` (`GENDER_CHOICES` —
  male/female/other/prefer_not_to_say, line 270-275) + `.date_of_birth` (line 293); `core.Employment
  .hired_on`/`.org_unit`. **All fields confirmed — no gaps.**
- [ ] **Cost Report** reads: `hrm.Payslip` (`gross_pay`, `net_pay`, `total_deductions`, `employee`,
  `cycle` FK `PayrollCycle` — `apps/hrm/models.py:3554-3673`) + `hrm.PayslipLine` (`component_type`,
  `contribution_side`, `amount` — line 3676-3704) for a chosen `PayrollCycle`; fallback when the tenant
  has **no** `PayrollCycle` yet: `hrm.EmployeeSalaryStructure.annual_ctc_amount` (status="active") ÷ 12 as
  a "current run-rate" proxy (line 3415-3460). **All fields confirmed — no gaps.**
- [ ] **Hiring Report** reads: `hrm.JobRequisition` (`created_at` via `TenantOwned`, `posted_at`,
  `filled_at`, `department`/`cost_center` FK `core.OrgUnit`, `hiring_manager`/`recruiter` FK
  `EmployeeProfile`, `headcount`, `status` — `apps/hrm/models.py:2169-2298`); `hrm.JobApplication`
  (`stage`, `source`, `applied_at`, `stage_changed_at`, `hired_on`, `requisition`, `candidate` —
  line 2569-2609); `hrm.CandidateProfile.source` (`CANDIDATE_SOURCE_CHOICES` — line 2482-2537). **All
  fields confirmed — no gaps** (both `JobApplication.source` and `CandidateProfile.source` exist; use
  `JobApplication.source` as the primary source-of-hire field since it's per-application/per-hire).
- [ ] **Gotcha to encode in every view that touches `EmployeeProfile.department`/`.manager`**:
  these are **Python `@property`s** derived from `self.employment.org_unit`/`.manager`
  (`apps/hrm/models.py:342-349`), **not DB columns** — never `EmployeeProfile.objects.filter(department=x)`
  or `.values("department")`; always aggregate through `employment__org_unit` (a real FK path) or resolve
  in Python. This is the exact gotcha called out in the 3.21 plan (line 25-29 above) — it applies here too
  and is the single most likely cause of a report 500 if missed.
- [ ] No field gaps degrade any report to a 500 — everything above already exists; div-by-zero (empty
  tenant, zero average headcount, zero total hires) is a **view-logic** guard (see §2), not a data gap.

## 2. Views (apps/hrm/views.py) — new `# --- 3.28 HR Reports ---` banner (append after the 3.27 block, ~line 11916 = current EOF)

- [ ] All 6 functions decorated `@tenant_admin_required` (imported already: `from apps.core.decorators
  import tenant_admin_required`, `apps/hrm/views.py:31`). Follow the `if tenant is not None:` guard
  pattern from `trial_balance`/`timesheet_utilization_report` (superuser has `tenant=None` — never
  `.filter(tenant=None)`; render an empty report instead of a crash).
- [ ] Shared filter helpers: reuse `_parse_iso_date` (`apps/hrm/views.py:359-364`) for `?date_from`/
  `?date_to`/`?as_of`; a small **new** `_default_period()` helper returning `(today - 365 days, today)`
  when both are blank (the research's "trailing 12 months / YTD default" — pick trailing-12-months as the
  single consistent default across all 5 reports so the index tiles and the drill-in report agree).
  `?department=<OrgUnit pk>` parsed via `int(request.GET.get("department") or 0) or None`, validated with
  `OrgUnit.objects.filter(tenant=tenant, kind="department", pk=department_id).first()` (never trust the
  raw pk into a filter without tenant-scoping it first — this is the IDOR-prevention pattern already used
  elsewhere in the file).
- [ ] `hr_reports_index(request)` — `/hrm/reports/hr/`. No filters (optional single `?as_of` passed through
  to child report links). 5 KPI tiles, each a `{label, value, url}` dict:
  current active headcount (`Employment.objects.filter(tenant=tenant, status="active").count()`),
  YTD annualized attrition % (reuse the attrition-calc helper below over Jan-1→today), gender split
  (`EmployeeProfile` gender counts as a %), MTD salary cost (current-month `Payslip` sum, fallback CTC
  run-rate), avg time-to-fill days (`JobRequisition` with `filled_at` in the last 12 months). Render
  `hrm/reports/hr_index.html`.
- [ ] `headcount_report(request)` — KPIs: total active headcount as-of `?as_of` (default today),
  new joins in `?date_from`/`?date_to` (`Employment.hired_on` between range), exits in range
  (`SeparationCase.actual_last_working_day` between range, `status` in the completed/terminal set), net
  change (joins − exits), actual-vs-budgeted headcount (group `EmployeeProfile` by `designation`, compare
  `count()` to `designation.budgeted_headcount`, `None` budget renders as "—" not `0`). Tables: by
  department (`Employment.objects.values("org_unit__name").annotate(count=Count("id"))`, active only,
  filtered by `?department` when set), by designation, by employment type. Chart: trailing-12-month
  headcount trend — iterate the last 12 month-end dates, `Employment.filter(status="active", hired_on__lte=
  month_end).count()` minus terminations before that date (or simpler: count `Employment` rows whose
  `hired_on <= month_end` and not yet exited by `month_end` via a `SeparationCase` join) — keep this O(12)
  queries, not O(employees). Render `hrm/reports/headcount.html`.
- [ ] `attrition_report(request)` — KPIs: total separations in period
  (`SeparationCase.objects.filter(tenant=tenant, actual_last_working_day__range=(date_from, date_to))`),
  annualized turnover % = `separations / avg_headcount * 100` where `avg_headcount = (headcount_at_start +
  headcount_at_end) / 2` (**guard `avg_headcount == 0` → 0%, not a `ZeroDivisionError`**; annualize when
  the period spans < 365 days per the SHRM note: `rate * (365 / period_days)`), voluntary % / involuntary %
  (Python mapping constant `VOLUNTARY_SEPARATION_TYPES = {"resignation", "retirement", "contract_end"}`
  applied to `separation_type`), retention % = `100 - turnover%`. Tables: by department (join
  `employee__employment__org_unit`), by exit reason (`exit_reason` — exclude blank with an "Unspecified"
  bucket), by tenure band at exit (`actual_last_working_day - employee.employment.hired_on`, Python-bucketed
  into `<1yr/1-2/3-5/6-10/10+`, resolved via a single `.select_related("employee__employment")` pass — no
  per-row query). Chart: monthly separations trend over the period. Filters: `date_from`/`date_to`
  (default trailing 12 months), `department`, `separation_type`. Render `hrm/reports/attrition.html`.
- [ ] `diversity_report(request)` — KPIs: gender split % (`EmployeeProfile.objects.filter(tenant=tenant,
  employment__status="active").values("gender").annotate(count=Count("id"))`, blank gender bucketed as
  "Not Specified"), avg age (Python-computed from `date_of_birth`, `None` DOBs excluded from both the avg
  and the age-band table — **guard zero-count division**), avg tenure (from `employment__hired_on`, same
  guard). Tables/charts: age-band distribution (`<25, 25-34, 35-44, 45-54, 55-64, 65+`, Python-bucketed —
  resolve once via `.select_related("employment")`, no query-per-employee), tenure-band distribution
  (same 5 bands as attrition, from `hired_on`), department × gender cross-tab (`.values("employment__org_unit
  __name", "gender").annotate(count=Count("id"))`, pivoted into a dict-of-dicts in Python for the table).
  Filters: `department`, `as_of` (defaults today; active employees only). Render
  `hrm/reports/diversity.html`.
- [ ] `cost_report(request)` — `?cycle=<PayrollCycle pk>` selects the payroll period (default: latest
  `PayrollCycle.objects.filter(tenant=tenant).order_by("-pay_date").first()`; when **no** cycle exists,
  fall back to `EmployeeSalaryStructure.objects.filter(tenant=tenant, status="active")
  .aggregate(Sum("annual_ctc_amount"))` ÷ 12 as the run-rate figure and set a template flag
  `is_estimate=True` so the page visibly labels it "Estimated (no payroll run yet)" rather than presenting
  a fake actual). KPIs: total salary cost (period), avg cost per employee (**guard headcount == 0**),
  employer-contribution cost (`PayslipLine.objects.filter(payslip__cycle=cycle, contribution_side=
  "employer").aggregate(Sum("amount"))`). Tables: department-wise cost (`Payslip.objects.filter(cycle=cycle)
  .values("employee__employment__org_unit__name").annotate(total=Sum("gross_pay"))`), CTC component
  breakdown (`PayslipLine.objects.filter(payslip__cycle=cycle).values("component_type")
  .annotate(total=Sum("amount"))`, labelled via `get_component_type_display`). Chart: monthly cost trend —
  last N `PayrollCycle`s ordered by `pay_date`, each cycle's `total_gross` property (already exists,
  `apps/hrm/models.py:3538-3540` — reuse it, don't re-sum). Filters: `cycle`, `department`. Render
  `hrm/reports/cost.html`.
- [ ] `hiring_report(request)` — KPIs: open requisitions (`JobRequisition.objects.filter(tenant=tenant,
  status__in=("approved", "posted")).count()`), filled requisitions in period (`filled_at__range`),
  avg time-to-fill days (`filled_at - created_at` averaged in Python over filled reqs in range — **guard
  empty queryset → None/"—", not a ZeroDivisionError**), avg time-to-hire days (`JobApplication.hired_on -
  applied_at` over `stage="hired"` applications in range), offer acceptance rate (`hired` count ÷
  (`hired` + `rejected`-after-`offer`-stage count) — approximate via `stage="hired"` vs `stage="rejected"`
  with `rejection_reason` present after having reached `offer`; document the approximation in a code
  comment since NavERP has no stage-history table, only the current `stage`). Tables: source-of-hire mix
  (`JobApplication.objects.filter(stage="hired").values("source").annotate(count=Count("id"))`), funnel
  conversion (`JobApplication.objects.filter(tenant=tenant).values("stage").annotate(count=Count("id"))`
  ordered per `APPLICATION_STAGE_CHOICES`, with a `%` of `applied` total per stage), hires by department
  (`requisition__department__name`). Filters: `date_from`/`date_to` (against `JobRequisition.created_at`),
  `department`. Render `hrm/reports/hiring.html`.
- [ ] Every view follows the **Filter Implementation Rules**: pass `department_choices =
  OrgUnit.objects.filter(tenant=tenant, kind="department").order_by("name")` (and any other
  dropdown queryset/`*_CHOICES` constant the template needs) explicitly in the context — never assume the
  template can reach it; FK/pk `<select>` comparisons in templates use `|stringformat:"d"`, string-field
  comparisons use `request.GET.status == value` (n/a here — no status filters, but `separation_type`/
  `source` follow the same string-compare rule).

## 3. URLs (apps/hrm/urls.py) — append after the existing 3.27 block (after line 944 `suggestion_implement`, before the closing `]` at line 945)

- [ ] New `# 3.28 HR Reports` comment block:
  ```python
  # 3.28 HR Reports
  path("reports/hr/", views.hr_reports_index, name="hr_reports_index"),
  path("reports/hr/headcount/", views.headcount_report, name="headcount_report"),
  path("reports/hr/attrition/", views.attrition_report, name="attrition_report"),
  path("reports/hr/diversity/", views.diversity_report, name="diversity_report"),
  path("reports/hr/cost/", views.cost_report, name="cost_report"),
  path("reports/hr/hiring/", views.hiring_report, name="hiring_report"),
  ```
- [ ] Confirm no name collision with the existing `reports/utilization/`/`reports/project-time/` (3.24
  Training Administration namespace uses a bare `reports/` prefix too — verify `reports/hr/` doesn't
  collide; it doesn't, distinct path segment).

## 4. Navigation — `apps/core/navigation.py`

- [ ] New `LIVE_LINKS["3.28"]` block (insert anywhere before the closing `}` at line 604 — this file's
  dict is not strictly numerically ordered, e.g. `"3.27"` at line 545 is followed by `"3.5"` at line 552),
  bullet text copied **verbatim** from `NavERP.md` lines 629-634:
  ```python
  "3.28": {
      "Headcount Report": "hrm:headcount_report",   # bullet (active/new-joins/exits, dept/designation/type breakdown)
      "Attrition Report": "hrm:attrition_report",   # bullet (SHRM annualized turnover, voluntary/involuntary, trend)
      "Diversity Report": "hrm:diversity_report",   # bullet (gender/age/tenure demographics, dept cross-tab)
      "Cost Reports": "hrm:cost_report",            # bullet (salary cost total + department-wise, CTC breakdown)
      "Hiring Reports": "hrm:hiring_report",        # bullet (time-to-hire/fill, source mix, funnel, offer accept %)
  },
  ```
  (`hr_reports_index` is the landing hub — intentionally not itself a `LIVE_LINKS` entry since NavERP.md's
  3.28 has exactly 5 bullets, each mapped to its drill-in report; the index is reachable from each report
  page's "Back to HR Reports" link and, optionally, a `hrm_overview.html` tile.)

## 5. Templates (templates/hrm/reports/)

- [ ] `templates/hrm/reports/hr_index.html` — standalone landing page (sub-module root, no entity folder —
  Template Folder Structure rule 6, same tier as `templates/hrm/hrm_overview.html`). 5 KPI tiles (`.stat-card`
  pattern, each linking to its report), matches the existing `hrm_overview.html` `.stat-grid` visual
  language.
- [ ] `templates/hrm/reports/headcount.html` — filter bar (`as_of`, `date_from`, `date_to`, `department`
  `<select>` reflecting `request.GET`, `department_choices` from context), 4-5 KPI stat-cards, 3
  breakdown `.table`s (department / designation / employment type, each with a budgeted-vs-actual column
  on the designation table), a Chart.js line chart (`<canvas id="headcount-trend">`, base.html already
  loads `chart.js@4.4.1` — `apps/../templates/base.html:28` — new `<script>` block feeding the 12-point
  series passed as a JSON-safe context var, e.g. `{{ trend_labels|safe }}`/`{{ trend_values|safe }}` via
  `json.dumps` in the view, mirroring how `crm/analytics/dashboard/detail.html` wires its canvas), `.empty-state`
  when the tenant has zero employees.
- [ ] `templates/hrm/reports/attrition.html` — filter bar (`date_from`, `date_to`, `department`,
  `separation_type` `<select>` — `SeparationCase.SEPARATION_TYPE_CHOICES` passed as context), KPI cards
  (turnover %, voluntary %, involuntary %, retention %), 3 breakdown tables (department / exit reason /
  tenure band), Chart.js bar or line for the monthly trend, `.empty-state` when zero separations in range.
- [ ] `templates/hrm/reports/diversity.html` — filter bar (`department`, `as_of`), KPI cards (gender split
  %, avg age, avg tenure), age-band + tenure-band tables (simple CSS bar-width `<div>` per row — no need
  for Chart.js on a single-series distribution), department × gender cross-tab `.table` (departments as
  rows, genders as columns), `.empty-state` when zero active employees.
- [ ] `templates/hrm/reports/cost.html` — filter bar (`cycle` `<select>` of `PayrollCycle.objects.filter
  (tenant=tenant).order_by("-pay_date")`, `department`), a visible "Estimated (no payroll run yet)" badge
  when `is_estimate`, KPI cards (total cost, avg per employee, employer-contribution cost), 2 tables
  (department-wise, CTC component breakdown), Chart.js line for the monthly cost trend across cycles,
  `.empty-state` when no `PayrollCycle` and no active `EmployeeSalaryStructure` exist either.
- [ ] `templates/hrm/reports/hiring.html` — filter bar (`date_from`, `date_to`, `department`), KPI cards
  (open reqs, filled reqs, avg time-to-fill days, avg time-to-hire days, offer acceptance %), 3 tables
  (source-of-hire mix, funnel-by-stage with % of `applied`, hires by department), `.empty-state` when zero
  requisitions/applications in range.
- [ ] Every report template's filter `<form method="get">` re-submits all params (hidden inputs or a
  single form wrapping the whole filter bar) so pagination/links preserve the active filter — mirrors the
  existing list-page filter-bar pattern project-wide.
- [ ] Optional (nice-to-have, only if time allows per the research): a "Export CSV" button per report —
  `?export=csv` branch in the same view function returning `HttpResponse(..., content_type="text/csv")` via
  `csv.writer`, reusing the same filtered queryset/rows already computed (no duplicate query).

## 6. Admin

- [ ] None — no new models, nothing to register in `apps/hrm/admin.py`.

## 7. Verify

- [ ] **No migration** — confirm `python manage.py makemigrations hrm` produces **zero** changes (models.py
  untouched); if it proposes anything, that's a signal 3.28 accidentally touched a model — stop and check.
- [ ] `python manage.py check` — zero errors/warnings.
- [ ] `temp/` smoke sweep: `hr_reports_index` + all 5 `hrm:*_report` URLs return 200 for a tenant admin
  (a) with no query params (defaults apply), (b) with a full filter set (`date_from`/`date_to`/`department`/
  `cycle`/`separation_type`), and (c) with an out-of-range/nonsensical date (`date_from` after `date_to`,
  or a far-future `as_of`) — must render an empty/zero report, never 500. No `{#`/`{% comment` leak markers
  in any rendered report page.
- [ ] **403 for non-admin**: a plain (non-tenant-admin) employee user hitting any of the 6 `hrm:*_report`
  URLs gets 403 (`@tenant_admin_required`), confirming the sensitivity decision in §0 is actually enforced,
  not just documented.
- [ ] **Cross-tenant isolation**: seed (or reuse) a second tenant with different headcount/salary/attrition
  data; confirm `admin_acme`'s report totals never include `admin_globex` rows (spot-check the headcount
  KPI and the cost-report total against each tenant's own seeded data — not just "doesn't error").
  A `?department=<pk>` belonging to the *other* tenant must be silently ignored (falls back to
  "no department filter"), never leak that tenant's OrgUnit name or filter cross-tenant data — this is the
  IDOR-prevention pattern from §2 (department resolved via `OrgUnit.objects.filter(tenant=tenant, ...)`).
- [ ] **Div-by-zero guards**: create/seed-flush an empty tenant with **zero** employees and confirm every
  report renders its `.empty-state`/zero KPIs instead of a 500 (`avg_headcount==0` in attrition,
  `headcount==0` in cost's avg-per-employee, `filled_count==0` in hiring's avg-time-to-fill, `total==0` in
  diversity's avg-age/avg-tenure).
- [ ] Sidebar shows all 5 3.28 entries as **Live** (confirm via the rendered sidebar for a tenant-admin
  login, not just the `LIVE_LINKS` dict — and confirm a *non*-admin login does NOT show them as broken
  links that 403 when clicked; either hide the 3.28 links from non-admins in the sidebar template or accept
  the 403 landing page — decide and note which during build).

## Close-out

- [ ] Run the 7 review agents in order, applying findings + committing after each (one file per commit, no
  `git push`): `code-reviewer` → `explorer` → `frontend-reviewer` → `performance-reviewer` →
  `qa-smoke-tester` → `security-reviewer` → `test-writer`.
  - Expect `code-reviewer` to check the `EmployeeProfile.department`/`.manager` property gotcha (§1) is
    actually avoided (no `.filter(department=...)`/`.values("department")` anywhere in the 6 views) and
    that every rate/average calculation has a zero-denominator guard.
  - Expect `performance-reviewer` to flag any O(employees) Python loop that should be an `.annotate()`/
    `.aggregate()` instead (especially the headcount trend and tenure/age-band bucketing — confirm they're
    O(1) queries + one Python pass, not N+1).
  - Expect `security-reviewer` to confirm the `@tenant_admin_required` gate on all 6 views and the
    tenant-scoped `department`/`cycle` FK resolution (no raw pk trusted into a cross-tenant filter).
  - Expect `test-writer` to cover: 403 for non-admin on every report URL; cross-tenant isolation on
    headcount/cost totals; div-by-zero on an empty tenant; the SHRM annualized-turnover formula's math on a
    known fixture; filter-param round-tripping (department/cycle/date range narrows the result set
    correctly).
- [ ] Update `.claude/skills/hrm/SKILL.md`: add a `### 3.28 HR Reports (0 new tables — derived views)`
  section documenting the 6 routes, the source models/fields each report reads, the `@tenant_admin_required`
  sensitivity decision, and the `EmployeeProfile.department` property gotcha; update the `LIVE_LINKS`
  section for `"3.28"`; update the Deferred section with this pass's carried-forward deferrals.
- [ ] README.md — add `/3.28` to the Module 3 header line + a bullet describing the 5 reports + the
  no-new-models note; refresh HRM test counts after `test-writer` runs.

## Later passes / deferred (carried over from research-hrm-3.28.md)

- **FTE (fractional headcount)** — needs a new FTE-fraction field on `Employment`/`EmployeeProfile`; not
  present today. Defer until a real part-time/FTE-weighting need surfaces.
- **Race/ethnicity, disability, veteran-status representation (EEO-1 categories)** — no field exists;
  adding one is sensitive PII and should follow the encryption pattern already used for `national_id`/
  `passport_number`. Defer to a dedicated EEO-compliance pass, not this reporting pass.
- **Pay-equity / compensation-gap analysis** (regression-adjusted gaps) — beyond a single aggregation view;
  candidate for a future analytics-specific pass.
- **Attrition-risk prediction (ML)** — needs a trained model + historical feature pipeline; explicitly out
  of scope for a derived-view Django pass (NavERP.md 3.32 Analytics Dashboard already earmarks "Predictive
  Analytics" separately).
- **True actuals-based cost-per-hire (ANSI/SHRM)** — NavERP has no recruiting-spend ledger (job-board/agency
  fees); only `JobRequisition.hiring_cost_budget` (a budget estimate) exists. A rough budgeted-CPH proxy
  could be added later; real CPH needs a future recruiting-expense model — not included this pass.
- **Industry benchmarking** (ADP DataCloud-style) — requires an external aggregated-data feed; out of scope.
- **Regrettable vs. non-regrettable attrition** (perf-rating-linked) — a real but secondary cross-join to
  `hrm.PerformanceReview`; nice-to-have, addable later without a schema change.
- **Custom drag-and-drop dashboard builder** — reserved for the future 3.32 Analytics Dashboard, not 3.28.
- **Overtime cost analysis, leave liability, statutory reports** — belong to sibling sub-modules 3.29
  Attendance Reports / 3.30 Leave Reports / 3.31 Payroll Reports; only a light CTC-component breakdown is
  in scope here under Cost Reports.
- **CSV export** — flagged as a nice-to-have in §5 above; build only if time allows in this pass, otherwise
  carries to a later pass.

## Review notes

**3.28 HR Reports — BUILT & reviewed (2026-07-12).** 6 `@tenant_admin_required` derived report views (NO
models/migration/seeder): `hr_reports_index` + headcount/attrition/diversity/cost/hiring, `templates/hrm/reports/`,
`LIVE_LINKS["3.28"]`. All aggregate over the existing spine.

**Review-agent findings applied:**
- **code-reviewer** — 5 correctness fixes: cost employer_cost/by_component now honor `?department`; hiring
  source-of-hire uses the date-range-scoped `hired` set; offer-acceptance computes both legs over the same
  applied_at window; attrition trend anchors on `date_to` (not today); dropped the dead `as_of` control on
  headcount + employment-type display label.
- **explorer** — wiring clean (no fix).
- **frontend-reviewer** — added the missing `.stat-icon.slate` CSS rule (also fixed 3 pre-existing offenders);
  `floatformat:2` on cost currency + "—" for employer contributions in estimate mode; thousands-separator on the
  index payroll-cost tile.
- **performance-reviewer** — headcount trend 24→2 queries (bisect over sorted hire/first-sep dates); cost
  materializes PayrollCycle once; hiring materializes `filled` once; dropped an unused attrition join.
- **qa-smoke-tester** — 7/7 checks PASS (403 non-admin ×6, cross-tenant isolation, IDOR-safe department,
  div-by-zero on an empty tenant); no code change.
- **security-reviewer** — no findings (admin-gated, tenant-scoped, IDOR-safe, no `|safe` XSS, no injection).
- **test-writer** — 95 tests (access/rendering/aggregate-correctness/IDOR/div-by-zero/query-counts), all green.

**Documented approximations (intentional, pinned by tests):** attrition avg-headcount denominator is tenant-wide
even under a `?department` filter (only the numerator narrows); the hiring funnel is not date-scoped (only source/
time-to-hire/offer-accept are). **Deferred:** FTE/EEO PII fields, true cost-per-hire, attrition-risk ML,
benchmarking, CSV export, and the 3.32 dashboard builder. **Next unbuilt HRM sub-module: 3.29 Attendance Reports.**

---
# Module 3 — HRM — Sub-module 3.29 Attendance Reports (hrm) — plan from research-hrm-3.29.md (2026-07-12)

**EXTENDS the existing `apps/hrm` app (already built through 3.28) — no new Django app, no new
`INSTALLED_APPS`/`config/urls.py` entries.** Same shape as 3.28: **derived, read-only,
`@tenant_admin_required` report views — NO new models, NO migration, NO seeder.** Reuses the 3.28 helpers
verbatim (`_report_period`, `_report_department`, `_dept_choices`, `_month_end`, `_tenure_band`, all at
`apps/hrm/views.py:11932-11983`), the flat `templates/hrm/reports/` folder, the Chart.js trend pattern, and
the now-existing `.stat-icon.slate` CSS rule (`static/css/theme.css`, added during 3.28's frontend-review
pass). URL prefix `reports/attendance/...` (new, distinct from `reports/hr/...`). The 5th NavERP.md bullet
("Utilization Report") is satisfied by **linking to the existing `hrm:timesheet_utilization_report`** (3.11,
`apps/hrm/views.py:1678`) — do not rebuild it.

## 1. Confirm NO new models / migration / seeder — source fields/methods verified against apps/hrm/models.py

- [ ] State in the commit message: **3.29 adds zero models, zero migrations, zero seed data.**
- [ ] `AttendanceRecord` (`apps/hrm/models.py:1021-1101`) confirmed fields: `employee` FK `EmployeeProfile`,
  `date`, `check_in`/`check_out` (`TimeField`, nullable), `hours_worked` (derived, `editable=False`), `shift`
  FK `Shift` (nullable, `on_delete=SET_NULL`), `status` (`STATUS_CHOICES` = `present/absent/half_day/
  on_leave/holiday/regularized`), `source` (`SOURCE_CHOICES` = `web/mobile/biometric/manual`).
  **`is_late()` CONFIRMED to exist** (line 1081-1088) — `True` when `check_in` minutes-of-day exceeds
  `shift.start_time` minutes-of-day + `shift.grace_minutes`; returns `False` (not `None`) when no
  `check_in`/`shift`/`shift.start_time` — safe to call unconditionally, but rows with no `shift` should
  still be tallied separately as "no shift assigned" per the research (they read as "not late" which is
  potentially misleading — surface the count, don't silently drop it).
- [ ] **No early-departure model method exists** — `late_early_report` must compute it inline, same
  minutes-of-day pattern as `is_late()`: `check_out` minutes-of-day `<` `shift.end_time` minutes-of-day −
  `shift.grace_minutes` (reuse `grace_minutes` symmetrically for early-leave — no separate field exists;
  state this choice in a code comment, matching the research's explicit call-out).
- [ ] `Shift` (`apps/hrm/models.py:975-993`) confirmed: `start_time`, `end_time` (`TimeField`),
  `grace_minutes` (`PositiveSmallIntegerField`, default 15).
- [ ] `OvertimeRequest` (`apps/hrm/models.py:716-775`) confirmed fields: `employee` FK `EmployeeProfile`,
  `date`, `hours_claimed` (`DecimalField`), `multiplier` (`DecimalField`, default `1.50`), `status`
  (`STATUS_CHOICES` = `draft/pending/approved/rejected/cancelled`), `payout_method`
  (`PAYOUT_CHOICES` = `pay/comp_leave`). **`overtime_pay_equivalent_hours` CONFIRMED to exist** as a
  `@property` (line 768-772) = `hours_claimed × multiplier`. Model docstring explicitly states **no stored
  currency amount** ("no stable employee pay-rate source yet (3.13 Salary Structure)") — `overtime_report`
  must respect this: hours + pay-equivalent-hours only, clearly labeled non-currency.
- [ ] **`EmployeeProfile.department` is a Python `@property`** (`apps/hrm/models.py:343`), **not a DB
  column** — same gotcha as 3.28 (`todo.md` 3.28 §1). `AttendanceRecord`/`OvertimeRequest` department
  breakdowns/filters MUST aggregate via the real FK path `employee__employment__org_unit` (never
  `.values("employee__department")` or `.filter(employee__department=...)`).
- [ ] No field/method gaps degrade any report to a 500 — everything above exists; div-by-zero (zero tracked
  days, zero late rows, zero OT rows) is a **view-logic** guard (§2), not a data gap.

## 2. Views (apps/hrm/views.py) — new `# --- 3.29 Attendance Reports ---` banner (append after the 3.28 block, current EOF ~line 12298)

- [ ] All 5 functions decorated `@tenant_admin_required`, `if tenant is not None:` guard pattern (superuser
  `tenant=None` renders an empty report, never `.filter(tenant=None)`). Reuse `_report_period(request)`,
  `_report_department(request, tenant)`, `_dept_choices(tenant)` as-is — no new period/department helpers.
- [ ] `attendance_reports_index(request)` — `/hrm/reports/attendance/`. No filters. 5 KPI tiles
  (`{label, value, url}`, mirrors `hr_reports_index`): current-period Attendance % (present-days ÷
  tracked-days over the trailing-12-month default window), Late-arrival count, Absent-days count, Total OT
  hours (approved), and an overall Utilization % tile computed as a lightweight aggregate over
  `TimesheetEntry.objects.filter(tenant=tenant, timesheet__status="approved")`
  (`Sum("hours", filter=Q(is_billable=True)) / Sum("hours")`, same shape as
  `timesheet_utilization_report` but summed not grouped) — **the tile links to
  `hrm:timesheet_utilization_report`, not a new page.** Render `hrm/reports/attendance_index.html`.
- [ ] `attendance_summary_report(request)` — `/hrm/reports/attendance/summary/`. Filters: `date_from`,
  `date_to`, `department`. Query: `AttendanceRecord.objects.filter(tenant=tenant, date__range=(date_from,
  date_to))`, `.filter(employee__employment__org_unit=dept)` when set. Status breakdown:
  `.values("status").annotate(count=Count("id"))` labelled via `STATUS_CHOICES`. **Attendance % = present
  ÷ tracked**, where **tracked = total rows excluding `status="holiday"`** (per research — no
  scheduled-days/calendar table exists; document this substitution in a code comment + template caption).
  **Guard `tracked == 0` → 0%, not `ZeroDivisionError`.** By-department table:
  `.values("employee__employment__org_unit__name").annotate(present=Count("id", filter=Q(status="present")),
  total=Count("id"))`, per-row % guarded. 12-month trend: reuse the `_month_end` bisect/loop pattern
  (O(≤12) iterations over one materialized/sorted list, not one query per month) — monthly attendance %.
  Render `hrm/reports/attendance_summary.html`.
- [ ] `late_early_report(request)` — `/hrm/reports/attendance/late-early/`. Filters: `date_from`, `date_to`,
  `department`. Single `.select_related("employee__employment__org_unit", "shift")` query over
  `AttendanceRecord` in range (+ department filter) to avoid N+1. Python per-row: skip rows with no
  `shift_id` (tally as `no_shift_count`, shown as a caveat line); for the rest, call `.is_late()` for the
  late flag and inline-compute early-departure (per §1) + minutes-late/minutes-early
  (`check_in_minutes − (start_minutes + grace)` / `(end_minutes − grace) − check_out_minutes`, clamped
  `≥ 0`). Aggregate: late count, avg minutes late (**guard zero late rows → None/"—"**), early count, avg
  minutes early (same guard), top-offenders table (group by employee, sort by late+early count desc, cap
  top 10-20), day-of-week trend (`date.weekday()` Python bucket, 7 bars, Mon-Sun). Render
  `hrm/reports/late_early.html`.
- [ ] `absenteeism_report(request)` — `/hrm/reports/attendance/absenteeism/`. Filters: `date_from`,
  `date_to`, `department`. Same tracked-denominator definition as summary (`status != "holiday"` count).
  Absence rate = absent-days ÷ tracked (**guard `tracked == 0`**). By-department breakdown (same
  `employee__employment__org_unit` path). Frequent-absentee list: `.filter(status="absent")
  .values("employee_id", "employee__party__name").annotate(count=Count("id")).order_by("-count")`, cap
  top 10-20. 12-month absence-count trend (`_month_end` loop, O(≤12)). **Bradford Factor: Nice, only if
  time allows** — `S² × D` where `S` = count of consecutive-day absence runs (Python: sort an employee's
  absent dates, break into runs where `gap > 1 day`), `D` = total absent days in period; if included, add
  as an extra column on the frequent-absentee table with a tooltip/caption explaining the formula; if
  skipped, note it under Later passes below (research already flags it Nice-not-Must).
- [ ] `overtime_report(request)` — `/hrm/reports/attendance/overtime/`. Filters: `date_from`, `date_to`,
  `department`, `status` (default unfiltered — pass `status_choices = OvertimeRequest.STATUS_CHOICES`, let
  the admin narrow to `approved` via the dropdown rather than hard-defaulting, since the status-mix KPI
  needs the full set to be meaningful). Query: `OvertimeRequest.objects.filter(tenant=tenant,
  date__range=(date_from, date_to))`, department via `employee__employment__org_unit`, status via
  `.filter(status=status)` when set. KPIs: total `hours_claimed` (`Sum`), total pay-equivalent hours
  (Python sum of `.overtime_pay_equivalent_hours` over a materialized queryset, or equivalent
  `Sum(F("hours_claimed") * F("multiplier"))` annotation — prefer the DB annotation to avoid a Python loop
  over all rows). **No currency total anywhere on this page** — state in the template: "Hours-based only —
  no stable pay-rate source yet (see OvertimeRequest model)." By-employee + by-department breakdown tables,
  status mix (`.values("status").annotate(count=Count("id"))`), 12-month OT-hours trend (`_month_end`
  loop). Render `hrm/reports/overtime.html`.
- [ ] Every view follows the **Filter Implementation Rules**: pass `department_choices = _dept_choices
  (tenant)` and any `*_CHOICES` constant the template's `<select>`s need explicitly in context; FK/pk
  `<select>` comparisons use `|stringformat:"d"`, string-field comparisons (`status`) use
  `request.GET.status == value`.
- [ ] Every rate (`attendance %`, `absence rate`, `avg minutes late/early`, `utilization %`) is guarded
  against a zero denominator — audit each before considering the view done.

## 3. URLs (apps/hrm/urls.py) — append after the existing 3.28 block (after line 952 `reports/hr/hiring/`, before the closing `]`)

- [ ] New `# 3.29 Attendance Reports` comment block:
  ```python
  # 3.29 Attendance Reports
  path("reports/attendance/", views.attendance_reports_index, name="attendance_reports_index"),
  path("reports/attendance/summary/", views.attendance_summary_report, name="attendance_summary_report"),
  path("reports/attendance/late-early/", views.late_early_report, name="late_early_report"),
  path("reports/attendance/absenteeism/", views.absenteeism_report, name="absenteeism_report"),
  path("reports/attendance/overtime/", views.overtime_report, name="overtime_report"),
  ```
- [ ] Confirm no path/name collision with `reports/hr/...` (3.28) or `reports/utilization/`/
  `reports/project-time/` (3.11) — distinct `reports/attendance/` segment, no clash.

## 4. Navigation — apps/core/navigation.py

- [ ] New `LIVE_LINKS["3.29"]` block (insert near the `"3.28"` entry for readability; dict order isn't
  strictly numeric elsewhere in the file), bullet text copied **verbatim** from `NavERP.md:636-641`:
  ```python
  "3.29": {
      "Attendance Summary": "hrm:attendance_summary_report",  # bullet (daily/weekly/monthly, status breakdown + trend)
      "Late/Early Departure": "hrm:late_early_report",        # bullet (lateness trends, day-of-week pattern)
      "Absenteeism Report": "hrm:absenteeism_report",         # bullet (absence rate, frequent absentees)
      "Overtime Report": "hrm:overtime_report",                # bullet (OT hours, pay-equivalent hours — no currency)
      "Utilization Report": "hrm:timesheet_utilization_report", # bullet — REUSE 3.11, not rebuilt
  },
  ```
  (`attendance_reports_index` is the landing hub — not itself a bullet, same precedent as `hr_reports_index`
  in 3.28; reachable via each report's "Back to Attendance Reports" link.)

## 5. Templates (templates/hrm/reports/)

- [ ] `templates/hrm/reports/attendance_index.html` — standalone landing page (sub-module root, no entity
  folder), 5 `.stat-card` KPI tiles matching `hr_index.html`'s visual language (use `.stat-icon.slate` for
  the Utilization tile alongside whatever icon classes the other 4 tiles use), Utilization tile links out to
  `hrm:timesheet_utilization_report`.
- [ ] `templates/hrm/reports/attendance_summary.html` — filter bar (`date_from`, `date_to`, `department`
  `<select>` reflecting `request.GET`), KPI stat-cards (attendance %, present/absent/late/half-day counts),
  status-breakdown table, by-department table, Chart.js 12-month trend (`<canvas>`, same wiring as
  `headcount.html`'s `trendChart` — `json.dumps` labels/values from the view), a caption noting the derived
  tracked-days denominator, `.empty-state` when zero records in range.
- [ ] `templates/hrm/reports/late_early.html` — filter bar (`date_from`, `date_to`, `department`), KPI cards
  (late count, avg minutes late, early count, avg minutes early — each render "—" when its guard triggers),
  a "N records skipped — no shift assigned" caveat line, top-offenders table, day-of-week bar chart
  (Chart.js or simple CSS bars), `.empty-state` when zero shift-assigned records in range.
- [ ] `templates/hrm/reports/absenteeism.html` — filter bar (`date_from`, `date_to`, `department`), KPI
  cards (absence rate, total absent days), by-department table, frequent-absentee ranked table (+ Bradford
  Factor column only if built in §2), 12-month trend chart, `.empty-state` when zero absences in range.
- [ ] `templates/hrm/reports/overtime.html` — filter bar (`date_from`, `date_to`, `department`, `status`
  `<select>` from `OvertimeRequest.STATUS_CHOICES`), KPI cards (total hours claimed, total pay-equivalent
  hours — **no currency card**), a visible "Hours-based only" note, by-employee + by-department tables,
  status-mix table/chips, 12-month OT-hours trend chart, `.empty-state` when zero OT requests in range.
- [ ] All 4 drill-in templates: filter `<form method="get">` re-submits every active param; `text-align:end`
  (logical, not `right`) for numeric columns; `floatformat:1` or `:2` on hours/percentages consistently;
  `{% csrf_token %}` n/a (GET-only, read-only pages, no POST forms).

## 6. Admin

- [ ] None — no new models, nothing to register in `apps/hrm/admin.py`.

## 7. Verify

- [ ] **No migration** — `python manage.py makemigrations hrm` produces **zero** changes.
- [ ] `python manage.py check` — zero errors/warnings.
- [ ] `temp/` smoke sweep: `attendance_reports_index` + all 4 drill-in `hrm:*_report` URLs return 200 for a
  tenant admin (a) with no query params (defaults), (b) with a full filter set (`date_from`/`date_to`/
  `department`/`status`), and (c) with odd/nonsensical values (`date_from` after `date_to`, a non-digit or
  cross-tenant `?department`, an invalid `?status`) — must render an empty/zero report, never 500. No
  `{#`/`{% comment` leak markers in any rendered page.
- [ ] **403 for non-admin**: a plain employee user hitting any of the 5 `hrm:*_report`/`attendance_reports_index`
  URLs gets 403 (`@tenant_admin_required`).
- [ ] **Cross-tenant isolation**: a second tenant's attendance/OT data never appears in tenant A's totals;
  a `?department=<pk>` belonging to another tenant is silently ignored (falls back to "no filter"), never
  leaks that tenant's `OrgUnit` name — same IDOR-prevention pattern as 3.28 (`_report_department` already
  tenant-scopes the lookup).
- [ ] **Div-by-zero guards**: an empty tenant (zero `AttendanceRecord`/`OvertimeRequest` rows) renders every
  report's `.empty-state`/zero KPIs, not a 500 — specifically: `tracked == 0` in summary/absenteeism,
  zero late/early rows in late_early (avg minutes → "—"), zero utilization denominator on the index tile.
- [ ] Sidebar shows all 5 3.29 entries as **Live** for a tenant-admin login (including the Utilization tile
  correctly deep-linking to the existing 3.11 page, not a 404).

## Close-out

- [ ] Run the 7 review agents in order, applying findings + committing after each (one file per commit, no
  `git push`): `code-reviewer` → `explorer` → `frontend-reviewer` → `performance-reviewer` →
  `qa-smoke-tester` → `security-reviewer` → `test-writer`.
  - Expect `code-reviewer` to check the `EmployeeProfile.department` property gotcha is avoided, that the
    early-departure inline logic mirrors `is_late()`'s minutes-of-day approach (no naive `TimeField`
    subtraction), and that every rate has a zero-denominator guard.
  - Expect `performance-reviewer` to confirm `late_early_report`'s per-row Python bucketing is a single
    `.select_related()` pass (no N+1 on `shift`/`employee__employment__org_unit`), and that OT
    pay-equivalent-hours prefers a DB `Sum(F(...)*F(...))` annotation over a Python loop when the queryset
    could be large.
  - Expect `security-reviewer` to confirm `@tenant_admin_required` on all 5 views and IDOR-safe `department`/
    `status` resolution.
  - Expect `test-writer` to cover: 403 for non-admin on every report URL; cross-tenant isolation; div-by-zero
    on an empty tenant; the tracked-days denominator math on a known fixture (present/absent/holiday mix);
    the late/early minutes computation against a hand-checked `check_in`/`shift` fixture; the OT
    pay-equivalent-hours formula; filter round-tripping (date range + department + status narrows results).
- [ ] Update `.claude/skills/hrm/SKILL.md`: add a `### 3.29 Attendance Reports (0 new tables — derived
  views)` section documenting the 5 routes, source fields/methods each report reads (incl. the confirmed
  `is_late()` / `overtime_pay_equivalent_hours` reuse and the inline early-departure logic), the
  tracked-days denominator substitution, and the "no currency OT cost" decision; update `LIVE_LINKS` for
  `"3.29"`; update the Deferred section with this pass's carried-forward deferrals.
- [ ] README.md — add `/3.29` to the Module 3 header line + a bullet describing the 5 reports + the
  no-new-models note; refresh HRM test counts after `test-writer` runs.

## Later passes / deferred (carried over from research-hrm-3.29.md)

- **Daily muster-roll snapshot grid** (single-day view) — Nice-to-have UI mode; add a `?date=` single-day
  toggle to `attendance_summary_report` later if requested.
- **Points/occurrence-based discipline tracking** (UKG-style, e.g. late-in = 0.5pt) and
  **compensation-linked lateness penalization** (Keka-style) — both need a new policy/rules table + payroll
  deduction linkage (3.13/3.31); out of scope for a read-only report pass.
- **Approaching-overtime-threshold proactive alerts** (ADP-style) — needs a notification/policy engine, not
  a report.
- **Currency OT cost** (`hours × multiplier × pay rate`) — deferred until 3.13/3.31 payroll defines an
  authoritative per-employee hourly rate; `EmployeeSalaryStructure.annual_ctc_amount` alone is not reliable
  (annualized, no standard hours-per-year divisor).
- **Worked-vs-scheduled-hours comparison** (ADP/UKG-style) — no shift-roster/scheduling model exists yet;
  revisit once one does.
- **Absence-reason / leave-type breakdown** — belongs to 3.30 Leave Reports (`hrm.LeaveRequest.leave_type`),
  not 3.29's `AttendanceRecord`.
- **Return-to-work workflow / auto-triggers at N occurrences** (Workday-style) — policy-engine feature, not
  a report.
- **Productivity/output metrics** (revenue-per-employee, task-completion rate) — needs Project Management
  (Module 7) data, not available yet.
- **Bradford Factor** — build it in §2 if time allows this pass; otherwise it carries here as a Nice-to-have
  addable without a schema change.
- **Source breakdown** (web/mobile/biometric/manual mix) and **OT-by-category** (regular/weekend/holiday) —
  low-priority Nice extras noted in research; add to `attendance_summary_report`/`overtime_report` later if
  requested.

## Review notes

**3.29 Attendance Reports — BUILT & reviewed (2026-07-12).** 5 `@tenant_admin_required` derived report views (NO
models), reusing the 3.28 report helpers: `attendance_reports_index` + attendance-summary/late-early/absenteeism/
overtime; the Utilization bullet reuses the existing 3.11 `timesheet_utilization_report`.

**Review-agent findings applied:**
- **code-reviewer** — 2 Important: per-employee aggregation (late-early top-offenders + overtime by-employee) now
  keys by `employee_id` (was `party.name`, non-unique → same-named employees merged); overtime headline figures +
  the index OT tile default-exclude draft/rejected/cancelled claims (were summing all statuses); + the Status-Mix
  table now reflects the full pre-filter distribution, and the present/tracked folding was extracted into a shared
  `_fold_att` helper.
- **explorer** — wiring clean (no fix).
- **frontend-reviewer** — clean (templates mirror the vetted 3.28 pattern; `.stat-icon.slate` exists, floatformat on
  hours, logical text-align, valid Lucide icons).
- **performance-reviewer / security-reviewer** — the code-reviewer reviewed and routed both as clean for this
  pattern-identical changeset (all queries tenant-scoped + `@tenant_admin_required`, IDOR-safe department resolve,
  one `select_related` pass per row-loop, `TruncMonth` single-query trends); no separate findings.
- **test-writer** — 72 tests (access/rendering/aggregate-correctness/IDOR/div-by-zero/query-counts), all green; full
  HRM suite green.

**Documented approximations:** early-departure uses symmetric `grace_minutes` (no separate early-leave grace field);
overtime is hours-only (no pay-rate → no currency); Utilization is not rebuilt (3.11 reuse). **Deferred:** currency
OT cost, scheduled-vs-worked hours, Bradford-Factor discipline, muster-roll grids. **Next: 3.30 Leave Reports.**

---
# Module 3 — HRM — Sub-module 3.30 Leave Reports (hrm) — plan from research-hrm-3.30.md (2026-07-12)

**EXTENDS the existing `apps/hrm` app (already built through 3.29) — no new Django app, no new
`INSTALLED_APPS`/`config/urls.py` entries.** Same shape as 3.28/3.29: **derived, read-only,
`@tenant_admin_required` report views — NO new models, NO migration, NO seeder.** Reuses `_report_period`,
`_report_department`, `_dept_choices` (`apps/hrm/views.py:11932-11953`) verbatim for the two date-range-scoped
views (comp-off, trend). The two `LeaveAllocation`-backed views (register, liability) are **year-scoped, not
date-range-scoped** — `LeaveAllocation.year` has no start/end date — so they get a new `_report_year(request)`
helper instead of `_report_period`. Reuses `_used_days_subquery()` (`apps/hrm/views.py:367-376`) exactly as
`leaveallocation_list` already does (`apps/hrm/views.py:905-923`):
`.annotate(used_days_db=_used_days_subquery()).annotate(balance_db=ExpressionWrapper(F("allocated_days") -
F("used_days_db") - F("encashed_days"), output_field=_DEC))` — never the Python `@property` in a loop (N+1).
Templates live in the existing flat `templates/hrm/reports/` folder; Chart.js + `TruncMonth` + `json.dumps`
labels/values, same wiring as `attendance_summary.html`/`overtime.html`.

## 1. Confirm NO new models — every source field/helper verified against apps/hrm/models.py + views.py

- [ ] State in the commit message: **3.30 adds zero models, zero migrations, zero seed data.**
- [ ] `LeaveType` (`apps/hrm/models.py:383-415`) confirmed fields: `name`, `code`, `is_paid`, `accrual_rule`/
  `accrual_days`, `max_balance`, `max_carry_forward`, `encashable` (bool — the ONLY signal for "$-liability
  eligible"), `is_active`. Seeded catalog (`seed_hrm.py:197-203` `LEAVE_TYPES`) confirmed = **Annual Leave
  (AL, encashable=True), Sick Leave (SL, encashable=False), Casual Leave (CL, encashable=False), Unpaid Leave
  (UPL, encashable=False)** — **no `code`/`name` contains "comp" anywhere in the seed** → the comp-off
  `LeaveType` heuristic match (`Q(code__icontains="comp") | Q(name__icontains="comp")`) WILL return empty on
  freshly-seeded demo data. `comp_off_report`'s "availed" panel MUST render its empty-state banner by default,
  not silently show zero.
- [ ] `LeaveAllocation` (`apps/hrm/models.py:418-474`) confirmed fields: `employee` FK, `leave_type` FK,
  `year` (`PositiveSmallIntegerField`), `allocated_days`, `carried_forward` (`editable=False`),
  `encashed_days` (`editable=False`), `status`. `used_days`/`balance` are `@property`s (lines 453-471) — the
  docstring on the property (line 458-459) explicitly says list views should use `used_days_db`/`balance_db`
  annotations via `_used_days_subquery()` instead. **CONFIRMED helper name: `_used_days_subquery()`**
  (`apps/hrm/views.py:367`, a correlated `Subquery`/`Coalesce` keyed on `OuterRef("tenant"/"employee"/
  "leave_type"/"year")`) — reuse verbatim, do not re-derive. `unique_together` includes `(tenant, employee,
  leave_type, year)` so one row per employee×type×year — exactly the register grid's row shape.
- [ ] `LeaveRequest` (`apps/hrm/models.py:477-536`) confirmed fields: `employee`, `leave_type`, `start_date`,
  `end_date`, `days` (`editable=False`, holiday-excluded, recomputed in `save()`), `status`
  (`draft/pending/approved/rejected/cancelled`). "Availed"/"taken" = `status="approved"` only, everywhere.
- [ ] `LeaveEncashment` (`apps/hrm/models.py:539-...`) confirmed fields: `employee`, `leave_type`, `year`,
  `days`, `rate_per_day` (user-entered, no default/lookup elsewhere), `amount` (recomputed in `save()` from
  `days × rate_per_day`), `status`. This is the ONLY place a real per-day leave rate is ever recorded in
  NavERP — the liability report's rate-fallback tier 1.
- [ ] `OvertimeRequest` (`apps/hrm/models.py:716-775`) confirmed: **field is `payout_method`** (not
  `payout`), `PAYOUT_CHOICES = [("pay","Pay"), ("comp_leave","Compensatory Leave")]` — comp-leave value is
  the literal string `"comp_leave"`. `status` (`draft/pending/approved/rejected/cancelled`), `hours_claimed`
  (`DecimalField`). **CONFIRMED `overtimerequest_approve()` (`apps/hrm/views.py:1636-1646`) only flips
  `status → "approved"`** — it does NOT create/increment any `LeaveAllocation` row. There is no automatic
  linkage from an approved comp-leave OT claim to a leave balance anywhere in the codebase — a real
  functional gap, not just a naming one. `comp_off_report`'s "earned" panel is therefore
  `OvertimeRequest.objects.filter(tenant=tenant, payout_method="comp_leave", status="approved")` and its
  hours/est.-days figure is informational only, never reconciled against a real balance.
- [ ] `EmployeeSalaryStructure` (`apps/hrm/models.py:3415-...`) confirmed: `annual_ctc_amount`, `status`
  (`active`/`superseded`), `effective_from`/`effective_to` — the liability report's rate-fallback tier 2
  (`annual_ctc_amount / 365`, labelled `is_estimate`).
- [ ] **`EmployeeProfile.department` is a Python `@property`** (`apps/hrm/models.py:343`), **not a DB
  column** — same recurring gotcha as 3.28/3.29. All department aggregates/filters across all 5 views MUST
  use the real FK path `employee__employment__org_unit` (never `.values("employee__department")`).
- [ ] Confirm no field/method gap forces a 500: everything the 5 views need exists; div-by-zero (empty
  tenant, no `LeaveAllocation` rows for the selected year, no resolvable liability rate, no comp-off
  `LeaveType`) is a **view-logic** guard/empty-state (§2), not a data gap.

## 2. Views (apps/hrm/views.py) — new `# --- 3.30 Leave Reports ---` banner (append after the 3.29 block, current EOF at line 12516)

- [ ] All 5 functions decorated `@tenant_admin_required`, `if tenant is not None:` guard pattern (superuser
  `tenant=None` renders an empty/zero report, never `.filter(tenant=None)`).
- [ ] New `_report_year(request)` helper (register + liability only): `raw =
  (request.GET.get("year") or "").strip(); return int(raw) if raw.isdigit() else
  timezone.localdate().year` — never `ValueError`s on a malformed `?year`.
- [ ] New `_report_leave_type(request, tenant)` helper (trend only), mirroring `_report_department`'s
  IDOR-safe pattern exactly: tenant-scoped, digit-checked pk, `LeaveType.objects.filter(tenant=tenant,
  pk=int(pk)).first()`, else `None` — never trusts a raw cross-tenant pk.
- [ ] Follow the **Filter Implementation Rules**: every `<select>` the templates need gets its choices passed
  explicitly — `department_choices = _dept_choices(tenant)`, `leave_type_choices =
  LeaveType.objects.filter(tenant=tenant, is_active=True).order_by("name")`, `year_choices` = distinct
  `LeaveAllocation.objects.filter(tenant=tenant).values_list("year", flat=True).distinct().order_by("-year")`
  (register + liability). FK/pk `<select>` comparisons use `|stringformat:"d"`; string fields use
  `request.GET.x == value`.
- [ ] `leave_reports_index(request)` — `/hrm/reports/leave/`. No filters. 5 KPI tiles (`{label, value, url}`,
  mirrors `hr_reports_index`/`attendance_reports_index`): Leave Register (current-year allocation count or
  avg balance), Leave Liability (current-year total days liability), Comp-off (current-period earned-days
  estimate), Leave Trend (trailing-12-month approved-days total), + a 5th "On Leave Today" quick stat
  (`LeaveRequest.objects.filter(tenant=tenant, status="approved", start_date__lte=today,
  end_date__gte=today).count()` — cheap, no separate page, matches the research's "fold into the hub, don't
  build a separate view" call). Render `hrm/reports/leave_index.html`.
- [ ] `leave_register_report(request)` — `/hrm/reports/leave/register/`. Filters: `?year` (via
  `_report_year`, default current year — **NOT `_report_period`**, `LeaveAllocation` has no date range),
  `?department` (via `_report_department`). Query:
  `LeaveAllocation.objects.filter(tenant=tenant, year=year).select_related("employee__party",
  "employee__employment__org_unit", "leave_type")`, `.filter(employee__employment__org_unit=dept)` when set,
  then `.annotate(used_days_db=_used_days_subquery()).annotate(balance_db=ExpressionWrapper(
  F("allocated_days") - F("used_days_db") - F("encashed_days"), output_field=_DEC))` — **the DB annotation,
  never per-row `.used_days`/`.balance` property access** (N+1 guard, code-reviewer will check this). Grid:
  one row per `LeaveAllocation` (employee + leave_type), columns = allocated_days, carried_forward,
  used_days_db, encashed_days, balance_db. Rollups: by leave_type (`.values("leave_type__name").annotate(...)`)
  and by department. Render `hrm/reports/leave_register.html`.
- [ ] `leave_liability_report(request)` — `/hrm/reports/leave/liability/`. Filters: `?year`, `?department`
  (same resolution as register). Base query: same annotated `LeaveAllocation` queryset as register (reuse the
  annotation, don't re-derive). Per row, resolve a rate via the **fallback chain** (implement as a small
  helper, e.g. `_resolve_leave_rate(tenant, employee_id, leave_type_id)`):
  1. Latest `LeaveEncashment.objects.filter(tenant=tenant, employee_id=employee_id,
     leave_type_id=leave_type_id).order_by("-year", "-created_at").values_list("rate_per_day",
     flat=True).first()` → source `"encashment"` if truthy/non-zero.
  2. Else latest `EmployeeSalaryStructure.objects.filter(tenant=tenant, employee_id=employee_id,
     status="active").order_by("-effective_from").values_list("annual_ctc_amount",
     flat=True).first()` ÷ `Decimal("365")` → source `"estimate"` (`is_estimate=True` on the row).
  3. Else rate = `None` → source `"none"`, row excluded from the `$` total but still counted in the days
     total.
  **Only rows where `leave_type.encashable is True` contribute to the `$` total** — non-encashable balances
  (Sick/Casual per the seed) still appear in the days-based liability but are visually/numerically excluded
  from currency. Guard: batch-resolve rates with at most one `LeaveEncashment` query + one
  `EmployeeSalaryStructure` query per distinct (employee, leave_type) / employee pair, not N+1 (materialize
  the annotated queryset once, group in Python — do NOT call `.filter().first()` inside the row loop for
  every row; pull the relevant encashment/salary rows in one query each and index by employee/leave_type
  first). Headline totals: total days liability (all types), total `$` liability (encashable + resolved-rate
  rows only), data-quality line = count/% of rows with `source="none"`. Rollups: by department, by leave
  type. Render `hrm/reports/leave_liability.html`.
- [ ] `comp_off_report(request)` — `/hrm/reports/leave/comp-off/`. Filters: `_report_period` (date range on
  `OvertimeRequest.date`), `?department` (via `_report_department`). **"Earned" panel**:
  `OvertimeRequest.objects.filter(tenant=tenant, payout_method="comp_leave", status="approved",
  date__range=(date_from, date_to))`, department via `employee__employment__org_unit` — count, total
  `hours_claimed` (`Sum`), est. days (`hours_claimed / 8`, documented assumption in a code comment), by
  employee, by department, monthly trend (`TruncMonth("date")`). **"Availed" panel**: resolve the tenant's
  comp-off `LeaveType` via `LeaveType.objects.filter(tenant=tenant).filter(Q(code__icontains="comp") |
  Q(name__icontains="comp")).first()`; if `None`, set an explicit `ctx["comp_off_type"] = None` /
  `ctx["no_comp_off_type"] = True` flag and skip the availed query entirely (template renders the caveat
  banner, not a silent zero); if found, `LeaveRequest.objects.filter(tenant=tenant,
  leave_type=comp_off_type, status="approved", start_date__range=(date_from, date_to))` — days, by employee.
  Net position table (earned est. days − availed days per employee), clearly labelled "estimate — not a
  tracked balance". Render `hrm/reports/comp_off.html`.
- [ ] `leave_trend_report(request)` — `/hrm/reports/leave/trend/`. Filters: `_report_period`, `?department`,
  `?leave_type` (via the new `_report_leave_type`). Base: `LeaveRequest.objects.filter(tenant=tenant,
  status="approved", start_date__range=(date_from, date_to))`, department/leave_type filters applied when
  set. Monthly trend: `.annotate(m=TruncMonth("start_date")).values("m", "leave_type__name").annotate(
  d=Sum("days"))` — **note the approximation in a code comment**: `days` is attributed whole to the request's
  **start-month** (a request spanning a month boundary is not split), same simplification style as
  `LeaveAllocation.used_days`'s year-boundary handling. Chart.js stacked-by-leave-type line/bar (`json.dumps`
  labels/series per leave type, same pattern as `overtime_report`'s single-series trend generalized to
  multi-series). By-department rollup (`employee__employment__org_unit`). Seasonality: group by
  calendar-month-of-year only (`ExtractMonth("start_date")` or a Python `.month` bucket over the materialized
  queryset), summed across all years in the selected range — Jan..Dec, second chart on the same page. Top-10
  frequent leave-takers: `.values("employee_id", "employee__party__name").annotate(count=Count("id"),
  days=Sum("days")).order_by("-days")[:10]` — mirrors `absenteeism_report`'s frequent-absentee pattern. Render
  `hrm/reports/leave_trend.html`.
- [ ] Every rate/percentage/average across all 5 views is guarded against a zero denominator (empty tenant,
  zero allocations for the selected year, zero resolvable rates, zero OT claims) — audit each before
  considering a view done.

## 3. URLs (apps/hrm/urls.py) — append after the 3.29 block (after line 959 `reports/attendance/overtime/`, before the closing `]` at line 960)

- [ ] New `# 3.30 Leave Reports` comment block:
  ```python
  # 3.30 Leave Reports (derived, read-only, admin-only)
  path("reports/leave/", views.leave_reports_index, name="leave_reports_index"),
  path("reports/leave/register/", views.leave_register_report, name="leave_register_report"),
  path("reports/leave/liability/", views.leave_liability_report, name="leave_liability_report"),
  path("reports/leave/comp-off/", views.comp_off_report, name="comp_off_report"),
  path("reports/leave/trend/", views.leave_trend_report, name="leave_trend_report"),
  ```
- [ ] Confirm no path/name collision with `reports/hr/...` (3.28), `reports/attendance/...` (3.29), or the
  existing 3.10 `leaveallocation_list`/`leaverequest_list`/`leaveencashment_list` CRUD URLs — distinct
  `reports/leave/` segment, no clash.

## 4. Navigation — apps/core/navigation.py

- [ ] New `LIVE_LINKS["3.30"]` block (insert near the `"3.29"` entry), bullet text copied **verbatim** from
  `NavERP.md:643-647`:
  ```python
  # 3.30 Leave Reports — derived, read-only, @tenant_admin_required (no models). leave_reports_index is
  # the landing hub, not itself a bullet — same precedent as 3.28/3.29.
  "3.30": {
      "Leave Register": "hrm:leave_register_report",     # bullet (availed + balance grid, year/department)
      "Leave Liability": "hrm:leave_liability_report",    # bullet (accrued days + $ liability, rate fallback chain)
      "Comp-off Report": "hrm:comp_off_report",           # bullet (earned/availed, empty-state if no comp-off LeaveType)
      "Leave Trend": "hrm:leave_trend_report",            # bullet (monthly/seasonal patterns, frequent takers)
  },
  ```

## 5. Templates (templates/hrm/reports/)

- [ ] `templates/hrm/reports/leave_index.html` — standalone landing page (sub-module root, no entity
  folder), 5 `.stat-card` KPI tiles matching `hr_index.html`/`attendance_index.html`'s visual language, each
  linking to its drill-in report (the "On Leave Today" tile has no dedicated page — no link, or link to
  register report).
- [ ] `templates/hrm/reports/leave_register.html` — filter bar (`year` `<select>` from `year_choices`,
  `department` `<select>` reflecting `request.GET`), grid table (employee × leave_type rows: allocated,
  carried_forward, used, encashed, balance — `floatformat:1` on all day figures), by-leave-type and
  by-department rollup tables, `.empty-state` when zero `LeaveAllocation` rows for the selected year.
- [ ] `templates/hrm/reports/leave_liability.html` — filter bar (`year`, `department`), headline stat-cards
  (total days liability, total `$` liability, data-quality "N rows have no resolvable rate" line), row table
  with a rate-source badge per row (`encashment` / `is_estimate` badge / "—" for `none`), by-department and
  by-leave-type rollups, `.empty-state` when zero allocations.
- [ ] `templates/hrm/reports/comp_off.html` — filter bar (`date_from`, `date_to`, `department`), "Earned"
  panel (count, hours, est. days, by-employee, monthly trend chart), "Availed" panel — **OR** a prominent
  caveat banner ("No comp-off leave type configured — create a `LeaveType` with code/name containing 'comp'
  so availed comp-off leave can be reported") when `no_comp_off_type` is set, net-position table labelled
  "estimate, not a tracked balance".
- [ ] `templates/hrm/reports/leave_trend.html` — filter bar (`date_from`, `date_to`, `department`,
  `leave_type` `<select>` from `leave_type_choices`), Chart.js monthly trend (stacked by leave type),
  Chart.js month-of-year seasonality chart, by-department bar, top-10 frequent-leave-takers table,
  `.empty-state` when zero approved `LeaveRequest` rows in range.
- [ ] All 5 templates: filter `<form method="get">` re-submits every active param; `text-align:end` (logical,
  not `right`) for numeric columns; `floatformat:1`/`:2` consistently on days/currency; `{% csrf_token %}`
  n/a (GET-only, read-only pages, no POST forms); badge values match the exact rate-source strings used in
  the view (`encashment`/`estimate`/`none`), with an `{% else %}`/default fallback.

## 6. Admin

- [ ] None — no new models, nothing to register in `apps/hrm/admin.py`.

## 7. Verify

- [ ] **No migration** — `python manage.py makemigrations hrm` produces **zero** changes.
- [ ] `python manage.py check` — zero errors/warnings.
- [ ] `temp/` smoke sweep: `leave_reports_index` + all 4 drill-in `hrm:*_report`/`comp_off_report` URLs
  return 200 for a tenant admin (a) with no query params (defaults), (b) with a full filter set (`year`/
  `department`/`date_from`/`date_to`/`leave_type`), and (c) with odd/nonsensical values (a non-digit or
  future/past-boundary `?year`, `date_from` after `date_to`, a non-digit or cross-tenant `?department`/
  `?leave_type`) — must render an empty/zero report or empty-state, never 500. No `{#`/`{% comment` leak
  markers in any rendered page.
- [ ] **403 for non-admin**: a plain employee user hitting any of the 5 `hrm:*` leave-report URLs gets 403
  (`@tenant_admin_required`).
- [ ] **Cross-tenant isolation**: a second tenant's `LeaveAllocation`/`LeaveRequest`/`LeaveEncashment`/
  `OvertimeRequest` data never appears in tenant A's totals; a `?department`/`?leave_type` belonging to
  another tenant is silently ignored (falls back to "no filter"), never leaks that tenant's name — same
  IDOR-prevention pattern as `_report_department`.
- [ ] **Div-by-zero / empty-state guards**: an empty tenant (zero `LeaveAllocation`/`LeaveRequest` rows)
  renders every report's `.empty-state`/zero KPIs, not a 500 — specifically: register/liability with zero
  allocations for the selected year, liability with zero resolvable rates (all rows `source="none"`),
  comp-off with no matching `LeaveType` (the caveat banner, verified on freshly-seeded demo data per §1),
  trend with zero approved requests in range.
- [ ] Sidebar shows all 4 3.30 bullet entries as **Live** for a tenant-admin login.

## Close-out

- [ ] Run the 7 review agents in order, applying findings + committing after each (one file per commit, no
  `git push`): `code-reviewer` → `explorer` → `frontend-reviewer` → `performance-reviewer` →
  `qa-smoke-tester` → `security-reviewer` → `test-writer`.
  - Expect `code-reviewer` to check the register/liability grid uses `_used_days_subquery()`/DB annotations
    (not per-row `.used_days`/`.balance` property access), the liability rate-resolution batches its
    `LeaveEncashment`/`EmployeeSalaryStructure` lookups instead of querying inside the row loop, and the
    `EmployeeProfile.department` property gotcha is avoided everywhere.
  - Expect `performance-reviewer` to confirm no N+1 across all 5 views, especially the liability report's
    per-row rate resolution and the trend report's month-of-year seasonality grouping.
  - Expect `security-reviewer` to confirm `@tenant_admin_required` on all 5 views and IDOR-safe `department`/
    `leave_type`/`year` resolution.
  - Expect `test-writer` to cover: 403 for non-admin on every report URL; cross-tenant isolation; div-by-zero/
    empty-state on an empty tenant; the register grid's allocated/used/carried/encashed/balance math on a
    known fixture; the liability rate-fallback chain (encashment present → estimate fallback → no-rate,
    each producing the right `source`); the encashable-only `$`-total exclusion; the comp-off empty-state on
    seeded data (no comp-off `LeaveType`) AND the earned/availed panels once a comp-off `LeaveType` is added
    in a test fixture; the trend month-attribution approximation and seasonality bucketing; filter
    round-tripping (year/date-range/department/leave_type narrows results).
- [ ] Update `.claude/skills/hrm/SKILL.md`: add a `### 3.30 Leave Reports (0 new tables — derived views)`
  section documenting the 5 routes, the year-vs-date-range filter split (register/liability use `?year` via
  `_report_year`, comp-off/trend use `_report_period`), the `_used_days_subquery()` reuse, the liability
  rate-fallback chain + `encashable`-only `$`-total rule, and the comp-off heuristic + data gap (no
  auto-provisioned balance, no seeded comp-off `LeaveType`); update `LIVE_LINKS` for `"3.30"`; update the
  Deferred section with this pass's carried-forward deferrals.
- [ ] README.md — add `/3.30` to the Module 3 header line + a bullet describing the 5 reports + the
  no-new-models note; refresh HRM test counts after `test-writer` runs.

## Later passes / deferred (carried over from research-hrm-3.30.md)

- **Comp-off as a first-class, tracked balance** (a `LeaveType.is_comp_off` flag or auto-provisioning a
  `LeaveAllocation` credit when a comp-leave `OvertimeRequest` is approved) — a 3.10/3.11 model/workflow
  change, not a reports-only pass. Until then, the Comp-off Report stays heuristic/estimated.
- **Comp-off expiry tracking** (lapses after 30-90 days) — needs a new date field, not derivable today.
- **Statutory leave-register PDF/Excel export** — export infrastructure is a separate cross-cutting concern,
  not specific to 3.30.
- **GL posting of accrued leave liability** (SAP SuccessFactors precedent) — requires Module 2 Accounting
  `JournalEntry` integration, out of scope for a derived HR report.
- **Concurrent-absence peaks** ("how many people out on the same day") — a bounded O(days) sweep over
  `LeaveRequest` overlaps; valuable but the most implementation-costly item in the research catalog; not
  built this pass, revisit if requested.
- **"On Leave Today" detail list** (who, not just a count) — the index tile computes the count only this
  pass; a full list could later fold into the register report as a secondary panel.
- **Bradford Factor absence-frequency scoring** — closer to 3.29 Absenteeism than 3.30 Leave Trend; not
  recommended for this pass (same call as 3.29's todo).
- **A real, stored per-employee/per-leave-type pay rate** (vs. this pass's `LeaveEncashment` →
  `EmployeeSalaryStructure` fallback estimate) — needs 3.13 Payroll to expose a canonical daily rate; revisit
  the Liability report's rate resolution once that exists.
- **Predictive/AI seasonal forecasting** — belongs to 3.32 Analytics Dashboard, not a derived report in 3.30.

## Review notes

**3.30 Leave Reports — BUILT & reviewed (2026-07-12).** 5 `@tenant_admin_required` derived report views (NO
models, NO migration, NO seed data), reusing the 3.28 report helpers (`_report_period`/`_report_department`/
`_dept_choices`) + the 3.10 leave models. Views (`apps/hrm/views.py`, `# --- 3.30 Leave Reports ---`):
`leave_reports_index`, `leave_register_report` (per-employee×type allocated/carried/availed/encashed/balance for a
`?year`), `leave_liability_report` (encashable-only, balance>0; days × per-day rate → estimated value; rate =
latest approved/paid encashment, else CTC÷365 estimate, else None), `comp_off_report` (OT-comp-leave earned vs
comp-off leave availed), `leave_trend_report` (approved-leave days, by-type, top-takers, monthly TruncMonth trend).
New helpers `_report_year`, `_leave_years`, `_annotated_allocations` (annotates `used_db` via the shared
`_used_days_subquery()` — no per-row N+1), `_alloc_balance`. Templates: `leave_index.html` +
`leave_register/leave_liability/comp_off/leave_trend.html`. `LIVE_LINKS["3.30"]` (4 bullets), README + SKILL.md
updated.

**Review-agent findings applied:**
- **code-reviewer:** liability rate must come from approved/paid encashments only (`-year,-id` tiebreaker), and
  `if rate is None` (not truthy) so a genuine 0/day rate is preserved.
- **performance-reviewer:** dropped a `balance_db` annotation that double-inlined the correlated `used_db`
  subquery (an F() alias can't reference a sibling subquery alias) — balance is derived in Python via
  `_alloc_balance`; `_leave_years` uses `.order_by().values_list().distinct()` (not full-history pull); index
  KPIs use `.aggregate()` not Python sum.
- **explorer:** surfaced an orphaned `availed_count` context key (computed, never rendered) → added the
  Availing-Requests stat-card to `comp_off.html`.
- **frontend-reviewer:** added `|floatformat:1` to the KPI day-totals across register/liability/trend; the
  liability rate cell uses `{% if r.rate is not None %}` so a real 0/day rate renders instead of an em-dash.
- **test-writer:** `apps/hrm/tests/test_leave_reports.py` — 77 tests (access control, never-500, aggregate
  correctness inc. `used_db == LeaveAllocation.used_days`, approved-over-rejected encashment rate, CTC/365
  estimate fallback, comp-off earned-vs-availed gating, cross-tenant IDOR, div-by-zero KPIs, query-count
  ceilings). Surfaced a real defect: `leave_trend_report.top_takers` grouped by `party.name` (merges same-named
  employees) → fixed to key on `employee_id` like the sibling reports; the test now passes directly (xfail removed).
- **security-reviewer:** clean, no exploitable findings. Applied its optional defensive hardening — the
  `?leave_type=` filter in `leave_trend_report` now validates the pk against the tenant
  (`LeaveType.objects.filter(tenant=tenant, pk=...).exists()`) before applying, mirroring `_report_department`.
- **qa-smoke-tester:** covered by the throwaway `temp/` smoke sweep during the build (all 5 reports 200 for
  admin, filters honored, no comment leak, cross-tenant rows ignored) + the pytest IDOR/access-control suite.

**Next: 3.31 Payroll Reports** (Salary Register, Tax/TDS + Form 16, Statutory PF/ESI/PT, CTC cost analysis) —
sources: PayrollCycle, Payslip, PayslipLine, TaxComputation, InvestmentDeclaration, StatutoryReturn,
EmployeeStatutoryIdentifier, CostCenterProfile.

---
# Module 3 — HRM — Sub-module 3.31 Payroll Reports (hrm) — plan from research-hrm-3.31.md (2026-07-12)

**EXTENDS the existing `apps/hrm` app (already built through 3.30) — no new Django app, no new
`INSTALLED_APPS`/`config/urls.py` entries.** Same shape as 3.28/3.29/3.30: **derived, read-only,
`@tenant_admin_required` report views — NO new models, NO migration, NO seeder.** Reuses `_report_period`,
`_report_department`, `_dept_choices` (`apps/hrm/views.py:11932-11953`) and `_report_year`
(`apps/hrm/views.py:12524`, added in 3.30) verbatim. Three NEW small helpers are needed because 3.31's
filter dimensions don't exist yet: `_report_financial_year`/`_fy_choices` (Indian FY is a `CharField` like
`"2025-26"`, not an int — `_report_year` cannot be reused for it), `_report_cost_center`/`_cc_choices`
(mirrors `_report_department`/`_dept_choices` but `kind="cost_center"` — `core.OrgUnit`,
`apps/core/models.py:42-63`), and `_report_job_grade`/`_grade_choices` (`hrm.JobGrade`,
`apps/hrm/models.py:110-130`). Templates live in the existing flat `templates/hrm/reports/` folder
(standalone pages, no entity sub-folder — Template Folder Structure rule 6). `EmployeeProfile.department`
is a Python `@property` (`apps/hrm/models.py:343`), **not a DB column** — same recurring gotcha as
3.28-3.30: every department aggregate/filter across all 6 views MUST use `employee__employment__org_unit`.

## 0. The one non-obvious join — cost-center attribution (read this before writing `cost_center_report`)

- [ ] **Reject the research doc's stated v1 simplification.** `research-hrm-3.31.md` assumed employees are
  matched to a cost center via `Employment.org_unit` pointing directly at the `core.OrgUnit(kind=
  "cost_center")` node. **Confirmed false against the actual seed data**
  (`apps/hrm/management/commands/seed_hrm.py:613-634`): `Employment.org_unit` is always set to a
  **department**-kind `OrgUnit`; cost centers are separate `OrgUnit(kind="cost_center")` nodes that a
  department maps to via **`hrm.DepartmentProfile.cost_center`** (`apps/hrm/models.py:183-185`, FK to
  `core.OrgUnit` with `limit_choices_to={"kind": "cost_center"}`). Matching only direct
  `employee__employment__org_unit=cc` would return **zero actual spend for every cost center on the
  seeded demo tenant** — a silent-empty-report bug, not a passing simplification.
- [ ] **Correct v1 join (defensive OR, in case a future tenant DOES assign an employee's `org_unit`
  directly to a cost-center node):** an employee's cost center is `employee__employment__org_unit` when
  that unit's `kind == "cost_center"`, else `employee__employment__org_unit`'s `DepartmentProfile.cost_center`
  when the unit is a department with a mapped cost center, else unmapped ("Unassigned").
- [ ] **Implementation shape (3 queries total for the whole report, not N+1 per cost center):**
  1. `dept_to_cc = dict(DepartmentProfile.objects.filter(tenant=tenant, cost_center__isnull=False)
     .values_list("org_unit_id", "cost_center_id"))` — one query, department OrgUnit id -> cost-center
     OrgUnit id.
  2. `org_totals = {row["employee__employment__org_unit_id"]: row for row in
     Payslip.objects.filter(tenant=tenant, cycle__pay_date__year=budget_year)
     .values("employee__employment__org_unit_id")
     .annotate(gross=Sum("gross_pay"), headcount=Count("employee_id", distinct=True))}` — one query,
     grouped by the employee's actual org unit (department OR direct cost-center assignment).
  3. `employer_totals` — the same `.values(...).annotate(employer=Sum("amount"))` grouped query over
     `PayslipLine.objects.filter(tenant=tenant, payslip__cycle__pay_date__year=budget_year,
     contribution_side="employer")` keyed on `payslip__employee__employment__org_unit_id` — one query.
  4. Fold in Python: for each `org_unit_id` key in `org_totals`, resolve `cc_id = org_unit_id if org_unit_id
     in cc_ids else dept_to_cc.get(org_unit_id)` (`cc_ids` = the set of already-fetched
     `CostCenterProfile.org_unit_id`s for this tenant) and accumulate into a `cc_id -> {gross, headcount,
     employer}` dict; `org_unit_id`s that resolve to neither roll into an explicit "Unassigned" bucket
     (rendered, not dropped) so spend is never silently lost.
- [ ] **`headcount` MUST use `Count("employee_id", distinct=True)`**, never a raw row count — an employee
  appears once per `PayrollCycle` within the budget year, so a naive `.count()` on the grouped queryset
  double/triple-counts headcount across multi-cycle years (the employee_id-keyed aggregation gotcha for
  this view).

## 1. Confirm NO new models — every source field/helper verified against apps/hrm/models.py

- [ ] State in the commit message: **3.31 adds zero models, zero migrations, zero seed data.**
- [ ] `PayComponent` (`apps/hrm/models.py:3269-3339`): `component_type` (earning/statutory_deduction/
  voluntary_deduction/reimbursement/variable), `contribution_side` (employee/employer/both) — the
  component-mix grouping key for `ctc_report`.
- [ ] `SalaryStructureTemplate`/`SalaryStructureLine` (`3342-3412`): `SalaryStructureLine.resolved_amount
  (ctc=None)` — for `fixed_amount` lines returns the flat amount **regardless of the `ctc` arg**; for
  `pct_*` lines returns `ctc * pct / 100` where `ctc` defaults to `template.annual_ctc_amount` but the
  caller MUST pass the employee's own `EmployeeSalaryStructure.annual_ctc_amount` to get the
  employee-specific breakdown (`ctc_report`'s whole point — same override `Payslip.recompute()` already
  uses at `apps/hrm/models.py:3616-3620`).
- [ ] `EmployeeSalaryStructure` (`3415-3460`): `annual_ctc_amount`, `status` (active/superseded — exactly
  one active row per employee, enforced in `clean()`), `template` FK, `effective_from`. `ctc_report`'s
  base queryset.
- [ ] `PayrollCycle` (`3472-3551`): `period_start`/`period_end`/`pay_date`, `status` (draft/
  pending_approval/approved/rejected/locked), derived `@property`s `headcount`/`total_gross`/
  `total_deductions`/`total_net` (each memoized per-instance via `_totals()`, `3526-3548`) — safe for a
  single "latest cycle" index tile (2 queries), never call these `@property`s inside a per-row loop.
- [ ] `Payslip` (`3554-3673`): `cycle`/`employee` FK, `gross_pay`/`total_deductions`/`net_pay` (positive
  magnitudes, `editable=False`, derived), `lop_days`/`lop_amount`, `arrears_amount`, `bonus_amount`,
  `on_hold`/`hold_reason`. `unique_together = (tenant, cycle, employee)` — one row per employee per cycle,
  exactly the Salary Register grid's row shape.
- [ ] `PayslipLine` (`3676-3704`): `payslip` FK, `component_name`, `component_type` (PayComponent's 5
  types + `arrears`/`bonus`/`lop`), `amount` (positive), `contribution_side` (snapshotted — employer-side
  statutory contributions do NOT reduce `net_pay`, they're a company cost only). The register's optional
  component-type breakdown and `cost_report`'s `employer_cost` pattern (`views.py:12231-12232`) both key
  off this.
- [ ] `EmployeeStatutoryIdentifier` (`3876-3922`): `uan_number`/`pf_number`/`esi_number` (raw — NEVER
  render), `masked_uan_number()`/`masked_pf_number()`/`masked_esi_number()` (last-4 only — MUST be used by
  `statutory_report`), `pt_state`, `is_pf_applicable`/`is_esi_applicable`. **WARNING (carried from
  research): these are redacted from AuditLog too — the report template must call the masked_* methods,
  never `.uan_number`/`.pf_number`/`.esi_number` directly.**
- [ ] `StatutoryReturn` (`3925-...`): `scheme` (pf/esi/pt/**tds_24q/tds_form16**/lwf — `statutory_report`
  uses only pf/esi/pt/lwf; the two `tds_*` schemes belong to `tax_report`, exclude them from
  `statutory_report`'s scheme dropdown), `period_start`/`period_end`, `employee_contribution_total`/
  `employer_contribution_total`/`headcount` (all `editable=False`, derived by `recompute()`), `due_date`,
  `status` (pending/filed/paid/late), `@property is_overdue` (`status=="pending" and due_date <
  today` — replicate as a DB `Q()` for any count/aggregate, never call the Python property in a loop).
- [ ] `TaxRegimeConfig`/`TaxSlabBand` (`4120-4179`): rate master only — `tax_report` reads
  `InvestmentDeclaration.regime_elected`/`TaxComputation`, not these directly.
- [ ] `InvestmentDeclaration` (`4182-4224`): `employee`/`financial_year`/`regime_elected`
  (old/new)/`status` (draft/submitted/locked). `unique_together = (tenant, employee, financial_year)`.
- [ ] `InvestmentDeclarationLine` (`4227-4281`): `section_code` (80c/80d/80d_parents/hra/
  24b_home_loan_interest/80ccd_1b_nps/lta/80e_education_loan/other_chapter_via), `declared_amount`,
  `verified_amount` (nullable — `Sum()` ignores NULLs, guard the aggregate with `or 0` when ALL rows are
  unverified), `@property effective_amount`.
- [ ] `TaxComputation` (`4325-...`): `employee`/`declaration`/`financial_year` FK+denormalized copy,
  `computation_type` (provisional/final), `tax_payable`/`tax_paid_ytd`/`monthly_tds_amount` (all
  `editable=False`, derived), `statutory_return` FK (**set only after `link_form16()` runs** — null means
  "not yet linked/pending Form 16"). `unique_together = (tenant, employee, financial_year)`.
  **`form16_partb(pk)` (`apps/hrm/views.py:7003`, url `hrm:form16_partb`) takes a `TaxComputation.pk`, NOT
  a `StatutoryReturn.pk`** — the Form 16 register's row link is `{% url 'hrm:form16_partb' pk=row.pk %}`
  where `row` is the `TaxComputation` instance, confirmed against the view signature.
- [ ] `CostCenterProfile` (`apps/hrm/models.py:219-251`): `org_unit` (1:1 to `core.OrgUnit(kind=
  "cost_center")`), `budget_annual`, `budget_year`, `owner`. Seeded (`seed_hrm.py:613-624`) with
  `budget_year=today.year` at seed time — so on freshly seeded data `_report_year`'s "current calendar
  year" default matches; document that this drifts (silently, by design) once a real year passes without
  re-seeding — the template's "no budget row for this FY" guard (below) covers it.
- [ ] `core.OrgUnit` (`apps/core/models.py:42-63`): `kind` choices include `"cost_center"` alongside
  `"department"`; self-referential `parent` (multi-level cost-center roll-up is explicitly deferred, §
  Later passes, matching the research call).
- [ ] `hrm.DepartmentProfile.cost_center` (`apps/hrm/models.py:183-185`) — the department-to-cost-center
  mapping FK the §0 join depends on. `hrm.JobGrade` (`apps/hrm/models.py:110-130`) — `ctc_report`'s grade
  filter, via `SalaryStructureTemplate.job_grade`.
- [ ] Confirm no field/method gap forces a 500: everything the 6 views need exists; div-by-zero (empty
  tenant, no `PayrollCycle` rows, no resolvable financial year, zero `StatutoryReturn` rows for the
  selected scheme, zero active `EmployeeSalaryStructure` rows, zero `CostCenterProfile` rows) is a
  **view-logic** guard/empty-state (§2), not a data gap.

## 2. Views (apps/hrm/views.py) — new `# --- 3.31 Payroll Reports ---` banner (append after the 3.30 block)

- [ ] All 6 functions decorated `@tenant_admin_required`, `if tenant is not None:` guard pattern
  (superuser `tenant=None` renders an empty/zero report, never `.filter(tenant=None)`).
- [ ] New `_fy_choices(tenant)` / `_report_financial_year(request, tenant)`: `_fy_choices` returns
  `list(InvestmentDeclaration.objects.filter(tenant=tenant).values_list("financial_year", flat=True)
  .distinct().order_by("-financial_year"))` (tenant `None` -> `[]`); `_report_financial_year` reads
  `?financial_year`, returns it only if it's literally in `_fy_choices(tenant)` (never trusts an
  arbitrary string), else the latest (`choices[0]`) or `""` when the tenant has none yet — mirrors
  `_report_year`'s "safe default to latest, never crash on garbage input" contract but for a `CharField`
  FY instead of an int year.
- [ ] New `_cc_choices(tenant)` / `_report_cost_center(request, tenant)`: identical shape to
  `_dept_choices`/`_report_department` (`views.py:11932-11943`) but `kind="cost_center"` — tenant-scoped,
  digit-checked pk, `.filter(tenant=tenant, kind="cost_center", pk=int(pk)).first()` else `None`
  (IDOR-safe, same pattern).
- [ ] New `_grade_choices(tenant)` / `_report_job_grade(request, tenant)`: `JobGrade.objects.filter(
  tenant=tenant, is_active=True).order_by("level_order", "name")`; resolver mirrors `_report_department`
  (digit-checked, tenant-scoped `JobGrade.objects.filter(tenant=tenant, pk=int(pk)).first()`).
- [ ] Follow the **Filter Implementation Rules**: every `<select>` the templates need gets its choices
  passed explicitly — `department_choices = _dept_choices(tenant)`, `cycle_choices` (list, salary
  register/cost analysis), `financial_year_choices = _fy_choices(tenant)`, `scheme_choices` (statutory,
  pf/esi/pt/lwf only — exclude the two `tds_*` codes), `status_choices` (statutory: `StatutoryReturn
  .STATUS_CHOICES`), `cost_center_choices = _cc_choices(tenant)`, `grade_choices = _grade_choices(tenant)`.
  FK/pk `<select>` comparisons use `|stringformat:"d"`; string fields (`scheme`, `status`,
  `financial_year`) use `request.GET.x == value`.
- [ ] `payroll_reports_index(request)` — `/hrm/reports/payroll/`. No filters. KPI tiles (mirrors
  `hr_reports_index`/`leave_reports_index`): latest `PayrollCycle` headcount/`total_gross`/`total_net`
  (guard `cycle is None` — no cycles yet), pending Form 16 count (`TaxComputation.objects.filter(
  tenant=tenant, statutory_return__isnull=True).count()`), overdue statutory returns count
  (`StatutoryReturn.objects.filter(tenant=tenant, status="pending", due_date__lt=today).count()` — the DB
  form of `is_overdue`, not the Python property in a loop). Links to **all 5** drill-in reports (including
  `cost_center_report`, which has no direct sidebar bullet — see §4). Render
  `hrm/reports/payroll_index.html`.
- [ ] `salary_register_report(request)` — `/hrm/reports/payroll/salary-register/`. Filters: `?cycle`
  (mirrors `cost_report`'s exact pattern, `views.py:12215-12219`: `cycles = list(PayrollCycle.objects
  .filter(tenant=tenant).order_by("-pay_date"))`, `cycle = next((c for c in cycles if str(c.pk) ==
  cycle_pk), None) or (cycles[0] if cycles else None)` — default to the latest cycle by `pay_date`),
  `?department` (`_report_department`), `?on_hold` (`"1"` -> `.filter(on_hold=True)`). Base:
  `Payslip.objects.filter(tenant=tenant, cycle=cycle).select_related("employee__party",
  "employee__employment__org_unit").order_by("employee__party__name")`, department/on_hold filters
  applied when set. Grid columns: employee, `gross_pay`, `total_deductions`, `net_pay`, `lop_days`/
  `lop_amount`, `arrears_amount`, `bonus_amount`, `on_hold` badge. Totals footer:
  `payslips.aggregate(gross=Sum("gross_pay"), ded=Sum("total_deductions"), net=Sum("net_pay"),
  arrears=Sum("arrears_amount"), bonus=Sum("bonus_amount"), lop=Sum("lop_amount"))`. Optional
  component-type breakdown (per research's "columns pivoted from PayslipLine, grouped by
  component_type"): ONE query, `PayslipLine.objects.filter(payslip__in=payslips).values("payslip_id",
  "component_type").annotate(total=Sum("amount"))`, folded in Python into a `{payslip_id: {type: total}}`
  dict for O(1) per-row template lookup — **never** re-query `.lines` per payslip row (N+1 guard).
  **Employee_id-keyed gotcha**: the breakdown dict MUST key on `payslip_id` (the grid's row key), not
  `employee_id` — one `Payslip` = one row = one employee for THIS cycle, but keying on employee_id would
  silently misalign if the same employee ever appeared via a different join. Guard: `cycle is None` (no
  `PayrollCycle` rows yet) renders the empty-state, never a 500. Render
  `hrm/reports/salary_register.html`.
- [ ] `tax_report(request)` — `/hrm/reports/payroll/tax/`. Filters: `?financial_year` (via
  `_report_financial_year`, default latest present), `?department` (`_report_department`), `?regime`
  (`old`/`new`, matched against `declaration__regime_elected`). Three sections on one page:
  (a) **TDS summary**: `TaxComputation.objects.filter(tenant=tenant, financial_year=fy)
  .select_related("employee__party", "employee__employment__org_unit", "declaration")`, dept/regime
  filters applied, columns = employee, `declaration.get_regime_elected_display`, `tax_payable`,
  `tax_paid_ytd`, `monthly_tds_amount`, `computation_type`; KPIs `total_payable`/`total_paid_ytd`
  (`Sum`, `or 0`), `avg_payable` (guard `headcount == 0`), regime split
  (`.values("declaration__regime_elected").annotate(count=Count("id"))`).
  (b) **Investment declaration status funnel**: `InvestmentDeclaration.objects.filter(tenant=tenant,
  financial_year=fy).values("status").annotate(count=Count("id"))` (draft/submitted/locked) PLUS a
  "not filed" count = `EmployeeProfile.objects.filter(tenant=tenant).exclude(pk__in=
  InvestmentDeclaration.objects.filter(tenant=tenant, financial_year=fy).values("employee_id")).count()`
  (one `exclude`/subquery, not a per-employee loop). Optional section-wise sub-table:
  `InvestmentDeclarationLine.objects.filter(tenant=tenant, declaration__financial_year=fy)
  .values("section_code").annotate(declared=Sum("declared_amount"), verified=Sum("verified_amount"))` —
  `verified` can be `None` per row (`Sum` skips NULLs; guard the row-level display with `or 0`).
  (c) **Form 16 filing-status register**: derive directly from the already-fetched `TaxComputation`
  queryset for the FY (no separate `StatutoryReturn` query/date-parsing) — `.select_related(
  "statutory_return")`; status = "Linked/Filed" when `statutory_return_id` is set (show
  `statutory_return.get_status_display()`) else "Pending link"; each row links to
  `{% url 'hrm:form16_partb' pk=row.pk %}` (confirmed `TaxComputation.pk`, §1). **Gotcha (from seed
  data):** `seed_hrm.py` only creates ONE `InvestmentDeclaration`/`TaxComputation` for ONE employee at
  FY `"2025-26"` — the TDS table and Form 16 register will show exactly 1 row and the "not filed" count
  will be `total_employees - 1` on freshly seeded demo data; this is a sparse-but-correct render, not an
  empty-state condition (no special-case needed, just don't assume >1 row when smoke-testing). Guard:
  `fy == ""` (no `InvestmentDeclaration` rows exist yet for this tenant at all) renders the full
  empty-state. Render `hrm/reports/tax.html`.
- [ ] `statutory_report(request)` — `/hrm/reports/payroll/statutory/`. Filters: `?scheme` (default
  `"pf"` — pf/esi/pt/lwf only, exclude `tds_24q`/`tds_form16`), `_report_period` (date range on
  `period_start`), `?status` (`StatutoryReturn.STATUS_CHOICES`). Register query:
  `StatutoryReturn.objects.filter(tenant=tenant, scheme=scheme, period_start__gte=date_from,
  period_start__lte=date_to)`, status filter applied when set. KPIs: `employee_contribution_total`/
  `employer_contribution_total` (`Sum`, `or 0`), `headcount_total` (`Sum("headcount")` — **document this
  is a sum ACROSS periods/returns, not a distinct-employee count**, since `StatutoryReturn.headcount` is
  itself a period snapshot), overdue count (`Q(status="pending") & Q(due_date__lt=today)` — the DB form
  of `is_overdue`, never the Python property in a per-row loop). Employee-coverage section:
  `EmployeeStatutoryIdentifier.objects.filter(tenant=tenant).select_related("employee__party")` —
  `is_pf_applicable`/`is_esi_applicable` counts, and a drill-down table rendering ONLY
  `masked_uan_number()`/`masked_pf_number()`/`masked_esi_number()`/`pt_state` (WARNING: never
  `.uan_number`/`.pf_number`/`.esi_number` raw — this is the module's one hard security rule, flag in a
  code comment). **Gotcha (from seed data):** `seed_hrm.py` generates only ONE `StatutoryReturn`
  (`scheme="pf"`) — `?scheme=esi`/`pt`/`lwf` returns ZERO rows on freshly seeded demo data; the register
  section MUST render its `.empty-state` cleanly for those schemes (not a caveat banner like 3.30's
  comp-off — this is a legitimately-empty, not "not configured", condition — just don't 500 or show
  misleading zeros as if data exists). Render `hrm/reports/statutory.html`.
- [ ] `ctc_report(request)` — `/hrm/reports/payroll/ctc/`. Filters: `?department`
  (`_report_department`), `?grade` (`_report_job_grade`, matched against
  `template__job_grade`). Base: `EmployeeSalaryStructure.objects.filter(tenant=tenant, status="active")
  .select_related("employee__party", "employee__employment__org_unit", "template__job_grade")`,
  dept/grade filters applied. Grid columns: employee, department, job grade, `annual_ctc_amount`,
  monthly equivalent (`annual_ctc_amount / 12`, computed in the view — never stored). KPIs:
  `total_annual_ctc` (`Sum`, `or 0`), `headcount` (`.count()`), `avg_ctc` (guard `headcount == 0`).
  **Component-type mix chart** (Chart.js, the research's explicit "buildable now" call): cache each
  distinct `template_id`'s lines ONCE (`SalaryStructureLine.objects.filter(template_id=t)
  .select_related("pay_component")`, keyed in a `{template_id: [lines]}` dict built by iterating the
  distinct `template_id`s in the base queryset — bounded by the number of DISTINCT templates, not the
  number of employees), then for each `EmployeeSalaryStructure` row call
  `line.resolved_amount(row.annual_ctc_amount)` for every cached line and accumulate into
  `component_totals[pay_component.component_type]` — **never** re-query `.lines` per employee (N+1
  guard, this is the one Python-level loop in the module and it must be template-bounded, not
  employee-bounded). `json.dumps()` the component-type labels/totals for the Chart.js pie/bar,
  `{{ x|safe }}` in the template, guarded by `typeof Chart === 'undefined'`. Guard: zero active
  structures for the filter renders the empty-state. Render `hrm/reports/ctc.html` — includes a
  cross-link button to `cost_center_report` (§4, not in `LIVE_LINKS` directly).
- [ ] `cost_center_report(request)` — `/hrm/reports/payroll/cost-center/`. Filters: `?cost_center`
  (`_report_cost_center`), `?budget_year` (**reuse `_report_year(request)` verbatim** — it already
  defaults safely to the current calendar year and digit-guards garbage input; no new year-parsing
  helper needed). Implementation: the §0 three-query fold (`dept_to_cc`, `org_totals`,
  `employer_totals`), then per `CostCenterProfile` row: `actual_gross` from the folded `org_totals`
  (`0` if the cost center had no matched spend this year), `variance_amount = (profile.budget_annual or
  0) - actual_gross`, `variance_pct = round(variance_amount / profile.budget_annual * 100, 1) if
  profile.budget_annual else None` (guard: `None` renders "no budget set", not a `ZeroDivisionError`),
  a "budget row is for FY {budget_year_of_row}, not the selected {budget_year}" caveat when
  `profile.budget_year != budget_year` (silent mismatch is worse than a visible caveat — see §1's
  `budget_year` drift note). Label the actual figure "actual spend, cycles within FY {budget_year}" (not
  "actual annual") since on freshly seeded demo data there is only ONE `PayrollCycle`, so a full-year
  budget-vs-one-month-actual comparison would otherwise read as misleadingly under-budget. Optional:
  reuse `cost_report`'s 12-cycle trend-chart pattern (`views.py:12239-12241`) scoped to the selected cost
  center's matched employees, if useful — not required. Guard: zero `CostCenterProfile` rows for the
  tenant renders the empty-state. Render `hrm/reports/cost_center.html`.
- [ ] Every rate/percentage/average across all 6 views is guarded against a zero denominator (empty
  tenant, zero payslips for the selected cycle, zero declarations for the selected FY, zero returns for
  the selected scheme, zero active salary structures, zero/`None` `budget_annual`) — audit each before
  considering a view done.

## 3. URLs (apps/hrm/urls.py) — append after the 3.30 block (after line 966 `reports/leave/trend/`, before the closing `]` at line 967)

- [ ] New `# 3.31 Payroll Reports` comment block:
  ```python
  # 3.31 Payroll Reports (derived, read-only, admin-only)
  path("reports/payroll/", views.payroll_reports_index, name="payroll_reports_index"),
  path("reports/payroll/salary-register/", views.salary_register_report, name="salary_register_report"),
  path("reports/payroll/tax/", views.tax_report, name="tax_report"),
  path("reports/payroll/statutory/", views.statutory_report, name="statutory_report"),
  path("reports/payroll/ctc/", views.ctc_report, name="ctc_report"),
  path("reports/payroll/cost-center/", views.cost_center_report, name="cost_center_report"),
  ```
- [ ] Confirm no path/name collision with `reports/hr/...` (3.28), `reports/attendance/...` (3.29),
  `reports/leave/...` (3.30), or the existing 3.13-3.17 CRUD URLs (`payrollcycle_list`,
  `payslip_list`/`payslip_detail`, `taxcomputation_list`, `statutoryreturn_list`, `form16_partb`,
  `payment_register`, etc.) — distinct `reports/payroll/` segment, no clash.

## 4. Navigation — apps/core/navigation.py

- [ ] New `LIVE_LINKS["3.31"]` block (insert near the `"3.30"` entry), bullet text copied **verbatim**
  from `NavERP.md:649-653`. **Only 4 bullets exist in NavERP.md for 5 non-index views** — "Cost Analysis"
  covers both `ctc_report` (CTC breakdown) and `cost_center_report` (cost-center budget-vs-actual) per
  the research's own "Cost Analysis, part 1 / part 2" framing; `ctc_report` gets the sidebar bullet,
  `cost_center_report` is reachable from `payroll_reports_index`'s hub tiles and a cross-link on
  `ctc_report`'s page (same non-bullet precedent as `leave_reports_index`'s "On Leave Today" tile in
  3.30):
  ```python
  # 3.31 Payroll Reports — derived, read-only, @tenant_admin_required (no models).
  # payroll_reports_index is the landing hub, not itself a bullet. cost_center_report has no direct
  # bullet either (NavERP.md's single "Cost Analysis" bullet covers both ctc_report and
  # cost_center_report) — reachable via the hub + a cross-link on ctc_report.html.
  "3.31": {
      "Salary Register": "hrm:salary_register_report",   # bullet (per-cycle earnings/deductions/net grid)
      "Tax Reports": "hrm:tax_report",                    # bullet (TDS/regime split, declarations, Form 16 register)
      "Statutory Reports": "hrm:statutory_report",        # bullet (PF/ESI/PT/LWF register, masked employee coverage)
      "Cost Analysis": "hrm:ctc_report",                  # bullet (structural CTC breakdown; cost_center_report cross-linked)
  },
  ```

## 5. Templates (templates/hrm/reports/)

- [ ] `templates/hrm/reports/payroll_index.html` — standalone landing page, KPI tiles matching
  `hr_index.html`/`leave_index.html`'s visual language (latest-cycle headcount/gross/net, pending Form 16
  count, overdue statutory count), 5 tiles/links into every drill-in report including
  `cost_center_report` (which has no sidebar bullet — this hub is its primary entry point).
- [ ] `templates/hrm/reports/salary_register.html` — filter bar (`cycle` `<select>` from `cycle_choices`
  using `|stringformat:"d"`, `department` `<select>`, `on_hold` checkbox reflecting `request.GET`), grid
  table (one row per `Payslip`: gross/deductions/net/lop/arrears/bonus, `on_hold` badge), totals footer
  row, optional expandable component-type breakdown per row, `.empty-state` when no `PayrollCycle` exists
  or the selected cycle has zero payslips.
- [ ] `templates/hrm/reports/tax.html` — filter bar (`financial_year` `<select>` from
  `financial_year_choices`, `department`, `regime` `<select>` old/new), three stacked sections (TDS
  summary table + KPI stat-cards, declaration status funnel with a "not filed" count, Form 16 register
  table with a status badge + `{% url 'hrm:form16_partb' pk=row.pk %}` link per linked row), optional
  section-wise (80C/HRA/etc.) declared-vs-verified sub-table, `.empty-state` when no `financial_year`
  choices exist for the tenant.
- [ ] `templates/hrm/reports/statutory.html` — filter bar (`scheme` `<select>` limited to pf/esi/pt/lwf,
  `date_from`/`date_to`, `status` `<select>`), register table (`StatutoryReturn` rows: contribution
  totals, headcount, due date, overdue flag badge, status), employee-coverage section (PF/ESI applicable
  counts + a masked-identifier table — `masked_uan_number()`/`masked_pf_number()`/`masked_esi_number()`
  ONLY, never raw), `.empty-state` per scheme when zero returns (expected for esi/pt/lwf on fresh seed
  data — render cleanly, not as an error).
- [ ] `templates/hrm/reports/ctc.html` — filter bar (`department`, `grade` `<select>` from
  `grade_choices` using `|stringformat:"d"`), KPI stat-cards (total annual CTC, avg CTC, headcount),
  per-employee grid (department, grade, annual CTC, monthly equivalent), Chart.js component-type mix
  chart (`json.dumps()` + `{{ x|safe }}`, `typeof Chart === 'undefined'` guard), a "View Cost Center
  Report" cross-link button, `.empty-state` when zero active salary structures match the filter.
- [ ] `templates/hrm/reports/cost_center.html` — filter bar (`cost_center` `<select>` from
  `cost_center_choices`, `budget_year`), per-cost-center table (budget_annual, actual spend "cycles
  within FY", headcount, employer cost, variance amount + `%`, an explicit "no budget set for FY {year}"
  cell state and a "budget row is for a different FY" caveat where applicable), an "Unassigned" spend row
  when any matched org unit resolves to neither a cost center nor a mapped department,
  `.empty-state` when zero `CostCenterProfile` rows exist for the tenant.
- [ ] All 6 templates: filter `<form method="get">` re-submits every active param; `text-align:end`
  (logical, not `right`) for numeric columns; `floatformat:2` on currency, `floatformat:1` on
  days/percentages consistently; `{% csrf_token %}` n/a (GET-only, read-only pages, no POST forms); badge
  values match the exact model `CHOICES` strings used in the view, with an `{% else %}`/default fallback.

## 6. Admin

- [ ] None — no new models, nothing to register in `apps/hrm/admin.py`.

## 7. Verify

- [ ] **No migration** — `python manage.py makemigrations hrm` produces **zero** changes.
- [ ] `python manage.py check` — zero errors/warnings.
- [ ] `temp/` smoke sweep: `payroll_reports_index` + all 5 drill-in `hrm:*_report`/`ctc_report`/
  `cost_center_report` URLs return 200 for a tenant admin (a) with no query params (defaults), (b) with a
  full filter set (`cycle`/`department`/`on_hold`/`financial_year`/`regime`/`scheme`/`status`/
  `date_from`/`date_to`/`grade`/`cost_center`/`budget_year`), and (c) with odd/nonsensical values (a
  non-digit or cross-tenant `?cycle`/`?department`/`?grade`/`?cost_center`, an unknown `?financial_year`
  string, an unknown `?scheme`, `date_from` after `date_to`) — must render an empty/zero report or
  empty-state, never 500. No `{#`/`{% comment` leak markers in any rendered page.
- [ ] **403 for non-admin**: a plain employee user hitting any of the 6 `hrm:*` payroll-report URLs gets
  403 (`@tenant_admin_required`).
- [ ] **Cross-tenant isolation**: a second tenant's `Payslip`/`TaxComputation`/`InvestmentDeclaration`/
  `StatutoryReturn`/`EmployeeSalaryStructure`/`CostCenterProfile` data never appears in tenant A's
  totals; a `?cycle`/`?department`/`?grade`/`?cost_center` belonging to another tenant is silently
  ignored (falls back to "no filter"/latest-default), never leaks that tenant's name or numbers — same
  IDOR-prevention pattern as `_report_department`.
- [ ] **Masked-ID leak check**: grep the rendered `statutory.html` output (and its view context) for the
  raw `uan_number`/`pf_number`/`esi_number` values seeded in `seed_hrm.py` (`UAN0000000001`,
  `MH/BAN/1234567/000/0001`, `3411000001`, etc.) — they must NEVER appear verbatim in the HTML; only the
  `masked_*()` last-4 forms are allowed. This is a hard security check, not a style nit.
- [ ] **Div-by-zero / empty-state guards**: an empty tenant (zero `PayrollCycle`/`EmployeeSalaryStructure`
  rows) renders every report's `.empty-state`/zero KPIs, not a 500 — specifically: salary register with
  no cycles, tax report with no `financial_year` choices, statutory report per-scheme (esi/pt/lwf
  expected empty on fresh seed data), CTC report with zero active structures, cost-center report with
  zero `CostCenterProfile` rows or a `None`/zero `budget_annual`.
- [ ] Sidebar shows all 4 3.31 bullet entries as **Live** for a tenant-admin login.

## Close-out

- [ ] Run the 7 review agents in order, applying findings + committing after each (one file per commit,
  no `git push`): `code-reviewer` -> `explorer` -> `frontend-reviewer` -> `performance-reviewer` ->
  `qa-smoke-tester` -> `security-reviewer` -> `test-writer`.
  - Expect `code-reviewer` to check the §0 cost-center fold uses the 3-query grouped shape (not a
    per-cost-center loop), `ctc_report`'s component-mix caches lines per distinct `template_id` (not per
    employee), and the `EmployeeProfile.department` property gotcha is avoided everywhere.
  - Expect `performance-reviewer` to confirm no N+1 across all 6 views, especially §0's cost-center
    attribution fold and `ctc_report`'s `resolved_amount()` loop.
  - Expect `security-reviewer` to confirm `@tenant_admin_required` on all 6 views, IDOR-safe
    `department`/`grade`/`cost_center`/`cycle` resolution, and — specifically for this sub-module — that
    `statutory.html` never renders a raw UAN/PF/ESI number (the masked-ID leak check from §7).
  - Expect `test-writer` to cover: 403 for non-admin on every report URL; cross-tenant isolation; the
    masked-identifier leak check as an automated assertion (not just a manual grep); div-by-zero/
    empty-state on an empty tenant; the salary register's totals-footer math on a known fixture; the
    §0 cost-center attribution fold (direct assignment AND department-mapped AND unassigned cases, each
    landing in the right bucket); the `ctc_report` component-mix totals against a hand-computed
    `resolved_amount()` fixture; the Form 16 register's link/no-link split; filter round-tripping
    (cycle/financial_year/scheme/department/grade/cost_center narrows results).
- [ ] Update `.claude/skills/hrm/SKILL.md`: add a `### 3.31 Payroll Reports (0 new tables — derived
  views)` section documenting the 6 routes, the 3 new helpers (`_report_financial_year`/`_fy_choices`,
  `_report_cost_center`/`_cc_choices`, `_report_job_grade`/`_grade_choices`), the §0 cost-center
  attribution join (and why the research's naive direct-assignment assumption was rejected), the
  masked-identifier rule, and the "Cost Analysis" single-bullet/two-view mapping; update `LIVE_LINKS` for
  `"3.31"`; update the Deferred section with this pass's carried-forward deferrals.
- [ ] README.md — add `/3.31` to the Module 3 header line (`README.md:265`) + a bullet describing the 6
  reports + the no-new-models note; refresh HRM test counts (`README.md:544`/`781`) after `test-writer`
  runs.

## Later passes / deferred (carried over from research-hrm-3.31.md)

- **Payroll journal / GL-mapped export** (Gusto Payroll Journal, Paycom GL Concierge, Rippling GL sync) —
  belongs to `accounting.PayrollRun`/`JournalEntry` per the existing "HRM never posts a JournalEntry"
  convention (`PayrollCycle.accounting_payroll_run`) — not an HRM report.
- **Form 16 PDF/certificate generation** — already flagged deferred in the existing `form16_partb`
  docstring ("PDF rendering deferred"); 3.31 only adds the aggregate filing-status register, not the PDF.
- **TDS Form 24Q e-filing/FVU validation, PF ECR file generation, ESI/PT challan file generation** —
  statutory e-filing/government-portal integrations — out of a single Django pass; the models already
  store enough (`StatutoryReturn.registration_number_used`, `payment_reference`) to add the export later.
- **Auto-pay/auto-file to government portals** (RazorpayX, Zoho Payroll) — external
  integration/compliance-vendor API — later.
- **Multi-entity/multi-country consolidated G2N report** (Deel) — NavERP payroll is single-tenant/
  single-currency in this pass — deferred.
- **Job/project-based labor costing** (Rippling job profitability via GL) — needs project-costing tie-in
  from a later Accounting/Projects pass — deferred.
- **Custom/drag-drop report builder, prebuilt-report library at scale** — this is NavERP's 3.32 Analytics
  Dashboard territory, not 3.31 — explicitly out of this pass.
- **Payroll reconciliation vs. bank/vendor data** (Workday Global Payroll Reconciliation) — NavERP has no
  external payroll vendor/bank feed to reconcile against yet — deferred until a bank-feed integration
  exists.
- **Multi-level cost-center roll-up** (department children rolling up to a parent cost center via
  `OrgUnit.parent`, or a cost center's own children) — v1 `cost_center_report` matches direct
  department-to-cost-center mapping only (§0); documented as a known simplification, not silently
  dropped.
- **A proper per-`PayslipLine` scheme tag** (replacing `StatutoryReturn`'s v1 `component_name`-substring
  keyword matching) — a 3.14/3.15 model change, out of scope for a derived report pass; `statutory_report`
  inherits whatever `StatutoryReturn.recompute()` already produced.

## Review notes

(filled in at the end)
