"""CRM 1.4 Customer Service & Support — Cases models (split from apps/crm/models.py)."""
from apps.crm.models._base import *  # noqa: F401,F403


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
