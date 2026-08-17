"""SCM 4.19 Integration & API Gateway — the ``WebhookSubscription`` form.

What a human types here is the RULE: what it is called, which supply-chain event fires it, where the
payload would go, what shape it takes and whether it is switched on. What a human never types is the
``number`` (minted in ``TenantNumbered.save()``), the ``tenant`` (stamped by :class:`TenantUniqueMixin`
before validation and by ``crud_create`` after it), the derived counters, or **the signing secret**.

--------------------------------------------------------------------------------------------------
THE SECRET IS NOT ON THIS FORM, AND ITS ABSENCE IS STRUCTURAL RATHER THAN A LIST ENTRY
--------------------------------------------------------------------------------------------------
``signing_secret_prefix`` / ``signing_secret_hash`` are ``editable=False`` **on the model**, so
Django refuses to build form fields for them at all. That is deliberately stronger than leaving them
off ``Meta.fields``: a whitelist protects against the columns you remembered, and ``editable=False``
protects against the ones a later pass adds without reading this file.

The rule it enforces is L20: a secret named in ``Meta.fields`` ships its stored value back to the
browser in the bound edit render's ``value=""`` — masking it in the TEMPLATE does not help, because
the leak is in the HTML the form generates, not in what the page chooses to print. The only writer
of either column is :meth:`WebhookSubscription.set_signing_secret`, reached from exactly one place:
``webhooksubscription_rotate_secret`` (POST-only, ``@tenant_admin_required``).

--------------------------------------------------------------------------------------------------
``TenantUniqueMixin`` IS LOAD-BEARING — do not "simplify" it away
--------------------------------------------------------------------------------------------------
``WebhookSubscription`` carries ``unique_together ("tenant", "name")``, and re-using a name is the
ordinary mistake on this page (somebody adds "Notify WMS on delivery" for a second target URL rather
than editing the first). Django skips a ``unique_together`` **entirely** if any member field is
excluded from validation, and ``tenant`` is never a form field, so it is always excluded. Without the
mixin the duplicate passes ``is_valid()`` and raises an uncaught ``IntegrityError`` — a 500 on a
mainline CRUD path, from an everyday user error.

Both halves are needed: its ``__init__`` stamps ``instance.tenant`` BEFORE validation (``crud_create``
only assigns it after ``is_valid()``), and its ``validate_unique`` discards ``tenant`` from the
exclusion set, which is what actually re-enables the constraint. It is mixed in **before**
``TenantModelForm`` so its ``__init__`` runs first in the MRO.

--------------------------------------------------------------------------------------------------
THERE ARE NO FK DROPDOWNS TO SCOPE ON THIS FORM — stated so the absence reads as a decision
--------------------------------------------------------------------------------------------------
Every other form in this sub-module ends its ``__init__`` with a block narrowing each
``ModelChoiceField`` to ``self.tenant`` and each ``clean()`` with a ``_reject_foreign`` re-check,
because an unscoped ``ModelChoiceField`` both DISPLAYS another workspace's rows and ACCEPTS their pk
from a crafted POST (L39 §2).

This form has neither block because :class:`WebhookSubscription` **has no foreign key beyond the
inherited ``tenant``** — it is a rule about internal events, so it points at no party, no partner and
no document. ``WebhookSubscription.TENANT_SCOPED_FKS`` is correspondingly ``()``. Nothing is missing
here; there is nothing to scope. If a pointer is ever added to that model, it goes into
``TENANT_SCOPED_FKS`` and a ``clean()`` calling ``_reject_foreign(self, cleaned,
WebhookSubscription.TENANT_SCOPED_FKS)`` belongs back in this class the same day.
"""
from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.forms._common import TenantUniqueMixin

from apps.scm.models import WebhookSubscription


class WebhookSubscriptionForm(TenantUniqueMixin, TenantModelForm):
    """The outbound event rule: trigger, target, payload shape and retry policy."""

    class Meta:
        model = WebhookSubscription
        # A WHITELIST, never `__all__` and never `Meta.exclude`. A whitelist fails CLOSED when a
        # column is added to the model later; an exclude list fails OPEN and would quietly enrol it.
        #
        # Deliberately ABSENT, and why each one:
        #   * `tenant`                  — stamped (TenantUniqueMixin, then crud_create). Never typed.
        #   * `number`                  — auto `WHK-#####` from TenantNumbered.save(). Nobody types a
        #                                 document number.
        #   * `signing_secret_prefix`   — secret material. See the module docstring; `editable=False`
        #   * `signing_secret_hash`       already makes these two structurally unavailable (L20), and
        #                                 `rotate_secret` is their only writer.
        #   * `consecutive_failures`    — a DERIVED counter (L29). A counter a human can type is a
        #                                 number that stops meaning anything.
        #   * `last_delivery_at`        — a SYSTEM timestamp (L22): a `*_at` on a form gets silently
        #                                 TRUNCATED by a DateInput, so the fix is to keep it off.
        #   * `created_at`/`updated_at` — automatic.
        #
        # `is_active` and `auto_disable_threshold` ARE here on purpose: switching a rule off and
        # choosing its retry budget are human decisions, not derived state.
        fields = ["name", "trigger_entity", "trigger_event", "target_url", "payload_format",
                  "filter_expression", "include_fields", "headers", "auto_disable_threshold",
                  "is_active", "description"]
        widgets = {
            # A JSONField renders as a Textarea by default at a size that hides the braces; three
            # rows is enough to see an object without dominating the form. Matches crm.WebhookForm.
            "headers": forms.Textarea(attrs={"rows": 3}),
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Instructions to the TYPIST. The model's own help_text says what each column MEANS; these
        # say what to do about it, and the distinction matters most on the two "recorded, never
        # evaluated" fields — without a note here they read as working features.
        if "target_url" in self.fields:
            self.fields["target_url"].help_text = (
                "HTTPS endpoint the payload would be POSTed to. Outbound delivery is not yet "
                "switched on — this is recorded configuration.")
        if "headers" in self.fields:
            self.fields["headers"].help_text = (
                'A JSON object of string keys and string values, e.g. {"X-Source": "NavERP"}. '
                'Leave as {} for none.')
        if "auto_disable_threshold" in self.fields:
            self.fields["auto_disable_threshold"].help_text = (
                "Consecutive failures after which this rule should be switched off (1-20). "
                "Recorded only — nothing enforces it while delivery is deferred.")

    def clean_headers(self):
        """Refuse anything that is not a FLAT ``{str: str}`` object, and refuse CR/LF in either half.

        Three separate failures are being prevented, and only the first is obvious:

        1. **A non-dict** (a list, a string, a number) would crash the future sender when it tried to
           iterate ``.items()`` — a config error surfacing as a 500 in a background job rather than
           as a field error on the page where it was typed.
        2. **Non-string keys or values** serialise unpredictably into an HTTP header line.
        3. **A CR or LF in either half is request splitting** — the classic header-injection
           primitive: a value ending ``\\r\\nX-Forwarded-For: …`` appends an attacker-chosen header,
           and with a full ``\\r\\n\\r\\n`` an attacker-chosen BODY.

        Validated now, at the point of entry, rather than at send time: this column is written today
        and read by a transport pass that does not exist yet, so the guard has to live where the
        value arrives. The shape is CRM's ``WebhookForm.clean_headers`` — one rule, stated the same
        way in both apps, rather than two implementations free to disagree.
        """
        headers = self.cleaned_data.get("headers")
        if headers in (None, ""):
            return {}
        if not isinstance(headers, dict):
            raise forms.ValidationError("Headers must be a JSON object of key/value pairs, e.g. "
                                        '{"X-Source": "NavERP"}.')
        for key, value in headers.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise forms.ValidationError("All header keys and values must be strings.")
            if any(ch in key or ch in value for ch in ("\r", "\n")):
                raise forms.ValidationError(
                    "Header keys and values must not contain newlines — a newline in a header is "
                    "request splitting, not formatting.")
        return headers
