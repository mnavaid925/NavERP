"""SCM 4.9 Quality Management — QualityInspection + InspectionResult, the execution record [QC-].

Realizes the *execution* half of the "Quality Inspection" bullet and carries the whole of the
"Certificate of Analysis (CoA)" bullet: a CoA is not a table, it is three stamp columns on the
outgoing inspection plus a REPORT over the results flagged ``include_on_coa``.

**The results are a SNAPSHOT.** :meth:`QualityInspection.generate_results` copies the plan's
characteristics — name, type, unit, limits, test method, critical/mandatory/CoA flags — onto
``InspectionResult`` rows once, and every reader afterwards reads the rows. This is the 4.8
BOM→WorkOrderComponent precedent applied to a document that gets *printed and sent to a customer*:
a plan re-issued with tighter limits next quarter must not retro-actively make last quarter's
certificate say something it never said.

**One writer per computed field.** ``status`` / ``usage_decision`` / ``action_taken`` and the three
CoA stamp columns are ``editable=False`` — the lifecycle actions own them, the form never sees
them, and the admin lists them read-only. ``InspectionResult.result`` has its own precedence rule;
see :func:`_evaluate`.

**No JournalEntry, ever (L29).** An inspection has no financial posting of any kind. The only
ledger effect anywhere in 4.9 is the ``adjustment`` StockMove a scrap disposition writes, and that
is :class:`~apps.scm.models.NonConformance`'s job, not this file's.
"""
from apps.scm.models._base import *  # noqa: F401,F403
# ABSOLUTE, and the module rather than the package: the snapshot's `characteristic_type` reuses the
# plan's choice tuple verbatim so the two can never drift, and importing from
# `apps.scm.models` here would be a circular import through the package __init__.
from apps.scm.models.QualityManagement.InspectionPlans import InspectionCharacteristic


def _evaluate(characteristic_type, measured_value, text_value, lower, upper, target,
              posted_result="pending"):
    """The ONE definition of pass/fail. Returns ``pass`` / ``fail`` / ``not_applicable`` / ``pending``.

    Precedence, by characteristic type — this is the whole rule, and it must not be re-implemented
    in a view, a template or a report:

    * ``instruction`` — there is nothing to judge, so the verdict is always ``not_applicable``.
    * ``measurement`` — DERIVED from the snapshotted limits and it overwrites whatever was posted.
      Outside either limit is a fail; inside is a pass; no recorded value is ``pending``. When the
      only figure is a target (no band), the measured value must equal it.
    * ``pass_fail`` / ``visual`` — subjective, so the INSPECTOR's verdict stands: ``posted_result``
      is returned when it is a real verdict, and ``pending`` until one is given. ``text_value`` is
      what they observed, not a criterion the machine can re-derive (``expected_text`` deliberately
      is not part of the snapshot — a human read it and decided).
    """
    if characteristic_type == "instruction":
        return "not_applicable"
    if characteristic_type == "measurement":
        if measured_value is None:
            return "pending"
        value = Decimal(measured_value)
        if lower is not None and value < Decimal(lower):
            return "fail"
        if upper is not None and value > Decimal(upper):
            return "fail"
        if lower is None and upper is None and target is not None:
            return "pass" if value == Decimal(target) else "fail"
        return "pass"
    return posted_result if posted_result in ("pass", "fail", "not_applicable") else "pending"


class QualityInspection(TenantNumbered):
    """One inspection event — a lot checked against a plan, with a verdict and a usage decision."""

    NUMBER_PREFIX = "QC"

    INSPECTION_TYPE_CHOICES = [
        ("incoming", "Incoming — against a goods receipt"),
        ("in_process", "In-process — against a work order"),
        ("outgoing", "Outgoing — against a shipment"),
        ("periodic_stock", "Periodic — stock on hand"),
    ]
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("in_progress", "In Progress"),
        ("passed", "Passed"),
        ("failed", "Failed"),
        ("on_hold", "On Hold"),
        ("cancelled", "Cancelled"),
    ]
    USAGE_DECISION_CHOICES = [
        ("pending", "Pending"),
        ("accept", "Accept"),
        ("accept_with_deviation", "Accept with Deviation"),
        ("reject", "Reject"),
    ]
    ACTION_TAKEN_CHOICES = [
        ("none", "None"),
        ("quarantined", "Quarantined"),
        ("ncr_raised", "NCR Raised"),
        ("returned_to_vendor", "Returned to Vendor"),
    ]
    #: Statuses whose header/results the inspector may still edit.
    EDITABLE_STATUSES = ("draft", "in_progress")
    #: Usage decisions that permit a certificate to be issued.
    ACCEPTING_DECISIONS = ("accept", "accept_with_deviation")

    plan = models.ForeignKey("scm.InspectionPlan", on_delete=models.SET_NULL, null=True, blank=True,
                             related_name="inspections",
                             help_text="Criteria snapshotted onto the result rows — the rows, not "
                                       "this link, are what the verdict is judged against")
    inspection_type = models.CharField(max_length=14, choices=INSPECTION_TYPE_CHOICES,
                                       default="incoming")
    # Source documents are CONTEXT, never a source of truth for the item: 4.1's GRN lines are free
    # text (there is no GoodsReceiptLine.item), so the item below is always picked explicitly.
    goods_receipt = models.ForeignKey("scm.GoodsReceiptNote", on_delete=models.SET_NULL, null=True,
                                      blank=True, related_name="quality_inspections")
    work_order = models.ForeignKey("scm.WorkOrder", on_delete=models.SET_NULL, null=True,
                                   blank=True, related_name="quality_inspections")
    shipment = models.ForeignKey("scm.Shipment", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="quality_inspections")

    item = models.ForeignKey("scm.Item", on_delete=models.PROTECT,
                             related_name="quality_inspections")
    lot_serial = models.ForeignKey("scm.LotSerial", on_delete=models.PROTECT, null=True, blank=True,
                                   related_name="quality_inspections")
    location = models.ForeignKey("scm.Location", on_delete=models.PROTECT, null=True, blank=True,
                                 related_name="quality_inspections")
    supplier = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="scm_quality_inspections")

    # Typed by the inspector — these are observations, not derived figures, so there is no
    # single-writer conflict. clean() keeps the arithmetic consistent.
    quantity_inspected = models.DecimalField(max_digits=14, decimal_places=4, default=0,
                                             validators=[MinValueValidator(ZERO)])
    sample_size = models.DecimalField(max_digits=14, decimal_places=4, default=0,
                                      validators=[MinValueValidator(ZERO)])
    quantity_accepted = models.DecimalField(max_digits=14, decimal_places=4, default=0,
                                            validators=[MinValueValidator(ZERO)])
    quantity_rejected = models.DecimalField(max_digits=14, decimal_places=4, default=0,
                                            validators=[MinValueValidator(ZERO)])

    inspector = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name="scm_inspections_performed",
                                  help_text="An employee party — 4.9 adds no person table")
    inspected_on = models.DateField()

    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="draft",
                              editable=False)
    usage_decision = models.CharField(max_length=22, choices=USAGE_DECISION_CHOICES,
                                      default="pending", editable=False)
    action_taken = models.CharField(max_length=20, choices=ACTION_TAKEN_CHOICES, default="none",
                                    editable=False)
    supplier_coa_reference = models.CharField(
        max_length=120, blank=True,
        help_text="The supplier's own certificate number — attach the PDF as a core.Document")
    notes = models.TextField(blank=True)

    # --- the CoA stamp: the issuance IS these three columns ------------------------------------
    # A standalone CertificateOfAnalysis register is deliberately deferred; `COA-` is reserved by
    # this field, assigned through next_number(..., field="coa_number").
    coa_number = models.CharField(max_length=20, blank=True, editable=False)
    coa_issued_on = models.DateTimeField(null=True, blank=True, editable=False)
    coa_issued_to = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True,
                                      blank=True, editable=False,
                                      related_name="scm_coa_certificates")

    class Meta:
        ordering = ["-inspected_on", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="scm_qc_tnt_status_idx"),
            models.Index(fields=["tenant", "inspection_type", "status"],
                         name="scm_qc_tnt_type_status_idx"),
            models.Index(fields=["tenant", "item"], name="scm_qc_tnt_item_idx"),
            models.Index(fields=["tenant", "lot_serial"], name="scm_qc_tnt_lot_idx"),
            models.Index(fields=["tenant", "coa_number"], name="scm_qc_tnt_coa_idx"),
            # Meta.ordering is ["-inspected_on", "-id"] and BOTH the list page and the CoA
            # register range-filter on inspected_on via _date_window — so the page sorted
            # and filtered on an unindexed column. Matches the app-wide document-date
            # pattern (StockMove(tenant, moved_at), SalesOrder, GoodsReceiptNote, and 4.9's
            # own QualityAudit(tenant, planned_date)).
            models.Index(fields=["tenant", "inspected_on"], name="scm_qc_tnt_insp_date_idx"),
        ]

    def __str__(self):
        return f"{self.number or 'QC'} · {self.item_id and self.item.sku}"

    def clean(self):
        super().clean()
        inspected = self.quantity_inspected or ZERO
        if (self.quantity_accepted or ZERO) + (self.quantity_rejected or ZERO) > inspected:
            raise ValidationError({"quantity_accepted": "Accepted plus rejected cannot exceed the "
                                                        "quantity inspected."})
        if (self.sample_size or ZERO) > inspected:
            raise ValidationError({"sample_size": "The sample cannot be larger than the quantity "
                                                  "inspected."})
        # A lot belongs to exactly one item. Scoping the dropdown to the tenant is not enough — a
        # crafted POST could pair item A with item B's lot, and the certificate would then certify
        # A's measurements under B's batch number.
        if self.lot_serial_id and self.item_id and self.lot_serial.item_id != self.item_id:
            raise ValidationError({"lot_serial": f"{self.lot_serial.number} belongs to "
                                                 f"{self.lot_serial.item.sku}, not {self.item.sku}."})

    # --- result rows -----------------------------------------------------------------------------
    def _result_rows(self):
        """Every result row, fetched ONCE per instance.

        Seven derived properties below read the same rows (the verdict, the counts, the CoA list and
        each of the seven CoA blockers). Calling ``self.results.all()`` in each of them is a fresh
        query every time — the detail page alone would fire eight. Cached on the instance and
        invalidated by :meth:`generate_results`, the only writer that adds rows.
        """
        if not hasattr(self, "_result_cache"):
            # Reuse a Prefetch when the caller supplied one. Chaining `.select_related("uom")` off
            # the related manager CLEARS the prefetch cache and re-queries, so a caller that
            # prefetched would otherwise pay for it twice and still get one query per row — which
            # is exactly what coa_report does over a whole page.
            prefetched = getattr(self, "_prefetched_objects_cache", {}).get("results")
            self._result_cache = (list(prefetched) if prefetched is not None
                                  else list(self.results.select_related("uom").all()))
        return self._result_cache

    def generate_results(self):
        """Snapshot the plan's characteristics onto result rows. Returns the number written.

        ONLY when the inspection has no results yet — the 4.8 ``explode_components()`` shape. A
        hand-corrected result set is never silently overwritten, and re-generating after a plan
        edit is deliberately impossible: that is the whole point of the snapshot.
        """
        if self.plan_id is None or self.results.exists():
            return 0
        characteristics = list(self.plan.characteristics.select_related("uom").all())
        InspectionResult.objects.bulk_create([
            InspectionResult(
                inspection=self, sequence=characteristic.sequence, characteristic=characteristic,
                characteristic_name=characteristic.name,
                characteristic_type=characteristic.characteristic_type,
                uom=characteristic.uom, target_value=characteristic.target_value,
                lower_limit=characteristic.lower_limit, upper_limit=characteristic.upper_limit,
                test_method=characteristic.test_method,
                include_on_coa=characteristic.include_on_coa,
                is_critical=characteristic.is_critical, is_mandatory=characteristic.is_mandatory,
                # An instruction has no verdict to reach — stamp it at creation so a plan full of
                # instructions cannot block `complete` on rows nobody can ever answer.
                result=("not_applicable" if characteristic.characteristic_type == "instruction"
                        else "pending"),
            )
            for characteristic in characteristics
        ])
        self.__dict__.pop("_result_cache", None)
        # The prefetch cache too, not just the instance cache: a prefetched instance that then
        # generates rows would keep returning the stale empty list it was prefetched with.
        getattr(self, "_prefetched_objects_cache", {}).pop("results", None)
        return len(characteristics)

    # --- derived state (nothing below is stored) -------------------------------------------------
    @property
    def is_editable(self):
        return self.status in self.EDITABLE_STATUSES

    @property
    def is_coa_issued(self):
        return bool(self.coa_number)

    @property
    def failed_count(self):
        return sum(1 for row in self._result_rows() if row.result == "fail")

    @property
    def pending_count(self):
        return sum(1 for row in self._result_rows() if row.result == "pending")

    @property
    def mandatory_pending_count(self):
        return sum(1 for row in self._result_rows()
                   if row.result == "pending" and row.is_mandatory)

    @property
    def has_critical_failure(self):
        return any(row.result == "fail" and row.is_critical for row in self._result_rows())

    @property
    def evaluated_result(self):
        """``pass`` / ``fail`` / ``pending`` for the lot as a whole.

        A failed CRITICAL or MANDATORY row fails the lot outright, whatever the rest say — the
        Siemens/SAP critical-characteristic rule. Only then does a still-unanswered mandatory row
        hold the verdict open; an optional row that failed still fails the lot, it just cannot
        pre-empt a mandatory one that has not been answered.
        """
        rows = self._result_rows()
        if not rows:
            return "pending"
        if any(row.result == "fail" and (row.is_critical or row.is_mandatory) for row in rows):
            return "fail"
        if any(row.result == "pending" and row.is_mandatory for row in rows):
            return "pending"
        if any(row.result == "fail" for row in rows):
            return "fail"
        return "pass"

    @property
    def coa_results(self):
        """The rows the certificate prints, in sequence."""
        return [row for row in self._result_rows() if row.include_on_coa]

    def coa_blockers(self):
        """Every reason this inspection may NOT be certified, as human strings. Empty = ready.

        Collected in ONE place so the report column, the Issue action and the print page can never
        disagree about what a valid certificate is. Rule 4 is the AlisQI rule and the reason the
        whole guard exists: a certificate must never carry an out-of-specification value.
        """
        blockers = []
        if self.inspection_type != "outgoing":
            blockers.append("Only an outgoing inspection can certify a shipped batch.")
        if self.status != "passed":
            blockers.append("The inspection has not passed.")
        if self.usage_decision not in self.ACCEPTING_DECISIONS:
            blockers.append("No usage decision has accepted this lot.")
        rows = self.coa_results
        failed = sum(1 for row in rows if row.result == "fail")
        pending = sum(1 for row in rows if row.result == "pending")
        if failed:
            blockers.append(f"{failed} included characteristic(s) are out of specification.")
        if pending:
            blockers.append(f"{pending} included characteristic(s) have no recorded value.")
        if self.lot_serial_id is None and self.item_id and self.item.tracking != "none":
            blockers.append("A lot/batch is required for a lot-tracked item.")
        if not rows:
            blockers.append("No characteristics are flagged for the certificate.")
        return blockers

    @property
    def coa_ready(self):
        return not self.coa_blockers()


class InspectionResult(models.Model):
    """One measured/observed characteristic. Tenant-less — reached only through its inspection."""

    RESULT_CHOICES = [
        ("pending", "Pending"),
        ("pass", "Pass"),
        ("fail", "Fail"),
        ("not_applicable", "Not Applicable"),
    ]

    inspection = models.ForeignKey("scm.QualityInspection", on_delete=models.CASCADE,
                                   related_name="results")
    sequence = models.PositiveIntegerField(default=10)
    # Traceability only, and editable=False for that reason: EVERY value rendered on a page or a
    # certificate comes from the snapshot columns below, never from this FK.
    characteristic = models.ForeignKey("scm.InspectionCharacteristic", on_delete=models.SET_NULL,
                                       null=True, blank=True, related_name="+", editable=False)

    # --- snapshot block: written once by generate_results(), read-only everywhere else ----------
    characteristic_name = models.CharField(max_length=255, editable=False)
    characteristic_type = models.CharField(
        max_length=16, choices=InspectionCharacteristic.CHARACTERISTIC_TYPE_CHOICES,
        default="measurement", editable=False)
    uom = models.ForeignKey("scm.UOM", on_delete=models.SET_NULL, null=True, blank=True,
                            related_name="+", editable=False)
    target_value = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True,
                                       editable=False)
    lower_limit = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True,
                                      editable=False)
    upper_limit = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True,
                                      editable=False)
    test_method = models.CharField(max_length=255, blank=True, editable=False)
    include_on_coa = models.BooleanField(default=False, editable=False)
    is_critical = models.BooleanField(default=False, editable=False)
    is_mandatory = models.BooleanField(default=True, editable=False)

    # --- inspector-typed -------------------------------------------------------------------------
    measured_value = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    text_value = models.CharField(max_length=255, blank=True)
    notes = models.CharField(max_length=255, blank=True)
    result = models.CharField(max_length=14, choices=RESULT_CHOICES, default="pending")

    class Meta:
        ordering = ["sequence", "id"]

    def __str__(self):
        return f"{self.characteristic_name} — {self.get_result_display()}"

    def save(self, *args, **kwargs):
        """The ONE writer of ``result`` — see :func:`_evaluate` for the precedence rule."""
        self.result = _evaluate(self.characteristic_type, self.measured_value, self.text_value,
                                self.lower_limit, self.upper_limit, self.target_value,
                                posted_result=self.result)
        return super().save(*args, **kwargs)

    @property
    def is_out_of_spec(self):
        return self.result == "fail"

    @property
    def spec_text(self):
        """The specification as printed on the certificate — from the snapshot alone.

        e.g. ``280.0000 – 320.0000 cd/m²``, ``≤ 0.0000``, ``≥ 16.0000``, ``= 16.0000``, or the
        observed criterion for a non-measurement row.
        """
        if self.characteristic_type != "measurement":
            return self.text_value or "—"
        unit = f" {self.uom.code}" if self.uom_id else ""
        if self.lower_limit is not None and self.upper_limit is not None:
            return f"{self.lower_limit} – {self.upper_limit}{unit}"
        if self.upper_limit is not None:
            return f"≤ {self.upper_limit}{unit}"
        if self.lower_limit is not None:
            return f"≥ {self.lower_limit}{unit}"
        if self.target_value is not None:
            return f"= {self.target_value}{unit}"
        return "—"
