"""tenants — Onboarding views (split from apps/tenants/views.py)."""
from apps.tenants.views._common import *  # noqa: F401,F403
from apps.tenants.models import (
    BrandingSetting,
    Subscription,
)
from apps.tenants.forms import (
    OnboardingForm,
)


# =============================================================== Onboarding
@tenant_admin_required
def onboarding(request):
    if request.tenant is None:
        messages.info(request, "Onboarding applies to a tenant workspace. Sign in as a tenant admin.")
        return redirect("dashboard:home")
    form = OnboardingForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        plan = form.cleaned_data["plan"]
        sub = Subscription.objects.filter(tenant=request.tenant).first() or Subscription(tenant=request.tenant)
        sub.plan = plan
        sub.seats = form.cleaned_data["seats"]
        sub.status = "trialing"
        if not sub.started_on:
            sub.started_on = timezone.localdate()
        sub.renews_on = timezone.localdate() + timezone.timedelta(days=14)
        sub.save()

        branding, _ = BrandingSetting.objects.get_or_create(tenant=request.tenant)
        branding.primary_color = form.cleaned_data["primary_color"]
        branding.accent_color = form.cleaned_data["accent_color"]
        if form.cleaned_data.get("logo"):
            branding.logo = form.cleaned_data["logo"]
        branding.save()

        request.tenant.plan = plan
        request.tenant.save(update_fields=["plan"])
        messages.success(request, "Workspace configured. Welcome aboard!")
        return redirect("dashboard:home")
    return render(request, "tenants/onboarding_wizard.html", {"form": form})
