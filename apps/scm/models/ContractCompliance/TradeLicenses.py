"""SCM 4.12 Contract & Compliance — ``TradeLicense`` [LIC-], the licence & permit register.

**What this is.** One row per authorisation that lets goods move: an export licence, an ITAR DSP, an
EAR/BIS authorisation, a TAA/MLA agreement, an import permit, a customs authorisation, a hazmat
permit — and, deliberately in the same table, a licence *exception* or general authorisation, which
is claimed rather than granted. Descartes and e2open both register "licences **and activities**" in
one place for the same reason: the question an operator asks before a shipment leaves is "what
authority covers this movement", and an answer that lives in two tables is an answer nobody trusts.

**The balance is the whole point.** A licence is not paperwork, it is a quantity: authorised for
2 000 000 USD or 50 000 units, drawn down by every document issued under it. ``used_value`` and
``used_quantity`` are therefore the only STORED derived figures on this model, and everything
computed *from* them (:attr:`remaining_value`, :attr:`remaining_quantity`,
:attr:`utilization_pct`) is a property that recomputes on read. The split is not arbitrary:

* the two counters are a **cache with a stated invalidation path** — they exist so the list page can
  show a balance without a correlated aggregate per row, they are ``editable=False`` so no form can
  type one, and :meth:`recompute_usage` re-derives both from the documents themselves. Every writer
  (issue / void / delete / the admin action) calls it, so drift is always one button from being
  corrected and can never become permanent;
* the *derived* figures are never columns, because a stored "remaining" would be a second copy of
  the same fact that could disagree with the first. A number a human can compute two ways must have
  exactly one place it comes from.

**Why ``None``, not ``0``, on an unlimited licence.** A licence with no ``authorized_value`` is
unlimited in value, not exhausted. ``remaining_value`` and ``utilization_pct`` return ``None`` there
and the template prints an em dash — the 4.11 ``projected_stockout_count`` lesson: a confident zero
in a green tile is worse than an honest blank, because the blank makes someone go and look.

**FK direction, and why the ``on_delete`` rules are opposite on the two sides.** Every FK *out of*
this model (``holder_party``, ``end_user_party``, ``currency``, ``document``, ``approved_by``) is
``SET_NULL``: those are link-outs to reference data owned by other sub-modules, and retiring a party
or deleting an attachment must never destroy the licence record, which is the audit artefact. The FK
*into* this model — ``TradeDocument.license`` — is ``PROTECT`` for the mirror-image reason: the
record of what actually moved under a licence is the evidence the whole category exists to keep, and
losing it must not be one click away. The consequence is a ``ProtectedError`` path on the delete
view, which is guarded there with a pre-check and a message rather than left as an uncaught 500.

**``renewal_notice_days`` is capped at 3650, like every day-count column in this app.**
``PositiveIntegerField`` accepts 4294967295 on MariaDB, and this number is compared against a date
delta and fed to reminder arithmetic; an absurd value is an uncaught ``OverflowError`` — a 500, not a
validation error (the 4.10 DoS finding). Ten years is past any real renewal horizon.

**``status`` is workflow-controlled and off the form**, exactly like ``SupplierContract.status``. It
moves through the submit / approve / revoke verbs, or — within ``AUTO_STATUSES`` only — from the
dates via :meth:`refresh_status`. A ``draft`` / ``applied`` / ``approved`` / ``suspended`` /
``revoked`` licence is a human decision and a date roll never walks it back.
"""
from apps.scm.models._base import *  # noqa: F401,F403


class TradeLicense(TenantNumbered):
    """An authority-granted (or claimed) authorisation, its dates, its scope and its balance [LIC-]."""

    NUMBER_PREFIX = "LIC"

    # Exceptions/exemptions (``license_exception``, ``general_authorization``) and agreements
    # (``taa_mla``) sit in the SAME register as granted licences — see the module docstring.
    LICENSE_TYPE_CHOICES = [
        ("export_license", "Export License"),
        ("import_license", "Import License"),
        ("itar_dsp", "ITAR DSP (State Dept.)"),
        ("ear_bis", "EAR / BIS License"),
        ("taa_mla", "TAA / MLA Agreement"),
        ("import_permit", "Import Permit"),
        ("customs_authorization", "Customs Authorization"),
        ("hazmat_permit", "HazMat Permit"),
        ("fda_registration", "FDA Registration"),
        ("license_exception", "License Exception"),
        ("general_authorization", "General Authorization"),
        ("other", "Other"),
    ]
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("applied", "Applied For"),
        ("approved", "Approved"),
        ("active", "Active"),
        ("expiring", "Expiring Soon"),
        ("expired", "Expired"),
        ("suspended", "Suspended"),
        ("revoked", "Revoked"),
    ]
    #: The ONLY statuses a date-driven refresh may move between — copied from
    #: ``SupplierContract.AUTO_STATUSES`` rather than reinvented, because the two registers make the
    #: same promise: an expiry roll is bookkeeping, a suspension is a decision.
    AUTO_STATUSES = ("active", "expiring", "expired")
    #: The statuses under which new movement may be authorised. Declared once and read by
    #: :meth:`can_charge`, the issue view and the detail page, so those three can never disagree
    #: about whether a licence is usable (the ``TradeDocument.CHARGING_STATUSES`` posture).
    CHARGEABLE_STATUSES = ("active", "expiring")

    #: Colour per status, decided in ONE place (the ``SupplyChainAlert.STATUS_CSS`` precedent).
    #: theme.css has badge-green / red / amber / info / muted / slate ONLY.
    STATUS_CSS = {
        "draft": "badge-slate",
        "applied": "badge-info",
        "approved": "badge-info",
        "active": "badge-green",
        "expiring": "badge-amber",
        "expired": "badge-red",
        "suspended": "badge-amber",
        "revoked": "badge-red",
    }

    #: The FKs ``clean()`` tenant-checks. Table-driven so adding a pointer to this model means adding
    #: it here, not remembering to copy a fourth if-block.
    TENANT_SCOPED_FKS = ("holder_party", "end_user_party", "document")

    # --- identity ------------------------------------------------------------------------------
    # The authority's own number, distinct from the internal LIC- ``number``. Unique per tenant so
    # the same licence cannot be registered twice and have its balance drawn down in two places;
    # the form mixes in TenantUniqueMixin so a duplicate is a field error, not an IntegrityError 500.
    license_number = models.CharField(max_length=64, help_text="The issuing authority's own number")
    title = models.CharField(max_length=255)
    license_type = models.CharField(max_length=24, choices=LICENSE_TYPE_CHOICES, default="export_license")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="draft", editable=False)
    issuing_authority = models.CharField(
        max_length=255, help_text="BIS, DDTC, the customs authority, the ministry")
    issuing_country = models.CharField(max_length=64, blank=True)

    # --- who it covers -------------------------------------------------------------------------
    holder_party = models.ForeignKey(
        "core.Party", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="scm_trade_licenses_held",
        help_text="Normally us — set it when the licence is held by a subsidiary or an agent")
    # BIS-711 style: the final recipient and intended use are part of the authorisation, not of the
    # shipment, so an end user recorded here is checkable before a document is ever raised.
    end_user_party = models.ForeignKey(
        "core.Party", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="scm_trade_licenses_as_end_user",
        help_text="The named end user / sub-licensee the authority approved")

    # --- dates ---------------------------------------------------------------------------------
    application_date = models.DateField(null=True, blank=True)
    issue_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    # Capped at ten years — see the module docstring for why a day count is never a bare
    # PositiveIntegerField here.
    renewal_notice_days = models.PositiveIntegerField(
        default=60, validators=[MinValueValidator(0), MaxValueValidator(3650)],
        help_text="Start flagging this licence as expiring this many days before it lapses")

    # --- system stamps (L22) — written only by the verb routes, never by a form -----------------
    approved_at = models.DateTimeField(null=True, blank=True, editable=False)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, editable=False,
        related_name="scm_trade_licenses_approved")
    revoked_at = models.DateTimeField(null=True, blank=True, editable=False)
    revocation_reason = models.TextField(blank=True, editable=False)

    # --- the balance ---------------------------------------------------------------------------
    # authorized_* are NULLABLE and that nullability carries meaning: NULL is "unlimited in this
    # dimension", which is why every reader below returns None rather than 0 for it. used_* are the
    # re-derivable cache described in the module docstring.
    authorized_value = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(ZERO)],
        help_text="Total value this licence authorises. Leave blank for a licence with no value cap")
    used_value = models.DecimalField(max_digits=14, decimal_places=2, default=0, editable=False)
    authorized_quantity = models.DecimalField(
        max_digits=14, decimal_places=4, null=True, blank=True, validators=[MinValueValidator(ZERO)],
        help_text="Total quantity this licence authorises. Leave blank for no quantity cap")
    used_quantity = models.DecimalField(max_digits=14, decimal_places=4, default=0, editable=False)
    currency = models.ForeignKey(
        "accounting.Currency", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="scm_trade_licenses")

    # --- what it covers ------------------------------------------------------------------------
    # Free text on purpose: this repo has no HS/ECCN master and no country-control content, and
    # inventing a dropdown over data we do not have would be a fake feed with a real audit trail
    # hanging off it. A typed string is honest; a wrong picklist is not.
    commodity_scope = models.TextField(blank=True, help_text="What goods this licence covers")
    eccn_or_hs = models.CharField(
        max_length=255, blank=True, help_text="ECCN / USML / HS classifications covered")
    destination_countries = models.CharField(max_length=500, blank=True, help_text="Approved destinations")
    # Provisos and RWA statuses. Anything needing PERIODIC PROOF becomes a ComplianceRequirement with
    # source="license" pointing here — 4.12 has exactly one recurring-obligation engine, not two.
    conditions = models.TextField(blank=True, help_text="Provisos, RWA statuses, conditions")

    document = models.ForeignKey(
        "core.Document", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="scm_trade_licenses", help_text="The issued licence document")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["expiry_date", "-id"]
        unique_together = (("tenant", "number"), ("tenant", "license_number"))
        indexes = [
            models.Index(fields=["tenant", "status"], name="scm_lic_tnt_status_idx"),
            # The expiry chip and the renewal queue both order/filter on this.
            models.Index(fields=["tenant", "expiry_date"], name="scm_lic_tnt_expiry_idx"),
            models.Index(fields=["tenant", "license_type"], name="scm_lic_tnt_type_idx"),
        ]

    def __str__(self):
        return f"{self.number or 'LIC'} · {self.title}"

    # ---------------------------------------------------------------------------------------------
    # Validation
    # ---------------------------------------------------------------------------------------------
    def clean(self):
        """Cross-tenant FK guard plus the date ladder.

        ``used_value`` / ``used_quantity`` are deliberately NOT validated here: they are not on the
        form and are only ever written by :meth:`recompute_usage`, so a rule here would be enforcing
        an invariant against code that already derives it.
        """
        super().clean()

        # THE GUARD. The form's querysets are tenant-scoped, but that is UX — a narrowed dropdown has
        # never held against a crafted POST (L39 §2). Skipped when the instance has no tenant yet: an
        # unsaved model has tenant_id None and ``self.tenant`` would raise RelatedObjectDoesNotExist
        # on a non-nullable FK rather than return None.
        if self.tenant_id is not None:
            for name in self.TENANT_SCOPED_FKS:
                if getattr(self, f"{name}_id", None) is None:
                    continue
                # Defaulted getattr: RelatedObjectDoesNotExist subclasses AttributeError, so a
                # pointer whose row went away degrades to None here instead of 500-ing inside
                # validation.
                related = getattr(self, name, None)
                if related is not None and related.tenant_id != self.tenant_id:
                    raise ValidationError({name: "That record belongs to another workspace."})

        # The ladder: application -> issue -> expiry. ASCII comparators in the messages deliberately —
        # they are printed by management commands on a cp1252 Windows console, where U+2264 raises
        # UnicodeEncodeError.
        if self.application_date and self.issue_date and self.issue_date < self.application_date:
            raise ValidationError(
                {"issue_date": "A licence cannot be issued before it was applied for "
                               "(application date <= issue date)."})
        if self.issue_date and self.expiry_date and self.expiry_date < self.issue_date:
            raise ValidationError(
                {"expiry_date": "A licence cannot expire before it was issued "
                                "(issue date <= expiry date)."})
        # The outer rung, checked separately: with no issue date the two guards above both pass and
        # a licence could still expire before it was applied for.
        if (self.issue_date is None and self.application_date and self.expiry_date
                and self.expiry_date < self.application_date):
            raise ValidationError(
                {"expiry_date": "A licence cannot expire before it was applied for "
                                "(application date <= expiry date)."})

    # ---------------------------------------------------------------------------------------------
    # Expiry — the same three methods as SupplierContract (SupplierContracts.py:109-136), reading
    # expiry_date instead of end_date. One idiom for "this agreement is running out", not two.
    # ---------------------------------------------------------------------------------------------
    def days_to_expiry(self, today=None):
        """Days until ``expiry_date`` (negative once past). ``None`` when no expiry is recorded."""
        if not self.expiry_date:
            return None
        # timezone.localdate(), not date.today(): the project is TZ-aware and the server's date is
        # not necessarily the workspace's. This is the idiom every module from 4.7 on uses.
        return (self.expiry_date - (today or timezone.localdate())).days

    def is_expiring_soon(self, today=None):
        """Inside the renewal notice window and not yet lapsed."""
        days = self.days_to_expiry(today)
        return days is not None and 0 <= days <= self.renewal_notice_days

    def refresh_status(self, today=None, save=True):
        """Move active <-> expiring <-> expired from the dates. Never overrides a human decision.

        ``save=False`` leaves the new status on the instance for the caller to write — that is how
        the list view rolls a whole page in ONE ``bulk_update`` instead of a ``save()`` per row
        (the ``_roll_contract_statuses`` precedent).
        """
        if self.status not in self.AUTO_STATUSES:
            return
        days = self.days_to_expiry(today)
        if days is None:
            new = "active"
        elif days < 0:
            new = "expired"
        elif days <= self.renewal_notice_days:
            new = "expiring"
        else:
            new = "active"
        if new != self.status:
            self.status = new
            if save:
                self.save(update_fields=["status", "updated_at"])

    # ---------------------------------------------------------------------------------------------
    # The balance
    # ---------------------------------------------------------------------------------------------
    def recompute_usage(self, save=True):
        """Re-derive both counters from the documents charged to this licence.

        TWO aggregates, and never a per-document loop — the cost is constant in the number of
        documents either way. It is two rather than the obvious one because ``declared_value`` lives
        on the document and ``quantity`` lives on its lines: asking for both in a single
        ``aggregate()`` joins the lines in, which FANS THE DOCUMENT ROWS OUT and multiplies every
        ``declared_value`` by that document's line count. A two-line invoice would charge the licence
        twice its face value, silently, forever. Two queries, each over one grain, is the fix.

        This is the stated invalidation path that lets the counters be columns at all: it is called
        by the issue, void and delete routes and by the admin re-derive action, so drift is always
        one press from being corrected.
        """
        # Local import: apps/scm/models/__init__.py imports THIS module before TradeDocuments (two
        # models point at TradeLicense), and a module-level import here would invert that edge. The
        # FK itself is declared by string on the other side, so nothing else needs the symbol.
        from apps.scm.models.ContractCompliance.TradeDocuments import TradeDocument

        charging = self.trade_documents.filter(status__in=TradeDocument.CHARGING_STATUSES)
        # q2/q4 rather than a bare Decimal: an over-range figure clamps to what the column holds
        # instead of raising DataError, so one poisoned document can only degrade its own licence.
        # Both also turn the empty-queryset Sum -> None into a clean zero.
        self.used_value = q2(charging.aggregate(total=Sum("declared_value"))["total"])
        self.used_quantity = q4(charging.aggregate(total=Sum("lines__quantity"))["total"])
        if save:
            self.save(update_fields=["used_value", "used_quantity", "updated_at"])

    def can_charge(self, value=None, quantity=None):
        """``(allowed, reason)`` — may this licence absorb one more ``value`` / ``quantity``?

        The caller REFUSES on False and shows ``reason``; it does not clamp the charge to the
        headroom and carry on. Clamping would let a shipment go out partly unauthorised while the
        register still looked healthy, which is precisely the failure a licence balance exists to
        prevent. ``reason`` is empty when allowed.
        """
        if self.status not in self.CHARGEABLE_STATUSES:
            return False, (f"This licence is {self.get_status_display().lower()} — only an active or "
                           "expiring licence can authorise new movement.")
        # Belt and braces against a STALE status: the column is rolled forward lazily by the list
        # page, so a licence that lapsed since anyone last looked is still sitting at 'active' in the
        # database. The dates are the authority here, not the cached word.
        days = self.days_to_expiry()
        if days is not None and days < 0:
            return False, f"This licence expired on {self.expiry_date} — it cannot authorise new movement."

        if self.authorized_value is not None:
            headroom = self.remaining_value
            charge = q2(value)
            if charge > headroom:
                return False, (f"Charging {charge} would exceed the authorised value — only "
                               f"{headroom} of {self.authorized_value} is left.")
        if self.authorized_quantity is not None:
            headroom = self.remaining_quantity
            charge = q4(quantity)
            if charge > headroom:
                return False, (f"Charging {charge} would exceed the authorised quantity — only "
                               f"{headroom} of {self.authorized_quantity} is left.")
        return True, ""

    # ---------------------------------------------------------------------------------------------
    # Derived — nothing below is stored. See the module docstring for why, and for why an unlimited
    # licence answers None rather than 0.
    # ---------------------------------------------------------------------------------------------
    @property
    def remaining_value(self):
        """Authorised minus used, or ``None`` when the licence has no value cap.

        Deliberately NOT floored at zero: an over-drawn licence must read as over-drawn on the page,
        not as a tidy 0.00 that looks like it merely ran out.
        """
        if self.authorized_value is None:
            return None
        return q2(self.authorized_value - (self.used_value or ZERO))

    @property
    def remaining_quantity(self):
        """The 4dp sibling of :attr:`remaining_value` — ``None`` when there is no quantity cap."""
        if self.authorized_quantity is None:
            return None
        return q4(self.authorized_quantity - (self.used_quantity or ZERO))

    @property
    def utilization_pct(self):
        """How much of the licence is consumed, 0-100+, or ``None`` when nothing is authorised.

        Value first, quantity second: a licence capped both ways is understood in money by everyone
        who reads the page. ``None`` — never ``0`` — when neither dimension is capped or the cap is
        zero, because "unlimited" and "untouched" are different facts and a 0% bar states the second.
        Values above 100 are returned as-is; an over-drawn licence has to look over-drawn.
        """
        for authorized, used in ((self.authorized_value, self.used_value),
                                 (self.authorized_quantity, self.used_quantity)):
            if authorized is None or Decimal(authorized) <= ZERO:
                continue
            return (Decimal(used or ZERO) / Decimal(authorized) * 100).quantize(Decimal("0.01"))
        return None

    @property
    def status_css(self):
        """theme.css badge class for :attr:`status` — one lookup, so no template invents a colour."""
        return self.STATUS_CSS.get(self.status, "badge-muted")
