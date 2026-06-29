# Research — Module 3.6: Candidate Management (hrm — candidate management sub-module)

## Leaders surveyed (with source links)

1. **Greenhouse** — Structured-hiring ATS; industry leader for mid-market/enterprise with 500+ integrations — https://www.greenhouse.com/features
2. **Lever (now LeverTRM by Employ Inc.)** — ATS + CRM combined ("TRM" = Talent Relationship Management); strong nurture & pipeline — https://www.lever.co/
3. **Workable** — All-in-one HR/ATS for SMBs; AI-powered parsing, branded career site, 200+ job boards — https://www.workable.com/features
4. **Zoho Recruit** — Feature-rich SMB ATS; detailed standard field taxonomy, career portal, resume parsing — https://www.zoho.com/recruit/candidate-management.html
5. **iCIMS** — Enterprise ATS; candidate CRM (CXM), multi-channel communication, AI sourcing — https://www.icims.com/glossary/applicant-tracking-system-ats/
6. **Ashby** — Modern all-in-one ATS; structured profiles, GDPR consent management, diversity data, fraud detection — https://docs.ashbyhq.com/candidate-profile
7. **Teamtailor** — Employer-branding-forward ATS; talent pool "Connect" subscriptions, GDPR auto-removal, WhatsApp — https://www.teamtailor.com/en/all-features/
8. **BambooHR ATS** — HRM-native ATS; career portal, simple pipeline, offer letters — https://www.bamboohr.com/platform/applicant-tracking-system/
9. **SmartRecruiters (now SAP)** — Enterprise ATS; GDPR-native, multi-language career site, structured hiring — https://www.smartrecruiters.com/resources/gdpr-recruiting/recruitment-gdpr-faq/
10. **Breezy HR / JazzHR** — SMB ATS with drag-and-drop Kanban pipeline, custom stages, email+SMS templates — https://breezy.hr/qualify

Additional reference: G2 ATS category leaders 2026 — https://www.g2.com/categories/applicant-tracking-systems-ats

---

## Feature catalog by sub-module

### 3.6.1 Application Portal (Career Page + Job Application Form)

- **Branded career/jobs page** — A public tenant-branded page listing all open (posted) JobRequisitions with search/filter; clicking a job shows the JD and an "Apply Now" button that opens the application form. Seen in: Greenhouse, Workable, Teamtailor, Zoho Recruit, BambooHR, SmartRecruiters, Breezy HR, JazzHR. Priority: **table-stakes** · Spine: new view over existing `hrm.JobRequisition` (posted ones); no new model needed for the listing page itself · Buildable now.

- **Online application form (web-to-candidate)** — Public unauthenticated form per job posting that collects: First Name, Last Name, Email, Phone, LinkedIn URL, City/Location, Resume/CV (file upload), Cover Letter (optional textarea or file), "How did you hear about this role?" (source picklist), optional custom screening questions per role, GDPR consent checkbox. Mirrors the CRM web-to-lead form pattern. Seen in: all 10 products. Priority: **table-stakes** · Spine: creates a `Candidate` (Party + PartyRole 'candidate') and a `JobApplication` linked to the `JobRequisition` · Buildable now.

- **CAPTCHA / bot protection on the application form** — Prevents spam submissions. Seen in: Zoho Recruit (explicit), Greenhouse, Workable. Priority: **common** · Spine: middleware/form validation, no model change · Integration/later (django-recaptcha).

- **Mobile-optimized, account-optional application** — Candidates can apply without creating a portal account; mobile-friendly single-page form. Teamtailor calls out that not requiring account creation significantly increases completion rates. Seen in: Teamtailor, Workable, BambooHR. Priority: **common** · Spine: no model change; the form POSTs anonymously · Buildable now.

- **Application acknowledgment email (auto-send)** — On successful application submission, an automated "application received" email is sent to the candidate's email address. Seen in: all 10 products. Priority: **table-stakes** · Spine: triggers a `CandidateCommunication` log row (new table) + Django email send · Buildable now (Django email, no external service needed for demo).

- **Candidate self-service status check** — A lightweight token-emailed link letting a candidate view their application status without a full portal login. Seen in: Greenhouse (MyGreenhouse), iCIMS, Zoho Recruit. Priority: **differentiator** · Spine: `JobApplication.status` field + a signed URL token · Deferred (complex token/session management; prioritize the core model first).

---

### 3.6.2 Resume Parser

- **Resume/CV file upload + text extraction** — Accept PDF/DOCX resume on the application form; extract raw text. Seen in: all 10 products. Priority: **table-stakes** · Spine: `Candidate.resume_file` (FileField); raw text stored in `Candidate.resume_text` (TextField) · Buildable now (file upload; full NLP parsing deferred).

- **Auto-populate candidate fields from resume** — On upload, a parser extracts and pre-fills structured fields: First Name, Last Name, Email, Phone, Current Job Title, Current Employer, LinkedIn URL, City/Location, Years of Experience (numeric), Highest Qualification, Skill Set (comma-delimited), Education (institution, degree, major). Zoho Recruit's standard field taxonomy is the most complete reference. Seen in: Greenhouse, Workable, Lever, Zoho Recruit, iCIMS, Ashby, Teamtailor. Priority: **table-stakes** · Spine: maps to `Candidate` profile fields (new table) + `CandidateSkill` for structured skills · Integration/later (requires a third-party parsing library like pyresparser, Affinda, or Sovren; for this pass, store raw text and let recruiters fill fields manually or via a simple regex extraction stub).

- **Skills extraction and structured skill tagging** — Parsed skills are stored as discrete tags/records (not just a flat text field), enabling filter-by-skill search. Seen in: Greenhouse, Workable, Zoho Recruit, Lever, Ashby. Priority: **common** · Spine: `CandidateSkill` new table (candidate → skill name, proficiency, source='parsed'|'manual') · Buildable now.

- **Education and work history structured parsing** — Separate structured records for each education entry (institution, degree, field, start/end year) and each work experience entry (company, title, start/end date). Seen in: Zoho Recruit (most explicit field taxonomy), Greenhouse, Lever. Priority: **common** · Spine: `CandidateEducation` + `CandidateExperience` child tables off `Candidate` · Deferred (adds 2 more models; out of scope for a single pass — store as free-text fields on `Candidate` for now and add structured child tables in a later pass).

- **Duplicate candidate detection** — When a new application arrives (from the portal or manual entry), the system checks for an existing `Candidate` with the same email and surfaces a merge/link suggestion rather than creating a duplicate. Seen in: Greenhouse, Lever, Workable, Ashby. Priority: **common** · Spine: unique constraint on `Candidate.email`; service function checks before creating · Buildable now.

---

### 3.6.3 Candidate Database (Talent Pool + Candidate Profiles)

- **Candidate record (Person profile)** — The central entity for a person who has applied or been sourced. Fields: first_name, last_name, email (unique per tenant), phone, mobile, linkedin_url, current_job_title, current_employer, city, country, years_of_experience (decimal), highest_qualification, skill_set (free text), resume_file, resume_text, gender (for diversity), source, gdpr_consent (bool), gdpr_consent_date, notes, photo (optional). Reuses `core.Party` (kind='person') as the identity anchor via a `CandidateProfile` 1:1 extension — exactly mirroring how `EmployeeProfile` extends `Party`. A `PartyRole(role='candidate')` marks the Party as a candidate. Seen in: all 10 products (Zoho Recruit's standard fields are the canonical reference). Priority: **table-stakes** · Spine: reuse `core.Party` + `core.PartyRole(role='candidate')`; add `hrm.CandidateProfile` as a 1:1 extension (mirrors `hrm.EmployeeProfile`) · Buildable now.

- **Candidate status / lifecycle state** — The candidate-level status (independent of any specific job application): `active`, `inactive`, `hired`, `blacklisted`, `do_not_contact`. Distinct from the `JobApplication.stage`. Seen in: Greenhouse, Zoho Recruit (Candidate Status field), Lever, Workable. Priority: **table-stakes** · Spine: `CandidateProfile.status` field · Buildable now.

- **Talent pool / saved searches / tags** — Tags or labels applied to a candidate record to organize them into pools (e.g. "Python Engineer Pool", "Strong Culture Fit", "Re-engage Q4"). Multiple tags per candidate. Used to group candidates for targeted outreach even when no open requisition exists. Seen in: Greenhouse (tags on profile header), Ashby (tags), Workable (tag+categorize), Teamtailor (custom tags + "Connect" interest subscriptions), Lever (tag-based search). Priority: **table-stakes** · Spine: `CandidateTag` new table (tenant, candidate_profile, name) OR M2M through tag-name model. Simple M2M via a `Tag` catalog table · Buildable now.

- **Activity / communication timeline** — A chronological log of every interaction with a candidate: notes added by recruiters, emails sent/received, stage changes, communications. Reuses `core.Activity` (kind=email|note|call|meeting with GenericFK pointing at the `CandidateProfile`). Seen in: Greenhouse (Notes tab, Tasks/Reminders tab), Ashby, Lever, Workable. Priority: **table-stakes** · Spine: reuse `core.Activity` with GenericFK → `CandidateProfile` · Buildable now.

- **Document attachments on candidate** — Attach files to a candidate profile (resume, cover letter, portfolio, ID). Reuses `core.Document` GenericFK → `CandidateProfile`. Seen in: Greenhouse (Application Details tab: documents), Ashby (resume + other files with public/private setting), Workable. Priority: **table-stakes** · Spine: reuse `core.Document` (GenericFK already supports this) · Buildable now.

- **Referral tracking (who referred this candidate)** — A field on the `CandidateProfile` or `JobApplication` capturing the referring employee's name/ID. Seen in: Greenhouse ("Referrals Over Time Report"), Ashby (credited user, referral info), Teamtailor, Workable (employee referral program). Priority: **common** · Spine: `JobApplication.referred_by` FK → `hrm.EmployeeProfile` (nullable) · Buildable now.

- **Candidate "Do Not Contact" / opt-out flag** — Marks a candidate as opted out of all communications; suppresses automated emails. Zoho Recruit calls this "E-mail Opt-Out"; Ashby calls it "Do Not Contact". Seen in: Zoho Recruit, Ashby, Workable, Greenhouse. Priority: **common** · Spine: `CandidateProfile.do_not_contact` BooleanField · Buildable now.

- **GDPR data retention and right-to-be-forgotten** — Consent captured on application (checkbox + timestamp). Configurable auto-delete or anonymize candidate data after a retention window (e.g. 6 months post-rejection). Seen in: Teamtailor (auto-remove + privacy center), SmartRecruiters, Ashby (consent capture + custom rules), Greenhouse. Priority: **common** · Spine: `CandidateProfile.gdpr_consent` + `gdpr_consent_date` + `gdpr_consent_expires` fields; a management command or scheduled task to anonymize expired records · Buildable now (consent fields); scheduled anonymization deferred.

---

### 3.6.4 Resume Search

- **Full-text search across candidate profiles** — Search the candidate database by keyword across name, job title, employer, skill set, resume text, notes. Seen in: all 10 products. Priority: **table-stakes** · Spine: Django ORM Q() search across `CandidateProfile` fields + `resume_text`; can use `__icontains` for demo; PostgreSQL full-text search with `SearchVector` as an upgrade · Buildable now.

- **Filter by source** — Filter the candidate list by how they came in (careers page, referral, LinkedIn, Indeed, agency, etc.). Seen in: Greenhouse (source quality report), Workable, Zoho Recruit, iCIMS. Priority: **table-stakes** · Spine: `JobApplication.source` CharField with choices · Buildable now.

- **Filter by application stage** — Filter the candidate list or pipeline view by current stage (Applied, Screening, Interview, Offer, Hired, Rejected). Seen in: all 10 products. Priority: **table-stakes** · Spine: `JobApplication.stage` CharField with choices · Buildable now.

- **Filter by years of experience** — Numeric range filter (e.g. 3–7 years) over `CandidateProfile.years_of_experience`. Seen in: Zoho Recruit (field: "Experience in Years"), iCIMS, Workable. Priority: **common** · Spine: `CandidateProfile.years_of_experience` DecimalField · Buildable now.

- **Filter/search by skill tags** — Filter candidates by one or more skill tags from `CandidateSkill`. Seen in: Greenhouse, Workable, Zoho Recruit, Lever (tag-based search is explicit for Lever). Priority: **common** · Spine: filter on M2M `CandidateSkill.skill_name` · Buildable now.

- **Filter by location (city/country)** — Filter candidates by city or country. Seen in: Zoho Recruit (City, State, Country fields), Workable, iCIMS. Priority: **common** · Spine: `CandidateProfile.city` + `CandidateProfile.country` fields · Buildable now.

- **Filter by job requisition applied to** — Show all candidates who applied to a specific `JobRequisition`. Seen in: all 10 products. Priority: **table-stakes** · Spine: `JobApplication.requisition` FK · Buildable now.

- **Candidate comparison / side-by-side view** — Select 2–3 candidates and view their profiles side-by-side. Seen in: Teamtailor (explicit "comparison tool"), Greenhouse. Priority: **differentiator** · Spine: template-level feature, no new model · Deferred (non-trivial template work; not in first pass).

- **Talent rediscovery / re-match** — Auto-suggest past applicants for a newly posted requisition based on skill/experience overlap. Seen in: Lever, Workable (AI-powered), urecruits.com top-10 feature list (explicit "Talent Rediscovery Engine"). Priority: **differentiator** · Spine: algorithmic matching across `CandidateSkill` + `JobRequisition.jd_requirements`; requires AI/ML layer · Deferred (integration/later).

---

### 3.6.5 Candidate Communication

- **Email template library** — A tenant-scoped catalog of reusable email templates for recurring recruiting communications: Application Received, Application Shortlisted, Phone Screen Invitation, Interview Invitation (maps to 3.7 but only the invite send is relevant here), Stage Advance Notification, Application Rejected, Application on Hold, Request for More Information. Seen in: Greenhouse, Workable, Lever, Zoho Recruit, Ashby, BambooHR, Breezy HR, iCIMS. Priority: **table-stakes** · Spine: `CandidateEmailTemplate` new table (tenant, name, subject, body_html, template_type choices, is_active) · Buildable now.

- **Candidate communication log** — An append-only record of every email sent to a candidate through the system: who sent it, when, which template was used, subject, and a reference back to the `JobApplication`. Distinct from `core.Activity` (which is broader); this is a typed email log. Can reuse `core.Activity(kind='email')` with GenericFK → `JobApplication` or `CandidateProfile`. Seen in: Greenhouse (Notes tab — email history), Ashby (email communication log), Lever, Workable. Priority: **table-stakes** · Spine: reuse `core.Activity(kind='email')` with GenericFK → `CandidateProfile`; add a FK to `CandidateEmailTemplate` (nullable) on the Activity row via a `CandidateCommunication` wrapper model · Buildable now.

- **Send email from application detail** — From the `JobApplication` detail view, HR can select a template, customize the message, and send to the candidate's email with the communication logged. Mirrors the CRM email-send-from-record pattern. Seen in: all 10 products. Priority: **table-stakes** · Spine: view action on `JobApplication` + Django email send + `CandidateCommunication` log write · Buildable now (Django SMTP).

- **Interview invite communication** — A lightweight "invite to interview" action on a `JobApplication` that sends the candidate a message (from template) with date/time and location/link. This is the communication touchpoint only — the full panel setup, scorecard, and scheduling live in 3.7 Interview Process. Seen in: Greenhouse (candidate availability requests in Tasks tab), Lever, Workable, Ashby. Priority: **table-stakes** (the communication part) · Spine: `CandidateCommunication` log; the `JobApplication.stage` advances to 'interview_scheduled'; interview scheduling detail deferred to 3.7 · Buildable now.

- **Bulk email to candidate segment** — Select multiple candidates (by filter/tag/pool) and send a templated email to all at once. Seen in: Teamtailor (bulk messaging), iCIMS (email campaigns via CXM), Workable. Priority: **common** · Spine: view action iterating over filtered `CandidateProfile` queryset + bulk CandidateCommunication log writes · Buildable now (no external service for demo; real bulk send deferred to integration).

- **Automated stage-change notification emails** — When a `JobApplication.stage` transitions (e.g. Applied → Screening, Screening → Rejected), the system auto-sends the mapped template to the candidate. Seen in: Greenhouse (stage transitions trigger automated notifications), Workable, Lever, Breezy HR. Priority: **common** · Spine: `post_save` signal or service function on `JobApplication`; maps stage → `CandidateEmailTemplate.template_type` · Buildable now (signal + Django email).

- **Candidate SMS / WhatsApp communication** — Alternative communication channels beyond email. Teamtailor offers WhatsApp; Workable offers SMS with "98% response rate" claim. Priority: **differentiator** · Spine: `CandidateCommunication.channel` choices ('email'|'sms'|'whatsapp'); actual send deferred to Twilio/WhatsApp API integration · Deferred.

---

## Recommended build scope (this pass — 6 models)

These 6 models cover all five NavERP 3.6 bullets with a clean, list-page-per-model structure and sufficient field depth for a realistic first pass.

---

### 1. `CandidateProfile` [CAND-]
**What it is:** The HRM candidate record — a 1:1 extension of `core.Party` (kind='person'), exactly mirroring `hrm.EmployeeProfile`. A `core.PartyRole(role='candidate')` is created alongside it. The `party` OneToOneField is the identity anchor.

**Fields (justified by research):**
- `tenant` FK → `core.Tenant`
- `number` CharField `CAND-#####` (auto, unique per tenant)
- `party` OneToOneField → `core.Party` (the person; name/email/phone live on Party/ContactMethod)
- `first_name`, `last_name` CharField (denormalized for fast display without joining Party)
- `email` EmailField (unique per tenant — duplicate detection anchor)
- `phone` CharField
- `linkedin_url` URLField
- `current_job_title` CharField
- `current_employer` CharField
- `city` CharField
- `country` CharField (ISO-3166 2-letter)
- `years_of_experience` DecimalField(max_digits=4, decimal_places=1)
- `highest_qualification` CharField (choices: high_school / diploma / bachelors / masters / phd / other)
- `skill_set` TextField (comma-delimited free text; structured skills in `CandidateSkill`)
- `resume_file` FileField (upload_to='hrm/candidates/resumes/%Y/%m/')
- `resume_text` TextField (raw extracted text; blank=True)
- `photo` ImageField (optional)
- `gender` CharField (choices: male/female/non_binary/prefer_not_to_say — for diversity reporting)
- `status` CharField (choices: active/inactive/hired/blacklisted/do_not_contact; default='active')
- `do_not_contact` BooleanField (email opt-out / DNC flag)
- `gdpr_consent` BooleanField default=False
- `gdpr_consent_date` DateTimeField null/blank
- `gdpr_consent_expires` DateField null/blank (computed from consent_date + tenant policy)
- `notes` TextField blank
- `sourced_by` FK → `accounts.User` null/blank (who added this candidate manually)

**Reuses:** `core.Party`, `core.PartyRole`, `core.ContactMethod` (email/phone as Party contact methods for cross-module reuse)
**Justified by:** Zoho Recruit standard fields taxonomy; Greenhouse profile header (name, pronouns, contact, tags, time zone); Ashby profile (email, phone, LinkedIn, source, tags, do-not-contact, GDPR consent)

---

### 2. `CandidateSkill` (no prefix — child of CandidateProfile)
**What it is:** A discrete skill tag linked to a candidate. Enables filter-by-skill search and structured skills display. Replaces the flat `skill_set` text field for searchability.

**Fields:**
- `tenant` FK → `core.Tenant`
- `candidate` FK → `hrm.CandidateProfile`
- `skill_name` CharField(max_length=100)
- `proficiency` CharField (choices: beginner/intermediate/advanced/expert; blank=True)
- `source` CharField (choices: parsed/manual/self_reported; default='manual')

**Reuses:** nothing from spine directly — pure HRM domain table.
**Justified by:** Greenhouse (skills extraction), Workable (AI parsing populates skill fields), Zoho Recruit (Skill Set field + must-have/nice-to-have designations), Lever (tag-based search on skills)

---

### 3. `JobApplication` [APP-]
**What it is:** The link between a `CandidateProfile` and a `JobRequisition` — one record per "this candidate applied to this job". Holds the application stage, source, screening answers, and the document (resume/cover letter) submitted for this specific application. A candidate can apply to multiple requisitions (multiple `JobApplication` rows, one `CandidateProfile`).

**Fields:**
- `tenant` FK → `core.Tenant`
- `number` CharField `APP-#####` (auto, unique per tenant)
- `candidate` FK → `hrm.CandidateProfile`
- `requisition` FK → `hrm.JobRequisition`
- `stage` CharField choices:
  - `applied` (Applied — just submitted)
  - `screening` (Screening — CV review)
  - `phone_screen` (Phone Screen)
  - `assessment` (Assessment / Test)
  - `interview` (Interview — used for 3.7 handoff)
  - `offer` (Offer — 3.8 handoff)
  - `hired` (Hired)
  - `rejected` (Rejected)
  - `withdrawn` (Withdrawn by candidate)
  - `on_hold` (On Hold)
  default='applied'
- `source` CharField choices:
  - `careers_page` (Company Careers Page)
  - `referral` (Employee Referral)
  - `linkedin` (LinkedIn)
  - `indeed` (Indeed)
  - `glassdoor` (Glassdoor)
  - `job_board` (Other Job Board)
  - `agency` (Recruitment Agency)
  - `direct_approach` (Direct / Sourced)
  - `walk_in` (Walk-in)
  - `other` (Other)
  default='careers_page'
- `referred_by` FK → `hrm.EmployeeProfile` null/blank (referral source employee)
- `cover_letter_text` TextField blank
- `cover_letter_file` FileField null/blank
- `screening_answers` JSONField default=dict blank (stores Q&A from custom questions)
- `rating` PositiveSmallIntegerField null/blank (1–5 recruiter rating of this application)
- `rejection_reason` CharField choices: overqualified/underqualified/position_filled/no_response/failed_screening/other blank
- `rejection_notes` TextField blank
- `applied_at` DateTimeField auto_now_add
- `stage_changed_at` DateTimeField null/blank (set when stage last changed)
- `hired_on` DateField null/blank (set when stage='hired')
- `notes` TextField blank

**Unique together:** (tenant, candidate, requisition) — prevents double-application to the same job

**Reuses:** `hrm.JobRequisition` (3.5 already built), `hrm.CandidateProfile` (new), `hrm.EmployeeProfile` (referral)
**Justified by:** All 10 products; Greenhouse "All Jobs" tab on candidate profile; Workable pipeline stages; Ashby "pipeline stage/status + archive reasons"; iCIMS application stages (Applied / Under Review / Interview Scheduled / Hired); Zoho Recruit candidate hiring pipeline; Breezy HR drag-and-drop stage pipeline

---

### 4. `CandidateTag` (no prefix — catalog + M2M)
**What it is:** A reusable tag/label catalog per tenant. Tags are applied to `CandidateProfile` records to build talent pools and segments. Enables bulk operations (e.g. "send email to all candidates in 'Python Engineers' pool").

**Fields (Tag catalog):**
- `tenant` FK → `core.Tenant`
- `name` CharField(max_length=100)
- `color` CharField(max_length=7, default='#6B7280') (hex color for UI badge)
- `description` TextField blank
- unique_together: (tenant, name)

**M2M join** via `CandidateProfileTag` through table (no extra fields beyond tenant+candidate+tag, or use Django M2M).

**Reuses:** nothing from spine; pure HRM taxonomy.
**Justified by:** Greenhouse (tags on profile header — "tags always visible at top"), Ashby (tags for organization), Workable ("tag, categorize, search"), Teamtailor (custom tags), Lever (tag-based search)

---

### 5. `CandidateEmailTemplate` [CETMPL-]
**What it is:** A tenant-scoped library of reusable email templates for candidate communications. Each template has a `template_type` that maps to a trigger point in the application lifecycle (e.g. `application_received` is auto-sent on `JobApplication` creation).

**Fields:**
- `tenant` FK → `core.Tenant`
- `number` CharField `CETMPL-#####`
- `name` CharField(max_length=255)
- `template_type` CharField choices:
  - `application_received` (Application Received — auto-sent)
  - `shortlisted` (Application Shortlisted)
  - `phone_screen_invite` (Phone Screen Invitation)
  - `interview_invite` (Interview Invitation — lightweight; full scheduling in 3.7)
  - `stage_advance` (Advance to Next Stage)
  - `assessment_invite` (Assessment / Test Invitation)
  - `rejection` (Application Rejected)
  - `on_hold` (Application On Hold)
  - `offer` (Offer Communication — 3.8 handoff)
  - `general` (General / Ad-hoc)
  default='general'
- `subject` CharField(max_length=500)
- `body_html` TextField (supports {{candidate_name}}, {{job_title}}, {{company_name}}, {{recruiter_name}} merge fields)
- `is_active` BooleanField default=True
- `is_auto_send` BooleanField default=False (if True, auto-sends when stage matches template_type)

**Reuses:** mirrors the CRM email template pattern.
**Justified by:** All 10 products; explicit template types: Greenhouse (stage-change auto-notifications), Workable ("custom email templates", personalized email creator), Ashby ("templated email" in activity automation), Lever (offer letter template, day-3 nurture), Breezy HR (auto-responding), BambooHR (pre-built templates)

---

### 6. `CandidateCommunication` [CC-]
**What it is:** An append-only log of every outbound communication sent to a candidate through the system. Ties together: who sent it, which candidate (and which application), which template was used, the final rendered subject/body, and the channel. Distinct from `core.Activity` (which is a broad cross-module task/note/call ledger); this is the typed, tenant-scoped communication log for the ATS sub-module. Can be queried to show a candidate's full communication history.

**Fields:**
- `tenant` FK → `core.Tenant`
- `number` CharField `CC-#####`
- `candidate` FK → `hrm.CandidateProfile`
- `application` FK → `hrm.JobApplication` null/blank (null = not tied to a specific application)
- `template` FK → `hrm.CandidateEmailTemplate` null/blank (null = ad-hoc message)
- `channel` CharField choices: email/sms/whatsapp; default='email'
- `direction` CharField choices: outbound/inbound; default='outbound'
- `subject` CharField(max_length=500) blank
- `body` TextField (the rendered/sent message body)
- `sent_by` FK → `accounts.User` null/blank (null = system auto-send)
- `sent_at` DateTimeField auto_now_add
- `delivery_status` CharField choices: sent/delivered/failed/pending; default='sent'

**Reuses:** supplements `core.Activity` (for broader timeline); `CandidateCommunication` is the ATS-specific email ledger.
**Justified by:** Greenhouse (email history in Notes tab), Ashby (email communication log, scheduled emails, delivery status), iCIMS (multi-channel communication tracking), Lever (automated follow-up logs), Workable (communication trail)

---

## Public Career Portal (no separate model — a view set)

The public career portal is realized as a set of unauthenticated URL patterns within the HRM app:
- `GET /careers/` — lists all `JobRequisition` where status='posted' for the active tenant; grouped by department; search/filter
- `GET /careers/<jr_number>/` — job detail page with full JD content
- `POST /careers/<jr_number>/apply/` — application form submit; creates `CandidateProfile` (or finds existing by email) + `JobApplication`; sends `application_received` email from the matching `CandidateEmailTemplate`

No new model needed — just views + URL patterns over existing `JobRequisition` and new `CandidateProfile`/`JobApplication` models.

---

## Deferred (later passes / integrations)

- **Resume parsing NLP / AI field extraction** — Auto-populate `CandidateProfile` fields from uploaded resume text using a Python NLP library (pyresparser, spaCy, or a third-party API like Affinda/Sovren). Deferred: requires a background task worker and/or paid API; store `resume_text` as raw text in this pass and parse manually or with a simple stub.

- **Structured education/work history child tables** — `CandidateEducation` and `CandidateExperience` child tables with per-entry records (institution, degree, company, title, start/end date). Deferred: keeps this pass to 6 models; resume text + `current_job_title`/`current_employer` fields on `CandidateProfile` cover the read path for now.

- **Candidate self-service status portal** — Token-emailed link for candidates to check their application status without a recruiter login. Deferred: requires signed URL / token management; add in a later pass.

- **CAPTCHA on application form** — Django-reCAPTCHA or HCaptcha integration on the public portal form. Deferred: integration dependency; stub with honeypot field in this pass.

- **GDPR auto-deletion / anonymization scheduled task** — A management command / Celery task that anonymizes `CandidateProfile` records where `gdpr_consent_expires < today` and status = 'rejected'/'withdrawn'. Deferred: needs Celery or Django-Q; consent fields captured in this pass.

- **Bulk SMS / WhatsApp communication** — Twilio or WhatsApp Business API for non-email channels. Deferred: external service integration; `CandidateCommunication.channel` field already accommodates it when integrated.

- **Talent rediscovery / AI candidate matching** — Algorithmic or AI-powered matching of existing candidates to new requisitions. Deferred: requires scoring layer; basic tag/skill filter search covers this pass.

- **Interview scheduling details (3.7)** — Full panel setup, room booking, calendar sync, scorecard assignment, and multi-round management. The `JobApplication.stage = 'interview'` is the 3.6/3.7 handoff point; the `interview_invite` email template is the 3.6 communication touchpoint. All structural interview data lives in 3.7.

- **Offer management details (3.8)** — Offer letter generation, approval workflow, background check. The `JobApplication.stage = 'offer'` / `'hired'` is the 3.6/3.8 handoff. All structural offer data lives in 3.8.

- **Candidate comparison / side-by-side view** — Template-level feature; deferred to avoid over-scoping the first pass.

- **DEI / diversity analytics** — Aggregate reporting on gender, qualification distribution by source, funnel drop-off by demographic. Deferred to BI/reporting pass; `CandidateProfile.gender` field is captured now to enable this later.

- **Candidate portal account / self-service** — Full candidate portal with login, profile editing, and application tracking. Deferred: requires auth extension for anonymous/candidate user type.
