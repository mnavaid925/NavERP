"""Quote Approval Rules model for CPQ pricing and discount governance."""
from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.sales.models._base import TenantNumbered


class QuoteApprovalRule(TenantNumbered):
    """Defines automated governance gates for quote discounting, margins, and contract value."""

    NUMBER_PREFIX = "QAR"

    RULE_TYPE_CHOICES = [
        ("max_discount", "Max Discount %"),
        ("min_margin", "Minimum Margin %"),
        ("max_amount", "Max Total Amount"),
        ("composite", "Composite Discount & Margin"),
    ]

    APPROVER_ROLE_CHOICES = [
        ("sales_manager", "Sales Manager"),
        ("sales_director", "Sales Director"),
        ("vp_sales", "VP of Sales"),
        ("finance_manager", "Finance Manager"),
        ("cfo", "Chief Financial Officer"),
    ]

    name = models.CharField(max_length=255)
    rule_type = models.CharField(max_length=25, choices=RULE_TYPE_CHOICES, default="max_discount")
    discount_threshold_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("20.00"),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Quotes exceeding this header or line discount % require approval.",
    )
    min_margin_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("15.00"),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Quotes with profit margin % below this floor require approval.",
    )
    amount_threshold = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Quote total exceeding this value requires approval.",
    )
    approver_role = models.CharField(
        max_length=30,
        choices=APPROVER_ROLE_CHOICES,
        default="sales_manager",
        help_text="Required role/tier for quote sign-off.",
    )
    auto_reject = models.BooleanField(
        default=False,
        help_text="Immediately mark quote as rejected if this rule is violated.",
    )
    priority = models.PositiveIntegerField(
        default=100,
        help_text="Evaluation priority order (lower evaluated first).",
    )
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["priority", "name"]
        indexes = [
            models.Index(fields=["tenant", "is_active", "priority"], name="sales_qar_active_prio_idx"),
        ]

    def __str__(self):
        return f"{self.number} · {self.name} ({self.get_rule_type_display()})"

    def evaluate(self, quote, max_line_disc=None):
        """Evaluate if quote violates this rule's thresholds.
        
        Returns:
            (triggered: bool, reason: str)
        """
        # Header discount check
        quote_disc = Decimal(str(quote.header_discount_pct or 0))
        
        # Line discounts check
        if max_line_disc is None:
            from django.db.models import Max
            agg = quote.lines.filter(is_selected=True).aggregate(m=Max("discount_pct"))
            max_line_disc = Decimal(str(agg["m"])) if agg["m"] is not None else Decimal("0")
        else:
            max_line_disc = Decimal(str(max_line_disc))

        effective_disc = max(quote_disc, max_line_disc)
        quote_margin = Decimal(str(quote.margin_pct or 0))
        quote_total = Decimal(str(quote.total or 0))

        if self.rule_type == "max_discount":
            if effective_disc > self.discount_threshold_pct:
                return True, f"Discount ({effective_disc}%) exceeds threshold of {self.discount_threshold_pct}%."

        elif self.rule_type == "min_margin":
            # Only enforce margin rule if quote has lines and a positive subtotal
            if quote.subtotal > Decimal("0") and quote_margin < self.min_margin_pct:
                return True, f"Profit margin ({quote_margin}%) is below minimum requirement of {self.min_margin_pct}%."

        elif self.rule_type == "max_amount":
            if self.amount_threshold and quote_total > self.amount_threshold:
                currency_code = quote.currency.code if quote.currency else ""
                return True, f"Quote total ({currency_code} {quote_total:,.2f}) exceeds approval limit of {currency_code} {self.amount_threshold:,.2f}."

        elif self.rule_type == "composite":
            disc_violation = effective_disc > self.discount_threshold_pct
            margin_violation = quote.subtotal > Decimal("0") and quote_margin < self.min_margin_pct
            if disc_violation and margin_violation:
                return True, f"Composite violation: Discount ({effective_disc}%) exceeds {self.discount_threshold_pct}% AND margin ({quote_margin}%) is below {self.min_margin_pct}%."

        return False, ""
