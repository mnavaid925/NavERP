"""HRM views package — split from apps/hrm/views.py.

One sub-package per sub-module (3.1-3.41), one module per entity (mirrors models/, forms/,
urls/). This __init__ re-exports every view so the apps/hrm/urls/ package (``views.<name>``)
is unchanged.
"""
from ._common import *  # noqa: F401,F403
from ._helpers import *  # noqa: F401,F403
from ._helpers import _DEC, _parse_iso_date, _used_days_subquery  # noqa: F401

# 3.1 Employee Management
from .EmployeeManagement.HrmOverview import (
    hrm_overview,
)  # noqa: F401
from .EmployeeManagement.List import (
    employee_list,
)  # noqa: F401
from .EmployeeManagement.Form import (
    employee_create,
    employee_edit,
    employee_delete,
)  # noqa: F401
from .EmployeeManagement.Detail import (
    employee_detail,
)  # noqa: F401
from .EmployeeManagement._helpers import (
    _is_hr_admin,
    _employee_child_create,
)  # noqa: F401
from .EmployeeManagement.Document import (
    employee_document_list,
    employee_document_create,
    employee_document_detail,
    employee_document_edit,
    employee_document_delete,
    employee_document_mark_verified,
    employee_document_reject,
)  # noqa: F401
from .EmployeeManagement.Lifecycle import (
    employee_lifecycle_list,
    employee_lifecycle_create,
    employee_lifecycle_detail,
    employee_lifecycle_edit,
    employee_lifecycle_delete,
)  # noqa: F401

# 3.2 Organizational Structure
from .OrganizationalStructure.Designation import (
    designation_list,
    designation_create,
    designation_detail,
    designation_edit,
    designation_delete,
)  # noqa: F401
from .OrganizationalStructure.Jobgrade import (
    jobgrade_list,
    jobgrade_create,
    jobgrade_detail,
    jobgrade_edit,
    jobgrade_delete,
)  # noqa: F401
from .OrganizationalStructure.Department import (
    department_list,
    department_create,
    department_detail,
    department_edit,
    department_delete,
)  # noqa: F401
from .OrganizationalStructure.Costcenter import (
    costcenter_list,
    costcenter_create,
    costcenter_detail,
    costcenter_edit,
    costcenter_delete,
)  # noqa: F401
from .OrganizationalStructure.OrgChart import (
    org_chart,
)  # noqa: F401
from .OrganizationalStructure.CompanySetup import (
    company_setup,
)  # noqa: F401

# 3.3 Employee Onboarding
from .EmployeeOnboarding.Template import (
    onboardingtemplate_list,
    onboardingtemplate_create,
    onboardingtemplate_detail,
    onboardingtemplate_edit,
    onboardingtemplate_delete,
)  # noqa: F401
from .EmployeeOnboarding.Templatetask import (
    onboardingtemplatetask_list,
    onboardingtemplatetask_create,
    onboardingtemplatetask_detail,
    onboardingtemplatetask_edit,
    onboardingtemplatetask_delete,
)  # noqa: F401
from .EmployeeOnboarding.Program import (
    onboardingprogram_list,
    onboardingprogram_create,
    onboardingprogram_detail,
    onboardingprogram_edit,
    onboardingprogram_delete,
    onboardingprogram_activate,
    onboardingprogram_generate_tasks,
    onboardingprogram_complete,
    onboardingprogram_cancel,
)  # noqa: F401
from .EmployeeOnboarding.Task import (
    onboardingtask_list,
    onboardingtask_create,
    onboardingtask_detail,
    onboardingtask_edit,
    onboardingtask_delete,
    onboardingtask_complete,
    onboardingtask_reopen,
    onboardingtask_skip,
)  # noqa: F401
from .EmployeeOnboarding.Document import (
    onboardingdocument_list,
    onboardingdocument_create,
    onboardingdocument_detail,
    onboardingdocument_edit,
    onboardingdocument_delete,
    onboardingdocument_mark_signed,
)  # noqa: F401
from .EmployeeOnboarding.Assetallocation import (
    assetallocation_list,
    assetallocation_create,
    assetallocation_detail,
    assetallocation_edit,
    assetallocation_delete,
    assetallocation_issue,
    assetallocation_return,
)  # noqa: F401
from .EmployeeOnboarding.Orientationsession import (
    orientationsession_list,
    orientationsession_create,
    orientationsession_detail,
    orientationsession_edit,
    orientationsession_delete,
    orientationsession_mark_attended,
    orientationsession_mark_missed,
)  # noqa: F401

# 3.4 Employee Offboarding
from .EmployeeOffboarding._helpers import (
    _offboarding_create,
    _generate_letter,
)  # noqa: F401
from .EmployeeOffboarding.Separationcase import (
    separationcase_list,
    separationcase_create,
    separationcase_detail,
    separationcase_edit,
    separationcase_delete,
    separationcase_submit,
    separationcase_approve,
    separationcase_reject,
    separationcase_withdraw,
    separationcase_mark_cleared,
    separationcase_complete,
)  # noqa: F401
from .EmployeeOffboarding.RelievingLetter import (
    separationcase_generate_relieving_letter,
)  # noqa: F401
from .EmployeeOffboarding.ExperienceLetter import (
    separationcase_generate_experience_letter,
)  # noqa: F401
from .EmployeeOffboarding.Letters import (
    offboarding_letters,
)  # noqa: F401
from .EmployeeOffboarding.Exitinterview import (
    exitinterview_list,
    exitinterview_create,
    exitinterview_detail,
    exitinterview_edit,
    exitinterview_delete,
    exitinterview_complete,
    exitinterview_skip,
)  # noqa: F401
from .EmployeeOffboarding.Clearanceitem import (
    clearanceitem_list,
    clearanceitem_create,
    clearanceitem_detail,
    clearanceitem_edit,
    clearanceitem_delete,
    clearanceitem_mark_cleared,
    clearanceitem_mark_na,
    clearanceitem_reject,
)  # noqa: F401
from .EmployeeOffboarding.Finalsettlement import (
    finalsettlement_list,
    finalsettlement_create,
    finalsettlement_detail,
    finalsettlement_edit,
    finalsettlement_delete,
    finalsettlement_compute,
    finalsettlement_hr_approve,
    finalsettlement_finance_approve,
    finalsettlement_mark_paid,
)  # noqa: F401

# 3.5 Job Requisition
from .JobRequisition.Jobdescriptiontemplate import (
    jobdescriptiontemplate_list,
    jobdescriptiontemplate_create,
    jobdescriptiontemplate_detail,
    jobdescriptiontemplate_edit,
    jobdescriptiontemplate_delete,
)  # noqa: F401
from .JobRequisition.Jobrequisition import (
    jobrequisition_list,
    jobrequisition_create,
    jobrequisition_detail,
    jobrequisition_edit,
    jobrequisition_delete,
    jobrequisition_submit,
    jobrequisition_approve_step,
    jobrequisition_reject,
    jobrequisition_return,
    jobrequisition_post,
    jobrequisition_hold,
    jobrequisition_mark_filled,
    jobrequisition_cancel,
    jobrequisition_apply_template,
    jobrequisition_clone,
)  # noqa: F401
from .JobRequisition.Approvals import (
    approval_add,
    approval_delete,
)  # noqa: F401
from .JobRequisition._helpers import (
    _JR_CLONE_FK_FIELDS,
    _JR_CLONE_PLAIN_FIELDS,
)  # noqa: F401

# 3.6 Candidate Management
from .CandidateManagement._helpers import (
    _STAGE_AUTO_TEMPLATE,
    _user_display,
    _apply_merge,
    _send_candidate_email,
    _auto_send_for_stage,
)  # noqa: F401
from .CandidateManagement.Candidate import (
    candidate_list,
    candidate_create,
    candidate_detail,
    candidate_edit,
    candidate_delete,
    candidate_mark_hired,
    candidate_blacklist,
    candidate_restore,
    candidate_skill_add,
    candidate_skill_delete,
    candidate_tag_add,
    candidate_tag_remove,
)  # noqa: F401
from .CandidateManagement.Partys import (
    party_has_only_candidate_role,
)  # noqa: F401
from .CandidateManagement.Application import (
    application_list,
    application_create,
    application_detail,
    application_edit,
    application_delete,
    application_advance_stage,
    application_reject,
    application_withdraw,
    application_hold,
    application_send_email,
)  # noqa: F401
from .CandidateManagement.Tag import (
    candidatetag_list,
    candidatetag_create,
    candidatetag_edit,
    candidatetag_delete,
)  # noqa: F401
from .CandidateManagement.Emailtemplate import (
    emailtemplate_list,
    emailtemplate_create,
    emailtemplate_detail,
    emailtemplate_edit,
    emailtemplate_delete,
)  # noqa: F401
from .CandidateManagement.Communication import (
    communication_list,
    communication_detail,
)  # noqa: F401
from .CandidateManagement.CareersList import (
    careers_list,
)  # noqa: F401
from .CandidateManagement.CareersApply import (
    careers_apply,
)  # noqa: F401

# 3.7 Interview Process
from .InterviewProcess._helpers import (
    _interview_detail_lines,
    _send_interview_email,
    _interview_or_404,
    _form_changes,
    _transition_interview,
)  # noqa: F401
from .InterviewProcess.Interview import (
    interview_list,
    interview_create,
    interview_detail,
    interview_edit,
    interview_delete,
    interview_confirm,
    interview_start,
    interview_complete,
    interview_cancel,
    interview_no_show,
    interview_reschedule,
    interview_panelist_add,
    interview_panelist_remove,
    interview_panelist_rsvp,
    interview_send_invite,
    interview_send_reminder,
    interview_request_feedback,
)  # noqa: F401
from .InterviewProcess.Interviewfeedback import (
    interviewfeedback_list,
    interviewfeedback_create,
    interviewfeedback_detail,
    interviewfeedback_edit,
    interviewfeedback_delete,
    interviewfeedback_submit,
)  # noqa: F401
from .InterviewProcess.Feedbackcriterions import (
    feedbackcriterion_add,
    feedbackcriterion_delete,
)  # noqa: F401

# 3.8 Offer Management
from .OfferManagement._helpers import (
    _offer_or_404,
    _bgv_or_404,
    _preboarding_or_404,
)  # noqa: F401
from .OfferManagement.Offerlettertemplate import (
    offerlettertemplate_list,
    offerlettertemplate_create,
    offerlettertemplate_detail,
    offerlettertemplate_edit,
    offerlettertemplate_delete,
)  # noqa: F401
from .OfferManagement.Offer import (
    offer_list,
    offer_create,
    offer_detail,
    offer_edit,
    offer_delete,
    offer_submit,
    offer_approve_step,
    offer_reject_step,
    offer_extend,
    offer_accept,
    offer_decline,
    offer_rescind,
    offer_expire,
    offer_send_email,
)  # noqa: F401
from .OfferManagement.Offerapprovals import (
    offerapproval_add,
    offerapproval_delete,
)  # noqa: F401
from .OfferManagement.OfferLetter import (
    offer_letter_print,
)  # noqa: F401
from .OfferManagement.Backgroundverification import (
    backgroundverification_list,
    backgroundverification_create,
    backgroundverification_detail,
    backgroundverification_edit,
    backgroundverification_delete,
    backgroundverification_initiate,
    backgroundverification_mark_status,
    backgroundverification_complete,
)  # noqa: F401
from .OfferManagement.Preboardingitems import (
    preboardingitem_add,
    preboardingitem_delete,
    preboardingitem_mark_submitted,
    preboardingitem_verify,
    preboardingitem_reject,
    preboardingitem_send_invite,
)  # noqa: F401

# 3.9 Attendance Management
from .AttendanceManagement.Shift import (
    shift_list,
    shift_create,
    shift_detail,
    shift_edit,
    shift_delete,
)  # noqa: F401
from .AttendanceManagement.Shiftassignment import (
    shiftassignment_list,
    shiftassignment_create,
    shiftassignment_detail,
    shiftassignment_edit,
    shiftassignment_delete,
)  # noqa: F401
from .AttendanceManagement.Record import (
    attendancerecord_list,
    attendancerecord_create,
    attendancerecord_detail,
    attendancerecord_edit,
    attendancerecord_delete,
)  # noqa: F401
from .AttendanceManagement.Geofence import (
    geofence_list,
    geofence_create,
    geofence_detail,
    geofence_edit,
    geofence_delete,
)  # noqa: F401
from .AttendanceManagement.Regularization import (
    attendanceregularization_list,
    attendanceregularization_create,
    attendanceregularization_detail,
    attendanceregularization_edit,
    attendanceregularization_delete,
    attendanceregularization_submit,
    attendanceregularization_approve,
    attendanceregularization_reject,
    attendanceregularization_cancel,
)  # noqa: F401

# 3.10 Leave Management
from .LeaveManagement.Type import (
    leavetype_list,
    leavetype_create,
    leavetype_detail,
    leavetype_edit,
    leavetype_delete,
)  # noqa: F401
from .LeaveManagement.Allocation import (
    leaveallocation_list,
    leaveallocation_create,
    leaveallocation_detail,
    leaveallocation_edit,
    leaveallocation_delete,
)  # noqa: F401
from .LeaveManagement.Request import (
    leaverequest_list,
    leaverequest_create,
    leaverequest_detail,
    leaverequest_edit,
    leaverequest_delete,
    leaverequest_submit,
    leaverequest_approve,
    leaverequest_reject,
    leaverequest_cancel,
)  # noqa: F401
from .LeaveManagement.Encashment import (
    leaveencashment_list,
    leaveencashment_create,
    leaveencashment_detail,
    leaveencashment_edit,
    leaveencashment_delete,
    leaveencashment_submit,
    leaveencashment_approve,
    leaveencashment_reject,
    leaveencashment_mark_paid,
    leaveencashment_cancel,
)  # noqa: F401
from .LeaveManagement._helpers import (
    _policy_year,
    _accrual_target,
)  # noqa: F401
from .LeaveManagement.Policy import (
    leave_policy,
    leave_accrual_run,
    leave_carryforward_run,
)  # noqa: F401

# 3.11 Time Tracking
from .TimeTracking.Timesheet import (
    timesheet_list,
    timesheet_create,
    timesheet_detail,
    timesheet_edit,
    timesheet_delete,
    timesheet_submit,
    timesheet_approve,
    timesheet_reject,
    timesheet_cancel,
    timesheetentry_add,
)  # noqa: F401
from .TimeTracking.Timesheetentry import (
    timesheetentry_edit,
    timesheetentry_delete,
)  # noqa: F401
from .TimeTracking.Overtimerequest import (
    overtimerequest_list,
    overtimerequest_create,
    overtimerequest_detail,
    overtimerequest_edit,
    overtimerequest_delete,
    overtimerequest_submit,
    overtimerequest_approve,
    overtimerequest_reject,
    overtimerequest_cancel,
)  # noqa: F401
from .TimeTracking.UtilizationReport import (
    timesheet_utilization_report,
)  # noqa: F401
from .TimeTracking.ProjectTimeReport import (
    project_time_report,
)  # noqa: F401

# 3.12 Holiday Management
from .HolidayManagement.Publicholiday import (
    publicholiday_list,
    publicholiday_create,
    publicholiday_detail,
    publicholiday_edit,
    publicholiday_delete,
)  # noqa: F401
from .HolidayManagement.Holidaypolicy import (
    holidaypolicy_list,
    holidaypolicy_create,
    holidaypolicy_detail,
    holidaypolicy_edit,
    holidaypolicy_delete,
)  # noqa: F401
from .HolidayManagement.Floatingholidayelection import (
    floatingholidayelection_list,
    floatingholidayelection_create,
    floatingholidayelection_detail,
    floatingholidayelection_edit,
    floatingholidayelection_delete,
    floatingholidayelection_approve,
    floatingholidayelection_reject,
)  # noqa: F401

# 3.13 Salary Structure
from .SalaryStructure.Paycomponent import (
    paycomponent_list,
    paycomponent_create,
    paycomponent_detail,
    paycomponent_edit,
    paycomponent_delete,
)  # noqa: F401
from .SalaryStructure.Salarystructuretemplate import (
    salarystructuretemplate_list,
    salarystructuretemplate_create,
    salarystructuretemplate_detail,
    salarystructuretemplate_edit,
    salarystructuretemplate_delete,
    salarystructureline_add,
    salarystructureline_edit,
    salarystructureline_delete,
)  # noqa: F401
from .SalaryStructure.Employeesalarystructure import (
    employeesalarystructure_list,
    employeesalarystructure_create,
    employeesalarystructure_detail,
    employeesalarystructure_edit,
    employeesalarystructure_delete,
)  # noqa: F401

# 3.14 Payroll Processing
from .PayrollProcessing.Payrollcycle import (
    payrollcycle_list,
    payrollcycle_create,
    payrollcycle_detail,
    payrollcycle_edit,
    payrollcycle_delete,
    payrollcycle_generate,
    payrollcycle_submit,
    payrollcycle_approve,
    payrollcycle_reject,
    payrollcycle_lock,
)  # noqa: F401
from .PayrollProcessing.Payslip import (
    payslip_list,
    payslip_detail,
    payslip_edit,
    payslip_hold,
    payslip_release,
)  # noqa: F401

# 3.15 Statutory Compliance
from .StatutoryCompliance.Statutoryconfig import (
    statutoryconfig_detail,
    statutoryconfig_edit,
)  # noqa: F401
from .StatutoryCompliance.Statutorystaterule import (
    statutorystaterule_list,
    statutorystaterule_create,
    statutorystaterule_detail,
    statutorystaterule_edit,
    statutorystaterule_delete,
)  # noqa: F401
from .StatutoryCompliance.Employeestatutoryidentifier import (
    employeestatutoryidentifier_list,
    employeestatutoryidentifier_create,
    employeestatutoryidentifier_detail,
    employeestatutoryidentifier_edit,
    employeestatutoryidentifier_delete,
)  # noqa: F401
from .StatutoryCompliance.Statutoryreturn import (
    statutoryreturn_list,
    statutoryreturn_create,
    statutoryreturn_detail,
    statutoryreturn_edit,
    statutoryreturn_delete,
    statutoryreturn_generate,
    statutoryreturn_mark_filed,
    statutoryreturn_mark_paid,
)  # noqa: F401
from .StatutoryCompliance.ComplianceCalendar import (
    statutory_compliance_calendar,
)  # noqa: F401

# 3.16 Tax & Investment
from .TaxInvestment.Taxregimeconfig import (
    taxregimeconfig_list,
    taxregimeconfig_create,
    taxregimeconfig_detail,
    taxregimeconfig_edit,
    taxregimeconfig_delete,
    taxslabband_create,
    taxslabband_edit,
    taxslabband_delete,
)  # noqa: F401
from .TaxInvestment._helpers import (
    _computation_breakdown,
    _proof_window_open,
    _set_proof_status,
)  # noqa: F401
from .TaxInvestment.RegimeComparison import (
    tax_regime_comparison,
)  # noqa: F401
from .TaxInvestment.Investmentdeclaration import (
    investmentdeclaration_list,
    investmentdeclaration_create,
    investmentdeclaration_detail,
    investmentdeclaration_edit,
    investmentdeclaration_delete,
    investmentdeclaration_submit,
    investmentdeclaration_lock,
    investmentdeclarationline_create,
    investmentdeclarationline_edit,
    investmentdeclarationline_delete,
)  # noqa: F401
from .TaxInvestment.Investmentproof import (
    investmentproof_upload,
    investmentproof_list,
    investmentproof_detail,
    investmentproof_verify,
    investmentproof_reject,
    investmentproof_on_hold,
)  # noqa: F401
from .TaxInvestment.Taxcomputation import (
    taxcomputation_list,
    taxcomputation_create,
    taxcomputation_detail,
    taxcomputation_edit,
    taxcomputation_delete,
    taxcomputation_generate,
    taxcomputation_link_form16,
)  # noqa: F401
from .TaxInvestment.Form16Partb import (
    form16_partb,
)  # noqa: F401

# 3.17 Payout & Reports
from .PayoutReports._helpers import (
    _recompute_batch_status,
    _mark_sent,
)  # noqa: F401
from .PayoutReports.Payoutbatch import (
    payoutbatch_list,
    payoutbatch_create,
    payoutbatch_detail,
    payoutbatch_edit,
    payoutbatch_delete,
    payoutbatch_generate,
    payoutbatch_approve,
    payoutbatch_disburse,
)  # noqa: F401
from .PayoutReports.Payoutpayments import (
    payoutpayment_mark_paid,
    payoutpayment_mark_failed,
    payoutpayment_retry,
)  # noqa: F401
from .PayoutReports.Payslipdistribution import (
    payslipdistribution_list,
    payslipdistribution_detail,
    payslipdistribution_send,
    payslipdistribution_send_cycle,
    payslipdistribution_mark_viewed,
    payslipdistribution_mark_downloaded,
)  # noqa: F401
from .PayoutReports.Bankreconciliation import (
    bankreconciliation_list,
    bankreconciliation_create,
    bankreconciliation_detail,
    bankreconciliation_edit,
    bankreconciliation_delete,
    bankreconciliation_reconcile,
)  # noqa: F401
from .PayoutReports.PaymentRegister import (
    payment_register,
)  # noqa: F401
from .PayoutReports.Exceptions import (
    payout_exceptions,
)  # noqa: F401

# 3.18 Goal Setting
from .GoalSetting._helpers import (
    _current_employee_profile,
)  # noqa: F401
from .GoalSetting.Goalperiod import (
    goalperiod_list,
    goalperiod_create,
    goalperiod_detail,
    goalperiod_edit,
    goalperiod_delete,
    goalperiod_activate,
    goalperiod_close,
)  # noqa: F401
from .GoalSetting.Objective import (
    objective_list,
    objective_tree,
    objective_create,
    objective_detail,
    objective_edit,
    objective_delete,
)  # noqa: F401
from .GoalSetting.Keyresult import (
    keyresult_create,
    keyresult_detail,
    keyresult_edit,
    keyresult_delete,
)  # noqa: F401
from .GoalSetting.Goalcheckin import (
    goalcheckin_list,
    goalcheckin_create,
    goalcheckin_detail,
    goalcheckin_delete,
)  # noqa: F401

# 3.19 Performance Review
from .PerformanceReview._helpers import (
    _is_admin,
    _is_reviewer,
    _can_edit_review,
    _can_view_review,
    _visible_reviews_q,
)  # noqa: F401
from .PerformanceReview.Reviewcycle import (
    reviewcycle_list,
    reviewcycle_create,
    reviewcycle_detail,
    reviewcycle_edit,
    reviewcycle_delete,
    reviewcycle_advance_phase,
)  # noqa: F401
from .PerformanceReview.Reviewtemplate import (
    reviewtemplate_list,
    reviewtemplate_create,
    reviewtemplate_detail,
    reviewtemplate_edit,
    reviewtemplate_delete,
)  # noqa: F401
from .PerformanceReview.Performancereview import (
    performancereview_list,
    performancereview_create,
    performancereview_detail,
    performancereview_edit,
    performancereview_delete,
    performancereview_submit,
    performancereview_share,
    performancereview_acknowledge,
    performancereview_calibrate,
)  # noqa: F401
from .PerformanceReview.CalibrationBoard import (
    calibration_board,
)  # noqa: F401
from .PerformanceReview.Reviewrating import (
    reviewrating_create,
    reviewrating_detail,
    reviewrating_edit,
    reviewrating_delete,
)  # noqa: F401

# 3.20 Continuous Feedback
from .ContinuousFeedback._helpers import (
    _can_view_feedback,
    _visible_feedback_q,
    _can_edit_feedback,
    _feedback_giver_display,
    _can_view_meeting,
    _visible_meetings_q,
    _can_manage_meeting,
    _can_manage_action_item,
)  # noqa: F401
from .ContinuousFeedback.Kudosbadge import (
    kudosbadge_list,
    kudosbadge_create,
    kudosbadge_detail,
    kudosbadge_edit,
    kudosbadge_delete,
)  # noqa: F401
from .ContinuousFeedback.Feedback import (
    feedback_list,
    feedback_create,
    feedback_detail,
    feedback_edit,
)  # noqa: F401
from .ContinuousFeedback.FeedbackDashboard import (
    feedback_delete,
    feedback_acknowledge,
    feedback_respond,
    feedback_dashboard,
)  # noqa: F401
from .ContinuousFeedback.Oneononemeeting import (
    oneononemeeting_list,
    oneononemeeting_create,
    oneononemeeting_detail,
    oneononemeeting_edit,
    oneononemeeting_delete,
    oneononemeeting_complete,
    oneononemeeting_cancel,
)  # noqa: F401
from .ContinuousFeedback.Meetingactionitem import (
    meetingactionitem_create,
    meetingactionitem_detail,
    meetingactionitem_edit,
    meetingactionitem_delete,
    meetingactionitem_toggle,
)  # noqa: F401

# 3.21 Performance Improvement
from .PerformanceImprovement._helpers import (
    _can_view_pip,
    _visible_pips_q,
    _can_edit_pip,
    _can_view_warning,
    _visible_warnings_q,
    _can_edit_warning,
    _can_view_coaching,
    _visible_coaching_q,
    _can_edit_coaching,
    _can_edit_checkin,
)  # noqa: F401
from .PerformanceImprovement.Pip import (
    pip_list,
    pip_create,
    pip_detail,
    pip_edit,
    pip_delete,
    pip_submit,
    pip_hr_approve,
    pip_acknowledge,
    pip_close,
    pip_extend,
)  # noqa: F401
from .PerformanceImprovement.Pipcheckin import (
    pipcheckin_create,
    pipcheckin_detail,
    pipcheckin_edit,
    pipcheckin_delete,
)  # noqa: F401
from .PerformanceImprovement.Warningletter import (
    warningletter_list,
    warningletter_create,
    warningletter_detail,
    warningletter_edit,
    warningletter_delete,
    warningletter_issue,
    warningletter_acknowledge,
    warningletter_print,
)  # noqa: F401
from .PerformanceImprovement.Coachingnote import (
    coachingnote_list,
    coachingnote_create,
    coachingnote_detail,
    coachingnote_edit,
    coachingnote_delete,
)  # noqa: F401

# 3.22 Training Management
from .TrainingManagement.Trainingcourse import (
    trainingcourse_list,
    trainingcourse_create,
    trainingcourse_detail,
    trainingcourse_edit,
    trainingcourse_delete,
)  # noqa: F401
from .TrainingManagement.Trainingsession import (
    trainingsession_list,
    trainingsession_create,
    trainingsession_detail,
    trainingsession_edit,
    trainingsession_delete,
)  # noqa: F401
from .TrainingManagement.Calendar import (
    training_calendar,
)  # noqa: F401

# 3.23 Learning Management (LMS)
from .LearningManagement.Learningcontentitem import (
    learningcontentitem_create,
    learningcontentitem_list,
    learningcontentitem_detail,
    learningcontentitem_edit,
    learningcontentitem_delete,
)  # noqa: F401
from .LearningManagement.Learningpath import (
    learningpath_list,
    learningpath_create,
    learningpath_detail,
    learningpath_edit,
    learningpath_delete,
)  # noqa: F401
from .LearningManagement.Learningpathitem import (
    learningpathitem_create,
    learningpathitem_list,
    learningpathitem_detail,
    learningpathitem_edit,
    learningpathitem_delete,
)  # noqa: F401
from .LearningManagement.Learningprogress import (
    learningprogress_list,
    learningprogress_create,
    learningprogress_detail,
    learningprogress_edit,
    learningprogress_delete,
)  # noqa: F401
from .LearningManagement._helpers import (
    _LMS_LEVEL_THRESHOLDS,
    _lms_level_for_points,
)  # noqa: F401
from .LearningManagement.Leaderboard import (
    learning_leaderboard,
)  # noqa: F401
from .LearningManagement.TeamProgress import (
    learning_team_progress,
)  # noqa: F401

# 3.24 Training Administration
from .TrainingAdministration._helpers import (
    _can_decide_nomination,
    _can_manage_feedback,
    _issue_certificate,
)  # noqa: F401
from .TrainingAdministration.Trainingnomination import (
    trainingnomination_list,
    trainingnomination_create,
    trainingnomination_detail,
    trainingnomination_edit,
    trainingnomination_delete,
    trainingnomination_approve,
    trainingnomination_reject,
    trainingnomination_waitlist,
    trainingnomination_cancel,
    trainingnomination_withdraw,
)  # noqa: F401
from .TrainingAdministration.Trainingattendance import (
    trainingattendance_list,
    trainingattendance_create,
    trainingattendance_detail,
    trainingattendance_edit,
    trainingattendance_delete,
)  # noqa: F401
from .TrainingAdministration.Trainingfeedback import (
    trainingfeedback_create,
    trainingfeedback_list,
    trainingfeedback_detail,
    trainingfeedback_edit,
    trainingfeedback_delete,
)  # noqa: F401
from .TrainingAdministration.Trainingcertificate import (
    trainingcertificate_list,
    trainingcertificate_create,
    trainingcertificate_issue_from_attendance,
    trainingcertificate_issue_from_progress,
    trainingcertificate_detail,
    trainingcertificate_edit,
    trainingcertificate_delete,
    trainingcertificate_revoke,
    trainingcertificate_print,
)  # noqa: F401
from .TrainingAdministration.Budget import (
    training_budget,
)  # noqa: F401

# 3.25 Personal Information
from .PersonalInformation._helpers import (
    _require_own_profile,
    _can_manage_own_child,
    _ss_scope,
    _ss_employees,
    _is_own_change_request,
    _ss_child_create,
    _ss_child_edit,
    _ss_child_detail,
    _ss_child_delete,
    _CHANGE_FORMS,
    _BANK_CR_FIELDS,
    _FAMILY_CR_FIELDS,
    _assemble_change_request,
    _SENSITIVE_DIFF_FIELDS,
    _mask_diff_value,
    _resolve_cr_employee,
)  # noqa: F401
from .PersonalInformation.MyInfo import (
    my_info,
)  # noqa: F401
from .PersonalInformation.MyInfoEdit import (
    my_info_edit,
)  # noqa: F401
from .PersonalInformation.Emergencycontact import (
    emergencycontact_list,
    emergencycontact_create,
    emergencycontact_detail,
    emergencycontact_edit,
    emergencycontact_delete,
)  # noqa: F401
from .PersonalInformation.Employeebankaccount import (
    employeebankaccount_list,
    employeebankaccount_detail,
    employeebankaccount_create,
    employeebankaccount_edit,
    employeebankaccount_delete,
    employeebankaccount_verify,
    employeebankaccount_reject,
)  # noqa: F401
from .PersonalInformation.Familymember import (
    familymember_list,
    familymember_detail,
    familymember_create,
    familymember_edit,
    familymember_delete,
)  # noqa: F401
from .PersonalInformation.Changerequest import (
    changerequest_list,
    changerequest_create,
    changerequest_detail,
    changerequest_edit,
    changerequest_delete,
    changerequest_cancel,
    changerequest_approve,
    changerequest_reject,
)  # noqa: F401

# 3.26 Request Management
from .RequestManagement._helpers import (
    _is_own_hr_request,
    _hr_request_submit,
    _hr_request_cancel,
    _hr_request_approve,
    _hr_request_reject,
    _hr_request_edit,
    _hr_request_delete,
)  # noqa: F401
from .RequestManagement.Documentrequest import (
    documentrequest_list,
    documentrequest_create,
    documentrequest_detail,
    documentrequest_edit,
    documentrequest_delete,
    documentrequest_submit,
    documentrequest_cancel,
    documentrequest_approve,
    documentrequest_reject,
    documentrequest_fulfill,
)  # noqa: F401
from .RequestManagement.Idcardrequest import (
    idcardrequest_list,
    idcardrequest_create,
    idcardrequest_detail,
    idcardrequest_edit,
    idcardrequest_delete,
    idcardrequest_submit,
    idcardrequest_cancel,
    idcardrequest_approve,
    idcardrequest_reject,
    idcardrequest_issue,
)  # noqa: F401
from .RequestManagement.Assetrequest import (
    assetrequest_list,
    assetrequest_create,
    assetrequest_detail,
    assetrequest_edit,
    assetrequest_delete,
    assetrequest_submit,
    assetrequest_cancel,
    assetrequest_approve,
    assetrequest_reject,
    assetrequest_fulfill,
)  # noqa: F401
from .RequestManagement.MyRequests import (
    my_requests,
)  # noqa: F401
from .RequestManagement.Suggestions import (
    suggestion_delete,
    suggestion_submit,
    suggestion_cancel,
    suggestion_approve,
    suggestion_reject,
    suggestion_implement,
)  # noqa: F401

# 3.27 Communication Hub
from .CommunicationHub._helpers import (
    _next_occurrence,
    _days_until,
    _is_number,
    _announcement_targets,
)  # noqa: F401
from .CommunicationHub.Celebrations import (
    celebrations,
)  # noqa: F401
from .CommunicationHub.Announcement import (
    announcement_list,
    announcement_detail,
    announcement_create,
    announcement_edit,
    announcement_delete,
    announcement_publish,
    announcement_archive,
)  # noqa: F401
from .CommunicationHub.Survey import (
    survey_list,
    survey_detail,
    survey_create,
    survey_edit,
    survey_delete,
    survey_open,
    survey_close,
    survey_respond,
    survey_results,
)  # noqa: F401
from .CommunicationHub.Suggestion import (
    suggestion_list,
    suggestion_create,
    suggestion_detail,
    suggestion_edit,
)  # noqa: F401

# 3.28 HR Reports
from .HRReports.Voluntarys import (
    VOLUNTARY_SEPARATION_TYPES,
)  # noqa: F401
from .HRReports.Tenures import (
    TENURE_BANDS,
)  # noqa: F401
from .HRReports.Ages import (
    AGE_BANDS,
)  # noqa: F401
from .HRReports._helpers import (
    _dept_choices,
    _report_department,
    _report_period,
    _month_end,
    _age,
    _tenure_band,
    _age_band,
    _headcount_at,
)  # noqa: F401
from .HRReports.HrIndex import (
    hr_reports_index,
)  # noqa: F401
from .HRReports.Headcount import (
    headcount_report,
)  # noqa: F401
from .HRReports.Attrition import (
    attrition_report,
)  # noqa: F401
from .HRReports.Diversity import (
    diversity_report,
)  # noqa: F401
from .HRReports.Cost import (
    cost_report,
)  # noqa: F401
from .HRReports.Hiring import (
    hiring_report,
)  # noqa: F401

# 3.29 Attendance Reports
from .AttendanceReports._helpers import (
    _ATT_NON_WORKING,
    _DOW_LABELS,
    _attendance_base,
    _attendance_pe_tracked,
    _fold_att,
)  # noqa: F401
from .AttendanceReports.AttendanceIndex import (
    attendance_reports_index,
)  # noqa: F401
from .AttendanceReports.AttendanceSummary import (
    attendance_summary_report,
)  # noqa: F401
from .AttendanceReports.LateEarly import (
    late_early_report,
)  # noqa: F401
from .AttendanceReports.Absenteeism import (
    absenteeism_report,
)  # noqa: F401
from .AttendanceReports.Overtime import (
    overtime_report,
)  # noqa: F401

# 3.30 Leave Reports
from .LeaveReports._helpers import (
    _report_year,
    _leave_years,
    _annotated_allocations,
    _alloc_balance,
)  # noqa: F401
from .LeaveReports.LeaveIndex import (
    leave_reports_index,
)  # noqa: F401
from .LeaveReports.LeaveRegister import (
    leave_register_report,
)  # noqa: F401
from .LeaveReports.LeaveLiability import (
    leave_liability_report,
)  # noqa: F401
from .LeaveReports.CompOff import (
    comp_off_report,
)  # noqa: F401
from .LeaveReports.LeaveTrend import (
    leave_trend_report,
)  # noqa: F401

# 3.31 Payroll Reports
from .PayrollReports._helpers import (
    _fy_choices,
    _report_financial_year,
    _cc_choices,
    _report_cost_center,
    _grade_choices,
    _report_job_grade,
)  # noqa: F401
from .PayrollReports.PayrollIndex import (
    payroll_reports_index,
)  # noqa: F401
from .PayrollReports.SalaryRegister import (
    salary_register_report,
)  # noqa: F401
from .PayrollReports.Tax import (
    tax_report,
)  # noqa: F401
from .PayrollReports.Statutory import (
    statutory_report,
)  # noqa: F401
from .PayrollReports.Ctc import (
    ctc_report,
)  # noqa: F401
from .PayrollReports.CostCenter import (
    cost_center_report,
)  # noqa: F401

# 3.32 Analytics Dashboard
from .AnalyticsDashboard._helpers import (
    _can_share_hrdash,
    _can_manage_hrdash,
    _bench_target,
)  # noqa: F401
from .AnalyticsDashboard.Dashboard import (
    hr_dashboard_list,
    hr_dashboard_create,
    hr_dashboard_detail,
    hr_dashboard_edit,
    hr_dashboard_delete,
)  # noqa: F401
from .AnalyticsDashboard.Widget import (
    hr_widget_create,
    hr_widget_edit,
    hr_widget_delete,
    hr_widget_move,
)  # noqa: F401
from .AnalyticsDashboard.Executive import (
    executive_dashboard,
)  # noqa: F401
from .AnalyticsDashboard.Predictive import (
    predictive_analytics,
)  # noqa: F401
from .AnalyticsDashboard.Benchmarking import (
    benchmarking,
)  # noqa: F401

# 3.33 Asset Management
from .AssetManagement.Asset import (
    asset_list,
    asset_create,
    asset_detail,
    asset_edit,
    asset_delete,
    asset_assign,
    asset_return,
    asset_retire,
    asset_dispose,
)  # noqa: F401
from .AssetManagement.Assetmaintenance import (
    assetmaintenance_list,
    assetmaintenance_create,
    assetmaintenance_detail,
    assetmaintenance_edit,
    assetmaintenance_delete,
    assetmaintenance_complete,
)  # noqa: F401

# 3.34 Expense Management
from .ExpenseManagement.Expensecategory import (
    expensecategory_list,
    expensecategory_create,
    expensecategory_detail,
    expensecategory_edit,
    expensecategory_delete,
)  # noqa: F401
from .ExpenseManagement.Expenseclaim import (
    expenseclaim_list,
    expenseclaim_create,
    expenseclaim_detail,
    expenseclaim_edit,
    expenseclaim_delete,
    expenseclaim_submit,
    expenseclaim_manager_approve,
    expenseclaim_approve,
    expenseclaim_reject,
    expenseclaim_cancel,
    expenseclaim_reimburse,
)  # noqa: F401
from .ExpenseManagement._helpers import (
    _get_own_claim,
)  # noqa: F401
from .ExpenseManagement.Expenseclaimline import (
    expenseclaimline_add,
    expenseclaimline_edit,
    expenseclaimline_delete,
)  # noqa: F401

# 3.35 Travel Management
from .TravelManagement.Travelpolicy import (
    travelpolicy_list,
    travelpolicy_create,
    travelpolicy_detail,
    travelpolicy_edit,
    travelpolicy_delete,
)  # noqa: F401
from .TravelManagement.Travelrequest import (
    travelrequest_list,
    travelrequest_create,
    travelrequest_detail,
    travelrequest_edit,
    travelrequest_delete,
    travelrequest_submit,
    travelrequest_cancel,
    travelrequest_approve,
    travelrequest_reject,
    travelrequest_approve_advance,
    travelrequest_mark_advance_paid,
    travelrequest_generate_settlement,
    travelrequest_complete,
)  # noqa: F401
from .TravelManagement.Travelbooking import (
    travelbooking_add,
    travelbooking_edit,
    travelbooking_delete,
)  # noqa: F401

# 3.36 Helpdesk
from .Helpdesk.Helpdeskslapolicy import (
    helpdesksla_list,
    helpdesksla_create,
    helpdesksla_detail,
    helpdesksla_edit,
    helpdesksla_delete,
)  # noqa: F401
from .Helpdesk.Helpdeskcategory import (
    helpdeskcategory_list,
    helpdeskcategory_create,
    helpdeskcategory_detail,
    helpdeskcategory_edit,
    helpdeskcategory_delete,
)  # noqa: F401
from .Helpdesk._helpers import (
    _ticket_is_agent,
    _ticket_can_view,
    _ticket_mark_first_response,
)  # noqa: F401
from .Helpdesk.Helpdeskticket import (
    ticket_list,
    ticket_create,
    ticket_detail,
    ticket_edit,
    ticket_delete,
    ticket_assign,
    ticket_start,
    ticket_waiting,
    ticket_resolve,
    ticket_close,
    ticket_reopen,
    ticket_cancel,
    ticket_feedback,
)  # noqa: F401
from .Helpdesk.Knowledgearticle import (
    knowledgearticle_list,
    knowledgearticle_create,
    knowledgearticle_detail,
    knowledgearticle_edit,
    knowledgearticle_delete,
    knowledgearticle_helpful,
)  # noqa: F401

# 3.37 Compensation & Benefits
from .CompensationBenefits.Salarybenchmark import (
    salarybenchmark_list,
    salarybenchmark_create,
    salarybenchmark_detail,
    salarybenchmark_edit,
    salarybenchmark_delete,
)  # noqa: F401
from .CompensationBenefits.Benefitplan import (
    benefitplan_list,
    benefitplan_create,
    benefitplan_detail,
    benefitplan_edit,
    benefitplan_delete,
)  # noqa: F401
from .CompensationBenefits.Employeebenefitenrollment import (
    employeebenefitenrollment_list,
    employeebenefitenrollment_create,
    employeebenefitenrollment_detail,
    employeebenefitenrollment_edit,
    employeebenefitenrollment_delete,
    employeebenefitenrollment_enroll,
    employeebenefitenrollment_waive,
    employeebenefitenrollment_terminate,
)  # noqa: F401
from .CompensationBenefits._helpers import (
    _enrollment_decide,
)  # noqa: F401
from .CompensationBenefits.Equitygrant import (
    equitygrant_list,
    equitygrant_create,
    equitygrant_detail,
    equitygrant_edit,
    equitygrant_delete,
    equitygrant_record_exercise,
)  # noqa: F401

# 3.38 Talent Management & Succession
from .TalentManagement.Talentpool import (
    talentpool_list,
    talentpool_create,
    talentpool_detail,
    talentpool_edit,
    talentpool_delete,
)  # noqa: F401
from .TalentManagement.Talentpoolmembership import (
    talentpoolmembership_list,
    talentpoolmembership_create,
    talentpoolmembership_detail,
    talentpoolmembership_edit,
    talentpoolmembership_delete,
)  # noqa: F401
from .TalentManagement.NineBox import (
    talent_nine_box,
)  # noqa: F401
from .TalentManagement.Successionplan import (
    successionplan_list,
    successionplan_create,
    successionplan_detail,
    successionplan_edit,
    successionplan_delete,
)  # noqa: F401
from .TalentManagement.Successioncandidate import (
    successioncandidate_add,
    successioncandidate_edit,
    successioncandidate_delete,
)  # noqa: F401

# 3.39 Compliance & Legal
from .ComplianceLegal.Employmentcontract import (
    employmentcontract_list,
    employmentcontract_create,
    employmentcontract_detail,
    employmentcontract_edit,
    employmentcontract_delete,
)  # noqa: F401
from .ComplianceLegal._helpers import (
    _annotate_policy_acks,
)  # noqa: F401
from .ComplianceLegal.Hrpolicy import (
    hrpolicy_list,
    hrpolicy_create,
    hrpolicy_detail,
    hrpolicy_edit,
    hrpolicy_delete,
    hrpolicy_publish,
)  # noqa: F401
from .ComplianceLegal.Policyacknowledgment import (
    policyacknowledgment_list,
    policyacknowledgment_acknowledge,
)  # noqa: F401
from .ComplianceLegal.Grievance import (
    grievance_list,
    grievance_create,
    grievance_detail,
    grievance_edit,
    grievance_delete,
    grievance_assign,
    grievance_resolve,
    grievance_close,
    grievance_withdraw,
)  # noqa: F401
from .ComplianceLegal.Complianceregister import (
    complianceregister_list,
    complianceregister_create,
    complianceregister_detail,
    complianceregister_edit,
    complianceregister_delete,
)  # noqa: F401

# 3.40 Workforce Planning
from .WorkforcePlanning._helpers import (
    _annotate_plan_totals,
    _normalize_baseline,
)  # noqa: F401
from .WorkforcePlanning.Workforceplan import (
    workforceplan_list,
    workforceplan_create,
    workforceplan_detail,
    workforceplan_edit,
    workforceplan_delete,
)  # noqa: F401
from .WorkforcePlanning.Workforceplanline import (
    workforceplanline_add,
    workforceplanline_edit,
    workforceplanline_delete,
)  # noqa: F401
from .WorkforcePlanning.Workforcescenario import (
    workforcescenario_list,
    workforcescenario_create,
    workforcescenario_detail,
    workforcescenario_edit,
    workforcescenario_delete,
)  # noqa: F401
from .WorkforcePlanning.Employeeskill import (
    employeeskill_list,
    employeeskill_create,
    employeeskill_detail,
    employeeskill_edit,
    employeeskill_delete,
)  # noqa: F401
from .WorkforcePlanning.GapAnalysis import (
    workforce_gap_analysis,
)  # noqa: F401
from .WorkforcePlanning.Analytics import (
    workforce_analytics,
)  # noqa: F401

# 3.41 Employee Engagement & Wellbeing
from .EmployeeEngagement._helpers import (
    _can_manage_action_plan,
)  # noqa: F401
from .EmployeeEngagement.Surveyactionplan import (
    surveyactionplan_list,
    surveyactionplan_create,
    surveyactionplan_detail,
    surveyactionplan_edit,
    surveyactionplan_delete,
)  # noqa: F401
from .EmployeeEngagement.Wellbeingprogram import (
    wellbeingprogram_list,
    wellbeingprogram_create,
    wellbeingprogram_detail,
    wellbeingprogram_edit,
    wellbeingprogram_delete,
)  # noqa: F401
from .EmployeeEngagement.Wellbeingparticipation import (
    wellbeingparticipation_add,
    wellbeingparticipation_edit,
    wellbeingparticipation_delete,
)  # noqa: F401
from .EmployeeEngagement.Flexibleworkarrangement import (
    flexibleworkarrangement_list,
    flexibleworkarrangement_create,
    flexibleworkarrangement_detail,
    flexibleworkarrangement_edit,
    flexibleworkarrangement_delete,
    flexibleworkarrangement_submit,
    flexibleworkarrangement_cancel,
    flexibleworkarrangement_approve,
    flexibleworkarrangement_reject,
)  # noqa: F401
