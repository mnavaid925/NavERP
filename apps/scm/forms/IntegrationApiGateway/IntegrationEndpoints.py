"""SCM 4.19 Integration & API Gateway — the ``IntegrationEndpoint`` staff form.

This row IS a connection's configuration: there is no verb ladder on it and no field owned by a
workflow, so the form takes everything except the system columns. Four rules worth reading before
editing:

* **``status`` is ON the form deliberately.** 4.19 ships no transport, so nothing can observe a
  connection succeed or fail — there is no state machine to own the column, and an integrations
  engineer marks a connection connected/error/disabled by editing the record. It is a
  human-maintained marker, exactly as ``LogisticsClient.status`` is. ``consecutive_failures`` is the
  opposite case and is NOT on the form: it is a derived counter.

* **THE TWO SECRET COLUMNS ARE STRUCTURALLY UNREACHABLE FROM HERE.** ``credential_prefix`` and
  ``credential_hash`` are ``editable=False`` on the model, so no ``fields`` list can pull them in by
  accident (L20/L22). ``integrationendpoint_rotate_credential`` is their only writer. A secret placed
  in ``Meta.fields`` ships its stored value in the edit form's ``value=""`` attribute, which is the
  exact shape L20 records; and a system ``*_at`` column on a ModelForm's ``DateInput`` is silently
  truncated to a date (L22). Neither can happen while those columns stay ``editable=False`` — do not
  "helpfully" make them editable.

* **Narrowed dropdowns are UX, never the boundary.** Every tenant-scoped FK is re-checked through
  ``_reject_foreign`` because a ``<select>`` has never held against a crafted POST (L39 §2), and
  ``IntegrationEndpoint.clean()`` carries the same rules at the model boundary — which is the copy
  that holds for the seeder and the shell.

* **Constraint A is repeated here as a FIELD error.** The model refuses an ``interchange_id`` typed
  onto a connection that already names a 3PL client (4.17 owns that partner's EDI identity). Both
  keys are on this form, which is what makes the refusal renderable rather than a ``ValueError`` out
  of ``add_error``.

EXCLUDED from ``Meta.fields``, each for its own reason, restated here so nobody re-adds them from the
model: ``tenant`` (stamped by ``crud_create`` / ``TenantUniqueMixin``), ``number`` (auto ``CNX-#####``),
``credential_prefix`` + ``credential_hash`` (the secret marker — rotate is the only writer),
``consecutive_failures`` (a derived counter), ``last_run_at`` / ``last_success_at`` / ``last_seen_at``
(system timestamps), and ``created_at`` / ``updated_at`` (``auto_now*``, unreachable by a ModelForm
anyway).
"""
from apps.scm.forms._common import *  # noqa: F401,F403
# The star import skips private names (this package's `_common` carries no `__all__`), so the helpers
# this module is subject to are named explicitly — a reader can see at the top which shared rules
# apply. `_keep_current` here is the SHARED one in `forms/_common.py`, signature
# `(form, name, base_queryset)` — not the older private copy inside
# `ThirdPartyLogistics/LogisticsClients.py`, which takes `(queryset, current_id)`.
from apps.scm.forms._common import _keep_current, _reject_foreign

from apps.core.models import Document
from apps.scm.models import IntegrationEndpoint, Location, LogisticsClient


def _tenant_qs(model, tenant):
    """A model's rows for this workspace, or NOTHING when there is no workspace.

    ``TenantModelForm`` already scopes any FK whose target has a tenant column — but only when
    ``tenant is not None``. The superuser has ``tenant=None`` by design, and for that user the base
    class leaves the queryset UNSCOPED, which would put every workspace's parties, clients, bins and
    documents into one dropdown. ``.none()`` is the honest answer: a tenant-less user cannot create
    tenant rows anyway (``crud_create`` refuses them), so an empty select is exactly right.
    """
    if tenant is None:
        return model.objects.none()
    return model.objects.filter(tenant=tenant)


class IntegrationEndpointForm(TenantUniqueMixin, TenantModelForm):
    """Staff-facing create/edit for one registered connection.

    ``TenantUniqueMixin`` is mixed in FIRST because ``IntegrationEndpoint`` carries
    ``unique_together = (("tenant", "number"), ("tenant", "name"))`` and the second of those is a rule
    a user breaks by hand — registering "Shopify" twice. Without the mixin that passes ``is_valid()``
    and then raises an uncaught ``IntegrityError`` on ``save()``: an everyday mistake turning into a
    500 on a mainline CRUD path. The mixin does two things and both are needed — it stamps the tenant
    onto the unsaved instance (``crud_create`` only assigns it AFTER ``is_valid()``, so without this
    ``IntegrationEndpoint.clean()``'s cross-tenant guards would validate against ``tenant_id=None``)
    and it removes ``tenant`` from the validation exclusions, without which Django skips the whole
    constraint.
    """

    class Meta:
        model = IntegrationEndpoint
        # EXPLICIT whitelist, never `__all__` and never `exclude`. With `exclude` a column added to
        # the model later is silently added to the form too, which is how a system field ends up
        # user-editable without anybody deciding it should be.
        fields = [
            # identity
            "name", "category", "system", "direction", "transport", "auth_method",
            "endpoint_url", "external_account_ref",
            # pointers
            "partner_party", "logistics_client", "location", "spec_document",
            # EDI / device identity (see constraint A)
            "interchange_id", "interchange_qualifier", "device_identifier",
            # scheduling intent
            "trigger_mode", "schedule_note",
            # lifecycle
            "environment", "lifecycle_stage", "status", "is_active",
            "notes",
        ]
        widgets = {
            # A plain TextInput, NOT a URLInput — `endpoint_url` legitimately holds sftp:// as2://
            # mqtt:// llrp:// values, and a URLInput's browser-side validation would refuse them
            # before the request was ever sent. The model column is a CharField for the matching
            # reason (Django's URLValidator accepts only http/https/ftp/ftps); see the field comment
            # on the model before "fixing" either half.
            "endpoint_url": forms.TextInput(attrs={"placeholder": "https://…  sftp://…  mqtt://…"}),
            "schedule_note": forms.TextInput(),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }
        help_texts = {
            # Says out loud what a narrowed dropdown would otherwise leave the user guessing about,
            # and states the credential rule where somebody filling the form will actually read it.
            "auth_method":
                "How this connection would authenticate. No credential is entered on this form — "
                "register one from the connection's page after saving, where it is shown once and "
                "then kept only as a prefix and a digest.",
            "logistics_client":
                "Link a 3PL client and this connection reads their EDI interchange id and qualifier "
                "straight off the client record — leave the two interchange fields below blank.",
            "status":
                "Set directly. Nothing in this build connects to anything, so no process can observe "
                "this connection go up or down — this is the marker a human maintains.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        tenant = self.tenant
        instance = self.instance

        # All four dropdowns are scoped to this workspace explicitly rather than left to the base
        # class, because the base class does nothing for a tenant-less user (see `_tenant_qs`).
        #
        # `partner_party` is deliberately NOT narrowed by PartyRole: an EDI counterpart may be a
        # customer (they send us 850s), a supplier (we send them 850s) or a partner, and narrowing to
        # one role would hide two thirds of the legitimate choices behind a select that looks merely
        # short.
        #
        # `_keep_current` is applied to each so a stored value that a LATER narrowing excludes cannot
        # silently NULL on edit — someone opening the page to fix a typo must not clear a field they
        # never touched. It is a no-op today (nothing below narrows past tenant scoping); it is here
        # so that a narrowing added later inherits the protection instead of quietly regressing.
        for name, model in (("partner_party", Party),
                            ("logistics_client", LogisticsClient),
                            ("location", Location),
                            ("spec_document", Document)):
            if name not in self.fields:
                continue
            base = _tenant_qs(model, tenant)
            self.fields[name].queryset = base
            _keep_current(self, name, base)

        # `LogisticsClient.__str__` is f"{code} · {party}", so without this join rendering that
        # <select> costs one query per option on both the create and the edit page.
        if "logistics_client" in self.fields:
            self.fields["logistics_client"].queryset = (
                self.fields["logistics_client"].queryset.select_related("party"))

    def clean(self):
        cleaned = super().clean()

        # Re-check every tenant-scoped FK against a crafted POST, keyed on fields the FORM has so the
        # failure renders as a field error rather than raising out of `add_error` (L39 §2). The list
        # is the model's own TENANT_SCOPED_FKS — one table, read by both boundaries, so the two
        # cannot come to disagree.
        _reject_foreign(self, cleaned, IntegrationEndpoint.TENANT_SCOPED_FKS)

        # CONSTRAINT A, repeated at the FORM boundary. `IntegrationEndpoint.clean()` carries the same
        # rule (and is the copy that holds for the seeder and the shell), but a ModelForm skips the
        # model's `clean()` for any instance whose validation it has already failed, and repeating it
        # here keys the error on the two fields the user is actually looking at.
        client = cleaned.get("logistics_client")
        if client is not None:
            label = getattr(client, "code", "") or ""
            named = f" ({label})" if label else ""
            message = (
                f"This connection is linked to a 3PL client{named}, and that client record already "
                "holds its EDI interchange id and qualifier. Clear this field and edit them on the "
                "client instead — the connection reads them through the link, so they stay correct "
                "in one place.")
            for name in ("interchange_id", "interchange_qualifier"):
                if (cleaned.get(name) or "").strip():
                    self.add_error(name, message)

        return cleaned
