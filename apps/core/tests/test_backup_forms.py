"""0.16 form-lane tests — Backup, Recovery & Data Lifecycle.

Contract: `.claude/tasks/test-contract-core-0.16.md` §5.

The theme here: **a form is where a rule is most easily bypassed, and where it is most easily
duplicated.** 0.16's seven forms are `Meta`-only on purpose — `ModelForm._post_clean` calls
`instance.full_clean()`, so every model rule fires on every form and a `clean_<field>` copy could never
fire on its own. These tests assert that the *model* rules reach the form, not that the form re-states
them.

The C7 tests are the exception and are the point of the lane: they pin behaviour the sub-module
**deliberately does not change**, so that if it is ever revisited the change is visible instead of
silent.
"""
import re

import pytest
from django.urls import reverse

from apps.core.forms import (
    BackupJobForm,
    DataArchiveForm,
    EnvironmentInstanceForm,
    LegalHoldForm,
    RecoveryDrillForm,
    RecoveryPostureForm,
    RestoreRecordForm,
)


# ============================================================ tenant scoping

class TestTenantScoping:
    """Every tenant-scoped FK's queryset must contain only this tenant's rows."""

    def test_backup_job_encryption_key_is_scoped(self, tenant_a, bkp_key_a, bkp_key_b):
        form = BackupJobForm(tenant=tenant_a)
        pks = set(form.fields["encryption_key"].queryset.values_list("pk", flat=True))
        assert bkp_key_a.pk in pks
        assert bkp_key_b.pk not in pks

    def test_data_archive_policy_is_scoped(self, tenant_a, tenant_b):
        from apps.core.models import RetentionPolicy
        mine = RetentionPolicy.objects.create(tenant=tenant_a, name="Mine", retention_months=12)
        theirs = RetentionPolicy.objects.create(tenant=tenant_b, name="Theirs", retention_months=12)
        form = DataArchiveForm(tenant=tenant_a)
        pks = set(form.fields["policy"].queryset.values_list("pk", flat=True))
        assert mine.pk in pks
        assert theirs.pk not in pks

    def test_legal_hold_retention_policy_is_scoped(self, tenant_a, tenant_b):
        from apps.core.models import RetentionPolicy
        mine = RetentionPolicy.objects.create(tenant=tenant_a, name="Mine", retention_months=12)
        theirs = RetentionPolicy.objects.create(tenant=tenant_b, name="Theirs", retention_months=12)
        form = LegalHoldForm(tenant=tenant_a)
        pks = set(form.fields["retention_policy"].queryset.values_list("pk", flat=True))
        assert mine.pk in pks
        assert theirs.pk not in pks

    def test_environment_source_is_scoped(self, tenant_a, bkp_env_production_a, bkp_env_b):
        form = EnvironmentInstanceForm(tenant=tenant_a)
        pks = set(form.fields["source_environment"].queryset.values_list("pk", flat=True))
        assert bkp_env_production_a.pk in pks
        assert bkp_env_b.pk not in pks

    def test_restore_record_backup_and_archive_are_scoped(self, tenant_a, bkp_verified_job_a,
                                                          bkp_job_b, bkp_archive_ok_a, bkp_archive_b):
        form = RestoreRecordForm(tenant=tenant_a)
        backups = set(form.fields["backup"].queryset.values_list("pk", flat=True))
        archives = set(form.fields["archive"].queryset.values_list("pk", flat=True))
        assert bkp_verified_job_a.pk in backups and bkp_job_b.pk not in backups
        assert bkp_archive_ok_a.pk in archives and bkp_archive_b.pk not in archives

    def test_tenant_is_never_a_form_field(self, tenant_a):
        for form_class in (BackupJobForm, DataArchiveForm, LegalHoldForm, EnvironmentInstanceForm,
                           RecoveryDrillForm, RecoveryPostureForm, RestoreRecordForm):
            assert "tenant" not in form_class(tenant=tenant_a).fields, form_class.__name__


class TestC7BoundaryIsDeliberate:
    """C7 — the shared `TenantModelForm` helper leaves a queryset UNNARROWED when `tenant is None`.

    **This is the CURRENT, DELIBERATE behaviour, pinned so a change is visible rather than silent.**

    A fix that emptied the queryset was tried and reverted (`68ebb8eb`): it broke 15 committed tests
    across `inventory`, `procurement` and `projects`, because those modules rely on the queryset staying
    loose so that `_reject_foreign` in `clean()` can return its precise "That record belongs to another
    workspace." message — Django validates `ModelChoiceField` in `Field.clean`, which runs BEFORE
    `Form.clean`, so an emptied queryset pre-empts that message with a generic one.

    C7 is **escalated, not fixed** (see the findings file). These tests exist so that whoever revisits it
    sees immediately that they are changing a decision, not repairing an oversight.
    """

    def test_a_tenant_less_form_leaves_the_queryset_unnarrowed(self, tenant_a, bkp_key_a, bkp_key_b):
        form = BackupJobForm(tenant=None)
        pks = set(form.fields["encryption_key"].queryset.values_list("pk", flat=True))
        assert bkp_key_a.pk in pks, "tenant_a's key should be visible to a tenant-less form"
        assert bkp_key_b.pk in pks, (
            "tenant_b's key is ALSO visible — this is C7's latent leak, deliberately unchanged. "
            "If this assertion now fails, someone has fixed C7: update the findings file, delete the "
            "C7 escalation section, and make sure the 15 tests in inventory/procurement/projects "
            "still pass."
        )

    def test_the_scoped_path_is_unaffected_by_the_same_form(self, tenant_a, bkp_key_a, bkp_key_b):
        """The control: the narrowing works whenever a tenant IS supplied, which is every real path."""
        form = BackupJobForm(tenant=tenant_a)
        pks = set(form.fields["encryption_key"].queryset.values_list("pk", flat=True))
        assert bkp_key_a.pk in pks and bkp_key_b.pk not in pks


# ============================================================ field behaviour

class TestLegalHoldFormRules:
    """C3's model rules must reach the form — the forms are `Meta`-only, so they do it through
    `_post_clean`. Asserting the MESSAGE lands on the right field, not just that `is_valid()` is False,
    because a form-level failure with no field attribution is unusable."""

    def test_active_with_a_release_date_is_refused_on_the_status_field(self, tenant_a, bkp_hold_active_a):
        """C3, reproduced through the form on the ONLY path that reaches it.

        `issued_at` is deliberately **not** a form field — a preservation order is issued when it is
        recorded, not when somebody types a date — so on the CREATE path the model default supplies
        "now" and a back-dated release is caught by rule 1 instead. The incoherent state therefore
        requires an existing hold with a PAST `issued_at`, i.e. the EDIT path. My first draft posted
        `issued_at` in the payload; it was silently ignored and the test failed on the wrong rule,
        which is how this was found.
        """
        from django.utils import timezone
        data = {"name": bkp_hold_active_a.name, "custodian": "", "subject_party": "",
                "matter_reference": "", "issuing_authority": "", "scope": "",
                "retention_policy": "", "model_label": "",
                "status": "active",
                "released_at": (timezone.now() - timezone.timedelta(days=1)).strftime("%Y-%m-%dT%H:%M"),
                "release_reason": "", "authority_reference": "", "notes": ""}
        form = LegalHoldForm(data, instance=bkp_hold_active_a, tenant=tenant_a)
        assert not form.is_valid()
        assert "status" in form.errors, (
            "expected rule 1b(a) on `status`; got %s. If `released_at` is the failing field, rule 1 "
            "fired first — check that the instance still carries a PAST issued_at." % form.errors)

    def test_issued_at_is_not_a_form_field(self, tenant_a):
        """The reason the test above needs an instance. Pinned so nobody "helpfully" adds it and
        silently makes every hold issue-datable by hand."""
        assert "issued_at" not in LegalHoldForm(tenant=tenant_a).fields

    def test_the_corrected_payload_saves(self, tenant_a, bkp_hold_payload):
        """THE CONTROL — without it the test above would pass if the form rejected everything."""
        form = LegalHoldForm(bkp_hold_payload, tenant=tenant_a)
        assert form.is_valid(), form.errors
        hold = form.save(commit=False)
        hold.tenant = tenant_a
        hold.save()
        assert hold.status == "active" and hold.released_at is None
        # And `issued_at` defaulted to "now" rather than to anything the client sent.
        assert hold.issued_at is not None

    def test_a_same_minute_release_is_accepted(self, tenant_a, bkp_hold_active_a):
        """I7, through the real form — the widget is minute-precision, so this is the common case."""
        issued = bkp_hold_active_a.issued_at
        data = {"name": bkp_hold_active_a.name, "custodian": "", "subject_party": "",
                "matter_reference": "", "issuing_authority": "", "scope": "",
                "retention_policy": "", "model_label": "",
                "status": "released",
                "released_at": issued.strftime("%Y-%m-%dT%H:%M"),
                "release_reason": "Wrong hold.", "authority_reference": "", "notes": ""}
        form = LegalHoldForm(data, instance=bkp_hold_active_a, tenant=tenant_a)
        assert form.is_valid(), form.errors


class TestRestoreRecordFormRules:
    def test_a_succeeded_restore_from_an_unrestorable_archive_is_refused(self, tenant_a,
                                                                        bkp_archive_lost_a,
                                                                        bkp_restore_payload):
        """I1 through the form. The seeder plants this exact archive on purpose."""
        bkp_restore_payload["archive"] = str(bkp_archive_lost_a.pk)
        bkp_restore_payload["scope"] = "archive_retrieval"
        form = RestoreRecordForm(bkp_restore_payload, tenant=tenant_a)
        assert not form.is_valid()
        assert "archive" in form.errors

    def test_the_same_restore_from_a_restorable_archive_is_accepted(self, tenant_a, bkp_archive_ok_a,
                                                                    bkp_restore_payload):
        """THE CONTROL."""
        bkp_restore_payload["archive"] = str(bkp_archive_ok_a.pk)
        bkp_restore_payload["scope"] = "archive_retrieval"
        form = RestoreRecordForm(bkp_restore_payload, tenant=tenant_a)
        assert form.is_valid(), form.errors


class TestBackupJobFormStates:
    def test_a_queued_payload_with_blank_stamps_is_accepted(self, tenant_a, bkp_job_payload):
        """C5's premise: the in-flight state must be CREATABLE through the form, or the whole
        in-flight path (the board's first row, the hub's preview) is unreachable in practice."""
        bkp_job_payload["status"] = "queued"
        bkp_job_payload["started_at"] = ""
        bkp_job_payload["finished_at"] = ""
        bkp_job_payload["integrity_verified_at"] = ""
        form = BackupJobForm(bkp_job_payload, tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_a_partial_payload_is_accepted(self, tenant_a, bkp_job_payload):
        bkp_job_payload["status"] = "warning"
        bkp_job_payload["failure_reason"] = "partial_scope_skipped"
        form = BackupJobForm(bkp_job_payload, tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_integrity_verified_at_is_not_editable(self, tenant_a):
        """The stamp is written only by the POST-only verify action, so a user cannot edit the register
        into claiming a verification that never happened."""
        assert "integrity_verified_at" not in BackupJobForm(tenant=tenant_a).fields

    def test_actor_fields_are_not_editable(self, tenant_a):
        """`released_by` especially: the release of a hold is the act an audit exists to attribute."""
        assert "performed_by" not in BackupJobForm(tenant=tenant_a).fields
        assert "requested_by" not in RestoreRecordForm(tenant=tenant_a).fields
        assert "issued_by" not in LegalHoldForm(tenant=tenant_a).fields
        assert "released_by" not in LegalHoldForm(tenant=tenant_a).fields


class TestRecoveryPostureFormTargets:
    """M6: the form must not make either target required, or the half-filled state the badge exists to
    describe would be unreachable."""

    def test_rpo_only_is_accepted(self, tenant_a):
        form = RecoveryPostureForm({"rpo_target_minutes": "60", "rto_target_minutes": "",
                                    "replication_mode": "none", "primary_region": "", "dr_region": "",
                                    "backup_retention_days": "", "dr_plan_reference": "",
                                    "last_reviewed_at": ""}, tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_rto_only_is_accepted(self, tenant_a):
        form = RecoveryPostureForm({"rpo_target_minutes": "", "rto_target_minutes": "240",
                                    "replication_mode": "none", "primary_region": "", "dr_region": "",
                                    "backup_retention_days": "", "dr_plan_reference": "",
                                    "last_reviewed_at": ""}, tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_both_set_is_accepted(self, tenant_a):
        form = RecoveryPostureForm({"rpo_target_minutes": "60", "rto_target_minutes": "240",
                                    "replication_mode": "none", "primary_region": "", "dr_region": "",
                                    "backup_retention_days": "", "dr_plan_reference": "",
                                    "last_reviewed_at": ""}, tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_neither_set_is_accepted(self, tenant_a):
        """The "Not set" state must remain reachable — the page has a warning for it."""
        form = RecoveryPostureForm({"rpo_target_minutes": "", "rto_target_minutes": "",
                                    "replication_mode": "none", "primary_region": "", "dr_region": "",
                                    "backup_retention_days": "", "dr_plan_reference": "",
                                    "last_reviewed_at": ""}, tenant=tenant_a)
        assert form.is_valid(), form.errors


# ============================================================ I11 — the large forms

class TestLargeFormGrouping:
    """I11: `BackupJobForm`'s 21 fields rendered as one undifferentiated block.

    The regression this guards against is a grouping pass that **duplicates or drops** a field — the
    page still renders 200 and still looks plausible, which is why a status-code assertion is useless
    here. Each field must appear **exactly once**.
    """

    LARGE_FORMS = [
        ("core:backup_job_create", BackupJobForm, 21),
        ("core:data_archive_create", DataArchiveForm, 18),
        ("core:environment_instance_create", EnvironmentInstanceForm, 16),
    ]

    @pytest.mark.parametrize("url_name,form_class,expected", LARGE_FORMS)
    def test_every_field_renders_exactly_once(self, client_a, url_name, form_class, expected):
        field_names = list(form_class(tenant=None).fields.keys())
        assert len(field_names) == expected, (
            "%s has %d fields, not the %d the contract pins — update the contract and this test together"
            % (form_class.__name__, len(field_names), expected))

        response = client_a.get(reverse(url_name))
        assert response.status_code == 200
        body = response.content.decode()

        duplicated = []
        missing = []
        for name in field_names:
            count = len(re.findall(r'id="id_%s"' % re.escape(name), body))
            if count == 0:
                missing.append(name)
            elif count > 1:
                duplicated.append("%s x%d" % (name, count))
        assert not missing, "%s: fields rendered ZERO times: %s" % (form_class.__name__, missing)
        assert not duplicated, "%s: fields rendered MORE THAN ONCE: %s" % (form_class.__name__, duplicated)

    def test_the_grouping_uses_labelled_sections(self, client_a):
        """I11's actual ask was human-readable grouping, not just non-duplication. Assert at least one
        heading exists between the first and last field, so a regression that flattened the template
        back into one block is caught."""
        body = client_a.get(reverse("core:backup_job_create")).content.decode()
        first = body.find('id="id_name"')
        last = body.find('id="id_notes"')
        assert first != -1 and last != -1 and first < last
        between = body[first:last]
        assert re.search(r"<h[23][^>]*>", between), "no section heading between the first and last field"
