import csv

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.shortcuts import render

from apps.quality.models.RiskManagement.RiskAssessments import RiskAssessment
from apps.quality.models.RiskManagement.RiskControlMeasures import RiskControlMeasure
from apps.quality.models.RiskManagement.RiskManagementPlans import RiskManagementPlan
from apps.quality.views._common import quality_object, quality_scope

ZONE_CLASSES = {
    "unacceptable": "bg-red-100 border-red-300 text-red-800",
    "alarp": "bg-amber-100 border-amber-300 text-amber-800",
    "broadly_acceptable": "bg-green-100 border-green-300 text-green-800",
}


def csv_safe(value):
    if value is None:
        return ""
    text = str(value)
    if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r", "%")):
        return f"'{text}"
    return text


@login_required
def fmea_matrix(request):
    plans = quality_scope(RiskManagementPlan.objects.all(), request).only(
        "id", "number", "title", "matrix_dimension"
    ).order_by("number")

    selected_plan_id = request.GET.get("plan", "").strip()
    selected_plan = None
    if selected_plan_id:
        if not selected_plan_id.isdigit():
            raise Http404("Invalid plan ID")
        selected_plan = quality_object(request, RiskManagementPlan, int(selected_plan_id))
    else:
        selected_plan = plans.first()

    assessments_qs = quality_scope(RiskAssessment.objects.all(), request)
    if selected_plan:
        assessments_qs = assessments_qs.filter(plan=selected_plan)

    assessments = list(assessments_qs.select_related("plan"))

    # 5x5 Matrix cells mapping (Severity: 5 down to 1, Probability: 1 up to 5)
    severity_range = [
        (5, "5 - Catastrophic"),
        (4, "4 - Critical"),
        (3, "3 - Serious"),
        (2, "2 - Minor"),
        (1, "1 - Negligible"),
    ]
    probability_range = [
        (1, "1 - Improbable"),
        (2, "2 - Remote"),
        (3, "3 - Occasional"),
        (4, "4 - Probable"),
        (5, "5 - Frequent"),
    ]

    matrix_cells = {}
    for s_val, s_label in severity_range:
        for p_val, p_label in probability_range:
            score = s_val * p_val
            if score >= 15:
                zone = "unacceptable"
            elif score >= 6:
                zone = "alarp"
            else:
                zone = "broadly_acceptable"

            matrix_cells[(s_val, p_val)] = {
                "score": score,
                "zone": zone,
                "color_class": ZONE_CLASSES[zone],
                "initial_items": [],
                "residual_items": [],
            }

    for item in assessments:
        s = item.initial_severity or 1
        p = item.initial_probability or 1
        if (s, p) in matrix_cells:
            matrix_cells[(s, p)]["initial_items"].append(item)

        if item.residual_severity and item.residual_probability:
            res_s = item.residual_severity
            res_p = item.residual_probability
            if (res_s, res_p) in matrix_cells:
                matrix_cells[(res_s, res_p)]["residual_items"].append(item)

    # Reorganize matrix into grid rows for the template: list of rows, each row has severity + cell list
    grid_rows = []
    for s_val, s_label in severity_range:
        row_cells = []
        for p_val, p_label in probability_range:
            cell_data = matrix_cells[(s_val, p_val)]
            row_cells.append({
                "severity": s_val,
                "probability": p_val,
                "score": cell_data["score"],
                "zone": cell_data["zone"],
                "color_class": cell_data["color_class"],
                "initial_count": len(cell_data["initial_items"]),
                "residual_count": len(cell_data["residual_items"]),
                "initial_items": cell_data["initial_items"],
                "residual_items": cell_data["residual_items"],
            })
        grid_rows.append({
            "severity_val": s_val,
            "severity_label": s_label,
            "cells": row_cells,
        })

    high_risk_items = [a for a in assessments if a.initial_risk_level == "unacceptable"]
    rpn_pareto_items = sorted(assessments, key=lambda x: x.initial_rpn, reverse=True)[:10]

    stats = {
        "total": len(assessments),
        "unacceptable": len([a for a in assessments if a.initial_risk_level == "unacceptable"]),
        "alarp": len([a for a in assessments if a.initial_risk_level == "alarp"]),
        "broadly_acceptable": len([a for a in assessments if a.initial_risk_level == "broadly_acceptable"]),
        "residual_acceptable": len([a for a in assessments if a.residual_risk_acceptable]),
    }

    return render(
        request,
        "quality/riskmanagement/fmea_matrix.html",
        {
            "plans": plans,
            "selected_plan": selected_plan,
            "grid_rows": grid_rows,
            "matrix_cells": matrix_cells,
            "matrix_dimension": selected_plan.matrix_dimension if selected_plan else "5x5",
            "severity_range": severity_range,
            "probability_range": probability_range,
            "high_risk_items": high_risk_items,
            "rpn_pareto_items": rpn_pareto_items,
            "stats": stats,
        },
    )


@login_required
def fmea_matrix_export(request):
    plans = quality_scope(RiskManagementPlan.objects.all(), request).only(
        "id", "number", "title"
    ).order_by("number")

    selected_plan_id = request.GET.get("plan", "").strip()
    selected_plan = None
    if selected_plan_id:
        if not selected_plan_id.isdigit():
            raise Http404("Invalid plan ID")
        selected_plan = quality_object(request, RiskManagementPlan, int(selected_plan_id))
    else:
        selected_plan = plans.first()

    assessments = quality_scope(RiskAssessment.objects.all(), request).select_related("plan")
    if selected_plan:
        assessments = assessments.filter(plan=selected_plan)

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="fmea_risk_matrix.csv"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow([
        "Plan",
        "Number",
        "Type",
        "Hazard / Failure Mode",
        "Initial S",
        "Initial P",
        "Initial D",
        "Initial RPN",
        "Initial Level",
        "Residual S",
        "Residual P",
        "Residual D",
        "Residual RPN",
        "Residual Level",
        "Residual Acceptable",
        "Lifecycle Status",
    ])

    for a in assessments:
        writer.writerow([
            csv_safe(a.plan.number if a.plan else ""),
            csv_safe(a.number),
            csv_safe(a.get_analysis_type_display()),
            csv_safe(a.hazard_description or a.failure_mode),
            csv_safe(a.initial_severity),
            csv_safe(a.initial_probability),
            csv_safe(a.initial_detectability),
            csv_safe(a.initial_rpn),
            csv_safe(a.get_initial_risk_level_display()),
            csv_safe(a.residual_severity or ""),
            csv_safe(a.residual_probability or ""),
            csv_safe(a.residual_detectability or ""),
            csv_safe(a.residual_rpn or ""),
            csv_safe(a.get_residual_risk_level_display() if a.residual_risk_level else ""),
            "Yes" if a.residual_risk_acceptable else "No",
            csv_safe(a.get_lifecycle_status_display()),
        ])

    return response


@login_required
def risk_traceability_matrix(request):
    plans = quality_scope(RiskManagementPlan.objects.all(), request).only(
        "id", "number", "title"
    ).order_by("number")

    selected_plan_id = request.GET.get("plan", "").strip()
    selected_plan = None
    if selected_plan_id:
        if not selected_plan_id.isdigit():
            raise Http404("Invalid plan ID")
        selected_plan = quality_object(request, RiskManagementPlan, int(selected_plan_id))
    else:
        selected_plan = plans.first()

    assessments = quality_scope(RiskAssessment.objects.all(), request)
    if selected_plan:
        assessments = assessments.filter(plan=selected_plan)

    assessments = assessments.select_related("plan", "design_input").prefetch_related(
        "control_measures",
        "control_measures__design_input",
        "control_measures__controlled_document",
        "control_measures__design_verification",
    )

    traceability_rows = []
    total_mitigations = 0
    covered_with_verification = 0

    for a in assessments:
        controls = list(a.control_measures.all())
        total_mitigations += len(controls)
        for c in controls:
            if c.design_verification or (c.implementation_verified and c.effectiveness_verified):
                covered_with_verification += 1

        traceability_rows.append({
            "assessment": a,
            "controls": controls,
            "controls_count": len(controls),
            "is_covered": len(controls) > 0,
        })

    stats = {
        "total_hazards": len(traceability_rows),
        "total_mitigations": total_mitigations,
        "covered_hazards": len([r for r in traceability_rows if r["is_covered"]]),
        "uncovered_hazards": len([r for r in traceability_rows if not r["is_covered"]]),
        "verification_coverage_pct": round((covered_with_verification / total_mitigations * 100), 1) if total_mitigations > 0 else 0,
    }

    return render(
        request,
        "quality/riskmanagement/risk_traceability_matrix.html",
        {
            "plans": plans,
            "selected_plan": selected_plan,
            "traceability_rows": traceability_rows,
            "stats": stats,
        },
    )


@login_required
def risk_traceability_matrix_export(request):
    plans = quality_scope(RiskManagementPlan.objects.all(), request).only(
        "id", "number", "title"
    ).order_by("number")

    selected_plan_id = request.GET.get("plan", "").strip()
    selected_plan = None
    if selected_plan_id:
        if not selected_plan_id.isdigit():
            raise Http404("Invalid plan ID")
        selected_plan = quality_object(request, RiskManagementPlan, int(selected_plan_id))
    else:
        selected_plan = plans.first()

    assessments = quality_scope(RiskAssessment.objects.all(), request).select_related("plan", "design_input").prefetch_related(
        "control_measures",
        "control_measures__design_input",
        "control_measures__controlled_document",
        "control_measures__design_verification",
    )
    if selected_plan:
        assessments = assessments.filter(plan=selected_plan)

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="risk_traceability_matrix.csv"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow([
        "Plan",
        "Hazard Number",
        "Hazard Description",
        "Initial Risk Level",
        "Control Number",
        "Control Tier",
        "Control Title",
        "Design Input (Spec)",
        "Controlled Document (SOP/IFU)",
        "Design Verification (Protocol)",
        "Implementation Verified",
        "Effectiveness Verified",
        "Residual Risk Level",
    ])

    for a in assessments:
        controls = list(a.control_measures.all())
        if controls:
            for c in controls:
                writer.writerow([
                    csv_safe(a.plan.number if a.plan else ""),
                    csv_safe(a.number),
                    csv_safe(a.hazard_description or a.failure_mode),
                    csv_safe(a.get_initial_risk_level_display()),
                    csv_safe(c.number),
                    csv_safe(c.get_control_hierarchy_display()),
                    csv_safe(c.title),
                    csv_safe(c.design_input.identifier if c.design_input else ""),
                    csv_safe(c.controlled_document.number if c.controlled_document else ""),
                    csv_safe(c.design_verification.number if c.design_verification else ""),
                    "Yes" if c.implementation_verified else "No",
                    "Yes" if c.effectiveness_verified else "No",
                    csv_safe(a.get_residual_risk_level_display() if a.residual_risk_level else ""),
                ])
        else:
            writer.writerow([
                csv_safe(a.plan.number if a.plan else ""),
                csv_safe(a.number),
                csv_safe(a.hazard_description or a.failure_mode),
                csv_safe(a.get_initial_risk_level_display()),
                "NO CONTROLS",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                csv_safe(a.get_residual_risk_level_display() if a.residual_risk_level else ""),
            ])

    return response
