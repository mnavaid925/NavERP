"""Tests for CRM sub-module 1.9 — Document & Contract Management.

Covers:
  - DocumentVersion unique_together(tenant, contract, version_no); ordering -version_no; __str__
  - contractdocument_generate: template rendering, v1/v2 creation, draft-only guard,
    no-template guard, malformed template → redirect+message (no 500, no version)
  - SSTI sandbox: safe/autoescape/include/load blocked; XSS-char in context escaped
  - contractdocument_version_add: valid upload, disallowed extension, empty form, signed guard
  - contractdocument_send: draft+body+signer → sent; no signer blocked; no body blocked; non-draft blocked
  - Privilege: doctemplate_create/edit/delete blocked for non-admin member; allowed for admin
  - document_repository: 200, tenant isolation, version_count annotation, filter by status/account
  - Multi-tenant IDOR: cross-tenant documentversion_detail / contractdocument_detail → 404;
    generate/version_add/send on foreign contract → 404
  - Query-count: document_repository bounded (no N+1)
"""
import secrets
import datetime

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

pytestmark = pytest.mark.django_db


# ========================================================================== helpers / factories

def _make_party(tenant, name="Acme Ltd", kind="organization"):
    from apps.core.models import Party
    return Party.objects.create(tenant=tenant, kind=kind, name=name)


def _make_opportunity(tenant, account, name="Big Deal", amount="5000.00"):
    from apps.crm.models import Opportunity
    return Opportunity.objects.create(
        tenant=tenant,
        name=name,
        account=account,
        stage="prospecting",
        amount=amount,
        probability=20,
    )


def _make_doctemplate(tenant, name="NDA Template", body="Hello {{ account.name }}", is_active=True):
    from apps.crm.models import DocTemplate
    return DocTemplate.objects.create(
        tenant=tenant,
        name=name,
        template_type="contract",
        body=body,
        is_active=is_active,
    )


def _make_contract(tenant, account=None, opportunity=None, template=None,
                   name="Service Contract", status="draft", body_snapshot=""):
    from apps.crm.models import ContractDocument
    return ContractDocument.objects.create(
        tenant=tenant,
        name=name,
        template=template,
        account=account,
        opportunity=opportunity,
        status=status,
        body_snapshot=body_snapshot,
    )


def _make_signer(tenant, contract, name="Alice Signer", email="alice@example.com"):
    from apps.crm.models import SignerRecord
    return SignerRecord.objects.create(
        tenant=tenant,
        contract=contract,
        signer_name=name,
        signer_email=email,
        token=secrets.token_urlsafe(32)[:64],
        order=1,
    )


def _make_version(tenant, contract, version_no=1, body_snapshot="<p>body</p>", change_note="init"):
    from apps.crm.models import DocumentVersion
    return DocumentVersion.objects.create(
        tenant=tenant,
        contract=contract,
        version_no=version_no,
        body_snapshot=body_snapshot,
        change_note=change_note,
    )


# ========================================================================== Group 1 — Models

class TestDocumentVersionModel:
    def test_unique_together_tenant_contract_version_no(self, tenant_a):
        from django.db import IntegrityError
        from apps.crm.models import DocumentVersion
        account = _make_party(tenant_a)
        contract = _make_contract(tenant_a, account=account)
        _make_version(tenant_a, contract, version_no=1)
        with pytest.raises(IntegrityError):
            DocumentVersion.objects.create(
                tenant=tenant_a,
                contract=contract,
                version_no=1,   # duplicate → must fail
                body_snapshot="dup",
                change_note="dup",
            )

    def test_ordering_descending_version_no(self, tenant_a):
        from apps.crm.models import DocumentVersion
        account = _make_party(tenant_a)
        contract = _make_contract(tenant_a, account=account)
        _make_version(tenant_a, contract, version_no=1)
        _make_version(tenant_a, contract, version_no=2)
        _make_version(tenant_a, contract, version_no=3)
        pks_ordered = list(
            DocumentVersion.objects.filter(tenant=tenant_a, contract=contract)
            .values_list("version_no", flat=True)
        )
        assert pks_ordered == [3, 2, 1]

    def test_str_contains_contract_number_and_version_no(self, tenant_a):
        account = _make_party(tenant_a)
        contract = _make_contract(tenant_a, account=account)
        ver = _make_version(tenant_a, contract, version_no=1)
        s = str(ver)
        assert contract.number in s
        assert "1" in s

    def test_different_contracts_same_version_no_allowed(self, tenant_a):
        """Two different contracts can each have version_no=1 — the unique_together uses contract FK."""
        from apps.crm.models import DocumentVersion
        account = _make_party(tenant_a)
        c1 = _make_contract(tenant_a, account=account, name="Contract 1")
        c2 = _make_contract(tenant_a, account=account, name="Contract 2")
        v1 = _make_version(tenant_a, c1, version_no=1)
        v2 = _make_version(tenant_a, c2, version_no=1)
        assert v1.pk != v2.pk

    def test_unique_together_scoped_to_tenant(self, tenant_a, tenant_b):
        """tenant_a and tenant_b can each have the same contract+version_no combination."""
        from apps.crm.models import DocumentVersion
        acc_a = _make_party(tenant_a)
        acc_b = _make_party(tenant_b, name="Corp B")
        c_a = _make_contract(tenant_a, account=acc_a)
        c_b = _make_contract(tenant_b, account=acc_b)
        _make_version(tenant_a, c_a, version_no=1)
        # Different tenant → same version_no is fine
        v_b = DocumentVersion.objects.create(
            tenant=tenant_b, contract=c_b, version_no=1,
            body_snapshot="b", change_note="b",
        )
        assert v_b.pk is not None


# ========================================================================== Group 2 — Document Generation

class TestContractDocumentGenerate:
    """Tests for contractdocument_generate — the headline SSTI-safe merge feature."""

    def _setup(self, tenant_a, body="Client {{ account.name }} deal {{ opportunity.amount }} on {{ today }}"):
        account = _make_party(tenant_a, name="Wayne Enterprises")
        opp = _make_opportunity(tenant_a, account, amount="99000.00")
        tpl = _make_doctemplate(tenant_a, body=body)
        contract = _make_contract(tenant_a, account=account, opportunity=opp, template=tpl)
        return contract, account, opp

    def test_generate_returns_302(self, client_a, tenant_a):
        contract, _, _ = self._setup(tenant_a)
        url = reverse("crm:contractdocument_generate", args=[contract.pk])
        resp = client_a.post(url)
        assert resp.status_code == 302

    def test_generate_creates_version_v1(self, client_a, tenant_a):
        from apps.crm.models import DocumentVersion
        contract, _, _ = self._setup(tenant_a)
        client_a.post(reverse("crm:contractdocument_generate", args=[contract.pk]))
        assert DocumentVersion.objects.filter(tenant=tenant_a, contract=contract, version_no=1).exists()

    def test_generate_body_contains_account_name(self, client_a, tenant_a):
        contract, account, _ = self._setup(tenant_a)
        client_a.post(reverse("crm:contractdocument_generate", args=[contract.pk]))
        contract.refresh_from_db()
        assert account.name in contract.body_snapshot

    def test_generate_body_contains_opportunity_amount(self, client_a, tenant_a):
        contract, _, opp = self._setup(tenant_a)
        client_a.post(reverse("crm:contractdocument_generate", args=[contract.pk]))
        contract.refresh_from_db()
        assert str(opp.amount) in contract.body_snapshot

    def test_generate_body_contains_today(self, client_a, tenant_a):
        contract, _, _ = self._setup(tenant_a)
        today = timezone.localdate().isoformat()
        client_a.post(reverse("crm:contractdocument_generate", args=[contract.pk]))
        contract.refresh_from_db()
        assert today in contract.body_snapshot

    def test_generate_no_literal_double_braces(self, client_a, tenant_a):
        contract, _, _ = self._setup(tenant_a)
        client_a.post(reverse("crm:contractdocument_generate", args=[contract.pk]))
        contract.refresh_from_db()
        assert "{{" not in contract.body_snapshot

    def test_generate_bumps_current_version(self, client_a, tenant_a):
        contract, _, _ = self._setup(tenant_a)
        client_a.post(reverse("crm:contractdocument_generate", args=[contract.pk]))
        contract.refresh_from_db()
        assert contract.current_version == 1

    def test_regenerate_creates_v2(self, client_a, tenant_a):
        from apps.crm.models import DocumentVersion
        contract, _, _ = self._setup(tenant_a)
        url = reverse("crm:contractdocument_generate", args=[contract.pk])
        client_a.post(url)  # v1
        client_a.post(url)  # v2
        contract.refresh_from_db()
        assert contract.current_version == 2
        assert DocumentVersion.objects.filter(tenant=tenant_a, contract=contract).count() == 2

    def test_generate_blocked_when_not_draft(self, client_a, tenant_a):
        """A non-draft contract must block generation — body_snapshot unchanged, no version created."""
        from apps.crm.models import DocumentVersion
        contract, _, _ = self._setup(tenant_a)
        contract.status = "sent"
        contract.save(update_fields=["status", "updated_at"])
        initial_count = DocumentVersion.objects.filter(contract=contract).count()
        client_a.post(reverse("crm:contractdocument_generate", args=[contract.pk]))
        assert DocumentVersion.objects.filter(contract=contract).count() == initial_count

    def test_generate_blocked_when_no_template(self, client_a, tenant_a):
        """No linked template → redirect + message, no version created."""
        from apps.crm.models import DocumentVersion
        account = _make_party(tenant_a)
        contract = _make_contract(tenant_a, account=account, template=None)
        url = reverse("crm:contractdocument_generate", args=[contract.pk])
        resp = client_a.post(url)
        assert resp.status_code == 302
        assert DocumentVersion.objects.filter(contract=contract).count() == 0

    def test_malformed_template_redirects_no_version_no_500(self, client_a, tenant_a):
        """A bad template body ({% if %} with no condition) must catch the error and redirect."""
        from apps.crm.models import DocumentVersion
        # Bad Jinja-like syntax that Django template will reject
        contract, _, _ = self._setup(tenant_a, body="{% if %} unclosed")
        url = reverse("crm:contractdocument_generate", args=[contract.pk])
        resp = client_a.post(url)
        # Must redirect (302), NOT 500
        assert resp.status_code == 302
        assert DocumentVersion.objects.filter(contract=contract).count() == 0

    def test_generate_anon_redirects(self, tenant_a):
        account = _make_party(tenant_a)
        contract = _make_contract(tenant_a, account=account)
        c = Client()
        resp = c.post(reverse("crm:contractdocument_generate", args=[contract.pk]))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_member_can_generate(self, member_client, tenant_a):
        """generate is @login_required (not @tenant_admin_required) — a member can trigger it."""
        from apps.crm.models import DocumentVersion
        contract, _, _ = self._setup(tenant_a)
        url = reverse("crm:contractdocument_generate", args=[contract.pk])
        resp = member_client.post(url)
        assert resp.status_code == 302
        # A version must have been created (member is allowed)
        assert DocumentVersion.objects.filter(contract=contract).count() == 1


# ========================================================================== Group 3 — SSTI sandbox

class TestSSTISandbox:
    """The isolated engine must block all escape-bypass and file-inclusion vectors."""

    def _make(self, tenant_a, body):
        account = _make_party(tenant_a, name="Sandbox Corp")
        opp = _make_opportunity(tenant_a, account, amount="1.00")
        tpl = _make_doctemplate(tenant_a, body=body)
        return _make_contract(tenant_a, account=account, opportunity=opp, template=tpl)

    def _post_generate(self, client, contract):
        return client.post(reverse("crm:contractdocument_generate", args=[contract.pk]))

    def test_safe_filter_blocked(self, client_a, tenant_a):
        """{{ account.name|safe }} — 'safe' filter is removed from engine, raises TemplateSyntaxError."""
        from apps.crm.models import DocumentVersion
        contract = self._make(tenant_a, body="{{ account.name|safe }}")
        resp = self._post_generate(client_a, contract)
        assert resp.status_code == 302
        # No version must be created (error caught in view)
        assert DocumentVersion.objects.filter(contract=contract).count() == 0

    def test_autoescape_tag_blocked(self, client_a, tenant_a):
        """{% autoescape off %} is stripped from the engine — must raise TemplateSyntaxError."""
        from apps.crm.models import DocumentVersion
        contract = self._make(tenant_a, body="{% autoescape off %}{{ account.name }}{% endautoescape %}")
        resp = self._post_generate(client_a, contract)
        assert resp.status_code == 302
        assert DocumentVersion.objects.filter(contract=contract).count() == 0

    def test_include_tag_blocked(self, client_a, tenant_a):
        """{% include 'base.html' %} must be blocked — no DOCTYPE/<html> in body_snapshot, no version."""
        from apps.crm.models import DocumentVersion
        contract = self._make(tenant_a, body="{% include 'base.html' %}")
        resp = self._post_generate(client_a, contract)
        assert resp.status_code == 302
        # Either raises or produces no file-inclusion output
        assert DocumentVersion.objects.filter(contract=contract).count() == 0

    def test_load_tag_blocked(self, client_a, tenant_a):
        """{% load humanize %} must raise TemplateSyntaxError — 'load' is in loader_tags, excluded."""
        from apps.crm.models import DocumentVersion
        contract = self._make(tenant_a, body="{% load humanize %}{{ account.name }}")
        resp = self._post_generate(client_a, contract)
        assert resp.status_code == 302
        assert DocumentVersion.objects.filter(contract=contract).count() == 0

    def test_allowed_filters_and_tags_still_render(self, client_a, tenant_a):
        """The sandbox must block ONLY the escape-bypass vectors — not every tag/filter.

        Guard-rail for the blocked-* tests above: they assert "no version was created", which also
        holds if the engine's restricted tag/filter libraries are left EMPTY — in that case every
        tag/filter raises, the merge-variable feature is dead, and those tests still pass. This
        test fails in exactly that scenario, so they can never pass vacuously.
        """
        from apps.crm.models import DocumentVersion
        contract = self._make(
            tenant_a,
            body="{{ account.name|upper }}|{{ opportunity.amount|floatformat:2 }}"
                 "{% if account.name %}|IF-OK{% endif %}"
                 "{% for c in '12'|make_list %}|{{ c }}{% endfor %}",
        )
        resp = self._post_generate(client_a, contract)
        assert resp.status_code == 302
        assert DocumentVersion.objects.filter(contract=contract).count() == 1
        contract.refresh_from_db()
        assert "SANDBOX CORP" in contract.body_snapshot   # |upper ran
        assert "1.00" in contract.body_snapshot           # |floatformat ran
        assert "IF-OK" in contract.body_snapshot          # {% if %} ran
        assert "|1|2" in contract.body_snapshot           # {% for %} + |make_list ran

    def test_xss_chars_in_context_value_are_escaped(self, client_a, tenant_a):
        """An account whose name contains '<x>' must appear escaped as '&lt;x&gt;' in body_snapshot."""
        from apps.core.models import Party
        from apps.crm.models import DocumentVersion
        # Create an account whose name contains an XSS probe
        account = Party.objects.create(tenant=tenant_a, kind="organization", name="<x>Corp</x>")
        opp = _make_opportunity(tenant_a, account, amount="1.00")
        tpl = _make_doctemplate(tenant_a, body="<b>{{ account.name }}</b>")
        contract = _make_contract(tenant_a, account=account, opportunity=opp, template=tpl)
        client_a.post(reverse("crm:contractdocument_generate", args=[contract.pk]))
        contract.refresh_from_db()
        # The raw '<' must NOT appear in the rendered output — it must be escaped
        assert "<x>" not in contract.body_snapshot
        assert "&lt;x&gt;" in contract.body_snapshot
        # Versions must be created (plain body still renders ok)
        assert DocumentVersion.objects.filter(contract=contract).count() == 1

    def test_plain_html_body_renders_account_name(self, client_a, tenant_a):
        """A safe template <b>{{ account.name }}</b> should render the name into body_snapshot."""
        from apps.crm.models import DocumentVersion
        account = _make_party(tenant_a, name="Good Corp")
        opp = _make_opportunity(tenant_a, account, amount="1.00")
        tpl = _make_doctemplate(tenant_a, body="<b>{{ account.name }}</b>")
        contract = _make_contract(tenant_a, account=account, opportunity=opp, template=tpl)
        client_a.post(reverse("crm:contractdocument_generate", args=[contract.pk]))
        contract.refresh_from_db()
        assert "Good Corp" in contract.body_snapshot
        assert DocumentVersion.objects.filter(contract=contract).count() == 1


# ========================================================================== Group 4 — File Repository / version_add

class TestContractDocumentVersionAdd:
    def test_valid_txt_upload_creates_version(self, client_a, tenant_a):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from apps.crm.models import DocumentVersion
        account = _make_party(tenant_a)
        contract = _make_contract(tenant_a, account=account, body_snapshot="<p>existing</p>")
        f = SimpleUploadedFile("contract_v2.txt", b"Revised contract text", content_type="text/plain")
        url = reverse("crm:contractdocument_version_add", args=[contract.pk])
        resp = client_a.post(url, {"file": f, "change_note": "Revision from upload"})
        assert resp.status_code == 302
        assert DocumentVersion.objects.filter(tenant=tenant_a, contract=contract).count() == 1

    def test_valid_txt_upload_bumps_current_version(self, client_a, tenant_a):
        from django.core.files.uploadedfile import SimpleUploadedFile
        account = _make_party(tenant_a)
        contract = _make_contract(tenant_a, account=account, body_snapshot="<p>existing</p>")
        f = SimpleUploadedFile("contract_v2.txt", b"Revised contract text", content_type="text/plain")
        client_a.post(
            reverse("crm:contractdocument_version_add", args=[contract.pk]),
            {"file": f, "change_note": "Version bump"},
        )
        contract.refresh_from_db()
        assert contract.current_version == 1  # was 1 before; upload → v1 (count was 0)

    def test_valid_txt_upload_second_bump(self, client_a, tenant_a):
        """Two uploads → version 1 then 2."""
        from django.core.files.uploadedfile import SimpleUploadedFile
        from apps.crm.models import DocumentVersion
        account = _make_party(tenant_a)
        contract = _make_contract(tenant_a, account=account, body_snapshot="<p>existing</p>")
        for i, note in enumerate(["First upload", "Second upload"], start=1):
            f = SimpleUploadedFile(f"contract_v{i}.txt", b"Text", content_type="text/plain")
            client_a.post(
                reverse("crm:contractdocument_version_add", args=[contract.pk]),
                {"file": f, "change_note": note},
            )
        contract.refresh_from_db()
        assert contract.current_version == 2
        assert DocumentVersion.objects.filter(contract=contract).count() == 2

    def test_disallowed_svg_extension_rejected(self, client_a, tenant_a):
        """An .svg file must fail the extension allowlist — no version created."""
        from django.core.files.uploadedfile import SimpleUploadedFile
        from apps.crm.models import DocumentVersion
        account = _make_party(tenant_a)
        contract = _make_contract(tenant_a, account=account, body_snapshot="<p>existing</p>")
        f = SimpleUploadedFile("malicious.svg", b"<svg><script>alert(1)</script></svg>",
                               content_type="image/svg+xml")
        client_a.post(
            reverse("crm:contractdocument_version_add", args=[contract.pk]),
            {"file": f, "change_note": ""},
        )
        assert DocumentVersion.objects.filter(contract=contract).count() == 0

    def test_disallowed_html_extension_rejected(self, client_a, tenant_a):
        """An .html file must be rejected — no version created."""
        from django.core.files.uploadedfile import SimpleUploadedFile
        from apps.crm.models import DocumentVersion
        account = _make_party(tenant_a)
        contract = _make_contract(tenant_a, account=account, body_snapshot="<p>existing</p>")
        f = SimpleUploadedFile("page.html", b"<html><body>XSS</body></html>",
                               content_type="text/html")
        client_a.post(
            reverse("crm:contractdocument_version_add", args=[contract.pk]),
            {"file": f, "change_note": ""},
        )
        assert DocumentVersion.objects.filter(contract=contract).count() == 0

    def test_empty_no_file_no_note_rejected(self, client_a, tenant_a):
        """No file AND no change_note → form invalid (clean raises) → no version created."""
        from apps.crm.models import DocumentVersion
        account = _make_party(tenant_a)
        contract = _make_contract(tenant_a, account=account, body_snapshot="<p>existing</p>")
        client_a.post(
            reverse("crm:contractdocument_version_add", args=[contract.pk]),
            {"file": "", "change_note": ""},
        )
        assert DocumentVersion.objects.filter(contract=contract).count() == 0

    def test_note_only_no_file_accepted(self, client_a, tenant_a):
        """A note without a file should be valid — clean() requires file OR note, not both."""
        from apps.crm.models import DocumentVersion
        account = _make_party(tenant_a)
        contract = _make_contract(tenant_a, account=account, body_snapshot="<p>existing</p>")
        client_a.post(
            reverse("crm:contractdocument_version_add", args=[contract.pk]),
            {"change_note": "Administrative note only"},
        )
        assert DocumentVersion.objects.filter(contract=contract).count() == 1

    def test_signed_contract_blocks_version_add(self, client_a, tenant_a):
        """A signed contract must reject new revisions."""
        from apps.crm.models import DocumentVersion
        account = _make_party(tenant_a)
        contract = _make_contract(tenant_a, account=account, status="signed", body_snapshot="<p>signed</p>")
        from django.core.files.uploadedfile import SimpleUploadedFile
        f = SimpleUploadedFile("revision.txt", b"content", content_type="text/plain")
        client_a.post(
            reverse("crm:contractdocument_version_add", args=[contract.pk]),
            {"file": f, "change_note": "Late revision"},
        )
        assert DocumentVersion.objects.filter(contract=contract).count() == 0

    def test_declined_contract_blocks_version_add(self, client_a, tenant_a):
        """A declined contract must reject new revisions."""
        from apps.crm.models import DocumentVersion
        account = _make_party(tenant_a)
        contract = _make_contract(tenant_a, account=account, status="declined", body_snapshot="<p>declined</p>")
        from django.core.files.uploadedfile import SimpleUploadedFile
        f = SimpleUploadedFile("revision.txt", b"content", content_type="text/plain")
        client_a.post(
            reverse("crm:contractdocument_version_add", args=[contract.pk]),
            {"file": f, "change_note": "Late revision"},
        )
        assert DocumentVersion.objects.filter(contract=contract).count() == 0

    def test_version_add_anon_redirects(self, tenant_a):
        account = _make_party(tenant_a)
        contract = _make_contract(tenant_a, account=account)
        c = Client()
        resp = c.post(reverse("crm:contractdocument_version_add", args=[contract.pk]))
        assert resp.status_code == 302
        assert "login" in resp["Location"]


# ========================================================================== Group 5 — Send

class TestContractDocumentSend:
    def test_draft_with_body_and_signer_sent(self, client_a, tenant_a):
        account = _make_party(tenant_a)
        contract = _make_contract(tenant_a, account=account, body_snapshot="<p>body</p>")
        _make_signer(tenant_a, contract)
        resp = client_a.post(reverse("crm:contractdocument_send", args=[contract.pk]))
        assert resp.status_code == 302
        contract.refresh_from_db()
        assert contract.status == "sent"

    def test_draft_with_no_signer_blocked(self, client_a, tenant_a):
        """No signers → must stay draft."""
        account = _make_party(tenant_a)
        contract = _make_contract(tenant_a, account=account, body_snapshot="<p>body</p>")
        client_a.post(reverse("crm:contractdocument_send", args=[contract.pk]))
        contract.refresh_from_db()
        assert contract.status == "draft"

    def test_draft_with_no_body_blocked(self, client_a, tenant_a):
        """Empty body_snapshot → must stay draft."""
        account = _make_party(tenant_a)
        contract = _make_contract(tenant_a, account=account, body_snapshot="")
        _make_signer(tenant_a, contract)
        client_a.post(reverse("crm:contractdocument_send", args=[contract.pk]))
        contract.refresh_from_db()
        assert contract.status == "draft"

    def test_non_draft_send_info_message_unchanged(self, client_a, tenant_a):
        """Sending a non-draft contract must be a no-op."""
        account = _make_party(tenant_a)
        contract = _make_contract(tenant_a, account=account, status="sent", body_snapshot="<p>body</p>")
        _make_signer(tenant_a, contract)
        resp = client_a.post(reverse("crm:contractdocument_send", args=[contract.pk]))
        assert resp.status_code == 302
        contract.refresh_from_db()
        assert contract.status == "sent"  # unchanged (not changed to another status)

    def test_send_anon_redirects(self, tenant_a):
        account = _make_party(tenant_a)
        contract = _make_contract(tenant_a, account=account)
        c = Client()
        resp = c.post(reverse("crm:contractdocument_send", args=[contract.pk]))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_member_can_send(self, member_client, tenant_a):
        """send is @login_required — a member CAN trigger it."""
        account = _make_party(tenant_a)
        contract = _make_contract(tenant_a, account=account, body_snapshot="<p>body</p>")
        _make_signer(tenant_a, contract)
        resp = member_client.post(reverse("crm:contractdocument_send", args=[contract.pk]))
        assert resp.status_code == 302
        contract.refresh_from_db()
        assert contract.status == "sent"


# ========================================================================== Group 6 — Privilege: doctemplate CRUD

class TestDocTemplatePrivilege:
    """doctemplate_create/edit/delete are @tenant_admin_required — non-admin must be blocked."""

    def test_member_get_doctemplate_create_blocked(self, member_client):
        resp = member_client.get(reverse("crm:doctemplate_create"))
        # @tenant_admin_required → 302 redirect or 403; not 200
        assert resp.status_code in (302, 403)

    def test_member_post_doctemplate_create_blocked(self, member_client):
        resp = member_client.post(reverse("crm:doctemplate_create"), {
            "name": "Injected Template",
            "template_type": "contract",
            "body": "{{ bad }}",
            "is_active": "on",
        })
        assert resp.status_code in (302, 403)

    def test_admin_get_doctemplate_create_allowed(self, client_a):
        resp = client_a.get(reverse("crm:doctemplate_create"))
        assert resp.status_code == 200

    def test_admin_post_doctemplate_create_allowed(self, client_a, tenant_a):
        from apps.crm.models import DocTemplate
        resp = client_a.post(reverse("crm:doctemplate_create"), {
            "name": "Admin NDA",
            "template_type": "nda",
            "body": "Hello {{ account.name }}",
            "is_active": "on",
        })
        assert resp.status_code == 302
        assert DocTemplate.objects.filter(tenant=tenant_a, name="Admin NDA").exists()

    def test_member_get_doctemplate_edit_blocked(self, member_client, tenant_a):
        tpl = _make_doctemplate(tenant_a)
        resp = member_client.get(reverse("crm:doctemplate_edit", args=[tpl.pk]))
        assert resp.status_code in (302, 403)

    def test_member_post_doctemplate_edit_blocked(self, member_client, tenant_a):
        tpl = _make_doctemplate(tenant_a, body="original body")
        member_client.post(reverse("crm:doctemplate_edit", args=[tpl.pk]), {
            "name": tpl.name,
            "template_type": "contract",
            "body": "hacked body",
            "is_active": "on",
        })
        tpl.refresh_from_db()
        # Body must remain unchanged
        assert tpl.body == "original body"

    def test_admin_get_doctemplate_edit_allowed(self, client_a, tenant_a):
        tpl = _make_doctemplate(tenant_a)
        resp = client_a.get(reverse("crm:doctemplate_edit", args=[tpl.pk]))
        assert resp.status_code == 200

    def test_member_post_doctemplate_delete_blocked(self, member_client, tenant_a):
        from apps.crm.models import DocTemplate
        tpl = _make_doctemplate(tenant_a)
        pk = tpl.pk
        resp = member_client.post(reverse("crm:doctemplate_delete", args=[pk]))
        assert resp.status_code in (302, 403)
        assert DocTemplate.objects.filter(pk=pk).exists()

    def test_admin_post_doctemplate_delete_allowed(self, client_a, tenant_a):
        from apps.crm.models import DocTemplate
        tpl = _make_doctemplate(tenant_a)
        pk = tpl.pk
        resp = client_a.post(reverse("crm:doctemplate_delete", args=[pk]))
        assert resp.status_code == 302
        assert not DocTemplate.objects.filter(pk=pk).exists()

    def test_anon_doctemplate_create_redirects(self):
        c = Client()
        resp = c.get(reverse("crm:doctemplate_create"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]


# ========================================================================== Group 7 — document_repository

class TestDocumentRepository:
    def test_returns_200(self, client_a, tenant_a):
        resp = client_a.get(reverse("crm:document_repository"))
        assert resp.status_code == 200

    def test_only_shows_own_tenant_contracts(self, client_a, tenant_a, tenant_b):
        acc_a = _make_party(tenant_a)
        acc_b = _make_party(tenant_b, name="Globex Ltd")
        c_a = _make_contract(tenant_a, account=acc_a, name="A Contract")
        c_b = _make_contract(tenant_b, account=acc_b, name="B Secret Contract")
        resp = client_a.get(reverse("crm:document_repository"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert c_a.pk in pks
        assert c_b.pk not in pks

    def test_version_count_annotation_correct(self, client_a, tenant_a):
        """The annotated version_count must equal the actual number of DocumentVersion records."""
        account = _make_party(tenant_a)
        contract = _make_contract(tenant_a, account=account, body_snapshot="<p>body</p>")
        _make_version(tenant_a, contract, version_no=1)
        _make_version(tenant_a, contract, version_no=2)
        resp = client_a.get(reverse("crm:document_repository"))
        obj = next(o for o in resp.context["object_list"] if o.pk == contract.pk)
        assert obj.version_count == 2

    def test_filter_by_status(self, client_a, tenant_a):
        """Filtering by status=sent must exclude draft contracts."""
        account = _make_party(tenant_a)
        c_draft = _make_contract(tenant_a, account=account, name="Draft", status="draft")
        c_sent = _make_contract(tenant_a, account=account, name="Sent", status="sent")
        resp = client_a.get(reverse("crm:document_repository"), {"status": "sent"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert c_sent.pk in pks
        assert c_draft.pk not in pks

    def test_filter_by_account(self, client_a, tenant_a):
        """Filtering by account must exclude contracts for other accounts."""
        acc1 = _make_party(tenant_a, name="Acme")
        acc2 = _make_party(tenant_a, name="Wayne")
        c1 = _make_contract(tenant_a, account=acc1, name="Acme Contract")
        c2 = _make_contract(tenant_a, account=acc2, name="Wayne Contract")
        resp = client_a.get(reverse("crm:document_repository"), {"account": str(acc1.pk)})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert c1.pk in pks
        assert c2.pk not in pks

    def test_status_choices_in_context(self, client_a):
        resp = client_a.get(reverse("crm:document_repository"))
        assert "status_choices" in resp.context

    def test_accounts_in_context(self, client_a, tenant_a):
        resp = client_a.get(reverse("crm:document_repository"))
        assert "accounts" in resp.context

    def test_anon_redirects(self):
        c = Client()
        resp = c.get(reverse("crm:document_repository"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]


# ========================================================================== Group 8 — Multi-tenant IDOR

class TestCrossTenanDocumentVersionIDOR:
    def test_documentversion_detail_cross_tenant_404(self, client_a, tenant_b):
        """Tenant A's client requesting tenant B's DocumentVersion → 404."""
        acc_b = _make_party(tenant_b, name="Globex")
        contract_b = _make_contract(tenant_b, account=acc_b)
        ver_b = _make_version(tenant_b, contract_b, version_no=1)
        resp = client_a.get(reverse("crm:documentversion_detail", args=[ver_b.pk]))
        assert resp.status_code == 404

    def test_contractdocument_detail_cross_tenant_404(self, client_a, tenant_b):
        """Tenant A's client requesting tenant B's ContractDocument detail → 404."""
        acc_b = _make_party(tenant_b, name="Globex")
        contract_b = _make_contract(tenant_b, account=acc_b)
        resp = client_a.get(reverse("crm:contractdocument_detail", args=[contract_b.pk]))
        assert resp.status_code == 404

    def test_generate_cross_tenant_404(self, client_a, tenant_b):
        """POST generate on tenant B's contract from tenant A's session → 404."""
        from apps.crm.models import DocumentVersion
        acc_b = _make_party(tenant_b, name="Globex")
        tpl_b = _make_doctemplate(tenant_b)
        contract_b = _make_contract(tenant_b, account=acc_b, template=tpl_b)
        resp = client_a.post(reverse("crm:contractdocument_generate", args=[contract_b.pk]))
        assert resp.status_code == 404
        assert DocumentVersion.objects.filter(contract=contract_b).count() == 0

    def test_version_add_cross_tenant_404(self, client_a, tenant_b):
        """POST version_add on tenant B's contract → 404, no version."""
        from django.core.files.uploadedfile import SimpleUploadedFile
        from apps.crm.models import DocumentVersion
        acc_b = _make_party(tenant_b, name="Globex")
        contract_b = _make_contract(tenant_b, account=acc_b, body_snapshot="<p>B</p>")
        f = SimpleUploadedFile("x.txt", b"data", content_type="text/plain")
        resp = client_a.post(
            reverse("crm:contractdocument_version_add", args=[contract_b.pk]),
            {"file": f, "change_note": "IDOR attempt"},
        )
        assert resp.status_code == 404
        assert DocumentVersion.objects.filter(contract=contract_b).count() == 0

    def test_send_cross_tenant_404(self, client_a, tenant_b, admin_b):
        """POST send on tenant B's contract → 404."""
        acc_b = _make_party(tenant_b, name="Globex")
        contract_b = _make_contract(tenant_b, account=acc_b, body_snapshot="<p>B</p>")
        _make_signer(tenant_b, contract_b, email="b@example.com")
        resp = client_a.post(reverse("crm:contractdocument_send", args=[contract_b.pk]))
        assert resp.status_code == 404
        contract_b.refresh_from_db()
        # Status must remain draft (untouched)
        assert contract_b.status == "draft"

    def test_doctemplate_edit_cross_tenant_404(self, client_a, tenant_b):
        """Tenant A admin trying to edit tenant B's DocTemplate → 404."""
        tpl_b = _make_doctemplate(tenant_b, name="B's Template")
        resp = client_a.get(reverse("crm:doctemplate_edit", args=[tpl_b.pk]))
        assert resp.status_code == 404

    def test_repository_never_leaks_other_tenant_rows(self, client_a, tenant_a, tenant_b):
        """document_repository for tenant A must never contain tenant B's contracts."""
        acc_a = _make_party(tenant_a)
        acc_b = _make_party(tenant_b, name="Globex")
        _make_contract(tenant_a, account=acc_a, name="A Contract")
        c_b = _make_contract(tenant_b, account=acc_b, name="B Secret")
        resp = client_a.get(reverse("crm:document_repository"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert c_b.pk not in pks


# ========================================================================== Group 9 — Forms

class TestDocumentVersionForm:
    def test_tenant_not_a_form_field(self, tenant_a):
        from apps.crm.forms import DocumentVersionForm
        form = DocumentVersionForm(tenant=tenant_a)
        assert "tenant" not in form.fields

    def test_version_no_not_a_form_field(self, tenant_a):
        from apps.crm.forms import DocumentVersionForm
        form = DocumentVersionForm(tenant=tenant_a)
        assert "version_no" not in form.fields

    def test_body_snapshot_not_a_form_field(self, tenant_a):
        from apps.crm.forms import DocumentVersionForm
        form = DocumentVersionForm(tenant=tenant_a)
        assert "body_snapshot" not in form.fields

    def test_created_by_not_a_form_field(self, tenant_a):
        from apps.crm.forms import DocumentVersionForm
        form = DocumentVersionForm(tenant=tenant_a)
        assert "created_by" not in form.fields

    def test_contract_not_a_form_field(self, tenant_a):
        from apps.crm.forms import DocumentVersionForm
        form = DocumentVersionForm(tenant=tenant_a)
        assert "contract" not in form.fields

    def test_empty_form_is_invalid(self, tenant_a):
        from apps.crm.forms import DocumentVersionForm
        form = DocumentVersionForm(data={"file": "", "change_note": ""}, tenant=tenant_a)
        assert not form.is_valid()

    def test_note_only_is_valid(self, tenant_a):
        from apps.crm.forms import DocumentVersionForm
        form = DocumentVersionForm(data={"change_note": "A note"}, tenant=tenant_a)
        assert form.is_valid(), form.errors


class TestContractDocumentForm:
    def test_body_snapshot_not_a_form_field(self, tenant_a):
        from apps.crm.forms import ContractDocumentForm
        form = ContractDocumentForm(tenant=tenant_a)
        assert "body_snapshot" not in form.fields

    def test_status_not_a_form_field(self, tenant_a):
        from apps.crm.forms import ContractDocumentForm
        form = ContractDocumentForm(tenant=tenant_a)
        assert "status" not in form.fields

    def test_current_version_not_a_form_field(self, tenant_a):
        from apps.crm.forms import ContractDocumentForm
        form = ContractDocumentForm(tenant=tenant_a)
        assert "current_version" not in form.fields

    def test_tenant_not_a_form_field(self, tenant_a):
        from apps.crm.forms import ContractDocumentForm
        form = ContractDocumentForm(tenant=tenant_a)
        assert "tenant" not in form.fields

    def test_number_not_a_form_field(self, tenant_a):
        from apps.crm.forms import ContractDocumentForm
        form = ContractDocumentForm(tenant=tenant_a)
        assert "number" not in form.fields


# ========================================================================== Group 10 — Query-count (document_repository)

class TestDocumentRepositoryQueryCount:
    """document_repository annotates in one query — must not N+1 per contract."""

    def test_bounded_queries_with_multiple_contracts(self, client_a, tenant_a, admin_user):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        account = _make_party(tenant_a)
        for i in range(5):
            contract = _make_contract(tenant_a, account=account, name=f"Contract {i}")
            for j in range(1, 4):
                _make_version(tenant_a, contract, version_no=j)

        # Warm up — first request populates session/middleware caches (not measured)
        client_a.get(reverse("crm:document_repository"))

        with CaptureQueriesContext(connection) as ctx:
            resp = client_a.get(reverse("crm:document_repository"))

        assert resp.status_code == 200
        # Generous cap: select_related + annotate should complete in <20 queries
        # regardless of contract count — no per-row N+1
        assert len(ctx.captured_queries) < 20, (
            f"Expected <20 queries for document_repository (5 contracts, 15 versions), "
            f"got {len(ctx.captured_queries)}. Possible N+1."
        )


# ========================================================================== Group 11 — CSRF enforcement

class TestDocumentCSRFEnforcement:
    def test_generate_enforces_csrf(self, admin_user, tenant_a):
        account = _make_party(tenant_a)
        tpl = _make_doctemplate(tenant_a)
        contract = _make_contract(tenant_a, account=account, template=tpl)
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("crm:contractdocument_generate", args=[contract.pk]))
        assert resp.status_code == 403

    def test_version_add_enforces_csrf(self, admin_user, tenant_a):
        from django.core.files.uploadedfile import SimpleUploadedFile
        account = _make_party(tenant_a)
        contract = _make_contract(tenant_a, account=account, body_snapshot="<p>body</p>")
        f = SimpleUploadedFile("x.txt", b"data", content_type="text/plain")
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("crm:contractdocument_version_add", args=[contract.pk]),
                      {"file": f, "change_note": "note"})
        assert resp.status_code == 403

    def test_send_enforces_csrf(self, admin_user, tenant_a):
        account = _make_party(tenant_a)
        contract = _make_contract(tenant_a, account=account, body_snapshot="<p>body</p>")
        _make_signer(tenant_a, contract)
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("crm:contractdocument_send", args=[contract.pk]))
        assert resp.status_code == 403

    def test_doctemplate_delete_enforces_csrf(self, admin_user, tenant_a):
        tpl = _make_doctemplate(tenant_a)
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("crm:doctemplate_delete", args=[tpl.pk]))
        assert resp.status_code == 403
