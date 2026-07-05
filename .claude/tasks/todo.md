---
# Module 3 — HRM — Sub-module 3.19 Performance Review (performance-review) — plan from research-hrm-performance-review.md (2026-07-05)

**Context.** Extends the existing `apps/hrm` app — NOT a new app. This is the **second**
Performance Management sub-module (3.18 Goal Setting -> **3.19 Performance Review** -> 3.20
Continuous Feedback -> 3.21 Performance Improvement). It builds the formal review-cycle
mechanics (self/manager/peer/upward review instances, per-competency ratings, calibration
fields) and **references** 3.18's `GoalPeriod`/`Objective`/`KeyResult` for the goal-review
section instead of duplicating any OKR field. 4 new models, all appended to
`apps/hrm/models.py`, migration `0033` (last is
`0032_objective_hrm_obj_tenant_department_idx.py`). No core-spine table is added — reviews FK
`hrm.EmployeeProfile` (subject/reviewer, never `core.Party`/`accounts.User` directly) and
`hrm.GoalPeriod`/`hrm.Objective` (goal-review section, reused exactly as already built).
Manager-review reviewer resolution uses the **derived** `EmployeeProfile.manager` property
(`self.employment.manager` -> a `core.Party`) — no new manager FK anywhere in this module.

NavERP.md 3.19 bullets (exact text, all 5 go Live this pass):
- Review Cycles — Annual, half-yearly, quarterly reviews.
- Self-Assessment — Employee self-evaluation forms.
- Manager Review — Manager feedback, ratings.
- 360° Feedback — Multi-rater feedback, peer review.
- Calibration — Rating normalization, bell curve.

Reuses (no duplication): `hrm.EmployeeProfile` (review `subject`/`reviewer`/`acknowledged_by` —
never `core.Party`/`settings.AUTH_USER_MODEL` directly), `EmployeeProfile.manager` (derived
`@property` off `core.Employment.manager`, a `core.Party` — used to validate/pre-fill the
manager-review `reviewer`, never a new FK), `hrm.GoalPeriod` (`ReviewCycle.goal_period`,
nullable FK — aligns a review cycle to the same quarter/year as the OKR period),
`hrm.Objective`/`hrm.KeyResult` (the review detail's goal-review section reads
`Objective.objects.filter(owner=subject, goal_period=cycle.goal_period)` live — no goal fields
copied onto any 3.19 model). **No new core-spine entity, posts no GL.**

**Grounding decisions carried over from research (decide, don't re-litigate at build time):**
- `ReviewCycle` follows `GoalPeriod`'s `TenantOwned` (not `TenantNumbered`) pattern — same
  "named catalog, not numbered" shape, same `PERIOD_TYPE_CHOICES`-analog (`cycle_type`) idea.
- `ReviewTemplate`/`PerformanceReview`/`ReviewRating` all extend `TenantNumbered` with prefixes
  `RVT-`/`RVW-`/`RVR-` — none of the 42 prefixes already in `apps/hrm/models.py` (the 39 from
  research + `OBJ`/`KR`/`GCI` added in 3.18) collide (confirmed by grep — no `RVT`/`RVW`/`RVR`
  hits anywhere in the codebase).
- Competencies are a denormalized `criterion_label`/`criterion_category` pair directly on
  `ReviewRating`, not a 5th `ReviewCriterion` catalog model — keeps this pass at 4 models per
  the research's explicit scope decision; a shared competency library is a natural v2 extract.
- `overall_rating` is a **derived `@property`** (weighted mean of the review's `ReviewRating`
  rows by `weight`) — mirrors the 3.18 `Objective.progress_pct` pattern exactly (`_ratings()`
  cached method + guard empty/zero-weight rows), never a stored, hand-editable field.
  `manager_rating` (the as-submitted snapshot) and `calibrated_rating` (the post-calibration
  override) ARE stored fields, distinct from the derived `overall_rating`, per Workday's
  documented two-field distinction.
- Calibration stays **field-based on `PerformanceReview`** this pass
  (`manager_rating`/`calibrated_rating`/`calibration_notes`) — no dedicated
  `CalibrationSession` grouping table; a calibration **board view** (not a new model) lists a
  cycle's manager-reviews sorted/grouped for on-screen adjustment.
- `potential_rating` is a cheap nullable field on `PerformanceReview` for 9-box groundwork —
  the 9-box grid/visualization itself is explicitly deferred (a later report, not this pass).
- Self-review is simply a `PerformanceReview` row with `review_type="self"` and
  `subject_id == reviewer_id` — no special-cased self-review table.
- Peer/360/upward are also just `PerformanceReview` rows (`review_type` in
  `peer`/`upward`/`skip_level`) with `reviewer_id != subject_id` — multiple peer rows per
  subject+cycle is just multiple rows, no separate "participant roster" table.

## A. Models + migration (`apps/hrm/models.py`, appended after `GoalCheckIn`)

- [ ] `ReviewCycle(TenantOwned)` [no `NUMBER_PREFIX` — small per-tenant catalog identified by
      `name`, same pattern as `GoalPeriod`/`JobGrade`] — the named review-cycle container +
      phase machine (drivers: 3.19.1 Review Cycles — 15Five's "cycle = participants + review
      types + timeline", Culture Amp's phased unified cycle, BambooHR/Lattice goal-integration):
  - [ ] `name` — CharField(max_length=100) — e.g. "H1 2026 Performance Review"
  - [ ] `cycle_type` — CharField(max_length=15, choices=`CYCLE_TYPE_CHOICES`, default="annual")
        — `[("annual","Annual"),("half_yearly","Half-Yearly"),("quarterly","Quarterly"),
        ("custom","Custom")]` — driver: 3.19.1 bullet text verbatim ("Annual, half-yearly,
        quarterly reviews")
  - [ ] `status` — CharField(max_length=20, choices=`STATUS_CHOICES`, default="draft") — the
        **phase machine**: `[("draft","Draft"),("self_assessment","Self-Assessment"),
        ("manager_review","Manager Review"),("calibration","Calibration"),
        ("released","Results Released"),("closed","Closed")]` — driver: Culture Amp's phased
        unified cycle, Workday's staged roll-up; each phase gates which `PerformanceReview`
        actions are open (e.g. self-review submission only during `self_assessment`+)
  - [ ] `self_review_start` / `self_review_end` — DateField(null=True, blank=True) — the
        self-assessment window (3.19.2)
  - [ ] `manager_review_start` / `manager_review_end` — DateField(null=True, blank=True) — the
        manager-review window (3.19.3)
  - [ ] `calibration_date` — DateField(null=True, blank=True) — single target date (simpler
        than a start/end window — calibration is typically a session, not a multi-week period,
        per SAP SuccessFactors/Betterworks framing)
  - [ ] `results_release_date` — DateField(null=True, blank=True) — when `overall_rating`/
        `calibrated_rating` become visible to the subject (3.19.5 groundwork —
        acknowledgment can't happen before release)
  - [ ] `goal_period` — `models.ForeignKey("hrm.GoalPeriod", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="review_cycles")` — driver: 3.19.2 goal/OKR
        self-reflection section (BambooHR/Lattice/PerformYard goal-integration) — **reuses
        `hrm.GoalPeriod`**, no duplicate period fields
  - [ ] `description` — TextField(blank=True)
  - [ ] `class Meta`: `ordering = ["-self_review_start", "name"]`;
        `unique_together = ("tenant", "name")`; index
        `models.Index(fields=["tenant", "status"], name="hrm_rc_tenant_status_idx")`
  - [ ] `clean()` — raise `ValidationError({"self_review_end": "..."})` if
        `self_review_end <= self_review_start` (when both set); same guard for
        `manager_review_end <= manager_review_start`; raise
        `ValidationError({"manager_review_start": "..."})` if
        `manager_review_start < self_review_end` (manager phase shouldn't start before
        self-assessment closes, when both windows are set)
  - [ ] derived **@property** `review_count` → `self.reviews.count()`
  - [ ] derived **@property** `PHASE_ORDER` class-level tuple
        `("draft","self_assessment","manager_review","calibration","released","closed")` used
        by the `reviewcycle_advance_phase` view to compute the next status (no magic-string
        phase math duplicated in the view)
  - [ ] `__str__` → `f"{self.name} ({self.get_cycle_type_display()})"`

- [ ] `ReviewTemplate(TenantNumbered, NUMBER_PREFIX="RVT")` — the review-form definition
      (drivers: 3.19.3 Manager Review per-competency ratings, 3.19.4 360° per-participant-type
      forms):
  - [ ] `name` — CharField(max_length=150)
  - [ ] `review_type` — CharField(max_length=15, choices=`REVIEW_TYPE_CHOICES`, default="self")
        — `[("self","Self"),("manager","Manager"),("peer","Peer"),("upward","Upward"),
        ("skip_level","Skip-Level")]` — driver: 3.19.4 (PerformYard's "form differs by review
        type" — a cycle can attach multiple templates, one per participant type)
  - [ ] `rating_scale_max` — PositiveSmallIntegerField(default=5,
        validators=[MinValueValidator(2), MaxValueValidator(10)]) — driver: 3.19.3 "Overall
        rating on a configurable scale" (5-point is the de-facto standard across all 10
        surveyed products)
  - [ ] `include_goals` — BooleanField(default=False) — whether this template's review form
        pulls the subject's `Objective`/`KeyResult` progress into a goal-review section, driver:
        3.19.2 goal/OKR self-reflection (BambooHR/Lattice/PerformYard)
  - [ ] `is_anonymous` — BooleanField(default=False) — per-template default anonymity (peer/360
        rows commonly default True, self/manager default False) — driver: 3.19.4 (Trakstar's
        "anonymous or named per relationship"); overridable per-review via
        `PerformanceReview.is_anonymous`
  - [ ] `description` — TextField(blank=True) — instructions shown to the reviewer
  - [ ] `is_active` — BooleanField(default=True)
  - [ ] `class Meta`: `ordering = ["review_type", "name"]`;
        `unique_together = ("tenant", "number")`; indexes
        `models.Index(fields=["tenant", "review_type"], name="hrm_rvt_tenant_type_idx")`,
        `models.Index(fields=["tenant", "is_active"], name="hrm_rvt_tenant_active_idx")`
  - [ ] derived **@property** `usage_count` → `self.reviews.count()` (guards delete —
        expose in the delete-confirmation template so an admin can't silently orphan
        historical reviews' template reference)
  - [ ] `__str__` → `f"{self.number} · {self.name} ({self.get_review_type_display()})"`

- [ ] `PerformanceReview(TenantNumbered, NUMBER_PREFIX="RVW")` — the per-instance review row,
      one per (cycle, subject, reviewer) combination (drivers: 3.19.2 Self-Assessment, 3.19.3
      Manager Review, 3.19.4 360° Feedback, 3.19.5 Calibration):
  - [ ] `cycle` — `models.ForeignKey("hrm.ReviewCycle", on_delete=models.PROTECT,
        related_name="reviews")` — PROTECT so a cycle can't be deleted out from under its
        historical reviews
  - [ ] `template` — `models.ForeignKey("hrm.ReviewTemplate", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="reviews")` — SET_NULL (not PROTECT) so a template
        can be retired/deleted later without blocking, per research's `usage_count` note
  - [ ] `subject` — `models.ForeignKey("hrm.EmployeeProfile", on_delete=models.PROTECT,
        related_name="reviews_received")` — the employee being reviewed; PROTECT matches
        `Objective.owner`'s convention
  - [ ] `reviewer` — `models.ForeignKey("hrm.EmployeeProfile", on_delete=models.PROTECT,
        related_name="reviews_authored")` — who fills it in; **equals `subject` for
        `review_type="self"`** (enforced in `clean()`, not by a DB constraint, since Django
        can't express "FK_A == FK_B conditionally" declaratively)
  - [ ] `review_type` — CharField(max_length=15, choices=`REVIEW_TYPE_CHOICES` — same 5 values
        as `ReviewTemplate.REVIEW_TYPE_CHOICES` (`self`/`manager`/`peer`/`upward`/
        `skip_level`), default="self") — copied from `template.review_type` at creation for
        query convenience (denormalized-for-query, mirrors `Objective.scope` per research)
  - [ ] `status` — CharField(max_length=15, choices=`STATUS_CHOICES`, default="draft") —
        `[("draft","Draft"),("submitted","Submitted"),("shared","Shared"),
        ("acknowledged","Acknowledged")]` — the review workflow gate (3.19.3's "draft ->
        submitted -> shared-with-employee -> acknowledged")
  - [ ] `overall_rating` is **NOT a stored field** — it is a derived `@property` (see below);
        do not add an editable `overall_rating` DB column
  - [ ] `manager_rating` — DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
        — the as-submitted pre-calibration snapshot, meaningful only when
        `review_type="manager"`; distinct from the derived `overall_rating` for audit, per
        Workday's explicit two-field pattern
  - [ ] `calibrated_rating` — DecimalField(max_digits=4, decimal_places=2, null=True,
        blank=True) — set during the calibration phase, overrides `manager_rating` downstream
        (comp/promotion decisions read this field, not `manager_rating`), per Workday/SAP
        SuccessFactors
  - [ ] `potential_rating` — DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
        — cheap 9-box groundwork (15Five's Talent Matrix, Workday's flagship calibration axis);
        visualization deferred
  - [ ] `strengths` — TextField(blank=True) — near-universal free-text section
  - [ ] `improvements` — TextField(blank=True) — near-universal free-text section (matches the
        prompt's field name; maps to the research's `areas_for_improvement`)
  - [ ] `private_notes` — TextField(blank=True) — manager-only, NEVER rendered on the
        subject-facing detail view (gate this in the view/template, not the model — mirrors how
        `EmployeeProfile.bank_account` is gated via `masked_*()` helpers, but here it's a full
        field visibility gate rather than masking); driver: 15Five's Private Manager Assessment
  - [ ] `calibration_notes` — TextField(blank=True) — the adjustment rationale, per SAP
        SuccessFactors' Bin View audit trail
  - [ ] `is_anonymous` — BooleanField(default=False) — overridable from
        `template.is_anonymous` at creation; display logic masks `reviewer` on the
        subject-facing view when True and `review_type` in `peer`/`upward`
  - [ ] `submitted_at` — DateTimeField(null=True, blank=True, editable=False)
  - [ ] `shared_at` — DateTimeField(null=True, blank=True, editable=False)
  - [ ] `acknowledged_at` — DateTimeField(null=True, blank=True, editable=False)
  - [ ] `acknowledged_by` — `models.ForeignKey("hrm.EmployeeProfile", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="reviews_acknowledged", editable=False)` — normally
        equals `subject`, set from the view on `performancereview_acknowledge`
  - [ ] `class Meta`: `ordering = ["-cycle__self_review_start", "subject__party__name"]`;
        `unique_together = ("tenant", "number")`; indexes
        `models.Index(fields=["tenant", "cycle"], name="hrm_rvw_tenant_cycle_idx")`,
        `models.Index(fields=["tenant", "subject"], name="hrm_rvw_tenant_subject_idx")`,
        `models.Index(fields=["tenant", "reviewer"], name="hrm_rvw_tenant_reviewer_idx")`,
        `models.Index(fields=["tenant", "review_type"], name="hrm_rvw_tenant_type_idx")`,
        `models.Index(fields=["tenant", "status"], name="hrm_rvw_tenant_status_idx")`
  - [ ] `clean()` — raise `ValidationError({"reviewer": "..."})` if `review_type == "self"` and
        `reviewer_id != subject_id`; raise `ValidationError({"reviewer": "..."})` if
        `review_type != "self"` and `reviewer_id == subject_id` (a non-self review can't have
        the subject reviewing themselves); raise
        `ValidationError({"manager_rating": "..."})` if `manager_rating` is set on a
        `review_type != "manager"` row (keeps the field meaningfully scoped)
  - [ ] `_ratings()` **method** — `self.ratings.all()`, cached per instance (mirrors
        `Objective._krs()` exactly — avoids re-querying across `overall_rating` and any
        detail-page rendering of the same ratings queryset)
  - [ ] derived **@property** `overall_rating` → weighted average of
        `r.rating_value * r.weight` over `self._ratings()`, normalized by
        `sum(r.weight for r in self._ratings())` (falls back to a simple average if all
        weights are 0); returns `None` if no ratings exist yet (distinct from `Decimal("0")`
        — an unrated review shouldn't display as "0/5", it should display "Not yet rated") —
        mirrors `Objective.progress_pct` but with a `None`-vs-`ZERO` distinction since a rating
        of 0 is a valid low score, unlike a progress percentage
  - [ ] derived **@property** `rating_count` → `len(self._ratings())`
  - [ ] derived **@property** `effective_rating` → `self.calibrated_rating` if not None, else
        `self.overall_rating` — the single field every downstream consumer (comp, promotion
        reports) should read, per Workday's documented pattern of calibrated overriding manager
      - [ ] derived **@property** `goal_period` → `self.cycle.goal_period` (convenience
        passthrough so the detail view/template doesn't need `obj.cycle.goal_period` chained
        lookups everywhere)
  - [ ] `__str__` → `f"{self.number} · {self.subject.party.name} ({self.get_review_type_display()})"`

- [ ] `ReviewRating(TenantNumbered, NUMBER_PREFIX="RVR")` — per-competency/question rating line
      under a review (drivers: 3.19.3 per-competency ratings with comments, 3.19.4 same-shape
      reuse across all review_types):
  - [ ] `review` — `models.ForeignKey("hrm.PerformanceReview", on_delete=models.CASCADE,
        related_name="ratings")`
  - [ ] `criterion_label` — CharField(max_length=255) — the competency/question text (kept as
        a label rather than a 5th `ReviewCriterion` FK model this pass, per research's Deferred
        note)
  - [ ] `criterion_category` — CharField(max_length=15, choices=`CATEGORY_CHOICES`,
        default="competency") — `[("competency","Competency"),("goal","Goal"),
        ("value","Company Value"),("custom","Custom")]` — folds 15Five's "Competency ratings /
        Company Values ratings / Objectives ratings" distinction into one field, same pattern
        as `KeyResult.metric_type`
  - [ ] `rating_value` — DecimalField(max_digits=4, decimal_places=2) — the per-criterion score,
        expected within `[0, review.template.rating_scale_max]` (validated in `clean()`, not a
        hardcoded `MaxValueValidator`, since the ceiling varies per template)
  - [ ] `weight` — DecimalField(max_digits=5, decimal_places=2, default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)]) — directly mirrors the
        already-built `Objective.weight`/`KeyResult.weight` pattern so
        `PerformanceReview.overall_rating` derives as a weighted mean instead of a
        manually-typed duplicate; form should default new rows to an equal split among
        existing siblings under the same review (mirrors `KeyResult.weight`'s
        `100 / (existing_sibling_count + 1)` default)
  - [ ] `comment` — TextField(blank=True)
  - [ ] `class Meta`: `ordering = ["review", "-weight", "criterion_label"]`;
        `unique_together = ("tenant", "number")`; index
        `models.Index(fields=["tenant", "review"], name="hrm_rvr_tenant_review_idx")`
  - [ ] `clean()` — raise `ValidationError({"rating_value": "..."})` if `rating_value` is
        negative or (when `self.review_id` and `self.review.template_id`) exceeds
        `self.review.template.rating_scale_max`; raise `ValidationError({"weight": "..."})` if
        `weight` is negative (validators already block this at the field level but keep the
        model-level guard for bulk/fixture writes that skip `full_clean()`, matching
        `KeyResult.clean()`'s exact rationale)
  - [ ] `__str__` → `f"{self.number} · {self.criterion_label} ({self.rating_value})"`

- [ ] one incremental migration
      `apps/hrm/migrations/0033_reviewcycle_reviewtemplate_performancereview_and_more.py`
      (NOT `0001_initial`; last is `0032_objective_hrm_obj_tenant_department_idx.py`) —
      `makemigrations hrm`, review the generated file, adjust index/constraint names to match
      the ones specified above if Django's auto-names differ

## B. Forms (`apps/hrm/forms.py`)

- [ ] `ReviewCycleForm(ModelForm)` — `tenant=` kwarg accepted (consistent signature with every
      other HRM form); excludes `tenant`/`status` (status is **workflow-only**, changed via the
      phase-advance action, never directly editable on the form — mirrors the 3.18 lesson where
      `GoalPeriodForm` originally leaked `status` and let a non-admin bypass the
      activate/close gate; do NOT repeat that mistake here); scopes `goal_period` to
      `GoalPeriod.objects.filter(tenant=tenant)`; fields = `name, cycle_type,
      self_review_start, self_review_end, manager_review_start, manager_review_end,
      calibration_date, results_release_date, goal_period, description`
- [ ] `ReviewTemplateForm(ModelForm)` — `tenant=` kwarg; excludes `tenant`/`number`; fields =
      `name, review_type, rating_scale_max, include_goals, is_anonymous, description,
      is_active`
- [ ] `PerformanceReviewForm(ModelForm)` — `tenant=` kwarg; excludes
      `tenant`/`number`/`status`/`manager_rating`/`calibrated_rating`/`potential_rating`/
      `calibration_notes`/`submitted_at`/`shared_at`/`acknowledged_at`/`acknowledged_by`
      (all workflow/calibration-only — set via dedicated actions, never on the create/edit
      form); scopes `cycle` to `ReviewCycle.objects.filter(tenant=tenant)`, `template` to
      `ReviewTemplate.objects.filter(tenant=tenant, is_active=True)`, `subject`/`reviewer` to
      `EmployeeProfile.objects.filter(tenant=tenant).select_related("party")`; fields = `cycle,
      template, subject, reviewer, review_type, strengths, improvements, private_notes,
      is_anonymous`
- [ ] `CalibrationForm(ModelForm)` — a **separate, narrow** form used only by the calibration
      action — `tenant=` kwarg (unused, kept for signature consistency); Meta `model =
      PerformanceReview`; fields = `calibrated_rating, calibration_notes` ONLY (this is the
      privileged-action form the research/prompt calls for — editing `calibrated_rating`
      must never be reachable via the general edit form)
- [ ] `ReviewRatingForm(ModelForm)` — `tenant=` kwarg; excludes `tenant`/`number`/`review`
      (review is set from the URL in the create view, matching `KeyResultForm`'s
      parent-scoped child-create pattern); fields = `criterion_label, criterion_category,
      rating_value, weight, comment`

## C. Views (`apps/hrm/views.py`) — full CRUD + custom actions, function-based,
      `@login_required` (privileged transitions `@tenant_admin_required`), tenant-scoped via
      `crud_list/crud_create/crud_edit/crud_detail/crud_delete`

- [ ] `reviewcycle_list` — `crud_list`; `search_fields=("name",)`; `filters=[("status",
      "status", False), ("cycle_type", "cycle_type", False)]`; pass
      `status_choices=ReviewCycle.STATUS_CHOICES`,
      `cycle_type_choices=ReviewCycle.CYCLE_TYPE_CHOICES` in `extra_context` (Filter
      Implementation Rule)
- [ ] `reviewcycle_create` / `reviewcycle_edit` / `reviewcycle_detail` / `reviewcycle_delete` —
      standard `crud_create/crud_edit/crud_detail/crud_delete`; `reviewcycle_detail`
      extra_context includes `review_count`, the cycle's reviews grouped by `review_type`
      (`select_related("subject__party", "reviewer__party", "template")`), and a per-phase
      progress summary (counts of draft/submitted/shared/acknowledged reviews) — 3.19.1
- [ ] `reviewcycle_advance_phase` (`@tenant_admin_required`, POST-only) — advances `status` to
      the next value in `ReviewCycle.PHASE_ORDER`; guards against skipping (only allow
      advancing exactly one step) and against advancing past `"closed"`; on transition INTO
      `"released"`, do NOT auto-share every review (an explicit per-review `share` action stays
      the single write path) — 3.19.1 cycle phase machine
- [ ] `reviewcycle_release` (`@tenant_admin_required`, POST-only) — convenience action that
      sets `status="released"` directly (equivalent to calling `reviewcycle_advance_phase`
      until released) IF the research/prompt's "release" action is kept distinct from generic
      phase-advance — decide at build time whether this is a separate view or folds into
      `reviewcycle_advance_phase`; either way, gate behind `@tenant_admin_required`
- [ ] `reviewtemplate_list` — `crud_list`; `search_fields=("name", "number")`;
      `filters=[("review_type", "review_type", False), ("is_active", "is_active", False)]`;
      pass `review_type_choices=ReviewTemplate.REVIEW_TYPE_CHOICES` in `extra_context`
- [ ] `reviewtemplate_create` / `reviewtemplate_edit` / `reviewtemplate_detail` /
      `reviewtemplate_delete` — standard; `reviewtemplate_detail` extra_context includes
      `usage_count` (guard messaging if non-zero, informational only — SET_NULL means delete
      still succeeds, but warn the admin)
- [ ] `performancereview_list` — `crud_list`; `search_fields=("number", "subject__party__name",
      "reviewer__party__name")`; `filters=[("cycle", "cycle_id", True), ("review_type",
      "review_type", False), ("status", "status", False), ("subject", "subject_id", True),
      ("reviewer", "reviewer_id", True)]`; pass `cycle_choices=
      ReviewCycle.objects.filter(tenant=request.tenant)`,
      `review_type_choices=PerformanceReview.REVIEW_TYPE_CHOICES`,
      `status_choices=PerformanceReview.STATUS_CHOICES`,
      `employees=EmployeeProfile.objects.filter(tenant=request.tenant).select_related("party")`
      in `extra_context`; `select_related("cycle", "template", "subject__party",
      "reviewer__party")`; support `?mine=1` (reviews authored by or about the logged-in
      user's linked `EmployeeProfile`, mirrors `objective_list`'s `_current_employee_profile`
      helper) — serves 3.19.2 (`?review_type=self`), 3.19.3 (`?review_type=manager`), 3.19.4
      (unfiltered or `?review_type=peer`/`upward`)
- [ ] `performancereview_create` / `performancereview_edit` / `performancereview_delete` —
      standard `crud_create/crud_edit/crud_delete`; on `crud_create`, after `form.save()`,
      copy `review_type` from `template.review_type` if a template was selected (view-level
      denormalization, not left to the form)
- [ ] `performancereview_detail` — `crud_detail`; extra_context includes `ratings=
      obj.ratings.all()` (for the inline rating table + add-inline form), `overall_rating`/
      `effective_rating`/`rating_count` (already properties — template reads them off `obj`),
      the subject's `Objective` set for the goal-review section (only when
      `obj.template.include_goals` is True) via
      `Objective.objects.filter(owner=obj.subject, goal_period=obj.goal_period)` (guard
      `obj.goal_period is None` -> empty queryset, no error) — 3.19.2 goal/OKR self-reflection
      section; gate `private_notes` rendering to reviewer/admin only (never shown when the
      requesting user's `EmployeeProfile == obj.subject` and `request.user` is not a tenant
      admin) — 3.19.3 Private Manager Assessment
- [ ] `performancereview_submit` (`@login_required`, POST-only, reviewer-or-admin only — guard
      `request.user`'s linked `EmployeeProfile == obj.reviewer` OR tenant-admin) — sets
      `status="submitted"`, `submitted_at=timezone.now()`; guard: only from `status="draft"`
      — 3.19.3 workflow states
- [ ] `performancereview_share` (`@tenant_admin_required`, POST-only) — sets
      `status="shared"`, `shared_at=timezone.now()`; guard: only from `status="submitted"`
      — makes the review visible to the subject (gates `private_notes` still apply)
- [ ] `performancereview_acknowledge` (`@login_required`, POST-only, subject-only guard —
      `request.user`'s linked `EmployeeProfile == obj.subject`) — sets
      `status="acknowledged"`, `acknowledged_at=timezone.now()`,
      `acknowledged_by=that_profile`; guard: only from `status="shared"` — 3.19.3 employee
      acknowledgment/e-signature
- [ ] `performancereview_calibrate` (`@tenant_admin_required`, GET shows `CalibrationForm`
      pre-filled with `manager_rating`/`overall_rating` as reference, POST saves
      `calibrated_rating`/`calibration_notes` only) — the ONLY write path to
      `calibrated_rating` — 3.19.5 Calibration
- [ ] `calibration_board` (`@tenant_admin_required`) — a **report-style view, not a CRUD
      view** — given `?cycle=<id>`, lists that cycle's `review_type="manager"` reviews
      (`select_related("subject__party", "subject__employment__org_unit")`) sorted by
      `effective_rating`/department for side-by-side calibration adjustment (SAP
      SuccessFactors Bin View / Stack Ranker, Culture Amp Calibration Views — no new model,
      pure aggregation over existing fields); each row links to
      `performancereview_calibrate` for the actual edit — 3.19.5
- [ ] `reviewrating_create` (nested under a review: `<int:review_pk>/ratings/add/`) — fetches
      the parent `PerformanceReview` (`tenant=request.tenant` guard), sets `review=review`
      before save, defaults `weight` to an equal split among existing sibling ratings
      (`100 / (sibling_count + 1)`) in the form's initial value — 3.19.3/3.19.4
- [ ] `reviewrating_edit` / `reviewrating_detail` / `reviewrating_delete` — standard;
      `success_url` redirects back to the parent `performancereview_detail`, not a standalone
      ratings list page (ratings are always viewed in the context of their review — no
      navigational `reviewrating_list` needed, though the URL/view exists for completeness)
- [ ] all list views pass `q` search + pagination automatically via `crud_list`; no manual
      `Paginator`/`Q()` code duplicated per view (Filter Implementation Rule + CRUD
      Completeness Rule)

## D. URLs (`apps/hrm/urls.py`, `app_name = "hrm"`, append to the existing `urlpatterns`)

- [ ] `review-cycles/` -> `reviewcycle_list`; `review-cycles/add/` -> `reviewcycle_create`;
      `review-cycles/<int:pk>/` -> `reviewcycle_detail`; `review-cycles/<int:pk>/edit/` ->
      `reviewcycle_edit`; `review-cycles/<int:pk>/delete/` -> `reviewcycle_delete`;
      `review-cycles/<int:pk>/advance/` -> `reviewcycle_advance_phase`;
      `review-cycles/<int:pk>/release/` -> `reviewcycle_release` (if kept distinct)
- [ ] `review-templates/` -> `reviewtemplate_list`; `review-templates/add/` ->
      `reviewtemplate_create`; `review-templates/<int:pk>/` -> `reviewtemplate_detail`;
      `review-templates/<int:pk>/edit/` -> `reviewtemplate_edit`;
      `review-templates/<int:pk>/delete/` -> `reviewtemplate_delete`
- [ ] `reviews/` -> `performancereview_list`; `reviews/add/` -> `performancereview_create`;
      `reviews/<int:pk>/` -> `performancereview_detail`; `reviews/<int:pk>/edit/` ->
      `performancereview_edit`; `reviews/<int:pk>/delete/` -> `performancereview_delete`;
      `reviews/<int:pk>/submit/` -> `performancereview_submit`; `reviews/<int:pk>/share/` ->
      `performancereview_share`; `reviews/<int:pk>/acknowledge/` ->
      `performancereview_acknowledge`; `reviews/<int:pk>/calibrate/` ->
      `performancereview_calibrate`
- [ ] `reviews/<int:review_pk>/ratings/add/` -> `reviewrating_create`; `ratings/<int:pk>/` ->
      `reviewrating_detail`; `ratings/<int:pk>/edit/` -> `reviewrating_edit`;
      `ratings/<int:pk>/delete/` -> `reviewrating_delete`
- [ ] `calibration/` -> `calibration_board` (accepts `?cycle=<id>` query param)
- [ ] verify every new `path()` name is unique against the ~185 existing `hrm:` names (`grep
      name=` in `apps/hrm/urls.py` before adding — no accidental collision, especially with
      3.18's `objective_*`/`keyresult_*` names)

## E. Admin (`apps/hrm/admin.py`)

- [ ] register `ReviewCycle` — `list_display=("name", "cycle_type", "status",
      "self_review_start", "manager_review_start", "results_release_date", "tenant")`,
      `list_filter=("status", "cycle_type", "tenant")`, `search_fields=("name",)`,
      `autocomplete_fields=("goal_period",)`
- [ ] register `ReviewTemplate` — `list_display=("number", "name", "review_type",
      "rating_scale_max", "is_active", "tenant")`, `list_filter=("review_type", "is_active",
      "tenant")`, `search_fields=("number", "name")`
- [ ] register `PerformanceReview` — `list_display=("number", "subject", "reviewer",
      "review_type", "cycle", "status", "tenant")`, `list_filter=("review_type", "status",
      "tenant")`, `search_fields=("number", "subject__party__name",
      "reviewer__party__name")`, `autocomplete_fields=("cycle", "template", "subject",
      "reviewer", "acknowledged_by")`
- [ ] register `ReviewRating` — `list_display=("number", "review", "criterion_label",
      "criterion_category", "rating_value", "weight", "tenant")`,
      `list_filter=("criterion_category", "tenant")`, `search_fields=("number",
      "criterion_label")`, `autocomplete_fields=("review",)`

## F. Seed (`apps/hrm/management/commands/seed_hrm.py`) — extend the existing per-tenant loop,
      idempotent (skip-if-exists check per model, same pattern as every prior HRM extension)

- [ ] guard: `if ReviewCycle.objects.filter(tenant=tenant).exists(): skip this block, print
      notice` (do NOT wrap the whole command's idempotency in this — only this section)
- [ ] reuse the existing `EmployeeProfile.objects.filter(tenant=tenant).select_related("party")`
      queryset (no new employee rows) and the **active** `GoalPeriod` already seeded by 3.18
      (`GoalPeriod.objects.filter(tenant=tenant, status="active").first()`) — do NOT create a
      second GoalPeriod for this seeder
- [ ] seed 1 `ReviewCycle` per tenant: `cycle_type="half_yearly"`, `status="manager_review"`
      (mid-phase, so both self and manager reviews have data), `goal_period=` the active
      GoalPeriod found above, sensible `self_review_start/end`/`manager_review_start/end`
      dates bracketing "now", `results_release_date` in the future
- [ ] seed 2-3 `ReviewTemplate` rows per tenant: at minimum one `review_type="self"`
      (`rating_scale_max=5`, `include_goals=True`), one `review_type="manager"`
      (`rating_scale_max=5`, `include_goals=True`), one `review_type="peer"`
      (`rating_scale_max=5`, `is_anonymous=True`) — demonstrates the per-participant-type
      template differentiation (3.19.4)
- [ ] seed a handful of `PerformanceReview` rows across `self`/`manager`/`peer` for 3-5
      employees (reuse the same manager/direct-report pair 3.18 resolved via `.manager`, if
      still available, so the manager-review reviewer resolution has real data): at least one
      `self` review (`subject==reviewer`) with `status="submitted"`, at least one `manager`
      review with `status="shared"` and `manager_rating` set, at least one `manager` review
      with `status="acknowledged"` (`acknowledged_at`/`acknowledged_by` populated) AND
      `calibrated_rating` set (different from `manager_rating`, demonstrating the calibration
      override), at least one `peer` review with `is_anonymous=True` — varied statuses so the
      list filters + calibration board have real data to show immediately after seeding
- [ ] seed 2-4 `ReviewRating` rows per `PerformanceReview` with varied `criterion_category`
      (at least one `competency`, one `goal` when `template.include_goals`), `rating_value`s
      that produce a sensible derived `overall_rating` (not all identical — show a spread),
      weights summing sensibly (e.g. equal-split or 40/40/20) — exercises the weighted-mean
      `overall_rating` property immediately after seeding; confirm at least one review's
      `effective_rating` differs from its `overall_rating` (the calibrated-override case)
- [ ] idempotent re-run check: run `seed_hrm` a 2nd time with no `--flush`, confirm no
      duplicate `ReviewCycle`/`ReviewTemplate`/`PerformanceReview`/`ReviewRating` rows are
      created (the per-model `.exists()` guard added above handles this — verify at Verify
      step, not just by inspection)

## G. Wire-up

- [ ] `config/settings.py` — no change needed (`apps.hrm` already in `INSTALLED_APPS`)
- [ ] `config/urls.py` — no change needed (`hrm/` include already wired from 3.1)
- [ ] `apps/core/navigation.py` `LIVE_LINKS["3.19"]` — new entry mapping all 5 NavERP.md
      bullets (exact bullet text, confirm no other sub-module already claims these 5 strings
      under a different key — they're new for 3.19 per NavERP.md):
  ```python
  # 3.19 Performance Review — second Performance-Management sub-module (formal review-cycle
  # mechanics; continuous feedback/kudos/1:1s are 3.20, PIP/coaching is 3.21). ReviewCycle
  # serves Review Cycles; performancereview_list filtered by review_type serves
  # Self-Assessment/Manager Review; the unfiltered list (all review_types incl. peer/upward)
  # serves 360° Feedback; calibration_board serves Calibration.
  "3.19": {
      "Review Cycles": "hrm:reviewcycle_list",                              # bullet (cycle catalog + phase machine)
      "Self-Assessment": "hrm:performancereview_list?review_type=self",     # bullet (self review_type slice)
      "Manager Review": "hrm:performancereview_list?review_type=manager",   # bullet (manager review_type slice)
      "360° Feedback": "hrm:performancereview_list",                        # bullet (all types incl. peer/upward)
      "Calibration": "hrm:calibration_board",                               # bullet (calibration board)
  },
  ```

## H. Templates (`templates/hrm/performance/<entity>/{list,detail,form}.html`) — REUSE the
      existing `performance/` sub-module folder from 3.18 (goalperiod/objective/keyresult/
      goalcheckin already live there); add reviewcycle/, reviewtemplate/,
      performancereview/, reviewrating/ alongside them (per Template Folder Structure Rule 2 —
      one folder per entity within the shared sub-module folder)

- [ ] `performance/reviewcycle/list.html` — filter bar (`status`, `cycle_type` dropdowns
      reflecting `request.GET`), Actions column (view/edit/delete + Advance-Phase button
      conditional on `obj.status != "closed"`), empty-state, pagination
- [ ] `performance/reviewcycle/detail.html` — shows `review_count`, the phase-progress summary
      (draft/submitted/shared/acknowledged counts), a status/phase badge, the cycle's reviews
      grouped by `review_type`, Actions sidebar (Edit/Delete conditional on `status ==
      "draft"`, Advance-Phase/Release workflow buttons, Back to List)
- [ ] `performance/reviewcycle/form.html` — create/edit, shared template (`is_edit` flag); NO
      `status` field on the form (workflow-only, per the `ReviewCycleForm` lesson-learned note
      above)
- [ ] `performance/reviewtemplate/list.html` — filter bar (`review_type`, `is_active`
      dropdowns), Actions column, empty-state, pagination
- [ ] `performance/reviewtemplate/detail.html` — shows `rating_scale_max`, `include_goals`/
      `is_anonymous` badges, `usage_count`, Actions sidebar (Edit/Delete with a usage-count
      warning, Back to List)
- [ ] `performance/reviewtemplate/form.html` — create/edit, shared template
- [ ] `performance/performancereview/list.html` — filter bar (`cycle`, `review_type`,
      `status`, `subject`, `reviewer` dropdowns + `?mine=1` toggle), Actions column
      (view/edit/delete conditional on `status == "draft"`, Submit button conditional on
      `status == "draft"` + reviewer/admin), empty-state, pagination — **CRITICAL**: pass
      every dropdown's options from the view context (Filter Implementation Rule 1), use
      `|stringformat:"d"` for the FK dropdowns' `selected` comparison (Rule 2)
- [ ] `performance/performancereview/detail.html` — header (subject/reviewer/cycle/
      review_type/status badge/`overall_rating` + `effective_rating` display, showing "Not
      yet rated" when `overall_rating is None`), Ratings table (inline, with an "Add Rating"
      button -> `reviewrating_create`), goal-review section (subject's Objectives for
      `cycle.goal_period`, rendered ONLY when `obj.template.include_goals`), `private_notes`
      panel gated to reviewer/admin only (never rendered when the viewer IS the subject and
      not a tenant admin), Actions sidebar (Submit/Share/Acknowledge/Calibrate workflow
      buttons each conditional on the review's current `status` + the viewer's role, Edit/
      Delete conditional on `status == "draft"`, Back to List)
- [ ] `performance/performancereview/form.html` — create/edit; `cycle`/`template`/`subject`/
      `reviewer` as searchable `<select>`s
- [ ] `performance/performancereview/calibrate.html` — the `CalibrationForm` (
      `calibrated_rating`/`calibration_notes` only), showing `manager_rating`/
      `overall_rating` as read-only reference values above the form fields
- [ ] `performance/calibration_board.html` — standalone report page (not a CRUD entity
      folder — a sub-module-root page per Template Folder Structure Rule 6): `?cycle=`
      selector dropdown, a sortable table of the selected cycle's manager reviews
      (subject/department/`manager_rating`/`overall_rating`/`calibrated_rating`/status), each
      row linking to `performancereview_calibrate`
- [ ] `performance/reviewrating/form.html` — create (nested under review, via `review_pk` in
      URL) + edit, shared template
- [ ] `performance/reviewrating/detail.html` — read-only, Actions sidebar (Edit/Delete, Back
      to Review)
- [ ] add a "Performance Review" card/section to the existing HRM overview page (mirrors how
      3.18 Goal Setting surfaced itself) pointing at `reviewcycle_list`

## I. Verify

- [ ] `python manage.py makemigrations hrm` — confirm exactly one new migration file numbered
      `0033`, review generated index/constraint names against section A's spec
- [ ] `python manage.py migrate` — applies cleanly with no errors
- [ ] `python manage.py seed_hrm` — run once, confirm ReviewCycle/ReviewTemplate/
      PerformanceReview/ReviewRating rows created per tenant, confirm login instructions
      print (tenant admin accounts, superuser warning)
- [ ] `python manage.py seed_hrm` — run a **2nd time**, confirm idempotent (no duplicate
      rows, "already exists" notice printed for this section)
- [ ] `python manage.py check` — no system check errors/warnings introduced
- [ ] `temp/` smoke sweep — every new `hrm:reviewcycle_*`/`hrm:reviewtemplate_*`/
      `hrm:performancereview_*`/`hrm:reviewrating_*`/`hrm:calibration_board` URL returns 200
      (GET) or 302 (POST redirect) when logged in as a tenant admin; confirm no
      `{#`/`{% comment %}` template-leak artifacts render; confirm a cross-tenant review/
      rating/cycle/template ID (belonging to a DIFFERENT tenant) returns 404 via
      `crud_detail`'s `tenant=request.tenant` guard (IDOR check)
- [ ] confirm the sidebar shows 3.19's 5 bullets as **Live** (not "On the roadmap") after the
      `LIVE_LINKS["3.19"]` wire-up, for a logged-in tenant admin
- [ ] confirm `PerformanceReview.overall_rating`/`effective_rating` render without raising on:
      a review with zero `ReviewRating` rows (returns `None`, template shows "Not yet rated"
      not a crash), a review where every rating has `weight=0` (falls back to simple mean, no
      divide-by-zero), a `ReviewCycle` with no `goal_period` set (goal-review section shows
      empty, not an AttributeError) — edge-case guard sweep matching the exact divide-by-zero/
      empty-queryset traps the 3.18 derived properties already defend against
- [ ] confirm the workflow gates hold: `performancereview_submit` rejects a non-`draft` review
      (redirects with an error message, doesn't silently no-op-succeed);
      `performancereview_calibrate` is unreachable by a non-tenant-admin (403, not a silent
      redirect); a subject viewing their own shared review never sees `private_notes` in the
      rendered HTML (view-source check, not just "the template has an `{% if %}`")

## J. Close-out

- [ ] `code-reviewer` agent — apply findings, one file per commit
- [ ] `explorer` agent — apply findings, one file per commit
- [ ] `frontend-reviewer` agent — apply findings, one file per commit
- [ ] `performance-reviewer` agent — apply findings (watch specifically for N+1 on
      `performancereview_list`'s `subject__party`/`reviewer__party`/`cycle`/`template` and on
      `performancereview_detail`'s inline `ratings` + goal-review `Objective` queryset — use
      `select_related`/`prefetch_related` from the start; watch `calibration_board` for an
      unbounded/unfiltered scan when no `?cycle=` is given, one file per commit
- [ ] `qa-smoke-tester` agent — apply findings, one file per commit
- [ ] `security-reviewer` agent — apply findings (watch specifically for: the cross-tenant
      IDOR check on nested create views — `reviewrating_create` fetches its parent
      `PerformanceReview` with an explicit `tenant=request.tenant` guard, not just `pk=`; the
      `private_notes` visibility gate actually excludes the field from the rendered response
      for a subject-viewer, not just hides it via CSS; `performancereview_calibrate` and
      `reviewcycle_advance_phase`/`reviewcycle_release` are genuinely gated by
      `@tenant_admin_required`, not just a template-level "hide the button" check), one file
      per commit
- [ ] `test-writer` agent — apply output, one file per commit
- [ ] create/update `.claude/skills/hrm/SKILL.md` — add the 4-model 3.19 table (ReviewCycle/
      ReviewTemplate/PerformanceReview/ReviewRating), the phase machine + review workflow +
      calibration flow, routes/templates/seeder/sidebar (`LIVE_LINKS["3.19"]`) notes, update
      the module's model count and built-sub-module list
- [ ] update the HRM README entry for 3.19 Performance Review (mirror the 3.18 README entry's
      shape and depth) + refresh HRM/project-wide test counts once `test-writer` lands

## Later passes / deferred (carried over from research-hrm-performance-review.md — do NOT
      build in 3.19)

- **Continuous feedback / kudos / praise / recognition** — belongs to 3.20 Continuous
  Feedback, not 3.19.
- **1:1 meeting scheduling/notes/action items** — belongs to 3.20 Continuous Feedback.
- **PIP / warning letters / coaching logs** — belongs to 3.21 Performance Improvement.
- **The goal/OKR mechanics themselves** (Objective/KeyResult/GoalCheckIn creation, weighting,
  cascading) — already built in 3.18; 3.19 only *references* `GoalPeriod`/`Objective`/
  `KeyResult` for the goal-review section, never duplicates their fields.
- **Dedicated `ReviewCriterion` / competency-catalog model** — this pass keeps competencies as
  a `criterion_label`/`criterion_category` pair directly on `ReviewRating` (denormalized per
  review, no shared catalog). If a tenant wants a reusable, editable company-wide competency
  library, extract `ReviewCriterion` as a 5th model in a later pass and FK
  `ReviewRating.criterion` to it instead of a free-text label.
- **Dedicated `CalibrationSession` grouping table** — this pass keeps calibration as fields
  (`manager_rating`/`calibrated_rating`/`calibration_notes`) on `PerformanceReview` plus the
  `calibration_board` report view. A later pass can add `CalibrationSession` (facilitator,
  group, meeting date, participants, sign-off) if formal session tracking/minutes are needed.
- **Rating-distribution / bell-curve enforcement, Stack Ranker view, 9-box visualization** —
  all buildable as reports/aggregations over the fields already captured
  (`calibrated_rating`, `potential_rating`) once this pass's 4 models exist; no new model
  required, `calibration_board` is the seed of the Stack Ranker idea but the bell-curve
  guideline/9-box grid itself is not built this pass.
- **Multi-level calibration roll-up / top-org sign-off chain** (Workday's mechanic) — a
  workflow-automation feature layered on top of the `EmployeeProfile.manager` chain;
  deferred as an integration-later item.
- **External/non-employee 360 reviewer** (Leapsome's "external reviews") — would require
  relaxing `reviewer` to accept a `core.Party` outside `EmployeeProfile`; deferred, not
  needed for internal-360 scope.
- **AI-drafted reviews, AI bias detection, AI auto-assignment to cycles, sentiment scoring**
  (Lattice, Betterworks, Engagedly, Synergita) — all require an LLM integration; out of a
  single Django pass.
- **Auto-launch / lifecycle-triggered cycles** (e.g. auto-start N days before a work
  anniversary) — would need a scheduling/cron mechanism; deferred.
- **Skip-level review as a distinct table** — not deferred as a *feature* (it's cheap — just
  another `review_type` choice value: `skip_level`), but noted here so the build doesn't
  over-scope trying to model it specially.

## Review notes
(filled in at the end)

---
# Module 3 — HRM — Sub-module 3.18 Goal Setting (goal-setting) — plan from research-hrm-goal-setting.md (2026-07-05)

## ✅ BUILD REVIEW (3.18 shipped — all 11 Module-Creation-Sequence steps done, 2026-07-05)

**Delivered:** 4 tenant-scoped models exactly as planned — `GoalPeriod` (cycle catalog, activate/close), `Objective`
(`OBJ-`, parent self-FK cascade + `core.OrgUnit` dept scope + weight + derived weighted `progress_pct`/pace
`health_status`), `KeyResult` (`KR-`, 5 metric types + weight + derived progress/health), `GoalCheckIn` (`GCI-`,
append-only log advancing `KeyResult.current_value`). Full CRUD via `crud_*` helpers, nested keyresult/goalcheckin
create, `goalperiod_activate/close` (`@tenant_admin_required`), `objective_tree` (3-level cascade), `?mine=1`
own+direct-reports view. 14 templates under `templates/hrm/performance/`, `LIVE_LINKS["3.18"]` (5 bullets live),
`_seed_goals` (active+closed period, 3-level cascade, 10 KRs tuned to a health spread, 19 check-ins; idempotent).
Migrations `0030`–`0032`. Reuses `EmployeeProfile` + `core.OrgUnit`; **no new core-spine entity, posts no GL**.

**Verified:** smoke sweep — every page 200/302, cross-tenant IDOR→404 (all 4 models), idempotent seed, derived
health spread correct (on_track 60% / at_risk 28% / off_track 15% / …). `manage.py check` clean.

**Review agents (all 7 run in order):** `code-reviewer` → fixed a **critical** authz bug (`GoalPeriodForm` exposed
`status`, letting a non-admin bypass the activate/close gate — dropped from the form) + added `unique_together
(tenant, number)` to the 3 numbered models + fixed a seeder `--flush` PROTECT-ordering regression (goals must wipe
before `EmployeeProfile` in the central flush loop) + capped `tree_max_depth` at 3. `explorer` → no wiring gaps.
`frontend-reviewer` → added `health_status_display` labels (was rendering raw `on_track`), made the All/My-team
toggle preserve filters via `{% querystring %}`, promoted `.tree-node`/`.tree-children` to RTL-safe theme classes.
`performance-reviewer` → added `goal_period` to the tree/child-objective `select_related` (killed a per-node N+1)
+ a `(tenant, department)` composite index. `qa-smoke-tester` → 15/15 routes green, no changes. `security-reviewer`
→ no vulnerabilities. `test-writer` → **204 tests** (74 models + 87 views + 51 security), all green; HRM suite now
**3,004**, project-wide **5,651**. HRM skill + README + this review updated. **Next: 3.19 Performance Review.**

**Context.** Extends the existing `apps/hrm` app — NOT a new app. Opens the **Performance Management**
group (3.18 Goal Setting -> 3.19 Performance Review -> 3.20 Continuous Feedback -> 3.21 Performance
Improvement) with the OKR/goal-mechanics layer only. 4 new models, all appended to
`apps/hrm/models.py`, migration `0030` (last is `0029_alter_payoutbatch_source_account_last4.py`). No
core-spine table is added — Goal Setting FKs `hrm.EmployeeProfile` (goal owner, never `core.Party`/
`accounts.User` directly, per the existing HRM convention) and `core.OrgUnit` (department scope, reused
exactly as `Designation.department` already does). Progress/health are **derived properties**, never
stored editable fields — mirrors the spine principle already used for `LeaveAllocation`/
`AttendanceRecord.hours_worked`/`PayrollCycle.total_*`.

NavERP.md 3.18 bullets (exact text, all 5 go Live this pass):
- OKR/KPI Management — Set objectives, key results.
- Goal Alignment — Cascading goals, team alignment.
- Weight Assignment — Weightage for different goals.
- Goal Timeline — Quarterly/annual goal periods.
- Goal Tracking — Progress updates, milestones.

Reuses (no duplication): `hrm.EmployeeProfile` (goal `owner`/`GoalCheckIn.checked_in_by` — never
`core.Party`/`settings.AUTH_USER_MODEL` directly), `hrm.EmployeeProfile.manager`/`.department` (derived
properties off `core.Employment` — used for "my direct reports' goals" queryset filters, no new manager
FK anywhere in this module), `core.OrgUnit` (`Objective.department`, FK'd by string exactly like
`Designation.department`). **No new core-spine entity.**

**Grounding decisions carried over from research (decide, don't re-litigate at build time):**
- `metric_type` is a `CharField` choice on `KeyResult`, not a 5th model — buys the Viva Goals/Perdoo/
  Profit.co KR-type distinction cheaply.
- Cascading alignment is the single self-FK `Objective.parent_objective` (`on_delete=SET_NULL`,
  `related_name="child_objectives"`) — vertical only; no M2M horizontal-alignment table this pass.
- Weighting is KR-level only (`KeyResult.weight`) — no `Objective`-to-parent cascade-weighting field.
- `GoalCheckIn` also extends `TenantNumbered` (`GCI-`) — every other timestamped-history-log table in
  HRM (`GoalCheckIn`'s closest analog is `LeaveRequest`/`AttendanceRecord`) is numbered, and a numbered
  check-in gives the audit trail + detail-page permalink a stable human ID.
- `GP`/`OBJ`/`KR`/`GCI` do not clash with any of the 39 prefixes already used in `apps/hrm/models.py`
  (confirmed by research's grep).
- Milestone-type KR tracking folds into `GoalCheckIn` (a lightweight `is_milestone_event` flag) for this
  pass — no 5th model.

## A. Models + migration (`apps/hrm/models.py`)

- [ ] `GoalPeriod(TenantOwned)` [no `NUMBER_PREFIX` — small per-tenant catalog identified by `name`,
      same pattern as `hrm.JobGrade`] — the quarterly/half-yearly/annual cycle container (drivers:
      3.18.4 Goal Timeline; 15Five/Lattice/BambooHR/Profit.co all scope every Objective to a named,
      dated cycle):
  - [ ] `name` — CharField(max_length=100) — e.g. "Q3 2026"
  - [ ] `period_type` — CharField(max_length=15, choices=`PERIOD_TYPE_CHOICES`, default="quarterly") —
        `[("quarterly","Quarterly"),("half_yearly","Half-Yearly"),("annual","Annual"),
        ("custom","Custom")]` — driver: 15Five "usually set quarterly, bi-annually, or yearly"
  - [ ] `start_date` — DateField()
  - [ ] `end_date` — DateField()
  - [ ] `status` — CharField(max_length=15, choices=`STATUS_CHOICES`, default="draft") —
        `[("draft","Draft"),("active","Active"),("closed","Closed"),("archived","Archived")]` —
        driver: Lattice/15Five carry-over-to-next-cycle pattern needs an explicit active/closed gate
  - [ ] `description` — TextField(blank=True)
  - [ ] `class Meta`: `ordering = ["-start_date"]`; `unique_together = ("tenant", "name")`; index
        `models.Index(fields=["tenant", "status"], name="hrm_gp_tenant_status_idx")`
  - [ ] `clean()` — raise `ValidationError({"end_date": "..."})` if `end_date <= start_date`
  - [ ] derived **@property** `objective_count` → `self.objectives.count()`
  - [ ] derived **@property** `avg_progress_pct` → one aggregate over `self.objectives.all()`
        (weighted-average of each `Objective.progress_pct`, `Decimal("0")` if no objectives — mirrors
        `PayrollCycle._totals()`'s single-aggregate-query convention, computed in Python over the
        already-derived per-objective values since `progress_pct` itself isn't a DB column)
  - [ ] `save()` — when set `status="active"`, no `is_current` boolean field (dropped per simplification
        — "current" is just `status="active"`, avoiding a second source of truth); no auto-flip of
        sibling periods to closed (an explicit `goalperiod_close` action does that, see section B)
  - [ ] `__str__` → `f"{self.name} ({self.get_period_type_display()})"`

- [ ] `Objective(TenantNumbered, NUMBER_PREFIX="OBJ")` — the "O" (drivers: 3.18.1 OKR/KPI Management,
      3.18.2 Goal Alignment, 3.18.3 Weight Assignment, 3.18.4 Goal Timeline):
  - [ ] `title` — CharField(max_length=255)
  - [ ] `description` — TextField(blank=True)
  - [ ] `owner` — `models.ForeignKey("hrm.EmployeeProfile", on_delete=models.PROTECT,
        related_name="objectives")` — PROTECT so an objective can't outlive its owner reference,
        matching `Payslip.employee`'s PROTECT convention; the goal-owner spine-reuse point
  - [ ] `goal_period` — `models.ForeignKey("hrm.GoalPeriod", on_delete=models.PROTECT,
        related_name="objectives")` — driver: 3.18.4 Goal Timeline, every Objective scoped to a named
        cycle (15Five/Lattice/BambooHR/Profit.co)
  - [ ] `parent_objective` — `models.ForeignKey("self", on_delete=models.SET_NULL, null=True,
        blank=True, related_name="child_objectives")` — driver: 3.18.2 Goal Alignment (cascading/
        parent-child linkage — Lattice/Betterworks/Quantive/Perdoo/WorkBoard/Viva Goals/Profit.co/
        Culture Amp/Leapsome all have this); also powers the Goal Tree view (no extra table)
  - [ ] `department` — `models.ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True,
        blank=True, related_name="objectives")` — driver: 3.18.2 scope/level tagging, reused exactly
        as `Designation.department` already does; nullable for individual-scope goals
  - [ ] `scope` — CharField(max_length=15, choices=`SCOPE_CHOICES`, default="individual") —
        `[("company","Company"),("department","Department"),("team","Team"),
        ("individual","Individual")]` — driver: 3.18.2, every one of the 10 surveyed products tags an
        Objective's organizational level
  - [ ] `target_type` — CharField(max_length=15, choices=`TARGET_TYPE_CHOICES`, default="committed") —
        `[("aspirational","Aspirational"),("committed","Committed")]` — driver: 15Five's aspirational-
        vs-commitment framing (50-70% success is a win vs. 100% expected)
  - [ ] `weight` — DecimalField(max_digits=5, decimal_places=2, default=100,
        validators=[MinValueValidator(0), MaxValueValidator(100)]) — driver: 3.18.3 Weight Assignment
        for **sibling** objectives under the same parent (used only when rendering a parent's
        weighted-children view; NOT used to compute this objective's own `progress_pct`, which is
        strictly a KR-weighted rollup per the research scope decision — document this distinction in
        the field's `help_text` so a future contributor doesn't conflate the two)
  - [ ] `status` — CharField(max_length=15, choices=`STATUS_CHOICES`, default="draft") —
        `[("draft","Draft"),("active","Active"),("at_risk","At Risk"),("completed","Completed"),
        ("cancelled","Cancelled")]` — `at_risk` is manually settable (an owner/manager call) distinct
        from the derived `health_status` percentage-based signal on `KeyResult`
  - [ ] `start_date` — DateField(null=True, blank=True) — defaults to `goal_period.start_date` in the
        form's initial value, but stored so an objective can start later than its period
  - [ ] `due_date` — DateField(null=True, blank=True) — same pattern, vs. `goal_period.end_date`
  - [ ] `class Meta`: `ordering = ["-goal_period__start_date", "title"]`; indexes
        `models.Index(fields=["tenant", "status"], name="hrm_obj_tenant_status_idx")`,
        `models.Index(fields=["tenant", "goal_period"], name="hrm_obj_tenant_period_idx")`,
        `models.Index(fields=["tenant", "owner"], name="hrm_obj_tenant_owner_idx")`,
        `models.Index(fields=["tenant", "parent_objective"], name="hrm_obj_tenant_parent_idx")`
  - [ ] `clean()` — raise `ValidationError({"parent_objective": "..."})` if
        `self.parent_objective_id == self.pk` (no self-parenting) and if setting `parent_objective`
        would create a cycle (walk `parent_objective.parent_objective...` up to a sane depth, e.g. 10,
        raising if `self.pk` is encountered — cheap guard against a corrupt tree)
  - [ ] `_krs()` **method** — `self.key_results.all()`, cached per instance (avoids re-querying across
        `progress_pct`/`health_status`/`key_result_count` on the same request)
  - [ ] derived **@property** `progress_pct` → weighted average of `kr.progress_pct * kr.weight` over
        `self._krs()`, normalized by `sum(kr.weight for kr in self._krs())` (falls back to a simple
        average if all weights are 0); returns `Decimal("0")` if no key results — 3.18.3's weighted-
        rollup feature (Lattice's documented Progress Calculation, Profit.co's KR weight-roll-up)
  - [ ] derived **@property** `health_status` → `"completed"` if `status == "completed"`; else derive
        from `progress_pct` vs. **time-elapsed-in-period** (`(today - goal_period.start_date) /
        (goal_period.end_date - goal_period.start_date)`): `on_track` if progress_pct >= expected pace
        (within a 10-point tolerance), `at_risk` if 10-25 points behind pace, `off_track` if >25 points
        behind — 3.18.5's status/health-coloring feature (Weekdone/WorkBoard/Betterworks), computed
        not stored
  - [ ] derived **@property** `key_result_count` → `self._krs().count()` (via `len(self._krs())` since
        `_krs()` is already materialized)
  - [ ] `__str__` → `f"{self.number} · {self.title}"`

- [ ] `KeyResult(TenantNumbered, NUMBER_PREFIX="KR")` — the "KR" under an Objective (drivers: 3.18.1
      OKR/KPI Management KR-type distinction, 3.18.3 Weight Assignment, 3.18.5 Goal Tracking):
  - [ ] `objective` — `models.ForeignKey("hrm.Objective", on_delete=models.CASCADE,
        related_name="key_results")`
  - [ ] `title` — CharField(max_length=255)
  - [ ] `metric_type` — CharField(max_length=15, choices=`METRIC_TYPE_CHOICES`, default="numeric") —
        `[("numeric","Numeric"),("percentage","Percentage"),("currency","Currency"),
        ("boolean","Boolean"),("milestone","Milestone")]` — driver: Viva Goals' 3 formal KR types +
        Perdoo/Profit.co's metric-vs-milestone split, folded into one CharField per research
  - [ ] `start_value` — DecimalField(max_digits=16, decimal_places=2, null=True, blank=True) —
        nullable for boolean/milestone types
  - [ ] `target_value` — DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
  - [ ] `current_value` — DecimalField(max_digits=16, decimal_places=2, null=True, blank=True) —
        updated by `GoalCheckIn.save()`, but kept directly editable on the KR form too (an owner can
        correct it without a formal check-in — matches how `Payslip.on_hold` stays directly editable
        alongside its workflow actions)
  - [ ] `is_milestone_event` — BooleanField(default=False) — for `metric_type="milestone"` KRs, marks
        that progress is driven by discrete `GoalCheckIn` milestone-completion events rather than a
        continuous numeric value (folds 3.18.5's milestone-tracking feature into the check-in log
        instead of a 5th model, per research)
  - [ ] `unit` — CharField(max_length=30, blank=True) — free text, e.g. "%", "$", "signups"
  - [ ] `weight` — DecimalField(max_digits=5, decimal_places=2, default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)]) — driver: 3.18.3, weighting across
        **sibling KeyResults under the same Objective** (Lattice/Perdoo/Profit.co/Betterworks); form
        should default new KRs to an equal split (`100 / (existing_sibling_count + 1)`) but leave it
        overridable, matching Lattice's "equal-by-default, override to e.g. 30/70" behavior
  - [ ] `status` — CharField(max_length=15, choices=`STATUS_CHOICES`, default="not_started") —
        `[("not_started","Not Started"),("in_progress","In Progress"),("completed","Completed"),
        ("cancelled","Cancelled")]`
  - [ ] `class Meta`: `ordering = ["objective", "-weight", "title"]`; indexes
        `models.Index(fields=["tenant", "objective"], name="hrm_kr_tenant_objective_idx")`,
        `models.Index(fields=["tenant", "status"], name="hrm_kr_tenant_status_idx")`
  - [ ] `clean()` — raise `ValidationError({"target_value": "..."})` if `metric_type` in
        `("numeric","percentage","currency")` and `target_value` is `None` (a metric KR must have a
        target); raise `ValidationError({"weight": "..."})` if `weight` is negative (validators already
        block this at the field level but keep the model-level guard for bulk/fixture writes that skip
        `full_clean()`)
  - [ ] derived **@property** `progress_pct` → for `metric_type` in `("numeric","percentage",
        "currency")`: `(current_value - start_value) / (target_value - start_value) * 100`, clamped to
        `[0, 100]`, guarding `target_value == start_value` (return 100 if `current_value >=
        target_value` else 0); for `"boolean"`: `100` if `current_value` truthy/`status="completed"`
        else `0`; for `"milestone"`: `self.checkins.filter(is_milestone_event=True,
        confidence="on_track").count() / max(self.milestone_target_count, 1) * 100` — **NOTE**: no
        `milestone_target_count` field exists in this pass; for milestone KRs without a defined step
        count, fall back to `100` if `status == "completed"` else `0` (documented simplification —
        step-weighted milestone sub-tracking is explicitly deferred, see Deferred section)
  - [ ] derived **@property** `health_status` → same on_track/at_risk/off_track logic as
        `Objective.health_status`, computed against `objective.goal_period`'s elapsed time — 3.18.5
        status/health-coloring
  - [ ] `__str__` → `f"{self.number} · {self.title} ({self.get_metric_type_display()})"`

- [ ] `GoalCheckIn(TenantNumbered, NUMBER_PREFIX="GCI")` — timestamped progress-update log against a
      KeyResult (driver: 3.18.5 Goal Tracking — Betterworks/Viva Goals/Quantive/Perdoo/Weekdone/
      Profit.co all treat check-ins as a history log, never a single mutable field):
  - [ ] `key_result` — `models.ForeignKey("hrm.KeyResult", on_delete=models.CASCADE,
        related_name="checkins")`
  - [ ] `checkin_date` — DateField(default=`django.utils.timezone.now` via a
        `default=timezone.localdate` callable, matching `AttendanceRecord`'s date-default convention)
  - [ ] `value_at_checkin` — DecimalField(max_digits=16, decimal_places=2, null=True, blank=True) —
        the KR value reported at this check-in (nullable for a milestone-only/qualitative check-in)
  - [ ] `confidence` — CharField(max_length=15, choices=`CONFIDENCE_CHOICES`, default="on_track") —
        `[("on_track","On Track"),("at_risk","At Risk"),("off_track","Off Track")]` — driver:
        Betterworks/Weekdone/WorkBoard's health-status framing, self-reported at check-in time
        (distinct from the derived `KeyResult.health_status` percentage-based signal)
  - [ ] `is_milestone_event` — BooleanField(default=False) — marks this check-in as a discrete
        milestone-completion event (folds 3.18.5's milestone-tracking into the check-in log, per
        research; only meaningful when `key_result.metric_type == "milestone"`)
  - [ ] `comment` — TextField(blank=True) — the blockers/wins note (Quantive/Perdoo/Profit.co)
  - [ ] `created_by` — `models.ForeignKey("hrm.EmployeeProfile", on_delete=models.SET_NULL, null=True,
        blank=True, related_name="goal_checkins", editable=False)` — set from
        `request.user`'s linked `EmployeeProfile` in the view (usually the KR/objective owner, but
        allow manager overrides — the view, not the form, resolves this so a manager checking in on a
        direct report's KR doesn't need to impersonate them)
  - [ ] `class Meta`: `ordering = ["-checkin_date", "-created_at"]`; indexes
        `models.Index(fields=["tenant", "key_result"], name="hrm_gci_tenant_kr_idx")`,
        `models.Index(fields=["tenant", "checkin_date"], name="hrm_gci_tenant_date_idx")`
  - [ ] `save()` override — on create (`self.pk is None`), after `super().save()`, if
        `value_at_checkin is not None`: set `self.key_result.current_value = value_at_checkin` and
        `self.key_result.save(update_fields=["current_value", "updated_at"])` — the check-in is the
        single write path that advances `KeyResult.current_value`, matching the research's "on save it
        can update the parent KeyResult.current_value" spec; if `is_milestone_event` is True, no
        additional side effect needed since `KeyResult.progress_pct` for milestone-type KRs already
        reads `self.checkins.filter(is_milestone_event=True, ...)` live
  - [ ] `__str__` → `f"{self.number} · {self.key_result.title} · {self.get_confidence_display()}"`

- [ ] one incremental migration `apps/hrm/migrations/0030_goalperiod_objective_keyresult_and_more.py`
      (NOT `0001_initial`; last is `0029_alter_payoutbatch_source_account_last4.py`) —
      `makemigrations hrm`, review the generated file, adjust index/constraint names to match the ones
      specified above if Django's auto-names differ

## B. Forms (`apps/hrm/forms.py`)

- [ ] `GoalPeriodForm(ModelForm)` — `tenant=` kwarg accepted (unused for FK-scoping since GoalPeriod has
      no in-module FKs, but keep the signature consistent with every other HRM form); excludes
      `tenant`; fields = `name, period_type, start_date, end_date, status, description`
- [ ] `ObjectiveForm(ModelForm)` — `tenant=` kwarg; excludes `tenant`/`number`; scopes `owner` to
      `EmployeeProfile.objects.filter(tenant=tenant)`, `goal_period` to
      `GoalPeriod.objects.filter(tenant=tenant)`, `department` to
      `core.OrgUnit.objects.filter(tenant=tenant, kind="department")`, `parent_objective` to
      `Objective.objects.filter(tenant=tenant).exclude(pk=self.instance.pk)` (guard against
      self-parenting at the form-queryset level, in addition to the model's `clean()`); fields =
      `title, description, owner, goal_period, parent_objective, department, scope, target_type,
      weight, status, start_date, due_date`
- [ ] `KeyResultForm(ModelForm)` — `tenant=` kwarg; excludes `tenant`/`number`/`objective` (objective is
      set from the URL in the create view, matching `PayslipLine`-style parent-scoped child-create
      views); scopes nothing else (metric_type/status are plain choices); fields = `title, metric_type,
      start_value, target_value, current_value, is_milestone_event, unit, weight, status`
- [ ] `KeyResultInlineForm(ModelForm)` — same as `KeyResultForm` but used from the Objective detail
      page's "add KR inline" action (thin wrapper or the same form reused with a different template
      context — decide at build time based on whether a distinct class adds value)
- [ ] `GoalCheckInForm(ModelForm)` — `tenant=` kwarg; excludes `tenant`/`number`/`key_result`/
      `created_by` (both set from the URL/request in the view); fields = `checkin_date,
      value_at_checkin, confidence, is_milestone_event, comment`

## C. Views (`apps/hrm/views.py`) — full CRUD + custom actions, function-based, `@login_required`,
      tenant-scoped via `crud_list/crud_create/crud_edit/crud_detail/crud_delete`

- [ ] `goalperiod_list` — `crud_list`; `search_fields=("name",)`; `filters=[("status",
      "status", False), ("period_type", "period_type", False)]`; pass `status_choices=
      GoalPeriod.STATUS_CHOICES`, `period_type_choices=GoalPeriod.PERIOD_TYPE_CHOICES` in
      `extra_context` (Filter Implementation Rule)
- [ ] `goalperiod_create` / `goalperiod_edit` / `goalperiod_detail` / `goalperiod_delete` — standard
      `crud_create/crud_edit/crud_detail/crud_delete`; `goalperiod_detail` extra_context includes
      `objective_count`/`avg_progress_pct` (already properties, just pass `obj` — template reads them)
      and the period's objectives list (`select_related("owner__party", "goal_period")`)
- [ ] `goalperiod_activate` (`@tenant_admin_required`, POST-only) — sets `status="active"`; no
      auto-close of sibling periods (explicit `goalperiod_close` handles that separately, avoiding a
      surprising side effect) — 3.18.4 Goal Timeline
- [ ] `goalperiod_close` (`@tenant_admin_required`, POST-only) — sets `status="closed"`; guard: only
      from `status="active"` (else redirect with an error message) — 3.18.4 Goal Timeline
- [ ] `objective_list` — `crud_list`; `search_fields=("title", "number", "owner__party__name")`;
      `filters=[("status", "status", False), ("scope", "scope", False), ("target_type", "target_type",
      False), ("goal_period", "goal_period_id", True), ("owner", "owner_id", True), ("department",
      "department_id", True)]`; pass `status_choices`, `scope_choices`, `target_type_choices`,
      `goal_periods=GoalPeriod.objects.filter(tenant=request.tenant)`,
      `employees=EmployeeProfile.objects.filter(tenant=request.tenant)`,
      `departments=OrgUnit.objects.filter(tenant=request.tenant, kind="department")` in extra_context;
      add a `?mine=1` convenience filter that resolves the logged-in user's `EmployeeProfile` (via
      `request.user.party.employee_profile` if present) and filters `owner=that_profile` OR
      `owner__employment__manager=that_profile.party` (direct-reports visibility — 3.18.2 "Manager
      visibility into direct reports' goals", using the **derived** `.manager`/`.department`
      properties, no new FK)
- [ ] `objective_create` / `objective_edit` / `objective_detail` / `objective_delete` — standard;
      `objective_detail` extra_context includes `key_results=obj.key_results.all()` (for inline KR
      list + add-inline form), `child_objectives=obj.child_objectives.all()` (cascade/alignment
      children — 3.18.2 Goal Tree), `recent_checkins` (a bounded queryset via
      `GoalCheckIn.objects.filter(key_result__objective=obj).select_related("key_result",
      "created_by__party").order_by("-checkin_date")[:20]` for the progress-trend/history panel — no
      N+1, single query)
- [ ] `objective_tree` (or a `?view=tree` query param on `objective_list` — decide at build time which
      is cleaner) — recursive rendering of top-level Objectives (`parent_objective__isnull=True`) with
      `child_objectives` nested, for the 3.18.2 Goal Tree / alignment-map visualization; bound the
      recursion depth (e.g. render up to 4 levels) to avoid a runaway template loop on a corrupt tree
- [ ] `keyresult_create` (nested under an objective: `<int:objective_pk>/key-results/add/`) — fetches
      the parent `Objective` (`tenant=request.tenant` guard), sets `objective=obj` before save,
      defaults `weight` to an equal split among existing siblings (`100 / (sibling_count + 1)`) in the
      form's initial value — 3.18.1/3.18.3
- [ ] `keyresult_edit` / `keyresult_detail` / `keyresult_delete` — standard `crud_edit/crud_detail/
      crud_delete`, `success_url` redirects back to the parent `objective_detail`, not a KR list page
      (KRs are always viewed in the context of their Objective — no standalone `keyresult_list` route
      needed for navigation, though the URL/view still exists for completeness and direct links)
- [ ] `goalcheckin_list` — `crud_list`; `search_fields=("key_result__title", "comment")`;
      `filters=[("confidence", "confidence", False), ("key_result", "key_result_id", True)]`; pass
      `confidence_choices=GoalCheckIn.CONFIDENCE_CHOICES`, `key_results=
      KeyResult.objects.filter(tenant=request.tenant)` in extra_context — serves the org-wide 3.18.5
      Goal Tracking history view
- [ ] `goalcheckin_create` (nested under a key result: `<int:keyresult_pk>/check-ins/add/`) — fetches
      the parent `KeyResult` (`tenant=request.tenant` guard), sets `key_result=kr` and
      `created_by=request.user`'s linked `EmployeeProfile` before save (resolve via
      `getattr(request.user, "party", None)` then `.employee_profile` if present — guard for a manager/
      admin user who has no linked EmployeeProfile: leave `created_by=None`, don't 500) — this IS the
      3.18.5 "Goal Tracking" check-in workflow action
- [ ] `goalcheckin_detail` / `goalcheckin_delete` — standard (no edit view — a check-in is an
      immutable history log entry once created, matching the append-only convention already used for
      `AttendanceRecord`/audit-style rows; if a correction is needed, delete + re-create, never mutate
      a past check-in's `value_at_checkin`)
- [ ] all list views pass `q` search + pagination automatically via `crud_list`; no manual
      `Paginator`/`Q()` code duplicated per view (Filter Implementation Rule + CRUD Completeness Rule)

## D. URLs (`apps/hrm/urls.py`, `app_name = "hrm"`, append to the existing `urlpatterns`)

- [ ] `goal-periods/` -> `goalperiod_list`; `goal-periods/add/` -> `goalperiod_create`;
      `goal-periods/<int:pk>/` -> `goalperiod_detail`; `goal-periods/<int:pk>/edit/` ->
      `goalperiod_edit`; `goal-periods/<int:pk>/delete/` -> `goalperiod_delete`;
      `goal-periods/<int:pk>/activate/` -> `goalperiod_activate`; `goal-periods/<int:pk>/close/` ->
      `goalperiod_close`
- [ ] `objectives/` -> `objective_list`; `objectives/tree/` -> `objective_tree`; `objectives/add/` ->
      `objective_create`; `objectives/<int:pk>/` -> `objective_detail`; `objectives/<int:pk>/edit/` ->
      `objective_edit`; `objectives/<int:pk>/delete/` -> `objective_delete`
- [ ] `objectives/<int:objective_pk>/key-results/add/` -> `keyresult_create`; `key-results/<int:pk>/` ->
      `keyresult_detail`; `key-results/<int:pk>/edit/` -> `keyresult_edit`; `key-results/<int:pk>/delete/`
      -> `keyresult_delete`
- [ ] `key-results/<int:keyresult_pk>/check-ins/add/` -> `goalcheckin_create`; `check-ins/` ->
      `goalcheckin_list`; `check-ins/<int:pk>/` -> `goalcheckin_detail`; `check-ins/<int:pk>/delete/` ->
      `goalcheckin_delete`
- [ ] verify every new `path()` name is unique against the ~180 existing `hrm:` names (`grep name=` in
      `apps/hrm/urls.py` before adding — no accidental collision)

## E. Admin (`apps/hrm/admin.py`)

- [ ] register `GoalPeriod` — `list_display=("name", "period_type", "status", "start_date",
      "end_date", "tenant")`, `list_filter=("status", "period_type", "tenant")`, `search_fields=
      ("name",)`
- [ ] register `Objective` — `list_display=("number", "title", "owner", "goal_period", "status",
      "scope", "tenant")`, `list_filter=("status", "scope", "target_type", "tenant")`,
      `search_fields=("number", "title")`, `autocomplete_fields=("owner", "goal_period",
      "parent_objective", "department")`
- [ ] register `KeyResult` — `list_display=("number", "title", "objective", "metric_type", "status",
      "tenant")`, `list_filter=("metric_type", "status", "tenant")`, `search_fields=("number", "title")`,
      `autocomplete_fields=("objective",)`
- [ ] register `GoalCheckIn` — `list_display=("number", "key_result", "checkin_date", "confidence",
      "created_by", "tenant")`, `list_filter=("confidence", "tenant")`, `search_fields=("number",
      "comment")`, `autocomplete_fields=("key_result", "created_by")`

## F. Seed (`apps/hrm/management/commands/seed_hrm.py`) — extend the existing per-tenant loop,
      idempotent (skip-if-exists check per model, same pattern as every prior HRM extension)

- [ ] guard: `if GoalPeriod.objects.filter(tenant=tenant).exists(): skip this block, print notice` (do
      NOT wrap the whole command's idempotency in this — only this section)
- [ ] seed 1-2 `GoalPeriod` rows per tenant: one `status="active"` covering roughly "now" (e.g. current
      quarter), optionally one `status="closed"` prior period to exercise the timeline/history view
- [ ] reuse existing `EmployeeProfile.objects.filter(tenant=tenant).select_related("party")` and
      `core.OrgUnit.objects.filter(tenant=tenant, kind="department")` querysets (no new employee/org
      rows created by this seeder) — pick 3-5 employees as objective owners, include at least one
      manager/direct-report pair if resolvable via `.manager` so the "my direct reports' goals" filter
      has data to show
- [ ] seed a handful of `Objective` rows demonstrating **parent cascade**: 1 company-level objective
      (`scope="company"`, no `department`, owned by a senior/first employee), 1-2 department-level
      objectives with `parent_objective` pointing at the company one (`scope="department"`,
      `department` set), 2-3 individual objectives with `parent_objective` pointing at a department one
      (`scope="individual"`) — demonstrates the 3-level cascade tree end to end
- [ ] seed 2-3 `KeyResult` rows per Objective with varied `metric_type` (at least one `numeric`, one
      `percentage`, one `boolean` or `milestone`) and weights that sum sensibly per objective (e.g.
      60/40 or equal-split 33/33/34) — exercises the weighted-rollup `progress_pct` property
      immediately after seeding
  - [ ] set `start_value`/`current_value`/`target_value` so seeded objectives show a MIX of health
        states after seeding (some on_track, at least one at_risk/off_track) — proves the derived
        `health_status` property renders correctly across all three states without needing manual
        testing to discover a broken branch
- [ ] seed 2-4 `GoalCheckIn` rows per KeyResult (staggered `checkin_date`s within the goal period) with
      varied `confidence` values, at least one with `comment` text populated — exercises the check-in
      history list + the "recent check-ins" panel on `objective_detail`; the LAST seeded check-in per
      KR should leave `key_result.current_value` matching what the seeded `Objective`/`KeyResult` health
      mix above expects (i.e., don't let the check-in `save()` override silently undo the intentional
      health-state seeding — seed check-ins with `value_at_checkin` values that are consistent with,
      not contradictory to, the KR's already-set `current_value`)
- [ ] idempotent re-run check: run `seed_hrm` a 2nd time with no `--flush`, confirm no duplicate
      `GoalPeriod`/`Objective`/`KeyResult`/`GoalCheckIn` rows are created (the per-model `.exists()`
      guard added above handles this — verify at Verify step, not just by inspection)

## G. Wire-up

- [ ] `config/settings.py` — no change needed (`apps.hrm` already in `INSTALLED_APPS`)
- [ ] `config/urls.py` — no change needed (`hrm/` include already wired from 3.1)
- [ ] `apps/core/navigation.py` `LIVE_LINKS["3.18"]` — new entry mapping all 5 NavERP.md bullets:
  ```python
  # 3.18 Goal Setting — Objective/KeyResult/GoalCheckIn/GoalPeriod (OKR mechanics only; review
  # cycles/ratings/360/kudos/PIPs are later Performance Management sub-modules 3.19-3.21).
  "3.18": {
      "OKR/KPI Management": "hrm:objective_list",           # bullet (Objective + KeyResult CRUD)
      "Goal Alignment": "hrm:objective_tree",                # bullet (cascade/alignment tree view)
      "Weight Assignment": "hrm:objective_list",             # bullet (KR weight editable on objective_detail)
      "Goal Timeline": "hrm:goalperiod_list",                # bullet (quarterly/annual cycle catalog)
      "Goal Tracking": "hrm:goalcheckin_list",                # bullet (check-in history log)
  },
  ```
  (confirm no other sub-module already claims these 5 exact bullet strings under a different key —
  they're new for 3.18, per NavERP.md)

## H. Templates (`templates/hrm/performance/<entity>/{list,detail,form}.html`) — `performance/` is the
      sub-module folder (first Performance Management sub-module; per Template Folder Structure Rule 2)

- [ ] `performance/goalperiod/list.html` — filter bar (`status`, `period_type` dropdowns reflecting
      `request.GET`), Actions column (view/edit/delete + Activate/Close buttons conditional on
      `obj.status`), empty-state, pagination
- [ ] `performance/goalperiod/detail.html` — shows `objective_count`/`avg_progress_pct`, the period's
      objectives table, Actions sidebar (Edit/Delete conditional on `status == "draft"`,
      Activate/Close workflow buttons, Back to List)
- [ ] `performance/goalperiod/form.html` — create/edit, shared template (`is_edit` flag)
- [ ] `performance/objective/list.html` — filter bar (`status`, `scope`, `target_type`, `goal_period`,
      `owner`, `department` dropdowns + `?mine=1` toggle), Actions column, empty-state, pagination —
      **CRITICAL**: pass every dropdown's options from the view context (Filter Implementation Rule 1),
      use `|stringformat:"d"` for the FK dropdowns' `selected` comparison (Rule 2)
- [ ] `performance/objective/detail.html` — header (title/owner/period/status/progress_pct bar/
      health_status badge), Key Results table (inline, with an "Add Key Result" button ->
      `keyresult_create`), Child Objectives section (cascade children, links to their own detail
      pages), Recent Check-ins panel (last 20, from `recent_checkins` context var), Actions sidebar
      (Edit/Delete conditional on status, Back to List)
- [ ] `performance/objective/form.html` — create/edit; `parent_objective`/`owner`/`goal_period`/
      `department` as searchable `<select>`s
- [ ] `performance/objective/tree.html` — recursive partial rendering `parent_objective__isnull=True`
      Objectives with nested `child_objectives` (use a `{% include %}` recursive partial, bounded
      depth per view-level guard) — the 3.18.2 Goal Tree / alignment visualization
- [ ] `performance/keyresult/detail.html` — shows metric_type/start/current/target/unit,
      `progress_pct` bar, `health_status` badge, weight, its own check-in list (scoped to this KR) +
      "Add Check-in" button -> `goalcheckin_create`, Actions sidebar (Edit/Delete, Back to Objective —
      NOT Back to List, since KRs are always viewed in Objective context)
- [ ] `performance/keyresult/form.html` — create (nested under objective, via `objective_pk` in URL) +
      edit, shared template
- [ ] `performance/goalcheckin/list.html` — org-wide check-in history, filter bar (`confidence`,
      `key_result` dropdowns), Actions column (view/delete only — no edit, immutable log)
- [ ] `performance/goalcheckin/detail.html` — read-only, Actions sidebar (Delete only, Back to Key
      Result)
- [ ] `performance/goalcheckin/form.html` — create only (nested under key result via `keyresult_pk` in
      URL); no edit template needed since there's no `goalcheckin_edit` view
- [ ] an overview/landing link: add a "Goal Setting" card/section to the existing `hrm_overview.html`
      (or equivalent HRM landing page) pointing at `objective_list` — mirrors how prior sub-modules
      surface themselves on the module landing page

## I. Verify

- [ ] `python manage.py makemigrations hrm` — confirm exactly one new migration file numbered `0030`,
      review generated index/constraint names against section A's spec
- [ ] `python manage.py migrate` — applies cleanly with no errors
- [ ] `python manage.py seed_hrm` — run once, confirm GoalPeriod/Objective/KeyResult/GoalCheckIn rows
      created per tenant, confirm login instructions print (tenant admin accounts, superuser warning)
- [ ] `python manage.py seed_hrm` — run a **2nd time**, confirm idempotent (no duplicate rows, "already
      exists" notice printed for this section)
- [ ] `python manage.py check` — no system check errors/warnings introduced
- [ ] `temp/` smoke sweep — every new `hrm:goalperiod_*`/`hrm:objective_*`/`hrm:keyresult_*`/
      `hrm:goalcheckin_*` URL returns 200 (GET) or 302 (POST redirect) when logged in as a tenant admin;
      confirm no `{#`/`{% comment %}` template-leak artifacts render; confirm a cross-tenant objective/
      KR/check-in ID (belonging to a DIFFERENT tenant) returns 404 via `crud_detail`'s
      `tenant=request.tenant` guard (IDOR check)
- [ ] confirm the sidebar shows 3.18's 5 bullets as **Live** (not "On the roadmap") after the
      `LIVE_LINKS["3.18"]` wire-up, for a logged-in tenant admin
- [ ] confirm `objective.progress_pct`/`health_status` and `key_result.progress_pct`/`health_status`
      render without raising on: an Objective with zero KeyResults, a KeyResult with
      `start_value == target_value`, a GoalPeriod with `end_date == start_date` blocked by `clean()`
      (edge-case guard sweep — these are exactly the divide-by-zero/empty-queryset traps the derived
      properties above must defend against)

## J. Close-out

- [ ] `code-reviewer` agent — apply findings, one file per commit
- [ ] `explorer` agent — apply findings, one file per commit
- [ ] `frontend-reviewer` agent — apply findings, one file per commit
- [ ] `performance-reviewer` agent — apply findings (watch specifically for N+1 on `objective_list`'s
      `owner__party__name`/`goal_period`/`department` and on `objective_tree`'s recursive
      `child_objectives` traversal — use `select_related`/`prefetch_related` from the start, don't wait
      for this review to catch it), one file per commit
- [ ] `qa-smoke-tester` agent — apply findings, one file per commit
- [ ] `security-reviewer` agent — apply findings (watch specifically for the cross-tenant IDOR check on
      nested create views — `keyresult_create`/`goalcheckin_create` fetch their parent
      Objective/KeyResult with an explicit `tenant=request.tenant` guard, not just `pk=`), one file per
      commit
- [ ] `test-writer` agent — apply output, one file per commit
- [ ] create/update `.claude/skills/hrm/SKILL.md` — add the 4-model 3.18 table (GoalPeriod/Objective/
      KeyResult/GoalCheckIn), the cascade/weight/check-in workflow, routes/templates/seeder/sidebar
      (`LIVE_LINKS["3.18"]`) notes, update the module's model count and built-sub-module list
- [ ] update the HRM README entry for 3.18 Goal Setting (mirror the 3.17 README entry's shape and
      depth) + refresh HRM/project-wide test counts once `test-writer` lands

## Later passes / deferred (carried over from research-hrm-goal-setting.md — do NOT build in 3.18)

- **Always-on KPI catalog** (400+ built-in KPIs, health-metric tracking distinct from cycle-bound
  OKRs) — Perdoo/Profit.co feature; overlaps Module 10 BI/Analytics scope, bigger than one sub-module.
- **Horizontal (cross-team, non-hierarchical) M2M alignment** ("contributing objectives" beyond the
  single `parent_objective` vertical cascade) — Quantive/Profit.co differentiator; add later if demand
  emerges.
- **Objective-to-cascade weighting** (weighting how much a child Objective's score contributes to its
  parent's, on top of KR-level weighting) — Perdoo refinement; this pass ships KR-level weighting only.
- **AI-drafted OKRs / AI check-in summaries** — Leapsome/WorkBoard/Profit.co; requires an external LLM
  call, out of a single Django pass.
- **Automated progress sync from external systems** (Jira, Azure DevOps, Salesforce, Excel, 170+
  integrations) — Quantive/Viva Goals/Lattice/Leapsome; `GoalCheckIn` stays manual-entry-only, schema
  doesn't block adding `is_automated`/`source_system` later.
- **Drift/stagnation Slack or notification alerts** — Betterworks/Profit.co; needs the notification
  integration layer.
- **Viva Goals' "control/guardrail" (Quality-type) Key Result behavior** — a KR that alerts on
  dropping below a floor rather than climbing to a ceiling; folded generically into `metric_type`
  choices for now, the guardrail *behavior* is a later refinement.
- **Step-weighted milestone sub-tracking** (discrete, individually-weighted milestone steps driving a
  KR's progress %, beyond the `is_milestone_event` flag on `GoalCheckIn`) — Perdoo/Profit.co/WorkBoard
  differentiator; this pass's milestone KRs fall back to a binary completed/not-completed signal.
- **3.19 Performance Review** — Review Cycles, Self-Assessment, Manager Review, 360° Feedback,
  Calibration/bell-curve. Explicitly out of scope even though 3.18's OKR data will later feed review
  scoring.
- **3.20 Continuous Feedback** — real-time kudos/appreciation, 1:1 meeting notes/action items,
  feedback dashboard, anonymous feedback channels.
- **3.21 Performance Improvement** — PIP management, warning letters, coaching notes.

## Review notes
(filled in at the end)

---
# HRM 3.14 Payroll Processing (payroll) — plan from research-payroll.md (2026-07-04)

**Context.** Extends the existing `apps/hrm` app — NOT a new app. Builds the **operational** payroll
run layer on top of 3.13's compensation *definition* layer: computes per-employee payslips from each
employee's active `EmployeeSalaryStructure`, routes the run through an approval workflow, supports
salary holds + arrears + bonus, and hands the rolled-up totals off to `accounting.PayrollRun` for GL
posting (lesson **L29** — HRM never builds a `JournalEntry`). 3 new models, all in `apps/hrm/models.py`.
Scope decision from research: **no `PayrollAdjustment` model** — flat `arrears_amount`/`bonus_amount`
fields on `Payslip` (+ mirrored `PayslipLine` snapshot rows) are sufficient for v1.

NavERP.md 3.14 bullets (exact text, all 5 go Live this pass):
- Payroll Run — Monthly processing, calculation engine.
- Payroll Approval — Multi-level approval before disbursement.
- Salary Holds — Hold salary for specific employees.
- Arrears Calculation — Retroactive calculations.
- Bonus Processing — Performance bonus, ex-gratia.

Reuses (no duplication): `hrm.EmployeeProfile`, `hrm.EmployeeSalaryStructure` (+ its
`template.lines`/`resolved_amount()`), `hrm.PayComponent.COMPONENT_TYPE_CHOICES`,
`accounting.PayrollRun` (existing, `apps/accounting/models_advanced.py:162`), `settings.AUTH_USER_MODEL`.

## A. Models + migration (`apps/hrm/models.py`)

- [ ] `PayrollCycle(TenantNumbered, NUMBER_PREFIX="PRC")` — the HRM operational run header (named
      distinctly from `accounting.PayrollRun` per the research coordination rule):
  - [ ] `period_start` — DateField()
  - [ ] `period_end` — DateField()
  - [ ] `pay_date` — DateField()
  - [ ] `cycle_type` — CharField(max_length=20, choices=`CYCLE_TYPE_CHOICES`, default="regular") —
        `[("regular","Regular"),("off_cycle","Off-Cycle"),("bonus","Bonus")]` — driver: Rippling
        unlimited off-cycle runs / Gusto "Extra Pay" bonus payroll / Zoho off-cycle vs regular
        distinction; gates whether approval is enforced (Gusto: off-cycle/bonus MAY skip approval)
  - [ ] `status` — CharField(max_length=20, choices=`STATUS_CHOICES`, default="draft") —
        `[("draft","Draft"),("pending_approval","Pending Approval"),("approved","Approved"),
        ("rejected","Rejected"),("locked","Locked")]` — driver: Workday calculate→commit two-phase
        lifecycle + greytHR "lock payroll" + Darwinbox RIVeR stages, collapsed to a buildable state
        machine
  - [ ] `submitted_by` — FK `settings.AUTH_USER_MODEL`, `on_delete=models.SET_NULL`, `null=True,
        blank=True`, `related_name="hrm_payroll_cycle_submissions"`, `editable=False`
  - [ ] `submitted_at` — DateTimeField(null=True, blank=True, editable=False)
  - [ ] `approved_by` — FK `settings.AUTH_USER_MODEL`, `on_delete=models.SET_NULL`, `null=True,
        blank=True`, `related_name="hrm_payroll_cycle_approvals"`, `editable=False`
  - [ ] `approved_at` — DateTimeField(null=True, blank=True, editable=False)
  - [ ] `rejection_reason` — TextField(blank=True)
  - [ ] `notes` — TextField(blank=True)
  - [ ] `accounting_payroll_run` — FK `"accounting.PayrollRun"`, `on_delete=models.SET_NULL,
        null=True, blank=True, editable=False, related_name="hrm_cycles"` — set on lock; carries the
        rolled-up totals into accounting's existing GL-posting flow (`payroll_run_post`)
  - [ ] `class Meta`: `ordering = ["-pay_date"]`; `unique_together = ("tenant", "number")`; index
        `models.Index(fields=["tenant", "status"], name="hrm_prc_tenant_status_idx")`
  - [ ] derived **properties** (NOT stored fields, aggregate over `self.payslips.all()`):
    - [ ] `headcount` → `self.payslips.count()`
    - [ ] `total_gross` → `sum(p.gross_pay for p in self.payslips.all()) or Decimal("0")` (use
          `.aggregate(Sum(...))` for efficiency — see performance note below)
    - [ ] `total_deductions` → same pattern, sums `total_deductions`
    - [ ] `total_net` → same pattern, sums `net_pay`
    - [ ] `is_locked` → `self.status == "locked"`
  - [ ] **Performance note (bake in from day 1, don't wait for performance-reviewer):** implement the
        three `total_*` properties with a single `self.payslips.aggregate(g=Sum("gross_pay"),
        d=Sum("total_deductions"), n=Sum("net_pay"))` call (one query, not three separate `.aggregate()`
        calls) — cache the dict on first access per-request if convenient, but at minimum don't issue 3
        separate queries when the detail page renders all three
  - [ ] `__str__` → `f"{self.number} · {self.get_cycle_type_display()} · {self.period_start}–{self.period_end}"`

- [ ] `Payslip(TenantNumbered, NUMBER_PREFIX="PSL")` — one per employee per cycle:
  - [ ] `cycle` — FK `"hrm.PayrollCycle"`, `on_delete=models.CASCADE`, `related_name="payslips"`
  - [ ] `employee` — FK `"hrm.EmployeeProfile"`, `on_delete=models.PROTECT` — PROTECT (not CASCADE/
        SET_NULL) so a payslip's employee can't vanish out from under paid-history
  - [ ] `salary_structure` — FK `"hrm.EmployeeSalaryStructure"`, `on_delete=models.SET_NULL,
        null=True, blank=True`, `related_name="payslips"` — the structure this payslip was computed
        from (calc-engine input/audit trail)
  - [ ] `days_in_period` — PositiveSmallIntegerField()
  - [ ] `days_worked` — PositiveSmallIntegerField() — defaults to `days_in_period` at generation time
        unless overridden (mid-period joiner/leaver pro-ration)
  - [ ] `lop_days` — DecimalField(max_digits=5, decimal_places=2, default=0)
  - [ ] `lop_amount` — DecimalField(max_digits=14, decimal_places=2, default=0, editable=False) —
        derived at generation/`recompute()`
  - [ ] `gross_pay` — DecimalField(max_digits=14, decimal_places=2, default=0, editable=False)
  - [ ] `total_deductions` — DecimalField(max_digits=14, decimal_places=2, default=0, editable=False)
  - [ ] `net_pay` — DecimalField(max_digits=14, decimal_places=2, default=0, editable=False)
  - [ ] `arrears_amount` — DecimalField(max_digits=14, decimal_places=2, default=0) — retroactive pay
        from a back-dated structure revision or new-joinee arrears (Keka/greytHR/Zoho); form-editable
        while cycle is draft
  - [ ] `bonus_amount` — DecimalField(max_digits=14, decimal_places=2, default=0) — performance bonus/
        ex-gratia, taxed as a normal earning (Gusto/Keka/factoHR); form-editable while cycle is draft
  - [ ] `on_hold` — BooleanField(default=False) — Salary Holds bullet (Keka "Salary on Hold", greytHR
        "Hold Salary Payout") — payslip still computed for statutory-compliance totals, excluded from
        disbursement (disbursement/bank-file itself is out of scope)
  - [ ] `hold_reason` — TextField(blank=True)
  - [ ] `released_at` — DateTimeField(null=True, blank=True, editable=False)
  - [ ] NO independent status field — "locked" is derived from `self.cycle.is_locked` (avoid a second
        state machine per the research's explicit recommendation)
  - [ ] `class Meta`: `ordering = ["cycle", "employee__party__name"]`; `unique_together = ("tenant",
        "cycle", "employee")` — one payslip per employee per cycle; indexes
        `models.Index(fields=["tenant", "cycle"], name="hrm_psl_tenant_cycle_idx")`,
        `models.Index(fields=["tenant", "employee"], name="hrm_psl_tenant_emp_idx")`
  - [ ] `is_locked` **property** → `self.cycle.is_locked`
  - [ ] `recompute()` **method** — the calculation engine (see spec below); (re)derives
        `gross_pay`/`total_deductions`/`net_pay`/`lop_amount`, rebuilds this payslip's `PayslipLine`
        rows (delete existing lines for this payslip, recreate from resolved structure lines +
        arrears/bonus/LOP), then `self.save(update_fields=[...])`. Callable standalone (used by both
        `payrollcycle_generate` for the initial build and `payslip_edit` after an arrears/bonus/
        days_worked/lop_days change) — **must raise/guard against being called when
        `self.cycle.is_locked`** (a locked cycle's payslips are immutable)
  - [ ] `__str__` → `f"{self.number} · {self.employee} · {self.cycle.number}"`

- [ ] `PayslipLine(TenantOwned)` — per-component snapshot, no own number:
  - [ ] `payslip` — FK `"hrm.Payslip"`, `on_delete=models.CASCADE`, `related_name="lines"`
  - [ ] `component_name` — CharField(max_length=150) — copied string label, NOT a live FK to
        `PayComponent` (so a later component rename/edit never rewrites historical payslips —
        Workday's immutable payroll-results-worklet convention)
  - [ ] `component_type` — CharField(max_length=20, choices=`COMPONENT_TYPE_CHOICES`) — union of
        `PayComponent.COMPONENT_TYPE_CHOICES` (`earning`/`statutory_deduction`/`voluntary_deduction`/
        `reimbursement`/`variable`) **plus** `("arrears","Arrears")`, `("bonus","Bonus")`,
        `("lop","Loss of Pay")` — build this list explicitly in `PayslipLine` (e.g.
        `PayComponent.COMPONENT_TYPE_CHOICES + [("arrears","Arrears"),("bonus","Bonus"),
        ("lop","Loss of Pay")]`) rather than re-typing the base 5, so a future `PayComponent` type
        addition doesn't silently drift out of sync
  - [ ] `amount` — DecimalField(max_digits=14, decimal_places=2) — resolved, pro-rated value for this
        line on this payslip (may be negative for the `lop` line — see calc engine)
  - [ ] `contribution_side` — CharField(max_length=10, choices=`PayComponent.CONTRIBUTION_SIDE_CHOICES`,
        blank=True, default="") — snapshotted from the source `PayComponent.contribution_side` (blank
        for arrears/bonus/lop synthetic lines) so `payrollcycle_lock`'s employee-tax-vs-employer-tax
        roll-up doesn't need to re-join back to `PayComponent`/`SalaryStructureLine` after the fact
  - [ ] `sequence` — PositiveSmallIntegerField(default=0)
  - [ ] `class Meta`: `ordering = ["sequence", "id"]`; index `models.Index(fields=["tenant",
        "payslip"], name="hrm_psll_tenant_payslip_idx")`
  - [ ] `__str__` → `f"{self.payslip} · {self.component_name}"`

- [ ] one incremental migration `apps/hrm/migrations/0025_payrollcycle_payslip_payslipline_and_more.py`
      (NOT `0001_initial`; last is `0024_paycomponent_salarystructuretemplate_and_more.py`) —
      `makemigrations hrm`, review the generated file, adjust index/constraint names to match the ones
      specified above if Django's auto-names differ

## Calculation engine — spec `Payslip.recompute()` exactly this way

- [ ] guard: if `self.cycle.is_locked` → raise (e.g. `ValidationError`/a plain `RuntimeError` — pick
      one and use it consistently across `recompute()` and the generate/edit views) — a locked cycle's
      payslips are immutable; corrections need a new `off_cycle` `PayrollCycle`
- [ ] resolve the employee's active structure lines: `structure = self.salary_structure`; if
      `structure` and `structure.template_id`: `lines = structure.template.lines.select_related(
      "pay_component").order_by("sequence", "id")`; else `lines = []` (no structure → zero earnings,
      payslip still exists so headcount/hold state is trackable)
- [ ] convert each line's annual `resolved_amount()` to a **monthly** amount:
      `monthly = (line.resolved_amount() / Decimal("12")).quantize(Decimal("0.01"))`
- [ ] split lines into EARNINGS (`pay_component.component_type in
      {"earning","reimbursement","variable"}`) vs DEDUCTIONS (`component_type in
      {"statutory_deduction","voluntary_deduction"}`)
- [ ] pro-rate EARNINGS only by `ratio = Decimal(self.days_worked) / Decimal(self.days_in_period)` if
      `self.days_in_period` else `Decimal("1")` (default `days_worked = days_in_period` at generation
      unless explicitly overridden — mid-period joiner/leaver case); DEDUCTIONS are NOT pro-rated by
      days_worked (statutory deductions are computed on the pro-rated gross downstream, not
      double-pro-rated — keep this simple: deductions resolve off the component's own
      `resolved_amount()`/12 unmodified for v1, note this as a v1 simplification matching the
      "generic statutory line" scope, not a full attendance-linked deduction proration engine)
- [ ] `period_gross = sum(pro-rated earning amounts)` (before LOP/arrears/bonus)
- [ ] `lop_amount = ((period_gross / Decimal(self.days_in_period)) * self.lop_days).quantize(
      Decimal("0.01"))` if `self.days_in_period` else `Decimal("0")`
- [ ] `gross_pay = (period_gross - lop_amount + self.arrears_amount + self.bonus_amount).quantize(
      Decimal("0.01"))`
- [ ] `total_deductions = sum(deduction line monthly amounts).quantize(Decimal("0.01"))`
- [ ] `net_pay = (gross_pay - total_deductions).quantize(Decimal("0.01"))`
- [ ] rebuild `PayslipLine`s: `self.lines.all().delete()`, then bulk-create:
  - [ ] one line per pro-rated EARNING (`component_type=pay_component.component_type`,
        `component_name=pay_component.name`, `amount=` the pro-rated value,
        `contribution_side=pay_component.contribution_side`, `sequence=pay_component.display_order`)
  - [ ] one line per DEDUCTION (same shape, `amount=` the resolved monthly deduction, negative sign
        convention documented — pick **positive magnitude with `component_type` distinguishing sign
        semantics** (i.e. store deductions as positive numbers, the type tells you it's a deduction) to
        match the existing `SalaryStructureLine`/`PayComponent` convention of no signed amounts; note
        this explicitly in the model docstring
  - [ ] an `arrears` line (`component_type="arrears"`, `component_name="Arrears"`,
        `amount=self.arrears_amount`) only if `self.arrears_amount != 0`
  - [ ] a `bonus` line (`component_type="bonus"`, `component_name="Bonus"`,
        `amount=self.bonus_amount`) only if `self.bonus_amount != 0`
  - [ ] a `lop` line (`component_type="lop"`, `component_name="Loss of Pay"`,
        `amount=self.lop_amount`) only if `self.lop_amount != 0`
  - [ ] use consistent `sequence` numbering so the payslip renders earnings, then arrears/bonus, then
        LOP, then deductions in a sensible print order (e.g. earnings 1-89, arrears/bonus 90-94, lop
        95, deductions 100+)
- [ ] `self.gross_pay`, `self.total_deductions`, `self.net_pay`, `self.lop_amount` set on the instance;
      `self.save(update_fields=["gross_pay","total_deductions","net_pay","lop_amount","updated_at"])`
- [ ] use `Decimal` throughout (never float); `.quantize(Decimal("0.01"))` at every derived-amount step
      per the research's explicit convention

## `payrollcycle_generate` — the batch driver around `recompute()`

- [ ] `@login_required`, `@require_POST` view, only runs while `cycle.status == "draft"` (else
      `messages.error` + redirect to detail — regeneration is draft-only, matches Keka's rollback
      convention: correction after lock needs a new off-cycle cycle)
- [ ] inside `transaction.atomic()`:
  - [ ] delete existing `cycle.payslips.all()` (cascades their `PayslipLine`s) — safe re-run/rollback
        while draft
  - [ ] for each `hrm.EmployeeProfile` in `tenant` that has an `EmployeeSalaryStructure` with
        `status="active"` as of `cycle.period_end` (i.e. `effective_from <= cycle.period_end` and
        (`effective_to` is null or `effective_to >= cycle.period_start`) — pick the simpler
        `status="active"` filter as the v1 baseline per the research's "Include/exclude headcount by
        pay group" table-stakes note; document the date-window refinement as a fast-follow if the
        simpler filter is used):
    - [ ] `Payslip.objects.create(tenant=tenant, cycle=cycle, employee=employee,
          salary_structure=structure, days_in_period=<days in cycle.period_start..period_end
          inclusive>, days_worked=days_in_period)`
    - [ ] call `payslip.recompute()` immediately after create
  - [ ] `write_audit_log(request.user, cycle, "update", {"action": "generate", "headcount": N})`
- [ ] redirect to `payrollcycle_detail`; `messages.success` with the generated headcount

## Approval workflow + hand-off (POST actions, mirror the 3.12 `FloatingHolidayElection` pattern)

- [ ] `payrollcycle_submit` (`@login_required`, `@require_POST`) — only from `status="draft"`;
      set `status="pending_approval"`, `submitted_by=request.user`, `submitted_at=timezone.now()`;
      **decision (documented per the brief):** an `off_cycle`/`bonus` `cycle_type` MAY skip approval —
      allow this same view to detect `cycle.cycle_type != "regular"` and go straight to submit-and-lock
      in one action if a `request.POST.get("skip_approval")` flag (or simply: for non-regular cycles,
      submit transitions directly to `"approved"` instead of `"pending_approval"`, then a separate lock
      action still required) — **pick the simpler rule: non-regular cycles submit straight to
      `"approved"`** (still requires an explicit `payrollcycle_lock` call to actually hand off to
      accounting — lock is never implicit); write this decision into the view's docstring so it's not
      re-litigated later
- [ ] `payrollcycle_approve` (`@tenant_admin_required`, `@require_POST`) — only from
      `status="pending_approval"`; set `status="approved"`, `approved_by=request.user`,
      `approved_at=timezone.now()`; `write_audit_log(..., "update", {"action": "approve"})`
- [ ] `payrollcycle_reject` (`@tenant_admin_required`, `@require_POST`) — only from
      `status="pending_approval"`; set `status="rejected"`, `approved_by=request.user`,
      `rejection_reason=request.POST.get("rejection_reason", "").strip()[:2000]`;
      `write_audit_log(..., "update", {"action": "reject"})` — mirror
      `floatingholidayelection_reject`'s truncation/no-op-if-not-pending pattern exactly
- [ ] `payrollcycle_lock` (`@tenant_admin_required`, `@require_POST`) — only from `status="approved"`;
      inside `transaction.atomic()`:
  - [ ] roll up across `cycle.payslips.select_related(None).prefetch_related("lines")`:
    - [ ] `headcount = cycle.payslips.count()`
    - [ ] `gross_wages = cycle.payslips.aggregate(Sum("gross_pay"))["gross_pay__sum"] or Decimal("0")`
    - [ ] `employee_tax = ` sum of `PayslipLine.amount` where
          `component_type="statutory_deduction"` and `contribution_side="employee"` across all of the
          cycle's payslips (`PayslipLine.objects.filter(payslip__cycle=cycle,
          component_type="statutory_deduction", contribution_side="employee").aggregate(
          Sum("amount"))`)
    - [ ] `employer_tax = ` same filter with `contribution_side="employer"`
    - [ ] `deductions = ` sum of `PayslipLine.amount` where `component_type="voluntary_deduction"`
          (regardless of side) across the cycle's payslips
    - [ ] `benefits = Decimal("0")` for v1 (no benefits-specific component_type modeled yet — note this
          as a placeholder the accounting form already defaults; `PayrollRun.benefits` stays 0 unless a
          later pass adds a benefits component_type)
    - [ ] holds still count toward these totals (Keka/greytHR: held salaries still hit statutory
          totals) — do NOT exclude `on_hold` payslips from the roll-up
  - [ ] `from apps.accounting.models_advanced import PayrollRun as AccountingPayrollRun` (import at
        top of `apps/hrm/models.py` or inside the view — **prefer a lazy import inside the view/method**
        to avoid a hard cross-app import at module load time; verify no circular-import issue exists
        first, else use `django.apps.apps.get_model("accounting", "PayrollRun")`)
  - [ ] `accounting_run = AccountingPayrollRun.objects.create(tenant=request.tenant,
        period_start=cycle.period_start, period_end=cycle.period_end, pay_date=cycle.pay_date,
        headcount=headcount, gross_wages=gross_wages, employee_tax=employee_tax,
        employer_tax=employer_tax, benefits=Decimal("0"), deductions=deductions)` — `net_pay` is
        derived by `AccountingPayrollRun.save()` automatically; `status` stays its model default
        (`"draft"`) — **HRM never sets `status="posted"` or builds a `JournalEntry`**
  - [ ] `cycle.accounting_payroll_run = accounting_run`; `cycle.status = "locked"`; save both with
        explicit `update_fields`
  - [ ] `write_audit_log(request.user, cycle, "update", {"action": "lock", "accounting_payroll_run":
        accounting_run.number})`
  - [ ] `messages.success` linking to the created accounting PayrollRun (e.g. "Locked — created
        accounting PayrollRun {number}, post it from Accounting → Payroll to generate the GL entry.")

## Salary holds

- [ ] `payslip_hold` (`@tenant_admin_required`, `@require_POST`) — gate: allowed while
      `payslip.cycle.status in {"draft", "pending_approval", "approved"}` (i.e. anytime BEFORE
      `locked` — a hold is a pre-disbursement decision; once the cycle is locked and handed to
      accounting, a hold no longer has meaning for that payslip — document this gate choice in the
      view's docstring since the brief flags it as "your call"); set `on_hold=True`,
      `hold_reason=request.POST.get("hold_reason","").strip()[:2000]`; `write_audit_log(...,
      {"action": "hold"})`
- [ ] `payslip_release` (`@tenant_admin_required`, `@require_POST`) — same gate (not locked); set
      `on_hold=False`, `released_at=timezone.now()`; keep `hold_reason` as history (don't clear it);
      `write_audit_log(..., {"action": "release"})`
- [ ] both redirect to `payslip_detail`

## Payslip edit (arrears/bonus/hold-adjacent fields, draft-cycle only)

- [ ] `payslip_edit` (`@login_required`) — only while `payslip.cycle.status == "draft"` (else
      `messages.error` "A locked/submitted cycle's payslips cannot be edited." + redirect to detail);
      `PayslipForm` covers `days_worked`, `lop_days`, `arrears_amount`, `bonus_amount` (NOT `on_hold`/
      `hold_reason` — those go through the dedicated hold/release actions, not a generic edit form);
      on valid POST save, call `obj.recompute()` immediately after `form.save()` so gross/deductions/
      net + lines reflect the new inputs before redirecting to `payslip_detail`

## B. Forms (`apps/hrm/forms.py`)

- [ ] `PayrollCycleForm(TenantModelForm)`:
  - [ ] `Meta.fields = ["period_start", "period_end", "pay_date", "cycle_type", "notes"]` (exclude
        `number`/`status`/`submitted_by`/`submitted_at`/`approved_by`/`approved_at`/
        `rejection_reason`/`accounting_payroll_run` — all workflow/derived, never form fields)
  - [ ] no custom `__init__` needed (no FK dropdowns to narrow)
- [ ] `PayslipForm(TenantModelForm)`:
  - [ ] `Meta.fields = ["days_worked", "lop_days", "arrears_amount", "bonus_amount"]` (exclude
        `cycle`/`employee`/`salary_structure`/`days_in_period`/`lop_amount`/`gross_pay`/
        `total_deductions`/`net_pay`/`on_hold`/`hold_reason`/`released_at` — set by the view/generate
        flow or the dedicated hold/release actions, never generic-form-editable)
  - [ ] no create view for `Payslip` (payslips are only created via `payrollcycle_generate`) — this
        form is edit-only

## C. Views (`apps/hrm/views.py`)

- [ ] `payrollcycle_list` (`@login_required`) — `crud_list(request,
      PayrollCycle.objects.filter(tenant=request.tenant), "hrm/payroll/payrollcycle/list.html",
      search_fields=["number", "notes"], filters=[("status", "status", False), ("cycle_type",
      "cycle_type", False)], extra_context={"status_choices": PayrollCycle.STATUS_CHOICES,
      "cycle_type_choices": PayrollCycle.CYCLE_TYPE_CHOICES})`
- [ ] `payrollcycle_create` — standard `crud_create` wrapper (`PayrollCycleForm`, template
      `hrm/payroll/payrollcycle/form.html`, success_url `hrm:payrollcycle_detail` of the new obj —
      note `crud_create` redirects to a fixed `success_url` string; if a post-create redirect to the
      new detail page (not the list) is wanted, mirror however 3.13's `salarystructuretemplate_create`
      does it — verify and match that exact pattern rather than inventing a new one)
- [ ] `payrollcycle_edit` — standard `crud_edit` wrapper, only while `status == "draft"` (else
      `messages.error` + redirect to detail, mirror the `floatingholidayelection_edit` pending-only
      guard pattern exactly)
- [ ] `payrollcycle_delete` (`@login_required`, `@require_POST`) — only while `status == "draft"` AND
      it has no payslips yet (or cascades its payslips — CASCADE FK means deleting the cycle deletes
      its payslips; guard: only allow delete while `draft`, mirror the
      `floatingholidayelection_delete` decided-lock pattern) — else `messages.error` + redirect
- [ ] `payrollcycle_detail` (`@login_required`) — `crud_detail(request, model=PayrollCycle, pk=pk,
      template="hrm/payroll/payrollcycle/detail.html")`; extra_context adds `"payslips":
      cycle.payslips.select_related("employee__party").order_by("employee__party__name")` (the
      cycle-detail hub lists all payslips with links to their detail pages) + the derived
      `total_gross`/`total_deductions`/`total_net`/`headcount` rendered from the model properties
- [ ] `payrollcycle_generate` (`@login_required`, `@require_POST`) — per the Calculation Engine spec
      above
- [ ] `payrollcycle_submit` / `_approve` / `_reject` / `_lock` — per the Approval Workflow spec above
- [ ] `payslip_list` (`@login_required`) — global cross-cycle list for the Salary Holds / Arrears
      Calculation / Bonus Processing nav deep-links: `crud_list(request,
      Payslip.objects.filter(tenant=request.tenant).select_related("cycle", "employee__party"),
      "hrm/payroll/payslip/list.html", search_fields=["number", "employee__party__name"],
      filters=[("cycle", "cycle_id", True), ("employee", "employee_id", True), ("on_hold", "on_hold",
      False)], extra_context={"cycles": PayrollCycle.objects.filter(tenant=request.tenant),
      "employees": EmployeeProfile.objects.filter(tenant=request.tenant)})`
- [ ] `payslip_detail` (`@login_required`) — `crud_detail(request, model=Payslip, pk=pk,
      template="hrm/payroll/payslip/detail.html", select_related=("cycle", "employee__party",
      "salary_structure"))`; extra_context adds `"lines": obj.lines.order_by("sequence", "id")`
- [ ] `payslip_edit` — per the Payslip Edit spec above (draft-cycle-only gate + `recompute()` call
      after save)
- [ ] `payslip_hold` / `payslip_release` — per the Salary Holds spec above
- [ ] NO `payslip_create`/`payslip_delete` standalone views — payslips are lifecycle-managed via
      `payrollcycle_generate` (create) and cascade-delete with their cycle; a delete-one-payslip action
      is out of scope (regenerate the whole cycle instead, matches the draft-only regenerate rule)
- [ ] all new views import `PayrollCycle`, `Payslip`, `PayslipLine`, `PayrollCycleForm`, `PayslipForm`
      at the top of `views.py` alongside the existing HRM imports; import `transaction` from
      `django.db`, `Sum` from `django.db.models` if not already imported

## D. URLs (`apps/hrm/urls.py`, `app_name = "hrm"` already set)

- [ ] `path("payroll-cycles/", views.payrollcycle_list, name="payrollcycle_list")`
- [ ] `path("payroll-cycles/add/", views.payrollcycle_create, name="payrollcycle_create")`
- [ ] `path("payroll-cycles/<int:pk>/", views.payrollcycle_detail, name="payrollcycle_detail")`
- [ ] `path("payroll-cycles/<int:pk>/edit/", views.payrollcycle_edit, name="payrollcycle_edit")`
- [ ] `path("payroll-cycles/<int:pk>/delete/", views.payrollcycle_delete, name="payrollcycle_delete")`
- [ ] `path("payroll-cycles/<int:pk>/generate/", views.payrollcycle_generate, name="payrollcycle_generate")`
- [ ] `path("payroll-cycles/<int:pk>/submit/", views.payrollcycle_submit, name="payrollcycle_submit")`
- [ ] `path("payroll-cycles/<int:pk>/approve/", views.payrollcycle_approve, name="payrollcycle_approve")`
- [ ] `path("payroll-cycles/<int:pk>/reject/", views.payrollcycle_reject, name="payrollcycle_reject")`
- [ ] `path("payroll-cycles/<int:pk>/lock/", views.payrollcycle_lock, name="payrollcycle_lock")`
- [ ] `path("payslips/", views.payslip_list, name="payslip_list")`
- [ ] `path("payslips/<int:pk>/", views.payslip_detail, name="payslip_detail")`
- [ ] `path("payslips/<int:pk>/edit/", views.payslip_edit, name="payslip_edit")`
- [ ] `path("payslips/<int:pk>/hold/", views.payslip_hold, name="payslip_hold")`
- [ ] `path("payslips/<int:pk>/release/", views.payslip_release, name="payslip_release")`

## E. Admin (`apps/hrm/admin.py`)

- [ ] register `PayrollCycle` — `list_display = ("number", "cycle_type", "period_start",
      "period_end", "pay_date", "status", "accounting_payroll_run")`, `list_filter = ("tenant",
      "cycle_type", "status")`, `search_fields = ("number", "notes")`
- [ ] register `Payslip` — `list_display = ("number", "cycle", "employee", "gross_pay",
      "total_deductions", "net_pay", "on_hold")`, `list_filter = ("tenant", "on_hold")`,
      `search_fields = ("number", "employee__party__name")` (verify exact lookup path matches
      `employeesalarystructure` admin's confirmed path from 3.13)
- [ ] register `PayslipLine` as a `TabularInline` on `PayslipAdmin` (`model = PayslipLine`,
      `extra = 0`, `fields = ("component_name", "component_type", "amount", "contribution_side",
      "sequence")`, `readonly_fields` matching since these are snapshot rows) — also register a thin
      standalone `PayslipLineAdmin` for direct lookup if useful (optional)

## F. Templates (`templates/hrm/payroll/<entity>/<page>.html`)

- [ ] `payroll/payrollcycle/list.html` — filter bar: search `q`, `status` select (from
      `status_choices`), `cycle_type` select (from `cycle_type_choices`); columns: number, cycle_type
      badge, period_start–period_end, pay_date, status badge, headcount, total_net, Actions
      (view/edit-if-draft/delete-if-draft); pagination include; empty-state. Badge classes (**L33,
      colour-named**): `draft`→`badge-muted`, `pending_approval`→`badge-amber`, `approved`→
      `badge-info`, `rejected`→`badge-red`, `locked`→`badge-green`; `cycle_type`:
      `regular`→`badge-info`, `off_cycle`→`badge-amber`, `bonus`→`badge-slate`; always
      `{% else %}{{ obj.get_status_display }}` / `{{ obj.get_cycle_type_display }}` fallback
- [ ] `payroll/payrollcycle/detail.html` — the **cycle-detail hub**: header fields (period, pay_date,
      cycle_type badge, status badge), derived-totals panel (headcount/total_gross/
      total_deductions/total_net), workflow action buttons gated by status (`Generate Payslips` —
      draft only; `Submit for Approval` — draft only, POST+confirm+csrf; `Approve`/`Reject` —
      pending_approval only, tenant-admin, POST+confirm+csrf, reject includes a `rejection_reason`
      textarea; `Lock & Hand Off to Accounting` — approved only, tenant-admin, POST+confirm+csrf,
      confirm text warns this is irreversible); if `accounting_payroll_run` is set, show a link to it
      (`accounting:payrollrun_detail` or whatever its real url name is — verify); **payslip list
      table**: number, employee, gross_pay, total_deductions, net_pay, on_hold badge, link to
      `payslip_detail`; Actions sidebar (Edit-if-draft/Delete-if-draft + Back to List)
- [ ] `payroll/payrollcycle/form.html` — standard form (period_start, period_end, pay_date,
      cycle_type, notes)
- [ ] `payroll/payslip/list.html` — filter bar: search `q`, `cycle` select (from `cycles`,
      `|stringformat:"d"` pk-compare), `employee` select (from `employees`, pk-compare), `on_hold`
      select (True/False); columns: number, cycle, employee, gross_pay, total_deductions, net_pay,
      on_hold badge (`True`→`badge-red "On Hold"`, `False`→`badge-green "Released/Active"`), Actions
      (view/edit-if-draft-cycle); pagination include; empty-state
- [ ] `payroll/payslip/detail.html` — header (cycle link, employee, salary_structure link,
      days_in_period/days_worked, lop_days/lop_amount, arrears_amount, bonus_amount, on_hold badge +
      hold_reason + released_at), derived totals (gross_pay/total_deductions/net_pay), **line
      breakdown table** (component_name, component_type badge, amount, contribution_side, sequence —
      read-only, snapshot data); Actions sidebar: Edit (only if `not obj.is_locked`), Hold/Release POST
      buttons (only if `not obj.is_locked`, toggle based on current `on_hold`), Back to List. Badge
      classes for `component_type`: `earning`→`badge-green`, `statutory_deduction`→`badge-red`,
      `voluntary_deduction`→`badge-amber`, `reimbursement`→`badge-info`, `variable`→`badge-slate`,
      `arrears`→`badge-amber`, `bonus`→`badge-green`, `lop`→`badge-red`; always
      `{% else %}{{ line.get_component_type_display }}` fallback
- [ ] `payroll/payslip/form.html` — standard form (days_worked, lop_days, arrears_amount,
      bonus_amount) with a note that saving triggers an automatic recompute of gross/deductions/net

## G. Seeder (`apps/hrm/management/commands/seed_hrm.py`)

- [ ] add `_seed_payroll(self, tenant, *, flush)` method, called from `handle()` **AFTER**
      `self._seed_salary(tenant, flush=options["flush"])` (payroll generation needs 3.13's
      `EmployeeSalaryStructure` rows to exist first)
- [ ] `if flush:` child-first wipe: `PayslipLine.objects.filter(tenant=tenant).delete()` →
      `Payslip.objects.filter(tenant=tenant).delete()` → `PayrollCycle.objects.filter(
      tenant=tenant).delete()`
- [ ] `if PayrollCycle.objects.filter(tenant=tenant).exists(): self.stdout.write(self.style.NOTICE(
      f"Payroll data already exists for '{tenant.name}'. Use --flush to re-seed.")); return`
- [ ] create 1 `regular` `PayrollCycle` for the current month:
      `period_start=timezone.localdate().replace(day=1)`, `period_end=` the last day of that month
      (use `calendar.monthrange` or the existing date-util pattern already used elsewhere in
      `seed_hrm.py` — check for an existing helper before hand-rolling), `pay_date=period_end`,
      `cycle_type="regular"`, `status="draft"` (or `"pending_approval"` — pick `"draft"` so the demo
      data still allows exercising `generate`/`submit` manually; document the choice)
- [ ] for each `EmployeeProfile` in `tenant` with an `active` `EmployeeSalaryStructure` (reuse the
      3.13-seeded assignment): create a `Payslip` (`days_in_period`/`days_worked` = the days in the
      seeded period) and call `.recompute()` — mirror the `payrollcycle_generate` view's own logic
      (consider factoring a small shared helper if convenient, but a direct call to the same
      `recompute()` method is sufficient and avoids duplicating the calc engine)
- [ ] optionally set one seeded payslip `on_hold=True` with a demo `hold_reason` (e.g. "Pending
      clearance verification.") to exercise the Salary Holds bullet in seeded data
- [ ] print a summary line: `f"Payroll seeded for '{tenant.name}': 1 cycle ({cycle.number}),
      {Payslip.objects.filter(tenant=tenant).count()} payslip(s)."`
- [ ] add the 3 models to the `--flush` wipe order in dependency sequence (children first):
      `PayslipLine` → `Payslip` → `PayrollCycle` (already specified above — restate here for the
      flush-order checklist)
- [ ] verify the seeder still prints the tenant-admin login reminder + "Data already exists" warning
      path unchanged — the new block is itself idempotent, no new top-level guard needed

## H. Navigation (`apps/core/navigation.py`)

- [ ] add `LIVE_LINKS["3.14"]` (verify the exact query-string highlighting convention against 3.11/
      3.13's existing entries before finalizing):
      ```python
      # 3.14 Payroll Processing — one PayrollCycle/Payslip surface serves all 5 bullets via
      # deep-linked query params (mirrors 3.13's ?component_type= pattern).
      "3.14": {
          "Payroll Run": "hrm:payrollcycle_list",                                   # bullet
          "Payroll Approval": "hrm:payrollcycle_list?status=pending_approval",      # bullet
          "Salary Holds": "hrm:payslip_list?on_hold=True",                         # bullet
          "Arrears Calculation": "hrm:payslip_list",                               # bullet (arrears entered on the payslip)
          "Bonus Processing": "hrm:payrollcycle_list?cycle_type=bonus",             # bullet
      },
      ```
      — all 5 NavERP.md 3.14 bullets go Live; adjust the literal query strings if the real filter
      param names implemented in Section C differ (e.g. confirm `on_hold` filter accepts the string
      `"True"` per `crud_list`'s boolean-string mapping)

## I. Migrate / seed / verify (run from the venv)

- [ ] `python manage.py makemigrations hrm` → review `0025_...py` (field/index/unique_together names
      match the plan; confirm the `accounting.PayrollRun` FK doesn't trigger a spurious
      cross-app migration dependency issue — it shouldn't since it's a plain FK-by-string)
- [ ] `python manage.py migrate`
- [ ] `python manage.py seed_hrm` (1st run — creates data; confirm 3.13's `_seed_salary` still runs
      first and the new `_seed_payroll` block generates payslips against it)
- [ ] `python manage.py seed_hrm` (2nd run — must be idempotent, no duplicates, no errors)
- [ ] `python manage.py check`
- [ ] `temp/` smoke sweep: every new `hrm:payrollcycle_*` and `hrm:payslip_*` URL returns 200/302 when
      logged in as a tenant admin; no `{#`/`{% comment` leaks in the new templates; cross-tenant IDOR
      check — a `PayrollCycle`/`Payslip` pk belonging to tenant A returns 404 when fetched as tenant B;
      `payrollcycle_generate` run twice while draft produces the same headcount (regeneration replaces,
      doesn't duplicate); `payrollcycle_lock` creates exactly one `accounting.PayrollRun` row with the
      correct rolled-up totals (spot-check `gross_wages`/`employee_tax`/`employer_tax`/`deductions`
      arithmetic against the seeded payslip(s) by hand); a second `lock` attempt on an already-locked
      cycle is a no-op (guarded by the `status="approved"` precondition); `payslip_edit`/`payslip_hold`/
      `payslip_release` are blocked (error message, no mutation) once the parent cycle is `locked`;
      `payrollcycle_edit`/`_delete` are blocked once not `draft`; non-admin user gets 403 on
      approve/reject/lock/hold/release (`@tenant_admin_required`); the `?status=pending_approval`,
      `?on_hold=True`, `?cycle_type=bonus` deep-links each render the filtered subset correctly
- [ ] sidebar: confirm 3.14 shows all five bullets as **Live** (not "Coming soon") for a tenant with
      data

## J. Close-out

- [ ] update `README.md` module-status / HRM section (3.14 bullets: Payroll Run / Payroll Approval /
      Salary Holds / Arrears Calculation / Bonus Processing all live; bump the HRM + project-wide
      test-count lines once test-writer runs)
- [ ] run the review-agent sequence in order, each ending in its own commit(s): `code-reviewer` →
      `explorer` → `frontend-reviewer` → `performance-reviewer` → `qa-smoke-tester` →
      `security-reviewer` → `test-writer`
- [ ] update `.claude/skills/hrm/SKILL.md` — 3.14 section: document `PayrollCycle`/`Payslip`/
      `PayslipLine` models, the `recompute()` calculation-engine contract, the approve/reject/lock
      workflow + the `accounting.PayrollRun` hand-off (and that HRM never builds a `JournalEntry` —
      L29), the salary-hold gate rule, the new `LIVE_LINKS["3.14"]` entries (incl. the deep-links), the
      extended seeder block, and mark all 5 bullets of 3.14 as built

## Later passes / deferred (carried over from research-payroll.md — do not build this pass)

- **Full statutory engine** (PF/ESI/PT/TDS slabs, challans, returns, Form 16) — NavERP.md **3.15
  Statutory Compliance**, a separate sub-module; this pass only stores generic
  `statutory_deduction`/`employer`-contribution amounts already modeled by `PayComponent`.
- **Bank file / NEFT / direct-deposit disbursement generation** — external banking integration (ADP,
  Rippling, Gusto, greytHR); out of a single Django pass.
- **Tax-slab TDS/withholding computation engine** — needs annual tax-regime rules (NavERP.md 3.16 Tax
  & Investment); this pass stores the deduction amount but does not compute it from a slab table.
- **Payslip PDF rendering + email delivery + employee self-service download portal** — templating/PDF
  generation and email dispatch; defer to an integration pass.
- **Configurable N-level approval criteria engine** (Zoho's WHEN/AND/OR custom approval builder) — v1
  ships a fixed submit→approve/reject two-step (with the off_cycle/bonus straight-to-approved shortcut
  documented above); a rules-based configurable chain is differentiator/deferred.
- **Automatic arrears computation by diffing salary-structure history** — v1 takes `arrears_amount` as
  a manually-entered value on the payslip (edited via `PayslipForm` while draft); an automated "detect
  every back-dated structure change since the last processed cycle and compute the exact delta" engine
  is a fast-follow, not blocking.
- **Rollback/re-run UX for a subset of employees within a locked cycle** (Keka) — v1 only allows
  regenerate-while-draft (the whole cycle, not per-employee); once `locked`, a correction requires a
  new `off_cycle` `PayrollCycle` (matches Workday's "corrections require off-cycle processing"
  convention) rather than in-place edits.
- **Multi-currency payroll** — `SalaryStructureTemplate.currency` stays a plain CharField (per 3.13);
  `PayrollCycle`/`Payslip` assume single-currency per tenant, consistent with that.
- **YTD tax projection / cumulative annual payslip aggregation view** — useful (Deel, Workday) but a
  reporting concern layered on top of per-cycle `Payslip` rows already being retained; can be added as
  a query/report later without new models.
- **Formula/criteria-driven incentive calculation** (factoHR's target-based bonus %) — store the
  resulting `bonus_amount`, don't build the rules/target-tracking engine.
- **LOP wired automatically to actual unpaid-leave records from 3.10** (Leave module) — v1 takes
  `lop_days` as a manually-entered field on the payslip; auto-pulling confirmed unpaid-leave days from
  `hrm.LeaveRequest`/attendance is a fast-follow integration, not blocking.
- **`accounting.PayrollRun` extension** (a cleaner "post directly from HRM" helper instead of leaving
  posting in accounting's existing UI) — a small accounting-side follow-up, not part of this HRM pass;
  HRM only creates the `draft` row and links it, accounting's own `payroll_run_post` view still does
  the actual GL posting.
- **Two distinct hold outcomes ("pay later" vs. "void/never pay")** (Keka) — v1 ships a single
  `on_hold`/`hold_reason`/`released_at` flag set; a `hold_resolution` choice
  (`pending`/`release_next_cycle`/`void`) is deferred unless a later pass needs the distinction.

## Review

**Delivered (2026-07-04):** HRM 3.14 Payroll Processing — the operational payroll run. All 5 NavERP.md bullets Live.
3 new models; the L29 boundary respected (HRM computes; `accounting.PayrollRun` posts the GL).
- **`PayrollCycle`** (`PRC-`) — run header + `draft→pending_approval→approved/rejected→locked` workflow;
  cycle_type regular/off_cycle/bonus (non-regular skip approval); derived totals (single aggregate); on lock creates
  a draft `accounting.PayrollRun` with rolled-up totals + links it.
- **`Payslip`** (`PSL-`) — per (cycle,employee); `recompute()` calc engine (monthly-from-CTC, day pro-ration, LOP,
  arrears/bonus; employer-side statutory excluded from net; pct lines scaled by the employee's assigned CTC); holds.
- **`PayslipLine`** — immutable component snapshot (name/type/amount/contribution_side) so a later structure edit
  never rewrites history.
- Migration `0025`; `_seed_payroll` (1 regular cycle, 3 generated payslips, 1 on hold; central flush wipes payslips
  before EmployeeProfile for the PROTECT FK); `LIVE_LINKS["3.14"]` → all 5 bullets.

**Verification:** own smoke test 0 failures — full lifecycle generate→submit→approve→lock created accounting run
PRUN-#### with penny-perfect totals (gross/employer_tax/net reconcile), immutable-after-lock, holds, arrears
recompute, IDOR→404, filters, sidebar Live.

**Module Creation Sequence — all 7 review agents, one at a time, findings applied + committed:**
- **code-reviewer** — 0 Critical. Fixed 6 Important: lock roll-up buckets employee_tax/deductions as "not
  employer-side" (so accounting net reconciles with Σ payslip net, incl. `both`); `resolved_amount(ctc=)` scales pct
  lines by the employee's CTC (different-CTC employees now differ); `Payslip.clean()` (days/negative guards);
  generate adds an effective-date window + preserves manual arrears/bonus/hold across a re-generate; + Minor badge.
  (Also fixed a seeder --flush ProtectedError the on_stop hook caught — payslips wiped before EmployeeProfile.)
- **explorer** — all 7 wiring seams clean; zero `JournalEntry` construction in HRM (L29 confirmed). No fixes.
- **frontend-reviewer** — 1 Critical: privileged buttons (approve/reject/lock/hold/release) rendered for everyone →
  gated behind `is_superuser or is_tenant_admin` with an awaiting-admin notice (matches the app-wide convention incl.
  accounting's own payroll template; the 2 stragglers spun off as a task).
- **performance-reviewer** — the generate loop is O(N), no hidden multiplier (FK cache warm). Fixed 1 Minor:
  `payslip_edit` select_related's the structure+template so the post-save recompute() doesn't re-fetch.
- **qa-smoke-tester** — **79/79** green; verified the accounting reconciliation (net == Σ payslip net, run stays
  draft, no JE) and the admin-gating (template + 403). No code changes.
- **security-reviewer** — no vulnerabilities (IDOR, authz, CSRF, mass-assignment, XSS, injection, hand-off integrity
  all correct). One app-wide authz-policy observation (already covered by a spawned task).
- **test-writer** — **+109 tests** (35 model/calc + 54 view + 20 security): recompute arithmetic + employer-exclusion
  + CTC-scaling, the lock penny-reconciliation, workflow guards, non-admin 403, immutability, IDOR. Full HRM suite
  **2,221 passed / 0 failed** (was 2,112); project-wide **4,868**.

**Follow-up tasks spawned (app-wide, not forked into 3.14):** gate the 2 straggler approve/reject templates
(leaverequest, floatingholidayelection); tenant-admin gate on sensitive HRM writes (carried from 3.13).

**Next:** 3.15 Statutory Compliance (PF/ESI/PT/TDS challans & returns over the payroll runs).

---
# Module 3 — HRM — Sub-module 3.15 Statutory Compliance (statutory-compliance) — plan from research-statutory-compliance.md (2026-07-04)

**Context.** Extends the existing `apps/hrm` app — NOT a new app. Builds the **compliance/reporting/
configuration** layer on top of 3.13 (`PayComponent`/`SalaryStructureTemplate`) and 3.14
(`PayrollCycle`/`Payslip`/`PayslipLine`). This is explicitly NOT a second payroll engine — it does not
recompute or re-store per-employee statutory amounts (those already live on `PayslipLine`); it adds
tenant-wide registration/config, state-wise PT+LWF slab rules, per-employee government identifiers
(UAN/PF/ESI numbers), and a shared per-scheme/per-period return/challan-tracking record that
**aggregates already-computed `PayslipLine` totals** — mirroring `PayrollCycle._totals()`'s
aggregate-and-cache convention and `payrollcycle_lock`'s employee-tax/employer-tax roll-up query. 4 new
models, all in `apps/hrm/models.py`. Money still posts only through `accounting.PayrollRun`/
`JournalEntry` (L29) — this sub-module never touches either.

NavERP.md 3.15 bullets (exact text, all 5 go Live this pass):
- PF Management — PF calculation, challan, returns.
- ESI Management — ESI calculation, contributions.
- PT Management — Professional tax, state-wise rules.
- TDS Management — Tax calculation, Form 16, quarterly returns.
- LWF Management — Labour welfare fund.

Reuses (no duplication): `hrm.EmployeeProfile` (incl. `national_id`/`national_id_type` for PAN,
`employee_type`), `hrm.PayrollCycle`, `hrm.Payslip`/`PayslipLine` (`component_type`,
`contribution_side`, `amount`), `hrm.PayComponent`, `settings.AUTH_USER_MODEL` (audit only via
`write_audit_log`). Never touches `accounting.PayrollRun`/`JournalEntry` — this sub-module builds no
GL-posting path (L29).

## A. Models + migration (`apps/hrm/models.py`)

- [ ] `StatutoryConfig(TenantOwned)` — tenant-wide settings singleton, no numeric prefix (drivers: Zoho
      Payroll's single Statutory Components screen; RazorpayX registration management; greytHR/ClearTax
      Form 16 TAN config):
  - [ ] `pf_establishment_code` — CharField(max_length=50, blank=True) — PF Management (Zoho: PF
        establishment code)
  - [ ] `pf_wage_ceiling` — DecimalField(max_digits=12, decimal_places=2, default=Decimal("15000.00"))
        — PF Management (Zoho: ₹15,000 Basic+DA ceiling)
  - [ ] `pf_employee_rate` — DecimalField(max_digits=5, decimal_places=2, default=Decimal("12.00")) —
        PF Management
  - [ ] `pf_employer_rate` — DecimalField(max_digits=5, decimal_places=2, default=Decimal("12.00")) —
        PF Management
  - [ ] `esi_employer_code` — CharField(max_length=50, blank=True) — ESI Management (Zoho: ESI number)
  - [ ] `esi_wage_ceiling` — DecimalField(max_digits=12, decimal_places=2, default=Decimal("21000.00"))
        — ESI Management (Zoho: ₹21,000 gross ceiling)
  - [ ] `esi_employee_rate` — DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.75")) —
        ESI Management
  - [ ] `esi_employer_rate` — DecimalField(max_digits=5, decimal_places=2, default=Decimal("3.25")) —
        ESI Management
  - [ ] `pt_default_state` — CharField(max_length=50, choices=`INDIAN_STATE_CHOICES`, blank=True) — PT
        Management fallback when an employee's own `pt_state` can't be resolved
  - [ ] `tan_number` — CharField(max_length=20, blank=True) — TDS Management (employer TAN, mandatory
        on Form 24Q/16, distinct from PAN)
  - [ ] `tds_circle_address` — TextField(blank=True) — TDS Management (greytHR Form 16 config: TDS
        circle address)
  - [ ] `pan_of_deductor` — CharField(max_length=10, blank=True) — TDS Management (the employer's own
        PAN, distinct from `EmployeeProfile.national_id` which is the *employee's* PAN)
  - [ ] `is_lwf_applicable` — BooleanField(default=False) — LWF Management, org-wide master switch
        (per-state detail lives on `StatutoryStateRule`)
  - [ ] `tenant` — override the inherited FK to add `unique=True` (one row per tenant, settings-object
        pattern — `tenant = models.OneToOneField("core.Tenant", on_delete=models.CASCADE,
        related_name="hrm_statutory_config")` instead of `TenantOwned`'s plain FK; keep
        `created_at`/`updated_at` via the same mixin)
  - [ ] `class Meta`: no numeric prefix, no `unique_together` beyond the OneToOne
  - [ ] `__str__` → `f"Statutory Config · {self.tenant.name}"`
  - [ ] get-or-create helper: a small `StatutoryConfig.for_tenant(tenant)` classmethod wrapping
        `StatutoryConfig.objects.get_or_create(tenant=tenant)` so every view/seeder call-site is
        consistent (avoid repeating the get_or_create kwargs inline everywhere)

- [ ] `StatutoryStateRule(TenantOwned)` — state-wise PT + LWF slab/rate table, one shared table for
      both state-scoped schemes (drivers: greytHR's editable state-wise PT slab grid; Zimyo/ClearTax/
      saral PayPack LWF state-applicability + periodicity + amount pattern):
  - [ ] `state` — CharField(max_length=50, choices=`INDIAN_STATE_CHOICES`) — a plain choices list of
        India's states/UTs (define `INDIAN_STATE_CHOICES` once near the top of the statutory model
        block, reused by `StatutoryConfig.pt_default_state` and `EmployeeStatutoryIdentifier.pt_state`)
  - [ ] `scheme` — CharField(max_length=10, choices=`[("pt","Professional Tax"),("lwf","Labour Welfare
        Fund")]`)
  - [ ] `income_from` — DecimalField(max_digits=12, decimal_places=2, null=True, blank=True) — PT-only
        (blank/null when `scheme="lwf"`); part of the `unique_together`
  - [ ] `income_to` — DecimalField(max_digits=12, decimal_places=2, null=True, blank=True) — PT-only
  - [ ] `pt_monthly_amount` — DecimalField(max_digits=10, decimal_places=2, null=True, blank=True) —
        PT-only, the tax amount for this income bracket
  - [ ] `pt_deduction_month` — CharField(max_length=20, blank=True) — PT-only, optional (some states
        deduct only in specific months, e.g. an annual lump sum in February)
  - [ ] `lwf_employee_contribution` — DecimalField(max_digits=10, decimal_places=2, null=True,
        blank=True) — LWF-only
  - [ ] `lwf_employer_contribution` — DecimalField(max_digits=10, decimal_places=2, null=True,
        blank=True) — LWF-only
  - [ ] `lwf_periodicity` — CharField(max_length=20, choices=`[("monthly","Monthly"),
        ("half_yearly","Half-Yearly"),("annual","Annual")]`, blank=True) — LWF-only
  - [ ] `lwf_due_month_1` — CharField(max_length=20, blank=True) — LWF-only (e.g. "July")
  - [ ] `lwf_due_month_2` — CharField(max_length=20, blank=True) — LWF-only, nullable-equivalent via
        blank (e.g. "January", for half-yearly states)
  - [ ] `registration_number` — CharField(max_length=50, blank=True) — the state-specific PT/LWF
        employer registration number, where applicable
  - [ ] `is_active` — BooleanField(default=True) — supports the greytHR "Odisha PT discontinued from
        April 2026" pattern: deactivate/supersede, never delete, so prior-period reports stay correct
  - [ ] `effective_from` — DateField(default=timezone.localdate... actually use
        `django.utils.timezone.now().date` via a callable default, or simply
        `models.DateField()` non-null required at creation — pick required, no silent default) —
        supports rate-change history as a new row, not an edit
  - [ ] `class Meta`: `ordering = ["state", "scheme", "income_from"]`; `unique_together = ("tenant",
        "state", "scheme", "income_from")` — for LWF, `income_from` stays `None` so uniqueness is
        effectively `(tenant, state, scheme)` (one active LWF row per state per tenant; supersede via
        `is_active=False` + a new row if a rate changes, don't edit in place; note this constraint
        nuance in the model docstring since `None` participates in `unique_together` per-Django's
        NULL-is-distinct semantics — confirm this is the desired behavior, i.e. **you technically CAN
        have two `income_from=None` LWF rows** for the same `(tenant, state, scheme)` since Postgres
        treats NULLs as distinct in unique constraints; document that `clean()` should additionally
        enforce "at most one `is_active=True` LWF row per `(tenant, state, scheme)`" as an application
        -level guard on top of the DB constraint)
  - [ ] `clean()` — validate PT fields present when `scheme="pt"` (income_from/income_to/
        pt_monthly_amount required), LWF fields present when `scheme="lwf"`
        (lwf_employee_contribution/lwf_employer_contribution/lwf_periodicity required); raise
        `ValidationError` otherwise
  - [ ] `__str__` → `f"{self.get_state_display()} · {self.get_scheme_display()}"` (+ bracket suffix for
        PT: `f" ({self.income_from}-{self.income_to})"` if `scheme == "pt"`)

- [ ] `EmployeeStatutoryIdentifier(TenantOwned)` — 1:1 per-employee government-issued identifiers,
      created lazily (drivers: UAN/ESI-number-per-employee called out across every India payroll
      product surveyed):
  - [ ] `employee` — `models.OneToOneField("hrm.EmployeeProfile", on_delete=models.CASCADE,
        related_name="statutory_identifiers")`
  - [ ] `uan_number` — CharField(max_length=20, blank=True) — PF Universal Account Number (lifelong,
        distinct from the establishment-specific PF number)
  - [ ] `pf_number` — CharField(max_length=30, blank=True) — the establishment-specific PF account/
        member ID
  - [ ] `esi_number` — CharField(max_length=20, blank=True) — ESI Insurance Number, blank if the
        employee's gross exceeds the ESI ceiling and they're exempt
  - [ ] `pt_state` — CharField(max_length=50, choices=`INDIAN_STATE_CHOICES`, blank=True) — resolves
        which `StatutoryStateRule` applies to this employee; falls back to
        `StatutoryConfig.pt_default_state` if blank (kept explicit here rather than overloading
        `EmployeeProfile.work_location`, which is free text)
  - [ ] `is_pf_applicable` — BooleanField(default=True)
  - [ ] `is_esi_applicable` — BooleanField(default=True) — an employee above the ESI wage ceiling, or
        exempted/international worker, can be flagged out without deleting the identifier record
  - [ ] WARNING: `uan_number`/`pf_number`/`esi_number` are government ID numbers — add these three
        field names to `apps.core.crud._SENSITIVE_AUDIT_FIELDS` (redacted in `AuditLog.changes`),
        mirroring the existing `national_id`/`passport_number` entries
  - [ ] `class Meta`: `ordering = ["employee__party__name"]`; index `models.Index(fields=["tenant",
        "employee"], name="hrm_esi_tenant_emp_idx")` (verify auto-index name doesn't collide with the
        model short-name abbreviation already used elsewhere)
  - [ ] `__str__` → `f"Statutory IDs · {self.employee}"`
  - [ ] get-or-create pattern: view-layer helper
        `EmployeeStatutoryIdentifier.objects.get_or_create(tenant=tenant, employee=employee)` called
        lazily from the detail/edit view (not every employee needs every identifier filled immediately)

- [ ] `StatutoryReturn(TenantNumbered, NUMBER_PREFIX="SCR")` — shared per-scheme, per-period compliance
      register/challan/return-tracking record (drivers: Keka's monthly PF ECR report, saral PayPack's
      PF/ESI return generation + compliance-calendar, ClearTax's quarterly Form 24Q + annual Form 16,
      Zimyo's LWF Report, RazorpayX's due-date/payment-status tracking):
  - [ ] `scheme` — CharField(max_length=15, choices=`[("pf","Provident Fund"),("esi","ESI"),
        ("pt","Professional Tax"),("tds_24q","TDS — Form 24Q"),("tds_form16","TDS — Form 16"),
        ("lwf","Labour Welfare Fund")]`)
  - [ ] `period_type` — CharField(max_length=15, choices=`[("monthly","Monthly"),
        ("quarterly","Quarterly"),("half_yearly","Half-Yearly"),("annual","Annual")]`)
  - [ ] `period_start` — DateField()
  - [ ] `period_end` — DateField()
  - [ ] `cycle` — `models.ForeignKey("hrm.PayrollCycle", on_delete=models.SET_NULL, null=True,
        blank=True, related_name="statutory_returns")` — set for the common one-cycle-to-one-return
        case (monthly PF/ESI/LWF); left null for multi-cycle rollups (quarterly Form 24Q spans 3
        cycles, aggregates from `Payslip`/`PayslipLine` by date range instead)
  - [ ] `employee` — `models.ForeignKey("hrm.EmployeeProfile", on_delete=models.SET_NULL, null=True,
        blank=True, related_name="statutory_returns")` — set only for `scheme="tds_form16"`; null for
        org-level returns (pf/esi/pt/lwf/tds_24q)
  - [ ] `employee_contribution_total` — DecimalField(max_digits=14, decimal_places=2, default=0,
        editable=False) — **derived/cached, never hand-typed**, rolled up from `PayslipLine.amount`
        where `contribution_side="employee"` matching the scheme, across the period (mirrors
        `PayrollCycle._totals()`'s aggregate-and-cache convention)
  - [ ] `employer_contribution_total` — DecimalField(max_digits=14, decimal_places=2, default=0,
        editable=False) — same pattern, `contribution_side="employer"` (+ `"both"` split rule — decide
        and document: include `contribution_side="both"` lines in BOTH totals, matching 3.14's
        `payrollcycle_lock` roll-up convention for `component_type="statutory_deduction"` with `both`)
  - [ ] `headcount` — PositiveIntegerField(default=0, editable=False) — distinct employee count
        contributing to this return's period for this scheme
  - [ ] `due_date` — DateField(null=True, blank=True) — drives the Compliance Calendar cross-cutting
        feature (PF/ESI by 15th, TDS by 7th via Challan 281, PT by 15th/20th depending on state, LWF
        half-yearly by 15 July/15 January)
  - [ ] `status` — CharField(max_length=15, choices=`[("pending","Pending"),("filed","Filed"),
        ("paid","Paid"),("late","Late")]`, default="pending")
  - [ ] `filed_on` — DateField(null=True, blank=True, editable=False)
  - [ ] `paid_on` — DateField(null=True, blank=True, editable=False)
  - [ ] `payment_reference` — CharField(max_length=100, blank=True)
  - [ ] `registration_number_used` — CharField(max_length=50, blank=True) — snapshot copy of the
        relevant `StatutoryConfig`/`StatutoryStateRule` registration number at generation time (mirrors
        `PayslipLine`'s immutable-snapshot convention from 3.14 — a later registration-number edit must
        never rewrite a historical return)
  - [ ] `notes` — TextField(blank=True)
  - [ ] `class Meta`: `ordering = ["-period_start", "scheme"]`; `unique_together = ("tenant", "scheme",
        "period_start", "employee")` — one return per scheme per period (per employee for
        `tds_form16`, org-wide otherwise — `employee=None` participates in the constraint the same way
        as any other FK value); index `models.Index(fields=["tenant", "status"],
        name="hrm_scr_tenant_status_idx")`, index `models.Index(fields=["tenant", "due_date"],
        name="hrm_scr_tenant_duedate_idx")` (powers the compliance calendar query)
  - [ ] `is_overdue` **property** → `self.status == "pending" and self.due_date and
        self.due_date < timezone.localdate()` (drives a "late" visual flag before the status is
        manually flipped to `"late"`)
  - [ ] `__str__` → `f"{self.number} · {self.get_scheme_display()} · {self.period_start}–{self.period_end}"`

- [ ] one incremental migration `apps/hrm/migrations/0026_statutoryconfig_statutorystaterule_and_more.py`
      (NOT `0001_initial`; last is `0025_payrollcycle_payslip_payslipline_and_more.py`) —
      `makemigrations hrm`, review the generated file, adjust index/constraint names to match the ones
      specified above if Django's auto-names differ; confirm `StatutoryConfig.tenant`
      `OneToOneField` doesn't collide with `TenantOwned`'s abstract FK (override cleanly, don't
      multiple-inherit both)

## `statutoryreturn_generate` — the aggregation engine (the key domain action)

- [ ] `@login_required`, `@require_POST` (or a `@tenant_admin_required` gate — pick tenant-admin to
      match 3.14's workflow-action convention) view, form/inputs: `scheme`, `period_type`,
      `period_start`, `period_end`, optional `cycle` (for the monthly single-cycle case), optional
      `employee` (for `tds_form16`)
- [ ] guard: `get_or_create`-style idempotent behavior — if a `StatutoryReturn` already exists for
      `(tenant, scheme, period_start, employee)`, either re-aggregate in place (if `status="pending"`)
      or block with `messages.error` if already `filed`/`paid` (mirror 3.14's draft-only-regenerate
      rule: only `pending` returns can be re-aggregated)
- [ ] inside `transaction.atomic()`:
  - [ ] resolve the `PayslipLine` queryset for this scheme+period: `PayslipLine.objects.filter(
        payslip__tenant=tenant, payslip__cycle__pay_date__gte=period_start,
        payslip__cycle__pay_date__lte=period_end, component_type="statutory_deduction")` — **note:**
        `PayslipLine` has no direct "scheme" tag (pf vs esi vs pt vs lwf are all
        `component_type="statutory_deduction"` today); document the v1 simplification explicitly: this
        pass aggregates ALL `statutory_deduction` lines for the period as a single pool per scheme
        selection (cannot yet distinguish a PF line from an ESI line within `PayslipLine` without a
        `PayComponent`-name-based heuristic) — **decide and document one of:** (a) filter additionally
        by `component_name__icontains=<scheme keyword>` (e.g. "PF"/"Provident", "ESI", "Professional
        Tax", "Labour Welfare") as a pragmatic v1 match against the seeded `PayComponent.name` strings,
        or (b) aggregate the full `statutory_deduction` pool once and let the user pick `scheme` purely
        as a label — **pick (a)**, the name-substring match, and note it as a v1 heuristic (a proper
        per-line scheme tag is a fast-follow noted under Later passes)
  - [ ] `employee_total = qs.filter(contribution_side__in=["employee", "both"]).aggregate(
        Sum("amount"))["amount__sum"] or Decimal("0")`
  - [ ] `employer_total = qs.filter(contribution_side__in=["employer", "both"]).aggregate(
        Sum("amount"))["amount__sum"] or Decimal("0")`
  - [ ] `headcount = qs.values("payslip__employee_id").distinct().count()`
  - [ ] snapshot `registration_number_used` from the relevant `StatutoryConfig`/`StatutoryStateRule`
        field for the chosen scheme (e.g. `pf_establishment_code` for `scheme="pf"`,
        `esi_employer_code` for `"esi"`, `tan_number` for `"tds_24q"`/`"tds_form16"`, the matching
        `StatutoryStateRule.registration_number` for `"pt"`/`"lwf"`)
  - [ ] `StatutoryReturn.objects.update_or_create(tenant=tenant, scheme=scheme,
        period_start=period_start, employee=employee, defaults={...period_end, cycle,
        employee_contribution_total: employee_total, employer_contribution_total: employer_total,
        headcount, registration_number_used, ...})`
  - [ ] `write_audit_log(request.user, obj, "update", {"action": "generate", "headcount": headcount})`
- [ ] redirect to `statutoryreturn_detail`; `messages.success` with the aggregated totals

## Filing/payment status-workflow actions

- [ ] `statutoryreturn_mark_filed` (`@tenant_admin_required`, `@require_POST`) — only from
      `status="pending"`; set `status="filed"`, `filed_on=timezone.localdate()`; `write_audit_log(...,
      {"action": "mark_filed"})`
- [ ] `statutoryreturn_mark_paid` (`@tenant_admin_required`, `@require_POST`) — only from
      `status in {"pending", "filed"}`; set `status="paid"`, `paid_on=timezone.localdate()`,
      `payment_reference=request.POST.get("payment_reference", "").strip()[:100]`; if `paid_on >
      due_date` (when `due_date` set) also flip `status="late"` instead of `"paid"` — document this
      override rule explicitly (mirrors RazorpayX/saral PayPack's paid-vs-late comparison); write_audit_log
- [ ] both redirect to `statutoryreturn_detail`

## B. Forms (`apps/hrm/forms.py`)

- [ ] `StatutoryConfigForm(TenantModelForm)`:
  - [ ] `Meta.fields = ["pf_establishment_code", "pf_wage_ceiling", "pf_employee_rate",
        "pf_employer_rate", "esi_employer_code", "esi_wage_ceiling", "esi_employee_rate",
        "esi_employer_rate", "pt_default_state", "tan_number", "tds_circle_address",
        "pan_of_deductor", "is_lwf_applicable"]` (exclude `tenant` — set via `get_or_create`, never a
        form field since there's exactly one row per tenant)
  - [ ] no custom `__init__` needed (no FK dropdowns)
- [ ] `StatutoryStateRuleForm(TenantModelForm)`:
  - [ ] `Meta.fields = ["state", "scheme", "income_from", "income_to", "pt_monthly_amount",
        "pt_deduction_month", "lwf_employee_contribution", "lwf_employer_contribution",
        "lwf_periodicity", "lwf_due_month_1", "lwf_due_month_2", "registration_number", "is_active",
        "effective_from"]` (exclude `tenant`/auto-number — no number field on this model, all fields
        form-editable except `tenant`)
  - [ ] template-side JS/UX note (not blocking backend): consider toggling PT-only vs LWF-only field
        visibility based on the `scheme` select, but not required for v1 — plain form with all fields
        shown is acceptable
- [ ] `EmployeeStatutoryIdentifierForm(TenantModelForm)`:
  - [ ] `Meta.fields = ["employee", "uan_number", "pf_number", "esi_number", "pt_state",
        "is_pf_applicable", "is_esi_applicable"]` (exclude `tenant`)
  - [ ] custom `__init__` narrows `employee` queryset to `EmployeeProfile.objects.filter(tenant=tenant)`
        (standard tenant-scoped FK-narrowing pattern used across every prior HRM form)
- [ ] `StatutoryReturnForm(TenantModelForm)`:
  - [ ] `Meta.fields = ["scheme", "period_type", "period_start", "period_end", "cycle", "employee",
        "due_date", "notes"]` (exclude `tenant`/auto-number `number`/derived
        `employee_contribution_total`/`employer_contribution_total`/`headcount`/`status`/`filed_on`/
        `paid_on`/`payment_reference`/`registration_number_used` — all workflow/derived, never
        generic-form-editable; totals are only ever set via `statutoryreturn_generate`)
  - [ ] custom `__init__` narrows `cycle` to `PayrollCycle.objects.filter(tenant=tenant)` and
        `employee` to `EmployeeProfile.objects.filter(tenant=tenant)`
  - [ ] this form covers manual create (a return with due_date/notes but zero aggregates, to be
        generated later) and metadata edit; the aggregate totals are never form-editable

## C. Views (`apps/hrm/views.py`)

- [ ] `statutoryconfig_detail` (`@login_required`) — the settings-singleton page: `config, _ =
      StatutoryConfig.objects.get_or_create(tenant=request.tenant)`; render
      `hrm/statutory/statutoryconfig/detail.html` with `{"obj": config}` — no `_list`/`_create`/
      `_delete` views (singleton, nothing to list or delete)
- [ ] `statutoryconfig_edit` (`@login_required`) — `get_or_create` then standard `crud_edit`-style
      handling (or a thin custom view since `crud_edit` expects a `pk` — either add a `pk`-taking
      wrapper that resolves `pk=config.pk` via redirect, or write a small dedicated
      get-or-create-then-edit view; **pick the dedicated view**, document why `crud_edit` isn't reused
      directly for this one singleton model)
- [ ] `statutorystaterule_list` (`@login_required`) — `crud_list(request,
      StatutoryStateRule.objects.filter(tenant=request.tenant), "hrm/statutory/statutorystaterule/list.html",
      search_fields=["state", "registration_number"], filters=[("scheme", "scheme", False),
      ("state", "state", False), ("is_active", "is_active", False)], extra_context={"scheme_choices":
      StatutoryStateRule._meta.get_field("scheme").choices, "state_choices": INDIAN_STATE_CHOICES})`
- [ ] `statutorystaterule_create` / `_edit` / `_detail` / `_delete` — standard `crud_create`/
      `crud_edit`/`crud_detail`/`crud_delete` wrappers, template base
      `hrm/statutory/statutorystaterule/{form,detail}.html`
- [ ] `employeestatutoryidentifier_list` (`@login_required`) — `crud_list(request,
      EmployeeStatutoryIdentifier.objects.filter(tenant=request.tenant).select_related(
      "employee__party"), "hrm/statutory/employeestatutoryidentifier/list.html",
      search_fields=["employee__party__name", "uan_number", "pf_number", "esi_number"],
      filters=[("pt_state", "pt_state", False), ("is_pf_applicable", "is_pf_applicable", False),
      ("is_esi_applicable", "is_esi_applicable", False)], extra_context={"state_choices":
      INDIAN_STATE_CHOICES})`
- [ ] `employeestatutoryidentifier_create` / `_edit` / `_detail` / `_delete` — standard wrappers;
      `_create`'s form narrows the `employee` dropdown to employees who don't already have an
      identifier row (`EmployeeProfile.objects.filter(tenant=tenant).exclude(
      statutory_identifiers__isnull=False)`) so the OneToOne can't collide — document this narrowing in
      the form's `__init__`
- [ ] `statutoryreturn_list` (`@login_required`) — `crud_list(request,
      StatutoryReturn.objects.filter(tenant=request.tenant).select_related("cycle",
      "employee__party"), "hrm/statutory/statutoryreturn/list.html", search_fields=["number",
      "registration_number_used", "notes"], filters=[("scheme", "scheme", False), ("status", "status",
      False), ("period_type", "period_type", False)], extra_context={"scheme_choices":
      StatutoryReturn._meta.get_field("scheme").choices, "status_choices":
      StatutoryReturn._meta.get_field("status").choices, "period_type_choices":
      StatutoryReturn._meta.get_field("period_type").choices})`
- [ ] `statutoryreturn_create` — standard `crud_create` wrapper (manual metadata-only create; totals
      stay 0 until `generate` is run)
- [ ] `statutoryreturn_edit` — standard `crud_edit` wrapper, only while `status == "pending"` (else
      `messages.error` + redirect to detail, mirror the `floatingholidayelection_edit`/
      `payrollcycle_edit` pending-only guard pattern)
- [ ] `statutoryreturn_delete` (`@login_required`, `@require_POST`) — only while `status == "pending"`
      (mirror `payrollcycle_delete`'s draft-only guard) — else `messages.error` + redirect
- [ ] `statutoryreturn_detail` (`@login_required`) — `crud_detail(request, model=StatutoryReturn,
      pk=pk, template="hrm/statutory/statutoryreturn/detail.html", select_related=("cycle",
      "employee__party"))`
- [ ] `statutoryreturn_generate` — per the Aggregation Engine spec above
- [ ] `statutoryreturn_mark_filed` / `_mark_paid` — per the Filing/Payment Status Workflow spec above
- [ ] `statutory_compliance_calendar` (`@login_required`) — the cross-cutting **compliance calendar**
      read-only view, no new model: `returns = StatutoryReturn.objects.filter(
      tenant=request.tenant).select_related("cycle", "employee__party").order_by("due_date",
      "scheme")`; group into buckets by `status` (overdue via `is_overdue` property / pending / filed /
      paid) for the template to render as calendar/list columns; support the same `scheme`/`status`
      GET-param filters as `statutoryreturn_list` (reuse `apply_search`/manual filtering, not
      necessarily full `crud_list` since this is a grouped, not paginated-flat, view — document that
      choice); render `hrm/statutory/compliance_calendar.html`
- [ ] all new views import `StatutoryConfig`, `StatutoryStateRule`, `EmployeeStatutoryIdentifier`,
      `StatutoryReturn`, `StatutoryConfigForm`, `StatutoryStateRuleForm`,
      `EmployeeStatutoryIdentifierForm`, `StatutoryReturnForm` at the top of `views.py`; `Sum` from
      `django.db.models` and `transaction` from `django.db` (already imported for 3.14 — confirm, don't
      re-import)

## D. URLs (`apps/hrm/urls.py`, `app_name = "hrm"` already set)

- [ ] `path("statutory-config/", views.statutoryconfig_detail, name="statutoryconfig_detail")`
- [ ] `path("statutory-config/edit/", views.statutoryconfig_edit, name="statutoryconfig_edit")`
- [ ] `path("statutory-state-rules/", views.statutorystaterule_list, name="statutorystaterule_list")`
- [ ] `path("statutory-state-rules/add/", views.statutorystaterule_create, name="statutorystaterule_create")`
- [ ] `path("statutory-state-rules/<int:pk>/", views.statutorystaterule_detail, name="statutorystaterule_detail")`
- [ ] `path("statutory-state-rules/<int:pk>/edit/", views.statutorystaterule_edit, name="statutorystaterule_edit")`
- [ ] `path("statutory-state-rules/<int:pk>/delete/", views.statutorystaterule_delete, name="statutorystaterule_delete")`
- [ ] `path("statutory-identifiers/", views.employeestatutoryidentifier_list, name="employeestatutoryidentifier_list")`
- [ ] `path("statutory-identifiers/add/", views.employeestatutoryidentifier_create, name="employeestatutoryidentifier_create")`
- [ ] `path("statutory-identifiers/<int:pk>/", views.employeestatutoryidentifier_detail, name="employeestatutoryidentifier_detail")`
- [ ] `path("statutory-identifiers/<int:pk>/edit/", views.employeestatutoryidentifier_edit, name="employeestatutoryidentifier_edit")`
- [ ] `path("statutory-identifiers/<int:pk>/delete/", views.employeestatutoryidentifier_delete, name="employeestatutoryidentifier_delete")`
- [ ] `path("statutory-returns/", views.statutoryreturn_list, name="statutoryreturn_list")`
- [ ] `path("statutory-returns/add/", views.statutoryreturn_create, name="statutoryreturn_create")`
- [ ] `path("statutory-returns/<int:pk>/", views.statutoryreturn_detail, name="statutoryreturn_detail")`
- [ ] `path("statutory-returns/<int:pk>/edit/", views.statutoryreturn_edit, name="statutoryreturn_edit")`
- [ ] `path("statutory-returns/<int:pk>/delete/", views.statutoryreturn_delete, name="statutoryreturn_delete")`
- [ ] `path("statutory-returns/<int:pk>/generate/", views.statutoryreturn_generate, name="statutoryreturn_generate")`
- [ ] `path("statutory-returns/<int:pk>/mark-filed/", views.statutoryreturn_mark_filed, name="statutoryreturn_mark_filed")`
- [ ] `path("statutory-returns/<int:pk>/mark-paid/", views.statutoryreturn_mark_paid, name="statutoryreturn_mark_paid")`
- [ ] `path("statutory-compliance-calendar/", views.statutory_compliance_calendar, name="statutory_compliance_calendar")`

## E. Admin (`apps/hrm/admin.py`)

- [ ] register `StatutoryConfig` — `list_display = ("tenant", "pf_establishment_code",
      "esi_employer_code", "tan_number", "is_lwf_applicable")`, `list_filter = ("is_lwf_applicable",)`,
      `search_fields = ("tenant__name", "pf_establishment_code", "esi_employer_code", "tan_number")`
- [ ] register `StatutoryStateRule` — `list_display = ("state", "scheme", "income_from", "income_to",
      "is_active", "effective_from")`, `list_filter = ("tenant", "scheme", "state", "is_active")`,
      `search_fields = ("state", "registration_number")`
- [ ] register `EmployeeStatutoryIdentifier` — `list_display = ("employee", "uan_number", "pf_number",
      "esi_number", "is_pf_applicable", "is_esi_applicable")`, `list_filter = ("tenant",
      "is_pf_applicable", "is_esi_applicable")`, `search_fields = ("employee__party__name",
      "uan_number", "pf_number", "esi_number")`
- [ ] register `StatutoryReturn` — `list_display = ("number", "scheme", "period_start", "period_end",
      "status", "employee_contribution_total", "employer_contribution_total", "due_date")`,
      `list_filter = ("tenant", "scheme", "status", "period_type")`, `search_fields = ("number",
      "registration_number_used", "notes")`

## F. Templates (`templates/hrm/statutory/<entity>/<page>.html`)

- [ ] `statutory/statutoryconfig/detail.html` — single-entity sub-module-doubles-as-entity-folder
      pattern (per Template Folder Structure rule 3): header sections PF (establishment_code,
      wage_ceiling, employee/employer rates), ESI (employer_code, wage_ceiling, employee/employer
      rates), PT (pt_default_state), TDS (tan_number, tds_circle_address, pan_of_deductor), LWF
      (is_lwf_applicable badge); single Edit action (links to `statutoryconfig_edit`, no delete —
      singleton); no list page for this model
- [ ] `statutory/statutoryconfig/form.html` — standard form, all `StatutoryConfigForm` fields grouped
      into the same PF/ESI/PT/TDS/LWF sections as the detail page
- [ ] `statutory/statutorystaterule/list.html` — filter bar: search `q`, `scheme` select (from
      `scheme_choices`), `state` select (from `state_choices`), `is_active` select (True/False);
      columns: state, scheme badge (`pt`→`badge-info`, `lwf`→`badge-amber`), income bracket (PT) or
      periodicity (LWF), amount, registration_number, is_active badge, effective_from, Actions
      (view/edit/delete); pagination include; empty-state
- [ ] `statutory/statutorystaterule/detail.html` — header (state, scheme badge, is_active badge,
      effective_from), PT section (income_from–income_to, pt_monthly_amount, pt_deduction_month) shown
      only if `scheme == "pt"`, LWF section (lwf_employee_contribution, lwf_employer_contribution,
      lwf_periodicity, lwf_due_month_1, lwf_due_month_2) shown only if `scheme == "lwf"`,
      registration_number; Actions sidebar (Edit/Delete/Back to List)
- [ ] `statutory/statutorystaterule/form.html` — standard form (all fields; PT/LWF fields shown
      together, no JS toggle required for v1 per Forms section note)
- [ ] `statutory/employeestatutoryidentifier/list.html` — filter bar: search `q`, `pt_state` select
      (from `state_choices`), `is_pf_applicable`/`is_esi_applicable` selects (True/False); columns:
      employee, uan_number, pf_number, esi_number, pt_state, is_pf_applicable badge, is_esi_applicable
      badge, Actions (view/edit/delete); pagination include; empty-state
- [ ] `statutory/employeestatutoryidentifier/detail.html` — header (employee link), PF section
      (uan_number, pf_number, is_pf_applicable badge), ESI section (esi_number, is_esi_applicable
      badge), PT section (pt_state); Actions sidebar (Edit/Delete/Back to List)
- [ ] `statutory/employeestatutoryidentifier/form.html` — standard form (employee dropdown +
      uan_number/pf_number/esi_number/pt_state/is_pf_applicable/is_esi_applicable)
- [ ] `statutory/statutoryreturn/list.html` — filter bar: search `q`, `scheme` select (from
      `scheme_choices`), `status` select (from `status_choices`), `period_type` select (from
      `period_type_choices`); columns: number, scheme badge, period_start–period_end, status badge
      (`pending`→`badge-muted`, `filed`→`badge-info`, `paid`→`badge-green`, `late`→`badge-red`),
      employee_contribution_total, employer_contribution_total, headcount, due_date (highlight red if
      `obj.is_overdue`), Actions (view/edit-if-pending/delete-if-pending/generate); pagination include;
      empty-state; always `{% else %}{{ obj.get_scheme_display }}`/`{{ obj.get_status_display }}`
      fallback per Badge Values rule
- [ ] `statutory/statutoryreturn/detail.html` — header fields (scheme badge, period_type,
      period_start–period_end, cycle link if set, employee link if `tds_form16`), derived-totals panel
      (employee_contribution_total/employer_contribution_total/headcount), status badge + due_date
      (with overdue flag), filed_on/paid_on/payment_reference, registration_number_used, notes; action
      buttons gated by status (`Generate/Re-aggregate` — pending only, POST+confirm+csrf; `Mark Filed`
      — pending only, tenant-admin, POST+confirm+csrf; `Mark Paid` — pending/filed only, tenant-admin,
      POST+confirm+csrf with a `payment_reference` input); Actions sidebar (Edit-if-pending/
      Delete-if-pending, Back to List)
- [ ] `statutory/statutoryreturn/form.html` — standard form (scheme, period_type, period_start,
      period_end, cycle, employee, due_date, notes)
- [ ] `statutory/compliance_calendar.html` — the cross-cutting calendar page: grouped sections
      (Overdue / Pending / Filed / Paid, or grouped by upcoming `due_date`), each row links to
      `statutoryreturn_detail`; filter bar mirrors `statutoryreturn_list`'s scheme/status selects;
      empty-state; this is a **standalone page** at the sub-module root (`statutory/`), not inside an
      entity folder, per Template Folder Structure rule 6
- [ ] a landing link: add a `statutory/overview.html`-style link OR simply ensure
      `statutoryreturn_list`/`statutory_compliance_calendar` are reachable from the sidebar — confirm
      against the existing HRM sub-module landing convention (3.13/3.14 didn't add a dedicated overview
      page; match whichever pattern those actually used) before adding a new one unnecessarily

## G. Seeder (`apps/hrm/management/commands/seed_hrm.py`)

- [ ] add `_seed_statutory(self, tenant, *, flush)` method, called from `handle()` **AFTER**
      `self._seed_payroll(tenant, flush=options["flush"])` (return generation needs 3.14's
      `PayrollCycle`/`Payslip`/`PayslipLine` rows to exist first)
- [ ] `if flush:` child-first wipe: `StatutoryReturn.objects.filter(tenant=tenant).delete()` →
      `EmployeeStatutoryIdentifier.objects.filter(tenant=tenant).delete()` →
      `StatutoryStateRule.objects.filter(tenant=tenant).delete()` →
      `StatutoryConfig.objects.filter(tenant=tenant).delete()`
- [ ] `if StatutoryConfig.objects.filter(tenant=tenant).exists(): self.stdout.write(self.style.NOTICE(
      f"Statutory compliance data already exists for '{tenant.name}'. Use --flush to re-seed.")); return`
- [ ] create 1 `StatutoryConfig` row: `pf_establishment_code="MH/BAN/1234567/000"`,
      `esi_employer_code="11-22-334455-000-1111"`, `pt_default_state="Maharashtra"`,
      `tan_number="MUMB12345C"`, `tds_circle_address="ITO (TDS), Room 101, Mumbai"`,
      `pan_of_deductor="AABCN1234A"`, `is_lwf_applicable=True` (defaults cover pf/esi rates/ceilings —
      don't override unless demonstrating a non-default rate)
- [ ] create 2 `StatutoryStateRule` rows:
  - [ ] a Maharashtra PT slab: `state="Maharashtra"`, `scheme="pt"`, `income_from=Decimal("0.00")`,
        `income_to=Decimal("7500.00")`, `pt_monthly_amount=Decimal("0.00")`, `is_active=True`,
        `effective_from=` a fixed past date (e.g. `2024-04-01`) — plus a second bracket row (e.g.
        `income_from=7501, income_to=10000, pt_monthly_amount=175`) to demonstrate the slab-table shape
        (2 PT rows minimum, satisfying "a couple of StatutoryStateRule rows")
  - [ ] a Maharashtra half-yearly LWF row: `state="Maharashtra"`, `scheme="lwf"`,
        `lwf_employee_contribution=Decimal("6.00")`, `lwf_employer_contribution=Decimal("18.00")`,
        `lwf_periodicity="half_yearly"`, `lwf_due_month_1="July"`, `lwf_due_month_2="January"`,
        `registration_number="LWF/MH/998877"`, `is_active=True`, `effective_from=` same fixed past date
- [ ] for each seeded `EmployeeProfile` in `tenant` (reuse the 3.13/3.14-seeded employees): `get_or_create`
      an `EmployeeStatutoryIdentifier` with deterministic demo values (`uan_number=f"UAN{employee.pk:010d}"`,
      `pf_number=f"MH/BAN/1234567/000/{employee.pk:04d}"`, `esi_number=f"3411{employee.pk:06d}"`,
      `pt_state="Maharashtra"`, `is_pf_applicable=True`, `is_esi_applicable=True`)
- [ ] generate 1 `StatutoryReturn` (scheme=`"pf"`) for the existing seeded `PayrollCycle` from
      `_seed_payroll`: reuse or directly call the same aggregation logic as `statutoryreturn_generate`
      (a shared helper is preferable — if the view logic is short enough, factor a
      `build_statutory_return(tenant, scheme, period_start, period_end, cycle=None, employee=None)`
      module-level function in `models.py` or a `services.py` that both the view and the seeder call,
      avoiding duplicating the aggregation query) — `period_type="monthly"`,
      `period_start=cycle.period_start`, `period_end=cycle.period_end`, `cycle=cycle`,
      `due_date=cycle.period_end.replace(day=15)` (approximate 15th-of-month PF due date, clamped if
      the month has fewer days — use a safe date-arithmetic helper), `registration_number_used=
      config.pf_establishment_code`
- [ ] print a summary line: `f"Statutory compliance seeded for '{tenant.name}': 1 config, 2 state
      rules, {EmployeeStatutoryIdentifier.objects.filter(tenant=tenant).count()} employee
      identifier(s), 1 statutory return ({return_obj.number})."`
- [ ] add the 4 models to the `--flush` wipe order in dependency sequence (children first):
      `StatutoryReturn` → `EmployeeStatutoryIdentifier` → `StatutoryStateRule` → `StatutoryConfig`
      (already specified above — restate here for the flush-order checklist); confirm this sits BEFORE
      `EmployeeProfile`'s own wipe in the central flush order (since `EmployeeStatutoryIdentifier` FKs
      to it) — mirror the 3.14 lesson about wiping children before the PROTECT-adjacent parent
- [ ] verify the seeder still prints the tenant-admin login reminder + "Data already exists" warning
      path unchanged — the new block is itself idempotent, no new top-level guard needed

## H. Navigation (`apps/core/navigation.py`)

- [ ] add `LIVE_LINKS["3.15"]` (verify the exact query-string highlighting convention against 3.13/
      3.14's existing entries before finalizing):
      ```python
      # 3.15 Statutory Compliance — StatutoryReturn (scheme-filtered) serves PF/ESI/PT/TDS/LWF;
      # StatutoryStateRule serves PT's state-wise rules; mirrors 3.14's deep-linked query-param pattern.
      "3.15": {
          "PF Management": "hrm:statutoryreturn_list?scheme=pf",                    # bullet
          "ESI Management": "hrm:statutoryreturn_list?scheme=esi",                  # bullet
          "PT Management": "hrm:statutorystaterule_list?scheme=pt",                 # bullet
          "TDS Management": "hrm:statutoryreturn_list?scheme=tds_24q",              # bullet
          "LWF Management": "hrm:statutorystaterule_list?scheme=lwf",               # bullet
      },
      ```
      — all 5 NavERP.md 3.15 bullets go Live; adjust the literal query strings if the real filter
      param names implemented in Section C differ; PT/LWF deliberately point at
      `statutorystaterule_list` (the state-wise rule table) rather than `statutoryreturn_list` since
      the rule table IS the PT/LWF-specific configuration surface the bullet describes, while PF/ESI/
      TDS point at the shared `statutoryreturn_list` (challan/return tracking) — document this split
      rationale in the navigation.py comment

## I. Migrate / seed / verify (run from the venv)

- [ ] `python manage.py makemigrations hrm` → review `0026_...py` (field/index/unique_together names
      match the plan; confirm `StatutoryConfig`'s `OneToOneField` override of the abstract `tenant` FK
      generates cleanly with no spurious `TenantOwned.tenant` leftover column)
- [ ] `python manage.py migrate`
- [ ] `python manage.py seed_hrm` (1st run — creates data; confirm 3.14's `_seed_payroll` still runs
      first and the new `_seed_statutory` block generates its config/rules/identifiers/return against
      it)
- [ ] `python manage.py seed_hrm` (2nd run — must be idempotent, no duplicates, no errors)
- [ ] `python manage.py check`
- [ ] `temp/` smoke sweep: every new `hrm:statutoryconfig_*`, `hrm:statutorystaterule_*`,
      `hrm:employeestatutoryidentifier_*`, `hrm:statutoryreturn_*`, and
      `hrm:statutory_compliance_calendar` URL returns 200/302 when logged in as a tenant admin; no
      `{#`/`{% comment` leaks in the new templates; cross-tenant IDOR check — a `StatutoryStateRule`/
      `EmployeeStatutoryIdentifier`/`StatutoryReturn` pk belonging to tenant A returns 404 when fetched
      as tenant B; `statutoryreturn_generate` run twice on a `pending` return produces the same
      totals (re-aggregation replaces, doesn't duplicate/double-count); spot-check
      `employee_contribution_total`/`employer_contribution_total`/`headcount` arithmetic against the
      seeded `PayslipLine` rows by hand; `statutoryreturn_mark_paid` after `due_date` correctly flips
      to `"late"` not `"paid"`; `statutoryreturn_edit`/`_delete` blocked once not `pending`; non-admin
      user gets 403 on mark_filed/mark_paid; the `?scheme=pf`/`?scheme=pt` deep-links each render the
      filtered subset correctly; the compliance calendar groups returns by status/due_date correctly
- [ ] sidebar: confirm 3.15 shows all five bullets as **Live** (not "Coming soon") for a tenant with
      data

## J. Close-out

- [ ] update `README.md` module-status / HRM section (3.15 bullets: PF Management / ESI Management /
      PT Management / TDS Management / LWF Management all live; bump the HRM + project-wide test-count
      lines once test-writer runs)
- [ ] run the review-agent sequence in order, each ending in its own commit(s): `code-reviewer` →
      `explorer` → `frontend-reviewer` → `performance-reviewer` → `qa-smoke-tester` →
      `security-reviewer` → `test-writer`
- [ ] update `.claude/skills/hrm/SKILL.md` — 3.15 section: document `StatutoryConfig`/
      `StatutoryStateRule`/`EmployeeStatutoryIdentifier`/`StatutoryReturn` models, the
      `statutoryreturn_generate` aggregation-engine contract (incl. the v1 `component_name`-substring
      scheme-matching heuristic against `PayslipLine`), the mark_filed/mark_paid workflow + the
      due-date/late-status rule, the compliance calendar view, the new `LIVE_LINKS["3.15"]` entries
      (incl. the PT/LWF-vs-PF/ESI/TDS routing split), the extended seeder block, and mark all 5 bullets
      of 3.15 as built

## Later passes / deferred (carried over from research-statutory-compliance.md — do not build this pass)

- **ECR file / ESIC challan / EPFO-portal file-format generation** — the exact pipe/CSV government file
  layouts and direct portal upload; this pass stores the aggregated numbers
  (`StatutoryReturn.employee_contribution_total` etc.) needed to generate them later.
- **TRACES integration / unconsumed-challan matching** — external government-portal API integration.
- **AI/rules-based error detection before filing** (late-deduction/PAN-validation flagging) — a
  validation-rules engine layered on top of `StatutoryReturn`; fast-follow, not blocking v1.
- **Form 16 / Form 24Q PDF/XML rendering and email delivery** — presentation/document-generation
  layer, consistent with the payslip-PDF deferral noted in 3.14; this pass tracks the
  `StatutoryReturn` row's status/aggregates, not the rendered document.
- **Automatic rate-change alerting** (e.g. the Odisha PT discontinuation pattern) — structurally
  supported via `StatutoryStateRule.is_active`/`effective_from` (supersede, don't edit), but no
  notification/alert engine built this pass.
- **Compliance-calendar dashboard UI as a distinct product surface beyond the read-only grouped list**
  — `statutory_compliance_calendar` ships as a straightforward grouped list this pass; a richer
  calendar-grid UI is a later frontend polish pass, not a data-model change.
- **Multi-country / non-India statutory schemes** — `StatutoryReturn.scheme` choices stay India-only
  this pass; extending for other jurisdictions is a future-pass consideration.
- **Gratuity and Bonus Act statutory compliance** — out of the five NavERP.md 3.15 bullets (PF/ESI/PT/
  TDS/LWF only); would be a separate future bullet if NavERP.md is extended.
- **PT/LWF per-employee-type differentiation beyond `EmployeeProfile.employee_type` reuse** — supported
  at the query/filter level using the existing field; no new per-type override table added.
- **Per-`PayslipLine` scheme tagging** (a proper `scheme` FK/choice on `PayslipLine` distinguishing PF
  vs ESI vs PT vs LWF lines cleanly, replacing the v1 `component_name`-substring heuristic used by
  `statutoryreturn_generate`) — noted above as the pragmatic v1 aggregation approach; a real per-line
  scheme tag would require a 3.14 model change and is deferred to avoid touching an already-shipped,
  reviewed, tested model this pass.

## Review — 3.15 Statutory Compliance (built 2026-07-04/05)

**Shipped (4 models, all wired Live).** `StatutoryConfig` (tenant settings singleton, OneToOne tenant override,
`for_tenant()`, detail+edit only), `StatutoryStateRule` (state-wise PT slabs + LWF rules, scheme-aware `clean()`,
supersede-not-edit), `EmployeeStatutoryIdentifier` (1:1 UAN/PF/ESI, **masked** in list+detail), `StatutoryReturn`
(`SCR-`, `recompute()` aggregates `PayslipLine` by contribution_side mirroring 3.14 `payrollcycle_lock` —
employer=`contribution_side="employer"`, employee=everything else, no double-count of "both"; v1 `SCHEME_KEYWORDS`
`component_name`-substring match; pending→filed→paid/late workflow with paid-after-due→`late`; compliance calendar).
Migration `0026`. `LIVE_LINKS["3.15"]` — all 5 NavERP.md bullets Live (PF/ESI/TDS→returns, PT/LWF→state-rules).
`_seed_statutory` after `_seed_payroll` (1 config, 3 MH rules, an identifier per employee, 1 generated PF return
SCR-00001 showing employer ≈1,800/3 heads). Reuses `EmployeeProfile`/`PayrollCycle`/`PayslipLine`/`PayComponent`;
**no new employee master, no GL path** (`accounting.PayrollRun`/`JournalEntry` untouched).

**Verification.** `manage.py check` clean; seeder idempotent (2nd run guards); smoke sweep 200/302 on all routes, no
template leaks, cross-tenant IDOR→404, mark_paid-after-due→late.

**Review agents (all run in order; findings applied + committed):**
- code-reviewer — 2 Important fixed: `StatutoryReturnForm.clean()` closes the org-level (employee=None) duplicate
  hole (MariaDB NULL-distinct); `statutoryconfig_edit` gated `@tenant_admin_required` (+ template Edit button).
- explorer — no wiring bugs (urls/templates/context/reuse all consistent).
- frontend-reviewer — 2 fixes: `.btn-icon danger` on 3 list delete buttons; flex/gap instead of inline margin.
- performance-reviewer — dropped dead `select_related` on `statutoryreturn_list` + `statutory_compliance_calendar`.
- qa-smoke-tester — all green, no bugs.
- security-reviewer — 1 Medium fixed: mask UAN/PF/ESI (list+detail) via `masked_*` accessors (kept edit-view
  gating as `@login_required`, consistent with `PayComponent`/`EmployeeProfile` precedent).
- test-writer — **174 tests** (58 model / 75 view / 41 security), all pass; HRM suite 2,221→**2,395**, project-wide
  4,868→**5,042**. Surfaced a real create-time bug (active-LWF-per-state guard skipped on create) — **fixed** at the
  form level (`StatutoryStateRuleForm.clean()`) and inverted the bug-locking test.

**Deferred (later passes):** ECR/ESIC file-format + portal upload, TRACES/challan matching, Form 16/24Q PDF, AI
pre-filing error detection, rate-change alerting, richer calendar-grid UI, multi-country schemes, Gratuity/Bonus Act,
and a per-`PayslipLine` scheme tag (to replace the v1 substring match). **Next:** 3.16 Tax & Investment.

---
# Module 3 — HRM — Sub-module 3.16 Tax & Investment (tax-investment) — plan from research-tax-investment.md (2026-07-05)

**Context.** Extends the existing `apps/hrm` app — NOT a new app. Builds the India income-tax
declaration + computation layer strictly ON TOP of 3.13 (`EmployeeSalaryStructure.annual_ctc_amount`),
3.14 (`PayrollCycle`/`Payslip`/`PayslipLine` — TDS already deducted, tagged
`component_type="statutory_deduction"`), and 3.15 (`StatutoryConfig` — TAN/PAN-of-deductor/circle
address already there; `StatutoryReturn(scheme="tds_form16")` — the existing Form-16 register row).
6 new tables (4 "models" + 2 detail children), all appended to `apps/hrm/models.py`. Money still posts
only through `accounting.PayrollRun`/`JournalEntry` (lesson **L29**) — **3.16 posts nothing to the
GL**; it only computes/declares/verifies/reports numbers.

**Regulatory caveat (documented in the model docstrings, not hard-coded as gospel):** the Income Tax
Act, 2025 (effective 1 Apr 2026) renumbers familiar sections and the exact new numbering is unsettled
across sources ("Form 122" vs "Form 124", disputed renumbering of 115BAC/Section 192/80C). Model
`section_code` as a descriptive CharField/choice keyed to the FAMILIAR names (80C, 80D, HRA, 24b,
80CCD(1B), …) plus a free-text `tax_law_reference` note on `TaxRegimeConfig`, so the UI label can be
corrected later without a schema change.

NavERP.md 3.16 bullets (exact text, all 5 go Live this pass):
- Tax Regime — Old vs New regime comparison.
- Investment Declaration — 80C, 80D, HRA, other deductions.
- Investment Proof — Document upload, verification.
- Tax Computation — Annual tax projection.
- Form 16 Generation — Auto-generate Form 16/16A.

Reuses (no duplication): `hrm.EmployeeProfile` (`national_id` = employee PAN — no new employee
master), `hrm.EmployeeSalaryStructure.annual_ctc_amount` (the gross-income basis), `hrm.PayrollCycle`/
`Payslip`/`PayslipLine` (TDS-paid-to-date aggregation, reusing the exact `_scheme_lines()`/
`recompute()` pattern from 3.15), `hrm.StatutoryConfig` (TAN/PAN-of-deductor/circle-address for Form
16 Part A — `StatutoryConfig.for_tenant(tenant)`), `hrm.StatutoryReturn` (`scheme="tds_form16"` — the
Form-16 register row 3.16 links to via a new FK; **do NOT add a new Form-16 header table**),
`settings.AUTH_USER_MODEL` (verify actor + `write_audit_log`). Never touches
`accounting.PayrollRun`/`JournalEntry` — no GL-posting path (L29).

## A. Models + migration (`apps/hrm/models.py`)

- [ ] `TaxRegimeConfig(TenantOwned)` — per-tenant-per-FY-per-regime rate master, no numeric prefix
      (drivers: every product's regime-comparison feature needing a rate table; greytHR's admin "View
      Income Tax slabs" screen):
  - [ ] `financial_year` — CharField(max_length=10) — e.g. `"2025-26"`, matches
        `StatutoryReturn`'s annual period convention
  - [ ] `regime` — CharField(max_length=10, choices=`[("old","Old Regime"),("new","New Regime")]`)
  - [ ] `standard_deduction` — DecimalField(max_digits=12, decimal_places=2,
        default=Decimal("75000.00")) — FY 2025-26 new-regime default; old-regime rows set
        `Decimal("50000.00")` explicitly at creation (Tax Regime — regime-specific standard
        deduction)
  - [ ] `cess_rate` — DecimalField(max_digits=5, decimal_places=2, default=Decimal("4.00")) — Health &
        Education Cess applied on computed tax, both regimes (Tax Computation)
  - [ ] `rebate_income_threshold` — DecimalField(max_digits=12, decimal_places=2, null=True,
        blank=True) — Section 87A taxable-income ceiling below which the rebate applies (new-regime
        FY 2025-26: `Decimal("1200000.00")`) — Tax Regime / Section 87A rebate
  - [ ] `rebate_max_tax` — DecimalField(max_digits=12, decimal_places=2, null=True, blank=True) — the
        maximum tax the 87A rebate can zero out (new-regime FY 2025-26: `Decimal("60000.00")`) — Tax
        Regime / Section 87A rebate
  - [ ] `is_default_regime` — BooleanField(default=False) — statutory default is `new` since FY
        2023-24; drives `InvestmentDeclaration.regime_elected`'s default (Tax Regime — new regime is
        the statutory default)
  - [ ] `tax_law_reference` — CharField(max_length=255, blank=True) — free-text note for the unsettled
        Income Tax Act 2025 section renumbering (regulatory caveat above)
  - [ ] `class Meta`: `ordering = ["-financial_year", "regime"]`; `unique_together = ("tenant",
        "financial_year", "regime")`; index `models.Index(fields=["tenant", "financial_year"],
        name="hrm_trc_tenant_fy_idx")`
  - [ ] `__str__` → `f"{self.financial_year} · {self.get_regime_display()}"`

- [ ] `TaxSlabBand(TenantOwned)` — child of `TaxRegimeConfig`, the actual bracket table walked by the
      computation engine (kept a genuine child table, not JSON, for clean bracket-walking — mirrors
      `PayslipLine` being a detail of `Payslip` without inflating the model count; managed **inline**
      on the `TaxRegimeConfig` detail page, like `SalaryStructureLine` on its template):
  - [ ] `config` — `models.ForeignKey("hrm.TaxRegimeConfig", on_delete=models.CASCADE,
        related_name="slab_bands")`
  - [ ] `income_from` — DecimalField(max_digits=12, decimal_places=2)
  - [ ] `income_to` — DecimalField(max_digits=12, decimal_places=2, null=True, blank=True) — null =
        top/unbounded band
  - [ ] `rate_percent` — DecimalField(max_digits=5, decimal_places=2)
  - [ ] `sequence` — PositiveSmallIntegerField(default=0)
  - [ ] `class Meta`: `ordering = ["config", "sequence", "income_from"]`; index
        `models.Index(fields=["tenant", "config"], name="hrm_tsb_tenant_config_idx")`
  - [ ] `clean()` — `income_to` (when set) must be `>= income_from`
  - [ ] `__str__` → `f"{self.config} · {self.income_from}-{self.income_to or '∞'} @ {self.rate_percent}%"`

- [ ] `InvestmentDeclaration(TenantNumbered, NUMBER_PREFIX="ITD")` — the per-employee-per-FY
      declaration header + regime election + both windows (drivers: Zimyo's admin-configurable
      declaration window, Keka's "last date for submission" + regime-change flow, RazorpayX's
      regime-lock-after-election rule):
  - [ ] `employee` — `models.ForeignKey("hrm.EmployeeProfile", on_delete=models.PROTECT,
        related_name="tax_declarations")` — PROTECT (not CASCADE) so a declaration can't vanish out
        from under a linked `TaxComputation`/Form-16 history, matching `Payslip.employee`'s PROTECT
        convention from 3.14
  - [ ] `financial_year` — CharField(max_length=10) — matches `TaxRegimeConfig.financial_year`
  - [ ] `regime_elected` — CharField(max_length=10, choices=`[("old","Old Regime"),
        ("new","New Regime")]`, default="new") — Tax Regime (statutory new-regime default)
  - [ ] `status` — CharField(max_length=15, choices=`[("draft","Draft"),("submitted","Submitted"),
        ("locked","Locked")]`, default="draft") — gates whether `regime_elected` and the declared-
        amount lines stay editable (collapses Zoho/RazorpayX's "lock after first payroll run" rule to
        a simple status field, mirroring `PayrollCycle`'s draft→…→locked convention)
  - [ ] `declaration_window_open` / `declaration_window_close` — DateField(null=True, blank=True) —
        Investment Declaration (tenant-set window)
  - [ ] `proof_window_open` / `proof_window_close` — DateField(null=True, blank=True) — Investment
        Proof (typically later/shorter than the declaration window — Dec-Jan/Jan-Mar per greytHR/
        RazorpayX/Keka)
  - [ ] `previous_employer_income` — DecimalField(max_digits=14, decimal_places=2, default=0) — Tax
        Computation input for a mid-year joiner (greytHR/Zoho Payroll)
  - [ ] `previous_employer_tds` — DecimalField(max_digits=14, decimal_places=2, default=0) — same
  - [ ] `submitted_at` — DateTimeField(null=True, blank=True, editable=False)
  - [ ] `notes` — TextField(blank=True)
  - [ ] `class Meta`: `ordering = ["-financial_year", "employee__party__name"]`; `unique_together =
        ("tenant", "employee", "financial_year")`; indexes `models.Index(fields=["tenant",
        "financial_year"], name="hrm_itd_tenant_fy_idx")`, `models.Index(fields=["tenant", "status"],
        name="hrm_itd_tenant_status_idx")`
  - [ ] `is_editable` **property** → `self.status == "draft"` (used by both the declaration and its
        child lines' edit/delete gating)
  - [ ] `__str__` → `f"{self.number} · {self.employee} · {self.financial_year}"`

- [ ] `InvestmentDeclarationLine(TenantOwned)` — child of `InvestmentDeclaration`, one row per section
      (drivers: Zoho Payroll's/greytHR's section-by-section structure, Keka's declared-vs-approved
      convention; managed **inline** on the declaration detail):
  - [ ] `declaration` — `models.ForeignKey("hrm.InvestmentDeclaration", on_delete=models.CASCADE,
        related_name="lines")`
  - [ ] `section_code` — CharField(max_length=25, choices=`SECTION_CODE_CHOICES`) —
        `[("80c","Section 80C"),("80d","Section 80D — Self & Family"),
        ("80d_parents","Section 80D — Parents"),("hra","HRA Exemption"),
        ("24b_home_loan_interest","Section 24(b) — Home Loan Interest"),
        ("80ccd_1b_nps","Section 80CCD(1B) — NPS"),("lta","Leave Travel Allowance"),
        ("80e_education_loan","Section 80E — Education Loan Interest"),
        ("other_chapter_via","Other Chapter VI-A")]` — Investment Declaration (section taxonomy
        cross-referenced from Zoho Payroll + greytHR + the Form 122/124 unified-form structure)
  - [ ] `declared_amount` — DecimalField(max_digits=12, decimal_places=2, default=0) — the employee's
        initial claim
  - [ ] `verified_amount` — DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
        editable=False) — the FINAL amount used once proofs are checked, set only by the proof
        verification rollup, never form-editable (Keka/greytHR's declared-vs-approved distinction)
  - [ ] `monthly_rent_amount` — DecimalField(max_digits=10, decimal_places=2, null=True, blank=True) —
        HRA-only (blank unless `section_code="hra"`)
  - [ ] `is_metro_city` — BooleanField(default=False) — HRA-only (changes the exemption formula —
        metro = 50% of basic, non-metro = 40%)
  - [ ] `landlord_pan` — CharField(max_length=10, blank=True) — HRA-only, UI-mandatory when
        annualized rent > ₹1,00,000 (Zoho Payroll)
  - [ ] `lender_name` — CharField(max_length=255, blank=True) — 24b-only (blank unless
        `section_code="24b_home_loan_interest"`)
  - [ ] `notes` — TextField(blank=True)
  - [ ] `class Meta`: `ordering = ["declaration", "section_code"]`; `unique_together = ("tenant",
        "declaration", "section_code")` — one row per section per declaration (multiple 80C
        instruments summed into the one line, matching every surveyed product's "one number per
        section" convention); index `models.Index(fields=["tenant", "declaration"],
        name="hrm_idl_tenant_decl_idx")`
  - [ ] `clean()` — HRA sub-fields required only when `section_code="hra"`; `lender_name` only
        meaningful when `section_code="24b_home_loan_interest"` (don't hard-block, just document —
        statutory per-section CAPS are enforced in the `TaxComputation` engine, not here, so a
        declaration can be saved above the cap and be flagged/capped at computation time, not
        silently truncated at entry time)
  - [ ] `__str__` → `f"{self.declaration} · {self.get_section_code_display()}"`

- [ ] `InvestmentProof(TenantOwned)` — child of `InvestmentDeclarationLine`, uploaded evidence +
      verification workflow (drivers: greytHR's Pending/Verified/Rejected/On-Hold POI states with
      employer-employee messaging, Zoho Payroll's per-line "Attach" flow; mirrors
      `EmployeeDocument`'s verified_by/verified_at/editable=False + upload-validation pattern exactly,
      one state richer — 4 states not 3):
  - [ ] `declaration_line` — `models.ForeignKey("hrm.InvestmentDeclarationLine",
        on_delete=models.CASCADE, related_name="proofs")` — a section can have >1 proof (e.g. 80C's
        PPF passbook + LIC receipt)
  - [ ] `file` — `models.FileField(upload_to="hrm/investment_proofs/%Y/%m/")` — add the SAME
        extension/size validation `EmployeeDocument.file` uses (check its `validators=`/clean-time
        guard in the current `apps/hrm/models.py` / `forms.py` before writing this field — reuse the
        identical validator function, don't hand-roll a second one)
  - [ ] `title` — CharField(max_length=255) — e.g. "LIC Premium Receipt", "Rent Agreement"
  - [ ] `amount` — DecimalField(max_digits=12, decimal_places=2, null=True, blank=True) — the specific
        amount this proof substantiates (so a line's `verified_amount` can derive as the sum of its
        individually-verified proofs' amounts)
  - [ ] `verification_status` — CharField(max_length=15, choices=`[("pending","Pending"),
        ("verified","Verified"),("rejected","Rejected"),("on_hold","On Hold")]`, default="pending",
        editable=False) — Investment Proof (greytHR's 4-state POI workflow — distinct from
        `EmployeeDocument.VERIFICATION_STATUS_CHOICES`'s 3-state list, don't reuse it directly)
  - [ ] `verified_by` — `models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="hrm_verified_investment_proofs", editable=False)`
  - [ ] `verified_at` — DateTimeField(null=True, blank=True, editable=False)
  - [ ] `rejection_reason` — TextField(blank=True)
  - [ ] `notes` — TextField(blank=True)
  - [ ] `class Meta`: `ordering = ["-created_at"]`; index `models.Index(fields=["tenant",
        "declaration_line"], name="hrm_ivp_tenant_line_idx")`, index `models.Index(fields=["tenant",
        "verification_status"], name="hrm_ivp_tenant_vstat_idx")`
  - [ ] `__str__` → `f"{self.declaration_line} · {self.title}"`

- [ ] `TaxComputation(TenantNumbered, NUMBER_PREFIX="TXC")` — the per-employee-per-FY engine
      (drivers: greytHR's IT Statement Annual Tax/Tax Paid Till Date/Balance Payable, Keka's
      provisional-vs-approved + manual-override pattern, Zoho/RazorpayX/saral PayPack's side-by-side
      regime comparison, the Form 16 Part-B data it must supply):
  - [ ] `employee` — `models.ForeignKey("hrm.EmployeeProfile", on_delete=models.PROTECT,
        related_name="tax_computations")`
  - [ ] `declaration` — `models.ForeignKey("hrm.InvestmentDeclaration", on_delete=models.PROTECT,
        related_name="tax_computations")` — the deduction source, one-to-one per FY in practice
        (enforced via the same `(tenant, employee, financial_year)` unique_together on this model,
        not a DB-level OneToOne, since a declaration could in principle outlive its computation)
  - [ ] `financial_year` — CharField(max_length=10) — denormalized copy of
        `declaration.financial_year` for easy filtering/reporting
  - [ ] `computation_type` — CharField(max_length=15, choices=`[("provisional","Provisional"),
        ("final","Final")]`, default="provisional") — Tax Computation (`provisional` runs on
        `declared_amount`s from day one of the FY; `final` re-runs on `verified_amount`s once the
        proof window closes)
  - [ ] `manual_override_amount` — DecimalField(max_digits=12, decimal_places=2, null=True,
        blank=True) — Keka's monthly-TDS-override pattern
  - [ ] `override_reason` — TextField(blank=True)
  - [ ] `remaining_pay_periods` — PositiveSmallIntegerField(default=12) — months left in the FY from
        the computation date; user-adjustable (mid-year computations set this lower)
  - [ ] `tax_payable` — DecimalField(max_digits=12, decimal_places=2, default=0, editable=False) —
        derived/cached by `recompute()`: the tax under whichever regime is `declaration.regime_elected`
  - [ ] `tax_paid_ytd` — DecimalField(max_digits=12, decimal_places=2, default=0, editable=False) —
        derived/cached by `recompute()`, aggregated from this employee's TDS-tagged `PayslipLine`
        rows across the FY's `PayrollCycle`s
  - [ ] `monthly_tds_amount` — DecimalField(max_digits=12, decimal_places=2, default=0,
        editable=False) — derived by `recompute()` as `(tax_payable − tax_paid_ytd) /
        remaining_pay_periods`, or `manual_override_amount` when set
  - [ ] `statutory_return` — `models.ForeignKey("hrm.StatutoryReturn", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="tax_computations", editable=False)` — links this Part-B
        detail to the existing `StatutoryReturn(scheme="tds_form16")` row for the same employee/FY
        (Form 16 Generation — **no new Form-16 header table**)
  - [ ] `computed_at` — DateTimeField(null=True, blank=True, editable=False)
  - [ ] `notes` — TextField(blank=True)
  - [ ] `class Meta`: `ordering = ["-financial_year", "employee__party__name"]`; `unique_together =
        ("tenant", "employee", "financial_year")` — one computation per employee per FY, recomputed
        in place (mirrors `Payslip.recompute()`/`StatutoryReturn.recompute()`, never a growing history
        table); indexes `models.Index(fields=["tenant", "financial_year"],
        name="hrm_txc_tenant_fy_idx")`, `models.Index(fields=["tenant", "employee"],
        name="hrm_txc_tenant_emp_idx")`
  - [ ] **static section-applicability-per-regime map** (module-level constant, NOT a DB flag):
        `NEW_REGIME_ALLOWED_SECTIONS = {"80ccd_1b_nps"}` (employer NPS contribution + standard
        deduction survive the new regime; 80C/80D/HRA/24b/LTA/80E/other Chapter VI-A do not) — used
        by `total_chapter_via_deductions`/`hra_exemption` to filter `InvestmentDeclarationLine`s when
        `declaration.regime_elected == "new"`
  - [ ] **statutory per-section caps** (module-level constant): `SECTION_CAPS = {"80c":
        Decimal("150000.00"), "80ccd_1b_nps": Decimal("50000.00"), "24b_home_loan_interest":
        Decimal("200000.00")}` — applied (capped, warned via a `capped_sections` computed list) in
        `total_chapter_via_deductions`, not silently truncated on the declaration line itself
  - [ ] derived **@property** methods (never stored columns, mirroring
        `SalaryStructureTemplate.computed_ctc_total`'s convention):
    - [ ] `gross_annual_income` → `(self.declaration.employee.salary_structures.filter(
          status="active").first().annual_ctc_amount if … else 0) +
          self.declaration.previous_employer_income` (resolve the employee's active
          `EmployeeSalaryStructure`; guard for none)
    - [ ] `hra_exemption` → looks up the `hra` `InvestmentDeclarationLine` (if any and if the
          regime allows it), computes the standard 3-way HRA exemption minimum (rent paid − 10% of
          basic; 50%/40% of basic for metro/non-metro; actual HRA received) using
          `monthly_rent_amount`/`is_metro_city` × 12 — returns `Decimal("0")` under the new regime or
          with no HRA line
    - [ ] `total_chapter_via_deductions` → sums the FINAL amount (verified_amount if not null else
          declared_amount) of every `InvestmentDeclarationLine` whose `section_code` is allowed under
          `declaration.regime_elected` (via `NEW_REGIME_ALLOWED_SECTIONS` when new), capped per
          `SECTION_CAPS`, excluding the `hra` line (handled separately by `hra_exemption`)
    - [ ] `capped_sections` → list of `(section_code, declared_total, cap)` tuples where the capped
          section's total exceeded its statutory cap (surfaced on the detail template as a warning,
          never silently dropped)
    - [ ] `taxable_income_old` / `taxable_income_new` → `gross_annual_income − hra_exemption
          (old only) − standard_deduction (per-regime TaxRegimeConfig) − total_chapter_via_deductions
          (regime-filtered)`, floored at 0
    - [ ] `tax_old_regime` / `tax_new_regime` → walk that regime's `TaxRegimeConfig`/`TaxSlabBand`
          rows for `self.financial_year` (bracket-by-bracket), apply the Section 87A rebate (zero out
          if `taxable_income <= rebate_income_threshold`, capped at `rebate_max_tax`), then add
          `cess_rate`% cess on the post-rebate tax — Tax Regime comparison (side-by-side, before the
          employee/HR commits)
  - [ ] `recompute()` **method** — mirrors `StatutoryReturn.recompute()`'s guard/derive/save shape:
    - [ ] guard: if `self.declaration.status != "locked"` is NOT required (computation can run on a
          draft/submitted declaration for the provisional case) — but DO guard: raise
          `ValidationError` if `self.computation_type == "final"` and the declaration's
          `proof_window_close` hasn't passed yet (final requires proofs settled) — document this
          explicitly, it's the provisional-vs-final gate
    - [ ] `tax_paid_ytd` — aggregate this employee's `PayslipLine` rows tagged TDS
          (`component_name__icontains` a TDS keyword — reuse `StatutoryReturn.SCHEME_KEYWORDS["tds_24q"]`
          list directly, don't redefine a second keyword list) across `PayrollCycle`s whose
          `pay_date` falls in `self.financial_year`'s date range (derive FY start/end from the
          `"YYYY-YY"` string — a small `_fy_date_range()` helper), filtered
          `contribution_side__in=["employee", "both"]` (mirrors 3.15's employee-bucket rule)
    - [ ] `self.tax_payable` = `self.tax_old_regime` if `declaration.regime_elected == "old"` else
          `self.tax_new_regime`
    - [ ] `self.monthly_tds_amount` = `self.manual_override_amount` if set, else
          `((self.tax_payable − self.tax_paid_ytd) / Decimal(self.remaining_pay_periods)).quantize(
          Decimal("0.01"))` if `self.remaining_pay_periods` else `Decimal("0")`
    - [ ] `self.computed_at = timezone.now()`; `self.save(update_fields=["tax_payable",
          "tax_paid_ytd", "monthly_tds_amount", "computed_at", "updated_at"])`
    - [ ] use `Decimal` throughout, `.quantize(Decimal("0.01"))` at every derived-amount step (project
          convention from 3.14/3.15)
  - [ ] `link_form16(user)` **method** (or a thin view-level helper) — `get_or_create`s the
        `StatutoryReturn(tenant=…, scheme="tds_form16", period_start=<FY start>, employee=self.employee)`
        row (via `StatutoryReturn.objects.update_or_create(...)` + its own `.recompute()` for Part-A
        aggregates), sets `self.statutory_return = that_row`, saves — the Form 16 Generation tie-in
        action
  - [ ] `__str__` → `f"{self.number} · {self.employee} · {self.financial_year}"`

- [ ] one incremental migration `apps/hrm/migrations/0027_taxregimeconfig_taxslabband_and_more.py`
      (NOT `0001_initial`; last is `0026_statutoryconfig_statutorystaterule_and_more.py`) —
      `makemigrations hrm`, review the generated file, adjust index/constraint names to match the ones
      specified above if Django's auto-names differ

## B. Workflow + engine actions (views)

- [ ] `investmentdeclaration_submit` (`@login_required`, `@require_POST`) — only from
      `status="draft"`; set `status="submitted"`, `submitted_at=timezone.now()`; `write_audit_log(...,
      {"action": "submit"})`
- [ ] `investmentdeclaration_lock` (`@tenant_admin_required`, `@require_POST`) — only from
      `status="submitted"`; set `status="locked"`; `write_audit_log(..., {"action": "lock"})` — once
      locked, `regime_elected` and every child `InvestmentDeclarationLine` become immutable (gate via
      `declaration.is_editable` in both the line-edit view and `InvestmentDeclarationLineForm`'s
      call-site)
- [ ] `investmentproof_upload` (`@login_required`) — POST-only create on a specific
      `InvestmentDeclarationLine` (`declaration_line_id` from the URL); only while
      `declaration.is_editable` or within the `proof_window_open`/`proof_window_close` window (proofs
      can be uploaded even after the declaration itself is locked, since the proof window is
      typically LATER — do NOT gate proof upload on `declaration.is_editable`, gate it on the proof
      window dates instead, document this explicitly as the deliberate distinction from the
      declaration-line edit gate)
- [ ] `investmentproof_verify` / `_reject` / `_on_hold` (`@tenant_admin_required`, `@require_POST`) —
      only from `verification_status="pending"` (or `"on_hold"` re-triage back to verified/rejected);
      set `verification_status`, `verified_by=request.user`, `verified_at=timezone.now()`,
      `rejection_reason` (reject only); after any status change, recompute the parent
      `InvestmentDeclarationLine.verified_amount` as the sum of that line's `verified` proofs'
      `amount` (fallback: if no per-proof amounts recorded, leave `verified_amount` as HR can also
      hand-set it directly via the line's own edit form when `declaration.is_editable`);
      `write_audit_log(..., {"action": "verify"/"reject"/"on_hold"})`
- [ ] `taxcomputation_generate` (`@tenant_admin_required`, `@require_POST`) — `get_or_create`s the
      `TaxComputation` row for `(tenant, employee, declaration.financial_year)` then calls
      `.recompute()`; mirrors `statutoryreturn_generate`'s idempotent re-aggregate-while-not-locked
      pattern (recompute always allowed — `TaxComputation` has no lock state of its own, only its
      `computation_type` provisional/final distinction gates the proof-settled check inside
      `recompute()`)
- [ ] `taxcomputation_link_form16` (`@tenant_admin_required`, `@require_POST`) — calls
      `computation.link_form16(request.user)`; `messages.success` linking to the created/updated
      `StatutoryReturn` detail page
- [ ] `tax_regime_comparison` (`@login_required`) — **read view**, no new model: given an `employee`
      + `financial_year` (GET params or from an existing `TaxComputation`), render `tax_old_regime`
      vs `tax_new_regime` + the delta ("you'd save ₹X under regime Y") side-by-side — Tax Regime
      comparison (Zoho "Save and Compare" / saral PayPack "Tax Regime Summary" pattern); render
      `hrm/tax/regime_comparison.html`
- [ ] `form16_partb` (`@login_required`) — **read/report view**, no new model: given a
      `TaxComputation` pk, render Part B (gross salary, HRA exemption, standard deduction, Chapter
      VI-A deductions section-by-section from `declaration.lines`, taxable income, tax computed,
      rebate, cess, net tax payable, TDS deducted) + the linked `StatutoryReturn`'s Part-A fields
      (TAN/employer/PAN/period) + the "opting for concessional new-regime tax? Yes/No" line read
      straight off `computation.declaration.regime_elected` — Form 16 Generation (data/report layer;
      PDF rendering deferred); render `hrm/tax/form16_partb.html`

## C. Forms (`apps/hrm/forms.py`)

- [ ] `TaxRegimeConfigForm(TenantModelForm)`:
  - [ ] `Meta.fields = ["financial_year", "regime", "standard_deduction", "cess_rate",
        "rebate_income_threshold", "rebate_max_tax", "is_default_regime", "tax_law_reference"]`
        (exclude `tenant`)
- [ ] `TaxSlabBandForm(TenantModelForm)`:
  - [ ] `Meta.fields = ["income_from", "income_to", "rate_percent", "sequence"]` (exclude
        `tenant`/`config` — `config` set from the URL/parent in the inline-management view, never a
        free-choice dropdown)
- [ ] `InvestmentDeclarationForm(TenantModelForm)`:
  - [ ] `Meta.fields = ["employee", "financial_year", "regime_elected",
        "declaration_window_open", "declaration_window_close", "proof_window_open",
        "proof_window_close", "previous_employer_income", "previous_employer_tds", "notes"]`
        (exclude `tenant`/auto-number `number`/`status`/`submitted_at` — workflow/derived)
  - [ ] custom `__init__` narrows `employee` to `EmployeeProfile.objects.filter(tenant=tenant)`
- [ ] `InvestmentDeclarationLineForm(TenantModelForm)`:
  - [ ] `Meta.fields = ["section_code", "declared_amount", "monthly_rent_amount", "is_metro_city",
        "landlord_pan", "lender_name", "notes"]` (exclude `tenant`/`declaration` [set from parent]/
        `verified_amount` [workflow-derived])
  - [ ] view-level guard (not the form itself): reject save if `not declaration.is_editable`
- [ ] `InvestmentProofForm(TenantModelForm)`:
  - [ ] `Meta.fields = ["file", "title", "amount", "notes"]` (exclude `tenant`/`declaration_line` [set
        from parent]/`verification_status`/`verified_by`/`verified_at`/`rejection_reason` — all
        workflow-owned)
- [ ] `TaxComputationForm(TenantModelForm)`:
  - [ ] `Meta.fields = ["employee", "declaration", "computation_type", "manual_override_amount",
        "override_reason", "remaining_pay_periods", "notes"]` (exclude `tenant`/auto-number
        `number`/`tax_payable`/`tax_paid_ytd`/`monthly_tds_amount`/`statutory_return`/`computed_at` —
        all derived by `recompute()`/`link_form16()`)
  - [ ] custom `__init__` narrows `employee` to `EmployeeProfile.objects.filter(tenant=tenant)` and
        `declaration` to `InvestmentDeclaration.objects.filter(tenant=tenant)`

## D. Views (`apps/hrm/views.py`) — full CRUD + filters via `crud_*`

- [ ] `taxregimeconfig_list` — `crud_list(request, TaxRegimeConfig.objects.filter(
      tenant=request.tenant), "hrm/tax/taxregimeconfig/list.html", search_fields=["financial_year",
      "tax_law_reference"], filters=[("financial_year", "financial_year", False), ("regime", "regime",
      False)], extra_context={"regime_choices": TaxRegimeConfig._meta.get_field("regime").choices})`
- [ ] `taxregimeconfig_create` / `_edit` / `_delete` — standard `crud_create`/`crud_edit`/
      `crud_delete` wrappers
- [ ] `taxregimeconfig_detail` — `crud_detail(...)`; extra_context adds `"slab_bands":
      obj.slab_bands.order_by("sequence")` (the inline-managed child list) — also the entry point for
      the `taxslabband_create`/`_edit`/`_delete` inline actions (URL-scoped under this config's pk)
- [ ] `taxslabband_create` / `_edit` / `_delete` — inline CRUD scoped to a `config_pk` in the URL
      (mirror how `SalaryStructureLine` is managed inline on its template in 3.13 — confirm and match
      that exact view/URL shape); redirect back to `taxregimeconfig_detail`
- [ ] `investmentdeclaration_list` — `crud_list(request,
      InvestmentDeclaration.objects.filter(tenant=request.tenant).select_related("employee__party"),
      "hrm/tax/investmentdeclaration/list.html", search_fields=["number", "employee__party__name"],
      filters=[("financial_year", "financial_year", False), ("regime_elected", "regime_elected",
      False), ("status", "status", False), ("employee", "employee_id", True)],
      extra_context={"status_choices": InvestmentDeclaration._meta.get_field("status").choices,
      "regime_choices": TaxRegimeConfig._meta.get_field("regime").choices, "employees":
      EmployeeProfile.objects.filter(tenant=request.tenant)})`
- [ ] `investmentdeclaration_create` / `_edit` / `_delete` — standard wrappers; `_edit`/`_delete` only
      while `status == "draft"` (mirror `payrollcycle_edit`/`_delete`'s draft-only guard); `_delete`
      also blocked if the declaration has a linked `TaxComputation` (PROTECT will raise — catch and
      surface a friendly `messages.error` instead of a 500)
- [ ] `investmentdeclaration_detail` — `crud_detail(...)`; extra_context adds `"lines":
      obj.lines.order_by("section_code")` (inline-managed) + action buttons for submit/lock — also the
      entry point for `investmentdeclarationline_create`/`_edit`/`_delete` inline actions (URL-scoped
      under this declaration's pk) and `investmentproof_upload` (scoped under a `line_pk`)
- [ ] `investmentdeclarationline_create` / `_edit` / `_delete` — inline CRUD scoped to a `declaration_pk`
      in the URL, gated by `declaration.is_editable`; redirect back to `investmentdeclaration_detail`
- [ ] `investmentdeclaration_submit` / `_lock` — per Section B spec
- [ ] `investmentproof_upload` / `_verify` / `_reject` / `_on_hold` — per Section B spec; `_upload`'s
      list/detail rendered inline on `investmentdeclaration_detail` (each line shows its `proofs`) —
      no standalone `investmentproof_list` required for v1, but ADD one anyway for a
      cross-declaration filterable view: `investmentproof_list` — `crud_list(request,
      InvestmentProof.objects.filter(tenant=request.tenant).select_related(
      "declaration_line__declaration__employee__party"), "hrm/tax/investmentproof/list.html",
      search_fields=["title"], filters=[("verification_status", "verification_status", False)],
      extra_context={"verification_status_choices": InvestmentProof._meta.get_field(
      "verification_status").choices})` (read/verify entry point; no create/edit/delete views beyond
      `_upload` and the verify/reject/on_hold actions — matches `EmployeeDocument`'s pattern of no
      generic edit on a verified artifact)
- [ ] `investmentproof_detail` — `crud_detail(...)` (verify/reject/on_hold action buttons live here)
- [ ] `taxcomputation_list` — `crud_list(request, TaxComputation.objects.filter(
      tenant=request.tenant).select_related("employee__party", "declaration"),
      "hrm/tax/taxcomputation/list.html", search_fields=["number", "employee__party__name"],
      filters=[("financial_year", "financial_year", False), ("computation_type", "computation_type",
      False), ("employee", "employee_id", True)], extra_context={"computation_type_choices":
      TaxComputation._meta.get_field("computation_type").choices, "employees":
      EmployeeProfile.objects.filter(tenant=request.tenant)})`
- [ ] `taxcomputation_create` / `_edit` / `_delete` — standard wrappers (`_delete` blocked if a
      `statutory_return` is linked — PROTECT-style friendly error, though the FK is SET_NULL so this
      is actually safe; still confirm no orphaned `StatutoryReturn.tax_computations` dangling
      reference issue)
- [ ] `taxcomputation_detail` — `crud_detail(...)`; extra_context adds the full derived-property
      breakdown (`gross_annual_income`, `hra_exemption`, `total_chapter_via_deductions`,
      `capped_sections`, `taxable_income_old`/`_new`, `tax_old_regime`/`_new`) rendered as a
      regime-comparison panel + action buttons (`Recompute`, `Link Form 16`, `View Form 16 Part B`)
- [ ] `taxcomputation_generate` / `_link_form16` — per Section B spec
- [ ] `tax_regime_comparison` / `form16_partb` — per Section B spec
- [ ] all new views import the 6 new models + their forms at the top of `views.py`; `Sum`/`Q` from
      `django.db.models`, `transaction` from `django.db`, `Decimal` from `decimal` (already imported
      for 3.14/3.15 — confirm, don't re-import)

## E. URLs (`apps/hrm/urls.py`, `app_name = "hrm"` already set)

- [ ] `path("tax-regimes/", views.taxregimeconfig_list, name="taxregimeconfig_list")`
- [ ] `path("tax-regimes/add/", views.taxregimeconfig_create, name="taxregimeconfig_create")`
- [ ] `path("tax-regimes/<int:pk>/", views.taxregimeconfig_detail, name="taxregimeconfig_detail")`
- [ ] `path("tax-regimes/<int:pk>/edit/", views.taxregimeconfig_edit, name="taxregimeconfig_edit")`
- [ ] `path("tax-regimes/<int:pk>/delete/", views.taxregimeconfig_delete, name="taxregimeconfig_delete")`
- [ ] `path("tax-regimes/<int:config_pk>/slab-bands/add/", views.taxslabband_create, name="taxslabband_create")`
- [ ] `path("tax-regimes/<int:config_pk>/slab-bands/<int:pk>/edit/", views.taxslabband_edit, name="taxslabband_edit")`
- [ ] `path("tax-regimes/<int:config_pk>/slab-bands/<int:pk>/delete/", views.taxslabband_delete, name="taxslabband_delete")`
- [ ] `path("tax-regime-comparison/", views.tax_regime_comparison, name="tax_regime_comparison")`
- [ ] `path("investment-declarations/", views.investmentdeclaration_list, name="investmentdeclaration_list")`
- [ ] `path("investment-declarations/add/", views.investmentdeclaration_create, name="investmentdeclaration_create")`
- [ ] `path("investment-declarations/<int:pk>/", views.investmentdeclaration_detail, name="investmentdeclaration_detail")`
- [ ] `path("investment-declarations/<int:pk>/edit/", views.investmentdeclaration_edit, name="investmentdeclaration_edit")`
- [ ] `path("investment-declarations/<int:pk>/delete/", views.investmentdeclaration_delete, name="investmentdeclaration_delete")`
- [ ] `path("investment-declarations/<int:pk>/submit/", views.investmentdeclaration_submit, name="investmentdeclaration_submit")`
- [ ] `path("investment-declarations/<int:pk>/lock/", views.investmentdeclaration_lock, name="investmentdeclaration_lock")`
- [ ] `path("investment-declarations/<int:declaration_pk>/lines/add/", views.investmentdeclarationline_create, name="investmentdeclarationline_create")`
- [ ] `path("investment-declarations/<int:declaration_pk>/lines/<int:pk>/edit/", views.investmentdeclarationline_edit, name="investmentdeclarationline_edit")`
- [ ] `path("investment-declarations/<int:declaration_pk>/lines/<int:pk>/delete/", views.investmentdeclarationline_delete, name="investmentdeclarationline_delete")`
- [ ] `path("investment-proofs/", views.investmentproof_list, name="investmentproof_list")`
- [ ] `path("investment-proofs/<int:pk>/", views.investmentproof_detail, name="investmentproof_detail")`
- [ ] `path("investment-declaration-lines/<int:line_pk>/proofs/upload/", views.investmentproof_upload, name="investmentproof_upload")`
- [ ] `path("investment-proofs/<int:pk>/verify/", views.investmentproof_verify, name="investmentproof_verify")`
- [ ] `path("investment-proofs/<int:pk>/reject/", views.investmentproof_reject, name="investmentproof_reject")`
- [ ] `path("investment-proofs/<int:pk>/on-hold/", views.investmentproof_on_hold, name="investmentproof_on_hold")`
- [ ] `path("tax-computations/", views.taxcomputation_list, name="taxcomputation_list")`
- [ ] `path("tax-computations/add/", views.taxcomputation_create, name="taxcomputation_create")`
- [ ] `path("tax-computations/<int:pk>/", views.taxcomputation_detail, name="taxcomputation_detail")`
- [ ] `path("tax-computations/<int:pk>/edit/", views.taxcomputation_edit, name="taxcomputation_edit")`
- [ ] `path("tax-computations/<int:pk>/delete/", views.taxcomputation_delete, name="taxcomputation_delete")`
- [ ] `path("tax-computations/<int:pk>/generate/", views.taxcomputation_generate, name="taxcomputation_generate")`
- [ ] `path("tax-computations/<int:pk>/link-form16/", views.taxcomputation_link_form16, name="taxcomputation_link_form16")`
- [ ] `path("tax-computations/<int:pk>/form16-partb/", views.form16_partb, name="form16_partb")`

## F. Admin (`apps/hrm/admin.py`)

- [ ] register `TaxRegimeConfig` — `list_display = ("financial_year", "regime",
      "standard_deduction", "cess_rate", "is_default_regime")`, `list_filter = ("tenant",
      "financial_year", "regime")`, `search_fields = ("financial_year", "tax_law_reference")`
- [ ] register `TaxSlabBand` as a `TabularInline` on `TaxRegimeConfigAdmin` (`model = TaxSlabBand`,
      `extra = 1`, `fields = ("income_from", "income_to", "rate_percent", "sequence")`)
- [ ] register `InvestmentDeclaration` — `list_display = ("number", "employee", "financial_year",
      "regime_elected", "status")`, `list_filter = ("tenant", "financial_year", "regime_elected",
      "status")`, `search_fields = ("number", "employee__party__name")`
- [ ] register `InvestmentDeclarationLine` as a `TabularInline` on `InvestmentDeclarationAdmin`
      (`model = InvestmentDeclarationLine`, `extra = 0`, `fields = ("section_code",
      "declared_amount", "verified_amount")`, `readonly_fields = ("verified_amount",)`)
- [ ] register `InvestmentProof` — `list_display = ("declaration_line", "title", "amount",
      "verification_status", "verified_by", "verified_at")`, `list_filter = ("tenant",
      "verification_status")`, `search_fields = ("title",)`
- [ ] register `TaxComputation` — `list_display = ("number", "employee", "financial_year",
      "computation_type", "tax_payable", "tax_paid_ytd", "monthly_tds_amount")`, `list_filter =
      ("tenant", "financial_year", "computation_type")`, `search_fields = ("number",
      "employee__party__name")`

## G. Templates (`templates/hrm/tax/<entity>/<page>.html`)

- [ ] `tax/taxregimeconfig/list.html` — filter bar: search `q`, `financial_year` free-text/select,
      `regime` select (from `regime_choices`); columns: financial_year, regime badge (`old`→
      `badge-slate`, `new`→`badge-info`), standard_deduction, cess_rate, is_default_regime badge,
      Actions (view/edit/delete); pagination; empty-state
- [ ] `tax/taxregimeconfig/detail.html` — header (financial_year, regime badge, standard_deduction,
      cess_rate, rebate_income_threshold/rebate_max_tax, is_default_regime badge,
      tax_law_reference); **slab bands table** (income_from–income_to, rate_percent, sequence) with
      inline add/edit/delete rows (mirror `salarystructuretemplate/detail.html`'s line-management
      UI); Actions sidebar (Edit/Delete/Back to List)
- [ ] `tax/taxregimeconfig/form.html` — standard form
- [ ] `tax/regime_comparison.html` — **standalone page** at the sub-module root (Template Folder
      Structure rule 6): employee + financial_year picker, side-by-side old-vs-new panel
      (taxable_income, tax before rebate, rebate applied, cess, net tax payable), a highlighted
      "you'd save ₹X under the {regime} regime" banner; empty-state if no `TaxComputation` exists yet
      for the pair (link to `taxcomputation_create`/`_generate`)
- [ ] `tax/investmentdeclaration/list.html` — filter bar: search `q`, `financial_year`, `regime_elected`
      select, `status` select (from `status_choices`), `employee` select (from `employees`,
      `|stringformat:"d"` pk-compare); columns: number, employee, financial_year, regime_elected
      badge, status badge (`draft`→`badge-muted`, `submitted`→`badge-amber`, `locked`→`badge-green`),
      Actions (view/edit-if-draft/delete-if-draft); pagination; empty-state; always
      `{% else %}{{ obj.get_status_display }}` fallback
- [ ] `tax/investmentdeclaration/detail.html` — header (employee, financial_year, regime_elected
      badge, status badge, both windows, previous_employer_income/tds); workflow buttons
      (`Submit` — draft only, POST+confirm+csrf; `Lock` — submitted only, tenant-admin,
      POST+confirm+csrf); **section lines table** (section_code, declared_amount, verified_amount,
      HRA/24b sub-fields where applicable) with inline add/edit/delete gated by `obj.is_editable`,
      each line showing its `proofs` (title, amount, verification_status badge — `pending`→
      `badge-muted`, `verified`→`badge-green`, `rejected`→`badge-red`, `on_hold`→`badge-amber`) +
      an upload-proof form/link + verify/reject/on_hold buttons (tenant-admin only) per proof; Actions
      sidebar (Edit-if-draft/Delete-if-draft, Back to List)
- [ ] `tax/investmentdeclaration/form.html` — standard form
- [ ] `tax/investmentproof/list.html` — filter bar: search `q`, `verification_status` select (from
      `verification_status_choices`); columns: declaration_line (→ employee/section), title, amount,
      verification_status badge, verified_by, verified_at, Actions (view); pagination; empty-state
- [ ] `tax/investmentproof/detail.html` — header (declaration_line link, file download link, title,
      amount, verification_status badge, verified_by/at, rejection_reason); Actions sidebar
      (`Verify`/`Reject` [with a rejection_reason textarea]/`On Hold` — all tenant-admin,
      POST+confirm+csrf, only while `pending`/`on_hold`; Back to List)
- [ ] `tax/taxcomputation/list.html` — filter bar: search `q`, `financial_year`, `computation_type`
      select (from `computation_type_choices`), `employee` select (from `employees`, pk-compare);
      columns: number, employee, financial_year, computation_type badge (`provisional`→`badge-amber`,
      `final`→`badge-green`), tax_payable, tax_paid_ytd, monthly_tds_amount, Actions
      (view/edit/delete); pagination; empty-state
- [ ] `tax/taxcomputation/detail.html` — header (employee, declaration link, financial_year,
      computation_type badge, manual_override_amount/override_reason if set, remaining_pay_periods,
      computed_at); **derived breakdown panel** (gross_annual_income, hra_exemption,
      total_chapter_via_deductions [+ `capped_sections` warning list if non-empty],
      taxable_income_old/_new, tax_old_regime/_new side-by-side, tax_payable, tax_paid_ytd,
      monthly_tds_amount); statutory_return link if set; action buttons (`Recompute`,
      POST+confirm+csrf; `Link Form 16` — tenant-admin, POST+confirm+csrf; `View Form 16 Part B` link
      to `form16_partb`); Actions sidebar (Edit/Delete, Back to List)
- [ ] `tax/taxcomputation/form.html` — standard form
- [ ] `tax/form16_partb.html` — **standalone report page** at the sub-module root: Part A block (TAN,
      employer name/PAN-of-deductor/circle-address from `StatutoryConfig`, employee PAN from
      `EmployeeProfile.national_id`, FY, linked `StatutoryReturn.employee_contribution_total`/
      `status`/`filed_on`), Part B block (gross salary, HRA exemption, standard deduction, section-
      wise Chapter VI-A deductions table from `declaration.lines`, taxable income, tax computed,
      87A rebate, cess, net tax payable, TDS deducted), the "opting for concessional new-regime tax?
      Yes/No" line from `regime_elected`; a visible "PDF rendering not yet available — data view only"
      note (per the deferred PDF-rendering scope)

## H. Seeder (`apps/hrm/management/commands/seed_hrm.py`)

- [ ] add `_seed_tax(self, tenant, *, flush)` method, called from `handle()` **AFTER**
      `self._seed_statutory(tenant, flush=options["flush"])` (Form-16 linkage needs 3.15's
      `StatutoryReturn`/`StatutoryConfig` rows to exist first; the TDS-YTD aggregation needs 3.14's
      `PayslipLine` rows)
- [ ] `if flush:` child-first wipe: `TaxComputation.objects.filter(tenant=tenant).delete()` →
      `InvestmentProof.objects.filter(tenant=tenant).delete()` →
      `InvestmentDeclarationLine.objects.filter(tenant=tenant).delete()` →
      `InvestmentDeclaration.objects.filter(tenant=tenant).delete()` →
      `TaxSlabBand.objects.filter(tenant=tenant).delete()` →
      `TaxRegimeConfig.objects.filter(tenant=tenant).delete()`
- [ ] `if TaxRegimeConfig.objects.filter(tenant=tenant).exists(): self.stdout.write(self.style.NOTICE(
      f"Tax & Investment data already exists for '{tenant.name}'. Use --flush to re-seed.")); return`
- [ ] create 2 `TaxRegimeConfig` rows for `financial_year="2025-26"`:
  - [ ] `regime="new"`: `standard_deduction=Decimal("75000.00")`, `cess_rate=Decimal("4.00")`,
        `rebate_income_threshold=Decimal("1200000.00")`, `rebate_max_tax=Decimal("60000.00")`,
        `is_default_regime=True`, `tax_law_reference="FY 2025-26 rates per Finance Act; Income Tax
        Act 2025 section renumbering pending as of this seed."` — with 7 `TaxSlabBand` rows: `0-4L
        @0%`, `4-8L @5%`, `8-12L @10%`, `12-16L @15%`, `16-20L @20%`, `20-24L @25%`, `24L+ @30%`
        (`income_to=None` on the last)
  - [ ] `regime="old"`: `standard_deduction=Decimal("50000.00")`, `cess_rate=Decimal("4.00")`,
        `rebate_income_threshold=Decimal("500000.00")`, `rebate_max_tax=Decimal("12500.00")`,
        `is_default_regime=False` — with 4 `TaxSlabBand` rows: `0-2.5L @0%`, `2.5-5L @5%`, `5-10L
        @20%`, `10L+ @30%`
- [ ] for one seeded `EmployeeProfile` with an active `EmployeeSalaryStructure` (reuse 3.13/3.14's
      seeded employee): create 1 `InvestmentDeclaration` (`financial_year="2025-26"`,
      `regime_elected="old"` — deliberately old so the declaration lines actually reduce tax in the
      demo, `status="submitted"`, `declaration_window_open/close` and `proof_window_open/close` set to
      a plausible past/current date range, `previous_employer_income=0`, `previous_employer_tds=0`)
  - [ ] 2 `InvestmentDeclarationLine` rows: `section_code="80c"` (`declared_amount=Decimal(
        "150000.00")`), `section_code="hra"` (`declared_amount=Decimal("0.00")` — HRA is exemption-
        derived, not a flat amount — set `monthly_rent_amount=Decimal("15000.00")`,
        `is_metro_city=True`)
  - [ ] 1 `InvestmentProof` on the 80C line: `title="LIC Premium Receipt"`,
        `amount=Decimal("150000.00")`, `verification_status="verified"`,
        `verified_by=` a seeded tenant-admin user, `verified_at=timezone.now()` — then set that
        line's `verified_amount=Decimal("150000.00")` directly (demonstrating the declared==verified
        settled case)
- [ ] generate 1 `TaxComputation` for that employee/FY: `computation_type="final"`,
      `remaining_pay_periods=` months remaining from the seeded `PayrollCycle`'s period, call
      `.recompute()`, then call `.link_form16(admin_user)` to demonstrate the `StatutoryReturn(
      scheme="tds_form16")` tie-in (reuses/creates the row for this employee/FY)
- [ ] print a summary line: `f"Tax & Investment seeded for '{tenant.name}': 2 regime configs (11 slab
      bands), 1 declaration ({declaration.number}), 1 proof, 1 computation ({computation.number}
      → {computation.tax_payable} payable)."`
- [ ] add the 6 tables to the `--flush` wipe order in dependency sequence (children first, already
      specified above — restate here for the flush-order checklist): `TaxComputation` →
      `InvestmentProof` → `InvestmentDeclarationLine` → `InvestmentDeclaration` → `TaxSlabBand` →
      `TaxRegimeConfig`; confirm this sits BEFORE `EmployeeProfile`'s own central wipe (both
      `InvestmentDeclaration.employee` and `TaxComputation.employee` are PROTECT)
- [ ] verify the seeder still prints the tenant-admin login reminder + "Data already exists" warning
      path unchanged — the new block is itself idempotent, no new top-level guard needed

## I. Navigation (`apps/core/navigation.py`)

- [ ] add `LIVE_LINKS["3.16"]` (verify the exact query-string/routing convention against 3.14/3.15's
      existing entries before finalizing):
      ```python
      # 3.16 Tax & Investment — TaxRegimeConfig/comparison serves Tax Regime; InvestmentDeclaration
      # serves Investment Declaration; InvestmentProof (pending filter) serves Investment Proof;
      # TaxComputation serves Tax Computation; Form16 Part B report serves Form 16 Generation.
      "3.16": {
          "Tax Regime": "hrm:taxregimeconfig_list",                                  # bullet
          "Investment Declaration": "hrm:investmentdeclaration_list",                # bullet
          "Investment Proof": "hrm:investmentproof_list?verification_status=pending", # bullet
          "Tax Computation": "hrm:taxcomputation_list",                              # bullet
          "Form 16 Generation": "hrm:taxcomputation_list",                           # bullet (detail links to form16_partb)
      },
      ```
      — all 5 NavERP.md 3.16 bullets go Live; adjust the literal query strings if the real filter
      param names implemented in Section D differ; "Form 16 Generation" deliberately routes through
      the computation list (no standalone Form-16 list model per the reuse decision) — document this
      routing rationale in the navigation.py comment, mirroring 3.15's PT/LWF-vs-PF/ESI/TDS routing
      split precedent

## J. Migrate / seed / verify (run from the venv)

- [ ] `python manage.py makemigrations hrm` → review `0027_...py` (field/index/unique_together names
      match the plan; confirm the `StatutoryReturn`/`EmployeeProfile`/`InvestmentDeclaration` FK
      chains don't trigger a spurious cross-dependency issue — they shouldn't, all plain FK-by-string)
- [ ] `python manage.py migrate`
- [ ] `python manage.py seed_hrm` (1st run — creates data; confirm 3.15's `_seed_statutory` still runs
      first and the new `_seed_tax` block generates its configs/declaration/proof/computation against
      it)
- [ ] `python manage.py seed_hrm` (2nd run — must be idempotent, no duplicates, no errors)
- [ ] `python manage.py check`
- [ ] `temp/` smoke sweep: every new `hrm:taxregimeconfig_*`, `hrm:taxslabband_*`,
      `hrm:tax_regime_comparison`, `hrm:investmentdeclaration_*`, `hrm:investmentdeclarationline_*`,
      `hrm:investmentproof_*`, `hrm:taxcomputation_*`, and `hrm:form16_partb` URL returns 200/302 when
      logged in as a tenant admin; no `{#`/`{% comment` leaks in the new templates; cross-tenant IDOR
      check — a `TaxRegimeConfig`/`InvestmentDeclaration`/`InvestmentProof`/`TaxComputation` pk
      belonging to tenant A returns 404 when fetched as tenant B; `taxcomputation_generate` run twice
      produces the same `tax_payable`/`tax_paid_ytd`/`monthly_tds_amount` (idempotent recompute, no
      duplication); spot-check the seeded computation's `tax_old_regime` arithmetic by hand against
      the 4-slab old-regime table + 87A rebate + 4% cess; `investmentdeclaration_lock` blocks further
      line edits (guarded by `is_editable`); `investmentproof_verify`/`_reject`/`_on_hold` blocked for
      non-tenant-admin (403); the 87A rebate zeroes tax correctly when taxable income is at/below the
      threshold; `SECTION_CAPS` caps (not silently truncates) an over-declared 80C amount and surfaces
      it in `capped_sections`; `link_form16` creates/reuses exactly one `StatutoryReturn(
      scheme="tds_form16")` row per (employee, FY) — no duplicates on a second call; the `?
      verification_status=pending` deep-link renders the filtered subset correctly
- [ ] sidebar: confirm 3.16 shows all five bullets as **Live** (not "Coming soon") for a tenant with
      data

## K. Close-out

- [ ] update `README.md` module-status / HRM section (3.16 bullets: Tax Regime / Investment
      Declaration / Investment Proof / Tax Computation / Form 16 Generation all live; bump the HRM +
      project-wide test-count lines once test-writer runs)
- [ ] run the review-agent sequence in order, each ending in its own commit(s): `code-reviewer` →
      `explorer` → `frontend-reviewer` → `performance-reviewer` → `qa-smoke-tester` →
      `security-reviewer` → `test-writer`
- [ ] update `.claude/skills/hrm/SKILL.md` — 3.16 section: document `TaxRegimeConfig`/`TaxSlabBand`/
      `InvestmentDeclaration`/`InvestmentDeclarationLine`/`InvestmentProof`/`TaxComputation` models,
      the `recompute()` calc-engine contract (regime comparison, 87A rebate, cess, section caps, TDS-
      YTD aggregation reusing 3.15's `SCHEME_KEYWORDS["tds_24q"]`), the submit/lock + proof-
      verification workflows, the `link_form16()` tie-in to `StatutoryReturn(scheme="tds_form16")`,
      the new `LIVE_LINKS["3.16"]` entries (incl. the Form-16-routes-to-computation-list rationale),
      the extended seeder block, and mark all 5 bullets of 3.16 as built

## Review — 3.16 Tax & Investment (built 2026-07-05)

**Shipped (6 tables, all wired Live, migration `0027`).** `TaxRegimeConfig` (+ `TaxSlabBand` slab table, per FY/regime
std-deduction/cess/87A), `InvestmentDeclaration` (`ITD-`, draft→submitted→locked) + `InvestmentDeclarationLine`
(section 80C/80D/HRA/24b/NPS, declared-vs-verified) + `InvestmentProof` (FileField + 4-state verify), `TaxComputation`
(`TXC-` engine — `recompute()`: progressive slabs → 87A rebate → 4% cess; HRA 3-way exemption; regime-filtered
Chapter-VI-A + `SECTION_CAPS`; TDS-YTD from `PayslipLine`; monthly spread). **Form 16 reuses the existing
`StatutoryReturn(tds_form16)`** via `TaxComputation.statutory_return` + `link_form16()` — **no new Form 16 table**.
Reuses `EmployeeProfile`/`EmployeeSalaryStructure`/`PayslipLine`/`StatutoryConfig`/`StatutoryReturn`; **no GL path**
(`accounting.PayrollRun`/`JournalEntry` untouched). `LIVE_LINKS["3.16"]` — all 5 bullets Live. `_seed_tax` after
`_seed_statutory` (2 regime configs / 11 slab bands, an old-regime declaration + 80C/HRA lines + a verified proof, a
generated + Form-16-linked computation: **52520 old / 0 new** via 87A — hand-verified).

**Verification.** `manage.py check` clean; no pending migrations; seeder idempotent; smoke sweep 200/302/405 on all
routes, no leaks, cross-tenant IDOR→404, idempotent recompute.

**Review agents (all run in order; findings applied + committed):**
- code-reviewer — **1 Critical fixed**: `TaxComputation.financial_year` was excluded from the form + never set →
  every UI-created computation silently computed 0 tax (+ 500 on the 2nd). Fixed in `save()` (derive from declaration)
  + `TaxComputationForm.clean()` (employee-match + form-level dup guard). + proof terminal-state guard, docstring.
- explorer — no wiring bugs; confirmed the Form-16-reuse design + zero accounting refs.
- frontend-reviewer — proofs-table empty-state (flat `proofs` list), `.table-wrap` on the comparison table, aria-labels.
- performance-reviewer — memoized the engine's DB primitives (`_engine_cache`) → computation detail **~60 → ~9
  queries**; dropped a dead `select_related`.
- qa-smoke-tester — all green, no bugs.
- security-reviewer — all PASS; masked the PAN in `form16_partb` (last-4, matching the app convention).
- test-writer — **245 tests** (68 model / 104 view / 73 security), all pass; HRM suite 2,395→**2,640**, project-wide
  5,042→**5,287**. Surfaced a real transaction-poisoning bug (duplicate-section IntegrityError → 400) — **fixed** by
  wrapping the save in a `transaction.atomic()` savepoint + inverted the test. Flagged the same pre-existing bug in
  3.5 `approval_add` / 3.8 `offerapproval_add` as a **separate task** (out of 3.16 scope).

**Next:** 3.17 Payout & Reports.

## Later passes / deferred (carried over from research-tax-investment.md — do not build this pass)

- **Form 16/16A/Part-A+B PDF rendering, merge, and email delivery** — presentation/document-
  generation layer, consistent with the payslip-PDF and Form-16-PDF deferrals already noted in the
  3.14/3.15 research; `form16_partb.html` is a data/report view only this pass.
- **TRACES portal integration** (downloading the government-issued Part A file/zip and importing it)
  — external government-portal API/file integration, not buildable in a single Django pass.
- **Form 16A (non-salary/vendor TDS certificate)** — belongs conceptually to Accounts Payable/vendor
  withholding, not the employee-tax scope of 3.16; not modeled here.
- **Bulk Excel import of employee declarations** (saral PayPack, Zoho Payroll "submit on behalf of")
  — v1 supports manual per-employee entry (including HR entering on an employee's behalf via the same
  form); a bulk import/export pipeline is a fast-follow.
- **AI-assisted anomaly detection on tax declarations** and **TRACES-notice early-warning system** —
  both are rules/ML layers on top of the core computation, deferred as fast-follows.
- **Automatic regime-change lock enforcement tied to "first payroll run of the FY"** — v1 gates
  editability via `InvestmentDeclaration.status` (draft/submitted/locked) rather than an automatic
  date/event-driven lock keyed to `PayrollCycle` creation; a tighter automatic trigger is a
  fast-follow.
- **Full instrument-level 80C sub-ledger** (tracking each individual PPF/ELSS/insurance policy
  separately rather than one summed `declared_amount` per section) — every surveyed product collapses
  to one number per section for computation purposes; deferred unless a future audit requirement
  demands it.
- **Non-India / multi-country tax-regime support** — this catalog is India-specific per 3.15's
  existing India-only statutory scope; extending regime/slab modeling to other jurisdictions is a
  future-pass consideration.
- **Exact Income Tax Act 2025 section-renumbering adoption** (the "Form 122" vs "Form 124" naming
  inconsistency and renumbered section codes) — modeled defensively via descriptive `section_code`
  choices + `TaxRegimeConfig.tax_law_reference`; revisit once the renumbering is finalized in official
  guidance.
- **Availability gating on Q4 24Q filing completion before Form 16 issuance** — v1's `link_form16()`
  creates/links the `StatutoryReturn(scheme="tds_form16")` row unconditionally; a view-level guard
  checking the related `tds_24q` `StatutoryReturn` rows' `status="filed"` first is a fast-follow, not
  blocking v1.
- **Per-`PayslipLine` scheme tagging** (replacing the `SCHEME_KEYWORDS` substring heuristic reused
  from 3.15) — same deferral as noted in the 3.15 review; a real per-line scheme tag would require a
  3.14 model change.

## Review notes
(filled in at the end)

---
# Module 3 — HRM — Sub-module 3.17 Payout & Reports (payout-reports) — plan from research-payout-reports.md (2026-07-05)

**Context.** Extends the existing `apps/hrm` app — NOT a new app. Builds the disbursement-tracking +
distribution-tracking + reconciliation layer strictly ON TOP of 3.14 (`PayrollCycle`/`Payslip`/
`PayslipLine`) and reuses 3.1's `EmployeeProfile` bank fields. 4 new tables, all appended to
`apps/hrm/models.py`, migration `0028` (last is `0027_investmentdeclaration_investmentdeclarationline_
and_more.py` from 3.16). Money still posts only through `accounting.PayrollRun`/`JournalEntry` (lesson
**L29**) — **3.17 posts nothing new to the GL**; it tracks payment status, distribution status, and
reconciliation status only — bookkeeping *about* a payment already recorded through
`accounting.PayrollRun`, never a new Dr/Cr entry.

NavERP.md 3.17 bullets (exact text, all 4 go Live this pass):
- Bank Integration — Bank file generation, direct deposit.
- Payslip Generation — Digital payslips, email distribution.
- Payment Register — Payment summary, batch reports.
- Reconciliation — Bank reconciliation, error reports.

Reuses (no duplication): `hrm.PayrollCycle` (`is_locked` gate + `accounting_payroll_run` — a batch is
generated only from a locked cycle), `hrm.Payslip` (`net_pay`/`on_hold`/`employee` — the amount to
disburse is read from here, never re-entered), `hrm.EmployeeProfile` (`bank_name`/`masked_bank_account()`/
`masked_bank_routing()` — snapshot the MASKED values only, the disbursement destination; no new employee/
bank-master table), `settings.AUTH_USER_MODEL` (audit actors). Never touches
`accounting.PayrollRun`/`JournalEntry` — no GL-posting path (L29). **No `BankStatementLine` model** — v1
reconciles directly against `PayoutPayment.transaction_reference`/`status` (per research recommendation,
keeping the build at 4 models).

**Sensitive-field note (decide, don't guess):** `PayoutPayment.bank_account_last4_snapshot` /
`bank_routing_snapshot` store already-MASKED (`••••1234`) copies, never the raw account/routing number —
unlike `EmployeeProfile.bank_account`/`bank_routing` (which ARE in `core.crud._SENSITIVE_AUDIT_FIELDS`
because they hold the raw value). Because the snapshot fields hold only masked text, they do **NOT** need
to be added to `_SENSITIVE_AUDIT_FIELDS` — document this explicitly in the model docstring so a future
reviewer doesn't "fix" it by redacting an already-safe value. `transaction_reference` (a bank UTR/trace
number, not an account number) also does not need redaction.

## A. Models + migration (`apps/hrm/models.py`)

- [ ] `PayoutBatch(TenantNumbered, NUMBER_PREFIX="POB")` — the disbursement-run header, generated from
      one locked `PayrollCycle` (drivers: Keka's payment-automation wizard runs after payroll closes;
      Darwinbox/Deel's payment-after-approval ordering; greytHR's Bank Transfer Advice report needing a
      batch to summarize):
  - [ ] `cycle` — `models.ForeignKey("hrm.PayrollCycle", on_delete=models.PROTECT,
        related_name="payout_batches")` — PROTECT so a batch can't vanish out from under its
        `PayoutPayment`/`BankReconciliation` history, matching `Payslip.employee`'s PROTECT convention
  - [ ] `status` — CharField(max_length=20, choices=`[("draft","Draft"),("approved","Approved"),
        ("disbursed","Disbursed"),("partially_disbursed","Partially Disbursed"),
        ("reconciled","Reconciled")]`, default="draft") — mirrors `PayrollCycle`'s state-machine
        convention; `partially_disbursed` covers some-paid/some-failed (Bank Integration)
  - [ ] `bank_file_format` — CharField(max_length=15, choices=`[("neft","NEFT"),("nach","NACH"),
        ("ach","ACH"),("manual","Manual"),("other","Other")]`, default="neft") — Bank Integration
        (Keka's bank-specific templates, NACH/ACH-rail research; leaves room for a future `wps_sif`
        value without a schema change)
  - [ ] `source_bank_name` — CharField(max_length=255, blank=True) — Keka's "disbursal account shown
        before initiating payment"
  - [ ] `source_account_last4` — CharField(max_length=8, blank=True) — masked, never the full
        disbursing account number (Bank Integration)
  - [ ] `generated_by` — `models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="hrm_payout_batch_generations", editable=False)`
  - [ ] `generated_at` — DateTimeField(null=True, blank=True, editable=False)
  - [ ] `approved_by` — `models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="hrm_payout_batch_approvals", editable=False)`
  - [ ] `approved_at` — DateTimeField(null=True, blank=True, editable=False)
  - [ ] `disbursed_at` — DateTimeField(null=True, blank=True, editable=False)
  - [ ] `notes` — TextField(blank=True)
  - [ ] `class Meta`: `ordering = ["-cycle__pay_date"]`; `unique_together = ("tenant", "cycle")` — one
        payout batch per cycle (regenerating replaces/updates while draft, matching 3.14's
        "regenerate while draft" convention); index `models.Index(fields=["tenant", "status"],
        name="hrm_pob_tenant_status_idx")`
  - [ ] `clean()` — raise `ValidationError({"cycle": "..."})` if `self.cycle_id` and not
        `self.cycle.is_locked` (a batch cannot be created/generated against a draft/unlocked cycle)
  - [ ] `is_editable` **property** → `self.status == "draft"`
  - [ ] `_totals()` **method** — one aggregate query over `self.payments`, cached per instance
        (mirrors `PayrollCycle._totals()` exactly): `Sum("net_amount")` for `total_amount`; separate
        `.filter(status="paid").aggregate(c=Count("id"), a=Sum("net_amount"))` for
        `paid_count`/`paid_amount`; `.filter(status="failed").count()` for `failed_count`;
        `.filter(status="on_hold").count()` for `on_hold_count`
  - [ ] derived **@property**: `headcount` (`self.payments.count()`), `total_amount`, `paid_count`,
        `paid_amount`, `failed_count`, `on_hold_count` — all read `self._totals()` — feeds the Payment
        Register report directly
  - [ ] `__str__` → `f"{self.number} · {self.cycle.number} · {self.get_status_display()}"`

- [ ] `PayoutPayment(TenantOwned)` — child of `PayoutBatch`, one row per disbursed employee (drivers:
      Zoho Payroll's per-payment status lifecycle, HROne's bank-advice-statement line, NACH/ACH's
      UTR-matching convention):
  - [ ] `batch` — `models.ForeignKey("hrm.PayoutBatch", on_delete=models.CASCADE,
        related_name="payments")`
  - [ ] `payslip` — `models.ForeignKey("hrm.Payslip", on_delete=models.PROTECT,
        related_name="payout_payments")` — the amount source; `net_pay` is read from here, never
        re-entered
  - [ ] `employee` — `models.ForeignKey("hrm.EmployeeProfile", on_delete=models.PROTECT,
        related_name="payout_payments")` — denormalized off `payslip.employee` for simpler list/filter
        queries (matches `Payslip.employee` alongside `Payslip.cycle` convention)
  - [ ] `net_amount` — DecimalField(max_digits=14, decimal_places=2, default=0, editable=False) —
        snapshot of `payslip.net_pay` at batch-generation time, so a later correction in a NEW cycle
        never rewrites a historical payment record
  - [ ] `bank_name_snapshot` — CharField(max_length=255, blank=True, editable=False) — masked copy of
        `EmployeeProfile.bank_name` at generation time
  - [ ] `bank_account_last4_snapshot` — CharField(max_length=8, blank=True, editable=False) — from
        `employee.masked_bank_account()` at generation time (**already masked — never the full
        account**)
  - [ ] `bank_routing_snapshot` — CharField(max_length=20, blank=True, editable=False) — from
        `employee.masked_bank_routing()` at generation time (**already masked**)
  - [ ] `payment_method` — CharField(max_length=15, choices=`[("bank_transfer","Bank Transfer"),
        ("neft","NEFT"),("nach","NACH"),("ach","ACH"),("cheque","Cheque"),("cash","Cash"),
        ("other","Other")]`, default="bank_transfer") — Zoho Payroll / greytHR's alternate-mode
        recording
  - [ ] `status` — CharField(max_length=15, choices=`[("pending","Pending"),
        ("processing","Processing"),("paid","Paid"),("failed","Failed"),("returned","Returned"),
        ("on_hold","On Hold")]`, default="pending") — Zoho Payroll's Initiated→Pending→Successful/
        Failed lifecycle, extended with `returned` (NACH return-file concept) and `on_hold` (an
        employee whose `Payslip.on_hold=True` included as a zero-action row for audit completeness,
        never actually paid)
  - [ ] `transaction_reference` — CharField(max_length=64, blank=True) — the bank-assigned UTR/trace
        number, the reconciliation match key (Reconciliation)
  - [ ] `initiated_at` — DateTimeField(null=True, blank=True, editable=False)
  - [ ] `paid_on` — DateTimeField(null=True, blank=True, editable=False) — two timestamps, not one
        (Gusto's "submitted ≠ arrived" distinction; NACH's T+1 settlement lag)
  - [ ] `failure_reason` — TextField(blank=True) — RazorpayX's documented failure-cause list
        (non-working-day, non-whitelisted account, incorrect bank details), NACH's return-reason-code
        convention
  - [ ] `retry_of` — `models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="retries")` — Zoho Payroll's "Re-initiate Payment" pattern: a corrected retry
        references the original failed attempt rather than mutating it, preserving failure history
  - [ ] `class Meta`: `ordering = ["batch", "employee__party__name"]`; `unique_together = ("tenant",
        "batch", "payslip")` — one payment row per payslip per batch (a retry is a new row via
        `retry_of`, not an in-place edit); indexes `models.Index(fields=["tenant", "batch"],
        name="hrm_pop_tenant_batch_idx")`, `models.Index(fields=["tenant", "status"],
        name="hrm_pop_tenant_status_idx")`
  - [ ] `__str__` → `f"{self.employee} · {self.net_amount} · {self.get_status_display()}"`

- [ ] `PayslipDistribution(TenantOwned)` — 1:1 with `hrm.Payslip`, delivery-tracking (drivers: Zimyo's
      send-confirmation flow, Keka/HROne's portal-download-as-primary-channel, Gusto's lifetime-access
      paystub history, Deel's payment-before-payslip-release ordering):
  - [ ] `payslip` — `models.OneToOneField("hrm.Payslip", on_delete=models.CASCADE,
        related_name="distribution")`
  - [ ] `delivery_channel` — CharField(max_length=10, choices=`[("email","Email"),("portal","Portal"),
        ("print","Print")]`, default="portal") — Keka's bulk-print fallback, HROne's ESS-portal
        publish, Zimyo's email flow
  - [ ] `status` — CharField(max_length=15, choices=`[("pending","Pending"),("sent","Sent"),
        ("viewed","Viewed"),("downloaded","Downloaded"),("failed","Failed")]`, default="pending") —
        the sent→viewed→downloaded signal chain common across Keka/HROne/Zimyo
  - [ ] `sent_to_email` — EmailField(blank=True, editable=False) — snapshot of the employee's email at
        send time, so a later profile email change never rewrites delivery history
  - [ ] `sent_at` — DateTimeField(null=True, blank=True, editable=False)
  - [ ] `viewed_at` — DateTimeField(null=True, blank=True, editable=False)
  - [ ] `downloaded_at` — DateTimeField(null=True, blank=True, editable=False)
  - [ ] `sent_by` — `models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        blank=True, related_name="hrm_payslip_distribution_sends", editable=False)`
  - [ ] `class Meta`: `ordering = ["-payslip__cycle__pay_date"]`; index `models.Index(fields=["tenant",
        "status"], name="hrm_psd_tenant_status_idx")`
  - [ ] `classmethod for_payslip(cls, payslip)` — get-or-create helper (`status="pending"`,
        `delivery_channel="portal"` default), called lazily wherever a distribution row is needed
        (mirrors the "created lazily" convention noted in research; avoids a signal/post_save hook)
  - [ ] `__str__` → `f"{self.payslip} · {self.get_status_display()}"`

- [ ] `BankReconciliation(TenantNumbered, NUMBER_PREFIX="BRC")` — matches a batch's payments against an
      imported bank statement (drivers: NACH/ACH three-way-match convention, ADP's "Bank Reconciliation"
      standard report, RazorpayX's Payroll↔Current-Account reconciliation framing, greytHR's dedicated
      reconciliation report):
  - [ ] `batch` — `models.ForeignKey("hrm.PayoutBatch", on_delete=models.PROTECT,
        related_name="reconciliations")`
  - [ ] `statement_date` — DateField() — the bank statement's as-of date
  - [ ] `status` — CharField(max_length=15, choices=`[("pending","Pending"),
        ("in_progress","In Progress"),("reconciled","Reconciled"),("discrepancy","Discrepancy")]`,
        default="pending") — the reconciliation run's own lifecycle, distinct from each
        `PayoutPayment.status`
  - [ ] `matched_count` — PositiveIntegerField(default=0, editable=False)
  - [ ] `matched_amount` — DecimalField(max_digits=14, decimal_places=2, default=0, editable=False)
  - [ ] `unmatched_count` — PositiveIntegerField(default=0, editable=False)
  - [ ] `unmatched_amount` — DecimalField(max_digits=14, decimal_places=2, default=0, editable=False)
  - [ ] `statement_reference` — CharField(max_length=100, blank=True) — the bank's own statement/file
        reference number
  - [ ] `reconciled_by` — `models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="hrm_bank_reconciliations", editable=False)`
  - [ ] `reconciled_at` — DateTimeField(null=True, blank=True, editable=False)
  - [ ] `notes` — TextField(blank=True)
  - [ ] `class Meta`: `ordering = ["-statement_date"]`; index `models.Index(fields=["tenant", "batch"],
        name="hrm_brc_tenant_batch_idx")`, `models.Index(fields=["tenant", "status"],
        name="hrm_brc_tenant_status_idx")`
  - [ ] `recompute()` **method** — matches `self.batch.payments` by `transaction_reference` +
        `status`: rows with a non-blank `transaction_reference` AND `status="paid"` count as matched
        (`matched_count`/`matched_amount` = `Sum("net_amount")`); rows `status in ("failed",
        "returned")` OR blank `transaction_reference` while `status="processing"` count as unmatched
        (`unmatched_count`/`unmatched_amount`); sets `self.status = "reconciled"` if
        `unmatched_count == 0` else `"discrepancy"`; `self.reconciled_at = timezone.now()`;
        `self.save(update_fields=["matched_count", "matched_amount", "unmatched_count",
        "unmatched_amount", "status", "reconciled_at", "updated_at"])` — no `BankStatementLine` child
        table (per research recommendation — v1 matches directly against `PayoutPayment` rows)
  - [ ] `__str__` → `f"{self.number} · {self.batch.number} · {self.get_status_display()}"`

- [ ] one incremental migration `apps/hrm/migrations/0028_payoutbatch_payoutpayment_and_more.py` (NOT
      `0001_initial`; last is `0027_investmentdeclaration_investmentdeclarationline_and_more.py`) —
      `makemigrations hrm`, review the generated file, adjust index/constraint names to match the ones
      specified above if Django's auto-names differ

## B. Workflow + engine actions (views)

- [ ] `payoutbatch_generate` (`@tenant_admin_required`, `@require_POST`) — from a URL-supplied
      `cycle_pk`: `get_or_create`s (or fetches, if already exists per `unique_together`) the draft
      `PayoutBatch` for that cycle (validate `cycle.is_locked` first — 400/friendly error if not);
      only proceeds while `batch.status == "draft"` (mirrors `payrollcycle_generate`'s draft-only
      preserve-on-regenerate guard); for each `cycle.payslips.all()`: if `payslip.on_hold`,
      `get_or_create` a `PayoutPayment(status="on_hold", net_amount=payslip.net_pay,
      employee=payslip.employee)` (zero-action row per research note); else `update_or_create`
      (keyed on `(batch, payslip)`) a `PayoutPayment` snapshotting `net_amount=payslip.net_pay`,
      `bank_name_snapshot=employee.bank_name`, `bank_account_last4_snapshot=
      employee.masked_bank_account()`, `bank_routing_snapshot=employee.masked_bank_routing()`,
      `status="pending"` — regenerating preserves any payment already past `pending` (paid/failed/
      processing rows are left untouched, matching 3.14's manual-input-preservation-on-regenerate
      rule); set `batch.generated_by=request.user`, `generated_at=timezone.now()`;
      `write_audit_log(..., {"action": "generate", "headcount": batch.headcount})`
- [ ] `payoutbatch_approve` (`@tenant_admin_required`, `@require_POST`) — only from `status="draft"`;
      set `status="approved"`, `approved_by=request.user`, `approved_at=timezone.now()`;
      `write_audit_log(..., {"action": "approve"})`
- [ ] `payoutbatch_disburse` (`@tenant_admin_required`, `@require_POST`) — only from
      `status="approved"`; sets `initiated_at=timezone.now()` on every `pending`/`processing` payment
      in the batch (bulk `update()`), sets `batch.disbursed_at=timezone.now()`; derive
      `batch.status` from `batch._totals()`: if `failed_count == 0 and on_hold_count == headcount -
      paid_count` → `"disbursed"`, elif `paid_count > 0 and failed_count > 0` → `"partially_disbursed"`,
      else `"disbursed"` (simple rule: any `failed` present while some `paid`/`pending`→initiated →
      `partially_disbursed`; otherwise `disbursed`) — document this exact rule in the view docstring
      since it's the one piece of derived logic that isn't a straight aggregate; a real bank-file
      export is DEFERRED, this action marks the batch as sent; `write_audit_log(...,
      {"action": "disburse"})`
- [ ] `payoutpayment_mark_paid` (`@tenant_admin_required`, `@require_POST`) — only from `status in
      ("pending", "processing")`; requires `transaction_reference` from the POST body (small inline
      form, not a full ModelForm); sets `status="paid"`, `paid_on=timezone.now()`,
      `transaction_reference=<posted value>`; after save, recompute `batch.status` (call a shared
      `_recompute_batch_status(batch)` helper used by disburse/mark_paid/mark_failed alike, so the
      derivation rule lives in exactly one place); `write_audit_log(...)`
- [ ] `payoutpayment_mark_failed` (`@tenant_admin_required`, `@require_POST`) — only from `status in
      ("pending", "processing")`; requires `failure_reason` from the POST body; sets `status="failed"`,
      `failure_reason=<posted value>`; recompute `batch.status`; `write_audit_log(...)`
- [ ] `payoutpayment_retry` (`@tenant_admin_required`, `@require_POST`) — only from
      `status="failed"`; creates a NEW `PayoutPayment` row (same `batch`/`payslip`/`employee`,
      re-snapshotting the CURRENT `employee.bank_name`/`masked_bank_account()`/
      `masked_bank_routing()` in case the employee corrected their bank details — Zoho Payroll's
      "edit bank details then re-initiate" pattern), `status="pending"`, `retry_of=original` — but
      `unique_together (tenant, batch, payslip)` blocks a second row for the same payslip in the SAME
      batch, so **first flip the original failed row's status to a terminal non-blocking state** (do
      NOT delete it — instead: since the unique constraint is on `(batch, payslip)`, the retry must
      replace-in-place: set the ORIGINAL row back to `status="pending"` + bump
      `initiated_at=None`/clear `failure_reason`/set a NEW `transaction_reference=""`, and record the
      retry lineage via a NEW field-less approach — **resolve this in code**: either (a) relax the
      unique_together to `("tenant", "batch", "payslip", "retry_of")`-style so a retry row can coexist,
      or (b) treat "retry" as resetting the SAME row to pending and use `retry_of` to point at a
      soft-archived copy created via `PayoutPayment.objects.create(..., batch=None-not-allowed)` —
      **decision for the build step: relax `unique_together` to only apply when `retry_of__isnull=True`
      is not expressible in Django's plain `unique_together`, so implement instead as a `UniqueConstraint`
      with `condition=Q(retry_of__isnull=True)`** (`Meta.constraints`, not `unique_together`) so the
      original failed row keeps existing untouched (audit trail) and exactly one non-retry OR
      most-recent-retry row exists per payslip; recompute `batch.status`; `write_audit_log(...,
      {"action": "retry", "retry_of": original.pk})`
- [ ] `payslipdistribution_send` (`@tenant_admin_required`, `@require_POST`) — per-payslip (URL
      `payslip_pk`) or bulk-on-a-cycle (URL `cycle_pk`, iterate `cycle.payslips.all()`): for each,
      `PayslipDistribution.for_payslip(payslip)`, snapshot `sent_to_email` from the employee's email
      (check `EmployeeProfile`/`party` for the actual email field name before writing — confirm field
      name at build time), set `status="sent"`, `sent_at=timezone.now()`, `sent_by=request.user` —
      actual SMTP/PDF dispatch DEFERRED, this marks it sent; optional workflow guard (per research —
      Deel's payment-before-payslip pattern): if a `PayoutPayment` exists for this payslip and its
      `status != "paid"`, still ALLOW send but surface a `messages.warning` (v1 does not hard-block,
      documented as a soft business rule per the research note); `write_audit_log(...)`
- [ ] `payslipdistribution_mark_viewed` / `_mark_downloaded` (`@login_required`, `@require_POST`) —
      the employee-portal self-service signals: set `viewed_at`/`downloaded_at=timezone.now()` and
      bump `status` to `"viewed"`/`"downloaded"` only forward (never regress `downloaded`→`viewed`);
      no tenant-admin gate (any authenticated user viewing/downloading THEIR OWN payslip triggers
      this — verify `request.user`'s linked `EmployeeProfile` matches `distribution.payslip.employee`
      before allowing, 403 otherwise)
- [ ] `bankreconciliation_reconcile` (`@tenant_admin_required`, `@require_POST`) — calls
      `reconciliation.recompute()`; on the resulting `status == "reconciled"`, also flip
      `reconciliation.batch.status = "reconciled"` and save (only the batch-level flip, no cascading
      payment-status changes); sets `reconciled_by=request.user`,
      `reconciled_at=timezone.now()` (already set inside `recompute()` — don't double-set);
      `write_audit_log(...)`
- [ ] `payment_register` (`@login_required`) — **read/report view**, no new model: given a `batch_pk`,
      render headcount/total_amount/paid/failed/on_hold breakdown, a by-`payment_method` group-by
      table, a by-`status` group-by table, and the bank-advice-style row list (employee, masked
      account last-4, masked routing, amount, `transaction_reference`, status) — Payment Register
      (greytHR Bank Transfer Advice / HROne salary bank advice statement); render
      `hrm/payout/payment_register.html`
- [ ] `payout_exceptions` (`@login_required`) — **read/report view**, no new model: a filtered
      `PayoutPayment.objects.filter(tenant=request.tenant, status__in=["failed", "returned"])` list
      across ALL batches (optionally narrowed by a `?batch=` GET param), each row linking to its
      `payoutpayment_retry` action — Reconciliation / exception report (Zoho Payroll's failed-status
      filter feeding re-initiate); render `hrm/payout/exceptions.html`

## C. Forms (`apps/hrm/forms.py`)

- [ ] `PayoutBatchForm(TenantModelForm)`:
  - [ ] `Meta.fields = ["cycle", "bank_file_format", "source_bank_name", "source_account_last4",
        "notes"]` (exclude `tenant`/auto-number `number`/`status`/`generated_by`/`generated_at`/
        `approved_by`/`approved_at`/`disbursed_at` — workflow/derived)
  - [ ] custom `__init__` narrows `cycle` to `PayrollCycle.objects.filter(tenant=tenant,
        status="locked")` — a draft/pending/approved/rejected cycle must never appear in the picker
        (Bank Integration — "generated from a locked cycle" rule enforced at the form layer, not just
        `clean()`)
- [ ] `BankReconciliationForm(TenantModelForm)`:
  - [ ] `Meta.fields = ["batch", "statement_date", "statement_reference", "notes"]` (exclude
        `tenant`/auto-number `number`/`status`/`matched_*`/`unmatched_*`/`reconciled_by`/
        `reconciled_at` — all derived by `recompute()`)
  - [ ] custom `__init__` narrows `batch` to `PayoutBatch.objects.filter(tenant=tenant)`
- [ ] `PayslipDistributionForm(TenantModelForm)` — **only needed if a standalone edit view is added**
      (v1's `send`/`mark_viewed`/`mark_downloaded` are POST-only actions, not a form-backed edit); if
      built, `Meta.fields = ["delivery_channel"]` (exclude everything else — workflow-owned); confirm
      at build time whether a manual override edit is actually needed or whether the list+actions
      pattern alone suffices (lean toward NOT building this form — document the decision either way)

## D. Views (`apps/hrm/views.py`) — full CRUD + filters via `crud_*`

- [ ] `payoutbatch_list` — `crud_list(request, PayoutBatch.objects.filter(
      tenant=request.tenant).select_related("cycle"), "hrm/payout/payoutbatch/list.html",
      search_fields=["number", "cycle__number"], filters=[("status", "status", False),
      ("bank_file_format", "bank_file_format", False), ("cycle", "cycle_id", True)],
      extra_context={"status_choices": PayoutBatch._meta.get_field("status").choices,
      "bank_file_format_choices": PayoutBatch._meta.get_field("bank_file_format").choices, "cycles":
      PayrollCycle.objects.filter(tenant=request.tenant, status="locked")})`
- [ ] `payoutbatch_create` / `_edit` / `_delete` — standard `crud_create`/`crud_edit`/`crud_delete`
      wrappers; `_edit`/`_delete` only while `status == "draft"` (mirror `payrollcycle_edit`/`_delete`'s
      draft-only guard); `_delete` blocked (PROTECT) if any `BankReconciliation` references the batch —
      catch and surface a friendly `messages.error`, not a 500
- [ ] `payoutbatch_detail` — `crud_detail(...)`; extra_context adds `"payments":
      obj.payments.select_related("employee__party").order_by("employee__party__name")` (inline-managed
      list) + action buttons (`Generate`/`Approve`/`Disburse` — status-gated) + a link to
      `payment_register` and `reconciliations` — also the entry point for
      `payoutpayment_mark_paid`/`_mark_failed`/`_retry` (URL-scoped under this batch's payments) and
      `bankreconciliation_create` (pre-filled `batch`)
- [ ] `payoutbatch_generate` / `_approve` / `_disburse` — per Section B spec
- [ ] `payoutpayment_mark_paid` / `_mark_failed` / `_retry` — per Section B spec; all redirect back to
      `payoutbatch_detail`
- [ ] `payslipdistribution_list` — `crud_list(request, PayslipDistribution.objects.filter(
      tenant=request.tenant).select_related("payslip__employee__party", "payslip__cycle"),
      "hrm/payout/payslipdistribution/list.html", search_fields=["payslip__number",
      "payslip__employee__party__name"], filters=[("status", "status", False), ("delivery_channel",
      "delivery_channel", False), ("cycle", "payslip__cycle_id", True)], extra_context={
      "status_choices": PayslipDistribution._meta.get_field("status").choices,
      "delivery_channel_choices": PayslipDistribution._meta.get_field("delivery_channel").choices,
      "cycles": PayrollCycle.objects.filter(tenant=request.tenant)})` — no create/edit/delete views
      (rows are lazily get-or-created via `for_payslip()`, matching `EmployeeDocument`'s
      no-generic-edit-on-a-tracked-artifact pattern)
- [ ] `payslipdistribution_detail` — `crud_detail(...)`; action buttons (`Send`, tenant-admin,
      POST+confirm+csrf, gated `status == "pending"`)
- [ ] `payslipdistribution_send` / `_mark_viewed` / `_mark_downloaded` — per Section B spec
- [ ] `bankreconciliation_list` — `crud_list(request, BankReconciliation.objects.filter(
      tenant=request.tenant).select_related("batch__cycle"), "hrm/payout/bankreconciliation/list.html",
      search_fields=["number", "batch__number", "statement_reference"], filters=[("status", "status",
      False), ("batch", "batch_id", True)], extra_context={"status_choices":
      BankReconciliation._meta.get_field("status").choices, "batches": PayoutBatch.objects.filter(
      tenant=request.tenant)})`
- [ ] `bankreconciliation_create` / `_edit` / `_delete` — standard wrappers; `_edit`/`_delete` only
      while `status in ("pending", "in_progress")` (not yet reconciled/discrepancy-closed)
- [ ] `bankreconciliation_detail` — `crud_detail(...)`; extra_context adds the matched/unmatched
      breakdown + the batch's exception payments (`status__in=["failed","returned"]`) for quick
      follow-up; action button (`Reconcile`, tenant-admin, POST+confirm+csrf)
- [ ] `bankreconciliation_reconcile` — per Section B spec
- [ ] `payment_register` / `payout_exceptions` — per Section B spec
- [ ] all new views import the 4 new models + their forms at the top of `views.py`; `Sum`/`Count`/`Q`
      from `django.db.models` (already imported for 3.14/3.15/3.16 — confirm, don't re-import);
      `timezone` from `django.utils`

## E. URLs (`apps/hrm/urls.py`, `app_name = "hrm"` already set)

- [ ] `path("payout-batches/", views.payoutbatch_list, name="payoutbatch_list")`
- [ ] `path("payout-batches/add/", views.payoutbatch_create, name="payoutbatch_create")`
- [ ] `path("payout-batches/<int:pk>/", views.payoutbatch_detail, name="payoutbatch_detail")`
- [ ] `path("payout-batches/<int:pk>/edit/", views.payoutbatch_edit, name="payoutbatch_edit")`
- [ ] `path("payout-batches/<int:pk>/delete/", views.payoutbatch_delete, name="payoutbatch_delete")`
- [ ] `path("payout-batches/<int:pk>/generate/", views.payoutbatch_generate, name="payoutbatch_generate")`
- [ ] `path("payout-batches/<int:pk>/approve/", views.payoutbatch_approve, name="payoutbatch_approve")`
- [ ] `path("payout-batches/<int:pk>/disburse/", views.payoutbatch_disburse, name="payoutbatch_disburse")`
- [ ] `path("payout-batches/<int:pk>/payment-register/", views.payment_register, name="payment_register")`
- [ ] `path("payout-payments/<int:pk>/mark-paid/", views.payoutpayment_mark_paid, name="payoutpayment_mark_paid")`
- [ ] `path("payout-payments/<int:pk>/mark-failed/", views.payoutpayment_mark_failed, name="payoutpayment_mark_failed")`
- [ ] `path("payout-payments/<int:pk>/retry/", views.payoutpayment_retry, name="payoutpayment_retry")`
- [ ] `path("payout-exceptions/", views.payout_exceptions, name="payout_exceptions")`
- [ ] `path("payslip-distributions/", views.payslipdistribution_list, name="payslipdistribution_list")`
- [ ] `path("payslip-distributions/<int:pk>/", views.payslipdistribution_detail, name="payslipdistribution_detail")`
- [ ] `path("payslips/<int:payslip_pk>/distribution/send/", views.payslipdistribution_send, name="payslipdistribution_send")`
- [ ] `path("payroll-cycles/<int:cycle_pk>/distributions/send-bulk/", views.payslipdistribution_send, name="payslipdistribution_send_bulk")`
- [ ] `path("payslip-distributions/<int:pk>/mark-viewed/", views.payslipdistribution_mark_viewed, name="payslipdistribution_mark_viewed")`
- [ ] `path("payslip-distributions/<int:pk>/mark-downloaded/", views.payslipdistribution_mark_downloaded, name="payslipdistribution_mark_downloaded")`
- [ ] `path("bank-reconciliations/", views.bankreconciliation_list, name="bankreconciliation_list")`
- [ ] `path("bank-reconciliations/add/", views.bankreconciliation_create, name="bankreconciliation_create")`
- [ ] `path("bank-reconciliations/<int:pk>/", views.bankreconciliation_detail, name="bankreconciliation_detail")`
- [ ] `path("bank-reconciliations/<int:pk>/edit/", views.bankreconciliation_edit, name="bankreconciliation_edit")`
- [ ] `path("bank-reconciliations/<int:pk>/delete/", views.bankreconciliation_delete, name="bankreconciliation_delete")`
- [ ] `path("bank-reconciliations/<int:pk>/reconcile/", views.bankreconciliation_reconcile, name="bankreconciliation_reconcile")`

## F. Admin (`apps/hrm/admin.py`)

- [ ] register `PayoutBatch` — `list_display = ("number", "cycle", "status", "bank_file_format",
      "headcount", "total_amount")`, `list_filter = ("tenant", "status", "bank_file_format")`,
      `search_fields = ("number", "cycle__number")`
- [ ] register `PayoutPayment` as a `TabularInline` on `PayoutBatchAdmin` (`model = PayoutPayment`,
      `extra = 0`, `fields = ("employee", "net_amount", "payment_method", "status",
      "transaction_reference")`, `readonly_fields = ("net_amount",)`) — also register standalone with
      `list_display = ("batch", "employee", "net_amount", "payment_method", "status", "paid_on")`,
      `list_filter = ("tenant", "status", "payment_method")`, `search_fields = ("employee__party__name",
      "transaction_reference")`
- [ ] register `PayslipDistribution` — `list_display = ("payslip", "delivery_channel", "status",
      "sent_at", "viewed_at", "downloaded_at")`, `list_filter = ("tenant", "delivery_channel",
      "status")`, `search_fields = ("payslip__number", "sent_to_email")`
- [ ] register `BankReconciliation` — `list_display = ("number", "batch", "statement_date", "status",
      "matched_count", "unmatched_count")`, `list_filter = ("tenant", "status")`, `search_fields =
      ("number", "batch__number", "statement_reference")`

## G. Templates (`templates/hrm/payout/<entity>/<page>.html`)

- [ ] `payout/payoutbatch/list.html` — filter bar: search `q`, `status` select (from
      `status_choices`), `bank_file_format` select, `cycle` select (from `cycles`,
      `|stringformat:"d"` pk-compare); columns: number, cycle, status badge (`draft`→`badge-muted`,
      `approved`→`badge-info`, `disbursed`→`badge-green`, `partially_disbursed`→`badge-amber`,
      `reconciled`→`badge-slate`), bank_file_format, headcount, total_amount, Actions
      (view/edit-if-draft/delete-if-draft); pagination; empty-state; `{% else %}
      {{ obj.get_status_display }}` fallback
- [ ] `payout/payoutbatch/detail.html` — header (cycle link, status badge, bank_file_format,
      source_bank_name/source_account_last4, generated_by/at, approved_by/at, disbursed_at); workflow
      buttons (`Generate` — draft only, POST+confirm+csrf; `Approve` — draft-with-payments only,
      tenant-admin; `Disburse` — approved only, tenant-admin); **payments table** (employee, net_amount,
      payment_method, status badge [`pending`→`badge-muted`, `processing`→`badge-info`, `paid`→
      `badge-green`, `failed`→`badge-red`, `returned`→`badge-amber`, `on_hold`→`badge-slate`],
      transaction_reference, initiated_at/paid_on) with per-row `Mark Paid`/`Mark Failed`/`Retry`
      buttons (tenant-admin, POST+confirm+csrf, status-gated); links to `payment_register` and
      `bankreconciliation_create` (pre-filled batch); Actions sidebar (Edit-if-draft/Delete-if-draft,
      Back to List)
- [ ] `payout/payoutbatch/form.html` — standard form
- [ ] `payout/payment_register.html` — **standalone report page** (Template Folder Structure rule 6):
      batch header + headcount/total_amount/paid/failed/on_hold summary cards, by-payment_method
      group-by table, by-status group-by table, bank-advice-style row list (employee, masked account
      last-4, masked routing, amount, transaction_reference, status) — masked accounts only, never the
      full number; a print/export-friendly layout note
- [ ] `payout/exceptions.html` — **standalone report page**: filtered failed/returned `PayoutPayment`
      list across all batches (optional `?batch=` narrowing), each row showing employee, batch link,
      net_amount, failure_reason, a `Retry` action button (tenant-admin, POST+confirm+csrf);
      empty-state when no exceptions exist
- [ ] `payout/payslipdistribution/list.html` — filter bar: search `q`, `status` select, `delivery_channel`
      select, `cycle` select (from `cycles`, pk-compare); columns: payslip (→employee), cycle,
      delivery_channel, status badge (`pending`→`badge-muted`, `sent`→`badge-info`, `viewed`→
      `badge-amber`, `downloaded`→`badge-green`, `failed`→`badge-red`), sent_at, viewed_at,
      downloaded_at, Actions (view); pagination; empty-state
- [ ] `payout/payslipdistribution/detail.html` — header (payslip link, employee, delivery_channel,
      status badge, sent_to_email, sent_at/viewed_at/downloaded_at, sent_by); Actions sidebar (`Send`
      — tenant-admin, POST+confirm+csrf, pending only; Back to List)
- [ ] `payout/bankreconciliation/list.html` — filter bar: search `q`, `status` select, `batch` select
      (from `batches`, pk-compare); columns: number, batch, statement_date, status badge (`pending`→
      `badge-muted`, `in_progress`→`badge-info`, `reconciled`→`badge-green`, `discrepancy`→
      `badge-red`), matched_count/unmatched_count, Actions (view/edit-if-not-reconciled/
      delete-if-not-reconciled); pagination; empty-state
- [ ] `payout/bankreconciliation/detail.html` — header (batch link, statement_date, status badge,
      statement_reference, reconciled_by/at); matched/unmatched summary panel
      (matched_count/matched_amount, unmatched_count/unmatched_amount); the batch's exception payments
      table (failed/returned rows) for follow-up; action button (`Reconcile`, tenant-admin,
      POST+confirm+csrf); Actions sidebar (Edit-if-not-reconciled/Delete-if-not-reconciled, Back to List)
- [ ] `payout/bankreconciliation/form.html` — standard form

## H. Seeder (`apps/hrm/management/commands/seed_hrm.py`)

- [ ] add `_seed_payout(self, tenant, *, flush)` method, called from `handle()` **AFTER**
      `self._seed_tax(tenant, flush=options["flush"])` (last method in the current chain — confirm the
      exact call order at build time; payout needs a LOCKED `PayrollCycle` with `Payslip`s already
      generated by `_seed_payroll`)
- [ ] `if flush:` child-first wipe: `BankReconciliation.objects.filter(tenant=tenant).delete()` →
      `PayoutPayment.objects.filter(tenant=tenant).delete()` →
      `PayslipDistribution.objects.filter(tenant=tenant).delete()` →
      `PayoutBatch.objects.filter(tenant=tenant).delete()`
- [ ] `if PayoutBatch.objects.filter(tenant=tenant).exists(): self.stdout.write(self.style.NOTICE(
      f"Payout & Reports data already exists for '{tenant.name}'. Use --flush to re-seed.")); return`
- [ ] **critical precondition** — the `PayrollCycle` seeded by `_seed_payroll` (3.14) is left in
      `status="draft"` at the end of that method (confirm this at build time by reading
      `_seed_payroll`'s last lines). A `PayoutBatch` requires `cycle.is_locked`. Resolve by ONE of:
      (a) locking the SAME seeded cycle in `_seed_payout` (fetch it, set
      `status="locked"`/`approved_by`/`approved_at`/`submitted_by`/`submitted_at` if not already set,
      save) — **preferred**, reuses existing demo data and demonstrates the real lock→payout flow
      end-to-end; or (b) creating a second, dedicated locked demo `PayrollCycle` + its `Payslip`s if
      locking the shared seeded cycle would break an assumption in 3.14/3.15/3.16's own idempotency
      checks (verify no other seeder step depends on that cycle staying in `draft`/`approved` before
      committing to (a)) — **decide and document the choice in the method's docstring**
- [ ] once a locked cycle is available: create 1 `PayoutBatch` (`bank_file_format="neft"`,
      `source_bank_name="HDFC Bank"`, `source_account_last4="4321"`, `status="draft"`) via the same
      logic `payoutbatch_generate` uses (call the view's underlying helper directly, or replicate the
      snapshot-per-payslip loop inline — prefer calling a shared non-view helper function if one is
      extracted, to avoid duplicating the snapshot logic between the seeder and the view)
  - [ ] `generated_by`/`generated_at` set to a seeded tenant-admin user / now
  - [ ] approve the batch (`status="approved"`, `approved_by`/`approved_at` set)
  - [ ] mark most payments `status="paid"` with a `transaction_reference` (e.g.
        `f"UTR{i:08d}"`) and `paid_on=timezone.now()`; mark exactly ONE payment `status="failed"` with
        a `failure_reason="Incorrect bank account number"` (demonstrating the exception-report path);
        any on-hold payslip's payment stays `status="on_hold"`
  - [ ] set `batch.status = "partially_disbursed"` (since one payment failed) and
        `batch.disbursed_at=timezone.now()`
- [ ] for every `Payslip` in that cycle: `PayslipDistribution.for_payslip(payslip)`, then mark most
      `status="sent"` (`sent_at`, `sent_by`) and one `status="viewed"` (`viewed_at` also set) to show
      the signal progression
- [ ] create 1 `BankReconciliation` (`statement_date=` a plausible date, `statement_reference=
      "STMT-2026-06-30"`), call `.recompute()` (will land on `status="discrepancy"` given the one
      failed payment) — demonstrating the non-trivial reconciliation outcome, not just the happy path
- [ ] print a summary line: `f"Payout & Reports seeded for '{tenant.name}': 1 batch
      ({batch.number}, {batch.get_status_display()}), {batch.headcount} payments
      ({batch.paid_count} paid / {batch.failed_count} failed), {distributions_sent} distributions
      sent, 1 reconciliation ({recon.number} → {recon.get_status_display()})."`
- [ ] confirm the seeder still prints the tenant-admin login reminder + "Data already exists" warning
      path unchanged — the new block is itself idempotent, no new top-level guard needed

## I. Navigation (`apps/core/navigation.py`)

- [ ] add `LIVE_LINKS["3.17"]` (verify the exact query-string/routing convention against 3.14/3.15/
      3.16's existing entries before finalizing):
      ```python
      # 3.17 Payout & Reports — PayoutBatch serves Bank Integration; PayslipDistribution serves
      # Payslip Generation; the payment_register report (linked from a batch detail) serves Payment
      # Register; BankReconciliation serves Reconciliation.
      "3.17": {
          "Bank Integration": "hrm:payoutbatch_list",                 # bullet
          "Payslip Generation": "hrm:payslipdistribution_list",       # bullet
          "Payment Register": "hrm:payoutbatch_list",                 # bullet (detail links to payment_register)
          "Reconciliation": "hrm:bankreconciliation_list",            # bullet
      },
      ```
      — all 4 NavERP.md 3.17 bullets go Live; "Payment Register" deliberately routes through the batch
      list (no standalone Payment-Register-model per the "report, not a model" research decision) —
      document this routing rationale in the navigation.py comment, mirroring 3.16's
      Form-16-routes-to-computation-list precedent

## J. Migrate / seed / verify (run from the venv)

- [ ] `python manage.py makemigrations hrm` → review `0028_...py` (field/index/unique_together/
      constraint names match the plan; confirm the `UniqueConstraint(condition=Q(...))` for
      `PayoutPayment` — if the retry design in Section B lands on this approach — is generated
      correctly and doesn't collide with the plain FK-by-string chains)
- [ ] `python manage.py migrate`
- [ ] `python manage.py seed_hrm` (1st run — creates data; confirm `_seed_tax` still runs first and
      the new `_seed_payout` block correctly locks/reuses the seeded `PayrollCycle` and generates its
      batch/payments/distributions/reconciliation against it)
- [ ] `python manage.py seed_hrm` (2nd run — must be idempotent, no duplicates, no errors)
- [ ] `python manage.py check`
- [ ] `temp/` smoke sweep: every new `hrm:payoutbatch_*`, `hrm:payoutpayment_*`,
      `hrm:payslipdistribution_*`, `hrm:bankreconciliation_*`, `hrm:payment_register`, and
      `hrm:payout_exceptions` URL returns 200/302 when logged in as a tenant admin; no `{#`/
      `{% comment` leaks in the new templates; cross-tenant IDOR check — a `PayoutBatch`/
      `PayoutPayment`/`PayslipDistribution`/`BankReconciliation` pk belonging to tenant A returns 404
      when fetched as tenant B; `payoutbatch_generate` run twice while draft produces the same
      headcount/no duplicate `PayoutPayment` rows (idempotent regenerate, preserves past-pending rows);
      `payoutbatch_generate` blocked (400/friendly error, not 500) against an unlocked cycle;
      `payoutpayment_retry` on a failed payment creates exactly one new row without violating the
      unique constraint; `bankreconciliation_reconcile` run twice produces the same matched/unmatched
      aggregates (idempotent recompute); the seeded batch's `partially_disbursed` status and the
      seeded reconciliation's `discrepancy` status are visible on their respective detail pages;
      masked account/routing values render as `••••1234` (never the full number) on
      `payoutbatch_detail`/`payment_register`; `payslipdistribution_mark_viewed`/`_mark_downloaded`
      403s for a user whose linked `EmployeeProfile` doesn't match the payslip's employee;
      `payout_exceptions` surfaces exactly the seeded failed payment
- [ ] sidebar: confirm 3.17 shows all four bullets as **Live** (not "Coming soon") for a tenant with
      data

## K. Close-out

- [ ] update `README.md` module-status / HRM section (3.17 bullets: Bank Integration / Payslip
      Generation / Payment Register / Reconciliation all live; bump the HRM + project-wide test-count
      lines once test-writer runs)
- [ ] run the review-agent sequence in order, each ending in its own commit(s): `code-reviewer` →
      `explorer` → `frontend-reviewer` → `performance-reviewer` → `qa-smoke-tester` →
      `security-reviewer` → `test-writer`
- [ ] create/update `.claude/skills/hrm/SKILL.md` — 3.17 section: document `PayoutBatch`/
      `PayoutPayment`/`PayslipDistribution`/`BankReconciliation` models, the
      generate→approve→disburse workflow + mark_paid/mark_failed/retry payment actions, the
      send/mark_viewed/mark_downloaded distribution signals, the `recompute()` reconciliation-match
      contract (transaction_reference + status, no `BankStatementLine`), the new
      `LIVE_LINKS["3.17"]` entries (incl. the Payment-Register-routes-to-batch-list rationale), the
      extended seeder block, the masked-snapshot convention (never store/render the raw account), and
      mark all 4 bullets of 3.17 as built

## Review — 3.17 Payout & Reports (built 2026-07-05)

**Shipped (4 tables, all wired Live, migrations `0028`+`0029`).** `PayoutBatch` (`POB-`, from a locked `PayrollCycle`,
draft→approved→disbursed/partially_disbursed→reconciled, cached `_totals()` over `_current_payments()`),
`PayoutPayment` (per-employee, **masked** bank snapshot — never raw, status lifecycle + `retry_of` supersede chain, no
`unique_together` so retries coexist), `PayslipDistribution` (1:1, send/view/download, `for_payslip()`),
`BankReconciliation` (`BRC-`, `recompute()` matches by UTR+paid → reconciled/discrepancy, no `BankStatementLine`).
Reports (no model): `payment_register` (bank-advice) + `payout_exceptions`. Reuses `PayrollCycle`/`Payslip`/
`EmployeeProfile`; **posts no GL** (L29). `LIVE_LINKS["3.17"]` — all 4 bullets Live. `_seed_payout` after `_seed_tax`
(locks the demo cycle, POB-00001 partially_disbursed 1 paid/1 failed/1 on-hold, BRC-00001 discrepancy 1 matched/2
unmatched).

**Verification.** `manage.py check` clean; no pending migrations; seeder idempotent; smoke sweep 200/302/405 on all
routes, no leaks, cross-tenant IDOR→404; retry supersede verified (failed original excluded → batch re-derives).

**Review agents (all run in order; findings applied + committed):**
- code-reviewer — **1 Important fixed**: `PayoutBatchForm.clean()` + dropdown-exclusion close the duplicate-batch
  IntegrityError-500. + 2 Minor (atomic wraps on mark_*/retry, register `get_*_display` labels).
- explorer — no wiring bugs; confirmed no raw bank + zero accounting refs.
- frontend-reviewer — aria-labels + flex-wrap on the per-payment inline forms, `.text-right` utility.
- performance-reviewer — **payoutbatch_list N+1 → O(1)** (annotated list_headcount/list_total/list_paid; verified flat
  query count across batch count); dropped dead select_related ×2; atomic-wrapped the bulk send_cycle.
- qa-smoke-tester — all green, no bugs.
- security-reviewer — all PASS (masked-bank confirmed); 1 Low fixed: `source_account_last4` RegexValidator (no full
  account); kept `mark_viewed`/`_downloaded` `@login_required` (discloses no data) with a tracking SECURITY NOTE.
- test-writer — **160 tests** (38 model / 65 view / 57 security), all pass; HRM suite 2,640→**2,800**, project-wide
  5,287→**5,447**. **No product bug found** this run — every invariant behaved as documented.

**Next:** 3.18 Goal Setting.

## Later passes / deferred (carried over from research-payout-reports.md — do not build this pass)

- **Bank-specific file-format writers** (exact NEFT/NACH/ACH/WPS-SIF CSV/fixed-width layouts per bank/
  country) — this pass stores the batch + payment rows needed to generate them, not the format writer.
- **Live bank-API integration for payment initiation** (RazorpayX Current Account, Keka's direct-bank-
  integration option) — external API integration; `PayoutPayment.status` transitions are
  admin/manual actions in v1, wireable to a live API callback later without a schema change.
- **Bank-account prenote / multi-day verification workflow** (ADP prenote, Zoho Payroll's 2–3-day
  re-verification after an account edit) — structurally could become a `pending_verification` status
  value; not built as its own workflow in v1.
- **Payslip PDF rendering + secure/password-protected delivery** — consistent with the deferral
  already noted in 3.14/3.15/3.16; `PayslipDistribution` tracks the send/view/download SIGNAL, not
  the document itself.
- **Live bank-statement feed / API-based auto-reconciliation** — v1 assumes a manual/CSV-driven
  statement import matched against `PayoutPayment.transaction_reference`; a live feed is
  integration/later.
- **A dedicated `BankStatementLine` persistence model** — considered and explicitly NOT added in this
  pass to keep the build at 4 models; revisit if raw-statement audit retention becomes a hard
  requirement.
- **Period-over-period payroll-cost anomaly/discrepancy detection** (greytHR's Payroll Reconciliation
  month-over-month compare) — buildable as a query across two periods without a new model; the
  anomaly-flagging logic itself is a nice-to-have, not core v1.
- **WPS/country-specific mandatory formats beyond India** (UAE SIF, other GCC wage-protection
  systems) — out of scope for this India-centric pass; `PayoutBatch.bank_file_format` choices leave
  room to extend later.
- **Form 16 / annual tax-document distribution tracking** — 3.16's `StatutoryReturn`
  (scheme=`tds_form16`) already tracks that document's filing workflow; extending the
  `PayslipDistribution`-style send/view/download pattern to it is a natural future enhancement.
- **Automatic re-initiation / retry scheduling** (auto-retry a failed payment after N days) — v1
  supports a manual retry via `PayoutPayment.retry_of`; an automated retry scheduler is a
  fast-follow, not blocking.

## Review notes
(filled in at the end)
