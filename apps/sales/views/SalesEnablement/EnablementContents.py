"""Sales 8.9 — Views for `EnablementContent`."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.utils import write_audit_log
from apps.sales.forms.SalesEnablement.EnablementContents import EnablementContentForm
from apps.sales.models.CompetitiveIntelligence.CompetitiveIntelligence import CompetitorProfile
from apps.sales.models.SalesEnablement.EnablementContents import (
    CONTENT_TYPE_CHOICES,
    TARGET_PERSONA_CHOICES,
    TARGET_STAGE_CHOICES,
    EnablementContent,
)
from apps.sales.views._helpers import is_tenant_admin



@login_required
def enablement_content_list(request):
    qs = (
        EnablementContent.objects.filter(tenant=request.tenant)
        .select_related("competitor__party", "document", "pipeline_stage", "author")
        .order_by("-updated_at")
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(description__icontains=q)
            | Q(tags__icontains=q)
            | Q(number__icontains=q)
        )

    content_type = request.GET.get("content_type", "").strip()
    if content_type:
        qs = qs.filter(content_type=content_type)

    target_stage = request.GET.get("target_stage", "").strip()
    if target_stage:
        qs = qs.filter(target_stage=target_stage)

    target_persona = request.GET.get("target_persona", "").strip()
    if target_persona:
        qs = qs.filter(target_persona=target_persona)

    competitor_id = request.GET.get("competitor", "").strip()
    if competitor_id.isdecimal():
        qs = qs.filter(competitor_id=int(competitor_id))

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    competitors = CompetitorProfile.objects.filter(tenant=request.tenant, is_active=True).select_related("party")

    context = {
        "contents": page_obj,
        "content_type_choices": CONTENT_TYPE_CHOICES,
        "stage_choices": TARGET_STAGE_CHOICES,
        "persona_choices": TARGET_PERSONA_CHOICES,
        "competitors": competitors,
        "q": q,
        "content_type": content_type,
        "target_stage": target_stage,
        "target_persona": target_persona,
        "competitor_id": competitor_id,
    }
    return render(request, "sales/salesenablement/enablementcontent/list.html", context)



@login_required
def enablement_content_detail(request, pk):
    content = get_object_or_404(
        EnablementContent.objects.filter(tenant=request.tenant).select_related(
            "competitor__party", "document", "pipeline_stage", "author"
        ),
        pk=pk,
    )
    content.record_view()
    context = {"content": content}
    return render(request, "sales/salesenablement/enablementcontent/detail.html", context)


@login_required
def enablement_content_create(request):
    if request.method == "POST":
        form = EnablementContentForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                obj = form.save(commit=False)
                obj.tenant = request.tenant
                if not obj.author_id:
                    obj.author = request.user
                obj.save()
                write_audit_log(
                    request.user,
                    obj,
                    "create",
                    changes={"title": obj.title, "number": obj.number},
                )
            messages.success(request, f"Enablement content '{obj.title}' created.")
            return redirect("sales:enablement_content_detail", pk=obj.pk)
    else:
        initial = {}
        comp_id = request.GET.get("competitor")
        if comp_id and comp_id.isdecimal():
            initial["competitor"] = int(comp_id)
        form = EnablementContentForm(initial=initial, tenant=request.tenant)

    context = {"form": form, "content": None, "is_edit": False}
    return render(request, "sales/salesenablement/enablementcontent/form.html", context)


@login_required
def enablement_content_edit(request, pk):
    obj = get_object_or_404(EnablementContent.objects.filter(tenant=request.tenant), pk=pk)
    if request.method == "POST":
        form = EnablementContentForm(request.POST, instance=obj, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                form.save()
                write_audit_log(
                    request.user,
                    obj,
                    "update",
                    changes={"title": obj.title, "number": obj.number},
                )
            messages.success(request, f"Enablement content '{obj.title}' updated.")
            return redirect("sales:enablement_content_detail", pk=obj.pk)
    else:
        form = EnablementContentForm(instance=obj, tenant=request.tenant)

    context = {"form": form, "content": obj, "is_edit": True}
    return render(request, "sales/salesenablement/enablementcontent/form.html", context)


@login_required
@require_POST
def enablement_content_delete(request, pk):
    obj = get_object_or_404(EnablementContent.objects.filter(tenant=request.tenant), pk=pk)
    if not is_tenant_admin(request.user) and obj.author_id != request.user.pk:
        messages.error(request, "Only the author or a tenant administrator may delete this enablement content.")
        return redirect("sales:enablement_content_detail", pk=obj.pk)
    title = obj.title
    number = obj.number
    with transaction.atomic():
        write_audit_log(
            request.user,
            obj,
            "delete",
            changes={"title": title, "number": number},
        )
        obj.delete()
    messages.success(request, f"Enablement content '{title}' deleted.")
    return redirect("sales:enablement_content_list")


@login_required
@require_POST
def enablement_content_share(request, pk):
    obj = get_object_or_404(EnablementContent.objects.filter(tenant=request.tenant), pk=pk)
    if not obj.is_active:
        messages.error(request, f"Cannot share '{obj.title}' because this content asset is inactive.")
        return redirect("sales:enablement_content_detail", pk=obj.pk)
    if obj.expires_on and obj.expires_on < timezone.now().date():
        messages.error(request, f"Cannot share '{obj.title}' because this content asset has expired.")
        return redirect("sales:enablement_content_detail", pk=obj.pk)
    with transaction.atomic():
        obj.record_share()
    messages.info(request, f"Link copied / share recorded for '{obj.title}'.")
    return redirect("sales:enablement_content_detail", pk=obj.pk)


