"""Sales 8.7 — the territory coverage roster (``TMB-``). Serves NavERP bullet 4.

This is the whole of 8.7's answer to "Hunter/farmer splits, SDR/AE pairing, and overlay specialist
assignments", and it is deliberately **three columns, not a graph**:

* ``member_role`` says WHO the member is (``hunter`` / ``farmer`` / ``sdr`` / ``ae`` /
  ``overlay_specialist`` / ``sales_engineer``), which is the hunter/farmer split, the overlay
  specialist and the pre-sales engineer.
* ``paired_user`` is the SDR→AE pairing. **A nullable FK IS the pairing.** Building a pairing graph
  on top of it would be a second thing to keep consistent with the roster.
* ``coverage_split_pct`` is the split credit, and it is a **percentage**, not a money column — 8.10
  owns incentive compensation, so 8.7 must not store a "credit" figure that 8.10 would own.

**There is deliberately no ``is_manager`` or ``manager`` column here.** ``crm.Territory.manager`` is
CRM 1.2's single accountable manager for a territory; a second management field on 8.7 would be a
second source of truth for the same fact, which is exactly the failure L29/L37 exist to prevent.

**Overlays are NOT a second territory subtree** (research §2 row 4.4). An overlay is an
``AccountTerritoryAssignment(alignment_type="overlay")`` PLUS a
``TerritoryMember(member_role="overlay_specialist")`` against the BASE territory. SAP's own finding —
"overlay quotas don't roll up with base territory quotas" — is therefore reproduced by the *data
shape*, with no second hierarchy to keep in step.
"""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.sales.models._base import TenantNumbered, settings

ONE_HUNDRED = Decimal("100.00")


class TerritoryMember(TenantNumbered):
    """One person's role in one ``crm.Territory``, and the split credit they carry."""

    NUMBER_PREFIX = "TMB"

    # Verbatim from the frozen contract §5.1. Do not shorten a label or drop a value here:
    # `sales_engineer` is a real roster role, and `overlay` is what makes an overlay membership
    # countable (contract §9.7 `stats.overlay`) without inventing a second hierarchy.
    MEMBER_ROLE_CHOICES = [
        ("hunter", "Hunter / New Business"),
        ("farmer", "Farmer / Existing Business"),
        ("sdr", "SDR / Business Development"),
        ("ae", "Account Executive"),
        ("overlay_specialist", "Overlay Specialist"),
        ("sales_engineer", "Sales Engineer"),
    ]
    ASSIGNMENT_TYPE_CHOICES = [
        ("direct", "Direct Coverage"),
        ("shared", "Shared / Split Coverage"),
        ("overlay", "Overlay Coverage"),
    ]

    territory = models.ForeignKey(
        "crm.Territory",
        on_delete=models.CASCADE,
        related_name="sales_members",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sales_territory_memberships",
    )
    #: NO default — a member must declare its role. Defaulting this to "hunter" would let a roster
    #: of correctly-saved rows be completely wrong about what those rows mean.
    member_role = models.CharField(max_length=20, choices=MEMBER_ROLE_CHOICES)
    assignment_type = models.CharField(max_length=12, choices=ASSIGNMENT_TYPE_CHOICES, default="direct")
    coverage_split_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("100.00"),
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
    )
    paired_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_paired_territory_members",
    )
    is_primary = models.BooleanField(default=True)
    effective_from = models.DateField(default=timezone.localdate)
    effective_to = models.DateField(null=True, blank=True)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["territory__name", "-is_primary", "member_role"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "territory", "user", "member_role"],
                name="sales_tmember_tnt_terr_user_role_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "user"], name="sales_tmember_tnt_user_idx"),
            models.Index(fields=["tenant", "territory", "is_primary"], name="sales_tmember_tnt_terr_idx"),
        ]

    def _relation_belongs_to_tenant(self, field_name):
        """The one-FK-one-check helper shared by every 8.7 model — see AccountTerritoryAssignments."""
        if not self.tenant_id:
            return True
        relation_id = getattr(self, f"{field_name}_id", None)
        if not relation_id:
            return True
        field = self._meta.get_field(field_name)
        related_model = field.remote_field.model
        return related_model._default_manager.filter(
            pk=relation_id,
            tenant_id=self.tenant_id,
        ).exists()

    def clean(self):
        super().clean()
        if not self.tenant_id:
            return
        errors = {}
        for field_name in ("territory", "user", "paired_user"):
            if not self._relation_belongs_to_tenant(field_name):
                errors[field_name] = "That record must belong to this workspace."
        if self.effective_to and self.effective_from and self.effective_to < self.effective_from:
            errors["effective_to"] = "The end date cannot precede the start date."
        # A member cannot be paired with themselves, and a pairing is SDR -> AE. Saying so in the
        # validator is cheaper than saying it in prose on the help text and hoping it is read.
        if self.paired_user_id and self.paired_user_id == self.user_id:
            errors["paired_user"] = "A member cannot be paired with themselves."
        if self.paired_user_id and not self._paired_user_is_ae():
            errors["paired_user"] = "A pairing must point at a member whose role is Account Executive."
        if errors:
            raise ValidationError(errors)
        self._check_split_sums(errors)
        if errors:
            raise ValidationError(errors)

    def _paired_user_is_ae(self):
        """True when the paired user holds an ``ae`` membership in this same territory.

        ``None`` (not ``False``) is returned when the pairing cannot be judged at all — the
        same-tenant check is a separate concern and reports its own error, so returning False here
        would emit a second, misleading message about the same field.
        """
        pair = (
            type(self)._default_manager
            .filter(tenant_id=self.tenant_id, territory_id=self.territory_id, user_id=self.paired_user_id)
            .exclude(pk=self.pk)
            .first()
        )
        if pair is None:
            return None
        return pair.member_role == "ae"

    def _check_split_sums(self, errors):
        """The ``direct`` members' split must total exactly 100 — but ONLY when a ``shared`` sibling exists.

        The gate matters: without it the common single-rep ``direct`` case would pay a sibling query
        and a sum on every save, and a lone rep carrying the default 100.00 would be scored against a
        total that is trivially satisfied. A territory only becomes a *split* territory when someone
        says so, and that is what ``shared`` means.
        """
        if not self.territory_id:
            return
        siblings = type(self)._default_manager.filter(
            tenant_id=self.tenant_id,
            territory_id=self.territory_id,
            effective_to__isnull=True,
        )
        if self.pk:
            siblings = siblings.exclude(pk=self.pk)
        if not siblings.filter(assignment_type="shared").exists():
            return
        # Fetch the rows and add the Decimals in PYTHON. NEVER `Sum("coverage_split_pct")` in SQL:
        # the SQLite integer-division trap silently drops fractional cents instead of raising, so a
        # database-side total here is a WRONG ANSWER, not a slow one.
        total = sum(
            (row.coverage_split_pct or Decimal("0")) for row in siblings if row.assignment_type == "direct"
        ) + (self.coverage_split_pct or Decimal("0"))
        if total != ONE_HUNDRED:
            errors["coverage_split_pct"] = (
                "Direct members must sum to exactly 100.00% when any member is shared. "
                f"With this change the total is {total:.2f}%."
            )

    def __str__(self):
        role = self.get_member_role_display() if self.member_role else "—"
        return f"{self.territory} · {self.user} · {role}"

