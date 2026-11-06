from decimal import Decimal

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.text import slugify

from apps.bi.models._base import TenantNumbered


class StrategicObjective(TenantNumbered):
    NUMBER_PREFIX = "BOBJ"

    PERSPECTIVE_CHOICES = [
        ("financial", "Financial"),
        ("customer", "Customer"),
        ("internal_process", "Internal Business Process"),
        ("learning_growth", "Learning & Growth"),
    ]

    RAG_STATUS_CHOICES = [
        ("green", "Green (On Track)"),
        ("amber", "Amber (Needs Attention)"),
        ("red", "Red (Critical / Off Track)"),
        ("gray", "Gray (Not Evaluated)"),
    ]

    STATUS_CHOICES = [
        ("proposed", "Proposed / Draft"),
        ("active", "Active Strategy"),
        ("achieved", "Achieved / Completed"),
        ("postponed", "Postponed"),
        ("canceled", "Canceled"),
    ]

    code = models.CharField(max_length=50)
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=120)
    perspective = models.CharField(max_length=30, choices=PERSPECTIVE_CHOICES, default="financial")
    statement_of_intent = models.TextField(
        blank=True,
        help_text="Strategic intent narrative, cause-and-effect rationale",
    )
    parent_objective = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="child_objectives",
        help_text="Upstream strategic objective driven by this initiative",
    )
    target_date = models.DateField(null=True, blank=True)
    rag_status = models.CharField(max_length=10, choices=RAG_STATUS_CHOICES, default="gray")
    alignment_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Objective achievement health index 0.00-100.00%",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="owned_strategic_objectives",
    )
    org_unit = models.ForeignKey(
        "core.OrgUnit",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="strategic_objectives",
    )
    sort_order = models.PositiveIntegerField(default=10)

    class Meta:
        ordering = ["perspective", "sort_order", "name"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "slug"], name="bi_bobj_tenant_slug_uniq"),
            models.UniqueConstraint(fields=["tenant", "number"], name="bi_bobj_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "perspective"], name="idx_bobj_ten_persp"),
            models.Index(fields=["tenant", "status"], name="idx_bobj_ten_stat"),
            models.Index(fields=["tenant", "parent_objective"], name="idx_bobj_ten_parent"),
            models.Index(fields=["tenant", "rag_status"], name="idx_bobj_ten_rag"),
        ]

    def __str__(self):
        return f"{self.number} - {self.name} ({self.code})"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:120]
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("bi:strategic_objective_detail", kwargs={"pk": self.pk})

    def recalculate_alignment(self):
        """Update alignment score and RAG status from linked KPI targets."""
        assigned = list(self.scorecard_kpis.all())
        if not assigned:
            if self.status == "achieved":
                self.alignment_score = Decimal("100.00")
                self.rag_status = "green"
            elif self.status in ["postponed", "canceled"]:
                self.rag_status = "gray"
            self.save(update_fields=["alignment_score", "rag_status", "updated_at"])
            return

        scores = [item.normalized_score for item in assigned]
        avg_score = round(sum(scores) / Decimal(str(len(scores))), 2)
        self.alignment_score = avg_score

        if avg_score >= Decimal("85.00"):
            self.rag_status = "green"
        elif avg_score >= Decimal("70.00"):
            self.rag_status = "amber"
        elif avg_score > Decimal("0.00"):
            self.rag_status = "red"
        else:
            self.rag_status = "gray"

        self.save(update_fields=["alignment_score", "rag_status", "updated_at"])
