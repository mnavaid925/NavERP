"""Sales 8.7 — the typed territory-assignment rule form (`TRG-`).

A **sibling** of ``LeadRoutingRuleForm``, not a second rule engine: ``conditions`` is checked by
the model's own ``validate_territory_conditions``, which re-uses 8.1's operators, caps and
scalar predicate and only swaps the closed allow-list for ``TERRITORY_FIELDS``.

**OWNERSHIP (L29/L36/L37).** ``target_territory`` is `crm.Territory`, owned by CRM 1.2. 8.7 EXTENDS
the territory master and declares neither ``Territory`` nor ``SalesQuota`` — see the package
docstring in ``apps/sales/models/TerritoryQuotaManagement/__init__.py`` for the full ruling.

Excluded from ``Meta.fields``, with the reason for each:

* ``tenant`` — set by ``TenantUniqueMixin`` from the view's ``request.tenant``, never from input.
* ``number`` — ``editable=False`` on ``TenantNumbered``; allocated by ``next_number`` (L22).
* ``last_run_at`` / ``last_run_matched_count`` — **FROZEN EVIDENCE**, ``editable=False``, written
  only by the ``territory_rule_run`` POST view inside the very transaction that writes the
  assignment rows. A run's own receipt must never be hand-editable afterwards (L22).
* ``created_at`` / ``updated_at`` — ``auto_now*`` stamps.

``conditions`` is **disabled** when the rule is a ``named_account`` one, because
``TerritoryRule.clean()`` refuses that combination: a named account is picked by hand, so a
condition attached to it is a contradiction, not a stricter rule. The field says so rather than
going blank, and the disable is re-applied on every bound form, so a crafted POST that flips
``segment_type`` to ``named_account`` still cannot smuggle conditions through.
"""
import json

from django import forms

from apps.sales.forms._common import (
    TenantModelForm,
    TenantUniqueMixin,
    _reject_foreign,
    tenant_territories,
)
from apps.sales.models.TerritoryQuotaManagement.TerritoryRules import (
    TERRITORY_FIELDS,
    TerritoryRule,
)

#: The `conditions` keys, read from the model's own allow-list so this help text cannot drift
#: from the list the validator actually enforces (the `AMOUNT_WIDGETS` pattern in 8.4).
ALLOWED_CONDITION_FIELDS = ", ".join(sorted(TERRITORY_FIELDS))

#: Replaces the JSON help text on `conditions` when the rule is a named-account one. The field is
#: disabled there, so an explanation is the only thing the author still sees on the page.
NAMED_ACCOUNT_CONDITIONS_HELP = (
    "A named-account rule picks its accounts by hand, so it carries no match conditions — "
    "TerritoryRule.clean() refuses that combination. Pick a different segment type to match on "
    "fields."
)


class TerritoryRuleForm(TenantUniqueMixin, TenantModelForm):
    """Create / edit one account-to-territory rule."""

    class Meta:
        model = TerritoryRule
        # Excluded, with the reason for each — see the module docstring.
        fields = [
            "name",
            "description",
            "segment_type",
            "match_mode",
            "conditions",
            "is_catch_all",
            "alignment_type",
            "assignment_scope",
            "target_territory",
            "is_active",
            "priority",
            "effective_from",
            "effective_to",
        ]
        widgets = {
            "description": forms.Textarea(attrs={
                "class": "form-textarea",
                "rows": 3,
                "placeholder": "Who asked for this rule, and which accounts it is meant to catch...",
            }),
            "conditions": forms.Textarea(attrs={
                "class": "form-textarea",
                "rows": 8,
                "placeholder": '[{"field": "industry", "operator": "eq", "value": "Manufacturing"}]',
            }),
        }
        help_texts = {
            "segment_type": (
                "How a territory's model type is declared: a territory is geographic because the "
                "active rules pointing at it are geographic."
            ),
            "match_mode": "All conditions must match, or any one of them is enough.",
            "conditions": (
                'A JSON list of {"field", "operator", "value"} objects — at most 20 of them, and '
                f"at most 16 KiB. Allowed fields: {ALLOWED_CONDITION_FIELDS}."
            ),
            "is_catch_all": "A rule with no conditions counts only when it is explicitly a catch-all.",
            "target_territory": (
                "The CRM 1.2 territory this rule assigns to. 8.7 extends CRM's territory; it never "
                "replaces it."
            ),
            "assignment_scope": "'This Territory And Children' also matches every descendant territory.",
            "priority": "Lower numbers are evaluated first. Default 100.",
            "effective_to": "Blank means open-ended. Close a rule to retire it without deleting its history.",
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        # TenantModelForm already narrows every ModelChoiceField to the tenant. This one is
        # narrowed again to the ACTIVE territories, because a rule may only steer new matches at a
        # live territory — a retired one is read by the boards, never selected by a new rule.
        # `tenant_territories` returns an empty queryset for a tenant-less form, so a form built
        # without a tenant offers nothing rather than every territory on the platform.
        self.fields["target_territory"].queryset = tenant_territories(self.tenant).order_by("name")
        # An edit otherwise renders the stored LIST as a Python repr — single quotes, `False`,
        # `None` — which is not valid JSON and not something a JSON textarea should ever show.
        if not self.is_bound and self.instance.pk and isinstance(self.instance.conditions, list):
            self.initial["conditions"] = json.dumps(self.instance.conditions, indent=2)
        if self._selected_segment_type() == "named_account":
            self._lock_conditions()

    def _selected_segment_type(self):
        """What the author has chosen (or has posted) as ``segment_type``.

        Read from the POST body on a bound form and from ``initial`` otherwise, so the disable
        rule holds on the very first post of a create form and on a re-post of an edit form —
        the two moments a static, render-time check would miss.
        """
        if self.is_bound:
            return self.data.get("segment_type")
        return self.initial.get("segment_type")

    def _lock_conditions(self):
        """Disable ``conditions`` on a named-account rule and say why on the field itself.

        Disabled rather than hidden, so the reason stays on the page. A disabled field takes its
        value from the instance, never from the POST body, so the conditions a crafted request
        attached are dropped instead of reaching ``clean()`` as a contradiction.
        """
        conditions = self.fields["conditions"]
        conditions.disabled = True
        conditions.required = False
        conditions.help_text = NAMED_ACCOUNT_CONDITIONS_HELP

    def clean(self):
        cleaned = super().clean()
        tenant_id = getattr(self.tenant, "pk", self.tenant)
        if tenant_id is None:
            self.add_error(None, "A tenant workspace is required.")
        elif self.instance.pk and self.instance.tenant_id != tenant_id:
            self.add_error(None, "The rule must belong to this workspace.")
        # Belt and braces on top of the narrowed queryset: a queryset filter alone would reject a
        # cross-tenant pk with "Select a valid choice", and this says WHY in the author's terms.
        _reject_foreign(self, cleaned, ["target_territory"])
        return cleaned
