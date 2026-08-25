"""Procurement 6.5 Sourcing & Tendering — SourcingEvent forms.

The event is edited as a header form plus an inline criterion formset — the evaluation matrix is
part of the event's SETUP (**Event Creation & Scheduling** bullet: "rules"), so it lives on the
same screen rather than a separate CRUD surface.
"""
from decimal import Decimal

from apps.procurement.forms._common import *  # noqa: F401,F403
from apps.procurement.forms._common import _reject_foreign
from apps.procurement.models import EventCriterion, SourcingEvent
from apps.scm.models import PurchaseRequisition


class SourcingEventForm(TenantModelForm):
    class Meta:
        model = SourcingEvent
        # EXCLUDED and why: ``number`` is assigned once by TenantNumbered.save();
        # ``status`` moves only through the view's POST verbs (open/close/cancel/award);
        # the ``*_at`` stamps are set by those same verbs; ``created_by`` is stamped from
        # request.user in the view (never choosable).
        fields = ["title", "description", "event_type", "requisition", "currency",
                  "budget_estimate", "opens_at", "closes_at", "rules"]

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        if tenant is not None:
            # Only live spine requisitions make sense as the trigger row; anything terminal is
            # history, not something a new tender should hang off.
            self.fields["requisition"].queryset = PurchaseRequisition.objects.filter(
                tenant=tenant,
                status__in=("draft", "pending_approval", "approved"),
            ).order_by("-created_at")

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["requisition"])
        opens_at, closes_at = cleaned.get("opens_at"), cleaned.get("closes_at")
        if opens_at and closes_at and closes_at < opens_at:
            self.add_error("closes_at",
                           "The submission deadline cannot be before the opening time.")
        return cleaned


class EventCriterionForm(TenantModelForm):
    class Meta:
        model = EventCriterion
        fields = ["name", "weight_pct", "max_score", "description"]


class BaseEventCriterionFormSet(forms.BaseInlineFormSet):
    """Keeps the matrix coherent: combined weight above 100% is refused outright.

    Below 100% is ALLOWED and rendered as visible coverage on the event page — evaluators may
    deliberately score only part of the matrix — but above 100% would make the weighted score
    exceed its own 0..100 scale, so it never passes validation.
    """

    def clean(self):
        super().clean()
        total = sum(
            (form.cleaned_data.get("weight_pct") or Decimal("0") for form in self.forms
             if form.cleaned_data and not form.cleaned_data.get("DELETE")),
            Decimal("0"),
        )
        if total > Decimal("100"):
            raise forms.ValidationError(
                f"The criteria weights add up to {total}% — together they must not exceed 100%.")


EventCriterionFormSet = inlineformset_factory(
    SourcingEvent, EventCriterion, form=EventCriterionForm,
    formset=BaseEventCriterionFormSet, extra=2, can_delete=True, max_num=20, validate_max=True,
)
