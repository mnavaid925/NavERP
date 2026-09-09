"""Projects 7.4 — ProjectExpense [PEX-]: the cost evidence that burns the budget.

One row per committed or incurred cost against a control account: ``entry_type`` discriminates a
``commitment`` (PO/contract raised — promised money) from an ``actual`` (money spent) and an
``accrual`` (cost incurred, paper pending). Realizes 7.4 bullet **3 Expense Tracking &
Commitments** and feeds ``ac``/``committed`` into bullets 2 and 4 — the EVM math reads exactly
these rows.

**Only POSTED rows burn budget.** A draft is nobody's approved number; a void row stays visible
and stops counting (the correction path — there are no negative rows: a reversal is a paired
void plus an adjustment entry, keeping ``amount`` non-negative like every money column since
migration 0002). Posted/void rows refuse edit and delete: they are the evidence the CPI/EAC
forecast stands on, and quietly rewriting evidence is how forecasts stop meaning anything.

``source_number`` is a SOFT reference (``PO-00042``, ``SIV-00187``) — never an FK: 4.x/6.x own
the PO and invoice engines and neither carries a project link (Ruling 5). The burn trend is an
aggregation over ``entry_date`` in the views — no snapshot table; charts are 7.16's.
"""
from apps.projects.models._base import *  # noqa: F401,F403
from apps.projects.models._base import models, settings


class ProjectExpense(TenantNumbered):
    NUMBER_PREFIX = "PEX"

    ENTRY_TYPE_CHOICES = [
        ("commitment", "Commitment"),
        ("actual", "Actual"),
        ("accrual", "Accrual"),
    ]
    SOURCE_KIND_CHOICES = [
        ("purchase_order", "Purchase Order"),
        ("supplier_invoice", "Supplier Invoice"),
        ("contract", "Contract"),
        ("timesheet", "Timesheet"),
        ("manual", "Manual"),
        ("accrual", "Accrual"),
    ]
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("posted", "Posted"),
        ("void", "Void"),
    ]

    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="expenses")
    #: Required, non-nullable: a CA-less cost row would silently drop out of every index and
    #: every EVM figure — better to refuse the row than to lose the money quietly.
    control_account = models.ForeignKey(
        "projects.CostControlAccount", on_delete=models.PROTECT, related_name="expenses")
    wbs_node = models.ForeignKey(
        "projects.ProjectTask", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="expenses")
    entry_type = models.CharField(
        max_length=10, choices=ENTRY_TYPE_CHOICES, default="actual")
    source_kind = models.CharField(
        max_length=16, choices=SOURCE_KIND_CHOICES, default="manual")
    source_number = models.CharField(
        max_length=30, blank=True,
        help_text="Reference in the owning system, e.g. PO-00042 or SIV-00187 — soft, never "
                  "an FK.")
    vendor = models.ForeignKey(
        "core.Party", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="project_expenses")
    gl_account = models.ForeignKey(
        "accounting.GLAccount", on_delete=models.PROTECT, null=True, blank=True,
        related_name="project_expenses")
    amount = models.DecimalField(
        max_digits=14, decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Non-negative — reversals are a paired void plus an adjustment row.")
    #: Face-value only, nothing converted (FX is 2.x/7.15's). Global table (L29).
    currency = models.ForeignKey(
        "accounting.Currency", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="project_expenses")
    #: The burn-trend dimension — required: a cost row without a date is meaningless.
    entry_date = models.DateField()
    #: Verb-driven (post/void) — OFF the form, so the evidence trail keeps its stamps.
    status = models.CharField(max_length=6, choices=STATUS_CHOICES, default="draft")
    description = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="pex_created")

    class Meta:
        ordering = ["-entry_date", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "project"], name="pex_tnt_project_idx"),
            models.Index(fields=["tenant", "control_account"], name="pex_tnt_ca_idx"),
            models.Index(fields=["tenant", "entry_type"], name="pex_tnt_etype_idx"),
            models.Index(fields=["tenant", "entry_date"], name="pex_tnt_date_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.get_entry_type_display()} {self.amount}"

    @property
    def is_locked(self):
        """Posted and void rows are frozen cost evidence — edit/delete refuse them."""
        return self.status in ("posted", "void")

    def clean(self):
        super().clean()
        if self.control_account_id and self.project_id \
                and self.control_account.project_id != self.project_id:
            raise ValidationError(
                {"control_account": "The control account must belong to the same project as "
                                    "the expense."})
        if self.wbs_node_id and self.project_id \
                and self.wbs_node.project_id != self.project_id:
            raise ValidationError(
                {"wbs_node": "The WBS node must belong to the same project as the expense."})
