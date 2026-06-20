"""CRM (Module 1) domain models.

CRM reuses the unified core spine (NavERP-ERD.md): **Accounts** and **Contacts** are
``core.Party`` (one record, many roles) — this app adds only its own domain tables and FKs
into core **by string**. Every model is tenant-scoped and carries a human-readable per-tenant
number (LEAD-/OPP-/CAM-/CASE-/KB-/TASK-) assigned in ``save()`` via the shared
``apps.core.utils.next_number`` helper, with the retry-on-collision pattern proven in
``tenants.SubscriptionInvoice``.
"""
from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator
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

    name = models.CharField(max_length=255)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="email")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="planned")
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    budget_planned = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    budget_actual = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    expected_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    actual_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    target_size = models.PositiveIntegerField(default=0)
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

    name = models.CharField(max_length=255)
    account = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_opportunities")
    primary_contact = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_contact_opportunities")
    stage = models.CharField(max_length=20, choices=STAGE_CHOICES, default="prospecting")
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    probability = models.PositiveSmallIntegerField(default=10, validators=[MaxValueValidator(100)])
    close_date = models.DateField(null=True, blank=True)
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
        ]

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
