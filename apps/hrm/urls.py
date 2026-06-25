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

    # Employees (3.1)
    path("employees/", views.employee_list, name="employee_list"),
    path("employees/add/", views.employee_create, name="employee_create"),
    path("employees/<int:pk>/", views.employee_detail, name="employee_detail"),
    path("employees/<int:pk>/edit/", views.employee_edit, name="employee_edit"),
    path("employees/<int:pk>/delete/", views.employee_delete, name="employee_delete"),

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

    # Public Holidays (3.12)
    path("holidays/", views.publicholiday_list, name="publicholiday_list"),
    path("holidays/add/", views.publicholiday_create, name="publicholiday_create"),
    path("holidays/<int:pk>/", views.publicholiday_detail, name="publicholiday_detail"),
    path("holidays/<int:pk>/edit/", views.publicholiday_edit, name="publicholiday_edit"),
    path("holidays/<int:pk>/delete/", views.publicholiday_delete, name="publicholiday_delete"),

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
]
