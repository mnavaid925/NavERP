---
# HRM Sub-module 3.6 — Candidate Management (hrm) — plan from research-hrm-candidate-management.md  (2026-06-29)

**Extending `apps/hrm`** — NOT a new app. `apps.py`, `__init__.py`, `settings.py`, `config/urls.py`
are already in place. The only new wire-up is ONE `LIVE_LINKS["3.6"]` entry + URL patterns appended to
the existing `apps/hrm/urls.py`. Six models: `CandidateProfile` [CAND-], `CandidateSkill` (child inline),
`JobApplication` [APP-], `CandidateTag` (catalog + M2M), `CandidateEmailTemplate` [CETMPL-],
`CandidateCommunication` [CC-]. Sub-module template folder: `templates/hrm/candidates/`.
Two cross-model prerequisite changes: (a) add `("candidate", "Candidate")` to `core.PartyRole.ROLE_CHOICES`
with its own migration; (b) add `JobRequisition.public_token` field with its own migration.

---

## 0. Template-folder decision

3.6 is a multi-entity sub-module. Per CLAUDE.md rule 2, the folder shape is
`templates/hrm/candidates/<entity>/<page>.html`. Public portal standalone pages live at the
sub-module root per rule 6 (no entity subfolder).

- [ ] Confirm folder paths:
  - `templates/hrm/candidates/candidate/{list,detail,form}.html` — CandidateProfile CRUD (detail = full hub with inline skills, applications, communications, tags)
  - `templates/hrm/candidates/application/{list,detail,form}.html` — JobApplication CRUD (detail = application hub with stage actions + send-email)
  - `templates/hrm/candidates/tag/{list,form}.html` — CandidateTag CRUD (no detail page — too few fields)
  - `templates/hrm/candidates/emailtemplate/{list,detail,form}.html` — CandidateEmailTemplate CRUD
  - `templates/hrm/candidates/communication/{list,detail}.html` — CandidateCommunication log (append-only; no create/edit form — created via POST action only)
  - `templates/hrm/candidates/careers_list.html` — Public portal: open requisitions listing (standalone, rule 6)
  - `templates/hrm/candidates/careers_apply.html` — Public portal: per-req apply form (standalone, rule 6)
  - NOTE: `CandidateSkill` rows render **inline on the candidate detail hub** — no standalone templates (mirrors `RequisitionApproval` / `ClearanceItem` inline pattern)

---

## 1. Cross-model prerequisite changes

### 1a. `core.PartyRole.ROLE_CHOICES` — add "candidate"

Driver: CandidateProfile is a 1:1 extension of `core.Party` with a `PartyRole(role="candidate")`
marker row — exactly mirroring the `EmployeeProfile` / `PartyRole(role="employee")` pattern.
The choice must exist in the DB before `CandidateProfile` rows can be created.

- [ ] In `apps/core/models.py`, add `("candidate", "Candidate")` to `PartyRole.ROLE_CHOICES` after the `("lead", "Lead")` entry:
  ```
  ROLE_CHOICES = [
      ("customer", "Customer"),
      ("vendor", "Vendor"),
      ("supplier", "Supplier"),
      ("employee", "Employee"),
      ("lead", "Lead"),
      ("candidate", "Candidate"),   # ← ADD THIS
      ("contact", "Contact"),
      ("partner", "Partner"),
  ]
  ```
- [ ] Run `python manage.py makemigrations core --name add_candidate_party_role` → produces `apps/core/migrations/000N_add_candidate_party_role.py` (N = next increment after existing core migrations)
- [ ] Verify migration is clean (no other core-model side effects) before proceeding

### 1b. `hrm.JobRequisition.public_token` — career portal bearer credential

Driver: public career portal resolves the tenant and requisition via an unguessable token
(mirrors `crm.LandingPage.public_token`). The `# FK upgrade deferred to 3.6` comment in the
existing `JobRequisition.is_replacement_for` field signals this was already anticipated.

- [ ] In `apps/hrm/models.py`, add to `JobRequisition` (after `filled_at`, before `class Meta`):
  ```python
  public_token = models.CharField(
      max_length=64, blank=True, db_index=True,
      help_text="URL-safe token set when the req is posted; powers the public careers portal. "
                "Generated via secrets.token_urlsafe(32) in the jobrequisition_post action.")
  ```
- [ ] In the `jobrequisition_post` action view (already built), add: `import secrets` and set `obj.public_token = secrets.token_urlsafe(32)` inside the `transaction.atomic()` block if `obj.public_token` is blank
- [ ] Run `python manage.py makemigrations hrm --name add_jobrequisition_public_token` → produces `apps/hrm/migrations/0011_add_jobrequisition_public_token.py`

---

## 2. Models (add to `apps/hrm/models.py`)

### Module-level CHOICES constants (add above `CandidateProfile` class)

- [ ] Add the following module-level constants to `apps/hrm/models.py` in the choices block (after the existing 3.5 `APPROVER_ROLE_CHOICES` block):

```python
# ── 3.6 Candidate Management choices ───────────────────────────────────────────

CANDIDATE_STATUS_CHOICES = [
    ("active", "Active"),
    ("inactive", "Inactive"),
    ("hired", "Hired"),
    ("blacklisted", "Blacklisted"),
    ("do_not_contact", "Do Not Contact"),
]

QUALIFICATION_CHOICES = [
    ("high_school", "High School / Secondary"),
    ("diploma", "Diploma / Certificate"),
    ("bachelors", "Bachelor's Degree"),
    ("masters", "Master's Degree"),
    ("phd", "PhD / Doctorate"),
    ("other", "Other"),
]

CANDIDATE_GENDER_CHOICES = [
    ("male", "Male"),
    ("female", "Female"),
    ("non_binary", "Non-Binary"),
    ("prefer_not_to_say", "Prefer Not to Say"),
]

CANDIDATE_SOURCE_CHOICES = [
    ("careers_page", "Company Careers Page"),
    ("referral", "Employee Referral"),
    ("linkedin", "LinkedIn"),
    ("indeed", "Indeed"),
    ("glassdoor", "Glassdoor"),
    ("job_board", "Other Job Board"),
    ("agency", "Recruitment Agency"),
    ("direct_approach", "Direct / Sourced"),
    ("walk_in", "Walk-in"),
    ("other", "Other"),
]

SKILL_PROFICIENCY_CHOICES = [
    ("beginner", "Beginner"),
    ("intermediate", "Intermediate"),
    ("advanced", "Advanced"),
    ("expert", "Expert"),
]

SKILL_SOURCE_CHOICES = [
    ("parsed", "Resume Parsed"),
    ("manual", "Manually Added"),
    ("self_reported", "Self-Reported"),
]

APPLICATION_STAGE_CHOICES = [
    ("applied", "Applied"),
    ("screening", "Screening"),
    ("phone_screen", "Phone Screen"),
    ("assessment", "Assessment / Test"),
    ("interview", "Interview"),
    ("offer", "Offer"),
    ("hired", "Hired"),
    ("rejected", "Rejected"),
    ("withdrawn", "Withdrawn"),
    ("on_hold", "On Hold"),
]

REJECTION_REASON_CHOICES = [
    ("overqualified", "Overqualified"),
    ("underqualified", "Underqualified"),
    ("position_filled", "Position Filled"),
    ("no_response", "No Response"),
    ("failed_screening", "Failed Screening"),
    ("other", "Other"),
]

EMAIL_TEMPLATE_TYPE_CHOICES = [
    ("application_received", "Application Received"),
    ("shortlisted", "Application Shortlisted"),
    ("phone_screen_invite", "Phone Screen Invitation"),
    ("interview_invite", "Interview Invitation"),
    ("stage_advance", "Advance to Next Stage"),
    ("assessment_invite", "Assessment / Test Invitation"),
    ("rejection", "Application Rejected"),
    ("on_hold", "Application On Hold"),
    ("offer", "Offer Communication"),
    ("general", "General / Ad-hoc"),
]

COMMUNICATION_CHANNEL_CHOICES = [
    ("email", "Email"),
    ("sms", "SMS"),
    ("whatsapp", "WhatsApp"),
]

COMMUNICATION_DIRECTION_CHOICES = [
    ("outbound", "Outbound"),
    ("inbound", "Inbound"),
]

DELIVERY_STATUS_CHOICES = [
    ("sent", "Sent"),
    ("delivered", "Delivered"),
    ("failed", "Failed"),
    ("pending", "Pending"),
]
```

### 2a. `CandidateProfile` [CAND-] — `TenantNumbered`, `NUMBER_PREFIX = "CAND"`

Drivers: Zoho Recruit standard fields taxonomy (canonical ATS field reference); Greenhouse profile
header (name, contact, tags, do-not-contact); Ashby (GDPR consent capture + DNC flag); Workable
(duplicate detection via unique email); all products require candidate-level status distinct from
application stage. Mirrors `EmployeeProfile` exactly: `TenantNumbered` base, `OneToOneField` to
`core.Party`, denormalized `first_name`/`last_name`/`email` for fast display.

- [ ] Add `CandidateProfile(TenantNumbered)` with `NUMBER_PREFIX = "CAND"`:
  - `party` — `OneToOneField("core.Party", on_delete=models.CASCADE, related_name="candidate_profile")` (identity anchor; Party.name = display name; mirrors EmployeeProfile.party)
  - `first_name` — `CharField(max_length=150)` (denormalized for fast display without Party join; driver: all ATS products show name on list page)
  - `last_name` — `CharField(max_length=150)`
  - `email` — `EmailField()` (unique per tenant — duplicate detection anchor; driver: Greenhouse/Ashby/Workable all deduplicate on email)
  - `phone` — `CharField(max_length=30, blank=True)`
  - `linkedin_url` — `URLField(blank=True)` (driver: Greenhouse/Lever/Ashby profile URLs; Zoho Recruit LinkedIn field)
  - `current_job_title` — `CharField(max_length=255, blank=True)` (driver: Zoho Recruit "Current Job Title"; Greenhouse profile sub-header)
  - `current_employer` — `CharField(max_length=255, blank=True)` (driver: Zoho Recruit "Current Employer"; Workable)
  - `city` — `CharField(max_length=100, blank=True)` (driver: Zoho Recruit City; Workable/iCIMS location filter)
  - `country` — `CharField(max_length=2, blank=True, help_text="ISO 3166-1 alpha-2 country code.")` (driver: Zoho Recruit Country; Workable geo-filter)
  - `years_of_experience` — `DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)` (driver: Zoho Recruit "Experience in Years"; iCIMS/Workable numeric range filter)
  - `highest_qualification` — `CharField(max_length=20, choices=QUALIFICATION_CHOICES, blank=True)` (driver: Zoho Recruit Education section; Greenhouse/Lever structured education; filter-by-qualification)
  - `skill_set` — `TextField(blank=True, help_text="Comma-delimited free-text skills (flat). Structured skills are in CandidateSkill.")` (driver: Zoho Recruit Skill Set field; fallback while NLP parsing deferred)
  - `resume_file` — `FileField(upload_to="hrm/candidates/resumes/%Y/%m/", null=True, blank=True)` (driver: all 10 products; PDF/DOCX accepted; size-capped in clean())
  - `resume_text` — `TextField(blank=True, help_text="Raw text extracted from resume_file. Populated manually or by a parsing stub.")` (driver: Greenhouse/Workable/Zoho full-text resume search; stored now, NLP deferred)
  - `photo` — `ImageField(upload_to="hrm/candidates/photos/%Y/%m/", null=True, blank=True)` (driver: Zoho Recruit profile photo; optional)
  - `gender` — `CharField(max_length=20, choices=CANDIDATE_GENDER_CHOICES, blank=True)` (driver: Ashby DEI diversity capture; Greenhouse/SmartRecruiters EEOC fields; non_binary + prefer_not_to_say)
  - `status` — `CharField(max_length=20, choices=CANDIDATE_STATUS_CHOICES, default="active", editable=False)` (driver: Greenhouse/Zoho/Lever candidate-level lifecycle state, distinct from application stage; workflow-owned)
  - `source` — `CharField(max_length=20, choices=CANDIDATE_SOURCE_CHOICES, blank=True)` (driver: Greenhouse source quality report; Workable source filter; iCIMS; overall sourcing channel for this person)
  - `do_not_contact` — `BooleanField(default=False)` (driver: Zoho Recruit "E-mail Opt-Out"; Ashby "Do Not Contact"; suppresses automated emails)
  - `gdpr_consent` — `BooleanField(default=False)` (driver: Teamtailor/SmartRecruiters/Ashby GDPR consent capture on application form)
  - `gdpr_consent_date` — `DateTimeField(null=True, blank=True, editable=False)` (driver: GDPR Article 7 — timestamp of consent; set by view, never form)
  - `gdpr_consent_expires` — `DateField(null=True, blank=True)` (driver: Teamtailor auto-removal / SmartRecruiters retention window; set by recruiter or policy)
  - `notes` — `TextField(blank=True)` (driver: Greenhouse notes tab; Ashby notes on profile)
  - `sourced_by` — `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="sourced_candidates")` (driver: Ashby "credited user"; Greenhouse sourcer attribution)
  - `expected_salary` — `DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)` (driver: Zoho Recruit "Expected Salary"; offer negotiation baseline)
  - `notice_period_days` — `PositiveSmallIntegerField(null=True, blank=True)` (driver: Zoho Recruit notice period field; used in offer stage)
  - `tags` — `ManyToManyField("hrm.CandidateTag", blank=True, related_name="candidates")` (driver: Greenhouse tags on profile header; Ashby/Workable/Teamtailor talent pool segmentation)

- [ ] Meta:
  ```python
  class Meta:
      ordering = ["-created_at"]
      unique_together = ("tenant", "number")
      constraints = [
          models.UniqueConstraint(fields=["tenant", "email"], name="hrm_cand_tenant_email_uniq")
      ]
      indexes = [
          models.Index(fields=["tenant", "status"], name="hrm_cand_tenant_status_idx"),
          models.Index(fields=["tenant", "source"], name="hrm_cand_tenant_source_idx"),
          models.Index(fields=["tenant", "do_not_contact"], name="hrm_cand_tenant_dnc_idx"),
      ]
  ```
- [ ] `clean()`: validate `resume_file` extension in {pdf, doc, docx} and size ≤ 10MB (mirrors `EmployeeProfile` photo + `clean_photo()` pattern); validate `photo` size ≤ 5MB
- [ ] `@property name`: returns `f"{self.first_name} {self.last_name}".strip()` (mirrors EmployeeProfile.name → party.name; here denormalized)
- [ ] `__str__`: `f"{self.number} · {self.first_name} {self.last_name}"`
- [ ] Reuses: `core.Party` (identity anchor), `core.PartyRole` (role="candidate" marker), `core.Tenant`

### 2b. `CandidateSkill` (no prefix — child of CandidateProfile, no standalone CRUD)

Driver: Greenhouse (skills extraction), Workable (AI skill parsing → structured tags), Zoho Recruit
(Skill Set with proficiency designations), Lever (tag-based skill search). Enables filter-by-skill
search and structured skills display on the candidate detail hub.
Mirrors `RequisitionApproval` / `ClearanceItem` pattern: child rows added/removed via POST actions
on the parent detail page, never via a standalone form.

- [ ] Add `CandidateSkill(TenantOwned)` (note: `TenantOwned`, not `TenantNumbered` — no auto-number needed):
  - `tenant` — FK→`core.Tenant` (inherited from TenantOwned)
  - `candidate` — `ForeignKey("hrm.CandidateProfile", on_delete=models.CASCADE, related_name="skills")`
  - `skill_name` — `CharField(max_length=100)` (the skill name; e.g. "Python", "SQL", "Project Management")
  - `proficiency` — `CharField(max_length=20, choices=SKILL_PROFICIENCY_CHOICES, blank=True)` (driver: Zoho Recruit must-have/nice-to-have; Greenhouse proficiency levels)
  - `source` — `CharField(max_length=20, choices=SKILL_SOURCE_CHOICES, default="manual")` (driver: Workable "AI-parsed" vs manually added; Greenhouse sourced vs self-reported)

- [ ] Meta:
  ```python
  class Meta:
      ordering = ["skill_name"]
      unique_together = ("candidate", "skill_name")
      indexes = [
          models.Index(fields=["tenant", "skill_name"], name="hrm_cskill_tenant_name_idx"),
      ]
  ```
- [ ] `__str__`: `f"{self.skill_name} ({self.get_proficiency_display()})"`

### 2c. `JobApplication` [APP-] — `TenantNumbered`, `NUMBER_PREFIX = "APP"`

Driver: All 10 ATS products; the core link between candidate and requisition. Stage = workflow-owned
field (pipeline state machine). Unique per (tenant, candidate, requisition) to prevent double-application.
Stage is **not on the create/edit form** — it is set via POST stage-move actions (mirrors the
`jobrequisition_post` / `jobrequisition_approve_step` pattern from 3.5). Rating and notes ARE editable
via form (recruiter annotation). The form includes source, referred_by, cover_letter_text, rating, notes.

- [ ] Add `JobApplication(TenantNumbered)` with `NUMBER_PREFIX = "APP"`:
  - `candidate` — `ForeignKey("hrm.CandidateProfile", on_delete=models.CASCADE, related_name="applications")` (driver: all products — one candidate can apply to multiple reqs)
  - `requisition` — `ForeignKey("hrm.JobRequisition", on_delete=models.CASCADE, related_name="applications")` (driver: all products — one req has many applicants)
  - `stage` — `CharField(max_length=20, choices=APPLICATION_STAGE_CHOICES, default="applied", editable=False)` (driver: Greenhouse/Workable/Breezy HR pipeline stages; workflow-owned — set only by stage-move POST actions)
  - `source` — `CharField(max_length=20, choices=CANDIDATE_SOURCE_CHOICES, default="careers_page")` (driver: Greenhouse source quality report; Workable/iCIMS source filter; per-application source can differ from candidate-level source)
  - `referred_by` — `ForeignKey("hrm.EmployeeProfile", on_delete=models.SET_NULL, null=True, blank=True, related_name="referrals")` (driver: Greenhouse referral tracking; Ashby credited referrer; Teamtailor/Workable employee referral program)
  - `cover_letter_text` — `TextField(blank=True)` (driver: Greenhouse/Workable application form cover letter textarea)
  - `cover_letter_file` — `FileField(upload_to="hrm/candidates/covers/%Y/%m/", null=True, blank=True)` (driver: Greenhouse cover letter file upload alternative)
  - `screening_answers` — `JSONField(default=dict, blank=True)` (driver: Greenhouse/Workable per-req screening questions + answers stored as {question: answer} dict; NLP deferred)
  - `rating` — `PositiveSmallIntegerField(null=True, blank=True, help_text="Recruiter rating 1–5.")` (driver: Greenhouse scorecard rating; Workable/Lever application quality rating)
  - `rejection_reason` — `CharField(max_length=30, choices=REJECTION_REASON_CHOICES, blank=True)` (driver: Ashby archive reasons; Greenhouse rejection reason; iCIMS disposition codes)
  - `rejection_notes` — `TextField(blank=True)` (driver: Greenhouse rejection comments; Ashby notes on archive)
  - `applied_at` — `DateTimeField(auto_now_add=True)` (driver: all products timestamp application receipt)
  - `stage_changed_at` — `DateTimeField(null=True, blank=True, editable=False)` (driver: Greenhouse time-in-stage analytics; set by stage-move actions)
  - `hired_on` — `DateField(null=True, blank=True, editable=False)` (driver: Greenhouse hire date; set when stage→hired)
  - `notes` — `TextField(blank=True)` (recruiter freeform notes on this application)

- [ ] Meta:
  ```python
  class Meta:
      ordering = ["-applied_at"]
      unique_together = ("tenant", "number")
      constraints = [
          models.UniqueConstraint(
              fields=["candidate", "requisition"],
              name="hrm_app_cand_req_uniq")
      ]
      indexes = [
          models.Index(fields=["tenant", "stage"], name="hrm_app_tenant_stage_idx"),
          models.Index(fields=["tenant", "source"], name="hrm_app_tenant_source_idx"),
          models.Index(fields=["tenant", "requisition"], name="hrm_app_tenant_req_idx"),
          models.Index(fields=["tenant", "candidate"], name="hrm_app_tenant_cand_idx"),
          models.Index(fields=["candidate", "requisition"], name="hrm_app_cand_req_idx"),
      ]
  ```
- [ ] `clean()`: validate `rating` in range 1–5 if provided; validate `cover_letter_file` extension in {pdf, doc, docx} and size ≤ 10MB
- [ ] `__str__`: `f"{self.number} · {self.candidate} → {self.requisition}"`
- [ ] Reuses: `hrm.JobRequisition` (3.5 already built), `hrm.CandidateProfile` (new 3.6), `hrm.EmployeeProfile` (referral FK)

### 2d. `CandidateTag` (no prefix — tenant catalog table + M2M to CandidateProfile)

Driver: Greenhouse (tags on profile header — "always visible at top"), Ashby (tags for organization),
Workable ("tag, categorize, search"), Teamtailor (custom tags + Connect subscriptions), Lever
(tag-based search). No detail page needed (only name + color). M2M to CandidateProfile via the
`tags` field on CandidateProfile (Django's built-in M2M; no explicit through table needed —
through table adds no extra fields beyond the FK pair).

- [ ] Add `CandidateTag(TenantOwned)`:
  - `name` — `CharField(max_length=100)` (e.g. "Python Engineers Pool", "Strong Culture Fit")
  - `color` — `CharField(max_length=7, default="#6B7280", help_text="Hex color for badge UI.")` (driver: Workable/Teamtailor color-coded tags; validated with HEX_COLOR_VALIDATOR if available in core, else inline regex validator)
  - `description` — `TextField(blank=True)` (optional label for what this pool means)

- [ ] Meta:
  ```python
  class Meta:
      ordering = ["name"]
      unique_together = ("tenant", "name")
      indexes = [
          models.Index(fields=["tenant", "name"], name="hrm_ctag_tenant_name_idx"),
      ]
  ```
- [ ] `__str__`: `f"{self.name}"`

### 2e. `CandidateEmailTemplate` [CETMPL-] — `TenantNumbered`, `NUMBER_PREFIX = "CETMPL"`

Driver: All 10 products have a template library; Greenhouse (stage-change auto-notifications),
Workable ("custom email templates"), Ashby ("templated email"), Lever (offer letter template,
nurture templates), Breezy HR (auto-responding with templates), BambooHR (pre-built templates).
HRM-OWNED — do NOT import from or reuse `crm.EmailTemplate`; peer apps do not cross-import.
`is_auto_send=True` templates are fired by the stage-move actions (signal/service) when the
`template_type` matches the new stage.

- [ ] Add `CandidateEmailTemplate(TenantNumbered)` with `NUMBER_PREFIX = "CETMPL"`:
  - `name` — `CharField(max_length=255)` (e.g. "Application Received — Standard", "Interview Invitation — Engineering")
  - `template_type` — `CharField(max_length=30, choices=EMAIL_TEMPLATE_TYPE_CHOICES, default="general")` (driver: Greenhouse trigger-based templates; Workable template type selector)
  - `subject` — `CharField(max_length=500)` (supports merge fields: {{candidate_name}}, {{job_title}}, {{company_name}}, {{recruiter_name}})
  - `body_html` — `TextField(help_text="Supports merge fields: {{candidate_name}}, {{job_title}}, {{company_name}}, {{recruiter_name}}, {{application_number}}.")` (driver: Greenhouse/Workable personalized body; Ashby templated email)
  - `is_active` — `BooleanField(default=True)` (driver: deactivate old templates without deleting)
  - `is_auto_send` — `BooleanField(default=False, help_text="If True, auto-sends when a JobApplication stage matches this template_type.")` (driver: Greenhouse automated stage-change notifications; Breezy HR auto-responding)

- [ ] Meta:
  ```python
  class Meta:
      ordering = ["template_type", "name"]
      unique_together = ("tenant", "number")
      indexes = [
          models.Index(fields=["tenant", "template_type", "is_active"], name="hrm_cetmpl_type_active_idx"),
      ]
  ```
- [ ] `__str__`: `f"{self.number} · {self.name}"`

### 2f. `CandidateCommunication` [CC-] — `TenantNumbered`, `NUMBER_PREFIX = "CC"`

Driver: Greenhouse (email history in Notes tab), Ashby (email communication log + delivery status),
iCIMS (multi-channel communication tracking), Lever (automated follow-up logs), Workable
(communication trail per application). Append-only by design — created via a "send email" POST
action on the candidate or application detail; admin blocks edit/delete. `sent_by=None` = system
auto-send (stage-change trigger). Distinct from `core.Activity` (broader cross-module ledger);
this is the ATS-specific typed email log.

- [ ] Add `CandidateCommunication(TenantNumbered)` with `NUMBER_PREFIX = "CC"`:
  - `candidate` — `ForeignKey("hrm.CandidateProfile", on_delete=models.CASCADE, related_name="communications")` (driver: candidate-level communication history)
  - `application` — `ForeignKey("hrm.JobApplication", on_delete=models.SET_NULL, null=True, blank=True, related_name="communications")` (driver: Greenhouse notes tab per application; null = not tied to a specific application)
  - `template` — `ForeignKey("hrm.CandidateEmailTemplate", on_delete=models.SET_NULL, null=True, blank=True, related_name="communications")` (driver: Ashby "which template was used"; audit trail links back to template)
  - `channel` — `CharField(max_length=10, choices=COMMUNICATION_CHANNEL_CHOICES, default="email")` (driver: iCIMS multi-channel; Teamtailor WhatsApp; sms/whatsapp wired now, actual send deferred to integrations)
  - `direction` — `CharField(max_length=10, choices=COMMUNICATION_DIRECTION_CHOICES, default="outbound")` (driver: Ashby inbound/outbound log; Lever conversation threading)
  - `subject` — `CharField(max_length=500, blank=True)` (the rendered/final subject after merge-field substitution)
  - `body` — `TextField()` (the rendered/sent body after merge-field substitution)
  - `sent_by` — `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="candidate_communications")` (null = system/auto-send; driver: Greenhouse "sent by" attribution)
  - `sent_at` — `DateTimeField(auto_now_add=True)`
  - `delivery_status` — `CharField(max_length=10, choices=DELIVERY_STATUS_CHOICES, default="sent")` (driver: Ashby delivery status tracking; failed = visible alert in UI)

- [ ] Meta:
  ```python
  class Meta:
      ordering = ["-sent_at"]
      unique_together = ("tenant", "number")
      indexes = [
          models.Index(fields=["tenant", "candidate"], name="hrm_cc_tenant_cand_idx"),
          models.Index(fields=["tenant", "application"], name="hrm_cc_tenant_app_idx"),
          models.Index(fields=["tenant", "delivery_status"], name="hrm_cc_tenant_dstatus_idx"),
      ]
  ```
- [ ] `__str__`: `f"{self.number} · {self.get_channel_display()} → {self.candidate}"`
- [ ] NOTE: no `clean()` needed — body is the rendered text (already validated at send time)

---

## 3. Migrations

- [ ] `python manage.py makemigrations core --name add_candidate_party_role` → `apps/core/migrations/000N_add_candidate_party_role.py`
- [ ] `python manage.py makemigrations hrm --name add_jobrequisition_public_token` → `apps/hrm/migrations/0011_add_jobrequisition_public_token.py`
- [ ] `python manage.py makemigrations hrm --name candidate_management_models` → `apps/hrm/migrations/0012_candidate_management_models.py` (covers CandidateProfile, CandidateSkill, JobApplication, CandidateTag, CandidateEmailTemplate, CandidateCommunication + the CandidateProfile.tags M2M through table)
- [ ] `python manage.py migrate` — verify no errors; confirm all 3 new migrations applied
- [ ] `python manage.py check` — zero errors/warnings

---

## 4. Forms (`apps/hrm/forms.py`)

All forms inherit `TenantModelForm` (or `forms.ModelForm` with `__init__(self, *args, tenant=None, **kwargs)` if TenantModelForm is the pattern already in hrm/forms.py). Exclude: `tenant`, auto-number fields (`number`), workflow-owned fields (`status`, `stage`, `gdpr_consent_date`, `stage_changed_at`, `hired_on`, `applied_at`, `sent_at`).

- [ ] **`CandidateProfileForm`** — fields: `first_name`, `last_name`, `email`, `phone`, `linkedin_url`, `current_job_title`, `current_employer`, `city`, `country`, `years_of_experience`, `highest_qualification`, `skill_set`, `resume_file`, `resume_text`, `photo`, `gender`, `source`, `do_not_contact`, `gdpr_consent`, `gdpr_consent_expires`, `notes`, `sourced_by`, `expected_salary`, `notice_period_days`. Exclude `tags` (managed via inline POST actions on detail hub), `status` (workflow-owned), `party` (set in view). Add `clean_resume_file()` validating extension in {.pdf,.doc,.docx} and size ≤ 10 MB. Add `clean_photo()` validating size ≤ 5 MB and extension in {.jpg,.jpeg,.png,.webp}.

- [ ] **`CandidateSkillForm`** — fields: `skill_name`, `proficiency`, `source`. Used for the inline-add POST on the candidate detail hub (no standalone template).

- [ ] **`JobApplicationForm`** — fields: `candidate`, `requisition`, `source`, `referred_by`, `cover_letter_text`, `cover_letter_file`, `screening_answers`, `rating`, `rejection_reason`, `rejection_notes`, `notes`. Exclude `stage` (workflow-owned), `stage_changed_at`, `hired_on`, `applied_at`. Limit candidate/requisition querysets to `tenant`. Add `clean_cover_letter_file()` same extension+size guard as resume. Add `clean_rating()` enforcing 1–5 range.

- [ ] **`CandidateTagForm`** — fields: `name`, `color`, `description`. Add `clean_color()` validating hex pattern `^#[0-9A-Fa-f]{6}$`.

- [ ] **`CandidateEmailTemplateForm`** — fields: `name`, `template_type`, `subject`, `body_html`, `is_active`, `is_auto_send`.

- [ ] **`PublicApplicationForm`** — a plain `forms.Form` (not model-bound) for the unauthenticated career portal. Fields: `first_name` (CharField), `last_name` (CharField), `email` (EmailField), `phone` (CharField, required=False), `linkedin_url` (URLField, required=False), `city` (CharField, required=False), `resume_file` (FileField — required; same extension/size guard), `cover_letter_text` (CharField widget=Textarea, required=False), `source` (ChoiceField with CANDIDATE_SOURCE_CHOICES, initial="careers_page"), `gdpr_consent` (BooleanField — required=True on submit). Add `clean_resume_file()` with same pdf/doc/docx + 10 MB guard.

---

## 5. Views (`apps/hrm/views.py`)

All internal views are `@login_required` + tenant-scoped. Delete views are `@require_POST`. Stage-move and send-email POST actions are `@require_POST`. Public career views have no `@login_required` — they are unauthenticated; see WARNING below.

### 5a. CandidateProfile views

- [ ] **`candidate_list`** — `crud_list(...)` with:
  - `qs = CandidateProfile.objects.filter(tenant=request.tenant).select_related("party").prefetch_related("tags", "skills")`
  - `search_fields = ["first_name", "last_name", "email", "phone", "current_job_title", "current_employer", "skill_set", "resume_text"]`
  - `filters = [("status", "status", False), ("source", "source", False), ("gender", "gender", False), ("qualification", "highest_qualification", False), ("tag", "tags__id", True), ("skill", "skills__skill_name__icontains", False)]`
  - NOTE: `("skill", "skills__skill_name__icontains", False)` needs a `.distinct()` after filtering to avoid duplicates — wrap the qs in `.distinct()` before passing to crud_list
  - `extra_context = {"status_choices": CANDIDATE_STATUS_CHOICES, "source_choices": CANDIDATE_SOURCE_CHOICES, "gender_choices": CANDIDATE_GENDER_CHOICES, "qualification_choices": QUALIFICATION_CHOICES, "tags": CandidateTag.objects.filter(tenant=request.tenant)}`
  - template: `"hrm/candidates/candidate/list.html"`

- [ ] **`candidate_create`** — `crud_create(...)` creating `Party(kind="person", name=..., tenant=request.tenant)` + `PartyRole(role="candidate")` + saving `CandidateProfile` in `transaction.atomic()`. The form does NOT have a `party` field; the view builds it. Set `profile.party = party` before `form.save(commit=False)`. Set `profile.tenant = request.tenant`. Template: `"hrm/candidates/candidate/form.html"`

- [ ] **`candidate_detail`** — custom view (not `crud_detail`) — the full **candidate hub**:
  - `obj = get_object_or_404(CandidateProfile.objects.filter(tenant=request.tenant).select_related("party", "sourced_by"), pk=pk)`
  - `skills = obj.skills.all()`
  - `applications = obj.applications.select_related("requisition").order_by("-applied_at")`
  - `communications = obj.communications.select_related("template", "sent_by").order_by("-sent_at")[:20]`
  - `tags = obj.tags.all()`
  - `all_tags = CandidateTag.objects.filter(tenant=request.tenant)`
  - `skill_form = CandidateSkillForm()`
  - `stage_choices = APPLICATION_STAGE_CHOICES`
  - template: `"hrm/candidates/candidate/detail.html"`

- [ ] **`candidate_edit`** — `crud_edit(...)`, template: `"hrm/candidates/candidate/form.html"`. On save, sync `Party.name = f"{first_name} {last_name}"` via `update_fields`.

- [ ] **`candidate_delete`** — `@require_POST`, `crud_delete(...)`, success_url: `"hrm:candidate_list"`. NOTE: deleting CandidateProfile also deletes the Party (CASCADE from Party's OneToOneField perspective is reversed — Profile is CASCADE on Party, so deleting Profile alone leaves Party orphaned). Add explicit `obj.party.delete()` inside the POST block (which cascades to delete the profile + PartyRole). Wrap in `transaction.atomic()`.

- [ ] **`candidate_mark_hired`** — `@require_POST`, `@login_required`. Sets `candidate.status = "hired"`, saves. Redirects to candidate_detail.

- [ ] **`candidate_blacklist`** — `@require_POST`, `@login_required`. Sets `candidate.status = "blacklisted"`, `candidate.do_not_contact = True`, saves. Redirects to candidate_detail.

- [ ] **`candidate_restore`** — `@require_POST`, `@login_required`. Sets `candidate.status = "active"`, saves. Redirects to candidate_detail.

- [ ] **`candidate_skill_add`** — `@require_POST`, `@login_required`. Creates `CandidateSkill` for the candidate (validates via `CandidateSkillForm`). Redirects to `candidate_detail`. Enforces (candidate, skill_name) unique via `get_or_create`.

- [ ] **`candidate_skill_delete`** — `@require_POST`, `@login_required`. Deletes the `CandidateSkill` (tenant-scoped via candidate FK). Redirects to `candidate_detail`.

- [ ] **`candidate_tag_add`** — `@require_POST`, `@login_required`. Adds a `CandidateTag` to the candidate's `tags` M2M (tag validated against tenant's catalog). Redirects to `candidate_detail`.

- [ ] **`candidate_tag_remove`** — `@require_POST`, `@login_required`. Removes a `CandidateTag` from the candidate's `tags` M2M. Redirects to `candidate_detail`.

### 5b. JobApplication views

- [ ] **`application_list`** — `crud_list(...)` with:
  - `qs = JobApplication.objects.filter(tenant=request.tenant).select_related("candidate", "requisition", "referred_by")`
  - `search_fields = ["number", "candidate__first_name", "candidate__last_name", "candidate__email", "requisition__title"]`
  - `filters = [("stage", "stage", False), ("source", "source", False), ("requisition", "requisition_id", True), ("candidate", "candidate_id", True)]`
  - `extra_context = {"stage_choices": APPLICATION_STAGE_CHOICES, "source_choices": CANDIDATE_SOURCE_CHOICES, "requisitions": JobRequisition.objects.filter(tenant=request.tenant).only("pk", "number", "title")}`
  - template: `"hrm/candidates/application/list.html"`

- [ ] **`application_create`** — `crud_create(...)`. On success, if an `application_received` `CandidateEmailTemplate` exists with `is_active=True`, auto-fire `_send_candidate_email(application, template_type="application_received", sent_by=request.user)` (see helper below). Template: `"hrm/candidates/application/form.html"`

- [ ] **`application_detail`** — custom detail hub view:
  - `obj = get_object_or_404(JobApplication.objects.filter(tenant=request.tenant).select_related("candidate", "requisition", "referred_by"), pk=pk)`
  - `communications = obj.communications.select_related("template", "sent_by").order_by("-sent_at")`
  - `email_templates = CandidateEmailTemplate.objects.filter(tenant=request.tenant, is_active=True)`
  - `stage_choices = APPLICATION_STAGE_CHOICES`
  - `rejection_reason_choices = REJECTION_REASON_CHOICES`
  - template: `"hrm/candidates/application/detail.html"`

- [ ] **`application_edit`** — `crud_edit(...)`, template: `"hrm/candidates/application/form.html"`

- [ ] **`application_delete`** — `@require_POST`, `crud_delete(...)`, success_url: `"hrm:application_list"`

- [ ] **Stage-move actions** — one view per stage transition (mirrors `jobrequisition_post`/`jobrequisition_approve_step` pattern):
  - `application_advance_stage` — `@require_POST`. Accepts `new_stage` from POST. Validates transition is legal (can't go backwards from hired/rejected without explicit restore). Sets `obj.stage = new_stage`, `obj.stage_changed_at = now()`. If `new_stage == "hired"`: also set `obj.hired_on = date.today()` AND set `obj.candidate.status = "hired"` + save candidate. Auto-fire matching `is_auto_send` template. Redirects to `application_detail`.
  - `application_reject` — `@require_POST`. Accepts `rejection_reason` + `rejection_notes` from POST. Sets `stage = "rejected"`, `stage_changed_at`, `rejection_reason`, `rejection_notes`. Auto-fire `rejection` template if `is_auto_send`. Redirects to `application_detail`.
  - `application_withdraw` — `@require_POST`. Sets `stage = "withdrawn"`. Redirects to `application_detail`.
  - `application_hold` — `@require_POST`. Sets `stage = "on_hold"`. Auto-fire `on_hold` template if `is_auto_send`. Redirects to `application_detail`.

- [ ] **`application_send_email`** — `@require_POST`, `@login_required`. Accepts `template_id` (optional) + `subject` + `body` from POST. Calls `_send_candidate_email(application, template_id=..., subject=..., body=..., sent_by=request.user)`. Redirects to `application_detail` with success/error message.

- [ ] **`_send_candidate_email(application, *, template_type=None, template_id=None, subject=None, body=None, sent_by=None)`** — private helper function (not a view). Checks `application.candidate.do_not_contact` — if True, logs a warning, does NOT send. Resolves template if `template_id` provided. Renders merge fields in subject/body: replace `{{candidate_name}}` with `candidate.first_name + " " + candidate.last_name`, `{{job_title}}` with `requisition.title`, `{{company_name}}` with `request.tenant.name` (passed as param), `{{recruiter_name}}`, `{{application_number}}`. Sends via `django.core.mail.send_mail()` (wrapped in try/except). Creates `CandidateCommunication` row regardless of send success (delivery_status="failed" if exception). Returns the created `CandidateCommunication` instance.

### 5c. CandidateTag views

- [ ] **`candidatetag_list`** — `crud_list(...)`, search_fields=["name", "description"], template: `"hrm/candidates/tag/list.html"`
- [ ] **`candidatetag_create`** — `crud_create(...)`, template: `"hrm/candidates/tag/form.html"`
- [ ] **`candidatetag_edit`** — `crud_edit(...)`, template: `"hrm/candidates/tag/form.html"`
- [ ] **`candidatetag_delete`** — `@require_POST`, `crud_delete(...)`, success_url: `"hrm:candidatetag_list"`. Note: no detail page for tags.

### 5d. CandidateEmailTemplate views

- [ ] **`emailtemplate_list`** — `crud_list(...)`, search_fields=["name", "subject"], filters=[("type", "template_type", False), ("active", "is_active", False)], extra_context={"type_choices": EMAIL_TEMPLATE_TYPE_CHOICES}, template: `"hrm/candidates/emailtemplate/list.html"`
- [ ] **`emailtemplate_create`** — `crud_create(...)`, template: `"hrm/candidates/emailtemplate/form.html"`
- [ ] **`emailtemplate_detail`** — `crud_detail(...)`, template: `"hrm/candidates/emailtemplate/detail.html"`
- [ ] **`emailtemplate_edit`** — `crud_edit(...)`, template: `"hrm/candidates/emailtemplate/form.html"`
- [ ] **`emailtemplate_delete`** — `@require_POST`, `crud_delete(...)`, success_url: `"hrm:emailtemplate_list"`

### 5e. CandidateCommunication views

- [ ] **`communication_list`** — `crud_list(...)`, search_fields=["subject", "body", "candidate__first_name", "candidate__last_name"], filters=[("channel", "channel", False), ("status", "delivery_status", False), ("candidate", "candidate_id", True)], extra_context={"channel_choices": COMMUNICATION_CHANNEL_CHOICES, "delivery_status_choices": DELIVERY_STATUS_CHOICES}, template: `"hrm/candidates/communication/list.html"`
- [ ] **`communication_detail`** — `crud_detail(...)` with select_related=["candidate", "application", "template", "sent_by"], template: `"hrm/candidates/communication/detail.html"`
- [ ] NOTE: No create/edit/delete views — CandidateCommunication is append-only; created only via `application_send_email` and `_send_candidate_email`. Admin-only admin.py access for manual correction if needed.

### 5f. Public career portal views (UNAUTHENTICATED)

- [ ] **`careers_list`** — no `@login_required`. GETs all `JobRequisition.objects.filter(status="posted", posting_type__in=["external", "both"]).select_related("department", "designation")` — this is a cross-tenant public listing. Resolve tenant: accept `?tenant=<slug>` GET param OR use the first posted requisition's tenant (demo mode). For production: each tenant has its own subdomain/path; for the demo, list all posted reqs filtered to a tenant identified via GET param. Template: `"hrm/candidates/careers_list.html"`. NOTE: no tenant-filter on the queryset when there's no authenticated user — filter by `tenant__slug = request.GET.get("tenant")` for safety.
  - `# WARNING: unauthenticated endpoint — add per-IP rate-limiting (django-ratelimit) in production.`

- [ ] **`careers_apply`** — no `@login_required`. Accepts `token` (the `JobRequisition.public_token`). `req = get_object_or_404(JobRequisition, public_token=token, status="posted")`. On GET: render `PublicApplicationForm`. On POST:
  ```python
  # WARNING: unauthenticated endpoint — add rate-limiting in production.
  with transaction.atomic():
      # Find or create candidate (dedup by email + tenant)
      existing = CandidateProfile.objects.filter(tenant=req.tenant, email=cd["email"]).first()
      if existing:
          candidate = existing
      else:
          party = Party.objects.create(kind="person", name=..., tenant=req.tenant)
          PartyRole.objects.create(tenant=req.tenant, party=party, role="candidate")
          candidate = CandidateProfile.objects.create(tenant=req.tenant, party=party, ...)
      # Prevent duplicate application
      app, created = JobApplication.objects.get_or_create(
          tenant=req.tenant, candidate=candidate, requisition=req,
          defaults={"source": "careers_page", "stage": "applied", ...})
      if not created:
          messages.info(request, "You have already applied for this position.")
      else:
          # Set GDPR consent if checked
          if cd["gdpr_consent"]:
              candidate.gdpr_consent = True
              candidate.gdpr_consent_date = now()
              candidate.save(update_fields=["gdpr_consent", "gdpr_consent_date"])
          # Auto-fire application_received template
          _send_candidate_email(app, template_type="application_received", sent_by=None, ...)
  return redirect(f"{reverse('hrm:careers_apply', args=[token])}?submitted=1")
  ```
  - template: `"hrm/candidates/careers_apply.html"`

---

## 6. URLs (`apps/hrm/urls.py`) — append to existing urlpatterns

- [ ] Add to `urlpatterns` in `apps/hrm/urls.py`:

```python
# Candidates (3.6) — CRUD + candidate hub + inline skill/tag actions
path("candidates/", views.candidate_list, name="candidate_list"),
path("candidates/add/", views.candidate_create, name="candidate_create"),
path("candidates/<int:pk>/", views.candidate_detail, name="candidate_detail"),
path("candidates/<int:pk>/edit/", views.candidate_edit, name="candidate_edit"),
path("candidates/<int:pk>/delete/", views.candidate_delete, name="candidate_delete"),
path("candidates/<int:pk>/hire/", views.candidate_mark_hired, name="candidate_mark_hired"),
path("candidates/<int:pk>/blacklist/", views.candidate_blacklist, name="candidate_blacklist"),
path("candidates/<int:pk>/restore/", views.candidate_restore, name="candidate_restore"),
path("candidates/<int:pk>/skills/add/", views.candidate_skill_add, name="candidate_skill_add"),
path("candidates/<int:pk>/skills/<int:skill_pk>/delete/", views.candidate_skill_delete, name="candidate_skill_delete"),
path("candidates/<int:pk>/tags/add/", views.candidate_tag_add, name="candidate_tag_add"),
path("candidates/<int:pk>/tags/<int:tag_pk>/remove/", views.candidate_tag_remove, name="candidate_tag_remove"),

# Job Applications (3.6)
path("applications/", views.application_list, name="application_list"),
path("applications/add/", views.application_create, name="application_create"),
path("applications/<int:pk>/", views.application_detail, name="application_detail"),
path("applications/<int:pk>/edit/", views.application_edit, name="application_edit"),
path("applications/<int:pk>/delete/", views.application_delete, name="application_delete"),
path("applications/<int:pk>/advance/", views.application_advance_stage, name="application_advance_stage"),
path("applications/<int:pk>/reject/", views.application_reject, name="application_reject"),
path("applications/<int:pk>/withdraw/", views.application_withdraw, name="application_withdraw"),
path("applications/<int:pk>/hold/", views.application_hold, name="application_hold"),
path("applications/<int:pk>/send-email/", views.application_send_email, name="application_send_email"),

# Candidate Tags (3.6) — catalog CRUD (no detail page)
path("candidate-tags/", views.candidatetag_list, name="candidatetag_list"),
path("candidate-tags/add/", views.candidatetag_create, name="candidatetag_create"),
path("candidate-tags/<int:pk>/edit/", views.candidatetag_edit, name="candidatetag_edit"),
path("candidate-tags/<int:pk>/delete/", views.candidatetag_delete, name="candidatetag_delete"),

# Candidate Email Templates (3.6)
path("email-templates/", views.emailtemplate_list, name="emailtemplate_list"),
path("email-templates/add/", views.emailtemplate_create, name="emailtemplate_create"),
path("email-templates/<int:pk>/", views.emailtemplate_detail, name="emailtemplate_detail"),
path("email-templates/<int:pk>/edit/", views.emailtemplate_edit, name="emailtemplate_edit"),
path("email-templates/<int:pk>/delete/", views.emailtemplate_delete, name="emailtemplate_delete"),

# Candidate Communications (3.6) — read-only list + detail (append-only; no create/edit/delete)
path("communications/", views.communication_list, name="communication_list"),
path("communications/<int:pk>/", views.communication_detail, name="communication_detail"),

# Public career portal (3.6) — UNAUTHENTICATED; WARNING: add rate-limiting in production
path("careers/", views.careers_list, name="careers_list"),
path("careers/<str:token>/apply/", views.careers_apply, name="careers_apply"),
```

---

## 7. `apps/hrm/admin.py`

- [ ] Register `CandidateProfile` with `list_display = ["number", "first_name", "last_name", "email", "status", "source", "created_at"]`, `list_filter = ["status", "source", "gender", "highest_qualification"]`, `search_fields = ["number", "first_name", "last_name", "email"]`, `readonly_fields = ["number", "status", "gdpr_consent_date", "party"]`
- [ ] Register `CandidateSkill` with `list_display = ["candidate", "skill_name", "proficiency", "source"]`, `list_filter = ["source", "proficiency"]`, `raw_id_fields = ["candidate"]`
- [ ] Register `JobApplication` with `list_display = ["number", "candidate", "requisition", "stage", "source", "applied_at", "rating"]`, `list_filter = ["stage", "source"]`, `search_fields = ["number", "candidate__first_name", "candidate__email", "requisition__title"]`, `readonly_fields = ["number", "stage", "stage_changed_at", "hired_on", "applied_at"]`
- [ ] Register `CandidateTag` with `list_display = ["name", "color", "tenant"]`, `list_filter = ["tenant"]`
- [ ] Register `CandidateEmailTemplate` with `list_display = ["number", "name", "template_type", "is_active", "is_auto_send"]`, `list_filter = ["template_type", "is_active", "is_auto_send"]`, `readonly_fields = ["number"]`
- [ ] Register `CandidateCommunication` with `list_display = ["number", "candidate", "channel", "subject", "delivery_status", "sent_at"]`, `list_filter = ["channel", "delivery_status", "direction"]`, `readonly_fields = ["number", "sent_at"]` — NOTE: no `save_model()` override needed; admin.py registers read-only for history display; block create in admin by overriding `has_add_permission = lambda self, req: False` and `has_change_permission = lambda self, req, obj=None: False`

---

## 8. Navigation — `apps/core/navigation.py` LIVE_LINKS["3.6"]

The NavERP.md 3.6 bullets are: Application Portal / Resume Parser / Candidate Database / Resume Search / Candidate Communication. Map each to the best route.

- [ ] Add to `LIVE_LINKS` dict in `apps/core/navigation.py` (after the `"3.5"` block):

```python
# 3.6 Candidate Management — public career portal, candidate database, skill search, communications.
# Application Portal → careers list (public) or applications list (internal); using application_list
# so it's accessible when logged in; careers_list is the public route.
# Resume Search → candidate list with resume_text filter or skill filter (deeplink with ?q=).
"3.6": {
    "Application Portal": "hrm:application_list",          # bullet (application pipeline hub)
    "Resume Parser": "hrm:candidate_list",                 # bullet (candidate DB with resume_text search)
    "Candidate Database": "hrm:candidate_list",            # bullet (full candidate list + filters)
    "Resume Search": "hrm:candidate_list",                 # bullet (same page; filter-bar covers skill/text search)
    "Candidate Communication": "hrm:communication_list",   # bullet (communication log)
},
```

NOTE: Both "Candidate Database" and "Resume Search" resolve to `hrm:candidate_list` — the filter bar on that page covers name/skill/resume_text search (most-specific-match wins in the active-item flagging; both bullets will highlight when on that page, which is the intended UX).

---

## 9. Templates (`templates/hrm/candidates/`)

### 9a. `candidates/candidate/list.html`

- [ ] Extends `base.html`. Page title: "Candidate Database". Filter bar with:
  - Text search (`q`) — searches name/email/title/employer/skill_set/resume_text
  - Status dropdown (`status`) — from `status_choices` context, compare with string `{% if request.GET.status == value %}`
  - Source dropdown (`source`) — from `source_choices`
  - Gender dropdown (`gender`) — from `gender_choices`
  - Qualification dropdown (`qualification`) — from `qualification_choices`
  - Tag dropdown (`tag`) — from `tags` queryset; FK comparison with `|stringformat:"d"`
  - Skill text filter (`skill`) — freeform text against `skills__skill_name__icontains`
  - Clear filters link when any filter is active
- [ ] Table columns: Number, Name (links to detail), Email, Current Title / Employer, Status (badge), Source badge, Tags (colored badges), Applied (application count badge), Actions (view/edit/delete)
- [ ] Actions column: eye→`candidate_detail`, pencil→`candidate_edit`, bin→POST `candidate_delete` with confirm
- [ ] Empty state: "No candidates found" with "Add Candidate" CTA
- [ ] Pagination using `page_obj.window`

### 9b. `candidates/candidate/detail.html`

- [ ] Candidate hub: header with name (CAND- number), status badge, do-not-contact warning if True. Sidebar: status actions (mark hired / blacklist / restore), edit, delete, back to list.
- [ ] **Profile section**: all CandidateProfile fields displayed (email, phone, linkedin, title, employer, city/country, years_exp, qualification, gender, source, GDPR consent, notes, expected salary, notice period)
- [ ] **Resume section**: download link if `resume_file` exists; `resume_text` in collapsible pre block
- [ ] **Skills inline**: table of `skills` (skill_name, proficiency, source) + "Add Skill" mini-form (POST to `candidate_skill_add`) + delete button per skill (POST to `candidate_skill_delete`)
- [ ] **Tags inline**: colored tag badges + "Add Tag" dropdown (POST to `candidate_tag_add`) + remove button per tag (POST to `candidate_tag_remove`)
- [ ] **Applications tab/section**: table of `applications` (req number/title, stage badge, source, applied_at, rating) with link to each application detail
- [ ] **Communications tab/section**: table of `communications[:20]` (sent_at, channel, subject, delivery_status, sent_by) with link to communication detail
- [ ] WARNING: must pass `all_tags` + `skill_form` + `stage_choices` as context vars

### 9c. `candidates/candidate/form.html`

- [ ] Shared create/edit form. `{% if is_edit %}Edit Candidate{% else %}Add Candidate{% endif %}` title.
- [ ] Fields grouped: Personal Info (first_name, last_name, email, phone, linkedin_url, gender), Professional (current_job_title, current_employer, city, country, years_of_experience, highest_qualification), Recruiting (source, expected_salary, notice_period_days, sourced_by), Resume (resume_file, resume_text help text: "Optional — paste raw text for keyword search"), Privacy (do_not_contact, gdpr_consent, gdpr_consent_expires), Notes.
- [ ] File upload widget for `resume_file` (shows current filename + "Change" on edit)
- [ ] `skill_set` textarea with placeholder: "e.g. Python, SQL, Project Management"

### 9d. `candidates/application/list.html`

- [ ] Filter bar: q (search), stage dropdown (APPLICATION_STAGE_CHOICES), source dropdown, requisition dropdown (FK — `|stringformat:"d"`)
- [ ] Table: Number, Candidate (name + email), Requisition (title), Stage (badge with colors: applied=gray, screening=blue, phone_screen=sky, assessment=yellow, interview=purple, offer=orange, hired=green, rejected=red, withdrawn=gray, on_hold=amber), Source, Applied At, Rating (stars or 1-5), Actions
- [ ] Actions: view/edit/delete

### 9e. `candidates/application/detail.html`

- [ ] Application hub. Header: APP- number, stage badge, candidate name → link to candidate_detail, requisition title → link to jobrequisition_detail.
- [ ] Sidebar: stage-move actions panel (Advance to next stage — dropdown of valid next stages; Reject — with rejection_reason; Withdraw; Hold). Edit + Delete. Back to list.
- [ ] **Application Details section**: all JobApplication fields (source, referred_by, cover_letter_text, cover_letter_file download, screening_answers JSON display, rating, rejection_reason, rejection_notes, notes, applied_at, stage_changed_at, hired_on)
- [ ] **Send Email section**: form with template selector (`email_templates` context, filtered to active), subject (pre-filled from template), body textarea. POST to `application_send_email`. Show DNC warning if candidate.do_not_contact.
- [ ] **Communications log**: table of `communications` (sent_at, channel, subject, delivery_status, sent_by) with link to communication_detail. Empty state: "No communications logged yet."

### 9f. `candidates/application/form.html`

- [ ] Fields: candidate (FK dropdown, show CAND- number + name), requisition (FK dropdown, show JR- number + title), source, referred_by (FK to EmployeeProfile), cover_letter_text, cover_letter_file, rating (1-5 number input), notes.
- [ ] Help text on stage: "Stage is managed via the pipeline actions on the application detail page."

### 9g. `candidates/tag/list.html`

- [ ] Simple table: Name (colored badge using tag.color), Description, Actions (edit, delete — no detail page)
- [ ] Filter: search `q` on name/description
- [ ] "Add Tag" button header. Empty state.

### 9h. `candidates/tag/form.html`

- [ ] Fields: name, color (hex input `<input type="color">`), description. Brief note about color: "Used for badge display in the candidate profile."

### 9i. `candidates/emailtemplate/list.html`

- [ ] Filter: q (name/subject search), type dropdown (EMAIL_TEMPLATE_TYPE_CHOICES), active filter (True/False)
- [ ] Table: Number, Name, Type (badge), Active (badge), Auto-send (badge), Subject (truncated), Actions (view/edit/delete)

### 9j. `candidates/emailtemplate/detail.html`

- [ ] Show all fields. Merge-field reference panel: "Available merge fields: {{candidate_name}}, {{job_title}}, {{company_name}}, {{recruiter_name}}, {{application_number}}". Body rendered as `{{ obj.body_html }}` (NOT escaped — be aware of XSS; only HR staff can create templates, but add `# WARNING: body_html is rendered unescaped — restrict template creation to staff`.

### 9k. `candidates/emailtemplate/form.html`

- [ ] Fields: name, template_type, subject (with merge-field hint), body_html (Textarea, tall), is_active, is_auto_send.
- [ ] Merge-field hint block next to subject/body: "Use {{candidate_name}}, {{job_title}}, {{company_name}}, {{recruiter_name}}, {{application_number}}"

### 9l. `candidates/communication/list.html`

- [ ] Filter: q (subject/body/candidate name), channel dropdown, delivery_status dropdown, candidate FK
- [ ] Table: Number, Candidate (name + link), Application (number + link, if set), Channel badge, Direction, Subject, Delivery Status badge, Sent By, Sent At. No create/edit/delete buttons (read-only log).
- [ ] NOTE: pass `candidates` queryset for the candidate FK filter dropdown: `CandidateProfile.objects.filter(tenant=request.tenant).only("pk", "first_name", "last_name", "number")`

### 9m. `candidates/communication/detail.html`

- [ ] Show all fields. Body rendered as preformatted text (not HTML — `<pre>{{ obj.body }}</pre>` for safety). Back to list + back to candidate link + back to application link (if set).

### 9n. `candidates/careers_list.html` (public, unauthenticated)

- [ ] No `{% extends "base.html" %}` — use a public-facing minimal layout (or extend a `base_public.html` if one exists; otherwise inline a simple HTML5 doc with Tailwind CDN or extend base.html without requiring login).
- [ ] List of posted requisitions grouped by department. Each card: job title, department, location, employment type, posting date, "Apply Now" button → `hrm:careers_apply` with public_token.
- [ ] Search bar filtering by title/department client-side or via GET `?q=`.
- [ ] If `submitted=1` in GET: show "Application submitted successfully!" banner.

### 9o. `candidates/careers_apply.html` (public, unauthenticated)

- [ ] Public application form. Header: company name (from req's tenant) + job title + location.
- [ ] `PublicApplicationForm` fields: First Name, Last Name, Email, Phone, LinkedIn URL, City, Resume (file upload — required), Cover Letter (optional textarea), "How did you hear about us?" (source picklist), GDPR consent checkbox (required — label: "I consent to the storage and processing of my personal data for recruitment purposes.").
- [ ] Resume upload field: accepts PDF/DOCX only; max 10 MB. Client-side hint text shown.
- [ ] After submit: redirect PRG → `?submitted=1` → show "Thank you for applying! We will be in touch." banner.
- [ ] NOTE: CSRF enforced via `{% csrf_token %}`. No bot protection beyond CSRF for demo; deferred CAPTCHA noted.

---

## 10. Seeder — extend `apps/hrm/management/commands/seed_hrm.py`

- [ ] At the top of the `handle()` method (before the new 3.6 block), add guard:
  ```python
  if CandidateProfile.objects.filter(tenant=tenant).exists():
      self.stdout.write("3.6 Candidate data already exists. Use --flush to re-seed.")
      # skip the 3.6 seeding block
  ```
- [ ] Seed **3 CandidateTags** per tenant (idempotent via `get_or_create(tenant=tenant, name=...)`):
  - "Python Engineers Pool" (#3B82F6)
  - "Strong Culture Fit" (#10B981)
  - "Re-engage Later" (#F59E0B)

- [ ] Seed **2 CandidateEmailTemplates** per tenant (idempotent via `get_or_create(tenant=tenant, name=...)`):
  - Template 1: name="Application Received — Standard", type="application_received", subject="Thank you for applying, {{candidate_name}}", body_html="Dear {{candidate_name}},\n\nThank you for applying for the {{job_title}} position at {{company_name}}. We have received your application ({{application_number}}) and will review it shortly.\n\nBest regards,\n{{recruiter_name}}", is_active=True, is_auto_send=True
  - Template 2: name="Application Rejected — Standard", type="rejection", subject="Update on your application for {{job_title}}", body_html="Dear {{candidate_name}},\n\nThank you for your interest in the {{job_title}} position at {{company_name}}. After careful consideration, we will not be moving forward with your application at this time.\n\nWe wish you the best in your search.\n\nBest regards,\n{{recruiter_name}}", is_active=True, is_auto_send=False

- [ ] Seed **6 CandidateProfiles** per tenant. For each: check existence via `CandidateProfile.objects.filter(tenant=tenant, email=email).first()`. If not exists: create `Party(kind="person", name=..., tenant=tenant)` + `PartyRole(tenant=tenant, party=party, role="candidate")` + `CandidateProfile(...)`. Sample data:
  - Alice Johnson (alice.johnson@example.com) — Senior Software Engineer, TechCorp, Python/Django/React skills, 7 years exp, Masters, source=linkedin, status=active
  - Bob Martinez (bob.martinez@example.com) — Product Manager, ProductCo, 5 years exp, Bachelors, source=referral, status=active
  - Carol Singh (carol.singh@example.com) — UX Designer, DesignStudio, 4 years exp, Bachelors, source=careers_page, status=active
  - David Lee (david.lee@example.com) — DevOps Engineer, CloudCo, 6 years exp, Bachelors, source=indeed, status=active
  - Eva Brown (eva.brown@example.com) — Data Analyst, DataCorp, 3 years exp, Masters, source=glassdoor, status=hired
  - Frank Wilson (frank.wilson@example.com) — Sales Executive, SalesCo, 8 years exp, Bachelors, source=agency, status=active

- [ ] Seed **2 CandidateSkills** per candidate (6 candidates × 2 = 12 skills total). Sample:
  - Alice: ("Python", "expert", "manual"), ("Django", "advanced", "manual")
  - Bob: ("Product Management", "advanced", "manual"), ("Agile", "expert", "manual")
  - Carol: ("Figma", "expert", "manual"), ("User Research", "advanced", "manual")
  - David: ("Docker", "expert", "manual"), ("Kubernetes", "advanced", "manual")
  - Eva: ("SQL", "advanced", "manual"), ("Python", "intermediate", "manual")
  - Frank: ("CRM", "advanced", "manual"), ("B2B Sales", "expert", "manual")

- [ ] Add **"Python Engineers Pool"** and **"Strong Culture Fit"** tags to Alice; **"Strong Culture Fit"** to Bob.

- [ ] Seed **8 JobApplications** per tenant (use the seeded JobRequisitions from 3.5 seed; check req exists with `JobRequisition.objects.filter(tenant=tenant).first()`):
  - Skip if no JobRequisitions exist (print warning)
  - Use `get_or_create(tenant=tenant, candidate=cand, requisition=req, defaults={...})` to be idempotent
  - Spread across stages: applied(×2), screening(×2), interview(×2), hired(×1), rejected(×1)
  - Set `source` varied across CANDIDATE_SOURCE_CHOICES
  - Set `rating` for screening+ stage applications

- [ ] Seed **2 CandidateCommunications** for Alice's first application (idempotent: check `CandidateCommunication.objects.filter(tenant=tenant, candidate=alice_profile).exists()`):
  - Auto-send "Application Received" CC row (sent_by=None, delivery_status="sent")
  - Manual "Shortlisting Update" CC row (sent_by=tenant_admin_user, delivery_status="sent")

- [ ] After seeding: print `"Login as admin_<slug> to see 3.6 Candidate Management data."` and `"Superuser 'admin' has no tenant — data won't appear when logged in as admin."`

---

## 11. Verify

- [ ] `python manage.py makemigrations` — confirm no unapplied changes remain
- [ ] `python manage.py migrate` — confirm 3 new migrations applied cleanly (core 000N, hrm 0011, hrm 0012)
- [ ] `python manage.py seed_hrm` (run twice — second run should print "already exists" guard and exit 3.6 block cleanly)
- [ ] `python manage.py check` — zero errors/warnings

- [ ] **Smoke script** — create `temp/smoke_36.py` that:
  1. GETs all `hrm:*` 3.6 routes as `admin_acme` user (logged in via test client) — expects 200:
     - `hrm:candidate_list`, `hrm:candidate_create`, `hrm:candidate_detail` (pk of first seeded candidate), `hrm:candidate_edit` (same pk)
     - `hrm:application_list`, `hrm:application_create`, `hrm:application_detail` (pk of first seeded app), `hrm:application_edit` (same pk)
     - `hrm:candidatetag_list`, `hrm:candidatetag_create`
     - `hrm:emailtemplate_list`, `hrm:emailtemplate_create`, `hrm:emailtemplate_detail` (pk of first template), `hrm:emailtemplate_edit` (same pk)
     - `hrm:communication_list`, `hrm:communication_detail` (pk of first seeded comm)
  2. GETs `hrm:careers_list` as anonymous user — expects 200 (public page)
  3. GETs `hrm:careers_apply` with a valid `public_token` as anonymous user — expects 200
  4. **Cross-tenant IDOR check**: GET `hrm:candidate_detail` (pk=<acme_candidate>) as `admin_beta` user — expects 404
  5. **Template leak scan**: search all rendered HTML for `{#` or `{% comment` — expects zero hits
  6. Print "ALL 3.6 SMOKE CHECKS PASSED" or list failures

- [ ] Verify sidebar shows 3.6 sub-module bullets as **Live** (green links, not "On the roadmap" gray) when logged in as `admin_acme`

---

## 12. Close-out

- [ ] Mark 3.6 Candidate Management as complete in the NavERP README roadmap section (if applicable)
- [ ] Run the full Module Creation Sequence review agents (in order, one at a time):
  1. `code-reviewer` agent
  2. `explorer` agent
  3. `frontend-reviewer` agent
  4. `performance-reviewer` agent
  5. `qa-smoke-tester` agent
  6. `security-reviewer` agent
  7. `test-writer` agent
- [ ] Author `.claude/skills/hrm/SKILL.md` update: add 3.6 models, URLs, templates, and seeder additions to the existing HRM skill (or create a sub-section `## Sub-module 3.6: Candidate Management`)

---

## Later passes / deferred (from research-hrm-candidate-management.md)

- **Resume parsing NLP / AI field extraction** — pyresparser, spaCy, or Affinda/Sovren API to auto-populate CandidateProfile fields from `resume_text`. Requires background task (Celery/Django-Q). `resume_text` field captured now.
- **Structured education/work history child tables** — `CandidateEducation` (institution, degree, field, start/end year) + `CandidateExperience` (company, title, start/end date) child models. Adds 2 models; deferred to next pass.
- **Candidate self-service status portal** — token-emailed link for candidates to check application status. Requires signed URL / token management; extend `JobApplication` with a `candidate_token` field.
- **CAPTCHA on public application form** — django-reCAPTCHA or hCaptcha on `careers_apply`. Stub with honeypot field in this pass.
- **GDPR auto-deletion / anonymization scheduled task** — management command or Celery task to anonymize CandidateProfile records where `gdpr_consent_expires < today` and status in (rejected, withdrawn). `gdpr_consent_expires` field captured now.
- **Bulk SMS / WhatsApp communication** — Twilio or WhatsApp Business API. `CandidateCommunication.channel` field already supports it; actual send deferred.
- **Bulk email to candidate segment** — select multiple candidates (by filter/tag) and send a templated email to all at once. Deferred for now; single-send via `application_send_email` covers the MVP.
- **Automated stage-change notification emails (post_save signal)** — `is_auto_send` CandidateEmailTemplate rows should fire on `JobApplication` save when stage changes. This pass fires manually in stage-move action views; a formal signal or service function for 100% coverage is a follow-up.
- **Talent rediscovery / AI candidate matching** — scoring layer to suggest past applicants for new requisitions based on skill/experience overlap. Deferred; basic tag/skill filter search covers this pass.
- **Candidate comparison / side-by-side view** — select 2-3 candidates; compare profiles in a multi-column layout. Template-level feature; deferred.
- **Interview scheduling details (3.7)** — full panel setup, room booking, calendar sync, scorecard. `JobApplication.stage = "interview"` is the 3.6/3.7 handoff.
- **Offer management details (3.8)** — offer letter generation, approval workflow, background check. `JobApplication.stage = "offer"` / `"hired"` is the 3.6/3.8 handoff.
- **DEI / diversity analytics** — aggregate reporting on gender, qualification, funnel drop-off by demographic. `CandidateProfile.gender` captured now; reporting deferred to BI/reporting pass.
- **Candidate portal account / self-service** — full candidate portal with login, profile editing, and application tracking. Requires auth extension for anonymous/candidate user type.

---

## Review notes

(filled in after review agents run)
