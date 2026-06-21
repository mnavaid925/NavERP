# Research — Module 3: Human Resource Management (hrm)

## Leaders surveyed (with source links)

1. **Workday HCM** — enterprise HCM suite covering global HR, payroll, talent, and people analytics in one platform — https://www.workday.com/en-us/products/human-capital-management/human-resource-management.html
2. **SAP SuccessFactors** — large-enterprise HCM with deep Employee Central, performance, learning, and succession modules — https://talenteam.com/products/sap-successfactors-hcm-suite/
3. **BambooHR** — SMB-focused HRIS: employee records, ATS, onboarding checklists, e-signatures, time-off, and payroll — https://www.bamboohr.com/platform/
4. **ADP Workforce Now** — all-in-one payroll, time & attendance, benefits, talent, and compliance platform for mid-market — https://www.adp.com/what-we-offer/products/adp-workforce-now/capabilities.aspx
5. **Gusto** — SMB payroll-first HR platform with unlimited payroll runs, automated tax filing, benefits, time tracking — https://gusto.com/product
6. **Rippling** — unified HR + IT + Finance HRIS with 650+ integrations, automated onboarding/offboarding, custom PTO — https://www.rippling.com/products/hr/hris
7. **Zoho People** — mid-market HRMS with attendance, leave, shift management, performance OKRs, and Zoho Payroll sync — https://www.zoho.com/people/features.html
8. **Paycom** — single-database HCM with employee-driven payroll (Beti), self-service, position management, LMS — https://www.paycom.com/software/
9. **Deel** — global employment platform: HRIS, EOR, contractor management, multi-currency payroll in 150+ countries — https://www.deel.com/solutions/hr/
10. **UKG Pro** — enterprise workforce management with AI scheduling, global payroll (160+ countries), and compliance — https://www.ukg.com/products/ukg-pro
11. **Frappe HRMS** — open-source HRMS: employee lifecycle, shifts, leave, payroll tax, expense, appraisals — https://frappe.io/hr

---

## Feature catalog by sub-module

### 3.1 Employee Management

- **Centralized Employee Database** — single record per employee with personal info, contact details, emergency contacts, job history, salary history, and signed documents · seen in: Workday, BambooHR, Rippling, ADP, Zoho People, Paycom, Gusto, Frappe HRMS · priority: table-stakes · spine: reuses `core.Party` (employee PartyRole) + extends `core.Employment` (job_title, hired_on, status) + new HRM-owned `EmployeeProfile` for extended HR fields · buildable now
- **Employee Directory with search/filter** — searchable list by name, department, designation, status with profile cards · seen in: all 10 products · priority: table-stakes · spine: reuses `core.Party` + `core.Employment`; `EmployeeProfile` adds employee_number, gender, date_of_birth, blood_group, nationality · buildable now
- **Employee Lifecycle Events** — hire, transfer, promotion, demotion, separation tracked as status changes with effective dates · seen in: Workday, SAP SuccessFactors, Rippling, ADP, Zoho People, Paycom · priority: table-stakes · spine: reuses `core.Employment` (status field); new `EmployeeEvent` table for history/audit · buildable now
- **Document Attachment** — store ID proofs, contracts, certifications, offer letters against employee records · seen in: BambooHR, Rippling, Paycom, Zoho People, Frappe HRMS · priority: common · spine: reuses `core.Document` (GenericFK) · buildable now
- **Employee Self-Service Portal** — employees update personal info, view payslips, apply leave, download documents · seen in: all 10 products · priority: table-stakes · spine: reuses `core.Party` + `core.Employment`; rendered by HRM views filtered to `request.user.party` · buildable now

### 3.2 Organizational Structure

- **Department Management** — create/edit departments with department heads and cost centers · seen in: all 10 products · priority: table-stakes · spine: reuses `core.OrgUnit` (kind=department); `Designation` model adds new HRM table for job grades · buildable now
- **Designation / Job Title Hierarchy** — job titles with grade levels and salary bands attached · seen in: Workday, SAP SuccessFactors, ADP, Zoho People, Paycom, Frappe HRMS · priority: table-stakes · spine: new HRM table `Designation` (name, grade, department→OrgUnit) · buildable now
- **Org Chart Visualization** — visual hierarchy showing reporting lines · seen in: BambooHR, Workday, SAP SuccessFactors, Zoho People, Rippling · priority: common · spine: derived from `core.Employment.manager` PartyRelationship; rendered as tree in templates · buildable now (tree rendering via Django template recursion)
- **Cost Center Mapping** — link employees/departments to cost centers for expense allocation · seen in: Workday, SAP SuccessFactors, ADP, Zoho People · priority: common · spine: reuses `core.OrgUnit` (kind=cost_center); `Employment` references OrgUnit already · buildable now

### 3.3 Employee Onboarding

- **Onboarding Checklist/Task Templates** — predefined task lists (IT setup, document collection, orientation) assigned to new hires · seen in: BambooHR, Rippling, ADP, Gusto, Workday, Frappe HRMS · priority: table-stakes · spine: new HRM table `OnboardingTask` (employee→EmployeeProfile, task_name, due_date, assigned_to, status) · buildable now
- **Document Collection & E-Signature** — digital form collection and e-signature for contracts and NDAs · seen in: BambooHR, Rippling, Gusto, Paycom · priority: common · spine: reuses `core.Document` (GenericFK to OnboardingTask or EmployeeProfile) · integration/later (e-signature provider)
- **Pre-boarding** — actions completed before day-1 (account creation, equipment request) · seen in: Workday, SAP SuccessFactors, Rippling, Gusto · priority: common · spine: flag on `OnboardingTask` (is_preboarding=True) · buildable now

### 3.4 Employee Offboarding

- **Resignation & Notice Period Management** — resignation submission, approval, notice period calculation · seen in: Zoho People, Frappe HRMS, SAP SuccessFactors, Workday · priority: common · spine: new HRM table `SeparationRequest` (employee, separation_type, last_working_day, status) · buildable now
- **Exit Interview** — structured questionnaire linked to employee separation · seen in: Zoho People, BambooHR, Frappe HRMS · priority: common · spine: new HRM table `ExitInterview` (separation→SeparationRequest, responses JSON, conducted_by) · buildable now
- **Clearance Process** — asset return tracking, department sign-offs · seen in: Zoho People, Frappe HRMS, SAP SuccessFactors · priority: common · spine: reuses asset FK + new `ClearanceItem` through table · deferred (needs Asset module)
- **Full & Final Settlement** — compute outstanding salary, leave encashment, deductions on exit · seen in: Zoho People, Frappe HRMS, ADP · priority: common · spine: coordinates with PayrollRun (accounting) and LeaveBalance · deferred to payroll pass

### 3.5 Job Requisition (Recruitment)

- **Job Posting / Requisition** — create open positions with description, headcount, salary band, department · seen in: BambooHR, Workday, SAP SuccessFactors, ADP, Paycom, Rippling · priority: table-stakes · spine: new HRM table `JobRequisition` (title, department→OrgUnit, designation→Designation, headcount, status, posted_on) · buildable now
- **Approval Workflow for Requisition** — multi-level approval before posting externally · seen in: Workday, SAP SuccessFactors, ADP, Paycom · priority: common · spine: status workflow on `JobRequisition` (draft→approved→published→closed) · buildable now

### 3.6 Candidate Management

- **Candidate Profile & Application Tracking** — capture applicant details, resume, applied position, stage · seen in: BambooHR, ADP, Paycom, Rippling, SAP SuccessFactors · priority: table-stakes · spine: new HRM table `Candidate` (name, email, phone, applied_for→JobRequisition, source, stage, status) · buildable now
- **Resume Parsing** — auto-extract name/email/experience from uploaded resume · seen in: SAP SuccessFactors, ADP, Rippling, Zoho People · priority: differentiator · spine: computed fields on `Candidate`; needs third-party parser API · integration/later
- **Candidate Pipeline / Stages** — Kanban-style stage progression (Applied→Screened→Interviewed→Offered→Hired) · seen in: BambooHR, Rippling, ADP, Zoho People · priority: table-stakes · spine: `status` field with choices on `Candidate` · buildable now

### 3.7 Interview Process

- **Interview Scheduling** — schedule rounds with panel members, assign interviewers · seen in: BambooHR, Workday, SAP SuccessFactors, Zoho People, Paycom · priority: common · spine: new HRM table `InterviewRound` (candidate→Candidate, round, scheduled_at, interviewers M2M, status) · buildable now
- **Interview Feedback / Scorecard** — structured rating form per interviewer per round · seen in: BambooHR, ADP, Paycom, Rippling · priority: common · spine: new HRM table `InterviewFeedback` (round→InterviewRound, interviewer→User, rating, recommendation, notes) · buildable now

### 3.8 Offer Management

- **Offer Letter Generation** — template-based offer letter with variable compensation · seen in: BambooHR, Rippling, ADP, Paycom · priority: table-stakes · spine: new HRM table `OfferLetter` (candidate→Candidate, gross_salary, joining_date, status, generated_at) · buildable now
- **Offer Approval Workflow** — multi-level approval before sending to candidate · seen in: Workday, SAP SuccessFactors, ADP · priority: common · spine: status workflow on `OfferLetter` (draft→pending_approval→approved→sent→accepted/declined) · buildable now

### 3.9 Attendance Management

- **Daily Attendance Record** — check-in/check-out capture with source (web, mobile, biometric) · seen in: all 10 products · priority: table-stakes · spine: new HRM table `AttendanceRecord` (employee→EmployeeProfile, date, check_in, check_out, hours_worked, status, source) · buildable now
- **Shift Management** — define shifts (name, start_time, end_time, tolerance), assign to employees · seen in: Zoho People, ADP, UKG Pro, Frappe HRMS, SAP SuccessFactors · priority: table-stakes · spine: new HRM table `Shift` + `ShiftAssignment` (employee, shift, effective_from, effective_to) · buildable now
- **Attendance Regularization** — employee requests correction for missed/incorrect punches · seen in: Zoho People, Frappe HRMS, ADP · priority: common · spine: status field on `AttendanceRecord` + new `RegularizationRequest` · buildable now
- **Geofenced / IP-Restricted Check-in** — restrict punch-in to office IP or GPS radius for field staff · seen in: Zoho People, ADP, UKG Pro, Rippling · priority: differentiator · spine: `check_in_location` JSON field on `AttendanceRecord` · integration/later (requires mobile/GPS)
- **Attendance Calendar View** — monthly color-coded grid (present/absent/leave/half-day) · seen in: Zoho People, BambooHR, Frappe HRMS, ADP · priority: table-stakes · spine: derived from `AttendanceRecord` + `LeaveRequest` · buildable now (template rendering)

### 3.10 Leave Management

- **Leave Types** — configurable leave types (Annual, Sick, Casual, Unpaid, Comp-Off) with accrual rules · seen in: all 10 products · priority: table-stakes · spine: new HRM table `LeaveType` (name, is_paid, is_annual, accrual_per_month, max_carry_forward, encashable) · buildable now
- **Leave Policy** — per-department / per-designation leave entitlement rules · seen in: Zoho People, Workday, SAP SuccessFactors, ADP, Frappe HRMS · priority: common · spine: new HRM table `LeavePolicy` (leave_type, org_unit, designation, annual_quota) · buildable now
- **Leave Request** — apply/cancel/modify leave with manager approval workflow · seen in: all 10 products · priority: table-stakes · spine: new HRM table `LeaveRequest` (employee, leave_type, start_date, end_date, days, reason, status workflow: draft→pending→approved/rejected) · buildable now
- **Leave Balance Tracking** — real-time balance per employee per leave type · seen in: all 10 products · priority: table-stakes · spine: new HRM table `LeaveAllocation` (employee, leave_type, year, allocated_days, used_days derived) · buildable now
- **Holiday Calendar** — national/company holidays that auto-block leave calculations · seen in: all 10 products · priority: table-stakes · spine: new HRM table `PublicHoliday` (tenant, date, name, applies_to_all) · buildable now
- **Leave Calendar / Team View** — see who is on leave in the team · seen in: BambooHR, Zoho People, Gusto, Rippling · priority: common · spine: derived from approved `LeaveRequest` rows · buildable now (template view)
- **Leave Carry Forward & Encashment** — auto-carry forward unused days and compute encashment on demand · seen in: Zoho People, Frappe HRMS, SAP SuccessFactors · priority: differentiator · spine: field `max_carry_forward` on `LeaveType` + year-end batch job · deferred (batch jobs)

### 3.11 Time Tracking

- **Timesheet (Daily/Weekly)** — employee logs hours per day, optionally against project/task · seen in: Workday, Frappe HRMS, Zoho People, ADP, Paycom · priority: table-stakes · spine: new HRM table `Timesheet` (employee, week_start, status) + `TimesheetEntry` (timesheet, date, project, task_desc, hours, is_billable) · coordinates with accounting Job Costing (`Project` already in accounting) · buildable now
- **Overtime Tracking** — flag hours beyond shift duration; approval + OT rate calculation · seen in: ADP, UKG Pro, Zoho People, Paycom, Frappe HRMS · priority: common · spine: `is_overtime` + `ot_hours` on `TimesheetEntry` or derived from AttendanceRecord vs Shift · buildable now
- **Timesheet Approval Workflow** — manager approval before hours are locked · seen in: all surveyed products · priority: table-stakes · spine: `status` workflow on `Timesheet` (draft→submitted→approved/rejected) · buildable now

### 3.12 Holiday Management

- **Holiday Calendar CRUD** — define national, regional, and company-specific holidays per year · seen in: all products · priority: table-stakes · spine: `PublicHoliday` model (tenant, date, name, location/region optional) · buildable now (captured under 3.10)
- **Floating/Optional Holidays** — holidays from which employee can choose N per year · seen in: Zoho People, Frappe HRMS, SAP SuccessFactors · priority: differentiator · spine: flag on `PublicHoliday` (is_optional=True) + `OptionalHolidaySelection` (employee, holiday) · deferred

### 3.13 Salary Structure

- **Pay Components / Earnings** — define earnings (Basic, HRA, Allowances) and deductions (PF, ESI, Tax) as component types · seen in: all products · priority: table-stakes · spine: new HRM table `SalaryComponent` (name, component_type: earning/deduction, is_statutory, formula_or_amount) · buildable now
- **Salary Structure Template** — grade-wise templates that combine components with amounts/formulas · seen in: Zoho People, Frappe HRMS, SAP SuccessFactors, ADP, Paycom · priority: table-stakes · spine: new HRM table `SalaryStructure` (name, components M2M with amounts) + `EmployeeSalary` (employee, structure, effective_from, gross_ctc) · buildable now
- **Variable Pay / Bonus** — ad-hoc or performance-linked additional payments per pay cycle · seen in: all products · priority: common · spine: `SalaryComponent` (component_type=bonus) + additional salary entry on `PayrollEntry` · buildable now

### 3.14 Payroll Processing — COORDINATION WITH ACCOUNTING

**CRITICAL NOTE:** `accounting.PayrollRun` (PRUN-#####) already exists in `apps/accounting/models_advanced.py`. It is the accounting-side GL posting record: period_start/end, pay_date, headcount, gross_wages, employee_tax, employer_tax, benefits, deductions, net_pay, status (draft/posted), journal_entry FK. HRM must NOT duplicate this model.

**HRM's role in payroll:** HRM owns the per-employee computation detail (individual salary slips, individual deductions). Accounting owns the aggregate GL journal posting.

**Coordination pattern:** HRM `PayrollEntry` (per-employee) → aggregates roll up into `accounting.PayrollRun` (period-level) → `accounting.PayrollRun.post()` creates `JournalEntry`.

- **HRM PayrollEntry (per-employee)** — individual salary computation for one employee in one pay period: component breakdown (earnings/deductions per SalaryComponent), gross, deductions, net · seen in: Frappe HRMS, Zoho People, ADP, Paycom, Gusto · priority: table-stakes · spine: new HRM table `PayrollEntry` (employee→EmployeeProfile, payroll_run→accounting.PayrollRun, period_start, period_end, gross, deductions, net, status) · buildable now
- **Payroll Approval Workflow** — multi-level approval before posting/disbursement · seen in: all products · priority: table-stakes · spine: status workflow on `PayrollEntry` (draft→verified→approved→paid) · buildable now
- **Salary Slip / Payslip Generation** — per-employee payslip with full breakdown · seen in: all products · priority: table-stakes · spine: derived from `PayrollEntry` + its component lines; render as PDF template · buildable now
- **Arrears Calculation** — retroactive pay adjustment when salary is changed mid-period · seen in: Zoho People, Frappe HRMS, SAP SuccessFactors, ADP · priority: common · spine: `is_arrears` flag + `arrears_for_period` on `PayrollEntry` · deferred (complex calculation)
- **Payroll Reconciliation** — gross-to-net verification across all employees · seen in: all products · priority: common · spine: derived from aggregate of `PayrollEntry` rows vs `accounting.PayrollRun` totals · buildable now (report view)

### 3.15 Statutory Compliance

- **PF / Social Security Contribution Tracking** — statutory contribution per employee per month · seen in: Zoho People, Frappe HRMS, ADP, Gusto, Paycom · priority: common · spine: `SalaryComponent` with `is_statutory=True`; computed on `PayrollEntry` line · buildable now (via salary structure)
- **Tax Deduction at Source (TDS/Withholding)** — tax component on `PayrollEntry` lines · seen in: all products · priority: table-stakes · spine: `SalaryComponent` (component_type=tax_deduction) · buildable now
- **Statutory Reporting** — monthly/quarterly compliance register (PF challan, ESI returns) · seen in: Zoho People, Frappe HRMS, ADP, Paycom · priority: common · spine: derived from `PayrollEntry` rows filtered by component type · deferred (jurisdiction-specific)

### 3.16 Tax & Investment Declaration

- **Tax Regime Selection / Investment Declaration** — employee declares investments for tax computation · seen in: Zoho People, Frappe HRMS, ADP, Paycom · priority: differentiator (jurisdiction-specific) · spine: new HRM table `TaxDeclaration` (employee, fiscal_year, regime, declared_amount, proof_uploaded) · deferred (jurisdiction-specific)
- **Form 16 / Tax Certificate Generation** — annual tax certificate auto-generation · seen in: Zoho People, Frappe HRMS, Paycom · priority: differentiator · spine: derived from `PayrollEntry` tax components per fiscal year · integration/later

### 3.17 Payout & Reports

- **Payslip Email Distribution** — digital payslips distributed to employees · seen in: all products · priority: table-stakes · spine: derived from `PayrollEntry`; email action in views · integration/later (email provider)
- **Bank File / NACHA Export** — generate direct deposit file for bank upload · seen in: ADP, Gusto, Rippling, UKG Pro, Paycom · priority: common · spine: export view on `PayrollEntry` rows · integration/later (bank format)
- **Payment Register** — batch summary report of all employee net pays for a run · seen in: all products · priority: table-stakes · spine: aggregate view over `PayrollEntry` joined to `accounting.PayrollRun` · buildable now

### 3.18–3.21 Performance Management

- **Goal Setting / OKR Tracking** — define objectives and key results per employee/team per cycle · seen in: Workday, SAP SuccessFactors, Zoho People, BambooHR, Paycom · priority: common · spine: new HRM table `Goal` (employee, title, period, weight, progress_pct, status) · buildable now
- **Performance Review Cycle** — configurable review periods (annual/half-yearly/quarterly) with self-assessment + manager review · seen in: all products · priority: table-stakes · spine: new HRM table `PerformanceReview` (employee, reviewer, cycle_period, self_rating, manager_rating, overall_rating, status) · buildable now
- **360-Degree Feedback** — peer and subordinate ratings in addition to manager review · seen in: Workday, SAP SuccessFactors, BambooHR, Zoho People · priority: differentiator · spine: new HRM table `PeerFeedback` (review→PerformanceReview, rater→User, rating, comments) · deferred (complex M2M feedback flow)
- **Performance Improvement Plan (PIP)** — documented corrective action plan with milestones · seen in: Workday, SAP SuccessFactors, Zoho People, BambooHR · priority: common · spine: new HRM table `PIPlan` (employee, start_date, end_date, objectives, outcome) · deferred

### 3.22–3.24 Training & Learning Management

- **Training Calendar / Session Management** — schedule training sessions, assign employees · seen in: SAP SuccessFactors, ADP, Zoho People, Paycom · priority: common · spine: new HRM table `TrainingSession` (title, date, trainer, venue, capacity) + M2M `TrainingAttendance` · deferred (separate pass)
- **LMS / Course Content** — SCORM-based learning paths, assessments, certificates · seen in: Workday, SAP SuccessFactors, Paycom (Paycom Learning), Zoho People · priority: differentiator · spine: separate LMS tables · deferred (full LMS is separate pass)

### 3.25–3.27 Employee Self-Service

- **Self-Service Profile Update** — employees update address, phone, emergency contacts, bank details · seen in: all products · priority: table-stakes · spine: views filtered to `request.user.party` on `EmployeeProfile` / `core.ContactMethod` / `core.Address` · buildable now
- **Document Request** — employee requests experience letter, salary certificate, etc. · seen in: Zoho People, BambooHR, Frappe HRMS · priority: common · spine: new HRM table `DocumentRequest` (employee, request_type, status, generated_file) · deferred
- **Company Announcements** — HR broadcasts news and policy updates · seen in: Zoho People, BambooHR, ADP, Paycom · priority: common · spine: new HRM table `Announcement` (tenant, title, body, published_at, audience) · deferred

### 3.28–3.32 Reporting & Analytics

- **Headcount Report** — active employees, new joins, exits by department/period · seen in: all products · priority: table-stakes · spine: aggregate over `EmployeeProfile` + `core.Employment.status` + lifecycle events · buildable now
- **Leave Register / Summary** — leave availed, balance, absenteeism by employee/period · seen in: all products · priority: table-stakes · spine: aggregate over `LeaveRequest` + `LeaveAllocation` · buildable now
- **Attendance Summary Report** — daily/monthly presence, late arrivals, OT · seen in: all products · priority: table-stakes · spine: aggregate over `AttendanceRecord` · buildable now
- **Salary Register** — monthly payroll summary with gross/net per employee · seen in: all products · priority: table-stakes · spine: aggregate over `PayrollEntry` rows per `accounting.PayrollRun` · buildable now
- **Attrition / Turnover Report** — exit rates by department/period · seen in: Workday, ADP, Zoho People, BambooHR · priority: common · spine: aggregate over `SeparationRequest` vs headcount · buildable now
- **Predictive Analytics (Attrition, Flight Risk)** — ML-based turnover prediction · seen in: Workday, ADP, UKG Pro · priority: differentiator · spine: requires BI module + ML pipeline · deferred

### 3.33–3.35 Asset / Expense / Travel (HR-side)

- **HR Asset Allocation** — assign laptops, phones, ID cards to employees during onboarding · seen in: Zoho People, BambooHR, Frappe HRMS · priority: common · spine: coordinates with Module 11 `core.Asset` (custodian→Party already in spine ERD) · deferred (needs Asset module)
- **Expense Claims** — employee submits travel/meal expense with receipts · seen in: Frappe HRMS, Zoho People, ADP, Gusto · priority: common · spine: new HRM table `ExpenseClaim` (employee, date, category, amount, receipt, status) + posts to `accounting.JournalEntry` on approval · deferred (coordinate with accounting)

### 3.37 Compensation & Benefits

- **Salary Benchmarking** — market salary data comparison · seen in: Workday, BambooHR, ADP · priority: differentiator · spine: external data source integration · integration/later
- **Benefits Administration** — health insurance, retirement, flexible benefits enrollment · seen in: ADP, Gusto, Rippling, UKG Pro, Paycom · priority: common (US-market) · spine: new HRM table `BenefitPlan` (name, type, employee_contribution, employer_contribution) + `EmployeeBenefit` enrollment · deferred

### 3.38–3.40 Talent Management / Workforce Planning

- **Succession Planning / 9-Box Grid** — identify high-potential employees for critical roles · seen in: Workday, SAP SuccessFactors, ADP, Paycom · priority: differentiator · spine: new HRM tables `SuccessionPlan`, `TalentRating` · deferred
- **Workforce Demand Forecasting** — headcount planning tied to business growth · seen in: Workday, UKG Pro, SAP SuccessFactors · priority: differentiator · spine: coordinates with BI module · deferred

### 3.41 Employee Engagement & Wellbeing

- **eNPS / Pulse Surveys** — measure employee satisfaction with configurable surveys · seen in: BambooHR, Workday, ADP, Zoho People · priority: common · spine: new HRM table `EngagementSurvey` + `SurveyResponse` · deferred
- **Announcements / Kudos / Recognition** — broadcast news, peer recognition · seen in: ADP, Paycom, Rippling · priority: common · spine: `Announcement` table · deferred

---

## Spine Mapping Summary

| HRM Feature Area | Reuses Core Spine | New HRM-Owned Table(s) |
|---|---|---|
| Employee record | `core.Party` (employee role) + `core.Employment` | `EmployeeProfile` (extended HR fields) |
| Org structure | `core.OrgUnit` (department/cost_center) | `Designation` (job title + grade) |
| Attendance | — | `Shift`, `ShiftAssignment`, `AttendanceRecord` |
| Leave | — | `LeaveType`, `LeavePolicy`, `LeaveAllocation`, `LeaveRequest`, `PublicHoliday` |
| Timesheets | `accounting.Project` (job costing link) | `Timesheet`, `TimesheetEntry` |
| Payroll (HR side) | `accounting.PayrollRun` (GL posting — DO NOT DUPLICATE) | `SalaryComponent`, `SalaryStructure`, `EmployeeSalary`, `PayrollEntry` |
| Recruitment | — | `JobRequisition`, `Candidate`, `InterviewRound`, `InterviewFeedback`, `OfferLetter` |
| Performance | — | `Goal`, `PerformanceReview` |
| Onboarding | `core.Document` (checklist attachments) | `OnboardingTask` |
| GL posting | `accounting.JournalEntry` (via PayrollRun.post()) | — |

---

## Recommended build scope (this pass — 8 models)

### P0 — Core Employee Foundation (must ship first pass)

**1. EmployeeProfile** [EMP-]
- Fields: `number` (EMP-#####, unique per tenant), `party` → `core.Party` (employee kind=person + PartyRole employee), `employment` → `core.Employment` (org_unit, manager, job_title, hired_on, status), `designation` → `Designation`, `employee_type` (full_time/part_time/contract/intern), `gender` (male/female/other), `date_of_birth`, `blood_group`, `nationality`, `personal_email`, `mobile`, `bank_name`, `bank_account`, `probation_end_date`, `confirmed_on`, `photo`
- Reuses: `core.Party` + `core.Employment` + `core.OrgUnit` (department)
- Justified by: table-stakes feature in all 10 products — "centralized employee database"

**2. Designation**
- Fields: `tenant`, `name` (e.g. "Senior Engineer"), `grade` (char, e.g. "L3"), `department` → `core.OrgUnit` (nullable), `min_salary`, `max_salary`
- Reuses: `core.OrgUnit`
- Justified by: table-stakes in Workday, SAP SuccessFactors, ADP, Zoho People, Paycom — "job title hierarchy with salary bands"

**3. LeaveType**
- Fields: `tenant`, `name`, `code` (SL/AL/CL), `is_paid`, `accrual_rule` (none/monthly/annual), `accrual_days`, `max_balance`, `max_carry_forward`, `encashable`, `is_active`
- Reuses: nothing new
- Justified by: every product has configurable leave type catalog (BambooHR, Zoho People, Gusto, ADP, Frappe HRMS)

**4. LeaveAllocation** [LA-]
- Fields: `number`, `tenant`, `employee` → `EmployeeProfile`, `leave_type` → `LeaveType`, `year`, `allocated_days`, `note`, `status` (draft/active/expired)
- Reuses: nothing new; `used_days` derived from approved `LeaveRequest` rows
- Justified by: all products track per-employee leave balance per year; BambooHR, Zoho People, Gusto emphasize real-time balance

**5. LeaveRequest** [LR-]
- Fields: `number`, `tenant`, `employee` → `EmployeeProfile`, `leave_type` → `LeaveType`, `start_date`, `end_date`, `days` (computed), `reason`, `status` (draft/pending/approved/rejected/cancelled), `approver` → `User`, `approved_at`, `cancelled_reason`
- Reuses: nothing new
- Justified by: table-stakes in all 10 products; status workflow matches BambooHR, Zoho People, ADP patterns

**6. PublicHoliday**
- Fields: `tenant`, `date`, `name`, `is_optional`
- Reuses: nothing new
- Justified by: every product integrates holiday calendar into leave calculations; Zoho People, Frappe HRMS, ADP all include holiday management

### P1 — Attendance & Time

**7. AttendanceRecord** [ATT-]
- Fields: `number`, `tenant`, `employee` → `EmployeeProfile`, `date`, `check_in` (TimeField, nullable), `check_out` (TimeField, nullable), `hours_worked` (derived), `shift` → `Shift` (nullable), `status` (present/absent/half_day/on_leave/holiday/regularized), `source` (web/mobile/biometric/manual), `notes`
- Reuses: `LeaveRequest` (to mark status=on_leave)
- Justified by: table-stakes in all 10 products; ADP, UKG Pro, Zoho People, Rippling, Paycom all prioritize attendance capture with source tracking

**8. Shift**
- Fields: `tenant`, `name`, `start_time`, `end_time`, `grace_minutes`, `is_default`, `is_active`; `ShiftAssignment` through-model: (employee→EmployeeProfile, shift→Shift, effective_from, effective_to)
- Reuses: nothing new
- Justified by: Zoho People, ADP, UKG Pro, Frappe HRMS, SAP SuccessFactors — shift management is table-stakes for attendance to work correctly

### P2 — Payroll (HR-Side) — Deferred to pass 2 or included as simplified version

**PayrollEntry** coordination model (NOT accounting.PayrollRun — that already exists):
- Link each employee's computed pay for a period to the accounting PayrollRun
- Key fields: `employee`, `payroll_run` → `accounting.PayrollRun`, `gross`, `deductions`, `net`, `status`
- This is P2 because it requires salary structures to be fully set up first

**PerformanceReview** — P2:
- `employee`, `reviewer`, `cycle_period`, `self_rating`, `manager_rating`, `overall_rating`, `status`
- Justified by: table-stakes in Workday, SAP SuccessFactors, BambooHR; deferred because it depends on goal-setting setup

---

## Deferred (later passes / integrations)

- **SalaryComponent + SalaryStructure + EmployeeSalary** — salary template engine needed before PayrollEntry can compute; deferred to payroll pass 2
- **PayrollEntry (per-employee payslip)** — needs salary structures first; the accounting `PayrollRun` handles GL-side now; HRM PayrollEntry is pass 2
- **JobRequisition + Candidate + InterviewRound + OfferLetter** — full ATS flow is a separate recruiting sub-module; can ship as pass 3
- **OnboardingTask** — checklist-based onboarding; pass 2 once employee foundation is stable
- **Goal + PerformanceReview** — deferred to pass 2 (depends on employee + designation)
- **Timesheet + TimesheetEntry** — deferred to pass 2 (coordinates with accounting Job Costing Projects)
- **ExitInterview + SeparationRequest** — offboarding flow; pass 2
- **BenefitPlan + EmployeeBenefit** — benefits administration; US-market feature; later pass
- **TaxDeclaration + Form16** — jurisdiction-specific; later pass
- **TrainingSession + LMS** — full LMS is separate module; later pass
- **EngagementSurvey + SurveyResponse** — engagement module; later pass
- **ExpenseClaim** — HR expense claims coordinate with accounting; later pass (after accounting expense flow)
- **E-signature for documents** — external provider (DocuSign, HelloSign); integration/later
- **Geofenced / mobile check-in** — requires mobile app or GPS API; integration/later
- **AI-powered attrition prediction** — requires BI module + ML pipeline; deferred
- **Salary benchmarking against market data** — requires external salary data feed; integration/later
- **Bank file / NACHA export** — bank format integration; later pass
- **Succession planning / 9-box grid** — talent management pass; later
- **Deel-style global EOR / multi-country payroll** — out of single-tenant Django scope; integration/later

---

## Key architectural decisions for the `todo` agent

1. **EmployeeProfile is the HRM anchor** — it holds HRM-specific fields, carries the `EMP-#####` number, and points at `core.Party` (the person) + `core.Employment` (the job). All HRM tables FK to `EmployeeProfile`, not directly to `core.Party`. This matches the spine design (Employment is the "employee" join; EmployeeProfile adds HR-domain detail).

2. **Do NOT create an HRM PayrollRun** — `accounting.PayrollRun` (PRUN-#####) already exists and owns the GL journal posting. HRM pass 1 does NOT implement payroll processing — that coordination model (`hrm.PayrollEntry`) is pass 2 and will FK into `accounting.PayrollRun`.

3. **OrgUnit reuse** — departments and cost centers are already `core.OrgUnit` (kind=department/cost_center). `Designation` is the only new org-structure table HRM needs.

4. **Leave calculations never store running balance** — follow the spine "derived, never stored" principle: used_days = `LeaveRequest.objects.filter(employee=..., leave_type=..., status='approved', start_date__year=year).aggregate(Sum('days'))`. Allocated days live in `LeaveAllocation`; the balance is derived.

5. **AttendanceRecord.hours_worked is derived** — always compute from check_in/check_out in `save()` or a property; never let it drift.

6. **Document store** — reuse `core.Document` (GenericFK) for employee contract uploads, offer letters stored as files. Do not create a separate HRM document model.
