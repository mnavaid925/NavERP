"""CRM 1.11 Customer Success & Retention — HealthScores views (split from apps/crm/views.py)."""
from apps.crm.views._common import *  # noqa: F401,F403
from apps.crm.models import (
    HealthScore,
    HealthScoreConfig,
    HealthScoreHistory,
    compute_health_score,
)
from apps.crm.forms import (
    HealthScoreConfigForm,
    HealthScoreForm,
)


# ------------------------------------------------------------ 1.11 Health scores
@login_required
def healthscore_list(request):
    return crud_list(
        request,
        HealthScore.objects.filter(tenant=request.tenant).select_related("account"),
        "crm/success/healthscore/list.html",
        search_fields=["number", "account__name"],
        filters=[("tier", "tier", False)],
        extra_context={"tier_choices": HealthScore.TIER_CHOICES},
    )


@login_required
def healthscore_create(request):
    return crud_create(request, form_class=HealthScoreForm, template="crm/success/healthscore/form.html",
                       success_url="crm:healthscore_list")


@login_required
def healthscore_detail(request, pk):
    obj = get_object_or_404(HealthScore.objects.select_related("account"), pk=pk, tenant=request.tenant)
    history = list(HealthScoreHistory.objects.filter(tenant=request.tenant, account=obj.account)
                   .order_by("-computed_at")[:12])  # recent trend points (newest first)
    return render(request, "crm/success/healthscore/detail.html", {"obj": obj, "history": history})


@login_required
def healthscore_edit(request, pk):
    return crud_edit(request, model=HealthScore, pk=pk, form_class=HealthScoreForm,
                     template="crm/success/healthscore/form.html", success_url="crm:healthscore_list")


@login_required
@require_POST
def healthscore_delete(request, pk):
    return crud_delete(request, model=HealthScore, pk=pk, success_url="crm:healthscore_list")


@login_required
@require_POST
def recompute_health_score(request, pk):
    obj = get_object_or_404(HealthScore.objects.select_related("account"), pk=pk, tenant=request.tenant)
    compute_health_score(obj.account, request.tenant)
    write_audit_log(request.user, obj, "update")
    messages.success(request, "Health score recomputed.")
    return redirect("crm:healthscore_detail", pk=obj.pk)


@tenant_admin_required  # bulk recompute is a privileged, tenant-wide operation
@require_POST
def recompute_all_health_scores(request):
    account_ids = list(HealthScore.objects.filter(tenant=request.tenant).values_list("account_id", flat=True))
    config, _ = HealthScoreConfig.objects.get_or_create(tenant=request.tenant)  # fetch weights once for the batch
    done, failed = 0, 0
    for party in Party.objects.filter(tenant=request.tenant, pk__in=account_ids):
        try:
            compute_health_score(party, request.tenant, config=config)
            done += 1
        except Exception:  # noqa: BLE001 — isolate one bad account so the batch still completes
            failed += 1
    write_audit_log(request.user, None, "update", tenant=request.tenant)
    if failed:
        messages.warning(request, f"Recomputed {done} health score(s); {failed} failed.")
    else:
        messages.success(request, f"Recomputed {done} health score(s).")
    return redirect("crm:healthscore_list")


@tenant_admin_required  # health-scoring weights are a tenant-wide privileged setting
def health_config_edit(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before configuring health scoring.")
        return redirect("dashboard:home")
    config, _ = HealthScoreConfig.objects.get_or_create(tenant=request.tenant)
    if request.method == "POST":
        form = HealthScoreConfigForm(request.POST, instance=config, tenant=request.tenant)
        if form.is_valid():
            form.save()
            write_audit_log(request.user, config, "update")
            messages.success(request, "Health-scoring weights saved.")
            return redirect("crm:healthscore_list")
    else:
        form = HealthScoreConfigForm(instance=config, tenant=request.tenant)
    return render(request, "crm/success/health_config/form.html", {"form": form, "config": config})
