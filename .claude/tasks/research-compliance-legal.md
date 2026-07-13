# Research — Module 3: HRM — 3.39 Compliance & Legal (compliance-legal)

Scope grounding: `apps/hrm/models.py` already has ~100 models. Reusable anchors for this pass:
`EmployeeProfile` (anchor every new FK points at), `core.OrgUnit` (department/location scoping),
`Designation`/`JobGrade` (3.2), `EmployeeSalaryStructure` (3.13), `EmployeeDocument` (3.1 — generic
personnel-file docs, already has `employment_contract`/`nda`/`non_compete` document types),
`EmployeeLifecycleEvent` (3.1 — already has an `event_type="contract_renewal"` choice),
`WarningLetter` (3.21 — **already implements "Disciplinary Actions": incident tracking, warning
levels, issue→acknowledge workflow, confidential visibility** — do NOT re-build this for 3.39),
`StatutoryReturn`/`StatutoryConfig`/`StatutoryStateRule` (3.15 — PF/ESI/PT/TDS/LWF **tax filings**
computed from `PayslipLine` roll-ups — a *payroll-remittance* concern, distinct from 3.39's
labor-law recordkeeping/inspection concern; do not conflate the two). Convention mirrors 3.35
Travel Management: `TenantOwned`/`TenantNumbered` bases, `next_number(type(self), tenant, PREFIX)`,
self-FK or derived-query history chains, a `FileField` for the source document, `clean()`
cross-field validation, `is_*` derived `@property` (never stored flags).

## Leaders surveyed (with source links)
1. **Deel** — global EOR/payroll platform; continuous, automated compliance monitoring across
   150+ countries and localized contract generation — [Compliance solutions](https://www.deel.com/solutions/compliance/) / [Enterprise Guide to Global Compliance](https://www.deel.com/blog/the-enterprise-guide-to-global-compliance-management/)
2. **Rippling** — HRIS with an HR-services compliance layer: handbook builder, e-signature
   tracking, automated policy enforcement — [HR Services](https://www.rippling.com/products/hr/hr-services) / [Policies platform](https://www.rippling.com/platform/policies)
3. **greytHR** — India-focused HRMS; statutory muster-roll/wage-register form generation (Forms
   II/III/V/X/XVIII, state-specific) — [Statutory compliance reports](https://admin-help.greythr.com/admin/answers/u7jzwb8zq2wgslclindbfw/) / [Form III Muster Roll wiki](https://www.greythr.com/wiki/compliances/central-form-iii-muster-roll-cum-wage-register/)
4. **Keka** — full HRMS with compliance embedded across modules; documented, auditable PIP/
   disciplinary workflows and grievance-redressal-committee support — [HR Compliance Guide](https://www.keka.com/hr-compliance-guide) / [Grievance Management for HR Leaders](https://www.keka.com/grievance-management-for-hr-leaders)
5. **Zoho People (Cases / HR Help Desk)** — categorized employee case/query intake routed to
   assigned agents with status tracking and notifications — [HR Case Management](https://www.zoho.com/people/hr-case-management.html) / [Guide to Cases in Zoho People](https://www.zoho.com/people/hrknowledgehive/a-guide-to-using-cases-in-zoho-people.html)
6. **PowerDMS** — dedicated policy management: version control, side-by-side redline compare,
   e-signature attestation, full archive/audit trail — [Top features of policy management software](https://www.powerdms.com/policy-learning-center/top-features-of-policy-management-software) / [Why policy software needs version control](https://www.powerdms.com/policy-learning-center/why-your-policy-software-needs-version-control)
7. **ConvergePoint** — SharePoint-based policy/procedure lifecycle: library, role-based access,
   auto-publish + reminder alerts, compliance-by-department reporting — [Policy Management Software](https://www.convergepoint.com/policy-management-software) / [Policy & Procedure lifecycle](https://www.convergepoint.com/policy-management-software/policy-and-procedure-policy-management-software/)
8. **HR Acuity** — dedicated employee-relations case management: structured Plan→Investigate→
   Determine methodology, centralized documentation, analytics on repeat patterns — [HR Case Management](https://www.hracuity.com/platform/hr-case-management/) / [Investigation Management](https://www.hracuity.com/platform/investigation-management/)
9. **NAVEX (EthicsPoint / WhistleB)** — whistleblowing & incident management: anonymous
   multilingual reporting, structured case fields, links reports to related policies, regulatory
   change tracking — [Whistleblowing Software](https://www.navex.com/en-us/platform/whistleblowing-software-solutions/) / [EthicsPoint Professional](https://www.navex.com/en-us/platform/whistleblowing-software-solutions/ethicspoint-professional/)
10. **Darwinbox** — enterprise HRMS; compliance/localization module + fixed-term contract
    workflows (renewal permissions, profile tags) — [Contract Management app](https://marketplace.darwinbox.com/en-US/apps/405759/contract-management/features) / [Top HRMS Modules 2026](https://darwinbox.com/blog/top-hr-modules)

Supplementary (feature detail, not full profiles): **BambooHR** contract storage/e-signature/
renewal-report limitations — [How to manage contracts in BambooHR](https://juro.com/learn/manage-contracts-bamboohr); generic disciplinary-appeal-process research — [AIHR Disciplinary Action Guide](https://www.aihr.com/blog/disciplinary-action/), [Fyxer Appeal Letter guidance](https://www.fyxer.com/blog/disciplinary-appeal-letter-template).

## Feature catalog by sub-module
### 3.39 Compliance & Legal

**— Labor Law Compliance —**
- **Jurisdiction-scoped rule tracking** — flag a labor-law requirement (min wage, working-hours
  cap, leave mandate, license/permit) by country/state and its review/renewal cadence · seen in:
  Deel, greytHR, Rippling · priority: differentiator · spine: new table `ComplianceRegister`
  (reuse `core.OrgUnit` for applicability) · buildable now (as a checklist/register; automated
  regulatory-change *feeds* are integration/later)
- **Overdue/at-risk alerting** — dashboard flags of non-compliant or lapsing items · seen in:
  Deel (Workforce Insights), Rippling (compliance tracking) · priority: common · spine: derived
  `@property` on `ComplianceRegister` (`is_overdue`), mirrors `StatutoryReturn.is_overdue` ·
  buildable now

**— Contract Management —**
- **Contract type + term tracking** (permanent/fixed-term/probation/intern/consultant, start/
  end/probation dates, notice period) · seen in: Darwinbox, BambooHR, Deel · priority:
  table-stakes · spine: new table `EmploymentContract` FKs `EmployeeProfile`,
  `Designation`/`JobGrade` (3.2) · buildable now
- **Renewal workflow / chain** (link a renewal to its prior term, permissions on renewal) · seen
  in: Darwinbox, BambooHR (reports only, no automation) · priority: common · spine: self-FK
  `EmploymentContract.renewed_from`; log the event via the **existing**
  `EmployeeLifecycleEvent(event_type="contract_renewal")` — no new history table needed ·
  buildable now
- **Localized/compliant contract terms tied to comp** · seen in: Deel (auto-generated localized
  contracts) · priority: differentiator · spine: reuse `EmployeeSalaryStructure` (3.13) FK ·
  buildable now (template/clause generation by jurisdiction is integration/later)
- **Document storage + e-signature + version/renewal reporting** · seen in: BambooHR, PowerDMS ·
  priority: table-stakes · spine: `FileField` on `EmploymentContract` (mirrors
  `TravelBooking.document`); true e-signature capture is integration/later — v1 stores the signed
  upload
- **Expiry reminders** · seen in: Rippling, ConvergePoint · priority: common · spine: derived
  `is_expiring_soon` property + a `reminder_days` field; actual email/notification send is
  integration/later

**— Policy Management —**
- **Policy library with categories** (code of conduct, leave, safety, IT, harassment, etc.) ·
  seen in: ConvergePoint, Rippling, Darwinbox, Keka (essential HR policies) · priority:
  table-stakes · spine: new table `HRPolicy` · buildable now
- **Version control** (know which version is current; prior versions archived/read-only) · seen
  in: PowerDMS, ConvergePoint · priority: table-stakes · spine: self-FK
  `HRPolicy.previous_version` + `version_number`/`status` — v1 is a linked chain + a `summary`
  "what changed" text field, not a redline diff UI · buildable now
- **Scoped applicability** (by department/location/role) · seen in: ConvergePoint ("roles-based
  access by dept/region") · priority: common · spine: `HRPolicy.applicable_org_unit` FK
  `core.OrgUnit`, blank = all (mirrors `TravelPolicy.job_grade` blank-is-all pattern) ·
  buildable now
- **Acknowledgment / attestation tracking** (who has/hasn't signed the latest version) · seen
  in: PowerDMS (e-signature), ConvergePoint ("managers see who's in compliance"), Rippling
  (auto-assign for e-signature, track completion) · priority: table-stakes · spine: new child
  table `PolicyAcknowledgment` (employee × policy × status/timestamp, mirrors
  `WarningLetter.acknowledged_at/acknowledged_by`) · buildable now (click-to-acknowledge; true
  cryptographic e-signature is integration/later)
- **Auto-publish + reminder notifications** · seen in: ConvergePoint, Rippling · priority:
  common · spine: `HRPolicy.published_at` + `PolicyAcknowledgment.status='pending'` list; the
  actual email/reminder send is integration/later

**— Disciplinary Actions — ALREADY BUILT, reuse only** (see `apps/hrm/models.py:5886`
`WarningLetter`, 3.21):
- **Incident tracking + warning levels** (verbal/written/final/suspension, category, policy
  reference, escalation via `prior_warnings`) · seen in: Keka, HR Acuity · priority:
  table-stakes · spine: **reuse `hrm.WarningLetter` as-is** — no new model
- **Appeals** — the one sub-feature `WarningLetter` doesn't yet model (it has
  `employee_response` free text but no formal appeal *status*) · seen in: generic HR practice
  (AIHR/Fyxer: appeal window, reviewer-not-involved, response turnaround) · priority: common ·
  spine: **small addition to the existing `WarningLetter`** (an `"appealed"` `STATUS_CHOICES`
  entry + an `appeal_notes` text field) rather than a new model — flagged for the `todo` agent as
  an optional 2-field extension, not part of the 4-model budget below

**— Grievance Handling —**
- **Complaint registration with categories** (harassment, discrimination, safety, policy
  violation, compensation dispute, management conduct) · seen in: Zoho People Cases, Keka,
  HR Acuity · priority: table-stakes · spine: new table `Grievance` FKs `EmployeeProfile`
  (complainant + optional respondent) · buildable now
- **Anonymous / confidential reporting** · seen in: NAVEX (EthicsPoint/WhistleB) · priority:
  common · spine: `Grievance.is_anonymous` + `is_confidential` flags (nullable complainant FK) ·
  buildable now (an external hotline/phone channel is integration/later)
- **Structured investigation workflow** (assign investigator, status progression, documented
  notes, resolution) · seen in: HR Acuity (Plan→Investigate→Determine), Zoho People Cases ·
  priority: table-stakes · spine: `Grievance.assigned_investigator` FK `EmployeeProfile`,
  `status` state machine · buildable now
- **Severity / pattern flagging** · seen in: HR Acuity (analytics on repeat issues) · priority:
  common · spine: `Grievance.severity` choice field; cross-case pattern analytics is
  integration/later (would need an analytics pass, not this one)
- **Link resolved grievance to disciplinary action / policy** · seen in: NAVEX ("link reports to
  related policies and training"), HR Acuity · priority: differentiator · spine:
  `Grievance.related_warning` FK **reuses `hrm.WarningLetter`**, `Grievance.related_policy` FK
  the new `HRPolicy` — ties this sub-module's own new models together instead of duplicating ·
  buildable now
- **AI-assisted investigation planning** (olivER™) · seen in: HR Acuity · priority:
  differentiator · integration/later (out of scope for a Django CRUD pass)

**— Statutory Registers —**
- **Muster roll / wage register generation** (Forms II/III/V/X/XVIII — attendance + wages +
  deductions consolidated per jurisdiction form) · seen in: greytHR · priority: table-stakes (in
  regulated markets) · spine: new table `ComplianceRegister` (`register_type` choice), scoped by
  `core.OrgUnit` and a `period_start`/`period_end` — the underlying attendance/wage *data* already
  lives in `AttendanceRecord`/`PayslipLine`; v1 records the register as a filed/uploaded document
  (period + status + file), not a fresh recomputation engine · buildable now
- **Inspection reports** (inspector visits, findings, follow-up) · seen in: greytHR (compliance
  forms), general labor-law practice · priority: common · spine: same `ComplianceRegister` table,
  `register_type="inspection_report"` with `inspector_name`/`inspection_date`/`findings` ·
  buildable now
- **Filing status / due-date tracking** · seen in: greytHR, Deel · priority: table-stakes ·
  spine: `ComplianceRegister.status`/`due_date`/`completed_on` (mirrors `StatutoryReturn`'s
  pending/filed/late shape, kept as a **separate** model since this is labor-law recordkeeping,
  not payroll-tax remittance) · buildable now

## Recommended build scope (this pass — 4 models + 1 natural child)
- **`EmploymentContract`** [`CTR-`] `TenantNumbered` — `employee` FK `EmployeeProfile`;
  `contract_type` (permanent/fixed_term/probation/internship/consultant/apprentice);
  `designation`/`job_grade` FK (reuse 3.2); `start_date`/`end_date`/`probation_end_date`;
  `notice_period_days`; `salary_structure` FK `EmployeeSalaryStructure` (reuse 3.13, SET_NULL);
  `renewed_from` self-FK (renewal chain); `status` (draft/active/renewed/expired/terminated);
  `signed_on`; `document` FileField; `reminder_days`; `terms_notes`. Derived `is_expiring_soon`/
  `is_expired`. On renew/terminate, the view also writes an `EmployeeLifecycleEvent` (existing
  `contract_renewal`/`separation` event types) — reuse, don't duplicate the timeline. Justified
  by: Darwinbox/BambooHR/Deel contract-management features above.
- **`HRPolicy`** [`POL-`] `TenantNumbered` — `title`; `category` (code_of_conduct/leave/
  attendance/harassment/safety/it_security/expense/compensation/remote_work/other);
  `version_number`; `previous_version` self-FK; `effective_date`; `applicable_org_unit` FK
  `core.OrgUnit` (blank = all, mirrors `TravelPolicy`); `requires_acknowledgment` bool;
  `status` (draft/published/archived/superseded); `document` FileField; `owner` FK
  `EmployeeProfile`; `published_at`; `summary` (what changed). Justified by: PowerDMS/
  ConvergePoint/Rippling policy-lifecycle features above.
- **`PolicyAcknowledgment`** (`TenantOwned` child of `HRPolicy`, no separate number) —
  `policy` FK CASCADE, `employee` FK CASCADE, `status` (pending/acknowledged/declined),
  `acknowledged_at` (editable=False, set only by the acknowledge action — mirrors
  `WarningLetter.acknowledged_at/acknowledged_by`), `unique_together (tenant, policy, employee)`.
  Gives HR the "who's in compliance" list ConvergePoint/PowerDMS/Rippling all call out. Not
  counted against the 4-model budget — it's the same shape as `TravelBooking` under
  `TravelRequest` in 3.35.
- **`Grievance`** [`GRV-`] `TenantNumbered` — `complainant` FK `EmployeeProfile` (SET_NULL,
  nullable for anonymous); `is_anonymous`; `against_employee` FK `EmployeeProfile` (SET_NULL,
  optional); `category` (harassment/discrimination/workplace_safety/policy_violation/
  compensation_dispute/management_conduct/other); `description`; `filed_date`; `severity` (low/
  medium/high/critical); `status` (registered/under_investigation/resolved/closed/escalated/
  withdrawn); `assigned_investigator` FK `EmployeeProfile`; `investigation_notes`; `resolution`;
  `resolution_date`; `is_confidential` (default True); `related_warning` FK **reuse**
  `hrm.WarningLetter`; `related_policy` FK **reuse** the new `HRPolicy`. Justified by: Zoho
  People Cases, HR Acuity, NAVEX EthicsPoint, Keka grievance-redressal features above.
- **`ComplianceRegister`** [`CMP-`] `TenantNumbered` — `register_type` (labor_law_requirement/
  muster_roll/wage_register/inspection_report/license_permit/other_statutory);
  `jurisdiction_country`/`jurisdiction_state`; `law_or_form_reference`; `title`;
  `applicable_org_unit` FK `core.OrgUnit`; `period_start`/`period_end`; `due_date`; `status`
  (pending/in_progress/compliant/filed/overdue/exempt); `completed_on`; `responsible` FK
  `EmployeeProfile`; `document` FileField; `inspector_name`; `inspection_date`; `findings`;
  `notes`. Derived `is_overdue` (mirrors `StatutoryReturn.is_overdue`). Deliberately **separate**
  from `StatutoryReturn` (3.15, payroll-tax remittance) — this is labor-law recordkeeping. 
  Justified by: greytHR muster-roll/wage-register forms, Deel/Rippling jurisdiction-tracking
  features above.

Optional small extension flagged for `todo` (not a new model): add `"appealed"` to
`WarningLetter.STATUS_CHOICES` + an `appeal_notes` field to close the Disciplinary-Actions
"appeals" gap.

## Deferred (later passes / integrations)
- **Automated regulatory-change monitoring** (Deel's 150-country law-change feed) — needs an
  external data subscription, not a Django-only feature.
- **True e-signature / biometric attestation** (PowerDMS mobile biometric sign, DocuSign-style
  flows) — v1 uses a simple click-to-acknowledge action, same pattern as `WarningLetter.acknowledge`.
  Real e-signature is an integration.
- **AI-assisted investigation planning** (HR Acuity olivER™: suggested interview questions,
  auto-generated plans) — integration/later, out of scope for this Django pass.
- **External whistleblower hotline** (24/7 phone + 35-language translation, NAVEX) — a
  reporting-channel integration, not a data-model concern for v1.
- **Multi-member Grievance Redressal Committee** (Keka's committee composition rules) — v1 is a
  single `assigned_investigator`; committee membership is a fast-follow.
- **Automated attendance/wage recomputation into `ComplianceRegister`** (a live Form-II/III
  generator pulling `AttendanceRecord`/`PayslipLine`) — v1 records the register as a filed
  document; the compute engine is a later pass (mirrors how `StatutoryReturn.recompute()` took a
  dedicated pass in 3.15).
- **Redline / side-by-side version diff UI** for `HRPolicy` (PowerDMS) — v1 has the version chain
  + a free-text `summary`, no visual diff.
- **Cross-case pattern analytics** (HR Acuity's repeat-issue detection across grievances) — a
  reporting/analytics pass, not this sub-module's CRUD pass.
