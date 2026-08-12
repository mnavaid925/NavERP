"""4.15 view and form layer — and a regression lock on every defect the review chain found.

The model and service suites prove the domain rules. This file proves the things a **request** can and
cannot do, which is where all three of the sub-module's most expensive defects lived:

* a **privilege escalation** — ``assessment`` (release-or-reject on physical product) was on the
  ModelForm whitelist while ``temperatureexcursion_edit`` is ``@login_required`` and the ``assess``
  verb is ``@tenant_admin_required``, so any workspace member could mark contaminated stock released
  with no ``assessed_by`` signature. Both the model and form docstrings already *claimed* ``assess()``
  was the only writer — **the whitelist is what makes such a claim true.** ``TestAssessmentIsNotOnTheEditForm``
  is the lock, and it asserts the bypass POST **through the view**, not just the form's field list:
  a later commit could put the field back and a form-only test would still pass if it checked
  ``Meta.fields`` alone.
* a **500 from one CSV cell** — ``Decimal("nan")`` and ``"sNaN"`` PARSE cleanly and only raise
  ``InvalidOperation`` at the first ordering comparison. ``Infinity`` was always safe; it compares and
  skips as out of bounds. So the regression test must use **NaN specifically** — testing with
  ``Infinity`` would pass against the unfixed code.
* a **bulk path bypassing ``clean()``** — ``bulk_create`` skips ``full_clean``, so the importer had to
  re-implement rule 4 (a reading cannot predate ``monitor.deployed_on``) itself. The test asserts the
  bulk path refuses what the single-row path refuses, because "the same input, two answers" is the
  actual defect.

Every assertion states what it would have caught. A test that cannot fail for the right reason is
worth less than no test, because it also carries a green badge.
"""
import pytest
from django.urls import reverse

# Star import, matching the sibling 4.15 modules: `_coldchain.py` is a plain module rather than a
# conftest, so its `cc_*` fixtures are only discoverable once their names are bound HERE.
from apps.scm.tests._coldchain import *  # noqa: F401,F403

# The non-admin actor every gate below is measured against is the root conftest's `member_client`
# (a `tenant_a` user with `is_tenant_admin=False`). An earlier draft of this file hand-rolled an
# identical one — same email, same username, same flag — which is the duplication that makes a
# fixture change fix one call site and miss the other.


# =================================================================================================
# The privilege escalation — the most expensive defect the review chain found
# =================================================================================================
@pytest.mark.django_db
class TestAssessmentIsNotOnTheEditForm:
    """``assessment`` is the release-or-reject decision on physical product.

    It is written ONLY by ``TemperatureExcursion.assess()``, which is ``@tenant_admin_required`` and
    stamps ``assessed_by`` / ``assessed_on``. The edit view is ``@login_required``, so any field on
    that form is writable by any member of the workspace."""

    def test_a_member_cannot_release_product_through_the_edit_view(self, member_client,
                                                                   cc_excursion_a):
        """THE regression test. Before the fix this POST set ``assessment='product_ok'`` and the
        detail page, triage queue, compliance report and audit CSV all printed "Product unaffected —
        release" for an episode no admin ever assessed, with "Assessed by: Not assessed" beside it."""
        before = cc_excursion_a.assessment
        response = member_client.post(
            reverse("scm:temperatureexcursion_edit", args=[cc_excursion_a.pk]),
            {"severity": "minor", "assessment": "product_ok", "cause": "",
             "corrective_action": "", "notes": "member edit", "non_conformance": "",
             "maintenance_work_order": "", "lot_serial": ""})
        assert response.status_code in (200, 302)
        cc_excursion_a.refresh_from_db()
        assert cc_excursion_a.assessment == before, (
            "a non-admin set the product-release decision through the login-only edit view")
        assert cc_excursion_a.assessed_by is None
        assert cc_excursion_a.assessed_on is None

    def test_the_members_legitimate_edit_still_saves(self, member_client, cc_excursion_a):
        """The fix must not have been "gate the whole form" — that would be a different product.

        Without this, dropping the entire edit view behind ``@tenant_admin_required`` would pass the
        test above while silently removing triage from every non-admin in the workspace."""
        member_client.post(reverse("scm:temperatureexcursion_edit", args=[cc_excursion_a.pk]),
                    {"severity": "minor", "cause": "", "corrective_action": "",
                     "notes": "member edit", "non_conformance": "",
                     "maintenance_work_order": "", "lot_serial": ""})
        cc_excursion_a.refresh_from_db()
        assert cc_excursion_a.notes == "member edit"

    def test_the_field_is_absent_from_the_rendered_form(self, client_a, cc_excursion_a):
        html = client_a.get(
            reverse("scm:temperatureexcursion_edit", args=[cc_excursion_a.pk])).content.decode()
        assert 'name="assessment"' not in html

    def test_the_gated_verb_refuses_a_member(self, member_client, cc_excursion_a):
        """The other half: the verb that IS the writer must actually be gated."""
        response = member_client.post(reverse("scm:temperatureexcursion_assess",
                                       args=[cc_excursion_a.pk]),
                               {"assessment": "product_ok", "cause": "", "corrective_action": ""})
        assert response.status_code in (403, 302)
        cc_excursion_a.refresh_from_db()
        assert cc_excursion_a.assessment != "product_ok" or cc_excursion_a.assessed_by is None


# =================================================================================================
# The CSV importer — a 500 from one cell, and a rule the bulk path was skipping
# =================================================================================================
@pytest.mark.django_db
class TestReadingImportHardening:

    def _import(self, client, monitor, rows):
        return client.post(reverse("scm:coldchainmonitor_import_readings", args=[monitor.pk]),
                           {"file": cc_csv(rows), "source": "logger_import"})

    def test_a_nan_temperature_is_skipped_not_a_500(self, client_a, cc_monitor_a):
        """NaN SPECIFICALLY. ``Decimal("nan")`` constructs cleanly and raises ``InvalidOperation``
        only at the first ordering comparison, so it sailed past the parse and detonated at the bounds
        check. A test written with ``Infinity`` would pass against the unfixed code, because Infinity
        compares fine and is skipped as out of bounds."""
        before = cc_monitor_a.readings.count()
        response = self._import(client_a, cc_monitor_a, [
            "%s,nan,,1,junk" % cc_local(cc_moment(120)),
            "%s,sNaN,,1,junk" % cc_local(cc_moment(110)),
            "%s,4.00,,1,good" % cc_local(cc_moment(100)),
        ])
        assert response.status_code == 200, "a crafted temperature cell 500'd the import"
        assert cc_monitor_a.readings.count() == before + 1, "only the good row should have landed"

    def test_a_malformed_file_is_a_form_error_not_a_traceback(self, client_a, cc_monitor_a):
        response = client_a.post(
            reverse("scm:coldchainmonitor_import_readings", args=[cc_monitor_a.pk]),
            {"file": cc_csv(["%s,4.00\x00,,1," % cc_local(cc_moment(90))]),
             "source": "logger_import"})
        assert response.status_code == 200

    def test_a_blank_temperature_is_skipped_never_coerced_to_zero(self, client_a, cc_monitor_a):
        """``Decimal(value or ZERO)`` would make a missing cell a perfectly plausible 0 °C, which in a
        freezer log either reads as a catastrophic excursion or masks a real one."""
        self._import(client_a, cc_monitor_a, ["%s,,,1,blank" % cc_local(cc_moment(80))])
        assert not cc_monitor_a.readings.filter(notes="blank").exists()

    def test_the_bulk_path_refuses_what_the_single_row_path_refuses(self, client_a, cc_monitor_a):
        """``bulk_create`` skips ``full_clean``, so ``clean()`` rule 4 had to be re-implemented in
        ``parse_rows``. Without it, re-uploading a reusable logger's full history filed a previous
        consignment's readings against this deployment, where they counted toward its % time in range
        and its MKT — while the same row typed by hand was refused."""
        from datetime import timedelta
        from django.utils import timezone
        cc_monitor_a.deployed_on = timezone.localdate()
        cc_monitor_a.save(update_fields=["deployed_on"])
        stale = timezone.localtime(timezone.now()) - timedelta(days=30)
        before = cc_monitor_a.readings.count()
        response = self._import(client_a, cc_monitor_a,
                                ["%s,4.00,,1,previous consignment" % stale.strftime("%Y-%m-%d %H:%M")])
        assert response.status_code == 200
        assert cc_monitor_a.readings.count() == before, (
            "a reading predating deployed_on was filed through the bulk path")


# =================================================================================================
# The append-only posture, enforced by the absence of routes rather than by a filter
# =================================================================================================
@pytest.mark.django_db
class TestReadingLedgerHasNoWritePath:

    def test_no_edit_or_delete_route_exists_for_a_reading(self):
        """The absence IS the rule. A future 'for consistency' CRUD pass would silently make the
        ledger rewritable, and nothing else in the sub-module would notice."""
        from django.urls import NoReverseMatch
        for name in ("temperaturereading_edit", "temperaturereading_delete"):
            with pytest.raises(NoReverseMatch):
                reverse("scm:" + name, args=[1])

    def test_the_list_page_renders_no_edit_or_delete_control(self, client_a, cc_reading_a):
        html = client_a.get(reverse("scm:temperaturereading_list")).content.decode()
        assert "/edit/" not in html.split("<tbody")[-1]


# =================================================================================================
# Verbs are POST-only, and the sweep asserts its own denominator
# =================================================================================================
@pytest.mark.django_db
class TestStatusVerbsRejectGet:

    def test_every_verb_405s_on_get(self, client_a, cc_monitor_a, cc_excursion_a):
        """A verb reachable by GET is reachable by a crafted link, a prefetch or a crawler."""
        targets = [
            reverse("scm:coldchain_detect"),
            reverse("scm:coldchainmonitor_detect", args=[cc_monitor_a.pk]),
            reverse("scm:coldchainmonitor_delete", args=[cc_monitor_a.pk]),
            reverse("scm:temperatureexcursion_acknowledge", args=[cc_excursion_a.pk]),
            reverse("scm:temperatureexcursion_assess", args=[cc_excursion_a.pk]),
            reverse("scm:temperatureexcursion_close", args=[cc_excursion_a.pk]),
            reverse("scm:temperatureexcursion_dismiss", args=[cc_excursion_a.pk]),
            reverse("scm:temperatureexcursion_raise_work_order", args=[cc_excursion_a.pk]),
            reverse("scm:temperatureexcursion_delete", args=[cc_excursion_a.pk]),
        ]
        assert len(targets) >= 9, "denominator guard — the sweep must not silently shrink"
        wrong = [(t, client_a.get(t).status_code) for t in targets]
        wrong = [(t, code) for t, code in wrong if code != 405]
        assert not wrong, wrong


# =================================================================================================
# Cross-tenant isolation at the request layer
# =================================================================================================
@pytest.mark.django_db
class TestColdChainViewIsolation:

    def test_every_detail_route_404s_across_tenants(self, client_a, cc_monitor_b, cc_reading_b,
                                                    cc_excursion_b):
        """404, never 302 — a redirect leaks "there is a row there, you just cannot have it"."""
        targets = [
            reverse("scm:coldchainmonitor_detail", args=[cc_monitor_b.pk]),
            reverse("scm:coldchainmonitor_edit", args=[cc_monitor_b.pk]),
            reverse("scm:coldchainmonitor_profile", args=[cc_monitor_b.pk]),
            reverse("scm:coldchainmonitor_add_reading", args=[cc_monitor_b.pk]),
            reverse("scm:coldchainmonitor_import_readings", args=[cc_monitor_b.pk]),
            reverse("scm:temperaturereading_detail", args=[cc_reading_b.pk]),
            reverse("scm:temperatureexcursion_detail", args=[cc_excursion_b.pk]),
            reverse("scm:temperatureexcursion_edit", args=[cc_excursion_b.pk]),
        ]
        assert len(targets) >= 8, "denominator guard"
        leaks = [(t, client_a.get(t).status_code) for t in targets]
        leaks = [(t, code) for t, code in leaks if code != 404]
        assert not leaks, leaks

    def test_a_crafted_subject_pk_cannot_bind_a_monitor_across_tenants(self, client_a, location_b):
        """The form re-checks every FK against ``request.tenant``; a pk in a POST body is the whole
        attack. Asserting the ROW COUNT, not just the status: a 200 re-rendering the form with an
        error and a 200 that quietly saved look identical from the outside."""
        from apps.scm.models import ColdChainMonitor
        before = ColdChainMonitor.objects.count()
        client_a.post(reverse("scm:coldchainmonitor_create"),
                      cc_monitor_post(location=str(location_b.pk)))
        assert ColdChainMonitor.objects.count() == before, (
            "a crafted location pk bound a monitor to another tenant's cold room")
