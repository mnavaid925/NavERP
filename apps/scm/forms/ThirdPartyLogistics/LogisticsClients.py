"""SCM 4.17 Third-Party Logistics (3PL) — the ``LogisticsClient`` staff form.

This row IS the 3PL agreement's configuration: there is no verb ladder on it and no field owned by a
workflow, so the form takes everything except the system columns. Three rules worth reading before
editing:

* **``status`` is ON the form deliberately.** It is staff configuration, exactly as
  ``PortalAccount``'s switches are — an account manager moves a client from prospect to onboarding to
  active by editing the record, and there is no approval to route it through. Do not strip it and do
  not replace it with POST verbs. (Its one side effect, stamping ``onboarded_on`` the first time the
  client is active, lives in ``LogisticsClient.save()`` where a seeder and a shell session inherit it
  too.)
* **Four columns are EXCLUDED and each for its own reason**, restated here so nobody re-adds them
  from the model: ``tenant`` (stamped by ``crud_create``), ``number`` (auto ``3PL-#####``),
  ``onboarded_on`` (``editable=False`` — evidence of when the client went live, not a date anybody
  picks) and ``last_synced_at`` (``editable=False`` — a system timestamp, and a DateTimeField put on
  a form's DateInput is silently truncated to a date, L22). ``created_at`` / ``updated_at`` are
  ``auto_now*`` and unreachable by a ModelForm anyway.
* **Narrowed dropdowns are UX, never the boundary.** Every tenant-scoped FK is re-checked through
  ``_reject_foreign`` because a ``<select>`` has never held against a crafted POST (L39 §2), and
  ``LogisticsClient.clean()`` carries the same rules at the model boundary — which is the copy that
  holds for the seeder and the shell.

``accounting.Currency`` is a GLOBAL model with no tenant FK, so ``TenantModelForm`` cannot scope it
and it is deliberately absent from ``_reject_foreign``'s list: a tenant comparison against a global
row would reject every valid selection. It is narrowed by ``is_active`` through ``_active_currencies``
instead.
"""
from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.forms._common import _active_currencies, _customer_parties, _reject_foreign

from apps.accounting.models import GLAccount, PaymentTerm
from apps.core.models import Document
from apps.scm.models import LogisticsClient


def _tenant_qs(model, tenant):
    """A model's rows for this workspace, or NOTHING when there is no workspace.

    ``TenantModelForm`` already scopes any FK whose target has a tenant column — but only when
    ``tenant is not None``. The superuser has ``tenant=None`` by design, and for that user the base
    class leaves the queryset UNSCOPED, which puts every workspace's payment terms, GL accounts and
    documents into one dropdown. ``.none()`` is the honest answer: a tenant-less user cannot create
    tenant rows anyway (``crud_create`` refuses them), so an empty select is exactly right.
    """
    if tenant is None:
        return model.objects.none()
    return model.objects.filter(tenant=tenant)


def _keep_current(queryset, current_id):
    """Union the row already on the instance back into a narrowed queryset.

    Every narrowing below can legitimately exclude the value a row already holds — a party whose
    ``customer`` role was removed after the client was onboarded, a payment term since deactivated, a
    parent client the user is now editing. Without this, opening the edit form would silently blank
    that field and the next save would clear it: a field nobody touched, changed by loading a page.

    Written as one ``pk__in`` subquery plus the current pk rather than a queryset ``|`` union, because
    the party queryset arrives ``.distinct()``-ed off a role join and OR-ing two joined querysets
    duplicates rows.
    """
    if current_id is None:
        return queryset
    model = queryset.model
    return model._default_manager.filter(
        Q(pk__in=queryset.values("pk")) | Q(pk=current_id)).distinct()


class LogisticsClientForm(TenantUniqueMixin, TenantModelForm):
    """Staff-facing create/edit for one 3PL client's commercial configuration.

    ``TenantUniqueMixin`` is mixed in FIRST because ``LogisticsClient`` carries
    ``unique_together = (("tenant", "number"), ("tenant", "code"), ("tenant", "party"))`` and two of
    those three are rules a user breaks by hand: reusing a client code, and onboarding the same
    company twice. Without the mixin both pass ``is_valid()`` and then raise an uncaught
    ``IntegrityError`` on ``save()`` — an everyday mistake turning into a 500 on a mainline CRUD path.
    The mixin does two things and both are needed: it stamps the tenant onto the unsaved instance
    (``crud_create`` only assigns it AFTER ``is_valid()``) and it removes ``tenant`` from the
    validation exclusions, without which Django skips the whole constraint.
    """

    class Meta:
        model = LogisticsClient
        # EXPLICIT whitelist, never `exclude`. With `exclude` a column added to the model later is
        # silently added to the form too, which is how a system field ends up user-editable without
        # anybody deciding it should be.
        fields = [
            # identity + lifecycle
            "party", "code", "parent_client", "status",
            # billing configuration
            "billing_cycle", "billing_day", "next_billing_date", "storage_billing_method",
            "minimum_monthly_charge", "default_tax_rate_pct",
            "currency", "payment_terms", "default_revenue_account",
            # space
            "space_model", "committed_sqft", "committed_pallet_positions",
            # contract
            "contract_start", "contract_end", "notice_days", "contract_document",
            # integration (NON-SECRET identifiers only — L20)
            "integration_mode", "client_system", "edi_partner_id", "edi_qualifier",
            # ownership + notes
            "account_manager", "notes",
        ]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
        }
        help_texts = {
            # Says out loud what the narrowed dropdown would otherwise leave the user guessing about.
            # A select that is short for a reason and a select that is short because nothing was set
            # up look identical, and the user cannot tell which one they are facing.
            "party":
                "Only parties tagged as a customer are listed. A company missing that tag is a data "
                "gap on the party record, not a blocker — add the customer role there and it appears "
                "here. Nothing in this module refuses a client whose party lacks the tag.",
            "status":
                "Set directly — there is no approval to route this through. The first time a client "
                "is saved as Active its onboarding date is stamped, once, and never rewritten.",
            "integration_mode":
                "How their orders reach us. Only non-secret partner identifiers are stored here: "
                "there is no API key, endpoint, password or token on this record, and none may be "
                "added. Credentials and transport belong to the integration module.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        tenant = self.tenant
        instance = self.instance

        # `party` narrows by ROLE on top of the base class's tenant scoping — without it the dropdown
        # offers the whole party book, suppliers and carriers included.
        if "party" in self.fields:
            self.fields["party"].queryset = _keep_current(
                _customer_parties(tenant), getattr(instance, "party_id", None))

        # A client cannot be its own parent. Excluded from the dropdown here (UX) AND refused in
        # `LogisticsClient.clean()` along with the cycle and cross-tenant cases (the boundary).
        if "parent_client" in self.fields:
            parents = _tenant_qs(LogisticsClient, tenant)
            if instance.pk is not None:
                parents = parents.exclude(pk=instance.pk)
            # `.select_related("party")` is chained onto the RESULT, not onto `parents`, because
            # `_keep_current` rebuilds off `model._default_manager` and would drop a join applied
            # earlier. `LogisticsClient.__str__` is f"{code} · {party}", so without it rendering this
            # <select> costs one query per option on both the create and the edit page.
            self.fields["parent_client"].queryset = _keep_current(
                parents, getattr(instance, "parent_client_id", None)).select_related("party")

        for name, model in (("payment_terms", PaymentTerm),
                            ("default_revenue_account", GLAccount),
                            ("contract_document", Document)):
            if name in self.fields:
                self.fields[name].queryset = _keep_current(
                    _tenant_qs(model, tenant), getattr(instance, f"{name}_id", None))

        # Currency is GLOBAL — no tenant column — so it is narrowed by `is_active` instead.
        _active_currencies(self)
        if "currency" in self.fields:
            self.fields["currency"].queryset = _keep_current(
                self.fields["currency"].queryset, getattr(instance, "currency_id", None))

        # The account manager is one of THIS workspace's users. `accounts.User.tenant` is nullable
        # (the superuser has none), so the filter also correctly leaves the superuser off the list —
        # a tenant-less login cannot be the named owner of a tenant's client.
        if "account_manager" in self.fields:
            self.fields["account_manager"].queryset = _keep_current(
                _tenant_qs(self.fields["account_manager"].queryset.model, tenant),
                getattr(instance, "account_manager_id", None))

    def clean(self):
        cleaned = super().clean()
        # Re-check every tenant-scoped FK against a crafted POST, keyed on fields the FORM has so the
        # failure renders as a field error rather than raising out of `add_error` (L39 §2). The list
        # is the model's own TENANT_SCOPED_FKS — one table, read by both boundaries, so the two
        # cannot come to disagree. `currency` is absent from it: it is a GLOBAL model.
        _reject_foreign(self, cleaned, LogisticsClient.TENANT_SCOPED_FKS)
        return cleaned
