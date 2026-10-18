# Build Contract — Sub-module 8.9: Sales Enablement (Module 8: Sales Management System, `apps/sales`)

> Phase 3 Step 1. `BASE = 759f25acb920ace14996183aa6b553b80a61cdd1`.
> Research: `.claude/tasks/research-sales-8.9.md`. Plan: `.claude/tasks/todo.md`.
> Next migration: **`0017_salesenablement`** (claimed).

---

## 0. Ownership Rulings (L29 / L36 / L37)

8.9 adds 4 tenant-scoped models and 5 derived read-only boards. It declares **zero duplicate competitor, call log, activity, document or pipeline master**.

| Entity / Domain | Read-Only Master Owner | Where It Lives | 8.9's Relationship |
|---|---|---|---|
| **Competitor Profiles** | **Sales 8.2** | `apps/sales/models/CompetitiveIntelligence/CompetitiveIntelligence.py` | `CompetitorProfile` (`CMP-`) is linked by FK (`EnablementContent.competitor`). Win/loss stats aggregate 8.2's `OpportunityOutcome` and `WinLossReason`. **Zero duplicate competitor profile model.** |
| **Call & Communication Logs** | **CRM 1.5** | `apps/crm/models/ActivityManagement/CommunicationLogs.py` | `crm.CommunicationLog` (`COM-`) is the mandatory interaction anchor (`CoachingScorecard.communication_log`). **Zero duplicate call log / meeting model.** |
| **Sales Activities** | **Sales 8.8** | `apps/sales/models/SalesActivityTaskManagement/ActivityLogs.py` | `sales.ActivityLog` (`SAL-`) is an optional attribution link (`CoachingScorecard.activity_log`). |
| **File Binaries** | **core 0** | `apps/core/models/Document.py` | `core.Document` is the binary storage engine (`EnablementContent.document`). 8.9 holds catalog metadata, tags, and cloud URLs. |
| **Pipelines & Stages** | **Sales 8.2** | `apps/sales/models/OpportunityPipeline/Pipelines.py` | `sales.Pipeline` & `sales.PipelineStage` are FKs on `SalesPlaybook` and `EnablementContent`. |
| **Users / Reps / Coaches** | **accounts 0** | `apps/accounts/models/User.py` | `settings.AUTH_USER_MODEL` (`accounts.User`) for reps, coachees, coaches, and certifiers. |
| **LMS Bridge** | **HRM 3.22** | `apps/hrm/models/TrainingManagement/Trainingcourse.py` | `hrm.TrainingCourse` (`TRC-`) is an optional nullable bridge FK (`SalesCertification.hrm_course`). |

---

## 1. Models — Every Field, Every Choice, Every Constraint

All models reside in `apps/sales/models/SalesEnablement/`.
Base: `apps.sales.models._base.TenantNumbered` (includes `tenant` FK `core.Tenant`, `number = CharField(max_length=20, editable=False)`, `created_at`, `updated_at`).

### 1.1 `EnablementContent` (`EnablementContents.py`) — `NUMBER_PREFIX = "ECN"`

```python
CONTENT_TYPE_CHOICES = [
    ("battle_card", "Battle Card"),
    ("pitch_deck", "Pitch Deck"),
    ("case_study", "Case Study"),
    ("product_sheet", "Product One-Pager"),
    ("whitepaper", "Whitepaper / Research"),
    ("demo_script", "Demo Script / Flow"),
    ("email_template", "Outreach Email Template"),
    ("proposal_template", "Proposal Snippet"),
]

TARGET_STAGE_CHOICES = [
    ("all", "All Stages"),
    ("prospecting", "Prospecting / Discovery"),
    ("qualification", "Qualification"),
    ("demo_eval", "Demo & Solution Evaluation"),
    ("proposal_neg", "Proposal & Negotiation"),
    ("closing", "Closing"),
    ("post_sale", "Expansion & Retention"),
]

TARGET_PERSONA_CHOICES = [
    ("all", "All Personas"),
    ("c_level", "Executive / C-Suite"),
    ("vp_director", "VP / Director"),
    ("manager", "Functional Manager"),
    ("technical_buyer", "IT & Technical Buyer"),
    ("end_user", "End-User Specialist"),
    ("procurement", "Procurement / Legal"),
]
```

| Field | Type | Attributes & Clean Guards |
|---|---|---|
| `title` | `CharField(200)` | Required, indexed |
| `description` | `TextField(blank=True)` | Summary / usage guidance |
| `content_type` | `CharField(30, choices=CONTENT_TYPE_CHOICES, default="battle_card")` | Indexed |
| `document` | `ForeignKey("core.Document", SET_NULL, null=True, blank=True, related_name="sales_enablement_contents")` | Optional file asset |
| `external_url` | `URLField(max_length=500, blank=True)` | Optional cloud asset (Google Slides, Notion, Canva, Loom, etc.) |
| `competitor` | `ForeignKey("sales.CompetitorProfile", SET_NULL, null=True, blank=True, related_name="enablement_contents")` | Links battlecard to 8.2 competitor |
| `target_stage` | `CharField(30, choices=TARGET_STAGE_CHOICES, default="all")` | Sales funnel stage focus |
| `target_persona` | `CharField(30, choices=TARGET_PERSONA_CHOICES, default="all")` | Audience focus |
| `pipeline_stage` | `ForeignKey("sales.PipelineStage", SET_NULL, null=True, blank=True, related_name="enablement_contents")` | Optional granular 8.2 pipeline stage |
| `author` | `ForeignKey(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, related_name="authored_enablement_contents")` | Rep / Enablement specialist |
| `tags` | `CharField(255, blank=True)` | Comma-delimited search keywords |
| `version` | `CharField(20, default="1.0")` | Collateral version |
| `is_client_facing` | `BooleanField(default=False)` | True = external asset; False = internal battlecard/script |
| `is_active` | `BooleanField(default=True)` | Soft toggle |
| `expires_on` | `DateField(null=True, blank=True)` | Expiration date for obsolete collateral |
| `view_count` | `PositiveIntegerField(default=0, editable=False)` | Frozen counter (L22) |
| `share_count` | `PositiveIntegerField(default=0, editable=False)` | Frozen counter (L22) |

- `Meta.ordering = ["-updated_at", "title"]`
- `Meta.constraints`: `UniqueConstraint(fields=["tenant", "number"], name="sales_ecn_tenant_number_uniq")`
- `Meta.indexes`: `Index(fields=["tenant", "content_type", "is_active"], name="sales_ecn_type_active_idx")`
- `clean()`:
  - **G1**: At least one of `document` or `external_url` must be provided (or non-empty description for pure-text scripts).
  - **G2**: If `competitor` is selected, verify it belongs to the same tenant (`competitor.tenant_id == self.tenant_id`).
  - **G3**: If `document` is selected, verify it belongs to the same tenant (`document.tenant_id == self.tenant_id`).
  - **G4**: If `pipeline_stage` is selected, verify it belongs to the same tenant (`pipeline_stage.tenant_id == self.tenant_id`).

---

### 1.2 `SalesPlaybook` (`SalesPlaybooks.py`) — `NUMBER_PREFIX = "SPB"`

```python
SELLING_MOTION_CHOICES = [
    ("new_business", "New Business (Land)"),
    ("expansion", "Account Expansion (Upsell/Cross-sell)"),
    ("renewal", "Contract Renewal"),
    ("competitive_displacement", "Competitive Takeout / Displacement"),
    ("partner_co_selling", "Partner Co-Selling"),
]

PLAYBOOK_STATUS_CHOICES = [
    ("draft", "Draft"),
    ("published", "Published"),
    ("under_review", "Under Review"),
    ("archived", "Archived"),
]
```

| Field | Type | Attributes & Clean Guards |
|---|---|---|
| `name` | `CharField(150)` | Required playbook title |
| `summary` | `TextField(blank=True)` | Executive summary of motion |
| `motion_type` | `CharField(30, choices=SELLING_MOTION_CHOICES, default="new_business")` | Selling motion |
| `pipeline` | `ForeignKey("sales.Pipeline", SET_NULL, null=True, blank=True, related_name="sales_playbooks")` | Associated 8.2 opportunity pipeline |
| `status` | `CharField(20, choices=PLAYBOOK_STATUS_CHOICES, default="draft")` | Lifecycle state |
| `target_audience` | `CharField(200, blank=True)` | Ideal customer profile / ICP trigger |
| `discovery_questions` | `TextField(blank=True)` | Key discovery / diagnostic questions (bullet/newline-separated) |
| `talk_tracks` | `TextField(blank=True)` | Recommended talk tracks, pitch positioning |
| `objection_scripts` | `TextField(blank=True)` | Objection handling rebuttals & response scripts |
| `dos_and_donts` | `TextField(blank=True)` | Best practices: what works and what to avoid |
| `exit_criteria` | `TextField(blank=True)` | Stage completion / exit verification criteria |
| `owner` | `ForeignKey(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, related_name="owned_sales_playbooks")` | Enablement lead |
| `version` | `CharField(20, default="1.0")` | Playbook revision |
| `is_active` | `BooleanField(default=True)` | Active toggle |

- `Meta.ordering = ["name", "-updated_at"]`
- `Meta.constraints`: `UniqueConstraint(fields=["tenant", "number"], name="sales_spb_tenant_number_uniq")`
- `Meta.indexes`: `Index(fields=["tenant", "motion_type", "status"], name="sales_spb_motion_stat_idx")`
- `clean()`:
  - **G5**: If `pipeline` is set, verify `pipeline.tenant_id == self.tenant_id`.

---

### 1.3 `SalesCertification` (`SalesCertifications.py`) — `NUMBER_PREFIX = "SCTF"`

```python
CERTIFICATION_CATEGORY_CHOICES = [
    ("onboarding", "New Rep Onboarding Curriculum"),
    ("product_certification", "Product / Solution Certification"),
    ("methodology", "Sales Methodology (MEDDPICC, Challenger, SPICED)"),
    ("compliance", "Security, Privacy & Regulatory Compliance"),
    ("pitch_accreditation", "Pitch & Demo Accreditation"),
]

CERTIFICATION_STATUS_CHOICES = [
    ("enrolled", "Enrolled / In Progress"),
    ("completed", "Completed / Passed"),
    ("failed", "Failed / Requires Retake"),
    ("expired", "Expired"),
]
```

| Field | Type | Attributes & Clean Guards |
|---|---|---|
| `curriculum_name` | `CharField(150)` | Curriculum or certification course title |
| `category` | `CharField(30, choices=CERTIFICATION_CATEGORY_CHOICES, default="product_certification")` | Certification domain |
| `rep` | `ForeignKey(settings.AUTH_USER_MODEL, CASCADE, related_name="sales_certifications")` | Rep evaluated |
| `status` | `CharField(20, choices=CERTIFICATION_STATUS_CHOICES, default="enrolled")` | Current certification state |
| `score_percent` | `DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)` | 0.00 to 100.00% score |
| `passing_score_percent` | `DecimalField(max_digits=5, decimal_places=2, default=80.00)` | Threshold to pass |
| `certified_by` | `ForeignKey(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, related_name="evaluated_sales_certifications")` | Manager or enablement certifier |
| `certified_at` | `DateField(null=True, blank=True)` | Accreditation date |
| `expires_at` | `DateField(null=True, blank=True)` | Expiration date for recertification |
| `accreditation_notes` | `TextField(blank=True)` | Evaluator notes, feedback, or verification link |
| `hrm_course` | `ForeignKey("hrm.TrainingCourse", SET_NULL, null=True, blank=True, related_name="sales_certifications")` | Optional HRM 3.22 course bridge |

- `Meta.ordering = ["-certified_at", "-created_at"]`
- `Meta.constraints`: `UniqueConstraint(fields=["tenant", "number"], name="sales_sctf_tenant_number_uniq")`
- `Meta.indexes`: `Index(fields=["tenant", "category", "status"], name="sales_sctf_cat_stat_idx")`
- `clean()`:
  - **G6**: `score_percent` when present must be between 0.00 and 100.00.
  - **G7**: `passing_score_percent` must be between 0.00 and 100.00.
  - **G8**: If `status == 'completed'`, `certified_at` must not be null (defaults to today if unset). If `score_percent` is provided and `< passing_score_percent`, raise ValidationError ("Score is below passing threshold; cannot be marked Completed").
  - **G9**: If `expires_at` is set, `expires_at` must be >= `certified_at`.

---

### 1.4 `CoachingScorecard` (`CoachingScorecards.py`) — `NUMBER_PREFIX = "CSC"`

```python
SCORECARD_STATUS_CHOICES = [
    ("draft", "Draft Evaluation"),
    ("shared", "Shared with Rep"),
    ("acknowledged", "Acknowledged by Rep"),
]

CALL_SENTIMENT_CHOICES = [
    ("positive", "Positive / Enthusiastic"),
    ("neutral", "Neutral / Professional"),
    ("skeptical", "Skeptical / Challenging"),
    ("negative", "Negative / Frustrated"),
]
```

| Field | Type | Attributes & Clean Guards |
|---|---|---|
| `communication_log` | `ForeignKey("crm.CommunicationLog", CASCADE, related_name="coaching_scorecards")` | Interaction anchor (calls, meetings, emails) |
| `activity_log` | `ForeignKey("sales.ActivityLog", SET_NULL, null=True, blank=True, related_name="coaching_scorecards")` | Optional Sales 8.8 activity link |
| `coach` | `ForeignKey(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, related_name="given_coaching_scorecards")` | Evaluating manager / coach |
| `coachee` | `ForeignKey(settings.AUTH_USER_MODEL, CASCADE, related_name="received_coaching_scorecards")` | Rep evaluated |
| `recording_url` | `URLField(max_length=500, blank=True)` | Call recording / meeting video link |
| `discovery_score` | `PositiveSmallIntegerField(default=3, validators=[MinValueValidator(1), MaxValueValidator(5)])` | Discovery & Pain Uncovering (1-5) |
| `value_prop_score` | `PositiveSmallIntegerField(default=3, validators=[MinValueValidator(1), MaxValueValidator(5)])` | Value Proposition & Solution Fit (1-5) |
| `objection_handling_score` | `PositiveSmallIntegerField(default=3, validators=[MinValueValidator(1), MaxValueValidator(5)])` | Objection Handling & Confidence (1-5) |
| `next_steps_score` | `PositiveSmallIntegerField(default=3, validators=[MinValueValidator(1), MaxValueValidator(5)])` | Next Steps & Deal Momentum (1-5) |
| `overall_score` | `PositiveSmallIntegerField(default=60, editable=False)` | Composite score: `((sum of 4 rubrics) / 20) * 100` (computed in `save()`) |
| `talk_listen_ratio_percent` | `PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(100)])` | Conversation Intelligence: Rep talk time % |
| `call_sentiment` | `CharField(20, choices=CALL_SENTIMENT_CHOICES, default="neutral")` | AI / coach evaluated client sentiment |
| `transcript_summary` | `TextField(blank=True)` | Call highlights, key customer quotes, discussed topics |
| `key_strengths` | `TextField(blank=True)` | What the rep did exceptionally well |
| `areas_for_improvement` | `TextField(blank=True)` | Actionable coaching critique |
| `action_items` | `TextField(blank=True)` | Agreed follow-up actions and skill drills |
| `review_status` | `CharField(20, choices=SCORECARD_STATUS_CHOICES, default="draft")` | Coaching workflow |
| `evaluated_on` | `DateField(default=timezone.now)` | Evaluation date |

- `Meta.ordering = ["-evaluated_on", "-created_at"]`
- `Meta.constraints`: `UniqueConstraint(fields=["tenant", "number"], name="sales_csc_tenant_number_uniq")`
- `Meta.indexes`: `Index(fields=["tenant", "coachee", "review_status"], name="sales_csc_coachee_stat_idx")`
- `clean()`:
  - **G10**: Verify `communication_log.tenant_id == self.tenant_id`.
  - **G11**: If `activity_log` is provided, verify `activity_log.tenant_id == self.tenant_id`.
  - **G12**: Each rubric score must be between 1 and 5.
- `save()`: Automatically computes `overall_score = int(round(((self.discovery_score + self.value_prop_score + self.objection_handling_score + self.next_steps_score) / 20.0) * 100))`.

---

## 2. Forms — Exclusions & Form Fields

All forms live in `apps/sales/forms/SalesEnablement/`:
1. `EnablementContentForm`:
   - `Meta.model = EnablementContent`
   - `Meta.fields = ["title", "description", "content_type", "document", "external_url", "competitor", "target_stage", "target_persona", "pipeline_stage", "author", "tags", "version", "is_client_facing", "is_active", "expires_on"]`
   - Excludes: `tenant`, `number`, `view_count`, `share_count`, `created_at`, `updated_at`.
2. `SalesPlaybookForm`:
   - `Meta.model = SalesPlaybook`
   - `Meta.fields = ["name", "summary", "motion_type", "pipeline", "status", "target_audience", "discovery_questions", "talk_tracks", "objection_scripts", "dos_and_donts", "exit_criteria", "owner", "version", "is_active"]`
   - Excludes: `tenant`, `number`, `created_at`, `updated_at`.
3. `SalesCertificationForm`:
   - `Meta.model = SalesCertification`
   - `Meta.fields = ["curriculum_name", "category", "rep", "status", "score_percent", "passing_score_percent", "certified_by", "certified_at", "expires_at", "accreditation_notes", "hrm_course"]`
   - Excludes: `tenant`, `number`, `created_at`, `updated_at`.
4. `CoachingScorecardForm`:
   - `Meta.model = CoachingScorecard`
   - `Meta.fields = ["communication_log", "activity_log", "coach", "coachee", "recording_url", "discovery_score", "value_prop_score", "objection_handling_score", "next_steps_score", "talk_listen_ratio_percent", "call_sentiment", "transcript_summary", "key_strengths", "areas_for_improvement", "action_items", "review_status", "evaluated_on"]`
   - Excludes: `tenant`, `number`, `overall_score`, `created_at`, `updated_at`.

---

## 3. URLs — Names & Routes

In `apps/sales/urls/SalesEnablement/`:
- `EnablementContents.py`:
  - `path("enablement/content/", enablement_content_list, name="enablement_content_list")`
  - `path("enablement/content/new/", enablement_content_create, name="enablement_content_create")`
  - `path("enablement/content/<int:pk>/", enablement_content_detail, name="enablement_content_detail")`
  - `path("enablement/content/<int:pk>/edit/", enablement_content_edit, name="enablement_content_edit")`
  - `path("enablement/content/<int:pk>/delete/", enablement_content_delete, name="enablement_content_delete")`
- `SalesPlaybooks.py`:
  - `path("enablement/playbooks/", sales_playbook_list, name="sales_playbook_list")`
  - `path("enablement/playbooks/new/", sales_playbook_create, name="sales_playbook_create")`
  - `path("enablement/playbooks/<int:pk>/", sales_playbook_detail, name="sales_playbook_detail")`
  - `path("enablement/playbooks/<int:pk>/edit/", sales_playbook_edit, name="sales_playbook_edit")`
  - `path("enablement/playbooks/<int:pk>/delete/", sales_playbook_delete, name="sales_playbook_delete")`
- `SalesCertifications.py`:
  - `path("enablement/certifications/", sales_certification_list, name="sales_certification_list")`
  - `path("enablement/certifications/new/", sales_certification_create, name="sales_certification_create")`
  - `path("enablement/certifications/<int:pk>/", sales_certification_detail, name="sales_certification_detail")`
  - `path("enablement/certifications/<int:pk>/edit/", sales_certification_edit, name="sales_certification_edit")`
  - `path("enablement/certifications/<int:pk>/delete/", sales_certification_delete, name="sales_certification_delete")`
- `CoachingScorecards.py`:
  - `path("enablement/coaching/", coaching_scorecard_list, name="coaching_scorecard_list")`
  - `path("enablement/coaching/new/", coaching_scorecard_create, name="coaching_scorecard_create")`
  - `path("enablement/coaching/<int:pk>/", coaching_scorecard_detail, name="coaching_scorecard_detail")`
  - `path("enablement/coaching/<int:pk>/edit/", coaching_scorecard_edit, name="coaching_scorecard_edit")`
  - `path("enablement/coaching/<int:pk>/delete/", coaching_scorecard_delete, name="coaching_scorecard_delete")`
- `EnablementBoards.py` (5 NavERP.md boards):
  - `path("enablement/hub/", sales_enablement_content_hub, name="enablement_content_hub")`
  - `path("enablement/playbooks/board/", sales_playbook_board, name="sales_playbook_board")`
  - `path("enablement/readiness/", sales_readiness_board, name="sales_readiness_board")`
  - `path("enablement/coaching/workbench/", sales_coaching_workbench, name="sales_coaching_workbench")`
  - `path("enablement/competitive-intelligence/", sales_competitive_intelligence_library, name="sales_competitive_intelligence_library")`

---

## 4. View Context Variables Pinned (L7 / L8)

### 4.1 List Views
- `enablement_content_list`: `contents` (Page object), `content_type_choices`, `stage_choices`, `persona_choices`, `competitors`, `q`, `content_type`, `target_stage`, `competitor_id`.
- `sales_playbook_list`: `playbooks` (Page object), `motion_type_choices`, `status_choices`, `pipelines`, `q`, `motion_type`, `status`, `pipeline_id`.
- `sales_certification_list`: `certifications` (Page object), `category_choices`, `status_choices`, `reps`, `q`, `category`, `status`, `rep_id`.
- `coaching_scorecard_list`: `scorecards` (Page object), `review_status_choices`, `coaches`, `coachees`, `q`, `review_status`, `coach_id`, `coachee_id`.

### 4.2 Detail Views
- `enablement_content_detail`: `content`
- `sales_playbook_detail`: `playbook`
- `sales_certification_detail`: `certification`
- `coaching_scorecard_detail`: `scorecard`

### 4.3 Form Views (Create / Edit)
- `enablement_content_form`: `form`, `content` (None on create), `is_edit`
- `sales_playbook_form`: `form`, `playbook` (None on create), `is_edit`
- `sales_certification_form`: `form`, `certification` (None on create), `is_edit`
- `coaching_scorecard_form`: `form`, `scorecard` (None on create), `is_edit`

### 4.4 Five Derived Boards Context
- `sales_enablement_content_hub`: `recent_contents`, `popular_contents`, `battlecards`, `decks`, `sheets`, `total_contents`, `total_battlecards`.
- `sales_playbook_board`: `playbooks_by_motion`, `pipelines`, `total_published`.
- `sales_readiness_board`: `certifications_summary`, `rep_readiness_matrix`, `completion_rate`, `expiring_soon_count`.
- `sales_coaching_workbench`: `recent_scorecards`, `avg_overall_score`, `talk_ratio_avg`, `unreviewed_logs`, `strengths_distribution`.
- `sales_competitive_intelligence_library`: `competitors_with_battlecards`, `total_competitors`, `win_loss_outcomes`.

---

## 5. Templates — Exact Folder Structure (Lowercase on Disk)

```
templates/sales/salesenablement/
├── enablementcontent/
│   ├── list.html
│   ├── detail.html
│   └── form.html
├── salesplaybook/
│   ├── list.html
│   ├── detail.html
│   └── form.html
├── salescertification/
│   ├── list.html
│   ├── detail.html
│   └── form.html
├── coachingscorecard/
│   ├── list.html
│   ├── detail.html
│   └── form.html
└── boards/
    ├── content_hub.html
    ├── playbook_board.html
    ├── readiness_board.html
    ├── coaching_workbench.html
    └── competitive_intelligence_library.html
```

Design-system classes:
- Color-named badges ONLY: `.badge-green`, `.badge-amber`, `.badge-red`, `.badge-info`, `.badge-muted`, `.badge-slate` (L33).
- Tables with `.table-wrap .table .table-actions`.
- Filters with `{% if request.GET.field == value %}selected{% endif %}`. For FK ids: `cat.pk|stringformat:"d"`.
- Pagination with `has_previous` / `has_next` guards (L9).
- Delete is POST-only with CSRF and confirm prompt.

---

## 6. Wire-Up: `LIVE_LINKS["8.9"]`

In `apps/core/navigation.py`:
```python
    "8.9": {
        "Content Repository & Search": "sales:enablement_content_hub",
        "Sales Playbooks & Guidance": "sales:sales_playbook_board",
        "Training & Certification Tracking": "sales:sales_readiness_board",
        "Coaching & Call Recording": "sales:sales_coaching_workbench",
        "Competitive Intelligence Library": "sales:sales_competitive_intelligence_library",
        # Extra leaves
        "Content Assets": "sales:enablement_content_list",
        "Sales Playbooks": "sales:sales_playbook_list",
        "Sales Certifications": "sales:sales_certification_list",
        "Coaching Scorecards": "sales:coaching_scorecard_list",
    },
```

---

## 7. Seeder Plan (`apps/sales/management/commands/seed_sales.py`)

Dedicated helper `_seed_sales_enablement(tenant, owner)`:
- Guarded per model: `if EnablementContent.objects.filter(tenant=tenant).exists(): return`
- ACME & GLOBEX tenants:
  - 4 `EnablementContent` rows (Battlecard against ACME's existing 8.2 competitor, Enterprise Pitch Deck, SaaS Case Study, Solution One-Pager).
  - 2 `SalesPlaybook` rows (New Business Outbound Motion, Competitive Takeout Motion).
  - 3 `SalesCertification` rows (Product Suite Certification, MEDDPICC Methodology, New Hire Sales Onboarding).
  - 3 `CoachingScorecard` rows (anchored to ACME's existing `crm.CommunicationLog` rows).
