# Research — HRM Sub-module 3.30: Leave Reports (hrm-3.30)

**Scope (NavERP.md 3.30):** Leave Register (availed + balance), Leave Liability (accrued liability), Comp-off
Report (earned/availed), Leave Trend (monthly/seasonal patterns).

**Build context confirmed in code:** these are DERIVED, read-only, `@tenant_admin_required` report views —
identical pattern to 3.28 (`hr_reports_index` + 5 drill-ins) and 3.29 (`attendance_reports_index` + 5 drill-ins) in
`apps/hrm/views.py`. Reusable helpers already exist: `_report_period(request)` (date_from/date_to, defaults to
trailing 12 months), `_report_department(request, tenant)` (tenant-scoped `OrgUnit(kind="department")`, IDOR-safe),
`_dept_choices(tenant)`. Templates live under `templates/hrm/reports/`; monthly rollups use `TruncMonth` +
`json.dumps([...])` label/value arrays consumed by Chart.js (see `attendance_summary.html` / `overtime.html`
pattern). **No new models — this pass is views + templates + URLs only.**

## Data sources already in the codebase (verified against `apps/hrm/models.py`)
- `hrm.LeaveType` — `name`, `code`, `is_paid`, `accrual_rule`/`accrual_days`, `max_balance`,
  `max_carry_forward`, `encashable` (bool — the only signal for "does this leave type convert to cash").
  Seeded catalog (`seed_hrm.py` `LEAVE_TYPES`) is only **Annual Leave (AL), Sick Leave (SL), Casual Leave (CL),
  Unpaid Leave (UPL)** — **no Comp-off LeaveType exists by convention.**
- `hrm.LeaveAllocation` — `employee`, `leave_type`, `year`, `allocated_days`, `carried_forward` (editable=False),
  `encashed_days` (editable=False). **`used_days` and `balance` are `@property`s, not stored columns**:
  `used_days` = `Sum(LeaveRequest.days)` for `status="approved"`, `start_date__year=self.year`, same
  employee+leave_type (a request that straddles a year boundary is charged whole to its start year — documented
  in-code as a known simplification). `balance = allocated_days − used_days − encashed_days`. For list/report
  aggregates, use the existing `_used_days_subquery()` helper (a correlated `Subquery`/`Coalesce`, already used by
  `leaveallocation_list` as `.annotate(used_days_db=..., balance_db=...)`) instead of the Python property — it
  avoids N+1 aggregate queries. **Reuse this helper for 3.30, do not re-derive.**
- `hrm.LeaveRequest` — `employee`, `leave_type`, `start_date`, `end_date`, `days` (editable=False, holiday-excluded),
  `status` (`draft/pending/approved/rejected/cancelled`). "Availed" = `status="approved"` only.
- `hrm.LeaveEncashment` — `employee`, `leave_type`, `year`, `days`, `rate_per_day` (user-entered on the form, no
  default/lookup elsewhere in the codebase), `amount` (= `days × rate_per_day`, recomputed in `save()`), `status`.
- `hrm.OvertimeRequest` — **field is `payout_method`, not `payout`** (correcting the brief's assumption), choices
  `PAYOUT_CHOICES = [("pay","Pay"), ("comp_leave","Compensatory Leave")]`. Verified `overtimerequest_approve()`:
  approving a `payout_method="comp_leave"` claim only flips `status→"approved"` — **it does NOT create or
  increment any `LeaveAllocation` row.** There is no automatic linkage from an approved comp-leave OT claim to a
  leave balance anywhere in the codebase. This is a real functional/data gap, not just a naming one.
- `hrm.EmployeeSalaryStructure` — `annual_ctc_amount`, `status="active"`, `effective_from/to` — the only CTC figure
  in the system usable to *estimate* a per-day rate when no `LeaveEncashment.rate_per_day` exists.
- `hrm.OrgUnit(kind="department")` — department filter, via `employee__employment__org_unit` (never the
  `.department` Python property, per the existing 3.29 convention).

## Leaders surveyed (with source links)
1. **Keka** — Indian/APAC HRMS; Leave Analytics with usage-trend, absenteeism, and leave-liability reporting; a
   dedicated "Leave Balances of Employees" export and year-end leave-balance-action screen (available balance,
   encashed, carry-forward, expiring) — [Keka Leave Register guide](https://www.keka.com/leave-register), [Keka
   Leave Balance report](https://help.keka.com/admin/admin-help/how-to-download-leave-balance-report), [Year-End
   Leave Processing](https://help.keka.com/admin/mastering-year-end-leave-processing-on-keka)
2. **greytHR** — Leave Balance report ("as on a day"), Leave Summary (deducted-this-month + balance), a dedicated
   **Comp-off tab** listing comp-offs per employee — [Leave Balance As On A Day](https://support.greythr.com/hc/en-us/articles/360002132032-How-can-I-generate-the-Leave-Balance-As-on-a-Day-report-for-an-individual-employee-), [Leave Summary Report](https://support.greythr.com/hc/en-us/articles/360004491451-How-to-generate-Leave-Summary-Report-on-greytHR-), [Employee leave details incl. comp-off](https://admin-help.greythr.com/admin/answers/123027067/)
3. **Zoho People** — Daily leave-status report ("who's on leave today"), Resource Availability report, Employee
   Leave Balance report, Leave Booked & Balance report explicitly segmenting paid/unpaid/**compensatory-off** —
   [Zoho People Leave Reports](https://www.zoho.com/people/help/adminguide/leave-reports.html), [Leave Booked and
   Balance Report API](https://www.zoho.com/people/api/leave/reports/bookedandbalance.html)
4. **BambooHR** — "Who's Out" calendar, self-service balance calculator, exportable time-off reports sliced by
   team/department/location for spotting overuse patterns — [BambooHR Time Off](https://www.bamboohr.com/platform/time-and-attendance/time-off), [Time Off Balances Report](https://help.bamboohr.com/s/article/587894)
5. **Darwinbox** — AI-assisted seasonal leave-pattern detection, comp-off/overtime/absconding handled in one
   attendance-exception dashboard, absenteeism-rate / frequency / duration metrics — [Darwinbox Leave Management
   guide](https://blog.darwinbox.com/leave-management), [Track Better, Act Smarter](https://darwinbox.com/blog/track-better-act-smarter-with-our-leave-and-attendance-module)
6. **SAP SuccessFactors Employee Central Time Off** — explicit **leave-liability** capability: "calculate the value
   of open vacation entitlements... reflect them in their balance sheets," computed off periodic **Time Account
   Snapshots**, country/region-specific — confirms leave liability is a real, GL-adjacent report family, not a
   NavERP invention — [SAP Reporting in Time Off](https://help.sap.com/docs/successfactors-employee-central/operating-time-management-in-sap-successfactors/using-reporting-in-time-off)
7. **Workday Absence Management** — the closest 1:1 precedent: a **Time Off Liability report** ("dollar-cost of
   each employee's remaining time off... the cost of those hours to the business"), a **Time Off Plan Details**
   report (accrual rate, YTD accrued, current balance), and a **Workers on Leave** report — [Workday Absence
   Management](https://www.workday.com/en-us/products/workforce-management/absence.html), [Must-Use Reports for
   Workday Absence](https://commitconsulting.com/blog/workday-absence-custom-reports)
8. **Replicon** — global leave/PTO tracking with accrual + carryover visibility, real-time absence visibility for
   staffing — [Replicon Time Off](https://www.replicon.com/time-attendance/time-off-software/)
9. **Deputy** — leave request/approve/track with team-schedule integration for coverage planning — [Deputy Leave
   Management](https://www.deputy.com/features/leave-management)
10. **Freshteam** — team/org-wide time-off reports for "upcoming leaves, absenteeism trends," bulk balance
    adjustment (explicitly called out for accommodating **comp-offs**) — [Freshteam
    features](https://www.getapp.com/hr-employee-management-software/a/freshteam/features/)
11. **Vacation Tracker** (industry reference for the liability *formula*, not a leaders-list product) — the
    canonical calc: `accrued balance (days/hours) × pay rate = liability value`, summed org-wide — [How Companies
    Calculate and Manage Leave Liabilities](https://vacationtracker.io/blog/leave-liabilities/)

## Feature catalog by report family

### Leave Register (availed + balance)
- **Per-employee × leave-type grid: allocated / carried-forward / used / balance** — seen in: Keka, greytHR,
  Zoho People, BambooHR · priority: table-stakes · source: `LeaveAllocation.allocated_days` + `.carried_forward` +
  `_used_days_subquery()` + `balance_db` · **Must** · buildable now (exact fields already exist).
- **"As on a day" point-in-time balance** — seen in: greytHR (Leave Balance As On A Day) · priority: common ·
  source: same as above, filtered to a `year`/`as_of` param · **Nice** (the year-scoped grid above already covers
  the common case; a specific as-of-date snapshot is a refinement, not a new data need).
- **Leave-availed detail (who took what, when)** — seen in: greytHR (leave-availed report), Keka · priority:
  table-stakes · source: `LeaveRequest` filtered `status="approved"` · **Must**.
- **Encashed-days shown alongside balance** — seen in: Keka (year-end leave-balance actions) · priority: common ·
  source: `LeaveAllocation.encashed_days` (already netted into `balance`) · **Must** (cheap — the field already
  exists on the row).
- **"Who's on leave today / this week" widget** — seen in: BambooHR ("Who's Out"), Zoho People (daily leave
  status), Darwinbox · priority: table-stakes (as a widget, not always a formal "report") · source: `LeaveRequest`
  `status="approved"`, `start_date__lte=X__lte=end_date` · **Nice** — `hrm_overview` already computes
  `on_leave_today` as a stat tile; a small "on leave today" list could be folded into the register report page
  rather than a separate view.
- **Department / leave-type rollups (totals, not just per-employee rows)** — seen in: all surveyed products ·
  priority: table-stakes · source: same models, `.values(...).annotate(...)` · **Must**.
- **Export to Excel/PDF for statutory leave-register compliance** — seen in: Keka (explicitly markets a
  "leave register" compliance template), greytHR · priority: common · integration/later (no PDF/Excel export
  infra in this pass — flag for a future export pass, same as other NavERP reports).

### Leave Liability (accrued unused-leave value)
- **Balance × per-day rate = liability value, per employee, summed org-wide** — seen in: Workday (Time Off
  Liability report), Vacation Tracker (canonical formula), SAP SuccessFactors (balance-sheet leave liability) ·
  priority: differentiator (fewer products expose this by name, but it's a recognized report family) · source:
  `LeaveAllocation.balance` (days) × a resolved rate · **Must** (days-based is trivial; $-based needs the
  fallback chain below).
- **Rate resolution when no stored per-day pay rate exists** — NavERP has **no** stored per-day leave rate on
  `LeaveType`/`EmployeeProfile`. Fallback chain (document as an explicit design decision, mirroring how Workday/SAP
  need payroll data to do this at all):
  1. Latest `LeaveEncashment.rate_per_day` for that employee+leave_type (any status, most recent by
     year/created_at) — the only "real" per-day rate NavERP has ever recorded for that person.
  2. Else estimate from `EmployeeSalaryStructure.annual_ctc_amount` (active) ÷ 365 — clearly labelled "estimated"
     in the UI, never silently blended with a real rate.
  3. Else **no monetary value** — report the row in the **days-based liability** total only; exclude it from the
     $-total; surface a data-quality "N employees have no resolvable rate" count.
  · priority: differentiator · **Must** (this fallback chain is the load-bearing design decision for this report —
    without it the feature can't ship as $-valued).
- **Only encashable leave types count toward $-liability** — SAP/Workday liability concepts are about leave that
  is contractually payable; NavERP's `LeaveType.encashable` boolean is the exact signal for "this converts to
  cash." Non-encashable balances (e.g. seeded Sick Leave) still count in the **days**-based liability (operational
  "how much leave is owed") but are excluded from the **$**-based liability. · priority: differentiator · **Must**
  — cheap, and prevents a misleading inflated dollar figure.
- **Fiscal-year-end / periodic snapshot framing** — seen in: SAP SuccessFactors (quarterly/annual Time Account
  Snapshots), Workday · priority: common · **Nice** — expose an `?as_of`/`?year` filter (reuse the `year` param
  design from the register report) rather than building a snapshot/history table (that would be a new model —
  out of scope for a derived-report pass).
- **GL posting of the liability accrual** — seen in: SAP SuccessFactors (Employee Central Payroll posts it to the
  balance sheet) · priority: differentiator · **Out-of-scope / integration-later** — this pass has no models and
  NavERP's Accounting module (Module 2) integration is a separate, later concern (would need a `JournalEntry`
  posting, not a report).

### Comp-off Report (earned/availed)
- **Comp-off earned from overtime worked** — seen in: greytHR ("Compensatory off... earned in exchange for
  working on a weekly off/holiday"), Darwinbox, Freshteam (bulk balance adjustment "to accommodate comp-offs") ·
  priority: table-stakes (as a concept) · source: `hrm.OvertimeRequest` where `payout_method="comp_leave"` and
  `status="approved"` — **Must**, with an explicit caveat: NavERP has **no stored comp-off day balance**; "earned"
  here means claimed-hours converted to an *estimated* day count (`hours_claimed / 8`, documented assumption,
  clearly labelled "est. days"), not a real ledger entry.
- **Comp-off availed (taken as leave)** — seen in: greytHR (dedicated COMPOFF tab), Zoho People (Leave Booked &
  Balance segments "compensatory off" as its own bucket) · priority: table-stakes (as a concept) · source: **data
  gap** — NavERP's seeded `LeaveType` catalog has no Comp-off entry and no boolean/flag marks a `LeaveType` as
  comp-off. Design: match by `LeaveType.name`/`code` `icontains "comp"` (case-insensitive heuristic) against the
  tenant's actual `LeaveType` catalog; if none matches, render an explicit empty-state ("No comp-off leave type
  configured — create a `LeaveType` (e.g. code `COMPOFF`) so availed comp-off leave can be reported") rather than
  silently reporting zero. · **Must** (the heuristic + empty state, not a new field).
- **Comp-off expiry tracking (lapses in 30–90 days if unused)** — seen in: greytHR, industry glossaries (Asanify,
  Superworks) · priority: common · **Out-of-scope** — NavERP has no expiry date anywhere in `LeaveAllocation`
  or `OvertimeRequest`; would require a new field/model. Flag for a future 3.10/3.11 enhancement, not this
  reports-only pass.
- **Net comp-off position (earned − availed) per employee** — synthesized from the above two, informational only
  (explicitly NOT a real tracked balance, since nothing links an approved comp-leave `OvertimeRequest` to a
  `LeaveAllocation` row today) · priority: differentiator · **Nice** — cheap to compute once both sides exist, but
  must be clearly labelled as an estimate/derived figure, not an authoritative balance.
- **Auto-provisioning: approving a comp-leave OT claim should credit a leave balance** — this is the *real* fix
  that would close the gap, but it is a **workflow/model change to 3.10/3.11**, not a report. · **Out-of-scope**
  for this pass — flagged prominently in Deferred so it isn't lost.

### Leave Trend (monthly/seasonal patterns)
- **Monthly leave-days-taken trend line (+ by leave-type stacked)** — seen in: Darwinbox, Freshteam, Keka (usage
  trends) · priority: table-stakes · source: `LeaveRequest` `status="approved"`, `TruncMonth("start_date")`,
  `Sum("days")` — exact `TruncMonth` pattern already used in `attendance_summary_report`/`overtime_report` ·
  **Must**.
- **By-department trend / rollup** — seen in: BambooHR (team/department slicing), Darwinbox · priority:
  table-stakes · source: `employee__employment__org_unit` · **Must**.
- **Seasonality (which calendar months spike, independent of year)** — seen in: Darwinbox ("AI tools identify
  seasonal leave patterns") · priority: differentiator · source: group by `month` component only
  (`ExtractMonth`/Python `.month` from `start_date`) summed across all years in range, not just the trailing-12
  trend line · **Nice** — the plain monthly trend line (Must, above) covers the common case; a dedicated
  month-of-year (Jan..Dec) seasonality view is a genuine differentiator worth adding as a second chart on the same
  page rather than skipping.
- **Absenteeism/leave-frequency by employee (repeat takers)** — seen in: Darwinbox (frequency of absences),
  BambooHR ("who is using or abusing time off") · priority: common · source: `LeaveRequest.objects.values(
  "employee").annotate(count=Count("id"), days=Sum("days"))`, top-N · **Must** (cheap, high signal, mirrors the
  existing `absenteeism_report`'s "frequent" top-10 pattern exactly).
- **Concurrent-absence peaks (how many people out on the same day)** — seen in: BambooHR/Deputy positioning
  (coverage planning) · priority: differentiator · source: a day-by-day sweep over `LeaveRequest` rows in range
  (start_date/end_date overlap count) — not a simple `.annotate()`, needs a small custom aggregation loop ·
  **Nice** — valuable but the most implementation-costly item in this catalog; bound it to the selected date range
  (already capped to reasonable windows by `_report_period`) to keep it O(days) not O(days × requests).
- **"Bradford Factor" absence-frequency scoring** — seen in referenced absence-management literature (surfaced via
  the Zoho/greytHR search, a UK-origin metric: `S² × D`) · priority: differentiator (niche) · **Out-of-scope** —
  belongs conceptually closer to 3.29 Absenteeism Report (already shipped) than 3.30 Leave Trend; not worth adding
  net-new here.

## Recommended build scope (this pass — views only, NO new models)

Mirror the 3.28/3.29 shape exactly: one `leave_reports_index` hub (5 KPI tiles) + 4 drill-in report views, all
`@tenant_admin_required`, all reusing `_report_period`/`_report_department`/`_dept_choices` where the metric is
naturally date-range/department scoped, plus a `year` selector where the metric is intrinsically year-scoped
(`LeaveAllocation.year`).

- **`leave_reports_index`** — 5 tiles (Leave Register / Leave Liability / Comp-off / Leave Trend, + an "On Leave
  Today" quick stat), same pattern as `hr_reports_index`/`attendance_reports_index`. URL `reports/leave/`.
- **`leave_register_report`** — filters: `?year` (default current year, dropdown sourced from distinct
  `LeaveAllocation.year` values, matching `leaveallocation_list`'s `current_year` convention), `?department`
  (via `_report_department`/`_dept_choices`), `?leave_type`. Grid: employee × leave_type — allocated,
  carried_forward, used (`_used_days_subquery()`), encashed_days, balance. Rollups: by department, by leave type.
  Secondary panel: "on leave today/this week" list. URL `reports/leave/register/`.
- **`leave_liability_report`** — filters: `?year` (defaults to current year, same convention as register),
  `?department`. Per-employee-per-leave-type rows: balance (days), resolved rate + its source
  (`encashment`/`estimated`/`none`), value ($, blank if unresolved). Two headline totals: total days liability
  (all leave types) and total $ liability (encashable leave types with a resolved rate only). Rollups: by
  department, by leave type. Data-quality line: count/% of rows with no resolvable rate. URL
  `reports/leave/liability/`.
- **`comp_off_report`** — filters: `?date_from`/`?date_to` (`_report_period`), `?department`. "Earned" panel: OT
  claims with `payout_method="comp_leave"`, `status="approved"` — count, total hours, est. days (`/8`), by
  employee/department, monthly trend. "Availed" panel: `LeaveRequest` rows against the heuristically-matched
  comp-off `LeaveType` (`icontains "comp"`) — days, by employee; explicit empty-state banner if no matching
  `LeaveType` exists for the tenant. Net position table (earned − availed, labelled "estimate"). URL
  `reports/leave/compoff/`.
- **`leave_trend_report`** — filters: `_report_period`, `?department`, `?leave_type`. Charts: (1) monthly
  leave-days trend (stacked by leave type, Chart.js, `TruncMonth`), (2) month-of-year seasonality (Jan..Dec summed
  across the range's years), (3) by-department bar. Tables: top-10 frequent leave-takers (mirrors
  `absenteeism_report`'s "frequent" pattern), top concurrent-absence peak dates (bounded sweep over the selected
  range). URL `reports/leave/trend/`.

All five views: `@tenant_admin_required`, tenant-scoped queries only, `?department`/`?leave_type` resolved
tenant-scoped (never trust a raw pk — same IDOR-safe pattern as `_report_department`), templates under
`templates/hrm/reports/` (`leave_index.html`, `leave_register.html`, `leave_liability.html`, `compoff.html`,
`leave_trend.html`).

## Deferred (later passes / integrations)
- **Comp-off as a first-class, tracked balance** (a `LeaveType.is_comp_off` flag or auto-provisioning a
  `LeaveAllocation` credit when a comp-leave `OvertimeRequest` is approved) — a 3.10/3.11 model/workflow change,
  not a reports-only pass. Until then, the Comp-off Report is necessarily heuristic/estimated.
- **Comp-off expiry tracking** (lapses after 30–90 days) — needs a new date field, not derivable from existing data.
- **Statutory leave-register PDF/Excel export** — export infrastructure is a separate concern across all NavERP
  reports, not specific to 3.30.
- **GL posting of accrued leave liability** (SAP SuccessFactors precedent: post to the balance sheet each fiscal
  period) — requires Module 2 Accounting integration (`JournalEntry`), out of scope for a derived HR report.
- **Bradford Factor scoring** — closer to 3.29 Absenteeism than 3.30 Leave Trend; not recommended for this pass.
- **A real, stored per-employee/per-leave-type pay rate** (vs. this pass's `LeaveEncashment`→`EmployeeSalaryStructure`
  fallback estimate) — would need 3.13 Payroll to expose a canonical daily rate; flag as a future refinement to
  the Liability report once that exists.
- **Predictive/AI seasonal forecasting** — belongs to 3.32 Analytics Dashboard, not a derived report in 3.30.
