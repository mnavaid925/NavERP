from django.db import models
from django.utils import timezone

from apps.ecommerce.models._base import TenantNumbered


class ProductQuestionAnswer(TenantNumbered):
    NUMBER_PREFIX = "EPQA"

    STATUS_CHOICES = [
        ("pending", "Pending Moderation"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    product = models.ForeignKey(
        "ecommerce.CatalogProduct",
        on_delete=models.CASCADE,
        related_name="questions_and_answers",
        help_text="Catalog product being asked about",
    )
    author_name = models.CharField(max_length=120, help_text="Public author name")
    author_email = models.EmailField(blank=True, help_text="Private email for notifications")
    customer = models.ForeignKey(
        "ecommerce.CustomerAccountProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="questions",
        help_text="Registered customer profile if authenticated",
    )
    question_text = models.TextField(help_text="Customer pre-purchase inquiry")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    answer_text = models.TextField(blank=True, help_text="Staff or expert response")
    answered_by_name = models.CharField(max_length=120, blank=True)
    is_staff_answer = models.BooleanField(default=False)
    answered_by_user = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="product_answers",
    )
    answered_at = models.DateTimeField(null=True, blank=True)
    helpful_votes = models.PositiveIntegerField(default=0)
    is_pinned = models.BooleanField(default=False, help_text="Pin to top of Q&A section")

    class Meta:
        ordering = ["-is_pinned", "-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="ecommerce_epqa_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_epqa_ten_stat"),
            models.Index(fields=["tenant", "product", "status"], name="idx_epqa_ten_prod_stat"),
            models.Index(fields=["tenant", "is_pinned"], name="idx_epqa_ten_pinned"),
        ]

    def __str__(self):
        return f"{self.number} - {self.product.name} ({self.status})"
