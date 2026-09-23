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
from apps.core.crud import _SENSITIVE_AUDIT_FIELDS
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
    behavioural gain. It is *not* a twin of `crud._changed`'s **redaction** though — that part is shared
    rather than copied, so a field added to the one sensitive list is redacted on this path too. (No live
    gap today: the recovery-posture form shares no field with the sensitive set.)
    """
    return {
        name: "***redacted***" if name in _SENSITIVE_AUDIT_FIELDS
        else str(form.cleaned_data.get(name))[:200]
        for name in form.changed_data
    }


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
    # A verification the record's own status contradicts is the inverted false all-clear this whole
    # sub-module exists to prevent (I6): POSTing verify to a `failed` job set `integrity_verified_at`
    # and the detail page then rendered a green "Verified" tick over a record whose own badge said
    # Failed — and the job also left `unverified_jobs` and `never_restored`. A `cancelled` job is
    # equally settled. Refused in the VIEW rather than by hiding the button or gating the tick, so the
    # audit row is not written either and the action cannot be reached by a hand-made POST.
    if obj.status in {"failed", "cancelled"}:
        messages.error(
            request,
            "A %s backup cannot be recorded as verified — its own status contradicts it. Record the "
            "re-run as a new backup instead." % obj.get_status_display())
        return redirect("core:backup_job_detail", pk=obj.pk)
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
    #
    # The set is read through `.only("id", "expires_at", "status")` (I5): `qs.all()` pulled EVERY column
    # of every row — including the `subset_rule` and `notes` TextFields — and then `crud_list`'s
    # Paginator read the same whole set again for the 15-row page, so one page view transferred the
    # tenant's environment table twice. `.only(...)` leaves the predicate exactly where it is (one rule,
    # one place, no SQL restatement) while pulling only the three columns `is_expired` reads. It is a
    # fresh queryset rather than `qs.only(...)` because `qs` is `select_related` and Django refuses to
    # defer a relation it is traversing.
    expired_count = sum(
        1 for e in EnvironmentInstance.objects.filter(tenant=request.tenant)
        .only("id", "expires_at", "status") if e.is_expired)
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

    # ---- ONE QUERY PER MODEL, THEN DERIVE IN PYTHON (I3) ----
    # This view used to re-derive every count with a second query: four separate `COUNT(*)` against the
    # same `BackupJob` base, two against `DataArchive`, and it materialised `environments` **twice**
    # (once for `.count()`, once for the `is_expired` generator). Measured: 20 queries against
    # `backup_board`'s 11, on the landing page an operator opens first. `is_verified`, `is_expired` and
    # the unrestorable test are Python properties on purpose -- restating them in SQL would be the
    # second copy of a rule that then drifts -- so each set is fetched once and the rules stay in one
    # place, exactly as `backup_board` two views below already does.
    #
    # `BackupJob` is ordered `-id` for the same reason the board is (C5): `Meta.ordering` is
    # `["-started_at", "-id"]`, a queued backup has `started_at=NULL`, and MariaDB sorts NULLs LAST
    # under `DESC` -- so the newest work sorted to the bottom of this five-row preview and vanished.
    # Insertion order is what "recent" means for an append-only register, and `-id` is PK-served.
    jobs = list(BackupJob.objects.filter(tenant=tenant)
                .select_related("encryption_key").order_by("-id"))
    archives = list(DataArchive.objects.filter(tenant=tenant))
    environments = list(EnvironmentInstance.objects.filter(tenant=tenant))
    holds = list(LegalHold.active_for_tenant(tenant))
    drills = list(RecoveryDrill.objects.filter(tenant=tenant).order_by("-performed_at", "-id"))

    job_count = len(jobs)
    archive_count = len(archives)

    # ---- A GREEN BADGE IS AN ACTIVE REASSURANCE, SO IT MUST BE EARNED (C4) ----
    # "Never verified: 0" is a claim about the members of a set -- "every backup has been integrity
    # checked". On a workspace that has recorded NO backups that claim is vacuously true and reads as
    # a clean bill of health, which is the one thing it is not: there is no evidence either way.
    # `None` is the honest answer, and the page names it ("nothing recorded to verify") instead of
    # printing a green zero. This is the same discipline `backup_board` already applies to
    # `never_restored` two views below, and the same one 0.8 states as "reporting 0 here would be a
    # false all-clear". Denominator zero -> the figure does not exist.
    #
    # In-flight rows first, then the newest settled ones -- the window rule `backup_board` applies, so
    # a backup happening right now is never the row a five-row preview drops.
    in_flight = [j for j in jobs if j.is_in_flight]
    settled = [j for j in jobs if not j.is_in_flight]

    # The denominator is the SETTLED backups, and that is load-bearing twice over. (a) C4: a workspace
    # that has recorded no backup at all gets `None`, not a green `0`. (b) A queued or running row has
    # no result and its absent check is "not yet a question" -- `backup_board` refuses to name one as an
    # untested claim for exactly that reason ("naming it would be an accusation rather than a finding").
    # Counting in-flight rows here would make this page disagree with that list, and a workspace whose
    # only row is still queued would read as "1 never verified" when nothing has run to verify. The
    # seeder now plants such a row (M11), so this is a live path, not a hypothetical one.
    unverified_count = None if not settled else sum(1 for j in settled if not j.is_verified)
    unrestorable_count = None if archive_count == 0 else sum(
        1 for a in archives if not a.location or a.status in {"lost", "destroyed"})

    context = {
        "job_count": job_count,
        "unverified_count": unverified_count,
        "partial_count": sum(1 for j in jobs if j.is_partial),
        "failed_count": sum(1 for j in jobs if j.status == "failed"),
        "archive_count": archive_count,
        "unrestorable_count": unrestorable_count,
        "active_hold_count": len(holds),
        "environment_count": len(environments),
        # `is_expired` is a property, so this is computed in Python off the already-fetched rows rather
        # than issuing a second query per row.
        "expired_count": sum(1 for e in environments if e.is_expired),
        "drill_count": len(drills),
        "posture": posture,
        # M6: `has_targets` is an `or`, so a workspace with only an RPO (or only an RTO) earned the same
        # green "Set" badge as one carrying both. A green badge is an active reassurance, so it has to
        # mean what it says: `targets_partial` names the half-filled case, and the warning below still
        # keys off `targets_set` (no target at all), which is the only state where nothing can be judged.
        "targets_set": bool(posture and posture.has_targets),
        "targets_partial": bool(posture and (posture.rpo_target_minutes is None)
                                != (posture.rto_target_minutes is None)),
        "recent_jobs": (in_flight + settled)[:5],
        "recent_drills": [d for d in drills if d.performed_at is not None][:5],
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

    # ---- ORDERING IS PART OF THE CORRECTNESS HERE (C5) ----
    # `Meta.ordering` is ["-started_at", "-id"], and a backup that has not started yet has
    # `started_at=NULL`. **MariaDB sorts NULLs LAST under `DESC`** (the opposite of PostgreSQL), so a
    # queued or running backup -- the newest work in the register, and the row an operator is actually
    # watching -- sorted to the BOTTOM and was the first thing `[:10]` discarded. Measured: with 9
    # finished jobs it was still visible; at 10 it was gone.
    #
    # Ordered by `-id` instead: insertion order, which is what "latest" means for an append-only
    # register. It is a single monotonic key, it never looks at a nullable column so the NULL
    # placement cannot bite, and it is served by the primary key (no new index -- cf. I4, which
    # rejects `-created_at` for needing one).
    #
    # `nulls_first=True` was the other candidate and was REJECTED: it emits
    # `ORDER BY started_at IS NOT NULL, started_at DESC`, which floats *every* never-started row above
    # *every* started one -- so a queued job abandoned two years ago would outrank a backup that
    # finished five minutes ago.
    jobs = list(BackupJob.objects.filter(tenant=tenant)
                .select_related("encryption_key").order_by("-id"))

    # An in-flight backup must never be invisible on a MONITORING board, whatever the ordering does.
    # "Latest ten" is a window over settled work; a backup that is running right now is not history, it
    # is the present, and it is the one row a reader came here to see. So in-flight rows are taken
    # first and the window is then filled from the settled ones -- the list stays ten rows, so the
    # heading remains true.
    in_flight = [j for j in jobs if j.is_in_flight]
    settled = [j for j in jobs if not j.is_in_flight]

    job_rows = []
    for job in (in_flight + settled)[:10]:
        age = (now - job.started_at).days if job.started_at else None
        note = ""
        # IN-FLIGHT BRANCHES COME FIRST, and that order is load-bearing. A queued backup has never run,
        # so `integrity_verified_at` is NULL and the old chain fell through to "No integrity check
        # recorded against this backup" -- which reads as an accusation about a check somebody skipped,
        # when in fact there is nothing yet to check. The register is saying "not started", not "not
        # verified".
        if job.status == "queued":
            note = "Not started yet — this row records an intention to back up, not a backup."
        elif job.status == "running":
            note = "In progress — no result and no integrity check recorded yet."
        elif job.is_partial:
            note = "Partial — some of the declared scope did not make it. Treat as unverified."
        elif job.status == "failed":
            note = f"Failed: {job.get_failure_reason_display()}."
        elif not job.is_verified:
            note = "No integrity check recorded against this backup."
        job_rows.append({"job": job, "age_days": age, "note": note})

    verified_total = sum(1 for j in jobs if j.is_verified)
    # In-flight jobs are excluded for the same reason they now get their own note above: this list is
    # the register's "restorable-looking artefacts with no recorded integrity check", and a backup that
    # has not run yet is neither restorable-looking nor an artefact. Leaving them in would have made
    # this page contradict itself -- the ten-job table saying "Not started yet" two cards below a list
    # that calls the same row an untested claim.
    unverified_jobs = [j for j in jobs if not j.is_verified and not j.is_in_flight]

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
        # ---- `unverifiable_count` AND THE ZERO RULE (C6) ----
        # The key is structurally 0: `is_verified` reads one nullable column, so every row's
        # verification state IS readable and nothing can be unreadable. That makes "0 — all records
        # carry a readable verification state" a true and meaningful statement **when there are rows**
        # -- and a claim about the members of an EMPTY SET when there are none, which is what C6 is.
        # The board's own intro promises "Where a figure cannot be determined the page says so and
        # prints —, never a 0", and the `never_restored` row a few keys up already obeys it. This row
        # sat two lines below that one violating it. So: `None`, not `0`, when there is nothing for the
        # claim to be about, and the page says "not applicable".
        "unverifiable_count": 0 if jobs else None,
        "notes": BACKUP_NOTES,
    }
    return render(request, "core/backupboard.html", context)
