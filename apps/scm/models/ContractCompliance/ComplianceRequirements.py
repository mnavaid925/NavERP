"""SCM 4.12 Contract & Compliance Management — ``ComplianceRequirement`` [CR-] + ``ComplianceCheck``.

**What this is.** The standing-obligation register: one row per thing this workspace has to keep
proving — an FDA/FSMA control, a HazMat classification, a GDPR data clause, an ISO surveillance
audit, a certificate of insurance, a supplier contract's SLA credit, a licence proviso. Each row
carries where the obligation comes from (``source`` / ``source_reference`` / ``framework``), who is
answerable (``owner``), what it applies to (``scope`` + the five typed pointers), how often it must
be re-proved (``frequency`` / ``next_due_date`` / ``notice_days``) and where it stands
(``status``). ``ComplianceCheck`` is the proof history — one row per cycle actually performed,
with the finding and the evidence document.

**Why a register and not a second contract or licence table.** ``contract`` and ``license`` are
*link-out* FKs. 4.2 already owns the agreement (``scm.SupplierContract`` — party, type, dates,
value, currency, terms, renewal window), and 4.12's own ``TradeLicense`` owns the authorisation.
Neither is re-modelled here; an obligation that comes out of one simply points at it. That is the
4.9 precedent where "an audit finding IS a ``NonConformance`` with ``source='audit'``" rather than
a parallel findings table.

**Why those link-outs are ``SET_NULL`` and not ``CASCADE``.** Deleting a contract must not silently
destroy the proof history of an obligation that was met. The evidence that we *were* compliant
outlives the paper that created the duty — a regulator asks what was done, not whether the source
record still exists. ``SET_NULL`` also keeps the 4.2 extension behaviour-neutral: 4.2's
``contract_delete`` needs no change and cannot suddenly start deleting 4.12 rows. Every other
outward pointer (``org_unit`` / ``party`` / ``location`` / ``item`` / ``document``) is ``SET_NULL``
for the same reason, and :attr:`ComplianceRequirement.scope_label` is what stops a *scoped* row
whose subject vanished from silently reading as workspace-wide.

**Why five typed scope FKs and not one ``scope_ref`` integer.** A bare int carries neither a tenant
nor a type, so it happily points at a deleted or cross-tenant row and the page narrows to the wrong
subject without saying so. With real FKs, :meth:`ComplianceRequirement.clean` can verify the tenant
and the database can ``SET_NULL`` the pointer when the subject goes away. Same reasoning as 4.11's
``KpiTarget``.

**Why ``notice_days`` is capped at 3650.** It is compared against a date and fed into date
arithmetic. ``PositiveIntegerField`` accepts 4294967295 on MariaDB, and that is an uncaught
``OverflowError`` — a 500, not a validation error (the 4.10 denial-of-service finding). Every
day-count column in this app carries the same ``MinValueValidator(0)`` /
``MaxValueValidator(3650)`` pair.

**Why ``compliance_rate`` is a property and returns ``None``, never ``0``.** A stored pass-rate goes
stale the instant a check is edited or deleted and nothing recomputes it — the mistake 4.7 shipped,
regretted and fixed, and the reason 4.9's ``findings_major`` is a property. It is derived from the
child rows on read. It returns ``None`` when there is nothing to divide by, so a requirement that
has never been checked renders "—" rather than a confident red 0% that reads as *failing* when the
truth is *unknown* (the 4.11 ``projected_stockout_count`` lesson). ``last_checked_on`` is the one
exception and is a *stamp*, not a derivation: it records an event, is written only by
:meth:`ComplianceRequirement.record_check`, and is ``editable=False`` so no form can type it (L22).

**Why ``ComplianceCheck`` has no ``tenant`` column.** It is a pure child of exactly one parent,
never listed or filtered on its own — the ``TrackingEvent`` / ``InspectionResult`` /
``SupplierCatalogItem`` precedent. Its tenant is ``requirement.tenant``, and views MUST resolve it
as ``get_object_or_404(ComplianceCheck, pk=pk, requirement__tenant=request.tenant)``. Because it
has no tenant of its own, ``TenantModelForm`` cannot scope its ``evidence`` dropdown for free, so
this module validates that FK against the parent's tenant itself — a narrowed dropdown has never
held against a crafted POST.

**Why ``corrective_reference`` is free text and not an FK to 4.9's ``NonConformance``.** Linking
properly means adding a ``compliance`` value to a shipped sub-module's ``SOURCE_CHOICES`` (and
``NonConformance.source`` is ``max_length=14``, so it is a column widen, not a one-line migration).
Refactoring a shipped sub-module for a convenience link is exactly what 4.11 declined to do. The
NCR/CAPA number is recorded as text this pass; the FK is parked in the plan's deferred list.

**No ``FileField`` anywhere in 4.12.** Attachments are ``core.Document`` — the generic,
tenant-scoped, classified attachment ``SupplierContract.document`` already uses. Module 13 (DMS)
owns folders and versioning; 4.12 must not grow a second file store.
"""
import calendar
import datetime

from django.db.models import Count

from apps.scm.models._base import *  # noqa: F401,F403


#: ``scope`` value → the FK field that carries the subject. ``None`` means the scope needs no
#: pointer. Declared once so ``clean()``'s exactly-one guard, :meth:`resolved_scope` and
#: :attr:`scope_label` can never disagree about which pointer a scope reads.
_SCOPE_FIELDS = {
    "tenant": None,
    "org_unit": "org_unit",
    "party": "party",
    "location": "location",
    "item": "item",
}

#: The four typed scope FKs, derived from ``_SCOPE_FIELDS`` rather than re-listed — adding a scope
#: must not require a matching edit here or the two drift apart silently.
_SCOPE_FK_FIELDS = tuple(field for field in _SCOPE_FIELDS.values() if field)

#: Every outward FK whose target is tenant-scoped. ``clean()`` walks this list, so a pointer added
#: later is covered by the cross-tenant guard the moment it is named here.
_TENANT_SCOPED_FK_FIELDS = _SCOPE_FK_FIELDS + ("contract", "license", "document")

#: ``frequency`` → months to add when a passed check advances the cycle. ``one_time`` and
#: ``on_event`` are deliberately ABSENT: neither has a next cycle, so a pass clears the due date
#: rather than inventing one.
_FREQUENCY_MONTHS = {
    "monthly": 1,
    "quarterly": 3,
    "semi_annual": 6,
    "annual": 12,
    "biennial": 24,
}


def _add_months(value, months):
    """``value`` plus ``months`` calendar months, clamped to the target month's last day.

    ``python-dateutil`` is not a dependency of this repo, so this is the stdlib
    ``calendar.monthrange`` idiom ``crm.Task`` and ``hrm`` already use. Clamping is the whole point:
    an annual obligation due on 31 January must land on 31 January, and a quarterly one due on
    31 March must land on 30 June — not silently roll into July.
    """
    total = value.year * 12 + (value.month - 1) + int(months)
    year, month = divmod(total, 12)
    month += 1
    return datetime.date(year, month, min(value.day, calendar.monthrange(year, month)[1]))


class ComplianceRequirement(TenantNumbered):
    """One standing obligation, its cadence, its subject and where it stands [CR-]."""

    NUMBER_PREFIX = "CR"

    # --- vocabulary -------------------------------------------------------------------------------
    SOURCE_CHOICES = [
        ("regulation", "Regulation"),
        ("contract", "Contract"),
        ("license", "Licence"),
        ("certification", "Certification"),
        ("customer_requirement", "Customer Requirement"),
        ("internal_policy", "Internal Policy"),
    ]
    # max_length 24 against a 22-char longest value (``customs_export_control``). Deliberate slack:
    # NonConformance.source was sized to its longest value at 14, and the first 15-char value was a
    # column widen rather than the "one-line migration" it looked like (the 4.10 lesson).
    FRAMEWORK_CHOICES = [
        ("fda_fsma", "FDA / FSMA"),
        ("hazmat_dot_iata_imdg", "HazMat — DOT / IATA / IMDG"),
        ("ghs_clp", "GHS / CLP"),
        ("data_privacy_gdpr", "Data Privacy / GDPR"),
        ("reach", "REACH"),
        ("rohs", "RoHS"),
        ("prop65_scip", "Prop 65 / SCIP"),
        ("forced_labor_uflpa", "Forced Labour / UFLPA"),
        ("conflict_minerals", "Conflict Minerals"),
        ("eudr", "EUDR — Deforestation"),
        ("csddd_lksg", "CSDDD / LkSG Due Diligence"),
        ("iso_9001", "ISO 9001"),
        ("iso_14001", "ISO 14001"),
        ("customs_export_control", "Customs / Export Control"),
        ("insurance_coi", "Insurance / COI"),
        ("other", "Other"),
    ]
    # The post-signature obligation taxonomy, verbatim from the contract-lifecycle products this
    # register is modelled on. Blank is legitimate: a pure regulatory row is not a contract clause.
    OBLIGATION_CATEGORY_CHOICES = [
        ("financial", "Financial"),
        ("delivery", "Delivery"),
        ("service_levels", "Service Levels"),
        ("termination", "Termination"),
        ("confidentiality", "Confidentiality"),
        ("regulatory", "Regulatory"),
        ("data", "Data"),
        ("insurance", "Insurance"),
        ("other", "Other"),
    ]
    # The display labels ARE the page text: scope_label renders "Supplier: Acme Ltd" and, for the
    # pointer-less scope, the bare label "Whole workspace".
    SCOPE_CHOICES = [
        ("tenant", "Whole workspace"),
        ("org_unit", "Org unit"),
        ("party", "Supplier"),
        ("location", "Location"),
        ("item", "Item"),
    ]
    FREQUENCY_CHOICES = [
        ("one_time", "One-time"),
        ("monthly", "Monthly"),
        ("quarterly", "Quarterly"),
        ("semi_annual", "Semi-annual"),
        ("annual", "Annual"),
        ("biennial", "Every two years"),
        ("on_event", "On event"),
    ]
    STATUS_CHOICES = [
        ("applicable", "Applicable"),
        ("not_applicable", "Not Applicable"),
        ("in_progress", "In Progress"),
        ("compliant", "Compliant"),
        ("non_compliant", "Non-Compliant"),
        ("overdue", "Overdue"),
        ("retired", "Retired"),
    ]
    CRITICALITY_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("critical", "Critical"),
    ]

    # Colour is decided HERE, in one place, so a list badge and a detail badge can never disagree.
    # theme.css ships colour-named badges ONLY — badge-green / badge-red / badge-amber / badge-info
    # / badge-muted / badge-slate. badge-success / badge-warning / badge-danger do not exist and
    # render as unstyled text (L33).
    STATUS_CSS = {
        "applicable": "badge-info",
        "not_applicable": "badge-muted",
        "in_progress": "badge-amber",
        "compliant": "badge-green",
        "non_compliant": "badge-red",
        "overdue": "badge-red",
        "retired": "badge-slate",
    }
    CRITICALITY_CSS = {
        "low": "badge-muted",
        "medium": "badge-info",
        "high": "badge-amber",
        "critical": "badge-red",
    }

    #: Statuses a date-driven refresh may move BETWEEN. ``compliant`` / ``non_compliant`` /
    #: ``not_applicable`` / ``retired`` are human decisions and are never walked back by a clock —
    #: the ``SupplierContract.AUTO_STATUSES`` posture.
    AUTO_STATUSES = ("applicable", "in_progress", "overdue")

    #: The "still owes us something" set. Declared once so the list filter, the header chips and the
    #: seeder guard read the same tuple — 4.10 shipped a bench filter that encoded two of three
    #: shapes and the count on the page disagreed with the rows under it.
    OPEN_STATUSES = ("applicable", "in_progress", "non_compliant", "overdue")

    # --- what the obligation IS -------------------------------------------------------------------
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    source = models.CharField(
        max_length=20, choices=SOURCE_CHOICES, default="regulation",
        help_text="What creates the duty — a regulation, a signed contract, a licence proviso, a "
                  "certification scheme, a customer's terms, or our own policy")
    source_reference = models.CharField(
        max_length=500, blank=True,
        help_text="Citation or URL — 21 CFR 117, REACH Annex XVII, the clause number")
    framework = models.CharField(
        max_length=24, choices=FRAMEWORK_CHOICES, default="other",
        help_text="The regime this obligation belongs to — what the compliance report groups by")
    obligation_category = models.CharField(
        max_length=16, choices=OBLIGATION_CATEGORY_CHOICES, blank=True,
        help_text="For a contract obligation: which kind of clause it came out of")
    jurisdiction = models.CharField(
        max_length=120, blank=True,
        help_text="Where it applies — EU, California, GCC, the issuing authority's territory")

    # --- what it applies to -----------------------------------------------------------------------
    # Five TYPED nullable pointers, not one generic scope_ref integer. A bare int carries neither a
    # tenant nor a type: it would happily survive pointing at a deleted or cross-tenant row and the
    # page would silently narrow to the wrong subject. With a real FK, clean() can check the tenant
    # and the database can SET_NULL the pointer when the subject goes away.
    scope = models.CharField(
        max_length=10, choices=SCOPE_CHOICES, default="tenant",
        help_text="Whether this binds the whole workspace or one org unit / supplier / site / item")
    org_unit = models.ForeignKey(
        "core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="scm_compliance_requirements", help_text="Only when the scope is 'Org unit'")
    party = models.ForeignKey(
        "core.Party", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="scm_compliance_requirements", help_text="Only when the scope is 'Supplier'")
    location = models.ForeignKey(
        "scm.Location", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="compliance_requirements", help_text="Only when the scope is 'Location'")
    item = models.ForeignKey(
        "scm.Item", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="compliance_requirements", help_text="Only when the scope is 'Item'")

    # --- who owns it, and how often it must be re-proved ------------------------------------------
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="scm_compliance_requirements_owned",
        help_text="The person answerable for keeping this proven")
    frequency = models.CharField(
        max_length=12, choices=FREQUENCY_CHOICES, default="annual",
        help_text="How often proof is owed. A pass advances the due date by this much")
    next_due_date = models.DateField(
        null=True, blank=True, help_text="When the next proof is owed")
    # Capped like every other day-count column in this app: PositiveIntegerField accepts up to
    # 4294967295 on MySQL/MariaDB, and this number is compared against a date, where an absurd value
    # is an uncaught OverflowError — a 500, not a validation error (the 4.10 DoS finding).
    notice_days = models.PositiveIntegerField(
        default=30, validators=[MinValueValidator(0), MaxValueValidator(3650)],
        help_text="Start warning this many days before the due date — the staged 90/60/30 reminder "
                  "pattern permit and certificate-of-insurance trackers use")
    # System stamp (L22): written only by record_check(), never offered on a form. This is a record
    # of an EVENT, not a derivation — which is why it is a column while compliance_rate is not.
    last_checked_on = models.DateField(null=True, blank=True, editable=False)

    # --- where it comes from (link-outs, never a second copy of the source record) -----------------
    # SET_NULL, emphatically not CASCADE: deleting the agreement must not destroy the proof history
    # of an obligation that was met. It also keeps the 4.2 extension behaviour-neutral — 4.2's
    # contract_delete needs no change and cannot start deleting 4.12 rows as a side effect.
    contract = models.ForeignKey(
        "scm.SupplierContract", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="compliance_requirements",
        help_text="The 4.2 agreement this obligation comes out of")
    license = models.ForeignKey(
        "scm.TradeLicense", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="compliance_requirements",
        help_text="Licence proviso/condition needing periodic proof")
    # core.Document, not a FileField — Module 13 (DMS) owns file storage and 4.12 must not grow a
    # second one. Same attachment 4.2's SupplierContract.document uses.
    document = models.ForeignKey(
        "core.Document", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="scm_compliance_requirements",
        help_text="The standing policy / certificate / clause extract this obligation rests on")

    # --- where it stands --------------------------------------------------------------------------
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="applicable")
    criticality = models.CharField(max_length=8, choices=CRITICALITY_CHOICES, default="medium")
    # A non-applicable row is KEPT with a reason rather than deleted: "we considered this and it does
    # not bind us, here is why" is itself an auditable answer. Deleting it leaves no answer at all.
    not_applicable_reason = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        # Soonest due first. NULL due dates sort first on MySQL/MariaDB, which is what we want on a
        # "what do I owe" queue: an obligation with no date at all is unscheduled and needs a human
        # more than a dated one does. Note that "-criticality" orders the STORED token descending
        # (medium > low > high > critical lexically), not by severity — anything that needs true
        # severity order sorts in Python against CRITICALITY_CHOICES.
        ordering = ["next_due_date", "-criticality", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="scm_cr_tnt_status_idx"),
            # The list's due/overdue/due-soon filters and both header chips all range-scan this one.
            models.Index(fields=["tenant", "next_due_date"], name="scm_cr_tnt_due_idx"),
            models.Index(fields=["tenant", "framework"], name="scm_cr_tnt_frame_idx"),
            models.Index(fields=["tenant", "source"], name="scm_cr_tnt_src_idx"),
        ]

    def __str__(self):
        return f"{self.number or 'CR'} · {self.title}"

    # ---------------------------------------------------------------------------------------------
    # Validation.
    # ---------------------------------------------------------------------------------------------
    def clean(self):
        super().clean()

        # (a) Exactly the pointer that matches `scope` is set, and every other one is blank. A scope
        #     switched from Supplier to Location that leaves the old party pointer behind is a stale
        #     filter quietly narrowing somebody else's register months later.
        required_field = _SCOPE_FIELDS.get(self.scope)
        for field in _SCOPE_FK_FIELDS:
            is_set = getattr(self, f"{field}_id", None) is not None
            if field == required_field and not is_set:
                raise ValidationError(
                    {field: f"A '{self.get_scope_display()}' requirement has to say which one."})
            if field != required_field and is_set:
                raise ValidationError(
                    {field: f"This requirement's scope is '{self.get_scope_display()}', so this "
                            "pointer would never be read — clear it."})

        # (b) THE GUARD. Every set FK must belong to this requirement's own tenant. The forms scope
        #     their querysets, but that is UX: a narrowed dropdown has never held against a crafted
        #     POST. Skipped when the instance has no tenant yet — an unsaved model built in a shell
        #     has tenant_id None and `self.tenant` would raise RelatedObjectDoesNotExist on a
        #     non-nullable FK rather than return None.
        if self.tenant_id is not None:
            for field in _TENANT_SCOPED_FK_FIELDS:
                if getattr(self, f"{field}_id", None) is None:
                    continue
                # Defaulted getattr: RelatedObjectDoesNotExist subclasses AttributeError, so a
                # pointer whose row went away degrades to None here instead of 500-ing inside
                # validation. scope_label reports the same None and says "(removed)" on the page.
                related = getattr(self, field, None)
                if related is not None and related.tenant_id != self.tenant_id:
                    raise ValidationError({field: "That record belongs to another workspace."})

        # (c) A link-out that links nowhere. Saying the duty comes out of a contract and then not
        #     naming the contract is the same empty claim as an alert with no threshold (L39).
        if self.source == "contract" and self.contract_id is None:
            raise ValidationError(
                {"contract": "A contract obligation has to name the contract it came out of."})
        if self.source == "license" and self.license_id is None:
            raise ValidationError(
                {"license": "A licence obligation has to name the licence it came out of."})

        # (d) A SCHEDULED obligation with no first due date can never surface on the queue that is
        #     the entire point of this register — it would sit invisible until an auditor found it.
        #     one_time and on_event are excluded because neither HAS a schedule: record_check()
        #     clears the due date on both, so requiring one here would make a passed on_event row
        #     un-editable by its own form.
        if self.frequency in _FREQUENCY_MONTHS and not self.next_due_date:
            raise ValidationError(
                {"next_due_date": f"A '{self.get_frequency_display()}' obligation needs a first "
                                  "due date, or it will never appear on the due queue."})

        # (e) "Not applicable" is an assertion, and an unexplained assertion is not auditable.
        if self.status == "not_applicable" and not self.not_applicable_reason.strip():
            raise ValidationError(
                {"not_applicable_reason": "Say why this does not apply — a non-applicable row is "
                                          "kept for the reason, not for the row."})

    # ---------------------------------------------------------------------------------------------
    # Behaviour — the projection idiom (SupplierContract.refresh_status /
    # Shipment.apply_tracking_event): one method owns each transition, and it writes exactly the
    # columns it changed.
    # ---------------------------------------------------------------------------------------------
    def refresh_status(self, today=None, save=True):
        """Move applicable ↔ in_progress ↔ overdue from the due date alone.

        Never touches a ``compliant`` / ``non_compliant`` / ``not_applicable`` / ``retired`` row:
        those are human decisions and a clock must not overwrite them. ``in_progress`` is likewise
        preserved while the date is still in the future — it means "somebody is working on it",
        which no date can tell you — but it DOES go overdue when the date passes.

        ``save=False`` lets a list view collect the crossed rows and write them in one
        ``bulk_update`` instead of one ``save()`` per row on an unpaginated scan.
        """
        if self.status not in self.AUTO_STATUSES:
            return
        today = today or timezone.localdate()
        if self.next_due_date and self.next_due_date < today:
            new = "overdue"
        elif self.status == "overdue":
            # The date moved out (rescheduled, or cleared) — fall back to the neutral open state
            # rather than guessing that work is under way.
            new = "applicable"
        else:
            new = self.status
        if new != self.status:
            self.status = new
            if save:
                self.save(update_fields=["status", "updated_at"])

    def record_check(self, check):
        """Fold a just-appended :class:`ComplianceCheck` into this requirement's standing.

        * ``fail``    → ``non_compliant``. The due date is deliberately left alone: the cycle was
          not satisfied, so it is still owed.
        * ``partial`` → ``in_progress``, same reasoning.
        * ``pass``    → ``compliant``, stamps ``last_checked_on`` and advances ``next_due_date`` by
          one ``frequency`` step (``one_time`` / ``on_event`` advance to ``None`` — neither has a
          next cycle).
        * ``not_applicable`` → nothing. It is evidence of neither compliance nor breach, it is
          excluded from :attr:`compliance_rate`, and it must not stamp ``last_checked_on`` — that
          would claim proof that was never obtained.

        The advance is anchored on the cycle the check ANSWERS (``check.due_date``), not on the day
        it happened, so a proof done three weeks late does not drag the whole schedule three weeks
        later. It advances exactly ONE cycle even when several were missed: skipping the gap would
        erase the fact that cycles were missed, and ``refresh_status`` will correctly re-flag the
        row as overdue on the next roll.

        One ``save``, listing only the columns actually written (``updated_at`` included because
        ``auto_now`` is skipped otherwise).
        """
        fields = []
        result = getattr(check, "result", None)

        if result == "fail":
            self.status = "non_compliant"
            fields.append("status")
        elif result == "partial":
            self.status = "in_progress"
            fields.append("status")
        elif result == "pass":
            anchor = (check.due_date or self.next_due_date or check.performed_on
                      or timezone.localdate())
            self.status = "compliant"
            self.last_checked_on = check.performed_on or timezone.localdate()
            self.next_due_date = self.advance_due_date(anchor)
            fields += ["status", "last_checked_on", "next_due_date"]
        else:
            return

        self.save(update_fields=fields + ["updated_at"])

    def advance_due_date(self, anchor):
        """``anchor`` plus one ``frequency`` step, or ``None`` for a cadence with no next cycle."""
        months = _FREQUENCY_MONTHS.get(self.frequency)
        if months is None:
            return None
        return _add_months(anchor, months)

    # ---------------------------------------------------------------------------------------------
    # Derived — NOTHING below is stored. Every one of these goes stale the moment a check or a date
    # changes, which is precisely why none of them is a column.
    # ---------------------------------------------------------------------------------------------
    @property
    def days_to_due(self):
        """Days until the next proof is owed; negative once past. ``None`` when nothing is due."""
        if not self.next_due_date:
            return None
        return (self.next_due_date - timezone.localdate()).days

    @property
    def is_overdue(self):
        days = self.days_to_due
        return days is not None and days < 0

    @property
    def is_due_soon(self):
        """Inside the notice window and not yet past it — what the amber chip counts."""
        days = self.days_to_due
        return days is not None and 0 <= days <= self.notice_days

    @property
    def compliance_rate(self):
        """Passed checks as a percentage (0–100) of the checks that COUNT, or ``None``.

        ``not_applicable`` checks are excluded from both halves: a cycle that did not apply is not
        a pass and not a failure, and counting it either way misstates the record.

        ``None`` — never ``0`` — when there is nothing to divide by. A requirement that has never
        been checked renders "—", not a confident 0% that reads as *failing* when the truth is
        *unknown*. One aggregate query, computed on read so it can never be stale.
        """
        if self.pk is None:
            return None
        counts = self.checks.aggregate(
            considered=Count("pk", filter=~Q(result="not_applicable")),
            passed=Count("pk", filter=Q(result="pass")),
        )
        considered = counts["considered"] or 0
        if not considered:
            return None
        return q2(Decimal(counts["passed"] or 0) * Decimal("100") / Decimal(considered))

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.status, "badge-muted")

    @property
    def criticality_css(self):
        return self.CRITICALITY_CSS.get(self.criticality, "badge-muted")

    def resolved_scope(self):
        """``(scope value, the object it narrows to or None)``.

        ``None`` with a scope of ``tenant`` means the whole workspace, which is the normal case.
        ``None`` with any OTHER scope means the subject was **deleted** — the pointers are
        ``SET_NULL``. Callers MUST NOT read that as "no filter": an obligation that bound one site
        would silently start reading as binding everything.
        """
        field = _SCOPE_FIELDS.get(self.scope)
        if not field:
            return self.scope, None
        return self.scope, getattr(self, field, None)

    @property
    def scope_label(self):
        """One line of display text — ``"Supplier: Acme Ltd"``, ``"Whole workspace"``, or
        ``"Location (removed)"`` when a ``SET_NULL`` pointer emptied out. The "(removed)" case is
        the point: a scoped row whose subject vanished must not read as workspace-wide."""
        scope, subject = self.resolved_scope()
        if _SCOPE_FIELDS.get(scope) is None:
            return self.get_scope_display()
        if subject is None:
            return f"{self.get_scope_display()} (removed)"
        return f"{self.get_scope_display()}: {subject}"


class ComplianceCheck(models.Model):
    """One performed proof cycle against a requirement — the defensible audit trail.

    Tenant-less child, reached only through ``requirement.tenant`` (the ``TrackingEvent`` /
    ``InspectionResult`` precedent): it is never listed or filtered on its own, so it carries no
    ``tenant`` column and no ``number``. Views MUST resolve it as
    ``get_object_or_404(ComplianceCheck, pk=pk, requirement__tenant=request.tenant)`` — a bare
    ``pk`` lookup is a cross-tenant read.
    """

    RESULT_CHOICES = [
        ("pass", "Pass"),
        ("fail", "Fail"),
        ("partial", "Partial"),
        ("not_applicable", "Not Applicable"),
    ]
    RESULT_CSS = {
        "pass": "badge-green",
        "fail": "badge-red",
        "partial": "badge-amber",
        "not_applicable": "badge-muted",
    }

    requirement = models.ForeignKey(
        "scm.ComplianceRequirement", on_delete=models.CASCADE, related_name="checks")
    result = models.CharField(max_length=14, choices=RESULT_CHOICES, default="pass")
    # Snapshotted from the parent's next_due_date when the check is created, so re-scheduling the
    # requirement later never rewrites what a PAST cycle was due. Nullable because an on_event or
    # ad-hoc check answers no scheduled cycle.
    due_date = models.DateField(
        null=True, blank=True, help_text="The cycle this check answers, as it stood at the time")
    performed_on = models.DateField(default=timezone.localdate)
    # Stamped from request.user, never typed — "who did it" is an audit fact, not an input (the
    # ReturnDisposition.received_by / SupplierRiskAssessment.assessed_by posture, L22).
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, editable=False,
        related_name="scm_compliance_checks_performed")
    finding = models.TextField(blank=True)
    # Free text, NOT an FK to 4.9's NonConformance — see the module docstring for why a shipped
    # sub-module is not being refactored for a convenience link this pass.
    corrective_reference = models.CharField(
        max_length=120, blank=True,
        help_text="The 4.9 NCR/CAPA number this failure was escalated to — link out by reference")
    evidence = models.ForeignKey(
        "core.Document", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="scm_compliance_checks",
        help_text="The certificate, report or signed record that proves this cycle")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-performed_on", "-id"]
        indexes = [
            models.Index(fields=["requirement", "due_date"], name="scm_cchk_req_due_idx"),
            models.Index(fields=["requirement", "result"], name="scm_cchk_result_idx"),
        ]

    def __str__(self):
        when = self.performed_on.isoformat() if self.performed_on else "unscheduled"
        return f"{self.get_result_display()} · {when}"

    def clean(self):
        super().clean()

        # A proof cycle cannot be recorded before it happened. Post-dating a check would let an
        # unperformed inspection mark a requirement compliant today.
        if self.performed_on and self.performed_on > timezone.localdate():
            raise ValidationError(
                {"performed_on": "A check cannot be dated in the future — record it once it has "
                                 "actually been performed."})

        # This model has no tenant column, so TenantModelForm cannot scope the evidence dropdown for
        # it and the ordinary tenant guard does not apply automatically. Check it against the
        # PARENT's tenant here: without this, a crafted POST could attach another workspace's
        # document and the detail page would render its name and link back.
        requirement = getattr(self, "requirement", None) if self.requirement_id else None
        if requirement is not None and self.evidence_id is not None:
            # Defaulted getattr — a SET_NULL target that went away degrades to None rather than
            # raising RelatedObjectDoesNotExist inside validation.
            evidence = getattr(self, "evidence", None)
            if evidence is not None and evidence.tenant_id != requirement.tenant_id:
                raise ValidationError({"evidence": "That document belongs to another workspace."})

    @property
    def result_css(self):
        """Django templates cannot subscript a dict by a variable, so the lookup lives here."""
        return self.RESULT_CSS.get(self.result, "badge-muted")
