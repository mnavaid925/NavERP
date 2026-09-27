"""tenants — Subscription forms (split from apps/tenants/forms.py)."""
from django import forms

from apps.tenants.forms._common import *  # noqa: F401,F403
from apps.tenants.models import (
    Subscription,
)


class _AutoRenewSelect(forms.NullBooleanSelect):
    """`NullBooleanSelect` with its three states named for a human (I10).

    `NullBooleanSelect.choices` is a class attribute, so it cannot be relabelled through the
    constructor; subclassing is the supported way to do it.
    """

    choices = [
        ("unknown", "Not specified — nobody has said"),
        ("true", "Yes — auto-renew when the term ends"),
        ("false", "No — do not auto-renew"),
    ]


class SubscriptionForm(TenantModelForm):
    class Meta:
        model = Subscription
        # `auto_renew` + `grace_ends_on` appended by 0.19. They are commercial terms an operator
        # negotiates, not system stamps, so they are editable here (unlike `UsageQuota.breached_at`).
        fields = ["plan", "status", "billing_cycle", "amount", "seats", "started_on", "renews_on",
                  "auto_renew", "grace_ends_on"]
        # I10: `auto_renew` is a THREE-state field (True / False / None), so it must not be
        # rendered as a checkbox. A checkbox is two-state, and the browser sends the same
        # "absent" POST for "nobody answered" and for "somebody declined" - so a checkbox would
        # silently rewrite every unanswered intent into a declined one the first time anybody
        # saved the form for an unrelated reason.
        #
        # `forms.NullBooleanSelect` already posts the three values (`true` / `false` / `unknown`),
        # which is the only stock widget that can carry the third state through a round trip — but
        # its `choices` are a CLASS attribute, so they cannot be passed to the constructor. This
        # subclass exists solely to relabel them for an operator, who should never be asked to
        # interpret the word "unknown" on a commercial term.
        widgets = {
            "auto_renew": _AutoRenewSelect(),
        }

