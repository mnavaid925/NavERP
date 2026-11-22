from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.documents.models._base import TenantNumbered

TEMPLATE_TYPE_CHOICES = [
    ("sop", "Standard Operating Procedure (SOP)"),
    ("contract", "Contract / Agreement"),
    ("policy", "Corporate Policy / Governance"),
    ("report", "Business / Technical Report"),
    ("memo", "Internal Memorandum"),
    ("letter", "Official Correspondence / Letter"),
    ("specification", "Product / Technical Specification"),
    ("meeting_minutes", "Meeting Minutes"),
    ("other", "General Document Template"),
]

CATEGORY_CHOICES = [
    ("legal", "Legal & Compliance"),
    ("hr", "Human Resources"),
    ("operations", "Operations & Manufacturing"),
    ("finance", "Finance & Accounting"),
    ("it", "Information Technology & Security"),
    ("quality", "Quality & Safety"),
    ("sales", "Sales & Marketing"),
    ("executive", "Executive & Strategy"),
]


class DocumentTemplate(TenantNumbered):
    NUMBER_PREFIX = "DTMPL"

    TEMPLATE_TYPE_CHOICES = TEMPLATE_TYPE_CHOICES
    CATEGORY_CHOICES = CATEGORY_CHOICES

    name = models.CharField(max_length=200, db_index=True)
    template_type = models.CharField(max_length=40, choices=TEMPLATE_TYPE_CHOICES, default="sop", db_index=True)
    category = models.CharField(max_length=40, choices=CATEGORY_CHOICES, default="operations", db_index=True)
    description = models.TextField(blank=True)
    content = models.TextField(blank=True, help_text="Template body markup and token placeholders e.g. {{company_name}}")
    styling_rules = models.TextField(blank=True, help_text="CSS or formatting constraints")
    is_active = models.BooleanField(default=True)
    is_locked = models.BooleanField(default=False, help_text="Locked templates prevent structural alterations by authors")
    available_tokens = models.JSONField(default=dict, blank=True, help_text="Dictionary of token keys and descriptions")
    version = models.CharField(max_length=20, default="1.0")
    target_org_unit = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="doc_templates",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_doc_templates",
    )

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="doc_tmpl_tnt_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "template_type", "is_active"], name="doc_tmpl_tnt_type_idx"),
        ]

    def __str__(self):
        return f"{self.number} - {self.name} (v{self.version})"

    def clean(self):
        super().clean()
        if self.target_org_unit_id and self.target_org_unit.tenant_id != self.tenant_id:
            raise ValidationError({"target_org_unit": "Organization unit must belong to the same workspace."})
        if self.owner_id and self.owner.tenant_id != self.tenant_id:
            raise ValidationError({"owner": "Template owner must belong to the same workspace."})
