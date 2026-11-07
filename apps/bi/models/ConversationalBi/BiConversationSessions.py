from django.conf import settings
from django.db import models
from django.urls import reverse

from apps.bi.models._base import TenantNumbered


class BiConversationSession(TenantNumbered):
    NUMBER_PREFIX = "BCON"

    SESSION_STATUS_CHOICES = [
        ("active", "Active Chat Thread"),
        ("closed", "Closed Session"),
        ("archived", "Archived Conversation"),
    ]

    title = models.CharField(
        max_length=200,
        help_text="Conversational thread topic / headline",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bi_conversations",
    )
    session_status = models.CharField(
        max_length=16,
        choices=SESSION_STATUS_CHOICES,
        default="active",
    )
    is_pinned = models.BooleanField(
        default=False,
        help_text="Pin session to top of user's conversation drawer",
    )
    primary_semantic_model = models.ForeignKey(
        "bi.SemanticModel",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="bi_conversations",
    )
    primary_dashboard = models.ForeignKey(
        "bi.BiDashboard",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="bi_conversations",
    )
    context_state = models.JSONField(
        default=dict,
        blank=True,
        help_text="Active filter criteria, pinned date ranges, and dimensional anchors",
    )
    suggested_prompts = models.JSONField(
        default=list,
        blank=True,
        help_text="Contextual follow-up and clarification question chips",
    )
    message_count = models.PositiveIntegerField(
        default=0,
        help_text="Total number of conversational query exchanges in thread",
    )
    last_interaction_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_pinned", "-last_interaction_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="bi_bcon_tenant_num_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "session_status"], name="idx_bcon_ten_stat"),
            models.Index(fields=["tenant", "user"], name="idx_bcon_ten_usr"),
            models.Index(fields=["tenant", "is_pinned"], name="idx_bcon_ten_pin"),
            models.Index(fields=["tenant", "last_interaction_at"], name="idx_bcon_ten_interact"),
        ]

    def __str__(self):
        return f"{self.number} — {self.title}"

    def get_absolute_url(self):
        return reverse("bi:bi_conversation_session_detail", kwargs={"pk": self.pk})

    @property
    def is_active(self):
        return self.session_status == "active"

    @property
    def suggested_followups(self):
        return self.suggested_prompts

    @property
    def status_badge_color(self):
        if self.session_status == "active":
            return "badge-green"
        if self.session_status == "closed":
            return "badge-slate"
        if self.session_status == "archived":
            return "badge-amber"
        return "badge-slate"
