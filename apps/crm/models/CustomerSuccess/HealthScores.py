"""CRM 1.11 Customer Success & Retention — HealthScores models (split from apps/crm/models.py)."""
from apps.crm.models._base import *  # noqa: F401,F403
from apps.crm.models.ActivityManagement.Tasks import CrmTask
from apps.crm.models.CustomerService.Cases import Case
from apps.crm.models.CustomerSuccess.OnboardingPlans import OnboardingPlan
from apps.crm.models.CustomerSuccess.Surveys import Survey
from apps.crm.models.SalesForceAutomation.Opportunities import Opportunity


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


class HealthScoreHistory(models.Model):
    """Append-only health-score trend point (1.11) — one row per recompute, so the detail
    page can show whether an account is improving or degrading. Immutable (list/detail only)."""

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="+", db_index=True)
    account = models.ForeignKey("core.Party", on_delete=models.CASCADE, related_name="crm_health_history")
    score = models.PositiveSmallIntegerField(default=0, validators=[MaxValueValidator(100)])
    tier = models.CharField(max_length=10, choices=HealthScore.TIER_CHOICES, default="green")
    breakdown = models.JSONField(default=dict, blank=True)
    computed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-computed_at"]
        indexes = [
            models.Index(fields=["tenant", "account", "-computed_at"], name="crm_hsh_tnt_acct_time_idx"),
        ]

    def __str__(self):
        return f"{self.account_id} · {self.score} ({self.tier})"


def compute_health_score(party, tenant, config=None):
    """Derive + persist a 0–100 health score for ``party`` from existing CRM signals.

    Reuses the per-tenant ``HealthScoreConfig`` weights (tickets/nps/tasks/engagement).
    Pass ``config`` to reuse one fetched config across a bulk recompute loop (avoids N refetches).
    The Accounting ledger (invoice/payment punctuality) is not built yet, so payments is
    intentionally absent — wire it in when Module 2 lands.
    """
    with transaction.atomic():
        if config is None:
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
        # Append-only trend point so the detail page can show score history/direction (1.11 recreate).
        HealthScoreHistory.objects.create(
            tenant=tenant, account=party, score=score, tier=tier, breakdown=obj.breakdown)
        # Churn-risk alert: a red-tier account raises ONE open follow-up task for its CS owner.
        # Skip if an open churn task already exists for this account (no spam on every recompute).
        if tier == "red" and not CrmTask.objects.filter(
                tenant=tenant, party=party, status__in=CrmTask.OPEN_STATUSES,
                type="follow_up", subject__startswith="Churn risk:").exists():
            owner_id = (OnboardingPlan.objects.filter(tenant=tenant, account=party)
                        .exclude(owner=None).values_list("owner_id", flat=True).first())
            CrmTask.objects.create(
                tenant=tenant, party=party, owner_id=owner_id,
                subject=f"Churn risk: {party} health is critical ({score}/100)",
                type="follow_up", priority="high", status="open",
                description="Auto-raised by Customer Success health scoring — account dropped to the Red tier.")
    return obj
