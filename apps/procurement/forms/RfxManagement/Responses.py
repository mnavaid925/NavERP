"""Procurement 6.6 RFx Management — RfxResponse forms.

The response form records WHO replied to WHAT; the answers formset is the scoring workspace —
one pre-created row per question whose widget adapts to the question's answer type, plus the
evaluator's 0–10 score. ``extra=0`` and no delete rows: the answer grid always mirrors the
event's questions exactly.
"""
from django import forms

from apps.procurement.forms._common import *  # noqa: F401,F403
from apps.procurement.forms._common import TenantUniqueMixin, _reject_foreign
from apps.procurement.models import RfxAnswer, RfxEvent, RfxResponse


class RfxResponseForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = RfxResponse
        # EXCLUDED and why: ``number``/``submitted_at``/``recorded_by`` are stamped server-side;
        # status moves only through the guarded transition action (status is never a form field,
        # same rule as ProcurementAlert).
        fields = ["event", "supplier", "notes", "attachment"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            # A response belongs to exactly one event forever — moving it would orphan its
            # pre-created answers, so the field exists on CREATE only.
            self.fields.pop("event")
        else:
            self.fields["event"].queryset = RfxEvent.objects.filter(
                tenant=self.tenant, is_template=False).exclude(status="cancelled")

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["supplier"])
        event = self.instance.event if self.instance.pk else cleaned.get("event")
        if event is not None and not event.accepts_responses:
            self.add_error("event", f"Event {event.number or event.pk} is {event.status} — "
                                    f"responses can only be recorded while it is open.")
        return cleaned


class RfxAnswerForm(forms.ModelForm):
    """One question's answer + score, with the input adapted to the question's type."""

    class Meta:
        model = RfxAnswer
        fields = ["answer_text", "score"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        question = getattr(self.instance, "question", None)
        if question is None:
            return
        text = self.fields["answer_text"]
        if question.answer_type == "choice":
            options = question.ordered_options()
            self.fields["answer_text"] = forms.ChoiceField(
                required=False,
                choices=[("", "---")] + [(o, o) for o in options],
                widget=forms.Select(attrs={"class": "form-select"}),
            )
        elif question.answer_type == "longtext":
            text.widget = forms.Textarea(attrs={"rows": 3, "class": "form-textarea"})
        elif question.answer_type == "date":
            text.widget = forms.TextInput(
                attrs={"class": "form-input", "placeholder": "YYYY-MM-DD"})
        elif question.answer_type == "number":
            text.widget = forms.TextInput(
                attrs={"class": "form-input", "inputmode": "decimal",
                       "placeholder": "Numeric answer"})

    def clean_answer_text(self):
        value = self.cleaned_data.get("answer_text") or ""
        if self.instance.question_id is None:
            # A crafted POST can omit the row's id hidden field; the formset then hands us an
            # unattached answer. Skip type checks — there is nothing valid to validate against.
            return value
        question = self.instance.question
        # Type-aware validation the generic column cannot express: numbers must parse as numbers,
        # dates as ISO dates — a typo'd figure would otherwise poison the comparison silently.
        if value and question.answer_type == "number":
            from decimal import Decimal, InvalidOperation

            try:
                Decimal(value)
            except InvalidOperation:
                raise forms.ValidationError("Enter a numeric value.")
        if value and question.answer_type == "date":
            from datetime import date

            try:
                date.fromisoformat(value)
            except ValueError:
                raise forms.ValidationError("Enter a date as YYYY-MM-DD.")
        return value


class BaseRfxAnswerFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        for form in self.forms:
            question = getattr(form.instance, "question", None)
            if question is None or not hasattr(form, "cleaned_data"):
                continue
            value = form.cleaned_data.get("answer_text")
            # Choice answers must be one of the question's declared options — a hand-POSTed
            # off-list value would corrupt the side-by-side comparison's like-for-like premise.
            if value and question.answer_type == "choice" \
                    and value not in question.ordered_options():
                form.add_error("answer_text",
                               "Choose one of the listed options.")


RfxAnswerFormSet = inlineformset_factory(
    RfxResponse, RfxAnswer, form=RfxAnswerForm,
    formset=BaseRfxAnswerFormSet,
    extra=0, can_delete=False,
)
