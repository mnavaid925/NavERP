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

## Review notes — DELIVERED (2026-06-30)

**Shipped:** all 6 models (CandidateProfile[CAND-], CandidateSkill, JobApplication[APP-], CandidateTag,
CandidateEmailTemplate[CETMPL-], CandidateCommunication[CC-]) + the 2 prereqs (core.PartyRole `candidate` role →
`core/0004`; JobRequisition.public_token → `hrm/0011`, made unique+null in `hrm/0012`; ordering indexes in
`hrm/0013`). Full CRUD + candidate hub (inline skills/tags/applications/communications) + the application pipeline
state machine + merge-field email (`_send_candidate_email`, console backend) + the public web-to-candidate career
portal (`careers_list`/`careers_apply`). Navigation `LIVE_LINKS["3.6"]`, admin (append-only CC blocked),
`_seed_candidates` (6 candidates / 8 applications / 3 tags / 2 templates per tenant).

**Verification:** `manage.py check` clean; migrations apply; seeder idempotent (2nd run skips, `--flush` re-seeds);
qa-smoke-tester **98/98** end-to-end (render + CRUD/workflow POSTs + public apply + IDOR + comment-leak); **108**
pytest tests in `apps/hrm/tests/test_candidate_management.py`; **full suite green**.

**Review-agent findings applied (commit-per-file):**
- **code-reviewer** (7): terminal-stage guard on reject/withdraw/hold; `public_token` unique+null (migration 0012);
  reuse loaded requisition in `careers_apply`; tenant-scope the party role check; audit inside the delete
  transaction; stamp `gdpr_consent_date` on staff create/edit; drop `send_mail(fail_silently)`;
  `application_create`→detail.
- **explorer** (7): requisition hub now lists its applications + shows the shareable public apply URL; HRM overview
  recruiting stat cards; `application_create` `?candidate`/`?requisition` pre-select; application-list candidate
  filter UI; communication→application back-link.
- **frontend-reviewer** (≈9): all 10 stages explicit in `_stage_badge`; `var(--warn)`/`var(--ok)` instead of hex;
  sr-only labels + tag-remove aria-label; `role="status"` banners; `<pre>` overflow; comm-list View action.
- **performance-reviewer** (6): `.distinct()` guard + `.only()` on the tags dropdown; bounded
  candidate_detail(25)/application_detail(50) reverse-FK loads; `(tenant,created_at)`+`(tenant,applied_at)` indexes.
  (The flagged "skill-filter duplication" was a false positive — the `Count` annotation's GROUP BY already dedupes;
  verified empirically.)
- **security-reviewer** (2 code + deferrals): `@tenant_admin_required` on candidate delete/blacklist/restore +
  email-template authoring (a raw POST bypassed the template gate); `CandidateTagForm.clean_color` strict hex
  (CSS-context). Deferred-with-WARNING: rate-limiting on the public endpoints, media `Content-Disposition` hardening.

**Deferred** (see the "Later passes" list above): resume NLP parsing, structured education/experience tables,
candidate self-service portal, CAPTCHA + rate-limiting, GDPR auto-anonymization, bulk SMS/WhatsApp, a post_save
auto-send signal, talent-rediscovery AI, candidate comparison, DEI analytics. 3.7 Interview / 3.8 Offer FK into the
built 3.6 `JobApplication` (`stage="interview"`/`"offer"` are the handoff).

---
# HRM Sub-module 3.7 — Interview Process (hrm) — plan from research-interview-process.md  (2026-06-30)

**Extending `apps/hrm`** — NOT a new app. `apps.py`, `__init__.py`, `settings.py`, `config/urls.py`
are already in place. The only new wire-up is ONE `LIVE_LINKS["3.7"]` entry + URL patterns appended
to the existing `apps/hrm/urls.py`. Four models: `Interview` [INTV-], `InterviewPanelist` (child
inline, no standalone list), `InterviewFeedback` [IFB-], `FeedbackCriterion` (child inline, no
standalone list). Sub-module template folder: `templates/hrm/interview/`. One choices addition:
`interview_reminder` tuple appended to the existing `EMAIL_TEMPLATE_TYPE_CHOICES` in `apps/hrm/models.py`
(no migration needed — `choices` are a Python-layer annotation; `interview_invite` is already present).
Next migration: `apps/hrm/migrations/0014_interview_process.py`.

---

## 0. Template-folder decision

3.7 is a multi-entity sub-module. Per CLAUDE.md rule 2, the folder shape is
`templates/hrm/interview/<entity>/<page>.html`.

- [ ] Confirm folder paths:
  - `templates/hrm/interview/interview/{list,detail,form}.html` — Interview CRUD
    (detail = the interview hub: schedule header + panelist inline + feedback list + action buttons)
  - `templates/hrm/interview/interviewfeedback/{list,detail,form}.html` — InterviewFeedback CRUD
    (detail = scorecard hub with per-criterion inline rows + submit action)
  - NOTE: `InterviewPanelist` rows render **inline on the Interview detail hub** — add/remove via POST
    actions on that page; no standalone list/detail/form templates.
  - NOTE: `FeedbackCriterion` rows render **inline on the InterviewFeedback detail/form** — added
    dynamically during feedback creation/edit; no standalone templates.

---

## 1. Choices additions (`apps/hrm/models.py`)

### 1a. Module-level CHOICES constants (add above the `Interview` class definition)

- [ ] Add to `apps/hrm/models.py` (in the 3.7 section, after the existing 3.6 choices block):

```python
# ── 3.7 Interview Process choices ──────────────────────────────────────────────

INTERVIEW_MODE_CHOICES = [
    ("in_person", "In Person"),
    ("phone",     "Phone Screen"),
    ("video",     "Video Call"),
    ("one_way_video", "One-Way Video"),
]

INTERVIEW_STATUS_CHOICES = [
    ("scheduled",   "Scheduled"),
    ("confirmed",   "Confirmed"),
    ("in_progress", "In Progress"),
    ("completed",   "Completed"),
    ("cancelled",   "Cancelled"),
    ("no_show",     "No Show"),
    ("rescheduled", "Rescheduled"),
]

VIDEO_PROVIDER_CHOICES = [
    ("none",        "None / N/A"),
    ("zoom",        "Zoom"),
    ("teams",       "Microsoft Teams"),
    ("meet",        "Google Meet"),
    ("other",       "Other"),
]

PANELIST_ROLE_CHOICES = [
    ("lead",        "Lead Interviewer"),
    ("interviewer", "Interviewer"),
    ("shadow",      "Shadow / Observer-in-Training"),
    ("observer",    "Observer"),
]

RSVP_STATUS_CHOICES = [
    ("pending",  "Pending"),
    ("accepted", "Accepted"),
    ("declined", "Declined"),
]

RECOMMENDATION_CHOICES = [
    ("strong_no",  "Strong No"),
    ("no",         "No"),
    ("maybe",      "Maybe / On Hold"),
    ("yes",        "Yes"),
    ("strong_yes", "Strong Yes"),
]
```

### 1b. Extend `EMAIL_TEMPLATE_TYPE_CHOICES`

- [ ] In `apps/hrm/models.py`, locate `EMAIL_TEMPLATE_TYPE_CHOICES` and append the `interview_reminder`
  tuple **after** the existing `("interview_invite", "Interview Invitation")` line:

```python
    ("interview_invite",    "Interview Invitation"),   # already present
    ("interview_reminder",  "Interview Reminder"),     # ADD THIS
```

  NOTE: `interview_invite` is already present (confirmed in models.py grep). No data migration
  is needed for a choices-only addition.

---

## 2. Models (add to `apps/hrm/models.py`)

### 2a. `Interview` [INTV-] — `TenantNumbered`, `NUMBER_PREFIX = "INTV"`

Drivers: all 10 products surveyed (Greenhouse, Lever, Ashby, SmartRecruiters, Workable, Zoho Recruit,
Recruitee, GoodTime, Workday, Spark Hire). Fields derived from research:
- `title` — Greenhouse "interview name"; Zoho interview title
- `round_number` — Greenhouse/Lever/Ashby/SmartRecruiters round ordering
- `mode` — Greenhouse in-person/phone/video; Zoho formal/video/log
- `status` — workflow-owned lifecycle; all products surface this
- `scheduled_at` / `duration_minutes` — Lever/Greenhouse/Zoho/Workable core event metadata
- `location` — Zoho/SmartRecruiters/Workable physical room
- `video_provider` + `meeting_url` — Greenhouse/Lever/Recruitee/Zoho meeting link metadata
- `interviewer_instructions` — Ashby "briefing views" (panel-wide)
- `scheduled_by` — Greenhouse "scheduled by" attribution
- `reminder_sent_at` / `feedback_reminder_sent_at` — metadata stubs for Celery dispatch (deferred)
- `notes` — recruiter internal notes (all products have internal notes)

DEFERRED (not built as live features — plain fields OMITTED to keep scope tight):
- `calendar_event_id` — future Google Calendar / Outlook OAuth sync; OMIT this pass
- `candidate_self_schedule_url` — future Calendly integration; OMIT this pass

- [ ] Add `Interview(TenantNumbered)` with `NUMBER_PREFIX = "INTV"`:
  - `application` — `ForeignKey("hrm.JobApplication", on_delete=models.CASCADE, related_name="interviews")`
    (the application this interview round belongs to; candidate + requisition reached through it)
  - `title` — `CharField(max_length=200)` (e.g. "Technical Round 2", "HR Final")
  - `round_number` — `PositiveSmallIntegerField(default=1)` (1-based; defines ordering within an application)
  - `mode` — `CharField(max_length=20, choices=INTERVIEW_MODE_CHOICES, default="in_person")`
  - `status` — `CharField(max_length=20, choices=INTERVIEW_STATUS_CHOICES, default="scheduled", editable=False)`
    (workflow-owned — set ONLY by POST status-transition actions, never the form)
  - `scheduled_at` — `DateTimeField()` (UTC; user sets this; displayed in views)
  - `duration_minutes` — `PositiveSmallIntegerField(default=60)`
  - `location` — `CharField(max_length=255, blank=True)` (physical room or address; optional)
  - `video_provider` — `CharField(max_length=10, choices=VIDEO_PROVIDER_CHOICES, default="none", blank=True)`
  - `meeting_url` — `URLField(blank=True)` (manually entered for now; OAuth auto-generate deferred)
  - `interviewer_instructions` — `TextField(blank=True)` (panel-wide briefing; visible to all panelists)
  - `notes` — `TextField(blank=True)` (recruiter internal notes)
  - `scheduled_by` — `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="scheduled_interviews")`
    (set in the create view to `request.user`; editable on form)
  - `reminder_sent_at` — `DateTimeField(null=True, blank=True, editable=False)` (stamped by the
    send-reminder POST action; Celery task to actually dispatch deferred)
  - `feedback_reminder_sent_at` — `DateTimeField(null=True, blank=True, editable=False)` (stamped by a
    feedback-nudge action; Celery dispatch deferred)

- [ ] Meta:
  ```python
  class Meta:
      ordering = ["scheduled_at"]
      unique_together = ("tenant", "number")
      indexes = [
          models.Index(fields=["tenant", "application"], name="hrm_intv_tenant_app_idx"),
          models.Index(fields=["tenant", "status"],      name="hrm_intv_tenant_status_idx"),
          models.Index(fields=["tenant", "scheduled_at"],name="hrm_intv_tenant_sched_idx"),
          models.Index(fields=["tenant", "mode"],        name="hrm_intv_tenant_mode_idx"),
      ]
  ```
- [ ] `__str__`: `f"{self.number} · {self.title} ({self.get_status_display()})"`
- [ ] Reuses: `hrm.JobApplication` (3.6 built), `core.Tenant`, `settings.AUTH_USER_MODEL`

### 2b. `InterviewPanelist` — `TenantOwned` (child of Interview, NO standalone list page)

Drivers: Greenhouse/Lever/Ashby/GoodTime/Workday — M2M interviewers with role labels + RSVP tracking;
Ashby "briefing views" (per-panelist prep notes). Managed inline on the Interview detail hub via
add/remove POST actions (mirrors `CandidateSkill` / `RequisitionApproval` inline pattern).

- [ ] Add `InterviewPanelist(TenantOwned)`:
  - `interview` — `ForeignKey("hrm.Interview", on_delete=models.CASCADE, related_name="panelists")`
  - `interviewer` — `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="interview_assignments")`
  - `role` — `CharField(max_length=20, choices=PANELIST_ROLE_CHOICES, default="interviewer")`
  - `rsvp_status` — `CharField(max_length=10, choices=RSVP_STATUS_CHOICES, default="pending")`
  - `briefing_notes` — `TextField(blank=True)` (per-panelist prep instructions; Ashby briefing view)
  - `notified_at` — `DateTimeField(null=True, blank=True, editable=False)` (stamped when assignment
    email is sent; set in the add-panelist POST action)

- [ ] Meta:
  ```python
  class Meta:
      ordering = ["role", "id"]
      unique_together = ("interview", "interviewer")
      indexes = [
          models.Index(fields=["tenant", "interview"], name="hrm_pan_tenant_intv_idx"),
          models.Index(fields=["tenant", "interviewer"], name="hrm_pan_tenant_user_idx"),
      ]
  ```
- [ ] `__str__`: `f"{self.get_role_display()} – {self.interviewer}"`
- [ ] NOTE: No standalone list, detail, or form templates — managed exclusively from the Interview detail hub.

### 2c. `InterviewFeedback` [IFB-] — `TenantNumbered`, `NUMBER_PREFIX = "IFB"`

Drivers: all 10 products for the scorecard concept; Greenhouse (strong_no/no/yes/strong_yes +
key-takeaways summary); Zoho Recruit (Strongly Hired → Strongly Rejected 5-level scale);
Workable/Ashby (draft vs. submitted flag enabling anti-anchoring feedback blinding);
Ashby/Greenhouse/Workable (per-criteria competency rows — see FeedbackCriterion below).

- [ ] Add `InterviewFeedback(TenantNumbered)` with `NUMBER_PREFIX = "IFB"`:
  - `interview` — `ForeignKey("hrm.Interview", on_delete=models.CASCADE, related_name="feedback_entries")`
  - `panelist` — `ForeignKey("hrm.InterviewPanelist", on_delete=models.SET_NULL, null=True, blank=True, related_name="feedback_entries")`
    (SET_NULL so feedback survives if a panelist row is removed; links back to the assignment slot)
  - `submitted_by` — `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="submitted_feedback")`
    (denormalized for query convenience; set in the view, never the form)
  - `overall_recommendation` — `CharField(max_length=20, choices=RECOMMENDATION_CHOICES)`
    (maps to Greenhouse Definitely Not/No/Yes/Strong Yes + Zoho On Hold → "maybe")
  - `summary` — `TextField(blank=True)` (free-text overall summary / Greenhouse "key takeaways")
  - `is_submitted` — `BooleanField(default=False)` (draft vs. formally submitted; enables
    anti-anchoring blinding logic in views — panelists see only their own draft until they submit)
  - `submitted_at` — `DateTimeField(null=True, blank=True, editable=False)` (stamped by the
    submit-feedback POST action; set in view, never form)

- [ ] Meta:
  ```python
  class Meta:
      ordering = ["-created_at"]
      unique_together = ("tenant", "number")
      constraints = [
          models.UniqueConstraint(fields=["interview", "panelist"],
                                  name="hrm_ifb_intv_pan_uniq")
      ]
      indexes = [
          models.Index(fields=["tenant", "interview"],            name="hrm_ifb_tenant_intv_idx"),
          models.Index(fields=["tenant", "overall_recommendation"],name="hrm_ifb_tenant_rec_idx"),
          models.Index(fields=["tenant", "is_submitted"],         name="hrm_ifb_tenant_sub_idx"),
      ]
  ```
- [ ] `__str__`: `f"{self.number} · {self.get_overall_recommendation_display()} by {self.submitted_by}"`
- [ ] Reuses: `hrm.Interview`, `hrm.InterviewPanelist`, `settings.AUTH_USER_MODEL`, `core.Tenant`

### 2d. `FeedbackCriterion` — `TenantOwned` (child of InterviewFeedback, NO standalone list page)

Drivers: Greenhouse "focus attributes"; SmartRecruiters (up to 20 competencies per scorecard);
Workable/Zoho Recruit (per-criterion rating + notes); 1–5 integer scale across all reviewed products.
Managed inline on the InterviewFeedback detail/form — created/edited/deleted during scorecard
submission.

- [ ] Add `FeedbackCriterion(TenantOwned)`:
  - `feedback` — `ForeignKey("hrm.InterviewFeedback", on_delete=models.CASCADE, related_name="criteria")`
  - `criterion_name` — `CharField(max_length=150)` (e.g. "Problem Solving", "Communication", "Culture Fit")
  - `rating` — `PositiveSmallIntegerField(null=True, blank=True)` (1=poor to 5=excellent; validated in clean())
  - `notes` — `TextField(blank=True)` (free-text note for this criterion; Greenhouse "key takeaways per criterion")

- [ ] Meta:
  ```python
  class Meta:
      ordering = ["criterion_name"]
      unique_together = ("feedback", "criterion_name")
      indexes = [
          models.Index(fields=["tenant", "feedback"], name="hrm_fc_tenant_fb_idx"),
      ]
  ```
- [ ] `clean()`: if `self.rating` is not None, validate `1 <= self.rating <= 5` else raise
  `ValidationError({"rating": "Rating must be between 1 and 5."})` (mirrors `CandidateSkill`
  rating guard pattern)
- [ ] `__str__`: `f"{self.criterion_name}: {self.rating}/5"`
- [ ] NOTE: No standalone list, detail, or form templates — managed exclusively from the
  InterviewFeedback detail/form hub.

---

## 3. Migration

- [ ] `python manage.py makemigrations hrm --name interview_process` → produces
  `apps/hrm/migrations/0014_interview_process.py` (covers `Interview`, `InterviewPanelist`,
  `InterviewFeedback`, `FeedbackCriterion`; choices additions to `EMAIL_TEMPLATE_TYPE_CHOICES`
  do NOT require a migration — Python-layer only)
- [ ] `python manage.py migrate` — verify no errors; confirm `0014_interview_process` applied cleanly
- [ ] `python manage.py check` — zero errors/warnings

---

## 4. Forms (`apps/hrm/forms.py`)

Exclude from all forms: `tenant` (set in view), auto-`number` (set in `save()`), `status`
(workflow-owned, set by POST actions), `editable=False` timestamp fields (`reminder_sent_at`,
`feedback_reminder_sent_at`, `submitted_at`, `notified_at`). Tenant-scope FK querysets in
`__init__`. Reference: CLAUDE.md lessons L20 (no system fields on forms) and L22
(tenant FK scoping in form init).

- [ ] **`InterviewForm`** — fields: `application`, `title`, `round_number`, `mode`, `scheduled_at`,
  `duration_minutes`, `location`, `video_provider`, `meeting_url`, `interviewer_instructions`,
  `notes`, `scheduled_by`. Exclude: `tenant`, `number`, `status`, `reminder_sent_at`,
  `feedback_reminder_sent_at`.
  - In `__init__`, limit `application` queryset to `JobApplication.objects.filter(tenant=self.tenant)`
    (display as `APP- number · candidate → requisition`).
  - In `__init__`, limit `scheduled_by` queryset to `User.objects.filter(tenant_memberships__tenant=self.tenant).distinct()` (or the equivalent pattern used in existing HRM forms — check `apps/hrm/forms.py` for the User queryset pattern already in use).
  - `scheduled_at` widget: `DateTimeInput(attrs={"type": "datetime-local"})` so the browser renders a
    datetime picker. Format `"%Y-%m-%dT%H:%M"`.

- [ ] **`InterviewPanelistForm`** — fields: `interviewer`, `role`, `briefing_notes`. Exclude `interview`
  (set in view), `rsvp_status` (set by the RSVP action), `notified_at` (set by the add action),
  `tenant`.
  - In `__init__`, limit `interviewer` queryset to `User.objects.filter(...)` scoped to tenant
    (same pattern as `InterviewForm.scheduled_by`).
  - Used only on the Interview detail hub (inline add panel); no standalone form template.

- [ ] **`InterviewFeedbackForm`** — fields: `interview`, `panelist`, `overall_recommendation`, `summary`,
  `is_submitted`. Exclude: `tenant`, `number`, `submitted_by`, `submitted_at`.
  - In `__init__`, limit `interview` queryset to `Interview.objects.filter(tenant=self.tenant)`.
  - In `__init__`, limit `panelist` queryset to `InterviewPanelist.objects.filter(tenant=self.tenant)`.
  - NOTE on `is_submitted`: include on the form but render as read-only on the list view. The
    "Submit Scorecard" action (a separate POST button on the detail page) is the canonical
    `is_submitted=True` + `submitted_at=now()` setter — the form field allows a draft to be
    explicitly marked submitted inline as well.

- [ ] **`FeedbackCriterionForm`** — fields: `criterion_name`, `rating`, `notes`. Exclude `feedback`
  (set in view), `tenant`.
  - Used only on the InterviewFeedback detail hub (inline add); no standalone template.
  - Widget for `rating`: `NumberInput(attrs={"min": 1, "max": 5})`.

---

## 5. Views (`apps/hrm/views.py`)

All views are `@login_required` + `tenant=request.tenant` scoped. DELETE/action views are also
`@require_POST`. Status-transition POST actions mirror the `application_advance_stage` /
`jobrequisition_post` pattern from 3.5/3.6. Audit via `log_action` on meaningful state changes.
Per CLAUDE.md CRUD Completeness Rules: every model with a list page has list + create + detail +
edit + delete. Privilege: CRUD on Interviews is normal `@login_required` (recruiters schedule
interviews); template-authoring (email templates) retains `@tenant_admin_required` from 3.6.

### 5a. `Interview` views

- [ ] **`interview_list`** — `@login_required`. Filter by: `q` (searches `title`, `application__candidate__first_name`,
  `application__candidate__last_name`, `number`), `status` (exact), `mode` (exact),
  `application` (FK pk). `select_related("application__candidate", "application__requisition")`.
  `prefetch_related("panelists__interviewer")`. Context: `status_choices=INTERVIEW_STATUS_CHOICES`,
  `mode_choices=INTERVIEW_MODE_CHOICES`, `applications=JobApplication.objects.filter(tenant=...).only("pk", "number")`.
  Template: `"hrm/interview/interview/list.html"`.

- [ ] **`interview_create`** — `@login_required`. On form valid: set `interview.tenant = request.tenant`,
  `interview.scheduled_by = request.user` (if not set on the form). Save. `log_action`. Redirect to
  `hrm:interview_detail`. Template: `"hrm/interview/interview/form.html"`.

- [ ] **`interview_detail`** — `@login_required`. The interview hub:
  - `obj = get_object_or_404(Interview.objects.filter(tenant=request.tenant).select_related("application__candidate", "application__requisition", "scheduled_by"), pk=pk)`
  - `panelists = obj.panelists.select_related("interviewer").all()`
  - `feedback_entries = obj.feedback_entries.select_related("submitted_by", "panelist__interviewer").prefetch_related("criteria").all()`
  - `panelist_form = InterviewPanelistForm(tenant=request.tenant)`
  - Anti-anchoring logic: if the logged-in user is a panelist, show OTHER panelists' feedback only if
    the current user has already submitted theirs (`is_submitted=True` for their own feedback).
    Recruiters / tenant admins see all feedback regardless.
  - Context: `panelist_form`, `feedback_entries`, `panelists`, `status_choices=INTERVIEW_STATUS_CHOICES`
  - Template: `"hrm/interview/interview/detail.html"`.

- [ ] **`interview_edit`** — `@login_required`. Exclude `status` from form (workflow-owned). Template:
  `"hrm/interview/interview/form.html"`. On save: `log_action`.

- [ ] **`interview_delete`** — `@login_required`, `@require_POST`. `get_object_or_404` tenant-scoped.
  Delete. `log_action`. Redirect to `hrm:interview_list`.

### 5b. Interview status-transition actions (POST-only)

Each action mirrors `application_advance_stage`; all are `@login_required` + `@require_POST`.

- [ ] **`interview_confirm`** — sets `status = "confirmed"`. `log_action`. Redirect to detail.
- [ ] **`interview_start`** — sets `status = "in_progress"`. `log_action`. Redirect to detail.
- [ ] **`interview_complete`** — sets `status = "completed"`. `log_action`. Redirect to detail.
- [ ] **`interview_cancel`** — sets `status = "cancelled"`. `log_action`. Redirect to detail.
- [ ] **`interview_no_show`** — sets `status = "no_show"`. `log_action`. Redirect to detail.
- [ ] **`interview_reschedule`** — sets `status = "rescheduled"`. `log_action`. Redirect to detail.
  NOTE: all transitions allowed from any non-terminal status; completed/cancelled/no_show are
  considered terminal (add a guard: reject repeated transitions into the same terminal status with
  an info message, but do not hard-block reschedule from terminal — recruiters may need to re-open).

### 5c. Panelist management actions (POST-only on Interview detail)

- [ ] **`interview_panelist_add`** — `@login_required`, `@require_POST`. Accepts `interview_pk` in URL.
  Validates `InterviewPanelistForm`. Creates `InterviewPanelist(interview=obj, tenant=request.tenant, ...)`.
  On success: send a plain `django.core.mail.send_mail()` notification to `panelist.interviewer.email`
  (subject: "You have been assigned as an interviewer", body includes interview title, date, candidate
  name). Stamp `notified_at = now()`. `log_action`. Redirect to `hrm:interview_detail`.
  Enforce `unique_together` with `get_or_create`; on duplicate, show info message "Panelist already
  assigned" and do not create a duplicate.

- [ ] **`interview_panelist_remove`** — `@login_required`, `@require_POST`. Accepts `interview_pk` +
  `panelist_pk` in URL. `get_object_or_404(InterviewPanelist, pk=panelist_pk, interview=obj,
  interview__tenant=request.tenant)`. Delete. `log_action`. Redirect to `hrm:interview_detail`.

- [ ] **`interview_panelist_rsvp`** — `@login_required`, `@require_POST`. Accepts `interview_pk` +
  `panelist_pk`. Accepts `rsvp_status` from POST body (validated against RSVP_STATUS_CHOICES).
  Updates `panelist.rsvp_status`. `log_action`. Redirect to `hrm:interview_detail`.

### 5d. Reminder actions (POST-only on Interview detail)

- [ ] **`interview_send_invite`** — `@login_required`, `@require_POST`. Reuses the existing
  `_send_candidate_email` helper (apps/hrm/views.py). Resolves `template_type="interview_invite"`.
  Calls `_send_candidate_email(application=obj.application, template_type="interview_invite",
  sent_by=request.user, company_name=request.tenant.name)`. Stamps `reminder_sent_at = now()`
  on the `Interview` object. `log_action`. Redirect to `hrm:interview_detail`.
  NOTE: if `candidate.do_not_contact` is True, `_send_candidate_email` suppresses the send and
  logs a CandidateCommunication with delivery_status="failed"; no extra guard needed here.

- [ ] **`interview_send_reminder`** — `@login_required`, `@require_POST`. Same pattern but uses
  `template_type="interview_reminder"`. Stamps `reminder_sent_at = now()`. Redirect to detail.

### 5e. `InterviewFeedback` views

- [ ] **`interviewfeedback_list`** — `@login_required`. Filter by: `q` (searches `number`,
  `interview__title`, `submitted_by__username`), `recommendation` (exact `overall_recommendation`),
  `is_submitted` (`"true"`/`"false"` → `BooleanField`), `interview` (FK pk).
  `select_related("interview__application__candidate", "submitted_by", "panelist__interviewer")`.
  Context: `recommendation_choices=RECOMMENDATION_CHOICES`,
  `status_choices=[("true","Submitted"),("false","Draft")]`,
  `interviews=Interview.objects.filter(tenant=...).only("pk","number","title")`.
  Template: `"hrm/interview/interviewfeedback/list.html"`.

- [ ] **`interviewfeedback_create`** — `@login_required`. On form valid: set `feedback.tenant=request.tenant`,
  `feedback.submitted_by=request.user`. Save. Redirect to `hrm:interviewfeedback_detail`. Template:
  `"hrm/interview/interviewfeedback/form.html"`. Context also includes a `FeedbackCriterionForm` for
  the inline criterion section.

- [ ] **`interviewfeedback_detail`** — `@login_required`. The scorecard hub:
  - `obj = get_object_or_404(InterviewFeedback.objects.filter(tenant=request.tenant).select_related("interview__application__candidate", "interview__application__requisition", "submitted_by", "panelist__interviewer"), pk=pk)`
  - `criteria = obj.criteria.all()`
  - `criterion_form = FeedbackCriterionForm()`
  - Anti-anchoring: only show "edit/delete" on criteria if `not obj.is_submitted` (submitted
    scorecards are read-only).
  - Template: `"hrm/interview/interviewfeedback/detail.html"`.

- [ ] **`interviewfeedback_edit`** — `@login_required`. Guard: if `obj.is_submitted`, redirect to
  detail with message "Submitted scorecards cannot be edited." (prevents edits after formal submission).
  Template: `"hrm/interview/interviewfeedback/form.html"`.

- [ ] **`interviewfeedback_delete`** — `@login_required`, `@require_POST`. Guard: if `obj.is_submitted`,
  return 403/redirect with message "Cannot delete a submitted scorecard." Else delete + `log_action`.
  Redirect to `hrm:interviewfeedback_list`.

- [ ] **`interviewfeedback_submit`** — `@login_required`, `@require_POST`. Sets `obj.is_submitted=True`,
  `obj.submitted_at=now()`. `log_action`. Redirect to `hrm:interviewfeedback_detail`.

- [ ] **`feedbackcriterion_add`** — `@login_required`, `@require_POST`. Accepts `feedback_pk` in URL.
  Guard: if feedback.is_submitted, reject (message + redirect). Validates `FeedbackCriterionForm`.
  Creates `FeedbackCriterion(feedback=obj, tenant=request.tenant, ...)`. Enforces unique
  (feedback, criterion_name) with `get_or_create`. Redirect to `hrm:interviewfeedback_detail`.

- [ ] **`feedbackcriterion_delete`** — `@login_required`, `@require_POST`. Accepts `feedback_pk` +
  `criterion_pk`. Guard: if feedback.is_submitted, reject. Delete. Redirect to
  `hrm:interviewfeedback_detail`.

---

## 6. URLs (`apps/hrm/urls.py`) — append to existing urlpatterns

- [ ] Append to `urlpatterns` in `apps/hrm/urls.py`:

```python
# ── 3.7 Interview Process ────────────────────────────────────────────────────────
# Interviews — full CRUD
path("interviews/",                               views.interview_list,              name="interview_list"),
path("interviews/add/",                           views.interview_create,            name="interview_create"),
path("interviews/<int:pk>/",                      views.interview_detail,            name="interview_detail"),
path("interviews/<int:pk>/edit/",                 views.interview_edit,              name="interview_edit"),
path("interviews/<int:pk>/delete/",               views.interview_delete,            name="interview_delete"),

# Interview status-transition actions (POST-only)
path("interviews/<int:pk>/confirm/",              views.interview_confirm,           name="interview_confirm"),
path("interviews/<int:pk>/start/",                views.interview_start,             name="interview_start"),
path("interviews/<int:pk>/complete/",             views.interview_complete,          name="interview_complete"),
path("interviews/<int:pk>/cancel/",               views.interview_cancel,            name="interview_cancel"),
path("interviews/<int:pk>/no-show/",              views.interview_no_show,           name="interview_no_show"),
path("interviews/<int:pk>/reschedule/",           views.interview_reschedule,        name="interview_reschedule"),

# Panelist inline management (POST-only; no standalone list)
path("interviews/<int:pk>/panelists/add/",        views.interview_panelist_add,      name="interview_panelist_add"),
path("interviews/<int:pk>/panelists/<int:panelist_pk>/remove/", views.interview_panelist_remove, name="interview_panelist_remove"),
path("interviews/<int:pk>/panelists/<int:panelist_pk>/rsvp/",   views.interview_panelist_rsvp,   name="interview_panelist_rsvp"),

# Reminder / invite send actions (POST-only)
path("interviews/<int:pk>/send-invite/",          views.interview_send_invite,       name="interview_send_invite"),
path("interviews/<int:pk>/send-reminder/",        views.interview_send_reminder,     name="interview_send_reminder"),

# Interview Feedback — full CRUD
path("interview-feedback/",                       views.interviewfeedback_list,      name="interviewfeedback_list"),
path("interview-feedback/add/",                   views.interviewfeedback_create,    name="interviewfeedback_create"),
path("interview-feedback/<int:pk>/",              views.interviewfeedback_detail,    name="interviewfeedback_detail"),
path("interview-feedback/<int:pk>/edit/",         views.interviewfeedback_edit,      name="interviewfeedback_edit"),
path("interview-feedback/<int:pk>/delete/",       views.interviewfeedback_delete,    name="interviewfeedback_delete"),
path("interview-feedback/<int:pk>/submit/",       views.interviewfeedback_submit,    name="interviewfeedback_submit"),

# Feedback criterion inline management (POST-only; no standalone list)
path("interview-feedback/<int:pk>/criteria/add/", views.feedbackcriterion_add,       name="feedbackcriterion_add"),
path("interview-feedback/<int:pk>/criteria/<int:criterion_pk>/delete/", views.feedbackcriterion_delete, name="feedbackcriterion_delete"),
```

---

## 7. `apps/hrm/admin.py`

- [ ] Register `Interview` with `list_display=["number","title","round_number","mode","status","scheduled_at","duration_minutes","scheduled_by"]`, `list_filter=["status","mode","video_provider"]`, `search_fields=["number","title","application__candidate__first_name","application__candidate__last_name"]`, `readonly_fields=["number","status","reminder_sent_at","feedback_reminder_sent_at"]`
- [ ] Register `InterviewPanelist` with `list_display=["interview","interviewer","role","rsvp_status","notified_at"]`, `list_filter=["role","rsvp_status"]`, `raw_id_fields=["interview","interviewer"]`, `readonly_fields=["notified_at"]`
- [ ] Register `InterviewFeedback` with `list_display=["number","interview","submitted_by","overall_recommendation","is_submitted","submitted_at"]`, `list_filter=["overall_recommendation","is_submitted"]`, `search_fields=["number","interview__title"]`, `readonly_fields=["number","submitted_by","submitted_at"]`
- [ ] Register `FeedbackCriterion` with `list_display=["feedback","criterion_name","rating"]`, `list_filter=["rating"]`, `raw_id_fields=["feedback"]`

---

## 8. Navigation — `apps/core/navigation.py` LIVE_LINKS["3.7"]

The NavERP.md 3.7 bullets are: Interview Scheduling / Interview Panel / Interview Feedback /
Video Interview / Interview Reminders. Map each to a meaningful, staff-reachable destination
(per L30/L32 — distinct routes where possible).

Decision rationale:
- "Interview Scheduling" → `hrm:interview_list` (the main interview list; scheduling is the core action)
- "Interview Panel" → `hrm:interview_list` (panelists are managed on the interview detail hub, not a
  separate list; this co-highlights with Interview Scheduling, which is correct — panel management
  is accessed from the same interview list)
- "Interview Feedback" → `hrm:interviewfeedback_list` (distinct list page for scorecards)
- "Video Interview" → `hrm:interview_list?mode=video` (deep-link filtered to video-mode interviews
  only; most-specific-match wins in active-item flagging, so this highlights distinctly)
- "Interview Reminders" → `hrm:interview_list` (reminders are inline actions on the interview detail;
  no dedicated reminder list; co-highlights with Interview Scheduling — automated dispatch deferred)

- [ ] Add to `LIVE_LINKS` dict in `apps/core/navigation.py` (after the `"3.6"` block, before the
  closing `}`):

```python
# 3.7 Interview Process — scheduling, panel, feedback/scorecards, video links, reminders.
# Panel management lives on the interview detail hub (inline add/remove) so "Interview Panel"
# co-highlights with interview_list. "Video Interview" deep-links to mode=video filtered list.
# "Interview Reminders" surfaces the send-invite/send-reminder actions on interview detail.
"3.7": {
    "Interview Scheduling": "hrm:interview_list",                  # bullet (interview schedule hub)
    "Interview Panel":      "hrm:interview_list",                  # bullet (panel on interview detail)
    "Interview Feedback":   "hrm:interviewfeedback_list",          # bullet (scorecard list)
    "Video Interview":      "hrm:interview_list?mode=video",       # bullet (filtered: video mode only)
    "Interview Reminders":  "hrm:interview_list",                  # bullet (reminder actions on detail)
},
```

---

## 9. Templates (`templates/hrm/interview/`)

### 9a. `interview/interview/list.html`

- [ ] Extends `base.html`. Page title: "Interviews". Filter bar with:
  - Text search (`q`) — searches title, candidate name, number
  - Status dropdown (`status`) — from `status_choices`; badge colors: scheduled=blue, confirmed=green,
    in_progress=purple, completed=emerald, cancelled=red, no_show=orange, rescheduled=amber
  - Mode dropdown (`mode`) — from `mode_choices`
  - Application dropdown (`application`) — from `applications` queryset; FK comparison with
    `|stringformat:"d"`
  - Clear filters link when any filter active
- [ ] Table columns: Number, Title, Round, Candidate (from application.candidate), Mode badge, Status
  badge, Scheduled At, Duration (mins), Panelists count, Actions
- [ ] Actions column: eye → `interview_detail`, pencil → `interview_edit`, bin → POST `interview_delete`
  with confirm ("Delete this interview? This cannot be undone.")
- [ ] Empty state: "No interviews found." with "Schedule Interview" CTA
- [ ] Pagination using `page_obj`

### 9b. `interview/interview/detail.html`

- [ ] Interview hub. Header: INTV- number, title, status badge. Back to interview list link.
- [ ] **Sidebar** (action panel):
  - Status-transition buttons (POST forms with csrf_token): Confirm, Start, Complete, Cancel, No Show,
    Reschedule — each conditionally rendered (hide if already in that state; grey-out terminal states
    per status)
  - Edit button → `interview_edit`
  - Delete button (POST confirm) — only if not completed/cancelled
  - Send Interview Invite button (POST → `interview_send_invite`) — reuses `_send_candidate_email` with
    `interview_invite` template
  - Send Reminder button (POST → `interview_send_reminder`) — uses `interview_reminder` template;
    show label "Reminder Sent [date]" if `reminder_sent_at` is not null
- [ ] **Interview Details section**: application link (candidate name → `candidate_detail`, req title →
  `jobrequisition_detail`), round number, mode, scheduled_at (formatted), duration_minutes, location,
  video_provider + meeting_url (show as clickable link if present), interviewer_instructions, notes,
  scheduled_by
- [ ] **Panel section** (inline):
  - Table of `panelists` (interviewer name, role badge, RSVP status badge, briefing_notes truncated,
    notified_at). Per-row: RSVP update buttons (POST form → `interview_panelist_rsvp`); Remove button
    (POST → `interview_panelist_remove` with confirm)
  - "Add Panelist" mini-form (POST → `interview_panelist_add`): `InterviewPanelistForm` fields inline —
    interviewer dropdown, role dropdown, briefing_notes textarea
  - Empty state: "No panelists assigned."
- [ ] **Feedback section** (inline):
  - Table of `feedback_entries` per panelist (panelist name, recommendation badge, is_submitted badge,
    submitted_at, link to feedback detail)
  - Anti-anchoring note: "Other panelists' feedback is hidden until you submit your own." (shown to
    non-admin users who have an unsubmitted draft)
  - "Add Scorecard" link → `interviewfeedback_create?interview=<pk>` (pre-selects this interview)
- [ ] NOTE: pass `panelist_form`, `feedback_entries`, `panelists`, `status_choices` as context vars.
  Pass `request.user` so the template can apply anti-anchoring logic.

### 9c. `interview/interview/form.html`

- [ ] Shared create/edit form. `{% if is_edit %}Edit Interview{% else %}Schedule Interview{% endif %}`.
- [ ] Fields grouped: Basic Info (title, round_number, application), Schedule (scheduled_at with
  datetime-local input, duration_minutes, scheduled_by), Location (mode, location — shown if
  `mode == in_person`), Video (video_provider, meeting_url — shown when `mode == video`),
  Instructions (interviewer_instructions, notes).
- [ ] Help text on status: "Status is managed via the pipeline actions on the interview detail page."
- [ ] Show link: if `meeting_url` is populated on edit, display it as a clickable preview.

### 9d. `interview/interviewfeedback/list.html`

- [ ] Extends `base.html`. Page title: "Interview Scorecards". Filter bar with:
  - Text search (`q`)
  - Recommendation dropdown (`recommendation`) — from `recommendation_choices`; badge colors:
    strong_no=red, no=orange, maybe=amber, yes=blue, strong_yes=green
  - Submitted filter (`is_submitted`) — from `[("true","Submitted"),("false","Draft")]`
  - Interview dropdown (`interview`) — from `interviews` queryset; FK `|stringformat:"d"`
  - Clear filters
- [ ] Table: Number, Interview (title + link), Submitted By, Recommendation badge, Criteria count
  (`obj.criteria.count()`), Submitted badge (Yes/Draft), Submitted At, Actions (view/edit/delete)
- [ ] Actions: eye → `interviewfeedback_detail`, pencil → `interviewfeedback_edit`, bin → POST delete
  (disabled with tooltip if `is_submitted`)
- [ ] Empty state: "No scorecards found." with "Add Scorecard" CTA

### 9e. `interview/interviewfeedback/detail.html`

- [ ] Scorecard hub. Header: IFB- number, recommendation badge, submitted badge. Back to feedback list link.
- [ ] **Sidebar**: Submit Scorecard button (POST → `interviewfeedback_submit`; disabled if
  `is_submitted`). Edit button → `interviewfeedback_edit` (disabled if submitted). Delete button (POST;
  disabled if submitted). Back to interview detail link.
- [ ] **Feedback Details section**: interview link, panelist name (via `panelist.interviewer`), submitted_by,
  overall_recommendation display, summary, is_submitted, submitted_at.
- [ ] **Criteria inline section**:
  - Table of `criteria` (criterion_name, rating badge (1-5 colored stars or number badge), notes
    truncated). Per-row: Remove button (POST → `feedbackcriterion_delete` — disabled if submitted).
  - "Add Criterion" mini-form (POST → `feedbackcriterion_add`): `FeedbackCriterionForm` fields inline —
    criterion_name, rating (1-5 number input), notes.
  - If submitted: hide add/remove forms; show "Submitted scorecards are read-only." notice.
  - Empty state: "No criteria added yet."

### 9f. `interview/interviewfeedback/form.html`

- [ ] Shared create/edit form. `{% if is_edit %}Edit Scorecard{% else %}Add Scorecard{% endif %}`.
- [ ] Fields: interview (FK dropdown, pre-selectable from `?interview=<pk>` GET param — set `initial`
  in view if GET param present), panelist (FK dropdown — filtered to panelists of the selected
  interview if possible; otherwise all tenant panelists), overall_recommendation, summary,
  is_submitted checkbox.
- [ ] Help text on `submitted_by`: "Automatically set to the current user when the scorecard is created."
- [ ] Help text on `is_submitted`: "Once submitted, the scorecard becomes read-only. Use the 'Submit
  Scorecard' action on the detail page for formal submission."

---

## 10. Seeder — extend `apps/hrm/management/commands/seed_hrm.py`

All new 3.7 seed logic is added as a new idempotent block inside the existing `handle()` method
(after the 3.6 candidate block). The management command file and both `__init__.py` files
already exist — no new files needed.

- [ ] Add a per-tenant guard at the top of the 3.7 block:
  ```python
  if Interview.objects.filter(tenant=tenant).exists():
      self.stdout.write("3.7 Interview data already exists. Skipping.")
  else:
      # ... seed 3.7 data
  ```

- [ ] Import the new models at the top of `seed_hrm.py`:
  `from apps.hrm.models import Interview, InterviewPanelist, InterviewFeedback, FeedbackCriterion`

- [ ] Add an `interview_reminder` `CandidateEmailTemplate` per tenant (idempotent via
  `get_or_create(tenant=tenant, name="Interview Reminder — Standard")`):
  - name: "Interview Reminder — Standard"
  - template_type: "interview_reminder"
  - subject: "Reminder: Your interview for {{job_title}} is coming up"
  - body_html: "Dear {{candidate_name}},\n\nThis is a friendly reminder that your interview for the
    {{job_title}} position at {{company_name}} is scheduled. Please contact us if you have any
    questions.\n\nBest regards,\n{{recruiter_name}}"
  - is_active: True, is_auto_send: False

- [ ] Seed **2 `Interview` records** per tenant (idempotent: check `Interview.objects.filter(tenant=tenant,
  number=number).first()` — use `next_number` to compute the expected number, or simply check
  `Interview.objects.filter(tenant=tenant, title=title, application=app).first()`):
  - Requires existing `JobApplication` rows (from 3.6 seed). Check
    `JobApplication.objects.filter(tenant=tenant).first()` — skip with a warning if none exist.
  - Interview 1: `title="Technical Round 1"`, `round_number=1`, `mode="video"`,
    `scheduled_at=now()+timedelta(days=3)`, `duration_minutes=60`, `video_provider="meet"`,
    `meeting_url="https://meet.google.com/demo-link"`, `status="scheduled"`,
    linked to the first application at stage "interview" (or first available application)
  - Interview 2: `title="HR Final Round"`, `round_number=2`, `mode="in_person"`,
    `scheduled_at=now()+timedelta(days=7)`, `duration_minutes=45`, `location="Board Room A"`,
    `status="confirmed"`, linked to the same or second application

- [ ] Seed **1–2 `InterviewPanelist` records** per interview (idempotent via
  `get_or_create(interview=intv, interviewer=user)`):
  - Use the tenant admin user (or any user returned by
    `User.objects.filter(tenant_memberships__tenant=tenant).first()`) as the panelist.
  - `role="lead"`, `rsvp_status="accepted"`, `notified_at=now()`

- [ ] Seed **1 `InterviewFeedback` + 3 `FeedbackCriterion` records** per interview (idempotent):
  - Feedback: `overall_recommendation="yes"`, `summary="Strong candidate; clear technical knowledge
    and good cultural fit."`, `is_submitted=True`, `submitted_at=now()`, `submitted_by=tenant_admin`
  - Criteria (idempotent via `get_or_create(feedback=fb, criterion_name=name)`):
    - ("Problem Solving", 4, "Solved the technical problem with a clear approach.")
    - ("Communication",  5, "Articulate and well-organized answers.")
    - ("Culture Fit",    4, "Aligns with company values.")

- [ ] Print after seeding: `"3.7 Interview data seeded for tenant <slug>."` and remind:
  `"Login as admin_<slug> to see Interview data. Superuser 'admin' has no tenant."`

---

## 11. Verify

- [ ] `python manage.py makemigrations` — confirm no unapplied changes remain
- [ ] `python manage.py migrate` — confirm `0014_interview_process` applied cleanly
- [ ] `python manage.py seed_hrm` (run twice — second run must print "already exists" guard and skip
  the 3.7 block cleanly without errors)
- [ ] `python manage.py check` — zero errors/warnings

- [ ] **Smoke script** — create `temp/smoke_37.py`:
  1. Log in as `admin_acme` (tenant user). GET all 3.7 routes — expect 200:
     - `hrm:interview_list`, `hrm:interview_create`
     - `hrm:interview_detail` (pk of first seeded interview)
     - `hrm:interview_edit` (same pk)
     - `hrm:interviewfeedback_list`, `hrm:interviewfeedback_create`
     - `hrm:interviewfeedback_detail` (pk of first seeded feedback)
     - `hrm:interviewfeedback_edit` (same pk)
  2. POST status transitions — expect 302:
     - `hrm:interview_confirm` (pk of first scheduled interview)
     - `hrm:interview_complete` (same)
  3. POST panelist add — expect 302:
     - `hrm:interview_panelist_add` (pk=first interview) with valid interviewer pk + role
  4. POST feedback submit — expect 302:
     - `hrm:interviewfeedback_submit` (pk of first draft feedback)
  5. POST feedback criterion add — expect 302 or 400 if already submitted:
     - `hrm:feedbackcriterion_add` (pk of first feedback) with criterion_name + rating
  6. **Cross-tenant IDOR**: GET `hrm:interview_detail` (pk from acme) as `admin_beta` user — expect 404
  7. **Template leak scan**: search rendered HTML for `{#` or `{% comment` — expect zero hits
  8. **`?mode=video` filter**: GET `hrm:interview_list?mode=video` — expect 200 and only video-mode rows
  9. Print "ALL 3.7 SMOKE CHECKS PASSED" or list failures

- [ ] Verify sidebar shows 3.7 sub-module bullets as **Live** (green links) when logged in as `admin_acme`

---

## 12. Close-out

- [ ] Run the full Module Creation Sequence review agents (in order, one at a time):
  1. `code-reviewer` agent
  2. `explorer` agent
  3. `frontend-reviewer` agent
  4. `performance-reviewer` agent
  5. `qa-smoke-tester` agent
  6. `security-reviewer` agent
  7. `test-writer` agent
- [ ] Update `.claude/skills/hrm/SKILL.md`: add 3.7 models (`Interview`/`InterviewPanelist`/
  `InterviewFeedback`/`FeedbackCriterion`), URL names, templates
  (`hrm/interview/interview/`, `hrm/interview/interviewfeedback/`), seeder additions
  (`Interview`/`InterviewPanelist`/`InterviewFeedback`/`FeedbackCriterion` + interview_reminder
  CandidateEmailTemplate), and the `LIVE_LINKS["3.7"]` wiring. Update "table count" and "templates
  count" in the skill header.

---

## Later passes / deferred (from research-interview-process.md)

- **Live calendar sync (Google Calendar / Outlook OAuth)** — two-way calendar sync via OAuth2 + webhook.
  `calendar_event_id` field OMITTED this pass; add as a plain CharField when OAuth is plumbed.
  (Seen: all 10 products)
- **Candidate self-scheduling portal** — slot picker backed by real calendar availability. Store
  `candidate_self_schedule_url` OMITTED this pass (use `meeting_url` for a manual Calendly link).
  (Seen: Greenhouse, Lever, Ashby, GoodTime)
- **Zoom/Teams/Meet OAuth auto-link generation** — call provider API on interview save; `meeting_url`
  is stored manually for now. (Seen: Recruitee, BambooHR, Workable)
- **SMS/WhatsApp reminders** — Twilio/WhatsApp Business API; `CandidateCommunication.channel` already
  supports the value. (Seen: GoodTime, Recruitee)
- **One-way / async video interviews** — candidates record answers; requires video hosting (Spark Hire /
  HireVue embed). (Seen: Spark Hire, HireVue, Zoho, SmartRecruiters)
- **AI scorecard summarization** — LLM-powered summary across all panelist scorecards. (Seen: Greenhouse,
  Ashby, Lever)
- **AI video scoring** — Spark Hire/HireVue dimensions (Communication, Enthusiasm, Comprehension).
  (Deferred)
- **Interviewer load balancing (AI)** — GoodTime-style AI-driven panelist selection by availability
  and past load. (Deferred)
- **Interview kit / question bank templates** — re-usable default `FeedbackCriterion` name sets per job
  type so scorecards are consistently pre-populated. Simple catalog table; next pass candidate.
- **Scorecard editing window (admin-gated)** — Greenhouse allows editing up to 30 days post-submission
  for admins. Add a time-window guard + `@tenant_admin_required` gate in a future pass.
- **Celery/async reminder dispatch** — `reminder_sent_at` / `feedback_reminder_sent_at` stubs are in
  place; the actual Celery beat task that reads those fields and fires emails is a separate infra pass.
- **Feedback blinding enforcement (strict)** — current pass uses view-level conditional display;
  a future pass can enforce it at the queryset level (ORM annotation) for airtight anti-anchoring.

---

## Review notes — HRM 3.7 Interview Process (close-out)

**Delivered (one sub-module, per the build unit).** 4 tenant-scoped models on the existing 3.6 `JobApplication`
spine: `Interview` [INTV-] (round + mode + 7-status workflow machine + video link + reminder stamps),
`InterviewPanelist` (interviewer seat + role + RSVP, inline), `InterviewFeedback` [IFB-] (per-panelist scorecard,
5-level recommendation, action-only submit), `FeedbackCriterion` (1–5 per-competency rating, inline). Full CRUD +
status machine (confirm/start/complete/cancel/no_show + terminal guard + reschedule-reopen), panel add/remove/RSVP,
candidate invite/reminder (reuse `_send_candidate_email` + `CandidateCommunication`, honor `do_not_contact`), panel
feedback-request, scorecard submit + inline criteria. Wired: `LIVE_LINKS["3.7"]` (5 bullets; Video Interview deep-
links `?mode=video`), idempotent `_seed_interviews`, migrations `0014`+`0015`, 8 templates (`interview/` submodule).

**Verification.** `manage.py check` clean; migrate clean to `nav_erp`; seed idempotent (2 interviews / 4 panelists /
1 scorecard / 3 criteria per tenant); my smoke test (9 routes 200/302, IDOR→404, no leaks); qa-smoke-tester 49/49
PASS (GET + POST-action + IDOR sweep); test-writer **141 new tests**, full HRM suite **1,297 passed / 0 failed**
(3,944 project-wide), zero regressions, no product bugs.

**Review-agent sequence (all 7 ran).**
- `code-reviewer` — 2 critical + 4 important fixed: scorecard could be un-submitted via the edit form (removed
  `is_submitted` from the form — submit is action-only); no one-scorecard-per-panelist constraint (added
  `unique_together (interview,panelist)`, portable on MariaDB via NULL-distinct UNIQUE); edits now land on the detail
  hub with `_form_changes` audit diffs; dropped an unused `feedback_count` annotation; module-level `parse_datetime`;
  past-time reschedule warning.
- `explorer` — clean (URL/arg, context-var, FK-null guards, LIVE_LINKS, badge choices all consistent).
- `frontend-reviewer` — 3 applied (reschedule label `for`/`id`; `<p>`→`<div>` button wrapper; `.text-muted` for
  status confirmations). `avg_rating` flag was a false positive (the detail view passes it as a context var; `obj`
  isn't annotated there). `th-actions`/sub-table-empty nits left as app-wide reference patterns (L28).
- `performance-reviewer` — clean across all 8 categories (every loop FK `select_related`, all counts/averages are SQL
  annotations, composite indexes cover every filter+sort, dropdowns select_related their `__str__` traversals).
- `qa-smoke-tester` — 49/49 pass, no code changes needed.
- `security-reviewer` — no Critical/High; 3 hardening fixes applied: a new reusable `core` `|safe_external_url` filter
  guards the `meeting_url` href against `javascript:`/`data:` (defense-in-depth beyond URLField); `interview_delete`
  + `interviewfeedback_delete` gated to `@tenant_admin_required` (matched the templates' admin-only buttons); create-
  path panelist dropdown scoped to the selected interview (clean() backstop retained).
- `test-writer` — the 141-test suite above (covers the 4 flagged gaps: edit-can't-unsubmit, cross-interview
  panelist, reschedule-reopen, no-template email fallback; + IDOR, admin-gated deletes, the URL-safety filter).

**Deferred (carried forward, see the skill's Deferred section):** live calendar OAuth + ICS; Zoom/Teams/Meet auto-
link generation; candidate self-scheduling portal; SMS/WhatsApp reminders; one-way async video capture; AI scorecard
summarization + AI video scoring; interviewer load-balancing; interview-kit/question-bank catalog; strict queryset-
level feedback blinding; admin-gated scorecard edit window; and the Celery beat task for timed reminder dispatch
(reminders/invites are manual actions; `reminder_sent_at`/`feedback_reminder_sent_at` record the last send).

**Next sub-module:** 3.8 Offer Management (FKs into the built `JobApplication`; an offer follows a completed 3.7
interview/scorecards).

---
# HRM Sub-module 3.8 — Offer Management (hrm) — plan from research-hrm-offer-management.md  (2026-07-01)

**Extending `apps/hrm`** — NOT a new app. `apps.py`, `__init__.py`, `config/settings.py`, `config/urls.py` are
already wired for `hrm`. The only new wire-up is ONE `LIVE_LINKS["3.8"]` entry + URL patterns appended to the
existing `apps/hrm/urls.py`. **5 models** (research's optional 5th is IN SCOPE — see decision below): `Offer`
[OFR-], `OfferApproval` (child, no number), `BackgroundVerification` [BGV-], `PreboardingItem` (child, no number),
`OfferLetterTemplate` [OLTMPL-]. Sub-module template folder: `templates/hrm/offer/`. Builds on the existing 3.5
`JobRequisition` (salary band + `is_overdue` pattern), 3.6 `JobApplication`/`CandidateEmailTemplate`/
`CandidateCommunication`/`_send_candidate_email`, and mirrors the 3.5 `RequisitionApproval` + 3.7
`InterviewPanelist`/`FeedbackCriterion` inline-child conventions exactly. Next migration file:
`apps/hrm/migrations/0016_offer_management.py` (last is `0015_alter_interviewfeedback_unique_together.py`).

## 0. Template-folder decision + OfferLetterTemplate call

- [ ] Confirm folder shape (CLAUDE.md rule 2 — multi-entity sub-module):
  `templates/hrm/offer/offer/{list,detail,form}.html`,
  `templates/hrm/offer/backgroundverification/{list,detail,form}.html`,
  `templates/hrm/offer/offerlettertemplate/{list,detail,form}.html`.
  `OfferApproval` + `PreboardingItem` are child rows managed on `offer/offer/detail.html` (no standalone
  list/CRUD pages — mirrors `RequisitionApproval` and `InterviewPanelist`/`FeedbackCriterion`).
- [ ] Standalone printable letter page at the sub-module root (rule 6, mirrors `relieving_letter.html`):
  `templates/hrm/offer/offer_letter.html`.
- [ ] **Decision: include `OfferLetterTemplate` as the 5th model** (research flagged this as optional/
  todo's-call). Rationale: it costs one small `TenantNumbered` catalog table (mirrors
  `CandidateEmailTemplate` exactly — same `name`/`is_active`/`body_html` shape), keeps the printable
  letter body reusable + merge-tokenized across offers instead of freezing it into a single TextField on
  `Offer`, and gives 3.8's "Offer Letter Generation" bullet a real list page to point `LIVE_LINKS` at. A
  bare `body_html` TextField directly on `Offer` was rejected — it would force copy/pasting the same
  boilerplate letter body onto every new offer with no template reuse.

## 1. Models (apps/hrm/models.py) — fields driven by research features

- [ ] **`OfferLetterTemplate(TenantNumbered)`** [`NUMBER_PREFIX = "OLTMPL"`] — mirrors
  `CandidateEmailTemplate`'s shape (driver: Offer Letter Generation — Greenhouse/Lever/Workday/Oracle
  Taleo template-token pattern):
  - `name` CharField(255)
  - `is_active` BooleanField(default=True)
  - `body_html` TextField — help_text documents merge fields: `{{candidate_name}}, {{job_title}},
    {{base_salary}}, {{currency}}, {{start_date}}, {{company_name}}, {{hiring_manager_name}}`
  - `Meta`: `ordering = ["name"]`, `unique_together = ("tenant", "name")`,
    index `["tenant", "is_active"]` (name `hrm_oltmpl_tenant_active_idx`)
  - No FK reuse beyond `TenantNumbered` — a standalone catalog like `CandidateEmailTemplate`.

- [ ] **`Offer(TenantNumbered)`** [`NUMBER_PREFIX = "OFR"`] — the offer-management hub, FK'd to
  `hrm.JobApplication` (not hard 1:1 — a re-issued offer supersedes rather than multiplies, mirrors how
  `Interview` FKs `JobApplication`):
  - `application` FK `hrm.JobApplication` (`on_delete=CASCADE`, `related_name="offers"`)
  - `offer_letter_template` FK `hrm.OfferLetterTemplate` (`on_delete=SET_NULL`, `null=True`, `blank=True`,
    `related_name="offers"`) — driver: Offer Letter Generation template-token pattern
  - Compensation breakdown (driver: "Variable compensation breakdown on the offer" — Workday comp bands /
    SAP SuccessFactors Offer Detail / CompUp+HiBob letter conventions):
    - `base_salary` DecimalField(max_digits=14, decimal_places=2)
    - `currency` CharField(max_length=3, default="USD") — help_text: "Defaults from the requisition's
      salary_currency at creation time" (view-layer default, not a DB default — mirrors how
      `JobRequisition.salary_currency` is a plain field, not derived)
    - `bonus_amount` DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    - `bonus_terms` TextField(blank=True)
    - `signing_bonus` DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    - `equity_terms` TextField(blank=True, help_text="Grant description / vesting schedule — equity plans
      aren't modeled as a structured table yet.")
    - `relocation_assistance` DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    - `benefits_summary` TextField(blank=True)
  - `start_date` DateField — proposed joining date
  - `expires_on` DateField(null=True, blank=True) + `is_overdue` property (driver: "Expected response/
    expiry date with overdue flag" — mirrors `JobRequisition.is_overdue` exactly: `expires_on is not None
    and expires_on < date.today() and status not in OFFER_TERMINAL_STATUSES`)
  - Workflow-owned (driver: "Offer status lifecycle" — universal P0 across all 10 surveyed products;
    "Approval blocks offer extension" — all 10 surveyed):
    - `status` CharField(max_length=20, choices=`OFFER_STATUS_CHOICES`, default="draft",
      `editable=False`) — choices: `draft / pending_approval / approved / extended / accepted / declined
      / rescinded / expired`
  - Decline tracking (driver: "Decline/rescind reason codes" — mirrors `JobApplication.rejection_reason`/
    `rejection_notes` exactly):
    - `decline_reason` CharField(max_length=30, choices=`OFFER_DECLINE_REASON_CHOICES`, blank=True) —
      choices: `salary / competing_offer / counteroffer / role_fit / culture_fit / timing / other`
    - `decline_notes` TextField(blank=True)
  - E-signature fields now, vendor wiring deferred (driver: "E-signature integration" P1):
    - `signed_document` FileField(upload_to="hrm/offers/signed/%Y/%m/", null=True, blank=True)
    - `signature_status` CharField(max_length=20, choices=`SIGNATURE_STATUS_CHOICES`, default="not_sent")
      — choices: `not_sent / sent / viewed / signed / declined`
  - Workflow stamps (`editable=False`, set only by POST actions):
    - `extended_by` FK `settings.AUTH_USER_MODEL` (`SET_NULL`, null/blank, `related_name="extended_offers"`)
    - `extended_at`, `accepted_at`, `declined_at`, `rescinded_at` — DateTimeField(null=True, blank=True,
      editable=False)
    - `created_by` FK `settings.AUTH_USER_MODEL` (`SET_NULL`, null/blank, `related_name="created_offers"`)
  - `notes` TextField(blank=True)
  - `Meta`: `ordering = ["-created_at"]`, `unique_together = ("tenant", "number")`, indexes:
    `["tenant", "status"]` (`hrm_ofr_tenant_status_idx`), `["tenant", "application"]`
    (`hrm_ofr_tenant_app_idx`), `["tenant", "created_at"]` (`hrm_ofr_tenant_created_idx`)
  - `clean()`: `expires_on` must be >= `start_date` when both set is NOT required (expiry is response
    deadline, start_date is joining date — they're independent); instead guard `bonus_amount`/
    `signing_bonus`/`relocation_assistance` >= 0 when set (`ValidationError` per field) — mirrors the
    `JobRequisition.clean()` guard-per-field pattern.
  - `is_overdue` property (see above).
  - `@property is_closed` — `status in OFFER_TERMINAL_STATUSES` where
    `OFFER_TERMINAL_STATUSES = ("accepted", "declined", "rescinded", "expired")` (mirrors
    `Interview.is_closed`/`INTERVIEW_TERMINAL_STATUSES`).
  - `@property approval_progress` — `(approved_count, total_count)` over `self.approvals.all()`, mirrors
    `JobRequisition.approval_progress` verbatim (same PERF docstring warning re: prefetch).
  - `@property current_approval_step` — lowest-`step_order` still-`pending` `OfferApproval`, mirrors
    `JobRequisition.current_approval_step` (same PERF warning).
  - `candidate`/`requisition` convenience properties via `self.application.candidate` /
    `self.application.requisition` (mirrors `Interview.candidate`/`Interview.requisition` — views that
    list offers must `select_related("application__candidate", "application__requisition")`).
  - Reuses: `hrm.JobApplication` (candidate + requisition reached through it — no duplicate candidate/req
    FK on `Offer`), `hrm.OfferLetterTemplate` (new, this pass). Drives `JobApplication.stage` → `"hired"` +
    `hired_on` stamp on the accept POST action (reuses existing fields, no schema change — mirrors how
    3.7's interview actions never touched `stage` and 3.6's own stage-advance actions do).

- [ ] **`OfferApproval(TenantOwned)`** — no number, child of `Offer`, mirrors `RequisitionApproval` field-
  for-field (driver: "Multi-level/multi-step approval chain" — P0 across Lever/Workday/Oracle
  Taleo/SAP SuccessFactors/Ashby; "Approver picked from configurable approver roles" — reuse
  `APPROVER_ROLE_CHOICES` verbatim, same choice set as `RequisitionApproval`):
  - `offer` FK `hrm.Offer` (`on_delete=CASCADE`, `related_name="approvals"`)
  - `step_order` PositiveSmallIntegerField(default=1)
  - `approver` FK `settings.AUTH_USER_MODEL` (`SET_NULL`, null/blank, `related_name="hrm_offer_approvals"`)
  - `approver_role` CharField(max_length=20, choices=`APPROVER_ROLE_CHOICES` — REUSE the existing
    hrm.models constant, do not redefine, default="hr")
  - `status` CharField(max_length=20, choices=`APPROVAL_STEP_STATUS_CHOICES` — REUSE the existing
    constant, default="pending", `editable=False`)
  - `decided_at` DateTimeField(null=True, blank=True, editable=False)
  - `decided_by` FK `settings.AUTH_USER_MODEL` (`SET_NULL`, null/blank,
    `related_name="hrm_offer_approval_decisions"`, editable=False)
  - `comments` TextField(blank=True)
  - `Meta`: `ordering = ["step_order"]`, `unique_together = ("offer", "step_order")`, indexes:
    `["offer", "status"]` (`hrm_oa_offer_status_idx`), `["approver", "status"]`
    (`hrm_oa_approver_status_idx`)
  - `clean()`: `step_order >= 1` guard (mirrors `RequisitionApproval.clean()`)
  - The "approval blocks extension" P0 finding = the `Offer.status` gate in the `offer_extend` view action
    (can't extend while `status == "pending_approval"` or any step not approved) — no schema impact,
    view-layer guard exactly like `jobrequisition_post` gates on `status == "approved"`.
  - Conditional/threshold-based extra-step insertion (Lever/Ashby P1) — a simple constant threshold check
    in the chain-builder service function (see Services below), NOT a configurable rule engine this pass.

- [ ] **`BackgroundVerification(TenantNumbered)`** [`NUMBER_PREFIX = "BGV"`] — FK'd to `Offer` (checks are
  ordered post-offer-extension in every surveyed workflow):
  - `offer` FK `hrm.Offer` (`on_delete=CASCADE`, `related_name="background_checks"`)
  - `vendor` CharField(max_length=30, choices=`BGV_VENDOR_CHOICES`, blank=True) — choices: `checkr /
    hireright / sterling / other` (driver: "vendor-integrated ordering" — iCIMS/Zoho/BambooHR partner
    marketplace pattern, field only, no live API)
  - `check_type` CharField(max_length=30, choices=`BGV_CHECK_TYPE_CHOICES`, default="employment") —
    choices: `criminal / employment / education / professional_license / identity / credit` (driver:
    Checkr's typed-verification-category finding)
  - `status` CharField(max_length=20, choices=`BGV_STATUS_CHOICES`, default="not_started",
    `editable=False`) — choices: `not_started / consent_pending / initiated / in_progress /
    action_needed / ready_for_review / completed` (driver: Checkr/Sterling/HireRight standardized
    lifecycle)
  - `result` CharField(max_length=20, choices=`BGV_RESULT_CHOICES`, blank=True) — choices: `clear /
    consider / not_applicable` (driver: same standardized-lifecycle finding — separate overall result)
  - `consent_given` BooleanField(default=False), `consent_date` DateTimeField(null=True, blank=True,
    editable=False) (driver: "Consent capture before initiating a check" P1)
  - `report_file` FileField(upload_to="hrm/offers/bgv_reports/%Y/%m/", null=True, blank=True) (driver:
    "Report/document attachment" P1)
  - `initiated_at`, `completed_at` — DateTimeField(null=True, blank=True, editable=False)
  - `initiated_by` FK `settings.AUTH_USER_MODEL` (`SET_NULL`, null/blank,
    `related_name="initiated_bgv_checks"`)
  - `notes` TextField(blank=True)
  - `Meta`: `ordering = ["-created_at"]`, `unique_together = ("tenant", "number")`, indexes:
    `["tenant", "status"]` (`hrm_bgv_tenant_status_idx"`), `["tenant", "offer"]` (`hrm_bgv_tenant_ofr_idx`),
    `["tenant", "check_type"]` (`hrm_bgv_tenant_type_idx`)
  - Reuses `hrm.Offer` → `hrm.JobApplication` → `hrm.CandidateProfile` chain for candidate identity —
    NEVER re-store name/DOB/address on `BackgroundVerification` (iCIMS "pre-populated candidate data"
    finding — view-layer convenience when rendering the initiate form, not a schema change).
  - Adverse-action/dispute sub-flow explicitly OUT of scope (see Deferred).

- [ ] **`PreboardingItem(TenantOwned)`** — no number, child of `Offer`, deliberately distinct from the
  existing 3.3 `OnboardingDocument`/`OnboardingTask` (those own post-start collection; this owns pre-start,
  offer-tied, candidate-facing collection):
  - `offer` FK `hrm.Offer` (`on_delete=CASCADE`, `related_name="preboarding_items"`)
  - `document_type` CharField(max_length=30, choices=`PREBOARDING_DOC_TYPE_CHOICES`, default="other") —
    choices: `id_proof / address_proof / tax_form / bank_details / nda / education_certificate /
    background_check_consent / other` (driver: HiBob/iCIMS document-collection convention)
  - `is_required` BooleanField(default=True)
  - `status` CharField(max_length=20, choices=`PREBOARDING_STATUS_CHOICES`, default="pending",
    `editable=False`) — choices: `pending / submitted / verified / rejected` (driver: mirrors
    `OnboardingTask`/`ClearanceItem` status-child convention already in HRM)
  - `uploaded_file` FileField(upload_to="hrm/offers/preboarding/%Y/%m/", null=True, blank=True)
  - `submitted_at` DateTimeField(null=True, blank=True, editable=False)
  - `verified_by` FK `settings.AUTH_USER_MODEL` (`SET_NULL`, null/blank, `related_name="verified_preboarding_items"`)
  - `verified_at` DateTimeField(null=True, blank=True, editable=False)
  - `reminder_sent_at` DateTimeField(null=True, blank=True, editable=False) — manual-action stamp,
    mirrors `Interview.reminder_sent_at` exactly; reuses `_send_candidate_email`/`CandidateCommunication`
    for the invite/reminder send (driver: "scheduled/timed invitation to complete pre-boarding" —
    manual-trigger this pass, Celery-style auto-scheduling deferred)
  - `notes` TextField(blank=True)
  - `Meta`: `ordering = ["document_type", "pk"]`, indexes: `["tenant", "offer"]` (`hrm_pbi_tenant_ofr_idx`),
    `["tenant", "status"]` (`hrm_pbi_tenant_status_idx`)
  - Hand-off to full 3.3 onboarding on full completion (all `is_required` items `verified`) is a view-layer
    trigger point noted in the `offer_accept` action's docstring — no new model, no forced auto-creation
    of `OnboardingProgram` this pass (flag as a TODO comment at the trigger point instead of building it,
    since 3.3's `OnboardingProgram` creation flow already has its own entry points).

- [ ] Add module-level `CHOICES` constants above `Offer`: `OFFER_STATUS_CHOICES`,
  `OFFER_DECLINE_REASON_CHOICES`, `SIGNATURE_STATUS_CHOICES`, `OFFER_TERMINAL_STATUSES` (tuple),
  `BGV_VENDOR_CHOICES`, `BGV_CHECK_TYPE_CHOICES`, `BGV_STATUS_CHOICES`, `BGV_RESULT_CHOICES`,
  `PREBOARDING_DOC_TYPE_CHOICES`, `PREBOARDING_STATUS_CHOICES` — grouped under a `# 3.8 Offer Management`
  section-comment banner (mirrors the `# 3.7 Interview Process` banner style at line ~2094), documenting
  the reuse-vs-new spine call per the module docstring convention.
- [ ] Confirm `APPROVER_ROLE_CHOICES` / `APPROVAL_STEP_STATUS_CHOICES` (defined ~line 1533-1547) are
  imported/reused as-is for `OfferApproval` — do NOT redefine a parallel choice set.

## 2. Services (apps/hrm/services.py)

- [ ] `_DEFAULT_OFFER_APPROVAL_CHAIN = [(1, "hiring_manager"), (2, "hr")]` constant (offer approval chain
  is simpler than the requisition's hr→executive chain per research — HR + hiring manager sign-off is the
  P0 baseline; append a 3rd `executive` step when `total_compensation > settings.OFFER_APPROVAL_THRESHOLD`
  or a simple hardcoded constant, e.g. `Decimal("150000")` annual base — implements the Lever/Ashby
  conditional-routing P1 finding as a **simple threshold**, not a rule engine).
- [ ] `generate_offer_approval_chain(offer)` — idempotent, mirrors `generate_approval_chain(requisition)`
  verbatim: returns existing chain untouched if any `OfferApproval` rows exist; else bulk-creates the
  default chain (+ the conditional executive step if base_salary+bonus+signing_bonus exceeds the
  threshold); shared by `views.offer_submit` and the seeder.
- [ ] `_PREBOARDING_CHECKLIST = [(doc_type, is_required), ...]` default lines (mirrors `_CLEARANCE_LINES`)
  covering `id_proof(required)/address_proof(required)/tax_form(required)/bank_details(required)/
  nda(required)/background_check_consent(required)/education_certificate(optional)`.
- [ ] `generate_preboarding_checklist(offer)` — idempotent (keyed on `document_type`), mirrors
  `generate_clearance_checklist(case)`; called on offer acceptance (offer_accept view action) and by the
  seeder.

## 3. Forms (apps/hrm/forms.py)

- [ ] `OfferForm(ModelForm)` — Meta.model=Offer, exclude `tenant`, `number`, `status`, `extended_by`,
  `extended_at`, `accepted_at`, `declined_at`, `rescinded_at`, `created_by` (workflow-owned/derived —
  never on the form). Include: `application`, `offer_letter_template`, `base_salary`, `currency`,
  `bonus_amount`, `bonus_terms`, `signing_bonus`, `equity_terms`, `relocation_assistance`,
  `benefits_summary`, `start_date`, `expires_on`, `decline_reason`, `decline_notes`, `signed_document`,
  `signature_status`, `notes`. `application` queryset scoped to `tenant` filtered to applications without
  an existing non-terminal offer (or all applications on create with a form-level warning) — follow the
  `__init__(self, *args, tenant=None, **kwargs)` convention used by every other HRM form.
  `decline_reason`/`decline_notes`/`signature_status` stay on the form (not workflow-status but
  recruiter-editable annotations, same as `JobApplication.rejection_reason` being form-editable).
- [ ] `OfferApprovalForm(ModelForm)` — Meta.model=OfferApproval, exclude `tenant`, `offer`, `status`,
  `decided_at`, `decided_by` (mirrors `RequisitionApprovalForm`). Fields: `step_order`, `approver`,
  `approver_role`, `comments`. `approver` queryset = tenant Users.
- [ ] `BackgroundVerificationForm(ModelForm)` — Meta.model=BackgroundVerification, exclude `tenant`,
  `number`, `offer`(set in view from URL), `status`, `initiated_at`, `completed_at`, `initiated_by`.
  Fields: `vendor`, `check_type`, `result`, `consent_given`, `consent_date`, `report_file`, `notes`.
- [ ] `PreboardingItemForm(ModelForm)` — Meta.model=PreboardingItem, exclude `tenant`, `offer`, `status`,
  `submitted_at`, `verified_by`, `verified_at`, `reminder_sent_at`. Fields: `document_type`, `is_required`,
  `uploaded_file`, `notes`. Used for the inline add-item action on the offer detail hub.
- [ ] `OfferLetterTemplateForm(ModelForm)` — Meta.model=OfferLetterTemplate, exclude `tenant`, `number`.
  Fields: `name`, `is_active`, `body_html`.

## 4. Views (apps/hrm/views.py)

- [ ] **`Offer` full CRUD**: `offer_list` (`crud_list`, search_fields=`["number",
  "application__candidate__first_name", "application__candidate__last_name",
  "application__requisition__title"]`, filters=`[("status","status",False),
  ("signature_status","signature_status",False), ("currency","currency",False)]`,
  extra_context passes `status_choices`, `signature_status_choices`); `offer_create`
  (`@login_required`, stamps `created_by=request.user`, `currency` defaults from
  `application.requisition.salary_currency` when left blank); `offer_detail` (select_related
  `application__candidate`, `application__requisition`, `offer_letter_template`; prefetch `approvals`,
  `background_checks`, `preboarding_items`; passes `approval_progress`, forms for the inline add actions);
  `offer_edit` (only while `status in ("draft", "pending_approval")` — mirrors requisition's editable-
  while-draft-or-rejected guard, adapted); `offer_delete` (`@tenant_admin_required`, only `status ==
  "draft"`, mirrors `jobrequisition_delete`).
- [ ] **Offer status-machine actions** (all `@tenant_admin_required` + `@require_POST`, mirror
  `jobrequisition_submit`/`_approve_step`/`_reject`/`interview_confirm` patterns):
  - `offer_submit` — draft/rejected-equivalent → pending_approval; calls
    `generate_offer_approval_chain(obj)` inside `transaction.atomic()`; guard: only from `"draft"`.
  - `offer_approve_step` — approves the lowest-pending `OfferApproval`; when the last step clears, sets
    `Offer.status = "approved"`; guard: only while `status == "pending_approval"`.
  - `offer_reject_step` — rejects the pending step + sets `Offer.status = "rejected"`... **NOTE**:
    research's status list has no plain `"rejected"` — reuse `"declined"` is wrong (that's post-extension
    candidate action). Resolve by adding an internal-only terminal outcome: on approval rejection, set
    `Offer.status` back to `"draft"` (mirrors `jobrequisition_return`'s reopen-to-draft behavior) with a
    `comments` stamp on the step, rather than inventing a new status value — keeps `OFFER_STATUS_CHOICES`
    exactly as researched (draft/pending_approval/approved/extended/accepted/declined/rescinded/expired).
  - `offer_extend` — `status == "approved"` → `"extended"`; stamps `extended_by`/`extended_at`; sends the
    offer email via `_send_candidate_email(application, template_type="offer", ...)` reusing the existing
    `"offer"` `EMAIL_TEMPLATE_TYPE_CHOICES` value already defined on `CandidateEmailTemplate` (no new
    template-type choice needed); guard: all `approvals` must be `"approved"` (the P0 "approval blocks
    extension" gate) — else `messages.error` + no-op.
  - `offer_accept` — `status == "extended"` → `"accepted"`; stamps `accepted_at`; sets
    `application.stage = "hired"` + `application.hired_on = date.today()` inside `transaction.atomic()`
    (mirrors the 3.6 stage-advance convention — reuse existing fields, no new column); calls
    `generate_preboarding_checklist(obj)`; logs a `CandidateCommunication` via `_send_candidate_email` for
    the acceptance confirmation.
  - `offer_decline` — `status == "extended"` → `"declined"`; requires `decline_reason` from POST body
    (validated against `OFFER_DECLINE_REASON_CHOICES`); stamps `declined_at`, `decline_notes`.
  - `offer_rescind` — `status in ("extended", "approved", "pending_approval")` → `"rescinded"`; stamps
    `rescinded_at`; `@tenant_admin_required` (a rescission is a sensitive HR action).
  - `offer_expire` — `status == "extended"` and `is_overdue` → `"expired"`; manual-trigger action (button
    on detail page when overdue), mirrors the manual-action convention used throughout (no Celery cron
    this pass).
  - `offer_send_email` — `@require_POST`, ad-hoc resend of the offer-letter email via
    `_send_candidate_email(..., template_type="offer")`; available at any non-terminal status.
- [ ] **`OfferApproval` inline child actions** (mirror `approval_add`/`approval_delete` exactly):
  `offerapproval_add` (`@tenant_admin_required`, `@require_POST`, only while `offer.status == "draft"`,
  `IntegrityError` guard on duplicate `step_order`), `offerapproval_delete` (`@tenant_admin_required`,
  `@require_POST`, only while `offer.status == "draft"`).
- [ ] **`BackgroundVerification` full CRUD**: `backgroundverification_list` (filters:
  `status`, `check_type`, `vendor`), `backgroundverification_create` (offer set from URL `?offer=<pk>` or
  a FK dropdown scoped to tenant offers, `initiated_by=request.user` stamped on `initiate` action not on
  plain create), `backgroundverification_detail`, `backgroundverification_edit`,
  `backgroundverification_delete` (`@tenant_admin_required`). Plus status-machine POSTs:
  `backgroundverification_initiate` (`not_started`/`consent_pending` → `initiated`, requires
  `consent_given=True` first — else `messages.error` per the "consent before initiating" P1 finding;
  stamps `initiated_at`/`initiated_by`), `backgroundverification_mark_status` (generic POST accepting a
  `status` value from `{in_progress, action_needed, ready_for_review}`, validated against
  `BGV_STATUS_CHOICES`, manual stand-in for the deferred webhook), `backgroundverification_complete`
  (→ `"completed"`, requires a `result` value from POST, stamps `completed_at`).
- [ ] **`PreboardingItem` inline child actions** (mirror `feedbackcriterion_add`/`_delete` +
  `interview_send_reminder`): `preboardingitem_add` (`@require_POST`, uses `PreboardingItemForm`),
  `preboardingitem_delete` (`@require_POST`), `preboardingitem_mark_submitted` (candidate/HR marks
  uploaded — stamps `submitted_at`; sets `status="submitted"`),
  `preboardingitem_verify`/`preboardingitem_reject` (`@tenant_admin_required`, `@require_POST`, stamps
  `verified_by`/`verified_at`, sets `status` accordingly), `preboardingitem_send_invite` (reuses
  `_send_candidate_email(application, template_type="general", ...)` or a dedicated future
  `"preboarding_invite"` type — for this pass, fixed body via `default_subject`/`body` kwargs mirroring
  `interview_send_invite`'s `_send_interview_email` call shape; stamps `reminder_sent_at` on send).
- [ ] **`OfferLetterTemplate` full CRUD**: `offerlettertemplate_list` (search_fields=`["name",
  "body_html"]`, filters=`[("is_active","is_active",False)]`), `_create`, `_detail`, `_edit`, `_delete`
  (`@tenant_admin_required`).
- [ ] **Printable offer-letter view**: `offer_letter_print(request, pk)` — `@login_required`, renders
  `templates/hrm/offer/offer_letter.html` with `{"offer": obj, "application": obj.application, "candidate":
  ..., "tenant": request.tenant, "today": timezone.localdate()}`; merges `offer_letter_template.body_html`
  tokens the same way `_apply_merge`/`_send_candidate_email` does (reuse `_apply_merge` helper); sets
  `response["Content-Disposition"] = "inline"` — mirrors `_generate_letter`/`offboarding_letters` pattern.
  No DB write (pure read/render, unlike `_generate_letter`'s stamp-on-first-generate — an offer letter can
  be reprinted freely).
- [ ] Add a small `_offer_or_404(request, pk)` private helper (mirrors `_interview_or_404`) with the
  standard `select_related`.
- [ ] Every `@tenant_admin_required` placement above follows the existing convention: sensitive/authority
  actions (approve/reject/rescind/delete/verify) are admin-gated; candidate-facing sends and status marks
  a regular tenant user can perform stay `@login_required` only (matches 3.5/3.7's split).

## 5. URLs (apps/hrm/urls.py) — `app_name = "hrm"` (existing), append these path() lines

- [ ] Offer CRUD: `offers/` (`offer_list`), `offers/add/` (`offer_create`), `offers/<int:pk>/`
  (`offer_detail`), `offers/<int:pk>/edit/` (`offer_edit`), `offers/<int:pk>/delete/` (`offer_delete`)
- [ ] Offer actions: `offers/<int:pk>/submit/` (`offer_submit`), `offers/<int:pk>/approve-step/`
  (`offer_approve_step`), `offers/<int:pk>/reject-step/` (`offer_reject_step`),
  `offers/<int:pk>/extend/` (`offer_extend`), `offers/<int:pk>/accept/` (`offer_accept`),
  `offers/<int:pk>/decline/` (`offer_decline`), `offers/<int:pk>/rescind/` (`offer_rescind`),
  `offers/<int:pk>/expire/` (`offer_expire`), `offers/<int:pk>/send-email/` (`offer_send_email`),
  `offers/<int:pk>/letter/` (`offer_letter_print`)
- [ ] OfferApproval child: `offers/<int:pk>/approvals/add/` (`offerapproval_add`),
  `offer-approvals/<int:pk>/delete/` (`offerapproval_delete`)
- [ ] BackgroundVerification CRUD + actions: `background-checks/` (`backgroundverification_list`),
  `background-checks/add/` (`_create`), `background-checks/<int:pk>/` (`_detail`),
  `background-checks/<int:pk>/edit/` (`_edit`), `background-checks/<int:pk>/delete/` (`_delete`),
  `background-checks/<int:pk>/initiate/` (`_initiate`), `background-checks/<int:pk>/mark-status/`
  (`_mark_status`), `background-checks/<int:pk>/complete/` (`_complete`)
- [ ] PreboardingItem child: `offers/<int:pk>/preboarding/add/` (`preboardingitem_add`),
  `preboarding-items/<int:pk>/delete/` (`preboardingitem_delete`),
  `preboarding-items/<int:pk>/submit/` (`preboardingitem_mark_submitted`),
  `preboarding-items/<int:pk>/verify/` (`preboardingitem_verify`),
  `preboarding-items/<int:pk>/reject/` (`preboardingitem_reject`),
  `preboarding-items/<int:pk>/send-invite/` (`preboardingitem_send_invite`)
- [ ] OfferLetterTemplate CRUD: `offer-letter-templates/` (`offerlettertemplate_list`), `.../add/`
  (`_create`), `.../<int:pk>/` (`_detail`), `.../<int:pk>/edit/` (`_edit`), `.../<int:pk>/delete/`
  (`_delete`)

## 6. Admin (apps/hrm/admin.py)

- [ ] Register `Offer` (list_display: number, application, status, base_salary, currency, start_date,
  expires_on; list_filter: status, signature_status; search_fields: number,
  application__candidate__first_name/last_name), `OfferApproval` (inline `TabularInline` on `Offer`'s
  admin, read-only `decided_at`/`decided_by`), `BackgroundVerification` (list_display: number, offer,
  vendor, check_type, status, result), `PreboardingItem` (inline `TabularInline` on `Offer`'s admin),
  `OfferLetterTemplate` (list_display: number, name, is_active). Mirror `RequisitionApproval`'s admin
  inline pattern and `Interview`'s admin registration style exactly.

## 7. Migration

- [ ] `python manage.py makemigrations hrm` → produces `apps/hrm/migrations/0016_offer_management.py`
  (verify the auto-generated number matches; rename only if Django picks a different auto-slug, keep the
  `0016_` prefix). Single migration file for all 5 new models (mirrors `0014_interview_process.py`
  covering Interview+InterviewPanelist+InterviewFeedback+FeedbackCriterion in one file) — one commit.

## 8. Seed data (apps/hrm/management/commands/seed_hrm.py)

- [ ] New `_seed_offers(self, tenant, *, flush)` method, called from `handle()` alongside
  `_seed_interviews` — reuses EXISTING seeded `JobApplication` rows (prefer applications with
  `stage="offer"` or `"hired"`, falling back to any application — mirrors `_seed_interviews`'s apps_qs
  fallback pattern exactly). Idempotent: `if flush: Offer.objects.filter(tenant=tenant).delete()`
  (cascades approvals/bgv/preboarding); `if Offer.objects.filter(tenant=tenant).exists(): ... return`
  notice.
- [ ] Seed 1 `OfferLetterTemplate` ("Standard Offer Letter") with a realistic `body_html` using the
  documented merge tokens (`get_or_create` keyed on name).
- [ ] Seed 2 offers over the 2 existing applications used by `_seed_interviews` (or the next 2 available):
  one **accepted** end-to-end (status walked through submit→approve→extend→accept via the service
  functions / direct field assignment mirroring the seeder's existing style of calling `generate_*`
  helpers directly rather than re-deriving the state machine) with 2 `OfferApproval` rows (both approved)
  + a `BackgroundVerification` (`status="completed"`, `result="clear"`) + 3-4 `PreboardingItem` rows (mix
  of verified/submitted/pending); one **pending_approval** (draft submitted, 1 approved + 1 pending
  `OfferApproval` step) with no bgv/preboarding yet (not accepted). Uses `generate_offer_approval_chain`/
  `generate_preboarding_checklist` from `services.py` so the seeder and the views build identical shapes.
  Reuses existing tenant `Users` for `approver`/`extended_by`/`created_by` (no duplicate Users created).
- [ ] Print summary counts (Offers/OfferApprovals/BackgroundVerifications/PreboardingItems/
  OfferLetterTemplates seeded) in the same `self.stdout.write(self.style.SUCCESS(...))` style as
  `_seed_interviews`.

## 9. Wire-up

- [ ] `apps/core/navigation.py` — add `"3.8"` to `LIVE_LINKS` mapping the 5 exact NavERP.md bullet strings:
  ```python
  "3.8": {
      "Offer Letter Generation": "hrm:offerlettertemplate_list",   # bullet (template library)
      "Offer Approval": "hrm:offer_list?status=pending_approval",  # bullet (pending queue)
      "Offer Tracking": "hrm:offer_list",                          # bullet (all-status tracking)
      "Background Verification": "hrm:backgroundverification_list", # bullet (BGV records)
      "Pre-boarding": "hrm:offer_list?status=accepted",            # bullet (accepted offers = active preboarding)
  },
  ```
- [ ] No `settings.py`/`config/urls.py` changes needed — `hrm` app + include already registered (3.6/3.7
  precedent).

## 10. Templates (templates/hrm/offer/)

- [ ] `offer/offer/list.html` — filter bar (status, signature_status, currency dropdowns fed from
  `status_choices`/`signature_status_choices` passed by the view per Filter Implementation Rules), Actions
  column (view/edit-if-draft-or-pending_approval/delete-if-draft), badges for `status`/`is_overdue`
  (red "Overdue" pill mirroring `JobRequisition`'s), empty-state, pagination.
- [ ] `offer/offer/detail.html` — hub layout mirroring `jobrequisition_detail`/`interview_detail`: header
  (number, candidate name, requisition title, status badge, overdue flag), compensation-breakdown card,
  status-action buttons conditional on current `status` (submit/approve-step/reject-step/extend/accept/
  decline/rescind/expire/send-email/print-letter), inline `OfferApproval` chain table + add-step
  mini-form (admin-only, draft-only), inline `BackgroundVerification` list + "Order Check" link to create,
  inline `PreboardingItem` checklist + add-item mini-form + verify/reject buttons per row, decline-reason
  fields shown only when `status == "declined"`, signed-document download link guarded by
  `|safe_external_url` if ever rendered as an href (file field itself is safe — apply the filter only if a
  vendor URL field is later added).
- [ ] `offer/offer/form.html` — standard create/edit form (application dropdown, compensation fields
  grouped visually, `is_edit` conditional).
- [ ] `offer/backgroundverification/{list,detail,form}.html` — list has filter bar (status/check_type/
  vendor), Actions column (view/edit/delete + initiate/mark-status/complete buttons conditional on
  `status`), detail shows consent capture state + report_file download, form excludes workflow fields.
- [ ] `offer/offerlettertemplate/{list,detail,form}.html` — standard CRUD triple mirroring
  `candidateemailtemplate` templates (is_active toggle, merge-token help text shown on the form).
- [ ] `offer/offer_letter.html` — standalone printable letter (sub-module root per rule 6), mirrors
  `hrm/offboarding/relieving_letter.html` layout: letterhead, merged `offer_letter_template.body_html`,
  print-only CSS (`@media print`), a "Print" button hidden in print media.
- [ ] Every list template: no `{#`/`{% comment %}` leaks; every status/choice badge has an `{% else
  %}{{ obj.get_status_display }}{% endif %}` fallback (Filter Implementation Rule 5).

## 11. Verify

- [ ] `python manage.py makemigrations hrm` then `python manage.py migrate` — clean, no missing-migration
  warnings.
- [ ] `python manage.py seed_hrm` **twice** in a row — second run must be a no-op (idempotency check) and
  must print the "already exists... use --flush" notice for the offer section.
- [ ] `python manage.py check` — no errors.
- [ ] `temp/` smoke sweep (write a throwaway script under `temp/`, not committed... actually DO commit per
  the qa-smoke-tester convention if that's this repo's pattern — check existing `temp/` usage): as
  `admin_acme`, GET every new `hrm:offer_*`, `hrm:backgroundverification_*`, `hrm:offerlettertemplate_*`,
  `hrm:offerapproval_*` (POST-only, skip GET), `hrm:preboardingitem_*` (POST-only, skip GET) URL name →
  expect 200 (list/detail/form) or 302 (POST actions redirect); no `{#`/`{% comment` leaks in rendered
  HTML; cross-tenant IDOR check — as `admin_acme`, GET/POST another tenant's `Offer`/
  `BackgroundVerification`/`OfferLetterTemplate` pk → expect 404.
- [ ] Confirm sidebar shows all 5 new "3.8 Offer Management" bullets as **Live** (not "Coming Soon") after
  the `LIVE_LINKS["3.8"]` entry lands.

## 12. Close-out

- [ ] Update `.claude/tasks/todo.md` with a **Review notes — HRM 3.8 Offer Management (close-out)** section
  once built + reviewed (delivered scope, verification results, all 7 review-agent findings/fixes,
  deferred items, next sub-module pointer) — same shape as the 3.7 close-out above.
- [ ] Run the 7 review agents **in order**, one at a time, committing after each: `code-reviewer` →
  `explorer` → `frontend-reviewer` → `performance-reviewer` → `qa-smoke-tester` → `security-reviewer` →
  `test-writer`.
- [ ] Update `.claude/skills/hrm/SKILL.md` — add the 3.8 models/routes/templates/seeder/LIVE_LINKS
  sections (mirrors how 3.6/3.7 were folded in), bump the model/route/template counts.
- [ ] Update `README.md` roadmap — add a 3.8 Offer Management detail line, bump the HRM sub-module count
  (currently 10 of 41 after 3.7) to 11 of 41, refresh HRM + project-wide test counts once `test-writer`
  lands.

## Later passes / deferred (from research-hrm-offer-management.md)

- **Live e-signature vendor wiring** (DocuSign / Adobe Acrobat Sign / Dropbox Sign / Zoho Sign API) —
  `signed_document`/`signature_status` fields ship now; the actual send-for-signature + webhook + auto-
  attach flow is integration/later (mirrors 3.7's deferred live Zoom/Teams auto-link).
- **Live background-check vendor API wiring** (Checkr/HireRight/Sterling order-and-webhook automation) —
  `BackgroundVerification` ships as a manually-updated status/result record this pass.
- **Formal adverse-action/dispute compliance workflow** (pre-adverse notice → candidate response window →
  final adverse notice) for "Consider" results — legally significant, distinct compliance sub-flow, not
  blocking this pass's scope. Flag as a compliance gap in the skill's Deferred section.
- **Parallel (all-at-once) approval routing** — this pass ships sequential `step_order` chains only
  (matches `RequisitionApproval`); true parallel/any-N-of-M routing is a state-machine expansion.
- **Configurable conditional-routing rule engine** (per-department/per-level comp thresholds editable by
  admins) — ships as one hardcoded threshold constant this pass; a full rule-builder UI is deferred.
- **Configurable approval-notification field picker** (Greenhouse Oct-2025 style) — notifications reuse a
  fixed internal-approver notification body this pass.
- **Companion-document bundling** (NDA/drug-screening authorization sent alongside the offer letter as one
  package) — `PreboardingItem` covers ad-hoc document collection; a bundled multi-doc send workflow is
  deferred.
- **Offer acceptance-rate / decline-reason analytics dashboard** — underlying `status`/`decline_reason`
  fields ship this pass; a dedicated reporting/dashboard page is a later pass (fits under 3.32 Analytics
  Dashboard).
- **Welcome kit / policy acknowledgment** — already owned by the existing 3.3 Onboarding feature set; not
  duplicated under pre-boarding.
- **Template-usage scoping rules** (Ashby-style "only show templates valid for this candidate's
  level/department") — `OfferLetterTemplate` ships without a scoping filter this pass; add a simple FK/
  choice filter later if needed.
- **Scheduled/automated pre-boarding invite dispatch** (Celery-style "send N days before start date") —
  this pass ships a manual, audited send action (`reminder_sent_at`); automated scheduled dispatch is
  deferred, consistent with 3.7's own Celery-dispatch deferral.
- **Webhook receiver endpoint** for background-check vendor status push-back — `BackgroundVerification`
  ships the fields a webhook would write to (`status`, `result`, `report_file`); the receiver itself is
  integration/later.

## Review notes — HRM 3.8 Offer Management (close-out, 2026-07-02)

**Delivered scope (5 models over the 3.6 `JobApplication` spine):** `OfferLetterTemplate` (OLTMPL-), `Offer` (OFR-,
compensation breakdown + workflow status machine draft→pending_approval→approved→extended→accepted/declined/
rescinded/expired), `OfferApproval` (child, mirrors `RequisitionApproval`, reuses `APPROVER_ROLE_CHOICES`/
`APPROVAL_STEP_STATUS_CHOICES`), `BackgroundVerification` (BGV-, Checkr/Sterling status+result lifecycle),
`PreboardingItem` (child). Services `generate_offer_approval_chain` (Hiring-Manager→HR + Executive step when total
comp > `OFFER_APPROVAL_EXEC_THRESHOLD`=150k) + `generate_preboarding_checklist` (7 lines). Full CRUD + the status
machine (submit/approve-step/reject-step/extend/accept/decline/rescind/expire/send-email) + inline child actions +
printable `offer_letter_print` + BGV lifecycle. Offer acceptance drives `JobApplication.stage`→hired + hired_on and
raises the pre-boarding checklist. Offer emails reuse `_send_candidate_email`/`CandidateCommunication`. Migrations
`0016_offer_management` + `0017_...bgv_tenant_created_idx`. `LIVE_LINKS["3.8"]` wires all 5 NavERP.md bullets (Live).

**Verification:** `manage.py check` clean; `seed_hrm` idempotent (2nd run skips with notice); temp/ smoke sweep — all
new GET pages 200, filtered lists (`?status=pending_approval`/`accepted`) 200, cross-tenant IDOR 404, no
comment-leaks; full POST status-machine walk (submit→approve→extend→accept + BGV + pre-boarding) all 302 with correct
state. qa-smoke-tester: 76 checks, 0 failures. Test suite `test_offer_management.py` = **251 tests**, full HRM suite
**1,548 passing** (project-wide **4,195**), 0 regressions.

**Review-agent findings + fixes (7 agents, in order):**
- **code-reviewer** (5 fixed): dropped `result` from `BackgroundVerificationForm` (form-editable verdict bypassed the
  lifecycle gate); locked `backgroundverification_edit` once completed; restricted `offer_edit` to draft-only (comp
  change under approval would invalidate the executive-step threshold chain); guarded `preboardingitem_mark_submitted`
  to pending/rejected + clear stale verify stamps; blocked `preboardingitem_add` on declined/rescinded/expired offers;
  refreshed `_form_changes` docstring.
- **explorer** (1 bug + 1 dead-code fixed): `offer_submit` now resets the whole approval chain to pending so a
  reject→resubmit re-approves from the top (a stuck `rejected` step previously let the offer auto-approve early);
  dropped an unused `offers` queryset from `backgroundverification_list`.
- **frontend-reviewer** (2 fixed): background-check consent column uses `badge-green/muted` (the `.text-green` class
  didn't exist); the Update-Status dropdown loops a shared `BGV_MANUAL_TRANSITION_STATUSES` subset instead of
  hardcoded options. (Reviewer's suggested parenthesised `{% if a and (b or c) %}` was NOT applied — Django `{% if %}`
  has no parentheses; the nested-`{% if %}` form is the correct equivalent.)
- **performance-reviewer** (2 fixed): `_offer_or_404` select_related the requisition's `hiring_manager__party` (was 2
  extra queries per letter print); added a `(tenant, created_at)` index to `BackgroundVerification` backing its
  default ordering. Otherwise N+1-free (list select_related chains + prefetched detail children confirmed).
- **qa-smoke-tester** (0 changes): 76 checks green, idempotency + IDOR + status machine all verified end-to-end.
- **security-reviewer** (3 fixed — no IDOR/CSRF/XSS/injection/mass-assignment found): added extension+size validation
  to the 3 new FileFields via a shared `_validate_upload`; gated `preboardingitem_delete` (drops a compliance item)
  and the BGV lifecycle `initiate`/`mark_status`/`complete` (records a hire-relevant verdict) behind
  `@tenant_admin_required`, with the templates hiding those actions from non-admins. (Findings #4/#5 — free-text
  audit PII + tenant-wide comp visibility — are pre-existing app-wide patterns, no change this pass.)
- **test-writer**: 251-test suite, all green; the reject/resubmit regression is explicitly covered; no product bugs.

**Deferred (carried forward — see the skill's 3.8 deferrals):** live e-sign / background-check vendor APIs,
adverse-action/dispute compliance flow, parallel + configurable-rule-engine approval routing, notification
field-picker, companion-document bundling, acceptance-rate analytics dashboard, template-usage scoping, scheduled
pre-boarding dispatch, and the pre-boarding→3.3 onboarding auto-handoff (a TODO at the `offer_accept` trigger).

**Next sub-module:** 3.11 Time Tracking (the lowest-numbered HRM sub-module without a `LIVE_LINKS` entry — 3.1–3.10
and 3.12 are now wired; coordinate timesheets with `accounting.Project`).
