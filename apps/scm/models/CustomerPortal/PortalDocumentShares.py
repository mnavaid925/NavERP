"""SCM 4.16 Customer Portal — PortalDocumentShare [PDS-], the grant and the proof it was used.

**This is the access-control table of the sub-module.** Everything else in 4.16 renders a projection
of rows the customer already owns; this one hands out a *file*, sometimes to a bearer who is not
logged in at all. So the interesting content of this module is not the columns — it is the four
rules below, and the reasons they are where they are rather than somewhere more convenient.

**1. Exactly one typed pointer, and it is the one the type means.** There is no
``GenericForeignKey`` here on purpose. ``core.Document`` already has one and it is the right shape
for *"attach any file to any record"*; it is the wrong shape for *"decide whether this customer may
read this"*, because a ``(content_type, object_id)`` pair cannot be tenant-joined, cannot be
ownership-checked without a per-model branch anyway, and cannot be scoped in a form queryset. Six
nullable FKs cost six columns and buy a database-level guarantee that the target exists, a real
``SET_NULL`` when it does not, and a dropdown per type the form can narrow to this customer's own
rows. The type/pointer matrix itself lives in ``_choices.SHARE_DOC_TYPE_FIELDS`` because
:meth:`clean`, the form and the download view all read it — three hand-written copies of that table
would be three chances to disagree about which column a ``coa`` lives in.

**2. The target must belong to this tenant AND to ``portal_account.customer``.** That single
sentence is the authorisation rule of the whole sub-module: a share is only ever of the customer's
OWN document. It is enforced here, in :meth:`clean`, so the form, the seeder and every future verb
inherit it — **and it is re-checked in the download view**, because validation that only runs on a
form is not an access control. ``full_clean()`` is called by ``ModelForm.is_valid()`` and by nothing
else; a row created by a shell, a data migration, a future API or a bug reaches the token URL
without ever having passed through here. Two checks that agree cost one function call; one check in
the wrong layer costs a customer someone else's invoice.

**3. The grant EXPIRES and can be REVOKED — the explicit fix for 4.10's stated residual risk.** 4.10
shipped an unguessable public token on ``ReturnAuthorization`` and wrote down what it could not do:
*"the token never expires, cannot be rotated and cannot be revoked. No token in this codebase can. A
forwarded link is permanent read access to one RMA."* (``apps/scm/views/ReturnsManagement/
Reports.py:41-42``.) A document share is strictly more dangerous than a return status page — it is a
file, and files get forwarded — so 4.16 pays for the two columns 4.10 went without.
``expires_at`` is staff-editable (a share has a business lifetime somebody decides);
``revoked_at`` is ``editable=False`` and written only by :meth:`revoke`, because "this link is dead"
is a verb a person presses with the consequence on screen, never a date field someone clears by
accident. **Both belong in the LOOKUP, not in a template if-block** — the download view filters
``public_token=token, revoked_at__isnull=True`` and 404s on an expired row, so a killed share is
indistinguishable from a wrong token and leaks not even its own existence.

**4. ``public_token`` is a CREDENTIAL, not an identifier.** It is minted once from the CSPRNG
(``secrets.token_urlsafe(32)``, re-exported through ``apps/scm/models/_base.py:17``) and it is the
only thing standing between a URL and a customer's paperwork. Therefore: never in a form (the column
is ``editable=False``), never in a ``messages.success()`` string, never in a log line, and never in
``AuditLog.changes``. That last one is worth being precise about, because the obvious reassurance is
wrong in an interesting way: ``token`` *is* in ``_SENSITIVE_AUDIT_FIELDS`` (``apps/core/crud.py:178``),
but ``_changed()`` tests ``name in _SENSITIVE_AUDIT_FIELDS`` — an **exact** match, which
``public_token`` would not satisfy. What actually protects it is that ``_changed()`` only ever walks
``form.changed_data``, and an ``editable=False`` column can never be a form field. The redaction list
is the second line of defence here, not the first; the first is that this value never enters a form
at all.

# WARNING (security — a token only protects a file if the file is SERVED THROUGH THE VIEW):
# ``config/urls.py:19-20`` appends ``static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)``
# whenever ``DEBUG`` is on, so in development the underlying ``/media/documents/...`` path is served
# directly by Django and **bypasses this token entirely**. Therefore the download view MUST stream
# via ``django.http.FileResponse(obj.file_field.open("rb"), as_attachment=True,
# filename=<sanitised title>)`` — never ``redirect(obj.file.url)``, never render ``.url`` into a
# template, never expose ``MEDIA_URL`` for a shared document. Nothing in 4.16 may treat the token as
# protection for the media directory: it protects the *view*, and the media directory is a separate
# problem that this module does not solve and must not pretend to.

**No second timestamp.** There is no ``shared_at`` column — ``TenantOwned.created_at`` already is
that instant, and two columns meaning "when was this shared" is two things to keep in sync and one
of them eventually lies.

**Template folder note (house rule, not a defect):** the backend package is
``models/CustomerPortal/`` (PascalCase of the NavERP.md sub-module title) while the templates live
under ``templates/scm/portal/`` (the short slug every other scm folder uses). The asymmetry is
deliberate and shared by all fourteen shipped sub-modules — do not "fix" either side.
"""
import datetime

from apps.scm.models._base import *  # noqa: F401,F403
from apps.scm.models.CustomerPortal._choices import (
    CUSTOMER_VISIBLE_INVOICE_KIND,
    CUSTOMER_VISIBLE_INVOICE_STATUSES,
    MAX_SHARE_EXPIRY_DAYS,
    SHARE_DOC_TYPE_CHOICES,
    SHARE_DOC_TYPE_CSS,
    SHARE_DOC_TYPE_FIELDS,
    SHARE_POINTER_FIELDS,
)


class PortalDocumentShare(TenantNumbered):
    """One document made retrievable by one portal account [PDS-], with its expiry and its evidence."""

    NUMBER_PREFIX = "PDS"

    #: Human names for the six pointer columns, used only to build validation messages. A message
    #: that says "set exactly one of document, invoice, shipment..." reads like a stack trace; one
    #: that names the six things a person actually picked between is the difference between a user
    #: fixing the row and a user filing a ticket.
    POINTER_LABELS = {
        "document": "Uploaded document",
        "invoice": "Invoice",
        "shipment": "Shipment (its POD)",
        "trade_document": "Trade document",
        "contract": "Contract",
        "quality_inspection": "Quality inspection (its CoA)",
    }

    #: For each pointer, the attribute paths on the TARGET that name the owning ``core.Party``, in
    #: preference order. :meth:`clean` walks them and the target passes if **any** resolves to
    #: ``portal_account.customer``. Table-driven for the same reason ``SHARE_DOC_TYPE_FIELDS`` is: a
    #: seventh pointer added later must add a row here, and forgetting to is then a visible hole in
    #: this dict rather than an invisible missing ``elif`` in a hundred-line method.
    #:
    #: The paths are deliberately narrow. ``Shipment`` has no customer of its own, so a POD is
    #: proved to be this customer's only through the sales order it fulfils; a shipment with no
    #: sales order cannot be proved to be theirs and is refused rather than assumed.
    #: ``QualityInspection`` reaches the customer through the CoA issuance (``coa_issued_to``) or,
    #: failing that, through the outgoing shipment's order — its ``supplier`` FK points the other
    #: way entirely and is never consulted.
    OWNER_PATHS = {
        "invoice": ("party_id",),
        "shipment": ("sales_order.customer_id",),
        "trade_document": ("sales_order.customer_id", "consignee_party_id"),
        "contract": ("account_id",),
        "quality_inspection": ("coa_issued_to_id", "shipment.sales_order.customer_id"),
        # core.Document is a GENERIC attachment: it carries a tenant and a GenericForeignKey and no
        # party column at all, by design. The best available proof is whatever its related record
        # names, so all three common spellings are tried. See the "documented weakening" note in
        # clean() for what happens when none of them resolves.
        "document": ("related.party_id", "related.customer_id", "related.account_id"),
    }

    #: pointer -> the dotted path to the ``FieldFile`` the download view streams. **A pointer absent
    #: from this map has no file on disk at all** and its page is RENDERED instead — an invoice, a
    #: contract and a CoA are printed by their own views, and ``Shipment`` records POD as
    #: ``pod_received`` / ``pod_received_at``, which is a fact rather than a scan. Verified against
    #: all six models on disk rather than assumed: ``core.Document.file`` is the only ``FileField``,
    #: and ``TradeDocument`` reaches it one hop out through its own ``document`` FK (its
    #: signed/stamped scan). Table-driven so :attr:`file_field` stays a lookup instead of the
    #: ``isinstance`` sniffing that would quietly start returning a file the day some other model
    #: grew an unrelated attribute called ``file``.
    FILE_PATHS = {
        "document": "file",
        "trade_document": "document.file",
    }

    # --- the audience -----------------------------------------------------------------------------
    # CASCADE, unlike PortalOrderInquiry's PROTECT: an inquiry is evidence of a conversation and must
    # not vanish under the account, but a share is a GRANT, and a grant to a deleted audience is not
    # something to preserve — it is something that must stop existing at the same instant the
    # audience does. Leaving orphan grants behind would leave live tokens pointing at files nobody
    # owns any more.
    portal_account = models.ForeignKey(
        "scm.PortalAccount", on_delete=models.CASCADE, related_name="document_shares",
        help_text="Who may retrieve this. The document must belong to this account's customer")

    doc_type = models.CharField(
        max_length=20, choices=SHARE_DOC_TYPE_CHOICES, default="invoice",
        help_text="What kind of document this is — it decides which of the six pointers below is "
                  "the legal one")

    # The CUSTOMER-FACING label, and the only string any portal page prints for this row. An
    # internal filename is a leak in miniature (it names our conventions, our systems and sometimes
    # our other customers), so the storage path is never rendered anywhere and never used as a
    # fallback here. `target_label` below is the STAFF-side counterpart.
    title = models.CharField(
        max_length=255,
        help_text="What the customer sees. Never paste an internal filename or a storage path here")

    # --- exactly one of these six is set (clean()) -------------------------------------------------
    # All SET_NULL with related_name="+": a share is a pointer, never an owner. Deleting the invoice
    # must not delete the record that we published it, and no target model wants six reverse
    # accessors it never asked for.
    document = models.ForeignKey(
        "core.Document", on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
        help_text="An uploaded file — the target for 'statement' and 'other'")
    invoice = models.ForeignKey(
        "accounting.Invoice", on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
        help_text="An AR invoice. 4.16 READS accounting and computes no AR of its own")
    shipment = models.ForeignKey(
        "scm.Shipment", on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
        help_text="The 4.6 consignment whose proof of delivery is being published")
    trade_document = models.ForeignKey(
        "scm.TradeDocument", on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
        help_text="4.12 paperwork — a BoL, a commercial invoice or a packing list")
    # crm.ContractDocument is the CUSTOMER-side contract. scm.SupplierContract is supplier-side
    # commercial data — our buy prices, our rebates, our terms with somebody else — and must never
    # be reachable from a customer-facing table. There is deliberately no FK to it anywhere here.
    contract = models.ForeignKey(
        "crm.ContractDocument", on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
        help_text="The customer-side contract from CRM 1.9")
    # The sixth pointer, added on top of the research's five: doc_type="coa" had no legal target
    # otherwise, and 4.9 explicitly deferred the customer-facing certificate of analysis to 4.16.
    # It surfaces the CoA that scm:coa_report already renders rather than storing a second copy.
    quality_inspection = models.ForeignKey(
        "scm.QualityInspection", on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
        help_text="The 4.9 inspection whose certificate of analysis is being published")

    # --- the credential ----------------------------------------------------------------------------
    # null=True, NOT blank="": NULLs are distinct under a unique index in MySQL/MariaDB while empty
    # strings are not, so a row that somehow reaches the database before save() has minted a token
    # cannot collide with the next one (the crm.Case public_token reasoning, Cases.py:56-58, and the
    # ReturnAuthorization.public_token precedent at ReturnAuthorizations.py:172-173).
    public_token = models.CharField(max_length=64, unique=True, editable=False, null=True,
                                    blank=True)

    # --- lifetime -----------------------------------------------------------------------------------
    # Staff-editable: how long a share should live is a business decision somebody makes per share.
    expires_at = models.DateTimeField(
        null=True, blank=True,
        help_text=f"After this the link 404s. Blank = no expiry, at most "
                  f"{MAX_SHARE_EXPIRY_DAYS} days out. A forwarded link outlives the person you "
                  f"sent it to — prefer a date")
    # editable=False: written only by revoke(). See the module docstring, rule 3.
    revoked_at = models.DateTimeField(null=True, blank=True, editable=False)

    # --- the evidence trail --------------------------------------------------------------------------
    # All editable=False and all written only by record_download(). "We published that POD on the
    # 3rd and they downloaded it on the 4th" is the sentence these three columns exist to make
    # defensible, and a figure a person can type is not evidence.
    download_count = models.PositiveIntegerField(default=0, editable=False)
    first_viewed_at = models.DateTimeField(null=True, blank=True, editable=False)
    last_downloaded_at = models.DateTimeField(null=True, blank=True, editable=False)

    shared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="+", editable=False,
        help_text="The staff member who published this — set server-side, never on the form")

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            # The account detail page and every customer-facing document list open on this pair.
            models.Index(fields=["tenant", "portal_account"], name="scm_pds_tnt_acct_idx"),
            models.Index(fields=["tenant", "doc_type"], name="scm_pds_tnt_type_idx"),
            # The ?state=live / revoked filter on the staff list, and the standing "what is still
            # readable out there" question an audit asks. Low cardinality as a column but highly
            # selective as a NULL test, which is the shape the filter actually uses.
            models.Index(fields=["tenant", "revoked_at"], name="scm_pds_tnt_revoked_idx"),
            # The staff list's ORDER BY. It sorts ``-created_at, -id`` with only ``tenant``
            # guaranteed — none of the three indexes above carries a date column, so the sort was a
            # filesort on every page load. Cheaper than it looks to add: this table grows per
            # document published, not per page view.
            models.Index(fields=["tenant", "created_at"], name="scm_pds_tnt_at_idx"),
        ]
        # No UniqueConstraint: unique_together is this app's shipped idiom and mixing the two makes
        # the next migration diff harder to read for no behavioural gain.

    def __str__(self):
        return f"{self.number or 'PDS'} · {self.title}"

    # ---------------------------------------------------------------------------------------------
    # Persistence
    # ---------------------------------------------------------------------------------------------
    def save(self, *args, **kwargs):
        """Mint the bearer token ONCE, then hand off to ``TenantNumbered.save``.

        ``secrets.token_urlsafe(32)`` — from the CSPRNG, never ``random`` and never a uuid4 hex,
        because this value is the only credential guarding a file. Minted once and never rotated on
        edit: the link has already been sent, and silently changing it would break a share the
        customer is holding without telling anybody. Rotation is spelled *revoke this one and
        publish another*, which leaves both facts on the record.
        """
        if not self.public_token:
            self.public_token = secrets.token_urlsafe(32)
        return super().save(*args, **kwargs)

    # ---------------------------------------------------------------------------------------------
    # Validation
    # ---------------------------------------------------------------------------------------------
    @staticmethod
    def _resolve(obj, path):
        """Follow a dotted attribute path, returning ``None`` the moment anything on it is missing.

        Defaulted ``getattr`` throughout on purpose: ``RelatedObjectDoesNotExist`` subclasses
        ``AttributeError``, so a pointer whose row went away degrades to ``None`` here instead of
        500-ing inside validation.
        """
        for part in path.split("."):
            obj = getattr(obj, part, None)
            if obj is None:
                return None
        return obj

    def _set_pointers(self):
        """The pointer columns that actually carry a value, in declaration order."""
        return [name for name in SHARE_POINTER_FIELDS
                if getattr(self, f"{name}_id", None) is not None]

    @property
    def pointer_field(self):
        """The name of the one pointer column that is set, or ``""``.

        ``clean()`` guarantees exactly one on any row that came through a form, but this is read by
        pages that render rows the database already holds, so it takes the first rather than
        asserting — a display property is the wrong place to raise.
        """
        pointers = self._set_pointers()
        return pointers[0] if pointers else ""

    def clean(self):
        """Four rules, in this order: exactly one pointer, the right pointer, a sane expiry, and —
        the one that matters — the target really is this customer's."""
        super().clean()

        # (a) EXACTLY ONE POINTER. Zero means a share of nothing (a live token that resolves to a
        #     404 at best and to whatever a template's `{% if %}` chain falls through to at worst);
        #     two means the doc_type decides which one is honoured and the other silently does
        #     nothing, which is how a row ends up meaning something different to the download view
        #     than to the person who created it.
        set_pointers = self._set_pointers()
        expected = SHARE_DOC_TYPE_FIELDS.get(self.doc_type)
        if not set_pointers:
            # Keyed on the pointer this doc_type expects, so the form highlights the box the user
            # should have filled. An unknown doc_type has no such box, so the blame falls on
            # doc_type itself — which is the real defect in that case anyway.
            raise ValidationError({
                expected or "doc_type": (
                    "Pick exactly one thing to share — "
                    + ", ".join(self.POINTER_LABELS[name] for name in SHARE_POINTER_FIELDS)
                    + ". A share with no target is a live link to nothing.")})
        if len(set_pointers) > 1:
            first, second = set_pointers[0], set_pointers[1]
            raise ValidationError({
                second: (f"Only one target per share — this row points at both "
                         f"{self.POINTER_LABELS[first]} and {self.POINTER_LABELS[second]}. Clear "
                         f"one, or create a second share.")})

        pointer = set_pointers[0]

        # (b) THE POINTER MUST MATCH THE DOC TYPE. Table-driven off SHARE_DOC_TYPE_FIELDS so the
        #     model, the form's queryset scoping and the download view's dispatch cannot come to
        #     disagree about which column a type lives in. A "Certificate of analysis" holding an
        #     invoice is not a cosmetic mismatch: the badge, the download handler and the customer's
        #     expectation all key off doc_type.
        if expected is None:
            # Unreachable through the form (doc_type has choices=), reachable through a crafted POST
            # or a shell. Refuse rather than fall through into an unvalidated share.
            raise ValidationError({"doc_type": "Unknown document type."})
        if pointer != expected:
            raise ValidationError({
                pointer: (f"A '{self.get_doc_type_display()}' share must point at "
                          f"{self.POINTER_LABELS[expected]}, not "
                          f"{self.POINTER_LABELS[pointer]}.")})

        errors = {}

        # (c) THE EXPIRY. "In the future" is checked on CREATE only — an existing share that has
        #     already lapsed must stay editable (that is how somebody extends or corrects it), and
        #     re-raising the error on every subsequent save would make an expired row impossible to
        #     touch. The ceiling applies always: a share dated 2099 is exactly the never-expiring
        #     token this column exists to abolish, wearing a date, and a mistyped year produces one
        #     by accident.
        if self.expires_at:
            now = timezone.now()
            if self._state.adding and self.expires_at <= now:
                errors["expires_at"] = ("An expiry in the past creates a share nobody can open — "
                                        "leave it blank or pick a future date.")
            elif self.expires_at > now + datetime.timedelta(days=MAX_SHARE_EXPIRY_DAYS):
                errors["expires_at"] = (
                    f"At most {MAX_SHARE_EXPIRY_DAYS} days out. A link that lives longer than that "
                    "is the permanent read access this column was added to prevent.")

        # (d) THE AUTHORISATION RULE OF THE WHOLE SUB-MODULE: the target belongs to this tenant AND
        #     to this portal account's customer. Re-checked in the download view — see the module
        #     docstring, rule 2. Skipped when there is no tenant or no account yet: an unsaved model
        #     has tenant_id None and `self.tenant` would raise on a non-nullable FK rather than
        #     return None.
        account = getattr(self, "portal_account", None)
        target = getattr(self, pointer, None)
        if self.tenant_id is not None and account is not None and target is not None:
            if account.tenant_id != self.tenant_id:
                errors["portal_account"] = "That portal account belongs to another workspace."
            elif getattr(target, "tenant_id", None) != self.tenant_id:
                # The form's querysets are tenant-scoped, but that is UX — a narrowed dropdown has
                # never held against a crafted POST.
                errors[pointer] = "That record belongs to another workspace."
            else:
                customer_id = account.customer_id
                owners = [self._resolve(target, path)
                          for path in self.OWNER_PATHS.get(pointer, ())]
                owners = [owner for owner in owners if owner is not None]
                if customer_id in owners:
                    pass
                elif owners:
                    errors[pointer] = (
                        f"{self.POINTER_LABELS[pointer]} belongs to a different customer — a share "
                        f"is only ever of {account.customer}'s own documents.")
                elif pointer != "document":
                    # Nothing on the target names an owner at all (a POD for a shipment with no
                    # sales order, a CoA never issued to anybody). Refuse: "cannot be proved to be
                    # theirs" is not the same as "is theirs", and this is the one place in 4.16
                    # where guessing hands a file to the wrong company.
                    errors[pointer] = (
                        f"{self.POINTER_LABELS[pointer]} is not linked to any customer, so it "
                        f"cannot be proved to be {account.customer}'s. Link it first.")
                # DOCUMENTED WEAKENING, and the only one: core.Document is a generic attachment
                # with no party column, so when its related record names no owner either there is
                # nothing left to PROVE ownership with beyond the tenant. Refusing here would make
                # 'statement' and 'other' — the two types that exist precisely for files with no
                # structured home — impossible to share at all. Anything stronger needs a party FK
                # on core.Document, which is a Module 0 schema change and not 4.16's to make.
                #
                # It is a weakening of the OWNERSHIP proof, and it must not become a licence to
                # share anything: `classification` is the one thing core.Document does state about
                # itself, and the check below is where 4.16 honours it. A `confidential` attachment
                # is a file whose own record says it is not for outsiders, and publishing it as a
                # bearer link — fetchable by anyone it is forwarded to, revocable only by an admin —
                # is the single worst thing this model can do. The form already declines to offer
                # one; this refuses a crafted pk, and the download view re-checks it a third time,
                # because a form queryset has never been an access control (L39 §2).
                if (pointer == "document"
                        and getattr(target, "classification", "") == "confidential"):
                    errors[pointer] = (
                        "That document is classified confidential and cannot be published to a "
                        "customer portal. Re-classify it, or share a customer-facing copy.")

                # An invoice must also be one the customer may SEE. Ownership is not the whole test:
                # a draft is ours until we send it, a void is one we withdrew, and a draft credit
                # note is an internal decision to refund that nobody has committed to. The rule
                # already existed for the profile page and was invisible here, which is how every
                # seeded share came to point at a draft credit note.
                if pointer == "invoice" and target is not None:
                    if (getattr(target, "kind", "") != CUSTOMER_VISIBLE_INVOICE_KIND
                            or getattr(target, "status", "")
                            not in CUSTOMER_VISIBLE_INVOICE_STATUSES):
                        errors["invoice"] = (
                            f"{target.number} is not a document this customer may see — only a "
                            "sent, part-paid or paid invoice can be shared. A draft is ours until "
                            "we send it, a void one we withdrew, and a credit note is not an "
                            "invoice.")

        if errors:
            raise ValidationError(errors)

    # ---------------------------------------------------------------------------------------------
    # Derived — never stored
    # ---------------------------------------------------------------------------------------------
    @property
    def is_expired(self):
        return bool(self.expires_at and self.expires_at <= timezone.now())

    @property
    def is_revoked(self):
        return self.revoked_at is not None

    @property
    def is_live(self):
        """Neither expired nor revoked — the one flag every page and badge should read.

        Deliberately a single property rather than two checks repeated at each call site: the day a
        third way to kill a share exists (a suspended account, a tenant that churned), it is added
        here and every reader inherits it. A page that had open-coded ``not obj.revoked_at`` would
        not.
        """
        return not self.is_revoked and not self.is_expired

    @property
    def target(self):
        """The single object this share points at, or ``None`` if the row is mid-edit or its target
        was deleted (every pointer is ``SET_NULL``, so that is a real state, not a bug)."""
        name = self.pointer_field
        return getattr(self, name, None) if name else None

    @property
    def target_label(self):
        """A short STAFF-side identification of the target — ``title`` is what the customer sees.

        Prefers the target's own human reference (its ``number``, its ``name``) and never touches a
        storage path: an internal filename must not reach a page at all, and the staff pages link to
        the target anyway, so there is nothing to gain from printing one.
        """
        target = self.target
        if target is None:
            return ""
        # QualityInspection's CoA has its own number, assigned when the certificate was issued; it
        # is the reference the customer will quote back, so it wins over the QC- inspection number.
        for attr in ("coa_number", "number", "name"):
            value = getattr(target, attr, "")
            if value:
                return str(value)
        return str(target)

    @property
    def file_field(self):
        """The underlying ``FieldFile`` the download view streams, or ``None``.

        ``None`` is a first-class answer, not a failure: an invoice, a contract and a CoA are
        **rendered** by their own pages (``accounting`` prints the invoice, ``scm:coa_report`` prints
        the certificate) and have no file on disk at all, and ``Shipment`` records POD as
        ``pod_received`` / ``pod_received_at`` — a fact, not a scan. The view branches on this: a
        file streams through ``FileResponse``, everything else renders. See the module docstring's
        WARNING for why streaming is not optional.
        """
        path = self.FILE_PATHS.get(self.pointer_field)
        if path is None:
            return None
        target = self.target
        if target is None:
            return None
        # `or None`: an empty FileField is falsy but not None, and "there is a column but no file
        # behind it" must reach the view as "nothing to stream", not as a FieldFile that raises on
        # .open().
        return self._resolve(target, path) or None

    # ---------------------------------------------------------------------------------------------
    # Verbs — both TOCTOU-safe conditional UPDATEs, never read-then-save
    # ---------------------------------------------------------------------------------------------
    def revoke(self, user=None):
        """Kill the link. Returns ``True`` if this call is the one that killed it.

        The guard is in the UPDATE's own filter (``revoked_at__isnull=True``), not in an ``if``
        above it — the ``returnauthorization_public`` / ``case_public`` shape. Read-then-save would
        leave the classic window: two staff members revoking the same share a moment apart would
        both read "not revoked" and the second write would move the revocation timestamp forward,
        rewriting when access actually stopped. That timestamp is evidence; the first one is the
        true one, so a second call updates 0 rows and says so.

        ``user`` is accepted and deliberately NOT stored: there is no ``revoked_by`` column, because
        the actor already lands in ``core.AuditLog`` from the view that called this, and a second
        copy of "who" is a second thing to keep in sync. The parameter exists so the call site reads
        as the audited action it is.
        """
        now = timezone.now()
        updated = (PortalDocumentShare.objects
                   .filter(pk=self.pk, revoked_at__isnull=True)
                   .update(revoked_at=now, updated_at=now))
        if updated:
            # Keep the in-memory object honest so the caller can render the result without a refetch.
            self.revoked_at = now
        return bool(updated)

    def record_download(self):
        """Stamp the evidence trail after a successful retrieval. Two conditional UPDATEs, no reads.

        ``F("download_count") + 1`` increments in the database, so two simultaneous downloads count
        as two — a read-then-save pair would count them as one, and the whole point of the column is
        that it can be quoted in a dispute.

        ``first_viewed_at`` is a **separate** statement filtered on ``first_viewed_at__isnull=True``
        rather than a branch on the value we just read: "the first time this was opened" must be
        written exactly once, and only the database can say whether this call is that once.

        Deliberately NOT gated on :attr:`is_live`. If a file left the building, that is a fact worth
        recording even if the share was revoked microseconds earlier — an evidence trail that
        declines to record inconvenient events is not one.
        """
        now = timezone.now()
        PortalDocumentShare.objects.filter(pk=self.pk, first_viewed_at__isnull=True).update(
            first_viewed_at=now)
        PortalDocumentShare.objects.filter(pk=self.pk).update(
            download_count=F("download_count") + 1, last_downloaded_at=now, updated_at=now)
        # Refresh the in-memory copy rather than leave the caller rendering a stale count. The F()
        # expression is unresolved on the instance until it is re-read, so this is the one place a
        # refetch is required rather than merely tidy.
        self.refresh_from_db(fields=["download_count", "first_viewed_at", "last_downloaded_at"])

    # ---------------------------------------------------------------------------------------------
    # Presentation
    # ---------------------------------------------------------------------------------------------
    @property
    def doc_type_css(self):
        """The badge class for this row's type, decided in ``_choices`` so the list page and the
        detail page cannot style the same value two ways. Only the six classes that exist in
        theme.css are ever returned (L33)."""
        return SHARE_DOC_TYPE_CSS.get(self.doc_type, "badge-muted")
