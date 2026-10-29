from decimal import Decimal

from django.db import models

from apps.ecommerce.models._base import TenantNumbered


class PaymentMethodConfig(TenantNumbered):
    """Configuration for eCommerce payment gateways and method orchestration."""

    PROVIDER_STRIPE = "stripe"
    PROVIDER_PAYPAL = "paypal"
    PROVIDER_KLARNA = "klarna"
    PROVIDER_BANK_TRANSFER = "bank_transfer"
    PROVIDER_COD = "cod"

    PROVIDER_CHOICES = [
        (PROVIDER_STRIPE, "Stripe Payments"),
        (PROVIDER_PAYPAL, "PayPal Express"),
        (PROVIDER_KLARNA, "Klarna BNPL"),
        (PROVIDER_BANK_TRANSFER, "Direct Bank Transfer / Wire"),
        (PROVIDER_COD, "Cash on Delivery (COD)"),
    ]

    CATEGORY_CREDIT_CARD = "credit_card"
    CATEGORY_WALLET = "wallet"
    CATEGORY_BNPL = "bnpl"
    CATEGORY_BANK_TRANSFER = "bank_transfer"
    CATEGORY_COD = "cash_on_delivery"

    CATEGORY_CHOICES = [
        (CATEGORY_CREDIT_CARD, "Credit / Debit Card"),
        (CATEGORY_WALLET, "Digital Wallet"),
        (CATEGORY_BNPL, "Buy Now Pay Later"),
        (CATEGORY_BANK_TRANSFER, "Bank Transfer"),
        (CATEGORY_COD, "Cash on Delivery"),
    ]

    ENV_SANDBOX = "sandbox"
    ENV_PRODUCTION = "production"

    ENVIRONMENT_CHOICES = [
        (ENV_SANDBOX, "Sandbox / Test Mode"),
        (ENV_PRODUCTION, "Live / Production"),
    ]

    FEE_NONE = "none"
    FEE_PERCENTAGE = "percentage"
    FEE_FIXED = "fixed"

    FEE_TYPE_CHOICES = [
        (FEE_NONE, "No Surcharge"),
        (FEE_PERCENTAGE, "Percentage Surcharge"),
        (FEE_FIXED, "Fixed Fee Surcharge"),
    ]

    NUMBER_PREFIX = "EPMC"

    name = models.CharField(max_length=100)
    provider = models.CharField(max_length=30, choices=PROVIDER_CHOICES, default=PROVIDER_STRIPE)
    method_category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default=CATEGORY_CREDIT_CARD)
    environment = models.CharField(max_length=15, choices=ENVIRONMENT_CHOICES, default=ENV_SANDBOX)
    is_active = models.BooleanField(default=True, db_index=True)
    display_order = models.PositiveSmallIntegerField(default=0)
    fee_type = models.CharField(max_length=15, choices=FEE_TYPE_CHOICES, default=FEE_NONE)
    fee_amount = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0.00"))
    min_order_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    max_order_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    supported_currencies = models.CharField(max_length=100, default="USD,EUR,GBP")
    instructions = models.TextField(blank=True, help_text="Customer instructions displayed at checkout.")
    supports_refunds = models.BooleanField(default=True)

    class Meta:
        ordering = ["display_order", "name", "id"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="ecom_pmc_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "is_active", "display_order"], name="ecom_pmc_tnt_act_dsp_idx"),
            models.Index(fields=["tenant", "provider"], name="ecom_pmc_tnt_prov_idx"),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_provider_display()}) — {self.get_environment_display()}"

    def calculate_surcharge(self, subtotal):
        """Calculate any payment gateway surcharge applied to the order subtotal."""
        if self.fee_type == self.FEE_FIXED:
            return self.fee_amount
        if self.fee_type == self.FEE_PERCENTAGE and self.fee_amount > 0:
            return ((subtotal * self.fee_amount) / Decimal("100.00")).quantize(Decimal("0.01"))
        return Decimal("0.00")

    def is_eligible_for_amount(self, subtotal):
        """Verify whether an order amount falls within allowed threshold bounds."""
        if self.min_order_amount and subtotal < self.min_order_amount:
            return False
        if self.max_order_amount and subtotal > self.max_order_amount:
            return False
        return True
