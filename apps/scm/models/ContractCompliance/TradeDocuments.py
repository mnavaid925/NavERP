"""SCM 4.12 Contract & Compliance — ``TradeDocument`` [TD-] + its ``TradeDocumentLine`` children.

**What this is.** The import/export paperwork register: one row per piece of trade documentation —
a commercial invoice, a packing list, an ocean bill of lading, an air waybill, a certificate of
origin, a dangerous-goods declaration, a customs declaration. It records what was declared, to whom,
under which licence, and where the filed document got to in its lifecycle. Drivers: Shipping
Solutions' standard export-form field lists, e2open / ONESOURCE documentation generation, SAP GTS's
customs-declaration lifecycle.

**What this is NOT: a second consignment.** 4.6 owns the physical movement. ``shipment`` /
``carrier`` / ``purchase_order`` / ``sales_order`` are link-outs, and this model re-declares no
addresses, no tracking events, no proof of delivery. The transport columns that ARE here
(``vessel_or_flight``, ``port_of_loading``, ``container_numbers``) are the ones *printed on the form*
and are snapshots for exactly the reason the line snapshots are — see below.

**Why the link-outs are ``SET_NULL`` and the licence is ``PROTECT``.** Every pointer out of this
table is ``SET_NULL``: a filed customs document is the record of a declaration that was actually
made, and it has to outlive the shipment, the order, the carrier or the counterparty it was made
against. ``CASCADE`` would mean tidying up an old shipment silently destroys the paperwork filed
under it, which is the one thing a customs audit asks for. ``license`` is the deliberate exception
and is ``PROTECT``: the record of what moved under a licence IS the licence's audit trail and its
consumed balance, so losing it must not be one click away. That makes ``tradelicense_delete`` a
``ProtectedError`` path — the view pre-checks ``license.trade_documents.exists()`` and refuses with a
message rather than 500-ing.

**Why the lines carry snapshot columns instead of reading the item master.** ``description`` /
``hs_code`` / ``country_of_origin`` / ``uom_text`` are frozen copies taken at line entry, sitting
next to the live ``item`` / ``uom`` pointers rather than instead of them. A filed declaration must
report **what was declared**; re-classifying an item a year later must never rewrite a document that
was already submitted to an authority. This is also why 4.12 adds no ``hs_code`` column to
``scm.Item``: a mutable master plus a filed document would be two sources of truth for the same
fact, and the "helpful" default that syncs them is the bug. Nothing in this module back-fills a
snapshot — there is deliberately no ``save()`` override on the line.

**Why ``status`` is off the form.** The lifecycle (draft → issued → submitted → accepted, plus
amended and void) is moved only by the issue / submit / accept / void verbs, because issuing is what
charges a licence balance and voiding is what gives it back. A free-text status dropdown would let
someone type "issued" without ever calling ``can_charge()``. ``CHARGING_STATUSES`` is declared here
and read by ``TradeLicense.recompute_usage()`` **and** by the detail page, so the set that spends a
licence and the set the page says spends a licence cannot drift apart.

**Why the money figures are properties.** ``lines_total``, ``declared_value_matches`` and
``line_value`` are computed, never columns. A stored line total is a column that can be edited to
disagree with its own arithmetic, and a stored document total is one that goes stale the moment a
line is added through the inline formset. ``declared_value`` is the exception and IS stored — it is
not derived, it is the value the filer *declared*, and the whole point of ``declared_value_matches``
is to show when the declaration and the lines diverge (an amber badge on the detail page: a customs
problem, not a rounding one).

**No day-count column lives here.** The 3650-day caps that the rest of 4.12 carries are on
``TradeLicense.renewal_notice_days`` and ``ComplianceRequirement.notice_days``, the two numbers fed
to ``timedelta(days=…)``. Nothing on this model is a duration, so nothing here needs that cap;
``package_count`` is a count of boxes and is never arithmetic on a date.

4.12 is read-only over 4.1-4.11: nothing here writes a ``StockMove`` or a ``JournalEntry`` (L29).
"""
from django.utils.functional import cached_property

from apps.scm.models._base import *  # noqa: F401,F403

#: Every tenant-scoped FK on ``TradeDocument``, listed once and walked by its ``clean()``. Adding an
#: FK to the model without adding it here silently drops it out of the cross-tenant guard, so the
#: list sits beside the class rather than buried inline in the method.
_TENANT_SCOPED_FKS = (
    "shipment", "carrier", "purchase_order", "sales_order", "license",
    "shipper_party", "consignee_party", "notify_party", "document",
)


class TradeDocument(TenantNumbered):
    """One piece of import/export paperwork [TD-], its parties, its transport and its filing state."""

    NUMBER_PREFIX = "TD"

    # max_length=32: `shippers_letter_of_instruction` is 30 chars. Sized with headroom on purpose —
    # 4.10's `NonConformance.source` was cut to the longest value of the day and the next 15-char
    # value turned "add a choice" into a column widen.
    DOC_TYPE_CHOICES = [
        ("commercial_invoice", "Commercial Invoice"),
        ("proforma_invoice", "Proforma Invoice"),
        ("packing_list", "Packing List"),
        ("certificate_of_origin", "Certificate of Origin"),
        ("bill_of_lading_ocean", "Bill of Lading (Ocean)"),
        ("bill_of_lading_inland", "Bill of Lading (Inland)"),
        ("air_waybill", "Air Waybill"),
        ("shippers_letter_of_instruction", "Shipper's Letter of Instruction"),
        ("dangerous_goods_declaration", "Dangerous Goods Declaration"),
        ("export_license_copy", "Export Licence Copy"),
        ("insurance_certificate", "Insurance Certificate"),
        ("customs_declaration", "Customs Declaration"),
        ("eei_aes", "EEI / AES Filing"),
    ]
    # Mirrors Shipment.DIRECTION_CHOICES semantics without re-declaring outbound/inbound: paperwork
    # talks about export and import, a consignment talks about outbound and inbound.
    DIRECTION_CHOICES = [
        ("export", "Export"),
        ("import", "Import"),
    ]
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("issued", "Issued"),
        ("submitted", "Submitted"),
        ("accepted", "Accepted"),
        ("amended", "Amended"),
        ("void", "Void"),
    ]
    # Incoterms 2020. Deliberately NOT wired to the field as `choices=` — see `clean()`.
    INCOTERM_CHOICES = [
        ("EXW", "EXW — Ex Works"),
        ("FCA", "FCA — Free Carrier"),
        ("FAS", "FAS — Free Alongside Ship"),
        ("FOB", "FOB — Free On Board"),
        ("CFR", "CFR — Cost and Freight"),
        ("CIF", "CIF — Cost, Insurance and Freight"),
        ("CPT", "CPT — Carriage Paid To"),
        ("CIP", "CIP — Carriage and Insurance Paid To"),
        ("DAP", "DAP — Delivered at Place"),
        ("DPU", "DPU — Delivered at Place Unloaded"),
        ("DDP", "DDP — Delivered Duty Paid"),
    ]

    # A document that has left the building is a filed instrument; changing it is an amendment.
    EDITABLE_STATUSES = ("draft", "amended")
    # The set that counts against a licence balance. Declared ONCE and read by
    # TradeLicense.recompute_usage() and by the detail page, so the balance and the page that
    # explains the balance can never encode two different rules (the 4.10 "unposted filter encoded
    # two of three shapes" finding).
    CHARGING_STATUSES = ("issued", "submitted", "accepted")

    STATUS_CSS = {
        "draft": "badge-slate",
        "issued": "badge-info",
        "submitted": "badge-amber",
        "accepted": "badge-green",
        "amended": "badge-amber",
        "void": "badge-muted",
    }

    # --- what kind of paper, and where it is in its life ------------------------------------------
    doc_type = models.CharField(max_length=32, choices=DOC_TYPE_CHOICES, default="commercial_invoice")
    direction = models.CharField(max_length=6, choices=DIRECTION_CHOICES, default="export")
    # Workflow-controlled (L22): moved only by the issue / submit / accept / void verbs, never typed.
    # Issuing is what charges a licence, so a hand-set status would spend a balance no one checked.
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="draft", editable=False)
    # The authority's / carrier's own number for this instrument, distinct from our internal TD-
    # sequence. Every GTM product keeps both: ours is how WE find it, theirs is what the broker,
    # the bank and the customs officer quote back at us.
    document_number = models.CharField(max_length=64, blank=True,
                                       help_text="The external BoL / invoice / AWB number printed on the form")
    issue_date = models.DateField(null=True, blank=True, help_text="The date printed on the form")
    # System stamps (L22): written by the issue verb, never by a form.
    issued_at = models.DateTimeField(null=True, blank=True, editable=False)
    issued_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                  editable=False, related_name="scm_trade_documents_issued")

    # --- what movement it papers (link-outs: 4.6 and 4.1/4.5 own these rows) ----------------------
    shipment = models.ForeignKey("scm.Shipment", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="trade_documents",
                                 help_text="The 4.6 consignment this paperwork covers")
    carrier = models.ForeignKey("scm.Carrier", on_delete=models.SET_NULL, null=True, blank=True,
                                related_name="trade_documents")
    purchase_order = models.ForeignKey("scm.PurchaseOrder", on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name="trade_documents")
    sales_order = models.ForeignKey("scm.SalesOrder", on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name="trade_documents")
    # PROTECT, alone among the FKs on this model: the documents issued under a licence ARE its
    # consumed balance and its audit trail. tradelicense_delete pre-checks trade_documents.exists()
    # and refuses with a message, so the ProtectedError never reaches the user as a 500.
    license = models.ForeignKey("scm.TradeLicense", on_delete=models.PROTECT, null=True, blank=True,
                                related_name="trade_documents",
                                help_text="The licence this movement is authorised under — its balance is "
                                          "charged when this is issued")

    # --- who the parties are (all core.Party — no party-like table of our own) --------------------
    shipper_party = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name="scm_trade_docs_as_shipper")
    consignee_party = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True,
                                        related_name="scm_trade_docs_as_consignee")
    notify_party = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name="scm_trade_docs_as_notify",
                                     help_text="Advised on arrival — often the broker, not the buyer")
    country_of_origin = models.CharField(max_length=64, blank=True)
    country_of_destination = models.CharField(max_length=64, blank=True)

    # --- the money on the form --------------------------------------------------------------------
    currency = models.ForeignKey("accounting.Currency", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="scm_trade_documents")
    # STORED, unlike every other figure here: this is what the filer DECLARED, not a sum of anything.
    # `declared_value_matches` is what surfaces a divergence from the lines.
    declared_value = models.DecimalField(max_digits=14, decimal_places=2, default=0,
                                         validators=[MinValueValidator(ZERO)])
    freight_charges = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True,
                                          validators=[MinValueValidator(ZERO)])
    insurance_value = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True,
                                          validators=[MinValueValidator(ZERO)],
                                          help_text="Marine / cargo insured value")
    # Incoterms 2020. No `choices=` on the column on purpose: the term set is a versioned external
    # standard, so keeping it in a constant means the next revision is a one-line data edit read by
    # the form and by clean(), not an AlterField migration on a shipped table. clean() normalises
    # case first and then enforces membership, which is what holds against a crafted POST.
    incoterm = models.CharField(max_length=3, blank=True,
                                help_text="Incoterms 2020 delivery term, e.g. FOB or DAP")

    # --- what is in the box ------------------------------------------------------------------------
    gross_weight_kg = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
                                          validators=[MinValueValidator(ZERO)])
    net_weight_kg = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
                                        validators=[MinValueValidator(ZERO)],
                                        help_text="The goods alone, without packaging")
    package_count = models.PositiveIntegerField(null=True, blank=True)

    # --- how it travels (as PRINTED on the form — see the module docstring on snapshots) ----------
    vessel_or_flight = models.CharField(max_length=120, blank=True)
    voyage_number = models.CharField(max_length=64, blank=True)
    port_of_loading = models.CharField(max_length=120, blank=True)
    port_of_discharge = models.CharField(max_length=120, blank=True)
    container_numbers = models.CharField(max_length=255, blank=True)
    is_negotiable = models.BooleanField(default=False,
                                        help_text="An ocean BoL is a document of title; an air waybill is not")

    # --- filing and evidence -----------------------------------------------------------------------
    # 4.12 STORES the reference; it does not transmit anything. Real AESDirect / broker filing is
    # deferred and named as such, so this column never pretends a submission happened.
    filing_reference = models.CharField(max_length=64, blank=True,
                                        help_text="AES/ITN or broker reference — 4.12 stores the reference, "
                                                  "it does not file")
    # No FileField anywhere in 4.12: core.Document is the generic attachment, exactly as
    # SupplierContract.document uses it. Module 13 (DMS) layers folders/versions on top later.
    document = models.ForeignKey("core.Document", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="scm_trade_documents", help_text="The signed/stamped scan")
    void_reason = models.TextField(blank=True, editable=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-issue_date", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="scm_td_tnt_status_idx"),
            models.Index(fields=["tenant", "doc_type"], name="scm_td_tnt_type_idx"),
            # The shipment detail page and the list's ?shipment= filter both enter this way.
            models.Index(fields=["tenant", "shipment"], name="scm_td_tnt_shp_idx"),
            models.Index(fields=["tenant", "issue_date"], name="scm_td_tnt_issued_idx"),
        ]

    def __str__(self):
        return f"{self.number or 'TD'} · {self.get_doc_type_display()}"

    # ---------------------------------------------------------------------------------------------
    # Validation
    # ---------------------------------------------------------------------------------------------
    def clean(self):
        super().clean()

        # THE GUARD. Every set FK must belong to this document's own tenant. The form's querysets
        # are tenant-scoped, but that is UX — a narrowed dropdown has never held against a crafted
        # POST (L39 §2). Skipped when the instance has no tenant yet: an unsaved model built in a
        # shell has tenant_id None, and there is nothing to compare against.
        if self.tenant_id is not None:
            for field in _TENANT_SCOPED_FKS:
                if getattr(self, f"{field}_id", None) is None:
                    continue
                # Defaulted getattr: RelatedObjectDoesNotExist subclasses AttributeError, so a
                # pointer whose row went away degrades to None here instead of 500-ing inside
                # validation. A dangling pointer is a display problem, not a tenancy breach.
                related = getattr(self, field, None)
                if related is not None and related.tenant_id != self.tenant_id:
                    raise ValidationError({field: "That record belongs to another workspace."})

        # Incoterm: normalise case, then enforce the closed vocabulary. Typing 'fob' into a text
        # input is a formatting slip, not a different term, so it is corrected rather than refused —
        # but an invented term is refused, because an Incoterm is a legal allocation of cost and
        # risk and a free-text one means nothing to the counterparty reading the form.
        self.incoterm = (self.incoterm or "").strip().upper()
        if self.incoterm and self.incoterm not in _INCOTERM_VALUES:
            raise ValidationError({"incoterm": (
                f"'{self.incoterm}' is not an Incoterms 2020 term. Use one of: "
                f"{', '.join(_INCOTERM_VALUES)}.")})

        # Net is the goods, gross is the goods plus the packaging. The reverse is not a smaller
        # number, it is a packing list that will be rejected at the border.
        if (self.net_weight_kg is not None and self.gross_weight_kg is not None
                and self.net_weight_kg > self.gross_weight_kg):
            raise ValidationError({"net_weight_kg": (
                f"Net weight ({self.net_weight_kg} kg) is the goods alone and gross weight "
                f"({self.gross_weight_kg} kg) includes the packaging, so net cannot be the larger "
                "of the two.")})

    # ---------------------------------------------------------------------------------------------
    # Derived — nothing below is stored.
    # ---------------------------------------------------------------------------------------------
    @cached_property
    def lines_total(self):
        """The sum of the child lines' ``quantity × unit_value``, in ONE aggregate.

        Memoised per instance because the detail page reads it and
        :attr:`declared_value_matches` reads it again — a plain property would be two identical
        queries per render. Cached on the instance, not stored on the row: a caller that has just
        written lines through the formset re-reads the document rather than trusting this.

        Pushed into SQL rather than summed in Python over ``line_value`` so that a 500-line customs
        invoice costs one query instead of 500 model instantiations. ``q2()`` clamps as well as
        quantizes, so a poisoned line can only distort this figure, never raise ``DataError``.
        """
        if self.pk is None:
            # An unsaved document has no reverse manager to query; the honest answer is zero, not
            # an exception raised from inside a template.
            return ZERO
        total = self.lines.aggregate(
            s=Sum(F("quantity") * F("unit_value"),
                  output_field=models.DecimalField(max_digits=20, decimal_places=6)))["s"]
        return q2(total or ZERO)

    @property
    def declared_value_matches(self):
        """Does the declared value agree with the sum of the lines, to the cent?

        A tolerance of one cent, not zero: ``declared_value`` is 2dp and the line arithmetic is
        4dp × 2dp, so an exact-equality test would flag ordinary rounding. Anything wider than a
        cent is a real divergence — the detail page badges it **amber**, because a declared value
        that quietly disagrees with the goods it describes is a customs problem, not a display one.

        Note the line-less case reads as a match only when the declared value is zero. Document
        types that legitimately carry no lines (a BoL, an insurance certificate) will therefore
        report ``False``; the badge is gated on the document HAVING lines at the template, which is
        the right split — this property states the arithmetic fact, the page decides when the fact
        is worth showing.
        """
        return abs((self.declared_value or ZERO) - self.lines_total) <= Decimal("0.01")

    @property
    def is_editable(self):
        """A draft or an amendment may be edited; a filed instrument may not."""
        return self.status in self.EDITABLE_STATUSES

    @property
    def is_charging(self):
        """True when this document is currently consuming its licence's balance."""
        return self.status in self.CHARGING_STATUSES

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.status, "badge-muted")


class TradeDocumentLine(models.Model):
    """One declared line of a :class:`TradeDocument` — what it is, how much, and worth how much.

    Tenant-less child reached through ``document.tenant``, the ``PurchaseOrderLine`` /
    ``InvoiceLine`` precedent: it is a pure child of one parent, never listed or filtered on its
    own, edited through an inline formset, and so takes neither a ``tenant`` column nor routes of
    its own.
    """

    document = models.ForeignKey("scm.TradeDocument", on_delete=models.CASCADE, related_name="lines")
    # Nullable on purpose: a customs line legitimately describes something that is not in the item
    # master — a sample, a spare, packaging materials, a repaired unit going back.
    item = models.ForeignKey("scm.Item", on_delete=models.SET_NULL, null=True, blank=True,
                             related_name="trade_document_lines")

    # --- the snapshot block: what was DECLARED, frozen at line entry ------------------------------
    # Copied from the item (or typed) once and never rewritten. Editing the item master a year later
    # must not change what a filed document says — see the module docstring. There is deliberately
    # no save() override back-filling these from `item`: a helpful default here is exactly the bug
    # that turns a snapshot into a mirror.
    description = models.CharField(max_length=255,
                                   help_text="What the customs officer reads — required on every line")
    hs_code = models.CharField(max_length=20, blank=True,
                               help_text="HS/HTS classification AS DECLARED on this document")
    country_of_origin = models.CharField(max_length=64, blank=True)
    uom_text = models.CharField(max_length=20, blank=True,
                                help_text="The unit as printed on the form")
    # The live pointer, kept ALONGSIDE uom_text rather than instead of it, for the same reason.
    uom = models.ForeignKey("scm.UOM", on_delete=models.SET_NULL, null=True, blank=True,
                            related_name="trade_document_lines")

    quantity = models.DecimalField(max_digits=14, decimal_places=4, default=0,
                                   validators=[MinValueValidator(ZERO)])
    unit_value = models.DecimalField(max_digits=14, decimal_places=2, default=0,
                                     validators=[MinValueValidator(ZERO)])
    net_weight_kg = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
                                        validators=[MinValueValidator(ZERO)])

    class Meta:
        ordering = ["id"]
        indexes = [
            models.Index(fields=["document", "id"], name="scm_tdl_doc_idx"),
        ]

    def __str__(self):
        return f"{self.description} ×{self.quantity}"

    def clean(self):
        super().clean()

        # `description` is already non-blank at the field level; this catches the whitespace-only
        # value that passes clean_fields() and prints as an empty line on a customs form.
        if not (self.description or "").strip():
            raise ValidationError({"description": "Every declared line needs a description — it is what "
                                                  "the customs officer reads."})

        # The child has no tenant of its own, so the tenancy question is asked of the parent.
        # Defaulted getattr because `document` is non-nullable: an unsaved line built by the formset
        # before its parent exists would otherwise raise RelatedObjectDoesNotExist here.
        parent = getattr(self, "document", None)
        if parent is None or parent.tenant_id is None:
            return
        # The formset scopes these two selects by hand (TenantModelForm cannot scope a tenant-less
        # child), which is UX; this is the guard that holds against a crafted POST.
        for field in ("item", "uom"):
            if getattr(self, f"{field}_id", None) is None:
                continue
            related = getattr(self, field, None)
            if related is not None and related.tenant_id != parent.tenant_id:
                raise ValidationError({field: "That record belongs to another workspace."})

    # ---------------------------------------------------------------------------------------------
    # Derived — never a column, never editable.
    # ---------------------------------------------------------------------------------------------
    @property
    def line_value(self):
        """``quantity × unit_value``, quantized and clamped to what a (14, 2) column would hold.

        A stored line total is a column somebody can edit into disagreeing with its own two
        factors, and a filed customs document whose line values do not multiply out is worse than
        one with no totals at all.
        """
        return q2((self.quantity or ZERO) * (self.unit_value or ZERO))


#: The bare Incoterm codes, derived from the labelled pairs so the vocabulary ``clean()`` enforces
#: and the vocabulary the form offers can never disagree. It has to sit BELOW the class because it
#: reads a class attribute — the one module constant that cannot live at the top.
_INCOTERM_VALUES = tuple(value for value, _label in TradeDocument.INCOTERM_CHOICES)
