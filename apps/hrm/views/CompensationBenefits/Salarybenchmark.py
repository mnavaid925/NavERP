"""HRM 3.37 Compensation & Benefits — Salarybenchmark views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    Designation,
    JobGrade,
    SalaryBenchmark,
)
from apps.hrm.forms import (
    SalaryBenchmarkForm,
)
from apps.hrm.views.PerformanceReview._helpers import _is_admin


# ---- Salary benchmarks (admin catalog) --------------------------------------------------------
@login_required
def salarybenchmark_list(request):
    qs = (SalaryBenchmark.objects.filter(tenant=request.tenant)
          .select_related("job_grade", "designation"))  # currency only rendered on the detail page
    return crud_list(request, qs, "hrm/compensation/salarybenchmark/list.html",
                     search_fields=["region", "job_grade__name", "designation__name", "notes"],
                     filters=[("source", "source", False), ("job_grade", "job_grade_id", True),
                              ("designation", "designation_id", True)],
                     extra_context={"is_admin": _is_admin(request.user),
                                    "source_choices": SalaryBenchmark.SOURCE_CHOICES,
                                    "job_grades": JobGrade.objects.filter(tenant=request.tenant, is_active=True)
                                    .order_by("level_order", "name"),
                                    "designations": Designation.objects.filter(tenant=request.tenant)
                                    .order_by("name")})


@tenant_admin_required
def salarybenchmark_create(request):
    return crud_create(request, form_class=SalaryBenchmarkForm,
                       template="hrm/compensation/salarybenchmark/form.html",
                       success_url="hrm:salarybenchmark_list")


@login_required
def salarybenchmark_detail(request, pk):
    obj = get_object_or_404(
        SalaryBenchmark.objects.select_related("job_grade", "designation", "currency"),
        pk=pk, tenant=request.tenant)
    # Illustrative compa-ratio: the linked designation's midpoint band vs this survey's median.
    band_mid = obj.designation.mid_salary if obj.designation_id else None
    return render(request, "hrm/compensation/salarybenchmark/detail.html", {
        "obj": obj, "is_admin": _is_admin(request.user), "band_mid": band_mid,
        "band_compa_ratio": obj.compa_ratio(band_mid) if band_mid else None})


@tenant_admin_required
def salarybenchmark_edit(request, pk):
    return crud_edit(request, model=SalaryBenchmark, pk=pk, form_class=SalaryBenchmarkForm,
                     template="hrm/compensation/salarybenchmark/form.html",
                     success_url="hrm:salarybenchmark_list")


@tenant_admin_required
@require_POST
def salarybenchmark_delete(request, pk):
    return crud_delete(request, model=SalaryBenchmark, pk=pk, success_url="hrm:salarybenchmark_list")
