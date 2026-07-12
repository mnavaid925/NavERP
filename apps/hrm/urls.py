"""HRM (Module 3) URL routes — ``app_name='hrm'``. Standard CRUD names per model
(``<entity>_list/_create/_detail/_edit/_delete``) plus the leave-workflow action routes
(submit/approve/reject/cancel)."""
from django.urls import path

from . import views

app_name = "hrm"

urlpatterns = [
    # Overview / landing (3.1)
    path("", views.hrm_overview, name="hrm_overview"),

    # Designations (3.2)
    path("designations/", views.designation_list, name="designation_list"),
    path("designations/add/", views.designation_create, name="designation_create"),
    path("designations/<int:pk>/", views.designation_detail, name="designation_detail"),
    path("designations/<int:pk>/edit/", views.designation_edit, name="designation_edit"),
    path("designations/<int:pk>/delete/", views.designation_delete, name="designation_delete"),

    # Job Grades (3.2)
    path("job-grades/", views.jobgrade_list, name="jobgrade_list"),
    path("job-grades/add/", views.jobgrade_create, name="jobgrade_create"),
    path("job-grades/<int:pk>/", views.jobgrade_detail, name="jobgrade_detail"),
    path("job-grades/<int:pk>/edit/", views.jobgrade_edit, name="jobgrade_edit"),
    path("job-grades/<int:pk>/delete/", views.jobgrade_delete, name="jobgrade_delete"),

    # Departments (3.2 — core.OrgUnit companion)
    path("departments/", views.department_list, name="department_list"),
    path("departments/add/", views.department_create, name="department_create"),
    path("departments/<int:pk>/", views.department_detail, name="department_detail"),
    path("departments/<int:pk>/edit/", views.department_edit, name="department_edit"),
    path("departments/<int:pk>/delete/", views.department_delete, name="department_delete"),

    # Cost Centers (3.2 — core.OrgUnit companion)
    path("cost-centers/", views.costcenter_list, name="costcenter_list"),
    path("cost-centers/add/", views.costcenter_create, name="costcenter_create"),
    path("cost-centers/<int:pk>/", views.costcenter_detail, name="costcenter_detail"),
    path("cost-centers/<int:pk>/edit/", views.costcenter_edit, name="costcenter_edit"),
    path("cost-centers/<int:pk>/delete/", views.costcenter_delete, name="costcenter_delete"),

    # Org Chart & Company Setup (3.2 — derived, no model)
    path("org-chart/", views.org_chart, name="org_chart"),
    path("company-setup/", views.company_setup, name="company_setup"),

    # Employees (3.1)
    path("employees/", views.employee_list, name="employee_list"),
    path("employees/add/", views.employee_create, name="employee_create"),
    path("employees/<int:pk>/", views.employee_detail, name="employee_detail"),
    path("employees/<int:pk>/edit/", views.employee_edit, name="employee_edit"),
    path("employees/<int:pk>/delete/", views.employee_delete, name="employee_delete"),

    # Employee Documents (3.1 — personnel-file vault) — CRUD + verify/reject
    path("employee-documents/", views.employee_document_list, name="employee_document_list"),
    path("employee-documents/add/", views.employee_document_create, name="employee_document_create"),
    path("employee-documents/<int:pk>/", views.employee_document_detail, name="employee_document_detail"),
    path("employee-documents/<int:pk>/edit/", views.employee_document_edit, name="employee_document_edit"),
    path("employee-documents/<int:pk>/delete/", views.employee_document_delete, name="employee_document_delete"),
    path("employee-documents/<int:pk>/verify/", views.employee_document_mark_verified, name="employee_document_mark_verified"),
    path("employee-documents/<int:pk>/reject/", views.employee_document_reject, name="employee_document_reject"),

    # Employee Lifecycle Events (3.1 — dated job-history timeline) — CRUD
    path("lifecycle-events/", views.employee_lifecycle_list, name="employee_lifecycle_list"),
    path("lifecycle-events/add/", views.employee_lifecycle_create, name="employee_lifecycle_create"),
    path("lifecycle-events/<int:pk>/", views.employee_lifecycle_detail, name="employee_lifecycle_detail"),
    path("lifecycle-events/<int:pk>/edit/", views.employee_lifecycle_edit, name="employee_lifecycle_edit"),
    path("lifecycle-events/<int:pk>/delete/", views.employee_lifecycle_delete, name="employee_lifecycle_delete"),

    # Leave Types (3.10)
    path("leave-types/", views.leavetype_list, name="leavetype_list"),
    path("leave-types/add/", views.leavetype_create, name="leavetype_create"),
    path("leave-types/<int:pk>/", views.leavetype_detail, name="leavetype_detail"),
    path("leave-types/<int:pk>/edit/", views.leavetype_edit, name="leavetype_edit"),
    path("leave-types/<int:pk>/delete/", views.leavetype_delete, name="leavetype_delete"),

    # Leave Allocations (3.10)
    path("leave-allocations/", views.leaveallocation_list, name="leaveallocation_list"),
    path("leave-allocations/add/", views.leaveallocation_create, name="leaveallocation_create"),
    path("leave-allocations/<int:pk>/", views.leaveallocation_detail, name="leaveallocation_detail"),
    path("leave-allocations/<int:pk>/edit/", views.leaveallocation_edit, name="leaveallocation_edit"),
    path("leave-allocations/<int:pk>/delete/", views.leaveallocation_delete, name="leaveallocation_delete"),

    # Leave Requests (3.10) — CRUD + workflow actions
    path("leave-requests/", views.leaverequest_list, name="leaverequest_list"),
    path("leave-requests/add/", views.leaverequest_create, name="leaverequest_create"),
    path("leave-requests/<int:pk>/", views.leaverequest_detail, name="leaverequest_detail"),
    path("leave-requests/<int:pk>/edit/", views.leaverequest_edit, name="leaverequest_edit"),
    path("leave-requests/<int:pk>/delete/", views.leaverequest_delete, name="leaverequest_delete"),
    path("leave-requests/<int:pk>/submit/", views.leaverequest_submit, name="leaverequest_submit"),
    path("leave-requests/<int:pk>/approve/", views.leaverequest_approve, name="leaverequest_approve"),
    path("leave-requests/<int:pk>/reject/", views.leaverequest_reject, name="leaverequest_reject"),
    path("leave-requests/<int:pk>/cancel/", views.leaverequest_cancel, name="leaverequest_cancel"),

    # Leave Encashment (3.10) — CRUD + workflow actions
    path("leave-encashments/", views.leaveencashment_list, name="leaveencashment_list"),
    path("leave-encashments/add/", views.leaveencashment_create, name="leaveencashment_create"),
    path("leave-encashments/<int:pk>/", views.leaveencashment_detail, name="leaveencashment_detail"),
    path("leave-encashments/<int:pk>/edit/", views.leaveencashment_edit, name="leaveencashment_edit"),
    path("leave-encashments/<int:pk>/delete/", views.leaveencashment_delete, name="leaveencashment_delete"),
    path("leave-encashments/<int:pk>/submit/", views.leaveencashment_submit, name="leaveencashment_submit"),
    path("leave-encashments/<int:pk>/approve/", views.leaveencashment_approve, name="leaveencashment_approve"),
    path("leave-encashments/<int:pk>/reject/", views.leaveencashment_reject, name="leaveencashment_reject"),
    path("leave-encashments/<int:pk>/mark-paid/", views.leaveencashment_mark_paid, name="leaveencashment_mark_paid"),
    path("leave-encashments/<int:pk>/cancel/", views.leaveencashment_cancel, name="leaveencashment_cancel"),

    # Leave Policy engine (3.10) — standalone page + admin run actions
    path("leave-policy/", views.leave_policy, name="leave_policy"),
    path("leave-policy/accrual-run/", views.leave_accrual_run, name="leave_accrual_run"),
    path("leave-policy/carry-forward-run/", views.leave_carryforward_run, name="leave_carryforward_run"),

    # Timesheets (3.11) — CRUD + workflow + inline entries
    path("timesheets/", views.timesheet_list, name="timesheet_list"),
    path("timesheets/add/", views.timesheet_create, name="timesheet_create"),
    path("timesheets/<int:pk>/", views.timesheet_detail, name="timesheet_detail"),
    path("timesheets/<int:pk>/edit/", views.timesheet_edit, name="timesheet_edit"),
    path("timesheets/<int:pk>/delete/", views.timesheet_delete, name="timesheet_delete"),
    path("timesheets/<int:pk>/submit/", views.timesheet_submit, name="timesheet_submit"),
    path("timesheets/<int:pk>/approve/", views.timesheet_approve, name="timesheet_approve"),
    path("timesheets/<int:pk>/reject/", views.timesheet_reject, name="timesheet_reject"),
    path("timesheets/<int:pk>/cancel/", views.timesheet_cancel, name="timesheet_cancel"),
    path("timesheets/<int:ts_pk>/entries/add/", views.timesheetentry_add, name="timesheetentry_add"),
    path("timesheet-entries/<int:pk>/edit/", views.timesheetentry_edit, name="timesheetentry_edit"),
    path("timesheet-entries/<int:pk>/delete/", views.timesheetentry_delete, name="timesheetentry_delete"),

    # Overtime Requests (3.11) — CRUD + workflow
    path("overtime-requests/", views.overtimerequest_list, name="overtimerequest_list"),
    path("overtime-requests/add/", views.overtimerequest_create, name="overtimerequest_create"),
    path("overtime-requests/<int:pk>/", views.overtimerequest_detail, name="overtimerequest_detail"),
    path("overtime-requests/<int:pk>/edit/", views.overtimerequest_edit, name="overtimerequest_edit"),
    path("overtime-requests/<int:pk>/delete/", views.overtimerequest_delete, name="overtimerequest_delete"),
    path("overtime-requests/<int:pk>/submit/", views.overtimerequest_submit, name="overtimerequest_submit"),
    path("overtime-requests/<int:pk>/approve/", views.overtimerequest_approve, name="overtimerequest_approve"),
    path("overtime-requests/<int:pk>/reject/", views.overtimerequest_reject, name="overtimerequest_reject"),
    path("overtime-requests/<int:pk>/cancel/", views.overtimerequest_cancel, name="overtimerequest_cancel"),

    # Time Tracking reports (3.11)
    path("reports/utilization/", views.timesheet_utilization_report, name="timesheet_utilization_report"),
    path("reports/project-time/", views.project_time_report, name="project_time_report"),

    # Public Holidays (3.12)
    path("holidays/", views.publicholiday_list, name="publicholiday_list"),
    path("holidays/add/", views.publicholiday_create, name="publicholiday_create"),
    path("holidays/<int:pk>/", views.publicholiday_detail, name="publicholiday_detail"),
    path("holidays/<int:pk>/edit/", views.publicholiday_edit, name="publicholiday_edit"),
    path("holidays/<int:pk>/delete/", views.publicholiday_delete, name="publicholiday_delete"),

    # Holiday Policies (3.12)
    path("holiday-policies/", views.holidaypolicy_list, name="holidaypolicy_list"),
    path("holiday-policies/add/", views.holidaypolicy_create, name="holidaypolicy_create"),
    path("holiday-policies/<int:pk>/", views.holidaypolicy_detail, name="holidaypolicy_detail"),
    path("holiday-policies/<int:pk>/edit/", views.holidaypolicy_edit, name="holidaypolicy_edit"),
    path("holiday-policies/<int:pk>/delete/", views.holidaypolicy_delete, name="holidaypolicy_delete"),

    # Floating Holiday Elections (3.12)
    path("floating-holidays/", views.floatingholidayelection_list, name="floatingholidayelection_list"),
    path("floating-holidays/add/", views.floatingholidayelection_create, name="floatingholidayelection_create"),
    path("floating-holidays/<int:pk>/", views.floatingholidayelection_detail, name="floatingholidayelection_detail"),
    path("floating-holidays/<int:pk>/edit/", views.floatingholidayelection_edit, name="floatingholidayelection_edit"),
    path("floating-holidays/<int:pk>/delete/", views.floatingholidayelection_delete, name="floatingholidayelection_delete"),
    path("floating-holidays/<int:pk>/approve/", views.floatingholidayelection_approve, name="floatingholidayelection_approve"),
    path("floating-holidays/<int:pk>/reject/", views.floatingholidayelection_reject, name="floatingholidayelection_reject"),

    # Pay Components (3.13 Salary Structure)
    path("pay-components/", views.paycomponent_list, name="paycomponent_list"),
    path("pay-components/add/", views.paycomponent_create, name="paycomponent_create"),
    path("pay-components/<int:pk>/", views.paycomponent_detail, name="paycomponent_detail"),
    path("pay-components/<int:pk>/edit/", views.paycomponent_edit, name="paycomponent_edit"),
    path("pay-components/<int:pk>/delete/", views.paycomponent_delete, name="paycomponent_delete"),

    # Salary Structure Templates (3.13)
    path("salary-structures/", views.salarystructuretemplate_list, name="salarystructuretemplate_list"),
    path("salary-structures/add/", views.salarystructuretemplate_create, name="salarystructuretemplate_create"),
    path("salary-structures/<int:pk>/", views.salarystructuretemplate_detail, name="salarystructuretemplate_detail"),
    path("salary-structures/<int:pk>/edit/", views.salarystructuretemplate_edit, name="salarystructuretemplate_edit"),
    path("salary-structures/<int:pk>/delete/", views.salarystructuretemplate_delete, name="salarystructuretemplate_delete"),
    path("salary-structures/<int:template_pk>/lines/add/", views.salarystructureline_add, name="salarystructureline_add"),
    path("salary-structure-lines/<int:pk>/edit/", views.salarystructureline_edit, name="salarystructureline_edit"),
    path("salary-structure-lines/<int:pk>/delete/", views.salarystructureline_delete, name="salarystructureline_delete"),

    # Employee Salary Structures (3.13)
    path("employee-salary/", views.employeesalarystructure_list, name="employeesalarystructure_list"),
    path("employee-salary/add/", views.employeesalarystructure_create, name="employeesalarystructure_create"),
    path("employee-salary/<int:pk>/", views.employeesalarystructure_detail, name="employeesalarystructure_detail"),
    path("employee-salary/<int:pk>/edit/", views.employeesalarystructure_edit, name="employeesalarystructure_edit"),
    path("employee-salary/<int:pk>/delete/", views.employeesalarystructure_delete, name="employeesalarystructure_delete"),

    # Payroll Cycles (3.14 Payroll Processing)
    path("payroll-cycles/", views.payrollcycle_list, name="payrollcycle_list"),
    path("payroll-cycles/add/", views.payrollcycle_create, name="payrollcycle_create"),
    path("payroll-cycles/<int:pk>/", views.payrollcycle_detail, name="payrollcycle_detail"),
    path("payroll-cycles/<int:pk>/edit/", views.payrollcycle_edit, name="payrollcycle_edit"),
    path("payroll-cycles/<int:pk>/delete/", views.payrollcycle_delete, name="payrollcycle_delete"),
    path("payroll-cycles/<int:pk>/generate/", views.payrollcycle_generate, name="payrollcycle_generate"),
    path("payroll-cycles/<int:pk>/submit/", views.payrollcycle_submit, name="payrollcycle_submit"),
    path("payroll-cycles/<int:pk>/approve/", views.payrollcycle_approve, name="payrollcycle_approve"),
    path("payroll-cycles/<int:pk>/reject/", views.payrollcycle_reject, name="payrollcycle_reject"),
    path("payroll-cycles/<int:pk>/lock/", views.payrollcycle_lock, name="payrollcycle_lock"),

    # Payslips (3.14)
    path("payslips/", views.payslip_list, name="payslip_list"),
    path("payslips/<int:pk>/", views.payslip_detail, name="payslip_detail"),
    path("payslips/<int:pk>/edit/", views.payslip_edit, name="payslip_edit"),
    path("payslips/<int:pk>/hold/", views.payslip_hold, name="payslip_hold"),
    path("payslips/<int:pk>/release/", views.payslip_release, name="payslip_release"),

    # Shifts (3.9)
    path("shifts/", views.shift_list, name="shift_list"),
    path("shifts/add/", views.shift_create, name="shift_create"),
    path("shifts/<int:pk>/", views.shift_detail, name="shift_detail"),
    path("shifts/<int:pk>/edit/", views.shift_edit, name="shift_edit"),
    path("shifts/<int:pk>/delete/", views.shift_delete, name="shift_delete"),

    # Shift Assignments (3.9)
    path("shift-assignments/", views.shiftassignment_list, name="shiftassignment_list"),
    path("shift-assignments/add/", views.shiftassignment_create, name="shiftassignment_create"),
    path("shift-assignments/<int:pk>/", views.shiftassignment_detail, name="shiftassignment_detail"),
    path("shift-assignments/<int:pk>/edit/", views.shiftassignment_edit, name="shiftassignment_edit"),
    path("shift-assignments/<int:pk>/delete/", views.shiftassignment_delete, name="shiftassignment_delete"),

    # Attendance (3.9)
    path("attendance/", views.attendancerecord_list, name="attendancerecord_list"),
    path("attendance/add/", views.attendancerecord_create, name="attendancerecord_create"),
    path("attendance/<int:pk>/", views.attendancerecord_detail, name="attendancerecord_detail"),
    path("attendance/<int:pk>/edit/", views.attendancerecord_edit, name="attendancerecord_edit"),
    path("attendance/<int:pk>/delete/", views.attendancerecord_delete, name="attendancerecord_delete"),

    # Geofences (3.9)
    path("geofences/", views.geofence_list, name="geofence_list"),
    path("geofences/add/", views.geofence_create, name="geofence_create"),
    path("geofences/<int:pk>/", views.geofence_detail, name="geofence_detail"),
    path("geofences/<int:pk>/edit/", views.geofence_edit, name="geofence_edit"),
    path("geofences/<int:pk>/delete/", views.geofence_delete, name="geofence_delete"),

    # Attendance Regularization (3.9)
    path("regularizations/", views.attendanceregularization_list, name="attendanceregularization_list"),
    path("regularizations/add/", views.attendanceregularization_create, name="attendanceregularization_create"),
    path("regularizations/<int:pk>/", views.attendanceregularization_detail, name="attendanceregularization_detail"),
    path("regularizations/<int:pk>/edit/", views.attendanceregularization_edit, name="attendanceregularization_edit"),
    path("regularizations/<int:pk>/delete/", views.attendanceregularization_delete, name="attendanceregularization_delete"),
    path("regularizations/<int:pk>/submit/", views.attendanceregularization_submit, name="attendanceregularization_submit"),
    path("regularizations/<int:pk>/approve/", views.attendanceregularization_approve, name="attendanceregularization_approve"),
    path("regularizations/<int:pk>/reject/", views.attendanceregularization_reject, name="attendanceregularization_reject"),
    path("regularizations/<int:pk>/cancel/", views.attendanceregularization_cancel, name="attendanceregularization_cancel"),

    # Onboarding Templates (3.3)
    path("onboarding-templates/", views.onboardingtemplate_list, name="onboardingtemplate_list"),
    path("onboarding-templates/add/", views.onboardingtemplate_create, name="onboardingtemplate_create"),
    path("onboarding-templates/<int:pk>/", views.onboardingtemplate_detail, name="onboardingtemplate_detail"),
    path("onboarding-templates/<int:pk>/edit/", views.onboardingtemplate_edit, name="onboardingtemplate_edit"),
    path("onboarding-templates/<int:pk>/delete/", views.onboardingtemplate_delete, name="onboardingtemplate_delete"),

    # Onboarding Template Tasks (3.3)
    path("onboarding-template-tasks/", views.onboardingtemplatetask_list, name="onboardingtemplatetask_list"),
    path("onboarding-template-tasks/add/", views.onboardingtemplatetask_create, name="onboardingtemplatetask_create"),
    path("onboarding-template-tasks/<int:pk>/", views.onboardingtemplatetask_detail, name="onboardingtemplatetask_detail"),
    path("onboarding-template-tasks/<int:pk>/edit/", views.onboardingtemplatetask_edit, name="onboardingtemplatetask_edit"),
    path("onboarding-template-tasks/<int:pk>/delete/", views.onboardingtemplatetask_delete, name="onboardingtemplatetask_delete"),

    # Onboarding Programs (3.3) — CRUD + workflow actions
    path("onboarding/", views.onboardingprogram_list, name="onboardingprogram_list"),
    path("onboarding/add/", views.onboardingprogram_create, name="onboardingprogram_create"),
    path("onboarding/<int:pk>/", views.onboardingprogram_detail, name="onboardingprogram_detail"),
    path("onboarding/<int:pk>/edit/", views.onboardingprogram_edit, name="onboardingprogram_edit"),
    path("onboarding/<int:pk>/delete/", views.onboardingprogram_delete, name="onboardingprogram_delete"),
    path("onboarding/<int:pk>/activate/", views.onboardingprogram_activate, name="onboardingprogram_activate"),
    path("onboarding/<int:pk>/generate-tasks/", views.onboardingprogram_generate_tasks, name="onboardingprogram_generate_tasks"),
    path("onboarding/<int:pk>/complete/", views.onboardingprogram_complete, name="onboardingprogram_complete"),
    path("onboarding/<int:pk>/cancel/", views.onboardingprogram_cancel, name="onboardingprogram_cancel"),

    # Onboarding Tasks (3.3) — CRUD + workflow actions
    path("onboarding-tasks/", views.onboardingtask_list, name="onboardingtask_list"),
    path("onboarding-tasks/add/", views.onboardingtask_create, name="onboardingtask_create"),
    path("onboarding-tasks/<int:pk>/", views.onboardingtask_detail, name="onboardingtask_detail"),
    path("onboarding-tasks/<int:pk>/edit/", views.onboardingtask_edit, name="onboardingtask_edit"),
    path("onboarding-tasks/<int:pk>/delete/", views.onboardingtask_delete, name="onboardingtask_delete"),
    path("onboarding-tasks/<int:pk>/complete/", views.onboardingtask_complete, name="onboardingtask_complete"),
    path("onboarding-tasks/<int:pk>/reopen/", views.onboardingtask_reopen, name="onboardingtask_reopen"),
    path("onboarding-tasks/<int:pk>/skip/", views.onboardingtask_skip, name="onboardingtask_skip"),

    # Onboarding Documents (3.3) — CRUD + mark-signed
    path("onboarding-documents/", views.onboardingdocument_list, name="onboardingdocument_list"),
    path("onboarding-documents/add/", views.onboardingdocument_create, name="onboardingdocument_create"),
    path("onboarding-documents/<int:pk>/", views.onboardingdocument_detail, name="onboardingdocument_detail"),
    path("onboarding-documents/<int:pk>/edit/", views.onboardingdocument_edit, name="onboardingdocument_edit"),
    path("onboarding-documents/<int:pk>/delete/", views.onboardingdocument_delete, name="onboardingdocument_delete"),
    path("onboarding-documents/<int:pk>/mark-signed/", views.onboardingdocument_mark_signed, name="onboardingdocument_mark_signed"),

    # Asset Allocations (3.3) — CRUD + issue/return
    path("assets/", views.assetallocation_list, name="assetallocation_list"),
    path("assets/add/", views.assetallocation_create, name="assetallocation_create"),
    path("assets/<int:pk>/", views.assetallocation_detail, name="assetallocation_detail"),
    path("assets/<int:pk>/edit/", views.assetallocation_edit, name="assetallocation_edit"),
    path("assets/<int:pk>/delete/", views.assetallocation_delete, name="assetallocation_delete"),
    path("assets/<int:pk>/issue/", views.assetallocation_issue, name="assetallocation_issue"),
    path("assets/<int:pk>/return/", views.assetallocation_return, name="assetallocation_return"),

    # Orientation Sessions (3.3) — CRUD + attendance
    path("orientation/", views.orientationsession_list, name="orientationsession_list"),
    path("orientation/add/", views.orientationsession_create, name="orientationsession_create"),
    path("orientation/<int:pk>/", views.orientationsession_detail, name="orientationsession_detail"),
    path("orientation/<int:pk>/edit/", views.orientationsession_edit, name="orientationsession_edit"),
    path("orientation/<int:pk>/delete/", views.orientationsession_delete, name="orientationsession_delete"),
    path("orientation/<int:pk>/mark-attended/", views.orientationsession_mark_attended, name="orientationsession_mark_attended"),
    path("orientation/<int:pk>/mark-missed/", views.orientationsession_mark_missed, name="orientationsession_mark_missed"),

    # Separation Cases (3.4) — CRUD + workflow + letters
    path("separations/", views.separationcase_list, name="separationcase_list"),
    path("separations/add/", views.separationcase_create, name="separationcase_create"),
    path("separations/<int:pk>/", views.separationcase_detail, name="separationcase_detail"),
    path("separations/<int:pk>/edit/", views.separationcase_edit, name="separationcase_edit"),
    path("separations/<int:pk>/delete/", views.separationcase_delete, name="separationcase_delete"),
    path("separations/<int:pk>/submit/", views.separationcase_submit, name="separationcase_submit"),
    path("separations/<int:pk>/approve/", views.separationcase_approve, name="separationcase_approve"),
    path("separations/<int:pk>/reject/", views.separationcase_reject, name="separationcase_reject"),
    path("separations/<int:pk>/withdraw/", views.separationcase_withdraw, name="separationcase_withdraw"),
    path("separations/<int:pk>/mark-cleared/", views.separationcase_mark_cleared, name="separationcase_mark_cleared"),
    path("separations/<int:pk>/complete/", views.separationcase_complete, name="separationcase_complete"),
    path("separations/<int:pk>/relieving-letter/", views.separationcase_generate_relieving_letter, name="separationcase_relieving_letter"),
    path("separations/<int:pk>/experience-letter/", views.separationcase_generate_experience_letter, name="separationcase_experience_letter"),
    path("letters/", views.offboarding_letters, name="offboarding_letters"),

    # Exit Interviews (3.4) — CRUD + workflow
    path("exit-interviews/", views.exitinterview_list, name="exitinterview_list"),
    path("exit-interviews/add/", views.exitinterview_create, name="exitinterview_create"),
    path("exit-interviews/<int:pk>/", views.exitinterview_detail, name="exitinterview_detail"),
    path("exit-interviews/<int:pk>/edit/", views.exitinterview_edit, name="exitinterview_edit"),
    path("exit-interviews/<int:pk>/delete/", views.exitinterview_delete, name="exitinterview_delete"),
    path("exit-interviews/<int:pk>/complete/", views.exitinterview_complete, name="exitinterview_complete"),
    path("exit-interviews/<int:pk>/skip/", views.exitinterview_skip, name="exitinterview_skip"),

    # Clearance Items (3.4) — CRUD + workflow
    path("clearance/", views.clearanceitem_list, name="clearanceitem_list"),
    path("clearance/add/", views.clearanceitem_create, name="clearanceitem_create"),
    path("clearance/<int:pk>/", views.clearanceitem_detail, name="clearanceitem_detail"),
    path("clearance/<int:pk>/edit/", views.clearanceitem_edit, name="clearanceitem_edit"),
    path("clearance/<int:pk>/delete/", views.clearanceitem_delete, name="clearanceitem_delete"),
    path("clearance/<int:pk>/mark-cleared/", views.clearanceitem_mark_cleared, name="clearanceitem_mark_cleared"),
    path("clearance/<int:pk>/mark-na/", views.clearanceitem_mark_na, name="clearanceitem_mark_na"),
    path("clearance/<int:pk>/reject/", views.clearanceitem_reject, name="clearanceitem_reject"),

    # Final Settlements (3.4) — CRUD + workflow
    path("settlements/", views.finalsettlement_list, name="finalsettlement_list"),
    path("settlements/add/", views.finalsettlement_create, name="finalsettlement_create"),
    path("settlements/<int:pk>/", views.finalsettlement_detail, name="finalsettlement_detail"),
    path("settlements/<int:pk>/edit/", views.finalsettlement_edit, name="finalsettlement_edit"),
    path("settlements/<int:pk>/delete/", views.finalsettlement_delete, name="finalsettlement_delete"),
    path("settlements/<int:pk>/compute/", views.finalsettlement_compute, name="finalsettlement_compute"),
    path("settlements/<int:pk>/hr-approve/", views.finalsettlement_hr_approve, name="finalsettlement_hr_approve"),
    path("settlements/<int:pk>/finance-approve/", views.finalsettlement_finance_approve, name="finalsettlement_finance_approve"),
    path("settlements/<int:pk>/mark-paid/", views.finalsettlement_mark_paid, name="finalsettlement_mark_paid"),

    # Job Description Templates (3.5) — CRUD
    path("job-templates/", views.jobdescriptiontemplate_list, name="jobdescriptiontemplate_list"),
    path("job-templates/add/", views.jobdescriptiontemplate_create, name="jobdescriptiontemplate_create"),
    path("job-templates/<int:pk>/", views.jobdescriptiontemplate_detail, name="jobdescriptiontemplate_detail"),
    path("job-templates/<int:pk>/edit/", views.jobdescriptiontemplate_edit, name="jobdescriptiontemplate_edit"),
    path("job-templates/<int:pk>/delete/", views.jobdescriptiontemplate_delete, name="jobdescriptiontemplate_delete"),

    # Job Requisitions (3.5) — CRUD + approval state machine + utilities
    path("requisitions/", views.jobrequisition_list, name="jobrequisition_list"),
    path("requisitions/add/", views.jobrequisition_create, name="jobrequisition_create"),
    path("requisitions/<int:pk>/", views.jobrequisition_detail, name="jobrequisition_detail"),
    path("requisitions/<int:pk>/edit/", views.jobrequisition_edit, name="jobrequisition_edit"),
    path("requisitions/<int:pk>/delete/", views.jobrequisition_delete, name="jobrequisition_delete"),
    path("requisitions/<int:pk>/submit/", views.jobrequisition_submit, name="jobrequisition_submit"),
    path("requisitions/<int:pk>/approve-step/", views.jobrequisition_approve_step, name="jobrequisition_approve_step"),
    path("requisitions/<int:pk>/reject/", views.jobrequisition_reject, name="jobrequisition_reject"),
    path("requisitions/<int:pk>/return/", views.jobrequisition_return, name="jobrequisition_return"),
    path("requisitions/<int:pk>/post/", views.jobrequisition_post, name="jobrequisition_post"),
    path("requisitions/<int:pk>/hold/", views.jobrequisition_hold, name="jobrequisition_hold"),
    path("requisitions/<int:pk>/fill/", views.jobrequisition_mark_filled, name="jobrequisition_mark_filled"),
    path("requisitions/<int:pk>/cancel/", views.jobrequisition_cancel, name="jobrequisition_cancel"),
    path("requisitions/<int:pk>/apply-template/", views.jobrequisition_apply_template, name="jobrequisition_apply_template"),
    path("requisitions/<int:pk>/clone/", views.jobrequisition_clone, name="jobrequisition_clone"),

    # Requisition approval steps (3.5) — inline add/remove from the requisition hub
    path("requisitions/<int:jr_pk>/approval/add/", views.approval_add, name="approval_add"),
    path("requisition-approvals/<int:pk>/delete/", views.approval_delete, name="approval_delete"),

    # Candidates (3.6) — CRUD + candidate hub + inline skill/tag actions
    path("candidates/", views.candidate_list, name="candidate_list"),
    path("candidates/add/", views.candidate_create, name="candidate_create"),
    path("candidates/<int:pk>/", views.candidate_detail, name="candidate_detail"),
    path("candidates/<int:pk>/edit/", views.candidate_edit, name="candidate_edit"),
    path("candidates/<int:pk>/delete/", views.candidate_delete, name="candidate_delete"),
    path("candidates/<int:pk>/hire/", views.candidate_mark_hired, name="candidate_mark_hired"),
    path("candidates/<int:pk>/blacklist/", views.candidate_blacklist, name="candidate_blacklist"),
    path("candidates/<int:pk>/restore/", views.candidate_restore, name="candidate_restore"),
    path("candidates/<int:pk>/skills/add/", views.candidate_skill_add, name="candidate_skill_add"),
    path("candidates/<int:pk>/skills/<int:skill_pk>/delete/", views.candidate_skill_delete, name="candidate_skill_delete"),
    path("candidates/<int:pk>/tags/add/", views.candidate_tag_add, name="candidate_tag_add"),
    path("candidates/<int:pk>/tags/<int:tag_pk>/remove/", views.candidate_tag_remove, name="candidate_tag_remove"),

    # Job Applications (3.6) — CRUD + pipeline stage actions + send-email
    path("applications/", views.application_list, name="application_list"),
    path("applications/add/", views.application_create, name="application_create"),
    path("applications/<int:pk>/", views.application_detail, name="application_detail"),
    path("applications/<int:pk>/edit/", views.application_edit, name="application_edit"),
    path("applications/<int:pk>/delete/", views.application_delete, name="application_delete"),
    path("applications/<int:pk>/advance/", views.application_advance_stage, name="application_advance_stage"),
    path("applications/<int:pk>/reject/", views.application_reject, name="application_reject"),
    path("applications/<int:pk>/withdraw/", views.application_withdraw, name="application_withdraw"),
    path("applications/<int:pk>/hold/", views.application_hold, name="application_hold"),
    path("applications/<int:pk>/send-email/", views.application_send_email, name="application_send_email"),

    # Candidate Tags (3.6) — catalog CRUD (no detail page)
    path("candidate-tags/", views.candidatetag_list, name="candidatetag_list"),
    path("candidate-tags/add/", views.candidatetag_create, name="candidatetag_create"),
    path("candidate-tags/<int:pk>/edit/", views.candidatetag_edit, name="candidatetag_edit"),
    path("candidate-tags/<int:pk>/delete/", views.candidatetag_delete, name="candidatetag_delete"),

    # Candidate Email Templates (3.6) — CRUD
    path("candidate-email-templates/", views.emailtemplate_list, name="emailtemplate_list"),
    path("candidate-email-templates/add/", views.emailtemplate_create, name="emailtemplate_create"),
    path("candidate-email-templates/<int:pk>/", views.emailtemplate_detail, name="emailtemplate_detail"),
    path("candidate-email-templates/<int:pk>/edit/", views.emailtemplate_edit, name="emailtemplate_edit"),
    path("candidate-email-templates/<int:pk>/delete/", views.emailtemplate_delete, name="emailtemplate_delete"),

    # Candidate Communications (3.6) — append-only log (list + detail only)
    path("candidate-communications/", views.communication_list, name="communication_list"),
    path("candidate-communications/<int:pk>/", views.communication_detail, name="communication_detail"),

    # Public career portal (3.6) — UNAUTHENTICATED. WARNING: add rate-limiting in production.
    path("careers/", views.careers_list, name="careers_list"),
    path("careers/<str:token>/apply/", views.careers_apply, name="careers_apply"),

    # Interviews (3.7) — CRUD + hub + status machine + panel + invite/reminder actions
    path("interviews/", views.interview_list, name="interview_list"),
    path("interviews/add/", views.interview_create, name="interview_create"),
    path("interviews/<int:pk>/", views.interview_detail, name="interview_detail"),
    path("interviews/<int:pk>/edit/", views.interview_edit, name="interview_edit"),
    path("interviews/<int:pk>/delete/", views.interview_delete, name="interview_delete"),
    path("interviews/<int:pk>/confirm/", views.interview_confirm, name="interview_confirm"),
    path("interviews/<int:pk>/start/", views.interview_start, name="interview_start"),
    path("interviews/<int:pk>/complete/", views.interview_complete, name="interview_complete"),
    path("interviews/<int:pk>/cancel/", views.interview_cancel, name="interview_cancel"),
    path("interviews/<int:pk>/no-show/", views.interview_no_show, name="interview_no_show"),
    path("interviews/<int:pk>/reschedule/", views.interview_reschedule, name="interview_reschedule"),
    path("interviews/<int:pk>/panelists/add/", views.interview_panelist_add, name="interview_panelist_add"),
    path("interviews/<int:pk>/panelists/<int:panelist_pk>/remove/", views.interview_panelist_remove, name="interview_panelist_remove"),
    path("interviews/<int:pk>/panelists/<int:panelist_pk>/rsvp/", views.interview_panelist_rsvp, name="interview_panelist_rsvp"),
    path("interviews/<int:pk>/send-invite/", views.interview_send_invite, name="interview_send_invite"),
    path("interviews/<int:pk>/send-reminder/", views.interview_send_reminder, name="interview_send_reminder"),
    path("interviews/<int:pk>/request-feedback/", views.interview_request_feedback, name="interview_request_feedback"),

    # Interview feedback / scorecards (3.7) — CRUD + hub + submit + inline criteria
    path("interview-feedback/", views.interviewfeedback_list, name="interviewfeedback_list"),
    path("interview-feedback/add/", views.interviewfeedback_create, name="interviewfeedback_create"),
    path("interview-feedback/<int:pk>/", views.interviewfeedback_detail, name="interviewfeedback_detail"),
    path("interview-feedback/<int:pk>/edit/", views.interviewfeedback_edit, name="interviewfeedback_edit"),
    path("interview-feedback/<int:pk>/delete/", views.interviewfeedback_delete, name="interviewfeedback_delete"),
    path("interview-feedback/<int:pk>/submit/", views.interviewfeedback_submit, name="interviewfeedback_submit"),
    path("interview-feedback/<int:pk>/criteria/add/", views.feedbackcriterion_add, name="feedbackcriterion_add"),
    path("interview-feedback/<int:pk>/criteria/<int:criterion_pk>/delete/", views.feedbackcriterion_delete, name="feedbackcriterion_delete"),

    # Offer Letter Templates (3.8) — CRUD (printable-letter body library)
    path("offer-letter-templates/", views.offerlettertemplate_list, name="offerlettertemplate_list"),
    path("offer-letter-templates/add/", views.offerlettertemplate_create, name="offerlettertemplate_create"),
    path("offer-letter-templates/<int:pk>/", views.offerlettertemplate_detail, name="offerlettertemplate_detail"),
    path("offer-letter-templates/<int:pk>/edit/", views.offerlettertemplate_edit, name="offerlettertemplate_edit"),
    path("offer-letter-templates/<int:pk>/delete/", views.offerlettertemplate_delete, name="offerlettertemplate_delete"),

    # Offers (3.8) — CRUD + hub + approval chain + status machine + printable letter
    path("offers/", views.offer_list, name="offer_list"),
    path("offers/add/", views.offer_create, name="offer_create"),
    path("offers/<int:pk>/", views.offer_detail, name="offer_detail"),
    path("offers/<int:pk>/edit/", views.offer_edit, name="offer_edit"),
    path("offers/<int:pk>/delete/", views.offer_delete, name="offer_delete"),
    path("offers/<int:pk>/submit/", views.offer_submit, name="offer_submit"),
    path("offers/<int:pk>/approve-step/", views.offer_approve_step, name="offer_approve_step"),
    path("offers/<int:pk>/reject-step/", views.offer_reject_step, name="offer_reject_step"),
    path("offers/<int:pk>/extend/", views.offer_extend, name="offer_extend"),
    path("offers/<int:pk>/accept/", views.offer_accept, name="offer_accept"),
    path("offers/<int:pk>/decline/", views.offer_decline, name="offer_decline"),
    path("offers/<int:pk>/rescind/", views.offer_rescind, name="offer_rescind"),
    path("offers/<int:pk>/expire/", views.offer_expire, name="offer_expire"),
    path("offers/<int:pk>/send-email/", views.offer_send_email, name="offer_send_email"),
    path("offers/<int:pk>/letter/", views.offer_letter_print, name="offer_letter_print"),
    path("offers/<int:pk>/approvals/add/", views.offerapproval_add, name="offerapproval_add"),
    path("offer-approvals/<int:pk>/delete/", views.offerapproval_delete, name="offerapproval_delete"),

    # Pre-boarding items (3.8) — inline on the offer hub (add/remove/submit/verify/reject/send-invite)
    path("offers/<int:pk>/preboarding/add/", views.preboardingitem_add, name="preboardingitem_add"),
    path("preboarding-items/<int:pk>/delete/", views.preboardingitem_delete, name="preboardingitem_delete"),
    path("preboarding-items/<int:pk>/submit/", views.preboardingitem_mark_submitted, name="preboardingitem_mark_submitted"),
    path("preboarding-items/<int:pk>/verify/", views.preboardingitem_verify, name="preboardingitem_verify"),
    path("preboarding-items/<int:pk>/reject/", views.preboardingitem_reject, name="preboardingitem_reject"),
    path("preboarding-items/<int:pk>/send-invite/", views.preboardingitem_send_invite, name="preboardingitem_send_invite"),

    # Background Verification (3.8) — CRUD + lifecycle actions
    path("background-checks/", views.backgroundverification_list, name="backgroundverification_list"),
    path("background-checks/add/", views.backgroundverification_create, name="backgroundverification_create"),
    path("background-checks/<int:pk>/", views.backgroundverification_detail, name="backgroundverification_detail"),
    path("background-checks/<int:pk>/edit/", views.backgroundverification_edit, name="backgroundverification_edit"),
    path("background-checks/<int:pk>/delete/", views.backgroundverification_delete, name="backgroundverification_delete"),
    path("background-checks/<int:pk>/initiate/", views.backgroundverification_initiate, name="backgroundverification_initiate"),
    path("background-checks/<int:pk>/mark-status/", views.backgroundverification_mark_status, name="backgroundverification_mark_status"),
    path("background-checks/<int:pk>/complete/", views.backgroundverification_complete, name="backgroundverification_complete"),

    # ===================== 3.15 Statutory Compliance =====================
    # Config singleton (detail + edit only — one row per tenant)
    path("statutory-config/", views.statutoryconfig_detail, name="statutoryconfig_detail"),
    path("statutory-config/edit/", views.statutoryconfig_edit, name="statutoryconfig_edit"),

    # State-wise PT + LWF slab/rate rules — CRUD
    path("statutory-state-rules/", views.statutorystaterule_list, name="statutorystaterule_list"),
    path("statutory-state-rules/add/", views.statutorystaterule_create, name="statutorystaterule_create"),
    path("statutory-state-rules/<int:pk>/", views.statutorystaterule_detail, name="statutorystaterule_detail"),
    path("statutory-state-rules/<int:pk>/edit/", views.statutorystaterule_edit, name="statutorystaterule_edit"),
    path("statutory-state-rules/<int:pk>/delete/", views.statutorystaterule_delete, name="statutorystaterule_delete"),

    # Per-employee statutory identifiers (UAN / PF / ESI) — CRUD
    path("statutory-identifiers/", views.employeestatutoryidentifier_list, name="employeestatutoryidentifier_list"),
    path("statutory-identifiers/add/", views.employeestatutoryidentifier_create, name="employeestatutoryidentifier_create"),
    path("statutory-identifiers/<int:pk>/", views.employeestatutoryidentifier_detail, name="employeestatutoryidentifier_detail"),
    path("statutory-identifiers/<int:pk>/edit/", views.employeestatutoryidentifier_edit, name="employeestatutoryidentifier_edit"),
    path("statutory-identifiers/<int:pk>/delete/", views.employeestatutoryidentifier_delete, name="employeestatutoryidentifier_delete"),

    # Statutory returns / challans (PF/ESI/PT/TDS/LWF) — CRUD + aggregation + filing workflow
    path("statutory-returns/", views.statutoryreturn_list, name="statutoryreturn_list"),
    path("statutory-returns/add/", views.statutoryreturn_create, name="statutoryreturn_create"),
    path("statutory-returns/<int:pk>/", views.statutoryreturn_detail, name="statutoryreturn_detail"),
    path("statutory-returns/<int:pk>/edit/", views.statutoryreturn_edit, name="statutoryreturn_edit"),
    path("statutory-returns/<int:pk>/delete/", views.statutoryreturn_delete, name="statutoryreturn_delete"),
    path("statutory-returns/<int:pk>/generate/", views.statutoryreturn_generate, name="statutoryreturn_generate"),
    path("statutory-returns/<int:pk>/mark-filed/", views.statutoryreturn_mark_filed, name="statutoryreturn_mark_filed"),
    path("statutory-returns/<int:pk>/mark-paid/", views.statutoryreturn_mark_paid, name="statutoryreturn_mark_paid"),

    # Compliance calendar (cross-scheme due-date overview)
    path("statutory-compliance-calendar/", views.statutory_compliance_calendar, name="statutory_compliance_calendar"),

    # ===================== 3.16 Tax & Investment =====================
    # Tax regime config (+ inline slab bands) + regime comparison
    path("tax-regimes/", views.taxregimeconfig_list, name="taxregimeconfig_list"),
    path("tax-regimes/add/", views.taxregimeconfig_create, name="taxregimeconfig_create"),
    path("tax-regimes/<int:pk>/", views.taxregimeconfig_detail, name="taxregimeconfig_detail"),
    path("tax-regimes/<int:pk>/edit/", views.taxregimeconfig_edit, name="taxregimeconfig_edit"),
    path("tax-regimes/<int:pk>/delete/", views.taxregimeconfig_delete, name="taxregimeconfig_delete"),
    path("tax-regimes/<int:config_pk>/slab-bands/add/", views.taxslabband_create, name="taxslabband_create"),
    path("tax-regimes/<int:config_pk>/slab-bands/<int:pk>/edit/", views.taxslabband_edit, name="taxslabband_edit"),
    path("tax-regimes/<int:config_pk>/slab-bands/<int:pk>/delete/", views.taxslabband_delete, name="taxslabband_delete"),
    path("tax-regime-comparison/", views.tax_regime_comparison, name="tax_regime_comparison"),

    # Investment declarations (+ inline section lines) + submit/lock workflow
    path("investment-declarations/", views.investmentdeclaration_list, name="investmentdeclaration_list"),
    path("investment-declarations/add/", views.investmentdeclaration_create, name="investmentdeclaration_create"),
    path("investment-declarations/<int:pk>/", views.investmentdeclaration_detail, name="investmentdeclaration_detail"),
    path("investment-declarations/<int:pk>/edit/", views.investmentdeclaration_edit, name="investmentdeclaration_edit"),
    path("investment-declarations/<int:pk>/delete/", views.investmentdeclaration_delete, name="investmentdeclaration_delete"),
    path("investment-declarations/<int:pk>/submit/", views.investmentdeclaration_submit, name="investmentdeclaration_submit"),
    path("investment-declarations/<int:pk>/lock/", views.investmentdeclaration_lock, name="investmentdeclaration_lock"),
    path("investment-declarations/<int:declaration_pk>/lines/add/", views.investmentdeclarationline_create, name="investmentdeclarationline_create"),
    path("investment-declarations/<int:declaration_pk>/lines/<int:pk>/edit/", views.investmentdeclarationline_edit, name="investmentdeclarationline_edit"),
    path("investment-declarations/<int:declaration_pk>/lines/<int:pk>/delete/", views.investmentdeclarationline_delete, name="investmentdeclarationline_delete"),

    # Investment proofs — upload (per line) + verify/reject/on-hold workflow
    path("investment-proofs/", views.investmentproof_list, name="investmentproof_list"),
    path("investment-proofs/<int:pk>/", views.investmentproof_detail, name="investmentproof_detail"),
    path("investment-declaration-lines/<int:line_pk>/proofs/upload/", views.investmentproof_upload, name="investmentproof_upload"),
    path("investment-proofs/<int:pk>/verify/", views.investmentproof_verify, name="investmentproof_verify"),
    path("investment-proofs/<int:pk>/reject/", views.investmentproof_reject, name="investmentproof_reject"),
    path("investment-proofs/<int:pk>/on-hold/", views.investmentproof_on_hold, name="investmentproof_on_hold"),

    # Tax computations — CRUD + recompute engine + Form 16 tie-in + Part B report
    path("tax-computations/", views.taxcomputation_list, name="taxcomputation_list"),
    path("tax-computations/add/", views.taxcomputation_create, name="taxcomputation_create"),
    path("tax-computations/<int:pk>/", views.taxcomputation_detail, name="taxcomputation_detail"),
    path("tax-computations/<int:pk>/edit/", views.taxcomputation_edit, name="taxcomputation_edit"),
    path("tax-computations/<int:pk>/delete/", views.taxcomputation_delete, name="taxcomputation_delete"),
    path("tax-computations/<int:pk>/generate/", views.taxcomputation_generate, name="taxcomputation_generate"),
    path("tax-computations/<int:pk>/link-form16/", views.taxcomputation_link_form16, name="taxcomputation_link_form16"),
    path("tax-computations/<int:pk>/form16-partb/", views.form16_partb, name="form16_partb"),

    # ===================== 3.17 Payout & Reports =====================
    # Payout batches (+ generate/approve/disburse from a locked cycle) + payment register
    path("payout-batches/", views.payoutbatch_list, name="payoutbatch_list"),
    path("payout-batches/add/", views.payoutbatch_create, name="payoutbatch_create"),
    path("payout-batches/<int:pk>/", views.payoutbatch_detail, name="payoutbatch_detail"),
    path("payout-batches/<int:pk>/edit/", views.payoutbatch_edit, name="payoutbatch_edit"),
    path("payout-batches/<int:pk>/delete/", views.payoutbatch_delete, name="payoutbatch_delete"),
    path("payout-batches/<int:pk>/generate/", views.payoutbatch_generate, name="payoutbatch_generate"),
    path("payout-batches/<int:pk>/approve/", views.payoutbatch_approve, name="payoutbatch_approve"),
    path("payout-batches/<int:pk>/disburse/", views.payoutbatch_disburse, name="payoutbatch_disburse"),
    path("payout-batches/<int:pk>/register/", views.payment_register, name="payment_register"),

    # Per-payment actions (mark paid/failed/retry)
    path("payout-payments/<int:pk>/mark-paid/", views.payoutpayment_mark_paid, name="payoutpayment_mark_paid"),
    path("payout-payments/<int:pk>/mark-failed/", views.payoutpayment_mark_failed, name="payoutpayment_mark_failed"),
    path("payout-payments/<int:pk>/retry/", views.payoutpayment_retry, name="payoutpayment_retry"),
    path("payout-exceptions/", views.payout_exceptions, name="payout_exceptions"),

    # Payslip distribution (send / view / download tracking)
    path("payslip-distributions/", views.payslipdistribution_list, name="payslipdistribution_list"),
    path("payslip-distributions/<int:pk>/", views.payslipdistribution_detail, name="payslipdistribution_detail"),
    path("payslip-distributions/<int:pk>/send/", views.payslipdistribution_send, name="payslipdistribution_send"),
    path("payslip-distributions/<int:pk>/mark-viewed/", views.payslipdistribution_mark_viewed, name="payslipdistribution_mark_viewed"),
    path("payslip-distributions/<int:pk>/mark-downloaded/", views.payslipdistribution_mark_downloaded, name="payslipdistribution_mark_downloaded"),
    path("payslip-distributions/send-cycle/", views.payslipdistribution_send_cycle, name="payslipdistribution_send_cycle"),

    # Bank reconciliation (match batch payments to the statement by UTR)
    path("bank-reconciliations/", views.bankreconciliation_list, name="bankreconciliation_list"),
    path("bank-reconciliations/add/", views.bankreconciliation_create, name="bankreconciliation_create"),
    path("bank-reconciliations/<int:pk>/", views.bankreconciliation_detail, name="bankreconciliation_detail"),
    path("bank-reconciliations/<int:pk>/edit/", views.bankreconciliation_edit, name="bankreconciliation_edit"),
    path("bank-reconciliations/<int:pk>/delete/", views.bankreconciliation_delete, name="bankreconciliation_delete"),
    path("bank-reconciliations/<int:pk>/reconcile/", views.bankreconciliation_reconcile, name="bankreconciliation_reconcile"),

    # ===================== 3.18 Goal Setting (Performance Management) =====================
    # Goal periods (quarterly/annual cycle catalog) + activate/close workflow
    path("goal-periods/", views.goalperiod_list, name="goalperiod_list"),
    path("goal-periods/add/", views.goalperiod_create, name="goalperiod_create"),
    path("goal-periods/<int:pk>/", views.goalperiod_detail, name="goalperiod_detail"),
    path("goal-periods/<int:pk>/edit/", views.goalperiod_edit, name="goalperiod_edit"),
    path("goal-periods/<int:pk>/delete/", views.goalperiod_delete, name="goalperiod_delete"),
    path("goal-periods/<int:pk>/activate/", views.goalperiod_activate, name="goalperiod_activate"),
    path("goal-periods/<int:pk>/close/", views.goalperiod_close, name="goalperiod_close"),

    # Objectives (the "O") — CRUD + the cascade/alignment tree view
    path("objectives/", views.objective_list, name="objective_list"),
    path("objectives/tree/", views.objective_tree, name="objective_tree"),
    path("objectives/add/", views.objective_create, name="objective_create"),
    path("objectives/<int:pk>/", views.objective_detail, name="objective_detail"),
    path("objectives/<int:pk>/edit/", views.objective_edit, name="objective_edit"),
    path("objectives/<int:pk>/delete/", views.objective_delete, name="objective_delete"),

    # Key results (the "KR") — created nested under an objective; viewed in its context
    path("objectives/<int:objective_pk>/key-results/add/", views.keyresult_create, name="keyresult_create"),
    path("key-results/<int:pk>/", views.keyresult_detail, name="keyresult_detail"),
    path("key-results/<int:pk>/edit/", views.keyresult_edit, name="keyresult_edit"),
    path("key-results/<int:pk>/delete/", views.keyresult_delete, name="keyresult_delete"),

    # Goal check-ins (append-only progress log) — created nested under a key result
    path("key-results/<int:keyresult_pk>/check-ins/add/", views.goalcheckin_create, name="goalcheckin_create"),
    path("check-ins/", views.goalcheckin_list, name="goalcheckin_list"),
    path("check-ins/<int:pk>/", views.goalcheckin_detail, name="goalcheckin_detail"),
    path("check-ins/<int:pk>/delete/", views.goalcheckin_delete, name="goalcheckin_delete"),

    # ===================== 3.19 Performance Review (Performance Management) =====================
    # Review cycles (catalog + phase machine) + advance-phase workflow
    path("review-cycles/", views.reviewcycle_list, name="reviewcycle_list"),
    path("review-cycles/add/", views.reviewcycle_create, name="reviewcycle_create"),
    path("review-cycles/<int:pk>/", views.reviewcycle_detail, name="reviewcycle_detail"),
    path("review-cycles/<int:pk>/edit/", views.reviewcycle_edit, name="reviewcycle_edit"),
    path("review-cycles/<int:pk>/delete/", views.reviewcycle_delete, name="reviewcycle_delete"),
    path("review-cycles/<int:pk>/advance/", views.reviewcycle_advance_phase, name="reviewcycle_advance_phase"),

    # Review templates (form definition per review_type)
    path("review-templates/", views.reviewtemplate_list, name="reviewtemplate_list"),
    path("review-templates/add/", views.reviewtemplate_create, name="reviewtemplate_create"),
    path("review-templates/<int:pk>/", views.reviewtemplate_detail, name="reviewtemplate_detail"),
    path("review-templates/<int:pk>/edit/", views.reviewtemplate_edit, name="reviewtemplate_edit"),
    path("review-templates/<int:pk>/delete/", views.reviewtemplate_delete, name="reviewtemplate_delete"),

    # Performance reviews (self/manager/peer/upward) + submit/share/acknowledge/calibrate workflow
    path("reviews/", views.performancereview_list, name="performancereview_list"),
    path("reviews/add/", views.performancereview_create, name="performancereview_create"),
    path("reviews/<int:pk>/", views.performancereview_detail, name="performancereview_detail"),
    path("reviews/<int:pk>/edit/", views.performancereview_edit, name="performancereview_edit"),
    path("reviews/<int:pk>/delete/", views.performancereview_delete, name="performancereview_delete"),
    path("reviews/<int:pk>/submit/", views.performancereview_submit, name="performancereview_submit"),
    path("reviews/<int:pk>/share/", views.performancereview_share, name="performancereview_share"),
    path("reviews/<int:pk>/acknowledge/", views.performancereview_acknowledge, name="performancereview_acknowledge"),
    path("reviews/<int:pk>/calibrate/", views.performancereview_calibrate, name="performancereview_calibrate"),

    # Review ratings (per-competency lines) — created nested under a review
    path("reviews/<int:review_pk>/ratings/add/", views.reviewrating_create, name="reviewrating_create"),
    path("ratings/<int:pk>/", views.reviewrating_detail, name="reviewrating_detail"),
    path("ratings/<int:pk>/edit/", views.reviewrating_edit, name="reviewrating_edit"),
    path("ratings/<int:pk>/delete/", views.reviewrating_delete, name="reviewrating_delete"),

    # Calibration board (report view — ?cycle=<id>)
    path("calibration/", views.calibration_board, name="calibration_board"),

    # ---- 3.20 Continuous Feedback ----
    # KudosBadge (recognition catalog)
    path("kudos-badges/", views.kudosbadge_list, name="kudosbadge_list"),
    path("kudos-badges/add/", views.kudosbadge_create, name="kudosbadge_create"),
    path("kudos-badges/<int:pk>/", views.kudosbadge_detail, name="kudosbadge_detail"),
    path("kudos-badges/<int:pk>/edit/", views.kudosbadge_edit, name="kudosbadge_edit"),
    path("kudos-badges/<int:pk>/delete/", views.kudosbadge_delete, name="kudosbadge_delete"),

    # Feedback (real-time kudos/appreciation/constructive + request-pull workflow)
    path("feedback/", views.feedback_list, name="feedback_list"),
    path("feedback/add/", views.feedback_create, name="feedback_create"),
    path("feedback/dashboard/", views.feedback_dashboard, name="feedback_dashboard"),
    path("feedback/<int:pk>/", views.feedback_detail, name="feedback_detail"),
    path("feedback/<int:pk>/edit/", views.feedback_edit, name="feedback_edit"),
    path("feedback/<int:pk>/delete/", views.feedback_delete, name="feedback_delete"),
    path("feedback/<int:pk>/acknowledge/", views.feedback_acknowledge, name="feedback_acknowledge"),
    path("feedback/<int:pk>/respond/", views.feedback_respond, name="feedback_respond"),

    # 1:1 Meetings
    path("one-on-ones/", views.oneononemeeting_list, name="oneononemeeting_list"),
    path("one-on-ones/add/", views.oneononemeeting_create, name="oneononemeeting_create"),
    path("one-on-ones/<int:pk>/", views.oneononemeeting_detail, name="oneononemeeting_detail"),
    path("one-on-ones/<int:pk>/edit/", views.oneononemeeting_edit, name="oneononemeeting_edit"),
    path("one-on-ones/<int:pk>/delete/", views.oneononemeeting_delete, name="oneononemeeting_delete"),
    path("one-on-ones/<int:pk>/complete/", views.oneononemeeting_complete, name="oneononemeeting_complete"),
    path("one-on-ones/<int:pk>/cancel/", views.oneononemeeting_cancel, name="oneononemeeting_cancel"),

    # Meeting action items — created nested under a 1:1
    path("one-on-ones/<int:meeting_pk>/action-items/add/", views.meetingactionitem_create, name="meetingactionitem_create"),
    path("action-items/<int:pk>/", views.meetingactionitem_detail, name="meetingactionitem_detail"),
    path("action-items/<int:pk>/edit/", views.meetingactionitem_edit, name="meetingactionitem_edit"),
    path("action-items/<int:pk>/delete/", views.meetingactionitem_delete, name="meetingactionitem_delete"),
    path("action-items/<int:pk>/toggle/", views.meetingactionitem_toggle, name="meetingactionitem_toggle"),

    # ---- 3.21 Performance Improvement ----
    # Performance Improvement Plans (PIPs)
    path("pips/", views.pip_list, name="pip_list"),
    path("pips/add/", views.pip_create, name="pip_create"),
    path("pips/<int:pk>/", views.pip_detail, name="pip_detail"),
    path("pips/<int:pk>/edit/", views.pip_edit, name="pip_edit"),
    path("pips/<int:pk>/delete/", views.pip_delete, name="pip_delete"),
    path("pips/<int:pk>/submit/", views.pip_submit, name="pip_submit"),
    path("pips/<int:pk>/hr-approve/", views.pip_hr_approve, name="pip_hr_approve"),
    path("pips/<int:pk>/acknowledge/", views.pip_acknowledge, name="pip_acknowledge"),
    path("pips/<int:pk>/close/", views.pip_close, name="pip_close"),
    path("pips/<int:pk>/extend/", views.pip_extend, name="pip_extend"),

    # PIP check-ins — created nested under a PIP
    path("pips/<int:pip_pk>/check-ins/add/", views.pipcheckin_create, name="pipcheckin_create"),
    path("pip-check-ins/<int:pk>/", views.pipcheckin_detail, name="pipcheckin_detail"),
    path("pip-check-ins/<int:pk>/edit/", views.pipcheckin_edit, name="pipcheckin_edit"),
    path("pip-check-ins/<int:pk>/delete/", views.pipcheckin_delete, name="pipcheckin_delete"),

    # Warning letters
    path("warning-letters/", views.warningletter_list, name="warningletter_list"),
    path("warning-letters/add/", views.warningletter_create, name="warningletter_create"),
    path("warning-letters/<int:pk>/", views.warningletter_detail, name="warningletter_detail"),
    path("warning-letters/<int:pk>/edit/", views.warningletter_edit, name="warningletter_edit"),
    path("warning-letters/<int:pk>/delete/", views.warningletter_delete, name="warningletter_delete"),
    path("warning-letters/<int:pk>/issue/", views.warningletter_issue, name="warningletter_issue"),
    path("warning-letters/<int:pk>/acknowledge/", views.warningletter_acknowledge, name="warningletter_acknowledge"),
    path("warning-letters/<int:pk>/print/", views.warningletter_print, name="warningletter_print"),

    # Coaching notes (coach/admin only — no employee-facing view)
    path("coaching-notes/", views.coachingnote_list, name="coachingnote_list"),
    path("coaching-notes/add/", views.coachingnote_create, name="coachingnote_create"),
    path("coaching-notes/<int:pk>/", views.coachingnote_detail, name="coachingnote_detail"),
    path("coaching-notes/<int:pk>/edit/", views.coachingnote_edit, name="coachingnote_edit"),
    path("coaching-notes/<int:pk>/delete/", views.coachingnote_delete, name="coachingnote_delete"),

    # ---- 3.22 Training Management ----
    # Training courses (catalog)
    path("training-courses/", views.trainingcourse_list, name="trainingcourse_list"),
    path("training-courses/add/", views.trainingcourse_create, name="trainingcourse_create"),
    path("training-courses/<int:pk>/", views.trainingcourse_detail, name="trainingcourse_detail"),
    path("training-courses/<int:pk>/edit/", views.trainingcourse_edit, name="trainingcourse_edit"),
    path("training-courses/<int:pk>/delete/", views.trainingcourse_delete, name="trainingcourse_delete"),

    # Training sessions (classroom / virtual / external occurrences)
    path("training-sessions/", views.trainingsession_list, name="trainingsession_list"),
    path("training-sessions/add/", views.trainingsession_create, name="trainingsession_create"),
    path("training-sessions/<int:pk>/", views.trainingsession_detail, name="trainingsession_detail"),
    path("training-sessions/<int:pk>/edit/", views.trainingsession_edit, name="trainingsession_edit"),
    path("training-sessions/<int:pk>/delete/", views.trainingsession_delete, name="trainingsession_delete"),

    # Training calendar (upcoming sessions, date-grouped)
    path("training-calendar/", views.training_calendar, name="training_calendar"),

    # ---- 3.23 Learning Management (LMS) ----
    # Learning content items (lessons, nested-create under a course)
    path("training-courses/<int:course_pk>/content/add/", views.learningcontentitem_create, name="learningcontentitem_create"),
    path("learning-content/", views.learningcontentitem_list, name="learningcontentitem_list"),
    path("learning-content/<int:pk>/", views.learningcontentitem_detail, name="learningcontentitem_detail"),
    path("learning-content/<int:pk>/edit/", views.learningcontentitem_edit, name="learningcontentitem_edit"),
    path("learning-content/<int:pk>/delete/", views.learningcontentitem_delete, name="learningcontentitem_delete"),

    # Learning paths (role-based journeys) + nested-create path items
    path("learning-paths/", views.learningpath_list, name="learningpath_list"),
    path("learning-paths/add/", views.learningpath_create, name="learningpath_create"),
    path("learning-paths/<int:pk>/", views.learningpath_detail, name="learningpath_detail"),
    path("learning-paths/<int:pk>/edit/", views.learningpath_edit, name="learningpath_edit"),
    path("learning-paths/<int:pk>/delete/", views.learningpath_delete, name="learningpath_delete"),
    path("learning-paths/<int:path_pk>/items/add/", views.learningpathitem_create, name="learningpathitem_create"),

    path("learning-path-items/", views.learningpathitem_list, name="learningpathitem_list"),
    path("learning-path-items/<int:pk>/", views.learningpathitem_detail, name="learningpathitem_detail"),
    path("learning-path-items/<int:pk>/edit/", views.learningpathitem_edit, name="learningpathitem_edit"),
    path("learning-path-items/<int:pk>/delete/", views.learningpathitem_delete, name="learningpathitem_delete"),

    # Learning progress (per-employee completion tracking)
    path("learning-progress/", views.learningprogress_list, name="learningprogress_list"),
    path("learning-progress/add/", views.learningprogress_create, name="learningprogress_create"),
    path("learning-progress/<int:pk>/", views.learningprogress_detail, name="learningprogress_detail"),
    path("learning-progress/<int:pk>/edit/", views.learningprogress_edit, name="learningprogress_edit"),
    path("learning-progress/<int:pk>/delete/", views.learningprogress_delete, name="learningprogress_delete"),

    # Gamification leaderboard + manager team-progress rollup (computed views)
    path("learning-leaderboard/", views.learning_leaderboard, name="learning_leaderboard"),
    path("learning-team-progress/", views.learning_team_progress, name="learning_team_progress"),

    # ---- 3.24 Training Administration ----
    # Nominations + approval workflow
    path("training-nominations/", views.trainingnomination_list, name="trainingnomination_list"),
    path("training-nominations/add/", views.trainingnomination_create, name="trainingnomination_create"),
    path("training-nominations/<int:pk>/", views.trainingnomination_detail, name="trainingnomination_detail"),
    path("training-nominations/<int:pk>/edit/", views.trainingnomination_edit, name="trainingnomination_edit"),
    path("training-nominations/<int:pk>/delete/", views.trainingnomination_delete, name="trainingnomination_delete"),
    path("training-nominations/<int:pk>/approve/", views.trainingnomination_approve, name="trainingnomination_approve"),
    path("training-nominations/<int:pk>/reject/", views.trainingnomination_reject, name="trainingnomination_reject"),
    path("training-nominations/<int:pk>/waitlist/", views.trainingnomination_waitlist, name="trainingnomination_waitlist"),
    path("training-nominations/<int:pk>/cancel/", views.trainingnomination_cancel, name="trainingnomination_cancel"),
    path("training-nominations/<int:pk>/withdraw/", views.trainingnomination_withdraw, name="trainingnomination_withdraw"),

    # Attendance
    path("training-attendance/", views.trainingattendance_list, name="trainingattendance_list"),
    path("training-attendance/add/", views.trainingattendance_create, name="trainingattendance_create"),
    path("training-attendance/<int:pk>/", views.trainingattendance_detail, name="trainingattendance_detail"),
    path("training-attendance/<int:pk>/edit/", views.trainingattendance_edit, name="trainingattendance_edit"),
    path("training-attendance/<int:pk>/delete/", views.trainingattendance_delete, name="trainingattendance_delete"),

    # Feedback (nested-create under an attendance record)
    path("training-attendance/<int:attendance_pk>/feedback/add/", views.trainingfeedback_create, name="trainingfeedback_create"),
    path("training-feedback/", views.trainingfeedback_list, name="trainingfeedback_list"),
    path("training-feedback/<int:pk>/", views.trainingfeedback_detail, name="trainingfeedback_detail"),
    path("training-feedback/<int:pk>/edit/", views.trainingfeedback_edit, name="trainingfeedback_edit"),
    path("training-feedback/<int:pk>/delete/", views.trainingfeedback_delete, name="trainingfeedback_delete"),

    # Certificates (+ issue-from-attendance/progress, revoke, print)
    path("training-certificates/", views.trainingcertificate_list, name="trainingcertificate_list"),
    path("training-certificates/add/", views.trainingcertificate_create, name="trainingcertificate_create"),
    path("training-attendance/<int:attendance_pk>/issue-certificate/", views.trainingcertificate_issue_from_attendance, name="trainingcertificate_issue_from_attendance"),
    path("learning-progress/<int:progress_pk>/issue-certificate/", views.trainingcertificate_issue_from_progress, name="trainingcertificate_issue_from_progress"),
    path("training-certificates/<int:pk>/", views.trainingcertificate_detail, name="trainingcertificate_detail"),
    path("training-certificates/<int:pk>/edit/", views.trainingcertificate_edit, name="trainingcertificate_edit"),
    path("training-certificates/<int:pk>/delete/", views.trainingcertificate_delete, name="trainingcertificate_delete"),
    path("training-certificates/<int:pk>/revoke/", views.trainingcertificate_revoke, name="trainingcertificate_revoke"),
    path("training-certificates/<int:pk>/print/", views.trainingcertificate_print, name="trainingcertificate_print"),

    # Training budget (computed aggregate view)
    path("training-budget/", views.training_budget, name="training_budget"),

    # 3.25 Personal Information (Self-Service)
    path("my-info/", views.my_info, name="my_info"),
    path("my-info/edit/", views.my_info_edit, name="my_info_edit"),

    # Emergency Contacts (direct self-edit)
    path("emergency-contacts/", views.emergencycontact_list, name="emergencycontact_list"),
    path("emergency-contacts/add/", views.emergencycontact_create, name="emergencycontact_create"),
    path("emergency-contacts/<int:pk>/", views.emergencycontact_detail, name="emergencycontact_detail"),
    path("emergency-contacts/<int:pk>/edit/", views.emergencycontact_edit, name="emergencycontact_edit"),
    path("emergency-contacts/<int:pk>/delete/", views.emergencycontact_delete, name="emergencycontact_delete"),

    # Bank Accounts (admin-gated writes; verify/reject workflow)
    path("bank-accounts/", views.employeebankaccount_list, name="employeebankaccount_list"),
    path("bank-accounts/add/", views.employeebankaccount_create, name="employeebankaccount_create"),
    path("bank-accounts/<int:pk>/", views.employeebankaccount_detail, name="employeebankaccount_detail"),
    path("bank-accounts/<int:pk>/edit/", views.employeebankaccount_edit, name="employeebankaccount_edit"),
    path("bank-accounts/<int:pk>/delete/", views.employeebankaccount_delete, name="employeebankaccount_delete"),
    path("bank-accounts/<int:pk>/verify/", views.employeebankaccount_verify, name="employeebankaccount_verify"),
    path("bank-accounts/<int:pk>/reject/", views.employeebankaccount_reject, name="employeebankaccount_reject"),

    # Family Members (admin-gated writes)
    path("family-members/", views.familymember_list, name="familymember_list"),
    path("family-members/add/", views.familymember_create, name="familymember_create"),
    path("family-members/<int:pk>/", views.familymember_detail, name="familymember_detail"),
    path("family-members/<int:pk>/edit/", views.familymember_edit, name="familymember_edit"),
    path("family-members/<int:pk>/delete/", views.familymember_delete, name="familymember_delete"),

    # Change Requests (maker-checker workflow)
    path("change-requests/", views.changerequest_list, name="changerequest_list"),
    path("change-requests/add/", views.changerequest_create, name="changerequest_create"),
    path("change-requests/<int:pk>/", views.changerequest_detail, name="changerequest_detail"),
    path("change-requests/<int:pk>/edit/", views.changerequest_edit, name="changerequest_edit"),
    path("change-requests/<int:pk>/delete/", views.changerequest_delete, name="changerequest_delete"),
    path("change-requests/<int:pk>/cancel/", views.changerequest_cancel, name="changerequest_cancel"),
    path("change-requests/<int:pk>/approve/", views.changerequest_approve, name="changerequest_approve"),
    path("change-requests/<int:pk>/reject/", views.changerequest_reject, name="changerequest_reject"),

    # 3.26 Request Management (Self-Service)
    path("my-requests/", views.my_requests, name="my_requests"),

    # Document Requests (experience letter / salary certificate / ...)
    path("document-requests/", views.documentrequest_list, name="documentrequest_list"),
    path("document-requests/add/", views.documentrequest_create, name="documentrequest_create"),
    path("document-requests/<int:pk>/", views.documentrequest_detail, name="documentrequest_detail"),
    path("document-requests/<int:pk>/edit/", views.documentrequest_edit, name="documentrequest_edit"),
    path("document-requests/<int:pk>/delete/", views.documentrequest_delete, name="documentrequest_delete"),
    path("document-requests/<int:pk>/submit/", views.documentrequest_submit, name="documentrequest_submit"),
    path("document-requests/<int:pk>/cancel/", views.documentrequest_cancel, name="documentrequest_cancel"),
    path("document-requests/<int:pk>/approve/", views.documentrequest_approve, name="documentrequest_approve"),
    path("document-requests/<int:pk>/reject/", views.documentrequest_reject, name="documentrequest_reject"),
    path("document-requests/<int:pk>/fulfill/", views.documentrequest_fulfill, name="documentrequest_fulfill"),

    # ID Card Requests (new / replacement / correction)
    path("id-card-requests/", views.idcardrequest_list, name="idcardrequest_list"),
    path("id-card-requests/add/", views.idcardrequest_create, name="idcardrequest_create"),
    path("id-card-requests/<int:pk>/", views.idcardrequest_detail, name="idcardrequest_detail"),
    path("id-card-requests/<int:pk>/edit/", views.idcardrequest_edit, name="idcardrequest_edit"),
    path("id-card-requests/<int:pk>/delete/", views.idcardrequest_delete, name="idcardrequest_delete"),
    path("id-card-requests/<int:pk>/submit/", views.idcardrequest_submit, name="idcardrequest_submit"),
    path("id-card-requests/<int:pk>/cancel/", views.idcardrequest_cancel, name="idcardrequest_cancel"),
    path("id-card-requests/<int:pk>/approve/", views.idcardrequest_approve, name="idcardrequest_approve"),
    path("id-card-requests/<int:pk>/reject/", views.idcardrequest_reject, name="idcardrequest_reject"),
    path("id-card-requests/<int:pk>/issue/", views.idcardrequest_issue, name="idcardrequest_issue"),

    # Asset Requests (laptop / equipment)
    path("asset-requests/", views.assetrequest_list, name="assetrequest_list"),
    path("asset-requests/add/", views.assetrequest_create, name="assetrequest_create"),
    path("asset-requests/<int:pk>/", views.assetrequest_detail, name="assetrequest_detail"),
    path("asset-requests/<int:pk>/edit/", views.assetrequest_edit, name="assetrequest_edit"),
    path("asset-requests/<int:pk>/delete/", views.assetrequest_delete, name="assetrequest_delete"),
    path("asset-requests/<int:pk>/submit/", views.assetrequest_submit, name="assetrequest_submit"),
    path("asset-requests/<int:pk>/cancel/", views.assetrequest_cancel, name="assetrequest_cancel"),
    path("asset-requests/<int:pk>/approve/", views.assetrequest_approve, name="assetrequest_approve"),
    path("asset-requests/<int:pk>/reject/", views.assetrequest_reject, name="assetrequest_reject"),
    path("asset-requests/<int:pk>/fulfill/", views.assetrequest_fulfill, name="assetrequest_fulfill"),

    # 3.27 Communication Hub
    path("celebrations/", views.celebrations, name="celebrations"),

    # Announcements
    path("announcements/", views.announcement_list, name="announcement_list"),
    path("announcements/add/", views.announcement_create, name="announcement_create"),
    path("announcements/<int:pk>/", views.announcement_detail, name="announcement_detail"),
    path("announcements/<int:pk>/edit/", views.announcement_edit, name="announcement_edit"),
    path("announcements/<int:pk>/delete/", views.announcement_delete, name="announcement_delete"),
    path("announcements/<int:pk>/publish/", views.announcement_publish, name="announcement_publish"),
    path("announcements/<int:pk>/archive/", views.announcement_archive, name="announcement_archive"),

    # Surveys
    path("surveys/", views.survey_list, name="survey_list"),
    path("surveys/add/", views.survey_create, name="survey_create"),
    path("surveys/<int:pk>/", views.survey_detail, name="survey_detail"),
    path("surveys/<int:pk>/edit/", views.survey_edit, name="survey_edit"),
    path("surveys/<int:pk>/delete/", views.survey_delete, name="survey_delete"),
    path("surveys/<int:pk>/open/", views.survey_open, name="survey_open"),
    path("surveys/<int:pk>/close/", views.survey_close, name="survey_close"),
    path("surveys/<int:pk>/respond/", views.survey_respond, name="survey_respond"),
    path("surveys/<int:pk>/results/", views.survey_results, name="survey_results"),

    # Suggestions (idea box — employee submits, admin reviews)
    path("suggestions/", views.suggestion_list, name="suggestion_list"),
    path("suggestions/add/", views.suggestion_create, name="suggestion_create"),
    path("suggestions/<int:pk>/", views.suggestion_detail, name="suggestion_detail"),
    path("suggestions/<int:pk>/edit/", views.suggestion_edit, name="suggestion_edit"),
    path("suggestions/<int:pk>/delete/", views.suggestion_delete, name="suggestion_delete"),
    path("suggestions/<int:pk>/submit/", views.suggestion_submit, name="suggestion_submit"),
    path("suggestions/<int:pk>/cancel/", views.suggestion_cancel, name="suggestion_cancel"),
    path("suggestions/<int:pk>/approve/", views.suggestion_approve, name="suggestion_approve"),
    path("suggestions/<int:pk>/reject/", views.suggestion_reject, name="suggestion_reject"),
    path("suggestions/<int:pk>/implement/", views.suggestion_implement, name="suggestion_implement"),

    # 3.28 HR Reports (derived, read-only, admin-only)
    path("reports/hr/", views.hr_reports_index, name="hr_reports_index"),
    path("reports/hr/headcount/", views.headcount_report, name="headcount_report"),
    path("reports/hr/attrition/", views.attrition_report, name="attrition_report"),
    path("reports/hr/diversity/", views.diversity_report, name="diversity_report"),
    path("reports/hr/cost/", views.cost_report, name="cost_report"),
    path("reports/hr/hiring/", views.hiring_report, name="hiring_report"),

    # 3.29 Attendance Reports (derived, read-only, admin-only)
    path("reports/attendance/", views.attendance_reports_index, name="attendance_reports_index"),
    path("reports/attendance/summary/", views.attendance_summary_report, name="attendance_summary_report"),
    path("reports/attendance/late-early/", views.late_early_report, name="late_early_report"),
    path("reports/attendance/absenteeism/", views.absenteeism_report, name="absenteeism_report"),
    path("reports/attendance/overtime/", views.overtime_report, name="overtime_report"),

    # 3.30 Leave Reports (derived, read-only, admin-only)
    path("reports/leave/", views.leave_reports_index, name="leave_reports_index"),
    path("reports/leave/register/", views.leave_register_report, name="leave_register_report"),
    path("reports/leave/liability/", views.leave_liability_report, name="leave_liability_report"),
    path("reports/leave/comp-off/", views.comp_off_report, name="comp_off_report"),
    path("reports/leave/trend/", views.leave_trend_report, name="leave_trend_report"),

    # 3.31 Payroll Reports (derived, read-only, admin-only)
    path("reports/payroll/", views.payroll_reports_index, name="payroll_reports_index"),
    path("reports/payroll/salary-register/", views.salary_register_report, name="salary_register_report"),
    path("reports/payroll/tax/", views.tax_report, name="tax_report"),
    path("reports/payroll/statutory/", views.statutory_report, name="statutory_report"),
    path("reports/payroll/ctc/", views.ctc_report, name="ctc_report"),
    path("reports/payroll/cost-center/", views.cost_center_report, name="cost_center_report"),

    # 3.32 Analytics Dashboard
    path("analytics/executive/", views.executive_dashboard, name="executive_dashboard"),
    path("analytics/predictive/", views.predictive_analytics, name="predictive_analytics"),
    path("analytics/benchmarking/", views.benchmarking, name="benchmarking"),
    path("analytics/dashboards/", views.hr_dashboard_list, name="hr_dashboard_list"),
    path("analytics/dashboards/add/", views.hr_dashboard_create, name="hr_dashboard_create"),
    path("analytics/dashboards/<int:pk>/", views.hr_dashboard_detail, name="hr_dashboard_detail"),
    path("analytics/dashboards/<int:pk>/edit/", views.hr_dashboard_edit, name="hr_dashboard_edit"),
    path("analytics/dashboards/<int:pk>/delete/", views.hr_dashboard_delete, name="hr_dashboard_delete"),
    path("analytics/dashboards/<int:dash_pk>/widgets/add/", views.hr_widget_create, name="hr_widget_create"),
    path("analytics/widgets/<int:pk>/edit/", views.hr_widget_edit, name="hr_widget_edit"),
    path("analytics/widgets/<int:pk>/delete/", views.hr_widget_delete, name="hr_widget_delete"),
    path("analytics/widgets/<int:pk>/move/<str:direction>/", views.hr_widget_move, name="hr_widget_move"),
]
