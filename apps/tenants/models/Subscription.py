"""tenants — Subscription models (split from apps/tenants/models.py)."""
from apps.tenants.models._base import *  # noqa: F401,F403


class Subscription(models.Model):
    PLAN_CHOICES = Tenant.PLAN_CHOICES
    STATUS_CHOICES = [
        ("trialing", "Trialing"),
        ("active", "Active"),
        ("past_due", "Past Due"),
        ("canceled", "Canceled"),
        ("incomplete", "Incomplete"),
    ]
    BILLING_CHOICES = [("monthly", "Monthly"), ("yearly", "Yearly")]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="subscriptions", db_index=True)
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default="starter")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="trialing")
    billing_cycle = models.CharField(max_length=10, choices=BILLING_CHOICES, default="monthly")
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    seats = models.PositiveIntegerField(default=5)
    started_on = models.DateField(null=True, blank=True)
    renews_on = models.DateField(null=True, blank=True)
    # Stripe linkage — set by the webhook, excluded from forms.
    stripe_customer_id = models.CharField(max_length=120, blank=True)
    stripe_subscription_id = models.CharField(max_length=120, blank=True, db_index=True)
    # 0.19 adds `auto_renew` and `grace_ends_on` — the recorded auto-renew INTENT and the grace
    # window. Both are negotiated commercial terms an operator sets by hand, so unlike
    # `UsageQuota.breached_at` they are NOT evidence stamps and belong on the form. NavERP has no
    # scheduler, so nothing acts on `auto_renew` yet; that is 0.20.
    #
    # **THREE STATES, NOT TWO (I10).** `null=True` is the point, and `default=False` would have
    # been the wrong fix rather than a cheaper one. This field shipped as `BooleanField(default=
    # True)`, which meant the 0.19 migration stamped EVERY pre-existing subscription "auto-renews"
    # — a decision nobody made, which the renewal board then rendered as a fact. That is the L52
    # failure class (a confident state that was fabricated) arriving through a column default.
    #
    # Changing the default to `False` fixes the direction of the lie but not the lie: it stamps
    # every one of those rows with the OPPOSITE decision, equally unexpressed. And there is no
    # "safe" default to fall back to, because nothing in NavERP reads this value — there is no
    # scheduler, so `True` and `False` are equally arbitrary and only "nobody has said" is a true
    # statement. Hence NULL:
    #
    #   True  - somebody flagged this subscription to auto-renew.
    #   False - somebody explicitly declined it.
    #   None  - nobody has expressed an intent. NOT a synonym for False.
    #
    # Every reader must therefore distinguish None from False. `Boards.renewal_board` counts only
    # `True` and renders all three; the form uses a tri-state widget so a POST cannot silently
    # collapse an unanswered question into a declined one.
    auto_renew = models.BooleanField(default=None, null=True, blank=True)

    grace_ends_on = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.tenant} · {self.get_plan_display()}"

    def days_left(self):
        if not self.renews_on:
            return None
        return (self.renews_on - timezone.localdate()).days
