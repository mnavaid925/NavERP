"""Identity & access models: User (custom), RBAC Role/Permission, and UserInvite.

0.2's other three bullets live here too — `AccessRequest` (bullet 3), `AccessReview` +
`AccessReviewItem` (bullet 4), `ElevationGrant` (bullet 5) and `UserImportBatch` (bullet 2's bulk
half). NOTE: this app is still FLAT (models.py/forms.py/views.py/urls.py) while `core` and
`tenants` are packages. New entities are appended here rather than starting a partial package;
converting accounts to the packaged layout is a separate refactor, and 69 modules import
`from apps.accounts.models import …`, so it must keep that path working.
"""
import secrets

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from .managers import UserManager


class Permission(models.Model):
    """RBAC permission catalog (global, not tenant-scoped). Bundled into Roles."""

    codename = models.CharField(max_length=120, unique=True)  # e.g. "accounts.user.manage"
    name = models.CharField(max_length=255)
    module = models.CharField(max_length=50, default="core")  # module number/slug grouping

    class Meta:
        ordering = ["module", "codename"]

    def __str__(self):
        return self.codename


class Role(models.Model):
    """A named bundle of permissions assigned to users within a tenant."""

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="roles", db_index=True)
    name = models.CharField(max_length=120)
    description = models.CharField(max_length=255, blank=True)
    permissions = models.ManyToManyField("accounts.Permission", blank=True, related_name="roles")
    is_system = models.BooleanField(default=False)  # seeded roles — protected from deletion

    class Meta:
        ordering = ["name"]
        unique_together = ("tenant", "name")

    def __str__(self):
        return self.name


class User(AbstractBaseUser, PermissionsMixin):
    """Custom user. Login is by email (or username via the auth backend).

    ``tenant`` is nullable: the superuser ``admin`` has tenant=None by design and sees
    no module data. ``party`` links the login to the Party that represents this person.
    """

    STATUS_CHOICES = [
        ("active", "Active"),
        ("suspended", "Suspended"),
        ("archived", "Archived"),
    ]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.SET_NULL, null=True, blank=True,
                               related_name="users", db_index=True)
    party = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True,
                              related_name="users")
    role = models.ForeignKey("accounts.Role", on_delete=models.SET_NULL, null=True, blank=True,
                             related_name="users")

    email = models.EmailField(unique=True)
    username = models.CharField(max_length=150, unique=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)

    is_tenant_admin = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    objects = UserManager()

    class Meta:
        ordering = ["email"]

    def __str__(self):
        return self.email

    def get_full_name(self):
        full = f"{self.first_name} {self.last_name}".strip()
        return full or self.username

    def get_short_name(self):
        return self.first_name or self.username

    @property
    def initials(self):
        a = (self.first_name[:1] or self.email[:1]).upper()
        b = (self.last_name[:1] or "").upper()
        return (a + b) or "?"


class UserInvite(models.Model):
    """Pending invitation for someone to join a tenant. Accepted via a tokenized link."""

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("accepted", "Accepted"),
        ("expired", "Expired"),
        ("revoked", "Revoked"),
    ]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="invites", db_index=True)
    email = models.EmailField()
    role = models.ForeignKey("accounts.Role", on_delete=models.SET_NULL, null=True, blank=True,
                             related_name="invites")
    token = models.CharField(max_length=64, unique=True, editable=False)  # secret — excluded from forms (L20)
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                   blank=True, related_name="sent_invites")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)  # system-set, out of forms (L22)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_urlsafe(32)
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(days=7)
        super().save(*args, **kwargs)

    def is_expired(self):
        return timezone.now() > self.expires_at

    def __str__(self):
        return f"{self.email} → {self.tenant}"


# ==================================================== 0.2 bullet 3: Access Request & Approval
class AccessRequest(models.Model):
    """A member's self-service request for a role, its approval decision, and the grant.

    Bullet 3 is "self-service access requests, approval workflows, and time-bound access grants".
    All three live on one row deliberately: the request, the decision and the resulting window are
    one story, and splitting them would let a decision and its grant drift apart. The decision
    stamps and `granted_until` are written ONLY by the approve/reject verbs and are form-excluded.

    There is no FK to the grant — approving sets `granted_until` and the requester's role, and
    `is_active` derives whether the window is still open. An expired grant needs no sweeper: it
    simply stops reading as active, and the member's role is left for the admin to revoke (there
    is no scheduler in this repo, so nothing silently rewrites access on a timer).
    """

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("cancelled", "Cancelled"),
    ]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE,
                               related_name="access_requests", db_index=True)
    requester = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                  related_name="access_requests")
    requested_role = models.ForeignKey("accounts.Role", on_delete=models.SET_NULL, null=True,
                                       blank=True, related_name="access_requests")
    justification = models.TextField()
    requested_days = models.PositiveIntegerField(
        default=30, help_text="How long the access should last once approved.")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    # Verb-written evidence — never form-editable (L22).
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                   blank=True, editable=False, related_name="decided_access_requests")
    decided_at = models.DateTimeField(null=True, blank=True, editable=False)
    decision_note = models.TextField(blank=True)
    granted_until = models.DateTimeField(null=True, blank=True, editable=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["tenant", "status"], name="acr_tenant_status_idx"),
            models.Index(fields=["tenant", "requester"], name="acr_tenant_req_idx"),
        ]

    def clean(self):
        super().clean()
        if not (self.justification or "").strip():
            raise ValidationError({"justification": "State why this access is needed."})

    @property
    def is_expired(self):
        """True once an APPROVED window has closed. Pending/rejected rows are never 'expired'."""
        return (self.status == "approved" and self.granted_until is not None
                and timezone.now() > self.granted_until)

    @property
    def is_active(self):
        return self.status == "approved" and not self.is_expired

    def __str__(self):
        return f"{self.requester} → {self.requested_role or '—'} ({self.get_status_display()})"


# ============================================= 0.2 bullet 4: Access Certification & Reviews
class AccessReview(models.Model):
    """A certification campaign: snapshot who holds what, then attest or revoke each row.

    Bullet 4 is "periodic entitlement reviews, attestation campaigns, and orphan-account
    detection". A campaign is a header plus one `AccessReviewItem` per user; generating the items
    is an explicit verb so the reviewed population is a recorded decision rather than whatever the
    user table happens to contain when someone opens the page.
    """

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("open", "Open"),
        ("closed", "Closed"),
    ]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE,
                               related_name="access_reviews", db_index=True)
    name = models.CharField(max_length=150)
    scope_role = models.ForeignKey("accounts.Role", on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="access_reviews",
                                   help_text="Leave blank to review every member.")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    due_on = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                   blank=True, related_name="created_access_reviews")
    closed_at = models.DateTimeField(null=True, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["tenant", "status"], name="arv_tenant_status_idx")]

    @property
    def decided_count(self):
        return self.items.exclude(decision="pending").count()

    @property
    def is_overdue(self):
        return (self.status == "open" and self.due_on is not None
                and timezone.localdate() > self.due_on)

    def __str__(self):
        return self.name


class AccessReviewItem(models.Model):
    """One member's line in a certification campaign — the attest/revoke decision.

    `role` is a SNAPSHOT of what the member held when the campaign was generated, so a later role
    change cannot rewrite what was certified. `decision` is written only by the ari_attest /
    ari_revoke verbs.
    """

    DECISION_CHOICES = [
        ("pending", "Pending"),
        ("attest", "Attest"),
        ("revoke", "Revoke"),
    ]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE,
                               related_name="access_review_items", db_index=True)
    review = models.ForeignKey("accounts.AccessReview", on_delete=models.CASCADE,
                               related_name="items")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="access_review_items")
    role = models.ForeignKey("accounts.Role", on_delete=models.SET_NULL, null=True, blank=True,
                             related_name="+")
    decision = models.CharField(max_length=10, choices=DECISION_CHOICES, default="pending")
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                   blank=True, editable=False, related_name="+")
    decided_at = models.DateTimeField(null=True, blank=True, editable=False)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["review", "user__email"]
        unique_together = ("review", "user")
        indexes = [models.Index(fields=["tenant", "decision"], name="ari_tenant_decision_idx")]

    def __str__(self):
        return f"{self.user} · {self.get_decision_display()}"


# ================================================= 0.2 bullet 5: Privileged Access Management
class ElevationGrant(models.Model):
    """Just-in-time privileged elevation: a time-boxed admin window with a stated reason.

    Bullet 5 names three things. This implements the second — JIT elevation — and is honest about
    the other two: there is **no credential vaulting** (no secret is stored; `tenants.EncryptionKey`
    keeps only a prefix + SHA-256 hash and that is 0.7's) and **no session recording** (nothing
    captures a session). Both are declared on the page rather than implied by a field name.

    A grant does not by itself confer anything: `is_live` reports whether the window is open, and
    applying it is an admin action. Nothing rewrites `User.is_tenant_admin` on a timer, because
    this repo has no scheduler and a silent privilege change is worse than an explicit one.
    """

    SCOPE_CHOICES = [
        ("tenant_admin", "Tenant Admin"),
        ("staff", "Staff (Django admin)"),
    ]
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("active", "Active"),
        ("rejected", "Rejected"),
        ("revoked", "Revoked"),
    ]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE,
                               related_name="elevation_grants", db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="elevation_grants")
    scope = models.CharField(max_length=20, choices=SCOPE_CHOICES, default="tenant_admin")
    reason = models.TextField()
    starts_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                     blank=True, related_name="requested_elevations")
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                    blank=True, editable=False, related_name="approved_elevations")
    approved_at = models.DateTimeField(null=True, blank=True, editable=False)
    revoked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                   blank=True, editable=False, related_name="revoked_elevations")
    revoked_at = models.DateTimeField(null=True, blank=True, editable=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["tenant", "status"], name="elv_tenant_status_idx"),
            models.Index(fields=["tenant", "user"], name="elv_tenant_user_idx"),
        ]

    def clean(self):
        super().clean()
        if not (self.reason or "").strip():
            raise ValidationError({"reason": "A privileged elevation needs a stated reason."})
        if self.starts_at and self.expires_at and self.expires_at <= self.starts_at:
            raise ValidationError({"expires_at": "The window must end after it starts."})

    @property
    def is_live(self):
        """Approved AND inside its window. A window that has passed stops reading as live without
        any sweeper touching the row."""
        now = timezone.now()
        return (self.status == "active" and self.starts_at <= now < self.expires_at)

    @property
    def is_elapsed(self):
        return self.status == "active" and timezone.now() >= self.expires_at

    def __str__(self):
        return f"{self.user} · {self.get_scope_display()} ({self.get_status_display()})"


# ================================== 0.2 bullet 2: bulk provisioning (import/export)
class UserImportBatch(models.Model):
    """A bulk CSV user import: the uploaded file's outcome, with line-numbered errors.

    Bullet 2 names "bulk user import/export". Import stages rows, validates them, and only writes
    users when the batch is committed — so a file with three bad rows cannot half-apply. Export is
    a plain CSV download and needs no table. **SCIM provisioning is NOT implemented** and is
    declared on the page rather than implied.
    """

    STATUS_CHOICES = [
        ("validated", "Validated"),
        ("committed", "Committed"),
        ("failed", "Failed"),
    ]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE,
                               related_name="user_import_batches", db_index=True)
    file_name = models.CharField(max_length=255)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                    blank=True, related_name="user_import_batches")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="validated")
    row_count = models.PositiveIntegerField(default=0)
    created_count = models.PositiveIntegerField(default=0)
    error_count = models.PositiveIntegerField(default=0)
    #: Line-numbered errors, e.g. [{"line": 3, "error": "duplicate email"}]. JSONField so a failed
    #: validation is inspectable later without a second table.
    errors = models.JSONField(default=list, blank=True)
    #: The rows that PASSED validation, held until the batch is committed. Staged rather than
    #: written immediately so a file with three bad rows cannot half-apply: the operator reviews
    #: the batch and commits it, and only then do users exist.
    staged_rows = models.JSONField(default=list, blank=True)
    committed_at = models.DateTimeField(null=True, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["tenant", "status"], name="uib_tenant_status_idx")]

    @property
    def has_errors(self):
        return self.error_count > 0

    def __str__(self):
        return f"{self.file_name} ({self.get_status_display()})"
