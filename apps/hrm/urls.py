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
]
