"""HRM 3.12 Holiday Management — Publicholiday views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    PublicHoliday,
)
from apps.hrm.forms import (
    PublicHolidayForm,
)


# ============================================================ Public Holidays (3.12)
@login_required
def publicholiday_list(request):
    qs = PublicHoliday.objects.filter(tenant=request.tenant)
    year = request.GET.get("year", "").strip()
    if year.isdigit():
        qs = qs.filter(date__year=int(year))
    years = sorted(PublicHoliday.objects.filter(tenant=request.tenant)
                   .values_list("date__year", flat=True).distinct().order_by(), reverse=True)
    today_year = timezone.localdate().year
    for y in (today_year, today_year + 1):
        if y not in years:
            years.append(y)
    years = sorted(set(years), reverse=True)
    return crud_list(
        request, qs, "hrm/holiday/publicholiday/list.html",
        search_fields=["name"],
        filters=[("is_optional", "is_optional", False), ("category", "category", False)],
        extra_context={"year_choices": years, "category_choices": PublicHoliday.CATEGORY_CHOICES},
    )


@login_required
def publicholiday_create(request):
    return crud_create(request, form_class=PublicHolidayForm,
                       template="hrm/holiday/publicholiday/form.html", success_url="hrm:publicholiday_list")


@login_required
def publicholiday_detail(request, pk):
    obj = get_object_or_404(PublicHoliday, pk=pk, tenant=request.tenant)
    return render(request, "hrm/holiday/publicholiday/detail.html", {"obj": obj})


@login_required
def publicholiday_edit(request, pk):
    return crud_edit(request, model=PublicHoliday, pk=pk, form_class=PublicHolidayForm,
                     template="hrm/holiday/publicholiday/form.html", success_url="hrm:publicholiday_list")


@login_required
@require_POST
def publicholiday_delete(request, pk):
    return crud_delete(request, model=PublicHoliday, pk=pk, success_url="hrm:publicholiday_list")
