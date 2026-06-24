# Research — Module 3.3: Employee Onboarding (hrm-onboarding)

Sub-module research pass for NavERP HRM Module 3, sub-module 3.3 only.
Scope: OnboardingTemplate + instance management, task checklists, document collection, asset allocation, orientation scheduling, welcome kit.
Out of scope: recruiting/ATS (3.5–3.8), offboarding (3.4), payroll.

---

## Leaders surveyed

1. **BambooHR** — All-in-one HRIS with strong self-service preboarding and e-signature workflows.
   Features page: https://www.bamboohr.com/platform/onboarding/

2. **Workday** — Enterprise HCM with phased onboarding plans, preboarding portal, journeys engine, and analytics.
   Features page: https://www.workday.com/en-us/products/talent-management/onboarding-plans.html

3. **Rippling** — HR + IT unified platform; hallmark feature is automated device/app provisioning triggered by role.
   Features page: https://www.rippling.com/blog/automated-onboarding-workflows

4. **HiBob (Bob)** — Mid-market HRIS with lifecycle-triggered onboarding workflows, cross-team task assignment, buddy assignment, and built-in eSign.
   Features page: https://www.hibob.com/features/onboarding/

5. **Personio** — European HR platform with reusable onboarding task templates, role-specific checklists, buddy info in welcome emails, and progress dashboard.
   Features page: https://www.personio.com/product/onboarding/

6. **Gusto** — Payroll-first SMB HR platform; onboarding checklists segmented by Before Day 1 / Day 1 / After Day 1, self-serve new hire portal, e-sign custom docs.
   Features page: https://gusto.com/product/hr/hiring-onboarding

7. **Click Boarding** — Purpose-built onboarding platform; drag-and-drop workflow builder, preboarding portal, eSignature, I-9/tax wizard, mentorship pairing, 250+ integrations.
   Features page: https://www.clickboarding.com/platform/onboarding/

8. **Enboarder** — Experience-oriented onboarding journey platform; AI-generated 30-60-90 day plans, manager nudges, multi-channel delivery (SMS/Slack/Teams), real-time completion dashboards.
   Features page: https://enboarder.com/employee-onboarding-automation/

9. **SAP SuccessFactors Onboarding 2.0** — Enterprise onboarding suite; structured onboarding programs with typed task categories (Equipment, Buddy, Schedule Meeting, Day One Prep, Welcome Message, Checklist), multi-group task assignment (IT/manager/HR/new hire), DocuSign/SAP eSign integration.
   Features page: https://blog.sap-press.com/sap-successfactors-onboarding-2-tasks-for-program-participants

10. **Sapling by Kallidus** — Dedicated onboarding platform with preboarding stage (company story/team intros), manager tasks, IT provisioning hooks (G Suite/AD), bulk onboarding, ATS integration (Lever).
    Features page: https://kallidus.zendesk.com/hc/en-us/articles/360018810238-Sapling-Preboarding

11. **Workable** — ATS-led HRIS with onboarding workflows, configurable task types (welcome email, profile info, document sign, custom tasks), welcome message + video, mobile-friendly new hire portal, preboarding before start date.
    Features page: https://help.workable.com/hc/en-us/articles/9294190133399-Employee-onboarding-workflows

---

## Feature catalog by sub-module (NavERP.md 3.3)

---

### 3.3.A Onboarding Tasks

- **Reusable onboarding task templates** — A named template (e.g. "Engineering Onboarding") holds a library of task definitions; applying the template to a new hire generates a concrete instance with due dates and assignees. All 10 products surveyed offer this pattern.
  · priority: **[MVP]** (table-stakes — every leader offers it)
  · spine: NEW table `OnboardingTemplate` + `OnboardingTemplateTask`
  · buildable now

- **Task categories / types** — Tasks are typed: IT Setup, HR Admin, Manager Action, New Hire Action, Buddy Assignment, Document Sign, Equipment Request, Training, Meet & Greet, Custom. SAP SuccessFactors makes task types explicit objects; BambooHR, Gusto, Workable, HiBob all support custom task categories.
  · priority: **[MVP]**
  · spine: choice field `task_category` on `OnboardingTemplateTask` and `OnboardingTask`
  · buildable now

- **Multi-stakeholder task assignment** — Each task is assigned to a role (HR, IT, Manager, Buddy, New Hire) rather than a fixed person. HiBob, SAP SuccessFactors, Personio, and Click Boarding all expose this. The concrete user filling that role is resolved at instance creation time.
  · priority: **[MVP]**
  · spine: `assignee_role` choice + `assignee` FK to `accounts.User` (nullable, resolved at instance time) on `OnboardingTask`
  · buildable now

- **Due-date offsets from start date** — Template tasks carry a relative offset (e.g., -3 = 3 days before start, 0 = start date, +7 = 1 week after). Gusto calls this "Before Day 1 / Day 1 / After Day 1"; Workable has "days before start date". All products support this.
  · priority: **[MVP]**
  · spine: `due_offset_days` IntegerField on `OnboardingTemplateTask`; absolute `due_date` on `OnboardingTask` (calculated at instance creation)
  · buildable now

- **Task status lifecycle** — Each task instance tracks: pending → in_progress → completed / skipped. Progress bar shown to HR on the program instance. BambooHR, HiBob, Workday, Workable all have this.
  · priority: **[MVP]**
  · spine: `status` choice on `OnboardingTask`; `completed_at` + `completed_by` FK
  · buildable now

- **Automated task reminders / nudges** — System sends email/notification reminders when tasks are overdue or approaching due date. Enboarder calls these "manager nudges"; HiBob, Rippling, Workday all have automated reminder cadences.
  · priority: **[Common]** (most leaders; requires notification system)
  · spine: no new table; hook into `core.Activity` or deferred email queue
  · integration/later (email dispatch is an integration concern; the due_date field makes it trivially addable later)

- **Progress tracking / completion percentage** — Program instance shows % tasks completed, overdue count, pending count. BambooHR has a visual progress bar; Workday, HiBob, Personio all surface a completion dashboard.
  · priority: **[MVP]**
  · spine: derived property on `OnboardingProgram` (aggregate query over `OnboardingTask.status`)
  · buildable now (property, no extra table)

- **30-60-90 day plan structure** — Phases aligned to first 30, 60, and 90 days with distinct task sets per phase. Enboarder generates AI-personalized plans; Rippling configures milestone check-ins; Paycom and SAP SuccessFactors support phased checklists. Represented as `phase` on the task.
  · priority: **[Differentiator]** (standout feature; a few leaders expose it explicitly)
  · spine: `phase` choice field (preboarding/week1/month1/month2/month3/ongoing) on `OnboardingTemplateTask` and `OnboardingTask`
  · buildable now (just a choice field; no new table)

- **Bulk / role-triggered onboarding** — Applying the same template to multiple hires at once, or auto-triggering when an employee is hired in a specific department/designation. Sapling supports bulk onboarding; Rippling auto-triggers from employment attributes.
  · priority: **[Differentiator]**
  · spine: no new table; a view action that creates multiple `OnboardingProgram` instances
  · buildable now (no model change needed; a utility function)

---

### 3.3.B Document Collection

- **Document collection checklist** — A list of documents the new hire must submit or sign (offer letter, NDA, tax form, ID proof, bank details form). BambooHR, Gusto, Workday, SAP SuccessFactors, Click Boarding all model this as an explicit list.
  · priority: **[MVP]**
  · spine: NEW table `OnboardingDocument` (FK to `OnboardingProgram`)
  · buildable now

- **Document types / categories** — Documents are typed: employment_contract, nda, offer_letter, id_proof, tax_form, bank_details, policy_acknowledgment, custom. SAP SuccessFactors, BambooHR, TriNet/Zenefits all distinguish document types.
  · priority: **[MVP]**
  · spine: `document_type` choice field on `OnboardingDocument`
  · buildable now

- **E-signature status tracking** — Track per-document whether it has been sent for signature, viewed, signed, or declined. BambooHR, Rippling (95% G2 rating for e-sign), HiBob, SAP SuccessFactors (DocuSign + SAP eSign), Click Boarding, TriNet, Workable all have this. Status: pending / sent / viewed / signed / declined.
  · priority: **[MVP]** (as a status field; actual signing integration is deferred)
  · spine: `esign_status` choice field on `OnboardingDocument`
  · buildable now for status tracking; actual DocuSign/HelloSign API call = integration/later

- **File upload for collected documents** — New hire uploads a scanned ID or signed form. Stored as a file attachment. BambooHR, Deel, Sapling all collect uploads.
  · priority: **[MVP]**
  · spine: `file` FileField on `OnboardingDocument` (or reuse `core.Document` via GenericFK)
  · buildable now (reuse core.Document for file storage is the spine-correct approach)

- **Document request deadline** — Each document in the collection list has a due date (often aligned to start date). HiBob, SAP SuccessFactors, Click Boarding expose this.
  · priority: **[Common]**
  · spine: `due_date` DateField on `OnboardingDocument`
  · buildable now

- **Digital form / data collection** — Beyond file uploads: structured forms the new hire fills in (personal details, bank info, emergency contact). Gusto's self-onboarding portal, BambooHR's new hire packet, Sapling's preboarding all include this. For NavERP, this is covered by the existing `EmployeeProfile` edit flow, not a separate form engine.
  · priority: **[Differentiator]** (full form engine is advanced)
  · spine: reuse `EmployeeProfile` edit view for structured data; no new table needed for this pass
  · deferred (custom form builder = later)

- **Full e-signature API integration** — DocuSign, HelloSign, or Adobe Sign integration so documents are sent, signed, and returned automatically. BambooHR uses Mitratech; SAP uses DocuSign; Click Boarding is API-first; Rippling has native eSign.
  · priority: **[Differentiator]** (few build this natively; most integrate)
  · spine: webhook/callback fields on `OnboardingDocument` (external_ref, signed_at) — stub fields only
  · integration/later

---

### 3.3.C Asset Allocation

- **Asset issuance checklist per new hire** — A list of physical items to issue: laptop, ID card, access card, phone, uniform, parking pass. SAP SuccessFactors has an explicit "Equipment List" task; Rippling auto-orders pre-configured devices; HiBob includes equipment in task lists; BambooHR and Sapling support equipment in checklists.
  · priority: **[MVP]**
  · spine: NEW table `AssetAllocation` (FK to `OnboardingProgram`)
  · buildable now

- **Asset item name + serial/tag** — What is being issued (laptop, ID card) + optional serial number or asset tag. SAP SuccessFactors "Request Equipment" task captures item name; Rippling tracks device serial; BambooHR/HiBob treat this as a task note. For NavERP, `AssetAllocation.asset_name` + optional `serial_number` covers MVP; integration with the future `assets.Asset` module is a deferred link.
  · priority: **[MVP]**
  · spine: `asset_name`, `serial_number`, `asset_tag` on `AssetAllocation`; optional `asset_id` FK to `core.Asset` (nullable — links to Module 11 later)
  · buildable now

- **Issuance status** — pending / issued / returned. Returned status is primarily relevant for offboarding (3.4) but the status field supports it now. SAP SuccessFactors, Rippling, BambooHR all track issuance state.
  · priority: **[MVP]**
  · spine: `status` choice field on `AssetAllocation`
  · buildable now

- **Issued-by / issued-date** — Records who issued the asset and when. BambooHR, SAP SuccessFactors track this in the checklist completion. Useful for audit.
  · priority: **[Common]**
  · spine: `issued_by` FK to `accounts.User` (nullable), `issued_at` DateTimeField on `AssetAllocation`
  · buildable now

- **IT system/software provisioning** — Auto-provisioning of email accounts, Slack, Salesforce, etc. by role. Rippling's differentiator: RBAC-based app provisioning fires on hire. TriNet/Zenefits also mentions app provisioning hooks. This is a third-party IT integration.
  · priority: **[Differentiator]** (Rippling hallmark; requires IT system APIs)
  · spine: no new table; could be a task category = "IT Provisioning" in `OnboardingTask`
  · integration/later (actual provisioning calls require external API; the task record captures the intent)

---

### 3.3.D Orientation Schedule

- **Orientation sessions (meetings/events)** — Named sessions (e.g. "HR Orientation", "IT Setup Walk-through", "Meet the Team Lunch") with date/time, location, and facilitator. SAP SuccessFactors "Schedule Meeting" task; Workday references structured milestones; HiBob adds "meet & greet schedules" as tasks; Sapling introduces key people on the People page; Click Boarding manages orientation activities.
  · priority: **[MVP]**
  · spine: NEW table `OrientationSession` (FK to `OnboardingProgram`)
  · buildable now

- **Session type** — training / meeting / department_intro / team_lunch / virtual / custom. HiBob, SAP SuccessFactors, Click Boarding all classify sessions by type.
  · priority: **[MVP]**
  · spine: `session_type` choice field on `OrientationSession`
  · buildable now

- **Facilitator assignment** — Who runs the session (FK to `accounts.User` or free-text for external trainers). SAP SuccessFactors and HiBob assign responsible users per session.
  · priority: **[Common]**
  · spine: `facilitator` FK to `accounts.User` (nullable) + `facilitator_name` CharField fallback
  · buildable now

- **Calendar/calendar invite integration** — Syncing sessions to Google Calendar / Outlook and sending invites. HiBob, Enboarder, Workable (video embed), Click Boarding mention calendar integration and MS Teams sync.
  · priority: **[Differentiator]**
  · spine: no new table; iCal export or calendar API call = integration/later
  · integration/later

- **Attendance / RSVP tracking** — Whether the new hire confirmed attendance and whether they attended. Click Boarding's engagement tracking; Enboarder's completion analytics.
  · priority: **[Common]**
  · spine: `attendance_status` choice (scheduled / attended / missed) on `OrientationSession`
  · buildable now

---

### 3.3.E Welcome Kit

- **Welcome message (rich-text)** — A personalized welcome note from the manager or CEO, displayed in the new hire portal. Workable has a configurable welcome message + video embed; Sapling's preboarding shows a Company Story page; Personio sends a personalized welcome email; Enboarder and Appical both deliver digital welcome experiences.
  · priority: **[MVP]**
  · spine: NEW table `OnboardingWelcomeKit` (1:1 or 1:many with `OnboardingProgram`; simplest: fields on `OnboardingProgram` itself — `welcome_message` TextField, `welcome_video_url`)
  · buildable now (fields on OnboardingProgram, no extra table)

- **Policy documents list** — A curated list of company policy documents (employee handbook, code of conduct, IT policy, safety policy) linked to the onboarding program. BambooHR's new hire packet, Workable's "view document" task, SAP SuccessFactors recommended links, Sapling's Company Introduction page all include policy/resource links.
  · priority: **[MVP]**
  · spine: `OnboardingDocument` with `document_type = 'policy_acknowledgment'` covers this; alternatively, a `policy_url` / `policy_file` on `OnboardingWelcomeKit` — reuse `OnboardingDocument` to avoid a second table
  · buildable now (reuse OnboardingDocument model with type=policy)

- **First-day information** — What to bring, where to go, parking info, dress code, first-day schedule. SAP SuccessFactors "Prepare for Day One" task with manager notes; Workable's welcome message; Personio welcome email; BambooHR new hire packet.
  · priority: **[MVP]**
  · spine: `first_day_notes` TextField on `OnboardingProgram` (or welcome kit section)
  · buildable now

- **Buddy / mentor assignment** — Assign a peer buddy to the new hire for social integration. HiBob tasks include "assign buddy"; SAP SuccessFactors "Assign a Buddy" task with personal note; Personio shows buddy in welcome email; Enboarder auto-triggers buddy briefing before day one; Click Boarding has mentorship facilitation.
  · priority: **[Common]** (most leaders have it; varies in depth)
  · spine: `buddy` FK to `hrm.EmployeeProfile` (nullable) on `OnboardingProgram`
  · buildable now

- **Org chart / team introduction** — Who's who in the team; Sapling's "People page" shows manager + department; HiBob's team org chart; BambooHR's employee directory.
  · priority: **[Differentiator]** (requires org chart UI)
  · spine: reuses existing `core.OrgUnit` + `hrm.EmployeeProfile` directory; no new table
  · buildable now as a link to existing pages; dedicated org chart view = later

- **Video welcome message** — CEO or manager records a video welcome. Workable supports YouTube/Vimeo embed URL; Enboarder and Appical both cite video welcome as a best practice.
  · priority: **[Differentiator]**
  · spine: `welcome_video_url` URLField on `OnboardingProgram`
  · buildable now (one field; video hosting/recording itself is external)

- **New hire self-service portal** — A dedicated page the new hire sees with all their tasks, documents to sign, and orientation schedule. BambooHR (new hire packet), Workday (self-service portal), Gusto (dashboard notification + self-onboard), Workable (onboarding website), Sapling (preboarding stages), Click Boarding (mobile-first portal), Enboarder (multi-channel journey).
  · priority: **[Differentiator]** (strong differentiator; requires a "new hire view" separate from HR admin view)
  · spine: no new model; a filtered view of `OnboardingProgram` and its related tasks/documents
  · buildable now (a dedicated template showing the hire's own program — possible in this pass)

---

## Mapping to unified core spine

### Entities that REUSE the existing spine

| Core entity | Onboarding use |
|-------------|---------------|
| `hrm.EmployeeProfile` | The anchor — `OnboardingProgram.employee` FKs here (the person being onboarded). `buddy` FK also points here. |
| `core.OrgUnit` | Used via `EmployeeProfile.department` (through `core.Employment`); orientation sessions can reference it for room/location. |
| `hrm.Designation` | Used via `EmployeeProfile.designation` to select the correct `OnboardingTemplate` (templates are optionally linked to a designation). |
| `accounts.User` | `OnboardingTask.assignee`, `OrientationSession.facilitator`, `AssetAllocation.issued_by` all FK to User. |
| `core.Document` (GenericFK) | `OnboardingDocument` can store its `file` via `core.Document` (GenericFK pointing at `OnboardingProgram`) rather than a raw FileField — spine-correct approach. For this pass, a direct FileField is acceptable and simpler. |
| `core.Tenant` | All new models carry `tenant` FK via `TenantOwned` abstract base. |

### Entities that are NEW (HRM-owned, onboarding sub-domain)

| New model | Rationale |
|-----------|-----------|
| `OnboardingTemplate` | Reusable named template; stores default tasks for a role/designation |
| `OnboardingTemplateTask` | Line item in a template: category, name, assignee_role, due_offset_days, phase |
| `OnboardingProgram` | One instance per hire: FK to EmployeeProfile, template used, status, start_date, welcome fields, buddy |
| `OnboardingTask` | Concrete task on a program: FK to OnboardingProgram, assignee User, due_date, status, completed_at |
| `OnboardingDocument` | Document to collect or sign: type, esign_status, file, due_date |
| `AssetAllocation` | Physical asset issued to the hire: asset_name, serial_number, status, issued_by |
| `OrientationSession` | Scheduled meeting/training: session_type, facilitator, scheduled_at, location, attendance_status |

Note: `OnboardingTemplate` + `OnboardingTemplateTask` together are the "template" side; `OnboardingProgram` + `OnboardingTask` are the "instance" side. This mirrors the Rippling / Personio / SAP SuccessFactors template-then-instance pattern universally used.

---

## Recommended build scope (this pass — 7 models)

### Model 1: `OnboardingTemplate` [ONB-T-]
**Fields:**
- `tenant` FK (`TenantOwned`)
- `name` CharField(255) — e.g. "Engineering New Hire"
- `description` TextField(blank=True)
- `designation` FK → `hrm.Designation` (null/blank — makes this template the default for that role)
- `is_active` BooleanField(default=True)
- `number` auto via `TenantNumbered` (NUMBER_PREFIX = "ONBT-")

**Justification:** Rippling, Personio, SAP SuccessFactors, HiBob, Workable all use named reusable templates that can be associated with a role/department. The `designation` link lets HR auto-suggest the right template when onboarding a new hire with that job title.

---

### Model 2: `OnboardingTemplateTask` (no number; child of template)
**Fields:**
- `tenant` FK (`TenantOwned`)
- `template` FK → `OnboardingTemplate`
- `title` CharField(255)
- `description` TextField(blank=True)
- `task_category` choice: hr_admin / it_setup / manager_action / buddy_action / new_hire_action / document_sign / equipment_request / training / meet_greet / custom
- `assignee_role` choice: hr / it / manager / buddy / new_hire
- `due_offset_days` IntegerField(default=0) — negative = before start date
- `phase` choice: preboarding / week_1 / month_1 / month_2 / month_3 / ongoing
- `order` PositiveIntegerField(default=0) — display sort order

**Justification:** Gusto's "Before Day 1 / Day 1 / After Day 1" segmentation, SAP SuccessFactors typed task categories, HiBob's multi-stakeholder assignment, and Enboarder's 30-60-90 phasing all map to these fields.

---

### Model 3: `OnboardingProgram` [ONB-]
**Fields:**
- `tenant` FK (`TenantOwned`)
- `number` auto via `TenantNumbered` (NUMBER_PREFIX = "ONB-")
- `employee` FK → `hrm.EmployeeProfile`
- `template` FK → `OnboardingTemplate` (null/blank — template used, kept for reference)
- `start_date` DateField — the hire's actual start date (drives due_date calculations)
- `status` choice: draft / active / completed / cancelled
- `buddy` FK → `hrm.EmployeeProfile` (null/blank, related_name="buddy_for")
- `welcome_message` TextField(blank=True) — rich text / markdown
- `welcome_video_url` URLField(blank=True)
- `first_day_notes` TextField(blank=True)
- `completed_at` DateTimeField(null=True, blank=True)
- `unique_together = (tenant, employee)` — one active program per employee per tenant (or enforce via `clean()`)

**Justification:** Every surveyed product has a "program instance" anchored to the employee and a start date. The welcome fields (message, video, first-day notes) implement the Welcome Kit feature. `buddy` implements the buddy assignment feature visible in HiBob, SAP SuccessFactors, Personio, and Enboarder.

**Spine note:** The `employee` FK to `EmployeeProfile` is the correct spine anchor per the HRM skill. A design consideration for preboarding (before the employee record exists) is noted as a deferral — for this pass, we require a pre-existing `EmployeeProfile`.

---

### Model 4: `OnboardingTask`
**Fields:**
- `tenant` FK (`TenantOwned`)
- `program` FK → `OnboardingProgram`
- `title` CharField(255)
- `description` TextField(blank=True)
- `task_category` choice (same as TemplateTask)
- `assignee_role` choice (same as TemplateTask)
- `assignee` FK → `settings.AUTH_USER_MODEL` (null/blank — resolved at instance creation)
- `due_date` DateField(null=True, blank=True) — calculated from program.start_date + template task offset
- `phase` choice (same as TemplateTask)
- `status` choice: pending / in_progress / completed / skipped
- `completed_at` DateTimeField(null=True, blank=True)
- `completed_by` FK → `settings.AUTH_USER_MODEL` (null/blank, related_name="completed_onboarding_tasks")
- `notes` TextField(blank=True)
- `order` PositiveIntegerField(default=0)

**Justification:** BambooHR progress bar, Workday to-do lists, HiBob completion tracking, Workable task status all converge on this shape. The `completed_by` field satisfies audit requirements (who ticked it off). `assignee_role` is kept alongside `assignee` so HR can see "IT should own this" even if no specific user is assigned.

---

### Model 5: `OnboardingDocument`
**Fields:**
- `tenant` FK (`TenantOwned`)
- `program` FK → `OnboardingProgram`
- `document_type` choice: employment_contract / nda / offer_letter / id_proof / tax_form / bank_details / policy_acknowledgment / background_check / custom
- `title` CharField(255) — friendly name
- `description` TextField(blank=True) — instructions to new hire
- `file` FileField(upload_to="onboarding/docs/", blank=True) — HR-uploaded template or collected file
- `esign_status` choice: not_required / pending / sent / viewed / signed / declined
- `due_date` DateField(null=True, blank=True)
- `signed_at` DateTimeField(null=True, blank=True)
- `external_ref` CharField(max_length=255, blank=True) — DocuSign envelope ID stub for future integration

**Justification:** BambooHR e-sign (I-9, W-4, custom docs), Gusto document collection, SAP SuccessFactors document workflows, Click Boarding eSignature, TriNet/Zenefits paperless onboarding, Deel compliance document upload all map to this model. `esign_status` tracks the signing lifecycle without requiring a live DocuSign integration now. `external_ref` stubs the integration hook. Policy documents reuse `document_type = policy_acknowledgment`, avoiding a separate welcome-kit document table.

---

### Model 6: `AssetAllocation` [AST-]
**Fields:**
- `tenant` FK (`TenantOwned`)
- `number` auto via `TenantNumbered` (NUMBER_PREFIX = "AST-")
- `program` FK → `OnboardingProgram`
- `asset_name` CharField(255) — "MacBook Pro 14", "ID Card", "Access Card"
- `asset_category` choice: laptop / desktop / phone / id_card / access_card / uniform / vehicle / other
- `serial_number` CharField(max_length=100, blank=True)
- `asset_tag` CharField(max_length=100, blank=True)
- `asset_id` FK → (nullable) — stub for future `assets.Asset` module link (Module 11); use `null=True, blank=True` and string reference `'core.Asset'` or defer as CharField for now
- `status` choice: pending / issued / returned
- `issued_at` DateTimeField(null=True, blank=True)
- `issued_by` FK → `settings.AUTH_USER_MODEL` (null/blank)
- `return_due_date` DateField(null=True, blank=True) — for offboarding use
- `notes` TextField(blank=True)

**Justification:** SAP SuccessFactors "Request Equipment" / "Equipment List" task, Rippling device provisioning + inventory tracking, HiBob equipment task, BambooHR IT checklist, TriNet app-provisioning hooks all converge on tracking what physical items were assigned to the new hire. The `AST-` number prefix was specified in the task prompt. The `asset_id` nullable FK stubs the eventual link to the Module 11 Asset Management module without creating a circular dependency now.

---

### Model 7: `OrientationSession`
**Fields:**
- `tenant` FK (`TenantOwned`)
- `program` FK → `OnboardingProgram`
- `title` CharField(255) — "HR Orientation", "IT Setup Walk-through", "Meet the Team"
- `session_type` choice: training / department_intro / team_meeting / virtual / social / custom
- `facilitator` FK → `settings.AUTH_USER_MODEL` (null/blank)
- `facilitator_name` CharField(max_length=255, blank=True) — free-text for external trainers
- `scheduled_at` DateTimeField(null=True, blank=True)
- `duration_minutes` PositiveIntegerField(null=True, blank=True)
- `location` CharField(max_length=255, blank=True) — room name, "Zoom", "Building A Room 3"
- `meeting_url` URLField(blank=True) — Zoom/Teams link
- `attendance_status` choice: scheduled / attended / missed / rescheduled
- `notes` TextField(blank=True)

**Justification:** SAP SuccessFactors "Schedule Meeting" task, HiBob "meet & greet schedules", Click Boarding orientation activities, Workable welcome video + portal, Sapling People page introductions. The `meeting_url` field supports the common pattern (Workable, Workday, Click Boarding) of embedding virtual meeting links. `attendance_status` tracks completion without requiring a full calendar integration.

---

## Deferred (later passes / integrations)

- **Real e-signature API integration** (DocuSign, HelloSign, Adobe Sign) — The `esign_status` field and `external_ref` stub are in place. The webhook/callback handler is a later integration pass. Seen in: BambooHR (Mitratech), SAP SuccessFactors (DocuSign), Rippling (native). Requires external API keys + webhook endpoint.

- **Preboarding before EmployeeProfile exists** — The research shows preboarding (after offer acceptance, before start date) is a common pattern. For NavERP 3.3, `OnboardingProgram` requires an existing `EmployeeProfile` (created when the offer is accepted in 3.8). True candidate-stage preboarding — where no EmployeeProfile exists yet — requires the ATS/Recruiting modules (3.5–3.8) to be built first. Deferred to the ATS pass.

- **Offboarding / asset return tracking** — The `AssetAllocation.status = returned` field and `return_due_date` stub the data model. Full offboarding workflows (resignation, clearance, F&F) belong to 3.4 and are out of scope.

- **Automated task reminders / nudges via email** — The due-date data is all present. The email dispatch (Celery task or Django send_mail scheduled job) requires the background task infrastructure. Deferred to a notifications pass.

- **Calendar invite integration** (Google Calendar / Outlook) — `OrientationSession.meeting_url` stores the link. Actual iCal/CalDAV API calls require OAuth and are an integration-later item.

- **IT system provisioning automation** — Rippling's hallmark: auto-provisioning Slack, email, Salesforce via role. The `OnboardingTask` with `task_category = it_setup` records the intent; the actual API calls to 500+ apps require each integration. Deferred.

- **AI-generated 30-60-90 day plans** — Enboarder's differentiator: AI reads job description + resume to generate a personalized plan. The `phase` field on `OnboardingTask` supports phases. AI generation requires an LLM integration pass.

- **New hire self-service portal** — A dedicated new-hire-facing view (separate from HR admin view) showing only the hire's own program, tasks, and documents. The data model fully supports this. Deferred to an employee self-service / ESS pass (see 3.25 Personal Information in NavERP.md). It is a template + view, not a model change.

- **Bulk / role-triggered auto-onboarding** — Auto-triggering an OnboardingProgram when an Employment is created with a specific Designation. Can be a Django signal or a management command; deferred to a workflow automation pass.

- **Custom digital form builder** — Structured forms for the new hire to fill in arbitrary data fields (beyond what EmployeeProfile already captures). Gusto and BambooHR have this. Requires a form-builder model (dynamic fields). Deferred — out of scope for this pass.

- **Background verification integration** — Deel, SAP SuccessFactors, Workable (3.8) mention BGV vendor integration. Belongs to the Offer Management (3.8) pass.

- **Policy acknowledgment workflow** — Tracking that the new hire read and acknowledged each policy. Currently modeled as `OnboardingDocument(document_type=policy_acknowledgment, esign_status=signed)`. A richer workflow (acknowledgment timestamp, digital signature, version tracking) is a later compliance pass.

- **Link `AssetAllocation` to Module 11 `assets.Asset`** — The `asset_id` field is stubbed as a note. Once Module 11 (Asset Management) is built, add the FK migration to create the real relation.

---

## Source references

- BambooHR onboarding: https://www.bamboohr.com/blog/bamboohr-review-onboarding-software
- Workday onboarding plans: https://www.workday.com/en-us/products/talent-management/onboarding-plans.html
- Rippling automated onboarding: https://www.rippling.com/blog/automated-onboarding-workflows
- HiBob onboarding: https://www.hibob.com/features/onboarding/ and https://www.hibob.com/blog/onboarding-automation-using-task-lists/
- Personio onboarding: https://www.personio.com/product/onboarding/ and https://support.personio.de/hc/en-us/articles/115002474325-Best-Practice-Onboarding-Templates-and-Steps
- Gusto onboarding: https://gusto.com/product/hr/hiring-onboarding and https://support.gusto.com/article/210728175340400/view-and-complete-onboarding-checklists-for-admins
- Click Boarding: https://www.clickboarding.com/platform/onboarding/
- Enboarder: https://enboarder.com/employee-onboarding-automation/
- SAP SuccessFactors Onboarding 2.0: https://blog.sap-press.com/sap-successfactors-onboarding-2-tasks-for-program-participants
- Sapling by Kallidus: https://kallidus.zendesk.com/hc/en-us/articles/360018810238-Sapling-Preboarding
- Workable: https://help.workable.com/hc/en-us/articles/9294190133399-Employee-onboarding-workflows
- G2 onboarding software overview: https://learn.g2.com/best-onboarding-software
- TriNet (formerly Zenefits): https://www.trinet.com/hr-plus/hr-platform/features
