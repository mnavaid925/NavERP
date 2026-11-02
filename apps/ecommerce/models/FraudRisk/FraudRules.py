from django.db import models
from apps.ecommerce.models._base import TenantNumbered


class FraudRule(TenantNumbered):
    NUMBER_PREFIX = "EFRR"

    RULE_SCOPE_CHOICES = [
        ("checkout", "Checkout / Payment"),
        ("account_login", "Account Login"),
        ("registration", "Account Registration"),
        ("promotion", "Coupon / Promotion Redemption"),
    ]

    RULE_TYPE_CHOICES = [
        ("velocity_orders", "Order Velocity (Orders / Hour)"),
        ("velocity_cards", "Card Attempt Velocity"),
        ("amount_threshold", "High Order Amount Threshold"),
        ("avs_cvv_mismatch", "AVS / CVV Failure"),
        ("ip_proxy_vpn", "Proxy / VPN / TOR Detection"),
        ("country_mismatch", "Billing / IP Country Mismatch"),
        ("email_domain_risk", "High-Risk Disposable Email Domain"),
        ("blacklist_match", "Blacklist Entity Match"),
        ("whitelist_match", "Whitelist Entity Match"),
    ]

    CONDITION_OPERATOR_CHOICES = [
        ("gt", "Greater Than (>)"),
        ("gte", "Greater Than or Equal (>=)"),
        ("lt", "Less Than (<)"),
        ("lte", "Less Than or Equal (<=)"),
        ("equals", "Equals (==)"),
        ("contains", "Contains"),
        ("in_list", "In Blacklist / Whitelist"),
    ]

    ACTION_CHOICES = [
        ("allow", "Allow / Trust"),
        ("flag_review", "Flag for Manual Review"),
        ("challenge_3ds", "Challenge (3D Secure / MFA)"),
        ("block", "Block / Reject"),
    ]

    name = models.CharField(
        max_length=255,
        help_text="Human-readable rule name",
    )
    rule_code = models.CharField(
        max_length=50,
        blank=True,
        default="",
        help_text="Unique identifier rule code, e.g. R-VEL-01",
    )
    rule_scope = models.CharField(
        max_length=30,
        choices=RULE_SCOPE_CHOICES,
        default="checkout",
        help_text="Operational lifecycle stage where rule is evaluated",
    )
    rule_type = models.CharField(
        max_length=40,
        choices=RULE_TYPE_CHOICES,
        default="velocity_orders",
        help_text="Risk factor and detection criteria evaluated",
    )
    condition_operator = models.CharField(
        max_length=20,
        choices=CONDITION_OPERATOR_CHOICES,
        default="gt",
        help_text="Comparison logic applied to evaluate threshold",
    )
    threshold_value = models.CharField(
        max_length=255,
        help_text="Numeric limit, threshold count, or comma-separated match values",
    )
    risk_score_impact = models.IntegerField(
        default=20,
        help_text="Risk points added (or subtracted if whitelist) when triggered",
    )
    action_to_take = models.CharField(
        max_length=25,
        choices=ACTION_CHOICES,
        default="flag_review",
        help_text="Automated policy intervention triggered upon rule match",
    )
    priority = models.IntegerField(
        default=10,
        help_text="Execution order (lower runs first)",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this rule is actively evaluated",
    )
    description = models.TextField(
        blank=True,
        default="",
        help_text="Administrative description of threat model and business justification",
    )

    class Meta:
        db_table = "ecommerce_fraud_rule"
        ordering = ["priority", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="ecommerce_efrr_tenant_num_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "is_active", "priority"], name="idx_efrr_ten_act_prio"),
            models.Index(fields=["tenant", "rule_scope"], name="idx_efrr_ten_scope"),
            models.Index(fields=["tenant", "rule_type"], name="idx_efrr_ten_type"),
        ]

    def __str__(self):
        return f"{self.number} - {self.name} ({self.get_rule_scope_display()})"
