from decimal import Decimal
from django.conf import settings
from django.db import models
from apps.ecommerce.models._base import TenantNumbered


class B2bCompanyUser(TenantNumbered):
    NUMBER_PREFIX = "EBCU"

    ROLE_CHOICES = [
        ("company_admin", "Company Administrator"),
        ("procurement_manager", "Procurement Manager"),
        ("buyer", "Authorized Buyer"),
        ("approver", "Order Approver"),
        ("finance_auditor", "Finance / Auditor"),
    ]

    STATUS_CHOICES = [
        ("active", "Active"),
        ("invited", "Invitation Pending"),
        ("suspended", "Suspended"),
        ("inactive", "Inactive"),
    ]

    company = models.ForeignKey(
        "ecommerce.B2bCompanyAccount",
        on_delete=models.CASCADE,
        related_name="company_users",
        help_text="Parent B2B company account",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="b2b_user_memberships",
        help_text="Associated login user account",
    )
    party = models.ForeignKey(
        "core.Party",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="b2b_company_roles",
        help_text="Optional individual party identity in core spine",
    )
    role = models.CharField(
        max_length=30,
        choices=ROLE_CHOICES,
        default="buyer",
        help_text="Organizational role and authority tier",
    )
    job_title = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Corporate position or job title",
    )
    department = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Department or cost center (e.g. Operations, Procurement)",
    )
    order_spend_limit = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Maximum per-order spend without approval (0 for unlimited)",
    )
    monthly_spend_limit = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Maximum monthly budget (0 for unlimited)",
    )
    monthly_spend_current = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Current calendar month spend accumulated",
    )
    can_place_orders = models.BooleanField(
        default=True,
        help_text="Permission to execute checkout orders",
    )
    can_request_quotes = models.BooleanField(
        default=True,
        help_text="Permission to submit RFQs and negotiate quotes",
    )
    can_view_invoices = models.BooleanField(
        default=False,
        help_text="Permission to access corporate invoices and credit billing records",
    )
    can_manage_users = models.BooleanField(
        default=False,
        help_text="Permission to invite and manage other company buyers",
    )
    can_approve_orders = models.BooleanField(
        default=False,
        help_text="Authority to approve orders exceeding buyer limits",
    )
    reports_to_approver = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="subordinate_buyers",
        help_text="Direct supervisor who reviews orders requiring approval",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="active",
        help_text="Membership status",
    )

    class Meta:
        ordering = ["company", "user__username"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="ecommerce_ebcu_tenant_num_uniq",
            ),
            models.UniqueConstraint(
                fields=["tenant", "company", "user"],
                name="ecommerce_ebcu_ten_co_usr_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "-created_at"], name="idx_ebcu_ten_created"),
            models.Index(fields=["tenant", "company", "status"], name="idx_ebcu_ten_co_stat"),
            models.Index(fields=["tenant", "role"], name="idx_ebcu_ten_role"),
            models.Index(fields=["tenant", "status"], name="idx_ebcu_ten_stat"),
        ]

    def __str__(self):
        return f"{self.user.username} @ {self.company.company_name} ({self.role})"

    def can_spend(self, amount):
        """Check whether the requested order amount requires approval."""
        amt = Decimal(str(amount))
        if self.order_spend_limit > Decimal("0.00") and amt > self.order_spend_limit:
            return False
        if self.monthly_spend_limit > Decimal("0.00") and (self.monthly_spend_current + amt) > self.monthly_spend_limit:
            return False
        return True
