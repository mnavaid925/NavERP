"""Procurement 6.18 Inventory & Warehouse Integration — MaterialIssue [MIS-] + lines.

**The gap this closes.** A workspace can receive stock (4.1 GRN), correct it (``scm.StockAdjustment``),
count it (5.11), transfer it (4.3) and send it back to a vendor (6.12 ``ReturnToVendor``) — but
there is nowhere to record the ordinary thing that happens to most of it: somebody takes it off the
shelf and uses it. SAP calls that movement 201/261, Coupa and Precoro call it inventory
consumption. This is that document, and the return-to-stock mirror lives in the SAME document via
:attr:`MaterialIssue.movement_type` (SAP's 202/262 reversal pair; Precoro reverses a completed
consumption the same way). **There is no separate return document.**

**THE BRIDGE — and it is the whole design.** :meth:`MaterialIssue.post` mints a **draft**
``scm.StockAdjustment`` plus one line per issue line, and stores it on :attr:`adjustment`.
``apps/procurement`` writes **ZERO ``scm.StockMove`` rows**. SCM's own post action on that
adjustment is what writes the ledger, exactly as it does for every other adjustment in the system —
so there is one code path that moves stock and it lives in the app that owns the ledger (L36).

The pattern is copied deliberately from
``apps/inventory/models/StocktakingCycleCounting/CountPrograms.py:85-125``
(:meth:`CountProgram.generate_tasks`): mint the spine document, stamp a **provenance marker** on it
so the row explains where it came from, re-read the owning header under ``select_for_update()`` so
two near-simultaneous presses serialise, and **reuse an already-minted document rather than
double-minting**. Every one of those four properties is load-bearing here for the same reasons it
is there.

**Reason-code mapping, pinned.** ``StockAdjustment.reason = "other"`` for BOTH directions, with
direction carried by the **sign of ``quantity_delta``** (negative = issued out, positive = returned
to stock). ``write_off`` would assert the stock was destroyed and ``found`` that it appeared from
nowhere; neither is remotely true of an internal consumption, and a reason code that lies is worse
than a generic one because the valuation and shrinkage reports both read it.
``StockAdjustment.clean()`` (``apps/scm/models/InventoryManagement/StockAdjustments.py:58``)
requires a note whenever the reason is ``other`` — so the marker string is not decoration, it is
what keeps the minted document VALID if anybody re-validates it on SCM's own edit form.

**Cancellation after posting is refused.** The correction for a posted issue is the mirror
document — a ``return`` against the same location — never a delete and never a status flip. That is
the repo's compensating-move law (``apps/scm/models/InventoryManagement/StockMoves.py:5-7``): the
ledger is append-only, so an entry that turned out to be wrong is answered by another entry, not by
erasure.

**Import discipline.** Every cross-app FK is a STRING and every cross-app model class is imported
INSIDE the method that needs it, mirroring the rest of this app. Nothing here imports
``apps.scm.views._helpers`` — :meth:`MaterialIssue.on_hand_at_location` mirrors
``_insufficient_stock()``'s SHAPE (``apps/scm/views/_helpers.py:157``) rather than reaching into a
peer app's view internals (the ``resolve_line_item`` precedent,
``apps/procurement/models/ReceiptInspection/ReceiptTolerances.py:398-405``).
"""
from apps.core.utils import write_audit_log
from apps.procurement.models._base import *  # noqa: F401,F403


def _adjustment_cost_ceiling():
    """The largest ``unit_cost`` SCM will accept on one ``StockAdjustmentLine``.

    READ off that field's own ``MaxValueValidator`` rather than restated here, so raising or
    lowering SCM's cap can never leave a stale copy behind in procurement. Falls back to the widest
    value the column itself can hold if SCM ever drops the validator, which keeps the clamp a
    clamp rather than turning it into a silent zero.

    This exists because :meth:`MaterialIssue.post` writes its adjustment lines with
    ``bulk_create()``, and ``bulk_create()`` skips ``full_clean()`` — so the validator SCM put
    there never runs on this path.
    """
    from django.core.validators import MaxValueValidator
    from apps.scm.models import StockAdjustmentLine

    field = StockAdjustmentLine._meta.get_field("unit_cost")
    limit = next((v.limit_value for v in field.validators
                  if isinstance(v, MaxValueValidator)), None)
    if limit is None:
        limit = (Decimal(10) ** (field.max_digits - field.decimal_places)
                 - Decimal(10) ** -field.decimal_places)
    return limit


class MaterialIssue(TenantNumbered):
    """One goods issue out of a location, or one return of unused material back into it [MIS-]."""

    NUMBER_PREFIX = "MIS"

    #: Direction. ONE document type covers both, because a return of unused material IS the
    #: reversal of the issue that drew it — splitting them into two models would duplicate every
    #: field and then let the two drift.
    MOVEMENT_TYPE_CHOICES = [
        ("issue", "Issue"),
        ("return", "Return to stock"),
    ]
    #: SAP's 201 (cost centre) / 261 (order) split, generalised to the consumers a workspace
    #: actually has. It drives WHERE the cost lands, which is why it sits beside ``org_unit`` and
    #: ``gl_account`` rather than inside the notes.
    PURPOSE_CHOICES = [
        ("cost_centre", "Cost centre"),
        ("project", "Project"),
        ("work_order", "Work order"),
        ("maintenance", "Maintenance"),
        ("sample", "Sample"),
        ("other", "Other"),
    ]
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("submitted", "Submitted"),
        ("posted", "Posted"),
        ("cancelled", "Cancelled"),
    ]

    EDITABLE_STATUSES = ("draft",)
    #: ``submit()`` is draft → submitted. Named separately from EDITABLE_STATUSES even though the
    #: two currently hold the same tuple: they answer different questions, and coupling a verb's
    #: gate to an editability flag is how one of them silently changes the other later.
    SUBMITTABLE_STATUSES = ("draft",)
    #: A draft can be posted directly — a one-person store issue does not need a second pair of
    #: eyes to become a movement, and forcing a pointless submit step is how people stop using the
    #: document at all.
    POSTABLE_STATUSES = ("draft", "submitted")
    CANCELLABLE_STATUSES = ("draft", "submitted")

    #: theme.css defines ONLY badge-green / badge-red / badge-amber / badge-info / badge-muted /
    #: badge-slate (L33) — a semantic badge-success renders unstyled.
    STATUS_CSS = {"draft": "badge-muted", "submitted": "badge-amber",
                  "posted": "badge-green", "cancelled": "badge-slate"}
    MOVEMENT_CSS = {"issue": "badge-info", "return": "badge-green"}

    location = models.ForeignKey(
        "scm.Location", on_delete=models.PROTECT,
        related_name="procurement_material_issues",
        help_text="The location material is issued FROM, or returned TO. PROTECTed because a "
                  "posted issue is the evidence for a stock movement — deleting the location out "
                  "from under it would leave a movement nothing explains.")
    movement_type = models.CharField(
        max_length=8, choices=MOVEMENT_TYPE_CHOICES, default="issue",
        help_text="Issue takes stock out of the location; Return puts unused material back in. "
                  "Returning goods to a SUPPLIER is a different document — 6.12 Return to Vendor.")
    purpose = models.CharField(
        max_length=12, choices=PURPOSE_CHOICES, default="cost_centre",
        help_text="What consumed the material. 'Other' requires a note — a consumption nobody can "
                  "categorise is exactly the one that needs explaining.")
    reference = models.CharField(
        max_length=64, blank=True,
        help_text="Free text: the project, job or work-order number this was drawn for, e.g. "
                  "JOB-0042. Deliberately NOT a foreign key to scm.WorkOrder — that is module "
                  "4.8's manufacturing object and a procurement issue is not a production draw "
                  "(which is why StockMove carries separate 'consumption' and 'maintenance' move "
                  "types). Anything a store issues against, including a purely external job "
                  "number, can be keyed here.")
    issue_date = models.DateField(
        help_text="The date the material actually left (or came back to) the shelf. The minted "
                  "stock adjustment carries this same date, not today's.")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="draft")

    org_unit = models.ForeignKey(
        "core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="procurement_material_issues",
        help_text="The cost centre / department the consumption belongs to.")
    gl_account = models.ForeignKey(
        "accounting.GLAccount", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="procurement_material_issues",
        help_text="Default expense account for the document. A line may override it.")
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="procurement_material_issues_requested",
        help_text="Who asked for the material. Not necessarily who handed it over.")
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="procurement_material_issues_issued",
        help_text="Who posted the document (system-stamped at post).")

    adjustment = models.ForeignKey(
        "scm.StockAdjustment", on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="procurement_material_issues",
        help_text="The DRAFT scm.StockAdjustment this issue minted when it was posted. Stock does "
                  "not move until SCM posts THAT document. The CycleCountTask.adjustment "
                  "provenance precedent.")
    reservation = models.ForeignKey(
        "inventory.InventoryReservation", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="procurement_material_issues",
        help_text="Optional: the soft lock this issue consumes (SAP's MB21 reservation feeding the "
                  "MB1A issue). Linked out to, never re-declared here — 5.6 owns reservations.")

    posted_at = models.DateTimeField(null=True, blank=True, editable=False)
    cancelled_at = models.DateTimeField(null=True, blank=True, editable=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-issue_date", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="prc_mis_tnt_status_idx"),
            models.Index(fields=["tenant", "issue_date"], name="prc_mis_tnt_date_idx"),
            models.Index(fields=["tenant", "movement_type"], name="prc_mis_tnt_mvt_idx"),
        ]
        verbose_name = "Material Issue"
        verbose_name_plural = "Material Issues"

    def __str__(self):
        return f"{self.number or 'MIS-?'} · {self.get_movement_type_display()}"

    # ------------------------------------------------------------------ display helpers
    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.status, "badge-muted")

    @property
    def movement_css(self):
        return self.MOVEMENT_CSS.get(self.movement_type, "badge-muted")

    @property
    def is_issue(self):
        return self.movement_type == "issue"

    @property
    def is_editable(self):
        return self.status in self.EDITABLE_STATUSES

    @property
    def can_edit(self):
        return self.status in self.EDITABLE_STATUSES

    @property
    def can_submit(self):
        return self.status in self.SUBMITTABLE_STATUSES

    @property
    def can_post(self):
        return self.status in self.POSTABLE_STATUSES

    @property
    def can_cancel(self):
        return self.status in self.CANCELLABLE_STATUSES

    # ------------------------------------------------------------------ derived figures
    @property
    def total_value(self):
        """``Σ quantity × unit_cost`` across every line, in ONE aggregate.

        The ``StockAdjustment.value_impact()`` shape (``StockAdjustments.py:48``) — and it is
        deliberately the same shape, because the detail page shows this figure NEXT TO the minted
        adjustment's own ``value_impact()`` and the two must be computed identically or a reader
        would be left comparing two numbers that were never meant to agree. Unsigned: direction is
        a property of the document, not of its value.
        """
        value = self.lines.aggregate(
            v=Sum(F("quantity") * F("unit_cost"),
                  output_field=models.DecimalField(max_digits=20, decimal_places=4)))["v"] or ZERO
        return q2(value)

    def on_hand_at_location(self, item_ids):
        """``{item_id: on_hand}`` at THIS document's location, in ONE grouped query.

        A LOCAL mirror of ``_insufficient_stock()``'s shape (``apps/scm/views/_helpers.py:157``),
        not an import of it: peer apps do not reach into each other's view internals, and that
        helper answers a one-line question per call while this page and this post need the whole
        document answered at once. On-hand is the live ``StockMove`` aggregate, so it already
        reflects everything posted up to this instant.

        **Honest limitation, stated because the caller needs it.** This is scoped to
        ``(tenant, location, item)`` and NOT to a lot/serial, whereas ``_insufficient_stock()``
        narrows to the lot when a line names one. That is deliberate: the contract's
        ``availability`` context key is ``{item_id: on_hand}``, one row per item, so a per-lot
        breakdown could not be rendered against it — and this check is the PRE-flight one. The
        authoritative per-lot check happens where the stock actually moves, when SCM posts the
        adjustment this document mints. A line that names a lot with less in it than the item has
        in total therefore passes here and is caught there.
        """
        from apps.scm.models import StockMove

        item_ids = [i for i in set(item_ids or ()) if i]
        if not item_ids or not self.location_id:
            return {}
        rows = (StockMove.objects
                .filter(tenant_id=self.tenant_id, location_id=self.location_id,
                        item_id__in=item_ids)
                .values("item_id").annotate(q=Sum("quantity")))
        return {row["item_id"]: (row["q"] or ZERO) for row in rows}

    # ------------------------------------------------------------------ the verbs
    def submit(self, user=None):
        """Draft → submitted: the document is finished and waiting to be posted.

        ``select_for_update()`` on the header for the same reason every verb here takes it — two
        submits racing would each write ``submitted`` and each append an audit entry, which reads
        afterwards as two people submitting the same document.
        """
        with transaction.atomic():
            locked = type(self).objects.select_for_update().get(pk=self.pk)
            if locked.status not in self.SUBMITTABLE_STATUSES:
                raise ValidationError(
                    f"{locked.number} is {locked.get_status_display().lower()} — only a draft can "
                    f"be submitted.")
            if not locked.lines.exists():
                raise ValidationError(
                    f"{locked.number} has no lines. Add what is actually being "
                    f"{'issued' if locked.is_issue else 'returned'} before submitting it — an "
                    f"empty document moves nothing and tells the next reader nothing.")
            self.status = "submitted"
            self.save(update_fields=["status", "updated_at"])
        write_audit_log(user, self, "submit", {"from": locked.status})
        return True

    def post(self, user=None):
        """Mint the **draft** ``scm.StockAdjustment`` this issue becomes, and stamp it on the header.

        **This method writes no ``StockMove`` row and must never write one.** It produces a draft
        adjustment; SCM's own post action on that adjustment writes the ledger. One code path moves
        stock and it lives in the app that owns the ledger.

        Four properties, all copied from :meth:`CountProgram.generate_tasks`
        (``apps/inventory/models/StocktakingCycleCounting/CountPrograms.py:85-125``):

        1. **Re-read under ``select_for_update()``.** Two simultaneous Post presses serialise; the
           second finds the status already ``posted`` and refuses, instead of minting a second
           adjustment that would double the stock movement once SCM posted both.
        2. **Reuse, never double-mint.** If :attr:`adjustment` is already set the existing document
           is reused. That is the ``existing``/``created`` branch of ``generate_tasks()``, and it
           covers the one case the status gate cannot: an adjustment stamped by an earlier attempt
           whose header write did not land.
        3. **A provenance marker on the minted row**, so the adjustment explains itself in SCM
           without anybody having to come back here — and, because the reason code is ``other``,
           that marker is also what satisfies ``StockAdjustment.clean()``.
        4. **The availability guard runs BEFORE anything is minted**, so a refused post leaves no
           orphan draft adjustment behind.

        The guard applies to ``movement_type == "issue"`` ONLY. A return ADDS stock, so there is
        nothing to be short of — demanding availability for it would refuse exactly the document
        that fixes an over-issue. Demand is summed **per item across the whole document** first:
        two lines for the same item must not each pass against the full on-hand figure.

        Returns the ``scm.StockAdjustment``.
        """
        from apps.scm.models import StockAdjustment, StockAdjustmentLine

        with transaction.atomic():
            locked = (type(self).objects.select_for_update()
                      .select_related("tenant", "location").get(pk=self.pk))
            if locked.status not in self.POSTABLE_STATUSES:
                raise ValidationError(
                    f"{locked.number} is {locked.get_status_display().lower()} and cannot be "
                    f"posted again. A posted issue has already minted its stock adjustment; "
                    f"correct it with a mirror document, not by re-posting this one.")

            lines = list(locked.lines.select_related("item"))
            if not lines:
                raise ValidationError(
                    f"{locked.number} has no lines. There is nothing to "
                    f"{'issue' if locked.is_issue else 'return'}.")

            if locked.is_issue:
                items = {line.item_id: line.item for line in lines}
                wanted = {}
                for line in lines:
                    wanted[line.item_id] = wanted.get(line.item_id, ZERO) + (line.quantity or ZERO)
                on_hand = locked.on_hand_at_location(wanted.keys())
                shortfalls = []
                # Sorted by SKU so a multi-item shortfall reads in a stable order rather than in
                # whatever order the lines happened to come back in.
                for item_id in sorted(wanted, key=lambda i: items[i].sku):
                    need, available = wanted[item_id], on_hand.get(item_id, ZERO)
                    if need > available:
                        shortfalls.append(
                            f"{items[item_id].sku}: only {available} available at "
                            f"{locked.location.code}, cannot issue {need}.")
                if shortfalls:
                    # A LIST of messages, so ValidationError.messages carries one line per short
                    # item and the view surfaces every shortfall at once — a store person fixing
                    # them one refused post at a time is the shape this avoids.
                    raise ValidationError(shortfalls)

            if locked.adjustment_id:
                # Already minted by an earlier attempt — reuse it. Minting a second would double
                # the movement the moment SCM posted both.
                adjustment = locked.adjustment
                created = False
            else:
                marker = (f"Via material issue {locked.number} "
                          f"({locked.get_movement_type_display()}) · "
                          f"{locked.get_purpose_display()}")
                adjustment = StockAdjustment(
                    tenant_id=locked.tenant_id, location=locked.location,
                    # "other", never write_off/found — see the module docstring. The marker above
                    # is what keeps StockAdjustment.clean() satisfied for that reason code.
                    reason="other", adjustment_date=locked.issue_date, status="draft",
                    notes=marker)
                adjustment.save()   # save(), not create(): TenantNumbered mints ADJ-##### here
                # Issue removes stock, return adds it. The direction lives in this sign and
                # nowhere else — which is why both directions can share one reason code.
                sign = -1 if locked.is_issue else 1
                # bulk_create() bypasses full_clean(), so StockAdjustmentLine's own
                # MaxValueValidator on unit_cost never runs on this path — and SCM's comment on
                # that validator describes exactly this route: a tenant member drafts the line and
                # a tenant-admin posts it, so an absurd cost would otherwise ride a bulk approval
                # straight into the valuation report. Our snapshot column is DecimalField(14, 4),
                # four orders of magnitude wider than SCM's ceiling, so the gap is real: without
                # the clamp the write either lands an unvalidated figure in the ledger or raises a
                # raw database error mid-post. Resolved ONCE per post, not per line.
                cost_ceiling = _adjustment_cost_ceiling()
                StockAdjustmentLine.objects.bulk_create([
                    StockAdjustmentLine(
                        adjustment=adjustment, item_id=line.item_id,
                        lot_serial_id=line.lot_serial_id,
                        quantity_delta=sign * (line.quantity or ZERO),
                        # bulk_create bypasses save(), so every column a line needs is set right
                        # here. StockAdjustmentLine derives nothing in save() today, and unit_cost
                        # is read straight off our own line's snapshot — a zero here would total
                        # to a zero value_impact() on a document full of real stock.
                        unit_cost=min(line.unit_cost or ZERO, cost_ceiling))
                    for line in lines])
                created = True

            self.adjustment = adjustment
            self.status = "posted"
            self.posted_at = timezone.now()
            self.issued_by = user if getattr(user, "is_authenticated", False) else None
            self.save(update_fields=["adjustment", "status", "posted_at", "issued_by",
                                     "updated_at"])

        write_audit_log(user, self, "post",
                        {"adjustment": adjustment.number, "minted": created,
                         "lines": len(lines)})
        return adjustment

    def cancel(self, user=None):
        """Abandon an unposted document. **Refused once posted.**

        A posted issue has minted a stock adjustment, and that adjustment may already have been
        posted into the ledger by SCM. Flipping this header to ``cancelled`` would leave an
        adjustment — and possibly real stock movements — with nothing on this side saying they were
        meant. The correction is the mirror document: a ``return`` against the same location for
        the same items, which is why ``movement_type`` exists on this model at all.
        """
        with transaction.atomic():
            locked = type(self).objects.select_for_update().get(pk=self.pk)
            if locked.status not in self.CANCELLABLE_STATUSES:
                raise ValidationError(
                    f"{locked.number} is {locked.get_status_display().lower()} and cannot be "
                    f"cancelled. A posted issue has already minted its stock adjustment — correct "
                    f"it by raising a return against the same location for the same items, never "
                    f"by cancelling or deleting this document.")
            self.status = "cancelled"
            self.cancelled_at = timezone.now()
            self.save(update_fields=["status", "cancelled_at", "updated_at"])
        write_audit_log(user, self, "cancel", {"from": locked.status})
        return True

    # ------------------------------------------------------------------ validation
    def clean(self):
        super().clean()
        errors = {}
        tenant_id = getattr(self, "tenant_id", None)
        if tenant_id:
            for field in ("location", "org_unit", "gl_account", "requested_by", "issued_by",
                          "adjustment", "reservation"):
                if not getattr(self, f"{field}_id", None):
                    continue
                if getattr(getattr(self, field, None), "tenant_id", None) != tenant_id:
                    errors[field] = "That record belongs to another workspace."

        if self.purpose == "other" and not (self.notes or "").strip():
            # The StockAdjustment.clean() precedent (StockAdjustments.py:58): a catch-all category
            # with no explanation is the one row nobody can account for later.
            errors["notes"] = ("Say what this was for. 'Other' is the one purpose that explains "
                               "nothing on its own.")

        if self.reservation_id:
            if self.movement_type == "return":
                errors["reservation"] = (
                    "A reservation is consumed by an issue, not by a return. Returning material to "
                    "stock releases a lock rather than drawing against one — clear the reservation "
                    "or change this to an issue.")
            reservation = getattr(self, "reservation", None)
            if reservation is not None and self.location_id and \
                    reservation.location_id != self.location_id:
                errors["reservation"] = (
                    f"{reservation.number} holds stock at a different location. A reservation can "
                    f"only be drawn down where the units are actually held.")
            elif reservation is not None and self.pk:
                # Only checkable once the document has lines, and only "at least one line", because
                # a reservation covers ONE item while an issue can legitimately draw several.
                line_items = set(self.lines.values_list("item_id", flat=True))
                if line_items and reservation.item_id not in line_items:
                    errors["reservation"] = (
                        f"{reservation.number} reserves an item that is not on this issue. Add a "
                        f"line for it, or clear the reservation — a lock this document never draws "
                        f"on would stay held forever.")

        if errors:
            raise ValidationError(errors)


class MaterialIssueLine(models.Model):
    """One item's worth of an issue or return, valued at the moving-average cost of the moment.

    ``unit_cost`` is a **snapshot**, stamped in :meth:`save` from ``Item.average_cost``
    (``apps/scm/models/InventoryManagement/Items.py:105``) and ``editable=False`` thereafter. It is
    a snapshot for the same reason every snapshot in this sub-module is one: the document has to
    still explain its own value after the item's moving average has rolled on. Nobody types it.
    """

    issue = models.ForeignKey(MaterialIssue, on_delete=models.CASCADE, related_name="lines")
    item = models.ForeignKey("scm.Item", on_delete=models.PROTECT,
                             related_name="procurement_material_issue_lines")
    lot_serial = models.ForeignKey(
        "scm.LotSerial", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="procurement_material_issue_lines",
        help_text="Optional lot/batch or serial for a tracked item. It rides through to the minted "
                  "stock adjustment line, so the ledger records which lot actually moved.")
    gl_account = models.ForeignKey(
        "accounting.GLAccount", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="procurement_material_issue_lines",
        help_text="Per-line override of the document's expense account.")

    quantity = models.DecimalField(
        max_digits=16, decimal_places=4, validators=[MinValueValidator(Decimal("0.0001"))],
        help_text="Always POSITIVE. Direction comes from the document's movement type, which is "
                  "what becomes the sign on the stock adjustment line.")
    unit_cost = models.DecimalField(
        max_digits=14, decimal_places=4, default=0, editable=False,
        help_text="Snapshot of the item's moving-average cost when the line was added.")
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["item__sku", "id"]
        verbose_name = "Material Issue Line"
        verbose_name_plural = "Material Issue Lines"

    def __str__(self):
        if not self.item_id:
            return "Material issue line"
        return f"{self.item.sku} ×{self.quantity}"

    @property
    def line_value(self):
        """``quantity × unit_cost`` — derived on read, never stored.

        A stored line value is a third number that can disagree with the two it comes from.
        """
        return (self.quantity or ZERO) * (self.unit_cost or ZERO)

    def save(self, *args, **kwargs):
        """Stamp the cost snapshot once, on the way in.

        **``bulk_create`` bypasses this method**, so any bulk path — a seeder, an import — must set
        ``unit_cost`` itself or it will write a column of zeros that totals to a zero-value
        document full of real stock.
        """
        if not self.unit_cost and self.item_id:
            self.unit_cost = getattr(self.item, "average_cost", None) or ZERO
        return super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        errors = {}
        # Tenant is reached through the ISSUE — this model has no tenant column of its own.
        tenant_id = self.issue.tenant_id if self.issue_id else None
        if tenant_id:
            for field in ("item", "lot_serial", "gl_account"):
                if not getattr(self, f"{field}_id", None):
                    continue
                if getattr(getattr(self, field, None), "tenant_id", None) != tenant_id:
                    errors[field] = "That record belongs to another workspace."

        # A lot belongs to exactly one item (LotSerials.py:16). A line naming a lot of a DIFFERENT
        # item would draw that lot's stock down against this item's balance on the minted
        # adjustment — the same class of bug _insufficient_stock() scopes its lot check to avoid.
        if self.lot_serial_id and self.item_id:
            lot = getattr(self, "lot_serial", None)
            if lot is not None and lot.item_id != self.item_id:
                errors["lot_serial"] = "That lot/serial belongs to a different item."

        if errors:
            raise ValidationError(errors)
