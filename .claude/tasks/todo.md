---
# HRM 3.12 Holiday Management — COMPLETION pass (Floating Holidays + Holiday Policies)  (2026-07-04)

**Context.** `PublicHoliday` (Holiday Calendar bullet) already exists with full CRUD, seeded, wired into
`LIVE_LINKS["3.12"]["Holiday Calendar"]`. Plan from `.claude/tasks/research-holiday.md`. This pass closes the two
remaining NavERP.md 3.12 bullets — **Floating Holidays** and **Holiday Policies** — by enriching `PublicHoliday`
with one field and adding two new `TenantOwned` models. Extending `apps/hrm` — NOT a new app. No new spine
masters; every FK points at `hrm.EmployeeProfile`, `hrm.Designation`, `core.OrgUnit`, or `accounts` User.

## A. Models + migration

- [ ] `PublicHoliday` — enrich (existing model, `apps/hrm/models.py` ~L753):
  - [ ] add `category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="national")` with
        `CATEGORY_CHOICES = [("national","National"),("regional","Regional"),("company","Company"),
        ("observance","Observance")]` — driver: Zoho People national/optional/special classification +
        Workday's regional-holiday distinction (research L60-63). Keep `is_optional` as-is (the floating switch —
        do not rename).
  - [ ] no other field changes; `date`/`name`/`is_optional`/`unique_together`/ordering/indexes stay as-is.

- [ ] `HolidayPolicy(TenantOwned)` [`apps/hrm/models.py`, new class near `PublicHoliday`] — no number prefix
      (`TenantOwned`, mirrors `PublicHoliday`/`Shift`), justified by Personio calendar-per-office, greytHR
      Location/Designation filters, Darwinbox/factoHR max-cap, SAP SuccessFactors default+most-specific-match
      (research L145-163):
  - [ ] `name` — CharField(max_length=150) — e.g. "Head Office — Full Time"
  - [ ] `location` — CharField(max_length=255, blank=True) — matched against `EmployeeProfile.work_location`
        (free-text contains-match, driver: greytHR Location column / Personio calendar-per-office)
  - [ ] `org_unit` — FK `core.OrgUnit`, `on_delete=models.SET_NULL`, `null=True, blank=True`,
        `related_name="holiday_policies"` — driver: greytHR/Workday department-level scoping
  - [ ] `employee_type` — CharField(max_length=20, blank=True, choices=`EmployeeProfile.EMPLOYEE_TYPE_CHOICES`)
        — driver: Keka/factoHR holiday-plan-per-employee-group (constrained to the existing enum, no new master)
  - [ ] `designation` — FK `hrm.Designation`, `on_delete=models.SET_NULL`, `null=True, blank=True`,
        `related_name="holiday_policies"` — driver: greytHR Designation column
  - [ ] `is_default` — BooleanField(default=False) — the fallback when nothing more specific matches (driver:
        Personio company-level default, SAP SuccessFactors)
  - [ ] `floating_holiday_quota` — PositiveSmallIntegerField(default=0) — "choose up to N" cap (driver:
        Darwinbox max-selection cap, factoHR "maximum of 2", HiBob "typical starting point is two")
  - [ ] `holidays` — ManyToManyField(`hrm.PublicHoliday`, blank=True, related_name="policies") — optional
        narrowing of which tenant holidays this policy's optional-holiday pool draws from; empty = all tenant
        `is_optional=True` holidays eligible (driver: greytHR per-holiday Location cell / Zoho single-list
        classification — join table, not a duplicated calendar)
  - [ ] `is_active` — BooleanField(default=True)
  - [ ] `description` — TextField(blank=True)
  - [ ] `class Meta`: `ordering = ["-is_default", "name"]`; `unique_together = ("tenant", "name")`; add an index
        `models.Index(fields=["tenant", "is_default"], name="hrm_hpol_tenant_default_idx")`
  - [ ] `for_employee(cls, profile)` classmethod resolver — queries `HolidayPolicy.objects.filter(tenant_id=
        profile.tenant_id, is_active=True)`, scores each candidate (org_unit match, designation match,
        employee_type match, location match — each contributes to specificity; a field left blank on the policy
        is a wildcard/skip, not a mismatch), returns the highest-scoring non-default match, else the row with
        `is_default=True`, else `None`. Reuses `EmployeeProfile.department` (org_unit) already on the profile.
  - [ ] `__str__` → `self.name`

- [ ] `FloatingHolidayElection(TenantOwned)` [new class] — no number prefix (`TenantOwned`), justified by Keka
      floater-leave application + approval, Darwinbox/factoHR cap enforcement, general approval-workflow pattern
      (research L165-181):
  - [ ] `employee` — FK `hrm.EmployeeProfile`, `on_delete=models.CASCADE`, `related_name="floating_holiday_elections"`
  - [ ] `holiday` — FK `hrm.PublicHoliday`, `on_delete=models.CASCADE`, `related_name="floating_elections"` —
        must have `is_optional=True` (enforced in form `__init__` queryset + model `clean()`)
  - [ ] `policy` — FK `HolidayPolicy`, `on_delete=models.SET_NULL`, `null=True, blank=True`,
        `related_name="elections"` — auto-resolved via `HolidayPolicy.for_employee(self.employee)` in `save()`
        when not already set
  - [ ] `status` — CharField(max_length=20, choices=`STATUS_CHOICES`, default="pending") with
        `STATUS_CHOICES = [("pending","Pending"),("approved","Approved"),("rejected","Rejected")]`
        (mirrors `LeaveRequest`/`Timesheet` shape, minus draft/cancelled — an election is submitted at creation)
  - [ ] `requested_on` — DateField(default=`django.utils.timezone.localdate`) (NOT `auto_now_add`, so the
        seeder/tests can backdate if ever needed — same idiom as other HRM date-default fields; if
        `auto_now_add=True` is simpler and matches `LeaveEncashment`'s `year` style, either is acceptable — pick
        `default=timezone.localdate` so the field stays editable pre-save via `clean()`re-checks)
  - [ ] `approved_by` — FK `settings.AUTH_USER_MODEL`, `on_delete=models.SET_NULL`, `null=True, blank=True`,
        `related_name="hrm_floating_holiday_approvals"` — system-set only (workflow view), never a form field
  - [ ] `approved_at` — DateTimeField(null=True, blank=True) — system-set only
  - [ ] `note` — TextField(blank=True) — light-touch reason/occasion field (research L91-93: free text is
        sufficient, no controlled taxonomy this pass)
  - [ ] `class Meta`: `ordering = ["-requested_on"]`; `unique_together = ("tenant", "employee", "holiday")` — an
        employee can't double-elect the same holiday; indexes:
        `models.Index(fields=["tenant","employee","status"], name="hrm_fhe_tenant_emp_status_idx")`,
        `models.Index(fields=["tenant","status"], name="hrm_fhe_tenant_status_idx")`
  - [ ] `clean()`:
    - [ ] reject if `self.holiday_id` and `self.holiday` is not `is_optional=True` →
          `ValidationError({"holiday": "Only optional (floating) holidays can be elected."})`
    - [ ] resolve `policy = self.policy or HolidayPolicy.for_employee(self.employee)` (don't mutate `self.policy`
          in `clean()` — only for the quota check) when `self.employee_id` and `self.holiday_id`
    - [ ] quota check: if a policy resolves and `policy.floating_holiday_quota` is set, count this employee's
          existing `pending`/`approved` elections (excluding `self.pk`) whose `holiday.date.year ==
          self.holiday.date.year` and whose resolved policy == this policy; if `count + 1 >
          floating_holiday_quota` → `ValidationError({"holiday": f"Quota exceeded — this policy allows
          {quota} floating holiday(s) per year."})`
  - [ ] `save()`: if `self.policy_id` is None and `self.employee_id`, set
        `self.policy = HolidayPolicy.for_employee(self.employee)` before calling `super().save()` (auto-resolve,
        per research L169-170)
  - [ ] `__str__` → `f"{self.employee} · {self.holiday} · {self.status}"`

- [ ] one incremental migration `apps/hrm/migrations/0023_publicholiday_category_holidaypolicy_and_more.py`
      (NOT `0001_initial`) — `makemigrations hrm`, review the generated file, adjust index/constraint names to
      match the ones specified above if Django's auto-names differ.

## B. Forms (`apps/hrm/forms.py`)

- [ ] `PublicHolidayForm(TenantModelForm)` — add `"category"` to `Meta.fields`: `["date", "name", "is_optional",
      "category"]` (was `["date", "name", "is_optional"]`).
- [ ] `HolidayPolicyForm(TenantModelForm)`:
  - [ ] `Meta.fields = ["name", "location", "org_unit", "employee_type", "designation", "is_default",
        "floating_holiday_quota", "holidays", "is_active", "description"]`
  - [ ] `__init__`: narrow `holidays` queryset to `PublicHoliday.objects.filter(tenant=self.tenant,
        is_optional=True)` (only optional holidays are electable, so only they belong in a policy's pool) —
        mirror the `LeaveEncashmentForm.__init__` narrowing idiom (guard with `if "holidays" in self.fields`)
  - [ ] widget: `holidays` as a checkbox multi-select or size-limited `SelectMultiple` (`forms.CheckboxSelectMultiple`
        is friendliest for a typically-short optional-holiday list)
- [ ] `FloatingHolidayElectionForm(TenantModelForm)` — **SECURITY comment mirroring `LeaveRequestForm`**:
      `status`/`approved_by`/`approved_at` are deliberately NOT form fields — a new election starts "pending" and
      both are set only by the approve/reject workflow views:
  - [ ] `Meta.fields = ["employee", "holiday", "policy", "note"]`
  - [ ] `__init__`: narrow `holiday` queryset to `PublicHoliday.objects.filter(tenant=self.tenant,
        is_optional=True)`; narrow `policy` queryset to `HolidayPolicy.objects.filter(tenant=self.tenant,
        is_active=True)`; make `policy` not required (`self.fields["policy"].required = False`) since it
        auto-resolves in `save()` if left blank

## C. Views (`apps/hrm/views.py`)

- [ ] `publicholiday_list` — no logic change needed beyond passing `category_choices` if a category filter is
      added (see below); import `PublicHoliday.CATEGORY_CHOICES`.
  - [ ] add a `category` filter to the existing `crud_list(...)` call: `filters=[("is_optional", "is_optional",
        False), ("category", "category", False)]`; add `"category_choices": PublicHoliday.CATEGORY_CHOICES` to
        `extra_context`.
- [ ] `holidaypolicy_list` (`@login_required`) — `crud_list(request,
      HolidayPolicy.objects.filter(tenant=request.tenant).select_related("org_unit", "designation"),
      "hrm/holiday/holidaypolicy/list.html", search_fields=["name", "location"], filters=[("is_active",
      "is_active", False), ("employee_type", "employee_type", False), ("org_unit", "org_unit_id", True),
      ("designation", "designation_id", True)], extra_context={"employee_type_choices":
      EmployeeProfile.EMPLOYEE_TYPE_CHOICES, "org_units": OrgUnit.objects.filter(tenant=request.tenant),
      "designations": Designation.objects.filter(tenant=request.tenant)})`
- [ ] `holidaypolicy_create` / `holidaypolicy_edit` / `holidaypolicy_delete` — standard `crud_create`/`crud_edit`/
      `crud_delete` wrappers (mirror `publicholiday_*`), template paths under `hrm/holiday/holidaypolicy/`.
- [ ] `holidaypolicy_detail` (`@login_required`) — `crud_detail(request, model=HolidayPolicy, pk=pk, template=
      "hrm/holiday/holidaypolicy/detail.html", select_related=("org_unit", "designation"))`; template shows the
      linked `holidays.all` and a reverse list of `obj.elections.all()[:10]` (recent elections against this
      policy) if useful.
- [ ] `floatingholidayelection_list` (`@login_required`) — `crud_list(request,
      FloatingHolidayElection.objects.filter(tenant=request.tenant).select_related("employee", "holiday",
      "policy"), "hrm/holiday/floatingholidayelection/list.html", search_fields=["employee__party__name",
      "holiday__name"] (verify the actual name-lookup path used elsewhere for `EmployeeProfile`, e.g. how
      `leaverequest_list` searches employee — mirror that exact lookup string), filters=[("status", "status",
      False), ("employee", "employee_id", True), ("holiday", "holiday_id", True)], extra_context={"status_choices":
      FloatingHolidayElection.STATUS_CHOICES, "employees": EmployeeProfile.objects.filter(tenant=request.tenant),
      "holidays": PublicHoliday.objects.filter(tenant=request.tenant, is_optional=True)})`
- [ ] `floatingholidayelection_create` (`@login_required`) — `crud_create(...)`; on success the `save()`
      auto-resolves `policy` if left blank (handled in the model, not the view).
- [ ] `floatingholidayelection_detail` / `_edit` / `_delete` — standard wrappers mirroring `publicholiday_*`,
      template paths under `hrm/holiday/floatingholidayelection/`.
- [ ] `floatingholidayelection_approve` (`@tenant_admin_required`, `@require_POST`) — mirror
      `leaverequest_approve`: `get_object_or_404(FloatingHolidayElection, pk=pk, tenant=request.tenant)`; if
      `status == "pending"`: set `status="approved"`, `approved_by=request.user`, `approved_at=timezone.now()`,
      `obj.save(update_fields=["status","approved_by","approved_at","updated_at"])`;
      `write_audit_log(request.user, obj, "update", {"action": "approve"})`; success message; redirect to
      `hrm:floatingholidayelection_detail`.
- [ ] `floatingholidayelection_reject` (`@tenant_admin_required`, `@require_POST`) — mirror
      `leaverequest_reject`: set `status="rejected"`, `approved_by=request.user`, store `request.POST.get("note",
      "").strip()[:2000]` appended/overwriting `note` (or a dedicated rejection reason — reuse `note` field since
      no separate `rejected_reason` was scoped); `write_audit_log(..., {"action": "reject"})`; redirect to detail.
- [ ] all new views import `HolidayPolicy`, `FloatingHolidayElection`, `HolidayPolicyForm`,
      `FloatingHolidayElectionForm` at the top of `views.py` alongside the existing HRM imports.

## D. URLs (`apps/hrm/urls.py`, `app_name = "hrm"` already set)

- [ ] no new path needed for `publicholiday_*` (existing 5 routes unchanged; only the form/list gain `category`).
- [ ] `path("holiday-policies/", views.holidaypolicy_list, name="holidaypolicy_list")`
- [ ] `path("holiday-policies/add/", views.holidaypolicy_create, name="holidaypolicy_create")`
- [ ] `path("holiday-policies/<int:pk>/", views.holidaypolicy_detail, name="holidaypolicy_detail")`
- [ ] `path("holiday-policies/<int:pk>/edit/", views.holidaypolicy_edit, name="holidaypolicy_edit")`
- [ ] `path("holiday-policies/<int:pk>/delete/", views.holidaypolicy_delete, name="holidaypolicy_delete")`
- [ ] `path("floating-holidays/", views.floatingholidayelection_list, name="floatingholidayelection_list")`
- [ ] `path("floating-holidays/add/", views.floatingholidayelection_create, name="floatingholidayelection_create")`
- [ ] `path("floating-holidays/<int:pk>/", views.floatingholidayelection_detail, name="floatingholidayelection_detail")`
- [ ] `path("floating-holidays/<int:pk>/edit/", views.floatingholidayelection_edit, name="floatingholidayelection_edit")`
- [ ] `path("floating-holidays/<int:pk>/delete/", views.floatingholidayelection_delete, name="floatingholidayelection_delete")`
- [ ] `path("floating-holidays/<int:pk>/approve/", views.floatingholidayelection_approve, name="floatingholidayelection_approve")`
- [ ] `path("floating-holidays/<int:pk>/reject/", views.floatingholidayelection_reject, name="floatingholidayelection_reject")`

## E. Admin (`apps/hrm/admin.py`)

- [ ] register `HolidayPolicy` — `list_display = ("name", "tenant", "location", "org_unit", "employee_type",
      "designation", "is_default", "floating_holiday_quota", "is_active")`, `list_filter = ("tenant",
      "is_default", "is_active", "employee_type")`, `search_fields = ("name", "location")`
- [ ] register `FloatingHolidayElection` — `list_display = ("employee", "holiday", "policy", "status",
      "requested_on", "approved_by")`, `list_filter = ("tenant", "status")`, `search_fields = ("employee__party__name",
      "holiday__name")` (match the real employee-name lookup path confirmed in Section C)
- [ ] update `PublicHolidayAdmin.list_display`/`list_filter` to include `category`

## F. Templates (`templates/hrm/holiday/<entity>/<page>.html`)

- [ ] `holiday/publicholiday/list.html` — add the `category` filter select (reflecting `request.GET.category`,
      options from `category_choices`) alongside the existing `is_optional`/`year` filters; add a category badge
      column.
- [ ] `holiday/publicholiday/detail.html` — show `category` (display value via `get_category_display`).
- [ ] `holiday/publicholiday/form.html` — add the `category` field to the form (no structural change otherwise).
- [ ] `holiday/holidaypolicy/list.html` — filter bar: search `q`, `is_active` select, `employee_type` select
      (from `employee_type_choices`), `org_unit` select (from `org_units`, `|stringformat:"d"` pk compare),
      `designation` select (from `designations`); columns: name, location, org_unit, employee_type, designation,
      floating_holiday_quota, is_default badge, is_active badge, Actions (view/edit/delete); pagination include;
      empty-state.
- [ ] `holiday/holidaypolicy/detail.html` — show all fields incl. `holidays.all` as a chip/badge list and
      `is_default`/`is_active` badges; Actions sidebar (Edit/Delete + Back to List).
- [ ] `holiday/holidaypolicy/form.html` — standard form template (checkbox-multiselect for `holidays`).
- [ ] `holiday/floatingholidayelection/list.html` — filter bar: search `q`, `status` select (from
      `status_choices`), `employee` select (from `employees`, pk-compare), `holiday` select (from `holidays`,
      pk-compare); columns: employee, holiday (+ date), policy, status badge, requested_on, Actions
      (view/edit/delete — Edit/Delete conditional on `status == "pending"` per CRUD rule 2); pagination include;
      empty-state.
- [ ] `holiday/floatingholidayelection/detail.html` — show employee/holiday/policy/status
      badge/requested_on/approved_by/approved_at/note; Actions sidebar: Approve button (POST form, confirm,
      csrf, `{% if obj.status == "pending" %}`), Reject button (POST form, confirm, csrf, same guard), Edit/Delete
      (guard on `status == "pending"`), Back to List.
- [ ] `holiday/floatingholidayelection/form.html` — standard form template (employee/holiday/policy/note).

## G. Seeder (`apps/hrm/management/commands/seed_hrm.py`)

- [ ] extend the existing "Public holidays" block (~L305-309): add `category` per row (national for the fixed
      seeded holidays, mark 1-2 as `regional`/`company` if the existing `HOLIDAYS` tuple has enough entries, else
      just set all to `"national"` via `defaults` update) — must stay idempotent (`get_or_create`, update
      `category` on the `defaults` dict only, no unconditional `.save()`).
- [ ] add a new idempotent block after Shifts/attendance (or right after the public-holidays block): create 1-2
      `HolidayPolicy` rows per tenant via `get_or_create(tenant=tenant, name=...)`:
  - [ ] a default policy: `name="Company Default"`, `is_default=True`, `floating_holiday_quota=2`,
        `is_active=True`
  - [ ] a scoped policy: `name="<some work_location or designation> Policy"`, `location=` (pull an existing
        seeded `EmployeeProfile.work_location` value if present, else leave blank and scope by `employee_type`
        or `designation` instead), `floating_holiday_quota=1`, `is_active=True`
  - [ ] attach 1-2 of the seeded optional `PublicHoliday` rows to each via `.holidays.set([...])`
- [ ] add a new idempotent block creating 2-3 `FloatingHolidayElection` rows against existing seeded
      `EmployeeProfile` + an optional `PublicHoliday`, using `get_or_create(tenant=tenant, employee=emp,
      holiday=holiday, defaults={"note": "...", "status": "pending" or "approved"})` — guard with `.exists()`
      check per (employee, holiday) pair (the `unique_together` already prevents dupes, but `get_or_create` is
      the idempotent-safe path per the Seed Command Rules). For an `"approved"` seeded row, also set
      `approved_by`/`approved_at` in `defaults` (pick the tenant's admin/first superuser-scoped user if available,
      else leave null).
- [ ] verify the seeder still prints the tenant-admin login reminder + "Data already exists" warning path
      unchanged (no new top-level `if Model.objects.filter(tenant=tenant).exists()` guard needed since this
      reuses the existing per-tenant loop — just make each new block itself idempotent).

## H. Navigation (`apps/core/navigation.py`)

- [ ] update `LIVE_LINKS["3.12"]` (currently only `"Holiday Calendar": "hrm:publicholiday_list"`) to:
      ```python
      "3.12": {
          "Holiday Calendar": "hrm:publicholiday_list",          # bullet
          "Floating Holidays": "hrm:floatingholidayelection_list",  # bullet
          "Holiday Policies": "hrm:holidaypolicy_list",          # bullet
      },
      ```
      — all 3 NavERP.md 3.12 bullets go Live.

## I. Migrate / seed / verify (run from the venv)

- [ ] `python manage.py makemigrations hrm` → review `0023_...py` (field/M2M/index names match plan)
- [ ] `python manage.py migrate`
- [ ] `python manage.py seed_hrm` (1st run — creates data)
- [ ] `python manage.py seed_hrm` (2nd run — must be idempotent, no duplicates, no errors)
- [ ] `python manage.py check`
- [ ] `temp/` smoke sweep: every new `hrm:holidaypolicy_*` and `hrm:floatingholidayelection_*` URL returns
      200/302 when logged in as a tenant admin; `publicholiday_list` still 200 with the new `category` filter
      param; no `{#`/`{% comment` leaks in the new templates; cross-tenant IDOR check — a `HolidayPolicy`/
      `FloatingHolidayElection` pk belonging to tenant A returns 404 when fetched as tenant B; approve/reject
      POST from a non-admin tenant user is blocked (`@tenant_admin_required`); quota-exceeding election attempt
      raises the `clean()` ValidationError (form re-renders with the error, no row created).
- [ ] sidebar: confirm 3.12 shows all three bullets as **Live** (not "Coming soon") for a tenant with data.

## J. Close-out

- [ ] update `README.md` module-status / HRM section (3.12 bullets: Holiday Calendar / Floating Holidays /
      Holiday Policies all live; bump the HRM + project-wide test-count lines once test-writer runs)
- [ ] run the review-agent sequence in order, each ending in its own commit(s): `code-reviewer` →
      `explorer` → `frontend-reviewer` → `performance-reviewer` → `qa-smoke-tester` → `security-reviewer` →
      `test-writer`
- [ ] update `.claude/skills/hrm/SKILL.md` — 3.12 section: document `HolidayPolicy`/`FloatingHolidayElection`
      models, the `for_employee` resolver, the approve/reject workflow, the new LIVE_LINKS entries, the extended
      seeder block, and mark all 3 bullets of 3.12 as built (bump the module's sub-module-count table if present)

## Later passes / deferred (carried over from research-holiday.md — do not build this pass)

- Bulk/country-based holiday import (CSV or "duplicate previous year") — UX add-on to `PublicHoliday`'s create
  flow, not a data-model gap.
- Weekend-observance auto-shift (holiday on Sat/Sun rolls to nearest weekday) — edge case, not a NavERP.md bullet.
- Auto-reprocessing of overlapping `LeaveRequest`s when a holiday is added/edited (Zoho People pattern) — needs a
  background-job mechanism; `_recompute_days()` only fires on the `LeaveRequest`'s own save today.
- Reminder emails before a holiday — email-delivery integration, later.
- iCal/Outlook/Google calendar sync, per-employee subscribable feeds — integration, explicitly out of scope.
- Public/private holiday visibility toggle + "Who's Out" dashboard widget (BambooHR) — UI/dashboard layer on the
  existing `publicholiday_list`, not a model change.
- Temporary/travel holiday-calendar override (SAP SuccessFactors) — the most-specific-match `HolidayPolicy`
  resolution already covers location differences without a per-trip override object.
- Controlled reason/occasion-code taxonomy for floating-holiday requests (vs. free-text `note`) — defer until a
  concrete compliance need arises.
- Hard scheduler/cutoff enforcement for election deadlines — at most a future informational field on
  `HolidayPolicy`; no blocking date-window validator this pass.

## Review

(filled in at the end)
