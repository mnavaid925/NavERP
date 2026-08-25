"""Procurement 6.6 - RFx Management form tests.

The builder/response forms are the crafted-POST boundary: foreign FKs land field errors,
an issued event's questionnaire is locked, template-ticking is refused once responses exist,
attachments pass an extension allowlist + size cap, and the answer grid mirrors the event's
questions exactly - including surviving a tampered POST that strips a row's id hidden field.
"""
import datetime

import pytest
from django import forms
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from apps.core.models import Party
from apps.procurement.forms import (
    RfxAnswerFormSet,
    RfxEventForm,
    RfxQuestionForm,
    RfxQuestionFormSet,
    RfxResponseForm,
)
from apps.procurement.forms.RfxManagement.Responses import (
    MAX_ATTACHMENT_BYTES,
    _validate_attachment,
)
from apps.procurement.models import RfxAnswer, RfxEvent, RfxQuestion, RfxResponse
from apps.scm.models import PurchaseRequisition

pytestmark = pytest.mark.django_db


# -- local builders -----------------------------------------------------------------------------------

def _event(tenant, status="draft", **overrides):
    fields = dict(tenant=tenant, title="Vendor capability survey",
                  rfx_type="rfp", status=status)
    fields.update(overrides)
    return RfxEvent.objects.create(**fields)


def _question(event, prompt="Describe your QC process?", order=1, **overrides):
    fields = dict(event=event, prompt=prompt, order=order, answer_type="text")
    fields.update(overrides)
    return RfxQuestion.objects.create(**fields)


def _party(tenant, name):
    return Party.objects.create(tenant=tenant, name=name, kind="organization")


def _response(event, party, **overrides):
    fields = dict(tenant=event.tenant, event=event, supplier=party)
    fields.update(overrides)
    return RfxResponse.objects.create(**fields)


def _answer(response, question, **overrides):
    fields = dict(response=response, question=question)
    fields.update(overrides)
    return RfxAnswer.objects.create(**fields)


def _mgmt(prefix, total, initial, max_num=60):
    return {
        f"{prefix}-TOTAL_FORMS": str(total),
        f"{prefix}-INITIAL_FORMS": str(initial),
        f"{prefix}-MIN_NUM_FORMS": "0",
        f"{prefix}-MAX_NUM_FORMS": str(max_num),
    }


class _DeclaredSizeUpload(SimpleUploadedFile):
    """Tiny in-memory payload that declares a huge size - crosses the cap without allocating."""

    def __init__(self, name, declared_size):
        super().__init__(name=name, content=b"%PDF-1.4 tiny")
        self._declared_size = declared_size

    @property
    def size(self):
        return self._declared_size

    @size.setter
    def size(self, value):
        pass  # UploadFile.__init__ writes the real byte count; the declaration wins here


# -- 1. event header form -----------------------------------------------------------------------------

def test_rfx_event_form_valid_save_stamps_tenant_number_and_status(tenant_a, admin_user):
    data = {
        "title": "Office fit-out RFP",
        "rfx_type": "rfp",
        "description": "Structured questionnaire across technical and commercial sections.",
        "response_due": (timezone.now() + datetime.timedelta(days=14)).strftime("%Y-%m-%dT%H:%M"),
    }
    form = RfxEventForm(data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    event = form.save(commit=False)          # views stamp tenant/user AFTER commit=False
    event.tenant = tenant_a
    event.created_by = admin_user
    event.save()
    assert event.number.startswith("RFX")
    assert event.tenant_id == tenant_a.pk
    assert event.status == "draft"
    assert event.is_editable and event.accepts_responses


def test_rfx_event_form_requires_title(tenant_a):
    form = RfxEventForm({"rfx_type": "rfi"}, tenant=tenant_a)
    assert not form.is_valid()
    assert "title" in form.errors


def test_rfx_event_form_rfx_type_choices(tenant_a):
    form = RfxEventForm(tenant=tenant_a)
    assert list(form.fields["rfx_type"].choices) == list(RfxEvent.RFX_TYPES)
    assert len(form.fields["rfx_type"].choices) == 3  # rfi / rfp / rfq
    bad = RfxEventForm({"title": "Bogus type", "rfx_type": "xxx"}, tenant=tenant_a)
    assert not bad.is_valid()
    assert "rfx_type" in bad.errors


# -- 2. foreign requisition ---------------------------------------------------------------------------

def test_rfx_event_form_rejects_foreign_requisition(tenant_a, tenant_b, admin_b):
    foreign = PurchaseRequisition.objects.create(
        tenant=tenant_b, title="Globex internal restock", requester=admin_b,
        required_by=datetime.date.today() + datetime.timedelta(days=10))
    form = RfxEventForm({
        "title": "Cross-workspace sourcing attempt", "rfx_type": "rfq",
        "requisition": str(foreign.pk),
    }, tenant=tenant_a)
    assert not form.is_valid()
    assert "requisition" in form.errors


# -- 3. template-library guard ------------------------------------------------------------------------

def test_rfx_event_form_is_template_refused_once_responses_exist(tenant_a):
    event = _event(tenant_a)
    _response(event, _party(tenant_a, "Northwind Industrial Supply"))
    form = RfxEventForm({
        "title": "Vendor capability survey", "rfx_type": "rfp", "is_template": "on",
    }, instance=event, tenant=tenant_a)
    assert not form.is_valid()
    assert "is_template" in form.errors


def test_rfx_event_form_is_template_allowed_without_responses(tenant_a):
    event = _event(tenant_a, title="Standard RFP pack", rfx_type="rfp")
    form = RfxEventForm({
        "title": "Standard RFP pack", "rfx_type": "rfp", "is_template": "on",
    }, instance=event, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["is_template"] is True


# -- 4. question form ---------------------------------------------------------------------------------

def test_rfx_question_form_choice_requires_options(tenant_a):
    form = RfxQuestionForm({
        "section": "Technical", "prompt": "Preferred support tier?", "help_text": "",
        "answer_type": "choice", "options": "", "weight": "1.00", "is_scored": "on",
    }, tenant=tenant_a)
    assert not form.is_valid()
    assert "options" in form.errors
    assert any("option" in message.lower() for message in form.errors["options"])


def test_rfx_question_form_non_choice_blanks_stored_options(tenant_a):
    form = RfxQuestionForm({
        "section": "", "prompt": "Annual volume forecast?", "help_text": "",
        "answer_type": "text", "options": "Stale option\r\nAnother stale",
        "weight": "2.00", "is_scored": "on",
    }, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["options"] == ""
    obj = form.save(commit=False)
    assert obj.options == ""


def test_rfx_question_form_rejects_negative_weight(tenant_a):
    form = RfxQuestionForm({
        "section": "", "prompt": "Any question", "help_text": "",
        "answer_type": "text", "options": "", "weight": "-1.00", "is_scored": "on",
    }, tenant=tenant_a)
    assert not form.is_valid()
    assert "weight" in form.errors


def test_rfx_question_form_accepts_tenant_kwarg(tenant_a):
    form = RfxQuestionForm(tenant=tenant_a)
    assert form.tenant is tenant_a
    assert set(form.fields) == {
        "section", "prompt", "help_text", "answer_type", "options", "weight", "is_scored"}
    assert "order" not in form.fields  # order is assigned by the formset / move action


# -- 5/6. question formset: lock guard + append ordering ----------------------------------------------

def test_rfx_question_formset_rejects_issued_event(tenant_a):
    event = _event(tenant_a)
    _question(event)
    assert event.issue()
    prefix = RfxQuestionFormSet.get_default_prefix()
    data = _mgmt(prefix, total=2, initial=0)
    data.update({
        f"{prefix}-0-section": "Commercial", f"{prefix}-0-prompt": "Tampered pricing row?",
        f"{prefix}-0-answer_type": "text", f"{prefix}-0-weight": "1.00",
        f"{prefix}-1-section": "", f"{prefix}-1-prompt": "Second tampered row?",
        f"{prefix}-1-answer_type": "text", f"{prefix}-1-weight": "1.00",
    })
    formset = RfxQuestionFormSet(data, instance=event)
    assert not formset.is_valid()
    non_form = formset.non_form_errors()
    assert non_form and any("locked" in str(message) for message in non_form)


def test_rfx_question_formset_draft_passes_and_appends_orders(tenant_a):
    event = _event(tenant_a)
    first = _question(event, prompt="Existing first question", order=1)

    unbound = RfxQuestionFormSet(instance=event)  # render step: 1 initial + 2 extras
    assert len(unbound.forms) == 3

    prefix = RfxQuestionFormSet.get_default_prefix()
    data = _mgmt(prefix, total=2, initial=0)
    data.update({
        f"{prefix}-0-section": "Commercial", f"{prefix}-0-prompt": "Pricing terms accepted?",
        f"{prefix}-0-answer_type": "text", f"{prefix}-0-weight": "2.00",
        f"{prefix}-1-section": "Logistics", f"{prefix}-1-prompt": "Delivery window?",
        f"{prefix}-1-answer_type": "choice", f"{prefix}-1-options": "4 weeks\n6 weeks",
        f"{prefix}-1-weight": "1.50",
    })
    formset = RfxQuestionFormSet(data, instance=event)
    assert formset.is_valid(), (formset.errors, formset.non_form_errors())
    formset.save()

    rows = list(event.questions.order_by("order"))
    assert [row.order for row in rows] == [1, 2, 3]
    assert rows[0].pk == first.pk
    assert rows[1].prompt == "Pricing terms accepted?"
    assert rows[2].prompt == "Delivery window?"


# -- 7. response form ---------------------------------------------------------------------------------

def test_rfx_response_form_fields_on_create_vs_edit(tenant_a):
    create_form = RfxResponseForm(tenant=tenant_a)
    assert set(create_form.fields) == {"event", "supplier", "notes", "attachment"}

    event = _event(tenant_a)
    response = _response(event, _party(tenant_a, "Northwind Industrial Supply"))
    edit_form = RfxResponseForm(instance=response, tenant=tenant_a)
    assert "event" not in edit_form.fields


def test_rfx_response_form_accepts_responses_gate_is_create_only(tenant_a):
    holder = _party(tenant_a, "Northwind Industrial Supply")
    newcomer = _party(tenant_a, "Apex Packaging Co")
    closed = _event(tenant_a, status="closed")
    existing = _response(closed, holder)

    edit = RfxResponseForm(
        {"supplier": str(holder.pk), "notes": "Evaluation notes finalised."},
        instance=existing, tenant=tenant_a)
    assert edit.is_valid(), edit.errors

    fresh = RfxResponseForm(
        {"event": str(closed.pk), "supplier": str(newcomer.pk)}, tenant=tenant_a)
    assert not fresh.is_valid()
    assert "event" in fresh.errors
    assert any("open" in message for message in fresh.errors["event"])


def test_rfx_response_form_rejects_foreign_supplier(tenant_a, tenant_b):
    event = _event(tenant_a)
    foreign = _party(tenant_b, "Globex Parts Co")
    form = RfxResponseForm(
        {"event": str(event.pk), "supplier": str(foreign.pk)}, tenant=tenant_a)
    assert not form.is_valid()
    assert "supplier" in form.errors


def test_rfx_response_form_rejects_duplicate_event_supplier(tenant_a):
    party = _party(tenant_a, "Northwind Industrial Supply")
    event = _event(tenant_a)
    _response(event, party)
    form = RfxResponseForm(
        {"event": str(event.pk), "supplier": str(party.pk)}, tenant=tenant_a)
    assert not form.is_valid()
    assert form.non_field_errors()


# -- 8. attachment guard ------------------------------------------------------------------------------

def test_rfx_attachment_extension_allowlist():
    for name in ("payload.exe", "exploit.html"):
        with pytest.raises(ValidationError) as excinfo:
            _validate_attachment(SimpleUploadedFile(name, b"<script>alert(1)</script>"))
        assert f".{name.rsplit('.', 1)[1]}" in str(excinfo.value)
    good = SimpleUploadedFile("proposal.pdf", b"%PDF-1.4")
    assert _validate_attachment(good) is good


def test_rfx_attachment_size_cap():
    with pytest.raises(ValidationError) as excinfo:
        _validate_attachment(_DeclaredSizeUpload("proposal.pdf", MAX_ATTACHMENT_BYTES + 1))
    assert "MB" in str(excinfo.value)
    at_cap = _validate_attachment(_DeclaredSizeUpload("proposal.pdf", MAX_ATTACHMENT_BYTES))
    assert at_cap.size == MAX_ATTACHMENT_BYTES


def test_rfx_response_form_good_pdf_passes(tenant_a):
    party = _party(tenant_a, "Northwind Industrial Supply")
    event = _event(tenant_a)
    upload = SimpleUploadedFile("proposal.pdf", b"%PDF-1.4\n% NavERP test proposal")
    form = RfxResponseForm(
        {"event": str(event.pk), "supplier": str(party.pk), "notes": "Proposal attached."},
        {"attachment": upload}, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["attachment"].read().startswith(b"%PDF")


# -- 9/10. answer grid --------------------------------------------------------------------------------

def test_rfx_answer_formset_grid_shape_and_caps():
    assert RfxAnswerFormSet.extra == 0
    assert RfxAnswerFormSet.can_delete is False
    assert RfxAnswerFormSet.max_num == 60
    assert RfxAnswerFormSet.validate_max is True


def test_rfx_answer_formset_rejects_more_than_sixty_rows(tenant_a):
    event = _event(tenant_a)
    question = _question(event)
    response = _response(event, _party(tenant_a, "Northwind Industrial Supply"))
    answer = _answer(response, question)

    prefix = RfxAnswerFormSet.get_default_prefix()
    data = _mgmt(prefix, total=61, initial=1)
    data[f"{prefix}-0-id"] = str(answer.pk)
    data[f"{prefix}-0-answer_text"] = "ISO 9001 certified."
    data[f"{prefix}-0-score"] = "8"
    formset = RfxAnswerFormSet(data, instance=response)
    assert not formset.is_valid()
    non_form = formset.non_form_errors()
    assert non_form and any("60" in str(message) for message in non_form)


def test_rfx_answer_formset_widgets_adapt_to_question_type(tenant_a):
    event = _event(tenant_a)
    long_q = _question(event, prompt="Describe implementation plan?",
                       answer_type="longtext", order=1)
    choice_q = _question(event, prompt="Preferred start quarter?",
                         answer_type="choice", options="Q1\nQ2\nQ3", order=2)
    text_q = _question(event, prompt="Primary contact email?", order=3)
    response = _response(event, _party(tenant_a, "Northwind Industrial Supply"))
    for question in (long_q, choice_q, text_q):
        _answer(response, question)

    formset = RfxAnswerFormSet(instance=response)
    assert len(formset.forms) == 3  # extra=0 -> exactly one row per question
    by_question = {form.instance.question_id: form for form in formset.forms}

    long_widget = by_question[long_q.pk].fields["answer_text"].widget
    assert isinstance(long_widget, forms.Textarea)
    assert long_widget.attrs["rows"] == 3
    assert long_widget.attrs["class"] == "form-textarea"

    choice_field = by_question[choice_q.pk].fields["answer_text"]
    assert isinstance(choice_field, forms.ChoiceField)
    assert list(choice_field.choices) == [("", "---")] + [
        (option, option) for option in choice_q.ordered_options()]

    # Short text stays the model-default CharField/Textarea - adapted types only.
    text_field = by_question[text_q.pk].fields["answer_text"]
    assert isinstance(text_field, forms.CharField)
    assert not isinstance(text_field, forms.ChoiceField)
    assert text_field.widget.attrs == {"cols": "40", "rows": "10"}  # untouched defaults


def test_rfx_answer_formset_missing_row_id_fails_cleanly(tenant_a):
    event = _event(tenant_a)
    question = _question(event)
    response = _response(event, _party(tenant_a, "Northwind Industrial Supply"))
    _answer(response, question)

    prefix = RfxAnswerFormSet.get_default_prefix()
    data = _mgmt(prefix, total=1, initial=1)
    data[f"{prefix}-0-answer_text"] = "42 units per month"
    data[f"{prefix}-0-score"] = "9"
    # NOTE: {prefix}-0-id is deliberately absent - a crafted POST with identity stripped.

    try:
        formset = RfxAnswerFormSet(data, instance=response)
        valid = formset.is_valid()
    except Exception as exc:  # noqa: BLE001 - the whole point is that nothing escapes
        pytest.fail(f"validation crashed on a row missing its id hidden field: {exc!r}")
    assert not valid
    assert formset.errors and "id" in formset.errors[0]
