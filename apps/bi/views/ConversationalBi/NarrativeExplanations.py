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
        audio_script=Count("id", filter=~Q(audio_ready_script="")),
    )
    total_count = counts["total"] or 0
    published_count = counts["published"] or 0
    executive_count = counts["executive"] or 0
    audio_script_count = counts["audio_script"] or 0

    # Search
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(number__icontains=q)
            | Q(headline__icontains=q)
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

    artifact = request.GET.get("artifact", "").strip()
    if artifact:
        qs = qs.filter(target_artifact_type=artifact)

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
    narrative = bi_object(NarrativeExplanation, request, pk)
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

                # Synthesize key takeaways and audio script if empty
                if not instance.key_takeaways:
                    takeaways = [
                        instance.headline or f"Observed key movements in {instance.title}.",
                    ]
                    if instance.top_positive_driver:
                        takeaways.append(f"Positive momentum: {instance.top_positive_driver}.")
                    if instance.top_negative_driver:
                        takeaways.append(f"Risk factor: {instance.top_negative_driver}.")
                    instance.key_takeaways = takeaways

                if not instance.audio_ready_script:
                    pos = f" Driving gains: {instance.top_positive_driver}." if instance.top_positive_driver else ""
                    neg = f" Offsetting drag: {instance.top_negative_driver}." if instance.top_negative_driver else ""
                    instance.audio_ready_script = (
                        f"Executive briefing for {instance.title}. {instance.headline}.{pos}{neg}"
                    )

                instance.save()
                form.save_m2m()

                write_audit_log(
                    user=request.user,
                    obj=instance,
                    action="create",
                    changes={"details": "Created natural language generated narrative explanation"},
                    tenant=request.tenant,
                )
                messages.success(request, f"Narrative explanation '{instance.number}' generated successfully.")
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
    narrative = bi_object(NarrativeExplanation, request, pk)

    if request.method == "POST":
        form = NarrativeExplanationForm(request.POST, instance=narrative, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                instance = form.save()

                write_audit_log(
                    user=request.user,
                    obj=instance,
                    action="update",
                    changes={"details": "Updated narrative explanation content"},
                    tenant=request.tenant,
                )
                messages.success(request, f"Narrative explanation '{instance.number}' updated.")
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
    narrative = bi_object(NarrativeExplanation, request, pk)
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

    messages.success(request, f"Narrative '{num}' has been deleted.")
    return redirect("bi:narrative_explanation_list")


@login_required
@require_POST
def narrative_explanation_publish(request, pk):
    narrative = bi_object(NarrativeExplanation, request, pk)

    with transaction.atomic():
        narrative.status = "published"
        narrative.save(update_fields=["status", "updated_at"])

        write_audit_log(
            user=request.user,
            obj=narrative,
            action="publish",
            changes={"details": f"Published narrative {narrative.number}"},
            tenant=request.tenant,
        )
    messages.success(request, f"Narrative '{narrative.number}' is now published.")

    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER")
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect("bi:narrative_explanation_detail", pk=narrative.pk)


@login_required
@require_POST
def narrative_explanation_regenerate(request, pk):
    narrative = bi_object(NarrativeExplanation, request, pk)

    with transaction.atomic():
        takeaways = [
            narrative.headline or f"Updated executive briefing for {narrative.title}.",
        ]
        if narrative.top_positive_driver:
            takeaways.append(f"Positive momentum: {narrative.top_positive_driver}.")
        if narrative.top_negative_driver:
            takeaways.append(f"Risk factor: {narrative.top_negative_driver}.")
        narrative.key_takeaways = takeaways

        pos = f" Driving gains: {narrative.top_positive_driver}." if narrative.top_positive_driver else ""
        neg = f" Offsetting drag: {narrative.top_negative_driver}." if narrative.top_negative_driver else ""
        narrative.audio_ready_script = (
            f"Executive audio briefing for {narrative.title}. {narrative.headline}.{pos}{neg}"
        )
        narrative.status = "generated"
        narrative.save(update_fields=["key_takeaways", "audio_ready_script", "status", "updated_at"])

        write_audit_log(
            user=request.user,
            obj=narrative,
            action="regen",
            changes={"details": f"Regenerated NLG takeaways and audio script for {narrative.number}"},
            tenant=request.tenant,
        )

    messages.success(request, f"Narrative '{narrative.number}' refreshed with updated takeaways.")
    return redirect("bi:narrative_explanation_detail", pk=narrative.pk)
