# Research — HRM Sub-module 3.37: Compensation & Benefits (compensation-benefits)

Scope note: this is a **sub-module addition to the existing `apps/hrm` app** (Module 3), not a new app. It must
reuse `hrm.EmployeeProfile` (the anchor), `hrm.JobGrade`/`Designation` (3.2), `hrm.PayComponent` /
`SalaryStructureTemplate` / `EmployeeSalaryStructure` (3.13 — salary structure/CTC already exists and must NOT be
re-created), `hrm.KudosBadge` / `Feedback` (3.20 — peer kudos already exists), `accounting.Currency`, and the
`TenantOwned` / `TenantNumbered` base classes exactly as used by 3.35 Travel (`TravelPolicy`/`TravelRequest`/
`TravelBooking`).

## Existing HRM models already covering part of this domain (grepped `apps/hrm/models.py`)
- **`PayComponent` / `SalaryStructureTemplate` / `SalaryStructureLine` / `EmployeeSalaryStructure`** (3.13) —
  full CTC/pay-component catalog + grade-wise structure templates + effective-dated per-employee assignment.
  This is the "salary structure" layer — 3.37 must build **on top of** it (benchmarking against it, planning
  changes to it), never duplicate it.
- **`Designation`** (3.2) already carries `min_salary` / `mid_salary` / `max_salary` — an internal salary **band**
  per job title/grade. This is the natural anchor for compa-ratio / range-penetration once external market data
  exists (3.37's job).
- **`KudosBadge` / `Feedback`** (3.20, `feedback_type="kudos"/"appreciation"`, `is_anonymous`, `visibility`) —
  peer-to-peer recognition already exists as free-text, unbudgeted, no-approval kudos. 3.37's "Rewards &
  Recognition" gap is specifically the **formal, monetary, budget/approval-gated** award (spot bonus, service
  anniversary award) that products like Bonusly/Workhuman treat as a distinct workflow from ad-hoc kudos.
- **`JobGrade`** (3.2) — grade catalog, reusable as the benchmarking axis.
- No existing model covers: external market salary data, health/life/retirement benefits enrollment, flexible/
  cafeteria opt-in-opt-out, equity/ESOP grants & vesting, or a formal merit/promotion/budget compensation-review
  cycle. Those are this sub-module's real gap.

## Leaders surveyed (with source links)
1. **Payscale** (MarketPay / CompAnalyst / Paycycle) — market-pricing & compensation-planning data platform;
   9M+ record library, AI job-pricing ("Smart Price"), compa-ratio/pay-equity dashboards —
   [payscale.com/products/software](https://www.payscale.com/products/software), [Paycycle](https://www.payscale.com/products/software/compensation-planning/)
2. **Mercer (WIN) / Radford** — global compensation survey providers; job-matching to a proprietary grading
   system, percentile benchmarking, custom peer groups —
   [Mercer global comp & benefits data](https://www.mercer.com/solutions/talent-and-rewards/rewards-strategy/global-compensation-and-benefits-data/), [Radford alternatives overview](https://ravio.com/blog/radford-alternatives-for-compensation-management)
3. **Carta** — cap-table & equity-management platform; grant issuance, vesting schedules, exercise tracking,
   409A/ASC 718 reporting, dilution/waterfall modeling —
   [carta.com/equity-management](https://carta.com/equity-management/), [carta.com/equity-management/cap-table](https://carta.com/equity-management/cap-table/)
4. **Shareworks by Morgan Stanley** — enterprise equity-plan administration (options/RSU/ESPP); vesting,
   exercise, FMV, ASC 718/IFRS 2 compliant reporting, budget/expense modeling —
   [morganstanley.com/atwork/shareworks](https://www.morganstanley.com/atwork/shareworks)
5. **Workday Compensation (+ Advanced Compensation)** — merit/bonus/stock review-cycle engine; guideline
   matrices, bottom-up budget pools, configurable multi-award workflows, real-time analytics —
   [workday.com … compensation](https://www.workday.com/en-in/products/human-capital-management/human-resource-management/compensation.html), [datasheet PDF](https://www.workday.com/content/dam/web/en-us/documents/datasheets/datasheet-workday-compensation.pdf)
6. **SAP SuccessFactors Compensation & Variable Pay** — salary structures/pay grades, budget management,
   merit-planning guidelines, compa-ratio/range-penetration, bonus/compensation statements —
   [diokles.de SF Compensation overview](https://diokles.de/en_us/sap-successfactors-compensation-variable-pay-overview/), [help.sap.com Variable Pay](https://help.sap.com/docs/successfactors-compensation/implementing-and-managing-variable-pay/sap-successfactors-variable-pay)
7. **bswift / Benefitfocus** — benefits administration & open-enrollment platform; decision-support enrollment,
   carrier EDI integrations, AI-personalized engagement (Evive) —
   [bswift.com/employers](https://www.bswift.com/employers/), [benefitfocus.com benefits-administration](https://www.benefitfocus.com/employer-benefit-solutions/benefits-administration)
8. **Bonusly** — peer recognition & spot-bonus platform; monthly point allowance, rewards catalog (gift
   cards/cash/donations), Slack/Teams integration, participation analytics —
   [bonusly.com/product/recognition](https://bonusly.com/product/recognition), [bonusly.com](https://bonusly.com/)
9. **Workhuman Social Recognition** — social recognition feed, Service Milestones (work anniversaries),
   Life Events/Community Celebrations, admin spend-control/misuse-detection, AI bias-mitigation ("Inclusion
   Advisor") —
   [workhuman.com/platform/social-recognition](https://www.workhuman.com/platform/social-recognition/)
10. **Zoho People — Compensation service** — CTC/benefit-component catalog, multi-package salary structures per
    location/designation, salary-revision workflow with approval + revision letters, performance-to-comp push —
    [zoho.com/people/compensation-management-software](https://www.zoho.com/people/compensation-management-software.html), [help.zoho.com compensation overview](https://help.zoho.com/portal/en/kb/people/administrator-guide/compensation/overview/articles/compensation-overview)

Also referenced for the cafeteria/flex-benefits shape: general Section 125 / flex-benefit plan design descriptions
(opt-out to taxable cash, tiered coverage elections) — [flexiblebenefit.com cafeteria plans](https://www.flexiblebenefit.com/employers/products/cafeteria-plans), [Paylocity glossary: cafeteria plan](https://www.paylocity.com/resources/glossary/cafeteria-plan/).

## Feature catalog by NavERP.md 3.37 bullet

### Salary Benchmarking (market salary data, industry comparisons)
- **Percentile market pricing (P25/P50/P75/P90) per job/grade/region** — what it does: stores external survey
  data an org buys, keyed to an internal job so pay decisions can be checked against the market · seen in:
  Payscale (MarketPay), Mercer (WIN), Radford · priority: table-stakes for any dedicated comp platform ·
  spine: reuse `hrm.JobGrade`/`Designation`, `accounting.Currency` — **new table** `SalaryBenchmark` ·
  buildable now (manual/periodic data entry; the survey purchase itself is out of scope).
- **AI job-matching / auto-classification to survey jobs** — what it does: matches internal roles to a vendor's
  job catalog automatically · seen in: Payscale Smart Price, Mercer Data Connector, Radford job-matching ·
  priority: differentiator · spine: n/a · **integration/later** (external vendor API + AI).
- **Compa-ratio & range penetration** — what it does: (employee pay ÷ range midpoint) and where an employee
  sits inside min–max · seen in: Payscale, SAP SuccessFactors, Mercer · priority: table-stakes among true comp
  platforms · spine: **computed property**, not stored — divides `EmployeeSalaryStructure`/`Designation` salary
  against `SalaryBenchmark.median` or `Designation.mid_salary` · buildable now.
- **Pay-equity risk / exposure dashboards** — what it does: flags statistical pay gaps by gender/role/tenure ·
  seen in: Payscale · priority: differentiator · spine: reporting only, no new core table · **later** (needs a
  reporting pass, not this model pass).

### Benefits Administration (health/life insurance, retirement plans)
- **Benefit plan catalog by type (medical/dental/vision/life/disability/retirement)** — what it does: the menu
  of benefits an org offers, each with an employer/employee cost split · seen in: bswift/Benefitfocus, Workday,
  SAP SuccessFactors, Zoho People · priority: table-stakes · spine: `accounting.Currency` — **new table**
  `BenefitPlan` · buildable now.
- **Open-enrollment / life-event enrollment workflow** — what it does: employee elects/waives coverage during
  an enrollment window or qualifying life event, tiered by coverage level (employee-only/+spouse/+family) ·
  seen in: bswift/Benefitfocus, Workday, Zoho People · priority: table-stakes · spine: reuse
  `hrm.EmployeeProfile` — **new table** `EmployeeBenefitEnrollment` · buildable now (the tiered election +
  status is a plain form; the *qualifying-life-event trigger engine* is integration/later).
- **Carrier EDI / 834-file integration** — what it does: pushes enrollment data to the insurance carrier ·
  seen in: bswift/Benefitfocus (550+ integrations) · priority: differentiator · spine: n/a · **integration/later**.
- **AI decision-support / personalized nudges** — what it does: recommends a plan tier / nudges usage
  year-round · seen in: bswift (Evive) · priority: differentiator · **integration/later**.
- **Retirement-plan contribution tracking (401k/PF-style employer match)** — what it does: tracks
  employee/employer contribution % into a retirement vehicle · seen in: bswift, Workday, SAP SuccessFactors ·
  priority: common · spine: modeled as a `BenefitPlan` of `plan_type="retirement"` with contribution fields on
  the enrollment row — reuses the same two new tables above; a payroll-deduction posting via `PayComponent`/
  `accounting.JournalEntry` is **integration/later**.

### Flexible Benefits (cafeteria-style benefit plans, opt-in/opt-out)
- **Cafeteria/flex-credit allowance the employee allocates across plans** — what it does: employer grants a
  flex-credit pool; employee spends it across benefit options, cashing out the remainder as taxable income if
  allowed · seen in: bswift/Benefitfocus, general Section 125 plan design · priority: common (mature-market
  differentiator, e.g. US) · spine: **reuses the same `BenefitPlan`** (`is_flex_credit_eligible` +
  `flex_credit_amount` fields) + `EmployeeBenefitEnrollment` (`election_choice` = opt_in/opt_out/waived) —
  no separate table needed · buildable now.
- **Opt-in / opt-out per benefit with an audit trail** — what it does: records the employee's explicit choice
  and effective date · seen in: all benefits platforms surveyed · priority: table-stakes · spine:
  `EmployeeBenefitEnrollment.election_choice` + `effective_from`/`effective_to` · buildable now.
- **Summary Plan Description / plan document distribution** — what it does: compliance document employees must
  receive · seen in: bswift/Benefitfocus · priority: common · spine: could reuse a generic document/file field
  on `BenefitPlan` · **later** (thin — a `FileField`, not a driver for this pass).

### Stock/ESOP Management (equity grants, vesting schedules, exercise tracking)
- **Equity grant issuance (ISO/NSO/RSU/ESPP/phantom)** — what it does: records a grant of shares/options to an
  employee with a strike/exercise price and grant-date fair market value · seen in: Carta, Shareworks, Workday
  (stock award process) · priority: table-stakes for any equity-management product · spine: reuse
  `hrm.EmployeeProfile`, `accounting.Currency` — **new table** `EquityGrant` · buildable now.
- **Vesting schedule (cliff + linear/graded vesting)** — what it does: computes what fraction of a grant is
  vested as of today from a cliff period + total vesting duration · seen in: Carta, Shareworks · priority:
  table-stakes · spine: **computed property** on `EquityGrant` (cliff_months/vesting_months fields), never a
  stored balance — mirrors `LeaveAllocation`'s "always computed from approved requests" spine principle ·
  buildable now.
- **Exercise tracking** — what it does: records how many vested options/shares have been exercised and when ·
  seen in: Carta, Shareworks · priority: table-stakes · spine: `EquityGrant.exercised_shares` +
  `last_exercised_at`, updated by a bespoke "record exercise" action (same shape as `TravelRequest`'s
  advance-paid action) · buildable now.
- **409A valuation / ASC 718 & IFRS 2 stock-comp expense reporting** — what it does: values option grants for
  GAAP/IFRS expense recognition, postable to the GL · seen in: Carta, Shareworks · priority: differentiator ·
  spine: would eventually post to `accounting.JournalEntry` as a stock-comp expense line · **integration/later**
  (needs a valuation input this pass doesn't have).
- **Cap table / dilution & waterfall modeling, investor reporting** — what it does: ownership-percentage and
  exit-proceeds modeling across the whole share register · seen in: Carta · priority: differentiator ·
  spine: out of scope — NavERP is not a fundraising/cap-table platform · **deferred indefinitely**, not just
  "later".

### Compensation Planning (merit increases, promotion raises, budget modeling)
- **Annual/cyclical compensation review with a budget pool** — what it does: HR opens a comp-review cycle with
  a total budget; managers propose merit %/promotion raises for their reports against guideline matrices ·
  seen in: Workday (Merit/Bonus/Stock Process), SAP SuccessFactors (Budget Management + Guidelines), Payscale
  Paycycle, Zoho People (salary revision + approval) · priority: table-stakes among comp-planning tools ·
  spine: reuses `hrm.EmployeeSalaryStructure` as the "current CTC" reference and, on approval, would create the
  *next* effective-dated `EmployeeSalaryStructure` row — **new tables** `CompensationCycle` +
  `CompensationReviewLine` · buildable now.
- **Guideline matrices tying merit % to performance rating** — what it does: suggests a merit % band from the
  employee's latest performance rating · seen in: Workday, SAP SuccessFactors · priority: differentiator ·
  spine: could FK `hrm.PerformanceReview`/`ReviewRating` (3.19, already exists) · **later** (needs the matrix
  config table this pass doesn't budget for).
- **Real-time budget-consumption tracking / pool remaining** — what it does: shows how much of the cycle budget
  is committed vs. remaining as managers submit proposals · seen in: Workday, SAP SuccessFactors · priority:
  common · spine: **computed property** summing `CompensationReviewLine.proposed_increase_amount` against
  `CompensationCycle.budget_amount` · buildable now.
- **Compensation/bonus statements to employees** — what it does: a formatted personal summary of the raise/
  bonus decision · seen in: SAP SuccessFactors, Zoho People (revision letters) · priority: common · spine:
  reuses the eventual `CompensationReviewLine` detail page as the "statement" · **later** (print-template work,
  not a model).

### Rewards & Recognition (spot awards, service awards, peer recognition)
- **Peer-to-peer social recognition with a feed** — what it does: any employee publicly praises another,
  optionally with points · seen in: Bonusly, Workhuman · priority: table-stakes for recognition platforms ·
  spine: **already exists** — `hrm.Feedback` (`feedback_type="kudos"/"appreciation"`, `visibility`) +
  `hrm.KudosBadge` (3.20) — no new table needed for the peer-praise part.
- **Monetary spot bonus / award with approval + budget control** — what it does: a manager/HR-approved cash or
  points award tied to a reason, distinct from free-text kudos · seen in: Bonusly (points → redeemable rewards),
  Workhuman (spend control, misuse detection), Payscale/Workday bonus process · priority: common · spine: reuse
  `hrm.EmployeeProfile`, `hrm.KudosBadge` (for the award "reason" tag), `accounting.Currency` — **new table**
  `RecognitionAward` (deferred this pass — see below) · would eventually post payout via `hrm.PayComponent`
  (`component_type="variable"`) — **integration/later** for the actual payroll payout.
- **Service/anniversary milestone awards** — what it does: auto-flags/records a tenure-milestone award (5/10/15
  years) · seen in: Workhuman (Service Milestones) · priority: common · spine: tenure is derivable from
  `EmployeeProfile.date_of_joining` (already exists) — the *award record* itself would live in the same
  deferred `RecognitionAward` table (`award_type="service"`).
- **Rewards catalog / redemption (gift cards, donations, merchandise)** — what it does: employees redeem earned
  points for real rewards · seen in: Bonusly, Workhuman · priority: differentiator · spine: n/a ·
  **integration/later** (third-party redemption vendor).
- **AI bias-mitigation in recognition text** — what it does: flags biased language in praise before it's posted
  · seen in: Workhuman (Inclusion Advisor) · priority: differentiator · **integration/later**.

## Recommended build scope (this pass — 4 models)

Lean, table-stakes-first cut: covers **4 of the 6** NavERP.md bullets with genuinely new tables (Salary
Benchmarking; Benefits Administration + Flexible Benefits folded into one plan/enrollment pair; Stock/ESOP).
Compensation Planning and Rewards & Recognition are deferred (see below) because they either need a follow-on
model pass of their own or already have partial coverage from existing 3.13/3.20 models.

1. **`SalaryBenchmark`** (`TenantOwned`, catalog-style like `TravelPolicy` — no auto-number) — Salary
   Benchmarking. Fields: `job_grade` FK `hrm.JobGrade` (nullable = applies to all), `designation` FK
   `hrm.Designation` (nullable), `source` (`CharField`, choices: `internal/payscale/mercer/radford/other`),
   `region` (`CharField`, free text — e.g. "US-National", "APAC"), `currency` FK `accounting.Currency`,
   `percentile_25`/`percentile_50`/`percentile_75`/`percentile_90` (`Decimal`), `survey_date` (`DateField`),
   `notes` (`TextField`). Property `compa_ratio(designation_or_employee)` divides current pay by
   `percentile_50`. Justified by: Payscale/Mercer/Radford percentile benchmarking + compa-ratio feature.

2. **`BenefitPlan`** (`TenantOwned`, catalog like `PayComponent`/`TravelPolicy` — no auto-number) — Benefits
   Administration + Flexible Benefits (catalog half). Fields: `name`, `plan_type` (choices: `medical/dental/
   vision/life/disability/retirement/wellness/other`), `provider` (`CharField`), `is_flex_credit_eligible`
   (`BooleanField`), `flex_credit_amount` (`Decimal`, null), `employer_cost_monthly` / `employee_cost_monthly`
   (`Decimal`), `currency` FK `accounting.Currency`, `coverage_tier_options` (simple `CharField`/comma list —
   e.g. "employee_only,employee_spouse,family"; a full tier-pricing sub-table is deferred), `enrollment_window_
   start`/`enrollment_window_end` (`DateField`, null — supports an open-enrollment period), `is_active`.
   Justified by: bswift/Benefitfocus plan catalog + tiered coverage, Zoho People CTC/benefit components,
   Section 125 flex-credit design.

3. **`EmployeeBenefitEnrollment`** (`TenantNumbered`, `NUMBER_PREFIX = "BEN"`, header pattern like
   `TravelRequest`) — Benefits Administration + Flexible Benefits (election half). Fields: `employee` FK
   `hrm.EmployeeProfile`, `plan` FK `hrm.BenefitPlan`, `election_choice` (choices: `opt_in/opt_out/waived`),
   `coverage_tier` (`CharField`, matches one of the plan's tier options), `effective_from`/`effective_to`
   (`DateField`), `employee_contribution`/`employer_contribution` (`Decimal`, defaults from the plan but
   overridable), `status` (choices: `pending/enrolled/waived/terminated`), `enrolled_at` (`DateTimeField`,
   null), `notes`. `unique_together` on (`tenant`, `employee`, `plan`, `effective_from`) so re-enrollment across
   periods is allowed but duplicates aren't. Justified by: bswift/Benefitfocus open-enrollment workflow +
   Section 125 opt-in/opt-out with an effective-dated audit trail.

4. **`EquityGrant`** (`TenantNumbered`, `NUMBER_PREFIX = "ESOP"`) — Stock/ESOP Management. Fields: `employee`
   FK `hrm.EmployeeProfile`, `grant_type` (choices: `iso/nso/rsu/espp/phantom`), `grant_date` (`DateField`),
   `shares_granted` (`PositiveIntegerField`), `exercise_price` (`Decimal`, null — RSUs have none),
   `fair_market_value_at_grant` (`Decimal`, null), `currency` FK `accounting.Currency`, `vesting_start_date`
   (`DateField`), `cliff_months` (`PositiveSmallIntegerField`, default 12), `vesting_duration_months`
   (`PositiveSmallIntegerField`, default 48), `vesting_frequency` (choices: `monthly/quarterly/annual`),
   `exercised_shares` (`PositiveIntegerField`, default 0), `last_exercised_at` (`DateTimeField`, null),
   `status` (choices: `active/fully_vested/exercised/cancelled/expired`), `notes`. Computed properties
   (never stored, mirrors `TravelBooking.out_of_policy`/`LeaveAllocation` derivation pattern):
   `vested_shares` (0 before cliff, then linear/graded to `shares_granted` by `vesting_duration_months`),
   `vested_percent`, `unvested_shares`, `exercisable_shares = vested_shares - exercised_shares`. Justified by:
   Carta/Shareworks grant issuance + vesting-schedule computation + exercise tracking (the three table-stakes
   features every equity-management leader has); 409A/ASC 718/cap-table modeling explicitly deferred.

## Deferred (later passes / integrations)

- **Compensation Planning (`CompensationCycle` + `CompensationReviewLine`)** — merit/promotion/budget review
  cycles (Workday Merit Process, SAP SuccessFactors Guidelines, Payscale Paycycle, Zoho salary revision).
  Deferred because it's a distinct workflow (budget pool + per-employee proposal + approval, feeding a *new*
  `hrm.EmployeeSalaryStructure` row) that deserves its own model pass rather than being squeezed into this one;
  `EmployeeSalaryStructure` (3.13) already holds the "current CTC" data it would read/write.
- **`RecognitionAward` (spot/service awards)** — Bonusly/Workhuman-style monetary, budget-controlled, approved
  awards distinct from the free-text kudos already covered by `hrm.Feedback`/`KudosBadge` (3.20). Deferred
  because peer recognition already has baseline coverage; the *formal* monetary/payout workflow is a follow-up.
- **Guideline matrices tying merit % to performance rating** — needs a small config table reading
  `hrm.PerformanceReview`/`ReviewRating` (3.19) — later, once Compensation Planning ships.
- **Rewards catalog/redemption (gift cards, donations, merchandise)** — third-party redemption vendor
  integration (Bonusly/Workhuman) — integration/later.
- **Carrier EDI (834 file) / benefits vendor integrations** (bswift/Benefitfocus) — integration/later.
- **AI job-pricing / auto job-matching to survey catalogs** (Payscale Smart Price, Mercer Data Connector,
  Radford job matching) — external vendor API + AI — integration/later.
- **Pay-equity risk dashboards, compa-ratio/range-penetration reports** — reporting-layer work once
  `SalaryBenchmark` + `Designation` bands both have data — later (reports, not new models).
- **409A valuation / ASC 718 & IFRS 2 stock-comp GL expense posting** — would post to
  `accounting.JournalEntry` but needs a valuation input this pass doesn't collect — integration/later.
- **Cap table, dilution/waterfall modeling, investor reporting** (Carta) — out of scope; NavERP is not a
  fundraising/cap-table platform — deferred indefinitely, not a near-term follow-up.
- **Payroll deduction posting for benefit contributions / equity exercise cash settlement** — would flow
  through `hrm.PayComponent` and eventually `accounting.PayrollRun`/`JournalEntry` — integration/later (mirrors
  the existing "Payroll/GL posting is owned by accounting.PayrollRun" spine note at the top of `models.py`).
- **AI bias-mitigation in recognition text** (Workhuman Inclusion Advisor) — integration/later.
