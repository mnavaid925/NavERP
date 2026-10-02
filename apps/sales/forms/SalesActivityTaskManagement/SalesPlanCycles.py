"""Sales 8.8 — the `SalesPlanCycle` (`SPC-`) and `ActivityGoal` forms.

Excluded from ``SalesPlanCycleForm.Meta.fields``, with the reason for each:

* ``tenant`` — set by ``TenantUniqueMixin`` from the view's ``request.tenant``.
* ``number`` — ``editable=False``; allocated by ``next_number`` (L22).
* ``closed_at`` — **FROZEN, SYSTEM-SET** (L22). The model stamps it on the transition into `closed`
  and clears it on re-open. A period-closing timestamp is an accounting fact, not a field a user
  types; letting one be typed is how a plan ends up closed "last Tuesday" when it closed in March.
* ``created_at`` / ``updated_at`` — ``auto_now*`` stamps.

**The date widgets are `type="date"`** so the browser hands Django an ISO date rather than a
locale-formatted string that `parse_date` may or may not accept.

**G11/G12 are enforced by the model.** The form's job is to make the daily-versus-weekly
consequence *legible before* the error, which is what the `period_end` help text does — it is
rewritten per cadence rather than stating one static sentence that is wrong for half the cadences.
"""
from django import forms

from apps.crm.models import Territory
from apps.sales.forms._common import (
    TenantModelForm,
    TenantUniqueMixin,
    _reject_foreign,
    tenant_users,
)
from apps.sales.models.SalesActivityTaskManagement.SalesPlanCycles import (
    MAX_TARGET_COUNT,
    ActivityGoal,
    SalesPlanCycle,
)

DAILY_END_HELP = (
    "A daily plan covers one day, so this must be the same day as the start. Switch the cadence to "
    "weekly to span several days."
)
WEEKLY_END_HELP = (
    "A weekly plan covers seven days, so this must be six days after the start."
)
OPEN_END_HELP = "When the plan's window ends. It must not fall before the start."


class SalesPlanCycleForm(TenantUniqueMixin, TenantModelForm):
    """Create or edit one rep's (or one territory's) day or week."""

    class Meta:
        model = SalesPlanCycle
        # Excluded, with the reason for each — see the module docstring.
        fields = [
            "name",
            "cadence",
            "period_start",
            "period_end",
            "owner",
            "territory",
            "status",
            "suggestion_mode",
            "notes",
        ]
        widgets = {
            "period_start": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "period_end": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "notes": forms.Textarea(attrs={
                "class": "form-textarea",
                "rows": 3,
                "placeholder": "What this week is for, and anything the numbers will not say...",
            }),
        }
        help_texts = {
            "cadence": "A single day, or a seven-day week.",
            "period_start": "The first day in the plan's window.",
            "period_end": OPEN_END_HELP,
            "owner": "Optional. Leave blank for a territory-wide or team plan.",
            "territory": "Optional. Narrows the plan to one territory's book.",
            "status": (
                "Draft while you are still setting goals, active once it is running, closed once "
                "the window has passed."
            ),
            "suggestion_mode": (
                "How far to trust the suggested next actions on this plan. 8.8 proposes them from "
                "fixed rules — no language model is involved — so 'Manual' is the honest default."
            ),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        self.fields["owner"].queryset = tenant_users(self.tenant).order_by("username")
        # ALL of the tenant's territories, retired ones included: a closed plan must still explain
        # which territory it was scoped to after that territory is retired. The shared
        # `tenant_territories` helper narrows to ACTIVE only (correct for a rule that must point at
        # a live territory), so it is the wrong helper here and the queryset is written out.
        self.fields["territory"].queryset = (
            Territory.objects.filter(tenant=self.tenant).order_by("name")
            if self.tenant is not None
            else Territory.objects.none()
        )
        self._rewrite_end_help()

    def _rewrite_end_help(self):
        """Say the consequence of the CHOSEN cadence, not a static sentence.

        A single static help string is wrong for half the cadences — that is the L13/L40 family of
        defect, where a control is present but tells the author something untrue.
        """
        if self.is_bound:
            cadence = self.data.get("cadence")
        elif "cadence" in self.initial:
            cadence = self.initial.get("cadence")
        else:
            cadence = self.instance.cadence
        if cadence == "daily":
            self.fields["period_end"].help_text = DAILY_END_HELP
        elif cadence == "weekly":
            self.fields["period_end"].help_text = WEEKLY_END_HELP
        else:
            self.fields["period_end"].help_text = OPEN_END_HELP

    def clean(self):
        cleaned = super().clean()
        tenant_id = getattr(self.tenant, "pk", self.tenant)
        if tenant_id is None:
            self.add_error(None, "A tenant workspace is required.")
        elif self.instance.pk and self.instance.tenant_id != tenant_id:
            self.add_error(None, "The plan cycle must belong to this workspace.")
        _reject_foreign(self, cleaned, ["owner", "territory"])
        return cleaned


class ActivityGoalForm(TenantModelForm):
    """One activity target inside a cycle. ``target_count`` only — the actual is derived."""

    class Meta:
        model = ActivityGoal
        # `tenant` excluded as always; `cycle` is supplied by the view as initial, never typed.
        fields = ["metric", "target_count"]
        widgets = {
            "target_count": forms.NumberInput(attrs={
                "class": "form-input", "min": "0", "max": str(MAX_TARGET_COUNT), "step": "1",
            }),
        }
        help_texts = {
            "metric": "What to count over the cycle's window.",
            "target_count": (
                f"How many to aim for, 0 to {MAX_TARGET_COUNT}. The ACTUAL is counted from logged "
                "activities when the page is read — it is never stored, so it cannot drift."
            ),
        }