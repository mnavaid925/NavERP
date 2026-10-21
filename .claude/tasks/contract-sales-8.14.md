# Build Contract — Sub-module 8.14: Partner & Channel Management (Module 8: Sales Management System, `apps/sales`)

> Phase 3 Step 1. `BASE = d1a87b0f7d6421a166f253bef8ff624c0aeddfa8`.
> Research: `.claude/tasks/research-sales-8.14.md`. Plan: `.claude/tasks/todo.md`.
> Next migration: **`0025_partnerprofile_dealregistration_jointaccountplan_channelconflict`** (claimed).

---

## 0. Ownership Rulings (L29 / L36 / L37)

8.14 adds 4 tenant-scoped models and 1 derived read-only performance console. It declares **zero duplicate company, opportunity, territory, or financial ledger tables**.

| Entity / Domain | Read-Only Master Owner | Where It Lives | 8.14's Relationship |
|---|---|---|---|
| **Partner Organizations & Clients** | **Core Spine** | `apps/core/models/Party.py` | `core.Party` (with `PartyRole.role="partner"` for partner companies, and role `customer` for end clients) is the master account anchor. Zero duplicate partner or company table. |
| **Partner Contacts** | **Core Spine** | `apps/core/models/Party.py` | Individual contacts at partner firms are `core.Party` rows with role `contact` or direct contact fields. |
| **Document Collateral & Agreements** | **Core Spine** | `apps/core/models/Document.py` | `core.Document` provides shared storage for signed partnership agreements, NDAs, and co-selling collateral. |
| **Deals & Opportunities** | **CRM 1.2** | `apps/crm/models/SalesForceAutomation/Opportunities.py` | `crm.Opportunity` (`OPP-`) is the opportunity master into which approved deal registrations convert. Zero duplicate deal table. |
| **Territories & Channel Regions** | **CRM 1.4** | `apps/crm/models/SalesForceAutomation/Territories.py` | `crm.Territory` (`TER-`) provides geographic and market territory anchors for partner authorization and dispute resolution. |
| **Currencies & Exchange Rates** | **Accounting 2.2** | `apps/accounting/models/GeneralLedger/Currencies.py` | `accounting.Currency` (global ISO 4217) provides currency denominations for deal values and revenue goals. |
| **Channel Account Managers & Direct Reps** | **accounts 0** | `apps/accounts/models/User.py` | `settings.AUTH_USER_MODEL` (`accounts.User`) represents Channel Account Managers (CAMs), Partner Managers, Direct Sales Reps, and Channel Chiefs. |

---

## 1. Models — Every Field, Every Choice, Every Constraint

All models reside in `apps/sales/models/PartnerChannel/`.
Base: `apps.sales.models._base.TenantNumbered` (includes `tenant` FK `core.Tenant`, `number = CharField(max_length=20, editable=False)`, `created_at`, `updated_at`).

### 1.1 `PartnerProfile` (`PartnerProfiles.py`) — `NUMBER_PREFIX = "PTR"`

```python
PARTNER_TYPE_CHOICES = [
    ("reseller", "Reseller / VAR"),
    ("system_integrator", "System Integrator (SI)"),
    ("distributor", "Distributor"),
    ("isv_technology", "ISV / Technology Partner"),
    ("referral", "Referral / Affiliate"),
    ("consulting", "Consulting & Advisory"),
]

ONBOARDING_STATUS_CHOICES = [
    ("applied", "Application Submitted"),
    ("under_review", "Under Review"),
    ("agreement_pending", "Agreement Pending"),
    ("onboarding", "Onboarding & Training"),
    ("active", "Active Certified Partner"),
    ("suspended", "Suspended"),
    ("terminated", "Terminated"),
]

PARTNER_TIER_CHOICES = [
    ("registered", "Registered Partner"),
    ("bronze", "Bronze"),
    ("silver", "Silver"),
    ("gold", "Gold"),
    ("platinum", "Platinum"),
]
```

| Field | Type | Attributes & Clean Guards |
|---|---|---|
| `partner` | `ForeignKey("core.Party", CASCADE, related_name="sales_partner_profiles")` | Partner company account, required |
| `partner_type` | `CharField(30, choices=PARTNER_TYPE_CHOICES, default="reseller")` | Channel category |
| `onboarding_status` | `CharField(20, choices=ONBOARDING_STATUS_CHOICES, default="applied")` | Recruitment & certification lifecycle stage |
| `tier` | `CharField(20, choices=PARTNER_TIER_CHOICES, default="registered")` | Performance tier |
| `tier_effective_date` | `DateField(null=True, blank=True)` | When current tier became active |
| `tier_review_date` | `DateField(null=True, blank=True)` | Next annual/quarterly audit date |
| `application_date` | `DateField(default=timezone.localdate)` | Date partner applied |
| `agreement_signed_at` | `DateTimeField(null=True, blank=True)` | Timestamp partner agreement executed |
| `agreement_document` | `ForeignKey("core.Document", SET_NULL, null=True, blank=True, related_name="sales_partner_agreements")` | Executed contract attachment |
| `channel_manager` | `ForeignKey(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, related_name="sales_managed_partners")` | Internal Channel Account Manager (CAM) |
| `authorized_territory` | `ForeignKey("crm.Territory", SET_NULL, null=True, blank=True, related_name="sales_territory_partners")` | Authorized geographic/industry territory |
| `currency` | `ForeignKey("accounting.Currency", PROTECT, related_name="sales_partner_currencies")` | Reporting currency master |
| `annual_revenue_target` | `DecimalField(14, 2, default=Decimal("0.00"))` | Target revenue quota |
| `actual_revenue_ytd` | `DecimalField(14, 2, default=Decimal("0.00"))` | Closed revenue year-to-date |
| `required_certifications_count` | `PositiveSmallIntegerField(default=1)` | Tier certification threshold |
| `active_certifications_count` | `PositiveSmallIntegerField(default=0)` | Current certified head count |
| `base_discount_pct` | `DecimalField(5, 2, default=Decimal("10.00"), validators=[MinValueValidator(0), MaxValueValidator(100)])` | Standard tier margin discount |
| `deal_reg_margin_pct` | `DecimalField(5, 2, default=Decimal("15.00"), validators=[MinValueValidator(0), MaxValueValidator(100)])` | Add-on margin for registered deals |
| `portal_access_enabled` | `BooleanField(default=False)` | Partner portal credentials flag |
| `notes` | `TextField(blank=True)` | Partner notes & relationship log |

- `Meta.ordering = ["-actual_revenue_ytd", "partner__legal_name"]`
- `Meta.constraints`:
  * `UniqueConstraint(fields=["tenant", "partner"], name="sales_ptr_ten_part_uniq")` (24 chars)
  * `UniqueConstraint(fields=["tenant", "number"], name="sales_ptr_ten_num_uniq")` (23 chars)
- `Meta.indexes`:
  * `Index(fields=["tenant", "onboarding_status"], name="sales_ptr_onboard_idx")` (21 chars)
  * `Index(fields=["tenant", "tier"], name="sales_ptr_tier_idx")` (18 chars)
  * `Index(fields=["tenant", "channel_manager"], name="sales_ptr_cam_idx")` (17 chars)
- `clean()`:
  - **G1**: Verify `partner` belongs to `self.tenant` (`self.partner.tenant_id == self.tenant_id`).
  - **G2**: If `authorized_territory` set, verify same tenant (`self.authorized_territory.tenant_id == self.tenant_id`).
  - **G3**: If `agreement_document` set, verify same tenant (`self.agreement_document.tenant_id == self.tenant_id`).
  - **G4**: If `channel_manager` set, verify same tenant (`self.channel_manager.tenant_id == self.tenant_id`).
  - **G5**: If `onboarding_status == "active"` and `agreement_signed_at` is None, raise ValidationError ("Active partner must have signed partnership agreement timestamp").

---

### 1.2 `DealRegistration` (`DealRegistrations.py`) — `NUMBER_PREFIX = "DLR"`

```python
REGISTRATION_STATUS_CHOICES = [
    ("submitted", "Submitted / Pending"),
    ("under_review", "Under Review"),
    ("approved", "Approved & Protected"),
    ("rejected", "Rejected"),
    ("expired", "Protection Expired"),
    ("converted", "Converted to Opportunity"),
    ("conflicted", "Channel Conflicted"),
]

EXCLUSIVITY_CHOICES = [
    ("pending", "Pending Approval"),
    ("exclusive", "Full Exclusivity"),
    ("non_exclusive", "Non-Exclusive"),
    ("expired", "Expired"),
    ("revoked", "Revoked"),
]
```

| Field | Type | Attributes & Clean Guards |
|---|---|---|
| `partner` | `ForeignKey("core.Party", CASCADE, related_name="sales_partner_deal_registrations")` | Registering partner firm |
| `customer_account` | `ForeignKey("core.Party", CASCADE, related_name="sales_registered_deals")` | Prospective client account |
| `deal_name` | `CharField(255)` | Project / Deal title |
| `estimated_value` | `DecimalField(14, 2, validators=[MinValueValidator(Decimal("0.01"))])` | Anticipated contract size |
| `currency` | `ForeignKey("accounting.Currency", PROTECT, related_name="sales_deal_reg_currencies")` | Currency master |
| `expected_close_date` | `DateField()` | Projected signature date |
| `submission_date` | `DateField(default=timezone.localdate)` | Date registration entered |
| `status` | `CharField(20, choices=REGISTRATION_STATUS_CHOICES, default="submitted")` | Review & protection status |
| `rejection_reason` | `CharField(255, blank=True)` | Reason code if rejected |
| `protection_start_date` | `DateField(null=True, blank=True)` | Exclusivity window start |
| `protection_end_date` | `DateField(null=True, blank=True)` | Exclusivity window expiration |
| `exclusivity_status` | `CharField(20, choices=EXCLUSIVITY_CHOICES, default="pending")` | Margin lock status |
| `protected_margin_pct` | `DecimalField(5, 2, default=Decimal("15.00"), validators=[MinValueValidator(0), MaxValueValidator(100)])` | Locked margin discount % |
| `extension_count` | `PositiveSmallIntegerField(default=0)` | Number of 30-day extensions granted |
| `is_conflicted` | `BooleanField(default=False)` | Channel collision flag |
| `conflict_summary` | `TextField(blank=True)` | Conflict notes |
| `opportunity` | `ForeignKey("crm.Opportunity", SET_NULL, null=True, blank=True, related_name="sales_registered_deal_sources")` | Resulting converted opportunity |
| `reviewed_by` | `ForeignKey(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, related_name="sales_reviewed_deal_regs")` | CAM who reviewed registration |
| `reviewed_at` | `DateTimeField(null=True, blank=True)` | Timestamp review completed |
| `partner_rep_name` | `CharField(150, blank=True)` | Partner sales rep contact |
| `partner_rep_email` | `EmailField(blank=True)` | Partner sales rep email |
| `notes` | `TextField(blank=True)` | Partner notes / scope description |

- `Meta.ordering = ["-submission_date", "-estimated_value"]`
- `Meta.constraints`: `UniqueConstraint(fields=["tenant", "number"], name="sales_dlr_ten_num_uniq")` (23 chars)
- `Meta.indexes`:
  * `Index(fields=["tenant", "partner", "status"], name="sales_dlr_part_stat_idx")` (24 chars)
  * `Index(fields=["tenant", "customer_account"], name="sales_dlr_cust_idx")` (18 chars)
  * `Index(fields=["tenant", "protection_end_date"], name="sales_dlr_prot_end_idx")` (22 chars)
  * `Index(fields=["tenant", "status"], name="sales_dlr_stat_idx")` (18 chars)
- `clean()`:
  - **G1**: Verify `partner` and `customer_account` belong to `self.tenant`.
  - **G2**: `partner` must not equal `customer_account`.
  - **G3**: If `protection_start_date` and `protection_end_date` are both set, `protection_end_date >= protection_start_date`.
  - **G4**: If `status == "approved"`, `protection_start_date` and `protection_end_date` must not be null.
  - **G5**: If `opportunity` set, verify same tenant.

---

### 1.3 `JointAccountPlan` (`JointAccountPlans.py`) — `NUMBER_PREFIX = "JAP"`

```python
PLAN_STATUS_CHOICES = [
    ("draft", "Drafting"),
    ("active", "Active & Executing"),
    ("achieved", "Targets Achieved"),
    ("underperforming", "Underperforming"),
    ("closed", "Closed"),
]

CO_SELL_MOTION_CHOICES = [
    ("partner_led", "Partner Led Co-Sell"),
    ("vendor_led", "Vendor Led Co-Sell"),
    ("joint_pursuit", "Equal Joint Pursuit"),
    ("services_only", "Partner Services Only"),
]
```

| Field | Type | Attributes & Clean Guards |
|---|---|---|
| `partner` | `ForeignKey("core.Party", CASCADE, related_name="sales_partner_joint_plans")` | Partner company |
| `client_account` | `ForeignKey("core.Party", CASCADE, related_name="sales_client_joint_plans")` | Target enterprise account |
| `plan_name` | `CharField(255)` | Strategic plan identifier |
| `plan_year` | `PositiveIntegerField(default=2026)` | Calendar / fiscal year |
| `period_start` | `DateField(default=timezone.localdate)` | Plan execution start |
| `period_end` | `DateField()` | Plan execution end |
| `status` | `CharField(20, choices=PLAN_STATUS_CHOICES, default="draft")` | Lifecycle state |
| `target_revenue` | `DecimalField(14, 2, default=Decimal("0.00"))` | Joint revenue goal |
| `actual_revenue` | `DecimalField(14, 2, default=Decimal("0.00"))` | Closed co-sell revenue |
| `currency` | `ForeignKey("accounting.Currency", PROTECT, related_name="sales_jap_currencies")` | Currency master |
| `vendor_lead` | `ForeignKey(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, related_name="sales_led_joint_plans")` | Internal Account Executive |
| `partner_lead_name` | `CharField(150)` | Partner co-sell champion |
| `partner_lead_email` | `EmailField(blank=True)` | Partner lead email |
| `co_sell_motion` | `CharField(30, choices=CO_SELL_MOTION_CHOICES, default="joint_pursuit")` | Primary go-to-market motion |
| `strategic_objectives` | `TextField(blank=True)` | Joint objectives & milestones |
| `joint_value_proposition` | `TextField(blank=True)` | Combined product/service value pitch |
| `action_items` | `JSONField(default=list, blank=True)` | Execution action item checklist |
| `collateral_document` | `ForeignKey("core.Document", SET_NULL, null=True, blank=True, related_name="sales_jap_collaterals")` | Co-branded collateral attachment |
| `notes` | `TextField(blank=True)` | Collaboration notes |

- `Meta.ordering = ["-period_end", "-target_revenue"]`
- `Meta.constraints`: `UniqueConstraint(fields=["tenant", "number"], name="sales_jap_ten_num_uniq")` (23 chars)
- `Meta.indexes`:
  * `Index(fields=["tenant", "partner", "client_account"], name="sales_jap_part_client_idx")` (26 chars)
  * `Index(fields=["tenant", "status"], name="sales_jap_status_idx")` (20 chars)
- `clean()`:
  - **G1**: Verify `partner` and `client_account` belong to `self.tenant`.
  - **G2**: `partner` must not equal `client_account`.
  - **G3**: `period_end >= period_start`.
  - **G4**: If `collateral_document` set, verify same tenant.

---

### 1.4 `ChannelConflict` (`ChannelConflicts.py`) — `NUMBER_PREFIX = "CCF"`

```python
CONFLICT_TYPE_CHOICES = [
    ("direct_vs_indirect", "Direct Sales vs. Partner Conflict"),
    ("partner_vs_partner", "Partner vs. Partner Collision"),
    ("territory_overlap", "Territory Boundary Dispute"),
    ("named_account_infringement", "Named Enterprise Account Infringement"),
]

SEVERITY_CHOICES = [
    ("low", "Low"),
    ("medium", "Medium"),
    ("high", "High"),
    ("critical", "Critical (Escalated to CRO)"),
]

CONFLICT_STATUS_CHOICES = [
    ("open", "Open / Investigating"),
    ("in_mediation", "In Active Mediation"),
    ("resolved", "Resolved & Adjudicated"),
    ("dismissed", "Dismissed / Ineligible"),
    ("escalated", "Escalated to Executive"),
]

ESCALATION_LEVEL_CHOICES = [
    ("l1_cam", "Level 1: Channel Account Manager (CAM)"),
    ("l2_channel_chief", "Level 2: Channel Chief / VP Channels"),
    ("l3_executive_cro", "Level 3: Executive Adjudication (CRO)"),
]

RESOLUTION_CHOICES = [
    ("pending", "Pending Determination"),
    ("partner_favored", "Partner Exclusivity Upheld"),
    ("direct_favored", "Direct Sales Precedence Upheld"),
    ("split_commission", "Commission / Revenue Split Imposed"),
    ("co_sell_mandate", "Mandated Joint Co-Sell Agreement"),
    ("deal_cancelled", "Deal Cancelled / Disqualified"),
]
```

| Field | Type | Attributes & Clean Guards |
|---|---|---|
| `conflict_type` | `CharField(35, choices=CONFLICT_TYPE_CHOICES, default="direct_vs_indirect")` | Conflict taxonomy |
| `severity` | `CharField(15, choices=SEVERITY_CHOICES, default="medium")` | Impact severity |
| `status` | `CharField(20, choices=CONFLICT_STATUS_CHOICES, default="open")` | Investigation state |
| `deal_registration` | `ForeignKey("sales.DealRegistration", SET_NULL, null=True, blank=True, related_name="channel_conflicts")` | Disputed deal registration |
| `opportunity` | `ForeignKey("crm.Opportunity", SET_NULL, null=True, blank=True, related_name="sales_channel_conflicts")` | Disputed opportunity |
| `claimant_partner` | `ForeignKey("core.Party", CASCADE, related_name="sales_claimed_conflicts")` | Partner lodging conflict |
| `competing_partner` | `ForeignKey("core.Party", SET_NULL, null=True, blank=True, related_name="sales_opposing_conflicts")` | Rival partner in collision |
| `direct_sales_rep` | `ForeignKey(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, related_name="sales_direct_conflicts")` | Internal direct AE in conflict |
| `client_account` | `ForeignKey("core.Party", CASCADE, related_name="sales_account_conflicts")` | Contested customer account |
| `territory` | `ForeignKey("crm.Territory", SET_NULL, null=True, blank=True, related_name="sales_conflict_territories")` | Contested territory |
| `escalation_level` | `CharField(25, choices=ESCALATION_LEVEL_CHOICES, default="l1_cam")` | Current tier in 3-level escalation ladder |
| `escalated_to` | `ForeignKey(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, related_name="sales_escalated_conflicts")` | Assignee handling dispute |
| `resolution_outcome` | `CharField(30, choices=RESOLUTION_CHOICES, default="pending")` | Adjudication ruling |
| `split_percentage` | `DecimalField(5, 2, default=Decimal("0.00"), validators=[MinValueValidator(0), MaxValueValidator(100)])` | Revenue / commission split % |
| `resolution_rationale` | `TextField(blank=True)` | Formal explanation of ruling |
| `resolved_by` | `ForeignKey(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, related_name="sales_adjudicated_conflicts")` | Executive adjudicator |
| `resolved_at` | `DateTimeField(null=True, blank=True)` | Ruling timestamp |
| `description` | `TextField(blank=True)` | Factual dispute narrative |

- `Meta.ordering = ["-created_at"]`
- `Meta.constraints`: `UniqueConstraint(fields=["tenant", "number"], name="sales_ccf_ten_num_uniq")` (23 chars)
- `Meta.indexes`:
  * `Index(fields=["tenant", "status"], name="sales_ccf_stat_idx")` (18 chars)
  * `Index(fields=["tenant", "conflict_type"], name="sales_ccf_type_idx")` (18 chars)
  * `Index(fields=["tenant", "claimant_partner"], name="sales_ccf_part_idx")` (18 chars)
  * `Index(fields=["tenant", "escalation_level"], name="sales_ccf_esc_idx")` (17 chars)
- `clean()`:
  - **G1**: Verify `claimant_partner` and `client_account` belong to `self.tenant`.
  - **G2**: If `competing_partner` set, verify same tenant and not equal to `claimant_partner`.
  - **G3**: If `territory` set, verify same tenant.
  - **G4**: If `status == "resolved"`, `resolution_outcome` must not be `"pending"`, and `resolved_at` must not be null.

---

## 2. Forms — Meta Fields & Exclusions

All forms reside in `apps/sales/forms/PartnerChannel/`.
Base rules:
- Exclude `tenant`, auto-`number`, and system timestamps `created_at`, `updated_at`.
- All foreign keys narrow querysets to `request.tenant` in `__init__`.
- Multi-tenant foreign key protection enforced in `clean()`.

### 2.1 `PartnerProfileForm` (`PartnerProfiles.py`)
- Model: `PartnerProfile`
- Fields: `["partner", "partner_type", "onboarding_status", "tier", "tier_effective_date", "tier_review_date", "application_date", "agreement_signed_at", "agreement_document", "channel_manager", "authorized_territory", "currency", "annual_revenue_target", "actual_revenue_ytd", "required_certifications_count", "active_certifications_count", "base_discount_pct", "deal_reg_margin_pct", "portal_access_enabled", "notes"]`
- Exclude: `["tenant", "number"]`

### 2.2 `DealRegistrationForm` (`DealRegistrations.py`)
- Model: `DealRegistration`
- Fields: `["partner", "customer_account", "deal_name", "estimated_value", "currency", "expected_close_date", "submission_date", "status", "rejection_reason", "protection_start_date", "protection_end_date", "exclusivity_status", "protected_margin_pct", "extension_count", "is_conflicted", "conflict_summary", "opportunity", "reviewed_by", "reviewed_at", "partner_rep_name", "partner_rep_email", "notes"]`
- Exclude: `["tenant", "number"]`

### 2.3 `JointAccountPlanForm` (`JointAccountPlans.py`)
- Model: `JointAccountPlan`
- Fields: `["partner", "client_account", "plan_name", "plan_year", "period_start", "period_end", "status", "target_revenue", "actual_revenue", "currency", "vendor_lead", "partner_lead_name", "partner_lead_email", "co_sell_motion", "strategic_objectives", "joint_value_proposition", "action_items", "collateral_document", "notes"]`
- Exclude: `["tenant", "number"]`

### 2.4 `ChannelConflictForm` (`ChannelConflicts.py`)
- Model: `ChannelConflict`
- Fields: `["conflict_type", "severity", "status", "deal_registration", "opportunity", "claimant_partner", "competing_partner", "direct_sales_rep", "client_account", "territory", "escalation_level", "escalated_to", "resolution_outcome", "split_percentage", "resolution_rationale", "resolved_by", "resolved_at", "description"]`
- Exclude: `["tenant", "number"]`

---

## 3. URLs & Route Names

All URL configs reside in `apps/sales/urls/PartnerChannel/`.
Base namespace: `sales:`.

| Route Pattern | View Function | URL Name | Description |
|---|---|---|---|
| `partner-channel/partners/` | `partner_profile_list` | `partner_profile_list` | Partner directory list |
| `partner-channel/partners/new/` | `partner_profile_create` | `partner_profile_create` | Add new partner profile |
| `partner-channel/partners/<int:pk>/` | `partner_profile_detail` | `partner_profile_detail` | Partner profile details & tiers |
| `partner-channel/partners/<int:pk>/edit/` | `partner_profile_edit` | `partner_profile_edit` | Edit partner profile |
| `partner-channel/partners/<int:pk>/delete/` | `partner_profile_delete` | `partner_profile_delete` | Delete partner profile |
| `partner-channel/deal-registrations/` | `deal_registration_list` | `deal_registration_list` | Deal registration list & filters |
| `partner-channel/deal-registrations/new/` | `deal_registration_create` | `deal_registration_create` | Register deal |
| `partner-channel/deal-registrations/<int:pk>/` | `deal_registration_detail` | `deal_registration_detail` | Deal registration detail |
| `partner-channel/deal-registrations/<int:pk>/edit/` | `deal_registration_edit` | `deal_registration_edit` | Edit deal registration |
| `partner-channel/deal-registrations/<int:pk>/delete/` | `deal_registration_delete` | `deal_registration_delete` | Delete deal registration |
| `partner-channel/joint-plans/` | `joint_account_plan_list` | `joint_account_plan_list` | Joint plans list |
| `partner-channel/joint-plans/new/` | `joint_account_plan_create` | `joint_account_plan_create` | Create joint plan |
| `partner-channel/joint-plans/<int:pk>/` | `joint_account_plan_detail` | `joint_account_plan_detail` | Joint plan detail |
| `partner-channel/joint-plans/<int:pk>/edit/` | `joint_account_plan_edit` | `joint_account_plan_edit` | Edit joint plan |
| `partner-channel/joint-plans/<int:pk>/delete/` | `joint_account_plan_delete` | `joint_account_plan_delete` | Delete joint plan |
| `partner-channel/conflicts/` | `channel_conflict_list` | `channel_conflict_list` | Channel conflicts list |
| `partner-channel/conflicts/new/` | `channel_conflict_create` | `channel_conflict_create` | File new conflict |
| `partner-channel/conflicts/<int:pk>/` | `channel_conflict_detail` | `channel_conflict_detail` | Conflict resolution detail |
| `partner-channel/conflicts/<int:pk>/edit/` | `channel_conflict_edit` | `channel_conflict_edit` | Edit / adjudicate conflict |
| `partner-channel/conflicts/<int:pk>/delete/` | `channel_conflict_delete` | `channel_conflict_delete` | Delete conflict |
| `partner-channel/console/` | `partner_performance_console` | `partner_performance_console` | Partner performance executive console |

---

## 4. Views & Context Keys Contract

All views reside in `apps/sales/views/PartnerChannel/`.

### 4.1 `partner_profile_list`
- Variables:
  - `page_obj`: paginated queryset of `PartnerProfile`
  - `partner_profiles`: `page_obj.object_list`
  - `partner_type_choices`: `PartnerProfile.PARTNER_TYPE_CHOICES`
  - `onboarding_status_choices`: `PartnerProfile.ONBOARDING_STATUS_CHOICES`
  - `tier_choices`: `PartnerProfile.PARTNER_TIER_CHOICES`
  - `channel_managers`: `accounts.User` queryset for CAM dropdown
  - `q`: search term
  - `selected_type`: `request.GET.get('partner_type')`
  - `selected_status`: `request.GET.get('onboarding_status')`
  - `selected_tier`: `request.GET.get('tier')`
  - `selected_cam`: `request.GET.get('channel_manager')`

### 4.2 `partner_profile_detail`
- Variables:
  - `partner_profile`: instance of `PartnerProfile`
  - `registrations`: recent `DealRegistration` rows for this partner
  - `joint_plans`: active `JointAccountPlan` rows for this partner
  - `conflicts`: active `ChannelConflict` rows involving this partner

### 4.3 `deal_registration_list`
- Variables:
  - `page_obj`: paginated queryset of `DealRegistration`
  - `deal_registrations`: `page_obj.object_list`
  - `status_choices`: `DealRegistration.REGISTRATION_STATUS_CHOICES`
  - `exclusivity_choices`: `DealRegistration.EXCLUSIVITY_CHOICES`
  - `partners`: `core.Party` queryset for partner dropdown
  - `q`: search term
  - `selected_status`: `request.GET.get('status')`
  - `selected_exclusivity`: `request.GET.get('exclusivity_status')`
  - `selected_partner`: `request.GET.get('partner')`

### 4.4 `deal_registration_detail`
- Variables:
  - `deal_registration`: instance of `DealRegistration`
  - `conflicts`: linked `ChannelConflict` records

### 4.5 `joint_account_plan_list`
- Variables:
  - `page_obj`: paginated queryset of `JointAccountPlan`
  - `joint_plans`: `page_obj.object_list`
  - `status_choices`: `JointAccountPlan.PLAN_STATUS_CHOICES`
  - `motion_choices`: `JointAccountPlan.CO_SELL_MOTION_CHOICES`
  - `partners`: `core.Party` queryset
  - `q`: search term
  - `selected_status`: `request.GET.get('status')`
  - `selected_motion`: `request.GET.get('co_sell_motion')`
  - `selected_partner`: `request.GET.get('partner')`

### 4.6 `joint_account_plan_detail`
- Variables:
  - `joint_plan`: instance of `JointAccountPlan`

### 4.7 `channel_conflict_list`
- Variables:
  - `page_obj`: paginated queryset of `ChannelConflict`
  - `conflicts`: `page_obj.object_list`
  - `conflict_type_choices`: `ChannelConflict.CONFLICT_TYPE_CHOICES`
  - `status_choices`: `ChannelConflict.CONFLICT_STATUS_CHOICES`
  - `escalation_level_choices`: `ChannelConflict.ESCALATION_LEVEL_CHOICES`
  - `q`: search term
  - `selected_type`: `request.GET.get('conflict_type')`
  - `selected_status`: `request.GET.get('status')`
  - `selected_level`: `request.GET.get('escalation_level')`

### 4.8 `channel_conflict_detail`
- Variables:
  - `conflict`: instance of `ChannelConflict`

### 4.9 `partner_performance_console`
- Variables:
  - `stats`: dict with:
    - `active_partners_count`
    - `total_partner_revenue`
    - `registered_deals_count`
    - `pipeline_value`
    - `open_conflicts_count`
    - `avg_certifications`
  - `tier_distribution`: list of tier dicts (`tier_name`, `count`, `revenue`)
  - `top_partners`: top 5 partners by revenue
  - `expiring_registrations`: deal registrations expiring in next 30 days
  - `recent_conflicts`: latest open conflicts

---

## 5. Templates Path Architecture

Templates live strictly at:
- `templates/sales/partnerchannel/partnerprofile/{list,detail,form}.html`
- `templates/sales/partnerchannel/dealregistration/{list,detail,form}.html`
- `templates/sales/partnerchannel/jointaccountplan/{list,detail,form}.html`
- `templates/sales/partnerchannel/channelconflict/{list,detail,form}.html`
- `templates/sales/partnerchannel/boards/partner_performance_console.html`

Badges: colour-named ONLY: `.badge-green`, `.badge-amber`, `.badge-red`, `.badge-info`, `.badge-muted`, `.badge-slate`.
Icons: `<i data-lucide="NAME"></i>`.
Actions: View (eye), Edit (pencil), Delete (trash-2).

---

## 6. Sidebar `LIVE_LINKS["8.14"]`

In `apps/core/navigation.py`:
```python
    "8.14": {
        "Partner Recruitment & Onboarding": "sales:partner_profile_list",
        "Deal Registration & Protection": "sales:deal_registration_list",
        "Partner Portal & Collaboration": "sales:joint_account_plan_list",
        "Partner Performance Tracking": "sales:partner_performance_console",
        "Channel Conflict Management": "sales:channel_conflict_list",
    },
```
