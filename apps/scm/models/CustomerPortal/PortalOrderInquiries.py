"""SCM 4.16 Customer Portal — PortalOrderInquiry, the order-context support ticket [PIQ-].

**Why this model is a WRAPPER and not a ticket.** "Where is my order?" is 25-40% of inbound support
volume in the surveyed literature, which is why the sub-module's *order tracking* bullet and its
*support requests* bullet are one design problem rather than two: the answer to a WISMO ticket is a
shipment, and a ticket that cannot name the shipment is a conversation nobody can close. So this row
carries the **supply-chain context and the outcome**, and nothing else — the conversation thread
(``crm.CaseComment.is_public``), the SLA clocks, ownership, CSAT and the public status token all
already exist on ``crm.Case``, built and tested in 1.4.

**Two alternatives were rejected, and the reasons are the design:**

* *Adding ``sales_order`` / ``shipment`` columns to ``crm.Case``.* A cross-app schema edit made from
  inside an SCM pass, and it puts SCM vocabulary permanently into CRM's model — every CRM agent form,
  admin and migration would then carry supply-chain fields that mean nothing to a CRM-only tenant.
* *A second ticket table with its own status, comments and SLA.* This is L29's one-ledger rule
  applied to the helpdesk: two ticket tables means two answers to "how many open tickets do we have",
  two SLA clocks that drift, and an internal note that is safe in one table and leaked in the other.

*(Precedent that SCM may FK into CRM: ``SalesOrder.source_quote → crm.Quote``,
``OrderManagement/SalesOrders.py``. The edge runs SCM → CRM and never back.)*

**The division of labour, stated once so no later pass re-litigates it.** CRM owns the case
lifecycle: status, priority, owner, the thread, the SLA timestamps and CSAT. SCM owns
:attr:`~PortalOrderInquiry.inquiry_type`, the four context pointers, the customer's requested
resolution and :attr:`~PortalOrderInquiry.outcome`. **Nothing here writes ``case.status``** — a
supply-chain outcome is not a helpdesk closure (we may have raised the RMA and still owe the customer
a reply), and an agent's queue is the agent's to manage.

**4.16 recomputes no SLA of its own.** :attr:`~PortalOrderInquiry.sla_state` reads
``case.is_response_overdue`` / ``case.is_resolution_overdue`` / ``case.first_response_due`` /
``case.resolution_due`` — all verified present on ``crm.Case`` at write time. A second breach
calculation would disagree with the CRM case list the first time a policy changed, and the customer
would be told two different things about the same ticket.

**``details`` and ``staff_notes`` are deliberately NOT fields.** The customer's own words live on
``Case.description`` and internal triage lives in ``CaseComment(is_public=False)``. A second copy of
either is a second thing to keep in sync and — for the internal one — a second place to leak a note
that was never meant to leave the building.

**Everything that decides an outcome is ``editable=False``**: ``outcome``, ``resolved_at``,
``return_authorization``, ``source`` and ``raised_by`` are written only by :meth:`open_for` and the
three workflow verbs, so no ModelForm can ever offer them and no crafted POST can set them (L22).
"""
from datetime import timedelta

from apps.scm.models._base import *  # noqa: F401,F403
# Not re-exported by `_base` (which carries `ValidationError` but not this), and named explicitly
# rather than assumed: `clean()` re-homes errors keyed on `editable=False` columns onto it, and that
# line runs only when validation actually fails — so a missing import would surface as a NameError
# on the error path, i.e. exactly where nobody is looking.
from django.core.exceptions import NON_FIELD_ERRORS
from apps.scm.models.CustomerPortal._choices import (
    CUSTOMER_STATUS_MAP,
    INQUIRY_OUTCOME_CHOICES,
    INQUIRY_OUTCOME_CSS,
    INQUIRY_SOURCE_CHOICES,
    INQUIRY_TYPE_CHOICES,
    INQUIRY_TYPE_CSS,
    ORDER_BOUND_INQUIRY_TYPES,
    REQUESTED_RESOLUTION_CHOICES,
)

#: ``Case.description`` is a TextField with no ceiling, so a hostile POST could park a megabyte in
#: it. The same cap ``crm.views…CustomerPortal.portal_case_create`` already applies to the customer
#: form, lifted here because :meth:`PortalOrderInquiry.open_for` is now the writer for BOTH the staff
#: and the portal paths and the bound must not depend on which one was used.
MAX_CASE_DESCRIPTION = 5000


class PortalOrderInquiry(TenantNumbered):
    """A support ticket that is **about a specific order, line, shipment or invoice** [PIQ-]."""

    NUMBER_PREFIX = "PIQ"

    #: ``inquiry_type`` -> ``crm.Case.TYPE_CHOICES``. Local to this model on purpose: it is read from
    #: exactly one direction (:meth:`open_for`, deriving the case type), and the ``_choices.py`` rule
    #: is that a one-directional vocabulary stays where it is used.
    #:
    #: The question it answers is "is this a fault report or an enquiry?", because that is the only
    #: distinction CRM's own vocabulary can carry. A *fault* is something we appear to have got wrong
    #: and somebody must investigate; a *question* asserts nothing is broken. ``return_request`` and
    #: ``reorder_request`` are neither — they are requests for an ACTION, and CRM's
    #: ``feature_request`` is about the product roadmap, so ``other`` is the truthful bucket rather
    #: than a mis-file that would pollute CRM's own type reporting.
    #:
    #: Read with ``.get(..., "other")`` — a type added to ``INQUIRY_TYPE_CHOICES`` without a line
    #: here degrades to ``other`` instead of raising in the middle of a customer's submission.
    CASE_TYPE_FOR_INQUIRY = {
        "wismo": "question",
        "delivery_exception": "problem",
        "short_shipment": "problem",
        "damaged": "problem",
        "wrong_item": "problem",
        "quality": "problem",
        "invoice_dispute": "problem",
        "return_request": "other",
        "reorder_request": "other",
        "product_question": "question",
        "other": "other",
    }

    #: The only kwargs :meth:`open_for` will accept through ``**context``. A whitelist rather than a
    #: bare ``cls(**context)``: without it, a caller (or a view that forwards ``request.POST`` a
    #: little too eagerly) could pass ``outcome="rejected"`` or ``return_authorization=…`` and walk
    #: straight past the ``editable=False`` guarantee those columns exist to provide.
    CONTEXT_FIELDS = (
        "inquiry_type", "requested_resolution", "quantity_affected",
        "sales_order", "sales_order_line", "shipment", "invoice",
    )

    #: What :meth:`resolve` may set. ``open`` is excluded because re-opening is :meth:`reopen`'s job
    #: and going through the resolve path would stamp ``resolved_at`` on a live inquiry.
    #: ``rma_raised`` is excluded because it is a claim about a DOCUMENT: an inquiry badged "RMA
    #: raised" with no ``return_authorization`` to click is a lie the list page repeats forever.
    #: Only :meth:`link_return`, which has the RMA in its hand, may set it.
    RESOLVABLE_OUTCOMES = tuple(
        value for value, _label in INQUIRY_OUTCOME_CHOICES if value not in ("open", "rma_raised"))

    #: How close a live SLA deadline has to be before :attr:`sla_state` calls it ``due_soon``. Four
    #: hours is a working half-day: long enough that the warning is actionable, short enough that the
    #: bucket does not swallow the whole open queue and stop meaning anything.
    SLA_DUE_SOON_HOURS = 4

    #: theme.css class per SLA bucket, decided here so the list badge and the detail badge cannot
    #: drift. Only the six colour-named classes that exist in ``static/css/theme.css`` (L33).
    SLA_STATE_CSS = {
        "breached": "badge-red",
        "due_soon": "badge-amber",
        "ok": "badge-green",
        "none": "badge-muted",
    }

    #: The FKs :meth:`clean` tenant-checks, table-driven so adding a pointer means adding it here
    #: rather than remembering to copy another if-block.
    #:
    #: ``sales_order_line`` is absent because it HAS no tenant column (a ``SalesOrderLine`` is reached
    #: through ``sales_order.tenant``, the scm child convention) — the parent-match guard below covers
    #: it completely. ``raised_by`` is absent because it is a ``User``, and the superuser's tenant is
    #: ``None`` by design: requiring equality there would refuse every row an admin filed.
    TENANT_SCOPED_FKS = (
        "case", "portal_account", "sales_order", "shipment", "invoice", "return_authorization")

    # --- the wrapped case -------------------------------------------------------------------------
    # CASCADE, unlike portal_account's PROTECT below, and the asymmetry is deliberate: without its
    # case this row has no thread, no SLA and no customer-visible conversation — it is not evidence
    # that can stand on its own, it is an orphaned annotation. editable=False keeps it out of every
    # ModelForm automatically rather than relying on each form to remember its own field list.
    case = models.ForeignKey(
        "crm.Case", on_delete=models.CASCADE, related_name="scm_portal_inquiries", editable=False,
        help_text="The crm.Case that carries the conversation, the SLA clocks, ownership and CSAT")
    # PROTECT: an inquiry is evidence, and the account must not vanish from under it because somebody
    # pressed delete once. The consequence is handled, not discovered — portalaccount_delete catches
    # ProtectedError and steers to is_active=False (the 4.13 precedent). Blank when a staff member
    # files an inquiry for a customer who has no portal account at all.
    portal_account = models.ForeignKey(
        "scm.PortalAccount", on_delete=models.PROTECT, null=True, blank=True,
        related_name="inquiries",
        help_text="The portal account this was raised under. Blank when staff file for a customer "
                  "who is not on the portal")

    # --- the supply-chain context -----------------------------------------------------------------
    # This block is the entire reason the model exists: it is what a plain crm.Case cannot say.
    # PROTECT on the order because the inquiry is an argument about that order and deleting the
    # subject of the argument silently is not a delete a user should be able to make by accident;
    # SET_NULL on the rest because they are corroborating detail — losing the shipment pointer
    # weakens the record, losing the order destroys it.
    sales_order = models.ForeignKey(
        "scm.SalesOrder", on_delete=models.PROTECT, null=True, blank=True,
        related_name="portal_inquiries", help_text="The order this is about")
    sales_order_line = models.ForeignKey(
        "scm.SalesOrderLine", on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
        help_text="The specific line, when the claim is about one item rather than the whole order")
    shipment = models.ForeignKey(
        "scm.Shipment", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="portal_inquiries", help_text="The shipment this is about, when known")
    invoice = models.ForeignKey(
        "accounting.Invoice", on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
        help_text="The disputed invoice. SCM computes no AR of its own — this is a READ-ONLY "
                  "pointer at 2.4's document")

    # --- what the customer reported, and what they asked for --------------------------------------
    inquiry_type = models.CharField(
        max_length=20, choices=INQUIRY_TYPE_CHOICES, default="wismo",
        help_text="What went wrong, or what is being asked. A closed set so 'which failure mode "
                  "drives our WISMO volume?' is a GROUP BY rather than a pile of free text")
    requested_resolution = models.CharField(
        max_length=16, choices=REQUESTED_RESOLUTION_CHOICES, default="information",
        help_text="What the customer wants done. Recorded separately from the type because 'my box "
                  "arrived damaged, just credit me' is a different job from the same damage with "
                  "'send another one', and an agent who has to infer it guesses wrong")
    quantity_affected = models.DecimalField(
        max_digits=14, decimal_places=4, null=True, blank=True, validators=[MinValueValidator(ZERO)],
        help_text="How many units the claim covers, for short-shipment and damage claims. Requires "
                  "a line, and may not exceed what that line ordered")

    # --- the outcome, written ONLY by the workflow verbs -------------------------------------------
    # editable=False across the board: an outcome a user picks out of a dropdown on an edit form is a
    # label, not an outcome. The verbs are what also stamp resolved_at and return the audit diff, so
    # routing everything through them is what keeps those three columns consistent with each other.
    outcome = models.CharField(
        max_length=24, choices=INQUIRY_OUTCOME_CHOICES, default="open", editable=False)
    resolved_at = models.DateTimeField(null=True, blank=True, editable=False)
    # Points at 4.10's EXISTING return document. 4.16 builds no second RMA and the customer-facing
    # request routes to 4.10's existing scm:portal_return_create — a second returns document would be
    # a second place for a credit to come from.
    return_authorization = models.ForeignKey(
        "scm.ReturnAuthorization", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="portal_inquiries", editable=False,
        help_text="Set only by the conversion verb, never typed")

    # --- provenance --------------------------------------------------------------------------------
    # Forced server-side by whichever view filed the row. This figure is the denominator of every
    # self-service / deflection claim the module makes, so a provenance a user can type is not one.
    source = models.CharField(
        max_length=10, choices=INQUIRY_SOURCE_CHOICES, default="staff", editable=False)
    raised_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="+", editable=False)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            # The list page opens on outcome (the default filter is "open") and the type breakdown is
            # the sub-module's headline chart; the order and case indexes serve the two joins —
            # "every inquiry about this order" on the order-tracking report, and the reverse walk
            # from a CRM case back to its supply-chain context.
            models.Index(fields=["tenant", "outcome"], name="scm_piq_tnt_outcome_idx"),
            models.Index(fields=["tenant", "inquiry_type"], name="scm_piq_tnt_type_idx"),
            models.Index(fields=["tenant", "sales_order"], name="scm_piq_tnt_so_idx"),
            models.Index(fields=["tenant", "case"], name="scm_piq_tnt_case_idx"),
            # The staff list's ORDER BY (``-created_at, -id`` with only ``tenant`` guaranteed) —
            # none of the four indexes above carries a date column, so the sort was a filesort.
            models.Index(fields=["tenant", "created_at"], name="scm_piq_tnt_at_idx"),
            # `(tenant, portal_account)` was missing while THREE hot queries correlate on exactly
            # that pair: the account list's open-inquiry `Subquery` and its `has_inquiries`
            # `Exists`, both evaluated ONCE PER ROW of that list, and the account detail panel.
            # They were falling back to the bare `portal_account_id` FK index, which carries no
            # tenant and therefore cannot serve the correlated pair.
            models.Index(fields=["tenant", "portal_account"], name="scm_piq_tnt_acct_idx"),
        ]

    def __str__(self):
        return f"{self.number or 'PIQ'} · {self.get_inquiry_type_display()}"

    # ---------------------------------------------------------------------------------------------
    # Validation
    # ---------------------------------------------------------------------------------------------
    def clean(self):
        """The cross-tenant guard, the "this type actually needs that pointer" matrix, and the
        mismatched-child guards that stop an inquiry pointing at another order's line or parcel."""
        super().clean()

        # THE GUARD. The forms scope every dropdown to the tenant, but that is UX — a narrowed
        # dropdown has never held against a crafted POST. Skipped when the instance has no tenant
        # yet: an unsaved row has tenant_id None and ``self.tenant`` would raise
        # RelatedObjectDoesNotExist on a non-nullable FK rather than return None.
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

        errors = {}

        # (a) The order-bound types. A WISMO ticket with no order attached is a question nobody can
        #     answer and a row that can never join to a shipment — which defeats the entire point of
        #     wrapping the case in supply-chain context. The set lives in _choices.py so this rule,
        #     the customer form's required-field hinting and any future triage rule branch on one
        #     tuple.
        if self.inquiry_type in ORDER_BOUND_INQUIRY_TYPES and self.sales_order_id is None:
            errors["sales_order"] = (
                f"A '{self.get_inquiry_type_display()}' inquiry is about a specific order — pick "
                "one, or change the type.")

        # (b) The invoice-dispute rule, the same shape for the money side. Disputing "an invoice" in
        #     general is not something AR can act on.
        if self.inquiry_type == "invoice_dispute" and self.invoice_id is None:
            errors["invoice"] = "An invoice dispute has to name the invoice being disputed."

        # (c) THE MISMATCHED-CHILD GUARD. Written as an unconditional comparison rather than an
        #     "if both are set" pair, because a SalesOrderLine ALWAYS has a parent: a line attached
        #     to an inquiry with no order is just as wrong as a line from a different order, and one
        #     comparison catches both. Without this a short-shipment claim can quote a quantity
        #     against another customer's line.
        if self.sales_order_line_id is not None:
            line = getattr(self, "sales_order_line", None)
            if line is not None and line.sales_order_id != self.sales_order_id:
                errors["sales_order_line"] = "That line belongs to a different order."

        # (d) The same guard for the parcel. A shipment carrying no order pointer at all fails this
        #     too, and deliberately: attaching it would assert "this parcel is part of that order"
        #     with nothing in the data supporting the claim, which is exactly what the guard exists
        #     to prevent. Only checked when the inquiry names an order — an order-less inquiry
        #     (a quality question about goods already delivered) may still name the shipment.
        if self.shipment_id is not None and self.sales_order_id is not None:
            shipment = getattr(self, "shipment", None)
            if shipment is not None and shipment.sales_order_id != self.sales_order_id:
                errors["shipment"] = (
                    "That shipment isn't linked to this order — pick a shipment of the order named "
                    "above, or clear the order.")

        # (e) The claimed quantity. It needs a line to be a quantity OF something, and it may not
        #     exceed what was ordered: a claim for more units than we sold is a credit note waiting
        #     to be written for goods that never existed. Skipped when (c) already failed, so the
        #     user sees the real problem instead of an arithmetic complaint about a bad pairing.
        if self.quantity_affected is not None and "sales_order_line" not in errors:
            if self.sales_order_line_id is None:
                errors["quantity_affected"] = (
                    "Pick the order line first — a quantity has to be a quantity of something.")
            else:
                line = getattr(self, "sales_order_line", None)
                ordered = getattr(line, "quantity_ordered", None) if line is not None else None
                if ordered is not None and self.quantity_affected > ordered:
                    errors["quantity_affected"] = (
                        f"That line only ordered {ordered}. A claim can't cover more units than "
                        "were sold.")

        # (e) THE COUNTERPARTY RULE. Same tenant is NOT the same customer.
        #
        # Everything above proves the FKs belong to this workspace and that the line/shipment belong
        # to the named order. None of it proved they belong to the customer whose portal this
        # inquiry is filed under — and the staff form's `sales_order` queryset is tenant-wide, so a
        # POST naming Acme's portal account and Contoso's order validated cleanly. The consequence
        # is not abstract: `portal_home` filters `recent_inquiries` on `portal_account` alone, so
        # Acme's own portal page would render Contoso's order number, and the wrapped `crm.Case`
        # would put whatever staff typed onto Acme's thread.
        #
        # `PortalDocumentShare.clean()` already enforces exactly this rule for its six pointers, and
        # `link_return()` enforces it for the RMA — the context FKs were simply the ones left out.
        #
        # Keyed on the field names the STAFF form declares. `invoice` is in FORM_INVISIBLE below, so
        # a customer-form submission re-homes rather than raising ValueError.
        account = getattr(self, "portal_account", None)
        owner_id = getattr(account, "customer_id", None) if account is not None else None
        if owner_id is not None:
            for name, path in (("sales_order", "customer_id"),
                               ("shipment", "sales_order.customer_id"),
                               ("invoice", "party_id")):
                if getattr(self, f"{name}_id", None) is None or name in errors:
                    continue
                found = getattr(self, name, None)
                for part in path.split("."):
                    found = getattr(found, part, None)
                    if found is None:
                        break
                # `None` means the target names no customer at all (a shipment with no order). That
                # is not a mismatch and is left alone — the order-bound `clean()` rules above already
                # decide which types may arrive without an order.
                if found is not None and found != owner_id:
                    errors[name] = (
                        f"That record belongs to a different customer — an inquiry filed under "
                        f"{account.customer}'s portal account may only name {account.customer}'s "
                        f"own documents.")

        # RE-HOME any error keyed on a column no ModelForm can declare.
        #
        # `case`, `return_authorization`, `outcome`, `source` and `raised_by` are all
        # `editable=False`, so Django omits them from every ModelForm — and `_post_clean` forwards a
        # model `ValidationError` straight to `form.add_error(<key>)`, which raises `ValueError` on
        # a field the form does not have. That turns a validation failure into a **500**, and it
        # already did once in this sub-module: the customer inquiry form offered `invoice_dispute`
        # while deliberately having no `invoice` picker, so `clean()`'s `{"invoice": …}` crashed the
        # page instead of rendering a message.
        #
        # `invoice` is in the list because it is genuinely absent from `PortalInquiryCustomerForm`
        # (that form now also drops the choice that requires it, which is the primary fix — this is
        # the backstop for any future form with a narrower field set).
        #
        # Moving the message to NON_FIELD_ERRORS keeps it visible and keeps the row un-saveable,
        # which is the correct outcome; losing the field anchor is a far smaller cost than a 500.
        FORM_INVISIBLE = ("case", "return_authorization", "outcome", "resolved_at", "source",
                          "raised_by", "invoice")
        homeless = []
        for name in FORM_INVISIBLE:
            if name in errors:
                message = errors.pop(name)
                homeless.extend(message if isinstance(message, list) else [message])
        if homeless:
            existing = errors.get(NON_FIELD_ERRORS, [])
            errors[NON_FIELD_ERRORS] = (
                (existing if isinstance(existing, list) else [existing]) + homeless)

        if errors:
            raise ValidationError(errors)

    # ---------------------------------------------------------------------------------------------
    # Creation — the SINGLE writer of the crm.Case
    # ---------------------------------------------------------------------------------------------
    @staticmethod
    def _actor(user):
        """A saveable user or None — the views are ``@login_required``, but an ``AnonymousUser``
        handed in by a management command would otherwise raise on assignment rather than simply
        going unattributed."""
        return user if getattr(user, "pk", None) else None

    @classmethod
    def open_for(cls, *, tenant, portal_account, subject, description, user, source, **context):
        """Open an inquiry **and its ``crm.Case``**, atomically. The only place a case is created.

        This is ``crm.views…CustomerPortal.portal_case_create``'s shape forced server-side: the
        origin, the account party and the case type are DERIVED here, never accepted from a caller,
        so a portal user cannot file against another customer and a staff console cannot invent a
        case type. It lives on the model rather than in a view helper because the staff create, the
        portal create and the seeder must all get the identical rule — a second copy is a rule that
        drifts, and this one decides who a ticket belongs to.

        **Why the transaction.** :meth:`clean` runs (through ``full_clean``) *after* the case exists,
        because the inquiry cannot be validated until it has the ``case`` its non-null FK requires.
        A validation failure inside the atomic block therefore rolls the case back; without it, every
        rejected submission would leave an orphaned, customer-visible ticket in the CRM queue.

        **The SLA policy is resolved HERE, not by ``Case.save()``.** Checked at write time against
        ``apps/crm/models/CustomerService/Cases.py``: ``save()`` computes ``first_response_due`` /
        ``resolution_due`` *from* a policy that is already set (``if self.sla_policy_id and …``) but
        never selects the tenant's default one. The CRM portal view does that lookup itself, so this
        does too — otherwise every portal ticket would land with no SLA clock at all.

        ``**context`` is whitelisted to :attr:`CONTEXT_FIELDS`: an unknown key is a ``TypeError``
        rather than a silently-ignored kwarg, and — the point of the whitelist — no caller can reach
        ``outcome`` / ``return_authorization`` / ``case`` through it.
        """
        # Local import, at call time: apps/scm does not import apps/crm at module scope (the
        # ReturnsManagement/Reports.py precedent). The dependency is real but it stays an edge one
        # function deep, so neither app's model layer can import-cycle the other's.
        from apps.crm.models import Case, SlaPolicy

        unknown = sorted(set(context) - set(cls.CONTEXT_FIELDS))
        if unknown:
            raise TypeError(
                f"open_for() got unexpected context {unknown!r}. Only {list(cls.CONTEXT_FIELDS)} "
                "may be passed — the outcome columns are workflow-controlled.")
        if source not in dict(INQUIRY_SOURCE_CHOICES):
            raise ValidationError({"source": "Unknown inquiry source."})

        subject = (subject or "").strip()[:255]
        if not subject:
            raise ValidationError({"subject": "A subject is required."})

        # Built first, unsaved, so the case type can be derived from the type the caller actually
        # asked for — or from the field's own default when they did not pass one.
        inquiry = cls(tenant=tenant, portal_account=portal_account, source=source,
                      raised_by=cls._actor(user), **context)

        # The party the case belongs to, resolved server-side. The portal account is the truth when
        # there is one; a staff-filed inquiry for a customer who is not on the portal falls back to
        # the order's customer, because a case attached to nobody is invisible on every account page
        # that would need it. Never taken from the caller.
        party = portal_account.customer if portal_account is not None else None
        if party is None and inquiry.sales_order_id is not None:
            party = inquiry.sales_order.customer

        default_sla = SlaPolicy.objects.filter(
            tenant=tenant, is_default=True, is_active=True).first()

        with transaction.atomic():
            case = Case.objects.create(
                tenant=tenant,
                subject=subject,
                description=(description or "").strip()[:MAX_CASE_DESCRIPTION],
                # origin is "portal" for BOTH sources: it records the CHANNEL — this is the portal's
                # order-context queue — while ``source`` records whether the customer or an agent
                # typed it. CRM's origin vocabulary has no better value, and picking "phone" for a
                # staff-filed row would be a guess written into someone else's reporting.
                origin="portal",
                status="new",
                type=cls.CASE_TYPE_FOR_INQUIRY.get(inquiry.inquiry_type, "other"),
                account=party,
                sla_policy=default_sla,
            )
            inquiry.case = case
            # exclude=["number"]: TenantNumbered assigns it inside save(), so it is still blank here
            # and a non-blank CharField would fail validation on every single create (the seeder's
            # established idiom). Excluding it also skips the ("tenant", "number") unique check,
            # which is exactly right for a number that does not exist yet.
            inquiry.full_clean(exclude=["number"])
            inquiry.save()
        return inquiry

    # ---------------------------------------------------------------------------------------------
    # Workflow — the ONLY writers of outcome / resolved_at / return_authorization
    # ---------------------------------------------------------------------------------------------
    # Each returns the ``{field: [before, after]}`` audit diff, or ``{}`` when nothing changed, so the
    # views stay thin and the seeder and the tests drive the code path the buttons drive
    # (the SupplyChainAlert precedent). A wrong VALUE raises; a wrong STATE is a silent no-op —
    # only the first is the caller's mistake.
    #
    # None of them touches ``case.status``. See the module docstring: CRM owns the case lifecycle,
    # and "we've raised the RMA" is not the same statement as "this conversation is over".

    def _comment(self, user, body, *, is_public):
        """Append a ``crm.CaseComment`` to the wrapped case. No-op on an empty body.

        Local CRM import for the same reason :meth:`open_for` uses one. ``author_name`` is snapshotted
        because ``CaseComment.author`` is SET_NULL — a deactivated agent must not silently un-sign a
        reply the customer has already read.
        """
        body = (body or "").strip()
        if not body:
            return
        from apps.crm.models import CaseComment
        actor = self._actor(user)
        CaseComment.objects.create(
            tenant_id=self.tenant_id, case_id=self.case_id, author=actor,
            author_name=(actor.get_full_name() or actor.username) if actor else "",
            body=body, is_public=is_public)

    def resolve(self, user, outcome, note=""):
        """Close the inquiry with an ``outcome``, optionally replying to the customer.

        Refuses a second resolution: the first resolver's answer is the one the customer was given,
        and letting a later press blank ``resolved_at`` would make "how long did we take?"
        unanswerable. Re-opening first is the supported way to change an answer.

        ``note``, when given, becomes a **public** ``CaseComment`` — the customer asked a question
        and this is the reply, so it goes in the thread they can actually read rather than into a
        column only staff ever open. It is also where the resolver's name is recorded: there is no
        ``resolved_by`` column, because the comment signs itself and ``core.AuditLog`` already
        answers "who pressed the button" for the rows with no note.
        """
        if outcome not in self.RESOLVABLE_OUTCOMES:
            raise ValidationError({"outcome": (
                "Pick how this inquiry ended. 'RMA raised' is set by raising the return itself, so "
                "the badge always has a document behind it.")})
        if not self.is_open:
            return {}
        changes = {"outcome": [self.outcome, outcome]}
        self.outcome = outcome
        self.resolved_at = timezone.now()
        self.save(update_fields=["outcome", "resolved_at", "updated_at"])
        self._comment(user, note, is_public=True)
        return changes

    def reopen(self, user):
        """Put a resolved inquiry back in the queue. No-op when it is already open.

        ``return_authorization`` is deliberately LEFT IN PLACE: the RMA is a document that exists in
        the world, and re-opening the conversation about it does not un-raise it. Only the outcome
        and the resolution timestamp are rolled back.

        ``user`` is accepted for symmetry with the other two verbs and is recorded by the view's
        ``write_audit_log``. There is no ``reopened_by`` column on purpose — it would be null on
        almost every row, would still only remember the LAST reopen, and the audit trail already
        holds the whole sequence.
        """
        if self.is_open:
            return {}
        changes = {"outcome": [self.outcome, "open"]}
        self.outcome = "open"
        self.resolved_at = None
        self.save(update_fields=["outcome", "resolved_at", "updated_at"])
        return changes

    def link_return(self, rma, user):
        """Attach 4.10's ``ReturnAuthorization`` and record the outcome as ``rma_raised``.

        The conversion verb — and the ONLY writer of ``return_authorization``, which is why
        ``rma_raised`` is not in :attr:`RESOLVABLE_OUTCOMES`.

        **It refuses a cross-tenant or cross-customer RMA, and that is an authorisation rule rather
        than a typo check**: linking another customer's return here would publish that return's
        number, dates and disposition on this customer's portal inquiry. The form's queryset is
        scoped too, but a narrowed dropdown has never held against a crafted POST, so the refusal
        lives where the write happens.

        Re-linking a DIFFERENT return is allowed — an agent correcting a mis-link is a real event and
        the audit diff records what it replaced. Re-linking the same one is a no-op.
        """
        if rma is None:
            raise ValidationError({"return_authorization": "Pick a return authorisation."})
        if rma.tenant_id != self.tenant_id:
            raise ValidationError({"return_authorization": "That return belongs to another workspace."})
        customer = self.customer
        if customer is not None and rma.customer_id != customer.pk:
            raise ValidationError({"return_authorization": (
                f"{rma.number} belongs to a different customer — a return can only be linked to an "
                "inquiry from the customer who raised it.")})
        if self.return_authorization_id == rma.pk and self.outcome == "rma_raised":
            return {}
        changes = {
            "return_authorization": [str(self.return_authorization or ""), str(rma)],
            "outcome": [self.outcome, "rma_raised"],
        }
        self.return_authorization = rma
        self.outcome = "rma_raised"
        self.resolved_at = self.resolved_at or timezone.now()
        self.save(update_fields=["return_authorization", "outcome", "resolved_at", "updated_at"])
        return changes

    # ---------------------------------------------------------------------------------------------
    # Derived — nothing below is stored
    # ---------------------------------------------------------------------------------------------
    @property
    def is_open(self):
        return self.outcome == "open"

    @property
    def customer(self):
        """The party this inquiry is about — the portal account's customer, else the order's.

        Derived rather than stored so it can never disagree with the two rows it is read from. It is
        what :meth:`link_return` checks an RMA against, and what the detail page titles itself with;
        ``None`` when a staff member filed a general inquiry with neither pointer set, and every
        caller must treat that as "unknown", never as "matches anything".
        """
        if self.portal_account_id is not None:
            return getattr(self.portal_account, "customer", None)
        if self.sales_order_id is not None:
            return getattr(self.sales_order, "customer", None)
        return None

    @property
    def age_days(self):
        """Whole days since it was raised — for an open inquiry, how long the customer has waited.

        Counted from ``created_at`` and never frozen at resolution: an inquiry answered on day nine
        should keep saying nine. ``None`` on an unsaved instance, where ``auto_now_add`` has not
        fired yet.
        """
        if self.created_at is None:
            return None
        end = self.resolved_at if (self.resolved_at and not self.is_open) else timezone.now()
        return max((end - self.created_at).days, 0)

    @property
    def sla_state(self):
        """``breached`` / ``due_soon`` / ``ok`` / ``none``, read off the wrapped case.

        **4.16 recomputes no SLA.** The breach test is ``crm.Case``'s own
        ``is_response_overdue`` / ``is_resolution_overdue`` — both of which already encode "and the
        case is still open" — so a policy change moves the CRM case list and this badge together, by
        construction rather than by discipline.

        ``none`` means nobody promised anything (no policy resolved when the case was opened), and it
        is deliberately distinct from ``ok``: a case with no SLA is not a case that is meeting one.
        """
        case = self.case if self.case_id else None
        if case is None:
            return "none"
        if case.first_response_due is None and case.resolution_due is None:
            return "none"
        if case.is_response_overdue or case.is_resolution_overdue:
            return "breached"
        if not case.is_open:
            return "ok"
        # The nearest deadline still to be met. A first response already given stops counting — the
        # clock it belonged to has been stopped, and re-warning about it would send agents chasing
        # work that is done.
        deadlines = [d for d in (
            case.first_response_due if case.first_responded_at is None else None,
            case.resolution_due,
        ) if d is not None]
        if deadlines:
            due = min(deadlines)
            if due - timezone.now() <= timedelta(hours=self.SLA_DUE_SOON_HOURS):
                return "due_soon"
        return "ok"

    @property
    def sla_state_css(self):
        return self.SLA_STATE_CSS.get(self.sla_state, "badge-muted")

    @property
    def customer_status(self):
        """``(label, badge class)`` for the CUSTOMER-facing status — a presentation map over
        ``case.status``, never a column.

        The customer's vocabulary is deliberately not the agent's: Zendesk documents outright that
        its portal statuses differ from its agent statuses, and the three triage states
        ``new`` / ``open`` / ``in_progress`` collapse to one customer word here because which of them
        a ticket sits in is a fact about *our* queue. ``.get`` with an explicit fallback, so a
        seventh ``crm.Case`` status added later renders as "In progress" instead of blanking the
        badge — and so nobody is tempted to spell a label inline in a template.
        """
        return CUSTOMER_STATUS_MAP.get(
            getattr(self.case, "status", None) if self.case_id else None,
            CUSTOMER_STATUS_MAP["open"])

    @property
    def customer_status_label(self):
        """So a template never has to subscript a tuple."""
        return self.customer_status[0]

    @property
    def customer_status_css(self):
        return self.customer_status[1]

    @property
    def inquiry_type_css(self):
        """theme.css badge class for :attr:`inquiry_type` — one lookup, so no template invents a
        colour and the list and detail badges cannot drift."""
        return INQUIRY_TYPE_CSS.get(self.inquiry_type, "badge-muted")

    @property
    def outcome_css(self):
        return INQUIRY_OUTCOME_CSS.get(self.outcome, "badge-muted")
