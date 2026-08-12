"""SCM 4.16 Customer Portal — the ``PortalDocumentShare`` staff form.

**The querysets are derived from ``PortalDocumentShare.OWNER_PATHS``, the same table
``clean()`` validates against.** That is the point of this module rather than an incidental tidiness:
if the form scoped its dropdowns by a hand-written second set of rules, the two would drift and the
symptom would be a picker that offers a document the model then refuses — the 4.11 finding, offering
a choice the system will reject. Deriving both from one table makes that impossible by construction,
and a seventh pointer added later inherits the scoping for free.

The paths are Python attribute paths (``sales_order.customer_id``); ORM lookups want
``sales_order__customer_id``. The translation is one ``replace`` and is done here rather than by
keeping two spellings of the same table.

**``document`` is the one pointer that cannot be scoped this way, and it is scoped to the tenant
alone.** ``core.Document`` reaches its owner through a ``GenericForeignKey``, which the ORM cannot
filter across — there is no join to follow. This is the same documented weakening ``clean()``
carries, and it is why ``core.Document`` is also the only pointer whose ownership check is allowed
to fall through. Closing it properly needs a party FK on ``core.Document``, which is a Module 0
schema change and not 4.16's to make.

**``public_token`` is not on this form and never will be.** It is a bearer credential (the L20
secret-field class) — minted in ``save()``, absent from every ModelForm because it is
``editable=False``, and never rendered, logged or put in a message. The same applies to
``revoked_at``, ``download_count``, ``first_viewed_at``, ``last_downloaded_at`` and ``shared_by``:
all system-written, all ``editable=False``, none listed below.

**# WARNING — ``expires_at`` and ``revoked_at`` are two halves of ONE control and must be gated
the same way.** Both answer the same question: *how much longer may this bearer token fetch this
customer's document?* ``revoked_at`` is ``editable=False`` and written only by the ``revoke`` verb,
which is ``@require_POST`` + ``@tenant_admin_required``. ``expires_at`` is on this form. So if
``portaldocumentshare_edit`` is left at plain ``@login_required``, **any tenant member can blank
``expires_at`` — blank means never expires — on a share only an admin is allowed to revoke.** That
is not a smaller version of revoking; an unrevokable-in-practice permanent link is strictly worse
than an un-revoked one, and it is exactly the permanent read access ``expires_at`` was added to
abolish (4.10's documented residual risk).

Therefore **``portaldocumentshare_edit`` MUST carry ``@tenant_admin_required``**, or ``expires_at``
must come off this form and move behind its own gated verb. Pick one; do not ship neither.

This is a general shape, not a one-off: *any field a form exposes whose authoritative writer is a
staff-gated verb is a privilege-escalation bypass by construction.* The sibling instance found by
the same grep lives at ``apps/scm/forms/ReturnsManagement/ReturnDispositions.py`` — ``disposition``
is on the form while ``returndisposition_decide`` is ``@tenant_admin_required`` and
``returndisposition_edit`` is not. When adding a field here, ask who else can write it and whether
they are held to the same bar.
"""
from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.forms._common import _reject_foreign

# The same int-FK guard the list views apply to a GET param (L11): a submitted `portal_account`
# that is not a pk — junk, a Unicode superscript, an over-range integer — must resolve to None and
# leave the dropdowns empty, never raise out of `.filter()`.
from apps.core.crud import as_db_int

#: pointer -> the FK its target's ``__str__`` walks, or absent when it walks none.
#:
#: Table-driven beside ``SHARE_DOC_TYPE_FIELDS`` and ``OWNER_PATHS`` for the same reason those are:
#: a seventh pointer added later must add a row here too, and forgetting to is then a visible hole
#: in a dict rather than an invisible missing ``elif``. **Only entries that a ``__str__`` actually
#: reads belong here** — a join nothing renders is not free, it is a wider row fetched per option
#: for nothing, and unlike a WRONG ``select_related`` (which raises ``FieldError`` the moment the
#: widget iterates) a merely useless one is completely silent.
SHARE_POINTER_SELECT_RELATED = {
    "quality_inspection": "item",   # QualityInspection.__str__ -> f"{number} · {item.sku}"
}

from apps.core.models import Document
from apps.scm.models import (
    SHARE_DOC_TYPE_CHOICES,
    SHARE_DOC_TYPE_FIELDS,
    PortalAccount,
    PortalDocumentShare,
    QualityInspection,
    Shipment,
    TradeDocument,
)


class PortalDocumentShareForm(TenantUniqueMixin, TenantModelForm):
    """Staff-facing create/edit for one shared document.

    ``TenantUniqueMixin`` for the ``("tenant", "number")`` pair, matching every other numbered form
    in this app — without it a number collision under concurrency surfaces as an ``IntegrityError``
    500 rather than a field error.
    """

    class Meta:
        model = PortalDocumentShare
        fields = [
            "portal_account", "doc_type", "title",
            # The six pointers. Exactly one may be set — see the help text and clean().
            "document", "invoice", "shipment", "trade_document", "contract", "quality_inspection",
            "expires_at",
        ]
        widgets = {
            "expires_at": forms.DateTimeInput(attrs={"type": "datetime-local"},
                                              format="%Y-%m-%dT%H:%M"),
        }
        help_texts = {
            "title":
                "The label the CUSTOMER sees. Never paste an internal filename or a storage path "
                "here — this string is rendered on their portal.",
            "expires_at":
                "Required when publishing. The link is a bearer credential — anyone the customer "
                "forwards it to can fetch the document until it lapses or is revoked — so a new "
                "share always gets an end date. An admin can clear it later to make the link "
                "permanent.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if "portal_account" in self.fields:
            self.fields["portal_account"].queryset = (
                PortalAccount.objects.filter(tenant=self.tenant).select_related("customer")
                if self.tenant is not None else PortalAccount.objects.none())

        # AN EXPIRY IS REQUIRED ON CREATE, optional on edit.
        #
        # `portaldocumentshare_edit` and `_revoke` are both `@tenant_admin_required`, but CREATE is
        # `@login_required` so any member may publish. Without this, a member could mint a link that
        # NEVER EXPIRES and that only an admin can then kill — the same split-control problem the
        # module docstring describes for `expires_at`/`revoked_at`, arriving through the one verb
        # that was not gated. The argument that a create is visible (an audit row, top of a
        # `-created_at` register) is true but only DETECTS; this prevents.
        #
        # Optional on edit rather than always-required, because clearing it is a real decision an
        # admin is entitled to make — and edit is where admins are. So the permanent link stays
        # possible and becomes something an admin chose, instead of something a member defaulted to.
        if "expires_at" in self.fields and self.instance.pk is None:
            self.fields["expires_at"].required = True

        self._scope_pointers()

        # Stated ABOVE the fields, not only in the error message. Someone looking at six pickers has
        # no way to know only one may be filled until they have already filled two and been told off.
        # Built from SHARE_DOC_TYPE_FIELDS so the printed matrix cannot disagree with the rule
        # clean() enforces — the same reason the querysets are derived rather than hand-written.
        doc_type_labels = dict(SHARE_DOC_TYPE_CHOICES)
        matrix = "; ".join(
            f"{doc_type_labels.get(doc_type, doc_type)} → {PortalDocumentShare.POINTER_LABELS[field]}"
            for doc_type, field in SHARE_DOC_TYPE_FIELDS.items())
        for name in PortalDocumentShare.POINTER_LABELS:
            if name in self.fields:
                # required=False on all six: the model decides which ONE is mandatory, based on
                # doc_type. Leaving Django's per-field requiredness on would demand all six.
                self.fields[name].required = False
                self.fields[name].help_text = (
                    "Pick exactly ONE target across these six fields, and it must match the "
                    f"document type chosen above. {matrix}")

    # ------------------------------------------------------------------------------------------
    def _scope_pointers(self):
        """Narrow each pointer to the chosen account's OWN documents, using ``OWNER_PATHS``.

        Falls back to an EMPTY queryset for every pointer when no account is known yet (a blank
        create form). That is deliberate and it is the same call ``PortalAccountForm`` makes for
        ``default_ship_to``: the tenant-wide default would offer every customer's invoices in one
        select, and the first one picked would belong to whoever the user scrolled to. ``clean()``
        would refuse it, but only after the form was filled in.
        """
        # Local CRM import — SCM does not import CRM at module scope (the 4.10 precedent). Kept
        # inside the method so the two apps stay independent at load time.
        from apps.crm.models import ContractDocument

        models_by_pointer = {
            "document": Document,
            "invoice": None,          # filled below, needs a local accounting import
            "shipment": Shipment,
            "trade_document": TradeDocument,
            "contract": ContractDocument,
            "quality_inspection": QualityInspection,
        }
        from apps.accounting.models import Invoice
        models_by_pointer["invoice"] = Invoice

        # RESOLVE THE ACCOUNT FROM THE SUBMITTED DATA FIRST, then fall back to the instance.
        #
        # Reading it off `self.instance` alone is why this form could never create a share: the
        # create view hands in `PortalDocumentShare(tenant=...)` with no `portal_account`, so
        # `customer_id` was None, every one of the six pointer querysets collapsed to `.none()`, and
        # the user was offered nothing to pick — on the GET *and* on the POST, so a valid choice
        # could not even be re-validated. The seeder builds its rows with `objects.create()`, which
        # never touches a form, which is exactly why the demo data looked healthy.
        #
        # `self.data` is the raw POST, so the pk is a string and may be anything a caller typed;
        # `as_db_int` refuses a non-pk (junk, a Unicode superscript, an over-range integer) instead
        # of raising out of `.filter()` (L11), and the lookup stays tenant-scoped so a crafted pk
        # from another workspace resolves to None and the querysets stay empty.
        account = None
        source = (self.data.get(self.add_prefix("portal_account")) if self.is_bound
                  else self.initial.get("portal_account"))
        chosen = as_db_int(source if source is None or isinstance(source, str) else str(source))
        if chosen is not None and self.tenant is not None:
            account = (PortalAccount.objects
                       .filter(tenant=self.tenant, pk=chosen)
                       .select_related("customer").first())
        if account is None:
            account = getattr(self.instance, "portal_account", None)
        customer_id = getattr(account, "customer_id", None) if account is not None else None

        for pointer, model in models_by_pointer.items():
            if pointer not in self.fields:
                continue
            if self.tenant is None or customer_id is None:
                self.fields[pointer].queryset = model.objects.none()
                continue

            queryset = model.objects.filter(tenant=self.tenant)
            if pointer == "document":
                # GenericForeignKey — no join to filter across, so ownership cannot be proved by
                # query here (the documented weakening; clean() carries the matching note).
                #
                # But `core.Document.classification` CAN be: it is that model's own
                # public / internal / confidential flag, and a column whose entire purpose is "this
                # file is not for outsiders" was being ignored by the one surface in the codebase
                # that publishes files TO outsiders. A confidential attachment offered here becomes
                # a bearer link that anyone it is forwarded to can fetch until an admin revokes it.
                #
                # `internal` is deliberately still offered: internal-vs-public is about origin, not
                # about permission to share, and refusing it would make the default classification
                # unshareable. `confidential` is the one that states the answer outright.
                self.fields[pointer].queryset = queryset.exclude(classification="confidential")
                continue

            # Prefetch the hop this pointer's `__str__` walks, where it walks one. Checked all six
            # in source rather than assumed — five build their label from local columns only
            # (`Document.name`; `Invoice.number`; `Shipment.number` + a display method;
            # `TradeDocument.number` + a display method; `ContractDocument.number` + `name`) and so
            # need no join at all. `QualityInspection.__str__` reads `self.item.sku`, so without
            # this it fired one query per rendered `<option>` — invisible, because an unhelpful
            # `select_related` is silent where a wrong one raises.
            related = SHARE_POINTER_SELECT_RELATED.get(pointer)
            if related:
                queryset = queryset.select_related(related)

            owner = Q()
            for path in PortalDocumentShare.OWNER_PATHS.get(pointer, ()):
                owner |= Q(**{path.replace(".", "__"): customer_id})
            # An empty Q() would be a no-op filter returning EVERYTHING, so a pointer accidentally
            # missing from OWNER_PATHS must collapse to none() rather than to the whole table.
            self.fields[pointer].queryset = queryset.filter(owner) if owner else model.objects.none()

    # ------------------------------------------------------------------------------------------
    def clean(self):
        cleaned = super().clean()
        # The exactly-one and doc_type-matches rules live on the model, which is where the seeder
        # and the shell also hit them. Repeated here only as the tenant re-check against a crafted
        # POST, keyed on fields this form actually has (L39 §2).
        _reject_foreign(self, cleaned, [
            name for name in ("portal_account", "invoice", "shipment", "trade_document",
                              "contract", "quality_inspection", "document")
            if name in self.fields
        ])
        return cleaned
