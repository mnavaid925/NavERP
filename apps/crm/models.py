"""CRM (Module 1) domain models.

CRM reuses the unified core spine (NavERP-ERD.md): **Accounts** and **Contacts** are
``core.Party`` (one record, many roles) — this app adds only its own domain tables and FKs
into core **by string**. Every model is tenant-scoped and carries a human-readable per-tenant
number (LEAD-/OPP-/CAM-/CASE-/KB-/TASK-) assigned in ``save()`` via the shared
``apps.core.utils.next_number`` helper, with the retry-on-collision pattern proven in
``tenants.SubscriptionInvoice``.
"""
import calendar
import secrets
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import IntegrityError, models, transaction
from django.utils import timezone

from apps.core.utils import next_number


class TenantNumbered(models.Model):
    """Abstract base: tenant FK + auto per-tenant ``number`` + created/updated timestamps.

    Subclasses set ``NUMBER_PREFIX`` (e.g. ``"LEAD"``). ``save()`` assigns the next number
    once (only when blank) and retries on the rare concurrent ``unique_together(tenant,
    number)`` collision — mirrors ``tenants.SubscriptionInvoice.save()``.
    """

    NUMBER_PREFIX = ""

    # related_name="+" : no reverse accessor needed (views filter Model.objects.filter(tenant=...)),
    # and it sidesteps reverse-name clashes across the abstract base's subclasses.
    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="+", db_index=True)
    number = models.CharField(max_length=20, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self.number and self.tenant_id and self.NUMBER_PREFIX:
            for _ in range(5):
                self.number = next_number(type(self), self.tenant, self.NUMBER_PREFIX)
                try:
                    with transaction.atomic():
                        return super().save(*args, **kwargs)
                except IntegrityError:
                    self.number = ""
        return super().save(*args, **kwargs)


class Lead(TenantNumbered):
    """A potential customer (1.1). Convertible to a Party/Contact + Opportunity."""

    NUMBER_PREFIX = "LEAD"

    SOURCE_CHOICES = [
        ("web", "Web Form"),
        ("referral", "Referral"),
        ("event", "Event"),
        ("cold_call", "Cold Call"),
        ("email_campaign", "Email Campaign"),
        ("social", "Social Media"),
        ("other", "Other"),
    ]
    RATING_CHOICES = [("hot", "Hot"), ("warm", "Warm"), ("cold", "Cold")]
    STATUS_CHOICES = [
        ("new", "New"),
        ("contacted", "Contacted"),
        ("qualified", "Qualified"),
        ("unqualified", "Unqualified"),
        ("converted", "Converted"),
        ("recycled", "Recycled"),
    ]

    name = models.CharField(max_length=255)
    company = models.CharField(max_length=255, blank=True)
    title = models.CharField(max_length=120, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default="web")
    rating = models.CharField(max_length=10, choices=RATING_CHOICES, default="warm")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="new")
    score = models.PositiveSmallIntegerField(default=0, validators=[MaxValueValidator(100)])  # 0–100 grade
    est_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_leads")
    description = models.TextField(blank=True)
    converted_party = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_converted_leads")

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="crm_lead_tenant_status_idx"),
            models.Index(fields=["tenant", "created_at"], name="crm_lead_tenant_created_idx"),
        ]

    def __str__(self):
        return f"{self.number} · {self.name}"


class Campaign(TenantNumbered):
    """A marketing campaign (1.3) with planned/actual budget + ROI."""

    NUMBER_PREFIX = "CAM"

    TYPE_CHOICES = [
        ("email", "Email"),
        ("webinar", "Webinar"),
        ("event", "Event"),
        ("digital_ad", "Digital Ad"),
        ("direct_mail", "Direct Mail"),
        ("social", "Social Media"),
        ("other", "Other"),
    ]
    STATUS_CHOICES = [
        ("planned", "Planned"),
        ("active", "Active"),
        ("paused", "Paused"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]
    OBJECTIVE_CHOICES = [
        ("awareness", "Brand Awareness"),
        ("lead_gen", "Lead Generation"),
        ("nurture", "Nurture / Engagement"),
        ("conversion", "Conversion / Sales"),
        ("event", "Event Promotion"),
        ("retention", "Retention / Loyalty"),
    ]

    name = models.CharField(max_length=255)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="email")
    objective = models.CharField(max_length=20, choices=OBJECTIVE_CHOICES, default="lead_gen")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="planned")
    # Self-FK lets campaigns roll up under a parent program (e.g. "Q3 Demand Gen").
    parent_campaign = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="child_campaigns")
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    budget_planned = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    budget_actual = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    expected_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    actual_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    target_size = models.PositiveIntegerField(default=0)
    # UTM tagging so downstream web/landing traffic can be attributed to the campaign.
    utm_source = models.CharField(max_length=120, blank=True)
    utm_medium = models.CharField(max_length=120, blank=True)
    utm_campaign = models.CharField(max_length=120, blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_campaigns")
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="crm_campaign_tnt_status_idx"),
            models.Index(fields=["tenant", "created_at"], name="crm_campaign_tnt_created_idx"),
        ]

    @property
    def roi(self):
        """Return on investment %, or None when no actual spend is recorded.

        Casts to Decimal so the property is correct on a freshly-created (un-round-tripped)
        instance, where DecimalField values are still plain strings.
        """
        budget = Decimal(self.budget_actual or 0)
        if not budget:
            return None
        return (Decimal(self.actual_revenue or 0) - budget) / budget * 100

    def __str__(self):
        return f"{self.number} · {self.name}"


class CampaignMember(models.Model):
    """A target-list member of a Campaign (1.3) with per-recipient response tracking.

    Not ``TenantNumbered`` — it's a membership row (target-list segmentation), so it
    carries its own tenant FK + timestamps and no human-readable number. Targets either a
    reused ``core.Party`` (account/contact) or a ``crm.Lead``; ``member_name``/``member_email``
    keep a display snapshot so imported list rows survive a null/changed source record.
    """

    STATUS_CHOICES = [
        ("targeted", "Targeted"),
        ("sent", "Sent"),
        ("opened", "Opened"),
        ("clicked", "Clicked"),
        ("responded", "Responded"),
        ("converted", "Converted"),
        ("bounced", "Bounced"),
        ("unsubscribed", "Unsubscribed"),
    ]
    RESPONDED_STATUSES = ("responded", "converted")

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="+", db_index=True)
    campaign = models.ForeignKey("Campaign", on_delete=models.CASCADE, related_name="members")
    party = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_campaign_members")
    lead = models.ForeignKey("Lead", on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_campaign_members")
    member_name = models.CharField(max_length=255)
    member_email = models.EmailField(blank=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="targeted")
    responded_at = models.DateTimeField(null=True, blank=True)  # system-set, out of forms
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "status"], name="crm_cmem_tnt_status_idx"),
            models.Index(fields=["tenant", "campaign"], name="crm_cmem_tnt_camp_idx"),
            models.Index(fields=["tenant", "created_at"], name="crm_cmem_tnt_created_idx"),
        ]

    @property
    def has_responded(self):
        return self.status in self.RESPONDED_STATUSES

    def save(self, *args, **kwargs):
        # System-set responded_at: stamp the first time the member responds/converts.
        if self.status in self.RESPONDED_STATUSES and self.responded_at is None:
            self.responded_at = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.member_name} · {self.get_status_display()}"


class EmailTemplate(TenantNumbered):
    """A reusable marketing-email template (1.3 Email Marketing) with merge variables.

    ``body`` is raw HTML with merge tokens (e.g. ``{{first_name}}``); it is shown ESCAPED
    as a source preview on the detail page (never ``|safe``) and deferred on the list QS.
    """

    NUMBER_PREFIX = "EMT"

    CATEGORY_CHOICES = [
        ("newsletter", "Newsletter"),
        ("promotional", "Promotional"),
        ("transactional", "Transactional"),
        ("drip", "Drip / Nurture"),
        ("announcement", "Announcement"),
        ("other", "Other"),
    ]

    name = models.CharField(max_length=255)
    category = models.CharField(max_length=15, choices=CATEGORY_CHOICES, default="promotional")
    subject = models.CharField(max_length=255)
    preheader = models.CharField(max_length=255, blank=True)
    body = models.TextField(blank=True)
    from_name = models.CharField(max_length=120, blank=True)
    from_email = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_email_templates")

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "category"], name="crm_etpl_tnt_cat_idx"),
            models.Index(fields=["tenant", "created_at"], name="crm_etpl_tnt_created_idx"),
        ]

    def __str__(self):
        return f"{self.number} · {self.name}"


class EmailCampaign(TenantNumbered):
    """An email send/blast (1.3 Email Marketing) tied to a Campaign + EmailTemplate.

    A/B testing folds into ``variant_template`` (+ ``is_ab_test``); drip folds into
    ``send_type='drip'`` + ``scheduled_at`` — no separate DripStep/ABVariant tables. All the
    engagement counters are SYSTEM-managed (set by ``emailcampaign_send`` / the seeder) and
    excluded from the form so a user can't fabricate metrics.
    """

    NUMBER_PREFIX = "BLAST"

    SEND_TYPE_CHOICES = [
        ("one_time", "One-time Blast"),
        ("drip", "Drip / Automated"),
        ("ab_test", "A/B Test"),
    ]
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("scheduled", "Scheduled"),
        ("sending", "Sending"),
        ("sent", "Sent"),
        ("paused", "Paused"),
        ("cancelled", "Cancelled"),
    ]
    SENT_STATUSES = ("sending", "sent")

    name = models.CharField(max_length=255)
    campaign = models.ForeignKey("Campaign", on_delete=models.CASCADE, related_name="email_campaigns")
    template = models.ForeignKey("EmailTemplate", on_delete=models.SET_NULL, null=True, blank=True, related_name="email_campaigns")
    variant_template = models.ForeignKey("EmailTemplate", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")  # A/B variant B
    is_ab_test = models.BooleanField(default=False)
    send_type = models.CharField(max_length=10, choices=SEND_TYPE_CHOICES, default="one_time")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="draft")
    scheduled_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)  # system-set on send
    # Engagement counters — system-managed (excluded from the form).
    recipients_count = models.PositiveIntegerField(default=0)
    sent_count = models.PositiveIntegerField(default=0)
    opened_count = models.PositiveIntegerField(default=0)
    clicked_count = models.PositiveIntegerField(default=0)
    bounced_count = models.PositiveIntegerField(default=0)
    unsubscribed_count = models.PositiveIntegerField(default=0)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_email_campaigns")

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="crm_blast_tnt_status_idx"),
            models.Index(fields=["tenant", "created_at"], name="crm_blast_tnt_created_idx"),
        ]

    @property
    def delivered_count(self):
        return max(0, (self.sent_count or 0) - (self.bounced_count or 0))

    @property
    def open_rate(self):
        """Unique opens ÷ delivered, as a %. None when nothing was delivered.

        Casts to Decimal so the property is correct on a freshly-created (un-round-tripped)
        instance, mirroring ``Campaign.roi``."""
        delivered = self.delivered_count
        if not delivered:
            return None
        return Decimal(self.opened_count or 0) / Decimal(delivered) * 100

    @property
    def click_rate(self):
        delivered = self.delivered_count
        if not delivered:
            return None
        return Decimal(self.clicked_count or 0) / Decimal(delivered) * 100

    @property
    def bounce_rate(self):
        sent = self.sent_count or 0
        if not sent:
            return None
        return Decimal(self.bounced_count or 0) / Decimal(sent) * 100

    def __str__(self):
        return f"{self.number} · {self.name}"


class LandingPage(TenantNumbered):
    """A public landing page + web-to-lead form (1.3 Landing Pages & Forms).

    Served at an unguessable ``public_token`` URL; only ``status='published'`` pages resolve
    publicly. ``body`` is tenant-authored and rendered to the public ESCAPED (via the
    ``linebreaks`` filter, never ``|safe``) to avoid stored XSS against visitors. Captured
    leads route to ``routing_owner``.
    """

    NUMBER_PREFIX = "LP"

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("published", "Published"),
        ("archived", "Archived"),
    ]

    name = models.CharField(max_length=255)
    campaign = models.ForeignKey("Campaign", on_delete=models.SET_NULL, null=True, blank=True, related_name="landing_pages")
    slug = models.SlugField(max_length=160, blank=True)
    public_token = models.CharField(max_length=64, unique=True, editable=False, blank=True)
    headline = models.CharField(max_length=255)
    subheadline = models.CharField(max_length=255, blank=True)
    body = models.TextField(blank=True)
    capture_phone = models.BooleanField(default=True)
    capture_company = models.BooleanField(default=True)
    capture_message = models.BooleanField(default=False)
    cta_label = models.CharField(max_length=60, default="Submit")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="draft")
    routing_owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_routed_landing_pages")
    lead_source = models.CharField(max_length=20, choices=Lead.SOURCE_CHOICES, default="web")
    submission_count = models.PositiveIntegerField(default=0)  # system-set (F()-bumped on submit)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_landing_pages")

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="crm_lp_tnt_status_idx"),
            models.Index(fields=["tenant", "created_at"], name="crm_lp_tnt_created_idx"),
        ]

    @property
    def is_published(self):
        return self.status == "published"

    def save(self, *args, **kwargs):
        # Unguessable public URL key — 256-bit, generated once, never user-editable
        # (matches the project-wide token convention: SignerRecord/UserInvite use token_urlsafe(32)).
        if not self.public_token:
            self.public_token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.number} · {self.name}"


class FormSubmission(models.Model):
    """A web-to-lead capture from a public LandingPage (1.3 Landing Pages & Forms).

    Read-mostly: rows are created only by the public ``landing_public`` endpoint, so there is
    no internal create/edit form (mirrors the ``WorkflowLog`` read-only precedent). They can be
    converted into a ``crm.Lead`` (routed to the rep) or deleted as spam.
    """

    STATUS_CHOICES = [
        ("new", "New"),
        ("routed", "Routed"),
        ("converted", "Converted"),
        ("spam", "Spam"),
    ]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="+", db_index=True)
    landing_page = models.ForeignKey("LandingPage", on_delete=models.CASCADE, related_name="submissions")
    name = models.CharField(max_length=255)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    company = models.CharField(max_length=255, blank=True)
    message = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="new")
    routed_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_routed_submissions")
    converted_lead = models.ForeignKey("Lead", on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_form_submissions")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "status"], name="crm_fsub_tnt_status_idx"),
            models.Index(fields=["tenant", "landing_page"], name="crm_fsub_tnt_lp_idx"),
        ]

    def __str__(self):
        return f"{self.name} · {self.get_status_display()}"


class Opportunity(TenantNumbered):
    """A sales deal (1.2) on the pipeline. Account/contact reuse ``core.Party``."""

    NUMBER_PREFIX = "OPP"

    STAGE_CHOICES = [
        ("prospecting", "Prospecting"),
        ("qualification", "Qualification"),
        ("proposal", "Proposal"),
        ("negotiation", "Negotiation"),
        ("closed_won", "Closed Won"),
        ("closed_lost", "Closed Lost"),
    ]
    OPEN_STAGES = ["prospecting", "qualification", "proposal", "negotiation"]
    # Forecast rollup buckets (Salesforce/Zoho/Clari) — drive the 1.2 forecast dashboard.
    FORECAST_CATEGORY_CHOICES = [
        ("omitted", "Omitted"),
        ("pipeline", "Pipeline"),
        ("best_case", "Best Case"),
        ("commit", "Commit"),
        ("closed", "Closed"),
    ]

    name = models.CharField(max_length=255)
    account = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_opportunities")
    primary_contact = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_contact_opportunities")
    stage = models.CharField(max_length=20, choices=STAGE_CHOICES, default="prospecting")
    forecast_category = models.CharField(max_length=12, choices=FORECAST_CATEGORY_CHOICES, default="pipeline")
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    probability = models.PositiveSmallIntegerField(default=10, validators=[MaxValueValidator(100)])
    close_date = models.DateField(null=True, blank=True)
    competitor = models.CharField(max_length=255, blank=True)
    loss_reason = models.CharField(max_length=255, blank=True)  # filled when closed_lost
    lost_at = models.DateTimeField(null=True, blank=True)  # system-set when stage→closed_lost
    stage_changed_at = models.DateTimeField(null=True, blank=True)  # system-set on stage change (days-in-stage)
    territory = models.ForeignKey("crm.Territory", on_delete=models.SET_NULL, null=True, blank=True, related_name="opportunities")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_opportunities")
    source_lead = models.ForeignKey("crm.Lead", on_delete=models.SET_NULL, null=True, blank=True, related_name="opportunities")
    campaign = models.ForeignKey("crm.Campaign", on_delete=models.SET_NULL, null=True, blank=True, related_name="opportunities")
    next_step = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "stage"], name="crm_opp_tenant_stage_idx"),
            models.Index(fields=["tenant", "created_at"], name="crm_opp_tenant_created_idx"),
            models.Index(fields=["tenant", "forecast_category"], name="crm_opp_tnt_fcast_idx"),
        ]

    @classmethod
    def from_db(cls, db, field_names, values):
        # Remember the persisted stage so save() can detect a transition without a re-query.
        inst = super().from_db(db, field_names, values)
        inst._loaded_stage = inst.stage
        return inst

    def save(self, *args, **kwargs):
        # System-stamp stage_changed_at on any stage transition (incl. first create — a fresh
        # instance has no _loaded_stage, so the None sentinel never equals a real stage);
        # stamp lost_at when entering closed_lost, clear it if re-opened (mirrors Case.resolved_at).
        if self.stage != getattr(self, "_loaded_stage", None):
            self.stage_changed_at = timezone.now()
        if self.stage == "closed_lost":
            if self.lost_at is None:
                self.lost_at = timezone.now()
        else:
            self.lost_at = None
        super().save(*args, **kwargs)
        self._loaded_stage = self.stage

    @property
    def weighted_amount(self):
        """Pipeline-forecast value: amount × probability ÷ 100.

        Casts to Decimal so it is correct on a freshly-created instance (where the
        DecimalField value is still a string before the first DB round-trip)."""
        return Decimal(self.amount or 0) * self.probability / 100

    @property
    def is_open(self):
        return self.stage in self.OPEN_STAGES

    @property
    def is_won(self):
        return self.stage == "closed_won"

    def __str__(self):
        return f"{self.number} · {self.name}"


# ============================================================================
# ===== 1.2 Sales Force Automation (recreated) ===============================
# Opportunity splits, the sales Product catalog + price books, the Quote builder,
# territories, and sales quotas (the forecast/Kanban are views, not tables).
# ============================================================================
class Territory(TenantNumbered):
    """A sales territory (1.2 Forecasting) — region/segment with an optional parent for
    roll-up hierarchies; opportunities + quotas hang off it for forecast-by-territory."""

    NUMBER_PREFIX = "TER"

    name = models.CharField(max_length=255)
    region = models.CharField(max_length=120, blank=True)
    segment = models.CharField(max_length=120, blank=True)
    parent = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="child_territories")
    manager = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_territories")
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="crm_ter_tnt_active_idx"),
            models.Index(fields=["tenant", "created_at"], name="crm_ter_tnt_created_idx"),
        ]

    def __str__(self):
        return f"{self.number} · {self.name}"


class Product(TenantNumbered):
    """A sales-catalog product/service (1.2 Quoting). CRM-owned for now — migrate to the
    shared ``core.Item`` master once Inventory (Module 5) ships. Distinct from the 1.12
    ``ProductStock`` (which tracks on-hand inventory, not a sellable catalog + list price)."""

    NUMBER_PREFIX = "PRD"

    TYPE_CHOICES = [
        ("good", "Good"),
        ("service", "Service"),
        ("subscription", "Subscription"),
    ]

    name = models.CharField(max_length=255)
    sku = models.CharField(max_length=64, blank=True)
    product_type = models.CharField(max_length=15, choices=TYPE_CHOICES, default="good")
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0,
                                  validators=[MinValueValidator(0), MaxValueValidator(100)])
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "product_type"], name="crm_prd_tnt_type_idx"),
            models.Index(fields=["tenant", "is_active"], name="crm_prd_tnt_active_idx"),
        ]

    @property
    def margin_pct(self):
        """Gross margin %, or None when no price is set. Decimal-safe on a fresh instance."""
        price = Decimal(self.unit_price or 0)
        if not price:
            return None
        return (price - Decimal(self.cost or 0)) / price * 100

    def __str__(self):
        return f"{self.number} · {self.name}"


class PriceBook(TenantNumbered):
    """A regional/tier price list (1.2 Quoting). ``price_adjustment_pct`` shifts a product's
    base price by ±% for this book (e.g. EU Tier-2 = -10%) — a per-product override table
    (PriceBookEntry) is a documented future enhancement, not built here."""

    NUMBER_PREFIX = "PB"

    name = models.CharField(max_length=255)
    currency_code = models.CharField(max_length=3, default="USD")
    region = models.CharField(max_length=120, blank=True)
    tier = models.CharField(max_length=120, blank=True)
    price_adjustment_pct = models.DecimalField(  # ± off base; floor at -100% so it can't make a negative price
        max_digits=6, decimal_places=2, default=0, validators=[MinValueValidator(-100)])
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["-is_default", "name"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="crm_pb_tnt_active_idx"),
            models.Index(fields=["tenant", "is_default"], name="crm_pb_tnt_default_idx"),
        ]

    def adjusted_price(self, base):
        """Apply this book's ± adjustment to a product base price (Decimal-safe)."""
        base = Decimal(base or 0)
        return base * (Decimal(100) + Decimal(self.price_adjustment_pct or 0)) / 100

    def __str__(self):
        return f"{self.number} · {self.name}"


class OpportunitySplit(models.Model):
    """A sales-team credit/commission split on an Opportunity (1.2). Plain tenant-scoped row
    (no auto-number). Revenue-type splits across an opportunity must total ≤ 100% (validated in
    ``clean()`` + the add view); overlay credit is uncapped (it doesn't divide the booking)."""

    SPLIT_TYPE_CHOICES = [
        ("revenue", "Revenue"),
        ("overlay", "Overlay / Credit"),
    ]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="+", db_index=True)
    opportunity = models.ForeignKey("Opportunity", on_delete=models.CASCADE, related_name="splits")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="crm_opportunity_splits")
    split_type = models.CharField(max_length=10, choices=SPLIT_TYPE_CHOICES, default="revenue")
    # WARNING: a negative percentage would slip under the ≤100% sum guard and corrupt
    # split_amount / forecast math — bound it to (0, 100].
    percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        validators=[MinValueValidator(Decimal("0.01")), MaxValueValidator(100)])
    notes = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["split_type", "-percentage"]
        indexes = [
            models.Index(fields=["tenant", "opportunity"], name="crm_osplit_tnt_opp_idx"),
        ]

    @property
    def split_amount(self):
        """This split's share of the opportunity amount (Decimal-safe)."""
        return Decimal(self.opportunity.amount or 0) * Decimal(self.percentage or 0) / 100

    def clean(self):
        from django.core.exceptions import ValidationError
        # Defence in depth (the inline add calls clean() directly, not full_clean()): reject a
        # non-positive percentage so it can't slip under the ≤100% aggregate guard below.
        if self.percentage is not None and self.percentage <= 0:
            raise ValidationError("Percentage must be greater than zero.")
        # Revenue splits divide the booking — they must not exceed 100% across the opportunity.
        # (Guard on tenant_id too so a clean() before the view sets tenant can't query tenant=None.)
        if self.split_type == "revenue" and self.opportunity_id and self.tenant_id:
            from django.db.models import Sum
            others = OpportunitySplit.objects.filter(
                tenant=self.tenant, opportunity=self.opportunity, split_type="revenue")
            if self.pk:
                others = others.exclude(pk=self.pk)
            # DB-side SUM instead of fetching every split row to add in Python.
            existing = others.aggregate(t=Sum("percentage"))["t"] or Decimal(0)
            if existing + Decimal(self.percentage or 0) > 100:
                raise ValidationError("Revenue splits for an opportunity cannot exceed 100%.")

    def __str__(self):
        return f"{self.user} · {self.percentage}% ({self.get_split_type_display()})"


class Quote(TenantNumbered):
    """A sales quote (1.2 Quoting) with line items, per-line + quote-level discount and tax.
    ``status`` and the ``subtotal``/``tax_total``/``total`` + ``sent_at``/``accepted_at`` are
    SYSTEM-managed (set by the send/accept/decline actions + ``recalc_totals()``) and excluded
    from the form, so a user can't forge a total or self-accept a quote via POST."""

    NUMBER_PREFIX = "QUO"

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("sent", "Sent"),
        ("accepted", "Accepted"),
        ("declined", "Declined"),
        ("expired", "Expired"),
    ]
    OPEN_STATUSES = ("draft", "sent")

    name = models.CharField(max_length=255)
    opportunity = models.ForeignKey("Opportunity", on_delete=models.SET_NULL, null=True, blank=True, related_name="quotes")
    account = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_quotes")
    price_book = models.ForeignKey("PriceBook", on_delete=models.SET_NULL, null=True, blank=True, related_name="quotes")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="draft")
    valid_until = models.DateField(null=True, blank=True)
    currency_code = models.CharField(max_length=3, default="USD")
    discount_pct = models.DecimalField(  # quote-level, on top of line discounts
        max_digits=5, decimal_places=2, default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)])
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=0)   # system (recalc_totals)
    tax_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)  # system
    total = models.DecimalField(max_digits=14, decimal_places=2, default=0)      # system
    sent_at = models.DateTimeField(null=True, blank=True)      # system (quote_send)
    accepted_at = models.DateTimeField(null=True, blank=True)  # system (quote_accept)
    terms = models.TextField(blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_quotes")

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="crm_quo_tnt_status_idx"),
            models.Index(fields=["tenant", "created_at"], name="crm_quo_tnt_created_idx"),
        ]

    def recalc_totals(self, save=True):
        """Recompute subtotal/tax/total from the lines, then apply the quote-level discount.
        Lines store unit_price/discount/tax; totals are derived, never user-entered.

        Summed in Python over the (few, bounded) lines using the Decimal-safe line properties —
        NOT a DB-side ``F()/100`` expression, which integer-divides on SQLite and silently drops
        per-line discounts/tax. One query (``self.lines.all()``); quotes have a handful of lines."""
        line_sub = Decimal(0)
        line_tax = Decimal(0)
        for ln in self.lines.all():
            line_sub += ln.line_subtotal
            line_tax += ln.line_tax
        disc = (Decimal(100) - Decimal(self.discount_pct or 0)) / 100  # quote-level discount factor
        # The discount factor is applied to BOTH subtotal and tax, so tax is effectively computed
        # on the discounted base (tax_total = line_sub*tax_pct*disc = discounted_subtotal*tax_pct).
        self.subtotal = (line_sub * disc).quantize(Decimal("0.01"))
        self.tax_total = (line_tax * disc).quantize(Decimal("0.01"))
        self.total = (self.subtotal + self.tax_total).quantize(Decimal("0.01"))
        if save:
            super().save(update_fields=["subtotal", "tax_total", "total", "updated_at"])

    @property
    def is_open(self):
        return self.status in self.OPEN_STATUSES

    @property
    def is_expired(self):
        return bool(self.valid_until and self.status in self.OPEN_STATUSES
                    and self.valid_until < timezone.localdate())

    def __str__(self):
        return f"{self.number} · {self.name}"


class QuoteLine(models.Model):
    """A line item on a Quote (1.2). Plain tenant-scoped child; ``line_total`` is a derived
    property (never stored/forged). ``product`` is nullable for free-text write-in lines."""

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="+", db_index=True)
    quote = models.ForeignKey("Quote", on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey("Product", on_delete=models.SET_NULL, null=True, blank=True, related_name="quote_lines")
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=1,
                                   validators=[MinValueValidator(0)])
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0,
                                       validators=[MinValueValidator(0), MaxValueValidator(100)])
    tax_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0,
                                  validators=[MinValueValidator(0), MaxValueValidator(100)])
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "created_at"]
        indexes = [
            models.Index(fields=["tenant", "quote"], name="crm_qline_tnt_quote_idx"),
        ]

    @property
    def line_subtotal(self):
        return (Decimal(self.quantity or 0) * Decimal(self.unit_price or 0)
                * (Decimal(1) - Decimal(self.discount_pct or 0) / 100))

    @property
    def line_tax(self):
        return self.line_subtotal * Decimal(self.tax_pct or 0) / 100

    @property
    def line_total(self):
        return self.line_subtotal + self.line_tax

    def __str__(self):
        return f"{self.description} × {self.quantity}"


class SalesQuota(TenantNumbered):
    """A per-rep (and optional per-territory) sales target for a period (1.2 Forecasting).
    The forecast dashboard rolls weighted pipeline + closed-won against this target."""

    NUMBER_PREFIX = "QTA"

    PERIOD_CHOICES = [
        ("month", "Monthly"),
        ("quarter", "Quarterly"),
        ("year", "Annual"),
    ]

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_sales_quotas")
    territory = models.ForeignKey("Territory", on_delete=models.SET_NULL, null=True, blank=True, related_name="sales_quotas")
    period_type = models.CharField(max_length=10, choices=PERIOD_CHOICES, default="quarter")
    period_year = models.PositiveSmallIntegerField(default=2026)
    period_number = models.PositiveSmallIntegerField(default=1)  # month 1-12 / quarter 1-4 / year=0
    target_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-period_year", "period_number"]
        unique_together = [
            ("tenant", "number"),
            # Territory is part of the key so a rep can hold one quota per territory per period
            # (a null-territory "overall" quota is also enforced friendly-side in the form).
            ("tenant", "owner", "territory", "period_type", "period_year", "period_number"),
        ]
        indexes = [
            models.Index(fields=["tenant", "period_year"], name="crm_qta_tnt_year_idx"),
            models.Index(fields=["tenant", "territory"], name="crm_qta_tnt_terr_idx"),
        ]

    def __str__(self):
        return f"{self.number} · {self.get_period_type_display()} {self.period_year}"


class Case(TenantNumbered):
    """A support ticket (1.4). ``resolved_at`` is system-set when status closes."""

    NUMBER_PREFIX = "CASE"

    TYPE_CHOICES = [
        ("question", "Question"),
        ("problem", "Problem"),
        ("incident", "Incident"),
        ("feature_request", "Feature Request"),
        ("other", "Other"),
    ]
    PRIORITY_CHOICES = [("low", "Low"), ("medium", "Medium"), ("high", "High"), ("critical", "Critical")]
    STATUS_CHOICES = [
        ("new", "New"),
        ("open", "Open"),
        ("in_progress", "In Progress"),
        ("waiting", "Waiting on Customer"),
        ("resolved", "Resolved"),
        ("closed", "Closed"),
    ]
    ORIGIN_CHOICES = [
        ("email", "Email"),
        ("phone", "Phone"),
        ("portal", "Portal"),
        ("web", "Web"),
        ("chat", "Chat"),
    ]
    OPEN_STATUSES = ["new", "open", "in_progress", "waiting"]

    subject = models.CharField(max_length=255)
    account = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_cases")
    contact = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_contact_cases")
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="question")
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default="medium")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="new")
    origin = models.CharField(max_length=10, choices=ORIGIN_CHOICES, default="email")
    description = models.TextField(blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_cases")
    due_at = models.DateTimeField(null=True, blank=True)  # manual SLA deadline (legacy)
    resolved_at = models.DateTimeField(null=True, blank=True)  # system-set, out of forms
    # SLA (1.4) — policy-driven targets, all system-computed in save(), excluded from the form.
    sla_policy = models.ForeignKey("SlaPolicy", on_delete=models.SET_NULL, null=True, blank=True, related_name="cases")
    first_response_due = models.DateTimeField(null=True, blank=True)
    first_responded_at = models.DateTimeField(null=True, blank=True)  # stamped on first public agent reply
    resolution_due = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    # CSAT (1.4) — set via the portal / public status page, never the agent form.
    satisfaction_rating = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)])
    satisfaction_comment = models.TextField(blank=True)
    satisfaction_at = models.DateTimeField(null=True, blank=True)
    # null=True (not blank="") so existing rows stay distinct under the unique index until backfilled;
    # NULLs are distinct in MySQL/MariaDB. New rows always get a token via save().
    public_token = models.CharField(max_length=64, unique=True, editable=False, null=True, blank=True)  # public status URL key

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="crm_case_tenant_status_idx"),
            models.Index(fields=["tenant", "created_at"], name="crm_case_tenant_created_idx"),
            models.Index(fields=["tenant", "priority"], name="crm_case_tnt_priority_idx"),
        ]

    @property
    def is_open(self):
        return self.status in self.OPEN_STATUSES

    @property
    def is_overdue(self):
        # Open + past either the manual due_at or the policy resolution_due.
        deadline = self.resolution_due or self.due_at
        return bool(deadline and self.is_open and deadline < timezone.now())

    @property
    def is_response_overdue(self):
        return bool(self.first_response_due and self.first_responded_at is None
                    and self.is_open and self.first_response_due < timezone.now())

    @property
    def is_resolution_overdue(self):
        return bool(self.resolution_due and self.is_open and self.resolution_due < timezone.now())

    def save(self, *args, **kwargs):
        # System-set resolved_at: stamp when first resolved/closed, clear if re-opened.
        if self.status in ("resolved", "closed"):
            if self.resolved_at is None:
                self.resolved_at = timezone.now()
        else:
            self.resolved_at = None
        # closed_at mirrors the resolved logic but only for the terminal "closed" status.
        if self.status == "closed":
            if self.closed_at is None:
                self.closed_at = timezone.now()
        else:
            self.closed_at = None
        # Policy-driven SLA due timestamps — each computed once (independently, when still blank).
        # The outer guard also skips the sla_policy lazy-load entirely on a normal edit where both
        # dues are already set (no extra SELECT per case-edit save).
        if self.sla_policy_id and (self.first_response_due is None or self.resolution_due is None):
            anchor = self.created_at or timezone.now()
            resp_h, res_h = self.sla_policy.targets_for(self.priority)
            if resp_h and self.first_response_due is None:
                self.first_response_due = anchor + timedelta(hours=resp_h)
            if res_h and self.resolution_due is None:
                self.resolution_due = anchor + timedelta(hours=res_h)
        # Unguessable public status-tracking URL key — generated once, never user-editable.
        if not self.public_token:
            self.public_token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.number} · {self.subject}"


class KnowledgeArticle(TenantNumbered):
    """A help-desk solution / FAQ (1.4) with internal vs external visibility."""

    NUMBER_PREFIX = "KB"

    VISIBILITY_CHOICES = [("internal", "Internal"), ("external", "External")]
    STATUS_CHOICES = [("draft", "Draft"), ("published", "Published"), ("archived", "Archived")]

    title = models.CharField(max_length=255)
    category = models.CharField(max_length=120, blank=True)  # legacy free-text (kept; kb_category preferred)
    kb_category = models.ForeignKey("KbCategory", on_delete=models.SET_NULL, null=True, blank=True, related_name="articles")
    slug = models.SlugField(max_length=200, blank=True)
    body = models.TextField(blank=True)
    visibility = models.CharField(max_length=10, choices=VISIBILITY_CHOICES, default="internal")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="draft")
    views_count = models.PositiveIntegerField(default=0)  # system-set on detail view
    helpful_count = models.PositiveIntegerField(default=0)  # system-set via public vote
    not_helpful_count = models.PositiveIntegerField(default=0)  # system-set via public vote
    # null=True (not blank="") so existing rows stay distinct under the unique index until backfilled.
    public_token = models.CharField(max_length=64, unique=True, editable=False, null=True, blank=True)  # public article URL key
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_articles")

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="crm_kb_tenant_status_idx"),
            models.Index(fields=["tenant", "created_at"], name="crm_kb_tenant_created_idx"),
            models.Index(fields=["tenant", "kb_category"], name="crm_kb_tnt_category_idx"),
        ]

    @property
    def is_public(self):
        return self.status == "published" and self.visibility == "external"

    def save(self, *args, **kwargs):
        if not self.public_token:  # unguessable public-share URL key, generated once
            self.public_token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.number} · {self.title}"


# ============================================================================
# ===== 1.4 Customer Service & Support / Help Desk (recreated) ================
# SLA policies + the case conversation thread, KB categories, and the customer
# self-service portal access (the portal + public pages are views, not tables).
# ============================================================================
class SlaPolicy(TenantNumbered):
    """A service-level policy (1.4) — per-priority first-response + resolution targets in HOURS.

    One named policy covers all four priorities; a Case picks a policy and ``save()`` computes its
    due timestamps from ``targets_for(priority)``. (Business-hours calendars are deferred.)"""

    NUMBER_PREFIX = "SLA"

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    # First-response targets (hours) per priority.
    response_low = models.PositiveSmallIntegerField(default=48)
    response_medium = models.PositiveSmallIntegerField(default=24)
    response_high = models.PositiveSmallIntegerField(default=8)
    response_critical = models.PositiveSmallIntegerField(default=2)
    # Resolution targets (hours) per priority.
    resolution_low = models.PositiveSmallIntegerField(default=240)
    resolution_medium = models.PositiveSmallIntegerField(default=120)
    resolution_high = models.PositiveSmallIntegerField(default=48)
    resolution_critical = models.PositiveSmallIntegerField(default=8)

    class Meta:
        ordering = ["-is_default", "name"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="crm_sla_tnt_active_idx"),
            models.Index(fields=["tenant", "is_default"], name="crm_sla_tnt_default_idx"),
        ]

    def targets_for(self, priority):
        """Return ``(first_response_hours, resolution_hours)`` for a Case priority."""
        return (
            getattr(self, f"response_{priority}", None),
            getattr(self, f"resolution_{priority}", None),
        )

    def __str__(self):
        return f"{self.number} · {self.name}"


class CaseComment(models.Model):
    """A reply/note on a Case (1.4) — the conversation thread. Plain tenant-scoped row (no number).

    ``is_public`` distinguishes a customer-visible reply from an internal agent note; the customer
    portal + public status page only ever show ``is_public=True`` comments."""

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="+", db_index=True)
    case = models.ForeignKey("Case", on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_case_comments")
    author_name = models.CharField(max_length=255, blank=True)  # snapshot (portal/public author)
    body = models.TextField()
    is_public = models.BooleanField(default=False)  # customer-visible reply vs internal note
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["tenant", "case"], name="crm_ccmt_tnt_case_idx"),
        ]

    def __str__(self):
        kind = "public" if self.is_public else "internal"
        return f"{self.case_id} · {kind} comment"


class KbCategory(TenantNumbered):
    """A knowledge-base category (1.4) with an optional parent for a section hierarchy."""

    NUMBER_PREFIX = "KBC"

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    slug = models.SlugField(max_length=160, blank=True)
    parent = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="child_categories")
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "name"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="crm_kbc_tnt_active_idx"),
        ]

    def __str__(self):
        return f"{self.number} · {self.name}"


class CustomerPortalAccess(TenantNumbered):
    """Customer self-service portal login mapping (1.4). Mirrors ``PartnerPortalAccess`` (1.12):
    a ``portal_user`` is bound to a ``customer_party`` and only ever sees that party's cases."""

    NUMBER_PREFIX = "CSP"

    customer_party = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_customer_portal_accesses")
    portal_user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_customer_portal_access")
    can_submit_cases = models.BooleanField(default=True)
    accepted_at = models.DateTimeField(null=True, blank=True)  # system-set when the customer activates
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="crm_csp_tnt_active_idx"),
            models.Index(fields=["tenant", "customer_party"], name="crm_csp_tnt_party_idx"),
        ]

    def __str__(self):
        return f"{self.number} · {self.customer_party or 'Customer'}"


class CrmTask(TenantNumbered):
    """A to-do / call / follow-up (1.5). ``completed_at`` is system-set on done. Recurring tasks
    spawn the next open occurrence when completed (see ``_spawn_next_occurrence``)."""

    NUMBER_PREFIX = "TASK"

    TYPE_CHOICES = [
        ("todo", "To-Do"),
        ("call", "Call"),
        ("email", "Email"),
        ("meeting", "Meeting"),
        ("follow_up", "Follow-Up"),
    ]
    PRIORITY_CHOICES = [("low", "Low"), ("medium", "Medium"), ("high", "High")]
    STATUS_CHOICES = [
        ("open", "Open"),
        ("in_progress", "In Progress"),
        ("done", "Done"),
        ("cancelled", "Cancelled"),
    ]
    RECURRENCE_CHOICES = [
        ("none", "Does Not Repeat"),
        ("daily", "Daily"),
        ("weekly", "Weekly"),
        ("monthly", "Monthly"),
    ]
    OPEN_STATUSES = ["open", "in_progress"]

    subject = models.CharField(max_length=255)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="todo")
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default="medium")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open")
    due_date = models.DateField(null=True, blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_tasks")
    party = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_tasks")
    related_opportunity = models.ForeignKey("crm.Opportunity", on_delete=models.SET_NULL, null=True, blank=True, related_name="tasks")
    related_case = models.ForeignKey("crm.Case", on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_tasks")
    description = models.TextField(blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)  # system-set
    # ---- Automated recurring tasks (1.5) ----------------------------------------------------
    recurrence = models.CharField(max_length=10, choices=RECURRENCE_CHOICES, default="none")
    recurrence_interval = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1)])  # "every N"
    recurrence_until = models.DateField(null=True, blank=True)  # optional series end date
    # System-set: links a spawned occurrence back to the series origin (never on the form).
    recurrence_parent = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="recurrence_children")

    class Meta:
        ordering = ["due_date", "-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="crm_task_tenant_status_idx"),
            models.Index(fields=["tenant", "due_date", "created_at"], name="crm_task_tnt_due_created_idx"),
        ]

    @property
    def is_overdue(self):
        return bool(self.due_date and self.status in self.OPEN_STATUSES
                    and self.due_date < timezone.localdate())

    def save(self, *args, **kwargs):
        # Detect the open→done transition (drives recurrence spawn) before writing.
        prev_status = (type(self).objects.filter(pk=self.pk)
                       .values_list("status", flat=True).first()) if self.pk else None
        # System-set completed_at: stamp when first marked done, clear if re-opened.
        if self.status == "done":
            if self.completed_at is None:
                self.completed_at = timezone.now()
        else:
            self.completed_at = None
        # Atomic: the parent write + the spawned next occurrence commit or roll back together,
        # so a failed spawn never leaves a completed task with a broken recurrence chain.
        with transaction.atomic():
            super().save(*args, **kwargs)
            # Automated recurring tasks: on the first transition into "done", spawn the next open
            # occurrence. The transition guard (prev != done) prevents double-spawn on re-save and
            # stops the spawned open child from recursing.
            if (self.status == "done" and prev_status != "done"
                    and self.recurrence != "none" and self.due_date):
                self._spawn_next_occurrence()

    def _next_due(self):
        """Next occurrence's due date, advancing by ``recurrence_interval`` units. Stdlib only —
        python-dateutil is not installed, so monthly is computed with ``calendar.monthrange``."""
        n = self.recurrence_interval or 1
        if self.recurrence == "daily":
            return self.due_date + timedelta(days=n)
        if self.recurrence == "weekly":
            return self.due_date + timedelta(weeks=n)
        if self.recurrence == "monthly":
            idx = self.due_date.month - 1 + n
            year = self.due_date.year + idx // 12
            month = idx % 12 + 1
            day = min(self.due_date.day, calendar.monthrange(year, month)[1])  # clamp to month end
            return self.due_date.replace(year=year, month=month, day=day)
        return None

    def _spawn_next_occurrence(self):
        next_due = self._next_due()
        if next_due is None:
            return
        if self.recurrence_until and next_due > self.recurrence_until:
            return  # the series has ended
        origin = self.recurrence_parent or self
        # Idempotent: never create a duplicate occurrence at the same next due date. (self can't
        # match — its own due_date is the current value, not next_due — so no self-exclude needed.)
        if CrmTask.objects.filter(tenant=self.tenant, recurrence_parent=origin,
                                  due_date=next_due).exists():
            return
        CrmTask.objects.create(
            tenant=self.tenant, subject=self.subject, type=self.type,
            priority=self.priority, status="open", due_date=next_due,
            owner=self.owner, party=self.party,
            related_opportunity=self.related_opportunity, related_case=self.related_case,
            recurrence=self.recurrence, recurrence_interval=self.recurrence_interval,
            recurrence_until=self.recurrence_until, recurrence_parent=origin,
        )

    def __str__(self):
        return f"{self.number} · {self.subject}"


class CalendarEvent(TenantNumbered):
    """A scheduled event / meeting (1.5 Calendar Integration). Carries a ``public_token`` for the
    login-free invite/RSVP + ``.ics`` pages (mirrors ``Case.public_token``). External
    Google/Outlook/iCal sync is represented by ``sync_source`` + the ICS export — OAuth push/pull
    is deferred."""

    NUMBER_PREFIX = "EVT"

    TYPE_CHOICES = [
        ("meeting", "Meeting"),
        ("call", "Call"),
        ("demo", "Demo"),
        ("deadline", "Deadline"),
        ("reminder", "Reminder"),
        ("other", "Other"),
    ]
    STATUS_CHOICES = [
        ("scheduled", "Scheduled"),
        ("confirmed", "Confirmed"),
        ("cancelled", "Cancelled"),
        ("completed", "Completed"),
    ]
    SYNC_SOURCE_CHOICES = [
        ("manual", "Manual"),
        ("google", "Google Calendar"),
        ("outlook", "Outlook"),
        ("ical", "iCal"),
    ]

    title = models.CharField(max_length=255)
    event_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="meeting")
    start = models.DateTimeField()
    end = models.DateTimeField(null=True, blank=True)
    all_day = models.BooleanField(default=False)
    location = models.CharField(max_length=255, blank=True)
    video_url = models.URLField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="scheduled")
    sync_source = models.CharField(max_length=10, choices=SYNC_SOURCE_CHOICES, default="manual")
    reminder_minutes = models.PositiveSmallIntegerField(default=15, null=True, blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_calendar_events")
    party = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_calendar_events")
    related_opportunity = models.ForeignKey("crm.Opportunity", on_delete=models.SET_NULL, null=True, blank=True, related_name="calendar_events")
    related_case = models.ForeignKey("crm.Case", on_delete=models.SET_NULL, null=True, blank=True, related_name="calendar_events")
    description = models.TextField(blank=True)
    # Unguessable bearer token for the public invite/RSVP/ICS endpoints (no login). System-set;
    # editable=False keeps it off every form/admin (mirrors Case/LandingPage/KnowledgeArticle tokens).
    public_token = models.CharField(max_length=64, unique=True, editable=False, blank=True)

    class Meta:
        ordering = ["-start"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="crm_calevent_tenant_status_idx"),
            models.Index(fields=["tenant", "start"], name="crm_calevent_tenant_start_idx"),
        ]

    @property
    def is_past(self):
        return bool(self.start and self.start < timezone.now())

    @property
    def duration_display(self):
        """``H:MM`` span when both ends are set, else ``""``."""
        if self.start and self.end and self.end > self.start:
            minutes = int((self.end - self.start).total_seconds() // 60)
            return "%d:%02d" % divmod(minutes, 60)
        return ""

    def save(self, *args, **kwargs):
        if not self.public_token:
            self.public_token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.number} · {self.title}"


class EventAttendee(models.Model):
    """An invitee on a ``CalendarEvent`` (1.5). Plain child row (mirrors ``CaseComment``) — no
    auto-number. ``responded_at`` is system-set when the RSVP leaves ``no_response``. ``email`` is
    NULLed when blank so multiple party-only attendees don't collide on ``unique_together``."""

    RSVP_CHOICES = [
        ("no_response", "No Response"),
        ("accepted", "Accepted"),
        ("declined", "Declined"),
        ("tentative", "Tentative"),
    ]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="+", db_index=True)
    event = models.ForeignKey("crm.CalendarEvent", on_delete=models.CASCADE, related_name="attendees")
    party = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="event_attendees")
    name = models.CharField(max_length=255)
    email = models.EmailField(null=True, blank=True)  # NULL (not "") when blank — see save()
    rsvp_status = models.CharField(max_length=20, choices=RSVP_CHOICES, default="no_response")
    is_organizer = models.BooleanField(default=False)
    responded_at = models.DateTimeField(null=True, blank=True)  # system-set on RSVP
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_organizer", "name"]
        # One row per (event, email); blank email stored as NULL so several party-only attendees
        # (no email) are allowed — MySQL/MariaDB exempt NULLs from a UNIQUE index.
        unique_together = ("event", "email")

    def save(self, *args, **kwargs):
        if not self.email:
            self.email = None
        if self.rsvp_status != "no_response" and self.responded_at is None:
            self.responded_at = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.get_rsvp_status_display()})"


class CommunicationLog(TenantNumbered):
    """A logged interaction — call/email/sms/note/meeting (1.5 Email & Call Integration). The
    unified activity-history record: call logging (duration/outcome) + email sync (BCC dropbox).
    Live send/receive engines are deferred; ``logged_via`` records provenance."""

    NUMBER_PREFIX = "COM"

    CHANNEL_CHOICES = [
        ("call", "Call"),
        ("email", "Email"),
        ("sms", "SMS"),
        ("note", "Note"),
        ("meeting", "Meeting"),
    ]
    DIRECTION_CHOICES = [("inbound", "Inbound"), ("outbound", "Outbound")]
    OUTCOME_CHOICES = [
        ("connected", "Connected"),
        ("voicemail", "Voicemail"),
        ("no_answer", "No Answer"),
        ("busy", "Busy"),
        ("wrong_number", "Wrong Number"),
    ]
    LOGGED_VIA_CHOICES = [
        ("manual", "Manual"),
        ("bcc_dropbox", "BCC Dropbox"),
        ("voip", "VoIP Auto-log"),
        ("sync", "Calendar Sync"),
    ]

    channel = models.CharField(max_length=10, choices=CHANNEL_CHOICES, default="call")
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES, blank=True)
    subject = models.CharField(max_length=255, blank=True)
    body = models.TextField(blank=True)
    party = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="communication_logs")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="communication_logs")
    related_opportunity = models.ForeignKey("crm.Opportunity", on_delete=models.SET_NULL, null=True, blank=True, related_name="communication_logs")
    related_case = models.ForeignKey("crm.Case", on_delete=models.SET_NULL, null=True, blank=True, related_name="communication_logs")
    occurred_at = models.DateTimeField(default=timezone.now)  # the actual interaction time
    duration_seconds = models.PositiveIntegerField(null=True, blank=True)  # calls only
    outcome = models.CharField(max_length=20, choices=OUTCOME_CHOICES, blank=True)  # calls only
    logged_via = models.CharField(max_length=20, choices=LOGGED_VIA_CHOICES, default="manual")
    email_message_id = models.CharField(max_length=255, blank=True, db_index=True)  # dedup synced email

    class Meta:
        ordering = ["-occurred_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "channel"], name="crm_commlog_tnt_channel_idx"),
            models.Index(fields=["tenant", "occurred_at"], name="crm_commlog_tnt_occurred_idx"),
        ]

    @property
    def duration_display(self):
        """``mm:ss`` for a call duration, else ``""``."""
        if self.duration_seconds is not None:
            return "%d:%02d" % divmod(self.duration_seconds, 60)
        return ""

    @property
    def is_call(self):
        return self.channel == "call"

    def __str__(self):
        return f"{self.number} · {self.get_channel_display()} ({self.occurred_at:%Y-%m-%d})"


# ============================ Accounts & Contacts — CRM profile extensions (1.1) =============
# Accounts and Contacts ARE the shared ``core.Party`` (one identity, many roles). These CRM-owned
# one-to-one extensions add the rich CRM attributes (firmographics, contact details, hierarchy)
# WITHOUT polluting the spine. The Party holds name/tax_id/kind; the profile holds everything else.
# Contact info is stored flat here for a single-form CRM UX; the normalized core.Address /
# core.ContactMethod remain available for advanced multi-value needs.

INDUSTRY_CHOICES = [
    ("technology", "Technology"),
    ("finance", "Finance & Banking"),
    ("healthcare", "Healthcare"),
    ("manufacturing", "Manufacturing"),
    ("retail", "Retail & E-commerce"),
    ("education", "Education"),
    ("real_estate", "Real Estate"),
    ("energy", "Energy & Utilities"),
    ("media", "Media & Entertainment"),
    ("professional_services", "Professional Services"),
    ("construction", "Construction"),
    ("transportation", "Transportation & Logistics"),
    ("hospitality", "Hospitality"),
    ("nonprofit", "Non-Profit"),
    ("government", "Government"),
    ("other", "Other"),
]


class AccountProfile(models.Model):
    """CRM firmographic + contact-detail extension for an organization ``core.Party``."""

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="+", db_index=True)
    party = models.OneToOneField("core.Party", on_delete=models.CASCADE, related_name="crm_account_profile")
    industry = models.CharField(max_length=40, choices=INDUSTRY_CHOICES, blank=True)
    website = models.URLField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    email = models.EmailField(blank=True)
    annual_revenue = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    employee_count = models.PositiveIntegerField(default=0)
    parent_account = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_child_account_profiles")
    address_line = models.CharField(max_length=255, blank=True)
    address_city = models.CharField(max_length=120, blank=True)
    address_state = models.CharField(max_length=120, blank=True)
    address_postal = models.CharField(max_length=20, blank=True)
    address_country = models.CharField(max_length=120, blank=True)
    source = models.CharField(max_length=20, choices=Lead.SOURCE_CHOICES, blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_account_profiles")
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["party__name"]
        indexes = [
            models.Index(fields=["tenant", "industry"], name="crm_accp_tnt_industry_idx"),
            models.Index(fields=["tenant", "source"], name="crm_accp_tnt_source_idx"),
            models.Index(fields=["tenant", "parent_account"], name="crm_accp_tnt_parent_idx"),
        ]

    def __str__(self):
        return f"Account · {self.party.name}"


class ContactProfile(models.Model):
    """CRM contact-detail extension for a person ``core.Party`` (job, phone, address, employer)."""

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="+", db_index=True)
    party = models.OneToOneField("core.Party", on_delete=models.CASCADE, related_name="crm_contact_profile")
    job_title = models.CharField(max_length=120, blank=True)
    department = models.CharField(max_length=120, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    mobile = models.CharField(max_length=40, blank=True)
    account = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_account_contacts")
    address_line = models.CharField(max_length=255, blank=True)
    address_city = models.CharField(max_length=120, blank=True)
    address_state = models.CharField(max_length=120, blank=True)
    address_postal = models.CharField(max_length=20, blank=True)
    address_country = models.CharField(max_length=120, blank=True)
    linkedin = models.URLField(blank=True)
    source = models.CharField(max_length=20, choices=Lead.SOURCE_CHOICES, blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_contact_profiles")
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["party__name"]
        indexes = [
            models.Index(fields=["tenant", "source"], name="crm_conp_tnt_source_idx"),
            models.Index(fields=["tenant", "account"], name="crm_conp_tnt_account_idx"),
        ]

    def __str__(self):
        return f"Contact · {self.party.name}"


# ============================================================================
# ===== Module 1 Extension — Sub-modules 1.7–1.12 ============================
# ============================================================================
# These reuse the unified core spine WHERE IT EXISTS TODAY (``core.Party`` for
# accounts/vendors/partners, ``settings.AUTH_USER_MODEL``, and the existing
# ``crm.Opportunity``/``crm.Case``). The Item / Currency / AR-AP ledger / StockMove /
# PurchaseOrder masters belong to the not-yet-built Accounting (2), Inventory (5)
# and Procurement (6) modules, so 1.12 ships CRM-owned PurchaseOrder/Line/ProductStock
# tables and 1.7 stores a currency *code* string. These can migrate onto the spine
# once those modules land — see ``.claude/tasks/todo.md`` "Spine-gap adaptation".


# -------------------------------------------------- 1.7 Finance & Billing Management
class Expense(TenantNumbered):
    """A deal/project-related cost (1.7) used to derive true opportunity profit margin."""

    NUMBER_PREFIX = "EXP"

    CATEGORY_CHOICES = [
        ("travel", "Travel"),
        ("meals", "Meals"),
        ("software", "Software"),
        ("accommodation", "Accommodation"),
        ("other", "Other"),
    ]
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("submitted", "Submitted"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    opportunity = models.ForeignKey("crm.Opportunity", on_delete=models.SET_NULL, null=True, blank=True, related_name="expenses")
    project = models.ForeignKey("crm.CrmProject", on_delete=models.SET_NULL, null=True, blank=True, related_name="expenses")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="travel")
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency_code = models.CharField(max_length=3, default="USD")  # core.Currency master not built yet
    expense_date = models.DateField()
    description = models.TextField(blank=True)
    receipt = models.FileField(upload_to="crm/receipts/%Y/%m/", blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_submitted_expenses")
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_approved_expenses")
    is_billable = models.BooleanField(
        default=False,
        help_text="Billable costs are re-billed to the client, so they are excluded from the deal's true margin.")

    class Meta:
        ordering = ["-expense_date", "-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="crm_exp_tnt_status_idx"),
            models.Index(fields=["tenant", "expense_date"], name="crm_exp_tnt_date_idx"),
            models.Index(fields=["tenant", "opportunity"], name="crm_exp_tnt_opp_idx"),
        ]

    def __str__(self):
        return f"{self.number} · {self.get_category_display()} {self.amount}"


# ---- 1.7 Invoicing — a CRM wrapper over the ACCOUNTING ledger ----------------------------
# The real AR invoice is an ``accounting.Invoice`` (Module 2 owns the ledger — lesson L29: reuse
# it, never build a second one). ``DealInvoice`` records the *deal context* (opportunity / quote /
# account) of a generated invoice and is created by the one-click quote→invoice conversion
# (``dealinvoice_from_quote``). Issuing / GL-posting + confirmed cash-application stay in
# Accounting (draft hand-off) — CRM only creates the draft and links it.
class DealInvoice(TenantNumbered):
    """Links a CRM deal (Opportunity / Quote) to the ``accounting.Invoice`` it generated."""

    NUMBER_PREFIX = "DINV"

    opportunity = models.ForeignKey("crm.Opportunity", on_delete=models.SET_NULL, null=True, blank=True, related_name="deal_invoices")
    quote = models.ForeignKey("crm.Quote", on_delete=models.SET_NULL, null=True, blank=True, related_name="deal_invoices")
    account = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_deal_invoices")
    # The generated ledger document (system-of-record). editable=False → set by the view/seeder,
    # never accepted from a form (a user must not re-point a wrapper at an arbitrary invoice).
    invoice = models.ForeignKey("accounting.Invoice", on_delete=models.SET_NULL, null=True, blank=True, editable=False, related_name="crm_deal_invoices")
    # Optional subscription schedule — recurring billing also lives in the ledger.
    recurring_invoice = models.ForeignKey("accounting.RecurringInvoice", on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_deal_invoices")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "opportunity"], name="crm_dinv_tnt_opp_idx"),
            models.Index(fields=["tenant", "created_at"], name="crm_dinv_tnt_created_idx"),
        ]

    def __str__(self):
        return f"{self.number} · {self.invoice_number}"

    # Totals / status / paid amounts are READ THROUGH to the linked ledger invoice — never copied
    # here, so there is a single source of truth. Every accessor guards a missing/unlinked invoice.
    @property
    def invoice_number(self):
        return self.invoice.number if self.invoice_id else "—"

    @property
    def invoice_status(self):
        return self.invoice.status if self.invoice_id else "unlinked"

    @property
    def invoice_status_display(self):
        return self.invoice.get_status_display() if self.invoice_id else "Unlinked"

    @property
    def invoice_total(self):
        return self.invoice.total if self.invoice_id else Decimal("0")

    @property
    def amount_paid(self):
        return self.invoice.amount_paid() if self.invoice_id else Decimal("0")

    @property
    def balance_due(self):
        return self.invoice.balance_due() if self.invoice_id else Decimal("0")


# ---- 1.7 Payment Tracking — a CRM receipt document over a ledger payment -----------------
class PaymentReceipt(TenantNumbered):
    """A customer receipt for a (partial / milestone) payment against a deal invoice.

    The money movement itself is an ``accounting.Payment`` (optional link); this model is the CRM
    receipt *document* (printable) plus payment-gateway metadata. Real gateway webhooks (Stripe /
    PayPal / Razorpay charge confirmation) are deferred — the gateway fields capture the reference."""

    NUMBER_PREFIX = "RCPT"

    METHOD_CHOICES = [
        ("bank_transfer", "Bank Transfer"),
        ("card", "Card"),
        ("cash", "Cash"),
        ("check", "Check"),
        ("paypal", "PayPal"),
        ("stripe", "Stripe"),
        ("razorpay", "Razorpay"),
        ("ach", "ACH"),
        ("wire", "Wire Transfer"),
        ("other", "Other"),
    ]
    GATEWAY_CHOICES = [
        ("manual", "Manual / Offline"),
        ("stripe", "Stripe"),
        ("paypal", "PayPal"),
        ("razorpay", "Razorpay"),
    ]

    deal_invoice = models.ForeignKey("crm.DealInvoice", on_delete=models.CASCADE, related_name="receipts")
    # Optional link to the ledger money movement (Module 2 owns Payment + cash application).
    payment = models.ForeignKey("accounting.Payment", on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_receipts")
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    received_date = models.DateField()
    method = models.CharField(max_length=16, choices=METHOD_CHOICES, default="bank_transfer")
    gateway = models.CharField(max_length=12, choices=GATEWAY_CHOICES, default="manual")
    gateway_txn_id = models.CharField(max_length=120, blank=True, help_text="External gateway charge / transaction id.")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-received_date", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "received_date"], name="crm_rcpt_tnt_date_idx"),
        ]

    def __str__(self):
        return f"{self.number} · {self.amount}"


# -------------------------------------------- 1.8 Project & Delivery Management (Post-Sale)
class CrmProject(TenantNumbered):
    """A post-sale delivery project (1.8), often auto-created from a won Opportunity."""

    NUMBER_PREFIX = "PRJ"

    STATUS_CHOICES = [
        ("planning", "Planning"),
        ("active", "Active"),
        ("on_hold", "On Hold"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    name = models.CharField(max_length=255)
    account = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_projects")
    source_opportunity = models.ForeignKey("crm.Opportunity", on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_projects")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="planning")
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    budget = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_projects")
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="crm_prj_tnt_status_idx"),
            models.Index(fields=["tenant", "created_at"], name="crm_prj_tnt_created_idx"),
        ]

    def __str__(self):
        return f"{self.number} · {self.name}"

    @property
    def progress_pct(self):
        """Completed milestones ÷ total, as a 0–100 int. Uses the list view's ``ms_total``/
        ``ms_done`` annotations when present (no N+1); falls back to a count on the detail page."""
        total = getattr(self, "ms_total", None)
        done = getattr(self, "ms_done", None)
        if total is None:
            total = self.milestones.count()
            done = self.milestones.filter(status="completed").count()
        return round(done * 100 / total) if total else 0

    @property
    def is_overdue(self):
        return bool(self.end_date and self.status not in ("completed", "cancelled")
                    and self.end_date < timezone.localdate())


class CrmMilestone(TenantNumbered):
    """A milestone/task within a project (1.8). ``completed_at`` is system-set on done."""

    NUMBER_PREFIX = "MS"

    KIND_CHOICES = [("milestone", "Milestone"), ("task", "Task")]
    STATUS_CHOICES = [
        ("not_started", "Not Started"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("blocked", "Blocked"),
    ]

    project = models.ForeignKey("crm.CrmProject", on_delete=models.CASCADE, related_name="milestones")
    title = models.CharField(max_length=255)
    kind = models.CharField(max_length=12, choices=KIND_CHOICES, default="task")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="not_started")
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_milestones")
    start_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)  # system-set
    order = models.PositiveSmallIntegerField(default=0)
    parent = models.ForeignKey("crm.CrmMilestone", on_delete=models.SET_NULL, null=True, blank=True, related_name="subtasks")
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["order", "due_date", "-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "project", "status"], name="crm_ms_tnt_prj_status_idx"),
            models.Index(fields=["tenant", "due_date"], name="crm_ms_tnt_due_idx"),
        ]

    def save(self, *args, **kwargs):
        # System-set completed_at: stamp on first completion, clear if re-opened.
        if self.status == "completed":
            if self.completed_at is None:
                self.completed_at = timezone.now()
        else:
            self.completed_at = None
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.number} · {self.title}"


class Timesheet(TenantNumbered):
    """A billable/non-billable time entry against a project (1.8)."""

    NUMBER_PREFIX = "TS"

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("submitted", "Submitted"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    project = models.ForeignKey("crm.CrmProject", on_delete=models.CASCADE, related_name="timesheets")
    milestone = models.ForeignKey("crm.CrmMilestone", on_delete=models.SET_NULL, null=True, blank=True, related_name="timesheets")
    employee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_timesheets")
    client = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_timesheets")
    date = models.DateField()
    hours = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    description = models.TextField(blank=True)
    is_billable = models.BooleanField(default=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_approved_timesheets")

    class Meta:
        ordering = ["-date", "-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "project", "date"], name="crm_ts_tnt_prj_date_idx"),
            models.Index(fields=["tenant", "employee", "date"], name="crm_ts_tnt_emp_date_idx"),
            models.Index(fields=["tenant", "status"], name="crm_ts_tnt_status_idx"),
        ]

    def __str__(self):
        return f"{self.number} · {self.hours}h"


# ---- 1.8 Resource Allocation — planned capacity bookings + a workload board -------------
class ResourceAllocation(TenantNumbered):
    """A planned capacity booking (1.8 Resource Allocation): assigns a person to a project for
    ``hours_per_week`` over a date window. The workload board aggregates these (planned) against
    logged ``Timesheet`` hours (actual) per person to flag overbooked vs. free capacity. People are
    keyed on ``User`` (matching ``Timesheet.employee`` / ``CrmMilestone.assignee``) so both sides of
    the workload join share one key — a future pass could move to HRM ``EmployeeProfile``."""

    NUMBER_PREFIX = "RA"

    STATUS_CHOICES = [
        ("planned", "Planned"),
        ("active", "Active"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    project = models.ForeignKey("crm.CrmProject", on_delete=models.CASCADE, related_name="allocations")
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_allocations")
    role = models.CharField(max_length=80, blank=True, help_text="e.g. Developer, Project Manager, QA")
    hours_per_week = models.DecimalField(max_digits=5, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True, help_text="Leave blank for an ongoing assignment.")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="active")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "assignee"], name="crm_ra_tnt_assignee_idx"),
            models.Index(fields=["tenant", "project"], name="crm_ra_tnt_project_idx"),
            # The workload board filters by status + a start/end date window (performance-review).
            models.Index(fields=["tenant", "status"], name="crm_ra_tnt_status_idx"),
            models.Index(fields=["tenant", "start_date"], name="crm_ra_tnt_start_idx"),
            models.Index(fields=["tenant", "end_date"], name="crm_ra_tnt_end_idx"),
        ]

    def __str__(self):
        return f"{self.number} · {self.role or 'Resource'}"

    def overlap_hours(self, win_start, win_end):
        """Planned hours for this booking within [win_start, win_end], prorated by overlapping days.
        A null ``end_date`` means ongoing → clamped to the window end. Cancelled bookings count 0."""
        if self.status == "cancelled":
            return Decimal("0")
        a_end = self.end_date or win_end  # null = ongoing
        ov_start = max(self.start_date, win_start)
        ov_end = min(a_end, win_end)
        if ov_end < ov_start:
            return Decimal("0")
        days = (ov_end - ov_start).days + 1
        return (Decimal(self.hours_per_week or 0) * Decimal(days) / Decimal(7)).quantize(Decimal("0.01"))


# ----------------------------------------------------- 1.9 Document & Contract Management
class DocTemplate(TenantNumbered):
    """A reusable HTML document template with Django merge variables (1.9)."""

    NUMBER_PREFIX = "TPL"

    TYPE_CHOICES = [
        ("nda", "NDA"),
        ("proposal", "Proposal"),
        ("contract", "Contract"),
        ("quote", "Quote"),
        ("receipt", "Receipt"),
    ]

    name = models.CharField(max_length=255)
    template_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="contract")
    body = models.TextField(blank=True)  # HTML with {{ account.name }} / {{ opportunity.amount }} / {{ today }}
    is_active = models.BooleanField(default=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_doc_templates")

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "template_type"], name="crm_tpl_tnt_type_idx"),
            models.Index(fields=["tenant", "is_active"], name="crm_tpl_tnt_active_idx"),
        ]

    def __str__(self):
        return f"{self.number} · {self.name}"


class ContractDocument(TenantNumbered):
    """A rendered document instance with e-signature tracking + versioning (1.9)."""

    NUMBER_PREFIX = "CTR"

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("sent", "Sent"),
        ("viewed", "Viewed"),
        ("signed", "Signed"),
        ("declined", "Declined"),
        ("expired", "Expired"),
        ("archived", "Archived"),
    ]

    name = models.CharField(max_length=255)
    template = models.ForeignKey("crm.DocTemplate", on_delete=models.SET_NULL, null=True, blank=True, related_name="contracts")
    opportunity = models.ForeignKey("crm.Opportunity", on_delete=models.SET_NULL, null=True, blank=True, related_name="contracts")
    account = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_contracts")
    current_version = models.PositiveSmallIntegerField(default=1)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="draft")
    body_snapshot = models.TextField(blank=True)  # merge-resolved HTML captured at send time
    signed_at = models.DateTimeField(null=True, blank=True)  # system-set when all signers sign
    expires_at = models.DateTimeField(null=True, blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_contracts")

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="crm_ctr_tnt_status_idx"),
            models.Index(fields=["tenant", "opportunity"], name="crm_ctr_tnt_opp_idx"),
            models.Index(fields=["tenant", "created_at"], name="crm_ctr_tnt_created_idx"),
            # The File Repository filters contracts by account (performance-review).
            models.Index(fields=["tenant", "account"], name="crm_ctr_tnt_account_idx"),
        ]

    def __str__(self):
        return f"{self.number} · {self.name}"


class SignerRecord(models.Model):
    """One signer per contract (1.9). Accessed only through its parent ContractDocument."""

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="+", db_index=True)
    contract = models.ForeignKey("crm.ContractDocument", on_delete=models.CASCADE, related_name="signers")
    signer_party = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_signer_records")
    signer_name = models.CharField(max_length=255)
    signer_email = models.EmailField()
    token = models.CharField(max_length=64, unique=True)  # URL-safe random token for the signing link
    order = models.PositiveSmallIntegerField(default=1)
    viewed_at = models.DateTimeField(null=True, blank=True)
    signed_at = models.DateTimeField(null=True, blank=True)
    declined_at = models.DateTimeField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.signer_name} <{self.signer_email}>"


# ---- 1.9 File Repository — version-controlled contract revisions -------------------------
class DocumentVersion(models.Model):
    """An **immutable** revision of a ContractDocument (1.9 File Repository / version control).
    Each generate-from-template or file upload creates one; ``ContractDocument.current_version``
    points at the latest ``version_no``. Plain tenant-scoped child — accessed through its parent
    contract; list+detail only, never edited (an audit-grade revision log, like ``WorkflowLog``).
    Contract-revision history is CRM-specific; the generic ``core.Document`` attachment + the future
    Module 13 DMS are a separate, broader repository."""

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="+", db_index=True)
    contract = models.ForeignKey("crm.ContractDocument", on_delete=models.CASCADE, related_name="versions")
    version_no = models.PositiveSmallIntegerField(default=1)
    body_snapshot = models.TextField(blank=True)  # the contract HTML captured at this revision
    file = models.FileField(upload_to="crm/contracts/%Y/%m/", blank=True, null=True)  # uploaded artifact (e.g. signed PDF)
    change_note = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_doc_versions")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-version_no"]
        unique_together = ("tenant", "contract", "version_no")
        indexes = [models.Index(fields=["tenant", "contract"], name="crm_dv_tnt_contract_idx")]

    def __str__(self):
        return f"{self.contract.number} v{self.version_no}"


# ------------------------------------------------------ 1.10 Automation & Workflow Engine
class WorkflowRule(TenantNumbered):
    """A declarative trigger-condition-action automation rule (1.10)."""

    NUMBER_PREFIX = "WFR"

    ENTITY_CHOICES = [
        ("lead", "Lead"),
        ("opportunity", "Opportunity"),
        ("case", "Case"),
        ("expense", "Expense"),
        ("contract", "Contract"),
        ("health_score", "Health Score"),
    ]
    EVENT_CHOICES = [
        ("created", "Created"),
        ("updated", "Updated"),
        ("status_changed", "Status Changed"),
        ("field_value", "Field Value Matches"),
        ("date_reached", "Date Reached"),
    ]
    DELAY_CHOICES = [("minutes", "Minutes"), ("hours", "Hours"), ("days", "Days")]

    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    trigger_entity = models.CharField(max_length=20, choices=ENTITY_CHOICES, default="opportunity")
    trigger_event = models.CharField(max_length=20, choices=EVENT_CHOICES, default="created")
    trigger_field = models.CharField(max_length=100, blank=True)
    trigger_value = models.CharField(max_length=255, blank=True)
    conditions = models.JSONField(default=list, blank=True)  # [{field, operator, value}] (AND)
    actions = models.JSONField(default=list, blank=True)      # [{type, params}]
    delay_value = models.PositiveSmallIntegerField(null=True, blank=True)
    delay_unit = models.CharField(max_length=10, choices=DELAY_CHOICES, blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_workflow_rules")

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="crm_wfr_tnt_active_idx"),
            models.Index(fields=["tenant", "trigger_entity"], name="crm_wfr_tnt_entity_idx"),
        ]

    def __str__(self):
        return f"{self.number} · {self.name}"


class WorkflowLog(models.Model):
    """Immutable append-only fire-record for a WorkflowRule execution (1.10)."""

    STATUS_CHOICES = [("success", "Success"), ("failed", "Failed"), ("skipped", "Skipped")]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="+", db_index=True)
    rule = models.ForeignKey("crm.WorkflowRule", on_delete=models.SET_NULL, null=True, related_name="logs")
    record_label = models.CharField(max_length=255)
    fired_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="success")
    error_msg = models.TextField(blank=True)

    class Meta:
        ordering = ["-fired_at"]
        indexes = [
            models.Index(fields=["tenant", "status"], name="crm_wfl_tnt_status_idx"),
            models.Index(fields=["tenant", "fired_at"], name="crm_wfl_tnt_fired_idx"),
            # rule detail shows this rule's recent logs; (tenant, rule, -fired_at) makes it a range scan (perf-review).
            models.Index(fields=["tenant", "rule", "-fired_at"], name="crm_wfl_tnt_rule_fired_idx"),
        ]

    def __str__(self):
        return f"{self.record_label} · {self.status}"


class ApprovalRequest(TenantNumbered):
    """A generic approval gate, e.g. a discount lock until a manager approves (1.10)."""

    NUMBER_PREFIX = "APR"

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("expired", "Expired"),
    ]

    rule = models.ForeignKey("crm.WorkflowRule", on_delete=models.SET_NULL, null=True, blank=True, related_name="approvals")
    subject = models.CharField(max_length=255)
    record_label = models.CharField(max_length=255, blank=True)
    approver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_approvals_to_action")
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_approvals_requested")
    threshold_field = models.CharField(max_length=100, blank=True)
    threshold_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    approved_at = models.DateTimeField(null=True, blank=True)  # system-set
    rejected_at = models.DateTimeField(null=True, blank=True)  # system-set
    reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="crm_apr_tnt_status_idx"),
            models.Index(fields=["tenant", "approver"], name="crm_apr_tnt_approver_idx"),
            models.Index(fields=["tenant", "created_at"], name="crm_apr_tnt_created_idx"),
        ]

    @property
    def is_pending(self):
        return self.status == "pending"

    def __str__(self):
        return f"{self.number} · {self.subject}"


# ---- 1.10 Webhooks — outbound event push (config + signed delivery log) ------------------
class Webhook(TenantNumbered):
    """An outbound webhook endpoint (1.10). A WorkflowRule's ``webhook`` action (or a manual test)
    builds a JSON payload, HMAC-signs it with ``secret``, and records a :class:`WebhookDelivery`.
    The real outbound HTTP POST is **deferred** — see the SSRF ``# WARNING`` on the delivery helper
    in views.py. Reuses ``WorkflowRule``'s entity/event vocab so a rule fires the matching webhooks."""

    NUMBER_PREFIX = "WH"

    name = models.CharField(max_length=255)
    target_url = models.URLField(max_length=500)
    trigger_entity = models.CharField(max_length=20, choices=WorkflowRule.ENTITY_CHOICES, default="opportunity")
    trigger_event = models.CharField(max_length=20, choices=WorkflowRule.EVENT_CHOICES, default="created")
    # WARNING: a signing secret — write-only. Excluded from the bound edit render (PasswordInput,
    # render_value=False) so it's never shipped back to the browser; used only to HMAC-sign payloads.
    secret = models.CharField(max_length=128, blank=True, help_text="HMAC signing key — write-only (never shown after saving).")
    is_active = models.BooleanField(default=True)
    headers = models.JSONField(default=dict, blank=True)  # optional custom request headers
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="crm_wh_tnt_active_idx"),
            models.Index(fields=["tenant", "trigger_entity"], name="crm_wh_tnt_entity_idx"),
        ]

    def __str__(self):
        return f"{self.number} · {self.name}"

    @property
    def secret_masked(self):
        s = self.secret or ""
        return f"••••{s[-4:]}" if len(s) >= 4 else ("(set)" if s else "(none)")


class WebhookDelivery(models.Model):
    """Immutable append-only delivery record for a :class:`Webhook` (1.10). Captures the signed payload
    + outcome of one fire. Real outbound HTTP is deferred (status starts ``pending``). Accessed
    list+detail only — never edited (an audit-grade log, like :class:`WorkflowLog`)."""

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("success", "Success"),
        ("failed", "Failed"),
        ("simulated", "Simulated"),
    ]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="+", db_index=True)
    webhook = models.ForeignKey("crm.Webhook", on_delete=models.CASCADE, related_name="deliveries")
    event = models.CharField(max_length=60)
    payload = models.TextField(blank=True)  # the JSON body that would be POSTed
    signature = models.CharField(max_length=128, blank=True)  # HMAC-SHA256 hex of the payload
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    response_code = models.PositiveSmallIntegerField(null=True, blank=True)
    error_msg = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "webhook"], name="crm_whd_tnt_webhook_idx"),
            models.Index(fields=["tenant", "status"], name="crm_whd_tnt_status_idx"),
        ]

    def __str__(self):
        return f"{self.webhook_id} · {self.event} · {self.status}"


# ----------------------------------------------------- 1.11 Customer Success & Retention
class OnboardingPlan(TenantNumbered):
    """A per-client onboarding checklist (1.11). ``progress_pct`` is derived from steps."""

    NUMBER_PREFIX = "CS"

    STATUS_CHOICES = [
        ("active", "Active"),
        ("completed", "Completed"),
        ("on_hold", "On Hold"),
        ("cancelled", "Cancelled"),
    ]

    account = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_onboarding_plans")
    name = models.CharField(max_length=255)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="active")
    target_date = models.DateField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)  # system-set when all steps done
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_onboarding_plans")
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "account"], name="crm_obp_tnt_account_idx"),
            models.Index(fields=["tenant", "status"], name="crm_obp_tnt_status_idx"),
        ]

    @property
    def progress_pct(self):
        steps = list(self.steps.all())
        if not steps:
            return 0
        done = sum(1 for s in steps if s.completed_at is not None)
        return round(done / len(steps) * 100)

    def __str__(self):
        return f"{self.number} · {self.name}"


class OnboardingStep(models.Model):
    """An ordered checklist item within an OnboardingPlan (1.11)."""

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="+", db_index=True)
    plan = models.ForeignKey("crm.OnboardingPlan", on_delete=models.CASCADE, related_name="steps")
    order = models.PositiveSmallIntegerField(default=0)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_onboarding_steps")
    due_date = models.DateField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)  # system-set on completion
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.title


class HealthScoreConfig(models.Model):
    """Per-tenant configurable signal weights + tier thresholds for health scoring (1.11).

    Signals are the CRM data that exists today (tickets/nps/tasks/engagement). The
    Accounting ledger (invoice/payment punctuality) is not built yet, so there is no
    ``payments`` signal — add it when Module 2 lands.
    """

    tenant = models.OneToOneField("core.Tenant", on_delete=models.CASCADE, related_name="crm_health_config")
    weight_tickets = models.DecimalField(max_digits=5, decimal_places=2, default=25)
    weight_nps = models.DecimalField(max_digits=5, decimal_places=2, default=25)
    weight_tasks = models.DecimalField(max_digits=5, decimal_places=2, default=25)
    weight_engagement = models.DecimalField(max_digits=5, decimal_places=2, default=25)
    red_threshold = models.PositiveSmallIntegerField(default=40)     # score below = Red
    yellow_threshold = models.PositiveSmallIntegerField(default=70)  # score below = Yellow
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Health config · {self.tenant}"


class HealthScore(TenantNumbered):
    """A 0–100 customer-health score per account (1.11), recomputed in place."""

    NUMBER_PREFIX = "HS"

    TIER_CHOICES = [
        ("green", "Green — Healthy"),
        ("yellow", "Yellow — At Risk"),
        ("red", "Red — Critical"),
    ]

    account = models.ForeignKey("core.Party", on_delete=models.CASCADE, related_name="crm_health_scores")
    score = models.PositiveSmallIntegerField(default=0, validators=[MaxValueValidator(100)])
    tier = models.CharField(max_length=10, choices=TIER_CHOICES, default="green")
    breakdown = models.JSONField(default=dict, blank=True)  # {tickets, nps, tasks, engagement}
    computed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["score", "-updated_at"]  # lowest = most at-risk first
        unique_together = (("tenant", "number"), ("tenant", "account"))
        indexes = [
            models.Index(fields=["tenant", "tier"], name="crm_hs_tnt_tier_idx"),
            models.Index(fields=["tenant", "computed_at"], name="crm_hs_tnt_computed_idx"),
        ]

    def __str__(self):
        return f"{self.number} · {self.score} ({self.tier})"


class Survey(TenantNumbered):
    """An NPS/CSAT/CES survey + response (1.11). ``classification`` is auto-set for NPS."""

    NUMBER_PREFIX = "NPS"

    TYPE_CHOICES = [("nps", "NPS"), ("csat", "CSAT"), ("ces", "CES")]
    TRIGGER_CHOICES = [
        ("manual", "Manual"),
        ("post_close", "Post Close Won"),
        ("post_ticket", "Post Ticket Close"),
        ("scheduled", "Scheduled"),
    ]
    CLASSIFICATION_CHOICES = [
        # NPS
        ("promoter", "Promoter"),
        ("passive", "Passive"),
        ("detractor", "Detractor"),
        # CSAT
        ("satisfied", "Satisfied"),
        ("neutral", "Neutral"),
        ("dissatisfied", "Dissatisfied"),
        # CES (effort) — "neutral" is shared with CSAT
        ("easy", "Low Effort"),
        ("hard", "High Effort"),
    ]

    account = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_surveys")
    contact = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_survey_contacts")
    survey_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default="nps")
    trigger = models.CharField(max_length=12, choices=TRIGGER_CHOICES, default="manual")
    related_case = models.ForeignKey("crm.Case", on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_surveys")
    score = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MaxValueValidator(10)])
    feedback_text = models.TextField(blank=True)
    classification = models.CharField(max_length=12, choices=CLASSIFICATION_CHOICES, blank=True)  # auto-set
    token = models.CharField(max_length=64, unique=True, null=True, blank=True)  # public respond link
    sent_at = models.DateTimeField(null=True, blank=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "survey_type"], name="crm_nps_tnt_type_idx"),
            models.Index(fields=["tenant", "account"], name="crm_nps_tnt_account_idx"),
            models.Index(fields=["tenant", "sent_at"], name="crm_nps_tnt_sent_idx"),
        ]

    def save(self, *args, **kwargs):
        # Public respond-link token (random, URL-safe) generated once.
        if not self.token:
            self.token = secrets.token_urlsafe(24)
        # Auto-classify by type against each type's own scale (1.11 recreate):
        #   NPS 0–10:  9–10 promoter / 7–8 passive / ≤6 detractor
        #   CSAT 1–5:  ≥4 satisfied / 3 neutral / ≤2 dissatisfied
        #   CES 1–7 (effort): ≤2 easy / 3–5 neutral / ≥6 hard
        if self.score is None:
            self.classification = ""
        elif self.survey_type == "nps":
            self.classification = ("promoter" if self.score >= 9
                                   else "passive" if self.score >= 7 else "detractor")
        elif self.survey_type == "csat":
            self.classification = ("satisfied" if self.score >= 4
                                   else "neutral" if self.score == 3 else "dissatisfied")
        elif self.survey_type == "ces":
            self.classification = ("easy" if self.score <= 2
                                   else "neutral" if self.score <= 5 else "hard")
        else:
            self.classification = ""
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.number} · {self.get_survey_type_display()}"


class OnboardingTemplate(TenantNumbered):
    """A reusable onboarding blueprint (1.11) whose ordered steps clone into a fresh
    OnboardingPlan for any client in one click (Gainsight/ChurnZero success-plan pattern)."""

    NUMBER_PREFIX = "OTPL"

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="crm_otpl_tnt_active_idx"),
        ]

    @property
    def step_count(self):
        return self.steps.count()

    def __str__(self):
        return f"{self.number} · {self.name}"


class OnboardingTemplateStep(models.Model):
    """An ordered step within an OnboardingTemplate (1.11). ``offset_days`` sets the cloned
    step's due date relative to the plan start when the template is applied."""

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="+", db_index=True)
    template = models.ForeignKey("crm.OnboardingTemplate", on_delete=models.CASCADE, related_name="steps")
    order = models.PositiveSmallIntegerField(default=0)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    offset_days = models.PositiveSmallIntegerField(default=0)  # cloned step due = plan start + N days
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.title


class HealthScoreHistory(models.Model):
    """Append-only health-score trend point (1.11) — one row per recompute, so the detail
    page can show whether an account is improving or degrading. Immutable (list/detail only)."""

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="+", db_index=True)
    account = models.ForeignKey("core.Party", on_delete=models.CASCADE, related_name="crm_health_history")
    score = models.PositiveSmallIntegerField(default=0, validators=[MaxValueValidator(100)])
    tier = models.CharField(max_length=10, choices=HealthScore.TIER_CHOICES, default="green")
    breakdown = models.JSONField(default=dict, blank=True)
    computed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-computed_at"]
        indexes = [
            models.Index(fields=["tenant", "account", "-computed_at"], name="crm_hsh_tnt_acct_time_idx"),
        ]

    def __str__(self):
        return f"{self.account_id} · {self.score} ({self.tier})"


def compute_health_score(party, tenant):
    """Derive + persist a 0–100 health score for ``party`` from existing CRM signals.

    Reuses the per-tenant ``HealthScoreConfig`` weights (tickets/nps/tasks/engagement).
    The Accounting ledger (invoice/payment punctuality) is not built yet, so payments is
    intentionally absent — wire it in when Module 2 lands.
    """
    with transaction.atomic():
        config, _ = HealthScoreConfig.objects.get_or_create(tenant=tenant)

        open_cases = Case.objects.filter(tenant=tenant, account=party, status__in=Case.OPEN_STATUSES).count()
        tickets_score = max(0, 100 - open_cases * 20)

        latest = (Survey.objects.filter(tenant=tenant, account=party, survey_type="nps")
                  .exclude(score=None).order_by("-sent_at", "-created_at").first())
        nps_map = {"promoter": 100, "passive": 60, "detractor": 20}
        nps_score = nps_map.get(latest.classification, 50) if latest else 50

        tasks = CrmTask.objects.filter(tenant=tenant, party=party)
        total_t = tasks.count()
        tasks_score = round(tasks.filter(status="done").count() / total_t * 100) if total_t else 60

        has_open_opp = Opportunity.objects.filter(
            tenant=tenant, account=party, stage__in=Opportunity.OPEN_STAGES).exists()
        engagement_score = 100 if has_open_opp else 40

        signals = [
            (tickets_score, config.weight_tickets),
            (nps_score, config.weight_nps),
            (tasks_score, config.weight_tasks),
            (engagement_score, config.weight_engagement),
        ]
        total_w = sum(float(w) for _, w in signals) or 1
        score = max(0, min(100, round(sum(s * float(w) for s, w in signals) / total_w)))
        tier = ("red" if score < config.red_threshold
                else "yellow" if score < config.yellow_threshold else "green")
        obj, _ = HealthScore.objects.update_or_create(
            tenant=tenant, account=party,
            defaults={"score": score, "tier": tier, "computed_at": timezone.now(),
                      "breakdown": {"tickets": tickets_score, "nps": nps_score,
                                    "tasks": tasks_score, "engagement": engagement_score}},
        )
        # Append-only trend point so the detail page can show score history/direction (1.11 recreate).
        HealthScoreHistory.objects.create(
            tenant=tenant, account=party, score=score, tier=tier, breakdown=obj.breakdown)
        # Churn-risk alert: a red-tier account raises ONE open follow-up task for its CS owner.
        # Skip if an open churn task already exists for this account (no spam on every recompute).
        if tier == "red" and not CrmTask.objects.filter(
                tenant=tenant, party=party, status__in=CrmTask.OPEN_STATUSES,
                type="follow_up", subject__startswith="Churn risk:").exists():
            owner_id = (OnboardingPlan.objects.filter(tenant=tenant, account=party)
                        .exclude(owner=None).values_list("owner_id", flat=True).first())
            CrmTask.objects.create(
                tenant=tenant, party=party, owner_id=owner_id,
                subject=f"Churn risk: {party} health is critical ({score}/100)",
                type="follow_up", priority="high", status="open",
                description="Auto-raised by Customer Success health scoring — account dropped to the Red tier.")
    return obj


# ------------------------------------------------- 1.12 Inventory & Vendor Management
# CRM-owned PurchaseOrder/ProductStock (the Procurement/Inventory spine masters are not
# built yet — see "Spine-gap adaptation" in todo.md). Vendors are core.Party organizations.
class ProductStock(TenantNumbered):
    """A simple stock-tracked product (1.12) with reorder-level low-stock alerting."""

    NUMBER_PREFIX = "STK"

    name = models.CharField(max_length=255)
    sku = models.CharField(max_length=64, blank=True)
    on_hand_qty = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    reorder_level = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="crm_stk_tnt_active_idx"),
            models.Index(fields=["tenant", "name"], name="crm_stk_tnt_name_idx"),
        ]

    @property
    def is_low_stock(self):
        return self.on_hand_qty <= self.reorder_level

    def __str__(self):
        return f"{self.number} · {self.name}"


class PurchaseOrder(TenantNumbered):
    """A CRM-owned purchase order to a vendor (1.12). ``total_amount`` is recomputed from lines."""

    NUMBER_PREFIX = "PO"

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("sent", "Sent"),
        ("received", "Received"),
        ("cancelled", "Cancelled"),
    ]

    vendor = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_purchase_orders")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="draft")
    order_date = models.DateField(null=True, blank=True)
    expected_date = models.DateField(null=True, blank=True)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)  # recomputed from lines
    received_at = models.DateTimeField(null=True, blank=True)  # system-set on receive
    notes = models.TextField(blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_purchase_orders")

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="crm_po_tnt_status_idx"),
            models.Index(fields=["tenant", "created_at"], name="crm_po_tnt_created_idx"),
        ]

    def recalc_total(self):
        """Sum line totals into ``total_amount`` (call after line add/edit/delete)."""
        agg = self.lines.aggregate(
            t=models.Sum(models.F("quantity") * models.F("unit_price"),
                         output_field=models.DecimalField(max_digits=18, decimal_places=2)))
        self.total_amount = agg["t"] or Decimal("0")
        self.save(update_fields=["total_amount", "updated_at"])

    def __str__(self):
        return f"{self.number} · {self.vendor or 'Vendor'}"


class PurchaseOrderLine(models.Model):
    """A line item on a CRM PurchaseOrder (1.12). ``line_total`` is derived."""

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="+", db_index=True)
    purchase_order = models.ForeignKey("crm.PurchaseOrder", on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey("crm.ProductStock", on_delete=models.SET_NULL, null=True, blank=True, related_name="po_lines")
    item_name = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "id"]

    @property
    def line_total(self):
        return Decimal(self.quantity or 0) * Decimal(self.unit_price or 0)

    def __str__(self):
        return f"{self.item_name} ×{self.quantity}"


class PartnerPortalAccess(TenantNumbered):
    """External partner/vendor portal login mapping (1.12)."""

    NUMBER_PREFIX = "PRT"

    ACCESS_CHOICES = [
        ("read_only", "Read Only"),
        ("lead_register", "Lead Registration"),
        ("full", "Full Access"),
    ]

    partner_party = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_portal_accesses")
    portal_user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_portal_access")
    access_level = models.CharField(max_length=20, choices=ACCESS_CHOICES, default="read_only")
    can_view_stock = models.BooleanField(default=False)
    can_register_leads = models.BooleanField(default=False)
    accepted_at = models.DateTimeField(null=True, blank=True)  # system-set when partner activates
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="crm_prt_tnt_active_idx"),
            models.Index(fields=["tenant", "partner_party"], name="crm_prt_tnt_partner_idx"),
        ]

    def __str__(self):
        return f"{self.number} · {self.partner_party or 'Partner'}"


# ============================================================================
# ===== 1.6 Analytics & Reporting ============================================
# Saved per-user dashboards whose widgets are computed LIVE on render, plus saved
# standard reports with point-in-time snapshots. Every metric is a READ-ONLY
# aggregation over the existing CRM models (Opportunity/Case/Lead/Campaign/
# CrmTask/CommunicationLog), computed in ``apps/crm/analytics.py`` — nothing here
# stores a derived figure EXCEPT ``ReportSnapshot``, which deliberately freezes a
# single run for period-over-period trend history.
#
# Choice lists live here (the field definitions own them); the compute metadata
# (which aggregation + which chart kinds each metric supports) lives in
# ``analytics.py``, keyed by the same metric keys. analytics.py imports this
# module — this module never imports analytics.py (no circular import).
# ============================================================================

# Shared date-window selector for both widgets and reports (filters ``created_at``).
ANALYTICS_RANGE_CHOICES = [
    ("last_7", "Last 7 days"),
    ("last_30", "Last 30 days"),
    ("last_90", "Last 90 days"),
    ("quarter", "This quarter"),
    ("year", "This year"),
    ("all", "All time"),
]

DASHBOARD_LAYOUT_CHOICES = [
    ("one", "Single column"),
    ("two", "Two columns"),
    ("three", "Three columns"),
]

WIDGET_CHART_CHOICES = [
    ("kpi", "KPI Card"),
    ("gauge", "Gauge"),
    ("bar", "Bar Chart"),
    ("line", "Line Chart"),
    ("pie", "Pie Chart"),
    ("doughnut", "Doughnut Chart"),
    ("table", "Table"),
]

WIDGET_SIZE_CHOICES = [
    ("small", "Small (quarter width)"),
    ("medium", "Medium (half width)"),
    ("large", "Large (three-quarter width)"),
    ("full", "Full width"),
]

# (key, label) for every widget metric. The matching compute behaviour + the chart
# kinds each one allows are declared in ``analytics.WIDGET_METRICS`` under the same keys.
WIDGET_METRIC_CHOICES = [
    # --- scalar (KPI card / gauge) -------------------------------------------------
    ("kpi_open_pipeline", "KPI · Open Pipeline ($)"),
    ("kpi_weighted_forecast", "KPI · Weighted Forecast ($)"),
    ("kpi_win_rate", "KPI · Win Rate (%)"),
    ("kpi_revenue_won", "KPI · Revenue Won ($)"),
    ("kpi_new_leads", "KPI · New Leads (#)"),
    ("kpi_open_cases", "KPI · Open Cases (#)"),
    ("kpi_avg_csat", "KPI · Avg CSAT (1-5)"),
    ("kpi_open_tasks", "KPI · Open Tasks (#)"),
    # --- series (bar / line / pie / doughnut) -------------------------------------
    ("pipeline_by_stage", "Chart · Pipeline by Stage (#)"),
    ("pipeline_value_by_stage", "Chart · Pipeline Value by Stage ($)"),
    ("win_loss", "Chart · Won vs Lost (#)"),
    ("revenue_won_by_month", "Chart · Revenue Won by Month ($)"),
    ("leads_by_rating", "Chart · Leads by Rating"),
    ("leads_by_status", "Chart · Leads by Status"),
    ("leads_by_source", "Chart · Leads by Source"),
    ("cases_by_status", "Chart · Cases by Status"),
    ("cases_by_priority", "Chart · Cases by Priority"),
    ("tasks_by_type", "Chart · Tasks by Type"),
    # --- table --------------------------------------------------------------------
    ("top_performers", "Table · Top Performers"),
    ("campaign_roi", "Table · Campaign ROI"),
]

REPORT_TYPE_CHOICES = [
    ("sales_activity", "Sales Activity"),
    ("sales_performance", "Sales Performance (Top Performers)"),
    ("funnel", "Funnel Analysis (Drop-off)"),
    ("service", "Service (Resolution Time & CSAT)"),
]

REPORT_GROUP_CHOICES = [
    ("month", "By Month"),
    ("week", "By Week"),
    ("owner", "By Owner"),
    ("priority", "By Priority"),
    ("stage", "By Stage"),
]


class AnalyticsDashboard(TenantNumbered):
    """A saved, per-user CRM dashboard (1.6). Holds a set of ``DashboardWidget`` tiles that are
    computed live on render (real-time data). ``is_shared`` exposes it to the whole tenant;
    ``is_default`` marks the one opened first. The owner can keep private dashboards."""

    NUMBER_PREFIX = "DASH"

    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_dashboards")
    is_shared = models.BooleanField(default=False)  # visible to the whole tenant, not just the owner
    is_default = models.BooleanField(default=False)  # the landing dashboard
    layout = models.CharField(max_length=10, choices=DASHBOARD_LAYOUT_CHOICES, default="two")

    class Meta:
        ordering = ["-is_default", "name"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "owner"], name="crm_dash_tnt_owner_idx"),
            models.Index(fields=["tenant", "is_shared"], name="crm_dash_tnt_shared_idx"),
        ]

    @property
    def widget_count(self):
        return self.widgets.count()

    def __str__(self):
        return f"{self.number} · {self.name}"


class DashboardWidget(models.Model):
    """One tile on an ``AnalyticsDashboard`` (1.6). ``metric`` selects a read-only aggregation
    (see ``analytics.WIDGET_METRICS``); ``chart_type`` chooses how to render it (the form's
    ``clean()`` enforces a chart that the metric supports). Not ``TenantNumbered`` — it is a
    child row, so it carries its own tenant FK + timestamps and no human-readable number.
    ``target_value`` is an optional goal used by gauge/KPI widgets (progress-to-target)."""

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="+", db_index=True)
    dashboard = models.ForeignKey("AnalyticsDashboard", on_delete=models.CASCADE, related_name="widgets")
    title = models.CharField(max_length=120)
    metric = models.CharField(max_length=40, choices=WIDGET_METRIC_CHOICES, default="kpi_open_pipeline")
    chart_type = models.CharField(max_length=10, choices=WIDGET_CHART_CHOICES, default="kpi")
    date_range = models.CharField(max_length=10, choices=ANALYTICS_RANGE_CHOICES, default="last_30")
    size = models.CharField(max_length=10, choices=WIDGET_SIZE_CHOICES, default="medium")
    target_value = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)  # optional goal for gauge/KPI
    position = models.PositiveIntegerField(default=0)  # manual ordering on the dashboard
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["position", "id"]
        indexes = [
            models.Index(fields=["tenant", "dashboard"], name="crm_widget_tnt_dash_idx"),
        ]

    def __str__(self):
        return f"{self.title} ({self.get_chart_type_display()})"


class AnalyticsReport(TenantNumbered):
    """A saved standard report (1.6) — one of four canned report types computed live over the
    CRM data (see ``analytics.compute_report``). ``last_run_at`` is system-stamped whenever the
    report is rendered or snapshotted (never on the form). ``is_favorite`` pins it to the top."""

    NUMBER_PREFIX = "RPT"

    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    report_type = models.CharField(max_length=20, choices=REPORT_TYPE_CHOICES, default="sales_activity")
    date_range = models.CharField(max_length=10, choices=ANALYTICS_RANGE_CHOICES, default="last_90")
    group_by = models.CharField(max_length=10, choices=REPORT_GROUP_CHOICES, default="month")
    is_favorite = models.BooleanField(default=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_reports")
    last_run_at = models.DateTimeField(null=True, blank=True, editable=False)  # system-set on render/snapshot

    class Meta:
        ordering = ["-is_favorite", "name"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "report_type"], name="crm_rpt_tnt_type_idx"),
            models.Index(fields=["tenant", "is_favorite"], name="crm_rpt_tnt_fav_idx"),
        ]

    def __str__(self):
        return f"{self.number} · {self.name}"


class ReportSnapshot(models.Model):
    """A point-in-time saved run of an ``AnalyticsReport`` (1.6) — freezes the computed result so
    a report can be compared period-over-period without re-querying historical state. Created
    only by the ``report_snapshot`` POST action, never by a user form. ``summary`` is the KPI
    card list, ``data`` is the full {columns, rows, chart_*} payload (rendered as-is, no recompute)."""

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="+", db_index=True)
    report = models.ForeignKey("AnalyticsReport", on_delete=models.CASCADE, related_name="snapshots")
    title = models.CharField(max_length=160)
    generated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_report_snapshots")
    generated_at = models.DateTimeField(auto_now_add=True)
    summary = models.JSONField(default=list, blank=True)   # [{label, value}, ...] KPI cards
    data = models.JSONField(default=dict, blank=True)      # {columns, rows, chart_type, chart_labels, chart_data}

    class Meta:
        ordering = ["-generated_at"]
        indexes = [
            models.Index(fields=["tenant", "report"], name="crm_snap_tnt_report_idx"),
        ]

    def __str__(self):
        return f"{self.title} ({self.generated_at:%Y-%m-%d %H:%M})"
