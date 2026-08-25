"""Procurement 6.6 - RFx Management security tests.

Tenant isolation is the spine: every pk route 404s another workspace's row, anonymous
users bounce to login, lifecycle verbs are POST-only and mutate nothing on GET, crafted
cross-tenant FK payloads land as field errors instead of smuggled links, STATUS_FLOW
(never the client) owns transitions, disqualified responses freeze, an event that
already collected responses cannot be mass-assigned into the Template Library, proposal
attachments pass an extension allowlist, the tenant-less superuser sees an empty
register, and the clone queryset accepts is_template=True rows only.
"""
import shutil
import tempfile
from decimal import Decimal
from pathlib import Path

import pytest

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, override_settings
from django.urls import reverse

from apps.procurement.models import RfxAnswer, RfxEvent, RfxQuestion, RfxResponse
from apps.scm.models import PurchaseRequisition

pytestmark = pytest.mark.django_db

#: The builder's inline formset default prefix (fk.related accessor name).
Q_FORMSET = {
    "questions-TOTAL_FORMS": "0",
    "questions-INITIAL_FORMS": "0",
    "questions-MIN_NUM_FORMS": "0",
    "questions-MAX_NUM_FORMS": "60",
}


# ------------------------------------------------------------------ local builders

def _party(tenant, name):
    from apps.core.models import Party
    return Party.objects.create(tenant=tenant, name=name, kind="organization")


def _event(tenant, user, **overrides):
    fields = dict(tenant=tenant, title="Acme vendor RFP", rfx_type="rfp",
                  status="draft", created_by=user)
    fields.update(overrides)
    return RfxEvent.objects.create(**fields)


def _question(event, prompt="Describe your support SLA.", order=1):
    return RfxQuestion.objects.create(event=event, prompt=prompt, answer_type="text",
                                      weight=Decimal("2.00"), is_scored=True,
                                      order=order)


def _response(event, supplier, status="draft", user=None):
    from django.utils import timezone
    rsp = RfxResponse.objects.create(
        tenant=event.tenant, event=event, supplier=supplier, status=status,
        recorded_by=user, notes="Our proposal covers every line.")
    if status != "draft":
        rsp.submitted_at = timezone.now()
        rsp.save(update_fields=["submitted_at"])
    return rsp


def _answer(response, question, text="24/7 with four-hour response.",
            score=Decimal("7.00")):
    return RfxAnswer.objects.create(response=response, question=question,
                                    answer_text=text, score=score)


@pytest.fixture
def foreign_rfx(tenant_b, admin_b):
    """Tenant B's mirror world: real event + question + submitted response + blueprint."""
    party = _party(tenant_b, "Globex Parts Co")
    event = _event(tenant_b, admin_b, title="Globex secret RFP")
    question = _question(event, "Globex-only prompt")
    response = _response(event, party, status="submitted", user=admin_b)
    _answer(response, question)
    template = _event(tenant_b, admin_b, title="Globex questionnaire blueprint",
                      is_template=True)
    return {"tenant": tenant_b, "admin": admin_b, "party": party, "event": event,
            "question": question, "response": response, "template": template}


@pytest.fixture
def isolated_media():
    """MEDIA_ROOT pointed at a throwaway dir so upload assertions can't touch the repo."""
    tmp = Path(tempfile.mkdtemp(prefix="naverp-rfx-media-"))
    with override_settings(MEDIA_ROOT=str(tmp)):
        yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------ IDOR matrix

def test_rfx_sec_idor_event_pk_routes_404(client_a, foreign_rfx):
    f = foreign_rfx
    routes = [
        ("rfx_detail", {"pk": f["event"].pk}, "get"),
        ("rfx_edit", {"pk": f["event"].pk}, "post"),
        ("rfx_delete", {"pk": f["event"].pk}, "post"),
        ("rfx_issue", {"pk": f["event"].pk}, "post"),
        ("rfx_close", {"pk": f["event"].pk}, "post"),
        ("rfx_cancel", {"pk": f["event"].pk}, "post"),
        ("rfx_compare", {"pk": f["event"].pk}, "get"),
        ("rfx_question_move", {"pk": f["event"].pk, "q_pk": f["question"].pk}, "post"),
        ("rfx_clone", {"pk": f["template"].pk}, "post"),
    ]
    for name, kwargs, verb in routes:
        url = reverse(f"procurement:{name}", kwargs=kwargs)
        data = {"direction": "up", "to": "x"} if verb == "post" else {}
        r = client_a.post(url, data) if verb == "post" else client_a.get(url)
        assert r.status_code == 404, name
    # Nothing moved while every door stayed shut.
    f["event"].refresh_from_db()
    assert f["event"].status == "draft"
    assert RfxEvent.objects.filter(tenant=f["tenant"]).count() == 2


def test_rfx_sec_idor_response_pk_routes_404(client_a, foreign_rfx):
    f = foreign_rfx
    routes = [
        ("rfx_response_detail", "get"),
        ("rfx_response_edit", "post"),
        ("rfx_response_delete", "post"),
        ("rfx_response_set_status", "post"),
    ]
    for name, verb in routes:
        url = reverse(f"procurement:{name}", kwargs={"pk": f["response"].pk})
        data = {"to": "scored"} if verb == "post" else {}
        r = client_a.post(url, data) if verb == "post" else client_a.get(url)
        assert r.status_code == 404, name
    f["response"].refresh_from_db()
    assert f["response"].status == "submitted"


# ------------------------------------------------------------------ anonymous access

def test_rfx_sec_anonymous_redirects_to_login(db, tenant_a, admin_user):
    event = _event(tenant_a, admin_user)
    anon = Client()
    login_url = reverse("accounts:login")
    targets = ["procurement:rfx_list", "procurement:rfx_scoring",
               "procurement:rfx_library", "procurement:rfx_response_list"]
    for name in targets:
        r = anon.get(reverse(name))
        assert r.status_code == 302, name
        assert r.url.startswith(login_url), name
    r = anon.get(reverse("procurement:rfx_detail", kwargs={"pk": event.pk}))
    assert r.status_code == 302
    assert r.url.startswith(login_url)


# ------------------------------------------------------------------ member vs admin writes

def test_rfx_sec_member_lifecycle_verbs_allowed_by_design(member_client, tenant_a,
                                                          admin_user):
    """These verbs carry no tenant-admin gate on purpose — pin what IS true."""
    party = _party(tenant_a, "Northwind Industrial Supply")
    event = _event(tenant_a, admin_user)
    _question(event)

    r = member_client.post(reverse("procurement:rfx_issue", kwargs={"pk": event.pk}))
    assert r.status_code == 302
    event.refresh_from_db()
    assert event.status == "issued"

    rsp = _response(event, party, status="draft", user=admin_user)
    r = member_client.post(reverse("procurement:rfx_response_set_status",
                                   kwargs={"pk": rsp.pk}), {"to": "submitted"})
    assert r.status_code == 302
    rsp.refresh_from_db()
    assert rsp.status == "submitted"
    assert rsp.submitted_at is not None


def test_rfx_sec_member_can_delete_draft_response_only(member_client, tenant_a,
                                                       admin_user):
    party_a = _party(tenant_a, "Northwind Industrial Supply")
    party_b = _party(tenant_a, "Apex Packaging Co")
    event = _event(tenant_a, admin_user)

    draft = _response(event, party_a, status="draft")
    r = member_client.post(reverse("procurement:rfx_response_delete",
                                   kwargs={"pk": draft.pk}))
    assert r.status_code == 302
    assert not RfxResponse.objects.filter(pk=draft.pk).exists()

    submitted = _response(event, party_b, status="submitted")  # repository keeps bids
    r = member_client.post(reverse("procurement:rfx_response_delete",
                                   kwargs={"pk": submitted.pk}))
    assert r.status_code == 302
    assert RfxResponse.objects.filter(pk=submitted.pk).exists()


# ------------------------------------------------------------------ GET never mutates

def test_rfx_sec_get_never_mutates_state(client_a, tenant_a, admin_user):
    party = _party(tenant_a, "Northwind Industrial Supply")
    draft_event = _event(tenant_a, admin_user)
    q1 = _question(draft_event, order=1)
    _question(draft_event, "Second prompt", order=2)
    issued_event = _event(tenant_a, admin_user, title="Acme issued RFP",
                          status="issued")
    template = _event(tenant_a, admin_user, title="Acme blueprint", is_template=True)
    rsp = _response(issued_event, party, status="under_review")

    events_before = sorted(RfxEvent.objects.values_list("pk", "status"))
    orders_before = list(RfxQuestion.objects.order_by("id")
                         .values_list("pk", "order"))
    responses_before = sorted(RfxResponse.objects.values_list("pk", "status"))

    verbs = [
        ("rfx_issue", {"pk": draft_event.pk}),
        ("rfx_close", {"pk": issued_event.pk}),
        ("rfx_cancel", {"pk": issued_event.pk}),
        ("rfx_delete", {"pk": template.pk}),
        ("rfx_clone", {"pk": template.pk}),
        ("rfx_question_move", {"pk": draft_event.pk, "q_pk": q1.pk}),
        ("rfx_response_set_status", {"pk": rsp.pk}),
        ("rfx_response_delete", {"pk": rsp.pk}),
    ]
    for name, kwargs in verbs:
        r = client_a.get(reverse(f"procurement:{name}", kwargs=kwargs))
        assert r.status_code == 405, name  # @require_POST refuses GET outright

    assert sorted(RfxEvent.objects.values_list("pk", "status")) == events_before
    assert list(RfxQuestion.objects.order_by("id").values_list("pk", "order")) \
        == orders_before
    assert sorted(RfxResponse.objects.values_list("pk", "status")) == responses_before


# ------------------------------------------------------------------ FK poisoning

def test_rfx_sec_foreign_supplier_rejected_on_response_create(client_a, tenant_a,
                                                              tenant_b, admin_user,
                                                              admin_b):
    own_event = _event(tenant_a, admin_user)
    _question(own_event)
    foreign_party = _party(tenant_b, "Globex Parts Co")

    r = client_a.post(reverse("procurement:rfx_response_create"), {
        "event": str(own_event.pk),
        "supplier": str(foreign_party.pk),
        "notes": "smuggled bid",
    })
    assert r.status_code == 200                      # re-rendered with field errors
    assert "supplier" in r.context["form"].errors
    assert RfxResponse.objects.count() == 0          # no row, no pre-created answers
    assert RfxAnswer.objects.count() == 0


def test_rfx_sec_foreign_requisition_rejected_on_event_create(client_a, tenant_a,
                                                              tenant_b, admin_b):
    foreign_pr = PurchaseRequisition.objects.create(
        tenant=tenant_b, title="Globex private PR", requester=admin_b,
        status="pending_approval")
    before = RfxEvent.objects.filter(tenant=tenant_a).count()

    r = client_a.post(reverse("procurement:rfx_create"), {
        "title": "Smuggled-link RFP", "rfx_type": "rfp", "description": "",
        "requisition": str(foreign_pr.pk), "response_due": "", **Q_FORMSET,
    })
    assert r.status_code == 200
    assert "requisition" in r.context["form"].errors
    assert RfxEvent.objects.filter(tenant=tenant_a).count() == before
    assert not RfxEvent.objects.filter(title="Smuggled-link RFP").exists()


# ------------------------------------------------------------------ filter-param leak

def test_rfx_sec_response_list_filter_param_leaks_nothing(client_a, tenant_a,
                                                          admin_user, foreign_rfx):
    f = foreign_rfx
    party = _party(tenant_a, "Northwind Industrial Supply")
    own_event = _event(tenant_a, admin_user)
    _question(own_event)
    _response(own_event, party, status="submitted")

    r = client_a.get(reverse("procurement:rfx_response_list")
                     + f"?event={f['event'].pk}")
    assert r.status_code == 200
    body = r.content.decode()
    assert f["response"].number not in body
    assert "Globex Parts Co" not in body


# ------------------------------------------------------------------ STATUS_FLOW server-side

def test_rfx_sec_set_status_refuses_crafted_and_garbage_targets(client_a, tenant_a,
                                                                admin_user):
    party = _party(tenant_a, "Northwind Industrial Supply")
    event = _event(tenant_a, admin_user, status="issued")
    rsp = _response(event, party, status="draft")
    url = reverse("procurement:rfx_response_set_status", kwargs={"pk": rsp.pk})

    r = client_a.post(url, {"to": "scored"})         # draft -> scored skips three gates
    assert r.status_code == 302
    rsp.refresh_from_db()
    assert rsp.status == "draft"

    r = client_a.post(url, {"to": "root@localhost"})  # not a status at all
    assert r.status_code == 302
    rsp.refresh_from_db()
    assert rsp.status == "draft"
    assert rsp.submitted_at is None


def test_rfx_sec_disqualified_response_frozen_against_edit_post(client_a, tenant_a,
                                                                admin_user):
    party = _party(tenant_a, "Northwind Industrial Supply")
    event = _event(tenant_a, admin_user, status="issued")
    question = _question(event)
    rsp = _response(event, party, status="disqualified")
    ans = _answer(rsp, question, "Original answer text")

    r = client_a.post(reverse("procurement:rfx_response_edit",
                              kwargs={"pk": rsp.pk}), {
        "notes": "tampered cover note",
        "answers-TOTAL_FORMS": "1",
        "answers-INITIAL_FORMS": "1",
        "answers-MIN_NUM_FORMS": "0",
        "answers-MAX_NUM_FORMS": "60",
        "answers-0-id": str(ans.pk),
        "answers-0-answer_text": "HACKED",
        "answers-0-score": "10",
    })
    assert r.status_code == 302                      # bounced back to the detail page
    rsp.refresh_from_db()
    assert rsp.notes != "tampered cover note"
    ans.refresh_from_db()
    assert ans.answer_text == "Original answer text"
    assert ans.score == Decimal("7.00")


# ------------------------------------------------------------------ mass assignment

def test_rfx_sec_is_template_mass_assignment_blocked_with_responses(client_a, tenant_a,
                                                                    admin_user):
    party = _party(tenant_a, "Northwind Industrial Supply")
    event = _event(tenant_a, admin_user, description="working copy")
    _question(event)
    _response(event, party, status="submitted")

    r = client_a.post(reverse("procurement:rfx_edit", kwargs={"pk": event.pk}), {
        "title": event.title, "rfx_type": "rfp", "description": "retrofitted",
        "requisition": "", "response_due": "", "is_template": "on", **Q_FORMSET,
    })
    assert r.status_code == 200                      # refused with a field error
    assert "is_template" in r.context["form"].errors
    event.refresh_from_db()
    assert event.is_template is False
    assert event.description == "working copy"       # the whole POST was dropped


# ------------------------------------------------------------------ attachment uploads

def _upload_post(client, event, party, filename, content):
    return client.post(reverse("procurement:rfx_response_create"), {
        "event": str(event.pk), "supplier": str(party.pk), "notes": "n",
        "attachment": SimpleUploadedFile(filename, content),
    })


def test_rfx_sec_attachment_html_and_exe_rejected(client_a, tenant_a, admin_user,
                                                  isolated_media):
    party = _party(tenant_a, "Northwind Industrial Supply")
    event = _event(tenant_a, admin_user)
    _question(event)

    for name, blob in (("proposal.html", b"<script>alert(1)</script>"),
                       ("tool.exe", b"MZ\x90\x00\x01")):
        r = _upload_post(client_a, event, party, name, blob)
        assert r.status_code == 200, name
        assert "attachment" in r.context["form"].errors, name

    assert RfxResponse.objects.count() == 0
    assert list(isolated_media.rglob("*")) == []     # nothing written under media/


def test_rfx_sec_attachment_pdf_accepted(client_a, tenant_a, admin_user,
                                         isolated_media):
    party = _party(tenant_a, "Northwind Industrial Supply")
    event = _event(tenant_a, admin_user)
    _question(event)

    r = _upload_post(client_a, event, party, "proposal.pdf", b"%PDF-1.4 fake body")
    assert r.status_code == 302
    rsp = RfxResponse.objects.get(event=event, supplier=party)
    stored = [p for p in isolated_media.rglob("*") if p.is_file()]
    assert len(stored) == 1
    assert stored[0].read_bytes().startswith(b"%PDF")
    rsp.attachment.delete(save=False)                # tidy the throwaway store


# ------------------------------------------------------------------ superuser isolation

def test_rfx_sec_tenantless_superuser_sees_empty_register(tenant_a, admin_user):
    from apps.accounts.models import User

    event = _event(tenant_a, admin_user)
    template = _event(tenant_a, admin_user, title="Acme internal blueprint",
                      is_template=True)

    su = User.objects.create_superuser(email="root@naverp.local", username="root",
                                       password="TestPass123!")
    c = Client()
    c.force_login(su)
    for url in (reverse("procurement:rfx_list"), reverse("procurement:rfx_library")):
        r = c.get(url)
        assert r.status_code == 200, url
        body = r.content.decode()
        assert event.title not in body, url
        assert event.number not in body, url
        assert template.title not in body, url


# ------------------------------------------------------------------ clone queryset gate

def test_rfx_sec_clone_route_refuses_non_template(client_a, tenant_a, admin_user):
    plain = _event(tenant_a, admin_user)
    _question(plain)
    before = RfxEvent.objects.count()

    r = client_a.post(reverse("procurement:rfx_clone", kwargs={"pk": plain.pk}))
    assert r.status_code == 404                      # queryset filters is_template=True
    assert RfxEvent.objects.count() == before

    plain.is_template = True                         # positive control: same pk now works
    plain.save(update_fields=["is_template"])
    r = client_a.post(reverse("procurement:rfx_clone", kwargs={"pk": plain.pk}))
    assert r.status_code == 302
    assert RfxEvent.objects.count() == before + 1
    clone = RfxEvent.objects.exclude(pk=plain.pk).get()
    assert clone.is_template is False
    assert clone.status == "draft"
