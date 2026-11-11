from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounting.models import JournalEntry, JournalLine
from apps.assets.forms.IntegrationApiHub.AssetGlSyncBatches import (
    AssetGlSyncBatchForm,
)
from apps.assets.models.IntegrationApiHub.AssetGlSyncBatches import (
    AssetGlSyncBatch,
)
from apps.assets.models.IntegrationApiHub.AssetIntegrationConnectors import (
    AssetIntegrationConnector,
)
from apps.assets.views._common import (
    assets_object,
    assets_scope,
    safe_parse_date,
)
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log


@login_required
def batch_list(request):
    """List tenant-scoped Asset GL Sync & Reconciliation Batches with KPIs and date/domain filters."""
    base_qs = assets_scope(
        AssetGlSyncBatch.objects.select_related(
            "connector",
            "fiscal_period",
            "gl_account",
            "offset_gl_account",
            "currency",
            "journal_entry",
            "executed_by",
        ),
        request,
    )

    kpis = base_qs.aggregate(
        total=Count("id"),
        posted=Count("id", filter=Q(status="posted")),
        variance=Count("id", filter=Q(reconciliation_status="variance_flagged")),
        draft=Count("id", filter=Q(status="draft")),
    )

    qs = base_qs
    q = (request.GET.get("q") or "").strip()
    connector_id = (request.GET.get("connector") or "").strip()
    sync_domain = (request.GET.get("sync_domain") or "").strip()
    status = (request.GET.get("status") or "").strip()
    reconciliation_status = (request.GET.get("reconciliation_status") or "").strip()
    date_from = safe_parse_date(request.GET.get("date_from"))
    date_to = safe_parse_date(request.GET.get("date_to"))

    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(external_batch_ref__icontains=q)
            | Q(connector__number__icontains=q)
            | Q(connector__name__icontains=q)
        )
    if connector_id.isdigit():
        qs = qs.filter(connector_id=int(connector_id))
    if sync_domain in dict(AssetGlSyncBatch.SYNC_DOMAIN_CHOICES):
        qs = qs.filter(sync_domain=sync_domain)
    if status in dict(AssetGlSyncBatch.STATUS_CHOICES):
        qs = qs.filter(status=status)
    if reconciliation_status in dict(AssetGlSyncBatch.RECONCILIATION_STATUS_CHOICES):
        qs = qs.filter(reconciliation_status=reconciliation_status)
    if date_from is not None:
        qs = qs.filter(batch_date__gte=date_from)
    if date_to is not None:
        qs = qs.filter(batch_date__lte=date_to)

    paginator = Paginator(qs.order_by("-batch_date", "-number"), 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    connectors = assets_scope(AssetIntegrationConnector.objects.all(), request).order_by(
        "number"
    )

    context = {
        "batches": page_obj,
        "paginator": paginator,
        "page_obj": page_obj,
        "is_paginated": page_obj.has_other_pages(),
        "total_count": kpis["total"] or 0,
        "posted_count": kpis["posted"] or 0,
        "variance_count": kpis["variance"] or 0,
        "draft_count": kpis["draft"] or 0,
        "connectors": connectors,
        "domain_choices": AssetGlSyncBatch.SYNC_DOMAIN_CHOICES,
        "status_choices": AssetGlSyncBatch.STATUS_CHOICES,
        "reconciliation_choices": AssetGlSyncBatch.RECONCILIATION_STATUS_CHOICES,
        "search_query": q,
    }
    return render(
        request,
        "assets/integrationapihub/asset_gl_sync_batch/list.html",
        context,
    )


@login_required
def batch_create(request):
    """Create a new Asset GL Sync & Reconciliation Batch."""
    if request.tenant is None:
        messages.error(
            request,
            "An active tenant workspace is required to create a GL sync batch.",
        )
        return redirect("assets:asset_gl_sync_batch_list")
    if request.method == "POST":
        form = AssetGlSyncBatchForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                batch = form.save(commit=False)
                batch.tenant = request.tenant
                batch.save()
                write_audit_log(
                    request.user,
                    batch,
                    "create",
                    changes={
                        "number": batch.number,
                        "sync_domain": batch.sync_domain,
                        "source_amount": str(batch.source_amount),
                    },
                    tenant=request.tenant,
                )
            messages.success(
                request, f"GL sync batch {batch.number} created successfully."
            )
            return redirect("assets:asset_gl_sync_batch_detail", pk=batch.pk)
    else:
        initial = {}
        connector_id = (request.GET.get("connector") or "").strip()
        if connector_id.isdigit():
            initial["connector"] = int(connector_id)
        form = AssetGlSyncBatchForm(tenant=request.tenant, initial=initial)

    return render(
        request,
        "assets/integrationapihub/asset_gl_sync_batch/form.html",
        {
            "form": form,
            "batch": None,
            "is_edit": False,
            "title": "New GL Sync Batch",
        },
    )


@login_required
def batch_detail(request, pk):
    """Display Asset GL Sync Batch details, GL mapping, and Journal Entry links."""
    batch = assets_object(
        request,
        AssetGlSyncBatch,
        pk,
        select_related=(
            "connector",
            "fiscal_period",
            "gl_account",
            "offset_gl_account",
            "fixed_asset",
            "purchase_order",
            "capitalization",
            "depreciation_schedule",
            "maintenance_request",
            "cost_center",
            "currency",
            "journal_entry",
            "executed_by",
        ),
    )
    return render(
        request,
        "assets/integrationapihub/asset_gl_sync_batch/detail.html",
        {"batch": batch},
    )


@login_required
def batch_edit(request, pk):
    """Edit an existing Asset GL Sync Batch."""
    batch = assets_object(request, AssetGlSyncBatch, pk)
    if batch.journal_entry_id is not None or batch.status == "posted":
        messages.error(
            request,
            f"Cannot edit {batch.number}: it is already posted to the General Ledger.",
        )
        return redirect("assets:asset_gl_sync_batch_detail", pk=batch.pk)
    if request.method == "POST":
        form = AssetGlSyncBatchForm(
            request.POST, instance=batch, tenant=batch.tenant
        )
        if form.is_valid():
            with transaction.atomic():
                batch = form.save()
                write_audit_log(
                    request.user,
                    batch,
                    "update",
                    changes={
                        "number": batch.number,
                        "status": batch.status,
                        "variance_amount": str(batch.variance_amount),
                    },
                    tenant=batch.tenant,
                )
            messages.success(
                request, f"GL sync batch {batch.number} updated successfully."
            )
            return redirect("assets:asset_gl_sync_batch_detail", pk=batch.pk)
    else:
        form = AssetGlSyncBatchForm(instance=batch, tenant=batch.tenant)

    return render(
        request,
        "assets/integrationapihub/asset_gl_sync_batch/form.html",
        {
            "form": form,
            "batch": batch,
            "is_edit": True,
            "title": f"Edit {batch.number} — {batch.get_sync_domain_display()}",
        },
    )


@tenant_admin_required
@require_POST
def batch_delete(request, pk):
    """Delete a draft/unposted Asset GL Sync Batch."""
    batch = assets_object(request, AssetGlSyncBatch, pk)
    if batch.journal_entry_id is not None or batch.status == "posted":
        messages.error(
            request,
            f"Cannot delete {batch.number}: it is already posted to the General Ledger.",
        )
        return redirect("assets:asset_gl_sync_batch_detail", pk=batch.pk)

    label = str(batch)
    with transaction.atomic():
        write_audit_log(
            request.user,
            batch,
            "delete",
            changes={"number": batch.number, "sync_domain": batch.sync_domain},
            tenant=batch.tenant,
        )
        batch.delete()
    messages.success(request, f"GL sync batch {label} deleted.")
    return redirect("assets:asset_gl_sync_batch_list")


@tenant_admin_required
@require_POST
def execute_reconcile_batch(request, pk):
    """Reconcile GL batch variance and post a balanced Journal Entry when eligible (admin only)."""
    with transaction.atomic():
        batch = get_object_or_404(
            AssetGlSyncBatch.objects.select_for_update(),
            pk=pk,
            tenant=request.tenant,
        )

        if batch.journal_entry_id is not None or batch.status == "posted":
            messages.info(
                request,
                f"Batch {batch.number} is already posted to the General Ledger; no changes made.",
            )
            return redirect("assets:asset_gl_sync_batch_detail", pk=batch.pk)

        if batch.status == "failed":
            messages.error(
                request,
                f"Cannot execute {batch.number}: batch status is Failed.",
            )
            return redirect("assets:asset_gl_sync_batch_detail", pk=batch.pk)

        connector = batch.connector
        fiscal_period = batch.fiscal_period
        gl_account = batch.gl_account
        offset_gl_account = batch.offset_gl_account
        cost_center = batch.cost_center
        currency = batch.currency

        for fk_label, rel in (
            ("Connector", connector),
            ("Fiscal period", fiscal_period),
            ("Primary GL account", gl_account),
            ("Offset GL account", offset_gl_account),
            ("Cost center", cost_center),
        ):
            if rel is not None and getattr(rel, "tenant_id", None) != batch.tenant_id:
                messages.error(
                    request,
                    f"Cannot execute {batch.number}: {fk_label} belongs to another workspace.",
                )
                return redirect("assets:asset_gl_sync_batch_detail", pk=batch.pk)

        if fiscal_period is not None and not fiscal_period.is_open:
            messages.error(
                request,
                f"Cannot execute {batch.number}: fiscal period {fiscal_period.name} is {fiscal_period.status} (must be open).",
            )
            return redirect("assets:asset_gl_sync_batch_detail", pk=batch.pk)

        src_amt = batch.source_amount or Decimal("0.00")
        tgt_amt = batch.target_gl_amount or Decimal("0.00")
        variance = src_amt - tgt_amt
        now = timezone.now()

        can_post_je = (
            variance == Decimal("0.00")
            and batch.sync_domain in AssetGlSyncBatch.GL_POSTING_DOMAINS
            and gl_account is not None
            and offset_gl_account is not None
            and gl_account.pk != offset_gl_account.pk
            and src_amt > Decimal("0.00")
        )

        je = None
        if can_post_je:
            je = JournalEntry.objects.create(
                tenant=batch.tenant,
                entry_type="recurring",
                entry_date=batch.batch_date,
                fiscal_period=fiscal_period,
                description=f"Asset GL Sync {batch.number} ({batch.get_sync_domain_display()})"[
                    :500
                ],
                reference=(batch.external_batch_ref or batch.number)[:100],
                status="posted",
                created_by=request.user,
                approved_by=request.user,
                posted_at=now,
            )
            debit_line = JournalLine(
                entry=je,
                gl_account=gl_account,
                debit=src_amt,
                credit=Decimal("0.00"),
                description=f"{batch.number} Debit — {batch.get_sync_domain_display()}"[
                    :255
                ],
                org_unit=cost_center,
                currency=currency,
            )
            debit_line.full_clean()
            debit_line.save()

            credit_line = JournalLine(
                entry=je,
                gl_account=offset_gl_account,
                debit=Decimal("0.00"),
                credit=src_amt,
                description=f"{batch.number} Offset Credit — {batch.get_sync_domain_display()}"[
                    :255
                ],
                org_unit=cost_center,
                currency=currency,
            )
            credit_line.full_clean()
            credit_line.save()

            batch.journal_entry = je
            batch.status = "posted"
        else:
            batch.status = "reconciled" if variance == Decimal("0.00") else "simulated"

        batch.variance_amount = variance
        batch.reconciliation_status = (
            "reconciled" if variance == Decimal("0.00") else "variance_flagged"
        )
        batch.records_processed = max(batch.records_processed or 0, 1)
        batch.records_succeeded = (
            batch.records_processed
            if variance == Decimal("0.00")
            else max(batch.records_processed - 1, 0)
        )
        batch.records_failed = 0 if variance == Decimal("0.00") else 1
        batch.synced_at = now
        batch.executed_by = request.user
        batch.save(
            update_fields=[
                "journal_entry",
                "status",
                "variance_amount",
                "reconciliation_status",
                "records_processed",
                "records_succeeded",
                "records_failed",
                "synced_at",
                "executed_by",
                "updated_at",
            ]
        )
        write_audit_log(
            request.user,
            batch,
            "reconcile",
            changes={
                "status": batch.status,
                "reconciliation_status": batch.reconciliation_status,
                "variance_amount": str(variance),
                "journal_entry": je.number if je else None,
            },
            tenant=batch.tenant,
        )

    if can_post_je and je is not None:
        messages.success(
            request,
            f"Batch {batch.number} reconciled and posted balanced Journal Entry {je.number}.",
        )
    else:
        messages.success(
            request,
            f"Batch {batch.number} reconciled ({batch.get_reconciliation_status_display()}, variance {variance}).",
        )
    return redirect("assets:asset_gl_sync_batch_detail", pk=batch.pk)
