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
]
