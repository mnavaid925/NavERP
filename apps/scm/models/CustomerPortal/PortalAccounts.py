"""SCM 4.16 Customer Portal — PortalAccount, the account-level entitlement record [PAC-].

One row per customer ``core.Party``: what that customer's portal shows them, how much of the live
stock figure they may read, which documents and financials they are entitled to, and where they
would prefer to be told about a shipment. It is the ROOT of the sub-module — ``PortalOrderInquiry``,
``PortalDocumentShare`` and ``PortalActivity`` all point back at it — and it is the row the staff
enablement console exists to manage.

**It is NOT a login, and 4.16 does not build one.** Users bind to a customer through the already
shipped ``crm.CustomerPortalAccess``, whose ``portal_user`` is a ``OneToOneField`` on the user model
(``apps/crm/models/CustomerService/CustomerPortalAccess.py``). Every gated portal page resolves
``user -> CustomerPortalAccess (active) -> customer_party -> PortalAccount (active)`` and **refuses
at each step**, so a customer with no ``PortalAccount`` row simply has no portal: enablement is an
explicit per-customer opt-in, which is exactly what makes the staff console meaningful.

A second, SCM-side login binding was considered and rejected. Two bindings can *disagree about which
party a user is* — CRM says this login belongs to Acme, SCM says Contoso — and there is no
tie-breaker that is anything other than a guess. Whichever one a given page happened to read would
decide whose orders, invoices and PODs that user saw. That is not a data-quality problem to reconcile
later; it is an authorisation bug by construction, so the second binding is never created.

**Deliberately NOT a field: ``visibility_scope`` (``company`` vs ``own``).** A "buyers see only their
own orders" switch would need a portal originator on ``SalesOrder``, and 4.5 records none — the
column does not exist and 4.16 may not add one to another sub-module's table. Offering the switch
anyway would ship a control that silently does nothing, which is worse than not offering it: an
administrator who sets it believes their buyers are separated when they are not. Company-wide
visibility is the only faithful v1 (and is Zendesk's organization-requests default). Carried forward
as a documented gap, not quietly dropped.

**The notification preferences store intent and dispatch nothing.** ``notify_on_*`` and
``preferred_channel`` are the same posture ``SalesOrder.confirmation_sent_at`` /
``shipped_notification_at`` / ``delivered_notification_at`` have held unfired since 4.5: record the
fact, leave the integration to the module that owns messaging. Capturing the preference now means
that on the day a mailer exists it reads a column carrying real customer intent instead of defaulting
everyone to email. **Do not read these as a promise that a message goes out, and do not invent a
mailer here.**

**Prices and stock are projections, never stored on this row.** ``price_basis="last_ordered"`` is
resolved at render time from the customer's own most recent ``SalesOrderLine.unit_price``, because
there is no customer price master on the SCM side and a stored copy would quietly become a quote we
never agreed to (a real price engine is 9.3). Stock likewise: whatever ``stock_display`` chooses, the
number behind it is derived over the append-only ``StockMove`` ledger (L37). This model configures
the *rendering* of both figures and is the source of neither.

**Note on layout, so no review agent "fixes" it:** the backend package is ``CustomerPortal/``
(PascalCase of the NavERP.md title) while the templates live in ``templates/scm/portal/`` (the short
slug every other scm template folder uses). The asymmetry is the house rule, not a defect.
"""
from apps.scm.models._base import *  # noqa: F401,F403
# BY NAME, never `import *` — `apps/scm/models/__init__.py` already star-imports 4.12's and 4.13's
# `_choices`, so a third star-import could silently shadow a shared token with the winner decided by
# import order. `_choices.py` imports nothing at all (not even `_base`), so the dependency edge
# inside 4.16 only ever runs one way and no cycle is possible.
from apps.scm.models.CustomerPortal._choices import (
    CATALOG_SCOPE_CHOICES,
    PREFERRED_CHANNEL_CHOICES,
    PRICE_BASIS_CHOICES,
    STOCK_DISPLAY_CHOICES,
    THRESHOLD_STOCK_DISPLAYS,
)


class PortalAccount(TenantNumbered):
    """One customer's portal configuration and entitlements [PAC-]. Not a login — see the module
    docstring for why the login binding stays in ``crm.CustomerPortalAccess``."""

    NUMBER_PREFIX = "PAC"

    #: The whole row is staff configuration, so the form takes everything EXCEPT the system columns
    #: (``tenant`` / ``number`` / ``activated_on`` / ``created_at`` / ``updated_at``). Recorded here
    #: rather than only in the form so the intent survives someone reading the model alone: there is
    #: no hidden lifecycle on this model and no verb that owns a field — this row IS the config.
    #:
    #: One exception is enforced by the field itself: :attr:`activated_on` is ``editable=False``
    #: because it is evidence of when enablement first happened, not a date anybody may choose.

    # --- who this account is for -----------------------------------------------------------------
    # PROTECT, not CASCADE: the account carries entitlements, an activity trail and (through
    # PortalDocumentShare) a record of what left the building. Deleting the customer party must not
    # take that evidence with it in one click — the customer is archived, the trail stays readable.
    customer = models.ForeignKey(
        "core.Party", on_delete=models.PROTECT, related_name="scm_portal_accounts",
        help_text="The company this portal account belongs to. Several named users may bind to it "
                  "through their CRM customer portal access — this is the COMPANY-level record")

    is_active = models.BooleanField(
        default=True,
        help_text="Switch a customer's portal off here. Deactivating is the safe alternative to "
                  "deleting: inquiries and document shares reference this row and would block it")
    # Stamped ONCE in save(), the first time this account is active, and never restamped — a
    # deactivate/reactivate cycle must not rewrite the adoption date, because "when did this customer
    # first get the portal?" is the question the enablement console is built to answer. editable=False
    # keeps it off every ModelForm automatically rather than relying on each form's field list (L22).
    activated_on = models.DateField(null=True, blank=True, editable=False)

    # --- entitlements ----------------------------------------------------------------------------
    # Per-buyer permissions are the surveyed norm (Sana access rights, Shopify permission levels, Oro
    # buyer roles, Salesforce permission sets). Booleans rather than a role table on purpose: there is
    # exactly one audience per row, so a join would add a table without adding an answer.
    #
    # Five default TRUE because they are read-only views of the customer's own documents, and the
    # sixth defaults FALSE because it is money: an aggregate balance and credit position is the one
    # thing on the portal an administrator must consciously decide to expose.
    can_track_shipments = models.BooleanField(
        default=True, help_text="Order tracking, shipment status and proof of delivery")
    can_view_invoices = models.BooleanField(
        default=True, help_text="Read-only invoice history. SCM computes no AR of its own — these "
                                "are accounting's invoices, shown, never recalculated")
    can_view_documents = models.BooleanField(
        default=True, help_text="The document library — only ever documents shared to THIS account")
    can_raise_inquiries = models.BooleanField(
        default=True, help_text="Raise an order inquiry from the portal (opens a CRM case)")
    can_request_returns = models.BooleanField(
        default=True, help_text="Routes to 4.10's existing customer return request — 4.16 builds no "
                                "second returns flow")
    show_credit_and_balance = models.BooleanField(
        default=False,
        help_text="OFF by default: outstanding balance, credit limit and payment terms are exposed "
                  "only when someone deliberately turns them on")

    # --- stock presentation ----------------------------------------------------------------------
    stock_display = models.CharField(
        max_length=20, choices=STOCK_DISPLAY_CHOICES, default="availability_text",
        help_text="How much of the live stock figure this customer may see. The reason to hide a "
                  "number is commercial, and it varies by who is looking — hence per account")
    low_stock_threshold = models.DecimalField(
        max_digits=14, decimal_places=4, default=ZERO, validators=[MinValueValidator(ZERO)],
        help_text="At or below this quantity the catalog says 'low stock'. Only meaningful for the "
                  "availability-text and colour-band displays")
    show_by_location = models.BooleanField(
        default=False,
        help_text="Break availability down by warehouse instead of one network figure. Off by "
                  "default — a per-site breakdown tells a competitor where our stock sits")

    # --- catalog scope ---------------------------------------------------------------------------
    catalog_scope = models.CharField(
        max_length=20, choices=CATALOG_SCOPE_CHOICES, default="all_active",
        help_text="Which items this customer's catalog contains")
    # blank=True because two of the three scopes need no categories at all. The "categories scope
    # needs at least one category" rule is NOT here — see clean() for why it cannot be.
    catalog_categories = models.ManyToManyField(
        "scm.ItemCategory", blank=True, related_name="portal_accounts",
        help_text="Used only when the scope is 'Selected categories only'")

    # --- pricing ---------------------------------------------------------------------------------
    price_basis = models.CharField(
        max_length=16, choices=PRICE_BASIS_CHOICES, default="hidden",
        help_text="'Last ordered' shows this customer's own most recent unit price for the item, "
                  "derived at render time. There is no customer price master to price against yet")

    # --- shipping default ------------------------------------------------------------------------
    # SET_NULL: an address is reference data and deleting one must not delete the portal account that
    # happened to default to it. related_name="+" — nothing ever asks an address for its portal
    # accounts, and core.Address is FK'd from several apps already.
    #
    # core.Address carries `kind` / `line1` / `city` / `country` and NO postal-code field (verified,
    # and already documented at 4.10). No form label, help text or template here may imply one exists
    # — in particular, an address is not enough to prove who a caller is.
    default_ship_to = models.ForeignKey(
        "core.Address", on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
        help_text="Pre-selected delivery address for this customer. Must be one of their own "
                  "addresses")

    # --- notification preferences (DATA ONLY — 4.16 dispatches nothing) --------------------------
    notify_on_shipment = models.BooleanField(
        default=True, help_text="Preference only — no message is sent by this module")
    notify_on_delivery = models.BooleanField(
        default=True, help_text="Preference only — no message is sent by this module")
    notify_on_exception = models.BooleanField(
        default=True, help_text="Preference only — no message is sent by this module")
    preferred_channel = models.CharField(
        max_length=8, choices=PREFERRED_CHANNEL_CHOICES, default="email",
        help_text="Where this customer would prefer to hear about shipment events. Stored intent "
                  "for the day a mailer exists — nothing is dispatched today")

    # --- presentation extras ---------------------------------------------------------------------
    welcome_message = models.TextField(
        blank=True, help_text="Shown on this customer's portal home page — a dealer-zone style "
                              "announcement or greeting")
    support_email = models.EmailField(
        blank=True, help_text="The address the portal tells this customer to contact. Blank falls "
                              "back to the tenant's own support routing")
    notes = models.TextField(blank=True, help_text="Internal — never rendered on a customer page")

    class Meta:
        ordering = ["-created_at"]
        # Two pairs. ("tenant", "number") is the house auto-number guarantee that TenantNumbered's
        # retry loop relies on; ("tenant", "customer") is the real business rule — ONE portal
        # configuration per customer. Without it a second row could hand the same company a different
        # set of entitlements, and which one applied would depend on row order, i.e. on luck.
        unique_together = (("tenant", "number"), ("tenant", "customer"))
        indexes = [
            # The enablement console opens on active accounts, and every derived count on the staff
            # pages ("how many customers are live?") filters the same pair.
            models.Index(fields=["tenant", "is_active"], name="scm_pac_tnt_active_idx"),
            # The hot path of the whole sub-module: every gated portal request resolves
            # customer_party -> PortalAccount on exactly this pair, once per page load.
            models.Index(fields=["tenant", "customer"], name="scm_pac_tnt_cust_idx"),
        ]

    def __str__(self):
        return f"{self.number} · {self.customer}"

    # ---------------------------------------------------------------------------------------------
    # Validation
    # ---------------------------------------------------------------------------------------------
    def clean(self):
        """The ship-to ownership guard and the "this setting can actually take effect" contract.

        **What is deliberately NOT checked here: the ``catalog_scope == "categories"`` -> at least
        one category rule.** ``catalog_categories`` is a ManyToMany, and a many-to-many has no rows
        until *after* ``save()`` — on create the instance has no pk to hang them on, so a model-level
        check would see an empty set for every new account and reject configurations that are
        perfectly valid. It is unenforceable here, not merely inconvenient. The rule therefore lives
        in ``PortalAccountForm.clean()``, where the submitted category ids are available before
        anything is written. **Do not "fix" it back into this method** — it will look like it works
        on edit and silently block every create.
        """
        super().clean()
        errors = {}

        # (a) THE OWNERSHIP GUARD. A ship-to belonging to another party is not a typo — it is a
        #     delivery address for someone else's company sitting on this customer's portal, and it
        #     would be pre-selected on anything that reads the default. The form's queryset is
        #     already scoped to tenant + customer, but a narrowed dropdown is UX and has never held
        #     against a crafted POST (L39 §2), so the rule is enforced on the model as well.
        #
        #     Skipped when the row has no tenant yet: an unsaved instance has tenant_id None and
        #     `self.tenant` would raise RelatedObjectDoesNotExist on a non-nullable FK rather than
        #     return None. Defaulted getattr for the same class of reason — RelatedObjectDoesNotExist
        #     subclasses AttributeError, so a pointer whose row went away degrades to None here
        #     instead of 500-ing inside validation.
        if self.default_ship_to_id is not None:
            address = getattr(self, "default_ship_to", None)
            if address is not None:
                if self.tenant_id is not None and address.tenant_id != self.tenant_id:
                    errors["default_ship_to"] = "That address belongs to another workspace."
                elif self.customer_id is not None and address.party_id != self.customer_id:
                    errors["default_ship_to"] = (
                        "That address belongs to a different customer. A portal account may only "
                        "default to one of its own customer's addresses.")

        # (b) A threshold the display cannot consume is REFUSED, not ignored. Hidden and exact-
        #     quantity displays never compare against it, so a number typed against either one takes
        #     no effect — and a value a user entered and the system silently dropped is worse than an
        #     error, because they leave believing it applied.
        if (self.low_stock_threshold or ZERO) > ZERO and self.stock_display not in THRESHOLD_STOCK_DISPLAYS:
            errors["low_stock_threshold"] = (
                f"A low-stock threshold does nothing with the '{self.get_stock_display_display()}' "
                "display — it is only read by the availability-text and colour-band displays. "
                "Clear it, or change the stock display.")

        if errors:
            raise ValidationError(errors)

    # ---------------------------------------------------------------------------------------------
    # Persistence
    # ---------------------------------------------------------------------------------------------
    def save(self, *args, **kwargs):
        """Stamp :attr:`activated_on` ONCE, then hand off to ``TenantNumbered.save``.

        First time the account is active, and never again — reactivating a customer after a pause
        must not rewrite the date they were first enabled. The adoption console's whole question is
        "when did this customer get the portal, and have they ever used it?", and a field that moves
        every time somebody toggles a switch cannot answer it.

        The ``update_fields`` fix-up matters because the stamp is a side effect of a save the caller
        did not ask for: a partial ``save(update_fields=["is_active"])`` that flipped the account on
        would otherwise compute the date, keep it in memory and never write it, leaving the row
        active with no activation date at all.
        """
        if self.is_active and self.activated_on is None:
            self.activated_on = timezone.localdate()
            update_fields = kwargs.get("update_fields")
            if update_fields is not None and "activated_on" not in update_fields:
                kwargs["update_fields"] = list(update_fields) + ["activated_on"]
        return super().save(*args, **kwargs)

    # ---------------------------------------------------------------------------------------------
    # Derived — nothing below is stored
    # ---------------------------------------------------------------------------------------------
    @property
    def linked_user_count(self):
        """How many active CRM portal logins currently resolve to this customer.

        Counted live rather than cached on a column: the binding lives in ``crm`` and is created,
        deactivated and re-pointed entirely from there, so any number stored on this side would be
        stale the moment a CRM admin touched it — and a stale "3 users" beside an account nobody can
        log into is exactly the reading the enablement console must not produce. **Zero is the normal
        state of a freshly enabled account**, not an error: staff configure the portal first and bind
        the people afterwards.

        **Local import, following ``apps/scm/views/ReturnsManagement/Reports.py:349-361``: SCM does
        not import CRM at module scope.** Cross-app FKs are declared as strings and need no import at
        all; only code that actually *queries* the peer app reaches for it, and it does so inside the
        function so the two apps stay independent at load time.
        """
        if self.customer_id is None:
            return 0
        from apps.crm.models import CustomerPortalAccess
        return (CustomerPortalAccess.objects
                .filter(tenant_id=self.tenant_id,
                        customer_party_id=self.customer_id,
                        is_active=True)
                .count())

    @property
    def has_never_logged_in(self):
        """True when no ``PortalActivity`` with ``action="login"`` has ever been written for this
        account — the "enabled but never used" signal the adoption console is built around.

        Read through the reverse accessor rather than by importing ``PortalActivity``: the sibling
        model FKs *this* one, so a module-scope import in this direction would close a loop between
        two files in the same package for no benefit. An unsaved instance has no reverse manager to
        query and is answered directly — a row that does not exist yet has certainly never been used.
        """
        if self.pk is None:
            return True
        return not self.activities.filter(action="login").exists()
