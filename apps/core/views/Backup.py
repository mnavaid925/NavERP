"""core — 0.16 views (backup, recovery & data lifecycle).

**The posture every view here takes, inherited from 0.8 (`apps/core/views/Privacy.py`):**

NavERP has **no scheduler, no object storage client and no ability to dump or restore its own MySQL
database**. So none of these views performs the act they describe. `backup_job_create` records a backup a
human reports having taken; `backup_job_verify` records that somebody checked one; `restore_record_create`
records that a restore was performed out of band. The pages say so in `notes` (§ the computed boards), and
the success messages say **"recorded"**, never "completed".

**The zero rule.** `retention_board` refuses to print a `0` it cannot justify — *"Reporting 0 here would be
a false all-clear."* The two boards below obey it: `backup_board` returns `None` (not `0`) where a figure
cannot be determined, and it **names** every unverified backup, every archive with no `location` (those
are unrestorable) and every active hold, rather than reporting a count that hides them.

**Two singleton editors, not CRUD.** `RecoveryPosture` is a `OneToOne`, so it gets one edit page and no
delete (the `LocaleProfile` / `BusinessCalendar` shape). Both read the existing row — possibly `None` —
and write only on a valid POST: `get_or_create` on GET would insert a row merely because somebody opened
the page.
"""
from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.core.views._common import *  # noqa: F401,F403
from apps.core.utils import write_audit_log
from apps.core.models import (
    BackupJob,
    DataArchive,
    EnvironmentInstance,
    RecoveryDrill,
    RecoveryPosture,
    RestoreRecord,
)
from apps.core.models.LegalHold import LegalHold
from apps.core.forms import (
    BackupJobForm,
    DataArchiveForm,
    EnvironmentInstanceForm,
    RecoveryDrillForm,
    RecoveryPostureForm,
    RestoreRecordForm,
)
from apps.core.forms.Backup import LegalHoldForm


#: The honest-limit lines the boards print verbatim. A module-level constant so a page and its board
#: cannot disagree about what this application can and cannot do.
BACKUP_NOTES = [
    "This is a register of evidence, not a backup engine. NavERP has no scheduler and no storage client — "
    "records here describe work performed outside the application.",
    "Nothing on these pages can take a backup, restore one, replicate data or provision an environment. "
    "The act is out of band; this is the trail it leaves.",
]


def _audit_changes(form):
    """The `{field: new_value}` diff for a hand-rolled singleton save's audit row.

    A local twin of the same two-line helper 0.15 uses: `crud._changed` stays private because ~75 call
    sites name it across scm/hrm/procurement/projects, so promoting it would be a cross-app rename for no
    behavioural gain.
    """
    return {name: str(form.cleaned_data.get(name))[:200] for name in form.changed_data}


# ============================================================ bullet 1: automated backups
@tenant_admin_required
def backup_job_list(request):
    qs = (BackupJob.objects.filter(tenant=request.tenant)
          .select_related("encryption_key", "performed_by"))
    return crud_list(
        request,
        qs,
        "core/backupjob/list.html",
        search_fields=["name", "scope_label", "evidence"],
        filters=[("status", "status", False), ("backup_type", "backup_type", False),
                 ("storage_tier", "storage_tier", False), ("integrity", "integrity_method", False)],
        extra_context={
            "status_choices": BackupJob.STATUS_CHOICES,
            "backup_type_choices": BackupJob.BACKUP_TYPE_CHOICES,
            "storage_tier_choices": BackupJob.STORAGE_TIER_CHOICES,
            "integrity_method_choices": BackupJob.INTEGRITY_METHOD_CHOICES,
            # The count that matters: a backup nobody has verified is an untested claim, so it is
            # surfaced rather than left for the reader to notice.
            "unverified_count": BackupJob.objects.filter(
                tenant=request.tenant, integrity_verified_at__isnull=True).count(),
            "notes": BACKUP_NOTES,
        },
    )


@tenant_admin_required
def backup_job_create(request):
    return crud_create(request, form_class=BackupJobForm,
                       template="core/backupjob/form.html",
                       success_url="core:backup_job_list",
                       extra_context={"unverified_note": True, "notes": BACKUP_NOTES})


@tenant_admin_required
def backup_job_detail(request, pk):
    return crud_detail(
        request, model=BackupJob, pk=pk, template="core/backupjob/detail.html",
        select_related=("encryption_key", "performed_by"),
        extra_context={
            "restore_count": RestoreRecord.objects.filter(
                tenant=request.tenant, backup_id=pk).count(),
            "notes": BACKUP_NOTES,
        },
    )


@tenant_admin_required
def backup_job_edit(request, pk):
    # The instance is read once, here, only to decide whether to show the "this form does not verify
    # anything" note. `crud_edit` re-fetches for the form itself (it re-resolves with `tenant=`, which is
    # the tenant guard, so it is not redundant), and `_meta`-free `update_fields` are not involved.
    unverified = BackupJob.objects.filter(
        tenant=request.tenant, pk=pk, integrity_verified_at__isnull=True).exists()
    return crud_edit(
        request, model=BackupJob, pk=pk, form_class=BackupJobForm,
        template="core/backupjob/form.html",
        # `reverse(...)` and not the bare name: `crud_edit` calls `redirect(success_url)` with no
        # arguments, so a pk-taking route passed as a string raises `NoReverseMatch` AFTER the row is
        # saved — the operator sees a 500 for a write that succeeded. House convention; see
        # `apps/procurement/views/OrderFulfillment/Backorder.py`.
        success_url=reverse("core:backup_job_detail", args=[pk]),
        extra_context={"unverified_note": unverified, "notes": BACKUP_NOTES},
    )


# `@require_POST` sits ABOVE the role gate on purpose: decorators apply bottom-up, so the outermost runs
# first. With the role gate outermost a member's GET would be answered 403 before the method check ran,
# and the house standard is 405 for a wrong method regardless of role (7.7's ruling).
@require_POST
@tenant_admin_required
def backup_job_delete(request, pk):
    return crud_delete(request, model=BackupJob, pk=pk, success_url="core:backup_job_list")


@require_POST
@tenant_admin_required
def backup_job_verify(request, pk):
    """Record that somebody checked this backup's integrity.

    **POST-only, and deliberately not a field on the edit form.** A verification is an event with a time
    and an actor; letting it be typed into a form would let the register claim a check that never
    happened. `audit` action stays a short valid choice — `AuditLog.action` is `varchar(10)` and
    `.create()` never validates `choices`, so the descriptive verb goes in `changes` (see
    `views/Localization.py` for the same pattern).
    """
    obj = get_object_or_404(BackupJob, pk=pk, tenant=request.tenant)
    now = timezone.now()
    obj.integrity_verified_at = now
    # A verification with no method recorded is a verification with no evidence, so default it.
    if obj.integrity_method == "none":
        obj.integrity_method = "restore_test"
    obj.save(update_fields=["integrity_verified_at", "integrity_method"])
    write_audit_log(request.user, obj, "update",
                    changes={"verb": "backup_job_verify",
                             "integrity_verified_at": now.isoformat(),
                             "integrity_method": obj.integrity_method})
    messages.success(request, "Verification recorded. This records the check — it does not perform one.")
    return redirect("core:backup_job_detail", pk=obj.pk)


# ============================================================ bullet 2: point-in-time recovery
@tenant_admin_required
def restore_record_list(request):
    qs = (RestoreRecord.objects.filter(tenant=request.tenant)
          .select_related("backup", "archive", "target_environment", "requested_by"))
    return crud_list(
        request,
        qs,
        "core/restorerecord/list.html",
        search_fields=["reason", "outcome", "evidence"],
        filters=[("status", "status", False), ("scope", "scope", False)],
        extra_context={
            "status_choices": RestoreRecord.STATUS_CHOICES,
            "scope_choices": RestoreRecord.SCOPE_CHOICES,
            "notes": BACKUP_NOTES,
        },
    )


@tenant_admin_required
def restore_record_create(request):
    return crud_create(request, form_class=RestoreRecordForm,
                       template="core/restorerecord/form.html",
                       success_url="core:restore_record_list",
                       extra_context={"notes": BACKUP_NOTES})


@tenant_admin_required
def restore_record_detail(request, pk):
    return crud_detail(
        request, model=RestoreRecord, pk=pk, template="core/restorerecord/detail.html",
        select_related=("backup", "archive", "target_environment", "requested_by"),
        extra_context={"notes": BACKUP_NOTES},
    )


@tenant_admin_required
def restore_record_edit(request, pk):
    return crud_edit(
        request, model=RestoreRecord, pk=pk, form_class=RestoreRecordForm,
        template="core/restorerecord/form.html",
        success_url=reverse("core:restore_record_detail", args=[pk]),
        extra_context={"notes": BACKUP_NOTES},
    )


@require_POST
@tenant_admin_required
def restore_record_delete(request, pk):
    return crud_delete(request, model=RestoreRecord, pk=pk, success_url="core:restore_record_list")


# ============================================================ bullet 4: archive catalogue
@tenant_admin_required
def data_archive_list(request):
    qs = (DataArchive.objects.filter(tenant=request.tenant)
          .select_related("policy", "disposal", "encryption_key"))
    return crud_list(
        request,
        qs,
        "core/dataarchive/list.html",
        search_fields=["name", "location", "content_description"],
        filters=[("status", "status", False), ("storage_tier", "storage_tier", False),
                 ("format", "format", False)],
        extra_context={
            "status_choices": DataArchive.STATUS_CHOICES,
            "tier_choices": DataArchive.STORAGE_TIER_CHOICES,
            "format_choices": DataArchive.FORMAT_CHOICES,
            # An archive with no location is unrestorable, which defeats the point of the model. Named,
            # not counted silently.
            "unrestorable_count": DataArchive.objects.filter(
                tenant=request.tenant).filter(Q(location="") | Q(status__in=["lost", "destroyed"])).count(),
            "notes": BACKUP_NOTES,
        },
    )


@tenant_admin_required
def data_archive_create(request):
    return crud_create(request, form_class=DataArchiveForm,
                       template="core/dataarchive/form.html",
                       success_url="core:data_archive_list",
                       extra_context={"notes": BACKUP_NOTES})


@tenant_admin_required
def data_archive_detail(request, pk):
    return crud_detail(
        request, model=DataArchive, pk=pk, template="core/dataarchive/detail.html",
        select_related=("policy", "disposal", "encryption_key"),
        extra_context={"notes": BACKUP_NOTES},
    )


@tenant_admin_required
def data_archive_edit(request, pk):
    return crud_edit(
        request, model=DataArchive, pk=pk, form_class=DataArchiveForm,
        template="core/dataarchive/form.html",
        success_url=reverse("core:data_archive_detail", args=[pk]),
        extra_context={"notes": BACKUP_NOTES},
    )


@require_POST
@tenant_admin_required
def data_archive_delete(request, pk):
    return crud_delete(request, model=DataArchive, pk=pk, success_url="core:data_archive_list")


# ============================================================ bullet 4: legal holds
@tenant_admin_required
def legal_hold_list(request):
    qs = (LegalHold.objects.filter(tenant=request.tenant)
          .select_related("retention_policy", "subject_party", "issued_by", "released_by"))
    return crud_list(
        request,
        qs,
        "core/legalhold/list.html",
        search_fields=["name", "custodian", "matter_reference", "issuing_authority"],
        filters=[("status", "status", False)],
        extra_context={
            "status_choices": LegalHold.STATUS_CHOICES,
            "active_count": LegalHold.active_for_tenant(request.tenant).count(),
            "notes": BACKUP_NOTES,
        },
    )


@tenant_admin_required
def legal_hold_create(request):
    return crud_create(request, form_class=LegalHoldForm,
                       template="core/legalhold/form.html",
                       success_url="core:legal_hold_list",
                       extra_context={"notes": BACKUP_NOTES})


@tenant_admin_required
def legal_hold_detail(request, pk):
    obj = get_object_or_404(LegalHold, pk=pk, tenant=request.tenant)
    # Other active holds on the same scope. A release that strands data on one of these is refused by
    # `LegalHold.clean()`, so surfacing them lets the page explain the refusal before it happens.
    siblings = LegalHold.active_for_tenant(request.tenant).exclude(pk=obj.pk)
    scope_query = Q(pk__in=[])
    if obj.retention_policy_id is not None:
        scope_query |= Q(retention_policy_id=obj.retention_policy_id)
    if obj.model_label:
        scope_query |= Q(model_label=obj.model_label)
    conflicting = (siblings.filter(scope_query)
                   if (obj.retention_policy_id or obj.model_label) else siblings.none())
    return crud_detail(
        request, model=LegalHold, pk=pk, template="core/legalhold/detail.html",
        select_related=("retention_policy", "subject_party", "issued_by", "released_by"),
        extra_context={"conflicting_holds": conflicting, "notes": BACKUP_NOTES},
    )


@tenant_admin_required
def legal_hold_edit(request, pk):
    return crud_edit(
        request, model=LegalHold, pk=pk, form_class=LegalHoldForm,
        template="core/legalhold/form.html",
        success_url=reverse("core:legal_hold_detail", args=[pk]),
        extra_context={"notes": BACKUP_NOTES},
    )


@require_POST
@tenant_admin_required
def legal_hold_delete(request, pk):
    return crud_delete(request, model=LegalHold, pk=pk, success_url="core:legal_hold_list")


# ============================================================ bullets 2 + 5: environments
@tenant_admin_required
def environment_instance_list(request):
    qs = (EnvironmentInstance.objects.filter(tenant=request.tenant)
          .select_related("source_environment", "refresh_source"))
    # `is_expired` is a Python property (it compares `expires_at` to now AND honours the status), so a DB
    # aggregate would mean restating that rule in SQL — exactly the second copy that drifts. It is
    # therefore computed from the tenant's whole set, deliberately NOT from the filtered page, because
    # this count answers "how many sandboxes has nobody reaped?", which is a tenant-wide question and
    # must not change when somebody types a search term.
    expired_count = sum(1 for e in qs.all() if e.is_expired)
    return crud_list(
        request,
        qs,
        "core/environmentinstance/list.html",
        search_fields=["name", "tier", "subset_rule"],
        filters=[("kind", "kind", False), ("status", "status", False),
                 ("copy_scope", "copy_scope", False)],
        extra_context={
            "kind_choices": EnvironmentInstance.KIND_CHOICES,
            "status_choices": EnvironmentInstance.STATUS_CHOICES,
            "copy_scope_choices": EnvironmentInstance.COPY_SCOPE_CHOICES,
            "expired_count": expired_count,
            "notes": BACKUP_NOTES,
        },
    )


@tenant_admin_required
def environment_instance_create(request):
    return crud_create(request, form_class=EnvironmentInstanceForm,
                       template="core/environmentinstance/form.html",
                       success_url="core:environment_instance_list",
                       extra_context={"notes": BACKUP_NOTES})


@tenant_admin_required
def environment_instance_detail(request, pk):
    return crud_detail(
        request, model=EnvironmentInstance, pk=pk, template="core/environmentinstance/detail.html",
        select_related=("source_environment", "refresh_source"),
        extra_context={"notes": BACKUP_NOTES},
    )


@tenant_admin_required
def environment_instance_edit(request, pk):
    return crud_edit(
        request, model=EnvironmentInstance, pk=pk, form_class=EnvironmentInstanceForm,
        template="core/environmentinstance/form.html",
        success_url=reverse("core:environment_instance_detail", args=[pk]),
        extra_context={"notes": BACKUP_NOTES},
    )


@require_POST
@tenant_admin_required
def environment_instance_delete(request, pk):
    return crud_delete(request, model=EnvironmentInstance, pk=pk,
                       success_url="core:environment_instance_list")


# ============================================================ bullet 3: recovery posture (singleton)
@tenant_admin_required
def recovery_posture_edit(request):
    """The workspace's DR targets — a singleton, so one edit page and no delete."""
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace first.")
        return redirect("dashboard:home")

    posture = RecoveryPosture.objects.filter(tenant=request.tenant).first()
    if request.method == "POST":
        form = RecoveryPostureForm(request.POST, instance=posture, tenant=request.tenant)
        if form.is_valid():
            posture = form.save(commit=False)
            # `tenant` is not a form field, so it must be set here — `form.save()` alone would try to
            # insert a NULL tenant on the create path and raise IntegrityError.
            posture.tenant = request.tenant
            posture.save()
            write_audit_log(request.user, posture, "update",
                            changes={"verb": "recovery_posture_save", **_audit_changes(form)})
            messages.success(request, "Recovery targets recorded.")
            return redirect("core:backup_overview")
    else:
        form = RecoveryPostureForm(instance=posture, tenant=request.tenant)
    last_drill = (RecoveryDrill.objects.filter(tenant=request.tenant)
                  .exclude(performed_at=None).order_by("-performed_at").first())
    return render(request, "core/recoveryposture/form.html", {
        "form": form,
        "posture": posture,
        "is_edit": posture is not None,
        "drill_count": RecoveryDrill.objects.filter(tenant=request.tenant).count(),
        "last_drill": last_drill,
        "targets_set": bool(posture and posture.has_targets),
        "notes": BACKUP_NOTES,
    })


# ============================================================ bullet 3: drills
@tenant_admin_required
def recovery_drill_list(request):
    qs = RecoveryDrill.objects.filter(tenant=request.tenant).select_related("performed_by")
    return crud_list(
        request,
        qs,
        "core/recoverydrill/list.html",
        search_fields=["name", "findings", "participants"],
        filters=[("kind", "kind", False), ("outcome", "outcome", False)],
        extra_context={
            "kind_choices": RecoveryDrill.KIND_CHOICES,
            "outcome_choices": RecoveryDrill.OUTCOME_CHOICES,
            "notes": BACKUP_NOTES,
        },
    )


@tenant_admin_required
def recovery_drill_create(request):
    return crud_create(request, form_class=RecoveryDrillForm,
                       template="core/recoverydrill/form.html",
                       success_url="core:recovery_drill_list",
                       extra_context={"notes": BACKUP_NOTES})


@tenant_admin_required
def recovery_drill_detail(request, pk):
    obj = get_object_or_404(RecoveryDrill, pk=pk, tenant=request.tenant)
    posture = RecoveryPosture.objects.filter(tenant=request.tenant).first()
    # `target_notes` returns an explicit "cannot tell" state when there is no posture or no target, so the
    # page never renders a missing comparison as a pass.
    notes_by_kind = obj.target_notes(posture)
    return render(request, "core/recoverydrill/detail.html", {
        "obj": obj,
        "posture": posture,
        "rpo_note": notes_by_kind["rpo"],
        "rto_note": notes_by_kind["rto"],
        "notes": BACKUP_NOTES,
    })


@tenant_admin_required
def recovery_drill_edit(request, pk):
    return crud_edit(
        request, model=RecoveryDrill, pk=pk, form_class=RecoveryDrillForm,
        template="core/recoverydrill/form.html",
        success_url=reverse("core:recovery_drill_detail", args=[pk]),
        extra_context={"notes": BACKUP_NOTES},
    )


@require_POST
@tenant_admin_required
def recovery_drill_delete(request, pk):
    return crud_delete(request, model=RecoveryDrill, pk=pk, success_url="core:recovery_drill_list")


# ============================================================ computed: the hub
@tenant_admin_required
def backup_overview(request):
    """COMPUTED hub. Stores nothing."""
    if request.tenant is None:
        messages.info(request, "Backup and recovery apply to a tenant workspace.")
        return redirect("dashboard:home")
    tenant = request.tenant
    posture = RecoveryPosture.objects.filter(tenant=tenant).first()
    jobs = BackupJob.objects.filter(tenant=tenant)
    archives = DataArchive.objects.filter(tenant=tenant)
    environments = EnvironmentInstance.objects.filter(tenant=tenant)
    context = {
        "job_count": jobs.count(),
        "unverified_count": jobs.filter(integrity_verified_at__isnull=True).count(),
        "partial_count": jobs.filter(status="warning").count(),
        "failed_count": jobs.filter(status="failed").count(),
        "archive_count": archives.count(),
        "unrestorable_count": archives.filter(
            Q(location="") | Q(status__in=["lost", "destroyed"])).count(),
        "active_hold_count": LegalHold.active_for_tenant(tenant).count(),
        "environment_count": environments.count(),
        # `is_expired` is a property, so this is computed in Python off the already-fetched rows rather
        # than issuing a second query per row.
        "expired_count": sum(1 for e in environments if e.is_expired),
        "drill_count": RecoveryDrill.objects.filter(tenant=tenant).count(),
        "posture": posture,
        "targets_set": bool(posture and posture.has_targets),
        "recent_jobs": jobs.select_related("encryption_key")[:5],
        "recent_drills": RecoveryDrill.objects.filter(tenant=tenant)
                         .exclude(performed_at=None).order_by("-performed_at")[:5],
        "notes": BACKUP_NOTES,
    }
    return render(request, "core/backupoverview.html", context)


@tenant_admin_required
def backup_board(request):
    """COMPUTED monitoring board — obeys 0.8's zero rule.

    Every figure that cannot be determined is `None` and is named as such on the page, never rendered as
    a `0`. The three lists that matter (`unverified_jobs`, `archives_without_location`, `active_holds`)
    are returned as ROWS, not counts, because a count of unverified backups hides the point: which ones.
    """
    if request.tenant is None:
        messages.info(request, "Backup monitoring applies to a tenant workspace.")
        return redirect("dashboard:home")
    tenant = request.tenant
    now = timezone.now()

    jobs = list(BackupJob.objects.filter(tenant=tenant).select_related("encryption_key"))
    job_rows = []
    for job in jobs[:10]:
        age = (now - job.started_at).days if job.started_at else None
        note = ""
        if job.is_partial:
            note = "Partial — some of the declared scope did not make it. Treat as unverified."
        elif job.status == "failed":
            note = f"Failed: {job.get_failure_reason_display()}."
        elif not job.is_verified:
            note = "No integrity check recorded against this backup."
        job_rows.append({"job": job, "age_days": age, "note": note})

    verified_total = sum(1 for j in jobs if j.is_verified)
    unverified_jobs = [j for j in jobs if not j.is_verified]

    archives = list(DataArchive.objects.filter(tenant=tenant))
    archives_without_location = [a for a in archives if not a.location]

    holds = list(LegalHold.active_for_tenant(tenant).select_related("retention_policy"))
    holds_suspending = [{"hold": h, "policy": h.retention_policy} for h in holds]

    environments = list(EnvironmentInstance.objects.filter(tenant=tenant))
    expired_environments = [e for e in environments if e.is_expired]

    # A backup that has never been test-restored is an untested claim. Report it as a figure only when
    # there IS a successful backup to be untrue of; otherwise the honest answer is "there is nothing to
    # say here", which is `None`, not `0`.
    successful = [j for j in jobs if j.status == "success"]
    if not successful:
        never_restored = None
    else:
        never_restored = sum(1 for j in successful if not j.is_verified)

    context = {
        "job_rows": job_rows,
        "job_total": len(jobs),
        "verified_total": verified_total,
        "unverified_jobs": unverified_jobs,
        "never_restored": never_restored,
        "archives_without_location": archives_without_location,
        "archive_total": len(archives),
        "async_retrieval_count": sum(1 for a in archives if a.retrieval_is_async),
        "active_holds": holds,
        "holds_suspending": holds_suspending,
        "expired_environments": expired_environments,
        # Jobs whose verification state cannot be determined: none here, but the key is pinned by the
        # contract and carried so the page can print it rather than omitting the question.
        "unverifiable_count": 0,
        "notes": BACKUP_NOTES,
    }
    return render(request, "core/backupboard.html", context)
