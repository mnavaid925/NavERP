"""Projects 7.4 — CostControlAccount [CCA-]: the EVM structure and its forecast.

One row per control account — the PMBOK management point where a slice of the WBS is planned,
measured and forecast as money. Realizes 7.4 bullet **2 Cost Baseline & Control Accounts** and
bullet **4 Forecasting & EAC**: every earned-value metric lives here as a DERIVED property
(``bac``/``ev``/``pv``/``ac``/``committed``/``available``/``cv``/``sv``/``cpi``/``spi``/``eac``/
``etc``/``tcpi``/``vac``/``health``), never a stored column — stored EVM numbers go stale the
moment a line or expense lands, and a stale EVM figure is worse than none.

The baseline the metrics measure against is the project's **approved-and-activated**
``BudgetRevision`` (there is no separate cost-baseline table — Ruling 2): ``bac`` sums that
revision's budget lines mapped to THIS control account. ``contingency`` is the CA-held reserve,
kept separable from BAC per PMBOK (``bac_with_contingency``) and sized by 7.5 Risk Management.

``percent_complete`` is a manual attestation, not a computation — 7.8 Task & Work Management will
ship execution fields that supersede it; until then this is the honest EV input.

**No verbs** — the register is read + CRUD; the money movement verbs live on BudgetRevision
(governance) and ProjectExpense (evidence).
"""
from decimal import Decimal

from apps.projects.models._base import *  # noqa: F401,F403
from apps.projects.models._base import models


class CostControlAccount(TenantNumbered):
    NUMBER_PREFIX = "CCA"

    STATUS_CHOICES = [
        ("planning", "Planning"),
        ("active", "Active"),
        ("closed", "Closed"),
    ]

    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="control_accounts")
    name = models.CharField(max_length=255)
    #: The tenant's own control-account id (e.g. "CA-1.2") — unique per project in Meta.
    code = models.CharField(max_length=30)
    #: The WBS anchor: a deliverable node (or the project root) this CA measures. Same-project
    #: only — enforced in ``clean()`` (the ``anchor_task`` pattern).
    wbs_node = models.ForeignKey(
        "projects.ProjectTask", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="control_accounts",
        help_text="WBS node this account measures — a deliverable or the project root.")
    #: The ledger LENS, never a posting target: 2.x owns the GL (Ruling 6). PROTECT so an account
    #: a control account points at cannot silently vanish from the cost reports.
    gl_account = models.ForeignKey(
        "accounting.GLAccount", on_delete=models.PROTECT, null=True, blank=True,
        related_name="project_control_accounts")
    #: The CA-held reserve. Sized by 7.5, recorded here — money, kept separable from BAC (PMBOK).
    contingency = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))])
    #: Manually attested % — 7.8's execution fields supersede it (docstring contract).
    percent_complete = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
        help_text="Attested work progress feeding EV. Task-level execution (7.8) supersedes "
                  "this figure.")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="planning")
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        unique_together = ("tenant", "number"), ("tenant", "project", "code")
        indexes = [
            models.Index(fields=["tenant", "project"], name="cca_tnt_project_idx"),
            models.Index(fields=["tenant", "status"], name="cca_tnt_status_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.name}"

    def clean(self):
        super().clean()
        if self.wbs_node_id and self.project_id \
                and self.wbs_node.project_id != self.project_id:
            raise ValidationError(
                {"wbs_node": "The WBS node must belong to the same project as the control "
                             "account."})

    # -- the baseline the metrics measure against ---------------------------------------------------

    @property
    def active_revision(self):
        """The project's cost baseline: the approved BudgetRevision activated most recently."""
        return (self.project.budget_revisions
                .filter(status="approved", activated_at__isnull=False)
                .order_by("-activated_at")
                .first())

    # -- EVM inputs (all q2-clamped Decimals, all derived, NEVER columns) ----------------------------

    @property
    def bac(self):
        """Budget at completion: the active baseline's lines mapped to this CA. 0 with no
        baseline — a CA without an approved plan has no budget to earn against."""
        active = self.active_revision
        if active is None:
            return ZERO
        return q2(active.lines.filter(control_account_id=self.pk)
                  .aggregate(total=Sum("amount"))["total"])

    @property
    def bac_with_contingency(self):
        return q2(self.bac + self.contingency)

    @property
    def ev(self):
        """Earned value = BAC × attested progress."""
        return q2(self.bac * self.percent_complete / 100)

    @property
    def _pv_fraction(self):
        """Linear elapsed fraction of the anchored node's planned window (else the project's).

        Planning-grade by design: a real PV needs a time-phased BCWS curve, which no plan in the
        repo carries yet — a linear spread over the planned window is the honest stand-in and is
        labelled as such on the page (the ``critical_path_ids`` honesty precedent).
        """
        if self.wbs_node and self.wbs_node.planned_start and self.wbs_node.planned_end:
            start, end = self.wbs_node.planned_start, self.wbs_node.planned_end
        else:
            start, end = self.project.start_date, self.project.end_date
        if not (start and end) or end < start:
            return ZERO
        today = timezone.localdate()
        if today <= start:
            return ZERO
        if today >= end:
            return Decimal("1")
        if end == start:
            return Decimal("1")
        return Decimal((today - start).days) / Decimal((end - start).days)

    @property
    def pv(self):
        """Planned value = BAC × the linear window fraction. 0 before start, BAC after finish."""
        return q2(self.bac * self._pv_fraction)

    def _posted_amount(self, entry_types):
        """Sum of POSTED expenses of the given entry types — the only rows that burn budget.

        Drafts never burn (nobody approved the number yet); void rows stay visible but stop
        counting. Accruals burn like actuals: the cost is incurred, the paper may lag.
        """
        row = self.expenses.filter(
            status="posted", entry_type__in=entry_types,
        ).aggregate(total=Sum("amount"))
        return q2(row["total"])

    @property
    def ac(self):
        """Actual cost: posted actual + accrual expenses."""
        return self._posted_amount(("actual", "accrual"))

    @property
    def committed(self):
        """Committed cost: posted commitments (POs/contracts raised against this CA)."""
        return self._posted_amount(("commitment",))

    @property
    def available(self):
        """BAC not yet committed or spent — negative means over-committed."""
        return q2(self.bac - self.committed - self.ac)

    # -- variances, indices and the forecast ----------------------------------------------------------

    @property
    def cv(self):
        """Cost variance = EV − AC (negative = over cost)."""
        return q2(self.ev - self.ac)

    @property
    def sv(self):
        """Schedule variance = EV − PV (negative = behind plan)."""
        return q2(self.ev - self.pv)

    @property
    def cpi(self):
        """Cost performance index = EV / AC. ``None`` with no actuals — not 1.0, which would
        read as healthy, and not a ZeroDivisionError."""
        if not self.ac:
            return None
        return q2(self.ev / self.ac)

    @property
    def spi(self):
        """Schedule performance index = EV / PV. ``None`` before the window opens (PV = 0)."""
        if not self.pv:
            return None
        return q2(self.ev / self.pv)

    @property
    def eac(self):
        """Estimate at completion = BAC / CPI — the one documented technique (no method
        selector yet). Falls back to BAC with no actuals, i.e. 'plan unchanged'."""
        cpi = self.cpi
        if not cpi:
            return q2(self.bac)
        return q2(self.bac / cpi)

    @property
    def etc(self):
        """Estimate to complete = EAC − AC."""
        return q2(self.eac - self.ac)

    @property
    def tcpi(self):
        """To-complete performance index = (BAC − EV) / (BAC − AC) — the efficiency the remaining
        work must hit to land on budget. ``None`` when the denominator is 0 (at or over budget
        with nothing left to earn, the ratio is meaningless)."""
        denominator = self.bac - self.ac
        if not denominator:
            return None
        return q2((self.bac - self.ev) / denominator)

    @property
    def vac(self):
        """Variance at completion = BAC − EAC (negative = forecast over budget)."""
        return q2(self.bac - self.eac)

    @property
    def health(self):
        """Traffic-light dict: ``{"state", "badge"}`` — colour-named classes only (L33: the
        semantic variants do not exist). Over = money already committed beyond budget, or CPI
        under 0.95; watch = CPI under 1.00; else under. ``cpi is None`` (no actuals) can never
        be over on CPI alone — absence of spend is not distress."""
        cpi = self.cpi
        if self.available < 0 or (cpi is not None and cpi < Decimal("0.95")):
            return {"state": "over", "badge": "badge-red"}
        if cpi is not None and cpi < Decimal("1"):
            return {"state": "watch", "badge": "badge-amber"}
        return {"state": "under", "badge": "badge-green"}
