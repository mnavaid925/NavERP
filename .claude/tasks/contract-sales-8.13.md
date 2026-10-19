# Build Contract — Sub-module 8.13: Marketing Alignment & Attribution (Module 8: Sales Management System, `apps/sales`)

> Phase 3 Step 1. `BASE = 386a2b27a38fb2589f69ddb287976cc2302ea332`.
> Research: `.claude/tasks/research-sales-8.13.md`. Plan: `.claude/tasks/todo.md`.
> Next migration: **`0022_marketingalignment`** (the last `apps/sales` migration is `0021_customersuccess`).
> App **already exists** → this run EXTENDS it. No scaffold, no `apps.py`, no `config/settings.py`
> or `config/urls.py` change. The only navigation change is one new `LIVE_LINKS["8.13"]` entry.

---

## 0. Ownership Rulings (L29 / L36 / L37)

8.13 adds **5 entity folders / 6 model classes** and **1 derived console**. It declares **zero
duplicate campaign, lead, opportunity, account, content, user, or currency tables**.

| Entity / Domain | Read-Only Master Owner | Where It Lives | 8.13's Relationship |
|---|---|---|---|
| **Marketing Campaigns** | **CRM 1.3** | `apps/crm/models/MarketingAutomation/Campaigns.py` | `crm.Campaign` (`CAM-`) is the campaign master — budget, actual spend, target size and the UTM triple. 8.13 FKs it on 4 of its 6 classes and reads its spend for the ROI rollup. Zero duplicate campaign table. |
| **Leads** | **CRM 1.1** | `apps/crm/models/CoreData/Leads.py` | `crm.Lead` (`LEAD-`) is the identity the whole journey is stitched to (status, score, source, owner, est. value). Zero duplicate lead table. |
| **Opportunities** | **CRM 1.2** | `apps/crm/models/SalesForceAutomation/Opportunities.py` | `crm.Opportunity` (`OPP-`) is the conversion endpoint — a touchpoint may point at it, and an accepted MQL handoff may point at the opportunity it produced. Zero duplicate deal table. |
| **Customer Accounts** | **Core Spine** | `apps/core/models/Party.py` | `core.Party` with role `customer` is the account anchor on handoffs, content engagements and event registrations. Zero duplicate customer table. |
| **Content / Collateral** | **Sales 8.9** | `apps/sales/models/SalesEnablement/EnablementContents.py` | `sales.EnablementContent` (`ECN-`) is the content master. `ContentEngagement` measures *interactions with* it. Zero duplicate content table. |
| **Owners / Reps / Attendees** | **accounts 0** | `apps/accounts/models/User.py` | `settings.AUTH_USER_MODEL` (`accounts.User`) is the marketing owner, the assigned sales rep, the attribution computer and the event owner. |
| **Currencies** | **Accounting 2.2** | `apps/accounting/models/GeneralLedger/Currencies.py` | `accounting.Currency` (global ISO 4217) denominates touch cost, engagement revenue, handoff value and event budget. |

**No JournalEntry is posted by 8.13 (L29).** Campaign ROI, "pipeline generated" and attributed
revenue are *marketing-side attribution of revenue recognised elsewhere*. 8.13 posts nothing to the
financial ledger.

**Ruling on the model budget (skill §Step 1, "aim for 1–4 models").** 8.13 has **five** NavERP
feature bullets and each needs its own navigable list page, so a strict 4-model cut would silently
drop a bullet. `EventRegistration` is a **child** of `MarketingEvent` inside the same entity file
(entity-file rule: one file owns its primary model plus its children), so the count is 5 entity
folders / 6 classes — **one** over the guidance, for a stated reason, with **no new master table**.

**Ruling on the console (no stored rollup).** "Campaign ROI, cost per lead, and pipeline generated
by campaign" is a **derived** fact. Storing it next to its sources is a field that drifts. It is
computed on `marketing_attribution_console` from `CampaignAttribution` + `AttributionTouchpoint` +
`crm.Campaign`.

**Ruling on `AttributionTouchpoint` vs `CampaignAttribution` (why two classes, not one).** The
touch ledger is the *raw interaction*; the credit is *a function of the model AND the whole
journey*. A journey with four touches needs four ledger rows but a different credit for each
model. Collapsing them would force the credit to be typed into the touch, which destroys the
ability to evaluate two models side by side (the thing every surveyed product does). Hence: ledger
rows are data, credit rows are per-(touchpoint × model).

---

## 1. Models — Every Field, Every Choice, Every Constraint

All models reside in `apps/sales/models/MarketingAlignment/`.
Base: `apps.sales.models._base.TenantNumbered` (gives `tenant` FK `core.Tenant` with
`related_name="+"`, `number = CharField(max_length=20, editable=False)`, `created_at`, `updated_at`)
and `apps.sales.models._base.TenantOwned` for the non-numbered child.

### 1.1 `AttributionTouchpoint` (`AttributionTouchpoints.py`) — `NUMBER_PREFIX = "ATB"`

```python
TOUCH_CHANNEL_CHOICES = [
    ("email", "Email"),
    ("paid_search", "Paid Search"),
    ("organic_search", "Organic Search"),
    ("social", "Social Media"),
    ("display", "Display / Banner"),
    ("webinar", "Webinar"),
    ("event", "Event"),
    ("referral", "Referral / Partner"),
    ("direct_mail", "Direct Mail"),
    ("website", "Website / Organic Visit"),
    ("other", "Other"),
]

TOUCH_TYPE_CHOICES = [
    ("impression", "Ad Impression"),
    ("click", "Click / Visit"),
    ("email_open", "Email Open"),
    ("email_click", "Email Click"),
    ("content_download", "Content Download"),
    ("event_registration", "Event Registration"),
    ("event_attendance", "Event Attendance"),
    ("meeting", "Sales Meeting"),
    ("trial_start", "Trial Start"),
    ("demo_request", "Demo Request"),
]

TOUCH_POSITION_CHOICES = [
    ("first", "First Touch"),
    ("middle", "Middle Touch"),
    ("last", "Last Touch"),
]
```

| Field | Type | Attributes & Clean Guards |
|---|---|---|
| `campaign` | `ForeignKey("crm.Campaign", SET_NULL, null=True, blank=True, related_name="sales_attribution_touchpoints")` | Source campaign; the ROI rollup groups on it. Nullable so a non-campaign touch (organic search) is still recordable. |
| `lead` | `ForeignKey("crm.Lead", SET_NULL, null=True, blank=True, related_name="sales_attribution_touchpoints")` | The identity the journey is stitched to. |
| `opportunity` | `ForeignKey("crm.Opportunity", SET_NULL, null=True, blank=True, related_name="sales_attribution_touchpoints")` | Conversion endpoint, when the touch belongs to a known deal. |
| `channel` | `CharField(30, choices=TOUCH_CHANNEL_CHOICES, default="email", db_index=True)` | Marketing channel. |
| `touch_type` | `CharField(30, choices=TOUCH_TYPE_CHOICES, default="click", db_index=True)` | The interaction itself. |
| `touch_date` | `DateField(db_index=True)` | When the interaction happened. |
| `touch_position` | `CharField(12, choices=TOUCH_POSITION_CHOICES, default="middle", db_index=True)` | Journey position — first/middle/last — so first-touch and last-touch are *derived from data*, never typed twice. |
| `cost` | `DecimalField(12, 2, default=Decimal("0.00"), validators=[MinValueValidator(0)])` | Cost of this interaction (media spend, event cost allocation). |
| `engagement_value` | `DecimalField(12, 2, default=Decimal("0.00"), validators=[MinValueValidator(0)])` | Pipeline/revenue value present at the moment of the touch. |
| `currency` | `ForeignKey("accounting.Currency", SET_NULL, null=True, blank=True, related_name="sales_attribution_touchpoints")` | Denomination for `cost` / `engagement_value`. |
| `source_reference` | `CharField(255, blank=True)` | UTM string or external interaction id. |
| `notes` | `TextField(blank=True)` | Free text. |

**Properties:** `is_first_touch` → `self.touch_position == "first"`; `is_last_touch` →
`self.touch_position == "last"`; `attributed_revenue` → `sum(a.attributed_revenue for a in self.attributions.all())`.

**Clean guards:** `campaign`, `lead`, `opportunity`, `currency` must belong to the same tenant as
`self.tenant` (a cross-tenant FK is rejected with a `ValidationError`).

**Meta:** `ordering = ["-touch_date", "-created_at"]`; indexes
`(tenant, touch_date)`, `(tenant, campaign, touch_date)`, `(tenant, lead)`, `(tenant, opportunity)`.
No `unique_together` on `(tenant, number)` is needed — `TenantNumbered` subclasses in this app
carry their own unique constraint where the number must be unique; **this model adds
`models.UniqueConstraint(fields=["tenant", "number"], name="sales_atb_tenant_number_uniq")`**.

**`__str__`** → `f"{self.number} · {self.get_channel_display()} · {self.touch_date}"`

### 1.2 `CampaignAttribution` (`CampaignAttributions.py`) — `NUMBER_PREFIX = "ATR"`

```python
ATTRIBUTION_MODEL_CHOICES = [
    ("first_touch", "First Touch"),
    ("last_touch", "Last Touch"),
    ("linear", "Linear (Multi-Touch)"),
    ("time_decay", "Time Decay (Multi-Touch)"),
    ("position_based", "Position-Based / U-Shaped"),
    ("custom", "Custom Model"),
]

ATTRIBUTION_STATUS_CHOICES = [
    ("draft", "Draft"),
    ("computed", "Computed"),
    ("approved", "Approved"),
    ("rejected", "Rejected"),
]
```

| Field | Type | Attributes & Clean Guards |
|---|---|---|
| `touchpoint` | `ForeignKey("sales.AttributionTouchpoint", CASCADE, related_name="attributions")` | The touch this credit belongs to. Required. |
| `attribution_model` | `CharField(30, choices=ATTRIBUTION_MODEL_CHOICES, default="first_touch", db_index=True)` | Which model produced this credit. |
| `credit_pct` | `DecimalField(5, 2, default=Decimal("0.00"), validators=[MinValueValidator(0), MaxValueValidator(100)])` | Share of conversion credit, 0–100. The **custom** escape hatch writes an arbitrary value here. |
| `attributed_revenue` | `DecimalField(12, 2, default=Decimal("0.00"), validators=[MinValueValidator(0)])` | Revenue credited to this touch under this model. |
| `attributed_cost` | `DecimalField(12, 2, default=Decimal("0.00"), validators=[MinValueValidator(0)])` | Cost credited to this touch under this model. |
| `status` | `CharField(15, choices=ATTRIBUTION_STATUS_CHOICES, default="draft", db_index=True)` | Draft → Computed → Approved / Rejected. |
| `computed_on` | `DateField(default=timezone.localdate)` | When the credit was computed. |
| `computed_by` | `ForeignKey(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, related_name="sales_campaign_attributions")` | Who computed it. |
| `notes` | `TextField(blank=True)` | Rationale for a custom credit. |

**Properties:** `campaign` → `self.touchpoint.campaign`; `lead` → `self.touchpoint.lead`;
`opportunity` → `self.touchpoint.opportunity`; `roi_pct` → `None` when `attributed_cost` is 0,
else `(attributed_revenue - attributed_cost) / attributed_cost * 100`.

**Clean guards:** `computed_by` same tenant; `credit_pct` ≤ 100; `attributed_revenue`/`attributed_cost` ≥ 0.

**Meta:** `ordering = ["-computed_on", "-created_at"]`;
`UniqueConstraint(fields=["tenant", "touchpoint", "attribution_model"], name="sales_atr_tp_model_uniq")`
— one credit per touch per model, which is what makes two models comparable side by side;
indexes `(tenant, status)`, `(tenant, attribution_model)`.

**`__str__`** → `f"{self.number} · {self.get_attribution_model_display()} · {self.credit_pct}%"`

### 1.3 `MqlHandoff` (`MqlHandoffs.py`) — `NUMBER_PREFIX = "MQL"`

```python
HANDOFF_STATUS_CHOICES = [
    ("pending", "Pending Review"),
    ("accepted", "Accepted by Sales"),
    ("rejected", "Rejected by Sales"),
    ("expired", "SLA Expired"),
    ("converted", "Converted to Opportunity"),
]

HANDOFF_SOURCE_CHOICES = [
    ("campaign", "Campaign"),
    ("content", "Content Download"),
    ("event", "Event / Webinar"),
    ("webinar", "Webinar"),
    ("referral", "Referral"),
    ("inbound", "Inbound Request"),
    ("partner", "Partner"),
    ("other", "Other"),
]
```

| Field | Type | Attributes & Clean Guards |
|---|---|---|
| `lead` | `ForeignKey("crm.Lead", CASCADE, related_name="sales_mql_handoffs")` | The MQL being handed to sales. Required. |
| `campaign` | `ForeignKey("crm.Campaign", SET_NULL, null=True, blank=True, related_name="sales_mql_handoffs")` | Originating campaign. |
| `account` | `ForeignKey("core.Party", SET_NULL, null=True, blank=True, related_name="sales_mql_handoffs")` | Target customer account. |
| `owner` | `ForeignKey(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, related_name="sales_mql_handoff_owners")` | Marketing owner of the handoff. |
| `assigned_to` | `ForeignKey(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, related_name="sales_mql_handoff_assignees")` | The sales rep who must respond. |
| `opportunity` | `ForeignKey("crm.Opportunity", SET_NULL, null=True, blank=True, related_name="sales_mql_handoffs")` | The deal this handoff produced. |
| `status` | `CharField(20, choices=HANDOFF_STATUS_CHOICES, default="pending", db_index=True)` | Lifecycle status. |
| `source_kind` | `CharField(20, choices=HANDOFF_SOURCE_CHOICES, default="campaign")` | What produced the MQL. |
| `handoff_at` | `DateTimeField(default=timezone.now, db_index=True)` | When the handoff was raised. |
| `sla_due_at` | `DateTimeField(db_index=True)` | Response deadline. Required — SLA compliance is a NavERP bullet, so the deadline is not optional. |
| `responded_at` | `DateTimeField(null=True, blank=True)` | Stamped by `save()` on the first transition to `accepted`/`rejected`/`converted`; **excluded from the form**. |
| `acceptance_reason` | `CharField(255, blank=True)` | Why sales accepted — the acceptance-rate evidence. |
| `rejection_reason` | `CharField(255, blank=True)` | Why sales rejected. |
| `lead_score` | `PositiveSmallIntegerField(default=0, validators=[MaxValueValidator(100)])` | Snapshot of the lead score at handoff time. |
| `estimated_value` | `DecimalField(12, 2, default=Decimal("0.00"), validators=[MinValueValidator(0)])` | Snapshot of the opportunity value. |
| `currency` | `ForeignKey("accounting.Currency", SET_NULL, null=True, blank=True, related_name="sales_mql_handoffs")` | Denomination for `estimated_value`. |
| `notes` | `TextField(blank=True)` | Free text. |

**Properties:** `is_responded` → `self.responded_at is not None`;
`is_sla_breached` → `responded_at > sla_due_at` when responded, else `timezone.now() > sla_due_at`
(an unanswered, overdue handoff is breached too);
`response_hours` → `round((responded_at - handoff_at).total_seconds() / 3600, 2)` or `None`.

**`save()`:** stamps `responded_at = timezone.now()` on the first transition into
`accepted` / `rejected` / `converted`; clears it if the row is moved back to `pending`.

**Clean guards:** `campaign`, `account`, `owner`, `assigned_to`, `opportunity`, `currency` same
tenant; `sla_due_at` must not be before `handoff_at`; a `rejected` row must carry a
`rejection_reason`.

**Meta:** `ordering = ["-handoff_at", "-created_at"]`; indexes `(tenant, status)`,
`(tenant, sla_due_at)`, `(tenant, lead)`, `(tenant, campaign)`;
`UniqueConstraint(fields=["tenant", "number"], name="sales_mql_tenant_number_uniq")`.

**`__str__`** → `f"{self.number} · {self.lead.name if self.lead_id else 'Lead'} · {self.get_status_display()}"`

### 1.4 `ContentEngagement` (`ContentEngagements.py`) — `NUMBER_PREFIX = "CNG"`

```python
ENGAGEMENT_TYPE_CHOICES = [
    ("view", "Content View"),
    ("download", "Content Download"),
    ("share", "Share / Forward"),
    ("comment", "Comment / Feedback"),
    ("attend", "Event / Session Attendance"),
    ("complete", "Full Consumption"),
]

ENGAGEMENT_CHANNEL_CHOICES = [
    ("email", "Email"),
    ("web", "Website"),
    ("search", "Search"),
    ("social", "Social Media"),
    ("sales", "Sales Rep Shared"),
    ("event", "Event"),
    ("partner", "Partner"),
    ("other", "Other"),
]
```

| Field | Type | Attributes & Clean Guards |
|---|---|---|
| `content` | `ForeignKey("sales.EnablementContent", CASCADE, related_name="sales_content_engagements")` | The content item engaged with (Sales 8.9 master). Required. |
| `account` | `ForeignKey("core.Party", SET_NULL, null=True, blank=True, related_name="sales_content_engagements")` | Which account engaged. |
| `lead` | `ForeignKey("crm.Lead", SET_NULL, null=True, blank=True, related_name="sales_content_engagements")` | Which lead engaged. |
| `campaign` | `ForeignKey("crm.Campaign", SET_NULL, null=True, blank=True, related_name="sales_content_engagements")` | Which campaign drove the engagement. |
| `engagement_type` | `CharField(20, choices=ENGAGEMENT_TYPE_CHOICES, default="view", db_index=True)` | The interaction — download tracking lives here. |
| `engagement_channel` | `CharField(20, choices=ENGAGEMENT_CHANNEL_CHOICES, default="web")` | Where the engagement came through. |
| `engagement_score` | `PositiveSmallIntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])` | Behavioural score, 0–100. |
| `revenue_attributed` | `DecimalField(12, 2, default=Decimal("0.00"), validators=[MinValueValidator(0)])` | **Content-to-revenue mapping** — revenue credited to this engagement. |
| `currency` | `ForeignKey("accounting.Currency", SET_NULL, null=True, blank=True, related_name="sales_content_engagements")` | Denomination for `revenue_attributed`. |
| `engaged_at` | `DateTimeField(default=timezone.now, db_index=True)` | When it happened. |
| `notes` | `TextField(blank=True)` | Free text. |

**Properties:** `is_high_intent` → `self.engagement_score >= 70`;
`is_download` → `self.engagement_type == "download"`.

**Clean guards:** `content`, `account`, `lead`, `campaign`, `currency` same tenant.

**Meta:** `ordering = ["-engaged_at", "-created_at"]`; indexes `(tenant, content, "-engaged_at")`,
`(tenant, account)`, `(tenant, engagement_type)`;
`UniqueConstraint(fields=["tenant", "number"], name="sales_cng_tenant_number_uniq")`.

**`__str__`** → `f"{self.number} · {self.content.title if self.content_id else 'Content'} · {self.get_engagement_type_display()}"`

### 1.5 `MarketingEvent` (`MarketingEvents.py`) — `NUMBER_PREFIX = "EVT"`

```python
EVENT_TYPE_CHOICES = [
    ("webinar", "Webinar"),
    ("conference", "Conference"),
    ("workshop", "Workshop"),
    ("trade_show", "Trade Show"),
    ("roadshow", "Roadshow"),
    ("roundtable", "Virtual Roundtable"),
    ("user_group", "User Group"),
    ("other", "Other"),
]

EVENT_STATUS_CHOICES = [
    ("planned", "Planned"),
    ("published", "Published / Open for Registration"),
    ("ongoing", "Ongoing"),
    ("completed", "Completed"),
    ("cancelled", "Cancelled"),
]
```

| Field | Type | Attributes & Clean Guards |
|---|---|---|
| `name` | `CharField(200)` | Event name. |
| `event_type` | `CharField(20, choices=EVENT_TYPE_CHOICES, default="webinar", db_index=True)` | Event kind. |
| `status` | `CharField(20, choices=EVENT_STATUS_CHOICES, default="planned", db_index=True)` | Lifecycle status. |
| `start_at` | `DateTimeField(db_index=True)` | Start. |
| `end_at` | `DateTimeField(null=True, blank=True)` | End. |
| `timezone_name` | `CharField(64, default="UTC")` | IANA zone the event runs in. |
| `venue` | `CharField(255, blank=True)` | Physical venue. |
| `virtual_url` | `URLField(max_length=500, blank=True)` | Streaming / join link. |
| `capacity` | `PositiveIntegerField(default=0)` | 0 = unlimited. |
| `budget` | `DecimalField(12, 2, default=Decimal("0.00"), validators=[MinValueValidator(0)])` | Event cost — the denominator of cost-per-registrant. |
| `currency` | `ForeignKey("accounting.Currency", SET_NULL, null=True, blank=True, related_name="sales_marketing_events")` | Denomination for `budget`. |
| `owner` | `ForeignKey(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, related_name="sales_marketing_events")` | Event owner. |
| `campaign` | `ForeignKey("crm.Campaign", SET_NULL, null=True, blank=True, related_name="sales_marketing_events")` | The campaign that promoted it. |
| `description` | `TextField(blank=True)` | Agenda / description. |

**Properties:** `registered_count` → `self.registrations.count()`;
`attended_count` → `self.registrations.filter(registration_status="attended").count()`;
`show_up_rate_pct` → `round(attended / registered * 100, 1)` or `None` when nothing registered;
`revenue_per_registrant` → sum of `revenue_attributed` on this event's registrations ÷
`registered_count`, or `None`.

**Clean guards:** `end_at` must not be before `start_at`; `owner`, `campaign`, `currency` same tenant.

**Meta:** `ordering = ["-start_at", "-created_at"]`; indexes `(tenant, status)`,
`(tenant, event_type)`, `(tenant, start_at)`;
`UniqueConstraint(fields=["tenant", "number"], name="sales_evt_tenant_number_uniq")`.

**`__str__`** → `f"{self.number} · {self.name}"`

### 1.6 `EventRegistration` (`MarketingEvents.py`, child of `MarketingEvent`) — **not numbered**

Base: `apps.sales.models._base.TenantOwned` (tenant FK + `created_at` + `updated_at`). It is an
attendance/membership row, so it carries **no** human-readable number — the same ruling as
`crm.CampaignMember`.

```python
REGISTRATION_STATUS_CHOICES = [
    ("registered", "Registered"),
    ("confirmed", "Confirmed"),
    ("attended", "Attended"),
    ("no_show", "No-Show"),
    ("cancelled", "Cancelled"),
    ("waitlisted", "Waitlisted"),
]

FOLLOWUP_STATUS_CHOICES = [
    ("pending", "Pending"),
    ("sent", "Follow-Up Sent"),
    ("meeting_booked", "Meeting Booked"),
    ("opportunity_created", "Opportunity Created"),
    ("no_action", "No Action"),
]

REGISTRATION_SOURCE_CHOICES = [
    ("campaign", "Campaign"),
    ("email", "Email Invitation"),
    ("organic", "Organic / Search"),
    ("partner", "Partner"),
    ("referral", "Referral"),
    ("sales_rep", "Sales Rep"),
    ("other", "Other"),
]
```

| Field | Type | Attributes & Clean Guards |
|---|---|---|
| `event` | `ForeignKey("sales.MarketingEvent", CASCADE, related_name="registrations")` | The event. Required. |
| `lead` | `ForeignKey("crm.Lead", SET_NULL, null=True, blank=True, related_name="sales_event_registrations")` | The registrant as a lead. |
| `account` | `ForeignKey("core.Party", SET_NULL, null=True, blank=True, related_name="sales_event_registrations")` | The registrant as an account. |
| `campaign` | `ForeignKey("crm.Campaign", SET_NULL, null=True, blank=True, related_name="sales_event_registrations")` | **UTM capture on the registrant** — which campaign filled the room. |
| `registrant_name` | `CharField(200)` | Display snapshot so the row survives a null/changed source record. |
| `registrant_email` | `EmailField(blank=True)` | Contact email. |
| `registration_status` | `CharField(20, choices=REGISTRATION_STATUS_CHOICES, default="registered", db_index=True)` | Registration / attendance state. |
| `source_channel` | `CharField(30, choices=REGISTRATION_SOURCE_CHOICES, default="campaign")` | How they got there. |
| `registered_at` | `DateTimeField(default=timezone.now, db_index=True)` | Registration timestamp. |
| `attended_at` | `DateTimeField(null=True, blank=True)` | Stamped by `save()` on the first transition to `attended`; **excluded from the form**. |
| `followup_status` | `CharField(20, choices=FOLLOWUP_STATUS_CHOICES, default="pending", db_index=True)` | **Post-event follow-up automation state.** |
| `followup_notes` | `TextField(blank=True)` | What the follow-up did. |
| `engagement_score` | `PositiveSmallIntegerField(default=0, validators=[MaxValueValidator(100)])` | Behavioural score (attendance, watch time, polls → Hot/Warm/Nurture style). |
| `revenue_attributed` | `DecimalField(12, 2, default=Decimal("0.00"), validators=[MinValueValidator(0)])` | Revenue credited to the registrant. |
| `opportunity` | `ForeignKey("crm.Opportunity", SET_NULL, null=True, blank=True, related_name="sales_event_registrations")` | The deal this attendee became. |

**`save()`:** stamps `attended_at = timezone.now()` on the first transition into `attended`;
clears it if the row moves off `attended`.

**Clean guards:** `event`, `lead`, `account`, `campaign`, `opportunity` same tenant.

**Meta:** `ordering = ["-registered_at", "-created_at"]`; indexes `(tenant, event)`,
`(tenant, registration_status)`, `(tenant, followup_status)`.

**`__str__`** → `f"{self.registrant_name} · {self.get_registration_status_display()}"`

---

## 2. Forms — `Meta.fields` and exclusions

All forms live in `apps/sales/forms/MarketingAlignment/`, extend
`apps.sales.forms._common.TenantUniqueMixin` + `apps.core.forms.TenantModelForm`, and scope every
FK queryset to `self.tenant` in `__init__`. Every form calls
`apps.sales.forms._common._reject_foreign(self, cleaned_data, [...])` in `clean()`.

### 2.1 `AttributionTouchpointForm`
`Meta.fields`:
`["campaign", "lead", "opportunity", "channel", "touch_type", "touch_date", "touch_position", "cost", "engagement_value", "currency", "source_reference", "notes"]`
**Excluded:** `tenant`, `number` (auto), `created_at`, `updated_at`.
**FK querysets:** `campaign` → `Campaign.objects.filter(tenant=…)`; `lead` → `Lead.objects.filter(tenant=…)`;
`opportunity` → `Opportunity.objects.filter(tenant=…)`; `currency` → `Currency.objects.all()`.
**Widgets:** `form-select` on the FKs and the three choice fields; `form-input` on text/date/decimal;
`form-textarea` on `notes`.

### 2.2 `CampaignAttributionForm`
`Meta.fields`:
`["touchpoint", "attribution_model", "credit_pct", "attributed_revenue", "attributed_cost", "status", "computed_on", "computed_by", "notes"]`
**Excluded:** `tenant`, `number`, `created_at`, `updated_at`.
**FK querysets:** `touchpoint` → `AttributionTouchpoint.objects.filter(tenant=…).select_related("campaign", "lead", "opportunity")`;
`computed_by` → `User.objects.filter(tenant=…)`.
**Clean:** `credit_pct` ≤ 100 (model validator), and for `attribution_model == "custom"` a
`credit_pct` of `0` is rejected with *"A custom attribution model must carry an explicit credit percentage."* — the
custom escape hatch is meaningless without a number.

### 2.3 `MqlHandoffForm`
`Meta.fields`:
`["lead", "campaign", "account", "owner", "assigned_to", "opportunity", "status", "source_kind", "handoff_at", "sla_due_at", "acceptance_reason", "rejection_reason", "lead_score", "estimated_value", "currency", "notes"]`
**Excluded:** `tenant`, `number`, **`responded_at`** (system-stamped), `created_at`, `updated_at`.
**FK querysets:** `lead` → `Lead.objects.filter(tenant=…)`; `campaign` → `Campaign.objects.filter(tenant=…)`;
`account` → `Party.objects.filter(tenant=…, roles__role="customer").distinct()`; `owner` / `assigned_to` →
`User.objects.filter(tenant=…)`; `opportunity` → `Opportunity.objects.filter(tenant=…)`; `currency` → `Currency.objects.all()`.
**Clean:** a `rejected` status requires `rejection_reason`; `sla_due_at` must be ≥ `handoff_at`.

### 2.4 `ContentEngagementForm`
`Meta.fields`:
`["content", "account", "lead", "campaign", "engagement_type", "engagement_channel", "engagement_score", "revenue_attributed", "currency", "engaged_at", "notes"]`
**Excluded:** `tenant`, `number`, `created_at`, `updated_at`.
**FK querysets:** `content` → `EnablementContent.objects.filter(tenant=…, is_active=True)`; `account` →
`Party.objects.filter(tenant=…, roles__role="customer").distinct()`; `lead` → `Lead.objects.filter(tenant=…)`;
`campaign` → `Campaign.objects.filter(tenant=…)`; `currency` → `Currency.objects.all()`.

### 2.5 `MarketingEventForm`
`Meta.fields`:
`["name", "event_type", "status", "start_at", "end_at", "timezone_name", "venue", "virtual_url", "capacity", "budget", "currency", "owner", "campaign", "description"]`
**Excluded:** `tenant`, `number`, `created_at`, `updated_at`.
**FK querysets:** `owner` → `User.objects.filter(tenant=…)`; `campaign` → `Campaign.objects.filter(tenant=…)`;
`currency` → `Currency.objects.all()`.

### 2.6 `EventRegistrationForm`
`Meta.fields`:
`["event", "lead", "account", "campaign", "registrant_name", "registrant_email", "registration_status", "source_channel", "registered_at", "followup_status", "followup_notes", "engagement_score", "revenue_attributed", "opportunity"]`
**Excluded:** `tenant`, **`attended_at`** (system-stamped), `created_at`, `updated_at`.
**FK querysets:** `event` → `MarketingEvent.objects.filter(tenant=…)`; `lead` → `Lead.objects.filter(tenant=…)`;
`account` → `Party.objects.filter(tenant=…, roles__role="customer").distinct()`; `campaign` →
`Campaign.objects.filter(tenant=…)`; `opportunity` → `Opportunity.objects.filter(tenant=…)`.

---

## 3. URLs — `apps/sales/urls/MarketingAlignment/`

`app_name = "sales"` lives in `apps/sales/urls/__init__.py`. **Django is first-match-wins**, so
every literal route is listed before its `<int:pk>` siblings.

| Name | Path | View |
|---|---|---|
| `marketing_attribution_console` | `marketing-alignment/console/` | `marketing_attribution_console` |
| `attribution_touchpoint_list` | `marketing-alignment/touchpoints/` | `attribution_touchpoint_list` |
| `attribution_touchpoint_create` | `marketing-alignment/touchpoints/create/` | `attribution_touchpoint_create` |
| `attribution_touchpoint_detail` | `marketing-alignment/touchpoints/<int:pk>/` | `attribution_touchpoint_detail` |
| `attribution_touchpoint_edit` | `marketing-alignment/touchpoints/<int:pk>/edit/` | `attribution_touchpoint_edit` |
| `attribution_touchpoint_delete` | `marketing-alignment/touchpoints/<int:pk>/delete/` | `attribution_touchpoint_delete` |
| `campaign_attribution_list` | `marketing-alignment/attributions/` | `campaign_attribution_list` |
| `campaign_attribution_create` | `marketing-alignment/attributions/create/` | `campaign_attribution_create` |
| `campaign_attribution_detail` | `marketing-alignment/attributions/<int:pk>/` | `campaign_attribution_detail` |
| `campaign_attribution_edit` | `marketing-alignment/attributions/<int:pk>/edit/` | `campaign_attribution_edit` |
| `campaign_attribution_delete` | `marketing-alignment/attributions/<int:pk>/delete/` | `campaign_attribution_delete` |
| `mql_handoff_list` | `marketing-alignment/mql-handoffs/` | `mql_handoff_list` |
| `mql_handoff_create` | `marketing-alignment/mql-handoffs/create/` | `mql_handoff_create` |
| `mql_handoff_detail` | `marketing-alignment/mql-handoffs/<int:pk>/` | `mql_handoff_detail` |
| `mql_handoff_edit` | `marketing-alignment/mql-handoffs/<int:pk>/edit/` | `mql_handoff_edit` |
| `mql_handoff_delete` | `marketing-alignment/mql-handoffs/<int:pk>/delete/` | `mql_handoff_delete` |
| `content_engagement_list` | `marketing-alignment/content-engagements/` | `content_engagement_list` |
| `content_engagement_create` | `marketing-alignment/content-engagements/create/` | `content_engagement_create` |
| `content_engagement_detail` | `marketing-alignment/content-engagements/<int:pk>/` | `content_engagement_detail` |
| `content_engagement_edit` | `marketing-alignment/content-engagements/<int:pk>/edit/` | `content_engagement_edit` |
| `content_engagement_delete` | `marketing-alignment/content-engagements/<int:pk>/delete/` | `content_engagement_delete` |
| `marketing_event_list` | `marketing-alignment/events/` | `marketing_event_list` |
| `marketing_event_create` | `marketing-alignment/events/create/` | `marketing_event_create` |
| `marketing_event_detail` | `marketing-alignment/events/<int:pk>/` | `marketing_event_detail` |
| `marketing_event_edit` | `marketing-alignment/events/<int:pk>/edit/` | `marketing_event_edit` |
| `marketing_event_delete` | `marketing-alignment/events/<int:pk>/delete/` | `marketing_event_delete` |
| `marketing_event_registrations` | `marketing-alignment/events/<int:pk>/registrations/` | `marketing_event_registrations` |
| `marketing_event_registration_create` | `marketing-alignment/events/<int:pk>/registrations/create/` | `marketing_event_registration_create` |

**Prefix collision check:** `marketing-alignment/` is verified free against every path already
mounted under `sales:` (the `sales:` root has no `marketing-alignment` segment).

---

## 4. Views — every context key pinned

All views are function-based, `@login_required`, tenant-scoped
(`Model.objects.filter(tenant=request.tenant)` — never `.all()`), paginated with
`Paginator(qs, 15)`, and write an audit row through
`apps.core.utils.write_audit_log(request.user, obj, <action>, <message>, tenant=request.tenant)`.
Deletes are `@require_POST` + `@tenant_admin_required` and redirect to the list.

### 4.1 `attribution_touchpoint_list` → `templates/sales/marketingalignment/attributiontouchpoint/list.html`
| Context key | Value |
|---|---|
| `page_obj` | the paginator page |
| `touchpoints` | `page_obj.object_list` |
| `channel_choices` | `TOUCH_CHANNEL_CHOICES` |
| `touch_type_choices` | `TOUCH_TYPE_CHOICES` |
| `position_choices` | `TOUCH_POSITION_CHOICES` |
| `campaigns` | `Campaign.objects.filter(tenant=request.tenant).order_by("name")` |
| `leads` | `Lead.objects.filter(tenant=request.tenant).order_by("name")` |
| `active_filters` | `{"q", "channel", "touch_type", "position", "campaign", "lead"}` — every value is the raw `request.GET` string |
| `stats` | `{"total_count", "total_cost", "total_engagement_value", "first_touch_count", "last_touch_count"}` |

> **Why `attributed_revenue` is NOT in the touchpoint list stats.** The credited revenue lives on
> `CampaignAttribution` (entity 2), and entity 1 is built **before** entity 2. Importing
> `CampaignAttribution` into the touchpoint view would forward-reference a module that does not
> exist yet and break the tree at that commit. The credited revenue for a single touch is still
> available on the detail page through the **model property** `obj.attributed_revenue`, which
> resolves the reverse accessor `self.attributions` lazily and therefore needs no import; and the
> campaign-level credited-revenue rollup lives on the console, which is built last. The list stat
> `total_engagement_value` is the touchpoint's own native field and is never a proxy for it.

**Filters:** `q` → `Q(campaign__name__icontains) | Q(lead__name__icontains) | Q(opportunity__name__icontains) | Q(source_reference__icontains) | Q(number__icontains)`;
`channel` → exact; `touch_type` → exact; `position` → exact; `campaign` → `campaign_id=int(v)` when `v.isdigit()`;
`lead` → `lead_id=int(v)` when `v.isdigit()`. All applied **before** pagination.

### 4.2 `attribution_touchpoint_detail` → `.../attributiontouchpoint/detail.html`
`{"obj": <AttributionTouchpoint>, "touchpoint": <same object>, "attributions": <list of CampaignAttribution for this touch>}`

### 4.3 `attribution_touchpoint_create` / `_edit` → `.../attributiontouchpoint/form.html`
`{"form": <form>, "obj": <None on create / the object on edit>, "is_edit": <bool>}` — the template
branches on `is_edit`.

### 4.4 `campaign_attribution_list` → `.../campaignattribution/list.html`
| Context key | Value |
|---|---|
| `page_obj` | the paginator page |
| `attributions` | `page_obj.object_list` |
| `model_choices` | `ATTRIBUTION_MODEL_CHOICES` |
| `status_choices` | `ATTRIBUTION_STATUS_CHOICES` |
| `campaigns` | `Campaign.objects.filter(tenant=request.tenant).order_by("name")` |
| `active_filters` | `{"q", "attribution_model", "status", "campaign"}` |
| `stats` | `{"total_count", "approved_count", "total_attributed_revenue", "total_attributed_cost", "total_credit_pct"}` |

**Filters:** `q` → `Q(touchpoint__campaign__name__icontains) | Q(touchpoint__lead__name__icontains) | Q(number__icontains)`;
`attribution_model` → exact; `status` → exact; `campaign` → `touchpoint__campaign_id=int(v)`.

### 4.5 `campaign_attribution_detail` → `.../campaignattribution/detail.html`
`{"obj": <CampaignAttribution>, "attribution": <same object>}`

### 4.6 `campaign_attribution_create` / `_edit` → `.../campaignattribution/form.html`
`{"form", "obj", "is_edit"}`

### 4.7 `mql_handoff_list` → `.../mqlhandoff/list.html`
| Context key | Value |
|---|---|
| `page_obj` | the paginator page |
| `handoffs` | `page_obj.object_list` |
| `status_choices` | `HANDOFF_STATUS_CHOICES` |
| `source_choices` | `HANDOFF_SOURCE_CHOICES` |
| `campaigns` | `Campaign.objects.filter(tenant=request.tenant).order_by("name")` |
| `owners` | `User.objects.filter(tenant=request.tenant).order_by("username")` |
| `active_filters` | `{"q", "status", "source_kind", "campaign", "owner"}` |
| `stats` | `{"total_count", "pending_count", "accepted_count", "rejected_count", "expired_count", "converted_count", "sla_breach_count", "acceptance_rate_pct", "avg_response_hours"}` |

**Filters:** `q` → `Q(lead__name__icontains) | Q(lead__number__icontains) | Q(account__name__icontains) | Q(number__icontains)`;
`status` → exact; `source_kind` → exact; `campaign` → `campaign_id=int(v)`; `owner` → `owner_id=int(v)`.

### 4.8 `mql_handoff_detail` → `.../mqlhandoff/detail.html`
`{"obj": <MqlHandoff>, "handoff": <same object>}`

### 4.9 `mql_handoff_create` / `_edit` → `.../mqlhandoff/form.html`
`{"form", "obj", "is_edit"}`

### 4.10 `content_engagement_list` → `.../contentengagement/list.html`
| Context key | Value |
|---|---|
| `page_obj` | the paginator page |
| `engagements` | `page_obj.object_list` |
| `engagement_type_choices` | `ENGAGEMENT_TYPE_CHOICES` |
| `channel_choices` | `ENGAGEMENT_CHANNEL_CHOICES` |
| `contents` | `EnablementContent.objects.filter(tenant=request.tenant, is_active=True).order_by("title")` |
| `accounts` | `Party.objects.filter(tenant=request.tenant, roles__role="customer").distinct().order_by("name")` |
| `campaigns` | `Campaign.objects.filter(tenant=request.tenant).order_by("name")` |
| `active_filters` | `{"q", "engagement_type", "engagement_channel", "content", "account", "campaign"}` |
| `stats` | `{"total_count", "download_count", "total_revenue_attributed", "avg_engagement_score", "engaged_account_count"}` |

**Filters:** `q` → `Q(content__title__icontains) | Q(account__name__icontains) | Q(lead__name__icontains) | Q(number__icontains)`;
`engagement_type` → exact; `engagement_channel` → exact; `content` → `content_id=int(v)`;
`account` → `account_id=int(v)`; `campaign` → `campaign_id=int(v)`.

### 4.11 `content_engagement_detail` → `.../contentengagement/detail.html`
`{"obj": <ContentEngagement>, "engagement": <same object>}`

### 4.12 `content_engagement_create` / `_edit` → `.../contentengagement/form.html`
`{"form", "obj", "is_edit"}`

### 4.13 `marketing_event_list` → `.../marketingevent/list.html`
| Context key | Value |
|---|---|
| `page_obj` | the paginator page |
| `events` | `page_obj.object_list` |
| `event_type_choices` | `EVENT_TYPE_CHOICES` |
| `status_choices` | `EVENT_STATUS_CHOICES` |
| `owners` | `User.objects.filter(tenant=request.tenant).order_by("username")` |
| `campaigns` | `Campaign.objects.filter(tenant=request.tenant).order_by("name")` |
| `active_filters` | `{"q", "event_type", "status", "owner", "campaign"}` |
| `stats` | `{"total_count", "published_count", "upcoming_count", "total_registrations", "total_attendance", "avg_show_up_pct"}` |

**Filters:** `q` → `Q(name__icontains) | Q(venue__icontains) | Q(number__icontains)`;
`event_type` → exact; `status` → exact; `owner` → `owner_id=int(v)`; `campaign` → `campaign_id=int(v)`.

### 4.14 `marketing_event_detail` → `.../marketingevent/detail.html`
`{"obj": <MarketingEvent>, "event": <same object>, "registrations": <list of EventRegistration for the event>}`

### 4.15 `marketing_event_create` / `_edit` → `.../marketingevent/form.html`
`{"form", "obj", "is_edit"}`

### 4.16 `marketing_event_registrations` → `.../marketingevent/registrations.html`
`{"event": <MarketingEvent>, "registrations": <list>, "page_obj": <page>}` — paginated at 20.
Filtered by `registration_status` and `followup_status` from `request.GET`.

### 4.17 `marketing_event_registration_create` → `.../marketingevent/form.html`? **No** — registrations
get their own page `templates/sales/marketingalignment/marketingevent/registration_form.html`
(a second form page inside the entity folder, sibling of `list/detail/form.html`).
Context: `{"form": <EventRegistrationForm>, "event": <MarketingEvent>, "obj": <None>, "is_edit": False}`

### 4.18 `marketing_attribution_console` → `templates/sales/marketingalignment/attribution_console.html`
| Context key | Value |
|---|---|
| `stats` | `{"total_touchpoints", "total_spend", "total_attributed_revenue", "blended_roi_pct", "avg_cost_per_lead", "mql_total", "mql_accepted", "mql_acceptance_rate_pct", "sla_compliance_pct", "content_engagements", "events"}` |
| `campaign_rows` | list of dicts: `{"campaign", "spend", "attributed_revenue", "roi_pct", "cost_per_lead", "pipeline_value", "lead_count", "touchpoint_count"}` |
| `channel_rows` | list of dicts: `{"channel", "label", "touchpoints", "cost", "attributed_revenue", "roi_pct"}` |
| `mql_funnel` | `{"pending", "accepted", "rejected", "expired", "converted", "acceptance_rate_pct", "sla_compliance_pct", "avg_response_hours"}` |
| `content_rows` | list of dicts: `{"content", "engagements", "avg_score", "revenue_attributed"}` |
| `event_rows` | list of dicts: `{"event", "registrations", "attended", "show_up_pct", "revenue_per_registrant"}` |
| `model_choices` | `ATTRIBUTION_MODEL_CHOICES` — the model selector labels shown on the page |
| `active_model` | the `request.GET["model"]` value, defaulting to `"first_touch"` — the console recomputes the rollup under the selected model |

**Computation rules for the console (derived — never stored):**
- `spend` per campaign = `crm.Campaign.budget_actual` (the campaign's own recorded spend) — 8.13 does
  **not** re-derive it.
- `attributed_revenue` per campaign = `SUM(CampaignAttribution.attributed_revenue)` over the rows whose
  `attribution_model == active_model` and whose `touchpoint.campaign == campaign`.
- `roi_pct` = `(attributed_revenue - spend) / spend * 100`, or `None` when `spend == 0`.
- `cost_per_lead` = `spend / COUNT(DISTINCT touchpoint.lead_id)`, or `None` when there are no leads or spend is 0.
- `pipeline_value` = `SUM(AttributionTouchpoint.engagement_value)` for the campaign's touchpoints.
- `blended_roi_pct` = `(total_attributed_revenue - total_spend) / total_spend * 100`, or `None`.
- `mql_acceptance_rate_pct` = `accepted / (accepted + rejected) * 100`, or `None` when neither exists.
- `sla_compliance_pct` = `100 - (breached / total * 100)`, or `None` when there are no handoffs.
- `avg_response_hours` = mean of `MqlHandoff.response_hours` over responded handoffs.

---

## 5. Templates — exact paths

`templates/sales/marketingalignment/` is the sub-module folder; each entity gets its own folder
inside it with bare `list.html` / `detail.html` / `form.html`.

| Template | Purpose |
|---|---|
| `templates/sales/marketingalignment/attribution_console.html` | the derived console (sub-module root — it is not an entity CRUD page) |
| `templates/sales/marketingalignment/attributiontouchpoint/list.html` | touch ledger list + filters + Actions |
| `templates/sales/marketingalignment/attributiontouchpoint/detail.html` | touch detail + its credit rows |
| `templates/sales/marketingalignment/attributiontouchpoint/form.html` | shared create/edit |
| `templates/sales/marketingalignment/campaignattribution/list.html` | credit list + filters + Actions |
| `templates/sales/marketingalignment/campaignattribution/detail.html` | credit detail |
| `templates/sales/marketingalignment/campaignattribution/form.html` | shared create/edit |
| `templates/sales/marketingalignment/mqlhandoff/list.html` | handoff list + filters + Actions |
| `templates/sales/marketingalignment/mqlhandoff/detail.html` | handoff detail + SLA panel |
| `templates/sales/marketingalignment/mqlhandoff/form.html` | shared create/edit |
| `templates/sales/marketingalignment/contentengagement/list.html` | engagement list + filters + Actions |
| `templates/sales/marketingalignment/contentengagement/detail.html` | engagement detail |
| `templates/sales/marketingalignment/contentengagement/form.html` | shared create/edit |
| `templates/sales/marketingalignment/marketingevent/list.html` | event list + filters + Actions |
| `templates/sales/marketingalignment/marketingevent/detail.html` | event detail + registrations + Actions |
| `templates/sales/marketingalignment/marketingevent/form.html` | shared create/edit |
| `templates/sales/marketingalignment/marketingevent/registrations.html` | registration list for one event |
| `templates/sales/marketingalignment/marketingevent/registration_form.html` | add-registration form |

**Design-system rules (theme.css — verified by grep before writing):**
- Badges: `.badge` + **colour-named only** — `.badge-green`, `.badge-red`, `.badge-amber`,
  `.badge-info`, `.badge-muted`, `.badge-slate`. **`.badge-success` / `.badge-warning` /
  `.badge-danger` DO NOT EXIST** (L33 shipped 3× on exactly this).
- Stat icons: `.stat-icon` + `.blue` / `.green` / `.orange` / `.purple` / `.slate` / `.red`.
- Text helpers: `.text-muted`, `.text-danger`, `.text-red`, `.text-warn`, `.text-ok`, `.text-brand`,
  `.text-right`.
- Structure: `.page-header` `.page-title` `.breadcrumb` `.page-actions` · `.card` `.card-header`
  `.card-body` `.card-title` · `.btn` `.btn-primary` `.btn-outline` `.btn-danger` `.btn-icon`
  `.btn-sm` · `.table-wrap` `.table` `.table-actions` · `.form-group` `.form-label` `.form-input`
  `.form-select` `.form-textarea` `.form-error` `.form-check` · `.stat-card` · `.empty-state`
  `.pagination` · `.detail-grid` `.detail-header` `.detail-item` · `.progress` `.progress-bar`.
- Icons: `<i data-lucide="NAME"></i>` — list Actions use **eye / pencil / trash-2**.
- Every list template: a GET filter form (search `q` + selects reflecting `request.GET`), an
  **Actions column** (view / edit / delete-POST-with-confirm+csrf), pagination that preserves the
  active filters, and an `.empty-state` with a "create first" CTA.
- Every filter dropdown that compares a pk uses `|stringformat:"d"` — **never** `|slugify`.
- Badges fall back with `{{ obj.get_<field>_display }}`.
- `{% csrf_token %}` on every POST form.
- Templates extend `templates/base.html` and link back through
  `{% url 'sales:sales_overview' %}` → `{% url 'sales:marketing_attribution_console' %}`.

---

## 6. Admin — `apps/sales/admin.py` (flat file, single-writer)

Register all 6 classes: `AttributionTouchpoint`, `CampaignAttribution`, `MqlHandoff`,
`ContentEngagement`, `MarketingEvent`, `EventRegistration`.
`tenant` and the auto-`number` are **readonly** on every admin (the number is minted by
`TenantNumbered.save()` and must never be typed in). `responded_at` and `attended_at` are
**readonly** (system-stamped). The FK querysets are narrowed to the requesting tenant via
`formfield_for_foreignkey`.

---

## 7. Seeder — extend `apps/sales/management/commands/seed_sales.py` (never a new command)

New method `_seed_marketing_alignment(self, tenant, owner)`, called from `_seed_tenant` after
`_seed_customer_success`. **Idempotency** — every block is an existence check, never an
unconditional `create`:

| Model | Idempotency key |
|---|---|
| `AttributionTouchpoint` | `(tenant, lead, campaign, touch_date, touch_type)` |
| `CampaignAttribution` | `(tenant, touchpoint, attribution_model)` |
| `MqlHandoff` | `(tenant, lead)` |
| `ContentEngagement` | `(tenant, content, account, engagement_type)` |
| `MarketingEvent` | `(tenant, name)` |
| `EventRegistration` | `(tenant, event, registrant_email or registrant_name)` |

The seeder **reuses** existing `crm.Campaign`, `crm.Lead`, `crm.Opportunity`, `core.Party` (customer
role) and `sales.EnablementContent` rows — it creates none of them. It must tolerate their
absence (skip the block with a `self.style.WARNING(...)` rather than crashing).

The command's success line is updated to include `8.13`, and a new warning line records the
**no-JournalEntry** fact (L29) and the **no-automation** fact (follow-up status is a recorded
state, not a dispatcher — see `GAP-sales-8.13-05`).

---

## 8. Navigation — `apps/core/navigation.py` (single-writer)

One new entry, `"8.13"`, mapping the five NavERP.md feature bullets → live pages, plus extra live
leaves for each entity list. The `parse_catalog()` / `MODULE_ICONS` machinery is **not** touched.

```python
"8.13": {
    # OWNERSHIP RULING (L36/L37)
    # Reuses crm.Campaign (CAM-) for the campaign master; reuses crm.Lead (LEAD-) and
    # crm.Opportunity (OPP-) for the journey; reuses core.Party for accounts; reuses
    # sales.EnablementContent (ECN-) for the content master.
    # Zero duplicate campaign, lead, opportunity, account or content models declared.
    "Campaign Influence & Attribution": "sales:marketing_attribution_console",
    "MQL-to-SQL Tracking": "sales:mql_handoff_list",
    "Campaign Performance Integration": "sales:marketing_attribution_console",
    "Content Performance & Engagement": "sales:content_engagement_list",
    "Event & Webinar Management": "sales:marketing_event_list",
    # Extra live leaves
    "Attribution Touchpoints": "sales:attribution_touchpoint_list",
    "Campaign Attributions": "sales:campaign_attribution_list",
},
```

---

## 9. Verification gates

1. `venv\Scripts\python.exe manage.py makemigrations sales` → `0022_marketingalignment`
2. `venv\Scripts\python.exe manage.py migrate`
3. `venv\Scripts\python.exe manage.py seed_sales` → **twice**; the second run must create nothing new
4. `venv\Scripts\python.exe manage.py check` → clean
5. Smoke (qa-smoke-tester): every new URL returns 200/302 as `admin_acme` **with asserted content**,
   not just a status; junk params fall back to the unfiltered list; page 2 renders; a
   `admin_globex` pk returns **404** as `admin_acme`.
6. No `{#` / `{% comment` leak markers in any rendered list page.
7. `manage.py check` must be clean **and** `python manage.py makemigrations --check --dry-run`
   must report no pending model changes.
