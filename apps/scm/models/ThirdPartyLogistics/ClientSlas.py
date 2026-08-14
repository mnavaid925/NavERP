"""SCM 4.17 Third-Party Logistics (3PL) — ``ClientSLA``: what we promised, measured from the ledger.

A **client SLA** is one service promise made to one :class:`~apps.scm.models.LogisticsClient` — "98% of
your shipments leave on time", "24 hours dock to stock", "damage under half a percent" — together with
the evidence of whether we are keeping it. :meth:`ClientSLA.recompute` goes and looks: it resolves the
measurement window, walks the as-built rows for that metric, and writes back a measured value, a
sample size, a plain-English summary of what it counted and a status.

**BACKEND PACKAGE ``ThirdPartyLogistics/`` vs TEMPLATE FOLDER ``templates/scm/3pl/`` — the asymmetry
is the house rule, not a defect.** All sixteen shipped scm template folders use a short slug while the
Python package uses the NavERP sub-module title in PascalCase (``CustomerPortal/`` ↔
``templates/scm/portal/``, ``ContractCompliance/`` ↔ ``templates/scm/compliance/``). Do not "fix"
``3pl/`` into ``thirdpartylogistics/``; ``CustomerPortal/PortalAccounts.py:45-47`` carries the same
note, and so does ``SKILL.md``.

--------------------------------------------------------------------------------------------------
THE FIVE DECISIONS A READER SHOULD NOT HAVE TO REDISCOVER
--------------------------------------------------------------------------------------------------

**1. ``no_data`` IS A FIRST-CLASS ANSWER AND IS NEVER WRITTEN AS ZERO.** This is the whole discipline
of the module. If there were no shipments in the window, :meth:`recompute` sets ``status="no_data"``,
**leaves ``last_measured_value`` untouched** and writes the REASON into ``measurement_summary``. It
never writes a confident 0 and never merges "we have no signal" into "we are meeting the target" —
those are different statements, and collapsing them reports a green SLA for a warehouse that did
nothing (``_choices.SLA_STATUS_CHOICES`` says the same from the vocabulary side). A 0 on a
``lower_is_better`` metric would additionally read as *perfect*, which is the worst possible direction
for that lie to point.

**2. The metric registry is CLOSED and its ``unit`` / ``direction`` are VALIDATED, not suggested.**
``SLA_METRIC_META`` is the single source of truth for what each metric is measured in and which way is
good; :meth:`clean` refuses a percentage metric saved with ``hours``, because such a row would compare
98 against 24 and breach forever. The same registry's ``source`` string is what the detail page prints
so a client can audit the number — an SLA figure with no statement of what it was computed from is a
figure nobody can argue with, and that is the first thing a client asks.

**3. Every evidence column is ``editable=False``.** ``last_measured_value``, ``last_measured_at``,
``measurement_window_start`` / ``_end``, ``measurement_summary``, ``sample_size``, ``breach_count`` and
``status`` are written by :meth:`recompute` and by nothing else — the ``ClientBillingRun.status``
posture. A measured figure a user can retype is not a measurement, and a ``DateInput`` over a system
``*_at`` silently truncates its time (L22). ``ClientSLAForm`` names all eight in its exclusion note so
nobody re-adds them.

**4. ``__date`` LOOKUPS ARE BANNED IN THIS MODULE**, exactly as in ``ClientBillingRuns.py``. Every
datetime column (``Shipment.actual_pickup_at``, ``CycleCountTask.counted_at``,
``PutawayTask.completed_at``, ``StockMove.moved_at``) is filtered with an explicit **aware datetime
range**: ``__date`` compiles to ``CONVERT_TZ`` on MariaDB and returns NULL when the timezone tables are
not loaded, which on XAMPP they are not (the 4.12 carbon-report finding). The date/datetime
COMPARISONS the metrics need (was the actual pickup on or before the planned date?) are then done in
**Python**, over a bounded row fetch, rather than in SQL for the same reason.

**5. Nothing here posts to the ledger and nothing here raises a credit note (L29).**
:meth:`suggested_service_credit` returns a SUGGESTION. 4.17 deliberately does not auto-draft an
``Invoice(kind="credit_note")`` for a breach — the page that renders it is labelled *SUGGESTED — NOT
APPLIED*, and applying it is a decision a human makes in ``apps/accounting``.

--------------------------------------------------------------------------------------------------
KNOWN LIMITATION — THE NULL-SCOPE DUPLICATE, HANDLED RATHER THAN IGNORED
--------------------------------------------------------------------------------------------------
``unique_together`` includes ``("tenant", "client", "metric", "scope_location")``, and **MySQL /
MariaDB treat NULLs as DISTINCT in a unique index**, so that tuple does *not* stop two rows with
``scope_location IS NULL`` — which is the common case, since most SLAs are workspace-wide. Django's own
``Model.validate_unique`` skips the check entirely when any member of the tuple is ``None``
(``_perform_unique_checks`` `continue`s on a NULL lookup value), so neither boundary catches it for
free. :meth:`clean` therefore refuses that duplicate EXPLICITLY.

**Do not "fix" the index.** A ``UniqueConstraint(condition=Q(scope_location__isnull=True))`` is the
4.15 precedent and is the right shape on PostgreSQL, but MariaDB has no partial indexes, so it would
migrate to nothing and read as protection that is not there. The explicit ``clean()`` guard is the
protection; this paragraph is why.
"""
import datetime

from apps.scm.models._base import *  # noqa: F401,F403
# BY NAME, never `import *` — the 4.17 vocabulary module is owned by the `LogisticsClients` entity
# file (see its docstring) and is imported here the same way `ClientRateCards.py` and
# `ClientBillingRuns.py` import it. It imports nothing itself, not even `_base`, so no cycle exists.
from apps.scm.models.ThirdPartyLogistics._choices import (
    MAX_MEASUREMENT_ROWS,
    SLA_DIRECTION_CHOICES,
    SLA_METRIC_CHOICES,
    SLA_METRIC_META,
    SLA_STATUS_CHOICES,
    SLA_STATUS_CSS,
    SLA_UNIT_CHOICES,
    SLA_WINDOW_CHOICES,
)


#: The sales-order statuses that count as "in full" for OTIF. An order that was cancelled or is still
#: being picked was not delivered in full no matter how punctual its shipment was.
_IN_FULL_ORDER_STATUSES = ("fulfilled", "invoiced", "closed")

#: ``ReturnReason.fault_party`` value that means *we* got it wrong — the only fault attribution in the
#: app that distinguishes a picking error from a customer's change of mind, and therefore the only
#: honest basis for an order-accuracy figure. See :meth:`ClientSLA._measure_order_accuracy`.
_MERCHANT_FAULT = "merchant"


def _sla_day_start(day):
    """Midnight on ``day``, timezone-aware.

    A private copy rather than an import from ``ClientBillingRuns``: the two entity modules in this
    sub-package are deliberately independent of each other (only ``_choices`` is shared), and a
    two-line timezone helper is not the thing to open an import edge for. See ruling 4 in the module
    docstring for why every datetime filter here is an explicit aware range.
    """
    return timezone.make_aware(datetime.datetime.combine(day, datetime.time.min))


def _sla_day_end(day):
    """The last instant of ``day``, timezone-aware — the inclusive upper bound of a window."""
    return timezone.make_aware(datetime.datetime.combine(day, datetime.time.max))


class ClientSLA(TenantNumbered):
    """One measurable service promise to one 3PL client [SLA-], plus the evidence for it.

    ``client`` is CASCADE, unlike ``ClientRateCard.client`` / ``ClientBillingRun.client``, which are
    both PROTECT. That difference is deliberate and it is about what the row IS: a tariff and a
    billing run are financial EVIDENCE that must outlive the client record, while an SLA is a live
    promise — once there is no client there is no promise, and a target with nobody to owe it to is
    noise on a list page. Nothing downstream references an SLA, so nothing is orphaned by the cascade.
    """

    NUMBER_PREFIX = "SLA"

    #: Read by BOTH boundaries — :meth:`clean` here and ``ClientSLAForm.clean``'s ``_reject_foreign``
    #: call — so a pointer added later is covered at the form the moment it is named here.
    TENANT_SCOPED_FKS = ("client", "scope_location")

    STATUS_CHOICES = SLA_STATUS_CHOICES
    STATUS_CSS = SLA_STATUS_CSS
    METRIC_META = SLA_METRIC_META

    #: metric -> the name of the method that measures it. A NAME table rather than a dict of bound
    #: methods so it can live at class scope, and a plain ``getattr`` so a metric added to the
    #: vocabulary without a resolver falls through to the honest ``no_data`` path in
    #: :meth:`recompute` instead of raising ``KeyError`` at the one moment somebody presses a button.
    RESOLVERS = {
        "on_time_shipment_pct": "_measure_on_time_shipment",
        "otif_pct": "_measure_otif",
        "same_day_ship_pct": "_measure_same_day_ship",
        "order_accuracy_pct": "_measure_order_accuracy",
        "inventory_accuracy_pct": "_measure_inventory_accuracy",
        "dock_to_stock_hours": "_measure_dock_to_stock",
        "order_cycle_time_hours": "_measure_order_cycle_time",
        "damage_rate_pct": "_measure_damage_rate",
        "shrinkage_pct": "_measure_shrinkage",
    }

    #: Metrics whose window is a shipment/order question rather than a stock-location one, so
    #: ``scope_location`` cannot narrow them. Named here rather than buried in each resolver, because
    #: the SUMMARY has to say that the scope was not applied — a narrowing a user set and the system
    #: silently ignored is worse than one it refuses.
    LOCATION_SCOPABLE_METRICS = ("inventory_accuracy_pct", "dock_to_stock_hours",
                                 "damage_rate_pct", "shrinkage_pct")

    client = models.ForeignKey("scm.LogisticsClient", on_delete=models.CASCADE, related_name="slas")
    metric = models.CharField(max_length=24, choices=SLA_METRIC_CHOICES,
                              help_text="What is measured. Each metric fixes its own unit and "
                                        "direction — see the help below the two fields.")
    name = models.CharField(max_length=120, blank=True,
                            help_text="What the contract calls this promise; blank uses the metric's "
                                      "own name")
    target_value = models.DecimalField(max_digits=10, decimal_places=2,
                                       validators=[MinValueValidator(ZERO)],
                                       help_text="The number that was agreed")
    unit = models.CharField(max_length=6, choices=SLA_UNIT_CHOICES, default="pct")
    direction = models.CharField(max_length=16, choices=SLA_DIRECTION_CHOICES,
                                 default="higher_is_better")
    warning_threshold = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="The at-risk band. It must sit on the failing side of the target — BELOW it when "
                  "higher is better, ABOVE it when lower is better — or it can never fire.")
    measurement_window = models.CharField(max_length=12, choices=SLA_WINDOW_CHOICES, default="monthly")
    scope_location = models.ForeignKey(
        "scm.Location", on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
        help_text="Narrow this promise to one site or zone; blank measures the whole workspace. Only "
                  "the stock-based metrics can be narrowed this way — a shipment metric ignores it "
                  "and says so in its summary.")
    service_credit_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        validators=[MinValueValidator(ZERO), MaxValueValidator(Decimal("100"))],
        help_text="Percentage of the period's fees suggested as a credit on a breach. SUGGESTED "
                  "only — 4.17 raises no credit note.")
    service_credit_cap_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        validators=[MinValueValidator(ZERO), MaxValueValidator(Decimal("100"))],
        help_text="Ceiling on that percentage; 0 means no ceiling")
    is_active = models.BooleanField(
        default=True, help_text="A paused promise is not measured by the sweep and cannot be "
                                "recomputed — deactivate rather than delete to keep its history")
    notes = models.TextField(blank=True)

    # ---------------------------------------------------------------------------------------------
    # EVIDENCE. Every one of these is written by recompute() and by nothing else (ruling 3).
    # ---------------------------------------------------------------------------------------------
    last_measured_value = models.DecimalField(
        max_digits=14, decimal_places=4, null=True, blank=True, editable=False,
        help_text="NULL means never measured — render it as 'Not measured', never as 0")
    last_measured_at = models.DateTimeField(null=True, blank=True, editable=False)
    measurement_window_start = models.DateField(null=True, blank=True, editable=False)
    measurement_window_end = models.DateField(null=True, blank=True, editable=False)
    measurement_summary = models.CharField(
        max_length=255, blank=True, editable=False,
        help_text="What was counted, in words — or WHY nothing could be")
    sample_size = models.PositiveIntegerField(default=0, editable=False)
    breach_count = models.PositiveIntegerField(
        default=0, editable=False,
        help_text="Windows this promise has been breached in; a re-run over the same window cannot "
                  "count twice")
    status = models.CharField(max_length=10, choices=SLA_STATUS_CHOICES, default="no_data",
                              editable=False)

    class Meta:
        # Grouped by client, then by metric, so one client's promises read as a block.
        ordering = ["client__code", "metric", "id"]
        unique_together = (("tenant", "number"),
                           ("tenant", "client", "metric", "scope_location"))
        indexes = [
            # The client detail panel's "this client's SLAs, breaches first" and the ?client=+?status=
            # pair on the list page both narrow on (tenant, client) before status.
            models.Index(fields=["tenant", "client", "status"], name="scm_sla_tnt_cli_st_idx"),
            # The list page's ?status= filter, the four status stat tiles and
            # `LogisticsClient.open_sla_breaches()`.
            models.Index(fields=["tenant", "status"], name="scm_sla_tnt_status_idx"),
        ]

    def __str__(self):
        # Guarded: `write_audit_log` calls str() on instances whose parent may not be loaded, and an
        # unsaved/unparented SLA must render rather than raise.
        code = self.client.code if self.client_id else "—"
        return f"{self.number or 'SLA'} · {code} {self.get_metric_display()}"

    # =============================================================================================
    # Derived reads — none of these is a column
    # =============================================================================================
    @property
    def metric_meta(self):
        """This metric's registry entry: ``label`` / ``unit`` / ``direction`` / ``default_target`` /
        ``source``. Empty dict for a metric with no entry, so a template never raises."""
        return SLA_METRIC_META.get(self.metric, {})

    @property
    def status_css(self):
        """The colour-named theme.css badge class for this status.

        COLOUR-NAMED ONLY (badge-green / -red / -amber / -info / -muted / -slate). A semantic
        ``badge-success`` / ``badge-danger`` does not exist in theme.css and renders UNSTYLED (L33).
        """
        return SLA_STATUS_CSS.get(self.status, "badge-muted")

    @property
    def is_measured(self):
        """Has a figure ever been derived? ``False`` must render as "Not measured", never as 0."""
        return self.last_measured_value is not None

    @property
    def is_breaching(self):
        return self.status == "breached"

    @property
    def variance(self):
        """Signed ``measured − target``, or ``None`` when nothing has been measured.

        Signed rather than absolute, and NOT flipped for a ``lower_is_better`` metric: the page reads
        it beside the direction, and a "helpfully" re-signed number is one a reader cannot check
        against the two figures printed either side of it.
        """
        if self.last_measured_value is None or self.target_value is None:
            return None
        return q4(self.last_measured_value - self.target_value)

    def resolve_window(self, as_of=None):
        """``(start_date, end_date, description)`` for this SLA's measurement window.

        ``monthly`` is the last FULL calendar month and ``quarterly`` the last full quarter — never a
        part-period, because a target measured over four days of a month is not the number anybody
        agreed to (``SLA_WINDOW_CHOICES`` says the same). The two rolling windows end on ``as_of``
        itself, which is what "rolling 30 days" means to the person reading it.
        """
        as_of = as_of or timezone.localdate()

        if self.measurement_window == "monthly":
            end = as_of.replace(day=1) - datetime.timedelta(days=1)
            return end.replace(day=1), end, "last full calendar month"

        if self.measurement_window == "quarterly":
            quarter_start_month = ((as_of.month - 1) // 3) * 3 + 1
            end = datetime.date(as_of.year, quarter_start_month, 1) - datetime.timedelta(days=1)
            start = datetime.date(end.year, ((end.month - 1) // 3) * 3 + 1, 1)
            return start, end, "last full quarter"

        days = 90 if self.measurement_window == "rolling_90" else 30
        return as_of - datetime.timedelta(days=days), as_of, f"rolling {days} days"

    def window_label(self, as_of=None):
        """The human window as one string, e.g. ``"01 Jul 2026 – 31 Jul 2026 (last full calendar
        month)"``.

        Reports the STORED window when there is one — that is the window the measured figure on the
        page actually refers to — and the window a recompute WOULD use when there is not, flagged as
        such. A page that printed the prospective window beside a figure measured over a different one
        would be quietly mislabelling evidence.
        """
        if self.measurement_window_start and self.measurement_window_end:
            start, end = self.measurement_window_start, self.measurement_window_end
            note = self.get_measurement_window_display().lower()
        else:
            start, end, note = self.resolve_window(as_of)
            note = f"{note} — not yet measured"
        return f"{start:%d %b %Y} – {end:%d %b %Y} ({note})"

    def suggested_service_credit(self, monthly_fees):
        """The credit a breach SUGGESTS against ``monthly_fees``. **A suggestion — never applied.**

        ``ZERO`` unless the SLA is currently ``breached``: an at-risk or meeting promise owes nothing,
        and ``no_data`` owes nothing either, because a credit computed from an absence of evidence is
        the mirror image of ruling 1.

        **A ``service_credit_cap_pct`` of 0 means NO CAP, not a cap of nothing.** That is what
        ``clean()`` guard (e) encodes when it only compares the two percentages once the cap is above
        zero, and it is what the field's help text says. Reading a 0 cap literally — ``min(pct, 0)``
        — would silently zero every credit in the application while every page went on displaying a
        credit percentage, which is the most expensive possible way to be wrong here.
        """
        if self.status != "breached":
            return ZERO
        fees = Decimal(monthly_fees or ZERO)
        if fees <= ZERO:
            return ZERO
        pct = self.service_credit_pct or ZERO
        cap = self.service_credit_cap_pct or ZERO
        if cap > ZERO:
            pct = min(pct, cap)
        return q2(fees * pct / Decimal("100"))

    # =============================================================================================
    # Validation
    # =============================================================================================
    def clean(self):
        """Seven guards. Every error is keyed on a field ``ClientSLAForm`` actually carries.

        That is not a stylistic point: ``BaseModelForm._post_clean`` hands each key straight to
        ``Form.add_error``, which **raises ``ValueError`` for a key that is not a form field** — a 500
        instead of a rendered message.

        Every FK is read behind an ``_id`` test so an unsaved instance validates instead of raising
        ``RelatedObjectDoesNotExist`` out of the attribute access.
        """
        errors = {}
        meta = self.metric_meta

        # (a) cross-tenant client. Read first: several later rules read THROUGH this FK.
        if self.client_id and self.tenant_id:
            client = getattr(self, "client", None)
            if client is not None and client.tenant_id != self.tenant_id:
                errors["client"] = "That client belongs to another workspace."

        # (b) / (c) the registry decides the unit and the direction, and it is validated rather than
        # suggested. A percentage metric saved as `hours` would compare 98 against 24 and breach
        # forever; a `lower_is_better` metric saved the other way up would call the fastest warehouse
        # the failing one.
        if meta:
            if self.unit and self.unit != meta["unit"]:
                errors["unit"] = (
                    f"{meta['label']} is measured in {dict(SLA_UNIT_CHOICES).get(meta['unit'], meta['unit'])}, "
                    f"not {self.get_unit_display()}. The two are compared against the same target, so "
                    "a mismatch would make this promise unmeetable.")
            if self.direction and self.direction != meta["direction"]:
                errors["direction"] = (
                    f"{meta['label']} is read as "
                    f"'{dict(SLA_DIRECTION_CHOICES).get(meta['direction'], meta['direction'])}'. "
                    "Reading it the other way would score the best performance as the worst.")

        # (d) the warning band must sit on the FAILING side of the target or it can never fire — and
        # a threshold that never fires is worse than none, because the page implies there is an early
        # warning when there is not. Both numbers are named so the fix is obvious.
        if self.warning_threshold is not None and self.target_value is not None:
            if self.direction == "higher_is_better" and self.warning_threshold >= self.target_value:
                errors["warning_threshold"] = (
                    f"Higher is better here, so the at-risk band has to be BELOW the target: "
                    f"{self.warning_threshold} is not below {self.target_value}, so it could never "
                    "fire before the target was already missed.")
            elif self.direction == "lower_is_better" and self.warning_threshold <= self.target_value:
                errors["warning_threshold"] = (
                    f"Lower is better here, so the at-risk band has to be ABOVE the target: "
                    f"{self.warning_threshold} is not above {self.target_value}, so it could never "
                    "fire before the target was already missed.")

        # (e) a cap BELOW the credit percentage is a contradiction somebody typed; 0 means "no cap"
        # (see `suggested_service_credit`), so the comparison only runs above zero.
        cap = self.service_credit_cap_pct or ZERO
        pct = self.service_credit_pct or ZERO
        if cap > ZERO and cap < pct:
            errors["service_credit_cap_pct"] = (
                f"The cap ({cap}%) is lower than the credit percentage ({pct}%), so the credit could "
                "never reach the figure above it. Raise the cap, lower the percentage, or set the cap "
                "to 0 for no ceiling.")

        # (f) scope_location: cross-tenant, and cross-CLIENT — a location dedicated to somebody else
        # would measure this client's promise against another client's stock.
        location = getattr(self, "scope_location", None) if self.scope_location_id else None
        if location is not None:
            if self.tenant_id and location.tenant_id != self.tenant_id:
                errors["scope_location"] = "That location belongs to another workspace."
            elif (self.client_id
                  and getattr(location, "owner_client_id", None) not in (None, self.client_id)):
                errors["scope_location"] = (
                    f"{location.code} is dedicated to another client, so measuring this promise "
                    "against it would score this client on somebody else's stock.")

        # (f, second half) THE NULL-SCOPE DUPLICATE — see the module docstring. MySQL/MariaDB treat
        # NULLs as distinct in a unique index AND Django's own validate_unique skips a tuple
        # containing a NULL, so neither boundary catches this for free. Two workspace-wide SLAs on
        # one metric would both be recomputed and would contradict each other on the client page.
        if (self.tenant_id and self.client_id and self.metric
                and self.scope_location_id is None and "scope_location" not in errors):
            duplicate = type(self).objects.filter(
                tenant_id=self.tenant_id, client_id=self.client_id, metric=self.metric,
                scope_location__isnull=True)
            if self.pk:
                duplicate = duplicate.exclude(pk=self.pk)
            existing = duplicate.only("number").first()
            if existing is not None:
                errors["metric"] = (
                    f"{existing.number} already measures {self.get_metric_display()} for this client "
                    "across the whole workspace. Edit that one, or narrow this promise to a specific "
                    "location.")

        # (g) a percentage target above 100 can never be met, whichever way it is read. Same class of
        # mistake as (d) — a promise that is unmeetable by arithmetic rather than by performance.
        if self.unit == "pct":
            for field, value in (("target_value", self.target_value),
                                 ("warning_threshold", self.warning_threshold)):
                if value is not None and value > Decimal("100") and field not in errors:
                    errors[field] = f"This metric is a percentage, so {value} is out of range (0–100)."

        if errors:
            raise ValidationError(errors)

    # =============================================================================================
    # The measurement
    # =============================================================================================
    def recompute(self, as_of=None, save=True):
        """Measure this promise over its window and write back the evidence. Returns a summary dict.

        The three rules this method obeys, in the order they matter:

        1. **Never write 0 when there is no signal.** A resolver that finds nothing returns
           ``(None, 0, reason)``; the status becomes ``no_data``, ``last_measured_value`` and
           ``last_measured_at`` are LEFT ALONE, and the reason is written into
           ``measurement_summary``. Leaving the pair alone together keeps ``is_measured`` honest: a
           value with no timestamp, or a timestamp with no value, would be a half-fact the detail
           page could not render truthfully.
        2. **``no_data`` is distinct from ``meeting``** — different colour, different meaning, never
           merged.
        3. **``breach_count`` cannot double-count.** It increments only on a transition INTO
           ``breached`` for a window this row has not already been counted as breaching, so pressing
           Recompute five times over the same July cannot manufacture five breaches.

        The write is a narrow ``save(update_fields=…)``: a full ``save()`` would push back every
        in-memory column, including any a concurrent edit had just changed.
        """
        start, end, _note = self.resolve_window(as_of)

        handler = getattr(self, self.RESOLVERS.get(self.metric, ""), None)
        if handler is None:
            value, sample, summary = None, 0, (
                "no measurement is implemented for this metric in this release")
        else:
            value, sample, summary = handler(start, end)

        if (self.scope_location_id and self.metric not in self.LOCATION_SCOPABLE_METRICS):
            # SAID, not silently ignored: a narrowing the user set and the resolver could not honour
            # has to appear on the page beside the figure it did not narrow.
            summary = f"{summary} (location scope does not apply to this metric)"

        status = "no_data" if value is None else self._status_for(value)

        fields = ["status", "measurement_window_start", "measurement_window_end",
                  "measurement_summary", "sample_size", "updated_at"]

        # Rule 3, before `status` is overwritten: "already counted" is (same window AND already
        # breached), so a re-run is free while a genuine meeting -> breached move in the same window
        # still counts.
        already_counted = (self.status == "breached" and self.measurement_window_end == end)
        if status == "breached" and not already_counted:
            self.breach_count = (self.breach_count or 0) + 1
            fields.append("breach_count")

        self.status = status
        self.measurement_window_start = start
        self.measurement_window_end = end
        self.measurement_summary = (summary or "")[:255]
        self.sample_size = sample or 0

        if value is not None:
            self.last_measured_value = q4(value)
            self.last_measured_at = timezone.now()
            fields.extend(["last_measured_value", "last_measured_at"])

        if save and self.pk:
            self.save(update_fields=list(dict.fromkeys(fields)))

        return {"status": status, "value": value, "sample_size": self.sample_size,
                "summary": self.measurement_summary, "window": (start, end)}

    def _status_for(self, value):
        """``meeting`` / ``at_risk`` / ``breached`` for a measured ``value``.

        The comparison against the target is INCLUSIVE on both directions — a metric that lands
        exactly on 98.00 against a target of 98.00 is meeting it, which is what "98% on time" means to
        everybody who signed it. With no warning threshold there is no at-risk band at all, and the
        row goes straight from meeting to breached rather than inventing a margin nobody agreed.
        """
        target = self.target_value or ZERO
        warning = self.warning_threshold
        if self.direction == "lower_is_better":
            if value <= target:
                return "meeting"
            if warning is not None and value <= warning:
                return "at_risk"
            return "breached"
        if value >= target:
            return "meeting"
        if warning is not None and value >= warning:
            return "at_risk"
        return "breached"

    # ---------------------------------------------------------------------------------------------
    # Measurement plumbing
    # ---------------------------------------------------------------------------------------------
    @staticmethod
    def _bounded(qs):
        """``(rows, truncated)`` — at most :data:`MAX_MEASUREMENT_ROWS` rows, and whether the cap bit.

        The cap is a queryset SLICE so the DATABASE applies it: it bounds what is FETCHED, not merely
        what is walked. One extra row is taken so the truncation can be reported without a second
        COUNT — and it IS reported, in the summary, because a capped measurement presented as a total
        is a figure somebody would act on.
        """
        rows = list(qs[:MAX_MEASUREMENT_ROWS + 1])
        truncated = len(rows) > MAX_MEASUREMENT_ROWS
        del rows[MAX_MEASUREMENT_ROWS:]
        return rows, truncated

    @staticmethod
    def _cap_note(truncated):
        return (f" (capped at the first {MAX_MEASUREMENT_ROWS:,} rows)" if truncated else "")

    @staticmethod
    def _pct(part, whole):
        """``part / whole`` as a percentage, 4dp. ``whole`` of 0 never reaches here — the resolvers
        answer ``no_data`` first rather than dividing."""
        if not whole:
            return ZERO
        return q4(Decimal(part) * Decimal("100") / Decimal(whole))

    @staticmethod
    def _mean_hours(deltas):
        """The mean of a list of ``timedelta``s, in hours, 4dp.

        Each delta is FLOORED AT ZERO by the callers before it gets here. ``str()`` around the float
        seconds rather than ``Decimal(float)`` so the value carries its decimal repr instead of the
        binary artefact of the same number.
        """
        if not deltas:
            return ZERO
        total = sum((Decimal(str(delta.total_seconds())) for delta in deltas), ZERO)
        return q4(total / Decimal("3600") / Decimal(len(deltas)))

    def _client_shipments(self):
        """4.6 shipments carrying this client's stock.

        Attribution runs through ``sales_order → lines → item.owner_client`` — the same path
        ``ClientBillingRun._qty_shipments`` uses — because there is no client column on a shipment and
        there should not be one: ``item.owner_client`` is the single source of truth for whose goods
        these are (L37).
        """
        from apps.scm.models import Shipment
        return (Shipment.objects
                .filter(tenant_id=self.tenant_id,
                        sales_order__lines__item__owner_client=self.client_id)
                .distinct())

    # ---------------------------------------------------------------------------------------------
    # The nine resolvers. Each returns (value, sample_size, summary) or (None, 0, reason).
    #
    # Every one of them fetches an `id` as the FIRST column of its `values_list`. That is
    # load-bearing, not decoration: these querysets carry `.distinct()` (a shipment joins its order's
    # LINES to attribute the client, which multiplies rows), and DISTINCT applies to the SELECTED
    # columns — so a values_list of two timestamps would COLLAPSE two genuinely different shipments
    # that happened to share them, silently shrinking the denominator.
    # ---------------------------------------------------------------------------------------------
    def _measure_on_time_shipment(self, start, end):
        """Shipments picked up on or before their planned pickup date, over those picked up at all."""
        qs = (self._client_shipments()
              .filter(actual_pickup_at__gte=_sla_day_start(start),
                      actual_pickup_at__lte=_sla_day_end(end),
                      planned_pickup_date__isnull=False)
              .order_by("id")
              .values_list("id", "actual_pickup_at", "planned_pickup_date"))
        rows, truncated = self._bounded(qs)
        if not rows:
            return None, 0, ("no shipment for this client was picked up in the window, or none of "
                             "those picked up carried a planned pickup date to be judged against")
        on_time = sum(1 for _pk, actual, planned in rows if timezone.localdate(actual) <= planned)
        return (self._pct(on_time, len(rows)), len(rows),
                f"{on_time} of {len(rows)} shipments picked up on or before the planned date"
                + self._cap_note(truncated))

    def _measure_otif(self, start, end):
        """On time AND in full: delivered by the planned date, on an order that actually completed."""
        qs = (self._client_shipments()
              .filter(actual_delivery_at__gte=_sla_day_start(start),
                      actual_delivery_at__lte=_sla_day_end(end),
                      planned_delivery_date__isnull=False)
              .order_by("id")
              .values_list("id", "actual_delivery_at", "planned_delivery_date",
                           "sales_order__status"))
        rows, truncated = self._bounded(qs)
        if not rows:
            return None, 0, ("no shipment for this client was delivered in the window with a planned "
                             "delivery date to be judged against")
        good = sum(1 for _pk, actual, planned, order_status in rows
                   if timezone.localdate(actual) <= planned
                   and order_status in _IN_FULL_ORDER_STATUSES)
        return (self._pct(good, len(rows)), len(rows),
                f"{good} of {len(rows)} shipments delivered by the planned date on an order that "
                f"reached fulfilled, invoiced or closed" + self._cap_note(truncated))

    def _measure_same_day_ship(self, start, end):
        """Shipments that left on the same calendar day the order was taken."""
        qs = (self._client_shipments()
              .filter(actual_pickup_at__gte=_sla_day_start(start),
                      actual_pickup_at__lte=_sla_day_end(end),
                      sales_order__order_date__isnull=False)
              .order_by("id")
              .values_list("id", "actual_pickup_at", "sales_order__order_date"))
        rows, truncated = self._bounded(qs)
        if not rows:
            return None, 0, ("no shipment for this client was picked up in the window against an "
                             "order carrying an order date")
        same_day = sum(1 for _pk, actual, ordered in rows
                       if timezone.localdate(actual) == ordered)
        return (self._pct(same_day, len(rows)), len(rows),
                f"{same_day} of {len(rows)} shipments left on the day the order was taken"
                + self._cap_note(truncated))

    def _measure_order_accuracy(self, start, end):
        """Orders with no OUR-FAULT return raised against them, over all orders in the window.

        ``ReturnReason.fault_party`` is the only attribution in the app that separates a picking
        error from a customer's change of mind, so it is what the numerator turns on. **When the
        workspace has no ``merchant``-fault reason configured at all, this answers ``no_data`` rather
        than a confident 100%** — with nothing on file that could ever mark a return as our mistake,
        an absence of such returns is an absence of evidence, not evidence of accuracy. The registry's
        own ``source`` text promises exactly that.
        """
        from apps.scm.models import ReturnReason, SalesOrder

        has_fault_vocabulary = ReturnReason.objects.filter(
            tenant_id=self.tenant_id, fault_party=_MERCHANT_FAULT).exists()
        if not has_fault_vocabulary:
            return None, 0, ("no return reason in this workspace is attributed to us as the "
                             "merchant, so a picking error cannot be told apart from a customer's "
                             "change of mind — configure one before this promise can be measured")

        orders = (SalesOrder.objects
                  .filter(tenant_id=self.tenant_id,
                          order_date__gte=start, order_date__lte=end,
                          lines__item__owner_client=self.client_id)
                  .distinct())
        total = orders.count()
        if not total:
            return None, 0, "no order carrying this client's stock was placed in the window"

        errored = orders.filter(
            scm_return_authorizations__lines__reason__fault_party=_MERCHANT_FAULT).count()
        return (self._pct(total - errored, total), total,
                f"{total - errored} of {total} orders had no return raised against them on an "
                f"our-fault reason")

    def _measure_inventory_accuracy(self, start, end):
        """Cycle-count lines where the count matched the book, over all counted lines."""
        from apps.scm.models import CycleCountTaskLine

        # `counted_quantity__isnull=False` is the whole difference between "we counted it and it was
        # wrong" and "nobody has counted it yet": the column is nullable precisely so an unstarted
        # line can exist, and treating an uncounted line as a mismatch would score a warehouse for
        # work it has not done yet.
        qs = CycleCountTaskLine.objects.filter(
            cycle_count__tenant_id=self.tenant_id,
            cycle_count__counted_at__gte=_sla_day_start(start),
            cycle_count__counted_at__lte=_sla_day_end(end),
            item__owner_client=self.client_id,
            counted_quantity__isnull=False)
        if self.scope_location_id:
            qs = qs.filter(cycle_count__location_id=self.scope_location_id)

        rows, truncated = self._bounded(
            qs.order_by("id").values_list("id", "counted_quantity", "expected_quantity"))
        if not rows:
            return None, 0, ("no cycle-count line for this client's items was counted in the window "
                             "— an uncounted line cannot be right or wrong")
        matched = sum(1 for _pk, counted, expected in rows if counted == expected)
        return (self._pct(matched, len(rows)), len(rows),
                f"{matched} of {len(rows)} counted lines matched the book quantity"
                + self._cap_note(truncated))

    def _measure_dock_to_stock(self, start, end):
        """Mean hours from a goods receipt to the completion of its putaway.

        **The date/datetime asymmetry is stated rather than hidden**: ``GoodsReceiptNote.receipt_date``
        is a DateField, so it resolves to midnight, while ``PutawayTask.completed_at`` is a timestamp.
        The figure is therefore accurate to within a day, and the summary says so on every
        measurement. A putaway stamped BEFORE that midnight is a data fault (it cannot be put away
        before the day it arrived) and is floored at zero rather than allowed to subtract real hours
        from the mean.
        """
        from apps.scm.models import PutawayTask

        qs = PutawayTask.objects.filter(
            tenant_id=self.tenant_id,
            goods_receipt__isnull=False,
            item__owner_client=self.client_id,
            completed_at__gte=_sla_day_start(start),
            completed_at__lte=_sla_day_end(end))
        if self.scope_location_id:
            qs = qs.filter(to_location_id=self.scope_location_id)

        rows, truncated = self._bounded(
            qs.order_by("id").values_list("id", "completed_at", "goods_receipt__receipt_date"))
        if not rows:
            return None, 0, ("no putaway against a goods receipt was completed for this client's "
                             "items in the window")

        zero = datetime.timedelta(0)
        deltas = [max(zero, completed - _sla_day_start(received))
                  for _pk, completed, received in rows if received is not None]
        if not deltas:
            return None, 0, ("the putaways completed in the window carry no receipt date to measure "
                             "from")
        return (self._mean_hours(deltas), len(deltas),
                f"mean over {len(deltas)} putaways; the receipt date is a date (midnight) and the "
                f"putaway is a timestamp, so this is accurate to within a day"
                + self._cap_note(truncated))

    def _measure_order_cycle_time(self, start, end):
        """Mean hours from a sales order's order date to its shipment's actual pickup.

        Same stated asymmetry as dock-to-stock: ``SalesOrder.order_date`` is a DateField and resolves
        to midnight, so the figure is accurate to within a day. Negative spans (a pickup stamped
        before the order date) are floored at zero rather than credited against the mean.
        """
        qs = (self._client_shipments()
              .filter(actual_pickup_at__gte=_sla_day_start(start),
                      actual_pickup_at__lte=_sla_day_end(end),
                      sales_order__order_date__isnull=False)
              .order_by("id")
              .values_list("id", "actual_pickup_at", "sales_order__order_date"))
        rows, truncated = self._bounded(qs)
        if not rows:
            return None, 0, ("no shipment for this client was picked up in the window against an "
                             "order carrying an order date")
        zero = datetime.timedelta(0)
        deltas = [max(zero, picked - _sla_day_start(ordered)) for _pk, picked, ordered in rows]
        return (self._mean_hours(deltas), len(deltas),
                f"mean over {len(deltas)} shipments; the order date is a date (midnight), so this is "
                f"accurate to within a day" + self._cap_note(truncated))

    def _adjustment_base(self, start, end):
        """``(receipt_quantity, adjustment_queryset)`` for the two loss metrics — one shared window.

        The denominator is what was RECEIVED in the window, which is the only quantity in the ledger
        that both loss metrics can honestly be expressed against. Both are attributed through
        ``item.owner_client``; neither reads a column on ``StockMove``, because an owner column on an
        append-only ledger would be a second source of truth (L37).
        """
        from apps.scm.models import StockMove

        base = StockMove.objects.filter(
            tenant_id=self.tenant_id,
            item__owner_client=self.client_id,
            moved_at__gte=_sla_day_start(start),
            moved_at__lte=_sla_day_end(end))
        if self.scope_location_id:
            base = base.filter(location_id=self.scope_location_id)

        received = (base.filter(move_type="receipt", quantity__gt=0)
                    .aggregate(s=Sum("quantity"))["s"] or ZERO)
        return received, base.filter(move_type="adjustment")

    def _measure_damage_rate(self, start, end):
        """Negative adjustment movements over the quantity received in the same window."""
        received, adjustments = self._adjustment_base(start, end)
        if received <= ZERO:
            return None, 0, ("nothing was received for this client in the window, so there is no "
                             "base to express a loss rate against")
        negative = adjustments.filter(quantity__lt=0)
        lost = -(negative.aggregate(s=Sum("quantity"))["s"] or ZERO)
        sample = negative.count()
        return (self._pct(lost, received), sample,
                f"{lost} written off over {received} received on {sample} negative adjustment(s)")

    def _measure_shrinkage(self, start, end):
        """NET negative adjustment over the quantity received — unexplained loss, not recorded damage.

        Net rather than gross, which is the difference between this metric and the damage rate: a
        write-off offset by a found-stock adjustment in the same window is a counting error that
        resolved itself, not shrinkage. A net POSITIVE (more found than lost) is reported as 0, never
        as a negative shrinkage — "we gained stock" is not a service level.
        """
        received, adjustments = self._adjustment_base(start, end)
        if received <= ZERO:
            return None, 0, ("nothing was received for this client in the window, so there is no "
                             "base to express a shrinkage rate against")
        net = adjustments.aggregate(s=Sum("quantity"))["s"] or ZERO
        lost = max(ZERO, -net)
        sample = adjustments.count()
        return (self._pct(lost, received), sample,
                f"net {lost} lost over {received} received across {sample} adjustment(s)")
