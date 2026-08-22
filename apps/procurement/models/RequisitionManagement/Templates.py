"""Procurement 6.2 Requisition Management — RequisitionTemplates models.

**Requisition Templates** bullet: pre-defined forms for recurring orders. A template is a named
blueprint of a requisition — header defaults plus item lines — that the Apply action turns into a
fresh ``scm.PurchaseRequisition`` DRAFT (the spine stays scm's, L36). The template itself stores
no money total: line values are estimates and the PR's ``recalc_totals()`` remains the single
writer of any derived figure, so nothing can drift between the two tables.

Line items are FREE-TEXT (``item_description``/``sku_hint``/``uom_hint``) mirroring
``scm.PurchaseRequisitionLine`` exactly, for the same reason it is: ``core.Item`` does not exist
yet (it lands with Module 5 Inventory; lesson L28 future migration).
"""
from apps.procurement.models._base import *  # noqa: F401,F403


class RequisitionTemplate(TenantNumbered):
    """A reusable requisition blueprint [RQT-]. Applying one drafts a new scm.PurchaseRequisition
    with the template's header defaults + lines, under the signed-in user's name."""

    NUMBER_PREFIX = "RQT"

    name = models.CharField(max_length=120, help_text="What this recurring order is, e.g. "
                              "'Monthly office supplies'")
    description = models.TextField(blank=True,
                                   help_text="When/how this template is meant to be used")
    org_unit = models.ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="procurement_requisition_templates",
                                 help_text="Pre-filled requesting department / cost centre")
    currency = models.ForeignKey("accounting.Currency", on_delete=models.SET_NULL, null=True,
                                 blank=True, related_name="procurement_requisition_templates")
    default_lead_days = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Applied requisitions fall due this many days ahead (blank = no date)")
    justification = models.TextField(blank=True,
                                     help_text="Pre-filled 'why this purchase is needed'")
    is_active = models.BooleanField(default=True, help_text="Inactive templates are hidden from "
                                                              "the apply action but kept for history")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                   blank=True, related_name="procurement_requisition_templates",
                                   editable=False)

    class Meta:
        ordering = ["name", "id"]
        unique_together = ("tenant", "number")

    @property
    def estimated_total(self):
        """Sum of the template's line estimates — derived on read, like every total here."""
        return sum((line.line_total for line in self.lines.all()), ZERO)

    def __str__(self):
        return f"{self.number or 'RQT'} · {self.name}"


class RequisitionTemplateLine(models.Model):
    """One standing item on a template. Mirrors ``scm.PurchaseRequisitionLine``'s editable fields;
    there is deliberately NO stored line_total — the estimate is computed on read."""

    template = models.ForeignKey("procurement.RequisitionTemplate", on_delete=models.CASCADE,
                                 related_name="lines")
    item_description = models.CharField(max_length=255, help_text="What is being requested")
    sku_hint = models.CharField(max_length=64, blank=True,
                                help_text="Vendor/catalog code, if known (free-text until core.Item exists)")
    uom_hint = models.CharField(max_length=32, blank=True, help_text="Unit of measure, e.g. each / box / kg")
    quantity = models.DecimalField(max_digits=14, decimal_places=4, default=1,
                                   validators=[MinValueValidator(Decimal("0.0001"))])
    estimated_unit_price = models.DecimalField(max_digits=14, decimal_places=2, default=0,
                                               validators=[MinValueValidator(ZERO)])
    gl_account = models.ForeignKey("accounting.GLAccount", on_delete=models.SET_NULL, null=True,
                                   blank=True, related_name="procurement_template_lines",
                                   help_text="Expense account to charge")

    class Meta:
        ordering = ["id"]

    @property
    def line_total(self):
        return q2((self.quantity or ZERO) * (self.estimated_unit_price or ZERO))

    def __str__(self):
        return f"{self.item_description} ×{self.quantity}"
