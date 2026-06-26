"""CRM (Module 1) domain models.

CRM reuses the unified core spine (NavERP-ERD.md): **Accounts** and **Contacts** are
``core.Party`` (one record, many roles) — this app adds only its own domain tables and FKs
into core **by string**. Every model is tenant-scoped and carries a human-readable per-tenant
number (LEAD-/OPP-/CAM-/CASE-/KB-/TASK-) assigned in ``save()`` via the shared
``apps.core.utils.next_number`` helper, with the retry-on-collision pattern proven in
``tenants.SubscriptionInvoice``.
"""
import secrets
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
        """Recompute subtotal/tax/total from the lines DB-side, then apply the quote-level
        discount. Lines store unit_price/discount/tax; totals are derived, never user-entered."""
        from django.db.models import DecimalField as DF
        from django.db.models import ExpressionWrapper, F, Sum
        net = ExpressionWrapper(
            F("quantity") * F("unit_price") * (Decimal(1) - F("discount_pct") / 100),
            output_field=DF(max_digits=18, decimal_places=4))
        agg = self.lines.aggregate(
            sub=Sum(net),
            tax=Sum(net * F("tax_pct") / 100, output_field=DF(max_digits=18, decimal_places=4)),
        )
        line_sub = Decimal(agg["sub"] or 0)
        line_tax = Decimal(agg["tax"] or 0)
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
    due_at = models.DateTimeField(null=True, blank=True)  # SLA deadline
    resolved_at = models.DateTimeField(null=True, blank=True)  # system-set, out of forms

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="crm_case_tenant_status_idx"),
            models.Index(fields=["tenant", "created_at"], name="crm_case_tenant_created_idx"),
        ]

    @property
    def is_open(self):
        return self.status in self.OPEN_STATUSES

    @property
    def is_overdue(self):
        return bool(self.due_at and self.is_open and self.due_at < timezone.now())

    def save(self, *args, **kwargs):
        # System-set resolved_at: stamp when first resolved/closed, clear if re-opened.
        if self.status in ("resolved", "closed"):
            if self.resolved_at is None:
                self.resolved_at = timezone.now()
        else:
            self.resolved_at = None
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.number} · {self.subject}"


class KnowledgeArticle(TenantNumbered):
    """A help-desk solution / FAQ (1.4) with internal vs external visibility."""

    NUMBER_PREFIX = "KB"

    VISIBILITY_CHOICES = [("internal", "Internal"), ("external", "External")]
    STATUS_CHOICES = [("draft", "Draft"), ("published", "Published"), ("archived", "Archived")]

    title = models.CharField(max_length=255)
    category = models.CharField(max_length=120, blank=True)
    body = models.TextField(blank=True)
    visibility = models.CharField(max_length=10, choices=VISIBILITY_CHOICES, default="internal")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="draft")
    views_count = models.PositiveIntegerField(default=0)  # system-set on detail view
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_articles")

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="crm_kb_tenant_status_idx"),
            models.Index(fields=["tenant", "created_at"], name="crm_kb_tenant_created_idx"),
        ]

    def __str__(self):
        return f"{self.number} · {self.title}"


class CrmTask(TenantNumbered):
    """A to-do / call / follow-up (1.5). ``completed_at`` is system-set on done."""

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
    OPEN_STATUSES = ["open", "in_progress"]

    subject = models.CharField(max_length=255)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="todo")
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default="medium")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open")
    due_date = models.DateField(null=True, blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_tasks")
    party = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_tasks")
    related_opportunity = models.ForeignKey("crm.Opportunity", on_delete=models.SET_NULL, null=True, blank=True, related_name="tasks")
    description = models.TextField(blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)  # system-set

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
        # System-set completed_at: stamp when first marked done, clear if re-opened.
        if self.status == "done":
            if self.completed_at is None:
                self.completed_at = timezone.now()
        else:
            self.completed_at = None
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.number} · {self.subject}"


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
        ("promoter", "Promoter"),
        ("passive", "Passive"),
        ("detractor", "Detractor"),
    ]

    account = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_surveys")
    contact = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_survey_contacts")
    survey_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default="nps")
    trigger = models.CharField(max_length=12, choices=TRIGGER_CHOICES, default="manual")
    related_case = models.ForeignKey("crm.Case", on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_surveys")
    score = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MaxValueValidator(10)])
    feedback_text = models.TextField(blank=True)
    classification = models.CharField(max_length=10, choices=CLASSIFICATION_CHOICES, blank=True)  # auto-set
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
        # Auto-classify NPS responses: 9–10 promoter, 7–8 passive, 0–6 detractor.
        if self.survey_type == "nps" and self.score is not None:
            self.classification = ("promoter" if self.score >= 9
                                   else "passive" if self.score >= 7 else "detractor")
        elif self.survey_type != "nps":
            self.classification = ""
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.number} · {self.get_survey_type_display()}"


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
