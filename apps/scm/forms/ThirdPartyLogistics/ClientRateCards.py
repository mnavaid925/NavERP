"""SCM 4.17 Third-Party Logistics (3PL) — the ``ClientRateCard`` header + rate-line forms.

**What a human types here is the PRICE LIST.** What a human never types is anything the sub-module
derives: ``number`` is minted in ``TenantNumbered.save()``, ``active_line_count`` is a query, and
every figure on a bill is ``ClientBillingRun``'s arithmetic over these rates.

--------------------------------------------------------------------------------------------------
FOUR THINGS A READER SHOULD NOT HAVE TO REDISCOVER
--------------------------------------------------------------------------------------------------
**1. ``status`` IS on the header form, deliberately.** A tariff is staff configuration with a short
ladder, and the two audited verbs (``clientratecard_activate`` / ``_supersede``) are the *preferred*
path rather than the only one — the same posture as ``ColdChainMonitorForm.status`` and the
deliberate OPPOSITE of ``ClientBillingRun.status``, which is ``editable=False`` because the run's
verbs own it. **Do not "fix" either one to match the other.** Promoting a card through this form is
safe because the overlap guard lives in ``ClientRateCard.clean()``, so it holds on every write path
— form, verb, management command and shell alike.

**2. ``rate_card`` is ABSENT from the line form and that is a security boundary, not a tidy-up.**
The parent comes from the URL, never from the POST body: a parent pk in a body is precisely how a
caller grafts a priced line onto somebody else's tariff. See ``AssetSparePartForm`` and
``TemperatureReadingForm`` for the same rule stated from the same direction.

**3. ``TenantUniqueMixin`` is mixed into the header form, and both halves are load-bearing.**
``ClientRateCard`` carries ``unique_together ("tenant", "client", "name", "version")``. Django skips
a ``unique_together`` entirely if ANY of its fields is excluded from validation, and ``tenant`` is
never a form field — so without the mixin, re-saving "Standard 2026 v1" for a client that already
has one passes ``is_valid()`` and then raises an uncaught ``IntegrityError`` (a 500) on an ordinary
user mistake. The mixin's constructor half stamps ``instance.tenant`` so the check runs against a
real workspace instead of ``None``; its ``validate_unique`` half is what actually enables it.

**4. DEVIATION FROM THE FROZEN CONTRACT, stated rather than hidden.** The contract specifies
``ClientRateCardLineForm(forms.ModelForm)`` on the grounds that the child has no tenant FK. It is
built on ``TenantModelForm`` instead, because that is the ONLY shape a tenant-less child form takes
anywhere in this app — ``AssetSparePartForm`` (``forms/AssetManagement/Assets.py:199``) and
``LaborPlanLineForm`` (``forms/LaborManagement/LaborPlans.py:132``) are both ``TenantModelForm`` over
a parent-scoped child, and ``apps/scm/forms`` contains no plain ``forms.ModelForm`` at all. Two
concrete things would break with a bare ``ModelForm``: every widget would render WITHOUT the house
``form-input`` / ``form-select`` / ``form-textarea`` classes the template agent's markup assumes
(that styling loop lives in ``TenantModelForm.__init__``), and the base's FK-scoping pass — which
does apply here, because ``Location`` / ``ItemCategory`` / ``GLAccount`` each carry their own tenant
column — would be lost. Nothing about the CONTRACT's interface changes: the class name, ``Meta.
fields`` and the ``rate_card=`` constructor kwarg are exactly as specified, and no context key moves.
"""
from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.forms._common import TenantUniqueMixin, _active_currencies, _reject_foreign

# `GLAccount` and `Currency` are accounting's, not scm's — the same one-way import `_common.py`
# already makes for `Currency` (a peer app's MASTER is imported; a peer app's internals never are).
# `Currency` is named explicitly rather than taken off the star import: `_common` carries no
# `__all__`, so it would arrive silently, and a reader of this file would have no way to see where
# it came from.
from apps.accounting.models import Currency, GLAccount

from apps.scm.models import (
    ClientRateCard,
    ClientRateCardLine,
    ItemCategory,
    Location,
    LogisticsClient,
)


def _scope_to_tenant(form, name, queryset, tenant=None):
    """Point one dropdown at a workspace's rows — and at NOTHING when there is no workspace.

    ``TenantModelForm`` already scopes every FK whose target carries a ``tenant`` column, but only
    ``if tenant is not None``; a tenant-less caller falls through to the UNSCOPED default manager.
    Re-filtering from the model rather than chaining off the base's result makes the scoping true by
    CONSTRUCTION instead of true by the caller behaving (4.13's ``AssetManagement/Assets.py`` and
    4.15's ``ColdChainMonitors.py`` carry this verbatim).

    ``tenant`` is an explicit argument rather than always ``form.tenant`` because the LINE form is
    scoped by its PARENT's workspace, which is the one the route already resolved — not by whatever
    a caller happened to pass.
    """
    if name not in form.fields:
        return
    tenant = tenant if tenant is not None else form.tenant
    form.fields[name].queryset = queryset.filter(tenant=tenant) if tenant is not None \
        else queryset.none()


def _keep_current(form, name, base_queryset):
    """Union the field's CURRENTLY-STORED choice back into a narrowed queryset.

    A narrowed dropdown that drops the saved value silently NULLs it (or, on a required field,
    refuses the save) for somebody who only came to fix a typo in the notes. The union is a no-op
    whenever the stored value still qualifies, which is the common case — it exists for the one that
    no longer does: a currency that was deactivated, a location that was later dedicated to another
    client.

    ``base_queryset`` is the UN-narrowed one, so any ``select_related`` the dropdown needs for its
    ``__str__`` survives the rebuild (rebuilding from the bare default manager would silently drop
    it and reintroduce one query per option).
    """
    if name not in form.fields:
        return
    current = getattr(form.instance, f"{name}_id", None)
    if current is None:
        return
    narrowed = form.fields[name].queryset
    form.fields[name].queryset = base_queryset.filter(
        Q(pk__in=narrowed.values("pk")) | Q(pk=current)).distinct()


class ClientRateCardForm(TenantUniqueMixin, TenantModelForm):
    """The tariff header: whose it is, what it is called, when it prices, and in what currency."""

    class Meta:
        model = ClientRateCard
        # A WHITELIST, never `Meta.exclude`. A whitelist fails CLOSED when a column is added to the
        # model later; an exclude list fails open and would quietly enrol it.
        #
        # Deliberately ABSENT, and why: `tenant` (stamped by `crud_create` AFTER is_valid(), and by
        # TenantUniqueMixin.__init__ before it so `clean()` and the uniqueness check can read it);
        # `number` (auto-assigned in `TenantNumbered.save()` — nobody types a document number);
        # `created_at` / `updated_at` (automatic). EVERYTHING else IS here, `status` included — see
        # the module docstring for why that is the design and not an oversight.
        fields = ["client", "name", "version", "status",
                  "effective_from", "effective_to", "currency", "notes"]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        # TenantUniqueMixin.__init__ runs first in the MRO: it calls up to TenantModelForm (which
        # builds `self.fields` and applies the widget/scoping pass) and only then stamps the tenant,
        # so both are in place by the time this body runs.
        super().__init__(*args, **kwargs)

        # `LogisticsClient.__str__` is f"{code} · {party}" — it walks a second FK, so the dropdown
        # would otherwise fire one query per option (§7.6).
        _scope_to_tenant(self, "client", LogisticsClient.objects.select_related("party"))
        _keep_current(self, "client", LogisticsClient.objects.select_related("party"))

        # `accounting.Currency` is GLOBAL (no tenant column), so TenantModelForm's scoping pass
        # skips it entirely — the narrowing to active currencies has to be explicit.
        _active_currencies(self)
        _keep_current(self, "currency", Currency.objects.all())

        # Deliberately NOT narrowed by client status: a tariff is routinely drafted for a client who
        # is still `prospect` or `onboarding` — that is when prices are negotiated — and narrowing
        # would make the obvious card un-creatable with no way to see why.

    def clean(self):
        """Re-check the chosen client against this workspace — see :func:`_reject_foreign`.

        ``ClientRateCard.clean()`` carries the same rule and is the guard at the DATABASE boundary;
        this repeats it at the FORM boundary because a narrowed ``<select>`` has never held against
        a crafted POST (L39 §2). Without it a tariff could be hung off another workspace's client,
        and every bill it produced would be a statement about somebody else's warehouse.

        Everything else — the date ordering and the active-overlap guard — stays in the model's
        ``clean()``, once, where it also holds against a management command and a shell.
        """
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ClientRateCard.TENANT_SCOPED_FKS)
        return cleaned


class ClientRateCardLineForm(TenantModelForm):
    """One priced charge. **The parent comes from the route** — see the module docstring.

    ``rate_card`` is passed to the constructor and STAMPED onto the instance so that
    ``ClientRateCardLine.clean()``'s five guards — every one of which reads through the parent to
    reach the client, the tenant and the line cap — are live on the CREATE path. Without the stamp
    they would all be dead code on exactly the path a crafted POST takes.
    """

    class Meta:
        model = ClientRateCardLine
        # A WHITELIST. `rate_card` is absent BY DESIGN (the route supplies it); the model has no
        # other columns.
        fields = ["charge_category", "charge_basis", "description", "rate", "period",
                  "included_quantity", "minimum_charge", "tier_from", "tier_to",
                  "applies_to_location", "applies_to_item_category", "gl_account", "is_active"]

    def __init__(self, *args, rate_card=None, **kwargs):
        super().__init__(*args, **kwargs)

        # THE STAMP, one level down from the tenant — the `AssetSparePartForm.asset` posture. Only
        # when it is unset: an edit already carries its parent and must never be repointed at
        # another one. `RelatedObjectDoesNotExist` subclasses `AttributeError`, so the getattr
        # default fires cleanly when the instance has no parent yet.
        if rate_card is not None and self.instance.rate_card_id is None:
            self.instance.rate_card = rate_card
        self.rate_card = rate_card if rate_card is not None \
            else getattr(self.instance, "rate_card", None)

        # Scoped by the PARENT's workspace, not by whatever `tenant=` a caller passed: the route
        # already resolved the card with `tenant=request.tenant`, so the parent's tenant is the one
        # this form's rows must belong to. Falls to `.none()` when there is no parent — an
        # unparented line form is itself a refusal, not a pass.
        parent_tenant = getattr(self.rate_card, "tenant", None)
        _scope_to_tenant(self, "applies_to_location", Location.objects.all(), parent_tenant)
        _scope_to_tenant(self, "applies_to_item_category", ItemCategory.objects.all(), parent_tenant)
        _scope_to_tenant(self, "gl_account", GLAccount.objects.all(), parent_tenant)

        # A location dedicated to ANOTHER client must not even be offered — pricing this client's
        # storage against it would bill them for somebody else's space. Blank-owner (shared) bins
        # and this client's own dedicated bins both stay. The model's `clean()` refuses the same
        # pairing at the database boundary; this is the presentation half.
        client_id = getattr(self.rate_card, "client_id", None)
        if client_id is not None and "applies_to_location" in self.fields:
            field = self.fields["applies_to_location"]
            field.queryset = field.queryset.filter(
                Q(owner_client__isnull=True) | Q(owner_client_id=client_id))

        _keep_current(self, "applies_to_location", Location.objects.all())
        _keep_current(self, "applies_to_item_category", ItemCategory.objects.all())
        _keep_current(self, "gl_account", GLAccount.objects.all())

    def clean(self):
        """The three FK checks, anchored on the PARENT — this row has no tenant column of its own.

        There is nothing on the instance to compare against ``self.tenant``, so ``_reject_foreign``
        (which reads ``form.tenant``) is not the right tool here: the authority is
        ``rate_card.tenant``, resolved by the route. An UNPARENTED form refuses everything, which is
        the correct answer rather than a lucky one — a form constructed by something that skipped
        the route's resolution has no workspace to be checked against (the ``AssetSparePartForm.
        clean`` posture).
        """
        cleaned = super().clean()
        parent_tenant_id = getattr(self.rate_card, "tenant_id", None)
        for name in ("applies_to_location", "applies_to_item_category", "gl_account"):
            chosen = cleaned.get(name)
            if chosen is None:
                continue
            if parent_tenant_id is None or chosen.tenant_id != parent_tenant_id:
                self.add_error(name, "That record belongs to another workspace.")
        return cleaned
