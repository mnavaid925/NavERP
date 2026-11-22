from django.core.exceptions import ValidationError
from django.db import models

from apps.documents.models._base import TenantNumbered

SECTION_TYPE_CHOICES = [
    ("header", "Document Header / Cover"),
    ("boilerplate", "Standard Boilerplate Clause"),
    ("disclaimer", "Legal Disclaimer / Notice"),
    ("signature_block", "Signature Block"),
    ("table_of_contents", "Table of Contents"),
    ("body_section", "Numbered Body Section"),
    ("appendix", "Appendix / Exhibit"),
    ("footer", "Document Footer"),
]


class TemplateSection(TenantNumbered):
    NUMBER_PREFIX = "DSEC"

    SECTION_TYPE_CHOICES = SECTION_TYPE_CHOICES

    template = models.ForeignKey(
        "documents.DocumentTemplate",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="sections",
        help_text="Parent document template, or null for reusable boilerplate blocks",
    )
    title = models.CharField(max_length=200)
    section_type = models.CharField(max_length=40, choices=SECTION_TYPE_CHOICES, default="body_section", db_index=True)
    content = models.TextField(blank=True, help_text="Modular clause text or section layout markup")
    order = models.PositiveIntegerField(default=10, help_text="Sort order within the template")
    is_locked = models.BooleanField(default=False, help_text="Locked sections cannot be modified or deleted by authors")
    is_mandatory = models.BooleanField(default=False, help_text="Mandatory clauses must be included in instantiated drafts")

    class Meta:
        ordering = ["template", "order", "id"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="doc_sec_tnt_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "section_type"], name="doc_sec_tnt_type_idx"),
            models.Index(fields=["tenant", "template", "order"], name="doc_sec_tnt_tmpl_ord_idx"),
        ]

    def __str__(self):
        parent = self.template.name if self.template else "Global Boilerplate"
        return f"{self.number} - {self.title} ({parent})"

    def clean(self):
        super().clean()
        if self.template_id and self.template.tenant_id != self.tenant_id:
            raise ValidationError({"template": "Parent template must belong to the same workspace."})
