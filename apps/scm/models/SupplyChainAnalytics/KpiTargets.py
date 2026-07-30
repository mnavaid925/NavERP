"""SCM 4.11 Supply Chain Analytics — ``KpiTarget`` [KPI-], the one row in 4.11 a human authors.

**Why this is STORED when the rest of 4.11 is derived.** Every figure on the five analytics pages is
computed live out of 4.1-4.10's transactional rows: turnover walks the append-only ``StockMove``
ledger, on-time delivery reads ``Shipment``, off-contract spend joins ``PurchaseOrder`` against
``SupplierContract``. A *target* is the only quantity in the sub-module with no source row anywhere.
Nothing in 4.1-4.10 says "our turnover goal is six turns", "warn me when dead stock passes 50 000",
"dead means ninety days without a movement" or "carrying cost runs at 22% a year" — those are
decisions a planner made, and there is nothing in the transactional record to derive them from. This
table is where that intent lives, together with who owns the number (``owner``), whether it earns a
tile on the control tower (``is_pinned`` / ``display_order``), and whether crossing it should raise a
``SupplyChainAlert`` (``is_alerting`` + the two thresholds).

**The Module 10 / 10.11 boundary — there is no formula language here.** 10.11 (``bi``) is where you
*author* a calculation: an expression over a semantic layer, for any domain. 4.11 does not rebuild
that and must not grow towards it. A target picks one key out of the CLOSED registry in
:mod:`apps.scm.models.SupplyChainAnalytics._choices` (``METRIC_META``) — hard-coded supply-chain
metrics whose SQL lives in ``apps/scm/analytics.py``. No expression field, no user-supplied SQL, no
aggregate builder, deliberately: a metric key is a promise that a *reviewed* resolver exists for it,
and that promise is what lets :meth:`KpiTarget.clean` validate a target against the metric's own
metadata (its legal scopes, its direction, the parameters it needs) instead of against whatever the
operator happened to type.

**Import direction is one-way.** The vocabularies below come from ``_choices`` — pure data, no
queries, no model imports — never from ``apps/scm/analytics.py``, which imports *this* package. See
``_choices``'s own docstring for why the split exists.

**4.11 is READ-ONLY over 4.1-4.10.** Nothing here, and nothing that reads it, writes a ``StockMove``
or a ``JournalEntry``.
"""
from apps.scm.models._base import *  # noqa: F401,F403
from apps.scm.models.SupplyChainAnalytics._choices import (
    DATE_RANGE_CHOICES,
    DIRECTION_CHOICES,
    METRIC_CHOICES,
    METRIC_META,
    PERIOD_GRAIN_CHOICES,
    SCOPE_CHOICES,
    SCOPE_FIELDS,
    SEVERITY_CHOICES,
)

#: The four typed scope FKs, derived from ``SCOPE_FIELDS`` rather than re-listed — adding a scope to
#: ``_choices`` must not require a matching edit here or the two drift apart silently.
_SCOPE_FK_FIELDS = tuple(field for field in SCOPE_FIELDS.values() if field)

#: Human words for the three band columns, used in ``clean()``'s error messages.
_BAND_LABELS = {
    "target_value": "target",
    "warning_threshold": "warning threshold",
    "critical_threshold": "critical threshold",
}

#: Last-resort direction when a metric key is unknown (``clean()`` rejects that case; ``save()``
#: still must not store a blank).
_FALLBACK_DIRECTION = "higher_is_better"


class KpiTarget(TenantNumbered):
    """A goal, its warning/critical bands and its knobs, for ONE registry metric [KPI-]."""

    NUMBER_PREFIX = "KPI"

    # --- what is being measured ------------------------------------------------------------------
    metric = models.CharField(
        max_length=40, choices=METRIC_CHOICES,
        help_text="One key from the closed supply-chain metric registry. Authoring your own formula "
                  "is Module 10's 10.11, not this")
    name = models.CharField(
        max_length=120,
        help_text="What this target is called on the tile — the metric's own label is generic, this "
                  "is the audience's words for it")

    # --- what it is measured over ----------------------------------------------------------------
    # Four TYPED nullable FKs, not one generic scope_ref integer. A bare int carries neither a tenant
    # nor a type, so it would happily point at a deleted or cross-tenant row and the page would
    # silently narrow to the wrong subject (L40 §3: same tenant is not the same subject — an untyped
    # int does not even give you the tenant). With a real FK, clean() can check the tenant and the DB
    # can SET_NULL the pointer when the subject goes away.
    scope = models.CharField(
        max_length=12, choices=SCOPE_CHOICES, default="all",
        help_text="Narrow the metric to one category / location / carrier / supplier, or leave it "
                  "across the whole network")
    scope_category = models.ForeignKey(
        "scm.ItemCategory", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="kpi_targets", help_text="Only when the scope is 'Item category'")
    scope_location = models.ForeignKey(
        "scm.Location", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="kpi_targets", help_text="Only when the scope is 'Location'")
    scope_carrier = models.ForeignKey(
        "scm.Carrier", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="kpi_targets", help_text="Only when the scope is 'Carrier'")
    scope_vendor = models.ForeignKey(
        "core.Party", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="scm_kpi_targets", help_text="Only when the scope is 'Supplier'")

    # --- over what window ------------------------------------------------------------------------
    period_grain = models.CharField(
        max_length=8, choices=PERIOD_GRAIN_CHOICES, default="month",
        help_text="The bucket one trend point covers")
    date_range = models.CharField(
        max_length=10, choices=DATE_RANGE_CHOICES, default="last_30",
        help_text="The rolling window the live figure is measured over")

    # --- which way good runs, and the bands ------------------------------------------------------
    direction = models.CharField(
        max_length=16, choices=DIRECTION_CHOICES, blank=True,
        help_text="Leave blank to inherit the metric's own direction. Set it only for a "
                  "deliberately inverted goal")
    target_value = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        help_text="The goal itself. Optional — a target row with no goal still snapshots and trends "
                  "its metric, it just cannot be banded")
    warning_threshold = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        help_text="Crossing this bands the value 'warning'")
    critical_threshold = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        help_text="Crossing this bands the value 'critical'")

    # --- the metric's own knobs ------------------------------------------------------------------
    # Capped, like every other days column in this app: PositiveIntegerField accepts up to
    # 4294967295 on MySQL/MariaDB and these numbers are fed to datetime.timedelta(days=...), where an
    # absurd value is an uncaught OverflowError — a 500, not a validation error.
    parameter_days = models.PositiveIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(3650)],
        help_text="The N in this metric's definition — dead-stock days, expiry window, "
                  "contract-expiry horizon, stale-tracking age")
    parameter_pct = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(ZERO), MaxValueValidator(Decimal("999.99"))],
        help_text="The percentage this metric's definition needs — annual carrying-cost rate, "
                  "demand-spike deviation band")

    # --- alerting --------------------------------------------------------------------------------
    is_alerting = models.BooleanField(
        default=False,
        help_text="Let the detector raise a SupplyChainAlert when this target's bands are crossed")
    min_impact_value = models.DecimalField(
        max_digits=14, decimal_places=2, default=ZERO, validators=[MinValueValidator(ZERO)],
        help_text="Alert-fatigue floor: a breach worth less than this raises nothing")
    severity = models.CharField(
        max_length=8, choices=SEVERITY_CHOICES, default="warning",
        help_text="Stamped on the alerts this target raises")

    # --- who cares, and where it shows -----------------------------------------------------------
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="scm_kpi_targets_owned",
        help_text="The person answerable for this number")
    is_pinned = models.BooleanField(
        default=False, help_text="Show as a tile on the analytics control tower")
    display_order = models.PositiveIntegerField(
        default=0, help_text="Tile order — lowest first")
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    # System stamp (L22): written by the snapshot/detect services, never by a form.
    last_evaluated_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["display_order", "name", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "metric"], name="scm_kpi_tnt_metric_idx"),
            models.Index(fields=["tenant", "is_active"], name="scm_kpi_tnt_active_idx"),
            # The detector's entry query is filter(tenant=…, is_active=True, is_alerting=True) — a
            # narrow slice of a table that is mostly display-only targets.
            models.Index(fields=["tenant", "is_alerting"], name="scm_kpi_tnt_alerting_idx"),
        ]

    def __str__(self):
        return f"{self.number or 'KPI'} · {self.name}"

    def save(self, *args, **kwargs):
        """Fill ``direction`` from the registry before handing off to ``TenantNumbered.save``.

        ``clean()`` does the same, but ``clean()`` is not on every path — the seeder, the detector
        and tests call ``.create()`` directly. Normalising here as well is what guarantees no stored
        row carries a blank direction, so every reader (the tile arrow, the band comparison, the
        alert detector) can read the column unconditionally.
        """
        self._inherit_registry_direction()
        return super().save(*args, **kwargs)

    def _inherit_registry_direction(self):
        if not self.direction:
            self.direction = (METRIC_META.get(self.metric) or {}).get(
                "direction", _FALLBACK_DIRECTION)

    # ---------------------------------------------------------------------------------------------
    # Validation — five registry-driven checks plus the alerting conjunction.
    #
    # All of it reads METRIC_META[self.metric] rather than branching per metric: a new metric is one
    # dict entry in _choices.py, and the rules below start applying to it without a line changing
    # here. An if-chain per metric would be ~36 branches that drift the moment a metric is added.
    # ---------------------------------------------------------------------------------------------
    def clean(self):
        super().clean()

        meta = METRIC_META.get(self.metric)
        if meta is None:
            if not self.metric:
                # clean_fields() already reported the blank; Model.full_clean() runs clean() anyway,
                # and nothing below is meaningful without a metric.
                return
            raise ValidationError(
                {"metric": f"'{self.metric}' is not a supply-chain metric this build can compute. "
                           "The metric set is closed — pick one from the list."})

        self._inherit_registry_direction()

        # (e) The metric must be able to MEAN anything at this scope. A carrier scope on a
        #     dead-stock metric is an empty conjunction (L39): the page would render 0 forever and
        #     look like good news.
        if self.scope not in meta["scopes"]:
            allowed = ", ".join(dict(SCOPE_CHOICES)[value] for value in meta["scopes"])
            raise ValidationError(
                {"scope": f"'{meta['label']}' cannot be narrowed that way — it is only computable "
                          f"at: {allowed}."})

        # (b) Exactly the FK that matches `scope` is set, and every other one is blank. A scope
        #     switched from Carrier to Location that leaves the old carrier pointer behind is a
        #     stale filter quietly narrowing somebody else's metric months later.
        required_field = SCOPE_FIELDS.get(self.scope)
        for field in _SCOPE_FK_FIELDS:
            is_set = getattr(self, f"{field}_id", None) is not None
            if field == required_field and not is_set:
                raise ValidationError(
                    {field: f"A '{self.get_scope_display()}' target has to say which one."})
            if field != required_field and is_set:
                raise ValidationError(
                    {field: f"This target's scope is '{self.get_scope_display()}', so this pointer "
                            "would never be read — clear it."})

        # (c) THE GUARD. Every set scope FK must belong to this target's own tenant. The form's
        #     querysets are tenant-scoped, but that is UX: a narrowed dropdown has never held
        #     against a crafted POST (L39 §2). Skipped when the instance has no tenant yet — an
        #     unsaved model built in a shell has tenant_id None and `self.tenant` would raise
        #     RelatedObjectDoesNotExist on a non-nullable FK rather than return None.
        if self.tenant_id is not None:
            for field in _SCOPE_FK_FIELDS:
                if getattr(self, f"{field}_id", None) is None:
                    continue
                # Defaulted getattr: RelatedObjectDoesNotExist subclasses AttributeError, so a
                # pointer whose row went away degrades to None here instead of 500-ing inside
                # validation. That is safe — resolved_scope() reports the same None and its
                # contract says a scoped target with no subject must be skipped, not widened.
                related = getattr(self, field, None)
                if related is not None and related.tenant_id != self.tenant_id:
                    raise ValidationError({field: "That record belongs to another workspace."})

        # (a) The bands run in the direction the metric runs. lower_is_better climbs away from the
        #     goal (target <= warning <= critical); higher_is_better falls away from it. Only the
        #     bands that are actually set take part — all three are optional.
        bands = [(field, value) for field, value in (
            ("target_value", self.target_value),
            ("warning_threshold", self.warning_threshold),
            ("critical_threshold", self.critical_threshold),
        ) if value is not None]
        lower_is_better = self.direction == "lower_is_better"
        for (prev_field, prev_value), (field, value) in zip(bands, bands[1:]):
            if (value < prev_value) if lower_is_better else (value > prev_value):
                # ASCII comparators deliberately: this string is printed by management commands on
                # a cp1252 Windows console, where U+2264/U+2265 raise UnicodeEncodeError. The '·'
                # and '—' used elsewhere in this app are both IN cp1252; these are not.
                order = ("target <= warning <= critical" if lower_is_better
                         else "target >= warning >= critical")
                raise ValidationError({field: (
                    f"{self.get_direction_display()} for this metric, so the bands run {order}. "
                    f"The {_BAND_LABELS[field]} ({value}) is on the wrong side of the "
                    f"{_BAND_LABELS[prev_field]} ({prev_value}).")})

        # (d) A metric whose registry entry declares a parameter is meaningless without it — "dead
        #     stock" with no N is not a smaller number, it is not a number at all.
        if meta["requires_days"] and self.parameter_days is None:
            raise ValidationError(
                {"parameter_days": f"'{meta['label']}' is defined in terms of a number of days — "
                                   "set one."})
        if meta["requires_pct"] and self.parameter_pct is None:
            raise ValidationError(
                {"parameter_pct": f"'{meta['label']}' is defined in terms of a percentage — "
                                  "set one."})

        # L39: the conjunction that can never be true. Alerting is driven by the two thresholds, so
        # a target with neither can never raise anything — a tick-box that does nothing, which is
        # worse than no tick-box because the operator believes they are covered.
        if self.is_alerting and self.warning_threshold is None and self.critical_threshold is None:
            raise ValidationError(
                {"is_alerting": "Alerting has nothing to fire on — set a warning or a critical "
                                "threshold, or turn alerting off."})

    # ---------------------------------------------------------------------------------------------
    # Derived — nothing below is stored.
    # ---------------------------------------------------------------------------------------------
    def resolved_scope(self):
        """``(scope value, the object it narrows to or None)`` — what the views and the resolver read.

        ``None`` with a scope of ``all`` means the whole network, which is the normal case. ``None``
        with any OTHER scope means the subject was **deleted**: the FKs are ``SET_NULL``, so removing
        a category leaves ``scope="category"`` pointing at nothing. Callers MUST NOT treat that as
        "no filter" and quietly compute the network-wide figure — a target that used to watch one
        category would start reporting a completely different number under the same name. Skip the
        target instead, and see :attr:`scope_label`, which says so on the page.
        """
        field = SCOPE_FIELDS.get(self.scope)
        if not field:
            return self.scope, None
        return self.scope, getattr(self, field, None)

    @property
    def scope_label(self):
        """One line of display text for the scope, e.g. ``"Carrier: DHL Express"``."""
        scope, subject = self.resolved_scope()
        if SCOPE_FIELDS.get(scope) is None:
            return self.get_scope_display()
        if subject is None:
            return f"{self.get_scope_display()} (removed)"
        return f"{self.get_scope_display()}: {subject}"
