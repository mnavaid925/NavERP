import secrets

from django.conf import settings
from django.db import models
from django.utils.text import slugify

from apps.bi.models._base import TenantNumbered


class BiDataStory(TenantNumbered):
    NUMBER_PREFIX = "DSTY"

    STORY_TYPE_CHOICES = [
        ("narrative_deck", "Executive Presentation Deck"),
        ("annotated_walkthrough", "Annotated Walkthrough"),
        ("dashboard_snapshot", "Guided Dashboard Tour"),
        ("kpi_review", "KPI & Business Review"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("published", "Published"),
        ("archived", "Archived"),
    ]

    PRESENTATION_THEME_CHOICES = [
        ("light_executive", "Executive Clean Light"),
        ("dark_boardroom", "Boardroom Navy Dark"),
        ("vibrant_accent", "Modern Vibrant"),
    ]

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, blank=True)
    summary = models.TextField(blank=True)

    workspace = models.ForeignKey(
        "bi.BiSharedWorkspace",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="stories",
        help_text="Workspace container for this narrative presentation",
    )

    story_type = models.CharField(
        max_length=24,
        choices=STORY_TYPE_CHOICES,
        default="narrative_deck",
    )
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default="draft",
    )
    theme = models.CharField(
        max_length=24,
        choices=PRESENTATION_THEME_CHOICES,
        default="light_executive",
    )

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="bi_authored_stories",
    )

    allow_live_drilldown = models.BooleanField(
        default=True,
        help_text="Allow presenters and audience to interactively drill down into chart data during presentation mode",
    )

    slides_data = models.JSONField(
        default=list,
        blank=True,
        help_text="Ordered slide definitions [{id, title, content, visual_type, visual_id, filter_state, notes}]",
    )
    slides_count = models.PositiveIntegerField(default=0)
    view_count = models.PositiveIntegerField(default=0)

    office_embed_token = models.CharField(
        max_length=64,
        blank=True,
        help_text="Secure token for PowerPoint / Excel live document embedding",
    )
    excel_export_settings = models.JSONField(
        default=dict,
        blank=True,
        help_text="Excel live refresh and tabular export configuration",
    )

    last_presented_at = models.DateTimeField(null=True, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="bi_created_stories",
    )

    class Meta:
        db_table = "bi_data_story"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="bi_dsty_ten_num_uniq"),
            models.UniqueConstraint(fields=["tenant", "slug"], name="bi_dsty_ten_slug_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_dsty_ten_stat"),
            models.Index(fields=["tenant", "story_type"], name="idx_dsty_ten_type"),
            models.Index(fields=["tenant", "workspace"], name="idx_dsty_ten_wspc"),
            models.Index(fields=["tenant", "author"], name="idx_dsty_ten_author"),
            models.Index(fields=["tenant", "created_at"], name="idx_dsty_ten_created"),
        ]

    def __str__(self):
        return f"{self.number} - {self.title}"

    def ensure_office_token(self):
        if not self.office_embed_token:
            self.office_embed_token = secrets.token_urlsafe(32)

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title) or "story"
            slug = base_slug
            counter = 1
            qs = BiDataStory.objects.filter(tenant=self.tenant)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            while qs.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug

        if isinstance(self.slides_data, list):
            self.slides_count = len(self.slides_data)
        else:
            self.slides_count = 0

        self.ensure_office_token()
        super().save(*args, **kwargs)
