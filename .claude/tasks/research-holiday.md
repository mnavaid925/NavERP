# Research — Module 3: HRM, Sub-module 3.12 Holiday Management (holiday)

> Scope note: this is a **completion** run, not greenfield. `apps/hrm/models.py::PublicHoliday` (date, name,
> is_optional, unique_together tenant+date+name) is already built with full CRUD, seeded, wired into
> `LIVE_LINKS["3.12"]["Holiday Calendar"]`, and already excludes non-optional holidays from `LeaveRequest.days`.
> Only the **Floating Holidays** and **Holiday Policies** bullets are open. This catalog researches those two
> gaps only, then maps findings onto realistic Django/tenant-scoped models built on the existing spine
> (`hrm.EmployeeProfile`, `hrm.PublicHoliday`, `core.OrgUnit`) — no new spine masters, no external calendar sync.

## Leaders surveyed (with source links)

1. **BambooHR** — SMB-friendly HRIS; bulk multi-country holiday creation (180+ countries), public/private holiday
   visibility toggle, "Who's Out" calendar — [Product Updates: Country-Specific Bulk Holiday Creation](https://www.bamboohr.com/product-updates/add-holidays-in-bulk-by-country), [Floating Holiday glossary](https://www.bamboohr.com/resources/hr-glossary/floating-holiday), [Holiday Visibility](https://www.bamboohr.com/product-updates/holiday-visibility-for-all-employees)
2. **Workday HCM** — enterprise HCM; holidays auto-assigned to time-off requests by entity/location/department,
   admin can select state/region — [Tracking Holidays in Workday](https://employeehelp.workday.uw.edu/admin-corner/hcm-resources/tracking-holidays-in-workday/), [Workable holiday calendars](https://help.workable.com/hc/en-us/articles/15935846902935-Adding-and-managing-holiday-calendars)
3. **Zoho People** — SMB/mid-market HRIS; holiday classification (national/optional/special), reprocess-leave-on-holiday-add, reminder emails — [Holiday Settings](https://help.zoho.com/portal/en/kb/people/administrator-guide/leave/settings/articles/holiday-zoho-people), [Managing Holidays](https://help.zoho.com/portal/en/kb/people/administrator-guide/leave/operations/articles/managing-holidays)
4. **Keka HR** — India-focused HRMS; multiple "holiday plans" assignable per employee group, per-holiday
   floater/optional flag (single + bulk import), Floater Leave applied via the leave-request dropdown —
   [Creating a holiday plan](https://help.keka.com/admin/creating-a-holiday-plan-for-your-employees), [Floating Holiday Policy](https://www.keka.com/glossary/floating-holiday), [Floater leave application](https://help.keka.com/admin/admin-help/how-can-an-employee-apply-for-floater-leave)
5. **Darwinbox** — enterprise HRMS (APAC); "Restricted Holiday" = optional holiday with a **maximum-selection
   cap** from a larger list, employee-only (not company-wide closure) — [Restricted Holidays glossary](https://darwinbox.com/hr-glossary/restricted-holidays)
6. **greytHR** — India HRMS; holiday list filterable/settable by **Location, Designation, and Attendance Scheme**
   columns; per-holiday "Restricted Holiday" Yes/No column — [How can admin set location wise holiday list](https://greythr.freshdesk.com/support/solutions/articles/1060000051068-how-can-admin-set-location-wise-holiday-list-), [Create Employee Holiday List (Location, Grade, Department)](https://www.greythr.com/videos/how-to-admin/create-employee-holiday-list/)
7. **factoHR** — India HRMS; optional/restricted holidays assignable to different **employee groups**, explicit
   example of "choose a maximum of 2 optional holidays from the list" — [Restricted Holidays definition](https://factohr.com/hr-glossary/restricted-holidays/)
8. **Personio** — EU-focused HRIS; public-holiday calendars are **assigned to offices/workplaces**, employees see
   the calendar tied to their assigned office; custom calendars can be duplicated/customized per country —
   [Configure time off policies and public holidays](https://learn.personio.com/configure-accrual-policies-and-public-holidays-en), [Create/manage custom bank holiday calendars](https://support.personio.de/hc/en-us/articles/22919070507037-Create-and-manage-custom-bank-holiday-calendars)
9. **HiBob (Bob)** — mid-market HRIS; calendars defined under Settings, "typical starting point is two floating
   holidays a year," policy note that some orgs restrict floating holidays to specific eligible days — [Holiday Calendars](https://help.hibob.com/en/articles/2057939-holiday-calendars), [What is a floating holiday?](https://www.hibob.com/hr-glossary/floating-holiday/)
10. **SAP SuccessFactors Employee Central** — enterprise HCM; Holiday Calendar as a first-class object, an
    employee assigned exactly **one** Holiday Calendar at a time (calendar tied to location/work schedule),
    permission-gated "Temporary Holiday Calendar" for business travel — [Holiday Calendar](https://help.sap.com/docs/successfactors-employee-central/implementing-time-management-in-sap-successfactors/holiday-calendar-f34eff3c38d4490c8fc650246b506fb1), [Temporary Holiday Calendar](https://help.sap.com/docs/successfactors-employee-central/implementing-time-management-in-sap-successfactors/temporary-holiday-calendar)

Also referenced for the approval-workflow pattern: **general floating-holiday-request workflow** (submit ->
manager notification -> approve/deny, advance-notice window, optional reason-code when restricted to specific
occasions) — [Floating Holidays: A Guide for HR Managers](https://www.leapsome.com/blog/floating-holiday), and
**Gusto** for the simplest-possible baseline (one company-wide holiday-pay policy, federal holidays auto-roll
forward, weekend-observance shift to nearest weekday) — [Gusto: Create a holiday pay policy](https://docs.gusto.com/embedded-payroll/docs/create-a-holiday-pay-policy).

## Feature catalog by NavERP.md bullet

### Holiday Calendar — national, regional, company holidays

- **Single tenant-wide holiday list with name/date/optional flag** — already built (`PublicHoliday`) · seen in:
  all 10 · priority: table-stakes · spine: reuse `hrm.PublicHoliday` · **ALREADY COVERED — no new work.**
- **Bulk/country-based holiday creation** — add many holidays for a country/year in one action · seen in:
  BambooHR, factoHR (per-state India lists) · priority: common · spine: could extend `PublicHoliday` create form
  with a "duplicate previous year" or CSV-style bulk-add action · **NEW but minor — buildable now, low
  priority** (a bulk-add helper view, not a new model).
- **Weekend-observance shift (holiday falling on Sat/Sun rolls to nearest weekday)** — seen in: Gusto (federal
  holidays) · priority: common · spine: could be a boolean/computed note on `PublicHoliday` · **deferred** — edge
  case, not requested by NavERP.md bullet, skip for this pass.
- **Public/private holiday visibility toggle, "Who's Out" style calendar widget** — seen in: BambooHR · priority:
  differentiator · **deferred** — UI/dashboard widget, not a data-model gap; can piggyback on existing
  `PublicHoliday` list view later.
- **Region/state-level public holidays (e.g. Indian state holiday calendars)** — seen in: Workday, factoHR ·
  priority: common · overlaps with "Holiday Policies" location scoping below — see `HolidayPolicy.location`
  field.
- **Holiday category/classification (national / regional / company / observance)** — seen in: Zoho People
  (national/optional/special classification) · priority: common · spine: `PublicHoliday.category` — **NEW,
  small field addition** to the existing model (not a new model) so calendar entries can be grouped/filtered by
  type beyond just the boolean `is_optional`.
- **Auto-reprocess overlapping leave requests when a holiday is added/changed** — seen in: Zoho People · priority:
  differentiator · **deferred** — nice automation, out of scope for this pass (existing `_recompute_days()` only
  runs on save of the `LeaveRequest` itself, not a bulk reprocessing job).
- **Reminder emails N days before a holiday** — seen in: Zoho People · priority: differentiator · **integration/
  later** (email delivery infra).
- **iCal / calendar-feed export, Outlook/Google sync** — seen in: BambooHR, Personio, HiBob · priority: common ·
  **integration/later** — explicitly out of scope per the prompt.

### Floating Holidays — optional holidays, restriction rules

- **Per-holiday "optional/floater" flag** — already built (`PublicHoliday.is_optional`) · seen in: all 10 ·
  priority: table-stakes · **ALREADY COVERED.**
- **Employee elects N holidays from the optional list (a discrete pick, not automatic)** — seen in: Darwinbox,
  Keka, factoHR, greytHR, HiBob · priority: table-stakes for any real "floating holiday" feature · spine: **NEW
  table** `FloatingHolidayElection` (employee -> chosen `PublicHoliday`, per year) · **NEW work — core of this
  pass.**
- **Maximum-selection cap ("choose up to N optional holidays")** — seen in: Darwinbox ("maximum limit attached"),
  factoHR (explicit "maximum of 2"), HiBob ("typical starting point is two") · priority: table-stakes · spine:
  new field `HolidayPolicy.floating_holiday_quota` (int) checked at election time · **NEW work.**
- **Floater/optional-holiday request routed through the normal leave-request-style approval workflow (submit ->
  manager notify -> approve/deny)** — seen in: Keka (applied via leave-request dropdown), general pattern (Leapsome
  guide) · priority: common · spine: `FloatingHolidayElection.status` (pending/approved/rejected) +
  `approved_by`/`approved_at`, mirroring the existing `LeaveRequest` approval shape · **NEW work.**
- **Advance-notice / cutoff deadline for floating-holiday requests** — seen in: general pattern (Leapsome,
  Careerminds) · priority: common · spine: could be `HolidayPolicy.election_deadline_days` but this is soft
  business-rule territory · **partial NEW** — include a simple deadline note/validation, not a hard scheduler.
  Keep as a small optional field, not a blocking workflow engine.
- **Reason/occasion code required when floating holiday is tied to religious/cultural observance** — seen in:
  general pattern · priority: differentiator · spine: `FloatingHolidayElection.note` (free text) is sufficient —
  don't build a controlled reason-code taxonomy this pass · **deferred (light touch only).**
- **Use-it-or-lose-it within the calendar year (no carryover)** — seen in: BambooHR (glossary) · priority: common
  · this is enforced implicitly by scoping `PublicHoliday`/election to a given year — no extra field needed
  beyond the date already on `PublicHoliday`.
- **Floating holiday counted separately from PTO/leave balance (doesn't consume vacation days)** — seen in: all —
  this is why `LeaveRequest._recompute_days()` already excludes only *non*-optional holidays (optional ones
  still count as working days unless separately elected) — confirms the election needs to be its **own** record,
  not folded into `LeaveRequest`. **Design confirmation, no new field.**

### Holiday Policies — location-based holidays, eligibility

- **Holiday calendar/list scoped by office/location** — seen in: Personio (calendar assigned to workplace/office),
  greytHR (Location column), Workday (entity/location/department auto-assignment), SAP SuccessFactors (one
  Holiday Calendar object per employee, tied to location) · priority: table-stakes for any "policy" concept ·
  spine: **NEW table** `HolidayPolicy` with a `location` matcher against `EmployeeProfile.work_location`
  (free-text field that already exists) · **NEW work — core of this pass.**
- **Holiday list scoped by employee group / grade / designation / attendance scheme** — seen in: greytHR
  (Location + Designation + Attendance Scheme filters), Keka (holiday plan per employee group), factoHR
  (assignable to different employee groups) · priority: common · spine: `HolidayPolicy` eligibility filters
  mapped onto **existing** `EmployeeProfile` fields only — `employee_type` (full_time/part_time/contract/intern/
  consultant) and `designation` FK; do **not** invent a new "employee group" master · **NEW work, constrained to
  existing fields** (per prompt guardrail — no FKs into unbuilt spine masters).
- **Department/org-unit scoping** — seen in: greytHR, Workday (department-level auto-assignment) · spine: reuse
  `core.OrgUnit` via `EmployeeProfile.department` property (from `employment.org_unit`) · priority: common ·
  **NEW work** — `HolidayPolicy.org_unit` FK (nullable = applies to all departments).
- **One calendar/policy assigned per employee at a time, admin can override for travel** — seen in: SAP
  SuccessFactors (single Holiday Calendar + temporary override) · priority: differentiator · **deferred** — the
  temporary-travel-calendar override is enterprise-grade complexity not warranted here; a single best-match
  policy resolution (most specific match wins) covers the NavERP need.
- **Policy links a subset of the tenant's holiday list to the group it applies to (not a fully separate
  calendar)** — seen in: greytHR (per-holiday Location cell rather than a wholesale separate list), Zoho People
  (single list with classification) · priority: table-stakes · spine: this favors a **join table** or M2M between
  `HolidayPolicy` and `PublicHoliday` rather than duplicating holiday rows per location · **design decision for
  this pass** — `HolidayPolicy.holidays = ManyToManyField(PublicHoliday)` (optional; if empty, policy applies to
  the full tenant list, only the eligibility/quota narrows).
- **Default/company-wide policy fallback when no specific policy matches an employee** — seen in: Personio
  (company-level calendar as default, office-level overrides), Gusto (one company-wide policy is often the only
  one at SMB scale) · priority: table-stakes · spine: `HolidayPolicy.is_default` boolean + `location`/`org_unit`/
  `employee_type`/`designation` all nullable = wildcard · **NEW work.**

## Recommended build scope (this pass — 2–3 models)

Fills the two open bullets (**Floating Holidays**, **Holiday Policies**) while enriching the already-built
`PublicHoliday` with one small field. No new spine masters; every FK/eligibility field points at
`hrm.EmployeeProfile`, `core.OrgUnit`, or the existing `accounts` User (approver) — nothing unbuilt.

1. **`PublicHoliday` — enrich, don't rebuild** [existing model, additive migration]
   - Add `category` choice field (`national`, `regional`, `company`, `observance`) — justified by Zoho People's
     national/optional/special classification and Workday's regional-holiday distinction. `is_optional` stays as
     the floating/non-floating switch (already correct — don't rename it).
   - No other changes; CRUD/urls/templates/seed already exist and stay as-is.

2. **`HolidayPolicy(TenantOwned)`** [`HPOL-` if numbered, or plain tenant-scoped, no number prefix needed —
   follow existing `PublicHoliday`/`Shift` pattern of `TenantOwned` without a number] — justified by Personio
   (calendar-per-office), greytHR (Location/Designation/Attendance-Scheme filters), Darwinbox/factoHR (max-cap),
   SAP SuccessFactors (default + most-specific-match resolution):
   - `name` (CharField) — e.g. "Head Office — Full Time", "Karachi Branch"
   - `location` (CharField, blank) — matched against `EmployeeProfile.work_location` (exact/contains match, since
     `work_location` is free text, not an FK)
   - `org_unit` (FK to `core.OrgUnit`, null/blank) — department/branch scoping, reuses spine
   - `employee_type` (CharField, blank, choices reuse `EmployeeProfile.EMPLOYEE_TYPE_CHOICES`) — eligibility by
     employment type
   - `designation` (FK to `hrm.Designation`, null/blank) — grade-level eligibility
   - `is_default` (BooleanField) — the fallback policy when no more specific policy matches
   - `floating_holiday_quota` (PositiveSmallIntegerField, default 0) — the "choose up to N" cap (Darwinbox/
     factoHR/HiBob pattern)
   - `holidays` (ManyToManyField to `PublicHoliday`, blank) — optional narrowing of which tenant holidays this
     policy's `is_optional=True` rows draw from; empty = all tenant optional holidays are eligible
   - A resolution helper (e.g. `HolidayPolicy.for_employee(profile)` classmethod) that picks the most specific
     matching policy (org_unit+designation+employee_type+location match > partial match > `is_default`) — keeps
     "eligibility" logic in one place rather than duplicated across views.

3. **`FloatingHolidayElection(TenantOwned)`** — justified by Keka (floater-leave application + approval),
   Darwinbox/factoHR (cap enforcement against the policy quota), general approval-workflow pattern:
   - `employee` (FK to `hrm.EmployeeProfile`)
   - `holiday` (FK to `hrm.PublicHoliday`, must have `is_optional=True`)
   - `policy` (FK to `HolidayPolicy`, null/blank — the policy whose quota this election counts against; can be
     resolved automatically at save time via `HolidayPolicy.for_employee`)
   - `status` (CharField, choices: `pending`, `approved`, `rejected`) — mirrors `LeaveRequest` shape
   - `requested_on` (DateField, auto_now_add)
   - `approved_by` (FK to `accounts.User`, null/blank)
   - `approved_at` (DateTimeField, null/blank)
   - `note` (TextField, blank) — light-touch reason/occasion field (per "deferred, light touch only" above)
   - `unique_together = (tenant, employee, holiday)` — an employee can't double-elect the same holiday
   - `clean()` validation: reject if the employee's approved-election count for the resolved policy's
     `floating_holiday_quota` in that holiday's year would be exceeded — this is the "restriction rules" bullet
     made concrete.
   - CRUD (list/create/detail/edit/delete + an approve/reject action) mirrors the existing `LeaveRequest` pattern
     already in the codebase.

This is 1 enriched existing model + 2 new models — within the 2–3 model budget the prompt asked for.

## Deferred (later passes / integrations)

- **Bulk/country-based holiday import (CSV or "duplicate previous year")** — nice-to-have UX, not a data-model
  gap; can be added to `PublicHoliday`'s existing create flow later without a new model.
- **Weekend-observance auto-shift** (holiday on Sat/Sun rolls to nearest weekday) — edge case not in the
  NavERP.md bullets; skip.
- **Auto-reprocessing of overlapping `LeaveRequest`s when a holiday is added/edited** (Zoho People) — real
  automation but a distinct background-job concern; the current `_recompute_days()` only fires on the
  `LeaveRequest`'s own save.
- **Reminder emails before a holiday** — integration (email infra), later.
- **iCal/Outlook/Google calendar sync, per-employee subscribable feeds** — integration, explicitly out of scope
  per the prompt.
- **Public/private holiday visibility toggle + "Who's Out" dashboard widget** (BambooHR) — a UI/dashboard
  concern layered on the existing `publicholiday_list` view, not a model change.
- **Temporary/travel holiday-calendar override** (SAP SuccessFactors) — enterprise edge case; the
  most-specific-match `HolidayPolicy` resolution already covers "different location, different holidays"
  without needing a per-trip override object.
- **Controlled reason/occasion-code taxonomy for floating-holiday requests** (vs. free-text `note`) — defer until
  there's a concrete compliance need; free text is enough for this pass.
- **Hard scheduler/cutoff enforcement for election deadlines** — keep as an optional informational field on
  `HolidayPolicy` at most; don't build a blocking date-window validator this pass.
