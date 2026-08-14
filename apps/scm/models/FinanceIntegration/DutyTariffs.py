"""SCM 4.18 Finance & Accounting Integration — ``DutyTariff``: the customs duty master.

A **duty tariff** is one tenant-scoped, effective-dated answer to the question a landed-cost
calculation asks at the border: *what percentage of declared value does this HS/HTS classification,
arriving from this country of origin, attract on this date?* It is the master 4.18's duty charge
line reads ONCE, to DEFAULT its own ``duty_rate_pct`` — the rate is then **snapshotted onto
``LandedCostCharge``**, so a later correction to a tariff can never silently rewrite what a landed
receipt was costed at last quarter.

--------------------------------------------------------------------------------------------------
WHY THIS IS NOT ``accounting.TaxCode`` — the one question every reviewer asks
--------------------------------------------------------------------------------------------------
``accounting.TaxCode`` (``apps/accounting/models/Tax/TaxCodes.py:6``) is structurally incapable of
being a customs master, and the gap is not cosmetic:

* its ``TAX_TYPE_CHOICES`` are ``sales`` / ``vat`` / ``gst`` / ``use`` — there is no customs member,
  and adding one would put a border levy into the same registry the sales-tax engine reads;
* it carries no ``hs_code``, so there is nothing to classify against; and
* it carries no origin dimension at all, and duty is a function of the ORIGIN/DESTINATION PAIR — the
  same classification arriving from two countries is routinely two different rates.

So this table exists. What it deliberately does **not** do is re-declare a sales-tax rate: VAT, GST,
sales and use tax stay ``accounting.TaxCode``, which ``LandedCostCharge.tax_code`` FKs directly and
which this model's own ``tax_code`` points at for the *recoverable import-VAT counterpart* of a duty
line. Two rate tables covering the same levy is the second-source-of-truth defect (L29); one rate
table covering two unrelated levies is the bug this one avoids.

--------------------------------------------------------------------------------------------------
THREE DECISIONS A READER SHOULD NOT HAVE TO REDISCOVER
--------------------------------------------------------------------------------------------------
1. **``effective_from`` is NEVER nullable.** It is part of
   ``unique_together ("tenant", "hs_code", "country_of_origin", "effective_from")``, and **MySQL does
   not enforce a unique key across rows where a member column is NULL** — every NULL compares
   unequal to every other NULL, so a nullable start date would silently permit unlimited duplicates
   of exactly the row this constraint exists to prevent. It is also what :meth:`DutyTariff.rate_for`
   orders and windows on; a rate with no start date cannot be looked up by transaction date at all.

2. **A blank ``country_of_origin`` MEANS "any origin"**, not "unknown". It is the catch-all row, and
   :meth:`rate_for` prefers a named origin over it rather than treating the two as alternatives —
   that ordering is the whole reason both can coexist for one HS code on one day.

3. **Nothing here is a stored balance and nothing here posts to the ledger.** SCM posts no
   ``JournalEntry``; ``LandedCostVoucher.draft_bill()`` creates a DRAFT ``accounting.Bill`` and
   stops, and accounting posts the entry. ``is_current`` is a computed property, never a column, so
   a row cannot go stale by sitting still (L29).

**BACKEND PACKAGE ``FinanceIntegration/`` vs TEMPLATE FOLDER ``templates/scm/finance/`` — the
asymmetry IS the house rule, not a defect.** All seventeen shipped scm template folders use a short
slug while the Python package uses the NavERP.md sub-module title in PascalCase
(``ThirdPartyLogistics/`` ↔ ``templates/scm/3pl/``, ``CustomerPortal/`` ↔ ``templates/scm/portal/``,
``ContractCompliance/`` ↔ ``templates/scm/compliance/``). Do not "fix" ``finance/`` into
``financeintegration/``; the note is repeated in ``SKILL.md`` for exactly that reason.
"""
from apps.scm.models._base import *  # noqa: F401,F403


class DutyTariff(TenantNumbered):
    """One effective-dated customs duty rate for an HS/HTS code and a country of origin [DTY-].

    The natural key is ``(tenant, hs_code, country_of_origin, effective_from)`` — one workspace may
    hold many rows for one classification (an origin-specific rate beside the any-origin fallback,
    and a new version of either the day a schedule changes), but never two that start on the same day
    for the same origin, because then :meth:`rate_for` would pick one by accident.
    """

    NUMBER_PREFIX = "DTY"

    #: Read by BOTH boundaries — this model's :meth:`clean` (which holds against a management command
    #: and a shell) and ``DutyTariffForm.clean``'s ``_reject_foreign`` call (which holds against a
    #: crafted POST, and keys the error on a field the form actually carries so it renders instead of
    #: raising ``ValueError`` out of ``add_error``). Naming a pointer here covers it at both.
    TENANT_SCOPED_FKS = ("tax_code",)

    hs_code = models.CharField(
        max_length=20,
        help_text="Harmonised System / HTS classification, e.g. 8471.30. Stored upper-cased.")
    country_of_origin = models.CharField(
        max_length=64, blank=True,
        help_text="Leave blank to apply to any country of origin.")
    description = models.CharField(
        max_length=255, blank=True,
        help_text="What this classification covers, in the words the broker uses.")
    duty_rate_pct = models.DecimalField(
        max_digits=6, decimal_places=3, default=0,
        validators=[MinValueValidator(ZERO), MaxValueValidator(100)],
        help_text="Percentage of declared value. 3dp — duty schedules are routinely quoted to "
                  "fractions of a percent.")
    # NEVER nullable. See decision 1 in the module docstring: a NULL member silently disables the
    # unique key in MySQL, and a rate with no start date cannot be windowed by transaction date.
    effective_from = models.DateField(
        help_text="Required — a rate with no start date cannot be looked up by transaction date.")
    effective_to = models.DateField(
        null=True, blank=True,
        help_text="Last day this rate applies; blank = open-ended (until it is superseded).")
    is_active = models.BooleanField(
        default=True,
        help_text="Clear this to retire a rate without losing what it costed.")
    # The RECOVERABLE counterpart of a duty line — import VAT/GST is reclaimable where the duty
    # itself is not, and the two are quoted together on a broker's entry. `accounting.TaxCode` is the
    # single owner of that rate; this is a pointer at it, never a second copy of it.
    tax_code = models.ForeignKey(
        "accounting.TaxCode", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="scm_duty_tariffs",
        help_text="Recoverable import VAT/GST that accompanies this duty, if any.")

    class Meta:
        # Grouped by classification, newest schedule first inside it — the row somebody wants is
        # almost always the one that just started applying.
        ordering = ["hs_code", "-effective_from"]
        unique_together = (
            ("tenant", "number"),
            ("tenant", "hs_code", "country_of_origin", "effective_from"),
        )
        indexes = [
            # Covers the ONE shape every read of this table takes: `rate_for()` narrows on
            # (tenant, hs_code) before it windows on the dates, and the list page's ORDER BY leads
            # with `hs_code`. The (tenant, hs_code, country_of_origin, effective_from) unique key
            # already indexes the wider prefix, but it is declared as a constraint rather than as an
            # ordering aid, and this one states the access path the queries are written against.
            models.Index(fields=["tenant", "hs_code"], name="scm_dty_tnt_hs_idx"),
        ]

    # ---------------------------------------------------------------------------------------------
    # Derived — not a column
    # ---------------------------------------------------------------------------------------------
    @property
    def is_current(self):
        """Is this rate in force TODAY? A property, deliberately — never a stored flag.

        A stored "current" column would be wrong the morning after every ``effective_to``, and there
        is no scheduler in this project to roll it. ``effective_to = None`` is +infinity.

        Reads ``is_active`` as well as the window, so it answers the question the badge asks: an
        inactive row is not in force even if today sits inside its dates. The list page's ``current``
        statistic is computed with the same two halves so the count and the badges can never disagree.
        """
        if not self.is_active or self.effective_from is None:
            return False
        today = timezone.localdate()
        if today < self.effective_from:
            return False
        return self.effective_to is None or today <= self.effective_to

    # ---------------------------------------------------------------------------------------------
    # The lookup — read ONCE, to DEFAULT a charge line; never to restate a costed one
    # ---------------------------------------------------------------------------------------------
    @classmethod
    def rate_for(cls, tenant, hs_code, country_of_origin, on_date):
        """The tariff that applies to ``hs_code`` from ``country_of_origin`` on ``on_date``, or ``None``.

        Resolution order, and every step of it matters:

        1. **Active only.** A retired rate is a rate nobody currently owes.
        2. **Window contains the date** — ``effective_from <= on_date`` and
           (``effective_to IS NULL`` OR ``effective_to >= on_date``). The ``isnull`` leg is carried
           explicitly because a comparison against NULL in SQL is neither true nor false and would
           silently drop every open-ended row from the result.
        3. **A named origin beats the any-origin row.** Both may legitimately exist for one HS code
           on one day — the blank row is the fallback, not an alternative — so the specific match is
           tried first and the blank one only if it misses.
        4. **Newest ``effective_from`` first**, tie-broken on ``-id``, so a schedule change that
           starts today wins over the one that started last year.

        Returns ``None`` rather than raising for anything unresolvable (no tenant, no code, no
        matching row): the caller is DEFAULTING a form field, and a missing tariff means "type the
        rate yourself", not "fail the page".

        **The result is a DEFAULT, not a source of truth.** ``LandedCostCharge.duty_rate_pct``
        snapshots the number, so correcting a tariff tomorrow never rewrites what a receipt was
        costed at today.
        """
        if tenant is None or on_date is None:
            return None
        code = (hs_code or "").strip().upper()
        if not code:
            return None

        qs = cls.objects.filter(
            tenant=tenant, hs_code=code, is_active=True, effective_from__lte=on_date,
        ).filter(Q(effective_to__isnull=True) | Q(effective_to__gte=on_date))

        origin = (country_of_origin or "").strip()
        if origin:
            # `__iexact`, not `=`: the column is free text a human types, and "germany" and
            # "Germany" are the same origin. The blank-any fallback below is an EXACT empty-string
            # test, which needs no such tolerance.
            match = qs.filter(country_of_origin__iexact=origin).order_by(
                "-effective_from", "-id").first()
            if match is not None:
                return match
        return qs.filter(country_of_origin="").order_by("-effective_from", "-id").first()

    # ---------------------------------------------------------------------------------------------
    # Validation + normalisation
    # ---------------------------------------------------------------------------------------------
    def clean(self):
        """Normalise the two free-text keys, then refuse an inverted window and a foreign tax code.

        The normalisation runs HERE rather than in the form because ``hs_code`` and
        ``country_of_origin`` are both members of the natural key: ``full_clean()`` calls ``clean()``
        **before** ``validate_unique()``, so upper-casing/stripping here is what makes ``8471.30``
        and ``  8471.30  `` collide on the uniqueness check instead of quietly becoming two rows that
        :meth:`rate_for` then has to choose between. It also holds on a shell/management-command save
        path that never sees a form.

        Every error key is a field ``DutyTariffForm`` actually carries — ``ModelForm._post_clean``
        hands each key straight to ``Form.add_error``, which **raises ``ValueError`` for a key the
        form does not have**, turning a field error into a 500.
        """
        self.hs_code = (self.hs_code or "").strip().upper()
        self.country_of_origin = (self.country_of_origin or "").strip()

        errors = {}

        if (self.effective_from is not None and self.effective_to is not None
                and self.effective_to < self.effective_from):
            errors["effective_to"] = (
                f"This rate would stop applying ({self.effective_to}) before it starts "
                f"({self.effective_from}).")

        # The DATABASE-boundary half of the cross-tenant guard. `DutyTariffForm.clean` repeats it at
        # the form boundary via `_reject_foreign` — a narrowed <select> has never held against a
        # crafted POST, and this leg also covers the shell and the seeder. Read behind an `_id` test
        # so an unsaved instance validates instead of raising `RelatedObjectDoesNotExist`.
        if self.tenant_id:
            for name in self.TENANT_SCOPED_FKS:
                if getattr(self, f"{name}_id", None) is None:
                    continue
                related = getattr(self, name, None)
                if related is not None and related.tenant_id != self.tenant_id:
                    errors[name] = "That record belongs to another workspace."

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.hs_code} · {self.country_of_origin or 'Any'} · {self.duty_rate_pct}%"
