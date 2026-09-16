"""Projects 7.10 — ``doc_retention``: the retention & archiving board (a computed page, no table).

Bullet 5's page: the records whose retention window or review date has arrived, the rows under a
legal hold, and the archive. The figures are computed on read against ``timezone.localdate()`` — a
stored "is due" flag would go stale at midnight (the 6.19 ``is_review_due`` ruling).

**The Run raises in-app rows into the 7.9 inbox, and idempotency comes from the TITLE.** 7.9's
``ProjectNotification`` carries no link column and no open/closed state machine — it has a recipient,
a kind, a title and ``is_read`` — so the dedupe key is ``(tenant, kind="due_date", recipient,
title, is_read=False)`` with the document's number AND its date inside the title. The same window
state therefore cannot raise twice, while a genuinely changed date raises a fresh row. The
authoritative re-check happens INSIDE the per-document row lock, so two concurrent Runs cannot both
raise for the same document (the 6.19 posture, adapted to the one field this inbox actually has).

**Nothing here deletes anything, ever.** Module 13.9/13.14 owns enforcement; this board owns the
human-readable queue, and there is no scheduler and no mail worker in this repo (the 6.3/6.19
ruling) — the Run is a button, not a cron.
"""
from datetime import timedelta

from django.db import transaction

from apps.projects.models import ProjectDocument, ProjectNotification
from apps.projects.views._common import *  # noqa: F401,F403
from apps.projects.views._common import (login_required, messages, redirect, render,
                                         require_POST, timezone, write_audit_log)


def _window(days=30):
    """The reminder window: documents whose retention or review date lands inside ``days``."""
    return timezone.localdate() + timedelta(days=days)


def _due_rows(tenant, window_end):
    """Documents whose retention or review date is inside the window, or already past.

    One pass over the tenant's live documents; the two dates derive from two different columns with
    two different semantics, so they are read in Python rather than forced into one SQL expression.
    """
    today = timezone.localdate()
    rows = []
    for row in (ProjectDocument.objects.filter(tenant=tenant, is_archived=False)
                .select_related("project").order_by("number")):
        if row.retain_until and row.retain_until <= window_end:
            rows.append({"document": row, "reason": "retention", "when": row.retain_until,
                         "days_left": (row.retain_until - today).days})
        if row.review_on and row.review_on <= window_end:
            rows.append({"document": row, "reason": "review", "when": row.review_on,
                         "days_left": (row.review_on - today).days})
    return rows


@login_required
def doc_retention(request):
    tenant = request.tenant
    if tenant is None:
        return redirect("dashboard:home")
    due = _due_rows(tenant, _window())
    documents = ProjectDocument.objects.filter(tenant=tenant)
    figures = {
        "retention_due": sum(1 for row in due if row["reason"] == "retention"),
        "review_due": sum(1 for row in due if row["reason"] == "review"),
        "held": documents.filter(is_legal_hold=True).count(),
        "archived": documents.filter(is_archived=True).count(),
        "live": documents.filter(is_archived=False).count(),
        "with_window": documents.filter(retention_months__isnull=False).count(),
    }
    return render(request, "projects/documentknowledge/retention.html", {
        "due": due,
        "figures": figures,
        "window_days": 30,
    })


@login_required
@require_POST
def doc_retention_run(request):
    """Raise one idempotent in-app reminder per in-window document into the 7.9 inbox."""
    tenant = request.tenant
    if tenant is None:
        messages.error(request, "Select a tenant workspace before running reminders.")
        return redirect("dashboard:home")
    rows = _due_rows(tenant, _window())
    raised = skipped = 0
    for row in rows:
        document = row["document"]
        when = row["when"]
        timing = (f"{abs(row['days_left'])} day(s) overdue"
                  if row["days_left"] < 0 else f"in {row['days_left']} day(s)")
        title = f"{document.number} {row['reason']} due {when:%d %b %Y} ({timing})"
        recipient = document.owner or request.user
        with transaction.atomic():
            locked = (ProjectDocument.objects.select_for_update()
                      .get(pk=document.pk, tenant=tenant))
            # The authoritative dedupe, INSIDE the lock: same tenant, same kind, same recipient,
            # same title (which embeds the document's number and its date), still unread.
            already = ProjectNotification.objects.filter(
                tenant=tenant, kind="due_date", recipient=recipient, title=title,
                is_read=False).exists()
            if already:
                skipped += 1
                continue
            ProjectNotification.objects.create(
                tenant=tenant, project=locked.project, recipient=recipient,
                kind="due_date", title=title,
                body=(f"{locked.title} — its {row['reason']} date is {when:%d %b %Y} ({timing}). "
                      f"Upload a replacement revision, push the date out, or archive the record if "
                      f"it no longer applies."),
                task=locked.task, triggered_by=request.user,
            )
            raised += 1
    # `AuditLog.action` is a varchar(10) holding create/update/delete — the verb belongs in
    # `changes`, not in the action. Writing "retention_reminders_run" there truncated to
    # "retention_" on a non-strict server and raised DataError (1406) under STRICT_TRANS_TABLES.
    write_audit_log(request.user, None, "update",
                    {"verb": "retention_reminders_run", "raised": raised,
                     "skipped_open": skipped})
    messages.success(request, f"Retention reminders: {raised} raised, {skipped} already open and "
                              f"unread.")
    return redirect("projects:doc_retention")