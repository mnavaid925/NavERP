# Build Contract — Sub-module 8.11: Customer Success & Account Management (Module 8: Sales Management System, `apps/sales`)

> Phase 3 Step 1. `BASE = db0cfe4b34538b933a169b722181f11c614f4a9c`.
> Research: `.claude/tasks/research-sales-8.11.md`. Plan: `.claude/tasks/todo.md`.
> Next migration: **`0021_customersuccess`** (claimed).

---

## 0. Ownership Rulings (L29 / L36 / L37)

8.11 adds 4 tenant-scoped models and 5 derived read-only consoles/boards. It declares **zero duplicate customer, deal, order, currency, or project ledger tables**.

| Entity / Domain | Read-Only Master Owner | Where It Lives | 8.11's Relationship |
|---|---|---|---|
| **Customers & Accounts** | **Core Spine** | `apps/core/models/Party.py` | `core.Party` (with role `customer`) is the primary account anchor for health scores, renewals, onboardings, and business reviews. Zero duplicate customer table. |
| **Document Collateral** | **Core Spine** | `apps/core/models/Document.py` | `core.Document` provides shared storage for signed renewal contracts and published case studies. |
| **Expansion Opportunities** | **CRM 1.2** | `apps/crm/models/SalesForceAutomation/Opportunities.py` | `crm.Opportunity` (`OPP-`) receives new expansion opportunities created during contract renewal motions. Zero duplicate deal table. |
| **Sales Orders & Subscriptions** | **SCM 4.5** | `apps/scm/models/OrderManagement/SalesOrders.py` | `scm.SalesOrder` (`SO-`) provides original contract execution records linked to renewals and customer onboarding. |
| **Strategic Account Plans** | **Sales 8.3** | `apps/sales/models/ContactAccountManagement/AccountPlans.py` | `sales.AccountPlan` (`ACPL-`) links strategic account objectives and whitespace assessments to quarterly business reviews. |
| **Currencies & Exchange Rates** | **Accounting 2.2** | `apps/accounting/models/GeneralLedger/Currencies.py` | `accounting.Currency` (global ISO 4217) provides currency denominations for contract ARR and expansion values. |
| **CSMs, Directors & Reviewers** | **accounts 0** | `apps/accounts/models/User.py` | `settings.AUTH_USER_MODEL` (`accounts.User`) represents Customer Success Managers, onboarding leads, executive sponsors, and reviewers. |

---

## 1. Models — Every Field, Every Choice, Every Constraint

All models reside in `apps/sales/models/CustomerSuccess/`.
Base: `apps.sales.models._base.TenantNumbered` (includes `tenant` FK `core.Tenant`, `number = CharField(max_length=20, editable=False)`, `created_at`, `updated_at`).

### 1.1 `CustomerHealthScore` (`CustomerHealthScores.py`) — `NUMBER_PREFIX = "CHS"`

```python
HEALTH_BAND_CHOICES = [
    ("green", "Healthy (75-100)"),
    ("yellow", "Needs Attention (50-74)"),
    ("red", "At Risk (0-49)"),
]

TREND_CHOICES = [
    ("improving", "Improving"),
    ("stable", "Stable"),
    ("declining", "Declining"),
]

RISK_LEVEL_CHOICES = [
    ("low", "Low Risk"),
    ("medium", "Medium Risk"),
    ("high", "High Risk"),
    ("critical", "Critical Risk"),
]
```

| Field | Type | Attributes & Clean Guards |
|---|---|---|
| `account` | `ForeignKey("core.Party", CASCADE, related_name="sales_customer_health_scores")` | Customer account, required |
| `evaluation_date` | `DateField(default=timezone.localdate)` | Date score evaluated |
| `overall_score` | `PositiveSmallIntegerField(validators=[MinValueValidator(0), MaxValueValidator(100)])` | 0-100 composite score |
| `health_band` | `CharField(15, choices=HEALTH_BAND_CHOICES, default="green")` | Traffic-light band, indexed |
| `previous_score` | `PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(100)])` | Previous score for delta |
| `score_trend` | `CharField(15, choices=TREND_CHOICES, default="stable")` | Directional trend |
| `product_usage_score` | `PositiveSmallIntegerField(default=75, validators=[MinValueValidator(0), MaxValueValidator(100)])` | Telemetry/adoption factor |
| `support_ticket_score` | `PositiveSmallIntegerField(default=75, validators=[MinValueValidator(0), MaxValueValidator(100)])` | Support ticket health factor |
| `nps_sentiment_score` | `PositiveSmallIntegerField(default=75, validators=[MinValueValidator(0), MaxValueValidator(100)])` | NPS survey factor |
| `relationship_score` | `PositiveSmallIntegerField(default=75, validators=[MinValueValidator(0), MaxValueValidator(100)])` | Stakeholder engagement factor |
| `renewal_risk_score` | `PositiveSmallIntegerField(default=75, validators=[MinValueValidator(0), MaxValueValidator(100)])` | Commercial renewal risk factor |
| `risk_level` | `CharField(15, choices=RISK_LEVEL_CHOICES, default="low")` | Churn risk level, indexed |
| `risk_reasons` | `JSONField(default=list, blank=True)` | List of risk codes e.g. `["low_adoption", "unresolved_tickets"]` |
| `active_alert_message` | `CharField(255, blank=True)` | Early warning alert text |
| `is_churn_risk` | `BooleanField(default=False)` | High-priority churn flag, indexed |
| `license_utilization_pct` | `DecimalField(5, 2, default=Decimal("80.00"), validators=[MinValueValidator(0), MaxValueValidator(100)])` | Seat utilization % |
| `open_support_tickets` | `PositiveIntegerField(default=0)` | Open ticket count |
| `latest_nps` | `IntegerField(null=True, blank=True, validators=[MinValueValidator(-100), MaxValueValidator(100)])` | -100 to +100 NPS |
| `last_activity_date` | `DateField(null=True, blank=True)` | Last contact/login date |
| `notes` | `TextField(blank=True)` | CSM evaluation notes |

- `Meta.ordering = ["-evaluation_date", "-overall_score"]`
- `Meta.constraints`: `UniqueConstraint(fields=["tenant", "number"], name="sales_chs_tenant_number_uniq")`
- `Meta.indexes`:
  * `Index(fields=["tenant", "account", "evaluation_date"], name="sales_chs_acct_date_idx")` (23 chars <= 30)
  * `Index(fields=["tenant", "health_band"], name="sales_chs_band_idx")` (18 chars <= 30)
  * `Index(fields=["tenant", "is_churn_risk"], name="sales_chs_churn_idx")` (19 chars <= 30)
- `clean()`:
  - **G1**: Verify `account` belongs to the same tenant (`self.account.tenant_id == self.tenant_id`).
  - **G2**: Health band consistency: if `overall_score >= 75` and band is `red`, raise ValidationError; if `overall_score < 50` and band is `green`, raise ValidationError.
  - **G3**: If `is_churn_risk == True`, `risk_level` must be `"medium"`, `"high"`, or `"critical"`, not `"low"`.

---

### 1.2 `CustomerRenewal` (`CustomerRenewals.py`) — `NUMBER_PREFIX = "CRN"`

```python
STAGE_CHOICES = [
    ("upcoming", "Upcoming (90+ Days)"),
    ("engagement", "Active Engagement"),
    ("proposal_sent", "Renewal Proposal Sent"),
    ("negotiation", "Contract Negotiation"),
    ("renewed", "Renewed (Closed-Won)"),
    ("expanded", "Renewed & Expanded"),
    ("churned", "Churned (Closed-Lost)"),
    ("contracted_down", "Contracted Down"),
]

CHURN_RISK_CHOICES = [
    ("low", "Low"),
    ("medium", "Medium"),
    ("high", "High"),
    ("critical", "Critical"),
]
```

| Field | Type | Attributes & Clean Guards |
|---|---|---|
| `account` | `ForeignKey("core.Party", CASCADE, related_name="sales_customer_renewals")` | Customer account, required |
| `owner` | `ForeignKey(settings.AUTH_USER_MODEL, PROTECT, related_name="sales_owned_renewals")` | Renewal owner / CSM |
| `original_order` | `ForeignKey("scm.SalesOrder", SET_NULL, null=True, blank=True, related_name="sales_renewal_records")` | Original order anchor |
| `renewal_name` | `CharField(160)` | Descriptive renewal title |
| `contract_reference` | `CharField(80, blank=True)` | External contract/MSA ID |
| `current_arr` | `DecimalField(14, 2, default=Decimal("0.00"), validators=[MinValueValidator(Decimal("0.00"))])` | Baseline ARR at risk |
| `projected_renewal_arr` | `DecimalField(14, 2, default=Decimal("0.00"), validators=[MinValueValidator(Decimal("0.00"))])` | Forecasted renewal ARR |
| `expansion_amount` | `DecimalField(14, 2, default=Decimal("0.00"), validators=[MinValueValidator(Decimal("0.00"))])` | Upsell/cross-sell headroom |
| `currency` | `ForeignKey("accounting.Currency", PROTECT, related_name="sales_customer_renewals")` | Contract currency |
| `renewal_date` | `DateField()` | Contract expiration / renewal date |
| `target_close_date` | `DateField()` | Target signature date |
| `stage` | `CharField(25, choices=STAGE_CHOICES, default="upcoming")` | Pipeline stage, indexed |
| `churn_risk_flag` | `CharField(15, choices=CHURN_RISK_CHOICES, default="low")` | Churn risk rating, indexed |
| `renewal_probability_pct` | `PositiveSmallIntegerField(default=80, validators=[MinValueValidator(0), MaxValueValidator(100)])` | Win probability % |
| `auto_renewal` | `BooleanField(default=False)` | Evergreen auto-renewal clause |
| `notice_period_days` | `PositiveIntegerField(default=60)` | Non-renewal notice window |
| `expansion_opportunity` | `ForeignKey("crm.Opportunity", SET_NULL, null=True, blank=True, related_name="sales_renewal_expansions")` | Linked CRM deal |
| `notes` | `TextField(blank=True)` | Commercial negotiation notes |

- `Meta.ordering = ["renewal_date", "-current_arr"]`
- `Meta.constraints`: `UniqueConstraint(fields=["tenant", "number"], name="sales_crn_tenant_number_uniq")`
- `Meta.indexes`:
  * `Index(fields=["tenant", "account", "stage"], name="sales_crn_acct_stage_idx")` (24 chars <= 30)
  * `Index(fields=["tenant", "renewal_date"], name="sales_crn_date_idx")` (18 chars <= 30)
  * `Index(fields=["tenant", "churn_risk_flag"], name="sales_crn_risk_idx")` (18 chars <= 30)
- `clean()`:
  - **G1**: Verify `account` belongs to the same tenant (`self.account.tenant_id == self.tenant_id`).
  - **G2**: If `original_order` is set, verify same tenant.
  - **G3**: If `expansion_opportunity` is set, verify same tenant.
  - **G4**: If `stage == "expanded"`, `expansion_amount` must be `> Decimal("0.00")`.

---

### 1.3 `CustomerOnboarding` (`CustomerOnboardings.py`) — `NUMBER_PREFIX = "COB"`

```python
PLAYBOOK_CHOICES = [
    ("enterprise_high_touch", "Enterprise High-Touch (90 Days)"),
    ("midmarket_standard", "Mid-Market Standard (45 Days)"),
    ("smb_accelerated", "SMB Accelerated (21 Days)"),
    ("tech_touch_automated", "Tech-Touch Automated"),
]

STAGE_CHOICES = [
    ("kickoff", "Kickoff & Alignment"),
    ("architecture_design", "Architecture & Solution Design"),
    ("configuration", "System Configuration"),
    ("data_migration", "Data Migration"),
    ("training", "User & Admin Training"),
    ("uat_testing", "User Acceptance Testing"),
    ("go_live", "Production Go-Live"),
    ("completed", "Completed & Handed to CS"),
    ("stalled", "Stalled / On Hold"),
]

STATUS_CHOICES = [
    ("not_started", "Not Started"),
    ("in_progress", "In Progress"),
    ("on_track", "On Track"),
    ("at_risk", "At Risk"),
    ("blocked", "Blocked"),
    ("completed", "Completed"),
]
```

| Field | Type | Attributes & Clean Guards |
|---|---|---|
| `account` | `ForeignKey("core.Party", CASCADE, related_name="sales_customer_onboardings")` | Customer account, required |
| `lead_csm` | `ForeignKey(settings.AUTH_USER_MODEL, PROTECT, related_name="sales_managed_onboardings")` | Assigned CSM / PM |
| `sales_order` | `ForeignKey("scm.SalesOrder", SET_NULL, null=True, blank=True, related_name="sales_onboardings")` | Order triggering onboarding |
| `title` | `CharField(160)` | Implementation project title |
| `playbook_template` | `CharField(30, choices=PLAYBOOK_CHOICES, default="midmarket_standard")` | Playbook framework |
| `stage` | `CharField(25, choices=STAGE_CHOICES, default="kickoff")` | Onboarding lifecycle stage |
| `status` | `CharField(15, choices=STATUS_CHOICES, default="in_progress")` | Project health status |
| `kickoff_date` | `DateField(default=timezone.localdate)` | Project start date |
| `target_go_live_date` | `DateField()` | Scheduled go-live date |
| `actual_go_live_date` | `DateField(null=True, blank=True)` | Actual production launch date |
| `time_to_value_days` | `PositiveIntegerField(null=True, blank=True)` | Elapsed days to value |
| `progress_pct` | `PositiveSmallIntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])` | Completion % |
| `executive_sponsor_name` | `CharField(120, blank=True)` | Client sponsor contact name |
| `executive_sponsor_email` | `EmailField(blank=True)` | Client sponsor email |
| `milestones_config` | `JSONField(default=list, blank=True)` | Checkable milestone objects |
| `blockers` | `TextField(blank=True)` | Current impediments |
| `success_criteria` | `TextField(blank=True)` | Client signoff criteria |

- `Meta.ordering = ["target_go_live_date", "-kickoff_date"]`
- `Meta.constraints`: `UniqueConstraint(fields=["tenant", "number"], name="sales_cob_tenant_number_uniq")`
- `Meta.indexes`:
  * `Index(fields=["tenant", "account", "status"], name="sales_cob_acct_stat_idx")` (23 chars <= 30)
  * `Index(fields=["tenant", "stage"], name="sales_cob_stage_idx")` (19 chars <= 30)
  * `Index(fields=["tenant", "target_go_live_date"], name="sales_cob_date_idx")` (18 chars <= 30)
- `clean()`:
  - **G1**: Verify `account` belongs to the same tenant (`self.account.tenant_id == self.tenant_id`).
  - **G2**: If `sales_order` is set, verify same tenant.
  - **G3**: `target_go_live_date >= kickoff_date`.
  - **G4**: If `actual_go_live_date` is provided, `actual_go_live_date >= kickoff_date`.

---

### 1.4 `CustomerBusinessReview` (`CustomerBusinessReviews.py`) — `NUMBER_PREFIX = "QBR"`

```python
REVIEW_PERIOD_CHOICES = [
    ("q1", "Q1 Review"),
    ("q2", "Q2 Review"),
    ("q3", "Q3 Review"),
    ("q4", "Q4 Review"),
    ("mid_year", "Mid-Year Review"),
    ("annual", "Annual Executive Review"),
]

STATUS_CHOICES = [
    ("scheduled", "Scheduled"),
    ("materials_prepared", "Materials Prepared"),
    ("conducted", "Conducted / Completed"),
    ("follow_up_sent", "Follow-Up Action Items Sent"),
    ("cancelled", "Cancelled"),
]

TEMPLATE_CHOICES = [
    ("executive_value", "Executive Value & ROI Review"),
    ("technical_roadmap", "Technical Architecture & Roadmap"),
    ("renewal_alignment", "Renewal & Partnership Alignment"),
    ("operational_cadence", "Standard Operational Cadence"),
]

CASE_STUDY_CHOICES = [
    ("none", "Not Candidate"),
    ("identified", "Candidate Identified"),
    ("interview_scheduled", "Interview Scheduled"),
    ("drafting", "Drafting Case Study"),
    ("approved", "Client Approved"),
    ("published", "Published"),
]
```

| Field | Type | Attributes & Clean Guards |
|---|---|---|
| `account` | `ForeignKey("core.Party", CASCADE, related_name="sales_customer_business_reviews")` | Customer account, required |
| `lead_csm` | `ForeignKey(settings.AUTH_USER_MODEL, PROTECT, related_name="sales_led_qbrs")` | CSM hosting review |
| `account_plan` | `ForeignKey("sales.AccountPlan", SET_NULL, null=True, blank=True, related_name="sales_qbr_reviews")` | Linked account plan |
| `title` | `CharField(160)` | QBR title / topic |
| `review_period` | `CharField(20, choices=REVIEW_PERIOD_CHOICES, default="q1")` | Cadence period |
| `review_year` | `PositiveIntegerField(default=2026)` | Calendar year |
| `scheduled_date` | `DateField()` | Review meeting date |
| `completed_date` | `DateField(null=True, blank=True)` | Actual completion date |
| `status` | `CharField(20, choices=STATUS_CHOICES, default="scheduled")` | Execution state, indexed |
| `template_type` | `CharField(30, choices=TEMPLATE_CHOICES, default="executive_value")` | Agenda / slide deck template |
| `executive_sponsor_attended` | `BooleanField(default=False)` | Key stakeholder presence |
| `client_attendees` | `TextField(blank=True)` | Client attendees list |
| `internal_attendees` | `TextField(blank=True)` | Internal attendees list |
| `health_score_at_review` | `PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(100)])` | Health score snapshot |
| `key_achievements` | `TextField(blank=True)` | Value delivered / ROI metrics |
| `challenges_and_risks` | `TextField(blank=True)` | Identified issues / blockers |
| `action_items` | `JSONField(default=list, blank=True)` | Post-review tasks: `[{"task": "x", "owner": "y", "due": "z", "status": "open"}]` |
| `is_referenceable` | `BooleanField(default=False)` | Customer reference willing flag |
| `reference_types_permitted` | `JSONField(default=list, blank=True)` | Allowed reference types: `["calls", "site_visits", "quotes", "case_study"]` |
| `case_study_status` | `CharField(25, choices=CASE_STUDY_CHOICES, default="none")` | Case study pipeline stage |
| `testimonial_quote` | `TextField(blank=True)` | Approved testimonial quote |
| `notes` | `TextField(blank=True)` | General meeting notes |

- `Meta.ordering = ["-scheduled_date", "-review_year"]`
- `Meta.constraints`: `UniqueConstraint(fields=["tenant", "number"], name="sales_qbr_tenant_number_uniq")`
- `Meta.indexes`:
  * `Index(fields=["tenant", "account", "status"], name="sales_qbr_acct_stat_idx")` (23 chars <= 30)
  * `Index(fields=["tenant", "scheduled_date"], name="sales_qbr_date_idx")` (18 chars <= 30)
  * `Index(fields=["tenant", "is_referenceable"], name="sales_qbr_ref_idx")` (17 chars <= 30)
- `clean()`:
  - **G1**: Verify `account` belongs to the same tenant (`self.account.tenant_id == self.tenant_id`).
  - **G2**: If `account_plan` is set, verify same tenant.
  - **G3**: If `completed_date` is set, status must not be `"scheduled"`.

---

## 2. Forms — Meta.fields, Exclusions, Widgets & Validation

All forms reside in `apps/sales/forms/CustomerSuccess/`.
Shared base: `from apps.sales.forms._common import *`.

1. **`CustomerHealthScoreForm`** (`CustomerHealthScores.py`):
   - Model: `CustomerHealthScore`
   - Fields: `["account", "evaluation_date", "overall_score", "health_band", "previous_score", "score_trend", "product_usage_score", "support_ticket_score", "nps_sentiment_score", "relationship_score", "renewal_risk_score", "risk_level", "active_alert_message", "is_churn_risk", "license_utilization_pct", "open_support_tickets", "latest_nps", "last_activity_date", "notes"]`
   - Excluded: `tenant`, `number`, `risk_reasons` (managed via risk codes or custom input).
   - Tenant scoping in `__init__`: filter `account` queryset to `Party.objects.filter(tenant=tenant, roles__role="customer").distinct().order_by("name")`.

2. **`CustomerRenewalForm`** (`CustomerRenewals.py`):
   - Model: `CustomerRenewal`
   - Fields: `["account", "owner", "original_order", "renewal_name", "contract_reference", "current_arr", "projected_renewal_arr", "expansion_amount", "currency", "renewal_date", "target_close_date", "stage", "churn_risk_flag", "renewal_probability_pct", "auto_renewal", "notice_period_days", "expansion_opportunity", "notes"]`
   - Excluded: `tenant`, `number`.
   - Tenant scoping in `__init__`:
     * `account`: `Party.objects.filter(tenant=tenant, roles__role="customer").distinct().order_by("name")`
     * `owner`: `User.objects.filter(tenant=tenant).order_by("username")`
     * `original_order`: `SalesOrder.objects.filter(tenant=tenant).order_by("-order_date")`
     * `expansion_opportunity`: `Opportunity.objects.filter(tenant=tenant).order_by("-created_at")`

3. **`CustomerOnboardingForm`** (`CustomerOnboardings.py`):
   - Model: `CustomerOnboarding`
   - Fields: `["account", "lead_csm", "sales_order", "title", "playbook_template", "stage", "status", "kickoff_date", "target_go_live_date", "actual_go_live_date", "time_to_value_days", "progress_pct", "executive_sponsor_name", "executive_sponsor_email", "blockers", "success_criteria"]`
   - Excluded: `tenant`, `number`, `milestones_config`.
   - Tenant scoping in `__init__`:
     * `account`: `Party.objects.filter(tenant=tenant, roles__role="customer").distinct().order_by("name")`
     * `lead_csm`: `User.objects.filter(tenant=tenant).order_by("username")`
     * `sales_order`: `SalesOrder.objects.filter(tenant=tenant).order_by("-order_date")`

4. **`CustomerBusinessReviewForm`** (`CustomerBusinessReviews.py`):
   - Model: `CustomerBusinessReview`
   - Fields: `["account", "lead_csm", "account_plan", "title", "review_period", "review_year", "scheduled_date", "completed_date", "status", "template_type", "executive_sponsor_attended", "client_attendees", "internal_attendees", "health_score_at_review", "key_achievements", "challenges_and_risks", "is_referenceable", "case_study_status", "testimonial_quote", "notes"]`
   - Excluded: `tenant`, `number`, `action_items`, `reference_types_permitted`.
   - Tenant scoping in `__init__`:
     * `account`: `Party.objects.filter(tenant=tenant, roles__role="customer").distinct().order_by("name")`
     * `lead_csm`: `User.objects.filter(tenant=tenant).order_by("username")`
     * `account_plan`: `AccountPlan.objects.filter(tenant=tenant).order_by("-period_start")`

---

## 3. Views & View Context Contract (L7 / L8)

All views are function-based with `@login_required` (and `@tenant_admin_required` for delete actions).
Shared base: `from apps.sales.views._common import *`.

### 3.1 `CustomerHealthScore` Views (`views/CustomerSuccess/CustomerHealthScores.py`)
- `customer_health_score_list`:
  * Context:
    - `page_obj`: paginated queryset
    - `health_scores`: alias for `page_obj.object_list`
    - `health_band_choices`: `CustomerHealthScore.HEALTH_BAND_CHOICES`
    - `risk_level_choices`: `CustomerHealthScore.RISK_LEVEL_CHOICES`
    - `trend_choices`: `CustomerHealthScore.TREND_CHOICES`
    - `accounts`: `Party.objects.filter(tenant=request.tenant, roles__role="customer").distinct().order_by("name")`
    - `active_filters`: dict with `q`, `health_band`, `risk_level`, `account`
    - `stats`: dict with `total_count`, `healthy_count`, `attention_count`, `at_risk_count`, `avg_score`
- `customer_health_score_detail`:
  * Context:
    - `obj`: `CustomerHealthScore` instance
    - `health_score`: alias for `obj`
- `customer_health_score_create`:
  * Context: `form`, `obj=None`, `is_edit=False`
- `customer_health_score_edit`:
  * Context: `form`, `obj=instance`, `is_edit=True`
- `customer_health_score_delete`:
  * POST-only, returns redirect to `sales:customer_health_score_list`.
- `customer_health_console` (Console 1):
  * Context:
    - `health_scores`: all recent scores
    - `healthy_scores`: filter `health_band="green"`
    - `attention_scores`: filter `health_band="yellow"`
    - `at_risk_scores`: filter `health_band="red"`
    - `churn_alerts`: filter `is_churn_risk=True`
    - `stats`: aggregate metrics

### 3.2 `CustomerRenewal` Views (`views/CustomerSuccess/CustomerRenewals.py`)
- `customer_renewal_list`:
  * Context:
    - `page_obj`: paginated queryset
    - `renewals`: alias for `page_obj.object_list`
    - `stage_choices`: `CustomerRenewal.STAGE_CHOICES`
    - `churn_risk_choices`: `CustomerRenewal.CHURN_RISK_CHOICES`
    - `accounts`: `Party.objects.filter(tenant=request.tenant, roles__role="customer").distinct().order_by("name")`
    - `owners`: `User.objects.filter(tenant=request.tenant).order_by("username")`
    - `active_filters`: dict
    - `stats`: dict with `total_arr`, `projected_arr`, `upcoming_count`, `churn_risk_count`
- `customer_renewal_detail`:
  * Context: `obj`, `renewal`: alias for `obj`
- `customer_renewal_create`:
  * Context: `form`, `obj=None`, `is_edit=False`
- `customer_renewal_edit`:
  * Context: `form`, `obj=instance`, `is_edit=True`
- `customer_renewal_delete`:
  * POST-only, redirect to `sales:customer_renewal_list`.
- `customer_renewal_pipeline` (Console 2):
  * Context:
    - `renewals_by_stage`: dict grouping renewals by stage
    - `stage_totals`: dict with ARR per stage
    - `upcoming_30_days`: queryset
    - `upcoming_60_days`: queryset
    - `upcoming_90_days`: queryset
    - `stats`: aggregate ARR pipeline metrics

### 3.3 `CustomerOnboarding` Views (`views/CustomerSuccess/CustomerOnboardings.py`)
- `customer_onboarding_list`:
  * Context:
    - `page_obj`: paginated queryset
    - `onboardings`: alias for `page_obj.object_list`
    - `playbook_choices`: `CustomerOnboarding.PLAYBOOK_CHOICES`
    - `stage_choices`: `CustomerOnboarding.STAGE_CHOICES`
    - `status_choices`: `CustomerOnboarding.STATUS_CHOICES`
    - `accounts`: queryset
    - `csm_users`: queryset
    - `active_filters`: dict
    - `stats`: dict with `total_count`, `in_progress_count`, `at_risk_count`, `avg_progress`
- `customer_onboarding_detail`:
  * Context: `obj`, `onboarding`: alias for `obj`
- `customer_onboarding_create`:
  * Context: `form`, `obj=None`, `is_edit=False`
- `customer_onboarding_edit`:
  * Context: `form`, `obj=instance`, `is_edit=True`
- `customer_onboarding_delete`:
  * POST-only, redirect to `sales:customer_onboarding_list`.
- `customer_onboarding_hub` (Console 3):
  * Context:
    - `active_onboardings`: queryset
    - `blocked_onboardings`: queryset
    - `completed_recent`: queryset
    - `avg_ttv`: float or int
    - `stats`: aggregate metrics

### 3.4 `CustomerBusinessReview` Views (`views/CustomerSuccess/CustomerBusinessReviews.py`)
- `customer_business_review_list`:
  * Context:
    - `page_obj`: paginated queryset
    - `reviews`: alias for `page_obj.object_list`
    - `period_choices`: `CustomerBusinessReview.REVIEW_PERIOD_CHOICES`
    - `status_choices`: `CustomerBusinessReview.STATUS_CHOICES`
    - `template_choices`: `CustomerBusinessReview.TEMPLATE_CHOICES`
    - `case_study_choices`: `CustomerBusinessReview.CASE_STUDY_CHOICES`
    - `accounts`: queryset
    - `csm_users`: queryset
    - `active_filters`: dict
    - `stats`: dict with `total_count`, `scheduled_count`, `conducted_count`, `referenceable_count`
- `customer_business_review_detail`:
  * Context: `obj`, `review`: alias for `obj`
- `customer_business_review_create`:
  * Context: `form`, `obj=None`, `is_edit=False`
- `customer_business_review_edit`:
  * Context: `form`, `obj=instance`, `is_edit=True`
- `customer_business_review_delete`:
  * POST-only, redirect to `sales:customer_business_review_list`.
- `customer_qbr_studio` (Console 5):
  * Context:
    - `upcoming_qbrs`: scheduled reviews
    - `recent_completed`: conducted reviews
    - `stats`: summary counts
- `customer_advocacy_hub` (Console 4 / Bullet 4 Hub):
  * Context:
    - `referenceable_accounts`: reviews with `is_referenceable=True`
    - `case_study_pipeline`: reviews with `case_study_status != "none"`
    - `testimonials`: reviews with non-blank `testimonial_quote`
    - `stats`: reference count, case study count, quote count

---

## 4. URL Names & Routing Contract

All URL routes are nested in `apps/sales/urls/CustomerSuccess/`.
Included under `apps/sales/urls/__init__.py`.

1. `sales:customer_health_score_list` -> `/sales/customer-success/health-scores/`
2. `sales:customer_health_score_create` -> `/sales/customer-success/health-scores/create/`
3. `sales:customer_health_score_detail` -> `/sales/customer-success/health-scores/<int:pk>/`
4. `sales:customer_health_score_edit` -> `/sales/customer-success/health-scores/<int:pk>/edit/`
5. `sales:customer_health_score_delete` -> `/sales/customer-success/health-scores/<int:pk>/delete/`
6. `sales:customer_health_console` -> `/sales/customer-success/health-console/`
7. `sales:customer_renewal_list` -> `/sales/customer-success/renewals/`
8. `sales:customer_renewal_create` -> `/sales/customer-success/renewals/create/`
9. `sales:customer_renewal_detail` -> `/sales/customer-success/renewals/<int:pk>/`
10. `sales:customer_renewal_edit` -> `/sales/customer-success/renewals/<int:pk>/edit/`
11. `sales:customer_renewal_delete` -> `/sales/customer-success/renewals/<int:pk>/delete/`
12. `sales:customer_renewal_pipeline` -> `/sales/customer-success/renewal-pipeline/`
13. `sales:customer_onboarding_list` -> `/sales/customer-success/onboardings/`
14. `sales:customer_onboarding_create` -> `/sales/customer-success/onboardings/create/`
15. `sales:customer_onboarding_detail` -> `/sales/customer-success/onboardings/<int:pk>/`
16. `sales:customer_onboarding_edit` -> `/sales/customer-success/onboardings/<int:pk>/edit/`
17. `sales:customer_onboarding_delete` -> `/sales/customer-success/onboardings/<int:pk>/delete/`
18. `sales:customer_onboarding_hub` -> `/sales/customer-success/onboarding-hub/`
19. `sales:customer_business_review_list` -> `/sales/customer-success/business-reviews/`
20. `sales:customer_business_review_create` -> `/sales/customer-success/business-reviews/create/`
21. `sales:customer_business_review_detail` -> `/sales/customer-success/business-reviews/<int:pk>/`
22. `sales:customer_business_review_edit` -> `/sales/customer-success/business-reviews/<int:pk>/edit/`
23. `sales:customer_business_review_delete` -> `/sales/customer-success/business-reviews/<int:pk>/delete/`
24. `sales:customer_qbr_studio` -> `/sales/customer-success/qbr-studio/`
25. `sales:customer_advocacy_hub` -> `/sales/customer-success/advocacy-hub/`

---

## 5. Templates Contract

Template paths strictly match: `templates/sales/customersuccess/<entity>/<page>.html`
- `customerhealthscore/` (`list.html`, `detail.html`, `form.html`)
- `customerrenewal/` (`list.html`, `detail.html`, `form.html`)
- `customeronboarding/` (`list.html`, `detail.html`, `form.html`)
- `customerbusinessreview/` (`list.html`, `detail.html`, `form.html`)
Consoles in `templates/sales/customersuccess/`:
- `health_console.html`
- `renewal_pipeline.html`
- `onboarding_hub.html`
- `advocacy_hub.html`
- `qbr_studio.html`

### Badge Design System Classes (L33)
- `.badge .badge-green` — Healthy (75-100), Renewed, Completed, On Track, Client Approved, Published.
- `.badge .badge-amber` — Needs Attention (50-74), In Progress, Negotiation, Proposal Sent, Drafting, Medium Risk.
- `.badge .badge-red` — At Risk (<50), Critical Risk, Churned, Blocked, Cancelled.
- `.badge .badge-info` — Upcoming, Kickoff, Scheduled, Candidate Identified.
- `.badge .badge-slate` — Not Started, Contracted Down.
- `.badge .badge-muted` — Stalled, None.

---

## 6. Sidebar Navigation Contract (`apps/core/navigation.py`)

Add `LIVE_LINKS["8.11"]` with exact NavERP.md feature bullet titles:
```python
    "8.11": {
        # OWNERSHIP RULINGS (L29/L36/L37)
        # Reuses core.Party (customer role); reuses crm.Opportunity (expansion deals);
        # reuses scm.SalesOrder (contract execution); reuses sales.AccountPlan (strategic alignment);
        # reuses accounting.Currency (contract ARR values).
        # Zero duplicate customer, deal, order, currency, or project ledger declared.
        "Health Scoring & Risk Alerts": "sales:customer_health_console",
        "Renewal & Expansion Pipeline": "sales:customer_renewal_pipeline",
        "Onboarding & Implementation": "sales:customer_onboarding_hub",
        "Advocacy & Reference Management": "sales:customer_advocacy_hub",
        "Quarterly Business Reviews (QBRs)": "sales:customer_qbr_studio",
        # Extra live leaves
        "Health Scores": "sales:customer_health_score_list",
        "Customer Renewals": "sales:customer_renewal_list",
        "Customer Onboardings": "sales:customer_onboarding_list",
        "Business Reviews": "sales:customer_business_review_list",
    },
```
