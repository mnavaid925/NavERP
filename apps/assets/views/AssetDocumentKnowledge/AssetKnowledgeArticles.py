"""Function-based views for Asset Knowledge Base, Lessons Learned & Failure RCA (11.16)."""

from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, F, Q, Sum
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.assets.forms.AssetDocumentKnowledge.AssetKnowledgeArticles import (
    AssetKnowledgeArticleForm,
)
from apps.assets.models.AssetDocumentKnowledge.AssetKnowledgeArticles import (
    AssetKnowledgeArticle,
)
from apps.assets.models.AssetReliability.AssetFailureModes import AssetFailureMode
from apps.assets.views._common import assets_object, assets_scope
from apps.assets.views.AssetDocumentKnowledge._helpers import (
    PAGE_SIZE,
    apply_choice_filter,
    apply_fk_filter,
    csv_export_response,
    is_asset_document_readable,
    is_tenant_admin_user,
    serve_protected_attachment,
)
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.scm.models.AssetManagement.Assets import Asset


_KB_LIST_SELECT_RELATED = (
    "operational_asset",
    "asset_category",
    "failure_mode",
)
_KB_EXPORT_SELECT_RELATED = (
    "operational_asset",
    "failure_mode",
)


def _filter_article_queryset(
    request, base_qs, select_related=_KB_LIST_SELECT_RELATED
):
    """Apply search and dropdown GET filters to an AssetKnowledgeArticle queryset."""
    qs = base_qs.select_related(*select_related) if select_related else base_qs
    search_query = request.GET.get("q", "").strip()
    if search_query:
        qs = qs.filter(
            Q(number__icontains=search_query)
            | Q(title__icontains=search_query)
            | Q(symptom_problem__icontains=search_query)
            | Q(root_cause_summary__icontains=search_query)
            | Q(preventive_lessons__icontains=search_query)
            | Q(tags__icontains=search_query)
        )
    qs = apply_choice_filter(
        qs,
        request,
        "article_type",
        allowed_values={val for val, _ in AssetKnowledgeArticle.ARTICLE_TYPE_CHOICES},
    )
    qs = apply_choice_filter(
        qs,
        request,
        "rca_methodology",
        allowed_values={val for val, _ in AssetKnowledgeArticle.RCA_METHODOLOGY_CHOICES},
    )
    qs = apply_choice_filter(
        qs,
        request,
        "severity",
        allowed_values={val for val, _ in AssetKnowledgeArticle.SEVERITY_CHOICES},
    )
    qs = apply_choice_filter(
        qs,
        request,
        "status",
        allowed_values={val for val, _ in AssetKnowledgeArticle.STATUS_CHOICES},
    )
    qs = apply_fk_filter(qs, request, "operational_asset")
    qs = apply_fk_filter(qs, request, "failure_mode")
    return qs


@login_required
def asset_knowledge_article_list(request):
    """Knowledge base, lessons learned, and RCA catalog list view."""
    base_qs = assets_scope(AssetKnowledgeArticle.objects.all(), request)
    filtered_qs = _filter_article_queryset(request, base_qs).defer(
        "symptom_problem",
        "root_cause_summary",
        "five_whys",
        "contributing_factors",
        "remedy_corrective_action",
        "preventive_lessons",
    )
    paginator = Paginator(filtered_qs, PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page"))

    kpis = base_qs.aggregate(
        total_count=Count("id"),
        published_count=Count("id", filter=Q(status="published")),
        critical_high_count=Count(
            "id", filter=Q(severity__in=["high", "critical"])
        ),
        total_downtime_hours=Sum("downtime_hours_impacted"),
    )

    context = {
        "articles": page_obj,
        "paginator": paginator,
        "page_obj": page_obj,
        "is_paginated": page_obj.has_other_pages(),
        "total_count": kpis["total_count"] or 0,
        "published_count": kpis["published_count"] or 0,
        "critical_high_count": kpis["critical_high_count"] or 0,
        "total_downtime_hours": kpis["total_downtime_hours"] or Decimal("0.00"),
        "article_type_choices": AssetKnowledgeArticle.ARTICLE_TYPE_CHOICES,
        "rca_choices": AssetKnowledgeArticle.RCA_METHODOLOGY_CHOICES,
        "severity_choices": AssetKnowledgeArticle.SEVERITY_CHOICES,
        "status_choices": AssetKnowledgeArticle.STATUS_CHOICES,
        "assets_list": Asset.objects.filter(tenant=request.tenant).order_by("name"),
        "failure_modes": AssetFailureMode.objects.filter(
            tenant=request.tenant
        ).order_by("number"),
        "search_query": request.GET.get("q", "").strip(),
    }
    return render(
        request,
        "assets/assetdocumentknowledge/asset_knowledge_article/list.html",
        context,
    )


@login_required
def asset_knowledge_article_export_csv(request):
    """Export filtered tenant Knowledge Articles & RCAs as a hardened CSV download."""
    base_qs = assets_scope(AssetKnowledgeArticle.objects.all(), request)
    filtered_qs = (
        _filter_article_queryset(
            request, base_qs, select_related=_KB_EXPORT_SELECT_RELATED
        )
        .only(
            "id",
            "number",
            "title",
            "article_type",
            "rca_methodology",
            "severity",
            "status",
            "downtime_hours_impacted",
            "recurrence_count",
            "helpful_votes",
            "tags",
            "operational_asset",
            "failure_mode",
        )[:10000]
        .iterator(chunk_size=1000)
    )
    headers = [
        "Article #",
        "Title",
        "Type",
        "RCA Methodology",
        "Severity",
        "Status",
        "Asset",
        "Failure Mode",
        "Downtime Hrs",
        "Recurrences",
        "Helpful Votes",
        "Tags",
    ]
    rows = (
        [
            art.number,
            art.title,
            art.get_article_type_display(),
            art.get_rca_methodology_display(),
            art.get_severity_display(),
            art.get_status_display(),
            str(art.operational_asset) if art.operational_asset else "",
            str(art.failure_mode) if art.failure_mode else "",
            str(art.downtime_hours_impacted),
            art.recurrence_count,
            art.helpful_votes,
            art.tags,
        ]
        for art in filtered_qs
    )
    return csv_export_response(
        filename="asset_knowledge_articles_11_16.csv",
        headers=headers,
        rows=rows,
    )


@login_required
def asset_knowledge_article_detail(request, pk):
    """Knowledge article and structured 5-Why / Fishbone 6M RCA detail view."""
    article = assets_object(
        request,
        AssetKnowledgeArticle,
        pk,
        select_related=(
            "org_unit",
            "operational_asset",
            "fixed_asset",
            "asset_category",
            "asset_model",
            "failure_mode",
            "maintenance_request",
            "maintenance_log",
            "incident_report__asset",
            "compliance_incident",
            "related_document",
            "recommended_procedure",
            "author",
            "reviewed_by",
        ),
    )
    AssetKnowledgeArticle.objects.filter(
        tenant=request.tenant, pk=article.pk
    ).update(view_count=F("view_count") + 1)
    article.view_count += 1

    is_admin = is_tenant_admin_user(request.user)
    context = {
        "article": article,
        "can_view_related_document": is_asset_document_readable(
            article.related_document, request.user
        ),
        "can_edit": article.status in AssetKnowledgeArticle.EDITABLE_STATUSES,
        "can_publish": (
            is_admin and article.status in AssetKnowledgeArticle.EDITABLE_STATUSES
        ),
    }
    return render(
        request,
        "assets/assetdocumentknowledge/asset_knowledge_article/detail.html",
        context,
    )


@login_required
def asset_knowledge_article_create(request):
    """Create a new Draft lessons-learned note or failure RCA article."""
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating a knowledge article.")
        return redirect("assets:asset_knowledge_article_list")
    if request.method == "POST":
        form = AssetKnowledgeArticleForm(
            request.POST, request.FILES, tenant=request.tenant, user=request.user
        )
        if form.is_valid():
            article = form.save(commit=False)
            article.tenant = request.tenant
            article.author = request.user
            article.status = "draft"
            article.save()
            write_audit_log(request.user, article, "create", tenant=request.tenant)
            messages.success(request, f"Created knowledge article {article.number}.")
            return redirect(
                "assets:asset_knowledge_article_detail", pk=article.pk
            )
    else:
        form = AssetKnowledgeArticleForm(tenant=request.tenant, user=request.user)

    return render(
        request,
        "assets/assetdocumentknowledge/asset_knowledge_article/form.html",
        {
            "form": form,
            "article": None,
            "is_edit": False,
            "title": "New Knowledge Article / RCA",
        },
    )


@login_required
def asset_knowledge_article_edit(request, pk):
    """Edit an unlocked Draft or Peer Review knowledge article."""
    article = assets_object(request, AssetKnowledgeArticle, pk)
    if article.is_locked:
        messages.warning(
            request,
            f"Article {article.number} is {article.get_status_display()} and cannot be edited.",
        )
        return redirect("assets:asset_knowledge_article_detail", pk=article.pk)

    if request.method == "POST":
        form = AssetKnowledgeArticleForm(
            request.POST,
            request.FILES,
            instance=article,
            tenant=request.tenant,
            user=request.user,
        )
        if form.is_valid():
            updated = form.save()
            write_audit_log(request.user, updated, "update", tenant=request.tenant)
            messages.success(request, f"Updated article {updated.number}.")
            return redirect(
                "assets:asset_knowledge_article_detail", pk=updated.pk
            )
    else:
        form = AssetKnowledgeArticleForm(
            instance=article, tenant=request.tenant, user=request.user
        )

    return render(
        request,
        "assets/assetdocumentknowledge/asset_knowledge_article/form.html",
        {
            "form": form,
            "article": article,
            "is_edit": True,
            "title": f"Edit {article.number}",
        },
    )


@login_required
@require_POST
@tenant_admin_required
def asset_knowledge_article_delete(request, pk):
    """Delete an unlocked Draft / Peer Review knowledge article."""
    article = assets_object(request, AssetKnowledgeArticle, pk)
    if article.is_locked:
        messages.error(
            request,
            f"Cannot delete {article.number} in status {article.get_status_display()}. Retire it instead.",
        )
        return redirect("assets:asset_knowledge_article_detail", pk=article.pk)
    article_number = article.number
    write_audit_log(request.user, article, "delete", tenant=request.tenant)
    article.delete()
    messages.success(request, f"Deleted knowledge article {article_number}.")
    return redirect("assets:asset_knowledge_article_list")


@login_required
def asset_knowledge_article_download(request, pk):
    """Download the RCA evidence attachment safely as an attachment with nosniff."""
    article = assets_object(request, AssetKnowledgeArticle, pk)
    return serve_protected_attachment(
        article,
        file_attr="attachment",
        original_filename_attr="original_filename",
    )


@login_required
@require_POST
def asset_knowledge_article_submit_review(request, pk):
    """Submit a Draft knowledge article for reliability / engineering peer review."""
    with transaction.atomic():
        article = assets_object(
            request,
            AssetKnowledgeArticle,
            pk,
            queryset=AssetKnowledgeArticle.objects.filter(
                tenant=request.tenant
            ).select_for_update(),
        )
        if article.status != "draft":
            messages.warning(
                request,
                f"Article {article.number} must be Draft to submit for peer review.",
            )
            return redirect(
                "assets:asset_knowledge_article_detail", pk=article.pk
            )
        article.status = "peer_review"
        article.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, article, "review", tenant=request.tenant)
    messages.success(request, f"Submitted {article.number} for peer review.")
    return redirect("assets:asset_knowledge_article_detail", pk=article.pk)


@login_required
@require_POST
@tenant_admin_required
def asset_knowledge_article_publish(request, pk):
    """Publish a reviewed lessons-learned / RCA article to the reliability knowledge base."""
    with transaction.atomic():
        article = assets_object(
            request,
            AssetKnowledgeArticle,
            pk,
            queryset=AssetKnowledgeArticle.objects.filter(
                tenant=request.tenant
            ).select_for_update(),
        )
        if article.status not in AssetKnowledgeArticle.EDITABLE_STATUSES:
            messages.warning(
                request,
                f"Article {article.number} cannot be published from {article.get_status_display()}.",
            )
            return redirect(
                "assets:asset_knowledge_article_detail", pk=article.pk
            )
        article.status = "published"
        article.reviewed_by = request.user
        article.published_at = timezone.now()
        article.save(
            update_fields=["status", "reviewed_by", "published_at", "updated_at"]
        )
        write_audit_log(request.user, article, "publish", tenant=request.tenant)
    messages.success(request, f"Published knowledge article {article.number}.")
    return redirect("assets:asset_knowledge_article_detail", pk=article.pk)


@login_required
@require_POST
def asset_knowledge_article_mark_helpful(request, pk):
    """Record a technician helpfulness vote on a knowledge base article."""
    with transaction.atomic():
        article = assets_object(
            request,
            AssetKnowledgeArticle,
            pk,
            queryset=AssetKnowledgeArticle.objects.filter(
                tenant=request.tenant
            ).select_for_update(),
        )
        AssetKnowledgeArticle.objects.filter(
            tenant=request.tenant, pk=article.pk
        ).update(helpful_votes=F("helpful_votes") + 1)
        write_audit_log(request.user, article, "helpful", tenant=request.tenant)
    messages.success(request, f"Marked {article.number} as helpful.")
    return redirect("assets:asset_knowledge_article_detail", pk=article.pk)


@login_required
@require_POST
@tenant_admin_required
def asset_knowledge_article_retire(request, pk):
    """Retire an obsolete troubleshooting note or RCA article."""
    with transaction.atomic():
        article = assets_object(
            request,
            AssetKnowledgeArticle,
            pk,
            queryset=AssetKnowledgeArticle.objects.filter(
                tenant=request.tenant
            ).select_for_update(),
        )
        if article.status == "retired":
            messages.info(request, f"Article {article.number} is already retired.")
            return redirect(
                "assets:asset_knowledge_article_detail", pk=article.pk
            )
        article.status = "retired"
        article.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, article, "retire", tenant=request.tenant)
    messages.success(request, f"Retired knowledge article {article.number}.")
    return redirect("assets:asset_knowledge_article_detail", pk=article.pk)
