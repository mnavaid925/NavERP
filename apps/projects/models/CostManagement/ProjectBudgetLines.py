"""Projects 7.4 — ProjectBudgetLine [PBL-]: the row the whole sub-module rolls up from.

One budgeted amount per category (labor/material/equipment/subcontract/overhead/contingency/
other) anchored where the money lands: a ``budget_revision`` (the line is only real inside a
revision — the baseline is the approved one), an optional WBS work package (the bottom-up rollup
source), an optional control account (the EVM lens) and an optional GL account (the ledger lens,
never a posting — Ruling 6).

**No ``hours``, no ``rate``** — Ruling 1: 7.4 stores amounts, never rates. 7.3 ships no money
columns and a future rate card may *generate* an ``amount``; it may not add rate fields here.

``project`` is denormalised on purpose so every register filter is a single-table predicate;
``clean()`` pins it to the revision's project, and the WBS node and control account to the
project. Category totals and the project total are view-level aggregations — never columns.
"""
from apps.projects.models._base import *  # noqa: F401,F403
from apps.projects.models._base import models


class ProjectBudgetLine(TenantNumbered):
    NUMBER_PREFIX = "PBL"

    CATEGORY_CHOICES = [
        ("labor", "Labor"),
        ("material", "Material"),
        ("equipment", "Equipment"),
        ("subcontract", "Subcontract"),
        ("overhead", "Overhead"),
        ("contingency", "Contingency"),
        ("other", "Other"),
    ]

    budget_revision = models.ForeignKey(
        "projects.BudgetRevision", on_delete=models.CASCADE, related_name="lines",
        help_text="The budget version this line belongs to — the approved-and-activated "
                  "revision is the cost baseline.")
    #: Denormalised from the revision for single-table filters; clean() pins it to match.
    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="budget_lines")
    #: Required on the form — a line without a category rolls into nothing.
    category = models.CharField(max_length=14, choices=CATEGORY_CHOICES)
    wbs_node = models.ForeignKey(
        "projects.ProjectTask", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="budget_lines",
        help_text="Work package this money is planned against — the bottom-up rollup source.")
    control_account = models.ForeignKey(
        "projects.CostControlAccount", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="budget_lines",
        help_text="EVM lens: the active baseline's lines per account are that account's BAC.")
    gl_account = models.ForeignKey(
        "accounting.GLAccount", on_delete=models.PROTECT, null=True, blank=True,
        related_name="project_budget_lines")
    amount = models.DecimalField(
        max_digits=14, decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))])
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "project"], name="pbl_tnt_project_idx"),
            models.Index(fields=["tenant", "budget_revision"], name="pbl_tnt_rev_idx"),
            models.Index(fields=["tenant", "control_account"], name="pbl_tnt_ca_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.get_category_display()} {self.amount}"

    def clean(self):
        super().clean()
        if self.budget_revision_id and self.project_id \
                and self.budget_revision.project_id != self.project_id:
            raise ValidationError(
                {"project": "The project must match the budget revision's project."})
        if self.wbs_node_id and self.project_id \
                and self.wbs_node.project_id != self.project_id:
            raise ValidationError(
                {"wbs_node": "The WBS node must belong to the same project as the line."})
        if self.control_account_id and self.project_id \
                and self.control_account.project_id != self.project_id:
            raise ValidationError(
                {"control_account": "The control account must belong to the same project as "
                                    "the line."})
