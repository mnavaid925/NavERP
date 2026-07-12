# Research — Module 3: HRM — 3.29 Attendance Reports (hrm-3.29)

**Build context (confirmed from repo):** these are DERIVED, read-only, `@tenant_admin_required` report pages —
same pattern as 3.28 HR Reports (`apps/hrm/views.py:11920+`). **NO new models.** Reusable helpers already exist:
`_report_period(request)` (date_from/date_to, default trailing 12 months), `_report_department(request, tenant)`
(tenant-scoped, IDOR-safe `?department` resolver), `_dept_choices(tenant)`. Templates live flat under
`templates/hrm/reports/` (`hr_index.html`, `headcount.html`, `attrition.html`, `diversity.html`, `cost.html`,
`hiring.html`) with a shared page shell: page-header + breadcrumb, `filter-bar` card (date range + department
select), `stat-grid` KPI tiles, Chart.js `<canvas>` trend (12-month line), one-or-more `table-wrap` breakdown
tables, `empty-state` fallback. URL prefix so far: `reports/hr/...`; this pass should use `reports/attendance/...`.

**Source models confirmed in `apps/hrm/models.py`:**
- `AttendanceRecord` (`apps/hrm/models.py:1021`) — `employee` FK, `date`, `check_in`/`check_out` (TimeField),
  `hours_worked` (derived, `_recompute_hours()`), `shift` FK (nullable), `status` (`present/absent/half_day/
  on_leave/holiday/regularized`), `source`. Has `is_late()` — a display-only bool helper comparing check-in
  minutes-of-day vs. `shift.start_time + shift.grace_minutes` (no minutes-late value, no early-leave equivalent
  — both must be computed by the report).
- `Shift` (`apps/hrm/models.py:975`) — `start_time`, `end_time`, `grace_minutes` (default 15).
- `OvertimeRequest` (`apps/hrm/models.py:716`) — `employee`, `date`, `hours_claimed`, `multiplier` (default 1.50),
  `status` (`draft/pending/approved/rejected/cancelled`), `payout_method`. Has `overtime_pay_equivalent_hours`
  property = `hours_claimed × multiplier`. Docstring is explicit: **"No stored currency amount — there is no
  stable employee pay-rate source yet (3.13 Salary Structure)."** This is a deliberate design decision already
  made by the model's author — the 3.29 Overtime Report should respect it (hours-based cost proxy, not currency).
- `Timesheet`/`TimesheetEntry` (`apps/hrm/models.py:608`) — already reported on by
  `timesheet_utilization_report` (3.11, `apps/hrm/views.py:1678`, template
  `hrm/timetracking/utilization_report.html`, url `hrm:timesheet_utilization_report`) — billable ÷ total hours
  per employee over approved timesheets. **Must be reused/linked, not rebuilt.**
- `EmployeeSalaryStructure` (`apps/hrm/models.py:3415`) — `annual_ctc_amount` exists (used by 3.28's
  `cost_report`) but is annualized CTC, not an hourly rate; there's no standard hours-per-year divisor defined
  anywhere in the codebase — using it for OT currency cost would be an invented estimate, not a sourced fact.
- Department breakdowns elsewhere use `employee__employment__org_unit` (OrgUnit, kind="department") — same path
  this pass should use for `AttendanceRecord`/`OvertimeRequest` department filters.

## Leaders surveyed (with source links)
1. **UKG (Kronos)** — enterprise workforce management; Attendance Analysis/Incident/Action reports, points-based
   occurrence tracking (e.g. late-in = 0.5 point) — [Time & Attendance features](https://www.ukg.com/products/features/time-and-attendance), [Standard attendance reports](https://communityfiles.ukg.com/support/KOL/OnlineHelp-WorkforceDimensions/en-us/Content/Reports/StandardReports/Attendance/Attendance_Reports_intro.htm)
2. **Deputy** — shift-based scheduling/attendance for hourly/shift workforces; late reports, per-location/per-employee attendance, labor-cost/overtime trend reporting — [How to generate a late report](https://help.deputy.com/hc/en-au/articles/4755463280911-How-to-generate-a-late-report)
3. **Keka HR** — Indian-market HRMS; Attendance Analysis, graphical late-coming/early-going trend, "Negligence Reports" (no-shows/latecomers), Overtime summary (gross/effective/OT hours), penalization/loss-of-pay linkage — [Using Attendance Reports](https://help.keka.com/hc/en-us/articles/39946612402193-Using-Attendance-Reports), [Attendance Management System](https://www.keka.com/attendance-management-system)
4. **greytHR** — Indian-market HRMS; attendance/leave reports, late-coming & OT tracking, Session Details card (First-In/Last-Out/Late-In-hrs/Early-Out-hrs), monthly Summary tab (avg work hours, absent days, OT hours) — [View attendance and leave reports](https://admin-help.greythr.com/admin/answers/ag34hqQ9RUSHxnCcbTn6ag), [Attendance management guide](https://www.greythr.com/guides/guide-to-attendance-management/)
5. **BambooHR** — SMB HRIS; automatic overtime calculation, absenteeism reports/dashboards with manager alerts, Who's-Out calendar — [Time & Attendance](https://www.bamboohr.com/platform/time-and-attendance/)
6. **Zoho People / Zoho Payroll** — early/late arrival reports, muster roll, Attendance Overtime Report broken out by regular/weekend/holiday OT, GPS-tagged check-in/out, regularization workflow — [Attendance Reports](https://help.zoho.com/portal/en/kb/people/administrator-guide/reports/articles/attendance-reports), [Overtime Policy](https://help.zoho.com/portal/en/kb/people/administrator-guide/attendance-management/settings/articles/overtime-policy-zoho-people-attendance-service)
7. **Rippling** — pre-built reports on overtime/absenteeism/coverage, labor-cost breakdown by location/role/project, custom dashboards — [Time & Attendance](https://www.rippling.com/products/hr/time-and-attendance)
8. **Darwinbox** — enterprise APAC HCM; BI dashboards surfacing absenteeism + overtime patterns, geo-fenced biometric attendance, live view of late entries/early exits/absence trends — [Attendance dashboard](https://darwinbox.com/blog/attendance-system-dashboard), [Advanced time & attendance features](https://blog.darwinbox.com/advanced-time-attendance-management-features)
9. **Workday Absence Management** — Bradford Factor & Weighted Bradford Factor scoring for chronic-absence detection, absence-episode calendar highlighting overtime worked around absences — [Workday Absence Management datasheet](https://www.workday.com/content/dam/web/en-us/documents/datasheets/workday-absence-management-datasheet-en-us.pdf), [Bradford Factor — Wikipedia](https://en.wikipedia.org/wiki/Bradford_Factor)
10. **ADP Workforce Now** — Actual-vs-Scheduled Hours reports, "Approaching Weekly Overtime" alerts, Labor Tracking dashboard tile by department, attendance-history trend spotting — [Time & attendance solutions](https://www.adp.com/what-we-offer/time-and-attendance.aspx), [Employee Attendance Guide](https://www.adp.com/resources/articles-and-insights/articles/e/employee-attendance.aspx)

(Bradford Factor formula cross-checked against [HRLocker](https://www.hrlocker.com/bradford-factor/) and
[Davidson Morris](https://www.davidsonmorris.com/bradford-factor/): `B = S² × D` where `S` = number of absence
spells, `D` = total absent days in the period.)

## Feature catalog by report family

### 3.29 Attendance Summary
- **Status breakdown (present/absent/half-day/on-leave/holiday counts)** — period roll-up of each status ·
  seen in: Keka, greytHR, Zoho People, ADP · priority: table-stakes · spine: reuse `hrm.AttendanceRecord.status`
  (`Count` grouped by status, tenant+period+department scoped) · buildable now
- **Attendance % (present-days ÷ scheduled-days)** — headline KPI · seen in: Keka, greytHR, ADP, UKG · priority:
  table-stakes · spine: reuse `AttendanceRecord` · buildable now, **with a defined denominator** — no
  scheduled-days/shift-calendar table exists in NavERP, so "scheduled days" must be derived as the count of
  `AttendanceRecord` rows in the period excluding `status='holiday'` (i.e., days that were actually tracked),
  not a theoretical calendar of working days. Flag this substitution explicitly in the report UI/help text.
- **Daily muster roll (single-day snapshot grid)** — one row per employee for a chosen date · seen in: Zoho
  People, Keka · priority: common · spine: reuse `AttendanceRecord` · buildable now but adds a second
  UI mode (date picker vs. range) — Nice, not Must, for this pass
- **Weekly/monthly rollup + trend chart** — bucketed attendance over time · seen in: UKG, ADP, Darwinbox ·
  priority: table-stakes · spine: reuse `AttendanceRecord` · buildable now (monthly bucket, mirrors the
  existing 12-month `trendChart` pattern in `headcount.html`); weekly bucketing is Nice (extra grouping logic)
- **By-department / by-designation breakdown** — attendance % or status counts sliced by org unit · seen in:
  all 10 · priority: table-stakes · spine: reuse `OrgUnit` via `employee__employment__org_unit` (same path as
  3.28) · buildable now
- **Source breakdown (web/mobile/biometric/manual)** — punch-source mix · seen in: Darwinbox (biometric/geo),
  UKG · priority: differentiator · spine: reuse `AttendanceRecord.source` · buildable now, low priority (Nice)

### 3.29 Late/Early Departure
- **Late-arrival count + avg minutes late per employee** — seen in: Keka (graphical late/early trend), greytHR
  (Late-In-hrs field), UKG (points: late-in = 0.5), ADP · priority: table-stakes · spine: reuse
  `AttendanceRecord.check_in` + `Shift.start_time`/`grace_minutes` · buildable now — **must compute in Python
  per row** (minutes-of-day comparison), mirroring the existing `AttendanceRecord.is_late()` /
  `_recompute_hours()` pattern (raw TimeField arithmetic isn't portable across SQLite/Postgres at the DB-query
  level); records with no `shift` FK assigned cannot be classified and must be excluded (flag as a data gap in
  the UI: "N records skipped — no shift assigned").
- **Early-departure count + avg minutes early** — symmetric metric to late-arrival, comparing `check_out` against
  `shift.end_time` · seen in: greytHR (Early-Out-hrs), Keka · priority: table-stakes · spine: reuse
  `AttendanceRecord.check_out` + `Shift.end_time` · buildable now — **no `AttendanceRecord` model method exists
  for this today**; the report computes it directly (same minutes-of-day pattern, no `grace_minutes` symmetric
  field exists for early-leave — use 0 grace or reuse `grace_minutes` for both, note the choice explicitly)
- **Top-offenders list (by employee, sorted by count/avg-minutes)** — seen in: Keka "Negligence Reports", UKG
  points-tracking · priority: common · spine: reuse `AttendanceRecord` · buildable now
- **Day-of-week lateness trend** — is Monday/Friday worse? · seen in: UKG, ADP (trend-spotting) · priority:
  differentiator · spine: reuse `AttendanceRecord.date.weekday()` (Python-side bucket, 7 bars) · buildable now
- **Points/occurrence-based discipline tracking (e.g. late-in = 0.5pt, no-show = 1pt)** — escalation trigger
  system · seen in: UKG Kronos · priority: differentiator · spine: would need a new points/policy table ·
  out-of-scope this pass (policy-engine feature, not a report)
- **Compensation-linked penalization / loss-of-pay for lateness** — seen in: Keka · priority: differentiator ·
  spine: needs payroll deduction rule linkage (3.13/3.31) · integration/later

### 3.29 Absenteeism Report
- **Absence rate (absent-days ÷ scheduled-days)** — seen in: all 10 (universal metric) · priority: table-stakes
  · spine: reuse `AttendanceRecord.status='absent'`, same derived-denominator approach as Attendance Summary ·
  buildable now
- **Frequent-absentee list** — employees ranked by absence count/rate over the period · seen in: Keka
  (Negligence Reports), BambooHR, Darwinbox, ADP · priority: table-stakes · spine: reuse `AttendanceRecord` ·
  buildable now
- **Bradford Factor (B = S² × D)** — weights frequent short absences more heavily than one long absence; `S` =
  number of absence "spells" (runs of consecutive `status='absent'` dates), `D` = total absent days · seen in:
  Workday, and referenced broadly across HR-analytics vendors (Dayforce, edays, HRLocker) as an industry-standard
  formula · priority: differentiator · spine: reuse `AttendanceRecord` — spell-detection is pure Python (sort an
  employee's absent dates, break into consecutive-day runs) · buildable now (no new model, no integration), but
  nontrivial logic — treat as Nice, include if time allows, otherwise defer
- **By-department absence-rate breakdown** — seen in: all 10 · priority: table-stakes · spine: reuse `OrgUnit`
  path · buildable now
- **Monthly/seasonal absence trend** — seen in: ADP, Darwinbox, UKG · priority: common · spine: reuse
  `AttendanceRecord` (12-month bucketed count, same chart pattern as Attendance Summary) · buildable now
- **Absence-reason / leave-type breakdown** — seen in: Workday, ADP · priority: common · spine: this needs
  `hrm.LeaveRequest.leave_type`, not `AttendanceRecord` (whose `on_leave` status doesn't carry a reason) —
  cross-model join is possible but adds scope; **defer to 3.30 Leave Reports**, which already owns leave data
- **Return-to-work / absence-trigger workflow (auto-flag at N occurrences)** — seen in: Workday · priority:
  differentiator · spine: would need a policy/threshold config · out-of-scope this pass (display the ranked
  list; let the admin apply judgment — no auto-triggered workflow)

### 3.29 Overtime Report
- **Total OT hours (claimed + multiplier-weighted "pay-equivalent" hours)** — seen in: all 10 · priority:
  table-stakes · spine: reuse `OvertimeRequest.hours_claimed` and the existing
  `overtime_pay_equivalent_hours` property (`hours_claimed × multiplier`) · buildable now — this is the
  **primary "cost" proxy** given the model's own explicit deferral of a currency amount
- **By-employee / by-department OT breakdown** — seen in: Rippling (by location/role/project), Keka, ADP (Labor
  Tracking tile) · priority: table-stakes · spine: reuse `OvertimeRequest` + `employee__employment__org_unit` ·
  buildable now
- **OT by category (regular/weekend/holiday OT)** — seen in: Zoho People Attendance Overtime Report · priority:
  common · spine: would need to cross-reference `OvertimeRequest.date` against `PublicHoliday`/weekday to bucket
  — buildable now as a derived classification (no new field), Nice for this pass
- **Approaching-overtime-threshold alert** — flags employees nearing a weekly OT cap before it's incurred · seen
  in: ADP ("Approaching Weekly Overtime") · priority: differentiator · spine: needs a policy threshold + proactive
  alerting (not a report) · out-of-scope this pass
- **OT trend over time (monthly)** — seen in: Rippling, Darwinbox, ADP · priority: common · spine: reuse
  `OvertimeRequest.date` (12-month bucket, same chart pattern) · buildable now
- **OT status mix (draft/pending/approved/rejected/cancelled)** — how much claimed OT is actually approved · seen
  in: implied by all approval-workflow vendors (Keka, Zoho, greytHR) · priority: common · spine: reuse
  `OvertimeRequest.status` · buildable now
- **Currency OT cost (hours × multiplier × pay rate)** — seen in: UKG, Rippling, ADP (labor-cost dashboards) ·
  priority: common in the market, but **out-of-scope this pass** — `OvertimeRequest`'s own docstring states
  there is no stable per-employee pay-rate source; `EmployeeSalaryStructure.annual_ctc_amount` is annualized CTC
  with no standard hours-per-year divisor defined anywhere in the codebase, so converting it to an hourly rate
  would be an invented number, not a sourced fact. Defer until 3.13/3.31 payroll defines an authoritative hourly
  rate; until then report **hours and pay-equivalent hours only**, clearly labeled as a non-currency proxy.

### 3.29 Utilization Report
- **Billable ÷ total hours per employee** — already built: `hrm.timesheet_utilization_report` (3.11,
  `apps/hrm/views.py:1678`, template `hrm/timetracking/utilization_report.html`, url
  `hrm:timesheet_utilization_report`) computes exactly this from `TimesheetEntry` (`is_billable` sum ÷ total sum)
  over approved `Timesheet`s · seen in: Rippling, Deputy (labor-cost/coverage), Darwinbox ("revenue per staff")
  · priority: table-stakes · spine: reuse `hrm.Timesheet`/`TimesheetEntry` · **DO NOT REBUILD** — the 3.29
  "Utilization Report" bullet in NavERP.md should be satisfied by linking to the existing 3.11 report, not a
  new view
- **Worked-vs-scheduled hours** — seen in: ADP (Actual vs Scheduled Hours reports), UKG · priority: common ·
  spine: "scheduled hours" has no source table in NavERP (no shift-roster/scheduling model yet); "worked hours"
  can be sourced from `AttendanceRecord.hours_worked` — a true worked-vs-scheduled comparison is out-of-scope
  until a scheduling model exists; note this as a data gap rather than attempting a derived scheduled-hours proxy
- **Productivity/output metrics (revenue-per-employee, tasks completed)** — seen in: Darwinbox · priority:
  differentiator · spine: none — needs Project Management (Module 7) data · integration/later

## Recommended report views (this pass — no new models)

All views: `@tenant_admin_required` (mirrors 3.28 — company-wide aggregates, not self-service), tenant-scoped,
filters via the existing `_report_period`/`_report_department`/`_dept_choices` helpers, templates under the
existing flat `templates/hrm/reports/` folder (same convention as `headcount.html`/`attrition.html`), URLs under
`reports/attendance/...` in `apps/hrm/urls.py`.

- **`attendance_reports_index`** [GET `reports/attendance/`] — landing page with 5 KPI tiles (mirrors
  `hr_reports_index`): current-period Attendance %, Late-arrival count, Absent-days count, Total OT hours, and an
  overall Utilization % (lightweight aggregate over approved `TimesheetEntry` — reuses the 3.11 query shape but
  computes only the headline number; the tile links out to `hrm:timesheet_utilization_report`, not a new page).
  Template: `hrm/reports/attendance_index.html`.
- **`attendance_summary_report`** [GET `reports/attendance/summary/`] — filters: date range, department. Reports:
  status-count breakdown (present/absent/half_day/on_leave/holiday/regularized), attendance % (derived-denominator
  as above), by-department breakdown table, 12-month monthly trend chart of attendance %. Source:
  `AttendanceRecord`. Template: `hrm/reports/attendance_summary.html`.
- **`late_early_report`** [GET `reports/attendance/late-early/`] — filters: date range, department. Reports:
  late-arrival count + avg minutes late, early-departure count + avg minutes early, top-offenders table (by
  employee), day-of-week trend chart. Source: `AttendanceRecord.check_in`/`check_out` + `Shift.start_time`/
  `end_time`/`grace_minutes`, computed per-row in Python (mirrors `AttendanceRecord.is_late()`). Records without
  a `shift` are excluded and counted separately as a "no shift assigned" caveat line. Template:
  `hrm/reports/late_early.html`.
- **`absenteeism_report`** [GET `reports/attendance/absenteeism/`] — filters: date range, department. Reports:
  absence rate, by-department breakdown, frequent-absentee ranked list, 12-month absence-count trend, and
  (if time allows) a Bradford Factor column on the ranked list (`S²×D` from consecutive-day absence spells).
  Source: `AttendanceRecord.status='absent'`. Template: `hrm/reports/absenteeism.html`.
- **`overtime_report`** [GET `reports/attendance/overtime/`] — filters: date range, department, status (default
  approved). Reports: total hours claimed + total pay-equivalent hours (`hours_claimed × multiplier`), by-employee
  and by-department breakdown, status mix, 12-month OT-hours trend. Source: `OvertimeRequest`. Explicitly
  hours-based, no currency figure (see data gap below). Template: `hrm/reports/overtime.html`.
- **Utilization Report** — no new view. `attendance_reports_index` links its 5th tile to the existing
  `hrm:timesheet_utilization_report` (3.11). Optionally add a "View full utilization report →" link from the
  index page; do not duplicate the computation.

## Deferred (later passes / integrations)

- **Daily muster-roll snapshot grid** (single-day view) — Nice-to-have UI mode; the range-based summary report
  covers the Must-have; add a `?date=` single-day toggle later if requested.
- **Points/occurrence-based discipline tracking (UKG-style)** and **compensation-linked lateness penalization**
  (Keka-style) — both need a new policy/rules table and payroll-deduction linkage (3.13/3.31) — out of scope for
  a read-only report pass.
- **Approaching-overtime-threshold proactive alerts** (ADP-style) — needs a notification/policy engine, not a
  report.
- **Currency OT cost** (`hours × multiplier × pay rate`) — deferred until 3.13/3.31 payroll defines an
  authoritative per-employee hourly rate; `EmployeeSalaryStructure.annual_ctc_amount` alone is not a reliable
  source (annualized, no standard divisor).
- **Worked-vs-scheduled-hours comparison** (ADP/UKG-style) — "scheduled hours" has no source table (no shift
  roster/scheduling model yet); revisit once a scheduling model exists.
- **Absence-reason/leave-type breakdown** — belongs to 3.30 Leave Reports (`hrm.LeaveRequest.leave_type`), not
  3.29's `AttendanceRecord`.
- **Return-to-work workflow / auto-triggers at N occurrences** (Workday-style) — policy-engine feature, not a
  report.
- **Productivity/output metrics (revenue-per-employee, task-completion rate)** (Darwinbox-style) — needs
  Project Management (Module 7) data, not available yet.
