"""SCM 4.9 Quality Management — InspectionPlan + InspectionCharacteristic, the criteria master.

Realizes the *definition of inspection criteria* half of the "Quality Inspection" bullet, and
doubles as the checklist a :class:`~apps.scm.models.QualityAudit` is run against
(``plan_type="audit_checklist"``) — which is why this file is read first: the audit and the
inspection both point at it.

**Deliberately NOT ``TenantNumbered``.** A plan is master data, keyed by a human-chosen ``code`` +
``version`` like ``Item.sku`` / ``Location.code`` / ``UOM.code`` / ``SupplierProfile``, not a
document with a running number. Do not "fix" this by adding a ``NUMBER_PREFIX``: the auto-number
prefixes are a finite shared namespace (``QC``/``NCR``/``CAPA``/``QA``/``COA`` are what 4.9 spends),
and a master that people refer to as *IQC-WS16 v2* gains nothing from also being *IP-00007*.

**The characteristics are copied, never referenced, once an inspection runs.**
:meth:`~apps.scm.models.QualityInspection.generate_results` SNAPSHOTS them onto ``InspectionResult``
rows (the 4.8 BOM→WorkOrderComponent precedent), so editing a plan next month cannot rewrite the
limits a certificate issued last month was measured against.
"""
from apps.scm.models._base import *  # noqa: F401,F403


class InspectionPlan(TenantOwned):
    """What to check, how much of it to check, and against which limits — a versioned master."""

    PLAN_TYPE_CHOICES = [
        ("incoming_receipt", "Incoming — goods receipt"),
        ("in_process", "In-process — production"),
        ("outgoing_shipment", "Outgoing — shipment"),
        ("periodic_stock", "Periodic — stock on hand"),
        ("audit_checklist", "Audit checklist"),
    ]
    SAMPLING_METHOD_CHOICES = [
        ("all_100", "100% — inspect every unit"),
        ("percentage", "Percentage of the lot"),
        ("fixed_count", "Fixed sample count"),
        ("aql", "AQL — accept/reject numbers"),
    ]
    FREQUENCY_CHOICES = [
        ("every", "Every receipt / run / shipment"),
        ("random_percent", "Randomly, a percentage of the time"),
        ("periodic", "Periodically"),
    ]
    #: Plan types that MUST name what they apply to. ``audit_checklist`` is the exception — it is
    #: scoped by the audit that uses it, not by an item/category/supplier.
    SCOPED_PLAN_TYPES = ("incoming_receipt", "in_process", "outgoing_shipment", "periodic_stock")

    code = models.CharField(max_length=32,
                            help_text="Short human key, e.g. IQC-WS16 — unique per version")
    name = models.CharField(max_length=255)
    plan_type = models.CharField(max_length=18, choices=PLAN_TYPE_CHOICES,
                                 default="incoming_receipt")
    item = models.ForeignKey("scm.Item", on_delete=models.SET_NULL, null=True, blank=True,
                             related_name="inspection_plans",
                             help_text="Applies to this item only — the most specific scope")
    item_category = models.ForeignKey("scm.ItemCategory", on_delete=models.SET_NULL, null=True,
                                      blank=True, related_name="inspection_plans",
                                      help_text="Applies to every item in this category")
    supplier = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="scm_inspection_plans",
                                 help_text="Applies to goods from this supplier")

    sampling_method = models.CharField(max_length=12, choices=SAMPLING_METHOD_CHOICES,
                                       default="all_100")
    sample_percentage = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(ZERO), MaxValueValidator(Decimal("100"))],
        help_text="Percentage of the lot to sample")
    sample_size = models.PositiveIntegerField(
        null=True, blank=True, validators=[MaxValueValidator(1000000)],
        help_text="Fixed number of units to sample")
    aql_accept_number = models.PositiveIntegerField(
        null=True, blank=True, validators=[MaxValueValidator(100000)],
        help_text="Lot is accepted at or below this many failures")
    aql_reject_number = models.PositiveIntegerField(
        null=True, blank=True, validators=[MaxValueValidator(100000)],
        help_text="Lot is rejected at or above this many failures")

    frequency = models.CharField(max_length=14, choices=FREQUENCY_CHOICES, default="every")
    frequency_value = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(ZERO), MaxValueValidator(Decimal("100"))],
        help_text="Percentage of events to inspect when sampling randomly")

    version = models.CharField(max_length=20, default="1")
    effective_from = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["code", "version"]
        unique_together = ("tenant", "code", "version")
        indexes = [
            models.Index(fields=["tenant", "plan_type", "is_active"],
                         name="scm_iplan_tnt_type_idx"),
            models.Index(fields=["tenant", "item"], name="scm_iplan_tnt_item_idx"),
        ]

    def __str__(self):
        return f"{self.code} v{self.version} · {self.name}"

    # --- validation --------------------------------------------------------------------------
    def clean(self):
        super().clean()
        if self.sampling_method == "percentage" and self.sample_percentage is None:
            raise ValidationError({"sample_percentage": "Percentage sampling needs a percentage."})
        if self.sampling_method == "fixed_count" and self.sample_size is None:
            raise ValidationError({"sample_size": "Fixed-count sampling needs a sample size."})
        if self.sampling_method == "aql":
            if self.aql_accept_number is None or self.aql_reject_number is None:
                raise ValidationError({"aql_accept_number": "AQL sampling needs both an accept and "
                                                            "a reject number."})
            # Oracle's rule: the lot is rejected at or above the rejection number, so the two
            # cannot meet — a plan where accept >= reject has an undefined band.
            if self.aql_reject_number <= self.aql_accept_number:
                raise ValidationError({"aql_reject_number": "The reject number must be greater "
                                                            "than the accept number."})
        if self.frequency == "random_percent" and self.frequency_value is None:
            raise ValidationError({"frequency_value": "Random sampling needs a percentage of "
                                                      "events to inspect."})
        scoped = any([self.item_id, self.item_category_id, self.supplier_id])
        if self.plan_type in self.SCOPED_PLAN_TYPES and not scoped:
            raise ValidationError({"item": "Name an item, a category or a supplier — a plan with no "
                                           "scope can never be selected for a trigger."})
        if self.plan_type == "audit_checklist" and scoped:
            raise ValidationError({"plan_type": "An audit checklist is scoped by the audit that "
                                                "uses it — clear the item, category and supplier."})

    # --- derived (nothing below is stored) -----------------------------------------------------
    @property
    def characteristic_count(self):
        return self.characteristics.count()

    def is_effective(self, on=None):
        """Active AND on/after its effective date (``None`` means always) — the BOM precedent."""
        if not self.is_active:
            return False
        on = on or timezone.localdate()
        return not (self.effective_from and on < self.effective_from)

    def sample_quantity(self, lot_quantity):
        """How many units this plan says to inspect out of ``lot_quantity``.

        ``aql`` falls back to the whole lot when no sample size is given: the accept/reject numbers
        bound the FAILURES, not the sample, so a plan that names neither has nothing else to go on.
        """
        lot_quantity = q4(lot_quantity)
        if lot_quantity <= ZERO:
            return ZERO
        if self.sampling_method == "percentage":
            return q4(lot_quantity * (self.sample_percentage or ZERO) / Decimal("100"))
        if self.sampling_method == "fixed_count":
            return q4(min(Decimal(self.sample_size or 0), lot_quantity))
        if self.sampling_method == "aql" and self.sample_size:
            return q4(min(Decimal(self.sample_size), lot_quantity))
        return lot_quantity

    @classmethod
    def for_trigger(cls, tenant, *, plan_type, item=None, supplier=None, on=None):
        """The plan an inspection of this kind should use — most specific wins.

        Precedence: item → the item's category → supplier → unscoped. ONE query fetches every
        candidate and the ranking happens in Python, deliberately: a per-tier query would be four
        round trips to answer a question whose candidate set is a handful of rows, and the
        effectivity rule (``effective_from`` null means open-ended) already lives in
        :meth:`is_effective` rather than in SQL.
        """
        if tenant is None:
            return None
        scope = Q(item__isnull=True, item_category__isnull=True, supplier__isnull=True)
        if item is not None:
            scope |= Q(item=item)
            if item.category_id:
                scope |= Q(item_category_id=item.category_id)
        if supplier is not None:
            scope |= Q(supplier=supplier)
        candidates = cls.objects.filter(tenant=tenant, plan_type=plan_type,
                                        is_active=True).filter(scope)

        def rank(plan):
            if item is not None and plan.item_id == item.pk:
                return 0
            if item is not None and plan.item_category_id and plan.item_category_id == item.category_id:
                return 1
            if supplier is not None and plan.supplier_id == supplier.pk:
                return 2
            return 3

        best = None
        best_rank = 99
        for plan in candidates:
            if not plan.is_effective(on):
                continue
            plan_rank = rank(plan)
            # Ties break on the later version/id, so re-issuing a plan supersedes it without
            # anyone having to deactivate the old row first.
            if plan_rank < best_rank or (plan_rank == best_rank and best is not None
                                         and plan.pk > best.pk):
                best, best_rank = plan, plan_rank
        return best


class InspectionCharacteristic(models.Model):
    """One thing to check on a plan. Tenant-less — reached only through its parent plan."""

    CHARACTERISTIC_TYPE_CHOICES = [
        ("measurement", "Measurement — numeric against limits"),
        ("pass_fail", "Pass / fail"),
        ("visual", "Visual check"),
        ("instruction", "Instruction — no result recorded"),
    ]

    plan = models.ForeignKey("scm.InspectionPlan", on_delete=models.CASCADE,
                             related_name="characteristics")
    sequence = models.PositiveIntegerField(default=10)
    name = models.CharField(max_length=255)
    characteristic_type = models.CharField(max_length=16, choices=CHARACTERISTIC_TYPE_CHOICES,
                                           default="measurement")
    uom = models.ForeignKey("scm.UOM", on_delete=models.SET_NULL, null=True, blank=True,
                            related_name="+")
    target_value = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    lower_limit = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    upper_limit = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    expected_text = models.CharField(max_length=255, blank=True,
                                     help_text="The pass criterion for a pass/fail or visual check")
    test_method = models.CharField(max_length=255, blank=True,
                                   help_text="How the value is obtained — printed on the certificate")
    is_critical = models.BooleanField(
        default=False,
        help_text="One failed critical characteristic fails the whole lot, whatever the rest say")
    is_mandatory = models.BooleanField(
        default=True, help_text="An inspection cannot be completed while this has no value")
    include_on_coa = models.BooleanField(
        default=False,
        help_text="Print this result on the Certificate of Analysis. This single flag is what "
                  "makes the CoA a REPORT over the inspection rather than a second table")

    class Meta:
        ordering = ["sequence", "id"]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        limits = (self.target_value, self.lower_limit, self.upper_limit)
        if self.characteristic_type == "measurement":
            if all(value is None for value in limits):
                raise ValidationError({"target_value": "A measurement needs a target, a lower "
                                                       "limit or an upper limit."})
            if (self.lower_limit is not None and self.upper_limit is not None
                    and self.upper_limit < self.lower_limit):
                raise ValidationError({"upper_limit": "The upper limit cannot be below the lower "
                                                      "limit."})
        elif any(value is not None for value in limits):
            # Keeps the SNAPSHOT honest: InspectionResult copies these three columns and evaluates
            # a measurement from them, so limits parked on a pass/fail row would be printed on a
            # certificate as a specification nothing was ever measured against.
            raise ValidationError({"target_value": "Only a measurement carries numeric limits — "
                                                   "clear them or change the type."})
        if self.include_on_coa and self.characteristic_type not in ("measurement", "pass_fail"):
            raise ValidationError({"include_on_coa": "Only a measurement or a pass/fail check can "
                                                     "be certified — an instruction has no result."})
