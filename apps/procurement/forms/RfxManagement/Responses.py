"""Procurement 6.6 RFx Management — RfxResponse forms.

The response form records WHO replied to WHAT; the answers formset is the scoring workspace —
one pre-created row per question whose widget adapts to the question's answer type, plus the
evaluator's 0–10 score. ``extra=0`` and no delete rows: the answer grid always mirrors the
event's questions exactly.
"""
import os

from django import forms

from apps.procurement.forms._common import *  # noqa: F401,F403
from apps.procurement.forms._common import TenantUniqueMixin, _reject_foreign
from apps.procurement.models import RfxAnswer, RfxEvent, RfxResponse

#: Proposal attachments: documents/images/plain text only. Media is served same-origin from the
#: webroot, so anything scriptable in the allowlist is stored-XSS/malware surface.
ALLOWED_ATTACHMENT_EXTENSIONS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".png", ".jpg", ".txt"}
MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024


def _validate_attachment(f):
    """Shared attachment upload guard — extension allowlist + size cap (mirrors HRM's
    _validate_upload; peer apps copy the pattern, never cross-import). Validates a freshly-uploaded
    file only (an existing FieldFile has no new size to re-check); the size cap applies when a size
    attribute is present, so a name-only wrapper is still extension-checked rather than skipped."""
    if f and hasattr(f, "name"):
        ext = os.path.splitext(f.name)[1].lower()
        if ext not in ALLOWED_ATTACHMENT_EXTENSIONS:
            raise forms.ValidationError(
                f"Attachment type '{ext}' is not allowed. Use "
                f"{', '.join(sorted(ALLOWED_ATTACHMENT_EXTENSIONS))}.")
        if hasattr(f, "size") and f.size and f.size > MAX_ATTACHMENT_BYTES:
            raise forms.ValidationError(
                f"Attachment exceeds the {MAX_ATTACHMENT_BYTES // (1024 * 1024)} MB limit.")
        # WARNING: extension allowlist only — serve uploads with Content-Disposition: attachment
        # + X-Content-Type-Options: nosniff (mirrors the HRM onboarding-doc guard).
    return f


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

    def clean_attachment(self):
        return _validate_attachment(self.cleaned_data.get("attachment"))

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["supplier"])
        # CREATE-only gate: on edit ``__init__`` popped ``event`` (a response never moves
        # events), so an add_error("event", ...) would raise ValueError — and a save after the
        # event closed is legitimate evaluation work anyway; accepts_responses stops NEW bids.
        if self.instance.pk is None:
            event = cleaned.get("event")
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
            # Belt-and-braces defence: the ChoiceField normally rejects off-list values already;
            # this re-check survives a future field swap silently weakening that guarantee. Cheap,
            # and the side-by-side comparison's like-for-like premise depends on it.
            if value and question.answer_type == "choice" \
                    and value not in question.ordered_options():
                form.add_error("answer_text",
                               "Choose one of the listed options.")


RfxAnswerFormSet = inlineformset_factory(
    RfxResponse, RfxAnswer, form=RfxAnswerForm,
    formset=BaseRfxAnswerFormSet,
    extra=0, can_delete=False,
    # TOTAL_FORMS is client-supplied: without a cap a crafted POST makes Django validate
    # thousands of empty forms (CPU amplification) and spray unattached-row IntegrityErrors.
    max_num=60, validate_max=True,
)
