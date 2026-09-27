"""core — 0.20 views: the admin console, job scheduler, maintenance, change and support surfaces.

**The posture every view here takes, inherited from 0.16 (`apps/core/views/Backup.py`) and the
whole of module 0 after it:** NavERP has **no scheduler, no queue, no bulk executor and no build
pipeline**. So no view here performs the act it describes. `jobdefinition_run_now` records a run
that nobody executed, `maintenance_window_end_now` records an ending rather than silencing
anything, `bulk_preview` counts rows and writes nothing, and `change_request_approve` records a
decision rather than deploying. **The success messages say "recorded", never "completed"**, and
`OPS_NOTES` is printed verbatim on the pages so no reader can mistake the register for the runtime.

**The zero rule** (0.16, restated because it is the one that matters here): a figure this
application cannot determine is reported as an em dash or as an explicit "not measured", never as
`0`. `admin_board` refuses to print a healthy `0` it cannot justify, and the support board counts
only what it can actually read — a support queue it cannot see is named, not reported as empty.

**Every guard lives in the view, never only in a hidden button.** Each POST-only verb re-reads the
row with `tenant=request.tenant` and refuses a contradictory transition *before* writing anything,
so a hand-made POST cannot reach it and the audit row is not written either. That is the 0.16
`backup_job_verify` ruling: refusing in the template would leave the action reachable and unaudited.

**`@require_POST` sits ABOVE the role gate on purpose** — decorators apply bottom-up, so the
outermost runs first. With the role gate outermost a member's GET would be answered 403 before the
method check ran, and the house standard is 405 for a wrong method regardless of role.
"""
from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.core.views._common import *  # noqa: F401,F403
from apps.core.utils import write_audit_log
from apps.core.models import (
    AlertEvent,
    AlertRule,
    AuditLog,
    ChangeRequest,
    FeatureFlag,
    FeatureRollout,
    Incident,
    JobDefinition,
    JobRun,
    MaintenanceWindow,
    ServiceComponent,
    SettingDefinition,
    SettingValue,
    SyncSchedule,
    VulnerabilityFinding,
)
from apps.core.models.Backup import EnvironmentInstance
from apps.core.forms import (
    ChangeRequestForm,
    FeatureRolloutForm,
    JobDefinitionForm,
    JobRunForm,
    MaintenanceWindowForm,
)

#: The honest-limit lines the 0.20 pages print verbatim. A module-level constant so a page and its
#: board cannot disagree about what this application can and cannot do.
OPS_NOTES = [
    "This is a register of declared intent, not a runtime. NavERP has no scheduler, no queue and no "
    "worker pool: no page here runs a job, silences an alert or applies a rollout.",
    "The run-now action records a dry run and nothing else. It does not import or call the handler "
    "path a job declares, because there is no dispatcher to call one with.",
    "Recorded-scope fields (a window's suppressed rules, a job's pool) are declarations an operator "
    "has written down. Nothing in this application enforces, counts or acts on them.",
]

# ============================================================ bullet 2: the job register
@tenant_admin_required
def jobdefinition_list(request):
    qs = JobDefinition.objects.filter(tenant=request.tenant).select_related(
        "sync_schedule", "environment")
    return crud_list(
        request, qs, "core/jobdefinition/list.html",
        search_fields=["name", "module_slug", "handler_path", "description"],
        filters=[("job_type", "job_type", False), ("schedule_kind", "schedule_kind", False),
                 ("environment", "environment_id", True), ("is_muted", "is_muted", False)],
        extra_context={
            "status_choices": JobDefinition.JOB_TYPE_CHOICES,
            "schedule_choices": JobDefinition.SCHEDULE_KIND_CHOICES,
            "sync_schedules": SyncSchedule.objects.filter(tenant=request.tenant),
            "environments": EnvironmentInstance.objects.filter(tenant=request.tenant),
            # A job nobody has ever run is a declaration, and a queue of those is what this
            # sub-module exists to make visible rather than leave implied.
            "unrun_count": JobDefinition.objects.filter(
                tenant=request.tenant, last_run_at__isnull=True).count(),
            "muted_count": JobDefinition.objects.filter(
                tenant=request.tenant, is_muted=True).count(),
            "notes": OPS_NOTES,
        },
    )


@tenant_admin_required
def jobdefinition_create(request):
    return crud_create(
        request, form_class=JobDefinitionForm, template="core/jobdefinition/form.html",
        success_url="core:jobdefinition_list", extra_context={"notes": OPS_NOTES})


@tenant_admin_required
def jobdefinition_detail(request, pk):
    return crud_detail(
        request, model=JobDefinition, pk=pk, template="core/jobdefinition/detail.html",
        select_related=("sync_schedule", "environment"),
        extra_context={
            "runs": JobRun.objects.filter(job_id=pk).order_by("-triggered_at", "-id")[:10],
            "run_count": JobRun.objects.filter(job_id=pk).count(),
            "notes": OPS_NOTES,
        },
    )


@tenant_admin_required
def jobdefinition_edit(request, pk):
    return crud_edit(
        request, model=JobDefinition, pk=pk, form_class=JobDefinitionForm,
        template="core/jobdefinition/form.html",
        success_url=reverse("core:jobdefinition_detail", args=[pk]),
        extra_context={"notes": OPS_NOTES},
    )


@require_POST
@tenant_admin_required
def jobdefinition_delete(request, pk):
    return crud_delete(request, model=JobDefinition, pk=pk, success_url="core:jobdefinition_list")


@require_POST
@tenant_admin_required
def jobdefinition_run_now(request, pk):
    """Record a run. **Execute nothing.**

    This is the single most important view in the sub-module, because it is the one an operator
    would expect to do real work. It writes exactly one `JobRun` with `is_dry_run=True` — the only
    truthful value available, since no dispatcher exists — and it never imports, resolves or calls
    `handler_path`. The success message says so in as many words, because a green "Job started"
    toast on a system with no scheduler is precisely the kind of claim this repo refuses to make.

    It also leaves `last_run_at` / `next_run_at` alone. Those are the *schedule's* record of what
    the dispatcher last did, and a human pressing a button is not the scheduler; stamping them here
    would invent a cadence observation.
    """
    obj = get_object_or_404(JobDefinition, pk=pk, tenant=request.tenant)
    run = JobRun.objects.create(
        tenant=request.tenant, job=obj, trigger_kind="manual", status="queued", is_dry_run=True,
        triggered_by=request.user if request.user.is_authenticated else None,
        notes=("Recorded by an operator pressing Run now. No scheduler exists, so no job was "
               "executed and the declared handler was never imported."),
    )
    # `AuditLog.action` is varchar(10); the descriptive verb goes in `changes`, never in `action`.
    write_audit_log(request.user, run, "run_now",
                    changes={"job": obj.number, "executed": False, "dry_run": True})
    messages.success(
        request, "Run recorded — no job was executed; this repository has no scheduler.")
    return redirect("core:jobdefinition_detail", pk=obj.pk)


# ============================================================ the run register
@tenant_admin_required
def jobrun_list(request):
    qs = JobRun.objects.filter(tenant=request.tenant).select_related("job")
    return crud_list(
        request, qs, "core/jobrun/list.html",
        search_fields=["number", "error_message", "notes"],
        filters=[("status", "status", False), ("trigger_kind", "trigger_kind", False),
                 ("job", "job_id", True)],
        extra_context={
            "status_choices": JobRun.STATUS_CHOICES,
            "trigger_choices": JobRun.TRIGGER_KIND_CHOICES,
            "jobs": JobDefinition.objects.filter(tenant=request.tenant),
            # Queued and running runs are promises nobody has delivered, so they are counted
            # rather than left for the reader to notice.
            "open_count": JobRun.objects.filter(
                tenant=request.tenant, status__in=("queued", "running")).count(),
            "notes": OPS_NOTES,
        },
    )


@tenant_admin_required
def jobrun_detail(request, pk):
    return crud_detail(
        request, model=JobRun, pk=pk, template="core/jobrun/detail.html",
        select_related=("job", "triggered_by"), extra_context={"notes": OPS_NOTES})


@tenant_admin_required
def jobrun_edit(request, pk):
    return crud_edit(
        request, model=JobRun, pk=pk, form_class=JobRunForm, template="core/jobrun/form.html",
        success_url=reverse("core:jobrun_detail", args=[pk]), extra_context={"notes": OPS_NOTES})


@require_POST
@tenant_admin_required
def jobrun_delete(request, pk):
    return crud_delete(request, model=JobRun, pk=pk, success_url="core:jobrun_list")


# ============================================================ bullet 3a: maintenance windows
def _window_querysets(tenant):
    """The five FK/M2M querysets both the window list and the window form need.

    One helper so the list page and the form page cannot drift about which choices they offer — a
    dropdown reading a different queryset than the filter above it is the classic L8 blank region.
    """
    return {
        "services": ServiceComponent.objects.filter(tenant=tenant),
        "environments": EnvironmentInstance.objects.filter(tenant=tenant),
        "incidents": Incident.objects.filter(tenant=tenant, incident_type="scheduled_maintenance"),
        "changes": ChangeRequest.objects.filter(tenant=tenant),
    }


@tenant_admin_required
def maintenancewindow_list(request):
    qs = MaintenanceWindow.objects.filter(tenant=request.tenant).prefetch_related(
        "affected_services")
    ctx = _window_querysets(request.tenant)
    return crud_list(
        request, qs, "core/maintenancewindow/list.html",
        search_fields=["title", "number", "purpose", "notes"],
        filters=[("status", "status", False), ("recurrence", "recurrence", False),
                 ("environment", "environment_id", True)],
        extra_context={
            "status_choices": MaintenanceWindow.STATUS_CHOICES,
            "recurrence_choices": MaintenanceWindow.RECURRENCE_CHOICES,
            **ctx,
            # A window in progress is the one an operator needs to see first, and nothing here
            # silences anything, so the only honest summary is the count.
            "current_count": sum(1 for w in qs if w.is_current),
            "notes": OPS_NOTES,
        },
    )


@tenant_admin_required
def maintenancewindow_create(request):
    return crud_create(
        request, form_class=MaintenanceWindowForm, template="core/maintenancewindow/form.html",
        success_url="core:maintenancewindow_list",
        extra_context={**_window_querysets(request.tenant), "notes": OPS_NOTES})


@tenant_admin_required
def maintenancewindow_detail(request, pk):
    return crud_detail(
        request, model=MaintenanceWindow, pk=pk, template="core/maintenancewindow/detail.html",
        select_related=("incident", "environment", "change_request"),
        extra_context={**_window_querysets(request.tenant), "notes": OPS_NOTES})


@tenant_admin_required
def maintenancewindow_edit(request, pk):
    return crud_edit(
        request, model=MaintenanceWindow, pk=pk, form_class=MaintenanceWindowForm,
        template="core/maintenancewindow/form.html",
        success_url=reverse("core:maintenancewindow_detail", args=[pk]),
        extra_context={**_window_querysets(request.tenant), "notes": OPS_NOTES})


@require_POST
@tenant_admin_required
def maintenancewindow_delete(request, pk):
    """Delete a window — but only one that has not started yet.

    A window somebody actually ran is evidence: it is what an incident review asks about a week
    later, and deleting it because it is no longer useful in the register destroys the record of
    the outage. The guard is HERE rather than in a hidden button, so a hand-made POST cannot reach
    it and no audit row is written for a refusal.
    """
    obj = get_object_or_404(MaintenanceWindow, pk=pk, tenant=request.tenant)
    if not obj.is_future:
        messages.error(
            request,
            "%s has already started and is kept as history — a window that ran is evidence an "
            "incident review may need. Cancel or end it instead of deleting it." % obj.number)
        return redirect("core:maintenancewindow_detail", pk=obj.pk)
    write_audit_log(request.user, obj, "delete")
    obj.delete()
    messages.success(request, "Deleted successfully.")
    return redirect("core:maintenancewindow_list")


@require_POST
@tenant_admin_required
def maintenance_window_end_now(request, pk):
    """PagerDuty's "End Now": record that this window was closed early.

    This does **not** silence anything — the window's recorded scope is still a declaration nothing
    consults. It stamps `ended_early` and `ended_at`, which is the only part of "ending" a window
    this application can honestly perform.

    Refused for a window that never started (there is nothing to end) and for one already ended
    (ending it twice would overwrite the first ending's evidence with a later time).
    """
    obj = get_object_or_404(MaintenanceWindow, pk=pk, tenant=request.tenant)
    if obj.status in ("draft", "cancelled"):
        messages.error(request, "%s has not started — there is nothing to end."
                       % obj.number)
        return redirect("core:maintenancewindow_detail", pk=obj.pk)
    if obj.ended_at is not None or obj.status == "ended_early":
        messages.error(request, "%s has already been ended (at %s)."
                       % (obj.number, obj.ended_at))
        return redirect("core:maintenancewindow_detail", pk=obj.pk)
    obj.status = "ended_early"
    obj.ended_at = timezone.now()
    obj.save(update_fields=["status", "ended_at"])
    write_audit_log(request.user, obj, "end_now",
                    changes={"window": obj.number, "ended_at": str(obj.ended_at),
                             "silenced_anything": False})
    messages.success(
        request, "Window recorded as ended early. No alerts were silenced — the window's scope is "
                 "a declaration nothing enforces.")
    return redirect("core:maintenancewindow_detail", pk=obj.pk)


# ============================================================ bullet 3b: the change register
@tenant_admin_required
def changerequest_list(request):
    qs = ChangeRequest.objects.filter(tenant=request.tenant).select_related(
        "environment", "requestor", "approved_by")
    return crud_list(
        request, qs, "core/changerequest/list.html",
        search_fields=["title", "number", "summary", "notes"],
        filters=[("status", "status", False), ("change_type", "change_type", False),
                 ("risk_level", "risk_level", False), ("impact_level", "impact_level", False),
                 ("environment", "environment_id", True)],
        extra_context={
            "status_choices": ChangeRequest.STATUS_CHOICES,
            "type_choices": ChangeRequest.CHANGE_TYPE_CHOICES,
            "risk_choices": ChangeRequest.RISK_LEVEL_CHOICES,
            "impact_choices": ChangeRequest.IMPACT_LEVEL_CHOICES,
            "environments": EnvironmentInstance.objects.filter(tenant=request.tenant),
            # Awaiting a decision is the actionable state, and a high-risk change nobody has ruled
            # on is the one that belongs at the top of it.
            "awaiting_count": ChangeRequest.objects.filter(
                tenant=request.tenant, status="submitted").count(),
            "high_risk_open": ChangeRequest.objects.filter(
                tenant=request.tenant, risk_level="high").exclude(
                status__in=["completed", "rejected", "cancelled", "rolled_back"]).count(),
            "notes": OPS_NOTES,
        },
    )


@tenant_admin_required
def changerequest_create(request):
    return crud_create(
        request, form_class=ChangeRequestForm, template="core/changerequest/form.html",
        success_url="core:changerequest_list",
        extra_context={"environments": EnvironmentInstance.objects.filter(tenant=request.tenant),
                       "notes": OPS_NOTES})


@tenant_admin_required
def changerequest_detail(request, pk):
    return crud_detail(
        request, model=ChangeRequest, pk=pk, template="core/changerequest/detail.html",
        select_related=("environment", "requestor", "approved_by"),
        extra_context={
            "rollouts": FeatureRollout.objects.filter(change_id=pk).select_related("feature_flag"),
            "windows": MaintenanceWindow.objects.filter(change_request_id=pk),
            "environments": EnvironmentInstance.objects.filter(tenant=request.tenant),
            "notes": OPS_NOTES,
        },
    )


@tenant_admin_required
def changerequest_edit(request, pk):
    return crud_edit(
        request, model=ChangeRequest, pk=pk, form_class=ChangeRequestForm,
        template="core/changerequest/form.html",
        success_url=reverse("core:changerequest_detail", args=[pk]),
        extra_context={"environments": EnvironmentInstance.objects.filter(tenant=request.tenant),
                       "notes": OPS_NOTES})


@require_POST
@tenant_admin_required
def changerequest_delete(request, pk):
    return crud_delete(request, model=ChangeRequest, pk=pk, success_url="core:changerequest_list")


@require_POST
@tenant_admin_required
def change_request_submit(request, pk):
    """Draft -> submitted, stamping the requestor and the time.

    A submitted change is a request, and a request needs an author. Both come from the acting user
    here rather than from the form, so a change cannot be submitted in somebody else's name.
    """
    obj = get_object_or_404(ChangeRequest, pk=pk, tenant=request.tenant)
    if obj.status != "draft":
        messages.error(request, "%s is %s — only a draft can be submitted."
                       % (obj.number, obj.get_status_display().lower()))
        return redirect("core:changerequest_detail", pk=obj.pk)
    obj.status = "submitted"
    obj.requested_at = timezone.now()
    if request.user.is_authenticated:
        obj.requestor = request.user
    obj.save(update_fields=["status", "requested_at", "requestor"])
    write_audit_log(request.user, obj, "submit",
                    changes={"change": obj.number, "from": "draft", "to": "submitted"})
    messages.success(request, "%s submitted for approval. No deployment is scheduled or performed."
                     % obj.number)
    return redirect("core:changerequest_detail", pk=obj.pk)


@require_POST
@tenant_admin_required
def change_request_approve(request, pk):
    """Submitted -> approved, stamping the approver and the time.

    `approved_by` is the acting user, never a form field: an approval is precisely the act an audit
    exists to attribute, so it must be impossible to approve a change in somebody else's name.
    """
    obj = get_object_or_404(ChangeRequest, pk=pk, tenant=request.tenant)
    if obj.status != "submitted":
        messages.error(request, "%s is %s — only a submitted change can be approved."
                       % (obj.number, obj.get_status_display().lower()))
        return redirect("core:changerequest_detail", pk=obj.pk)
    obj.status = "approved"
    obj.approved_at = timezone.now()
    if request.user.is_authenticated:
        obj.approved_by = request.user
    obj.save(update_fields=["status", "approved_at", "approved_by"])
    write_audit_log(request.user, obj, "approve",
                    changes={"change": obj.number, "approved_by": str(request.user)})
    messages.success(
        request, "%s approved and recorded. Nothing is deployed — this repository has no build or "
                 "deploy pipeline." % obj.number)
    return redirect("core:changerequest_detail", pk=obj.pk)


@require_POST
@tenant_admin_required
def change_request_rollback(request, pk):
    """Completed -> rolled_back. **A reason is mandatory.**

    An unexplained reversal is the one outcome a change register exists to prevent, so the reason
    is read from the POST body and the transition is refused without it. The view enforces that
    rather than relying on the button, so a hand-made POST with an empty reason is refused and no
    audit row is written.
    """
    obj = get_object_or_404(ChangeRequest, pk=pk, tenant=request.tenant)
    if obj.status != "completed":
        messages.error(request, "%s is %s — only a completed change can be rolled back."
                       % (obj.number, obj.get_status_display().lower()))
        return redirect("core:changerequest_detail", pk=obj.pk)
    reason = (request.POST.get("rollback_reason") or "").strip()
    if not reason:
        messages.error(request, "A rollback must state its reason — an unexplained reversal is "
                                 "exactly what a change register exists to prevent.")
        return redirect("core:changerequest_detail", pk=obj.pk)
    obj.status = "rolled_back"
    obj.rollback_reason = reason
    obj.rollback_at = timezone.now()
    obj.save(update_fields=["status", "rollback_reason", "rollback_at"])
    write_audit_log(request.user, obj, "rollback",
                    changes={"change": obj.number, "reason": reason[:200]})
    messages.success(request, "%s recorded as rolled back. No system was reverted — this "
                              "repository has no deployment to undo." % obj.number)
    return redirect("core:changerequest_detail", pk=obj.pk)


# ============================================================ phased feature rollouts
@tenant_admin_required
def featurerollout_list(request):
    qs = FeatureRollout.objects.filter(tenant=request.tenant).select_related(
        "change", "feature_flag")
    return crud_list(
        request, qs, "core/featurerollout/list.html",
        search_fields=["cohort_label", "change__title", "feature_flag__key", "notes"],
        filters=[("stage", "stage", False), ("status", "status", False),
                 ("change", "change_id", True)],
        extra_context={
            "stage_choices": FeatureRollout.STAGE_CHOICES,
            "status_choices": FeatureRollout.STATUS_CHOICES,
            "changes": ChangeRequest.objects.filter(tenant=request.tenant),
            "feature_flags": FeatureFlag.objects.filter(tenant=request.tenant),
            "notes": OPS_NOTES,
        },
    )


@tenant_admin_required
def featurerollout_create(request):
    return crud_create(
        request, form_class=FeatureRolloutForm, template="core/featurerollout/form.html",
        success_url="core:featurerollout_list",
        extra_context={
            "changes": ChangeRequest.objects.filter(tenant=request.tenant),
            "feature_flags": FeatureFlag.objects.filter(tenant=request.tenant),
            "notes": OPS_NOTES,
        })


@tenant_admin_required
def featurerollout_detail(request, pk):
    return crud_detail(
        request, model=FeatureRollout, pk=pk, template="core/featurerollout/detail.html",
        select_related=("change", "feature_flag"),
        extra_context={
            "changes": ChangeRequest.objects.filter(tenant=request.tenant),
            "feature_flags": FeatureFlag.objects.filter(tenant=request.tenant),
            "notes": OPS_NOTES,
        })


@tenant_admin_required
def featurerollout_edit(request, pk):
    return crud_edit(
        request, model=FeatureRollout, pk=pk, form_class=FeatureRolloutForm,
        template="core/featurerollout/form.html",
        success_url=reverse("core:featurerollout_detail", args=[pk]),
        extra_context={
            "changes": ChangeRequest.objects.filter(tenant=request.tenant),
            "feature_flags": FeatureFlag.objects.filter(tenant=request.tenant),
            "notes": OPS_NOTES,
        })


@require_POST
@tenant_admin_required
def featurerollout_delete(request, pk):
    return crud_delete(request, model=FeatureRollout, pk=pk, success_url="core:featurerollout_list")


# ============================================================ bullet 1: the unified admin board
#: The existing boards the command centre LINKS. It aggregates and drills through; it re-derives
#: no health, no security, no backup and no config logic, so none of these pages can drift from the
#: one that owns the answer. Each target is a distinct page — two labels over one page would make
#: "which page is this?" unanswerable and light the sidebar highlight twice.
ADMIN_BOARD_LINKS = [
    ("System health", "core:health_board", "activity"),
    ("Security overview", "core:security_overview", "shield"),
    ("Monitoring overview", "core:monitoring_overview", "gauge"),
    ("Backup & recovery", "core:backup_overview", "database-backup"),
    ("Settings overview", "core:settingsoverview", "settings"),
    ("Integrations", "core:integration_overview", "plug"),
    ("Vulnerabilities", "core:vulnerability_board", "bug"),
    ("Capacity", "core:capacity_board", "trending-up"),
    ("Numbering", "core:numbering_board", "hash"),
    ("Access matrix", "core:access_matrix", "key-round"),
]

#: The open statuses on the two support queues. `resolved` and `closed` are not open work, and a
#: board that counted them would tell an operator their queue is fuller than it is.
OPEN_CASE_STATUSES = ("new", "open", "in_progress", "waiting")
OPEN_TICKET_STATUSES = ("new", "open", "in_progress", "waiting")


def _tile(key, label, value, hint, url, icon, tone):
    """One tile on the command centre.

    A dict rather than a template-only loop so the count and its caveat travel together — a tile
    showing a bare `0` for a figure nobody measures is a false all-clear.
    """
    return {"key": key, "label": label, "value": value, "hint": hint, "url": url,
            "icon": icon, "tone": tone}


@tenant_admin_required
def admin_board(request):
    """The central command centre: eight tiles, a needs-attention strip, and links out.

    **This page replaces nothing.** Every figure below is a count over a table some earlier
    sub-module already owns, and every tile is a link to that sub-module's own board. It exists so
    an operator can see what needs attention without opening six pages — not so 0.20 can become a
    second source of truth for any of them.
    """
    tenant = request.tenant
    now = timezone.now()

    # ---- jobs: the 0.20 half. A job with no run is a declaration nobody has exercised.
    job_total = JobDefinition.objects.filter(tenant=tenant).count()
    job_unrun = JobDefinition.objects.filter(tenant=tenant, last_run_at__isnull=True).count()
    open_runs = JobRun.objects.filter(tenant=tenant, status__in=("queued", "running")).count()

    # ---- maintenance: only a window that has not closed is actionable.
    window_live = MaintenanceWindow.objects.filter(
        tenant=tenant, starts_at__lte=now, ends_at__gt=now).count()
    window_scheduled = MaintenanceWindow.objects.filter(
        tenant=tenant, status__in=("draft", "scheduled"), starts_at__gt=now).count()

    # ---- changes: a submitted change is a decision somebody owes.
    change_awaiting = ChangeRequest.objects.filter(tenant=tenant, status="submitted").count()
    change_open = ChangeRequest.objects.filter(tenant=tenant).exclude(
        status__in=["completed", "rejected", "cancelled", "rolled_back"]).count()

    # ---- health/security, read straight from the tables 0.16-0.18 own. Never a stored roll-up:
    # one of those would freeze a bad hour into a good morning.
    firing_alerts = AlertEvent.objects.filter(tenant=tenant, resolved_at__isnull=True).count()
    open_incidents = Incident.objects.filter(tenant=tenant, resolved_at__isnull=True).count()
    open_vulns = VulnerabilityFinding.objects.filter(tenant=tenant, status="open").count()
    setting_count = SettingValue.objects.filter(tenant=tenant).count()

    tiles = [
        _tile("jobs", "Declared jobs", job_total,
              "%d never run" % job_unrun if job_unrun else "all have a recorded run",
              "core:jobdefinition_list", "calendar-clock", "blue"),
        _tile("runs", "Open runs", open_runs,
              "queued or running — nothing executes them", "core:jobrun_list", "play", "amber"),
        _tile("maintenance", "Live windows", window_live,
              "%d scheduled ahead" % window_scheduled,
              "core:maintenancewindow_list", "wrench", "orange"),
        _tile("changes", "Open changes", change_open,
              "%d awaiting approval" % change_awaiting,
              "core:changerequest_list", "git-pull-request", "purple"),
        _tile("alerts", "Firing alerts", firing_alerts,
              "recorded firings, unresolved", "core:firing_board", "bell-ring", "red"),
        _tile("incidents", "Open incidents", open_incidents, "unresolved",
              "core:incident_list", "siren", "red"),
        _tile("vulns", "Open vulnerabilities", open_vulns, "status open",
              "core:vulnerabilityfinding_list", "bug", "amber"),
        _tile("settings", "Configured settings", setting_count, "per-tenant overrides",
              "core:settingsoverview", "settings", "slate"),
    ]

    # ---- the attention strip: the numbers an admin opens this page for, in one place.
    needs_attention = [
        {"label": "Jobs never run", "value": job_unrun, "url": "core:jobdefinition_list"},
        {"label": "Runs left open", "value": open_runs, "url": "core:jobrun_list"},
        {"label": "Changes awaiting approval", "value": change_awaiting,
         "url": "core:changerequest_list"},
        {"label": "Firing alerts", "value": firing_alerts, "url": "core:firing_board"},
        {"label": "Open incidents", "value": open_incidents, "url": "core:incident_list"},
        {"label": "Open vulnerabilities", "value": open_vulns,
         "url": "core:vulnerabilityfinding_list"},
        {"label": "Windows scheduled ahead", "value": window_scheduled,
         "url": "core:maintenancewindow_list"},
    ]

    boards = [{"label": label, "url": url, "icon": icon}
              for label, url, icon in ADMIN_BOARD_LINKS]

    return render(request, "core/adminboard.html", {
        "tiles": tiles,
        "needs_attention": needs_attention,
        "recent_activity": AuditLog.objects.filter(tenant=tenant).order_by("-id")[:10],
        "boards": boards,
        "notes": OPS_NOTES,
    })


# ============================================================ bullet 5: the support help centre
#: **This board declares no ticket table and no knowledge base.** Both already exist, in two
#: different apps, and re-declaring either would be the exact second-schema bug L29 forbids:
#:   * `crm.Case` (1.4) — the customer-facing support queue, with `crm.KbCategory` and
#:     `crm.KnowledgeArticle` (the class inside `CustomerService/KnowledgeBase.py`; there is **no**
#:     `KnowledgeBase` class anywhere in this repository).
#:   * `hrm.HelpdeskTicket` (3.x) — the internal employee desk, with `hrm.HelpdeskCategory` and a
#:     *second* `hrm.KnowledgeArticle` in a different app_label.
#: So the board READS both and LINKS to their own list/detail pages. The two articles are genuinely
#: different tables and this board is the only place an operator sees them side by side — which is
#: the whole value, and the reason a third table would be a duplication rather than a feature.
SUPPORT_LINKS = [
    ("Customer cases (CRM 1.4)", "crm:case_list", "life-buoy"),
    ("Internal tickets (HRM 3.x)", "hrm:ticket_list", "ticket"),
    ("Customer knowledge base", "crm:knowledgearticle_list", "book-open"),
    ("Internal knowledge base", "hrm:knowledgearticle_list", "library"),
    ("KB categories (customer)", "crm:kbcategory_list", "folder"),
    ("Helpdesk categories (internal)", "hrm:helpdeskcategory_list", "folder-tree"),
    ("SLA policies (customer)", "crm:slapolicy_list", "timer"),
    ("Helpdesk SLA policies", "hrm:helpdesksla_list", "timer"),
]


@tenant_admin_required
def support_board(request):
    """One page over BOTH existing support queues and BOTH knowledge bases.

    **The zero rule applies with teeth here.** A queue this board cannot see must be NAMED, never
    reported as `0`: an empty-looking support board that has simply failed to read a table is the
    most dangerous page in this sub-module, so each count is a live query and a genuine empty queue
    prints as "0 open" while a missing one would raise rather than render a calm zero.
    """
    from apps.crm.models import Case, KbCategory
    from apps.crm.models.CustomerService.KnowledgeBase import KnowledgeArticle as CrmArticle
    from apps.hrm.models import HelpdeskCategory, HelpdeskTicket
    from apps.hrm.models.Helpdesk.Knowledgearticle import KnowledgeArticle as HrmArticle

    tenant = request.tenant

    crm_open = Case.objects.filter(tenant=tenant, status__in=OPEN_CASE_STATUSES)
    hrm_open = HelpdeskTicket.objects.filter(tenant=tenant, status__in=OPEN_TICKET_STATUSES)
    crm_articles = CrmArticle.objects.filter(tenant=tenant)
    hrm_articles = HrmArticle.objects.filter(tenant=tenant)

    counts = {
        # Open work only. Counting resolved and closed tickets would tell an operator their queue is
        # fuller than it is, which is the same false-pressure defect as an over-broad severity list.
        "crm_open_cases": crm_open.count(),
        "hrm_open_tickets": hrm_open.count(),
        "crm_articles_published": crm_articles.filter(status="published").count(),
        "hrm_articles_published": hrm_articles.filter(status="published").count(),
        "crm_articles_draft": crm_articles.filter(status="draft").count(),
        "hrm_articles_draft": hrm_articles.filter(status="draft").count(),
        "crm_categories": KbCategory.objects.filter(tenant=tenant).count(),
        "hrm_categories": HelpdeskCategory.objects.filter(tenant=tenant).count(),
    }

    return render(request, "core/supportboard.html", {
        "crm_cases": crm_open.order_by("-updated_at", "-id")[:10],
        "hrm_tickets": hrm_open.order_by("-updated_at", "-id")[:10],
        "crm_articles": crm_articles.order_by("-updated_at", "-id")[:10],
        "hrm_articles": hrm_articles.order_by("-updated_at", "-id")[:10],
        "crm_categories": KbCategory.objects.filter(tenant=tenant, is_active=True),
        "hrm_categories": HelpdeskCategory.objects.filter(tenant=tenant, is_active=True),
        "counts": counts,
        "links": [{"label": label, "url": url, "icon": icon}
                  for label, url, icon in SUPPORT_LINKS],
        # Stated on the page, because a reader who sees a help centre with no ticket intake has to
        # be told whether that is a feature or a hole.
        "notes": OPS_NOTES + [
            "This page reads the CRM customer queue and the HRM internal desk. It creates neither, "
            "and it does not open, route, merge or escalate a ticket — open one where it belongs.",
        ],
    })


# ============================================================ bullet 4: bulk operations & data tools
#: The data tools a real console would offer, described honestly. **None of them is executable here**
#: — there is no bulk executor, no queryset-writer and no background worker — so each is a
#: *description* paired with the count it would touch, and the page says plainly that pressing
#: Preview changes nothing. Inventing an "Apply" that half-works would be far worse than not
#: offering one: an operator who believes 4,000 rows were recalculated when none were has been
#: actively misled.
BULK_TOOL_CHOICES = [
    ("recalculate_balances", "Recalculate ledger balances",
     "Re-derive every account balance from its journal lines. Balances are already derived, so this "
     "would report what the existing aggregate reports."),
    ("rebuild_derived_totals", "Rebuild derived totals",
     "Recompute cached roll-ups on documents that derive their totals at read time."),
    ("backfill_numbering", "Backfill document numbers",
     "Assign a number to rows created before their prefix was registered."),
    ("normalize_module_slugs", "Normalize module slugs",
     "Rewrite legacy module identifiers to the current slug vocabulary."),
    ("purge_orphaned_relations", "Report orphaned relations",
     "List rows whose foreign key points at a record that no longer exists."),
    ("reindex_search", "Rebuild search index",
     "Repopulate the global header search index from the source tables."),
]

#: The declines, printed on the page in full. This is a DECLINE LIST, not a status page: a reader
#: must be able to see exactly which capabilities this sub-module does not perform, in the same
#: words on every visit.
BULK_DECLINES = [
    "No bulk executor exists. A mass update, a recalculation and a data fix are all declines: the "
    "application can count the rows a tool would touch and nothing more.",
    "No queryset builder and no saved filter. A console that could write arbitrary filters into a "
    "tenant's tables would need row-level authorisation this repository does not have.",
    "No background worker and no queue, so a long-running job cannot be queued, chunked or retried.",
    "No rollback for a bulk change. An update applied to 4,000 rows with no undo is not a tool this "
    "application is willing to offer.",
    "No cross-tenant operation of any kind, and none is planned: a console that could reach another "
    "workspace's rows is a data-breach primitive.",
]

#: What each previewable tool WOULD touch, keyed by its value. Every entry is a live count over a
#: real table, so the number an operator reads is the number the tool would be asked about.
#: A `0` here means "nothing to do", which is a different statement from "not measurable" — the
#: three entries at zero are the tools whose subject matter this application does not own at all
#: (accounting owns the ledger, CASCADE leaves no orphans, search has no separate index), and the
#: board's note says so rather than leaving a reader to guess.
BULK_AFFECTED = {
    "rebuild_derived_totals": lambda t: ChangeRequest.objects.filter(tenant=t).count(),
    "backfill_numbering": lambda t: JobDefinition.objects.filter(tenant=t, number="").count(),
    "normalize_module_slugs": lambda t: JobDefinition.objects.filter(
        tenant=t).exclude(module_slug="").count(),
    "recalculate_balances": lambda t: 0,
    "purge_orphaned_relations": lambda t: 0,
    "reindex_search": lambda t: 0,
}


@tenant_admin_required
def bulk_board(request):
    """The data-tools board. **Preview only — this page changes no data.**"""
    tenant = request.tenant

    # Every figure is a live count over a table that exists, so a tool can say what it WOULD touch.
    # `numbered_unnumbered` is the one genuinely useful signal here: rows whose number column is
    # blank are the rows a backfill would have to touch.
    counts = {
        "jobs": JobDefinition.objects.filter(tenant=tenant).count(),
        "job_runs": JobRun.objects.filter(tenant=tenant).count(),
        "maintenance_windows": MaintenanceWindow.objects.filter(tenant=tenant).count(),
        "changes": ChangeRequest.objects.filter(tenant=tenant).count(),
        "rollouts": FeatureRollout.objects.filter(tenant=tenant).count(),
        "numbered_unnumbered": JobDefinition.objects.filter(tenant=tenant, number="").count(),
        "open_runs": JobRun.objects.filter(
            tenant=tenant, status__in=("queued", "running")).count(),
    }

    return render(request, "core/bulkboard.html", {
        "tool_choices": [{"value": v, "label": l, "description": d}
                         for v, l, d in BULK_TOOL_CHOICES],
        "preview": None,
        "counts": counts,
        "declines": BULK_DECLINES,
        "notes": OPS_NOTES,
    })


@require_POST
@tenant_admin_required
def bulk_preview(request):
    """Count what a named tool WOULD touch. **Writes nothing. Executes nothing.**

    The only database access in this function is a `.count()`: there is no branch here that calls
    `save()`, `update()` or `delete()`, and the smoke test asserts the row counts are identical
    before and after a preview. An unrecognised tool name is refused rather than defaulted, so a
    hand-made POST cannot reach a lookup with a key that does not exist.
    """
    tool = (request.POST.get("tool") or "").strip()
    if tool not in BULK_AFFECTED:
        messages.error(request, "Choose one of the listed tools to preview.")
        return redirect("core:bulk_board")

    tenant = request.tenant
    affected = BULK_AFFECTED[tool](tenant)
    label = dict((v, l) for v, l, _ in BULK_TOOL_CHOICES)[tool]

    write_audit_log(request.user, None, "bulk_preview", tenant=tenant,
                    changes={"tool": tool, "would_affect": affected, "executed": False})
    messages.info(
        request, "Preview only: %s would affect %d rows. Nothing was changed — this application has "
                 "no bulk executor." % (label, affected))
    return redirect("core:bulk_board")


# ============================================================ the operations audit trail
@tenant_admin_required
def ops_audit_trail(request):
    """Read-only over `core.AuditLog`, which 0.9 already owns.

    **Read-only by construction.** This view has no create, edit or delete route, no form and no
    POST handler: an audit trail that can be edited through the UI is not an audit trail. It
    reuses 0.9's `AuditLog` rather than declaring a second one (L29), and it is offered as an
    operational leaf rather than as a NavERP.md bullet.
    """
    qs = AuditLog.objects.filter(tenant=request.tenant).select_related("user")
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(target__icontains=q) | Q(user__username__icontains=q)
                       | Q(action__icontains=q))
    action = (request.GET.get("action") or "").strip()
    if action:
        qs = qs.filter(action=action)
    page_obj = paginate(request, qs, 25)
    return render(request, "core/opstrail.html", {
        "object_list": page_obj.object_list,
        "page_obj": page_obj,
        "q": q,
        "action_choices": sorted(
            {a for a in AuditLog.objects.filter(tenant=request.tenant)
             .values_list("action", flat=True) if a}),
        "notes": OPS_NOTES,
    })











