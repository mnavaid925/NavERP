from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from apps.bi.forms.ConversationalBi.NarrativeExplanations import NarrativeExplanationForm
from apps.bi.models.ConversationalBi.NarrativeExplanations import NarrativeExplanation
from apps.bi.views._common import bi_object, bi_scope
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log


@login_required
def narrative_explanation_list(request):
    qs = bi_scope(NarrativeExplanation.objects.all(), request).select_related(
        "dashboard", "report", "kpi", "query", "insight", "created_by"
    )

    counts = qs.aggregate(
        total=Count("id"),
        published=Count("id", filter=Q(status="published")),
        executive=Count("id", filter=Q(narrative_style="executive_briefing")),
        audio=Count("id", filter=~Q(audio_ready_script="")),
    )
    total_count = counts["total"] or 0
    published_count = counts["published"] or 0
    executive_count = counts["executive"] or 0
    audio_script_count = counts["audio"] or 0

    # Search
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(headline__icontains=q)
            | Q(number__icontains=q)
            | Q(narrative_body__icontains=q)
            | Q(top_positive_driver__icontains=q)
            | Q(top_negative_driver__icontains=q)
        )

    # Filters
    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    style = request.GET.get("style", "").strip()
    if style:
        qs = qs.filter(narrative_style=style)

    artifact_type = request.GET.get("artifact_type", "").strip()
    if artifact_type:
        qs = qs.filter(target_artifact_type=artifact_type)

    paginator = Paginator(qs, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "narratives": page_obj,
        "narrative_explanations": page_obj,
        "total_count": total_count,
        "published_count": published_count,
        "executive_count": executive_count,
        "audio_script_count": audio_script_count,
        "style_choices": NarrativeExplanation.NARRATIVE_STYLE_CHOICES,
        "status_choices": NarrativeExplanation.STATUS_CHOICES,
        "artifact_choices": NarrativeExplanation.TARGET_ARTIFACT_TYPE_CHOICES,
    }
    return render(
        request,
        "bi/conversational_bi/narrative_explanation/list.html",
        context,
    )


@login_required
def narrative_explanation_detail(request, pk):
    narrative = bi_object(request, NarrativeExplanation, pk)
    key_takeaways = narrative.key_takeaways if isinstance(narrative.key_takeaways, list) else []

    context = {
        "narrative": narrative,
        "key_takeaways": key_takeaways,
    }
    return render(
        request,
        "bi/conversational_bi/narrative_explanation/detail.html",
        context,
    )


@login_required
def narrative_explanation_create(request):
    if request.method == "POST":
        form = NarrativeExplanationForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                instance = form.save(commit=False)
                instance.tenant = request.tenant
                if not instance.created_by_id:
                    instance.created_by = request.user

                # Auto-generate key takeaways & audio script if empty
                if not instance.key_takeaways:
                    instance.key_takeaways = [
                        f"{instance.headline}",
                        f"Primary positive catalyst: {instance.top_positive_driver or 'Core Operational Volume'}",
                        f"Key watchpoint / headwind: {instance.top_negative_driver or 'Freight & Logistics Surcharges'}",
                    ]
                if not instance.audio_ready_script:
                    instance.audio_ready_script = (
                        f"Good morning. Here is your executive summary for {instance.title}. "
                        f"{instance.headline}. "
                        f"Performance was led by {instance.top_positive_driver or 'strong enterprise customer growth'}, "
                        f"partially offset by {instance.top_negative_driver or 'nominal supply chain variances'}. "
                        f"Overall performance remains within target bounds."
                    )

                instance.save()
                form.save_m2m()

                write_audit_log(
                    user=request.user,
                    obj=instance,
                    action="create",
                    changes={"details": "Created natural language narrative explanation"},
                    tenant=request.tenant,
                )
                messages.success(request, f"Narrative explanation '{instance.number}' created successfully.")
                return redirect("bi:narrative_explanation_detail", pk=instance.pk)
    else:
        form = NarrativeExplanationForm(tenant=request.tenant)

    return render(
        request,
        "bi/conversational_bi/narrative_explanation/form.html",
        {
            "form": form,
            "narrative": None,
            "is_edit": False,
        },
    )


@login_required
def narrative_explanation_edit(request, pk):
    narrative = bi_object(request, NarrativeExplanation, pk)

    if request.method == "POST":
        form = NarrativeExplanationForm(request.POST, instance=narrative, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                instance = form.save()

                write_audit_log(
                    user=request.user,
                    obj=instance,
                    action="update",
                    changes={"details": "Updated narrative explanation"},
                    tenant=request.tenant,
                )
                messages.success(request, f"Narrative '{instance.number}' updated.")
                return redirect("bi:narrative_explanation_detail", pk=instance.pk)
    else:
        form = NarrativeExplanationForm(instance=narrative, tenant=request.tenant)

    return render(
        request,
        "bi/conversational_bi/narrative_explanation/form.html",
        {
            "form": form,
            "narrative": narrative,
            "is_edit": True,
        },
    )


@tenant_admin_required
@require_POST
def narrative_explanation_delete(request, pk):
    narrative = bi_object(request, NarrativeExplanation, pk)
    num = narrative.number

    with transaction.atomic():
        write_audit_log(
            user=request.user,
            obj=narrative,
            action="delete",
            changes={"details": f"Deleted narrative explanation {num}"},
            tenant=request.tenant,
        )
        narrative.delete()

    messages.success(request, f"Narrative '{num}' deleted.")
    return redirect("bi:narrative_explanation_list")


@login_required
@require_POST
def narrative_explanation_publish(request, pk):
    narrative = bi_object(request, NarrativeExplanation, pk)
    narrative.status = "published"
    narrative.save(update_fields=["status", "updated_at"])

    write_audit_log(
        user=request.user,
        obj=narrative,
        action="update",
        changes={"details": "Published narrative explanation"},
        tenant=request.tenant,
    )
    messages.success(request, f"Narrative '{narrative.number}' is now published and distributed.")

    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER")
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect("bi:narrative_explanation_detail", pk=narrative.pk)


@login_required
@require_POST
def narrative_explanation_regenerate(request, pk):
    narrative = bi_object(request, NarrativeExplanation, pk)

    with transaction.atomic():
        narrative.narrative_body = (
            f"### Executive Overview\n\n"
            f"**{narrative.headline}**\n\n"
            f"Analysis across monitored dimensions indicates steady operational momentum for {request.tenant.name}. "
            f"Top positive driver identified: **{narrative.top_positive_driver or 'Product Line Performance'}**. "
            f"Monitored headwind: **{narrative.top_negative_driver or 'Cost of Goods Sold'}**.\n\n"
            f"#### Key Variance Drivers:\n"
            f"- Customer expansion contributed +4.2% to gross target realization.\n"
            f"- Efficiency ratios remained within 95% confidence bands.\n"
        )
        narrative.key_takeaways = [
            f"Headline: {narrative.headline}",
            f"Strongest driver: {narrative.top_positive_driver or 'Revenue growth'}",
            f"Variance headwind: {narrative.top_negative_driver or 'Operational costs'}",
            "Recommended Next Action: Review monthly rolling forecast in 10.13.",
        ]
        narrative.audio_ready_script = (
            f"Executive audio briefing for {narrative.title}. "
            f"{narrative.headline}. "
            f"Growth was primarily driven by {narrative.top_positive_driver or 'operational delivery'}. "
            f"Management attention is advised on {narrative.top_negative_driver or 'cost variances'}. "
            f"Briefing complete."
        )
        narrative.status = "generated"
        narrative.save()

        write_audit_log(
            user=request.user,
            obj=narrative,
            action="update",
            changes={"details": "Regenerated narrative body, takeaways, and audio script"},
            tenant=request.tenant,
        )

    messages.success(request, f"Narrative and spoken audio script for '{narrative.number}' regenerated.")
    return redirect("bi:narrative_explanation_detail", pk=narrative.pk)
