"""Procurement 6.6 RFx Management — RfxEvent forms.

The event form carries the header plus an inline question formset — the **Questionnaire Builder**
bullet: sections, typed prompts, weights and delete rows in one screen, with ▲/▼ reorder actions
on the detail page for the fine positioning (the drag-and-drop intent, keyboard-and-button form).
"""
from django.db.models import Max

from apps.procurement.forms._common import *  # noqa: F401,F403
from apps.procurement.forms._common import TenantUniqueMixin, _reject_foreign
from apps.procurement.models import RfxEvent, RfxQuestion


class RfxEventForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = RfxEvent
        # EXCLUDED and why: ``number`` is assigned once by TenantNumbered.save(); status moves
        # only through the guarded issue/close/cancel actions; issued_at/closed_at/created_by are
        # stamped server-side.
        fields = ["title", "rfx_type", "description", "requisition", "response_due",
                  "is_template"]
        labels = {"is_template": "Save to Template Library"}
        help_texts = {"is_template": "Library rows stay drafts and are cloned into real events "
                                     "via Use."}

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["requisition"])
        # A library row is a questionnaire blueprint — an event that already collected responses
        # must not retroactively become one.
        if cleaned.get("is_template") and self.instance.pk and self.instance.responses.exists():
            self.add_error("is_template",
                           "This event already has supplier responses and cannot become a "
                           "template.")
        return cleaned


class RfxQuestionForm(TenantModelForm):
    """Plain per-question fields; ``TenantModelForm`` is the package convention so the formset
    can hand every row the workspace kwarg uniformly (this form has no FK dropdowns to scope)."""

    class Meta:
        model = RfxQuestion
        # ``order`` is NOT on the form: new questions append after the last one (see the formset)
        # and reordering happens through the move action on the detail page.
        fields = ["section", "prompt", "help_text", "answer_type", "options", "weight",
                  "is_scored"]

    def clean(self):
        cleaned = super().clean()
        # Non-choice questions carry no options; blanking them here keeps cloned/edited rows tidy
        # instead of storing dead text that would resurface if the type were switched back.
        if cleaned.get("answer_type") != "choice":
            cleaned["options"] = ""
        return cleaned


class BaseRfxQuestionFormSet(forms.BaseInlineFormSet):
    """Builder guards + order assignment for newly appended questions.

    The formset is refused outright when the event is no longer a draft: an issued event's
    questionnaire is frozen so its responses stay comparable — a crafted POST to the edit page
    must land as a validation error, not silently rewrite history.
    """

    def clean(self):
        super().clean()
        if self.instance.pk and not self.instance.is_editable:
            raise forms.ValidationError(
                "Questions are locked once an event is issued — clone or cancel it instead.")

    def _next_order(self):
        if getattr(self, "_order_seq", None) is None:
            agg = self.instance.questions.aggregate(m=Max("order"))
            self._order_seq = agg["m"] or 0
        self._order_seq += 1
        return self._order_seq

    def save_new(self, form, commit=True):
        obj = super().save_new(form, commit=False)
        obj.order = self._next_order()
        if commit:
            obj.save()
        return obj


RfxQuestionFormSet = inlineformset_factory(
    RfxEvent, RfxQuestion, form=RfxQuestionForm,
    formset=BaseRfxQuestionFormSet,
    extra=2, can_delete=True,
    max_num=60, validate_max=True,  # caps a crafted TOTAL_FORMS at a sane builder size
)
